#!/usr/bin/env python3
"""Build an isolated, opt-in xc7 DSP timing backend from validated full-scope data."""
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
from openxc7_dsp_timing_tables import parameter


CPP = r'''
#include "dsp_timing_data.h"

struct Xc7DspTiming
{
    std::vector<IdString> pins;
    dict<IdString, unsigned> pin_index;
    dict<IdString, unsigned> cell_model;
    std::vector<std::vector<TimingPortClass>> classes;
};

namespace {
uint32_t dsp_arc_key(unsigned kind, unsigned from, unsigned to)
{
    return (kind << 24) | (from << 12) | to;
}

const DspTimingArc *dsp_find_arc(unsigned model, unsigned kind, unsigned from, unsigned to)
{
    const auto &m = dsp_models[model];
    uint32_t key = dsp_arc_key(kind, from, to);
    auto p = std::lower_bound(m.arcs, m.arcs + m.count, key,
                             [](const DspTimingArc &a, uint32_t key) { return a.key < key; });
    return p != m.arcs + m.count && p->key == key ? p : nullptr;
}

DelayQuad dsp_delay(const DspTimingArc &arc)
{
    return DelayQuad(arc.min_rise, arc.max_rise, arc.min_fall, arc.max_fall);
}

unsigned dsp_model_for_cell(const Xc7DspTiming &data, const CellInfo *cell)
{
    auto found = data.cell_model.find(cell->name);
    if (found == data.cell_model.end())
        log_error("DSP timing model was not initialized for %s.\n", cell->name.c_str(cell->ctx));
    return found->second;
}

bool dsp_parameter_matches(Context *ctx, const CellInfo *cell, IdString id,
                           const DspParam &expected, const DspParam &fallback)
{
    auto found = cell->params.find(id);
    if (expected.is_string) {
        if (found == cell->params.end())
            return fallback.is_string && std::string(fallback.text) == expected.text;
        return found->second.is_string && found->second.str == expected.text;
    }
    int64_t number = fallback.number;
    if (found != cell->params.end()) {
        const auto &actual = found->second;
        if (actual.is_string || !actual.is_fully_def() || actual.size() > 64)
            return false;
        number = actual.as_int64();
    } else if (fallback.is_string) {
        return false;
    }
    // The existing FASM writer ORs individual packer flags with vendor bus
    // masks. Timing must select the same effective silicon configuration.
    std::string name = expected.name;
    int width = name == "IS_ALUMODE_INVERTED" ? 4 :
                name == "IS_INMODE_INVERTED" ? 5 :
                name == "IS_OPMODE_INVERTED" ? 7 : 0;
    std::string bus = width ? name.substr(3, name.size() - 12) : "";
    for (int bit = 0; bit < width; ++bit) {
        auto flag_id = ctx->idf("IS_%s[%d]_INVERTED", bus.c_str(), bit);
        auto flag = cell->params.find(flag_id);
        if (flag == cell->params.end())
            continue;
        const auto &value = flag->second;
        if (value.is_string || !value.is_fully_def() || value.size() > 64 ||
            (value.as_int64() != 0 && value.as_int64() != 1))
            log_error("Malformed DSP bus inversion flag %s on %s.\n", flag_id.c_str(ctx), cell->name.c_str(ctx));
        if (value.as_int64())
            number |= int64_t(1) << bit;
    }
    return number == expected.number;
}

const char *dsp_class_name(TimingPortClass type)
{
    switch (type) {
    case TMG_CLOCK_INPUT: return "clock_input";
    case TMG_REGISTER_INPUT: return "register_input";
    case TMG_REGISTER_OUTPUT: return "register_output";
    case TMG_COMB_INPUT: return "comb_input";
    case TMG_COMB_OUTPUT: return "comb_output";
    default: return "ignore";
    }
}
} // namespace

void XilinxImpl::initialize_dsp_timing()
{
    const auto &opts = ctx->args.options;
    std::string mode = opts.count("dsp-vivado-timing") ? opts["dsp-vivado-timing"].as<std::string>() : "off";
    if (mode != "on" && mode != "off")
        log_error("dsp-vivado-timing must be on or off.\n");
    if (mode == "off") {
        if (opts.count("dsp-timing-audit"))
            log_error("DSP timing audit requires dsp-vivado-timing=on.\n");
        return;
    }
    if (ctx->args.device != "xc7k480tffg1156-2")
        log_error("DSP timing data are characterized only for xc7k480tffg1156-2.\n");
    dsp_timing.reset(new Xc7DspTiming);
    auto &data = *dsp_timing;
    for (unsigned i = 0; i < sizeof(dsp_pin_names) / sizeof(dsp_pin_names[0]); ++i) {
        data.pins.push_back(ctx->id(dsp_pin_names[i]));
        data.pin_index[data.pins.back()] = i;
    }
    unsigned clock = data.pin_index.at(ctx->id("CLK"));
    for (const auto &model : dsp_models) {
        std::vector<TimingPortClass> classes;
        for (bool output : dsp_pin_outputs)
            classes.push_back(output ? TMG_IGNORE : TMG_COMB_INPUT);
        classes[clock] = TMG_CLOCK_INPUT;
        for (size_t i = 0; i < model.count; ++i) {
            const auto &arc = model.arcs[i];
            unsigned kind = arc.key >> 24, to = arc.key & 4095;
            if (kind == 1)
                classes[to] = TMG_REGISTER_OUTPUT;
            else if (kind == 2 || kind == 3)
                classes[to] = TMG_REGISTER_INPUT;
            else if (classes[to] != TMG_REGISTER_OUTPUT)
                classes[to] = TMG_COMB_OUTPUT;
        }
        data.classes.push_back(std::move(classes));
    }
    std::vector<IdString> param_ids;
    for (const auto &value : dsp_defaults)
        param_ids.push_back(ctx->id(value.name));
    for (const auto &entry : ctx->cells) {
        auto *cell = entry.second.get();
        if (cell->type != id_DSP48E1_DSP48E1)
            continue;
        bool matched = false;
        for (unsigned model = 0; model < sizeof(dsp_models) / sizeof(dsp_models[0]); ++model) {
            bool equal = true;
            for (unsigned p = 0; p < param_ids.size(); ++p) {
                const auto &expected = dsp_models[model].params[p];
                equal &= dsp_parameter_matches(ctx, cell, param_ids[p], expected, dsp_defaults[p]);
                if (!equal)
                    break;
            }
            if (equal) {
                data.cell_model[cell->name] = model;
                matched = true;
                break;
            }
        }
        if (!matched)
            log_error("Unsupported DSP timing configuration for %s; no delay was invented.\n", cell->name.c_str(ctx));
    }
    log_info("Vivado-derived DSP timing enabled for %zu cells; whole-device timing remains unqualified.\n", data.cell_model.size());
    if (!opts.count("dsp-timing-audit"))
        return;
    std::string path = opts["dsp-timing-audit"].as<std::string>();
    if (std::ifstream(path).good())
        log_error("DSP timing audit output already exists.\n");
    std::ofstream audit(path);
    if (!audit)
        log_error("Cannot create DSP timing audit output.\n");
    for (const auto &entry : ctx->cells) {
        const auto *cell = entry.second.get();
        if (cell->type != id_DSP48E1_DSP48E1)
            continue;
        audit << "M\t" << cell->name.str(ctx) << '\t' << data.cell_model.at(cell->name) << '\n';
        for (const auto &port : cell->ports) {
            int count = 0;
            auto cls = getPortTimingClass(cell, port.first, count);
            audit << "P\t" << cell->name.str(ctx) << '\t' << port.first.str(ctx) << '\t' << dsp_class_name(cls) << '\t' << count << '\n';
            if (count) {
                auto info = getPortClockingInfo(cell, port.first, 0);
                audit << "R\t" << cell->name.str(ctx) << '\t' << port.first.str(ctx) << '\t' << info.clock_port.str(ctx)
                      << '\t' << (info.edge == RISING_EDGE ? "rising" : "falling")
                      << '\t' << info.setup.minDelay() << '\t' << info.setup.maxDelay()
                      << '\t' << info.hold.minDelay() << '\t' << info.hold.maxDelay()
                      << '\t' << info.clockToQ.minRiseDelay() << '\t' << info.clockToQ.maxRiseDelay()
                      << '\t' << info.clockToQ.minFallDelay() << '\t' << info.clockToQ.maxFallDelay() << '\n';
            }
            if (port.second.type != PORT_IN)
                continue;
            for (const auto &output : cell->ports) {
                if (output.second.type != PORT_OUT)
                    continue;
                DelayQuad delay;
                if (getCellDelay(cell, port.first, output.first, delay))
                    audit << "C\t" << cell->name.str(ctx) << '\t' << port.first.str(ctx) << '\t' << output.first.str(ctx)
                          << '\t' << delay.minRiseDelay() << '\t' << delay.maxRiseDelay()
                          << '\t' << delay.minFallDelay() << '\t' << delay.maxFallDelay() << '\n';
            }
        }
    }
    audit.flush();
    if (!audit)
        log_error("DSP timing audit write failed.\n");
}

bool XilinxImpl::getCellDelay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const
{
    if (!dsp_timing || cell->type != id_DSP48E1_DSP48E1)
        return HimbaechelAPI::getCellDelay(cell, from, to, delay);
    const auto &data = *dsp_timing;
    auto f = data.pin_index.find(from), t = data.pin_index.find(to);
    if (f == data.pin_index.end() || t == data.pin_index.end())
        return false;
    const auto *arc = dsp_find_arc(dsp_model_for_cell(data, cell), 0, f->second, t->second);
    if (!arc)
        return false;
    delay = dsp_delay(*arc);
    return true;
}

TimingPortClass XilinxImpl::getPortTimingClass(const CellInfo *cell, IdString port, int &count) const
{
    if (!dsp_timing || cell->type != id_DSP48E1_DSP48E1)
        return HimbaechelAPI::getPortTimingClass(cell, port, count);
    const auto &data = *dsp_timing;
    auto pin = data.pin_index.find(port);
    if (pin == data.pin_index.end())
        log_error("Unknown DSP timing pin %s.\n", port.c_str(ctx));
    auto cls = data.classes[dsp_model_for_cell(data, cell)][pin->second];
    count = (cls == TMG_REGISTER_INPUT || cls == TMG_REGISTER_OUTPUT) ? 1 : 0;
    return cls;
}

TimingClockingInfo XilinxImpl::dsp_port_clocking(const CellInfo *cell, IdString port, int index) const
{
    NPNR_ASSERT(index == 0);
    const auto &data = *dsp_timing;
    unsigned model = dsp_model_for_cell(data, cell), pin = data.pin_index.at(port), clock = data.pin_index.at(ctx->id("CLK"));
    TimingClockingInfo info;
    info.clock_port = ctx->id("CLK");
    info.edge = dsp_models[model].inverted ? FALLING_EDGE : RISING_EDGE;
    if (data.classes[model][pin] == TMG_REGISTER_INPUT) {
        const auto *setup = dsp_find_arc(model, 2, clock, pin), *hold = dsp_find_arc(model, 3, clock, pin);
        NPNR_ASSERT(setup && hold);
        info.setup = dsp_delay(*setup).delayPair();
        info.hold = dsp_delay(*hold).delayPair();
    } else {
        NPNR_ASSERT(data.classes[model][pin] == TMG_REGISTER_OUTPUT);
        const auto *clkq = dsp_find_arc(model, 1, clock, pin);
        NPNR_ASSERT(clkq);
        info.clockToQ = dsp_delay(*clkq);
    }
    return info;
}
'''


