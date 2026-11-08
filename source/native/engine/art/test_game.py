"""Exercise linked ART guards, original caller ABI and one-use decode admission.

The file, resources, allocation map and operating-system calls are synthetic.
The retained original instructions independently check registers, flags and output."""

import json
import random
import struct
from art_fixture import synthetic_artifact
from art_fixture import (
    ARENA,
    BITMAP,
    Fixture,
    INDEX,
    LUT,
    PRIMARY,
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
    unicorn,
)

env = load_environment(description=__doc__)

RESULTS = []


def result(name, **kw):
    RESULTS.append(dict(name=name, **kw))
    print(name, kw, flush=True)


f = Fixture(env)
f.setup()
assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK)) == 1
result("valid registered C2P")
for name, change in [
    ("ROM table", lambda c: be32(c, env.globals_base + 0x2368, 0xF80000)),
    ("IO table", lambda c: be32(c, env.globals_base + 0x2368, 0xDFF000)),
    ("count zero", lambda c: be16(c, env.globals_base + 0x235A, 0)),
    (
        "owner moved",
        lambda c: be32(c, TABLE + env.room * 4, env.owner + 2),
    ),
    ("source offset changed", lambda c: be32(c, env.globals_base + 0x1DB2, 16)),
    ("slot changed", lambda c: c.mem_write(env.globals_base + 0x68E8, b"\x02")),
    ("short primary", lambda c: c.mem_write(PRIMARY, struct.pack("<I", 8))),
    (
        "backup overlaps primary",
        lambda c: be32(c, env.globals_base + 0x2794, PRIMARY),
    ),
    ("backup ROM", lambda c: be32(c, env.globals_base + 0x2794, 0xF80000)),
    ("mask IO", lambda c: be32(c, env.globals_base + 0x27A4, 0xDFF000)),
    (
        "bad codec",
        lambda c: c.mem_write(env.owner + 6 + env.codec_offset, b"\x00"),
    ),
    ("height zero", lambda c: c.mem_write(env.globals_base + 0x5C38, b"\x00")),
]:
    f = Fixture(env)
    f.setup()
    c = f.cpu
    c.mem_write(env.addr("_nv_art_decode_ready"), b"\x00\x00")
    before = bytes(c.mem_read(env.addr("_nv_art_decode"), 28))
    change(c)
    reads = []

    def rd(uc, access, p, n, value, u):
        if p >= 0xDFF000:
            reads.append((p, n))

    hook = c.hook_add(unicorn.UC_HOOK_MEM_READ, rd)
    f.call("_nv_art_game_bind", (0, STACK))
    c.hook_del(hook)
    assert not reads, (name, reads)
    assert not u16(c, env.addr("_nv_art_decode_ready")), (name, "armed")
    assert bytes(c.mem_read(env.addr("_nv_art_decode"), 28)) == before
    result("bind rejects " + name)
for name, src, dst, h, stack, change in [
    (
        "wrong display owner",
        PRIMARY + 6,
        0x700000,
        env.height,
        STACK,
        lambda c: None,
    ),
    (
        "output source",
        PRIMARY + 6,
        PRIMARY + 6,
        env.height,
        STACK,
        lambda c: None,
    ),
    ("output LUT", PRIMARY + 6, LUT, env.height, STACK, lambda c: None),
    ("output ART arena", PRIMARY + 6, ARENA, env.height, STACK, lambda c: None),
    (
        "output native control",
        PRIMARY + 6,
        env.addr("_nv_control"),
        env.height,
        STACK,
        lambda c: None,
    ),
    (
        "output stack",
        PRIMARY + 6,
        STACK - 100,
        env.height,
        STACK,
        lambda c: None,
    ),
    ("source ROM", 0xF80000, BITMAP, env.height, STACK, lambda c: None),
    ("source odd", PRIMARY + 7, BITMAP, env.height, STACK, lambda c: None),
    ("height0", PRIMARY + 6, BITMAP, 0, STACK, lambda c: None),
    ("height201", PRIMARY + 6, BITMAP, 201, STACK, lambda c: None),
    ("plane end", PRIMARY + 6, BITMAP + 7999, 2, STACK, lambda c: None),
    (
        "bad flip",
        PRIMARY + 6,
        BITMAP,
        env.height,
        STACK,
        lambda c: c.mem_write(env.globals_base + 0x16F5, b"\x02"),
    ),
    (
        "LUT owner mismatch",
        PRIMARY + 6,
        BITMAP,
        env.height,
        STACK,
        lambda c: be32(c, env.globals_base + 0x16F8, LUT + 2),
    ),
    ("stack underflow", PRIMARY + 6, BITMAP, env.height, 0, lambda c: None),
]:
    f = Fixture(env)
    f.setup()
    assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
    change(f.cpu)
    assert f.call("_nv_art_game_c2p", (src, dst, h, stack)) == 0, name
    result("C2P rejects " + name)
