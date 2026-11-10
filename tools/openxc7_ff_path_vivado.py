#!/usr/bin/env python3
"""Compare FF arc queries and effective paths in immutable Vivado checkpoints."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_ff_vivado_timing import SR_PORT


PROCEDURES = r'''
set af [open arcs.tsv w]
puts $af "stage\tcell\tarc\tproperty\tvalue"
set cf [open objects.tsv w]
puts $cf "stage\tobject\tproperty\tvalue"
set pf [open paths.tsv w]
puts $pf "stage\tcase\tmode\tcount\trequirement_ns\tdatapath_ns\tslack_ns\tstart_pin\tend_pin"
proc safe_value {value} {
    return [string map [list "\t" "\\t" "\n" "\\n" "\r" "\\r"] $value]
}
proc properties {stage kind names} {
    global cf
    foreach name $names {
        if {$kind == "cell"} {
            set object [get_cells $name]
        } elseif {$kind == "pin"} {
            set object [get_pins $name]
        } else {
            error "Unsupported property object kind"
        }
        foreach property [lsort [list_property $object]] {
            puts $cf "$stage\t$name\t$property\t[safe_value [get_property $property $object]]"
        }
    }
}
proc snapshot {stage cells} {
    global af
    foreach cell $cells {
        set object [get_cells $cell]
        properties $stage cell $cell
        properties $stage pin [get_pins -of_objects $object]
        foreach arc [get_timing_arcs -of_objects $object] {
            foreach property [lsort [list_property $arc]] {
                puts $af "$stage\t$cell\t$arc\t$property\t[safe_value [get_property $property $arc]]"
            }
        }
    }
    puts "FF_SNAPSHOT|$stage|[llength $cells]"
}
proc sample_path {stage name mode from to required} {
    global pf
    set paths [get_timing_paths -from $from -to $to -delay_type $mode -max_paths 1 -nworst 1]
    set count [llength $paths]
    if {$count > 1 || ($required && $count != 1)} {error "Missing or ambiguous expected path: $stage $name $mode"}
    if {$count == 0} {
        puts $pf "$stage\t$name\t$mode\t0\t\t\t\t\t"
        return
    }
    set p $paths
    puts $pf "$stage\t$name\t$mode\t$count\t[get_property REQUIREMENT $p]\t[get_property DATAPATH_DELAY $p]\t[get_property SLACK $p]\t[get_property STARTPOINT_PIN $p]\t[get_property ENDPOINT_PIN $p]"
    report_timing -of_objects $p -file $stage-$name-$mode.rpt
    report_property -all $p -file $stage-$name-$mode.properties.rpt
}
'''


def query(mailbox: Path, ff: Path, out: Path):
    mg = json.loads((mailbox / 'manifest.json').read_text())
    fg = json.loads((ff / 'manifest.json').read_text())
    if (mg['status'] != 'ALL_1103_VENDOR_MAILBOX_DATAPATH_ONLY_REQUIREMENTS_PASS_NATIVE_IMPORT_PENDING'
            or mg['native_exit'] != 0
            or fg['status'] != 'ALL_FULL_DESIGN_FF_MODE_VENDOR_INTRINSICS_PASS_NATIVE_IMPORT_PENDING'
            or fg['native_exit'] != 0):
        raise ValueError('Complete vendor checkpoints must have passed first')
    ff_dcp = Path(fg['outputs']['ff-last-locations.dcp']['path'])
    if describe(ff_dcp) != fg['outputs']['ff-last-locations.dcp']:
        raise ValueError('FF checkpoint changed')
    mailbox_dcp = mailbox / 'mailbox_paths.dcp'
    configs = json.loads((ff / 'configurations.json').read_text())['cells']
    if len(configs) != 10:
        raise ValueError('Five modes and both INIT values are required')
    out.mkdir(parents=True, exist_ok=False)
    tcl = ['set_param general.maxThreads 8', PROCEDURES,
           f'open_checkpoint {{{mailbox_dcp}}}',
           'set selected [get_cells {source_request_0 capture_request_0 source_response_0 capture_response_0}]',
           'if {[llength $selected] != 4} {error "Missing actual mailbox FF sample"}',
           'snapshot mailbox-loaded $selected', 'update_timing -full', 'snapshot mailbox-updated $selected']
    for role in ('request', 'response'):
        tcl.append(f'sample_path mailbox {role} max [get_cells source_{role}_0] [get_cells capture_{role}_0] 1')
    tcl += ['snapshot mailbox-after-paths $selected', 'close_design', f'open_checkpoint {{{ff_dcp}}}',
            'set selected [get_cells ff_*]', 'if {[llength $selected] != 10} {error "Missing actual FF modes"}',
            'snapshot ff-loaded $selected', 'update_timing -full', 'snapshot ff-updated $selected',
            'set_input_delay -clock [get_clocks core] 0 [get_ports {din[*] en[*] sr[*]}]',
            'set_output_delay -clock [get_clocks core] 0 [get_ports {q[*]}]',
            'update_timing -full', 'snapshot ff-io-constrained $selected']

    def samples(stage, include_control=True):
        result = []
        for index, c in enumerate(configs):
            cell = c['cell']; control = SR_PORT[c['primitive']]
            pins = [('D', 'din'), ('CE', 'en')]
            if include_control:
                pins.append((control, 'sr'))
            for pin, port in pins:
                for mode in ('max', 'min'):
                    result.append(f'sample_path {stage} {cell}-{pin} {mode} [get_ports {{{port}[{index}]}}] [get_pins {{{cell}/{pin}}}] 1')
            for mode in ('max', 'min'):
                result.append(f'sample_path {stage} {cell}-Q {mode} [get_cells {cell}] [get_ports {{q[{index}]}}] 1')
        return result

    tcl += samples('ff-placed')
    tcl += ['snapshot ff-after-paths $selected', 'unplace_cell $selected', 'update_timing -full',
            'snapshot ff-unplaced $selected']
    tcl += samples('ff-unplaced')
    tcl += ['snapshot ff-unplaced-after-paths $selected']
    # Constant control values are stated analysis assumptions for these probes;
    # they do not modify the production RTL or replace a hardware connection.
    for c in configs:
        tcl += [f'set_case_analysis 0 [get_pins {c["cell"]}/{SR_PORT[c["primitive"]]}]']
    tcl += ['update_timing -full', 'snapshot ff-neutral-control $selected']
    tcl += samples('ff-neutral-control', include_control=False)
    tcl += ['snapshot ff-neutral-after-paths $selected',
            'close $af', 'close $cf', 'close $pf', 'puts "FF_CONTEXT_PATH_QUERY_COMPLETE"', 'exit 0']
    (out / 'query.tcl').write_text('\n'.join(tcl) + '\n')
    shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md', out / 'plan.md')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace', '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': 'xc7k480tffg1156-2',
            'helper': describe(__file__), 'mailbox_gate': describe(mailbox / 'manifest.json'), 'ff_gate': describe(ff / 'manifest.json'),
            'checkpoints': {'mailbox': describe(mailbox_dcp), 'ff': describe(ff_dcp)}, 'configs': configs,
            'threads': 8, 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'FF_TIMING_CONTEXT_AND_PATH_COMPARISON_NOT_PARENT_ROUTE_OR_HARDWARE_PROOF'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    try:
        save(stage='native-vendor-context-query')
        print('VIVADO_FF_PATH_CONTEXT_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid); code = child.wait()
        (out / 'native.exit').write_text(str(code) + '\n'); save(native_exit=code)
        if code:
            raise RuntimeError('Vendor FF context/path query failed')
        with (out / 'paths.tsv').open() as stream:
            paths = list(csv.DictReader(stream, delimiter='\t'))
        counts = dict(Counter(row['stage'] for row in paths))
        if counts != {'mailbox': 2, 'ff-placed': 80, 'ff-unplaced': 80, 'ff-neutral-control': 60}:
            raise ValueError('Complete timing-context path coverage differs')
        save(status='ALL_222_VENDOR_FF_CONTEXT_PATH_QUERIES_COMPLETE_COMPARISON_PENDING', path_counts=counts,
             outputs={n: describe(out / n) for n in ('arcs.tsv', 'objects.tsv', 'paths.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'path_counts': counts}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('mailbox', 'ff', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--drivers-only', action='store_true')
    args = p.parse_args()
    if args.drivers_only:
        driver_query(args.ff.resolve(), args.out.resolve())
    else:
        query(args.mailbox.resolve(), args.ff.resolve(), args.out.resolve())


def driver_query(ff: Path, out: Path):
    gate = json.loads((ff / 'manifest.json').read_text())
    if gate['status'] != 'ALL_FULL_DESIGN_FF_MODE_VENDOR_INTRINSICS_PASS_NATIVE_IMPORT_PENDING' or gate['native_exit'] != 0:
        raise ValueError('Complete FF characterization required')
    dcp = Path(gate['outputs']['ff-last-locations.dcp']['path'])
    if describe(dcp) != gate['outputs']['ff-last-locations.dcp']:
        raise ValueError('FF checkpoint changed')
    configs = json.loads((ff / 'configurations.json').read_text())['cells']
    out.mkdir(parents=True, exist_ok=False)
    tcl = ['set_param general.maxThreads 8', PROCEDURES]
    stages = []
    for topology in ('direct', 'lut-ff', 'lut-port'):
        tcl += [f'open_checkpoint {{{dcp}}}', 'set selected [get_cells ff_*]', 'unplace_cell $selected',
                'set_input_delay -clock [get_clocks core] 0 [get_ports {din[*] en[*] sr[*]}]',
                'set_output_delay -clock [get_clocks core] 0 [get_ports {q[*]}]']
        for c in configs:
            tcl += [f'set_case_analysis 0 [get_pins {c["cell"]}/{SR_PORT[c["primitive"]]}]']
        pairs = []
        for pair in range(5):
            index = 2 * pair
            source, capture = configs[index]['cell'], configs[index + 1]['cell']
            tcl += [f'disconnect_net -pinlist [get_pins {capture}/D]']
            if topology == 'direct':
                tcl += [f'connect_net -net [get_nets -of_objects [get_pins {source}/Q]] -objects [get_pins {capture}/D]']
                start = f'[get_cells {source}]'
            else:
                lut, net = f'driver_lut_{pair}', f'driver_lut_output_{pair}'
                tcl += [f'create_cell -reference LUT1 {lut}', f"set_property INIT 2'h2 [get_cells {lut}]",
                        f'create_net {net}', f'connect_net -net [get_nets {net}] -objects [get_pins {{{lut}/O {capture}/D}}]']
                if topology == 'lut-ff':
                    driver = f'[get_nets -of_objects [get_pins {source}/Q]]'
                    start = f'[get_cells {source}]'
                else:
                    driver = f'[get_nets -of_objects [get_ports {{din[{index}]}}]]'
                    start = f'[get_ports {{din[{index}]}}]'
                tcl += [f'connect_net -net {driver} -objects [get_pins {lut}/I0]']
            pairs.append((source, capture, start))
        stage = topology + '-normal'
        stages.append(stage)
        tcl += ['update_timing -full', f'snapshot {stage} $selected']
        for source, capture, start in pairs:
            for mode in ('max', 'min'):
                tcl += [f'sample_path {stage} {capture} {mode} {start} [get_pins {capture}/D] 1']
        if topology != 'lut-port':
            for source, capture, start in pairs:
                tcl += [f'set_max_delay -datapath_only 20 -from [get_cells {source}] -to [get_cells {capture}]']
            stage = topology + '-datapath'
            stages.append(stage)
            tcl += ['update_timing -full', f'snapshot {stage} $selected']
            for source, capture, start in pairs:
                for mode in ('max', 'min'):
                    tcl += [f'sample_path {stage} {capture} {mode} {start} [get_pins {capture}/D] ' + ('1' if mode == 'max' else '0')]
        tcl += ['close_design']
    tcl += ['close $af', 'close $cf', 'close $pf', 'puts "FF_CONTROLLED_DRIVER_AND_EXCEPTION_QUERY_COMPLETE"', 'exit 0']
    (out / 'query.tcl').write_text('\n'.join(tcl) + '\n')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace', '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': 'xc7k480tffg1156-2',
            'helper': describe(__file__), 'ff_gate': describe(ff / 'manifest.json'), 'checkpoint': describe(dcp),
            'configs': configs, 'stages': stages, 'threads': 8, 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'CONTROLLED_FF_DRIVERS_AND_DATAPATH_EXCEPTION_NOT_PARENT_DESIGN_OR_HARDWARE_PROOF'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    try:
        save(stage='controlled-native-query')
        print('CONTROLLED_FF_DRIVER_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid); code = child.wait()
        (out / 'native.exit').write_text(str(code) + '\n'); save(native_exit=code)
        if code:
            raise RuntimeError('Controlled FF driver/exception query failed')
        with (out / 'paths.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        counts = dict(Counter(r['stage'] for r in rows))
        if counts != {stage: 10 for stage in stages}:
            raise ValueError('Five-mode driver/exception path coverage differs')
        save(status='ALL_50_CONTROLLED_FF_DRIVER_EXCEPTION_PATH_QUERIES_COMPLETE_COMPARISON_PENDING', path_counts=counts,
             outputs={name: describe(out / name) for name in ('arcs.tsv', 'objects.tsv', 'paths.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'path_counts': counts}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


if __name__ == '__main__':
    main()
