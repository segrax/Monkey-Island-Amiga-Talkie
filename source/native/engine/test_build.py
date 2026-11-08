"""Check build option validation without the native toolchain or game inputs."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import build


class StopBeforeCompilation(Exception):
    """Stop the pipeline after observing its first compiler command."""


class BuildOptionsTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.output = self.root / 'build' / 'candidate'
        root_patch = patch.object(build, 'PROJECT_ROOT', self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def test_invalid_options_leave_no_output_directory(self):
        cases = (
            ({'stereo_mix': True}, 'Mixing trials require --candidate'),
            ({'hybrid_mix': True}, 'Mixing trials require --candidate'),
            ({'candidate': True, 'stereo_mix': True, 'hybrid_mix': True},
             'Choose one mixing backend'),
            ({'candidate': True, 'planar_cache': True},
             'The planar prototype requires'),
            ({'candidate': True, 'hybrid_mix': True, 'planar_cache': True,
              'costume_cache': False}, 'The planar prototype requires'),
            ({'candidate': True, 'hybrid_mix': True, 'glyph_cache': True},
             'The glyph cache requires'),
            ({'candidate': True, 'planar_chip_fallback': True},
             'The planar Chip fallback requires'),
        )
        with patch.object(build.subprocess, 'run') as run:
            for options, message in cases:
                with self.subTest(options=options):
                    with self.assertRaisesRegex(ValueError, message):
                        build.build(self.output, **options)
                    self.assertFalse(self.output.exists())
            run.assert_not_called()

    def test_module_flags_and_build_environment(self):
        cases = (
            ({}, ['--with-metadata']),
            ({'stereo_mix': True}, ['--with-metadata', '--stereo-mix']),
            ({'hybrid_mix': True},
             ['--with-metadata', '--hybrid-mix', '--costume-cache']),
            ({'hybrid_mix': True, 'costume_cache': False},
             ['--with-metadata', '--hybrid-mix']),
            ({'hybrid_mix': True, 'planar_cache': True,
              'planar_chip_fallback': True, 'glyph_cache': True},
             ['--with-metadata', '--hybrid-mix', '--costume-cache',
              '--planar-cache', '--planar-chip-fallback', '--glyph-cache']),
        )
        for index, (options, flags) in enumerate(cases):
            with self.subTest(options=options):
                output = self.output / str(index)
                with patch.object(build.subprocess, 'run',
                                  side_effect=StopBeforeCompilation) as run:
                    with self.assertRaises(StopBeforeCompilation):
                        build.build(output, candidate=True, **options)
                command = run.call_args.args[0]
                self.assertEqual(command[:2], [
                    build.sys.executable,
                    str(build.SOURCE / 'core/build_module.py'),
                ])
                self.assertEqual(command[2:], flags)
                self.assertEqual(run.call_args.kwargs['env']['MONKEY_ENGINE_BUILD'],
                                 str(output))
                self.assertEqual(run.call_args.kwargs['cwd'], self.root)
                self.assertTrue(run.call_args.kwargs['check'])
                self.assertIn('--with-metadata', (output / 'build.log').read_text())


if __name__ == '__main__':
    unittest.main()
