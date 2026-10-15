#!/usr/bin/env python3
"""Build an isolated xc7 falling-edge timing correction from local inputs.

Reuse the installed donor's compiler flags and unchanged object files. Rebuild
every translation unit depending on the modified Xilinx class declaration.
The donor, chipdb, current full-design build and physical hardware are untouched.
"""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
DONOR = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb'))
SOURCE = DONOR/'nextpnr-himbaechel'
BUILD = DONOR/'nextpnr-cli-build'
OWNER = BUILD/'himbaechel/CMakeFiles/nextpnr-himbaechel.dir'
REVISION = 'c68c13582e972292c86a5025140d52e713384cbc'


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            h.update(block)
    return h.hexdigest()


def describe(path):
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest(path))


def build(out):
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(status='RUNNING', scope='xc7 fabric FF clock-edge semantics only; numerical delays, hard-cell models and full board timing remain unqualified',
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    physical_hardware='NOT_RUN', helper=describe(Path(__file__).resolve()))
    mp = out/'manifest.json'

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
        save()
        revision = subprocess.check_output(['git', '-C', str(SOURCE), 'rev-parse', 'HEAD'], text=True).strip()
        dirty = subprocess.check_output(['git', '-C', str(SOURCE), 'status', '--porcelain'], text=True)
        if revision != REVISION or dirty:
            raise RuntimeError('Donor revision or worktree differs from the checked baseline')
        source = out/'source'
        shutil.copytree(SOURCE, source, symlinks=True,
                        ignore=shutil.ignore_patterns('.git', '__pycache__'))
        original_hashes = {str(p.relative_to(source)):digest(p) for p in source.rglob('*') if p.is_file()}
        (out/'source.original.json').write_text(json.dumps(original_hashes, indent=2)+'\n')
        header = source/'himbaechel/uarch/xilinx/xilinx.h'
        cc = source/'himbaechel/uarch/xilinx/xilinx.cc'
        old_header = '    void configurePlacerHeap(PlacerHeapCfg &cfg) override;'
        declaration = '    TimingClockingInfo getPortClockingInfo(const CellInfo *cell, IdString port, int index) const override;\n\n'
        text = header.read_text()
        if text.count(old_header) != 1 or 'getPortClockingInfo' in text:
            raise RuntimeError('Unexpected Xilinx timing API declaration')
        header.write_text(text.replace(old_header, declaration+old_header))
        anchor = 'void XilinxImpl::configurePlacerHeap(PlacerHeapCfg &cfg)'
        implementation = '''TimingClockingInfo XilinxImpl::getPortClockingInfo(const CellInfo *cell, IdString port, int index) const
{
    auto info = HimbaechelAPI::getPortClockingInfo(cell, port, index);
    // Packing retains IS_C_INVERTED; the default SLICE_FFX chipdb arcs use
    // the non-inverted CK edge. Apply inversion to every CK-associated
    // input/output timing check, preserving all numerical delay bounds.
    if (cell->type == id_SLICE_FFX && info.clock_port == id_CK &&
        int_or_default(cell->params, id_IS_C_INVERTED, 0) == 1)
        info.edge = info.edge == RISING_EDGE ? FALLING_EDGE : RISING_EDGE;
    return info;
}

'''
        text = cc.read_text()
        if text.count(anchor) != 1:
            raise RuntimeError('Unexpected Xilinx implementation anchor')
        cc.write_text(text.replace(anchor, implementation+anchor))
        save(revision=revision, source=str(source), source_original_manifest=describe(out/'source.original.json'),
             modifications=[describe(header), describe(cc)], donor_binary=describe(BUILD/'nextpnr-himbaechel'))
        flags = {}
        for line in (OWNER/'flags.make').read_text().splitlines():
            if line.startswith(('CXX_DEFINES =', 'CXX_INCLUDES =', 'CXX_FLAGS =')):
                key, value = line.split('=', 1)
                flags[key.strip()] = shlex.split(value)
        options = flags['CXX_DEFINES']+flags['CXX_INCLUDES']+flags['CXX_FLAGS']
        options = [x.replace(str(SOURCE), str(source)) for x in options]
        original_link = shlex.split((OWNER/'link.txt').read_text())
        link = []; compiles = []; inputs = []
        for index, arg in enumerate(original_link):
            if arg.startswith('-Wl,--dependency-file='):
                link.append('-Wl,--dependency-file='+str(out/'link.d'))
                continue
            if index and original_link[index-1] == '-o':
                link.append(str(out/'nextpnr-himbaechel'))
                continue
            candidate = (BUILD/'himbaechel'/arg).resolve()
            if candidate.suffix not in ('.o', '.a') or not candidate.is_file():
                link.append(arg)
                continue
            dest = out/'input-objects'/candidate.relative_to(BUILD)
            dest.parent.mkdir(parents=True, exist_ok=True)
            inputs.append(describe(candidate))
            dep = Path(str(candidate)+'.d')
            if candidate.suffix == '.o' and not dep.is_file():
                raise RuntimeError('Missing dependency record: '+str(dep))
            dependencies = shlex.split(dep.read_text().replace('\\\n', ' ')) if dep.is_file() else []
            if str(SOURCE/'himbaechel/uarch/xilinx/xilinx.h') in dependencies:
                original_cc = Path(dependencies[1])
                if original_cc.suffix != '.cc':
                    raise RuntimeError('Unexpected translation unit: '+str(original_cc))
                selected_cc = source/original_cc.relative_to(SOURCE)
                argv = [original_link[0]]+options+['-MMD', '-MF', str(dest)+'.d', '-o', str(dest), '-c', str(selected_cc)]
                compiles.append(dict(source=str(selected_cc), output=str(dest), argv=argv))
            else:
                subprocess.run(['cp', '--reflink=auto', '--preserve=timestamps', str(candidate), str(dest)], check=True)
            link.append(str(dest))
        if not compiles or not any(c['source'].endswith('/xilinx.cc') for c in compiles):
            raise RuntimeError('No complete Xilinx-dependent rebuild set identified')
        save(inputs=inputs, compile_plan=compiles, rebuilt_translation_units=len(compiles), link_argv=link)
        for index, job in enumerate(compiles):
            run(job['argv'], 'compile-'+str(index).zfill(2))
        run(link, 'link')
        if any(digest(p['path']) != p['sha256'] for p in inputs):
            raise RuntimeError('Donor object changed while building')
        run([str(out/'nextpnr-himbaechel'), '--version'], 'version')
        save(status='BACKEND_BUILD_PASS_CLOCK_EDGE_BEHAVIOR_NOT_YET_TESTED',
             binary=describe(out/'nextpnr-himbaechel'))
    except Exception as error:
        save(status='FAIL', error=str(error))
        raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())
        print(mp)


