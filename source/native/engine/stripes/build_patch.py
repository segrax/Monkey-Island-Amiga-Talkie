"""Append the branch-only stripe clone to an explicitly pinned private HUNK image."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import argparse, hashlib, json, struct, sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
W=lambda *n:struct.pack('>%dI'%len(n),*n)
def build(source,output,expected):
 raw=source.read_bytes();assert hashlib.sha256(raw).hexdigest()==expected
 assert source.resolve()!=output.resolve() and not output.exists()
 r=HunkReader();assert r.read_file(str(source))==0 and r.build_segments()
 header=r.hunks[0];n=header['table_size'];assert header['first_hunk']==0 and header['last_hunk']==n-1 and not header['names']
 code=bytearray(next(h['data']for h in r.hunks if h.get('hunk_no')==0 and 'data'in h));generation=json.loads((BUILD / 'generation.json').read_text())
 a=0x4ddc;assert code[a:a+6]==bytes.fromhex('4ef900015190')
 relocs={};section=0;firstend=None
 for h in r.hunks:
  section=h.get('hunk_no',section)
  if section==0 and h['type_name']=='HUNK_ABSRELOC32':
   for target,offs in h['reloc'].items():relocs.setdefault(target,[]).extend(offs)
  if h['type_name']=='HUNK_END' and firstend is None:firstend=h['hunk_file_offset']
 assert a+2 in relocs[0];relocs[0].remove(a+2)
 assert not any(a<=off<a+6 for offs in relocs.values()for off in offs)
 relocs[n]=[a+2];code[a+2:a+6]=W(0)
 def reloc(groups):
  result=W(1004)
  for target,offs in sorted(groups.items()):
   if offs:result+=W(len(offs),target,*sorted(offs))
  return result+W(0)
 kernel=(BUILD / 'stripe.bin').read_bytes();kernel+=bytes((-len(kernel))%4)
 newhead=bytearray(raw[:20+4*n]);struct.pack_into('>I',newhead,8,n+1);struct.pack_into('>I',newhead,16,n);newhead+=W(len(kernel)//4)
 result=newhead+W(1001,len(code)//4)+code+reloc(relocs)+W(1010)+raw[firstend+4:]+W(1001,len(kernel)//4)+kernel+reloc({2:generation['absolute_h2_relocations']})+W(1010)
 output.write_bytes(result)
 q=HunkReader();assert q.read_file(str(output))==0 and q.build_segments()
 olddata=[h for h in r.hunks if 'data'in h];newdata=[h for h in q.hunks if 'data'in h]
 for old,new in zip(olddata,newdata):assert new['data']==(bytes(code)if old['hunk_no']==0 else old['data'])
 report=dict(source_sha256=expected,sha256=hashlib.sha256(result).hexdigest(),kernel_hunk=n,kernel_sha256=generation['kernel_sha256'],hook=dict(address=a,size=6,expected='4ef900015190',changed_operand_offset=a+2,changed_bytes=4),removed_relocations=[dict(source=0,target=0,offset=a+2)],added_relocations=[dict(source=0,target=n,offset=a+2)],original_decoder_body_unchanged=True,no_additional_entry_jump=True,original_data_hunks_unchanged=True,original_relocations_outside_patch_retained=True,runtime_validated=False)
 output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n');return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--expected',required=True);a=p.parse_args();print(json.dumps(build(a.source,a.output,a.expected),indent=2))
