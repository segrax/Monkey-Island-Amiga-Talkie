"""Check music-register wrappers against the prior compiled adapters."""
import argparse,json,os,random
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',required=True,type=Path);args=p.parse_args();current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build);ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'register_fixture'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns);ns['call']('_nv_driver_start')
 ns['sample_callbacks']=[ns['get'](ns['sym']('_nv_driver')+54*c+46,4) for c in range(2)]
 assert len(set(ns['sample_callbacks']))==1
 for pointer in ns['sample_callbacks']:
  assert bytes(ns['cpu'].mem_read(pointer,10))==bytes.fromhex('202f0008204010104e75')
 return ns

def native_state(ns):
 raw=bytearray(ns['cpu'].mem_read(ns['sym']('_nv_driver'),108))
 # Normalize only the initialized, unchanged sample-reader relocation.
 for c,pointer in enumerate(ns['sample_callbacks']):
  offset=54*c+46
  assert int.from_bytes(raw[offset:offset+4],'big')==pointer,'Sample callback changed'
  assert bytes(ns['cpu'].mem_read(pointer,10))==bytes.fromhex('202f0008204010104e75')
  raw[offset:offset+4]=b'CALL'
 return bytes(raw)
old,new=load(args.baseline),load(current);rng=random.Random(7729);cases=0;counts={}
for address in (0xb6a,0xe82,0xea0,0xac2,0xb90,0xba2,0xe8c,0xeaa,
                0x84a,0x8ae,0xac8,0xd5c,0xd76,0xdc4,0x96a,0xb0e):
 patch=next(p for p in new['meta']['patches'] if p['address']==address)
 for channel in range(4):
  for case in range(48):
   results=[]
   initial=[rng.getrandbits(32) for i in range(8)]
   initial[0]=(initial[0]&0xffff0000)|rng.choice((0,1,63,64,65,127,128,255,65535));initial[1]=rng.choice((0,1,32,63,64,127,65535))
   for ns in (old,new):
    cpu=ns['cpu'];r=ns['r'];ns['put'](0x6070c0,case%2 if address in (0x84a,0xd5c) else 0,2)
    ns['put'](0x60802a,0xabcd,2);ns['put'](0x6070a0,0x1234,2)
    # ADDQ replay must retain carry/overflow, unlike final MOVE.W sites.
    ns['put'](0x607040,(0,1,0x7fff,0x8000,0xfffe,0xffff)[case%6],2)
    for c in range(2):
     base=ns['sym']('_nv_driver')+54*c
     ns['put'](base+40,(case>>c)&1,2)
     ns['put'](base+42,case%3==0,2)

    cpu.reg_write(r.UC_M68K_REG_SR,case&31)
    regs=[getattr(r,'UC_M68K_REG_D'+str(i)) for i in range(8)]+[getattr(r,'UC_M68K_REG_A'+str(i)) for i in range(8)]
    values=initial+[0x609000,0x500100,0x609100,0x609200,ns['bank']+16*channel,0x607000,0x608000,0x50f000]
    for reg,value in zip(regs,values):cpu.reg_write(reg,value)
    count=[0]
    def step(*unused):count[0]+=1
    hook=cpu.hook_add(ns['unicorn'].UC_HOOK_CODE,step)
    stop=0x500100 if patch.get('terminal') else ns['bases'][0]+patch['continuation']
    cpu.emu_start(ns['bases'][0]+address,stop,count=200000);cpu.hook_del(hook)
    assert cpu.reg_read(r.UC_M68K_REG_PC)==stop,(hex(address),channel,case)
    # Materialize Unicorn's lazy condition flags using an actual 68000 MOVE SR.
    cpu.mem_write(0x500200,bytes.fromhex('40f900609f00'));cpu.emu_start(0x500200,0x500206,count=1)
    results.append(([cpu.reg_read(reg) for reg in regs],ns['get'](0x609f00,2)&31,dict(ns['hardware']),bytes(cpu.mem_read(ns['bank'],64)),native_state(ns),bytes(cpu.mem_read(ns['bases'][0]+0x17e2,16))))
    if case==0:counts.setdefault(hex(address)+'/channel'+str(channel),[]).append(count[0])
   assert results[0]==results[1],(hex(address),channel,case,results[0][:2],results[1][:2])
   cases+=1
os.environ['MONKEY_ENGINE_BUILD']=current
report=dict(pass_=True,cases=cases,registers_ccr_stack_pointer_bank_hardware=True,live_dma_and_event_flags=True,sample_callback_relocation_verified=True,all_register_write_sites=True,representative_instructions=counts,scope='compiled 68000 wrapper differential; hardware/OS mocks')
(new['BUILD']/'register-wrapper-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
