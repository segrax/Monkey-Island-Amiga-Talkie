from pathlib import Path
import json,itertools
B=Path(__file__).resolve().parent
exec(compile((B/'test_quiet_fixture.py').read_text(),str(B/'test_quiet_fixture.py'),'exec'))
counts=0
for c,enabled,master,operation,fetch_order,stage in itertools.product(range(2),range(2),range(2),('set','ack'),('before','after'),('plain','reload')):
 n=fixture();cpu=n['cpu'];get=n['get'];put=n['put'];call=n['call'];sym=n['sym'];q=sym('_nv_quiet');owner=sym('_nv_music_owner');p=n['driver']+54*c;bit=0x80<<c;hw=n['hardware'];bank=n['bank'];flag=n['bases'][0]+0x17e2+4*c;signal=[]
 call('_nv_driver_start');put(owner,1,2);put(q+28,bit,2);put(q+38,0,2)
 for off,value,size in [(0,0x606000,4),(4,128,4),(8,0x605000,4),(12,512,4),(16,3,4),(20,0,4),(24,428,4),(28,428,4),(36,47,2),(38,1,2),(40,enabled,2),(42,0,2)]:put(p+off,value,size)
 put(n['driver']+n['layout']['last_tick'],100,4);put(flag,0,1);put(bank+16*c,0x606000,4);put(bank+16*c+4,64,2);put(bank+16*c+6,428,2);put(bank+16*c+8,47,2)
 put(0xdff0a0+16*c,0x605000,4);put(0xdff0a4+16*c,256,2)
 hw[0xdff096]=0x200|(1<<c);put(0xdff002,hw[0xdff096],2);hw[0xdff09a]=(0x4000 if master else 0)|bit;put(0xdff01c,hw[0xdff09a],2);hw[0xdff09c]=bit if fetch_order=='before' else 0;put(0xdff01e,hw[0xdff09c],2)
 def watch(uc,access,address,size,value,_):
  if address==flag and value==255:signal.append(1)
 h=cpu.hook_add(n['unicorn'].UC_HOOK_MEM_WRITE,watch)
 if stage=='reload':
  n['write'](c,0,0x606080,4);n['write'](c,4,32)
  assert get(0xdff0a0+16*c,4)==0x605000 and get(0xdff0a4+16*c,2)==256,'client overwrote owned first fetch'
 call('_nv_driver_control',2,bit|(0x8000 if operation=='set' else 0))
 assert get(q+28,2)==bit,'client consumed owned fetch'
 if fetch_order=='after':hw[0xdff09c]|=bit;put(0xdff01e,hw[0xdff09c],2)
 assert hw[0xdff09c]&bit,'client ACK cleared owned fetch'
 if not master:call('_nv_driver_control',1,0xc000)
 call('_nv_driver_irq');assert get(q+28,2)==0
 assert get(0xdff0a0+16*c,4)==(0x606080 if stage=='reload' else 0x606000)
 assert get(0xdff0a4+16*c,2)==(32 if stage=='reload' else 64)
 if operation=='set' and not enabled:call('_nv_driver_control',1,0x8000|bit)
 assert len(signal)==(1 if operation=='set' else 0),(c,enabled,master,operation,fetch_order,stage,len(signal))
 cpu.hook_del(h);counts+=1
# DMA clear while prime must retire the private prime ownership and restore logical IRQ enable.
for c in range(2):
 n=fixture();n['call']('_nv_driver_start');p=n['driver']+54*c;q=n['sym']('_nv_quiet');bit=0x80<<c
 for off,value,size in [(0,0x605000,4),(4,512,4),(8,0x605000,4),(12,512,4),(24,428,4),(28,428,4),(38,1,2),(40,1,2)]:n['put'](p+off,value,size)
 n['put'](q+28,bit,2);n['put'](n['driver']+n['layout']['dma_bits'],0x200|(1<<c),2)
 n['hardware'][0xdff09a]|=bit;n['put'](0xdff01c,n['hardware'][0xdff09a],2)
 n['call']('_nv_driver_control',0,1<<c)
 assert n['get'](q+28,2)==0
 assert n['hardware'][0xdff09a]&bit,'prime cancellation lost logical IRQ enable'
 counts+=1
j={'pass_':True,'cases':counts,'scope':'Actual compiled driver with fake MMIO; both source channels, logical enable/master states, SET/ACK, fetch-before/fetch-after, staged LC/LEN, DMA cancellation. Not physical DMA-pipeline qualification.'};(n['BUILD']/'quiet-prime-validation.json').write_text(json.dumps(j,indent=2));print(json.dumps(j,indent=2))
