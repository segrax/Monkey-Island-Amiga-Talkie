"""Count actual compiled 68000 instructions; this is not a cycle benchmark."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util
import json
import sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('driver_fixture',HERE/'test_driver.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
import unicorn
count=0
def instruction(uc,pc,size,data):
    global count
    count+=1
t.cpu.hook_add(unicorn.UC_HOOK_CODE,instruction)
driver=t.sym('_nv_driver')
t.put(t.voice+8,17,2);t.put(t.voice+10,0,2);t.put(t.voice+6,6,2)
sample=0x605000
t.cpu.mem_write(sample,bytes([32,224])*128)
result=dict(module_sha256=t.meta['sha256'],samples=256,metric='compiled_68000_instructions_not_cycles')
for dma in (0,1):
    t.call('_nv_paula_dma',driver,0)
    t.call('_nv_paula_pointer',driver,sample)
    t.call('_nv_paula_length',driver,128)
    t.call('_nv_paula_period',driver,322)
    t.call('_nv_paula_volume',driver,64)
    t.call('_nv_paula_dma',driver,dma)
    count=0
    t.call('_nv_mixer_render',driver,0x606000,256,10)
    result['dma_'+str(dma)]=dict(instructions=count,output_hex=bytes(t.cpu.mem_read(0x606000,256)).hex())
path=HERE/(sys.argv[1] if len(sys.argv)>1 else 'idle-profile.json')
path.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v if k not in ('dma_0','dma_1') else v['instructions'] for k,v in result.items()}))
