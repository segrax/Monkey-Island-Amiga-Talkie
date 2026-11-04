"""Append the guarded packed-font decoder and preserve the original fallback."""
from pathlib import Path
import json,sys,hashlib,struct
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
P=artifact_dir('font');folder=engine_build()/'module'
image=folder/'Monkey_Talkie_Test';raw=image.read_bytes();meta=json.loads((folder/'module.json').read_text());g=json.loads((P/'generation.json').read_text())
assert hashlib.sha256(raw).hexdigest()==meta['sha256'] and 'engine_packed_font' not in meta
r=HunkReader();assert r.read_file(str(image))==0 and r.build_segments();n=r.hunks[0]['table_size'];code=bytearray(next(h['data']for h in r.hunks if h.get('hunk_no')==0 and'data'in h));W=lambda *v:struct.pack('>'+len(v)*'I',*v)
def relocs(reader):
 out={};section=0
 for h in reader.hunks:
  section=h.get('hunk_no',section)
  if h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():out.setdefault((section,target),set()).update(offsets)
 return out
before=relocs(r);after={k:set(v)for k,v in before.items()};a,b=g['footprint']['start'],g['footprint']['end'];assert code[a:b].hex()==g['footprint']['expected']
assert hashlib.sha256(code[0x16020:0x16124]).hexdigest()==g['original_function_sha256']
removed={(s,t):{o for o in offsets if a<=o<b}for(s,t),offsets in before.items()if s==0};removed={k:v for k,v in removed.items()if v};assert removed=={(0,2):{a+6}},removed
for k,v in removed.items():after[k]-=v
code[a:b]=bytes.fromhex('4ef9')+W(g['entries']['_engine_font2'])+bytes.fromhex('4e714e71');after[(0,n)]={a+2};after[(n,2)]=set(g['global_relocations'])
def encode(groups):
 out=W(1004)
 for target,offsets in sorted(groups.items()):
  if offsets:out+=W(len(offsets),target,*sorted(offsets))
 return out+W(0)
blob=bytearray((P/'font.bin').read_bytes());assert hashlib.sha256(blob).hexdigest()==g['sha256']
blob+=bytes((-len(blob))%4);header=bytearray(raw[:20+4*n]);struct.pack_into('>I',header,8,n+1);struct.pack_into('>I',header,16,n);header+=W(len(blob)//4)
firstend=next(h['hunk_file_offset']for h in r.hunks if h['type_name']=='HUNK_END')
result=header+W(1001,len(code)//4)+code+encode({t:o for(s,t),o in after.items()if s==0})+W(1010)+raw[firstend+4:]+W(1001,len(blob)//4)+blob+encode({2:after[(n,2)]})+W(1010)
temp=folder/'Monkey_Talkie_Test.font-new';temp.write_bytes(result);q=HunkReader();assert q.read_file(str(temp))==0 and q.build_segments();assert relocs(q)==after
sections=lambda r:[h for h in r.hunks if h['type_name']in('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
assert len(sections(q))==len(sections(r))+1
for i,(x,y)in enumerate(zip(sections(r),sections(q))):assert x['alloc_size']==y['alloc_size']and x['type_name']==y['type_name']and y.get('data')==(bytes(code)if i==0 else x.get('data'))
temp.replace(image);meta['sha256']=hashlib.sha256(result).hexdigest()
for name,offset in g['entries'].items():meta['exports'][name]=dict(hunk=n,offset=offset)
meta['engine_patches'].append(dict(address=a,size=b-a,symbol='_engine_font2',jump=True,expected=g['footprint']['expected'],terminal=True))
meta['engine_packed_font']=dict(code_bytes=len(blob),guard=g['guard'],original_fallback=True,global_relocation_count=len(g['global_relocations']),kernel_sha256=g['sha256'])
meta['engine_removed_original_relocations'] += [dict(source_hunk=s,target_hunk=t,offset=off)for(s,t),offsets in removed.items()for off in sorted(offsets)]
(folder/'module.json').write_text(json.dumps(meta,indent=2)+'\n');print(meta['sha256'])
(P/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],patch_footprint_bytes=b-a,existing_allocations_preserved=True,existing_relocations_outside_footprint_preserved=True,removed_original_relocations=[dict(source_hunk=s,target_hunk=t,offset=off)for(s,t),offsets in removed.items()for off in sorted(offsets)],new_global_relocations=len(g['global_relocations']),kernel_sha256=g['sha256']),indent=2)+'\n')
