"""Use positive word-sized blitter strides without depending on caller upper bits."""
import sys,json,hashlib
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,engine_build,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
SITES={0x15c52:('dbc5','dac5'),0x15c54:('ddc5','dcc5'),0x15c56:('d3c5','d2c5'),0x15c58:('d5c5','d4c5'),0x15c6a:('d7c6','d6c6'),0x15c6c:('d9c6','d8c6')}
EXPECTED_BODY='4ba13c320f0bb221e7c6755d2968805586f46cc7831825516d40a8afb5bcf699'
folder=engine_build()/'module';image=folder/'Monkey_Talkie_Test';raw=image.read_bytes();meta=json.loads((folder/'module.json').read_text())
assert hashlib.sha256(raw).hexdigest()==meta['sha256'] and 'engine_blitter_strides' not in meta
r=HunkReader();assert r.read_file(str(image))==0 and r.build_segments()
h=next(h for h in r.hunks if h.get('hunk_no')==0 and 'data'in h);code=h['data'];assert hashlib.sha256(code[0x15b9c:0x15c84]).hexdigest()==EXPECTED_BODY
section=0
for record in r.hunks:
 section=record.get('hunk_no',section)
 if section==0 and record['type_name']=='HUNK_ABSRELOC32':
  assert not any(at<off+4 and off<at+2 for offsets in record['reloc'].values() for off in offsets for at in SITES)
result=bytearray(raw);allowed=set()
for at,(old,new) in SITES.items():
 assert code[at:at+2]==bytes.fromhex(old)
 off=h['data_file_offset']+at;result[off:off+2]=bytes.fromhex(new);allowed.update(range(off,off+2))
assert len(result)==len(raw) and all(i in allowed for i,(a,b) in enumerate(zip(raw,result)) if a!=b)
# Exact raw-byte footprint preserves all hunk boundaries, relocations and incoming references.
image.write_bytes(result);meta['sha256']=hashlib.sha256(result).hexdigest()
meta['engine_blitter_strides']=dict(body_sha256=EXPECTED_BODY,word_strides=[2,8000],sites={hex(k):dict(expected=v[0],replacement=v[1]) for k,v in SITES.items()},caller_registers_preserved=True)
(folder/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
(artifact_dir('blitter')/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],same_file_size=True,only_six_words_changed=True,relocations_and_all_other_bytes_preserved=True),indent=2)+'\n')
print('BLITTER STRIDES',meta['sha256'])
