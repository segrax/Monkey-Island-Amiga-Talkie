"""Generate exact original instruction clones with transparent source-run batching."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json,struct,sys,subprocess,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
ORIGINAL=ROOT/'data/original/Monkey_Island'
r=HunkReader();assert r.read_file(str(ORIGINAL))==0 and r.build_segments()
hunks={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h};code=hunks[0];table=hunks[2][0x1118:0x1218]
assert hashlib.sha256(table).hexdigest()=='4848f9b3128d7bd5f591097002c691fb997da40168f12035ec5f80a9f75696e8'
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
# Each transparent batch is bounded by a byte-sized run counter minus one:
# at most 255 source pixels. Prefix differences therefore fit in a byte,
# even when the cumulative counter wraps through 256 or the phase wraps.
# One period plus its total replaces the duplicated second period; a wrapped
# lookup adds row[256] before subtracting the starting prefix, modulo 256.
PREFIX_PHASES=256
PREFIX_ROW_BYTES=257
ACCEPT_POINTER_OFFSET=PREFIX_PHASES*4+PREFIX_PHASES*PREFIX_ROW_BYTES
# Prove the entire source-sized rectangle is on screen and its mask is clear.
# Scaling accepts at most one destination pixel per source pixel, so this
# conservative rectangle bounds every output for either scale direction.
# Scan aligned longword-sized supersets; masked neighbours only cause fallback.
# Reject mask/output overlap because drawing could otherwise invalidate the proof.
GUARD=[' moveq #0,d0',' move.b $6ded.l,d0',' bne .height_one',' move.w #256,d0','.height_one:',
 ' move.w $6df4.l,d1',' cmp.w $6df6.l,d1',' bne normal_one_body',' add.w d1,d0',' bcs normal_one_body',' cmp.w $6df8.l,d0',' bhi normal_one_body',' cmpi.w #200,$6df8.l',' bhi normal_one_body',
 ' move.w $6df2.l,d1',' cmpi.w #319,d1',' bhi normal_one_body',' move.w d1,d2',
 ' moveq #0,d0',' move.b $6dec.l,d0',' bne .width_one',' move.w #256,d0','.width_one:', ' subq.w #1,d0',
 ' cmpi.w #1,$6dfc.l',' beq .right_one',' cmpi.w #-1,$6dfc.l',' bne normal_one_body',
 ' sub.w d0,d2',' bmi normal_one_body',' bra .bounds_one','.right_one:',' add.w d0,d2',' cmpi.w #319,d2',' bhi normal_one_body',
 '.bounds_one:',' cmp.w d2,d1',' bls .ordered_one',' exg d1,d2','.ordered_one:',' lsr.w #5,d1',' lsr.w #5,d2',' sub.w d1,d2',' lsl.w #2,d1',
 ' movea.l $6de0.l,a0',' move.l a0,d0',' btst #0,d0',' bne normal_one_body',' move.w $6df2.l,d0',' lsr.w #3,d0',' lea (a0,d0.w),a1',' cmpa.l $5c22.l,a1',' bne normal_one_body',
 ' move.l $5c16.l,d3',' cmpi.l #256,d3',' blo normal_one_body',' move.l d3,d4',' subi.l #256,d4',' addi.l #82176,d3',' bcs normal_one_body',
 ' move.l a0,d0',' addi.l #10280,d0',' bcs normal_one_body',' cmp.l d4,d0',' bls .separate_one',' cmpa.l d3,a0',' bcs normal_one_body','.separate_one:',
 ' adda.w d1,a0',' moveq #0,d1',' move.b $6ded.l,d1',' bne .rows_one',' move.w #256,d1','.rows_one:',' subq.w #1,d1',
 '.row_one:',' move.w d2,d0',' movea.l a0,a1','.mask_one:',' tst.l (a1)+',' bne visible_one_body',' dbra d0,.mask_one',
 ' adda.w #40,a0',' dbra d1,.row_one',' bra clear_one_body','normal_one_body:']

CACHE = '--costume-cache' in sys.argv

def record_enabled(name):return CACHE and name in ('clear_one','visible_one')
def record_fallback(tag,destination):
 if destination==0x15956:
  name='visible_one' if 'visible_one' in tag else 'clear_one'
  return [tag+':',' bra Lplain_'+name+'_15956']
 if destination==0x15a06:
  name='visible_one' if 'visible_one' in tag else 'clear_one'
  return [tag+':',' dbra d3,'+tag+'_resume',' bra Lplain_'+name+'_15960',
         tag+'_resume:',' bra resume_dispatch_plain_'+name]
 return [tag+':',' move.w $6df8.l,d4',' lea $1118.l,a6',' lea $5cdb.l,a0',' jmp $%x.l'%destination]
def record_header(name,tag,destination=0x15a06):
 if not record_enabled(name):return []
 return [' moveq #0,d0',' move.b $6ded.l,d0',' bne '+tag+'_height',' move.w #256,d0',tag+'_height:',
 ' mulu.w #12,d0',' add.l a4,d0',' addq.l #6,d0',' cmp.l _nv_costume_cache+4,d0',' bhi '+tag+'_overflow',
 ' move.w d6,d0',' andi.w #7,d0',' ori.w #$7c00,d0',' move.w d0,(a4)+',' moveq #0,d4',' bra '+tag+'_done']+record_fallback(tag+'_overflow',destination)+[tag+'_done:']

def record(ins,name,tag,color=None):
 if not record_enabled(name):return []
 if ins.address==0x15956:
  prefix=[' movem.l d0-d7/a0-a6,-(sp)',' move.l #%d,-(sp)'%(name=='visible_one'),
   ' jsr _nv_costume_cache_begin',' addq.l #4,sp',' cmpi.l #-1,d0',' beq '+tag+'_cache_rejected',' tst.l d0',' beq '+tag+'_cache_miss',
   ' movem.l (sp)+,d0-d7/a0-a6',' bra cache_replay_'+name,
   tag+'_cache_rejected:',' movem.l (sp)+,d0-d7/a0-a6',' bra Lplain_'+name+'_15956',
   tag+'_cache_miss:',' movem.l (sp)+,d0-d7/a0-a6']
  return prefix+[' clr.w _nv_costume_cache+24',' tst.b $6dfa.l',' bne '+tag+'_unsupported',' cmpi.w #1,$6dfc.l',' beq '+tag+'_direction_ok',' cmpi.w #-1,$6dfc.l',' bne '+tag+'_unsupported',tag+'_direction_ok:',' movea.l _nv_costume_cache,a4',' move.l a4,d0',' beq '+tag+'_unsupported',' addi.l #14,d0',' cmp.l _nv_costume_cache+4,d0',' bhi '+tag+'_unsupported',' clr.l (a4)+',' clr.l (a4)+',' moveq #0,d0',' move.b $6dec.l,d0',' bne '+tag+'_width',' move.w #256,d0',tag+'_width:',' move.w d0,(a4)+']+record_header(name,tag+'_header',0x15956)+[' bra '+tag+'_ready']+record_fallback(tag+'_unsupported',0x15956)+[tag+'_ready:']
 if ins.address==(0x15996 if name=='clear_one' else 0x15990):
  return [' move.w #$0d2b,(a4)+',' move.l a3,d0',' sub.l $5c22.l,d0',' move.w d0,(a4)+',
   ' move.w #$6606,(a4)+',' move.w #$1368,(a4)+',
   (' move.w #%d,(a4)+'%color)if color is not None else ' move.w d2,(a4)+',
   ' move.l a1,d0',' sub.l $5c16.l,d0',' subi.w #32512,d0',' move.w d0,(a4)+']
 if ins.address==0x159aa:return []
 if ins.address==0x15a0e:
  return [' move.l a4,d0',' addq.l #2,d0',' cmp.l _nv_costume_cache+4,d0',' bhi '+tag+'_done',' move.w #$4e75,(a4)+',' movea.l $59b8.l,a1',' cmpa.l _nv_costume_cache+12,a1',' bne '+tag+'_done',' cmpa.l _nv_costume_cache+8,a2',' bhi '+tag+'_done',' move.l a2,d1',' sub.l a1,d1',' beq '+tag+'_done',' move.l a1,d0',' btst #0,d0',' beq '+tag+'_aligned',' addq.l #1,a4',tag+'_aligned:',' move.l a4,d0',' add.l d1,d0',' cmp.l _nv_costume_cache+4,d0',' bhi '+tag+'_done',' movea.l _nv_costume_cache,a0',' move.l a4,(a0)',' move.l d1,4(a0)',' move.l a1,d0',' btst #0,d0',' beq '+tag+'_longs',' move.b (a1)+,(a4)+',' subq.w #1,d1',tag+'_longs:',' move.w d1,d2',' lsr.w #2,d2',' beq '+tag+'_tail',' subq.w #1,d2',tag+'_copy_long:',' move.l (a1)+,(a4)+',' dbra d2,'+tag+'_copy_long',tag+'_tail:',' move.w d1,d2',' andi.w #3,d2',' beq '+tag+'_published',' subq.w #1,d2',tag+'_copy_byte:',' move.b (a1)+,(a4)+',' dbra d2,'+tag+'_copy_byte',tag+'_published:',' move.w #1,_nv_costume_cache+24',tag+'_done:',' move.l a4,_nv_costume_cache+20',' jsr _nv_costume_cache_finish',' moveq #0,d0',' sub.w d0,d0']
 return []


out=[' section text,code',' xdef _scaled_one',' xdef _scaled_two']
if CACHE:out+=[' xref _nv_costume_cache',' xref _nv_costume_cache_begin',' xref _nv_costume_cache_finish']
kernels=[(0x158ee,0x15a14,0x15972,0x15960,0x1595c,0x15a04,0x15a06,'one',False),(0x158ee,0x15a14,0x15972,0x15960,0x1595c,0x15a04,0x15a06,'clear_one',False),(0x158ee,0x15a14,0x15972,0x15960,0x1595c,0x15a04,0x15a06,'visible_one',False),(0x15a14,0x15b54,0x15aa0,0x15a8e,0x15a8a,0x15b44,0x15b46,'two',True)]
if CACHE:kernels += [(*item[:-2],'plain_'+item[-2],item[-1]) for item in kernels if item[-2] in ('clear_one','visible_one')]
for start,end,pixel,decode,resume,wraplast,dbra,name,two in kernels:
 kind=name.removeprefix('plain_')
 # Without vertical clipping D7 is dead; without masks A3 is dead as well.
 # Pixel-loop SUBQ.B D5 replaces flags from the removed row increment.
 end_pixel = 0x15adc if two else 0x159a4
 color_test = 0x15ab2 if two else 0x15984
 label=lambda a:f'L{name}_{a:x}'
 out.append('_scaled_'+name+':')
 for ins in cs.disasm(code[start:end],start):
  if kind in ('clear_one','visible_one') and ins.address==0x159a2:continue
  if kind=='clear_one' and not record_enabled(name) and ins.address==0x1599e:continue
  if kind=='clear_one' and not record_enabled(name) and ins.address==0x1599e:continue
  out.append(label(ins.address)+':');out+=(record(ins,name,label(ins.address)) if ins.address not in (0x15990,0x15996) else [])
  if ins.address==start:
   if kind in ('clear_one','visible_one'):
    out.append(name+'_body:');continue
   if name=='one':
    out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2)))
    out += GUARD
    continue
  if decode <= ins.address < pixel:
   if ins.address==decode:
    out += [' moveq #0,d0',' move.b (a2)+,d0',' add.w d0,d0',' move.w rle_table_'+name+'(pc,d0.w),d0',' jmp rle_table_'+name+'(pc,d0.w)',' xdef rle_table_'+name,' xdef rle_table_end_'+name,'rle_table_'+name+':']
    for color in range(16):
     for count in range(16):out += [' dc.w rle_%s_%d_%d-rle_table_%s'%(name,color,count,name)]
    out += ['rle_table_end_'+name+':']
   continue
  if ins.address==pixel:
   # Fresh decoder falls through dispatcher; initial resume is retargeted here.
   out+=['dispatch_'+name+':',' tst.w d2',' bne opaque_'+name,'transparent_dispatch_'+name+':',' cmpi.w #8,d3',' blo .short_'+name,' moveq #0,d2',' move.b d5,d2',' subq.b #1,d2',' cmp.w d3,d2',' bls.s .bounded_'+name,' move.w d3,d2','.bounded_'+name+':',' cmpi.w #8,d2',' blo .short_'+name,
    ' move.w $59ae.l,d0',' ble .none_'+name,' cmpi.w #256,d0',' bge .all_'+name,
    ' lsl.w #2,d0',' lea $70000000.l,a0',' movea.l (a0,d0.w),a0',' moveq #0,d0',' move.w d2,d0',' add.b d1,d0',' bcc .compact_nowrap_'+name,' move.b (a0,d0.w),d0',' add.b 256(a0),d0',' bra .compact_combine_'+name,'.compact_nowrap_'+name+':',' move.b (a0,d0.w),d0','.compact_combine_'+name+':',' sub.b (a0,d1.w),d0',' bra.s .advance_'+name,
    '.all_'+name+':',' move.w d2,d0',' bra.s .advance_'+name,'.none_'+name+':',' moveq #0,d0','.advance_'+name+':']
   if kind=='clear_one' and not record_enabled(name):out+=[' mulu.w #320,d0']
   else:out+=([] if kind in ('clear_one','visible_one') else [' add.w d0,d7'])+[' mulu.w #40,d0',' adda.l d0,a3']
   if two:out+=[' adda.l d0,a4']
   out+= ([] if kind=='clear_one' and not record_enabled(name) else [' lsl.l #3,d0'])+[' adda.l d0,a1',' sub.w d2,d3',' sub.b d2,d5',' add.b d2,d1',' lea $5cdb.l,a0','.short_'+name+':',' moveq #0,d2',label(pixel)+'_pixel:']
  if pixel <= ins.address < color_test:
   if ins.address == pixel:
    out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+label(end_pixel)]
   continue
  if ins.address in (0x15924,0x15a4a):
   out += [' move.w $59ae.l,d0',' ble .accept_none_'+name,
    ' cmpi.w #256,d0',' blt .accept_lookup_'+name,' move.w #256,d0',
    ' bra .accept_lookup_'+name,'.accept_none_'+name+':',' moveq #0,d0',
    '.accept_lookup_'+name+':',' lsl.w #2,d0',' lea $70000000.l,a6',
    f' adda.l #{ACCEPT_POINTER_OFFSET},a6',' movea.l (a6,d0.w),a6']
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
   if ins.address==resume:targetlabel=('dispatch_' if two else 'resume_dispatch_')+name
   elif target==pixel:targetlabel=label(pixel)+'_pixel'
   else:targetlabel=label(target)
   args=('d3,' if ins.mnemonic.startswith('db') else '')+targetlabel
   mnemonic=ins.mnemonic.split('.')[0]
   out.append(' '+mnemonic+' '+args)
  else:out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2)))
  if ins.address==wraplast:
   out+=record_header(name,label(ins.address)+'_record_header')
   out+=[' dbra d3,'+('dispatch_' if two else 'resume_dispatch_')+name,' bra.w '+label(decode)]
 # Long opaque runs amortize the column-limit check. A4 is unused by the
 # one-mask original; the function envelope still preserves its caller value.
 if not two:
  assert all(i.mnemonic.startswith('movem') or not re.search(r'\ba4\b',i.op_str) for i in cs.disasm(code[start:end],start))
  end_pixel,column_wrap=0x159a4,0x159aa
  out += ['resume_dispatch_'+name+':',' tst.w d2',' beq transparent_dispatch_'+name,'long_opaque_'+name+':',' cmpi.w #15,d3',' blo opaque_'+name,' moveq #0,d0',' move.b d5,d0',' subq.b #1,d0',' cmpi.w #15,d0',' blo opaque_'+name,(' move.w d3,d7' if record_enabled(name) else ' movea.w d3,a4'),' cmp.w d3,d0',' bls .bounded_opaque_'+name,' move.w d3,d0','.bounded_opaque_'+name+':',' move.w d0,d3']
  if record_enabled(name):out+=[' swap d4',' move.w d0,d4',' swap d4']
  batch_label=lambda a:f'B{name}_{a:x}'
  for ins in cs.disasm(code[pixel:end_pixel],pixel):
   if kind in ('clear_one','visible_one') and ins.address==0x159a2:continue
   if kind=='clear_one' and not record_enabled(name) and ins.address==0x1599e:continue
   out.append(batch_label(ins.address)+':');out+=record(ins,name,batch_label(ins.address))
   if pixel <= ins.address < color_test:
    if ins.address==pixel:out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+batch_label(end_pixel)]
    continue
   if kind=='clear_one' and color_test <= ins.address < 0x15996:continue
   if kind=='visible_one' and 0x1598a <= ins.address < 0x15990:continue
   if ins.address in (color_test,color_test+2):continue
   op=ins.operands[-1] if ins.operands else None
   if op is not None and op.type==M.M68K_OP_BR_DISP:
    target=ins.address+2+op.br_disp.disp;out.append(' '+ins.mnemonic.split('.')[0]+' '+batch_label(target))
   else:out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2)))
  out += [batch_label(end_pixel)+':',' dbra d3,'+batch_label(pixel)]+([' swap d4',' move.w d4,d0',' swap d4'] if record_enabled(name) else [])+[' addq.w #1,d0',' sub.b d0,d5',' neg.w d0',(' add.w d7,d0' if record_enabled(name) else ' add.w a4,d0'),' move.w d0,d3',' tst.b d5',' bne .opaque_within_column_'+name,' addq.w #1,d3',' bra '+label(column_wrap),'.opaque_within_column_'+name+':',' bra '+label(decode)]
 # Opaque runs use an equivalent pixel loop without the repeated color test.
 out.append('opaque_'+name+':')
 end_pixel, column_wrap = ((0x15adc,0x15ae2) if two else (0x159a4,0x159aa))
 opaque_label=lambda a:f'O{name}_{a:x}'
 for ins in cs.disasm(code[pixel:end_pixel+2],pixel):
  if kind in ('clear_one','visible_one') and ins.address==0x159a2:continue
  if kind=='clear_one' and not record_enabled(name) and ins.address==0x1599e:continue
  out.append(opaque_label(ins.address)+':');out+=record(ins,name,opaque_label(ins.address))
  if pixel <= ins.address < color_test:
   if ins.address == pixel:
    out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+opaque_label(end_pixel)]
   continue
  if kind=='visible_one' and 0x1598a <= ins.address < 0x15990:continue
  if kind=='clear_one' and color_test <= ins.address < (0x15ace if two else 0x15996):
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
 # Fresh short opaque packets enter a counted suffix directly. Only column
 # boundaries need a residual run count; ordinary pixels fall through.
 packet_end,packet_wrap=((0x15adc,0x15ae2) if two else (0x159a4,0x159aa))
 for color in range(16):
  for count in range(16):
   out += ['rle_%s_%d_%d:'%(name,color,count)]
   # A consumed single pixel never resumes its color. Keep the palette read
   # at the original pixel so palette/output aliases retain their ordering.
   if color and count==1:
    direct_label=lambda address:'D%s_%d_%x'%(name,color,address)
    for ins in cs.disasm(code[pixel:packet_end],pixel):
     if kind in ('clear_one','visible_one') and ins.address==0x159a2:continue
     if kind=='clear_one' and not record_enabled(name) and ins.address==0x1599e:continue
     out += [direct_label(ins.address)+':']+record(ins,name,direct_label(ins.address),color)
     if pixel<=ins.address<color_test:
      if ins.address==pixel:out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+direct_label(packet_end)]
      continue
     if ins.address in (color_test,color_test+2):continue
     if kind=='clear_one' and 0x15984<=ins.address<0x15996:continue
     if kind=='visible_one' and 0x1598a<=ins.address<0x15990:continue
     if ins.mnemonic=='move.b' and ins.op_str=='(a0, d2.w), (a1)':
      out += [' move.b %d(a0),(a1)'%color];continue
     op=ins.operands[-1] if ins.operands else None
     if op is not None and op.type==M.M68K_OP_BR_DISP:
      out += [' '+ins.mnemonic.split('.')[0]+' '+direct_label(ins.address+2+op.br_disp.disp)]
     else:out += [' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2))]
    out += [direct_label(packet_end)+':',' subq.b #1,d5',' beq packet_wrap_%s_1'%name,' bra '+label(decode)]
    continue
   out += [' moveq #%d,d2'%color]
   if not count:
    out += [' moveq #0,d3',' move.b (a2)+,d3',' subq.b #1,d3',' bra '+(('opaque_' if two else 'long_opaque_') if color else 'transparent_dispatch_')+name]
   elif not color:
    out += [' moveq #%d,d3'%(count-1),' bra transparent_dispatch_'+name]
   else:out += [' bra packet_%s_%d'%(name,count)]
 for remaining in range(15,0,-1):
  plabel=lambda address:'P%s_%d_%x'%(name,remaining,address)
  out += ['packet_%s_%d:'%(name,remaining)]
  for ins in cs.disasm(code[pixel:packet_end],pixel):
   if kind in ('clear_one','visible_one') and ins.address==0x159a2:continue
   if kind=='clear_one' and not record_enabled(name) and ins.address==0x1599e:continue
   out += [plabel(ins.address)+':']+record(ins,name,plabel(ins.address))
   if pixel<=ins.address<color_test:
    if ins.address==pixel:out += [' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+plabel(packet_end)]
    continue
   if ins.address in (color_test,color_test+2):continue
   if kind=='clear_one' and 0x15984<=ins.address<0x15996:continue
   if kind=='visible_one' and 0x1598a<=ins.address<0x15990:continue
   op=ins.operands[-1] if ins.operands else None
   if op is not None and op.type==M.M68K_OP_BR_DISP:
    target=ins.address+2+op.br_disp.disp
    out += [' '+ins.mnemonic.split('.')[0]+' '+plabel(target)]
   else:out += [' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,len(ins.bytes),2))]
  out += [plabel(packet_end)+':',' subq.b #1,d5',' beq packet_wrap_%s_%d'%(name,remaining)]
  if remaining==1:out += [' bra '+label(decode)]
 for remaining in range(1,16):
  out += ['packet_wrap_%s_%d:'%(name,remaining),' moveq #%d,d3'%(remaining-1),' bra '+label(packet_wrap)]
if CACHE:
 for name in ('clear_one','visible_one'):
  out += ['cache_replay_'+name+':',' movea.l _nv_costume_cache+16,a2',' adda.w #10,a2',
   ' lea $5cdb.l,a0',' movea.l $5c16.l,a1',' adda.l #32512,a1',' movea.l $5c22.l,a3',
   ' jsr (a2)',' moveq #0,d0',' sub.w d0,d0',' movem.l (sp)+,d0-d7/a0-a6',' rts']
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
prefix=bytearray(PREFIX_PHASES*4)
for scale in range(PREFIX_PHASES):
 struct.pack_into('>I',prefix,scale*4,len(prefix));n=0;prefix.append(0)
 for index in range(256):
  n+=table[index&255]<scale;prefix.append(n&255)
accept_pointers=len(prefix)
assert accept_pointers==ACCEPT_POINTER_OFFSET
prefix += bytes(257*4)
for scale in range(257):
 struct.pack_into('>I',prefix,accept_pointers+scale*4,len(prefix)+1)
 prefix += bytes([table[255]<scale])+bytes(value<scale for value in table)
prefix += bytes((-len(prefix))%4)
pointer_offsets=list(range(0,1024,4))+list(range(accept_pointers,accept_pointers+257*4,4))
(BUILD / 'scale_prefix.bin').write_bytes(prefix)
(BUILD / 'generation.json').write_text(json.dumps(dict(entries=entries,embedded_data_ranges=[(entries['rle_table_'+n],entries['rle_table_end_'+n]) for n in [item[-2] for item in kernels]],code_bytes=len(obj),clear_mask_fast_path=True,kernel_variants=len(kernels),visible_mask_fast_path=True,prefix_bytes=len(prefix),prefix_counter_bits=8,prefix_max_batch=255,prefix_row_bytes=PREFIX_ROW_BYTES,table_sha256=hashlib.sha256(table).hexdigest(),accept_pointer_offset=accept_pointers,accept_rows=257,accept_row_bytes=257,prefix_pointer_offsets=pointer_offsets),indent=2)+'\n')
print((BUILD / 'generation.json').read_text())
