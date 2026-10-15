#!/usr/bin/env python3
"""Route the fully reviewed accelerator placement with qualified replay."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
from fedora_openxc7 import describe, digest
from openxc7_full_congestion_placement import PROFILE
from openxc7_bufg_route_guard import fasm_check


def clock_gate(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    clocks = {r['net']: r for r in rows}
    if len(clocks) != len(rows) or len(rows) < 30:
        raise ValueError('Complete restored clock audit required')
    for name, period in [('SYS_CLK', 20000), ('core_clk', 10000), ('tck', 166666)]:
        if name not in clocks:
            raise ValueError('Restored base clock missing: ' + name)
        if any(abs(int(clocks[name][key]) - period) > 1 for key in ('period_min_ps', 'period_max_ps')):
            raise ValueError('Restored full-profile clock differs: ' + name)
    return {'clock_count': len(rows), 'base_clocks': {k: clocks[k] for k in ('SYS_CLK', 'core_clk', 'tck')}}


def domain_gate(path, reference):
    def rows(p):
        with p.open() as stream:
            return sorted(tuple(sorted(row.items())) for row in csv.DictReader(stream, delimiter='\t'))
    actual, expected = rows(path), rows(reference)
    if len(expected) != 18 or actual != expected:
        raise ValueError('Full timing domain pairs or budgets differ from qualified pack')
    known = sum(dict(row)['known'] == '1' for row in actual)
    if known != 16:
        raise ValueError('Full phase-domain coverage differs')
    return {'domain_pairs': 18, 'known': known, 'unknown': 2, 'budgets_identical': True}


def route(review, fixture, timing_reference, out):
    r, f = (json.loads(p.read_text()) for p in (review, fixture))
    if r['status'] != 'ALL_FULL_NATIVE_LOGICAL_CELLS_PHYSICAL_ASSIGNMENTS_AND_SYNC_CHAINS_PASS_ROUTE_TIMING_PENDING':
        raise ValueError('Complete full placement review required')
    if f['status'] != 'PLACED_REPLAY_CLOCKS_MATRIX_CACHE_BINDINGS_AND_NATIVE_ROUTE_PASS_FULL_ROUTE_PENDING':
        raise ValueError('Completed native replay qualification required')
    if f.get('timing_domain_budgets_identical') is not True or f.get('timing_domain_pairs', 0) < 16:
        raise ValueError('Model-enabled timing-domain replay qualification required')
    if r['profile'] != PROFILE or r['cell_count'] != 464200 or r['ff_count'] != 179299:
        raise ValueError('Full accelerator scope differs')
    trial = Path(r['trial']['path'])
    t = json.loads(trial.read_text())
    q = json.loads(timing_reference.read_text())
    if (q['status'] != 'FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS'
            or q['full_inputs'] != t['full_inputs'] or q['comparison']['domain_pairs'] != 18
            or q['comparison']['endpoints'] != 1103):
        raise ValueError('Matching complete full timing-contract reference required')
    domains_reference = q['outputs']['full.domains.tsv']
    candidate = Path(f['candidate']['path'])
    c = json.loads(candidate.read_text())
    if c['parent_binary'] != t['binary'] or c['source_delta'] != ['himbaechel/uarch/xilinx/xilinx.cc']:
        raise ValueError('Replay candidate parent or xc7-only delta differs')
    records = [r['trial'], r['packed'], r['placed'], r['helper'], r['lut_equivalence_helper'],
               r['stream_helper'], *r['outputs'].values(), f['candidate'], c['binary'],
               c['source_inventory'], t['source_proof'], t['chipdb'], *t['full_inputs'].values(),
               describe(timing_reference), domains_reference]
    for case in f['cases'].values():
        records.extend(case.get('outputs', {}).values())
    proof = json.loads(Path(t['source_proof']['path']).read_text())
    inventory = json.loads(Path(c['source_inventory']['path']).read_text())

    def verify():
        if any(describe(x['path']) != x for x in records):
            raise ValueError('Reviewed input, backend, helper or fixture output changed')
        if len(proof['source']) != 31 or any(digest(p) != v for p, v in proof['source'].items()):
            raise ValueError('Original full-design source changed')
        if any(digest(Path(c['source']) / p) != v for p, v in inventory.items()):
            raise ValueError('Candidate source changed')

    verify()
    memory = {line.split(':')[0]: int(line.split()[1]) for line in Path('/proc/meminfo').read_text().splitlines()
              if line.startswith(('MemAvailable:', 'SwapFree:'))}
    if memory['MemAvailable'] < 10 * 1024 * 1024:
        raise ValueError('Full route needs at least 10 GiB currently available memory')
    if memory['SwapFree'] < 2 * 1024 * 1024 and memory['MemAvailable'] < 14 * 1024 * 1024:
        raise ValueError('Full replay needs 14 GiB available RAM when less than 2 GiB swap is free')
    out.mkdir(parents=True, exist_ok=False)
    original_xdc = Path(t['full_inputs']['openxc7.xdc']['path'])
    clock_lines = []
    for line in original_xdc.read_text().splitlines():
        value = line.strip()
        if value.startswith('create_clock '):
            clock_lines.append(line)
        elif value and not value.startswith(('#', 'set_property ')):
            raise ValueError('Unsupported frozen replay XDC command')
    if not clock_lines:
        raise ValueError('Base clocks absent from full XDC')
    clock_xdc = out / 'clock-replay.xdc'
    clock_xdc.write_text('\n'.join(clock_lines) + '\n')
    old = json.loads((trial.parent / 'placement.command.json').read_text())
    argv, i = [c['binary']['path']], 1
    while i < len(old):
        arg = old[i]
        if arg in ('--no-route', '--placer-heap-congestion-spread'):
            i += 1
            continue
        if arg in ('--placer', '--placer-heap-congestion-weight', '--write', '--report'):
            i += 2
            continue
        if arg == '--json':
            argv.extend((arg, r['placed']['path']))
            i += 2
            continue
        if '=' in arg and arg.split('=', 1)[0].endswith('-audit'):
            arg = arg.split('=', 1)[0] + '=' + str(out / Path(arg.split('=', 1)[1]).name)
        argv.append(arg)
        i += 1
    argv.extend(('--no-pack', '--no-place', '-o', 'delay-matrix=' + str(out / 'matrix.txt'),
                 '-o', 'placed-replay-clock-xdc=' + str(clock_xdc),
                 '-o', 'placed-replay-bindings=' + str(out / 'bindings'),
                 '-o', 'clock-constraint-audit=' + str(out / 'clocks.tsv'),
                 '-o', 'bufg-route-audit=' + str(out / 'clock.policy.tsv'),
                 '-o', 'fasm=' + str(out / 'design.raw.fasm'),
                 '--write', str(out / 'routed.json'), '--report', str(out / 'timing.json')))
    if (argv[argv.index('--threads') + 1] != '8' or argv[argv.index('--freq') + 1] != '100.0'
            or '--timing-allow-fail' in argv or '--force' in argv):
        raise ValueError('Full route CPU/clock/failure policy differs')
    (out / 'route.command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'review': describe(review), 'fixture': describe(fixture), 'trial': r['trial'],
            'candidate': describe(candidate), 'binary': c['binary'], 'chipdb': t['chipdb'],
            'placed': r['placed'], 'full_inputs': t['full_inputs'], 'source_proof': t['source_proof'],
            'helper': describe(__file__), 'clock_only_xdc': describe(clock_xdc), 'profile': PROFILE,
            'timing_reference': describe(timing_reference), 'domains_reference': domains_reference,
            'threads_requested': 8, 'allowed_cpus': sorted(os.sched_getaffinity(0)), 'memory_kib': memory,
            'hardware_accessed': False, 'original_jobs_changed': False, 'timing_signoff': False,
            'scope': 'FULL_ACCELERATOR_NATIVE_ROUTE_FROM_REVIEWED_CONGESTION_PLACEMENT',
            'image_ready': False}

    def save(**values):
        info.update(values)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-load-and-route')
        validated = False
        domains_validated = False
        with (out / 'route.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            fields = (Path('/proc') / str(child.pid) / 'stat').read_text().split(') ', 1)[1].split()
            save(native_pid=child.pid, native_start_ticks=int(fields[19]))
            print('FULL_PLACED_REPLAY_ROUTE_STARTED PID ' + str(child.pid), flush=True)
            while child.poll() is None:
                if not validated or not domains_validated:
                    with (out / 'route.log').open('rb') as stream:
                        stream.seek(max(0,(out / 'route.log').stat().st_size - 65536))
                        tail = stream.read().decode(errors='replace')
                    if not validated and 'Placed replay: generated clocks restored.' in tail:
                        try:
                            restored = clock_gate(out / 'clocks.tsv')
                        except Exception:
                            child.terminate()
                            child.wait()
                            (out / 'route.exit').write_text(str(child.returncode) + '\n')
                            raise
                        save(stage='clocks-restored-timing-domain-gate-pending', restored_clock_gate=restored)
                        validated = True
                        print('FULL_PROFILE_RESTORED_CLOCK_GATE_PASS', flush=True)
                    if validated and not domains_validated and 'Nominal phase-domain budgets:' in tail:
                        try:
                            domains = domain_gate(out / 'full.domains.tsv', Path(domains_reference['path']))
                            if 'Imported 1103 direct mailbox datapath limits;' not in tail:
                                raise ValueError('All full-design mailbox limits were not reimported')
                        except Exception:
                            child.terminate()
                            child.wait()
                            (out / 'route.exit').write_text(str(child.returncode) + '\n')
                            raise
                        save(stage='full-native-routing', restored_domain_gate=domains, mailbox_limits_reimported=1103)
                        domains_validated = True
                        print('FULL_PROFILE_RESTORED_DOMAIN_AND_MAILBOX_GATE_PASS', flush=True)
                time.sleep(2)
            code = child.returncode
        (out / 'route.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Full native route exit ' + str(code))
        restored = clock_gate(out / 'clocks.tsv')
        domains = domain_gate(out / 'full.domains.tsv', Path(domains_reference['path']))
        if not domains_validated:
            raise ValueError('Full live timing-domain/mailbox gate did not complete')
        for name in ('routed.json', 'timing.json', 'design.raw.fasm', 'bindings.before.tsv', 'bindings.after.tsv'):
            if not (out / name).is_file() or not (out / name).stat().st_size:
                raise ValueError('Full native output missing: ' + name)
        with (out / 'bindings.before.tsv').open() as stream:
            before_rows = list(csv.DictReader(stream, delimiter='\t'))
        with (out / 'bindings.after.tsv').open() as stream:
            after_rows = list(csv.DictReader(stream, delimiter='\t'))
        before_map = {x['cell']: x['bel'] for x in before_rows}
        after_map = {x['cell']: x['bel'] for x in after_rows}
        if (len(before_rows) != 464198 or len(after_rows) != 464198
                or len(before_map) != 464198 or before_map != after_map):
            raise ValueError('Full native physical binding inventory changed')
        verify()
        save(status='FULL_PLACED_REPLAY_NATIVE_ROUTE_AND_CLOCK_DRIVER_GATE_PASS_IMAGE_TIMING_PENDING',
             restored_clock_gate=restored, physical_assignments=464198,
             restored_domain_gate=domains,
             fasm_clock_driver_gate=fasm_check(out / 'design.raw.fasm'),
             outputs={n: describe(out / n) for n in ('routed.json', 'timing.json', 'design.raw.fasm',
                 'bindings.before.tsv', 'bindings.after.tsv', 'clocks.tsv', 'matrix.txt', 'full.domains.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('review', 'fixture', 'timing-reference', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    a = parser.parse_args()
    route(a.review.resolve(), a.fixture.resolve(), a.timing_reference.resolve(), a.out.resolve())
