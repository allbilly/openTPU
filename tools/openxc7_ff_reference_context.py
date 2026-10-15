#!/usr/bin/env python3
"""Inventory and query actual routed FF contexts in the full Vivado reference."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_ff_path_vivado import PROCEDURES


QUERY = r'''
set inventory [open inventory.tsv w]
puts $inventory "cell\tprimitive\tis_c_inverted_property\tloc\tbel\tdriver_cell\tdriver_type\tdriver_port\tdriver_loc\tdriver_bel\tsame_site\tgroup"
set samples [open samples.tsv w]
puts $samples "sample\tcell\tgroup\tcapture_bel_pins\tcapture_site_pins\tdriver_bel_pins\tdriver_site_pins\tnet_site_pins"
set cells [get_cells -hierarchical -filter {REF_NAME =~ FD*}]
set total [llength $cells]
if {$total == 0} {error "No reference FF cells"}
puts "REFERENCE_FF_COUNT|$total"
array set group_names {}
array set group_samples {}
set group_count 0
set selected {}
set done 0
foreach name $cells {
    set cell [get_cells $name]
    set primitive [get_property REF_NAME $cell]
    set inv [get_property IS_C_INVERTED $cell]
    if {$primitive ni {FDRE FDSE FDCE FDPE FDRE_1 FDSE_1 FDCE_1 FDPE_1}} {error "Unsupported actual FF primitive: $primitive"}
    if {$inv == ""} {set inv DEFAULT}
    set loc [get_property LOC $cell]
    set bel [get_property BEL $cell]
    if {$loc == "" || $bel == ""} {error "Reference FF is not placed: $name"}
    set pin [get_pins $name/D]
    if {[llength $pin] != 1} {error "Missing reference FF data pin"}
    set nets [get_nets -segments -of_objects $pin]
    set drivers [get_pins -leaf -of_objects $nets -filter {DIRECTION == OUT}]
    set dn ""
    set dt ""
    set dp ""
    set dl ""
    set db ""
    if {[llength $drivers] == 1} {
        set driver [get_cells -of_objects $drivers]
        if {[llength $driver] != 1} {error "Ambiguous driver cell"}
        set dn [get_property NAME $driver]
        set dt [get_property REF_NAME $driver]
        set dp [get_property REF_PIN_NAME $drivers]
        set dl [get_property LOC $driver]
        set db [get_property BEL $driver]
    } elseif {[llength $drivers] == 0} {
        set ports [get_ports -quiet -of_objects $nets -filter {DIRECTION == IN}]
        if {[llength $ports] != 1} {error "Missing/ambiguous reference driver: $name"}
        set dn [get_property NAME $ports]
        set dt PRIMARY_INPUT
        set dp $dn
    } else {
        error "Multiple reference FF drivers: $name"
    }
    set same [expr {$dl != "" && $dl == $loc}]
    set key [list $primitive $inv $bel $dt $dp $same]
    if {![info exists group_names($key)]} {
        set group_names($key) [format "group_%05d" $group_count]
        incr group_count
        set group_samples($key) 0
    }
    set group $group_names($key)
    puts $inventory "[safe_value $name]\t$primitive\t$inv\t$loc\t$bel\t[safe_value $dn]\t$dt\t[safe_value $dp]\t$dl\t$db\t$same\t$group"
    if {$group_samples($key) < $samples_per_group} {
        set sample [format "%s_%d" $group $group_samples($key)]
        incr group_samples($key)
        lappend selected [list $sample $name $group]
        set cp [get_pins $name/D]
        set bp [get_bel_pins -quiet -of_objects $cp]
        set sp [get_site_pins -quiet -of_objects $cp]
        set ns [get_site_pins -quiet -of_objects $nets]
        set driver_bp ""
        set driver_sp ""
        if {[llength $drivers] == 1} {
            set driver_bp [get_bel_pins -quiet -of_objects $drivers]
            set driver_sp [get_site_pins -quiet -of_objects $drivers]
        }
        puts $samples "$sample\t[safe_value $name]\t$group\t[safe_value $bp]\t[safe_value $sp]\t[safe_value $driver_bp]\t[safe_value $driver_sp]\t[safe_value $ns]"
    }
    incr done
    if {$done % 10000 == 0} {puts "REFERENCE_FF_INVENTORY|$done|$total|$group_count"; flush stdout}
}
close $inventory
close $samples
puts "REFERENCE_FF_INVENTORY_COMPLETE|$done|$group_count|[llength $selected]"
flush stdout
foreach item $selected {
    lassign $item sample name group
    snapshot reference [get_cells $name]
    foreach mode {max min} {
        set ps [get_timing_paths -to [get_pins $name/D] -delay_type $mode -max_paths 1 -nworst 1]
        set count [llength $ps]
        if {$count > 1} {error "Ambiguous reference timing path"}
        if {$count == 0} {
            puts $pf "reference\t$sample\t$mode\t0\t\t\t\t\t"
        } else {
            puts $pf "reference\t$sample\t$mode\t1\t[get_property REQUIREMENT $ps]\t[get_property DATAPATH_DELAY $ps]\t[get_property SLACK $ps]\t[get_property STARTPOINT_PIN $ps]\t[get_property ENDPOINT_PIN $ps]"
            report_timing -of_objects $ps -file reference-$sample-$mode.rpt
        }
    }
    puts "REFERENCE_FF_SAMPLE|$sample|$name"
    flush stdout
}
close $af
close $cf
close $pf
puts "REFERENCE_FF_CONTEXT_QUERY_COMPLETE"
exit 0
'''


def query(checkpoint: Path, out: Path, samples: int):
    if not checkpoint.is_file() or samples < 1 or samples > 3:
        raise ValueError('Existing checkpoint and one to three samples per group required')
    checkpoint_input = describe(checkpoint)
    out.mkdir(parents=True, exist_ok=False)
    tcl = ('set_param general.maxThreads 8\nset_param tcl.collectionResultDisplayLimit 0\n' + PROCEDURES
           + f'\nopen_checkpoint {{{checkpoint}}}\n'
           + 'if {[get_property PART [current_design]] != "xc7k480tffg1156-2"} {error "Wrong reference part"}\n'
           + f'set samples_per_group {samples}\n' + QUERY)
    (out / 'query.tcl').write_text(tcl)
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'checkpoint': checkpoint_input, 'helper': describe(__file__),
            'query_procedures': describe(Path(__file__).with_name('openxc7_ff_path_vivado.py')),
            'part': 'xc7k480tffg1156-2', 'samples_per_group': samples, 'threads': 8,
            'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'COMPLETE_ROUTED_VIVADO_REFERENCE_FF_CONTEXTS_NOT_IDENTICAL_TO_OPENXC7_NETLIST',
            'numerical_import': 'PENDING', 'reference_checkpoint_modified': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-full-reference-query')
        print('FULL_REFERENCE_FF_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid)
            code = child.wait()
        (out / 'native.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Native full-reference FF query failed')
        if describe(checkpoint) != checkpoint_input:
            raise ValueError('Reference checkpoint changed')
        with (out / 'inventory.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        with (out / 'samples.tsv').open() as stream:
            selected = list(csv.DictReader(stream, delimiter='\t'))
        groups = Counter(row['group'] for row in rows)
        names = {row['cell'] for row in rows}
        counts = Counter(row['group'] for row in selected)
        if not names or len(names) != len(rows) or counts != {key: min(samples, count) for key, count in groups.items()}:
            raise ValueError('Complete reference inventory/group coverage differs')
        with (out / 'paths.tsv').open() as stream:
            paths = list(csv.DictReader(stream, delimiter='\t'))
        expected = {(row['sample'], mode) for row in selected for mode in ('max', 'min')}
        if len(paths) != len(expected) or {(row['case'], row['mode']) for row in paths} != expected:
            raise ValueError('Reference group path-query coverage differs')
        save(status='ALL_ROUTED_REFERENCE_FF_GROUPS_QUERY_COMPLETE_COMPARISON_PENDING',
             ff_count=len(rows), groups=len(groups), samples=len(selected), path_queries=len(paths),
             missing_paths=sum(row['count'] == '0' for row in paths),
             primitive_counts=dict(Counter(row['primitive'] for row in rows)),
             driver_counts=dict(Counter(row['driver_type'] for row in rows)),
             outputs={name: describe(out / name) for name in ('inventory.tsv', 'samples.tsv', 'arcs.tsv', 'objects.tsv', 'paths.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({key: info[key] for key in ('status', 'ff_count', 'groups', 'samples', 'path_queries', 'missing_paths')}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--samples-per-group', type=int, default=3)
    args = parser.parse_args()
    query(args.checkpoint.resolve(), args.out.resolve(), args.samples_per_group)


if __name__ == '__main__':
    main()
