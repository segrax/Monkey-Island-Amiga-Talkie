from pathlib import Path
import json
B=Path(__file__).resolve().parent
exec(compile((B/'test_quiet_fixture.py').read_text(),str(B/'test_quiet_fixture.py'),'exec'))
CASES=0

def setup(period=428,prepare=0):
 n=fixture();n['call']('_nv_driver_start');n['ticks']+=71001
 for c,value in enumerate((20,40)):
  n['cpu'].mem_write(0x605000+512*c,bytes([value])*512)
  for off,v,size in [(0,0x605000+512*c,4),(4,256,2),(6,period,2),(8,64,2)]:n['write'](c,off,v,size)
 n['call']('_nv_driver_control',0,0x8203)
 n['put'](n['voice']+8,7,2);n['put'](n['voice']+12,0,2);n['put'](n['voice']+14,511,2)
 n['put'](n['voice']+16,1,2);n['put'](n['voice']+6,3,2);n['put'](n['voice']+26,64,2)
 n['cpu'].mem_write(n['pcm'],bytes([244])*511)
 clocks=[0]
 def delay(uc,pc,size,_):
  if pc in n['clock_now_addresses']:
   clocks[0]+=1
   if clocks[0]==2:
    n['ticks']=(n['ticks']+prepare)&0xffffffff
    uc.reg_write(n['r'].UC_M68K_REG_D0,n['ticks'])
 n['cpu'].hook_add(n['unicorn'].UC_HOOK_CODE,delay)
 return n

def irq(n,t):
 n['ticks']=t&0xffffffff;n['hardware'][0xdff09c]|=0x80
 n['put'](0xdff01e,n['hardware'][0xdff09c],2);n['call']('_nv_driver_irq')

