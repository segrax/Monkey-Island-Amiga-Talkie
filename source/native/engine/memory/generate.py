from pathlib import Path
import hashlib,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
P=artifact_dir('memory');HERE=Path(__file__).resolve().parent
original=PROJECT_ROOT/'data/original/Monkey_Island'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
r=HunkReader();assert r.read_file(str(original))==0 and r.build_segments()
c=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)
functions=[dict(name='_engine_fill',start=0x1476a,end=0x14772),dict(name='_engine_copy',start=0x14792,end=0x1479a)]
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True;cs.skipdata=True
for i in cs.disasm(c,0):
 if not i.id:continue
 for op in i.operands:
  if op.type==M.M68K_OP_BR_DISP:
   target=i.address+2+op.br_disp.disp
   for f in functions:assert not f['start']<target<f['end'],(i.address,target)
section=0;data={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h}
for h in r.hunks:
 section=h.get('hunk_no',section)
 if h['type_name']=='HUNK_ABSRELOC32':
  for off in h['reloc'].get(0,[]):
   for f in functions:assert not f['start']<int.from_bytes(data[section][off:off+4],'big')<f['end']
(P/'memory.s').write_text((HERE/'fill.s').read_text()+'\n'+(HERE/'copy.s').read_text())
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(P/'memory.o'),str(P/'memory.s')],check=True)
o=HunkReader();assert o.read_file(str(P/'memory.o'))==0
blob=next(h['data'] for h in o.hunks if h['type_name']=='HUNK_CODE')
assert not any(h['type_name']in('HUNK_RELOC32','HUNK_ABSRELOC32','HUNK_EXT') and h.get('reloc') for h in o.hunks)
(P/'memory.bin').write_bytes(blob)
entries={e['name']:e['def'] for h in o.hunks if h['type_name']=='HUNK_EXT' for e in h['ext_def']}
assert set(entries)=={f['name'] for f in functions} and entries['_engine_fill']==0
for f in functions:f['expected']=c[f['start']:f['end']].hex()
(P/'generation.json').write_text(json.dumps(dict(functions=functions,entries=entries,code_bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest()),indent=2)+'\n')
print('Generated exact memory primitives:',len(blob),'bytes')
