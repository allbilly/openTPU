#!/usr/bin/env python3
"""Correct the XC7 pinned-DSP LOC handoff using the upstream BEL interface.

Reuse the completed DSP geometry build's unchanged source, headers and objects.
Only the modified xilinx.cc body is recompiled. Every old input is hash checked.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from openxc7_ff_edge import describe, digest


def build(previous, out):
    old = json.loads((previous/'manifest.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    helper=describe(Path(__file__).resolve()), previous=describe(previous/'manifest.json'),
                    scope='XC7 DSP geometry, pinned root LOC-to-BEL handoff and retained FF clock edges; numerical timing and hardware remain unqualified',
                    physical_hardware='NOT_RUN', retained_ff_edge_correction=True)

    def save(**fields):
        manifest.update(fields)
        mp.write_text(json.dumps(manifest, indent=2)+'\n')

    def run(argv, name):
        save(stage=name)
        (out/(name+'.command.json')).write_text(json.dumps(argv, indent=2)+'\n')
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(name+'.exit')).write_text(str(result.returncode)+'\n')
        if result.returncode:
            raise RuntimeError(name+' exited '+str(result.returncode))

    try:
        save(stage='verify-completed-backend')
        if old['status'] != 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED':
            raise RuntimeError('Previous backend did not build successfully')
        inventory = old['source_inventory']
        if digest(inventory['path']) != inventory['sha256']:
            raise RuntimeError('Previous source inventory changed')
        originals = json.loads(Path(inventory['path']).read_text())
        for relative, expected in originals.items():
            if digest(Path(old['source'])/relative) != expected:
                raise RuntimeError('Previous source changed: '+relative)
        source = out/'source'
        shutil.copytree(old['source'], source, symlinks=True)
        cc = source/'himbaechel/uarch/xilinx/xilinx.cc'
        anchor = '''    int placed = 0;
    for (auto &w : wanted) {
        if (w.first->bel == w.second)'''
        replacement = '''    int placed = 0;
    for (auto &w : wanted) {
        // The upstream placer carries the other cluster members along
        // for BEL-constrained roots, including roots bound before placement.
        // A site LOC alone would leave these DSP children without locations.
        if (w.first->type == id_DSP48E1_DSP48E1 && w.first->cluster == w.first->name) {
            if (w.first->constr_abs_z && ctx->getBelLocation(w.second).z != w.first->constr_z)
                log_error("DSP cascade root '%s' LOC conflicts with its absolute z alignment\\n",
                          ctx->nameOf(w.first));
            w.first->attrs[ctx->id("BEL")] = ctx->getBelName(w.second).str(ctx);
        }
        if (w.first->bel == w.second)'''
        text = cc.read_text()
        if text.count(anchor) != 1:
            raise RuntimeError('Unexpected LOC handoff anchor')
        cc.write_text(text.replace(anchor, replacement))
        changes = [relative for relative, expected in originals.items()
                   if digest(source/relative) != expected]
        if changes != ['himbaechel/uarch/xilinx/xilinx.cc']:
            raise RuntimeError('Incremental rebuild changes headers or other files: '+str(changes))
        (out/'source.input.json').write_text(json.dumps(
            {str(p.relative_to(source)):digest(p) for p in source.rglob('*') if p.is_file()}, indent=2)+'\n')
        job = next(j for j in old['compile_plan'] if j['source'].endswith('/xilinx.cc'))
        compile_argv = [a.replace(str(previous), str(out)) for a in job['argv']]
        argv = [a.replace(str(previous), str(out)) for a in old['link_argv']]
        argv[argv.index('-o')+1] = str(out/'nextpnr-himbaechel')
        inputs = []
        for index, arg in enumerate(old['link_argv']):
            path = Path(arg)
            if path.suffix not in ('.o','.a') or not path.is_file():
                continue
            dest = Path(argv[index])
            if dest == path:
                dest = out/'input-objects'/('external-'+str(index)+'-'+path.name)
                argv[index] = str(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['cp','--reflink=auto',str(path),str(dest)], check=True)
            inputs.append(describe(path))
        save(source=str(source), modifications=[describe(cc)], source_inventory=describe(out/'source.input.json'),
             compile_plan=[dict(source=str(cc), output=compile_argv[compile_argv.index('-o')+1], argv=compile_argv)],
             rebuilt_translation_units=1, reused_inputs=inputs, link_argv=argv,
             previous_binary=old['binary'], header_declarations='UNCHANGED_HASH_VERIFIED')
        run(compile_argv, 'compile-xilinx')
        run(argv, 'link')
        if not all(digest(p['path']) == p['sha256'] for p in inputs):
            raise RuntimeError('Previous objects changed while building')
        run([str(out/'nextpnr-himbaechel'),'--version'], 'version')
        save(status='BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED', binary=describe(out/'nextpnr-himbaechel'))
    except Exception as error:
        save(status='FAIL', error=str(error))
        raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())
        print(mp)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--previous', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    build(args.previous.resolve(), args.out.resolve())
