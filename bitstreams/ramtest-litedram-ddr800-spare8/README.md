# DDR800 CH0 lane-8 replacement

Build ID `c0172060`. LDRT ABI 3; two 2 GiB channels.
Controller clock: 100.000000 MHz. DDR data rate: 800.000000 MT/s.
ECC channels: [1]. This RAM diagnostic has no PCIe endpoint or compute core.

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

## Spare-lane limits

CH0 logical lanes map to physical `[0,1,2,3,4,5,8,7]`; physical lane 6 is held
high impedance. CH0 has no ECC. CH1 retains its nine-lane ECC interface.
Only CH1 calibrates automatically. CH0 requires the matched eight-lane
`core/sdram_init_ch0.py`; nine-lane calibration/readers are incompatible.
Its two native ports use serialized full-word read/merge/write for partial
writes. Keep raw BIST idle while native clients run. Host procedures and full
physical qualification are still pending; no capacity recovery is claimed.
