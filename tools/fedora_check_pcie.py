#!/usr/bin/env python3
"""Save strict host/TLP/mailbox protocol gates without touching physical PCIe."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True,type=Path)
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists():
        raise RuntimeError('Use a fresh output directory to retain previous gate results')
    out.mkdir(parents=True)
    board = ROOT/'rtl/boards/ypcb-00338'
    benches = ROOT/'boards/ypcb-00338/sim'
    endpoint = ROOT/'build/fedora-openxc7/deps/pcie_7x/src'
    inputs = [Path(__file__),board/'otpu_pcie_mailbox.sv',board/'otpu_jtag_axi.sv',
              benches/'tb_openxc7_pcie.sv',benches/'tb_openxc7_pcie_mailbox.sv',
              endpoint/'axis_pcie_to_al_us.v',endpoint/'axil_to_al.v',
              ROOT/'opentpu/host/pcie_pio.py',ROOT/'opentpu/host/jtag.py',
              ROOT/'tests/test_pcie_pio.py',ROOT/'tests/test_jtag_transport.py',
              ROOT/'tools/pcie_mmio.c',ROOT/'build/fedora-pcie-mmio/manifest.json',
              ROOT/'build/fedora-pcie-mmio/libotpu_mmio.so']
    report = dict(status='RUNNING',started_utc=datetime.now(timezone.utc).isoformat(),
                  sources={str(p):digest(p) for p in inputs},commands=[],
                  hardware='NOT_RUN',full_image='NOT_BUILT',timing='NOT_QUALIFIED',
                  scope='Host and actual TLP/AXI/mailbox protocol; modeled AXI responses, no physical DDR/GTX')
    path = out/'manifest.json'
    def save():
        path.write_text(json.dumps(report,indent=2)+'\n')
    def execute(name,command):
        entry = dict(name=name,argv=[str(x) for x in command])
        report['commands'].append(entry)
        save()
        with (out/(name+'.log')).open('w') as log:
            entry['exit_code'] = subprocess.run(entry['argv'],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT).returncode
        save()
        if entry['exit_code']:
            raise RuntimeError(name+' failed; see '+str(out/(name+'.log')))
    save()
    try:
        execute('host',[ROOT/'build/fedora-venv/bin/python','-m','pytest','-q',
                        'tests/test_pcie_pio.py','tests/test_jtag_transport.py',
                        '--junitxml='+str(out/'host.xml')])
        cases = list(ET.parse(out/'host.xml').getroot().iter('testcase'))
        if not cases or any(t.find('failure') is not None or t.find('error') is not None or t.find('skipped') is not None for t in cases):
            raise RuntimeError('Host report is missing cases or contains a failure/error/skip')
        report['host_passed'] = len(cases)
        for name in ('tb_openxc7_pcie_mailbox','tb_openxc7_pcie'):
            rtl = [board/'otpu_pcie_mailbox.sv']
            if name == 'tb_openxc7_pcie':
                rtl += [board/'otpu_jtag_axi.sv',endpoint/'axis_pcie_to_al_us.v',endpoint/'axil_to_al.v']
            target = out/(name+'.vvp')
            execute(name+'-compile',['iverilog','-g2012','-s',name,'-o',target,benches/(name+'.sv'),*rtl])
            execute(name,['vvp',target])
            if 'PASS:' not in (out/(name+'.log')).read_text():
                raise RuntimeError(name+' lacks its completion marker')
        changed = [str(p) for p in inputs if digest(p) != report['sources'][str(p)]]
        report['changed_inputs'] = changed
        if changed:
            raise RuntimeError('Protocol inputs changed during validation')
        report['status'] = 'HOST_24_AND_BOTH_RTL_PROTOCOL_GATES_PASS_FULL_IMAGE_PENDING'
        report['artifacts'] = {str(p):digest(p) for p in out.iterdir() if p != path}
    except BaseException as e:
        report.update(status='FAIL',error=str(e))
        raise
    finally:
        report['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print(report['status'])
    print(path)


if __name__ == '__main__':
    main()
