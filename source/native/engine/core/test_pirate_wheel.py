"""Run generated pirate-wheel scripts through the shipped 68000 VM.

Requires a generated game folder and the native test dependencies. Rendering,
input and timer scheduling are modeled; arithmetic, branches, string mutation
and the original success comparison execute in the actual game VM.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import sys

NATIVE = Path(__file__).resolve().parents[2]
sys.pycache_prefix = str(NATIVE / 'build/python-cache')
sys.path.insert(0, str(NATIVE / 'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as r


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, required=True)
    args = parser.parse_args()
    recipe = json.loads((NATIVE.parent / 'assets/patches/pirate-wheel.json').read_text())
    disk = (args.game_dir / 'Rooms' / recipe['file']).read_bytes()
    assert hashlib.sha256(disk).hexdigest() == recipe['sha256']
    disk = bytes(x ^ recipe['xor'] for x in disk)

    def script(start, size):
        assert disk[start:start + 6] == struct.pack('<I', size) + b'SC'
        return disk[start + 6:start + size]

    welcome = script(recipe['patches'][0]['offset'] - 6 - 0xbf, 533)
    wheel = script(recipe['patches'][1]['offset'] - 6 - 0x103, 493)
    image = args.game_dir / 'Monkey_Talkie'
    pins = json.loads((NATIVE.parent / 'assets/supported-inputs.json').read_text())
    assert hashlib.sha256(image.read_bytes()).hexdigest() == pins['hybrid_engine']
    reader = HunkReader()
    assert reader.read_file(str(image)) == 0 and reader.build_segments()
    sections = [h for h in reader.hunks if h['type_name'] in ('HUNK_CODE', 'HUNK_DATA', 'HUNK_BSS')]
    bases = [0x100000 + i * 0x40000 for i in range(len(sections))]
    assert all(h['alloc_size'] <= 0x40000 for h in sections)
    cpu = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
    cpu.ctl_set_cpu_model(r.UC_CPU_M68K_M68000)
    cpu.mem_map(0, 0x1000000)

    def put(address, value, size):
        cpu.mem_write(address, int(value).to_bytes(size, 'big'))

    def get(address, size):
        return int.from_bytes(cpu.mem_read(address, size), 'big')

    current = 0
    for h in reader.hunks:
        current = h.get('hunk_no', current)
        if 'data' in h:
            cpu.mem_write(bases[current], h['data'])
        if h['type_name'] == 'HUNK_ABSRELOC32':
            for target, offsets in h['reloc'].items():
                for offset in offsets:
                    at = bases[current] + offset
                    put(at, get(at, 4) + bases[target], 4)
    globals_base = bases[2]
    code_base, string_base = 0xc00000, 0xc08000
    cpu.reg_write(r.UC_M68K_REG_SR, 0)

    def step(code, offset=0):
        cpu.mem_write(code_base, code)
        put(globals_base + 0x2024, 0, 1)
        put(globals_base + 0x5a56, code_base, 4)
        put(globals_base + 0x5a50, code_base + offset, 4)
        cpu.reg_write(r.UC_M68K_REG_A4, globals_base)
        cpu.reg_write(r.UC_M68K_REG_A7, 0xe00000)
        cpu.emu_start(bases[0] + 0x92a4, bases[0] + 0x92d4, count=10000)
        assert cpu.reg_read(r.UC_M68K_REG_PC) == bases[0] + 0x92d4
        return get(globals_base + 0x5a50, 4) - code_base

    # The welcome wait no longer reads Var[105] or needs an Enter event.
    assert welcome[0xbf] == 0x2e
    assert int.from_bytes(welcome[0xc0:0xc3], 'little') == 60
    assert step(welcome, 0xc3) == 0xd3

    # The answer is 1506 plus one unsigned byte from the wheel's date table.
    for year in range(1506, 1762):
        for variable, value in ((0x4003, 1000), (0x4004, 0), (0x4006, 21)):
            assert step(b'\x1a' + struct.pack('<HH', variable, value)) == 5
        put(globals_base + 0x3a5c + 2 * 266, year, 2)
        # String 39 is stored as resource 172, with a six-byte header.
        put(globals_base + 0x2780 + 4 * 172, string_base, 4)
        cpu.mem_write(string_base, b'\0' * 6 + b'Type in your answer: ' + b'\0' * 5)
        offset, displays, delays = 0xe6, [], []
        for _ in range(150):
            if offset in (0xe6, 0x15f, 0x180):
                offset += 12  # drawBox: rendering modeled
            elif offset in (0xf2, 0x16b):
                displays.append(bytes(cpu.mem_read(string_base + 6 + 21, 4)))
                offset += 17  # print: capture the actual mutated string
            elif offset == 0x1b9:
                break  # Original comparison accepted the entered year.
            elif offset == 0x198:
                raise AssertionError(f'Original comparison rejected {year}')
            elif wheel[offset] == 0x2e:
                delays.append(int.from_bytes(wheel[offset + 1:offset + 4], 'little'))
                offset += 4  # timer scheduling modeled
            else:
                offset = step(wheel, offset)
        else:
            raise AssertionError(f'Input loop did not finish for {year}')
        digits = str(year).encode()
        assert displays == [digits[:n] + b'\0' * (4 - n) for n in range(5)]
        assert delays == [90, 12, 12, 12, 30]
    print('PASS: answer strings for all 256 possible years accumulate four correct digits; '
          'original 68000 VM comparison accepts every answer; Enter wait automated. '
          'Rendering and timer scheduling modeled; AmigaOS not executed.')


if __name__ == '__main__':
    main()
