"""Compiled fused IRQ against an independent sample oracle and dispatch coverage."""
from pathlib import Path
import os,json,random
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(oracle=False):
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'fused_irq_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['call']('_nv_driver_start');ns['dma_irq']()
 if oracle:
  entry=ns['sym']('_nv_hybrid_fused_unity')
  def independent(cpu,pc,size,unused):
   if pc!=entry:return
   r=ns['r'];stack=cpu.reg_read(r.UC_M68K_REG_A7);get=ns['get']
   p=get(stack+4,4);step=get(stack+12,4);output=get(stack+16,4);speech=get(stack+20,4)
   at=get(p+16,4);remaining=get(p+28,4)-get(p+20,4);period=get(p+24,4)
   address=get(p+8,4);length=get(p+12,4);reload=get(p,4);reload_length=get(p+4,4);volume=get(p+36,2)
   signed=lambda n:n if n<128 else n-256
   expected=[]
   for value in bytes(cpu.mem_read(speech,256)):
    sample=signed(bytes(cpu.mem_read(address+at,1))[0]);expected.append(((sample*volume//64+signed(value))//2)&255)
    remaining-=step
    if remaining<=0:
     advances=(-remaining)//period+1;remaining+=advances*period;at+=advances
     if at>=length:at=(at-length)%reload_length;address=reload;length=reload_length
   cpu.mem_write(output,bytes(expected));cpu.reg_write(r.UC_M68K_REG_A7,stack+4);cpu.reg_write(r.UC_M68K_REG_PC,get(stack,4))
  ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,independent)
 return ns
rng=random.Random(87123)
reports=[]
def scenario(name,periods=(642,856),gain=64,read=0,available=256,length=512,volumes=(41,54),enabled=3,latched=None,cancel=False,expected_calls=0,music_delay=0,expected_remaining=None):
 global old,new
 old,new=load(True),load()
 pcm=rng.randbytes(16384);sources=[rng.randbytes(4096) for _ in range(2)]
 dispatch={}
 for label,ns in (('baseline',old),('current',new)):
  ns['ticks']+=music_delay
  for c in range(2):
   address=0x605000+c*4096;ns['cpu'].mem_write(address,sources[c])
   for off,value,size in ((0,address,4),(4,length,2),(6,periods[c],2),(8,volumes[c],2)):ns['write'](c,off,value,size)
  ns['call']('_nv_driver_control',0,0x8200|enabled)
  if latched:
   for c in range(2):ns['put'](ns['sym']('_nv_driver')+54*c+28,latched,4)
  for off,value in ((8,1),(10,1 if cancel else 0),(12,read),(14,(read+available)&65535),(16,1),(6,3),(26,gain)):ns['put'](ns['voice']+off,value,2)
  ns['cpu'].mem_write(ns['pcm'],pcm)
  calls=[0];entry=ns['sym']('_nv_hybrid_fused_unity');observed=[]
  def snapshot(cpu,pc,size,unused):
   stack=cpu.reg_read(ns['r'].UC_M68K_REG_A7);ptr=ns['get'](stack+4,4)
   observed.append(ns['get'](ptr+12,4)-ns['get'](ptr+16,4))
  probes=[ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,snapshot,begin=ns['sym'](fn),end=ns['sym'](fn))for fn in('_nv_hybrid_fused_unity','_nv_hybrid_channel_runs','_nv_hybrid_channel')] if label=='current' else []
  def step(cpu,pc,size,unused):
   calls[0]+=1
  hook=ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,step,begin=entry,end=entry);ns['dma_irq']();ns['cpu'].hook_del(hook)
  dispatch[label]=calls[0]
  for probe in probes:ns['cpu'].hook_del(probe)
  if expected_remaining is not None and label=='current':assert observed and observed[0]==expected_remaining,(name,observed)
 for side in range(2):
  for buffer in range(2):assert old['out'](side,buffer)==new['out'](side,buffer),(name,side,buffer)
 for off in (6,8,10,12,14,16,18,20,22):assert old['get'](old['voice']+off,2)==new['get'](new['voice']+off,2),(name,off)
 assert old['hardware']==new['hardware'],name
 assert bytes(old['cpu'].mem_read(old['sym']('_nv_driver'),108))==bytes(new['cpu'].mem_read(new['sym']('_nv_driver'),108)),name
 assert new['get'](new['voice']+12,2)==((read+available if cancel else read+min(available,256))&65535),name
 assert dispatch['current']==expected_calls,(name,dispatch)
 reports.append(dict(name=name,fused_calls=dispatch['current']))
scenario('eligible',expected_calls=2)
scenario('clamped_unity',gain=100,expected_calls=2)
scenario('mixed_periods',periods=(642,286))
scenario('nonunity',gain=63)
scenario('ring_wrap',read=16200)
scenario('cursor_wrap',read=65530)
scenario('no_speech',available=0)
scenario('odd_speech',read=1)
scenario('partial_speech',available=255)
scenario('short_source',length=32)
scenario('one_virtual',enabled=1)
scenario('zero_volume',volumes=(0,54))
scenario('below_q3',periods=(482,856),expected_calls=2)
scenario('q2_boundary',periods=(322,856),expected_calls=2)
scenario('below_q2',periods=(321,856))
scenario('q2_short130',periods=(322,856),length=193,expected_calls=2,expected_remaining=130)
scenario('q2_short128',periods=(322,856),length=192,expected_remaining=128)
scenario('q3_boundary',periods=(483,856),expected_calls=2)
scenario('below_q8',periods=(1287,856),expected_calls=2)
scenario('q8_boundary',periods=(1288,856))
scenario('span_96',periods=(642,642),length=112,expected_calls=2,expected_remaining=96)
scenario('span_94',periods=(642,642),length=111,expected_remaining=94)
scenario('old_latched_prefix',latched=65536,music_delay=4096)
scenario('cancelled',cancel=True)
report=dict(pass_=True,cases=len(reports),module_sha256=new['meta']['sha256'],scope='current compiled IRQ against independent Python fused-output oracle; full live state, hardware and explicit cursor comparison',profiles=reports)
(new['BUILD']/'fused-driver-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

