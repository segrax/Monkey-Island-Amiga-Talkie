"""Trace-difference MC68000 core-cycle estimate, excluding DMA/bus waits.

Only changed instruction counts are priced; unchanged work cancels. Unknown
changes reject the estimate. Timings: MC68000UM chapter 8, NXP original manual:
https://www.nxp.com/docs/en/reference-manual/MC68000UM.pdf
"""
from collections import Counter
import capstone


def histogram(cpu, trace):
    cs = capstone.Cs(capstone.CS_ARCH_M68K,
                     capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
    cache, result = {}, Counter()
    for pc, nextpc in zip(trace, trace[1:]):
        if pc not in cache:
            cache[pc] = next(cs.disasm(bytes(cpu.mem_read(pc, 10)), pc, count=1))
        ins = cache[pc]
        name = ins.mnemonic.split('.')[0]
        if name == 'dbra':
            key = ('dbra', 'taken' if nextpc != pc + ins.size else 'expired')
        elif name == 'bra':
            key = ('bra', '')
        elif name.startswith('b') and name != 'btst':
            key = ('bcc', 'taken' if nextpc != pc + ins.size else str(ins.size))
        else:
            key = (ins.mnemonic, ins.op_str)
        result[key] += 1
    return result


def cycles(key):
    name, operands = key
    if name == 'dbra': return 10 if operands == 'taken' else 14
    if name == 'bra': return 10
    if name == 'bcc': return 10 if operands == 'taken' else 8 if operands == '2' else 12
    if name in ('moveq', 'swap'): return 4
    if name in ('cmpi.w', 'cmpi.b', 'andi.w'): return 8
    if name in ('tst.b','tst.w') and operands.startswith('d'): return 4
    if name in ('subq.b','subq.w') and operands.split(',')[-1].strip().startswith('d'): return 4
    if name in ('sub.b','sub.w','cmp.w'):
        parts = [part.strip() for part in operands.split(',')]
        if len(parts)==2 and all(len(part)==2 and part[0]=='d' and part[1].isdigit() for part in parts): return 4
    if name == 'ror.w' and operands.startswith('#$1,'): return 8
    if name in ('btst.l', 'btst.b') and operands == '#$0, d1': return 10
    if name.startswith(('move.', 'movea.')):
        source = operands.split(',')[0]
        if source.startswith('#'): return 12 if name.endswith('.l') else 8
        if source.startswith('$'): return 20 if name.endswith('.l') else 16
        if source.startswith(('a', 'd')): return 4
    raise AssertionError(('Unpriced changed instruction', key))


def difference(old_cpu, old_trace, new_cpu, new_trace):
    before, after = histogram(old_cpu, old_trace), histogram(new_cpu, new_trace)
    changes = {key: after[key] - before[key] for key in before.keys() | after.keys()
               if after[key] != before[key]}
    return -sum(count * cycles(key) for key, count in changes.items())
