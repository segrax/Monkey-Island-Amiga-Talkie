"""Compare compiled resampler work for note periods captured from the game."""
import argparse,json,os
from pathlib import Path
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--baseline',type=Path,required=True);args=parser.parse_args();current=os.environ['MONKEY_ENGINE_BUILD']
prefix=(HERE/'test_driver.py').read_text().split("call('_nv_driver_start')",1)[0]
def load(build):
 os.environ['MONKEY_ENGINE_BUILD']=str(build);ns={'__file__':str(HERE/'test_driver.py'),'__name__':'batch_fixture'}
 exec(compile(prefix,str(HERE/'test_driver.py'),'exec'),ns)
 ns['cpu'].mem_map(0x900000,0x20000)
 ns['cpu'].mem_write(0x900000,bytes(range(256))*256)
 return ns
old,new=load(args.baseline),load(current);cases=[]
for length in (16,64,512,4096):
 for period in (62,81,124,160,161,254,322,428,568,642,856,1141,65535):
  for elapsed in (0,period-1):
   results=[];counts=[]
   function='_nv_hybrid_channel'
   if 322<=period<1288 and all('_nv_hybrid_channel_runs' in ns['meta']['exports'] for ns in (old,new)):
    function='_nv_hybrid_channel_runs'
   for ns in (old,new):
    cpu=ns['cpu'];snapshot,row,source,output=0x604000,0x605200,0x900000,0x606000
    cpu.mem_write(source,bytes(range(256))*2);cpu.mem_write(row,bytes(range(256)))
    words=(source,length,source,length,0,elapsed,period,period)
    cpu.mem_write(snapshot,b''.join(w.to_bytes(4,'big') for w in words))
    count=[0]
    def step(*unused):count[0]+=1
    hook=cpu.hook_add(ns['unicorn'].UC_HOOK_CODE,step)
    ns['call'](function,snapshot,row,161,output)
    cpu.hook_del(hook);results.append(bytes(cpu.mem_read(output,256)));counts.append(count[0])
   assert results[0]==results[1],(length,period,elapsed)
   cases.append(dict(function=function,length=length,period=period,elapsed=elapsed,baseline_instructions=counts[0],current_instructions=counts[1]))
os.environ['MONKEY_ENGINE_BUILD']=current
report=dict(pass_=True,cases=cases,scope='compiled 68000 exact-output/instruction comparison; not a cycle or whole-game benchmark')
(new['BUILD']/'resampler-batches.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
