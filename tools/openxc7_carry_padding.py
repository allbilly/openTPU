#!/usr/bin/env python3
"""Build an isolated XC7 splitter that omits unobserved trailing carry bits.

Retain the verified DSP geometry, LOC handoff and FF-edge corrections.
Rebuild pack_carry.cc only; verify all reused headers, sources and objects.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from openxc7_ff_edge import describe, digest

ROOT = Path(__file__).resolve().parents[1]


def build(previous, out):
    old = json.loads((previous/'manifest.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    helper=describe(Path(__file__).resolve()), previous=describe(previous/'manifest.json'),
                    scope='XC7 unobservable carry padding; retain full compute, DDR and validated DSP/LOC/FF fixes',
                    physical_hardware='NOT_RUN', carry_padding='BUILDING_BEHAVIOR_NOT_YET_TESTED')

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
        cc = source/'himbaechel/uarch/xilinx/pack_carry.cc'
        text = cc.read_text()
        anchor = '    for (CellInfo *ci : carry4s) {\n        NetInfo *cin = ci->getPort(id_CI);'
        replacement = '''    int omitted_bits = 0;
    for (CellInfo *ci : carry4s) {
        // Keep every stage needed by a consumed sum/carry output. In
        // particular, CO[3] feeding another CARRY4 preserves all four.
        // Unused upper padding must not become a separate dead cluster
        // when an observable intermediate CO leaves through the fabric.
        int used_bits = 0;
        for (int i = 0; i < 4; i++) {
            NetInfo *o = ci->getPort(ctx->idf("O[%d]", i));
            NetInfo *co = ci->getPort(ctx->idf("CO[%d]", i));
            if ((o && !o->users.empty()) || (co && !co->users.empty()))
                used_bits = i + 1;
        }
        omitted_bits += 4 - used_bits;
        NetInfo *cin = ci->getPort(id_CI);'''
        if text.count(anchor) != 1:
            raise RuntimeError('Unexpected carry splitter anchor')
        text = text.replace(anchor, replacement)
        start = text.index('void XilinxPacker::split_carry4s()')
        end = text.index('void XC7Packer::pack_carries()', start)
        body = text[start:end]
        loop = '        for (int i = 0; i < 4; i++) {\n            CellInfo *xorcy'
        if body.count(loop) != 1:
            raise RuntimeError('Unexpected carry stage loop')
        body = body.replace(loop, '        for (int i = 0; i < used_bits; i++) {\n            CellInfo *xorcy')
        body = body.replace('    flush_cells();',
                            '    flush_cells();\n    log_info("   Omitted %d unobserved trailing carry stages\\n", omitted_bits);')
        cc.write_text(text[:start]+body+text[end:])
        changes = [relative for relative, expected in originals.items()
                   if digest(source/relative) != expected]
        if changes != ['himbaechel/uarch/xilinx/pack_carry.cc']:
            raise RuntimeError('Incremental correction changed another source/header: '+str(changes))
        plan = source/'docs/xilinx-porting/06-carry-padding.md'
        shutil.copyfile(ROOT/'docs/openxc7_carry_padding.md', plan)
        readme = source/'docs/xilinx-porting/README.md'
        readme.write_text(readme.read_text()+'\n## Additional board-port evidence\n\n'
                          'See `06-carry-padding.md` for the full OpenTPU unused-tail capture,\n'
                          'isolated correction and required verification. Hardware and numerical\n'
                          'timing qualification remain incomplete.\n')
        (out/'source.input.json').write_text(json.dumps(
            {str(p.relative_to(source)):digest(p) for p in source.rglob('*') if p.is_file()}, indent=2)+'\n')
        ancestor_path = Path(old['previous']['path'])
        if digest(ancestor_path) != old['previous']['sha256']:
            raise RuntimeError('Recorded compile-plan ancestor changed')
        ancestor = json.loads(ancestor_path.read_text())
        job = next(j for j in ancestor['compile_plan'] if j['source'].endswith('/pack_carry.cc'))
        compile_argv = [a.replace(str(ancestor_path.parent), str(out)) for a in job['argv']]
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
        obj = compile_argv[compile_argv.index('-o')+1]
        if obj not in argv:
            raise RuntimeError('New carry object is absent from link command')
        save(source=str(source), modifications=[describe(cc), describe(plan), describe(readme)],
             source_inventory=describe(out/'source.input.json'),
             compile_plan=[dict(source=str(cc), output=obj, argv=compile_argv)],
             rebuilt_translation_units=1, reused_inputs=inputs, link_argv=argv,
             previous_binary=old['binary'], header_declarations='UNCHANGED_HASH_VERIFIED',
             retained_corrections=['DSP_CONSECUTIVE_SITES','DSP_LOC_TO_BEL','FF_CLOCK_EDGE'])
        run(compile_argv, 'compile-carry')
        run(argv, 'link')
        if not all(digest(p['path']) == p['sha256'] for p in inputs):
            raise RuntimeError('Previous objects changed while building')
        run([str(out/'nextpnr-himbaechel'),'--version'], 'version')
        save(status='BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED',
             carry_padding='BUILT_BEHAVIOR_NOT_YET_TESTED', binary=describe(out/'nextpnr-himbaechel'))
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
