"""Verify unity stereo speech and its entry dispatch against signed arithmetic."""
from pathlib import Path
import os,json,random
HERE=Path(__file__).resolve().parent
source=HERE/'test_driver.py';ns={'__file__':str(source),'__name__':'unity_speech_fixture'}
exec(compile(source.read_text().split("call('_nv_driver_start')",1)[0],str(source),'exec'),ns)
cpu,r,uc=ns['cpu'],ns['r'],ns['unicorn'];proto=ns['sym']('_nv_hybrid_speech_unity')
for base in (0x900000,0x920000,0x940000):cpu.mem_map(base,0x20000)
table=ns['sym']('_nv_speech_words')+64*512
entry=ns['sym']('_nv_hybrid_speech')
assert bytes(cpu.mem_read(entry,8))==bytes.fromhex('0caf')+table.to_bytes(4,'big')+bytes.fromhex('0010')
assert bytes(cpu.mem_read(entry+8,2))==bytes.fromhex('6700')
legacy=entry+12
assert bytes(cpu.mem_read(legacy,4))==bytes.fromhex('48e73038')
savedregs=[getattr(r,'UC_M68K_REG_'+s) for s in ('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6')]
bounds=[];source_bounds=[0,0];counts=[0];reads=[0];rng=random.Random(0x64706169);cases=0;profiles=[]
def ins(*_):counts[0]+=1
def writes(uc_,access,at,size,value,unused):
 assert any(a<=at and at+size<=b for a,b in bounds) or 0x50ec00<=at and at+size<=0x50f000,(hex(at),size,bounds)
def source_read(uc_,access,at,size,value,unused):
 if 0x900000<=at<0x920000:
  assert source_bounds[0]<=at and at+size<=source_bounds[1],(hex(at),size,source_bounds)
  reads[0]+=1
cpu.hook_add(uc.UC_HOOK_CODE,ins);cpu.hook_add(uc.UC_HOOK_MEM_WRITE,writes);cpu.hook_add(uc.UC_HOOK_MEM_READ,source_read)
def check(pcm,left,right,si,li,ri,profile=False):
 global cases,bounds
 n=len(pcm);src,L,R=0x900004+si,0x920004+li,0x940004+ri
 signed=lambda x:x if x<128 else x-256
 expectedL=bytes(((signed(a)+signed(b))//2)&255 for a,b in zip(left,pcm));expectedR=bytes(((signed(a)+signed(b))//2)&255 for a,b in zip(right,pcm));resultcounts=[]
 for target in (legacy,proto,entry):
  cpu.mem_write(src-4,b'\xa5'*4+pcm+b'\xa5'*4);cpu.mem_write(L-4,b'\xa5'*4+left+b'\xa5'*4);cpu.mem_write(R-4,b'\xa5'*4+right+b'\xa5'*4)
  source_bounds[:]=[src,src+n];bounds=[(L,L+n),(R,R+n)];saved={x:rng.randrange(2**32) for x in savedregs}
  for reg,v in saved.items():cpu.reg_write(reg,v)
  args=(L,R,src,table,n)
  ns['put'](0x50f000,0x60f000,4)
  for i,arg in enumerate(args):ns['put'](0x50f004+4*i,arg,4)
  cpu.reg_write(r.UC_M68K_REG_A7,0x50f000);counts[0]=reads[0]=0;cpu.emu_start(target,0x60f000,count=2000000)
  assert cpu.reg_read(r.UC_M68K_REG_PC)==0x60f000 and cpu.reg_read(r.UC_M68K_REG_A7)==0x50f004
  assert all(cpu.reg_read(reg)==v for reg,v in saved.items())
  assert bytes(cpu.mem_read(L-4,n+8))==b'\xa5'*4+expectedL+b'\xa5'*4
  assert bytes(cpu.mem_read(R-4,n+8))==b'\xa5'*4+expectedR+b'\xa5'*4
  assert bytes(cpu.mem_read(src-4,n+8))==b'\xa5'*4+pcm+b'\xa5'*4
  if not n:assert reads[0]==0
  resultcounts.append(counts[0])
 if profile:profiles.append(dict(count=n,source_odd=si,left_odd=li,right_odd=ri,baseline_instructions=resultcounts[0],candidate_instructions=resultcounts[1],dispatch_instructions=resultcounts[2]))
 cases+=1
for n in list(range(50))+[63,64,65,127,128,129,255,256,257,511,512,513]:
 for si in (0,1):
  for li in (0,1):
   for ri in (0,1):check(rng.randbytes(n),rng.randbytes(n),rng.randbytes(n),si,li,ri,True)
# Exhaust every signed music/speech combination, with different right music.
for value in range(256):
 for si in (0,1):check(bytes(range(256)),bytes([value])*256,bytes([255-value])*256,si,value&1,(value>>1)&1)
for si in (0,1):check(rng.randbytes(65535),rng.randbytes(65535),rng.randbytes(65535),si,1,0,True)
check(rng.randbytes(65535),rng.randbytes(65535),rng.randbytes(65535),0,0,0,True)
report=dict(cases=cases,helper='_nv_hybrid_speech_unity',independent_signed_average_oracle=True,all_65536_music_speech_pairs=True,source_and_output_bounds=True,callee_ABI_preserved=True,source_immutable=True,profiles=profiles)
report_path=Path(os.environ.get('MONKEY_UNITY_REPORT',str(ns['BUILD']/'hybrid-speech-unity.json')))
report_path.write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='profiles'}));print([x for x in profiles if x['count'] in(1,2,255,256,257) and x['left_odd']==0 and x['right_odd']==0])
