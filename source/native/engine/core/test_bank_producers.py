"""Every native bank producer leaves canonical shadow coherent without control sync."""
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
n={'__file__':str(H/'test_direct_driver.py'),'__name__':'producer_fixture'}
exec(compile((H/'test_direct_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0],str(H/'test_direct_driver.py'),'exec'),n)
cpu=n['cpu'];r=n['r'];put=n['put'];get=n['get'];call=n['call'];driver=n['driver'];bank=n['bank'];bases=n['bases'];sym=n['sym']
call('_nv_driver_start');cpu.mem_write(0x605000,bytes(range(256))*8)

def invariant():
 assert get(driver,4)==get(bank,4)&0xfffffffe
 assert get(driver+4,4)==(get(bank+4,2)*2 if get(bank+4,2) else 131072)
 assert get(driver+24,4)==(get(bank+6,2) or 65536)
 v=get(bank+8,2);assert get(driver+36,2)==(64 if v&64 else v&63)
invariant();checks=[]
for patch in n['meta']['patches']:
 if not patch['symbol'].startswith('_nv_native_write_'):continue
 # Valid source operands for every original register-store footprint.
 put(bases[0]+0x17e2+0xc0,0,2);put(bases[0]+0x17e2+0xa0,322,2)
 put(bases[0]+0x17e2+0xb0,0x605100,4);put(bases[0]+0x17e2+0xd0,55,2)
 put(bases[0]+0x176e+4,0x605000,4);put(bases[0]+0x176e+0x2a,77,2)
 cpu.reg_write(r.UC_M68K_REG_A4,bank);cpu.reg_write(r.UC_M68K_REG_A5,bases[0]+0x17e2);cpu.reg_write(r.UC_M68K_REG_A6,bases[0]+0x176e)
 cpu.reg_write(r.UC_M68K_REG_A1,bases[0]+patch['continuation'])
 cpu.reg_write(r.UC_M68K_REG_D0,0x605100 if patch['address'] in (0xb6a,0xe82,0xea0) else 428)
 cpu.reg_write(r.UC_M68K_REG_D1,64);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
 cpu.emu_start(bases[0]+patch['address'],bases[0]+patch['continuation'],count=100000)
 assert cpu.reg_read(r.UC_M68K_REG_PC)==bases[0]+patch['continuation']
 invariant();checks.append(hex(patch['address']))
call('_nv_driver_clear_volume');invariant();assert get(driver+36,2)==0
# The old dormant bank-only writer is now a proper producer too.
call('_nv_driver_volume',bank,0x7f);invariant();assert get(driver+36,2)==64
n['write'](0,0x605101,4);n['write'](4,0);n['write'](6,0);invariant()
retained=bytes(cpu.mem_read(bank,12))
call('_nv_driver_end');call('_nv_driver_start')
assert bytes(cpu.mem_read(bank,12))==retained
invariant();assert get(driver+4,4)==131072 and get(driver+24,4)==65536
# A DMA start uses restored retained producer state, no control synchronize needed.
call('_nv_driver_control',0,0x8201)
assert get(driver+8,4)==0x605100 and get(driver+12,4)==131072
result=dict(original_store_wrappers=len(checks),addresses=checks,fresh_zero_bank_matches_defaults=True,clear_volume_coherent=True,dormant_bank_volume_coherent=True,same_image_retained_bank_restart_coherent=True,zero_len_period_and_odd_pointer_canonical=True,restart_dma_latches_correct_region=True,module_sha256=n['meta']['sha256'])
(BUILD / 'bank-producer-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
