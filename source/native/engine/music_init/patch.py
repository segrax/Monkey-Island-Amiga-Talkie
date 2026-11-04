"""Correct the original player's PCM status clear before loader fingerprinting."""
from pathlib import Path
import hashlib,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from paths import PROJECT_ROOT,engine_build,artifact_dir
sys.path.insert(0,str(PROJECT_ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader


def corrected(raw, code_offset, relocations):
    at = code_offset + 0x1508
    if raw[at-2:at+4] != bytes.fromhex('284142902840'):
        raise ValueError('Unknown original PCM initialization footprint')
    if any(off < 0x150a and 0x1508 < off+4 for off in relocations):
        raise ValueError('PCM initialization instruction overlaps a relocation')
    result = bytearray(raw)
    result[at:at+2] = bytes.fromhex('4294')
    assert len(result) == len(raw)
    assert all(i == at+1 for i,(a,b) in enumerate(zip(raw,result)) if a != b)
    return bytes(result)


def main():
    folder = engine_build()/'module'
    image = folder/'Monkey_Talkie_Test'
    raw = image.read_bytes()
    meta = json.loads((folder/'module.json').read_text())
    if hashlib.sha256(raw).hexdigest() != meta['sha256'] or 'tfmx_pcm_init_fix' in meta:
        raise ValueError('Module manifest mismatch or PCM initialization already corrected')
    reader = HunkReader()
    assert reader.read_file(str(image)) == 0 and reader.build_segments()
    code = next(h for h in reader.hunks if h.get('hunk_no') == 0 and 'data' in h)
    section = 0
    relocations = []
    for h in reader.hunks:
        section = h.get('hunk_no',section)
        if section == 0 and h['type_name'] == 'HUNK_ABSRELOC32':
            relocations.extend(off for offsets in h['reloc'].values() for off in offsets)
    result = corrected(raw,code['data_file_offset'],relocations)
    meta['sha256'] = hashlib.sha256(result).hexdigest()
    meta['tfmx_pcm_init_fix'] = dict(address=0x1508,size=2,expected='4290',replacement='4294',preceding='2841',following='2840',purpose='Clear first PCM status LONG at D1 via already initialized A4; preserve stale A0',runtime_validated=False)
    meta['patches'].append(dict(address=0x1508,size=2,expected='4290',replacement='4294',symbol='original_pcm_init_clear_A4',private_diagnostic=True))
    image.write_bytes(result)
    (folder/'module.json').write_text(json.dumps(meta,indent=2)+'\n')
    (artifact_dir('music_init')/'patch.json').write_text(json.dumps(dict(sha256=meta['sha256'],only_H0_word_1508_changed=True,relocations_and_other_bytes_identical=True),indent=2)+'\n')
    print('PCM INITIALIZATION',meta['sha256'])


if __name__ == '__main__':
    main()
