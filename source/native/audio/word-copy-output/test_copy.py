"""Check the actual 68000 copy helper at both alignments and all short tails."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools/python'))
import unicorn
from unicorn import m68k_const as r

subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe', '-quiet', '-m68000',
                '-Fbin', '-o', str(HERE / 'copy_output.bin'),
                str(HERE / 'copy_output.s')], check=True)
code = (HERE / 'copy_output.bin').read_bytes()
cpu = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
cpu.ctl_set_cpu_model(r.UC_CPU_M68K_M68000)
cpu.mem_map(0x100000, 0x1000)
cpu.mem_map(0x200000, 0x40000)
cpu.mem_map(0x300000, 0x1000)
cpu.mem_write(0x100000, code)
cpu.reg_write(r.UC_M68K_REG_SR, 0)
preserved = [getattr(r, 'UC_M68K_REG_D' + str(i)) for i in range(2, 8)]
preserved += [getattr(r, 'UC_M68K_REG_A' + str(i)) for i in range(2, 7)]
checks = 0
instructions = 0

def tick(*args):
    global instructions
    instructions += 1

cpu.hook_add(unicorn.UC_HOOK_CODE, tick)
profile = {}
for source_alignment in (0, 1):
    for destination_alignment in (0, 1):
        for count in list(range(513)) + [8191, 8192, 16383, 16384, 65535]:
            src = 0x200100 + source_alignment
            dst = 0x220100 + destination_alignment
            payload = bytes((i * 73 + 29) & 255 for i in range(count))
            cpu.mem_write(src - 8, b'\xa6' * 8 + payload + b'\xa6' * 8)
            cpu.mem_write(dst - 8, b'\xa5' * (count + 16))
            cpu.mem_write(0x300800, (0x100800).to_bytes(4, 'big'))
            # The C ABI places the word count in the low half of a long slot.
            cpu.mem_write(0x300804, dst.to_bytes(4, 'big') +
                          src.to_bytes(4, 'big') + count.to_bytes(4, 'big'))
            for i, reg in enumerate(preserved):
                cpu.reg_write(reg, 0x15263748 + i)
            cpu.reg_write(r.UC_M68K_REG_A7, 0x300800)
            instructions = 0
            cpu.emu_start(0x100000, 0x100800, count=200000)
            assert cpu.reg_read(r.UC_M68K_REG_PC) == 0x100800
            assert cpu.reg_read(r.UC_M68K_REG_A7) == 0x300804
            assert bytes(cpu.mem_read(dst - 8, count + 16)) == b'\xa5' * 8 + payload + b'\xa5' * 8
            assert bytes(cpu.mem_read(src - 8, count + 16)) == b'\xa6' * 8 + payload + b'\xa6' * 8
            assert all(cpu.reg_read(reg) == 0x15263748 + i for i, reg in enumerate(preserved))
            if count == 256:
                profile[f'{source_alignment}:{destination_alignment}'] = instructions
            checks += 1
report = dict(checks=checks, source_and_destination_alignments=[0, 1],
              lengths='0..512,8191,8192,16383,16384,65535',
              exact_bytes_canaries_callee_registers_stack=True,
              instructions_for_256_bytes=profile,
              binary_sha256=hashlib.sha256(code).hexdigest())
(HERE / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
