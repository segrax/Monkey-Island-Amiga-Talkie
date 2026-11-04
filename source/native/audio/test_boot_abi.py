from pathlib import Path
import sys,json,struct,subprocess
S=Path(__file__).resolve().parents[1];sys.path.insert(0,str(S/'engine'));from paths import engine_build;OUTPUT=engine_build();B=OUTPUT/'boot-proof';B.mkdir(parents=True,exist_ok=True);sys.path.insert(0,str(S/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R
REG=[getattr(R,'UC_M68K_REG_'+n) for n in ('D0','D1','D2','D3','D4','D5','D6','D7','A0','A1','A2','A3','A4','A5','A6','A7')]
def cpu(model):
 c=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN);c.ctl_set_cpu_model(model);c.mem_map(0,0x1000000);return c
subprocess.run(['D:/Tools/amiga-dev/bin/vasmm68k_mot.exe','-quiet','-m68000','-Fbin','-o',str(B/'call_game.bin'),str(S/'audio/call_game.s')],check=True)
call=(B/'call_game.bin').read_bytes();assert bytes.fromhex('41fa') not in call
cases=0
for model in (R.UC_CPU_M68K_M68000,R.UC_CPU_M68K_M68020,R.UC_CPU_M68K_M68030):
 c=cpu(model);c.mem_write(0x100000,call)
 for text in (b'\n',b'28\n',b'32767\n'):
  for ccr in range(32):
   c.mem_write(0x200000,bytes.fromhex('70004e75'));c.mem_write(0x300000,text+b'\0');c.mem_write(0x900000,struct.pack('>I',0xa00000));c.reg_write(R.UC_M68K_REG_SR,ccr)
   initial=[0x12340000+n for n in range(16)];initial[0]=len(text);initial[8]=0x300000;initial[9]=0x200000;initial[-1]=0x900000
   for r,v in zip(REG,initial):c.reg_write(r,v)
   hit=[]
   def hook(uc,pc,n,_):
    if pc==0x200000:hit.append((uc.reg_read(REG[0]),uc.reg_read(REG[8]),uc.reg_read(REG[9])))
   h=c.hook_add(unicorn.UC_HOOK_CODE,hook);c.emu_start(0x100000,0xa00000,count=100);c.hook_del(h)
   assert hit==[(len(text),0x300000,0x200000)]
   assert [c.reg_read(r) for r in REG[2:8]+REG[10:15]]==initial[2:8]+initial[10:15]
   cases+=1
r=HunkReader();assert r.read_file(str(OUTPUT/'core/Monkey_Talkie_Test'))==0 and r.build_segments();m=json.loads((OUTPUT/'core/module.json').read_text());bases=[0x100000+n*0x40000 for n in range(8)]
c=cpu(R.UC_CPU_M68K_M68000);section=0
for h in r.hunks:
 section=h.get('hunk_no',section)
 if 'data' in h:c.mem_write(bases[section],h['data'])
 if h['type_name']=='HUNK_ABSRELOC32':
  for target,offsets in h['reloc'].items():
   for off in offsets:
    a=bases[section]+off;c.mem_write(a,struct.pack('>I',int.from_bytes(c.mem_read(a,4),'big')+bases[target]))
def address(name):
 e=m['exports'][name];return bases[e['hunk']]+e['offset']
control=address('_nv_control');entry=address('_nv_driver_start');g=bases[2]
for flags in (0,1,3,17,19):
 c.mem_write(control+16,struct.pack('>II',g,flags));c.mem_write(g+0x5d29,b'\x77\xa5\x5a\x66');c.reg_write(R.UC_M68K_REG_A7,0x900000);c.mem_write(0x900000,struct.pack('>I',0xa00000))
 def stop(uc,pc,n,_):
  if pc==entry+100:uc.emu_stop()
  elif pc==entry+28:uc.reg_write(R.UC_M68K_REG_PC,pc+6)
 h=c.hook_add(unicorn.UC_HOOK_CODE,stop);c.emu_start(entry,0xa00000,count=1000);c.hook_del(h)
 assert bytes(c.mem_read(g+0x5d29,4))==(b'\x77\x01\x5a\x66' if flags==17 else b'\x77\xa5\x5a\x66'),(flags,bytes(c.mem_read(g+0x5d29,4)).hex())
 cases+=1
report={'PASS':True,'call_ABI_cases':cases-5,'startup_cases':5,'models':['68000','68020','68030'],'all32CCR_call_arguments':True,'default_newline_length1':True,'debug_byte_only_adjacent_fastmode_preserved':True,'disabled_and_running_unchanged':True}
(B/'boot-validation.json').write_text(json.dumps(report,indent=2)+'\n');print(report)
