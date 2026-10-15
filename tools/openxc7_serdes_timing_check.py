#!/usr/bin/env python3
"""Compare actual serializer callbacks independently with raw Vivado arc data."""
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
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phy_vivado_timing import render


TYPES = {'ISERDESE2_ISERDESE2', 'OSERDESE2_OSERDESE2'}
CHIPDB = expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin')


def raw_reference(characterization):
    configs = json.loads((characterization / 'configurations.json').read_text())
    source = json.loads((characterization / 'timing-arcs-compact.json').read_text())
    groups = [c for c in configs['configs'] if c['packed_type'] in TYPES]
    models = []
    for group in groups:
        arcs = []
        for record in source['arcs']:
            if record['cell'] != group['probe_cell']:
                continue
            limits = []
            for edge in ('RISE', 'FALL'):
                values = [Decimal(str(value)) * 1000 for name, value in record['delays_ns'].items()
                          if name.endswith('_' + edge) and ('_FAST_' in name or '_SLOW_' in name)]
                if len(values) != 4 or any(not v.is_finite() for v in values):
                    raise ValueError('Incomplete independent vendor corner values')
                limits.extend((int(min(values).to_integral_value(rounding=ROUND_FLOOR)),
                               int(max(values).to_integral_value(rounding=ROUND_CEILING))))
            if record['disabled']:
                raise ValueError('Disabled vendor arc needs explicit semantics')
            kind = record['type']
            if kind not in ('combinational', 'Reg Clk to Q', 'setup', 'hold'):
                raise ValueError('Unsupported raw serializer arc')
            sampling = None
            if kind != 'combinational':
                clock_edges = {t[0] for t in record['transition'].split()}
                if len(clock_edges) != 1:
                    raise ValueError('Ambiguous independent clock transition')
                inverted = group['parameters']['IS_' + record['from'] + '_INVERTED']['value']
                sampling = 'falling' if (clock_edges == {'f'}) != bool(inverted) else 'rising'
            arcs.append((kind, record['from'], record['to'], sampling, tuple(limits)))
        models.append({'config': group, 'arcs': arcs})
    return models


def compare(audit, characterization, packed_cells, scope):
    models = raw_reference(characterization)
    assignments = {name: i for i, m in enumerate(models) for name in (
        m['config']['full_design_cells'] if scope == 'full' else [m['config']['probe_cell']])}
    if set(packed_cells) != set(assignments):
        raise ValueError('Named serializer scope differs from vendor inventory')
    want = {tag: {} for tag in ('M', 'P', 'R', 'C')}
    for name, cell in packed_cells.items():
        index = assignments[name]; model = models[index]; config = model['config']
        if cell['type'] != config['packed_type']:
            raise ValueError('Serializer primitive type differs')
        want['M'][name] = index
        present = cell['port_directions']; connections = cell['connections']
        clocks = {'CLK', 'CLKDIV'}
        if config['primitive'] == 'ISERDESE2':
            clocks.update(('CLKB', 'CLKDIVP', 'OCLK', 'OCLKB'))
        for pin, direction in present.items():
            checks = [a for a in model['arcs'] if a[0] in ('setup', 'Reg Clk to Q') and a[2] == pin
                      and connections.get(a[1]) and all(isinstance(b, int) and b not in cell.get('constant_bits', ())
                                                       for b in connections[a[1]])]
            checks.sort(key=lambda a: (a[1], a[3]))
            if pin in clocks:
                cls = 'clock_input'; checks = []
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
                    h = [a for a in model['arcs'] if a[:4] == ('hold', clock, pin, sampling)]
                    if len(h) != 1:
                        raise ValueError('Independent setup/hold pairing failed')
                    hold = h[0][4]
                    timing = (min(values[0], values[2]), max(values[1], values[3]),
                              min(hold[0], hold[2]), max(hold[1], hold[3]), 0, 0, 0, 0)
                else:
                    timing = (0, 0, 0, 0, *values)
                want['R'][(name, pin, number)] = (clock, sampling, *timing)
        for kind, source, target, _, limits in model['arcs']:
            if kind == 'combinational' and source in present and target in present:
                want['C'][(name, source, target)] = limits
    actual = {tag: {} for tag in want}
    for line in audit.read_text().splitlines():
        fields = line.split('\t'); tag, cell = fields[:2]
        if tag == 'M':
            key, value = cell, int(fields[2])
        elif tag == 'P':
            key, value = (cell, fields[2]), (fields[3], int(fields[4]))
        elif tag == 'R':
            key, value = (cell, fields[2], int(fields[3])), (fields[4], fields[5], *map(int, fields[6:]))
        elif tag == 'C':
            key, value = (cell, fields[2], fields[3]), tuple(map(int, fields[4:]))
        else:
            raise ValueError('Unknown native serializer record')
        if key in actual[tag]:
            raise ValueError('Duplicate native serializer record')
        actual[tag][key] = value
    for tag in want:
        if actual[tag] != want[tag]:
            wrong = [key for key in actual[tag].keys() & want[tag].keys() if actual[tag][key] != want[tag][key]]
            examples = [(key, actual[tag][key], want[tag][key]) for key in wrong[:3]]
            raise ValueError(f'Serializer {tag} mismatch: missing={len(want[tag].keys()-actual[tag].keys())}, '
                             f'extra={len(actual[tag].keys()-want[tag].keys())}, wrong={len(wrong)}, examples={examples!r}')
    return {'serializer_cells': len(packed_cells), 'configurations': len(set(assignments.values())),
            'port_classifications': len(actual['P']), 'sequential_checks': len(actual['R']),
            'multi_clock_pins': sum(v[1] > 1 for v in actual['P'].values()),
            'falling_edge_checks': sum(v[1] == 'falling' for v in actual['R'].values()),
            'combinational_arcs': len(actual['C']), 'model_distribution': dict(Counter(assignments.values())), 'mismatches': 0}


