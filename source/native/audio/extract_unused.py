"""Extract the audited unmatched recordings as unchanged PCM WAV files."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import wave

from build_pcm import voc_pcm

ROOT = Path(__file__).resolve().parents[1]


def extract(output, refresh_index=False):
    output = output.resolve()
    if not output.is_relative_to(ROOT / 'build') or (output.exists() and not refresh_index):
        raise ValueError('Choose a new output directory beneath build/, or refresh an existing index')
    if refresh_index and not (output / 'extraction.json').is_file():
        raise ValueError('Index refresh requires an existing extraction')
    audit = json.loads((ROOT / 'docs/unused-audio.json').read_text())
    binding = json.loads((ROOT / 'data/prepared/21472/native-voice.audit.json').read_text())
    archive = (ROOT / 'data/original/monster.sou').read_bytes()
    if hashlib.sha256(archive).hexdigest() != binding['source_sha256']:
        raise ValueError('Source archive hash mismatch')
    if audit['map_sha256'] != binding['map_sha256']:
        raise ValueError('Audit/map binding mismatch')
    notes = json.loads((ROOT / 'docs/audio-listening-notes.json').read_text())
    if notes['source_sha256'] != binding['source_sha256']:
        raise ValueError('Listening notes/archive binding mismatch')
    output.mkdir(parents=True, exist_ok=refresh_index)
    rows, playlist, entries = [], ['#EXTM3U'], []
    for clip in audit['unused_records']:
        offset, length = clip['offset'], clip['header_length']
        pcm = voc_pcm(archive, offset, length)
        captions = list(dict.fromkeys(o.get('text', '').strip()
                        for o in clip['source_occurrences'] if o.get('text', '').strip()))
        caption = ' | '.join(captions) or '[no readable caption]'
        dynamic = any(o.get('dynamic') for o in clip['source_occurrences'])
        slug = re.sub(r'[^a-z0-9]+', '-', caption.lower()).strip('-')[:65]
        name = f'{offset:09d}_{length}_{slug}.wav'
        path = output / name
        # VOC PCM here is unsigned 8-bit mono at 22050 Hz, also native WAV PCM.
        # Copy samples directly: no gain, resampling, filtering or recompression.
        if not refresh_index:
            with wave.open(str(path), 'wb') as wav:
                wav.setparams((1, 1, 22050, 0, 'NONE', 'not compressed'))
                wav.writeframes(pcm)
        with wave.open(str(path), 'rb') as wav:
            if (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) != (1, 1, 22050):
                raise ValueError('WAV format mismatch')
            if wav.readframes(wav.getnframes()) != pcm:
                raise ValueError('WAV samples differ from source')
        seconds = len(pcm) / 22050
        note = dict(next((r for r in notes['ranges']
                         if r['first_offset'] <= offset <= r['last_offset']), {}))
        note.update(notes['clips'].get(str(offset), {}))
        label = note.get('heard_text', caption)
        if dynamic and not note.get('heard_text'):
            label += ' [dynamic caption]'
        if note:
            label = (note.get('speaker') or note.get('category', '')) + ': ' + label
            label += ' [user listening review]'
        rows.append(f'<tr><td>{offset}/{length}</td><td>{seconds:.2f}s</td>'
                    f'<td>{html.escape(label)}</td><td><audio controls preload="none" '
                    f'src="{name}"></audio> <a href="{name}">WAV</a></td></tr>')
        playlist += [f'#EXTINF:{seconds:.3f},{label}', name]
        entries.append({'file': name, 'source_offset': offset, 'header_length': length,
                        'caption': caption, 'dynamic_caption': dynamic, 'seconds': seconds,
                        'listening_note': note or None,
                        'pcm_sha256': hashlib.sha256(pcm).hexdigest()})
    (output / 'index.html').write_text('<!doctype html><meta charset="utf-8">'
        '<title>Unmatched Monkey Island recordings</title>'
        '<style>body{font:16px system-ui;margin:2em}td{padding:.5em;border-bottom:1px solid #ddd}'
        'table{border-collapse:collapse}audio{width:260px}</style>'
        f'<h1>{len(entries)} recordings absent from the Amiga map</h1>'
        '<p>Original unsigned 8-bit mono PCM at 22050 Hz, copied without audio changes. '
        'Captions come from Ultimate Talkie scripts; they are not new transcriptions. '
        'Identifications and transcripts supplied by the user are labelled as listening reviews. '
        'Empty and dynamic captions may not describe all the spoken words.</p>'
        '<p><a href="all-clips.m3u">Playlist for an external player</a></p>'
        '<table><tr><th>Source clip</th><th>Duration</th><th>Caption</th><th>Listen</th></tr>'
        + ''.join(rows) + '</table>', encoding='utf-8')
    (output / 'all-clips.m3u').write_text('\n'.join(playlist) + '\n', encoding='utf-8')
    (output / 'extraction.json').write_text(json.dumps({
        'source_sha256': binding['source_sha256'], 'map_sha256': audit['map_sha256'],
        'clips': entries, 'all_wav_samples_byte_identical_to_source': True}, indent=2) + '\n')
    print(f'PASS: {len(entries)} WAVs; every sample verified against source.\n{output / "index.html"}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'build/listening/unused-audio')
    parser.add_argument('--refresh-index', action='store_true', help='Update labels, verify and preserve existing WAVs')
    args = parser.parse_args()
    extract(args.output, args.refresh_index)
