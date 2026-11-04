"""Compare deferred volume writes against a compiled eager-timeline baseline."""
import argparse,json,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',required=True,type=Path)
parser.add_argument('--max-write-ratio',type=float,default=0.6)
args=parser.parse_args();current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build)
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'volume_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['call']('_nv_driver_start');ns['irq']()
 for c in range(2):
  ns['cpu'].mem_write(0x605000+c*512,bytes(range(256))*2)
  for off,value,size in ((0,0x605000+c*512,4),(4,7+c*3,2),(6,124+c*198,2),(8,64,2)):
   ns['write'](c,off,value,size)
 ns['call']('_nv_driver_control',0,0x8203)
 return ns
def visible(a,b):
 assert a['hardware']==b['hardware']
 assert bytes(a['cpu'].mem_read(a['bases'][0]+0x17e2,16))==bytes(b['cpu'].mem_read(b['bases'][0]+0x17e2,16))
def synced(a,b):
 visible(a,b)
 def state(ns):
  raw=bytearray(ns['cpu'].mem_read(ns['sym']('_nv_driver'),108))
  for c in range(2):
   off=54*c+46;pointer=int.from_bytes(raw[off:off+4],'big')
   assert bytes(ns['cpu'].mem_read(pointer,10))==bytes.fromhex('202f0008204010104e75')
   raw[off:off+4]=bytes(4)
  return raw
 assert state(a)==state(b)
 for side in range(2):
  for buffer in range(2):assert a['out'](side,buffer)==b['out'](side,buffer)
cases=0;fast_clock_calls={};write_instructions={}
for route in ('bank','volume'):
 for mask in range(4):
  for span in (1,71,65540):
   old,new=load(args.baseline),load(current)
   for ns in (old,new):
    ns['call']('_nv_driver_control',1,0x180)
    ns['call']('_nv_driver_control',2,0x180)
    ns['call']('_nv_driver_control',1,0x8000|(mask<<7))
   for step in range(12):
    for ns in (old,new):
     ns['ticks']+=span+step
     c=step&1;value=(0,1,63,64,128,255)[step%6]
     if route=='bank':ns['write'](c,8,value)
     else:ns['call']('_nv_driver_volume',ns['bank']+c*16,value)
    visible(old,new)
    # Several writes may cross samples/reloads before any timed operation.
    if step%4==3:
     for ns in (old,new):ns['call']('_nv_driver_service')
     synced(old,new)
   for ns in (old,new):ns['irq']()
   synced(old,new);cases+=1
 # Measure one isolated volume update with IRQs disabled/enabled.
 for mask in (0,1):
  for label,build in (('baseline',args.baseline),('current',current)):
   ns=load(build);ns['call']('_nv_driver_control',1,0x180);ns['call']('_nv_driver_control',2,0x180)
   if mask:ns['call']('_nv_driver_control',1,0x8080)
   ns['ticks']+=1000;counts=[0,0]
   def count(uc,pc,size,unused):
    counts[0]+=1
    if pc in ns['clock_now_addresses']:counts[1]+=1
   hook=ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,count)
   if route=='bank':ns['write'](0,8,32)
   else:ns['call']('_nv_driver_volume',ns['bank'],32)
   ns['cpu'].hook_del(hook)
   key=route+('_irq_enabled' if mask else '_irq_disabled')
   fast_clock_calls.setdefault(key,{})[label]=counts[1]
   write_instructions.setdefault(key,{})[label]=counts[0]
  assert fast_clock_calls[key]['current']==(1 if mask else 0),fast_clock_calls
  if not mask:assert write_instructions[key]['current']<write_instructions[key]['baseline']*args.max_write_ratio,write_instructions
os.environ['MONKEY_ENGINE_BUILD']=current
report=dict(pass_=True,cases=cases,volume_writes=cases*12,clock_calls=fast_clock_calls,instructions=write_instructions,scope='compiled 68000 external writes/events and synchronized DMA/output state; clock/OS mocks')
(new['BUILD']/'volume-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
