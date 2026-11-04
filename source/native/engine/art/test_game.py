"""Exercise linked ART guards, original caller ABI and one-use decode admission.

The file, resources, allocation map and operating-system calls are synthetic.
The retained original instructions independently check registers, flags and output.
"""
from pathlib import Path
import sys,json,struct,hashlib,random
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT/'engine'),str(ROOT/'tools/python')]
from paths import engine_build,artifact_dir
import argparse
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate',type=Path,default=engine_build()/'module/Monkey_Talkie_Test')
args=parser.parse_args()
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
MODULE=args.candidate
META=json.loads((MODULE.parent/'module.json').read_text())
assert hashlib.sha256(MODULE.read_bytes()).hexdigest()==META['sha256']
def synthetic_artifact(specs=((113,8),)):
 palette=bytes([16,0]+list(range(18,32)))
 color=palette[2]
 planes=bytes(255 if color&(1<<bit)else 0 for bit in(0,1,3,4,2))
 payloads=[]
 for obj,height in specs:
  source=struct.pack('<I',19)+b'OI'+struct.pack('<H',obj)+bytes(4)+struct.pack('<I',8)+bytes((10,2,height*8))
  dictionary=72;indices=86;source_offset=indices+height*2
  masks=(source_offset+len(source)+1)&~1;size=(masks+(height+7)//8+1)&~1
  payload=bytearray(size)
  struct.pack_into('>4sHHIHHHHIIIIIIHH',payload,0,b'NPD1',1,64,size,8,height,1,14,height,dictionary,indices,source_offset,len(source),64,1,3)
  payload[48:64]=palette;struct.pack_into('>IHH',payload,64,16,3,0)
  payload[dictionary:dictionary+14]=bytes([color])*8+planes+b'\0'
  payload[source_offset:source_offset+len(source)]=source
  a=total=65535
  for offset in range(0,size,2):a+=int.from_bytes(payload[offset:offset+2],'big');total+=a
  checksum=((total%65535 or 65535)<<16)|(a%65535 or 65535)
  payloads.append((obj,height,bytes(payload),checksum))
 data_offset=32+len(payloads)*24;offset=data_offset;entries=bytearray();data=bytearray()
 for obj,height,payload,checksum in payloads:
  entries+=struct.pack('>HHIIIHHI',10,obj,offset,len(payload),19,8,height,checksum)
  data+=payload;offset+=len(payload)
 header=struct.pack('>8sHHIIIII',b'NVPART01',1,24,len(payloads),32,data_offset,offset,0)
 return header+entries+data
ART=synthetic_artifact()
r=HunkReader();assert r.read_file(str(MODULE))==0 and r.build_segments()
BASES={};cursor=0x100000
for n,x in enumerate(r.hunks[0]['hunks']):BASES[n]=cursor;cursor+=(x['size']+65535)&~65535
IMAGES={x['hunk_no']:bytearray(x['data'])for x in r.hunks if'data'in x};sec=0
for x in r.hunks:
 sec=x.get('hunk_no',sec)
 if x['type_name']in('HUNK_ABSRELOC32','HUNK_RELOC32SHORT'):
  for target,offs in x['reloc'].items():
   for off in offs:struct.pack_into('>I',IMAGES[sec],off,struct.unpack_from('>I',IMAGES[sec],off)[0]+BASES[target])
def addr(n):e=META['exports'][n];return BASES[e['hunk']]+e['offset']
C,G=BASES[0],BASES[2]
ARENA,INDEX,OWNER,TABLE,PRIMARY,BACKUP,MASK,LUT,BITMAP,STACK,STOP,SRSTORE=(0x400000,0x410000,0x500000,0x520000,0x600000,0x620000,0x640000,0x660000,0x680000,0xa0f000,0xb00000,0xb00100)
REGS=[getattr(R,'UC_M68K_REG_'+q)for q in['D'+str(i)for i in range(8)]+['A'+str(i)for i in range(8)]]
def be32(c,p,n):c.mem_write(p,struct.pack('>I',n))
def be16(c,p,n):c.mem_write(p,struct.pack('>H',n))
def u32(c,p):return int.from_bytes(c.mem_read(p,4),'big')
def u16(c,p):return int.from_bytes(c.mem_read(p,2),'big')
for n in range(int.from_bytes(ART[12:16],'big')):
 entry=struct.unpack_from('>HHIIIHHI',ART,32+24*n)
 if entry[:2]==(10,113):break
else:raise AssertionError('owned fixture absent')
ROOM,OBJ,OFF,SIZE,SOURCEBYTES,WIDTH,HEIGHT,CHECKSUM=entry
PAYLOAD=ART[OFF:OFF+SIZE];DICT,INDICES,SOURCE,STRIPS=[int.from_bytes(PAYLOAD[o:o+4],'big')for o in(24,28,32,40)]
CODECOFF=int.from_bytes(PAYLOAD[STRIPS:STRIPS+4],'big')
class Fixture:
 def __init__(self,missing=False,failalloc=False,short=False,corrupt=False,artifact=None,failindex=False,failfast=False):
  self.cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);self.cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);self.cpu.mem_map(0,0x1000000)
  c=self.cpu
  for n,data in IMAGES.items():c.mem_write(BASES[n],bytes(data))
  self.allocs=[];self.frees=[];self.reads=[];self.closed=[];self.missing=missing;self.failalloc=failalloc;self.failindex=failindex;self.failfast=failfast;self.short=short;self.art=bytearray(ART if artifact is None else artifact)
  if corrupt:self.art[OFF+DICT]^=1
  self.io={addr(n):n for n in('_nv_costume_alloc','_nv_art_alloc','_nv_art_alloc_any','_nv_art_free','_nv_art_file_open','_nv_art_file_close','_nv_art_read_at')if n in META['exports']}
  c.hook_add(unicorn.UC_HOOK_CODE,self.iohook)
  be32(c,4,0x8000);be32(c,0x8000+322,0x8200);be32(c,0x8200,0x8240);be32(c,0x8240,0);be32(c,0x8200+20,0x10000);be32(c,0x8200+24,0xc00000)
  be32(c,addr('_nv_control')+12,C);be32(c,addr('_nv_control')+16,G)
  self.call('_nv_art_game_start')
 def iohook(self,c,pc,size,unused):
  if pc not in self.io:return
  n=self.io[pc];sp=c.reg_read(R.UC_M68K_REG_A7);a=[u32(c,sp+4*i)for i in range(1,5)];result=0
  if n in('_nv_art_alloc','_nv_art_alloc_any','_nv_costume_alloc'):
   self.allocs.append(a[0]);result=0 if self.failalloc or (self.failfast and n=='_nv_art_alloc'and a[0]==32768)or (self.failindex and n=='_nv_art_alloc'and a[0]!=32768)else (0x700000 if n=='_nv_costume_alloc'else 0x40000 if n=='_nv_art_alloc_any'else ARENA if a[0]==32768 else INDEX)
   if result:c.mem_write(result,bytes(a[0]))
  elif n=='_nv_art_free':self.frees.append(tuple(a[:2]))
  elif n=='_nv_art_file_open':result=0 if self.missing else 1
  elif n=='_nv_art_file_close':self.closed.append(a[0])
  else:
   file,offset,dst,count=a;self.reads.append((offset,count));result=count
   if file!=1 or offset>len(self.art) or count>len(self.art)-offset:result=0xffffffff
   else:
    if self.short and offset==OFF:result=count-1
    c.mem_write(dst,bytes(self.art[offset:offset+(count if result==count else max(0,result))]))
  c.reg_write(R.UC_M68K_REG_D0,result);c.reg_write(R.UC_M68K_REG_PC,u32(c,sp));c.reg_write(R.UC_M68K_REG_A7,sp+4)
 def call(self,n,args=()):
  c=self.cpu;c.reg_write(R.UC_M68K_REG_A7,STACK);c.mem_write(STACK,struct.pack('>'+str(len(args)+1)+'I',STOP,*args));c.emu_start(addr(n)if isinstance(n,str)else n,STOP,count=5000000);assert c.reg_read(R.UC_M68K_REG_PC)==STOP,(n,hex(c.reg_read(R.UC_M68K_REG_PC)));return c.reg_read(R.UC_M68K_REG_D0)
 def setup(self):
  c=self.cpu
  c.mem_write(OWNER,struct.pack('<I',SOURCEBYTES+6)+bytes((3,ROOM))+PAYLOAD[SOURCE:SOURCE+SOURCEBYTES]);c.mem_write(TABLE,bytes(256*4));be32(c,TABLE+ROOM*4,OWNER)
  for base,bytes_,id_ in((PRIMARY,64006,1),(BACKUP,64006,5),(MASK,8006,9)):
   c.mem_write(base,struct.pack('<I',bytes_)+bytes((4,id_))+bytes(bytes_-6))
  for off,value,size in((0x19f9,ROOM,1),(0x68e8,1,1),(0x235a,256,2),(0x2368,TABLE,4),(0x1dae+4,14,4),(0x2784,PRIMARY,4),(0x2794,BACKUP,4),(0x27a4,MASK,4),(0x5c38,HEIGHT,1),(0x5c34,0,2),(0x5c32,0,2),(0x5992,0,2),(0x5d40,0,2),(0x5c1e,PRIMARY+6,4),(0x5c1a,BACKUP+6,4),(0x5c2a,OWNER+6+CODECOFF,4),(0x16f8,LUT,4),(0x16f5,0,1),(0x706e,BITMAP,4),(0x6fee,BITMAP,4),(0x5ebe,0,2)):
   c.mem_write(G+off,value.to_bytes(size,'big'))
  self.call(C+0x15418,(LUT,))
  self.call('_nv_art_game_object',(STACK,));assert u16(c,addr('_nv_art')+80)==1
  self.call('_nv_art_game_bind',(0,STACK));assert u16(c,addr('_nv_art_decode_ready'))==1
  for row in range(HEIGHT):
   index=int.from_bytes(PAYLOAD[INDICES+row*2:INDICES+row*2+2],'big');c.mem_write(PRIMARY+6+row*320,PAYLOAD[DICT+index:DICT+index+8])
 def regs(self):
  c=self.cpu;c.mem_write(STOP,bytes.fromhex('40f900b00100'));c.emu_start(STOP,STOP+6,count=1);return tuple(c.reg_read(r)for r in REGS),bytes(c.mem_read(SRSTORE,2))
