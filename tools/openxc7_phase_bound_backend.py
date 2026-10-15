#!/usr/bin/env python3
"""Build opt-in software phase-bound timing in an isolated exact-part backend."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest


IMPORT_CPP = r'''
void import_xc7_software_phase_contract(Context *ctx)
{
    // Exported metadata is not authorization for a software timing assumption.
    // Replays must provide and validate their contract again.
    for (const auto &entry : ctx->nets) {
        for (const char *key : {"X_VIVADO_PHASE_BOUND_VALID", "X_VIVADO_PHASE_BOUND_MIN_PS", "X_VIVADO_PHASE_BOUND_MAX_PS"})
            entry.second->attrs.erase(ctx->id(key));
    }
    if (!ctx->args.options.count("phase-bound-contract"))
        return;
    if (!ctx->setting<bool>("xilinx/phase-engine-vivado", false))
        log_error("Software phase contract requires phase-engine-vivado=on.\n");
    std::ifstream stream(ctx->args.options["phase-bound-contract"].as<std::string>());
    if (!stream)
        log_error("Cannot read software phase contract.\n");
    std::string input((std::istreambuf_iterator<char>(stream)), std::istreambuf_iterator<char>());
    std::string error;
    auto contract = json11::Json::parse(input, error);
    const std::string scope = "SOFTWARE_PHASE_BOUND_CONTRACT_NOT_HARDWARE_ENFORCED";
    if (!error.empty() || !contract.is_object() || contract["schema"].number_value() != 1 ||
        contract["scope"].string_value() != scope || contract["part"].string_value() != "xc7k480tffg1156-2" ||
        ctx->args.device != "xc7k480tffg1156-2" ||
        contract["runtime_assumption"].string_value() != "WRAPPED_CALIBRATION_RAW_CSR_WRITES_EXCLUDED" ||
        !contract["groups"].is_array() || contract["groups"].array_items().empty())
        log_error("Malformed or incompatible software phase contract.\n");
    auto integer = [&](const json11::Json &value) -> int64_t {
        double x = value.number_value();
        if (!value.is_number() || !std::isfinite(x) || std::abs(x) > 1000000000 || x != std::floor(x))
            log_error("Software phase bound must be a finite integer.\n");
        return int64_t(x);
    };
    auto real_parameter = [&](const CellInfo *cell, const char *key) {
        auto found = cell->params.find(ctx->id(key));
        if (found == cell->params.end())
            log_error("Software phase contract generator parameter missing.\n");
        if (!found->second.is_string)
            return double(found->second.as_int64());
        std::string value = found->second.as_string();
        size_t end = 0;
        double x = 0;
        try { x = std::stod(value, &end); }
        catch (...) { log_error("Malformed software phase generator parameter.\n"); }
        if (end != value.size() || !std::isfinite(x) || x <= 0)
            log_error("Malformed software phase generator parameter.\n");
        return x;
    };
    pool<IdString> seen;
    for (const auto &group : contract["groups"].array_items()) {
        std::string name = group["dynamic_group"].string_value(), root = group["root"].string_value();
        int64_t low = integer(group["min_offset_ps"]), high = integer(group["max_offset_ps"]);
        int64_t vco = integer(group["vco_hz"]);
        if (name.empty() || root.empty() || low > 0 || high < 0 || low > high || high - low > 1000000 || vco <= 0 ||
            !seen.insert(ctx->id(name)).second)
            log_error("Invalid or duplicate software phase group.\n");
        auto generator = ctx->cells.find(ctx->id(name));
        if (generator == ctx->cells.end() || generator->second->type != ctx->id("MMCME2_ADV_MMCME2_ADV"))
            log_error("Software phase group has no matching MMCM.\n");
        const auto *select = generator->second->getPort(id_CLKINSEL);
        if (!select || !select->constant_value.in(id_GND, id_VCC) ||
            !((select->constant_value == id_VCC) ^ bool(int_or_default(generator->second->params, ctx->id("IS_CLKINSEL_INVERTED"), 0))))
            log_error("Software phase contract requires confirmed CLKIN1 selection.\n");
        auto *source = generator->second->getPort(ctx->id("CLKIN1"));
        if (!source || !source->attrs.count(ctx->id("X_VIVADO_CLOCK_VALID")) ||
            !source->attrs.at(ctx->id("X_VIVADO_CLOCK_VALID")).as_int64())
            log_error("Software phase group has unknown source waveform.\n");
        double input_period = double(source->attrs.at(ctx->id("X_VIVADO_CLOCK_PERIOD_NUM_PS")).as_int64()) /
                              source->attrs.at(ctx->id("X_VIVADO_CLOCK_PERIOD_DEN")).as_int64();
        double actual_vco = 1e12 / input_period * real_parameter(generator->second.get(), "CLKFBOUT_MULT_F") /
                            real_parameter(generator->second.get(), "DIVCLK_DIVIDE");
        if (!std::isfinite(actual_vco) || std::abs(actual_vco - vco) > 0.001)
            log_error("Software phase contract VCO differs from actual generator.\n");
        unsigned matches = 0;
        for (const auto &entry : ctx->nets) {
            auto *net = entry.second.get();
            auto dg = net->attrs.find(ctx->id("X_VIVADO_CLOCK_DYNAMIC_GROUP"));
            if (dg == net->attrs.end() || dg->second.as_string() != name)
                continue;
            if (net->attrs.at(ctx->id("X_VIVADO_CLOCK_ROOT")).as_string() != root)
                log_error("Software phase contract root differs from actual waveform.\n");
            net->attrs[ctx->id("X_VIVADO_PHASE_BOUND_VALID")] = Property(1);
            net->attrs[ctx->id("X_VIVADO_PHASE_BOUND_MIN_PS")] = Property(low, 64);
            net->attrs[ctx->id("X_VIVADO_PHASE_BOUND_MAX_PS")] = Property(high, 64);
            ++matches;
        }
        if (!matches)
            log_error("Software phase group has no matching clock waveforms.\n");
        log_info("Conditional SOFTWARE phase group %s: [%lld,%lld] ps, %u clock nets; raw CSR writes excluded, skew/jitter unqualified.\n",
                 name.c_str(), (long long)low, (long long)high, matches);
    }
}
'''

BOUND_RELATION_CPP = r'''
    bool conditional = text(a, "X_VIVADO_CLOCK_DYNAMIC_GROUP") != text(b, "X_VIVADO_CLOCK_DYNAMIC_GROUP");
    Xc7PhaseFraction relative_low(0), relative_high(0);
    if (conditional) {
        auto interval = [&](const NetInfo *net, Xc7PhaseFraction &low, Xc7PhaseFraction &high) {
            if (text(net, "X_VIVADO_CLOCK_DYNAMIC_GROUP").empty()) {
                low = high = Xc7PhaseFraction(0);
                return true;
            }
            auto valid_bound = net->attrs.find(ctx->id("X_VIVADO_PHASE_BOUND_VALID"));
            if (valid_bound == net->attrs.end() || !valid_bound->second.as_int64())
                return false;
            low = Xc7PhaseFraction(net->attrs.at(ctx->id("X_VIVADO_PHASE_BOUND_MIN_PS")).as_int64());
            high = Xc7PhaseFraction(net->attrs.at(ctx->id("X_VIVADO_PHASE_BOUND_MAX_PS")).as_int64());
            return true;
        };
        Xc7PhaseFraction al, ah, bl, bh;
        if (!interval(a, al, ah) || !interval(b, bl, bh)) {
            result.status = "DYNAMIC_RELATIVE_PHASE";
            return result;
        }
        relative_low = bl - ah;
        relative_high = bh - al;
    }
'''


def build(previous: Path, vendor: Path, review: Path, out: Path, workers: int):
    before = json.loads(previous.read_text())
    gold = json.loads(vendor.read_text())
    software = json.loads(review.read_text())
    if before['status'] != 'UNPLACED_PATH_EXPORT_BUILD_PASS_NATIVE_VALIDATION_PENDING':
        raise ValueError('Expected completed path exporter')
    if gold['status'] != 'ALL_18_VENDOR_PHASE_BOUND_SNAPSHOT_PATHS_PASS' or gold['comparison']['mismatches']:
        raise ValueError('Vendor snapshot gate incomplete')
    if software['status'] != 'FOUR_UNKNOWN_PATHS_IDENTIFIED_MAILBOX_CHAIN_AND_HOST_PHASE_BOUNDS_REVIEWED' or software['dynamic_phase']['host_move_checks'] != 25088:
        raise ValueError('Actual software phase contract not reviewed')
    for field in ('binary', 'source_inventory'):
        if describe(before[field]['path']) != before[field]:
            raise ValueError('Previous ' + field + ' changed')
    for field in ('phy_settings', 'firmware_header', 'host_phase_source'):
        item = software['inputs'][field]
        if describe(item['path']) != item:
            raise ValueError('Software contract source changed')
    original = Path(before['source'])
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'helper': describe(__file__),
            'previous': describe(previous), 'vendor_gate': describe(vendor), 'software_review': describe(review), 'workers': workers,
            'scope': 'CONDITIONAL_SOFTWARE_PHASE_BUDGET_NOT_ROUTED_SKEW_JITTER_OR_HARDWARE_PROOF',
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
        p = kernel / 'xc7_phase_budget.h'
        text = p.read_text()
        old = '''    if (text(a, "X_VIVADO_CLOCK_DYNAMIC_GROUP") != text(b, "X_VIVADO_CLOCK_DYNAMIC_GROUP")) {
        result.status = "DYNAMIC_RELATIVE_PHASE";
        return result;
    }'''
        text = replace(text, old, BOUND_RELATION_CPP)
        text = replace(text, '    auto hold = offset.num ? offset - unit : Xc7PhaseFraction(0);', '''    auto hold = offset.num ? offset - unit : Xc7PhaseFraction(0);
    if (conditional && (relative_low.num != 0 || relative_high.num != 0)) {
        auto earliest = offset + relative_low;
        auto latest = offset + relative_high;
        if (earliest.num <= 0 || (latest - unit).num >= 0) {
            result.status = "SOFTWARE_BOUND_INTERVAL_CROSSES_CAPTURE_EDGE";
            return result;
        }
        setup = earliest;
        hold = latest - unit;
    }''')
        text = replace(text, '    result.status = "NOMINAL_COMMON_PHASE_GROUP";',
                       '    result.status = conditional ? "CONDITIONAL_SOFTWARE_PHASE_BOUND" : "NOMINAL_COMMON_PHASE_GROUP";')
        p.write_text(text)
        xilinx = source / 'himbaechel/uarch/xilinx'
        p = xilinx / 'pack.cc'
        text = '#include <cmath>\n' + p.read_text()
        text = replace(text, 'NEXTPNR_NAMESPACE_BEGIN', 'NEXTPNR_NAMESPACE_BEGIN\n' + IMPORT_CPP)
        text = replace(text, '    generate_xc7_clock_waveforms(ctx);', '    generate_xc7_clock_waveforms(ctx);\n    import_xc7_software_phase_contract(ctx);')
        p.write_text(text)
        p = xilinx / 'xilinx.cc'
        p.write_text(replace(p.read_text(), '    return specific;',
                            '    specific.add_options()("phase-bound-contract", po::value<std::string>(), "explicit conditional software phase bounds (not hardware enforced)");\n    return specific;'))
        shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md',
                     source / 'docs/xilinx-porting/11-software-phase-contract.md')
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
            raise RuntimeError('Software phase-bound compilation failed')
        for stage, argv in (('link', link), ('version', [str(out / 'nextpnr-himbaechel'), '--version'])):
            save(stage=stage)
            _, code = run(stage, argv)
            if code:
                raise RuntimeError(stage + ' failed')
        if any(digest(original / name) != sha for name, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='SOFTWARE_PHASE_BOUND_BUILD_PASS_NATIVE_VALIDATION_PENDING', binary=describe(out / 'nextpnr-himbaechel'),
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'vendor', 'review', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.vendor.resolve(), args.review.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
