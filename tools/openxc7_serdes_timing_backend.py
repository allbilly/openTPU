#!/usr/bin/env python3
"""Build isolated, opt-in timing callbacks for the full design's serializers."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_phy_vivado_timing import library_parameters


CPP = r'''
#include "serdes_timing_data.h"

struct Xc7SerdesTiming
{
    std::vector<IdString> pins;
    dict<IdString, unsigned> pin_index;
    dict<IdString, unsigned> cell_model;
};

namespace {
bool serdes_cell(const CellInfo *cell)
{
    return cell->type.in(id_ISERDESE2_ISERDESE2, id_OSERDESE2_OSERDESE2);
}

unsigned serdes_model_for_cell(const Xc7SerdesTiming &data, const CellInfo *cell)
{
    auto found = data.cell_model.find(cell->name);
    if (found == data.cell_model.end())
        log_error("Serializer timing was not initialized for %s.\n", cell->name.c_str(cell->ctx));
    return found->second;
}

DelayQuad serdes_delay(const SerdesArc &arc)
{
    return DelayQuad(arc.min_rise, arc.max_rise, arc.min_fall, arc.max_fall);
}

bool serdes_parameter_matches(const CellInfo *cell, const SerdesParam &wanted,
                              const SerdesParam &fallback)
{
    auto found = cell->params.find(cell->ctx->id(wanted.name));
    if (found == cell->params.end())
        return wanted.is_string == fallback.is_string && (wanted.is_string ?
                std::string(wanted.text) == fallback.text : wanted.number == fallback.number);
    const auto &actual = found->second;
    if (wanted.is_string)
        return actual.is_string && actual.str == wanted.text;
    return !actual.is_string && actual.is_fully_def() && actual.size() <= 64 &&
           actual.as_int64() == wanted.number;
}

std::vector<const SerdesArc *> serdes_clock_arcs(const Xc7SerdesTiming &data,
                                               const CellInfo *cell, unsigned pin)
{
    const auto &model = serdes_models[serdes_model_for_cell(data, cell)];
    std::vector<const SerdesArc *> result;
    for (size_t i = 0; i < model.arc_count; ++i) {
        const auto &arc = model.arcs[i];
        if (arc.to != pin || (arc.kind != 1 && arc.kind != 2))
            continue;
        // Tied and absent clocks do not create a timing domain. In particular,
        // the real input serializers have no connected CLKDIVP clock.
        const auto *net = cell->getPort(data.pins[arc.from]);
        if (net && net->constant_value == IdString())
            result.push_back(&arc);
    }
    return result;
}
} // namespace

bool XilinxImpl::serdes_cell_delay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const
{
    const auto &data = *serdes_timing;
    auto f = data.pin_index.find(from), t = data.pin_index.find(to);
    if (f == data.pin_index.end() || t == data.pin_index.end())
        return false;
    const auto &model = serdes_models[serdes_model_for_cell(data, cell)];
    for (size_t i = 0; i < model.arc_count; ++i) {
        const auto &arc = model.arcs[i];
        if (arc.kind == 0 && arc.from == f->second && arc.to == t->second) {
            delay = serdes_delay(arc);
            return true;
        }
    }
    return false;
}

TimingPortClass XilinxImpl::serdes_port_class(const CellInfo *cell, IdString port, int &count) const
{
    const auto &data = *serdes_timing;
    auto found = data.pin_index.find(port);
    if (found == data.pin_index.end())
        log_error("Unknown serializer timing pin %s.\n", port.c_str(ctx));
    unsigned pin = found->second;
    const auto &model = serdes_models[serdes_model_for_cell(data, cell)];
    count = 0;
    if (model.directions[pin] < 0)
        log_error("Serializer pin %s is not present in this primitive.\n", port.c_str(ctx));
    if (model.clocks[pin])
        return TMG_CLOCK_INPUT;
    count = int(serdes_clock_arcs(data, cell, pin).size());
    if (count)
        return model.directions[pin] ? TMG_REGISTER_OUTPUT : TMG_REGISTER_INPUT;
    if (!model.directions[pin])
        return TMG_COMB_INPUT;
    for (size_t i = 0; i < model.arc_count; ++i)
        if (model.arcs[i].kind == 0 && model.arcs[i].to == pin)
            return TMG_COMB_OUTPUT;
    return TMG_IGNORE;
}

TimingClockingInfo XilinxImpl::serdes_port_clocking(const CellInfo *cell, IdString port, int index) const
{
    const auto &data = *serdes_timing;
    unsigned pin = data.pin_index.at(port);
    auto arcs = serdes_clock_arcs(data, cell, pin);
    NPNR_ASSERT(index >= 0 && size_t(index) < arcs.size());
    const auto &arc = *arcs[index];
    TimingClockingInfo info;
    info.clock_port = data.pins[arc.from];
    info.edge = arc.falling ? FALLING_EDGE : RISING_EDGE;
    if (arc.kind == 1) {
        info.clockToQ = serdes_delay(arc);
    } else {
        info.setup = serdes_delay(arc).delayPair();
        const auto &model = serdes_models[serdes_model_for_cell(data, cell)];
        const SerdesArc *hold = nullptr;
        for (size_t i = 0; i < model.arc_count; ++i) {
            const auto &candidate = model.arcs[i];
            if (candidate.kind == 3 && candidate.from == arc.from && candidate.to == pin &&
                    candidate.falling == arc.falling) {
                hold = &candidate;
                break;
            }
        }
        NPNR_ASSERT(hold);
        info.hold = serdes_delay(*hold).delayPair();
    }
    return info;
}

void XilinxImpl::initialize_serdes_timing()
{
    const auto &opts = ctx->args.options;
    std::string mode = opts.count("serdes-vivado-timing") ? opts["serdes-vivado-timing"].as<std::string>() : "off";
    if (mode != "on" && mode != "off")
        log_error("serdes-vivado-timing must be on or off.\n");
    if (mode == "off") {
        if (opts.count("serdes-timing-audit"))
            log_error("Serializer timing audit requires serdes-vivado-timing=on.\n");
        return;
    }
    if (ctx->args.device != "xc7k480tffg1156-2")
        log_error("Serializer timing data are characterized only for xc7k480tffg1156-2.\n");
    serdes_timing.reset(new Xc7SerdesTiming);
    auto &data = *serdes_timing;
    for (unsigned i = 0; i < sizeof(serdes_pin_names) / sizeof(serdes_pin_names[0]); ++i) {
        data.pins.push_back(ctx->id(serdes_pin_names[i]));
        data.pin_index[data.pins.back()] = i;
    }
    for (const auto &entry : ctx->cells) {
        const auto *cell = entry.second.get();
        if (!serdes_cell(cell))
            continue;
        bool matched = false;
        for (unsigned m = 0; m < sizeof(serdes_models) / sizeof(serdes_models[0]); ++m) {
            const auto &model = serdes_models[m];
            if (cell->type != ctx->id(model.type))
                continue;
            bool equal = true;
            for (size_t p = 0; p < model.param_count && equal; ++p)
                equal = serdes_parameter_matches(cell, model.params[p], model.defaults[p]);
            if (equal) {
                data.cell_model[cell->name] = m;
                matched = true;
                break;
            }
        }
        if (!matched)
            log_error("Unsupported serializer timing configuration for %s; no delay was invented.\n", cell->name.c_str(ctx));
    }
    log_info("Vivado-derived serializer timing enabled for %zu cells; full timing remains unqualified.\n", data.cell_model.size());
    if (!opts.count("serdes-timing-audit"))
        return;
    std::string path = opts["serdes-timing-audit"].as<std::string>();
    if (std::ifstream(path).good())
        log_error("Serializer timing audit output already exists.\n");
    std::ofstream audit(path);
    if (!audit)
        log_error("Cannot create serializer timing audit output.\n");
    for (const auto &entry : ctx->cells) {
        const auto *cell = entry.second.get();
        if (!serdes_cell(cell))
            continue;
        audit << "M\t" << cell->name.str(ctx) << '\t' << data.cell_model.at(cell->name) << '\n';
        for (const auto &port : cell->ports) {
            int count = 0;
            auto cls = getPortTimingClass(cell, port.first, count);
            audit << "P\t" << cell->name.str(ctx) << '\t' << port.first.str(ctx) << '\t' << dsp_class_name(cls) << '\t' << count << '\n';
            for (int i = 0; i < count; ++i) {
                auto info = getPortClockingInfo(cell, port.first, i);
                audit << "R\t" << cell->name.str(ctx) << '\t' << port.first.str(ctx) << '\t' << i
                      << '\t' << info.clock_port.str(ctx) << '\t' << (info.edge == RISING_EDGE ? "rising" : "falling")
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
        log_error("Serializer timing audit write failed.\n");
}
'''


def bounds(arc):
    result = []
    for transition in ('RISE', 'FALL'):
        values = [Decimal(str(arc['delays_ns'][f'DELAY_{corner}_{limit}_{transition}'])) * 1000
                  for corner in ('FAST', 'SLOW') for limit in ('MIN', 'MAX')]
        if any(not v.is_finite() for v in values):
            raise ValueError('Nonfinite serializer timing value')
        result.extend((int(min(values).to_integral_value(rounding=ROUND_FLOOR)),
                       int(max(values).to_integral_value(rounding=ROUND_CEILING))))
    return result


def prepare(characterization):
    cfg_path = characterization / 'configurations.json'
    raw_path = characterization / 'timing-arcs-compact.json'
    configs = json.loads(cfg_path.read_text())
    raw = json.loads(raw_path.read_text())
    semantic = json.loads((characterization / 'semantic-summary.json').read_text())
    if (semantic['parameter_mismatches'] or semantic['nonfinite_delays'] or
            semantic['configs'] != 7 or semantic['full_design_cells'] != 378 or
            (characterization / 'query.exit').read_text().strip() != '0' or
            (characterization / 'semantic-validator.exit').read_text().strip() != '0'):
        raise ValueError('Full PHY vendor validation did not pass')
    if raw['part'] != 'xc7k480tffg1156-2' or raw['units'] != 'ns' or describe(raw['source_tsv']['path']) != raw['source_tsv']:
        raise ValueError('Exact-part vendor timing source changed')
    selected = [c for c in configs['configs'] if c['primitive'] in ('ISERDESE2', 'OSERDESE2')]
    if len(selected) != 3 or sum(len(c['full_design_cells']) for c in selected) != 358:
        raise ValueError('Complete serializer configuration coverage changed')
    pins = sorted({p['name'] for c in selected for p in c['ports']})
    ids = {p: i for i, p in enumerate(pins)}
    kinds = {'combinational': 0, 'Reg Clk to Q': 1, 'setup': 2, 'hold': 3}
    models = []
    for c in selected:
        defaults, record = library_parameters(c['primitive'])
        if record != configs['library_defaults'][c['primitive']] or set(defaults) != set(c['parameters']):
            raise ValueError('Primitive defaults or complete signature changed')
        if any(p['width'] != 1 for p in c['ports']):
            raise ValueError('Unexpected serializer vector port')
        arcs = []
        for a in raw['arcs']:
            if a['cell'] != c['probe_cell']:
                continue
            if a['disabled'] or a['type'] not in kinds:
                raise ValueError('Disabled or unsupported serializer arc requires explicit semantics')
            transitions = a['transition'].split()
            if not transitions or any(t not in ('rr', 'rf', 'fr', 'ff') for t in transitions):
                raise ValueError('Unknown serializer transition')
            kind = kinds[a['type']]
            edges = {t[0] for t in transitions}
            if kind and len(edges) != 1:
                raise ValueError('Clock arc requires separate edge characterization')
            falling = False
            if kind:
                inversion = c['parameters'].get('IS_' + a['from'] + '_INVERTED')
                if inversion is None or inversion['value'] not in (0, 1):
                    raise ValueError('Missing characterized clock inversion')
                falling = ('f' in edges) != bool(inversion['value'])
            arcs.append([kind, a['from'], a['to'], falling, *bounds(a)])
        arcs.sort(key=lambda a: (ids[a[2]], ids[a[1]], a[0], a[3]))
        if len({tuple(a[:4]) for a in arcs}) != len(arcs):
            raise ValueError('Duplicate serializer timing lookup key')
        keys = {tuple(a[:4]) for a in arcs}
        for a in arcs:
            if a[0] in (2, 3) and ((5 - a[0], *a[1:4]) not in keys):
                raise ValueError('Unpaired setup/hold check')
        directions = {p['name']: p['direction'] for p in c['ports']}
        clocks = {'CLK', 'CLKDIV'}
        if c['primitive'] == 'ISERDESE2':
            clocks.update(('CLKB', 'CLKDIVP', 'OCLK', 'OCLKB'))
        models.append({**c, 'defaults': defaults, 'arcs': arcs, 'directions': directions, 'clocks': sorted(clocks)})
    if sum(len(c['arcs']) for c in models) != 82:
        raise ValueError('Complete serializer raw arc coverage changed')
    return {'part': raw['part'], 'units': 'ps', 'pins': pins, 'models': models,
            'raw': describe(raw_path), 'configs': describe(cfg_path), 'semantic': describe(characterization / 'semantic-summary.json'),
            'raw_arcs': 82, 'full_design_cells': 358, 'numerical_timing': 'NOT_QUALIFIED'}


def generate_data(data):
    pins = data['pins']; ids = {p: i for i, p in enumerate(pins)}
    def param(name, value):
        string = value['kind'] == 'string'
        if value['kind'] not in ('string', 'integer'):
            raise ValueError('Unexpected serializer parameter kind')
        return '{' + json.dumps(name) + ',' + str(string).lower() + ',' + (
            json.dumps(value['value']) if string else 'nullptr') + ',' + (
            '0' if string else str(value['value']) + 'LL') + '}'
    lines = ['// Exact xc7k480tffg1156-2 intrinsic serializer timing; full timing remains unqualified.',
             'namespace {',
             'struct SerdesParam { const char *name; bool is_string; const char *text; int64_t number; };',
             'struct SerdesArc { unsigned kind, from, to; bool falling; int32_t min_rise, max_rise, min_fall, max_fall; };',
             'struct SerdesModel { const char *type; const SerdesParam *params, *defaults; size_t param_count; const SerdesArc *arcs; size_t arc_count; const int8_t *directions; const bool *clocks; };',
             'const char *const serdes_pin_names[] = {' + ','.join(map(json.dumps, pins)) + '};']
    descriptors = []
    for i, m in enumerate(data['models']):
        names = sorted(m['parameters'])
        for label in ('params', 'defaults'):
            values = m['parameters' if label == 'params' else 'defaults']
            lines.append(f'const SerdesParam serdes_{label}_{i}[] = {{' + ','.join(param(n, values[n]) for n in names) + '};')
        rows = [[a[0], ids[a[1]], ids[a[2]], str(a[3]).lower(), *a[4:]] for a in m['arcs']]
        lines.append(f'const SerdesArc serdes_arcs_{i}[] = {{\n' + ',\n'.join('{' + ','.join(map(str, a)) + '}' for a in rows) + '\n};')
        directions = [0 if m['directions'].get(p) == 'input' else 1 if m['directions'].get(p) == 'output' else -1 for p in pins]
        lines.append(f'const int8_t serdes_directions_{i}[] = {{' + ','.join(map(str, directions)) + '};')
        lines.append(f'const bool serdes_clocks_{i}[] = {{' + ','.join(str(p in m['clocks']).lower() for p in pins) + '};')
        descriptors.append('{' + json.dumps(m['packed_type']) + f',serdes_params_{i},serdes_defaults_{i},{len(names)},serdes_arcs_{i},{len(rows)},serdes_directions_{i},serdes_clocks_{i}' + '}')
    lines.extend(('const SerdesModel serdes_models[] = {' + ','.join(descriptors) + '};', '} // namespace\n'))
    return '\n'.join(lines)


def build(previous, characterization, out, workers):
    before = json.loads(previous.read_text())
    original = Path(before['source'])
    if describe(before['binary']['path']) != before['binary'] or describe(before['source_inventory']['path']) != before['source_inventory']:
        raise ValueError('Previous verified backend changed')
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    data = prepare(characterization)
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'previous': describe(previous),
            'previous_binary': before['binary'], 'helper': describe(__file__), 'workers': workers,
            'scope': 'ALL_358_SERIALIZER_INTRINSIC_CALLBACKS_CLOCK_FAMILY_PHASE_AND_WHOLE_TIMING_PENDING',
            'numerical_timing': 'NOT_QUALIFIED', 'hardware_accessed': False, 'live_full_route_changed': False}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out / (stage + '.exit')).write_text(str(result.returncode) + '\n')
        return stage, result.returncode
    try:
        save(stage='copy-and-patch')
        source = out / 'source'; shutil.copytree(original, source)
        if any(digest(source / n) != sha for n, sha in expected.items()):
            raise ValueError('Copied backend source differs')
        (out / 'serdes-timing-tables.json').write_text(json.dumps(data, indent=2) + '\n')
        header = source / 'himbaechel/uarch/xilinx/xilinx.h'
        text = header.read_text()
        def replace_once(text, old, new):
            if text.count(old) != 1:
                raise ValueError('Unexpected patch anchor: ' + old[:100])
            return text.replace(old, new)
        text = replace_once(text, 'struct Xc7DspTiming;', 'struct Xc7DspTiming;\nstruct Xc7SerdesTiming;')
        anchor = '    std::unique_ptr<Xc7DspTiming> dsp_timing;'
        text = replace_once(text, anchor, anchor + '''
    void initialize_serdes_timing();
    bool serdes_cell_delay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const;
    TimingPortClass serdes_port_class(const CellInfo *cell, IdString port, int &count) const;
    TimingClockingInfo serdes_port_clocking(const CellInfo *cell, IdString port, int index) const;
    std::unique_ptr<Xc7SerdesTiming> serdes_timing;
''')
        header.write_text(text)
        cc = source / 'himbaechel/uarch/xilinx/xilinx.cc'; text = cc.read_text()
        text = replace_once(text, 'struct FFControlSet', CPP + '\nstruct FFControlSet')
        anchor = 'bool XilinxImpl::getCellDelay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const\n{'
        text = replace_once(text, anchor, anchor + '\n    if (serdes_timing && serdes_cell(cell))\n        return serdes_cell_delay(cell, from, to, delay);')
        anchor = 'TimingPortClass XilinxImpl::getPortTimingClass(const CellInfo *cell, IdString port, int &count) const\n{'
        text = replace_once(text, anchor, anchor + '\n    if (serdes_timing && serdes_cell(cell))\n        return serdes_port_class(cell, port, count);')
        anchor = 'TimingClockingInfo XilinxImpl::getPortClockingInfo(const CellInfo *cell, IdString port, int index) const\n{'
        text = replace_once(text, anchor, anchor + '\n    if (serdes_timing && serdes_cell(cell))\n        return serdes_port_clocking(cell, port, index);')
        # The runtime definition must precede the callbacks that dispatch to it.
        text = replace_once(text, CPP + '\nstruct FFControlSet', 'struct FFControlSet')
        text = replace_once(text, 'bool XilinxImpl::getCellDelay(', CPP + '\nbool XilinxImpl::getCellDelay(')
        text = replace_once(text, '    return specific;', '''    specific.add_options()("serdes-vivado-timing", po::value<std::string>(), "experimental exact-part serializer timing: on or off (default off)");
    specific.add_options()("serdes-timing-audit", po::value<std::string>(), "post-pack serializer timing callback audit output");
    return specific;''')
        cc.write_text(text)
        pack = source / 'himbaechel/uarch/xilinx/pack.cc'
        pack.write_text(replace_once(pack.read_text(), '    initialize_dsp_timing();', '    initialize_dsp_timing();\n    initialize_serdes_timing();'))
        (source / 'himbaechel/uarch/xilinx/serdes_timing_data.h').write_text(generate_data(data))
        plan = Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md'
        shutil.copy2(plan, source / 'docs/xilinx-porting/07-phy-timing.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        owner = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-cli-build/himbaechel/CMakeFiles/nextpnr-himbaechel.dir'))
        donor = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-himbaechel'))
        dependencies = {}
        for dep in owner.rglob('*.o.d'):
            fields = shlex.split(dep.read_text().replace('\\\n', ' '))
            if str(donor / 'himbaechel/uarch/xilinx/xilinx.h') in fields:
                basename = Path(fields[1]).name + '.o'
                if basename in dependencies:
                    raise ValueError('Ambiguous header-dependent translation unit')
                dependencies[basename] = (str(Path(fields[1]).relative_to(donor)), describe(dep))
        if len(dependencies) != 14:
            raise ValueError('Header-dependent rebuild set changed')
        objects = out / 'input-objects'; objects.mkdir(); link = []; jobs = []; reused = []
        template = before['compile_plan'][0]['argv']
        for i, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                target = objects / (str(i).zfill(3) + '-' + Path(arg).name)
                selected = next((n for n in dependencies if Path(arg).name == n or Path(arg).name.endswith('-' + n)), None)
                if selected:
                    relative, dep_record = dependencies.pop(selected)
                    argv = [v.replace(str(original), str(source)) for v in template]
                    for flag, value in [('-MF', str(target) + '.d'), ('-o', str(target)), ('-c', str(source / relative))]:
                        argv[argv.index(flag) + 1] = value
                    jobs.append({'source': str(source / relative), 'output': str(target), 'argv': argv, 'dependency_record': dep_record})
                else:
                    shutil.copy2(arg, target)
                    if digest(arg) != digest(target):
                        raise ValueError('Copied link input changed')
                    reused.append({'original': describe(arg), 'copied': describe(target)})
                link.append(str(target))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
            else:
                link.append(arg)
        if dependencies or len(jobs) != 14:
            raise ValueError('Incomplete header-dependent rebuild')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out / 'source.input.json'),
             tables=describe(out / 'serdes-timing-tables.json'), source_delta=[n for n in updated if expected.get(n) != updated[n]],
             compile_plan=jobs, reused_inputs=reused, link_argv=link,
             retained_corrections=[*before.get('retained_corrections', []), 'OPT_IN_CLOCK_FEEDBACK', 'OPT_IN_SERDES_TIMING'])
        print(f'COMPILING {len(jobs)} translation units with {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda item: run('compile-' + str(item[0]).zfill(2), item[1]['argv']), enumerate(jobs)))
        save(compile_results=dict(results))
        if any(code for _, code in results):
            raise RuntimeError('Serializer backend compilation failed')
        save(stage='link'); _, code = run('link', link)
        if code:
            raise RuntimeError('Serializer backend link failed')
        _, code = run('version', [str(out / 'nextpnr-himbaechel'), '--version'])
        if code:
            raise RuntimeError('Serializer backend startup failed')
        if any(digest(original / n) != sha for n, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='SERDES_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING', stage='compiled',
             binary=describe(out / 'nextpnr-himbaechel'), rebuilt_translation_units=[describe(j['output']) for j in jobs],
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); shutil.copy2(__file__, out / 'helper.py'); raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('previous', 'characterization', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.characterization.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