RESULTS=[]
def result(name,**kw):RESULTS.append(dict(name=name,**kw));print(name,kw,flush=True)
f=Fixture();f.setup();assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))==1;result('valid registered C2P')
for name,change in [
('ROM table',lambda c:be32(c,G+0x2368,0xf80000)),('IO table',lambda c:be32(c,G+0x2368,0xdff000)),('count zero',lambda c:be16(c,G+0x235a,0)),
('owner moved',lambda c:be32(c,TABLE+ROOM*4,OWNER+2)),('source offset changed',lambda c:be32(c,G+0x1db2,16)),('slot changed',lambda c:c.mem_write(G+0x68e8,b'\x02')),
('short primary',lambda c:c.mem_write(PRIMARY,struct.pack('<I',8))),('backup overlaps primary',lambda c:be32(c,G+0x2794,PRIMARY)),('backup ROM',lambda c:be32(c,G+0x2794,0xf80000)),('mask IO',lambda c:be32(c,G+0x27a4,0xdff000)),
('bad codec',lambda c:c.mem_write(OWNER+6+CODECOFF,b'\x00')),('height zero',lambda c:c.mem_write(G+0x5c38,b'\x00'))]:
 f=Fixture();f.setup();c=f.cpu;c.mem_write(addr('_nv_art_decode_ready'),b'\x00\x00');before=bytes(c.mem_read(addr('_nv_art_decode'),28));change(c);reads=[]
 def rd(uc,access,p,n,value,u):
  if p>=0xdff000:reads.append((p,n))
 hook=c.hook_add(unicorn.UC_HOOK_MEM_READ,rd);f.call('_nv_art_game_bind',(0,STACK));c.hook_del(hook)
 assert not reads,(name,reads);assert not u16(c,addr('_nv_art_decode_ready')),(name,'armed');assert bytes(c.mem_read(addr('_nv_art_decode'),28))==before
 result('bind rejects '+name)
