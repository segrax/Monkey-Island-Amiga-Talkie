"""New entry hooks preserve all CCR/register/prologue effects."""
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
exec(compile((HERE/'test_adapters.py').read_text().split('\ncount=0',1)[0],str(HERE/'test_adapters.py'),'exec'))
checks=0
for bases in ((0x100000,0x20000,0x200000,0x300000,0x310000,0x320000,0x330000),(0x180000,0x40000,0x280000,0x380000,0x390000,0x3a0000,0x3b0000)):
 for patch in META['patches']:
  if patch['address'] not in (0xc540,0xc9c0,0xcf8a):continue
  for flags in range(32):
   expected=execute(ROOT/'data/original/Monkey_Island',bases[:3],patch,flags,False)
   actual=execute(BUILD / 'Monkey_Talkie_Test',bases,patch,flags,True)
   assert actual==expected,(hex(patch['address']),flags)
   checks+=1
result=dict(checks=checks,all32ccr=True,two_relocations=True,actual_saved_register_frames=True,module_sha256=META['sha256'])
(BUILD / 'definition-adapter-validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
