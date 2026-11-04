from pathlib import Path
import sys,json,struct,hashlib
S=Path(__file__).resolve().parents[2];sys.path.insert(0,str(S/'engine'));from paths import engine_build;B=engine_build();sys.path.insert(0,str(S/'tools/python'))
import unicorn
from unicorn import m68k_const as R
from amitools.binfmt.hunk.HunkReader import HunkReader
REG=[getattr(R,'UC_M68K_REG_'+s)for s in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
r=HunkReader();assert r.read_file(str(B/'module/Monkey_Talkie_Test'))==0 and r.build_segments();code=next(h['data']for h in r.hunks if h.get('hunk_no')==0 and 'data'in h);base=0x100000;raw=code[0x14ea:0x150c];assert raw[0x1508-0x14ea:0x150a-0x14ea]==bytes.fromhex('4294');old=bytearray(raw);old[0x1508-0x14ea:0x150a-0x14ea]=bytes.fromhex('4290')
cases=0
for model in (R.UC_CPU_M68K_M68000,R.UC_CPU_M68K_M68020,R.UC_CPU_M68K_M68030):
 for ccr in range(32):
  for pcm in (0x500000,0x500002):
   for stale in (0,1,0x330000,0x330001,0x500000,0x500003,0xdff0a0):
    outputs=[]
    for fixed in (False,True):
     c=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);c.ctl_set_cpu_model(model);c.mem_map(0,0x1000000);c.mem_write(base+0x14ea,raw if fixed else bytes(old));c.mem_write(pcm,b'ABCD');c.mem_write(base+0x176e,b'Z'*128);c.mem_write(0x900000,b'Y'*64)
     c.reg_write(R.UC_M68K_REG_SR,ccr);initial=[0x12340000+n for n in range(16)];initial[0]=0x600000;initial[1]=pcm;initial[8]=stale if fixed else pcm;initial[-1]=0x900040
     for reg,value in zip(REG,initial):c.reg_write(reg,value)
     writes=[]
     def wr(uc,access,a,n,v,_):writes.append((a,n,v))
     h=c.hook_add(unicorn.UC_HOOK_MEM_WRITE,wr);c.emu_start(base+0x14ea,base+0x150c,count=100);c.hook_del(h)
     assert c.reg_read(REG[8])==initial[8]
     assert bytes(c.mem_read(pcm,4))==bytes(4)
     c.mem_write(0xa00000,bytes.fromhex('40f900a00100'));c.emu_start(0xa00000,0xa00006,count=1)
     values=[c.reg_read(reg)for reg in REG];values[8]=0
     outputs.append((values,bytes(c.mem_read(0xa00100,2)),bytes(c.mem_read(base+0x176e,128)),bytes(c.mem_read(0x900000,64)),writes))
    assert outputs[0]==outputs[1],(model,ccr,pcm,hex(stale))
    assert [w for w in writes if w[0]==pcm]==[(pcm,4,0)]
    assert all(a!=stale for a,n,v in writes if stale!=pcm)
    cases+=1
report={'PASS':True,'cases':cases,'models':['68000','68020','68030'],'all32CCR':True,'reference':'Original valid caller A0=D1 versus fixed arbitrary stale A0','scope':'14EA through150A MOVEA D0,A4; remaining original initialization unchanged and not executed','ordered_writes_exact':True,'PCM_D1_only_cleared':True,'stale_A0_unchanged_and_never_accessed_for_write':True,'all_other_GPR_CCR_stack_playerstate_exact':True}
(B/'init-clear-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
