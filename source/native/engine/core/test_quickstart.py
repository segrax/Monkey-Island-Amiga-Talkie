"""Verify optional native script omission before any VM/resource allocation."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('fixture',HERE/'test_context.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
from unicorn import m68k_const as r
cpu=t.cpu
for flags,script,wanted in ((1,152,0),(3,152,0),(9,151,0),(9,153,0),(9,152,1),(11,152,1)):
    t.put(t.control+20,flags,4);t.put(0x50f004,script,4)
    assert t.call('_nv_game_skip_script')==wanted

names=['D%d'%n for n in range(8)]+['A%d'%n for n in range(7)]
regs=[getattr(r,'UC_M68K_REG_'+n) for n in names]
start=t.bases[0]+0x9a34;stop=0x600000
gstate=bytes(cpu.mem_read(t.g,0x7270))
for flags in range(32):
    cpu.reg_write(r.UC_M68K_REG_SR,flags)
    for i,reg in enumerate(regs):cpu.reg_write(reg,0x500100+i*0x100)
    cpu.reg_write(r.UC_M68K_REG_A4,t.g)
    t.put(t.control+20,11,4)
    t.put(0x50f000,stop,4);t.put(0x50f004,152,2)
    cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    before=[cpu.reg_read(reg) for reg in regs]
    cpu.emu_start(start,stop,count=1000)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==stop
    assert [cpu.reg_read(reg) for reg in regs]==before
    assert cpu.reg_read(r.UC_M68K_REG_A7)==0x50f004
    assert cpu.reg_read(r.UC_M68K_REG_SR)==flags
    assert bytes(cpu.mem_read(t.g,0x7270))==gstate
result=dict(optional_flag8_only=True,only_script152=True,all32ccr_registers_preserved=True,
            vm_and_resources_unchanged=True,caller_stack_retained=True,actual_amiga_runtime=False)
(BUILD / 'quickstart-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
