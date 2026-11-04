"""Exhaust signed music/speech pairs through the compiled 68000 mixer."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'))
call('_nv_driver_start')
signed=lambda n:n if n<128 else n-256
for gain in range(65):
 expected=[signed(n)*gain//64 for n in range(256)]
 assert bytes(cpu.mem_read(sym('_nv_amplitude')+gain*256,256))==bytes(v&255 for v in expected)
 assert bytes(cpu.mem_read(sym('_nv_half_amplitude')+gain*256,256))==bytes((v>>1)&255 for v in expected)
 assert bytes(cpu.mem_read(sym('_nv_speech_words')+gain*512,512))==b''.join(bytes([v&255,0]) for v in expected)
left,right=ptr(0,0),ptr(1,0)
for speech in range(256):
 cpu.mem_write(left,bytes(range(256)));cpu.mem_write(right,bytes(reversed(range(256))))
 cpu.mem_write(pcm,bytes([speech])*256)
 call('_nv_hybrid_speech',left,right,pcm,sym('_nv_speech_words')+64*512,256)
 expected=bytes(((signed(music)+signed(speech))>>1)&255 for music in range(256))
 assert bytes(cpu.mem_read(left,256))==expected,speech
 assert bytes(cpu.mem_read(right,256))==expected[::-1],speech
# The unrolled loop must consume exact byte counts at either alignment.
# Exercise every possible buffer tail and reject reads beyond that tail.
allowed=None
def pcm_bounds(uc,access,address,size,value,unused):
 if pcm<=address<pcm+16384:
  assert allowed[0]<=address and address+size<=allowed[1],(address,size,allowed)
hook=cpu.hook_add(unicorn.UC_HOOK_MEM_READ,pcm_bounds)
tails=0
for alignment in (0,1):
 for gain in (0,1,32,64):
  samples=bytes((n*37+19)&255 for n in range(256))
  for count in range(257):
   initial_left=bytes(range(256));initial_right=bytes(reversed(range(256)))
   cpu.mem_write(left,initial_left);cpu.mem_write(right,initial_right)
   cpu.mem_write(pcm+alignment,samples);allowed=(pcm+alignment,pcm+alignment+count)
   call('_nv_hybrid_speech',left,right,pcm+alignment,sym('_nv_speech_words')+gain*512,count)
   for output,initial in ((left,initial_left),(right,initial_right)):
    expected=bytes(((signed(initial[n])+signed(samples[n])*gain//64)>>1)&255 for n in range(count))+initial[count:]
    assert bytes(cpu.mem_read(output,256))==expected,(alignment,gain,count)
   # Direct speech must overwrite stale buffers, preserving bytes after its tail.
   cpu.mem_write(left,initial_left);cpu.mem_write(right,initial_right)
   call('_nv_hybrid_speech_only',left,right,pcm+alignment,sym('_nv_half_amplitude')+gain*256,count)
   expected=bytes(((signed(samples[n])*gain//64)>>1)&255 for n in range(count))
   assert bytes(cpu.mem_read(left,256))==expected+initial_left[count:],(alignment,gain,count)
   assert bytes(cpu.mem_read(right,256))==expected+initial_right[count:],(alignment,gain,count)
   tails+=1
for gain in range(65):
 allowed=(pcm,pcm+256);cpu.mem_write(pcm,bytes(range(256)))
 call('_nv_hybrid_speech_only',left,right,pcm,sym('_nv_half_amplitude')+gain*256,256)
 expected=bytes(((signed(n)*gain//64)>>1)&255 for n in range(256))
 assert bytes(cpu.mem_read(left,256))==bytes(cpu.mem_read(right,256))==expected,gain
cpu.hook_del(hook)
print(json.dumps(dict(pass_=True,signed_pairs=65536,both_speakers=True,gain_rows=65,original_rounding=True,all_tail_lengths_both_alignments=tails,direct_stereo_speech=True)))
