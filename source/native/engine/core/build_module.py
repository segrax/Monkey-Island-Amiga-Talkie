"""Build relocation-aware native adapters; never modify original game files."""
from pathlib import Path as _EnginePath
import sys as _engine_sys
_engine_sys.pycache_prefix = str(_EnginePath(__file__).resolve().parents[2] / "build/python-cache")
_engine_sys.path.insert(0, str(_EnginePath(__file__).resolve().parents[1]))
from paths import artifact_dir, engine_build
BUILD = artifact_dir('core')
ENGINE_BUILD = engine_build()
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = Path(os.environ.get('NATIVE_PROJECT_ROOT', str(HERE.parents[1]))).resolve()
WORKER = ROOT / 'audio/worker'
sys.path.insert(0, str(ROOT / 'tools/python'))
from amitools.binfmt.hunk.HunkReader import HunkReader

ORIGINAL = ROOT / 'data/original/Monkey_Island'
EXPECTED = '1ac24b2fa0e4f9e454a5523bb57e48496805e8c4fa3dfa07efb6855a1bfa7725'
TOOLS = Path('D:/Tools/amiga-dev')
ENV = dict(os.environ, VBCC=str(TOOLS/'targets/m68k-amigaos'), PATH=str(TOOLS/'bin') + os.pathsep + os.environ['PATH'])
WITH_METADATA = '--with-metadata' in sys.argv
WITH_DUCKING = '--duck-music' in sys.argv
HYBRID_MIX = '--hybrid-mix' in sys.argv
STEREO_MIX = '--stereo-mix' in sys.argv or HYBRID_MIX
if STEREO_MIX and WITH_DUCKING:
    raise SystemExit('Stereo mixing uses fixed headroom; do not enable music ducking')
if WITH_METADATA and '--without-metadata' in sys.argv:
    raise SystemExit('Choose either --with-metadata or --without-metadata')

SAVE = '''
 movem.l d0-d7/a0-a6,-(sp)
 seq d0
 smi d1
 scs d2
 svs d3
 moveq #0,d4
 addx.b d4,d4
 andi.w #1,d0
 andi.w #1,d1
 andi.w #1,d2
 andi.w #1,d3
 lsl.w #4,d4
 lsl.w #2,d0
 lsl.w #3,d1
 lsl.w #1,d3
 or.w d0,d4
 or.w d1,d4
 or.w d2,d4
 or.w d3,d4
 move.w d4,-(sp)
 movem.l 2(sp),d0-d7/a0-a6
'''
CONTROL_SAVE = '''
 movem.l d0-d7/a0-a6,-(sp)
 moveq #0,d0
 addx.b d0,d0
 lsl.w #4,d0
 move.w d0,-(sp)
'''
RESTORE = ' move.w (sp)+,ccr\n movem.l (sp)+,d0-d7/a0-a6\n'

def run(args):
    subprocess.run([str(a) for a in args], cwd=BUILD, env=ENV, check=True)

def read(path):
    reader = HunkReader()
    assert reader.read_file(str(path)) == 0 and reader.build_segments()
    return reader

