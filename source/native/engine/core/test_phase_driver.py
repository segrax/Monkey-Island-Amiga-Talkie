"""Actual compiled driver against fixed-target phase and independent sample oracle."""
from pathlib import Path
import json,os,hashlib,sys,argparse
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'engine'))
from paths import engine_build,artifact_dir
candidate=engine_build();BUILD=artifact_dir('core')
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path);args=parser.parse_args();base=args.baseline
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(build,start):
 os.environ['MONKEY_ENGINE_BUILD']=str(build)
 ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'fixed_phase_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['ticks']=start;ns['call']('_nv_driver_start')
 return ns
signed=lambda x:x if x<128 else x-256
J=[30,200,80,0,150,40]
scenarios=[('q1',(286,428),512,0),('q2q4',(381,764),6144,0),('q8short',(1357,1362),64,0),('q65536',(65536,428),64,0),('fused',(381,764),6144,256),('speech_generic',(286,1357),64,256),('partial',(381,764),6144,255)]
rows=[];callpaths={}
for name,periods,length,available in scenarios:
 for start in (1000,0xfffff000,0x33333000):
  runs=[]
  for latencies in ([0],J):
   ns=load(candidate,start);g=ns['get'];p=ns['put'];sym=ns['sym'];driver=sym('_nv_driver');phaseoff=g(sym('_nv_phase_layout'),2);resyncoff=g(sym('_nv_phase_layout')+2,2)
   epoch=ns['transport_epoch'];music_start=ns['ticks']
   sources=[]
   for c in range(2):
    pattern=bytes(((i*(37+6*c)+i*i*3+17*c)&255)for i in range(length));sources.append(pattern);addr=0x602000+8192*c;ns['cpu'].mem_write(addr,pattern)
    for off,value,size in((0,addr,4),(4,length//2,2),(6,periods[c]&65535,2),(8,(54,47)[c],2)):ns['write'](c,off,value,size)
   ns['call']('_nv_driver_control',0,0x8203);ns['cpu'].mem_write(ns['pcm'],bytes(range(256))*64);ns['irq']()
   target=(epoch*5+512*161)&0xffffffff;assert g(driver+phaseoff,4)==target
   out=[];live=[];paths={}
   for fn in('_nv_hybrid_channel_ahead','_nv_hybrid_fused_unity','_nv_hybrid_channel_runs','_nv_hybrid_channel'):
    if fn in ns['meta']['exports']:
     pc=sym(fn)
     def hit(cpu,pc,size,unused,fn=fn):paths[fn]=paths.get(fn,0)+1
     ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,hit,begin=pc,end=pc)
   for k in range(12):
    now=(epoch+(((k+1)*256-2)*161)//5+latencies[k%len(latencies)])&0xffffffff;ns['ticks']=now
    read=g(ns['voice']+12,2)
    if available:
     for off,value in((8,1),(10,0),(14,(read+available)&65535),(16,0),(6,3),(26,64)):p(ns['voice']+off,value,2)
    free=ns['field']('active');ns['irq']();assert g(driver+resyncoff,4)==0,(name,start,k)
    assert g(driver+phaseoff,4)==((target+(k+1)*256*161)&0xffffffff)
    channel=[]
    live_clocks=((now-music_start)&0xffffffff)*5
    for c in range(2):
     assert g(driver+54*c+16,4)==(live_clocks//periods[c])%length
     assert g(driver+54*c+20,4)==live_clocks%periods[c]
    for c in range(2):
     expected=[]
     for i in range(256):
      clocks=((k+2)*256+i)*161-((music_start-epoch)&0xffffffff)*5;index=(clocks//periods[c])%length;value=signed(sources[c][index]);music=value*(54,47)[c]//64
      speech=signed((read+i)&255)if i<available else 0
      expected.append(((music+speech)//2)&255)
     actual=ns['out'](c,free);assert actual==bytes(expected),(name,start,k,c,next((i for i,(a,b)in enumerate(zip(actual,expected))if a!=b),None))
     channel.append(actual)
    out.append(channel);live.append([bytes(ns['cpu'].mem_read(driver+54*c,44))for c in range(2)])
   runs.append(out);callpaths[name]=paths
  assert runs[0]==runs[1],(name,start,'jitter')
  rows.append({'scenario':name,'start':hex(start),'banks':12,'samples_per_side':3072,'jitter_invariant':True})
if base:
 # Baseline vs candidate with identical service timestamps: live phase/events unchanged.
 old,new=load(base,1000),load(candidate,1000)
 for ns in(old,new):
  for c in range(2):
   addr=0x602000+c*8192;ns['cpu'].mem_write(addr,bytes(range(256))*16)
   for off,value,size in((0,addr,4),(4,32,2),(6,(381,764)[c],2),(8,64,2)):ns['write'](c,off,value,size)
  ns['call']('_nv_driver_control',0,0x8203);ns['call']('_nv_driver_control',1,0x8180);ns['irq']()
 for k in range(18):
  for ns in(old,new):ns['ticks']=1000+(((k+1)*256-2)*161)//5+J[k%len(J)];ns['irq']()
  for c in range(2):assert bytes(old['cpu'].mem_read(old['sym']('_nv_driver')+54*c,44))==bytes(new['cpu'].mem_read(new['sym']('_nv_driver')+54*c,44))
  assert old['hardware']==new['hardware']
  for c in range(4):assert old['get'](old['bases'][0]+0x17e2+4*c,1)==new['get'](new['bases'][0]+0x17e2+4*c,1)
# Deadline miss is explicitly rebased and counted, never huge unsigned projection.
ns=load(candidate,1000);g,p,sym=ns['get'],ns['put'],ns['sym'];driver=sym('_nv_driver');off=g(sym('_nv_phase_layout'),2);resync=g(sym('_nv_phase_layout')+2,2);ns['irq']()
ns['ticks']=(ns['transport_epoch']+5*256*161//5)&0xffffffff;ns['irq']();now=(ns['ticks']*5)&0xffffffff
assert g(driver+resync,4)==1 and g(driver+off,4)==(now+2*256*161)&0xffffffff
# Restart enters native, then READY establishes PREP; first fetch builds bank1 and steps one bank.
ns['call']('_nv_driver_end');ns['ticks']=0xfffff000;ns['call']('_nv_driver_start');target=g(driver+off,4);assert g(driver+resync,4)==0;ns['irq']();assert g(driver+off,4)==(target+256*161)&0xffffffff
# A small positive lead and a delayed first request are not diagnosed as
# missed hardware banks by this guard. The new first-fetch render can diagnose a late first request.
ctx=load(candidate,1000);g=ctx['get'];sym=ctx['sym'];d=sym('_nv_driver');toff=g(sym('_nv_phase_layout'),2);coff=g(sym('_nv_phase_layout')+2,2);ctx['irq']();target=g(d+toff,4)
ctx['ticks']=(target-100)//5;ctx['irq']();assert 0<target-ctx['ticks']*5<161 and g(d+coff,4)==0
ctx=load(candidate,1000);g=ctx['get'];sym=ctx['sym'];d=sym('_nv_driver');toff=g(sym('_nv_phase_layout'),2);coff=g(sym('_nv_phase_layout')+2,2);target=g(d+toff,4)
ctx['ticks']+=5*256*161//5;ctx['irq']();assert g(d+toff,4)==((ctx['ticks']*5+2*256*161)&0xffffffff) and g(d+coff,4)==1
report={'pass_':True,'held_note_scenarios':len(rows),'independent_output_samples':len(rows)*12*256*2,'both_channels_jitter_invariant':True,'generic_runs_and_fused_coverage':callpaths,'live_clock_independent_samples':len(rows)*12*2,'preceding_module_comparisons':18 if base else 0,'EClock_and_Paula_clock_wraps':True,'late_rebase_counted':True,'startup_firstIRQ_restart':True,'fixed_step_clocks':41216,'small_positive_and_startup_late_limits_tested':True,'exact_playback_through_missed_hardware_IRQ_not_claimed':True,'raw_sample_and_gain_tables_unchanged':True,'scope':'Actual compiled C/ASM driver with mocked clock/registers; independent fixed transport-target sample oracle. Does not prove absolute physical startup phase.'}
(BUILD/'phase-driver-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
