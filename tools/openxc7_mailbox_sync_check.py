#!/usr/bin/env python3
"""Validate mailbox synchronizer guards, placement and unchanged full packing."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phase_engine_check import domain_rows
from openxc7_packed_dsp_inventory import cells


CHIPDB = expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin')


def fixture():
    top = {'attributes': {}, 'ports': {}, 'cells': {}, 'netnames': {}}
    for name, raw, output in [('core', 2, 4), ('tck', 3, 5)]:
        top['cells'][name + '_standin'] = {'type': 'LUT1', 'parameters': {'INIT': '10'}, 'attributes': {'keep': '1'},
                                         'port_directions': {'I0': 'input', 'O': 'output'}, 'connections': {'I0': ['0'], 'O': [raw]}}
        top['cells'][name + '_buffer'] = {'type': 'BUFG', 'parameters': {}, 'attributes': {},
                                        'port_directions': {'I': 'input', 'O': 'output'}, 'connections': {'I': [raw], 'O': [output]}}
        top['netnames'][name + ('_clk' if name == 'core' else '')] = {'bits': [output], 'attributes': {}, 'hide_name': 0}
    chains = []
    for name, clock, source_clock, bit in [('rq', 4, 5, 10), ('rs', 5, 4, 20)]:
        previous = bit
        for i in range(4):
            cell = 'source_' + name if i == 0 else name + str(i - 1)
            q = bit + i
            top['cells'][cell] = {'hide_name': 0, 'type': 'FDRE', 'parameters': {'INIT': '0', 'IS_C_INVERTED': '0'},
                                 'attributes': {}, 'port_directions': {'C': 'input', 'CE': 'input', 'R': 'input', 'D': 'input', 'Q': 'output'},
                                 'connections': {'C': [source_clock if i == 0 else clock], 'CE': ['1'], 'R': ['0'],
                                                 'D': ['0'] if i == 0 else [previous], 'Q': [q]}}
            top['netnames'][cell + '_q'] = {'hide_name': 0, 'bits': [q], 'attributes': {'ASYNC_REG': 'TRUE'} if i else {}}
            previous = q
        chains.append({'name': name, 'clock': 'core_clk' if name == 'rq' else 'tck',
                       'stages': [{'cell': name + str(i), 'q_net': name + str(i) + '_q'} for i in range(3)],
                       'placement_required': 'ALL_THREE_PRIMARY_FFS_IN_ONE_SLICE',
                       'timing_required': 'NORMAL_RECEIVER_CLOCK_SETUP_HOLD_BETWEEN_STAGES'})
    return {'creator': 'clock-source stand-ins for offline placement only', 'modules': {'sync_probe': top}}, {
        'schema': 1, 'part': 'xc7k480tffg1156-2', 'synchronizers': chains}


def check(backend: Path, out: Path, workers: int, previous: Path | None, contract: Path | None, gate: Path | None):
    b = json.loads(backend.read_text())
    if b['status'] != 'MAILBOX_SYNC_PLACEMENT_BUILD_PASS_NATIVE_VALIDATION_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Expected completed unchanged synchronizer backend')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'helper': describe(__file__), 'workers': workers, 'hardware_accessed': False,
            'scope': 'SYNCHRONIZER_PLACEMENT_ONLY_NOT_FULL_ROUTED_TIMING_OR_HARDWARE_PROOF', 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def run(job):
        name, argv, rejection = job
        (out / (name + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (name + '.log')).open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / (name + '.exit')).write_text(str(code) + '\n')
        if rejection:
            if code != 125 or rejection not in (out / (name + '.log')).read_text():
                raise ValueError('Synchronizer rejection failed: ' + name)
        elif code:
            raise RuntimeError('Native synchronizer case failed: ' + name)
        return name, code

    def audit_clusters(path, wanted):
        actual = {chain['name']: chain['stages'] for chain in json.loads(path.read_text())}
        if set(actual) != {chain['name'] for chain in wanted}:
            raise ValueError('Actual cluster audit has the wrong chains')
        for chain in wanted:
            names = [stage['cell'] for stage in chain['stages']]
            stages = actual[chain['name']]
            if [stage['cell'] for stage in stages] != names:
                raise ValueError('Actual cluster stage order differs')
            for i, stage in enumerate(stages):
                if stage['cluster'] != names[0] or stage['ASYNC_REG'] != 'TRUE':
                    raise ValueError('Actual cluster parent or annotation differs')
                if i:
                    if stage['x'] != 0 or stage['y'] != 0 or stage['z'] != 16 * i or stage['absolute_z'] or stage['children']:
                        raise ValueError('Actual relative cluster offsets differ')
                elif stage['children'] != names[1:]:
                    raise ValueError('Actual cluster children differ')
        return actual

    try:
        if previous:
            p = json.loads((previous / 'manifest.json').read_text())
            g = json.loads(gate.read_text())
            if (p['status'] != 'FULL_UNPLACED_SOFTWARE_PHASE_CONTRACT_PASS_ROUTED_TIMING_PENDING' or p['backend'] != b['previous']
                    or g['status'] != 'ALL_NATIVE_MAILBOX_SYNC_PLACEMENT_CASES_PASS' or g['backend'] != describe(backend)):
                raise ValueError('Full-source or native-gate ancestry mismatch')
            for item in p['full_inputs'].values():
                if describe(item['path']) != item:
                    raise ValueError('Pinned complete source changed')
            argv = json.loads((previous / 'full-analysis.command.json').read_text())
            argv[0] = b['binary']['path']
            for i, arg in enumerate(argv):
                if arg.startswith('phase-domain-audit='):
                    argv[i] = 'phase-domain-audit=' + str(out / 'full.domains.tsv')
                if arg.startswith('phase-path-audit='):
                    argv[i] = 'phase-path-audit=' + str(out / 'full.paths.json')
            argv += ['-o', 'mailbox-sync-contract=' + str(contract), '-o', 'mailbox-sync-audit=' + str(out / 'full.clusters.json')]
            save(stage='full-native-pack', profile=p['profile'], full_inputs=p['full_inputs'], contract=describe(contract), native_gate=describe(gate))
            jobs = [('full-pack', argv, None)]
        else:
            design, declaration = fixture()
            xdc = out / 'probe.xdc'
            xdc.write_text('create_clock -period 10 [get_nets {core_clk}]\ncreate_clock -period 166.666667 [get_nets {tck}]\n')

            def command(name, design, declaration=None, route=False, preplaced=None):
                source = out / (name + '.json')
                source.write_text(json.dumps(design, separators=(',', ':')) + '\n')
                argv = [b['binary']['path'], '--chipdb', CHIPDB, '--device', 'xc7k480tffg1156-2', '--json', str(source),
                        '-o', 'xdc=' + str(xdc), '--threads', '8', '--freq', '100', '--seed', '1',
                        '--write', str(out / (name + '.packed.json'))]
                if declaration is not None:
                    path = out / (name + '.contract.json')
                    path.write_text(json.dumps(declaration, indent=2) + '\n')
                    argv += ['-o', 'mailbox-sync-contract=' + str(path)]
                    argv += ['-o', 'mailbox-sync-audit=' + str(out / (name + '.clusters.json'))]
                if route:
                    argv += ['-o', 'delay-matrix=off', '--router', 'router2', '-o', 'fasm=' + str(out / (name + '.fasm')),
                             '--detailed-timing-report', '--report', str(out / (name + '.timing.json'))]
                    if preplaced:
                        path = out / (name + '.preplaced.tsv')
                        path.write_text('rq0\t' + preplaced[0] + '\nrs0\t' + preplaced[1] + '\n')
                        argv += ['-o', 'preplaced=' + str(path)]
                else:
                    argv += ['--pack-only']
                return argv

            jobs = [('default-off', command('default-off', design), None),
                    ('clustered-pack', command('clustered-pack', design, declaration), None),
                    ('routed-seed1', command('routed-seed1', design, declaration, True), None),
                    ('routed-seed2', command('routed-seed2', design, declaration, True), None)]
            jobs[3][1][jobs[3][1].index('--seed') + 1] = '2'
            for name, cell, change, message in [
                    ('missing-annotation', 'rq0', 'annotation', 'Mailbox synchronizer ASYNC_REG annotation missing'),
                    ('wrong-clock', 'rq1', 'clock', 'Mailbox synchronizer clock, edge or control set differs'),
                    ('early-fanout', 'rq0', 'fanout', 'An early mailbox synchronizer stage feeds other logic'),
                    ('wrong-connection', 'rq2', 'connection', 'Mailbox synchronizer stages are not directly connected')]:
                bad = json.loads(json.dumps(design))
                t = bad['modules']['sync_probe']
                if change == 'annotation': t['netnames'][cell + '_q']['attributes'] = {}
                if change == 'clock': t['cells'][cell]['connections']['C'] = [5]
                if change == 'fanout': t['cells']['rs2']['connections']['D'] = [11]
                if change == 'connection': t['cells'][cell]['connections']['D'] = [10]
                jobs.append((name, command(name, bad, declaration), message))
            save(stage='parallel-native-placement-cases', clock_sources='STANDIN_LUTS_NOT_FUNCTIONAL_BOARD_CLOCKS')
        print(f'RUNNING {len(jobs)} synchronizer cases with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(run, jobs))
        if previous:
            wanted = json.loads(contract.read_text())['synchronizers']
            actual = audit_clusters(out / 'full.clusters.json', wanted)
            if domain_rows(out / 'full.domains.tsv') != domain_rows(previous / 'full-analysis.domains.tsv'):
                raise ValueError('Placement-only import changed phase budgets')
            comparison = {'chains': len(actual), 'annotated_ffs': sum(len(stages) for stages in actual.values()),
                          'actual_relative_offsets': [0, 16, 32], 'phase_budget_changes': 0, 'physical_placement': 'PENDING_FULL_IMPLEMENTATION'}
        else:
            comparison = {}
            for name in ('default-off', 'clustered-pack', 'routed-seed1', 'routed-seed2'):
                design = json.loads((out / (name + '.packed.json')).read_text())
                top = next(iter(design['modules'].values()))
                selected = {cell: top['cells'][cell] for cell in ['rq0', 'rq1', 'rq2', 'rs0', 'rs1', 'rs2']}
                if name == 'default-off':
                    if any('X_MAILBOX_SYNC_ROOT' in cell['attributes'] for cell in selected.values()):
                        raise ValueError('Default-off import changed clusters')
                else:
                    if any(cell['attributes'].get('ASYNC_REG') != 'TRUE' for cell in selected.values()):
                        raise ValueError('Cell annotations missing')
                    audit_clusters(out / (name + '.clusters.json'), declaration['synchronizers'])
                if name in ('routed-seed1', 'routed-seed2'):
                    for prefix in ('rq', 'rs'):
                        bels = [selected[prefix + str(i)]['attributes']['NEXTPNR_BEL'] for i in range(3)]
                        if len({b.split('/')[0] for b in bels}) != 1 or any(b.split('/')[1] not in ('AFF', 'BFF', 'CFF', 'DFF') for b in bels):
                            raise ValueError('Actual placed stages leave their primary-FF slice')
                        comparison[name + '-' + prefix] = bels
        shutil.copy2(__file__, out / 'helper.py')
        save(status='FULL_MAILBOX_SYNC_CLUSTER_PACK_PASS_ROUTED_PLACEMENT_PENDING' if previous else 'ALL_NATIVE_MAILBOX_SYNC_PLACEMENT_CASES_PASS',
             native_results=results, comparison=comparison, completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'native_results': results, 'comparison': comparison}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('previous', 'contract', 'gate'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or len({bool(args.previous), bool(args.contract), bool(args.gate)}) != 1:
        parser.error('Use one to eight workers; supply previous/contract/gate together')
    check(args.backend.resolve(), args.out.resolve(), args.workers,
          args.previous.resolve() if args.previous else None, args.contract.resolve() if args.contract else None,
          args.gate.resolve() if args.gate else None)


if __name__ == '__main__':
    main()
