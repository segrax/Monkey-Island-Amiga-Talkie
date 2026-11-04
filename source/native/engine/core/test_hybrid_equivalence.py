"""Compare optimized and baseline compiled hybrid output using owned build fixtures."""
import argparse,json,os,random
from pathlib import Path

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',required=True,type=Path)
parser.add_argument('--max-active-ratio',type=float,default=0.65,help='Required active IRQ instruction ratio against the chosen baseline')
parser.add_argument('--max-idle-extra',type=int,default=0,help='Permitted extra instructions in the idle IRQ')
parser.add_argument('--max-speech-only-ratio',type=float,default=None,help='Optional speech-without-music instruction limit')
args=parser.parse_args()
current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build)
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'equivalence_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['call']('_nv_driver_start');ns['irq']()
 ns['read_callbacks']=[ns['get'](ns['sym']('_nv_driver')+54*c+46,4) for c in range(2)]
 ns['run_calls']=[0,0,0,0]
 if '_nv_hybrid_channel_runs' in ns['meta']['exports']:
  entry=ns['sym']('_nv_hybrid_channel_runs')
  def count_runs(cpu,pc,size,unused):
   if pc!=entry:return
   ns['run_calls'][0]+=1
   stack=cpu.reg_read(ns['r'].UC_M68K_REG_A7)
   snapshot=ns['get'](stack+4,4);step=ns['get'](stack+12,4)
   period=ns['get'](snapshot+24,4)
   remaining=ns['get'](snapshot+28,4)-ns['get'](snapshot+20,4)
   if 2*step<=period<8*step and 0<remaining<=8*step:
    ns['run_calls'][1]+=1
    if 2*step<=period<3*step:ns['run_calls'][2]+=1
    if 3*step<=period<4*step:ns['run_calls'][3]+=1
  ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,count_runs)
 return ns

def native_state(ns):
 raw=bytearray(ns['cpu'].mem_read(ns['sym']('_nv_driver'),108))
 for c,pointer in enumerate(ns['read_callbacks']):
  offset=54*c+46
  assert int.from_bytes(raw[offset:offset+4],'big')==pointer,'Sample callback changed'
  # Static read_sample relocates when earlier code grows. Prove its body
  # unchanged rather than discarding an unverified function-pointer field.
  assert bytes(ns['cpu'].mem_read(pointer,10))==bytes.fromhex('202f0008204010104e75')
  raw[offset:offset+4]=bytes(4)
 return bytes(raw)
old,new=load(args.baseline),load(current)
os.environ['MONKEY_ENGINE_BUILD']=current
rng=random.Random(1736);cases=0
for case in range(128):
 # Disable native DMA before changing reload/period data.
 for ns in (old,new):ns['call']('_nv_driver_control',0,0x200)
 params=[]
 for c in range(2):
  data=rng.randbytes(512);period=rng.choice((124,161,322,381,428,571,642,856,960,1017,1141,65535,0));volume=rng.choice((0,1,17,32,63,64));length=rng.choice((1,7,128,256))
  if case<8:period=(381,428,571,642,856,960,1017,1141)[(case+c)%8];volume=64
  params.append((data,period,volume,length))
 enabled=rng.choice((0,1,2,3));available=rng.choice((0,1,255,256,257,511,1000));read=rng.choice((0,16380,65530))
 if case<8:enabled=3
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
 for ns in (old,new):ns['native_state']=native_state(ns)
 assert old['native_state']==new['native_state'],case
 cases+=1
if '_nv_hybrid_channel_runs' in new['meta']['exports']:
 assert all(new['run_calls']),new['run_calls']

def irq_instructions(build,mode):
 ns=load(build)
 if mode!='idle':
  for c in range(2):
   ns['cpu'].mem_write(0x605000+512*c,bytes(range(256))*2)
   for off,value,size in ((0,0x605000+512*c,4),(4,256,2),(6,(856+285*c) if mode=='run_music' else (322+106*c),2),(8,64,2)):
    ns['write'](c,off,value,size)
  ns['call']('_nv_driver_control',0,0x8203 if mode in ('active','run_music') else 0x200)
  for off,value in ((8,1),(6,3),(12,0),(14,256),(16,0),(26,64)):ns['put'](ns['voice']+off,value,2)
  ns['cpu'].mem_write(ns['pcm'],bytes(range(256)))
 count=[0]
 def step(*unused):count[0]+=1
 hook=ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,step)
 ns['irq']();ns['cpu'].hook_del(hook)
 return count[0]
builds=(('baseline',args.baseline),('current',current))
instructions={label:irq_instructions(build,'idle') for label,build in builds}
active_instructions={label:irq_instructions(build,'active') for label,build in builds}
speech_only_instructions={label:irq_instructions(build,'speech_only') for label,build in builds}
run_music_instructions={label:irq_instructions(build,'run_music') for label,build in builds}
assert instructions['current'] <= instructions['baseline']+args.max_idle_extra,instructions
if args.max_speech_only_ratio is not None:
 assert speech_only_instructions['current'] < speech_only_instructions['baseline']*args.max_speech_only_ratio,speech_only_instructions
assert active_instructions['current'] < active_instructions['baseline']*args.max_active_ratio,active_instructions
os.environ['MONKEY_ENGINE_BUILD']=current
report=dict(pass_=True,cases=cases,source_run_calls=new['run_calls'][0],eligible_source_run_calls=new['run_calls'][1],q2_source_run_calls=new['run_calls'][2],q3_source_run_calls=new['run_calls'][3],source_run_irq_instructions=run_music_instructions,idle_irq_instructions=instructions,active_irq_instructions=active_instructions,speech_only_irq_instructions=speech_only_instructions,baseline=old['meta']['sha256'],current=new['meta']['sha256'],scope='compiled 68000 output/state differential with clock/OS mocks; not hardware timing')
(new['BUILD']/'hybrid-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
