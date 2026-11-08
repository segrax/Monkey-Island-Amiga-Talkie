"""Execute original/fixed pointer routines with an Intuition SetPointer mock."""
from pathlib import Path
import json
import struct
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT, engine_build, artifact_dir
sys.path.insert(0, str(PROJECT_ROOT / 'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as r
from patch import ADDRESS, EXPECTED, REPLACEMENT, corrected

reader = HunkReader()
assert reader.read_file(str(engine_build() / 'module/Monkey_Talkie_Test')) == 0 and reader.build_segments()
code = next(h['data'] for h in reader.hunks if h.get('hunk_no') == 0 and 'data' in h)
assert code[ADDRESS:ADDRESS + 4] == REPLACEMENT
# The original allocates 96 cleared Chip bytes and hides using its final 24.
assert code[0x13b5c:0x13b66] == bytes.fromhex('7048d080223c00010002')
assert code[0x15126:0x1512a] == bytes.fromhex('d0fc0048')

cases = 0
for model in (r.UC_CPU_M68K_M68000, r.UC_CPU_M68K_M68020, r.UC_CPU_M68K_M68030):
    for ccr in range(32):
        for fixed, visible in ((False, False), (True, False), (True, True)):
            cpu = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
            cpu.ctl_set_cpu_model(model)
            cpu.mem_map(0, 0x1000000)
            cpu.mem_write(0x100000, code)
            if not fixed:
                cpu.mem_write(0x100000 + ADDRESS, EXPECTED)
            globals_base, ring = 0x200000, 0x500000
            # Nonzero neighboring allocation reproduces the unwanted sprite.
            cpu.mem_write(ring, b'\x5a' * 72 + b'\0' * 24 + b'\xa5' * 80)
            for offset, value in ((0x6f9c, ring), (0x70e4, 0x600000), (0x7258, 0x700000)):
                cpu.mem_write(globals_base + offset, struct.pack('>I', value))
            cpu.mem_write(0x700000 - 270, bytes.fromhex('4e75'))
            cpu.mem_write(0x900000, struct.pack('>I', 0xa00000))
            cpu.reg_write(r.UC_M68K_REG_SR, ccr)
            cpu.reg_write(r.UC_M68K_REG_A4, globals_base)
            cpu.reg_write(r.UC_M68K_REG_A7, 0x900000)
            cpu.reg_write(r.UC_M68K_REG_D2, 0x12345678)
            cpu.reg_write(r.UC_M68K_REG_D3, 0x87654321)
            calls = []

            def pointer(uc, pc, size, unused):
                if pc != 0x700000 - 270:
                    return
                data = uc.reg_read(r.UC_M68K_REG_A1)
                height = uc.reg_read(r.UC_M68K_REG_D0)
                width = uc.reg_read(r.UC_M68K_REG_D1)
                assert uc.reg_read(r.UC_M68K_REG_A0) == 0x600000
                assert uc.reg_read(r.UC_M68K_REG_D2) == (0xfffffff7 if visible else 0)
                assert uc.reg_read(r.UC_M68K_REG_D3) == (0xfffffff9 if visible else 0)
                assert data == ring + (0 if visible else 72) and width == 16
                sprite_bytes = 4 * height + 8
                sprite = bytes(uc.mem_read(data, sprite_bytes))
                calls.append((height, sprite_bytes, any(sprite), data + sprite_bytes <= ring + 96))

            cpu.hook_add(unicorn.UC_HOOK_CODE, pointer)
            cpu.emu_start(0x100000 + (0x150fc if visible else 0x1511e), 0xa00000, count=100)
            assert cpu.reg_read(r.UC_M68K_REG_PC) == 0xa00000
            expected = [(16, 72, True, True)] if visible else (
                [(1, 12, False, True)] if fixed else [(16, 72, True, False)])
            assert calls == expected
            assert cpu.reg_read(r.UC_M68K_REG_D2) == 0x12345678
            assert cpu.reg_read(r.UC_M68K_REG_D3) == 0x87654321
            cases += 1

raw = bytes(ADDRESS) + EXPECTED + b'unchanged'
assert corrected(raw, 0, []) == bytes(ADDRESS) + REPLACEMENT + b'unchanged'
for bad in (corrected(raw, 0, []), raw[:ADDRESS] + b'bad!' + raw[ADDRESS + 4:]):
    try:
        corrected(bad, 0, [])
    except ValueError:
        pass
    else:
        raise AssertionError('Unknown/double patch accepted')
for offset in range(ADDRESS - 3, ADDRESS + 4):
    try:
        corrected(raw, 0, [offset])
    except ValueError:
        pass
    else:
        raise AssertionError('Relocation overlap accepted')
report = dict(PASS=True, cases=cases, models=['68000', '68020', '68030'],
    original_overread_reproduced=True, fixed_sprite_blank_and_within_allocation=True,
    patch_guards=True, intuition_mocked=True, amigaos_executed=False)
(artifact_dir('cursor') / 'pointer-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
