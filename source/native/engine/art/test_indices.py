"""Prove the linked row-index admission helper, including every uint16 value."""
from pathlib import Path
import json
import random

HERE = Path(__file__).resolve().parent
fixture = HERE.parent / 'core/test_driver.py'
ns = {'__file__': str(fixture), '__name__': 'art_indices_fixture'}
exec(compile(fixture.read_text().split("call('_nv_driver_start')", 1)[0], str(fixture), 'exec'), ns)
cpu, registers, unicorn = ns['cpu'], ns['r'], ns['unicorn']
cpu.mem_map(0x620000, 65536)
assert '_nv_art_indices' in ns['meta']['exports'], 'Build with --planar-cache'
rng = random.Random(0x494e4458)
callee = [getattr(registers, 'UC_M68K_REG_' + name)
          for name in ('D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'A2', 'A3', 'A4', 'A5', 'A6')]
active = None
cases = 0


def read(uc, access, address, size, value, unused):
    if 0x620000 <= address < 0x630000:
        assert active[0] <= address and address + size <= active[1]


cpu.hook_add(unicorn.UC_HOOK_MEM_READ, read)


def check(values, limit):
    global active, cases
    data = b''.join(value.to_bytes(2, 'big') for value in values)
    address = 0x620004 + 2 * (cases & 1)
    active = (address, address + len(data))
    before = b'PRE!' + data + b'POST'
    cpu.mem_write(address - 4, before)
    ns['put'](0x50f010, 0x504f5354, 4)
    saved = [rng.getrandbits(32) for _ in callee]
    cpu.reg_write(registers.UC_M68K_REG_SR, cases % 32)
    for register, value in zip(callee, saved):
        cpu.reg_write(register, value)
    ns['call']('_nv_art_indices', address, len(values), limit)
    expected = int(all(not (value & 1) and value <= limit for value in values))
    assert cpu.reg_read(registers.UC_M68K_REG_D0) == expected, (cases, limit)
    assert [cpu.reg_read(register) for register in callee] == saved
    assert cpu.reg_read(registers.UC_M68K_REG_A7) == 0x50f004
    assert [ns['get'](0x50f000 + i * 4, 4) for i in range(5)] == [
        0x60f000, address, len(values), limit, 0x504f5354]
    assert bytes(cpu.mem_read(address - 4, len(before))) == before
    cases += 1


for value in range(65536):
    check([value], 32754)
for limit in (0, 12, 14, 28, 32754):
    check([], limit)
    for count in (1, 2, 17, 120, 3240, 8000):
        values = [2 * rng.randrange(limit // 2 + 1) for _ in range(count)]
        check(values, limit)
        for position in sorted({0, count // 2, count - 1}):
            for bad in (1, limit + 2, 65535):
                changed = values.copy()
                changed[position] = bad
                check(changed, limit)

report = dict(pass_=True, cases=cases, all_uint16_indices=True,
              maximum_rows_and_corruption=True,
              callee_ABI_stack_source_and_read_bounds=True)
(ns['BUILD'] / 'art-indices-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
