#!/usr/bin/env python3
"""Inventory Mac FPGA tools without opening a programmer or changing hardware.

USB serial numbers, shell history, environment variables and credentials are
not collected. The result does not establish that programming or XVC works.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys


def usb_devices(tree):
    """Keep only product name and VID/PID from system_profiler's nested JSON."""
    result = []

    def visit(node):
        if isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, dict):
            if 'vendor_id' in node and 'product_id' in node:
                item = {'name': node.get('_name', 'USB device')}
                for key in ('vendor_id', 'product_id'):
                    match = re.search(r'0x[0-9a-fA-F]{4}', str(node[key]))
                    item[key] = match.group(0).lower() if match else 'unknown'
                result.append(item)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    visit(value)

    visit(tree)
    return result


def command(argv, timeout=15):
    try:
        run = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return {'returncode': run.returncode,
                'output': (run.stdout + run.stderr).strip()[:2000]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'error': str(error)}


def inventory(root):
    result = dict(status='READ_ONLY_INVENTORY_PROGRAMMING_NOT_TESTED',
                  created_utc=datetime.now(timezone.utc).isoformat(),
                  system=platform.system(), machine=platform.machine(),
                  python={'executable': sys.executable, 'version': platform.python_version()},
                  tools={}, packages={}, local_scripts={}, usb=[])
    for name, flag in (('openFPGALoader', '--Version'), ('openocd', '--version'),
                       ('cmake', '--version'), ('pkg-config', '--version')):
        executable = shutil.which(name)
        result['tools'][name] = ({'path': executable, **command([executable, flag])}
                                 if executable else {'available': False})
    for name in ('numpy', 'pyusb', 'libusb-package', 'torch', 'transformers'):
        try:
            result['packages'][name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result['packages'][name] = None
    for name in ('transport.py', 'run_lfm2.py'):
        path = root / 'build/chestnut-lfm' / name
        result['local_scripts'][str(path.relative_to(root))] = (
            {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            if path.is_file() else {'present': False})
    if platform.system() == 'Darwin':
        # Parse the complete output; command() deliberately truncates version text.
        try:
            run = subprocess.run(['/usr/sbin/system_profiler', 'SPUSBDataType', '-json'],
                                 capture_output=True, text=True, timeout=45, check=True)
            result['usb'] = usb_devices(json.loads(run.stdout))
        except (OSError, ValueError, subprocess.SubprocessError) as error:
            result['usb_error'] = str(error)
    else:
        result['usb_note'] = 'Run on macOS to inventory USB programmers.'
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='new JSON receipt; never overwritten')
    args = parser.parse_args()
    if args.out.exists():
        parser.error('Choose a new --out file')
    result = inventory(Path(__file__).resolve().parents[1])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open('x') as stream:
        json.dump(result, stream, indent=2)
        stream.write('\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
