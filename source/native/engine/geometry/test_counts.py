from pathlib import Path
import sys,json,struct,random,hashlib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
P=artifact_dir('geometry');S=artifact_dir('scaling');m=json.loads((P/'generation.json').read_text());rng=random.Random(0xf192)
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments();hunks={h['hunk_no']:h['data'] for h in r.hunks if 'data'in h}
blob=bytearray((P/'geometry.bin').read_bytes())
for off in m['prefix_relocations']:struct.pack_into('>I',blob,off,0x500000)
prefix=bytearray((S/'scale_prefix.bin').read_bytes());sm=json.loads((S/'generation.json').read_text())
for off in sm['prefix_pointer_offsets']:struct.pack_into('>I',prefix,off,int.from_bytes(prefix[off:off+4],'big')+0x500000)
linked=False;image=P.parent/'module/Monkey_Talkie_Test'
if image.exists():
 meta=json.loads(image.with_name('module.json').read_text())
 if 'engine_geometry_counts' in meta:
  linked=True;q=HunkReader();assert q.read_file(str(image))==0 and q.build_segments();index=meta['exports']['_x_offset']['hunk'];section=0
  linked_code=bytearray(next(h['data'] for h in q.hunks if h.get('hunk_no')==0 and 'data'in h))
  linked_blob=bytearray(next(h['data'] for h in q.hunks if h.get('hunk_no')==index and 'data'in h))
  for h in q.hunks:
   section=h.get('hunk_no',section)
   if h['type_name']=='HUNK_ABSRELOC32':
    if section==0:
     for off in h['reloc'].get(index,[]):struct.pack_into('>I',linked_code,off,int.from_bytes(linked_code[off:off+4],'big')+0x400000)
    if section==index:
     assert set(h['reloc'])=={meta['engine_geometry_counts']['prefix_hunk']}
     for off in next(iter(h['reloc'].values())):struct.pack_into('>I',linked_blob,off,int.from_bytes(linked_blob[off:off+4],'big')+0x500000)
  blob=linked_blob
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0,0x1000000);cpu.mem_write(0x100000,hunks[0]);cpu.mem_write(0x400000,bytes(blob));
if linked:cpu.mem_write(0x200000,bytes(linked_code))
cpu.mem_write(0x500000,bytes(prefix))
cases=[(50,128,p,0) for p in range(256)]
for n in (0,1,15,16,17,255,256,257,1023,32767,32768,65535):
 for scale in (0,1,127,128,129,254,255,256,32767,32768,65535):cases.append((n,scale,rng.randrange(256),0))
for _ in range(64):cases.append((rng.randrange(512),rng.randrange(65536),rng.randrange(256),rng.randrange(4)))
for _ in range(64):cases.append((rng.randrange(65536),rng.randrange(65536),rng.randrange(256),0))
profiles=[];total=0
for loop in m['loops']:
 for number,(n,scale,phase,counter) in enumerate(cases):
  g=0x700000;frame=0x90f800;stack=0x90f000;initial=[rng.getrandbits(32) for _ in regs];initial[12]=g;initial[13]=frame;initial[15]=stack;out=[];counts=[];ccr=number&31;direction=rng.choice((0,1,2,65535,32768));coordinate=rng.randrange(65536)
  for fast in (False,True):
   cpu.mem_write(g,bytes(0x8000));cpu.mem_write(g,hunks[2]);cpu.mem_write(stack-256,bytes(0x1000));cpu.mem_write(stack,struct.pack('>I',0xa00000))
   def put(at,value):cpu.mem_write(at,struct.pack('>H',value))
   for off,value in ((0x59ac,scale),(0x59ae,scale),(0x6de8,n),(0x6dea,n),(0x6dfc,direction),(0x6dfe,direction),(0x6df2,coordinate),(0x6df4,coordinate),(0x6dd8,coordinate),(0x6dda,coordinate),(0x6dde,coordinate)):put(g+off,value)
   cpu.mem_write(g+0x6e00,bytes([phase,phase]));put(frame-2,counter);put(frame-4,n);put(frame-6,n)
   cpu.reg_write(R.UC_M68K_REG_SR,ccr)
   for reg,value in zip(regs,initial):cpu.reg_write(reg,value)
   instructions=[0]
   def trace(*args):instructions[0]+=1
   def guard(uc,access,address,size,value,unused):assert g<=address and address+size<=g+0x8000 or stack-256<=address and address+size<=stack or frame-2<=address and address+size<=frame,(loop['name'],number,hex(address),size)
   wh=cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,guard)
   # Count representative traces; avoid Python code callbacks on long cases.
   ch=cpu.hook_add(unicorn.UC_HOOK_CODE,trace) if number==66 else None
   cpu.ctl_remove_cache(0,0xffffff)
   stop=(0x200000+loop['end'] if linked else 0xa00000) if fast else 0x100000+loop['end'];entry=(0x200000+loop['start'] if linked else 0x400000+m['entries']['_'+loop['name']]) if fast else 0x100000+loop['start']
   cpu.emu_start(entry,stop,count=2000000);cpu.hook_del(wh)
   if ch is not None:cpu.hook_del(ch)
   assert cpu.reg_read(R.UC_M68K_REG_PC)==stop,(loop['name'],number,fast)
   assert cpu.reg_read(R.UC_M68K_REG_A7)==stack+(4 if fast and not linked else 0),(loop['name'],number,fast,hex(cpu.reg_read(R.UC_M68K_REG_A7)))
   state=[cpu.reg_read(r) for r in regs];state[-1]=stack
   cpu.mem_write(0xa00000,bytes.fromhex('40f900a00100'));cpu.emu_start(0xa00000,0xa00006,count=1)
   out.append((state,bytes(cpu.mem_read(0xa00100,2)),bytes(cpu.mem_read(g,0x8000)),bytes(cpu.mem_read(frame-6,6))))
   counts.append(instructions[0])
  assert out[0]==out[1],(loop['name'],number,n,scale,phase,counter,[(i, a if i<2 else 'memory',b if i<2 else 'memory') for i,(a,b) in enumerate(zip(*out)) if a!=b])
  total+=1
  if number==66:profiles.append(dict(loop=loop['name'],n=n,scale=scale,phase=phase,old_instructions=counts[0],new_instructions=counts[1]))
report=dict(cases=total,linked_original_entries_and_relocations=linked,all_registers_CCR_globals_locals_exact=True,all_phases=True,full_cycles_and_thresholds=True,guarded_writes=True,profiles=profiles)
(P/'validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
