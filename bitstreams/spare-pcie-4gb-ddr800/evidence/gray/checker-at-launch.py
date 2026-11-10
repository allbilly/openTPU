#!/usr/bin/env python3
"""Check LiteDRAM CSR FIFO pointer skew on an already routed PCIe image.

Adds ten analysis-only bus-skew assertions in a disposable Vivado session.
No placement, routing, checkpoint/bitstream writes or hardware access occur.
The original build false paths and reports are retained unchanged.
"""
from __future__ import annotations

import sys
sys.path.insert(0,'/home/fedora/openTPU/tools')
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import subprocess

from fedora_qualify_ch1_image import VIVADO, describe, require, unchanged
from fedora_review_ramtest_mig import cdc_rows

GROUPS = [('aw', 0, 0), ('aw', 1, 1), ('w', 0, 2), ('w', 1, 3),
          ('b', 0, 4), ('b', 1, 5), ('ar', 0, 6), ('ar', 1, 7),
          ('r', 0, 8), ('r', 1, 9)]

TCL = r'''
set dcp [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
set_param general.maxThreads 2
open_checkpoint $dcp
set f [open $out/facts.tsv w]
foreach group {{aw 0 0} {aw 1 1} {w 0 2} {w 1 3} {b 0 4} {b 1 5} {ar 0 6} {ar 1 7} {r 0 8} {r 1 9}} {
    lassign $group channel counter index
    set source_base [format {u_ld/%s_cdc_cdc_graycounter%d_q_reg} $channel $counter]
    set dest_base [format {u_ld/xilinxmultiregimpl%d_regs0_reg} $index]
    set next_base [format {u_ld/xilinxmultiregimpl%d_regs1_reg} $index]
    set sources {}; set destinations {}; set source_periods {}; set dest_periods {}
    for {set bit 0} {$bit < 3} {incr bit} {
        set sname [format {%s[%d]} $source_base $bit]
        set dname [format {%s[%d]} $dest_base $bit]
        set nname [format {%s[%d]} $next_base $bit]
        set src [get_cells -quiet [list $sname]]
        set dst [get_cells -quiet [list $dname]]
        set nxt [get_cells -quiet [list $nname]]
        if {[llength $src] != 1 || [llength $dst] != 1 || [llength $nxt] != 1} {
            error "Missing exact pointer/synchronizer cells: $sname $dname $nname"
        }
        foreach cell [concat $dst $nxt] {
            if {![get_property ASYNC_REG $cell]} {error "Synchronizer lacks ASYNC_REG: $cell"}
        }
        foreach pair [list [list $src $dst] [list $dst $nxt]] {
            lassign $pair launch capture
            set pin [get_pins -of_objects $capture -filter {REF_PIN_NAME == D}]
            set actual [lsort [all_fanin -flat -startpoints_only -to $pin]]
            set expected [get_pins -of_objects $launch -filter {REF_PIN_NAME == C}]
            if {[llength $actual] != 1 || [llength $expected] != 1 ||
                [lindex $actual 0] ne [lindex $expected 0]} {
                error "Unexpected synchronizer fanin: $capture $actual, expected $expected"
            }
            puts $f "FANIN\t$capture\t$actual"
        }
        set sc [get_clocks -of_objects [get_pins -of_objects $src -filter {REF_PIN_NAME == C}]]
        set dc [get_clocks -of_objects [get_pins -of_objects $dst -filter {REF_PIN_NAME == C}]]
        if {[llength $sc] != 1 || [llength $dc] != 1} {error "Ambiguous pointer clock"}
        lappend source_periods [get_property PERIOD $sc]
        lappend dest_periods [get_property PERIOD $dc]
        lappend sources $src
        lappend destinations $dst
        puts $f "BIT\t$channel\t$counter\t$bit\t$src\t$dst\t$sc\t$dc"
    }
    if {[llength [lsort -unique $source_periods]] != 1 || [llength [lsort -unique $dest_periods]] != 1} {
        error "Mixed pointer clock periods"
    }
    set budget [expr {min([lindex $source_periods 0], [lindex $dest_periods 0])}]
    if {$budget <= 0} {error "Invalid pointer period"}
    set_bus_skew -from $sources -to $destinations $budget
    puts $f "GROUP\t$channel\t$counter\t$index\t$budget\t[lindex $source_periods 0]\t[lindex $dest_periods 0]"
}
close $f
report_bus_skew -warn_on_violation -file $out/bus-skew.rpt
report_route_status -file $out/route.rpt
close_design
exit
'''


