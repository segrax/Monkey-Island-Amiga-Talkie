"""Compare packed resource XOR with the original loop, including key aliasing."""
from pathlib import Path
import sys,hashlib,json,random,struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
P=artifact_dir('io');meta=json.loads((P/'kernel.json').read_text());blob=(P/'fast.bin').read_bytes()
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
original=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data' in h)
assert hashlib.sha256(original[0x126ac:0x126c0]).hexdigest()==meta['original_decode_sha256']
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
rng=random.Random(0x126ac);cases=[]
for size in (0,1,2,3,4,5,7,8,9,15,16,17,31,32,255,256,1023,4096,16384):
 for align in (0,1,2,3):
  for key in (0,0x69,0xff):cases.append((size,align,key,None))
for size in (1,2,3,7,16,255,4096):
 for position in (0,size//2,size-1):cases.append((size,0,0x69,position))
profiles=[]
for case,(size,align,key,alias) in enumerate(cases):
 dest=0x600010+align;g=0x700000 if alias is None else dest+alias-0x671c
 data=bytearray(rng.randbytes(size+32));data[:16]=b'Z'*16;data[-16:]=b'Z'*16
 initial=[rng.getrandbits(32) for _ in regs];initial[6]=size;initial[11]=dest;initial[12]=g;initial[15]=0x90f000;outputs=[];counts=[];ccr=case&31
 for entry,stop in ((0x1126ac,0x1126c0),(0x400000+meta['entries']['_decode_fast'],0xa00000)):
  cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000)
  cpu.mem_write(0x100000,original);cpu.mem_write(0x400000,blob);cpu.mem_write(dest-16,bytes(data));cpu.mem_write(g+0x671c,bytes([key]));cpu.mem_write(0x90ee00,bytes(0x200));cpu.mem_write(0x90f000,struct.pack('>I',0xa00000))
  cpu.reg_write(R.UC_M68K_REG_SR,ccr)
  for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
  count=[0]
  def trace(*args):count[0]+=1
  def guard(uc,access,address,n,value,unused):assert dest<=address and address+n<=dest+size or 0x90ee00<=address and address+n<=0x90f000,(case,hex(address),n)
  cpu.hook_add(unicorn.UC_HOOK_CODE,trace);wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard)
  cpu.emu_start(entry,stop,count=3000000);assert cpu.reg_read(R.UC_M68K_REG_PC)==stop;cpu.hook_del(wh)
  cpu.mem_write(0xa00000,bytes.fromhex('40f900a00100'));cpu.emu_start(0xa00000,0xa00006,count=1)
  state=[cpu.reg_read(r) for r in regs];state[-1]=initial[-1] # The standalone helper consumes its injected return address.
  outputs.append((state,bytes(cpu.mem_read(0xa00100,2)),bytes(cpu.mem_read(dest-16,size+32)),bytes(cpu.mem_read(g+0x671c,1))))
  counts.append(count[0])
 assert outputs[0]==outputs[1],(case,size,align,key,alias,[(i,a,b) for i,(a,b) in enumerate(zip(outputs[0],outputs[1])) if a!=b])
 if size==16384 and key==0x69:profiles.append(dict(size=size,alignment=align,old_instructions=counts[0],new_instructions=counts[1]))
report=dict(cases=len(cases),all_registers_CCR_and_bytes_exact=True,key_alias_fallback=True,guarded_writes=True,profiles=profiles)
(P/'decode-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

# Execute the final relocated wrapper, preserving its fread call sequence even
# for short reads: the original XORs the entire requested chunk after EOF.
image=P.parent/'module/Monkey_Talkie_Test'
if image.exists():
 q=HunkReader();assert q.read_file(str(image))==0 and q.build_segments()
 index=json.loads(image.with_name('module.json').read_text())['exports']['_decode_fast']['hunk']
 wrapper_cases=0
 for length in (0,1,2,3,17,16383,16384,16385,32769):
  for odd in (0,1):
   for short in (0,1,2):
    outputs=[]
    for fast in (False,True):
     cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000)
     base=0x200000 if fast else 0x100000
     cpu.mem_write(base,original)
     if fast:
      section=0
      for h in q.hunks:
       section=h.get('hunk_no',section)
       if section in (0,index) and 'data'in h:cpu.mem_write(base if section==0 else 0x400000,h['data'])
       if section in (0,index) and h['type_name']=='HUNK_ABSRELOC32':
        for target,offsets in h['reloc'].items():
         for offset in offsets:
          at=(base if section==0 else 0x400000)+offset
          add=base if target==0 else 0x400000 if target==index else 0
          cpu.mem_write(at,struct.pack('>I',int.from_bytes(cpu.mem_read(at,4),'big')+add))
     dest=0x600010+odd;g=0x700000;stack=0x90f000
     cpu.mem_write(dest-16,b'Z'*(length+32));cpu.mem_write(g+0x671c,b'\x69');cpu.mem_write(g+0x5984,struct.pack('>I',0x710000));cpu.mem_write(stack,struct.pack('>III',0xa00000,dest,length));cpu.mem_write(0x800000,bytes.fromhex('4e75'))
     initial=[0x12340000+i for i in range(16)];initial[12]=g;initial[-1]=stack
     cpu.reg_write(R.UC_M68K_REG_SR,wrapper_cases&31)
     for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
     calls=[]
     def fread(uc,pc,n,unused):
      sp=uc.reg_read(R.UC_M68K_REG_A7)
      block=bytes(uc.mem_read(sp+4,12));to,size,count,file=struct.unpack('>IHHI',block);calls.append((to,size,count,file))
      assert size==1 and file==0x710000
      got=count if short==0 else 0 if short==1 else count//2
      if got:uc.mem_write(to,bytes((i+len(calls)*37)&255 for i in range(got)))
      for reg,value in ((R.UC_M68K_REG_D0,got),(R.UC_M68K_REG_D1,0xaabbccdd),(R.UC_M68K_REG_A0,0x76543210),(R.UC_M68K_REG_A1,0x12345678)):uc.reg_write(reg,value)
      uc.reg_write(R.UC_M68K_REG_PC,0x800000)
     def guard(uc,access,address,n,value,unused):assert dest<=address and address+n<=dest+length or stack-512<=address and address+n<=stack,(length,odd,short,hex(address),n)
     cpu.hook_add(unicorn.UC_HOOK_CODE,fread,begin=base+0x16d80,end=base+0x16d80)
     wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard)
     cpu.emu_start(base+0x12676,0xa00000,count=3000000);assert cpu.reg_read(R.UC_M68K_REG_PC)==0xa00000;cpu.hook_del(wh)
     cpu.mem_write(0xa00000,bytes.fromhex('40f900a00100'));cpu.emu_start(0xa00000,0xa00006,count=1)
     outputs.append((tuple(cpu.reg_read(r) for r in regs),bytes(cpu.mem_read(0xa00100,2)),bytes(cpu.mem_read(dest-16,length+32)),calls,bytes(cpu.mem_read(stack,12))))
    assert outputs[0]==outputs[1],(length,odd,short)
    wrapper_cases+=1
 report['linked_wrapper_cases']=wrapper_cases
 report['original_read_chunks_and_short_read_semantics_exact']=True
 (P/'decode-validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS final resource wrapper:',wrapper_cases,'cases, including short reads and chunk boundaries')
