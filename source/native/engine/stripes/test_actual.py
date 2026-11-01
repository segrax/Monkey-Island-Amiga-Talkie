"""Replay coherent post-lastdraw globals; this is not a captured call-entry trace."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json,random,struct,sys
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
import unicorn
from unicorn import m68k_const as R
ramfile=ROOT/'tests/fixtures/combined-ram.bin'
ram=ramfile.read_bytes();gen=json.loads((BUILD / 'generation.json').read_text());kernel=(BUILD / 'stripe.bin').read_bytes()
g=0x289d28;h0=0x271b30;clone=0xb00000
regs=[getattr(R,'UC_M68K_REG_'+s) for s in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
rng=random.Random(0x15270);outputs=[];traces=[];writes=[]
initial=[rng.randrange(2**32)for _ in regs];initial[-1]=0xe0f000
for new in (False,True):
 c=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);c.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);c.mem_map(0,0x1000000);c.mem_write(0,ram);c.mem_write(clone,kernel)
 for off in gen['absolute_h2_relocations']:c.mem_write(clone+off,struct.pack('>I',int.from_bytes(c.mem_read(clone+off,4),'big')+g))
 c.mem_write(0xe0f000,struct.pack('>I',0xf00000));c.reg_write(R.UC_M68K_REG_SR,31)
 for reg,value in zip(regs,initial):c.reg_write(reg,value)
 trace=[];wr=[]
 def execute(uc,pc,size,unused):trace.append((pc,size))
 def write(uc,access,a,n,v,unused):
  assert a>=g+0x6812 and a+n<=g+0x6912 or 0x300000<=a and a+n<=0x370000 or 0xe0ee00<=a and a+n<=0xe0f000,(hex(a),n)
  wr.append((a,n,v))
 ch=c.hook_add(unicorn.UC_HOOK_CODE,execute);wh=c.hook_add(unicorn.UC_HOOK_MEM_WRITE,write)
 c.emu_start(clone if new else h0+0x15190,0xf00000,count=200000);c.hook_del(ch);c.hook_del(wh);assert c.reg_read(R.UC_M68K_REG_PC)==0xf00000
 c.mem_write(0xf00000,bytes.fromhex('40f900f00100'));c.emu_start(0xf00000,0xf00006,count=1)
 outputs.append((tuple(c.reg_read(v)for v in regs),bytes(c.mem_read(0xf00100,2)),bytes(c.mem_read(0,len(ram))),bytes(c.mem_read(0xe0ee00,0x204))))
 traces.append(trace);writes.append(wr)
assert outputs[0]==outputs[1] and writes[0]==writes[1] and len(traces[0])==len(traces[1])
shortened={x['old']:x['old_size'] for x in gen['branches']};savings=0;hist={}
for i,(pc,size)in enumerate(traces[0][:-1]):
 off=pc-h0;hist[hex(off)]=hist.get(hex(off),0)+1
 if off in shortened and traces[0][i+1][0]==pc+shortened[off]:savings+=4
report=dict(kernel_sha256=gen['kernel_sha256'],snapshot_sha256=hashlib.sha256(ram).hexdigest(),snapshot='Post-lastdraw coherent globals, not call-entry capture',height=ram[g+0x5c38],cases=1,full_register_CCR_stack_RAM_and_write_sequence_exact=True,instructions=len(traces[0]),saved_documented_core_cycles=savings,excludes_DMA_bus_and_runtime_measurement=True,original_instruction_hits=hist)
(BUILD / 'actual-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='original_instruction_hits'},indent=2))
