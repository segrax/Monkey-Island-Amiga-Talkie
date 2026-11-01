"""Compare complete target Update calls, excluding OS/I/O, C versus assembly block."""
from pathlib import Path
import hashlib,json,random
HERE=Path(__file__).resolve().parent;BASE=HERE.parent/'save-metadata-worker-preflight'
def model(folder):
 s=(folder/'test_store_native.py').read_text().split("ctx=call('_probe_md5')")[0]
 env={'__file__':str(folder/'test_store_native.py')};exec(compile(s,str(folder/'test_store_native.py'),'exec'),env)
 return env
rng=random.Random(1321);rows=[]
for folder in (BASE,HERE):
 rng=random.Random(1321)  # Identical bytes for both target implementations.
 e=model(folder);cpu=e['cpu'];ctx=e['call']('_probe_md5');active=[False];count=[0]
 def tick(uc,pc,size,data):
  if active[0]:count[0]+=1
 cpu.hook_add(e['unicorn'].UC_HOOK_CODE,tick)
 cases=[]
 for n in (64,1024,4096,65536):
  data=rng.randbytes(n);cpu.mem_write(0x600000,data);e['call']('_nv_md5_init',ctx);count[0]=0;active[0]=True;e['call']('_nv_md5_update',ctx,0x600000,n);active[0]=False;instructions=count[0]
  e['call']('_nv_md5_finish',ctx,0x601000)
  assert bytes(cpu.mem_read(0x601000,16))==hashlib.md5(data).digest()
  cases.append(dict(bytes=n,update_instructions=instructions,instructions_per_byte=instructions/n))
 rows.append(dict(model='C'if folder==BASE else'ASM',fixture_sha256=hashlib.sha256((folder/'store_fixture.hunk').read_bytes()).hexdigest(),cases=cases))
report=dict(compiled_68000_actual_instructions=True,not_cycle_counts=True,amiga_os_io_and_dma_excluded=True,same_input_bytes=True,scope='complete nv_md5_update with full64-byte blocks; no mocked memcpy is executed in these cases',models=rows,ratios=[dict(bytes=c['bytes'],instruction_reduction_percent=(1-a['update_instructions']/c['update_instructions'])*100)for c,a in zip(rows[0]['cases'],rows[1]['cases'])])
(HERE/'md5-instruction-profile.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))
