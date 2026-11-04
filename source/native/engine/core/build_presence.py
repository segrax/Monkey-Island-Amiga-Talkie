"""Generate a text-presence superset from SHA-pinned MAT2 maps."""
import argparse,hashlib,struct
from pathlib import Path

def generate(inputs):
 bits=bytearray(8192);tokens=set()
 for path,pin in inputs:
  data=Path(path).read_bytes()
  if hashlib.sha256(data).hexdigest()!=pin:raise ValueError('Map SHA256 differs from the supplied pin')
  if data[:4]!=b'MAT2' or len(data)<64:raise ValueError('Expected MAT2')
  count=struct.unpack_from('>I',data,12)[0];at=struct.unpack_from('>I',data,28)[0]
  if struct.unpack_from('>I',data,32)[0]!=len(data):raise ValueError('Map length mismatch')
  for _ in range(count):
   size=struct.unpack_from('<H',data,at)[0];at+=2
   key=data[at:at+size];at+=size+8
   if not size or at>len(data):raise ValueError('Invalid map record')
   for token in key.split(b':'):
    token=bytes(c+32 if 65<=c<=90 else c for c in token if 48<=c<=57 or 65<=c<=90 or 97<=c<=122)
    if token:tokens.add(token)
  if at!=len(data):raise ValueError('Unexpected map tail')
 for token in tokens:
  value=5381
  for c in token:value=(((value<<5)+value)^c)&0xffffffff
  for index in (value&65535,value>>16):bits[index>>3]|=1<<(index&7)
 return bytes(bits),len(tokens)

if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--map',action='append',nargs=2,required=True,metavar=('PATH','SHA256'))
 parser.add_argument('--output',type=Path,default=Path(__file__).with_name('speech_presence.bin'))
 args=parser.parse_args();bits,count=generate(args.map);args.output.write_bytes(bits)
 print('Presence tokens:',count,'SHA256:',hashlib.sha256(bits).hexdigest())
