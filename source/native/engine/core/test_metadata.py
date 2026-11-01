"""Run the compiled pointer-free metadata codec on an explicit 68000 fixture."""
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
HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('provenance_fixture', HERE/'test_provenance.py')
t = importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
from unicorn import m68k_const as r
cpu = t.cpu
put = t.put
buffer = 0x604000
def call(name, *args):
    for i, value in enumerate(args): put(0x50f004+4*i, value, 4)
    put(0x50f000, 0x600000, 4)
    cpu.reg_write(r.UC_M68K_REG_A7, 0x50f000)
    cpu.emu_start(t.t.sym(name), 0x600000, count=2000000)
    assert cpu.reg_read(r.UC_M68K_REG_PC) == 0x600000
    return cpu.reg_read(r.UC_M68K_REG_D0)

t.opcode(6, 203, 2, 192)  # Literal PC is opcode + 1 in this fixture.
t.resource(168, 0x600800, b'First saved line.\xff\x03Second saved line.\0')
t.expand(b'Before: \xff\x07\x23\x00 after.\0')
assert t.segment(0) == 'c:g:7:53:r:l:38:203:193:0'
assert call('_nv_metadata_export', buffer, 6574) == 6574
saved = bytes(cpu.mem_read(buffer, 6574))
assert saved[:16] == bytes.fromhex('4e564f31000100b70014000100000000')
call('_nv_metadata_clear')
assert bytes(cpu.mem_read(t.t.sym('_nv_dialogue_valid'), 2)) == b'\0\0'
assert call('_nv_metadata_import', buffer, 6574) == 1
assert t.segment(0) == 'c:g:7:53:r:l:38:203:193:0'
# A failed import must preserve every byte of the existing valid state.
assert call('_nv_metadata_export', buffer, 6574) == 6574
baseline = bytes(cpu.mem_read(buffer, 6574))
cases = [(0, b'BAD!'), (4, b'\x00\x02'), (6, b'\x00\xb8'),
         (10, b'\x00\x21'), (12, b'\x00\x02'), (14, b'\x00\x01'),
         (16, b'\x00\x09\x00\x00\x00\x00\x00\x01'),
         (4888+24, b'\x00\x20\x00\x10'), (5784, b'\x00\x02'),
         (5784+4+16, b'x'*256), (5784+4+272, b'\x02\x01')]
for offset, value in cases:
    corrupt = bytearray(saved); corrupt[offset:offset+len(value)] = value
    cpu.mem_write(buffer, bytes(corrupt))
    assert call('_nv_metadata_import', buffer, 6574) == 0, offset
    assert call('_nv_metadata_export', buffer, 6574) == 6574
    assert bytes(cpu.mem_read(buffer, 6574)) == baseline, offset
assert call('_nv_metadata_import', buffer, 6573) == 0
assert call('_nv_metadata_export', buffer, 6573) == 0
# Loaded game resources can have different pointers; no host/game pointers persist.
cpu.mem_write(buffer, saved)
put(t.t.g+0x2780+4*168, 0x600e00, 4)
cpu.mem_write(0x600e00, b'\0'*6+b'First saved line.\xff\x03Second saved line.\0')
assert call('_nv_metadata_import', buffer, 6574) == 1
t.expand(b'Before: \xff\x07\x23\x00 after.\0')
assert t.segment(0) == 'c:g:7:53:r:l:38:203:193:0'
# A resource absent from the loaded game must not inherit its saved definition.
put(t.t.g+0x2780+4*168, 0, 4)
cpu.mem_write(buffer, saved)
assert call('_nv_metadata_import', buffer, 6574) == 1
assert call('_nv_metadata_export', buffer, 6574) == 6574
assert bytes(cpu.mem_read(buffer+16+168*24, 24)) == b'\0'*24
result = dict(compiled_68000_metadata_pass=True, missing_resource_invalidated=True, fixed_bytes=6574,
              exact_BE_header=True, roundtrip_origin_caller_context_spans=True,
              relocated_resource_pointer_pass=True, malformed_transactional_cases=len(cases)+1,
              amiga_os_not_executed=True)
(BUILD / 'metadata-validation.json').write_text(json.dumps(result, indent=2)+'\n')
print(json.dumps(result))
