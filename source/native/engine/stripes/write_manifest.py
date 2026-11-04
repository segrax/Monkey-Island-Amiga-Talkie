"""Add only the new stripe target/export to the frozen combined manifest."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('stripes')
ENGINE_BUILD = engine_build()
from pathlib import Path
import hashlib,json
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[1]
target=ENGINE_BUILD/'module'
source=ENGINE_BUILD/'scaling'
m=json.loads((source/'module.json').read_text());patch=json.loads((target/'Monkey_Talkie_Test.json').read_text());assert m['sha256']==patch['source_sha256']
m['sha256']=patch['sha256'];m['exports']['_stripe_decoder']={'hunk':9,'offset':0}
m['engine_patches'].append(patch['hook'])
m['engine_removed_original_relocations'].append({'source_hunk':0,'target_hunk':0,'offset':0x4dde})
generation=json.loads((BUILD/'generation.json').read_text())
m['engine_stripe_relax']=dict(source_module_sha256=patch['source_sha256'],kernel_hunk=9,kernel_bytes=generation['kernel_bytes'],kernel_sha256=patch['kernel_sha256'],original_bytes=424,shortened_branches=sum(b['new_size']<b['old_size'] for b in generation['branches']),extended_run_batching=generation['extended_run_batching'],batch_minimum_pixels=generation['batch_minimum_pixels'],appended_batch_bytes=generation['appended_batch_bytes'],all_nonbranch_bytes_exact=True,original_prefix_nonbranch_bytes_exact=True,original_body_retained=True,existing_jump_retargeted=True,extra_entry_jump=False,runtime_validation=False)
(target/'module.json').write_text(json.dumps(m,indent=2)+'\n')
print(m['sha256'])
