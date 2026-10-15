#!/usr/bin/env python3
"""Build an isolated xc7 backend restoring clocks/matrix on placed reload."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess
from fedora_openxc7 import describe, digest


def build(parent, out):
    before = json.loads(parent.read_text())
    for key in ('binary', 'source_inventory'):
        if describe(before[key]['path']) != before[key]:
            raise ValueError('Parent binary or source inventory changed')
    original = Path(before['source'])
    expected = json.loads(Path(before['source_inventory']['path']).read_text())
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'parent': describe(parent), 'parent_binary': before['binary'],
            'helper': describe(__file__), 'hardware_accessed': False,
            'original_jobs_changed': False, 'scope': 'XC7_PLACED_REPLAY_CLOCK_AND_MATRIX_RESTORE',
            'allowed_cpus': sorted(os.sched_getaffinity(0)), 'compile_units': 1,
            'full_route_started': False, 'timing_signoff': False}

    def save(**values):
        info.update(values)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def run(stage, argv):
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            f = (Path('/proc') / str(child.pid) / 'stat').read_text().split(') ', 1)[1].split()
            save(stage=stage, native_pid=child.pid, native_start_ticks=int(f[19]))
            print(stage.upper() + '_STARTED PID ' + str(child.pid), flush=True)
            code = child.wait()
        (out / (stage + '.exit')).write_text(str(code) + '\n')
        if code:
            raise RuntimeError(stage + ' failed: ' + str(code))

    try:
        save(stage='copy-and-patch')
        source = out / 'source'
        shutil.copytree(original, source)
        if any(digest(source / name) != value for name, value in expected.items()):
            raise ValueError('Source copy differs')
        target = source / 'himbaechel/uarch/xilinx/xilinx.cc'
        text = target.read_text()
        include = '#include "xilinx.h"'
        if text.count(include) != 1 or '#include "pack.h"' in text:
            raise ValueError('Unexpected Xilinx header layout')
        text = text.replace(include, include + '\n#include "pack.h"')
        option = '    specific.add_options()("fasm", po::value<std::string>(), "fasm bitstream output file");'
        if text.count(option) != 1:
            raise ValueError('Unexpected replay audit option anchor')
        text = text.replace(option, option + '\n    specific.add_options()("placed-replay-bindings", po::value<std::string>(), "optional exact native binding audit prefix");\n    specific.add_options()("placed-replay-clock-xdc", po::value<std::string>(), "clock-only constraints for an already placed design");')
        binding_dump = r'''
void generate_xc7_clock_waveforms(Context *ctx);
void import_xc7_software_phase_contract(Context *ctx);
void import_mailbox_datapath_limits(Context *ctx);

static void dump_placed_replay_bindings(Context *ctx, const std::string &path)
{
    std::ofstream stream(path);
    if (!stream)
        log_error("Cannot open placed replay binding audit.\n");
    stream << "cell\tbel\n";
    for (const auto &entry : ctx->cells) {
        const CellInfo *ci = entry.second.get();
        if (ci->type.in(id_PSEUDO_GND, id_PSEUDO_VCC))
            continue;
        if (ci->bel == BelId())
            log_error("Placed replay has an unbound cell '%s'.\n", ctx->nameOf(ci));
        std::string name = ci->name.str(ctx);
        if (name.find_first_of("\t\r\n") != std::string::npos)
            log_error("Unsupported control character in placed replay cell name.\n");
        stream << name << '\t' << ctx->nameOfBel(ci->bel) << '\n';
    }
    stream.flush();
    if (!stream)
        log_error("Placed replay binding audit write failed.\n");
}

'''
        text = text.replace('void XilinxImpl::preRoute()', binding_dump + 'void XilinxImpl::preRoute()', 1)
        start = text.index('void XilinxImpl::preRoute()')
        end = text.index('\n}', start) + 2
        body = text[start:end]
        anchor = '    }\n    find_source_sink_locs();'
        if body.count(anchor) != 1 or 'generate_constraints()' in body or 'build_delay_matrix()' in body:
            raise ValueError('Unexpected placed replay implementation')
        matrix_start = text.index('    const ArchArgs &dm_args = ctx->args;')
        matrix_end = text.index('    apply_loc_constraints();', matrix_start)
        matrix = text[matrix_start:matrix_end]
        if matrix.count('build_delay_matrix();') != 1:
            raise ValueError('Original measured-matrix code differs')
        restore = ('        // A loaded placement has BELs, but generated clocks and the\n'
                   '        // in-memory measured delay matrix are not serialized in JSON.\n'
                   '        if (ctx->args.options.count("placed-replay-clock-xdc"))\n'
                   '            parse_xdc(ctx->args.options["placed-replay-clock-xdc"].as<std::string>());\n'
                   '        else if (ctx->args.options.count("xdc"))\n'
                   '            log_error("Loaded placement requires explicit clock-only replay XDC.\\n");\n'
                   '        XilinxPacker(ctx, this).generate_constraints();\n'
                   '        initialize_dsp_timing();\n'
                   '        initialize_clock_timing();\n'
                   '        initialize_serdes_timing();\n'
                   '        generate_xc7_clock_waveforms(ctx);\n'
                   '        import_xc7_software_phase_contract(ctx);\n'
                   '        import_mailbox_datapath_limits(ctx);\n'
                   '        log_info("Placed replay: generated clocks restored.\\n");\n'
                   + ''.join('    ' + line if line.strip() else line for line in matrix.splitlines(True)))
        body = body.replace(anchor, restore + anchor)
        body = body.replace('    find_source_sink_locs();',
            '    if (ctx->args.options.count("placed-replay-bindings"))\n'
            '        dump_placed_replay_bindings(ctx, ctx->args.options["placed-replay-bindings"].as<std::string>() + ".before.tsv");\n'
            '    find_source_sink_locs();')
        text = text[:start] + body + text[end:]
        post_start = text.index('void XilinxImpl::postRoute()')
        post_end = text.index('\n}', post_start) + 2
        post = text[post_start:post_end]
        post_anchor = '    const ArchArgs &args = ctx->args;'
        if post.count(post_anchor) != 1:
            raise ValueError('Unexpected post-route audit anchor')
        post = post.replace(post_anchor, post_anchor + '\n'
            '    if (args.options.count("placed-replay-bindings"))\n'
            '        dump_placed_replay_bindings(ctx, args.options["placed-replay-bindings"].as<std::string>() + ".after.tsv");')
        text = text[:post_start] + post + text[post_end:]
        target.write_text(text)
        inventory = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
        delta = [name for name in inventory if inventory[name] != expected.get(name)]
        if delta != ['himbaechel/uarch/xilinx/xilinx.cc']:
            raise ValueError('Unexpected source delta: ' + repr(delta))
        (out / 'source.input.json').write_text(json.dumps(inventory, indent=2) + '\n')
        objects = out / 'input-objects'
        objects.mkdir()
        templates = {Path(j['source']).name: j['argv'] for j in before['compile_plan']}
        link, reused, changed = [], [], []
        for index, arg in enumerate(before['link_argv']):
            if arg.endswith(('.o', '.a')) and Path(arg).is_file():
                destination = objects / (str(index).zfill(3) + '-' + Path(arg).name)
                if Path(arg).name.endswith('xilinx.cc.o'):
                    argv = [v.replace(str(original), str(source)) for v in templates['xilinx.cc']]
                    for flag, value in [('-MF', str(destination) + '.d'), ('-o', str(destination)), ('-c', str(target))]:
                        argv[argv.index(flag) + 1] = value
                    changed.append({'source': str(target), 'output': str(destination), 'argv': argv})
                else:
                    shutil.copy2(arg, destination)
                    if digest(arg) != digest(destination):
                        raise ValueError('Reused link input differs')
                    reused.append({'original': describe(arg), 'copied': describe(destination)})
                link.append(str(destination))
            elif arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file=' + str(out / 'link.d'))
            else:
                link.append(arg)
        if len(changed) != 1:
            raise ValueError('Exactly one xc7 translation unit must change')
        link[link.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        save(source=str(source), source_inventory=describe(out / 'source.input.json'),
             source_delta=delta, compile_plan=changed, reused_inputs=reused, link_argv=link)
        run('compile', changed[0]['argv'])
        run('link', link)
        run('version', [str(out / 'nextpnr-himbaechel'), '--version'])
        if any(digest(source / name) != value for name, value in inventory.items()):
            raise ValueError('Candidate source changed during build')
        save(status='PLACED_REPLAY_BACKEND_BUILD_PASS_FIXTURE_PENDING',
             binary=describe(out / 'nextpnr-himbaechel'),
             rebuilt_translation_units=[describe(changed[0]['output'])],
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parent', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    build(args.parent.resolve(), args.out.resolve())
