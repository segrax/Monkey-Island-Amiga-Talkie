"""Shared synthetic resources and linked 68000 graphics fixtures.

Importing this module does not parse arguments, load a candidate or run tests.
Each ArtEnvironment owns its linked images and mutable resource description.
"""

from pathlib import Path
import argparse
import hashlib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "engine"), str(ROOT / "tools/python")]
from paths import engine_build
from paths import artifact_dir as artifact_dir
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as R

ARENA, INDEX, TABLE, PRIMARY, BACKUP, MASK, LUT, BITMAP, STACK, STOP, SRSTORE = (
    0x400000,
    0x410000,
    0x520000,
    0x600000,
    0x620000,
    0x640000,
    0x660000,
    0x680000,
    0xA0F000,
    0xB00000,
    0xB00100,
)
REGS = [
    getattr(R, "UC_M68K_REG_" + name)
    for name in [f"D{i}" for i in range(8)] + [f"A{i}" for i in range(8)]
]


def synthetic_artifact(specs=((113, 8),)):
    palette = bytes([16, 0] + list(range(18, 32)))
    color = palette[2]
    planes = bytes(255 if color & (1 << bit) else 0 for bit in (0, 1, 3, 4, 2))
    payloads = []
    for obj, height in specs:
        source = (
            struct.pack("<I", 19)
            + b"OI"
            + struct.pack("<H", obj)
            + bytes(4)
            + struct.pack("<I", 8)
            + bytes((10, 2, height * 8))
        )
        dictionary = 72
        indices = 86
        source_offset = indices + height * 2
        masks = (source_offset + len(source) + 1) & ~1
        size = (masks + (height + 7) // 8 + 1) & ~1
        payload = bytearray(size)
        struct.pack_into(
            ">4sHHIHHHHIIIIIIHH",
            payload,
            0,
            b"NPD1",
            1,
            64,
            size,
            8,
            height,
            1,
            14,
            height,
            dictionary,
            indices,
            source_offset,
            len(source),
            64,
            1,
            3,
        )
        payload[48:64] = palette
        struct.pack_into(">IHH", payload, 64, 16, 3, 0)
        payload[dictionary : dictionary + 14] = bytes([color]) * 8 + planes + b"\0"
        payload[source_offset : source_offset + len(source)] = source
        a = total = 65535
        for offset in range(0, size, 2):
            a += int.from_bytes(payload[offset : offset + 2], "big")
            total += a
        checksum = ((total % 65535 or 65535) << 16) | (a % 65535 or 65535)
        payloads.append((obj, height, bytes(payload), checksum))
    data_offset = 32 + len(payloads) * 24
    offset = data_offset
    entries = bytearray()
    data = bytearray()
    for obj, height, payload, checksum in payloads:
        entries += struct.pack(
            ">HHIIIHHI", 10, obj, offset, len(payload), 19, 8, height, checksum
        )
        data += payload
        offset += len(payload)
    header = struct.pack(
        ">8sHHIIIII", b"NVPART01", 1, 24, len(payloads), 32, data_offset, offset, 0
    )
    return header + entries + data


def be32(c, p, n):
    c.mem_write(p, struct.pack(">I", n))


def be16(c, p, n):
    c.mem_write(p, struct.pack(">H", n))


def u32(c, p):
    return int.from_bytes(c.mem_read(p, 4), "big")


def u16(c, p):
    return int.from_bytes(c.mem_read(p, 2), "big")


class ArtEnvironment:
    """A relocated candidate and an independently configurable synthetic resource."""

    def __init__(self, candidate):
        self.candidate = Path(candidate)
        self.metadata = json.loads((self.candidate.parent / "module.json").read_text())
        assert (
            hashlib.sha256(self.candidate.read_bytes()).hexdigest()
            == self.metadata["sha256"]
        )
        reader = HunkReader()
        assert reader.read_file(str(self.candidate)) == 0 and reader.build_segments()
        self.bases = {}
        cursor = 0x100000
        for index, hunk in enumerate(reader.hunks[0]["hunks"]):
            self.bases[index] = cursor
            cursor += (hunk["size"] + 65535) & ~65535
        self.images = {
            hunk["hunk_no"]: bytearray(hunk["data"])
            for hunk in reader.hunks
            if "data" in hunk
        }
        section = 0
        for hunk in reader.hunks:
            section = hunk.get("hunk_no", section)
            if hunk["type_name"] in ("HUNK_ABSRELOC32", "HUNK_RELOC32SHORT"):
                for target, offsets in hunk["reloc"].items():
                    for offset in offsets:
                        value = struct.unpack_from(">I", self.images[section], offset)[
                            0
                        ]
                        struct.pack_into(
                            ">I",
                            self.images[section],
                            offset,
                            value + self.bases[target],
                        )
        self.code_base, self.globals_base = self.bases[0], self.bases[2]
        self.owner = 0x500000
        self.art = synthetic_artifact()
        for index in range(int.from_bytes(self.art[12:16], "big")):
            entry = struct.unpack_from(">HHIIIHHI", self.art, 32 + 24 * index)
            if entry[:2] == (10, 113):
                break
        else:
            raise AssertionError("synthetic object fixture absent")
        (
            self.room,
            self.obj,
            self.offset,
            self.size,
            self.source_bytes,
            self.width,
            self.height,
            self.checksum,
        ) = entry
        self.payload = self.art[self.offset : self.offset + self.size]
        self.dictionary, self.indices, self.source, self.strips = [
            int.from_bytes(self.payload[offset : offset + 4], "big")
            for offset in (24, 28, 32, 40)
        ]
        self.codec_offset = int.from_bytes(
            self.payload[self.strips : self.strips + 4], "big"
        )

    def addr(self, name):
        export = self.metadata["exports"][name]
        return self.bases[export["hunk"]] + export["offset"]


def load_environment(argv=None, *, description=None):
    """Parse the common standalone-test CLI, then load its selected candidate."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "--candidate", type=Path, default=engine_build() / "module/Monkey_Talkie_Test"
    )
    return ArtEnvironment(parser.parse_args(argv).candidate)


class Fixture:
    """One emulated game instance using the supplied environment."""

    def __init__(
        self,
        environment,
        missing=False,
        failalloc=False,
        short=False,
        corrupt=False,
        artifact=None,
        failindex=False,
        failfast=False,
    ):
        self.environment = environment
        env = environment
        self.cpu = unicorn.Uc(unicorn.UC_ARCH_M68K, unicorn.UC_MODE_BIG_ENDIAN)
        self.cpu.ctl_set_cpu_model(R.UC_CPU_M68K_M68000)
        self.cpu.mem_map(0, 0x1000000)
        c = self.cpu
        for n, data in env.images.items():
            c.mem_write(env.bases[n], bytes(data))
        self.allocs = []
        self.frees = []
        self.reads = []
        self.closed = []
        self.missing = missing
        self.failalloc = failalloc
        self.failindex = failindex
        self.failfast = failfast
        self.short = short
        self.art = bytearray(env.art if artifact is None else artifact)
        if corrupt:
            self.art[env.offset + env.dictionary] ^= 1
        self.io = {
            env.addr(n): n
            for n in (
                "_nv_costume_alloc",
                "_nv_art_alloc",
                "_nv_art_alloc_any",
                "_nv_art_free",
                "_nv_art_file_open",
                "_nv_art_file_close",
                "_nv_art_read_at",
            )
            if n in env.metadata["exports"]
        }
        c.hook_add(unicorn.UC_HOOK_CODE, self.iohook)
        be32(c, 4, 0x8000)
        be32(c, 0x8000 + 322, 0x8200)
        be32(c, 0x8200, 0x8240)
        be32(c, 0x8240, 0)
        be32(c, 0x8200 + 20, 0x10000)
        be32(c, 0x8200 + 24, 0xC00000)
        be32(c, env.addr("_nv_control") + 12, env.code_base)
        be32(c, env.addr("_nv_control") + 16, env.globals_base)
        self.call("_nv_art_game_start")

    def _allocate(self, name, size):
        self.allocs.append(size)
        if self.failalloc:
            return 0
        if name == "_nv_art_alloc":
            if self.failfast and size == 32768:
                return 0
            if self.failindex and size != 32768:
                return 0
        if name == "_nv_costume_alloc":
            return 0x700000
        if name == "_nv_art_alloc_any":
            return 0x40000
        return ARENA if size == 32768 else INDEX

    def iohook(self, cpu, pc, size, unused):
        """Model allocation and file calls at their linked entry points."""
        if pc not in self.io:
            return
        name = self.io[pc]
        stack = cpu.reg_read(R.UC_M68K_REG_A7)
        arguments = [u32(cpu, stack + 4 * index) for index in range(1, 5)]
        result = 0
        if name in ("_nv_art_alloc", "_nv_art_alloc_any", "_nv_costume_alloc"):
            result = self._allocate(name, arguments[0])
            if result:
                cpu.mem_write(result, bytes(arguments[0]))
        elif name == "_nv_art_free":
            self.frees.append(tuple(arguments[:2]))
        elif name == "_nv_art_file_open":
            result = 0 if self.missing else 1
        elif name == "_nv_art_file_close":
            self.closed.append(arguments[0])
        else:
            file, offset, destination, count = arguments
            self.reads.append((offset, count))
            result = count
            if file != 1 or offset > len(self.art) or count > len(self.art) - offset:
                result = 0xFFFFFFFF
            else:
                if self.short and offset == self.environment.offset:
                    result = count - 1
                read_size = max(0, result)
                cpu.mem_write(destination, bytes(self.art[offset : offset + read_size]))
        cpu.reg_write(R.UC_M68K_REG_D0, result)
        cpu.reg_write(R.UC_M68K_REG_PC, u32(cpu, stack))
        cpu.reg_write(R.UC_M68K_REG_A7, stack + 4)

    def call(self, n, args=()):
        env = self.environment
        c = self.cpu
        c.reg_write(R.UC_M68K_REG_A7, STACK)
        c.mem_write(STACK, struct.pack(">" + str(len(args) + 1) + "I", STOP, *args))
        c.emu_start(env.addr(n) if isinstance(n, str) else n, STOP, count=5000000)
        assert c.reg_read(R.UC_M68K_REG_PC) == STOP, (
            n,
            hex(c.reg_read(R.UC_M68K_REG_PC)),
        )
        return c.reg_read(R.UC_M68K_REG_D0)

    def setup(self):
        env = self.environment
        c = self.cpu
        c.mem_write(
            env.owner,
            struct.pack("<I", env.source_bytes + 6)
            + bytes((3, env.room))
            + env.payload[env.source : env.source + env.source_bytes],
        )
        c.mem_write(TABLE, bytes(256 * 4))
        be32(c, TABLE + env.room * 4, env.owner)
        for base, bytes_, id_ in (
            (PRIMARY, 64006, 1),
            (BACKUP, 64006, 5),
            (MASK, 8006, 9),
        ):
            c.mem_write(
                base, struct.pack("<I", bytes_) + bytes((4, id_)) + bytes(bytes_ - 6)
            )
        for off, value, size in (
            (0x19F9, env.room, 1),
            (0x68E8, 1, 1),
            (0x235A, 256, 2),
            (0x2368, TABLE, 4),
            (0x1DAE + 4, 14, 4),
            (0x2784, PRIMARY, 4),
            (0x2794, BACKUP, 4),
            (0x27A4, MASK, 4),
            (0x5C38, env.height, 1),
            (0x5C34, 0, 2),
            (0x5C32, 0, 2),
            (0x5992, 0, 2),
            (0x5D40, 0, 2),
            (0x5C1E, PRIMARY + 6, 4),
            (0x5C1A, BACKUP + 6, 4),
            (0x5C2A, env.owner + 6 + env.codec_offset, 4),
            (0x16F8, LUT, 4),
            (0x16F5, 0, 1),
            (0x706E, BITMAP, 4),
            (0x6FEE, BITMAP, 4),
            (0x5EBE, 0, 2),
        ):
            c.mem_write(env.globals_base + off, value.to_bytes(size, "big"))
        self.call(env.code_base + 0x15418, (LUT,))
        self.call("_nv_art_game_object", (STACK,))
        assert u16(c, env.addr("_nv_art") + 80) == 1
        self.call("_nv_art_game_bind", (0, STACK))
        assert u16(c, env.addr("_nv_art_decode_ready")) == 1
        for row in range(env.height):
            index = int.from_bytes(
                env.payload[env.indices + row * 2 : env.indices + row * 2 + 2],
                "big",
            )
            c.mem_write(
                PRIMARY + 6 + row * 320,
                env.payload[env.dictionary + index : env.dictionary + index + 8],
            )

    def regs(self):
        c = self.cpu
        c.mem_write(STOP, bytes.fromhex("40f900b00100"))
        c.emu_start(STOP, STOP + 6, count=1)
        return tuple(c.reg_read(r) for r in REGS), bytes(c.mem_read(SRSTORE, 2))
