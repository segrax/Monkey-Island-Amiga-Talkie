"""Actual VBCC -O2 68000 store/MD5 with in-memory stdio and fault injection."""
from pathlib import Path
import sys,re,struct,json,hashlib
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1];sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
rd=HunkReader();assert rd.read_file(str(HERE/'store_fixture.hunk'))==0 and rd.build_segments()
cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000);cpu.mem_map(0x100000,0x700000)
bases=[0x100000,0x110000,0x120000];symbols={};sections={'CODE':0,'mocks':1,'BSS':2};section=0
for line in (HERE/'store_fixture.map').read_text().splitlines():
 if line.startswith('Symbols of '):section=sections[line[11:-1]]
 m=re.match(r'  0x([0-9a-f]+) (_\w+):',line)
 if m:symbols[m[2]]=bases[section]+int(m[1],16)
for h in rd.hunks:
 section=h.get('hunk_no',section)
 if 'data'in h:cpu.mem_write(bases[section],h['data'])
 if h['type_name']=='HUNK_ABSRELOC32':
  for target,offs in h['reloc'].items():
   for off in offs:
    at=bases[section]+off;cpu.mem_write(at,(int.from_bytes(cpu.mem_read(at,4),'big')+bases[target]).to_bytes(4,'big'))
def put(a,v,n=4):cpu.mem_write(a,(v&((1<<(n*8))-1)).to_bytes(n,'big'))
def get(a,n=4):return int.from_bytes(cpu.mem_read(a,n),'big')
def text(a):
 b=bytearray()
 while (v:=get(a,1))!=0:b.append(v);a+=1
 return bytes(b)
def call(name,*args):
 put(0x70f000,0x70e000)
 for i,a in enumerate(args):put(0x70f004+4*i,a)
 cpu.reg_write(R.UC_M68K_REG_A7,0x70f000);cpu.emu_start(symbols[name],0x70e000,count=20000000)
 assert cpu.reg_read(R.UC_M68K_REG_PC)==0x70e000,name
 return cpu.reg_read(R.UC_M68K_REG_D0)
fs={b'savegame._a_':b'unchanged original save'};open_error={};close_error=set();handles={};allocation=0x300000;fault=None;rename_n=0;events=[]
mocks={symbols['_'+n]:n for n in 'malloc free fread fwrite fclose fopen fseek ftell ferror clearerr memcmp memcpy memset strlen strcpy strcat remove rename'.split()}
def hook(uc,pc,size,data):
 global allocation,rename_n
 if pc not in mocks:return
 name=mocks[pc];sp=uc.reg_read(R.UC_M68K_REG_A7);a=lambda i:get(sp+4+i*4);ret=0;events.append(name)
 if name=='malloc':ret=allocation;allocation+=(a(0)+3)&~3
 elif name=='fopen':
  path,mode=text(a(0)),text(a(1))
  if mode==b'wb':fs[path]=b''
  if path in open_error:put(symbols['_errno'],open_error[path])
  elif path in fs:ret=0x200000+4*(len(handles)+1);handles[ret]=[path,0]
  else:put(symbols['_errno'],2)
 elif name in ('fread','fwrite'):
  p,width,n,h=a(0),a(1),a(2),a(3);path,pos=handles[h]
  if name=='fread':b=fs[path][pos:pos+width*n];uc.mem_write(p,b);ret=len(b)//width;handles[h][1]+=len(b)
  else:
   b=bytes(uc.mem_read(p,width*n));ret=n
   if fault=='write':b=b[:-1];ret=max(0,n-1)
   fs[path]=fs[path][:pos]+b+fs[path][pos+len(b):];handles[h][1]+=len(b)
 elif name=='fclose':
  path,_=handles[a(0)];ret=0xffffffff if path in close_error or fault=='close' and path.endswith(b'.tmp') else 0
 elif name=='ftell':ret=handles[a(0)][1]
 elif name=='fseek':
  h,off,origin=a(0),a(1),a(2);off=off-(1<<32) if off&0x80000000 else off
  path,pos=handles[h];handles[h][1]=(0 if origin==0xffffffff else pos if origin==0 else len(fs[path]))+off
 elif name=='memcmp':
  x,y=bytes(uc.mem_read(a(0),a(2))),bytes(uc.mem_read(a(1),a(2)));ret=(x>y)-(x<y)
 elif name in ('memcpy','memset'):
  uc.mem_write(a(0),bytes(uc.mem_read(a(1),a(2))) if name=='memcpy' else bytes([a(1)&255])*a(2));ret=a(0)
 elif name=='strlen':ret=len(text(a(0)))
 elif name in ('strcpy','strcat'):
  dest=a(0)+(len(text(a(0))) if name=='strcat' else 0);uc.mem_write(dest,text(a(1))+b'\0');ret=a(0)
 elif name=='remove':ret=0 if fs.pop(text(a(0)),None) is not None else 0xffffffff
 elif name=='rename':
  rename_n+=1;x,y=text(a(0)),text(a(1))
  if fault==f'rename{rename_n}' or fault=='rollback' and (rename_n==2 or x.endswith(b'.bak')):ret=0xffffffff
  elif x not in fs or y in fs:ret=0xffffffff
  else:fs[y]=fs.pop(x)
 uc.reg_write(R.UC_M68K_REG_D0,ret&0xffffffff)
