#!/usr/bin/env python3
"""Finalize the selected full replay only after verified native/service success."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

from fedora_openxc7 import describe


ROUTE_PASS = 'FULL_PLACED_REPLAY_NATIVE_ROUTE_AND_CLOCK_DRIVER_GATE_PASS_IMAGE_TIMING_PENDING'
IMAGE_PASS = 'FULL_CORRECTED_IMAGE_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED'


def service_state(unit):
    fields = ('ActiveState', 'SubState', 'MainPID', 'InvocationID', 'Result', 'ExecMainStatus',
              'ExecMainStartTimestampMonotonic')
    result = subprocess.run(['systemctl', '--user', 'show', unit,
                             *['--property=' + k for k in fields]],
                            capture_output=True, text=True, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)


def native_state(owner):
    path = Path('/proc') / str(owner['pid']) / 'stat'
    try:
        fields = path.read_text().split(') ', 1)[1].split()
    except FileNotFoundError:
        return {'alive': False}
    if int(fields[19]) != owner['start_ticks']:
        raise ValueError('Recorded native PID was reused')
    return {'alive': fields[0] not in ('X', 'Z'), 'state': fields[0],
            'cpu_ticks': int(fields[11]) + int(fields[12]), 'threads': int(fields[17])}


def follow(preparation, unit, out, once=False):
    prepared = json.loads(preparation.read_text())
    if (prepared['status'] != 'FULL_PLACED_REPLAY_SOURCE_AND_ASSEMBLY_INPUTS_PREPARED_WAITING_FOR_ROUTE'
            or prepared.get('route_kind') != 'PLACED_REPLAY'):
        raise ValueError('Complete exact full replay image preparation required')
    route = Path(prepared['route_directory'])
    assembler = Path(__file__).with_name('openxc7_clock_image_assemble.py').resolve()
    frozen = [describe(preparation), describe(assembler), prepared['planned_inputs']]
    initial_service = service_state(unit)
    if initial_service.get('ExecMainStartTimestampMonotonic', '0') == '0':
        raise ValueError('Recorded route service start identity required')
    initial_native = native_state(prepared['native_owner'])
    native_proc = Path('/proc') / str(prepared['native_owner']['pid'])
    if (not initial_native['alive'] or initial_service['ActiveState'] != 'active'
            or not (native_proc / 'cgroup').read_text().strip().endswith('/' + unit)
            or (native_proc / 'stat').read_text().split(') ', 1)[1].split()[1] != initial_service['MainPID']):
        raise ValueError('Follow-up must start on the exact live native owner and its controller service')
    out.mkdir(parents=True, exist_ok=False)
    shutil.copy2(__file__, out / 'helper.py')
    info = {'status': 'WAITING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'helper': describe(__file__), 'preparation': frozen[0], 'assembler': frozen[1],
            'unit': unit, 'service_invocation': initial_service['InvocationID'],
            'service_start_monotonic': initial_service['ExecMainStartTimestampMonotonic'],
            'native_owner': prepared['native_owner'], 'route_directory': str(route),
            'scope': 'FULL_REPLAY_OFFLINE_IMAGE_AFTER_ACTUAL_NATIVE_ROUTE_SUCCESS',
            'hardware_accessed': False, 'flash_written': False,
            'numerical_timing': 'NOT_QUALIFIED'}

    def save(**values):
        info.update(values)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def unchanged():
        if any(describe(v['path']) != v for v in frozen):
            raise ValueError('Prepared inputs or assembler changed during wait')

    try:
        while True:
            unchanged()
            state = service_state(unit)
            if (state.get('ExecMainStartTimestampMonotonic') != info['service_start_monotonic']
                    or (state['ActiveState'] == 'active' and state.get('InvocationID') != info['service_invocation'])):
                raise ValueError('Route service invocation changed; no automatic restart permitted')
            try:
                current = json.loads((route / 'manifest.json').read_text())
            except json.JSONDecodeError:
                if state['ActiveState'] == 'active' and state['MainPID'] != '0':
                    save(status='WAITING_FOR_CONTROLLER_RECEIPT_WRITE', service=state)
                    if once:
                        return 2
                    time.sleep(10)
                    continue
                raise
            if (current['native_pid'] != info['native_owner']['pid']
                    or current['native_start_ticks'] != info['native_owner']['start_ticks']
                    or current['binary'] != prepared['binary'] or current['chipdb'] != prepared['chipdb']
                    or current['profile'] != prepared['profile']):
                raise ValueError('Selected full replay owner or profile changed')
            native = native_state(info['native_owner'])
            if current['status'] == 'RUNNING':
                if state['ActiveState'] != 'active' or state['MainPID'] == '0':
                    raise ValueError('Route service stopped without a terminal route receipt')
                save(status='WAITING_FOR_VERIFIED_ISOLATED_ROUTE' if native['alive']
                     else 'WAITING_FOR_LIVE_CONTROLLER_FINALIZATION', native=native, service=state,
                     observed_utc=datetime.now(timezone.utc).isoformat())
                if once:
                    print(info['status'], flush=True)
                    return 2
                time.sleep(10)
                continue
            if current['status'] != ROUTE_PASS or current.get('native_exit') != 0:
                raise ValueError('Full native route did not complete successfully: ' + current['status'])
            if state['ActiveState'] == 'active' and state['MainPID'] != '0':
                save(status='WAITING_FOR_SUCCESSFUL_CONTROLLER_EXIT', service=state)
                if once:
                    return 2
                time.sleep(10)
                continue
            if (native['alive'] or state['Result'] != 'success' or state['ExecMainStatus'] != '0'
                    or (route / 'route.exit').read_text().strip() != '0'):
                raise ValueError('Actual native and service success required before image assembly')
            save(status='FULL_NATIVE_ROUTE_SUCCESS_IMAGE_ASSEMBLY_RUNNING', service=state,
                 terminal_route=describe(route / 'manifest.json'))
            image = out / 'image'
            command = [sys.executable, str(assembler), '--preparation', str(preparation), '--out', str(image)]
            (out / 'assembly.command.json').write_text(json.dumps(command, indent=2) + '\n')
            with (out / 'assembly.log').open('w') as log:
                code = subprocess.run(command, cwd=Path(__file__).resolve().parent.parent,
                                      stdout=log, stderr=subprocess.STDOUT).returncode
            (out / 'assembly.exit').write_text(str(code) + '\n')
            unchanged()
            if code:
                raise RuntimeError('Strict full image assembly exit ' + str(code))
            result = json.loads((image / 'manifest.json').read_text())
            if result['status'] != IMAGE_PASS or result['route_kind'] != 'PLACED_REPLAY':
                raise ValueError('Complete strict replay image checks required')
            save(status='FULL_OFFLINE_REPLAY_IMAGE_CHECKS_PASS_NUMERICAL_TIMING_AND_HARDWARE_PENDING',
                 assembly_exit=code, image=describe(image / 'manifest.json'),
                 completed_utc=datetime.now(timezone.utc).isoformat())
            print(info['status'], flush=True)
            return 0
    except Exception as exc:
        save(status='FAIL', error=repr(exc), failed_utc=datetime.now(timezone.utc).isoformat())
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('preparation', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--unit', required=True)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    raise SystemExit(follow(args.preparation.resolve(), args.unit, args.out.resolve(), args.once))
