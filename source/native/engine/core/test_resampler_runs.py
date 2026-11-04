"""Exercise the source-run helper with the independent legacy sample oracle."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
source=(HERE/'test_resampler_boundaries.py').read_text()
source=source.replace("call('_nv_hybrid_channel',", "call('_nv_hybrid_channel_runs',")
source=source.replace("'resampler-boundaries.json'", "'resampler-runs.json'")
exec(compile(source,str(HERE/'test_resampler_boundaries.py'),'exec'))
# The quotient dispatch and bounded initial prefix retain exact fallbacks.
for step in (1,124,161,322,2047):
 for period in sorted(set(min(65536,step*q+d) for q in (2,3,4,5,6,7,8,9) for d in (-1,0,1))):
  for latched in (1,period,65536):
   for remaining in sorted(set((1,step,step+1,9*step,9*step+1,latched))):
    if remaining<=latched:
     check(latched,latched-remaining,period,step,active,reload,len(active)-1)
for period in (381,428,571,642,643,644,856,960,1017,1141,1281):
 for latched in (1,period,65536):
  for elapsed in sorted(set((0,latched//2,latched-1))):
   check(latched,elapsed,period,161,active,reload,len(active)-1)
# Put the last output exactly at a source boundary; the final tail is one byte.
for period in (322,381,428,483,571,642,644,805,856,1017,1141,1281):
 for prefix_count in range(1,10):
  error=(-((255-prefix_count)*161))%period
  if error<161:
   remaining=prefix_count*161-error
   check(65536,65536-remaining,period,161,active,reload,len(active)-1)
# q8 attack/reload boundaries and old latched prefixes from intro periods.
for period in (1288,1351,1357,1362,1448):
 for length in (1,2,16,64,166,512):
  active=bytes(rng.randrange(256) for _ in range(length))
  for loop_length in (1,2,16,64):
   reload=bytes(rng.randrange(256) for _ in range(loop_length))
   for index in sorted(set((0,length-1))):
    for remaining in sorted(set((1,161,162,1288,period))):
     check(65536,65536-remaining,period,161,active,reload,index)
report.update(cases=cases,source_run_quotients_2_through_8=True,counted_complete_runs=True,initial_prefix_and_fallback=True)
(BUILD/'resampler-runs.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
