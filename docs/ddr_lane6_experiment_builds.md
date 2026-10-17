# Lane-6 diagnostic images: loading, rebuilding and review

These three local packages were built and independently reviewed on October
17, 2026. They are experimental RAM diagnostics, not qualified OpenTPU releases.
They have not been committed or pushed.

| Package | Build ID | Controller / DDR rate | ECC | Offline build |
| --- | --- | --- | --- | --- |
| [Command/PHY trace](../bitstreams/ramtest-litedram-ddr800-phy-trace/) | `c0172040` | 100 MHz / 800 MT/s | Both channels | Complete |
| [Lower rate](../bitstreams/ramtest-litedram-ddr667/) | `c0172050` | 83.333 MHz / 666.667 MT/s | Both channels | Complete |
| [Spare lane](../bitstreams/ramtest-litedram-ddr800-spare8/) | `c0172060` | 100 MHz / 800 MT/s | CH1 only | Complete |

All preserve 2 GiB per channel. The spare image replaces CH0 physical lane 6
with physical lane 8, retaining eight data devices but sacrificing CH0 ECC.
Only CH1 calibrates automatically in that image. CH0 needs its packaged
eight-lane `sdram_init_ch0.py`; a nine-lane reader is incompatible.

## Loading on macOS or Linux

Vivado is needed to **build**, not to load these existing `.bit` files.
Verify `SHA256SUMS` inside the selected package, use the working JTAG loader
to load `ramtest.bit` into volatile SRAM, and start XVC on port 3721. Do not
write BPI flash as part of these tests. The [trace package README](../bitstreams/ramtest-litedram-ddr800-phy-trace/README.md)
has its bounded physical reader command. Lower-rate and spare-lane host
procedures remain separate qualification work; do not bypass another reader's
identity or geometry checks to use it with these images.

The current queue on the test machine waits for the retained-image address
sweep and its independent review, then loads the trace image and runs 14
full-word writes and 720 serialized reads. It retains the reported sole
12 V / 2 A supply as an unresolved experimental condition. This queue is not
part of the packages and does not run when they are downloaded.

## Build prerequisites

