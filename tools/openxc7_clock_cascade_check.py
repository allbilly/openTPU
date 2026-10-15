#!/usr/bin/env python3
"""Compare dedicated clock routes with stock/fixed databases, then route the fixture."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

from fedora_openxc7 import describe
from openxc7_bufg_route_guard import fasm_check, policy, through
from openxc7_clock_route_probe import probe
from openxc7_route_wire_memory import run


def check(backend: Path, databases: Path, prototype: Path, out: Path):
    pair = json.loads(databases.read_text())
    b = json.loads(backend.read_text())
    p = json.loads((prototype / 'manifest.json').read_text())
    if pair['status'] != 'STOCK_DATABASE_REPRODUCED_FIXED_CASCADE_DATABASE_BUILD_PASS_NATIVE_QUERY_PENDING':
        raise ValueError('Completed controlled database pair required')
    if pair['parent'] != describe(backend) or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Native diagnostic differs from database parent')
    for row in pair['variants'].values():
        if describe(row['binary']['path']) != row['binary']:
            raise ValueError('Controlled database changed')
    census = {}
    for variant in ('stock', 'fixed'):
        log = (databases.parent / variant / 'generator.log').read_text()
        pattern = (r'check: (\d+) tile-routing pips, (\d+) expressible, '
                   r'(\d+) NOT expressible .*?, (\d+) unchecked')
        matches = re.findall(pattern, log)
        if len(matches) != 1:
            raise ValueError('Generator configuration census missing or duplicated')
        census[variant] = tuple(map(int, matches[0]))
    if tuple(a - b for a, b in zip(census['fixed'], census['stock'])) != (32, 32, 0, 0):
        raise ValueError('Database changes more than the 32 verified configurable cascade PIPs')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'backend': describe(backend), 'databases': describe(databases),
            'prototype': describe(prototype / 'manifest.json'), 'helper': describe(__file__),
            'generator_pip_census': census,
            'scope': 'ACTUAL_FULL_CLOCK_TOPOLOGY_NOT_FULL_ACCELERATOR_ROUTE_OR_TIMING_SIGNOFF',
            'hardware_accessed': False, 'live_full_jobs_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def diagnostic(variant):
        target = out / variant
        probe(backend, prototype, target, 1, True, pair['variants'][variant]['binary']['path'])
        with (target / 'clocks.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        keyed = {(r['source_cell'], r['source_port'], r['sink_cell'], r['sink_port']): r for r in rows}
        if len(keyed) != 54 or len(rows) != 54:
            raise ValueError('Actual 54 clock arcs missing or duplicated')
        pip_policy = policy(target / 'clock.policy.tsv')
        forbidden = [r for r in pip_policy.values() if through(r)]
        if len(pip_policy) != 480 or len(forbidden) != 32 or any(r['unavailable'] != '1' for r in forbidden):
            raise ValueError('Existing clock-buffer route-through guard changed')
        return variant, keyed

    try:
        save(stage='native-stock-fixed-dedicated-clock-comparison')
        print('NATIVE_CASCADE_DATABASE_COMPARISON_STARTED ' + str(out), flush=True)
        with ThreadPoolExecutor(max_workers=2) as pool:
            rows = dict(pool.map(diagnostic, ('stock', 'fixed')))
        if rows['stock'].keys() != rows['fixed'].keys():
            raise ValueError('Clock topology differs between database variants')
        improvements, regressions = [], []
        for key, before in rows['stock'].items():
            after = rows['fixed'][key]
            if before['dedicated_found'] == '0' and after['dedicated_found'] == '1':
                improvements.append(key)
            if before['dedicated_found'] == '1' and after['dedicated_found'] == '0':
                regressions.append(key)
        failures = [r for r in rows['fixed'].values() if r['dedicated_found'] != '1']
        comparison = {'clock_arcs': 54, 'stock_failed': sum(r['dedicated_found'] == '0' for r in rows['stock'].values()),
                      'fixed_failed': len(failures), 'improved_arcs': improvements, 'regressions': regressions,
                      'fixed_failures': failures, 'no_config_bit_guard': 'UNCHANGED',
                      'buffer_route_through_pips_blocked': 32}
        save(comparison=comparison)
        if failures or regressions or len(improvements) != 6:
            raise ValueError('Cascade database did not fix exactly the six outstanding dedicated arcs')

        target = out / 'fixed-main-route'
        target.mkdir()
        argv = [b['binary']['path'], '--chipdb', pair['variants']['fixed']['binary']['path'],
                '--device', 'xc7k480tffg1156-2', '--json', p['prototype']['path'],
                '-o', 'xdc=' + p['xdc']['path'], '-o', 'delay-matrix=off', '-o', 'clock-loc-contract',
                '-o', 'bufg-route-audit=' + str(target / 'clock.policy.tsv'), '--threads', '8',
                '--freq', '100', '--seed', '1', '--router', 'router2',
                '-o', 'fasm=' + str(target / 'clock.fasm'), '--write', str(target / 'routed.json'),
                '--report', str(target / 'timing.json')]
        save(stage='native-main-route-of-actual-clock-fixture')
        code, elapsed = run(target, 'native', argv)
        save(main_route_native_exit=code, main_route_seconds=elapsed)
        if code != 0:
            raise RuntimeError('Clock fixture main route failed: ' + str(code))
        fasm_gate = fasm_check(target / 'clock.fasm')
        lines = (target / 'clock.fasm').read_text().splitlines()
        restored = [line for line in lines if 'CLK_HROW_TOP_R' in line and '.CLK_HROW_TOP_R_CK_BUFG_CASCO' in line
                    and '.CLK_HROW_TOP_R_CK_BUFG_CASCIN' in line]
        if not restored:
            raise ValueError('Completed clock route did not emit restored cascade configuration')
        save(status='ALL_54_DEDICATED_CLOCK_ARCS_AND_NATIVE_CLOCK_FIXTURE_MAIN_ROUTE_PASS',
             fasm_clock_driver_gate=fasm_gate, restored_cascade_fasm_features=restored,
             outputs={name: describe(target / name) for name in ('clock.fasm', 'routed.json', 'timing.json', 'clock.policy.tsv')},
             full_accelerator_route='PENDING', numerical_timing='NOT_QUALIFIED',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': comparison,
                          'restored_cascade_features': len(restored), 'fasm_clock_driver_gate': fasm_gate}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'databases', 'prototype', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    check(*(getattr(args, name).resolve() for name in ('backend', 'databases', 'prototype', 'out')))


if __name__ == '__main__':
    main()
