"""Exercise compiled resampler boundaries against an independent sample oracle."""
from pathlib import Path
import json,random,struct
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_driver.py').read_text().split("call('_nv_driver_start')",1)[0]
exec(compile(prefix,str(HERE/'test_driver.py'),'exec'))
rng=random.Random(83917)
snapshot,row,output=0x604000,0x605200,0x606000
source,loop=0x900000,0x920000
cpu.mem_map(source,0x40000)
cases=0

# Every source read must stay inside the active/reload buffers.
source_ranges=[]

def read_bounds(uc,access,address,size,value,unused):
 if source<=address<source+0x40000:
  assert any(a<=address and address+size<=b for a,b in source_ranges),(hex(address),size,source_ranges)
cpu.hook_add(unicorn.UC_HOOK_MEM_READ,read_bounds)
bss_hunk=meta['exports']['_nv_driver']['hunk']
bss_start=bases[bss_hunk]
bss_bytes=next(h['alloc_size'] for h in reader.hunks if h.get('hunk_no')==bss_hunk and h['type_name']=='HUNK_BSS')
def write_bounds(uc,access,address,size,value,unused):
 assert not (address<bss_start+((bss_bytes+4095)&~4095) and address+size>bss_start),('Renderer changed global state',hex(address),size)
cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write_bounds)


def check(latched,elapsed,period,step,active,reload,index,shared=False):
 global cases,source_ranges
 gain=(17,64)[cases%2]
 table=bytes(((n if n<128 else n-256)*gain//64)&255 for n in range(256))
 cpu.mem_write(row,table);cpu.mem_write(source,active);cpu.mem_write(loop,reload)
 if shared:
  assert active[:min(len(active),len(reload))]==reload[:min(len(active),len(reload))]
  cpu.mem_write(source,active if len(active)>=len(reload) else reload)
 reload_pointer=source if shared else loop
 state=struct.pack('>8I',reload_pointer,len(reload),source,len(active),index,elapsed,period,latched)
 source_ranges=[(source,source+max(len(active),len(reload)))] if shared else [(source,source+len(active)),(loop,loop+len(reload))]
 cpu.mem_write(snapshot,state);cpu.mem_write(output,b'\xa5'*258)
 expected=[];remaining=latched-elapsed;data=active
 for _ in range(256):
  expected.append(table[data[index]])
  remaining-=step
  if remaining<=0:
   advances=(-remaining)//period+1;remaining+=advances*period
   index+=advances
   if index>=len(data):index=(index-len(data))%len(reload);data=reload
 call('_nv_hybrid_channel',snapshot,row,step,output+1)
 assert bytes(cpu.mem_read(output,258))==b'\xa5'+bytes(expected)+b'\xa5',(latched,elapsed,period,step,len(active),len(reload))
 assert bytes(cpu.mem_read(snapshot,32))==state,'Renderer changed the live snapshot'
 cases+=1

active=bytes(rng.randrange(256) for _ in range(14));reload=bytes(rng.randrange(256) for _ in range(6))
for latched in (1,124,161,65535,65536):
 for elapsed in (0,latched-1):
  for period in (1,2,124,161,428,65535,65536):
   for step in (1,124,161,322,65535,65536):
    # Avoid millions of irrelevant one-tick transitions in extreme cases.
    if step>1000 and period<65535:continue
    check(latched,elapsed,period,step,active,reload,len(active)-2)
# Exact DBRA wrap and long-buffer fallback boundaries. Different data patterns
# distinguish the current buffer from a newly latched reload buffer.
for length in (65534,65536,65538,131072):
 for reload_length in (6,65536,131072):
  active=bytes((n*3+17)&255 for n in range(length));reload=bytes((n*7+89)&255 for n in range(reload_length))
  for index in (0,length-2):
   for period,step in ((1,1),(161,322),(65536,161)):
    check(period,period-1,period,step,active,reload,index)
# Exercise batching dispatch and each four-sample span boundary, including
# thresholds whose word representation has its sign bit set.
active=bytes(rng.randrange(256) for _ in range(14));reload=bytes(rng.randrange(256) for _ in range(6))
for step in (124,161,322,10922,10923,16383,16384):
 for period in sorted(set(min(65535,step*k+d) for k in (3,4,7) for d in (-1,0,1))):
  for latched in (period,65536):
   for remaining in sorted(set((1,step,step+1,3*step,3*step+1,4*step,4*step+1,latched))):
    if remaining<=latched:
     check(latched,latched-remaining,period,step,active,reload,len(active)-2)
# Single-transition dispatch: equality must be safe, one tick below must
# retain the repeated-transition loop even with a one-tick latched sample.
for step in (124,161,322):
 for period in (step-1,step,step+1,2*step-1,2*step,2*step+1):
  for latched in (1,period,65536):
   for remaining in sorted(set((1,step,step+1,latched))):
    if remaining<=latched:
     check(latched,latched-remaining,period,step,active,reload,len(active)-2)
# Shared buffers, near misses, and changing active/reload lengths.
for active_len,reload_len in ((1,1),(2,2),(4,4),(8,8),(16,16),(64,64),(256,256),
                              (32768,32768),(65536,65536),(15,15),(17,17),
                              (63,63),(65,65),(16,64),(64,16)):
 backing=bytes(rng.randrange(256) for _ in range(max(active_len,reload_len)))
 active,reload=backing[:active_len],backing[:reload_len]
 for period in (124,161,286,428,642,856,1141,65536):
  for latched in (1,period,65536):
   for index in (0,active_len-1):
    check(latched,latched-1,period,161,active,reload,index,shared=True)
# Equal lengths with different addresses/data must remain ordinary reloads.
for length in (2,16,64):
 active=bytes(rng.randrange(256) for _ in range(length));reload=bytes(rng.randrange(256) for _ in range(length))
 for period in (161,286,642):
  check(period,period-1,period,161,active,reload,length-1)
# The bounded high-note path may consume one or two source samples.
# Exercise both sides of its threshold, repeated one-byte reloads, and a
# first latched sample whose period differs from the subsequent reloads.
for step in (124,161,322,16383):
 half=(step+1)//2
 for period in sorted(set((half-1,half,half+1,step-1,step,step+1))):
  for active_len,reload_len in ((1,2),(2,1),(3,5),(14,6)):
   active=bytes(rng.randrange(256) for _ in range(active_len))
   reload=bytes(rng.randrange(256) for _ in range(reload_len))
   for latched in (1,period,65536):
    for remaining in sorted(set((1,min(step,latched),latched))):
     for index in sorted(set((0,active_len-1))):
      check(latched,latched-remaining,period,step,active,reload,index)
# Exact edges of contiguous-span entry, including its final look-ahead read.
# One-byte loops distinguish a safe span from an accidentally skipped reload.
for active_len in (256,257,258,512,513,514):
 active=bytes(rng.randrange(256) for _ in range(active_len))
 for period in (81,124,160,161,254,322,428,642,856,1141):
  for latched in (1,period,65536):
   for index in (0,1,active_len-1):
    for reload_len in (1,6):
     reload=bytes(rng.randrange(256) for _ in range(reload_len))
     check(latched,latched-1,period,161,active,reload,index)
report=dict(pass_=True,cases=cases,latched_period_65536=True,new_period_65536=True,oversized_output_fallback=True,source_reload_boundaries=True,source_counter_65536_and_131072=True,four_sample_batch_boundaries=True,single_transition_dispatch_boundaries=True,two_transition_dispatch_boundaries=True,contiguous_span_boundaries=True,shared_wave_layouts=True,snapshot_unchanged=True,bounded_output=True)
(BUILD/'resampler-boundaries.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
