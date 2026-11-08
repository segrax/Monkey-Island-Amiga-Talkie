"""Check both source alignments through the linked resource loader and guards."""

import json
import struct
from art_fixture import (
    ARENA,
    BITMAP,
    Fixture,
    PRIMARY,
    STACK,
    artifact_dir,
    load_environment,
    u32,
)

env = load_environment(description=__doc__)


def checksum(data):
    a = total = 65535
    for at in range(0, len(data), 2):
        a = (a + int.from_bytes(data[at : at + 2], "big")) % 65535
        total = (total + a) % 65535
    return ((total or 65535) << 16) | (a or 65535)


original = env.payload
source = env.source
length = env.source_bytes
columns = env.width // 8
mask_bytes = columns * ((env.height + 7) // 8)
old_masks = (source + length + 1) & ~1
new_end = source + length + 1
odd = bytearray(original[:source]) + b"\0" + original[source : source + length]
odd += bytes(new_end & 1)
odd += original[old_masks : old_masks + mask_bytes]
odd += bytes(len(odd) & 1)
struct.pack_into(">H", odd, 4, 2)
struct.pack_into(">I", odd, 8, len(odd))
struct.pack_into(">I", odd, 32, source + 1)
artifact = bytearray(env.art[: env.offset]) + odd
struct.pack_into(">I", artifact, 24, len(artifact))
struct.pack_into(">I", artifact, 40, len(odd))
struct.pack_into(">I", artifact, 52, checksum(odd))
results = []
for owner_parity in (0, 1):
    env.owner = 0x500000 + owner_parity
    for version, data in ((1, env.art), (2, artifact)):
        f = Fixture(env, artifact=bytes(data))
        f.setup()
        art = env.addr("_nv_art")
        cached_source = u32(f.cpu, art + 12)
        assert cached_source == ARENA + source + version - 1
        assert (
            f.cpu.mem_read(cached_source, length) == original[source : source + length]
        )
        decode = env.addr("_nv_art_decode")
        assert u32(f.cpu, decode + 8) == cached_source + env.codec_offset
        assert f.call("_nv_art_game_c2p", (PRIMARY + 6, BITMAP, env.height, STACK)) == 1
        results.append(
            dict(owner_parity=owner_parity, version=version, load_bind_conversion=True)
        )

f = Fixture(env)
output = 0x7F0000
for at, size, value in (
    (4, 2, 0),
    (4, 2, 3),
    (4, 2, 65535),
    (32, 4, 0),
    (32, 4, 0xFFFFFFFF),
    (36, 4, 0xFFFFFFFF),
    (36, 4, 0xFFFFFFFE),
    (source, 1, 1),
):
    data = bytearray(odd)
    data[at : at + size] = value.to_bytes(size, "big")
    f.cpu.mem_write(ARENA, bytes(data))
    f.cpu.mem_write(output, bytes([0xA5]) * 44)
    assert f.call("_nv_art_validate", (ARENA, len(data), output)) == 0
    assert f.cpu.mem_read(output, 44) == bytes([0xA5]) * 44
    results.append(
        dict(rejected_offset=at, rejected_value=value, no_partial_publication=True)
    )
report = dict(
    pass_=True,
    cases=len(results),
    module_sha256=env.metadata["sha256"],
    fixtures=results,
)
(artifact_dir("art") / "payload-versions.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    json.dumps(
        dict(
            payload_version_cases=len(results),
            module_sha256=env.metadata["sha256"],
        )
    )
)