for name,src,dst,h,stack,change in [
('wrong display owner',PRIMARY+6,0x700000,HEIGHT,STACK,lambda c:None),('output source',PRIMARY+6,PRIMARY+6,HEIGHT,STACK,lambda c:None),('output LUT',PRIMARY+6,LUT,HEIGHT,STACK,lambda c:None),('output ART arena',PRIMARY+6,ARENA,HEIGHT,STACK,lambda c:None),('output native control',PRIMARY+6,addr('_nv_control'),HEIGHT,STACK,lambda c:None),('output stack',PRIMARY+6,STACK-100,HEIGHT,STACK,lambda c:None),('source ROM',0xf80000,BITMAP,HEIGHT,STACK,lambda c:None),('source odd',PRIMARY+7,BITMAP,HEIGHT,STACK,lambda c:None),('height0',PRIMARY+6,BITMAP,0,STACK,lambda c:None),('height201',PRIMARY+6,BITMAP,201,STACK,lambda c:None),('plane end',PRIMARY+6,BITMAP+7999,2,STACK,lambda c:None),('bad flip',PRIMARY+6,BITMAP,HEIGHT,STACK,lambda c:c.mem_write(G+0x16f5,b'\x02')),('LUT owner mismatch',PRIMARY+6,BITMAP,HEIGHT,STACK,lambda c:be32(c,G+0x16f8,LUT+2)),('stack underflow',PRIMARY+6,BITMAP,HEIGHT,0,lambda c:None)]:
 f=Fixture();f.setup();assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK));change(f.cpu);assert f.call('_nv_art_game_c2p',(src,dst,h,stack))==0,name;result('C2P rejects '+name)
