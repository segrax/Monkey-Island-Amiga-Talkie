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
obj=HunkReader();assert obj.read_file(str(BUILD/'scaled_kernels.o'))==0
symbols={name:offset for h in obj.hunks if h['type_name']=='HUNK_SYMBOL' for name,offset in h['symbols']}
clear_body=symbols['clear_one_body']
visible_body=symbols['visible_one_body']
visible_hits=[0]
def fixture(path,layout):
 rd=HunkReader();assert rd.read_file(str(path))==0 and rd.build_segments();bases=([0x100000,0x200000,0x300000,0x400000,0xa80000]if layout==0 else[0x180000,0x280000,0x380000,0x480000,0xb00000])
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
cases=[]
for phase in range(256):
 cases.append(dict(width=50,height=62,phase=phase,sy=128,sx=128,resume=0,ccr=phase&31,kind='clear'))
for kind in ('mask-first','mask-last','mask-wide','odd','reset','clip','x','left','alias'):
 for phase in (0,1,127,128,255):
  cases.append(dict(width=50,height=62,phase=phase,sy=128,sx=128,resume=0,ccr=phase&31,kind=kind))
profiles=[];checks=0;fast_hits=[0];hit_kinds={}
for layout in (0,1):
 old=fixture(ROOT/'data/original/Monkey_Island',layout);new=fixture(BUILD / 'Monkey_Scaled',layout)
 for entry in (0x158ee,):
  for number,case in enumerate(cases):
   before_hits=fast_hits[0];before_visible=visible_hits[0]
   encoded=stream();initial=[rng.randrange(1<<32)for _ in regs];initial[-1]=0x90f000
   width,height=case['width'],case['height'];palette=bytes(range(16));payload=b'Z'*0x30020;mask=bytearray(0x8000)
   if case['kind']=='mask-first':mask[15]=255
   if case['kind']=='mask-last':mask[61*40+21]=255
   if case['kind']=='mask-wide':mask[12]=255
   outputs=[];counts=[]
   kind=case['kind'];x=121;y=65;clip=144;direction=1;partial=0;partialcolor=0;resetphase=case['phase']
   if kind=='x':x=300
   if kind=='left':direction=65535
   if kind=='clip':clip=100
   maskbase=0x680001 if kind=='odd' else 0x680000
   if kind=='alias':maskbase=0x600800
   for cpu,bases in (old,new):
    g=bases[2]
    def put(off,val,n):cpu.mem_write(g+off,int(val).to_bytes(n,'big'))
    cpu.mem_write(0x500000,encoded);cpu.mem_write(0x600000,payload);cpu.mem_write(maskbase,bytes(mask));cpu.mem_write(0x90ee00,bytes(0x200));cpu.mem_write(0x90f000,struct.pack('>I',0xa00000))
    for off,val,n in ((0x59b8,0x500000,4),(0x5c16,0x600410,4),(0x5c22,maskbase+x//8,4),(0x6de0,maskbase,4),(0x6de4,0x4000,2),(0x6df2,x,2),(0x6df4,y,2),(0x6df6,y+1 if kind=='reset' else y,2),(0x6df8,clip,2),(0x6dfc,direction,2),(0x6dec,width&255,1),(0x6ded,height&255,1),(0x6de6,partial,1),(0x6de7,partialcolor,1),(0x6dfa,case['resume'],1),(0x59ae,case['sy'],2),(0x59ac,case['sx'],2),(0x6e00,rng.randrange(256),1),(0x6e01,case['phase'],1),(0x6e02,resetphase,1)):
     # Xphase must be identical in both executions.
     if off==0x6e00:val=case['phase']^127
     put(off,val,n)
    cpu.mem_write(g+0x5cdb,palette);glob=bytes(cpu.mem_read(g,29312))
    cpu.reg_write(R.UC_M68K_REG_SR,case['ccr'])
    for reg,val in zip(regs,initial):cpu.reg_write(reg,val)
    count=[0]
    def trace(uc,address,size,unused):
     count[0]+=1
     if address==bases[3]+clear_body:fast_hits[0]+=1
     if address==bases[3]+visible_body:visible_hits[0]+=1
    def guard(uc,access,address,size,value,unused):assert 0x90ee00<=address and address+size<=0x90f000 or 0x600010<=address and address+size<=0x630010,(hex(address),size)
    wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard);ch=cpu.hook_add(unicorn.UC_HOOK_CODE,trace)
    cpu.emu_start(bases[0]+entry,0xa00000,count=3000000);cpu.hook_del(wh);cpu.hook_del(ch)
    assert cpu.reg_read(R.UC_M68K_REG_PC)==0xa00000,(layout,entry,number)
    cpu.mem_write(0xa00000,bytes.fromhex('40f900a00100'));cpu.emu_start(0xa00000,0xa00006,count=1)
    assert bytes(cpu.mem_read(g,29312))==glob
    if kind!='alias':assert bytes(cpu.mem_read(maskbase,len(mask)))==bytes(mask)
    assert bytes(cpu.mem_read(0x600000,16))==b'Z'*16 and bytes(cpu.mem_read(0x630010,16))==b'Z'*16
    outputs.append((tuple(cpu.reg_read(r)for r in regs),bytes(cpu.mem_read(0xa00100,2)),bytes(cpu.mem_read(0x600000,len(payload))),bytes(cpu.mem_read(0x90ee00,0x204))))
    counts.append(count[0])
   if outputs[0]!=outputs[1]:
    print('DIFF',[(i,len(a) if hasattr(a,'__len__') else 0,[(j,x,y)for j,(x,y)in enumerate(zip(a,b))if x!=y][:12])for i,(a,b)in enumerate(zip(outputs[0],outputs[1]))if a!=b]);raise AssertionError((layout,hex(entry),number,case))
   assert visible_hits[0]-before_visible==(1 if kind in ('mask-first','mask-last','mask-wide') else 0),(kind,visible_hits[0]-before_visible)
   delta=fast_hits[0]-before_hits
   assert delta==(1 if kind in ('clear','left') else 0),(kind,delta)
   hit_kinds[kind]=hit_kinds.get(kind,0)+delta
   checks+=1
   if layout==0 and number<3:profiles.append(dict(entry=hex(entry),case=case,old=counts[0],new=counts[1]))
assert fast_hits[0]>=512,fast_hits
report=dict(visible_path_calls=visible_hits[0],clear_fast_path_hits=fast_hits[0],fast_hits_by_kind=hit_kinds,module_sha256=hashlib.sha256((BUILD / 'Monkey_Scaled').read_bytes()).hexdigest(),cases=checks,all_registers_CCR_stack_framebuffer_globals_exact=True,nonaliased_masks_unchanged=True,all256phases=True,all32CCR=True,clear_and_fallback_edges=True,two_layouts=True,write_bounds_guarded=True,metric='compiled_instructions_not_cycles',actual_runtime=False,profiles=profiles)
(BUILD / 'clear-mask-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='profiles'},indent=2))
