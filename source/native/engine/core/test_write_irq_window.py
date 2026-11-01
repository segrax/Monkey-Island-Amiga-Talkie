"""Interrupt between bank store and commit sees old physical/shadow state."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
H=Path(__file__).resolve().parent
source=(H/'test_direct_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
results=[]
for address,offset,new in ((0xb6a,0,0x605c00),(0xac2,4,1),(0x84a,6,428),(0x96a,8,37)):
 for pending,speech in ((0,0),(0x100,0),(0x80,0),(0x100,1)):
  n={'__file__':str(H/'test_direct_driver.py'),'__name__':'write_irq_fixture'}
  exec(compile(source,str(H/'test_direct_driver.py'),'exec'),n)
  cpu=n['cpu'];r=n['r'];put=n['put'];get=n['get'];call=n['call'];sym=n['sym'];bank=n['bank'];driver=n['driver'];bases=n['bases']
  call('_nv_driver_start')
  # Old active sample is about to wrap into the OLD programmed reload region.
  for off,val in ((0,0x605800),(4,12),(8,0x605000),(12,8),(16,7),(20,321),(24,322),(28,322)):
   put(driver+off,val,4)
  put(driver+36,51,2);put(driver+38,1,2);put(driver+40,1 if pending==0x80 else 0,2);put(driver+42,0,2)
  put(bank,0x605800,4);put(bank+4,6,2);put(bank+6,322,2);put(bank+8,51,2)
  put(driver+n['layout']['speech_active'],speech,2)
  put(0xdff0a0,0x605800,4);put(0xdff0a4,6,2);put(0xdff0a6,322,2);put(0xdff0a8,64 if speech else 51,2)
  physical=bytes(cpu.mem_read(0xdff0a0,10))
  patch=next(p for p in n['meta']['patches'] if p['address']==address)
  put(bases[0]+0x17e2+0xc0,0,2)
  cpu.reg_write(r.UC_M68K_REG_A4,bank);cpu.reg_write(r.UC_M68K_REG_A5,bases[0]+0x17e2)
  cpu.reg_write(r.UC_M68K_REG_D0,new);cpu.reg_write(r.UC_M68K_REG_D1,64);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
  n['ticks']=101
  cpu.emu_start(bases[0]+address,sym('_nv_driver_write'),count=2000)
  assert get(bank+offset,4 if offset==0 else 2)==new
  assert bytes(cpu.mem_read(0xdff0a0,10))==physical
  assert get(driver+8,4)==0x605000 and get(driver+16,4)==7
  saved=cpu.context_save()
  if pending:
   # Model the assembly IRQ's register save/restore with a separate interrupt stack.
   n['hardware'][0xdff09a]|=pending;n['hardware'][0xdff09c]=pending
   put(0xdff01c,n['hardware'][0xdff09a],2);put(0xdff01e,pending,2)
   put(0x50d000,0x60f000,4);cpu.reg_write(r.UC_M68K_REG_SR,0x2700);cpu.reg_write(r.UC_M68K_REG_A7,0x50d000)
   cpu.emu_start(sym('_nv_driver_irq'),0x60f000,count=100000)
   assert bytes(cpu.mem_read(0xdff0a0,10))==physical
   assert get(driver+8,4)==0x605800 and get(driver+12,4)==12
   if pending==0x80:assert get(bases[0]+0x17e2,1)==255
   else:assert get(bases[0]+0x17e2+4,1)==255
  cpu.context_restore(saved)
  cpu.emu_start(sym('_nv_driver_write'),bases[0]+patch['continuation'],count=100000)
  assert get(driver+8,4)==0x605800 and get(driver+12,4)==12
  assert get(driver+16,4)==0 and get(driver+20,4)==4 and get(driver+28,4)==322
  assert get(driver+24,4)==(new if offset==6 else 322)
  if speech:assert bytes(cpu.mem_read(0xdff0a0,10))==physical
  else:assert get(0xdff0a0+offset,4 if offset==0 else 2)==new
  results.append(dict(offset=offset,irq=pending,speech=speech))
report=dict(checks=len(results),old_reload_and_latched_period_before_update=True,bank_write_does_not_change_physical_state_until_commit=True,irq_old_shadow_consistent=True,module_sha256=n['meta']['sha256'],scope='Compiled68000 with modeled Exec/Paula/clock; IRQ CPU context saved/restored explicitly.')
(BUILD / 'write-irq-window-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
