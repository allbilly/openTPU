#!/usr/bin/env python3
"""Elaborate/synthesize the complete frozen Vivado MIG + OpenTPU RTL in Yosys.

Uses the generated MIG RTL, not an empty controller stub. A synthesis pass
does not imply OpenXC7 can place or encode the MIG hard PHY cells.
"""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import subprocess

from fedora_openxc7 import describe, xilinx_stages


def strip_display(text):
    """Remove simulation display statements, preserving other RTL and lines."""
    pattern = re.compile(r'\$display\s*\(')
    cursor, pieces, count = 0, [], 0
    for match in pattern.finditer(text):
        if match.start() < cursor:
            continue
        i, depth, quoted = match.end(), 1, False
        while depth:
            char = text[i]
            if quoted and char == '\\':
                i += 2
                continue
            if char == '"':
                quoted = not quoted
            elif not quoted:
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
            i += 1
        while text[i].isspace():
            i += 1
        if text[i] != ';':
            raise RuntimeError('Unexpected MIG display statement syntax')
        i += 1
        pieces += [text[cursor:match.start()], ';'+'\n'*text[match.start():i].count('\n')]
        cursor, count = i, count+1
    pieces.append(text[cursor:])
    return ''.join(pieces), count


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--reference', required=True, type=Path)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--elaborate-only', action='store_true')
    args = ap.parse_args()
    ref, out = args.reference.resolve(), args.out.resolve()
    if out.exists():
        ap.error('Choose a fresh output directory')
    out.mkdir(parents=True)
    top = 'otpu_fpga_top_vivado_mig_jtag'
    params = dict(MCOLS=4, ACT_ROWS=4, MXU_IMPL=2, VPU_CL=2, LANES=8,
                  CORE_KHZ=100000, DDR_MTS=1066, BUILD_ID=0x5b1e646c, PCIE_GEN=2)
    sources = sorted((ref/'source/rtl').rglob('*.sv'))
    ip = sorted(p for p in (ref/'ip/otpu_mig_ddr3/otpu_mig_ddr3/user_design/rtl').rglob('*.v')
                if not p.name.endswith('_sim.v'))
    share = Path(expand_paths('@YOSYS_SHARE@'))
    names = ['DSP48E1', 'IBUF', 'BUFG', 'IOBUF', 'BSCANE2', 'XADC', 'MMCME2_ADV']
    texts = [(share/'xilinx'/p).read_text() for p in ('cells_sim.v', 'cells_xtra.v')]
    declarations = []
    for name in names:
        matches = [m for text in texts if (m := re.search(r'^module '+name+r'\b.*?^endmodule', text, re.M | re.S))]
        if len(matches) != 1:
            raise RuntimeError('Missing real primitive declaration: '+name)
        body = matches[0].group()
        header = body[:body.index(');')+2]
        decls = re.findall(r'^\s*parameter\b.*?;', body, re.M | re.S)
        if not re.search(r'\b(input|output|inout)\b', header):
            decls += re.findall(r'^\s*(?:input|output|inout)\b.*?;', body, re.M | re.S)
        declaration = header+'\n'+'\n'.join(decls)+'\nendmodule'
        if name == 'MMCME2_ADV':
            # Yosys represents primitive real parameters as decimal strings.
            declaration = re.sub(r'parameter real (\w+)\s*=\s*([^;]+);',
                                 lambda m: f'parameter {m[1]} = "{m[2].strip()}";', declaration)
        declarations.append(declaration)
    (out/'primitives.v').write_text('// Real installed hardware primitive declarations.\n'+'\n'.join(declarations)+'\n')
    manifest = dict(status='RUNNING', scope='FULL_FROZEN_RTL_AND_REAL_MIG',
                    parameters=params, top=top, reference=str(ref),
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    physical_programming=False, threads_requested=len(os.sched_getaffinity(0)),
                    source=[describe(p) for p in sources+ip],
                    tools=[describe(expand_paths('@YOSYS@')),
                           describe(expand_paths('@SLANG@'))])
    # MIG uses a vendor fine-delay primitive absent from cells_xtra.v. Import
    # its actual parameter/port declarations, preserving the physical cell.
    vendor = Path(expand_paths('@VIVADO_ROOT@/data/verilog/src/unisims/IDELAYE2_FINEDELAY.v'))
    body = re.search(r'\bmodule IDELAYE2_FINEDELAY\b.*?\bendmodule',vendor.read_text(),re.S).group()
    header = body[:body.index(');')+2]
    decls = re.findall(r'^\s*parameter\b.*?;',body,re.M|re.S)
    decls += re.findall(r'^\s*(?:input|output|inout)\b.*?;',body,re.M|re.S)
    (out/'vendor-primitives.v').write_text('(* blackbox *) '+header+'\n'+'\n'.join(decls)+'\nendmodule\n')
    manifest['vendor_primitive_library'] = dict(source=describe(vendor), generated=describe(out/'vendor-primitives.v'))
    normalized_sources = []
    manifest['source_normalization'] = []
    for path in sources:
        target = out/'source'/path.relative_to(ref/'source')
        target.parent.mkdir(parents=True,exist_ok=True)
        text = path.read_text()
        if path.name == top+'.sv':
            text, count = re.subn(r'\.(CLKIN1_PERIOD|CLKFBOUT_MULT_F|CLKOUT0_DIVIDE_F)\((\d+\.\d+)\)',
                                  lambda m: f'.{m[1]}("{m[2]}")',text)
            if count != 3:
                raise RuntimeError('Unexpected core MMCM real-parameter scope')
            manifest['source_normalization'].append(dict(original=str(path),
                    kind='MMCM_DECIMAL_STRING_PARAMETERS', changes=count))
        target.write_text(text)
        normalized_sources.append(target)
    # The frontend validates printf formats even with -nodisplay. Make local
    # copies that remove only simulation $display statements; frozen vendor
    # sources remain intact and each transformation is recorded.
    local_ip = []
    manifest['display_only_normalization'] = []
    for path in ip:
        target = out/'generated-ip'/path.relative_to(ref/'ip')
        target.parent.mkdir(parents=True,exist_ok=True)
        text, count = strip_display(path.read_text())
        target.write_text(text)
        local_ip.append(target)
        manifest['display_only_normalization'].append(dict(original=str(path),
                normalized=describe(target), removed_display_statements=count))
    def save():
        (out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    script = [
        expand_paths('plugin -i @SLANG@'),
        'read_verilog -lib +/xilinx/cells_sim.v',
        'read_verilog -lib +/xilinx/cells_xtra.v',
        f'read_verilog -lib {out/"vendor-primitives.v"}',
        # MIG emits simulation diagnostics with printf formats that the
        # Verilog frontend cannot interpret. Suppress display tasks only.
        'read_verilog -sv -nodisplay -D SYNTHESIS '+' '.join(map(str,local_ip)),
        'read_slang --allow-use-before-declare -D SYNTHESIS -v '+str(out/'primitives.v')+' '+
        ' '.join('--blackboxed-module '+n for n in names)+' --top '+top+' '+
        ' '.join(f'-G {k}={v}' for k,v in params.items())+' '+' '.join(map(str,normalized_sources)),
        'hierarchy -check -top '+top,
        f'write_rtlil {out/"frontend.il"}',
        # Generic MIG lane/debug ports can be undriven in inactive generate
        # branches. Flatten and optimize the full graph before checking it.
        # Only primitive whitebox models become opaque: preserve the top and
        # every accelerator/MIG cell. Never use an all-module blackbox selection
        # after loading the design, and do not tie off unknown signals.
        'proc', 'flatten', 'opt -full', 'blackbox =A:whitebox',
        'check -assert', f'write_rtlil {out/"elaborated.il"}']
    if not args.elaborate_only:
        script += xilinx_stages(top, 'jtag', abc_fast=True)
        script += ['check -assert', f'write_json {out/"synth.json"}', 'stat -tech xilinx']
    (out/'synth.ys').write_text('\n'.join(script)+'\n')
    command = [expand_paths('@YOSYS@'),'-s',str(out/'synth.ys')]
    (out/'command.json').write_text(json.dumps(command,indent=2)+'\n')
    save()
    try:
        env = dict(os.environ, LD_PRELOAD='/usr/lib64/libstdc++.so.6',
                   OMP_NUM_THREADS=str(len(os.sched_getaffinity(0))))
        with (out/'synth.log').open('w') as log:
            process = subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
            manifest['child_pid'] = process.pid
            save()
            code = process.wait()
        (out/'command.exit').write_text(f'{code}\n')
        manifest.pop('child_pid',None)
        manifest.update(exit_code=code,status=('ELABORATION_PASS' if args.elaborate_only else 'SYNTHESIS_PASS') if code == 0 else 'FAIL')
        print(manifest['status']+': '+str(out),flush=True)
        return code
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
