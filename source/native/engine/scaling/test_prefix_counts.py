"""Check every scale/phase/run against pixel-by-pixel scaling decisions."""
from pathlib import Path
import json
import struct
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent))
from paths import artifact_dir
BUILD=artifact_dir('scaling')
sys.path.insert(0,str(HERE.parents[1]/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader

reader=HunkReader()
assert reader.read_file(str(HERE.parents[1]/'data/original/Monkey_Island'))==0 and reader.build_segments()
original=next(h['data'] for h in reader.hunks if h.get('hunk_no')==2 and 'data' in h)
scale_table=original[0x1118:0x1218]
prefix=(BUILD/'scale_prefix.bin').read_bytes()
metadata=json.loads((BUILD/'generation.json').read_text())
assert metadata['prefix_counter_bits']==8 and metadata['prefix_max_batch']==255
assert metadata['prefix_row_bytes']==257
assert metadata['accept_pointer_offset']==66816
assert len(prefix)==133896
cases=0
for scale in range(256):
 base=struct.unpack_from('>I',prefix,4*scale)[0]
 for phase in range(256):
  accepted=0
  for run in range(256):
   if run:accepted+=scale_table[(phase+run-1)&255]<scale
   end=phase+run
   count=prefix[base+(end&255)]-prefix[base+phase]
   if end>=256:count+=prefix[base+256]
   assert count&255==accepted,(scale,phase,run)
   cases+=1
# The separately indexed acceptance rows retain their preceding-phase sentinel.
scale_count=metadata['accept_rows']
for scale in range(scale_count):
 row=struct.unpack_from('>I',prefix,metadata['accept_pointer_offset']+4*scale)[0]
 assert prefix[row-1]==(scale_table[255]<scale)
 assert prefix[row:row+256]==bytes(value<scale for value in scale_table)
result=dict(cases=cases,all_scales_phases_and_byte_run_lengths=True,prefix_bytes=len(prefix),previous_prefix_bytes=199432,bytes_saved=65536)
(BUILD/'prefix-count-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
