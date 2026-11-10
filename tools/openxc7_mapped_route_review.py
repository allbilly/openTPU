#!/usr/bin/env python3
"""Review completed full Vivado routing and actual setup/hold/pulse timing."""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

from fedora_openxc7 import describe
from openxc7_mapped_edif import PROFILE


def timing_summary(path):
    lines = Path(path).read_text().splitlines()
    for index, line in enumerate(lines):
        if line.lstrip().startswith('WNS(ns)'):
            fields = lines[index + 2].split()
            if len(fields) != 12:
                raise ValueError('Unexpected global timing summary format')
            names = ['wns_ns', 'tns_ns', 'setup_failing_endpoints', 'setup_total_endpoints',
                     'whs_ns', 'ths_ns', 'hold_failing_endpoints', 'hold_total_endpoints',
                     'wpws_ns', 'tpws_ns', 'pulse_failing_endpoints', 'pulse_total_endpoints']
            return {name: int(value) if name.endswith('endpoints') else float(value)
                    for name, value in zip(names, fields, strict=True)}
    raise ValueError('Global actual timing summary missing')


def route_summary(path):
    data = {}
    for line in Path(path).read_text().splitlines():
        match = re.search(r'# of (.*?)\.\.*\s*:\s*(\d+)\s*:', line)
        if match:
            data[match[1].strip()] = int(match[2])
    if not all(key in data for key in ['routable nets', 'fully routed nets', 'nets with routing errors']):
        raise ValueError('Actual full route status coverage missing')
    return data


def paths(path):
    records = []
    for block in re.split(r'(?=Slack \()', Path(path).read_text()):
        row = {}
        for key, pattern in [('slack_ns', r'Slack\s*\([^)]*\)\s*:\s*([-+\d.]+)ns'),
                             ('source', r'Source:\s*(\S+)'), ('destination', r'Destination:\s*(\S+)'),
                             ('path_group', r'Path Group:\s*(\S+)'),
                             ('data_delay_ns', r'Data Path Delay:\s*([-+\d.]+)ns'),
                             ('logic_delay_ns', r'Data Path Delay:.*?logic\s*([-+\d.]+)ns'),
                             ('route_delay_ns', r'Data Path Delay:.*?route\s*([-+\d.]+)ns'),
                             ('logic_levels', r'Logic Levels:\s*(\d+)')]:
            match = re.search(pattern, block)
            if match:
                row[key] = float(match[1]) if key.endswith('_ns') else int(match[1]) if key == 'logic_levels' else match[1]
        if 'slack_ns' in row:
            records.append(row)
    if len(records) != 20:
        raise ValueError('Full detailed critical path report coverage differs')
    return records


