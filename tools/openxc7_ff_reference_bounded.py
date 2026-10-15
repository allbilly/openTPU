#!/usr/bin/env python3
"""Query every saved full-reference FF sample with bounded object metadata."""
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
import re
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_ff_path_vivado import PROCEDURES
from openxc7_mapped_edif import TOP, PROFILE


BOUNDED = r'''
proc properties {stage kind names} {
    global cf
    foreach name $names {
        if {$kind == "cell"} {
            set object [get_cells $name]
            set wanted {NAME CLASS REF_NAME LOC BEL INIT IS_C_INVERTED IS_D_INVERTED IS_CE_INVERTED IS_R_INVERTED IS_S_INVERTED IS_CLR_INVERTED IS_PRE_INVERTED}
        } elseif {$kind == "pin"} {
            set object [get_pins $name]
            set wanted {NAME CLASS REF_PIN_NAME DIRECTION IS_CLOCK IS_INVERTED IS_LEAF IS_ENABLED FANOUT LOAD CAPACITANCE SLEW}
        } else {error "Unsupported property object kind"}
        if {[llength $object] != 1} {error "Missing exact snapshot object"}
        set available [list_property $object]
        foreach property $wanted {
            if {$property in $available} {
                set value [get_property $property $object]
            } else {set value UNAVAILABLE}
            puts $cf "$stage\t$name\t$property\t[safe_value $value]"
        }
    }
}
foreach item $specifications {
    lassign $item sample name group
    set started [clock milliseconds]
    snapshot reference [get_cells $name]
    set snapshot_done [clock milliseconds]
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
    set finished [clock milliseconds]
    puts "REFERENCE_FF_SAMPLE|$sample|$name"
    puts "REFERENCE_FF_SAMPLE_MS|$sample|[expr {$snapshot_done-$started}]|[expr {$finished-$snapshot_done}]"
    flush $af
    flush $cf
    flush $pf
    flush stdout
}
close $af
close $cf
close $pf
puts "REFERENCE_FF_CONTEXT_QUERY_COMPLETE"
exit 0
'''


