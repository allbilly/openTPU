#!/usr/bin/env python3
"""Test the OpenXC7 backend against an immutable, full Vivado MIG reference.

The imported netlist was synthesized by Vivado. This is a backend compatibility
test, not an independent OpenXC7 synthesis result or permission to program it.
"""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BACKEND = Path(expand_paths('@YPCB@/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/carry-sites-backend-v2/nextpnr-himbaechel'))
CHIPDB = Path(expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin'))


def describe(path):
    path = Path(path).resolve()
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=h.hexdigest())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--reuse-export', type=Path,
                        help='Reuse a completed, hash-matched reference export in a fresh run')
    parser.add_argument('--reuse-import', type=Path,
                        help='Reuse a completed import of the same reference in a fresh run')
    args = parser.parse_args()
    ref, out = args.reference.resolve(), args.out.resolve()
    if out.exists():
        parser.error('Choose a new output directory')
    out.mkdir(parents=True)
    threads = len(os.sched_getaffinity(0))
    manifest = dict(status='RUNNING', scope='FULL_VIVADO_NETLIST_BACKEND_TRIAL',
                    independent_openxc7_synthesis=False, physical_programming=False,
                    started_utc=datetime.now(timezone.utc).isoformat(), threads=threads,
                    reference=str(ref), stages=[])

    def save():
        target = out / 'manifest.json'
        temporary = out / 'manifest.json.tmp'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(target)

    def run(stage, command):
        manifest['stage'] = stage
        save()
        (out / f'{stage}.command.json').write_text(json.dumps(command, indent=2) + '\n')
        print(f'START {stage}: {out}', flush=True)
        with (out / f'{stage}.log').open('w') as log:
            process = subprocess.Popen(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            manifest['child_pid'] = process.pid
            save()
            code = process.wait()
        (out / f'{stage}.exit').write_text(f'{code}\n')
        manifest.pop('child_pid', None)
        manifest['stages'].append(dict(stage=stage, exit_code=code))
        save()
        if code:
            raise RuntimeError(f'{stage} exited {code}; see {out / (stage + ".log")}')
        print(f'PASS {stage}', flush=True)

    try:
        bit = ref / 'implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit'
        manifest['inputs'] = {name: describe(path) for name, path in dict(
            bitstream=bit, checkpoint=ref/'routed.dcp', nextpnr=BACKEND,
            chipdb=CHIPDB, yosys=expand_paths('@YOSYS@'),
            cells_sim=expand_paths('@YOSYS_SHARE@/xilinx/cells_sim.v'),
            cells_xtra=expand_paths('@YOSYS_SHARE@/xilinx/cells_xtra.v')).items()}
        if manifest['inputs']['bitstream']['sha256'] != '0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f':
            raise RuntimeError('Unexpected reference bitstream')
        tcl = f'''set_param general.maxThreads {threads}
open_checkpoint {{{ref / 'routed.dcp'}}}
if {{[get_property PART [current_design]] ne "xc7k480tffg1156-2"}} {{error "Wrong reference part"}}
write_verilog -force -mode funcsim {{{out / 'reference.v'}}}
write_edif -force {{{out / 'reference.edf'}}}
set counts [dict create]
set f [open {{{out / 'reference-cells.tsv'}}} w]
puts $f "NAME\tREF_NAME\tLOC\tBEL"
foreach cell [get_cells -hier -filter {{IS_PRIMITIVE == 1}}] {{
  set type [get_property REF_NAME $cell]
  dict incr counts $type
  puts $f "[get_property NAME $cell]\t$type\t[get_property LOC $cell]\t[get_property BEL $cell]"
}}
close $f
set f [open {{{out / 'reference-counts.tsv'}}} w]
dict for {{type count}} $counts {{puts $f "$type\t$count"}}
close $f
set f [open {{{out / 'reference-ports.tsv'}}} w]
foreach port [get_ports] {{puts $f "[get_property NAME $port]\t[get_property PACKAGE_PIN $port]\t[get_property IOSTANDARD $port]"}}
close $f
close_design
exit
'''
        (out / 'export.tcl').write_text(tcl)
        save()
        if args.reuse_export or args.reuse_import:
            previous = (args.reuse_export or args.reuse_import).resolve()
            old = json.loads((previous/'manifest.json').read_text())
            if old['inputs']['checkpoint'] != manifest['inputs']['checkpoint'] or not (
                    any(row == dict(stage='export', exit_code=0) for row in old['stages'])
                    or old.get('reused_export')):
                raise RuntimeError('Reuse requires the same checkpoint and a successful export')
            manifest['reused_export'] = str(previous)
            for name in ('reference.v', 'reference-counts.tsv', 'reference-cells.tsv', 'reference-ports.tsv'):
                shutil.copyfile(previous/name, out/name)
            save()
        else:
            run('export', [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch',
                           '-nojournal', '-nolog', '-source', str(out/'export.tcl')])
        script = '\n'.join([
            'read_verilog -lib +/xilinx/cells_sim.v',
            'read_verilog -lib +/xilinx/cells_xtra.v',
            # Keep every installed hardware primitive opaque, including the
            # whitebox FF/RAM models; the reference already contains mapping.
            'blackbox =*',
            # Vivado appends its unreferenced glbl simulation startup module.
            # Its guard suppresses only that module, not the FPGA netlist.
            f'read_verilog -D GLBL {out / "reference.v"}',
            'hierarchy -check -top otpu_fpga_top_vivado_mig_jtag',
            'flatten',
            'stat',
            f'write_json {out / "reference.json"}', ''])
        (out / 'import.ys').write_text(script)
        if args.reuse_import:
            old = json.loads((args.reuse_import/'manifest.json').read_text())
            if not any(row == dict(stage='import', exit_code=0) for row in old['stages']):
                raise RuntimeError('Reuse requires a completed import')
            shutil.copyfile(args.reuse_import/'reference.json', out/'reference.json')
            manifest['reused_import'] = str(args.reuse_import.resolve())
        else:
            run('import', [expand_paths('@YOSYS@'), '-s', str(out/'import.ys')])
        design = json.loads((out/'reference.json').read_text())
        counts = Counter(cell['type'] for cell in design['modules']['otpu_fpga_top_vivado_mig_jtag']['cells'].values())
        manifest['imported_primitive_counts'] = dict(sorted(counts.items()))
        expected = dict(line.strip().split('\t') for line in (out/'reference-counts.tsv').read_text().splitlines())
        # These cells are essential to the complete accelerator and both PHYs.
        for kind in ('DSP48E1', 'RAMB36E1', 'PHASER_IN_PHY', 'PHASER_OUT_PHY',
                     'IN_FIFO', 'OUT_FIFO', 'PHASER_REF', 'PHY_CONTROL', 'BSCANE2'):
            if counts[kind] != int(expected[kind]):
                raise RuntimeError(f'Reference lost primitive {kind}: {counts[kind]} != {expected[kind]}')
        module = design['modules']['otpu_fpga_top_vivado_mig_jtag']
        manifest['pullup_normalization'] = []
        xdc = []
        for line in (out/'reference-ports.tsv').read_text().splitlines():
            port, pad, standard = line.split('\t')
            xdc += [f'set_property PACKAGE_PIN {pad} [get_ports {{{port}}}]',
                    f'set_property IOSTANDARD {standard} [get_ports {{{port}}}]']
        # Simulation pullup cells must become pad configuration; they are not
        # extra logic drivers. Preserve each electrical setting explicitly.
        for name, cell in list(module['cells'].items()):
            if cell['type'] != 'PULLUP':
                continue
            ports = [port for port, p in module['ports'].items()
                     if p['bits'] == cell['connections']['O']]
            if len(ports) != 1:
                raise RuntimeError('Pullup is not attached to one top-level pad: '+name)
            port = ports[0]
            module['netnames'][port]['attributes'].pop('PULLTYPE', None)
            xdc.append(f'set_property PULLTYPE PULLUP [get_ports {{{port}}}]')
            manifest['pullup_normalization'].append(dict(cell=name, port=port))
            del module['cells'][name]
        (out/'reference.xdc').write_text('\n'.join(xdc)+'\n')
        (out/'constrained.json').write_text(json.dumps(design)+'\n')
        manifest['artifacts'] = {name: describe(out/name) for name in (
            'reference.v','reference.json','reference-counts.tsv','reference.xdc','constrained.json')}
        save()
        run('pack', [str(BACKEND), '--chipdb', str(CHIPDB), '--device', 'xc7k480tffg1156-2',
                     '--json', str(out/'constrained.json'), '-o', 'xdc='+str(out/'reference.xdc'),
                     '--pack-only', '--threads', str(threads),
                     '--write', str(out/'packed.json')])
        manifest['status'] = 'PASS_REFERENCE_IMPORT_AND_BACKEND_PACK'
    except Exception as error:
        manifest.update(status='FAIL', error=repr(error))
        print(manifest['error'], flush=True)
        return 1
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
