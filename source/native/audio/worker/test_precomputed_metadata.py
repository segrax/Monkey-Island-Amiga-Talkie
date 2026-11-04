"""Compiled strict-digest gating, exact binding, and unchanged generic fallback."""
from pathlib import Path
HERE = Path(__file__).resolve().parent
exec(compile((HERE / 'test_worker_metadata.py').read_text(), str(HERE / 'test_worker_metadata.py'), 'exec'))

data = (ROOT / 'data/prepared/21472/amiga-talkie.dat').read_bytes()
assert len(data) == 1156091
assert hashlib.sha256(data).hexdigest() == '1f4fe61ea18cb921d762049f87950df2ba758c2e1c1a827cbf8396874224aad5'
expected = hashlib.md5(data).digest()
fs[mapname] = data
call('_probe_map', mapaddr)
map_state, pcm_state = 0x609000, 0x609100


def states():
 cpu.mem_write(map_state, bytes(32)); cpu.mem_write(pcm_state, bytes(20))
 put(map_state + 12, 21472); put(map_state + 16, 198054609)
 put(map_state + 24, len(data)); put(map_state + 28, 1)
 put(pcm_state, 0x1111); put(pcm_state + 8, 4239); put(pcm_state + 12, 188709201)


def bind(prepared=1, status=1, gain=4, pcm=pcm_state):
 call('_probe_prepared', map_state, prepared, status, gain, pcm)
 return call('_probe_trusted')


states(); assert bind() == 1
map_reads = []


def audit(uc, pc, size, unused):
 if pc == symbols['_fread']:
  sp = uc.reg_read(R.UC_M68K_REG_A7); handle = get(sp + 16)
  if handle in handles and handles[handle][0] == mapname: map_reads.append(True)


cpu.hook_add(unicorn.UC_HOOK_CODE, audit)
prepare(); events.clear(); before = statcalls
assert request() == 1 and statcalls == before + 2 and not map_reads
strict_sidecar = fs[b'savegame._a_.talkie']
assert strict_sidecar[20:36] == expected
assert strict_sidecar[-16:] == hashlib.md5(strict_sidecar[:-16]).digest()
prepare(7); before = statcalls
assert request() == 1 and statcalls == before + 1 and not map_reads
# Every mutable filesystem identity component is still checked on every operation.
for field in ('disk', 'days', 'minute', 'tick'):
 identity[field] += 1; prepare(); assert request() == 0xfffffffe
 identity[field] -= 1
fs[mapname] += b'x'; prepare(); assert request() == 0xfffffffe
fs[mapname] = fs[mapname][:-1]
# A replacement between the two first-operation identity reads rejects the bind.
call('_probe_map', mapaddr); states(); assert bind() == 1
race_at = statcalls + 1
race_done = False


def race(uc, pc, size, unused):
 global race_done
 if pc == dosbase - 102 and statcalls == race_at and not race_done:
  identity['tick'] += 1; race_done = True


race_hook = cpu.hook_add(unicorn.UC_HOOK_CODE, race)
prepare(); assert request() == 0xfffffffe and race_done
cpu.hook_del(race_hook); identity['tick'] -= 1
call('_probe_map', mapaddr)
# Every strict gate independently rejects trusting a declared digest.
cases = 0
for arguments in ((0, 1, 4, pcm_state), (-1, 1, 4, pcm_state),
                  (1, 0, 4, pcm_state), (1, -1, 4, pcm_state),
                  (1, 2, 4, pcm_state), (1, 1, 2, pcm_state), (1, 1, 4, 0)):
 states(); assert bind(*arguments) == 0; cases += 1
for address, value in ((map_state + 12, 21471), (map_state + 16, 198054608),
                       (map_state + 24, len(data) - 1), (map_state + 28, 0),
                       (map_state + 28, 31), (pcm_state, 0),
                       (pcm_state + 8, 4238), (pcm_state + 12, 188709200)):
 states(); put(address, value); assert bind() == 0; cases += 1
states(); lockok = False; call('_probe_map', mapaddr); assert bind() == 0
lockok = True
# Marker-absent mode still hashes actual file bytes, independent of the constant.
fs[mapname] = b'generic mutable map with different bytes'
call('_probe_map', mapaddr); states(); assert bind(0) == 0
changed = True  # Disable the earlier test's one-time deliberate race hook.
prepare(); map_reads.clear(); assert request() == 1 and map_reads
assert fs[b'savegame._a_.talkie'][20:36] == hashlib.md5(fs[mapname]).digest()

report = {'status': 'PASS_UNIT_ONLY', 'worker_sha256': hashlib.sha256((HERE / 'VoiceServer_PreparedOnly').read_bytes()).hexdigest(),
          'actual_map_md5': expected.hex(), 'strict_zero_map_payload_reads': True,
          'strict_first_stat_checks': 2, 'cached_stat_checks': 1,
          'negative_readiness_cases': cases + 1, 'marker_absent_actual_hash_unchanged': True,
          'NMT1_binding_byte_identical_to_host_actual_hash': True,
          'per_operation_identity_mutation_rejected': True,
          'strict_first_operation_identity_race_rejected': True,
          'trust_model': 'Immutable installer-hash-verified package; no runtime map-body authentication.'}
(HERE / 'precomputed-metadata-validation.json').write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report))