for name,kwargs in [('missing',dict(missing=True)),('alloc fail',dict(failalloc=True)),('short payload',dict(short=True))]:
 f=Fixture(**kwargs)
 if not kwargs.get('missing')and not kwargs.get('failalloc'):
  # Original-source setup does not depend on whether payload load is admitted.
  try:f.setup()
  except AssertionError:pass
 assert not u16(f.cpu,addr('_nv_art')+80),name;result('fallback '+name,frees=f.frees)
def runhook(f,kind,fast,ccr=31,miss=False,unbound=False):
 c=f.cpu
 if not fast:
  old={'object':(0x516a,'3b40fff66000008e'),'bind':(0x4ac4,'7000102c5c38'),'c2p':(0x14e72,'4eba051c4fef000e')}[kind];c.mem_write(C+old[0],bytes.fromhex(old[1]))
 if miss:c.mem_write(PRIMARY+6+320*3,b'\x01\x02\x03\x04\x05\x06\x07\x08')
 if unbound:c.mem_write(addr('_nv_art_columns'),bytes(40))
 rng=random.Random(514);values=[rng.randrange(1<<32)for _ in REGS];values[12]=G;values[13]=0x900100;values[15]=STACK;values[7]=0
 c.reg_write(R.UC_M68K_REG_SR,ccr)
 for reg,v in zip(REGS,values):c.reg_write(reg,v)
 if kind=='c2p':c.mem_write(STACK,struct.pack('>IIIH',BITMAP,PRIMARY+6,PRIMARY+6,HEIGHT));start,end=0x14e72,0x14e7a
 elif kind=='object':start,end=0x516a,0x51fe
 else:start,end=0x4ac4,0x4aca
 c.emu_start(C+start,C+end,count=5000000);assert c.reg_read(R.UC_M68K_REG_PC)==C+end
 return f.regs(),bytes(c.mem_read(BITMAP,40000)),bytes(c.mem_read(G,29312)),bytes(c.mem_read(0x9000e0,48))
