"""Compare the original and BYTE-unrolled mask-plane decoder, including aliased streams."""
from pathlib import Path
import sys,subprocess,struct,random,json,hashlib
sys.path.insert(0,'D:/Projects/Monkey.Island.Amiga/tools/python')
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
import capstone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
P=artifact_dir('mask')
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
original=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)[0x15338:0x1538e]
candidate=(P/'mask.bin').read_bytes()
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000)
relocs=[]
for i in cs.disasm(candidate,0):
 if '.l' in i.op_str and any(x in i.op_str for x in ('$5c22','$5c38','$5c2e')):relocs.append(i.address+2)
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
rng=random.Random(0x15338);cpus=[]
for code in (original,candidate):
 u=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);u.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);u.mem_map(0,0x100000);u.mem_write(0x10000,code);cpus.append(u)
def stream(mode,n):
 b=bytearray()
 for _ in range(300):
  length=n if n>=0 else rng.choice((0,1,2,3,7,16,63,127))
  repeat=mode==1 or mode==2 and rng.randrange(2)
  b.append(length|(128 if repeat else 0))
  b.extend(rng.randbytes(1 if repeat else length or 256))
 return bytes(b)
profiles=[];count=0
for forced in range(32):
 for height in(1,2,7,8,255,256):
  for mode in range(3):
   for n in(0,1,2,3,4,7,8,127,-1):
    # All CCR combinations distributed through every height/mode/packet class.
    ccr=forced
    for alias in (False,True):
     data=stream(mode,n);src=0x30000;dst=src+40 if alias else 0x50000
     init=[0xffffffff if forced&1 else rng.randrange(2**32) for _ in regs];init[-1]=0x8f000
     results=[]
     for u in cpus:
      u.mem_write(src,bytes(0x14000));u.mem_write(0x50000,bytes(0x4000));u.mem_write(src,data)
      u.mem_write(0x5c22,struct.pack('>I',dst));u.mem_write(0x5c2e,struct.pack('>I',src));u.mem_write(0x5c38,bytes((height&255,)))
      u.mem_write(0x8ef00,bytes(0x104));u.mem_write(0x8f000,struct.pack('>I',0x90000));u.reg_write(R.UC_M68K_REG_SR,ccr)
      for reg,v in zip(regs,init):u.reg_write(reg,v)
      accesses=[];steps=[0]
      def mem(cpu,access,addr,size,value,_):
       if src<=addr<src+0x14000 or 0x50000<=addr<0x54000:
        accesses.append((access,addr,size,value if access==unicorn.UC_MEM_WRITE else bytes(cpu.mem_read(addr,size)).hex()))
      def ins(*args):steps[0]+=1
      hooks=[u.hook_add(unicorn.UC_HOOK_MEM_READ|unicorn.UC_HOOK_MEM_WRITE,mem),u.hook_add(unicorn.UC_HOOK_CODE,ins)]
      u.emu_start(0x10000,0x90000,count=200000)
      for h in hooks:u.hook_del(h)
      assert u.reg_read(R.UC_M68K_REG_PC)==0x90000
      # Materialize lazy arithmetic flags using MOVE SR to absolute memory.
      u.mem_write(0x90000,bytes.fromhex('40f900090100'));u.emu_start(0x90000,0x90006,count=1)
      results.append((tuple(u.reg_read(reg) for reg in regs),bytes(u.mem_read(0x90100,2)),bytes(u.mem_read(src,0x14000)),bytes(u.mem_read(0x50000,0x4000)),bytes(u.mem_read(0x8ef00,0x104)),accesses,steps[0]))
     assert results[0][:-1]==results[1][:-1],(height,mode,n,alias,[(x[0][:2],x[1],len(x[-2])) for x in results])
     if not alias:profiles.append(dict(height=height,mode=mode,packet_length=n,original_instructions=results[0][-1],candidate_instructions=results[1][-1]))
     count+=1
report=dict(cases=count,kernel_bytes=len(candidate),sha256=hashlib.sha256(candidate).hexdigest(),absolute_h2_relocations=relocs,all_registers_CCR_stack_memory_exact=True,ordered_source_reads_and_destination_writes_exact=True,all_heights=True,source_destination_alias=True,profiles=profiles)
(P/'flags-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='profiles'},indent=2))
