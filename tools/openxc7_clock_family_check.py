#!/usr/bin/env python3
"""Validate native nominal clock waveforms on probes and the complete design."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from fractions import Fraction
import csv
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe


CHIPDB = expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin')
GENERATORS = {'MMCME2_ADV_MMCME2_ADV', 'PLLE2_ADV_PLLE2_ADV'}


def net_aliases(packed, wanted):
    result = defaultdict(list)
    with packed.open() as stream:
        buffer = ''
        while True:
            chunk = stream.read(65536)
            if not chunk: raise ValueError('Packed netnames not found')
            buffer = buffer[-64:] + chunk
            match = re.search(r'"netnames"\s*:\s*\{', buffer)
            if match: position = match.end(); break
        decoder = json.JSONDecoder()
        def space():
            nonlocal buffer, position
            while True:
                while position < len(buffer) and buffer[position].isspace(): position += 1
                if position < len(buffer): return
                chunk = stream.read(65536)
                if not chunk: raise ValueError('Truncated packed netnames')
                buffer += chunk
        def decode():
            nonlocal buffer, position
            while True:
                try:
                    value, end = decoder.raw_decode(buffer, position); position = end; return value
                except json.JSONDecodeError:
                    chunk = stream.read(65536)
                    if not chunk or len(buffer) - position > 16 * 1024 * 1024:
                        raise ValueError('Invalid packed netname')
                    buffer += chunk
        while True:
            if position > 65536: buffer, position = buffer[position:], 0
            space()
            if buffer[position] == '}': break
            name = decode(); space()
            if buffer[position] != ':': raise ValueError('Invalid packed netname separator')
            position += 1; space(); record = decode(); bits = tuple(record['bits'])
            if bits in wanted: result[bits].append(name)
            space()
            if buffer[position] == '}': break
            if buffer[position] != ',': raise ValueError('Invalid packed netname record')
            position += 1
    return result


def waveforms(path):
    result = {}
    with path.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            name = row['net']
            if name in result: raise ValueError('Duplicate native clock waveform')
            for key in ('known', 'references'): row[key] = int(row[key])
            for quantity in ('period', 'phase', 'high'):
                row[quantity] = Fraction(int(row[quantity + '_num_ps']), int(row[quantity + '_den']))
            result[name] = row
    return result


def compare_generated(audit, vendor, configurations, cells, aliases, expected_unknown=None):
    actual = waveforms(audit); checked = []; roots = set()
    by_cell = {name: c for c in configurations for name in c['full_design_cells']}
    by_probe = {c['probe_cell']: c for c in configurations}
    for name, cell in cells.items():
        if cell['type'] not in GENERATORS: continue
        config = by_cell.get(name, by_probe.get(name))
        if config is None: raise ValueError('Generator configuration has no independent vendor source')
        for port, bits in cell['connections'].items():
            if not port.startswith('CLKOUT') and port not in ('CLKFBOUT', 'CLKFBOUTB'): continue
            matches = [actual[n] for n in aliases[tuple(bits)] if n in actual]
            if not matches: raise ValueError(f'Generator waveform missing: {name}/{port}')
            if len(matches) != 1: raise ValueError('Ambiguous native waveform alias')
            row = matches[0]
            if expected_unknown and name in expected_unknown:
                if row['known'] or row['reason'] != expected_unknown[name]:
                    raise ValueError('Unmodeled source was incorrectly assigned a waveform')
                checked.append({'cell': name, 'port': port, 'known': False, 'reason': row['reason']}); continue
            if not row['known']: raise ValueError(f'Generator waveform unknown: {name}/{port}: {row["reason"]}')
            gold = vendor[config['probe_cell'] + '_' + port]
            period = Fraction(gold['PERIOD']) * 1000
            rise, fall = [Fraction(v) * 1000 for v in gold['WAVEFORM'].split()]
            expected_high = fall - rise
            phase_error = (row['phase'] - rise) % row['period']
            phase_error = min(phase_error, row['period'] - phase_error)
            if abs(row['period'] - period) > 1 or abs(row['high'] - expected_high) > 1 or phase_error > 1:
                raise ValueError(f'Native/vendor waveform differs: {name}/{port}: {row!r} vs {gold!r}')
            stem = port.rstrip('B')
            fine = config['parameters'].get(stem + '_USE_FINE_PS', {'value': 'FALSE'})['value'] == 'TRUE'
            if row['dynamic_group'] != (name if fine else ''):
                raise ValueError('Dynamic fine-phase group was lost or invented')
            roots.add(row['root'])
            checked.append({'cell': name, 'port': port, 'net': row['net'], 'known': True,
                            'period_ps': str(row['period']), 'phase_ps': str(row['phase']),
                            'high_ps': str(row['high']), 'root': row['root'], 'dynamic_group': row['dynamic_group']})
    return {'generator_ports_checked': len(checked), 'generator_cells': sum(c['type'] in GENERATORS for c in cells.values()),
            'known_generator_roots': sorted(roots), 'mismatches': 0, 'rows': checked,
            'clock_nets': len(actual), 'known_clock_nets': sum(r['known'] for r in actual.values()),
            'unknown_clock_nets': sum(not r['known'] for r in actual.values()),
            'unknown_reasons': dict(Counter(r['reason'] for r in actual.values() if not r['known'])),
            'clock_insertion_skew': 'NOT_QUALIFIED', 'phase_engine': 'NOT_IMPLEMENTED'}


def check(backend, characterization, out, workers, prototype=None, shifted_vendor=None, source=None, inventory=None, gate=None):
    b = json.loads(backend.read_text())
    if b['status'] != 'CLOCK_WAVEFORM_BACKEND_BUILD_PASS_NATIVE_FULL_WAVEFORM_VALIDATION_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Expected completed, unchanged waveform backend')
    configs = json.loads((characterization / 'configurations.json').read_text())['configs']
    configs = [c for c in configs if c['packed_type'] in GENERATORS]
    vendor = json.loads((characterization / 'semantic-summary.json').read_text())['clocks']
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'helper': describe(__file__), 'workers': workers,
            'scope': 'NOMINAL_CLOCK_WAVEFORMS_NOT_PHASE_ENGINE_SKEW_OR_FULL_TIMING_QUALIFICATION',
            'hardware_accessed': False, 'live_full_route_changed': False, 'numerical_timing': 'NOT_QUALIFIED'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    def command(path, xdc, audit=None, mode='on', packed=None, full=False):
        argv = [b['binary']['path'], '--chipdb', CHIPDB, '--device', 'xc7k480tffg1156-2', '--json', str(path),
                '-o', 'xdc=' + str(xdc), '--pack-only', '--threads', '8', '--freq', '100.0', '--seed', '1',
                '-o', 'clock-vivado-timing=on', '-o', 'clock-feedback-vivado=on', '-o', 'clock-family-vivado=' + mode]
        if audit: argv += ['-o', 'clock-waveform-audit=' + str(audit)]
        if packed: argv += ['--write', str(packed)]
        if full: argv += ['-o', 'dsp-vivado-timing=on', '-o', 'serdes-vivado-timing=on']
        return argv
    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out / (stage + '.exit')).write_text(str(result.returncode) + '\n')
        return stage, result.returncode
    try:
        save(stage='prepare')
        if source:
            g = json.loads(gate.read_text())
            if g['status'] != 'CLOCK_WAVEFORM_NATIVE_CASES_PASS_FULL_DESIGN_CHECK_PENDING' or g['backend'] != describe(backend):
                raise ValueError('Waveform configuration gates do not match backend')
            inv = json.loads(inventory.read_text()); packed_path = Path(inv['packed_netlist']['path'])
            cfg_record = json.loads((characterization / 'configurations.json').read_text())
            if describe(inventory) != cfg_record['inventory'] or describe(packed_path) != inv['packed_netlist']:
                raise ValueError('Independent full packed clock inventory changed')
            reference = json.loads((source.parent.parent / 'full-packed-dsp-inventory-20261011T223120Z/manifest.json').read_text())
            for name in ('constrained.json', 'openxc7.xdc'):
                if describe(source / name) != reference['inputs'][name]: raise ValueError('Pinned full source changed')
            wanted_cells = {c['name']: c for c in inv['cells'] if c['type'] in GENERATORS}
            sampling = {tuple(c['connections']['CLK']) for c in inv['cells'] if c['type'] == 'ISERDESE2_ISERDESE2'}
            bits = {tuple(v) for c in wanted_cells.values() for p, v in c['connections'].items()
                    if p.startswith('CLKOUT') or p in ('CLKFBOUT', 'CLKFBOUTB')}
            aliases = net_aliases(packed_path, bits | sampling)
            audit = out / 'full-clock-waveforms.tsv'
            save(stage='full-native-pack', profile=reference['profile'], full_inputs=reference['inputs'], gate=describe(gate), inventory=describe(inventory))
            print('FULL_CLOCK_WAVEFORM_AUDIT_STARTED ' + str(out), flush=True)
            _, code = run('full-pack', command(source / 'constrained.json', source / 'openxc7.xdc', audit, full=True))
            save(native_exit=code)
            if code: raise RuntimeError('Complete waveform extraction failed')
            comparison = compare_generated(audit, vendor, configs, wanted_cells, aliases)
            actual = waveforms(audit); sampler_rows = []
            for bit in sampling:
                matches = [actual[n] for n in aliases[bit] if n in actual]
                if len(matches) != 1: raise ValueError('Full sampler clock coverage missing or ambiguous')
                row = matches[0]
                if row['references'] <= 0:
                    raise ValueError('Sampler clock callbacks were not initialized before waveform extraction')
                sampler_rows.append({'net': row['net'], 'known': row['known'], 'root': row['root'], 'reason': row['reason'], 'references': row['references']})
            if comparison['generator_ports_checked'] != 20 or len(comparison['known_generator_roots']) != 1:
                raise ValueError('Full 20-output clock ancestry scope differs')
            comparison['unknown_clocks_with_references'] = [
                {'net': row['net'], 'references': row['references'], 'reason': row['reason']}
                for row in actual.values() if not row['known'] and row['references'] > 0]
            save(status='FULL_20_GENERATOR_WAVEFORMS_PASS_USED_CLOCK_UNKNOWNS_RECORDED_ENGINE_PENDING',
                 comparison=comparison, sampler_clock_coverage=sampler_rows, audit=describe(audit))
        else:
            if not prototype or not shifted_vendor: raise ValueError('Prototype and vendor shifted-clock evidence are required')
            shifted_file = shifted_vendor / 'clock-waveforms.tsv'
            if (shifted_vendor / 'native.exit').read_text().strip() != '0': raise ValueError('Shifted vendor query failed')
            shifted = dict(vendor)
            with shifted_file.open() as stream:
                for row in csv.DictReader(stream, delimiter='\t'):
                    shifted[row['clock']] = {'PERIOD': row['period'], 'WAVEFORM': row['waveform']}
            design = json.loads(prototype.read_text()); top, = design['modules'].values()
            by_name = {c['probe_cell']: c for c in configs}
            max_bit = max(bit for c in top['cells'].values() for bits in c['connections'].values() for bit in bits if isinstance(bit, int))
            original = json.loads(json.dumps(design))
            buf_model = next(c for c in json.loads((characterization / 'configurations.json').read_text())['configs'] if c['primitive'] == 'BUFGCTRL')
            def encoded(value):
                if value['kind'] in ('string', 'real'): return str(value['value'])
                return format(value['value'], '032b')
            for name, cfg in by_name.items():
                c = top['cells'][name]
                c['connections']['CLKINSEL'] = ['1']; c['connections']['CLKIN2'] = ['0']
                if cfg['parameters']['COMPENSATION']['value'] == 'ZHOLD':
                    max_bit += 1; new_bit = max_bit; buffer_name = name + '_feedback_buffer'
                    pins = {'I0': c['connections']['CLKFBOUT'], 'O': [new_bit]}
                    pins.update({p: ['1'] for p in ('CE0', 'CE1', 'S0', 'S1', 'IGNORE0', 'IGNORE1')})
                    top['cells'][buffer_name] = {'hide_name': 0, 'type': 'BUFGCTRL', 'parameters': {p: encoded(v) for p, v in buf_model['parameters'].items()},
                        'attributes': {}, 'port_directions': {p: 'output' if p == 'O' else 'input' for p in pins}, 'connections': pins}
                    top['netnames'][buffer_name + '_out'] = {'hide_name': 0, 'bits': [new_bit], 'attributes': {}}
                    c['connections']['CLKFBIN'] = [new_bit]
                else:
                    c['connections']['CLKFBIN'] = c['connections']['CLKFBOUT']
            root_lines = []
            for name, cfg in by_name.items():
                root_lines.append(f'create_clock -period {cfg["parameters"]["CLKIN1_PERIOD"]["value"]} [get_nets {{{name}_CLKIN1}}]')
                root_lines.append(f'create_clock -period 10 [get_nets {{{name}_DCLK}}]')
                if cfg['primitive'] == 'MMCME2_ADV': root_lines.append(f'create_clock -period 10 [get_nets {{{name}_PSCLK}}]')
            root_lines += ['create_clock -period 10 [get_nets {phy_06_I0}]', 'create_clock -period 10 [get_nets {phy_06_I1}]']
            def make_case(name, value, lines, rejection=None, mode='on', expected_unknown=None):
                source_path = out / (name + '.json'); source_path.write_text(json.dumps(value, separators=(',', ':')) + '\n')
                xdc = out / (name + '.xdc'); xdc.write_text('\n'.join(lines) + '\n')
                audit = out / (name + '.waveforms.tsv') if mode != 'off' and not rejection else None
                packed = out / (name + '.packed.json') if not rejection else None
                return {'name': name, 'source': source_path, 'audit': audit, 'packed': packed, 'rejection': rejection,
                        'unknown': expected_unknown, 'command': command(source_path, xdc, audit, mode, packed)}
            jobs = [make_case('baseline', design, root_lines),
                    make_case('shifted-primary', design, ['create_clock -period 10 -waveform {1.25 3.75} [get_nets {phy_03_CLKIN1}]' if 'phy_03_CLKIN1' in l else l for l in root_lines]),
                    make_case('missing-primary', design, [l for l in root_lines if 'phy_03_CLKIN1' not in l], expected_unknown={'phy_03': 'NO_SOURCE_CLOCK_CONSTRAINT'})]
            ambiguous = json.loads(json.dumps(design)); amb, = ambiguous['modules'].values(); old, = original['modules'].values()
            amb['cells']['phy_03']['connections']['CLKINSEL'] = old['cells']['phy_03']['connections']['CLKINSEL']
            amb['cells']['phy_03']['connections']['CLKIN2'] = old['cells']['phy_03']['connections']['CLKIN2']
            jobs.append(make_case('ambiguous-primary', ambiguous, root_lines, expected_unknown={'phy_03': 'AMBIGUOUS_OR_ABSENT_GENERATOR_INPUT'}))
            feedback = json.loads(json.dumps(design)); fb, = feedback['modules'].values(); fb['cells']['phy_03']['connections']['CLKFBIN'] = old['cells']['phy_03']['connections']['CLKFBIN']
            jobs += [make_case('invalid-feedback', feedback, root_lines, expected_unknown={'phy_03': 'FEEDBACK_TOPOLOGY_NOT_CHARACTERIZED'}),
                     make_case('default-off', design, root_lines, mode='off'),
                     make_case('invalid-option', design, root_lines, mode='maybe', rejection='clock-family-vivado must be on or off'),
                     make_case('nonfinite-waveform', design, ['create_clock -period 10 -waveform {nan 5} [get_nets {phy_03_CLKIN1}]' if 'phy_03_CLKIN1' in l else l for l in root_lines], rejection='Malformed primary clock number')]
            save(stage='parallel-native-cases', prototype=describe(prototype), shifted_vendor=describe(shifted_file))
            print(f'RUNNING {len(jobs)} native clock waveform cases with {workers} workers', flush=True)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = dict(pool.map(lambda j: run(j['name'], j['command']), jobs))
            save(native_results=results); comparisons = {}
            for job in jobs:
                name = job['name']; rejection = job['rejection']
                if rejection:
                    if results[name] != 125 or rejection not in (out / (name + '.log')).read_text(): raise ValueError('Waveform rejection failed: ' + name)
                    continue
                if results[name]: raise RuntimeError('Native waveform case failed: ' + name)
                d = json.loads(job['packed'].read_text()); t, = d['modules'].values()
                if name == 'default-off':
                    if any('X_VIVADO_CLOCK_VALID' in n['attributes'] for n in t['netnames'].values()): raise ValueError('Default-off path emitted waveform metadata')
                    continue
                wanted = {tuple(bits) for c in t['cells'].values() if c['type'] in GENERATORS for p, bits in c['connections'].items()
                          if p.startswith('CLKOUT') or p in ('CLKFBOUT', 'CLKFBOUTB')}
                aliases = defaultdict(list)
                for n, v in t['netnames'].items():
                    if tuple(v['bits']) in wanted: aliases[tuple(v['bits'])].append(n)
                comparisons[name] = compare_generated(job['audit'], shifted if name == 'shifted-primary' else vendor,
                                                      configs, t['cells'], aliases, job['unknown'])
            save(status='CLOCK_WAVEFORM_NATIVE_CASES_PASS_FULL_DESIGN_CHECK_PENDING', comparisons=comparisons)
        shutil.copy2(__file__, out / 'helper.py'); save(completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': {k: v for k, v in info.get('comparison', {}).items() if k != 'rows'},
                          'cases': info.get('native_results'), 'sampler_clock_nets': len(info.get('sampler_clock_coverage', []))}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'characterization', 'out'): parser.add_argument('--' + name, type=Path, required=True)
    for name in ('prototype', 'shifted-vendor', 'source', 'inventory', 'gate'): parser.add_argument('--' + name, type=Path)
    parser.add_argument('--workers', type=int, default=8); args = parser.parse_args()
    if not 1 <= args.workers <= 8: parser.error('Expected one to eight workers')
    if bool(args.source) != bool(args.inventory) or bool(args.source) != bool(args.gate): parser.error('Full source, inventory and gate are required together')
    check(args.backend.resolve(), args.characterization.resolve(), args.out.resolve(), args.workers,
          args.prototype.resolve() if args.prototype else None, args.shifted_vendor.resolve() if args.shifted_vendor else None,
          args.source.resolve() if args.source else None, args.inventory.resolve() if args.inventory else None, args.gate.resolve() if args.gate else None)


if __name__ == '__main__': main()