def expected_rows():
    return {(f'u_ld/{channel}_cdc_cdc_graycounter{counter}_q_reg[2:0]/C',
             f'u_ld/xilinxmultiregimpl{index}_regs0_reg[2:0]/D')
            for channel, counter, index in GROUPS}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--vivado', type=Path, default=VIVADO)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = dict(status='CHECKING_QUALIFICATION', hardware_accessed=False,
                 netlist_placement_routing_modified=False, original_constraints_modified=False,
                 analysis_only_added_skew_assertions=10,
                 scope='Exact routed CSR FIFO pointer skew and synchronizer structure; not a complete CDC or physical qualification',
                 references=['https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/set_bus_skew-Example-Two'])

    def save():
        state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temp = out/'manifest.json.tmp'
        temp.write_text(json.dumps(state, indent=2)+'\n')
        temp.replace(out/'manifest.json')

    try:
        save()
        qpath = args.qualification.resolve()
        q = json.loads(qpath.read_text())
        require(q['status'] in ('SPARE_PCIE_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING',
                               'SPARE_PCIE_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING'),
                'Independent image review must complete first')
        unchanged(q['build_manifest'])
        m = json.loads(Path(q['build_manifest']['path']).read_text())
        require(m['status'] == 'FULL_NATIVE_VIVADO_PCIE_SPARE8_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING'
                and m['build_id'] == 'c0172080' and m['ecc_channels'] == [1]
                and m['physical_user_channels'] == [0, 1] and m['usable_logical_bytes'] == 1 << 32,
                'Require exact spare full-OpenTPU implementation')
        witnesses = [describe(qpath), q['build_manifest']] + m['sources'] + list(m['outputs'].values()) + [item for item in q['evidence'] if Path(item['path']).name.startswith('oob-')]
        for item in witnesses:
            unchanged(item)
        rows = cdc_rows((qpath.parent/'oob-cdc.rpt').read_text())
        gray = [row for row in rows if row[0] == 'CDC-6' and '_cdc_cdc_graycounter' in row[5]]
        require(len(gray) == 10 and {(row[5], row[6]) for row in gray} == expected_rows(),
                'CSR gray-pointer inventory differs')
        require(all(row[1:5] == ('Warning', 'Multi-bit synchronized with ASYNC_REG property', '2', 'False Path')
                    for row in gray), 'Unexpected pointer synchronizer structure')
        state.update(status='ROUTED_GRAY_SKEW_CHECK_RUNNING', qualification=describe(qpath),
                     bitstream=q['bitstream'], routed_checkpoint=m['outputs']['final-routed.dcp'],
                     source=describe(Path(__file__)), reviewed_gray_rows=gray)
        (out/'checker-at-launch.py').write_bytes(Path(__file__).read_bytes())
        (out/'audit.tcl').write_text(TCL)
        command = [str(args.vivado), '-mode', 'batch', '-nojournal', '-nolog', '-source', str(out/'audit.tcl'),
                   '-tclargs', m['outputs']['final-routed.dcp']['path'], str(out)]
        (out/'command.json').write_text(json.dumps(command, indent=2)+'\n')
        save()
        with (out/'audit.log').open('w') as log:
            state['vivado_exit'] = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        require(state['vivado_exit'] == 0, 'Routed pointer review failed; inspect audit.log')
        for item in witnesses:
            unchanged(item)
        facts = [line.split('\t') for line in (out/'facts.tsv').read_text().splitlines()]
        require(sum(r[0] == 'GROUP' for r in facts) == 10 and sum(r[0] == 'BIT' for r in facts) == 30
                and sum(r[0] == 'FANIN' for r in facts) == 60, 'Incomplete routed synchronizer evidence')
        skew = re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',
                          (out/'bus-skew.rpt').read_text(), re.M)
        require(len(skew) == q['oob_clock_review']['bus_skew_constraints']+10 and
                all(label == 'MET' and float(value) >= 0 for label, value in skew),
                'Incomplete or failing original/additional bus-skew assertions')
        state.update(status='PASS_ROUTED_CSR_GRAY_SKEW_AND_SYNCHRONIZERS_PHYSICAL_PENDING',
                     facts=facts, total_skew_constraints=len(skew),
                     minimum_skew_slack_ns=min(float(value) for _, value in skew),
                     evidence=[describe(p) for p in sorted(out.iterdir()) if p.is_file()
                               and p.name not in ('manifest.json', 'manifest.json.tmp')])
        return 0
    except Exception as error:
        state.update(status='FAIL', error=repr(error))
        return 1
    finally:
        save()
        print(json.dumps(dict(status=state['status'], error=state.get('error'), out=str(out))), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
