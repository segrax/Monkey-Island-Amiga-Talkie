"""Bounded synthetic resource, occlusion and live-placement cache regressions."""
from pathlib import Path
import sys,json,random,hashlib,struct
sys.path.insert(0,str(Path(__file__).resolve().parent))
from test_cache import Guest,ROOT,BUILD,engine_build,stream,put32,u32,FRAME,MASK,ARENA,SOURCE,unicorn,R

BASE=dict(width=24,height=62,x=121,sx=128,sy=128,xp=104,yp=66,reset=67,
          odd=0,mask=0,palette=0,ccr=31)

def compare(old,new,case,encoded,seed,destination=FRAME,relocate=False,table_only=False):
 """Compare all registers/CCR/output plus exact ordered palette reads and writes."""
 rng=random.Random(seed)
 mask=bytes(rng.randrange(256) for _ in range(0x3000))
 palette=bytes(rng.randrange(256) for _ in range(16))
 writes=[]
 for guest in(old,new):
  guest.setup(case,encoded,seed)
  cpu=guest.cpu;g=guest.g
  cpu.mem_write(MASK,mask);cpu.mem_write(g+0x5cdb,palette)
  put32(cpu,g+0x5c16,destination)
  if relocate or table_only:
   table=0x950000;source=0x910006 if relocate else SOURCE
   cpu.mem_write(table,bytes(199*4));put32(cpu,table+48*4,source-6)
   put32(cpu,g+0x2778,table)
   if relocate:
    cpu.mem_write(source-6,struct.pack('<I',len(encoded)+6)+bytes((2,48))+encoded)
    put32(cpu,g+0x59b4,source-6);put32(cpu,g+0x59b8,source)
  ordered=[]
  def written(cpu,access,address,size,value,unused):
   if FRAME-16<=address<FRAME-16+0x20020:
    delta=address-destination
    assert size==1 and delta>=0 and delta//320<case['height'] and delta%320<case['width'],('write bound',hex(address),size)
    ordered.append((address-FRAME,size,value))
  hook=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,written)
  try:state=guest.draw()
  finally:cpu.hook_del(hook)
  writes.append((state,ordered))
 assert writes[0]==writes[1],('differential',seed,case,destination,relocate,table_only)
 return len(writes[1][1])

def main():
 image=engine_build()/'module/Monkey_Talkie_Test'
 meta=json.loads(image.with_name('module.json').read_text());results=[];rejections=0
 for layout in(0,1):
  old=Guest(ROOT/'data/original/Monkey_Island',layout);new=Guest(image,layout,meta)
  encoded=stream(BASE['width']*BASE['height'],42);ctx=new.addr('_nv_costume_cache')
  for visit in range(6):
   case=dict(BASE,x=121+8*max(0,visit-2),ccr=(visit*7)&31)
   before=u32(new.cpu,ctx+36)
   count=compare(old,new,case,encoded,100+visit,FRAME+visit*320+visit*8,table_only=visit==5)
   if visit>=2:assert u32(new.cpu,ctx+36)==before+1,'Placement/mask/palette should retain the key'
   assert u32(new.cpu,ctx+40)==(0 if visit==0 else 1)
   results.append(dict(layout=layout,scenario='live placement/mask/palette',visit=visit,writes=count))
  new.call(new.addr('_nv_driver_end'))
  old=Guest(ROOT/'data/original/Monkey_Island',layout);new=Guest(image,layout,meta);ctx=new.addr('_nv_costume_cache')
  changed=bytes((encoded[0]^0x10,))+encoded[1:]
  for visit,data in enumerate((encoded,encoded,encoded,changed,changed)):
   count=compare(old,new,BASE,data,200+visit)
   assert u32(new.cpu,ctx+40)==(0 if visit==0 else 1 if visit<3 else 2),'Changed bytes at same address must rebuild'
   if visit in(2,4):assert u32(new.cpu,ctx+36)==(1 if visit==2 else 2)
   results.append(dict(layout=layout,scenario='allocation address/extent reused',visit=visit,writes=count))
  # Replacing the registration/table must reject the old source before comparing it.
  new.setup(BASE,changed,42);cpu=new.cpu;g=new.g
  cpu.mem_write(0x950000,bytes(199*4));put32(cpu,0x950000+48*4,0x910000);put32(cpu,g+0x2778,0x950000)
  before=bytes(cpu.mem_read(FRAME-16,0x20020));reads=[]
  def source_read(cpu,access,address,size,value,unused):
   if SOURCE<=address<SOURCE+len(changed):reads.append((address,size))
  hook=cpu.hook_add(unicorn.UC_HOOK_MEM_READ,source_read)
  try:new.call(new.addr('_nv_costume_cache_begin'),(0,))
  finally:cpu.hook_del(hook)
  assert new.cpu.reg_read(R.UC_M68K_REG_D0)==0xffffffff
  assert not reads and bytes(cpu.mem_read(FRAME-16,0x20020))==before
  rejections+=1
  for visit in range(3):
   before=u32(cpu,ctx+36)
   count=compare(old,new,BASE,changed,300+visit,relocate=True)
   assert u32(cpu,ctx+40)==(2 if visit==0 else 3)
   if visit==2:assert u32(cpu,ctx+36)==before+1
   results.append(dict(layout=layout,scenario='registered resource/table relocated',visit=visit,writes=count))
  new.call(new.addr('_nv_driver_end'));assert new.free==[(ARENA,65536)]
 report=dict(cases=len(results),registration_rejections=rejections,
  all_registers_CCR_framebuffer_globals_masks_palette_reads_ordered_writes_exact=True,
  destination_row_bounds_guarded=True,synthetic_inputs=True,
  image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),results=results)
 (BUILD/'cache-extended-validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='results'},indent=2))
if __name__=='__main__':main()
