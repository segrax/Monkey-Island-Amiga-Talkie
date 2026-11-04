"""Reject unknown init bytes and any overlapping original relocation."""
import json
from patch import corrected
from paths import artifact_dir
raw=bytearray(0x1800);raw[0x1506:0x150c]=bytes.fromhex('284142902840')
result=corrected(bytes(raw),0,[0x1504,0x150a])
assert result[:0x1508] == raw[:0x1508] and result[0x1508:0x150a] == bytes.fromhex('4294') and result[0x150a:] == raw[0x150a:]
cases=1
for off in range(0x1506,0x150c):
    bad=bytearray(raw);bad[off]^=1
    try: corrected(bytes(bad),0,[])
    except ValueError: pass
    else: raise AssertionError(('unknown footprint accepted',off))
    cases+=1
for rel in range(0x1505,0x150a):
    try: corrected(bytes(raw),0,[rel])
    except ValueError: pass
    else: raise AssertionError(('overlap accepted',rel))
    cases+=1
try: corrected(result,0,[])
except ValueError: pass
else: raise AssertionError('double patch accepted')
cases+=1
(artifact_dir('music_init')/'patch-validation.json').write_text(json.dumps(dict(PASS=True,cases=cases,unknown_footprints_rejected=True,relocation_overlap_rejected=True,double_patch_rejected=True),indent=2)+'\n')
print('PCM PATCH GUARDS',cases)
