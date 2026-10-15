#!/usr/bin/env python3
"""Validate physical FF query results and retain explicit routing selections."""
from __future__ import annotations

import argparse
from collections import defaultdict
import csv
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil

from fedora_openxc7 import describe
from openxc7_ff_path_compare import read_arcs


def rows(path):
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def compare(query: Path, out: Path):
    g = json.loads((query / 'manifest.json').read_text())
    if g['status'] != 'ALL_NINE_ACTUAL_ROUTED_FF_PHYSICAL_CONTEXT_QUERIES_COMPLETE_COMPARISON_PENDING' or g['native_exit']:
        raise ValueError('Complete actual native physical query required')
    for item in [g['checkpoint'], *g['outputs'].values(), g['regroup']]:
        if describe(item['path']) != item:
            raise ValueError('Actual query evidence changed')
    regroup = json.loads(Path(g['regroup']['path']).read_text())
    original = Path(regroup['query']['path']).parent
    specification = {r[0]: r for r in json.loads((query / 'specifications.json').read_text())}
    physical = {r['sample']: r for r in rows(query / 'physical.tsv')}
    paths = rows(query / 'paths.tsv')
    if len(specification) != 9 or physical.keys() != specification.keys() or len(paths) != 18:
        raise ValueError('All nine samples and 18 path queries are required')
    arcs = read_arcs(query / 'arcs.tsv')
    old_arcs = read_arcs(original / 'arcs.tsv')
    objects = defaultdict(lambda: defaultdict(dict))
    selected_cells = {value for spec in specification.values() for value in spec[1:3]}
    with (query / 'objects.tsv').open() as stream:
        for r in csv.DictReader(stream, delimiter='\t'):
            if r['object'] in selected_cells or r['property'] == 'IS_USED':
                objects[r['stage']][r['object']][r['property']] = r['value']
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'query': describe(query / 'manifest.json'), 'regroup': g['regroup'], 'checkpoint': g['checkpoint'],
            'helper': describe(__file__), 'hardware_accessed': False, 'live_backend_changed': False,
            'scope': 'ACTUAL_FF_PHYSICAL_PIN_MUX_CONTROL_CLOCK_AND_FANOUT_NOT_UNIVERSAL_MODEL'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        details = {}
        for sid, (_, cell, driver, _) in specification.items():
            arc_checks = {}
            for kind in ('setup', 'hold'):
                now = arcs[(sid, cell, 'C', 'D', kind)]
                before = old_arcs[('reference', cell, 'C', 'D', kind)]
                values = {k: v for k, v in now.items() if k.startswith('DELAY_') or k == 'IS_DISABLED'}
                expected = {k: v for k, v in before.items() if k.startswith('DELAY_') or k == 'IS_DISABLED'}
                if values != expected:
                    raise ValueError('Actual FF raw arc changed: ' + sid)
                arc_checks[kind] = values
            capture_loc = objects[sid][cell]['LOC']
            driver_loc = objects[sid][driver]['LOC']
            used = {role: sorted(n.removeprefix(loc + '/') for n, props in objects[sid].items()
                                 if n.startswith(loc + '/') and props.get('IS_USED') == '1')
                    for role, loc in [('capture', capture_loc), ('driver', driver_loc)]}
            details[sid] = {'physical': physical[sid], 'capture_loc': capture_loc, 'driver_loc': driver_loc,
                            'capture_properties': objects[sid][cell], 'driver_properties': objects[sid][driver],
                            'used_site_pips': used, 'setup_hold_arcs': arc_checks, 'raw_arc_matches': 2}
        compared = []
        for path in paths:
            sid, mode = path['case'], path['mode']
            cell = specification[sid][1]
            if path['count'] != '1' or path['end_pin'] != cell + '/D':
                raise ValueError('Selected actual timing path endpoint differs')
            text = (query / (sid + '-' + mode + '.rpt')).read_text()
            if not path['slack_ns'] or not Decimal(path['slack_ns']).is_finite():
                if not re.search(r'Timing Exception:\s+False\s*Path', text):
                    raise ValueError('Unexplained unconstrained physical sample')
                compared.append({'sample': sid, 'mode': mode, 'status': 'IGNORED_FALSE_PATH'})
                continue
            kind = 'setup' if mode == 'max' else 'hold'
            corner = re.search(r'Path Type:[^\n]*\b(?:Max|Min) at (Fast|Slow) Process Corner', text)
            prefix = 'Setup_' if kind == 'setup' else 'Hold_'
            contributions = [Decimal(v) for name, v in re.findall(r'\(([^()\s]+)\)\s+(-?\d+\.\d+)', text)
                             if name.startswith(prefix)]
            if not corner or len(contributions) != 1:
                raise ValueError('Missing actual physical FF path contribution')
            value = -contributions[0] if kind == 'setup' else contributions[0]
            allowed = {Decimal(v) for k, v in details[sid]['setup_hold_arcs'][kind].items()
                       if k in (f'DELAY_{corner[1].upper()}_MAX_RISE', f'DELAY_{corner[1].upper()}_MAX_FALL')}
            if value not in allowed:
                raise ValueError('Physical FF path contribution differs from raw timing arc')
            compared.append({'sample': sid, 'mode': mode, 'status': 'MATCH', 'check_ns': str(value)})
        (out / 'physical-contexts.json').write_text(json.dumps(details, indent=2) + '\n')
        (out / 'path-comparison.json').write_text(json.dumps(compared, indent=2) + '\n')
        save(status='ALL_NINE_PHYSICAL_FF_CONTEXTS_RAW_ARCS_AND_FINITE_PATHS_MATCH',
             samples=9, raw_arc_matches=18, path_queries=18, mismatches=0,
             carry_group_fanout={sid: int(physical[sid]['data_net_leaf_inputs'])
                                 for sid in ('group_01837_0', 'group_01837_1', 'group_01837_2')},
             outputs={n: describe(out / n) for n in ('physical-contexts.json', 'path-comparison.json')},
             native_import='PENDING_UNIVERSAL_COVERAGE_AND_ELECTRICAL_DEPENDENCE',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
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
    compare(args.query.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
