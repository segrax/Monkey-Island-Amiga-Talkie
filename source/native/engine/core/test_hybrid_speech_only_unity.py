"""Check unity speech halving against independent signed arithmetic."""
from pathlib import Path
import json
import random

HERE = Path(__file__).resolve().parent
source = HERE / 'test_driver.py'
prefix = source.read_text().split("call('_nv_driver_start')", 1)[0]
exec(compile(prefix, str(source), 'exec'))

# Shared linked/raw fixture tests begin here.
for address in (0xa00000, 0xb00000, 0xc00000):
    cpu.mem_map(address, 0x30000)
cpu.mem_map(0xd00000, 4096)
table = 0xd00000
unity_row = bytes(((value if value < 128 else value - 256) // 2) & 255
                  for value in range(256))
cpu.mem_write(table, unity_row)
saved_registers = [r.UC_M68K_REG_D2, r.UC_M68K_REG_D3, r.UC_M68K_REG_D4,
                   r.UC_M68K_REG_D5, r.UC_M68K_REG_D6, r.UC_M68K_REG_D7,
                   r.UC_M68K_REG_A2, r.UC_M68K_REG_A3, r.UC_M68K_REG_A4,
                   r.UC_M68K_REG_A5, r.UC_M68K_REG_A6]
rng = random.Random(0x554e4954)
code_read_ranges = [(bases[h['hunk_no']], bases[h['hunk_no']] + len(h['data']))
                    for h in reader.hunks if h['type_name'] == 'HUNK_CODE']
limits = {}; accesses = {}; steps = [0]

def read_bounds(uc, access, address, size, value, unused):
    if 0x50e000 <= address and address + size <= 0x50f100:
        return
    if table <= address and address + size <= table + 256:
        accesses['table'] += size
        return
    if any(begin <= address and address + size <= end for begin, end in code_read_ranges):
        return  # The legacy byte loop reads its PC-relative entry table.
    begin, end = limits['source']
    assert begin <= address and address + size <= end, ('read', address, size, limits)
    assert size == 1 or not (address & 1), ('unaligned read', address, size)
    accesses['source'] += size


def write_bounds(uc, access, address, size, value, unused):
    if 0x50e000 <= address and address + size <= 0x50f100:
        return
    assert any(begin <= address and address + size <= end
               for begin, end in (limits['left'], limits['right'])), ('write', address, size, limits)
    assert size == 1 or not (address & 1), ('unaligned write', address, size)
    accesses['output'] += size


def count_instruction(uc, pc, size, unused):
    steps[0] += 1

cpu.hook_add(unicorn.UC_HOOK_MEM_READ, read_bounds)
cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE, write_bounds)
cpu.hook_add(unicorn.UC_HOOK_CODE, count_instruction)
cases = 0
costs = {}

def check(count, alignment, payload=None, both=False):
    global cases
    left = 0xb00008 + alignment[0]
    right = 0xc00008 + alignment[1]
    source_at = 0xa00008 + alignment[2]
    payload = rng.randbytes(count) if payload is None else payload
    assert len(payload) == count
    expected = bytes(((x if x < 128 else x - 256) // 2) & 255 for x in payload)
    cpu.mem_write(source_at - 4, b'\xa5' * 4 + payload + b'\xa5' * 4)
    limits.update(source=(source_at, source_at + count), left=(left, left + count),
                  right=(right, right + count))
    names = ('_nv_hybrid_speech_only', '_nv_hybrid_speech_only_unity') if both else ('_nv_hybrid_speech_only_unity',)
    for name in names:
        for address in (left, right):
            cpu.mem_write(address - 4, b'\xa5' * (count + 8))
        saved = {reg: rng.getrandbits(32) for reg in saved_registers}
        for reg, value in saved.items():
            cpu.reg_write(reg, value)
        cpu.reg_write(r.UC_M68K_REG_SR, rng.randrange(32))
        accesses.update(source=0, table=0, output=0); steps[0] = 0
        call(name, left, right, source_at, table, count)
        assert cpu.reg_read(r.UC_M68K_REG_A7) == 0x50f004
        assert all(cpu.reg_read(reg) == value for reg, value in saved.items())
        assert accesses['source'] == count and accesses['output'] == 2 * count, accesses
        assert bytes(cpu.mem_read(source_at - 4, count + 8)) == b'\xa5' * 4 + payload + b'\xa5' * 4
        for address in (left, right):
            assert bytes(cpu.mem_read(address - 4, count + 8)) == b'\xa5' * 4 + expected + b'\xa5' * 4
        if both:
            costs.setdefault(str(count) + '/' + str(alignment), {})[name] = steps[0]
        cases += 1

counts = list(range(41)) + [63,64,65,127,128,129,255,256,257,511,512,513,1023,1024,4095,65535,65536]
for count in counts:
    for bits in range(8):
        alignment = (bits & 1, (bits >> 1) & 1, (bits >> 2) & 1)
        payload = bytes(range(256)) if count == 256 else None
        check(count, alignment, payload, both=bits in (0,1) and count <= 1024)
for alignment in ((2,0,0), (0,2,0), (0,0,2), (2,2,2)):
    check(256, alignment, bytes(range(256)), both=True)
for value in range(256):
    check(16, (0,0,0), bytes([value]) * 16)
for unused in range(128):
    count = rng.randrange(1025)
    check(count, tuple(rng.randrange(4) for unused in range(3)))
# Exercise the original entry with the real unity/clamped row pointer as well.
synthetic_table = table
table = sym('_nv_half_amplitude') + 64 * 256
assert bytes(cpu.mem_read(table, 256)) == unity_row
for count in (0,1,15,16,17,31,32,33,255,256,257):
    for bits in range(8):
        alignment = (bits & 1, (bits >> 1) & 1, (bits >> 2) & 1)
        check(count, alignment, both=True)
table = synthetic_table

# Zero count must not dereference any supplied pointer.
for pointer in (0,1,0xffffffff):
    limits.update(source=(pointer,pointer), left=(pointer,pointer), right=(pointer,pointer))
    accesses.update(source=0,table=0,output=0)
    call('_nv_hybrid_speech_only_unity', pointer,pointer,pointer,pointer,0)
    assert accesses == dict(source=0,table=0,output=0)
    cases += 1
report = dict(pass_=True, cases=cases, all_256_signed_values=True,
              all_pointer_parities=True, original_entry_real_unity_table=True, word_aligned_not_long_aligned=True,
              counts_0_through_40=True, maximum_65536_count=True,
              random_pcm_tails_and_parities=True, exact_source_and_output_bounds=True,
              source_immutable=True, callee_registers_and_stack_preserved=True,
              zero_count_no_pointer_dereferences=True, instruction_counts=costs,
              scope='Compiled 68000 helper and independent signed integer oracle; instructions are not CPU cycles')
(BUILD / 'hybrid-speech-only-unity.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps({key:value for key,value in report.items() if key != 'instruction_counts'}))
