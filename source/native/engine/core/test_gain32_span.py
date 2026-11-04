"""Exact gain-32 rendering, including every signed source byte and fallbacks."""
from pathlib import Path
import json,random
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]

def fixture():
 ns=dict(__file__=str(HERE/'test_hybrid_driver.py'),__name__='gain32_fixture')
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['cpu'].mem_map(0x900000,0x80000)
 return ns

old,new=fixture(),fixture();rng=random.Random(320204);allowed=[];reads=[];hits=[]

def source_read(cpu,access,address,size,value,unused):
 if 0x900000<=address<0x980000:
  assert any(start<=address and address+size<=start+length for start,length in allowed)
  reads.append((address,size))

def fast_entry(cpu,pc,size,unused):hits.append(pc)

new['cpu'].hook_add(new['unicorn'].UC_HOOK_MEM_READ,source_read)
entry=new['sym']('_nv_project_asr_ready')
new['cpu'].hook_add(new['unicorn'].UC_HOOK_CODE,fast_entry,begin=entry,end=entry)
reports=[]
for case in range(1280):
 step=161 if case<512 else rng.choice([124,161,256,8191,8192])
 q=(2 if case<256 else 4)if case<512 else rng.choice([1,2,3,4,5,8,9])
 period=min(65536,q*step+17);volume=32 if case<512 or case%2 else rng.choice([0,16,31,33,64])
 latched=period if case<512 else rng.choice([1,period,65536]);elapsed=rng.randrange(latched)
 length=rng.choice([2,16,64,512]);reload_length=rng.choice([2,16,64,512])
 index=rng.choice([0,length-1,rng.randrange(length)])
 ahead=256*step if case<512 else min(256*step,rng.choice([0,256*step,latched-elapsed,max(0,latched-elapsed-1)]))
 data=[bytes([case&255])*512]*2 if case<512 else[rng.randbytes(512),rng.randbytes(512)]
 if case>=1024:
  step=161;q=4;period=764;volume=32
  latched=65536 if case%16==0 else period
  elapsed=rng.randrange(latched)
  length=rng.choice([2,16,64,166,512])
  reload_length=[1,2,8,15,16,17,64,166][case%8]
  index=rng.choice([0,length-1,rng.randrange(length)])
  ahead=0 if case%4==0 else 256*step
  data=[bytes([case&255])*512]*2
 state=bytearray(54)
 for off,value in((0,0x940000),(4,reload_length),(8,0x900000),(12,length),(16,index),
                  (20,elapsed),(24,period),(28,latched)):
  state[off:off+4]=value.to_bytes(4,'big')
 for off,value in((36,volume),(38,1)):state[off:off+2]=value.to_bytes(2,'big')
 remaining=latched-elapsed;position=index;which=0;limit=length
 if ahead<remaining:remaining-=ahead
 else:
  clocks=ahead-remaining;position+=1+clocks//period;remaining=period-clocks%period
  if position>=limit:position=(position-limit)%reload_length;which=1;limit=reload_length
 expected=[]
 for _ in range(256):
  value=data[which][position];value=value if value<128 else value-256
  expected.append((value*volume//128)&255)
  remaining-=step
  if remaining<=0:
   count=(-remaining)//period+1;remaining+=count*period;position+=count
   if position>=limit:position=(position-limit)%reload_length;which=1;limit=reload_length
 allowed[:]=[(0x900000,length),(0x940000,reload_length)];reads.clear();before=len(hits)
 flags=[]
 for is_new,ns in((False,old),(True,new)):
  cpu=ns['cpu'];r=ns['r'];p=0x607000;output=0x608000
  for at,blob in zip((0x900000,0x940000),data):cpu.mem_write(at,blob)
  cpu.mem_write(p,bytes(state));cpu.mem_write(output-16,b'Z'*288)
  table=ns['sym']('_nv_half_amplitude')+volume*256
  saved={}
  for name in('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6'):
   reg=getattr(r,'UC_M68K_REG_'+name);saved[reg]=rng.getrandbits(32);cpu.reg_write(reg,saved[reg])
  cpu.reg_write(r.UC_M68K_REG_SR,0x2000|(case&31))
  if is_new:ns['call']('_nv_hybrid_channel_ahead',p,table,step,output,ahead)
  else:
   ns['call']('_nv_paula_advance',p,ahead)
   ns['call']('_nv_hybrid_channel_runs'if 2*step<=period<9*step else'_nv_hybrid_channel',p,table,step,output)
  assert bytes(cpu.mem_read(output,256))==bytes(expected),(case,is_new)
  assert bytes(cpu.mem_read(output-16,16))==b'Z'*16 and bytes(cpu.mem_read(output+256,16))==b'Z'*16
  assert all(cpu.reg_read(reg)==value for reg,value in saved.items()),('ABI',case,is_new)
  if is_new:assert bytes(cpu.mem_read(p,54))==bytes(state)
  cpu.mem_write(0x60f000,bytes.fromhex('40f900607100'));cpu.emu_start(0x60f000,0x60f006,count=1)
  flags.append(ns['get'](0x607100,2)&31)
 if case<512:
  assert len(hits)==before+1,('Gain32 path not entered',case)
  assert flags[0]==flags[1],('Final CCR',case,flags)
 if case>=1024:assert flags[0]==flags[1],('Final CCR',case,flags)
 reports.append(dict(case=case,period=period,step=step,volume=volume,ahead=ahead,fast_calls=len(hits)-before,source_reads=len(reads)))
report=dict(pass_=True,cases=len(reports),all256_signed_bytes_at_q2_and_q4=True,
            fast_calls=len(hits),module_sha256=new['meta']['sha256'],
            exact_output_phase_reload_live_state_bounds_ABI=True,uniform_byte_final_CCR_exact=True,
            scope='Independent Python phase/signed-floor oracle and existing snapshot helpers; actual gain32 row identity, source boundaries, exceptional periods, old latched prefixes, other gains and q ranges',reports=reports)
(new['BUILD']/'gain32-span-validation.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({key:value for key,value in report.items()if key!='reports'}))
