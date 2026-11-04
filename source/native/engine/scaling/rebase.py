"""Apply generated sprite-scaling kernels to an explicitly selected seven-hunk core."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--speech-dir', required=True, type=Path)
    parser.add_argument('--expected', required=True)
    parser.add_argument('--expected-patch-count', type=int, default=57)
    parser.add_argument('--skip-fixture-tests', action='store_true')
    args = parser.parse_args()
    image, manifest = args.speech_dir / 'Monkey_Talkie_Test', args.speech_dir / 'module.json'
    metadata = json.loads(manifest.read_text())
    if sha(image) != args.expected or metadata['sha256'] != args.expected:
        raise ValueError('Speech image/manifest differs from approved freeze')
    if len(metadata['patches']) != args.expected_patch_count:
        raise ValueError('Source hook count differs from the explicitly selected core')
    from build_patch import read
    if read(image).hunks[0]['table_size'] != 7:
        raise ValueError('Renderer requires a seven-hunk core, not an already patched image')
    for name in ('scaled_kernels.bin', 'scale_prefix.bin', 'generation.json'):
        if not (BUILD / name).is_file():
            raise ValueError('Missing generated scaling input: ' + name)
    source = {'source_image': str(image.resolve()), 'source_manifest': str(manifest.resolve()),
              'source_sha256': args.expected, 'kernel_sha256': sha(BUILD / 'scaled_kernels.bin'),
              'prefix_sha256': sha(BUILD / 'scale_prefix.bin'), 'runtime_validation': False}
    if (BUILD / 'rebase-input.json').exists():
        raise ValueError('Refusing to overwrite an existing combined build')
    (BUILD / 'rebase-input.json').write_text(json.dumps(source, indent=2) + '\n')
    commands = [
        ['build_patch.py', '--source', str(image), '--expected', args.expected,
         '--output', str(BUILD / 'Monkey_Talkie_Scaled')],
        ['write_manifest.py', '--base', str(manifest), '--patch', str(BUILD / 'Monkey_Talkie_Scaled.json'),
         '--output', str(BUILD / 'module.json')],
        ['test_static.py'], ['test_prefix_counts.py'], ['test_production.py']]
    for command in commands:
        if args.skip_fixture_tests and command[0] == 'test_production.py':
            continue
        subprocess.run([sys.executable, str(HERE / command[0]), *command[1:]], check=True)
    result = {'status': 'REBASED_STATIC_PRODUCTION_KERNEL_PASS_RUNTIME_PENDING', **source,
              'combined_sha256': sha(BUILD / 'Monkey_Talkie_Scaled'),
              'manifest_sha256': sha(BUILD / 'module.json'),
              'preserved_native_patch_count': len(metadata['patches']),
              'renderer_changes': 'Only two existing scaled kernel entries plus new H7/H8 payloads.',
              'loader_built': False}
    if args.skip_fixture_tests:
        result.update(status='REBASED_STATIC_PASS_PRODUCTION_FIXTURE_TEST_OMITTED', production_fixture_test=False)
    (BUILD / 'COMBINED-VALIDATION.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
