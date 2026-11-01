"""Actual Amiga source definitions through original VM/handlers; GPL-3.0-or-later."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json,hashlib,struct
HERE=Path(__file__).resolve().parent
fixture=(HERE/'test_context.py').read_text().split('\nput(g+0x19f8,38,1)',1)[0]
ASSETS=Path('D:/Projects/rescumm/assets/mi1-amiga/room')
bar=ASSETS/'028/scripts/script_local_134_LSCR_off072601.lscr'
cases=[('kill',bar,7,0x2f4,28,220,b'I mean to kill you all!'),('pirate',bar,7,0x33d,28,220,b'I want to be a pirate.'),('fireman',bar,7,0x385,28,220,b'I want to be a fireman.'),('string',ASSETS/'002/scripts/script_096_SC_off025955.sc',6,0,2,96,b'.'*100),('actor_name',ASSETS/'031/scripts/script_local_057_LSCR_off014149.lscr',7,0x1b,31,201,b'Otis')]
results=[]
for shifted in (False,True):
 for name,path,header,opcode,room,script,text in cases:
  n={'__file__':str(HERE/'test_context.py'),'__name__':'literal_actual_fixture'}
  source=fixture
  if shifted:source=source.replace('bases=[0x100000,0x20000,0x200000,0x300000,0x310000,0x320000,0x330000,0x400000,0xa80000]','bases=[0x180000,0x40000,0x280000,0x380000,0x390000,0x3a0000,0x3b0000,0x480000,0xb00000]')
  exec(compile(source,str(HERE/'test_context.py'),'exec'),n)
  cpu,g,put,sym,bases,r=[n[x] for x in ('cpu','g','put','sym','bases','r')]
  raw=path.read_bytes();code=raw[header:];literal=code.index(text,opcode);assert code[literal+len(text)]==0
  put(g+0x19f8,room,1);put(g+0x19f9,room,1);put(g+0x2024,6,1);put(g+0x20ee+12,script,2);put(g+0x20da+6,2,1);put(g+0x5980,200,1)
  put(g+0x3a5c+2*100,122,2);put(g+0x3a5c+2*228,40,2)
  put(g+0x5a56,0x600000,4);put(g+0x5a50,0x600000+opcode,4);cpu.mem_write(0x600000,code)
  seen=[]
  def trace(uc,pc,size,unused):
   if pc==sym('_nv_resource_begin'):
    sp=uc.reg_read(r.UC_M68K_REG_A7);index=int.from_bytes(uc.mem_read(sp+4,4),'big');source=int.from_bytes(uc.mem_read(sp+8,4),'big');current=int.from_bytes(uc.mem_read(g+0x5a50,4),'big')
    assert source==0 and current==0x600000+literal
    # Model a script relocation before resource allocation; native retained opcode stays stale.
    uc.mem_write(0x603000,code);put(g+0x5a56,0x603000,4);put(g+0x5a50,0x603000+literal,4)
    seen.append(index)
   if pc==bases[0]+0xccca:uc.emu_stop()
  cpu.hook_add(n['unicorn'].UC_HOOK_CODE,trace);cpu.reg_write(r.UC_M68K_REG_A4,g);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
  cpu.emu_start(bases[0]+0x92a4,0x600000,count=100000)
  assert cpu.reg_read(r.UC_M68K_REG_PC)==bases[0]+0xccca and len(seen)==1
  index=seen[0];put(g+0x2780+4*index,0x608000,4);cpu.mem_write(0x608000,b'\0'*6+text+b'\0');n['call']('_nv_resource_end')
  put(g+0x5ed0,g+0x5ed4,4);put(0x50f004,0x608006,4);n['call']('_nv_conversion_begin');cpu.mem_write(g+0x5ed4,text+b'\0');put(g+0x5ed0,g+0x5ed4+len(text),4);n['call']('_nv_conversion_end')
  put(0x50f004,0,4);put(0x50f008,0x609000,4);put(0x50f00c,256,4);n['call']('_nv_provenance_origin')
  origin=bytes(cpu.mem_read(0x609000,256)).split(b'\0',1)[0].decode();expected=('r:g:%d:%d:0'%(script,literal)) if script<200 else ('r:l:%d:%d:%d:0'%(room,script,literal));assert origin==expected,(name,origin,expected)
  results.append({'case':name,'relocated_layout':shifted,'source_sha256':hashlib.sha256(raw).hexdigest(),'opcode_offset':opcode,'literal_offset':literal,'origin':origin,'resource_index':index})
report={'pass':True,'checks':len(results),'module_sha256':n['meta']['sha256'],'actual_original_VM_dispatch_and_constructor_handlers':True,'earlier_script_relocation_modeled_before_resource_allocator':True,'results':results,'limitations':'Allocator and visible expansion bytes modeled; actual pending capture/origin composition compiled68000. Actual recursive converter/copy/mutation separately tested.'}
(BUILD / 'actual-literal-validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
