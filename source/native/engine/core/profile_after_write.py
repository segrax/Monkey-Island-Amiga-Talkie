"""Count actual compiled field-write work; Exec calls are explicitly modeled."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
import sys
here=Path(__file__).resolve().parent
exec(compile((here/'test_direct_driver.py').read_text(),str(here/'test_direct_driver.py'),'exec'))
put(control+20,3,4)
counter=0
def count_instruction(uc,pc,size,data):
    global counter
    counter+=1
cpu.hook_add(unicorn.UC_HOOK_CODE,count_instruction)
result=dict(module_sha256=meta['sha256'],metric='compiled_68000_instructions_not_cycles',exec_mocked=True,cases={})
for speech in (0,1):
    put(driver+layout['speech_active'],speech,2)
    for offset in (0,4,6,8,10):
        counter=0
        call('_nv_driver_after_write',bank,offset)
        result['cases'][f'speech_{speech}_offset_{offset}']=counter
path=here/(sys.argv[1] if len(sys.argv)>1 else 'after-write-profile.json')
path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
