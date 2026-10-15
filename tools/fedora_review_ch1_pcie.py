#!/usr/bin/env python3
"""Bind the existing CH1 PCIe image to its reviewed CDC and physical compute proof.

Normal operation and configuration boot are reviewed. The LiteX global SoC
reset CSR has an unqualified narrow pulse crossing and is excluded: supported
host software never writes it. Cold power-up and PCIe reset do not use it.
No image, timing exception, source netlist or hardware state is modified.
"""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from fedora_program_ch1_sram import describe, require, check_receipts
from opentpu.host import bpi_image

BASE = ROOT / 'build/fedora-vivado'
Q = BASE / 'ch1-image-qualification-20261014T113000Z/manifest.json'
MODEL = BASE / 'ch1-lfm2-physical-pass-current.json'
PARTIAL = BASE / 'ch1-pcie-cdc-reset-review-20261014T132900Z.json'
CLOCK = BASE / 'ch1-pcie-oob-clock-model-pass-20261014T131900Z.json'
BUILD = BASE / 'pcie-ch1-recovery-overlap-20261014T085912Z'
JTAG = BASE / 'ch1-jtag-resume-20261014T105300Z'


def main():
    out = BASE / ('ch1-pcie-final-review-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir()
    q = json.loads(Q.read_text())
    require(describe(q['bitstream']['path']) == q['bitstream'], 'Qualified bitstream changed')
    require(describe(q['build_manifest']['path']) == q['build_manifest'], 'Build manifest changed')
    m = json.loads((BUILD / 'manifest.json').read_text())
    j = json.loads((JTAG / 'manifest.json').read_text())
    for item in m['sources'] + list(m['outputs'].values()) + j['source_files']:
        require(describe(item['path']) == item, 'Frozen source/output changed: ' + item['path'])
    common = []
    for name in ('otpu_litedram.v', 'otpu_board.sv', 'otpu_native_sys.sv',
                 'otpu_native_dram.sv', 'otpu_mem_ch.sv', 'otpu_ctrl.sv'):
        a = [x for x in m['sources'] if Path(x['path']).name == name]
        b = [x for x in j['source_files'] if Path(x['path']).name == name]
        require(len(a) == len(b) == 1 and a[0]['sha256'] == b[0]['sha256'],
                'PCIe memory/compute source differs from physical inference image: ' + name)
        common.append(dict(name=name, sha256=a[0]['sha256'], pcie=a[0], jtag=b[0]))
    physical = json.loads(MODEL.read_text())
    require(physical['status'] == 'PASS_AUDITED_PHYSICAL_CH1_JTAG_MATMUL_AND_LFM2',
            'Audited physical LFM2 proof absent')
    partial = json.loads(PARTIAL.read_text())
    require(partial['reviewed'] == dict(calibration_status=2, bufgctrl_select=2,
                                       vendor_reset_synchronizers=3), 'Prior critical review differs')
    pending = partial['remaining']
    require(len(pending) == 1 and pending[0]['kind'] == 'CDC-10' and
            pending[0]['depth'] == 8 and set(pending[0]['targets']) ==
            {'u_ld/FDCE/D', 'u_ld/FDCE_8/D'}, 'Unexpected unreviewed crossing')
    clk = json.loads(CLOCK.read_text())
    require(clk['status'] == 'CH1_PCIE_OOB_CLOCK_MODEL_TIMING_ROUTE_SKEW_PASS_CDC_REVIEW_PENDING',
            'Reviewed OOB clock model absent')
    report = BASE / 'ch1-pcie-oob-timing-model-20261014T131100Z'
    skew = re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',
                      (report / 'bus-skew.rpt').read_text(), re.M)
    require(len(skew) == 39 and all(k == 'MET' and float(v) >= 0 for k,v in skew),
            'PCIe bus-skew review does not cover all 39 constraints')
    ld = (BUILD / 'source/boards/ypcb-00338/litedram/otpu_litedram.v').read_text()
    top = (BUILD / 'source/rtl/boards/ypcb-00338/otpu_fpga_top_ld.sv').read_text()
    require('.clk50g(clk50), .rst(1\'b0)' in top, 'External LiteDRAM reset is not tied off')
    require("reg     [1:0] reset_storage = 2'd0;" in ld and
            "    if (reset_wr_stb) begin\n        soc_rst = reset_storage[0];" in ld,
            'Reviewed global reset source differs')
    for c, d in [('FDCE','crg_mmcm_reset'), ('FDCE_8','crg_pll_reset')]:
        match = re.search(r'FDCE ' + c + r'\((.*?)\n\);', ld, re.S)
        require(match and '.C   (crg_s7' in match[1] and '.D   (' + d + ')' in match[1] and
                ".CLR (1'd0)" in match[1], 'Clock reset pipeline source differs')
    # The narrow management reset is not used by the qualified host flow.
    host_files = []
    reset_write = re.compile(r"\.w\(\s*['\"]reset['\"]\s*,")
    for p in sorted((ROOT / 'opentpu/host').glob('*.py')):
        require(not reset_write.search(p.read_text()), 'Host uses excluded global SoC reset: ' + str(p))
        host_files.append(describe(p))
    bit = Path(q['bitstream']['path'])
    mcs = BUILD / 'project/otpu.mcs'
    _, body = bpi_image.read_bit(bit.read_bytes())
    encoded = bpi_image.flash_order(body)
    flash = bpi_image.read_mcs(mcs.read_text())
    require(flash[:len(encoded)] == encoded and set(flash[len(encoded):]) <= {255},
            'BPI MCS does not match the qualified PCIe bitstream byte for byte')
    r = dict(status='CH1_PCIE_IMAGE_CDC_BUS_SKEW_REVIEW_PASS',
             qualification=describe(Q), clock_review=describe(CLOCK),
             partial_review=describe(PARTIAL), physical_compute_proof=describe(MODEL),
             common_compute_memory_sources=common, mcs=describe(mcs),
             bus_skew_constraints=39,
             reviewed_reset_scope='Configuration startup and normal PCIe/model operation. External LD reset tied low; default global reset CSR is zero and never written by supported host tools. Eight-stage management reset crossings do not carry normal data or PCIe reset.',
             operating_limitations=['Do not write the LiteX global SoC reset CSR. Its pulse capture/reset duration is unqualified. Use configuration reload or cold power cycle instead.'],
             qualified_host_files=host_files, hardware_accessed=False,
             pci_endpoint_physically_tested=False, flash_written=False,
             observed_utc=datetime.now(timezone.utc).isoformat())
    receipt = out / 'review.json'
    receipt.write_text(json.dumps(r, indent=2) + '\n')
    check_receipts(Q, receipt)
    (BASE / 'ch1-pcie-program-review-current.json').write_text(
        json.dumps(dict(out=str(out), review=str(receipt), qualification=str(Q),
                        bitstream=str(bit), mcs=str(mcs)), indent=2) + '\n')
    print(json.dumps(dict(status=r['status'], review=str(receipt), bitstream=str(bit),
                         mcs=str(mcs), physical_pcie_tested=False)))


if __name__ == '__main__':
    main()
