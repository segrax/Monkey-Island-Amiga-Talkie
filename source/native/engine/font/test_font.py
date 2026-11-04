"""Generate a guarded two-bit packed-font decoder from the owned original."""
from pathlib import Path
import sys,struct,json,hashlib,random
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
ROOT=PROJECT_ROOT;OUT=artifact_dir('font')
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
from capstone import Cs,CS_ARCH_M68K,CS_MODE_BIG_ENDIAN,CS_MODE_M68K_000
assert hashlib.sha256((ROOT/'data/original/Monkey_Island').read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
import unicorn
from unicorn import m68k_const as R
rd=HunkReader();assert rd.read_file(str(ROOT/'data/original/Monkey_Island'))==0 and rd.build_segments()
h=bytearray(next(x['data']for x in rd.hunks if x.get('hunk_no')==0 and'data'in x));cur=None
BASE=0x100000;G=0x200000
for x in rd.hunks:
 if 'hunk_no'in x:cur=x['hunk_no']
 if cur==0 and x['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in x['reloc'].items():
   for off in offsets:struct.pack_into('>I',h,off,(int.from_bytes(h[off:off+4],'big')+[BASE,0x20000,G][target])&0xffffffff)
generation=json.loads((OUT/'generation.json').read_text())
linked=engine_build()/'module/Monkey_Talkie_Test';linked_meta=json.loads((linked.parent/'module.json').read_text())
assert hashlib.sha256(linked.read_bytes()).hexdigest()==linked_meta['sha256']
lr=HunkReader();assert lr.read_file(str(linked))==0 and lr.build_segments()
font_hunk=linked_meta['exports']['_engine_font2']['hunk'];assert linked_meta['exports']['_engine_font2']['offset']==0
new=bytearray(next(x['data']for x in lr.hunks if x.get('hunk_no')==font_hunk and'data'in x))
patched_entry=next(x['data']for x in lr.hunks if x.get('hunk_no')==0 and'data'in x)[0x16020:0x1602a]
assert patched_entry==bytes.fromhex('4ef9000000004e714e71')
relocations={};section=0
for block in lr.hunks:
 section=block.get('hunk_no',section)
 if block['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in block['reloc'].items():relocations.setdefault((section,target),set()).update(offsets)
assert relocations[(font_hunk,2)]==set(generation['global_relocations'])
assert 0x16022 in relocations[(0,font_hunk)] and 0x16026 not in relocations[(0,2)]

assert hashlib.sha256(new).hexdigest()==generation['sha256']
for off in generation['global_relocations']:struct.pack_into('>I',new,off,int.from_bytes(new[off:off+4],'big')+G)
new=bytes(new);rng=random.Random(76195)
regs=[getattr(R,'UC_M68K_REG_'+n)for n in ['D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7']]
initial={r:rng.getrandbits(32)for r in regs};initial[regs[-1]]=0x70ff00
cases=[]
def fixture(width,height,mode,bpp=2,alias='none',seed=0,counter=8,shift_override=None,mask_override=None):
 random_=random.Random(seed);mem=bytearray(random_.randbytes(0x40000));glob=bytearray(random_.randbytes(0x8000));dest=0x600000;dirty=0x610000;source=0x620000
 if alias=='source_dest':source=dest+2
 if alias=='source_dirty':source=dirty
 if alias=='palette_dest':dest=G+0x5920
 if alias=='width_dest':dest=G+0x6f58
 def put(off,value,n=4):glob[off:off+n]=value.to_bytes(n,'big')
 shift=8-bpp if shift_override is None else shift_override;mask=(255<<shift)&255 if mask_override is None else mask_override
 for off,value in [(0x5c1e,dest),(0x5c22,dirty),(0x5c26,dirty),(0x6f48,source)]:put(off,value)
 for off,value in [(0x6f3a,counter),(0x5d40,mode),(0x6f54,0),(0x6f50,max(0,height-(seed%3))),(0x6f58,width),(0x6f40,random_.randrange(256))]:put(off,value,2)
 for off,value in [(0x6f5a,height),(0x6f5c,0x80>>(seed%8)),(0x6f5f,bpp),(0x6f60,shift),(0x6f61,mask),(0x66e9,seed%2 if mode else 0)]:put(off,value,1)
 if alias=='width_dest':
  glob[0x5920:0x5a20]=bytes(range(256));mem[0x20000:0x21000]=bytes(4096);put(0x6f40,0x60,2);put(0x6f50,3,2);put(0x6f5a,3,1)
 results=[]
 for entry in [BASE+0x16020,0x400000]:
  cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000)
  for at,size in [(BASE,0x20000),(G,0x10000),(0x400000,0x1000),(0x600000,0x40000),(0x700000,0x10000)]:cpu.mem_map(at,size)
  cpu.mem_write(BASE,bytes(h));cpu.mem_write(0x400000,new);
  if entry==0x400000:cpu.mem_write(BASE+0x16020,patched_entry[:2]+(0x400000).to_bytes(4,'big')+patched_entry[6:])
  cpu.mem_write(G,bytes(glob));cpu.mem_write(0x600000,bytes(mem))
  cpu.reg_write(R.UC_M68K_REG_SR,0x2000|(seed&31))
  for r,v in initial.items():cpu.reg_write(r,v)
  cpu.reg_write(R.UC_M68K_REG_SR,0x2000|(seed&31));cpu.mem_write(0x70ff00,(0x700000).to_bytes(4,'big'))
  writes=[];pal=[];reads=[];count=[0];fallback=[0]
  def write(uc,access,at,size,value,ud):
   if not 0x700000<=at<0x710000:writes.append((at,size,value))
  def read(uc,access,at,size,value,ud):
   if G+0x5920<=at<G+0x5a20:pal.append((at,size,bytes(uc.mem_read(at,size)).hex()))
   if source<=at<source+4096:reads.append((at,size))
  def trace(uc,at,size,ud):
   count[0]+=1
   if entry==0x400000 and at==entry+generation['entries']['_engine_font_original']:fallback[0]+=1
  cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write);cpu.hook_add(unicorn.UC_HOOK_MEM_READ,read);cpu.hook_add(unicorn.UC_HOOK_CODE,trace)
  cpu.emu_start(BASE+0x16020,0x700000,count=200000)
  assert cpu.reg_read(R.UC_M68K_REG_PC)==0x700000
  if entry==0x400000:assert fallback[0]==int(not(bpp==2 and shift==6 and mask==192 and counter==8)),(bpp,shift,mask,counter,fallback)
  results.append((tuple(cpu.reg_read(r)for r in regs),cpu.reg_read(R.UC_M68K_REG_SR)&31,bytes(cpu.mem_read(G,0x8000)),bytes(cpu.mem_read(0x600000,0x40000)),writes,pal,reads,count[0]))
 assert results[0][:-1]==results[1][:-1],(width,height,mode,bpp,alias,seed,[(k,results[0][k] if k<2 else 'data')for k in range(7)if results[0][k]!=results[1][k]])
 cases.append(dict(width=width,height=height,mode=mode,bpp=bpp,alias=alias,original_instructions=results[0][-1],candidate_instructions=results[1][-1]))
for width in [0,1,2,3,4,7,8,15,16,31]:
 for height in [0,1,3,9]:
  for mode in [0,1]:fixture(width,height,mode,seed=len(cases))
for alias in ['source_dest','source_dirty','palette_dest']:
 for mode in [0,1]:fixture(31,5,mode,alias=alias,seed=len(cases))
for bpp in [1,4,8]:
 for mode in [0,1]:fixture(16,5,mode,bpp=bpp,seed=len(cases))
for counter in [0,1,2,3,4,6,7,9,255]:
 for mode in [0,1]:fixture(16,5,mode,counter=counter,seed=len(cases))
for shift,mask in [(5,192),(6,128),(5,224),(7,192)]:
 fixture(16,5,0,shift_override=shift,mask_override=mask,seed=len(cases))
for seed in range(256):
 for mode in (0,1):fixture(8,12,mode,seed=seed)
for alias in ('source_dest','source_dirty','palette_dest'):
 for mode in (0,1):
  for ccr in range(32):fixture(31,5,mode,alias=alias,seed=ccr)
for alias in ('source_dest','source_dirty','palette_dest','width_dest'):
 for mode in (0,1):
  for ccr in range(32):fixture(8,3 if alias=='width_dest'else 5,mode,alias=alias,seed=ccr)
for height in (127,128,255):
 for mode in (0,1):fixture(8,height,mode,seed=len(cases))
report=dict(pass_=True,cases=len(cases),payload_bytes=len(new),all_regs_ccr=True,ordered_writes=True,ordered_palette_reads=True,ordered_source_reads=True,full_memory_exact=True,linked_entry_and_relocations=True,fixtures=cases)
(OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print('PASS',len(cases),'exact cases',len(new),'bytes')


