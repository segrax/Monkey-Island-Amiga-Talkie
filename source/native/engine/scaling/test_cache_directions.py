"""Compare both draw directions, including signed displacement extremes."""
from pathlib import Path
import sys,json,random,struct,hashlib
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'engine/scaling'))
from test_cache import Guest,stream,put32,u32,FRAME,MASK,SOURCE,unicorn
from paths import artifact_dir,engine_build
build=artifact_dir('scaling');image=engine_build()/'module/Monkey_Talkie_Test'
if not image.exists():image=build/'Monkey_Talkie_Scaled'
meta=json.loads(image.with_name('module.json').read_text())
base=dict(width=24,height=62,x=121,sx=128,sy=128,xp=104,yp=66,reset=67,odd=0,mask=0,palette=0,ccr=31)
def sparse(n,index):
 out=bytearray()
 for count,color in ((index,0),(1,1),(n-index-1,0)):
  while count:
   k=min(count,256);out.append(color<<4|(k if k<16 else 0))
   if k>=16:out.append(k&255)
   count-=k
 return bytes(out)
scenarios=[{},dict(odd=1),dict(sx=256,sy=256),dict(width=4,height=200,x=31,sy=256,yp=255,reset=1),
 dict(width=256,height=1,x=255,sx=256,sy=256,sparse_at=255),
 dict(width=256,height=200,x=255,sx=256,sy=256,sparse_at=51000),
 dict(width=256,height=200,x=0,sx=256,sy=256,sparse_at=51199,direction=1),
 dict(x=23,sx=256),dict(width=1,height=1,x=0)]
results=[]
for layout in(0,1):
 for number,changes in enumerate(scenarios):
  case=dict(base,**changes);direction=case.get('direction',-1)
  encoded=sparse(case['width']*case['height'],case['sparse_at']) if 'sparse_at'in case else stream(case['width']*case['height'],number)
  old=Guest(root/'data/original/Monkey_Island',layout);new=Guest(image,layout,meta)
  for visit in range(3):
   live=dict(case,palette=17*visit);rng=random.Random(1000+visit+number)
   mask=bytes(0 if visit<2 else rng.randrange(256) for _ in range(0x3000))
   for guest in(old,new):
    guest.setup(live,encoded,number);put32(guest.cpu,guest.g+0x5c16,FRAME+256)
    guest.cpu.mem_write(guest.g+0x6dfc,struct.pack('>h',direction));guest.cpu.mem_write(MASK,mask)
   states=[]
   for guest in(old,new):
    ordered=[]
    def writes(cpu,access,address,size,value,unused):
     if FRAME-16<=address<FRAME-16+0x20020:
      relative=address-(FRAME+256)
      row=(relative+case['width']-1)//320 if direction<0 else relative//320
      column=relative-row*320
      assert size==1 and 0<=row<case['height']
      assert 1-case['width']<=column<=0 if direction<0 else 0<=column<case['width']
      ordered.append((address,size,value))
    hook=guest.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,writes)
    try:state=guest.draw()
    finally:guest.cpu.hook_del(hook)
    states.append((state,ordered))
   assert states[0]==states[1],(layout,number,visit,case)
  ctx=new.addr('_nv_costume_cache');assert u32(new.cpu,ctx+36)>=1,(layout,number,'not cached')
  assert new.generated_instructions>0
  results.append(dict(layout=layout,scenario=case,hits=u32(new.cpu,ctx+36)))
report=dict(cases=len(results)*3,ordered_writes_and_destination_row_bounds=True,all_registers_CCR_framebuffer_globals_masks_palette_order_exact=True,
 image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),scenarios=results)
(build/'cache-direction-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print({k:v for k,v in report.items()if k!='scenarios'})
