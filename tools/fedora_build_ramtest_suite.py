#!/usr/bin/env python3
"""Historical DDR800 MIG diagnostic suite, retired from implementation.

The RAM-only images lack the required JTAG and PCIe runtime interfaces.
Retain the variant identities and receipts for historical review; new builds
must use a reviewed combined-interface design.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

try:
    from .workspace_paths import vivado_bin
except ImportError:
    from workspace_paths import vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / 'tools/fedora_build_ramtest_mig.py'
VARIANTS = (
    ('ch0-address', '0', 'address', 'c0161010'),
    ('ch1-address', '1', 'address', 'c0161011'),
    ('both-zeros', 'both', 'zeros', 'c0161020'),
    ('both-ones', 'both', 'ones', 'c0161021'),
    ('both-walking1', 'both', 'walking1', 'c0161025'),
    ('both-walking0', 'both', 'walking0', 'c0161026'),
    ('both-prbs', 'both', 'prbs', 'c0161027'),
)
BUILT = 'RAM_ONLY_BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def unit_state(name):
    result = subprocess.run(
        ['systemctl', '--user', 'show', name, '-p', 'LoadState', '-p', 'ActiveState',
         '-p', 'SubState', '-p', 'ExecMainStatus', '-p', 'InvocationID'],
        check=True, text=True, capture_output=True)
    state = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--vivado', default=str(vivado_bin() / 'vivado'))
    parser.add_argument('--wait-unit', help='Wait for this existing user service to stop; never restart it')
    args = parser.parse_args()
    parser.error('This historical RAM-only suite is retired: every new image requires '
                 'both JTAG and PCIe runtime memory/control interfaces. '
                 'Existing sources and evidence remain available for review.')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    builder_sha = sha(BUILDER)
    manifest = dict(status='QUEUED', started_utc=now(), ddr_mts=800,
                    physical_tests_performed=False, builder_sha256=builder_sha,
                    suite_source_sha256=sha(Path(__file__)),
                    prerequisite_unit=args.wait_unit, variants=[])
    for name, channel, pattern, build_id in VARIANTS:
        command = [sys.executable, '-u', str(BUILDER), '--vivado', args.vivado,
                   '--ddr-mts', '800', '--channels', channel, '--pattern', pattern,
                   '--build-id', build_id, '--out', str(out / name)]
        manifest['variants'].append(dict(name=name, channels=channel, pattern=pattern,
                                         build_id=build_id, command=command, status='QUEUED'))

    def save():
        manifest['updated_utc'] = now()
        temporary = out / 'manifest.json.tmp'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(out / 'manifest.json')

    save()
    try:
        if args.wait_unit:
            manifest['status'] = 'WAITING_FOR_PREREQUISITE'
            previous = None
            while True:
                state = unit_state(args.wait_unit)
                identity = state['InvocationID']
                # Successful transient units may be garbage-collected. A
                # missing handle is terminal only after we observed it live.
                if state.get('LoadState') == 'not-found' and previous:
                    manifest['prerequisite_state'] = state
                    save()
                    break
                if state.get('LoadState') != 'loaded':
                    raise RuntimeError('Cannot identify prerequisite unit: ' + args.wait_unit)
                if previous and identity and identity != previous:
                    raise RuntimeError('Prerequisite invocation changed while waiting')
                previous = identity or previous
                manifest['prerequisite_state'] = state
                save()
                if state['ActiveState'] in ('inactive', 'failed'):
                    break
                if state['ActiveState'] not in ('activating', 'active', 'deactivating'):
                    raise RuntimeError('Unexpected prerequisite state: ' + repr(state))
                time.sleep(10)
            # The diagnostic builds are independent of the compute image's
            # outcome. Record that outcome without retrying or altering it.
        manifest['status'] = 'BUILDING_SEQUENTIALLY'
        save()
        for item in manifest['variants']:
            if sha(BUILDER) != builder_sha:
                raise RuntimeError('RAM-only builder changed after suite preparation')
            item.update(status='BUILD_RUNNING', started_utc=now())
            save()
            print('BUILDING', item['name'], item['build_id'], flush=True)
            with (out / (item['name'] + '.log')).open('w') as log:
                result = subprocess.run(item['command'], cwd=ROOT, stdout=log,
                                        stderr=subprocess.STDOUT)
            item.update(exit_code=result.returncode, finished_utc=now())
            receipt_path = out / item['name'] / 'manifest.json'
            if receipt_path.is_file():
                receipt = json.loads(receipt_path.read_text())
                item['build_manifest_sha256'] = sha(receipt_path)
                item['build_status'] = receipt['status']
            else:
                receipt = {}
            if result.returncode == 0 and receipt.get('status') == BUILT:
                bit = out / item['name'] / 'ramtest.bit'
                if sha(bit) != receipt['bitstream_sha256']:
                    raise RuntimeError('Completed image changed: ' + item['name'])
                item.update(status='BUILT_CDC_PIN_REVIEW_AND_PHYSICAL_TESTS_PENDING',
                            bitstream_sha256=receipt['bitstream_sha256'])
            else:
                item['status'] = 'BUILD_FAILED'
            save()
        failed = [item['name'] for item in manifest['variants'] if item['status'] == 'BUILD_FAILED']
        manifest['status'] = ('SOME_BUILDS_FAILED' if failed else
                              'ALL_BUILT_CDC_PIN_REVIEW_AND_PHYSICAL_TESTS_PENDING')
        manifest['failed_variants'] = failed
        save()
        return bool(failed)
    except Exception as error:
        manifest.update(status='FAIL', error=str(error))
        save()
        raise


if __name__ == '__main__':
    raise SystemExit(main())
