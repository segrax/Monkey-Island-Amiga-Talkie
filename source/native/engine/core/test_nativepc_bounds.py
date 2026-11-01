"""Native retained-PC bounds fail closed without a per-opcode array."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
exec(compile((HERE/'test_provenance.py').read_text().split('result=dict(',1)[0],str(HERE/'test_provenance.py'),'exec'))
checks=0
for slot,base,nxt,current in ((20,0x600000,0x600041,0x600050),(255,0x600000,0x600041,0x600050),(6,0,0x600041,0x600050),(6,0x600000,0x600000,0x600050),(6,0x600000,0x5fffff,0x600050),(6,0x600000,0x600060,0x600050)):
 put(g+0x2024,slot,1);put(g+0x5a56,base,4);put(g+0x66fa,nxt,4);put(g+0x5a50,current,4)
 call('_nv_definition_begin')
 resource(168,0x600800,b'Invalid definition.\0')
 # Restore a valid dialogue identity; captured resource validity remains invalid.
 put(g+0x2024,6,1);put(g+0x5a56,0x600000,4);put(g+0x5a50,0x600080,4)
 expand(b'\xff\x07\x23\x00\0');assert segment(0)==''
 checks+=1
report=dict(invalid_native_pc_cases=checks,fail_closed=True,module_sha256=t.meta['sha256'])
(BUILD / 'nativepc-bounds-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
