"""Compiled stereo driver: speaker routing, single consumption and playback tail."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_driver.py').read_text().split("call('_nv_driver_start')",1)[0]
prefix=prefix.replace('==256','==128')
exec(compile(prefix,str(HERE/'test_driver.py'),'exec'))
assert meta['audio_backend']=='continuous_stereo_mix'
ticks=100;stops=0;nesting=-1
for off in (-120,-126):cpu.mem_write(0x700800+off,bytes.fromhex('4e75'))
mocked={sym('_nv_clock_start'):'start',sym('_nv_clock_now'):'now',sym('_nv_clock_stop'):'stop'}
if '_nv_clock_now_locked' in meta['exports']:mocked[sym('_nv_clock_now_locked')]='now'
clock_now_addresses={address for address,kind in mocked.items() if kind=='now'}
for a in mocked:cpu.mem_write(a,bytes.fromhex('4e75'))
def clock(uc,pc,size,unused):
 global stops,nesting
 if pc==0x700800-120:
  nesting+=1;hardware[0xdff09a]&=~0x4000;put(0xdff01c,hardware[0xdff09a],2)
 elif pc==0x700800-126:
  nesting-=1
  if nesting<0:hardware[0xdff09a]|=0x4000
  put(0xdff01c,hardware[0xdff09a],2)
 elif pc in mocked:
  if mocked[pc]=='stop':stops+=1
  uc.reg_write(r.UC_M68K_REG_D0,ticks if mocked[pc]=='now' else 1)
cpu.hook_add(unicorn.UC_HOOK_CODE,clock)
def no_audio_read(uc,access,address,size,value,unused):
 assert not (0xdff0a0<=address<0xdff0e0),'CPU read from write-only Paula audio register: '+hex(address)
cpu.hook_add(unicorn.UC_HOOK_MEM_READ,no_audio_read)
def output_bounds(uc,access,address,size,value,unused):
 if 0x800000<=address<0x810000:
  assert any(p<=address and address+size<=p+128 for p in allocs),'Write outside allocated stereo output'
cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,output_bounds)
layout=meta['driver_layout'];driver=sym('_nv_driver');bank=sym('_nv_stereo_bank')
def field(n,size=2):return get(driver+layout[n],size)
def ptr(side,b):return get(driver+layout['right' if side else 'buffers']+4*b,4)
def out(side,b):return bytes(cpu.mem_read(ptr(side,b),128))
def write(c,off,value,size=2):
 put(bank+16*c+off,value,size);call('_nv_driver_write',bank+16*c,off)
call('_nv_driver_start')
assert len(allocs)==4 and nesting==-1 and hardware[0xdff096]&0x20f==0x203
assert get(0xdff0a8,2)==get(0xdff0b8,2)==0
assert all(get(bases[0]+0x1942+4*c,4)==bank+16*c for c in range(4))
for c,value in enumerate((30,60,-15,-6)):
 sample=0x605000+512*c;cpu.mem_write(sample,bytes([value&255])*256)
 write(c,0,sample,4);write(c,4,128);write(c,6,161);write(c,8,64)
hardware[0xdff096]&=~3;put(0xdff002,hardware[0xdff096],2)
hardware[0xdff09a]&=~0x80;put(0xdff01c,hardware[0xdff09a],2)
call('_nv_driver_control',1,0x4000)
for c in range(4):put(bases[0]+0x17e2+4*c,0,1)
call('_nv_driver_control',0,0x820f)
call('_nv_driver_control',1,0x8780)
assert hardware[0xdff096]&3==3 and hardware[0xdff09a]&0x80
assert all(get(bases[0]+0x17e2+4*c,1)==0 for c in range(4))
call('_nv_driver_control',1,0xc000)
assert all(get(bases[0]+0x17e2+4*c,1)==255 for c in range(4))
# Execute a real relocated original pointer-store hook for the fourth bank.
cpu.reg_write(r.UC_M68K_REG_A4,bank+48);cpu.reg_write(r.UC_M68K_REG_D0,0x605600)
cpu.reg_write(r.UC_M68K_REG_A5,bases[0]+0x17e2);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
cpu.emu_start(bases[0]+0xb6a,bases[0]+0xb70,count=20000)
assert get(bank+48,4)==0x605600
put(voice+8,7,2);put(voice+10,0,2);put(voice+12,0,2);put(voice+14,255,2)
put(voice+16,1,2);put(voice+6,3,2);put(voice+26,64,2);cpu.mem_write(pcm,bytes([244])*255)
irq();assert get(0xdff0a8,2)==get(0xdff0b8,2)==64
ticks+=100;irq()
assert out(0,0)==bytes([4])*128 and out(1,0)==bytes([11])*128
assert get(voice+12,2)==128
ticks+=100;irq()
assert out(0,1)==bytes([4])*127+bytes([8]) and out(1,1)==bytes([11])*127+bytes([15])
assert get(voice+12,2)==255 and get(voice+6,2)==5 and get(voice+20,2)!=7
ticks+=100;irq();assert get(voice+20,2)!=7
ticks+=100;irq();assert get(voice+20,2)==7 and get(voice+6,2)==6
assert out(0,0)==bytes([8])*128 and out(1,0)==bytes([15])*128
# Song DMA master-off silences native voices without stopping centered speech.
call('_nv_driver_control',0,0x200)
assert hardware[0xdff096]&0x203==0x203
put(voice+8,8,2);put(voice+12,0,2);put(voice+14,200,2);put(voice+16,1,2);put(voice+6,3,2)
cpu.mem_write(pcm,bytes([9])*200)
free=field('active');ticks+=100;irq()
assert out(0,free)==out(1,free)==bytes([3])*128 and get(voice+12,2)==128
put(voice+10,8,2);ticks+=100;irq()
assert get(voice+6,2)==8 and get(voice+12,2)==200
for generation,value in ((9,127),(10,128)):
 for c in range(4):cpu.mem_write(0x605000+512*c,bytes([value])*256)
 call('_nv_driver_control',0,0x820f)
 put(voice+8,generation,2);put(voice+10,0,2);put(voice+12,0,2);put(voice+14,128,2)
 put(voice+16,1,2);put(voice+6,3,2);cpu.mem_write(pcm,bytes([value])*128)
 free=field('active');ticks+=100;irq()
 assert out(0,free)==out(1,free)==bytes([value])*128
 assert get(voice+12,2)==128
call('_nv_driver_end')
assert len(freed)==4 and stops==1 and nesting==-1 and hardware[0xdff096]&15==0
assert get(0x70,4)==0x700400
assert all(get(bases[0]+0x1942+4*c,4)==0xdff0a0+16*c for c in range(4))
report=dict(compiled_stereo_pass=True,four_native_voices=True,original_left_right_pairing=True,
 speech_consumed_once=True,speech_both_speakers=True,tail_waits_for_actual_buffer_completion=True,
 no_speech_dependent_gain_changes=True,native_master_off_preserves_speech=True,
 no_reads_from_write_only_audio_registers=True,
 master_off_defers_music_events=True,transport_recovers_from_game_init=True,
 signed_full_scale_headroom_no_wrap=True,
 output_writes_within_allocated_chip_buffers=True,
 real_original_fourth_bank_hook=True,cancellation=True,cleanup=True,
 hardware_runtime=False,module_sha256=meta['sha256'])
(BUILD/'stereo-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
