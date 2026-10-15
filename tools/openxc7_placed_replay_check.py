#!/usr/bin/env python3
"""Qualify native xc7 placed reload using the complete clock-topology fixture."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from fedora_openxc7 import describe
from openxc7_bufg_route_guard import fasm_check


def clocks(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    values = {r.pop('net'): r for r in rows}
    if len(values) != len(rows) or not values:
        raise ValueError('Duplicate or missing generated clock constraints')
    return values


def cells(path):
    design = json.loads(path.read_text())['modules']
    if len(design) != 1:
        raise ValueError('Expected one native fixture module')
    return next(iter(design.values()))['cells']


def bindings(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    values = {r['cell']: r['bel'] for r in rows}
    if not values or len(values) != len(rows):
        raise ValueError('Duplicate or empty exact native binding audit')
    return values


def check(parent, candidate, template, clock_inventory, out):
    p, c = (json.loads(x.read_text()) for x in (parent, candidate))
    if c['status'] != 'PLACED_REPLAY_BACKEND_BUILD_PASS_FIXTURE_PENDING':
        raise ValueError('Completed isolated replay build required')
    if c['parent'] != describe(parent):
        raise ValueError('Candidate has a different parent')
    argv = json.loads(template.read_text())
    if argv[0] != p['binary']['path']:
        raise ValueError('Fixture parent executable differs')
    frozen = [p['binary'], c['binary'], describe(argv[argv.index('--chipdb') + 1]),
              describe(argv[argv.index('--json') + 1]),
              describe(next(a[4:] for a in argv if a.startswith('xdc=')))]
    if any(describe(x['path']) != x for x in frozen):
        raise ValueError('Frozen native fixture inputs differ')
    out.mkdir(parents=True, exist_ok=False)
    inventory = json.loads(clock_inventory.read_text())
    frozen.append(describe(clock_inventory))
    prototype = Path(argv[argv.index('--json') + 1])
    design = json.loads(prototype.read_text())
    if len(design['modules']) != 1:
        raise ValueError('Single-module clock prototype required')
    module = next(iter(design['modules'].values()))
    fixture_cells = module['cells']
    control_driver = fixture_cells['clock_load_u_ld.BUFG_1']
    if control_driver['type'] != 'FDRE' or len(control_driver['connections']['Q']) != 1:
        raise ValueError('Existing diagnostic core-clock register required')
    control_bit = control_driver['connections']['Q'][0]
    controls = []
    dynamic_controls = []
    for record in inventory['cells']:
        if record['type'] not in ('MMCME2_ADV_MMCME2_ADV', 'PLLE2_ADV_PLLE2_ADV'):
            continue
        cell = fixture_cells[record['name']]
        actual = cell['connections']['PWRDWN']
        old = cell['parameters'].get('IS_PWRDWN_INVERTED', '0')
        wanted = record['parameters']['IS_PWRDWN_INVERTED']
        if actual != ['0'] or old != '0' or wanted != {'kind': 'integer', 'value': 1}:
            raise ValueError('Unexpected diagnostic/full PWRDWN representation')
        cell['parameters']['IS_PWRDWN_INVERTED'] = '1'
        cell['connections']['PWRDWN'] = ['1']
        if (int(actual[0]) ^ int(old, 2)) != (1 ^ wanted['value']):
            raise ValueError('Effective PWRDWN behavior differs')
        controls.append(record['name'])
        for port in ('RST', 'PSEN', 'PSINCDEC'):
            key = 'IS_' + port + '_INVERTED'
            if port not in cell['connections']:
                continue
            if (record['parameters'].get(key, {'kind': 'integer', 'value': 0}) != {'kind': 'integer', 'value': 0}
                    or cell['connections'][port] != ['0']):
                raise ValueError('Unexpected full-design dynamic clock control')
            cell['connections'][port] = [control_bit]
            dynamic_controls.append({'cell': record['name'], 'port': port,
                                     'driver': 'clock_load_u_ld.BUFG_1.Q'})
    if len(controls) != 4:
        raise ValueError('All four full-design clock controls required')
    staged = out / 'clock-model-fixture.json'
    staged.write_text(json.dumps(design, indent=2) + '\n')
    frozen.append(describe(staged))
    argv[argv.index('--json') + 1] = str(staged)
    original_xdc = Path(next(a[4:] for a in argv if a.startswith('xdc=')))
    clock_lines = []
    for line in original_xdc.read_text().splitlines():
        stripped = line.strip()
        if stripped.startswith('create_clock '):
            clock_lines.append(line)
        elif stripped and not stripped.startswith(('#', 'set_property ')):
            raise ValueError('Unsupported clock replay XDC command')
    if not clock_lines:
        raise ValueError('Frozen base clock constraints required')
    clock_xdc = out / 'clock-replay.xdc'
    clock_xdc.write_text('\n'.join(clock_lines) + '\n')
    frozen.append(describe(clock_xdc))
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'parent': describe(parent), 'candidate': describe(candidate), 'template': describe(template),
            'helper': describe(__file__), 'inputs': frozen, 'hardware_accessed': False,
            'clock_only_xdc': describe(clock_xdc),
            'clock_inventory': describe(clock_inventory),
            'equivalent_inactive_clock_controls': controls,
            'dynamic_clock_controls': dynamic_controls,
            'original_jobs_changed': False, 'scope': 'CLOCK_TOPOLOGY_REPLAY_NOT_FULL_ACCELERATOR_ROUTE',
            'timing_signoff': False, 'cases': {}}

    def save(**values):
        info.update(values)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def command(binary, directory, placed=None, matrix='off', prepare=False):
        args, i = [binary], 1
        while i < len(argv):
            item = argv[i]
            if item in ('--write', '--report'):
                i += 2
                continue
            if item == '-o' and argv[i + 1].startswith(('fasm=', 'delay-matrix=', 'bufg-route-audit=')):
                i += 2
                continue
            if item == '--json' and placed:
                args.extend((item, str(placed)))
                i += 2
                continue
            args.append(item)
            i += 1
        args.extend(('-o', 'clock-feedback-vivado=on', '-o', 'delay-matrix=' + matrix,
                     '-o', 'clock-vivado-timing=on', '-o', 'clock-family-vivado=on',
                     '-o', 'phase-engine-vivado=on', '-o', 'dsp-vivado-timing=on',
                     '-o', 'serdes-vivado-timing=on',
                     '-o', 'phase-domain-audit=' + str(directory / 'domains.tsv'),
                     '-o', 'clock-waveform-audit=' + str(directory / 'waveforms.tsv'),
                     '-o', 'clock-constraint-audit=' + str(directory / 'clocks.tsv'),
                     '--write', str(directory / 'native.json'), '--report', str(directory / 'timing.json')))
        if prepare:
            args.append('--no-route')
        else:
            args.extend(('-o', 'fasm=' + str(directory / 'native.fasm'),
                         '-o', 'bufg-route-audit=' + str(directory / 'clock.policy.tsv')))
        if placed:
            args.extend(('--no-pack', '--no-place'))
            args.extend(('-o', 'placed-replay-bindings=' + str(directory / 'bindings')))
            args.extend(('-o', 'placed-replay-clock-xdc=' + str(clock_xdc)))
        return args

    def run(name, args):
        directory = out / name
        (directory / 'command.json').write_text(json.dumps(args, indent=2) + '\n')
        save(stage=name)
        with (directory / 'native.log').open('w') as log:
            child = subprocess.Popen(args, cwd=directory, stdout=log, stderr=subprocess.STDOUT)
            fields = (Path('/proc') / str(child.pid) / 'stat').read_text().split(') ', 1)[1].split()
            save(native_pid=child.pid, native_start_ticks=int(fields[19]))
            print(name.upper() + '_STARTED PID ' + str(child.pid), flush=True)
            code = child.wait()
        (directory / 'native.exit').write_text(str(code) + '\n')
        if code:
            raise RuntimeError(name + ' native exit ' + str(code))
        info['cases'][name] = {'native_exit': code, 'command': describe(directory / 'command.json')}
        save()
        return directory

    try:
        save(stage='baseline-placement')
        prep = out / 'parent-placement'
        prep.mkdir()
        run('parent-placement', command(p['binary']['path'], prep, matrix=str(prep / 'matrix.txt'), prepare=True))
        baseline_cells = cells(prep / 'native.json')
        baseline_bindings = {name: cell['attributes']['NEXTPNR_BEL']
                             for name, cell in baseline_cells.items()
                             if cell['type'] not in ('PSEUDO_GND', 'PSEUDO_VCC')}
        baseline_clocks = clocks(prep / 'clocks.tsv')
        with (prep / 'domains.tsv').open() as stream:
            baseline_domains = sorted(tuple(row.items()) for row in csv.DictReader(stream, delimiter='\t'))
        if len(baseline_cells) < 50 or len(baseline_clocks) < 20 or not (prep / 'matrix.txt').is_file():
            raise ValueError('Clock fixture or measured delay matrix scope differs')
        routes = []
        for name, cached in [('candidate-rebuilt', False), ('candidate-cached', True), ('candidate-matrix-off', None)]:
            directory = out / name
            directory.mkdir()
            matrix = directory / 'matrix.txt'
            if cached:
                shutil.copy2(prep / 'matrix.txt', matrix)
            mode = 'off' if cached is None else str(matrix)
            run(name, command(c['binary']['path'], directory, prep / 'native.json', mode))
            if clocks(directory / 'clocks.tsv') != baseline_clocks:
                raise ValueError('Reloaded generated clock constraints differ')
            with (directory / 'domains.tsv').open() as stream:
                restored_domains = sorted(tuple(row.items()) for row in csv.DictReader(stream, delimiter='\t'))
            if restored_domains != baseline_domains:
                raise ValueError('Reloaded timing domain pairs or budgets differ')
            actual = cells(directory / 'native.json')
            if (bindings(directory / 'bindings.before.tsv') != baseline_bindings
                    or bindings(directory / 'bindings.after.tsv') != baseline_bindings):
                raise ValueError('Exact native bindings changed on reload or routing')
            if set(actual) != set(baseline_cells):
                raise ValueError('Reloaded cell inventory differs')
            for cell_name, cell in actual.items():
                old = baseline_cells[cell_name]
                if cell['type'] != old['type'] or cell['parameters'] != old['parameters']:
                    raise ValueError('Reloaded primitive or parameter differs')
            log = (directory / 'native.log').read_text()
            if 'Placed replay: generated clocks restored.' not in log:
                raise ValueError('Replay restoration did not execute')
            if cached is None:
                if matrix.exists() or 'Delay matrix:' in log:
                    raise ValueError('Explicit disabled matrix was rebuilt')
            elif matrix.read_bytes() != (prep / 'matrix.txt').read_bytes():
                raise ValueError('Rebuilt/cached measured matrix differs')
            elif cached and 'Delay matrix: loaded' not in log:
                raise ValueError('Measured cache was not loaded')
            elif not cached and 'offsets measured' not in log:
                raise ValueError('Measured matrix was not rebuilt')
            gate = fasm_check(directory / 'native.fasm')
            routes.append((directory / 'native.fasm').read_bytes())
            info['cases'][name].update(clock_driver_gate=gate,
                outputs={n: describe(directory / n) for n in ('native.json', 'clocks.tsv', 'native.fasm',
                                                               'bindings.before.tsv', 'bindings.after.tsv')})
            save()
        if routes[0] != routes[1]:
            raise ValueError('Rebuilt and cached measured matrices produce different routing/FASM')
        if any(describe(x['path']) != x for x in frozen):
            raise ValueError('Fixture inputs changed during check')
        save(status='PLACED_REPLAY_CLOCKS_MATRIX_CACHE_BINDINGS_AND_NATIVE_ROUTE_PASS_FULL_ROUTE_PENDING',
             fixture_cells=len(baseline_cells), restored_clock_constraints=len(baseline_clocks),
             rebuilt_and_cached_fasm_outputs_identical=True,
             timing_domain_pairs=len(baseline_domains), timing_domain_budgets_identical=True,
             disabled_matrix_fasm_identical=routes[0] == routes[2],
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('parent', 'candidate', 'template', 'clock-inventory', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    check(a.parent.resolve(), a.candidate.resolve(), a.template.resolve(), a.clock_inventory.resolve(), a.out.resolve())
