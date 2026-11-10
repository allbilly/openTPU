#!/usr/bin/env python3
"""Validate actual conditional timing budgets and unchanged full-design scope."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phase_engine_check import domain_rows


SCOPE = 'SOFTWARE_PHASE_BOUND_CONTRACT_NOT_HARDWARE_ENFORCED'


def contract(groups, root):
    return {'schema': 1, 'scope': SCOPE, 'part': 'xc7k480tffg1156-2',
            'runtime_assumption': 'WRAPPED_CALIBRATION_RAW_CSR_WRITES_EXCLUDED',
            'groups': [{'dynamic_group': name, 'root': root, 'vco_hz': 800000000,
                        'min_offset_ps': -1250, 'max_offset_ps': 1250} for name in groups]}


def check(backend: Path, previous: Path, out: Path, workers: int, full: bool, native_gate: Path | None):
    b = json.loads(backend.read_text())
    if b['status'] != 'SOFTWARE_PHASE_BOUND_BUILD_PASS_NATIVE_VALIDATION_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Expected unchanged completed phase-bound backend')
    vendor = json.loads(Path(b['vendor_gate']['path']).read_text())
    if describe(b['vendor_gate']['path']) != b['vendor_gate'] or vendor['status'] != 'ALL_18_VENDOR_PHASE_BOUND_SNAPSHOT_PATHS_PASS':
        raise ValueError('Vendor snapshot gate changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'helper': describe(__file__), 'workers': workers, 'vendor_gate': b['vendor_gate'],
            'scope': 'CONDITIONAL_SOFTWARE_BUDGETS_UNPLACED_NOT_ROUTED_SKEW_JITTER_OR_HARDWARE_PROOF',
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
                raise ValueError('Native contract rejection failed: ' + name)
            return name, {'native_exit': code, 'expected_rejection': rejection}
        if code:
            raise RuntimeError('Native conditional analysis failed: ' + name)
        return name, {'native_exit': code}

    def command(name, input_file=None, value=None):
        argv = list(template)
        argv[0] = b['binary']['path']
        if '--write' in argv:
            i = argv.index('--write')
            del argv[i:i + 2]
        if input_file:
            argv[argv.index('--json') + 1] = str(input_file)
        for i, item in enumerate(argv):
            if item.startswith('phase-domain-audit='):
                argv[i] = 'phase-domain-audit=' + str(out / (name + '.domains.tsv'))
            if item.startswith('phase-path-audit='):
                argv[i] = 'phase-path-audit=' + str(out / (name + '.paths.json'))
        if not any(item.startswith('phase-path-audit=') for item in argv):
            argv += ['-o', 'phase-path-audit=' + str(out / (name + '.paths.json'))]
        if value is not None:
            path = out / (name + '.contract.json')
            path.write_text(json.dumps(value, indent=2) + '\n')
            argv += ['-o', 'phase-bound-contract=' + str(path)]
        return argv

    try:
        if full:
            prior = json.loads((previous / 'manifest.json').read_text())
            gate = json.loads(native_gate.read_text())
            if (prior['status'] != 'FULL_UNPLACED_UNKNOWN_PATH_EXPORT_PASS_CDC_REVIEW_PENDING' or b['previous'] != prior['backend']
                    or gate['status'] != 'ALL_NATIVE_SOFTWARE_PHASE_CONTRACT_CASES_PASS' or gate['backend'] != describe(backend)):
                raise ValueError('Full source or native gate ancestry mismatch')
            for item in prior['full_inputs'].values():
                if describe(item['path']) != item:
                    raise ValueError('Pinned full source changed')
            template = json.loads((previous / 'full-analysis.command.json').read_text())
            value = contract(['u_ld.ldmmcm0', 'u_ld.ldmmcm1'], 'SYS_CLK')
            value['software_review'] = b['software_review']
            save(stage='full-conditional-intrinsic-analysis', profile=prior['profile'], full_inputs=prior['full_inputs'],
                 native_gate=describe(native_gate), previous_check=describe(previous / 'manifest.json'))
            jobs = [('full-analysis', command('full-analysis', value=value), None)]
        else:
            template = json.loads((previous / 'baseline.command.json').read_text())
            design = json.loads((previous / 'baseline.json').read_text())
            top = design['modules']['phase_edges']
            bit = max(bit for item in top['netnames'].values() for bit in item['bits'] if isinstance(bit, int)) + 1
            primary = top['netnames']['primary']['bits'][0]
            fine = top['netnames']['c0']['bits'][0]
            for i, (case, source, target, se, te) in enumerate([('ddr_command', primary, fine, 1, 0), ('ddr_reverse', fine, primary, 0, 1)]):
                data_bit = top['netnames']['data']['bits'][i]
                for role, clock, edge, d, q in [('launch', source, se, data_bit, bit), ('capture', target, te, bit, bit + 1)]:
                    name = role + '_' + case
                    top['cells'][name] = {'hide_name': 0, 'type': 'FDRE', 'parameters': {'IS_C_INVERTED': str(edge)},
                                         'attributes': {'DONT_TOUCH': 'TRUE', 'src': str(Path(b['vendor_gate']['path']).parent / 'phase_bounds.v')},
                                         'port_directions': {'C': 'input', 'CE': 'input', 'D': 'input', 'Q': 'output', 'R': 'input'},
                                         'connections': {'C': [clock], 'CE': ['1'], 'R': ['0'], 'D': [d], 'Q': [q]}}
                    top['netnames'][name + '_q'] = {'hide_name': 0, 'bits': [q], 'attributes': {}}
                bit += 2
            fixture = out / 'phase-bound-fixture.json'
            fixture.write_text(json.dumps(design, separators=(',', ':')) + '\n')
            value = contract(['phy_03'], 'primary')
            jobs = [('unbounded', command('unbounded', fixture), None), ('bounded', command('bounded', fixture, value), None)]
            stale = json.loads(json.dumps(design))
            for net in ('c0', 'c1'):
                stale['modules']['phase_edges']['netnames'][net]['attributes'].update({
                    'X_VIVADO_PHASE_BOUND_VALID': format(1, '032b'),
                    'X_VIVADO_PHASE_BOUND_MIN_PS': format((-1250) & ((1 << 64) - 1), '064b'),
                    'X_VIVADO_PHASE_BOUND_MAX_PS': format(1250, '064b')})
            stale_file = out / 'stale-input-bounds.json'
            stale_file.write_text(json.dumps(stale, separators=(',', ':')) + '\n')
            jobs.append(('stale-input-bounds', command('stale-input-bounds', stale_file), None))
            alternate = json.loads(json.dumps(design))
            alternate['modules']['phase_edges']['cells']['phy_03']['connections']['CLKINSEL'] = ['0']
            alternate_file = out / 'alternate-input.json'
            alternate_file.write_text(json.dumps(alternate, separators=(',', ':')) + '\n')
            jobs.append(('alternate-input', command('alternate-input', alternate_file, value), 'Software phase contract requires confirmed CLKIN1 selection'))
            zero = json.loads(json.dumps(value))
            zero['groups'][0].update(min_offset_ps=0, max_offset_ps=0)
            wide = json.loads(json.dumps(value))
            wide['groups'][0].update(min_offset_ps=-6000, max_offset_ps=6000)
            jobs += [('zero-bound', command('zero-bound', fixture, zero), None),
                     ('capture-edge-crossing', command('capture-edge-crossing', fixture, wide), None)]
            for name, field, data, message in [
                    ('wrong-root', 'root', 'unrelated', 'Software phase contract root differs'),
                    ('unmatched-group', 'dynamic_group', 'absent', 'Software phase group has no matching MMCM'),
                    ('stale-vco', 'vco_hz', 799000000, 'Software phase contract VCO differs'),
                    ('fractional-bound', 'min_offset_ps', -1250.5, 'Software phase bound must be a finite integer')]:
                bad = json.loads(json.dumps(value))
                bad['groups'][0][field] = data
                jobs.append((name, command(name, fixture, bad), message))
            argv = command('engine-off', fixture, value)
            argv[argv.index('phase-engine-vivado=on')] = 'phase-engine-vivado=off'
            argv = [item for item in argv if not item.startswith('phase-domain-audit=')]
            # Remove the orphan -o that preceded the removed audit option.
            argv = [item for i, item in enumerate(argv) if not (item == '-o' and i + 1 < len(argv) and argv[i + 1] == '-o')]
            jobs.append(('engine-off', argv, 'Software phase contract requires phase-engine-vivado=on'))
            save(stage='parallel-native-conditional-cases', previous_fixture=describe(previous / 'baseline.json'))
        print(f'RUNNING {len(jobs)} native software-contract cases with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(run, jobs))
        if full:
            rows = domain_rows(out / 'full-analysis.domains.tsv')
            old = domain_rows(previous / 'full-analysis.domains.tsv')
            expected_pairs = {('core_clk', 'falling', 'u_ld.sysc0_clk', 'rising'), ('core_clk', 'falling', 'u_ld.sysc1_clk', 'rising')}
            for pair, value in rows.items():
                if pair in expected_pairs:
                    if value != {'known': 1, 'setup': 3750, 'hold': -3750, 'status': 'CONDITIONAL_SOFTWARE_PHASE_BOUND'}:
                        raise ValueError('Complete DDR conditional budget differs')
                elif value != old[pair]:
                    raise ValueError('Unrelated complete domain budget changed')
            if set(rows) != set(old) or len(rows) != 18 or sum(value['known'] for value in rows.values()) != 16:
                raise ValueError('Complete conditional domain scope differs')
            checks = {'domain_pairs': 18, 'known_pairs': 16, 'conditional_pairs': 2, 'unrelated_pairs': 2}
            names = ['full-analysis']
        else:
            expected_pairs = {('primary', 'falling', 'c0', 'rising'), ('c0', 'rising', 'primary', 'falling')}
            checks = {}
            for name, known, setup, hold, status in [('unbounded', 0, 0, 0, 'DYNAMIC_RELATIVE_PHASE'),
                                                    ('stale-input-bounds', 0, 0, 0, 'DYNAMIC_RELATIVE_PHASE'),
                                                    ('bounded', 1, 3750, -3750, 'CONDITIONAL_SOFTWARE_PHASE_BOUND'),
                                                    ('zero-bound', 1, 5000, -5000, 'CONDITIONAL_SOFTWARE_PHASE_BOUND'),
                                                    ('capture-edge-crossing', 0, 0, 0, 'SOFTWARE_BOUND_INTERVAL_CROSSES_CAPTURE_EDGE')]:
                rows = domain_rows(out / (name + '.domains.tsv'))
                for pair in expected_pairs:
                    if rows[pair] != {'known': known, 'setup': setup, 'hold': hold, 'status': status}:
                        raise ValueError('Actual native conditional budget differs: ' + name)
                same_group = rows[('c0', 'rising', 'c1', 'rising')]
                if same_group != {'known': 1, 'setup': 2500, 'hold': 0, 'status': 'NOMINAL_COMMON_PHASE_GROUP'}:
                    raise ValueError('Common phase-group cancellation changed')
                checks[name] = {'domain_pairs': len(rows), 'conditional_setup_ps': setup, 'conditional_hold_ps': hold, 'status': status}
            names = ['bounded']
        for name in names:
            reports = json.loads((out / (name + '.paths.json')).read_text())['paths']
            seen = set()
            for path in reports:
                pair = (path['launch'], path['launch_edge'], path['capture'], path['capture_edge'])
                if pair in expected_pairs:
                    if path['requirement_ps'] != vendor['comparison']['conditional_ddr_setup_budget_ps']:
                        raise ValueError('Actual critical-path requirement differs from vendor snapshot envelope')
                    seen.add(pair)
            if seen != expected_pairs:
                raise ValueError('Conditional path report scope incomplete')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='FULL_UNPLACED_SOFTWARE_PHASE_CONTRACT_PASS_ROUTED_TIMING_PENDING' if full else 'ALL_NATIVE_SOFTWARE_PHASE_CONTRACT_CASES_PASS',
             results=results, comparison=checks, completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': checks, 'results': results}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'previous', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--native-gate', type=Path)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8 or bool(args.native_gate) != args.full:
        parser.error('Use one to eight workers; full mode requires a native gate')
    check(args.backend.resolve(), args.previous.resolve(), args.out.resolve(), args.workers, args.full,
          args.native_gate.resolve() if args.native_gate else None)


if __name__ == '__main__':
    main()
