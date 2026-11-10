#!/usr/bin/env python3
"""Build and validate upstream PR81's BUFGCTRL guard in isolated xc7 backends."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_mailbox_sync_check import fixture, CHIPDB


AUDIT = r'''
    const ArchArgs &args = ctx->args;
    if (args.options.count("bufg-route-audit")) {
        std::ofstream audit(args.options["bufg-route-audit"].as<std::string>());
        if (!audit)
            log_error("Cannot open BUFG route policy audit.\n");
        audit << "tile\tpip\tsource\tdestination\tunavailable\tbound_slots\tbound_cells\n";
        for (int tile = 0; tile < ctx->chip_info->tile_insts.ssize(); ++tile) {
            const auto &data = chip_tile_info(ctx->chip_info, tile);
            IdString type_id(data.type_name);
            const std::string &type = type_id.str(ctx);
            if (!boost::starts_with(type, "CLK_BUFG_TOP_R") && !boost::starts_with(type, "CLK_BUFG_BOT_R"))
                continue;
            std::string slots, cells;
            for (int bel = 0; bel < data.bels.ssize(); ++bel) {
                BelId id(tile, bel);
                CellInfo *cell = ctx->getBoundBelCell(id);
                if (!cell || cell->type != id_BUFGCTRL)
                    continue;
                auto site = get_bel_site(id);
                const auto &sd = tile_extra_data(tile)->sites[site.site];
                slots += std::to_string(sd.site_y % 16) + ",";
                cells += cell->name.str(ctx) + "@" + get_site_name(site).str(ctx) + ",";
            }
            for (int pip = 0; pip < data.pips.ssize(); ++pip) {
                const auto &pd = data.pips[pip];
                if (pd.flags != PIP_TILE_ROUTING)
                    continue;
                audit << tile_name(tile) << '\t' << pip << '\t'
                      << IdString(data.wires[pd.src_wire].name).str(ctx) << '\t'
                      << IdString(data.wires[pd.dst_wire].name).str(ctx) << '\t'
                      << int(is_pip_unavail(PipId(tile, pip))) << '\t' << slots << '\t' << cells << '\n';
            }
        }
        audit.flush();
        if (!audit)
            log_error("BUFG route policy audit write failed.\n");
    }
'''


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected source patch anchor: ' + old[:90])
    return text.replace(old, new)


def run(out, name, argv):
    (out / (name + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
    with (out / (name + '.log')).open('w') as log:
        code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
    (out / (name + '.exit')).write_text(str(code) + '\n')
    return code


def build(previous: Path, patch_file: Path, out: Path, workers: int):
    before = json.loads(previous.read_text()); original = Path(before['source'])
    if (before['status'] != 'MAILBOX_DATAPATH_BUILD_PASS_NATIVE_VALIDATION_PENDING'
            or describe(before['binary']['path']) != before['binary']
            or describe(before['source_inventory']['path']) != before['source_inventory']):
        raise ValueError('Verified parent backend changed or did not pass')
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    patch = json.loads(patch_file.read_text())
    if len(patch) != 1 or patch[0]['filename'] != 'himbaechel/uarch/xilinx/xilinx.cc':
        raise ValueError('Unexpected upstream PR 81 file scope')
    addition = '\n'.join(line[1:] for line in patch[0]['patch'].splitlines() if line.startswith('+')) + '\n'
    if 'through_bufgctrl' not in addition or addition.count('return true;') != 1:
        raise ValueError('Unexpected upstream routing guard')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'previous': describe(previous), 'previous_binary': before['binary'], 'patch': describe(patch_file),
            'upstream': 'https://github.com/openXC7/nextpnr/pull/81', 'upstream_commit': 'a17bd29c1270',
            'helper': describe(__file__), 'workers': workers, 'live_full_jobs_changed': False,
            'hardware_accessed': False, 'scope': 'XC7_BUFG_ROUTE_POLICY_NOT_FULL_IMPLEMENTATION_OR_TIMING_PROOF'}

    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def variant(name):
        target = out / name; target.mkdir()
        source = target / 'source'; shutil.copytree(original, source)
        if any(digest(source / n) != sha for n, sha in expected.items()):
            raise ValueError('Parent source copy changed')
        cc = source / 'himbaechel/uarch/xilinx/xilinx.cc'; text = cc.read_text()
        if name == 'fixed':
            anchor = '            if (!has_bound_bufgctrl)\n                return true;\n'
            text = replace_once(text, anchor, anchor + addition)
        anchor = 'void XilinxImpl::postPlace()\n{\n    fixup_placement();\n    ctx->assignArchInfo();\n'
        text = replace_once(text, anchor, anchor + AUDIT)
        text = replace_once(text, '    return specific;', '''    specific.add_options()("bufg-route-audit", po::value<std::string>(), "post-placement actual BUFG pip availability audit");
    return specific;''')
        cc.write_text(text)
        shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/openxc7_router_review.md', source / 'docs/xilinx-porting/14-bufg-route-guard.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (target / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        objects = target / 'input-objects'; objects.mkdir(); link = []; compile_plan = []; reused = []
        template = before['compile_plan'][0]['argv']
        for index, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                obj = objects / (str(index).zfill(3) + '-' + Path(arg).name)
                if Path(arg).name.endswith('xilinx.cc.o'):
                    argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in (('-MF', str(obj) + '.d'), ('-o', str(obj)), ('-c', str(cc))):
                        argv[argv.index(flag) + 1] = value
                    compile_plan.append({'source': str(cc), 'output': str(obj), 'argv': argv})
                else:
                    shutil.copy2(arg, obj)
                    if digest(arg) != digest(obj):
                        raise ValueError('Reused object changed')
                    reused.append({'original': describe(arg), 'copied': describe(obj)})
                link.append(str(obj))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(target / 'link.d'))
            else:
                link.append(arg)
        if len(compile_plan) != 1:
            raise ValueError('Single translation-unit rebuild incomplete')
        link[link.index('-o') + 1] = str(target / 'nextpnr-himbaechel')
        manifest = {'status': 'RUNNING', 'variant': name, 'previous': describe(previous),
                    'source': str(source), 'source_inventory': describe(target / 'source.input.json'),
                    'source_delta': sorted(n for n in updated if updated[n] != expected.get(n)),
                    'compile_plan': compile_plan, 'link_argv': link, 'reused_inputs': reused,
                    'verification_only': name == 'stock', 'upstream_guard_present': name == 'fixed'}
        def checkpoint(**fields):
            manifest.update(fields); (target / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        checkpoint(stage='compile')
        for stage, argv in (('compile', compile_plan[0]['argv']), ('link', link), ('version', [str(target / 'nextpnr-himbaechel'), '--version'])):
            checkpoint(stage=stage)
            code = run(target, stage, argv)
            if code:
                checkpoint(status='FAIL', failed_stage=stage, native_exit=code)
                raise RuntimeError(name + ' ' + stage + ' failed')
        checkpoint(status='BUFG_GUARD_VARIANT_BUILD_PASS_NATIVE_VALIDATION_PENDING',
                   binary=describe(target / 'nextpnr-himbaechel'), completed_utc=datetime.now(timezone.utc).isoformat())
        return name, describe(target / 'manifest.json')

    try:
        save(stage='parallel-isolated-variant-builds')
        print('BUILDING stock/fixed xilinx.cc with up to ' + str(workers) + ' workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            variants = dict(pool.map(variant, ('stock', 'fixed')))
        if (any(digest(original / n) != sha for n, sha in expected.items())
                or describe(before['binary']['path']) != before['binary']):
            raise ValueError('Parent backend changed during isolated build')
        save(status='BUFG_GUARD_BUILD_PAIR_PASS_NATIVE_VALIDATION_PENDING', variants=variants,
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def policy(path):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    result = {(row['tile'], int(row['pip'])): row for row in rows}
    if len(result) != len(rows) or len({r['tile'] for r in rows}) != 2:
        raise ValueError('Complete K480T BUFG tile audit missing or duplicated')
    return result


def through(row):
    source = re.fullmatch(r'CLK_BUFG_BUFGCTRL(\d+)_I[01]', row['source'])
    target = re.fullmatch(r'CLK_BUFG_BUFGCTRL(\d+)_O', row['destination'])
    return source is not None and target is not None


def fasm_check(path):
    configured, driven = set(), []
    for line in path.read_text().splitlines():
        line = line.split('#', 1)[0].strip()
        match = re.fullmatch(r'(CLK_BUFG_(?:TOP|BOT)_R_X\d+Y\d+)\.BUFGCTRL\.BUFGCTRL_X\d+Y(\d+)\.IN_USE', line)
        if match:
            configured.add((match[1], int(match[2]) % 16))
        match = re.fullmatch(r'(CLK_BUFG_(?:TOP|BOT)_R_X\d+Y\d+)\.CLK_BUFG_CK_GCLK\d+\.CLK_BUFG_BUFGCTRL(\d+)_O', line)
        if match:
            driven.append((match[1], int(match[2])))
    if not configured or not driven or any(pair not in configured for pair in driven):
        raise ValueError('FASM global clock spine has an unconfigured buffer')
    return {'configured_slots': len(configured), 'driven_global_spines': len(driven), 'unconfigured_drivers': 0}


def check(backend: Path, out: Path, workers: int, previous_check: Path | None = None):
    before = json.loads(backend.read_text())
    if before['status'] != 'BUFG_GUARD_BUILD_PAIR_PASS_NATIVE_VALIDATION_PENDING':
        raise ValueError('Both immutable guard variants must compile first')
    variants = {}
    for name, descriptor in before['variants'].items():
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Variant manifest changed')
        row = json.loads(Path(descriptor['path']).read_text())
        if describe(row['binary']['path']) != row['binary']:
            raise ValueError('Variant binary changed')
        variants[name] = row
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'helper': describe(__file__), 'workers': workers, 'route_workers': 2, 'chipdb': describe(CHIPDB),
            'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'ACTUAL_K480T_BUFG_POLICY_AND_SMALL_ROUTES_NOT_FULL_BOARD_TIMING_OR_IMAGE_PROOF'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    inherited = {}
    if previous_check:
        prior = json.loads(previous_check.read_text())
        if (prior['status'] != 'UPSTREAM_BUFG_GUARD_ACTUAL_POLICY_AB_AND_TWO_NATIVE_ROUTES_PASS'
                or prior['backend'] != describe(backend) or any(prior['native_results'].values())):
            raise ValueError('Prior native comparison did not pass with this backend')
        copied = {}
        for source in previous_check.parent.iterdir():
            if not source.is_file() or source.name in ('manifest.json', 'helper.py'):
                continue
            copied[source.name] = describe(source)
            shutil.copy2(source, out / source.name)
            if digest(out / source.name) != copied[source.name]['sha256']:
                raise ValueError('Prior completed native output copy changed')
        inherited = prior['native_results']
        info['previous_check'] = describe(previous_check)
        info['copied_completed_outputs'] = copied
    def command(variant, seed, route, bottom=False):
        name = f'{variant}' + ('-bottom' if bottom else '') + f'-seed{seed}' + ('-route' if route else '-place')
        design, contract = fixture()
        if bottom:
            for cell, y in (('core_buffer', 0), ('tck_buffer', 1)):
                design['modules']['sync_probe']['cells'][cell]['attributes']['LOC'] = 'BUFGCTRL_X0Y' + str(y)
        source = out / (name + '.json'); source.write_text(json.dumps(design, separators=(',', ':')) + '\n')
        declaration = out / (name + '.contract.json'); declaration.write_text(json.dumps(contract, indent=2) + '\n')
        xdc = out / 'probe.xdc'
        argv = [variants[variant]['binary']['path'], '--chipdb', CHIPDB, '--device', 'xc7k480tffg1156-2',
                '--json', str(source), '-o', 'xdc=' + str(xdc), '--threads', '8', '--freq', '100', '--seed', str(seed),
                '-o', 'delay-matrix=off', '-o', 'mailbox-sync-contract=' + str(declaration),
                '-o', 'bufg-route-audit=' + str(out / (name + '.policy.tsv')),
                '--write', str(out / (name + '.placed.json'))]
        if route:
            argv += ['--router', 'router2', '-o', 'fasm=' + str(out / (name + '.fasm')),
                     '--report', str(out / (name + '.timing.json'))]
        else:
            argv += ['--no-route']
        return name, argv
    def execute(job):
        name, argv = job
        code = run(out, name, argv)
        if code:
            raise RuntimeError('Native guard case failed: ' + name)
        return name, code
    try:
        (out / 'probe.xdc').write_text('create_clock -period 10 [get_nets {core_clk}]\ncreate_clock -period 166.666667 [get_nets {tck}]\n')
        save(stage='parallel-native-placements', clock_sources='STANDIN_LUTS_NOT_FUNCTIONAL_BOARD_CLOCKS')
        jobs = ([] if previous_check else [command(v, seed, False) for seed in (1, 2) for v in ('stock', 'fixed')])
        jobs += [command(v, 1, False, True) for v in ('stock', 'fixed')]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = inherited | dict(pool.map(execute, jobs))
        comparisons = {}
        bound_tiles = set()
        for case, suffix in [('1', '-seed1'), ('2', '-seed2'), ('bottom', '-bottom-seed1')]:
            old = policy(out / f'stock{suffix}-place.policy.tsv'); new = policy(out / f'fixed{suffix}-place.policy.tsv')
            if old.keys() != new.keys():
                raise ValueError('Stock/fixed routing resources differ')
            changes, unbound = [], []
            for key, row in old.items():
                current = new[key]
                if any(row[field] != current[field] for field in row if field != 'unavailable'):
                    raise ValueError('Stock/fixed placements or routing resource definitions differ')
                if row['bound_slots']:
                    bound_tiles.add(row['tile'])
                if through(row):
                    if current['unavailable'] != '1':
                        raise ValueError('Upstream guard leaves a BUFG route-through usable')
                    slot = int(re.fullmatch(r'CLK_BUFG_BUFGCTRL(\d+)_O', row['destination'])[1])
                    if row['unavailable'] == '0' and slot not in {int(s) for s in row['bound_slots'].split(',') if s}:
                        unbound.append(key)
                elif row['unavailable'] != current['unavailable']:
                    raise ValueError('Guard changes an ordinary clock input/output route')
                if row['unavailable'] != current['unavailable']:
                    changes.append(key)
            if not changes or not unbound:
                raise ValueError('Probe did not reproduce the unconfigured-slot routing gap')
            if case == 'bottom' and {r['bound_cells'] for r in old.values() if r['bound_cells']} != {
                    'core_buffer@BUFGCTRL_X0Y0,tck_buffer@BUFGCTRL_X0Y1,'}:
                raise ValueError('Bottom-tile probe did not retain its requested physical buffer sites')
            comparisons[case] = {'tile_pips': len(old), 'guarded_through_pips': sum(through(r) for r in old.values()),
                                      'changed_availability': len(changes), 'previously_usable_unbound_pips': len(unbound),
                                      'other_policy_changes': 0, 'placements_identical': True}
        if len(bound_tiles) != 2:
            raise ValueError('Positive bound-buffer cases did not exercise both clock tiles')
        save(stage='two-fixed-native-routes', placement_results=results, policy_comparisons=comparisons)
        route_jobs = ([] if previous_check else [command('fixed', seed, True) for seed in (1, 2)])
        route_jobs += [command('fixed', 1, True, True)]
        with ThreadPoolExecutor(max_workers=2) as pool:
            routes = dict(pool.map(execute, route_jobs))
        fasms = {str(seed): fasm_check(out / f'fixed-seed{seed}-route.fasm') for seed in (1, 2)}
        fasms['bottom'] = fasm_check(out / 'fixed-bottom-seed1-route.fasm')
        save(status='UPSTREAM_BUFG_GUARD_ACTUAL_POLICY_AB_BOTH_TILES_AND_THREE_NATIVE_ROUTES_PASS', native_results=results | routes,
             policy_comparisons=comparisons, fasm_comparisons=fasms, full_new_implementation='PENDING',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'policies': comparisons, 'fasms': fasms}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def full_check(backend: Path, native_gate: Path, previous: Path, out: Path):
    b = json.loads(backend.read_text()); g = json.loads(native_gate.read_text()); p = json.loads(previous.read_text())
    pair = json.loads(Path(g['backend']['path']).read_text())
    if (b['variant'] != 'fixed' or b['verification_only'] or not b['upstream_guard_present']
            or b['status'] != 'BUFG_GUARD_VARIANT_BUILD_PASS_NATIVE_VALIDATION_PENDING'
            or describe(b['binary']['path']) != b['binary']
            or describe(g['backend']['path']) != g['backend'] or describe(backend) != pair['variants']['fixed']
            or g['status'] != 'UPSTREAM_BUFG_GUARD_ACTUAL_POLICY_AB_BOTH_TILES_AND_THREE_NATIVE_ROUTES_PASS'
            or any(g['native_results'].values()) or describe(pair['previous']['path']) != p['backend']
            or p['status'] != 'FULL_UNPLACED_MAILBOX_DATAPATH_LIMITS_PASS_ROUTED_NUMERICS_PENDING'):
        raise ValueError('Fixed backend, native gate or full-reference ancestry differs')
    inputs = dict(p['full_inputs'])
    inputs['mailbox-contract'] = p['contract']
    argv = json.loads((previous.parent / 'full.command.json').read_text())
    for arg in argv:
        if arg.startswith('phase-bound-contract='):
            inputs['phase-contract'] = describe(arg.split('=', 1)[1])
    for record in inputs.values():
        if describe(record['path']) != record:
            raise ValueError('Full constrained input changed')
    out.mkdir(parents=True, exist_ok=False)
    argv[0] = b['binary']['path']
    for i, arg in enumerate(argv):
        if '=' in arg and arg.split('=', 1)[0].endswith('-audit'):
            argv[i] = arg.split('=', 1)[0] + '=' + str(out / Path(arg.split('=', 1)[1]).name)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'binary': b['binary'], 'native_gate': describe(native_gate), 'previous_full_analysis': describe(previous),
            'helper': describe(__file__), 'profile': p['profile'], 'full_inputs': inputs,
            'live_full_jobs_changed': False, 'hardware_accessed': False,
            'scope': 'COMPLETE_UNPLACED_DESIGN_INVARIANTS_NOT_FULL_ROUTED_NUMERICAL_TIMING_OR_IMAGE_PROOF'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    try:
        save(stage='full-native-pack-and-analysis')
        code = run(out, 'full', argv); save(native_exit=code)
        if code:
            raise RuntimeError('Complete native pack/analysis failed')
        for name in ('full.clusters.json', 'full.datapath.json'):
            if json.loads((out / name).read_text()) != json.loads((previous.parent / name).read_text()):
                raise ValueError('Complete native cluster/datapath audit changed: ' + name)
        from openxc7_phase_engine_check import domain_rows
        if domain_rows(out / 'full.domains.tsv') != domain_rows(previous.parent / 'full.domains.tsv'):
            raise ValueError('Complete phase budgets changed')
        endpoints = json.loads((out / 'full.datapath.json').read_text())
        if len(endpoints) != 1103:
            raise ValueError('Complete mailbox endpoint coverage changed')
        summary = {'endpoints': len(endpoints), 'phase_budget_changes': 0, 'synchronizer_cluster_changes': 0,
                   'datapath_audit_changes': 0, 'profile_changes': 0, 'geometry': 'UNPLACED_ZERO_DATA_ROUTE',
                   'ff_numerical_values': 'PROVISIONAL_UNCHANGED'}
        save(status='FULL_BUFG_GUARD_PACK_AND_COMPLETE_TIMING_CONSTRAINT_INVARIANTS_PASS', comparison=summary,
             outputs={n: describe(out / n) for n in ('full.domains.tsv', 'full.clusters.json', 'full.datapath.json', 'full.paths.json')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(summary), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def audit_fasm(source: Path, out: Path):
    """Check clock drivers only; this is one gate, not full image qualification."""
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'fasm': describe(source),
            'helper': describe(__file__), 'hardware_accessed': False,
            'scope': 'BUFG_GLOBAL_SPINE_CONFIGURATION_ONLY_NOT_FULL_IMAGE_OR_TIMING_QUALIFICATION'}
    try:
        result = fasm_check(source)
        info.update(status='BUFG_GLOBAL_SPINE_CONFIGURATION_CHECK_PASS', comparison=result)
        print(json.dumps(result), flush=True)
    except Exception as exc:
        info.update(status='FAIL', error=repr(exc)); raise
    finally:
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__); sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build')
    for name in ('previous', 'patch', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    p = sub.add_parser('check')
    for name in ('backend', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    p.add_argument('--previous-check', type=Path)
    p = sub.add_parser('full')
    for name in ('backend', 'native-gate', 'previous', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.set_defaults(workers=8)
    p = sub.add_parser('audit-fasm')
    p.add_argument('--fasm', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.set_defaults(workers=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Use one to eight workers')
    if args.command == 'build':
        build(args.previous.resolve(), args.patch.resolve(), args.out.resolve(), args.workers)
    elif args.command == 'check':
        check(args.backend.resolve(), args.out.resolve(), args.workers,
              args.previous_check.resolve() if args.previous_check else None)
    elif args.command == 'full':
        full_check(args.backend.resolve(), args.native_gate.resolve(), args.previous.resolve(), args.out.resolve())
    else:
        audit_fasm(args.fasm.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