for name, kwargs in [
    ("missing", dict(missing=True)),
    ("alloc fail", dict(failalloc=True)),
    ("short payload", dict(short=True)),
]:
    f = Fixture(env, **kwargs)
    if not kwargs.get("missing") and not kwargs.get("failalloc"):
        # Original-source setup does not depend on whether payload load is admitted.
        try:
            f.setup()
        except AssertionError:
            pass
    assert not u16(f.cpu, env.addr("_nv_art") + 80), name
    result("fallback " + name, frees=f.frees)


def runhook(f, kind, fast, ccr=31, miss=False, unbound=False):
    c = f.cpu
    if not fast:
        old = {
            "object": (0x516A, "3b40fff66000008e"),
            "bind": (0x4AC4, "7000102c5c38"),
            "c2p": (0x14E72, "4eba051c4fef000e"),
        }[kind]
        c.mem_write(env.code_base + old[0], bytes.fromhex(old[1]))
    if miss:
        c.mem_write(PRIMARY + 6 + 320 * 3, b"\x01\x02\x03\x04\x05\x06\x07\x08")
    if unbound:
        c.mem_write(env.addr("_nv_art_columns"), bytes(40))
    rng = random.Random(514)
    values = [rng.randrange(1 << 32) for _ in REGS]
    values[12] = env.globals_base
    values[13] = 0x900100
    values[15] = STACK
    values[7] = 0
    c.reg_write(R.UC_M68K_REG_SR, ccr)
    for reg, v in zip(REGS, values):
        c.reg_write(reg, v)
    if kind == "c2p":
        c.mem_write(
            STACK,
            struct.pack(">IIIH", BITMAP, PRIMARY + 6, PRIMARY + 6, env.height),
        )
        start, end = 0x14E72, 0x14E7A
    elif kind == "object":
        start, end = 0x516A, 0x51FE
    else:
        start, end = 0x4AC4, 0x4ACA
    c.emu_start(env.code_base + start, env.code_base + end, count=5000000)
    assert c.reg_read(R.UC_M68K_REG_PC) == env.code_base + end
    return (
        f.regs(),
        bytes(c.mem_read(BITMAP, 40000)),
        bytes(c.mem_read(env.globals_base, 29312)),
        bytes(c.mem_read(0x9000E0, 48)),
    )


for kind in ("object", "bind", "c2p"):
    for ccr in (0, 4, 16, 31):
        for miss, unbound in (
            [(False, False), (True, False), (False, True)]
            if kind == "c2p"
            else [(False, False)]
        ):
            a = Fixture(env)
            a.setup()
            b = Fixture(env)
            b.setup()
            x = runhook(a, kind, False, ccr, miss, unbound)
            y = runhook(b, kind, True, ccr, miss, unbound)
            assert x == y, (
                kind,
                ccr,
                miss,
                unbound,
                [(i, x[i], y[i]) for i in range(len(x)) if x[i] != y[i]][:1],
            )
            result(
                "original hook differential",
                kind=kind,
                ccr=ccr,
                miss=miss,
                unbound=unbound,
            )