for kind in('object','bind','c2p'):
 for ccr in(0,4,16,31):
  for miss,unbound in([(False,False),(True,False),(False,True)]if kind=='c2p'else[(False,False)]):
   a=Fixture();a.setup();b=Fixture();b.setup()
   x=runhook(a,kind,False,ccr,miss,unbound);y=runhook(b,kind,True,ccr,miss,unbound)
   assert x==y,(kind,ccr,miss,unbound,[(i,x[i],y[i])for i in range(len(x))if x[i]!=y[i]][:1])
   result('original hook differential',kind=kind,ccr=ccr,miss=miss,unbound=unbound)
def note(name,**kw):result(name,**kw)
def flow(f,strip=0):
 c=f.cpu;c.reg_write(R.UC_M68K_REG_SR,31);c.reg_write(R.UC_M68K_REG_A7,STACK);c.reg_write(R.UC_M68K_REG_A4,G);c.reg_write(R.UC_M68K_REG_D7,strip)
 events=[]
 def trace(uc,pc,size,u):
  if pc in(C+0x4aca,C+0x4ba2,addr('_nv_art_dispatch'),addr('_nv_continue_art_stripe')):events.append((hex(pc-C),u16(c,addr('_nv_art_decode_ready'))))
 hk=c.hook_add(unicorn.UC_HOOK_CODE,trace);c.emu_start(C+0x4ac4,C+0x4b06,count=5000000);c.hook_del(hk);assert c.reg_read(R.UC_M68K_REG_PC)==C+0x4b06;return events
# Test the real uninterrupted bind->setup->opcode-read->dispatch chain.
f=Fixture();f.setup();c=f.cpu;c.mem_write(G+0x5c49,PAYLOAD[48:64]);c.mem_write(G+0x6812,bytes(PAYLOAD[DICT+int.from_bytes(PAYLOAD[INDICES+row*2:INDICES+row*2+2],'big')]for row in range(HEIGHT)));c.mem_write(addr('_nv_art_decode_ready'),b'\x00\x00');events=flow(f);assert events[0][1]==1 and events[-1][1]==1 and len(events)==3;assert not u16(c,addr('_nv_art_decode_ready'));note('actual valid bind dispatch consumes latch',trace=events)
# A later object refusal cannot inherit the previous consumed latch. Same source,
# different slot, then the actual bind/dispatch flow must retain original fallback.
c.mem_write(G+0x68e8,b'\x02');f.call('_nv_art_game_object',(STACK,));be32(c,G+0x5c2a,OWNER+6+CODECOFF);events=flow(f);assert all(not x[1]for x in events);note('declined next slot leaves latch unarmed',trace=events)
# Owner pointer changes must reject bind without dereferencing non-RAM resources.
f=Fixture();f.setup();flow(f);c=f.cpu;be32(c,TABLE+ROOM*4,0xdff000);be32(c,G+0x5c2a,OWNER+6+CODECOFF);f.call('_nv_art_game_object',(STACK,));events=flow(f);assert all(not x[1]for x in events);note('declined moved owner cannot reuse latch',trace=events)
# Validly armed source mutated between bind and decoder is independently refused by
# wrapper; no precomputed bytes published. Here ordinary original flow stays valid.
f=Fixture();f.setup();flow(f);c=f.cpu;c.mem_write(G+0x5c49,PAYLOAD[48:64]);be32(c,G+0x5c2a,OWNER+6+CODECOFF);c.mem_write(OWNER+6+CODECOFF+1,bytes([c.mem_read(OWNER+6+CODECOFF+1,1)[0]^1]));events=flow(f);assert len(events)==4 and not u16(c,addr('_nv_art_decode_ready'));note('changed compressed source consumed with exact fallback',trace=events)
# Room changes, freed owners, and arena teardown invalidate C2P hints.
f=Fixture();f.setup();c=f.cpu;assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK));f.call('_nv_art_object',(255,65534,2));assert bytes(c.mem_read(addr('_nv_art_columns'),40))==bytes(40);assert not f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK));note('room change clears C2P bindings')
f=Fixture();f.setup();c=f.cpu;be32(c,G+0x2784,0);assert not f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK));note('freed primary owner refuses stale C2P hint')
f=Fixture();f.setup();f.call('_nv_art_game_stop');f.call('_nv_art_game_stop');c=f.cpu;assert not u16(c,addr('_nv_art')+80);assert not u16(c,addr('_nv_art_decode_ready'));assert bytes(c.mem_read(addr('_nv_art_columns'),40))==bytes(40);assert len(f.frees)==2;assert not f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK));note('idempotent stop clears arena binding latch',frees=f.frees)

