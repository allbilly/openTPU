#!/usr/bin/env python3
"""Verify unchanged full accelerator contracts with the corrected clock database."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phase_engine_check import domain_rows


def check(backend: Path, clock_gate: Path, negative_gate: Path, previous: Path, out: Path):
    b = json.loads(backend.read_text())
    g = json.loads(clock_gate.read_text())
    n = json.loads(negative_gate.read_text())
    p = json.loads(previous.read_text())
    if (b['status'] != 'CLOCK_ROUTE_DIAGNOSTIC_BUILD_PASS_NATIVE_QUERY_PENDING'
            or b['parent'] != p['backend']
            or g['status'] != 'ALL_54_DEDICATED_CLOCK_ARCS_AND_NATIVE_CLOCK_FIXTURE_MAIN_ROUTE_PASS'
            or g['backend'] != describe(backend) or n['status'] != 'ALL_NEGATIVE_CLOCK_LOCS_REJECTED'
            or p['status'] != 'FULL_COMPACT_BACKEND_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS'):
        raise ValueError('Completed native clock, negative LOC and full parent gates required')
    if p['profile'] != {'MCOLS': 4, 'ACT_ROWS': 4, 'LANES': 8, 'VPU_CL': 2, 'MXU_IMPL': 2,
                        'CORE_KHZ': 100000, 'DDR_MTS': 800}:
        raise ValueError('Original full accelerator scope differs')
    if describe(b['binary']['path']) != b['binary'] or describe(g['databases']['path']) != g['databases']:
        raise ValueError('Tested binary or database manifest changed')
    db = json.loads(Path(g['databases']['path']).read_text())['variants']['fixed']['binary']
    for record in [db, *p['full_inputs'].values(), *p['outputs'].values()]:
        if describe(record['path']) != record:
            raise ValueError('Pinned input or prior full audit changed')
    out.mkdir(parents=True, exist_ok=False)
    argv = json.loads((previous.parent / 'full.command.json').read_text())
    argv[0] = b['binary']['path']
    argv[argv.index('--chipdb') + 1] = db['path']
    argv += ['-o', 'clock-loc-contract']
    for index, arg in enumerate(argv):
        if '=' in arg and arg.split('=', 1)[0].endswith('-audit'):
            argv[index] = arg.split('=', 1)[0] + '=' + str(out / Path(arg.split('=', 1)[1]).name)
    (out / 'full.command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'backend': describe(backend), 'binary': b['binary'], 'chipdb': db,
            'clock_gate': describe(clock_gate), 'negative_gate': describe(negative_gate),
            'previous_full': describe(previous), 'helper': describe(__file__),
            'profile': p['profile'], 'full_inputs': p['full_inputs'],
            'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'FULL_ACCELERATOR_PACK_AND_TIMING_CONTRACTS_NOT_FULL_ROUTE_OR_TIMING_SIGNOFF'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='complete-native-pack-and-analysis')
        print('FULL_CLOCK_DATABASE_CONTRACT_CHECK_STARTED ' + str(out), flush=True)
        with (out / 'full.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid)
            code = child.wait()
        (out / 'full.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Complete corrected clock database pack failed')
        for name in ('full.clusters.json', 'full.datapath.json', 'full.paths.json'):
            if json.loads((out / name).read_text()) != json.loads((previous.parent / name).read_text()):
                raise ValueError('Full native contract differs: ' + name)
        domains = domain_rows(out / 'full.domains.tsv')
        if domains != domain_rows(previous.parent / 'full.domains.tsv'):
            raise ValueError('Full generated-clock/phase budgets changed')
        endpoints = json.loads((out / 'full.datapath.json').read_text())
        clusters = json.loads((out / 'full.clusters.json').read_text())
        if len(endpoints) != 1103 or len(clusters) != 2:
            raise ValueError('Full mailbox or synchronizer coverage differs')
        save(status='FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS',
             comparison={'endpoints': len(endpoints), 'synchronizer_clusters': len(clusters),
                         'domain_pairs': len(domains), 'full_audit_changes': 0, 'profile_changes': 0},
             outputs={name: describe(out / name) for name in ('full.clusters.json', 'full.datapath.json',
                                                            'full.paths.json', 'full.domains.tsv')},
             full_route='PENDING', numerical_timing='NOT_QUALIFIED',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'clock-gate', 'negative-gate', 'previous', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    check(*(getattr(args, name.replace('-', '_')).resolve()
            for name in ('backend', 'clock-gate', 'negative-gate', 'previous', 'out')))


if __name__ == '__main__':
    main()
