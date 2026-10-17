#!/usr/bin/env python3
"""Export small runtime files from the reviewed c0172300 image. No hardware access.

The original image and programming receipt stay local. Review and pin the
resulting runtime.json digest in spare_c0172300.py before publishing the files.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from opentpu.host.dual_pcie import digest,require
from opentpu.host.spare_c0172300 import SparePcieProfile,REVIEWED_MANIFEST_SHA256

SMALL_FILES=(
    'core/csr.csv','core/sdram_init.py','core/sdram_init_ch0.py','core/otpu_litedram_mem.init',
    'calibration/selfcal.bin','calibration/pipeline-binding.json','calibration/bundle.json',
    'calibration/host-model-review.json',
)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--flash-receipt',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    profile=SparePcieProfile(args.package)
    require(not profile.runtime_only and profile.manifest_sha256==REVIEWED_MANIFEST_SHA256,
            'Export requires the original, fully checked c0172300 package')
    receipt=json.loads(args.flash_receipt.read_text())
    require(receipt['status']=='PASS_SPARE_PCIE_PERMANENT_FLASH_VERIFY_JTAG_BOOT_MAC_RUNTIME_PENDING' and
            receipt['bitstream']['sha256']==profile.bitstream_sha256 and
            receipt['package_manifest_sha256']==profile.manifest_sha256 and
            all(receipt[key] is True for key in ('flash_written','flash_verified','jtag_boot_from_flash_verified')),
            'Successful matching permanent programming receipt required')
    core=json.loads((profile.core/'variant-profile.json').read_text())
    review={}
    for name in ('offline-image-review','cdc-review','csr-gray-review','adapter-model'):
        path=profile.package/'evidence'/f'{name}.json'
        data=json.loads(path.read_text())
        review[name]=dict(source_sha256=digest(path),status=data['status'])
        if 'bitstream' in data:
            require(data['bitstream']['sha256']==profile.bitstream_sha256,'Review image differs')
            review[name]['bitstream_sha256']=data['bitstream']['sha256']
        if name=='adapter-model':
            require(data['status']=='PASS_SPARE_PIPELINED_NATIVE_TWO_PORT_READS_AND_EXCLUSIVE_RMW' and
                    len(data['reports'])==8,'Adapter model review incomplete')
            review[name]['report_count']=len(data['reports'])
    runtime=dict(kind='C0172300_ALREADY_FLASHED_RUNTIME_FILES',build_id='c0172300',
        bitstream_sha256=profile.bitstream_sha256,
        original_image_manifest_sha256=profile.manifest_sha256,
        configuration={key:core[key] for key in ('variant','parameters','physical_databits','ecc_channels',
            'ch0_physical_lanes','automatic_calibration_channels','host_calibration_channels',
            'native_read_depth_per_port','native_raw_ports_used','masked_writes_globally_exclusive')},
        reviews=review,
        programming=dict(source_receipt_sha256=digest(args.flash_receipt),
            **{key:receipt[key] for key in ('status','finished_utc','flash_written','flash_verified',
                'jtag_boot_from_flash_verified','cold_boot_verified','physical_pcie_verified')}),
        limitations=[
            'No bitstream, checkpoint or generated netlist is distributed here.',
            'Runtime validation checks these small files and live register identity; it does not rehash flash or omitted build outputs.',
            'The original manifest describes offline review before programming; the programming summary is a later observation.',
            'External DDR pad timing, cold power-cycle and Mac inference/bandwidth qualification remain separate.',
        ],files=[])
    args.out.mkdir(parents=True,exist_ok=False)
    for name in SMALL_FILES+('reviewed-image.json',):
        source=(profile.package/'manifest.json' if name=='reviewed-image.json' else profile.package/name)
        data=source.read_bytes()
        require(len(data)<128*1024,'Unexpectedly large runtime file')
        require(b'/home/' not in data and b'/Users/' not in data,'Private path in public runtime file')
        target=args.out/name;target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(source,target)
        runtime['files'].append(dict(name=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    manifest=args.out/'runtime.json'
    manifest.write_text(json.dumps(runtime,indent=2)+'\n')
    print('Review and pin runtime manifest SHA256:',digest(manifest))


if __name__=='__main__':main()