def generate():
    data = ORIGINAL.read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED
    original = read(ORIGINAL)
    code = next(h['data'] for h in original.hunks if h['type_name'] == 'HUNK_CODE')
    lines = [' section text,code']
    imports = ['nv_driver_start', 'nv_driver_install', 'nv_driver_restore', 'nv_driver_control',
               'nv_driver_intena', 'nv_driver_clear_volume', 'nv_driver_irq',
               'nv_dialogue_capture','nv_dialogue_segment','nv_dialogue_display','nv_dialogue_stop','nv_dialogue_program',
               'nv_definition_begin','nv_resource_begin','nv_resource_end','nv_resource_clear','nv_resource_mutate','nv_conversion_begin','nv_conversion_end',
               'nv_game_skip_script','nv_driver_write','nv_driver']
    if WITH_DUCKING or STEREO_MIX: imports += ['nv_driver_volume','nv_driver_clear_native_volume']
    if STEREO_MIX: imports += ['nv_stereo_bank']
    if WITH_METADATA: imports += ['nv_metadata_save','nv_metadata_load_begin','nv_metadata_load']
    lines += [' xref _' + name for name in imports]
    patches = []
    for address,size,offset in ((0xb6a,6,0),(0xe82,6,0),(0xea0,10,0),
        (0xac2,6,4),(0xb90,8,4),(0xba2,6,4),(0xe8c,6,4),(0xeaa,6,4),
        (0x84a,10,6),(0x8ae,6,6),(0xac8,6,6),(0xd5c,12,6),(0xd76,6,6),(0xdc4,6,6),
        (0x96a,6,8),(0xb0e,6,8)):
        name='_nv_native_write_%x'%address
        lines += [' xdef '+name,name+':']
        if address in (0x84a,0xd5c): lines += [' tst.w $c0(a5)',' bne .skip_write']
        if STEREO_MIX:
            for channel in range(4):
                lines += [' cmpa.l #_nv_stereo_bank+%d,a4'%(16*channel),' beq .tracked_write']
            lines += [' bra .fast_write','.tracked_write:']
        else:
            lines += [' cmpa.l #_nv_driver+72,a4',' bne .fast_write']
        if address in (0x96a,0xb0e):
            lines += [' btst #6,d1',' bne .volume',' add.w d0,d0',' add.w d0,d0',
                      ' mulu.w d1,d0',' lsr.w #8,d0','.volume:',' move.w d0,8(a4)']
            continuation=0x97c if address==0x96a else 0xb20
        elif address in (0x84a,0xd5c):
            lines += [' move.w d0,6(a4)']
            continuation=0x854 if address==0x84a else 0xd68
        else:
            replay=4 if address in (0x8ae,0xd62) else size
            lines += [' dc.b '+','.join('$%02x'%b for b in code[address:address+replay])]
            continuation=0x8c8 if address==0x8ae else address+size
        lines += [SAVE,' move.l #%d,-(sp)'%offset,' move.l a4,-(sp)',
                  ' jsr _nv_driver_write',' lea 8(sp),sp',RESTORE]
        lines += [' bra .write_done','.fast_write:']
        if address in (0x96a,0xb0e):
            lines += [' btst #6,d1',' bne .fast_volume',' add.w d0,d0',' add.w d0,d0',
                      ' mulu.w d1,d0',' lsr.w #8,d0','.fast_volume:',' move.w d0,8(a4)']
        elif address in (0x84a,0xd5c):
            lines += [' move.w d0,6(a4)']
        else:
            replay=4 if address==0x8ae else size
            lines += [' dc.b '+','.join('$%02x'%b for b in code[address:address+replay])]
        lines += ['.write_done:']
        if address in (0x84a,0xd5c): lines += ['.skip_write:']
        if address==0xd5c: lines += [' jmp (a1)']
        else: lines += [' xdef _nv_continue_'+name,'_nv_continue_'+name+':',' jmp $%x.l'%continuation]
        patches.append(dict(address=address,size=size,symbol=name,jump=True,
                            continuation=continuation,terminal=address==0xd5c,
                            expected=code[address:address+size].hex()))
    for address,continuation in ((0x96a,0x97c),(0xb0e,0xb20)):
        if not WITH_DUCKING: continue
        name='_nv_volume_%x'%address
        lines.extend([' xdef '+name,name+':',' btst #6,d1',' bne .volume',
                      ' add.w d0,d0',' add.w d0,d0',' mulu.w d1,d0',' lsr.w #8,d0','.volume:',SAVE,
                      ' moveq #0,d1',' move.w d0,d1',' move.l d1,-(sp)',' move.l a4,-(sp)',
                      ' jsr _nv_driver_volume',' lea 8(sp),sp',RESTORE,
                      ' move.w d0,-(sp)',' lea 2(sp),sp',
                      ' xdef _nv_continue_'+name,'_nv_continue_'+name+':',' jmp $%x.l'%continuation])
        patches.append(dict(address=address,size=6,symbol=name,jump=True,continuation=continuation,expected=code[address:address+6].hex()))
    for channel,address in ((1,0x109a),(2,0x10a0),(3,0x10a6)):
        if not (WITH_DUCKING or STEREO_MIX): continue
        name='_nv_clear_volume_%d'%channel
        lines.extend([' xdef '+name,name+':',SAVE,' move.l #%d,-(sp)'%channel,
                      ' jsr _nv_driver_clear_native_volume',' lea 4(sp),sp',RESTORE,
                      ' clr.w -(sp)',' lea 2(sp),sp',' rts'])
        patches.append(dict(address=address,size=6,symbol=name,expected=code[address:address+6].hex()))
    def wrapper(address, source, helper, kind=None, long=False, size=8):
        name = 'nv_patch_%04x' % address
        if kind is not None:
            assert helper == 'nv_driver_control' and (source.startswith('#') or '(' in source)
        lines.extend([' xdef _'+name, '_'+name+':', CONTROL_SAVE if kind is not None else SAVE])
        if long:
            lines.append(' move.l '+source+',-(sp)')
        else:
            lines.extend([' clr.l -(sp)', ' move.w '+source+',2(sp)'])
        if kind is not None:
            lines.append(' move.l #%d,-(sp)' % kind)
        lines.extend([' jsr _'+helper, ' lea %d(sp),sp' % (8 if kind is not None else 4), RESTORE,
                      ' move.%s %s,-(sp)' % ('l' if long else 'w', source),
                      ' lea %d(sp),sp' % (4 if long else 2), ' rts'])
        patches.append(dict(address=address, size=size, symbol='_'+name, expected=code[address:address+size].hex()))
    sources = {
        0x30e:('$70(a6)',0), 0xaae:('$52(a5)',0), 0xb3e:('$50(a5)',0),
        0x102e:('$52(a5)',0),0x10ac:('#$f',0),
        0x9a4:('$112(a5)',1),0xb24:('$112(a5)',1),0xbbe:('$110(a5)',1),
        0xbf6:('$112(a5)',1),0x1026:('$112(a5)',1),0x108c:('#$780',1),
        0x16ac:('#$4780',1),0x170c:('$a(a6)',1),
        0x9ac:('$112(a5)',2),0xb2c:('$112(a5)',2),0xbfe:('$112(a5)',2),0x1084:('#$780',2)}
    for address,(source,kind) in sources.items():
        wrapper(address,source,'nv_driver_control',kind)
    for address in (0x1574,0x1696):
        wrapper(address,'a4','nv_driver_install',long=True,size=6)
    wrapper(0x16c4,'$32(a6)','nv_driver_restore',long=True)
    for address,helper in ((0x1094,'nv_driver_clear_volume'),(0x1668,'nv_driver_intena')):
        name = '_nv_patch_%04x' % address
        lines.extend([' xdef '+name,name+':',SAVE,' jsr _'+helper])
        if address == 0x1668:
            lines.append(' move.w d0,$a(a6)')
        lines.extend([RESTORE,' move.w $a(a6),-(sp)' if address==0x1668 else ' clr.w -(sp)', ' lea 2(sp),sp',' rts'])
        patches.append(dict(address=address,size=8 if address==0x1668 else 6,symbol=name,expected=code[address:address+(8 if address==0x1668 else 6)].hex()))
    # Replay only complete, verified instructions; external continuation relocation
    # is generated after linking, rather than relying on an installed load address.
    for address,size,name,helper,expected,hold in (
        (0x1c5c,8,'entry','nv_driver_start','4e55fff848e72710',False),
        (0xdcee,8,'capture','nv_dialogue_capture','4e55fffc48e72100',False),
        (0xdddc,8,'display','nv_dialogue_display','4e55fff848e73910',True),
        (0xe158,6,'stop','nv_dialogue_stop','2f02422c59f7',False)):
        assert code[address:address+size].hex() == expected
        lines.extend([' xdef _nv_'+name,'_nv_'+name+':',SAVE,' jsr _'+helper])
        if hold:
            lines.extend([' tst.l d0',' beq .proceed',RESTORE,' rts','.proceed:'])
        lines.extend([RESTORE,' dc.b '+','.join('$%02x'%v for v in code[address:address+size]),
                      ' xdef _nv_continue_'+name,'_nv_continue_'+name+':',' jmp $%x.l'%(address+size)])
        patches.append(dict(address=address,size=size,symbol='_nv_'+name,jump=True,
                            continuation=address+size,expected=expected))
    lines.extend([' xdef _nv_segment','_nv_segment:',SAVE,' jsr _nv_dialogue_segment',RESTORE,
                  ' move.w $59fa(a4),$59f8(a4)',' rts'])
    patches.append(dict(address=0xdf42,size=6,symbol='_nv_segment',expected='396c59fa59f8'))
    address=0x97c0
    expected='4e55fff448e73130'
    assert code[address:address+8].hex()==expected
    lines.extend([' xdef _nv_program','_nv_program:',SAVE,' moveq #0,d0',' move.w 66(sp),d0',
                  ' move.l d0,-(sp)',' jsr _nv_dialogue_program',' lea 4(sp),sp',RESTORE,
                  ' dc.b '+','.join('$%02x'%v for v in code[address:address+8]),
                  ' xdef _nv_continue_program','_nv_continue_program:',' jmp $97c8.l'])
    patches.append(dict(address=address,size=8,symbol='_nv_program',jump=True,continuation=address+8,expected=expected))
    address=0x9a34
    expected=code[address:address+8].hex()
    lines.extend([' xdef _nv_start_script','_nv_start_script:',SAVE,
                  ' moveq #0,d0',' move.w 66(sp),d0',' move.l d0,-(sp)',
                  ' jsr _nv_game_skip_script',' lea 4(sp),sp',' tst.l d0',' beq .start',
                  RESTORE,' rts','.start:',RESTORE,
                  ' dc.b '+','.join('$%02x'%v for v in code[address:address+8]),
                  ' xdef _nv_continue_start_script','_nv_continue_start_script:',' jmp $9a3c.l'])
    patches.append(dict(address=address,size=8,symbol='_nv_start_script',jump=True,continuation=address+8,expected=expected))
    # These entry/exit instructions have no PC-relative operands.
    for address,size,name,helper,arguments,terminal in (
        (0xc540,8,'verb_definition','nv_definition_begin',[],False),
        (0xc9c0,8,'string_definition','nv_definition_begin',[],False),
        (0xcf8a,8,'actor_definition','nv_definition_begin',[],False),
        (0xccc2,8,'resource_begin','nv_resource_begin',
         [' move.l 68(sp),-(sp)',' moveq #0,d0',' move.w 70(sp),d0',' move.l d0,-(sp)'],False),
        (0xcda2,8,'resource_end','nv_resource_end',[],False),
        (0xcc84,6,'resource_clear','nv_resource_clear',
         [' moveq #0,d0',' move.w 66(sp),d0',' move.l d0,-(sp)'],False),
        (0xca7c,8,'resource_mutate','nv_resource_mutate',
         [' moveq #0,d1',' move.w d0,d1',' move.l d1,-(sp)'],False),
        (0xe286,6,'conversion_begin','nv_conversion_begin',[' move.l 66(sp),-(sp)'],False),
        (0x5482,6,'save_return','nv_metadata_save',
         [' moveq #0,d0',' move.w d7,d0',' move.l d0,-(sp)'],True),
        (0x5488,8,'load_begin','nv_metadata_load_begin',[],False),
        (0x5632,8,'load_return','nv_metadata_load',
         [' moveq #0,d0',' move.w 8(a5),d0',' move.l d0,-(sp)'],True),
        (0xe348,8,'conversion_end','nv_conversion_end',[],True)):
        if not WITH_METADATA and helper.startswith('nv_metadata_'): continue
        name='_nv_hook_'+name
        # Signatures are recorded into the manifest and verified against the pinned SHA.
        expected=code[address:address+size].hex()
        lines.extend([' xdef '+name,name+':',SAVE])
        if address in (0x5482,0x5632):
            lines.extend([' cmpi.l #1,d0',' bne .metadata_done'])
        lines.extend(arguments+[' jsr _'+helper])
        if arguments:
            lines.append(' lea %d(sp),sp'%(8 if helper=='nv_resource_begin' else 4))
        if address in (0x5482,0x5632): lines.append('.metadata_done:')
        lines.extend([RESTORE,' dc.b '+','.join('$%02x'%v for v in code[address:address+size])])
        if not terminal:
            lines.extend([' xdef _nv_continue_'+name,'_nv_continue_'+name+':',' jmp $%x.l'%(address+size)])
        patches.append(dict(address=address,size=size,symbol=name,jump=True,continuation=address+size,
                            terminal=terminal,expected=expected))
    lines.extend([' xdef _nv_irq','_nv_irq:',' movem.l d0-d7/a0-a6,-(sp)',
                  ' ori.w #$0700,sr',' jsr _nv_driver_irq',' movem.l (sp)+,d0-d7/a0-a6',' rte'])
    lines.extend([' xdef _nv_zero_output','_nv_zero_output:',
                  ' move.l 4(sp),a0',' moveq #0,d0',' move.w 10(sp),d0',' beq .done',
                  ' move.l a0,d1',' btst #0,d1',' beq .words',' clr.b (a0)+',' subq.w #1,d0',
                  '.words:',' move.w d0,d1',' lsr.w #2,d1',' beq .bytes',' subq.w #1,d1',
                  '.long:',' clr.l (a0)+',' dbra d1,.long',
                  '.bytes:',' andi.w #3,d0',' beq .done',' subq.w #1,d0',
                  '.byte:',' clr.b (a0)+',' dbra d0,.byte','.done:',' rts'])
    lines += (ROOT / 'audio/word-copy-output/copy_output.s').read_text().splitlines()[2:]
    for name,lvo in (('nv_disable_interrupts',-120),('nv_enable_interrupts',-126)):
        lines += [' xdef _'+name,'_'+name+':',' move.l a6,-(sp)',' move.l 4.w,a6',
                  ' jsr %d(a6)'%lvo,' move.l (sp)+,a6',' rts']
    for name,body in {
        'nv_alloc_chip':[' move.l 8(sp),d0',' move.l #$10003,d1',' move.l 4.w,a6',' jsr -198(a6)'],
        'nv_free_chip':[' move.l 8(sp),a1',' move.l 12(sp),d0',' move.l 4.w,a6',' jsr -210(a6)'],
        'nv_signal_worker':[' move.l 8(sp),a1',' move.l 12(sp),d0',' move.l 4.w,a6',' jsr -324(a6)']
    }.items():
        lines.extend([' xdef _'+name,'_'+name+':',' move.l a6,-(sp)']+body+[' move.l (sp)+,a6',' rts'])
    (BUILD / 'wrappers.s').write_text('\n'.join(lines)+'\n')
    (BUILD / 'patches.json').write_text(json.dumps(patches,indent=2)+'\n')

