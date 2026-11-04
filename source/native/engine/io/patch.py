from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
HERE=Path(__file__).resolve().parent
BUILD=artifact_dir('io')
import hashlib,json,struct,shutil,sys
from amitools.binfmt.hunk.HunkReader import HunkReader
P=BUILD;source=engine_build()/'module';dest=source
raw=(source/'Monkey_Talkie_Test').read_bytes();meta=json.loads((source/'module.json').read_bytes());r=HunkReader();assert r.read_file(str(source/'Monkey_Talkie_Test'))==0 and r.build_segments()
W=lambda *v:struct.pack('>'+len(v)*'I',*v)
n=r.hunks[0]['table_size'];c=bytearray(next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data' in h));expected=bytes(c[0x16d80:0x16d88]);assert expected.hex()=='4e55fffa48e70f30';assert hashlib.sha256(c[0x16d80:0x16dee]).hexdigest()==json.loads((P/'kernel.json').read_text())['original_body_sha256']
c[0x16d80:0x16d88]=bytes.fromhex('4ef9')+W(0)+bytes.fromhex('4e71')
kernel=json.loads((P/'kernel.json').read_text());decode_expected=bytes(c[0x126ac:0x126c0]);assert hashlib.sha256(decode_expected).hexdigest()==kernel['original_decode_sha256']
c[0x126ac:0x126c0]=bytes.fromhex('4eb9')+W(kernel['entries']['_decode_fast'])+bytes.fromhex('4e71')*7
relocs={};section=0
for h in r.hunks:
 section=h.get('hunk_no',section)
 if section==0 and h['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in h['reloc'].items():relocs.setdefault(target,[]).extend(offsets)
assert not any(0x16d80<=off<0x16d88 or 0x126ac<=off<0x126c0 for offsets in relocs.values() for off in offsets)
relocs[n]=[0x16d82,0x126ae]
def encode(groups):
 b=W(1004)
 for target,offsets in sorted(groups.items()):
  if offsets:b+=W(len(offsets),target,*sorted(offsets))
 return b+W(0)
blob=(P/'fast.bin').read_bytes();kernel=json.loads((P/'kernel.json').read_text());hb=20+4*n;header=bytearray(raw[:hb]);struct.pack_into('>I',header,8,n+1);struct.pack_into('>I',header,16,n);header+=W(len(blob)//4)
firstend=next(h['hunk_file_offset'] for h in r.hunks if h['type_name']=='HUNK_END')
assert all(h['type_name'] in ('HUNK_HEADER','HUNK_CODE','HUNK_ABSRELOC32','HUNK_END') for h in r.hunks if h['hunk_file_offset']<=firstend)
result=header+W(1001,len(c)//4)+c+encode(relocs)+W(1010)+raw[firstend+4:]+W(1001,len(blob)//4)+blob+encode({0:kernel['original_code_relocations']})+W(1010)
temporary=dest/'Monkey_Talkie_Test.io-new';temporary.write_bytes(result)
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
assert (0,n) not in expected_relocs and (n,0) not in expected_relocs
expected_relocs[(0,n)]={0x16d82,0x126ae};expected_relocs[(n,0)]=set(kernel['original_code_relocations'])
assert relocation_sets(q)==expected_relocs
temporary.replace(dest/'Monkey_Talkie_Test')
meta['sha256']=hashlib.sha256(result).hexdigest();meta['exports'].update({name:dict(hunk=n,offset=off) for name,off in kernel['entries'].items()});meta['engine_patches'].append(dict(address=0x16d80,size=8,symbol='_fread_fast',jump=True,expected=expected.hex(),terminal=True,continuation=0x16d88))
(dest/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
meta['engine_patches'].append(dict(address=0x126ac,size=20,symbol='_decode_fast',jump=False,expected=decode_expected.hex(),terminal=False,continuation=0x126c0))
meta['engine_buffered_read']=kernel
(dest/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
(P/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],all_existing_allocations_unchanged=True,only_original_read_entry_and_decode_loop_changed=True,new_code_bytes=len(blob)),indent=2)+'\n')
print(meta['sha256'])
