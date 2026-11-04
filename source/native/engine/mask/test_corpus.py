"""Compare the original and relaxed mask-plane decoder, including aliased streams."""
from pathlib import Path
import sys,subprocess,struct,random,json,hashlib
sys.path.insert(0,'D:/Projects/Monkey.Island.Amiga/tools/python')
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
import capstone
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,artifact_dir
P=artifact_dir('mask')
r=HunkReader();assert r.read_file(str(PROJECT_ROOT/'data/original/Monkey_Island'))==0 and r.build_segments()
original=next(h['data'] for h in r.hunks if h.get('hunk_no')==0 and 'data'in h)[0x15338:0x1538e]
candidate=(P/'mask.bin').read_bytes()
cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000)
relocs=[]
for i in cs.disasm(candidate,0):
 if '.l' in i.op_str and any(x in i.op_str for x in ('$5c22','$5c38','$5c2e')):relocs.append(i.address+2)
regs=[getattr(R,'UC_M68K_REG_'+x) for x in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
rng=random.Random(0x15338);cpus=[]
for code in (original,candidate):
 u=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);u.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);u.mem_map(0,0x100000);u.mem_write(0x10000,code);cpus.append(u)
def stream(mode,n):
 b=bytearray()
 for _ in range(300):
  length=n if n>=0 else rng.choice((0,1,2,3,7,16,63,127))
  repeat=mode==1 or mode==2 and rng.randrange(2)
  b.append(length|(128 if repeat else 0))
  b.extend(rng.randbytes(1 if repeat else length or 256))
 return bytes(b)
from collections import Counter,defaultdict
artifact=Path(sys.argv[1]);blob=artifact.read_bytes();packets=Counter();skipped=[];rows=[];objects={};vectors=[]
for number in range(struct.unpack_from('>I',blob,12)[0]):
 room,obj,offset,size,_,width,height,_=struct.unpack_from('>HHIIIHHI',blob,32+number*24);payload=blob[offset:offset+size];so,sn=struct.unpack_from('>II',payload,32);source=payload[so:so+sn];delta=struct.unpack_from('<I',source,8)[0]
 if not delta:continue
 base=8+delta
 for plane in range(8):
  if base+2>len(source):break
  length=struct.unpack_from('<H',source,base)[0]
  if not length:break
  columns=width//8
  if length<2+columns*2 or base+length>len(source):skipped.append((room,obj,plane,'blockbounds'));break
  for col in range(columns):
   begin=base+struct.unpack_from('<H',source,base+2+2*col)[0];pos=begin;expected=[];counts=[]
   if not base+2+2*columns<=begin<base+length:skipped.append((room,obj,plane,col,'offset'));continue
   bad=False
   while len(expected)<height:
    if pos>=len(source):bad=True;break
    flag=source[pos];pos+=1;count=(flag&127 if flag&128 else flag)or 256;n=min(count,height-len(expected));kind='repeat'if flag&128 else'literal'
    if kind=='repeat':
     if pos>=len(source):bad=True;break
     expected.extend([source[pos]]*n);pos+=1
    else:
     if pos+n>len(source):bad=True;break
     expected.extend(source[pos:pos+n]);pos+=n
    counts.append((kind,count,n));packets[(kind,count)]+=1
   if bad:skipped.append((room,obj,plane,col,'sourceprefix_not_within_OI'));continue
   vectors.append((room,obj,plane,col,height,source[begin:pos],bytes(expected),counts))
  base+=length
for i,(room,obj,plane,col,height,data,expected,counts)in enumerate(vectors):
 initial=[0xffffffff]*len(regs);initial[-1]=0x8f000;snapshots=[]
 for u in cpus:
  src=0x30000;dst=0x50000;u.mem_write(src,bytes(0x14000));u.mem_write(dst,bytes(0x4000));u.mem_write(src,data);u.mem_write(0x5c22,struct.pack('>I',dst));u.mem_write(0x5c2e,struct.pack('>I',src));u.mem_write(0x5c38,bytes((height&255,)));u.mem_write(0x8f000,struct.pack('>I',0x90000));u.reg_write(R.UC_M68K_REG_SR,0)
  for r,v in zip(regs,initial):u.reg_write(r,v)
  bus=[];steps=[0]
  def memory(cpu,kind,at,n,v,unused):
   if src<=at<src+0x14000 or dst<=at<dst+0x4000:bus.append((kind,at,n,v if kind==unicorn.UC_MEM_WRITE else bytes(cpu.mem_read(at,n)).hex()))
  def code(*args):steps[0]+=1
  h=u.hook_add(unicorn.UC_HOOK_MEM_READ|unicorn.UC_HOOK_MEM_WRITE,memory);t=u.hook_add(unicorn.UC_HOOK_CODE,code);u.emu_start(0x10000,0x90000,count=100000);u.hook_del(h);u.hook_del(t)
  assert bytes(u.mem_read(dst+y*40,1)[0]for y in range(height))==expected
  u.mem_write(0x90000,bytes.fromhex('40f900090100'));u.emu_start(0x90000,0x90006,count=1)
  snapshots.append((tuple(u.reg_read(r)for r in regs),bytes(u.mem_read(0x90100,2)),tuple(bus),steps[0]))
 assert snapshots[0][:-1]==snapshots[1][:-1],(room,obj,plane,col)
 rows.append(dict(room=room,object=obj,plane=plane,column=col,height=height,packets=counts,old_instructions=snapshots[0][-1],new_instructions=snapshots[1][-1]))
 if i%500==0:print('progress',i,len(vectors),flush=True)
a=sum(r['old_instructions']for r in rows);b=sum(r['new_instructions']for r in rows)
by=defaultdict(lambda:[0,0,0])
for r in rows:
 v=by[(r['room'],r['object'])];v[0]+=r['old_instructions'];v[1]+=r['new_instructions'];v[2]+=1
object_rows=[dict(room=k[0],object=k[1],old_instructions=v[0],new_instructions=v[1],columns=v[2],ratio=v[1]/v[0])for k,v in by.items()]
report=dict(pass_=True,scope='Every structurally boundedmaskblock/column found in605typedpreparedOIreferences; objectswithoutmask or outside32KBARTeligibilitynotincluded. Oneexecutionpercolumn, not gameplayfrequencyweight. Compiled68000instructions NOTguestcycles.',artifact_sha256=hashlib.sha256(blob).hexdigest(),cases=len(rows),objects=len(object_rows),old_instructions=a,new_instructions=b,ratio=b/a,columns_faster=sum(r['new_instructions']<r['old_instructions']for r in rows),columns_equal=sum(r['new_instructions']==r['old_instructions']for r in rows),columns_slower=sum(r['new_instructions']>r['old_instructions']for r in rows),worst_column_ratio=max(r['new_instructions']/r['old_instructions']for r in rows),objects_faster=sum(r['ratio']<1 for r in object_rows),objects_slower=sum(r['ratio']>1 for r in object_rows),objects_equal=sum(r['ratio']==1 for r in object_rows),worst_objects=sorted(object_rows,key=lambda r:r['ratio'],reverse=True)[:20],packet_histogram=[dict(kind=k[0],length=k[1],packets=v)for k,v in packets.most_common()],skipped=skipped,objects_detail=object_rows)
(P/'corpus-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k not in('objects_detail','packet_histogram','worst_objects','skipped')},indent=2))
