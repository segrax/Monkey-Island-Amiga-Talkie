"""Exercise compiled owned CIA clocks on V34/V37 with OS/hardware mocks."""
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
for a in (E-444,E-450,E-498,E-120,E-126,T-60):cpu.mem_write(a,bytes.fromhex('4e75'))
def os_call(uc,pc,size,data):
 assert pc not in (E-444,E-450,T-60),'Shared timer.device clock must not be used'
def wr(uc,access,address,size,value,data):
 if address==0xdff09a and value==0x4000:put(0xdff01c,0,2)
cpu.hook_add(unicorn.UC_HOOK_CODE,os_call);cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,wr)
def get(a,n):return int.from_bytes(cpu.mem_read(a,n),'big')
C=0x708800
cpu.mem_map(0xbfd000,0x2000)
for offset in (6,12,24):cpu.mem_write(C-offset,bytes.fromhex('4e75'))
cia=dict(available=False, busy=True, deny_b=False, attempts=[], acquired=None, removed=[], pending=0, race=False)
def counter(value):
 put(0xbfe601,value&255,1);put(0xbfe701,value>>8,1)
def cia_calls(uc,pc,size,data):
 if pc==E-498:
  assert bytes(cpu.mem_read(uc.reg_read(r.UC_M68K_REG_A1),14))==b'ciaa.resource\0'
  uc.reg_write(r.UC_M68K_REG_D0,C if cia['available'] else 0)
 elif pc==E-120:put(0xdff01c,0,2)
 elif pc==E-126:put(0xdff01c,0x4000,2)
 elif pc==C-6:
  bit=uc.reg_read(r.UC_M68K_REG_D0);cia['attempts'].append(bit)
  busy=cia['busy'] or (cia['deny_b'] and bit==1)
  cia['acquired']=None if busy else (bit,uc.reg_read(r.UC_M68K_REG_A1))
  uc.reg_write(r.UC_M68K_REG_D0,0x1234 if busy else 0)
 elif pc==C-12:
  cia['removed'].append((uc.reg_read(r.UC_M68K_REG_D0),uc.reg_read(r.UC_M68K_REG_A1)))
 elif pc==C-24:
  mask=uc.reg_read(r.UC_M68K_REG_D0)
  uc.reg_write(r.UC_M68K_REG_D0,cia['pending']);cia['pending']&=~mask
cpu.hook_add(unicorn.UC_HOOK_CODE,cia_calls)
def counter_wrap(uc,access,address,size,value,data):
 if address==0xbfe601 and cia['race']:
  cia['race']=False;counter(65530);cia['pending']|=2
cpu.hook_add(unicorn.UC_HOOK_MEM_READ,counter_wrap)
put(E+20,34,2);cia['available']=True
assert call('_nv_clock_start')==0 and cia['attempts']==[1,0]
cia['busy']=False;put(0xbfeF01,0x80,1);put(0xdff01c,0,2)
assert call('_nv_clock_start')==1 and get(0xdff01c,2)==0
assert get(sym('_nv_clock_hardware'),4)==0xbfe601
assert get(0xbfef01,1)==0x91 # preserve unrelated TOD mode
acquired=cia['acquired'];assert acquired[0]==1
attempts=len(cia['attempts']);assert call('_nv_clock_start')==1 and len(cia['attempts'])==attempts
counter(65500);assert call('_nv_clock_now')==35
counter(100);assert call('_nv_clock_now')==65435
counter(65520);cia['pending']=2;assert call('_nv_clock_now')==65551
assert call('_nv_clock_now')==65551 # pending wrap counted exactly once
# Deliver the wrap already observed by polling. Then another whole period
# elapses without a poll: its callback must retain that full period too.
interrupt=acquired[1];epoch=get(interrupt+14,4);handler=get(interrupt+18,4)
def callback():
 cia['pending']&=~2
 put(0x50f000,0x600000,4);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
 cpu.reg_write(r.UC_M68K_REG_A1,epoch);cpu.emu_start(handler,0x600000,count=10000)
callback();assert call('_nv_clock_now')==65551
callback()
assert call('_nv_clock_now')==131087
counter(1);cia['race']=True
assert call('_nv_clock_now')==196613 and cia['pending']==2
for sr in (0,0x2700):
 for master in (True,False):
  cpu.reg_write(r.UC_M68K_REG_SR,sr);put(0xdff01c,0x4000 if master else 0,2)
  assert call('_nv_clock_now')==196613
  assert bool(get(0xdff01c,2)&0x4000)==master
  assert cpu.reg_read(r.UC_M68K_REG_SR)&0x2700==sr
put(epoch,0xffff0000,4);put(epoch+4,0xfffffffe,4);put(epoch+8,1,2)
counter(65530);cia['pending']=2
assert call('_nv_clock_now')==5 # modulo-32-bit rollover, matching ReadEClock ev_lo
callback();assert call('_nv_clock_now')==5
call('_nv_clock_stop');assert cia['removed']==[acquired] and get(0xbfef01,1)==0x90
assert get(sym('_nv_clock_hardware'),4)==0
assert call('_nv_clock_now')==0
call('_nv_clock_stop');assert cia['removed']==[acquired]
cia['deny_b']=True;put(0xbfee01,0xc0,1)
assert call('_nv_clock_start')==1 and cia['acquired'][0]==0
assert get(0xbfee01,1)==0xd1 # preserve unrelated serial control bits
put(0xbfe401,65000&255,1);put(0xbfe501,65000>>8,1);cia['pending']=2
assert call('_nv_clock_now')==535 and cia['pending']==2 # leave another timer's pending bit alone
call('_nv_clock_stop');assert len(cia['removed'])==2 and get(0xbfee01,1)==0xd0
# V37 must use the same owned timer, including masked-wrap snapshots.
put(E+20,37,2);cia['deny_b']=False
for bad in (0,699999,720001):
 put(E+0x238,bad,4);attempts=len(cia['attempts'])
 assert call('_nv_clock_start')==0 and len(cia['attempts'])==attempts
put(E+0x238,709379,4)
assert call('_nv_clock_start')==1 and cia['acquired'][0]==1
counter(2);assert call('_nv_clock_now')==65533
counter(65530);cia['pending']=2
assert call('_nv_clock_now')==65541
call('_nv_clock_stop')
result=dict(pass_=True,scope='compiled68000 owned CIA clock on V34/V37 with OS/resource mocks; not full OS execution',module_sha256=meta['sha256'])
(BUILD / 'clock-lifecycle-results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
