#!/usr/bin/env python3
"""Package c0172080 only after its exact artifact, CDC and gray-pointer reviews.

Offline only. A manual CDC disposition is required; collection is not approval.
No flash programming file is included.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import gzip
import json
from pathlib import Path
import shutil
import sys

from fedora_prepare_litedram import ROOT, sha
from fedora_qualify_ch1_image import describe, unchanged, FULL
from fedora_review_ramtest_mig import cdc_rows
from fedora_check_native_image import timing_summary, route_summary
from probe_ramtest_spare_calibration import preflight as reference_preflight

sys.path.insert(0, str(ROOT))


def check(build, qualification, review_path):
    m = json.loads((build/'manifest.json').read_text())
    q = json.loads(qualification.read_text())
    r = json.loads(review_path.read_text())
    assert m['status'] == 'FULL_NATIVE_VIVADO_PCIE_SPARE8_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING'
    assert m['build_id'] == 'c0172080' and m['profile'] == FULL
    assert m['physical_user_channels'] == [0, 1] and m['usable_logical_bytes'] == 1 << 32
    assert m['ecc_channels'] == [1] and m['automatic_calibration_channels'] == [1] and m['host_calibration_channels'] == [0]
    assert q['status'] == 'SPARE_PCIE_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING'
    assert q['build_manifest'] == describe(build/'manifest.json')
    assert q['bitstream'] == m['outputs']['otpu.bit'] and q['routed_checkpoint'] == m['outputs']['final-routed.dcp']
    assert r['status'] == 'SPARE_PCIE_CDC_REVIEW_PASS_EXTERNAL_DDR_TIMING_AND_PHYSICAL_PENDING'
    assert r['qualification'] == describe(qualification) and r['bitstream'] == q['bitstream']
    assert r['reviewed_scope'] and r['operating_limitations']
    assert r['external_ddr_pad_timing_qualified'] is False and r['physical_operation_verified'] is False
    unchanged(r['source_comparison'])
    source_review = json.loads(Path(r['source_comparison']['path']).read_text())
    assert source_review['status'] == 'SPARE_CDC_SOURCE_COMPARISON_RECORDED_ROUTED_AND_MANUAL_REVIEW_PENDING'
    for path, digest in source_review['sources'].items():
        assert sha(Path(path)) == digest
    unchanged(r['collection']); unchanged(r['csr_gray_review'])
    c = json.loads(Path(r['collection']['path']).read_text())
    g = json.loads(Path(r['csr_gray_review']['path']).read_text())
    assert c['status'] == 'CDC_EVIDENCE_COLLECTED_REVIEW_PENDING'
    assert g['status'] == 'PASS_ROUTED_CSR_GRAY_SKEW_AND_SYNCHRONIZERS_PHYSICAL_PENDING'
    for item in (c, g):
        assert item['qualification'] == describe(qualification)
        assert item['bitstream'] == q['bitstream'] and item['routed_checkpoint'] == q['routed_checkpoint']
    assert not g['netlist_placement_routing_modified'] and not g['original_constraints_modified']
    assert g['total_skew_constraints'] == 49 and g['minimum_skew_slack_ns'] >= 0
    assert len(g['reviewed_gray_rows']) == 10
    witnesses = m['sources'] + list(m['outputs'].values()) + q['evidence'] + c['evidence'] + g['evidence']
    witnesses += [c['collector'], c['reference_cdc'], g['source'], q['preparation'], q['reference_pin_evidence']]
    for item in witnesses:
        unchanged(item)
    for path, digest in q['source_hashes'].items():
        assert sha(Path(path)) == digest
    rows = [list(row) for row in cdc_rows((qualification.parent/'oob-cdc.rpt').read_text())]
    assert rows and r['reviewed_non_info_rows'] == rows
    groups = r['finding_groups']
    assert groups and all(group['reason'] and group['rows'] for group in groups)
    assert Counter(tuple(row) for group in groups for row in group['rows']) == Counter(map(tuple, rows))
    timing = timing_summary((qualification.parent/'oob-timing.rpt').read_text())
    route = route_summary((qualification.parent/'oob-route.rpt').read_text())
    assert timing == q['oob_clock_review']['timing'] and route == q['route']
    assert all(timing[k] >= 0 for k in ('WNS', 'WHS', 'WPWS'))
    assert all(timing[k] == 0 for k in ('setup_failing', 'hold_failing', 'pulse_failing'))
    assert route['routable'] == route['fully_routed'] > 0 and route['routing_errors'] == 0
    assert q['pins_checked'] == 278 and q['pad_connections'] == 180 and q['disabled_buffers'] == 9
    assert q['oob_clock_review']['bus_skew_constraints'] == 39 and q['oob_clock_review']['minimum_bus_skew_slack_ns'] >= 0
    assert {row[1] for row in q['serializer_reset_registers']} == {'0', '1'}
    assert q['crc']['status'] == 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH' and q['crc']['crc_checkpoints'] == 2
    return m, q, r, c, g, timing, route


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for name in ('build', 'qualification', 'cdc-review', 'reference-package', 'firmware', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    a = p.parse_args()
    from opentpu.host.spare_pcie import SparePcieProfile, MEMORY, PACKAGE_STATUS
    build, qualification, review, out = (path.resolve() for path in (a.build, a.qualification, a.cdc_review, a.out))
    stage = out.with_name(out.name+'.preparing')
    assert not out.exists() and not stage.exists()
    m, q, r, c, g, timing, route = check(build, qualification, review)
    reference_preflight(a.reference_package, a.firmware)
    core = build/'source/boards/ypcb-00338/litedram'
    for name in ('otpu_litedram.v', 'csr.csv', 'sdram_init.py', 'sdram_init_ch0.py', 'otpu_litedram_mem.init'):
        assert sha(core/name) == sha(a.reference_package/'core'/name)
    stage.mkdir(parents=True)
    shutil.copy2(m['outputs']['otpu.bit']['path'], stage/'otpu.bit')
    shutil.copytree(core, stage/'core', ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copytree(a.firmware, stage/'calibration', ignore=shutil.ignore_patterns('__pycache__'))
    evidence = stage/'evidence'; evidence.mkdir()
    for path, name in [(build/'manifest.json', 'build-manifest.json'), (qualification, 'offline-image-review.json'),
                       (review, 'cdc-review.json'), (Path(r['collection']['path']), 'cdc-collection.json'),
                       (Path(r['source_comparison']['path']), 'cdc-source-comparison.json'),
                       (Path(r['csr_gray_review']['path']), 'csr-gray-review.json'), (Path(__file__), 'packager.py'),
                       (a.reference_package/'bundle.json', 'reference-bundle.json')]:
        shutil.copy2(path, evidence/name)
    for label, report in [('artifact', q), ('cdc', c), ('gray', g)]:
        folder = evidence/label; folder.mkdir()
        names = set()
        for item in report['evidence']:
            source = Path(item['path'])
            name = source.name + ('.gz' if source.suffix in ('.rpt', '.log') else '')
            assert name not in names; names.add(name)
            if source.suffix in ('.rpt', '.log'):
                (folder/name).write_bytes(gzip.compress(source.read_bytes(), mtime=0))
            else:
                shutil.copy2(source, folder/name)
    (stage/'README.md').write_text('''# Experimental OpenTPU spare-lane 4 GiB image

Build `c0172080`: full OpenTPU at 100 MHz, DDR800, XDMA Gen2 x8.
CH0 uses physical lanes 0,1,2,3,4,5,8,7 without ECC; CH1 retains ECC.
Both channels expose 2 GiB. This does not restore the original dual-ECC design.
Internal artifact/CDC reviews do not establish external DDR pad timing or
physical runtime reliability. No flash image is included.

Verify `shasum -a 256 -c SHA256SUMS` here before loading `otpu.bit` into SRAM.
Keep the entire `core/` and `calibration/` directories. Startup firmware
calibrates CH1 only. CH0 needs the separately bound eight-lane calibration
procedure, followed by complete memory initialization and native/ECC checks.
The host guard checks the spare lane map, capacity and ECC mask registers;
do not use a CH1-only or dual-ECC transport with this image.

See [build, calibration and qualification procedures](../../docs/ddr_spare_native_probe.md).
The CH0 calibration helper also requires the original
`../ramtest-litedram-ddr800-spare8/` reference package to verify the firmware
binding. This dependency is intentional; keep it available on the test host.
The physical DDR/partial-write passes recorded for the RAM-only image do not
qualify this full implementation. PCIe DMA, matmul and LFM inference remain
separate qualification steps. The working CH1-only package remains available.
''')
    files = [dict(name=str(path.relative_to(stage)), bytes=path.stat().st_size, sha256=sha(path))
             for path in sorted(stage.rglob('*')) if path.is_file()]
    manifest = dict(status=PACKAGE_STATUS, created_utc=datetime.now(timezone.utc).isoformat(),
        build_id_register='0xc0172080', part='xc7k480tffg1156-2', compute=FULL,
        compute_clock=m['compute_clock'], memory_clock=m['memory_clock'], memory=MEMORY,
        pcie='XDMA Gen2 x8', hardware_accessed=False, flash_written=False,
        physical_ch0_repair_verified=False, physical_model_verified=False,
        external_ddr_pad_timing_qualified=False, timing=timing, route=route,
        oob_clock_review=q['oob_clock_review'], files=files)
    (stage/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    (stage/'SHA256SUMS').write_text(''.join(f'{sha(path)}  {path.relative_to(stage)}\n'
        for path in sorted(stage.rglob('*')) if path.is_file()))
    SparePcieProfile(stage)
    # Revalidate source evidence after copying, before publishing the local directory.
    check(build, qualification, review)
    stage.rename(out)
    print(json.dumps(dict(status=PACKAGE_STATUS, package=str(out), bitstream_sha256=sha(out/'otpu.bit'))))


if __name__ == '__main__':
    main()
