"""Check the compiled zero-fill helper's ABI, alignment and exact write bounds."""
from pathlib import Path
import json
import random

HERE = Path(__file__).resolve().parent
source = HERE / 'test_driver.py'
prefix = source.read_text().split("call('_nv_driver_start')", 1)[0]
exec(compile(prefix, str(source), 'exec'))

cpu.mem_map(0x900000, 0x20000)
saved_registers = [
    r.UC_M68K_REG_D2, r.UC_M68K_REG_D3, r.UC_M68K_REG_D4,
    r.UC_M68K_REG_D5, r.UC_M68K_REG_D6, r.UC_M68K_REG_D7,
    r.UC_M68K_REG_A2, r.UC_M68K_REG_A3, r.UC_M68K_REG_A4,
    r.UC_M68K_REG_A5, r.UC_M68K_REG_A6,
]
bounds = [0, 0]


def write_bounds(uc, access, address, size, value, unused):
    assert bounds[0] <= address and address + size <= bounds[1], (address, size, bounds)


cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_bounds)
rng = random.Random(48002)
counts = list(range(513)) + [1023, 1024, 1025, 4095, 4096, 32767, 32768, 65534, 65535]
cases = 0
for count in counts:
    for alignment in (0, 1):
        address = 0x900004 + alignment
        bounds[:] = [address, address + count]
        cpu.mem_write(address - 4, b'\xa5' * (count + 8))
        saved = {reg: rng.getrandbits(32) for reg in saved_registers}
        for reg, value in saved.items():
            cpu.reg_write(reg, value)
        cpu.reg_write(r.UC_M68K_REG_SR, rng.randrange(32))
        # NvU16 is carried in the low word of a stack argument.
        call('_nv_zero_output', address, 0xa1010000 | count)
        assert cpu.reg_read(r.UC_M68K_REG_A7) == 0x50f004
        assert all(cpu.reg_read(reg) == value for reg, value in saved.items())
        assert bytes(cpu.mem_read(address - 4, count + 8)) == b'\xa5' * 4 + b'\0' * count + b'\xa5' * 4
        cases += 1

# A zero count must not dereference the supplied pointer.
for address in (0, 1, 0xffffffff):
    bounds[:] = [address, address]
    call('_nv_zero_output', address, 0)
    cases += 1

report = dict(pass_=True, cases=cases, both_alignments=True,
              callee_registers_stack_and_write_bounds=True,
              count_0_through_512=True, maximum_u16_count=True,
              zero_count_does_not_dereference_pointer=True)
(BUILD / 'zero-output.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