def generate_hybrid_tables():
    # The existing unsigned gain counter makes negative products wrap before
    # division; their signed-byte result equals floor(product / 64). Preserve
    # that rounding, followed separately by the final arithmetic half.
    signed = lambda n: n if n < 128 else n - 256
    gain = lambda n, v: signed(n) * v // 64
    tables = {
        'nv_amplitude': bytes(gain(n,v) & 255 for v in range(65) for n in range(256)),
        'nv_half_amplitude': bytes((gain(n,v) >> 1) & 255 for v in range(65) for n in range(256)),
        'nv_speech_words': b''.join(struct.pack('>H', (gain(n,v) & 255) << 8) for v in range(65) for n in range(256)),
        'nv_average': bytes(((signed(((i + 32768) & 65535) >> 8) + signed(i & 255)) >> 1) & 255 for i in range(65536)),
    }
    # Immutable tables share the existing read-only assembly section.
    lines = [' section text,code']
    for name, data in tables.items():
        (BUILD / (name + '.bin')).write_bytes(data)
        lines += [' even', ' xdef _' + name, '_' + name + ':', ' incbin "' + name + '.bin"']
    (BUILD / 'hybrid_tables.s').write_text('\n'.join(lines) + '\n')


def main():
    generate()
    objects = ['paula_mix','native_timeline','native_driver','game_speech','native_provenance']
    if WITH_METADATA: objects.append('native_metadata')
    for name in objects:
        run([TOOLS/'bin/vc.exe','+'+str(ROOT/'audio/kick13.cfg'),'-c','-O2','-cpu=68000']+
            (['-DNV_MUSIC_DUCK'] if WITH_DUCKING else [])+['-I'+str(HERE),'-I'+str(WORKER),HERE/(('hybrid_driver.c' if HYBRID_MIX else 'stereo_driver.c') if STEREO_MIX and name=='native_driver' else name+'.c'),'-o',name+'.o'])
    for name in ('native_client', 'native_policy'):
        run([TOOLS/'bin/vc.exe','+'+str(ROOT/'audio/kick13.cfg'),'-c','-O2','-cpu=68000',
             '-I'+str(WORKER), WORKER/(name+'.c'), '-o', name+'.o'])
    run([TOOLS/'bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o','wrappers.o','wrappers.s'])
    run([TOOLS/'bin/vc.exe','+'+str(ROOT/'audio/kick13.cfg'),'-c','-O2','-cpu=68000',
         HERE/'native_clock.c','-o','native_clock.o'])
    run([TOOLS/'bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o','native_divmod.o',HERE/'native_divmod.s'])
    if HYBRID_MIX:
        generate_hybrid_tables()
        run([TOOLS/'bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o','hybrid_tables.o','hybrid_tables.s'])
        run([TOOLS/'bin/vasmm68k_mot.exe','-quiet','-m68000','-Fhunk','-o','hybrid_samples.o',HERE/'hybrid_samples.s'])
    run([TOOLS/'bin/vlink.exe','-bamigahunk','-Z','-Bstatic','-Cvbcc','-nostdlib','-Mmodule.map',
         '-o','module.hunk','wrappers.o']+[name+'.o' for name in objects]+['native_client.o','native_policy.o','native_clock.o','native_divmod.o']+(['hybrid_samples.o','hybrid_tables.o'] if HYBRID_MIX else []))
    append_module()

