"""Execute the linked ART dispatch against its retained stripe fallback."""
from pathlib import Path
import argparse, hashlib, json, random, struct, sys, time

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'engine'))
from paths import artifact_dir,engine_build
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R

BUILD=artifact_dir('art')
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate',type=Path,default=engine_build()/'module/Monkey_Talkie_Test')
parser.add_argument('--artifact',type=Path,help='Optional privately generated NVPART01 corpus')
args=parser.parse_args()
blob=args.artifact.read_bytes()if args.artifact else b''
entries=[]
if blob:assert blob[:8]==b'NVPART01'
for n in range(struct.unpack_from('>I',blob,12)[0]if blob else 0):
 room,obj,offset,size,original_bytes,width,height,checksum=struct.unpack_from('>HHIIIHHI',blob,32+24*n)
 payload=blob[offset:offset+size]
 assert payload[:4]==b'NPD1' and len(payload)==size<=32768
 dc,record_bytes=struct.unpack_from('>HH',payload,16)
 rows,di,ix,so,sn,st=struct.unpack_from('>6I',payload,20)
 cols,flags=struct.unpack_from('>HH',payload,44)
 assert record_bytes==14 and rows==width//8*height and cols==width//8 and flags==3
 assert original_bytes==sn and 0<height<=200 and 0<width<=320 and width%8==0
 entries.append(dict(room=room,obj=obj,payload=payload,height=height,width=width,dict=di,
                     indices=ix,source=so,source_bytes=sn,strips=st,dependencies=(so+sn+1)&~1,
                     palette=payload[48:64],dictionary_count=dc))

reader=HunkReader()
assert reader.read_file(str(args.candidate))==0 and reader.build_segments()
module_meta=json.loads((args.candidate.parent/'module.json').read_text())
assert hashlib.sha256(args.candidate.read_bytes()).hexdigest()==module_meta['sha256']
addresses={};cursor=0x100000
for n,item in enumerate(reader.hunks[0]['hunks']):
 addresses[n]=cursor;cursor+=(item['size']+0xffff)&~0xffff
assert cursor<=0x400000
images={h['hunk_no']:bytearray(h['data'])for h in reader.hunks if'data'in h}
section=0;actual_relocations=set()
for h in reader.hunks:
 section=h.get('hunk_no',section)
 if h['type_name']in('HUNK_ABSRELOC32','HUNK_RELOC32SHORT'):
  for target,offsets in h['reloc'].items():
   for off in offsets:
    actual_relocations.add((section,target,off))
    struct.pack_into('>I',images[section],off,struct.unpack_from('>I',images[section],off)[0]+addresses[target])
def export(name):
 item=module_meta['exports'][name];return addresses[item['hunk']]+item['offset']
CODE,G=addresses[0],addresses[2]
expected_globals=(0x5d40,0x5c38,0x5c36,0x5c1a,0x5c1e,0x5c2a,0x5c49,0x6812,0x6812,0x5c1a,0x5c1e,0x5c26)
for i,expected in enumerate(expected_globals):
 entry=module_meta['exports']['_nv_art_global_%03d'%i];h,off=entry['hunk'],entry['offset']
 assert(h,2,off+2)in actual_relocations
 assert int.from_bytes(images[h][off+2:off+6],'big')==G+expected
