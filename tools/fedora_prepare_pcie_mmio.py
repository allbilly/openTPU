#!/usr/bin/env python3
"""Build the local aligned MMIO helper; performs no PCIe hardware accesses."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    if platform.machine() not in ('x86_64', 'aarch64'):
        raise RuntimeError('MMIO helper is supported on x86_64 and aarch64 Linux hosts')
    source = ROOT/'tools/pcie_mmio.c'
    out = ROOT/'build/fedora-pcie-mmio'
    out.mkdir(parents=True, exist_ok=True)
    target = out/'libotpu_mmio.so'
    cmd = ['gcc','-std=c11','-D_DEFAULT_SOURCE','-O2','-Wall','-Wextra','-Werror',
           '-fPIC','-shared',str(source),'-o',str(target)]
    subprocess.run(cmd, check=True)
    report = dict(status='BUILT_NOT_PHYSICALLY_TESTED', architecture=platform.machine(), command=cmd,
                  source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  library_sha256=hashlib.sha256(target.read_bytes()).hexdigest())
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(target)


if __name__ == '__main__':
    main()
