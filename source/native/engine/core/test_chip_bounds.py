"""Compiled speech-copy writes guarded to exactly256-byte CHIP allocations."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
here=Path(__file__).resolve().parent
source=(here/'test_direct_driver.py').read_text()
guard="""
chip_writes=[]
def chip_guard(uc,access,address,size,value,unused):
 if 0x800000 <= address < 0x810000:
  offset=(address-0x800000)%0x2000
  assert offset+size<=256,(hex(address),size)
  chip_writes.append((address,size))
cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,chip_guard)
def free_guard(uc,pc,size,unused):
 if pc==0x700800-210:
  assert uc.reg_read(r.UC_M68K_REG_D0)==256
cpu.hook_add(unicorn.UC_HOOK_CODE,free_guard)
"""
source=source.replace("\ncall('_nv_driver_start')",guard+"\ncall('_nv_driver_start')",1)
exec(compile(source,str(here/'test_direct_driver.py'),'exec'))
assert chip_writes
print('All compiled PCM copy/zero writes within256-byte bounds; allFreeMem sizes256')
