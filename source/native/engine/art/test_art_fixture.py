"""Exercise the shared fixture with synthetic HUNK code and real 68000 emulation."""

import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from art_fixture import (
    ARENA,
    INDEX,
    PRIMARY,
    R,
    TABLE,
    ArtEnvironment,
    Fixture,
    load_environment,
    synthetic_artifact,
    u32,
)


def write_candidate(directory):
    """Write three hunks, real relocations, RTS stubs and two admission stores."""

    def words(*values):
        return struct.pack(">" + len(values) * "I", *values)

    code = bytearray(bytes.fromhex("4e75") * (0x18000 // 2))
    struct.pack_into(">I", code, 4, 0x10)
    # MOVE.W #1,abs.l followed by RTS. Both destination operands are relocated.
    code[0x100:0x10A] = bytes.fromhex("33fc0001") + words(0x150) + bytes.fromhex("4e75")
    code[0x120:0x12A] = bytes.fromhex("33fc0001") + words(0x200) + bytes.fromhex("4e75")
    data = words(1011, 0, 3, 0, 2, len(code) // 4, 1, 0x8000 // 4)
    data += words(1001, len(code) // 4) + code
    data += words(1004, 3, 2, 4, 0x104, 0x124, 0, 1010)
    data += words(1002, 1, 0, 1010) + words(1003, 0x8000 // 4, 1010)
    exports = {
        "_nv_control": dict(hunk=2, offset=0),
        "_nv_art": dict(hunk=2, offset=0x100),
        "_nv_art_decode_ready": dict(hunk=2, offset=0x200),
        "_nv_art_game_start": dict(hunk=0, offset=0),
        "_nv_art_game_object": dict(hunk=0, offset=0x100),
        "_nv_art_game_bind": dict(hunk=0, offset=0x120),
    }
    for index, name in enumerate(
        (
            "_nv_costume_alloc",
            "_nv_art_alloc",
            "_nv_art_alloc_any",
            "_nv_art_free",
            "_nv_art_file_open",
            "_nv_art_file_close",
            "_nv_art_read_at",
        )
    ):
        exports[name] = dict(hunk=0, offset=0x1000 + index * 2)
    candidate = directory / "Monkey_Talkie_Test"
    candidate.write_bytes(data)
    (directory / "module.json").write_text(
        json.dumps(
            dict(
                sha256=hashlib.sha256(data).hexdigest(),
                exports=exports,
            )
        )
    )
    return candidate


class ArtFixtureTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.candidate = write_candidate(self.directory)
        self.env = ArtEnvironment(self.candidate)

    def test_import_does_not_load_candidate_or_parse_arguments(self):
        script = (
            "import sys; "
            f"sys.path.insert(0, {str(Path(__file__).resolve().parent)!r}); "
            "import art_fixture"
        )
        result = subprocess.run(
            [sys.executable, "-c", script, "--unrelated-option"],
            cwd=self.directory,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_cli_selects_explicit_and_default_candidates(self):
        with patch("art_fixture.ArtEnvironment") as loader:
            load_environment(["--candidate", str(self.candidate)])
            loader.assert_called_once_with(self.candidate)
        with patch("art_fixture.ArtEnvironment") as loader:
            with patch("art_fixture.engine_build", return_value=self.directory):
                load_environment([])
            loader.assert_called_once_with(self.directory / "module/Monkey_Talkie_Test")

    def test_rejects_hash_mismatch(self):
        self.candidate.write_bytes(self.candidate.read_bytes() + b"changed")
        with self.assertRaises(AssertionError):
            ArtEnvironment(self.candidate)

    def test_relocation_and_original_resource_setup(self):
        fixture = Fixture(self.env)
        self.assertEqual(
            u32(fixture.cpu, self.env.code_base + 4), self.env.globals_base + 0x10
        )
        fixture.setup()
        self.assertEqual(u32(fixture.cpu, TABLE + self.env.room * 4), self.env.owner)
        self.assertEqual(
            bytes(fixture.cpu.mem_read(self.env.owner + 6, self.env.source_bytes)),
            self.env.payload[self.env.source : self.env.source + self.env.source_bytes],
        )
        self.assertEqual(bytes(fixture.cpu.mem_read(PRIMARY + 6, 8)), bytes([18]) * 8)
        self.assertEqual(fixture.cpu.reg_read(R.UC_M68K_REG_PC), 0xB00000)

    def test_instances_and_environments_are_isolated(self):
        other = ArtEnvironment(self.candidate)
        other.owner += 1
        other.art = synthetic_artifact(((113, 9),))
        other.images[0][8] ^= 1
        self.assertEqual(self.env.owner, 0x500000)
        self.assertNotEqual(self.env.art, other.art)
        self.assertNotEqual(self.env.images[0], other.images[0])
        first, second = Fixture(self.env), Fixture(self.env)
        first.cpu.mem_write(PRIMARY, b"changed")
        first.art[0] ^= 1
        first.reads.append((0, 1))
        self.assertEqual(bytes(second.cpu.mem_read(PRIMARY, 7)), bytes(7))
        self.assertEqual(second.art, self.env.art)
        self.assertEqual(second.reads, [])

    def test_allocation_failure_modes_and_fallbacks(self):
        for options, fast, index, chip, costume in (
            ({}, ARENA, INDEX, 0x40000, 0x700000),
            ({"failalloc": True}, 0, 0, 0, 0),
            ({"failfast": True}, 0, INDEX, 0x40000, 0x700000),
            ({"failindex": True}, ARENA, 0, 0x40000, 0x700000),
        ):
            with self.subTest(options=options):
                fixture = Fixture(self.env, **options)
                self.assertEqual(fixture.call("_nv_art_alloc", (32768,)), fast)
                self.assertEqual(fixture.call("_nv_art_alloc", (24,)), index)
                self.assertEqual(fixture.call("_nv_art_alloc_any", (32,)), chip)
                self.assertEqual(fixture.call("_nv_costume_alloc", (64,)), costume)
                fixture.call("_nv_art_free", (fast, 32768))
                self.assertEqual(fixture.frees, [(fast, 32768)])

    def test_file_reads_short_reads_and_corruption(self):
        destination = 0x7F0000
        for options in ({}, {"short": True}, {"corrupt": True}):
            with self.subTest(options=options):
                fixture = Fixture(self.env, **options)
                self.assertEqual(fixture.call("_nv_art_file_open"), 1)
                size = 15 if options.get("short") else 16
                self.assertEqual(
                    fixture.call(
                        "_nv_art_read_at", (1, self.env.offset, destination, 16)
                    ),
                    size,
                )
                self.assertEqual(
                    bytes(fixture.cpu.mem_read(destination, size)),
                    fixture.art[self.env.offset : self.env.offset + size],
                )
                for file, offset, count in (
                    (2, 0, 1),
                    (1, len(fixture.art) + 1, 1),
                    (1, len(fixture.art), 1),
                ):
                    self.assertEqual(
                        fixture.call(
                            "_nv_art_read_at", (file, offset, destination, count)
                        ),
                        0xFFFFFFFF,
                    )
                fixture.call("_nv_art_file_close", (1,))
                self.assertEqual(fixture.closed, [1])
                self.assertEqual(
                    fixture.art != self.env.art, bool(options.get("corrupt"))
                )
        self.assertEqual(Fixture(self.env, missing=True).call("_nv_art_file_open"), 0)


if __name__ == "__main__":
    unittest.main()
