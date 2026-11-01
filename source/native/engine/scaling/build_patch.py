"""Relocate whole scaled-kernel clones in a verified isolated executable."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
from pathlib import Path
import argparse,hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
W=lambda *v:struct.pack('>%dI'%len(v),*v)
def read(p):
 r=HunkReader();assert r.read_file(str(p))==0 and r.build_segments();return r

def build(source,output,expected):
 raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected and source.resolve()!=output.resolve() and not output.exists()
 r=read(source);header=r.hunks[0];n=header['table_size'];assert not header['names'] and header['first_hunk']==0 and header['last_hunk']==n-1
 code=bytearray(next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and h['type_name']=='HUNK_CODE'))
 data=next(h['data'] for h in r.hunks if h.get('hunk_no')==2 and 'data'in h)
 generation=json.loads((BUILD / 'generation.json').read_text());assert hashlib.sha256(data[0x1118:0x1218]).hexdigest()==generation['table_sha256']
 hooks=[(0x158ee,generation['entries']['_scaled_one']),(0x15a14,generation['entries']['_scaled_two'])]
 originals={a:bytes(code[a:a+10]) for a,_ in hooks}
 assert originals[0x158ee]==bytes.fromhex('48e7fffe2479000059b8') and originals[0x15a14]==originals[0x158ee]
 relocs={};current=0;firstend=None
 for h in r.hunks:
  current=h.get('hunk_no',current)
  if current==0 and h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():relocs.setdefault(target,[]).extend(offsets)
  if h['type_name']=='HUNK_END' and firstend is None:firstend=h['hunk_file_offset']
 for a,entry in hooks:
  assert a+6 in relocs[2];relocs[2].remove(a+6)
  assert not any(a<=o<a+10 for offsets in relocs.values() for o in offsets)
  code[a:a+10]=bytes.fromhex('4ef9')+W(entry)+bytes.fromhex('4e714e71');relocs.setdefault(n,[]).append(a+2)
 def reloc_bytes(groups):
  result=W(1004)
  for target,offsets in sorted(groups.items()):
   if offsets:result+=W(len(offsets),target,*sorted(offsets))
  return result+W(0)
 kernel=(BUILD / 'scaled_kernels.bin').read_bytes();kr={2:[],n+1:[]};cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
 for ins in cs.disasm(kernel,0):
  operands=[o for o in ins.operands if o.address_mode==M.M68K_AM_ABSOLUTE_DATA_LONG]
  if operands:
   assert len(operands)==1
   value=int.from_bytes(ins.bytes[-4:],'big')
   if value==0x70000000:kr[n+1].append(ins.address+len(ins.bytes)-4)
   else:
    assert 0<=value<header['hunks'][2]['size'],hex(value);kr[2].append(ins.address+len(ins.bytes)-4)
 assert len(kr[n+1])==4
 kernel=bytearray(kernel)
 for off in kr[n+1]:kernel[off:off+4]=W(0)
 kernel+=bytes((-len(kernel))%4)
 prefix=(BUILD / 'scale_prefix.bin').read_bytes();assert len(prefix)==generation['prefix_bytes']
 hb=20+4*n;newhead=bytearray(raw[:hb]);struct.pack_into('>I',newhead,8,n+2);struct.pack_into('>I',newhead,16,n+1);newhead+=W(len(kernel)//4,0x80000000|len(prefix)//4)
 # H0 has only code plus standard32-bit relocations and END; no metadata is discarded.
 allowed={'HUNK_HEADER','HUNK_CODE','HUNK_ABSRELOC32','HUNK_END'}
 assert all(h['type_name'] in allowed for h in r.hunks if h['hunk_file_offset']<=firstend)
 result=newhead+W(1001,len(code)//4)+code+reloc_bytes(relocs)+W(1010)+raw[firstend+4:]
 result+=W(1001,len(kernel)//4)+kernel+reloc_bytes(kr)+W(1010)
 result+=W(1002,len(prefix)//4)+prefix+reloc_bytes({n+1:generation['prefix_pointer_offsets']})+W(1010)
 output.write_bytes(result);new=read(output)
 olddata=[h for h in r.hunks if 'data'in h];newdata=[h for h in new.hunks if 'data'in h]
 for a,b in zip(olddata,newdata):
  if a['hunk_no']==0:assert b['data']==bytes(code)
  else:assert a['data']==b['data']
 report=dict(source_sha256=expected,sha256=hashlib.sha256(result).hexdigest(),kernel_hunk=n,prefix_hunk=n+1,entries=generation['entries'],hooks=[dict(address=a,size=10,expected=originals[a].hex())for a,_ in hooks],removed_original_relocations=[0x158f4,0x15a1a],kernel_relocations=kr,prefix_bytes=len(prefix),table_sha256=generation['table_sha256'],threshold_source_pixels=9,original_data_unchanged_except_two_detours=True,isolated_prototype=True)
 output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--expected',required=True);a=p.parse_args();print(json.dumps(build(a.source,a.output,a.expected),indent=2))
