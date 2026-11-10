#!/usr/bin/env python3
"""Build opt-in full-design nominal clock waveform/ancestry extraction."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest


CPP = r'''
namespace {
struct Xc7ClockFraction
{
    int64_t num = 0, den = 1;
    Xc7ClockFraction(int64_t n = 0, int64_t d = 1) : num(n), den(d)
    {
        if (den <= 0)
            log_error("Invalid clock rational denominator.\n");
        int64_t common = std::gcd(num, den);
        num /= common;
        den /= common;
    }
    static Xc7ClockFraction wide(__int128 n, __int128 d)
    {
        auto gcd = [](__int128 a, __int128 b) {
            if (a < 0) a = -a;
            while (b) { __int128 rem = a % b; a = b; b = rem; }
            return a;
        };
        if (d <= 0)
            log_error("Invalid clock arithmetic divisor.\n");
        __int128 common = gcd(n, d);
        n /= common; d /= common;
        if (n < std::numeric_limits<int64_t>::min() || n > std::numeric_limits<int64_t>::max() ||
            d > std::numeric_limits<int64_t>::max())
            log_error("Clock rational arithmetic overflow.\n");
        return Xc7ClockFraction(int64_t(n), int64_t(d));
    }
    static Xc7ClockFraction real(double value)
    {
        if (!std::isfinite(value) || std::abs(value) > 1e9)
            log_error("Invalid clock parameter.\n");
        int64_t scaled = std::llround(value * 1000000);
        if (std::abs(value - double(scaled) / 1000000) > 1e-12)
            log_error("Clock parameter needs more than six decimal places.\n");
        return Xc7ClockFraction(scaled, 1000000);
    }
    Xc7ClockFraction operator+(const Xc7ClockFraction &other) const
    {
        return wide(__int128(num) * other.den + __int128(other.num) * den, __int128(den) * other.den);
    }
    Xc7ClockFraction operator-(const Xc7ClockFraction &other) const
    {
        return *this + Xc7ClockFraction(-other.num, other.den);
    }
    Xc7ClockFraction operator*(const Xc7ClockFraction &other) const
    {
        return wide(__int128(num) * other.num, __int128(den) * other.den);
    }
    Xc7ClockFraction operator/(const Xc7ClockFraction &other) const
    {
        if (other.num <= 0)
            log_error("Invalid clock parameter divisor.\n");
        return wide(__int128(num) * other.den, __int128(den) * other.num);
    }
    double as_double() const { return double(num) / den; }
};

struct Xc7ClockWaveform
{
    bool known = false;
    IdString root;
    Xc7ClockFraction period, phase, high;
    std::string dynamic_group, reason;
};

class Xc7ClockWaveformExtractor
{
    Context *ctx;
    dict<IdString, Xc7ClockWaveform> cache;
    pool<IdString> visiting;

    Xc7ClockWaveform unknown(const std::string &reason) const
    {
        Xc7ClockWaveform value;
        value.reason = reason;
        return value;
    }

    const NetInfo *single_clock_input(const CellInfo *cell, std::initializer_list<IdString> ports) const
    {
        const NetInfo *input = nullptr;
        for (IdString port : ports) {
            const NetInfo *net = cell->getPort(port);
            if (!net || net->constant_value != IdString())
                continue;
            if (input && input != net)
                return nullptr;
            input = net;
        }
        return input;
    }

    Xc7ClockFraction parameter(const CellInfo *cell, const std::string &name, double fallback) const
    {
        auto found = cell->params.find(ctx->id(name));
        double value = fallback;
        if (found != cell->params.end()) {
            const auto &property = found->second;
            if (property.is_string) {
                size_t consumed = 0;
                value = std::stod(property.as_string(), &consumed);
                if (consumed != property.as_string().size())
                    log_error("Malformed clock parameter.\n");
            } else if (property.is_fully_def() && property.size() <= 64) {
                value = property.as_int64();
            } else {
                log_error("Undefined clock parameter.\n");
            }
        }
        return Xc7ClockFraction::real(value);
    }

    Xc7ClockWaveform explicit_source(const NetInfo *net) const
    {
        if (!net->clkconstr)
            return unknown("NO_SOURCE_CLOCK_CONSTRAINT");
        auto primary = net->attrs.find(ctx->id("X_VIVADO_PRIMARY_CLOCK"));
        if (net->driver.cell && primary == net->attrs.end())
            return unknown("UNCHARACTERIZED_CLOCK_SOURCE");
        Xc7ClockWaveform value;
        value.known = true;
        value.root = net->name;
        value.period = Xc7ClockFraction(net->clkconstr->period.minDelay());
        value.high = Xc7ClockFraction(net->clkconstr->high.minDelay());
        for (auto entry : {std::make_pair("X_VIVADO_PRIMARY_PERIOD_PS", &value.period),
                           std::make_pair("X_VIVADO_PRIMARY_HIGH_PS", &value.high),
                           std::make_pair("X_VIVADO_PRIMARY_PHASE_PS", &value.phase)}) {
            auto exact = net->attrs.find(ctx->id(entry.first));
            if (exact != net->attrs.end())
                *entry.second = Xc7ClockFraction::real(std::stod(exact->second.as_string()));
        }
        if (value.period.num <= 0 || value.high.num <= 0 || value.high.as_double() >= value.period.as_double())
            return unknown("INVALID_SOURCE_WAVEFORM");
        value.reason = "EXPLICIT_SOURCE_WAVEFORM";
        return value;
    }

    Xc7ClockWaveform derive(const NetInfo *net, unsigned depth)
    {
        if (!net || net->constant_value != IdString())
            return unknown("ABSENT_OR_CONSTANT_CLOCK");
        const CellInfo *cell = net->driver.cell;
        IdString output = net->driver.port;
        if (cell && cell->type.in(id_BUFGCTRL, id_BUFHCE_BUFHCE, id_BUFIO_BUFIO, id_BUFMRCE, id_BUFR_BUFR)) {
            const NetInfo *input = single_clock_input(cell, {id_I, id_I0, id_I1});
            if (!input)
                return unknown("AMBIGUOUS_OR_ABSENT_BUFFER_INPUT");
            auto parent = get(input, depth + 1);
            // A create_clock on this buffer output declares an independent
            // source even when its upstream external clock is unconstrained.
            if (!parent.known && net->attrs.count(ctx->id("X_VIVADO_PRIMARY_CLOCK")))
                return explicit_source(net);
            if (parent.known && cell->type == id_BUFR_BUFR) {
                std::string divide = str_or_default(cell->params, ctx->id("BUFR_DIVIDE"), "BYPASS");
                if (divide != "BYPASS")
                    return unknown("BUFR_EDGE_ALIGNMENT_NOT_CHARACTERIZED");
            }
            return parent;
        }
        if (cell && cell->type.in(id_IOB33M_INBUF_EN, id_IOB33S_INBUF_EN, id_IOB33_INBUF_EN,
                                 id_IOB18_INBUF_DCIEN, id_IOB18M_INBUF_DCIEN)) {
            const NetInfo *input = cell->getPort(id_PAD);
            if (!input)
                return unknown("ABSENT_IO_CLOCK_PAD");
            return get(input, depth + 1);
        }
        if (cell && cell->type.in(id_MMCME2_ADV_MMCME2_ADV, id_PLLE2_ADV_PLLE2_ADV)) {
            bool mmcm = cell->type == id_MMCME2_ADV_MMCME2_ADV;
            const NetInfo *feedback = cell->getPort(id_CLKFBIN);
            pool<IdString> feedback_seen;
            for (unsigned step = 0; feedback && feedback->driver.cell != cell && step < 16; ++step) {
                if (!feedback_seen.insert(feedback->name).second) {
                    feedback = nullptr;
                    break;
                }
                const CellInfo *buffer = feedback->driver.cell;
                if (!buffer || !buffer->type.in(id_BUFGCTRL, id_BUFHCE_BUFHCE, id_BUFIO_BUFIO, id_BUFMRCE)) {
                    feedback = nullptr;
                    break;
                }
                feedback = single_clock_input(buffer, {id_I, id_I0, id_I1});
            }
            if (!feedback || feedback->driver.cell != cell || feedback->driver.port != ctx->id("CLKFBOUT"))
                return unknown("FEEDBACK_TOPOLOGY_NOT_CHARACTERIZED");
            const NetInfo *input = nullptr;
            const NetInfo *select = cell->getPort(id_CLKINSEL);
            if (select && select->constant_value.in(id_GND, id_VCC)) {
                bool primary = select->constant_value == id_VCC;
                primary ^= bool(int_or_default(cell->params, ctx->id("IS_CLKINSEL_INVERTED"), 0));
                input = cell->getPort(primary ? id_CLKIN1 : id_CLKIN2);
            } else {
                input = single_clock_input(cell, {id_CLKIN1, id_CLKIN2});
            }
            if (!input)
                return unknown("AMBIGUOUS_OR_ABSENT_GENERATOR_INPUT");
            auto parent = get(input, depth + 1);
            if (!parent.known)
                return parent;
            if (parameter(cell, "CLKFBOUT_PHASE", 0).num != 0)
                return unknown("FEEDBACK_PHASE_NOT_CHARACTERIZED");
            if (mmcm && str_or_default(cell->params, ctx->id("CLKFBOUT_USE_FINE_PS"), "FALSE") != "FALSE")
                return unknown("FEEDBACK_FINE_PHASE_NOT_CHARACTERIZED");
            std::string name = output.str(ctx);
            auto divclk = parameter(cell, "DIVCLK_DIVIDE", 1);
            auto multiply = parameter(cell, mmcm ? "CLKFBOUT_MULT_F" : "CLKFBOUT_MULT", 1);
            Xc7ClockWaveform value = parent;
            bool inverted = !name.empty() && name.back() == 'B';
            if (name == "CLKFBOUT" || name == "CLKFBOUTB") {
                value.period = parent.period * divclk;
                value.high = value.period / Xc7ClockFraction(2);
            } else if (name.size() >= 7 && name.substr(0, 6) == "CLKOUT") {
                std::string index = name.substr(6, 1), stem = "CLKOUT" + index;
                value.period = parent.period * divclk / multiply * parameter(cell,
                    stem + (mmcm && index == "0" ? "_DIVIDE_F" : "_DIVIDE"), 1);
                auto duty = parameter(cell, stem + "_DUTY_CYCLE", 0.5);
                if (duty.as_double() <= 0 || duty.as_double() >= 1)
                    return unknown("INVALID_OUTPUT_DUTY_CYCLE");
                value.high = value.period * duty;
                value.phase = parent.phase + value.period * parameter(cell, stem + "_PHASE", 0) / Xc7ClockFraction(360);
                if (mmcm && str_or_default(cell->params, ctx->id(stem + "_USE_FINE_PS"), "FALSE") == "TRUE") {
                    if (!value.dynamic_group.empty())
                        value.dynamic_group += ";";
                    value.dynamic_group += cell->name.str(ctx);
                }
            } else {
                return unknown("UNSUPPORTED_GENERATOR_OUTPUT");
            }
            if (inverted) {
                value.phase = value.phase + value.high;
                value.high = value.period - value.high;
            }
            value.reason = "NOMINAL_GENERATED_WAVEFORM";
            return value;
        }
        // Stop at an explicitly constrained source, never infer a frequency
        // from the timing engine's global target or a primitive's input hint.
        return explicit_source(net);
    }

  public:
    explicit Xc7ClockWaveformExtractor(Context *ctx) : ctx(ctx) {}
    Xc7ClockWaveform get(const NetInfo *net, unsigned depth = 0)
    {
        if (!net)
            return unknown("ABSENT_CLOCK");
        auto found = cache.find(net->name);
        if (found != cache.end())
            return found->second;
        if (depth > 64 || !visiting.insert(net->name).second)
            return unknown("CLOCK_ANCESTRY_CYCLE_OR_DEPTH_LIMIT");
        auto value = derive(net, depth);
        visiting.erase(net->name);
        cache[net->name] = value;
        return value;
    }
};
} // namespace

void generate_xc7_clock_waveforms(Context *ctx)
{
    const auto &opts = ctx->args.options;
    std::string mode = opts.count("clock-family-vivado") ? opts["clock-family-vivado"].as<std::string>() : "off";
    if (mode != "on" && mode != "off")
        log_error("clock-family-vivado must be on or off.\n");
    if (mode == "off") {
        if (opts.count("clock-waveform-audit"))
            log_error("Clock waveform audit requires clock-family-vivado=on.\n");
        return;
    }
    if (ctx->args.device != "xc7k480tffg1156-2")
        log_error("Clock waveforms are characterized only for xc7k480tffg1156-2.\n");
    for (const char *option : {"clock-vivado-timing", "clock-feedback-vivado"})
        if (!opts.count(option) || opts[option].as<std::string>() != "on")
            log_error("Clock waveform extraction requires %s=on.\n", option);
    pool<IdString> names;
    dict<IdString, unsigned> references;
    for (const auto &entry : ctx->nets)
        if (entry.second->clkconstr)
            names.insert(entry.first);
    for (const auto &entry : ctx->cells) {
        const CellInfo *cell = entry.second.get();
        for (const auto &port : cell->ports) {
            int count = 0;
            auto type = ctx->getPortTimingClass(cell, port.first, count);
            if ((type == TMG_CLOCK_INPUT || type == TMG_GEN_CLOCK) && port.second.net &&
                    port.second.net->constant_value == IdString()) {
                names.insert(port.second.net->name);
                if (type == TMG_CLOCK_INPUT)
                    references[port.second.net->name]++;
            }
            for (int i = 0; i < count; ++i) {
                auto info = ctx->getPortClockingInfo(cell, port.first, i);
                const NetInfo *net = cell->getPort(info.clock_port);
                if (net && net->constant_value == IdString()) {
                    names.insert(net->name);
                    references[net->name]++;
                }
            }
        }
    }
    Xc7ClockWaveformExtractor extractor(ctx);
    std::ofstream audit;
    if (opts.count("clock-waveform-audit")) {
        std::string path = opts["clock-waveform-audit"].as<std::string>();
        if (std::ifstream(path).good())
            log_error("Clock waveform audit output already exists.\n");
        audit.open(path);
        if (!audit)
            log_error("Cannot create clock waveform audit.\n");
        audit << "net\tknown\troot\tperiod_num_ps\tperiod_den\tphase_num_ps\tphase_den\thigh_num_ps\thigh_den\tdynamic_group\treferences\treason\n";
    }
    unsigned known = 0, unknown = 0;
    for (IdString name : names) {
        auto *net = ctx->nets.at(name).get();
        auto wave = extractor.get(net);
        net->attrs[ctx->id("X_VIVADO_CLOCK_VALID")] = Property(wave.known ? 1 : 0);
        if (wave.known) {
            ++known;
            net->attrs[ctx->id("X_VIVADO_CLOCK_ROOT")] = wave.root.str(ctx);
            net->attrs[ctx->id("X_VIVADO_CLOCK_DYNAMIC_GROUP")] = wave.dynamic_group;
            for (const auto &value : {std::make_pair("PERIOD", wave.period), std::make_pair("PHASE", wave.phase), std::make_pair("HIGH", wave.high)}) {
                net->attrs[ctx->idf("X_VIVADO_CLOCK_%s_NUM_PS", value.first)] = Property(value.second.num, 64);
                net->attrs[ctx->idf("X_VIVADO_CLOCK_%s_DEN", value.first)] = Property(value.second.den, 64);
            }
        } else {
            ++unknown;
        }
        if (audit)
            audit << name.str(ctx) << '\t' << wave.known << '\t' << wave.root.str(ctx)
                  << '\t' << wave.period.num << '\t' << wave.period.den
                  << '\t' << wave.phase.num << '\t' << wave.phase.den
                  << '\t' << wave.high.num << '\t' << wave.high.den
                  << '\t' << wave.dynamic_group << '\t' << (references.count(name) ? references.at(name) : 0)
                  << '\t' << wave.reason << '\n';
    }
    if (audit.is_open()) {
        audit.flush();
        if (!audit)
            log_error("Clock waveform audit write failed.\n");
    }
    log_info("Exact nominal clock waveforms: %u known, %u unknown; engine/skew and full timing remain unqualified.\n", known, unknown);
}
'''


def build(previous, out, workers):
    before = json.loads(previous.read_text())
    if describe(before['binary']['path']) != before['binary'] or describe(before['source_inventory']['path']) != before['source_inventory']:
        raise ValueError('Verified clock backend changed')
    original = Path(before['source']); expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'previous': describe(previous),
            'previous_binary': before['binary'], 'helper': describe(__file__), 'workers': workers,
            'scope': 'NOMINAL_FULL_DESIGN_CLOCK_WAVEFORMS_AND_ANCESTRY_ENGINE_AND_SKEW_PENDING',
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
        if text.count(old) != 1:
            raise ValueError('Unexpected source anchor: ' + old[:80])
        return text.replace(old, new)
    try:
        save(stage='copy-and-patch')
        source = out / 'source'; shutil.copytree(original, source)
        if any(digest(source / n) != sha for n, sha in expected.items()):
            raise ValueError('Copied source differs')
        folder = source / 'himbaechel/uarch/xilinx'
        (folder / 'xc7_clock_waveforms.h').write_text('// Included within the nextpnr namespace, only by pack_clocking.cc.\n' + CPP)
        cc = folder / 'pack_clocking.cc'; text = cc.read_text()
        text = '#include <numeric>\n#include <limits>\n#include <cmath>\n' + text
        text = replace(text, 'NEXTPNR_NAMESPACE_BEGIN', 'NEXTPNR_NAMESPACE_BEGIN\n#include "xc7_clock_waveforms.h"')
        cc.write_text(text)
        cc = folder / 'pack.cc'; text = cc.read_text()
        text = replace(text, 'NEXTPNR_NAMESPACE_BEGIN', 'NEXTPNR_NAMESPACE_BEGIN\nvoid generate_xc7_clock_waveforms(Context *ctx);')
        text = replace(text, '    initialize_serdes_timing();', '    initialize_serdes_timing();\n    generate_xc7_clock_waveforms(ctx);')
        cc.write_text(text)
        cc = folder / 'xilinx.cc'; text = cc.read_text()
        text = replace(text, '    return specific;', '''    specific.add_options()("clock-family-vivado", po::value<std::string>(), "experimental exact nominal clock ancestry/waveforms: on or off (default off)");
    specific.add_options()("clock-waveform-audit", po::value<std::string>(), "complete used-clock waveform/ancestry audit output");
    return specific;''')
        cc.write_text(text)
        cc = folder / 'xdc.cc'; text = cc.read_text()
        text = '#include <cmath>\n' + text
        text = replace(text, '    unsigned num_errors = 0;', '''    unsigned num_errors = 0;
    const auto &options = ctx->args.options;
    bool exact_waveforms = options.count("clock-family-vivado") && options["clock-family-vivado"].as<std::string>() == "on";''')
        text = replace(text, '            bool got_period = false;', '''            bool got_period = false;
            bool got_waveform = false;
            double rise = 0, fall = 0;
            auto clock_number = [&](const std::string &text) {
                size_t consumed = 0;
                double value = std::stod(text, &consumed);
                if (exact_waveforms && (!std::isfinite(value) || consumed != text.size()))
                    log_error("Malformed primary clock number.\\n");
                return value;
            };''')
        old = '''                } else if (opt == "-name" || opt == "-waveform") {
                    log_warning("ignoring unsupported XDC option '%s' (on line %d)\\n", opt.c_str(), lineno);
                    cursor++;'''
        new = '''                } else if (opt == "-waveform" && exact_waveforms) {
                    cursor++;
                    if (cursor >= int(arguments.size()))
                        log_error("XDC clock waveform is missing.\\n");
                    auto edges = split_to_args(strip_quotes(arguments.at(cursor)), true);
                    if (edges.size() != 2)
                        log_error("XDC clock waveform requires two edges.\\n");
                    rise = clock_number(edges[0]); fall = clock_number(edges[1]);
                    got_waveform = true;
                } else if (opt == "-name" || opt == "-waveform") {
                    log_warning("ignoring unsupported XDC option '%s' (on line %d)\\n", opt.c_str(), lineno);
                    cursor++;'''
        text = replace(text, old, new)
        text = replace(text, '                    period = std::stod(arguments.at(cursor));',
                       '                    period = clock_number(arguments.at(cursor));')
        old = '''                n->clkconstr->low = DelayPair(ctx->getDelayFromNS(period / 2));'''
        new = old + '''
                if (exact_waveforms) {
                    if (period <= 0 || (got_waveform && (fall <= rise || fall - rise >= period)))
                        log_error("Invalid primary clock waveform.\\n");
                    double high = got_waveform ? fall - rise : period / 2;
                    n->clkconstr->high = DelayPair(ctx->getDelayFromNS(high));
                    n->clkconstr->low = DelayPair(ctx->getDelayFromNS(period - high));
                    n->attrs[ctx->id("X_VIVADO_PRIMARY_CLOCK")] = Property(1);
                    n->attrs[ctx->id("X_VIVADO_PRIMARY_PHASE_PS")] = std::to_string(got_waveform ? rise * 1000 : 0);
                    n->attrs[ctx->id("X_VIVADO_PRIMARY_PERIOD_PS")] = std::to_string(period * 1000);
                    n->attrs[ctx->id("X_VIVADO_PRIMARY_HIGH_PS")] = std::to_string(high * 1000);
                }'''
        text = replace(text, old, new); cc.write_text(text)
        plan = Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md'
        shutil.copy2(plan, source / 'docs/xilinx-porting/08-clock-waveforms.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        objects = out / 'input-objects'; objects.mkdir(); link = []; jobs = []; reused = []
        template = before['compile_plan'][0]['argv']
        changed = {'pack.cc', 'pack_clocking.cc', 'xilinx.cc', 'xdc.cc'}
        for i, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                dest = objects / (str(i).zfill(3) + '-' + Path(arg).name)
                name = next((n for n in changed if Path(arg).name.endswith(n + '.o')), None)
                if name:
                    changed.remove(name); argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in [('-MF', str(dest) + '.d'), ('-o', str(dest)), ('-c', str(folder / name))]:
                        argv[argv.index(flag) + 1] = value
                    jobs.append({'source': str(folder / name), 'output': str(dest), 'argv': argv})
                else:
                    shutil.copy2(arg, dest)
                    if digest(arg) != digest(dest):
                        raise ValueError('Reused link input changed')
                    reused.append({'original': describe(arg), 'copied': describe(dest)})
                link.append(str(dest))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
            else:
                link.append(arg)
        if changed or len(jobs) != 4:
            raise ValueError('Incomplete four-file rebuild')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out / 'source.input.json'),
             source_delta=[n for n in updated if expected.get(n) != updated[n]], compile_plan=jobs,
             link_argv=link, reused_inputs=reused, retained_corrections=[*before.get('retained_corrections', []), 'OPT_IN_NOMINAL_CLOCK_WAVEFORMS'])
        print(f'COMPILING {len(jobs)} translation units with at most {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(lambda item: run('compile-' + str(item[0]), item[1]['argv']), enumerate(jobs)))
        save(compile_results=results)
        if any(results.values()): raise RuntimeError('Clock waveform compilation failed')
        save(stage='link'); _, code = run('link', link)
        if code: raise RuntimeError('Clock waveform link failed')
        _, code = run('version', [str(out / 'nextpnr-himbaechel'), '--version'])
        if code: raise RuntimeError('Clock waveform backend startup failed')
        if any(digest(original / n) != sha for n, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='CLOCK_WAVEFORM_BACKEND_BUILD_PASS_NATIVE_FULL_WAVEFORM_VALIDATION_PENDING',
             binary=describe(out / 'nextpnr-himbaechel'), rebuilt_translation_units=[describe(j['output']) for j in jobs],
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
