"""Check direct Paula register routing, gain and ABI independently of the C fallback."""
from pathlib import Path
import json,random,struct
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
ns=dict(__file__=str(HERE/'test_hybrid_driver.py'),__name__='write_dispatch_fixture')
exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
ns['call']('_nv_driver_start')
cpu,r=ns['cpu'],ns['r'];bank=ns['bank'];assert bank%2==0
control=ns['sym']('_nv_control');flags=ns['get'](control+20,4);rng=random.Random(0x5041554c)
regs=[getattr(r,'UC_M68K_REG_'+name) for name in ('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6')]
cases=[]
for c in (2,3):
 for physical in (False,True):
  address=0xdff0a0+16*c if physical else bank+16*c
  for offset in (0,2,4,6,8,10,12,14):cases.append((True,c,address,offset,None))
  for high in (0,0x100,0x8000,0xff00):
   for value in range(256):cases.append((True,c,address,8,high|value))
for enabled in (False,True):
 for address in (0,bank-1,bank+1,bank+17,bank+49,0xdff0a1,0xdff0e0):cases.append((enabled,None,address,8,None))
for c in range(4):
 for address in (bank+16*c,0xdff0a0+16*c):cases.append((False,c,address,8,None))
clock_calls=[0]
def trace(uc,pc,size,unused):
 if pc in ns['clock_now_addresses']:clock_calls[0]+=1
hook=cpu.hook_add(ns['unicorn'].UC_HOOK_CODE,trace)
for number,(enabled,c,address,offset,volume) in enumerate(cases):
 values=[rng.getrandbits(32) for _ in regs]
 for reg,value in zip(regs,values):cpu.reg_write(reg,value)
 cpu.mem_write(bank,bytes(rng.randrange(256) for _ in range(64)))
 if volume is not None:ns['put'](bank+16*c+8,volume,2)
 raw=bytes(cpu.mem_read(bank,64));before=bytes(cpu.mem_read(ns['driver'],ns['layout']['size']))
 expected=dict(ns['hardware']);audio=bytearray(cpu.mem_read(0xdff0a0,64))
 if enabled and c is not None:
  value=int.from_bytes(raw[16*c+offset:16*c+offset+(4 if offset==0 else 2)],'big')
  if offset==8:value=32 if value&64 else (value&63)//2
  length=4 if offset==0 else 2;audio[16*c+offset:16*c+offset+length]=value.to_bytes(length,'big')
 ns['put'](control+20,flags if enabled else flags&~2,4)
 ns['call']('_nv_driver_write',address,offset)
 assert bytes(cpu.mem_read(0xdff0a0,64))==bytes(audio),(number,c,offset,'Paula register value')
 assert ns['hardware']==expected,(number,c,offset,'hardware routing/value')
 assert bytes(cpu.mem_read(bank,64))==raw,(number,'mirror modified')
 assert bytes(cpu.mem_read(ns['driver'],ns['layout']['size']))==before,(number,'virtual timing/state changed')
 assert [cpu.reg_read(reg) for reg in regs]==values,(number,'callee register')
 assert cpu.reg_read(r.UC_M68K_REG_A7)==0x50f004
 assert bytes(cpu.mem_read(0x50f000,12))==struct.pack('>III',0x60f000,address,offset)
assert clock_calls[0]==0,clock_calls
cpu.hook_del(hook)
report=dict(pass_=True,cases=len(cases),both_bank_and_physical_address_forms=True,disabled_and_invalid_addresses=True,all_byte_volume_values_and_high_bits=True,callee_registers_stack_and_mirrors_unchanged=True,no_virtual_clock_or_state_updates=True)
(ns['BUILD']/'write-dispatch-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
