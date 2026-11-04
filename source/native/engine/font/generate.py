"""Generate a guarded two-bit packed-font decoder from the owned original."""
from pathlib import Path
import sys,struct,json,subprocess,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
ROOT=PROJECT_ROOT;OUT=artifact_dir('font')
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
from capstone import Cs,CS_ARCH_M68K,CS_MODE_BIG_ENDIAN,CS_MODE_M68K_000
assert hashlib.sha256((ROOT/'data/original/Monkey_Island').read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
rd=HunkReader();assert rd.read_file(str(ROOT/'data/original/Monkey_Island'))==0 and rd.build_segments()
h=bytearray(next(x['data']for x in rd.hunks if x.get('hunk_no')==0 and'data'in x));cur=None
BASE=0x100000;G=0x200000
for x in rd.hunks:
 if 'hunk_no'in x:cur=x['hunk_no']
 if cur==0 and x['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in x['reloc'].items():
   for off in offsets:struct.pack_into('>I',h,off,(int.from_bytes(h[off:off+4],'big')+[BASE,0x20000,G][target])&0xffffffff)
cs=Cs(CS_ARCH_M68K,CS_MODE_BIG_ENDIAN|CS_MODE_M68K_000)
ins=list(cs.disasm(h[0x16020:0x16124],BASE+0x16020));assert ins[-1].mnemonic=='rts'

def body(prefix,optimized):
 # The guarded eight-bit source counter reloads each byte after four pixels.
 # Rotating before extraction exposes the same next two bits while retaining
 # ordered palette reads, dirty-mask writes and destination writes. The wrapped
 # bits are discarded at the next source load; no source byte is prefetched.

 lines=[]
 replace={0x16064:'move.w $206f3a,d3',0x1606a:'',0x16082:'tst.w d6\n bne.w plain16084',0x160ca:'',0x160cc:'',0x160ce:'',0x160d6:'',0x160e2:'',0x160ec:'move.b #8,d3',0x160f2:'',0x160bc:'rol.b #2,d5',0x160be:'move.b d5,d6',0x160c0:'andi.b #3,d6',0x160c2:'',0x160c4:'',0x160de:'',0x160e0:'',0x160e4:'subq.b #2,d3',0x160f0:''}if optimized else{}
 if prefix=='plain':replace[0x160d2]=''
 for i in ins:
  if prefix=='plain'and i.address<BASE+0x16084:continue
  off=i.address-BASE;op=i.op_str.replace(' ','')
  if i.mnemonic.startswith(('b','db')):
   for target in ins:op=op.replace('$'+format(target.address,'x'),prefix+format(target.address-BASE,'x'))
  lines+=[prefix+format(off,'x')+':']
  if optimized and off==0x160aa:
   lines+=[' cmpi.w #8,$206f58',' bne.w '+prefix+'160aa_generic',' cmpi.b #8,d3',' bne.w '+prefix+'160aa_generic',' bra.w '+prefix+'unroll8',prefix+'160aa_generic:']
  text=replace.get(off,i.mnemonic+' '+op)
  if text:lines+=[' '+text.replace(', ',',').replace('.l,',',')]
 if optimized:
  lines += [prefix+'unroll8:']
  for pixel in range(8):
   skip=prefix+'u_skip'+str(pixel);nxt=prefix+'u_next'+str(pixel)
   lines += [' rol.b #2,d5',' move.b d5,d6',' andi.b #3,d6',' beq.w '+skip]
   if prefix!='plain':lines+=[' or.b d2,(a4,d4.w)']
   lines+=[' move.b (a2,d6.w),(a0)',skip+':',' addq.w #1,a0']
   if pixel%4==3:lines+=[' move.b (a5)+,d5']
   lines+=[' lsr.b #1,d2',' bne.s '+nxt,' move.b #$80,d2',' addq.w #1,d4',nxt+':']
  lines+=[' swap d1',' move.w #$ffff,d1',' swap d1',' bra.w '+prefix+'16106']
 return lines
lines=[' section code,code',' xdef _engine_font2',' xdef _engine_font_original','_engine_font2:',' cmpi.b #2,$206f5f',' bne.w original16020',' cmpi.b #6,$206f60',' bne.w original16020',' cmpi.b #$c0,$206f61',' bne.w original16020',' cmpi.w #8,$206f3a',' bne.w original16020']+body('fast',True)+body('plain',True)+['_engine_font_original:']+body('original',False)
(OUT/'font.s').write_text('\n'.join(lines)+'\n')
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(OUT/'font.o'),str(OUT/'font.s')],check=True)
r=HunkReader();assert r.read_file(str(OUT/'font.o'))==0
assert not any(x.get('ext_ref') or x.get('reloc') for x in r.hunks)
blob=bytearray(next(x['data']for x in r.hunks if x['type_name']=='HUNK_CODE'));entries={e['name']:e['def']for x in r.hunks if x['type_name']=='HUNK_EXT'for e in x['ext_def']}
cs.detail=True;relocs=[]
from capstone import m68k_const as M
for i in cs.disasm(bytes(blob),0):
 for op in i.operands:
  if op.type==M.M68K_OP_MEM and op.address_mode==M.M68K_AM_ABSOLUTE_DATA_LONG:
   v=op.mem.base_reg if False else op.imm
   # Capstone absolute addresses use op.imm; require everyabsolute access isglobalRAM.
   assert G<=v<G+0x8000,(i.mnemonic,i.op_str,hex(v))
   raw=v.to_bytes(4,'big');pos=i.bytes.find(raw);assert pos>=0 and i.bytes.find(raw,pos+1)<0
   relocs.append(i.address+pos);struct.pack_into('>I',blob,i.address+pos,v-G)
