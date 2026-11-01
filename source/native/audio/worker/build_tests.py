"""Build target-only metadata fixtures from the current production sources."""
from pathlib import Path
import os,subprocess,json,hashlib
P=Path(__file__).resolve().parent;TOOLS=Path('D:/Tools/amiga-dev');env=dict(os.environ,VBCC=str(TOOLS/'targets/m68k-amigaos'),PATH=str(TOOLS/'bin')+os.pathsep+os.environ['PATH'])
s=(P/'native_server.c').read_text();block=s[s.index('struct MapIdentity'):s.index('\nstatic void cancel_voice')]
fixture=(P/'worker_metadata_fixture.c').read_text();begin=fixture.index('struct MapIdentity');end=fixture.index('\nvoid probe_map')
(P/'worker_metadata_fixture.c').write_text(fixture[:begin]+block+fixture[end:])
vc=[str(TOOLS/'bin/vc.exe'),'+'+str(P.parent/'kick13.cfg'),'-O2','-cpu=68000','-I'+str(P),'-I'+str(P.parent),'-c']
subprocess.run(vc+['native_metadata_store.c','native_md5.c','native_policy.c','store_fixture.c','worker_metadata_fixture.c'],cwd=P,env=env,check=True)
subprocess.run([str(TOOLS/'bin/vasmm68k_mot.exe'),'-quiet','-Fhunk','-m68000','-o','store_mocks.o','store_mocks.s'],cwd=P,env=env,check=True)
subprocess.run([str(TOOLS/'bin/vasmm68k_mot.exe'),'-quiet','-Fhunk','-m68000','-o','md5_block.o','md5_block.s'],cwd=P,env=env,check=True)
for prefix in ('store_fixture','worker_metadata_fixture'):
 args=[str(TOOLS/'bin/vlink.exe'),'-Z','-bamigahunk','-Bstatic','-Cvbcc','-nostdlib','-M','-o',prefix+'.hunk','native_metadata_store.o','native_md5.o','native_policy.o',prefix+'.o','md5_block.o','store_mocks.o']
 result=subprocess.run(args,cwd=P,env=env,check=True,capture_output=True,text=True);(P/(prefix+'.map')).write_text(result.stdout)
report={'production_helper_source_sha256':hashlib.sha256(block.encode()).hexdigest(),'fixtures':{n:hashlib.sha256((P/(n+'.hunk')).read_bytes()).hexdigest()for n in ('store_fixture','worker_metadata_fixture')}}
(P/'fixture-build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
