#!/usr/bin/env python3
"""Build an isolated exporter for actual unplaced nominal timing paths."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest


EXPORT_CPP = r'''
            if (ctx->args.options.count("phase-path-audit")) {
                using json11::Json;
                auto endpoint = [&](const std::pair<IdString, IdString> &pin) {
                    Json::object value{{"cell", pin.first.str(ctx)}, {"port", pin.second.str(ctx)}};
                    auto found = ctx->cells.find(pin.first);
                    if (found == ctx->cells.end())
                        return value;
                    const auto &cell = *found->second;
                    value["type"] = cell.type.str(ctx);
                    Json::object attrs, ports, params;
                    for (const auto &attr : cell.attrs)
                        attrs[attr.first.str(ctx)] = attr.second.to_string();
                    for (const auto &param : cell.params)
                        params[param.first.str(ctx)] = param.second.to_string();
                    for (const auto &port : cell.ports)
                        ports[port.first.str(ctx)] = port.second.net ? port.second.net->name.str(ctx) : "";
                    value["attributes"] = attrs;
                    value["parameters"] = params;
                    value["connections"] = ports;
                    return value;
                };
                auto path_json = [&](const CriticalPath &path, const char *kind) {
                    Json::array segments;
                    for (const auto &segment : path.segments) {
                        segments.push_back(Json::object{
                            {"type", CriticalPath::Segment::type_to_str(segment.type)},
                            {"delay_ps", double(segment.delay)},
                            {"net", segment.net.str(ctx)},
                            {"from", endpoint(segment.from)}, {"to", endpoint(segment.to)}});
                    }
                    return Json::object{
                        {"kind", kind}, {"launch", path.clock_pair.start.clock.str(ctx)},
                        {"launch_edge", path.clock_pair.start.edge == RISING_EDGE ? "rising" : "falling"},
                        {"capture", path.clock_pair.end.clock.str(ctx)},
                        {"capture_edge", path.clock_pair.end.edge == RISING_EDGE ? "rising" : "falling"},
                        {"requirement_ps", double(path.max_delay)}, {"segments", segments}};
                };
                const auto &result = analyser.get_timing_result();
                Json::array paths;
                for (const auto &path : result.clock_paths)
                    paths.push_back(path_json(path.second, "single-clock-critical"));
                for (const auto &path : result.xclock_paths)
                    paths.push_back(path_json(path, "cross-clock-critical"));
                Json output = Json::object{
                    {"scope", "UNPLACED_INTRINSIC_ONLY_NOT_ROUTED_TIMING"},
                    {"coverage", "ONE_WORST_PATH_PER_REPORTED_DOMAIN_PAIR_NOT_ALL_CDC_ENDPOINTS"},
                    {"paths", paths}};
                std::string filename = ctx->args.options["phase-path-audit"].as<std::string>();
                if (std::ifstream(filename).good())
                    log_error("Phase-path audit output already exists.\n");
                std::ofstream stream(filename);
                stream << output.dump() << '\n';
                stream.close();
                if (!stream)
                    log_error("Cannot write unplaced phase-path audit.\n");
                log_info("Exported %zu actual unplaced critical paths; exhaustive CDC and routed timing remain pending.\n", paths.size());
            }
'''


def build(previous: Path, out: Path, workers: int):
    before = json.loads(previous.read_text())
    if before['status'] != 'PHASE_ENGINE_BUILD_PASS_NATIVE_ANALYSER_VALIDATION_PENDING':
        raise ValueError('Expected completed phase engine')
    for field in ('binary', 'source_inventory'):
        if describe(before[field]['path']) != before[field]:
            raise ValueError('Previous ' + field + ' changed')
    original = Path(before['source'])
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'previous': describe(previous), 'helper': describe(__file__), 'workers': workers,
            'scope': 'UNPLACED_PATH_PROVENANCE_NOT_ROUTED_TIMING_OR_EXHAUSTIVE_CDC',
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
        xilinx = source / 'himbaechel/uarch/xilinx'
        p = xilinx / 'pack.cc'
        text = '#include <fstream>\n#include "json11.hpp"\n' + p.read_text()
        text = replace(text, '    if (probe == "on") {', '''    if (ctx->args.options.count("phase-path-audit") && probe != "on")
        log_error("phase-path-audit requires phase-analysis-after-pack=on.\\n");
    if (probe == "on") {''')
        text = replace(text, '            analyser.setup(false, false, true);',
                       '            analyser.setup(false, false, true);\n' + EXPORT_CPP)
        p.write_text(text)
        p = xilinx / 'xilinx.cc'
        p.write_text(replace(p.read_text(), '    return specific;',
                            '    specific.add_options()("phase-path-audit", po::value<std::string>(), "actual unplaced phase path and source audit");\n    return specific;'))
        shutil.copy2(Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md',
                     source / 'docs/xilinx-porting/10-unplaced-path-audit.md')
        updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        changed = {name for name in updated if name.endswith(('.h', '.cc')) and expected.get(name) != updated[name]}
        required = {'himbaechel/uarch/xilinx/pack.cc', 'himbaechel/uarch/xilinx/xilinx.cc'}
        if changed != required:
            raise ValueError('Unexpected source rebuild scope')
        objects = out / 'input-objects'
        objects.mkdir()
        link, jobs, reused = [], [], []
        template = before['compile_plan'][0]['argv']
        selected = {Path(name).name + '.o': name for name in required}
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
        if selected or len(jobs) != 2:
            raise ValueError('Incomplete isolated rebuild')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(stage='compile', source=str(source), source_inventory=describe(out / 'source.input.json'),
             compile_plan=jobs, link_argv=link, reused_inputs=reused,
             source_delta=sorted(name for name in updated if expected.get(name) != updated[name]))
        print(f'COMPILING {len(jobs)} changed files with up to {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(lambda item: run('compile-' + str(item[0]), item[1]['argv']), enumerate(jobs)))
        save(compile_results=results)
        if any(results.values()):
            raise RuntimeError('Path exporter compilation failed')
        for stage, argv in (('link', link), ('version', [str(out / 'nextpnr-himbaechel'), '--version'])):
            save(stage=stage)
            _, code = run(stage, argv)
            if code:
                raise RuntimeError(stage + ' failed')
        if any(digest(original / name) != sha for name, sha in expected.items()) or describe(before['binary']['path']) != before['binary']:
            raise ValueError('Previous backend changed during build')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='UNPLACED_PATH_EXPORT_BUILD_PASS_NATIVE_VALIDATION_PENDING',
             binary=describe(out / 'nextpnr-himbaechel'), completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight compiler workers')
    build(args.previous.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
