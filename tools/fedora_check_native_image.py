#!/usr/bin/env python3
"""Check the completed full Vivado JTAG test image without touching hardware."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
FULL = dict(MCOLS=4, ACT_ROWS=4, MXU_IMPL=2, VPU_CL=2, LANES=8,
            CORE_KHZ=100000, DDR_MTS=800)
COMPLETE = 'VIVADO_JTAG_BITSTREAM_STRUCTURAL_CHECK_PASS_PHYSICAL_TEST_NOT_RUN'
CHECKER = ROOT.parent / 'bonetto-soc/scripts/fedora-check-vivado-bitstream.py'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def describe(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha)


def recorded(item):
    require(describe(item['path']) == item, 'Recorded file changed: ' + item['path'])


def timing_summary(text):
    """Read Vivado's design-wide row, not an individual clock-group row."""
    body = text.split('| Design Timing Summary', 1)[1]
    table = re.search(r'^\s*WNS\(ns\).*\n\s*-+.*\n\s*([-+0-9. ]+)\s*$', body, re.M)
    require(table is not None, 'Missing design-wide native timing summary')
    values = table[1].split()
    require(len(values) == 12, 'Unexpected native timing summary columns')
    names = ('WNS', 'TNS', 'setup_failing', 'setup_total', 'WHS', 'THS',
             'hold_failing', 'hold_total', 'WPWS', 'TPWS', 'pulse_failing', 'pulse_total')
    return {name:float(value) for name, value in zip(names, values)}


def route_summary(text):
    def number(label):
        found = re.findall(r'# of ' + label + r'\.+\s*:\s*(\d+)\s*:', text)
        require(len(found) == 1, 'Missing or duplicated native route count: ' + label)
        return int(found[0])
    return dict(routable=number('routable nets'), fully_routed=number('fully routed nets'),
                routing_errors=number('nets with routing errors'))


def bus_skew_summary(text):
    paths = re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns', text, re.M)
    # Fourteen Gray-pointer/count constraints per memory channel, plus the
    # two held JTAG mailbox payloads in the selected full standalone design.
    require(len(paths) == 30, 'Missing native bus-skew constraints')
    require(all(status == 'MET' and float(slack) >= 0 for status, slack in paths),
            'Native bus-skew violations remain')
    return dict(reported_constraints=len(paths), min_slack_ns=min(float(v) for _, v in paths),
                status='ALL_30_REPORTED_BUS_SKEW_CONSTRAINTS_MET')


def cdc_summary(text):
    rows = []
    for line in text.splitlines():
        if not line.startswith(('Critical ', 'Warning ', 'Info ')):
            continue
        fields = re.split(r'\s{2,}', line.strip())
        require(len(fields) == 10, 'Unexpected native CDC summary columns')
        rows.append(dict(severity=fields[0], source=fields[1], destination=fields[2],
                         type=fields[3], exceptions=fields[4], endpoints=int(fields[5]),
                         safe=int(fields[6]), unsafe=int(fields[7]), unknown=int(fields[8]),
                         no_async_reg=int(fields[9])))
    require(rows, 'Missing native CDC summary')
    return dict(rows=rows, unsafe_endpoints=sum(row['unsafe'] for row in rows),
                unknown_endpoints=sum(row['unknown'] for row in rows),
                status='REVIEW_PENDING' if any(row['unsafe'] or row['unknown'] for row in rows)
                else 'REPORTED_ENDPOINTS_SAFE')


