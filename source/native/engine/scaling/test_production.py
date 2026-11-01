"""Differential original/scaled-prefix kernels with explicit emulated memory bounds."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json,random,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
regs=[getattr(R,'UC_M68K_REG_'+x)for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
rng=random.Random(0x15972)
def fixture(path,layout):
 rd=HunkReader();assert rd.read_file(str(path))==0 and rd.build_segments();bases=([0x100000,0x200000,0x300000,0x400000,0x410000,0x420000,0x430000,0x440000,0xa80000]if layout==0 else[0x180000,0x280000,0x380000,0x480000,0x490000,0x4a0000,0x4b0000,0x4c0000,0xb00000])
 cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000);section=0
 for h in rd.hunks:
  section=h.get('hunk_no',section)
  if 'data'in h:cpu.mem_write(bases[section],h['data'])
  if h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():
    for o in offsets:
     a=bases[section]+o;cpu.mem_write(a,struct.pack('>I',int.from_bytes(cpu.mem_read(a,4),'big')+bases[target]))
 return cpu,bases

def stream():
 out=bytearray()
 for _ in range(3000):
  color=rng.choice((0,0,0,1,6,15));count=rng.choice((1,2,4,7,8,9,15,16,127,255,256));out.append(color<<4|(count if count<16 else 0))
  if count>=16:out.append(count&255)
 return bytes(out)
capture=(ROOT/'tests/fixtures/production-final-ram.bin').read_bytes()
G=0x286110
def captured(off,n):return int.from_bytes(capture[G+off:G+off+n],'big')
cases=[dict(width=50,height=62,phase=66,sy=128,sx=128,resume=0,ccr=ccr) for ccr in (0,31)]
profiles=[];checks=0
for layout in (0,1):
 old=fixture(Path(json.loads((BUILD / 'rebase-input.json').read_text())['source_image']),layout);new=fixture(BUILD / 'Monkey_Talkie_Scaled',layout)
 for entry in (0x158ee,0x15a14):
  for number,case in enumerate(cases):
   encoded=capture[0x2c3d9a:0x2c3d9a+865];initial=[rng.randrange(1<<32)for _ in regs];initial[-1]=0x90f000
   width,height=case['width'],case['height'];palette=capture[G+0x5cdb:G+0x5cdb+16];payload=b'Z'*0x30020;mask=capture[captured(0x6de0,4):captured(0x6de0,4)+0x8000];outputs=[];counts=[];cycles=[]
   x=121;y=65;clip=144;direction=1;partial=0;partialcolor=0;resetphase=66
   for cpu,bases in (old,new):
    g=bases[2]
    def put(off,val,n):cpu.mem_write(g+off,int(val).to_bytes(n,'big'))
    cpu.mem_write(0x500000,encoded);cpu.mem_write(0x600000,payload);cpu.mem_write(0x680000,mask);cpu.mem_write(0x90ee00,bytes(0x200));cpu.mem_write(0x90f000,struct.pack('>I',0xa00000))
    for off,val,n in ((0x59b8,0x500000,4),(0x5c16,0x600410,4),(0x5c22,0x680000+x//8,4),(0x6de0,0x680000,4),(0x6de4,5920,2),(0x6df2,x,2),(0x6df4,y,2),(0x6df6,y,2),(0x6df8,clip,2),(0x6dfc,direction,2),(0x6dec,width&255,1),(0x6ded,height&255,1),(0x6de6,partial,1),(0x6de7,partialcolor,1),(0x6dfa,case['resume'],1),(0x59ae,case['sy'],2),(0x59ac,case['sx'],2),(0x6e00,rng.randrange(256),1),(0x6e01,case['phase'],1),(0x6e02,resetphase,1)):
     # Xphase must be identical in both executions.
     if off==0x6e00:val=104
     put(off,val,n)
    cpu.mem_write(g+0x5cdb,palette);glob=bytes(cpu.mem_read(g,29312))
    cpu.reg_write(R.UC_M68K_REG_SR,case['ccr'])
    for reg,val in zip(regs,initial):cpu.reg_write(reg,val)
    from core_cycles import CoreClock
    clock=CoreClock(cpu,R)
    count=[0]; memory_writes=[]
    def trace(*args):
     count[0]+=1;clock.trace(*args)
    def guard(uc,access,address,size,value,unused):
     memory_writes.append((address,size,value))
     assert 0x90ee00<=address and address+size<=0x90f000 or 0x600010<=address and address+size<=0x630010,(hex(address),size)
    wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard);ch=cpu.hook_add(unicorn.UC_HOOK_CODE,trace)
    cpu.emu_start(bases[0]+entry,0xa00000,count=3000000);cpu.hook_del(wh);cpu.hook_del(ch);cycles.append(clock.finish(0xa00000))
    assert cpu.reg_read(R.UC_M68K_REG_PC)==0xa00000,(layout,entry,number)
    cpu.mem_write(0xa00000,bytes.fromhex('40f900a00100'));cpu.emu_start(0xa00000,0xa00006,count=1)
    assert bytes(cpu.mem_read(g,29312))==glob and bytes(cpu.mem_read(0x680000,len(mask)))==mask
    assert bytes(cpu.mem_read(0x600000,16))==b'Z'*16 and bytes(cpu.mem_read(0x630010,16))==b'Z'*16
    outputs.append((tuple(cpu.reg_read(r)for r in regs),bytes(cpu.mem_read(0xa00100,2)),bytes(cpu.mem_read(0x600000,len(payload))),bytes(cpu.mem_read(0x90ee00,0x204)),tuple(memory_writes)))
    counts.append(count[0])
   if outputs[0]!=outputs[1]:
    print('DIFF',[(i,len(a) if hasattr(a,'__len__') else 0,[(j,x,y)for j,(x,y)in enumerate(zip(a,b))if x!=y][:12])for i,(a,b)in enumerate(zip(outputs[0],outputs[1]))if a!=b]);raise AssertionError((layout,hex(entry),number,case))
   checks+=1
   if layout==0 and number<3:profiles.append(dict(entry=hex(entry),case=case,old=counts[0],new=counts[1],old_core_cycles_estimate=cycles[0],new_core_cycles_estimate=cycles[1]))
report=dict(module_sha256=hashlib.sha256((BUILD / 'Monkey_Talkie_Scaled').read_bytes()).hexdigest(),cases=checks,all_registers_CCR_stack_framebuffer_globals_masks_exact=True,all_memory_write_sequences_exact=True,source_phase=66,source_scale_xy=128,input_CCR_values=[0,31],source_horizontal_phase=104,two_layouts=True,write_bounds_guarded=True,metric='compiled_instructions_not_cycles',actual_runtime=False,profiles=profiles)
(BUILD / 'production-kernel-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='profiles'},indent=2))
