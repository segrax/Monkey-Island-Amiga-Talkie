"""Count compiled 68000 voice-render instructions, not processor cycles."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util
import json
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fixture', here / 'test_driver.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
import unicorn

count = 0
def instruction(uc, pc, size, data):
    global count
    count += 1
t.cpu.hook_add(unicorn.UC_HOOK_CODE, instruction)
driver = t.sym('_nv_driver')
sample = 0x605000
t.cpu.mem_write(sample, bytes([32, 224]) * 128)
t.cpu.mem_write(t.pcm, bytes(range(256)) * 32)
results = dict(module_sha256=t.meta['sha256'], samples=256,
               metric='compiled_68000_instructions_not_cycles')
for output_period in (161, 322):
  for dma in (0, 1):
    for state in (3, 4):
        t.call('_nv_paula_dma', driver, 0)
        t.call('_nv_paula_pointer', driver, sample)
        t.call('_nv_paula_length', driver, 128)
        t.call('_nv_paula_period', driver, 322)
        t.call('_nv_paula_volume', driver, 64)
        t.call('_nv_paula_dma', driver, dma)
        t.put(t.voice + 8, 50 + dma * 2 + state, 2)
        t.put(t.voice + 10, 0, 2)
        t.put(t.voice + 12, 0, 2)
        t.put(t.voice + 14, 8192, 2)
        t.put(t.voice + 16, 0, 2)
        t.put(t.voice + 26, 64, 2)
        t.put(t.voice + 6, state, 2)
        # Cost model only: no speech resampling or playable low-rate build.
        t.put(driver + 64, output_period, 2)
        count = 0
        t.call('_nv_mixer_render', driver, 0x606000, 256, 20)
        results[f'period_{output_period}_dma_{dma}_state_{state}'] = dict(
            instructions=count, consumed=t.get(t.voice + 12, 2),
            instructions_per_sample=count / 256,
            modeled_rate=22050 * 161 / output_period,
            instructions_per_second=count * 22050 * 161 / output_period / 256)
(BUILD / 'voice-profile.json').write_text(json.dumps(results, indent=2) + '\n')
print(json.dumps(results, indent=2))