(OUT/'font.bin').write_bytes(blob)
import hashlib
meta=dict(entries=entries,code_bytes=len(blob),sha256=hashlib.sha256(blob).hexdigest(),global_relocations=relocs,footprint=dict(start=0x16020,end=0x1602a,expected=h[0x16020:0x1602a].hex()),original_function_sha256=hashlib.sha256(next(x['data']for x in rd.hunks if x.get('hunk_no')==0 and'data'in x)[0x16020:0x16124]).hexdigest())
# Footprint expected is unrelocated originalbytes.
original_h=next(x['data']for x in rd.hunks if x.get('hunk_no')==0 and'data'in x);meta['footprint']['expected']=original_h[0x16020:0x1602a].hex()
# The ten replaced bytes have no alternate entry, including relocation targets.
scan=Cs(CS_ARCH_M68K,CS_MODE_BIG_ENDIAN|CS_MODE_M68K_000);scan.detail=True;scan.skipdata=True
for instruction in scan.disasm(original_h,0):
 if not instruction.id:continue
 for operand in instruction.operands:
  if operand.type==M.M68K_OP_BR_DISP:
   target=instruction.address+2+operand.br_disp.disp
   assert not 0x16020<target<0x1602a,(instruction.address,target)
section=0;sections={x['hunk_no']:x['data']for x in rd.hunks if'data'in x}
for block in rd.hunks:
 section=block.get('hunk_no',section)
 if block['type_name']=='HUNK_ABSRELOC32':
  for off in block['reloc'].get(0,[]):
   target=int.from_bytes(sections[section][off:off+4],'big')
   assert not 0x16020<target<0x1602a,(section,off,target)
meta.update(original_sha256=hashlib.sha256((ROOT/'data/original/Monkey_Island').read_bytes()).hexdigest(),guard=dict(bits_per_pixel=2,shift=6,mask=192,initial_bit_counter=8),inbound_branches_and_pointers_checked=True)
(OUT/'generation.json').write_text(json.dumps(meta,indent=2)+'\n');print(meta)
