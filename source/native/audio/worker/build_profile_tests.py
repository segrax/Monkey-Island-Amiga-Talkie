"""Rebuild the exact profile/clip fixture from current production C."""
from pathlib import Path
import os,subprocess,hashlib,json
P=Path(__file__).resolve().parent;TOOLS=Path('D:/Tools/amiga-dev');env=dict(os.environ,VBCC=str(TOOLS/'targets/m68k-amigaos'),PATH=str(TOOLS/'bin')+os.pathsep+os.environ['PATH'])
s=(P/'native_server.c').read_text();block=s[s.index('static int next_clip'):s.index('\nstatic void refill')]
f=(P/'profile_fixture.c').read_text();a=f.index('static int next_clip');b=f.index('\nstruct NativePcm *probe_pcm');(P/'profile_fixture.c').write_text(f[:a]+block+f[b:])
subprocess.run([str(TOOLS/'bin/vc.exe'),'+'+str(P.parent/'kick13.cfg'),'-O2','-cpu=68000','-I'+str(P),'-I'+str(P.parent),'-c','native_profile.c','profile_fixture.c'],cwd=P,env=env,check=True)
subprocess.run([str(TOOLS/'bin/vasmm68k_mot.exe'),'-quiet','-Fhunk','-m68000','-o','profile_mocks.o','profile_mocks.s'],cwd=P,env=env,check=True)
a=[str(TOOLS/'bin/vlink.exe'),'-Z','-bamigahunk','-Bstatic','-Cvbcc','-nostdlib','-M','-o','profile_fixture.hunk','native_profile.o','profile_fixture.o','profile_mocks.o']
r=subprocess.run(a,cwd=P,env=env,check=True,capture_output=True,text=True);(P/'profile_fixture.map').write_text(r.stdout)
report=dict(next_clip_source_sha256=hashlib.sha256(block.encode()).hexdigest(),profile_source_sha256=hashlib.sha256((P/'native_profile.c').read_bytes()).hexdigest(),fixture_sha256=hashlib.sha256((P/'profile_fixture.hunk').read_bytes()).hexdigest());(P/'profile-fixture-build.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
