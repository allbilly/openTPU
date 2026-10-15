#!/usr/bin/env python3
"""Run a full-design congestion-aware placement using immutable route inputs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from fedora_openxc7 import describe, digest

PROFILE = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2,
               CORE_KHZ=100000, DDR_MTS=800)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--source-proof', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    baseline, gate, proof, out = (p.resolve() for p in
                                 (args.baseline, args.gate, args.source_proof, args.out))
    b, g, s = (json.loads(p.read_text()) for p in (baseline, gate, proof))
    if g['status'] != 'FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS':
        raise ValueError('Complete full-design clock/CDC gate required')
    if b['profile'] != PROFILE or g['profile'] != PROFILE:
        raise ValueError('Full profile changed')
    if b['binary'] != g['binary'] or b['chipdb'] != g['chipdb'] or b['full_inputs'] != g['full_inputs']:
        raise ValueError('Baseline and qualified full inputs differ')
    if s['status'] != 'ALL_31_FULL_DESIGN_SOURCE_FILES_UNCHANGED' or len(s['source']) != 31:
        raise ValueError('Complete original source proof required')
    records = [b['binary'], b['chipdb'], *b['full_inputs'].values(), *g['outputs'].values()]

    def verify():
        for record in records:
            if describe(record['path']) != record:
                raise ValueError('Immutable backend, database, input or gate output changed')
        if any(digest(name) != value for name, value in s['source'].items()):
            raise ValueError('Original full-design source changed')

    verify()
    original = json.loads((baseline.parent / 'route.command.json').read_text())
    if original[0] != b['binary']['path'] or '--timing-allow-fail' in original:
        raise ValueError('Unexpected baseline command')
    out.mkdir(parents=True, exist_ok=False)
    argv = []
    i = 0
    while i < len(original):
        item = original[i]
        if item == '-o' and original[i + 1].startswith(('fasm=', 'bufg-route-audit=')):
            i += 2
            continue
        if item in ('--placer', '--write', '--report'):
            value = {'--placer': 'heap', '--write': str(out / 'placed.json'),
                     '--report': str(out / 'placement-timing.json')}[item]
            argv.extend((item, value))
            i += 2
            continue
        if '=' in item and item.split('=', 1)[0].endswith('-audit'):
            item = item.split('=', 1)[0] + '=' + str(out / Path(item.split('=', 1)[1]).name)
        argv.append(item)
        i += 1
    argv.extend(('--no-route', '--placer-heap-congestion-spread',
                 '--placer-heap-congestion-weight', '0.5'))
    if argv[argv.index('--threads') + 1] != '8' or argv[argv.index('--freq') + 1] != '100.0':
        raise ValueError('Requested full-design clock or CPU count differs')
    (out / 'placement.command.json').write_text(json.dumps(argv, indent=2) + '\n')
    allowed = sorted(os.sched_getaffinity(0))
    info = dict(status='RUNNING', stage='full-native-congestion-aware-placement',
                created_utc=datetime.now(timezone.utc).isoformat(), helper=describe(__file__),
                baseline=describe(baseline), gate=describe(gate), source_proof=describe(proof),
                binary=b['binary'], chipdb=b['chipdb'], full_inputs=b['full_inputs'],
                profile=PROFILE, threads_requested=8, allowed_cpus=allowed,
                congestion_spread=True, congestion_weight=0.5,
                scope='FULL_ACCELERATOR_PLACEMENT_COMPARISON_ROUTING_AND_TIMING_QUALIFICATION_PENDING',
                hardware_accessed=False, original_full_jobs_changed=False,
                backend_changed=False, timing_signoff=False, hardware_ready=False)

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        with (out / 'placement.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            stat = Path(f'/proc/{child.pid}/stat').read_text().rsplit(')', 1)[1].split()
            save(native_pid=child.pid, native_start_ticks=int(stat[19]))
            print('FULL_CONGESTION_PLACEMENT_STARTED ' + str(out) + ' PID ' + str(child.pid), flush=True)
            code = child.wait()
        (out / 'placement.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Full native placement failed: ' + str(code))
        verify()
        paths = [out / 'placed.json', out / 'placement-timing.json']
        if any(not p.is_file() or not p.stat().st_size for p in paths):
            raise ValueError('Completed full placement outputs missing')
        save(status='FULL_CONGESTION_PLACEMENT_NATIVE_COMPLETE_REVIEW_PENDING',
             outputs={p.name: describe(p) for p in paths},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise


if __name__ == '__main__':
    main()
