"""Generate exact original instruction clones with transparent source-run batching."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json,struct,sys,subprocess
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
ORIGINAL=ROOT/'data/original/Monkey_Island'
r=HunkReader();assert r.read_file(str(ORIGINAL))==0 and r.build_segments()
hunks={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h};code=hunks[0];table=hunks[2][0x1118:0x1218]
assert hashlib.sha256(table).hexdigest()=='4848f9b3128d7bd5f591097002c691fb997da40168f12035ec5f80a9f75696e8'
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
out=[' section text,code',' xdef _scaled_one',' xdef _scaled_two']
kernels=[(0x158ee,0x15a14,0x15972,0x15960,0x1595c,0x15a04,0x15a06,'one',False),(0x15a14,0x15b54,0x15aa0,0x15a8e,0x15a8a,0x15b44,0x15b46,'two',True)]
for start,end,pixel,decode,resume,wraplast,dbra,name,two in kernels:
 end_pixel = 0x15adc if two else 0x159a4
 color_test = 0x15ab2 if two else 0x15984
 label=lambda a:f'L{name}_{a:x}'
 out.append('_scaled_'+name+':')
 for ins in cs.disasm(code[start:end],start):
  out.append(label(ins.address)+':')
  if ins.address==pixel:
   # Fresh decoder falls through dispatcher; initial resume is retargeted here.
   out+=['dispatch_'+name+':',' tst.w d2',' bne opaque_'+name,' cmpi.w #8,d3',' blo .short_'+name,' moveq #0,d2',' move.b d5,d2',' subq.b #1,d2',' cmp.w d3,d2',' bls.s .bounded_'+name,' move.w d3,d2','.bounded_'+name+':',' cmpi.w #8,d2',' blo .short_'+name,
    ' move.w $59ae.l,d0',' ble .none_'+name,' cmpi.w #256,d0',' bge .all_'+name,
    ' lsl.w #2,d0',' lea $70000000.l,a0',' movea.l (a0,d0.w),a0',' moveq #0,d0',' move.b d1,d0',' add.w d0,d0',' adda.w d0,a0',' move.w d2,d0',' add.w d0,d0',' move.w (a0,d0.w),d0',' sub.w (a0),d0',' bra.s .advance_'+name,
    '.all_'+name+':',' move.w d2,d0',' bra.s .advance_'+name,'.none_'+name+':',' moveq #0,d0','.advance_'+name+':',' add.w d0,d7',' mulu.w #40,d0',' adda.l d0,a3']
   if two:out+=[' adda.l d0,a4']
   out+=[' lsl.l #3,d0',' adda.l d0,a1',' sub.w d2,d3',' sub.b d2,d5',' add.b d2,d1',' lea $5cdb.l,a0','.short_'+name+':',' moveq #0,d2',label(pixel)+'_pixel:']
  if pixel <= ins.address < color_test:
   if ins.address == pixel:
    out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+label(end_pixel)]
   continue
  if ins.address in (0x15924,0x15a4a):
   out += [' move.w $59ae.l,d0',' ble .accept_none_'+name,
    ' cmpi.w #256,d0',' blt .accept_lookup_'+name,' move.w #256,d0',
    ' bra .accept_lookup_'+name,'.accept_none_'+name+':',' moveq #0,d0',
    '.accept_lookup_'+name+':',' lsl.w #2,d0',' lea $70000000.l,a6',
    ' adda.l #263680,a6',' movea.l (a6,d0.w),a6']
   continue
  if ins.address in (0x159c8,0x15b00):
   out += [' lea $1118.l,a0',' move.b (a0,d1.w),d0',' lea $5cdb.l,a0']
   continue
  # Only transparent runs reach the shared loop after dispatch.
  color_test, advance_pixel = ((0x15ab2,0x15ace) if two else (0x15984,0x1599a))
  if color_test <= ins.address < advance_pixel:
   continue
  # Branches must follow labels after insertion, not original encoded displacements.
  op=ins.operands[-1] if ins.operands else None
  if op is not None and op.type==M.M68K_OP_BR_DISP:
   target=ins.address+2+op.br_disp.disp
   if ins.address==resume:targetlabel='dispatch_'+name
   elif target==pixel:targetlabel=label(pixel)+'_pixel'
   else:targetlabel=label(target)
   args=('d3,' if ins.mnemonic.startswith('db') else '')+targetlabel
   mnemonic=ins.mnemonic.split('.')[0]
   out.append(' '+mnemonic+' '+args)
  else:out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2)))
  if ins.address==wraplast:
   out+=[' dbra d3,dispatch_'+name,' bra.w '+label(decode)]
 # Opaque runs use an equivalent pixel loop without the repeated color test.
 out.append('opaque_'+name+':')
 end_pixel, column_wrap = ((0x15adc,0x15ae2) if two else (0x159a4,0x159aa))
 opaque_label=lambda a:f'O{name}_{a:x}'
 for ins in cs.disasm(code[pixel:end_pixel+2],pixel):
  out.append(opaque_label(ins.address)+':')
  if pixel <= ins.address < color_test:
   if ins.address == pixel:
    out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+opaque_label(end_pixel)]
   continue
  if ins.address in (color_test,color_test+2):
   continue
  op=ins.operands[-1] if ins.operands else None
  if op is not None and op.type==M.M68K_OP_BR_DISP:
   target=ins.address+2+op.br_disp.disp
   out.append(' '+ins.mnemonic.split('.')[0]+' '+opaque_label(target))
  else:
   out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2)))
 out+=[' bne opaque_continue_'+name,' bra '+label(column_wrap),
       'opaque_continue_'+name+':',' dbra d3,opaque_'+name,' bra '+label(decode)]
(BUILD / 'scaled_kernels.s').write_text('\n'.join(out)+'\n')
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(BUILD / 'scaled_kernels.o'),str(BUILD / 'scaled_kernels.s')],check=True)
reader=HunkReader();assert reader.read_file(str(BUILD / 'scaled_kernels.o'))==0
print([(h['type_name'],list(h.keys())) for h in reader.hunks])
# Standalone object has one code section and exported entries.
obj=next(h['data'] for h in reader.hunks if h['type_name']=='HUNK_CODE');entries={}
for h in reader.hunks:
 if h['type_name']=='HUNK_EXT':
  for x in h['ext_def']:entries[x['name']]=x.get('def',x.get('value'))
(BUILD / 'scaled_kernels.bin').write_bytes(obj)
# Prefix pointers are relative to their own data hunk; loader relocation adds base.
prefix=bytearray(1024)
for scale in range(256):
 struct.pack_into('>I',prefix,scale*4,len(prefix));n=0;prefix+=struct.pack('>H',0)
 for index in range(512):
  n+=table[index&255]<scale;prefix+=struct.pack('>H',n)
accept_pointers=len(prefix)
prefix += bytes(257*4)
for scale in range(257):
 struct.pack_into('>I',prefix,accept_pointers+scale*4,len(prefix)+1)
 prefix += bytes([table[255]<scale])+bytes(value<scale for value in table)
prefix += bytes((-len(prefix))%4)
pointer_offsets=list(range(0,1024,4))+list(range(accept_pointers,accept_pointers+257*4,4))
(BUILD / 'scale_prefix.bin').write_bytes(prefix)
(BUILD / 'generation.json').write_text(json.dumps(dict(entries=entries,code_bytes=len(obj),prefix_bytes=len(prefix),table_sha256=hashlib.sha256(table).hexdigest(),accept_pointer_offset=accept_pointers,accept_rows=257,accept_row_bytes=257,prefix_pointer_offsets=pointer_offsets),indent=2)+'\n')
print((BUILD / 'generation.json').read_text())
