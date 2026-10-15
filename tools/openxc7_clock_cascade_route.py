#!/usr/bin/env python3
"""Run the original full accelerator with the qualified clock connectivity fix."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_bufg_route_guard import fasm_check


def route(gate: Path, source_proof: Path, out: Path):
    g = json.loads(gate.read_text())
    s = json.loads(source_proof.read_text())
    if g['status'] != 'FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS':
        raise ValueError('Complete corrected-clock full-design qualification required')
    if s['status'] != 'ALL_31_FULL_DESIGN_SOURCE_FILES_UNCHANGED' or len(s['source']) != 31:
        raise ValueError('Original full-design source proof required')
    if any(digest(name) != value for name, value in s['source'].items()):
        raise ValueError('Full design source changed')
    for record in [g['binary'], g['chipdb'], *g['full_inputs'].values(), *g['outputs'].values()]:
        if describe(record['path']) != record:
            raise ValueError('Qualified executable, database or full input changed')
    out.mkdir(parents=True, exist_ok=False)
    argv = json.loads((gate.parent / 'full.command.json').read_text())
    argv.remove('--pack-only')
    for index, arg in enumerate(argv):
        if '=' in arg and arg.split('=', 1)[0].endswith('-audit'):
            argv[index] = arg.split('=', 1)[0] + '=' + str(out / Path(arg.split('=', 1)[1]).name)
    argv += ['--placer', 'static', '--router', 'router2', '--detailed-timing-report',
             '--write', str(out / 'routed.json'), '--report', str(out / 'timing.json'),
             '-o', 'fasm=' + str(out / 'design.raw.fasm'),
             '-o', 'bufg-route-audit=' + str(out / 'clock.policy.tsv')]
    (out / 'route.command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'full_gate': describe(gate), 'source_proof': describe(source_proof),
            'helper': describe(__file__), 'binary': g['binary'], 'chipdb': g['chipdb'],
            'profile': g['profile'], 'full_inputs': g['full_inputs'], 'threads_requested': 8,
            'clock_loc_enabled': True, 'hardware_accessed': False,
            'original_full_jobs_changed': False, 'scope': 'ORIGINAL_FULL_ACCELERATOR_PLACEMENT_AND_ROUTING',
            'timing_signoff': False, 'hardware_ready': False, 'accepted_image': None}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='full-native-placement-and-routing')
        with (out / 'route.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            proc = Path('/proc') / str(child.pid)
            fields = (proc / 'stat').read_text().split()
            allowed = next(line.split(':', 1)[1].strip() for line in (proc / 'status').read_text().splitlines()
                           if line.startswith('Cpus_allowed_list:'))
            save(native_pid=child.pid, native_start_ticks=int(fields[21]), cpus_allowed=allowed)
            print('FULL_CORRECTED_CLOCK_ROUTE_STARTED ' + str(out) + ' PID ' + str(child.pid), flush=True)
            code = child.wait()
        (out / 'route.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Full native implementation failed: ' + str(code))
        for name in ('routed.json', 'timing.json', 'design.raw.fasm'):
            if not (out / name).is_file() or not (out / name).stat().st_size:
                raise ValueError('Full route output missing: ' + name)
        save(status='FULL_NATIVE_ROUTE_AND_FASM_CLOCK_DRIVER_GATE_PASS_IMAGE_AND_TIMING_QUALIFICATION_PENDING',
             fasm_clock_driver_gate=fasm_check(out / 'design.raw.fasm'),
             outputs={name: describe(out / name) for name in ('routed.json', 'timing.json', 'design.raw.fasm', 'clock.policy.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('gate', 'source-proof', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    route(args.gate.resolve(), args.source_proof.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
