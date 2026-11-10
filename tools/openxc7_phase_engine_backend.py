#!/usr/bin/env python3
"""Build isolated, opt-in nominal setup/hold clock-edge timing integration."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_clock_family_backend import CPP as WAVEFORM_CPP


FRACTION_CPP = WAVEFORM_CPP[WAVEFORM_CPP.index('struct Xc7ClockFraction'):WAVEFORM_CPP.index('struct Xc7ClockWaveform')].replace('Xc7ClockFraction', 'Xc7PhaseFraction')
RELATION_CPP = r'''
namespace {
bool xc7_phase_enabled(Context *ctx)
{
    return ctx->setting<bool>("xilinx/phase-engine-vivado", false);
}

struct Xc7PhaseRelation
{
    bool known = false;
    delay_t setup = 0, hold = 0;
    const char *status = "UNKNOWN_WAVEFORM";
};

Xc7PhaseRelation xc7_phase_relation(Context *ctx, const ClockDomainKey &launch, const ClockDomainKey &capture)
{
    Xc7PhaseRelation result;
    if (launch.is_async() || capture.is_async()) {
        result.status = "ASYNCHRONOUS_ENDPOINT";
        return result;
    }
    auto l = ctx->nets.find(launch.clock), c = ctx->nets.find(capture.clock);
    if (l == ctx->nets.end() || c == ctx->nets.end())
        return result;
    const NetInfo *a = l->second.get(), *b = c->second.get();
    IdString valid = ctx->id("X_VIVADO_CLOCK_VALID");
    if (!a->attrs.count(valid) || !b->attrs.count(valid) || !a->attrs.at(valid).as_int64() || !b->attrs.at(valid).as_int64())
        return result;
    auto text = [&](const NetInfo *net, const char *key) {
        auto found = net->attrs.find(ctx->id(key));
        if (found == net->attrs.end() || !found->second.is_string)
            log_error("Missing or malformed nominal clock metadata.\n");
        return found->second.as_string();
    };
    if (text(a, "X_VIVADO_CLOCK_ROOT") != text(b, "X_VIVADO_CLOCK_ROOT")) {
        result.status = "UNRELATED_SOURCES";
        return result;
    }
    if (text(a, "X_VIVADO_CLOCK_DYNAMIC_GROUP") != text(b, "X_VIVADO_CLOCK_DYNAMIC_GROUP")) {
        result.status = "DYNAMIC_RELATIVE_PHASE";
        return result;
    }
    auto value = [&](const NetInfo *net, const char *quantity) {
        auto num = ctx->idf("X_VIVADO_CLOCK_%s_NUM_PS", quantity);
        auto den = ctx->idf("X_VIVADO_CLOCK_%s_DEN", quantity);
        if (!net->attrs.count(num) || !net->attrs.count(den) || !net->attrs.at(num).is_fully_def() || !net->attrs.at(den).is_fully_def())
            log_error("Missing or undefined nominal clock fraction.\n");
        return Xc7PhaseFraction(net->attrs.at(num).as_int64(), net->attrs.at(den).as_int64());
    };
    auto ap = value(a, "PERIOD"), bp = value(b, "PERIOD");
    if (ap.num <= 0 || bp.num <= 0)
        log_error("Invalid nominal clock period.\n");
    auto gcd = [](__int128 x, __int128 y) {
        while (y) { __int128 rem = x % y; x = y; y = rem; }
        return x;
    };
    auto unit = Xc7PhaseFraction::wide(gcd(__int128(ap.num) * bp.den, __int128(bp.num) * ap.den), __int128(ap.den) * bp.den);
    auto ae = value(a, "PHASE"), be = value(b, "PHASE");
    if (launch.edge == FALLING_EDGE) ae = ae + value(a, "HIGH");
    if (capture.edge == FALLING_EDGE) be = be + value(b, "HIGH");
    auto difference = be - ae;
    __int128 denominator = __int128(difference.den) * unit.num;
    __int128 numerator = __int128(difference.num) * unit.den;
    __int128 remainder = numerator % denominator;
    if (remainder < 0) remainder += denominator;
    auto offset = Xc7PhaseFraction::wide(remainder, __int128(difference.den) * unit.den);
    auto setup = offset.num ? offset : unit;
    auto hold = offset.num ? offset - unit : Xc7PhaseFraction(0);
    // Minimum setup allowance and latest hold edge are conservative when the
    // exact edge lies between integer picoseconds. Never round before GCD.
    result.setup = setup.num / setup.den;
    result.hold = hold.num / hold.den; // negative division truncates toward zero
    result.known = true;
    result.status = "NOMINAL_COMMON_PHASE_GROUP";
    return result;
}
} // namespace
'''


SETUP_CPP = r'''
    if (xc7_phase_enabled(ctx)) {
        unsigned known = 0, unknown = 0;
        std::ofstream audit;
        auto audit_setting = ctx->settings.find(ctx->id("xilinx/phase-domain-audit"));
        std::string path = audit_setting == ctx->settings.end() ? "" : audit_setting->second.as_string();
        if (!path.empty() && !std::ifstream(path).good()) {
            audit.open(path);
            if (!audit)
                log_error("Cannot create nominal phase-domain audit.\n");
            audit << "launch\tlaunch_edge\tcapture\tcapture_edge\tknown\tsetup_budget_ps\thold_edge_ps\tstatus\n";
        }
        for (auto &dp : domain_pairs) {
            const auto &launch = domains.at(dp.key.launch).key;
            const auto &capture = domains.at(dp.key.capture).key;
            auto relation = xc7_phase_relation(ctx, launch, capture);
            dp.phase_related = relation.known;
            dp.phase_hold_offset = relation.hold;
            dp.period = DelayPair(relation.known ? relation.setup : 0);
            relation.known ? ++known : ++unknown;
            if (audit)
                audit << launch.clock.str(ctx) << '\t' << (launch.edge == RISING_EDGE ? "rising" : "falling")
                      << '\t' << capture.clock.str(ctx) << '\t' << (capture.edge == RISING_EDGE ? "rising" : "falling")
                      << '\t' << relation.known << '\t' << relation.setup << '\t' << relation.hold
                      << '\t' << relation.status << '\n';
        }
        if (audit.is_open()) {
            audit.flush();
            if (!audit)
                log_error("Phase-domain audit write failed.\n");
        }
        log_info("Nominal phase-domain budgets: %u known, %u unknown; routed skew and full timing remain unqualified.\n", known, unknown);
    }
'''


def build(previous, vendor_gate, out, workers):
    before = json.loads(previous.read_text()); gold = json.loads(vendor_gate.read_text())
    if gold['status'] != 'ALL_40_VENDOR_REGISTER_EDGE_RELATIONS_MATCH_EXACT_ARITHMETIC_ENGINE_PENDING' or gold['comparison']['mismatches']:
        raise ValueError('Actual vendor register-edge gate did not pass')
    if describe(before['binary']['path']) != before['binary'] or describe(before['source_inventory']['path']) != before['source_inventory']:
        raise ValueError('Verified waveform backend changed')
    original = Path(before['source']); expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'previous': describe(previous),
            'previous_binary': before['binary'], 'vendor_gate': describe(vendor_gate), 'helper': describe(__file__), 'workers': workers,
            'scope': 'NOMINAL_PHASE_EDGE_TIMING_NOT_ROUTED_SKEW_OR_FULL_BOARD_QUALIFICATION',
            'numerical_timing': 'NOT_QUALIFIED', 'hardware_accessed': False, 'live_full_route_changed': False}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out / (stage + '.exit')).write_text(str(result.returncode) + '\n')
        return stage, result.returncode
    def replace(text, old, new):
        if text.count(old) != 1: raise ValueError('Unexpected source anchor: ' + old[:100])
        return text.replace(old, new)
    try:
        save(stage='copy-and-patch'); source = out / 'source'; shutil.copytree(original, source)
        if any(digest(source / n) != sha for n, sha in expected.items()): raise ValueError('Copied source differs')
        kernel = source / 'common/kernel'; xilinx = source / 'himbaechel/uarch/xilinx'
        (kernel / 'xc7_phase_budget.h').write_text('namespace {\n' + FRACTION_CPP + '}\n' + RELATION_CPP)
        p = kernel / 'timing.h'; text = p.read_text()
        text = replace(text, '        DelayPair period{0};', '        DelayPair period{0};\n        delay_t phase_hold_offset = 0;\n        bool phase_related = false;')
        p.write_text(text)
        p = kernel / 'timing.cc'; text = p.read_text()
        text = '#include <numeric>\n#include <fstream>\n#include <cmath>\n' + text
        text = replace(text, 'NEXTPNR_NAMESPACE_BEGIN', 'NEXTPNR_NAMESPACE_BEGIN\n#include "xc7_phase_budget.h"')
        text = replace(text, '    identify_related_domains();', '    identify_related_domains();\n' + SETUP_CPP)
        text = replace(text, '    run(true, update_net_timings, update_histogram, update_crit_paths);',
                       '    run(!ctx->setting<bool>("xilinx/phase-intrinsic-probe", false), update_net_timings, update_histogram, update_crit_paths);')
        text = replace(text, '                const auto &launch = domains.at(capture_id);',
                       '                const auto &launch = domains.at(xc7_phase_enabled(ctx) ? launch_id : capture_id);')
        # Existing insertion-delay convention is retained; this step imports
        # nominal clock edges, not a qualified inter-generator skew model.
        text = replace(text, '            pdp.second.max_path_length = arr.path_length + req.path_length;', '''            if (dp.phase_related) {
                pdp.second.setup_slack += dp.period.minDelay();
                if (!setup_only)
                    pdp.second.hold_slack -= dp.phase_hold_offset;
            }
            pdp.second.max_path_length = arr.path_length + req.path_length;''')
        text = replace(text, '''            if (dp.key.launch == dp.key.capture)
                pd.worst_setup_slack = std::min(pd.worst_setup_slack, dp.period.minDelay() + pdp.second.setup_slack);''',
                       '''            if (dp.phase_related)
                pd.worst_setup_slack = std::min(pd.worst_setup_slack, pdp.second.setup_slack);
            else if (!xc7_phase_enabled(ctx) && dp.key.launch == dp.key.capture)
                pd.worst_setup_slack = std::min(pd.worst_setup_slack, dp.period.minDelay() + pdp.second.setup_slack);''')
        text = replace(text, '            crit = std::min(crit, 1.0f);', '''            if (xc7_phase_enabled(ctx) && (!dp.phase_related || dp.worst_setup_slack >= 0))
                crit = 0;
            crit = std::min(crit, 1.0f);''')
        old = '''                if (launch_id == async_clock_id || (launch_id != capture_id && !related_clocks)) {'''
        new = '''                const auto &dp = domain_pairs.at(dom_pair_id);
                if (launch_id == async_clock_id || (xc7_phase_enabled(ctx) ? !dp.phase_related : (launch_id != capture_id && !related_clocks))) {'''
        text = replace(text, old, new)
        text = replace(text, '                auto hold_slack = arr.value.minDelay() - req.value.maxDelay() + clock_to_clock;',
                       '                auto hold_slack = arr.value.minDelay() - req.value.maxDelay() + clock_to_clock - dp.phase_hold_offset;')
        # Critical-path requirements and duty-dependent same-clock Fmax must
        # report the same budgets used for actual slack.
        anchor = '    auto same_clock = launch.clock == capture.clock;'
        text = replace(text, anchor, anchor + '\n    related_clock |= dp.phase_related;')
        text = replace(text, '    if (related_clock) {\n        delay_t clock_delay = clock_delays.at(clock_pair);',
                       '    if (clock_delays.count(clock_pair)) {\n        delay_t clock_delay = clock_delays.at(clock_pair);')
        # Keep the legacy report calculation but replace its final constraint
        # with the measured nominal edge relationship when it is available.
        anchor = '    return report;'
        text = replace(text, anchor, '''    if (dp.phase_related)
        report.max_delay = longest_path ? dp.period.minDelay() : dp.phase_hold_offset;
'''+anchor)
        anchor = '''        if (!clock_fmax.count(launch.clock) || Fmax < clock_fmax.at(launch.clock).achieved) {'''
        text = replace(text, anchor, '''        if (dp.phase_related && ctx->nets.at(launch.clock)->clkconstr) {
            auto period = ctx->nets.at(launch.clock)->clkconstr->period.minDelay();
            Fmax = (1000 / ctx->getDelayNS(path_delay)) * double(dp.period.minDelay()) / period;
        }
'''+anchor)
        anchor = '''                    if (launch.clock != capture.clock || launch.is_async())
                        continue;

                    float clk_period ='''
        text = replace(text, anchor, '''                    if (xc7_phase_enabled(ctx)) {
                        const auto &pair = domain_pairs.at(domain_pair_id(arr.first, req.first));
                        if (!pair.phase_related)
                            continue;
                        delay_t extra = 0;
                        auto clocks = std::make_pair(launch.clock, capture.clock);
                        if (clock_delays.count(clocks)) extra = clock_delays.at(clocks);
                        delay_t slack = pair.period.minDelay() - (arr.second.value.maxDelay() - req.second.value.minDelay() + extra);
                        slack_histogram[int(ctx->getDelayNS(slack) * 1000)]++;
                        continue;
                    }
                    if (launch.clock != capture.clock || launch.is_async())
                        continue;

                    float clk_period =''')
        p.write_text(text)
        p = xilinx / 'xc7_clock_waveforms.h'; text = p.read_text()
        anchor = '    if (mode == "off") {'
        text = replace(text, anchor, '''    std::string engine = opts.count("phase-engine-vivado") ? opts["phase-engine-vivado"].as<std::string>() : "off";
    if (engine != "on" && engine != "off")
        log_error("phase-engine-vivado must be on or off.\\n");
    if (engine == "on" && mode != "on")
        log_error("Phase engine requires clock-family-vivado=on.\\n");
    if (opts.count("phase-domain-audit") && engine != "on")
        log_error("Phase-domain audit requires phase-engine-vivado=on.\\n");
    ctx->settings[ctx->id("xilinx/phase-engine-vivado")] = Property(engine == "on" ? 1 : 0);
    ctx->settings[ctx->id("xilinx/phase-domain-audit")] = opts.count("phase-domain-audit") ? opts["phase-domain-audit"].as<std::string>() : "";
'''+anchor)
        p.write_text(text)
        p = xilinx / 'xilinx.cc'; text = p.read_text()
        text = replace(text, '    return specific;', '''    specific.add_options()("phase-engine-vivado", po::value<std::string>(), "experimental nominal setup/hold edge budgets: on or off (default off)");
    specific.add_options()("phase-domain-audit", po::value<std::string>(), "actual timing analyser domain-budget audit");
    specific.add_options()("phase-analysis-after-pack", po::value<std::string>(), "intrinsic-only unplaced analyser check: on or off (default off)");
    return specific;''')
        p.write_text(text)
        p = xilinx / 'pack.cc'; text = p.read_text()
        text = '#include "timing.h"\n' + text
        anchor = '    generate_xc7_clock_waveforms(ctx);'
        text = replace(text, anchor, r'''
    if (ctx->args.options.count("clock-family-vivado") && ctx->args.options["clock-family-vivado"].as<std::string>() == "on")
        ctx->assignArchInfo();
''' + anchor + r'''
    std::string probe = ctx->args.options.count("phase-analysis-after-pack") ? ctx->args.options["phase-analysis-after-pack"].as<std::string>() : "off";
    if (probe != "on" && probe != "off")
        log_error("phase-analysis-after-pack must be on or off.\n");
    if (probe == "on") {
        if (!ctx->setting<bool>("xilinx/phase-engine-vivado", false))
            log_error("Post-pack phase probe requires phase-engine-vivado=on.\n");
        log_info("Running explicit UNPLACED INTRINSIC-ONLY nominal phase analyser; no routed timing claim.\n");
        ctx->settings[ctx->id("xilinx/phase-intrinsic-probe")] = Property(1);
        try {
            TimingAnalyser analyser(ctx);
            analyser.setup(false, false, true);
        } catch (...) {
            ctx->settings[ctx->id("xilinx/phase-intrinsic-probe")] = Property(0);
            throw;
        }
        ctx->settings[ctx->id("xilinx/phase-intrinsic-probe")] = Property(0);
    }
''')
        p.write_text(text)
        plan = Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md'
        shutil.copy2(plan, source / 'docs/xilinx-porting/09-phase-edge-timing.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        owner = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-cli-build/himbaechel/CMakeFiles/nextpnr-himbaechel.dir'))
        donor = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-himbaechel')); dependencies = {}
        for p in owner.rglob('*.o.d'):
            fields = shlex.split(p.read_text().replace('\\\n', ' '))
            if str(donor / 'common/kernel/timing.h') in fields:
                relative = str(Path(fields[1]).relative_to(donor)); key = Path(fields[1]).name + '.o'
                if key in dependencies: raise ValueError('Ambiguous timing-header dependency')
                dependencies[key] = (relative, describe(p))
        if len(dependencies) != 13: raise ValueError('Timing-header rebuild scope changed')
        for relative in ('himbaechel/uarch/xilinx/pack.cc', 'himbaechel/uarch/xilinx/pack_clocking.cc', 'himbaechel/uarch/xilinx/xilinx.cc'):
            dependencies.setdefault(Path(relative).name + '.o', (relative, None))
        objects = out / 'input-objects'; objects.mkdir(); link = []; jobs = []; reused = []
        template = before['compile_plan'][0]['argv']
        for i, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                target = objects / (str(i).zfill(3) + '-' + Path(arg).name)
                selected = next((n for n in dependencies if Path(arg).name.endswith(n)), None)
                if selected:
                    relative, dep = dependencies.pop(selected)
                    argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in [('-MF', str(target) + '.d'), ('-o', str(target)), ('-c', str(source / relative))]: argv[argv.index(flag) + 1] = value
                    jobs.append({'source': str(source / relative), 'output': str(target), 'argv': argv, 'dependency': dep})
                else:
                    shutil.copy2(arg, target)
                    if digest(arg) != digest(target): raise ValueError('Reused link input changed')
                    reused.append({'original': describe(arg), 'copied': describe(target)})
                link.append(str(target))
            elif arg.startswith('-Wl,--dependency-file='): link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
            else: link.append(arg)
        if dependencies or len(jobs) != 16: raise ValueError('Incomplete timing-header rebuild')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out / 'source.input.json'),
             source_delta=[n for n in updated if expected.get(n) != updated[n]], compile_plan=jobs, link_argv=link,
             reused_inputs=reused, retained_corrections=[*before.get('retained_corrections', []), 'OPT_IN_NOMINAL_PHASE_ENGINE'])
        print(f'COMPILING {len(jobs)} timing-dependent files with {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(lambda j: run('compile-' + str(j[0]).zfill(2), j[1]['argv']), enumerate(jobs)))
        save(compile_results=results)
        if any(results.values()): raise RuntimeError('Phase-engine compilation failed')
        save(stage='link'); _, code = run('link', link)
        if code: raise RuntimeError('Phase-engine link failed')
        _, code = run('version', [str(out / 'nextpnr-himbaechel'), '--version'])
        if code: raise RuntimeError('Phase-engine startup failed')
        if any(digest(original / n) != sha for n, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='PHASE_ENGINE_BUILD_PASS_NATIVE_ANALYSER_VALIDATION_PENDING', binary=describe(out / 'nextpnr-himbaechel'),
             rebuilt_translation_units=[describe(j['output']) for j in jobs], completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'vendor-gate', 'out'): parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8); args = parser.parse_args()
    if not 1 <= args.workers <= 8: parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.vendor_gate.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__': main()
