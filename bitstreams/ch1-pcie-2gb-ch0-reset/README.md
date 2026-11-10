# Experimental CH0 serializer-reset comparison

BUILD_ID `c0160001`; full OpenTPU compute at 100 MHz, DDR3-800, Gen2 x8
PCIe and 2 GiB through physical CH1. The `f2d1023d` serializer-reset stage is
present on both PHYs. CH0 still has no normal host/compute user mapping.
Its retained calibration CPU and raw BIST permit CH0 PHY comparisons.
This is a full-system comparison image. The RAM-only LiteDRAM image remains
separate unfinished work. A built image does not demonstrate a CH0 repair.
Start with the RAM-only MIG baseline in the debug plan before this comparison.

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
build/chestnut-lfm/venv/bin/python tools/fedora_probe_ddr_recovery.py \
  --adapter build/chestnut-lfm/transport.py \
  --core bitstreams/ch1-pcie-2gb-ch0-reset/core --snapshot-only \
  --out build/results/ch0-reset-identity
```

The snapshot command does not recalibrate or start BIST. Check the
result's `identity_before.build_id` and require `0xc0160001` before attributing
results to this candidate. Follow the
[debug plan](../../docs/ddr_ram_only_debug.md) for cold/warm ordering and
controlled rescans. Save a failing warm state before retraining. A CH0 raw
BIST pass does not establish normal ECC user-port, host or inference access.

## Rebuild on Fedora

The pinned generated core allows a rebuild with full Vivado and Python, with
no LiteX generator/compiler dependency:

```bash
python3 tools/fedora_build_vivado_pcie_ddr800.py \
  --core bitstreams/ch1-pcie-2gb-ch0-reset/core \
  --core-mhz 100 --build-id c0160001 --out build/ch0-reset-rebuild
python3 tools/fedora_qualify_ch1_image.py \
  --build build/ch0-reset-rebuild \
  --reference-release bitstreams/ch1-pcie-2gb-ch0-reset \
  --core-khz 100000 --expect-serializer-reset-stage --review-oob-clocks \
  --out build/ch0-reset-rebuild-review
```

Use fresh output directories. Review fresh CDC/skew findings before loading a
rebuilt image. The retained historical ECC comparison is identified separately
from physical tests. Read the [PHY/branch review](../../docs/ddr_upstream_branch_review.md)
for the distinction between this reset change and the older framing fixes.
