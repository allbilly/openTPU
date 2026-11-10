#!/usr/bin/env python3
"""Freeze full source and assembly provenance while the corrected route runs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil

from fedora_openxc7 import describe, digest, configuration, PART
from fedora_check_jtag_image import select_jtag_backend, synthesis_witness, TOP


def prepare(full_gate: Path, primitive_gate: Path, selection: Path, route: Path, out: Path):
    full = json.loads(full_gate.read_text())
    primitive = json.loads(primitive_gate.read_text())
    previous = json.loads(selection.read_text())
    current = json.loads((route / 'manifest.json').read_text())
    if (full['status'] != 'FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS'
            or primitive['status'] != 'FIVE_EXACT_PRIMITIVE_GRAPHS_FRAMES_AND_RESTORED_CLOCK_BITS_PASS'
            or primitive['binary'] != full['binary'] or primitive['chipdb'] != full['chipdb']
            or current['full_gate'] != describe(full_gate)
            or current['profile'] != full['profile'] or current['binary'] != full['binary']
            or current['chipdb'] != full['chipdb']):
        raise ValueError('Actual corrected route and completed full/primitive gates differ')
    if current['status'] != 'RUNNING':
        raise ValueError('Preparation currently requires the verified live full route')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'full_gate': describe(full_gate), 'primitive_gate': describe(primitive_gate),
            'previous_selection': describe(selection), 'route_directory': str(route),
            'binary': full['binary'], 'chipdb': full['chipdb'], 'profile': full['profile'],
            'helper': describe(__file__), 'part': PART, 'hardware_accessed': False,
            'scope': 'FULL_SOURCE_AND_ASSEMBLY_PROVENANCE_NOT_COMPLETED_ROUTE_OR_IMAGE',
            'numerical_timing': 'NOT_QUALIFIED', 'image': None}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='original-exact-backend-and-synthesis-provenance')
        _, _, inventory = select_jtag_backend(selection)
        counts = synthesis_witness(previous)
        for item in [full['binary'], full['chipdb'], *full['full_inputs'].values(),
                     *full['outputs'].values(), describe(full_gate), describe(primitive_gate),
                     describe(selection), previous['mapped_checkpoint'], previous['adopted_synthesis_manifest']]:
            if describe(item['path']) != item:
                raise ValueError('Pinned full source or qualification changed')
            inventory[item['path']] = item['sha256']
        save(stage='exact-mapped-graph-and-only-two-mmcm-locs')
        design = json.loads(Path(previous['mapped_checkpoint']['path']).read_text())
        cells = design['modules'][TOP]['cells']
        locs = {'u_ld.ldmmcm0': 'MMCME2_ADV_X0Y2', 'u_ld.ldmmcm1': 'MMCME2_ADV_X0Y6'}
        for name, loc in locs.items():
            if cells[name]['type'] != 'MMCME2_ADV':
                raise ValueError('Actual DDR write-clock generator missing')
            cells[name]['attributes']['LOC'] = loc
        expected = hashlib.sha256((json.dumps(design) + '\n').encode()).hexdigest()
        del design, cells
        if expected != full['full_inputs']['constrained.json']['sha256']:
            raise ValueError('Route graph differs from the full mapped graph plus two MMCM LOCs')
        argv = json.loads((route / 'route.command.json').read_text())
        expected_flags = {'--json': full['full_inputs']['constrained.json']['path'],
                          '--chipdb': full['chipdb']['path'], '--device': PART, '--threads': '8',
                          '--freq': '100.0', '--placer': 'static', '--router': 'router2',
                          '--write': str(route / 'routed.json'), '--report': str(route / 'timing.json')}
        if argv[0] != full['binary']['path']:
            raise ValueError('Full route executable differs')
        for flag, value in expected_flags.items():
            if argv.count(flag) != 1 or argv[argv.index(flag) + 1] != value:
                raise ValueError('Full route option differs: ' + flag)
        if ('xdc=' + full['full_inputs']['openxc7.xdc']['path'] not in argv
                or 'fasm=' + str(route / 'design.raw.fasm') not in argv or 'clock-loc-contract' not in argv):
            raise ValueError('Full constraints, FASM destination or early clock LOC option differs')
        proc = Path('/proc') / str(current['native_pid'])
        fields = (proc / 'stat').read_text().split()
        native_argv = [s.decode() for s in (proc / 'cmdline').read_bytes().split(b'\0') if s]
        if (int(fields[21]) != current['native_start_ticks'] or native_argv != argv
                or os.readlink(proc / 'exe') != full['binary']['path']):
            raise ValueError('Exact native route owner is no longer live')
        cfg = configuration()
        python = (cfg['fasm2frames'].parent / 'python').resolve()
        tools = {'python': describe(python), 'assembler': describe(Path(__file__).with_name('openxc7_fasm2frames.py')),
                 'frames2bit': describe(cfg['frames2bit']), 'database': str(cfg['database']), 'xray': str(cfg['xray'])}
        for key in ('python', 'assembler', 'frames2bit'):
            inventory[tools[key]['path']] = tools[key]['sha256']
        for p in cfg['database'].rglob('*'):
            if p.is_file():
                inventory[str(p)] = digest(p)
        for directory in ('prjxray', 'utils'):
            for p in (cfg['xray'] / directory).rglob('*.py'):
                inventory[str(p)] = digest(p)
        for name in ('vref-plan.json', 'constraint-audit.json', 'hard-cell-timing-audit.json'):
            p = Path(full['full_inputs']['constrained.json']['path']).parent / name
            inventory[str(p)] = digest(p)
        inventory[str(route / 'route.command.json')] = digest(route / 'route.command.json')
        inventory[str(Path(__file__).resolve())] = digest(__file__)
        (out / 'planned-inputs.json').write_text(json.dumps(inventory, indent=2) + '\n')
        save(status='FULL_CORRECTED_ROUTE_SOURCE_AND_ASSEMBLY_INPUTS_PREPARED_WAITING_FOR_ROUTE',
             netlist_transform='COMPLETE_MAPPED_GRAPH_AND_ONLY_TWO_MMCM_LOCS_VERIFIED',
             mapped_counts=dict(counts), assembly_tools=tools, planned_inputs=describe(out / 'planned-inputs.json'),
             native_owner={'pid': current['native_pid'], 'start_ticks': current['native_start_ticks']},
             route_command=describe(route / 'route.command.json'),
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('full-gate', 'primitive-gate', 'selection', 'route', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.full_gate.resolve(), args.primitive_gate.resolve(), args.selection.resolve(),
            args.route.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
