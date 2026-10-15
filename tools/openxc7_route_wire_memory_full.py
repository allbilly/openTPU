#!/usr/bin/env python3
"""Check unchanged full-design timing contracts with the compact router backend."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phase_engine_check import domain_rows


def check(backend, native_gate, previous, out):
    b = json.loads(backend.read_text())
    g = json.loads(native_gate.read_text())
    p = json.loads(previous.read_text())
    if (b['status'] != 'ROUTER_WIRE_MEMORY_VARIANT_BUILD_PASS_NATIVE_VALIDATION_PENDING'
            or not b['compact_enabled'] or b['verification_only'] or not b['upstream_guard_present']
            or g['status'] != 'ALL_SIX_NATIVE_MEMORY_ROUTES_AND_EXACT_OUTPUT_AB_PASS'
            or p['status'] != 'FULL_BUFG_GUARD_PACK_AND_COMPLETE_TIMING_CONSTRAINT_INVARIANTS_PASS'
            or b['parent'] != p['backend']):
        raise ValueError('Compact backend, completed native comparison or full ancestry differs')
    if describe(g['backend']['path']) != g['backend'] or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Native comparison/backend changed')
    pair = json.loads(Path(g['backend']['path']).read_text())
    if describe(backend) != pair['variants']['compact'] or any(row['native_exit'] for row in g['results'].values()):
        raise ValueError('Compact candidate differs from the tested native binary')
    for record in [*p['full_inputs'].values(), *p['outputs'].values()]:
        if describe(record['path']) != record:
            raise ValueError('Complete full input or prior result changed')
    out.mkdir(parents=True, exist_ok=False)
    argv = json.loads((previous.parent / 'full.command.json').read_text())
    argv[0] = b['binary']['path']
    for index, arg in enumerate(argv):
        if '=' in arg and arg.split('=', 1)[0].endswith('-audit'):
            argv[index] = arg.split('=', 1)[0] + '=' + str(out / Path(arg.split('=', 1)[1]).name)
    (out / 'full.command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'backend': describe(backend), 'binary': b['binary'], 'native_gate': describe(native_gate),
            'previous_full': describe(previous), 'helper': describe(__file__), 'profile': p['profile'],
            'full_inputs': p['full_inputs'], 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'COMPLETE_UNPLACED_PACKING_CONTRACTS_NOT_NEW_FULL_ROUTE_OR_NUMERICAL_TIMING'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='complete-native-pack-and-analysis')
        print('FULL_COMPACT_BACKEND_CONTRACT_CHECK_STARTED ' + str(out), flush=True)
        with (out / 'full.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid)
            code = child.wait()
        (out / 'full.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Complete compact-backend native pack failed')
        for name in ('full.clusters.json', 'full.datapath.json', 'full.paths.json'):
            if json.loads((out / name).read_text()) != json.loads((previous.parent / name).read_text()):
                raise ValueError('Complete native timing contract changed: ' + name)
        if domain_rows(out / 'full.domains.tsv') != domain_rows(previous.parent / 'full.domains.tsv'):
            raise ValueError('Complete generated-clock/phase budgets changed')
        endpoints = json.loads((out / 'full.datapath.json').read_text())
        domains = domain_rows(out / 'full.domains.tsv')
        clusters = json.loads((out / 'full.clusters.json').read_text())
        if len(endpoints) != 1103 or len(clusters) != 2:
            raise ValueError('Complete mailbox or synchronizer coverage differs')
        save(status='FULL_COMPACT_BACKEND_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS',
             comparison={'endpoints': len(endpoints), 'synchronizer_clusters': len(clusters),
                         'domain_pairs': len(domains), 'all_full_audit_changes': 0, 'profile_changes': 0,
                         'ff_numerical_values': 'PROVISIONAL_UNCHANGED', 'geometry': 'UNPLACED_ZERO_DATA_ROUTE'},
             outputs={name: describe(out / name) for name in ('full.clusters.json', 'full.datapath.json', 'full.paths.json', 'full.domains.tsv')},
             full_new_route='PENDING', numerical_timing='NOT_QUALIFIED',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': info['comparison']}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'native-gate', 'previous', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    check(args.backend.resolve(), args.native_gate.resolve(), args.previous.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
