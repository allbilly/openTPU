#!/usr/bin/env python3
"""Query datapath-only constraints on all actual surviving mailbox FF pairs."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe


def query(inventory: Path, simulation: Path, out: Path):
    inv = json.loads(inventory.read_text())
    sim = json.loads(simulation.read_text())
    if (inv['status'] != 'COMPLETE_PACKED_MAILBOX_PAYLOAD_AND_SYNCHRONIZER_TOPOLOGY_PASS_TIMING_PENDING'
            or inv['payload_crossings'] != 1103 or describe(inv['payloads']['path']) != inv['payloads']):
        raise ValueError('Complete packed mailbox topology has not passed')
    if sim['status'] != 'ALL_MAILBOX_DIGITAL_LATENCY_AND_BOUNDED_BUS_DELAY_CASES_PASS':
        raise ValueError('Digital latency gate has not passed')
    sim_inventory = json.loads(Path(sim['inventory']['path']).read_text())
    if sim_inventory['packed_netlist'] != inv['packed_netlist'] or sim['summary']['positive_cases'] != 22:
        raise ValueError('Digital latency gate uses a different packed input')
    records = json.loads(Path(inv['payloads']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': 'xc7k480tffg1156-2',
            'helper': describe(__file__), 'inventory': describe(inventory), 'simulation': describe(simulation),
            'scope': 'ALL_ACTUAL_PAYLOAD_FF_PAIR_CONFIGURATIONS_WITH_STANDIN_CLOCKS_ENABLES_NOT_PARENT_DESIGN_PLACEMENT_OR_FUNCTION',
            'hardware_accessed': False, 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        lines = [f'module mailbox_paths(input core_clk,tck,request_store,request_capture,response_store,response_capture,',
                 f'input [{len(records)-1}:0] data, output [{len(records)-1}:0] result);']
        mapped = []
        undefined_inits = 0
        for i, record in enumerate(records):
            request = record['capture_clock'] == 'core_clk'
            role = 'request' if request else 'response'
            source, capture = f'source_{role}_{record["index"]}', f'capture_{role}_{record["index"]}'
            lines.append(f'wire intermediate_{i};')
            for name, ff, clock, enable, d, q in [
                    (source, record['source_ff'], record['source_clock'], role + '_store', f'data[{i}]', f'intermediate_{i}'),
                    (capture, record['capture_ff'], record['capture_clock'], role + '_capture', f'intermediate_{i}', f'result[{i}]')]:
                if not ff['attributes'].get('X_FFSYNC') or ff['parameters'].get('IS_C_INVERTED', '0').strip('0'):
                    raise ValueError('Unexpected source/capture FF mode')
                raw_init = ff['parameters'].get('INIT', '0')
                if raw_init == 'x' and ff['attributes'].get('X_ORIG_TYPE') == 'FDRE':
                    # The actual FASM writer resolves undefined FDRE INIT to
                    # its primitive default zero. INIT does not affect the
                    # datapath delay but must match the programmed mode.
                    init = 0
                    undefined_inits += 1
                else:
                    init = int(raw_init, 2)
                lines.append(f'(* DONT_TOUCH="TRUE" *) FDRE #(.INIT(1\'b{init}),.IS_C_INVERTED(1\'b0)) {name} '
                             f'(.C({clock}),.CE({enable}),.R(1\'b0),.D({d}),.Q({q}));')
            mapped.append({'source': source, 'capture': capture, 'index': record['index'],
                           'source_packed_cell': record['source_cell'], 'capture_packed_cell': record['capture_cell'],
                           'budget_ns': 20 if request else 300, 'direction': role})
        lines.append('endmodule\n')
        (out / 'mailbox_paths.v').write_text('\n'.join(lines))
        (out / 'pair-map.json').write_text(json.dumps(mapped, indent=2) + '\n')
        tcl = '''set_param general.maxThreads 8
create_project -in_memory -part xc7k480tffg1156-2
read_verilog mailbox_paths.v
synth_design -top mailbox_paths -part xc7k480tffg1156-2 -mode out_of_context
create_clock -name core_clk -period 10 [get_ports core_clk]
create_clock -name tck -period 166.666667 [get_ports tck]
set_max_delay -datapath_only 20 -from [get_cells source_request_*] -to [get_cells capture_request_*]
set_max_delay -datapath_only 300 -from [get_cells source_response_*] -to [get_cells capture_response_*]
write_checkpoint -force mailbox_paths.dcp
set f [open paths.tsv w]
puts $f "source\\tcapture\\trequirement_ns\\tdatapath_ns\\tslack_ns\\tstart_pin\\tend_pin\\tmin_paths"
'''
        for i, record in enumerate(mapped):
            source, capture = record['source'], record['capture']
            tcl += f'''set p [get_timing_paths -from [get_cells {source}] -to [get_cells {capture}] -delay_type max -max_paths 1 -nworst 1]
if {{[llength $p] != 1}} {{error "Expected one direct mailbox datapath: {source}"}}
set hp [get_timing_paths -from [get_cells {source}] -to [get_cells {capture}] -delay_type min -no_report_unconstrained -max_paths 1 -nworst 1]
puts $f "{source}\\t{capture}\\t[get_property REQUIREMENT $p]\\t[get_property DATAPATH_DELAY $p]\\t[get_property SLACK $p]\\t[get_property STARTPOINT_PIN $p]\\t[get_property ENDPOINT_PIN $p]\\t[llength $hp]"
'''
            if i in (0, 572):
                tcl += f'report_timing -of_objects $p -file {record["direction"]}-example.rpt\nreport_property -all $p -file {record["direction"]}-path-properties.rpt\n'
                tcl += f'''set rawmin [get_timing_paths -from [get_cells {source}] -to [get_cells {capture}] -delay_type min -max_paths 1]
if {{[llength $rawmin]}} {{report_timing -of_objects $rawmin -file {record["direction"]}-raw-min.rpt; report_property -all $rawmin -file {record["direction"]}-raw-min-properties.rpt}}
'''
        tcl += 'close $f\nreport_exceptions -file exceptions.rpt\nputs "ALL_MAILBOX_DATAPATHS_EXPORTED|1103"\n'
        script = out / 'query.tcl'
        script.write_text(tcl)
        argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace', '-source', str(script)]
        (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
        save(stage='native-vendor-query', pair_map=describe(out / 'pair-map.json'), rtl=describe(out / 'mailbox_paths.v'),
             undefined_FDRE_INIT_resolved_to_primitive_default_zero=undefined_inits)
        print('ALL_MAILBOX_VENDOR_DATAPATH_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / 'native.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Full mailbox datapath query failed')
        expected = {record['source']: record for record in mapped}
        seen = set()
        with (out / 'paths.tsv').open() as stream:
            for row in csv.DictReader(stream, delimiter='\t'):
                record = expected[row['source']]
                if row['source'] in seen or row['capture'] != record['capture']:
                    raise ValueError('Duplicate or incorrect direct mailbox path')
                seen.add(row['source'])
                requirement, datapath, slack = [Decimal(row[key]) for key in ('requirement_ns', 'datapath_ns', 'slack_ns')]
                if (any(not value.is_finite() for value in (requirement, datapath, slack))
                        or requirement != record['budget_ns'] or int(row['min_paths']) != 0
                        or row['start_pin'] != record['source'] + '/C' or row['end_pin'] != record['capture'] + '/D'):
                    raise ValueError('Vendor datapath-only semantics or scope differs')
        if seen != set(expected):
            raise ValueError('Full surviving payload scope incomplete')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='ALL_1103_VENDOR_MAILBOX_DATAPATH_ONLY_REQUIREMENTS_PASS_NATIVE_IMPORT_PENDING',
             comparison={'payload_paths': 1103, 'request_paths': 572, 'response_paths': 531,
                         'request_budget_ns': 20, 'response_budget_ns': 300,
                         'hold_paths': 0, 'scope': 'EXACT_FF_PAIRS_WITH_STANDIN_ENABLES_CLOCKS_NOT_ROUTED_PARENT_DESIGN'},
             paths=describe(out / 'paths.tsv'), completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(info['comparison']), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'simulation', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    query(args.inventory.resolve(), args.simulation.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
