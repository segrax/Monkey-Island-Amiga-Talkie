"""Exercise compiled ReadEClock lifecycle against explicit OS vector mocks."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
exec(compile((HERE/'test_context.py').read_text().split('put(g+0x19f8',1)[0],str(HERE/'test_context.py'),'exec'))
cpu.mem_map(0,0x1000);cpu.mem_map(0x700000,0x20000);cpu.mem_map(0xdff000,0x1000)
E=0x700800;T=0x710800
put(sym('_SysBase'),E,4);put(4,E,4)
for a in (E-444,E-450,T-60):cpu.mem_write(a,bytes.fromhex('4e75'))
state=dict(opens=0,closes=0,reads=0,open_fail=0,device_version=37,freq=709379,ticks=0,master=True)
def os_call(uc,pc,size,data):
 if pc==E-444:
  state['opens']+=1
  p=uc.reg_read(r.UC_M68K_REG_A1)
  assert get(p+18,2)==40 and uc.reg_read(r.UC_M68K_REG_D0)==2
  put(p+20,T,4);put(T+20,state['device_version'],2)
  uc.reg_write(r.UC_M68K_REG_D0,state['open_fail'])
 elif pc==E-450:state['closes']+=1
 elif pc==T-60:
  state['reads']+=1;p=uc.reg_read(r.UC_M68K_REG_A0)
  put(p,state['ticks']>>32,4);put(p+4,state['ticks']&0xffffffff,4)
  put(0xdff01c,0x4000,2) # OS implementation may Enable after raw master-off
  uc.reg_write(r.UC_M68K_REG_D0,state['freq'])
def wr(uc,access,address,size,value,data):
 if address==0xdff09a and value==0x4000:put(0xdff01c,0,2)
cpu.hook_add(unicorn.UC_HOOK_CODE,os_call);cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,wr)
def get(a,n):return int.from_bytes(cpu.mem_read(a,n),'big')
put(E+20,34,2);assert call('_nv_clock_start')==0 and state['opens']==0
put(E+20,37,2);put(E+0x238,709379,4)
state['open_fail']=1;assert call('_nv_clock_start')==0 and state['closes']==0
state['open_fail']=0;state['device_version']=35
assert call('_nv_clock_start')==0 and state['closes']==1
state['device_version']=37
for bad in (0,699999,720001,715909):
 state['freq']=bad;assert call('_nv_clock_start')==0
assert state['closes']==5
state['freq']=709379;put(0xdff01c,0,2);assert call('_nv_clock_start')==1
assert get(0xdff01c,2)==0
count=state['opens'];assert call('_nv_clock_start')==1 and state['opens']==count
for sr,master in ((0,True),(0,False),(0x2700,True),(0x2700,False)):
 cpu.reg_write(r.UC_M68K_REG_SR,sr);put(0xdff01c,0x4000 if master else 0,2)
 state['ticks']=0x12fffffffe;assert call('_nv_clock_now')==0xfffffffe
 assert bool(get(0xdff01c,2)&0x4000)==master
 assert cpu.reg_read(r.UC_M68K_REG_SR)&0x2700==sr
state['ticks']=0x1300000007;assert call('_nv_clock_now')==7
call('_nv_clock_stop');assert state['closes']==6
call('_nv_clock_stop');assert state['closes']==6 and call('_nv_clock_now')==0
assert call('_nv_clock_start')==1
call('_nv_clock_stop');assert state['closes']==7
result=dict(pass_=True,scope='compiled68000 with OS vector mocks; not real timer.device execution',state=state,module_sha256=meta['sha256'])
(BUILD / 'clock-lifecycle-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
