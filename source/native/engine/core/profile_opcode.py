"""Count the compiled instruction-start hook, without executing its next opcode."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util,json,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('context_fixture',HERE/'test_context.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
import unicorn
from unicorn import m68k_const as r
count=0
def instruction(cpu,pc,size,data):
    global count
    count+=1
t.cpu.hook_add(unicorn.UC_HOOK_CODE,instruction)
result=dict(module_sha256=t.meta['sha256'],metric='compiled_68000_instructions_not_cycles')
for name,where,script in [('local',2,203),('object64',1,401)]:
    t.put(t.control+20,3,4);t.put(t.g+0x2024,6,1)
    t.put(t.g+0x20da+6,where,1);t.put(t.g+0x20ee+12,script,2)
    t.put(t.g+0x1a1e,64,1);t.put(t.g+0x1c96+2,401,2);t.put(t.g+0x1ec6+4,300,4)
    t.put(t.g+0x5a50,0x60015f,4);t.put(t.g+0x5a56,0x600000,4)
    t.cpu.reg_write(r.UC_M68K_REG_A4,t.g);t.cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    count=0;t.cpu.emu_start(t.bases[0]+0x92aa,t.bases[0]+0x92b0,count=100000)
    assert t.cpu.reg_read(r.UC_M68K_REG_PC)==t.bases[0]+0x92b0
    result[name]=count
(HERE/(sys.argv[1]if len(sys.argv)>1 else'opcode-profile.json')).write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
