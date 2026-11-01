"""Actual68000 prepared-only profile/next-clip tests; stdio is mocked."""
from pathlib import Path
HERE=Path(__file__).resolve().parent
src=(HERE/'test_store_native.py').read_text().split("ctx=call('_probe_md5')")[0].replace('store_fixture.hunk','profile_fixture.hunk').replace('store_fixture.map','profile_fixture.map')
exec(compile(src,str(HERE/'test_store_native.py'),'exec'))
pins=json.loads((HERE/'package-pins.json').read_text());clips=pins['clips'];npcbytes=pins['npc_bytes']
fs.clear();checks=[];io_error=False;seek_error=False;tell_error=False;select_ok=True;voc_calls=0;messages=[]
def extra(uc,pc,size,data):
 global voc_calls
 sp=uc.reg_read(R.UC_M68K_REG_A7);a=lambda i:get(sp+4+4*i)
 if pc==symbols['_fread']:put(a(3)+24,16 if io_error else 0)
 if pc==symbols['_fseek']and seek_error:uc.reg_write(R.UC_M68K_REG_D0,0xffffffff)
 if pc==symbols['_ftell']and tell_error:uc.reg_write(R.UC_M68K_REG_D0,0xffffffff)
 if pc==symbols['_puts']:messages.append(text(a(0)));uc.reg_write(R.UC_M68K_REG_D0,0)
 if pc==symbols['_native_pcm_select']:
  if select_ok:put(a(3),100)
  uc.reg_write(R.UC_M68K_REG_D0,int(select_ok))
 if pc==symbols['_native_voc_open']:
  voc_calls+=1;assert a(0)!=0;put(a(3),100);put(a(4),22050,2);uc.reg_write(R.UC_M68K_REG_D0,1)
cpu.hook_add(unicorn.UC_HOOK_CODE,extra)
assert call('_native_profile_mode')==0;checks.append('missingmarker fullfallback')
for raw in (b'NPC1\n',b'NPC1\r\n'):
 fs[b'PreparedOnly']=raw;assert call('_native_profile_mode')==1
checks.append('explicit LF/CRLF marker')
for raw in (b'',b'NPC1',b'NPC2\n',b'NPC1\nextra',b'NPC1\0',b'x'*100):
 fs[b'PreparedOnly']=raw;assert call('_native_profile_mode')==0xffffffff
checks.append('six malformedmarkers reject')
fs.pop(b'PreparedOnly');open_error[b'PreparedOnly']=5;assert call('_native_profile_mode')==0xffffffff;open_error.clear()
fs[b'PreparedOnly']=b'NPC1\n';io_error=True;assert call('_native_profile_mode')==0xffffffff;io_error=False
close_error.add(b'PreparedOnly');assert call('_native_profile_mode')==0xffffffff;close_error.clear();checks.append('marker IO/read/close failures')
gain=0x602000
assert call('_native_profile_gain',gain)==1 and get(gain)==4
for raw in (b'4',b'4\n',b'4\r\n'):
 fs[b'VoiceBoost']=raw;assert call('_native_profile_gain',gain)==1 and get(gain)==4
for raw in (b'2\n',b'8\n',b'9\n',b'',b'4 junk',b'4\0'):
 fs[b'VoiceBoost']=raw;assert call('_native_profile_gain',gain)==0
fs.pop(b'VoiceBoost');open_error[b'VoiceBoost']=5;assert call('_native_profile_gain',gain)==0;open_error.clear();checks.append('strict gain4 only, missing default4, invalid and IO reject')
path=0x602100;out=0x602200;size=0x602300;cpu.mem_write(path,b'monster.sou\0')
events.clear();put(out,0xdeadbeef);assert call('_native_profile_archive',1,path,out,size)==1
assert get(out)==0 and get(size)==198054609 and not events;checks.append('strict archive NULL+logicalbound, no fopen/seek/read')
fs[b'monster.sou']=b'x'*1234;events.clear();assert call('_native_profile_archive',0,path,out,size)==1 and get(out)!=0 and get(size)==1234
assert 'fopen'in events and 'fclose'not in events;checks.append('full fallback real source open retained')
for which in ('seek','tell'):
 seek_error=which=='seek';tell_error=which=='tell';events.clear();assert call('_native_profile_archive',0,path,out,size)==0 and get(out)==0 and get(size)==0 and 'fclose'in events
seek_error=tell_error=False
fs.pop(b'monster.sou');assert call('_native_profile_archive',0,path,out,size)==0;checks.append('full source missing/seek/tell failure closes safely')
p=call('_probe_pcm');put(p,0x200100);put(p+8,clips);put(p+12,npcbytes)
assert call('_native_profile_ready',1,1,4,p)==1
for status,g,ptr in ((0,4,p),(2,4,p),(0xffffffff,4,p),(1,2,p),(1,8,p),(1,4,0)):
 assert call('_native_profile_ready',1,status,g,ptr)==0
for off,value in ((8,clips-1),(12,npcbytes-1)):
 old=get(p+off);put(p+off,value);assert call('_native_profile_ready',1,1,4,p)==0;put(p+off,old)
checks.append('strict prepared valid status/count/filebytes/gain/pointer requirements')
select_ok=True;before=voc_calls;assert call('_probe_next',1,1,0)==1 and voc_calls==before
select_ok=False;messages.clear();assert call('_probe_next',1,1,0)==0xffffffff and voc_calls==before and b'mapped clip'in messages[-1]
messages.clear();assert call('_probe_next',1,0,0)==0xffffffff and voc_calls==before and b'no SOU fallback'in messages[-1]
select_ok=True;assert call('_probe_next',0,0,0x200100)==1 and voc_calls==before+1
checks.append('strict clip selection uses no archive, missing clip/buffer errors, full VOC fallback retained')
report=dict(fixture_sha256=hashlib.sha256((HERE/'profile_fixture.hunk').read_bytes()).hexdigest(),actual_vbcc_O2_68000=True,checks=checks,stdio_codec_calls_mocked=True,actual_amiga_os=False)
(HERE/'profile-native-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
