"""Run the compiled 68000 driver with explicit Exec and Paula register models."""
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
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as r
meta=json.loads((BUILD / 'module.json').read_text())
bases=[0x100000,0x20000,0x200000,0x300000,0x310000,0x320000,0x330000]
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN)
cpu.ctl_set_cpu_model(r.UC_CPU_M68K_M68000)
reader=HunkReader();assert reader.read_file(str(BUILD / 'Monkey_Talkie_Test'))==0 and reader.build_segments()
for h in reader.hunks:
    if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS'):
        cpu.mem_map(bases[h['hunk_no']],(h['alloc_size']+4095)&~4095)
        if 'data' in h:cpu.mem_write(bases[h['hunk_no']],h['data'])
current=None
for h in reader.hunks:
    if 'hunk_no'in h:current=h['hunk_no']
    if h['type_name']=='HUNK_ABSRELOC32':
        for target,offsets in h['reloc'].items():
            for offset in offsets:
                p=bases[current]+offset
                cpu.mem_write(p,struct.pack('>I',int.from_bytes(cpu.mem_read(p,4),'big')+bases[target]))
for address,size in ((0,4096),(0x500000,0x10000),(0x600000,0x20000),
                     (0x700000,0x10000),(0x800000,0x10000),(0xdff000,4096)):
    cpu.mem_map(address,size)
def put(address,value,size):cpu.mem_write(address,value.to_bytes(size,'big'))
def get(address,size):return int.from_bytes(cpu.mem_read(address,size),'big')
def sym(name):
    e=meta['exports'][name];return bases[e['hunk']]+e['offset']
put(4,0x700800,4);put(0x70,0x700400,4)
voice=0x600000;pcm=0x610000;control=sym('_nv_control')
put(voice,0x4d563031,4);put(voice+4,1,2);put(voice+24,16384,2)
put(voice+26,32,2);put(voice+28,22050,2);put(voice+30,161,2);put(voice+36,pcm,4)
put(control+8,voice,4);put(control+12,bases[0],4);put(control+16,bases[2],4);put(control+20,1,4)
hardware={0xdff096:0x200,0xdff09a:0x4000,0xdff09c:0}
duck=meta['speech_balance']['music_ducking']
mirrors={0xdff096:0xdff002,0xdff09a:0xdff01c,0xdff09c:0xdff01e}
for port,value in hardware.items():put(mirrors[port],value,2)
writes=[];allocs=[];freed=[]
def memhook(uc,access,address,size,value,userdata):
    if address in hardware:
        mask=value&0x7fff
        hardware[address]=(hardware[address]|mask) if value&0x8000 else (hardware[address]&~mask)
        put(mirrors[address],hardware[address],2)
        writes.append((hex(address),hex(value)))
cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,memhook)
execs={0x700800-198:'alloc',0x700800-210:'free',0x700800-324:'signal'}
for pc in execs:cpu.mem_write(pc,bytes.fromhex('4e75'))
def codehook(uc,pc,size,userdata):
    if pc not in execs:return
    if execs[pc]=='alloc':
        assert uc.reg_read(r.UC_M68K_REG_D0)==256
        assert uc.reg_read(r.UC_M68K_REG_D1)==0x10003
        p=0x800000+len(allocs)*0x2000;allocs.append(p);uc.reg_write(r.UC_M68K_REG_D0,p)
    elif execs[pc]=='free':freed.append(uc.reg_read(r.UC_M68K_REG_A1))
cpu.hook_add(unicorn.UC_HOOK_CODE,codehook)
cpu.reg_write(r.UC_M68K_REG_SR,0)
def call(name,*args):
    put(0x50f000,0x60f000,4)
    for i,arg in enumerate(args):put(0x50f004+i*4,arg,4)
    cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    cpu.emu_start(sym(name),0x60f000,count=500000)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==0x60f000,(name,hex(cpu.reg_read(r.UC_M68K_REG_PC)))
