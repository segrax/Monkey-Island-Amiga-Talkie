"""Check compiled driver timestamp subtraction and unsigned Paula-clock scaling."""
from pathlib import Path
import json

HERE = Path(__file__).resolve().parent
source = HERE / 'test_hybrid_driver.py'
prefix = source.read_text().split("\ncall('_nv_driver_start')", 1)[0]
exec(compile(prefix, str(source), 'exec'))
call('_nv_driver_start')

# Intercept only the timeline callee. The real driver still computes and
# passes both channel addresses and clock counts through its compiled ABI.
entry = sym('_nv_paula_advance')
cpu.mem_write(entry, bytes.fromhex('4e75'))
seen = []


def capture(uc, pc, size, unused):
    if pc == entry:
        stack = uc.reg_read(r.UC_M68K_REG_A7)
        seen.append((get(stack + 4, 4) - driver, get(stack + 8, 4)))


cpu.hook_add(unicorn.UC_HOOK_CODE, capture)
cases = 0
elapsed_values = (0, 1, 0x33333333, 0x33333334, 0x7fffffff, 0x80000000, 0xffffffff)
for method in ('_nv_driver_service', '_nv_driver_irq'):
    for previous in (0, 0x12345678, 0xfffffff0):
        for elapsed in elapsed_values:
            ticks = (previous + elapsed) & 0xffffffff
            put(driver + layout['last_tick'], previous, 4)
            hardware[0xdff09c] = 0
            put(0xdff01e, 0, 2)
            seen.clear()
            call(method)
            expected = (elapsed * 5) & 0xffffffff
            assert seen == [(0, expected), (54, expected)], (method, previous, elapsed, seen)
            assert get(driver + layout['last_tick'], 4) == ticks
            cases += 1

report = dict(pass_=True, cases=cases, timestamp_wrap=True,
              unsigned_scale_overflow=True, both_channels_in_order=True,
              scope='Compiled driver; timeline callee intercepted to inspect stack arguments')
(BUILD / 'driver-clock-scale.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
