"""Deploy only a stopped, runtime-validated local candidate, retaining rollback files."""
from pathlib import Path
import argparse, hashlib, json, shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = Path('D:/Games/ScummVM/LucasArts/MonkeyIsland/Monkey_Amiga_Ultimate_Talkie_WinUAE')
SYSTEM = PUBLIC / 'System_A500_Dedicated'
NAMES = ('Monkey_Talkie', 'MonkeyTalkie', 'module.json', 'VoiceServer',
         'amiga-talkie.dat', 'native-voice.pcm', 'VoiceBoost', 'PreparedOnly')

def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def deploy(stage, proof_path, backup):
    stage, backup = stage.resolve(), backup.resolve()
    if not stage.is_relative_to(ROOT/'build') or not backup.is_relative_to(ROOT/'build'):
        raise ValueError('Candidate and backup must be inside this workspace build')
    if backup.exists():
        raise ValueError('Backup must be a new directory')
    proof = json.loads(proof_path.read_text())
    if not proof['status'].startswith('PASS') or not proof['stopped'] or proof['instrumented']:
        raise ValueError('Requires stopped, uninstrumented successful runtime proof')
    hashes = {name: sha(stage/name) for name in NAMES}
    if proof['runtime_hashes'] != hashes or (stage/'monster.sou').exists():
        raise ValueError('Candidate differs from runtime proof or contains duplicate archive')
    if (stage/'PreparedOnly').read_bytes() != b'NPC1\n':
        raise ValueError('Missing strict-profile marker')
    for folder in ('Rooms', 'S'):
        left = {p.relative_to(stage/folder).as_posix(): sha(p) for p in (stage/folder).rglob('*') if p.is_file()}
        right = {p.relative_to(SYSTEM/folder).as_posix(): sha(p) for p in (SYSTEM/folder).rglob('*') if p.is_file()}
        if left != right:
            raise ValueError('Unexpected original data/startup change: '+folder)
    source = SYSTEM/'monster.sou'
    if not source.is_file() or sha(source) != '45119490a85c4b7588272501da527666c777492ead9fe3a6ce6e3c44bd50f046':
        raise ValueError('Installed archive differs from expected owned source')
    old_names = [name for name in (*NAMES, 'monster.sou') if (SYSTEM/name).is_file()]
    old = {name: sha(SYSTEM/name) for name in old_names}
    backup.mkdir(parents=True)
    for name in old_names:
        shutil.copy2(SYSTEM/name, backup/name)
        if sha(backup/name) != old[name]:
            raise ValueError('Backup verification failed: '+name)
    for name in NAMES:
        shutil.copy2(stage/name, SYSTEM/name)
        if sha(SYSTEM/name) != hashes[name]:
            raise ValueError('Installed verification failed: '+name)
    # Exact fixed file, only after the entire original archive has a verified backup.
    source.unlink()
    record = dict(installed=hashes, previous=old, backup=str(backup),
                  runtime_proof=str(proof_path.resolve()), duplicate_archive_omitted=True)
    (backup/'deployment.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps(record, indent=2))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--proof', type=Path, required=True)
    parser.add_argument('--backup', type=Path, required=True)
    args = parser.parse_args()
    deploy(args.stage, args.proof, args.backup)
