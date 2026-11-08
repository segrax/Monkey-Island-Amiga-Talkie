"""Linked graphics loop checks."""

import json
import random
import struct
from art_fixture import (
    BACKUP,
    Fixture,
    MASK,
    PRIMARY,
    R,
    REGS,
    STACK,
    STOP,
    artifact_dir,
    be16,
    load_environment,
    u32,
    unicorn,
)

env = load_environment(description=__doc__)

P = artifact_dir("art")

# Two synthetic columns: both original codecs are valid independent repeat packets.
height = 8
source = (
    struct.pack("<I", 26)
    + b"OI"
    + struct.pack("<H", 113)
    + bytes(4)
    + struct.pack("<II", 12, 15)
    + bytes((10, 2, 64)) * 2
)
env.dictionary = 80
env.indices = 94
env.source = 126
env.strips = 64
env.codec_offset = 20
env.source_bytes = len(source)
env.size = 154
env.height = 8
env.width = 16
payload = bytearray(env.size)
struct.pack_into(
    ">4sHHIHHHHIIIIIIHH",
    payload,
    0,
    b"NPD1",
    1,
    64,
    env.size,
    env.width,
    env.height,
    1,
    14,
    16,
    env.dictionary,
    env.indices,
    env.source,
    env.source_bytes,
    env.strips,
    2,
    3,
)
palette = bytes([16, 0] + list(range(18, 32)))
payload[48:64] = palette
for i in range(2):
    struct.pack_into(">IHH", payload, 64 + 8 * i, 20 + i * 3, 3, 0)
payload[env.dictionary : env.dictionary + 14] = (
    bytes([18]) * 8 + bytes((0, 255, 0, 255, 0)) + b"\0"
)
payload[env.source : env.source + env.source_bytes] = source
env.payload = bytes(payload)
env.art = (
    struct.pack(">8sHHIIIII", b"NVPART01", 1, 24, 1, 32, 56, 56 + env.size, 0)
    + struct.pack(
        ">HHIIIHHI",
        10,
        113,
        56,
        env.size,
        env.source_bytes,
        env.width,
        env.height,
        0,
    )
    + env.payload
)
results = []
for ccr in range(32):
    states = []
    calls = []
    for fast in (False, True):
        f = Fixture(env)
        f.setup()
        c = f.cpu
        if not fast:
            for a, b in [
                (0x5104, "4e55fff448e73f20"),
                (0x516A, "3b40fff66000008e"),
                (0x5208, "4cdf04fc4e5d"),
            ]:
                c.mem_write(env.code_base + a, bytes.fromhex(b))
                c.ctl_remove_cache(
                    env.code_base + a,
                    env.code_base + a + len(bytes.fromhex(b)),
                )
        # Real object metadata: width two strips, height one eight-pixel unit.
        c.mem_write(env.globals_base + 0x1A1F + 1, b"\0")
        c.mem_write(env.globals_base + 0x1A1F + 0x46 + 1, b"\0")
        c.mem_write(env.globals_base + 0x1A1F + 0x8C + 1, b"\x02")
        c.mem_write(env.globals_base + 0x1A1F + 0xD2 + 1, b"\x01")
        be16(c, env.globals_base + 0x5994, 39)
        c.mem_write(env.globals_base + 0x5C49, palette)
        rng = random.Random(ccr + 600)
        vals = [rng.getrandbits(32) for _ in REGS]
        vals[12] = env.globals_base
        vals[15] = STACK
        vals[0] = 0
        c.reg_write(R.UC_M68K_REG_SR, 0x2000 | ccr)
        for r, v in zip(REGS, vals):
            c.reg_write(r, v)
        c.mem_write(STACK, struct.pack(">II", STOP, 0))
        entries = []
        current = [None, 0]

        def code(c, pc, size, u):
            if current[0] is not None:
                if pc == current[0]:
                    entries.append(current[1])
                    current[:] = [None, 0]
                else:
                    current[1] += 1
            if pc == env.addr("_nv_art_game_bind"):
                current[:] = [u32(c, c.reg_read(R.UC_M68K_REG_A7)), 1]

        hook = c.hook_add(unicorn.UC_HOOK_CODE, code)
        c.emu_start(env.code_base + 0x5104, STOP, count=1000000)
        c.hook_del(hook)
        assert c.reg_read(R.UC_M68K_REG_PC) == STOP
        states.append(
            (
                f.regs(),
                bytes(c.mem_read(env.globals_base, 29312)),
                bytes(c.mem_read(PRIMARY, 64006)),
                bytes(c.mem_read(BACKUP, 64006)),
                bytes(c.mem_read(MASK, 8006)),
            )
        )
        calls.append(entries)
    assert states[0] == states[1], (
        "whole object",
        ccr,
        [(x[0][0], x[0][1]) for x in states],
    )
    assert len(calls[0]) == len(calls[1]) == 2, (ccr, calls)
    assert calls[1][1] < calls[0][1] * 0.6, (ccr, calls)
    results.append(
        dict(
            ccr=ccr, bind_instructions_full=calls[0], bind_instructions_scoped=calls[1]
        )
    )
    print("whole original object loop CCR", ccr, calls, flush=True)
(P / "loop-validation.json").write_text(
    json.dumps(
        dict(
            module_sha256=env.metadata["sha256"],
            cases=len(results),
            results=results,
        ),
        indent=2,
    )
    + "\n"
)
