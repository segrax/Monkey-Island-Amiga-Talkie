"""68000 documented core/EA timing estimate; excludes all bus/DMA waitstates."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
import capstone
from capstone import m68k_const as M
class CoreClock:
 def __init__(self,cpu,regs):
  self.cpu=cpu;self.regs=regs;self.cs=capstone.Cs(capstone.CS_ARCH_M68K,capstone.CS_MODE_BIG_ENDIAN|capstone.CS_MODE_M68K_000);self.cs.detail=True;self.cache={};self.previous=None;self.total=0;self.instructions=0
 def ea(self,op,long=False):
  am=op.address_mode
  if am in (1,2):return 0
  base={3:4,4:4,5:6,6:8,7:10,11:8,12:10,16:8,17:12,18:4}[am]
  return base+(4 if long else 0)
 def cost(self,ins,nextpc,d3after,before):
  name=ins.mnemonic;ops=ins.operands
  if name.startswith('db'):
   if (d3after&65535)==(before&65535):return 12
   return 10 if nextpc!=ins.address+ins.size else 14
  if name.startswith('bra'):return 10
  if name.startswith('b')and name not in ('btst.l',):return 10 if nextpc!=ins.address+ins.size else (8 if ins.size==2 else 12)
  if name=='rts':return 16
  if name=='jmp':return 12
  if name=='movem.l':return 128 if '-(a7)'in ins.op_str else 132
  if name=='moveq':return 4
  if name in ('swap','not.w'):return 4
  if name.startswith(('lsl.','lsr.','asl.','asr.')):return (8 if name.endswith('.l') else 6)+2*ops[0].imm
  if name=='lea.l':return {17:12,6:8,7:12}[ops[0].address_mode]
  if name.startswith(('move.','movea.')):return 4+self.ea(ops[0],name.endswith('.l'))+self.ea(ops[1],name.endswith('.l'))
  if name.startswith('adda.'):return 8+self.ea(ops[0],name.endswith('.l'))
  if name.startswith(('addq.','subq.')):return 4
  if name in ('subi.w','andi.w','cmpi.w'):return 8
  if name.startswith(('tst.','cmp.','add.','sub.')):return 4+self.ea(ops[0])
  if name=='btst.l':return 4+self.ea(ops[1])
  if name=='mulu.w':return 38+2*int(ops[0].imm).bit_count()+self.ea(ops[0])
  raise AssertionError((name,ins.op_str))
 def trace(self,uc,pc,size,unused):
  if self.previous:
   ins,before=self.previous;self.total+=self.cost(ins,pc,uc.reg_read(self.regs.UC_M68K_REG_D3),before)
  if pc not in self.cache:self.cache[pc]=next(self.cs.disasm(bytes(uc.mem_read(pc,size)),pc,count=1))
  self.previous=(self.cache[pc],uc.reg_read(self.regs.UC_M68K_REG_D3));self.instructions+=1
 def finish(self,pc):
  if self.previous:
   ins,before=self.previous;self.total+=self.cost(ins,pc,self.cpu.reg_read(self.regs.UC_M68K_REG_D3),before);self.previous=None
  return self.total
