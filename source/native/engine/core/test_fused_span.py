"""Independent exact-output/bounds/ABI test of the integrated span-only helper."""
from pathlib import Path
import os,json,struct,random
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
source=HERE/'test_driver.py';ns={'__file__':str(source),'__name__':'fused_span_fixture'}
exec(compile(source.read_text().split("call('_nv_driver_start')",1)[0],str(source),'exec'),ns)
cpu,r,uc=ns['cpu'],ns['r'],ns['unicorn'];rng=random.Random(6339);src,pcm,out,state=0x900000,0x920000,0x940004,0x604000
for at in(src,pcm,0x940000):cpu.mem_map(at,0x10000)
allowed=[];bounds=[];enabled=False
savedregs=[getattr(r,'UC_M68K_REG_'+s) for s in('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6')]
def read(uc_,access,at,size,value,unused):
 if enabled and src<=at<0x930000:assert any(a<=at and at+size<=b for a,b in bounds),(hex(at),size,bounds)
def write(uc_,access,at,size,value,unused):
 if enabled:assert 0x50e000<=at and at+size<=0x50f100 or any(a<=at and at+size<=b for a,b in allowed),(hex(at),size)
cpu.hook_add(uc.UC_HOOK_MEM_READ,read);cpu.hook_add(uc.UC_HOOK_MEM_WRITE,write)
cases=0

def check(step,period,remaining,index,gain,odd=0,music=None):
 global enabled,bounds,allowed,cases
 data=rng.randbytes(512) if music is None else bytes([music])*512;speech=rng.randbytes(256) if music is None else bytes(range(256))
 snapshot=struct.pack('>8I',src,512,src,512,index,0,period,remaining)
 cpu.mem_write(src,data);cpu.mem_write(pcm+odd,speech);cpu.mem_write(out+odd-1,b'\xa5'*258);cpu.mem_write(state,snapshot)
 bounds=[(src,src+512),(pcm+odd,pcm+odd+256)];allowed=[(out+odd,out+odd+256)]
 expected=[];phase=remaining;at=index;signed=lambda n:n if n<128 else n-256
 for s in speech:
  expected.append(((signed(data[at])*gain//64+signed(s))//2)&255);phase-=step
  if phase<=0:advance=(-phase)//period+1;phase+=advance*period;at+=advance
 saved={reg:rng.randrange(2**32) for reg in savedregs}
 for reg,value in saved.items():cpu.reg_write(reg,value)
 enabled=True
 try:ns['call']('_nv_hybrid_fused_unity',state,ns['sym']('_nv_speech_words')+gain*512,step,out+odd,pcm+odd,ns['sym']('_nv_average')+32768)
 finally:enabled=False
 assert all(cpu.reg_read(reg)==value for reg,value in saved.items())
 assert bytes(cpu.mem_read(out+odd-1,258))==b'\xa5'+bytes(expected)+b'\xa5',(step,period,remaining,index,gain,odd)
 assert bytes(cpu.mem_read(state,32))==snapshot
 cases+=1
for step in(124,161,322,4095,8191):
 for q in range(2,8):
  for delta in(0,1,step//2,step-1):
   period=q*step+delta
   for remaining in(1,step,step+1,3*step,3*step+1,8*step):
    for index in((0,383) if q==2 else (0,416)):
     for odd in(0,1):check(step,period,remaining,index,(0,1,17,41,64)[cases%5],odd)
for music in range(256):check(161,642,642,0,64,music=music)
report=dict(pass_=True,cases=cases,actual_integrated_helper=True,all_65536_signed_pairs=True,negative_odd_rounding=True,old_latched_prefix=True,source96byte_span_boundary=True,all_steps124_161_322_4095_8191=True,bounded_source_speech_output=True,callee_ABI=True,snapshot_immutable=True,module_sha256=ns['meta']['sha256'])
(ns['BUILD']/'fused-span-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
