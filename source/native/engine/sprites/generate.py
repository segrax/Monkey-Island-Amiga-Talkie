"""Clone and accelerate the original unmasked scaled-sprite renderer."""
from pathlib import Path
import sys,json,hashlib,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
P=artifact_dir('sprites');r=HunkReader();original=PROJECT_ROOT/'data/original/Monkey_Island'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
assert r.read_file(str(original))==0 and r.build_segments();data={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h};code=data[0]
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
start,end,pixel,decode,resume,finish,column=0x157ee,0x158ee,0x1586a,0x15858,0x15854,0x15892,0x15898
scan=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);scan.detail=True;scan.skipdata=True
for ins in scan.disasm(code,0):
 if ins.id==0:continue
 for op in ins.operands:
  if op.type==M.M68K_OP_BR_DISP:
   target=ins.address+2+op.br_disp.disp
   assert not (start<target<start+10 and not start<=ins.address<end),(ins.address,target)
section=0
for h in r.hunks:
 section=h.get('hunk_no',section)
 if h['type_name']=='HUNK_ABSRELOC32':
  for off in h['reloc'].get(0,[]):assert not start<int.from_bytes(data[section][off:off+4],'big')<start+10
label=lambda a:'L%x'%a
out=[' section text,code',' xdef _scaled_zero','_scaled_zero:']
for ins in cs.disasm(code[start:end],start):
 out.append(label(ins.address)+':')
 if ins.address==0x1581e:
  out+=[' move.w $59ae.l,d0',' ble .none',' cmpi.w #256,d0',' blt .accept',' move.w #256,d0',' bra .accept','.none:',' moveq #0,d0','.accept:',' lsl.w #2,d0',' lea $70000000.l,a6',' adda.l #66816,a6',' movea.l (a6,d0.w),a6'];continue
 if ins.address==pixel:
  out+=['dispatch:',' tst.w d2',' bne opaque',' cmpi.w #8,d3',' blo .short',' moveq #0,d2',' move.b d5,d2',' subq.b #1,d2',' cmp.w d3,d2',' bls .bounded',' move.w d3,d2','.bounded:',' cmpi.w #8,d2',' blo .short',' move.w $59ae.l,d0',' ble .empty',' cmpi.w #256,d0',' bge .all',' lsl.w #2,d0',' lea $70000000.l,a0',' movea.l (a0,d0.w),a0',' moveq #0,d0',' move.w d2,d0',' add.b d1,d0',' bcc .compact_nowrap',' move.b (a0,d0.w),d0',' add.b 256(a0),d0',' bra .compact_combine','.compact_nowrap:',' move.b (a0,d0.w),d0','.compact_combine:',' sub.b (a0,d1.w),d0',' bra .advance','.all:',' move.w d2,d0',' bra .advance','.empty:',' moveq #0,d0','.advance:',' add.w d0,d7',' mulu.w #320,d0',' adda.l d0,a1',' sub.w d2,d3',' sub.b d2,d5',' add.b d2,d1',' lea $5cdb.l,a0','.short:',' moveq #0,d2',label(pixel)+'_pixel:']
 if pixel<=ins.address<0x1587c:
  if ins.address==pixel:out+=[' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq '+label(finish)]
  continue
 if 0x1587c<=ins.address<0x1588c:continue
 if ins.address==0x158b4:
  out+=[' moveq #0,d0',' lea $1118.l,a0',' move.b (a0,d1.w),d0',' lea $5cdb.l,a0'];continue
 if ins.address==0x158b6:continue
 op=ins.operands[-1] if ins.operands else None
 if op is not None and op.type==M.M68K_OP_BR_DISP:
  target=ins.address+2+op.br_disp.disp
  assert start<=target<end
  targetlabel='dispatch' if ins.address==resume else label(pixel)+'_pixel' if target==pixel else label(target)
  out.append(' '+ins.mnemonic.split('.')[0]+' '+('d3,' if ins.mnemonic.startswith('db') else '')+targetlabel)
 else:out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,ins.size,2)))
 if ins.address==0x158de:out+=[' dbra d3,dispatch',' bra '+label(decode)]
out+=['opaque:']
for ins in cs.disasm(code[pixel:finish+2],pixel):
 out.append('O%x:'%ins.address)
 if pixel<=ins.address<0x1587c:
  if ins.address==pixel:out+=[' addq.b #1,d1',' tst.b -1(a6,d1.w)',' beq O%x'%finish]
  continue
 if ins.address in (0x1587c,0x1587e):continue
 op=ins.operands[-1] if ins.operands else None
 if op is not None and op.type==M.M68K_OP_BR_DISP:out.append(' '+ins.mnemonic.split('.')[0]+' O%x'%(ins.address+2+op.br_disp.disp))
 else:out.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,ins.size,2)))
out+=[' bne .opaque_more',' bra '+label(column),'.opaque_more:',' dbra d3,opaque',' bra '+label(decode)]
(P/'unmasked.s').write_text('\n'.join(out)+'\n');subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(P/'unmasked.o'),str(P/'unmasked.s')],check=True)
o=HunkReader();assert o.read_file(str(P/'unmasked.o'))==0;blob=next(h['data'] for h in o.hunks if h['type_name']=='HUNK_CODE');global_refs=[];prefix_refs=[]
for ins in cs.disasm(blob,0):
 for op in ins.operands:
  if op.address_mode==M.M68K_AM_ABSOLUTE_DATA_LONG:
   v=int.from_bytes(ins.bytes[-4:],'big');assert v==0x70000000 or 0<=v<29312,hex(v)
   (prefix_refs if v==0x70000000 else global_refs).append(ins.address+ins.size-4)
assert len(prefix_refs)==2
(P/'unmasked.bin').write_bytes(blob);(P/'generation.json').write_text(json.dumps(dict(start=start,end=end,expected=code[start:start+10].hex(),code_bytes=len(blob),globals=global_refs,prefix=prefix_refs,table_sha256=hashlib.sha256(data[2][0x1118:0x1218]).hexdigest()),indent=2)+'\n');print('Unmasked kernel bytes:',len(blob))