def generate_data(data, defaults):
    pins = sorted(p["packed"] for p in data["pin_map"].values())
    if len(pins) >= 4096 or len(set(pins)) != len(pins):
        raise ValueError("Invalid packed pin indices")
    ids = {name: i for i, name in enumerate(pins)}
    directions = {p["packed"]: p["direction"] for p in data["pin_map"].values()}
    names = sorted(defaults)
    def value(name, item):
        string = item["kind"] == "string"
        return '{' + json.dumps(name) + ',' + ('true' if string else 'false') + ',' + (
            json.dumps(item["value"]) if string else 'nullptr') + ',' + (
            '0' if string else str(item["value"]) + 'LL') + '}'
    lines = ['// Generated from independently raw-validated full-design DSP timing data.',
             'namespace {',
             'struct DspParam { const char *name; bool is_string; const char *text; int64_t number; };',
             'struct DspTimingArc { uint32_t key; int32_t min_rise, max_rise, min_fall, max_fall; };',
             'struct DspModel { const DspParam *params; const DspTimingArc *arcs; size_t count; bool inverted; };',
             'const char *const dsp_pin_names[] = {' + ','.join(map(json.dumps, pins)) + '};',
             'const bool dsp_pin_outputs[] = {' + ','.join('true' if directions[p] == 'output' else 'false' for p in pins) + '};',
             'const DspParam dsp_defaults[] = {' + ','.join(value(n, defaults[n]) for n in names) + '};']
    models = []
    kinds = {"comb": 0, "clkq": 1, "setup": 2, "hold": 3}
    for i, config in enumerate(data["configurations"]):
        if set(config["parameters"]) != set(names):
            raise ValueError("DSP parameter signature differs from declared defaults")
        lines.append(f'const DspParam dsp_params_{i}[] = {{' + ','.join(value(n, config['parameters'][n]) for n in names) + '};')
        arcs = []
        for row in config["arcs"]:
            kind, source, target = row[:3]
            key = (kinds[kind] << 24) | (ids[source] << 12) | ids[target]
            arcs.append((key, *row[3:7]))
        arcs.sort()
        if len({a[0] for a in arcs}) != len(arcs):
            raise ValueError("Duplicate DSP timing lookup key")
        lines.append(f'const DspTimingArc dsp_arcs_{i}[] = {{\n' + ',\n'.join('{' + ','.join(map(str, a)) + '}' for a in arcs) + '\n};')
        models.append(f'{{dsp_params_{i},dsp_arcs_{i},{len(arcs)},' + ('true' if config['clock_edge'] == 'falling' else 'false') + '}')
    lines.append('const DspModel dsp_models[] = {' + ','.join(models) + '};')
    lines.append('} // namespace\n')
    return '\n'.join(lines)