def note(name, **kw):
    result(name, **kw)


def flow(f, strip=0):
    c = f.cpu
    c.reg_write(R.UC_M68K_REG_SR, 31)
    c.reg_write(R.UC_M68K_REG_A7, STACK)
    c.reg_write(R.UC_M68K_REG_A4, env.globals_base)
    c.reg_write(R.UC_M68K_REG_D7, strip)
    events = []

    def trace(uc, pc, size, u):
        if pc in (
            env.code_base + 0x4ACA,
            env.code_base + 0x4BA2,
            env.addr("_nv_art_dispatch"),
            env.addr("_nv_continue_art_stripe"),
        ):
            events.append(
                (
                    hex(pc - env.code_base),
                    u16(c, env.addr("_nv_art_decode_ready")),
                )
            )

    hk = c.hook_add(unicorn.UC_HOOK_CODE, trace)
    c.emu_start(env.code_base + 0x4AC4, env.code_base + 0x4B06, count=5000000)
    c.hook_del(hk)
    assert c.reg_read(R.UC_M68K_REG_PC) == env.code_base + 0x4B06
    return events


# Test the real uninterrupted bind->setup->opcode-read->dispatch chain.
f = Fixture(env)
f.setup()
c = f.cpu
c.mem_write(env.globals_base + 0x5C49, env.payload[48:64])
c.mem_write(
    env.globals_base + 0x6812,
    bytes(
        env.payload[
            env.dictionary
            + int.from_bytes(
                env.payload[env.indices + row * 2 : env.indices + row * 2 + 2],
                "big",
            )
        ]
        for row in range(env.height)
    ),
)
c.mem_write(env.addr("_nv_art_decode_ready"), b"\x00\x00")
events = flow(f)
assert events[0][1] == 1 and events[-1][1] == 1 and len(events) == 3
assert not u16(c, env.addr("_nv_art_decode_ready"))
note("actual valid bind dispatch consumes latch", trace=events)
# A later object refusal cannot inherit the previous consumed latch. Same source,
# different slot, then the actual bind/dispatch flow must retain original fallback.
c.mem_write(env.globals_base + 0x68E8, b"\x02")
f.call("_nv_art_game_object", (STACK,))
be32(
    c,
    env.globals_base + 0x5C2A,
    env.owner + 6 + env.codec_offset,
)
events = flow(f)
assert all(not x[1] for x in events)
note("declined next slot leaves latch unarmed", trace=events)
# Owner pointer changes must reject bind without dereferencing non-RAM resources.
f = Fixture(env)
f.setup()
flow(f)
c = f.cpu
be32(c, TABLE + env.room * 4, 0xDFF000)
be32(
    c,
    env.globals_base + 0x5C2A,
    env.owner + 6 + env.codec_offset,
)
f.call("_nv_art_game_object", (STACK,))
events = flow(f)
assert all(not x[1] for x in events)
note("declined moved owner cannot reuse latch", trace=events)
# Validly armed source mutated between bind and decoder is independently refused by
# wrapper; no precomputed bytes published. Here ordinary original flow stays valid.
f = Fixture(env)
f.setup()
flow(f)
c = f.cpu
c.mem_write(env.globals_base + 0x5C49, env.payload[48:64])
be32(
    c,
    env.globals_base + 0x5C2A,
    env.owner + 6 + env.codec_offset,
)
c.mem_write(
    env.owner + 6 + env.codec_offset + 1,
    bytes([c.mem_read(env.owner + 6 + env.codec_offset + 1, 1)[0] ^ 1]),
)
events = flow(f)
assert len(events) == 4 and not u16(c, env.addr("_nv_art_decode_ready"))
note("changed compressed source consumed with exact fallback", trace=events)
# Room changes, freed owners, and arena teardown invalidate C2P hints.
f = Fixture(env)
f.setup()
c = f.cpu
assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
f.call("_nv_art_object", (255, 65534, 2))
assert bytes(c.mem_read(env.addr("_nv_art_columns"), 40)) == bytes(40)
assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
note("room change clears C2P bindings")
f = Fixture(env)
f.setup()
c = f.cpu
be32(c, env.globals_base + 0x2784, 0)
assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
note("freed primary owner refuses stale C2P hint")
f = Fixture(env)
f.setup()
f.call("_nv_art_game_stop")
f.call("_nv_art_game_stop")
c = f.cpu
assert not u16(c, env.addr("_nv_art") + 80)
assert not u16(c, env.addr("_nv_art_decode_ready"))
assert bytes(c.mem_read(env.addr("_nv_art_columns"), 40)) == bytes(40)
assert len(f.frees) == 2
assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
note("idempotent stop clears arena binding latch", frees=f.frees)

