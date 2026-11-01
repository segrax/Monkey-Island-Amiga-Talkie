"""Actual compiled metadata client with register-ABI Exec traps; no real OS."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util,json,hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('fixture',HERE/'test_context.py');t=importlib.util.module_from_spec(s);s.loader.exec_module(t)
import unicorn
from unicorn import m68k_const as r
cpu=t.cpu;put=t.put;sym=t.sym
execbase=0x808000;cpu.mem_map(0x800000,0x10000);cpu.mem_map(0xdff000,0x1000)
put(sym('_SysBase'),execbase,4);put(execbase+0x126,0xffff,2);put(0xdff01c,0x4000,2)
policy=0x602000;voice=0x603000;blob=0x604000;path=0x601000;outbytes=0x601300
cpu.mem_write(path,b'savegame._a_\0');put(0x50f004,policy,4);put(0x50f008,0x12345678,4)
t.call('_nv_policy_init') if '_nv_policy_init' in t.meta['exports'] else None
# Canonical 400-byte policy and one legal persona domain.
cpu.mem_write(policy,b'\0'*400);put(policy,0x4e565059,4);put(policy+4,1,2);put(policy+6,400,2);put(policy+8,1,2);put(policy+12,0x12345678,4)
put(policy+16+6,49,2);put(policy+16+8,3,2);put(policy+16+10,3,2)
# Every mocked library entry returns through the real compiler-emitted JSR ABI.
lvos={-198:'AllocSignal',-294:'FindTask',-132:'Forbid',-138:'Permit',-390:'FindPort',-366:'PutMsg',-372:'GetMsg',-384:'WaitPort',-120:'Disable',-126:'Enable',-204:'FreeSignal'}
for off in lvos:cpu.mem_write(execbase+off,bytes.fromhex('4e75'))
queue=[];events=[];server=True;mode='valid';expected=b'opaque verified payload';response_seed=0x10203040
get=lambda a,n=4:int.from_bytes(cpu.mem_read(a,n),'big')
def hook(uc,pc,size,data):
 global mode
 if pc-execbase not in lvos:return
 name=lvos[pc-execbase];events.append(name);result=0
 if name=='AllocSignal':result=5
 if name=='FindTask':result=0x806000
 if name=='FindPort':result=0x807000 if server else 0
 if name=='PutMsg':
  p=uc.reg_read(r.UC_M68K_REG_A1);cmd=get(p+22,2);length=get(p+18,2)
  put(p+26,0,2)
  if cmd==1:assert length==956;put(p+32,voice,4);put(p+822,policy,4)
  if cmd in (6,7):
   assert length==1366 and get(p+1224,2)==1 and get(p+1226,2)==0
   assert bytes(cpu.mem_read(p+956,12))==b'savegame._a_'
   dest=get(p+1212);cap=get(p+1216)
   if cmd==6:assert bytes(cpu.mem_read(dest,cap))==expected;put(p+1228,1,4)
   else:
    put(p+1228,1 if mode!='missing' else 0,4);put(p+1220,len(expected),4)
    uc.mem_write(dest,expected);put(p+1232,response_seed,4);put(p+1236,1,2)
    uc.mem_write(p+1238,bytes.fromhex('0003003100020003'))
    if mode=='invalid':put(p+1238+4,3,2)
  queue.append(p)
 if name=='GetMsg':result=queue.pop(0) if queue else 0
 if name=='Disable':put(execbase+0x126,(get(execbase+0x126,1)+1)&255,1)
 if name=='Enable':put(execbase+0x126,(get(execbase+0x126,1)-1)&255,1)
 uc.reg_write(r.UC_M68K_REG_D0,result)
cpu.hook_add(unicorn.UC_HOOK_CODE,hook)
def call(n,*args):
 for i,a in enumerate(args):put(0x50f004+4*i,a,4)
 return t.call(n)
assert call('_nv_game_set_policy',policy)==1
cpu.mem_write(blob,expected)
assert call('_nv_game_metadata_save',path,blob,len(expected),1)==1
assert events.count('PutMsg')==2 and not queue
# Load returns opaque data + pending policy; no persona mutation until validated.
assert call('_nv_game_metadata_load',path,blob,6574,outbytes,1)==1
assert get(outbytes)==len(expected) and get(policy+12)==0x12345678
assert call('_nv_game_metadata_commit',1)==1 and get(policy+12)==response_seed and get(policy+10,2)==1
# Rejected inner blob does not apply RNG; stale selector state is explicitly cleared.
put(policy+12,0x12345678,4);assert call('_nv_game_metadata_load',path,blob,6574,outbytes,1)==1
assert call('_nv_game_metadata_commit',0)==0 and get(policy+12)==0x12345678 and get(policy+10,2)==0
mode='invalid';assert call('_nv_game_metadata_load',path,blob,6574,outbytes,1)==1
assert call('_nv_game_metadata_commit',1)==0 and get(policy+10,2)==0
mode='missing';assert call('_nv_game_metadata_load',path,blob,6574,outbytes,1)==0
assert call('_nv_game_metadata_commit',1)==0
# Refuse synchronous metadata operation in forbidden/disabled/raw-master-off contexts.
for offset in (0x126,0x127):
 n=len(events);put(execbase+offset,0,1);assert call('_nv_game_metadata_save',path,blob,len(expected),1)==0xfffffffe;assert len(events)==n;put(execbase+offset,255,1)
put(0xdff01c,0,2);n=len(events);assert call('_nv_game_metadata_save',path,blob,len(expected),1)==0xfffffffe and len(events)==n;put(0xdff01c,0x4000,2)
server=False;assert call('_nv_game_metadata_save',path,blob,len(expected),1)==0xfffffffe
report=dict(module_sha256=hashlib.sha256((BUILD / 'Monkey_Talkie_Test').read_bytes()).hexdigest(),compiled_68000_client=True,extended_wire_1366=True,attach_then_save=True,load_two_phase_persona_commit=True,reject_invalid_domain=True,missing_safe_default=True,refuse_disabled_forbidden_and_masteroff=True,missing_server_no_wait=True,exec_library_calls_mocked=True)
(BUILD / 'metadata-client-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