def fixture_cells(packed):
    design = json.loads(packed.read_text()); top, = design['modules'].values()
    constants = {b for c in top['cells'].values() if c['type'] in ('PSEUDO_GND', 'PSEUDO_VCC')
                 for bits in c['connections'].values() for b in bits}
    return {name: {**c, 'constant_bits': constants} for name, c in top['cells'].items() if c['type'] in TYPES}


def check(backend, characterization, out, workers=8, source=None, inventory=None, gate=None):
    b = json.loads(backend.read_text())
    if b['status'] != 'SERDES_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING':
        raise ValueError('Expected completed isolated serializer backend')
    binary = Path(b['binary']['path'])
    if describe(binary) != b['binary']:
        raise ValueError('Serializer backend binary changed')
    if describe(b['tables']['path']) != b['tables']:
        raise ValueError('Prepared serializer table changed')
    prepared = json.loads(Path(b['tables']['path']).read_text())
    for key, filename in [('raw', 'timing-arcs-compact.json'), ('configs', 'configurations.json'), ('semantic', 'semantic-summary.json')]:
        if describe(characterization / filename) != prepared[key]:
            raise ValueError('Independently characterized vendor source changed')
    models = raw_reference(characterization)
    if len(models) != 3 or sum(len(m['config']['full_design_cells']) for m in models) != 358:
        raise ValueError('Complete serializer scope changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'helper': describe(__file__), 'workers': workers,
            'scope': 'COMPLETE_SERIALIZER_INTRINSIC_CALLBACKS_NOT_CLOCK_PHASE_FAMILY_FULL_TIMING_OR_ROUTE',
            'hardware_accessed': False, 'live_full_route_changed': False, 'numerical_timing': 'NOT_QUALIFIED'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    def command(design, audit=None, packed=None, part='xc7k480tffg1156-2', mode='on', full=False):
        argv = [str(binary), '--chipdb', CHIPDB, '--device', part, '--json', str(design), '--pack-only', '--threads', '8']
        if mode is not None:
            argv += ['-o', 'serdes-vivado-timing=' + mode]
        if audit:
            argv += ['-o', 'serdes-timing-audit=' + str(audit)]
        if packed:
            argv += ['--write', str(packed)]
        if full:
            argv += ['--freq', '100.0', '--seed', '1', '-o', 'xdc=' + str(source / 'openxc7.xdc'),
                     '-o', 'dsp-vivado-timing=on', '-o', 'clock-feedback-vivado=on',
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
            if g['status'] != 'ALL_SERDES_CONFIGURATION_NATIVE_CALLBACKS_PASS_FULL_DESIGN_CHECK_PENDING' or g['backend'] != describe(backend):
                raise ValueError('Native configuration gates do not match this backend')
            inv = json.loads(inventory.read_text())
            configs = json.loads((characterization / 'configurations.json').read_text())
            if describe(inventory) != configs['inventory']:
                raise ValueError('Full named serializer inventory changed')
            pack_manifest = json.loads((source.parent.parent / 'full-packed-dsp-inventory-20261011T223120Z/manifest.json').read_text())
            for name in ('constrained.json', 'openxc7.xdc'):
                if describe(source / name) != pack_manifest['inputs'][name]:
                    raise ValueError('Full source input changed')
            cells = {c['name']: c for c in inv['cells'] if c['type'] in TYPES}
            audit = out / 'full-serdes-callbacks.tsv'
            argv = command(source / 'constrained.json', audit, full=True)
            save(stage='full-native-pack', full_inputs=pack_manifest['inputs'], profile=pack_manifest['profile'], inventory=describe(inventory), gate=describe(gate))
            print('FULL_SERDES_NATIVE_AUDIT_STARTED ' + str(out), flush=True)
            _, code = run('full-pack', argv)
            save(native_exit=code)
            if code:
                raise RuntimeError('Complete native serializer audit failed')
            comparison = compare(audit, characterization, cells, 'full')
            save(status='COMPLETE_358_SERDES_NATIVE_CALLBACKS_PASS_CLOCK_PHASE_FAMILY_AND_FULL_TIMING_PENDING',
                 comparison=comparison, audit=describe(audit))
        else:
            raw = out / 'probe.yosys.json'
            # Use only the already-characterized serializer declarations. The
            # unrelated vendor BUFGCTRL SIM_DEVICE property has no Yosys
            # library equivalent and does not belong in this callback fixture.
            declarations, instances = [], []
            for model in models:
                c = model['config']; name = c['probe_cell']; connections = []
                for port in c['ports']:
                    pin = port['name']
                    if c['primitive'] == 'ISERDESE2' and pin == 'CLKB':
                        connections.append('.CLKB(' + name + '_CLK)'); continue
                    declarations.append(port['direction'] + ' wire ' + name + '_' + pin)
                    connections.append('.' + pin + '(' + name + '_' + pin + ')')
                params = ','.join('.' + p + '(' + render(v) + ')' for p, v in c['parameters'].items())
                instances.append(c['primitive'] + ' #(' + params + ') ' + name + '(' + ','.join(connections) + ');')
            rtl = out / 'serializer_configs.v'
            rtl.write_text('module phy_configs(' + ','.join(declarations) + ');\n' + '\n'.join(instances) + '\nendmodule\n')
            script = f'read_verilog -lib +/xilinx/cells_sim.v; read_verilog -lib +/xilinx/cells_xtra.v; read_verilog {rtl}; hierarchy -check -top phy_configs; select phy_configs; write_json -selected {raw}'
            _, code = run('yosys', ['yosys', '-p', script])
            if code:
                raise RuntimeError('Serializer fixture elaboration failed')
            design = json.loads(raw.read_text()); top = design['modules']['phy_configs']
            selected = {m['config']['probe_cell'] for m in models}
            top['cells'] = {n: c for n, c in top['cells'].items() if n in selected}
            if set(top['cells']) != selected:
                raise ValueError('Elaborated serializer configuration scope changed')
            # These are timing-only packed-cell fixtures, with no external I/O
            # site placement. The separate full-design check exercises the
            # actual I/O packer, IDELAY topology and constrained physical sites.
            for model in models:
                c = model['config']; cell = top['cells'][c['probe_cell']]
                if cell['type'] != c['primitive']:
                    raise ValueError('Elaborated serializer primitive differs')
                cell['type'] = c['packed_type']
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
                    if expected['kind'] == default['kind'] and expected['value'] == default['value']:
                        del params[name]; removed += 1
            missing = json.loads(json.dumps(design)); del missing['modules']['phy_configs']['cells']['phy_00']['connections']['CLKDIVP']
            tied = json.loads(json.dumps(design)); tied['modules']['phy_configs']['cells']['phy_00']['connections']['CLKDIVP'] = ['0']
            unsupported = json.loads(json.dumps(design)); unsupported['modules']['phy_configs']['cells']['phy_00']['parameters']['DATA_WIDTH'] = '00000000000000000000000000000110'
            cases = {'all-configurations': (probe, None, 'on', True),
                     'defaults-omitted': (write('defaults-omitted', omitted), None, 'on', True),
                     'missing-clock': (write('missing-clock', missing), None, 'on', True),
                     'tied-clock': (write('tied-clock', tied), None, 'on', True),
                     'default-off': (probe, None, None, False),
                     'unsupported-mode': (write('unsupported-mode', unsupported), 'Unsupported serializer timing configuration', 'on', False),
                     'invalid-option': (probe, 'serdes-vivado-timing must be on or off', 'maybe', False),
                     'wrong-speed-grade': (probe, 'characterized only for xc7k480tffg1156-2', 'on', False)}
            jobs = []
            for name, (path, rejection, mode, audit_enabled) in cases.items():
                audit = out / (name + '.callbacks.tsv') if audit_enabled else None
                packed = out / (name + '.packed.json') if audit_enabled else None
                part = 'xc7k480tffg1156-1' if name == 'wrong-speed-grade' else 'xc7k480tffg1156-2'
                jobs.append((name, command(path, audit, packed, part=part, mode=mode)))
            save(stage='parallel-native-callback-checks', cases=list(cases), declared_defaults_removed=removed, fixture_input_drivers=len(input_bits))
            print(f'RUNNING {len(jobs)} independent native serializer checks with {workers} workers', flush=True)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                results = dict(pool.map(lambda item: run(*item), jobs))
            save(native_results=results)
            comparisons = {}
            for name, (_, rejection, _, audit_enabled) in cases.items():
                if rejection:
                    if results[name] != 125 or rejection not in (out / (name + '.log')).read_text():
                        raise ValueError('Native rejection did not match: ' + name)
                elif results[name]:
                    raise RuntimeError('Native serializer case failed: ' + name)
                if audit_enabled:
                    comparisons[name] = compare(out / (name + '.callbacks.tsv'), characterization,
                                                fixture_cells(out / (name + '.packed.json')), 'fixture')
            save(status='ALL_SERDES_CONFIGURATION_NATIVE_CALLBACKS_PASS_FULL_DESIGN_CHECK_PENDING', comparisons=comparisons)
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
