#!/usr/bin/env python3
"""Review a completed RAM-only MIG build before packaging; no hardware access."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from check_vivado_bitstream import parse_bitstream
from fedora_check_native_image import route_summary, timing_summary

ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / 'bitstreams/ramtest-mig-ddr800-address'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cdc_rows(text):
    """Read every non-info row and reconcile it with Vivado's summary.

    Keep this reader standalone: historical preparation tools copy this module
    without the newer shared parser. Vivado stops padding row numbers at 100.
    """
    rows = []
    summary = {}
    for line in text.splitlines():
        count = re.match(r'^\s*(CDC-\d+)\s+(Critical|Warning)\s+(\d+)\s+', line)
        if count:
            key = count[1], count[2]
            require(key not in summary, 'Duplicate CDC summary entry: ' + str(key))
            summary[key] = int(count[3])
        if not re.match(r'^\s*\d+\s+CDC-\d+\s+(Critical|Warning)\b', line):
            continue
        fields = re.split(r'\s{2,}', line.strip())
        require(len(fields) == 8, 'Unexpected CDC report format')
        rows.append(tuple(fields[1:]))  # Exclude the table-local row number.
    require(summary, 'Missing non-info CDC summary')
    require(rows, 'Missing CDC detail rows')
    expected = Counter({key: value for key, value in summary.items() if value})
    actual = Counter((row[0], row[1]) for row in rows)
    require(expected == actual,
            'Incomplete CDC details: summary=' + repr(dict(expected)) +
            ', parsed=' + repr(dict(actual)))
    return rows


def payload_path(row):
    """Normalize only reviewed, constrained held-bus representative paths.

    Vivado reports one representative input to each snapshot mux output. Its
    chosen snapshot bit changes with placement/patterns. Payload registers may
    also be replicated; the existing wildcard constraints include those copies.
    The protocol source and all four fresh skew constraints are checked below.
    """
    kind, severity, description, depth, exception, source, target = row
    if (kind, severity, depth, exception) != ('CDC-15', 'Warning', '0', 'Max Delay Datapath Only'):
        return row
    snap = re.fullmatch(r'u_observer([01])/snapshot_reg\[(\d+)\]/C', source)
    response = re.fullmatch(r'u_status/response_data_reg\[(\d+)\]/D', target)
    if snap and response and int(snap[2]) < 2048 and int(response[1]) < 32:
        source = f'u_observer{snap[1]}/snapshot_reg[*]/C'
    held = re.fullmatch(r'u_status/u_mailbox/(held|response)_reg\[(\d+)\]/C', source)
    capture = re.fullmatch(r'u_status/u_mailbox/(req|response_tck)_reg\[(\d+)\](?:_rep__\d+)?/D', target)
    if held and capture and held[2] == capture[2] and (
            (held[1], capture[1]) == ('held', 'req') and int(held[2]) < 604 or
            (held[1], capture[1]) == ('response', 'response_tck') and int(held[2]) < 536):
        target = f'u_status/u_mailbox/{capture[1]}_reg[{capture[2]}]/D'
    return kind, severity, description, depth, exception, source, target


def review(build):
    mp = build / 'manifest.json'
    manifest = json.loads(mp.read_text())
    require(manifest['status'] == 'RAM_ONLY_BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING',
            'RAM-only implementation did not finish')
    require(manifest['ddr_mts'] == 800 and manifest['channels'] in (1, 2, 3),
            'This review covers the DDR800 suite only')
    require(manifest['pattern'] in ('address', 'zeros', 'ones', 'walking1', 'walking0', 'prbs'),
            'Unknown test pattern')
    for name, expected in manifest['snapshot_source_sha256'].items():
        path = (build / 'source' / name).resolve()
        require(path.is_relative_to(build / 'source') and sha(path) == expected,
                'Frozen RAM-test source changed: ' + name)
    bit = build / 'ramtest.bit'
    require(sha(bit) == manifest['bitstream_sha256'], 'Bitstream changed after build')
    require(sha(build / 'otpu_mig_ddr3.prj') == manifest['generated_prj_sha256'],
            'Generated MIG configuration changed')
    packet = parse_bitstream(bit.read_bytes())
    require(packet == manifest['packet_check'], 'Packet review differs from build receipt')
    crc = json.loads((build / 'crc.log').read_text())
    require(crc == manifest['crc'] and crc['status'] == 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH',
            'Independent bitstream CRC review did not pass')

    controllers = ET.parse(build / 'otpu_mig_ddr3.prj').getroot().findall('Controller')
    reference = ET.parse(ROOT / 'boards/ypcb-00338/ramtest/mig-ddr3-1066.prj').getroot().findall('Controller')
    require(len(controllers) == len(reference) == 2, 'Missing physical DDR controller')
    expected_pins = {}
    for channel, (controller, original) in enumerate(zip(controllers, reference)):
        for field, value in {'TimePeriod': '2500', 'MMCM_VCO': '800', 'DataWidth': '72',
                             'ECC': 'Enabled', 'RowAddress': '15', 'ColAddress': '10',
                             'BankAddress': '3', 'PortInterface': 'NATIVE',
                             'mrCasLatency': '6', 'mr2CasWriteLatency': '5'}.items():
            require(controller.findtext(field) == value, 'Unexpected MIG field: ' + field)
        require(ET.canonicalize(ET.tostring(controller.find('PinSelection'), encoding='unicode'), strip_text=True) ==
                ET.canonicalize(ET.tostring(original.find('PinSelection'), encoding='unicode'), strip_text=True),
                'DDR board-reference pin selection changed')
        for pin in controller.find('PinSelection').findall('Pin'):
            name = pin.attrib['name']
            standard = ('LVCMOS15' if name == 'ddr3_reset_n' else
                        'DIFF_SSTL15' if 'dqs_' in name or 'ck_' in name else 'SSTL15')
            expected_pins[f'c{channel}_{name}'] = (pin.attrib['PADName'], standard)
        pads = controller.find('System_Clock/Pin').attrib['PADName']
        require(pads == original.find('System_Clock/Pin').attrib['PADName'],
                'DDR reference clock pins changed')
        for polarity, pad in zip(('p', 'n'), pads.split('(')[0].split('/')):
            expected_pins[f'c{channel}_sys_clk_{polarity}'] = (pad, 'DIFF_SSTL15')
    for name, pad in {'SYS_CLK': 'AA28', 'led[0]': 'P30', 'led[1]': 'M30', 'led[2]': 'N30'}.items():
        expected_pins[name] = (pad, 'LVCMOS18')
    observed = {}
    for line in (build / 'reports/io.rpt').read_text().splitlines():
        columns = [x.strip() for x in line.split('|')[1:-1]] if line.startswith('|') else []
        if len(columns) > 12 and columns[4] in ('INPUT', 'OUTPUT', 'BIDIR'):
            require(columns[12] == 'FIXED' and columns[1] not in observed,
                    'Unfixed or duplicate board port')
            observed[columns[1]] = (columns[0], columns[5])
    require(len(expected_pins) == 242 and observed == expected_pins,
            'Implemented board pins/standards differ from the 242-port reference')

    timing_text = (build / 'reports/timing.rpt').read_text()
    timing = timing_summary(timing_text)
    require(all(timing[k] >= 0 for k in ('WNS', 'WHS', 'WPWS')) and
            all(timing[k] == 0 for k in ('TNS', 'THS', 'TPWS', 'setup_failing',
                                       'hold_failing', 'pulse_failing')), 'Timing did not pass')
    coverage = {}
    for key, count in re.findall(r'^\d+\. checking (\w+) \((\d+)\)$', timing_text, re.M):
        coverage.setdefault(key, set()).add(int(count))
    for key in ('no_clock', 'constant_clock', 'pulse_width_clock', 'unconstrained_internal_endpoints',
                'no_input_delay', 'multiple_clock', 'generated_clocks', 'loops',
                'partial_input_delay', 'partial_output_delay', 'latch_loops'):
        require(coverage.get(key) == {0}, 'Timing coverage incomplete: ' + key)
    # Three LEDs and two DDR reset outputs use deliberate false paths.
    require(coverage.get('no_output_delay') == {5}, 'Unexpected output timing coverage')
    route = route_summary((build / 'reports/route.rpt').read_text())
    require(route['routable'] == route['fully_routed'] > 0 and route['routing_errors'] == 0,
            'Routing incomplete')
    require(not re.search(r'^\S+#\d+\s+(?:Error|Critical Warning)',
                          (build / 'reports/drc.rpt').read_text(), re.M), 'Blocking DRC findings')
    skew = re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',
                      (build / 'reports/bus_skew.rpt').read_text(), re.M)
    require(len(skew) == 4 and all(k == 'MET' and float(v) >= 0 for k, v in skew),
            'Held-payload bus skew failed')

    baseline_review = json.loads((BASELINE / 'evidence/offline-review.json').read_text())
    require(baseline_review['status'] == 'OFFLINE_ADDRESS_IMAGE_CHECKS_PASS_PHYSICAL_TESTS_PENDING'
            and baseline_review['bitstream_sha256'] == sha(BASELINE / 'ramtest.bit'),
            'Address baseline CDC review is unavailable')
    baseline_build = json.loads((BASELINE / 'evidence/build-manifest.json').read_text())
    protocol_files = ('ramtest_jtag.sv', 'ramtest_channel.sv', 'ramtest_cdc.tcl', 'otpu_jtag_mailbox.sv')
    for name in protocol_files:
        require(sha(build / 'source' / name) == baseline_build['snapshot_source_sha256'][name],
                'Reviewed CDC protocol/constraints changed: ' + name)
    baseline_cdc = gzip.decompress((BASELINE / 'evidence/cdc.rpt.gz').read_bytes()).decode()
    allowed = Counter(cdc_rows(baseline_cdc))
    current = Counter(cdc_rows((build / 'reports/cdc.rpt').read_text()))
    require({payload_path(row) for row in current} <= {payload_path(row) for row in allowed},
            'New CDC findings require manual review')
    critical = [row for row in current.elements() if row[1] == 'Critical']
    require(Counter(critical) == Counter(row for row in allowed.elements() if row[1] == 'Critical'),
            'Expected two vendor reset crossings changed')
    return dict(status='OFFLINE_RAM_ONLY_IMAGE_CHECKS_PASS_PHYSICAL_TESTS_PENDING',
                reviewed_utc=datetime.now(timezone.utc).isoformat(),
                reviewer_sha256=sha(Path(__file__)), build_manifest_sha256=sha(mp),
                build_id=manifest['build_id'], pattern=manifest['pattern'],
                traffic_channel_mask=manifest['channels'], ddr_mts=800,
                physical_hardware_test='NOT_RUN', pins_checked=len(observed),
                bitstream_sha256=sha(bit), packet_check=packet, crc=crc,
                timing=timing, route=route,
                timing_coverage={key: sorted(value) for key, value in coverage.items()},
                bus_skew=dict(constraints=4, minimum_slack_ns=min(float(v) for _, v in skew)),
                cdc_critical_paths=critical, cdc_non_info_rows=sum(current.values()),
                cdc_reference_sha256=sha(BASELINE / 'evidence/cdc.rpt.gz'),
                cdc_protocol_source_match=list(protocol_files),
                cdc_payload_review='Representative snapshot mux bits and _rep__ request/response register copies are normalized only for CDC-15, depth 0, Max Delay Datapath Only. Identical protocol/constraint source and four fresh skew checks are required.',
                cdc_changed_representatives=[list(row) for row in current if row not in allowed],
                cdc_review=baseline_review['cdc_review'],
                reports_sha256={p.name: sha(p) for p in sorted((build / 'reports').glob('*.rpt'))},
                limitations=[
                    'First-error address/data record is unverified; use sticky lane/cycle/ECC counters.',
                    'Fill once and repeat reads; mixed traffic and retention are separate experiments.',
                    'Channel isolation selects traffic; both PHYs remain present and calibrate.',
                    'Mac programming, USER2 readback and physical RAM tests are pending.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', required=True, type=Path)
    parser.add_argument('--out', required=True, type=Path, help='New JSON review file')
    args = parser.parse_args()
    require(not args.out.exists(), 'Choose a new review output file')
    result = review(args.build.resolve())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({k: result[k] for k in ('status', 'build_id', 'bitstream_sha256', 'pins_checked')}))


if __name__ == '__main__':
    main()
