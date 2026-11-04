"""Compiled IRQ against an independent no-speech projection/output oracle."""
from pathlib import Path
import os,json,random
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]

def load(oracle=False):
 ns=dict(__file__=str(HERE/'test_hybrid_driver.py'),__name__='projected_irq_fixture')
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['call']('_nv_driver_start');ns['dma_irq']()
 if oracle:
  entry=ns['sym']('_nv_hybrid_channel_ahead')
  def independent(cpu,pc,size,unused):
   if pc!=entry:return
   r=ns['r'];get=ns['get'];stack=cpu.reg_read(r.UC_M68K_REG_A7)
   p=get(stack+4,4);step=get(stack+12,4);output=get(stack+16,4);ahead=get(stack+20,4)
   address=get(p+8,4);length=get(p+12,4);index=get(p+16,4)
   remaining=get(p+28,4)-get(p+20,4);period=get(p+24,4)
   reload=get(p,4);reload_length=get(p+4,4);volume=get(p+36,2)
   if ahead<remaining:remaining-=ahead
   else:
    clocks=ahead-remaining;index+=1+clocks//period;remaining=period-clocks%period
    if index>=length:index=(index-length)%reload_length;address=reload;length=reload_length
   expected=[]
   for i in range(256):
    value=get(address+index,1);value=value if value<128 else value-256
    expected.append((value*volume//128)&255)
    remaining-=step
    if remaining<=0:
     advances=(-remaining)//period+1;remaining+=advances*period;index+=advances
     if index>=length:index=(index-length)%reload_length;address=reload;length=reload_length
   cpu.mem_write(output,bytes(expected));cpu.reg_write(r.UC_M68K_REG_A7,stack+4);cpu.reg_write(r.UC_M68K_REG_PC,get(stack,4))
  ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,independent)
 return ns

rng=random.Random(553287);reports=[]
for case in range(96):
 old,new=load(True),load()
 periods=tuple(rng.choice([124,161,286,322,483,642,856,1287,1288,1351,1357,1362,1448,1449,4096,65536]) for _ in range(2))
 lengths=tuple(rng.choice([16,32,64,96,512,6144]) for _ in range(2))
 sources=[rng.randbytes(8192) for _ in range(2)]
 available=[0,0,0,0,128,256][case%6];gain=64 if case%2 else 47;enabled=case%4
 for ns in (old,new):
  for c in range(2):
   sample=0x602000+c*8192;ns['cpu'].mem_write(sample,sources[c])
   for off,value,size in [(0,sample,4),(4,lengths[c]//2,2),(6,periods[c]&65535,2),(8,41+13*c if case%5 else 0,2)]:ns['write'](c,off,value,size)
  ns['call']('_nv_driver_control',0,0x8200|enabled)
  read=16300 if case%7==0 else 0
  for off,value in [(8,case+1),(10,case+1 if case%11==0 else 0),(12,read),(14,read+available),(16,case%2),(6,3),(26,gain)]:ns['put'](ns['voice']+off,value,2)
  ns['cpu'].mem_write(ns['pcm'],bytes(range(256))*64);ns['ticks']+=100;ns['dma_irq']()
 for side in range(2):
  for buffer in range(2):assert old['out'](side,buffer)==new['out'](side,buffer),(case,side,buffer)
 assert bytes(old['cpu'].mem_read(old['voice'],48))==bytes(new['cpu'].mem_read(new['voice'],48)),('voice',case)
 assert bytes(old['cpu'].mem_read(old['sym']('_nv_driver'),108))==bytes(new['cpu'].mem_read(new['sym']('_nv_driver'),108)),('live',case)
 assert old['hardware']==new['hardware'] and old['writes']==new['writes'],('hardware',case)
 reports.append(dict(case=case,periods=periods,lengths=lengths,available=available,enabled=enabled))
report=dict(pass_=True,cases=len(reports),module_sha256=new['meta']['sha256'],scope='Current compiled IRQ against independent Python ahead/output oracle; complete voice, live music state, all output banks and ordered hardware writes',reports=reports)
(new['BUILD']/'projected-driver-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='reports'}))