KERNEL=export('_nv_art_dispatch');DECODER=export('_nv_art_decoder')
END_KERNEL=export('_nv_art_decoder_end')
CTX=export('_nv_art_decode');READY=export('_nv_art_decode_ready')
ARENA,LIVE,BACKUP,PRIMARY,MASK,STACK,STOP,SRSTORE=(0x400000,0x500000,0x600000,0x700000,0x800000,0xa0f000,0xb00000,0x900100)
assert images[0][0x4bb2:0x4bb8]==b'\x4e\xf9'+KERNEL.to_bytes(4,'big')
assert images[0][0x4bb8:0x4bba]==b'\x4e\x75'
assert images[0][0x4ddc:0x4dde]==b'\x4e\xf9'
STRIPE=int.from_bytes(images[0][0x4dde:0x4de2],'big')
stripe_hunk=next(n for n,at in addresses.items()if n!=0 and at<=STRIPE<at+len(images.get(n,b'')))
stripe=images[stripe_hunk]
tail_pattern=images[0][0x15294:0x152a2]
tail_offsets=[at for at in range(len(stripe)-len(tail_pattern)+1)if stripe[at:at+len(tail_pattern)]==tail_pattern]
assert len(tail_offsets)==1
STRIPE_TAIL=addresses[stripe_hunk]+tail_offsets[0]
rng=random.Random(15190)
REGS=[getattr(R,'UC_M68K_REG_D'+str(n))for n in range(8)]+[getattr(R,'UC_M68K_REG_A'+str(n))for n in range(7)]

