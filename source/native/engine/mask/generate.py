from pathlib import Path
import hashlib,json,subprocess,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
P=artifact_dir('mask');HERE=Path(__file__).resolve().parent
original=PROJECT_ROOT/'data/original/Monkey_Island'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
r=HunkReader();assert r.read_file(str(original))==0 and r.build_segments()
c=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)
functions=[dict(name='_engine_mask_rle',start=0x4de2,end=0x4de8)]
assert c[0x4de2:0x4de8].hex()=='4ef900015338'
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
(P/'mask.s').write_text((HERE/'kernel.s').read_text())
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(P/'mask.o'),str(P/'mask.s')],check=True)
o=HunkReader();assert o.read_file(str(P/'mask.o'))==0
assert not any(h.get('reloc')or h.get('ext_ref')for h in o.hunks)
blob=next(h['data']for h in o.hunks if h['type_name']=='HUNK_CODE')
entries={e['name']:e['def']for h in o.hunks if h['type_name']=='HUNK_EXT'for e in h['ext_def']}
assert entries['_engine_mask_rle']==0 and entries['_engine_mask_rle_end']<=len(blob)
blob=blob[:entries['_engine_mask_rle_end']]
relocs=[]
cs.detail=True
for i in cs.disasm(blob,0):
 for op in i.operands:
  if op.type==M.M68K_OP_MEM and op.address_mode==M.M68K_AM_ABSOLUTE_DATA_LONG:
   assert op.imm in(0x5c22,0x5c38,0x5c2e)
   pos=i.bytes.find(op.imm.to_bytes(4,'big'));assert pos>=0;relocs.append(i.address+pos)
assert relocs==[6,22,28]
(P/'mask.bin').write_bytes(blob)
for f in functions:f['expected']=c[f['start']:f['end']].hex()
metadata=dict(functions=functions,entries=entries,code_bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),global_relocations=relocs,original_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),retained_original_entry=0x15338,repeat_threshold=8,unroll_bytes=8,byte_access_order_preserved=True,inbound_branches_and_code_pointers_checked=True)
(P/'generation.json').write_text(json.dumps(metadata,indent=2)+'\n');print('Generated exact mask decoder:',len(blob),'bytes')
