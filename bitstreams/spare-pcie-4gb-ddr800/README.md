# Experimental OpenTPU spare-lane 4 GiB image

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
