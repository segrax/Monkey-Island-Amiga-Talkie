"""Compare compiled normalization/filter tests with an independent model."""
from pathlib import Path
import argparse,json,random,struct
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('--map',type=Path);args=parser.parse_args()
src=HERE/'test_driver.py';ns={'__file__':str(src),'__name__':'presence_fixture'}
exec(compile(src.read_text().split("call('_nv_driver_start')",1)[0],str(src),'exec'),ns)
cpu=ns['cpu'];cpu.mem_map(0x900000,0x10000);context=0x900000
bits=(HERE/'speech_presence.bin').read_bytes();assert bytes(cpu.mem_read(ns['sym']('_nv_presence_bits'),8192))==bits

def reference(text):
 at=0;value=5381;used=0
 while at<len(text):
  c=text[at];at+=1
  if not c:break
  if c in (254,255):
   if at==len(text):return 1
   c=text[at];at+=1
   if c in (2,3):break
   if c in (1,8):continue
   if c not in (9,12,13,14) or len(text)-at<2:return 1
   at+=2;continue
  if 65<=c<=90:c+=32
  if 48<=c<=57 or 97<=c<=122:value=(((value<<5)+value)^c)&0xffffffff;used+=1
 if not used:return 0
 return int(all(bits[i>>3]&(1<<(i&7)) for i in (value&65535,value>>16)))

cases=0
def check(text,required=None):
 global cases
 cpu.mem_write(context,bytes(1024));ns['put'](context+272,len(text),2);cpu.mem_write(context+274,text)
 ns['call']('_nv_presence_possible',context);value=cpu.reg_read(ns['r'].UC_M68K_REG_D0)
 assert value==reference(text),(text,value,reference(text))
 if required is not None:assert value==required
 cases+=1
rng=random.Random(0x50524553)
for text in (b'',b' ',b'!~..',b'Hi!',b'I want to be a pirate',b'Unmatched filter test word',b'abc\xff\x01DEF',b'abc\xfe\x02ignored',b'\xff',b'\xff\x09x',b'\xff\x09xx'):
 check(text)
for _ in range(2048):check(rng.randbytes(rng.randrange(513)))
map_tokens=0
if args.map:
 data=args.map.read_bytes();count=struct.unpack_from('>I',data,12)[0];at=struct.unpack_from('>I',data,28)[0];tokens=set()
 for _ in range(count):
  size=struct.unpack_from('<H',data,at)[0];at+=2;tokens.update(data[at:at+size].split(b':'));at+=size+8
 for token in tokens:
  if token:check(token,1);map_tokens+=1
# A proven negative returns before IPC initialization and does not hold display.
for i in range(100):
 text=('unmappedpresenceproof%d'%i).encode()
 if not reference(text):break
else:raise AssertionError('No negative test word')
check(text,0);ns['put'](ns['sym']('_nv_presence_enabled'),1,2)
ns['call']('_nv_game_play',context);assert cpu.reg_read(ns['r'].UC_M68K_REG_D0)==0
ns['call']('_nv_game_active');assert cpu.reg_read(ns['r'].UC_M68K_REG_D0)==0
report=dict(pass_=True,cases=cases,map_tokens=map_tokens,normalization_control_codes_and_random_bytes=True,negative_does_not_queue_or_hold=True)
(ns['BUILD']/'presence-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