# Budget refusal leaves native hardware running and restores all consumed voice metadata.
for period,delay,accept in ((428,0,True),(1530,1500,True),(428,7600,False),(65535,0,False)):
 n=setup(period,delay);d=n['driver'];v=n['voice'];q=n['sym']('_nv_quiet');owner=n['sym']('_nv_music_owner')
 vb=bytes(n['cpu'].mem_read(v,44));db=bytes(n['cpu'].mem_read(d,n['layout']['size']))
 start=len(n['writes']);epoch=n['ticks'];timeline=[]
 def writes(uc,access,a,size,value,_):
  if 0xdff000<=a<0xdff100:timeline.append((a,value,n['ticks']))
  assert a not in (0xdff0aa,0xdff0ba),'Unexpected AUDxDAT write'
  if n['get'](owner,2)==0 and n['get'](d+n['layout']['first_irq'],2)==0 and (n['ptr'](0,1)<=a<n['ptr'](0,1)+256 or n['ptr'](1,1)<=a<n['ptr'](1,1)+256):
   assert n['get'](0xdff0a8,2)==n['get'](0xdff0b8,2)==64,'Bank1 rendered before first-fetch unmute'
 n['cpu'].hook_add(n['unicorn'].UC_HOOK_MEM_WRITE,writes)
 n['call']('_nv_driver_service')
 if not accept:
  assert n['get'](owner,2)==1,(period,delay,n['get'](owner,2),n['get'](n['sym']('_nv_quiet_prepare_refused'),4))
  assert bytes(n['cpu'].mem_read(v,44))==vb
  # Failed preparation may invalidate inactive output clean bits, but does not advance serials/tails/frames.
  after=bytes(n['cpu'].mem_read(d,n['layout']['size']))
  assert after[:348]==db[:348] and after[352:]==db[352:]
  assert not any(a==0xdff096 and value==3 for a,value,t in timeline)
  CASES+=1;continue
 assert n['get'](owner,2)==0 and n['get'](v+12,2)==256
 assert n['get'](d+352,4)==(epoch*5+256*161)&0xffffffff
 assert n['out'](0,0)==bytes([4])*256 and n['out'](1,0)==bytes([14])*256
 assert n['get'](0xdff0a8,2)==n['get'](0xdff0b8,2)==0
 off=next(i for i,x in enumerate(timeline) if x[0]==0xdff096 and x[1]==3)
 ack=next(i for i in range(off+1,len(timeline)) if timeline[i][0]==0xdff09c)
 required=period+4*124+456+4
 assert 5*((timeline[ack][2]-timeline[off][2])&0xffffffff)>=required
 assert not any(a in (0xdff0aa,0xdff0ba) for a,value,t in timeline)
 physical=n['ticks'];irq_start=len(n['writes']);irq(n,physical+1)
 assert n['get'](v+12,2)==511 and n['get'](v+6,2)==5
 assert n['out'](0,1)==bytes([4])*255+bytes([10])
 assert n['out'](1,1)==bytes([14])*255+bytes([20])
 # Gain writes precede any render-bank output write in the genuine initial fetch callback.
 assert n['get'](0xdff0a8,2)==n['get'](0xdff0b8,2)==64
 for i in range(1,4):
  irq(n,physical+((i*256-2)*161)//5);n['call']('_nv_driver_service')
 assert n['get'](v+20,2)==7 and n['get'](owner,2)==1
 assert n['get'](d+356,4)==0
 assert n['get'](q+28,2)==0x180
 offs=[i for i,x in enumerate(timeline) if x[0]==0xdff096 and x[1]==3]
 assert len(offs)==2
 second_ack=next(i for i in range(offs[1]+1,len(timeline)) if timeline[i][0]==0xdff09c)
 assert 5*((timeline[second_ack][2]-timeline[offs[1]][2])&0xffffffff)>=161+4*124+456+4
 # Both native channels remain muted until their separately owned startup fetch.
 for c in range(2):
  assert n['get'](0xdff0a8+16*c,2)==0
 n['hardware'][0xdff09c]|=0x180;n['put'](0xdff01e,n['hardware'][0xdff09c],2);n['call']('_nv_driver_irq')
 assert n['get'](q+28,2)==0 and n['get'](0xdff0a8,2)==32 and n['get'](0xdff0b8,2)==32
 assert n['nesting']==-1
 CASES+=1

# Attachment and unknown-long counters defer BEFORE consuming speech or stopping hardware.
for attach in (1,2,0x10,0x20):
 n=setup();n['put'](0xdff010,attach,2);n['call']('_nv_driver_service')
 assert n['get'](n['sym']('_nv_music_owner'),2)==1 and n['get'](n['voice']+12,2)==0
 CASES+=1

# Bound is sampled after pending flag handling, not before it.
n=setup();bit=0x80;n['hardware'][0xdff09a]|=bit;n['put'](0xdff01c,n['hardware'][0xdff09a],2)
n['hardware'][0xdff09c]|=bit;n['put'](0xdff01e,bit,2)
def change_period(uc,access,a,size,value,_):
 if a==n['bases'][0]+0x17e2 and value==255:
  n['put'](n['sym']('_nv_quiet_period_bound'),65536,4)
n['cpu'].hook_add(n['unicorn'].UC_HOOK_MEM_WRITE,change_period);n['call']('_nv_driver_service')
assert n['get'](n['sym']('_nv_music_owner'),2)==1 and n['get'](n['voice']+12,2)==0
CASES+=1

# A drain may cross a reload: resumed descriptors are selected from freshly advanced live state.
n=setup();n['call']('_nv_driver_service');irq(n,n['ticks']+1)
for c in range(2):
 p=n['driver']+54*c
 for off,value,size in ((0,0x606000,4),(4,128,4),(8,0x605000,4),(12,512,4),(16,511,4),(20,400,4),(24,428,4),(28,428,4)):
  n['put'](p+off,value,size)
 n['cpu'].mem_write(0x606000,bytes([10])*128)
n['put'](n['voice']+6,7,2);n['put'](n['sym']('_nv_quiet')+30,0,2);n['put'](n['sym']('_nv_quiet')+32,2,2)
n['call']('_nv_driver_service')
assert n['get'](n['sym']('_nv_music_owner'),2)==1
for c in range(2):
 p=n['driver']+54*c
 assert n['get'](p+8,4)==0x606000
 assert n['get'](0xdff0a0+16*c,4)==0x606000+(n['get'](p+16,4)&~1)
CASES+=1
# EClock and Paula target arithmetic remain modulo32 through a real drain wrap.
n=setup();n['ticks']=0xffffff80;n['put'](n['driver']+n['layout']['last_tick'],n['ticks'],4)
epoch=n['ticks'];n['call']('_nv_driver_service')
assert n['get'](n['sym']('_nv_music_owner'),2)==0
assert n['get'](n['driver']+352,4)==(epoch*5+256*161)&0xffffffff
irq(n,n['ticks']+1);assert n['get'](n['voice']+12,2)==511 and n['get'](n['driver']+356,4)==0
CASES+=1

j={'pass_':True,'cases':CASES,'one_bank_preparation':True,'all_511_speech_bytes_once':True,'initial_fetch_unmutes_before_bank1':True,'epoch_not_rebased':True,'both_directions_quiesce_before_ACK_restart':True,'long_counter_and_attachment_defer_before_stop':True,'budget_refusal_restores_voice_serials_tail':True,'post_pending_bound_order':True,'drain_reload_fresh_cursor':True,'resyncs_in_directed_cadence':0,'scope':'Actual linked private driver with fake Exec/MMIO and advancing mock clock. Physical state-machine bound is source-backed; real capture still required.'}
(n['BUILD']/'quiet-restart-validation.json').write_text(json.dumps(j,indent=2)+'\n');print(json.dumps(j,indent=2))


