#!/usr/bin/env python3
"""Build and compare an isolated upstream router2 visited-state memory backport."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import time

from fedora_openxc7 import describe, digest
from openxc7_bufg_route_guard import fasm_check, policy, replace_once, through
from openxc7_mailbox_sync_check import CHIPDB, fixture


FLAG = 'OPENXC7_ROUTER_COMPACT_VISITS'


def choice(old, new):
    return '#ifdef ' + FLAG + '\n' + new + '\n#else\n' + old + '\n#endif'


def adapt(text):
    old = '        bool visited_fwd = false, visited_bwd = false;\n        float cost_fwd = 0.0, cost_bwd = 0.0;'
    new = ('        static constexpr float NOT_VISITED = std::numeric_limits<float>::max();\n'
           '        float cost_fwd = NOT_VISITED, cost_bwd = NOT_VISITED;')
    text = replace_once(text, old, choice(old, new))
    old = ('            flat_wires[w].visited_fwd = false;\n            flat_wires[w].visited_bwd = false;\n'
           '            flat_wires[w].cost_fwd = 0.0;\n            flat_wires[w].cost_bwd = 0.0;')
    new = '            flat_wires[w].cost_fwd = PerWireData::NOT_VISITED;\n            flat_wires[w].cost_bwd = PerWireData::NOT_VISITED;'
    text = replace_once(text, old, choice(old, new))
    for direction in ('fwd', 'bwd'):
        old = f'''    void set_visited_{direction}(ThreadContext &t, int wire, PipId pip, float cost)
    {{
        auto &wd = flat_wires.at(wire);
        if (!wd.visited_fwd && !wd.visited_bwd)
            t.dirty_wires.push_back(wire);
        wd.pip_{direction} = pip;
        wd.visited_{direction} = true;
        wd.cost_{direction} = cost;
    }}'''
        new = f'''    void set_visited_{direction}(ThreadContext &t, int wire, PipId pip, float cost)
    {{
        // A real cost must never silently alias the unvisited sentinel.
        NPNR_ASSERT(cost != PerWireData::NOT_VISITED);
        auto &wd = flat_wires.at(wire);
        if (wd.cost_fwd == PerWireData::NOT_VISITED && wd.cost_bwd == PerWireData::NOT_VISITED)
            t.dirty_wires.push_back(wire);
        wd.pip_{direction} = pip;
        wd.cost_{direction} = cost;
    }}'''
        text = replace_once(text, old, choice(old, new))
        old = f'        return flat_wires.at(wire).visited_{direction} && flat_wires.at(wire).cost_{direction} <= cost;'
        new = f'        return flat_wires.at(wire).cost_{direction} != PerWireData::NOT_VISITED && flat_wires.at(wire).cost_{direction} <= cost;'
        text = replace_once(text, old, choice(old, new))
    anchor = '        for (auto &net_pair : ctx->nets) {\n            auto *net = net_pair.second.get();\n            auto &nd = nets.at(net->udata);'
    audit = ('        log_info("ROUTER_WIRE_MEMORY|%zu|%zu|%zu|%zu\\n", sizeof(PerWireData), flat_wires.size(),\n'
             '                 flat_wires.capacity(), sizeof(PerWireData) * flat_wires.capacity());\n\n')
    text = replace_once(text, anchor, audit + anchor)
    return text


def run(out, name, argv):
    (out / (name + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
    start = time.monotonic()
    with (out / (name + '.log')).open('w') as log:
        code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
    (out / (name + '.exit')).write_text(str(code) + '\n')
    return code, time.monotonic() - start


def build(previous, upstream, out, workers):
    parent = json.loads(previous.read_text())
    if parent['status'] != 'BUFG_GUARD_VARIANT_BUILD_PASS_NATIVE_VALIDATION_PENDING' or not parent['upstream_guard_present']:
        raise ValueError('Validated guarded parent backend required')
    for key in ('binary', 'source_inventory'):
        if describe(parent[key]['path']) != parent[key]:
            raise ValueError('Parent backend changed')
    original = Path(parent['source'])
    expected = json.loads(Path(parent['source_inventory']['path']).read_text())
    commit = json.loads(upstream.read_text())
    if commit['sha'] != '914e84257dff480b652bd6156e9944441ec3e4ff':
        raise ValueError('Unexpected upstream memory change')
    if any(digest(original / name) != value for name, value in expected.items()):
        raise ValueError('Parent source inventory changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'parent': describe(previous),
            'upstream': describe(upstream), 'helper': describe(__file__), 'workers': workers,
            'hardware_accessed': False, 'live_full_jobs_changed': False, 'headers_changed': False,
            'scope': 'ROUTER2_VISITED_STATE_MEMORY_NOT_NUMERICAL_TIMING_OR_FULL_IMAGE_QUALIFICATION'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def variant(name):
        target = out / name
        target.mkdir()
        source = target / 'source'
        shutil.copytree(original, source)
        cc = source / 'common/route/router2.cc'
        cc.write_text(adapt(cc.read_text()))
        doc = Path(__file__).resolve().parents[1] / 'docs/openxc7_router_review.md'
        shutil.copy2(doc, source / 'docs/xilinx-porting/15-router-wire-memory.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        changed = sorted(n for n in updated if updated[n] != expected.get(n))
        if changed != ['common/route/router2.cc', 'docs/xilinx-porting/15-router-wire-memory.md']:
            raise ValueError('Memory backport changed unrelated source/header')
        (target / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        objects = target / 'input-objects'
        objects.mkdir()
        link, reused, compile_plan = [], [], []
        for index, arg in enumerate(parent['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                obj = objects / (f'{index:03d}-' + Path(arg).name)
                shutil.copy2(arg, obj)
                if digest(obj) != digest(arg):
                    raise ValueError('Unchanged object copy differs')
                link.append(str(obj))
                if arg.endswith('router2.cc.o'):
                    argv = [a.replace(str(original), str(source)) for a in parent['compile_plan'][0]['argv']]
                    argv[argv.index('-o') + 1] = str(obj)
                    argv[argv.index('-MF') + 1] = str(obj) + '.d'
                    argv[-1] = str(cc)
                    if name == 'compact':
                        argv.insert(1, '-D' + FLAG)
                    compile_plan.append({'source': str(cc), 'output': str(obj), 'argv': argv})
                else:
                    reused.append({'original': describe(arg), 'copied': describe(obj)})
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(target / 'link.d'))
            else:
                link.append(arg)
        if len(compile_plan) != 1:
            raise ValueError('One actual router translation unit must rebuild')
        link[link.index('-o') + 1] = str(target / 'nextpnr-himbaechel')
        state = {'status': 'RUNNING', 'variant': name, 'parent': describe(previous), 'source': str(source),
                 'source_inventory': describe(target / 'source.input.json'), 'source_delta': changed,
                 'compile_plan': compile_plan, 'link_argv': link, 'reused_inputs': reused,
                 'compact_enabled': name == 'compact', 'verification_only': name == 'stock',
                 'upstream_guard_present': True}

        def checkpoint(**fields):
            state.update(fields)
            (target / 'manifest.json').write_text(json.dumps(state, indent=2) + '\n')

        for stage, argv in [('compile', compile_plan[0]['argv']), ('link', link),
                            ('version', [str(target / 'nextpnr-himbaechel'), '--version'])]:
            checkpoint(stage=stage)
            code, elapsed = run(target, stage, argv)
            if code:
                checkpoint(status='FAIL', native_exit=code, failed_stage=stage)
                raise RuntimeError(name + ' ' + stage + ' failed')
        checkpoint(status='ROUTER_WIRE_MEMORY_VARIANT_BUILD_PASS_NATIVE_VALIDATION_PENDING',
                   binary=describe(target / 'nextpnr-himbaechel'), completed_utc=datetime.now(timezone.utc).isoformat())
        return name, describe(target / 'manifest.json')

    try:
        save(stage='parallel-isolated-builds')
        print('ROUTER_WIRE_MEMORY_BUILD_STARTED ' + str(out), flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            variants = dict(pool.map(variant, ('stock', 'compact')))
        a = json.loads(Path(json.loads(Path(variants['stock']['path']).read_text())['source_inventory']['path']).read_text())
        b = json.loads(Path(json.loads(Path(variants['compact']['path']).read_text())['source_inventory']['path']).read_text())
        if a != b or describe(parent['binary']['path']) != parent['binary']:
            raise ValueError('A/B sources differ or parent changed')
        save(status='ROUTER_WIRE_MEMORY_BUILD_PAIR_PASS_NATIVE_VALIDATION_PENDING', variants=variants,
             source_equal=True, completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def check(backend, out, workers):
    pair = json.loads(backend.read_text())
    if pair['status'] != 'ROUTER_WIRE_MEMORY_BUILD_PAIR_PASS_NATIVE_VALIDATION_PENDING':
        raise ValueError('Complete isolated A/B build required')
    variants = {}
    for name, descriptor in pair['variants'].items():
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Variant manifest changed')
        state = json.loads(Path(descriptor['path']).read_text())
        if describe(state['binary']['path']) != state['binary']:
            raise ValueError('Variant binary changed')
        variants[name] = state
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'backend': describe(backend), 'helper': describe(__file__), 'route_workers': workers,
            'chipdb': describe(CHIPDB), 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'ACTUAL_XC7K480T_SMALL_ROUTE_AB_AND_MEMORY_NOT_FULL_ROUTE_OR_SPEEDUP_PROOF'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    xdc = out / 'probe.xdc'
    xdc.write_text('create_clock -period 10 [get_nets {core_clk}]\ncreate_clock -period 166.666667 [get_nets {tck}]\n')
    jobs = []
    for seed, bottom in [(1, False), (2, False), (1, True)]:
        for variant in ('stock', 'compact'):
            case = variant + ('-bottom' if bottom else '') + f'-seed{seed}'
            design, contract = fixture()
            if bottom:
                for cell, y in [('core_buffer', 0), ('tck_buffer', 1)]:
                    design['modules']['sync_probe']['cells'][cell]['attributes']['LOC'] = 'BUFGCTRL_X0Y' + str(y)
            source = out / (case + '.json')
            source.write_text(json.dumps(design, separators=(',', ':')) + '\n')
            declaration = out / (case + '.contract.json')
            declaration.write_text(json.dumps(contract, indent=2) + '\n')
            argv = [variants[variant]['binary']['path'], '--chipdb', CHIPDB, '--device', 'xc7k480tffg1156-2',
                    '--json', str(source), '-o', 'xdc=' + str(xdc), '--threads', '8', '--freq', '100', '--seed', str(seed),
                    '--router', 'router2', '-o', 'delay-matrix=off', '-o', 'mailbox-sync-contract=' + str(declaration),
                    '-o', 'bufg-route-audit=' + str(out / (case + '.policy.tsv')),
                    '-o', 'fasm=' + str(out / (case + '.fasm')), '--write', str(out / (case + '.routed.json')),
                    '--report', str(out / (case + '.timing.json'))]
            jobs.append((case, argv))

    def execute(job):
        case, argv = job
        code, elapsed = run(out, case, argv)
        if code:
            raise RuntimeError('Native memory route failed: ' + case)
        log = (out / (case + '.log')).read_text()
        metrics = re.findall(r'ROUTER_WIRE_MEMORY\|(\d+)\|(\d+)\|(\d+)\|(\d+)', log)
        if len(metrics) != 1:
            raise ValueError('Missing or duplicated actual wire-memory metrics')
        size, count, capacity, allocated = map(int, metrics[0])
        if count <= 0 or capacity < count or allocated != size * capacity:
            raise ValueError('Actual wire-memory geometry is inconsistent')
        return case, {'native_exit': code, 'elapsed_seconds': elapsed, 'struct_bytes': size,
                      'wire_count': count, 'capacity': capacity, 'allocated_bytes': allocated}

    try:
        save(stage='native-same-seed-routing')
        print('ROUTER_WIRE_MEMORY_NATIVE_CHECK_STARTED ' + str(out), flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(execute, jobs))
        comparisons = {}
        tiles = set()
        for suffix in ['-seed1', '-seed2', '-bottom-seed1']:
            a, b = 'stock' + suffix, 'compact' + suffix
            old, new = results[a], results[b]
            if old['wire_count'] != new['wire_count'] or old['capacity'] != new['capacity'] or new['struct_bytes'] >= old['struct_bytes']:
                raise ValueError('Compact state does not reduce the same native wire table')
            for extension in ('.fasm', '.routed.json'):
                if digest(out / (a + extension)) != digest(out / (b + extension)):
                    raise ValueError('Same-seed native routed output differs: ' + extension)
            pa, pb = policy(out / (a + '.policy.tsv')), policy(out / (b + '.policy.tsv'))
            if pa != pb or any(row['unavailable'] != '1' for row in pb.values() if through(row)):
                raise ValueError('Retained clock routing policy changed')
            tiles |= {row['tile'] for row in pb.values() if row['bound_slots']}
            comparisons[suffix] = {'fasm_equal': True, 'routed_netlist_equal': True, 'clock_policy_equal': True,
                                   'fasm_clock_driver_gate': fasm_check(out / (b + '.fasm')),
                                   'struct_bytes_saved': old['struct_bytes'] - new['struct_bytes'],
                                   'allocated_bytes_saved': old['allocated_bytes'] - new['allocated_bytes']}
        if len(tiles) != 2:
            raise ValueError('Both actual clock tiles were not exercised')
        save(status='ALL_SIX_NATIVE_MEMORY_ROUTES_AND_EXACT_OUTPUT_AB_PASS', results=results, comparisons=comparisons,
             speedup='NOT_ESTABLISHED_BY_SMALL_CASES', full_new_route='PENDING',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'comparisons': comparisons}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build')
    for name in ('previous', 'upstream', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    p = sub.add_parser('check')
    for name in ('backend', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--workers', type=int, default=2)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Use one to eight workers')
    if args.command == 'build':
        build(args.previous.resolve(), args.upstream.resolve(), args.out.resolve(), args.workers)
    else:
        check(args.backend.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
