"""Exact projected resampler against an independent phase/output oracle."""
from pathlib import Path
import os,json,random,sys
here=Path(__file__).resolve().parent;root=here.parents[1]
prefix=(here/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(path):
 os.environ['MONKEY_ENGINE_BUILD']=str(path)
 ns=dict(__file__=str(here/'test_hybrid_driver.py'),__name__='projection_fixture')
 exec(compile(prefix,str(here/'test_hybrid_driver.py'),'exec'),ns)
 ns['cpu'].mem_map(0x900000,0x80000)
 return ns
variant='integrated'
current=Path(os.environ['MONKEY_ENGINE_BUILD'])
old=load(current);new=load(current)
rng=random.Random(587321)
data=[rng.randbytes(131072),rng.randbytes(131072)]
for ns in (old,new):
 for address,blob in zip((0x900000,0x940000),data):ns['cpu'].mem_write(address,blob)
reads=[];allowed=[]
def read(cpu,access,address,size,value,unused):
 if 0x900000<=address<0x980000:
  assert any(at<=address and address+size<=at+length for at,length in allowed),(hex(address),size,allowed)
  reads.append((address,size))
new['cpu'].hook_add(new['unicorn'].UC_HOOK_MEM_READ,read)
reports=[]
for case in range(1024):
 step=([124,161,256,8191,8192,16383,65535] if variant=='integrated' else [124,161,256,8191])[case%(7 if variant=='integrated' else 4)]
 period=rng.randrange(step,min(step*10,65536))
 if case%8<4:period=min(65535,step*[1,2,8,9][case%4])
 if variant=='integrated' and case%11==0:period=65536
 if variant=='integrated' and case%17==0:period=max(124,step//2)
 latched=rng.choice([1,period,65536])
 elapsed=rng.randrange(latched)
 length=rng.choice([2,16,64,512,6144,65536,131072])
 reload_length=rng.choice([2,16,64,512,65536,131072])
 index=rng.choice([0,length-1,rng.randrange(length)])
 ahead=rng.choice([0,step*256,max(0,latched-elapsed-1),latched-elapsed])
 ahead=min(ahead,step*256)
 volume=rng.randrange(65)
 state=bytearray(54)
 fields={0:0x940000,4:reload_length,8:0x900000,12:length,16:index,20:elapsed,24:period,28:latched,32:0xffffffff}
 for off,value in fields.items():state[off:off+4]=value.to_bytes(4,'big')
 for off,value in [(36,volume),(38,1),(40,1),(42,1)]:state[off:off+2]=value.to_bytes(2,'big')
 state[44]=127
 remaining=latched-elapsed;position=index;which=0;limit=length
 if ahead<remaining:remaining-=ahead
 else:
  clocks=ahead-remaining;position+=1+clocks//period;remaining=period-clocks%period
  if position>=limit:position=(position-limit)%reload_length;which=1;limit=reload_length
 expected=[]
 for i in range(256):
  value=data[which][position];value=value if value<128 else value-256
  expected.append((value*volume//128)&255)
  remaining-=step
  if remaining<=0:
   count=(-remaining)//period+1;remaining+=count*period;position+=count
   if position>=limit:position=(position-limit)%reload_length;which=1;limit=reload_length
 results=[]
 allowed[:]=[(0x900000,length),(0x940000,reload_length)];reads.clear()
 for label,ns in [('old',old),('new',new)]:
  p=0x607000;output=0x608000
  ns['cpu'].mem_write(p,bytes(state));ns['cpu'].mem_write(output-16,b'Z'*288)
  table=ns['sym']('_nv_half_amplitude')+volume*256
  if label=='old':ns['call']('_nv_paula_advance',p,ahead)
  preserved={}
  for reg in [ns['r'].UC_M68K_REG_D2,ns['r'].UC_M68K_REG_D3,ns['r'].UC_M68K_REG_D4,ns['r'].UC_M68K_REG_D5,ns['r'].UC_M68K_REG_D6,ns['r'].UC_M68K_REG_D7,ns['r'].UC_M68K_REG_A2,ns['r'].UC_M68K_REG_A3,ns['r'].UC_M68K_REG_A4,ns['r'].UC_M68K_REG_A5,ns['r'].UC_M68K_REG_A6]:
   value=rng.randrange(2**32);ns['cpu'].reg_write(reg,value);preserved[reg]=value
  if label=='new':ns['call']('_nv_hybrid_channel_ahead',p,table,step,output,ahead)
  else:ns['call']('_nv_hybrid_channel_runs' if step*2<=period<step*8 else '_nv_hybrid_channel',p,table,step,output)
  actual=bytes(ns['cpu'].mem_read(output,256));assert actual==bytes(expected),(case,label,step,period,latched,elapsed,index,length,reload_length,ahead)
  assert bytes(ns['cpu'].mem_read(output-16,16))==b'Z'*16 and bytes(ns['cpu'].mem_read(output+256,16))==b'Z'*16,('output bounds',case,label)
  assert all(ns['cpu'].reg_read(reg)==value for reg,value in preserved.items()),('register',case,label)
  if label=='new':assert bytes(ns['cpu'].mem_read(p,54))==bytes(state),('state mutated',case)
 reports.append(dict(case=case,step=step,period=period,latched=latched,length=length,reload_length=reload_length,ahead=ahead,source_reads=len(reads)))
report=dict(pass_=True,cases=len(reports),baseline_sha256=old['meta']['sha256'],candidate_sha256=new['meta']['sha256'],scope='Independent Python signed averaging and phase/reload oracle plus existing snapshot projection/kernel; exact 256-byte writes, bounded source reads, unchanged live state and all eleven ABI-preserved registers',reports=reports)
(new['BUILD']/'projected-span-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='reports'}))
