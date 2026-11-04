from pathlib import Path
import sys,hashlib,json,struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
P=artifact_dir('memory');folder=engine_build()/'module';image=folder/'Monkey_Talkie_Test'
raw=image.read_bytes();meta=json.loads((folder/'module.json').read_text());g=json.loads((P/'generation.json').read_text())
assert hashlib.sha256(raw).hexdigest()==meta['sha256'] and 'engine_memory_fill' not in meta
r=HunkReader();assert r.read_file(str(image))==0 and r.build_segments()
n=r.hunks[0]['table_size'];code=bytearray(next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h))
W=lambda *v:struct.pack('>'+len(v)*'I',*v)
def relocations(reader):
 out={};section=0
 for h in reader.hunks:
  section=h.get('hunk_no',section)
  if h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():out.setdefault((section,target),set()).update(offsets)
 return out
before=relocations(r);after=dict(before);assert (0,n) not in after;after[(0,n)]=set()
for f in g['functions']:
 a,b=f['start'],f['end'];assert code[a:b].hex()==f['expected'] and b-a==8
 assert not any(a<=off<b for (source,target),offsets in before.items() if source==0 for off in offsets)
 code[a:b]=bytes.fromhex('4ef9')+W(g['entries'][f['name']])+bytes.fromhex('4e71');after[(0,n)].add(a+2)
def encode(groups):
 out=W(1004)
 for target,offsets in sorted(groups.items()):
  if offsets:out+=W(len(offsets),target,*sorted(offsets))
 return out+W(0)
blob=(P/'memory.bin').read_bytes();assert hashlib.sha256(blob).hexdigest()==g['sha256'];blob+=bytes((-len(blob))%4)
header=bytearray(raw[:20+4*n]);struct.pack_into('>I',header,8,n+1);struct.pack_into('>I',header,16,n);header+=W(len(blob)//4)
firstend=next(h['hunk_file_offset'] for h in r.hunks if h['type_name']=='HUNK_END')
assert all(h['type_name'] in ('HUNK_HEADER','HUNK_CODE','HUNK_ABSRELOC32','HUNK_END') for h in r.hunks if h['hunk_file_offset']<=firstend)
result=header+W(1001,len(code)//4)+code+encode({t:o for (s,t),o in after.items() if s==0})+W(1010)+raw[firstend+4:]+W(1001,len(blob)//4)+blob+W(1010)
temp=folder/'Monkey_Talkie_Test.memory-new';temp.write_bytes(result)
q=HunkReader();assert q.read_file(str(temp))==0 and q.build_segments();assert relocations(q)==after
sections=lambda reader:[h for h in reader.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
old,new=sections(r),sections(q);assert len(new)==len(old)+1
for i,(x,y) in enumerate(zip(old,new)):
 assert x['alloc_size']==y['alloc_size'] and x['type_name']==y['type_name']
 assert y.get('data')==(bytes(code) if i==0 else x.get('data'))
temp.replace(image);meta['sha256']=hashlib.sha256(result).hexdigest()
for f in g['functions']:
 a,b=f['start'],f['end'];name=f['name'];assert name not in meta['exports']
 meta['exports'][name]=dict(hunk=n,offset=g['entries'][name])
 meta['engine_patches'].append(dict(address=a,size=b-a,symbol=name,jump=True,expected=f['expected'],terminal=True))
meta['engine_memory_fill']=dict(code_bytes=g['entries']['_engine_copy'],threshold_bytes=16,unaligned_leading_byte=True)
meta['engine_memory_copy']=dict(code_bytes=len(blob)-g['entries']['_engine_copy'],threshold_bytes=16,close_forward_overlap_retains_byte_copy=True)
(folder/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
(P/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],existing_allocations_and_relocations_preserved=True,new_code_bytes=len(blob)),indent=2)+'\n')
print(meta['sha256'])
