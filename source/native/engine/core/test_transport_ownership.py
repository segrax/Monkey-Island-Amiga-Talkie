"""Check physical stereo transport ownership across music writes and DMA clears."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]

def load(period):
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'transport_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['put'](ns['voice']+30,period,2)
 writes=[]
 def trace(uc,access,address,size,value,data):
  if 0xdff0a0<=address<0xdff0c0:writes.append((address,size,value))
 ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_MEM_WRITE,trace)
 ns['call']('_nv_driver_start')
 assert ns['get'](0xdff0a6,2)==period==ns['get'](0xdff0b6,2)
 assert ns['get'](0xdff0a8,2)==0==ns['get'](0xdff0b8,2)
 assert [w[0] for w in writes]==[0xdff0a8,0xdff0b8]*2+[0xdff0a6,0xdff0b6]*2+[0xdff0a0,0xdff0b0,0xdff0a4,0xdff0b4]
 assert [w[2] for w in writes[4:8]]==[124,124,period,period]
 assert all(ns['get'](ns['bases'][0]+0x1942+4*c,4)==ns['bank']+16*c for c in range(4))
 patches={p['address'] for p in ns['meta']['patches']}
 assert {0x1094,0x109a,0x10a0,0x10a6}<=patches
 writes.clear();ns['irq']()
 assert [w[0] for w in writes]==[0xdff0a8,0xdff0b8,0xdff0a0,0xdff0b0,0xdff0a4,0xdff0b4]
 assert ns['get'](0xdff0a8,2)==64==ns['get'](0xdff0b8,2)
 return ns,writes

rows=[]
for period in (124,161,322):
 ns,writes=load(period);call,put,get=ns['call'],ns['put'],ns['get']
 for step in range(40):
  writes.clear()
  for c in range(4):
   ns['cpu'].mem_write(0x605000+512*c,bytes(range(256))*2)
   for offset,value,size in ((0,0x605000+512*c,4),(4,256,2),(6,(124,322,428,856)[c],2),(8,(step+c)%65,2)):
    ns['write'](c,offset,value,size)
   call('_nv_driver_volume',0xdff0a0+16*c,(step+c)%65)
   call('_nv_driver_clear_native_volume',c)
  for kind,value in ((0,0x20f),(0,0x820f),(1,0x180),(1,0x8180),(2,0x180)):
   call('_nv_driver_control',kind,value)
  # Re-enable after a graphics DMA clear; PER/VOL retain their physical state.
  ns['hardware'][0xdff096]=0;put(0xdff002,0,2);call('_nv_driver_control',0,0x820f)
  assert not writes,'Music hooks wrote physical transport registers'
  ns['ticks']+=1000;free=ns['field']('active');ns['irq']()
  assert writes==[(0xdff0a0,4,ns['ptr'](0,free)),(0xdff0b0,4,ns['ptr'](1,free)),(0xdff0a4,2,128),(0xdff0b4,2,128)]
  assert get(0xdff0a6,2)==period==get(0xdff0b6,2)
  assert get(0xdff0a8,2)==64==get(0xdff0b8,2)
  assert ns['out'](0,free)==bytes(256)==ns['out'](1,free)
 call('_nv_driver_end')
 assert all(get(0xdff0a8+16*c,2)==0 for c in range(4))
 rows.append(dict(output_period=period,steps=40,steady_transport_writes=4))
report=dict(pass_=True,cases=120,rows=rows,
 scope='compiled 68000 startup/handoff, mirrored music writes, DMA recovery and shutdown; OS/Paula mocks')
(ns['BUILD']/'transport-ownership.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))

