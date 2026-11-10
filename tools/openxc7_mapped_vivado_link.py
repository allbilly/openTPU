#!/usr/bin/env python3
"""Link the complete reviewed OpenXC7 EDIF in Vivado and capture inventory."""
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
from openxc7_mapped_edif import TOP, PROFILE


def link(review_path: Path, out: Path):
    review = json.loads(review_path.read_text())
    if review['status'] != 'FULL_MAPPED_GRAPH_REVIEW_PASS_ONLY_EXPLICIT_METADATA_LOSS_VIVADO_LINK_PENDING':
        raise ValueError('Completed full graph review required')
    if review['profile'] != PROFILE:
        raise ValueError('Full scope changed')
    for descriptor in [review['edif'], review['exported_json'], review['input'], review['xdc']]:
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Reviewed full input changed')
    out.mkdir(parents=True, exist_ok=False)
    # Vivado identifies an EDIF top through its basename before reading it.
    edif_alias = out / (TOP + '.edf')
    edif_alias.symlink_to(review['edif']['path'])
    # Link and inventory first. Do not optimize or implement an unreviewed import.
    tcl = r'''
set_param general.maxThreads 8
set_param tcl.collectionResultDisplayLimit 0
create_project -in_memory -part xc7k480tffg1156-2
read_edif {%s}
link_design -top %s -part xc7k480tffg1156-2
puts "FULL_MAPPED_EDIF_LINK_COMPLETE"
set cf [open cells.tsv w]
puts $cf "cell\tprimitive\tis_primitive\tis_blackbox"
set cells [get_cells -hierarchical]
foreach cell $cells {
    puts $cf [join [list [get_property NAME $cell] [get_property REF_NAME $cell] [get_property IS_PRIMITIVE $cell] [get_property IS_BLACKBOX $cell]] "\t"]
}
close $cf
set pf [open clock-properties.tsv w]
puts $pf "cell\tprimitive\tproperty\tvalue"
foreach cell [get_cells -hierarchical -filter {REF_NAME == MMCME2_ADV || REF_NAME == PLLE2_ADV || REF_NAME == BSCANE2 || REF_NAME == IBUF}] {
    foreach property [lsort [list_property $cell]] {
        if {[string match CLK* $property] || [string match DIVCLK* $property] || [string match IS_* $property] || $property in {JTAG_CHAIN COMPENSATION LOC CCIO_EN IOSTANDARD}} {
            puts $pf [join [list [get_property NAME $cell] [get_property REF_NAME $cell] $property [get_property $property $cell]] "\t"]
        }
    }
}
close $pf
read_xdc {%s}
report_clocks -file clocks.rpt
report_utilization -file utilization.rpt
report_drc -file link-drc.rpt
write_checkpoint -force linked.dcp
puts "FULL_MAPPED_EDIF_INVENTORY_AND_CONSTRAINTS_COMPLETE"
exit 0
''' % (str(edif_alias), TOP, review['xdc']['path'])
    (out / 'link.tcl').write_text(tcl)
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'link.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'review': describe(review_path), 'edif': review['edif'], 'input': review['input'],
            'xdc': review['xdc'], 'profile': PROFILE, 'part': 'xc7k480tffg1156-2', 'threads': 8,
            'helper': describe(__file__), 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'edif_top_name_alias': str(edif_alias),
            'scope': 'FULL_EXACT_MAPPED_EDIF_VIVADO_LINK_INVENTORY_NOT_PLACEMENT_ROUTING_OR_HARDWARE_PASS',
            'unknown_ram_inputs_left_unconnected': review['summary']['unknown_ram_input_bits'],
            'imported_graph_equivalence': False, 'timing_signoff': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-full-edif-link-and-inventory')
        print('FULL_MAPPED_VIVADO_LINK_STARTED ' + str(out), flush=True)
        with (out / 'link.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_launcher_pid=child.pid)
            code = child.wait()
        (out / 'link.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        log = (out / 'link.log').read_text(errors='replace')
        if code or 'FULL_MAPPED_EDIF_INVENTORY_AND_CONSTRAINTS_COMPLETE' not in log:
            raise RuntimeError('Full mapped Vivado link or constraint query failed')
        with (out / 'cells.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        from collections import Counter
        save(status='FULL_MAPPED_VIVADO_LINK_COMPLETE_IMPORT_GRAPH_REVIEW_PENDING',
             actual_inventory_cells=len(rows),
             actual_primitive_counts=dict(sorted(Counter(row['primitive'] for row in rows).items())),
             blackboxes=[row['cell'] for row in rows if row['is_blackbox'] == '1'],
             outputs={name: describe(out / name) for name in ['cells.tsv', 'clock-properties.tsv', 'clocks.rpt', 'utilization.rpt', 'link-drc.rpt', 'linked.dcp']},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    link(args.review.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
