#!/usr/bin/env python3
"""Independently compare vendor FF path contributions with raw timing arcs."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
from decimal import Decimal
import csv
import json
from pathlib import Path
import re
import shutil

from fedora_openxc7 import describe


def read_arcs(path):
    objects = defaultdict(dict)
    with path.open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            key = row['stage'], row['cell'], row['arc']
            if row['property'] in objects[key]:
                raise ValueError('Duplicate vendor property')
            objects[key][row['property']] = row['value']
    result = {}
    for (stage, cell, _), props in objects.items():
        source = props['FROM_PIN'].removeprefix(cell + '/')
        target = props['TO_PIN'].removeprefix(cell + '/')
        key = stage, cell, source, target, props['TYPE']
        if key in result:
            raise ValueError('Ambiguous clock/data arc')
        result[key] = props
    return result


def compare_query(query, expected_status):
    gate = json.loads((query / 'manifest.json').read_text())
    if gate['status'] != expected_status or gate['native_exit'] != 0:
        raise ValueError('Complete native vendor query did not pass')
    for record in gate['outputs'].values():
        if describe(record['path']) != record:
            raise ValueError('Native vendor output changed')
    arcs = read_arcs(query / 'arcs.tsv')
    snapshots = {'mailbox': 'mailbox-after-paths', 'ff-placed': 'ff-after-paths',
                 'ff-unplaced': 'ff-unplaced-after-paths', 'ff-neutral-control': 'ff-neutral-after-paths'}
    records = []
    with (query / 'paths.tsv').open() as stream:
        paths = list(csv.DictReader(stream, delimiter='\t'))
    for row in paths:
        if row['count'] != '1':
            if not row['stage'].endswith('-datapath') or row['mode'] != 'min' or row['count'] != '0':
                raise ValueError('Unexpected missing vendor path')
            records.append({'stage': row['stage'], 'case': row['case'], 'mode': row['mode'], 'ignored_hold': True})
            continue
        report = query / (row['stage'] + '-' + row['case'] + '-' + row['mode'] + '.rpt')
        text = report.read_text()
        ignored_exception = re.search(r'Timing Exception:\s+False\s*Path', text)
        if not row['slack_ns']:
            if (not row['stage'].endswith('-datapath') or row['mode'] != 'min'
                    or not ignored_exception or not re.search(r'Slack:\s+inf\b', text)):
                raise ValueError('Unexpected absent vendor slack: ' + str(report))
            records.append({'stage': row['stage'], 'case': row['case'], 'mode': row['mode'], 'ignored_hold': True})
            continue
        slack = Decimal(row['slack_ns'])
        if not slack.is_finite():
            if not row['stage'].endswith('-datapath') or row['mode'] != 'min' or not ignored_exception:
                raise ValueError('Unexpected unconstrained/nonfinite path')
            records.append({'stage': row['stage'], 'case': row['case'], 'mode': row['mode'], 'ignored_hold': True})
            continue
        match = re.search(r'Path Type:[^\n]*\b(?:Max|Min) at (Fast|Slow) Process Corner', text)
        if not match:
            raise ValueError('Missing real path corner: ' + str(report))
        corner = match[1].upper()
        output_path = row['case'].endswith('-Q')
        tokens = [(m[1], Decimal(m[2])) for m in re.finditer(r'\(([^()\s]+)\)\s+(-?\d+\.\d+)', text)]
        if output_path:
            cell = row['start_pin'].rsplit('/', 1)[0]; pin = 'Q'
            choices = [(tag, value, 'Reg Clk to Q') for tag, value in tokens if tag.startswith('Prop_')]
            limit = 'MAX' if row['mode'] == 'max' else 'MIN'
            sign = 1
        else:
            cell, pin = row['end_pin'].rsplit('/', 1)
            kinds = {'Setup_': 'setup', 'Recov_': 'recovery'} if row['mode'] == 'max' else {'Hold_': 'hold', 'Remov_': 'removal'}
            choices = [(tag, value, kind) for tag, value in tokens for prefix, kind in kinds.items() if tag.startswith(prefix)]
            limit = 'MAX'; sign = -1 if row['mode'] == 'max' else 1
        if len(choices) != 1:
            raise ValueError('Missing/ambiguous FF contribution: ' + str(report))
        tag, reported, kind = choices[0]
        snapshot = snapshots.get(row['stage'], row['stage'])
        arc = arcs[(snapshot, cell, 'C', pin, kind)]
        if arc['IS_DISABLED'] != '0':
            raise ValueError('Path uses an explicitly disabled arc')
        reference = {Decimal(arc[key]) for key in (f'DELAY_{corner}_{limit}_RISE', f'DELAY_{corner}_{limit}_FALL') if key in arc}
        if not reference or reported * sign not in reference:
            raise ValueError('Effective FF path and vendor arc disagree: ' + str(report))
        records.append({'stage': row['stage'], 'case': row['case'], 'mode': row['mode'], 'cell': cell, 'pin': pin,
                        'kind': kind, 'corner': corner, 'reported_contribution_ns': str(reported),
                        'check_value_ns': str(reported * sign), 'mismatches': 0})
    return gate, arcs, records


def compare(context, drivers, out):
    cg, ca, cr = compare_query(context, 'ALL_222_VENDOR_FF_CONTEXT_PATH_QUERIES_COMPLETE_COMPARISON_PENDING')
    dg, da, dr = compare_query(drivers, 'ALL_50_CONTROLLED_FF_DRIVER_EXCEPTION_PATH_QUERIES_COMPLETE_COMPARISON_PENDING')
    if cg['ff_gate'] != dg['ff_gate'] or len(cr) != 222 or len(dr) != 50:
        raise ValueError('Context ancestry or full five-mode coverage differs')
    out.mkdir(parents=True, exist_ok=False)
    summary = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
               'context_query': describe(context / 'manifest.json'), 'driver_query': describe(drivers / 'manifest.json'),
               'helper': describe(__file__), 'hardware_accessed': False, 'live_full_jobs_changed': False,
               'scope': 'COMPLETE_FIVE_MODE_PATH_CONTRIBUTIONS_AND_CONTROLLED_DRIVER_EFFECTS_NOT_NATIVE_MODEL_IMPORT'}
    def save(**fields):
        summary.update(fields); (out / 'manifest.json').write_text(json.dumps(summary, indent=2) + '\n')
    try:
        save(stage='controlled-driver-comparison')
        effects = []
        for c in dg['configs'][1::2]:
            cell = c['cell']; profiles = {}
            for stage in dg['stages']:
                selected = {kind: da[(stage, cell, 'C', 'D', kind)] for kind in ('setup', 'hold')}
                profiles[stage] = {kind: {key: value for key, value in arc.items() if key.startswith('DELAY_')}
                                   for kind, arc in selected.items()}
            if profiles['direct-normal'] != profiles['direct-datapath'] or profiles['lut-ff-normal'] != profiles['lut-ff-datapath']:
                raise ValueError('Datapath exception unexpectedly changes intrinsic FF checks')
            if profiles['lut-ff-normal'] != profiles['lut-port-normal']:
                raise ValueError('Immediate LUT output is not the controlled factor')
            if profiles['direct-normal'] == profiles['lut-ff-normal']:
                raise ValueError('Driver-context effect was not reproduced')
            effects.append({'primitive': c['primitive'], 'clock_inverted': c['parameters']['IS_C_INVERTED'], 'cell': cell,
                            'checks': profiles, 'datapath_exception_changes': 0, 'lut_upstream_source_changes': 0,
                            'immediate_driver_changes_checks': True})
        # Update/path extraction never changes the same selected arc data.
        pairs = [('mailbox-loaded', 'mailbox-updated'), ('mailbox-updated', 'mailbox-after-paths'),
                 ('ff-loaded', 'ff-updated'), ('ff-io-constrained', 'ff-after-paths'),
                 ('ff-unplaced', 'ff-unplaced-after-paths'), ('ff-neutral-control', 'ff-neutral-after-paths')]
        for first, second in pairs:
            a = {key[1:]: value for key, value in ca.items() if key[0] == first}
            b = {key[1:]: value for key, value in ca.items() if key[0] == second}
            if a != b:
                raise ValueError('Timing update/path extraction altered an otherwise identical context')
        records = cr + dr
        ignored = sum(r.get('ignored_hold', False) for r in records)
        counts = dict(Counter(r['kind'] for r in records if not r.get('ignored_hold')))
        (out / 'path-comparison.json').write_text(json.dumps(records, indent=2) + '\n')
        (out / 'driver-effects.json').write_text(json.dumps(effects, indent=2) + '\n')
        save(status='ALL_272_VENDOR_FF_PATH_CONTRIBUTIONS_AND_DRIVER_EFFECTS_MATCH',
             path_queries=len(records), finite_contribution_checks=len(records)-ignored, ignored_datapath_holds=ignored,
             contribution_types=counts, mismatches=0, five_mode_driver_effects=len(effects),
             numerical_import='PENDING_SOURCE_AND_PHYSICAL_PIN_CONTEXT_COVERAGE',
             old_85_location_tables='VALID_FOR_ORIGINAL_PORT_DRIVEN_PROBES_INSUFFICIENT_AS_ALL_FF_NATIVE_MODELS',
             outputs={n: describe(out / n) for n in ('path-comparison.json', 'driver-effects.json')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({k: summary[k] for k in ('status','path_queries','finite_contribution_checks','ignored_datapath_holds','contribution_types','mismatches')}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('context', 'drivers', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    args = p.parse_args(); compare(args.context.resolve(), args.drivers.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