def rows(path):
    # Full-design fanout/site-pin lists legitimately exceed CSV's 128 KiB default.
    csv.field_size_limit(64 * 1024 * 1024)
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def query(source: Path, reference: Path, out: Path):
    original = json.loads((source / 'manifest.json').read_text())
    ref = json.loads(reference.read_text())
    if (ref['status'] != 'FULL_MAPPED_REFERENCE_BITSTREAM_TIMING_DRC_PINS_PACKET_PASS_HARDWARE_PENDING'
            or ref['native_exit'] != 0 or ref['profile'] != PROFILE
            or original['checkpoint'] != ref['outputs']['final-routed.dcp']):
        raise ValueError('Completed full mapped-reference provenance required')
    checkpoint = original['checkpoint']
    if describe(checkpoint['path']) != checkpoint:
        raise ValueError('Full routed reference changed')
    log = (source / 'query.log').read_text(errors='replace')
    complete = re.findall(r'REFERENCE_FF_INVENTORY_COMPLETE\|(\d+)\|(\d+)\|(\d+)', log)
    if complete != [('179299', '1988', '4810')]:
        raise ValueError('Complete observed full inventory required')
    inventory, selected = rows(source / 'inventory.tsv'), rows(source / 'samples.tsv')
    cells = {row['cell']: row for row in inventory}
    groups = Counter(row['group'] for row in inventory)
    counts = Counter(row['group'] for row in selected)
    if (len(inventory) != 179299 or len(cells) != 179299 or len(groups) != 1988
            or len(selected) != 4810 or len({r['sample'] for r in selected}) != 4810
            or counts != {k: min(3, n) for k, n in groups.items()}
            or any(row['cell'] not in cells or row['group'] != cells[row['cell']]['group'] for row in selected)):
        raise ValueError('Full inventory or sample coverage differs')
    saved = {name: describe(source / name) for name in ['inventory.tsv', 'samples.tsv']}
    out.mkdir(parents=True, exist_ok=False)
    for name in saved:
        shutil.copy2(source / name, out / name)
    specifications = []
    for row in selected:
        values = [row['sample'], row['cell'], row['group']]
        if any(any(c in value for c in '{}\r\n') for value in values):
            raise ValueError('Unsupported exact sample name')
        specifications.append('[list ' + ' '.join('{' + value + '}' for value in values) + ']')
    tcl = ('set_param general.maxThreads 8\nset_param tcl.collectionResultDisplayLimit 0\n' + PROCEDURES
           + '\nopen_checkpoint {' + checkpoint['path'] + '}\n'
           + 'if {[get_property PART [current_design]] ne "xc7k480tffg1156-2"} {error "Wrong reference part"}\n'
           + 'if {[get_property TOP [current_design]] ne {' + TOP + '}} {error "Wrong reference top"}\n'
           + 'if {[llength [get_cells -hierarchical -filter {REF_NAME =~ FD*}]] != 179299} {error "Full FF count changed"}\n'
           + 'puts "REFERENCE_FF_COUNT|179299"\n'
           + 'puts "REFERENCE_FF_INVENTORY_COMPLETE|179299|1988|4810"\n'
           + 'set specifications [list ' + ' '.join(specifications) + ']\n' + BOUNDED)
    (out / 'query.tcl').write_text(tcl)
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog',
            '-notrace', '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'checkpoint': checkpoint, 'reference_image': describe(reference),
            'source_query': describe(source / 'manifest.json'), 'saved_complete_inventory': saved,
            'helper': describe(__file__), 'query_procedures': describe(Path(__file__).with_name('openxc7_ff_path_vivado.py')),
            'part': 'xc7k480tffg1156-2', 'profile': PROFILE, 'samples_per_group': 3, 'threads': 8,
            'ff_count': 179299, 'groups': 1988, 'samples': 4810, 'path_queries_expected': 9620,
            'object_metadata': 'BOUNDED_CELL_PIN_MODE_AND_ELECTRICAL_PROPERTIES',
            'raw_timing_arc_properties': 'ALL_PRESERVED', 'numerical_import': 'PENDING',
            'hardware_accessed': False, 'live_full_jobs_changed': False, 'reference_checkpoint_modified': False,
            'scope': 'COMPLETE_SAME_INPUT_ROUTED_REFERENCE_FF_CONTEXT_SAMPLES_NOT_UNIVERSAL_OPENXC7_MODEL'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        print('BOUNDED_FULL_REFERENCE_FF_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as stream:
            child = subprocess.Popen(argv, cwd=out, stdout=stream, stderr=subprocess.STDOUT)
            save(native_pid=child.pid)
            code = child.wait()
        (out / 'native.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        text = (out / 'query.log').read_text(errors='replace')
        if code or 'REFERENCE_FF_CONTEXT_QUERY_COMPLETE' not in text:
            raise RuntimeError('Full bounded reference query incomplete')
        paths = rows(out / 'paths.tsv')
        expected = {(r['sample'], mode) for r in selected for mode in ['max', 'min']}
        if (len(paths) != 9620 or {(r['case'], r['mode']) for r in paths} != expected
                or len(re.findall(r'^REFERENCE_FF_SAMPLE\|', text, re.M)) != 4810):
            raise ValueError('Complete unchanged timing-sample coverage differs')
        if describe(checkpoint['path']) != checkpoint or any(describe(source / name) != d for name, d in saved.items()):
            raise ValueError('Immutable complete reference inputs changed')
        save(status='ALL_ROUTED_REFERENCE_FF_GROUPS_QUERY_COMPLETE_COMPARISON_PENDING',
             path_queries=len(paths), missing_paths=sum(r['count'] == '0' for r in paths),
             primitive_counts=dict(Counter(r['primitive'] for r in inventory)),
             driver_counts=dict(Counter(r['driver_type'] for r in inventory)),
             outputs={name: describe(out / name) for name in ['inventory.tsv', 'samples.tsv', 'arcs.tsv', 'objects.tsv', 'paths.tsv']},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--from-query', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    query(args.from_query.resolve(), args.reference.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
