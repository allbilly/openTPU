#!/usr/bin/env python3
"""Check actual mailbox slack semantics and all complete-design endpoints."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_mailbox_sync_check import CHIPDB, fixture
from openxc7_phase_engine_check import domain_rows


def check(backend: Path, out: Path, workers: int, previous: Path | None, contract: Path | None, gate: Path | None):
    b = json.loads(backend.read_text())
    if b['status'] != 'MAILBOX_DATAPATH_BUILD_PASS_NATIVE_VALIDATION_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Expected completed unchanged mailbox datapath backend')
    gold = json.loads(Path(b['vendor_gate']['path']).read_text())
    if describe(b['vendor_gate']['path']) != b['vendor_gate'] or gold['comparison']['payload_paths'] != 1103:
        raise ValueError('Vendor requirements changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'helper': describe(__file__), 'workers': workers, 'vendor_gate': b['vendor_gate'],
            'scope': 'DIRECT_DATAPATH_SLACK_SEMANTICS_UNPLACED_GENERIC_FF_NUMERICS_NOT_QUALIFIED',
            'hardware_accessed': False, 'live_full_route_changed': False}

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
                raise ValueError('Expected datapath rejection failed: ' + name)
        elif code:
            raise RuntimeError('Native datapath case failed: ' + name)
        return name, code

    def rows(name):
        return {row['capture']: row for row in json.loads((out / (name + '.datapath.json')).read_text())}

    try:
        if previous:
            p = json.loads((previous / 'manifest.json').read_text())
            g = json.loads(gate.read_text())
            if (p['status'] != 'FULL_MAILBOX_SYNC_CLUSTER_PACK_PASS_ROUTED_PLACEMENT_PENDING' or p['backend'] != b['previous']
                    or g['status'] != 'ALL_NATIVE_DIRECT_MAILBOX_DATAPATH_SEMANTIC_CASES_PASS' or g['backend'] != describe(backend)):
                raise ValueError('Complete source or native gate ancestry mismatch')
            for item in p['full_inputs'].values():
                if describe(item['path']) != item:
                    raise ValueError('Pinned complete source changed')
            argv = json.loads((previous / 'full-pack.command.json').read_text())
            argv[0] = b['binary']['path']
            for i, arg in enumerate(argv):
                if arg.startswith('phase-domain-audit='): argv[i] = 'phase-domain-audit=' + str(out / 'full.domains.tsv')
                if arg.startswith('phase-path-audit='): argv[i] = 'phase-path-audit=' + str(out / 'full.paths.json')
                if arg.startswith('mailbox-sync-audit='): argv[i] = 'mailbox-sync-audit=' + str(out / 'full.clusters.json')
            argv += ['-o', 'mailbox-datapath-contract=' + str(contract), '-o', 'mailbox-datapath-audit=' + str(out / 'full.datapath.json')]
            save(stage='complete-native-intrinsic-datapath-analysis', profile=p['profile'], full_inputs=p['full_inputs'],
                 native_gate=describe(gate), contract=describe(contract))
            jobs = [('full', argv, None)]
        else:
            design, sync = fixture()
            top = design['modules']['sync_probe']
            bounds = []
            for role, source_clock, capture_clock, bit, maximum in [('request', 5, 4, 40, 20000), ('response', 4, 5, 42, 300000)]:
                for name, clk, d, q in [('source_' + role, source_clock, '0', bit), ('capture_' + role, capture_clock, bit, bit + 1)]:
                    top['cells'][name] = {'hide_name': 0, 'type': 'FDRE', 'parameters': {'INIT': '0', 'IS_C_INVERTED': '0'}, 'attributes': {},
                                         'port_directions': {'C': 'input', 'CE': 'input', 'D': 'input', 'Q': 'output', 'R': 'input'},
                                         'connections': {'C': [clk], 'CE': ['1'], 'R': ['0'], 'D': [d], 'Q': [q]}}
                    top['netnames'][name + '_q'] = {'hide_name': 0, 'bits': [q], 'attributes': {}}
                bounds.append({'source_cell': 'source_' + role, 'source_port': 'Q', 'source_net': 'source_' + role + '_q',
                               'source_clock': 'tck' if source_clock == 5 else 'core_clk', 'capture_cell': 'capture_' + role,
                               'capture_port': 'D', 'capture_clock': 'tck' if capture_clock == 5 else 'core_clk', 'max_delay_ps': maximum})
            declaration = {'schema': 1, 'part': 'xc7k480tffg1156-2',
                           'runtime_assumption': 'ONE_OUTSTANDING_COMMAND_SOURCE_PAYLOAD_HELD_UNTIL_MATCHING_RESPONSE_IS_RECEIVED',
                           'cell_path_delay_definition': 'SOURCE_CLOCK_TO_Q_PLUS_DATA_ROUTE_PLUS_CAPTURE_SETUP_CLOCK_SKEW_AND_JITTER_EXCLUDED',
                           'payload_bounds': bounds}
            xdc = out / 'probe.xdc'
            xdc.write_text('create_clock -period 10 [get_nets {core_clk}]\ncreate_clock -period 166.666667 [get_nets {tck}]\n')

            def command(name, design=design, declaration=declaration, delays=None):
                src = out / (name + '.json'); src.write_text(json.dumps(design, separators=(',', ':')) + '\n')
                argv = [b['binary']['path'], '--chipdb', CHIPDB, '--device', 'xc7k480tffg1156-2', '--json', str(src),
                        '-o', 'xdc=' + str(xdc), '--pack-only', '--threads', '8', '--freq', '100', '--seed', '1',
                        '-o', 'clock-vivado-timing=on', '-o', 'clock-feedback-vivado=on', '-o', 'clock-family-vivado=on',
                        '-o', 'phase-engine-vivado=on', '-o', 'phase-analysis-after-pack=on',
                        '-o', 'phase-path-audit=' + str(out / (name + '.paths.json')), '--write', str(out / (name + '.packed.json'))]
                if declaration is not None:
                    path = out / (name + '.contract.json'); path.write_text(json.dumps(declaration, indent=2) + '\n')
                    argv += ['-o', 'mailbox-datapath-contract=' + str(path), '-o', 'mailbox-datapath-audit=' + str(out / (name + '.datapath.json'))]
                if delays:
                    argv += ['-o', 'mailbox-datapath-probe-delays=' + delays]
                return argv

            jobs = [('default-off', command('default-off', declaration=None), None),
                    ('baseline', command('baseline'), None),
                    ('clock-only', command('clock-only', delays='0,100000,25000'), None),
                    ('data-delay', command('data-delay', delays='40000,0,0'), None),
                    ('data-and-clocks', command('data-and-clocks', delays='40000,100000,25000'), None)]
            stale = json.loads(json.dumps(design))
            stale['modules']['sync_probe']['cells']['source_request']['attributes']['X_MAILBOX_DP_TARGET'] = 'capture_request'
            stale['modules']['sync_probe']['cells']['capture_request']['attributes'].update({
                'X_MAILBOX_DP_SOURCE': 'source_request', 'X_MAILBOX_DP_MAX_PS': format(20000, '064b')})
            jobs.append(('stale-input', command('stale-input', design=stale, declaration=None), None))
            related = json.loads(json.dumps(design)); related['modules']['sync_probe']['cells']['capture_request']['connections']['C'] = [5]
            related_contract = json.loads(json.dumps(declaration)); related_contract['payload_bounds'][0]['capture_clock'] = 'tck'
            jobs.append(('related-clock', command('related-clock', design=related, declaration=related_contract),
                         'Mailbox datapath-only contract cannot replace related-clock timing'))
            for name, field, value, message in [
                    ('wrong-net', 'source_net', 'absent', 'Mailbox datapath connection, clock or FF mode differs'),
                    ('fractional-maximum', 'max_delay_ps', 20000.5, 'Mailbox datapath maximum must be a positive finite integer')]:
                bad = json.loads(json.dumps(declaration)); bad['payload_bounds'][0][field] = value
                jobs.append((name, command(name, declaration=bad), message))
            bad = json.loads(json.dumps(declaration)); bad['payload_bounds'].append(bad['payload_bounds'][0])
            jobs.append(('duplicate', command('duplicate', declaration=bad), 'Mailbox datapath has duplicate or nonunique source/capture mapping'))
            tagged = json.loads(json.dumps(design)); tagged['modules']['sync_probe']['netnames']['capture_request_q']['attributes']['ASYNC_REG'] = 'TRUE'
            jobs.append(('tagged-synchronizer', command('tagged-synchronizer', design=tagged), 'Mailbox payload limits cannot tag a synchronizer stage'))
            save(stage='parallel-native-slack-and-report-cases')
        print(f'RUNNING {len(jobs)} mailbox datapath cases with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            codes = dict(pool.map(run, jobs))
        if previous:
            actual = rows('full'); expected = {row['capture_cell']: row for row in json.loads(contract.read_text())['payload_bounds']}
            if set(actual) != set(expected) or len(actual) != 1103:
                raise ValueError('Complete datapath endpoint coverage differs')
            for name, row in actual.items():
                if row['source'] != expected[name]['source_cell'] or row['maximum_ps'] != expected[name]['max_delay_ps']:
                    raise ValueError('Complete endpoint requirement differs from vendor contract')
                if row['capture_slack_ps'] != row['source_slack_ps'] or row['capture_slack_ps'] <= 0:
                    raise ValueError('Complete intrinsic direct source/capture slack differs')
            if domain_rows(out / 'full.domains.tsv') != domain_rows(previous / 'full.domains.tsv'):
                raise ValueError('Payload import changed nominal phase budgets')
            if json.loads((out / 'full.clusters.json').read_text()) != json.loads((previous / 'full.clusters.json').read_text()):
                raise ValueError('Payload import changed synchronizer clusters')
            comparison = {'endpoints': len(actual), 'request_endpoints': sum(row['maximum_ps'] == 20000 for row in actual.values()),
                          'response_endpoints': sum(row['maximum_ps'] == 300000 for row in actual.values()),
                          'minimum_intrinsic_slack_ps': min(row['capture_slack_ps'] for row in actual.values()),
                          'phase_budget_changes': 0, 'synchronizer_cluster_changes': 0, 'geometry': 'UNPLACED_ZERO_DATA_ROUTE'}
        else:
            for variant in ('default-off', 'stale-input'):
                cleared = json.loads((out / (variant + '.packed.json')).read_text())
                cells = next(iter(cleared['modules'].values()))['cells']
                if any(key.startswith('X_MAILBOX_DP_') for cell in cells.values() for key in cell['attributes']):
                    raise ValueError('No-contract replay retained payload timing tags')
            baseline = rows('baseline'); clocks = rows('clock-only'); delayed = rows('data-delay'); combined = rows('data-and-clocks')
            if set(baseline) != {'capture_request', 'capture_response'} or clocks != baseline or combined != delayed:
                raise ValueError('Clock route delays affected datapath-only slack or criticality')
            for name, row in baseline.items():
                if row['maximum_ps'] != (20000 if name == 'capture_request' else 300000):
                    raise ValueError('Native maximum differs from vendor requirements')
                if row['source_slack_ps'] != row['capture_slack_ps'] or delayed[name]['capture_slack_ps'] != row['capture_slack_ps'] - 40000:
                    raise ValueError('Data route slack sensitivity differs')
            for variant in ('data-delay', 'data-and-clocks'):
                req = rows(variant)['capture_request']
                if req['capture_slack_ps'] >= 0 or req['source_criticality'] <= 0 or req['capture_criticality'] <= 0:
                    raise ValueError('Violation does not drive source/capture criticality')
                paths = json.loads((out / (variant + '.paths.json')).read_text())['paths']
                found = [path for path in paths if any(s['to']['cell'] == 'capture_request' and s['type'] == 'setup' for s in path['segments'])]
                if len(found) != 1 or found[0]['requirement_ps'] != 20000:
                    raise ValueError('Failed direct path requirement differs')
                segments = found[0]['segments']
                if any(s['type'] in ('clk-to-clk', 'clk-skew') for s in segments):
                    raise ValueError('Datapath report includes a clock contribution')
                if sum(s['delay_ps'] for s in segments) != req['maximum_ps'] - req['capture_slack_ps']:
                    raise ValueError('Path report disagrees with analyser slack')
            comparison = {'baseline': baseline, 'delayed': delayed, 'clock_route_invariance': True, 'data_route_delta_ps': 40000,
                          'negative_slack_criticality_and_report': 'PASS', 'generic_ff_numerical_calibration': 'PENDING'}
        shutil.copy2(__file__, out / 'helper.py')
        save(status='FULL_UNPLACED_MAILBOX_DATAPATH_LIMITS_PASS_ROUTED_NUMERICS_PENDING' if previous else 'ALL_NATIVE_DIRECT_MAILBOX_DATAPATH_SEMANTIC_CASES_PASS',
             native_results=codes, comparison=comparison, completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': comparison, 'native_results': codes}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'out'): parser.add_argument('--' + name, type=Path, required=True)
    for name in ('previous', 'contract', 'gate'): parser.add_argument('--' + name, type=Path)
    parser.add_argument('--workers', type=int, default=8); args = parser.parse_args()
    if not 1 <= args.workers <= 8 or len({bool(args.previous), bool(args.contract), bool(args.gate)}) != 1:
        parser.error('Use one to eight workers; supply previous/contract/gate together')
    check(args.backend.resolve(), args.out.resolve(), args.workers, args.previous.resolve() if args.previous else None,
          args.contract.resolve() if args.contract else None, args.gate.resolve() if args.gate else None)


if __name__ == '__main__':
    main()