def irq():
    hardware[0xdff09c]|=0x80;put(0xdff01e,hardware[0xdff09c],2)
    call('_nv_driver_irq')
call('_nv_driver_start')
assert get(control+20,4)==3 and len(allocs)==2
assert get(0x70,4)==sym('_nv_irq') and hardware[0xdff096]&0x201==0x201
assert hardware[0xdff09a]&0x4080==0x4080
call('_nv_driver_volume',0xdff0b0,127)
call('_nv_driver_volume',0xdff0c0,63)
call('_nv_driver_volume',0xdff0d0,32)
assert [get(a,2) for a in (0xdff0b8,0xdff0c8,0xdff0d8)]==[64,63,32]
# Speech starts before any original music-install call.
cpu.mem_write(pcm,bytes(range(256))*4)
put(voice+8,1,2);put(voice+10,0,2);put(voice+14,1000,2);put(voice+16,1,2);put(voice+6,3,2)
irq();irq();assert get(voice+12,2)==256
assert any(cpu.mem_read(p,256)!=b'\0'*256 for p in allocs)
call('_nv_driver_control',0,0x800f)
assert hardware[0xdff096]&15==15
call('_nv_driver_control',0,0x200)
assert hardware[0xdff096]&0x20f==0x201
irq();assert get(voice+12,2)==512
assert [get(a,2) for a in (0xdff0b8,0xdff0c8,0xdff0d8)]==([16,15,8] if duck else [64,63,32])
call('_nv_driver_volume',0xdff0b0,48)
assert get(0xdff0b8,2)==(12 if duck else 48)
call('_nv_driver_clear_native_volume',2)
assert get(0xdff0c8,2)==0
call('_nv_driver_control',0,0x8200)
assert hardware[0xdff096]&0x20f==0x20f
# Original music shutdown restores then clears its saved vector; stream survives.
call('_nv_driver_restore',0x700400)
put(bases[0]+0x17a0,0,4)
assert get(0x70,4)==sym('_nv_irq') and hardware[0xdff096]&0x201==0x201
irq();irq();assert get(voice+12,2)==1000 and get(voice+6,2)==5
assert get(voice+20,2)==0
call('_nv_driver_install',bases[0]+0xbca)
irq();irq();assert get(voice+6,2)==6 and get(voice+20,2)==1
irq();irq()
assert [get(a,2) for a in (0xdff0b8,0xdff0c8,0xdff0d8)]==[48,0,32]
put(voice+8,2,2);put(voice+10,0,2);put(voice+12,0,2)
put(voice+14,1000,2);put(voice+16,0,2);put(voice+6,3,2)
irq();irq()
assert get(0xdff0b8,2)==(12 if duck else 48)
call('_nv_driver_volume',0xdff0b0,60)
assert get(0xdff0b8,2)==(15 if duck else 60)
put(voice+10,2,2)
irq();irq()
assert get(voice+6,2)==8 and get(0xdff0b8,2)==60
call('_nv_driver_end')
assert get(0x70,4)==0x700400 and get(control+20,4)==1
assert get(bases[0]+0x1942,4)==0xdff0a0
assert hardware[0xdff096]&1==0 and hardware[0xdff09a]&0x80==0
assert freed==allocs
result=dict(compiled_68000_driver_pass=True,early_speech_before_music=True,
    master_clear_preserves_stream_and_native_channel_masks=True,music_stop_reinit_preserves_stream=True,
    eof_waits_for_physical_played_counter=True,teardown_restores_owned_nonzero_vector=True,
    music_ducking_enabled=duck,all_channel_latest_write_restore_pass=True,volume_bit6_normalization_pass=True,
    cancelled_voice_restores_latest_native_volumes=True,
    physical_gain_waits_for_playing_buffer=True,
    exec_and_hardware_explicitly_modeled=True,actual_amiga_runtime=False,writes=writes)
(BUILD / 'driver-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({k:v for k,v in result.items() if k!='writes'}))
