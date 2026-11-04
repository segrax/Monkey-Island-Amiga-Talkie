"""Execute original and relaxed stripe kernels against identical bounded fixtures."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib, json, random, struct, sys
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
from timing import difference
gen=json.loads((BUILD / 'generation.json').read_text()); kernel=(BUILD / 'stripe.bin').read_bytes()
regs=[getattr(R,'UC_M68K_REG_'+s) for s in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
rng=random.Random(0x15190)
r=HunkReader();assert r.read_file(str(ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
oldcode=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)

def cpu_new(layout,clone):
 c=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);c.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);c.mem_map(0,0x1000000)
 base=0x100000+layout*0x40000; g=0x200000+layout*0x40000
 c.mem_write(base,oldcode)
 section=0
 for h in r.hunks:
  section=h.get('hunk_no',section)
  if section==0 and h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():
    if target!=2:continue
    for off in offsets:c.mem_write(base+off,struct.pack('>I',int.from_bytes(c.mem_read(base+off,4),'big')+g))
 entry=base+0x15190
 if clone:
  entry=0x400000+layout*0x40000;c.mem_write(entry,kernel)
  for off in gen['absolute_h2_relocations']:c.mem_write(entry+off,struct.pack('>I',int.from_bytes(c.mem_read(entry+off,4),'big')+g))
 return c,g,entry,base

def encoded(mode, opcode=None):
 if opcode is not None:
  if opcode<0x80:head=bytes([opcode])+(bytes([0]) if opcode>>4==0 else b'')
  elif opcode<0xc0:head=bytes([opcode])+(bytes([0]) if opcode&63==0 else b'')
  else:head=bytes([opcode,0x3e])+(bytes([0]) if opcode&63==0 else b'')
  return head+b'\x00\x00'*3000
 b=bytearray()
 for _ in range(5000):
  m=mode if mode<3 else rng.randrange(3);n=rng.choice((0,1,2,3,7,8,15,31,63,64,127,255))
  a,bcol=rng.randrange(16),rng.randrange(16)
  if m==0:
   if 1<=n<=7:b.append(n<<4|a)
   else:b.extend((a,n))
  elif m==1:
   if 1<=n<=63:b.append(0x80|n)
   else:b.extend((0x80,n))
  else:
   if 1<=n<=63:b.extend((0xc0|n,a<<4|bcol))
   else:b.extend((0xc0,a<<4|bcol,n))
 return bytes(b)

cases=[(h,mode,ccr,mask) for h in (1,2,7,8,16,63,127,128,144,200,255,256) for mode in range(4) for ccr,mask in ((0,0),(31,1))]
cases += [(1+i*8,3,i,i&1) for i in range(32)]
cases += [(h,3,h&31,h&1) for h in range(1,257)]
cases=[(*case,None,False) for case in cases]
cases += [(256,3,ccr,mask,opcode,alias) for alias in (False,True) for opcode in range(256) for ccr,mask in ((0,0),(31,1))]
profiles=[];checks=0
for layout in (0,1):
 pairs=[cpu_new(layout,False),cpu_new(layout,True)]
 for case_no,(height,mode,ccr,maskflag,opcode,alias) in enumerate(cases):
  data=encoded(mode,opcode)
  if alias:data+=bytes(0x90000-len(data))
  pixels=rng.randbytes(0x90000);frame=rng.randbytes(0x30000);history=rng.randbytes(256);mask=bytes(rng.randrange(2)*255 for _ in range(0x3000));initial=[rng.randrange(2**32) for _ in regs];initial[-1]=0x90f000
  outputs=[];traces=[];writes=[]
  for c,g,entry,base in pairs:
   c.mem_write(0x500000,data);c.mem_write(0x600000,pixels);c.mem_write(0x700000,frame);c.mem_write(0x800000,mask);c.mem_write(g+0x6812,history);c.mem_write(g+0x5c49,bytes(range(16)));c.mem_write(0x90ee00,bytes(0x200));c.mem_write(0x90f000,struct.pack('>I',0xa00000))
   for off,value,n in ((0x5c26,0x800000,4),(0x5c2a,0x500000,4),(0x5c1e,0x700000,4),(0x5c1a,0x500000+maskflag if alias else 0x600000,4),(0x5c36,(height*320-1)&65535,2),(0x5c38,height&255,1),(0x5d40,maskflag,2)):
    c.mem_write(g+off,value.to_bytes(n,'big'))
   before=bytes(c.mem_read(g,0x7300));c.reg_write(R.UC_M68K_REG_SR,ccr)
   for reg,value in zip(regs,initial):c.reg_write(reg,value)
   trace=[];wr=[]
   def instruction(uc,pc,size,unused):trace.append((pc,size))
   def write(uc,access,addr,size,value,unused):
    assert alias and 0x500000<=addr and addr+size<=0x590000 or 0x600000<=addr and addr+size<=0x690000 or 0x700000<=addr and addr+size<=0x730000 or g+0x6812<=addr and addr+size<=g+0x6912 or 0x90ee00<=addr and addr+size<=0x90f000,(hex(addr),size)
    wr.append((addr-g if g<=addr<g+0x7300 else addr,size,value))
   wh=c.hook_add(unicorn.UC_HOOK_MEM_WRITE,write);ch=c.hook_add(unicorn.UC_HOOK_CODE,instruction)
   c.emu_start(entry,0xa00000,count=200000);c.hook_del(wh);c.hook_del(ch)
   assert c.reg_read(R.UC_M68K_REG_PC)==0xa00000,(case_no,height)
   c.mem_write(0xa00000,bytes.fromhex('40f900a00100'));c.emu_start(0xa00000,0xa00006,count=1)
   after=bytes(c.mem_read(g,0x7300));assert before[:0x6812]==after[:0x6812] and before[0x6912:]==after[0x6912:]
   outputs.append((tuple(c.reg_read(v) for v in regs),bytes(c.mem_read(0xa00100,2)),bytes(c.mem_read(0x600000,len(pixels))),bytes(c.mem_read(0x700000,len(frame))),bytes(c.mem_read(g+0x6812,256)),bytes(c.mem_read(0x90ee00,0x204))))
   outputs[-1]+=(bytes(c.mem_read(0x500000,0x90000)) if alias else b'',)
   traces.append(trace);writes.append(wr)
  assert outputs[0]==outputs[1],(layout,case_no,height,mode,ccr,maskflag)
  assert writes[0]==writes[1],(layout,case_no,'write sequence')

  saved=difference(pairs[0][0],[pc for pc,_ in traces[0]],pairs[1][0],[pc for pc,_ in traces[1]])
  if layout==0:profiles.append(dict(height=height,mode=mode,ccr=ccr,maskflag=maskflag,opcode=opcode,source_alias=alias,reference_instructions=len(traces[0]),candidate_instructions=len(traces[1]),estimated_saved_core_cycles=saved))
  checks+=1
report=dict(kernel_sha256=hashlib.sha256(kernel).hexdigest(),cases=checks,all_registers_CCR_stack_history_framebuffer_globals_exact=True,memory_write_sequence_exact=True,all_heights_1_to_256=True,all32CCR=True,two_layouts=True,all_three_encoding_classes_and_mixed=True,mask_modes=[0,1],cross_column_run_resume=True,all_256_opcodes=True,destination_overlaps_compressed_source=True,malformed_streams='Original routine has no bounds checking; only valid complete encoded streams are certified.',timing='Changed MC68000 instruction core-cycle estimate, excluding DMA/bus waits; not actual runtime.',profiles=profiles)
(BUILD / 'stripe-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='profiles'},indent=2))