class Fixture:
 def __init__(self,fast):
  self.fast=fast;self.cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN)
  self.cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);self.cpu.mem_map(0,0x1000000)
  for n,image in images.items():self.cpu.mem_write(addresses[n],bytes(image))
  if not fast:self.cpu.mem_write(CODE+0x4bb2,bytes.fromhex('66044eba0226'))
  self.cpu.hook_add(unicorn.UC_HOOK_CODE,self.original_enter,begin=STRIPE,end=STRIPE)
  self.cpu.hook_add(unicorn.UC_HOOK_CODE,self.tail_enter,begin=STRIPE_TAIL,end=STRIPE_TAIL)
  self.cpu.mem_write(STOP,bytes.fromhex('40f900900100'))
  self.cpu.hook_add(unicorn.UC_HOOK_CODE,self.original_enter,begin=CODE+0x15194,end=CODE+0x15194)
  self.cpu.hook_add(unicorn.UC_HOOK_CODE,self.original_enter,begin=CODE+0x1519a,end=CODE+0x1519a)
  self.cpu.hook_add(unicorn.UC_HOOK_CODE,self.tail_enter,begin=CODE+0x15294,end=CODE+0x15294)
  self.cpu.hook_add(unicorn.UC_HOOK_MEM_WRITE,self.written)
  self.cpu.hook_add(unicorn.UC_HOOK_MEM_READ,self.read)
  self.bounds=[];self.capture_all=False;self.in_tail=False
 def original_enter(self,*unused):self.missed=True
 def tail_enter(self,*unused):self.in_tail=True
 def written(self,cpu,access,address,size,value,unused):
  event=(address,size,value)
  if self.primary<=address<self.primary+64000:self.primary_writes.append(event)
  if STACK-80<=address<STACK:assert STACK-44<=address and address+size<=STACK
  if self.capture_all and address!=READY and not(STACK-80<=address<STACK):self.all_writes.append(event)
  if self.in_tail and address!=SRSTORE:self.tail_writes.append(event)
  if self.fast and KERNEL<=cpu.reg_read(R.UC_M68K_REG_PC)<END_KERNEL:
   allowed=STACK-40<=address and address+size<=STACK
   if address==READY and size==2 and value==0:allowed=True
   if self.backup<=address<self.backup+64000:
    d=address-self.backup;allowed=d//320<self.height and d%320+size<=8
   if self.primary<=address<self.primary+64000:
    d=address-self.primary;allowed=d//320<self.height and d%320+size<=8
   if G+0x6812<=address<G+0x6912:allowed=address+size<=G+0x6812+self.height
   assert allowed,('Unexpected shortcut write',hex(address),size)
 def read(self,cpu,access,address,size,value,unused):
  if MASK<=address<MASK+8000:self.mask_reads.append((address,size))
  if self.in_tail and not(STACK-80<=address<STACK+4):self.tail_reads.append((address,size))
  if self.fast and self.source_base<=address<self.source_base+self.source_length:
   pc=cpu.reg_read(R.UC_M68K_REG_PC)
   if DECODER<=pc<END_KERNEL:
    assert self.codec<=address and address+size<=self.codec+self.consumed,('Encoded read bound',hex(address),size)
    self.source_reads[size]=self.source_reads.get(size,0)+1
 def put(self,at,value,size):self.cpu.mem_write(at,value.to_bytes(size,'big'))
 def prepare(self,e,strip,case,mutation=None):
  self.in_tail=False;self.missed=False;self.capture_all=mutation is not None
  self.all_writes=[];self.tail_writes=[];self.tail_reads=[];self.source_reads={};self.primary_writes=[];self.mask_reads=[]
  self.height=h=e['height'];self.backup=BACKUP+2*(case&1);primary=PRIMARY+2*((case>>1)&1)
  self.source_base=LIVE+(case&1);self.source_length=e['source_bytes']
  payload=e['payload'];desc=e['strips']+8*strip
  start,self.consumed,tail=struct.unpack_from('>IHH',payload,desc)
  self.codec=self.source_base+start
  self.cpu.mem_write(G,bytes([0x5a])*0x8000)
  self.cpu.mem_write(ARENA,payload)
  source=bytearray(payload[e['source']:e['source']+e['source_bytes']])
  palette=bytearray(e['palette']);history=bytearray((case*17+y*29)&255 for y in range(256))
  raw_rows=[];dependencies=[]
  for y in range(h):
   offset=struct.unpack_from('>H',payload,e['indices']+2*(strip*h+y))[0]
   assert offset%14==0 and offset<14*e['dictionary_count']
   row=payload[e['dict']+offset:e['dict']+offset+8];assert len(row)==8
   raw_rows.append(row)
   dependent=bool(payload[e['dependencies']+strip*((h+7)//8)+y//8]&(0x80>>(y&7)))
   if dependent:history[y]=row[0];dependencies.append(y)
  published=True;screen=0;geometry=320*h-1;ctx_height=h;reserved=0
  if mutation=='palette':palette[0]^=1
  if mutation=='codec':source[start]^=1
  if mutation=='interior':
   p=start+1
   while p<start+self.consumed:
    token=source[p];p+=1
    if token<128:
     source[p-1]^=1;break
    if token>=192:
     source[p]^=1;break
    if not(token&63):p+=1
   else:raise ValueError('No literal color in selected strip')
  if mutation=='history' and dependencies:history[dependencies[0]]^=1
  if mutation=='screen':screen=1
  if mutation=='geometry':geometry+=1
  if mutation=='height':ctx_height=h-1 if h>1 else 2
  if mutation=='reserved':reserved=1
  if mutation=='publication':published=False
  if mutation=='odd_backup':self.backup+=1
  if mutation=='odd_primary':primary+=1
  self.cpu.mem_write(self.source_base,bytes(source))
  self.cpu.mem_write(BACKUP-16,bytes([0xa5])*(64000+32))
  self.cpu.mem_write(PRIMARY-16,bytes([0x96])*(64000+32))
  masks=bytearray([0x13]*8000)
  for y in range(h):masks[40*y]=0xff if mutation in ('odd_backup','odd_primary') else 0 if (case+y)%5 else (0x80|y)
  self.cpu.mem_write(MASK,bytes(masks))
  for off,value,n in ((0x5c26,MASK,4),(0x5c2a,self.codec+1,4),(0x5c1e,primary,4),
                      (0x5c1a,self.backup,4),(0x5c36,geometry,2),(0x5c38,h,1),(0x5d40,screen,2)):
   self.put(G+off,value,n)
  self.put(G+0x5c2a,self.codec,4)
  self.cpu.mem_write(G+0x5c49,bytes(palette));self.cpu.mem_write(G+0x6812,bytes(history))
  if mutation and mutation.startswith('alias_'):
   published=False
   if mutation=='alias_source':
    self.source_base=self.backup;self.codec=self.source_base+start
    self.cpu.mem_write(self.source_base,bytes(source))
    self.put(G+0x5c2a,self.codec,4)
   if mutation=='alias_history':self.backup=G+0x6812
   if mutation=='alias_palette_control':self.backup=G+0x5c48
   if mutation=='alias_output':primary=self.backup+2
   if mutation=='alias_primary_source':primary=self.source_base
   self.put(G+0x5c1a,self.backup,4);self.put(G+0x5c1e,primary,4)
  self.primary=primary
  indices=ARENA+e['indices']+2*strip*h
  expected=ARENA+e['source']+start
  context=struct.pack('>6IHH',ARENA+e['dict'],indices,expected,expected+self.consumed,
                      ARENA+e['dependencies']+strip*((h+7)//8),ARENA+48,ctx_height,reserved)
  self.cpu.mem_write(CTX,context)
  self.put(READY,int(published),2)
  self.cpu.mem_write(STACK-80,bytes([0x71])*100);self.put(STACK,STOP,4)
  self.raw_rows=raw_rows;self.expected_history=bytes(history[h:])
  return CTX if published else 0
 def run(self,registers,ccr,ctx):
  for register,value in zip(REGS,registers):self.cpu.reg_write(register,value)
  self.cpu.reg_write(R.UC_M68K_REG_A4,G)
  self.cpu.reg_write(R.UC_M68K_REG_SR,0x2000|ccr);self.cpu.reg_write(R.UC_M68K_REG_A7,STACK)
  self.cpu.emu_start(CODE+0x4ba2,STOP+6,count=1000000)
  assert self.cpu.reg_read(R.UC_M68K_REG_PC)==STOP+6
  result=([self.cpu.reg_read(reg)for reg in REGS],self.cpu.reg_read(R.UC_M68K_REG_A7),
          int.from_bytes(self.cpu.mem_read(SRSTORE,2),'big')&31)
  memory=[bytes(self.cpu.mem_read(a,n))for a,n in (
   (G,0x8000),(BACKUP-16,64032),(PRIMARY-16,64032),(MASK,8000),
   (self.source_base,self.source_length),(ARENA,self.payload_size),(CTX,28),(STACK-80,100))]
  memory[-1]=memory[-1][:36]+b'\0'*44+memory[-1][80:]
  return result,memory

def synthetic_entry(height):
 palette=bytes([16,0]+list(range(18,32)))
 history=[16+(y&15)for y in range(height)]
 source=bytearray([10]);left=8*height;packet=0
 while left:
  mode=packet%3;n=min(left,(32,256,193,1,7,63,64)[packet%7]);packet+=1;left-=n
  if mode==0:
   source.extend([0x80|n]if n<64 else[0x80,n&255])
  elif mode==1:
   color=packet&15;source.extend([(n<<4)|color]if n<8 else[color,n&255])
  else:
   color=((packet&15)<<4)|((packet+1)&15)
   source.extend([0xc0|n,color]if n<64 else[0xc0,color,n&255])
 rows=[bytearray(8)for _ in range(height)];dependency=bytearray((height+7)//8)
 p=1;remaining=0
 for x in range(8):
  for y in range(height):
   if not remaining:
    token=source[p];p+=1
    if token<128:mode=0;a=token&15;remaining=token>>4
    elif token<192:mode=1;remaining=token&63
    else:mode=2;remaining=token&63;a=source[p]>>4;b=source[p]&15;p+=1
    if not remaining:remaining=source[p]or 256;p+=1
   color=history[y]if mode==1 else palette[a]
   if x==0 and mode==1:dependency[y//8]|=0x80>>(y&7)
   rows[y][x]=color;history[y]=color;remaining-=1
   if mode==2:a,b=b,a
 assert not remaining and p==len(source)
 dictionary=list(dict.fromkeys(bytes(row)for row in rows));di=72;ix=di+14*len(dictionary)
 so=ix+2*height;dep=(so+len(source)+1)&~1
 payload=bytearray(dep+len(dependency));payload[48:64]=palette
 struct.pack_into('>IHH',payload,64,0,len(source),128 if any(dependency)else 0)
 for n,row in enumerate(dictionary):
  planes=bytes(sum(((row[x]>>bit)&1)<<(7-x)for x in range(8))for bit in(0,1,3,4,2))
  payload[di+14*n:di+14*n+14]=row+planes+b'\0'
 for y,row in enumerate(rows):struct.pack_into('>H',payload,ix+2*y,14*dictionary.index(bytes(row)))
 payload[so:so+len(source)]=source;payload[dep:dep+len(dependency)]=dependency
 return dict(room=-3,obj=height,payload=bytes(payload),height=height,width=8,dict=di,
             indices=ix,source=so,source_bytes=len(source),strips=64,dependencies=dep,
             palette=palette,dictionary_count=len(dictionary))

old,new=Fixture(False),Fixture(True);cases=hits=misses=pixels=0;source_reads={}
target=next((e for e in entries if(e['room'],e['obj'])==(10,113)),synthetic_entry(120))
selected=entries or[synthetic_entry(h)for h in(1,2,7,8,9,15,16,17,63,64,65,120,199,200)]
started=time.monotonic()
def check(e,strip,mutation=None):
 global cases,hits,misses,pixels
 regs=[rng.getrandbits(32)for _ in REGS];results=[]
 for f in (old,new):
  f.payload_size=len(e['payload']);ctx=f.prepare(e,strip,cases,mutation)
  results.append(f.run(regs,cases&31,ctx))
  if f.fast:assert bytes(f.cpu.mem_read(READY,2))==b'\0\0'
 assert results[0]==results[1],('Return state or RAM',e['room'],e['obj'],strip,mutation,cases)
 assert old.primary_writes==new.primary_writes,('Ordered primary writes',e['room'],e['obj'],strip,mutation)
 assert old.mask_reads==new.mask_reads,('Ordered mask reads',e['room'],e['obj'],strip,mutation)
 if mutation is not None:
  assert old.tail_writes==new.tail_writes and old.tail_reads==new.tail_reads
  assert new.missed,('Guard unexpectedly accepted changed input',mutation)
  assert old.all_writes==new.all_writes,('Miss write order',mutation)
 else:
  assert not new.missed,('Valid strip rejected',e['room'],e['obj'],strip)
  for y,row in enumerate(new.raw_rows):assert bytes(new.cpu.mem_read(new.backup+320*y,8))==row
  assert bytes(new.cpu.mem_read(G+0x6812,e['height']))==bytes(row[7]for row in new.raw_rows)
  assert bytes(new.cpu.mem_read(G+0x6812+e['height'],256-e['height']))==new.expected_history
 hits+=not new.missed;misses+=new.missed;pixels+=8*e['height'];cases+=1
 for width,n in new.source_reads.items():source_reads[width]=source_reads.get(width,0)+n

for e in selected:
 for strip in range(e['width']//8):check(e,strip)
 if cases%200<e['width']//8:print('Progress',cases,'strips',pixels,'pixels',round(time.monotonic()-started,2),'seconds',flush=True)
for ccr in range(32):
 for mutation in ('palette','codec','interior','history','screen','geometry','height','reserved','publication','odd_backup','odd_primary'):
  if mutation=='codec':continue
  strip=ccr%(target['width']//8)
  if mutation=='history':
   h=target['height'];mask=target['payload'][target['dependencies']+strip*((h+7)//8):target['dependencies']+(strip+1)*((h+7)//8)]
   if not any(mask):continue
  check(target,strip,mutation)
# Model the manager withholding publication for otherwise legal original aliases.
# Eight COPY runs are deliberately independent of palette and byte alignment.
synthetic=bytearray(212);synthetic[48:64]=bytes([16,0]+list(range(18,32)))
struct.pack_into('>IHH',synthetic,64,0,9,128)
for y in range(8):
 synthetic[72+14*y:80+14*y]=bytes([16+y])*8
 struct.pack_into('>H',synthetic,184+2*y,14*y)
synthetic[200:209]=bytes([10]+[0x88]*8);synthetic[210]=0xff
alias_entry=dict(room=-1,obj=-1,payload=bytes(synthetic),height=8,width=8,dict=72,
                 indices=184,source=200,source_bytes=9,strips=64,dependencies=210,
                 palette=bytes(synthetic[48:64]),dictionary_count=8)
for ccr in range(32):
 for mutation in ('alias_source','alias_history','alias_palette_control','alias_output','alias_primary_source'):
  check(alias_entry,0,mutation)
for height in(1,2,7,8,9,15,16,17,199,200):
 tokens=bytes([0x80|height])if height<64 else bytes([0x80,height])
 source=bytes([10])+tokens*8;indices=296;source_at=indices+2*height
 dependency_at=(source_at+len(source)+1)&~1
 synthetic=bytearray(dependency_at+(height+7)//8)
 synthetic[48:64]=bytes([16,0]+list(range(18,32)))
 struct.pack_into('>IHH',synthetic,64,0,len(source),128)
 for color in range(16):synthetic[72+14*color:80+14*color]=bytes([16+color])*8
 for y in range(height):
  struct.pack_into('>H',synthetic,indices+2*y,14*(y&15))
  synthetic[dependency_at+y//8]|=0x80>>(y&7)
 synthetic[source_at:source_at+len(source)]=source
 edge=dict(room=-2,obj=height,payload=bytes(synthetic),height=height,width=8,dict=72,
           indices=indices,source=source_at,source_bytes=len(source),strips=64,
           dependencies=dependency_at,palette=bytes(synthetic[48:64]),dictionary_count=16)
 for ccr in range(32):check(edge,0)
dispatch_codec_cases=0
for codec in range(256):
  for ccr in range(32):
   results=[];regs=[rng.getrandbits(32)for _ in REGS]
   for f in(old,new):
    f.payload_size=len(target['payload']);ctx=f.prepare(target,0,ccr,'publication')
    f.cpu.mem_write(f.codec,bytes([codec]))
    results.append(f.run(regs,ccr,ctx))
   assert results[0]==results[1],('Full dispatcher',codec,ccr)
   assert old.all_writes==new.all_writes,('Dispatcher game-write order',codec,ccr)
   assert bytes(new.cpu.mem_read(READY,2))==b'\0\0'
   dispatch_codec_cases+=1
report=dict(pass_=True,cases=cases,fast_hits=hits,guard_misses=misses,pixels=pixels,
            candidate_sha256=module_meta['sha256'],
            artifact_sha256=hashlib.sha256(blob).hexdigest()if blob else None,
            candidate_module=str(args.candidate),retained_stripe_hunk=stripe_hunk,
            source_read_widths=source_reads,elapsed_seconds=time.monotonic()-started,
            ordered_primary_writes_and_mask_reads_equal=True,miss_original_tail_read_write_order_equal=True,backup_history_interleaved_under_disjoint_admission=True,all12_actual_global_relocations_verified=True,fallback_game_write_order_equal=True,
            return_registers_CCR_SP_game_RAM_equal=True,all32_CCR_inputs=True,
            initial_COPY_history_and_last_column_history=True,
            manager_withheld_alias_fallback_cases=160,
            caller_A4_equals_globals_and_is_preserved=True,
            production_wrapper_single_use_ready=True,
            current_stripe_dispatch=True,
            all256_codecs_all32_CCR_dispatch_cases=dispatch_codec_cases,
            synthetic_height_edge_cases=320,
            dead_callee_stack_bytes_excluded=44,
            contract='Manager validates contexts and disjoint source/palette/history/output/globals/arena/stack spans before publication; this kernel independently checks stream,palette,first-column dependencies and geometry before any new write')
(BUILD/('decoder-corpus-validation.json'if args.artifact else'decoder-validation.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2),flush=True)
