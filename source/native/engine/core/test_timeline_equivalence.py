"""Compare compiled analytical timelines, including every preserved Paula field."""
import argparse,json,os,random,struct
from pathlib import Path

HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',type=Path,help='Optional earlier compiled core; the independent oracle always runs')
args=parser.parse_args();current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_driver.py').read_text().split("call('_nv_driver_start')",1)[0]

def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build)
 ns={'__file__':str(HERE/'test_driver.py'),'__name__':'timeline_fixture'}
 exec(compile(prefix,str(HERE/'test_driver.py'),'exec'),ns)
 return ns

old,new=load(args.baseline or current),load(current)
os.environ['MONKEY_ENGINE_BUILD']=current
rng=random.Random(0x5041554c);address=0x608000;size=54;mask=0xffffffff

def make(active,reload,period,latched,index,elapsed,dma=1,latches=0):
 # Include opaque sample, padding and callback fields: advance must preserve them.
 return struct.pack('>9I4H2B2I',0x601000,reload,0x602000,active,index,elapsed,
                    period,latched,latches,rng.randrange(65),dma,rng.randrange(2),
                    rng.randrange(2),rng.randrange(256),rng.randrange(256),
                    0x700123,0x600abc)

def reference(raw,clocks):
 fields=list(struct.unpack('>9I4H2B2I',raw))
 if not fields[10]:return raw
 first=fields[7]-fields[5]
 if clocks<first:fields[5]+=clocks
 else:
  remaining=clocks-first
  transitions=1+remaining//fields[6]
  fields[5]=remaining%fields[6];fields[7]=fields[6]
  position=fields[4]+transitions
  if position<fields[3]:fields[4]=position
  else:
   position-=fields[3]
   reloads=1+position//fields[1]
   fields[2]=fields[0];fields[3]=fields[1];fields[4]=position%fields[1]
   fields[8]=(fields[8]+reloads)&mask;fields[12]=1
 return struct.pack('>9I4H2B2I',*fields)

counts={};cases=0
abi_rng=random.Random(0x414249)
callee_saved=('D2','D3','D4','D5','D6','D7','A2','A3','A4','A5','A6')
def check(raw,clocks,label):
 global cases
 expected=reference(raw,clocks);instructions=[]
 for ns in (old,new):
  ns['cpu'].mem_write(address-4,b'PRE!'+raw+b'POST')
  registers=[getattr(ns['r'],'UC_M68K_REG_'+name) for name in callee_saved]
  saved=[abi_rng.getrandbits(32) for reg in registers]
  for reg,value in zip(registers,saved):ns['cpu'].reg_write(reg,value)
  ns['cpu'].mem_write(0x50f00c,b'POST')
  counter=[0]
  def count(uc,pc,length,unused):counter[0]+=1
  hook=ns['cpu'].hook_add(ns['unicorn'].UC_HOOK_CODE,count)
  ns['call']('_nv_paula_advance',address,clocks)
  ns['cpu'].hook_del(hook)
  assert [ns['cpu'].reg_read(reg) for reg in registers]==saved,'Timeline callee-saved register changed'
  assert ns['cpu'].reg_read(ns['r'].UC_M68K_REG_A7)==0x50f004,'Timeline stack unbalanced'
  assert bytes(ns['cpu'].mem_read(0x50f000,16))==struct.pack('>3I',0x60f000,address,clocks)+b'POST','Timeline caller stack changed'
  observed=bytes(ns['cpu'].mem_read(address-4,size+8))
  assert observed==b'PRE!'+expected+b'POST',(cases,label,clocks,raw.hex(),observed.hex(),expected.hex())
  instructions.append(counter[0])
 item=counts.setdefault(label,{'cases':0,'baseline':0,'current':0})
 item['cases']+=1;item['baseline']+=instructions[0];item['current']+=instructions[1]
 cases+=1

lengths=(2,3,15,16,64,66,65536,131072)
periods=(1,16,64,161,65535,65536)
for active in lengths:
 for reload in lengths:
  for period in periods:
   latched=periods[(periods.index(period)+1)%len(periods)]
   for index in (0,active-1):
    elapsed=latched-1
    first=latched-elapsed
    clocks=(0,first-1,first,first+period-1,first+period,
            first+period*(active-index),0x7fffffff,0xffffffff)
    raw=make(active,reload,period,latched,index,elapsed,latches=0xfffffffe)
    for clock in clocks:
     if clock<=mask:check(raw,clock,'reload_'+str(reload))

# Frequent IRQ/write advances, including exact division overflow and reload edges.
for period in (1,16,64,124,161,322,428,856,65535,65536):
 for active in (2,16,256,65536,131072):
  for index in sorted(set((0,active//2,active-1))):
   latched=161;elapsed=73;first=latched-elapsed
   raw=make(active,66,period,latched,index,elapsed,latches=0xffffffff)
   for steps in (0,1,2,15,16,255,256,active-index-1,active-index,65535,65536):
    for tail in (0,period-1):
     clocks=first+steps*period+tail
     if clocks<=mask:check(raw,clocks,'common_period_'+str(period))

for period in (124,161,322,428,856):
 raw=make(65536,512,period,161,10,73)
 for clocks in (1240,31744,41216):check(raw,clocks,'long_source_no_reload_'+str(period))

for i in range(4096):
 active=rng.choice(lengths) if i%2 else rng.randrange(1,131073)
 reload=rng.choice(lengths) if i%3 else rng.randrange(1,131073)
 period=rng.choice(periods) if i%2 else rng.randrange(1,65537)
 latched=rng.choice(periods) if i%3 else rng.randrange(1,65537)
 raw=make(active,reload,period,latched,rng.randrange(active),rng.randrange(latched),
          dma=0 if i%11==0 else 1,latches=rng.getrandbits(32))
 check(raw,rng.getrandbits(32),'random')

report=dict(pass_=True,cases=cases,callee_saved_and_stack_preserved=True,baseline_differential=args.baseline is not None,instructions=counts,
            scope='compiled 68000 baseline and independent integer oracle; all 54 Paula bytes and adjacent guards; instruction counts are not cycle timings')
(new['BUILD']/('timeline-equivalence.json' if args.baseline else 'timeline-oracle.json')).write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report))
