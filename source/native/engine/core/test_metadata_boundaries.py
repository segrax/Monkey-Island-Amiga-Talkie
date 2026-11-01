"""Execute original failed-open flow and native return detours, mocking only I/O/IPC."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import importlib.util, json, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('codec',HERE/'test_metadata.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
from unicorn import m68k_const as r
import unicorn
cpu=t.cpu; put=t.put; g=t.t.t.g; sym=t.t.t.sym; h0=t.t.t.bases[0]
# The complete NVO1 + dialogue state must survive a native open failure.
t.call('_nv_metadata_export',t.buffer,6574)
baseline=bytes(cpu.mem_read(t.buffer,6574))
records=[]; responses={'save':1,'load':0,'commit':1}
for name in ('save','load','commit'):
    pc=sym('_nv_game_metadata_'+name);cpu.mem_write(pc,bytes.fromhex('4e75'))
    def callback(uc,address,size,data,name=name,pc=pc):
        if address!=pc:return
        sp=uc.reg_read(r.UC_M68K_REG_A7)
        args=[int.from_bytes(uc.mem_read(sp+4+4*i,4),'big') for i in range(5)]
        records.append((name,args))
        if name=='load' and responses[name]==1:
            uc.mem_write(args[1],baseline);put(args[3],len(baseline),4)
        uc.reg_write(r.UC_M68K_REG_D0,responses[name]&0xffffffff)
    cpu.hook_add(unicorn.UC_HOOK_CODE,callback)
# Original functions free an old resource, close the prior file, open, and poll input.
# Their task/OS implementations are mocked; the original control flow is executed.
io=[]
for offset in (0x76bc,0x3ebe,0x767a,0x8ef6):
    pc=h0+offset;cpu.mem_write(pc,bytes.fromhex('4e75'))
    def callback(uc,address,size,data,pc=pc,offset=offset):
        if address==pc:io.append(offset)
    cpu.hook_add(unicorn.UC_HOOK_CODE,callback)
put(g+0x5984,0,4);cpu.mem_write(g+0x3a4,b'savegame._a_\0')
put(0x50f000,0x600000,4);put(0x50f004,1,2)
cpu.reg_write(r.UC_M68K_REG_A7,0x50f000);cpu.reg_write(r.UC_M68K_REG_A4,g)
cpu.reg_write(r.UC_M68K_REG_A5,0x506abc)
cpu.emu_start(h0+0x5488,0x600000,count=300000)
assert cpu.reg_read(r.UC_M68K_REG_PC)==0x600000
assert cpu.reg_read(r.UC_M68K_REG_D0)==0 and io==[0x76bc,0x3ebe,0x767a,0x8ef6],io
assert records==[],records
assert t.call('_nv_metadata_export',t.buffer,6574)==6574
assert bytes(cpu.mem_read(t.buffer,6574))==baseline
# A successful persistent SAVE cancels the current line before potentially slow
# metadata hashing, while retaining all provenance/persona selection state.
records.clear();before_cancel=t.t.t.cancels
t.call('_nv_metadata_save',1)
assert t.t.t.cancels==before_cancel+1 and [x[0]for x in records]==['save']
assert t.call('_nv_metadata_export',t.buffer,6574)==6574
assert bytes(cpu.mem_read(t.buffer,6574))==baseline
# Entry cancellation alone never clears provenance; only successful native load
# reaches the metadata return helper. Validate both native success/failure gates.
def native_load_return(result,slot):
    frame=0x50e000;sp=frame-80
    put(frame,0x506abc,4);put(frame+4,0x600000,4);put(frame+8,slot,2)
    put(sp,0x12345678,4);put(sp+4,0x23456789,4)
    cpu.reg_write(r.UC_M68K_REG_A7,sp);cpu.reg_write(r.UC_M68K_REG_A5,frame)
    cpu.reg_write(r.UC_M68K_REG_A4,g);cpu.reg_write(r.UC_M68K_REG_D0,result)
    cpu.emu_start(h0+0x5632,0x600000,count=2000000)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==0x600000
    assert cpu.reg_read(r.UC_M68K_REG_D7)==0x12345678
    assert cpu.reg_read(r.UC_M68K_REG_A3)==0x23456789
    assert cpu.reg_read(r.UC_M68K_REG_A5)==0x506abc
    assert cpu.reg_read(r.UC_M68K_REG_D0)==result
for result,slot in ((0,1),(1,0),(1,27)):
    records.clear();native_load_return(result,slot);assert not records
# Successful old native save with absent sidecar clears stale origins, not game data.
records.clear();responses['load']=0;native_load_return(1,1)
assert [x[0] for x in records]==['load','commit'] and records[-1][1][0]==0
assert bytes(cpu.mem_read(sym('_nv_dialogue_valid'),2))==b'\0\0'
# Valid metadata imports then commits the persona snapshot; commit failure clears.
for commit in (1,0):
    records.clear();responses.update(load=1,commit=commit)
    native_load_return(1,1)
    assert [x[0] for x in records]==['load','commit'] if commit else [x[0] for x in records]==['load','commit','commit']
    assert records[1][1][0]==1
    assert t.call('_nv_metadata_export',t.buffer,6574)==6574
    current=bytes(cpu.mem_read(t.buffer,6574))
    assert (current==baseline)==bool(commit)
report=dict(module_sha256=hashlib.sha256((BUILD / 'Monkey_Talkie_Test').read_bytes()).hexdigest(),
 original_failed_open_flow_executed=True,failed_load_preserves_origin_context=True,
 failed_load_no_metadata_ipc=True,success_and_slot_gates=True,original_load_epilogue_preserved=True,
 absent_old_save_clears_stale_metadata=True,valid_import_before_policy_commit=True,save_cancels_voice_before_hash=True,
 policy_commit_failure_clears_metadata=True,os_and_metadata_ipc_mocked=True)
(BUILD / 'metadata-boundary-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
