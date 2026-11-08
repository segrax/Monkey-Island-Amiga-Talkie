"""Synthetic initial-prewarm lifecycle and actual hook comparison."""

import json
import random
import struct
from art_fixture import (
    ARENA,
    Fixture,
    R,
    REGS,
    STACK,
    TABLE,
    artifact_dir,
    be16,
    be32,
    load_environment,
    u16,
    u32,
)

env = load_environment(description=__doc__)


def artifact(specs=((10, 113, 8), (10, 114, 9), (10, 115, 7), (12, 211, 6))):
    palette = bytes([16, 0] + list(range(18, 32)))
    color = palette[2]
    planes = bytes(255 if color & (1 << bit) else 0 for bit in (0, 1, 3, 4, 2))
    payloads = []
    for room, obj, height in specs:
        source = (
            struct.pack("<I", 19)
            + b"OI"
            + struct.pack("<H", obj)
            + bytes(4)
            + struct.pack("<I", 8)
            + bytes((10, 2, height * 8))
        )
        src = 86 + height * 2
        deps = (src + len(source) + 1) & ~1
        size = (deps + (height + 7) // 8 + 1) & ~1
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
            72,
            86,
            src,
            len(source),
            64,
            1,
            3,
        )
        payload[48:64] = palette
        struct.pack_into(">IHH", payload, 64, 16, 3, 0)
        payload[72:86] = bytes([color]) * 8 + planes + b"\0"
        payload[src : src + len(source)] = source
        a = b = 65535
        for i in range(0, size, 2):
            a = (a + int.from_bytes(payload[i : i + 2], "big")) % 65535
            b = (b + a) % 65535
        payloads.append(
            (room, obj, height, payload, ((b or 65535) << 16) | (a or 65535))
        )
    offset = 32 + len(payloads) * 24
    index = bytearray()
    body = bytearray()
    for room, obj, h, payload, checksum in payloads:
        index += struct.pack(
            ">HHIIIHHI", room, obj, offset, len(payload), 19, 8, h, checksum
        )
        body += payload
        offset += len(payload)
    return (
        struct.pack(
            ">8sHHIIIII",
            b"NVPART01",
            1,
            24,
            len(payloads),
            32,
            32 + len(payloads) * 24,
            offset,
            0,
        )
        + index
        + body
    )


SYNTHETIC = artifact()
(artifact_dir("art") / "synthetic-prewarm.dat").write_bytes(SYNTHETIC)


def resources(f, room=10, obj=113, visible=0):
    c = f.cpu
    for i in range(int.from_bytes(SYNTHETIC[12:16], "big")):
        entry = struct.unpack_from(">HHIIIHHI", SYNTHETIC, 32 + 24 * i)
        if entry[:2] == (room, obj):
            break
    else:
        raise AssertionError((room, obj))
    payload = SYNTHETIC[entry[2] : entry[2] + entry[3]]
    src = int.from_bytes(payload[32:36], "big")
    source = payload[src : src + 19]
    c.mem_write(env.owner, struct.pack("<I", 25) + bytes((3, room)) + source)
    c.mem_write(TABLE, bytes(1024))
    be32(c, TABLE + room * 4, env.owner)
    for off, value, n in (
        (0x19F9, visible, 1),
        (0x68E8, 1, 1),
        (0x235A, 256, 2),
        (0x2368, TABLE, 4),
        (0x1DB2, 14, 4),
    ):
        c.mem_write(env.globals_base + off, value.to_bytes(n, "big"))
    return source


def warm(f, room=10):
    f.call("_nv_art_game_prewarm", (room, STACK))


def count(f, off):
    return u32(f.cpu, env.addr("_nv_art_warm") + off)


def entry(f, original, room, ccr):
    c = f.cpu
    if original:
        c.mem_write(env.code_base + 0x3B7A, bytes.fromhex("7000102d0009"))
        c.ctl_remove_cache(env.code_base + 0x3B7A, env.code_base + 0x3B80)
    rng = random.Random(151)
    values = [rng.randrange(1 << 32) for _ in REGS]
    values[12] = env.globals_base
    values[13] = STACK + 24
    values[15] = STACK
    c.reg_write(R.UC_M68K_REG_SR, ccr)
    for reg, v in zip(REGS, values):
        c.reg_write(reg, v)
    c.mem_write(STACK, bytes(range(64)))
    c.mem_write(STACK + 33, bytes((room,)))
    c.emu_start(env.code_base + 0x3B7A, env.code_base + 0x3B80, count=5000000)
    assert c.reg_read(R.UC_M68K_REG_PC) == env.code_base + 0x3B80
    return (
        f.regs(),
        bytes(c.mem_read(env.globals_base, 29312)),
        bytes(c.mem_read(env.owner, 25)),
        bytes(c.mem_read(TABLE, 1024)),
        bytes(c.mem_read(STACK, 64)),
    )


