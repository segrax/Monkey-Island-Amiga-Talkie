"""Check output reuse after music, speech, DMA and gain transitions."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'))
call('_nv_driver_start');irq()
def pump(n):
 global ticks
 for _ in range(n):ticks+=1000;irq()
writes=[0];side_writes=[0,0]
def written(uc,access,address,size,value,unused):
 if any(p<=address and address+size<=p+256 for p in allocs):writes[0]+=1
 for side in range(2):
  if any(ptr(side,b)<=address and address+size<=ptr(side,b)+256 for b in range(2)):side_writes[side]+=1
hook=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,written)
cases=0
for enabled in (1,2,3):
 call('_nv_driver_control',0,0x20f)
 for c in range(2):
  cpu.mem_write(0x605000+512*c,bytes([40+20*c])*512)
  for off,value,size in ((0,0x605000+512*c,4),(4,256,2),(6,642,2),(8,64,2)):write(c,off,value,size)
 call('_nv_driver_control',0,0x8200|enabled);pump(4)
 for side in range(2):
  for buffer in range(2):assert any(out(side,buffer))==bool(enabled&(1<<side)),(enabled,side,buffer,out(side,buffer)[:12])
 if enabled!=3:
  quiet=1 if enabled==1 else 0;before=side_writes[quiet];pump(4)
  assert side_writes[quiet]==before,'Silent side rewritten while opposite side plays'
 # Silent DMA still advances, but its output becomes reusable after both banks.
 for c in range(2):write(c,8,0)
 pump(4)
 assert all(out(side,buffer)==bytes(256) for side in range(2) for buffer in range(2))
 before=writes[0];pump(4);assert writes[0]==before,'Already-silent buffer rewritten'
 # New speech must overwrite both reusable banks and later leave clean silence.
 call('_nv_driver_control',0,0x200)
 for off,value in ((8,enabled),(10,0),(12,0),(14,256),(16,1),(6,3),(26,64)):put(voice+off,value,2)
 cpu.mem_write(pcm,bytes([80])*256);free=field('active');pump(1)
 assert out(0,free)==out(1,free)==bytes([40])*256
 pump(6)
 assert all(out(side,buffer)==bytes(256) for side in range(2) for buffer in range(2))
 before=writes[0];pump(4);assert writes[0]==before
 cases+=1
cpu.hook_del(hook)
call('_nv_driver_end');call('_nv_driver_start');irq();pump(4)
assert all(out(side,buffer)==bytes(256) for side in range(2) for buffer in range(2))
report=dict(pass_=True,music_channel_masks=cases,music_gain_speech_silence_transitions=True,silent_DMA_retained=True,restart_initialization=True,no_writes_to_already_clean_buffers=True,independent_silent_side_reuse=True)
(BUILD/'idle-zero-cache.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
