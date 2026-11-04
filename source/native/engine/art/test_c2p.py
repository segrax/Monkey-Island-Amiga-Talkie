"""Differentially execute linked partial-span C2P against retained original code."""
from pathlib import Path
import json,hashlib,random,struct,time
HERE=Path(__file__).resolve().parent
fixture=HERE/'test_game.py'
ns={'__file__':str(fixture),'__name__':'art_c2p_fixture'}
exec(compile(fixture.read_text().split('RESULTS=[]',1)[0],str(fixture),'exec'),ns)
globals().update({k:v for k,v in ns.items()if not k.startswith('__')})
KERNEL=addr('_nv_art_c2p_kernel');DICTIONARY=0x7c0000;INDICES_AT=0x7e0000
f=Fixture();c=f.cpu;f.call(C+0x15418,(LUT,))
rng=random.Random(15390);results=[];active=None;writes=[];index_reads=[]
def memwrite(cpu,access,p,n,v,u):
 if BITMAP<=p<BITMAP+40016:writes.append((p,n,int(v)&((1<<(8*n))-1)))
def memread(cpu,access,p,n,v,u):
 if INDICES_AT-8<=p<INDICES_AT+420:index_reads.append((p,n))
c.hook_add(unicorn.UC_HOOK_MEM_WRITE,memwrite);c.hook_add(unicorn.UC_HOOK_MEM_READ,memread)
def planes(raw):return bytes(sum(((x>>bit)&1)<<(7-i)for i,x in enumerate(raw))for bit in(0,1,3,4,2))
def one(height,prefix,overlap,pattern,odd,ccr,seed):
 rng=random.Random(seed);src=PRIMARY+6;dst=BITMAP+odd
 live=bytearray(rng.randrange(256)for _ in range(height*320));records=bytearray();indices=bytearray()
 for row in range(height):
  raw=bytes(rng.randrange(32)for _ in range(8));live[row*320:row*320+8]=raw
  if prefix<=row<prefix+overlap:
   indices+=struct.pack('>H',len(records));records+=raw+planes(raw)+b'\0'
   if pattern=='first'and row==prefix or pattern=='last'and row==prefix+overlap-1 or pattern=='mixed'and row%3==0 or pattern=='all':live[row*320+(0 if row%2 else 7)]^=1
 background=bytes(rng.randrange(256)for _ in range(40016));initial=[rng.randrange(1<<32)for _ in REGS];initial[-1]=STACK
 snapshots=[]
 for fast in(False,True):
  c.mem_write(src,bytes(live));c.mem_write(BITMAP,background);c.mem_write(DICTIONARY,bytes(records)if records else b'\0');c.mem_write(INDICES_AT,b'Z'*420)
  if indices:c.mem_write(INDICES_AT,bytes(indices))
  c.reg_write(R.UC_M68K_REG_SR,ccr)
  for reg,value in zip(REGS,initial):c.reg_write(reg,value)
  if fast:args=struct.pack('>IIIHHIIHH',dst,src,src,height,0,DICTIONARY if overlap else 0xdeaddead,INDICES_AT if overlap else 0xdeaddead,prefix,overlap)
  else:args=struct.pack('>IIIH',dst,src,src,height)
  c.mem_write(STACK,struct.pack('>I',STOP)+args);writes.clear();index_reads.clear();c.emu_start(KERNEL if fast else C+0x15390,STOP,count=1000000)
  assert c.reg_read(R.UC_M68K_REG_PC)==STOP
  snapshots.append((f.regs(),bytes(c.mem_read(BITMAP,40016)),tuple(writes)))
  assert bytes(c.mem_read(src,len(live)))==bytes(live)
  if fast:assert index_reads==[(INDICES_AT+2*n,2)for n in range(overlap)],(prefix,overlap,index_reads)
 assert snapshots[0]==snapshots[1],(height,prefix,overlap,pattern,odd,ccr,[(i,snapshots[0][i],snapshots[1][i])for i in range(3)if snapshots[0][i]!=snapshots[1][i]][:1])
 assert len(writes)==height*5 and all(n==1 for p,n,v in writes)
 results.append(dict(height=height,prefix=prefix,overlap=overlap,pattern=pattern,odd=odd,ccr=ccr))
