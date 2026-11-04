"""Check the linked 68000 checksum against an independent wide-integer oracle."""
from pathlib import Path
import hashlib
import json
import random

HERE = Path(__file__).resolve().parent
fixture = HERE.parent / 'core/test_driver.py'
ns = {'__file__': str(fixture), '__name__': 'art_checksum_fixture'}
exec(compile(fixture.read_text().split("call('_nv_driver_start')", 1)[0], str(fixture), 'exec'), ns)
cpu, registers, unicorn = ns['cpu'], ns['r'], ns['unicorn']
cpu.mem_map(0x620000, 65536)
assert '_nv_art_checksum' in ns['meta']['exports'], 'Build with --planar-cache'
rng = random.Random(0x464c4554)
callee = [getattr(registers, 'UC_M68K_REG_' + name)
          for name in ('D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'A2', 'A3', 'A4', 'A5', 'A6')]
active = None
cases = 0


def reference(data):
    # Unbounded accumulators and one final modulo avoid the native block algorithm.
    a = total = 65535
    for p in range(0, len(data), 2):
        a += int.from_bytes(data[p:p + 2], 'big')
        total += a
    return ((total % 65535 or 65535) << 16) | (a % 65535 or 65535)


def read(uc, access, address, size, value, unused):
    if 0x620000 <= address < 0x630000:
        assert active[0] <= address and address + size <= active[1], (address, size, active)


cpu.hook_add(unicorn.UC_HOOK_MEM_READ, read)


def check(data):
    global active, cases
    address = 0x620004 + 2 * (cases & 1)
    active = (address, address + len(data))
    initial = b'PRE!' + data + b'POST'
    cpu.mem_write(address - 4, initial)
    ns['put'](0x50f00c, 0x504f5354, 4)
    saved = [rng.getrandbits(32) for _ in callee]
    cpu.reg_write(registers.UC_M68K_REG_SR, cases % 32)
    for register, value in zip(callee, saved):
        cpu.reg_write(register, value)
    ns['call']('_nv_art_checksum', address, len(data))
    assert cpu.reg_read(registers.UC_M68K_REG_D0) == reference(data), cases
    assert [cpu.reg_read(register) for register in callee] == saved
    assert cpu.reg_read(registers.UC_M68K_REG_A7) == 0x50f004
    assert [ns['get'](0x50f000 + i * 4, 4) for i in range(4)] == [
        0x60f000, address, len(data), 0x504f5354]
    assert bytes(cpu.mem_read(address - 4, len(initial))) == initial
    cases += 1


for words in (0, 1, 2, 3, 4, 5, 354, 355, 356, 357, 358, 359, 360, 361,
              712, 713, 714, 1024, 16384):
    for byte in (0, 255):
        check(bytes([byte]) * (words * 2))
    check(rng.randbytes(words * 2))
for _ in range(64):
    check(rng.randbytes(2 * rng.randrange(16385)))

report = dict(pass_=True, cases=cases, independent_wide_integer_oracle=True,
              zero_maximum_word_and_block_boundaries=True, source_read_bounds=True,
              callee_ABI_stack_and_source_preserved=True,
              source_sha256=hashlib.sha256((HERE / 'art_checksum.s').read_bytes()).hexdigest())
(ns['BUILD'] / 'art-checksum-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
