"""Linked original text-scope and replay proofs using synthetic fonts only."""
import hashlib,json,random,struct
from glyph_fixture import Fixture,make_font,META,IMAGE,artifact_dir,OWNER,PRIMARY,MASK,FONT,T,unicorn,R

def layout(f):return struct.unpack('>4H',bytes(f.c.mem_read(f.t.addr('_nv_glyph_layout'),8)))
def flag(f,i):return int.from_bytes(f.c.mem_read(f.t.addr('_nv_glyph')+layout(f)[i],2),'big')
def begin(f):
 f.c.mem_write(f.g+0x60d5,bytes((FONT,)));f.call('_nv_glyph_scope_begin',(T.STACK+42,))
 assert flag(f,2) and not flag(f,3)
def scoped_draw(f,reference,seed):
 c=f.c;rng=random.Random(seed);regs=[rng.getrandbits(32) for _ in T.REGS];regs[-1]=T.STACK;regs[-3]=T.STACK+32
 c.reg_write(R.UC_M68K_REG_SR,seed&31)
 for reg,value in zip(T.REGS,regs):c.reg_write(reg,value)
 target=f.t.bases[0]+0x12b9e;c.mem_write(T.STACK,struct.pack('>I',target));c.mem_write(T.STACK+36,struct.pack('>I',f.t.bases[0]+0xe132));reads=[]
 def palette(c,access,at,n,value,_):
  if f.g+0x5920<=at<f.g+0x5924:reads.append((at-f.g-0x5920,n))
 hook=c.hook_add(unicorn.UC_HOOK_MEM_READ,palette)
 c.emu_start(f.t.addr('_engine_font2') if reference else f.t.bases[0]+0x16020,target,count=3000000);c.hook_del(hook)
 assert c.reg_read(R.UC_M68K_REG_PC)==target
 c.mem_write(T.STOP,bytes.fromhex('40f900e00100'));c.emu_start(T.STOP,T.STOP+6,count=1)
 return tuple(c.reg_read(r) for r in T.REGS),bytes(c.mem_read(T.STOP+256,2)),bytes(c.mem_read(f.g,29312)),bytes(c.mem_read(PRIMARY,64006)),bytes(c.mem_read(MASK,8006)),reads

