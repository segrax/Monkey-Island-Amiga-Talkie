"""Build isolated metadata-enabled NPC1 worker and CRT-free native client."""
from pathlib import Path
import hashlib,json,os,subprocess
HERE=Path(__file__).resolve().parent;PARENT=HERE.parent;TOOLS=Path('D:/Tools/amiga-dev')
env=dict(os.environ,VBCC=str(TOOLS/'targets/m68k-amigaos'),PATH=str(TOOLS/'bin')+os.pathsep+os.environ['PATH'])
args=[str(TOOLS/'bin/vc.exe'),'+'+str(PARENT/'kick13.cfg'),'-O2','-cpu=68000','-DNATIVE_ASM_LUT','-I'+str(HERE),'-I'+str(PARENT)]
sources=['native_server.c','native_pcm.c','native_lookup.c','native_map.c','native_policy.c','native_gain.c','ring_lut.c','lut_copy.s','native_metadata_store.c','native_md5.c','native_profile.c','md5_block.s']
subprocess.run(args+['-o','VoiceServer_PreparedOnly']+sources,cwd=HERE,env=env,check=True)
subprocess.run(args+['-c','-o','native_client.o','native_client.c'],cwd=HERE,env=env,check=True)
report=dict(worker_sha256=hashlib.sha256((HERE/'VoiceServer_PreparedOnly').read_bytes()).hexdigest(),worker_bytes=(HERE/'VoiceServer_PreparedOnly').stat().st_size,client_sha256=hashlib.sha256((HERE/'native_client.o').read_bytes()).hexdigest(),sources={n:hashlib.sha256((HERE/n).read_bytes()).hexdigest()for n in sources+['native_client.c','native_client.h','native_server.h','native_profile.h','prepared_bindings.h','pcm_bindings.h','metadata_bindings.h']},runtime_validation=False)
(HERE/'build-manifest.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items()if k!='sources'},indent=2))
