#!/usr/bin/env python3
"""Build full-compute Vivado PCIe CH1 recovery after core/ECC gates complete.

Does not program the card or flash. Uses a separate source snapshot and cache.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from fedora_prepare_litedram import profile


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--generation',required=True,type=Path)
    ap.add_argument('--ecc-preparation',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--wait-seconds',type=int,default=3600)
    ap.add_argument('--overlap-ecc-build',action='store_true',
                    help='Permit offline synthesis while the exact ECC test remains live; hardware gate still required')
    ap.add_argument('--ecc-unit',help='Exact live systemd unit when overlapping ECC verification')
    args=ap.parse_args()
    generation=args.generation.resolve();ecc=args.ecc_preparation.resolve();out=args.out.resolve()
    if out.exists():ap.error('Choose a fresh build directory')
    wait=out.with_name(out.name+'-dependency-wait.json')
    deadline=time.monotonic()+args.wait_seconds
    while True:
        m=json.loads((generation/'manifest.json').read_text())
        if m['status']=='FAIL':raise RuntimeError('CH1 core generation failed: '+str(m.get('error')))
        gf=generation/'generate.exit';ef=ecc/'four-port-ecc.exit'
        for p in [gf,ef]:
            if p.exists() and p.read_text().strip()!='0':raise RuntimeError('Dependency failed: '+str(p))
        ecc_complete=ef.exists()
        ecc_live=False
        if args.overlap_ecc_build and not ecc_complete:
            if not args.ecc_unit:raise ValueError('--ecc-unit required for overlap')
            props=subprocess.check_output(['systemctl','--user','show',args.ecc_unit,
                                          '-p','ActiveState','-p','MainPID'],text=True)
            props=dict(line.split('=',1) for line in props.splitlines())
            e=json.loads((ecc/'manifest.json').read_text())
            cmd=Path('/proc')/str(e.get('child_pid',0))/'cmdline'
            ecc_live=props['ActiveState']=='active' and props['MainPID']!='0' and cmd.exists() and \
                     str(ecc/'generator/ecc_ports_check.py').encode() in cmd.read_bytes()
        ready=m['status']=='CH1_RECOVERY_CORE_GENERATED_ABI_PASS_FOUR_PORT_ECC_GATE_PENDING' and gf.exists() and (ecc_complete or ecc_live)
        wait.write_text(json.dumps(dict(status='READY' if ready else 'WAITING_FOR_CORE_AND_FOUR_PORT_ECC',
                        observed_utc=datetime.now(timezone.utc).isoformat(),generation=str(generation),
                        ecc_preparation=str(ecc),hardware_accessed=False,flash_written=False),indent=2)+'\n')
        if ready:break
        if time.monotonic()>deadline:raise TimeoutError('Dependencies did not complete')
        time.sleep(5)
    core=Path(m['core'])
    p=json.loads((core/'openxc7-profile.json').read_text())
    assert p['physical_user_channels']==[1] and p['usable_logical_bytes']==1<<31
    assert p['virtual_channel_bytes']==1<<30 and p['calibration_mask']==2
    assert p['user_address_mapping']=='physical CH1 beat = (virtual beat << 1) | virtual channel'
    checked=profile(core)
    assert checked['parameters']==dict(CORE_KHZ=100000,DDR_MTS=800)
    # The ECC test and module used by the generated core must be exactly those tested.
    for name in ['ecc_ports.py','ecc_ports_check.py']:
        expected=hashlib.sha256((ecc/'generator'/name).read_bytes()).hexdigest()
        item=next(x for x in m['source_witness'] if Path(x['path']).name==name)
        assert item['sha256']==expected and hashlib.sha256(Path(item['path']).read_bytes()).hexdigest()==expected
    if ecc_complete:
        assert (ecc/'four-port-ecc.log').read_text().splitlines()[-1]=='PASS'
    template=ROOT/'tools/fedora_build_vivado_pcie_ddr800.py'
    text=template.read_text()
    old='ROOT = Path(__file__).resolve().parents[1]'
    assert text.count(old)==1
    text=text.replace(old,'ROOT = Path('+repr(str(ROOT))+')')
    old='from fedora_vivado_ddr800_qualify import CORE, PROFILE, describe'
    assert text.count(old)==1
    text=text.replace(old,'from fedora_vivado_ddr800_qualify import PROFILE, describe\nCORE=Path('+repr(str(core))+')')
    marker='    create = board/\'vivado/create_project.tcl\''
    assert text.count(marker)==1
    adaptation='''    ctrl = src/'rtl/boards/ypcb-00338/otpu_ctrl.sv'
    ctl = ctrl.read_text()
    marker = "      10'h016: r_d <= 32'(ACT_ROWS);"
    if ctl.count(marker) != 1:
        raise ValueError('Unexpected control-register capacity marker')
    ctrl.write_text(ctl.replace(marker, marker+"\\n      10'h017: r_d <= 32'h08000102; // CH1 recovery, ABI1, 2048 MiB"))
'''
    text=text.replace(marker,adaptation+marker)
    text=text.replace("record = dict(status='PREPARED',", "record = dict(physical_user_channels=[1], usable_logical_bytes=1<<31, virtual_channel_bytes=1<<30, memory_profile_register='0x5c: 0x08000102', user_address_mapping='physical CH1 beat = (virtual beat << 1) | virtual channel', calibration_mask=2, status='PREPARED',")
    text=text.replace("record = dict(physical_user_channels=", "record = dict(ecc_gate_exit_file="+repr(str(ef))+", ecc_gate_complete_before_build="+repr(ecc_complete)+", physical_user_channels=")
    text=text.replace('FULL_NATIVE_VIVADO_PCIE_DDR800_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING',
                      'FULL_NATIVE_VIVADO_PCIE_CH1_RECOVERY_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING')
    driver=out.with_suffix('.py');driver.write_text(text)
    command=[sys.executable,str(driver),'--out',str(out)]
    out.with_suffix('.command.json').write_text(json.dumps(command,indent=2)+'\n')
    return subprocess.run(command,cwd=ROOT).returncode


if __name__=='__main__':raise SystemExit(main())
