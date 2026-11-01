"""Execute compiled native context capture with explicit IPC function mocks."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import json
from pathlib import Path
import struct
import sys
import os
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as r

bases=[0x100000,0x20000,0x200000,0x300000,0x340000,0x380000,0x3c0000,0x400000,0xa80000]
IMAGE_DIR=Path(os.environ.get('NATIVE_FIXTURE_DIR',str(BUILD)))
IMAGE=IMAGE_DIR/('Monkey_Talkie_Scaled' if (IMAGE_DIR/'Monkey_Talkie_Scaled').exists() else 'Monkey_Talkie_Test')
meta=json.loads((IMAGE_DIR/'module.json').read_text())
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN)
cpu.ctl_set_cpu_model(r.UC_CPU_M68K_M68000)
reader=HunkReader();assert reader.read_file(str(IMAGE))==0 and reader.build_segments()
for h in reader.hunks:
    if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS'):
        cpu.mem_map(bases[h['hunk_no']],(h['alloc_size']+4095)&~4095)
        if 'data'in h:cpu.mem_write(bases[h['hunk_no']],h['data'])
current=None
for h in reader.hunks:
    if 'hunk_no'in h:current=h['hunk_no']
    if h['type_name']=='HUNK_ABSRELOC32':
        for target,offsets in h['reloc'].items():
            for offset in offsets:
                p=bases[current]+offset
                cpu.mem_write(p,struct.pack('>I',int.from_bytes(cpu.mem_read(p,4),'big')+bases[target]))
cpu.mem_map(0x500000,0x10000);cpu.mem_map(0x600000,0x10000)
def put(address,value,size):cpu.mem_write(address,value.to_bytes(size,'big'))
def sym(name):
    e=meta['exports'][name]
    return bases[e['hunk']]+e['offset']
control=sym('_nv_control');g=bases[2]
put(control+12,bases[0],4);put(control+16,g,4);put(control+20,2,4)
cpu.reg_write(r.UC_M68K_REG_SR,0)
captured=[];captured_origins=[];programs=[];active=0;cancels=0
mock={sym('_nv_game_'+n):n for n in ('play','poll','active','cancel','program')}
mock[sym('_nv_driver_service')]='driver_service'
for pc in mock:cpu.mem_write(pc,bytes.fromhex('4e75'))
def hook(uc,pc,size,userdata):
    global cancels
    if pc not in mock:return
    name=mock[pc]
    if name=='play':
        sp=uc.reg_read(r.UC_M68K_REG_A7)
        p=int.from_bytes(uc.mem_read(sp+4,4),'big')
        raw=bytes(uc.mem_read(p,786))
        fields=struct.unpack_from('>6HI',raw)
        length=int.from_bytes(raw[272:274],'big')
        captured.append(dict(fields=fields,text=raw[274:274+length].hex()))
        captured_origins.append(raw[16:272].split(b'\0',1)[0].decode('ascii'))
    if name=='cancel':cancels+=1
    if name=='program':
        sp=uc.reg_read(r.UC_M68K_REG_A7)
        programs.append(struct.unpack('>4I',bytes(uc.mem_read(sp+4,16))))
    uc.reg_write(r.UC_M68K_REG_D0,active if name=='active' else 1)
cpu.hook_add(unicorn.UC_HOOK_CODE,hook)
def call(name):
    put(0x50f000,0x600000,4)
    cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    cpu.emu_start(sym(name),0x600000,count=100000)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==0x600000
    return cpu.reg_read(r.UC_M68K_REG_D0)

put(g+0x19f8,38,1);put(g+0x19f9,38,1);put(g+0x2024,6,1)
put(g+0x20ee+12,203,2);put(g+0x20da+6,2,1);put(g+0x5980,200,1)
put(g+0x59f2,0x600048,4);put(g+0x5a56,0x600000,4);put(g+0x3a8e,1,2)
cpu.mem_write(g+0x5ed4,b'Hi!\xff\x03My name is Guybrush.\0')
put(g+0x59f6,0,1);call('_nv_dialogue_capture');call('_nv_dialogue_segment')
assert captured[-1]==dict(fields=(38,38,1,2,203,0,72),text=b'Hi!'.hex()),captured
# VM moved to another script slot; identity must remain the initial print source.
put(g+0x2024,1,1);put(g+0x20ee+2,99,2);put(g+0x59f6,5,1)
call('_nv_dialogue_segment')
assert captured[-1]==dict(fields=(38,38,1,2,203,1,72),text=b'My name is Guybrush.'.hex()),captured
# Formatting words may contain zero and FF03 bytes without ending the sentence.
cpu.mem_write(g+0x5ed4,b'A\xff\x0c\x00\x00B\xff\x09\xff\x03C\0')
put(g+0x59f6,0,1);call('_nv_dialogue_segment')
assert bytes.fromhex(captured[-1]['text'])==b'A\xff\x0c\x00\x00B\xff\x09\xff\x03C'
active=1;assert call('_nv_dialogue_display')==1
active=0;assert call('_nv_dialogue_display')==0
put(g+0x19f8,39,1);call('_nv_dialogue_display');assert cancels==1
call('_nv_dialogue_segment');assert len(captured)==3
call('_nv_dialogue_stop');assert cancels==2
def capture_program(script,where,base_offset,kind):
    put(g+0x19f8,38,1);put(g+0x2024,6,1)
    put(g+0x20ee+12,script,2);put(g+0x20da+6,where,1)
    put(g+0x59f2,0x600000+base_offset+43,4)
    put(g+0x59f6,0,1);cpu.mem_write(g+0x5ed4,b'Test\0')
    call('_nv_dialogue_capture');call('_nv_dialogue_segment')
    assert captured[-1]['fields']==(38,38,1,kind,script,0,43),captured[-1]
put(g+0x19fe,100,4);capture_program(998,1,100,4)
put(g+0x19fa,200,4);capture_program(999,1,200,5)
put(g+0x1a1e,2,1);put(g+0x1c96+4,401,2);put(g+0x1ec6+8,300,4)
capture_program(401,1,300,3)
capture_program(401,0,0,3)
# New global-script activation uses the target slot's saved PC, not caller PC.
put(g+0x20ee+12,111,2);put(g+0x20da+6,2,1);put(g+0x2026+24,0,4)
put(0x50f004,6,4);call('_nv_dialogue_program')
assert programs[-1]==(1,38,111,0),programs
result=dict(compiled_68000_context_fixtures_pass=True,identity_retained_after_slot_change=True,
            embedded_zero_format_operands_preserved=True,hold_release_room_cancel_pass=True,
            original_encd998_excd999_room_inventory_object_offsets_pass=True,program_activation_context_pass=True,
            ipc_mocked=True,actual_amiga_os_execution=False)
(BUILD / 'context-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
