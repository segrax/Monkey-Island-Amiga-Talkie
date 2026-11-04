"""Relax internal branches in the original mask-plane RLE decoder."""
from pathlib import Path
import hashlib,json,sys,subprocess
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import capstone
from capstone import m68k_const as M
BUILD=artifact_dir('mask-rle');START,END=0x15338,0x1538e
original=PROJECT_ROOT/'data/original/Monkey_Island'
assert hashlib.sha256(original.read_bytes()).hexdigest()=='1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
r=HunkReader();assert r.read_file(str(original))==0 and r.build_segments()
code=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data' in h)
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);cs.detail=True
instructions=list(cs.disasm(code[START:END],START));assert instructions[-1].address==END-2
lines=[' section text,code',' xdef _mask_rle','_mask_rle:']
for ins in instructions:
 lines.append(f'L{ins.address:x}:');op=ins.operands[-1] if ins.operands else None
 if op and op.type==M.M68K_OP_BR_DISP:
  target=ins.address+2+op.br_disp.disp;assert START<=target<END
  name=ins.mnemonic.split('.')[0]
  args=('d'+str(ins.operands[0].reg-M.M68K_REG_D0)+',' if name.startswith('db') else '')+f'L{target:x}'
  lines.append(' '+name+' '+args)
 else:lines.append(' dc.w '+','.join('$'+ins.bytes[i:i+2].hex() for i in range(0,ins.size,2)))
(BUILD/'mask-rle.s').write_text('\n'.join(lines)+'\n')
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o',str(BUILD/'mask-rle.o'),str(BUILD/'mask-rle.s')],check=True)
o=HunkReader();assert o.read_file(str(BUILD/'mask-rle.o'))==0
kernel=bytes(next(h['data'] for h in o.hunks if h['type_name']=='HUNK_CODE'))
new=list(cs.disasm(kernel,0));assert len(new)>=len(instructions)
# HUNK_CODE is padded to a longword. Padding after the final RTS is not part
# of the routine; the in-place patch supplies its own unreachable NOP fill.
size=new[len(instructions)-1].address+new[len(instructions)-1].size
assert kernel[size:] in (b'',bytes.fromhex('4e71'),bytes(2))
kernel=kernel[:size];new=new[:len(instructions)];assert len(kernel)<=END-START
mapping={a.address:b.address for a,b in zip(instructions,new)};branches=[]
for a,b in zip(instructions,new):
 op=a.operands[-1] if a.operands else None
 if op and op.type==M.M68K_OP_BR_DISP:
  assert a.mnemonic.split('.')[0]==b.mnemonic.split('.')[0]
  assert b.address+2+b.operands[-1].br_disp.disp==mapping[a.address+2+op.br_disp.disp]
  if a.size!=b.size:branches.append(dict(old=a.address,new=b.address,old_size=a.size,new_size=b.size))
 else:assert a.bytes==b.bytes
relocs=[];section=0;data={h['hunk_no']:h['data'] for h in r.hunks if 'data' in h}
for h in r.hunks:
 section=h.get('hunk_no',section)
 if h['type_name']!='HUNK_ABSRELOC32':continue
 for off in h['reloc'].get(0,[]):
  value=int.from_bytes(data[section][off:off+4],'big');assert not START<value<END,(section,off,value)
 if section==0:
  for target,offsets in h['reloc'].items():
   for off in offsets:
    if START<=off<END:
     assert target==2;offset=off-START;assert kernel[offset:offset+4]==code[off:off+4];relocs.append(offset)
assert len(relocs)==3
cs.skipdata=True;entries=[]
for ins in cs.disasm(code,0):
 if not ins.id:continue
 for op in ins.operands:
  target=None
  if op.type==M.M68K_OP_BR_DISP:target=ins.address+2+op.br_disp.disp
  elif op.address_mode==M.M68K_AM_PCI_DISP:target=ins.address+2+op.mem.disp
  elif ins.mnemonic in ('jmp','jsr') and op.address_mode==M.M68K_AM_ABSOLUTE_DATA_LONG:target=op.imm
  if target is not None and not START<=ins.address<END:
   assert not START<target<END,(ins.address,target)
   if target==START:entries.append(ins.address)
assert 0x4de2 in entries
(BUILD/'mask-rle.bin').write_bytes(kernel)
report=dict(start=START,end=END,original_bytes=END-START,kernel_bytes=len(kernel),source_sha256=hashlib.sha256(original.read_bytes()).hexdigest(),kernel_sha256=hashlib.sha256(kernel).hexdigest(),absolute_h2_relocations=sorted(relocs),branches=branches,external_entry_references=entries,no_external_interior_entry=True,nonbranch_bytes_identical=True,relocation_positions_unchanged=True)
(BUILD/'generation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
