"""Compare period/volume adapters with original instructions and real callbacks."""
import json, random, itertools
from pathlib import Path

HERE = Path(__file__).resolve().parent
prefix = (HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')", 1)[0]
fixture = (HERE/'test_driver.py').read_text().split("call('_nv_driver_start')", 1)[0]
fixture_line = 'prefix=(HERE/\'test_driver.py\').read_text().split("call(\'_nv_driver_start\')",1)[0]'

def load(model,route):
    driver = fixture.replace('r.UC_CPU_M68K_M68000', 'r.UC_CPU_M68K_'+model)
    source = prefix.replace(fixture_line, 'prefix='+repr(driver))
    assert source != prefix
    ns = dict(__file__=str(HERE/'test_hybrid_driver.py'), __name__='word_wrapper_fixture', NATIVE_START=bool(route))
    exec(compile(source, str(HERE/'test_hybrid_driver.py'), 'exec'), ns)
    ns['call']('_nv_driver_start')
    return ns

# Original instructions through the mirrored MOVE.W, excluding the terminal
# JMP (A1). Relative branches stay within each copied instruction sequence.
original = {
    0x84a: '4a6d00c0660439400006', 0x8ae: '39400006',
    0xac8: '397c00040006', 0xd5c: '4a6d00c0660439400006',
    0xd76: '396e002a0006', 0xdc4: '396d00a00006',
    0x96a: '080100066608d040d040c0c1e04839400008',
    0xb0e: '080100066608d040d040c0c1e04839400008',
}
values = [0, 1, 63, 64, 65, 127, 128, 255, 256, 32767, 32768, 65535]
rng = random.Random(97422)
cases = 0
for model,route in itertools.product(('M68000','M68020'),(0,1)):
    reference, actual = load(model,route), load(model,route)
    for address, replay in original.items():
        offset = 8 if address in (0x96a, 0xb0e) else 6
        for ccr in range(32):
            for value in values:
                for volume_mode in ((0x40, 0x3f) if offset == 8 else (0x40,)):
                    channel = (ccr+value) & 1
                    skip = address in (0x84a, 0xd5c) and value == 65
                    initial = [rng.getrandbits(32) for _ in range(15)]
                    results = []
                    for oracle, ns in ((True, reference), (False, actual)):
                        cpu, r = ns['cpu'], ns['r']
                        regs = [getattr(r, 'UC_M68K_REG_D'+str(i)) for i in range(8)]
                        regs += [getattr(r, 'UC_M68K_REG_A'+str(i)) for i in range(7)]
                        for reg, setting in zip(regs, initial): cpu.reg_write(reg, setting)
                        cpu.reg_write(r.UC_M68K_REG_D0, 0x89ab0000 | value)
                        cpu.reg_write(r.UC_M68K_REG_D1, 0x12340000 | volume_mode)
                        cpu.reg_write(r.UC_M68K_REG_A1, 0x60f000)
                        cpu.reg_write(r.UC_M68K_REG_A4, ns['bank']+16*channel)
                        cpu.reg_write(r.UC_M68K_REG_A5, 0x606000)
                        cpu.reg_write(r.UC_M68K_REG_A6, 0x607000)
                        ns['put'](0x6060c0, int(skip), 2)
                        ns['put'](0x6060a0, value, 2)
                        ns['put'](0x60702a, value, 2)
                        ns['put'](0x50f000, 0x60f000, 4)
                        cpu.reg_write(r.UC_M68K_REG_SR, 0x2000 | ccr)
                        cpu.reg_write(r.UC_M68K_REG_A7, 0x50f000)
                        if oracle:
                            entry = 0x500400
                            raw = bytes.fromhex(replay)
                            end = entry+len(raw)
                            cpu.mem_write(entry, raw)
                        else:
                            name = '_nv_native_write_%x' % address
                            entry = ns['sym'](name)
                            end = 0x60f000 if address == 0xd5c else ns['sym']('_nv_continue_'+name)
                        # Materialize Unicorn's lazy NZ flags in a test-only
                        # supervisor stub; production uses no privileged read.
                        cpu.mem_write(end, bytes.fromhex('40f900608000'))
                        if oracle: cpu.ctl_remove_cache(entry, end+6)
                        try: cpu.emu_start(entry, end+6, count=100000)
                        except Exception:
                            print(model, hex(address), ccr, value, volume_mode, oracle,
                                  hex(cpu.reg_read(r.UC_M68K_REG_PC)))
                            raise
                        assert cpu.reg_read(r.UC_M68K_REG_PC) == end+6
                        result = ([cpu.reg_read(reg) for reg in regs],
                                  ns['get'](0x608000, 2) & 31,
                                  cpu.reg_read(r.UC_M68K_REG_A7))
                        if oracle and not skip:
                            ns['call']('_nv_driver_write', ns['bank']+16*channel, offset)
                        results.append((result, bytes(cpu.mem_read(ns['bank'], 64)),
                                        dict(ns['hardware']), bytes(cpu.mem_read(0xdff0a0, 64)),
                                        bytes(cpu.mem_read(ns['driver'], ns['layout']['size']))))
                    assert results[0] == results[1], (model, hex(address), ccr, value, volume_mode)
                    cases += 1

report = dict(pass_=True, cases=cases, CPU_models=['M68000', 'M68020'],
              all32_CCR_states=True, ownership_modes=['MIX','NATIVE'], word_boundaries=values,
              both_virtual_channels=True, conditional_skip=True,
              volume_math_and_override=True,
              registers_stack_mirrors_hardware_live_state_equal=True,
              scope='Original instruction replay plus same-module real C callback; complete generated adapters')
(actual['BUILD']/'word-wrapper-validation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps(report))
