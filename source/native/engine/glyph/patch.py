from pathlib import Path
import sys,os,struct,json,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,engine_build
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
out=engine_build()/'module';image=out/'Monkey_Talkie_Test';raw=image.read_bytes();meta=json.loads((out/'module.json').read_text());assert hashlib.sha256(raw).hexdigest()==meta['sha256']
r=HunkReader();assert r.read_file(str(image))==0 and r.build_segments();n=r.hunks[0]['table_size'];sections=[h for h in r.hunks if h['type_name']in('HUNK_CODE','HUNK_DATA','HUNK_BSS')];data={i:bytearray(h.get('data',b''))for i,h in enumerate(sections)};rel={};cur=0
for h in r.hunks:
 cur=h.get('hunk_no',cur)
 if h['type_name']=='HUNK_ABSRELOC32':
  for target,offs in h['reloc'].items():rel.setdefault((cur,target),set()).update(offs)
def export(name):return meta['exports'][name]['hunk'],meta['exports'][name]['offset']
def patchjump(at,name,expected):
 assert data[0][at:at+6].hex()==expected
 h,o=export(name);data[0][at:at+6]=bytes.fromhex('4ef9')+struct.pack('>I',o);rel.setdefault((0,h),set()).add(at+2)
font_h,font_off=export('_engine_font2');assert data[0][0x16020:0x16026]==bytes.fromhex('4ef9')+struct.pack('>I',font_off)
rel[(0,font_h)].remove(0x16022);h,o=export('_nv_glyph_entry');data[0][0x16022:0x16026]=struct.pack('>I',o);rel.setdefault((0,h),set()).add(0x16022)
h,o=export('_nv_glyph_fallback');assert data[h][o:o+6]==bytes.fromhex('4ef900000000');data[h][o+2:o+6]=struct.pack('>I',font_off);rel.setdefault((h,font_h),set()).add(o+2)
patchjump(0x2508,'_nv_glyph_load_entry','4ced00e0ffec')
patchjump(0xdfd0,'_nv_glyph_scope_entry','4a2c672c670c')
patchjump(0xe150,'_nv_glyph_scope_exit','4cdf089c4e5d')
W=lambda *v:struct.pack('>'+len(v)*'I',*v)
result=bytearray(raw[:20+4*n])
for i,s in enumerate(sections):
 if s['type_name']=='HUNK_BSS':result+=W(1003,s['alloc_size']//4)
 else:result+=W(1001 if s['type_name']=='HUNK_CODE'else 1002,len(data[i])//4)+data[i]
 groups={t:v for(a,t),v in rel.items()if a==i and v}
 if groups:
  result+=W(1004)
  for target,offs in sorted(groups.items()):result+=W(len(offs),target,*sorted(offs))
  result+=W(0)
 result+=W(1010)
image.write_bytes(result);meta['sha256']=hashlib.sha256(result).hexdigest();meta['engine_font_cache']=dict(format=2,capacity=64548,files={'native-font-2.dat':'4b7746140791df2ea1ffd68f7773d5939fe5b0fb30c1625f509c4f5333558a5a','native-font-4.dat':'bcf080edbdd72947f75f935ae23899cc838206a31bab02d30e0b6638366f5a78'},prototype=True);(out/'module.json').write_text(json.dumps(meta,indent=2)+'\n');print('PRIVATE GLYPH',meta['sha256'])