results = []
for ccr in range(32):
    a = Fixture(env, artifact=SYNTHETIC)
    b = Fixture(env, artifact=SYNTHETIC)
    resources(a)
    resources(b)
    assert entry(a, True, 10, ccr) == entry(b, False, 10, ccr), ccr
    assert count(b, 8) == 1 and not u16(b.cpu, env.addr("_nv_art_decode_ready"))
    assert bytes(b.cpu.mem_read(env.addr("_nv_art_columns"), 40)) == bytes(40)
    results.append({"case": "success actual3B7A ABI/CCR", "ccr": ccr})
for room in range(256):
    for ccr in (0, 4, 16, 31):
        a = Fixture(env, missing=True)
        b = Fixture(env, missing=True)
        assert entry(a, True, room, ccr) == entry(b, False, room, ccr), (room, ccr)
        results.append(
            {"case": "disabled actual3B7A ABI/CCR", "room": room, "ccr": ccr}
        )
for ccr in range(32):
    a = Fixture(env, artifact=SYNTHETIC)
    b = Fixture(env, artifact=SYNTHETIC)
    for f in (a, b):
        c = f.cpu
        c.mem_write(env.owner, struct.pack("<I", 6) + bytes((3, 250)))
        be32(c, TABLE + 1000, env.owner)
        be16(c, env.globals_base + 0x235A, 256)
        be32(c, env.globals_base + 0x2368, TABLE)
    assert entry(a, True, 250, ccr) == entry(b, False, 250, ccr), ccr
    assert not count(b, 8) and count(b, 4) == 1
    results.append(
        {"case": "enabled no eligible negative room actual3B7A ABI/CCR", "ccr": ccr}
    )
for name, change in [
    ("ROM table", lambda c: be32(c, env.globals_base + 0x2368, 0xF80000)),
    ("IO table", lambda c: be32(c, env.globals_base + 0x2368, 0xDFF000)),
    ("room count", lambda c: be16(c, env.globals_base + 0x235A, 0)),
    ("wrong owner", lambda c: c.mem_write(env.owner + 4, b"\x04")),
    ("short owner", lambda c: c.mem_write(env.owner, struct.pack("<I", 5))),
    ("owner ART arena", lambda c: be32(c, TABLE + 40, ARENA)),
]:
    f = Fixture(env, artifact=SYNTHETIC)
    resources(f)
    change(f.cpu)
    warm(f)
    assert not count(f, 8), name
    results.append({"case": "owner rejection", "name": name})
f = Fixture(env, artifact=SYNTHETIC)
resources(f)
warm(f)
c = f.cpu
assert count(f, 8) == 1 and u16(c, env.addr("_nv_art_warm") + 22) == 114
assert (
    u16(c, env.addr("_nv_art") + 76) == 65535
    and u16(c, env.addr("_nv_art") + 78) == 65535
)
oldreads = len(f.reads)
c.mem_write(env.globals_base + 0x19F9, b"\0")
f.call("_nv_art_game_room")
c.mem_write(env.globals_base + 0x19F9, b"\x0a")
f.call("_nv_art_game_room")
resources(f, obj=114, visible=10)
f.call("_nv_art_game_object", (STACK,))
assert (
    count(f, 12) == 1
    and len(f.reads) == oldreads
    and u16(c, env.addr("_nv_art") + 78) == 114
)
results.append({"case": "pending survives room0 to visible room and no reload"})
f = Fixture(env, artifact=SYNTHETIC)
resources(f)
warm(f)
old = u32(f.cpu, env.addr("_nv_art") + 52)
resources(f, obj=113, visible=10)
f.call("_nv_art_game_object", (STACK,))
assert (
    u16(f.cpu, env.addr("_nv_art") + 78) == 113
    and u32(f.cpu, env.addr("_nv_art") + 52) == old + 1
    and count(f, 16) == 1
)
results.append({"case": "smaller first visible object supersedes low priority prefill"})
f = Fixture(env, artifact=SYNTHETIC)
resources(f, visible=10)
f.call("_nv_art_game_object", (STACK,))
oldreads = len(f.reads)
warm(f, 12)
assert len(f.reads) == oldreads and count(f, 8) == 0
results.append({"case": "existing active cache blocks later prewarm"})


