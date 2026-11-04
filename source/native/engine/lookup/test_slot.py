from pathlib import Path
import sys,json,random,struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
P=artifact_dir('lookup');rng=random.Random(0x11dd2)
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
code=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000)
cpu.mem_map(0,0x1000000);cpu.mem_write(0x100000,code);cpu.mem_write(0x400000,(P/'lookup.bin').read_bytes());cpu.mem_write(0x40f000,bytes.fromhex('40f90040f100'))
linked=False;image=P.parent/'module/Monkey_Talkie_Test'
if image.exists():
 meta=json.loads(image.with_name('module.json').read_text())
 if 'engine_verb_lookup' in meta or 'engine_resource_lookup' in meta:
  linked=True;q=HunkReader();assert q.read_file(str(image))==0 and q.build_segments()
  patched=bytearray(next(h['data'] for h in q.hunks if h.get('hunk_no')==0 and 'data'in h))
  assert patched[0x11dd2:0x11dda]==bytes.fromhex('4ef9000000004e71')
  struct.pack_into('>I',patched,0x11dd4,0x400000)
  index=meta['exports']['_engine_find_slot']['hunk'];blob=next(h['data'] for h in q.hunks if h.get('hunk_no')==index and 'data'in h)
  assert blob[:len((P/'lookup.bin').read_bytes())]==(P/'lookup.bin').read_bytes()
  cpu.mem_write(0x200000,bytes(patched));cpu.mem_write(0x400000,blob)
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
cases=[]
for match in range(100):
 for ccr in range(32):
  a=bytearray([0x44]*100);b=bytearray([0x66]*100)
  for i in range(7,100,7):a[i]=0x7f
  if match:a[match]=0x7f;b[match]=0x80
  cases.append((bytes(a),bytes(b),0x7f,0x80,ccr,match))
for first,second in ((0,0),(255,255),(256,1),(1,256),(65535,65535)):
 for ccr in range(32):cases.append((bytes([first&255])*100,bytes([second&255])*100,first,second,ccr,1 if first<256 and second<256 else 0))
for _ in range(128):
 a=rng.randbytes(100);b=rng.randbytes(100);x=rng.randrange(256);y=rng.randrange(256)
 match=next((i for i in range(1,100) if a[i]==x and b[i]==y),0);cases.append((a,b,x,y,rng.randrange(32),match))
profiles=[]
for number,(a,b,x,y,ccr,match) in enumerate(cases):
 g=0x700000;stack=0x90f000;initial=[rng.getrandbits(32) for _ in regs];initial[12]=g;initial[-1]=stack
 outputs=[];counts=[]
 for fast in (False,True):
  cpu.mem_write(g+0x5538,a);cpu.mem_write(g+0x57f4,b);cpu.mem_write(stack-256,bytes(512));cpu.mem_write(stack,struct.pack('>IHH',0x40e000,x,y))
  cpu.reg_write(R.UC_M68K_REG_SR,ccr)
  for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
  reads=[];count=[0]
  def read(uc,access,address,size,value,unused):
   if g+0x5538<=address<g+0x559c or g+0x57f4<=address<g+0x5858:reads.append((address-g,size))
  def write(uc,access,address,size,value,unused):assert stack-256<=address and address+size<=stack,('non-stack write',address,size)
  def trace(*unused):count[0]+=1
  hooks=[cpu.hook_add(unicorn.UC_HOOK_MEM_READ,read),cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)]
  measure=number in (0,32,96,3136)
  if measure:hooks.append(cpu.hook_add(unicorn.UC_HOOK_CODE,trace))
  cpu.ctl_remove_cache(0x100000,0x40ffff)
  cpu.emu_start((0x211dd2 if linked else 0x400000) if fast else 0x111dd2,0x40e000,count=10000)
  for h in hooks:cpu.hook_del(h)
  assert cpu.reg_read(R.UC_M68K_REG_PC)==0x40e000,(number,fast)
  state=[cpu.reg_read(reg) for reg in regs];assert state[0]==match,(number,fast,state[0],match)
  cpu.emu_start(0x40f000,0x40f006,count=1);flags=bytes(cpu.mem_read(0x40f100,2))
  assert bytes(cpu.mem_read(g+0x5538,100))==a and bytes(cpu.mem_read(g+0x57f4,100))==b
  outputs.append((state,flags,reads));counts.append(count[0])
 assert outputs[0]==outputs[1],(number,match,[(i,a,b) for i,(a,b) in enumerate(zip(outputs[0][0],outputs[1][0])) if a!=b],outputs[0][1],outputs[1][1])
 if measure:profiles.append(dict(first_match=match,old_instructions=counts[0],new_instructions=counts[1]))
report=dict(pass_=True,cases=len(cases),linked_original_entry=linked,all_registers_CCR_and_ordered_reads_exact=True,all_match_positions_and_initial_CCRs=True,wide_word_arguments=True,profiles=profiles)
(P/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
