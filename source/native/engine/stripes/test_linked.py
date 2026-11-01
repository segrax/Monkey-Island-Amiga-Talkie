"""Audit the ten-hunk rebase and execute its relocated existing JMP entry."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
target=ENGINE_BUILD/'module';source=ENGINE_BUILD/'scaling'
def load(p):
 r=HunkReader();assert r.read_file(str(p))==0 and r.build_segments();return r
a=load(source/'Monkey_Talkie_Scaled');b=load(target/'Monkey_Talkie_Test')
old={h['hunk_no']:h for h in a.hunks if 'data'in h};new={h['hunk_no']:h for h in b.hunks if 'data'in h}
assert b.hunks[0]['table_size']==a.hunks[0]['table_size']+1==10
for index,x in old.items():
 y=new[index]
 expected=bytearray(x['data'])
 if x['hunk_no']==0:expected[0x4dde:0x4de2]=bytes(4)
 assert y['data']==expected
assert new[0]['data'][0x15190:0x15338]==old[0]['data'][0x15190:0x15338]
def relocs(r):
 groups={};section=0
 for h in r.hunks:
  section=h.get('hunk_no',section)
  if h['type_name']=='HUNK_ABSRELOC32':
   for dest,offs in h['reloc'].items():groups.setdefault((section,dest),set()).update(offs)
 return groups
ar,br=relocs(a),relocs(b);expected={k:set(v)for k,v in ar.items()};expected[(0,0)].remove(0x4dde);expected[(0,9)]={0x4dde};expected[(9,2)]=set(json.loads((BUILD / 'generation.json').read_text())['absolute_h2_relocations'])
assert {k:v for k,v in br.items()if v}=={k:v for k,v in expected.items()if v}
ram=(ROOT/'tests/fixtures/combined-ram.bin').read_bytes();h0=0x271b30;g=0x289d28;h9=0xb00000;out=[];writes=[]
regs=[getattr(R,'UC_M68K_REG_'+s)for s in('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
for changed in(False,True):
 c=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);c.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);c.mem_map(0,0x1000000);c.mem_write(0,ram)
 if changed:
  c.mem_write(h0+0x4dde,struct.pack('>I',h9));c.mem_write(h9,new[9]['data'])
  for off in br[(9,2)]:c.mem_write(h9+off,struct.pack('>I',int.from_bytes(c.mem_read(h9+off,4),'big')+g))
 c.mem_write(0xe0f000,struct.pack('>I',0xf00000));c.reg_write(R.UC_M68K_REG_SR,31)
 for i,reg in enumerate(regs):c.reg_write(reg,0xe0f000 if i==15 else 0x12345600+i)
 wr=[]
 def write(uc,access,addr,size,value,unused):wr.append((addr,size,value))
 wh=c.hook_add(unicorn.UC_HOOK_MEM_WRITE,write);c.emu_start(h0+0x4ddc,0xf00000,count=100000);c.hook_del(wh);assert c.reg_read(R.UC_M68K_REG_PC)==0xf00000
 c.mem_write(0xf00000,bytes.fromhex('40f900f00100'));c.emu_start(0xf00000,0xf00006,count=1)
 c.mem_write(h0+0x4dde,ram[h0+0x4dde:h0+0x4de2])
 out.append((tuple(c.reg_read(v)for v in regs),bytes(c.mem_read(0xf00100,2)),bytes(c.mem_read(0,len(ram))),bytes(c.mem_read(0xe0ee00,0x204))))
 writes.append(wr)
assert out[0]==out[1] and writes[0]==writes[1]
report=dict(sha256=hashlib.sha256((target/'Monkey_Talkie_Test').read_bytes()).hexdigest(),all_nine_source_hunks_unchanged_except_four_H0_operand_bytes=True,original_decoder_body_exact=True,all_relocations_exact_except_declared_target_swap_and_new_kernel=True,linked_existing_JMP_entry_exact_GPR_CCR_stack_RAM_write_sequence=True,retains_all_native_hooks_and_two_scaled_entry_hooks=True,runtime_validated=False)
(target/'linked-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
