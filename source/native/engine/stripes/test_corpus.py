"""Run independently decoded owned room28 stripe data through both 68000 kernels."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import argparse,hashlib,json,random,struct,sys
from timing import difference
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--reference-dir', type=Path)
args = parser.parse_args()
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
gen=json.loads((BUILD / 'generation.json').read_text());kernel=(BUILD / 'stripe.bin').read_bytes()
fd=ROOT/'tests/fixtures/bar-stripes';fixtures=json.loads((fd/'fixtures.json').read_text())['fixtures']
r=HunkReader();assert r.read_file(str(ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
old=next(h['data']for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)
regs=[getattr(R,'UC_M68K_REG_'+s)for s in('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
cpu=[];rng=random.Random(0x151f6)
entries=[]
for new in(False,True):
 c=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);c.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);c.mem_map(0,0x1000000);c.mem_write(0x100000,old);c.mem_write(0x400000,kernel)
 section=0
 for h in r.hunks:
  section=h.get('hunk_no',section)
  if section==0 and h['type_name']=='HUNK_ABSRELOC32':
   for off in h['reloc'].get(2,[]):c.mem_write(0x100000+off,struct.pack('>I',int.from_bytes(c.mem_read(0x100000+off,4),'big')+0x200000))
 for off in gen['absolute_h2_relocations']:c.mem_write(0x400000+off,struct.pack('>I',int.from_bytes(c.mem_read(0x400000+off,4),'big')+0x200000))
 if not new and args.reference_dir:
  reference=json.loads((args.reference_dir/'generation.json').read_text())
  c.mem_write(0x400000,(args.reference_dir/'stripe.bin').read_bytes())
  for off in reference['absolute_h2_relocations']:c.mem_write(0x400000+off,struct.pack('>I',int.from_bytes(c.mem_read(0x400000+off,4),'big')+0x200000))
 entries.append(0x400000 if new or args.reference_dir else 0x115190)
 cpu.append(c)
checks=0;profiles=[]
for item in fixtures:
 data=(fd/item['token_file']).read_bytes();expected=(fd/item['pixels_file']).read_bytes();assert hashlib.sha256(data).hexdigest()==item['token_sha256'] and hashlib.sha256(expected).hexdigest()==item['pixels_sha256'];h=item['height']
 for maskflag in(0,1):
  initial=[rng.randrange(2**32)for _ in regs];initial[-1]=0x90f000;out=[];traces=[];writes=[]
  for new,c in enumerate(cpu):
   g=0x200000;c.mem_write(0x500000,data+bytes(16));c.mem_write(0x600000,b'Z'*0x20000);c.mem_write(0x700000,b'Q'*0x20000);c.mem_write(0x800000,bytes(0x3000));c.mem_write(g+0x6812,b'W'*256);c.mem_write(g+0x5c49,bytes(range(16,32)));c.mem_write(0x90ee00,bytes(0x200));c.mem_write(0x90f000,struct.pack('>I',0xa00000))
   for off,v,n in((0x5c26,0x800000,4),(0x5c2a,0x500000,4),(0x5c1e,0x700000,4),(0x5c1a,0x600000,4),(0x5c36,h*320-1,2),(0x5c38,h,1),(0x5d40,maskflag,2)):c.mem_write(g+off,v.to_bytes(n,'big'))
   c.reg_write(R.UC_M68K_REG_SR,checks&31)
   for reg,v in zip(regs,initial):c.reg_write(reg,v)
   trace=[];wr=[]
   def execute(uc,pc,size,unused):trace.append(pc)
   def write(uc,access,a,n,v,unused):wr.append((a,n,v))
   ch=c.hook_add(unicorn.UC_HOOK_CODE,execute);wh=c.hook_add(unicorn.UC_HOOK_MEM_WRITE,write);c.emu_start(entries[new],0xa00000,count=100000);c.hook_del(ch);c.hook_del(wh);assert c.reg_read(R.UC_M68K_REG_PC)==0xa00000
   c.mem_write(0xa00000,bytes.fromhex('40f900a00100'));c.emu_start(0xa00000,0xa00006,count=1)
   pixels=b''.join(bytes(c.mem_read(0x600000+y*320,8))for y in range(h));assert pixels==expected,(item['object_id'],item['stripe'],'pixels')
   out.append((tuple(c.reg_read(v)for v in regs),bytes(c.mem_read(0xa00100,2)),bytes(c.mem_read(0x600000,0x20000)),bytes(c.mem_read(0x700000,0x20000)),bytes(c.mem_read(g+0x6812,256)),bytes(c.mem_read(0x90ee00,0x204))))
   traces.append(trace);writes.append(wr)
  assert out[0]==out[1] and writes[0]==writes[1]
  savings=sum(4 for pc,nextpc in zip(traces[0],traces[0][1:])for b in gen['branches']if pc-0x100000==b['old'] and nextpc==pc+b['old_size'])
  saved=difference(cpu[0],traces[0],cpu[1],traces[1])
  profiles.append(dict(object=item['object_id'],stripe=item['stripe'],height=h,maskflag=maskflag,reference_instructions=len(traces[0]),candidate_instructions=len(traces[1]),estimated_saved_core_cycles=saved));checks+=1
report=dict(kernel_sha256=gen['kernel_sha256'],reference=str(args.reference_dir) if args.reference_dir else 'original executable',fixtures=45,cases=checks,owned_original_tokens_match_independent_PNG_pixels=True,all_GPR_CCR_stack_framebuffer_history_and_write_sequence_exact=True,actual_runtime=False,no_original_call_entry_claim=True,profiles=profiles,total_estimated_saved_core_cycles=sum(x['estimated_saved_core_cycles']for x in profiles),minimum_estimated_saved_core_cycles=min(x['estimated_saved_core_cycles']for x in profiles),timing='Changed MC68000 instruction counts times documented chapter-8 costs; excludes DMA/bus waits, not wall time')
(BUILD / 'corpus-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='profiles'},indent=2))
