#!/usr/bin/env python3
"""Validate unplaced path provenance, then export unchanged full-design paths."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_phase_engine_check import domain_rows


def check(backend: Path, previous: Path, out: Path, workers: int, full: bool):
    b = json.loads(backend.read_text())
    p = json.loads((previous / 'manifest.json').read_text())
    if b['status'] != 'UNPLACED_PATH_EXPORT_BUILD_PASS_NATIVE_VALIDATION_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Expected unchanged completed path-export backend')
    expected = ('FULL_UNPLACED_PHASE_DOMAIN_ANALYSIS_PASS_ROUTED_SKEW_AND_WHOLE_TIMING_PENDING' if full else
                'ALL_NATIVE_PHASE_ENGINE_CASES_MATCH_VENDOR_EDGES_FULL_DESIGN_PENDING')
    if p['status'] != expected or b['previous'] != p['backend']:
        raise ValueError('Previous validation does not match backend ancestry')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'backend': describe(backend), 'binary': b['binary'], 'previous_check': describe(previous / 'manifest.json'),
            'helper': describe(__file__), 'workers': workers, 'hardware_accessed': False,
            'scope': 'UNPLACED_INTRINSIC_ONLY_NOT_EXHAUSTIVE_CDC_OR_ROUTED_TIMING', 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def command(name, original):
        argv = json.loads((previous / (original + '.command.json')).read_text())
        argv[0] = b['binary']['path']
        if '--write' in argv:
            i = argv.index('--write')
            del argv[i:i + 2]
        for i, value in enumerate(argv):
            if value.startswith('phase-domain-audit='):
                argv[i] = 'phase-domain-audit=' + str(out / (name + '.domains.tsv'))
        return argv + ['-o', 'phase-path-audit=' + str(out / (name + '.paths.json'))]

    def run(job):
        name, argv, rejection = job
        (out / (name + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (name + '.log')).open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / (name + '.exit')).write_text(str(code) + '\n')
        if rejection:
            if code != 125 or rejection not in (out / (name + '.log')).read_text():
                raise ValueError('Expected rejection did not occur: ' + name)
            if name == 'existing-output' and (out / (name + '.paths.json')).read_text() != 'preserve-existing-output\n':
                raise ValueError('Existing export overwritten')
            return name, {'native_exit': code, 'expected_rejection': rejection}
        if code:
            raise RuntimeError('Native export failed: ' + name)
        audit = out / (name + '.domains.tsv')
        old_audit = previous / ('full-phase-domains.tsv' if full else original_names[name] + '.domains.tsv')
        rows = domain_rows(audit)
        if rows != domain_rows(old_audit):
            raise ValueError('Exporter changed nominal budgets: ' + name)
        report = json.loads((out / (name + '.paths.json')).read_text())
        if report['scope'] != 'UNPLACED_INTRINSIC_ONLY_NOT_ROUTED_TIMING':
            raise ValueError('Export has wrong scope')
        pairs = set()
        for path in report['paths']:
            pair = (path['launch'], path['launch_edge'], path['capture'], path['capture_edge'])
            pairs.add(pair)
            if not path['segments'] or pair not in rows:
                raise ValueError('Exported path lacks segments or domain evidence')
            for segment in path['segments']:
                for key in ('from', 'to'):
                    pin = segment[key]
                    if not pin.get('cell') or not pin.get('port') or not pin.get('type') or 'connections' not in pin:
                        raise ValueError('Exported endpoint lacks cell/pin provenance')
        unknown = {pair for pair, value in rows.items() if not value['known'] and pair[0] != pair[2]}
        if not unknown.issubset(pairs):
            raise ValueError('Missing unresolved crossing paths')
        return name, {'native_exit': code, 'domain_pairs': len(rows), 'exported_paths': len(report['paths']),
                      'unresolved_pairs_with_paths': len(unknown), 'audit': describe(audit),
                      'paths': describe(out / (name + '.paths.json'))}

    try:
        if full:
            for item in p['full_inputs'].values():
                if describe(item['path']) != item:
                    raise ValueError('Pinned full input changed')
            save(stage='full-native-intrinsic-path-export', profile=p['profile'], full_inputs=p['full_inputs'])
            original_names = {'full-analysis': 'full-analysis'}
            jobs = [('full-analysis', command('full-analysis', 'full-analysis'), None)]
        else:
            original_names = {name: name for name in ('baseline', 'shifted', 'dynamic-relative-phase', 'unrelated-source', 'missing-source')}
            jobs = [(name, command(name, name), None) for name in original_names]
            argv = command('probe-off', 'baseline')
            argv[argv.index('phase-analysis-after-pack=on')] = 'phase-analysis-after-pack=off'
            jobs.append(('probe-off', argv, 'phase-path-audit requires phase-analysis-after-pack=on'))
            (out / 'existing-output.paths.json').write_text('preserve-existing-output\n')
            jobs.append(('existing-output', command('existing-output', 'baseline'), 'Phase-path audit output already exists'))
            argv = command('invalid-output', 'baseline')
            argv[-1] = 'phase-path-audit=' + str(out / 'missing-directory' / 'paths.json')
            jobs.append(('invalid-output', argv, 'Cannot write unplaced phase-path audit'))
            save(stage='parallel-native-export-validation')
        print(f'RUNNING {len(jobs)} native path exports with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(run, jobs))
        shutil.copy2(__file__, out / 'helper.py')
        save(status='FULL_UNPLACED_UNKNOWN_PATH_EXPORT_PASS_CDC_REVIEW_PENDING' if full else 'ALL_NATIVE_UNPLACED_PATH_EXPORT_CASES_PASS',
             results=results, completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'results': results}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'previous', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    parser.add_argument('--full', action='store_true')
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight workers')
    check(args.backend.resolve(), args.previous.resolve(), args.out.resolve(), args.workers, args.full)


if __name__ == '__main__':
    main()
