"""Build the current engine from its components into a fresh output directory."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

sys.pycache_prefix = str(Path(__file__).resolve().parents[1] / "build/python-cache")

from paths import PROJECT_ROOT

SOURCE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(output, candidate=False, stereo_mix=False, hybrid_mix=False, skip_fixture_tests=False):
    output = output.resolve()
    if not output.is_relative_to(PROJECT_ROOT / 'build') or output == PROJECT_ROOT / 'build' or output.exists():
        raise ValueError('Choose a new output directory beneath project build/')
    output.mkdir(parents=True)
    env = dict(os.environ, MONKEY_ENGINE_BUILD=str(output))
    with (output / 'build.log').open('w', encoding='utf-8') as log:
        def run(script, *arguments):
            command = [sys.executable, str(script), *map(str, arguments)]
            log.write(' '.join(command) + '\n'); log.flush()
            subprocess.run(command, env=env, cwd=PROJECT_ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)

        run(SOURCE / 'core/build_module.py', '--with-metadata', *(['--hybrid-mix'] if hybrid_mix else ['--stereo-mix'] if stereo_mix else []))
        if hybrid_mix:
            for test in ('test_clock_lifecycle.py', 'test_clock_preemption.py', 'test_hybrid_driver.py', 'test_hybrid_tables.py'):
                run(SOURCE / 'core' / test)
        run(SOURCE / 'scaling/generate.py')
        core, scaling, module = output / 'core', output / 'scaling', output / 'module'
        run(SOURCE / 'scaling/rebase.py', '--speech-dir', core, '--expected', digest(core / 'Monkey_Talkie_Test'),
            *(['--expected-patch-count', '60'] if stereo_mix or hybrid_mix else []),
            *(['--skip-fixture-tests'] if skip_fixture_tests else []))
        # A minimal graphics-only fixture tests the same kernels independently
        # of speech hooks and their extra HUNKs.
        original = PROJECT_ROOT / 'data/original/Monkey_Island'
        run(SOURCE / 'scaling/build_patch.py', '--source', original,
            '--expected', digest(original), '--output', scaling / 'Monkey_Scaled')
        run(SOURCE / 'stripes/generate.py')
        module.mkdir()
        run(SOURCE / 'stripes/build_patch.py', '--source', scaling / 'Monkey_Talkie_Scaled',
            '--expected', digest(scaling / 'Monkey_Talkie_Scaled'), '--output', module / 'Monkey_Talkie_Test')
        run(SOURCE / 'stripes/write_manifest.py')
        run(PROJECT_ROOT / 'audio/build_loader.py', '--module-dir', module,
            '--output-dir', module / 'loader-build')
        if skip_fixture_tests:
            log.write('Fixture-dependent linked execution test omitted; original RAM fixture not supplied.\n')
        else:
            run(SOURCE / 'stripes/test_linked.py')
    pins = {} if candidate else json.loads((PROJECT_ROOT / 'build/releases/c28-21472/deployment-release.json').read_text())['installed']
    results = {name: digest(path) for name, path in {
        'Monkey_Talkie': module / 'Monkey_Talkie_Test',
        'MonkeyTalkie': module / 'loader-build/MonkeyTalkie',
        'module.json': module / 'module.json',
    }.items()}
    if not candidate and any(value != pins[name] for name, value in results.items()):
        raise ValueError('Rebuilt engine differs from the frozen current release: ' + repr(results))
    (output / 'verification.json').write_text(json.dumps(results, indent=2) + '\n')
    if candidate:
        if skip_fixture_tests:
            print('PASS: candidate built; static/patch checks passed; owned-fixture execution tests omitted')
        else:
            print('PASS: candidate built and linked checks passed; not a validated release')
    else:
        print('PASS: engine, module manifest and loader match current release exactly')
    print(f'Outputs: {output}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--candidate', action='store_true',
                        help='Build an experimental module without requiring current-release hashes')
    parser.add_argument('--stereo-mix', action='store_true', help='Experimental continuous stereo mixing (requires --candidate)')
    parser.add_argument('--hybrid-mix', action='store_true', help='Two native hardware voices and two mixed with centered speech')
    parser.add_argument('--skip-fixture-tests', action='store_true', help='Omit the linked execution test when the owned RAM fixture is unavailable')
    args = parser.parse_args()
    try:
        if (args.stereo_mix or args.hybrid_mix) and not args.candidate:
            parser.error('Mixing trials require --candidate')
        if args.stereo_mix and args.hybrid_mix:
            parser.error('Choose one mixing backend')
        build(args.output, args.candidate, args.stereo_mix, args.hybrid_mix, args.skip_fixture_tests)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        print(f'Build log: {args.output / "build.log"}', file=sys.stderr)
        raise SystemExit(1)
