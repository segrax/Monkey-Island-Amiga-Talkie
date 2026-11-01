"""Build a new isolated playback-identical prepared-only native package."""
from pathlib import Path
import argparse,hashlib,json,struct,shutil,sys,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE.parent))
from build_pcm import map_references,voc_pcm,gain_table
PINS=json.loads((HERE/'package-pins.json').read_text())
def sha(path):
 with path.open('rb')as f:return hashlib.file_digest(f,'sha256').hexdigest()
def pinned(path,prefix):
 if path.stat().st_size!=PINS[prefix+'_bytes']or sha(path)!=PINS[prefix+'_sha256']:raise ValueError('Unexpected '+prefix+' asset: '+str(path))
def verify(archive_path,map_path,pcm_path):
 for p,n in ((archive_path,'source'),(map_path,'map'),(pcm_path,'npc')):pinned(p,n)
 archive,mapping,pcm=archive_path.read_bytes(),map_path.read_bytes(),pcm_path.read_bytes()
 archive_size,refs=map_references(mapping)
 if archive_size!=len(archive)or len(refs)!=PINS['clips']or struct.unpack_from('>I',mapping,12)[0]!=PINS['map_entries']:raise ValueError('Unexpected map refs/entry count')
 h=struct.unpack_from('>4sHH8I',pcm)
 if h!=(b'NPC1',1,128,22050,4,len(archive),len(mapping),len(refs),128,128+16*len(refs),len(pcm)):raise ValueError('Invalid NPC1 header')
 if pcm[40:72]!=hashlib.sha256(archive).digest()or pcm[72:104]!=hashlib.sha256(mapping).digest()or any(pcm[104:128]):raise ValueError('NPC1 bindings/reserved invalid')
 rows=[struct.unpack_from('>4I',pcm,128+16*i)for i in range(len(refs))]
 if [(a,b)for a,b,_,_ in rows]!=refs:raise ValueError('Incomplete/extra prepared clip refs')
 table=gain_table(PINS['gain']);at=128+16*len(refs);samples=0
 for off,head,pos,n in rows:
  expected=voc_pcm(archive,off,head).translate(table)
  if pos!=at or n!=len(expected)or pcm[pos:pos+n]!=expected:raise ValueError('Prepared PCM differs at source ref '+str((off,head)))
  at+=n;samples+=n
 if at!=len(pcm):raise ValueError('Trailing/gapped prepared PCM')
 return dict(all_map_refs_present=len(rows),all_prepared_pcm_bytes_exact=samples,gain=4,source_untouched=True)
def runtime_inputs(base):
 allowed={'Monkey_Talkie','MonkeyTalkie','module.json','VoiceServer','VoiceBoost','PreparedOnly','monster.sou','amiga-talkie.dat','native-voice.pcm','S','Rooms'}
 unexpected={p.name for p in base.iterdir()}-allowed
 if unexpected:raise ValueError('Unexpected base-system entries: '+repr(sorted(unexpected)))
 for name in ('Monkey_Talkie','MonkeyTalkie','module.json','Rooms','S'):
  if not(base/name).exists():raise ValueError('Missing runtime '+name)
 meta=json.loads((base/'module.json').read_text())
 if meta['sha256']!=sha(base/'Monkey_Talkie'):raise ValueError('Game/module manifest mismatch')
 if {p.name for p in (base/'Rooms').iterdir()}!=set(PINS['rooms']):raise ValueError('Unexpected native room files')
 for name,pin in PINS['rooms'].items():
  p=base/'Rooms'/name
  if not p.is_file()or p.stat().st_size!=pin['bytes']or sha(p)!=pin['sha256']:raise ValueError('Unexpected native room bytes: '+name)
 if {p.name for p in (base/'S').iterdir()}-{'startup-sequence','startup-sequence.normal'}:raise ValueError('Unexpected startup entries')
 if not(base/'S/startup-sequence').is_file():raise ValueError('Missing startup-sequence')
 for p in base.rglob('*'):
  if p.is_symlink()or getattr(p,'is_junction',lambda:False)():raise ValueError('Refusing linked runtime input')
 return ['Monkey_Talkie','MonkeyTalkie','module.json','Rooms','S']
