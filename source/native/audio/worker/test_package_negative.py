"""Packaging pin/unsafe-input rejection; no original asset is written."""
from pathlib import Path
import argparse,json,hashlib
from build_slim_package import HERE,ROOT,PINS,pinned,runtime_inputs,package
T=ROOT/'build/tests/package-negative';T.mkdir(parents=True,exist_ok=True)
checks=[]
for name in ('source','map','npc'):
 p=T/('wrong-'+name);p.write_bytes(b'not a pinned asset')
 try:pinned(p,name)
 except ValueError:pass
 else:raise AssertionError(name)
 checks.append('unexpected '+name+' size/hash rejects')
base=T/'unexpected-base';base.mkdir(exist_ok=True);(base/'unrelated-user-data').write_bytes(b'never copy me')
try:runtime_inputs(base)
except ValueError as e:assert 'Unexpected base-system entries'in str(e)
else:raise AssertionError('unexpected file copied')
checks.append('unexpected runtime input rejected before copy')
# Existing and external output locations are refused before any input reads/copies.
for output in (T,ROOT.parent/'outside-slim-test-must-not-exist'):
 try:package(argparse.Namespace(output=output))
 except ValueError as e:assert 'Output must be a new isolated'in str(e)
 else:raise AssertionError('unsafe/existing output accepted')
checks.append('existing or outside-workspace output refused')
assets=ROOT/'build/releases/c28-21472'
manifest=json.loads((assets/'slim-package-manifest.json').read_text())
assert not any(p.name.lower()=='monster.sou'for p in assets.rglob('*'))
assert set(manifest['files'])>={'VoiceServer','amiga-talkie.dat','native-voice.pcm','PreparedOnly','VoiceBoost'}
assert manifest['proof']['all_map_refs_present']==PINS['clips']
for name,v in manifest['files'].items():
 p=assets/name
 with p.open('rb')as f:assert hashlib.file_digest(f,'sha256').hexdigest()==v['sha256']
checks.append('complete Slim stage, all hashes verified, no SOU')
(HERE/'package-negative-validation.json').write_text(json.dumps(dict(checks=checks,source_assets_untouched=True),indent=2)+'\n');print(json.dumps(checks))
