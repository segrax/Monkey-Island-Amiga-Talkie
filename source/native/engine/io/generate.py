from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
HERE=Path(__file__).resolve().parent
BUILD=artifact_dir('io')
import hashlib,json,struct,subprocess,sys
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
P=BUILD
W=lambda *v:struct.pack('>'+len(v)*'I',*v)
def read(path):
 r=HunkReader();assert r.read_file(str(path))==0 and r.build_segments();return r
assert hashlib.sha256((PROJECT_ROOT/'data/original/Monkey_Island').read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
original=read(PROJECT_ROOT/'data/original/Monkey_Island')
c=next(h['data'] for h in original.hunks if h.get('hunk_no')==0 and 'data' in h)
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
lines=[(HERE/'read_buffered.s').read_text().replace('jsr _fread_original','bsr _fread_original')]
for ins in cs.disasm(c[0x16d80:0x16dee],0x16d80):
 lines.append(f'L{ins.address:x}:')
 op=ins.operands[-1] if ins.operands else None
 if op and op.type==M.M68K_OP_BR_DISP:
  target=ins.address+2+op.br_disp.disp;assert 0x16d80<=target<0x16dee
  lines.append(' '+ins.mnemonic.split('.')[0]+f' L{target:x}')
 elif ins.mnemonic=='jsr':
  assert ins.address==0x16dc6
  lines.append(' jsr $163b8.l')
 else:lines.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2)))
lines.append((HERE/'decode_resource.s').read_text())
(P/'fast.s').write_text('\n'.join(lines)+'\n')
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(P/'fast.o'),str(P/'fast.s')],check=True)
r=HunkReader();assert r.read_file(str(P/'fast.o'))==0
blob=next(h['data'] for h in r.hunks if h['type_name']=='HUNK_CODE')
assert not any(h['type_name']=='HUNK_ABSRELOC32' for h in r.hunks)
entries={e['name']:e['def'] for h in r.hunks if h['type_name']=='HUNK_EXT' for e in h['ext_def']}
relocs=[]
for ins in cs.disasm(blob,0):
 if ins.mnemonic=='jsr':
  assert ins.operands[0].imm==0x163b8
  relocs.append(ins.address+2)
assert len(relocs)==1
(P/'fast.bin').write_bytes(blob)
(P/'kernel.json').write_text(json.dumps(dict(entries=entries,original_code_relocations=relocs,code_bytes=len(blob),original_body_sha256=hashlib.sha256(c[0x16d80:0x16dee]).hexdigest(),original_decode_sha256=hashlib.sha256(c[0x126ac:0x126c0]).hexdigest()),indent=2)+'\n')
print(entries,len(blob),relocs)
