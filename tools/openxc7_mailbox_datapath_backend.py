#!/usr/bin/env python3
"""Build explicit direct-FF mailbox datapath limits into an isolated backend."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest


TIMING_CPP = r'''
namespace {
std::set<const Context *> xc7_mailbox_validated_contexts;
}
void set_xc7_mailbox_datapath_validation(Context *ctx, bool valid)
{
    if (valid) xc7_mailbox_validated_contexts.insert(ctx);
    else xc7_mailbox_validated_contexts.erase(ctx);
}
namespace {
const CellInfo *xc7_mailbox_destination(Context *ctx, const CellPortKey &port,
                                       const ClockDomainKey &launch, const ClockDomainKey &capture)
{
    if (!xc7_mailbox_validated_contexts.count(ctx))
        return nullptr;
    auto active = ctx->settings.find(ctx->id("xilinx/mailbox-datapath-active"));
    if (active == ctx->settings.end() || !active->second.as_int64())
        return nullptr;
    auto found = ctx->cells.find(port.cell);
    if (found == ctx->cells.end())
        return nullptr;
    const CellInfo *endpoint = nullptr;
    const auto *cell = found->second.get();
    if (port.port == ctx->id("D") && cell->attrs.count(ctx->id("X_MAILBOX_DP_MAX_PS")))
        endpoint = cell;
    else if (port.port == ctx->id("Q") && cell->attrs.count(ctx->id("X_MAILBOX_DP_TARGET")))
        endpoint = ctx->cells.at(ctx->id(cell->attrs.at(ctx->id("X_MAILBOX_DP_TARGET")).as_string())).get();
    if (!endpoint)
        return nullptr;
    auto source = ctx->cells.at(ctx->id(endpoint->attrs.at(ctx->id("X_MAILBOX_DP_SOURCE")).as_string())).get();
    if (launch.edge != RISING_EDGE || capture.edge != RISING_EDGE ||
        launch.clock != source->getPort(ctx->id("CK"))->name || capture.clock != endpoint->getPort(ctx->id("CK"))->name)
        return nullptr;
    const auto *net = endpoint->getPort(ctx->id("D"));
    if (!net || net->driver.cell != source || net->driver.port != ctx->id("Q"))
        log_error("Imported direct mailbox datapath topology changed during implementation.\n");
    return endpoint;
}
} // namespace
'''

IMPORT_CPP = r'''
void set_xc7_mailbox_datapath_validation(Context *ctx, bool valid);
void import_mailbox_datapath_limits(Context *ctx)
{
    set_xc7_mailbox_datapath_validation(ctx, false);
    ctx->settings[ctx->id("xilinx/mailbox-datapath-active")] = Property(0);
    for (auto &entry : ctx->cells)
        for (const char *key : {"X_MAILBOX_DP_MAX_PS", "X_MAILBOX_DP_SOURCE", "X_MAILBOX_DP_TARGET"})
            entry.second->attrs.erase(ctx->id(key));
    if (!ctx->args.options.count("mailbox-datapath-contract")) {
        if (ctx->args.options.count("mailbox-datapath-audit") || ctx->args.options.count("mailbox-datapath-probe-delays"))
            log_error("Mailbox datapath audit/probe requires a contract.\n");
        return;
    }
    if (!ctx->setting<bool>("xilinx/phase-engine-vivado", false))
        log_error("Mailbox datapath contract requires phase-engine-vivado=on.\n");
    std::ifstream stream(ctx->args.options["mailbox-datapath-contract"].as<std::string>());
    if (!stream)
        log_error("Cannot read mailbox datapath contract.\n");
    std::string input((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>()), error;
    auto contract = json11::Json::parse(input, error);
    if (!error.empty() || !contract.is_object() || contract["schema"].number_value() != 1 ||
        contract["part"].string_value() != "xc7k480tffg1156-2" || ctx->args.device != "xc7k480tffg1156-2" ||
        contract["runtime_assumption"].string_value() != "ONE_OUTSTANDING_COMMAND_SOURCE_PAYLOAD_HELD_UNTIL_MATCHING_RESPONSE_IS_RECEIVED" ||
        contract["cell_path_delay_definition"].string_value() != "SOURCE_CLOCK_TO_Q_PLUS_DATA_ROUTE_PLUS_CAPTURE_SETUP_CLOCK_SKEW_AND_JITTER_EXCLUDED" ||
        !contract["payload_bounds"].is_array() || contract["payload_bounds"].array_items().empty())
        log_error("Malformed or incompatible mailbox datapath contract.\n");
    pool<IdString> sources, destinations;
    for (const auto &row : contract["payload_bounds"].array_items()) {
        auto sf = ctx->cells.find(ctx->id(row["source_cell"].string_value()));
        auto df = ctx->cells.find(ctx->id(row["capture_cell"].string_value()));
        if (sf == ctx->cells.end() || df == ctx->cells.end() || sf->second->type != id_SLICE_FFX || df->second->type != id_SLICE_FFX ||
            row["source_port"].string_value() != "Q" || row["capture_port"].string_value() != "D")
            log_error("Mailbox datapath source/capture is not a direct packed FF pair.\n");
        auto *source = sf->second.get(), *dest = df->second.get();
        auto *q = source->getPort(id_Q), *d = dest->getPort(id_D), *sc = source->getPort(id_CK), *dc = dest->getPort(id_CK);
        if (!q || !d || q != d || q->name.str(ctx) != row["source_net"].string_value() ||
            !sc || !dc || sc->name.str(ctx) != row["source_clock"].string_value() || dc->name.str(ctx) != row["capture_clock"].string_value() ||
            int_or_default(source->params, id_IS_C_INVERTED, 0) || int_or_default(dest->params, id_IS_C_INVERTED, 0) ||
            str_or_default(source->attrs, ctx->id("X_ORIG_TYPE"), "") != "FDRE" ||
            str_or_default(dest->attrs, ctx->id("X_ORIG_TYPE"), "") != "FDRE")
            log_error("Mailbox datapath connection, clock or FF mode differs.\n");
        auto root = [&](const NetInfo *net) {
            if (!net->attrs.count(ctx->id("X_VIVADO_CLOCK_VALID")) || !net->attrs.at(ctx->id("X_VIVADO_CLOCK_VALID")).as_int64())
                log_error("Mailbox datapath has an unknown clock root.\n");
            return net->attrs.at(ctx->id("X_VIVADO_CLOCK_ROOT")).as_string();
        };
        if (root(sc) == root(dc))
            log_error("Mailbox datapath-only contract cannot replace related-clock timing.\n");
        auto is_sync_net = [&](const NetInfo *net) {
            if (!net) return false;
            auto tag = net->attrs.find(ctx->id("ASYNC_REG"));
            return tag != net->attrs.end() && tag->second.is_string && tag->second.as_string() == "TRUE";
        };
        if (is_sync_net(q) || is_sync_net(dest->getPort(id_Q)))
            log_error("Mailbox payload limits cannot tag a synchronizer stage.\n");
        unsigned users = 0;
        for (const auto &user : q->users) {
            ++users;
            if (user.cell != dest || user.port != id_D)
                log_error("Mailbox direct source has another consumer.\n");
        }
        if (users != 1 || !sources.insert(source->name).second || !destinations.insert(dest->name).second)
            log_error("Mailbox datapath has duplicate or nonunique source/capture mapping.\n");
        double maximum = row["max_delay_ps"].number_value();
        if (!row["max_delay_ps"].is_number() || !std::isfinite(maximum) || maximum <= 0 || maximum > 1000000000 || maximum != std::floor(maximum))
            log_error("Mailbox datapath maximum must be a positive finite integer.\n");
        dest->attrs[ctx->id("X_MAILBOX_DP_MAX_PS")] = Property(int64_t(maximum), 64);
        dest->attrs[ctx->id("X_MAILBOX_DP_SOURCE")] = source->name.str(ctx);
        source->attrs[ctx->id("X_MAILBOX_DP_TARGET")] = dest->name.str(ctx);
    }
    ctx->settings[ctx->id("xilinx/mailbox-datapath-active")] = Property(1);
    set_xc7_mailbox_datapath_validation(ctx, true);
    log_info("Imported %zu direct mailbox datapath limits; held-payload protocol required, full numerical timing remains unqualified.\n", destinations.size());
}
'''

AUDIT_CPP = r'''
            if (ctx->args.options.count("mailbox-datapath-probe-delays")) {
                std::string value = ctx->args.options["mailbox-datapath-probe-delays"].as<std::string>();
                std::istringstream parser(value);
                int64_t data, source_clock, capture_clock;
                char comma1, comma2, extra;
                if (!(parser >> data >> comma1 >> source_clock >> comma2 >> capture_clock) || comma1 != ',' || comma2 != ',' ||
                    (parser >> extra) || data < 0 || source_clock < 0 || capture_clock < 0 ||
                    data > 1000000 || source_clock > 1000000 || capture_clock > 1000000)
                    log_error("Invalid explicit mailbox probe delays.\n");
                analyser.with_clock_skew = true;
                for (const auto &entry : ctx->cells) {
                    const auto *dest = entry.second.get();
                    if (!dest->attrs.count(ctx->id("X_MAILBOX_DP_MAX_PS")))
                        continue;
                    auto *source = ctx->cells.at(ctx->id(dest->attrs.at(ctx->id("X_MAILBOX_DP_SOURCE")).as_string())).get();
                    analyser.set_route_delay(CellPortKey(dest->name, id_D), DelayPair(data));
                    analyser.set_route_delay(CellPortKey(source->name, id_CK), DelayPair(source_clock));
                    analyser.set_route_delay(CellPortKey(dest->name, id_CK), DelayPair(capture_clock));
                }
                analyser.run(false, false, false, true);
                log_info("Applied SYNTHETIC UNPLACED mailbox data/clock delays for validation only.\n");
            }
            if (ctx->args.options.count("mailbox-datapath-audit")) {
                json11::Json::array rows;
                for (const auto &entry : ctx->cells) {
                    const auto *dest = entry.second.get();
                    if (!dest->attrs.count(ctx->id("X_MAILBOX_DP_MAX_PS")))
                        continue;
                    const auto *source = ctx->cells.at(ctx->id(dest->attrs.at(ctx->id("X_MAILBOX_DP_SOURCE")).as_string())).get();
                    auto sq = ctx->getPortClockingInfo(source, id_Q, 0), ds = ctx->getPortClockingInfo(dest, id_D, 0);
                    rows.push_back(json11::Json::object{
                        {"source", source->name.str(ctx)}, {"capture", dest->name.str(ctx)},
                        {"maximum_ps", double(dest->attrs.at(ctx->id("X_MAILBOX_DP_MAX_PS")).as_int64())},
                        {"source_clock_to_q_ps", double(sq.clockToQ.maxDelay())}, {"capture_setup_ps", double(ds.setup.maxDelay())},
                        {"source_slack_ps", double(analyser.get_setup_slack(CellPortKey(source->name, id_Q)))},
                        {"capture_slack_ps", double(analyser.get_setup_slack(CellPortKey(dest->name, id_D)))},
                        {"source_criticality", double(analyser.get_criticality(CellPortKey(source->name, id_Q)))},
                        {"capture_criticality", double(analyser.get_criticality(CellPortKey(dest->name, id_D)))}});
                }
                std::string filename = ctx->args.options["mailbox-datapath-audit"].as<std::string>();
                if (std::ifstream(filename).good()) log_error("Mailbox datapath audit already exists.\n");
                std::ofstream output(filename);
                output << json11::Json(rows).dump() << '\n';
                output.close();
                if (!output) log_error("Cannot write mailbox datapath audit.\n");
            }
'''


def build(previous: Path, vendor: Path, out: Path, workers: int):
    before = json.loads(previous.read_text())
    gold = json.loads(vendor.read_text())
    if before['status'] != 'MAILBOX_SYNC_PLACEMENT_BUILD_PASS_NATIVE_VALIDATION_PENDING':
        raise ValueError('Expected completed synchronizer backend')
    if gold['status'] != 'ALL_1103_VENDOR_MAILBOX_DATAPATH_ONLY_REQUIREMENTS_PASS_NATIVE_IMPORT_PENDING' or gold['comparison']['payload_paths'] != 1103:
        raise ValueError('Complete vendor datapath gate missing')
    for field in ('binary', 'source_inventory'):
        if describe(before[field]['path']) != before[field]:
            raise ValueError('Previous ' + field + ' changed')
    original = Path(before['source'])
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'helper': describe(__file__),
            'previous': describe(previous), 'vendor_gate': describe(vendor), 'workers': workers,
            'scope': 'DIRECT_MAILBOX_DATAPATH_SEMANTICS_NOT_FULL_NUMERICAL_ROUTE_OR_HARDWARE_QUALIFICATION',
            'hardware_accessed': False, 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / (stage + '.exit')).write_text(str(code) + '\n')
        return stage, code

    def replace(text, old, new):
        if text.count(old) != 1:
            raise ValueError('Unexpected source anchor: ' + old[:100])
        return text.replace(old, new)

    try:
        save(stage='copy-and-patch')
        source = out / 'source'
        shutil.copytree(original, source)
        if any(digest(source / name) != sha for name, sha in expected.items()):
            raise ValueError('Previous source changed')
        kernel = source / 'common/kernel'
        (kernel / 'xc7_mailbox_datapath.h').write_text(TIMING_CPP)
        p = kernel / 'timing.cc'
        text = '#include <set>\n' + p.read_text()
        text = replace(text, '#include "xc7_phase_budget.h"', '#include "xc7_phase_budget.h"\n#include "xc7_mailbox_datapath.h"')
        anchor = '            pdp.second.max_path_length = arr.path_length + req.path_length;'
        text = replace(text, anchor, r'''
            const auto *bound = xc7_mailbox_destination(ctx, p, domains.at(dp.key.launch).key, domains.at(dp.key.capture).key);
            if (bound) {
                auto *source = ctx->cells.at(ctx->id(bound->attrs.at(ctx->id("X_MAILBOX_DP_SOURCE")).as_string())).get();
                auto sq = ctx->getPortClockingInfo(source, ctx->id("Q"), 0);
                auto ds = ctx->getPortClockingInfo(bound, ctx->id("D"), 0);
                auto data_route = ports.at(CellPortKey(bound->name, ctx->id("D"))).route_delay.maxDelay();
                pdp.second.setup_slack = bound->attrs.at(ctx->id("X_MAILBOX_DP_MAX_PS")).as_int64()
                                         - sq.clockToQ.maxDelay() - data_route - ds.setup.maxDelay();
                pdp.second.hold_slack = std::numeric_limits<delay_t>::max();
            }
''' + anchor)
        text = replace(text, '            if (dp.phase_related)\n                pd.worst_setup_slack', '            if (dp.phase_related || bound)\n                pd.worst_setup_slack')
        text = replace(text, '            if (xc7_phase_enabled(ctx) && (!dp.phase_related || dp.worst_setup_slack >= 0))',
                       '            if (xc7_phase_enabled(ctx) && ((!dp.phase_related && !xc7_mailbox_destination(ctx, p, domains.at(dp.key.launch).key, domains.at(dp.key.capture).key)) || dp.worst_setup_slack >= 0))')
        anchor = '    auto clock_pair = std::make_pair(launch.clock, capture.clock);'
        text = replace(text, anchor, '    const auto *datapath_bound = xc7_mailbox_destination(ctx, CellPortKey(ep.cell->name, ep.port), launch, capture);\n' + anchor)
        text = replace(text, '    if (clock_delays.count(clock_pair)) {', '    if (!datapath_bound && clock_delays.count(clock_pair)) {')
        text = replace(text, '    if (with_clock_skew && register_start && register_end && (same_clock || related_clock)) {',
                       '    if (!datapath_bound && with_clock_skew && register_start && register_end && (same_clock || related_clock)) {')
        text = replace(text, '        auto net_delay = DelayPair(ctx->getNetinfoRouteDelay(net, sink));',
                       '        auto net_delay = datapath_bound ? ports.at(CellPortKey(sink)).route_delay : DelayPair(ctx->getNetinfoRouteDelay(net, sink));')
        text = replace(text, '    if (dp.phase_related)\n        report.max_delay = longest_path ? dp.period.minDelay() : dp.phase_hold_offset;',
                       '    if (datapath_bound && longest_path)\n        report.max_delay = datapath_bound->attrs.at(ctx->id("X_MAILBOX_DP_MAX_PS")).as_int64();\n    else if (dp.phase_related)\n        report.max_delay = longest_path ? dp.period.minDelay() : dp.phase_hold_offset;')
        p.write_text(text)
        xilinx = source / 'himbaechel/uarch/xilinx'
        p = xilinx / 'pack.cc'
        text = '#include <sstream>\n' + p.read_text()
        text = replace(text, 'NEXTPNR_NAMESPACE_BEGIN', 'NEXTPNR_NAMESPACE_BEGIN\n' + IMPORT_CPP)
        text = replace(text, '    import_xc7_software_phase_contract(ctx);', '    import_xc7_software_phase_contract(ctx);\n    import_mailbox_datapath_limits(ctx);')
        text = replace(text, '            analyser.setup(false, false, true);', '            analyser.setup(false, false, true);\n' + AUDIT_CPP)
        anchor = '    if (probe == "on") {'
        text = replace(text, anchor, '''    if ((ctx->args.options.count("mailbox-datapath-audit") || ctx->args.options.count("mailbox-datapath-probe-delays")) && probe != "on")
        log_error("Mailbox datapath audit/probe requires explicit phase-analysis-after-pack=on.\\n");
''' + anchor)
        p.write_text(text)
        p = xilinx / 'xilinx.cc'
        text = replace(p.read_text(), '    return specific;', '''    specific.add_options()("mailbox-datapath-contract", po::value<std::string>(), "validated direct FF mailbox datapath-only limits");
    specific.add_options()("mailbox-datapath-audit", po::value<std::string>(), "actual analyser per-endpoint mailbox slack audit");
    specific.add_options()("mailbox-datapath-probe-delays", po::value<std::string>(), "unplaced synthetic data,source-clock,capture-clock ps delays");
    return specific;''')
        p.write_text(text)
        shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md',
                     source / 'docs/xilinx-porting/13-mailbox-datapath-timing.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        objects = out / 'input-objects'
        objects.mkdir()
        link, jobs, reused = [], [], []
        template = before['compile_plan'][0]['argv']
        selected = {'pack.cc.o': 'himbaechel/uarch/xilinx/pack.cc', 'xilinx.cc.o': 'himbaechel/uarch/xilinx/xilinx.cc',
                    'timing.cc.o': 'common/kernel/timing.cc'}
        for i, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                target = objects / (str(i).zfill(3) + '-' + Path(arg).name)
                key = next((key for key in selected if Path(arg).name.endswith(key)), None)
                if key:
                    name = selected.pop(key)
                    argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in (('-MF', str(target) + '.d'), ('-o', str(target)), ('-c', str(source / name))):
                        argv[argv.index(flag) + 1] = value
                    jobs.append({'source': str(source / name), 'output': str(target), 'argv': argv})
                else:
                    shutil.copy2(arg, target)
                    if digest(arg) != digest(target):
                        raise ValueError('Reused object changed')
                    reused.append({'original': describe(arg), 'copied': describe(target)})
                link.append(str(target))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
            else:
                link.append(arg)
        if selected or len(jobs) != 3:
            raise ValueError('Incomplete isolated rebuild')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out / 'source.input.json'),
             source_delta=sorted(name for name in updated if expected.get(name) != updated[name]),
             compile_plan=jobs, link_argv=link, reused_inputs=reused)
        print(f'COMPILING {len(jobs)} affected files with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(lambda item: run('compile-' + str(item[0]), item[1]['argv']), enumerate(jobs)))
        save(compile_results=results)
        if any(results.values()):
            raise RuntimeError('Mailbox datapath compilation failed')
        for stage, argv in (('link', link), ('version', [str(out / 'nextpnr-himbaechel'), '--version'])):
            save(stage=stage)
            _, code = run(stage, argv)
            if code:
                raise RuntimeError(stage + ' failed')
        if any(digest(original / name) != sha for name, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='MAILBOX_DATAPATH_BUILD_PASS_NATIVE_VALIDATION_PENDING', binary=describe(out / 'nextpnr-himbaechel'),
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'vendor', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.vendor.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
