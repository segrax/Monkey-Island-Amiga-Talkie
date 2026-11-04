"""The audio IRQ may preempt CIA dispatch after its pending bit is consumed."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_clock_lifecycle.py').read_text().split("put(E+20,34,2);cia['available']=True",1)[0]
exec(compile(prefix,str(HERE/'test_clock_lifecycle.py'),'exec'))
put(E+20,37,2);put(E+0x238,709379,4)
cia['available']=True;cia['busy']=False
assert call('_nv_clock_start')==1
counter(100)
assert clock_read()==65435
# Hardware wrapped. CIA dispatch has already consumed the pending bit, but a
# higher-priority audio IRQ arrives before the resource callback executes.
counter(65520);cia['pending']=0
now=locked_clock_read()
assert now==65551,('Clock moved backwards when CIA callback was deferred',now)
interrupt=cia['acquired'][1]
handler=get(interrupt+18,4)
def callback():
 put(0x50f000,0x600000,4);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
 cpu.reg_write(r.UC_M68K_REG_A1,get(interrupt+14,4))
 cpu.emu_start(handler,0x600000,count=10000)
callback()
assert clock_read()==65551,'Deferred callback counted the same wrap twice'
counter(100);assert clock_read()==130971
# A subsequent wrap may first be observed by the callback instead of polling.
counter(65510);callback()
assert clock_read()==131097
call('_nv_clock_stop')
print('PASS: deferred lower-priority CIA callbacks neither rewind nor double-count the clock')
