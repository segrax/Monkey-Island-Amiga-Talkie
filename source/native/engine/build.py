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


def build(output, candidate=False, stereo_mix=False, hybrid_mix=False, skip_fixture_tests=False, costume_cache=True, planar_cache=False, planar_chip_fallback=False, glyph_cache=False):
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

        cache_enabled=hybrid_mix and costume_cache
        if planar_cache and (not candidate or not cache_enabled):
            raise ValueError('The planar prototype requires --candidate --hybrid-mix and the costume cache')
        if glyph_cache and not (planar_cache and cache_enabled):
            raise ValueError('The glyph cache requires --planar-cache --hybrid-mix and the costume cache')
        if planar_chip_fallback and not planar_cache:
            raise ValueError('The planar Chip fallback requires --planar-cache')
        run(SOURCE / 'core/build_module.py', '--with-metadata', *(['--hybrid-mix'] if hybrid_mix else ['--stereo-mix'] if stereo_mix else []),
            *(['--costume-cache'] if cache_enabled else []), *(['--planar-cache'] if planar_cache else []),
            *(['--planar-chip-fallback'] if planar_chip_fallback else []), *(['--glyph-cache'] if glyph_cache else []))
        if hybrid_mix:
            run(PROJECT_ROOT / 'audio/test_boot_abi.py')
            for test in ('test_clock_lifecycle.py', 'test_clock_preemption.py', 'test_music_clock.py', 'test_hybrid_driver.py', 'test_driver_clock_scale.py', 'test_transport_ownership.py', 'test_idle_zero_cache.py', 'test_presence.py', 'test_hybrid_tables.py', 'test_hybrid_speech_unity.py', 'test_speech_packed.py', 'test_hybrid_speech_only_unity.py', 'test_zero_output.py', 'test_resampler_boundaries.py', 'test_resampler_runs.py', 'test_fused_span.py', 'test_fused_driver.py', 'test_projected_span.py', 'test_gain32_span.py', 'test_projected_driver.py', 'test_irq_registers.py', 'test_phase_driver.py', 'test_timeline_equivalence.py', 'test_write_dispatch.py', 'test_volume_fast.py', 'test_word_wrapper.py', 'test_quiet_restart.py', 'test_quiet_prime.py'):
                run(SOURCE / 'core' / test)
        if planar_cache:
            run(SOURCE / 'art/test_checksum.py')
            run(SOURCE / 'art/test_indices.py')
        run(SOURCE / 'scaling/generate.py')
        run(SOURCE / 'scaling/test_prefix_counts.py')
        core, scaling, module = output / 'core', output / 'scaling', output / 'module'
        if not cache_enabled:
            run(SOURCE / 'scaling/rebase.py', '--speech-dir', core, '--expected', digest(core / 'Monkey_Talkie_Test'),
                *(['--expected-patch-count', '62' if hybrid_mix else '60'] if stereo_mix or hybrid_mix else []),
                *(['--skip-fixture-tests'] if skip_fixture_tests else []))
        # A minimal graphics-only fixture tests the same kernels independently
        # of speech hooks and their extra HUNKs.
        original = PROJECT_ROOT / 'data/original/Monkey_Island'
        run(SOURCE / 'scaling/build_patch.py', '--source', original,
            '--expected', digest(original), '--output', scaling / 'Monkey_Scaled')
        run(SOURCE / 'scaling/test_clear_masks.py')
        run(SOURCE / 'scaling/test_short_packets.py')
        run(SOURCE / 'scaling/test_single_packets.py')
        run(SOURCE / 'scaling/test_long_opaque.py')
        if cache_enabled:
            run(SOURCE / 'scaling/generate.py', '--costume-cache')
            run(SOURCE / 'scaling/cache_patch.py')
        run(SOURCE / 'stripes/generate.py')
        run(SOURCE / 'stripes/test_stripe.py')
        module.mkdir()
        run(SOURCE / 'stripes/build_patch.py', '--source', scaling / 'Monkey_Talkie_Scaled',
            '--expected', digest(scaling / 'Monkey_Talkie_Scaled'), '--output', module / 'Monkey_Talkie_Test')
        run(SOURCE / 'stripes/write_manifest.py')
        if not skip_fixture_tests:
            run(SOURCE / 'stripes/test_linked.py')
        run(SOURCE / 'restoration/generate.py')
        run(SOURCE / 'restoration/test_kernel.py')
        run(SOURCE / 'restoration/patch.py')
        run(SOURCE / 'restoration/rle_generate.py')
        run(SOURCE / 'restoration/rle_test.py')
        run(SOURCE / 'restoration/rle_patch.py')
        run(SOURCE / 'io/generate.py')
        run(SOURCE / 'io/patch.py')
        run(SOURCE / 'io/test_reader.py')
        run(SOURCE / 'io/test_decode.py')
        run(SOURCE / 'geometry/generate.py')
        run(SOURCE / 'geometry/patch.py')
        run(SOURCE / 'geometry/test_counts.py')
        run(SOURCE / 'sprites/generate.py')
        run(SOURCE / 'sprites/patch.py')
        run(SOURCE / 'sprites/test_kernel.py')
        run(SOURCE / 'memory/generate.py')
        run(SOURCE / 'memory/patch.py')
        run(SOURCE / 'memory/test_fill.py')
        run(SOURCE / 'memory/test_copy.py')
        run(SOURCE / 'font/generate.py')
        run(SOURCE / 'font/patch.py')
        run(SOURCE / 'font/test_font.py')
        run(SOURCE / 'lookup/generate.py')
        run(SOURCE / 'lookup/patch.py')
        run(SOURCE / 'lookup/test_slot.py')
        run(SOURCE / 'mask/generate.py')
        run(SOURCE / 'mask/test_kernel.py')
        run(SOURCE / 'mask/test_flags.py')
        run(SOURCE / 'mask/patch.py')
        run(SOURCE / 'mask/test_linked.py')
        if glyph_cache:
            run(SOURCE / 'glyph/patch.py')
            for test in ('test_load_hook.py', 'test_glyph.py', 'test_scope.py', 'test_compare.py'):
                run(SOURCE / 'glyph' / test)
        if cache_enabled:
            run(SOURCE / 'scaling/test_cache.py')
            run(SOURCE / 'scaling/test_capacity.py')
            run(SOURCE / 'scaling/test_cache_extended.py')
            run(SOURCE / 'scaling/test_cache_directions.py')
        if planar_cache:
            run(SOURCE / 'art/test_decoder.py')
            run(SOURCE / 'art/test_game.py')
            run(SOURCE / 'art/test_scope.py')
            run(SOURCE / 'art/test_loop.py')
            run(SOURCE / 'art/test_payload_versions.py')
            run(SOURCE / 'art/test_prewarm.py')
            run(SOURCE / 'art/test_c2p.py')
        run(SOURCE / 'blitter/patch.py')
        run(SOURCE / 'blitter/test_stride.py')
        run(SOURCE / 'music_init/patch.py')
        run(SOURCE / 'music_init/test_patch.py')
        run(SOURCE / 'music_init/test_init_clear.py')
        run(PROJECT_ROOT / 'audio/build_loader.py', '--module-dir', module,
            '--output-dir', module / 'loader-build')
        if skip_fixture_tests:
            log.write('Fixture-dependent linked execution test omitted; original RAM fixture not supplied.\n')
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
    parser.add_argument('--without-costume-cache', action='store_true', help='Disable the optional bounded draw cache for comparisons')
    parser.add_argument('--planar-cache', action='store_true', help='Experimental optional immutable-art cache (requires --candidate --hybrid-mix)')
    parser.add_argument('--planar-chip-fallback', action='store_true', help='Allow only the optional planar payload to fall back to Chip RAM')
    parser.add_argument('--glyph-cache', action='store_true', help='Optional bounded prepared font cache (requires --planar-cache --hybrid-mix)')
    args = parser.parse_args()
    try:
        if (args.stereo_mix or args.hybrid_mix) and not args.candidate:
            parser.error('Mixing trials require --candidate')
        if args.stereo_mix and args.hybrid_mix:
            parser.error('Choose one mixing backend')
        build(args.output, args.candidate, args.stereo_mix, args.hybrid_mix, args.skip_fixture_tests, not args.without_costume_cache, args.planar_cache, args.planar_chip_fallback, args.glyph_cache)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(str(error), file=sys.stderr)
        print(f'Build log: {args.output / "build.log"}', file=sys.stderr)
        raise SystemExit(1)
