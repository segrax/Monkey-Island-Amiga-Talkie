"""Stage the current c28 prepared-audio package into a new private directory."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import argparse
import hashlib
import json
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KEYS = ('Monkey_Talkie', 'MonkeyTalkie', 'module.json', 'VoiceServer',
        'amiga-talkie.dat', 'native-voice.pcm', 'VoiceBoost', 'PreparedOnly')
EXPECTED = 'c28ffdccebc9d7df80e1923a773588dcadabe1d43d270168e1253ebe4ac5c8dd'


def pin(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    return {'bytes': path.stat().st_size, 'sha256': digest}


def stage(base, output):
    base, output = base.resolve(), output.resolve()
    build = (ROOT / 'build').resolve()
    if output == build or not output.is_relative_to(build) or output.exists():
        raise ValueError('Output must be a new directory beneath project build/')
    if output.is_relative_to(base) or base.is_relative_to(output):
        raise ValueError('Base and output must be separate directories')
    source = ENGINE_BUILD / 'module'
    sources = {key: base / key for key in KEYS}
    sources.update(Monkey_Talkie=source / 'Monkey_Talkie_Test',
                   MonkeyTalkie=source / 'loader-build/MonkeyTalkie',
                   **{'module.json': source / 'module.json'})
    metadata = json.loads(sources['module.json'].read_text())
    if metadata['sha256'] != EXPECTED or pin(sources['Monkey_Talkie'])['sha256'] != EXPECTED:
        raise ValueError('Current c28 module image/manifest mismatch')
    base_pins = json.loads((base / 'runtime-hashes.json').read_text())
    for key in KEYS[3:]:
        if pin(sources[key]) != base_pins[key]:
            raise ValueError('Base audio/profile hash mismatch: ' + key)
    for name in ('Rooms', 'S'):
        if not (base / name).is_dir():
            raise ValueError('Missing base directory: ' + name)
    for path in sources.values():
        if not path.is_file():
            raise ValueError('Missing source: ' + str(path))
    full = json.loads((base / 'slim-package-manifest.json').read_text())
    output.mkdir(parents=True, exist_ok=False)
    for name in ('Rooms', 'S'):
        shutil.copytree(base / name, output / name)
    for key, path in sources.items():
        shutil.copy2(path, output / key)
    pins = {key: pin(output / key) for key in KEYS}
    (output / 'runtime-hashes.json').write_text(json.dumps(pins, indent=2) + '\n')
    full['files'] = {str(path.relative_to(output)).replace('\\', '/'): pin(path)
                     for path in output.rglob('*') if path.is_file() and
                     (path.name in KEYS or path.relative_to(output).parts[0] in ('Rooms', 'S'))}
    full.update(awaiting_runtime_validation=True, candidate='stripe-branch-relax-c28')
    (output / 'slim-package-manifest.json').write_text(json.dumps(full, indent=2) + '\n')
    status = dict(status='STAGED_RUNTIME_PENDING', diagnostic_only=False,
                  production_source=EXPECTED, same_21472_audio_assets=True,
                  prepared_only=True, source_SOU_omitted=True, files=pins)
    (output / 'candidate-unit-status.json').write_text(json.dumps(status, indent=2) + '\n')
    return {'path': str(output), 'files': pins}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, default=ROOT / 'build/releases/c28-21472')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(args.base, args.output), indent=2))
