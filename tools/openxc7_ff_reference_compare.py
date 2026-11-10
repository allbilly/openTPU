#!/usr/bin/env python3
"""Validate routed reference FF inventory, physical pins and path contributions."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil

from fedora_openxc7 import describe
from openxc7_ff_path_compare import read_arcs


# Exact external inputs of the mapped YPCB reference. These are retained as
# unvalidated boundaries, never as numerical matches or zero-delay paths.
EXTERNAL_BOUNDARIES = {
    ('BSCANE2', 'u_bscan', 'TDI'): ('u_bscan/TDI', 'jtag_tck', Decimal('166.667')),
    ('IBUF', 'u_iob_scl0/IBUF', 'O'): ('lm73_scl', 'u_ld.crg_s7mmcm_clkout', Decimal('10')),
    ('IBUF', 'u_iob_sda0/IBUF', 'O'): ('lm73_sda', 'u_ld.crg_s7mmcm_clkout', Decimal('10')),
    ('IBUF', 'u_iob_scl1/IBUF', 'O'): ('smb_scl', 'u_ld.crg_s7mmcm_clkout', Decimal('10')),
    ('IBUF', 'u_iob_sda1/IBUF', 'O'): ('smb_sda', 'u_ld.crg_s7mmcm_clkout', Decimal('10')),
    ('IBUF', '$iopadmap$otpu_fpga_top_openxc7_jtag.lm73_alert_n', 'O'):
        ('lm73_alert_n', 'u_ld.crg_s7mmcm_clkout', Decimal('10')),
}


def external_boundary(row, record, text, reference):
    if (not reference or reference.get('top') != 'otpu_fpga_top_openxc7_jtag'
            or reference.get('status') != 'FULL_MAPPED_REFERENCE_BITSTREAM_TIMING_DRC_PINS_PACKET_PASS_HARDWARE_PENDING'
            or reference.get('native_exit') != 0):
        return None
    boundary = EXTERNAL_BOUNDARIES.get((record['driver_type'], record['driver_cell'], record['driver_port']))
    if boundary is None:
        return None
    source, clock, period = boundary
    source_match = re.search(r'^\s*Source:\s*(\S+)\s*$', text, re.M)
    destination = re.search(r'^\s*Destination:\s*(\S+)\s*$', text, re.M)
    capture = re.search(r'cell FDRE clocked by (\S+)\s+\{[^}]*period=([\d.]+)ns\}', text)
    if (row['count'] != '1' or row['requirement_ns'] or row['slack_ns']
            or row['start_pin'] != source or not source_match or source_match[1] != source
            or not destination or destination[1] != row['end_pin']
            or row['end_pin'] != record['cell'] + '/D'
            or not re.search(r'Path Group:\s*\(none\)', text)
            or not re.search(r'Slack:\s+inf\b', text)
            or not capture or capture[1] != clock or Decimal(capture[2]) != period
            or not Decimal(row['datapath_ns']).is_finite()):
        return None
    return {'source': source, 'capture_clock': clock, 'capture_period_ns': str(period),
            'driver_type': record['driver_type'], 'driver_cell': record['driver_cell'],
            'driver_port': record['driver_port'], 'datapath_ns': row['datapath_ns'],
            'numerically_validated': False, 'requirement': 'NOT_PROVIDED_BY_REFERENCE'}


def rows(path):
    # Preserve the complete full-design site-pin lists when checking coverage.
    csv.field_size_limit(64 * 1024 * 1024)
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def validate(query: Path, out: Path):
    gate = json.loads((query / 'manifest.json').read_text())
    if gate['status'] != 'ALL_ROUTED_REFERENCE_FF_GROUPS_QUERY_COMPLETE_COMPARISON_PENDING' or gate['native_exit'] != 0:
        raise ValueError('Complete native reference query required')
    for record in [gate['checkpoint'], *gate['outputs'].values()]:
        if describe(record['path']) != record:
            raise ValueError('Immutable reference input/output changed')
    reference = None
    if gate.get('reference_image'):
        descriptor = gate['reference_image']
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Mapped reference image provenance changed')
        reference = json.loads(Path(descriptor['path']).read_text())
        if reference['profile'] != gate['profile']:
            raise ValueError('Mapped reference full profile differs')
    inventory = rows(query / 'inventory.tsv')
    samples = rows(query / 'samples.tsv')
    paths = rows(query / 'paths.tsv')
    named = {row['cell']: row for row in inventory}
    by_sample = {row['sample']: row for row in samples}
    native_count = re.search(r'REFERENCE_FF_COUNT\|(\d+)', (query / 'query.log').read_text())
    if (not native_count or int(native_count[1]) != len(inventory) or len(named) != len(inventory)
            or len(inventory) != gate['ff_count'] or len(by_sample) != len(samples)):
        raise ValueError('Complete actual FF scope differs')
    groups = Counter(row['group'] for row in inventory)
    counts = Counter(row['group'] for row in samples)
    if counts != {key: min(value, gate['samples_per_group']) for key, value in groups.items()}:
        raise ValueError('Actual group sample coverage differs')
    expected = {(sample, mode) for sample in by_sample for mode in ('max', 'min')}
    if len(paths) != len(expected) or {(row['case'], row['mode']) for row in paths} != expected:
        raise ValueError('Actual path query coverage differs')
    for sample in samples:
        record = named[sample['cell']]
        bel = record['bel'].split('.')[-1]
        if (sample['group'] != record['group'] or not record['loc']
                or f"{record['loc']}/{bel}/D" not in sample['capture_bel_pins'].split()):
            raise ValueError('Actual routed capture BEL/pin mapping differs')
        if record['driver_type'] not in ('PRIMARY_INPUT', 'GND', 'VCC') and not sample['driver_bel_pins']:
            raise ValueError('Actual routed driver lacks physical BEL mapping')
    arcs = read_arcs(query / 'arcs.tsv')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'query': describe(query / 'manifest.json'), 'helper': describe(__file__),
            'raw_arc_parser': describe(Path(__file__).with_name('openxc7_ff_path_compare.py')),
            'checkpoint': gate['checkpoint'], 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'ACTUAL_ROUTED_VIVADO_REFERENCE_CONTEXT_COMPARISON_NOT_UNIVERSAL_OPENXC7_MODEL'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='independent-reference-comparison')
        compared = []
        boundaries = []
        for row in paths:
            sample = by_sample[row['case']]
            cell = sample['cell']
            base = {'sample': row['case'], 'cell': cell, 'group': sample['group'], 'mode': row['mode']}
            if row['count'] == '0':
                compared.append({**base, 'status': 'NO_TIMED_PATH', 'driver_type': named[cell]['driver_type']})
                continue
            if row['count'] != '1':
                raise ValueError('Ambiguous actual path count')
            report = query / ('reference-' + row['case'] + '-' + row['mode'] + '.rpt')
            text = report.read_text()
            if row['end_pin'] != cell + '/D':
                raise ValueError('Reference path endpoint differs from selected cell')
            if not row['slack_ns'] or not Decimal(row['slack_ns']).is_finite():
                if re.search(r'Timing Exception:\s+False\s*Path', text) and re.search(r'Slack:\s+inf\b', text):
                    compared.append({**base, 'status': 'IGNORED_FALSE_PATH'})
                else:
                    boundary = external_boundary(row, named[cell], text, reference)
                    if boundary is None:
                        raise ValueError('Unexplained unconstrained reference path: ' + str(report))
                    item = {**base, **boundary, 'status': 'UNCONSTRAINED_EXTERNAL_BOUNDARY_NOT_VALIDATED'}
                    compared.append(item)
                    boundaries.append(item)
                continue
            corner = re.search(r'Path Type:[^\n]*\b(?:Max|Min) at (Fast|Slow) Process Corner', text)
            if not corner:
                raise ValueError('Missing actual report corner')
            kind = 'setup' if row['mode'] == 'max' else 'hold'
            prefix = 'Setup_' if kind == 'setup' else 'Hold_'
            choices = [Decimal(m[2]) for m in re.finditer(r'\(([^()\s]+)\)\s+(-?\d+\.\d+)', text) if m[1].startswith(prefix)]
            if len(choices) != 1:
                raise ValueError('Missing/ambiguous actual FF contribution: ' + str(report))
            value = -choices[0] if kind == 'setup' else choices[0]
            arc = arcs[('reference', cell, 'C', 'D', kind)]
            values = {Decimal(arc[key]) for key in (f'DELAY_{corner[1].upper()}_MAX_RISE', f'DELAY_{corner[1].upper()}_MAX_FALL') if key in arc}
            if arc['IS_DISABLED'] != '0' or value not in values:
                raise ValueError('Actual routed FF report/raw arc discrepancy: ' + str(report))
            compared.append({**base, 'status': 'MATCH', 'kind': kind, 'corner': corner[1],
                             'check_ns': str(value), 'driver_type': named[cell]['driver_type'],
                             'same_site': named[cell]['same_site'], 'capture_bel_pins': sample['capture_bel_pins'],
                             'capture_site_pins': sample['capture_site_pins'], 'mismatches': 0})
        signatures = defaultdict(list)
        for sample in samples:
            cell = sample['cell']
            checks = {}
            for kind in ('setup', 'hold'):
                arc = arcs[('reference', cell, 'C', 'D', kind)]
                checks[kind] = {key: str(Decimal(value).normalize()) for key, value in arc.items() if key.startswith('DELAY_')}
            signatures[sample['group']].append((sample['sample'], checks))
        variation = []
        for group, values in signatures.items():
            unique = defaultdict(list)
            for sample, checks in values:
                unique[json.dumps(checks, sort_keys=True)].append(sample)
            variation.append({'group': group, 'distinct_signatures': len(unique),
                              'samples': len(values), 'signatures': [{'samples': names, 'checks': json.loads(signature)} for signature, names in unique.items()]})
        (out / 'path-comparison.json').write_text(json.dumps(compared, indent=2) + '\n')
        (out / 'group-variation.json').write_text(json.dumps(variation, indent=2) + '\n')
        (out / 'unvalidated-boundaries.json').write_text(json.dumps(boundaries, indent=2) + '\n')
        statuses = dict(Counter(row['status'] for row in compared))
        save(status='ALL_ROUTED_REFERENCE_FF_GROUPS_AND_FINITE_PATH_CHECKS_MATCH', ff_count=len(inventory),
             groups=len(groups), samples=len(samples), path_queries=len(paths), path_statuses=statuses,
             groups_with_numeric_variation=sum(row['distinct_signatures'] > 1 for row in variation), mismatches=0,
             primitive_counts=gate['primitive_counts'], driver_counts=gate['driver_counts'],
             constant_driver_samples=sum(named[row['cell']]['driver_type'] in ('GND', 'VCC') for row in samples),
             unvalidated_boundary_queries=len(boundaries),
             external_boundary_qualification='PENDING' if boundaries else 'NO_UNTIMED_EXTERNAL_SAMPLES',
             native_import='PENDING_OPENXC7_PHYSICAL_CONTEXT_MAPPING_AND_COVERAGE',
             outputs={name: describe(out / name) for name in ('path-comparison.json', 'group-variation.json',
                                                             'unvalidated-boundaries.json')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({key: info[key] for key in ('status', 'ff_count', 'groups', 'samples', 'path_queries', 'path_statuses', 'groups_with_numeric_variation', 'mismatches')}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--query', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    validate(args.query.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
