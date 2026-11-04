"""Append private cache draw kernels using the core's actual exported relocations."""
from pathlib import Path
import sys,json,struct,hashlib
root=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(root/'engine'),'D:/Projects/Monkey.Island.Amiga/tools/python']
from paths import artifact_dir
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
build=artifact_dir('scaling');core=artifact_dir('core')
W=lambda *v:struct.pack('>%dI'%len(v),*v)
def read(p):
 r=HunkReader();assert r.read_file(str(p))==0 and r.build_segments();return r
source=core/'Monkey_Talkie_Test';raw=source.read_bytes();r=read(source);n=r.hunks[0]['table_size']
meta=json.loads((core/'module.json').read_text());exports=meta['exports']
cache=read(build/'scaled_kernels.o')
generation=json.loads((build/'generation.json').read_text())
kernel=bytearray((build/'scaled_kernels.bin').read_bytes())
local=generation['entries'];relocs={}
for h in cache.hunks:
 if h['type_name']=='HUNK_EXT':
  for ref in h['ext_ref']:
   assert ref['type_name']=='EXT_ABSREF32'
   dest=exports[ref['name']]
   for off in ref['refs']:
    value=int.from_bytes(kernel[off:off+4],'big')+dest['offset']
    kernel[off:off+4]=W(value);relocs.setdefault(dest['hunk'],[]).append(off)
known={o for offsets in relocs.values()for o in offsets}
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
regions=[];start=0
for lo,hi in generation['embedded_data_ranges']:regions.append((start,lo));start=hi
regions.append((start,len(kernel)))
for lo,hi in regions:
 for ins in cs.disasm(kernel[lo:hi],lo):
  if any(op.address_mode==capstone.m68k_const.M68K_AM_ABSOLUTE_DATA_LONG for op in ins.operands):
   off=ins.address+ins.size-4
   if off in known:continue
   value=int.from_bytes(kernel[off:off+4],'big')
   if value<29312:target=2
   elif value in(0x15956,0x15a06):target=0
   elif value==0x70000000:target=n+1;kernel[off:off+4]=W(0)
   else:raise AssertionError((hex(ins.address),hex(value)))
   relocs.setdefault(target,[]).append(off)
code=bytearray(next(h['data']for h in r.hunks if h.get('hunk_no')==0 and 'data'in h));oldrel={};firstend=None;current=0
for h in r.hunks:
 current=h.get('hunk_no',current)
 if current==0 and h['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in h['reloc'].items():oldrel.setdefault(target,[]).extend(offsets)
 if current==0 and h['type_name']=='HUNK_END':firstend=h['hunk_file_offset'];break
assert code[0x158ee:0x158f8]==bytes.fromhex('48e7fffe2479000059b8')
assert 0x158f4 in oldrel[2];oldrel[2].remove(0x158f4)
code[0x158ee:0x158f8]=bytes.fromhex('4ef9')+W(local['_scaled_one'])+bytes.fromhex('4e714e71');oldrel.setdefault(n,[]).append(0x158f0)
# The two-mask path stays on the existing exact optimized kernel too.
assert code[0x15a14:0x15a1e]==bytes.fromhex('48e7fffe2479000059b8')
assert 0x15a1a in oldrel[2];oldrel[2].remove(0x15a1a)
code[0x15a14:0x15a1e]=bytes.fromhex('4ef9')+W(local['_scaled_two'])+bytes.fromhex('4e714e71');oldrel[n].append(0x15a16)
def reloc(groups):
 out=W(1004)
 for target,offsets in sorted(groups.items()):
  if offsets:out+=W(len(offsets),target,*sorted(offsets))
 return out+W(0)
prefix=(build/'scale_prefix.bin').read_bytes();head=bytearray(raw[:20+4*n]);struct.pack_into('>I',head,8,n+2);struct.pack_into('>I',head,16,n+1)
head+=W(len(kernel)//4,len(prefix)//4)
result=head+W(1001,len(code)//4)+code+reloc(oldrel)+W(1010)+raw[firstend+4:]
result+=W(1001,len(kernel)//4)+kernel+reloc(relocs)+W(1010)
result+=W(1002,len(prefix)//4)+prefix+reloc({n+1:generation['prefix_pointer_offsets']})+W(1010)
out=build/'Monkey_Talkie_Scaled';out.write_bytes(result);check=read(out)
report=dict(sha256=hashlib.sha256(result).hexdigest(),source_sha256=hashlib.sha256(raw).hexdigest(),kernel_hunk=n,prefix_hunk=n+1,kernel_relocations=relocs,cache_bytes=65536,optional_fast_only=True,compiled_draws=True)
(build/'cache-linked.json').write_text(json.dumps(report,indent=2)+'\n')
# Existing downstream components consume this manifest and carry its exports.
meta.update(sha256=report['sha256'],costume_cache=report,scaling_kernel_hunk=n,scaling_prefix_hunk=n+1)
meta['engine_patches']=[dict(address=a,size=10,expected='48e7fffe2479000059b8')for a in(0x158ee,0x15a14)]
meta['engine_removed_original_relocations']=[dict(source_hunk=0,target_hunk=2,offset=o)for o in(0x158f4,0x15a1a)]
meta['original_relocations_retained']=False
meta['original_relocations_outside_engine_patch_footprints_retained']=True
meta['engine_scaled_runs']=dict(kernel_hunk=n,prefix_hunk=n+1,prefix_bytes=len(prefix),table_sha256=generation['table_sha256'],compiled_cache=True)
for name in('_scaled_one','_scaled_two'):meta['exports'][name]=dict(hunk=n,offset=local[name])
(build/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items()if k!='kernel_relocations'},indent=2))
