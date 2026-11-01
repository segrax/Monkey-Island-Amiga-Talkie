"""Exercise the compiled zero-fill helper, including odd pointers and canaries."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util
from pathlib import Path

here = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('fixture', here / 'test_driver.py')
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)
checks = 0
for alignment in (0, 1):
    for count in (0, 1, 2, 3, 4, 5, 7, 8, 15, 255, 256, 257, 8191, 8192):
        begin = 0x601000 + alignment
        t.cpu.mem_write(begin - 8, b'\xa5' * (count + 16))
        t.call('_nv_zero_output', begin, count)
        assert bytes(t.cpu.mem_read(begin - 8, 8)) == b'\xa5' * 8
        assert bytes(t.cpu.mem_read(begin, count)) == b'\0' * count
        assert bytes(t.cpu.mem_read(begin + count, 8)) == b'\xa5' * 8
        checks += 1
print('Compiled zero-fill alignment/tail/canary checks PASS:', checks)
