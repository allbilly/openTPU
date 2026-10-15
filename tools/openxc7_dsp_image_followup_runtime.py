#!/usr/bin/env python3
"""Wait for the preserved full route, then inspect a separate DSP-corrected image."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import time

from fedora_openxc7 import describe, digest, PART
from fedora_check_pcie_image import compare_frames, STRUCTURE_CHECKER
from openxc7_bufg_route_guard import fasm_check
from openxc7_dsp_fasm_correction import correct, rewrite


def identity(pid):
    try:
        fields = (Path('/proc') / str(pid) / 'stat').read_text().split(') ', 1)[1].split()
        return int(fields[19]) if fields[0] not in ('Z', 'X') else None
    except FileNotFoundError:
        return None


def service(unit):
    result = subprocess.run(['systemctl', '--user', 'show', unit, '-p', 'Result', '-p', 'ExecMainStatus',
                             '-p', 'MainPID', '-p', 'InvocationID', '-p', 'ActiveState', '-p', 'SubState'],
                            capture_output=True, text=True, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def read_live_json(path):
    for attempt in range(5):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            if attempt == 4:
                raise
            time.sleep(0.2)


def follow(prepared, parent_image, route_unit, parent_unit, out):
    proof = json.loads(prepared.read_text())
    if proof['status'] != 'NATIVE_DIFFERENTIAL_FASM_REPRODUCTION_AND_FULL_717_DSP_CORRECTION_MAP_PASS_ROUTE_PENDING':
        raise ValueError('Completed native differential and full DSP correction map required')
    image_preparation = Path(proof['image_preparation']['path'])
    plan = json.loads(image_preparation.read_text())
    route = Path(plan['route_directory'])
    owner = plan['native_owner']
    route_service, parent_service = service(route_unit), service(parent_unit)
    if identity(owner['pid']) != owner['start_ticks'] or route_service['SubState'] != 'running':
        raise ValueError('Launch requires the actual preserved native route to be alive')
    if parent_service['SubState'] != 'running':
        raise ValueError('The original offline image follow-up must be alive')
    out.mkdir(parents=True, exist_ok=False)
    frozen = [describe(prepared), proof['helper'], proof['image_preparation'], *proof['outputs'].values(),
              describe(__file__), describe(Path(__file__).with_name('fedora_check_pcie_image.py')), describe(STRUCTURE_CHECKER)]
    info = {'status': 'WAITING_FOR_NATIVE_ROUTE_AND_ORIGINAL_OFFLINE_IMAGE',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'inputs': frozen,
            'prepared': describe(prepared), 'parent_image': str(parent_image),
            'route_unit': route_unit, 'parent_unit': parent_unit,
            'route_invocation': route_service['InvocationID'], 'parent_invocation': parent_service['InvocationID'],
            'native_owner': owner, 'profile': plan['profile'], 'hardware_accessed': False,
            'hardware_ready': False, 'numerical_timing': 'NOT_QUALIFIED',
            'live_route_changed': False, 'original_image_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def unchanged():
        if any(describe(item['path']) != item for item in frozen):
            raise ValueError('Qualified correction/follow-up provenance changed')

    def run(name, argv, env):
        save(stage=name)
        (out / (name + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (name + '.log')).open('w') as log:
            process = subprocess.Popen(argv, cwd=out, env=env, stdout=log, stderr=subprocess.STDOUT)
            save(child_pid=process.pid)
            code = process.wait()
        (out / (name + '.exit')).write_text(str(code) + '\n')
        save(child_pid=None)
        if code:
            raise RuntimeError(name + ' failed: ' + str(code))
        unchanged()

    try:
        save()
        while True:
            unchanged()
            state = read_live_json(route / 'manifest.json')
            rs, ps = service(route_unit), service(parent_unit)
            if rs['InvocationID'] != info['route_invocation'] or ps['InvocationID'] != info['parent_invocation']:
                raise ValueError('A pinned service invocation changed')
            if state['status'] == 'RUNNING':
                if identity(owner['pid']) != owner['start_ticks']:
                    # Allow the original controller to write its terminal receipt.
                    if rs['MainPID'] == '0':
                        raise ValueError('Native route disappeared without a terminal receipt')
                time.sleep(15)
                continue
            if state['status'] != 'FULL_PLACED_REPLAY_NATIVE_ROUTE_AND_CLOCK_DRIVER_GATE_PASS_IMAGE_TIMING_PENDING':
                raise ValueError('Full native route failed or lacks the required terminal gates')
            if rs['MainPID'] != '0':
                time.sleep(15)
                continue
            if rs['Result'] != 'success' or rs['ExecMainStatus'] != '0':
                raise ValueError('Native route service failed')
            if parent_image.exists():
                parent = read_live_json(parent_image)
                if parent['status'] == 'FAIL':
                    raise ValueError('Original offline image assembly failed')
                if parent['status'] == 'FULL_CORRECTED_IMAGE_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED':
                    if ps['MainPID'] != '0':
                        time.sleep(15)
                        continue
                    if ps['Result'] != 'success' or ps['ExecMainStatus'] != '0':
                        raise ValueError('Original image follow-up service failed')
                    break
            if ps['MainPID'] == '0':
                raise ValueError('Original image follow-up ended without successful image receipt')
            time.sleep(15)
        if parent['preparation'] != describe(image_preparation):
            raise ValueError('Original offline image used a different source preparation')
        frozen += [describe(parent_image), *parent['artifacts'].values(), parent['planned_inputs']]
        unchanged()
        inventory = json.loads(Path(parent['planned_inputs']['path']).read_text())

        def verify_inventory():
            with ThreadPoolExecutor(max_workers=8) as pool:
                if not all(pool.map(lambda pair: digest(pair[0]) == pair[1], inventory.items())):
                    raise ValueError('Original full image source/tool/database inventory changed')

        verify_inventory()
        save(status='RUNNING', stage='correct-native-full-dsp-fasm', parent_image_receipt=describe(parent_image))
        if correct(prepared, out / 'native-correction') != 0:
            raise ValueError('Terminal full DSP correction unexpectedly deferred')
        correction = json.loads((out / 'native-correction/manifest.json').read_text())
        records = json.loads(Path(proof['outputs']['full-dsp-map.json']['path']).read_text())
        original_fasm = Path(parent['artifacts']['design.fasm']['path'])
        fasm = out / 'design.fasm'
        fasm.write_text(rewrite(original_fasm, records))
        clock_gate = fasm_check(fasm)
        tools = plan['assembly_tools']
        env = dict(os.environ, PYTHONPATH=tools['xray'], OTPU_XRAY_DB=tools['database'])
        frames, bit = out / 'design.frames', out / 'design.bit'
        run('strict-frames', [tools['python_argv'], tools['assembler']['path'], '--db-root', tools['database'],
                             '--part', PART, str(fasm), str(frames)], env)
        run('frames-to-bit', [tools['frames2bit']['path'], '--part_file=' + str(Path(tools['database']) / PART / 'part.yaml'),
                              '--part_name=' + PART, '--frm_file=' + str(frames), '--output_file=' + str(bit)], env)
        spec = importlib.util.spec_from_file_location('dsp_image_packet_checker', STRUCTURE_CHECKER)
        checker = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        structure = checker.check(bit, fasm, 2)
        payload = compare_frames(bit, frames, Path(tools['database']) / PART / 'part.json')
        verify_inventory()
        unchanged()
        save(status='FULL_DSP_CORRECTED_IMAGE_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED',
             completed_utc=datetime.now(timezone.utc).isoformat(), native_correction=describe(out / 'native-correction/manifest.json'),
             corrected_dsp_count=correction['full_dsps'], preserved_parent_vref=True,
             clock_driver_gate=clock_gate, structure=structure, frame_comparison=payload, crc='NOT_CHECKED',
             full_source_inventory=parent['planned_inputs'], inputs=frozen,
             artifacts={p.name: describe(p) for p in (fasm, frames, bit)})
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('prepared', 'parent-image', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    for name in ('route-unit', 'parent-unit'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    follow(args.prepared.resolve(), args.parent_image.resolve(), args.route_unit, args.parent_unit, args.out.resolve())


if __name__ == '__main__':
    main()
