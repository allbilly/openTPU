#!/usr/bin/env python3
"""Collect routed PCIe CDC evidence for review; never approve or program an image."""
import sys
sys.path.insert(0,'/home/fedora/openTPU/tools')
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import subprocess

from fedora_qualify_ch1_image import describe, require, unchanged, VIVADO
from fedora_review_ramtest_mig import cdc_rows


TCL = r'''
set dcp [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
set_param general.maxThreads 2
open_checkpoint $dcp
set f [open $out/facts.tsv w]
foreach name {u_ld/FDCE/D u_ld/FDCE_8/D u_sys/u_board/cal_s1_reg[0]/D u_sys/u_board/cal_s1_reg[1]/D u_sys/u_board/cal_s2_reg[0]/D u_sys/u_board/cal_s2_reg[1]/D} {
    set pin [get_pins -quiet [list $name]]
    if {[llength $pin] != 1} {error "Expected exactly one routed pin: $name"}
    foreach source [lsort [all_fanin -flat -startpoints_only -to $pin]] {
        puts $f "FANIN\t$name\t$source"
    }
    set cell [get_cells -of_objects $pin]
    puts $f "CELL\t$name\t[get_property REF_NAME $cell]\t[get_property ASYNC_REG $cell]"
    foreach clock [get_clocks -of_objects [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]] {
        puts $f "CLOCK\t$name\t$clock\t[get_property PERIOD $clock]"
    }
}
close $f
report_cdc -details -file $out/cdc.rpt
report_exceptions -file $out/exceptions.rpt
check_timing -override_defaults {no_input_delay no_output_delay} -verbose -file $out/pad-coverage.rpt
close_design
exit
'''


def inventory(rows):
    counts = Counter(row[:5] for row in rows)
    return [dict(kind=k[0], severity=k[1], description=k[2], depth=k[3],
                 exception=k[4], count=count) for k, count in sorted(counts.items())]


def read_report(path):
    return gzip.decompress(path.read_bytes()).decode() if path.suffix == '.gz' else path.read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--qualification', type=Path, required=True)
    parser.add_argument('--reference-cdc', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--vivado', type=Path, default=VIVADO)
    args = parser.parse_args()
    build, qualification, out = args.build.resolve(), args.qualification.resolve(), args.out.resolve()
    require(not out.exists(), 'Choose a new evidence directory')
    out.mkdir(parents=True)
    state = dict(status='CHECKING_INPUTS', hardware_accessed=False, flash_written=False,
                 scope='Additional CDC evidence only; manual review and physical qualification remain required')

    def save():
        state['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temporary = out/'manifest.json.tmp'
        temporary.write_text(json.dumps(state, indent=2)+'\n')
        temporary.replace(out/'manifest.json')

    try:
        save()
        q = json.loads(qualification.read_text())
        require(q['status'] in (
            'SPARE_PCIE_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING',
            'SPARE_PCIE_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING'),
            'Independent image qualification is incomplete')
        require(Path(q['build_manifest']['path']).resolve() == build/'manifest.json',
                'Qualification belongs to another build')
        unchanged(q['build_manifest'])
        m = json.loads((build/'manifest.json').read_text())
        require(m['status'] == 'FULL_NATIVE_VIVADO_PCIE_SPARE8_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING'
                and m['build_id'] == 'c0172080' and m['ecc_channels'] == [1]
                and m['physical_user_channels'] == [0, 1] and m['usable_logical_bytes'] == 1 << 32,
                'Require exact spare full-OpenTPU implementation')
        witnesses = m['sources'] + list(m['outputs'].values()) + [item for item in q['evidence'] if Path(item['path']).name.startswith('oob-')]
        for item in witnesses:
            unchanged(item)
        require(q['bitstream'] == m['outputs']['otpu.bit'] and
                q['oob_clock_review']['bus_skew_constraints'] == 39,
                'Bitstream binding or OOB/skew coverage differs')
        dcp = Path(m['outputs']['final-routed.dcp']['path']).resolve()
        require(dcp == build/'project/final-routed.dcp', 'Unexpected routed checkpoint')
        state.update(qualification=describe(qualification), bitstream=q['bitstream'],
                     routed_checkpoint=describe(dcp), collector=describe(Path(__file__)),
                     reference_cdc=describe(args.reference_cdc), status='COLLECTING_ROUTED_CDC_EVIDENCE')
        (out/'collector-at-launch.py').write_bytes(Path(__file__).read_bytes())
        (out/'audit.tcl').write_text(TCL)
        command = [str(args.vivado), '-mode', 'batch', '-nojournal', '-nolog',
                   '-source', str(out/'audit.tcl'), '-tclargs', str(dcp), str(out)]
        (out/'command.json').write_text(json.dumps(command, indent=2)+'\n')
        save()
        with (out/'audit.log').open('w') as log:
            state['vivado_exit'] = subprocess.run(command, cwd=out, stdout=log,
                                                  stderr=subprocess.STDOUT, timeout=1200).returncode
        require(state['vivado_exit'] == 0, 'Checkpoint evidence collection failed; inspect audit.log')
        for item in witnesses + [state['qualification'], state['reference_cdc']]:
            unchanged(item)
        oob = qualification.parent/'oob-cdc.rpt'
        require(any(Path(x['path']).resolve() == oob for x in [item for item in q['evidence'] if Path(item['path']).name.startswith('oob-')]),
                'OOB CDC report is not bound to the qualification')
        rows, reference = cdc_rows(oob.read_text()), cdc_rows(read_report(args.reference_cdc))
        added = Counter(rows) - Counter(reference)
        removed = Counter(reference) - Counter(rows)
        state.update(status='CDC_EVIDENCE_COLLECTED_REVIEW_PENDING',
                     original_clock_inventory=inventory(cdc_rows((out/'cdc.rpt').read_text())),
                     oob_inventory=inventory(rows), reference_inventory=inventory(reference),
                     added_paths=[dict(row=list(row), count=n) for row, n in sorted(added.items())],
                     removed_paths=[dict(row=list(row), count=n) for row, n in sorted(removed.items())],
                     facts=[line.split('\t') for line in (out/'facts.tsv').read_text().splitlines()],
                     evidence=[describe(p) for p in sorted(out.iterdir())
                               if p.is_file() and p.name not in ('manifest.json', 'manifest.json.tmp')],
                     limitations=['No CDC approval is implied by an unchanged report inventory.',
                                  'External DDR pad timing is not established by internal timing.',
                                  'No hardware was programmed or tested.'])
        return 0
    except Exception as error:
        state.update(status='FAIL', error=repr(error))
        return 1
    finally:
        save()
        print(json.dumps(dict(status=state['status'], out=str(out), error=state.get('error'))), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
