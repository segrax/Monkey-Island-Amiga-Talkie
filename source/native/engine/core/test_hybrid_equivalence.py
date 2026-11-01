"""Compare optimized and baseline compiled hybrid output using owned build fixtures."""
import argparse,json,os,random
from pathlib import Path

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',required=True,type=Path)
args=parser.parse_args()
current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build)
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'equivalence_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['call']('_nv_driver_start');ns['irq']()
 return ns
old,new=load(args.baseline),load(current)
os.environ['MONKEY_ENGINE_BUILD']=current
rng=random.Random(1736);cases=0
for case in range(128):
 # Disable native DMA before changing reload/period data.
 for ns in (old,new):ns['call']('_nv_driver_control',0,0x200)
 params=[]
 for c in range(2):
  data=rng.randbytes(512);period=rng.choice((124,161,322,428,65535,0));volume=rng.choice((0,1,17,32,63,64));length=rng.choice((1,7,128,256))
  params.append((data,period,volume,length))
 enabled=rng.choice((0,1,2,3));available=rng.choice((0,1,255,256,257,511,1000));read=rng.choice((0,16380,65530))
 eof=rng.randrange(2);cancel=rng.randrange(9)==0;gain=rng.choice((0,1,32,64,100));pcm=rng.randbytes(16384);tick=rng.randrange(1,10000)
 for ns in (old,new):
  for c,(data,period,volume,length) in enumerate(params):
   ns['cpu'].mem_write(0x605000+512*c,data)
   for offset,value,size in ((0,0x605000+512*c,4),(4,length,2),(6,period,2),(8,volume,2)):ns['write'](c,offset,value,size)
  ns['call']('_nv_driver_control',0,0x8200|enabled)
  voice=ns['voice'];put=ns['put'];generation=case+1
  for offset,value in ((8,generation),(10,generation if cancel else 0),(12,read),(14,(read+available)&65535),(16,eof),(6,3),(26,gain)):
   put(voice+offset,value,2)
  ns['cpu'].mem_write(ns['pcm'],pcm);ns['ticks']+=tick
  ns['irq']()
 for side in range(2):
  for buffer in range(2):assert old['out'](side,buffer)==new['out'](side,buffer),(case,side,buffer)
 for offset in (6,8,10,12,14,16,18,20,22):assert old['get'](old['voice']+offset,2)==new['get'](new['voice']+offset,2),(case,offset)
 assert old['hardware']==new['hardware'],case
 # Live virtual channel phase and reload/IRQ state must be unchanged.
 for ns in (old,new):ns['native_state']=bytes(ns['cpu'].mem_read(ns['sym']('_nv_driver'),108))
 assert old['native_state']==new['native_state'],case
 cases+=1
instructions={}
for label,build in (('baseline',args.baseline),('current',current)):
 ns=load(build);count=[0]
 def step(*unused):count[0]+=1
 hook=ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,step)
 ns['irq']();ns['cpu'].hook_del(hook);instructions[label]=count[0]
os.environ['MONKEY_ENGINE_BUILD']=current
assert instructions['current'] < instructions['baseline']//10,instructions
report=dict(pass_=True,cases=cases,idle_irq_instructions=instructions,baseline=old['meta']['sha256'],current=new['meta']['sha256'],scope='compiled 68000 output/state differential with clock/OS mocks; not hardware timing')
(new['BUILD']/'hybrid-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