- Linux, Vivado with Kintex-7 support, and a C++ compiler for packet/CRC checks.
- The pinned LiteX/Migen/LiteDRAM environment used by the existing
  [RAM-only build procedure](ddr_ram_only_debug.md#frozen-core-generation-and-rebuild).
- A working RV32I compiler plus matching `objcopy` and `objdump`. A container
  wrapper must mount the selected output directory writable. An old wrapper
  that mounts another build directory will fail.
- The reference core and packaged traffic/capture model receipts already
  used by the ordinary RAM-only builder.

Run from the repository root and always choose fresh output directories.
`--vivado /path/to/vivado` overrides the local default on implementation and
review tools. The variant builder accepts `--python`, `--rv-cc`, and
`--traffic-build` overrides. Without `--rv-cc`, it uses the existing local
Podman toolchain image; that image is not installed by this command.

## Command/PHY trace

Follow the [trace generation, implementation and review commands](ddr_lane6_trace_build.md#build).
The matching model can be regenerated using the pinned Python:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python \
  tools/check_ramtest_phy_trace.py --out build/checks/trace-model-new
```

Pass that receipt to `review_ramtest_phy_trace.py --model`. The model checks
BRAM packing, freeze/epoch behavior and unchanged native traffic; it does not
simulate the external DDR electrical interface.

## DDR667 and spare-lane generation and implementation

Prepare a traffic-source donor once. It does not program the card:

```bash
python3 tools/fedora_build_ramtest_mig.py \
  --ddr-mts 800 --channels both --pattern address --build-id c0161001 \
  --prepare-only --out build/vivado/experiment-traffic-donor
```

Use one fresh directory per variant. The example compiler path must be
replaced with the actual working compiler:

```bash
python3 tools/fedora_build_ramtest_variant.py --variant ddr667 \
  --rv-cc /path/to/riscv64-elf-gcc \
  --traffic-build build/vivado/experiment-traffic-donor \
  --out build/vivado/ddr667-new

python3 tools/fedora_build_ramtest_variant.py --variant spare8 \
  --rv-cc /path/to/riscv64-elf-gcc \
  --traffic-build build/vivado/experiment-traffic-donor \
  --out build/vivado/spare8-new
```

The driver freezes the generator and calibration firmware, builds the matched
core and firmware, then synthesizes, places and routes the wrapper. Bitstream
emission requires nonnegative internal timing and no blocking DRC findings.
Configuration packet and CRC checks follow. Generation success alone is not
build completion.

Future main-builder runs apply setup/hold uncertainty after generated clocks
exist: half the DDR clock period, 1.25 ns at DDR800 or 1.5 ns at DDR667. The
original candidates were additionally reviewed against these full bounds in
separate post-route analyses. Static DRP group-offset changes are outside that
particular analysis and require their own review.

## Independent variant review

For DDR667, use `variant=ddr667` and `run=build/vivado/ddr667-new`; for the spare
image use `variant=spare8` and its directory. These are shell variables local
to this task:

```bash
variant=ddr667
run=build/vivado/ddr667-new
python3 tools/fedora_review_ramtest_litedram.py --variant "$variant" \
  --build "$run/implementation" --out "$run/base-review.json"
python3 tools/review_ramtest_phase_envelope.py \
  --build "$run/implementation" --out "$run/phase-review"
python3 tools/review_ramtest_variant.py \
  --build "$run/implementation" --generation "$run" \
  --base-review "$run/base-review.json" \
  --phase-review "$run/phase-review/manifest.json" \
  --out "$run/extension-review"
```

For a new spare build, first run its adapter model and pass the receipt to
the last command with `--native-model`:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python \
  tools/check_ramtest_spare_native.py --out build/checks/spare-model-new
```

The base review checks matched resources, clocks, 238 board-reference pins,
route completion, timing, coverage and CDC. The extension checks every DQ/DQS
group in generated Verilog and all 180 corresponding routed pad connections.
For the spare image it also checks nine disabled buffers are held high
impedance, CH0 calibration is excluded from the nine-lane firmware, the
eight-lane host configuration is present, and the tested partial-write adapter
matches the generated source.

## Package without publishing

```bash
python3 tools/fedora_package_ramtest_experiment.py \
  --build "$run/implementation" --generation "$run" \
  --base-review "$run/base-review.json" \
  --phase-review "$run/phase-review/manifest.json" \
  --extension-review "$run/extension-review/manifest.json" \
  --out bitstreams/ramtest-new-experiment
```

For trace/spare packages, pass the matching observer/adapter model using
`--model`. Trace generation lives in its separate generation directory, and
its extension receipt is the JSON output of `review_ramtest_phy_trace.py`.
The packager checks the evidence bindings and copies the bitstream, matched
core, frozen implementation inputs, generator sources and review evidence.
It generates and checks `SHA256SUMS`. It neither commits nor pushes.

Offline completion is distinct from a physical repair. Reproduce the failing
sequence, then qualify full capacity, repeated initialization, thermal behavior
and full OpenTPU workloads before declaring recovery.

## Bounded DDR800 / DDR667 history comparison

The rate reader uses the same 14 full-word writes and 720 serialized raw reads
for each image. It checks package checksums, exact loaded identity, matched
CSR widths, idle native generators and calibration state. It does not retrieve
PHY traces, request calibration, program the FPGA or write flash. Its raw
writes invalidate normal ECC contents in the selected region; initialize memory
before subsequently using the native ECC path.

First check a package without accessing hardware:

```bash
python3 tools/probe_ramtest_rate_history.py \
  --variant ddr667 --package bitstreams/ramtest-litedram-ddr667 \
  --out build/checks/ddr667-host-preflight-new --preflight-only
```

With that image loaded into SRAM and an exclusively owned XVC server on
port 3721, omit `--preflight-only` and use a fresh output directory to run the
bounded experiment. For the DDR800 trace image, select `--variant trace` and
`--package bitstreams/ramtest-litedram-ddr800-phy-trace`. Never run another
reader or loader while the comparison service owns the cable.

The current local comparison runner is
`build/hardware-test/rate-history-comparison-20261017/run.py`. It records
SRAM-load logs, owns/stops its XVC child, and invokes
`tools/review_ramtest_rate_history.py` to archive and independently check every
payload before advancing. Its experiment directories record calibration,
temperature, image identity and the sole 12 V / 2 A supply condition.

For saved PHY traces, `tools/analyze_ramtest_phy_pipeline.py --review REVIEW
--out NEW_JSON` reconstructs the digital alignment transforms from an archived
`review_ramtest_phy_history.py` receipt. This is offline analysis; it neither
captures new data nor proves electrical timing at the DRAM pins.
