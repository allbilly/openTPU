# Full 4 GiB spare-lane speed candidates

**Historical October 17 build plan.** Current recorded results and remaining
tests are in [the bitstream table](bitstreams.md#tested-builds-and-outstanding-tests)
and [HANDOFF.md](../HANDOFF.md). The later c0182800/c0182863 baselines passed
Mac LFM/Qwen; c0182600/c0182663 passed local JTAG startup/TinyStories checks.
c0172462 was rejected, and the old candidate queues below are not an active
test plan. The c01848 runtime-clock effort was abandoned on October 22.
No new implementation or programming is selected by this historical guide.

The permanently flashed baseline at that time was `c0172080`: **100 MHz compute,
DDR3-800**, a 400 MHz RAM clock and 800 MT/s. It is not DDR3-866.
All candidates below retain four compute columns, four activation rows, eight
compute lanes, the systolic MXU, both 2 GiB memory channels and XDMA Gen2 x8.
CH0 physical lanes are `0,1,2,3,4,5,8,7` with ECC disabled; CH1 retains ECC.

The later Mac performance report identified a separate throughput issue:
6.10 GB/s on the earlier CH1 image versus 0.89 GB/s on the spare image, with
approximately unchanged bytes per token. Source inspection confirms a shared
one-outstanding-transaction CH0 adapter. All three speed candidates below
inherit it; higher clocks do not remove that serialization. These remain
clock-comparison candidates. A new pipelined-read spare image at baseline
clocks is now the performance priority. See the
verified source finding (local-only `docs/data/spare_pcie_serial_read_bottleneck_20261017.json`)
and revised plan (local-only `docs/ddr_lane6_debug_plan.md`).

## Above DDR1066: documented experiments, not qualified configurations

Reviewed October 17, 2026 against the upstream board/LiteDRAM documentation
and AMD DS182 Table 18. The board uses HR I/O banks; the -2 device's DDR3
rating at 1.5 V is 1066 Mb/s per pin. The higher HP-bank ratings do not apply.
Using LiteDRAM does not raise this characterized I/O limit. This does not
establish the actual DRAM supply/reference voltage on this particular card.

| Rate | Upstream evidence | Scope and limitation |
| --- | --- | --- |
| DDR1200 | One-channel A7DDRPHY implementation at 150 MHz sys met setup/hold timing | Out-of-context implementation only; not a demonstrated full OpenTPU or current spare-lane WL7DDRPHY hardware pass |
| DDR1300 | Historical MIG image `819fee49`: both channels calibrated, memory/soak checks and three models matching ISA passed | One reported run; ECC correction counters and warm qualification were missing. Remained explicitly unqualified and out of spec |
| DDR1333 | Historical patched MIG image `254f8388` met routed timing and calibrated | DMA timeout followed by PCIe disappearance. The documented host-write confound prevents a clean DDR-only diagnosis; not a working candidate |
| DDR1600 | Historical configuration/PHY-patch path documented | Hardware testing not pursued after the DDR1333 failure |

The historical MIG evidence does not qualify this fork's pipelined spare-lane
LiteDRAM images. A faster LiteDRAM experiment needs a regenerated core,
matching DDR initialization, firmware/host bindings, full routed review and
physical numerical checks. The user selected `c0172462` DDR1066 first at that
time, then requested the four faster-rate builds recorded below. c0172462
subsequently failed final review for its shared-host reset defect; none of
these earlier selection statements establishes current eligibility.

Sources: [upstream board speed experiments](https://github.com/FeSens/openTPU/blob/main/docs/board.md#faster-ddr3),
[upstream LiteDRAM assessment](https://github.com/FeSens/openTPU/blob/main/docs/litedram.md),
[AMD DS182, Table 18](https://docs.amd.com/api/khub/documents/BhulK6GRrzUpQYw0lzrnMA/content).

### Historical requested faster-rate implementation queue

The recorded `opentpu-spare4gb-overclock-queue-20261017.service` was intended
to prepare rate-specific cores and calibration binaries, wait for the exact
four-image parallel queue, then admit at most two implementations. Its paths
and proposed states below are retained history, not evidence of live workers.

| Build ID | Compute request / actual | DDR rate | Initial state |
| --- | --- | --- | --- |
| c0173120 | 150 / 148.837209 MHz | DDR1200 | Core and firmware generation started |
| c0173130 | 150 / 148.837209 MHz | DDR1300 | Source preparation queued |
| c0173133 | 150 / 148.837209 MHz | DDR1333, actual 1333.333 MT/s | Source preparation queued |
| c0173160 | 150 / 148.837209 MHz | DDR1600 | Source preparation queued |

All retain the full accelerator, 4 GiB, the spare CH0 lane map, pipelined
two-port CH0 reads, CH1 ECC, JTAG USER2 and PCIe. CL/CWL and DDR initialization
are regenerated for each rate; the CH0 helper is recompiled. Startup remains
CH1-only. Rate-specific calibration models, host/package bindings and complete
routed review are additional pending gates. The existing numerical, pulse,
routing and DRC gates remain mandatory. A requested rate is not a promise
that the current clock topology can implement it; failed limits will not be
relaxed to produce a bitstream.

Historical read-only queue inspection commands:

```bash
systemctl --user status opentpu-spare4gb-overclock-queue-20261017.service
cat build/fedora-vivado/spare-overclock-queue-20261017/manifest.json
```

Its frozen preparer, commands and logs are in the latter directory. To prepare
a fresh individual experiment from the checked combined-host and generation
references, use `tools/prepare_spare_overclock.py --help`. After preparation,
implement its exact frozen source with `tools/run_spare_dual_snapshot.py`,
passing the preparation manifest's SHA-256. No new image is programmed or
permanently flashed by these build services.

All four source preparations have now passed and the queue is waiting for the
existing implementation owner. Their rate-specific CH0 firmware comparisons
also passed all three established cases (ordinary, per-bit framing, missing
lane window). Receipts are under
`build/checks/spare-overclock-firmware-queue-20261017/`.

Exact JTAG/Chestnut/XDMA host helpers are prepared under
`build/handoffs/spare-overclock-host-c0173120-v2-20261017/host/`, with matching
directories for c0173130, c0173133 and c0173160. CLI imports and shell syntax
passed, and each helper rejected the actual c0172080 baseline package. The
helpers require their own correctly reviewed package before device access;
no actual higher-rate package or positive hardware acceptance exists yet.
The v1 host preparations are retained. The v2 metadata binds both preparation
fields to the selected rate's actual source manifest and updates the clock-rate
diagnostic text; it does not change the running implementation snapshots.

The corresponding artifact/CDC/Gray/source collectors are prepared under
`build/checks/spare-overclock-review-c0173120-v2-20261017/review/`, with
matching paths for the other IDs. A streaming collection worker,
`opentpu-spare4gb-overclock-review-complete-cdc-20261017.service`, waits for each
exact implementation receipt in rate order. It collects successful images
without waiting for every later implementation. Failed numerical/DRC builds
are skipped with their evidence preserved; collection still requires an
explicit CDC disposition before packaging. The first source-only collector
preparation attempts are retained; the corrected v2 preparations passed.

Reproduce an exact host or review preparation in fresh output directories:

```bash
python3 -B tools/prepare_spare_overclock_host.py \
  --preparation "$RATE_PREPARATION" \
  --firmware-review "$RATE_FIRMWARE_MODEL" \
  --out build/handoffs/spare-overclock-host-new
python3 -B tools/prepare_spare_overclock_review.py \
  --preparation "$RATE_PREPARATION" \
  --out build/checks/spare-overclock-review-new
```

`tools/run_spare_dual_bandwidth.py` accepts all four new IDs, retaining the
same exact-package/calibration/initialized-memory guards. Device bandwidth
and numerical inference results remain unmeasured at these rates.

Exact package scripts are also prepared at
`build/checks/spare-overclock-packager-c0173120-v1-20261017/generated/`, with
corresponding paths for the other IDs. They require the actual higher-rate
implementation, per-image artifact/Gray/source evidence and complete explicit
CDC disposition. All 40 routed-review assertions in the existing combined-host
checker are retained, verified by an AST comparison after exact build-ID
substitution. The checked firmware/model and corrected v2 host tree are bound
to each script; each resulting package includes its own host tree.

Separate firmware-only fixtures confirmed the generated calibration helper
accepts the corresponding firmware bundle, rejects a changed firmware ID, and
the package checker rejects the actual original c0172080 implementation.
These fixtures use zero image hashes and have no FPGA bitstream; they are not
image packages or evidence of positive acceptance of a higher-rate image.
Receipts are under `build/checks/spare-overclock-package-bindings-20261017/`;
the source checker comparison is under
`build/checks/spare-overclock-packager-contracts-20261017/`.

To prepare a fresh exact package script after its host/firmware preparation:

```bash
python3 -B tools/prepare_spare_overclock_packager.py \
  --preparation "$RATE_PREPARATION" \
  --host-tree "$RATE_HOST_TREE" \
  --firmware-model "$RATE_FIRMWARE_HOST_REVIEW" \
  --out build/checks/spare-overclock-packager-new
```

`RATE_FIRMWARE_HOST_REVIEW` names that model's `host-model-review.json`.
The generated script's `--help` lists its packaging arguments. The reference
preparation and firmware arguments must select the same rate's preparation
and its `calibration/` directory. Numerical/CRC/CDC checks still precede
packaging; no script was run to package a nonexistent or failing image.

## Queue created October 17, 2026

**This original queue is superseded.** After confirming the shared adapter
bottleneck, the user asked to stop the old-adapter routing. `c0172150` and its
two review waiters were stopped; the two unstarted DDR1066 jobs and their
waiters were removed from the queue. No package was produced from the stopped
route. Checkpoints, logs and command schedules are retained. The active build
is [pipelined baseline `c0172300`](ddr_spare_pipeline.md). Four replacement
builds, c0172400/c0172450/c0172461/c0172462, now include the pipeline and both
JTAG/PCIe interfaces. The user selected c0172462 first; it and c0172400 are
building concurrently, followed by c0172450 and c0172461 in freed slots. See
[the current queue and rebuild procedure](ddr_spare_dual_host.md). The table
and handles below describe the preserved original preparations.

| Build ID | Requested compute | Actual compute | RAM data rate | State when queued |
| --- | --- | --- | --- | --- |
| `c0172080` | 100 MHz | 100 MHz | DDR800 | Flash/verify/JTAG boot passed; subsequent Mac Qwen2B inference pass reported by user, raw logs pending |
| `c0172150` | 150 MHz | 148.837209 MHz | DDR800 | Vivado implementation running; artifact collector waiting for this build |
| `c0172161` | 100 MHz | 100 MHz | DDR1066, actual 1066.666667 MT/s | Controller/firmware generated and source prepared; implementation queued |
| `c0172162` | 150 MHz | 148.837209 MHz | DDR1066, actual 1066.666667 MT/s | Controller/firmware generated and source prepared; implementation queued |

The compute MMCM keeps its 800 MHz VCO and fractional divider, so its nearest
setting for a 150 MHz request is 148.837209 MHz. The DDR1066 controller uses a
133.333333 MHz user clock, 533.333333 MHz DDR clock and CL7/CWL6. Compute and
RAM clocks are independent. Both DDR1066 candidates have new build IDs and
cannot be accepted by the existing DDR800 runtime guard.

The DDR1066 generator starts from the reviewed spare-lane generator snapshot.
It recompiles CH1-only startup firmware (`c0172160`) and separate eight-lane
CH0 firmware (`c0172168`) against the new initialization sequence, CSR map,
phase settings and wait counts. It preserves the reference calibration CPU
and checks the full controller interface and existing CSR register addresses.
The phase uncertainty is 1 ns, covering the 0.9375 ns half-DDR-clock bound.
These source checks and compilation do not prove physical calibration.

The source comparison in
`build/checks/spare4gb-speed-source-contracts-20261017/manifest.json` passed:
all 31 accelerator RTL files match the baseline exactly for `c0172150`.
For `c0172161` and `c0172162`, 30 match exactly and the remaining control file
differs only in an ECC comment. The full compute parameters and both 2 GiB
channels remain selected. All 33 frozen generator files and nine CH0 firmware
source files match their reviewed references. CSR register addresses, widths
and access modes match; the generated timestamp and declared clock-frequency
constant change at DDR1066. The two selected CSR FIFO/synchronizer source
groups (512 and 50 lines) also match. These comparisons establish those source
relationships, not routed timing or physical correctness at the new clocks.

## Build and review order

1. Build `c0172150` through synthesis, routing and strict pre-bit timing/DRC
   gates. Its own collector waits on the exact live service invocation.
2. The DDR1066 queue waits for that implementation process to terminate, then
   builds and collects artifacts for `c0172161`, followed by `c0172162`.
3. Review each candidate's exact routed setup/hold/pulse timing, clocks,
   serializer resets, phase queries, pads, bitstream CRC and packets.
4. Collect and review its CDC paths and gray-pointer skew at the new clocks.
   Baseline CDC approval is not copied to a faster image automatically.
5. Package only candidates that pass the relevant offline gates, with a new
   explicit host identity/calibration binding. Then perform SRAM-load, DMA,
   native partial writes, full payload, matmul, LFM2 and repeated-start tests.

The queue runs one implementation at a time to limit memory contention. A
failed candidate retains its logs and skips its dependent artifact review;
the other independent candidate is still attempted. An observation timeout
does not restart the existing job. No job in this queue accesses JTAG, USB,
PCIe hardware or flash. The card can be powered down and moved to the Mac.

Clock-specific crossing collectors have also been prepared for all three
candidates. Their jobs wait on the exact artifact producer's invocation,
then collect synchronizer fanins, actual clock periods, all ten CSR FIFO
Gray-pointer groups and a source-contract comparison. The Gray-pointer skew
budget is derived from the actual source and destination periods. Collection
preserves the routed checkpoint and original constraints; it does not grant
CDC approval. A changed path inventory or clock/fanin fact needs an explicit
review before packaging.

Five build milestones are used for progress: source preparation, synthesis,
routing, bitstream and completed review/package. Thus prepared candidates are
20%, even when waiting in a queue. This is not a time estimate.

## Reproduce preparation

From the checkout, with the pinned LiteX environment and working compiler
container used by the DDR800 preparation:

```bash
python3 tools/prepare_spare_pcie.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8 \
  --firmware bitstreams/ramtest-spare8-ch0-firmware \
  --adapter-model build/checks/spare-native-rmw-20261017/manifest.json \
  --core-mhz 150 --threads 2 --out build/vivado/spare4gb-core150-ddr800
```

The output contains `build.command.json` with the exact implementation command.
The adapter-model receipt must match the current reviewed native adapter source.

Generate both DDR1066 preparations in a fresh directory:

```bash
python3 tools/prepare_spare_pcie_ddr1066.py \
  --reference-package bitstreams/ramtest-litedram-ddr800-spare8 \
  --reference-firmware bitstreams/ramtest-spare8-ch0-firmware \
  --threads 2 --out build/vivado/spare4gb-ddr1066
```

Use `--python` to select another environment with the exact pinned package
commits. Its `manifest.json` contains each implementation command, generated
core hashes and the freshly compiled CH0 firmware hash. Each candidate's
`source-check/manifest.json` records its prepared full-image source snapshot.
`tools/prepare_spare_speed_review.py` freezes the matching artifact collector.
`tools/run_spare_speed_queue.py` executes a hash-bound command schedule after
a specific service invocation exits. These tools do not automatically program
or qualify hardware.

`tools/prepare_spare_speed_crossings.py` prepares the exact-ID/clock collectors
against a candidate's expected artifact receipt. Its companion
`tools/run_spare_speed_postreview.py` waits for that receipt while checking the
producer's live service invocation, then runs CDC, Gray-pointer and selected
source-contract collection sequentially. A collection failure stops that
candidate's review and preserves its logs.

## Current local handles

- DDR800 compute build:
  `opentpu-spare4gb-core150-ddr800-20261017.service`;
  `build/fedora-vivado/spare-full-pcie-core150-ddr800-20261017/implementation/manifest.json`.
- Its artifact collector:
  `opentpu-spare4gb-core150-ddr800-review-20261017.service`;
  `build/checks/spare4gb-core150-ddr800-20261017/artifacts/manifest.json`.
- DDR1066 queue:
  `opentpu-spare4gb-ddr1066-queue-20261017.service`;
  `build/fedora-vivado/spare-full-pcie-ddr1066-20261017/queue/manifest.json`.
- Crossing evidence jobs:
  `opentpu-spare4gb-core150-ddr800-crossings-20261017.service`,
  `opentpu-spare4gb-core100-ddr1066-crossings-20261017.service`, and
  `opentpu-spare4gb-core150-ddr1066-crossings-20261017.service`.
  Each writes its coordinator receipt under
  `build/checks/spare4gb-<clock-and-DDR>-crossings-20261017/run/manifest.json`.

The existing [Mac handoff](spare_pcie_mac_bringup.md) applies to the flashed
100 MHz/DDR800 image only. Qualify that baseline first. Faster images remain
experimental and should not be represented as runtime-tested releases.

## Separate host preparation and calibration review

Image-specific Mac host helpers have been prepared for all three candidates.
They retain the one-command `lfm` workflow, but require their own exact build
ID, clock profile, reviewed package and firmware binding. The published
`c0172080` host guards remain unchanged. A host preparation is not an image
release and does not provide a bitstream or approve a CDC path.

To reproduce one preparation in a fresh output directory:

```bash
python3 tools/prepare_spare_speed_host.py --build-id c0172150 \
  --out build/handoffs/spare4gb-host-c0172150
```

The same command accepts `c0172161` and `c0172162`. Its
`host-preparation.json` records original/generated source hashes and the CLI
import and shell syntax checks. The generated helpers are kept in an isolated
tree until the matching reviewed package exists; the current Mac test should
continue using the existing baseline `tools/mac_spare_pcie_bringup.sh lfm`.

DDR1066 requires new CH0 firmware `c0172168`; DDR800 firmware bytes are not
reused. The offline review uses the existing three-case firmware/host CSR
trace comparison (ordinary calibration, per-bit framing and a missing-lane
window), against the generated DDR1066 initialization and CSR map:

```bash
python3 tools/review_spare_speed_firmware.py \
  --preparation build/vivado/spare4gb-ddr1066 \
  --out build/checks/spare4gb-ddr1066-firmware
```

This freezes the review input without changing the queued build sources.
Only an actual passing comparison can produce its model receipt. The future
DDR1066 package must bind that receipt, the firmware and all matched core
files to its exact build ID and bitstream hash. Host compilation compares
the C algorithm and CSR writes; RV32 execution, physical calibration and
memory reliability remain separate checks.

The October 17 run passed all three cases with exact reference CSR-write
traces: 531,219 writes for ordinary calibration, 531,315 for per-bit framing
and 449,823 for the expected missing-window rejection. The image-specific
receipt is
`build/checks/spare4gb-ddr1066-firmware-20261017/host-model-review.json`.
Firmware SHA-256 is
`0ade05b57f78c3a62a171ef179d0af46a519900067fc5378ed647376c127775a`.
This advances firmware preparation only; the FPGA images still need routing,
timing and CDC review before packaging, and physical qualification afterward.

## Exact-image package preparation

`tools/prepare_spare_speed_packager.py` freezes a separate packager for each
candidate without changing the baseline packager or creating an image release:

```bash
python3 tools/prepare_spare_speed_packager.py --build-id c0172150 \
  --host-tree build/handoffs/spare4gb-host-c0172150 \
  --out build/checks/spare4gb-packager-c0172150
```

The generated `package-speed-image.py --help` lists its inputs. Its numerical
timing/route, CRC, pads, CDC path coverage and Gray-skew gates are retained
from the baseline packager. Each candidate requires a new explicit routed
CDC disposition; the preparation never supplies one. The DDR800 candidate
uses the existing reviewed RAM-only firmware reference. DDR1066 packagers
additionally take `--firmware-model` pointing to the actual passing
`host-model-review.json`, `--reference-package` pointing to their DDR1066
preparation directory and `--firmware` pointing to its `calibration/` child.
They verify the generated core, firmware, model trace results and all input
hashes before creating an image-bound calibration bundle.

Preparations for all three candidates passed Python syntax and CLI import
checks. They remain unused until the actual routed evidence and its CDC
disposition pass. No candidate package or physical runtime result is implied.
