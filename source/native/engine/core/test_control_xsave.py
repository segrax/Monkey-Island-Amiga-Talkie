"""68000 adapter ABI validation with deliberately clobbering mock C helpers."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import json
from pathlib import Path
import struct
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader
import unicorn
from unicorn import m68k_const as r

NAMES=['D%d'%n for n in range(8)]+['A%d'%n for n in range(8)]
REGS=[getattr(r,'UC_M68K_REG_'+name) for name in NAMES]
META=json.loads((BUILD / 'module.json').read_text())

def execute(path,bases,patch,flags,mocked,return_value=None,write_address=None, source_word=0x6789):
    reader=HunkReader();assert reader.read_file(str(path))==0 and reader.build_segments()
    cpu=unicorn.Uc(unicorn.UC_ARCH_M68K,unicorn.UC_MODE_BIG_ENDIAN)
    cpu.ctl_set_cpu_model(r.UC_CPU_M68K_M68000)
    for h in reader.hunks:
        if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS'):
            cpu.mem_map(bases[h['hunk_no']],(h['alloc_size']+4095)&~4095)
            if 'data' in h:cpu.mem_write(bases[h['hunk_no']],h['data'])
    source=None
    for h in reader.hunks:
        if 'hunk_no' in h:source=h['hunk_no']
        if h['type_name']=='HUNK_ABSRELOC32':
            for target,offsets in h['reloc'].items():
                for offset in offsets:
                    address=bases[source]+offset
                    cpu.mem_write(address,struct.pack('>I',int.from_bytes(cpu.mem_read(address,4),'big')+bases[target]))
    for address in (0,0x500000,0xdff000):cpu.mem_map(address,0x10000 if address==0x500000 else 0x1000)
    cpu.mem_map(0x600000,4096)
    cpu.mem_write(0x500000,struct.pack('>H',source_word)*0x8000)
    cpu.mem_write(0xdff01c,bytes.fromhex('6789'))
    cpu.reg_write(r.UC_M68K_REG_SR,flags)
    for i,reg in enumerate(REGS):cpu.reg_write(reg,0x500100+i*0x100)
    if return_value is not None:
        if patch['address'] in (0x96a,0xb0e):
            cpu.reg_write(r.UC_M68K_REG_D1,0x500200 | (64 if return_value else 0))
        else:cpu.reg_write(r.UC_M68K_REG_D0,return_value)
    cpu.reg_write(r.UC_M68K_REG_A4,bases[2])
    if write_address is not None:
        page = write_address & ~4095
        if not any(begin <= write_address <= end for begin,end,permissions in cpu.mem_regions()):
            cpu.mem_map(page, 4096)
        cpu.mem_write(write_address, bytes.fromhex('6789') * 8)
        cpu.reg_write(r.UC_M68K_REG_A4,write_address)
    cpu.reg_write(r.UC_M68K_REG_A7,0x50f000)
    address,size=patch['address'],patch['size']
    start=bases[0]+address; stop=start+size
    if patch.get('jump'):stop=bases[0]+patch['continuation']
    if patch.get('terminal'):
        stop=0x600000
        if address==0xd5c:cpu.reg_write(r.UC_M68K_REG_A1,stop)
        if address==0x5482:cpu.mem_write(0x50f008,struct.pack('>I',stop))
        else:
            cpu.reg_write(r.UC_M68K_REG_A5,0x50f020)
            cpu.mem_write(0x50f020,struct.pack('>II',0x500d00,stop))
    if address in (0x84a,0xd5c):
        cpu.mem_write(cpu.reg_read(r.UC_M68K_REG_A5)+0xc0,struct.pack('>H',return_value))
    if mocked:
        helpers={}
        for name,entry in META['exports'].items():
            if entry['hunk']==4 and name.startswith(('_nv_definition_','_nv_driver_','_nv_dialogue_','_nv_resource_','_nv_conversion_','_nv_metadata_')):
                pc=bases[entry['hunk']]+entry['offset'];helpers[pc]=name
                cpu.mem_write(pc,bytes.fromhex('4e75'))
        def callback(uc,pc,size,userdata):
            if pc not in helpers:return
            name=helpers[pc];sp=uc.reg_read(r.UC_M68K_REG_A7)
            arg=lambda off:int.from_bytes(uc.mem_read(sp+off,4),'big')
            if name=='_nv_driver_control':
                assert arg(4) in (0,1,2)
                destination=(0xdff096,0xdff09a,0xdff09c)[arg(4)]
                uc.mem_write(destination,struct.pack('>H',arg(8)&65535))
            elif name in ('_nv_driver_install','_nv_driver_restore'):
                uc.mem_write(0x70,struct.pack('>I',arg(4)))
            elif name=='_nv_driver_clear_volume':uc.mem_write(0xdff0a8,b'\0\0')
            elif name=='_nv_resource_begin':assert arg(4)==0x6789 and arg(8)==0x67896789
            elif name in ('_nv_resource_clear','_nv_dialogue_program'):assert arg(4)==0x6789
            elif name=='_nv_resource_mutate':assert arg(4)==0x100
            elif name=='_nv_conversion_begin':assert arg(4)==0x67896789
            elif name=='_nv_metadata_save':assert return_value==1 and arg(4)==0x800
            elif name=='_nv_metadata_load':assert return_value==1 and arg(4)==0x6789
            for reg in (r.UC_M68K_REG_D0,r.UC_M68K_REG_D1,r.UC_M68K_REG_A0,r.UC_M68K_REG_A1):
                uc.reg_write(reg,0xdead0000+reg)
            uc.reg_write(r.UC_M68K_REG_D0,0 if name=='_nv_dialogue_display' else 0x6789)
            uc.reg_write(r.UC_M68K_REG_SR,flags^31)
        cpu.hook_add(unicorn.UC_HOOK_CODE,callback)
    try:
        cpu.emu_start(start,stop,count=500)
    except unicorn.UcError:
        print('FAILED',hex(address),flags,'mocked',mocked,'pc',hex(cpu.reg_read(r.UC_M68K_REG_PC)))
        raise
    assert cpu.reg_read(r.UC_M68K_REG_PC)==stop
    # Materialize Unicorn's lazy CCR through a real 68000 MOVE SR instruction.
    # reg_read(SR) alone can expose stale pre-ADDQ flags at this boundary.
    cpu.mem_write(0x600100,bytes.fromhex('40f900600200'))
    cpu.emu_start(0x600100,0x600106,count=1)
    result=[cpu.reg_read(reg) for reg in REGS]+[int.from_bytes(cpu.mem_read(0x600200,2),'big')]
    if write_address is not None:
        result.append(bytes(cpu.mem_read(write_address,16)).hex())
        result.append(bytes(cpu.mem_read(0xdff0a0,64)).hex())
    # Prologue saves registers into stack; compare its observable frame as well.
    if patch.get('jump') and patch['expected'].startswith('4e55'):
        sp=cpu.reg_read(r.UC_M68K_REG_A7)
        saved=16 if address==0xc540 else 12 if address==0xcf8a else 8 if address in (0xdcee,0x5488) else 12 if address==0x9a34 else 16 if address==0xccc2 else 4 if address in (0xe286,0xcc84) else 20
        result.append(bytes(cpu.mem_read(sp,saved)).hex())
        result.append(bytes(cpu.mem_read(0x50effc,4)).hex())
    return result

CONTROL_ADDRESSES={0x30e,0xaae,0xb3e,0x102e,0x10ac,0x9a4,0xb24,0xbbe,0xbf6,0x1026,0x108c,0x16ac,0x170c,0x9ac,0xb2c,0xbfe,0x1084}
checks=0
for bases in ((0x100000,0x20000,0x200000,0x300000,0x310000,0x320000,0x330000),
              (0x180000,0x40000,0x280000,0x380000,0x390000,0x3a0000,0x3b0000)):
    for patch in META['patches']:
        if patch['address'] not in CONTROL_ADDRESSES: continue
        for flags in range(32):
            for source_word in (0,0x8000,0xffff,0x4080,0x0201):
                expected=execute(ROOT/'data/original/Monkey_Island',bases[:3],patch,flags,False,source_word=source_word)
                actual=execute(BUILD / 'Monkey_Talkie_Test',bases,patch,flags,True,source_word=source_word)
                assert actual==expected,(hex(patch['address']),flags,hex(source_word),expected,actual)
                checks+=1
result={'checks':checks,'control_sites':len(CONTROL_ADDRESSES),'all_32_ccr_values':True,
        'relocation_layouts':2,'source_words':[0,0x8000,0xffff,0x4080,0x0201],
        'all_registers_stack_and_final_ccr_match_original':True,'clobbering_mock_helpers':True,
        'module_sha256':META['sha256'],'scope':'Control wrapper ABI/CCR proof; actual helper behavior unchanged'}
(BUILD / 'control-xsave-validation.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result))
