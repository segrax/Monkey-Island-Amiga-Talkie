from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
HERE=Path(__file__).resolve().parent
BUILD=artifact_dir('io')
import json,random,struct,sys
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
P=BUILD;r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
code=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data' in h);kernel=json.loads((P/'kernel.json').read_text());rng=random.Random(0x16d80)
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6')]
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000);cpu.mem_write(0x100000,code);blob=bytearray((P/'fast.bin').read_bytes())
for off in kernel['original_code_relocations']:struct.pack_into('>I',blob,off,0x1163b8)
cpu.mem_write(0x180000,bytes(blob));cpu.mem_write(0x1163b8,bytes.fromhex('4e75'))
linked=False;image=engine_build()/'module/Monkey_Talkie_Test';manifest=image.with_name('module.json')
if manifest.exists() and 'engine_buffered_read' in json.loads(manifest.read_text()):
 linked=True;m=json.loads(manifest.read_text());q=HunkReader();assert q.read_file(str(image))==0 and q.build_segments()
 index=m['exports']['_fread_fast']['hunk'];section=0
 for h in q.hunks:
  section=h.get('hunk_no',section)
  if section==0 and 'data' in h:cpu.mem_write(0x200000,h['data'])
  if section==index and 'data' in h:cpu.mem_write(0x180000,h['data'])
  if h['type_name']=='HUNK_ABSRELOC32' and section in (0,index):
   for target,offsets in h['reloc'].items():
    base=0x200000 if section==0 else 0x180000
    add=0x200000 if target==0 else 0x180000 if target==index else 0
    for off in offsets:
     a=base+off;cpu.mem_write(a,struct.pack('>I',int.from_bytes(cpu.mem_read(a,4),'big')+add))
 cpu.mem_write(0x2163b8,bytes.fromhex('4e75'))

def put(a,v,n):cpu.mem_write(a,int(v).to_bytes(n,'big'))
def get(a,n):return int.from_bytes(cpu.mem_read(a,n),'big')
cases=[]
for count in (0,1,2,3,7,16,255,256,257,1024,16384,32767):
 for chunk in (1,17,1024):cases.append((1,count,chunk,count+3,0))
for size,count in ((0,7),(2,9),(16,19),(65535,9),(1,65535)):
 for chunk in (1,17):cases.append((size,count,chunk,33,0))
for _ in range(128):
 count=rng.randrange(1025);cases.append((1,count,rng.choice((1,2,3,17,256,1024)),rng.randrange(2*count+1),rng.randrange(2)))
cases += [(1,1,1,4,2),(1,1,1,4,3),(1,17,17,20,4),(1,17,17,20,5)]
for delta in (-4,-3,-2,2,3,4):
 for count in (15,16,17,31,32,33,256):
  cases.append((1,count,count,count+3,10+delta))
for mode in (30,31):
 for count in (15,16,17,31,32,33,256,16384):cases.append((1,count,1024,count+3,mode))
results=[]
for case,(size,count,chunk,total,odd) in enumerate(cases):
 payload=bytes(rng.randrange(256) for _ in range(total));initial=[rng.getrandbits(32) for _ in regs];out=[]
 for fast in (False,True):
  file,buffer,dest,stack=0x500000,0x600000+(odd&1),0x700000+(odd&1),0x90f000
  if odd==2:buffer=file+22
  if odd==3:dest=file+22
  if odd==4:dest=buffer+1
  if odd==5:dest=buffer-1
  if 6<=odd<30:dest=buffer+odd-10
  if odd==30:dest=0x700001
  if odd==31:dest=0x700000
  cpu.mem_write(file,b'F'*32);cpu.mem_write(buffer-1,b'B'*0x10010);cpu.mem_write(dest-1,b'Z'*0x10010);cpu.mem_write(stack-256,b'S'*288)
  first=min(total,chunk);cpu.mem_write(buffer,payload[:first]);put(file+4,buffer,4);put(file+8,first,2)
  cpu.mem_write(stack,struct.pack('>IIHHI',0xa00000,dest,size,count,file));pos=[first];refills=[];instructions=[0]
  cpu.reg_write(R.UC_M68K_REG_SR,0)
  for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
  cpu.reg_write(R.UC_M68K_REG_A7,stack)
  def trace(uc,pc,length,unused):
   instructions[0]+=1
   if pc not in (0x1163b8,0x2163b8):return
   assert get(cpu.reg_read(R.UC_M68K_REG_A7)+4,4)==file
   refills.append(bytes(cpu.mem_read(file,32)))
   n=min(chunk,total-pos[0]);put(file+8,max(0,n-1),2)
   if n:
    block=payload[pos[0]:pos[0]+n];cpu.mem_write(buffer,block);pos[0]+=n;put(file+4,buffer+1,4);putreg=block[0]
   else:putreg=0xffffffff;put(file+18,0x10,2)
   cpu.reg_write(R.UC_M68K_REG_D0,putreg);cpu.reg_write(R.UC_M68K_REG_D1,0xaabbccdd);cpu.reg_write(R.UC_M68K_REG_A0,0x11223344);cpu.reg_write(R.UC_M68K_REG_A1,0x55667788)
  def guard(uc,access,address,length,value,unused):
   allowed=(stack-512<=address and address+length<=stack) or (file<=address and address+length<=file+32) or (dest<=address and address+length<=dest+size*count)
   assert allowed,(case,fast,hex(address),length,'write outside stack/stream/destination')
  write_hook=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard)
  hook=cpu.hook_add(unicorn.UC_HOOK_CODE,trace)
  cpu.emu_start((0x216d80 if linked else 0x180000) if fast else 0x116d80,0xa00000,count=8000000);cpu.hook_del(hook);cpu.hook_del(write_hook)
  assert cpu.reg_read(R.UC_M68K_REG_PC)==0xa00000,(case,fast)
  assert [cpu.reg_read(reg) for reg in regs]==initial,(case,fast,'ABI')
  assert cpu.reg_read(R.UC_M68K_REG_A7)==stack+4
  assert bytes(cpu.mem_read(stack,16))==struct.pack('>IIHHI',0xa00000,dest,size,count,file)
  out.append((cpu.reg_read(R.UC_M68K_REG_D0),bytes(cpu.mem_read(dest-1,0x10010)),bytes(cpu.mem_read(file,32)),bytes(cpu.mem_read(buffer-1,0x10010)),refills,pos[0]))
  if case in (29,32,35):results.append(dict(case=case,fast=fast,count=count,chunk=chunk,instructions=instructions[0]))
 assert out[0]==out[1],(case,size,count,chunk,total,odd,[(i,a if i==0 else len(a),b if i==0 else len(b)) for i,(a,b) in enumerate(zip(*out)) if a!=b])
report=dict(pass_=True,cases=len(cases),return_output_stream_refill_trace_callee_stack_exact=True,write_bounds_guarded=True,linked_image_entry_and_relocations=linked,overlapping_destinations_and_embedded_buffers=True,metrics=results,scope='Compiled 68000 versus original fread; deterministic buffer-refill model; instruction counts are not cycles')
(P/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

