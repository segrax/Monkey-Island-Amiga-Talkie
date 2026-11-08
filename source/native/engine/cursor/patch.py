"""Keep the invisible Amiga pointer inside its allocated blank sprite tail."""
from pathlib import Path
import hashlib
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT, engine_build
sys.path.insert(0, str(PROJECT_ROOT / 'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader

ADDRESS = 0x15130
EXPECTED = bytes.fromhex('70102200')  # height=16; width=height
REPLACEMENT = bytes.fromhex('70017210')  # height=1; width=16


def corrected(raw, code_offset, relocations):
    at = code_offset + ADDRESS
    if raw[at:at + 4] != EXPECTED:
        raise ValueError('Unknown invisible-pointer instruction footprint')
    if any(offset < ADDRESS + 4 and ADDRESS < offset + 4 for offset in relocations):
        raise ValueError('Invisible-pointer instructions overlap a relocation')
    return raw[:at] + REPLACEMENT + raw[at + 4:]


def main():
    folder = engine_build() / 'module'
    image, manifest = folder / 'Monkey_Talkie_Test', folder / 'module.json'
    raw = image.read_bytes()
    meta = json.loads(manifest.read_text())
    if hashlib.sha256(raw).hexdigest() != meta['sha256'] or 'invisible_pointer_fix' in meta:
        raise ValueError('Module manifest mismatch or invisible pointer already corrected')
    reader = HunkReader()
    assert reader.read_file(str(image)) == 0 and reader.build_segments()
    code = next(h for h in reader.hunks if h.get('hunk_no') == 0 and 'data' in h)
    section, relocations = 0, []
    for h in reader.hunks:
        section = h.get('hunk_no', section)
        if section == 0 and h['type_name'] == 'HUNK_ABSRELOC32':
            relocations.extend(offset for offsets in h['reloc'].values() for offset in offsets)
    result = corrected(raw, code['data_file_offset'], relocations)
    meta['sha256'] = hashlib.sha256(result).hexdigest()
    meta['invisible_pointer_fix'] = dict(address=ADDRESS, size=4,
        expected=EXPECTED.hex(), replacement=REPLACEMENT.hex(),
        allocation_bytes=96, blank_offset=72, blank_bytes=24,
        height=1, width=16, sprite_bytes=12, amigaos_validated=False)
    meta['patches'].append(dict(address=ADDRESS, size=4,
        expected=EXPECTED.hex(), replacement=REPLACEMENT.hex(),
        symbol='original_invisible_pointer_dimensions', private_diagnostic=True))
    image.write_bytes(result)
    manifest.write_text(json.dumps(meta, indent=2) + '\n')
    print('INVISIBLE POINTER', meta['sha256'])


if __name__ == '__main__':
    main()
