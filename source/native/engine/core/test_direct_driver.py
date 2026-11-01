"""Compiled dedicated driver with explicit Exec, E-clock and Paula models."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
from pathlib import Path
import json
here = Path(__file__).resolve().parent
# Reuse only HUNK relocation, memory and call setup; old mixed-mode assertions
# below the fixture's first start call intentionally do not apply here.
source = (here / 'test_driver.py').read_text().split("call('_nv_driver_start')", 1)[0]
exec(compile(source, str(here / 'test_driver.py'), 'exec'))
ticks = 100
nesting = -1
clock_stops = 0
clock_available = 1
other_volumes = (19, 47, 63)
for n,value in enumerate(other_volumes,1): put(0xdff0a8+16*n,value,2)
def others_unchanged():
    assert tuple(get(0xdff0a8+16*n,2) for n in range(1,4)) == other_volumes
for offset in (-120, -126):
    cpu.mem_write(0x700800 + offset, bytes.fromhex('4e75'))
mocked = {sym('_nv_clock_start'): 'start', sym('_nv_clock_now'): 'now', sym('_nv_clock_stop'): 'stop'}
for address in mocked: cpu.mem_write(address, bytes.fromhex('4e75'))
def clock_hook(uc, pc, size, data):
    global nesting, clock_stops
    if pc == 0x700800 - 120:
        nesting += 1; hardware[0xdff09a] &= ~0x4000
        put(0xdff01c, hardware[0xdff09a], 2)
    elif pc == 0x700800 - 126:
        nesting -= 1
        if nesting < 0: hardware[0xdff09a] |= 0x4000
        put(0xdff01c, hardware[0xdff09a], 2)
    elif pc in mocked:
        if mocked[pc] == 'stop': clock_stops += 1
        uc.reg_write(r.UC_M68K_REG_D0, ticks if mocked[pc] == 'now' else clock_available)
cpu.hook_add(unicorn.UC_HOOK_CODE, clock_hook)
layout = meta['driver_layout']; driver = sym('_nv_driver'); bank = driver + layout['bank']
def field(name, size=2): return get(driver + layout[name], size)
def write(offset, value, size=2):
    put(bank + offset, value, size)
    call('_nv_driver_write', bank, offset)
call('_nv_driver_start')
assert nesting == -1 and field('running') == 1 and field('speech_active') == 0
assert hardware[0xdff096] & 1 == 0  # no continuous idle PCM DMA
sample = 0x605000
cpu.mem_write(sample, bytes(range(256)) * 8)
write(0, sample, 4); write(4, 1000); write(6, 322); write(8, 51)
assert get(0xdff0a0,4) == sample and get(0xdff0a4,2) == 1000
assert get(0xdff0a6,2) == 322 and get(0xdff0a8,2) == 51
call('_nv_driver_control', 0, 0x820f)
assert hardware[0xdff096] & 0x20f == 0x20f
call('_nv_driver_control', 1, 0x8080)
irq()  # genuine native initial latch
assert get(bases[0] + 0x17e2,1) == 255 and field('speech_active') == 0
cpu.mem_write(pcm, bytes(range(256)) * 8)
put(voice+8, 7, 2); put(voice+10, 0, 2); put(voice+12, 0, 2)
put(voice+14, 1001, 2); put(voice+16, 1, 2); put(voice+6, 3, 2)
ticks += 20
call('_nv_driver_service')
assert field('speech_active') == 1 and get(voice+12,2) == 512
assert bytes(cpu.mem_read(allocs[0],256)) == bytes(range(256))
assert get(0xdff0a8,2) == 0 and get(0xdff0a6,2) == 161
# Music keeps updating its latest shadow controls while speech owns Paula 0.
write(0, sample+512,4); write(4, 300); write(6, 428); write(8, 37)
assert get(0xdff0a0,4) in allocs and get(0xdff0a8,2) == 0
ticks += 100
irq()  # initial speech latch, no buffer has physically finished
assert get(0xdff0a8,2) == 64  # unmute only after the DMA latch
others_unchanged()
assert get(voice+20,2) != 7
for _ in range(8):
    ticks += 1600
    irq()
    if get(voice+6,2) == 6: break
assert get(voice+12,2) == 1001 and get(voice+20,2) == 7
assert field('speech_active') == 0
others_unchanged()
assert get(0xdff0a6,2) == 428 and get(0xdff0a8,2) == 37
assert get(0xdff0a0,4) not in allocs
index = (get(driver+16,4) + 1) & ~1
address = get(driver+8,4) + index
remaining = get(driver+12,4) - index
if not remaining: address, remaining = get(driver,4), get(driver+4,4)
assert get(0xdff0a0,4) == address and get(0xdff0a4,2) == remaining//2
before = field('native_events',4)
irq()  # artificial resume latch must not become a macro event
assert field('native_events',4) == before
assert get(0xdff0a0,4) == sample+512 and get(0xdff0a4,2) == 300
assert hardware[0xdff09a] & 0x80 == 0  # no forced reload IRQ storm while idle
events = field('native_events',4)
irq()  # pending but disabled must not be dispatched (distinct MMIO reads)
assert field('native_events',4) == events
# Wrap the source ring; odd final byte must be followed by zero, not stale PCM.
put(voice+8, 8,2); put(voice+12,16380,2); put(voice+14,16389,2)
put(voice+6,3,2); put(voice+16,1,2)
cpu.mem_write(pcm+16380,b'ABCD'); cpu.mem_write(pcm,b'EFGHI')
call('_nv_driver_service')
assert bytes(cpu.mem_read(allocs[0],12)) == b'ABCDEFGHI\0\0\0'
put(voice+10,8,2); call('_nv_driver_service')
assert field('speech_active') == 0
# A newer worker generation must stop queued old DMA during its prefill.
put(voice+8,10,2);put(voice+10,0,2);put(voice+12,0,2);put(voice+14,1024,2)
put(voice+16,0,2);put(voice+6,3,2);call('_nv_driver_service')
assert field('speech_active') == 1
put(voice+8,11,2);put(voice+6,2,2);call('_nv_driver_service')
assert field('speech_active') == 0 and get(voice+6,2) == 2
# Native master stop/reinit does not stop an active speech DMA stream.
put(voice+8,9,2);put(voice+10,0,2);put(voice+12,0,2);put(voice+14,1024,2)
put(voice+16,0,2);put(voice+6,3,2);call('_nv_driver_service')
call('_nv_driver_control',0,0x200)
assert hardware[0xdff096] & 0x201 == 0x201
call('_nv_driver_control',0,0x820f)
assert hardware[0xdff096] & 0x20f == 0x20f
call('_nv_driver_restore',0x700400)
assert get(0x70,4) == sym('_nv_irq')
put(voice+10,9,2);call('_nv_driver_service')
call('_nv_driver_end')
assert get(0x70,4) == 0x700400 and hardware[0xdff096] & 1 == 0
assert clock_stops == 1 and nesting == -1 and len(freed) == 2
others_unchanged()
clock_available = 0
put(control+20,1,4)
before_segments = get(sym('_nv_dialogue_segments'),4)
call('_nv_driver_start')
assert get(control+20,4) == 5 and len(freed) == 4
assert get(0x70,4) == 0x700400 and get(bases[0]+0x1942,4) == 0xdff0a0
put(sym('_nv_dialogue_valid'),1,2)
call('_nv_dialogue_capture'); call('_nv_dialogue_segment'); call('_nv_dialogue_display')
assert cpu.reg_read(r.UC_M68K_REG_D0) == 0
assert get(sym('_nv_dialogue_valid'),2) == 0
assert get(sym('_nv_dialogue_segments'),4) == before_segments
print(json.dumps(dict(compiled_dedicated_driver_pass=True, idle_hardware_dma=True,
    voice_copy_exact=True, odd_ring_wrap=True, physical_tail=True,
    latest_native_restore=True, no_false_resume_event=True,
    master_stop_reinit=True, clock_and_vector_cleanup=True,
    busy_clock_falls_back_to_original_text_without_voice_hold=True,
    actual_amiga_runtime=False)))
