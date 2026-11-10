#!/usr/bin/env python3
"""Build an isolated XC7 DSP-site placement correction, retaining FF edges.

Start from the hash-checked FF correction's source snapshot and frozen build
plan. Recompile its complete Xilinx-header dependency set; reuse unchanged
objects and compiler options. Never modify the donor or earlier build inputs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from openxc7_ff_edge import ROOT, describe, digest


def replace_once(path, old, new):
    text = path.read_text()
    if text.count(old) != 1:
        raise RuntimeError('Unexpected source anchor in '+str(path))
    path.write_text(text.replace(old, new))


def patch(source):
    header = source/'himbaechel/uarch/xilinx/xilinx.h'
    cc = source/'himbaechel/uarch/xilinx/xilinx.cc'
    replace_once(header, '    void configurePlacerHeap(PlacerHeapCfg &cfg) override;', '''    // Consecutive absolute DSP sites can straddle a clock-row tile gap.
    dict<BelId, BelId> dsp_cascade_next;
    bool getClusterPlacement(ClusterId cluster, BelId root_bel,
                             std::vector<std::pair<CellInfo *, BelId>> &placement) const override;

    void configurePlacerHeap(PlacerHeapCfg &cfg) override;''')
    replace_once(cc, '#include <queue>', '#include <map>\n#include <queue>')
    replace_once(cc, '    // Resolve the repeated-name bel types once', '''    std::map<std::pair<int, int>, BelId> dsps_by_site;

    // Resolve the repeated-name bel types once''')
    replace_once(cc, '        IdString bel_type = ctx->getBelType(bel);', '''        IdString bel_type = ctx->getBelType(bel);
        if (bel_type == id_DSP48E1_DSP48E1) {
            const auto site = get_bel_site(bel);
            const auto &data = tile_extra_data(site.tile)->sites[site.site];
            const bool inserted = dsps_by_site.emplace(std::make_pair(data.site_x, data.site_y), bel).second;
            NPNR_ASSERT(inserted);
        }''')
    replace_once(cc, '    tile_status.resize(ctx->chip_info->tile_insts.size());', '''    for (const auto &entry : dsps_by_site) {
        auto next = dsps_by_site.find(std::make_pair(entry.first.first, entry.first.second + 1));
        if (next != dsps_by_site.end())
            dsp_cascade_next.emplace(entry.second, next->second);
    }

    tile_status.resize(ctx->chip_info->tile_insts.size());''')
    replace_once(cc, 'void XilinxImpl::configurePlacerHeap(PlacerHeapCfg &cfg)', '''bool XilinxImpl::getClusterPlacement(ClusterId cluster, BelId root_bel,
                                      std::vector<std::pair<CellInfo *, BelId>> &placement) const
{
    CellInfo *root_cell = ctx->getClusterRootCell(cluster);
    if (root_cell->type != id_DSP48E1_DSP48E1)
        return HimbaechelAPI::getClusterPlacement(cluster, root_bel, placement);

    placement.clear();
    NPNR_ASSERT(root_bel != BelId());
    Loc root_loc = ctx->getBelLocation(root_bel);
    if (root_cell->constr_abs_z) {
        root_loc.z = root_cell->constr_z;
        root_bel = ctx->getBelByLocation(root_loc);
    }
    if (root_bel == BelId() || !ctx->isValidBelForCellType(root_cell->type, root_bel))
        return false;
    placement.emplace_back(root_cell, root_bel);

    // The packer appends DSP children in cascade order. Nominal -5 tile
    // offsets are useful estimates, but do not include intervening HCLK
    // rows. The database's absolute site coordinates describe the real
    // consecutive DSPs, including both BELs in each DSP_L/DSP_R tile.
    BelId previous = root_bel;
    for (auto child : root_cell->constr_children) {
        const auto next = dsp_cascade_next.find(previous);
        if (next == dsp_cascade_next.end() || !ctx->isValidBelForCellType(child->type, next->second))
            return false;
        placement.emplace_back(child, next->second);
        previous = next->second;
    }
    return true;
}

void XilinxImpl::configurePlacerHeap(PlacerHeapCfg &cfg)''')
    return [describe(header), describe(cc)]


def build(previous, out):
    old = json.loads((previous/'manifest.json').read_text())
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    helper=describe(Path(__file__).resolve()), previous=describe(previous/'manifest.json'),
                    scope='XC7 DSP cluster geometry and retained fabric FF edge semantics; numerical timing and hardware remain unqualified',
                    physical_hardware='NOT_RUN')

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
        save(stage='verify-source-and-build-plan')
        original = old['source_original_manifest']
        if digest(original['path']) != original['sha256']:
            raise RuntimeError('Original source inventory changed')
        originals = json.loads(Path(original['path']).read_text())
        changed = {p['path']:p['sha256'] for p in old['modifications']}
        for relative, expected in originals.items():
            path = Path(old['source'])/relative
            if digest(path) != changed.get(str(path), expected):
                raise RuntimeError('FF source changed: '+str(path))
        if not all(digest(p['path']) == p['sha256'] for p in old['inputs']):
            raise RuntimeError('Donor build input changed')
        source = out/'source'
        shutil.copytree(old['source'], source, symlinks=True)
        modifications = patch(source)
        (out/'source.input.json').write_text(json.dumps(
            {str(p.relative_to(source)):digest(p) for p in source.rglob('*') if p.is_file()}, indent=2)+'\n')
        compiles = [{k:([a.replace(str(previous), str(out)) for a in v] if k=='argv'
                        else v.replace(str(previous), str(out))) for k,v in job.items()}
                    for job in old['compile_plan']]
        if len(compiles) != old['rebuilt_translation_units']:
            raise RuntimeError('Incomplete header dependency rebuild set')
        argv = [a.replace(str(previous), str(out)) for a in old['link_argv']]
        argv[argv.index('-o')+1] = str(out/'nextpnr-himbaechel')
        frozen = []
        for index, arg in enumerate(old['link_argv']):
            path = Path(arg)
            if path.suffix not in ('.o', '.a') or not path.is_file():
                continue
            dest = Path(argv[index])
            if dest == path:
                dest = out/'input-objects'/('external-'+str(index)+'-'+path.name)
                argv[index] = str(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            subprocess.run(['cp', '--reflink=auto', str(path), str(dest)], check=True)
            frozen.append(describe(path))
        save(source=str(source), modifications=modifications, source_inventory=describe(out/'source.input.json'),
             compile_plan=compiles, rebuilt_translation_units=len(compiles), link_argv=argv,
             reused_inputs=frozen, retained_ff_edge_correction=True)
        for index, job in enumerate(compiles):
            run(job['argv'], 'compile-'+str(index).zfill(2))
        run(argv, 'link')
        if not all(digest(p['path']) == p['sha256'] for p in frozen):
            raise RuntimeError('Previous object changed while building')
        run([str(out/'nextpnr-himbaechel'), '--version'], 'version')
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
