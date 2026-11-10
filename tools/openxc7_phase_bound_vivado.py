#!/usr/bin/env python3
"""Measure register edge relations for declared DDR800 phase-bound snapshots."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
import csv
from datetime import datetime, timezone
from fractions import Fraction
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe


CASES = [('ddr_command', -1), ('ddr_reverse', 1), ('common_fine_phase', 0)]


def query(previous: Path, out: Path):
    gold = json.loads((previous / 'manifest.json').read_text())
    if gold['status'] != 'ALL_40_VENDOR_REGISTER_EDGE_RELATIONS_MATCH_EXACT_ARITHMETIC_ENGINE_PENDING' or gold['comparison']['mismatches']:
        raise ValueError('Expected completed exact-part edge query')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'part': 'xc7k480tffg1156-2', 'helper': describe(__file__), 'previous': describe(previous / 'manifest.json'),
            'source_rtl': describe(previous / 'phase_edges.v'), 'source_properties': describe(previous / 'cell-properties.tsv'),
            'scope': 'DECLARED_CLOCK_SNAPSHOT_REGISTER_PATHS_NOT_DYNAMIC_MMCM_MEASUREMENT_OR_ROUTED_TIMING',
            'hardware_accessed': False, 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        rtl = (previous / 'phase_edges.v').read_text()
        if rtl.count('output [9:0] result') != 1 or rtl.count('endmodule') != 1:
            raise ValueError('Vendor fixture changed')
        rtl = rtl.replace('output [9:0] result', 'output [11:0] result')
        extra = '''
wire data_ddr_command, data_ddr_reverse;
(* DONT_TOUCH="TRUE" *) FDRE #(.IS_C_INVERTED(1'b1)) launch_ddr_command (.C(primary), .CE(1'b1), .R(1'b0), .D(data[0]), .Q(data_ddr_command));
(* DONT_TOUCH="TRUE" *) FDRE capture_ddr_command (.C(c0), .CE(1'b1), .R(1'b0), .D(data_ddr_command), .Q(result[10]));
(* DONT_TOUCH="TRUE" *) FDRE launch_ddr_reverse (.C(c0), .CE(1'b1), .R(1'b0), .D(data[1]), .Q(data_ddr_reverse));
(* DONT_TOUCH="TRUE" *) FDRE #(.IS_C_INVERTED(1'b1)) capture_ddr_reverse (.C(primary), .CE(1'b1), .R(1'b0), .D(data_ddr_reverse), .Q(result[11]));
'''
        (out / 'phase_bounds.v').write_text(rtl.replace('endmodule', extra + '\nendmodule'))
        tcl = '''set_param general.maxThreads 8
create_project -in_memory -part xc7k480tffg1156-2
read_verilog phase_bounds.v
synth_design -top phase_edges -part xc7k480tffg1156-2 -mode out_of_context
create_clock -name primary -period 10 [get_ports primary]
set cf [open cell-properties.tsv w]
puts $cf "property\\tvalue"
'''
        with (previous / 'cell-properties.tsv').open() as stream:
            properties = {r['property']: r['value'] for r in csv.DictReader(stream, delimiter='\t')}
        for name in sorted(properties):
            tcl += f'puts $cf "{name}\\t[get_property {name} [get_cells phy_03]]"\n'
        tcl += 'close $cf\nset f [open paths.tsv w]\nputs $f "shift_ps\\tcase\\tdelay_type\\tlaunch_edge_ns\\tcapture_edge_ns\\tstart_pin\\tend_pin"\n'
        for shift in (-1250, 0, 1250):
            ns = shift / 1000
            tcl += f'''create_generated_clock -name fine0 -source [get_ports primary] -edges {{1 2 3}} -edge_shift {{{ns} {ns} {ns}}} [get_pins phy_03/CLKOUT0]
create_generated_clock -name fine1 -source [get_ports primary] -edges {{1 2 3}} -edge_shift {{{ns} {ns-3.75} {ns-7.5}}} [get_pins phy_03/CLKOUT1]
update_timing
'''
            for case, _ in CASES:
                for kind in ('max', 'min'):
                    tcl += f'''set p [get_timing_paths -from [get_pins launch_{case}/Q] -to [get_pins capture_{case}/D] -delay_type {kind} -max_paths 1 -nworst 1]
if {{[llength $p] != 1}} {{error "Expected one actual snapshot register path"}}
puts $f "{shift}\\t{case}\\t{kind}\\t[get_property STARTPOINT_CLOCK_EDGE $p]\\t[get_property ENDPOINT_CLOCK_EDGE $p]\\t[get_property STARTPOINT_PIN $p]\\t[get_property ENDPOINT_PIN $p]"
report_timing -of_objects $p -file shift{shift}-{case}-{kind}.rpt
'''
        tcl += 'close $f\nputs "PHASE_BOUND_SNAPSHOT_PATHS_EXPORTED|18"\n'
        script = out / 'query.tcl'
        script.write_text(tcl)
        argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace', '-source', str(script)]
        (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
        save(stage='native-vendor-query')
        print('PHASE_BOUND_SNAPSHOT_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / 'native.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Snapshot vendor query failed')
        with (out / 'cell-properties.tsv').open() as stream:
            actual = {r['property']: r['value'] for r in csv.DictReader(stream, delimiter='\t')}
        if actual != properties:
            raise ValueError('Snapshot query changed the exact MMCM parameters')
        rows, seen = [], set()
        with (out / 'paths.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                shift, case, kind = int(row['shift_ps']), row['case'], row['delay_type']
                key = (shift, case, kind)
                if key in seen:
                    raise ValueError('Duplicate vendor snapshot')
                seen.add(key)
                wanted = (2500 if kind == 'max' else 0) if case == 'common_fine_phase' else ((5000 if kind == 'max' else -5000) + (shift if case == 'ddr_command' else -shift))
                actual = (Fraction(row['capture_edge_ns']) - Fraction(row['launch_edge_ns'])) * 1000
                if actual != wanted or row['start_pin'] != 'launch_' + case + '/C' or row['end_pin'] != 'capture_' + case + '/D':
                    raise ValueError('Actual snapshot relation differs: ' + repr((key, actual, wanted)))
                rows.append({**row, 'relative_edge_ps': str(actual)})
        if seen != {(shift, case, kind) for shift in (-1250, 0, 1250) for case, _ in CASES for kind in ('max', 'min')}:
            raise ValueError('Vendor snapshot scope incomplete')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='ALL_18_VENDOR_PHASE_BOUND_SNAPSHOT_PATHS_PASS', rows=rows,
             comparison={'paths': 18, 'snapshots': 3, 'cases': 3, 'mismatches': 0,
                         'conditional_ddr_setup_budget_ps': 3750, 'conditional_ddr_hold_edge_ps': -3750},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(info['comparison']), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    query(args.previous.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
