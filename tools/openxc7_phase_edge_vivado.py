#!/usr/bin/env python3
"""Measure actual setup/hold clock edges on exact-part vendor register paths."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
from fractions import Fraction
import json
from math import gcd
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_phy_vivado_timing import render


CASES = [
    ('same_rising', 'primary', 0, 'primary', 0),
    ('primary_rise_fall', 'primary', 0, 'primary', 1),
    ('primary_fall_rise', 'primary', 1, 'primary', 0),
    ('quarter_forward', 'c3', 0, 'c4', 0),
    ('quarter_reverse', 'c4', 0, 'c3', 0),
    ('ddr_rise_fall', 'c3', 0, 'c3', 1),
    ('ddr_fall_rise', 'c3', 1, 'c3', 0),
    ('slow_fast', 'c2', 0, 'c3', 0),
    ('fast_slow', 'c3', 0, 'c2', 0),
    ('common_fine_phase', 'c0', 0, 'c1', 0),
]


def expected(scenario, case):
    shift = Fraction(1250) if scenario == 'shifted' else Fraction(0)
    primary_high = Fraction(2500) if scenario == 'shifted' else Fraction(5000)
    waves = {'primary': (Fraction(10000), shift, primary_high),
             'c0': (Fraction(10000), shift, Fraction(5000)),
             'c1': (Fraction(2500), shift, Fraction(1250)),
             'c2': (Fraction(10000), shift, Fraction(5000)),
             'c3': (Fraction(2500), shift, Fraction(1250)),
             'c4': (Fraction(2500), shift + 625, Fraction(1250))}
    _, source, se, target, te = case
    sp, ss, sh = waves[source]; tp, ts, th = waves[target]
    unit = Fraction(gcd(sp.numerator * tp.denominator, tp.numerator * sp.denominator), sp.denominator * tp.denominator)
    relative = (ts + te * th - ss - se * sh) % unit
    return {'max': relative if relative else unit, 'min': relative - unit if relative else Fraction(0)}


def query(characterization, out, reuse_query=None):
    cfg = json.loads((characterization / 'configurations.json').read_text())
    mmcm = next(c for c in cfg['configs'] if c['probe_cell'] == 'phy_03')
    out.mkdir(parents=True, exist_ok=False)
    params = ',\n'.join('.' + name + '(' + render(value) + ')' for name, value in mmcm['parameters'].items())
    connections = ['.CLKIN1(primary)', '.CLKIN2(secondary)', '.CLKINSEL(clkinsel)', '.CLKFBIN(feedback)', '.CLKFBOUT(fbout)',
                   '.PWRDWN(pwrdwn)', '.RST(reset)', '.DCLK(primary)', '.PSCLK(primary)', '.PSEN(psen)', '.PSINCDEC(psinc)',
                   ".DI(16'b0)", ".DADDR(7'b0)", ".DEN(1'b0)", ".DWE(1'b0)"]
    connections += ['.CLKOUT' + str(i) + '(c' + str(i) + ')' for i in range(7)]
    regs = []
    for i, (name, source, se, target, te) in enumerate(CASES):
        regs += [f'wire data_{name};',
                 f'(* DONT_TOUCH="TRUE" *) FDRE #(.IS_C_INVERTED(1\'b{se})) launch_{name} (.C({source}), .CE(1\'b1), .R(1\'b0), .D(data[{i}]), .Q(data_{name}));',
                 f'(* DONT_TOUCH="TRUE" *) FDRE #(.IS_C_INVERTED(1\'b{te})) capture_{name} (.C({target}), .CE(1\'b1), .R(1\'b0), .D(data_{name}), .Q(result[{i}]));']
    rtl = f'''module phase_edges(input primary, secondary, clkinsel, pwrdwn, reset, psen, psinc,
input [{len(CASES)-1}:0] data, output [{len(CASES)-1}:0] result);
wire feedback, fbout, c0, c1, c2, c3, c4, c5, c6;
(* DONT_TOUCH="TRUE" *) BUFG feedback_buffer (.I(fbout), .O(feedback));
(* DONT_TOUCH="TRUE" *) MMCME2_ADV #(
{params}) phy_03 ({','.join(connections)});
{chr(10).join(regs)}
endmodule
'''
    (out / 'phase_edges.v').write_text(rtl)
    tcl = '''set_param general.maxThreads 8
create_project -in_memory -part xc7k480tffg1156-2
read_verilog phase_edges.v
synth_design -top phase_edges -part xc7k480tffg1156-2 -mode out_of_context
create_clock -name primary -period 10 [get_ports primary]
set f [open paths.tsv w]
puts $f "scenario\\tcase\\tdelay_type\\tlaunch_edge_ns\\tcapture_edge_ns\\tstart_pin\\tend_pin"
'''
    property_tcl = 'set cf [open cell-properties.tsv w]\nputs $cf "property\\tvalue"\n'
    for name in sorted(mmcm['parameters']):
        property_tcl += f'puts $cf "{name}\\t[get_property {name} [get_cells phy_03]]"\n'
    property_tcl += 'close $cf\n'
    tcl += property_tcl
    for scenario in ('baseline', 'shifted'):
        if scenario == 'shifted': tcl += 'create_clock -name primary -period 10 -waveform {1.25 3.75} [get_ports primary]\n'
        tcl += 'update_timing\n'
        for name, _, _, _, _ in CASES:
            for delay_type in ('max', 'min'):
                tcl += f'''set p [get_timing_paths -from [get_pins launch_{name}/Q] -to [get_pins capture_{name}/D] -delay_type {delay_type} -max_paths 1 -nworst 1]
if {{[llength $p] != 1}} {{error "Expected one actual {scenario}/{name}/{delay_type} register path"}}
puts $f "{scenario}\\t{name}\\t{delay_type}\\t[get_property STARTPOINT_CLOCK_EDGE $p]\\t[get_property ENDPOINT_CLOCK_EDGE $p]\\t[get_property STARTPOINT_PIN $p]\\t[get_property ENDPOINT_PIN $p]"
report_timing -of_objects $p -file {scenario}-{name}-{delay_type}.rpt
'''
    tcl += 'close $f\nputs "PHASE_EDGE_PATHS_EXPORTED|40"\n'
    script = out / 'query.tcl'; script.write_text(tcl)
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace', '-source', str(script)]
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': 'xc7k480tffg1156-2',
            'scope': 'ACTUAL_REGISTER_CLOCK_EDGE_PATHS_NOT_ROUTED_SKEW_OR_FULL_BOARD_TIMING', 'cases': CASES,
            'source_configuration': describe(characterization / 'configurations.json'), 'helper': describe(__file__),
            'hardware_accessed': False, 'live_full_route_changed': False}
    def save(**fields): info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    try:
        save(); (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
        if reuse_query:
            if (reuse_query / 'native.exit').read_text().strip() != '0': raise ValueError('Completed vendor query did not exit 0')
            for name in ('phase_edges.v', 'query.tcl'):
                if digest(out / name) != digest(reuse_query / name): raise ValueError('Reused vendor inputs differ')
            for name in ('paths.tsv', 'cell-properties.tsv', 'query.log', 'command.json', 'native.exit'):
                shutil.copy2(reuse_query / name, out / name)
            for report in reuse_query.glob('*.rpt'): shutil.copy2(report, out / report.name)
            save(native_exit=0, native_rerun=False, reused_native_query=describe(reuse_query / 'manifest.json'),
                 reused_paths=describe(reuse_query / 'paths.tsv'), reused_properties=describe(reuse_query / 'cell-properties.tsv'))
            print('REVALIDATING_COMPLETED_VENDOR_QUERY ' + str(reuse_query), flush=True)
        else:
            print('PHASE_EDGE_VENDOR_QUERY_STARTED ' + str(out), flush=True)
            with (out / 'query.log').open('w') as log: result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            (out / 'native.exit').write_text(str(result.returncode) + '\n'); save(native_exit=result.returncode)
            if result.returncode: raise RuntimeError('Actual vendor edge query failed')
        with (out / 'cell-properties.tsv').open() as stream:
            observed = {r['property']: r['value'] for r in csv.DictReader(stream, delimiter='\t')}
        for name, value in mmcm['parameters'].items():
            actual = observed[name]
            if value['kind'] == 'string':
                if value['value'] in ('FALSE', 'TRUE') and actual.upper() in ('FALSE', 'TRUE', '0', '1'):
                    matches = (actual.upper() in ('TRUE', '1')) == (value['value'] == 'TRUE')
                else:
                    matches = actual == value['value']
            elif value['kind'] == 'real':
                matches = Decimal(actual) == Decimal(str(value['value']))
            else:
                literal = re.fullmatch(r"(\d+)'([bBhHdDoO])([0-9a-fA-F]+)", actual)
                parsed = int(literal[3], {'b': 2, 'h': 16, 'd': 10, 'o': 8}[literal[2].lower()]) if literal else int(actual)
                matches = parsed == value['value']
            if not matches: raise ValueError(f'Actual MMCM parameter differs: {name}: {actual} vs {value!r}')
        by_name = {c[0]: c for c in CASES}; rows = []; seen = set()
        with (out / 'paths.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                key = (row['scenario'], row['case'], row['delay_type'])
                if key in seen: raise ValueError('Duplicate vendor path')
                seen.add(key)
                actual = (Fraction(row['capture_edge_ns']) - Fraction(row['launch_edge_ns'])) * 1000
                wanted = expected(row['scenario'], by_name[row['case']])[row['delay_type']]
                if actual != wanted: raise ValueError(f'Actual vendor edge relation differs: {key!r}: {actual} vs {wanted}')
                # Vivado's register startpoint is the clock pin; the data
                # traversal begins at Q after that clock-to-Q arc.
                if row['start_pin'] != 'launch_' + row['case'] + '/C' or row['end_pin'] != 'capture_' + row['case'] + '/D':
                    raise ValueError('Vendor path endpoints differ')
                rows.append({**row, 'relative_edge_ps': str(actual)})
        if len(seen) != 40: raise ValueError('Complete vendor edge scope missing')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='ALL_40_VENDOR_REGISTER_EDGE_RELATIONS_MATCH_EXACT_ARITHMETIC_ENGINE_PENDING',
             comparison={'paths': 40, 'cases': 10, 'scenarios': 2, 'mismatches': 0}, rows=rows,
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(info['comparison']), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('characterization', 'out'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--reuse-query', type=Path)
    args = parser.parse_args(); query(args.characterization.resolve(), args.out.resolve(), args.reuse_query.resolve() if args.reuse_query else None)


if __name__ == '__main__': main()