class ReadFailureFixture(Fixture):
    def iohook(self, c, pc, size, unused):
        if pc == env.addr("_nv_art_read_at") and getattr(self, "fail_read_once", False):
            self.fail_read_once = False
            sp = c.reg_read(R.UC_M68K_REG_A7)
            self.reads.append((u32(c, sp + 8), u32(c, sp + 16)))
            c.reg_write(R.UC_M68K_REG_D0, 0xFFFFFFFF)
            c.reg_write(R.UC_M68K_REG_PC, u32(c, sp))
            c.reg_write(R.UC_M68K_REG_A7, sp + 4)
            return
        super().iohook(c, pc, size, unused)


def empty_room(f, room):
    c = f.cpu
    c.mem_write(env.owner, struct.pack("<I", 6) + bytes((3, room)))
    be32(c, TABLE + 4 * room, env.owner)
    be16(c, env.globals_base + 0x235A, 256)
    be32(c, env.globals_base + 0x2368, TABLE)


f = Fixture(env, artifact=SYNTHETIC)
empty_room(f, 0)
warm(f, 0)
assert count(f, 8) == 0 and not u16(f.cpu, env.addr("_nv_art_warm") + 24)
resources(f)
warm(f)
assert count(f, 8) == 1
old = len(f.reads)
warm(f, 12)
assert len(f.reads) == old
results.append(
    {"case": "multiple no eligible then eligible preloads; first pending wins"}
)
f = ReadFailureFixture(env, artifact=SYNTHETIC, failindex=True)
empty_room(f, 250)
f.fail_read_once = True
warm(f, 250)
assert count(f, 8) == 0 and u16(f.cpu, env.addr("_nv_art") + 80)
old = len(f.reads)
warm(f, 250)
assert len(f.reads) == old
resources(f)
warm(f)
assert count(f, 8) == 1
results.append(
    {"case": "directory IO failure bounded per room; later eligible preload succeeds"}
)
f = ReadFailureFixture(env, artifact=SYNTHETIC)
resources(f)
f.fail_read_once = True
warm(f)
assert not u16(f.cpu, env.addr("_nv_art") + 80)
old = len(f.reads)
warm(f)
assert len(f.reads) == old
results.append({"case": "selected payload IO failure disables optional prewarm"})
corrupt = bytearray(SYNTHETIC)
for i in range(int.from_bytes(corrupt[12:16], "big")):
    if struct.unpack_from(">HH", corrupt, 32 + 24 * i) == (10, 114):
        corrupt[int.from_bytes(corrupt[36 + 24 * i : 40 + 24 * i], "big")] ^= 1
        break
f = Fixture(env, artifact=corrupt)
resources(f)
warm(f)
assert not u16(f.cpu, env.addr("_nv_art") + 80)
results.append(
    {"case": "selected payload invalid bounds/header never publishes identity"}
)
f = ReadFailureFixture(env, artifact=SYNTHETIC)
resources(f)
warm(f)
resources(f, obj=113, visible=10)
f.fail_read_once = True
f.call("_nv_art_game_object", (STACK,))
assert not u16(f.cpu, env.addr("_nv_art") + 80) and not u16(
    f.cpu, env.addr("_nv_art_decode_ready")
)
old = len(f.reads)
resources(f, obj=114, visible=10)
f.call("_nv_art_game_object", (STACK,))
assert len(f.reads) == old and not u16(f.cpu, env.addr("_nv_art_decode_ready"))
results.append({"case": "superseding failed read cannot reuse old pending image"})
f = Fixture(env, artifact=SYNTHETIC)
resources(f)
warm(f)
f.call("_nv_art_game_stop")
f.call("_nv_art_game_start")
resources(f)
warm(f)
assert count(f, 8) == 1 and count(f, 12) == 0
results.append(
    {"case": "stop restart resets pending identity and initial warmup state"}
)
report = {
    "pass": True,
    "cases": len(results),
    "module_sha256": env.metadata["sha256"],
    "synthetic_only": True,
    "results": results,
    "all32_CCR_success": True,
    "all256_room_bytes_disabled": True,
    "registers_CCR_X_SP_caller_frame_globals_equal": True,
}
(artifact_dir("art") / "prewarm-validation.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(json.dumps({k: v for k, v in report.items() if k != "results"}), flush=True)
