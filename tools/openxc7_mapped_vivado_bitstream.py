#!/usr/bin/env python3
"""Export a fully reviewed mapped Vivado reference without accessing hardware."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from datetime import datetime, timezone
import importlib.util
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile

from fedora_openxc7 import PART, describe
from openxc7_mapped_edif import PROFILE, TOP
from openxc7_mapped_route_review import review, route_summary, timing_summary

ROOT = Path(__file__).resolve().parents[1]
CHECKER = ROOT.parent / 'bonetto-soc/scripts/fedora-check-vivado-bitstream.py'
PASS = 'FULL_REFERENCE_ROUTE_NUMERICAL_TIMING_CLOCKS_CDC_MEMORY_PASS_HARDWARE_PENDING'


def pinned(descriptor):
    if describe(descriptor['path']) != descriptor:
        raise ValueError('Recorded input changed: ' + descriptor['path'])
    return json.loads(Path(descriptor['path']).read_text())


def inputs(review_path):
    result = json.loads(review_path.read_text())
    if result['status'] != PASS or result['profile'] != PROFILE or not result['numerical_timing_pass']:
        raise ValueError('Completed full positive setup/hold/pulse route review required')
    checkpoint = result['checkpoints']['routed.dcp']
    if describe(checkpoint['path']) != checkpoint:
        raise ValueError('Reviewed routed checkpoint changed')
    with zipfile.ZipFile(checkpoint['path']) as archive:
        metadata = ET.fromstring(archive.read('dcp.xml'))
    if metadata.find('Top').get('Name') != TOP or metadata.find('Part').get('Name') != PART:
        raise ValueError('Reviewed checkpoint module or part differs')
    native = pinned(result['native_route'])
    source = native
    lineage = [result['native_route']]
    seen = set()
    while 'link' not in source:
        parent = source.get('baseline')
        if not parent or parent['path'] in seen:
            raise ValueError('Original implementation lineage missing or cyclic')
        seen.add(parent['path'])
        parent_review = pinned(parent)
        source = pinned(parent_review['native_route'])
        lineage += [parent, parent_review['native_route']]
    link = pinned(source['link'])
    lineage.append(source['link'])
    xdc = link['xdc']
    if describe(xdc['path']) != xdc:
        raise ValueError('Original package constraints changed')
    properties = {}
    for prop, value, port in re.findall(
            r'^set_property (\S+) (\S+) \[get_ports \{([^{}\n]+)\}\]\s*$',
            Path(xdc['path']).read_text(), re.M):
        previous = properties.setdefault(port, {}).get(prop)
        if previous is not None and previous != value:
            raise ValueError('Conflicting original pin property: ' + port + '/' + prop)
        properties[port][prop] = value
    if len(properties) != 243 or any(not {'PACKAGE_PIN', 'IOSTANDARD'} <= set(p) for p in properties.values()):
        raise ValueError('Complete 243-port package and standard witness required')
    config = ROOT / 'boards/ypcb-00338/constraints/otpu_top_ld.xdc'
    settings = dict(re.findall(r'^set_property (CFGBVS|CONFIG_VOLTAGE) (\S+) \[current_design\]',
                               config.read_text(), re.M))
    if settings != {'CFGBVS': 'GND', 'CONFIG_VOLTAGE': '1.8'}:
        raise ValueError('Original board configuration profile changed')
    return result, checkpoint, lineage, xdc, properties, describe(config)


def export(review_path, out):
    result, checkpoint, lineage, xdc, properties, config = inputs(review_path)
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'PREPARING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'review': describe(review_path), 'checkpoint': checkpoint, 'lineage': lineage,
            'package_constraints': xdc, 'configuration_constraints': config,
            'helper': describe(__file__), 'packet_checker': describe(CHECKER),
            'profile': PROFILE, 'part': PART, 'top': TOP, 'threads': 8,
            'hardware_accessed': False, 'flash_written': False, 'accepted_image': False,
            'electrical_values': 'EXISTING_BOARD_REFERENCE_CONSTRAINTS_NOT_NEW_MEASUREMENTS',
            'scope': 'FULL_MAPPED_VIVADO_REFERENCE_OFFLINE_IMAGE_NOT_OPENXC7_OR_HARDWARE_PASS'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        review(Path(result['native_route']['path']), out / 'route-rechecked')
        rechecked = json.loads((out / 'route-rechecked/manifest.json').read_text())
        if rechecked['status'] != PASS or rechecked['timing'] != result['timing']:
            raise ValueError('Independent full route review no longer passes')
        tcl = ['set_param general.maxThreads 8', 'set_param tcl.collectionResultDisplayLimit 0',
               'open_checkpoint {' + checkpoint['path'] + '}',
               'if {[get_property PART [current_design]] ne {' + PART + '}} {error "Wrong reference part"}',
               'if {[get_property TOP [current_design]] ne {' + TOP + '}} {error "Wrong reference top"}',
               'set_property CFGBVS GND [current_design]',
               'set_property CONFIG_VOLTAGE 1.8 [current_design]',
               'set_property BITSTREAM.GENERAL.COMPRESS FALSE [current_design]',
               'set bscan [get_cells -hierarchical -filter {REF_NAME == BSCANE2}]',
               'if {[llength $bscan] != 1 || [get_property JTAG_CHAIN $bscan] ne "2"} {error "USER2 BSCAN differs"}',
               'if {[llength [get_ports]] != 243} {error "Full reference port count differs"}',
               'set pf [open pins.tsv w]', 'puts $pf "port\tproperty\tvalue"']
        for port, props in sorted(properties.items()):
            if any(char in port for char in '{}\r\n'):
                raise ValueError('Unsupported exact package port name')
            tcl += ['set p [get_ports {' + port + '}]',
                    'if {[llength $p] != 1} {error "Original port missing"}']
            for prop, value in sorted(props.items()):
                if not re.fullmatch(r'[A-Z0-9_]+', prop) or not re.fullmatch(r'[A-Za-z0-9_.]+', value):
                    raise ValueError('Unsupported exact package property')
                tcl += ['set v [get_property ' + prop + ' $p]']
                if prop == 'PULLUP':
                    if value.lower() not in ('true', 'false', '1', '0'):
                        raise ValueError('Unsupported original Boolean pin property')
                    allowed = "1 true True TRUE 1'b1 1'h1" if value.lower() in ('true', '1') else "0 false False FALSE 1'b0 1'h0"
                    tcl += ['if {$v ni {' + allowed + '}} {error "Original pullup setting changed"}']
                else:
                    tcl += ['if {$v ne {' + value + '}} {error "Original IO property changed: ' + port + '/' + prop + '"}']
                tcl += ['puts $pf [join [list {' + port + '} {' + prop + '} $v] "\t"]']
        tcl += ['close $pf']
        for bank in range(11, 19):
            tcl += ['if {abs([get_property INTERNAL_VREF [get_iobanks ' + str(bank) +
                    ']] - 0.750) > 0.000001} {error "Original DDR VREF changed"}']
        tcl += ['report_drc -file final-drc.rpt',
                'foreach violation [get_drc_violations] {',
                '  set severity [get_property SEVERITY $violation]',
                '  if {[regexp -nocase {error|critical} $severity]} {error "Unresolved native DRC: $violation ($severity)"}',
                '}', 'report_route_status -file route-status.rpt',
                'report_timing_summary -file final-timing.rpt',
                'report_clocks -file final-clocks.rpt',
                'write_checkpoint -force final-routed.dcp',
                'write_bitstream -force full-mapped-reference.bit',
                'puts "FULL_MAPPED_REFERENCE_BITSTREAM_EXPORTED"', 'exit 0']
        (out / 'bitstream.tcl').write_text('\n'.join(tcl) + '\n')
        argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog',
                '-notrace', '-source', str(out / 'bitstream.tcl')]
        (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
        save(status='RUNNING', route_rechecked=describe(out / 'route-rechecked/manifest.json'))
        print('FULL_MAPPED_REFERENCE_BITSTREAM_STARTED ' + str(out), flush=True)
        with (out / 'bitstream.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_launcher_pid=child.pid)
            code = child.wait()
        (out / 'bitstream.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code or 'FULL_MAPPED_REFERENCE_BITSTREAM_EXPORTED' not in (out / 'bitstream.log').read_text():
            raise RuntimeError('Native guarded bitstream generation incomplete')
        final_timing = timing_summary(out / 'final-timing.rpt')
        if final_timing != rechecked['timing']:
            raise ValueError('Final bitstream checkpoint timing changed')
        final_route = route_summary(out / 'route-status.rpt')
        if final_route != rechecked['route']:
            raise ValueError('Final bitstream checkpoint routing changed')
        spec = importlib.util.spec_from_file_location('mapped_vivado_packet_checker', CHECKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        bit = describe(out / 'full-mapped-reference.bit')
        packet = module.check(Path(bit['path']), bit['sha256'])
        (out / 'packet-check.json').write_text(json.dumps(packet, indent=2) + '\n')
        if packet['status'] != 'PASS' or describe(CHECKER) != info['packet_checker']:
            raise ValueError('Independent packet checker failed or changed')
        if describe(checkpoint['path']) != checkpoint or describe(review_path) != info['review']:
            raise ValueError('Preserved full reviewed reference changed during export')
        for descriptor in [config, xdc, *lineage]:
            if describe(descriptor['path']) != descriptor:
                raise ValueError('Full reference input changed during export: ' + descriptor['path'])
        save(status='FULL_MAPPED_REFERENCE_BITSTREAM_TIMING_DRC_PINS_PACKET_PASS_HARDWARE_PENDING',
             final_timing=final_timing, final_route=final_route, original_ports=243,
             original_port_properties=sum(map(len, properties.values())), jtag_chain=2,
             internal_vref_banks=list(range(11, 19)), crc=packet['crc'],
             outputs={name: describe(out / name) for name in ['full-mapped-reference.bit', 'final-routed.dcp',
                      'pins.tsv', 'final-drc.rpt', 'final-timing.rpt', 'final-clocks.rpt', 'route-status.rpt',
                      'packet-check.json', 'bitstream.tcl', 'command.json', 'bitstream.exit', 'bitstream.log']},
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
    export(args.review.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
