#!/usr/bin/env python3
"""Package a reviewed trace, DDR667 or spare-lane diagnostic without publishing."""
import argparse
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil

from fedora_prepare_litedram import ROOT, sha


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('build','generation','base-review','phase-review','extension-review','out'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args();build=a.build.resolve();gen=a.generation.resolve();out=a.out.resolve()
    stage=out.with_name(out.name+'.preparing');assert not out.exists() and not stage.exists()
    m=json.loads((build/'manifest.json').read_text());ext=json.loads(a.extension_review.read_text())
    base=json.loads(a.base_review.read_text());phase=json.loads(a.phase_review.read_text())
    assert m['status']=='RAM_ONLY_LITEDRAM_BITSTREAM_BUILT_CDC_AND_PHYSICAL_REVIEW_PENDING'
    assert phase['status']=='PASS_FULL_FINE_PHASE_INTERNAL_TIMING'
    trace=m['build_id']=='c0172040'
    variant='trace' if trace else {'c0172050':'ddr667','c0172060':'spare8'}[m['build_id']]
    assert ext['status']==('OFFLINE_TRC1_EXTENSION_REVIEW_PASS_PHYSICAL_PENDING' if trace else
                           'OFFLINE_RAM_VARIANT_EXTENSION_REVIEW_PASS_PHYSICAL_PENDING')
    for receipt in (ext,base,phase):
        assert receipt['build_manifest_sha256']==sha(build/'manifest.json')
        assert receipt['bitstream_sha256']==m['bitstream_sha256']==sha(build/'ramtest.bit')
    assert ext['base_review_sha256']==sha(a.base_review) and ext['phase_review_sha256']==sha(a.phase_review)
    assert ext['generation_manifest_sha256']==sha(gen/'manifest.json')
    for name,digest in m['frozen_files'].items():assert sha(build/name)==digest,name
    generation=json.loads((gen/'manifest.json').read_text())
    for name,digest in generation['frozen_sources'].items():assert sha(gen/'source'/name)==digest,name
    stage.mkdir(parents=True)
    for name in ['manifest.json','ramtest.bit','crc.log',*m['frozen_files']]:
        target=stage/name;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(build/name,target)
    evidence=stage/'evidence';evidence.mkdir()
    for source,name in [(a.base_review,'base-review.json'),(a.phase_review,'phase-review.json'),
                        (a.extension_review,'extension-review.json'),(gen/'manifest.json','generation.json'),
                        (Path(__file__),'packager.py')]:shutil.copy2(source,evidence/name)
    shutil.copytree(gen/'source',evidence/'generation-source',ignore=shutil.ignore_patterns('__pycache__'))
    for label,folder in [('base-audit',a.base_review.parent),('phase-audit',a.phase_review.parent),
                         ('extension-audit',a.extension_review.parent)]:
        dest=evidence/label;dest.mkdir()
        for source in folder.iterdir():
            if source.is_file() and source.suffix in ('.rpt','.tsv','.log','.tcl'):
                if source.suffix in ('.rpt','.log'):
                    (dest/(source.name+'.gz')).write_bytes(gzip.compress(source.read_bytes(),mtime=0))
                else:shutil.copy2(source,dest/source.name)
    if trace:
        assert sha(gen/'trace-format.json')==ext['trace_format_sha256']
        shutil.copy2(gen/'trace-format.json',stage/'trace-format.json')
        model=ROOT/'build/checks/lane6-phy-trace-v2-20261017/manifest.json'
        assert sha(model)==ext['model_sha256'];shutil.copy2(model,evidence/'trace-model.json')
    elif variant=='spare8':
        model=ROOT/'build/checks/spare-native-rmw-20261017/manifest.json'
        assert sha(model)==ext['native_adapter_model_sha256'];shutil.copy2(model,evidence/'native-rmw-model.json')
    config=dict(trace=('DDR800 command/PHY trace',100,800,[0,1]),
                ddr667=('DDR667 diagnostic',250/3,2000/3,[0,1]),
                spare8=('DDR800 CH0 lane-8 replacement',100,800,[1]))[variant]
    bundle=dict(status='EXPERIMENTAL_RAM_DIAGNOSTIC_OFFLINE_REVIEW_PASS_PHYSICAL_PENDING',
                variant=variant,build_id=m['build_id'],controller_mhz=config[1],ddr_mts=config[2],
                capacity_bytes_per_channel=2**31,ecc_channels=config[3],bitstream_sha256=m['bitstream_sha256'],
                packaged_utc=datetime.now(timezone.utc).isoformat(),physical_qualification=False,
                base_review='evidence/base-review.json',phase_review='evidence/phase-review.json',
                extension_review='evidence/extension-review.json',flash_written=False,published=False)
    (stage/'bundle.json').write_text(json.dumps(bundle,indent=2)+'\n')
    readme=f'''# {config[0]}

Build ID `{m['build_id']}`. LDRT ABI 3; two 2 GiB channels.
Controller clock: {config[1]:.6f} MHz. DDR data rate: {config[2]:.6f} MT/s.
ECC channels: {config[3]}. This RAM diagnostic has no PCIe endpoint or compute core.

The bitstream, CRC, internal timing over the full calibration fine-phase range,
board pins, CDC and variant-specific review passed. Physical qualification and
external DDR pad timing remain pending. This package does not establish a CH0 repair.

## Load

Run `shasum -a 256 -c SHA256SUMS` inside this directory. Load `ramtest.bit`
into volatile SRAM with the working JTAG loader, then start its XVC server on
port 3721. Loading on macOS does not require Vivado. These instructions do not
write flash. Native traffic starts held reset and paused.

Keep this image's `core/csr.csv` and calibration data together. Raw BIST writes
overwrite memory outside the native ECC path; fully initialize normal ECC
memory before native workloads. Do not use a reader for a different build ID.

## Build and evidence

See [the experiment build guide](../../docs/ddr_lane6_experiment_builds.md).
Linux Vivado and the pinned LiteX/Migen and RV32I toolchains are required for
building. `manifest.json` and its frozen inputs retain the exact implementation
record; `bundle.json` describes this delivery. Archived generator sources are
provenance, while the build guide supplies the current rebuild commands.
Routed checkpoints remain in the build workspace, identified by SHA-256 in
the review receipts; they are not needed to load this package.
'''
    if trace:
        readme+='''
## Bounded command/PHY experiment

From the repository root, after SRAM loading and starting XVC:

```bash
python3 tools/probe_ramtest_phy_history.py \\
  --build bitstreams/ramtest-litedram-ddr800-phy-trace \\
  --review bitstreams/ramtest-litedram-ddr800-phy-trace/evidence/extension-review.json \\
  --format bitstreams/ramtest-litedram-ddr800-phy-trace/trace-format.json \\
  --out build/results/phy-history-1
```

This waits for startup calibration, then performs 14 full raw-word writes and
720 serialized reads. Every read has its 576-bit payload recorded; selected
writes and clean/bad victim reads also preserve 256 cycles of native, DFI and
lane-6 alignment data. Capture storage is FPGA block RAM. It does not restart
calibration or release native traffic. Reloading changes calibration and
placement; reproduce the original error before assigning its cause.
'''
    elif variant=='spare8':
        readme+='''
## Spare-lane limits

CH0 logical lanes map to physical `[0,1,2,3,4,5,8,7]`; physical lane 6 is held
high impedance. CH0 has no ECC. CH1 retains its nine-lane ECC interface.
Only CH1 calibrates automatically. CH0 requires the matched eight-lane
`core/sdram_init_ch0.py`; nine-lane calibration/readers are incompatible.
Its two native ports use serialized full-word read/merge/write for partial
writes. Keep raw BIST idle while native clients run. Host procedures and full
physical qualification are still pending; no capacity recovery is claimed.
'''
    else:
        readme+='''
## Lower-rate comparison

Both channels retain 72 physical bits and ECC. Configuration-time calibration
runs on both channels. CL6/CWL5 and the matched DDR667 profile must stay with
this image. A reader must accept build ID `c0172050`, rate field `667` and
controller-frequency field `83333`; the actual data rate is 666.666667 MT/s.
Do not reuse a DDR800-only reader by bypassing its identity checks.
'''
    (stage/'README.md').write_text(readme)
    files=sorted(f for f in stage.rglob('*') if f.is_file())
    (stage/'SHA256SUMS').write_text(''.join(f'{sha(f)}  {f.relative_to(stage)}\n' for f in files))
    for line in (stage/'SHA256SUMS').read_text().splitlines():
        digest,name=line.split(None,1);assert sha(stage/name)==digest,name
    stage.rename(out)
    print(json.dumps(dict(package=str(out),files=len(files),build_id=m['build_id'],bitstream_sha256=m['bitstream_sha256'])))


if __name__=='__main__':main()
