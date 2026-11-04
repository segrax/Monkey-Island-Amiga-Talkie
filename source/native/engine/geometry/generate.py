from pathlib import Path
import sys,json,hashlib,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
P=artifact_dir('geometry')
assert hashlib.sha256((PROJECT_ROOT/'data/original/Monkey_Island').read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
c=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
loops=[dict(name='mirrored_x_offset',start=0xf0f2,end=0xf12a,count='-4(a5)',scale='$59ac(a4)',phase='$6e00(a4)',target='$6df2(a4)',op='sub',direction='$6dfc(a4)'),dict(name='mirrored_x_extent',start=0xf140,end=0xf174,count='$6de8(a4)',scale='$59ac(a4)',phase='$6e00(a4)',target='$6dda(a4)',op='add',direction=None),dict(name='x_offset',start=0xf192,end=0xf1ca,count='-4(a5)',scale='$59ac(a4)',phase='$6e00(a4)',target='$6df2(a4)',op='add',direction='$6dfc(a4)'),dict(name='x_extent',start=0xf1e0,end=0xf214,count='$6de8(a4)',scale='$59ac(a4)',phase='$6e00(a4)',target='$6dd8(a4)',op='sub',direction=None),dict(name='y_offset',start=0xf246,end=0xf27e,count='-6(a5)',scale='$59ae(a4)',phase='$6e01(a4)',target='$6df4(a4)',op='sub',direction='$6dfe(a4)'),dict(name='y_extent',start=0xf294,end=0xf2c8,count='$6dea(a4)',scale='$59ae(a4)',phase='$6e01(a4)',target='$6dde(a4)',op='add',direction=None)]
# Reject references that would enter the middle of a replaced loop.
scan=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);scan.detail=True;scan.skipdata=True
for ins in scan.disasm(c,0):
 if ins.id==0:continue
 for op in ins.operands:
  if op.type==M.M68K_OP_BR_DISP:
   target=ins.address+2+op.br_disp.disp
   for v in loops:assert not (v['start']<target<v['end'] and not v['start']<=ins.address<v['end']),(hex(ins.address),hex(target))
section=0;data={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h}
for h in r.hunks:
 section=h.get('hunk_no',section)
 if h['type_name']=='HUNK_ABSRELOC32':
  for off in h['reloc'].get(0,[]):
   target=int.from_bytes(data[section][off:off+4],'big')
   for v in loops:assert not v['start']<target<v['end'],(section,off,target)
lines=[' section text,code']
for v in loops:
 name=v['name'];lines+=[' xdef _'+name,'_'+name+':',' tst.w -2(a5)',' bne fallback_'+name,' move.w '+v['count']+',d0',' cmpi.w #16,d0',' blt fallback_'+name,' movem.l d2-d5/a1-a2,-(sp)',' moveq #0,d2',' move.w d0,d2',' moveq #0,d3',' move.b '+v['phase']+',d3',' moveq #0,d5',' move.w '+v['scale']+',d5',' bsr count_accepted']
 if v['direction']:lines+=[' mulu.w '+v['direction']+',d4']
 lines += [' '+v['op']+'.w d4,'+v['target'],' move.w d3,d0',' add.w d2,d0',' move.b d0,'+v['phase'],' subq.b #1,d0',' moveq #0,d1',' move.b d0,d1',' lea $1118(a4),a0',' move.w d2,-2(a5)',' moveq #0,d0',' addq.w #1,d0',' move.w d2,d0',' cmp.w '+v['count']+',d0',' movem.l (sp)+,d2-d5/a1-a2',' rts','fallback_'+name+':']
 for i in cs.disasm(c[v['start']:v['end']],v['start']):
  lines.append('L%x:'%i.address)
  op=i.operands[-1] if i.operands else None
  if op and op.type==M.M68K_OP_BR_DISP:
   target=i.address+2+op.br_disp.disp;assert v['start']<=target<v['end'];lines.append(' '+i.mnemonic.split('.')[0]+' L%x'%target)
  else:lines.append(' dc.w '+','.join('$'+i.bytes[k:k+2].hex() for k in range(0,i.size,2)))
 lines.append(' rts');v['expected']=c[v['start']:v['end']].hex()
# Count complete 256-phase cycles and a remainder from the existing byte-prefix
# table. Scales >=256 accept every table entry; lower scales fit in one byte.
lines+=['count_accepted:',' move.w d2,d4',' cmpi.w #256,d5',' bcc .done',' lsl.w #2,d5',' lea $70000000.l,a1',' movea.l (a1,d5.w),a1',' lsr.w #8,d4',' moveq #0,d0',' move.b 256(a1),d0',' mulu.w d0,d4',' move.w d2,d0',' andi.w #255,d0',' moveq #0,d5',' add.b d3,d0',' bcc .compact_nowrap',' move.b (a1,d0.w),d5',' add.b 256(a1),d5',' bra .compact_combine','.compact_nowrap:',' move.b (a1,d0.w),d5','.compact_combine:',' sub.b (a1,d3.w),d5',' andi.w #255,d5',' add.w d5,d4','.done:',' rts']
(P/'geometry.s').write_text('\n'.join(lines)+'\n');subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(P/'geometry.o'),str(P/'geometry.s')],check=True)
o=HunkReader();assert o.read_file(str(P/'geometry.o'))==0
blob=next(h['data'] for h in o.hunks if h['type_name']=='HUNK_CODE');entries={e['name']:e['def'] for h in o.hunks if h['type_name']=='HUNK_EXT' for e in h['ext_def']};rel=[]
for i in cs.disasm(blob,0):
 for op in i.operands:
  if op.address_mode==M.M68K_AM_ABSOLUTE_DATA_LONG:assert op.imm==0x70000000;rel.append(i.address+2)
assert len(rel)==1
(P/'geometry.bin').write_bytes(blob);(P/'generation.json').write_text(json.dumps(dict(loops=loops,entries=entries,prefix_relocations=rel,code_bytes=len(blob)),indent=2)+'\n');print(entries,len(blob))
