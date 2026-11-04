"""Clone the stripe decoder and batch extended runs with ordered byte writes."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib, json, struct, subprocess, sys
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / 'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
START, END = 0x15190, 0x15338
original = ROOT / 'data/original/Monkey_Island'
assert hashlib.sha256(original.read_bytes()).hexdigest() == '1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
r = HunkReader()
assert r.read_file(str(original)) == 0 and r.build_segments()
code = next(h['data'] for h in r.hunks if h.get('hunk_no') == 0 and 'data' in h)
cs = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
cs.detail = True
instructions = list(cs.disasm(code[START:END], START))
assert instructions[-1].address == END - 2
out = [' section text,code', ' xdef _stripe', '_stripe:']
branches = []
redirect = {0x151e8:0x15254,0x151ee:0x15282,0x151f2:0x15232,
            0x1522a:0x15232,0x1524c:0x15254,0x15278:0x15282}
expected = {0x151e8:'6700006a',0x151ee:'67000092',0x151f2:'6000003e',
            0x1522a:'60000006',0x1524c:'60000006',0x15278:'60000008'}
for address, value in expected.items():
    assert code[address:address+4].hex() == value
for ins in instructions:
    out.append(f'L{ins.address:x}:')
    op = ins.operands[-1] if ins.operands else None
    if op is not None and op.type == M.M68K_OP_BR_DISP:
        target = ins.address + 2 + op.br_disp.disp
        assert START <= target < END
        name = ins.mnemonic.split('.')[0]
        label = f'B{redirect[ins.address]:x}' if ins.address in redirect else f'L{target:x}'
        args = ('d' + str(ins.operands[0].reg - M.M68K_REG_D0) + ',' if name.startswith('db') else '') + label
        out.append(' ' + name + ' ' + args)
        branches.append(dict(old=ins.address, target=target, size=ins.size))
    else:
        out.append(' dc.w ' + ','.join('$' + ins.bytes[i:i+2].hex() for i in range(0, ins.size, 2)))
# Inline short packets keep their original loops. Only extended packets and
# cross-column resumes enter these gates after the original RTS.
batches = {
    0x15232:(0x1522e,[' move.b d4,(a2)+',' move.b d4,(a4)',' adda.w d7,a4',' exg d4,d5']),
    0x15254:(0x15250,[' move.b (a2)+,(a4)',' adda.w d7,a4']),
    0x15282:(0x1527c,[' move.b d4,(a2)+',' move.b d4,(a4)',' adda.w d7,a4'])}
# D2=N-1 leaves low-byte D3=remaining-N+1 for the original predecrement.
for address, (resume, emit) in batches.items():
    label, old = f'B{address:x}', f'L{address:x}'
    out += [label+':',' cmpi.w #7,d1',' blo '+old,' tst.b d3',
            ' beq '+label+'_batch',' cmpi.b #8,d3',' blo '+old,
            label+'_batch:',' moveq #0,d2',' move.b d3,d2',' subq.b #1,d2',
            ' cmp.w d1,d2',' bls '+label+'_count',' move.w d1,d2',
            label+'_count:',' sub.b d2,d3',' sub.w d2,d1',' subq.w #1,d1',
            ' cmpi.w #7,d2',' blo '+label+'_tail',label+'_eight:']
    out += emit * 8
    out += [' subq.w #8,d2',' cmpi.w #7,d2',' bge '+label+'_eight',
            label+'_tail:',' tst.w d2',' bmi '+label+'_done',label+'_one:']
    out += emit
    out += [' dbra d2,'+label+'_one',label+'_done:',' tst.w d1',
            ' bmi L1528c',f' bra L{resume:x}']
(BUILD / 'stripe.s').write_text('\n'.join(out) + '\n')
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe', '-quiet', '-m68000', '-Fhunk', '-o', str(BUILD / 'stripe.o'), str(BUILD / 'stripe.s')], check=True)
o = HunkReader()
assert o.read_file(str(BUILD / 'stripe.o')) == 0
kernel = next(h['data'] for h in o.hunks if h['type_name'] == 'HUNK_CODE')
(BUILD / 'stripe.bin').write_bytes(kernel)
new = list(cs.disasm(kernel, 0))
assert len(new) > len(instructions)
prefix = new[:len(instructions)]
assert prefix[-1].mnemonic == 'rts'
prefix_end = prefix[-1].address + prefix[-1].size
mapping = {a.address: b.address for a, b in zip(instructions, prefix)}
relocations = []
batch_targets = {}
for a, b in zip(instructions, prefix):
    op = a.operands[-1] if a.operands else None
    if op is not None and op.type == M.M68K_OP_BR_DISP:
        assert b.mnemonic.split('.')[0] == a.mnemonic.split('.')[0]
        target = b.address + 2 + b.operands[-1].br_disp.disp
        if a.address in redirect:
            assert prefix_end <= target < len(kernel)
            batch_targets.setdefault(redirect[a.address], set()).add(target)
        else:
            assert target == mapping[a.address + 2 + op.br_disp.disp]
    else:
        assert a.bytes == b.bytes
        if any(p.address_mode == M.M68K_AM_ABSOLUTE_DATA_LONG for p in a.operands):
            relocations.append(b.address + b.size - 4)
assert set(batch_targets) == set(batches) and all(len(v)==1 for v in batch_targets.values())
assert len({next(iter(v)) for v in batch_targets.values()}) == 3
inbound = []
cs.skipdata = True
for ins in cs.disasm(code, 0):
    if not ins.id: continue
    for op in ins.operands:
        if op.type == M.M68K_OP_BR_DISP:
            target = ins.address + 2 + op.br_disp.disp
            if START < target < START + 10 and not START <= ins.address < END:
                inbound.append(dict(site=ins.address, target=target))
        elif ins.mnemonic in ('jmp','jsr') and op.address_mode == M.M68K_AM_ABSOLUTE_DATA_LONG:
            if START < op.imm < START + 10:
                inbound.append(dict(site=ins.address, target=op.imm))
assert not inbound
section=0
data_by_hunk={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h}
absolute_entry_references=[]
original_relocations=set()
for h in r.hunks:
    section=h.get('hunk_no',section)
    if h['type_name']=='HUNK_ABSRELOC32':
        if section==0:
            for target, offsets in h['reloc'].items():
                for off in offsets:
                    if START<=off<END:
                        assert target==2
                        original_relocations.add(off)
        for off in h['reloc'].get(0,[]):
            value=int.from_bytes(data_by_hunk[section][off:off+4],'big')
            assert not START < value < START+10,(section,off,value)
            if value==START:absolute_entry_references.append(dict(hunk=section,offset=off))
expected_relocations={mapping[a.address]+a.size-4 for a in instructions if a.address+a.size-4 in original_relocations}
assert set(relocations)==expected_relocations
assert code[0x4ddc:0x4de2].hex()=='4ef900015190'
report = dict(source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(), kernel_sha256=hashlib.sha256(kernel).hexdigest(), original_bytes=END-START, kernel_bytes=len(kernel), instruction_count=len(new), mapping=mapping, absolute_h2_relocations=relocations, branches=[dict(old=a.address,new=b.address,old_size=a.size,new_size=b.size) for a,b in zip(instructions,new) if a.size!=b.size], footprint=dict(address=START,size=10,expected=code[START:START+10].hex()), no_external_interior_inbound=True, all_nonbranch_instruction_bytes_identical=True,original_prefix_nonbranch_instructions_exact=True,original_global_relocations_exact=True,existing_jump=dict(address=0x4ddc,size=6,expected='4ef900015190'), extended_run_batching=True, batch_minimum_pixels=8, prefix_bytes=prefix_end, appended_batch_bytes=len(kernel)-prefix_end, redirected_branches=[dict(old=a,expected=expected[a],batch_original_entry=redirect[a],new_target=next(iter(batch_targets[redirect[a]]))) for a in redirect], runtime_validated=False)
report['absolute_entry_references']=absolute_entry_references
report['all_hunk_relocated_absolute_targets_no_interior_entry']=True
(BUILD / 'generation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('mapping','branches')},indent=2))