def main():
 font,data,records=make_font([(w,h,lambda x,y:(x+3*y)&3) for w,h in ((2,1),(8,9),(9,15),(3,103))])
 f=Fixture(font,data);f.load();begin(f);draws=0
 for off,n,code in records:
  for phase in range(8):
   for mode in range(2):
    seed=draws;f.setup(off,phase,mode);a=scoped_draw(f,True,seed);f.setup(off,phase,mode);b=scoped_draw(f,False,seed);assert a==b,(off,phase,mode);assert flag(f,3);draws+=1
 # Actual original TST/BEQ replay at scope entry, all CCR and both branches.
 for value in (0,1,128):
  for ccr in range(32):
   c=f.c;f.call('_nv_glyph_scope_cancel');rng=random.Random(value+ccr);regs=[rng.getrandbits(32) for _ in T.REGS];regs[12]=f.g;regs[-1]=T.STACK
   c.mem_write(f.g+0x672c,bytes((value,)));c.reg_write(R.UC_M68K_REG_SR,ccr)
   for reg,v in zip(T.REGS,regs):c.reg_write(reg,v)
   end=f.t.bases[0]+(0xdfe2 if value==0 else 0xdfd6);c.emu_start(f.t.bases[0]+0xdfd0,end,count=10000)
   assert tuple(c.reg_read(r) for r in T.REGS)==tuple(regs) and flag(f,2)
   c.mem_write(T.STOP,bytes.fromhex('40f900e00100'));c.emu_start(T.STOP,T.STOP+6,count=1)
   assert int.from_bytes(c.mem_read(T.STOP+256,2),'big')&31==((ccr&16)|(4 if value==0 else 8 if value&128 else 0))
 # Actual E150 restores original frame and cancels, preserving every CCR.
 for ccr in range(32):
  begin(f);c=f.c;sp=T.STACK-256;frame=sp+28;rng=random.Random(ccr);regs=[rng.getrandbits(32) for _ in T.REGS];regs[-3]=frame;regs[-1]=sp
  c.mem_write(sp,b''.join(struct.pack('>I',rng.getrandbits(32)) for _ in range(5)));c.mem_write(frame,struct.pack('>II',0x12345678,T.STOP));c.mem_write(T.STOP+0x800,bytes.fromhex('4cdf089c4e5d4e75'))
  def run(pc):
   c.reg_write(R.UC_M68K_REG_SR,ccr)
   for reg,v in zip(T.REGS,regs):c.reg_write(reg,v)
   c.emu_start(pc,T.STOP,count=10000);c.mem_write(T.STOP,bytes.fromhex('40f900e00100'));c.emu_start(T.STOP,T.STOP+6,count=1)
   return tuple(c.reg_read(r) for r in T.REGS),bytes(c.mem_read(T.STOP+256,2))
  assert run(T.STOP+0x800)==run(f.t.bases[0]+0xe150) and not flag(f,2)
 # ANY DDDC cancels before dialogue helper, including voice-hold early return.
 for hold in (0,1):
  begin(f);seen=[];c=f.c
  def helper(c,pc,size,_):
   if pc==f.t.addr('_nv_dialogue_display'):
    assert not flag(f,2);seen.append(1);sp=c.reg_read(R.UC_M68K_REG_A7);c.reg_write(R.UC_M68K_REG_D0,hold);c.reg_write(R.UC_M68K_REG_PC,T.u32(c,sp));c.reg_write(R.UC_M68K_REG_A7,sp+4)
  hook=c.hook_add(unicorn.UC_HOOK_CODE,helper);c.reg_write(R.UC_M68K_REG_A7,T.STACK);c.mem_write(T.STACK,struct.pack('>I',T.STOP));end=T.STOP if hold else f.t.bases[0]+0xdde4;c.emu_start(f.t.bases[0]+0xdddc,end,count=10000);c.hook_del(hook);assert seen==[1]
 # Whole-font immutability is established before arming, not assumed from one glyph.
 if '_nv_glyph_scope_lookup' in META['exports']:
  f=Fixture(font,data);f.load();off=records[0][0];f.setup(off);f.c.mem_write(OWNER+6+20,b'\x7f');begin(f);scoped_draw(f,False,3);assert not flag(f,3)
  # Restoring data between scopes and beginning again permits a new full proof.
  f.c.mem_write(OWNER+6+20,font[20:21]);begin(f);f.setup(off);scoped_draw(f,False,4);assert flag(f,3)
 # Revocation bypasses all C; all input CCR combinations remain exact.
 f=Fixture(font,data);f.load();off=records[1][0];f.c.mem_write(f.t.addr('_nv_glyph')+98,b'\0\0')
 for ccr in range(32):
  for mode in (0,1):
   for h in (0,1,9,128,255):
    f.setup(off,ccr%8,mode);f.c.mem_write(f.g+0x6f5a,bytes((h,)));a=f.draw(True,ccr);f.setup(off,ccr%8,mode);f.c.mem_write(f.g+0x6f5a,bytes((h,)));b=f.draw(False,ccr);assert a==b,(ccr,mode,h)
 report=dict(pass_=True,module_sha256=hashlib.sha256(IMAGE.read_bytes()).hexdigest(),synthetic_only=True,scoped_draws=draws,entry_ccr=96,exit_ccr=32,dialogue_cancel=2,whole_font_before_arm='_nv_glyph_scope_lookup' in META['exports'],revoked_fallback=320)
 out=artifact_dir('glyph')/'glyph-scope-test-results.json';out.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
if __name__=='__main__':main()
