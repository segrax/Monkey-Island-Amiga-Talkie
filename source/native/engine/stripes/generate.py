"""Clone the original stripe decoder, relaxing only internal branch encodings."""
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
r = HunkReader()
assert r.read_file(str(original)) == 0 and r.build_segments()
code = next(h['data'] for h in r.hunks if h.get('hunk_no') == 0 and 'data' in h)
cs = capstone.Cs(capstone.CS_ARCH_M68K, capstone.CS_MODE_BIG_ENDIAN | capstone.CS_MODE_M68K_000)
cs.detail = True
instructions = list(cs.disasm(code[START:END], START))
assert instructions[-1].address == END - 2
out = [' section text,code', ' xdef _stripe', '_stripe:']
branches = []
for ins in instructions:
    out.append(f'L{ins.address:x}:')
    op = ins.operands[-1] if ins.operands else None
    if op is not None and op.type == M.M68K_OP_BR_DISP:
        target = ins.address + 2 + op.br_disp.disp
        assert START <= target < END
        name = ins.mnemonic.split('.')[0]
        args = ('d' + str(ins.operands[0].reg - M.M68K_REG_D0) + ',' if name.startswith('db') else '') + f'L{target:x}'
        out.append(' ' + name + ' ' + args)
        branches.append(dict(old=ins.address, target=target, size=ins.size))
    else:
        out.append(' dc.w ' + ','.join('$' + ins.bytes[i:i+2].hex() for i in range(0, ins.size, 2)))
(BUILD / 'stripe.s').write_text('\n'.join(out) + '\n')
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe', '-quiet', '-m68000', '-Fhunk', '-o', str(BUILD / 'stripe.o'), str(BUILD / 'stripe.s')], check=True)
o = HunkReader()
assert o.read_file(str(BUILD / 'stripe.o')) == 0
kernel = next(h['data'] for h in o.hunks if h['type_name'] == 'HUNK_CODE')
(BUILD / 'stripe.bin').write_bytes(kernel)
new = list(cs.disasm(kernel, 0))
assert len(new) == len(instructions)
mapping = {a.address: b.address for a, b in zip(instructions, new)}
relocations = []
for a, b in zip(instructions, new):
    op = a.operands[-1] if a.operands else None
    if op is not None and op.type == M.M68K_OP_BR_DISP:
        assert b.mnemonic.split('.')[0] == a.mnemonic.split('.')[0]
        assert b.address + 2 + b.operands[-1].br_disp.disp == mapping[a.address + 2 + op.br_disp.disp]
    else:
        assert a.bytes == b.bytes
        if any(p.address_mode == M.M68K_AM_ABSOLUTE_DATA_LONG for p in a.operands):
            relocations.append(b.address + b.size - 4)
inbound = []
for ins in cs.disasm(code, 0):
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
for h in r.hunks:
    section=h.get('hunk_no',section)
    if h['type_name']=='HUNK_ABSRELOC32':
        for off in h['reloc'].get(0,[]):
            value=int.from_bytes(data_by_hunk[section][off:off+4],'big')
            assert not START < value < START+10,(section,off,value)
            if value==START:absolute_entry_references.append(dict(hunk=section,offset=off))
report = dict(source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(), kernel_sha256=hashlib.sha256(kernel).hexdigest(), original_bytes=END-START, kernel_bytes=len(kernel), instruction_count=len(new), mapping=mapping, absolute_h2_relocations=relocations, branches=[dict(old=a.address,new=b.address,old_size=a.size,new_size=b.size) for a,b in zip(instructions,new) if a.size!=b.size], footprint=dict(address=START,size=10,expected=code[START:START+10].hex()), no_external_interior_inbound=True, all_nonbranch_instruction_bytes_identical=True, runtime_validated=False)
report['absolute_entry_references']=absolute_entry_references
report['all_hunk_relocated_absolute_targets_no_interior_entry']=True
(BUILD / 'generation.json').write_text(json.dumps(report, indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('mapping','branches')},indent=2))
