"""Prepare a standalone PAL/A500 guest benchmark for two stripe kernels."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import csv
import statistics

SOURCE = Path(__file__).resolve().parent
ROOT = SOURCE.parents[1]


def prepare(output, candidate, reference):
    output=output.resolve()
    if not output.is_relative_to(ROOT/'build') or output.exists():
        raise ValueError('Choose a new output beneath build/')
    output.mkdir(parents=True)
    header=[]
    for label, directory in [('baseline',reference),('candidate',candidate)]:
        gen=json.loads((directory/'generation.json').read_text()); raw=(directory/'stripe.bin').read_bytes()
        assert hashlib.sha256(raw).hexdigest()==gen['kernel_sha256']
        (output/(label+'.bin')).write_bytes(raw)
        header.append('static const unsigned short '+label+'_relocs[] = {'+
                      ','.join(map(str,gen['absolute_h2_relocations']))+'};')
    (output/'bench_bindings.h').write_text('\n'.join(header)+'\n')
    fixtures=ROOT/'tests/fixtures/bar-stripes'
    cases=json.loads((fixtures/'fixtures.json').read_text())['fixtures']
    packed=bytearray(struct.pack('>I',len(cases)))
    for case in cases:
        tokens=(fixtures/case['token_file']).read_bytes()
        assert hashlib.sha256(tokens).hexdigest()==case['token_sha256']
        packed+=struct.pack('>II',case['height'],len(tokens))+tokens
    (output/'cases.dat').write_bytes(packed)
    tools=Path('D:/Tools/amiga-dev')
    env=dict(os.environ,VBCC=str(tools/'targets/m68k-amigaos'),PATH=str(tools/'bin')+os.pathsep+os.environ['PATH'])
    subprocess.run([str(tools/'bin/vc.exe'),'+'+str(ROOT/'audio/kick13.cfg'),'-O2','-cpu=68000',
                    '-I'+str(output),'-I'+str(ROOT/'engine/core'),'-o',str(output/'StripeBench'),
                    str(SOURCE/'benchmark.c'),str(ROOT/'engine/core/native_clock.c')],env=env,check=True)
    (output/'S').mkdir();(output/'S/startup-sequence').write_bytes(b'StripeBench\n')
    settings=json.loads((ROOT/'run/settings.json').read_text())
    write_fsuae_config(output, Path(settings['kickstart']))
    (output/'inputs.json').write_text(json.dumps({'candidate':str(candidate),'reference':str(reference),
        'cases':len(cases),'clock':'guest timer.device EClock at real PAL A500 settings',
        'scope':'standalone function workload; not gameplay FPS','iterations_per_interval':4,
        'timed_region':'four decoder calls; file IO/checksums outside timer interval'},indent=2)+'\n')
    print(output)


def write_fsuae_config(output, kickstart):
    """Use a private guest disk and ROM copy; never touch a running game."""
    import shutil
    shutil.copyfile(kickstart, output/'kickstart.rom')
    drive=output.resolve().as_posix()
    if len(drive)>2 and drive[1]==':':
        drive='/mnt/'+drive[0].lower()+drive[2:]
    (output/'benchmark.fs-uae').write_text('[fs-uae]\n'
        'amiga_model = A500\ncpu = 68000\nchip_memory = 1024\nfast_memory = 8192\n'
        'ntsc_mode = 0\nuae_cpu_speed = real\nuae_cpu_compatible = true\n'
        'uae_cpu_cycle_exact = true\nuae_cpu_memory_cycle_exact = true\n'
        'uae_blitter_cycle_exact = true\nuae_cachesize = 0\n'
        'audio_driver = dummy\nvolume = 0\nfloppy_drive_volume = 0\n'
        'floppy_drive_volume_empty = 0\n'
        'uae_sound_volume = 100\nuae_sound_volume_paula = 100\n'
        'automatic_input_grab = 0\nclipboard_sharing = 0\n'
        f'kickstart_file = {drive}/kickstart.rom\nhard_drive_0 = {drive}\n')
    (output/'run-fsuae.sh').write_text('#!/bin/sh\nset -eu\n'
        'TASK=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\n'
        'mkdir -p "$TASK/home"\nexport HOME="$TASK/home"\n'
        'export SDL_AUDIODRIVER=dummy\n'
        'cd "$TASK"\n'
        'exec timeout 300s xvfb-run -a fs-uae "$TASK/benchmark.fs-uae" '
        '> "$TASK/fsuae.log" 2>&1\n', newline='\n')


def summarize(output):
    """Reject partial runs and report paired timings without claiming game FPS."""
    lines=(output/'results.csv').read_text().splitlines()
    if not lines or lines[-1]!='DONE' or 'MISMATCH' in lines:
        raise ValueError('Benchmark incomplete or output mismatch')
    rows=list(csv.DictReader(lines[:-1]))
    cases=json.loads((output/'inputs.json').read_text())['cases']
    expected={(m,c,k,o) for m in range(2) for c in range(cases)
              for k in range(2) for o in range(2)}
    keys=[tuple(int(r[n]) for n in ('memory','case','mask','order')) for r in rows]
    if len(keys)!=len(expected) or set(keys)!=expected:
        raise ValueError('Missing, duplicate or unexpected benchmark rows')
    summary={'comparisons':len(rows),'all_output_checksums_matched':True,
        'scope':'standalone decoder workload, not gameplay FPS',
        'results_sha256':hashlib.sha256((output/'results.csv').read_bytes()).hexdigest(),
        'kernels_sha256':{name:hashlib.sha256((output/(name+'.bin')).read_bytes()).hexdigest()
                          for name in ('baseline','candidate')},'timings':[]}
    for memory in range(2):
        for mask in (0,1,None):
            selected=[r for r in rows if int(r['memory'])==memory
                      and (mask is None or int(r['mask'])==mask)]
            baseline=sum(int(r['baseline_ticks']) for r in selected)
            candidate=sum(int(r['candidate_ticks']) for r in selected)
            if any(int(r['baseline_ticks'])<=0 or int(r['candidate_ticks'])<=0 for r in selected):
                raise ValueError('Nonpositive timing')
            summary['timings'].append({'destination':'chip' if memory else 'fast',
                'mask':mask,'comparisons':len(selected),'baseline_ticks':baseline,
                'candidate_ticks':candidate,'aggregate_reduction_percent':100*(1-candidate/baseline),
                'median_paired_reduction_percent':statistics.median(
                    100*(1-int(r['candidate_ticks'])/int(r['baseline_ticks'])) for r in selected)})
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--candidate',type=Path)
    parser.add_argument('--summarize',action='store_true')
    parser.add_argument('--reference',type=Path,default=ROOT/'build/engine/stripes')
    args=parser.parse_args()
    if args.summarize:
        summarize(args.output)
    else:
        if args.candidate is None:
            parser.error('--candidate is required when preparing a benchmark')
        prepare(args.output,args.candidate,args.reference)
