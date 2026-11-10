#!/usr/bin/env python3
"""Resume the CH1 USER2 implementation from a verified synthesis checkpoint."""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
from xml.etree import ElementTree
from zipfile import ZipFile

from fedora_build_vivado_ch1_jtag import describe


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--from-build', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    a = ap.parse_args()
    donor, out = a.from_build.resolve(), a.out.resolve()
    if out.exists():
        ap.error('Choose a fresh output directory')
    previous = json.loads((donor / 'manifest.json').read_text())
    assert previous['status'] == 'FAIL' and previous['build_exit'] == 1
    assert previous['top'] == 'otpu_fpga_top_openxc7_jtag'
    assert previous['physical_user_channels'] == [1]
    assert previous['logical_capacity_bytes'] == 1 << 31
    assert '100 MHz core clock missing' in (donor / 'build.log').read_text()
    for item in previous['source_files'] + [previous['reference_pins'], previous['helper']]:
        assert describe(item['path']) == item, 'Donor changed: ' + item['path']
    checkpoint = describe(donor / 'synth.dcp')
    with ZipFile(checkpoint['path']) as archive:
        metadata = ElementTree.fromstring(archive.read('dcp.xml'))
    assert metadata.find('Part').attrib['Name'] == previous['part']
    assert metadata.find('Top').attrib['Name'] == previous['top']
    out.mkdir(parents=True)
    src = out / 'source'
    shutil.copytree(donor / 'source', src)
    for name in ('synth.dcp', 'board.xdc', 'expected-pins.json', 'pre_bit_gate.py'):
        shutil.copy2(donor / name, out / name)
    old_clock = 'set core [get_clocks -of_objects [get_nets ld_sys_clk]]'
    late = (donor / 'late.tcl').read_text()
    assert late.count(old_clock) == 1
    late = late.replace(old_clock, 'set core [get_clocks -of_objects [get_pins u_ld/MMCME2_ADV/CLKOUT0]]')
    scope = '''    current_instance $inst
    source $src/boards/ypcb-00338/constraints/otpu_mem_ch.tcl
    current_instance
'''
    assert late.count(scope) == 1
    # The standalone top wires clk, uclk and xclk to the same LiteDRAM
    # output. Synthesis merges those hierarchy-pin aliases; queries through
    # get_ports cannot find them even in a scoped constraint file.
    top = src / 'rtl/boards/ypcb-00338/otpu_fpga_top_openxc7_jtag.sv'
    top_text = top.read_text()
    for connection in ('wire core_clk = ld_sys_clk;', 'wire xdma_aclk = ld_sys_clk;',
                       '.clk(core_clk), .rst(core_rst), .xclk(xdma_aclk), .xrst,',
                       '.uclk({2{ld_sys_clk}}), .urst({2{ld_sys_rst}}),'):
        assert connection in top_text, 'Shared-clock wiring differs: ' + connection
    constraints = src / 'boards/ypcb-00338/constraints/otpu_mem_ch.tcl'
    constraints_text = constraints.read_text()
    for name, port in (('c_clk', 'clk'), ('c_ucl', 'uclk'), ('c_xcl', 'xclk')):
        query = f'set {name} [get_clocks -quiet -of_objects [get_ports {port}]]'
        assert constraints_text.count(query) == 1
        constraints_text = constraints_text.replace(query, f'set {name} $core')
    constraints.write_text(constraints_text)
    # Source as Tcl under current_instance so missing constraint endpoints
    # fail immediately, rather than continuing with critical warnings.
    (out / 'late.tcl').write_text(late)
    original = (donor / 'build.tcl').read_text()
    boundary = 'source $out/late.tcl\n'
    assert original.count(boundary) == 1
    tail = boundary + original.split(boundary, 1)[1]
    assert tail.count('close_project') == 1
    tail = tail.replace('close_project', 'close_design')
    tail = tail.replace('TOP\\t[get_property NAME [current_design]]',
                        'TOP\\t[get_property TOP [current_design]]')
    prefix = '''set_param general.maxThreads 8
set src [lindex $argv 0]
set out [lindex $argv 1]
open_checkpoint $out/synth.dcp
if {[get_property PART [current_design]] ne "xc7k480tffg1156-2" || [get_property TOP [current_design]] ne "otpu_fpga_top_openxc7_jtag"} {error "Synthesis checkpoint identity differs: part=[get_property PART [current_design]] top=[get_property TOP [current_design]]"}
# Establish the board clock before applying DDR generated-clock uncertainty.
read_xdc $out/board.xdc
read_xdc $src/boards/ypcb-00338/litedram/otpu_litedram.xdc
'''
    (out / 'build.tcl').write_text(prefix + tail)
    command = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog',
               '-source', str(out / 'build.tcl'), '-tclargs', str(src), str(out)]
    (out / 'build.command.json').write_text(json.dumps(command, indent=2) + '\n')
    record = {k: previous[k] for k in ('top', 'part', 'profile', 'host', 'physical_user_channels',
              'logical_capacity_bytes', 'threads_requested', 'reference_pins', 'core', 'ecc_preparation')}
    record.update(status='PREPARED', started_utc=datetime.now(timezone.utc).isoformat(),
                  hardware_accessed=False, flash_written=False, physical_model_verified=False,
                  resumed_from=str(donor), donor_checkpoint=checkpoint, synthesis_reused=True,
                  helper=describe(Path(__file__)),
                  source_files=[describe(src / Path(x['path']).relative_to(donor / 'source'))
                                for x in previous['source_files']] +
                               [describe(src / 'boards/ypcb-00338/constraints/otpu_mem_ch.tcl')] +
                               [describe(out / n) for n in ('synth.dcp', 'board.xdc', 'late.tcl',
                                'build.tcl', 'expected-pins.json', 'pre_bit_gate.py')])
    def save():
        tmp = out / 'manifest.json.tmp'
        tmp.write_text(json.dumps(record, indent=2) + '\n')
        tmp.replace(out / 'manifest.json')
    try:
        save()
        with (out / 'build.log').open('w') as log:
            child = subprocess.Popen(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            record.update(status='NATIVE_VIVADO_BUILD_RUNNING', child_pid=child.pid)
            save()
            code = child.wait()
        record.pop('child_pid', None)
        record['build_exit'] = code
        (out / 'build.exit').write_text(str(code) + '\n')
        if code:
            raise RuntimeError('Vivado implementation failed; inspect build.log')
        record.update(status='CH1_JTAG_BITSTREAM_BUILD_PASS_IMAGE_REVIEW_PENDING',
                      outputs={n: describe(out / n) for n in
                               ('otpu-ch1-jtag.bit', 'final-routed.dcp', 'pre-bit-gates.json')})
        return 0
    except Exception as e:
        record.update(status='FAIL', error=repr(e))
        print(record['error'], flush=True)
        return 1
    finally:
        record['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
