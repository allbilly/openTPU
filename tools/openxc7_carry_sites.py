#!/usr/bin/env python3
"""Build the documented XC7 two-slice carry placement extension in isolation."""
import argparse
from datetime import datetime,timezone
import hashlib,json,shutil,subprocess
from pathlib import Path

def sha(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
def describe(p):
 p=Path(p);return dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))

CARRY = r"""    if (root_cell->type == id_CARRY4) {
        // The packed absolute z values describe a slice-local template.
        // Preserve upstream x/y placement and translate it to the proposed
        // physical slice, instead of coercing both candidates to slice zero.
        placement.clear();
        if (root_bel == BelId() || !ctx->isValidBelForCellType(root_cell->type, root_bel))
            return false;
        int shift = ctx->getBelLocation(root_bel).z - BEL_CARRY4;
        if (shift != 0 && shift != 64)
            return false;
        if (!HimbaechelAPI::getClusterPlacement(cluster, root_bel, placement))
            return false;
        for (auto &target : placement) {
            Loc loc = ctx->getBelLocation(target.second);
            loc.z += shift;
            BelId translated = ctx->getBelByLocation(loc);
            if (translated == BelId() || !ctx->isValidBelForCellType(target.first->type, translated)) {
                placement.clear();
                return false;
            }
            target.second = translated;
        }
        return !placement.empty() && placement.front().second == root_bel;
    }
"""
PROBE = r"""    // Optional validation only: pin a small real carry probe to slice one
    // after exercising ordinary binding and legality in empty locations.
    if (ctx->args.options.count("carry-upper-probe")) {
        if (ctx->cells.size() > 512)
            log_error("carry-upper-probe is restricted to small verification netlists\n");
        pool<BelId> reserved;
        int roots = 0;
        for (auto &entry : ctx->cells) {
            CellInfo *ci = entry.second.get();
            if (ci->type != id_CARRY4 || ci->cluster != ci->name)
                continue;
            bool selected = false;
            for (int y = 190; y >= 100; --y) {
                BelId proposed = ctx->getBelByLocation(Loc(10, y, 79));
                if (proposed == BelId())
                    continue;
                std::vector<std::pair<CellInfo *, BelId>> targets, baseline;
                if (!HimbaechelAPI::getClusterPlacement(ci->cluster, proposed, baseline) ||
                    !getClusterPlacement(ci->cluster, proposed, targets))
                    continue;
                bool available = true;
                pool<BelId> unique;
                for (auto &target : targets) {
                    if (reserved.count(target.second) || unique.count(target.second) ||
                        ctx->getBoundBelCell(target.second) != nullptr)
                        available = false;
                    unique.insert(target.second);
                }
                if (!available)
                    continue;
                for (auto &target : targets)
                    ctx->bindBel(target.second, target.first, STRENGTH_STRONG);
                bool legal = true;
                for (auto &target : targets)
                    legal &= ctx->isBelLocationValid(target.second, true);
                for (auto it = targets.rbegin(); it != targets.rend(); ++it)
                    ctx->unbindBel(it->second);
                if (!legal)
                    continue;
                int old_z = ctx->getBelLocation(baseline.front().second).z;
                int new_z = ctx->getBelLocation(targets.front().second).z;
                if (old_z != 15 || new_z != 79 || targets.front().second != proposed)
                    log_error("Carry second-slice probe returned unexpected root geometry\n");
                ci->attrs[id_BEL] = ctx->getBelName(proposed).str(ctx);
                for (auto &target : targets)
                    reserved.insert(target.second);
                log_info("CARRY_UPPER_SITE_PROBE root='%s' members=%zu old_z=%d new_z=%d legality=PASS\n",
                         ctx->nameOf(ci), targets.size(), old_z, new_z);
                ++roots;
                selected = true;
                break;
            }
            if (!selected)
                log_error("No legal empty upper-slice location for carry probe root '%s'\n", ctx->nameOf(ci));
        }
        if (roots == 0)
            log_error("No carry roots in the second-slice probe\n");
        log_info("CARRY_UPPER_SITE_PROBE_PASS roots=%d\n", roots);
    }
"""

