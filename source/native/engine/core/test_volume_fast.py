"""Compare the linked volume entry with its unchanged C fallback."""
from pathlib import Path
import json,random
HERE=Path(__file__).resolve().parent
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(model):
 original=(HERE/'test_driver.py').read_text().split("call('_nv_driver_start')",1)[0]
 original=original.replace('r.UC_CPU_M68K_M68000','r.UC_CPU_M68K_'+model)
 s=prefix.replace('prefix=(HERE/\'test_driver.py\').read_text().split("call(\'_nv_driver_start\')",1)[0]','prefix='+repr(original))
 ns=dict(__file__=str(HERE/'test_hybrid_driver.py'),__name__='volume_fixture',NATIVE_START=bool(ROUTE));exec(compile(s,str(HERE/'test_hybrid_driver.py'),'exec'),ns)
 ns['call']('_nv_driver_start');return ns
def check_route(route):
 global ROUTE,gate_checks
 ROUTE=route
 rng=random.Random(401994);cases=0;gate_checks=0
 for model in ('M68000','M68020'):
  old=load(model);new=load(model)
  entry=old['sym']('_nv_driver_write');raw=bytes(old['cpu'].mem_read(entry,256));gate=raw.index(bytes.fromhex('0c8100000008'));target=raw.index(bytes.fromhex('4ef9')+old['sym']('_nv_driver_write_virtual').to_bytes(4,'big'))-2
  assert raw[target:target+2]==bytes.fromhex('e848')
  delta=target-gate-2;old['cpu'].mem_write(entry+gate,bytes.fromhex('6000')+delta.to_bytes(2,'big')+bytes.fromhex('4e71'))
  old['cpu'].ctl_remove_cache(entry,entry+256)
  def masked_reads(cpu,access,address,size,value,unused):
   global gate_checks
   if address in (new['driver']+40,new['driver']+94):
    # Existing C reads IRQ flags after Exec Disable too.
    assert not new['hardware'][0xdff09a]&0x4000
    gate_checks+=1
  new['cpu'].hook_add(new['unicorn'].UC_HOOK_MEM_READ,masked_reads)
  for ns in (old,new):
   def idnest(cpu,pc,size,unused,ns=ns):
    if pc in (0x700800-120,0x700800-126):ns['put'](0x700800+0x126,ns['nesting']&255,1)
   ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,idnest)
  for case in range(5632):
   value=case%256 if case<1024 else rng.randrange(65536)
   channel=case&1;irqflags=[(0,0),(0,1),(1,0),(1,1)][(case//2)%4]
   master,nest=[(0x4000,-1),(0,-1),(0,0),(0,1),(0,3),(0x4000,0),(0x4000,1),(0x4000,3)][(case//8)%8]
   if case>=4096:
    number=case-4096;channel=(number//32)%2;irqflags=(0,0);master=0x4000 if number<768 else 0;nest=-1
    value=[0,1,63,64,65,127,128,255,256,32767,32768,65535][(number//64)%12]
   pending=(case//40)%4;raw=rng.randbytes(old['layout']['size']);initial=[rng.getrandbits(32) for _ in range(15)];results=[]
   for ns in (old,new):
    cpu,r=ns['cpu'],ns['r'];put=ns['put'];driver=ns['driver'];bank=ns['bank']
    cpu.mem_write(driver,raw)
    # Quiet DMA makes enabled-IRQ fallback exact without arbitrary source pointers.
    for c in range(2):
     put(driver+c*54+38,0,2);put(driver+c*54+40,irqflags[c],2);put(driver+c*54+42,(pending>>c)&1,2)
    put(driver+ns['layout']['last_tick'],100,4)
    ns['nesting']=nest;ns['hardware'][0xdff09a]=0x0800|master;put(0xdff01c,0x0800|master,2);put(0x700800+0x126,nest&255,1)
    ns['hardware'][0xdff09c]=0x780;put(0xdff01e,0x780,2)
    cpu.mem_write(bank,b'\0'*64);cpu.mem_write(ns['bases'][0]+0x17e2,b'\0'*8)
    regs=[getattr(r,'UC_M68K_REG_D'+str(i))for i in range(8)]+[getattr(r,'UC_M68K_REG_A'+str(i))for i in range(7)]
    for reg,v in zip(regs,initial):cpu.reg_write(reg,v)
    cpu.reg_write(r.UC_M68K_REG_SR,0x2000|(case&31));cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    if case<2048 or case>=4096:
     # Real production wrapper includes original volume math, mirror, X/NZ reconstruction.
     cpu.reg_write(r.UC_M68K_REG_D0,0x89ab0000|value);cpu.reg_write(r.UC_M68K_REG_D1,0x12340000|(0x40 if case&2 else 0x3f))
     cpu.reg_write(r.UC_M68K_REG_A4,bank+16*channel)
     entry=ns['sym']('_nv_native_write_96a');end=ns['sym']('_nv_continue__nv_native_write_96a')
     cpu.mem_write(end,bytes.fromhex('40f900608000'));cpu.emu_start(entry,end+6,count=100000)
     result=([cpu.reg_read(reg)for reg in regs],ns['get'](0x608000,2)&31,cpu.reg_read(r.UC_M68K_REG_A7))
    else:
     put(bank+16*channel+8,value,2);ns['call']('_nv_driver_write',bank+16*channel,8)
     result=([cpu.reg_read(reg)for reg in regs[2:8]+regs[10:]],cpu.reg_read(r.UC_M68K_REG_A7))
     expected=64 if value&64 else value&63
     assert ns['get'](driver+54*channel+36,2)==expected
    results.append((result,bytes(cpu.mem_read(driver,len(raw))),bytes(cpu.mem_read(bank,64)),dict(ns['hardware']),ns['nesting'],bytes(cpu.mem_read(ns['bases'][0]+0x17e2,8))))
   assert results[0]==results[1],(model,case,value,irqflags,master,nest,pending)
   cases+=1
 report=dict(passed=True,cases=cases,models=['M68000','M68020'],masked_irqflag_reads=gate_checks,valid_nested_master_states=True,pending_bits_not_acked=True,full_wrapper_regs_ccr=True,live_driver_mirrors_hardware_nesting_equal=True)
 (new['BUILD']/'volume-fast-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))



 cases=0
 for model in ('M68000','M68020'):
  old=load(model);new=load(model)
  entry=old['sym']('_nv_driver_write');raw=bytes(old['cpu'].mem_read(entry,256));gate=raw.index(bytes.fromhex('0c8100000008'));target=raw.index(bytes.fromhex('4ef9')+old['sym']('_nv_driver_write_virtual').to_bytes(4,'big'))-2
  old['cpu'].mem_write(entry+gate,bytes.fromhex('6000')+(target-gate-2).to_bytes(2,'big')+bytes.fromhex('4e71'));old['cpu'].ctl_remove_cache(entry,entry+256)
  for case in range(512):
   channel=case&1;stage='before' if case<256 else 'after';results=[]
   for ns in (old,new):
    cpu,r=ns['cpu'],ns['r'];put=ns['put'];driver=ns['driver'];bank=ns['bank'];fired=[False];seen_off=[False];committed=[False]
    cpu.mem_write(driver,bytes(ns['layout']['size']));put(driver+ns['layout']['last_tick'],100,4)
    prior_master=0x4000 if stage=='before' or case&32 else 0
    ns['nesting']=-1;put(0x700800+0x126,255,1);ns['hardware'][0xdff09a]=0x0800|prior_master;put(0xdff01c,0x0800|prior_master,2)
    ns['hardware'][0xdff09c]=0x780;put(0xdff01e,0x780,2);cpu.mem_write(bank,bytes(64));put(bank+16*channel+8,7,2)
    cpu.mem_write(ns['bases'][0]+0x17e2,bytes(8))
    if ns is old or not prior_master or ROUTE:trigger=ns['sym']('_nv_disable_interrupts')
    else:
     base=ns['sym']('_nv_driver_write');trigger=base+bytes(cpu.mem_read(base,256)).index(bytes.fromhex('33fc400000dff09a'))
    def store(cpu,access,address,size,value,unused):
     if address==driver+54*channel+36:
      assert not ns['hardware'][0xdff09a]&0x4000
      committed[0]=True
    def inject(cpu,pc,size,unused):
     on=bool(ns['hardware'][0xdff09a]&0x4000)
     if not on:seen_off[0]=True
     ready=pc==trigger if stage=='before' else on and seen_off[0] and committed[0]
     if ready and not fired[0]:
      fired[0]=True
      # Model an interrupt's competing mirror/IRQ update with registers restored by RTE.
      put(bank+16*channel+8,case&255,2)
      put(driver+40,int(bool(case&2)),2);put(driver+94,int(bool(case&4)),2)
      put(driver+42,int(bool(case&8)),2);put(driver+96,int(bool(case&16)),2)
    hooks=[cpu.hook_add(ns['unicorn'].UC_HOOK_MEM_WRITE,store),cpu.hook_add(ns['unicorn'].UC_HOOK_CODE,inject)]
    cpu.reg_write(r.UC_M68K_REG_SR,0x2000|(case&31));ns['call']('_nv_driver_write',bank+16*channel,8)
    for hook in hooks:cpu.hook_del(hook)
    assert fired[0],(model,case,stage)
    results.append((bytes(cpu.mem_read(driver,ns['layout']['size'])),bytes(cpu.mem_read(bank,64)),dict(ns['hardware']),ns['nesting'],bytes(cpu.mem_read(ns['bases'][0]+0x17e2,8))))
   assert results[0]==results[1],(model,case,stage)
   cases+=1
 report.update(preemption_interleavings=cases,preemption_windows=['between_prior_read_and_mask','after_commit_and_unmask','old_C_transient_enable_with_prior_master_off'],atomic_volume_store_masked=True,module_sha256=new['meta']['sha256'])
 (new['BUILD']/'volume-fast-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))

for route in (0,1):check_route(route)
