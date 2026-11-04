"""Bounded linked comparator ABI/read-span proof; synthetic RAM only."""
import struct,random,json,hashlib
from glyph_fixture import T,R,unicorn,IMAGE,META,artifact_dir

def main():
 guest=T.Guest(IMAGE,0,META);u=guest.cpu;entry=guest.addr('_nv_glyph_same')
 regs=[getattr(R,'UC_M68K_REG_D%d'%i)for i in range(8)]+[getattr(R,'UC_M68K_REG_A%d'%i)for i in range(8)]
 rng=random.Random(0x852068);limits=[0,0,0,0];cases=0;reads=[]
 def read(c,access,at,n,value,_):
  if 0x40000<=at<0x50004:assert limits[0]<=at and at+n<=limits[1],('A overread',at,n,limits)
  if 0x60000<=at<0x70004:assert limits[2]<=at and at+n<=limits[3],('B overread',at,n,limits)
 u.hook_add(unicorn.UC_HOOK_MEM_READ,read)
 lengths=list(range(257))+[511,512,513,1023,1024,1025,3314,4367,16383,16384,16385,32767,32768,32769,64547,64548]+[rng.randrange(64549)for _ in range(32)]
 for n in lengths:
  data=bytes(rng.getrandbits(8)for _ in range(n))
  for pa in (0,1):
   for pb in (0,1):
    a=0x40000+pa;b=0x60000+pb;limits[:]=[a,a+n,b,b+n]
    for change in (None,0,n//2,n-1)if n else(None,):
     other=bytearray(data)
     if change is not None:other[change]^=255
     if n:u.mem_write(a,data);u.mem_write(b,bytes(other))
     values=[rng.getrandbits(32)for _ in regs];values[-1]=0x90000
     u.reg_write(R.UC_M68K_REG_SR,cases&31)
     for reg,v in zip(regs,values):u.reg_write(reg,v)
     u.mem_write(0x90000,struct.pack('>IIII',0x20000,a,b,n))
     try:u.emu_start(entry,0x20000,count=1000000)
     except Exception:
      print(n,pa,pb,change,hex(u.reg_read(R.UC_M68K_REG_PC)),bytes(u.mem_read(u.reg_read(R.UC_M68K_REG_PC),8)).hex());raise
     assert u.reg_read(R.UC_M68K_REG_PC)==0x20000
     assert u.reg_read(R.UC_M68K_REG_D0)==int(change is None),(n,pa,pb,change)
     for i in list(range(2,8))+list(range(10,15)):assert u.reg_read(regs[i])==values[i],(n,i)
     assert u.reg_read(R.UC_M68K_REG_A7)==0x90004
     if n:assert bytes(u.mem_read(a,n))==data and bytes(u.mem_read(b,n))==bytes(other)
     cases+=1
 report=dict(pass_=True,cases=cases,max_bytes=64548,all_four_parity_pairs=True,zero_length=True,first_middle_last_mismatch=True,callee_saved_and_SP=True,no_source_overread_or_write=True,module_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),synthetic_only=True)
 (artifact_dir('glyph')/'glyph-compare-test-results.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))

if __name__=='__main__':main()