cpu.hook_add(unicorn.UC_HOOK_CODE,hook)
ctx=call('_probe_md5');buf=0x600000;out=0x601000
vectors=[b'',b'a',b'abc',b'x'*55,b'x'*56,b'x'*64,b'x'*1025]
for b in vectors:
 cpu.mem_write(buf,b);call('_nv_md5_init',ctx);call('_nv_md5_update',ctx,buf,len(b));call('_nv_md5_finish',ctx,out)
 assert bytes(cpu.mem_read(out,16))==hashlib.md5(b).digest(),len(b)
p=call('_probe_policy');call('_nv_policy_init',p,0x12345678);put(p+8,1,2);put(p+16+6,49,2);put(p+16+8,3,2);put(p+16+10,3,2)
put(p+10,1,2);cpu.mem_write(p+272,bytes.fromhex('0003003100020003'))
path=0x602000;digest=0x602100;blob=0x603000;dest=0x604000;count=0x602200
cpu.mem_write(path,b'savegame._a_\0');cpu.mem_write(digest,b'M'*16);payload=bytes(range(128));cpu.mem_write(blob,payload)
def store():return call('_nv_metadata_save',path,digest,p,blob,len(payload),1)
def load():return call('_nv_metadata_load',path,digest,p,dest,6574,count,1)
assert store()==1;good=fs[b'savegame._a_.talkie'];assert good[:4]==b'NMT1' and good[-16:]==hashlib.md5(good[:-16]).digest()
assert good[20:36]==b'M'*16 and good[36:52]==hashlib.md5(fs[b'savegame._a_']).digest()
put(p+12,55);put(p+10,0,2);assert load()==1 and get(p+12)==0x12345678 and get(p+10,2)==1 and bytes(cpu.mem_read(dest,len(payload)))==payload
checks=[]
for off in (0,4,6,8,12,16,18,20,36,52,56,60,64,68,72,len(good)-1):
 b=bytearray(good);b[off]^=128;fs[b'savegame._a_.talkie']=bytes(b);cpu.mem_write(dest,b'\xaa'*128)
 assert load()==0xffffffff and get(count)==0 and get(p+10,2)==0 and get(dest,1)==170,off
 checks.append(off)
for f in ('write','close','rename1','rename2','rollback'):
 fs[b'savegame._a_.talkie']=good;fs.pop(b'savegame._a_.talkie.bak',None);rename_n=0;fault=f
 assert store()==0xfffffffe,f
 fault=None;assert load()==1,f
# A corrupt current file must never be hidden by a valid backup.
fs[b'savegame._a_.talkie.bak']=good;fs[b'savegame._a_.talkie']=b'bad';assert load()==0xffffffff
fs.pop(b'savegame._a_.talkie');assert load()==1
assert fs[b'savegame._a_']==b'unchanged original save'
report=dict(fixture_sha256=hashlib.sha256((HERE/'store_fixture.hunk').read_bytes()).hexdigest(),compiled_vbcc_O2_68000=True,md5_python_vectors=len(vectors),exact_sidecar_MD5_and_BE_header=True,roundtrip_seed_selectors_blob=True,malformed_cases=len(checks),write_close_rename_rollback_failures=5,missing_main_backup_validated=True,invalid_main_not_hidden_by_backup=True,original_save_untouched=True,stdio_mocked=True)
(HERE/'store-native-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
