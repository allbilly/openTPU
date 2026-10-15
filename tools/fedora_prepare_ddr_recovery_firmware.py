#!/usr/bin/env python3
"""Build an isolated DDR recovery experiment for the existing calibration CPU.

The production source and bitstream stay intact. Scan each phase with the
existing 64 MiB test and a fixed second PRBS seed; after final training require
full 2 GiB PRBS and address tests before asserting cal_ready.
"""
import argparse
import hashlib
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'build/fedora-vivado/ch1-core-writable-20261014T082631Z/core'
FW_ID = 0xD0150001


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--traffic-scan', action='store_true',
                    help='Diagnostic only: sweep lane 6 write/read bitslip and read taps at CK phase 45')
    args = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = ROOT / ('build/fedora-openxc7/ddr-recovery-firmware-' + stamp)
    src = out / 'source'
    src.mkdir(parents=True)
    original = ROOT / 'tools/litedram/selfcal_fw'
    for path in original.iterdir():
        if path.is_file():
            shutil.copy2(path, src / path.name)
    path = src / 'cal.c'
    code = path.read_text()
    scan_anchor = '''            for (int m = 0; m < NM; m++)
                if (lanes >> m & 1)
                    table[j][m] = 0;
'''
    scan_extra = '''            uint32_t extra;
            if ((e = bist(beats, 0, 0x9e3779b97f4a7c15ull, &extra)))
                return e;
            if ((e = bist(beats, 1, 0x9e3779b97f4a7c15ull, &extra)))
                return e;
            lanes |= extra;
'''
    assert code.count(scan_anchor) == 1
    code = code.replace(scan_anchor, scan_extra + scan_anchor)
    final_anchor = '''    ctl(CTL_SEL);                              /* hardware() */
    if (R->has_ready)
        wr(R->cal_ready, 1);
'''
    final_extra = '''    ctl(CTL_SEL);                              /* hardware() */
    if (R->has_bist) {
        uint32_t lanes;
        for (int mode = 0; mode < 4; mode++) {
            if ((e = bist(1u << 25, mode, 0x9e3779b97f4a7c15ull, &lanes)))
                return e;
            if ((mode & 1) && lanes)
                return E_FINAL;
        }
    }
    if (R->has_ready)
        wr(R->cal_ready, 1);
'''
    assert code.count(final_anchor) == 1
    code = code.replace(final_anchor, final_extra)
    fw_id = FW_ID
    if args.traffic_scan:
        fw_id += 1
        anchor = 'static int cal_channel(int ch, int stride)\n{\n'
        diagnostic = '''/* Diagnostic only: no cal_ready is asserted. Mailbox 144 onward is raw data. */
static int traffic_diagnostic(void)
{
    R = &CH[0];
    per_bit = R->per_bit;
    wr(R->cal_ready, 0);
    int e;
    if ((e = wclk_check()) || (e = set_group1_0()) || (e = dqs_move(45)))
        return e;
    int8_t wl[NM];
    struct lane_rl rl[NM];
    uint32_t bad;
    calibrate(N_SEEDS, wl, rl, &bad);
    hw_mbox(144, 0xd16a0001u);
    hw_mbox(150, bad);
    uint32_t best = 0xffffffffu, bestw = 0, bestr = 0, bestt = 0, count = 0;
    for (int w = 0; w < 8; w += 2) {
        set_wbitslip(6, w);
        ctl(CTL_SEL);
        if ((e = bist(2048, 0, 0x9e3779b97f4a7c15ull, &bad)))
            return e;
        for (int b = 0; b < 8; b++) {
            uint32_t mask = 0;
            set_rbitslip(6, b);
            for (int t = 0; t < 32; t++) {
                set_rdelay(6, t);
                if ((e = bist(2048, 1, 0x9e3779b97f4a7c15ull, &bad)))
                    return e;
                uint32_t wrong = rdw(R->bist_lane_errors[6]);
                if (!wrong)
                    mask |= 1u << t;
                if (wrong < best) {
                    best = wrong;
                    bestw = w;
                    bestr = b;
                    bestt = t;
                }
                hw_mbox(149, ++count);
            }
            hw_mbox(160 + (w / 2) * 8 + b, mask);
        }
    }
    hw_mbox(145, bestw);
    hw_mbox(146, bestr);
    hw_mbox(147, bestt);
    hw_mbox(148, best);
    set_wbitslip(6, bestw);
    set_rbitslip(6, bestr);
    set_rdelay(6, bestt);
    return E_FINAL; /* A diagnostic result never declares the channel ready. */
}

'''
        assert code.count(anchor) == 1
        code = code.replace(anchor, diagnostic + anchor + '    if (ch == 0)\n        return traffic_diagnostic();\n')
    path.write_text(code)
    spec = importlib.util.spec_from_file_location('ddr_experimental_fw', original / 'fw.py')
    fw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fw)
    fw.HERE = src
    compiler = ROOT / 'build/fedora-openxc7/litedram-environment/toolchain/riscv64-elf-gcc'
    data = fw.target(CORE, out / 'firmware', fw_id=fw_id, cc=str(compiler))
    header = (out / 'firmware/selfcal_cfg.h').read_bytes()
    assert header == (CORE / 'selfcal_fw/selfcal_cfg.h').read_bytes()
    manifest = dict(status='EXPERIMENTAL_FIRMWARE_BUILT_HARDWARE_NOT_RUN', fw_id=fw_id,
                    traffic_diagnostic=args.traffic_scan,
                    firmware=str(out / 'firmware/selfcal.bin'), bytes=len(data),
                    sha256=hashlib.sha256(data).hexdigest(), core=str(CORE),
                    header_sha256=hashlib.sha256(header).hexdigest(),
                    scan_mib=64, extra_scan_seed='0x9e3779b97f4a7c15',
                    final_mib=2048, final_modes=[0, 1, 2, 3],
                    production_source_changed=False, bitstream_changed=False,
                    flash_written=False,
                    source_hashes={p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in src.iterdir() if p.is_file()})
    (out / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (ROOT / 'build/fedora-vivado/ddr-recovery-firmware-current.json').write_text(
        json.dumps(dict(out=str(out), **manifest), indent=2) + '\n')
    print(json.dumps(manifest), flush=True)


if __name__ == '__main__':
    main()
