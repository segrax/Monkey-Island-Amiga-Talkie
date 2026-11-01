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
print(json.dumps(dict(pass_=True,signed_pairs=65536,both_speakers=True,gain_rows=65,original_rounding=True)))
