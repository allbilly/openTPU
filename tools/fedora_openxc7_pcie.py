#!/usr/bin/env python3
"""Independent full OpenTPU/LiteDRAM/open-PCIe elaboration and synthesis stages."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import ROOT, CORE, configuration, digest, library, run, xilinx_stages
from fedora_prepare_litedram import profile
from fedora_prepare_pcie import prepare

TOP = 'otpu_fpga_top_openxc7_pcie'


def full_scope_witness(artifact):
    """Count reachable hardware instances, never library declarations or prototypes."""
    modules = {}
    current = None
    pending_blackbox = False
    with Path(artifact).open() as stream:
        for line in stream:
            if current is None:
                if line.startswith('attribute \\blackbox '):
                    pending_blackbox = line.strip().endswith(' 1')
                elif line.startswith('module '):
                    current = line.split()[1].lstrip('\\')
                    modules[current] = dict(blackbox=pending_blackbox,cells=Counter())
                    pending_blackbox = False
            elif line == 'end\n':
                current = None
            elif line.startswith('  cell '):
                modules[current]['cells'][line.split()[1].lstrip('\\')] += 1
    primitives = {'PCIE_2_1','GTXE2_CHANNEL','GTPE2_CHANNEL','DSP48E1',
                  'ISERDESE2','OSERDESE2','MMCME2_ADV'}
    counts = Counter()
    visited = Counter()
    def visit(name,instances=1,parents=()):
        if name in primitives:
            counts[name] += instances
            return
        if name not in modules:
            return
        if name in parents:
            raise RuntimeError('Recursive hardware hierarchy: '+name)
        visited[name] += instances
        if modules[name]['blackbox']:
            if name.startswith('otpu_'):
                raise RuntimeError('Full design contains an OpenTPU blackbox: '+name)
            return
        for child,n in modules[name]['cells'].items():
            visit(child,instances*n,parents+(name,))
    visit(TOP)
    required = {'PCIE_2_1':1,'GTXE2_CHANNEL':1,'DSP48E1':528,
                'ISERDESE2':144,'OSERDESE2':214,'MMCME2_ADV':4}
    if any(counts[k] < n for k,n in required.items()) or counts['GTPE2_CHANNEL']:
        raise RuntimeError('Full hardware instance coverage missing or wrong GT family: '+str(dict(counts)))
    if visited['otpu_litedram'] != 1 or visited['otpu_selfcal_VexRiscv'] != 1:
        raise RuntimeError('Real dual DDR core/calibration CPU hierarchy is missing')
    return dict(status='FULL_REACHABLE_INSTANCE_COVERAGE_PASS',primitives=dict(counts),
                calibration_cpu_instances=visited['otpu_selfcal_VexRiscv'],
                note='Elaboration coverage only; no synthesis, timing or physical hardware proof')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['elaborate','synth'])
    ap.add_argument('--litedram-core', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--from-elaborated',type=Path,help='reuse a matching full-scope elaboration checkpoint for synthesis')
    ap.add_argument('--dependency', type=Path, default=ROOT/'build/fedora-openxc7/deps/pcie_7x')
    args = ap.parse_args()
    if args.from_elaborated and args.action != 'synth':
        ap.error('--from-elaborated is for synth')
    out = args.out.resolve()
    if out.exists():
        raise RuntimeError('Use a fresh output directory; preserve previous implementation evidence')
    dram = profile(args.litedram_core)
    config = configuration()
    out.mkdir(parents=True)
    manifest = dict(status='RUNNING', action=args.action, top=TOP,
                    stage='full-elaboration',
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    parameters=dict(MCOLS=4,ACT_ROWS=4,LANES=8,VPU_CL=2,MXU_IMPL=2,
                                    **dram['parameters']),
                    timing='NOT_QUALIFIED', physical_hardware='NOT_RUN', programming='NOT_RUN')
    manifest['source_revision'] = subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    sources = [ROOT/'rtl'/p for p in CORE]
    sources += [ROOT/'rtl/boards/ypcb-00338'/p for p in
                ['otpu_jtag_axi.sv','otpu_pcie_mailbox.sv','otpu_fpga_top_openxc7_pcie.sv']]
    manifest_path = out/'manifest.json'
    try:
        endpoint = prepare(args.dependency, out/'endpoint')
        pinned = [Path(p) for p in endpoint['inputs']]
        inputs = sources+pinned+[Path(__file__),ROOT/'tools/fedora_prepare_pcie.py',
                                ROOT/'tools/fedora_openxc7.py',dram['verilog'],dram['rom'],
                                dram['data']/'csr.csv',dram['data']/'sdram_init.py']
        manifest['source'] = {str(p):digest(p) for p in inputs}
        manifest['generated_endpoint_sources'] = {
            Path(p).name:digest(p) for p in endpoint['sources'] if Path(p).parent == out/'endpoint'}
        manifest['endpoint'] = str(out/'endpoint/manifest.json')
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        target,names = library(config,out)
        endpoint_text = Path(endpoint['wrapper']['path']).read_text()
        start = endpoint_text.index('module otpu_pcie_endpoint #')
        end = endpoint_text.index(');',start)+2
        target.write_text(target.read_text()+'\n'+endpoint_text[start:end]+'\nendmodule\n')
        names.append('otpu_pcie_endpoint')
        shutil.copyfile(dram['rom'],out/'otpu_litedram_mem.init')
        params = dict(manifest['parameters'],PCIE_GEN=2)
        params['BUILD_ID'] = int(subprocess.check_output(['git','rev-parse','--short=8','HEAD'],cwd=ROOT,text=True).strip(),16)
        lines = [f'plugin -i {config["slang"]}',
                 'read_verilog -lib +/xilinx/cells_sim.v',
                 'read_verilog -lib +/xilinx/cells_xtra.v',
                 # Defer parsing parameterized PCIe logic until hierarchy can
                 # apply GTX/Gen2. Eager parsing exposes the unused default
                 # Artix GTP branch to hierarchy -check before specialization.
                 'read_verilog -defer -D SYNTHESIS '+' '.join(endpoint['sources']),
                 f'read_verilog {dram["verilog"]}',
                 'read_slang --allow-use-before-declare -v '+str(target)+' '+
                 ' '.join('--blackboxed-module '+n for n in names)+' --top '+TOP+' '+
                 ' '.join(f'-G {k}={v}' for k,v in params.items())+' '+
                 ' '.join(str(p) for p in sources),
                 # Load the real endpoint after Slang has used its port-only
                 # declaration. Otherwise Slang's external prototype can
                 # shadow the deferred real module during hierarchy.
                 f'read_verilog -overwrite -D SYNTHESIS {endpoint["wrapper"]["path"]}',
                 f'hierarchy -check -top {TOP}', 'proc', 'opt_clean', 'check -assert',
                 f'write_rtlil {out/"elaborated.il"}']
        script = out/'elaborate.ys'
        script.write_text('\n'.join(lines)+'\n')
        env = dict(os.environ,LD_PRELOAD=str(config['cxx']))
        if args.from_elaborated:
            checkpoint = args.from_elaborated.resolve()
            old = json.loads((checkpoint.parent/'manifest.json').read_text())
            if (old.get('status') != 'FULL_PCIE_ELABORATION_PASS'
                or old.get('full_scope_witness',{}).get('status') != 'FULL_REACHABLE_INSTANCE_COVERAGE_PASS'
                or old.get('parameters') != manifest['parameters']
                or old.get('source_revision') != manifest['source_revision']
                or old.get('source') != manifest['source']
                or old.get('generated_endpoint_sources') != manifest['generated_endpoint_sources']
                or old.get('artifact',{}).get('sha256') != digest(checkpoint)):
                raise RuntimeError('Checkpoint is not a matching full-scope PCIe elaboration')
            shutil.copyfile(checkpoint,out/'elaborated.il')
            manifest['reused_elaboration'] = str(checkpoint)
        else:
            run([str(config['yosys']),'-Q','-T','-s',str(script)],out,'elaborate',env)
        manifest['full_scope_witness'] = full_scope_witness(out/'elaborated.il')
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
        if args.action == 'synth':
            manifest['stage'] = 'full-synthesis'
            manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
            script = out/'synth.ys'
            lines = [f'read_rtlil {out/"elaborated.il"}',f'hierarchy -check -top {TOP}']
            lines += xilinx_stages(TOP,'jtag')
            lines += ['check -assert',f'write_json {out/"synth.json"}','stat -tech xilinx']
            script.write_text('\n'.join(lines)+'\n')
            run([str(config['yosys']),'-Q','-T','-s',str(script)],out,'synth',env)
        changed = [p for p,h in manifest['source'].items() if digest(p) != h]
        changed += [str(out/'endpoint'/p) for p,h in manifest['generated_endpoint_sources'].items()
                    if digest(out/'endpoint'/p) != h]
        if changed:
            raise RuntimeError('Inputs changed during the stage: '+str(changed))
        manifest['status'] = 'FULL_PCIE_ELABORATION_PASS' if args.action == 'elaborate' else 'FULL_PCIE_SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN'
        artifact = out/('elaborated.il' if args.action == 'elaborate' else 'synth.json')
        manifest['artifact'] = dict(path=str(artifact),sha256=digest(artifact),bytes=artifact.stat().st_size)
    except BaseException as e:
        manifest.update(status='FAIL',error=str(e))
        raise
    finally:
        manifest['updated_utc'] = datetime.now(timezone.utc).isoformat()
        manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    print(manifest['status'])
    print(manifest_path)


if __name__ == '__main__':
    main()