def check(manifest):
    manifest = Path(manifest).resolve()
    info = json.loads(manifest.read_text())
    require(info.get('status') == COMPLETE and info.get('stage') == 'independently-checked',
            'Native Vivado bitstream generation and independent check have not completed')
    require(info.get('backend') == 'VIVADO_2026_1' and info.get('configuration') == FULL
            and info.get('part') == 'xc7k480tffg1156-2'
            and info.get('top') == 'otpu_fpga_top_openxc7_jtag', 'Wrong full native standalone profile')
    directory = manifest.parent
    require((directory / 'native-command.exit').read_text().strip() == '0'
            and (directory / 'structure-check.exit').read_text().strip() == '0',
            'Native execution or independent checker did not exit zero')
    for item in info['inputs']:
        recorded(item)
    require(info['placed_checkpoint'] in info['inputs'], 'Unpinned native placed checkpoint')
    config_items = [item for item in info['inputs'] if Path(item['path']).name == 'config.json']
    require(len(config_items) == 1, 'Missing native full-source configuration witness')
    config = json.loads(Path(config_items[0]['path']).read_text())
    require(config.get('configuration') == FULL and config.get('part') == info['part']
            and config.get('top') == info['top'] and len(config['source_snapshots']) == 31,
            'Native reference source scope differs')
    for pair in config['source_snapshots']:
        require(pair['original'] in info['inputs'] and pair['snapshot'] in info['inputs']
                and pair['original']['sha256'] == pair['snapshot']['sha256'],
                'Native full source differs from the selected accelerator')
    cores = [Path(pair['original']['path']).parent for pair in config['source_snapshots']
             if Path(pair['original']['path']).name == 'otpu_litedram.v']
    require(len(cores) == 1, 'Missing exact native DDR calibration data directory')
    output = directory / 'output'
    needed = {'design.bit', 'final-routed.dcp', 'final-timing.rpt', 'final-drc.rpt',
              'final-bus-skew.rpt', 'final-cdc.rpt', 'route-status.rpt', 'timing-gate.txt',
              'checkpoint-audit.txt', 'checkpoint-io.rpt', 'checkpoint-clocks.rpt'}
    require(needed <= set(info['artifacts']), 'Native build lacks complete implementation reports')
    for name, item in info['artifacts'].items():
        require(Path(name).name == name and Path(item['path']).resolve() == output / name,
                'Native artifact path differs')
        recorded(item)
        require(item['bytes'] > 0, 'Empty native artifact: ' + name)
    audit = (output / 'checkpoint-audit.txt').read_text().splitlines()
    metadata = dict(line.split('=', 1) for line in audit if '=' in line and not line.startswith('PORT\t'))
    for name, value in dict(PART=info['part'], TOP=info['top'], PORTS='243', CFGBVS='GND',
                            CONFIG_VOLTAGE='1.8', JTAG_CHAIN='2', DSP48E1='716',
                            RAMB36E1='562', RAMB18E1='34', ISERDESE2='144',
                            OSERDESE2='214', IDELAYE2='144').items():
        require(metadata.get(name) == value, 'Native checkpoint audit differs: ' + name)
    pins = [line for line in audit if line.startswith('PORT\t')]
    expected = (directory / 'expected-port-constraints.tsv').read_text().splitlines()
    require(len(pins) == 243 and {line[5:] for line in pins} == set(expected),
            'Native pin/standard audit does not match all 243 expected ports')
    routed = route_summary((output / 'route-status.rpt').read_text())
    require(routed['routing_errors'] == 0 and routed['routable'] == routed['fully_routed'] > 0,
            'Native design is not fully routed without errors')
    timing_text = (output / 'final-timing.rpt').read_text()
    timing = timing_summary(timing_text)
    require(all(timing[name] >= 0 for name in ('WNS', 'WHS', 'WPWS'))
            and all(timing[name] == 0 for name in ('setup_failing', 'hold_failing', 'pulse_failing')),
            'Native setup/hold/pulse-width timing violations remain')
    checks = {name:int(value) for name, value in
              re.findall(r'^\d+\. checking (\w+) \((\d+)\)$', timing_text, re.M)}
    for name in ('no_clock', 'unconstrained_internal_endpoints', 'multiple_clock',
                 'generated_clocks', 'loops', 'partial_input_delay', 'partial_output_delay', 'latch_loops'):
        require(checks.get(name) == 0, 'Native timing coverage is incomplete: ' + name)
    skew = bus_skew_summary((output / 'final-bus-skew.rpt').read_text())
    cdc = cdc_summary((output / 'final-cdc.rpt').read_text())
    recorded(info['structure_check'])
    require(info['structure_checker'] == describe(CHECKER), 'Native packet checker differs')
    spec = importlib.util.spec_from_file_location('ypcb_native_packet_checker', CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    bit = info['artifacts']['design.bit']
    structure = module.check(Path(bit['path']), bit['sha256'])
    receipt = json.loads(Path(info['structure_check']['path']).read_text())
    require(receipt == structure and structure['status'] == 'PASS', 'Native packet receipt differs')
    return dict(status='FULL_NATIVE_JTAG_TEST_IMAGE_PROVENANCE_ROUTE_AND_TIMING_CHECK_PASS',
                manifest=describe(manifest), bitstream=bit, configuration=FULL,
                litedram_core=str(cores[0]),
                route=routed, timing_summary=timing, timing_coverage=checks,
                bus_skew=skew, cdc=cdc,
                structure=structure, checker=describe(__file__),
                external_ddr_timing='CALIBRATION_AND_PHYSICAL_BOARD_TEST_PENDING',
                synthesis_warning_review=info['synthesis_warning_review'],
                physical_hardware='NOT_RUN', programming='NOT_RUN', flash_written=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--emit-bit', action='store_true', help='print only the verified bitstream path')
    args = parser.parse_args()
    try:
        if args.out:
            require(not args.out.exists(), 'Output receipt already exists')
        result = check(args.manifest)
    except Exception as error:
        result = dict(status='FAIL', error=str(error), physical_hardware='NOT_RUN',
                      programming='NOT_RUN', flash_written=False)
    result['captured_utc'] = datetime.now(timezone.utc).isoformat()
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open('x') as stream:
            json.dump(result, stream, indent=2)
            stream.write('\n')
    if args.emit_bit:
        if result['status'] == 'FAIL':
            parser.exit(1, result['error'] + '\n')
        path = result['bitstream']['path']
        require('\n' not in path and '\r' not in path, 'Unsupported newline in bitstream path')
        print(path)
    else:
        print(json.dumps(result, indent=2))
    return 1 if result['status'] == 'FAIL' else 0


if __name__ == '__main__':
    raise SystemExit(main())
