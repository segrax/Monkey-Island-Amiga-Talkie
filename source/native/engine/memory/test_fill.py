from pathlib import Path
import sys,json,random,struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
P=artifact_dir('memory');rng=random.Random(0x1476a)
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
code=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000)
cpu.mem_map(0x100000,0x100000);cpu.mem_map(0x400000,0x10000);cpu.mem_map(0x700000,0x20000);cpu.mem_map(0x900000,0x10000)
cpu.mem_write(0x100000,code);cpu.mem_write(0x400000,(P/'memory.bin').read_bytes())
linked=False;image=P.parent/'module/Monkey_Talkie_Test'
if image.exists():
 meta=json.loads(image.with_name('module.json').read_text())
 if 'engine_memory_fill' in meta:
  linked=True;q=HunkReader();assert q.read_file(str(image))==0 and q.build_segments()
  patched=bytearray(next(h['data'] for h in q.hunks if h.get('hunk_no')==0 and 'data'in h))
  assert patched[0x1476a:0x14772]==bytes.fromhex('4ef9000000004e71')
  struct.pack_into('>I',patched,0x1476c,0x400000)
  index=meta['exports']['_engine_fill']['hunk'];blob=next(h['data'] for h in q.hunks if h.get('hunk_no')==index and 'data'in h)
  assert blob[:len((P/'memory.bin').read_bytes())]==(P/'memory.bin').read_bytes()
  cpu.mem_map(0x200000,0x100000);cpu.mem_write(0x200000,bytes(patched));cpu.mem_write(0x400000,blob)
cpu.mem_write(0x40f000,bytes.fromhex('40f90040f100'))
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
cases=[(n,byte,alignment,n&31) for n in (0,1,2,3,4,7,15,16,17,31,32,33,127,255,256,257,4096,65535) for byte in (0,1,127,128,255) for alignment in (0,1)]
cases += [(31,b,b&1,b&31) for b in range(256)]
cases += [(rng.randrange(2048),rng.randrange(256),rng.randrange(8),ccr) for ccr in range(32) for _ in range(4)]
profiles=[]
for number,(n,byte,alignment,ccr) in enumerate(cases):
 initial=[rng.getrandbits(32) for _ in regs];initial[-1]=0x90f000
 dest=0x700010+alignment;backing=bytes([0x91])*0x10020;outputs=[];counts=[]
 for fast in (False,True):
  cpu.mem_write(0x700000,backing);cpu.mem_write(0x90ef00,bytes(0x200))
  cpu.mem_write(initial[-1],struct.pack('>IIHH',0x40e000,dest,0xa500|byte,n))
  cpu.reg_write(R.UC_M68K_REG_SR,ccr)
  for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
  count=[0]
  def trace(*unused):count[0]+=1
  hook=cpu.hook_add(unicorn.UC_HOOK_CODE,trace) if n==4096 else None
  if hook is not None:cpu.ctl_remove_cache(0x100000,0x40ffff)
  cpu.emu_start((0x21476a if linked else 0x400000) if fast else 0x11476a,0x40e000,count=2000000)
  if hook is not None:cpu.hook_del(hook)
  assert cpu.reg_read(R.UC_M68K_REG_PC)==0x40e000,(number,fast)
  state=[cpu.reg_read(reg) for reg in regs]
  cpu.emu_start(0x40f000,0x40f006,count=1);flags=bytes(cpu.mem_read(0x40f100,2))
  data=bytes(cpu.mem_read(0x700000,len(backing)));expected=bytearray(backing);expected[dest-0x700000:dest-0x700000+n]=bytes([byte])*n
  assert data==expected,(number,fast,'bounded fill mismatch')
  outputs.append((state,flags,data));counts.append(count[0])
 assert outputs[0]==outputs[1],(number,n,byte,alignment,ccr,[(i,a,b) for i,(a,b) in enumerate(zip(outputs[0][0],outputs[1][0])) if a!=b],outputs[0][1],outputs[1][1])
 if n==4096:profiles.append(dict(bytes=n,alignment=alignment,old_instructions=counts[0],new_instructions=counts[1]))
report=dict(pass_=True,linked_original_entry=linked,cases=len(cases),all_registers_and_CCR_exact=True,zero_and_65535_counts=True,all_fill_bytes=True,guarded_output=True,profiles=profiles)
(P/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
