"""Compare the real mask gateway and retained decoder in the complete linked image."""
from pathlib import Path
import sys,json,hashlib,struct,random,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
parser=argparse.ArgumentParser();parser.add_argument('--candidate',type=Path,default=engine_build()/'module/Monkey_Talkie_Test');args=parser.parse_args()
meta=json.loads(args.candidate.with_name('module.json').read_text());assert hashlib.sha256(args.candidate.read_bytes()).hexdigest()==meta['sha256']
r=HunkReader();assert r.read_file(str(args.candidate))==0 and r.build_segments();images={h['hunk_no']:bytearray(h['data'])for h in r.hunks if'data'in h};bases={};cursor=0x100000
for index,h in enumerate(r.hunks[0]['hunks']):bases[index]=cursor;cursor+=(h['size']+65535)&~65535
assert cursor<0x700000
rel={};section=0
for h in r.hunks:
 section=h.get('hunk_no',section)
 if h['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in h['reloc'].items():
   rel[(section,target)]=set(offsets)
   for off in offsets:struct.pack_into('>I',images[section],off,struct.unpack_from('>I',images[section],off)[0]+bases[target])
e=meta['exports']['_engine_mask_rle'];C,G=bases[0],bases[2];K=bases[e['hunk']]+e['offset'];generation=json.loads((artifact_dir('mask')/'generation.json').read_text())
assert bytes(images[0][0x4de2:0x4de4])==bytes.fromhex('4ef9') and struct.unpack_from('>I',images[0],0x4de4)[0]==K
assert 0x4de4 in rel[(0,e['hunk'])] and 0x4de4 not in rel.get((0,0),set())
assert rel[(e['hunk'],2)]==set(generation['global_relocations'])
for off,expected in zip(generation['global_relocations'],(0x5c22,0x5c38,0x5c2e)):assert struct.unpack_from('>I',images[e['hunk']],off)[0]==G+expected
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000)
for index,data in images.items():cpu.mem_write(bases[index],bytes(data))
cpu.mem_write(0x7f0000,bytes.fromhex('40f9007f0100'))
regs=[getattr(R,'UC_M68K_REG_'+x)for x in('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')];rng=random.Random(0x4de2);access=[];io=False;fifo=0;data=b'';src=dst=0

def memory(uc,kind,at,n,v,unused):
 global fifo
 if io and kind==unicorn.UC_MEM_READ and src<=at<src+len(data):
  assert n==1 and fifo<len(data);uc.mem_write(at,data[fifo:fifo+1]);fifo+=1
 if src<=at<src+0x14000 or dst<=at<dst+0x4000:access.append((kind,at,n,v if kind==unicorn.UC_MEM_WRITE else bytes(uc.mem_read(at,n)).hex()))
cpu.hook_add(unicorn.UC_HOOK_MEM_READ|unicorn.UC_HOOK_MEM_WRITE,memory)

def stream(mode,n):
 out=bytearray()
 for _ in range(300):
  count=n if n>=0 else rng.choice((0,1,2,3,7,8,16,63,127));repeat=mode==1 or mode==2 and rng.randrange(2);out.append(count|(128 if repeat else 0));out.extend(rng.randbytes(1 if repeat else count or 256))
 return bytes(out)

cases=[(h,m,n,a,(h+m+n)&31,False)for h in(1,2,7,8,127,255,256)for m in range(3)for n in(0,1,2,3,7,8,127,-1)for a in(False,True)]
cases +=[(h,m,n,a,ccr,False)for h in(1,8)for m in(0,1)for n in(1,2,7,8)for a in(False,True)for ccr in range(32)]
cases +=[(h,m,n,False,ccr,True)for h in(1,8,256)for m in range(3)for n in(0,1,7,8,127)for ccr in(0,31)]
for number,(height,mode,count,alias,ccr,io)in enumerate(cases):
 src=0xdff100 if io else 0x30000;dst=(0xdff200 if io else 0x50000)if not alias else src+40;data=stream(mode,count);initial=[0xffffffff if ccr&1 else rng.randrange(1<<32)for _ in regs];initial[-1]=0x7ef000;snapshots=[]
 for fast in(False,True):
  cpu.mem_write(src,bytes(0x14000));cpu.mem_write(dst,bytes(0x4000));cpu.mem_write(src,data);cpu.mem_write(G+0x5c22,struct.pack('>I',dst));cpu.mem_write(G+0x5c2e,struct.pack('>I',src));cpu.mem_write(G+0x5c38,bytes((height&255,)));cpu.mem_write(initial[-1]-64,bytes(128));cpu.mem_write(C+0x4de4,struct.pack('>I',K if fast else C+0x15338));cpu.ctl_remove_cache(C+0x4de2,C+0x4de8)
  cpu.reg_write(R.UC_M68K_REG_SR,0x2000|ccr)
  for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
  access.clear();fifo=0;cpu.emu_start(C+0x4b80,C+0x4b84,count=100000);assert cpu.reg_read(R.UC_M68K_REG_PC)==C+0x4b84;cpu.emu_start(0x7f0000,0x7f0006,count=1)
  snapshots.append((tuple(cpu.reg_read(reg)for reg in regs),bytes(cpu.mem_read(0x7f0100,2)),bytes(cpu.mem_read(src,0x14000)),bytes(cpu.mem_read(dst,0x4000)),bytes(cpu.mem_read(initial[-1]-64,128)),bytes(cpu.mem_read(G,29312)),tuple(access),fifo))
 assert snapshots[0]==snapshots[1],(number,height,mode,count,alias,ccr,io)
report=dict(pass_=True,cases=len(cases),module_sha256=meta['sha256'],actual_caller_entry=hex(C+0x4b80),all_hunks_and_relocations_loaded=True,real_gateway_and_global_relocations_verified=True,original_decoder_retained=True,all_registers_CCR_stack_globals_RAM_exact=True,ordered_BYTE_reads_writes_exact=True,volatile_FIFO_IO_cases=sum(v[-1]for v in cases),source_destination_alias=True,all32CCR_short_packets=True,allFFFF_registers=True)
(artifact_dir('mask')/'linked-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