# Entry validation must remain safe whether metadata is prefetched or searched.
for label, offset, value in [
    ("offset before data", 36, 32),
    ("offset beyond file", 36, len(env.art) + 2),
    ("zero payload", 40, 0),
    ("odd payload", 40, env.size - 1),
    ("payload exceeds file", 40, env.size + 2),
]:
    malformed = bytearray(env.art)
    struct.pack_into(">I", malformed, offset, value)
    f = Fixture(env, artifact=malformed)
    admitted = (
        f.call("_nv_art_object", (env.room, env.obj, 1))
        if u16(f.cpu, env.addr("_nv_art") + 80)
        else 0
    )
    assert not admitted, label
    assert bytes(f.cpu.mem_read(env.addr("_nv_art_columns"), 40)) == bytes(40)
    result("invalid directory fallback " + label)
# Even matching forged bitmap globals cannot admit native state as a display.
for name, base in [
    ("ART arena", ARENA),
    ("ART metadata", INDEX),
    ("native control", env.addr("_nv_control")),
    ("LUT", LUT),
    ("stack", STACK - 200),
]:
    f = Fixture(env)
    f.setup()
    c = f.cpu
    be32(c, env.globals_base + 0x706E, base)
    be32(c, env.globals_base + 0x6FEE, base)
    assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, base, env.height, STACK)), name
    result("forged bitmap ownership rejects " + name)
f = Fixture(env)
f.setup()
f.call("_nv_costume_cache_start")
c = f.cpu
assert u32(c, env.addr("_nv_costume_cache") + 28) == 0x700000
be32(c, env.globals_base + 0x706E, 0x700000)
be32(c, env.globals_base + 0x6FEE, 0x700000)
assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, 0x700000, env.height, STACK))
result("forged bitmap ownership rejects compiled arena")
# An unknown object gate must preserve the same caller state while calling C.
for ccr in (0, 31):
    a = Fixture(env)
    a.setup()
    b = Fixture(env)
    b.setup()
    b.cpu.mem_write(env.addr("_nv_art_object_gate"), bytes(72))
    assert runhook(a, "object", False, ccr) == runhook(b, "object", True, ccr)
    result("unknown object gate original caller differential", ccr=ccr)

f = Fixture(env, failindex=True)
f.setup()
assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
result("optional metadata allocation failure retains file search fallback")
f = Fixture(env, artifact=synthetic_artifact(((113, 8), (114, 9))))
f.setup()
c = f.cpu
assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
assert f.call("_nv_art_object", (env.room, 114, 2))
assert u16(c, env.addr("_nv_art") + 78) == 114
assert bytes(c.mem_read(env.addr("_nv_art_columns"), 40)) == bytes(40)
assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
result("same room larger artifact reuse invalidates old arena bindings")

