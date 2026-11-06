"""Portable lifecycle and streamed-PCM tests; no original game files required."""
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

DRIVER, BUILDER = map(str, map(Path.resolve, map(Path, sys.argv[1:])))
sys.argv[1:] = []


class BuilderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "Unicode café 日本語 with spaces"
        self.root.mkdir()
        self.stage = self.root / "game.building"
        self.output = self.root / "game"

    def run_driver(self, mode, success=True):
        result = subprocess.run([DRIVER, mode], cwd=self.root, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 0 if success else 1, result.stderr)
        return result

    def test_failure_cleanup_and_retry(self):
        self.run_driver("fail", False)
        self.assertFalse(self.stage.exists())
        self.assertFalse(self.output.exists())
        self.run_driver("publish")
        self.assertEqual((self.output / "partial").read_bytes(), b"\1\2\3")
        self.assertFalse(self.stage.exists())
        self.run_driver("publish", False)
        self.assertEqual((self.output / "partial").read_bytes(), b"\1\2\3")

    def test_keep_failed_build(self):
        self.run_driver("keep", False)
        self.assertTrue((self.stage / "partial").is_file())
        self.run_driver("publish", False)
        self.assertTrue((self.stage / "partial").is_file())

    def test_output_appears_during_build(self):
        self.run_driver("collision", False)
        self.assertEqual((self.output / "sentinel").read_bytes(), b"*")
        self.assertFalse(self.stage.exists())

    def test_malformed_staging_path(self):
        self.stage.write_text("unrelated file")
        self.run_driver("publish", False)
        self.assertEqual(self.stage.read_text(), "unrelated file")

    def test_competing_and_interrupted_builds(self):
        child = subprocess.Popen([DRIVER, "hold"], cwd=self.root,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            self.assertEqual(child.stdout.readline().strip(), b"ready")
            self.run_driver("publish", False)
            self.assertTrue((self.stage / "partial").exists())
        finally:
            child.kill()
            child.communicate(timeout=5)
        self.assertFalse(self.output.exists())
        # Forced termination cannot run C++ destructors. Preserve the stale stage
        # and reject it until the user explicitly removes it.
        result = self.run_driver("publish", False)
        self.assertIn(b"interrupted", result.stderr)
        shutil.rmtree(self.stage)
        self.run_driver("publish")

    def fixture(self):
        archive = bytearray(b"prefix")
        refs, samples = [], []
        for data_offset, pcm in [(26, bytes(range(256)) * 300), (40, b"\0\x80\xff\x40")]:
            refs.append([len(archive), 8])
            header = b"Creative Voice File\x1a" + struct.pack("<HHH", data_offset, 0x114, 0x111F)
            header += bytes(data_offset - len(header))
            size = len(pcm) + 2
            archive += b"VCTL\0\0\0\x08" + header
            archive += b"\1" + size.to_bytes(3, "little") + b"\xd3\0" + pcm + b"\0"
            samples.append(pcm)
        dialogue = b"synthetic dialogue map"
        start = 128 + 16 * len(refs)
        header = bytearray(128)
        header[:8] = b"NPC1\0\1\0\x80"
        lengths = [len(pcm) for pcm in samples]
        struct.pack_into(">8I", header, 8, 22050, 4, len(archive), len(dialogue),
                         len(refs), 128, start, start + sum(lengths))
        header[40:72] = hashlib.sha256(archive).digest()
        header[72:104] = hashlib.sha256(dialogue).digest()
        rows, converted = bytearray(), bytearray()
        for ref, pcm in zip(refs, samples):
            rows += struct.pack(">4I", *ref, start + len(converted), len(pcm))
            for value in pcm:
                signed = value - 128
                limit = 128 if signed < 0 else 127
                gain = abs(signed) * 4 * limit // (limit + 3 * abs(signed))
                converted.append((-gain if signed < 0 else gain) & 255)
        expected = header + rows + converted
        (self.root / "archive.sou").write_bytes(archive)
        (self.root / "spec.json").write_text(json.dumps({
            "map": dialogue.hex(), "refs": refs,
            "expected": hashlib.sha256(expected).hexdigest()}))
        return archive, expected

    def test_streamed_pcm_exact_bytes(self):
        _, expected = self.fixture()
        self.run_driver("pcm")
        self.assertEqual((self.root / "voice.pcm").read_bytes(), expected)

    def test_truncated_and_malformed_speech(self):
        archive, _ = self.fixture()
        for bad in [archive[:-1], b"invalid", archive[:42],
                    archive[:6] + b"FAIL" + archive[10:], archive[:-1] + b"\1",
                    archive[:38] + b"\0" + archive[39:]]:
            with self.subTest(length=len(bad)):
                (self.root / "archive.sou").write_bytes(bad)
                (self.root / "voice.pcm").unlink(missing_ok=True)
                self.run_driver("pcm", False)

    def test_unsupported_input_diagnostic(self):
        source = self.root / "inputs"
        source.mkdir()
        invalid = b"unsupported room data"
        (source / "000.LFL").write_bytes(invalid)
        result = subprocess.run([
            BUILDER, "--amiga", str(source), "--sou", str(source / "archive.sou"),
            "--engine", str(source / "engine"), "--output", str(self.output)],
            capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertIn(hashlib.sha256(invalid).hexdigest().encode(), result.stderr)
        self.assertIn(b"Expected SHA-256:", result.stderr)
        self.assertIn(b"Supported speech profiles:", result.stderr)
        self.assertIn(b"README.md#what-you-need", result.stderr)
        self.assertFalse(self.stage.exists())

    def test_cli_and_malformed_input_directory(self):
        args = [BUILDER, "--amiga", str(self.root / "missing"), "--sou", "missing.sou",
                "--engine", "missing.engine", "--output", str(self.output), "--keep-failed-build"]
        result = subprocess.run(args, capture_output=True, timeout=15)
        self.assertEqual(result.returncode, 1)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.stage.exists())
        result = subprocess.run([BUILDER, "--help"], capture_output=True, timeout=15)
        self.assertIn(b"--keep-failed-build", result.stdout)


if __name__ == "__main__":
    unittest.main()
