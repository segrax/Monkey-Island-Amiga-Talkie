"""Compiled production worker metadata helpers with DOS-register/stdio mocks."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
src=(HERE/'test_store_native.py').read_text().split("ctx=call('_probe_md5')")[0].replace("store_fixture.hunk","worker_metadata_fixture.hunk").replace("store_fixture.map","worker_metadata_fixture.map")
exec(compile(src,str(HERE/'test_store_native.py'),'exec'))
dosbase=0x7f8000;put(symbols['_DOSBase'],dosbase)
for off in (-84,-90,-102):cpu.mem_write(dosbase+off,bytes.fromhex('4e75'))
identity={'disk':17,'days':31,'minute':22,'tick':1};statcalls=0;lockok=True;examineok=True
mapname=b'amiga-talkie.dat';fs[mapname]=b'actual opened runtime MAT2 bytes for digest test'
def doshook(uc,pc,size,data):
 global statcalls
 off=pc-dosbase;ret=0
 if off not in (-84,-90,-102):return
 if off==-84:
  assert text(uc.reg_read(R.UC_M68K_REG_D1))==mapname
  ret=0x1234 if lockok else 0
 if off==-102:
  info=uc.reg_read(R.UC_M68K_REG_D2);assert info%4==0;statcalls+=1
  put(info,identity['disk']);put(info+124,len(fs[mapname]));put(info+132,identity['days']);put(info+136,identity['minute']);put(info+140,identity['tick']);ret=int(examineok)
 uc.reg_write(R.UC_M68K_REG_D0,ret)
cpu.hook_add(unicorn.UC_HOOK_CODE,doshook)
path=0x602000;packet=0x604000;blob=0x605000;client=0x607000;mapaddr=0x602100
cpu.mem_write(mapaddr,mapname+b'\0');call('_probe_map',mapaddr)
p=call('_probe_policy');call('_nv_policy_init',p,0x12345678);put(p+8,1,2);put(p+16+6,49,2);put(p+16+8,3,2);put(p+16+10,3,2)
put(p+10,1,2);cpu.mem_write(p+272,bytes.fromhex('0003003100020003'))
payload=b'opaque origin blob';cpu.mem_write(blob,payload)
def prepare(command=6):
 cpu.mem_write(packet,b'\0'*1366);put(packet+18,1366,2);put(packet+20,2,2);put(packet+22,command,2);put(packet+28,client)
 cpu.mem_write(packet+956,b'savegame._a_\0');put(packet+1212,blob);put(packet+1216,6574);put(packet+1220,len(payload));put(packet+1224,1,2)
def request():call('_probe_request',packet,client);return get(packet+1228)
# Old saves with neither sidecar nor backup skip map hashing entirely.
prepare(7);events.clear();before=statcalls
assert request()==0 and get(packet+1220)==0 and statcalls==before
assert events.count('fopen')==2 and not any(e in events for e in ('fread','fwrite','rename'))
# Main I/O errors must not masquerade as missing or consult a backup.
open_error[b'savegame._a_.talkie']=5
prepare(7);events.clear();before=statcalls
assert request()==0xfffffffe and statcalls==before and events.count('fopen')==1
open_error.clear()
open_error[b'savegame._a_.talkie.bak']=5
prepare(7);events.clear();before=statcalls
assert request()==0xfffffffe and statcalls==before and events.count('fopen')==2
open_error.clear()
prepare();events.clear();assert request()==1
assert fs[b'savegame._a_.talkie'][20:36]==hashlib.md5(fs[mapname]).digest();assert statcalls==3
# Digest reads actual map once; later requests check identity but do not rescan it.
prepare(7);put(p+12,0x88888888);put(p+10,0,2);events.clear();before=statcalls
assert request()==1 and get(packet+1220)==len(payload) and get(packet+1232)==0x12345678 and get(packet+1236,2)==1
assert get(p+12)==0x88888888 and get(p+10,2)==0 and statcalls==before+1
# Policy remains untouched until the client validates the inner opaque blob.
assert bytes(cpu.mem_read(blob,len(payload)))==payload
# Presence is not validity: malformed main must be rejected after normal binding
# checks, and must never hide behind a valid backup.
good=fs[b'savegame._a_.talkie'];fs[b'savegame._a_.talkie.bak']=good
fs[b'savegame._a_.talkie']=b'bad';prepare(7);assert request()==0xffffffff
fs.pop(b'savegame._a_.talkie');prepare(7);assert request()==1
fs[b'savegame._a_.talkie']=good;fs.pop(b'savegame._a_.talkie.bak')
close_error.add(b'savegame._a_.talkie');prepare(7);events.clear();before=statcalls
assert request()==0xfffffffe and statcalls==before and 'fread'not in events
close_error.clear()
# Reject map replacement/changes for the process lifetime instead of binding stale index.
for field in ('disk','days','minute','tick'):
 identity[field]+=1;prepare();assert request()==0xfffffffe;identity[field]-=1
fs[mapname]+=b'x';prepare();assert request()==0xfffffffe;fs[mapname]=fs[mapname][:-1]
# Exact bounded request/name rules prevent arbitrary filesystem paths.
cases=[(18,1365,2),(28,client+4,4),(1216,65537,4),(1212,0,4),(1224,0,2),(1226,1,2),(1220,70000,4)]
for off,val,width in cases:
 prepare();put(packet+off,val,width);events.clear();assert request()==0xffffffff and not any(e in events for e in ('fopen','fwrite','rename')),(off,events)
for name in (b'../evil',b'savegame._A_',b'savegame._a_x',b'savegame._{_'):
 prepare();cpu.mem_write(packet+956,name+b'\0');events.clear();assert request()==0xffffffff and not any(e in events for e in ('fopen','fwrite','rename'))
# Read failure/missing map identity must not attempt any sidecar operation.
lockok=False;prepare();events.clear();assert request()==0xfffffffe and not any(e in events for e in ('fopen','fwrite','rename')); lockok=True
examineok=False;prepare();assert request()==0xfffffffe;examineok=True
# A changed map while its MD5 is being calculated is rejected at post-hash stat.
call('_probe_map',mapaddr);changed=False
def change_during_read(uc,pc,size,data):
 global changed
 if pc==symbols['_fread']:
  sp=uc.reg_read(R.UC_M68K_REG_A7);handle=get(sp+16)
  if handle in handles and handles[handle][0]==mapname and not changed:identity['tick']+=1;changed=True
cpu.hook_add(unicorn.UC_HOOK_CODE,change_during_read)
prepare();assert request()==0xfffffffe and changed
report=dict(fixture_sha256=hashlib.sha256((HERE/'worker_metadata_fixture.hunk').read_bytes()).hexdigest(),compiled_production_helpers=True,missing_sidecar_skips_map_hash=True,main_and_backup_IO_distinguished=True,presence_close_error_safe=True,present_corrupt_sidecar_still_validated=True,actual_map_md5_lazily_cached=True,stat_checked_each_request=True,post_hash_identity_race_rejected=True,changed_map_rejected=True,load_policy_transactional_candidate_only=True,request_name_bounds_cases=len(cases)+4,aligned_Examine_FileInfoBlock=True,missing_lock_examine_fail_safe=True,dos_stdio_mocked=True)
(HERE/'worker-metadata-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
