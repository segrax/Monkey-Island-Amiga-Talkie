"""Dedicated steady IRQ instruction count; clock/Exec calls are modeled."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
here = Path(__file__).resolve().parent
exec(compile((here/'test_direct_driver.py').read_text(), str(here/'test_direct_driver.py'), 'exec'))
counts = 0
def count_instruction(uc, pc, size, data):
    global counts
    counts += 1
cpu.hook_add(unicorn.UC_HOOK_CODE, count_instruction)
put(control+20,1,4)
clock_available = 1
call('_nv_driver_start')
write(0,sample,4);write(4,1000);write(6,322);write(8,51)
call('_nv_driver_control',0,0x820f)
put(voice+8,30,2);put(voice+10,0,2);put(voice+12,0,2)
put(voice+14,12000,2);put(voice+16,0,2);put(voice+6,3,2)
call('_nv_driver_service')
irq()
ticks += 1600
counts = 0
irq()
result = dict(module_sha256=meta['sha256'],steady_voice_irq_instructions=counts,
    samples=256,metric='compiled_68000_instructions_not_cycles',
    clock_and_exec_mocked=True, worker_signal_not_required=True,
    no_per_sample_native_render=True)
(BUILD / 'direct-profile.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