def relink(previous, out):
    """Recover a completed object build without replaying its compilation."""
    old = json.loads((previous/'manifest.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    recovered_from=describe(previous/'manifest.json'),
                    helper=describe(Path(__file__).resolve()), source=old['source'],
                    scope=old['scope'], physical_hardware='NOT_RUN',
                    compiled_translation_units_reused=old['rebuilt_translation_units'])

    def save(**fields):
        manifest.update(fields)
        mp.write_text(json.dumps(manifest, indent=2)+'\n')

    try:
        save(stage='verify-completed-inputs')
        assert (previous/'link.exit').read_text().strip()=='0'
        for index, job in enumerate(old['compile_plan']):
            assert (previous/('compile-'+str(index).zfill(2)+'.exit')).read_text().strip()=='0'
            assert Path(job['output']).is_file()
        original = old['source_original_manifest']
        assert digest(original['path'])==original['sha256']
        originals = json.loads(Path(original['path']).read_text())
        changed = {p['path']:p['sha256'] for p in old['modifications']}
        for relative, expected in originals.items():
            path = Path(old['source'])/relative
            assert digest(path)==changed.get(str(path), expected), str(path)
        assert all(digest(p['path'])==p['sha256'] for p in old['inputs'])
        argv = list(old['link_argv'])
        argv[argv.index('-o')+1] = str(out/'nextpnr-himbaechel')
        argv = ['-Wl,--dependency-file='+str(out/'link.d') if
                p.startswith('-Wl,--dependency-file=') else p for p in argv]
        inputs = [describe(Path(p)) for p in argv if Path(p).suffix in ('.o', '.a')]
        save(stage='link', reused_objects=inputs, link_argv=argv,
             modifications=old['modifications'], donor_binary=old['donor_binary'])
        for name, command in [('link', argv), ('version', [str(out/'nextpnr-himbaechel'), '--version'])]:
            save(stage=name)
            (out/(name+'.command.json')).write_text(json.dumps(command, indent=2)+'\n')
            with (out/(name+'.log')).open('w') as log:
                result = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            (out/(name+'.exit')).write_text(str(result.returncode)+'\n')
            if result.returncode:
                raise RuntimeError(name+' exited '+str(result.returncode))
        assert all(digest(p['path'])==p['sha256'] for p in inputs)
        save(status='BACKEND_BUILD_PASS_CLOCK_EDGE_BEHAVIOR_NOT_YET_TESTED',
             binary=describe(out/'nextpnr-himbaechel'))
    except Exception as error:
        save(status='FAIL', error=str(error))
        raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())
        print(mp)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--relink-from', type=Path, help='reuse the completed, checked objects from an earlier run')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = (args.out or ROOT/'build/fedora-openxc7'/('ff-edge-backend-'+stamp)).resolve()
    if args.relink_from:
        relink(args.relink_from.resolve(), out)
    else:
        build(out)
