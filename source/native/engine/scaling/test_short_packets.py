"""Check every encoded run byte against the original renderer."""
from pathlib import Path
here=Path(__file__).resolve().parent
source=(here/'test_kernels.py').read_text()
a=source.index('cases=[]');b=source.index('profiles=[];checks=0',a)
source=source[:a]+"""cases=[]
for opcode in range(256):
 for count in ((opcode&15,) if opcode&15 else (1,16,255,256)):
  for height in sorted(set((1,count,min(256,count+1)))):
   cases.append(dict(opcode=opcode,count=count,width=3,height=height,phase=opcode,sy=128 if opcode&1 else 256,sx=128,resume=0,ccr=opcode&31))
"""+source[b:]
source=source.replace('encoded=stream();','encoded=(bytes([case["opcode"]]) if case["opcode"]&15 else bytes([case["opcode"],case["count"]&255]))*5000;')
source=source.replace("'kernel-validation.json'","'short-packet-validation.json'")
source=source.replace('signed_fullscale_boundaries=True','every_RLE_opcode=True,short_and_extended_column_boundaries=True')
exec(compile(source,str(here/'test_kernels.py'),'exec'))
