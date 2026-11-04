"""Synthetic guest differential tests for the source-built bounded draw cache.

No captured RAM or previous generated build is required.  The original executable
is the oracle; inputs, palette, mask, resource ownership and Exec calls are synthetic.
"""
from pathlib import Path
import sys,json,struct,random,hashlib
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'engine'),str(ROOT/'tools/python')]
from paths import artifact_dir,engine_build
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
BUILD=artifact_dir('scaling')
REGS=[getattr(R,'UC_M68K_REG_'+n)for n in('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
STOP=0xe00000;STACK=0xf0f000;FRAME=0xa10010;MASK=0xb10000;ARENA=0xc00000;SOURCE=0x900006
def put32(cpu,p,n):cpu.mem_write(p,struct.pack('>I',n))
def u32(cpu,p):return int.from_bytes(cpu.mem_read(p,4),'big')
def reader(p):
 r=HunkReader();assert r.read_file(str(p))==0 and r.build_segments();return r
class Guest:
 def __init__(self,path,layout,metadata=None,fail=False,attn_flags=0,exec_version=0,alloc_limit=65536):
  r=reader(path);self.cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN)
  self.cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);self.cpu.mem_map(0,0x1000000)
  sections=[h for h in r.hunks if h['type_name']in('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
  self.bases=[0x100000+n*0x40000+layout*0x10000 for n in range(len(sections))]
  section=0
  for h in r.hunks:
   section=h.get('hunk_no',section)
   if 'data'in h:self.cpu.mem_write(self.bases[section],h['data'])
   if h['type_name']=='HUNK_ABSRELOC32':
    for target,offsets in h['reloc'].items():
     for off in offsets:
      p=self.bases[section]+off;put32(self.cpu,p,u32(self.cpu,p)+self.bases[target])
  self.g=self.bases[2];self.exports=metadata['exports']if metadata else{}
  self.alloc=[];self.free=[];self.flushes=[];self.generated_instructions=0;self.capacity=0
  self.attn_flags=attn_flags;self.exec_version=exec_version
  if metadata:
   put32(self.cpu,self.addr('_nv_control')+16,self.g)
   put32(self.cpu,4,0x8000);put32(self.cpu,0x8000+322,0x8200)
   self.cpu.mem_write(0x8000+296,struct.pack('>H',attn_flags))
   self.cpu.mem_write(0x8000+20,struct.pack('>H',exec_version))
   put32(self.cpu,0x8200,0x8240);put32(self.cpu,0x8240,0)
   put32(self.cpu,0x8200+20,0x100000);put32(self.cpu,0x8200+24,0xf80000)
   def exec_call(cpu,pc,size,unused):
    if ARENA<=pc<ARENA+65536:
     assert pc<ARENA+self.capacity,'Generated entry exceeds allocated arena'
     assert not(pc&1),'Generated entry must be word aligned'
     self.generated_instructions+=1
    if pc==0x8000-198:
     requested=cpu.reg_read(R.UC_M68K_REG_D0)
     assert requested in range(16384,65537,4096)
     assert cpu.reg_read(R.UC_M68K_REG_D1)==0x10005,'Must not fall back to Chip'
     self.alloc.append(requested)
     self.capacity=requested if not fail and requested<=alloc_limit else 0
     cpu.reg_write(R.UC_M68K_REG_D0,ARENA if self.capacity else 0)
     if self.capacity:cpu.mem_write(ARENA,bytes(self.capacity))
    elif pc==0x8000-210:self.free.append((cpu.reg_read(R.UC_M68K_REG_A1),cpu.reg_read(R.UC_M68K_REG_D0)))
    elif pc==0x8000-636:
     assert self.attn_flags&2 and self.exec_version>=37,'Unavailable or unnecessary cache API'
     context=self.addr('_nv_costume_cache');plan=u32(cpu,context);end=u32(cpu,context+4)
     assert ARENA+976<=plan<end<=ARENA+self.capacity
     copy=u32(cpu,plan);copied=u32(cpu,plan+4)
     assert plan+10<copy and 0<copied<=end-copy
     assert bytes(cpu.mem_read(copy-2,2))==b'\x4e\x75' or bytes(cpu.mem_read(copy-3,2))==b'\x4e\x75','Code must be complete before flush'
     for slot in range(16):
      entry=ARENA+36*slot
      assert not u32(cpu,entry+28) or ARENA+u32(cpu,entry+24)!=plan,'Entry published before flush'
     self.flushes.append(dict(plan=plan,builds_before=u32(cpu,context+40),source_bytes=copied))
     # Exec may clobber these caller-save registers; generated publication must not rely on them.
     for register in(R.UC_M68K_REG_D0,R.UC_M68K_REG_D1,R.UC_M68K_REG_A0,R.UC_M68K_REG_A1):cpu.reg_write(register,0x5a5a1234)

    else:return
    sp=cpu.reg_read(R.UC_M68K_REG_A7);cpu.reg_write(R.UC_M68K_REG_PC,u32(cpu,sp));cpu.reg_write(R.UC_M68K_REG_A7,sp+4)
   self.cpu.hook_add(unicorn.UC_HOOK_CODE,exec_call)
   self.cpu.reg_write(R.UC_M68K_REG_SR,0);self.call(self.addr('_nv_costume_cache_start'))
 def addr(self,name):
  entry=self.exports[name];return self.bases[entry['hunk']]+entry['offset']
 def call(self,pc,args=()):
  self.cpu.reg_write(R.UC_M68K_REG_A7,STACK)
  self.cpu.mem_write(STACK,struct.pack('>%dI'%(len(args)+1),STOP,*args))
  self.cpu.emu_start(pc,STOP,count=3000000)
  assert self.cpu.reg_read(R.UC_M68K_REG_PC)==STOP
 def setup(self,case,encoded,seed):
  cpu=self.cpu;g=self.g;source=SOURCE+case['odd'];width=case['width'];height=case['height']
  cpu.mem_write(source-6,struct.pack('<I',len(encoded)+6)+bytes((2,48))+encoded)
  cpu.mem_write(0x940000,bytes(199*4));put32(cpu,0x940000+48*4,source-6)
  cpu.mem_write(FRAME-16,b'Z'*0x20020)
  cpu.mem_write(MASK,bytes([case['mask']])*0x3000)
  cpu.mem_write(g+0x5cdb,bytes((i*13+case['palette'])&255 for i in range(16)))
  for off,value,n in((0x2778,0x940000,4),(0x235c,199,2),(0x59b4,source-6,4),(0x59b8,source,4),
   (0x5c16,FRAME,4),(0x5c22,MASK+case['x']//8,4),(0x6de0,MASK,4),(0x6de4,8000,2),
   (0x6df2,case['x'],2),(0x6df4,0,2),(0x6df6,0,2),(0x6df8,200,2),(0x6dfc,1,2),
   (0x6dec,width&255,1),(0x6ded,height&255,1),(0x6de6,0,1),(0x6de7,0,1),(0x6dfa,0,1),
   (0x59ac,case['sx'],2),(0x59ae,case['sy'],2),(0x6e00,case['xp'],1),(0x6e01,case['yp'],1),(0x6e02,case['reset'],1)):
   cpu.mem_write(g+off,int(value).to_bytes(n,'big'))
  cpu.mem_write(STACK-0x1000,bytes(0x1000));put32(cpu,STACK,STOP)
  initial=random.Random(seed);values=[initial.randrange(1<<32)for _ in REGS];values[-1]=STACK
  cpu.reg_write(R.UC_M68K_REG_SR,case['ccr'])
  for reg,value in zip(REGS,values):cpu.reg_write(reg,value)
 def draw(self):
  cpu=self.cpu;palette_reads=[];before=bytes(cpu.mem_read(self.g,29312));mask=bytes(cpu.mem_read(MASK,0x3000))
  def reads(uc,access,p,n,value,unused):
   if self.g+0x5cdb<=p<self.g+0x5ceb:palette_reads.append((p-self.g-0x5cdb,n))
  hook=cpu.hook_add(unicorn.UC_HOOK_MEM_READ,reads)
  self.call(self.bases[0]+0x158ee);cpu.hook_del(hook)
  cpu.mem_write(STOP,bytes.fromhex('40f900e00100'));cpu.emu_start(STOP,STOP+6,count=1)
  assert bytes(cpu.mem_read(self.g,29312))==before
  assert bytes(cpu.mem_read(MASK,0x3000))==mask
  return tuple(cpu.reg_read(r)for r in REGS),bytes(cpu.mem_read(STOP+0x100,2)),bytes(cpu.mem_read(FRAME-16,0x20020)),palette_reads
def stream(pixels,seed,opaque=False):
 rng=random.Random(seed);out=bytearray();covered=0
 while covered<pixels:
  n=rng.choice((1,2,7,15,16,127,255,256));color=rng.choice((1,6,15))if opaque else rng.choice((0,0,1,6,15))
  out.append(color<<4|(n if n<16 else 0))
  if n>=16:out.append(n&255)
  covered+=n
 return bytes(out)
def main():
 image=BUILD/'Monkey_Talkie_Scaled';meta=json.loads((BUILD/'module.json').read_text())
 if (engine_build()/'module/Monkey_Talkie_Test').exists():
  image=engine_build()/'module/Monkey_Talkie_Test';meta=json.loads((image.parent/'module.json').read_text())
 results=[];base=dict(width=24,height=62,x=121,sx=128,sy=128,xp=104,yp=66,reset=67,odd=0,mask=0,palette=0,ccr=31)
 scenarios=[{},dict(mask=0x55),dict(odd=1),dict(width=4,height=200,sy=256,sx=256,yp=255,reset=1),
  dict(width=256,height=1,x=0,sx=256),dict(sy=0),dict(sy=65535),dict(sx=0),dict(yp=255,reset=0),
  dict(width=1,height=1),dict(width=100,height=200,x=0,sy=256,sx=256,opaque=True)]
 for layout in(0,1):
  for number,changes in enumerate(scenarios):
   case=dict(base,**changes);encoded=stream(case['width']*case['height'],number,case.get('opaque',False))
   old=Guest(ROOT/'data/original/Monkey_Island',layout);new=Guest(image,layout,meta)
   for visit in range(3):
    live=dict(case,mask=(case['mask']if visit<2 else case['mask']^0x55),palette=visit*17)
    old.setup(live,encoded,number);new.setup(live,encoded,number)
    assert old.draw()==new.draw(),(layout,number,visit,case)
   ctx=new.addr('_nv_costume_cache');hits=u32(new.cpu,ctx+36)
   if number!=len(scenarios)-1:assert hits>=1,(layout,number,'not cached')
   new.call(new.addr('_nv_driver_end'));new.call(new.addr('_nv_driver_end'))
   assert new.alloc==[65536]and new.free==[(ARENA,65536)]
   results.append(dict(layout=layout,scenario=changes,hits=hits))
 # Reallocation, mutation and alias guards run without a framebuffer write.
 encoded=stream(base['width']*base['height'],42)
 guards=[
  ('freed owner',lambda c,g:put32(c,0x940000+48*4,0),True),
  ('shorter reallocation',lambda c,g:c.mem_write(SOURCE-6,struct.pack('<I',22)),True),
  ('wrong type',lambda c,g:c.mem_write(SOURCE-2,b'\x01'),True),
  ('source end',lambda c,g:put32(c,g+0x59b8,SOURCE+len(encoded)),True),
  ('changed first byte',lambda c,g:c.mem_write(SOURCE,bytes((encoded[0]^1,))),False),
  ('changed last byte',lambda c,g:c.mem_write(SOURCE+len(encoded)-1,bytes((encoded[-1]^1,))),False),
  ('output globals',lambda c,g:put32(c,g+0x5c16,g+0x6000),True),
  ('output source',lambda c,g:put32(c,g+0x5c16,SOURCE),True),
  ('output mask',lambda c,g:put32(c,g+0x5c16,MASK),True),
  ('output arena',lambda c,g:put32(c,g+0x5c16,ARENA),True),
  ('mask arena',lambda c,g:put32(c,g+0x5c22,ARENA),True),
  ('resume',lambda c,g:c.mem_write(g+0x6dfa,b'\x01'),True),
  ('left clipped',lambda c,g:(c.mem_write(g+0x6dfc,b'\xff\xff'),c.mem_write(g+0x6df2,b'\x00\x00')),True),
  ('reset Y',lambda c,g:c.mem_write(g+0x6e02,b'\x41'),True),
  ('X scale',lambda c,g:c.mem_write(g+0x59ac,b'\x00\x7f'),True),
  ('height zero',lambda c,g:c.mem_write(g+0x6ded,b'\x00'),True),
 ]
 for name,change,no_source_reads in guards:
  new=Guest(image,0,meta)
  for _ in range(2):new.setup(base,encoded,42);new.draw()
  new.setup(base,encoded,42);change(new.cpu,new.g);reads=[]
  def source_reads(cpu,access,p,n,value,unused):
   if SOURCE<=p<SOURCE+len(encoded):reads.append((p,n))
  hook=new.cpu.hook_add(unicorn.UC_HOOK_MEM_READ,source_reads)
  frame=bytes(new.cpu.mem_read(FRAME-16,0x20020))
  new.call(new.addr('_nv_costume_cache_begin'),(0,));new.cpu.hook_del(hook)
  assert new.cpu.reg_read(R.UC_M68K_REG_D0)in(0,0xffffffff),name
  assert bytes(new.cpu.mem_read(FRAME-16,0x20020))==frame,name
  if no_source_reads:assert not reads,(name,reads[:3])
  new.call(new.addr('_nv_driver_end'))
 for target in('_nv_costume_cache','_nv_control'):
  for field in(0x5c16,0x5c22):
   new=Guest(image,0,meta)
   for _ in range(2):new.setup(base,encoded,42);new.draw()
   new.setup(base,encoded,42);put32(new.cpu,new.g+field,new.addr(target))
   context=bytes(new.cpu.mem_read(new.addr('_nv_costume_cache'),76))
   new.call(new.addr('_nv_costume_cache_begin'),(0,))
   assert new.cpu.reg_read(R.UC_M68K_REG_D0)==0xffffffff
   assert bytes(new.cpu.mem_read(new.addr('_nv_costume_cache'),76))==context
   new.call(new.addr('_nv_driver_end'))
 # An entry larger than the entire arena must not repeatedly pay recording
 # overhead.  After two failed attempts its resident history key is negative.
 oversized=dict(base,width=100,height=200,x=0,sx=256,sy=256)
 encoded=stream(20000,73,opaque=True)
 old=Guest(ROOT/'data/original/Monkey_Island',0);new=Guest(image,0,meta)
 for visit in range(8):
  old.setup(oversized,encoded,73);new.setup(oversized,encoded,73)
  assert old.draw()==new.draw(),('repeated oversized',visit)
 ctx=new.addr('_nv_costume_cache')
 assert u32(new.cpu,ctx+72)==2,'Oversized key retried recording without a bound'
 assert u32(new.cpu,ctx+68)>=4,'Oversized key did not use negative admission'
 assert u32(new.cpu,ctx+40)==0,'Oversized entry was published'
 new.call(new.addr('_nv_driver_end'))
 # Allocation failure is optional, has no Chip retry, and keeps exact rendering.
 old=Guest(ROOT/'data/original/Monkey_Island',0);new=Guest(image,0,meta,fail=True)
 encoded=stream(base['width']*base['height'],42)
 old.setup(base,encoded,42);new.setup(base,encoded,42);assert old.draw()==new.draw()
 new.call(new.addr('_nv_driver_end'));assert new.alloc==list(range(65536,16383,-4096))and not new.free
 # Synthetic OS/CPU publication matrix.  The emulator remains a68000 to
 # catch any accidental privileged cache instruction in a supposedly portable path.
 publication=[]
 for layout in(0,1):
  for flags in(0,1,2,3,0x83):
   for version in(34,36,37,40):
    old=Guest(ROOT/'data/original/Monkey_Island',layout)
    new=Guest(image,layout,meta,attn_flags=flags,exec_version=version)
    admitted=not(flags&2)or version>=37;needs_flush=bool(flags&2)and version>=37
    original=stream(base['width']*base['height'],42)
    changed=bytes((original[0]^0x10,))+original[1:]
    for visit,encoded in enumerate((original,original,original,changed,changed)):
     live=dict(base,mask=0 if visit<3 else 0x55,palette=visit*17)
     old.setup(live,encoded,42);new.setup(live,encoded,42)
     assert old.draw()==new.draw(),('publication',layout,flags,version,visit)
     expected=(0 if visit==0 else 1 if visit<3 else 2)if needs_flush else 0
     assert len(new.flushes)==expected,('flush count',layout,flags,version,visit,new.flushes)
    if admitted:
     assert new.alloc==[65536]and new.generated_instructions>0
     if needs_flush:
      assert [event['builds_before']for event in new.flushes]==[0,1]
      assert new.flushes[0]['plan']==new.flushes[1]['plan'],'Reused address must be flushed again'
    else:assert not new.alloc and not new.flushes and not new.generated_instructions
    new.call(new.addr('_nv_driver_end'));new.call(new.addr('_nv_driver_end'))
    assert new.free==([(ARENA,65536)]if admitted else[])
    publication.append(dict(layout=layout,attn_flags=flags,exec_version=version,
     admitted=admitted,flushes=len(new.flushes),generated_instructions=new.generated_instructions))
 report=dict(cases=len(results)*3+len(guards)+4+8+1+5*len(publication),all_registers_CCR_framebuffer_globals_masks_palette_read_order_exact=True,
  synthetic_inputs=True,no_captured_RAM_or_previous_build_dependency=True,allocation_failure_no_Chip_retry=True,
  repeated_oversized_maximum_record_attempts=2,
  compiled_publication_profiles=publication,flush_before_publish_and_every_reuse=True,
  image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),scenarios=results)
 (BUILD/'cache-validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items()if k!='scenarios'},indent=2))
if __name__=='__main__':main()
