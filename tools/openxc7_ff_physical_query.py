#!/usr/bin/env python3
"""Inspect routed FF physical context and the remaining carry-driven variation."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_ff_path_vivado import PROCEDURES


EXTRA = r'''
proc dump_object {stage object} {
    global cf
    # Avoid expanding all hierarchical clock-net pins and routing properties.
    foreach property {NAME CLASS REF_NAME LOC BEL INIT IS_C_INVERTED IS_D_INVERTED IS_CE_INVERTED IS_R_INVERTED IS_S_INVERTED IS_CLR_INVERTED IS_PRE_INVERTED TYPE IS_CLOCK IS_INVERTED IS_GROUND IS_POWER FANOUT ROUTE_STATUS DRIVER_PIN LOAD CAPACITANCE SLEW FROM_PIN TO_PIN IS_USED PERIOD WAVEFORM STARTPOINT_PIN ENDPOINT_PIN REQUIREMENT DATAPATH_DELAY SLACK LOGIC_LEVELS DELAY_FAST_MAX DELAY_FAST_MIN DELAY_SLOW_MAX DELAY_SLOW_MIN} {
        if {[catch {get_property -quiet $property $object} value]} {set value UNAVAILABLE}
        if {[string length $value] > 512} {set value "OMITTED_LARGE_VALUE_LENGTH_[string length $value]"}
        puts $cf "$stage\t[safe_value $object]\t$property\t[safe_value $value]"
    }
}
set sf [open physical.tsv w]
puts $sf "sample\tcell\tdriver\tdata_site_pins\tdriver_site_pins\tdata_net_leaf_inputs\tdata_net_site_pins\tclock_drivers\tclock_site_pins"
foreach spec $specifications {
    lassign $spec sample name driver driver_port
    set capture [get_cells $name]
    set source [get_cells $driver]
    if {[llength $capture] != 1 || [llength $source] != 1} {error "Missing exact physical sample cells"}
    snapshot $sample [list $name $driver]
    set d [get_pins [list "${name}/D"]]
    set c [get_pins [list "${name}/C"]]
    set output [get_pins [list "${driver}/${driver_port}"]]
    if {[llength $d] != 1 || [llength $c] != 1 || [llength $output] != 1} {error "Missing sample pins"}
    set dn [get_nets -segments -of_objects $d]
    set cn [get_nets -segments -of_objects $c]
    set leaves [get_pins -leaf -of_objects $dn -filter {DIRECTION == IN}]
    set clock_drivers [get_pins -leaf -of_objects $cn -filter {DIRECTION == OUT}]
    foreach net $dn {dump_object $sample $net}
    foreach net [get_nets -of_objects $c] {dump_object $sample $net}
    foreach clock [get_clocks -quiet -of_objects $c] {dump_object $sample $clock}
    foreach cell [list $capture $source] {
        set site [get_sites [get_property LOC $cell]]
        dump_object $sample $site
        foreach pip [get_site_pips -of_objects $site] {dump_object $sample $pip}
    }
    puts $sf "$sample\t[safe_value $name]\t[safe_value $driver]\t[safe_value [get_site_pins -of_objects $d]]\t[safe_value [get_site_pins -of_objects $output]]\t[llength $leaves]\t[llength [get_site_pins -of_objects $dn]]\t[safe_value $clock_drivers]\t[safe_value [get_site_pins -of_objects $c]]"
    foreach net $dn {
        foreach delay [get_net_delays -of_objects $net] {dump_object $sample $delay}
    }
    foreach mode {max min} {
        set path [get_timing_paths -to $d -delay_type $mode -max_paths 1 -nworst 1]
        if {[llength $path] != 1} {error "Missing selected routed physical timing path"}
        dump_object $sample $path
        report_timing -of_objects $path -input_pins -file $sample-$mode.rpt
        puts $pf "$sample\t$sample\t$mode\t1\t[get_property REQUIREMENT $path]\t[get_property DATAPATH_DELAY $path]\t[get_property SLACK $path]\t[get_property STARTPOINT_PIN $path]\t[get_property ENDPOINT_PIN $path]"
    }
    puts "PHYSICAL_FF_SAMPLE_COMPLETE|$sample"
    flush $cf
    flush $af
    flush $sf
    flush $pf
    flush stdout
}
close $sf
close $af
close $cf
close $pf
puts "ALL_PHYSICAL_FF_CONTEXT_SAMPLES_QUERY_COMPLETE"
exit 0
'''


def query(regroup: Path, out: Path):
    group = json.loads(regroup.read_text())
    if group['status'] != 'ALL_4002_REFERENCE_SAMPLES_PHYSICAL_CONTEXT_REGROUP_COMPLETE_MODEL_UNQUALIFIED':
        raise ValueError('Completed physical grouping required')
    if describe(group['query']['path']) != group['query']:
        raise ValueError('Actual routed reference query changed')
    original = json.loads(Path(group['query']['path']).read_text())
    checkpoint = original['checkpoint']
    if describe(checkpoint['path']) != checkpoint:
        raise ValueError('Working full routed reference changed')
    root = Path(group['query']['path']).parent
    with (root / 'samples.tsv').open() as stream:
        samples = {r['sample']: r for r in csv.DictReader(stream, delimiter='\t')}
    with (root / 'inventory.tsv').open() as stream:
        inventory = {r['cell']: r for r in csv.DictReader(stream, delimiter='\t')}
    ids = ['group_01837_0', 'group_01837_1', 'group_01837_2',
           'group_00000_0', 'group_00000_1', 'group_00003_0', 'group_00003_2', 'group_00004_1', 'group_00004_2']
    specifications = []
    for sid in ids:
        sample = samples[sid]
        record = inventory[sample['cell']]
        specifications.append([sid, sample['cell'], record['driver_cell'], record['driver_port']])
    out.mkdir(parents=True, exist_ok=False)
    quoted = ' '.join('[list ' + ' '.join('{' + value + '}' for value in row) + ']' for row in specifications)
    tcl = ('set_param general.maxThreads 8\n' + PROCEDURES + '\nopen_checkpoint {' + checkpoint['path'] + '}\n'
           + 'set specifications [list ' + quoted + ']\n' + EXTRA)
    (out / 'query.tcl').write_text(tcl)
    (out / 'specifications.json').write_text(json.dumps(specifications, indent=2) + '\n')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'regroup': describe(regroup), 'checkpoint': checkpoint, 'samples': len(ids), 'threads': 8,
            'helper': describe(__file__), 'hardware_accessed': False, 'live_backend_changed': False,
            'scope': 'ACTUAL_REFERENCE_FF_SITE_MUX_DRIVER_CLOCK_FANOUT_AND_PATH_CONTEXT_NOT_MODEL_IMPORT'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='read-only-routed-reference-query')
        print('PHYSICAL_FF_CONTEXT_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid)
            code = child.wait()
        (out / 'query.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        text = (out / 'query.log').read_text()
        if (code or text.count('PHYSICAL_FF_SAMPLE_COMPLETE|') != len(ids)
                or 'ALL_PHYSICAL_FF_CONTEXT_SAMPLES_QUERY_COMPLETE' not in text):
            raise RuntimeError('Actual physical FF sample query incomplete')
        if describe(checkpoint['path']) != checkpoint:
            raise ValueError('Working routed reference changed during the query')
        save(status='ALL_NINE_ACTUAL_ROUTED_FF_PHYSICAL_CONTEXT_QUERIES_COMPLETE_COMPARISON_PENDING',
             outputs={n: describe(out / n) for n in ('arcs.tsv', 'objects.tsv', 'paths.tsv', 'physical.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--regroup', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    query(args.regroup.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
