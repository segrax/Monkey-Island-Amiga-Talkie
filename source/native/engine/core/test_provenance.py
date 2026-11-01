"""Compiled provenance + original recursive text conversion; explicit IPC mocks."""
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
spec=importlib.util.spec_from_file_location('context_fixture',HERE/'test_context.py')
t=importlib.util.module_from_spec(spec);spec.loader.exec_module(t)
from unicorn import m68k_const as r
cpu=t.cpu;g=t.g;put=t.put;call0=t.call
def call(name,*args):
    for i,value in enumerate(args):put(0x50f004+4*i,value,4)
    return call0(name)
def opcode(slot,script,where,offset):
    put(g+0x2024,slot,1);put(g+0x20ee+2*slot,script,2);put(g+0x20da+slot,where,1)
    put(g+0x5a50,0x600000+offset+1,4)
    cpu.reg_write(r.UC_M68K_REG_A4,g);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    cpu.emu_start(t.bases[0]+0x92aa,t.bases[0]+0x92b0,count=200)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==t.bases[0]+0x92b0
    call('_nv_definition_begin')
def resource(index,address,text,source=0):
    call('_nv_resource_begin',index,source)
    call('_nv_resource_clear',index)
    put(g+0x2780+4*index,address,4)
    cpu.mem_write(address,b'\0'*6+text)
    call('_nv_resource_end')
def expand(raw):
    cpu.mem_write(0x600a00,raw)
    put(g+0x59f2,0x600a00,4)
    call('_nv_dialogue_capture')
    put(g+0x5ed0,g+0x5ed4,4)
    put(0x50f000,0x600000,4);put(0x50f004,0x600a00,4)
    cpu.reg_write(r.UC_M68K_REG_A4,g);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    cpu.emu_start(t.bases[0]+0xe286,0x600000,count=200000)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==0x600000
def segment(start):
    put(g+0x59f6,start,1);call('_nv_dialogue_segment')
    return t.captured_origins[-1]

put(g+0x19f8,38,1);put(g+0x19f9,38,1);put(g+0x5980,200,1);put(g+0x5a56,0x600000,4)
opcode(1,7,2,31)
# Caller keys use continuation after startScript operands, independently of opcode.
put(g+0x20ee+12,203,2);put(g+0x20da+6,2,1)
put(g+0x5a50,0x600035,4)
call('_nv_provenance_program',6)
opcode(6,203,2,64)
put(g+0x5a50,0x600050,4)  # Literal PC deliberately differs from opcode64.
text=b'Choose this line.\xff\x03And this one.\0'
resource(168,0x600800,text)
expand(b'I said: \xff\x07\x23\x00\0')
assert segment(0)=='c:g:7:53:r:l:38:203:80:0',t.captured_origins[-1]
converted=bytes(cpu.mem_read(g+0x5ed4,100))
next_segment=converted.index(b'\xff\x03')+2
assert segment(next_segment)=='c:g:7:53:r:l:38:203:80:1',t.captured_origins[-1]
# Copying a resource retains its definition/caller despite a later VM opcode.
opcode(6,203,2,90)
resource(169,0x600900,text,0x600806)
expand(b'\xff\x07\x24\x00\0')
assert segment(0)=='c:g:7:53:r:l:38:203:80:0'
# Mutation invalidates identity even though bytes still look identical.
call('_nv_resource_mutate',36)
expand(b'\xff\x07\x24\x00\0');assert segment(0)==''
# Two different definitions in the same visible segment must not pick one.
resource(170,0x600b00,b'Another line.\0')
opcode(6,203,2,100)
resource(168,0x600800,b'Known single.\0')
expand(b'\xff\x07\x23\x00 plus \xff\x07\x25\x00\0');assert segment(0)==''
# Unknown resource identity also prevents selecting a different known span.
expand(b'\xff\x07\x23\x00 plus \xff\x07\x24\x00\0');assert segment(0)==''
resource(171,0x600c00,b'Known single.\0')
expand(b'\xff\x07\x26\x00 plus \xff\x07\x24\x00\0');assert segment(0)==''
call('_nv_resource_clear',168)
expand(b'\xff\x07\x23\x00\0');assert segment(0)==''
for script,base,entry,wanted in ((998,100,0x19fe,'e:38:ENCD'),(999,200,0x19fa,'e:38:EXCD'),(401,300,None,'o:401')):
    if entry is not None:put(g+entry,base,4)
    else:
        put(g+0x1a1e,2,1);put(g+0x1c96+4,401,2);put(g+0x1ec6+8,base,4)
    opcode(6,script,1,base+17)
    resource(168,0x600800,b'Entry/object resource.\0')
    expand(b'\xff\x07\x23\x00\0')
    assert segment(0)=='c:g:7:53:r:'+wanted+':18:0',t.captured_origins[-1]
result=dict(module_sha256=t.meta['sha256'],compiled_68000_provenance_pass=True,original_recursive_conversion_executed=True,
    exact_literal_pc_origin_not_opcode=True,retained_nested_caller=True,
    mixed_literal_prefix=True,resource_segment1=True,copy_retains_origin=True,
    mutation_erase_multiple_unknown_fail_closed=True,encd_excd_object_definition_program_bases_pass=True,
    original_unpatched_opcode_dispatch_executed=True,ipc_mocked=True,amiga_os_not_executed=True)
(BUILD / 'provenance-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