def review(manifest_path: Path, out: Path):
    source = json.loads(manifest_path.read_text())
    statuses = {
        'FULL_MAPPED_VIVADO_ROUTE_COMPLETE_TIMING_AND_IMPORT_SEMANTICS_REVIEW_PENDING': 'implement.exit',
        'FULL_PHYSOPT_REFERENCE_ROUTE_AND_NUMERICAL_TIMING_PASS_IMPORT_CDC_REVIEW_PENDING': 'physopt.exit',
        'FULL_PHYSOPT_REFERENCE_ROUTE_PASS_TIMING_FAIL_REVIEW_REQUIRED': 'physopt.exit',
    }
    if source.get('native_exit') != 0 or source['status'] not in statuses:
        raise ValueError('Actual terminal completed full route required')
    if source['profile'] != PROFILE:
        raise ValueError('Full profile changed')
    for descriptor in source['outputs'].values():
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Completed full route artifact changed')
    root = manifest_path.parent
    if (root / statuses[source['status']]).read_text().strip() != '0':
        raise ValueError('Actual native route exit differs')
    timing = timing_summary(root / 'routed-timing.rpt')
    route = route_summary(root / 'route-status.rpt')
    route_pass = route['routable nets'] == route['fully routed nets'] and route['nets with routing errors'] == 0
    if not route_pass:
        raise ValueError('Complete route has unresolved nets or routing errors')
    with (root / 'synchronizers.tsv').open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    chains = {}
    for row in rows:
        if not row['loc']:
            raise ValueError('Actual synchronizer placement missing')
        chains.setdefault(row['chain'], []).append(row)
    if len(chains) != 2 or any(len(chain) != 3 or len({row['loc'] for row in chain}) != 1 for chain in chains.values()):
        raise ValueError('Two actual three-stage same-slice synchronizers required')
    timing_pass = (timing['wns_ns'] >= 0 and timing['whs_ns'] >= 0 and timing['wpws_ns'] >= 0
                   and all(timing[key] == 0 for key in ['setup_failing_endpoints', 'hold_failing_endpoints', 'pulse_failing_endpoints']))
    checks = {}
    summary_text = (root / 'routed-timing.rpt').read_text()
    for key in ['no_clock', 'unconstrained_internal_endpoints', 'multiple_clock', 'pulse_width_clock']:
        values = [int(value) for value in re.findall(r'checking ' + key + r' \((\d+)\)', summary_text)]
        if not values or any(value != 0 for value in values):
            raise ValueError('Incomplete internal clock coverage: ' + key)
        checks[key] = values
    cdc_rows = []
    for line in (root / 'routed-cdc.rpt').read_text().splitlines():
        tokens = line.split()
        if (tokens and tokens[0] in ['Warning', 'Info', 'Critical'] and len(tokens) >= 8
                and all(value.isdigit() for value in tokens[-5:])):
            counts = list(map(int, tokens[-5:]))
            cdc_rows.append({'severity': tokens[0], 'source_clock': tokens[1], 'destination_clock': tokens[2],
                             'description': ' '.join(tokens[3:-5]), 'endpoints': counts[0], 'safe': counts[1],
                             'unsafe': counts[2], 'unknown': counts[3], 'no_async_reg': counts[4]})
    if not cdc_rows or any(row['endpoints'] != row['safe'] or row['unsafe'] or row['unknown'] or row['no_async_reg']
                           for row in cdc_rows):
        raise ValueError('Full routed CDC safety review failed')
    mailbox_rows = [row for row in cdc_rows if 'jtag_tck' in (row['source_clock'], row['destination_clock'])]
    if len(mailbox_rows) != 2 or any('Max Delay Datapath Only' not in row['description'] for row in mailbox_rows):
        raise ValueError('JTAG mailbox exception scope differs')
    clocks = {}
    for line in (root / 'clocks.rpt').read_text().splitlines():
        tokens = line.split()
        if len(tokens) >= 3 and tokens[0] in ['SYS_CLK', 'jtag_tck', 'u_ld.crg_s7mmcm_clkout',
                                             'u_ld.writeclocks0_outs1', 'u_ld.writeclocks1_outs1']:
            try:
                clocks[tokens[0]] = float(tokens[1])
            except ValueError:
                pass
    expected_periods = {'SYS_CLK': 20.0, 'jtag_tck': 166.667, 'u_ld.crg_s7mmcm_clkout': 10.0,
                        'u_ld.writeclocks0_outs1': 2.5, 'u_ld.writeclocks1_outs1': 2.5}
    if any(abs(clocks.get(name, float('inf')) - period) > 0.000001 for name, period in expected_periods.items()):
        raise ValueError('Original full clock frequency targets changed')
    memory_path = root.parent / 'full-mapped-memory-parameters-20261012T162344Z/manifest.json'
    memory = json.loads(memory_path.read_text())
    if (memory['status'] != 'ALL_5623_MAPPED_MEMORY_CELLS_EXPLICIT_PARAMETERS_AND_KNOWN_INIT_BITS_MATCH'
            or memory['native_exit'] != 0 or memory['profile'] != PROFILE
            or memory['mismatch_count'] != 0 or memory['parameters'] != 105612 or memory['memory_cells'] != 5623):
        raise ValueError('Completed full memory parameter/known-bit review required')
    for descriptor in memory['outputs'].values():
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Complete memory review artifact changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'FULL_REFERENCE_ROUTE_NUMERICAL_TIMING_CLOCKS_CDC_MEMORY_PASS_HARDWARE_PENDING' if timing_pass else
            'FULL_VIVADO_ROUTE_PASS_TIMING_FAIL_FULL_SCOPE_OPTIMIZATION_REQUIRED',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'native_route': describe(manifest_path),
            'helper': describe(__file__), 'profile': PROFILE, 'route': route, 'timing': timing,
            'critical_paths': paths(root / 'routed-paths.rpt'), 'synchronizers': chains,
            'checkpoints': {'placed.dcp': source['outputs'].get('placed.dcp', source['outputs'].get('physopt-placed.dcp', source['outputs'].get('physopt-routed.dcp'))),
                            'routed.dcp': source['outputs']['routed.dcp']},
            'route_pass': route_pass, 'numerical_timing_pass': timing_pass,
            'memory_import_review': describe(memory_path), 'cdc_review': cdc_rows,
            'internal_clock_coverage': checks, 'clock_periods_ns': clocks,
            'protocol_assumption': 'ONE_OUTSTANDING_COMMAND_PAYLOAD_HELD_UNTIL_MATCHING_RESPONSE',
            'hardware_accessed': False, 'live_jobs_changed': False, 'accepted_image': False,
            'scope': 'ACTUAL_FULL_NATIVE_ROUTE_AND_NUMERICAL_TIMING_NOT_HARDWARE_PASS'}
    (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    shutil.copy2(__file__, out / 'helper.py')
    print(json.dumps({'status': info['status'], 'route': route, 'timing': timing}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--route', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    review(args.route.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
