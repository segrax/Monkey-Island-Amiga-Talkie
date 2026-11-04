"""Check the compiled hybrid IRQ's C ABI saves and untouched RTE frame."""
import argparse,json,os,random,struct
from pathlib import Path
HERE=Path(__file__).resolve().parent
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--baseline',type=Path,help='Optional preceding core; default is the full-save IRQ envelope calling this core');args=p.parse_args();current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_hybrid_driver.py').read_text().split("\ncall('_nv_driver_start')",1)[0]
def load(build,route):
 os.environ['MONKEY_ENGINE_BUILD']=str(build);ns={'__file__':str(HERE/'test_hybrid_driver.py'),'__name__':'irq_fixture','NATIVE_START':route=='NATIVE'}
 exec(compile(prefix,str(HERE/'test_hybrid_driver.py'),'exec'),ns);ns['call']('_nv_driver_start')
 if route=='PRIME':
  for _ in range(3):ns['dma_irq']()
  ns['call']('_nv_driver_service')
  assert ns['get'](ns['sym']('_nv_music_owner'),2)==1
  assert ns['get'](ns['sym']('_nv_quiet_muted'),2)==0x180
 return ns
rng=random.Random(70034)
for route in ('MIX','NATIVE','PRIME'):
 old,new=load(args.baseline or current,route),load(current,route)
 if args.baseline is None:
  # Original full-save interrupt envelope as an independent ABI control. Keep
  # it outside generated code so it cannot overwrite another exported helper.
  old['entry']=0x500400
  old['cpu'].mem_write(old['entry'],bytes.fromhex('48e7fffe007c07004eb9')+
                       struct.pack('>I',old['sym']('_nv_driver_irq'))+bytes.fromhex('4cdf7fff4e73'))
  old['end']=old['entry']+18

 for case in range(64):
  values=[rng.getrandbits(32) for _ in range(15)];results=[]
  for ns in (old,new):
   cpu,r=ns['cpu'],ns['r'];call,put=ns['call'],ns['put']
   # Exercise every IRQ path, including silent/music/speech/partial tails.
   call('_nv_driver_control',0,0x200)
   for c in range(2):
    cpu.mem_write(0x605000+512*c,bytes(range(256))*2)
    for off,value,size in ((0,0x605000+512*c,4),(4,(1,2,4,8,7,256)[case%6],2),(6,(0,124,161,322,642,856,1141,568)[case%8],2),(8,64 if case%3 else 0,2)):
     ns['write'](c,off,value,size)
   call('_nv_driver_control',0,0x8203);call('_nv_driver_control',1,0x8780)
   for off,value in ((8,case+1),(10,case+1 if case%7==0 else 0),(6,3),(12,0),(14,(0,1,255,256)[case%4]),(16,case%2),(26,case%65)):
    put(ns['voice']+off,value,2)
   cpu.mem_write(ns['pcm'],bytes(reversed(range(256))))
   ns['ticks']+=713
   ns['hardware'][0xdff09c]|=0x680;put(0xdff01e,ns['hardware'][0xdff09c],2)
   regs=[getattr(r,'UC_M68K_REG_D'+str(i)) for i in range(8)]+[getattr(r,'UC_M68K_REG_A'+str(i)) for i in range(7)]
   cpu.reg_write(r.UC_M68K_REG_SR,0x2300|(case&31))
   for reg,value in zip(regs,values):cpu.reg_write(reg,value)
   frame=struct.pack('>HI',((case%2)<<13)|(case&31),0x60f000)+b'\xa5'*16
   cpu.mem_write(0x50f000,frame);cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
   end=ns.get('end',ns['sym']('_nv_music_tick')-2)
   assert bytes(cpu.mem_read(end,2))==b'\x4e\x73','Expected final RTE'
   cpu.emu_start(ns.get('entry',ns['sym']('_nv_irq')),end,count=500000)
   assert cpu.reg_read(r.UC_M68K_REG_PC)==end
   assert [cpu.reg_read(reg) for reg in regs]==values,(case,'register clobbered')
   assert cpu.reg_read(r.UC_M68K_REG_A7)==0x50f000,(case,'stack imbalance')
   assert bytes(cpu.mem_read(0x50f000,len(frame)))==frame,(case,'exception frame overwritten')
   results.append((dict(ns['hardware']),bytes(cpu.mem_read(ns['voice'],40)),[ns['out'](s,b) for s in range(2) for b in range(2)],bytes(cpu.mem_read(ns['sym']('_nv_driver'),108))))
  assert results[0]==results[1],(case,'IRQ audio/state difference')
os.environ['MONKEY_ENGINE_BUILD']=current
report=dict(pass_=True,cases=192,ownership_modes=['MIX','NATIVE','PRIME'],all_data_address_registers_preserved=True,stack_and_rte_frame_preserved=True,audio_and_live_state_identical=True,scope='compiled 68000 IRQ through final RTE boundary; explicit OS/Paula mocks')
(new['BUILD']/'irq-register-equivalence.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
