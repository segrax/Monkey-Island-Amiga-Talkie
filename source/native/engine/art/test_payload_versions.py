"""Check both source alignments through the linked resource loader and guards."""
from pathlib import Path
import json, struct

HERE = Path(__file__).resolve().parent
fixture = HERE / 'test_game.py'
ns = {'__file__': str(fixture), '__name__': 'payload_version_fixture'}
exec(compile(fixture.read_text().split('RESULTS=[]', 1)[0], str(fixture), 'exec'), ns)

def checksum(data):
    a = total = 65535
    for at in range(0, len(data), 2):
        a = (a + int.from_bytes(data[at:at + 2], 'big')) % 65535
        total = (total + a) % 65535
    return ((total or 65535) << 16) | (a or 65535)

original = ns['PAYLOAD']
source = ns['SOURCE']
length = ns['SOURCEBYTES']
columns = ns['WIDTH'] // 8
mask_bytes = columns * ((ns['HEIGHT'] + 7) // 8)
old_masks = (source + length + 1) & ~1
new_end = source + length + 1
odd = bytearray(original[:source]) + b'\0' + original[source:source + length]
odd += bytes(new_end & 1)
odd += original[old_masks:old_masks + mask_bytes]
odd += bytes(len(odd) & 1)
struct.pack_into('>H', odd, 4, 2)
struct.pack_into('>I', odd, 8, len(odd))
struct.pack_into('>I', odd, 32, source + 1)
artifact = bytearray(ns['ART'][:ns['OFF']]) + odd
struct.pack_into('>I', artifact, 24, len(artifact))
struct.pack_into('>I', artifact, 40, len(odd))
struct.pack_into('>I', artifact, 52, checksum(odd))
results = []
for owner_parity in (0, 1):
    ns['OWNER'] = 0x500000 + owner_parity
    for version, data in ((1, ns['ART']), (2, artifact)):
        f = ns['Fixture'](artifact=bytes(data))
        f.setup()
        art = ns['addr']('_nv_art')
        cached_source = ns['u32'](f.cpu, art + 12)
        assert cached_source == ns['ARENA'] + source + version - 1
        assert f.cpu.mem_read(cached_source, length) == original[source:source + length]
        decode = ns['addr']('_nv_art_decode')
        assert ns['u32'](f.cpu, decode + 8) == cached_source + ns['CODECOFF']
        assert f.call('_nv_art_game_c2p', (ns['PRIMARY'] + 6, ns['BITMAP'], ns['HEIGHT'], ns['STACK'])) == 1
        results.append(dict(owner_parity=owner_parity, version=version, load_bind_conversion=True))

f = ns['Fixture']()
output = 0x7f0000
for at, size, value in ((4, 2, 0), (4, 2, 3), (4, 2, 65535),
                         (32, 4, 0), (32, 4, 0xffffffff),
                         (36, 4, 0xffffffff), (36, 4, 0xfffffffe),
                         (source, 1, 1)):
    data = bytearray(odd)
    data[at:at + size] = value.to_bytes(size, 'big')
    f.cpu.mem_write(ns['ARENA'], bytes(data))
    f.cpu.mem_write(output, bytes([0xa5]) * 44)
    assert f.call('_nv_art_validate', (ns['ARENA'], len(data), output)) == 0
    assert f.cpu.mem_read(output, 44) == bytes([0xa5]) * 44
    results.append(dict(rejected_offset=at, rejected_value=value, no_partial_publication=True))
report = dict(pass_=True, cases=len(results), module_sha256=ns['META']['sha256'], fixtures=results)
(ns['artifact_dir']('art') / 'payload-versions.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(dict(payload_version_cases=len(results), module_sha256=ns['META']['sha256'])))
