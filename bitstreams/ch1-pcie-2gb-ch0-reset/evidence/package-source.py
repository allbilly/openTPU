"""Finish offline review and package the already-built CH0 reset experiment."""
from collections import Counter
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path('/home/fedora/openTPU')
BUILD = ROOT / 'build/fedora-vivado/ch0-reset-pcie-20261016'
AUDIT = BUILD / 'independent-image-review'
OUT = ROOT / 'bitstreams/ch1-pcie-2gb-ch0-reset'
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from opentpu.host import bpi_image
from fedora_check_native_image import timing_summary, route_summary
from check_vivado_bitstream import parse_bitstream


def require(ok, message):
    if not ok:
        raise ValueError(message)


def describe(path):
    return dict(bytes=path.stat().st_size, sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def verify(item):
    require(describe(Path(item['path'])) == {k: item[k] for k in ('bytes', 'sha256')},
            'Recorded artifact changed: ' + item['path'])


m = json.loads((BUILD / 'manifest.json').read_text())
q = json.loads((AUDIT / 'manifest.json').read_text())
require(m['status'] == 'FULL_NATIVE_VIVADO_PCIE_CH1_RECOVERY_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING', 'Build incomplete')
require(q['status'] == 'CH1_PCIE_IMAGE_PACKET_CRC_PINS_ROUTE_TIMING_PASS_CDC_REVIEW_PENDING', 'Independent review incomplete')
require(m['build_id'] == 'c0160001' and m['profile']['CORE_KHZ'] == 100000
        and m['physical_user_channels'] == [1] and m['calibration_mask'] == 2, 'Unexpected profile')
verify(q['build_manifest'])
for item in m['sources'] + list(m['outputs'].values()) + q['oob_reports']:
    verify(item)
for item in q['ecc'].values():
    if isinstance(item, dict) and 'path' in item:
        verify(item)
original_checker = subprocess.check_output(['git', 'show', 'HEAD:tools/fedora_qualify_ch1_image.py'], cwd=ROOT)
require(hashlib.sha256(original_checker).hexdigest() == q['checker']['sha256'], 'Historical checker source unavailable')
for name, expected in m['source_hashes'].items():
    require(describe(BUILD / 'source' / name)['sha256'] == expected, 'Frozen source changed: ' + name)
for item in m['generator_sources']:
    require(describe(Path(item['path']))['sha256'] == item['sha256'], 'Frozen generator changed')

timing = timing_summary((AUDIT / 'oob-timing.rpt').read_text())
route = route_summary((AUDIT / 'oob-route.rpt').read_text())
require(timing == q['oob_clock_review']['timing'] and
        all(timing[k] >= 0 for k in ('WNS', 'WHS', 'WPWS')) and
        all(timing[k] == 0 for k in ('setup_failing', 'hold_failing', 'pulse_failing')), 'Timing failed')
require(route == q['route'] and route['routable'] == route['fully_routed'] > 0 and route['routing_errors'] == 0, 'Routing incomplete')
require(q['oob_clock_review']['bus_skew_constraints'] == 39 and
        q['oob_clock_review']['minimum_bus_skew_slack_ns'] >= 0 and
        q['pins_checked'] == 278, 'Pin/skew review incomplete')
require({row[1] for row in q['serializer_reset_registers']} == {'0', '1'}, 'PHY reset-stage witness missing')
clocks = (AUDIT / 'clocks.rpt').read_text()
for name in ('core_clk_otpu_bd_clk_wiz_0_0', 'crg_s7mmcm_clkout'):
    require(re.search(r'^' + re.escape(name) + r'\s+10\.000\s', clocks, re.M),
            'Expected 100 MHz clock is missing: ' + name)

entries = []
counts = Counter()
for line in (AUDIT / 'oob-cdc.rpt').read_text().splitlines():
    if not re.match(r'^\s*\d+\s+CDC-\d+\s+Critical\s', line):
        continue
    fields = re.split(r'\s{2,}', line.strip())
    require(len(fields) == 8, 'Unexpected CDC row')
    _, kind, _, _, depth, exception, source, target = fields
    reason = None
    if (kind == 'CDC-13' and depth == '0' and exception == 'False Path' and
            source.endswith('/pipe_clock_int.pipe_clock_i/pclk_sel_reg/C') and
            target == source.rsplit('/', 2)[0] + '/pclk_i1_bufgctrl.pclk_i1/S1'):
        reason = 'pcie_clock_select'
    elif (kind == 'CDC-11' and depth == '2' and exception == 'Max Delay Datapath Only' and
          source == 'u_ld/cal1_storage_reg/C' and target in
          {'u_sys/u_board/cal_s1_reg[0]/D', 'u_sys/u_board/cal_s1_reg[1]/D'}):
        reason = 'calibration_ready'
    elif (kind == 'CDC-11' and depth == '5' and exception == 'False Path' and
          source.endswith('/pcie2_ip_i/inst/inst/user_reset_out_reg/C') and
          re.fullmatch(r'u_bd/otpu_bd_i/sc_ctl/inst/sc_ul/inst/M_AXI\[[012]\]\.mi_cdc\.m_psr/U0/EXT_LPF/ACTIVE_LOW_AUX\.ACT_LO_AUX/syncstages_ff_reg\[0\]/D', target)):
        reason = 'vendor_reset'
    elif (kind == 'CDC-10' and depth == '8' and exception == 'False Path' and
          source == 'u_ld/reset_storage_reg[0]/C' and target in {'u_ld/FDCE/D', 'u_ld/FDCE_8/D'}):
        reason = 'unused_management_reset'
    require(reason is not None, 'New critical CDC finding: ' + line)
    counts[reason] += 1
    entries.append(dict(kind=kind, depth=int(depth), exception=exception, source=source, target=target, review=reason))
require(counts == Counter(pcie_clock_select=2, calibration_ready=2, vendor_reset=3, unused_management_reset=2), 'CDC inventory changed')

bit = BUILD / 'project/otpu.bit'
packet = parse_bitstream(bit.read_bytes())
require(describe(bit) == {k: q['bitstream'][k] for k in ('bytes', 'sha256')}, 'Reviewed bitstream changed')
require(q['crc']['status'] == 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH' and q['crc']['crc_checkpoints'] == 2, 'CRC review incomplete')
_, body = bpi_image.read_bit(bit.read_bytes())
expected = bpi_image.flash_order(body)
flash = bpi_image.read_mcs((BUILD / 'project/otpu.mcs').read_text())
require(flash[:len(expected)] == expected and set(flash[len(expected):]) <= {255}, 'MCS payload mismatch')
core = BUILD / 'source/boards/ypcb-00338/litedram'
p = json.loads((core / 'openxc7-profile.json').read_text())
require(p['physical_user_channels'] == [1] and p['calibration_mask'] == 2, 'Matched core missing')
for item in p['files'].values():
    require(describe(core / item['name']) == {k: item[k] for k in ('bytes', 'sha256')}, 'Core file changed')
review = dict(status='CH1_PCIE_RESET_CANDIDATE_CDC_AND_BUS_SKEW_REVIEW_PASS_PHYSICAL_PENDING',
              observed_utc=datetime.now(timezone.utc).isoformat(), bitstream=describe(bit),
              source_sha256=describe(Path(__file__))['sha256'], entries=entries,
              bus_skew_constraints=39, timing=timing, route=route,
              physical_hardware='NOT_RUN', ch0_repaired=False,
              reviewed_scope='Configuration startup and normal PCIe operation; critical crossings retain the baseline structures and fresh max-delay/bus-skew checks.',
              operating_limitations=['Do not write the unused LiteX global SoC reset CSR. Use a configuration reload or power cycle.'],
              interpretation='CH1-only user mapping remains. CH0 is available only through calibration/raw BIST; this is not a RAM-only or 4 GiB image.')
OUT.mkdir(exist_ok=False)
evidence = OUT / 'evidence'
evidence.mkdir()
shutil.copy2(bit, OUT / 'otpu.bit')
(OUT / 'core').mkdir()
for name in list(x['name'] for x in p['files'].values()) + ['openxc7-profile.json']:
    shutil.copy2(core / name, OUT / 'core' / name)
for source, name in [(BUILD / 'manifest.json', 'build-manifest.json'),
                     (AUDIT / 'manifest.json', 'offline-image-review.json'),
                     (AUDIT / 'packets.json', 'packets.json'), (AUDIT / 'crc.json', 'crc.json'),
                     (Path(__file__), 'package-source.py'),
                     (ROOT / 'build/ch0_reset_pcie_build.py', 'original-build-driver.py')]:
    shutil.copy2(source, evidence / name)
(evidence / 'qualifier-at-build.py').write_bytes(original_checker)
for report in sorted(AUDIT.glob('*.rpt')):
    (evidence / (report.name + '.gz')).write_bytes(gzip.compress(report.read_bytes(), mtime=0))
(evidence / 'cdc-review.json').write_text(json.dumps(review, indent=2) + '\n')
(evidence / 'packet-review.json').write_text(json.dumps(packet, indent=2) + '\n')
(OUT / 'README.md').write_text('''# Experimental CH0 serializer-reset comparison

BUILD_ID `c0160001`; full OpenTPU compute at 100 MHz, DDR3-800, Gen2 x8
PCIe and 2 GiB through physical CH1. The `f2d1023d` serializer-reset stage is
present on both PHYs. CH0 still has no normal host/compute user mapping.
Its retained calibration CPU and raw BIST permit CH0 PHY comparisons.
This is a full-system comparison image. The RAM-only LiteDRAM image remains
separate unfinished work. A built image does not demonstrate a CH0 repair.

## Status and loading

Offline timing, routing, all 278 board-reference pins, packet/CRC, full compute
and DDR resources, the two reset registers, PCIe OOB modes, 39 bus-skew checks
and the recorded critical CDC inventory passed. Physical loading, memory and
inference with this candidate are pending. Use `shasum -a 256 -c SHA256SUMS`
inside this folder, then load `otpu.bit` into SRAM with the working Mac JTAG
loader. Preserve the 100 MHz working CH1 NOR image. This package contains no
NOR programming file. Do not write the LiteX global SoC reset CSR.

Use this folder's `core/` with the existing Chestnut adapter. From the repository
root, after loading and with inference stopped, capture identity and CH0/CH1
calibration/ECC state:

```bash
build/chestnut-lfm/venv/bin/python tools/fedora_probe_ddr_recovery.py \\
  --adapter build/chestnut-lfm/transport.py \\
  --core bitstreams/ch1-pcie-2gb-ch0-reset/core --snapshot-only \\
  --out build/results/ch0-reset-identity
```

The snapshot command does not recalibrate or start BIST. Follow the
[debug plan](../../docs/ddr_ram_only_debug.md) for cold/warm ordering and
controlled rescans. Save a failing warm state before retraining. A CH0 raw
BIST pass does not establish normal ECC user-port, host or inference access.

## Rebuild on Fedora

The pinned generated core allows a rebuild with full Vivado and Python, with
no LiteX generator/compiler dependency:

```bash
python3 tools/fedora_build_vivado_pcie_ddr800.py \\
  --core bitstreams/ch1-pcie-2gb-ch0-reset/core \\
  --core-mhz 100 --build-id c0160001 --out build/ch0-reset-rebuild
python3 tools/fedora_qualify_ch1_image.py \\
  --build build/ch0-reset-rebuild \\
  --reference-release bitstreams/ch1-pcie-2gb-ch0-reset \\
  --core-khz 100000 --expect-serializer-reset-stage --review-oob-clocks \\
  --out build/ch0-reset-rebuild-review
```

Use fresh output directories. Review fresh CDC/skew findings before loading a
rebuilt image. The retained historical ECC comparison is identified separately
from physical tests. Read the [PHY/branch review](../../docs/ddr_upstream_branch_review.md)
for the distinction between this reset change and the older framing fixes.
''')
files = [dict(name=str(path.relative_to(OUT)), **describe(path))
         for path in sorted(OUT.rglob('*')) if path.is_file()]
manifest = dict(status='EXPERIMENTAL_CH1_PCIE_CH0_RESET_OFFLINE_REVIEW_PASS_PHYSICAL_PENDING',
                created_utc=datetime.now(timezone.utc).isoformat(), part='xc7k480tffg1156-2',
                build_id_register='0xc0160001', compute=m['profile'], pcie='XDMA Gen2 x8',
                memory=dict(physical_user_channels=[1], logical_capacity_bytes=1 << 31,
                            virtual_channel_bytes=1 << 30, ddr_mts=800, ecc=True,
                            calibration_mask=2, ch0_normal_user_access=False),
                upstream_commit=m['upstream_commit'], serializer_reset_stage=True,
                read_register=False, read_latency=8, hardware_accessed=False,
                flash_written=False, physical_ch0_repair_verified=False,
                physical_model_verified=False, mcs_payload_checked_not_packaged=True,
                timing=timing, route=route, files=files)
(OUT / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
(OUT / 'SHA256SUMS').write_text(''.join(f"{describe(path)['sha256']}  {path.relative_to(OUT)}\n"
                                      for path in sorted(OUT.rglob('*')) if path.is_file()))
print(json.dumps(dict(folder=str(OUT), status=manifest['status'], bitstream=describe(OUT / 'otpu.bit'))))
