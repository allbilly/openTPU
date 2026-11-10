#!/usr/bin/env python3
"""Reproducible openXC7 stages for the full YPCB accelerator and LiteDRAM.

No lint stand-ins enter synthesis. Tool dependencies are read from existing
local installations; output directories and manifests belong to this checkout.
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
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from openxc7_vref import apply as apply_vref, bank_plan
from openxc7_chipdb_audit import inspect as inspect_timing
from fedora_prepare_litedram import profile as litedram_profile

ROOT = Path(__file__).resolve().parents[1]
DONOR = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb'))
PART = 'xc7k480tffg1156-2'
CORE = '''vpu/otpu_fp.sv vpu/otpu_fpipe.sv top/otpu_pkg.sv
mem/otpu_tmem.sv mem/otpu_actram.sv seq/otpu_seq.sv vpu/otpu_vtree.sv
dma/otpu_dma.sv mxu/otpu_mxu.sv vpu/otpu_quant.sv vpu/otpu_se_comp.sv
vpu/otpu_se_tail.sv vpu/otpu_vpu.sv top/otpu_coll.sv top/otpu_slice.sv
boards/ypcb-00338/otpu_ctrl.sv boards/ypcb-00338/otpu_trace.sv
boards/ypcb-00338/otpu_board.sv mem/otpu_native_dram.sv
boards/ypcb-00338/otpu_afifo.sv boards/ypcb-00338/otpu_mem_ch.sv
boards/ypcb-00338/otpu_axi_split2.sv boards/ypcb-00338/otpu_native_sys.sv'''.split()
JTAG = ['otpu_jtag_mailbox.sv', 'otpu_jtag_axi.sv', 'otpu_fpga_top_openxc7_jtag.sv']
PARAMS = dict(MCOLS=4, ACT_ROWS=4, MXU_IMPL=2, VPU_CL=2, LANES=8,
              CORE_KHZ=133333, DDR_MTS=1066)


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(1 << 20), b''):
            h.update(b)
    return h.hexdigest()


def describe(path):
    p = Path(path).resolve()
    return dict(path=str(p), bytes=p.stat().st_size, sha256=digest(p))


def tool(name, default):
    return Path(os.environ.get(name, default)).resolve()


def route_threads():
    requested = os.environ.get('OTPU_THREADS', '2').strip().lower()
    if requested == 'all':
        available = len(os.sched_getaffinity(0)) if hasattr(os, 'sched_getaffinity') else (os.cpu_count() or 1)
        return max(1, available)
    try:
        count = int(requested)
    except ValueError as e:
        raise RuntimeError('OTPU_THREADS must be a positive integer or "all"') from e
    if count < 1:
        raise RuntimeError('OTPU_THREADS must be a positive integer or "all"')
    return count


def configuration():
    yosys = tool('OTPU_YOSYS', shutil.which('yosys') or 'yosys')
    share = tool('OTPU_YOSYS_SHARE', expand_paths('@YOSYS_SHARE@'))
    return dict(yosys=yosys, share=share,
                slang=tool('OTPU_SLANG', expand_paths('@SLANG@')),
                cxx=tool('OTPU_CXX_RUNTIME', '/usr/lib64/libstdc++.so.6'),
                nextpnr=tool('OTPU_NEXTPNR', DONOR/'nextpnr-cli-build/nextpnr-himbaechel'),
                nextpnr_source=tool('OTPU_NEXTPNR_SOURCE', DONOR/'nextpnr-himbaechel'),
                chipdb=tool('OTPU_CHIPDB', DONOR/'nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin'),
                database=tool('OTPU_XRAY_DB', DONOR/'prjxray-db/kintex7'),
                xray=tool('OTPU_XRAY_SOURCE', DONOR/'prjxray'),
                fasm2frames=tool('OTPU_FASM2FRAMES', DONOR/'xray-venv/bin/fasm2frames'),
                frames2bit=tool('OTPU_FRAMES2BIT', DONOR/'prjxray-build/tools/xc7frames2bit'))


def run(cmd, out, name, env=None, stdout_path=None):
    (out/f'{name}.command.json').write_text(json.dumps([str(c) for c in cmd], indent=2)+'\n')
    with (out/f'{name}.log').open('w') as log:
        if stdout_path:
            with Path(stdout_path).open('w') as target:
                code = subprocess.run(cmd, cwd=out, env=env, stdout=target, stderr=log).returncode
        else:
            code = subprocess.run(cmd, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
    (out/f'{name}.exit').write_text(f'{code}\n')
    if code:
        raise RuntimeError(f'{name} exited {code}; see {out/name}.log')


def library(config, out):
    # Slang needs primitive parameter declarations. Its import of already-loaded
    # Yosys cells exposes ports only. Take the real installed library definitions,
    # remove specify timing syntax, and blackbox these hardware primitives.
    names = ['DSP48E1', 'IBUF', 'BUFG', 'IOBUF', 'BSCANE2', 'XADC']
    texts = [(config['share']/'xilinx'/p).read_text() for p in ('cells_sim.v', 'cells_xtra.v')]
    decls = []
    for name in names:
        matches = [m for s in texts if (m := re.search(r'^module '+name+r'\b.*?^endmodule', s, re.M | re.S))]
        if len(matches) != 1:
            raise RuntimeError(f'Expected one installed declaration for {name}')
        # Do not supply the behavioral body: Slang would otherwise export a
        # model's generate-loop variable as a spurious primitive parameter.
        body = matches[0].group()
        header = body[:body.index(');')+2]
        declarations = re.findall(r'^\s*parameter\b.*?;', body, re.M | re.S)
        if not re.search(r'\b(input|output|inout)\b', header):
            declarations += re.findall(r'^\s*(?:input|output|inout)\b.*?;', body, re.M | re.S)
        decls.append(header+'\n'+'\n'.join(declarations)+'\nendmodule')
    target = out/'primitive-library.v'
    target.write_text('// Declarations from the installed Yosys library; hardware blackboxes.\n'+'\n'.join(decls)+'\n')
    return target, names


def xilinx_stages(top, kind, abc_fast=False):
    command = f'synth_xilinx -family xc7 -flatten -nosrl -top {top}'
    if kind == 'core':
        command += ' -noiopad -noclkbuf'
    if not abc_fast:
        return [command]
    # Preserve the complete xc7 flow and its LUT costs; replace only ABC's
    # default SAT-intensive optimisation script with its documented -fast
    # script. Save the pre-LUT design for mapping refinements without replaying
    # frontend, arithmetic and memory lowering.
    # synth_xilinx's ending label is excluded. Stop before map_luts so FF
    # legalisation runs; resume through the check/whitebox finalisation.
    return [command+' -run begin:map_luts', 'write_rtlil pre-lut.il',
            'opt_expr -mux_undef -noclkinv',
            'abc -fast -luts 2:2,3,6:5,10,20', 'clean',
            'techmap -map +/xilinx/ff_map.v',
            'techmap -map +/xilinx/lut_map.v -map +/xilinx/cells_map.v -D LUT_WIDTH=6',
            'xilinx_dffopt', 'opt_lut_ins -tech xilinx',
            command+' -run finalize:']


def synth(config, out, kind, dram, elaborate=False, from_elaborated=None, abc_fast=False):
    real_ld = dram['verilog']
    shutil.copyfile(dram['rom'], out/'otpu_litedram_mem.init')
    target, names = library(config, out)
    lines = [f'plugin -i {config["slang"]}',
             'read_verilog -lib +/xilinx/cells_sim.v',
             'read_verilog -lib +/xilinx/cells_xtra.v']
    params = dict(PARAMS, **dram['parameters'])
    params['BUILD_ID'] = int(subprocess.check_output(['git','rev-parse','--short=8','HEAD'],cwd=ROOT,text=True).strip(),16)
    if from_elaborated:
        previous = Path(from_elaborated).resolve()
        old = json.loads((previous.parent/'manifest.json').read_text())
        if old.get('status') != 'ELABORATION_PASS' or old.get('action') != kind+'-elaborate':
            raise RuntimeError('Resume requires a successful matching elaboration manifest')
        if old.get('parameters') != dict(PARAMS, **dram['parameters']):
            raise RuntimeError('Selected DDR/core rate differs from the elaborated image')
        if digest(previous) != old.get('artifacts', {}).get(previous.name, {}).get('sha256'):
            raise RuntimeError('Elaboration checkpoint hash differs from its manifest')
        for name, sha in old['source'].items():
            if digest(name) != sha: raise RuntimeError('Source changed since elaboration: '+name)
        lines = [f'read_rtlil {previous}']
        top = 'otpu_fpga_top_openxc7_jtag' if kind == 'jtag' else 'otpu_native_sys'
    elif kind == 'ddr':
        lines += [f'read_verilog {real_ld}', 'hierarchy -check -top otpu_litedram']
        top = 'otpu_litedram'
    else:
        sources = [ROOT/'rtl'/p for p in CORE]
        top = 'otpu_native_sys'
        if kind == 'jtag':
            lines += [f'read_verilog {real_ld}']
            sources += [ROOT/'rtl/boards/ypcb-00338'/p for p in JTAG]
            top = 'otpu_fpga_top_openxc7_jtag'
            params['PCIE_GEN'] = 2
        else:
            params.update(HOSTCAL=1, XREG=1)
        lines += ['read_slang --allow-use-before-declare -v '+str(target)+' '+
                  ' '.join('--blackboxed-module '+n for n in names)+
                  ' --top '+top+' '+ ' '.join(f'-G {k}={v}' for k,v in params.items())+
                  ' '+' '.join(str(p) for p in sources), f'hierarchy -check -top {top}']
    lines += [f'write_rtlil {out/"frontend.il"}']
    if from_elaborated:
        lines += [f'hierarchy -check -top {top}']
    else:
        lines += ['proc', 'opt_clean']
    lines += ['check -assert', f'write_rtlil {out/"elaborated.il"}']
    if not elaborate:
        # Native DDR serializers and the explicit systolic DSPs are preserved.
        # No SRLC32 cascade is required by this flow.
        lines += xilinx_stages(top, kind, abc_fast)
        lines += ['check -assert', f'write_json {out/"synth.json"}', 'stat -tech xilinx']
    script = out/'synth.ys'; script.write_text('\n'.join(lines)+'\n')
    env = dict(os.environ, LD_PRELOAD=str(config['cxx']))
    run([str(config['yosys']), '-Q', '-T', '-s', str(script)], out, 'elaborate' if elaborate else 'synth', env)


def implementation(config, out, netlist, dram):
    """Diagnostic placement/routing; never silently consume Vivado-only XDC."""
    previous = json.loads((Path(netlist).parent/'manifest.json').read_text())
    if previous.get('status') != 'SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN' or previous.get('action') != 'jtag-synth':
        raise RuntimeError('Routing requires a successful full JTAG synthesis manifest')
    if digest(netlist) != previous.get('artifacts',{}).get('synth.json',{}).get('sha256'):
        raise RuntimeError('Synthesis netlist hash differs from its manifest')
    if previous.get('parameters') != dict(PARAMS, **dram['parameters']):
        raise RuntimeError('Route DDR/core parameters differ from synthesis')
    if digest(dram['xdc']) != previous.get('constraint_source', {}).get('sha256'):
        raise RuntimeError('DDR constraints changed since synthesis')
    for name,sha in previous['source'].items():
        if digest(name) != sha: raise RuntimeError('Source changed since synthesis: '+name)
    design = json.loads(Path(netlist).read_text())
    top = design['modules']['otpu_fpga_top_openxc7_jtag']
    locs = {'u_ld.ldmmcm0':'MMCME2_ADV_X0Y2', 'u_ld.ldmmcm1':'MMCME2_ADV_X0Y6'}
    for name, loc in locs.items():
        if name not in top['cells'] or top['cells'][name]['type'] != 'MMCME2_ADV':
            raise RuntimeError('Missing physical write-clock MMCM: '+name)
        top['cells'][name]['attributes']['LOC'] = loc
    (out/'constrained.json').write_text(json.dumps(design)+'\n')
    constraints = []
    omitted = []
    ld_xdc = dram['xdc']
    vref_plan = bank_plan(ld_xdc, config['database'])
    (out/'vref-plan.json').write_text(json.dumps(vref_plan,indent=2)+'\n')
    timing_coverage = inspect_timing(config['chipdb'],config['nextpnr_source']/'himbaechel/uarch/xilinx/constids.inc')
    (out/'hard-cell-timing-audit.json').write_text(json.dumps(timing_coverage,indent=2)+'\n')
    # All physical DDR I/O properties have literal selectors. Preserve each;
    # bank VREF and timing expressions get an explicit audit, not a silent drop.
    for num, line in enumerate(ld_xdc.read_text().splitlines(),1):
        if not line.strip() or line.startswith('#'): continue
        if re.fullmatch(r'set_property (LOC|SLEW|IOSTANDARD|IN_TERM) \S+ \[get_ports \{[^}]+\}\]',line):
            constraints.append(line.replace('set_property LOC ','set_property PACKAGE_PIN '))
        else: omitted.append(dict(source=str(ld_xdc),line=num,text=line))
    pins = {'SYS_CLK':'AA28','led[0]':'P30','led[1]':'M30','led[2]':'N30',
            'lm73_scl':'N24','lm73_sda':'N25','lm73_alert_n':'P25','smb_scl':'R26','smb_sda':'R27'}
    for name,pin in pins.items():
        if name not in top['ports'] and not name.startswith('led['):
            raise RuntimeError('Missing constrained board port: '+name)
        constraints += [f'set_property PACKAGE_PIN {pin} [get_ports {{{name}}}]',
                        f'set_property IOSTANDARD LVCMOS18 [get_ports {{{name}}}]']
        if name.startswith(('lm73_','smb_')):
            constraints += [f'set_property PULLUP true [get_ports {{{name}}}]']
    core_khz = previous['parameters']['CORE_KHZ']
    threads = route_threads()
    for name, period, kind in [('SYS_CLK',20,'ports'),('ld_sys_clk',1e6/core_khz,'nets'),('tck',166.666667,'nets')]:
        if name not in (top['ports'] if kind == 'ports' else top['netnames']):
            raise RuntimeError('Missing clock constraint target: '+name)
        constraints.append(f'create_clock -period {period} [get_{kind} {{{name}}}]')
    (out/'openxc7.xdc').write_text('\n'.join(constraints)+'\n')
    (out/'constraint-audit.json').write_text(json.dumps(dict(
        status='INCOMPLETE_TIMING_QUALIFICATION', literal_constraints=len(constraints),
        omitted_vivado_constraints=omitted,
        note='DDR write-clock uncertainty/reset max-delay and asynchronous mailbox constraints need qualification. Bank VREF is applied by the checked FASM adapter after routing.'),indent=2)+'\n')
    run([str(config['nextpnr']),'--chipdb',str(config['chipdb']),'--device',PART,
         '--json',str(out/'constrained.json'),'-o','xdc='+str(out/'openxc7.xdc'),
         '-o','fasm='+str(out/'design.raw.fasm'),'--router',os.environ.get('OTPU_ROUTER','router2'),
         '--freq',str(core_khz/1000),'--seed','1','--threads',str(threads),
         '--detailed-timing-report', '--report',str(out/'timing.json'),
         '--write',str(out/'routed.json')],out,'route')
    apply_vref(out/'design.raw.fasm', out/'design.fasm', ld_xdc,
               config['database'], out/'vref-audit.json')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=['check','core-elaborate','core-synth','ddr-synth','jtag-elaborate','jtag-synth','jtag-route'])
    ap.add_argument('--out', type=Path)
    ap.add_argument('--from-elaborated',type=Path)
    ap.add_argument('--netlist',type=Path,help='synthesis JSON for jtag-route')
    ap.add_argument('--litedram-core',type=Path,help='checked generated core directory; default: committed DDR3-1066 core')
    ap.add_argument('--abc-fast',action='store_true',help='use the documented fast LUT mapper on the complete design; area and timing still require verification')
    args = ap.parse_args()
    if args.abc_fast and not args.action.endswith('-synth'):
        ap.error('--abc-fast applies only to synthesis actions')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = (args.out or ROOT/'build/fedora-openxc7'/f'{args.action}-{stamp}').resolve()
    out.mkdir(parents=True, exist_ok=False)
    cfg = configuration()
    manifest = dict(status='RUNNING', action=args.action, started_utc=stamp, part=PART,
                    physical_hardware='NOT_RUN', bitstream='NOT_BUILT',
                    logic_mapping='ABC_FAST_LUT' if args.abc_fast else 'ABC_DEFAULT')
    mp = out/'manifest.json'
    mp.write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        selected = args.litedram_core
        if args.action == 'jtag-route':
            if not args.netlist: raise RuntimeError('jtag-route requires --netlist')
            manifest['route_threads'] = route_threads()
            prior = json.loads((args.netlist.resolve().parent/'manifest.json').read_text())
            manifest['logic_mapping'] = prior.get('logic_mapping', 'ABC_DEFAULT')
            inherited = prior.get('litedram',{}).get('manifest')
            inherited = Path(inherited).parent if inherited else None
            if selected and (inherited is None or selected.resolve() != inherited.resolve()):
                raise RuntimeError('Route must use the exact DDR profile from synthesis')
            selected = inherited
        dram = litedram_profile(selected)
        manifest['parameters'] = dict(PARAMS, **dram['parameters'])
        manifest['litedram'] = {k:str(v) if isinstance(v,Path) else v for k,v in dram.items()}
        # Keep the default 1066 run diagnostic: DS182 Table 18 note 2 limits
        # memory interfaces using internal VREF to 800 Mb/s. This marker is
        # independent of later placement and setup/hold qualification.
        manifest['internal_vref_rate'] = ('WITHIN_PUBLISHED_800_MBPS_LIMIT' if
                dram['parameters']['DDR_MTS'] <= 800 else 'ABOVE_PUBLISHED_INTERNAL_VREF_LIMIT')
        manifest['internal_vref_specification'] = 'https://docs.amd.com/v/u/en-US/ds182_Kintex_7_Data_Sheet (v2.19, Table 18 note 2)'
        manifest['tools'] = {k:describe(v) for k,v in cfg.items() if v.is_file()}
        manifest['source'] = {str(ROOT/'rtl'/p):digest(ROOT/'rtl'/p) for p in CORE}
        manifest['source'].update({str(ROOT/'rtl/boards/ypcb-00338'/p):digest(ROOT/'rtl/boards/ypcb-00338'/p) for p in JTAG})
        for p in (dram['verilog'],dram['rom'],dram['data']/'csr.csv',dram['data']/'sdram_init.py'):
            manifest['source'][str(p)] = digest(p)
        if dram['manifest']:
            manifest['source'][str(dram['manifest'])] = digest(dram['manifest'])
        manifest['constraint_source'] = describe(dram['xdc'])
        manifest['primitive_libraries'] = {str(cfg['share']/'xilinx'/p):digest(cfg['share']/'xilinx'/p)
                                            for p in ('cells_sim.v','cells_xtra.v')}
        manifest['vref_adapter'] = describe(Path(__file__).with_name('openxc7_vref.py'))
        manifest['helper_sha256'] = digest(__file__)
        mp.write_text(json.dumps(manifest,indent=2)+'\n')
        if args.action == 'check':
            required = ['yosys','slang','cxx','nextpnr','chipdb','fasm2frames','frames2bit']
            missing = [str(cfg[k]) for k in required if not cfg[k].is_file()]
            if not (cfg['database']/PART/'part.yaml').is_file(): missing.append(str(cfg['database']/PART/'part.yaml'))
            if missing: raise RuntimeError('Missing tool inputs: '+', '.join(missing))
            env = dict(os.environ,LD_PRELOAD=str(cfg['cxx']))
            run([str(cfg['yosys']),'-Q','-T','-p',f'plugin -i {cfg["slang"]}; help read_slang'],out,'slang-load',env)
            coverage = inspect_timing(cfg['chipdb'],cfg['nextpnr_source']/'himbaechel/uarch/xilinx/constids.inc')
            (out/'hard-cell-timing-audit.json').write_text(json.dumps(coverage,indent=2)+'\n')
            manifest['hard_cell_timing'] = coverage['status']
            manifest['status'] = 'TOOLS_READY_BOARD_BUILD_NOT_RUN'
        elif args.action == 'jtag-route':
            if not args.netlist: raise RuntimeError('jtag-route requires --netlist')
            implementation(cfg,out,args.netlist.resolve(),dram)
            manifest['status'] = 'ROUTE_PASS_TIMING_QUALIFICATION_INCOMPLETE'
            manifest['bitstream'] = 'NOT_ASSEMBLED_PENDING_TIMING_QUALIFICATION'
            manifest['artifacts'] = {p.name:describe(p) for p in out.iterdir()
                                     if p.suffix in ('.json','.fasm','.xdc') and p != mp}
        else:
            kind = args.action.split('-')[0]
            synth(cfg,out,kind,dram,args.action.endswith('elaborate'),args.from_elaborated,args.abc_fast)
            manifest['status'] = 'ELABORATION_PASS' if args.action.endswith('elaborate') else 'SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN'
            manifest['artifacts'] = {p.name:describe(p) for p in out.iterdir() if p.suffix in ('.il','.json') and p != mp}
    except Exception as e:
        manifest.update(status='FAIL',error=str(e))
        print(str(e),file=sys.stderr)
        return 1
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        mp.write_text(json.dumps(manifest,indent=2)+'\n')
        print(mp)
    return 0


if __name__ == '__main__':
    sys.exit(main())
