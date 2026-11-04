from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
HERE=Path(__file__).resolve().parent
BUILD=artifact_dir('geometry')
import hashlib,json,struct,shutil,sys
from amitools.binfmt.hunk.HunkReader import HunkReader
P=BUILD;source=engine_build()/'module';dest=source
raw=(source/'Monkey_Talkie_Test').read_bytes();meta=json.loads((source/'module.json').read_bytes());r=HunkReader();assert r.read_file(str(source/'Monkey_Talkie_Test'))==0 and r.build_segments()
W=lambda *v:struct.pack('>'+len(v)*'I',*v)
n=r.hunks[0]['table_size'];c=bytearray(next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h));kernel=json.loads((P/'generation.json').read_text());relocs={};section=0
for h in r.hunks:
 section=h.get('hunk_no',section)
 if section==0 and h['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in h['reloc'].items():relocs.setdefault(target,[]).extend(offsets)
assert n not in relocs
relocs[n]=[]
for v in kernel['loops']:
 a,b=v['start'],v['end'];assert bytes(c[a:b]).hex()==v['expected'];assert not any(a<=off<b for offsets in relocs.values() for off in offsets)
 c[a:b]=bytes.fromhex('4eb9')+W(kernel['entries']['_'+v['name']])+bytes([0x60,b-a-8])+bytes.fromhex('4e71')*((b-a-8)//2);relocs[n].append(a+2)
prefix=meta['engine_scaled_runs']['prefix_hunk'];assert meta['engine_scaled_runs']['prefix_bytes']==133896

def encode(groups):
 b=W(1004)
 for target,offsets in sorted(groups.items()):
  if offsets:b+=W(len(offsets),target,*sorted(offsets))
 return b+W(0)
blob=bytearray((P/'geometry.bin').read_bytes())
for off in kernel['prefix_relocations']:struct.pack_into('>I',blob,off,0)
blob+=bytes((-len(blob))%4)
hb=20+4*n;header=bytearray(raw[:hb]);struct.pack_into('>I',header,8,n+1);struct.pack_into('>I',header,16,n);header+=W(len(blob)//4)
firstend=next(h['hunk_file_offset'] for h in r.hunks if h['type_name']=='HUNK_END')
assert all(h['type_name'] in ('HUNK_HEADER','HUNK_CODE','HUNK_ABSRELOC32','HUNK_END') for h in r.hunks if h['hunk_file_offset']<=firstend)
result=header+W(1001,len(c)//4)+c+encode(relocs)+W(1010)+raw[firstend+4:]+W(1001,len(blob)//4)+blob+encode({prefix:kernel['prefix_relocations']})+W(1010)
temporary=dest/'Monkey_Talkie_Test.geometry-new';temporary.write_bytes(result)
q=HunkReader();assert q.read_file(str(temporary))==0 and q.build_segments()
a=[h for h in r.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')];b=[h for h in q.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
assert len(b)==len(a)+1
for i,(old,new) in enumerate(zip(a,b)):
 assert old['alloc_size']==new['alloc_size'] and old['type_name']==new['type_name']
 assert new.get('data')==(bytes(c) if i==0 else old.get('data'))
def relocation_sets(reader):
 groups={};section=0
 for h in reader.hunks:
  section=h.get('hunk_no',section)
  if h['type_name']=='HUNK_ABSRELOC32':
   for target,offsets in h['reloc'].items():groups.setdefault((section,target),set()).update(offsets)
 return groups
expected_relocs=relocation_sets(r)
assert (0,n) not in expected_relocs and (n,prefix) not in expected_relocs
expected_relocs[(0,n)]=set(relocs[n]);expected_relocs[(n,prefix)]=set(kernel['prefix_relocations'])
assert relocation_sets(q)==expected_relocs
temporary.replace(dest/'Monkey_Talkie_Test')
assert not set(kernel['entries']) & set(meta['exports'])
meta['sha256']=hashlib.sha256(result).hexdigest();meta['exports'].update({name:dict(hunk=n,offset=off) for name,off in kernel['entries'].items()})
for v in kernel['loops']:meta['engine_patches'].append(dict(address=v['start'],size=v['end']-v['start'],symbol='_'+v['name'],jump=False,expected=v['expected'],terminal=False,continuation=v['end']))
meta['engine_geometry_counts']=dict(code_bytes=len(blob),prefix_hunk=prefix,threshold_source_pixels=16)
(dest/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
(P/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],all_existing_allocations_unchanged=True,original_scale_loops_changed=len(kernel['loops']),new_code_bytes=len(blob)),indent=2)+'\n');print(meta['sha256'])