def package(args):
 output=args.output.resolve()
 if not output.is_relative_to((ROOT/'build').resolve())or output.exists():raise ValueError('Output must be a new isolated build directory')
 worker=HERE/'VoiceServer_PreparedOnly';manifest=json.loads((HERE/'build-manifest.json').read_text())
 if sha(worker)!=manifest['worker_sha256']:raise ValueError('Unexpected worker image')
 for header in ('pcm_bindings.h','prepared_bindings.h','native_profile.h','metadata_bindings.h'):
  if manifest['sources'].get(header)!=sha(HERE/header):raise ValueError('Worker was not built against current '+header)
 h=(HERE/'pcm_bindings.h').read_text();prepared=(HERE/'prepared_bindings.h').read_text()
 for name,value in (('NPC_SOURCE_BYTES',PINS['source_bytes']),('NPC_MAP_BYTES',PINS['map_bytes'])):
  if not re.search(r'#define\s+'+name+r'\s+'+str(value)+r'UL\b',h):raise ValueError('Worker logical byte bound mismatch')
 for name,key in (('npc_source_sha','source_sha256'),('npc_map_sha','map_sha256')):
  m=re.search(name+r'\[32\]\s*=\s*\{([^}]+)\}',h)
  if not m or bytes(int(v.strip())for v in m[1].split(',')).hex()!=PINS[key]:raise ValueError('Worker SHA binding mismatch')
 for name,value in (('NPC_PREPARED_CLIPS',PINS['clips']),('NPC_PREPARED_BYTES',PINS['npc_bytes']),('NPC_PREPARED_GAIN',PINS['gain'])):
  if not re.search(r'#define\s+'+name+r'\s+'+str(value)+r'(?:UL)?\b',prepared):raise ValueError('Worker prepared profile mismatch')
 from build_metadata_bindings import generate
 if (HERE/'metadata_bindings.h').read_text()!=generate(args.map):raise ValueError('Worker precomputed MD5 differs from actual pinned map')
 proof=verify(args.archive,args.map,args.pcm)
 copy=runtime_inputs(args.base_system)if args.base_system else []
 output.mkdir(parents=True)
 for name in copy:
  src=args.base_system/name
  if src.is_dir():shutil.copytree(src,output/name)
  else:shutil.copy2(src,output/name)
 for src,name in ((args.map,'amiga-talkie.dat'),(args.pcm,'native-voice.pcm'),(worker,'VoiceServer')):shutil.copy2(src,output/name)
 (output/'PreparedOnly').write_bytes(b'NPC1\n');(output/'VoiceBoost').write_bytes(b'4\n')
 files={p.relative_to(output).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p))for p in output.rglob('*')if p.is_file()}
 if any(p.name.lower()=='monster.sou'for p in output.rglob('*')):raise AssertionError('SOU must never be staged')
 record=dict(profile='STRICT_PREPARED_ONLY_GAIN4',awaiting_runtime_validation=True,complete_runtime=bool(copy),source_archive_read_only=str(args.archive),source_archive_sha256=PINS['source_sha256'],proof=proof,files=files,omitted_source_bytes=PINS['source_bytes'],data_decoder='none; direct prepared PCM streaming')
 (output/'slim-package-manifest.json').write_text(json.dumps(record,indent=2)+'\n');print(json.dumps(dict(output=str(output),files=len(files),**proof)))
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--archive',type=Path,required=True);a.add_argument('--map',type=Path,default=ROOT/'data/prepared/21472/amiga-talkie.dat');a.add_argument('--pcm',type=Path,default=ROOT/'data/prepared/21472/native-voice.pcm');a.add_argument('--base-system',type=Path);a.add_argument('--output',type=Path,required=True);package(a.parse_args())
