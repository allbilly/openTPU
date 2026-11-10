#!/usr/bin/env python3
"""Freeze the matched CH1 LFM2 host, model and calibration data for another PC.

This prepares a host bundle. It does not qualify or program an FPGA image.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--core', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--runtime', type=Path, default=ROOT/'build/fedora-venv/bin/python')
    a = ap.parse_args()
    out = a.out.absolute()
    archive = out.with_suffix('.tar')
    if out.exists() or archive.exists():
        ap.error('Choose a fresh bundle and archive path')
    core = a.core.resolve()
    profile = json.loads((core/'openxc7-profile.json').read_text())
    if (profile['physical_user_channels'], profile['usable_logical_bytes'],
        profile['calibration_mask']) != ([1], 1 << 31, 2):
        ap.error('The generated CH1 recovery core is required')
    for item in profile['files'].values():
        path = core/item['name']
        if path.stat().st_size != item['bytes'] or digest(path) != item['sha256']:
            ap.error('Changed recovery core file: '+str(path))
    model = ROOT/'models/LFM2.5-230M'
    expected = 'f630da86651136c9aee893b04b7542007e90fdd718355358e57e7ecc31517cfd'
    if digest(model/'model.safetensors') != expected:
        ap.error('The previously verified full LFM2 checkpoint changed')
    packages = subprocess.check_output([str(a.runtime.absolute()), '-c',
        'from importlib.metadata import distributions; '
        'print("\\n".join(sorted(d.metadata["Name"]+"=="+d.version for d in distributions() '
        'if d.metadata["Name"].lower() not in ("opentpu","pip"))))'], text=True)
    out.mkdir(parents=True)
    ignored = shutil.ignore_patterns('__pycache__', '*.pyc')
    shutil.copytree(ROOT/'opentpu', out/'opentpu', ignore=ignored)
    shutil.copytree(model, out/'models/LFM2.5-230M', ignore=ignored)
    shutil.copytree(core, out/'core', ignore=ignored)
    (out/'tools').mkdir()
    for name in ['fedora_run_ch1_lfm2.py', 'fedora_matmul_check.py']:
        shutil.copy2(ROOT/'tools'/name, out/'tools'/name)
    (out/'requirements.lock.txt').write_text(packages)
    setup = out/'prepare_env.sh'
    setup.write_text('''#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
sha256sum -c SHA256SUMS
"${OTPU_PYTHON:-python3}" -m venv .venv
.venv/bin/python -m pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.lock.txt
''')
    setup.chmod(0o755)
    run = out/'run_lfm2.sh'
    run.write_text('''#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
sha256sum -c SHA256SUMS
exec .venv/bin/python tools/fedora_run_ch1_lfm2.py --core core --model lfm2 "$@"
''')
    run.chmod(0o755)
    (out/'README.md').write_text('''# Matched CH1 LFM2 host bundle

This bundle contains the full LFM2.5-230M checkpoint, matched local host/compiler
source and generated CH1 DDR800 calibration data. It contains no bitstream.
The Vivado build and four-port ECC test must finish, then the recovery image
must pass its image checks and be loaded into FPGA SRAM.

Use this bundle on the Linux PC with the card in a PCIe slot. Do not mix its
host code with a different openTPU checkout. On this PC:

```bash
./prepare_env.sh
bash opentpu/host/setup_pcie.sh
bash opentpu/host/setup_pcie.sh --rescan
./run_lfm2.sh --dev /dev/xdma0 --out results-lfm2
```

Driver setup uses sudo and installs the repository's pinned XDMA driver.
Rescan is performed after the qualified SRAM image is loaded. Select the actual
XDMA device if it is not xdma0. This host bundle never programs SRAM or flash.
Read results-lfm2/manifest.json. Only
PASS_PHYSICAL_CH1_RECOVERY_MATMUL_AND_LFM2 means warm memory, physical matmul
and eight actual LFM2 tokens passed. The required answer is
"The capital of France is Paris.", with tokens matching the ISA simulator.
An identity-only preflight is not an inference pass.
''')
    receipt = dict(status='MATCHED_CH1_LFM2_HOST_BUNDLE_PREPARED_IMAGE_PENDING',
        created_utc=datetime.now(timezone.utc).isoformat(), physical_model_verified=False,
        hardware_accessed=False, flash_written=False, image_included=False,
        repository_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_root=str(ROOT), generated_core=str(core), logical_capacity_bytes=1 << 31,
        physical_memory_channels=[1], model_checkpoint_sha256=expected,
        expected_text='The capital of France is Paris.', expected_token_ids=[1098,5706,803,4481,856,5242,523,7])
    files = [p for p in sorted(out.rglob('*')) if p.is_file()]
    receipt['files'] = [dict(name=str(p.relative_to(out)), bytes=p.stat().st_size,
                             sha256=digest(p)) for p in files]
    (out/'bundle-manifest.json').write_text(json.dumps(receipt,indent=2)+'\n')
    files.append(out/'bundle-manifest.json')
    (out/'SHA256SUMS').write_text(''.join(digest(p)+'  '+str(p.relative_to(out))+'\n' for p in files))
    with tarfile.open(archive, 'w') as tar:
        tar.add(out, arcname=out.name, recursive=True)
    archive_receipt = dict(path=str(archive),bytes=archive.stat().st_size,sha256=digest(archive),
                           status=receipt['status'],physical_model_verified=False,image_included=False)
    archive.with_suffix('.tar.json').write_text(json.dumps(archive_receipt,indent=2)+'\n')
    print(json.dumps(archive_receipt,indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
