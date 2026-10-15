#!/usr/bin/env python3
"""Assemble and independently inspect a terminal corrected full route."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest, PART
from fedora_check_pcie_image import compare_frames, STRUCTURE_CHECKER
from openxc7_bufg_route_guard import fasm_check
from openxc7_vref import apply as apply_vref


def assemble(preparation: Path, out: Path):
    p = json.loads(preparation.read_text())
    replay = p.get('route_kind') == 'PLACED_REPLAY'
    prepared_status = ('FULL_PLACED_REPLAY_SOURCE_AND_ASSEMBLY_INPUTS_PREPARED_WAITING_FOR_ROUTE' if replay
                       else 'FULL_CORRECTED_ROUTE_SOURCE_AND_ASSEMBLY_INPUTS_PREPARED_WAITING_FOR_ROUTE')
    if p['status'] != prepared_status:
        raise ValueError('Complete immutable full-source preparation required')
    route = Path(p['route_directory'])
    m = json.loads((route / 'manifest.json').read_text())
    if m['status'] == 'RUNNING':
        proc = Path('/proc') / str(p['native_owner']['pid'])
        if proc.exists():
            fields = (proc / 'stat').read_text().split(') ', 1)[1].split()
            if int(fields[19]) != p['native_owner']['start_ticks']:
                raise ValueError('Recorded route PID was reused')
            if fields[0] not in ('Z', 'X'):
                print('WAITING_FOR_VERIFIED_LIVE_FULL_ROUTE PID ' + str(p['native_owner']['pid']), flush=True)
                return 2
        print('WAITING_FOR_NATIVE_ROUTE_CONTROLLER_TERMINAL_RECEIPT', flush=True)
        return 2
    expected = ('FULL_PLACED_REPLAY_NATIVE_ROUTE_AND_CLOCK_DRIVER_GATE_PASS_IMAGE_TIMING_PENDING' if replay
                else 'FULL_NATIVE_ROUTE_AND_FASM_CLOCK_DRIVER_GATE_PASS_IMAGE_AND_TIMING_QUALIFICATION_PENDING')
    if (m['status'] != expected or m['native_exit'] != 0
            or (route / 'route.exit').read_text().strip() != '0'
            or m['binary'] != p['binary'] or m['chipdb'] != p['chipdb'] or m['profile'] != p['profile']):
        raise ValueError('Full route has no matching successful native terminal result')
    if replay and (m['candidate'] != p['candidate'] or m['review'] != p['placement_review']
                   or m['timing_reference'] != p['full_gate'] or m.get('physical_assignments') != 464198
                   or m.get('restored_domain_gate') != {'domain_pairs': 18, 'known': 16, 'unknown': 2, 'budgets_identical': True}
                   or m.get('mailbox_limits_reimported') != 1103):
        raise ValueError('Complete replay placement, timing-domain and mailbox terminal gates differ')
    inventory = json.loads(Path(p['planned_inputs']['path']).read_text())
    if describe(p['planned_inputs']['path']) != p['planned_inputs']:
        raise ValueError('Frozen assembly input inventory changed')
    for item in m['outputs'].values():
        if describe(item['path']) != item:
            raise ValueError('Terminal full route output changed')
        inventory[item['path']] = item['sha256']
    reference = m['timing_reference'] if replay else m['full_gate']
    original_inputs = json.loads(Path(reference['path']).read_text())['full_inputs']
    parent = Path(original_inputs['constrained.json']['path']).parent
    original_route = json.loads((parent / 'manifest.json').read_text())
    if original_route['parameters'] != p['profile'] or original_route['part'] != PART:
        raise ValueError('Original DDR and source profile differs')
    for source_name in ('source', 'primitive_libraries'):
        for path, expected_hash in original_route[source_name].items():
            if digest(path) != expected_hash:
                raise ValueError('Original synthesis or primitive source changed')
            inventory[path] = expected_hash
    for key in ('constraint_source', 'vref_adapter'):
        item = original_route[key]
        if describe(item['path']) != item:
            raise ValueError('Original DDR constraint or VREF adapter changed')
        inventory[item['path']] = item['sha256']
    for path in [Path(__file__).resolve(), Path(__file__).with_name('openxc7_vref.py'),
                 Path(__file__).with_name('fedora_check_pcie_image.py'), STRUCTURE_CHECKER, preparation,
                 route / 'manifest.json', route / 'route.exit']:
        inventory[str(path)] = digest(path)

    def unchanged():
        def valid(item):
            path, value = item
            return Path(path).is_file() and digest(path) == value
        with ThreadPoolExecutor(max_workers=8) as pool:
            if not all(pool.map(valid, inventory.items())):
                raise ValueError('Full-route or assembly provenance changed')

    unchanged()
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'preparation': describe(preparation), 'route': describe(route / 'manifest.json'),
            'binary': p['binary'], 'chipdb': p['chipdb'], 'profile': p['profile'], 'part': PART,
            'route_kind': 'PLACED_REPLAY' if replay else 'STATIC',
            'helper': describe(__file__), 'physical_hardware': 'NOT_RUN', 'flash_written': False,
            'numerical_timing': 'NOT_QUALIFIED', 'hardware_ready': False,
            'scope': 'FULL_OFFLINE_IMAGE_ASSEMBLY_PACKET_FRAME_ECC_AND_PROVENANCE'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def run(stage, argv, env):
        save(stage=stage)
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (stage + '.log')).open('w') as log:
            code = subprocess.run(argv, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / (stage + '.exit')).write_text(str(code) + '\n')
        if code:
            raise RuntimeError(stage + ' failed: ' + str(code))
        unchanged()

    try:
        save(stage='terminal-full-route-and-clock-driver-check')
        clock_driver = fasm_check(route / 'design.raw.fasm')
        constraint = Path(original_route['constraint_source']['path'])
        if str(constraint) not in inventory or digest(constraint) != inventory[str(constraint)]:
            raise ValueError('Original literal DDR/VREF source is not pinned')
        tools = p['assembly_tools']
        database = Path(tools['database'])
        fasm = out / 'design.fasm'
        vref = apply_vref(route / 'design.raw.fasm', fasm, constraint, database, out / 'vref-audit.json')
        original_plan = json.loads((parent / 'vref-plan.json').read_text())
        if vref['plan'] != original_plan:
            raise ValueError('Literal VREF plan differs from the full route input')
        frames, bit = out / 'design.frames', out / 'design.bit'
        env = dict(os.environ, PYTHONPATH=tools['xray'], OTPU_XRAY_DB=str(database))
        run('strict-frames', [tools['python']['path'], tools['assembler']['path'], '--db-root', str(database),
                             '--part', PART, str(fasm), str(frames)], env)
        run('frames-to-bit', [tools['frames2bit']['path'], '--part_file=' + str(database / PART / 'part.yaml'),
                              '--part_name=' + PART, '--frm_file=' + str(frames), '--output_file=' + str(bit)], env)
        if not bit.is_file() or not bit.stat().st_size or not frames.is_file() or not frames.stat().st_size:
            raise ValueError('Full image assembler produced an empty or missing output')
        spec = importlib.util.spec_from_file_location('corrected_full_image_structure', STRUCTURE_CHECKER)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        structure = module.check(bit, fasm, 2)
        payload = compare_frames(bit, frames, database / PART / 'part.json')
        unchanged()
        (out / 'planned-inputs.json').write_text(json.dumps(inventory, indent=2) + '\n')
        save(status='FULL_CORRECTED_IMAGE_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED',
             structure=structure, frame_comparison=payload, clock_driver_gate=clock_driver,
             vref_audit=describe(out / 'vref-audit.json'), planned_inputs=describe(out / 'planned-inputs.json'),
             artifacts={path.name: describe(path) for path in (fasm, frames, bit)},
             crc='NOT_CHECKED', completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
        return 0
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preparation', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    return assemble(args.preparation.resolve(), args.out.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
