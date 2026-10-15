#!/usr/bin/env python3
"""Build an isolated XC7 64-bit, saturating placement timeout correction."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from openxc7_ff_edge import describe, digest

ROOT = Path(__file__).resolve().parents[1]
BLOCK = '''    // XC7: the common constructor's int square overflows on full designs.
    // Recompute the existing policy without altering the placement algorithm.
    int timeout_divisor = ctx->setting<int>("placerHeap/cellPlacementTimeout", 8);
    int64_t cell_count = ctx->cells.size();
    if (timeout_divisor > 0) {
        int64_t attempts = std::max(int64_t(10000), cell_count * cell_count / timeout_divisor);
        cfg.cell_placement_timeout = int(std::min(attempts, int64_t(std::numeric_limits<int>::max() - 1)));
    } else {
        cfg.cell_placement_timeout = 0;
    }
    log_info("XC7 placement search limit: cells=%lld divisor=%d attempts=%d\\n",
             static_cast<long long>(cell_count), timeout_divisor, cfg.cell_placement_timeout);
'''


def build(previous, out):
    old = json.loads((previous/'manifest.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    helper=describe(Path(__file__).resolve()), previous=describe(previous/'manifest.json'),
                    scope='XC7 timeout arithmetic; unchanged full design and upstream placement algorithms',
                    physical_hardware='NOT_RUN', carry_padding='BUILT_BEHAVIOR_NOT_YET_TESTED',
                    placer_timeout='BUILDING_BEHAVIOR_NOT_YET_TESTED')

    def save(**fields):
        manifest.update(fields)
        mp.write_text(json.dumps(manifest, indent=2)+'\n')

    def run(argv, stage):
        save(stage=stage)
        (out/(stage+'.command.json')).write_text(json.dumps(argv, indent=2)+'\n')
        with (out/(stage+'.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(result.returncode)+'\n')
        if result.returncode:
            raise RuntimeError(stage+' exited '+str(result.returncode))

    try:
        save(stage='verify-completed-backend')
        if old['status'] != 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED':
            raise RuntimeError('Previous build did not pass')
        inventory = old['source_inventory']
        if digest(inventory['path']) != inventory['sha256']:
            raise RuntimeError('Previous inventory changed')
        originals = json.loads(Path(inventory['path']).read_text())
        for relative, expected in originals.items():
            if digest(Path(old['source'])/relative) != expected:
                raise RuntimeError('Previous source changed: '+relative)
        source = out/'source'
        shutil.copytree(old['source'], source, symlinks=True)
        cc = source/'himbaechel/uarch/xilinx/xilinx.cc'
        text = cc.read_text()
        anchor = 'void XilinxImpl::configurePlacerHeap(PlacerHeapCfg &cfg)\n{\n'
        if text.count(anchor) != 1:
            raise RuntimeError('Unexpected configuration anchor')
        cc.write_text(text.replace('#include <map>', '#include <limits>\n#include <map>')
                      .replace(anchor, anchor+BLOCK))
        changes = [r for r, expected in originals.items() if digest(source/r) != expected]
        if changes != ['himbaechel/uarch/xilinx/xilinx.cc']:
            raise RuntimeError('Another source/header changed: '+str(changes))
        plan = source/'docs/xilinx-porting/07-placer-timeout.md'
        shutil.copyfile(ROOT/'docs/openxc7_placer_timeout.md', plan)
        readme = source/'docs/xilinx-porting/README.md'
        readme.write_text(readme.read_text()+'\nSee `07-placer-timeout.md` for the full-design '
                          'overflow capture and XC7-only correction. Full fit remains unproven.\n')
        inventory_path = out/'source.input.json'
        inventory_path.write_text(json.dumps({str(p.relative_to(source)):digest(p)
                                             for p in source.rglob('*') if p.is_file()}, indent=2)+'\n')
        ancestor_path = Path(old['previous']['path'])
        if digest(ancestor_path) != old['previous']['sha256']:
            raise RuntimeError('Compile ancestor changed')
        ancestor = json.loads(ancestor_path.read_text())
        job = next(j for j in ancestor['compile_plan'] if j['source'].endswith('/xilinx.cc'))
        compile_argv = [a.replace(str(ancestor_path.parent), str(out)) for a in job['argv']]
        argv = [a.replace(str(previous), str(out)) for a in old['link_argv']]
        argv[argv.index('-o')+1] = str(out/'nextpnr-himbaechel')
        inputs = []
        for i, arg in enumerate(old['link_argv']):
            path = Path(arg)
            if path.suffix not in ('.o', '.a') or not path.is_file():
                continue
            dest = Path(argv[i])
            if dest == path:
                dest = out/'input-objects'/('external-'+str(i)+'-'+path.name)
                argv[i] = str(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['cp', '--reflink=auto', str(path), str(dest)], check=True)
            inputs.append(describe(path))
        obj = compile_argv[compile_argv.index('-o')+1]
        if obj not in argv:
            raise RuntimeError('New object absent from link command')
        save(source=str(source), modifications=[describe(cc), describe(plan), describe(readme)],
             source_inventory=describe(inventory_path),
             compile_plan=[dict(source=str(cc), output=obj, argv=compile_argv)],
             rebuilt_translation_units=1, reused_inputs=inputs, link_argv=argv,
             previous_binary=old['binary'], header_declarations='UNCHANGED_HASH_VERIFIED',
             retained_corrections=['CARRY_UNUSED_PADDING', 'DSP_CONSECUTIVE_SITES', 'DSP_LOC_TO_BEL', 'FF_CLOCK_EDGE'])
        # Execute the exact inserted configuration body with boundary inputs.
        contract = out/'timeout-contract.cc'
        contract.write_text('''#include <algorithm>
#include <cassert>
#include <cstdint>
#include <cstdio>
#include <limits>
struct Cells { int64_t n; int64_t size() const { return n; } };
struct Context { Cells cells; int divisor; template<typename T> T setting(const char*, int) { return T(divisor); } };
struct Config { int cell_placement_timeout; };
template<typename... Args> void log_info(const char*, Args...) {}
int limit(Context *ctx) { Config cfg;
'''+BLOCK+'''return cfg.cell_placement_timeout; }
int main() {
    struct Case { int64_t cells; int divisor, expected; };
    Case cases[] = {{0,8,10000},{293,8,10731},{46340,8,268424450},
                    {46341,8,268436035},{531351,8,2147483646},
                    {531351,1,2147483646},{531351,1000,282333885},
                    {531351,0,0},{531351,-1,0}};
    for (auto c : cases) { Context ctx{{c.cells},c.divisor}; int attempts=limit(&ctx); assert(attempts==c.expected); if (c.divisor>0) { int next=attempts+1; assert(next>attempts); } }
    puts("TIMEOUT_CONTRACT_PASS cases=9 full_cells=531351 attempts=2147483646");
}
''')
        contract_cxx = shutil.which('clang++') or compile_argv[0]
        run([contract_cxx, '-std=c++17', '-O1', '-fsanitize=undefined',
             '-fno-sanitize-recover=all', str(contract), '-o', str(out/'timeout-contract')], 'compile-timeout-contract')
        run([str(out/'timeout-contract')], 'timeout-contract')
        run(compile_argv, 'compile-xilinx')
        run(argv, 'link')
        if not all(digest(p['path']) == p['sha256'] for p in inputs):
            raise RuntimeError('Reused objects changed during build')
        run([str(out/'nextpnr-himbaechel'), '--version'], 'version')
        save(status='BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED',
             placer_timeout='ARITHMETIC_CONTRACT_PASS_REAL_PLACEMENT_NOT_YET_TESTED',
             arithmetic_contract=dict(cases=9, source=describe(contract), log=describe(out/'timeout-contract.log')),
             binary=describe(out/'nextpnr-himbaechel'))
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
