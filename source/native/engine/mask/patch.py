"""Retarget the existing terminal mask gateway, preserving its original decoder."""
from pathlib import Path
import sys,hashlib,json,struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
P=artifact_dir('mask');folder=engine_build()/'module';image=folder/'Monkey_Talkie_Test'
raw=image.read_bytes();meta=json.loads((folder/'module.json').read_text());g=json.loads((P/'generation.json').read_text())
assert hashlib.sha256(raw).hexdigest()==meta['sha256'] and 'engine_mask_rle_unroll'not in meta
r=HunkReader();assert r.read_file(str(image))==0 and r.build_segments()
n=r.hunks[0]['table_size'];code=bytearray(next(h['data']for h in r.hunks if h.get('hunk_no')==0 and'data'in h));oldcode=bytes(code)
W=lambda *v:struct.pack('>'+len(v)*'I',*v)
def relocations(reader):
 result={};section=0
 for h in reader.hunks:
  section=h.get('hunk_no',section)
  if h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():result.setdefault((section,target),set()).update(offsets)
 return result
before=relocations(r);after={k:set(v)for k,v in before.items()}
f=g['functions'][0];a,b=f['start'],f['end'];assert(a,b)==(0x4de2,0x4de8) and code[a:b].hex()==f['expected']
assert [off for(s,t),v in before.items()if s==0 for off in v if a<=off<b]==[a+2] and a+2 in before[(0,0)]
code[a+2:b]=W(g['entries']['_engine_mask_rle']);after[(0,0)].remove(a+2);after[(0,n)]={a+2};after[(n,2)]=set(g['global_relocations'])
def encode(groups):
 result=W(1004)
 for target,offsets in sorted(groups.items()):
  if offsets:result+=W(len(offsets),target,*sorted(offsets))
 return result+W(0)
blob=(P/'mask.bin').read_bytes();assert hashlib.sha256(blob).hexdigest()==g['sha256'];blob+=bytes((-len(blob))%4)
header=bytearray(raw[:20+4*n]);struct.pack_into('>I',header,8,n+1);struct.pack_into('>I',header,16,n);header+=W(len(blob)//4)
firstend=next(h['hunk_file_offset']for h in r.hunks if h['type_name']=='HUNK_END')
assert all(h['type_name']in('HUNK_HEADER','HUNK_CODE','HUNK_ABSRELOC32','HUNK_END')for h in r.hunks if h['hunk_file_offset']<=firstend)
result=header+W(1001,len(code)//4)+code+encode({t:v for(s,t),v in after.items()if s==0})+W(1010)+raw[firstend+4:]+W(1001,len(blob)//4)+blob+encode({2:after[(n,2)]})+W(1010)
temp=folder/'Monkey_Talkie_Test.mask-new';temp.write_bytes(result);q=HunkReader();assert q.read_file(str(temp))==0 and q.build_segments();assert relocations(q)==after
old=[h for h in r.hunks if h['type_name']in('HUNK_CODE','HUNK_DATA','HUNK_BSS')];new=[h for h in q.hunks if h['type_name']in('HUNK_CODE','HUNK_DATA','HUNK_BSS')];assert len(new)==len(old)+1
for i,(x,y)in enumerate(zip(old,new)):
 assert x['alloc_size']==y['alloc_size'] and x['type_name']==y['type_name'] and y.get('data')==(bytes(code)if i==0 else x.get('data'))
assert code[:a]==oldcode[:a] and code[b:]==oldcode[b:] and code[0x15338:0x1538e]==oldcode[0x15338:0x1538e]
temp.replace(image);meta['sha256']=hashlib.sha256(result).hexdigest();meta['exports']['_engine_mask_rle']=dict(hunk=n,offset=0)
meta['engine_patches'].append(dict(address=a,size=b-a,symbol='_engine_mask_rle',jump=True,expected=f['expected'],terminal=True))
meta['engine_mask_rle_unroll']=dict(code_bytes=g['code_bytes'],repeat_threshold=8,unroll_bytes=8,global_relocations=g['global_relocations'],original_decoder_retained=True,byte_access_order_preserved=True)
(folder/'module.json').write_text(json.dumps(meta,indent=2)+'\n');(P/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],new_hunk=n,new_code_bytes=len(blob),original_decoder_retained=True,all_unrelated_allocations_and_relocations_preserved=True),indent=2)+'\n');print(meta['sha256'])
