#!/usr/bin/env python3
"""Implement the complete PCIe accelerator; retain timing/hardware boundaries."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import sys

from fedora_openxc7 import PART, ROOT, configuration, describe, digest, run
from fedora_pcie_constraints import prepare as pin_constraints, properties, top_bits
from fedora_prepare_litedram import profile
from openxc7_chipdb_audit import inspect as inspect_timing
from openxc7_vref import apply as apply_vref

TOP = 'otpu_fpga_top_openxc7_pcie'
FULL = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2,
            CORE_KHZ=100000, DDR_MTS=800)
BACKEND_SHA = '8628624e01f6c007e9235cb323532a32264e353dcfd26a790ec5a4a9e6418a51'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, indent=2) + '\n')
    temporary.replace(path)


def unchanged(inventory):
    for path, expected in inventory.items():
        require(Path(path).is_file() and digest(path) == expected,
                'Input changed or missing: ' + path)


def recorded(item):
    require(describe(item['path']) == item, 'Recorded artifact changed: ' + item['path'])


def synthesis_inputs(directory, dram):
    directory = Path(directory).resolve()
    manifest = read(directory / 'manifest.json')
    require(manifest.get('status') == 'FULL_PCIE_SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN',
            'Full PCIe synthesis has not completed successfully')
    require(manifest.get('top') == TOP and manifest.get('action') == 'synth',
            'Wrong synthesis top or action')
    require(manifest.get('parameters') == FULL and dram['parameters'] ==
            {k:FULL[k] for k in ('CORE_KHZ', 'DDR_MTS')}, 'Full configuration differs')
    require(manifest.get('full_scope_witness', {}).get('status') ==
            'FULL_REACHABLE_INSTANCE_COVERAGE_PASS', 'Missing full elaboration witness')
    require(Path(manifest['artifact']['path']).resolve() == directory / 'synth.json',
            'Wrong mapped checkpoint path')
    recorded(manifest['artifact'])
    inventory = dict(manifest['source'])
    inventory.update({str(directory / 'endpoint' / name):sha
                      for name,sha in manifest['generated_endpoint_sources'].items()})
    for path in (dram['verilog'], dram['rom']):
        require(str(path) in inventory, 'Synthesis used a different DDR core: ' + str(path))
    unchanged(inventory)
    return manifest, inventory


def select_backend(selection):
    selected = read(selection)
    require(selected.get('configuration') == FULL, 'Backend selection has a different profile')
    backend = selected['corrected_backend']
    require(backend['binary']['sha256'] == BACKEND_SHA, 'Unverified implementation backend')
    inventory = {}
    for item in (backend['binary'], backend['manifest']):
        recorded(item)
        inventory[item['path']] = item['sha256']
    gates = {}
    for name in ('carry_probe', 'cascade_probe', 'upper_carry_probe'):
        gate = selected[name]
        require(gate['status'] == 'PROBE_ROUTE_AND_STRICT_FRAMES_PASS_NUMERICAL_TIMING_NOT_QUALIFIED',
                'Backend correction gate failed: ' + name)
        for item in (gate['manifest'], gate['strict_frames']):
            recorded(item)
            inventory[item['path']] = item['sha256']
        expected_status = ('DSP_CASCADE_16_SITE_PLACEMENT_AND_ROUTING_PASS_STRICT_FRAMES_NOT_TESTED'
                           if name == 'cascade_probe' else 'CARRY_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS')
        require(read(gate['manifest']['path']).get('status') == expected_status,
                'Correction receipt has not passed: ' + name)
        gates[name] = gate
    # The selected pipeline may be live. Pin these immutable receipts rather
    # than hashing its changing heartbeat/stage fields.
    return backend, gates, inventory


def constant(value):
    require(isinstance(value, str) and value and set(value) <= {'0','1'},
            'Nonconstant hardware parameter')
    return int(value, 2)


def netlist_coverage(design, constraints):
    require(TOP in design['modules'], 'Missing complete PCIe top')
    top = design['modules'][TOP]
    counts = Counter(cell['type'] for cell in top['cells'].values())
    for name,minimum in {'PCIE_2_1':1, 'GTXE2_CHANNEL':1, 'IBUFDS_GTE2':1,
                         'DSP48E1':528, 'ISERDESE2':144, 'OSERDESE2':214,
                         'MMCME2_ADV':4}.items():
        require(counts[name] >= minimum, 'Mapped full-scope hardware missing: ' + name)
    require(counts['PCIE_2_1'] == counts['GTXE2_CHANNEL'] == counts['IBUFDS_GTE2'] == 1,
            'PCIe lane/reference-clock instance count differs')
    require(not counts['GTPE2_CHANNEL'] and not counts['BSCANE2'],
            'Wrong GT family or standalone JTAG mailbox image')
    pcie = next(c for c in top['cells'].values() if c['type'] == 'PCIE_2_1')
    for name,value in {'BAR0':0xfffff000, 'LINK_CAP_MAX_LINK_SPEED':2,
                       'LINK_CAP_MAX_LINK_WIDTH':1}.items():
        require(constant(pcie['parameters'][name]) == value, 'PCIe parameter differs: ' + name)
    bits = set()
    for name,port in top['ports'].items():
        width = len(port['bits'])
        offset = port.get('offset', 0)
        bits.update([name] if width == 1 and offset == 0 else
                    [f'{name}[{index}]' for index in range(offset, offset+width)])
    expected = top_bits((ROOT / 'rtl/boards/ypcb-00338/otpu_fpga_top_openxc7_pcie.sv').read_text())
    require(bits == expected == set(properties(constraints.read_text())),
            'Synthesized pad bits differ from complete pin constraints')
    require(len(bits) == 250, 'Complete board pad count differs')
    for name in ('ld_sys_clk', 'pcie_clk'):
        require(name in top['netnames'] and len(top['netnames'][name]['bits']) == 1,
                'Missing synthesized clock target: ' + name)
    for name,loc in {'u_ld.ldmmcm0':'MMCME2_ADV_X0Y2',
                     'u_ld.ldmmcm1':'MMCME2_ADV_X0Y6'}.items():
        require(name in top['cells'] and top['cells'][name]['type'] == 'MMCME2_ADV',
                'Missing physical DDR write-clock MMCM: ' + name)
        top['cells'][name]['attributes']['LOC'] = loc
    return dict(status='FULL_MAPPED_HARDWARE_AND_SYNTHESIZED_PIN_COVERAGE_PASS',
                cells=dict(counts), pad_bits=len(bits),
                clocks=['SYS_CLK','sys_clk_p','ld_sys_clk','pcie_clk'],
                scope='Mapped hierarchy and constraint targets; timing and hardware not qualified')


def execute(action, synthesis, core, selection, out):
    out = Path(out).resolve()
    require(not out.exists(), 'Use a fresh pipeline output directory')
    out.mkdir(parents=True)
    mp = out / 'pipeline.json'
    info = dict(status='RUNNING', stage='validate-full-synthesis', action=action,
                top=TOP, part=PART, configuration=FULL,
                started_utc=datetime.now(timezone.utc).isoformat(),
                timing='NOT_QUALIFIED', physical_hardware='NOT_RUN',
                programming='NOT_RUN', flash_written=False)

    def save(**fields):
        info.update(fields, updated_utc=datetime.now(timezone.utc).isoformat())
        write(mp, info)

    try:
        save()
        dram = profile(Path(core).resolve())
        mapped, inventory = synthesis_inputs(synthesis, dram)
        backend, gates, backend_inputs = select_backend(selection)
        inventory.update(backend_inputs)
        cfg = configuration()
        cfg['nextpnr'] = Path(backend['binary']['path'])
        cfg['nextpnr_source'] = Path(backend['source'])
        inventory.update({str(Path(__file__)):digest(__file__),
                          str(Path(synthesis).resolve() / 'manifest.json'):digest(Path(synthesis) / 'manifest.json')})
        for name in ('fedora_pcie_constraints.py','fedora_check_pcie_image.py',
                     'fedora_openxc7.py','fedora_prepare_litedram.py',
                     'openxc7_vref.py','openxc7_chipdb_audit.py',
                     'openxc7_fasm2frames.py'):
            path = ROOT / 'tools' / name
            inventory[str(path)] = digest(path)
        checker = ROOT.parent / 'bonetto-soc/scripts/fedora-check-bitstream.py'
        inventory[str(checker)] = digest(checker)
        pins = pin_constraints(core, out / 'constraints', cfg['database'])
        inventory.update(pins['inputs'])
        for name in ('chipdb','frames2bit','fasm2frames'):
            inventory[str(cfg[name])] = digest(cfg[name])
        for name in ('part.json','part.yaml'):
            path = cfg['database'] / PART / name
            inventory[str(path)] = digest(path)
        route = out / 'route'
        route.mkdir()
        shutil.copyfile(pins['output']['path'], route / 'openxc7.xdc')
        design = read(mapped['artifact']['path'])
        coverage = netlist_coverage(design, route / 'openxc7.xdc')
        (route / 'constrained.json').write_text(json.dumps(design) + '\n')
        del design
        timing = inspect_timing(cfg['chipdb'], cfg['nextpnr_source'] / 'himbaechel/uarch/xilinx/constids.inc')
        write(out / 'hard-cell-timing-audit.json', timing)
        save(stage='prepared', synthesis=describe(Path(synthesis) / 'manifest.json'),
             synthesis_directory=str(Path(synthesis).resolve()), litedram_core=str(Path(core).resolve()),
             selected_backend=backend, correction_gates=gates,
             planned_inputs=inventory, mapped_coverage=coverage,
             pin_constraints=describe(out / 'constraints/manifest.json'),
             hard_cell_timing=timing['status'])
        unchanged(inventory)
        if action == 'prepare':
            save(status='FULL_PCIE_IMPLEMENTATION_INPUTS_PREPARED_IMPLEMENTATION_NOT_RUN')
            return info
        save(stage='full-pcie-route')
        run([str(cfg['nextpnr']), '--chipdb',str(cfg['chipdb']), '--device',PART,
             '--json',str(route / 'constrained.json'), '-o','xdc='+str(route / 'openxc7.xdc'),
             '-o','fasm='+str(route / 'design.raw.fasm'), '--router','router2',
             '--freq','100', '--seed','1', '--threads','2', '--detailed-timing-report',
             '--report',str(route / 'timing.json'), '--write',str(route / 'routed.json')], route, 'route')
        for name in ('routed.json','timing.json','design.raw.fasm'):
            require((route / name).is_file() and (route / name).stat().st_size,
                    'Native route did not produce ' + name)
        apply_vref(route / 'design.raw.fasm', route / 'design.fasm', dram['xdc'],
                   cfg['database'], route / 'vref-audit.json')
        unchanged(inventory)
        route_artifacts = {name:describe(route / name) for name in
                           ('constrained.json','openxc7.xdc','routed.json','timing.json',
                            'design.raw.fasm','design.fasm','vref-audit.json')}
        write(route / 'manifest.json', dict(status='FULL_PCIE_ROUTE_PASS_TIMING_NOT_QUALIFIED',
              top=TOP, configuration=FULL, artifacts=route_artifacts,
              selected_backend=backend, timing='NOT_QUALIFIED', physical_hardware='NOT_RUN'))
        save(status='FULL_PCIE_ROUTE_PASS_TIMING_NOT_QUALIFIED', stage='routed',
             route_manifest=describe(route / 'manifest.json'))
        if action == 'route':
            return info
        unchanged(inventory)
        save(status='RUNNING', stage='strict-frames')
        frames = out / 'design.frames'
        run([str(cfg['fasm2frames'].parent / 'python'), str(ROOT / 'tools/openxc7_fasm2frames.py'),
             '--db-root',str(cfg['database']), '--part',PART,str(route / 'design.fasm')],
            out, 'strict-frames', dict(os.environ, PYTHONPATH=str(cfg['xray'])), frames)
        save(stage='frames-to-bit')
        bit = out / 'design.bit'
        run([str(cfg['frames2bit']), '--part_file='+str(cfg['database'] / PART / 'part.yaml'),
             '--part_name='+PART, '--frm_file='+str(frames), '--output_file='+str(bit)], out, 'frames-to-bit')
        unchanged(inventory)
        save(status='FULL_PCIE_CONFIGURATION_ASSEMBLY_PASS_TIMING_NOT_QUALIFIED', stage='assembled',
             artifacts={p.name:describe(p) for p in (frames,bit)}, database=str(cfg['database']))
        run([sys.executable,str(ROOT / 'tools/fedora_check_pcie_image.py'),
             '--pipeline',str(mp), '--out',str(out / 'independent-image-check.json')], out, 'independent-image-check')
        unchanged(inventory)
        save(status='FULL_PCIE_CONFIGURATION_ASSEMBLY_PASS_TIMING_NOT_QUALIFIED',
             stage='independently-checked', independent_check=describe(out / 'independent-image-check.json'))
        return info
    except BaseException as error:
        save(status='FAIL', error=str(error))
        raise


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('action', choices=('prepare','route','build'))
    ap.add_argument('--synthesis',required=True,type=Path)
    ap.add_argument('--litedram-core',required=True,type=Path)
    ap.add_argument('--backend-selection',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args = ap.parse_args()
    result = execute(args.action,args.synthesis,args.litedram_core,args.backend_selection,args.out)
    print(result['status'])
    print(args.out / 'pipeline.json')


if __name__ == '__main__':
    main()