def pack(*values):
    return struct.pack('>%dI' % len(values), *values)

def append_module():
    original = ORIGINAL.read_bytes()
    old = read(ORIGINAL)
    module = read(BUILD / 'module.hunk')
    symbols = {}
    current = -1
    for h in module.hunks:
        if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS'):
            current += 1
        if h['type_name'] == 'HUNK_SYMBOL':
            for name,offset in h['symbols']:
                if name.startswith('_nv_') or name == '_SysBase':
                    symbols[name] = dict(hunk=current+3,offset=offset)
    body = bytearray(original[32:])
    code = next(h for h in old.hunks if h['type_name']=='HUNK_CODE')
    patches = json.loads((BUILD / 'patches.json').read_text())
    relocs = {}
    for patch in patches:
        address,size = patch['address'],patch['size']
        start = code['data_file_offset']-32+address
        assert body[start:start+size].hex() == patch['expected']
        destination = symbols[patch['symbol']]
        operation = 0x4ef9 if patch.get('jump') else 0x4eb9
        body[start:start+size] = struct.pack('>HI',operation,destination['offset']) + bytes.fromhex('4e71')*((size-6)//2)
        relocs.setdefault(destination['hunk'],[]).append(address+2)
    record = pack(1004)
    for target,offsets in relocs.items():
        record += pack(len(offsets),target,*offsets)
    record += pack(0)
    end = next(h['hunk_file_offset'] for h in old.hunks if h['type_name']=='HUNK_END')-32
    body[end:end] = record
    appended = bytearray()
    for h in module.hunks:
        name = h['type_name']
        if name == 'HUNK_HEADER':
            continue
        if name in ('HUNK_CODE','HUNK_DATA','HUNK_BSS'):
            appended += pack(h['type'],h['size']//4)
            if name != 'HUNK_BSS':
                appended += h['data']
        elif name == 'HUNK_ABSRELOC32':
            appended += pack(1004)
            for target,offsets in h['reloc'].items():
                appended += pack(len(offsets),target+3,*offsets)
            appended += pack(0)
        elif name == 'HUNK_SYMBOL':
            # Keep global export metadata separately; no need for Amiga symbols in release file.
            continue
        elif name == 'HUNK_END':
            if len(appended) and current >= 0:
                pass
            appended += pack(1010)
        else:
            raise ValueError('Unexpected module record '+name)
    # The continuation absolute jump is deliberately external to the linked module.
    # Add its H0 relocation before the first appended HUNK_END.
    first_end = next(h['hunk_file_offset'] for h in module.hunks if h['type_name']=='HUNK_END')
    # Locate serialized end after code and reloc record (symbols were omitted).
    first_code = next(h for h in module.hunks if h['type_name']=='HUNK_CODE')
    pos = 8 + len(first_code['data'])
    if struct.unpack_from('>I',appended,pos)[0] == 1004:
        pos += 4
        while True:
            count = struct.unpack_from('>I',appended,pos)[0]
            pos += 4
            if not count: break
            pos += 4 + count*4
    assert appended[pos:pos+4] == pack(1010)
    offsets = [entry['offset']+2 for name,entry in symbols.items() if name.startswith('_nv_continue_')]
    assert all(entry['hunk']==3 for name,entry in symbols.items() if name.startswith('_nv_continue_'))
    appended[pos:pos] = pack(1004,len(offsets),0,*offsets,0)
    sections = [h for h in module.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
    count = 3+len(sections)
    header = pack(1011,0,count,0,count-1)+original[20:32]+b''.join(pack(h['alloc_size']//4) for h in sections)
    patched = header+body+appended
    output = BUILD / 'Monkey_Talkie_Test'
    output.write_bytes(patched)
    checked = read(output)
    assert len([h for h in checked.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')]) == count
    old_sections=[h for h in old.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
    new_sections=[h for h in checked.hunks if h['type_name'] in ('HUNK_CODE','HUNK_DATA','HUNK_BSS')]
    for index in (1,2):
        assert old_sections[index].get('data')==new_sections[index].get('data')
    restored=bytearray(new_sections[0]['data'])
    for patch in patches:
        address=patch['address']
        restored[address:address+patch['size']]=bytes.fromhex(patch['expected'])
    assert restored==old_sections[0]['data']
    def relocation_set(reader):
        result=set();source=None
        for h in reader.hunks:
            if 'hunk_no' in h:source=h['hunk_no']
            if h['type_name']=='HUNK_ABSRELOC32':
                for target,offsets in h['reloc'].items():
                    for offset in offsets:result.add((source,target,offset))
        return result
    assert relocation_set(old)<=relocation_set(checked)
    manifest = dict(original_sha256=EXPECTED,sha256=hashlib.sha256(patched).hexdigest(),
                    exports=symbols,patches=patches,voice_abi_version=1,control_version=2,control_size=28,
                    original_relocations_retained=True,original_data_hunks_unchanged=True,
                    prototype=True,gameplay_validated=False,metadata_enabled=WITH_METADATA,
                    audio_backend='dedicated_paula0',
                    output_buffer_bytes=256,
                    output_copy='aligned_longword_with_byte_tail_or_unaligned_fallback',
                    idle_audio='original_native_hardware',
                    active_audio='speech_on_paula0_native_channels_1_to_3_unchanged',
                    native_channel0_during_speech='muted_with_analytical_phase_and_macro_events',
                    voice_pcm='preprocessed_signed_ring_copied_without_mixing',
                    hardware_clock='owned_ciaa_resource_timer_all_os',
                    skip_pirate_check_flag=8,
                    speech_balance=dict(max_speech_gain=48 if WITH_DUCKING else 64,
                                        native_gain_during_speech=16 if WITH_DUCKING else 64,
                                        native_gain_idle=64,scale=64,music_ducking=WITH_DUCKING,
                                        physical_volume_latest_write_cache=WITH_DUCKING,
                                        physical_gain_aligned_to_playing_buffer=WITH_DUCKING))
    layout=symbols['_nv_driver_layout']
    names=['size','mixer','clipped','music_gain','bank','buffers','serials','next_serial','active','first_irq','running','dma_bits','irqs','original_handler','gains','physical_gain','native_volumes','speech_active','native_first_irq','clock_started','last_tick','native_events']
    if STEREO_MIX:
        names=['size','native','buffers','right','serials','next_serial','active','first_irq','running','dma_bits','irqs','original_handler','clock_started','last_tick','clipped','frames_produced']
        manifest.update(audio_backend='continuous_stereo_mix',output_buffer_bytes=128,
            output_copy='four native voices plus centered speech; constant three-way headroom',
            idle_audio='software stereo music/SFX',active_audio='same stereo mix plus speech on both outputs',
            native_channel0_during_speech='mixed together with native channels 1..3',
            music_clock='EClock only; render snapshots never advance live phase',
            music_ducking=False,render_ahead_max_samples=256,
            target='experimental accelerated Amiga; A500 performance not established')
    if HYBRID_MIX:
        names += ['max_render_ticks','late_buffers']
        manifest.update(audio_backend='hybrid_stereo_mix',output_buffer_bytes=256,
            output_copy='lookup scaled native0/1 plus centered speech; fixed half headroom',
            idle_audio='native2/3 hardware; native0/1 software',
            active_audio='native0/1 plus speech; native2/3 hardware',
            native_channel0_during_speech='mixed with speech; native1 likewise',
            render_ahead_max_samples=512,deadline_counter='render wall time >= one buffer',
            target='experimental hybrid; physical hardware and A500 not certified')
    raw=new_sections[layout['hunk']]['data'][layout['offset']:layout['offset']+2*len(names)]
    manifest['driver_layout']=dict(zip(names,struct.unpack('>'+str(len(names))+'H',raw)))
    (BUILD / 'module.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(dict(output=str(output),control=symbols['_nv_control'],end=symbols['_nv_driver_end'])))

if __name__ == '__main__':
    main()