cases=[(1,0,1),(2,0,1),(2,1,1),(3,1,1),(200,0,200),(200,1,198),(200,199,1),(200,0,1),(200,0,0),(200,199,0),(144,24,120),(144,12,120),(144,0,120)]
start=time.monotonic()
for h,p,n in cases:
 for pattern in('none','first','last','mixed','all'):
  for odd in(0,1):
   for ccr in range(32):one(h,p,n,pattern,odd,ccr,len(results))
 print('complete',h,p,n,len(results),round(time.monotonic()-start,2),flush=True)

# Exercise the real patched caller plus manager span computation, rather than
# constructing only the kernel ABI. Each fixture owns an eight-row synthetic strip.
for total,prefix in((8,0),(9,0),(9,1),(144,24),(200,199)):
 for odd in(0,1):
  for ccr in(0,31):
   host=Fixture();host.setup();cpu=host.cpu;src=PRIMARY+6;dst=BITMAP+odd
   assert host.call('_nv_art_bind',(0,src+prefix*320,OWNER+6+CODECOFF,OWNER+6,SOURCEBYTES,0))
   generator=random.Random(total*100+prefix);live=bytearray(generator.randrange(32)for _ in range(total*320))
   overlap=min(HEIGHT,total-prefix)
   for row in range(overlap):
    index=int.from_bytes(PAYLOAD[INDICES+row*2:INDICES+row*2+2],'big')
    live[(prefix+row)*320:(prefix+row)*320+8]=PAYLOAD[DICT+index:DICT+index+8]
   background=bytes(generator.randrange(256)for _ in range(40016))
   values=[generator.randrange(1<<32)for _ in REGS];values[12]=G;values[-1]=STACK
   snapshots=[];out=[];reads=[]
   def output_store(uc,access,p,n,v,unused):
    if BITMAP<=p<BITMAP+40016:out.append((p,n,int(v)&((1<<(8*n))-1)))
   def index_read(uc,access,p,n,v,unused):
    if ARENA+INDICES<=p<ARENA+INDICES+HEIGHT*2:reads.append((p,n))
   wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,output_store)
   rh=cpu.hook_add(unicorn.UC_HOOK_MEM_READ,index_read)
   for fast in(False,True):
    cpu.mem_write(C+0x14e72,bytes(IMAGES[0][0x14e72:0x14e7a])if fast else bytes.fromhex('4eba051c4fef000e'))
    cpu.ctl_remove_cache(C+0x14e72,C+0x14e7a)
    cpu.mem_write(src,bytes(live));cpu.mem_write(BITMAP,background)
    cpu.reg_write(R.UC_M68K_REG_SR,ccr)
    for reg,value in zip(REGS,values):cpu.reg_write(reg,value)
    cpu.mem_write(STACK,struct.pack('>IIIH',dst,src,src,total));out.clear();reads.clear()
    cpu.emu_start(C+0x14e72,C+0x14e7a,count=1000000)
    assert cpu.reg_read(R.UC_M68K_REG_PC)==C+0x14e7a
    snapshots.append((host.regs(),bytes(cpu.mem_read(BITMAP,40016)),tuple(out),bytes(cpu.mem_read(G,29312))))
    assert bytes(cpu.mem_read(src,len(live)))==bytes(live)
    if fast:
     assert reads==[(ARENA+INDICES+row*2,2)for row in range(overlap)]
     assert u16(cpu,addr('_nv_art_c2p')+8)==prefix
     assert u16(cpu,addr('_nv_art_c2p')+10)==overlap
   cpu.hook_del(wh);cpu.hook_del(rh)
   assert snapshots[0]==snapshots[1],('whole caller',total,prefix,odd,ccr)
   results.append(dict(whole_caller=True,height=total,prefix=prefix,overlap=overlap,odd=odd,ccr=ccr))

report=dict(status='PASS',module_sha256=META['sha256'],cases=len(results),coverage=results,
 oracle='Retained original H0+15390;16GPR/CCR/SP,full40016byteoutput,orderedfiveBYTEwritesperrow,sourceunchanged,indexreadexactness')
(artifact_dir('art')/'c2p-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(art_c2p_cases=len(results),module_sha256=META['sha256'])))
