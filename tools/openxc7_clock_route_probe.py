#!/usr/bin/env python3
"""Export dedicated clock reachability without entering the main router."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from fedora_openxc7 import describe, digest
from openxc7_bufg_route_guard import replace_once
from openxc7_route_wire_memory import run
from openxc7_mailbox_sync_check import CHIPDB


START = r'''
    std::ofstream clock_audit;
    if (ctx->args.options.count("clock-route-audit")) {
        clock_audit.open(ctx->args.options.at("clock-route-audit").as<std::string>());
        if (!clock_audit)
            log_error("Cannot open dedicated clock audit.\n");
        clock_audit << "net\tsource_cell\tsource_port\tsource_site\tsink_cell\tsink_port\tsink_site\tsource_wire\tsink_wire\tsource_downhill\tsource_available\tdedicated_found\tvisited\n";
    }
'''

FORWARD = r'''
    if (clock_audit.is_open()) {
        const std::string prefix = ctx->args.options.at("clock-route-audit").as<std::string>();
        std::ofstream forward(prefix + ".forward.tsv"), blocked(prefix + ".blocked.tsv");
        if (!forward || !blocked)
            log_error("Cannot open forward clock diagnostics.\n");
        forward << "cell\tport\tsite\tmode\tvisited\tlimited\ttargets\n";
        blocked << "cell\tport\tpip\tsource\tdestination\tflags\tpip_config\n";
        for (auto &entry : ctx->nets) {
            NetInfo *net = entry.second.get();
            if (!net->driver.cell || net->users.entries() == 0 ||
                !net->driver.cell->type.in(id_MMCME2_ADV_MMCME2_ADV, id_PLLE2_ADV_PLLE2_ADV))
                continue;
            bool drives_buffer = false;
            for (auto &user : net->users)
                drives_buffer |= user.cell->type == id_BUFGCTRL && user.port.in(id_I0, id_I1);
            if (!drives_buffer)
                continue;
            for (int mode = 0; mode < 3; ++mode) {
                pool<WireId> seen;
                std::queue<WireId> queue;
                std::set<std::string> targets;
                WireId source = ctx->getNetinfoSourceWire(net);
                seen.insert(source);
                queue.push(source);
                while (!queue.empty() && seen.size() < 1000000) {
                    WireId wire = queue.front();
                    queue.pop();
                    for (auto bp : ctx->getWireBelPins(wire))
                        if (ctx->getBelType(bp.bel) == id_BUFGCTRL && bp.pin.in(id_I0, id_I1))
                            targets.insert(get_site_name(get_bel_site(bp.bel)).str(ctx) + "." + bp.pin.str(ctx));
                    for (auto pip : ctx->getPipsDownhill(wire)) {
                        WireId destination = ctx->getPipDstWire(pip);
                        IdString intent = ctx->getWireType(destination);
                        if (intent.in(id_NODE_DOUBLE, id_NODE_HLONG, id_NODE_HQUAD, id_NODE_VLONG, id_NODE_VQUAD,
                                      id_NODE_SINGLE, id_NODE_CLE_OUTPUT, id_NODE_OPTDELAY, id_BENTQUAD, id_DOUBLE,
                                      id_HLONG, id_HQUAD, id_OPTDELAY, id_SINGLE, id_VLONG, id_VLONG12, id_VQUAD))
                            continue;
                        if (mode != 0 && intent == id_PINBOUNCE)
                            continue;
                        if (mode == 2 && is_pip_unavail(pip)) {
                            const auto &pd = chip_pip_info(ctx->chip_info, pip);
                            const auto &extra = *reinterpret_cast<const XlnxPipExtraDataPOD *>(pd.extra_data.get());
                            blocked << net->driver.cell->name.str(ctx) << '\t' << net->driver.port.str(ctx) << '\t'
                                    << ctx->nameOfPip(pip) << '\t' << ctx->nameOfWire(wire) << '\t'
                                    << ctx->nameOfWire(destination) << '\t' << int(pd.flags) << '\t'
                                    << uint32_t(extra.pip_config) << '\n';
                            continue;
                        }
                        if (seen.insert(destination).second)
                            queue.push(destination);
                    }
                }
                std::string list;
                for (auto &target : targets)
                    list += target + ";";
                forward << net->driver.cell->name.str(ctx) << '\t' << net->driver.port.str(ctx) << '\t'
                        << get_site_name(get_bel_site(net->driver.cell->bel)).str(ctx) << '\t' << mode << '\t'
                        << seen.size() << '\t' << int(!queue.empty()) << '\t' << list << '\n';
            }
        }
        forward.flush();
        blocked.flush();
        if (!forward || !blocked)
            log_error("Forward clock diagnostic write failed.\n");
    }
'''

ROW = r'''
            if (clock_audit.is_open()) {
                WireId source_wire = ctx->getNetinfoSourceWire(clk_net);
                int downhill = 0, available = 0;
                for (auto pip : ctx->getPipsDownhill(source_wire)) {
                    ++downhill;
                    if (ctx->checkPipAvail(pip))
                        ++available;
                }
                clock_audit << clk_net->name.str(ctx) << '\t' << clk_net->driver.cell->name.str(ctx) << '\t'
                            << clk_net->driver.port.str(ctx) << '\t'
                            << get_site_name(get_bel_site(clk_net->driver.cell->bel)).str(ctx) << '\t'
                            << usr.cell->name.str(ctx) << '\t' << usr.port.str(ctx) << '\t'
                            << get_site_name(get_bel_site(usr.cell->bel)).str(ctx) << '\t'
                            << ctx->nameOfWire(source_wire) << '\t' << ctx->nameOfWire(sink_wire) << '\t'
                            << downhill << '\t' << available << '\t' << int(dest != WireId()) << '\t'
                            << backtrace.size() << '\n';
            }
'''

END = r'''
    if (clock_audit.is_open()) {
        clock_audit.flush();
        if (!clock_audit)
            log_error("Dedicated clock audit write failed.\n");
        // This intentional diagnostic stop must never be reported as a full route pass.
        log_error("CLOCK_ROUTE_DIAGNOSTIC_COMPLETE: stopped before main routing.\n");
    }
'''


EARLY_LOC = r'''
    if (ctx->args.options.count("clock-loc-contract")) {
        // Clock buffers must be selected from the generator's final explicit location.
        for (auto &entry : ctx->cells) {
            CellInfo *cell = entry.second.get();
            if (!cell->type.in(id_BUFGCTRL, id_BUFG_BUFG, id_BUFHCE_BUFHCE,
                               id_PLLE2_ADV_PLLE2_ADV, id_MMCME2_ADV_MMCME2_ADV,
                               id_MMCM_MMCM_TOP, id_PLL_PLL_TOP) || !cell->attrs.count(id_LOC))
                continue;
            IdString site = ctx->id(cell->attrs.at(id_LOC).as_string());
            BelId target;
            for (auto bel : ctx->getBels()) {
                if (ctx->getBelType(bel) != cell->type)
                    continue;
                if (uarch->get_site_name(uarch->get_bel_site(bel)) == site) {
                    if (target != BelId())
                        log_error("Ambiguous explicit clock LOC for %s.\n", ctx->nameOf(cell));
                    target = bel;
                }
            }
            if (target == BelId())
                log_error("Unsupported explicit clock LOC for %s.\n", ctx->nameOf(cell));
            if (cell->bel != target) {
                if (cell->bel != BelId())
                    ctx->unbindBel(cell->bel);
                if (!ctx->checkBelAvail(target))
                    log_error("Explicit clock LOC is occupied for %s.\n", ctx->nameOf(cell));
                ctx->bindBel(target, cell, STRENGTH_USER);
            }
            log_info("EARLY_CLOCK_LOC|%s|%s\n", ctx->nameOf(cell), site.c_str(ctx));
        }
    }
'''


def build(parent, out):
    b = json.loads(parent.read_text())
    if b['status'] != 'ROUTER_WIRE_MEMORY_VARIANT_BUILD_PASS_NATIVE_VALIDATION_PENDING' or not b['compact_enabled']:
        raise ValueError('Completed compact parent required')
    for key in ('binary', 'source_inventory'):
        if describe(b[key]['path']) != b[key]:
            raise ValueError('Parent backend changed')
    original = Path(b['source'])
    expected = json.loads(Path(b['source_inventory']['path']).read_text())
    if any(digest(original / n) != value for n, value in expected.items()):
        raise ValueError('Parent source changed')
    out.mkdir(parents=True, exist_ok=False)
    source = out / 'source'
    shutil.copytree(original, source)
    cc = source / 'himbaechel/uarch/xilinx/pack_clocking.cc'
    text = cc.read_text()
    text = replace_once(text, 'void XilinxImpl::route_clocks()\n{\n', 'void XilinxImpl::route_clocks()\n{\n' + START + FORWARD)
    text = replace_once(text, '            if (dest == WireId()) {\n                log_info("            failed to find a route using dedicated resources.\\n");',
                        ROW + '            if (dest == WireId()) {\n                log_info("            failed to find a route using dedicated resources.\\n");')
    text = replace_once(text, '#if 0\n    for (auto& net : nets)', END + '#if 0\n    for (auto& net : nets)')
    text = replace_once(text, 'void XC7Packer::preplace_clocking()\n{\n',
                        'void XC7Packer::preplace_clocking()\n{\n' + EARLY_LOC)
    cc.write_text(text)
    option_source = source / 'himbaechel/uarch/xilinx/xilinx.cc'
    option_source.write_text(replace_once(option_source.read_text(), '    return specific;',
        '    specific.add_options()("clock-route-audit", po::value<std::string>(), "dedicated clock diagnostic; stops before main routing");\n'
        '    specific.add_options()("clock-loc-contract", po::value<std::string>()->implicit_value(""), "apply explicit clock LOC before clock preplacement");\n    return specific;'))
    updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
    changed = sorted(n for n in updated if updated[n] != expected.get(n))
    if changed != ['himbaechel/uarch/xilinx/pack_clocking.cc', 'himbaechel/uarch/xilinx/xilinx.cc']:
        raise ValueError('Clock diagnostic changes unrelated source')
    (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
    objects = out / 'input-objects'
    objects.mkdir()
    link, reused, plan = [], [], []
    for index, arg in enumerate(b['link_argv']):
        if arg.endswith(('.o', '.a')) and Path(arg).is_file():
            obj = objects / (f'{index:03d}-' + Path(arg).name)
            shutil.copy2(arg, obj)
            if digest(obj) != digest(arg):
                raise ValueError('Unchanged object copy differs')
            link.append(str(obj))
            if arg.endswith(('pack_clocking.cc.o', 'xilinx.cc.o')):
                argv = [a.replace(str(original), str(source)) for a in b['compile_plan'][0]['argv']
                        if a != '-DOPENXC7_ROUTER_COMPACT_VISITS']
                argv[argv.index('-o') + 1] = str(obj)
                argv[argv.index('-MF') + 1] = str(obj) + '.d'
                translation_unit = cc if arg.endswith('pack_clocking.cc.o') else option_source
                argv[-1] = str(translation_unit)
                plan.append({'source': str(translation_unit), 'output': str(obj), 'argv': argv})
            else:
                reused.append({'original': describe(arg), 'copied': describe(obj)})
        elif arg.startswith('-Wl,--dependency-file='):
            link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
        else:
            link.append(arg)
    if len(plan) != 2:
        raise ValueError('Clock audit and option-registration translation units must rebuild')
    link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'parent': describe(parent),
            'source': str(source), 'source_inventory': describe(out / 'source.input.json'), 'source_delta': changed,
            'compile_plan': plan, 'link_argv': link, 'reused_inputs': reused, 'helper': describe(__file__),
            'hardware_accessed': False, 'live_full_jobs_changed': False, 'diagnostic_only': True,
            'scope': 'DEDICATED_CLOCK_REACHABILITY_EXPORT_NOT_COMPLETE_ROUTING'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        print('CLOCK_ROUTE_DIAGNOSTIC_BUILD_STARTED', flush=True)
        save(stage='parallel-compile')
        def compile_one(item):
            index, item = item
            code, elapsed = run(out, 'compile-' + str(index), item['argv'])
            if code:
                raise RuntimeError('Clock diagnostic compilation failed')
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(compile_one, enumerate(plan)))
        for stage, argv in [('link', link), ('version', [str(out / 'nextpnr-himbaechel'), '--version'])]:
            save(stage=stage)
            code, elapsed = run(out, stage, argv)
            if code:
                raise RuntimeError('Clock diagnostic ' + stage + ' failed')
        save(status='CLOCK_ROUTE_DIAGNOSTIC_BUILD_PASS_NATIVE_QUERY_PENDING', binary=describe(out / 'nextpnr-himbaechel'),
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def probe(backend, prototype, out, seed, early_loc=False, chipdb=CHIPDB):
    b = json.loads(backend.read_text())
    p = json.loads((prototype / 'manifest.json').read_text())
    if b['status'] != 'CLOCK_ROUTE_DIAGNOSTIC_BUILD_PASS_NATIVE_QUERY_PENDING' or describe(b['binary']['path']) != b['binary']:
        raise ValueError('Immutable diagnostic backend required')
    for key in ('prototype', 'xdc'):
        if describe(p[key]['path']) != p[key]:
            raise ValueError('Clock prototype changed')
    chipdb = str(Path(chipdb).resolve())
    chipdb_input = describe(chipdb)
    out.mkdir(parents=True, exist_ok=False)
    argv = [b['binary']['path'], '--chipdb', chipdb, '--device', 'xc7k480tffg1156-2', '--json', p['prototype']['path'],
            '-o', 'xdc=' + p['xdc']['path'], '-o', 'delay-matrix=off', '--threads', '8', '--freq', '100', '--seed', str(seed),
            '--router', 'router2', '-o', 'clock-route-audit=' + str(out / 'clocks.tsv'),
            '-o', 'bufg-route-audit=' + str(out / 'clock.policy.tsv')]
    if early_loc:
        argv += ['-o', 'clock-loc-contract']
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'backend': describe(backend),
            'prototype': describe(prototype / 'manifest.json'), 'helper': describe(__file__), 'seed': seed,
            'hardware_accessed': False, 'live_full_jobs_changed': False, 'expected_native_exit': 125,
            'early_clock_loc_enabled': early_loc,
            'chipdb': chipdb_input,
            'scope': 'CLOCK_ONLY_ACTUAL_TOPOLOGY_DIAGNOSTIC_NOT_FULL_ROUTE_OR_FUNCTIONAL_BOARD_IMAGE'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='dedicated-clock-reachability')
        print('CLOCK_ROUTE_DIAGNOSTIC_PROBE_STARTED ' + str(out), flush=True)
        code, elapsed = run(out, 'native', argv)
        if describe(chipdb) != chipdb_input:
            raise ValueError('Clock diagnostic database changed during the query')
        log = (out / 'native.log').read_text()
        if code != 125 or 'CLOCK_ROUTE_DIAGNOSTIC_COMPLETE: stopped before main routing.' not in log:
            raise RuntimeError('Dedicated diagnostic did not terminate at its explicit stop')
        with (out / 'clocks.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        if not rows or any(row['dedicated_found'] not in ('0', '1') for row in rows):
            raise ValueError('Incomplete or malformed dedicated clock audit')
        failed = [row for row in rows if row['dedicated_found'] == '0']
        save(status='DEDICATED_CLOCK_DIAGNOSTIC_COMPLETE_MAIN_ROUTER_NOT_RUN', native_exit=code,
             elapsed_seconds=elapsed, clock_arcs=len(rows), failed_dedicated_arcs=len(failed), failures=failed,
             outputs={name: describe(out / name) for name in ('clocks.tsv', 'clock.policy.tsv', 'clocks.tsv.forward.tsv', 'clocks.tsv.blocked.tsv')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'clock_arcs': len(rows), 'failed_dedicated_arcs': len(failed),
                          'failures': failed}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('build')
    p.add_argument('--parent', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('probe')
    for name in ('backend', 'prototype', 'out'):
        p.add_argument('--' + name, type=Path, required=True)
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--early-loc', action='store_true')
    p.add_argument('--chipdb', type=Path, default=Path(CHIPDB))
    args = parser.parse_args()
    if args.command == 'build':
        build(args.parent.resolve(), args.out.resolve())
    else:
        probe(args.backend.resolve(), args.prototype.resolve(), args.out.resolve(), args.seed, args.early_loc,
              args.chipdb.resolve())


if __name__ == '__main__':
    main()
