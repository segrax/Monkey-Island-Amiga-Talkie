"""Compare original and relaxed restorer, including ordered memory accesses."""
from pathlib import Path
import sys,json,random,struct,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
root=artifact_dir('restoration');generation=json.loads((root/'generation.json').read_text())
original=PROJECT_ROOT/'data/original/Monkey_Island'
assert hashlib.sha256(original.read_bytes()).hexdigest()==generation['source_sha256']
r=HunkReader();assert r.read_file(str(original))==0 and r.build_segments()
code=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data' in h)
kernel=(root/'restore.bin').read_bytes();assert hashlib.sha256(kernel).hexdigest()==generation['kernel_sha256']
variants={'original':code[generation['start']:generation['end']],'relaxed':kernel}
relocs=generation['absolute_h2_relocations']
regs=[getattr(R,'UC_M68K_REG_'+n) for n in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
cpus=[]
for name,kernel in variants.items():
 cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000)
 cpus.append((name,cpu,kernel))
rng=random.Random(0x15f5a);cases=[]
for mask in range(256):cases.append((1,[mask],mask&31,False))
for mask in (0,255,85,170):
 for height in (1,2,16):
  for ccr in range(32):cases.append((height,[mask]*height,ccr,False))
for _ in range(128):
 height=rng.choice((1,2,8,64,128,200,256));cases.append((height,[rng.randrange(256) for _ in range(height)],rng.randrange(32),rng.choice((False,False,True))))
profiles={};checks=0
for layout in range(2):
 for number,(height,masks,ccr,alias) in enumerate(cases):
  g=0x300000+layout*0x10000;dest=0x500010+layout*0x20000;source=dest+4 if alias else 0x400010+layout*0x20000;maskptr=0x600010+layout*0x10000
  data=bytes(rng.randrange(256) for _ in range(height*320+16));background=bytes(rng.randrange(256) for _ in range(height*320+16));mb=bytearray(height*40)
  for y,m in enumerate(masks):mb[y*40]=m
  initial=[rng.getrandbits(32) for _ in regs];initial[-1]=0x80f000;results=[]
  for name,cpu,kernel in cpus:
   blob=bytearray(kernel)
   for off in relocs:struct.pack_into('>I',blob,off,int.from_bytes(blob[off:off+4],'big')+g)
   cpu.mem_write(0x100000,bytes(blob));cpu.mem_write(g,bytes(0x7300))
   for off,value,size in ((0x5c1e,dest,4),(0x5c1a,source,4),(0x5c22,maskptr,4),(0x6e0a,height,2)):cpu.mem_write(g+off,value.to_bytes(size,'big'))
   cpu.mem_write(dest-16,b'X'*16+data);cpu.mem_write(source,background);cpu.mem_write(maskptr,bytes(mb));cpu.mem_write(0x80ef00,bytes(0x104));cpu.mem_write(0x80f000,struct.pack('>I',0x900000))
   cpu.reg_write(R.UC_M68K_REG_SR,ccr)
   for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
   reads=[];writes=[];count=[0]
   def read(uc,access,address,size,value,unused):
    if not 0x80ef00<=address<0x80f004:reads.append((address,size))
   def write(uc,access,address,size,value,unused):
    assert 0x80ef00<=address and address+size<=0x80f000 or dest<=address and address+size<=dest+(height-1)*320+8,(hex(address),size)
    writes.append((address,size,value))
   def step(*unused):count[0]+=1
   hooks=[cpu.hook_add(unicorn.UC_HOOK_MEM_READ,read),cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,write),cpu.hook_add(unicorn.UC_HOOK_CODE,step)]
   cpu.emu_start(0x100000,0x900000,count=1000000)
   for h in hooks:cpu.hook_del(h)
   assert cpu.reg_read(R.UC_M68K_REG_PC)==0x900000
   cpu.mem_write(0x900000,bytes.fromhex('40f900900100'));cpu.emu_start(0x900000,0x900006,count=1)
   result=(tuple(cpu.reg_read(reg) for reg in regs),bytes(cpu.mem_read(0x900100,2)),bytes(cpu.mem_read(dest-16,height*320+32)),bytes(cpu.mem_read(source,height*320+16)),bytes(cpu.mem_read(maskptr,len(mb))),bytes(cpu.mem_read(g,0x7300)),bytes(cpu.mem_read(0x80ef00,0x104)),reads,writes)
   results.append(result)
   if layout==0 and number in (0,1,85,170,255):profiles.setdefault(str(masks[0]),{})[name]=count[0]
  assert results[0]==results[1],(layout,number,height,masks,ccr,[(i,[j for j,(a,b) in enumerate(zip(results[0],v)) if a!=b]) for i,v in enumerate(results)])
  checks+=1
report=dict(pass_=True,cases=checks,all_masks=True,all_ccr=True,two_layouts=True,alias_checked=True,registers_flags_stack_globals_pixels_masks_ordered_memory_exact=True,profiles=profiles)
(root/'kernel-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
