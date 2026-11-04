"""Execute V39 timer ownership, TFMX routing, callbacks and cleanup on 68000."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_clock_lifecycle.py').read_text().split("put(E+20,34,2);cia['available']=True",1)[0]
prefix=prefix.replace("assert pc not in (E-444,E-450,T-60),'Shared timer.device clock must not be used'", "pass")
exec(compile(prefix,str(HERE/'test_clock_lifecycle.py'),'exec'))

cpu.mem_write(E-636,bytes.fromhex('4e75'))
put(E+20,40,2);put(E+0x238,709379,4);put(T+20,40,2)
cia['available']=True;cia['busy']=False
state=dict(ticks=123456,opens=0,closes=0,flushes=0,music=0,fail_open=False)
code=bases[0]
original=bytes(cpu.mem_read(code,0x1800))
cpu.mem_write(code+0x2cc,bytes.fromhex('4e75'))

def system_calls(uc,pc,size,data):
 if pc==E-444:
  assert bytes(cpu.mem_read(uc.reg_read(r.UC_M68K_REG_A0),13))==b'timer.device\0'
  assert uc.reg_read(r.UC_M68K_REG_D0)==2 # UNIT_ECLOCK
  state['opens']+=1
  put(uc.reg_read(r.UC_M68K_REG_A1)+20,T,4)
  uc.reg_write(r.UC_M68K_REG_D0,1 if state['fail_open'] else 0)
 elif pc==E-450:state['closes']+=1
 elif pc==E-636:state['flushes']+=1
 elif pc==T-60:
  put(0xdff01c,0x4000,2)
  at=uc.reg_read(r.UC_M68K_REG_A0)
  put(at,0,4);put(at+4,state['ticks'],4)
  uc.reg_write(r.UC_M68K_REG_D0,709379)
 elif pc==code+0x2cc:
  assert uc.reg_read(r.UC_M68K_REG_A6)==code+0x176e
  state['music']+=1
cpu.hook_add(unicorn.UC_HOOK_CODE,system_calls)

offsets=[0x922,0x92a,0x116e,0x1176,0x11a8,0x11b0,0x15d2,0x15da,0x15f6,0x15fe]
for deny_b in (False,True):
 cia['deny_b']=deny_b
 before=bytes(cpu.mem_read(code,0x1800))
 vector=0x765432;put(0x78,vector,4)
 assert call('_nv_clock_start')==1
 low=0xbfe401 if deny_b else 0xbfe601
 for i,offset in enumerate(offsets):assert get(code+offset,4)==low+(0 if i&1 else 0x100)
 for offset,size in ((0x1608,8),(0x1614,6),(0x1622,8),(0x162a,8)):
  assert bytes(cpu.mem_read(code+offset,size))==bytes.fromhex('4e71')*(size//2)
 assert get(code+0x161e,4)==low+(0xa00 if deny_b else 0x900)
 assert get(0x78,4)==vector
 assert clock_read()==state['ticks']
 state['ticks']+=9876
 assert clock_read()==state['ticks']
 # ReadEClock may transiently enable the master; both entries must restore it.
 for sr in (0,0x2700):
  for master in (False,True):
   cpu.reg_write(r.UC_M68K_REG_SR,sr);put(0xdff01c,0x4000 if master else 0,2)
   assert clock_read()==state['ticks']
   assert bool(get(0xdff01c,2)&0x4000)==master
   assert cpu.reg_read(r.UC_M68K_REG_SR)&0x2700==sr
 acquired=cia['acquired'];interrupt=acquired[1]
 handler=get(interrupt+18,4)
 def callback():
  put(0x50f000,0x600000,4);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
  cpu.reg_write(r.UC_M68K_REG_A1,get(interrupt+14,4))
  cpu.emu_start(handler,0x600000,count=10000)
  assert cpu.reg_read(r.UC_M68K_REG_PC)==0x600000
 previous=state['music']
 for inactive in (0,128):
  put(code+0x176e+0x44,inactive,1);callback();assert state['music']==previous
 put(code+0x176e+0x44,1,1);callback();assert state['music']==previous+1
 # Restore the test's flag before comparing every original player byte.
 put(code+0x176e+0x44,before[0x176e+0x44],1)
 call('_nv_clock_stop')
 assert bytes(cpu.mem_read(code,0x1800))==before
 assert get(0x78,4)==vector and get(sym('_nv_clock_hardware'),4)==0
 assert state['opens']==state['closes']
saved=get(code+offsets[0],4);put(code+offsets[0],0,4)
assert call('_nv_clock_start')==0 and state['opens']==state['closes']
assert get(sym('_nv_clock_hardware'),4)==0
put(code+offsets[0],saved,4)
cia['busy']=True
assert call('_nv_clock_start')==0 and state['opens']==state['closes']
cia['busy']=False
state['fail_open']=True
assert call('_nv_clock_start')==0 and state['opens']==state['closes']+1
assert state['flushes']==4
print('PASS: V39 TFMX uses a reserved CIAA timer; system clock, music callbacks and exact cleanup pass')