# Entry validation must remain safe whether metadata is prefetched or searched.
for label,offset,value in [('offset before data',36,32),('offset beyond file',36,len(ART)+2),
                           ('zero payload',40,0),('odd payload',40,SIZE-1),
                           ('payload exceeds file',40,SIZE+2)]:
 malformed=bytearray(ART);struct.pack_into('>I',malformed,offset,value)
 f=Fixture(artifact=malformed)
 admitted=f.call('_nv_art_object',(ROOM,OBJ,1))if u16(f.cpu,addr('_nv_art')+80)else 0
 assert not admitted,label
 assert bytes(f.cpu.mem_read(addr('_nv_art_columns'),40))==bytes(40)
 result('invalid directory fallback '+label)
# Even matching forged bitmap globals cannot admit native state as a display.
for name,base in [('ART arena',ARENA),('ART metadata',INDEX),('native control',addr('_nv_control')),('LUT',LUT),('stack',STACK-200)]:
 f=Fixture();f.setup();c=f.cpu;be32(c,G+0x706e,base);be32(c,G+0x6fee,base)
 assert not f.call('_nv_art_game_c2p',(PRIMARY+6,base,HEIGHT,STACK)),name
 result('forged bitmap ownership rejects '+name)
f=Fixture();f.setup();f.call('_nv_costume_cache_start');c=f.cpu
assert u32(c,addr('_nv_costume_cache')+28)==0x700000
be32(c,G+0x706e,0x700000);be32(c,G+0x6fee,0x700000)
assert not f.call('_nv_art_game_c2p',(PRIMARY+6,0x700000,HEIGHT,STACK))
result('forged bitmap ownership rejects compiled arena')
# An unknown object gate must preserve the same caller state while calling C.
for ccr in(0,31):
 a=Fixture();a.setup();b=Fixture();b.setup();b.cpu.mem_write(addr('_nv_art_object_gate'),bytes(72))
 assert runhook(a,'object',False,ccr)==runhook(b,'object',True,ccr)
 result('unknown object gate original caller differential',ccr=ccr)

f=Fixture(failindex=True);f.setup()
assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
result('optional metadata allocation failure retains file search fallback')
f=Fixture(artifact=synthetic_artifact(((113,8),(114,9))));f.setup();c=f.cpu
assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
assert f.call('_nv_art_object',(ROOM,114,2))
assert u16(c,addr('_nv_art')+78)==114
assert bytes(c.mem_read(addr('_nv_art_columns'),40))==bytes(40)
assert not f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
result('same room larger artifact reuse invalidates old arena bindings')