if env.metadata.get("engine_planar_cache", {}).get("allow_chip_fallback"):
    f = Fixture(env, failfast=True)
    f.setup()
    c = f.cpu
    assert u16(c, env.addr("_nv_art") + 82) == 256
    assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
    be32(c, env.globals_base + 0x706E, 0x40000)
    be32(c, env.globals_base + 0x6FEE, 0x40000)
    assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, 0x40000, env.height, STACK))
    f.call("_nv_art_game_stop")
    f.call("_nv_art_game_stop")
    assert sorted(f.frees) == sorted([(INDEX, 24), (0x40000, 32768)])
    result("FAST failure ANY payload fallback lifecycle and alias guards")

checksum_only = bytearray(env.art)
struct.pack_into(">I", checksum_only, 52, env.checksum ^ 1)
f = Fixture(env, artifact=checksum_only)
f.setup()
assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
result("trusted generated artifact accepts checksum field only change")

# A room transition can precede every new object hook; the C2P caller must clear
# the prior room binding once and subsequently take its cheap unbound fallback.
a = Fixture(env)
a.setup()
b = Fixture(env)
b.setup()
for fixture in (a, b):
    fixture.cpu.mem_write(env.globals_base + 0x19F9, bytes((env.room + 1,)))
counts = {"room": 0, "c2p": 0}


def gate_calls(cpu, pc, size, unused):
    if pc == env.addr("_nv_art_game_room"):
        counts["room"] += 1
    if pc == env.addr("_nv_art_game_c2p"):
        counts["c2p"] += 1


hook = b.cpu.hook_add(unicorn.UC_HOOK_CODE, gate_calls)
assert runhook(a, "c2p", False) == runhook(b, "c2p", True)
assert not u16(b.cpu, env.addr("_nv_art_decode_ready"))
assert bytes(b.cpu.mem_read(env.addr("_nv_art_columns"), 40)) == bytes(40)
assert counts == {"room": 1, "c2p": 0}
runhook(b, "c2p", True)
assert counts == {"room": 1, "c2p": 0}
b.cpu.hook_del(hook)
result("actual C2P room transition clears stale hints once", calls=counts)
for name, change in [
    ("primary allocation shrunk", lambda c: c.mem_write(PRIMARY, struct.pack("<I", 8))),
    (
        "bitmap identity moved",
        lambda c: be32(c, env.globals_base + 0x6FEE, BITMAP + 2),
    ),
    ("LUT owner moved", lambda c: be32(c, env.globals_base + 0x16F8, LUT + 2)),
]:
    f = Fixture(env)
    f.setup()
    c = f.cpu
    assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
    change(c)
    assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK)), (
        name
    )
    result("warm display memo invalidation " + name)

f = Fixture(env)
f.setup()
c = f.cpu
assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
assert not f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, BITMAP + 4096))
result("warm display memo exact stack invalidation")
f = Fixture(env)
f.setup()
c = f.cpu
f.call("_nv_art_game_bind", (0, PRIMARY + 4096))
assert not u16(c, env.addr("_nv_art_decode_ready"))
result("warm bind memo exact stack invalidation")
for kind in ("bind", "display"):
    f = Fixture(env)
    f.setup()
    c = f.cpu
    if kind == "display":
        assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
    checks = []

    def protection_call(cpu, pc, size, unused):
        if pc == env.addr("_nv_art_runtime_overlap"):
            checks.append(pc)

    hook = c.hook_add(unicorn.UC_HOOK_CODE, protection_call)
    be32(
        c,
        env.addr("_nv_art") + 52,
        u32(c, env.addr("_nv_art") + 52) + 1,
    )
    if kind == "bind":
        f.call("_nv_art_game_bind", (0, STACK))
        assert u16(c, env.addr("_nv_art_decode_ready"))
    else:
        assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK))
    c.hook_del(hook)
    assert checks, kind
    result("warm " + kind + " memo generation revalidates", checks=len(checks))

report = dict(
    module_sha256=env.metadata["sha256"], synthetic_artifact=True, cases=RESULTS
)
(artifact_dir("art") / "game-validation.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    json.dumps(dict(art_game_cases=len(RESULTS), module_sha256=env.metadata["sha256"]))
)
