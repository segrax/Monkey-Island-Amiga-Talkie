"""Build signed native PCM from local owned speech assets; GPL-3.0-or-later."""
import argparse
import hashlib
import json
from pathlib import Path
import struct

HEADER = 128
RATE = 22050


def gain_table(gain):
    if not 1 <= gain <= 8:
        raise ValueError('Gain outside1..8')
    values = []
    for value in range(256):
        sample = value - 128
        magnitude = abs(sample)
        limit = 128 if sample < 0 else 127
        scaled = magnitude * gain * limit // (limit + (gain - 1) * magnitude)
        values.append((-scaled if sample < 0 else scaled) & 255)
    return bytes(values)


def map_references(data):
    if data[:4] == b'MAT1':
        archive_size, count = struct.unpack_from('<II', data, 4)
        position = 12
    elif data[:4] == b'MAT2':
        if len(data) < 64 or struct.unpack_from('>HH', data, 4) != (1, 64):
            raise ValueError('InvalidMAT2header')
        archive_size, count = struct.unpack_from('>II', data, 8)
        position = struct.unpack_from('>I', data, 28)[0]
        if struct.unpack_from('>I', data, 32)[0] != len(data):
            raise ValueError('MAT2filebytes mismatch')
    else:
        raise ValueError('ExpectedMAT1orMAT2')
    if not 0 < count <= 50000 or position > len(data):
        raise ValueError('Invalidmapbounds')
    refs = set()
    for _ in range(count):
        if position + 2 > len(data):
            raise ValueError('Truncatedmap')
        length = struct.unpack_from('<H', data, position)[0]
        position += 2
        if not 0 < length < 2048 or position + length + 8 > len(data):
            raise ValueError('Invalidkeybounds')
        if b'\0' in data[position:position + length]:
            raise ValueError('NULmapkey')
        position += length
        ref = struct.unpack_from('<II', data, position)
        position += 8
        refs.add(ref)
    if position != len(data):
        raise ValueError('Trailingmapbytes')
    return archive_size, sorted(refs)


def voc_pcm(archive, offset, header_length):
    if not 8 <= header_length <= 132 or header_length & 1:
        raise ValueError('InvalidVCTLlength')
    if offset + header_length + 32 > len(archive):
        raise ValueError('OutofboundsVOC')
    if archive[offset:offset + 4] != b'VCTL' or struct.unpack_from('>I', archive, offset + 4)[0] != header_length:
        raise ValueError('VCTLreference mismatch')
    start = offset + header_length
    if archive[start:start + 20] != b'Creative Voice File\x1a':
        raise ValueError('MissingVOCsignature')
    data_offset, version, checksum = struct.unpack_from('<HHH', archive, start + 20)
    if data_offset < 26 or checksum != ((~version + 0x1234) & 65535):
        raise ValueError('InvalidVOCheader')
    block = start + data_offset
    if block + 6 > len(archive):
        raise ValueError('TruncatedVOCblock')
    length = int.from_bytes(archive[block + 1:block + 4], 'little')
    if archive[block] != 1 or length < 3 or archive[block + 5] != 0 or archive[block + 4] != 0xd3:
        raise ValueError('Expectednative22050HzPCM8VOC')
    pcm = block + 6
    size = length - 2
    if pcm + size >= len(archive) or archive[pcm + size] != 0:
        raise ValueError('MissingVOCterminator')
    return archive[pcm:pcm + size]


def build(archive_path, map_path, output_path, gain=4):
    if output_path.exists():
        raise ValueError('Refusingexisting output')
    archive, mapping = archive_path.read_bytes(), map_path.read_bytes()
    archive_size, refs = map_references(mapping)
    if archive_size != len(archive):
        raise ValueError('Maparchive mismatch')
    table = gain_table(gain)
    source_hash = hashlib.sha256(archive).digest()
    map_hash = hashlib.sha256(mapping).digest()
    data_offset = HEADER + 16 * len(refs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows, audit = [], []
    with output_path.open('xb') as target:
        target.write(bytes(data_offset))
        for offset, length in refs:
            raw = voc_pcm(archive, offset, length)
            converted = raw.translate(table)
            position = target.tell()
            target.write(converted)
            rows.append((offset, length, position, len(converted)))
            audit.append({'source_offset': offset, 'source_header_length': length,
                          'pcm_offset': position, 'pcm_bytes': len(converted),
                          'pcm_sha256': hashlib.sha256(converted).hexdigest()})
        file_bytes = target.tell()
        if file_bytes > 0x7fffffff:
            raise ValueError('Nativearchive exceeds signed32bitfilelimit')
        target.seek(0)
        target.write(struct.pack('>4sHH8I', b'NPC1', 1, HEADER, RATE, gain,
                                 len(archive), len(mapping), len(refs), HEADER,
                                 data_offset, file_bytes) + source_hash + map_hash + bytes(24))
        for row in rows:
            target.write(struct.pack('>4I', *row))
    # Independent full output reread: every mapped payload must equal the source LUT.
    with output_path.open('rb') as target:
        for row in rows:
            offset, length, position, size = row
            target.seek(position)
            if target.read(size) != voc_pcm(archive, offset, length).translate(table):
                raise ValueError('PCMverification mismatch')
    report = {'format': 'NPC1', 'version': 1, 'gain': gain, 'rate': RATE,
              'source_sha256': source_hash.hex(), 'map_sha256': map_hash.hex(),
              'source_bytes': len(archive), 'map_bytes': len(mapping),
              'clip_count': len(refs), 'file_bytes': file_bytes,
              'output_sha256': hashlib.sha256(output_path.read_bytes()).hexdigest(),
              'all_mapped_clips_byte_verified': True, 'clips': audit}
    output_path.with_suffix('.audit.json').write_text(json.dumps(report, indent=2))
    constants = '/* Generated source bindings; GPL-3.0-or-later. */\n'
    constants += '#define NPC_SOURCE_BYTES %dUL\n#define NPC_MAP_BYTES %dUL\n' % (len(archive), len(mapping))
    for name, digest in [('npc_source_sha', source_hash), ('npc_map_sha', map_hash)]:
        constants += 'static const unsigned char %s[32] = {%s};\n' % (name, ','.join(str(x) for x in digest))
    output_path.with_name('pcm_bindings.h').write_text(constants)
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive', type=Path, required=True)
    p.add_argument('--map', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--gain', type=int, default=4)
    a = p.parse_args()
    report = build(a.archive, a.map, a.output, a.gain)
    print(json.dumps({k: v for k, v in report.items() if k != 'clips'}, indent=2))
