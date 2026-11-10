#!/usr/bin/env python3
"""Wait for the existing verified full DSP image, then create a CRC-only copy."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

from fedora_openxc7 import describe
from openxc7_bitstream_crc_image import prepare, FULL_PARENT, PROFILE


def unit(name):
    args = ['systemctl', '--user', 'show', name, '-p', 'ActiveState', '-p', 'SubState',
            '-p', 'MainPID', '-p', 'InvocationID', '-p', 'Result', '-p', 'ExecMainStatus']
    result = subprocess.run(args, capture_output=True, text=True, check=True)
    return dict(line.split('=', 1) for line in result.stdout.splitlines())


def read(path):
    for attempt in range(5):
        try:
            return json.loads(path.read_text())
        except json.JSONDecodeError:
            if attempt == 4:
                raise
            time.sleep(0.1)


def follow(qualification, converter_gate, parent, parent_unit, out):
    gate = read(converter_gate)
    if gate['status'] != 'ACTUAL_CRC_CONVERTER_REPRODUCES_QUALIFIED_FIXTURE_BYTE_IDENTICALLY_AND_REJECTS_LIVE_FULL_IMAGE_WITHOUT_OUTPUT':
        raise ValueError('Actual converter fixture and live full-image guard required')
    initial = read(parent)
    if initial['profile'] != PROFILE:
        raise ValueError('Full original profile required')
    owner = unit(parent_unit)
    route_unit = initial['route_unit']
    route_owner = unit(route_unit)
    if (owner['MainPID'] == '0' or owner['SubState'] != 'running'
            or owner['InvocationID'] != 'af76cb3843e24d14989509e9c443a1e9'
            or route_owner['InvocationID'] != initial['route_invocation']):
        raise ValueError('Existing full DSP and native route service identities differ')
    proof = read(qualification)
    frozen = [describe(qualification), describe(converter_gate), gate['helper'],
              describe(__file__), *proof['inputs']]
    for item in frozen:
        if describe(item['path']) != item:
            raise ValueError('Pinned CRC converter/qualification changed')
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'WAITING_FOR_VERIFIED_FULL_DSP_IMAGE',
               'created_utc': datetime.now(timezone.utc).isoformat(), 'inputs': frozen,
               'parent_image': str(parent), 'parent_unit': parent_unit,
               'parent_invocation': owner['InvocationID'], 'route_unit': route_unit,
               'route_invocation': route_owner['InvocationID'], 'native_owner': initial['native_owner'],
               'profile': PROFILE, 'hardware_ready': False, 'hardware_accessed': False,
               'numerical_timing': 'NOT_QUALIFIED', 'live_route_changed': False,
               'original_image_changed': False}

    def save(**fields):
        receipt.update(fields)
        (out / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')

    try:
        while True:
            for item in frozen:
                if describe(item['path']) != item:
                    raise ValueError('Pinned CRC input changed while waiting')
            current, route = unit(parent_unit), unit(route_unit)
            if (current['InvocationID'] != receipt['parent_invocation']
                    or route['InvocationID'] != receipt['route_invocation']):
                raise ValueError('Parent/native service was replaced')
            parent_receipt = read(parent)
            if parent_receipt['status'] == 'FAIL':
                raise ValueError('Full DSP parent image failed')
            if current['MainPID'] == '0' and (current['Result'] != 'success' or current['ExecMainStatus'] != '0'):
                raise ValueError('Actual full DSP parent service exited unsuccessfully')
            if (parent_receipt['status'] == FULL_PARENT and current['MainPID'] == '0'):
                if (current['SubState'] != 'exited' or route['MainPID'] != '0'
                        or route['Result'] != 'success' or route['ExecMainStatus'] != '0'):
                    raise ValueError('Actual successful terminal full native and DSP services required')
                break
            save(observed_utc=datetime.now(timezone.utc).isoformat(), parent_status=parent_receipt['status'])
            time.sleep(15)
        save(status='RUNNING', stage='full-crc-copy-after-actual-parent-and-route-exit-zero',
             parent_receipt=describe(parent))
        code = prepare(qualification, parent, False, out / 'image')
        (out / 'crc-image.exit').write_text(str(code) + '\n')
        if code:
            raise ValueError('Terminal parent unexpectedly deferred or failed CRC conversion')
        image = read(out / 'image/manifest.json')
        if image['status'] != 'FULL_DSP_CORRECTED_IMAGE_CRC_CHECKPOINTS_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED':
            raise ValueError('CRC converter did not complete its full offline gates')
        save(status=image['status'], image_receipt=describe(out / 'image/manifest.json'),
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(receipt['status'], flush=True)
    except Exception as error:
        save(status='FAIL', error=repr(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('qualification', 'converter-gate', 'parent-image', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--parent-unit', required=True)
    args = parser.parse_args()
    follow(args.qualification.resolve(), args.converter_gate.resolve(), args.parent_image.resolve(),
           args.parent_unit, args.out.resolve())


if __name__ == '__main__':
    main()
