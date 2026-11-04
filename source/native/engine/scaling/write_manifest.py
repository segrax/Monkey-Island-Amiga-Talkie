"""Merge preserved native metadata with this isolated engine patch manifest."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('scaling')
ENGINE_BUILD = engine_build()
from pathlib import Path
import argparse,hashlib,json
HERE=Path(__file__).resolve().parent

def write(base_path,patch_path,output):
 m=json.loads(base_path.read_text());patch=json.loads(patch_path.read_text());assert m['sha256']==patch['source_sha256']
 m['sha256']=patch['sha256'];m['source_module_sha256']=patch['source_sha256'];m['original_relocations_retained']=False;m['original_relocations_outside_engine_patch_footprints_retained']=True
 m['engine_removed_original_relocations']=[dict(source_hunk=0,target_hunk=2,offset=o)for o in patch['removed_original_relocations']];m['engine_patches']=patch['hooks']
 m['engine_scaled_runs']=dict(kernel_hunk=patch['kernel_hunk'],prefix_hunk=patch['prefix_hunk'],prefix_bytes=patch['prefix_bytes'],prefix_memf='any',prefix_counter_bits=8,prefix_max_batch=255,prefix_row_bytes=257,table_sha256=patch['table_sha256'],threshold_source_pixels=9,cloned_kernel_entries=patch['entries'],prefix_sha256=hashlib.sha256((BUILD / 'scale_prefix.bin').read_bytes()).hexdigest(),runtime_validation=False)
 m['engine_short_RLE_packets']=dict(opcode_entries=256,unrolled_lengths_1_to_15=True,exact_column_residuals=True,runtime_validation=False)
 m.pop('engine_branch_relaxation',None)
 m['engine_accept_rows']=dict(rows=257,row_bytes=257,phase255_wrap_slot=True,signed_scale_clamped_0_256=True,runtime_validation=False)
 m['engine_run_specialization']=dict(color_classified_once_per_RLE=True,opaque_pixel_loop_without_color_check=True,transparent_pixel_loop_without_opaque_mask_work=True,relaxed_conditional_branches=True,runtime_validation=False)
 for name,off in patch['entries'].items():m['exports'][name]=dict(hunk=patch['kernel_hunk'],offset=off)
 output.write_text(json.dumps(m,indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',required=True,type=Path);p.add_argument('--patch',required=True,type=Path);p.add_argument('--output',required=True,type=Path);a=p.parse_args();write(a.base,a.patch,a.output)
