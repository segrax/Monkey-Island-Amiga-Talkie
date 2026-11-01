# SPDX-License-Identifier: GPL-3.0-or-later
"""Generate the actual map MD5 only after verifying the pinned host SHA256."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def generate(path):
    pins = json.loads((HERE / 'package-pins.json').read_text())
    data = path.read_bytes()
    if len(data) != pins['map_bytes'] or hashlib.sha256(data).hexdigest() != pins['map_sha256']:
        raise ValueError('Map differs from the frozen package')
    return ('/* Generated from host SHA-pinned MAT2; GPL-3.0-or-later. */\n'
            '#define NV_META_MAP_BYTES %dUL\n#define NV_META_MAP_COUNT %dUL\n'
            '#define NV_META_SOURCE_BYTES %dUL\n'
            'static const unsigned char nv_meta_map_md5[16] = {%s};\n' %
            (pins['map_bytes'], pins['map_entries'], pins['source_bytes'],
             ','.join(str(value) for value in hashlib.md5(data).digest())))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('map', type=Path)
    args = parser.parse_args()
    (HERE / 'metadata_bindings.h').write_text(generate(args.map))
