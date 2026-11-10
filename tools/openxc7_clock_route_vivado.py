#!/usr/bin/env python3
"""Route the actual clock-only diagnostic in Vivado and export physical PIPs."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phy_vivado_timing import library_parameters, render


def parameter(primitive, name, value):
    if primitive in ('MMCME2_ADV', 'PLLE2_ADV'):
        defaults, _ = library_parameters(primitive)
        if name not in defaults:
            raise ValueError('Unknown actual clock parameter: ' + name)
        kind = defaults[name]['kind']
        if kind == 'integer':
            if not isinstance(value, str) or not value or set(value) - {'0', '1'}:
                raise ValueError('Clock integer parameter is not binary')
            return str(int(value, 2))
        if kind == 'real':
            value = str(int(value, 2)) if isinstance(value, str) and value and not set(value) - {'0', '1'} else str(value)
            if not Decimal(value).is_finite():
                raise ValueError('Clock real parameter is not finite')
            return value
        return json.dumps(value)
    if primitive == 'FDRE' and name == 'INIT':
        return "1'b" + value
    if primitive == 'BSCANE2' and name == 'JTAG_CHAIN':
        return str(int(value, 2))
    return json.dumps(value)


def route(prototype, out):
    gate = json.loads((prototype / 'manifest.json').read_text())
    for key in ('prototype', 'xdc'):
        if describe(gate[key]['path']) != gate[key]:
            raise ValueError('Actual native clock prototype changed')
    design = json.loads(Path(gate['prototype']['path']).read_text())
    top, = design['modules'].values()
    expected = {'MMCME2_ADV': 3, 'PLLE2_ADV': 1, 'BUFG': 16, 'IBUF': 1, 'BSCANE2': 1, 'FDRE': 32}
    if dict(Counter(c['type'] for c in top['cells'].values())) != expected:
        raise ValueError('Complete actual clock prototype scope changed')
    out.mkdir(parents=True, exist_ok=False)
    all_bits = sorted({bit for cell in top['cells'].values() for bits in cell['connections'].values()
                       for bit in bits if isinstance(bit, int)})
    lines = ['module clock_probe(input wire SYS_CLK);']
    lines += ['wire n' + str(bit) + ';' for bit in all_bits]
    lines += ['assign n' + str(top['ports']['SYS_CLK']['bits'][0]) + ' = SYS_CLK;']
    mappings, adjustments = {}, []
    for index, (name, cell) in enumerate(top['cells'].items()):
        inst, primitive = f'probe_{index:03d}', cell['type']
        params = dict(cell['parameters'])
        connections = dict(cell['connections'])
        if primitive == 'IBUF' and 'CCIO_EN' in params:
            adjustments.append({'cell': name, 'parameter': 'CCIO_EN', 'value': params.pop('CCIO_EN'),
                                'reason': 'OPENXC7_LIBRARY_PARAMETER_ABSENT_FROM_INSTALLED_VIVADO_IBUF'})
        if primitive in ('MMCME2_ADV', 'PLLE2_ADV'):
            if 'COMPENSATION' not in params:
                params['COMPENSATION'] = 'INTERNAL'
                adjustments.append({'cell': name, 'parameter': 'COMPENSATION', 'value': 'INTERNAL',
                                    'reason': 'MATCH_EXISTING_NATIVE_BITSTREAM_DEFAULT'})
            for pin, value in [('CLKINSEL', '1'), ('CLKIN2', '0')]:
                if pin not in connections:
                    connections[pin] = [value]
                    adjustments.append({'cell': name, 'pin': pin, 'value': value,
                                        'reason': 'MAKE_IMPLICIT_SELECTED_REFERENCE_INPUT_EXPLICIT'})
        assignments = ', '.join('.' + key + '(' + parameter(primitive, key, value) + ')' for key, value in params.items())
        pins = []
        for pin, bits in connections.items():
            signals = [f'n{bit}' if isinstance(bit, int) else "1'b" + bit for bit in reversed(bits)]
            signal = signals[0] if len(signals) == 1 else '{' + ', '.join(signals) + '}'
            pins.append('.' + pin + '(' + signal + ')')
        loc = cell.get('attributes', {}).get('LOC')
        attrs = '(* DONT_TOUCH = "TRUE"' + (', LOC = ' + json.dumps(loc) if loc else '') + ' *)'
        lines.append(attrs + ' ' + primitive + (' #(' + assignments + ')' if assignments else '')
                     + ' ' + inst + ' (' + ', '.join(pins) + ');')
        mappings[name] = {'instance': inst, 'primitive': primitive, 'loc': loc, 'parameters': params,
                          'connections': connections}
    lines += ['endmodule']
    (out / 'clock_probe.v').write_text('\n'.join(lines) + '\n')
    (out / 'mapping.json').write_text(json.dumps(mappings, indent=2) + '\n')
    (out / 'adjustments.json').write_text(json.dumps(adjustments, indent=2) + '\n')
    bscan, = (row['instance'] for row in mappings.values() if row['primitive'] == 'BSCANE2')
    tcl = [
        'set_param general.maxThreads 8', 'set_param tcl.collectionResultDisplayLimit 0',
        'create_project -in_memory -part xc7k480tffg1156-2',
        'read_verilog {' + str(out / 'clock_probe.v') + '}',
        'synth_design -top clock_probe -part xc7k480tffg1156-2',
        'set_property PACKAGE_PIN AA28 [get_ports SYS_CLK]',
        'set_property IOSTANDARD LVCMOS18 [get_ports SYS_CLK]',
        'create_clock -name sys_50 -period 20 [get_ports SYS_CLK]',
        f'create_clock -name jtag_tck -period 166.666667 [get_pins {bscan}/TCK]',
        'set cf [open cells.tsv w]', 'puts $cf "cell\\tprimitive\\tloc\\tbel"',
    ]
    for name, row in mappings.items():
        inst = row['instance']
        tcl += [f'set c [get_cells {inst}]', f'if {{[llength $c] != 1}} {{error "Missing retained actual cell {inst}"}}',
                f'if {{[get_property REF_NAME $c] != "{row["primitive"]}"}} {{error "Retained actual primitive changed"}}']
        if row['primitive'] in ('MMCME2_ADV', 'PLLE2_ADV'):
            for key, raw in row['parameters'].items():
                if key in ('CLKFBOUT_MULT_F', 'CLKFBOUT_MULT', 'CLKOUT0_DIVIDE_F', 'CLKOUT0_DIVIDE', 'DIVCLK_DIVIDE'):
                    expected_value = parameter(row['primitive'], key, raw)
                    tcl += [f'if {{abs(double([get_property {key} $c]) - {expected_value}) > 0.000001}} {{error "Actual clock numeric parameter changed: {inst}/{key}"}}']
    tcl += ['opt_design', 'place_design', 'route_design', 'report_route_status -file route-status.rpt',
            'write_checkpoint -force clock-routed.dcp',
            'report_timing_summary -file timing.rpt', 'report_drc -file drc.rpt',
            'set rf [open routes.tsv w]', 'puts $rf "source_cell\\tsource_port\\tsource_site\\tsink_cell\\tsink_port\\tsink_site\\tnet\\troute_status\\tpips"',
            'set pf [open pips.tsv w]', 'puts $pf "source_cell\\tsource_port\\tpip"']
    for name, row in mappings.items():
        inst = row['instance']
        tcl += [f'set c [get_cells {inst}]', f'if {{[llength $c] != 1}} {{error "Actual cell removed by implementation"}}',
                f'puts $cf [join [list {{{name}}} [get_property REF_NAME $c] [get_property LOC $c] [get_property BEL $c]] "\\t"]']
        if row['loc']:
            tcl += [f'if {{[get_property LOC $c] != "{row["loc"]}"}} {{error "Explicit generator LOC changed"}}']
        if row['primitive'] not in ('MMCME2_ADV', 'PLLE2_ADV'):
            continue
        for port, bits in row['connections'].items():
            if not port.startswith('CLKOUT') and port != 'CLKFBOUT':
                continue
            sinks = [(n, s, p) for n, s in mappings.items() if s['primitive'] == 'BUFG'
                     for p, v in s['connections'].items() if p == 'I' and v == bits]
            if not sinks:
                continue
            tcl += [f'set net [get_nets -of_objects [get_pins {inst}/{port}]]',
                    'if {[llength $net] != 1} {error "Missing actual generator output net"}',
                    'set pips [get_pips -of_objects $net]',
                    f'foreach pip $pips {{puts $pf [join [list {{{name}}} {{{port}}} $pip] "\\t"]}}']
            for sink_name, sink, sink_port in sinks:
                tcl += [f'puts $rf [join [list {{{name}}} {{{port}}} [get_property LOC [get_cells {inst}]] {{{sink_name}}} {{{sink_port}}} [get_property LOC [get_cells {sink["instance"]}]] $net [get_property ROUTE_STATUS $net] [llength $pips]] "\\t"]']
    tcl += ['close $cf', 'close $rf', 'close $pf',
            'puts "ACTUAL_CLOCK_PROTOTYPE_VIVADO_ROUTE_COMPLETE"', 'exit 0']
    (out / 'route.tcl').write_text('\n'.join(tcl) + '\n')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'route.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'prototype': describe(prototype / 'manifest.json'),
            'prototype_json': gate['prototype'], 'helper': describe(__file__), 'part': 'xc7k480tffg1156-2', 'threads': 8,
            'mapping': describe(out / 'mapping.json'), 'parameter_adjustments': describe(out / 'adjustments.json'),
            'hardware_accessed': False, 'working_full_reference_modified': False, 'live_full_jobs_changed': False,
            'scope': 'EXACT_ACTUAL_CLOCK_PROTOTYPE_VIVADO_PHYSICAL_REFERENCE_NOT_FULL_BOARD_IMAGE'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-synthesis-placement-routing')
        print('ACTUAL_CLOCK_PROTOTYPE_VIVADO_ROUTE_STARTED ' + str(out), flush=True)
        with (out / 'native.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid)
            code = child.wait()
        (out / 'native.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Vivado actual clock prototype route failed')
        with (out / 'cells.tsv').open() as stream:
            retained = list(csv.DictReader(stream, delimiter='\t'))
        with (out / 'routes.tsv').open() as stream:
            routes = list(csv.DictReader(stream, delimiter='\t'))
        if len(retained) != 54 or len(routes) != 14 or any(row['route_status'] != 'ROUTED' or int(row['pips']) < 1 for row in routes):
            raise ValueError('Complete actual clock prototype retention/routing coverage differs')
        save(status='ALL_54_ACTUAL_CLOCK_CELLS_AND_14_GENERATOR_BUFFER_ROUTES_COMPLETE_PIP_COMPARISON_PENDING',
             actual_cells=len(retained), actual_generator_buffer_arcs=len(routes),
             outputs={name: describe(out / name) for name in ('cells.tsv', 'routes.tsv', 'pips.tsv', 'clock-routed.dcp', 'route-status.rpt', 'timing.rpt', 'drc.rpt')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'actual_cells': len(retained), 'arcs': len(routes)}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prototype', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    route(args.prototype.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
