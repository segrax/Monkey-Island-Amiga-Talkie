"""Patch only a generated module's original restorer; retain every relocation."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
build=artifact_dir('restoration');module=engine_build()/'module';path=module/'Monkey_Talkie_Test'
raw=path.read_bytes();manifest=json.loads((module/'module.json').read_text());assert hashlib.sha256(raw).hexdigest()==manifest['sha256']
generation=json.loads((build/'generation.json').read_text());start,end=generation['start'],generation['end']
r=HunkReader();assert r.read_file(str(path))==0 and r.build_segments()
hunk=next(h for h in r.hunks if h.get('hunk_no')==0 and h['type_name']=='HUNK_CODE')
o=HunkReader();assert o.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and o.build_segments()
original=next(h['data'] for h in o.hunks if h.get('hunk_no')==0 and 'data' in h)
assert hunk['data'][start:end]==original[start:end]
kernel=(build/'restore.bin').read_bytes();assert hashlib.sha256(kernel).hexdigest()==generation['kernel_sha256']
replacement=kernel+bytes.fromhex('4e71')*((end-start-len(kernel))//2);assert len(replacement)==end-start
offset=hunk['hunk_file_offset']+8+start;assert raw[offset:offset+end-start]==original[start:end]
patched=raw[:offset]+replacement+raw[offset+end-start:];assert len(patched)==len(raw)
temporary=path.with_suffix('.restore-new');temporary.write_bytes(patched)
q=HunkReader();assert q.read_file(str(temporary))==0 and q.build_segments()
assert [h for h in r.hunks if h['type_name']=='HUNK_ABSRELOC32']==[h for h in q.hunks if h['type_name']=='HUNK_ABSRELOC32']
new_code=next(h['data'] for h in q.hunks if h.get('hunk_no')==0 and 'data' in h)
assert new_code[:start]==hunk['data'][:start] and new_code[end:]==hunk['data'][end:] and new_code[start:end]==replacement
temporary.replace(path)
manifest['engine_patches'].append(dict(address=start,size=end-start,expected=original[start:end].hex(),changed_bytes=sum(a!=b for a,b in zip(original[start:end],replacement))))
manifest['engine_restore_relax']=generation
manifest['sha256']=hashlib.sha256(patched).hexdigest();(module/'module.json').write_text(json.dumps(manifest,indent=2)+'\n')
(build/'patch.json').write_text(json.dumps(dict(sha256=manifest['sha256'],same_file_size=True,all_relocations_unchanged=True,only_restore_body_changed=True),indent=2)+'\n');print(manifest['sha256'])
