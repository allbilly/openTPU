#!/usr/bin/env python3
"""Re-group validated routed FF timing by physical pins without fitting delays."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from fedora_openxc7 import describe


def rows(path):
    # Full-design site-pin lists can exceed csv's default 128 KiB limit.
    csv.field_size_limit(64 * 1024 * 1024)
    with path.open() as stream:
        return list(csv.DictReader(stream, delimiter='\t'))


def pins(value, site):
    return tuple(sorted(p.split('/', 1)[1] for p in value.split() if p.startswith(site + '/')))


def analyze(query: Path, validation: Path, out: Path):
    q = json.loads((query / 'manifest.json').read_text())
    v = json.loads(validation.read_text())
    if (q['status'] != 'ALL_ROUTED_REFERENCE_FF_GROUPS_QUERY_COMPLETE_COMPARISON_PENDING'
            or q['native_exit'] != 0 or v['query'] != describe(query / 'manifest.json')
            or v.get('status') != 'ALL_ROUTED_REFERENCE_FF_GROUPS_AND_FINITE_PATH_CHECKS_MATCH'):
        raise ValueError('Completed immutable FF query and independent comparison required')
    for item in [q['checkpoint'], *q['outputs'].values(), *v['outputs'].values()]:
        if describe(item['path']) != item:
            raise ValueError('Actual reference FF evidence changed')
    sample_rows = rows(query / 'samples.tsv')
    inventory_rows = rows(query / 'inventory.tsv')
    inventory = {r['cell']: r for r in inventory_rows}
    variation = json.loads((validation.parent / 'group-variation.json').read_text())
    samples = {row['sample']: row for row in sample_rows}
    groups = Counter(row['group'] for row in inventory_rows)
    selected = Counter(row['group'] for row in sample_rows)
    if (not sample_rows or len(inventory) != len(inventory_rows)
            or len(samples) != len(sample_rows)
            or len(inventory_rows) != q['ff_count'] or len(groups) != q['groups']
            or len(sample_rows) != q['samples']
            or selected != {key: min(count, q['samples_per_group']) for key, count in groups.items()}
            or any(v[key] != q[key] for key in ('ff_count', 'groups', 'samples'))
            or v['path_queries'] != 2 * len(sample_rows) or v['mismatches'] != 0
            or v['checkpoint'] != q['checkpoint']):
        raise ValueError('Actual complete reference FF inventory/sample scope differs')
    checks = {}
    seen_groups = set()
    for group in variation:
        gid = group['group']
        if gid in seen_groups or gid not in selected:
            raise ValueError('Independent variation grouping is duplicated or unknown')
        seen_groups.add(gid)
        members = 0
        for signature in group['signatures']:
            for sid in signature['samples']:
                if sid in checks or sid not in samples or samples[sid]['group'] != gid:
                    raise ValueError('Independent variation sample coverage differs')
                sample = samples[sid]
                if (sample['cell'] not in inventory
                        or inventory[sample['cell']]['group'] != gid):
                    raise ValueError('Actual FF sample does not match its inventoried group')
                checks[sid] = json.dumps(signature['checks'], sort_keys=True)
                members += 1
        if (members != selected[gid] or group['samples'] != members
                or group['distinct_signatures'] != len(group['signatures'])):
            raise ValueError('Independent variation group sample count differs')
    if seen_groups != selected.keys() or checks.keys() != samples.keys():
        raise ValueError('Complete reference sample coverage differs')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'query': describe(query / 'manifest.json'), 'validation': describe(validation),
            'helper': describe(__file__), 'samples': len(sample_rows),
            'ff_count': len(inventory_rows), 'groups': len(groups),
            'path_queries': v['path_queries'], 'hardware_accessed': False,
            'live_backend_changed': False, 'scope': 'ROUTED_REFERENCE_PHYSICAL_FF_CONTEXT_NOT_UNIVERSAL_TIMING_MODEL'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        variants = {n: defaultdict(list) for n in ('original', 'driver_bel', 'capture_boundary', 'physical_boundaries')}
        context_rows = []
        for sample in sample_rows:
            sid = sample['sample']
            record = inventory[sample['cell']]
            capture = pins(sample['capture_site_pins'], record['loc'])
            driver = pins(sample['driver_site_pins'], record['driver_loc']) if record['driver_loc'] else ()
            base = (record['primitive'], record['is_c_inverted_property'], record['bel'],
                    record['driver_type'], record['driver_port'], record['same_site'])
            additions = {'original': (), 'driver_bel': (record['driver_bel'],),
                         'capture_boundary': (capture,),
                         'physical_boundaries': (record['driver_bel'], capture, driver)}
            for name, extra in additions.items():
                variants[name][base + extra].append((sid, checks[sid]))
            context_rows.append({'sample': sid, 'cell': sample['cell'], 'key': base + additions['physical_boundaries'],
                                 'checks': json.loads(checks[sid])})
        summary, remaining, tables = {}, {}, []
        for name, groups in variants.items():
            varied, repeated, covered = [], 0, 0
            for key, values in groups.items():
                signatures = defaultdict(list)
                for sid, value in values:
                    signatures[value].append(sid)
                if len(values) > 1:
                    repeated += 1
                    covered += len(values)
                row = {'key': key, 'samples': len(values),
                       'signatures': [{'samples': names, 'checks': json.loads(value)} for value, names in signatures.items()]}
                if len(signatures) > 1:
                    varied.append(row)
                if name == 'physical_boundaries':
                    tables.append(row)
            summary[name] = {'groups': len(groups), 'varying_groups': len(varied), 'repeated_groups': repeated,
                             'samples_in_repeated_groups': covered, 'varying_samples': sum(g['samples'] for g in varied)}
            remaining[name] = varied
        if (summary['original']['groups'] != len(variation)
                or summary['original']['varying_groups'] != sum(g['distinct_signatures'] > 1 for g in variation)):
            raise ValueError('Original independently validated grouping was not reproduced')
        (out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
        (out / 'remaining-variation.json').write_text(json.dumps(remaining, indent=2) + '\n')
        (out / 'physical-contexts.json').write_text(json.dumps(tables, indent=2) + '\n')
        (out / 'samples.json').write_text(json.dumps(context_rows, indent=2) + '\n')
        save(status='ALL_REFERENCE_SAMPLES_PHYSICAL_CONTEXT_REGROUP_COMPLETE_MODEL_UNQUALIFIED', summary=summary,
             outputs={n: describe(out / n) for n in ('summary.json', 'remaining-variation.json', 'physical-contexts.json', 'samples.json')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'summary': summary}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('query', 'validation', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    analyze(args.query.resolve(), args.validation.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
