"""Compare timed music-register writes with a compiled baseline."""
import argparse,json,os
from pathlib import Path

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',required=True,type=Path)
args=parser.parse_args();current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]

def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build)
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'register_timing_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['cpu'].mem_map(0x620000,0x60000)
 ns['cpu'].mem_write(0x620000,bytes(range(256))*1536)
 ns['call']('_nv_driver_start');ns['irq']()
 for c in range(2):
  for off,value,size in ((0,0x620000+c*0x20000,4),(4,3+c*4,2),(6,124+c*198,2),(8,64,2)):
   ns['write'](c,off,value,size)
 ns['call']('_nv_driver_control',0,0x8203)
 ns['sample_callbacks']=[ns['get'](ns['sym']('_nv_driver')+54*c+46,4) for c in range(2)]
 assert len(set(ns['sample_callbacks']))==1
 for address in ns['sample_callbacks']:
  assert bytes(ns['cpu'].mem_read(address,10))==bytes.fromhex('202f0008204010104e75')
 return ns

def visible(a,b):
 assert a['hardware']==b['hardware']
 assert a['writes']==b['writes'], 'Different hardware event sequence'
 assert bytes(a['cpu'].mem_read(a['bases'][0]+0x17e2,16))==bytes(b['cpu'].mem_read(b['bases'][0]+0x17e2,16))
 assert bytes(a['cpu'].mem_read(a['bank'],64))==bytes(b['cpu'].mem_read(b['bank'],64))

def synced(a,b):
 visible(a,b)
 def native_state(ns):
  raw=bytearray(ns['cpu'].mem_read(ns['sym']('_nv_driver'),108))
  # The unchanged sample-read function moves when surrounding code changes.
  # Validate its original pointer and code before normalizing that relocation.
  for c,address in enumerate(ns['sample_callbacks']):
   offset=54*c+46
   assert int.from_bytes(raw[offset:offset+4],'big')==address
   assert bytes(ns['cpu'].mem_read(address,10))==bytes.fromhex('202f0008204010104e75')
   raw[offset:offset+4]=b'CALL'
  return raw
 assert native_state(a)==native_state(b)
 for side in range(2):
  for buffer in range(2):assert a['out'](side,buffer)==b['out'](side,buffer)

def irq_mask(ns,mask):
 ns['call']('_nv_driver_control',1,0x180)
 ns['call']('_nv_driver_control',2,0x180)
 ns['call']('_nv_driver_control',1,0x8000|(mask<<7))

cases=0;register_writes=0
for off in (0,4,6):
 for mask in range(4):
  for span in (1,71,65540):
   old,new=load(args.baseline),load(current)
   for ns in (old,new):irq_mask(ns,mask)
   # Interleave both virtual channels. Odd pointers normalize to their even
   # counterpart; zero length/period retain the hardware's maximum encoding.
   for step in range(16):
    c=step&1;k=step//2;base=0x620000+c*0x20000
    values={0:(base,base|1,base+0x1000,base+0x1001,base,base|1,base+0x1000,base+0x1001),
            4:(3+c*4,3+c*4,0,0,1,1,7,7),
            6:(124+c*198,124+c*198,0,0,161,161,65535,65535)}
    for ns in (old,new):
     ns['ticks']+=span+step
     ns['write'](c,off,values[off][k],4 if off==0 else 2)
    register_writes+=1;visible(old,new)
    if step%4==3:
     for ns in (old,new):ns['call']('_nv_driver_service')
     synced(old,new)
   # Accumulate repeated no-op writes without an intervening service, then
   # change another timed register before enabling a virtual IRQ.
   for ns in (old,new):irq_mask(ns,0)
   for step in range(6):
    for ns in (old,new):
     ns['ticks']+=65540+step
     ns['write'](step&1,off,values[off][-1] if off else 0x620001+(step&1)*0x20000+0x1000,4 if off==0 else 2)
    register_writes+=1;visible(old,new)
   for ns in (old,new):
    ns['write'](0,6,428 if off!=6 else 286)
   for ns in (old,new):ns['call']('_nv_driver_service')
   visible(old,new);synced(old,new)
   for ns in (old,new):
    irq_mask(ns,1<<(cases&1));ns['ticks']+=65540;ns['irq']()
   synced(old,new);cases+=1

clock_calls={};instructions={}
for off in (0,4,6):
 for mask in range(4):
  for unchanged in (False,True):
   key='%d_mask%d_%s'%(off,mask,'same' if unchanged else 'changed')
   for label,build in (('baseline',args.baseline),('current',current)):
    ns=load(build)
    # Include normalized zero encodings and odd pointers. No source boundary
    # occurs during this isolated measurement; timing must still be sampled.
    value={0:0x620001,4:0,6:0}[off]
    ns['write'](0,off,value,4 if off==0 else 2)
    irq_mask(ns,mask);ns['ticks']+=1
    if not unchanged:value={0:0x621000,4:1,6:161}[off]
    counts=[0,0]
    def count(uc,pc,size,unused):
     counts[0]+=1
     if pc in ns['clock_now_addresses']:counts[1]+=1
    hook=ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,count)
    ns['write'](0,off,value,4 if off==0 else 2)
    ns['cpu'].hook_del(hook)
    clock_calls.setdefault(key,{})[label]=counts[1]
    instructions.setdefault(key,{})[label]=counts[0]
   assert clock_calls[key]['baseline']==1,clock_calls
   assert clock_calls[key]['current']==(0 if off==6 and mask==0 and unchanged else 1),clock_calls

os.environ['MONKEY_ENGINE_BUILD']=current
report=dict(pass_=True,cases=cases,register_writes=register_writes,
 clock_calls=clock_calls,instructions=instructions,
 scope='compiled 68000 hardware/event sequences and synchronized DMA/output; clock/OS mocks')
(new['BUILD']/'register-timing.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
