"""Compare packed speech and its fallback with the previous byte algorithm."""
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
src=HERE/'test_driver.py';ns={'__file__':str(src),'__name__':'packed_speech_fixture'}
exec(compile(src.read_text().split("call('_nv_driver_start')",1)[0],str(src),'exec'),ns)
cpu=ns['cpu'];cpu.mem_map(0x900000,0x10000)
base=0x900100;initial=bytes((i*37+i//3+91)&255 for i in range(2048));cases=0
layouts=[(0,256,512),(0,0,512),(0,2,512),(2,0,512),(0,32,512),(0,256,0),(0,256,2),(2,256,0),(0,256,256),(0,256,258),(0,1,512),(0,256,513)]
for count in (0,1,2,15,31,32,33,34,35,36,37,38,39,40,63,64,65,127,128,255,256):
 for left,right,pcm in layouts:
  outputs=[]
  for entry in ('_nv_hybrid_speech_unity_bytes','_nv_hybrid_speech_unity'):
   cpu.mem_write(base,initial)
   ns['call'](entry,base+left,base+right,base+pcm,ns['sym']('_nv_speech_words')+64*512,count)
   outputs.append(bytes(cpu.mem_read(base,len(initial))))
  assert outputs[0]==outputs[1],(count,left,right,pcm)
  cases+=1
report=dict(pass_=True,cases=cases,aligned_packed_and_odd_fallback=True,output_overlap_and_PCM_aliases=True,all_modulo8_tails=True,previous_byte_algorithm_exact=True)
(ns['BUILD']/'speech-packed.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
