"""Production HUNK preservation and entry-footprint checks."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M

def read(path):
 r=HunkReader();assert r.read_file(str(path))==0 and r.build_segments();data={h['hunk_no']:h['data']for h in r.hunks if'data'in h};rel={};current=0
 for h in r.hunks:
  current=h.get('hunk_no',current)
  if h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():rel.setdefault(current,{}).setdefault(target,set()).update(offsets)
 return r,data,rel
rebase=json.loads((BUILD / 'rebase-input.json').read_text())
old,od,oreloc=read(Path(rebase['source_image']));new,nd,nreloc=read(BUILD / 'Monkey_Talkie_Scaled')
meta=json.loads((BUILD / 'Monkey_Talkie_Scaled.json').read_text());assert new.hunks[0]['hunks'][:7]==old.hunks[0]['hunks']
restored=bytearray(nd[0])
for h in meta['hooks']:restored[h['address']:h['address']+10]=od[0][h['address']:h['address']+10]
assert bytes(restored)==od[0]
for n in range(1,7):
 if n in od:assert od[n]==nd[n]
expected={s:{t:set(o)for t,o in groups.items()}for s,groups in oreloc.items()}
for off in meta['removed_original_relocations']:expected[0][2].remove(off)
expected[0].setdefault(7,set()).update(h['address']+2 for h in meta['hooks'])
for s,groups in expected.items():assert groups==nreloc[s],s
assert new.hunks[0]['hunks'][8]['memf']=='' and nreloc[8]=={8:set(json.loads((BUILD / 'generation.json').read_text())['prefix_pointer_offsets'])}
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
ins=list(cs.disasm(nd[7],0));starts={i.address for i in ins};assert sum(i.size for i in ins)==len(nd[7])
for i in ins:
 for o in i.operands:
  if o.type==M.M68K_OP_BR_DISP:assert i.address+2+o.br_disp.disp in starts
# Full original linear sweep supplements independently reviewed entry prologues.
for i in cs.disasm(od[0],0):
 for o in i.operands:
  if o.type==M.M68K_OP_BR_DISP:
   target=i.address+2+o.br_disp.disp
   assert not any(h['address']<target<h['address']+10 for h in meta['hooks']),(hex(i.address),hex(target))
for off in oreloc[0].get(0,[]):
 target=int.from_bytes(od[0][off:off+4],'big');assert not any(h['address']<target<h['address']+10 for h in meta['hooks'])
base_manifest=json.loads(Path(rebase['source_manifest']).read_text());combined_manifest=json.loads((BUILD / 'module.json').read_text())
assert combined_manifest['patches']==base_manifest['patches']
assert combined_manifest['driver_layout']==base_manifest['driver_layout']
assert all(combined_manifest['exports'][name]==value for name,value in base_manifest['exports'].items())
report=dict(source_core_sha256=base_manifest['sha256'],preserved_native_patch_count=len(base_manifest['patches']),all_source_exports_and_driver_layout_identical=True,production_sha256=meta['sha256'],all_previous7_hunk_sizes_flags_unchanged=True,all_previous_data_unchanged_except_two_10byte_detours=True,all_previous_relocations_preserved_except_two_overwritten_H2operands=True,removed_H2_offsets=meta['removed_original_relocations'],no_explicit_interior_inbound_targets=True,new_internal_branches_valid=True,prefix_memf_any=True,prefix_pointer_relocations=len(nreloc[8][8]))
(BUILD / 'static-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