def build(previous, tables, inventory_path, out, workers):
    before = json.loads(previous.read_text())
    if describe(before["binary"]["path"]) != before["binary"]:
        raise ValueError("Previous backend changed")
    if describe(before['source_inventory']['path']) != before['source_inventory']:
        raise ValueError("Previous source inventory changed")
    tm = json.loads((tables / 'manifest.json').read_text())
    if tm['status'] != 'FULL_DSP_TABLES_PREPARED_RAW_BOUNDS_VERIFIED_BACKEND_NOT_QUALIFIED' or tm['raw_validation']['bound_mismatches']:
        raise ValueError("Expected independently validated full-scope DSP tables")
    data_path = tables / 'dsp-timing-tables.json'
    if describe(data_path) != tm['output']:
        raise ValueError("Prepared DSP table changed")
    data = json.loads(data_path.read_text())
    if data['part'] != 'xc7k480tffg1156-2' or data['units'] != 'ps' or len(data['configurations']) != tm['complete_configurations']:
        raise ValueError("Full exact-part DSP table scope changed")
    if sum(len(c['full_design_cells']) for c in data['configurations']) != 717:
        raise ValueError("Full design DSP coverage changed")
    if (tables/'native.exit').read_text().strip() != '0':
        raise ValueError("DSP table preparation did not exit successfully")
    config_source = Path(tm['source']) / 'configurations.json'
    configs = json.loads(config_source.read_text())
    if digest(inventory_path) != configs['source_inventory_sha256']:
        raise ValueError("DSP defaults inventory changed")
    inventory = json.loads(inventory_path.read_text())
    defaults = {n: parameter(v) for n, v in inventory['vendor_defaults_raw'].items()}
    out.mkdir(parents=True, exist_ok=False)
    info = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                previous=describe(previous), previous_binary=before['binary'],
                helper=describe(__file__), table_manifest=describe(tables/'manifest.json'),
                tables=describe(data_path), defaults_inventory=describe(inventory_path),
                workers=workers, physical_hardware='NOT_RUN', numerical_timing='NOT_QUALIFIED',
                scope='OPT_IN_FULL_DESIGN_DSP_CONFIGURATIONS_NOT_COMPLETE_PHY_TIMING')
    def save(**fields):
        info.update(fields); (out/'manifest.json').write_text(json.dumps(info, indent=2)+'\n')
    def run(stage, command):
        (out/(stage+'.command.json')).write_text(json.dumps(command, indent=2)+'\n')
        with (out/(stage+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(result.returncode)+'\n')
        return stage, result.returncode
    try:
        save(stage='copy-and-patch')
        source = out/'source'; original = Path(before['source'])
        expected = json.loads(Path(before['source_inventory']['path']).read_text())
        shutil.copytree(original, source)
        if any(digest(source/n) != sha for n, sha in expected.items()):
            raise ValueError("Source copy differs from checked backend")
        header = source/'himbaechel/uarch/xilinx/xilinx.h'
        text = header.read_text(); anchor = 'struct XilinxImpl : HimbaechelAPI'
        if text.count(anchor) != 1:
            raise ValueError("Unexpected Xilinx declaration")
        text = text.replace(anchor, 'struct Xc7DspTiming;\n\n'+anchor)
        anchor = '    TimingClockingInfo getPortClockingInfo(const CellInfo *cell, IdString port, int index) const override;'
        if text.count(anchor) != 1:
            raise ValueError("Unexpected Xilinx timing declaration")
        text = text.replace(anchor, anchor + '''
    bool getCellDelay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const override;
    TimingPortClass getPortTimingClass(const CellInfo *cell, IdString port, int &count) const override;
    void initialize_dsp_timing();
    TimingClockingInfo dsp_port_clocking(const CellInfo *cell, IdString port, int index) const;
    std::unique_ptr<Xc7DspTiming> dsp_timing;
''')
        header.write_text(text)
        cc = source/'himbaechel/uarch/xilinx/xilinx.cc'; text = cc.read_text()
        anchor = 'struct FFControlSet'
        if text.count(anchor) != 1:
            raise ValueError("Unexpected Xilinx source anchor")
        text = text.replace(anchor, CPP + '\n' + anchor)
        anchor = '    auto info = HimbaechelAPI::getPortClockingInfo(cell, port, index);'
        if text.count(anchor) != 1:
            raise ValueError("Unexpected fabric clock-edge correction")
        text = text.replace(anchor, '    if (dsp_timing && cell->type == id_DSP48E1_DSP48E1)\n        return dsp_port_clocking(cell, port, index);\n'+anchor)
        anchor = '    return specific;'
        if text.count(anchor) != 1:
            raise ValueError("Unexpected Xilinx options")
        text = text.replace(anchor, '''    specific.add_options()("dsp-vivado-timing", po::value<std::string>(), "experimental exact-part DSP timing: on or off (default off)");
    specific.add_options()("dsp-timing-audit", po::value<std::string>(), "post-pack DSP timing callback audit output");
'''+anchor)
        cc.write_text(text)
        pack = source/'himbaechel/uarch/xilinx/pack.cc'; text = pack.read_text()
        anchor = '\n}\nNEXTPNR_NAMESPACE_END'
        if text.count(anchor) != 1:
            raise ValueError("Unexpected Xilinx pack completion")
        pack.write_text(text.replace(anchor, '\n    initialize_dsp_timing();'+anchor))
        generated = source/'himbaechel/uarch/xilinx/dsp_timing_data.h'
        generated.write_text(generate_data(data, defaults))
        plan = Path(__file__).resolve().parents[1]/'docs/openxc7_dsp_timing_plan.md'
        shutil.copy2(plan, source/'docs/xilinx-porting/06-dsp-timing.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out/'source.input.json').write_text(json.dumps(updated, indent=2)+'\n')
        owner = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-cli-build/himbaechel/CMakeFiles/nextpnr-himbaechel.dir'))
        donor = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-himbaechel'))
        dependencies = {}
        for dep in owner.rglob('*.o.d'):
            fields = shlex.split(dep.read_text().replace('\\\n', ' '))
            if str(donor/'himbaechel/uarch/xilinx/xilinx.h') in fields:
                relative = str(Path(fields[1]).relative_to(donor))
                basename = Path(fields[1]).name+'.o'
                if basename in dependencies:
                    raise ValueError("Ambiguous header-dependent translation unit")
                dependencies[basename] = (relative, describe(dep))
        if len(dependencies) != 14:
            raise ValueError("Header-dependent rebuild set changed")
        objects = out/'input-objects'; objects.mkdir()
        link, compiles, reused = [], [], []
        template = before['compile_plan'][0]['argv']
        for i, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                target = objects/(str(i).zfill(3)+'-'+Path(arg).name)
                basename = Path(arg).name
                selected = next((name for name in dependencies if basename == name or basename.endswith('-'+name)), None)
                if selected:
                    relative, dep_record = dependencies.pop(selected)
                    argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in [('-MF', str(target)+'.d'), ('-o', str(target)), ('-c', str(source/relative))]:
                        argv[argv.index(flag)+1] = value
                    compiles.append(dict(source=str(source/relative), output=str(target), argv=argv, dependency_record=dep_record))
                else:
                    shutil.copy2(arg, target)
                    if digest(target) != digest(arg):
                        raise ValueError("Copied object differs")
                    reused.append({'original': describe(arg), 'copied': describe(target)})
                link.append(str(target))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file='+str(out/'link.d'))
            else:
                link.append(arg)
        if dependencies or len(compiles) != 14:
            raise ValueError("Incomplete header-dependent rebuild")
        link[link.index('-o')+1] = str(out/'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out/'source.input.json'),
             source_delta=[n for n in updated if expected.get(n) != updated[n]],
             compile_plan=compiles, link_argv=link, reused_inputs=reused,
             retained_corrections=[*before['retained_corrections'], 'OPT_IN_VIVADO_DSP_TIMING'])
        print('COMPILING 14 header-dependent translation units with '+str(workers)+' workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda job: run('compile-'+str(job[0]).zfill(2), job[1]['argv']), enumerate(compiles)))
        save(compile_results=dict(results))
        if any(code for _, code in results):
            raise RuntimeError('DSP backend compilation failed; inspect compile logs')
        save(stage='link')
        stage, code = run('link', link)
        if code:
            raise RuntimeError('DSP backend link failed')
        _, code = run('version', [str(out/'nextpnr-himbaechel'), '--version'])
        if code:
            raise RuntimeError('DSP backend startup failed')
        if any(digest(Path(before['source'])/n) != sha for n, sha in expected.items()):
            raise ValueError("Previous source changed during build")
        if describe(before['binary']['path']) != before['binary']:
            raise ValueError("Previous binary changed during build")
        shutil.copy2(__file__, out/'helper.py')
        save(status='DSP_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING', stage='compiled',
             binary=describe(out/'nextpnr-himbaechel'), rebuilt_translation_units=[describe(c['output']) for c in compiles])
        print(info['status'], flush=True)
    except Exception as error:
        save(status='FAIL', error=repr(error)); raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'tables', 'inventory', 'out'):
        parser.add_argument('--'+name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.tables.resolve(), args.inventory.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
