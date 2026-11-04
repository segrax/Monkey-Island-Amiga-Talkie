"""Compiled hybrid driver: native DMA, resampling, centered speech and deadlines."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_driver.py').read_text().split("call('_nv_driver_start')",1)[0]

exec(compile(prefix,str(HERE/'test_driver.py'),'exec'))
assert meta['audio_backend']=='hybrid_stereo_mix'
ticks=100;stops=0;nesting=-1
transport_epoch=100;transport_irq_index=0
for off in (-120,-126):cpu.mem_write(0x700800+off,bytes.fromhex('4e75'))
mocked={sym('_nv_clock_start'):'start',sym('_nv_clock_now'):'now',sym('_nv_clock_stop'):'stop'}
if '_nv_clock_now_locked' in meta['exports']:mocked[sym('_nv_clock_now_locked')]='now'
clock_now_addresses={address for address,kind in mocked.items() if kind=='now'}
for a in mocked:cpu.mem_write(a,bytes.fromhex('4e75'))
def clock(uc,pc,size,unused):
 global stops,nesting,ticks,transport_epoch,transport_irq_index
 if pc==0x700800-120:
  nesting+=1;hardware[0xdff09a]&=~0x4000;put(0xdff01c,hardware[0xdff09a],2)
 elif pc==0x700800-126:
  nesting-=1
  if nesting<0:hardware[0xdff09a]|=0x4000
  put(0xdff01c,hardware[0xdff09a],2)
 elif pc in mocked:
  if mocked[pc]=='now' and '_nv_music_owner' in meta['exports'] and get(sym('_nv_music_owner'),2)==2:ticks=(ticks+5)&0xffffffff
  if mocked[pc]=='stop':stops+=1
  if mocked[pc]=='start':transport_epoch=ticks;transport_irq_index=0
  uc.reg_write(r.UC_M68K_REG_D0,ticks if mocked[pc]=='now' else 1)
cpu.hook_add(unicorn.UC_HOOK_CODE,clock)
def no_audio_read(uc,access,address,size,value,unused):
 assert not (0xdff0a0<=address<0xdff0e0),'CPU read from write-only Paula audio register: '+hex(address)
cpu.hook_add(unicorn.UC_HOOK_MEM_READ,no_audio_read)
def output_bounds(uc,access,address,size,value,unused):
 if 0x800000<=address<0x810000:
  assert any(p<=address and address+size<=p+256 for p in allocs),'Write outside allocated stereo output'
cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,output_bounds)
layout=meta['driver_layout'];driver=sym('_nv_driver');bank=sym('_nv_stereo_bank')
def field(n,size=2):return get(driver+layout[n],size)
def ptr(side,b):return get(driver+layout['right' if side else 'buffers']+4*b,4)
def out(side,b):return bytes(cpu.mem_read(ptr(side,b),256))
def write(c,off,value,size=2):
 put(bank+16*c+off,value,size);call('_nv_driver_write',bank+16*c,off)
def dma_irq(latency=0):
 global ticks,transport_irq_index
 # First request primes the paired DMA; subsequent requests occur as the
 # previous bank's last word starts. Clock is integer EClock (5Paula clocks).
 if transport_irq_index:
  ticks=(transport_epoch+((transport_irq_index*256-2)*get(voice+30,2))//5+latency)&0xffffffff
 else:ticks=(transport_epoch+latency)&0xffffffff
 irq();transport_irq_index+=1
# Renderer tests exercise the real READY/service entry rather than assuming
# native startup immediately owns the software transport. Routing tests opt out.
raw_call=call
native_start=globals().get('NATIVE_START',False)
def enter_mixed():
 global ticks,transport_epoch,transport_irq_index
 if '_nv_music_owner' not in meta['exports']:return
 assert get(sym('_nv_music_owner'),2)==1
 saved=bytes(cpu.mem_read(voice,44))
 ticks=(ticks+71001)&0xffffffff
 transport_epoch=ticks;transport_irq_index=0
 for off,value in ((8,65535),(10,0),(12,0),(14,0),(16,1),(6,3)):
  put(voice+off,value,2)
 raw_call('_nv_driver_service')
 assert get(sym('_nv_music_owner'),2)==0
 assert get(voice+12,2)==0 and get(voice+18,2)==65535
 cpu.mem_write(voice,saved)
def call(name,*args):
 raw_call(name,*args)
 if name=='_nv_driver_start' and not native_start:enter_mixed()

# Simulate loud output latches inherited from a previous player/game.
for c in range(4):put(0xdff0a8+16*c,64,2)
call('_nv_driver_start')
assert all(get(0xdff0a8+16*c,2)==0 for c in range(4)), 'Startup left a Paula channel audible'
assert len(allocs)==4 and hardware[0xdff096]&0x20f==0x203
assert all(get(bases[0]+0x1942+4*c,4)==bank+16*c for c in range(4))
for c,value in enumerate((30,60,-15,-6)):
 sample=0x605000+512*c;cpu.mem_write(sample,bytes([value&255])*512)
 write(c,0,sample,4);write(c,4,256);write(c,6,161);write(c,8,64)
assert [get(a,2) for a in (0xdff0c8,0xdff0d8)]==[32,32]
assert get(0xdff0c0,4)==0x605400 and get(0xdff0d0,4)==0x605600
# An unrelated DMA update must not restart either direct hardware channel.
call('_nv_driver_control',0,0x820f)
start=len(writes);call('_nv_driver_control',0,0x8001)
assert not any(int(port,16)==0xdff096 and int(value,16)&12 for port,value in writes[start:])
# Hardware2/3 native completion flags retain original one-shot IRQ handshake.
call('_nv_driver_control',1,0x8780)
hardware[0xdff09c]|=0x600;put(0xdff01e,hardware[0xdff09c],2)
call('_nv_driver_irq')
assert all(get(bases[0]+0x17e2+4*c,1)==255 for c in (2,3))
assert hardware[0xdff09a]&0x600==0
# Real original fourth-channel store is still routed to physical Paula3.
cpu.reg_write(r.UC_M68K_REG_A4,bank+48);cpu.reg_write(r.UC_M68K_REG_D0,0x605600)
cpu.reg_write(r.UC_M68K_REG_A5,bases[0]+0x17e2);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
cpu.emu_start(bases[0]+0xb6a,bases[0]+0xb70,count=20000)
assert get(0xdff0d0,4)==0x605600
dma_irq() # Prime the paired DMA transport before requesting speech.
put(voice+8,7,2);put(voice+10,0,2);put(voice+12,0,2);put(voice+14,511,2)
put(voice+16,1,2);put(voice+6,3,2);put(voice+26,64,2);cpu.mem_write(pcm,bytes([244])*511)
free=field('active');ticks+=100;dma_irq()
assert out(0,free)==bytes([9])*256 and out(1,free)==bytes([24])*256
assert get(voice+12,2)==256
free=field('active');ticks+=100;dma_irq()
assert out(0,free)==bytes([9])*255+bytes([15])
assert out(1,free)==bytes([24])*255+bytes([30])
assert get(voice+6,2)==5 and get(voice+20,2)!=7
ticks+=100;dma_irq();assert get(voice+20,2)!=7
ticks+=100;dma_irq();assert get(voice+20,2)==7
# Song master clear stops both direct channels but keeps speech outputs alive.
call('_nv_driver_control',0,0x200)
assert hardware[0xdff096]&0x20f==0x203
put(voice+8,8,2);put(voice+12,0,2);put(voice+14,256,2);put(voice+16,1,2);put(voice+6,3,2)
cpu.mem_write(pcm,bytes([20])*256);free=field('active');ticks+=100;dma_irq()
assert out(0,free)==out(1,free)==bytes([10])*256
# Full-scale sums remain signed, bounded and identical across speakers.
for gen,value in ((9,127),(10,128)):
 for c in range(2):cpu.mem_write(0x605000+512*c,bytes([value])*512)
 call('_nv_driver_control',0,0x820f)
 put(voice+8,gen,2);put(voice+12,0,2);put(voice+14,256,2);put(voice+6,3,2)
 cpu.mem_write(pcm,bytes([value])*256);free=field('active');ticks+=100;dma_irq()
 assert out(0,free)==out(1,free)==bytes([value])*256
# Cancellation and direct-channel clear do not disturb the other voices.
call('_nv_driver_clear_native_volume',3);assert get(0xdff0d8,2)==0
put(voice+8,11,2);put(voice+10,11,2);put(voice+12,0,2);put(voice+14,100,2);put(voice+6,3,2)
ticks+=100;dma_irq();assert get(voice+6,2)==8 and get(voice+12,2)==100
# Nonconstant samples verify resampling phase and loop reloads, not just levels.
call('_nv_driver_control',0,0x200)
patterns=[]
for c,period in enumerate((322,161)):
 data=bytes((i*(3+5*c)+17*c)&255 for i in range(512));patterns.append(data)
 cpu.mem_write(0x605000+512*c,data);write(c,6,period)
call('_nv_driver_control',0,0x8203)
music_started=ticks
expected_start=transport_epoch*5+(transport_irq_index+1)*256*161-music_started*5
free=field('active');dma_irq()
for c in range(2):
 expected=[]
 for i in range(256):
  index=((expected_start+i*161)//(322 if c==0 else 161))%512
  value=patterns[c][index];value=value if value<128 else value-256
  expected.append((value>>1)&255)
 assert out(c,free)==bytes(expected),'Incorrect variable-pitch phase or loop'
# The deadline counter measures render duration, independently of speech underruns.
now_calls=[0]
def delayed_clock(uc,pc,size,unused):
 if pc in clock_now_addresses:
  now_calls[0]+=1
  if now_calls[0]==3:uc.reg_write(r.UC_M68K_REG_D0,ticks+9000)
prior_late=field('late_buffers',4)
hook=cpu.hook_add(unicorn.UC_HOOK_CODE,delayed_clock)
dma_irq();cpu.hook_del(hook)
if meta.get('render_statistics',True):
 assert now_calls[0]==3 and field('late_buffers',4)==prior_late+1 and field('max_render_ticks',4)>=9000
else:
 assert now_calls[0]==1,'Release IRQ must read the scheduling clock only once'
 assert field('late_buffers',4)==prior_late and field('max_render_ticks',4)==0
call('_nv_driver_end')
assert all(get(0xdff0a8+16*c,2)==0 for c in range(4)), 'Shutdown left a Paula channel audible'
assert len(freed)==4 and stops==1 and nesting==-1
assert get(0x70,4)==0x700400 and hardware[0xdff096]&15==0
assert all(get(bases[0]+0x1942+4*c,4)==0xdff0a0+16*c for c in range(4))
report=dict(compiled_hybrid_pass=True,two_direct_hardware_music_channels=True,
 original_channel23_irq_handshake=True,no_unrelated_native_dma_restarts=True,
 centered_speech_consumed_once=True,odd_tail_waits_for_playback=True,
 master_clear_keeps_speech=True,signed_full_scale_no_wrap=True,cancellation=True,
 no_write_only_audio_register_reads=True,bounded_chip_writes=True,cleanup=True,
 all_four_startup_and_shutdown_volumes_muted=True,
 variable_pitch_waveform_and_loop_phase=True,render_statistics=meta.get('render_statistics',True),render_clock_reads=now_calls[0],hardware_runtime=False,module_sha256=meta['sha256'])
(BUILD/'hybrid-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
