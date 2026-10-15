#!/usr/bin/env python3
"""Audit clock intrinsic callbacks against the independent raw vendor records."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phy_vivado_timing import render
from openxc7_serdes_timing_check import compare as compare_serializers
from openxc7_packed_dsp_inventory import cells as packed_cell_records


TYPES = {'MMCME2_ADV_MMCME2_ADV', 'PLLE2_ADV_PLLE2_ADV', 'BUFGCTRL'}
CHIPDB = expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin')


def raw_reference(characterization):
    configs = json.loads((characterization / 'configurations.json').read_text())
    source = json.loads((characterization / 'timing-arcs-compact.json').read_text())
    models = []
    for group in [c for c in configs['configs'] if c['packed_type'] in TYPES]:
        arcs, disabled = [], []
        for record in source['arcs']:
            if record['cell'] != group['probe_cell']:
                continue
            source_pin = re.sub(r'\[(\d+)\]', r'\1', record['from'])
            target_pin = re.sub(r'\[(\d+)\]', r'\1', record['to'])
            if record['disabled']:
                if record['type'] != 'Reg Set/Clr' or source_pin != 'RST':
                    raise ValueError('Unexpected disabled clock arc')
                disabled.append((source_pin, target_pin)); continue
            limits = []
            for edge in ('RISE', 'FALL'):
                values = [Decimal(str(value)) * 1000 for name, value in record['delays_ns'].items()
                          if name.endswith('_' + edge) and ('_FAST_' in name or '_SLOW_' in name)]
                if len(values) != 4 or any(not v.is_finite() for v in values):
                    raise ValueError('Incomplete independent clock corner data')
                limits.extend((int(min(values).to_integral_value(rounding=ROUND_FLOOR)),
                               int(max(values).to_integral_value(rounding=ROUND_CEILING))))
            kind = record['type']; sampling = None
            if kind not in ('combinational', 'Reg Clk to Q', 'setup', 'hold'):
                raise ValueError('Unsupported enabled clock arc')
            if kind != 'combinational':
                edges = {t[0] for t in record['transition'].split()}
                if len(edges) != 1:
                    raise ValueError('Ambiguous clock edge')
                inverted = group['parameters'].get('IS_' + source_pin + '_INVERTED', {'value': 0})['value']
                sampling = 'falling' if (edges == {'f'}) != bool(inverted) else 'rising'
            arcs.append((kind, source_pin, target_pin, sampling, tuple(limits)))
        models.append({'config': group, 'arcs': arcs, 'disabled': disabled})
    return models


def compare(audit, characterization, packed_cells, scope):
    models = raw_reference(characterization)
    assignments = {name: i for i, m in enumerate(models) for name in (
        m['config']['full_design_cells'] if scope == 'full' else [m['config']['probe_cell']])}
    if set(packed_cells) != set(assignments):
        raise ValueError('Complete named clock-cell scope differs')
    want = {tag: {} for tag in ('M', 'P', 'R', 'C', 'D')}
    for name, cell in packed_cells.items():
        index = assignments[name]; model = models[index]; cfg = model['config']
        if cell['type'] != cfg['packed_type']:
            raise ValueError('Clock primitive type differs')
        want['M'][name] = index
        present = cell['port_directions']; connections = cell['connections']
        clocks = set() if cfg['primitive'] == 'BUFGCTRL' else {'CLKIN1', 'CLKIN2', 'CLKFBIN', 'DCLK'}
        if cfg['primitive'] == 'MMCME2_ADV':
            clocks.add('PSCLK')
        for pin, direction in present.items():
            checks = [a for a in model['arcs'] if a[0] in ('setup', 'Reg Clk to Q') and a[2] == pin
                      and connections.get(a[1]) and all(isinstance(b, int) and b not in cell.get('constant_bits', ())
                                                       for b in connections[a[1]])]
            checks.sort(key=lambda a: (a[1], a[3]))
            if pin in clocks:
                cls = 'clock_input'; checks = []
            elif direction == 'output' and cfg['primitive'] != 'BUFGCTRL' and pin.startswith(('CLKOUT', 'CLKFBOUT')):
                cls = 'generated_clock'; checks = []
            elif checks:
                cls = 'register_input' if direction == 'input' else 'register_output'
            elif direction == 'input':
                cls = 'comb_input'
            elif any(a[0] == 'combinational' and a[2] == pin for a in model['arcs']):
                cls = 'comb_output'
            else:
                cls = 'ignore'
            want['P'][(name, pin)] = (cls, len(checks))
            for number, arc in enumerate(checks):
                kind, clock, _, sampling, values = arc
                if kind == 'setup':
                    holds = [a for a in model['arcs'] if a[:4] == ('hold', clock, pin, sampling)]
                    if len(holds) != 1:
                        raise ValueError('Independent clock setup/hold pair differs')
                    h = holds[0][4]
                    timing = (min(values[0], values[2]), max(values[1], values[3]), min(h[0], h[2]), max(h[1], h[3]), 0, 0, 0, 0)
                else:
                    timing = (0, 0, 0, 0, *values)
                want['R'][(name, pin, number)] = (clock, sampling, *timing)
        for kind, source, target, _, limits in model['arcs']:
            if kind == 'combinational' and source in present and target in present:
                want['C'][(name, source, target)] = limits
        for source, target in model['disabled']:
            want['D'][(name, source, target)] = ('vendor_disabled_set_clr', 0)
    actual = {tag: {} for tag in want}
    for line in audit.read_text().splitlines():
        f = line.split('\t'); tag, cell = f[:2]
        if tag == 'M': key, value = cell, int(f[2])
        elif tag == 'P': key, value = (cell, f[2]), (f[3], int(f[4]))
        elif tag == 'R': key, value = (cell, f[2], int(f[3])), (f[4], f[5], *map(int, f[6:]))
        elif tag == 'C': key, value = (cell, f[2], f[3]), tuple(map(int, f[4:]))
        elif tag == 'D': key, value = (cell, f[2], f[3]), (f[4], int(f[5]))
        else: raise ValueError('Unknown clock callback record')
        if key in actual[tag]: raise ValueError('Duplicate clock callback record')
        actual[tag][key] = value
    for tag in want:
        if actual[tag] != want[tag]:
            wrong = [k for k in actual[tag].keys() & want[tag].keys() if actual[tag][k] != want[tag][k]]
            examples = [(k, actual[tag][k], want[tag][k]) for k in wrong[:3]]
            raise ValueError(f'Clock {tag} mismatch: missing={len(want[tag].keys()-actual[tag].keys())}, '
                             f'extra={len(actual[tag].keys()-want[tag].keys())}, wrong={len(wrong)}, examples={examples!r}')
    return {'clock_cells': len(packed_cells), 'configurations': len(set(assignments.values())),
            'port_classifications': len(actual['P']), 'sequential_checks': len(actual['R']),
            'generated_clock_ports': sum(v[0] == 'generated_clock' for v in actual['P'].values()),
            'falling_edge_checks': sum(v[1] == 'falling' for v in actual['R'].values()),
            'combinational_arcs': len(actual['C']), 'explicit_disabled_reset_arcs': len(actual['D']),
            'model_distribution': dict(Counter(assignments.values())), 'mismatches': 0}


def fixture_cells(packed):
    d = json.loads(packed.read_text()); top, = d['modules'].values()
    constants = {b for c in top['cells'].values() if c['type'] in ('PSEUDO_GND', 'PSEUDO_VCC')
                 for bits in c['connections'].values() for b in bits}
    return {name: {**c, 'constant_bits': constants} for name, c in top['cells'].items() if c['type'] in TYPES}


def check(backend, characterization, out, workers=8, source=None, inventory=None, gate=None):
    b = json.loads(backend.read_text())
    if b['status'] != 'CLOCK_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING':
        raise ValueError('Expected completed isolated clock backend')
    binary = Path(b['binary']['path'])
    if describe(binary) != b['binary']:
        raise ValueError('Clock backend binary changed')
    if describe(b['tables']['path']) != b['tables']:
        raise ValueError('Prepared clock table changed')
    prepared = json.loads(Path(b['tables']['path']).read_text())
    for key, filename in [('raw', 'timing-arcs-compact.json'), ('configs', 'configurations.json'), ('semantic', 'semantic-summary.json')]:
        if describe(characterization / filename) != prepared[key]:
            raise ValueError('Independently characterized vendor source changed')
    models = raw_reference(characterization)
    if len(models) != 4 or sum(len(m['config']['full_design_cells']) for m in models) != 20:
        raise ValueError('Complete clock scope changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'helper': describe(__file__), 'workers': workers,
            'scope': 'COMPLETE_CLOCK_INTRINSIC_CALLBACKS_NOT_CLOCK_PHASE_FAMILY_FULL_TIMING_OR_ROUTE',
            'hardware_accessed': False, 'live_full_route_changed': False, 'numerical_timing': 'NOT_QUALIFIED'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    def command(design, audit=None, packed=None, part='xc7k480tffg1156-2', mode='on', full=False):
        argv = [str(binary), '--chipdb', CHIPDB, '--device', part, '--json', str(design), '--pack-only', '--threads', '8']
        if mode is not None:
            argv += ['-o', 'clock-vivado-timing=' + mode]
        if audit:
            argv += ['-o', 'clock-timing-audit=' + str(audit)]
        if packed:
            argv += ['--write', str(packed)]
        if full:
            argv += ['--freq', '100.0', '--seed', '1', '-o', 'xdc=' + str(source / 'openxc7.xdc'),
                     '-o', 'dsp-vivado-timing=on', '-o', 'clock-feedback-vivado=on',
                     '-o', 'serdes-vivado-timing=on', '-o', 'serdes-timing-audit=' + str(out / 'full-serdes-callbacks.tsv'),
                     '-o', 'clock-constraint-audit=' + str(out / 'clock-constraints.tsv')]
        return argv
    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            code = child.wait()
        (out / (stage + '.exit')).write_text(str(code) + '\n')
        return stage, code
    try:
        save(stage='prepare')
        if source is not None:
            g = json.loads(gate.read_text())
            if g['status'] != 'ALL_CLOCK_CONFIGURATION_NATIVE_CALLBACKS_PASS_FULL_DESIGN_CHECK_PENDING' or g['backend'] != describe(backend):
                raise ValueError('Native configuration gates do not match this backend')
            inv = json.loads(inventory.read_text())
            configs = json.loads((characterization / 'configurations.json').read_text())
            if describe(inventory) != configs['inventory']:
                raise ValueError('Full named clock inventory changed')
            pack_manifest = json.loads((source.parent.parent / 'full-packed-dsp-inventory-20261011T223120Z/manifest.json').read_text())
            for name in ('constrained.json', 'openxc7.xdc'):
                if describe(source / name) != pack_manifest['inputs'][name]:
                    raise ValueError('Full source input changed')
            packed_path = Path(inv['packed_netlist']['path'])
            if describe(packed_path) != inv['packed_netlist']:
                raise ValueError('Independent full packed netlist changed')
            constant_bits = set()
            for _, record in packed_cell_records(packed_path):
                if record['type'] in ('PSEUDO_GND', 'PSEUDO_VCC'):
                    constant_bits.update(b for bits in record['connections'].values() for b in bits)
            if len(constant_bits) != 2:
                raise ValueError('Full packed constant-net scope changed')
            cells = {c['name']: {**c, 'constant_bits': constant_bits} for c in inv['cells'] if c['type'] in TYPES}
            audit = out / 'full-clock-callbacks.tsv'
            argv = command(source / 'constrained.json', audit, full=True)
            save(stage='full-native-pack', full_inputs=pack_manifest['inputs'], profile=pack_manifest['profile'], inventory=describe(inventory), gate=describe(gate))
            print('FULL_CLOCK_NATIVE_AUDIT_STARTED ' + str(out), flush=True)
            _, code = run('full-pack', argv)
            save(native_exit=code)
            if code:
                raise RuntimeError('Complete native clock audit failed')
            comparison = compare(audit, characterization, cells, 'full')
            serializer_cells = {c['name']: c for c in inv['cells'] if c['type'] in ('ISERDESE2_ISERDESE2','OSERDESE2_OSERDESE2')}
            serializer_result = compare_serializers(out / 'full-serdes-callbacks.tsv', characterization, serializer_cells, 'full')
            save(retained_serializer_comparison=serializer_result)
            save(status='COMPLETE_20_CLOCK_NATIVE_CALLBACKS_PASS_CLOCK_PHASE_FAMILY_AND_FULL_TIMING_PENDING',
                 comparison=comparison, audit=describe(audit))
        else:
            raw = out / 'probe.yosys.json'
            # Use only the already-characterized clock declarations. The
            # unrelated vendor BUFGCTRL SIM_DEVICE property has no Yosys
            # library equivalent and does not belong in this callback fixture.
            declarations, instances = [], []
            for model in models:
                c = model['config']; name = c['probe_cell']; connections = []
                for port in c['ports']:
                    pin = port['name']
                    if c['primitive'] == 'ICLOCKE2' and pin == 'CLKB':
                        connections.append('.CLKB(' + name + '_CLK)'); continue
                    declarations.append(port['direction'] + ' wire ' + name + '_' + pin)
                    connections.append('.' + pin + '(' + name + '_' + pin + ')')
                params = ','.join('.' + p + '(' + render(v) + ')' for p, v in c['parameters'].items() if not (c['primitive'] == 'BUFGCTRL' and p == 'SIM_DEVICE'))
                instances.append(c['primitive'] + ' #(' + params + ') ' + name + '(' + ','.join(connections) + ');')
            rtl = out / 'clock_configs.v'
            rtl.write_text('module phy_configs(' + ','.join(declarations) + ');\n' + '\n'.join(instances) + '\nendmodule\n')
            script = f'read_verilog -lib +/xilinx/cells_sim.v; read_verilog -lib +/xilinx/cells_xtra.v; read_verilog {rtl}; hierarchy -check -top phy_configs; select phy_configs; write_json -selected {raw}'
            _, code = run('yosys', ['yosys', '-p', script])
            if code:
                raise RuntimeError('Clock fixture elaboration failed')
            design = json.loads(raw.read_text()); top = design['modules']['phy_configs']
            selected = {m['config']['probe_cell'] for m in models}
            top['cells'] = {n: c for n, c in top['cells'].items() if n in selected}
            if set(top['cells']) != selected:
                raise ValueError('Elaborated clock configuration scope changed')
            # These are timing-only packed-cell fixtures, with no external I/O
            # site placement. The separate full-design check exercises the
            # actual I/O packer, IDELAY topology and constrained physical sites.
            for model in models:
                c = model['config']; cell = top['cells'][c['probe_cell']]
                if cell['type'] != c['primitive']:
                    raise ValueError('Elaborated clock primitive differs')
                cell['type'] = c['packed_type']
                flat_connections, flat_directions = {}, {}
                for port in c['ports']:
                    pin, width = port['name'], port['width']
                    for bit in range(width):
                        packed_pin = pin + (str(bit) if width > 1 else '')
                        flat_connections[packed_pin] = [cell['connections'][pin][bit]]
                        flat_directions[packed_pin] = port['direction']
                cell['connections'] = flat_connections; cell['port_directions'] = flat_directions
            input_bits = {bit for c in top['cells'].values() for pin, bits in c['connections'].items()
                          if c['port_directions'][pin] == 'input' for bit in bits if isinstance(bit, int)}
            for bit in sorted(input_bits):
                top['cells'][f'fixture_driver_{bit}'] = {'hide_name': 0, 'type': 'LUT1', 'parameters': {'INIT': '10'},
                    'attributes': {'keep': '1'}, 'port_directions': {'I0': 'input', 'O': 'output'}, 'connections': {'I0': ['0'], 'O': [bit]}}
            top['ports'] = {}
            def write(name, value):
                path = out / ('probe.' + name + '.json'); path.write_text(json.dumps(value, separators=(',', ':')) + '\n'); return path
            probe = write('all-configurations', design)
            omitted = json.loads(json.dumps(design)); removed = 0
            for m in json.loads(Path(b['tables']['path']).read_text())['models']:
                params = omitted['modules']['phy_configs']['cells'][m['probe_cell']]['parameters']
                for name in list(params):
                    expected, default = m['parameters'][name], m['defaults'][name]
                    if expected['kind'] == default['kind'] and (Decimal(str(expected['value'])) == Decimal(str(default['value'])) if expected['kind'] == 'real' else expected['value'] == default['value']):
                        del params[name]; removed += 1
            formatted = json.loads(json.dumps(design))
            for m in models:
                params = formatted['modules']['phy_configs']['cells'][m['config']['probe_cell']]['parameters']
                for name, value in m['config']['parameters'].items():
                    if value['kind'] == 'real': params[name] = format(Decimal(str(value['value'])), '.9f')
            tied = json.loads(json.dumps(design)); tied['modules']['phy_configs']['cells']['phy_03']['connections']['DCLK'] = ['0']
            unsupported = json.loads(json.dumps(design)); unsupported['modules']['phy_configs']['cells']['phy_03']['parameters']['BANDWIDTH'] = 'LOW'
            malformed = json.loads(json.dumps(design)); malformed['modules']['phy_configs']['cells']['phy_03']['parameters']['CLKIN1_PERIOD'] = 'nan'
            cases = {'all-configurations': (probe, None, 'on', True),
                     'defaults-omitted': (write('defaults-omitted', omitted), None, 'on', True),
                     'real-formatting': (write('real-formatting', formatted), None, 'on', True),
                     'tied-clock': (write('tied-clock', tied), None, 'on', True),
                     'default-off': (probe, None, None, False),
                     'unsupported-mode': (write('unsupported-mode', unsupported), 'Unsupported clock timing configuration', 'on', False),
                     'nonfinite-real': (write('nonfinite-real', malformed), 'Unsupported clock timing configuration', 'on', False),
                     'wrong-speed-grade': (probe, 'characterized only for xc7k480tffg1156-2', 'on', False)}
            jobs = []
            for name, (path, rejection, mode, audit_enabled) in cases.items():
                audit = out / (name + '.callbacks.tsv') if audit_enabled else None
                packed = out / (name + '.packed.json') if audit_enabled else None
                part = 'xc7k480tffg1156-1' if name == 'wrong-speed-grade' else 'xc7k480tffg1156-2'
                jobs.append((name, command(path, audit, packed, part=part, mode=mode)))
            save(stage='parallel-native-callback-checks', cases=list(cases), declared_defaults_removed=removed, fixture_input_drivers=len(input_bits))
            print(f'RUNNING {len(jobs)} independent native clock checks with {workers} workers', flush=True)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = dict(pool.map(lambda item: run(*item), jobs))
            save(native_results=results)
            comparisons = {}
            for name, (_, rejection, _, audit_enabled) in cases.items():
                if rejection:
                    if results[name] != 125 or rejection not in (out / (name + '.log')).read_text():
                        raise ValueError('Native rejection did not match: ' + name)
                elif results[name]:
                    raise RuntimeError('Native clock case failed: ' + name)
                if audit_enabled:
                    comparisons[name] = compare(out / (name + '.callbacks.tsv'), characterization,
                                                fixture_cells(out / (name + '.packed.json')), 'fixture')
            save(status='ALL_CLOCK_CONFIGURATION_NATIVE_CALLBACKS_PASS_FULL_DESIGN_CHECK_PENDING', comparisons=comparisons)
        shutil.copy2(__file__, out / 'helper.py')
        save(completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparison': info.get('comparison'), 'comparisons': info.get('comparisons')}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'characterization', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('source', 'inventory', 'gate'):
        parser.add_argument('--' + name, type=Path)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if len({bool(args.source), bool(args.inventory), bool(args.gate)}) != 1 or not 1 <= args.workers <= 8:
        parser.error('Supply full source, inventory and native gate together, and one to eight workers')
    check(args.backend.resolve(), args.characterization.resolve(), args.out.resolve(), args.workers,
          args.source.resolve() if args.source else None, args.inventory.resolve() if args.inventory else None,
          args.gate.resolve() if args.gate else None)


if __name__ == '__main__':
    main()
