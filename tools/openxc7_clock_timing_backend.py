#!/usr/bin/env python3
"""Build isolated, opt-in exact-part MMCM/PLL/BUFGCTRL timing callbacks."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import shlex
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_phy_vivado_timing import library_parameters
import openxc7_serdes_timing_backend as serializers


CPP = serializers.CPP.replace('Xc7SerdesTiming', 'Xc7ClockTiming').replace('Serdes', 'Clock').replace('serdes', 'clock').replace('Serializer', 'Clock').replace('serializer', 'clock')
CPP = CPP.replace('#include "clock_timing_data.h"', '#include <cmath>\n#include "clock_timing_data.h"')
CPP = CPP.replace('return cell->type.in(id_ISERDESE2_ISERDESE2, id_OSERDESE2_OSERDESE2);',
                  'return cell->type.in(id_MMCME2_ADV_MMCME2_ADV, id_PLLE2_ADV_PLLE2_ADV, id_BUFGCTRL);')
start = CPP.index('bool clock_parameter_matches(')
end = CPP.index('std::vector<const ClockArc *> clock_clock_arcs', start)
CPP = CPP[:start] + r'''
bool clock_parameter_matches(const CellInfo *cell, const ClockParam &wanted,
                             const ClockParam &fallback)
{
    auto found = cell->params.find(cell->ctx->id(wanted.name));
    if (wanted.is_real) {
        std::string actual = fallback.text;
        if (found != cell->params.end()) {
            const auto &value = found->second;
            if (value.is_string)
                actual = value.str;
            else if (value.is_fully_def() && value.size() <= 64)
                actual = std::to_string(value.as_int64());
            else
                return false;
        }
        try {
            size_t consumed = 0;
            double parsed = std::stod(actual, &consumed), expected = std::stod(wanted.text);
            return consumed == actual.size() && std::isfinite(parsed) && parsed == expected;
        } catch (...) {
            return false;
        }
    }
    if (found == cell->params.end())
        return wanted.is_string == fallback.is_string && (wanted.is_string ?
                std::string(wanted.text) == fallback.text : wanted.number == fallback.number);
    const auto &actual = found->second;
    if (wanted.is_string)
        return actual.is_string && actual.str == wanted.text;
    return !actual.is_string && actual.is_fully_def() && actual.size() <= 64 &&
           actual.as_int64() == wanted.number;
}

''' + CPP[end:]
CPP = CPP.replace('    if (model.clocks[pin])\n        return TMG_CLOCK_INPUT;',
                  '    if (model.clocks[pin])\n        return TMG_CLOCK_INPUT;\n    if (model.generated[pin])\n        return TMG_GEN_CLOCK;')
CPP = CPP.replace('<< dsp_class_name(cls)', '<< (cls == TMG_GEN_CLOCK ? "generated_clock" : dsp_class_name(cls))')
anchor = '        audit << "M\\t" << cell->name.str(ctx) << \'\\t\' << data.cell_model.at(cell->name) << \'\\n\';'
if CPP.count(anchor) != 1:
    raise ValueError('Clock audit anchor changed')
CPP = CPP.replace(anchor, anchor + r'''
        const auto &model = clock_models[data.cell_model.at(cell->name)];
        for (size_t i = 0; i < model.disabled_count; ++i) {
            const auto &record = model.disabled[i];
            DelayQuad delay;
            bool exists = getCellDelay(cell, data.pins[record.from], data.pins[record.to], delay);
            if (exists)
                log_error("Disabled reset arc was incorrectly imported as a propagation delay.\n");
            audit << "D\t" << cell->name.str(ctx) << '\t' << data.pins[record.from].str(ctx)
                  << '\t' << data.pins[record.to].str(ctx) << "\tvendor_disabled_set_clr\t0\n";
        }
''')


def prepare(characterization):
    configs_path = characterization / 'configurations.json'
    raw_path = characterization / 'timing-arcs-compact.json'
    cfg = json.loads(configs_path.read_text()); raw = json.loads(raw_path.read_text())
    semantic = json.loads((characterization / 'semantic-summary.json').read_text())
    if (semantic['parameter_mismatches'] or semantic['nonfinite_delays'] or
            semantic['configs'] != 7 or semantic['full_design_cells'] != 378 or
            (characterization / 'query.exit').read_text().strip() != '0' or
            (characterization / 'semantic-validator.exit').read_text().strip() != '0'):
        raise ValueError('Exact full-design vendor characterization did not pass')
    if raw['part'] != 'xc7k480tffg1156-2' or raw['units'] != 'ns' or describe(raw['source_tsv']['path']) != raw['source_tsv']:
        raise ValueError('Exact-part vendor timing source changed')
    selected = [c for c in cfg['configs'] if c['primitive'] in ('MMCME2_ADV', 'PLLE2_ADV', 'BUFGCTRL')]
    if len(selected) != 4 or sum(len(c['full_design_cells']) for c in selected) != 20:
        raise ValueError('Complete clock-cell scope changed')
    all_pins = set(); models = []
    kinds = {'combinational': 0, 'Reg Clk to Q': 1, 'setup': 2, 'hold': 3}
    for c in selected:
        defaults, record = library_parameters(c['primitive'])
        if record != cfg['library_defaults'][c['primitive']]:
            raise ValueError('Primitive default library changed')
        if c['primitive'] == 'BUFGCTRL':
            defaults['SIM_DEVICE'] = {'kind': 'string', 'value': '7SERIES'}
        else:
            # This is the real packed FASM default, already vendor-validated.
            defaults['COMPENSATION']['value'] = 'INTERNAL'
        if set(defaults) != set(c['parameters']):
            raise ValueError('Complete physical parameter signature changed')
        if any(v['kind'] == 'real' and not Decimal(str(v['value'])).is_finite() for v in c['parameters'].values()):
            raise ValueError('Nonfinite clock parameter')
        pin_map = {}
        for p in c['ports']:
            for bit in range(p['width']):
                raw_pin = p['name'] + (f'[{bit}]' if p['width'] > 1 else '')
                packed_pin = p['name'] + (str(bit) if p['width'] > 1 else '')
                pin_map[raw_pin] = {'packed': packed_pin, 'direction': p['direction']}
                all_pins.add(packed_pin)
        arcs, disabled = [], []
        for a in raw['arcs']:
            if a['cell'] != c['probe_cell']:
                continue
            source, target = pin_map[a['from']]['packed'], pin_map[a['to']]['packed']
            if a['disabled']:
                if a['type'] != 'Reg Set/Clr' or source != 'RST':
                    raise ValueError('Disabled clock arc needs unimplemented semantics')
                disabled.append({'from': source, 'to': target, 'reason': 'vendor_constraint_disabled_set_clr'})
                continue
            if a['type'] not in kinds:
                raise ValueError('Unsupported enabled clock arc')
            kind = kinds[a['type']]; transitions = a['transition'].split(); edges = {t[0] for t in transitions}
            if not transitions or any(t not in ('rr', 'rf', 'fr', 'ff') for t in transitions) or (kind and len(edges) != 1):
                raise ValueError('Unknown clock transition')
            inversion = c['parameters'].get('IS_' + source + '_INVERTED', {'value': 0})['value']
            if inversion not in (0, 1):
                raise ValueError('Malformed clock inversion')
            falling = kind != 0 and (('f' in edges) != bool(inversion))
            arcs.append([kind, source, target, falling, *serializers.bounds(a)])
        arcs.sort(key=lambda a: (a[2], a[1], a[0], a[3]))
        keys = {tuple(a[:4]) for a in arcs}
        if len(keys) != len(arcs) or any(a[0] in (2, 3) and (5 - a[0], *a[1:4]) not in keys for a in arcs):
            raise ValueError('Duplicate or unpaired clock timing check')
        clocks = [] if c['primitive'] == 'BUFGCTRL' else ['CLKIN1', 'CLKIN2', 'CLKFBIN', 'DCLK']
        if c['primitive'] == 'MMCME2_ADV':
            clocks.append('PSCLK')
        generated = [p['packed'] for p in pin_map.values() if p['direction'] == 'output' and
                     (p['packed'].startswith('CLKOUT') or p['packed'].startswith('CLKFBOUT'))]
        models.append({**c, 'defaults': defaults, 'arcs': arcs, 'disabled': disabled,
                       'directions': {p['packed']: p['direction'] for p in pin_map.values()},
                       'pin_map': pin_map, 'clocks': clocks, 'generated': generated})
    if sum(len(m['arcs']) for m in models) != 287 or sum(len(m['disabled']) for m in models) != 7:
        raise ValueError('Complete raw clock timing coverage changed')
    return {'part': raw['part'], 'units': 'ps', 'pins': sorted(all_pins), 'models': models,
            'raw': describe(raw_path), 'configs': describe(configs_path), 'semantic': describe(characterization / 'semantic-summary.json'),
            'enabled_arcs': 287, 'explicit_disabled_arcs': 7, 'full_design_cells': 20, 'numerical_timing': 'NOT_QUALIFIED',
            'serializer_helper': describe(serializers.__file__)}


def generate_data(data):
    pins = data['pins']; ids = {p: i for i, p in enumerate(pins)}
    def param(name, value):
        string, real = value['kind'] in ('string', 'real'), value['kind'] == 'real'
        if value['kind'] not in ('string', 'integer', 'real'):
            raise ValueError('Unknown physical clock parameter kind')
        return '{' + json.dumps(name) + ',' + str(string).lower() + ',' + str(real).lower() + ',' + (
            json.dumps(str(value['value'])) if string else 'nullptr') + ',' + ('0' if string else str(value['value']) + 'LL') + '}'
    lines = ['// Characterized intrinsic clock arcs; generated-clock phases/families remain unqualified.',
             'namespace {',
             'struct ClockParam { const char *name; bool is_string, is_real; const char *text; int64_t number; };',
             'struct ClockArc { unsigned kind, from, to; bool falling; int32_t min_rise, max_rise, min_fall, max_fall; };',
             'struct ClockDisabled { unsigned from, to; };',
             'struct ClockModel { const char *type; const ClockParam *params, *defaults; size_t param_count; const ClockArc *arcs; size_t arc_count; const int8_t *directions; const bool *clocks, *generated; const ClockDisabled *disabled; size_t disabled_count; };',
             'const char *const clock_pin_names[] = {' + ','.join(map(json.dumps, pins)) + '};']
    descriptors = []
    for i, m in enumerate(data['models']):
        names = sorted(m['parameters'])
        for label in ('params', 'defaults'):
            values = m['parameters' if label == 'params' else 'defaults']
            lines.append(f'const ClockParam clock_{label}_{i}[] = {{' + ','.join(param(n, values[n]) for n in names) + '};')
        rows = [[a[0], ids[a[1]], ids[a[2]], str(a[3]).lower(), *a[4:]] for a in m['arcs']]
        lines.append(f'const ClockArc clock_arcs_{i}[] = {{\n' + ',\n'.join('{' + ','.join(map(str, a)) + '}' for a in rows) + '\n};')
        directions = [0 if m['directions'].get(p) == 'input' else 1 if m['directions'].get(p) == 'output' else -1 for p in pins]
        lines.append(f'const int8_t clock_directions_{i}[] = {{' + ','.join(map(str, directions)) + '};')
        for key in ('clocks', 'generated'):
            lines.append(f'const bool clock_{key}_{i}[] = {{' + ','.join(str(p in m[key]).lower() for p in pins) + '};')
        if m['disabled']:
            lines.append(f'const ClockDisabled clock_disabled_{i}[] = {{' + ','.join('{' + str(ids[d['from']]) + ',' + str(ids[d['to']]) + '}' for d in m['disabled']) + '};')
        disabled = f'clock_disabled_{i}' if m['disabled'] else 'nullptr'
        descriptors.append('{' + json.dumps(m['packed_type']) + f',clock_params_{i},clock_defaults_{i},{len(names)},clock_arcs_{i},{len(rows)},clock_directions_{i},clock_clocks_{i},clock_generated_{i},{disabled},{len(m["disabled"])}' + '}')
    lines.extend(('const ClockModel clock_models[] = {' + ','.join(descriptors) + '};', '} // namespace\n'))
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
            'scope': 'ALL_20_CLOCK_INTRINSIC_CALLBACKS_CLOCK_FAMILY_PHASE_AND_WHOLE_TIMING_PENDING',
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
        (out / 'clock-timing-tables.json').write_text(json.dumps(data, indent=2) + '\n')
        header = source / 'himbaechel/uarch/xilinx/xilinx.h'
        text = header.read_text()
        def replace_once(text, old, new):
            if text.count(old) != 1:
                raise ValueError('Unexpected patch anchor: ' + old[:100])
            return text.replace(old, new)
        text = replace_once(text, 'struct Xc7DspTiming;', 'struct Xc7DspTiming;\nstruct Xc7ClockTiming;')
        anchor = '    std::unique_ptr<Xc7DspTiming> dsp_timing;'
        text = replace_once(text, anchor, anchor + '''
    void initialize_clock_timing();
    bool clock_cell_delay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const;
    TimingPortClass clock_port_class(const CellInfo *cell, IdString port, int &count) const;
    TimingClockingInfo clock_port_clocking(const CellInfo *cell, IdString port, int index) const;
    std::unique_ptr<Xc7ClockTiming> clock_timing;
''')
        header.write_text(text)
        cc = source / 'himbaechel/uarch/xilinx/xilinx.cc'; text = cc.read_text()
        text = replace_once(text, 'struct FFControlSet', CPP + '\nstruct FFControlSet')
        anchor = 'bool XilinxImpl::getCellDelay(const CellInfo *cell, IdString from, IdString to, DelayQuad &delay) const\n{'
        text = replace_once(text, anchor, anchor + '\n    if (clock_timing && clock_cell(cell))\n        return clock_cell_delay(cell, from, to, delay);')
        anchor = 'TimingPortClass XilinxImpl::getPortTimingClass(const CellInfo *cell, IdString port, int &count) const\n{'
        text = replace_once(text, anchor, anchor + '\n    if (clock_timing && clock_cell(cell))\n        return clock_port_class(cell, port, count);')
        anchor = 'TimingClockingInfo XilinxImpl::getPortClockingInfo(const CellInfo *cell, IdString port, int index) const\n{'
        text = replace_once(text, anchor, anchor + '\n    if (clock_timing && clock_cell(cell))\n        return clock_port_clocking(cell, port, index);')
        # The runtime definition must precede the callbacks that dispatch to it.
        text = replace_once(text, CPP + '\nstruct FFControlSet', 'struct FFControlSet')
        text = replace_once(text, 'bool XilinxImpl::getCellDelay(', CPP + '\nbool XilinxImpl::getCellDelay(')
        text = replace_once(text, '    return specific;', '''    specific.add_options()("clock-vivado-timing", po::value<std::string>(), "experimental exact-part clock timing: on or off (default off)");
    specific.add_options()("clock-timing-audit", po::value<std::string>(), "post-pack clock timing callback audit output");
    return specific;''')
        cc.write_text(text)
        pack = source / 'himbaechel/uarch/xilinx/pack.cc'
        pack.write_text(replace_once(pack.read_text(), '    initialize_dsp_timing();', '    initialize_dsp_timing();\n    initialize_clock_timing();'))
        (source / 'himbaechel/uarch/xilinx/clock_timing_data.h').write_text(generate_data(data))
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
             tables=describe(out / 'clock-timing-tables.json'), source_delta=[n for n in updated if expected.get(n) != updated[n]],
             compile_plan=jobs, reused_inputs=reused, link_argv=link,
             retained_corrections=[*before.get('retained_corrections', []), 'OPT_IN_CLOCK_FEEDBACK', 'OPT_IN_CLOCK_TIMING'])
        print(f'COMPILING {len(jobs)} translation units with {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda item: run('compile-' + str(item[0]).zfill(2), item[1]['argv']), enumerate(jobs)))
        save(compile_results=dict(results))
        if any(code for _, code in results):
            raise RuntimeError('Clock backend compilation failed')
        save(stage='link'); _, code = run('link', link)
        if code:
            raise RuntimeError('Clock backend link failed')
        _, code = run('version', [str(out / 'nextpnr-himbaechel'), '--version'])
        if code:
            raise RuntimeError('Clock backend startup failed')
        if any(digest(original / n) != sha for n, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='CLOCK_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING', stage='compiled',
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
