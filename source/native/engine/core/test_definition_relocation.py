"""Definition-entry sites survive resource relocation and disabled controls."""
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
control=t.control
flags=int.from_bytes(cpu.mem_read(control+20,4),'big')
# A disabled bridge must not dereference an unavailable globals pointer.
put(control+20,0,4);put(control+16,0,4);call('_nv_definition_begin')
put(control+16,g,4);put(control+20,flags,4)
results=[]
for script,where,offset,expected in ((7,2,64,'g:7:64'),(203,2,64,'l:38:203:64'),(998,1,117,'e:38:ENCD:17'),(999,1,217,'e:38:EXCD:17'),(401,1,317,'o:401:17')):
 put(g+0x5a56,0x600000,4)
 opcode(6,script,where,offset) # actual unpatched store and definition-entry capture
 # Simulate script movement after an earlier resource-loading sub-operation.
 # Original native retainedPC remains stale; current PC/base both relocate.
 put(g+0x5a56,0x603000,4);put(g+0x5a50,0x603000+offset+50,4)
 assert int.from_bytes(cpu.mem_read(g+0x66fa,4),'big')<0x603000
 resource(168,0x600800,b'Relocated definition.\0')
 # Dialogue fixture source belongs to its original synthetic script allocation.
 put(g+0x5a56,0x600000,4);put(g+0x5a50,0x600000+offset+50,4)
 expand(b'\xff\x07\x23\x00\0')
 origin=segment(0);assert origin.endswith('r:'+expected.rsplit(':',1)[0]+':'+str(int(expected.rsplit(':',1)[1])+50)+':0'),origin
 results.append(origin)
report=dict(disabled_null_globals_safe=True,relocated_definition_sites=results,stale_raw66fa_not_reused=True,module_sha256=t.meta['sha256'])
(BUILD / 'definition-relocation-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

