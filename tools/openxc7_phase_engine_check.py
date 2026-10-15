#!/usr/bin/env python3
"""Check actual timing-analyser edge budgets against vendor register paths."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import csv
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phase_edge_vivado import CASES, expected


CHIPDB = expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin')


def domain_rows(path):
    result = {}
    with path.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            key = (row['launch'], row['launch_edge'], row['capture'], row['capture_edge'])
            if key in result: raise ValueError('Duplicate actual domain pair')
            result[key] = {'known': int(row['known']), 'setup': int(row['setup_budget_ps']),
                           'hold': int(row['hold_edge_ps']), 'status': row['status']}
    return result


def compare(path, scenario, changed=None, missing=False):
    rows = domain_rows(path); checked = []
    for case in CASES:
        name, source, se, target, te = case
        if changed and name == 'common_fine_phase': target = changed[0]
        key = (source, 'falling' if se else 'rising', target, 'falling' if te else 'rising')
        if key not in rows: raise ValueError('Actual analyser domain pair missing: ' + repr(key))
        row = rows[key]
        unknown = 'UNKNOWN_WAVEFORM' if missing else changed[1] if changed and name == 'common_fine_phase' else None
        if unknown:
            if row != {'known': 0, 'setup': 0, 'hold': 0, 'status': unknown}:
                raise ValueError('Unknown edge relationship received a budget: ' + repr((key, row)))
        else:
            wanted = expected(scenario, case)
            if row != {'known': 1, 'setup': int(wanted['max']), 'hold': int(wanted['min']), 'status': 'NOMINAL_COMMON_PHASE_GROUP'}:
                raise ValueError('Actual analyser budget differs from vendor path: ' + repr((key, row, wanted)))
        checked.append({'case': name, 'domain': key, **row})
    return {'domain_pairs_checked': len(checked), 'known_cases': sum(r['known'] for r in checked),
            'unknown_cases': sum(not r['known'] for r in checked), 'mismatches': 0, 'rows': checked}


def check(backend, vendor_gate, characterization, out, workers=8, source=None, gate=None):
    b = json.loads(backend.read_text()); gold = json.loads(vendor_gate.read_text())
    if b['status'] != 'PHASE_ENGINE_BUILD_PASS_NATIVE_ANALYSER_VALIDATION_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Expected completed, unchanged phase engine')
    if gold['status'] != 'ALL_40_VENDOR_REGISTER_EDGE_RELATIONS_MATCH_EXACT_ARITHMETIC_ENGINE_PENDING' or gold['comparison']['mismatches']:
        raise ValueError('Actual vendor edge paths did not pass')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend), 'binary': b['binary'],
            'vendor_gate': describe(vendor_gate), 'helper': describe(__file__), 'workers': workers,
            'scope': 'ACTUAL_UNPLACED_INTRINSIC_ANALYSER_NOMINAL_BUDGETS_NOT_ROUTED_BOARD_TIMING',
            'hardware_accessed': False, 'live_full_route_changed': False, 'numerical_timing': 'NOT_QUALIFIED'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT); code = child.wait()
        (out / (stage + '.exit')).write_text(str(code) + '\n'); return stage, code
    def command(path, xdc, audit=None, mode='on', packed=None, full=False):
        argv = [b['binary']['path'], '--chipdb', CHIPDB, '--device', 'xc7k480tffg1156-2', '--json', str(path), '-o', 'xdc=' + str(xdc),
                '--pack-only', '--threads', '8', '--freq', '100.0', '--seed', '1', '-o', 'clock-vivado-timing=on',
                '-o', 'clock-feedback-vivado=on', '-o', 'clock-family-vivado=on', '-o', 'phase-engine-vivado=' + mode]
        if audit: argv += ['-o', 'phase-domain-audit=' + str(audit), '-o', 'phase-analysis-after-pack=on']
        if packed: argv += ['--write', str(packed)]
        if full: argv += ['-o', 'dsp-vivado-timing=on', '-o', 'serdes-vivado-timing=on']
        return argv
    try:
        save(stage='prepare')
        if source:
            g = json.loads(gate.read_text())
            if g['status'] != 'ALL_NATIVE_PHASE_ENGINE_CASES_MATCH_VENDOR_EDGES_FULL_DESIGN_PENDING' or g['backend'] != describe(backend):
                raise ValueError('Phase-engine configuration gates do not match backend')
            old = json.loads((source.parent.parent / 'full-packed-dsp-inventory-20261011T223120Z/manifest.json').read_text())
            for name in ('constrained.json', 'openxc7.xdc'):
                if describe(source / name) != old['inputs'][name]: raise ValueError('Pinned full source changed')
            audit = out / 'full-phase-domains.tsv'; save(stage='full-native-intrinsic-analysis', profile=old['profile'], full_inputs=old['inputs'], gate=describe(gate))
            print('FULL_UNPLACED_PHASE_ANALYSIS_STARTED ' + str(out), flush=True)
            _, code = run('full-analysis', command(source / 'constrained.json', source / 'openxc7.xdc', audit, full=True)); save(native_exit=code)
            if code: raise RuntimeError('Complete intrinsic phase analysis failed')
            rows = domain_rows(audit)
            known = [r for r in rows.values() if r['known']]
            if not known: raise ValueError('Complete analyser has no known phase relationships')
            if any(r['setup'] <= 0 or r['hold'] > 0 for r in known): raise ValueError('Invalid complete phase budget')
            summary = {'domain_pairs': len(rows), 'known_pairs': len(known), 'unknown_pairs': len(rows) - len(known),
                       'unknown_reasons': {status: sum(r['status'] == status for r in rows.values()) for status in sorted({r['status'] for r in rows.values() if not r['known']})},
                       'smallest_setup_budget_ps': min(r['setup'] for r in known), 'geometry': 'UNPLACED_INTRINSIC_ONLY'}
            save(status='FULL_UNPLACED_PHASE_DOMAIN_ANALYSIS_PASS_ROUTED_SKEW_AND_WHOLE_TIMING_PENDING', comparison=summary, audit=describe(audit))
        else:
            rtl = vendor_gate.parent / 'phase_edges.v'; raw = out / 'probe.yosys.json'
            script = f'read_verilog -lib +/xilinx/cells_sim.v; read_verilog -lib +/xilinx/cells_xtra.v; read_verilog {rtl}; hierarchy -check -top phase_edges; select phase_edges; write_json -selected {raw}'
            _, code = run('yosys', ['yosys', '-p', script])
            if code: raise RuntimeError('Phase register fixture elaboration failed')
            design = json.loads(raw.read_text()); top = design['modules']['phase_edges']
            config = next(c for c in json.loads((characterization / 'configurations.json').read_text())['configs'] if c['probe_cell'] == 'phy_03')
            mmcm = top['cells']['phy_03']; mmcm['type'] = config['packed_type']; connections, directions = {}, {}
            for pin, bits in mmcm['connections'].items():
                for i, bit in enumerate(bits):
                    name = pin + (str(i) if len(bits) > 1 else '')
                    connections[name] = [bit]; directions[name] = mmcm['port_directions'][pin]
            mmcm['connections'] = connections; mmcm['port_directions'] = directions
            mmcm['connections']['CLKINSEL'] = ['1']; mmcm['connections']['CLKIN2'] = ['0']
            input_bits = {bit for p in top['ports'].values() if p['direction'] == 'input' for bit in p['bits'] if isinstance(bit, int)}
            secondary, = top['ports']['secondary']['bits']
            c3, = top['netnames']['c3']['bits']
            for bit in input_bits:
                top['cells'][f'fixture_driver_{bit}'] = {'hide_name': 0, 'type': 'LUT1', 'parameters': {'INIT': '10'}, 'attributes': {'keep': '1'},
                    'port_directions': {'I0': 'input', 'O': 'output'}, 'connections': {'I0': ['0'], 'O': [bit]}}
            top['ports'] = {}
            def case(name, value, xdc_text, mode='on', rejection=None):
                path = out / (name + '.json'); path.write_text(json.dumps(value, separators=(',', ':')) + '\n')
                xdc = out / (name + '.xdc'); xdc.write_text(xdc_text)
                audit = out / (name + '.domains.tsv') if not rejection and mode == 'on' else None
                packed = out / (name + '.packed.json') if not rejection else None
                return {'name': name, 'audit': audit, 'packed': packed, 'rejection': rejection,
                        'command': command(path, xdc, audit, mode, packed)}
            baseline = 'create_clock -period 10 [get_nets {primary}]\n'
            shifted = 'create_clock -period 10 -waveform {1.25 3.75} [get_nets {primary}]\n'
            jobs = [case('baseline', design, baseline), case('shifted', design, shifted)]
            dynamic = json.loads(json.dumps(design)); dynamic['modules']['phase_edges']['cells']['capture_common_fine_phase']['connections']['C'] = [c3]
            unrelated = json.loads(json.dumps(design)); unrelated['modules']['phase_edges']['cells']['capture_common_fine_phase']['connections']['C'] = [secondary]
            jobs += [case('dynamic-relative-phase', dynamic, baseline),
                     case('unrelated-source', unrelated, baseline + 'create_clock -period 10 [get_nets {secondary}]\n'),
                     case('missing-source', design, ''), case('default-off', design, baseline, mode='off'),
                     case('invalid-option', design, baseline, mode='maybe', rejection='phase-engine-vivado must be on or off'),
                     case('audit-with-engine-off', design, baseline, mode='off', rejection='Phase-domain audit requires phase-engine-vivado=on')]
            jobs[-1]['command'] += ['-o', 'phase-domain-audit=' + str(out / 'invalid-audit.tsv')]
            save(stage='parallel-native-analyser-cases', fixture_rtl=describe(rtl), fixture_drivers=len(input_bits))
            print(f'RUNNING {len(jobs)} native phase-analyser cases with {workers} workers', flush=True)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = dict(pool.map(lambda job: run(job['name'], job['command']), jobs))
            save(native_results=results); comparisons = {}
            for job in jobs:
                name = job['name']; rejection = job['rejection']
                if rejection:
                    if results[name] != 125 or rejection not in (out / (name + '.log')).read_text(): raise ValueError('Native phase rejection failed: ' + name)
                    continue
                if results[name]: raise RuntimeError('Native phase analysis failed: ' + name)
                if name == 'default-off': continue
                change = ('c3', 'DYNAMIC_RELATIVE_PHASE') if name == 'dynamic-relative-phase' else ('secondary', 'UNRELATED_SOURCES') if name == 'unrelated-source' else None
                comparisons[name] = compare(job['audit'], 'shifted' if name == 'shifted' else 'baseline', change, name == 'missing-source')
            save(status='ALL_NATIVE_PHASE_ENGINE_CASES_MATCH_VENDOR_EDGES_FULL_DESIGN_PENDING', comparisons=comparisons)
        shutil.copy2(__file__, out / 'helper.py'); save(completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': info.get('comparison'), 'native_results': info.get('native_results')}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'vendor-gate', 'characterization', 'out'): parser.add_argument('--' + name, type=Path, required=True)
    for name in ('source', 'gate'): parser.add_argument('--' + name, type=Path)
    parser.add_argument('--workers', type=int, default=8); args = parser.parse_args()
    if bool(args.source) != bool(args.gate) or not 1 <= args.workers <= 8: parser.error('Supply full source and gate together, and one to eight workers')
    check(args.backend.resolve(), args.vendor_gate.resolve(), args.characterization.resolve(), args.out.resolve(), args.workers,
          args.source.resolve() if args.source else None, args.gate.resolve() if args.gate else None)


if __name__ == '__main__': main()