if META.get('engine_planar_cache',{}).get('allow_chip_fallback'):
 f=Fixture(failfast=True);f.setup();c=f.cpu
 assert u16(c,addr('_nv_art')+82)==256
 assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
 be32(c,G+0x706e,0x40000);be32(c,G+0x6fee,0x40000)
 assert not f.call('_nv_art_game_c2p',(PRIMARY+6,0x40000,HEIGHT,STACK))
 f.call('_nv_art_game_stop');f.call('_nv_art_game_stop')
 assert sorted(f.frees)==sorted([(INDEX,24),(0x40000,32768)])
 result('FAST failure ANY payload fallback lifecycle and alias guards')

checksum_only=bytearray(ART);struct.pack_into('>I',checksum_only,52,CHECKSUM^1)
f=Fixture(artifact=checksum_only);f.setup()
assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
result('trusted generated artifact accepts checksum field only change')

# A room transition can precede every new object hook; the C2P caller must clear
# the prior room binding once and subsequently take its cheap unbound fallback.
a=Fixture();a.setup();b=Fixture();b.setup()
for fixture in(a,b):fixture.cpu.mem_write(G+0x19f9,bytes((ROOM+1,)))
counts={'room':0,'c2p':0}
def gate_calls(cpu,pc,size,unused):
 if pc==addr('_nv_art_game_room'):counts['room']+=1
 if pc==addr('_nv_art_game_c2p'):counts['c2p']+=1
hook=b.cpu.hook_add(unicorn.UC_HOOK_CODE,gate_calls)
assert runhook(a,'c2p',False)==runhook(b,'c2p',True)
assert not u16(b.cpu,addr('_nv_art_decode_ready'))
assert bytes(b.cpu.mem_read(addr('_nv_art_columns'),40))==bytes(40)
assert counts=={'room':1,'c2p':0}
runhook(b,'c2p',True)
assert counts=={'room':1,'c2p':0}
b.cpu.hook_del(hook)
result('actual C2P room transition clears stale hints once',calls=counts)
for name,change in [('primary allocation shrunk',lambda c:c.mem_write(PRIMARY,struct.pack('<I',8))),
                    ('bitmap identity moved',lambda c:be32(c,G+0x6fee,BITMAP+2)),
                    ('LUT owner moved',lambda c:be32(c,G+0x16f8,LUT+2))]:
 f=Fixture();f.setup();c=f.cpu
 assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
 change(c)
 assert not f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK)),name
 result('warm display memo invalidation '+name)

f=Fixture();f.setup();c=f.cpu
assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
assert not f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,BITMAP+4096))
result('warm display memo exact stack invalidation')
f=Fixture();f.setup();c=f.cpu
f.call('_nv_art_game_bind',(0,PRIMARY+4096))
assert not u16(c,addr('_nv_art_decode_ready'))
result('warm bind memo exact stack invalidation')
for kind in('bind','display'):
 f=Fixture();f.setup();c=f.cpu
 if kind=='display':assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
 checks=[]
 def protection_call(cpu,pc,size,unused):
  if pc==addr('_nv_art_runtime_overlap'):checks.append(pc)
 hook=c.hook_add(unicorn.UC_HOOK_CODE,protection_call)
 be32(c,addr('_nv_art')+52,u32(c,addr('_nv_art')+52)+1)
 if kind=='bind':
  f.call('_nv_art_game_bind',(0,STACK));assert u16(c,addr('_nv_art_decode_ready'))
 else:assert f.call('_nv_art_game_c2p',(PRIMARY+6,BITMAP,HEIGHT,STACK))
 c.hook_del(hook);assert checks,kind
 result('warm '+kind+' memo generation revalidates',checks=len(checks))

report=dict(module_sha256=META['sha256'],synthetic_artifact=True,cases=RESULTS)
(artifact_dir('art')/'game-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(dict(art_game_cases=len(RESULTS),module_sha256=META['sha256'])))