def build(previous,out):
 old=json.loads((previous/'manifest.json').read_text());out.mkdir(parents=True,exist_ok=False);mp=out/'manifest.json'
 m=dict(status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat(),previous=describe(previous/'manifest.json'),previous_binary=old['binary'],helper=describe(Path(__file__).resolve()),scope='XC7 carry clusters in both physical slices; retain upstream algorithms and verified corrections',physical_hardware='NOT_RUN',carry_padding=old['carry_padding'],placer_timeout=old['placer_timeout'],arithmetic_contract=old.get('arithmetic_contract'),carry_sites='BUILDING_NOT_YET_TESTED')
 def save(**fields):m.update(fields);mp.write_text(json.dumps(m,indent=2)+'\n')
 def run(argv,name):
  save(stage=name);(out/(name+'.command.json')).write_text(json.dumps(argv,indent=2)+'\n')
  with (out/(name+'.log')).open('w') as log:r=subprocess.run(argv,cwd=out,stdout=log,stderr=subprocess.STDOUT)
  (out/(name+'.exit')).write_text(str(r.returncode)+'\n')
  if r.returncode:raise RuntimeError(name+' exited '+str(r.returncode))
 try:
  save(stage='verify-inputs');assert old['status']=='BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED';assert sha(old['source_inventory']['path'])==old['source_inventory']['sha256'];assert sha(old['binary']['path'])==old['binary']['sha256']
  inventory=json.loads(Path(old['source_inventory']['path']).read_text())
  for name,expected in inventory.items():
   if sha(Path(old['source'])/name)!=expected:raise RuntimeError('Previous source changed: '+name)
  source=out/'source';shutil.copytree(old['source'],source,symlinks=True);cc=source/'himbaechel/uarch/xilinx/xilinx.cc';text=cc.read_text()
  anchor='    CellInfo *root_cell = ctx->getClusterRootCell(cluster);\n    if (root_cell->type != id_DSP48E1_DSP48E1)'
  assert text.count(anchor)==1;text=text.replace(anchor,'    CellInfo *root_cell = ctx->getClusterRootCell(cluster);\n'+CARRY+'    if (root_cell->type != id_DSP48E1_DSP48E1)')
  option_anchor='    return specific;\n'
  assert text.count(option_anchor)==1
  text=text.replace(option_anchor,'    specific.add_options()("carry-upper-probe", po::value<std::string>(),\n                           "verification only: pin small carry probes to the second slice");\n'+option_anchor)
  cfg='void XilinxImpl::configurePlacerHeap(PlacerHeapCfg &cfg)\n{\n';assert text.count(cfg)==1;cc.write_text(text.replace(cfg,cfg+PROBE))
  changes=[name for name,expected in inventory.items() if sha(source/name)!=expected];assert changes==['himbaechel/uarch/xilinx/xilinx.cc'],changes
  plan=source/'docs/xilinx-porting/08-carry-sites.md';shutil.copyfile(Path(__file__).resolve().parents[1]/'docs/openxc7_carry_sites.md',plan)
  readme=source/'docs/xilinx-porting/README.md';readme.write_text(readme.read_text()+'\nSee `08-carry-sites.md` for two-slice carry placement and required real routed verification. Full physical fit and timing remain unproven.\n')
  inv=out/'source.input.json';inv.write_text(json.dumps({str(p.relative_to(source)):sha(p) for p in source.rglob('*') if p.is_file()},indent=2)+'\n')
  job=next(j for j in old['compile_plan'] if j['source'].endswith('/xilinx.cc'));compile_argv=[a.replace(str(previous),str(out)) for a in job['argv']];link=[a.replace(str(previous),str(out)) for a in old['link_argv']];link[link.index('-o')+1]=str(out/'nextpnr-himbaechel');inputs=[]
  for i,arg in enumerate(old['link_argv']):
   p=Path(arg)
   if p.suffix not in ('.o','.a') or not p.is_file():continue
   dest=Path(link[i])
   if dest==p:dest=out/'input-objects'/('external-'+str(i)+'-'+p.name);link[i]=str(dest)
   dest.parent.mkdir(parents=True,exist_ok=True);subprocess.run(['cp','--reflink=auto',str(p),str(dest)],check=True);inputs.append(describe(p))
  obj=compile_argv[compile_argv.index('-o')+1];assert obj in link
  save(source=str(source),source_inventory=describe(inv),modifications=[describe(cc),describe(plan),describe(readme)],compile_plan=[dict(source=str(cc),output=obj,argv=compile_argv)],link_argv=link,reused_inputs=inputs,rebuilt_translation_units=1,header_declarations='UNCHANGED_HASH_VERIFIED',retained_corrections=list(dict.fromkeys(old.get('retained_corrections',[])+['CARRY_SECOND_SLICE','FINITE_64BIT_TIMEOUT'])))
  run(compile_argv,'compile-xilinx');run(link,'link')
  for p in inputs:assert sha(p['path'])==p['sha256']
  run([str(out/'nextpnr-himbaechel'),'--version'],'version');save(status='BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED',carry_sites='BUILT_GEOMETRY_AND_ROUTING_NOT_YET_TESTED',binary=describe(out/'nextpnr-himbaechel'))
 except Exception as e:save(status='FAIL',error=str(e));raise
 finally:save(finished_utc=datetime.now(timezone.utc).isoformat());print(mp)
if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--previous',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();build(a.previous.resolve(),a.out.resolve())
