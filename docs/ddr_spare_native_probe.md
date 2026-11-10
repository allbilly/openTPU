# Spare-lane native partial-write diagnostic

This candidate closes the physical-access gap in the spare-lane experiment.
The raw BIST uses a separate crossbar client and cannot qualify the native
adapter's masked-write read/merge/write path.

## Candidate

- Build ID: `c0172070`, DDR800, 100 MHz controller clock.
- CH0 physical lanes: `0,1,2,3,4,5,8,7`, without ECC; CH1 retains ECC.
- CH0 native port B is dedicated to `NativeProbe`; its external inputs are
  ignored and its external ready/valid outputs are inactive.
- CH0 native port A and the serialized `NativePortsNoECC` adapter remain.
- New CSR bank `nativeprobe` is fixed at slot 17 (`0x8800` relative to the
  core CSR aperture). Generation checks that every original spare CSR retains
  its address and width. Use the generated `csr.csv`, not guessed offsets.
- The probe accepts one transaction at a time, snapshots address/data/mask,
  rejects starts while busy or disallowed, and keeps the returned data until
  the next accepted request. The sequence counter identifies that request.
- A write uses the requested 64-byte mask, then issues a read of the same
  address through the native adapter. `done` means that read returned; the
  host must independently compare the complete returned word.

The probe is allowed to start only when CH0 is calibrated and raw CH0 BIST is
idle. This is an admission check, not an ownership lock: the host must keep
raw BIST, calibration and other native traffic idle throughout the test.
In particular, a new raw BIST request during a partial write would bypass the
adapter's arbitration and invalidate the experiment.

## Build on Linux with Vivado

Use the same environment and prerequisites as the
[experimental diagnostic builds](ddr_lane6_experiment_builds.md). From the
repository root, choose fresh output directories:

```sh
build/fedora-openxc7/litedram-environment/venv/bin/python \
  tools/check_ramtest_native_probe.py \
  --out build/checks/native-probe-rmw-local

python3 tools/fedora_build_ramtest_variant.py \
  --variant spare8 --native-probe \
  --native-probe-model build/checks/native-probe-rmw-local/manifest.json \
  --out build/fedora-vivado/ramtest-spare-native-probe-local
```

Override `--vivado`, `--python`, `--rv-cc` and `--traffic-build` when their
locations differ. The builder freezes its generator and RTL sources, retains
the existing full phase-range timing constraints, and does not access hardware.
Do not program an unfinished or unreviewed implementation. A packaged image,
matching calibration firmware, CSR map and physical runner still need review.
macOS can consume those artifacts without Vivado after that review.

## Evidence and remaining gates

The October 17 model passed 96 CSR transactions through the actual spare
adapter, with randomized raw-command/data stalls. It checked 56 full physical
writes and 144 raw reads, including read/merge/write operations, zero masks,
single-byte masks, alternating masks and randomized masks. It rejected 97
starts while busy/disallowed and verified that changing host CSRs while busy
did not change the accepted transaction. This is model evidence only.

Before physical use:

1. Review generated wiring, existing CSR stability, firmware and bitstream
   identities, routed timing, phase constraints and artifact checksums.
2. Prepare the matching eight-lane CH0 calibration firmware and host identity
   checks. The old host runner deliberately accepts only `c0172060`.
3. Initialize each test word with a full native write. Verify all 64 bytes.
4. Apply each partial mask and independently merge expected bytes on the host.
   Compare all returned bytes, including preserved bytes and boundary bytes.
5. Include zero-mask writes, changed write order, multiple resident addresses,
   repeated initialization, and raw/full-system cross-checks where appropriate.

A passing small native test will not qualify all 4 GiB or restore CH0 ECC.

## Host protocol preparation

`tools/native_probe_protocol.py` supplies a bounded 1,160-operation schedule:
584 writes (560 partial and eight zero-mask), each with automatic native
readback, plus 576 explicit reads of resident data. Eight aligned addresses
include the original failure sites and the top of the 2 GiB CH0 range. Each
byte position is individually masked; both changed and preserved bytes are
checked. This is sparse native-access qualification, not full-capacity coverage.

The protocol waits for a new sequence number, checks accepted address/mask and
operation, detects rejected requests, and reads the held 512-bit response.
The independent byte-array reviewer checks every result and the complete
sequence. `tools/check_native_probe_protocol.py` passed the entire schedule
through the real `WordCsr` serializer using the generated map and an emulated
memory/probe. It checked sequence wrap, detected one injected bad byte,
rejected seven altered receipts, and rejected three invalid protocol responses.
This host check does not simulate physical DDR or replace the Migen model.

```sh
python3 tools/check_native_probe_protocol.py \
  --csr build/fedora-vivado/ramtest-spare-native-probe-local/core/csr.csv \
  --out build/checks/native-probe-host-local
```

The offline review queue checks base timing/pins/CDC, the full fine-phase
range, spare-pad routing, original CSR stability, and 12 generated native
connections. It also checks that the seven external CH0 port B inputs have
no consumers. Packaging requires that additional probe review and model.
The reviewed candidate and matched calibration firmware are packaged. Physical
qualification is recorded separately from those offline checks.

## Prepared physical runner

`tools/probe_ramtest_spare_native.py` requires reviewed image `c0172070` and
matched firmware `c0172078`. It checks package checksums and their review/model
bindings before opening hardware. On a fresh SRAM load it waits for CH1 startup
calibration, uploads and verifies all 4,096 firmware RAM words, calibrates CH0,
then runs the 1,160-operation native schedule. Native traffic generators stay
reset/paused. It records calibration, raw BIST epochs, phase counters, die
temperature, accepted transaction metadata and every complete response.

The runner's orchestration passed a separate test with emulated hardware APIs
and package preflight. That test exercised the calibration-to-transactions
sequence and all schedule operations; it does not qualify package validation,
JTAG, RV32 execution or physical DDR. The actual upload library and native RTL
have separate model evidence. `tools/review_ramtest_spare_native.py` archives
and independently checks the eventual physical result, including both changed
and preserved bytes.

Once the candidate and firmware packages are reviewed, the command is:

```sh
python3 tools/probe_ramtest_spare_native.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8-native-probe \
  --firmware bitstreams/ramtest-spare8-native-ch0-firmware \
  --host-model build/checks/native-probe-host-protocol-20261017/manifest.json \
  --out build/results/native-probe-1
```

Use `--preflight-only` to check packages without accessing hardware. A normal
run requires the freshly SRAM-loaded image and exclusive XVC service on port
3721; the runner itself does not program the FPGA or write flash. The current
hardware queue performs loading only after the previous owner's reviewed run
has ended and its XVC child has stopped. Do not run this command concurrently
with that queue. Host-model source paths in the current local receipt must be
regenerated for a relocated checkout before use there.

## Full-range follow-up on the same initialization

After the native test has passed independent review, the raw BIST can cover
both complete 2 GiB address ranges without reloading or recalibrating. The
reader verifies the same image, firmware, calibration mailbox and phase values,
and requires the completed 1,160-operation native sequence. It refuses to run
if native generators or another BIST are active.

The schedule has 4,096 chunks of 4 MiB: write both channels completely, then
read both in descending address order; repeat with complementary seeds. It
pauses at least 200 ms between chunks and stops at the first failing chunk.
This reduces average activity but does not bound peak current. The first raw
word and whole-chunk error counters are recorded separately, so a clean first
word cannot hide an error later in the chunk.

With exclusive XVC ownership and the reviewed native initialization retained:

```sh
python3 tools/probe_ramtest_spare_range.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8-native-probe \
  --firmware bitstreams/ramtest-spare8-native-ch0-firmware \
  --native-review docs/data/ddr_spare_ch0_native_partial_20261017.json \
  --model build/checks/spare-full-range-20261017/manifest.json \
  --gap-ms 200 --out build/results/spare-range-1
```

Use `--preflight-only` with a fresh output directory for a check without hardware
access. The dated prerequisite receipt must exist and pass; a prepared reader
is not evidence of a completed native test. Do not execute this command while
the automated queue owns the card.

The local `opentpu-spare-range-sequence-20261017.service` waits for the exact
native v2 invocation and a zero-error archived review. It checks source/model
hashes and the stopped previous XVC child, opens one XVC service, runs coverage,
closes that service, then invokes the independent range reviewer. It neither
loads another image nor requests calibration. A bad native result prevents
launch; a bad range chunk preserves the failing state for investigation.

Preparation includes frozen BIST RTL checks, independent coverage/receipt checks,
and `tools/check_spare_range_runner.py` orchestration checks for complete coverage,
a later-word error, and calibration mismatch. Emulated observations in those
checks are fixtures, not physical results.

Raw coverage bypasses the native adapter and CH1 ECC. It destroys valid CH1 ECC
contents; reinitialize through the proper native path before subsequent ECC
tests. Passing coverage does not establish cold-start repeatability, sustained
load, supply adequacy, or full OpenTPU operation. CH0 remains non-ECC.

## Full OpenTPU integration candidate

`tools/prepare_spare_pcie.py` prepares build `c0172080`: the full OpenTPU
compute design, XDMA Gen2 x8, 100 MHz compute, DDR800 and both 2 GiB channels.
CH0 uses the non-ECC spare adapter; CH1 retains ECC. This is a separate
experimental profile. Existing release validators and host transports must
continue rejecting it until dedicated support and qualification are complete.

The input is the reviewed **non-probe** `c0172060` core: it retains both
external native ports, unlike `c0172070`, which dedicates CH0 port B to its
diagnostic probe. The preparer verifies the package and two-port adapter model,
copies the core, and increases its eight cross-phase setup/hold constraints
from 1.0 ns to the full 1.25 ns fine-phase envelope. It preserves the complete
accelerator RTL; only three identification registers are added to its snapshot:

| Byte address | Value | Meaning |
|---|---|---|
| `0x5c` | `0x10000203` | 4096 MiB, memory ABI 2, both physical channels |
| `0x60` | `0x78543210` | CH0 physical lane index per logical byte, least-significant nibble first |
| `0x64` | `0x00000002` | ECC on CH1 only |

Prepare and build in a fresh directory:

```sh
python3 tools/prepare_spare_pcie.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8 \
  --firmware bitstreams/ramtest-spare8-ch0-firmware \
  --adapter-model build/checks/spare-native-rmw-20261017/manifest.json \
  --out build/spare-full-pcie-local

python3 build/spare-full-pcie-local/build-spare-pcie.py \
  --core build/spare-full-pcie-local/core \
  --core-mhz 100 --build-id c0172080 --threads 2 \
  --out build/spare-full-pcie-local/implementation
```

Preparation exercises source generation without running synthesis. The second
command runs Vivado and requires the same configured toolchain as the existing
PCIe builder. Timing, route and DRC gates precede bitstream generation. Dedicated
full-image artifact review and physical tests remain mandatory afterward.

At startup this core automatically calibrates CH1 only. CH0 requires the
eight-lane calibration firmware or equivalent verified host calibration. The
copied RAM-only firmware package is reference evidence; its original image
binding does **not** authorize the existing RAM-only loader to open the full
OpenTPU image. A new binding/host loader, CH1 ECC initialization, and native
memory qualification are required before inference. This candidate does not
restore CH0 ECC and is not automatically loaded by the build job.

### Artifact review and host preparation

The dedicated offline collector can follow the build:

```sh
python3 tools/collect_spare_pcie_review_v3.py \
  --preparation build/spare-full-pcie-local \
  --out build/checks/spare-full-pcie-local
```

For a running background build, add `--wait-unit UNIT --invocation ID` using
the exact systemd invocation. The collector preserves a distinct status:
`SPARE_PCIE_ARTIFACT_CHECKS_PASS_CDC_AND_RUNTIME_PENDING`. It does not package,
program, or declare the image physically qualified. It requires fresh CDC and
gray-pointer review before any final image package can be accepted by the host.

Collect the additional routed evidence in fresh directories:

```sh
python3 tools/collect_spare_pcie_cdc.py \
  --build build/spare-full-pcie-local/implementation \
  --qualification build/checks/spare-full-pcie-local/manifest.json \
  --reference-cdc bitstreams/dual-pcie-4gb-ddr800-reset/evidence/oob-cdc.rpt.gz \
  --out build/checks/spare-full-pcie-local-crossings

python3 tools/check_spare_pcie_gray.py \
  --qualification build/checks/spare-full-pcie-local/manifest.json \
  --out build/checks/spare-full-pcie-local-gray
```

These collectors preserve the checks used for the packaged image; their only
change from the archived launch scripts removes a machine-specific import
path. Collection alone does not approve clock-domain crossings.

Compare the selected source contracts, inspect the reports, and bind the exact
matching inventory to its disposition:

```sh
python3 tools/collect_spare_cdc_source.py \
  --build build/spare-full-pcie-local/implementation \
  --reference bitstreams/dual-pcie-4gb-ddr800-reset \
  --out build/checks/spare-full-pcie-local-source.json

python3 tools/review_spare_pcie_cdc.py \
  --build build/spare-full-pcie-local/implementation \
  --qualification build/checks/spare-full-pcie-local/manifest.json \
  --collection build/checks/spare-full-pcie-local-crossings/manifest.json \
  --gray build/checks/spare-full-pcie-local-gray/manifest.json \
  --source build/checks/spare-full-pcie-local-source.json \
  --reference bitstreams/dual-pcie-4gb-ddr800-reset \
  --out build/checks/spare-full-pcie-local-cdc-review.json
```

Any changed CDC rows, fan-in or clock-domain facts stop this gate and require
review of the new implementation. Matching selected source blocks is not
formal equivalence. Use the resulting paths with the package command below.

`opentpu.host.spare_pcie` supplies dedicated `SparePcieProfile`,
`SpareChestnutTransport` and `SpareXdmaTransport` classes. They check the new
identity registers, both 2 GiB limits, CH0 ECC disabled and CH1 ECC enabled,
calibration readiness, and idle raw BIST before memory operations. Existing
CH1 and dual-ECC transports keep their old identity/guard requirements.

The new package status, bitstream binding and required CDC/gray reviews are
mandatory before a transport opens a device. The local
`bitstreams/spare-pcie-4gb-ddr800/` package passed these gates on October 17.
Firmware binding/loading and physical qualification remain separate steps.

The `scrub()` implementation is destructive: it clears the initialization
marker, writes zero to both whole channels in 4 MiB chunks, then verifies both,
pausing 200 ms between operations. CH0 uses eight lane counters and CH1 nine.
It stops on errors without clearing their evidence. Only the enclosing board
flow may mark initialization complete after successful return. Raw zero
verification still needs a subsequent native ECC/data check.

Preparation tests, without hardware access:

```sh
python3 -m pytest -q tests/test_spare_pcie.py tests/test_dual_pcie.py
```

### Full-image CH0 calibration handoff

`tools/run_spare_pcie_calibration.py` prepares the explicit binding between a
reviewed `c0172080` full-image package and the already reviewed `c0172068`
eight-lane firmware. Firmware identity and FPGA image identity are different
fields. The reference firmware's original binding remains unchanged.

Before opening a device, the helper requires the full-image package's artifact,
CDC and gray-pointer reviews, verifies the original RAM-only package/firmware,
and compares five core files byte for byte: controller Verilog, CSR map, both
PHY initialization descriptions and identifier ROM. The new full-image XDC
has a stricter 1.25 ns constraint and is reviewed with the full image; identical
controller files do not qualify its new placement/routing.

Once a reviewed full-image package exists, check the handoff first:

```sh
python3 tools/run_spare_pcie_calibration.py \
  --package bitstreams/dual-pcie-4gb-spare8 \
  --reference-package bitstreams/ramtest-litedram-ddr800-spare8 \
  --firmware bitstreams/ramtest-spare8-ch0-firmware \
  --preflight-only --out build/results/spare-pcie-calibration-preflight
```

`bitstreams/dual-pcie-4gb-spare8` is the intended package destination, **not
an existing reviewed package at this stage**. For actual calibration, use a
fresh SRAM-loaded full image, a fresh output directory, remove
`--preflight-only`, and select `--transport xdma --dev /dev/xdma0` or
`--transport chestnut` according to the connected PCIe path. A JTAG programmer
alone cannot access this full PCIe image's CSRs.

The helper waits for the original CH1-only startup firmware, requires no prior
native memory traffic and an idle accelerator/BIST, clears the initialization
marker, uploads and reads back all 4,096 firmware RAM words, and calibrates CH0
only. It records both mailboxes, temperature, CH0's eight lane settings, native
counters and CH1 phase preservation. It never clears ECC counters or starts
inference. Calibration success leaves memory explicitly uninitialized; whole
memory initialization and native data/ECC qualification must follow.

Its host-sequence checks cover successful CH0-only calibration, active BIST,
running accelerator, prior native traffic, failed calibration, changed CH1
phase, and mismatched CSR bindings. The combined suite passed 66 checks using
emulated APIs; physical PCIe calibration remains pending.

## Retention after full-range coverage

The retention follow-up preserves the second full-range pass's complementary
address pattern. It requires a reviewed, error-free complete range result and
the same bitstream, firmware, calibration mailbox, phase settings and BIST
epochs. It issues no data writes or calibration request.

After a 60-second interval with normal controller refresh left enabled, it
reads both complete 2 GiB channels in 4 MiB chunks with 200 ms gaps. It stops
at the first bad chunk and records first-word capture separately from whole-
chunk error counters. This tests retained contents with normal refresh; it is
not a test with refresh disabled and does not measure a DRAM cell retention
limit.

```sh
python3 tools/probe_ramtest_spare_retention.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8-native-probe \
  --firmware bitstreams/ramtest-spare8-native-ch0-firmware \
  --range-review docs/data/ddr_spare_ch0_full_range_20261017.json \
  --model build/checks/spare-retention-20261017/manifest.json \
  --hold-seconds 60 --gap-ms 200 --out build/results/spare-retention-1
```

Use a fresh output directory and exclusive XVC ownership; do not run alongside
the automated queue. `--preflight-only` checks prerequisites without hardware.
The local `opentpu-spare-retention-sequence-20261017.service` waits for the full
range review, checks the previous XVC child has stopped, runs this procedure,
then closes XVC before the independent reviewer archives its result.

`tools/check_spare_retention.py` checked the exact resident pattern schedule,
full and failed-prefix receipts, eight malformed cases, and emulated complete,
stop-on-error and changed-epoch reader sequences. Its fixtures are not physical
retention results. Existing bitstream/BIST model evidence remains required.

## Normal eight-lane control build

The `c0172090` control keeps the spare design's 64-bit non-ECC CH0 datapath,
but uses physical lanes 0–7 and disables lane 8. This comparison helps separate
the effect of replacing physical lane 6 from removing the ninth lane/ECC path.
It does not restore ECC. Placement, routing and calibration still differ and
must be recorded for each physical run.

```sh
python3 tools/prepare_ramtest_normal8.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8 \
  --firmware bitstreams/ramtest-spare8-ch0-firmware \
  --out build/normal8-control-local

python3 build/normal8-control-local/source/implementation-builder.py \
  --core build/normal8-control-local/core \
  --traffic-build build/fedora-vivado/ram-only-mig-ddr800-address-20261016-v5 \
  --build-id c0172090 --capture-first-read \
  --capture-model-review bitstreams/ramtest-litedram-ddr800-runtime-pattern/evidence/source/read-capture-model.json \
  --runtime-pattern-reset-fix \
  --pattern-restart-model-review bitstreams/ramtest-litedram-ddr800-runtime-pattern/evidence/source/pattern-restart-model.json \
  --out build/normal8-control-local/implementation
```

The traffic donor is an existing preparation artifact with frozen vendor
traffic sources; supply its equivalent path when rebuilding elsewhere. The
generated `build.command.json` records the exact local invocation. Preparation
checks package integrity, the reversible 20-pad-reference change, all 162 pad
groups, unchanged CSR/PHY/ROM files and the new strict `normal8` profile.
Existing release/variant validators remain unchanged.

The core's embedded CH1-only startup firmware still identifies itself as
`c0172060`; the FPGA diagnostic build ID is `c0172090`. A distinct reviewed
image/calibration binding is required before reusing the eight-lane CH0
firmware. Do not use the existing spare loader against the control image.
Independent artifact review, package creation and physical testing remain
pending.

### Normal-lane package and calibration handoff

`tools/package_ramtest_normal8.py` packages only a completed normal-lane base,
full-phase timing and routed-pad review. `tools/normal8_package.py` binds the
image, unchanged internal core (verified by reversing the pad swap), CSR map,
eight-lane PHY configuration and original firmware evidence. The original
spare-image guard remains unchanged.

The local `opentpu-normal8-control-package-20261017.service` waits for the
identified review service, then packages the control and runs this read-only
preflight. It never opens hardware or programs the card:

```sh
python3 tools/probe_ramtest_normal8_calibration.py \
  --package bitstreams/ramtest-litedram-ddr800-normal8-control \
  --preflight-only --out build/results/normal8-preflight-1
```

After the reviewed control image has been loaded to SRAM and exclusive XVC
ownership has been established, omit `--preflight-only` and choose a fresh
output directory to calibrate CH0. The tool requires FPGA ID `c0172090`,
startup firmware `c0172060`, idle native generators, completed CH1 calibration,
and uncalibrated CH0. It uploads and verifies 4,096 volatile firmware words,
then requests CH0-only calibration with firmware `c0172068`. CH1's phase must
remain unchanged. Calibration destroys disposable CH0 contents; it does not
qualify memory, initialize ECC contents or establish an ECC repair.

Seven emulated host checks cover successful and failed calibration, wrong
FPGA/startup IDs, active traffic, incomplete upload and changed CH1 phase.
They do not execute the firmware or validate physical DDR. Package creation,
physical control calibration and the matched history experiment remain pending.

### Matched normal-lane history and automatic handoff

`tools/probe_ramtest_normal8_history.py` uses the same 14 writes and 720 reads
as the spare history experiment (640 CH0 reads, 80 CH1 reads), with the same
addresses, rotating beat signatures and operation order. It requires the
reviewed control calibration, exact live build ID, unchanged mailbox/phase,
and idle native generators. The reader does not recalibrate. Its separate
reviewer maps logical lane 6 errors to physical lane 6, not physical lane 8.

```sh
python3 tools/probe_ramtest_normal8_history.py \
  --package bitstreams/ramtest-litedram-ddr800-normal8-control \
  --calibration-review docs/data/ddr_normal8_ch0_calibration_20261017.json \
  --model build/checks/spare-raw-capture-20261017/manifest.json \
  --out build/results/normal8-history-1
```

This command requires exclusive XVC ownership and a matching calibration
receipt for the currently loaded image. Do not run it beside an automated
session. Raw writes invalidate normal ECC contents.

The local `opentpu-normal8-control-sequence-20261017.service` is queued to:

1. Wait for reviewed, error-free complete retention and the approved control
   package. Preserve a failed predecessor's FPGA state instead of reloading.
2. Confirm the old XVC child stopped and the cable endpoint is unowned.
3. SRAM-load the exact reviewed control; upload and verify volatile CH0
   calibration firmware; archive the calibration result.
4. Run the matched history only if calibration succeeded, then independently
   review and archive every transaction. Calibration failure is recorded and
   stops progression without another reload.

The orchestrator is `tools/run_normal8_control_sequence.py`; its `--help`
lists explicit package/job/model/loader paths and predecessor service IDs.
It issues no flash writes. The combined calibration/history host tests passed
11 emulated cases; the history reviewer also rejects seven malformed-record
cases and checks physical-lane identity. Those checks are preparation evidence,
not a physical control result. New routing/calibration remain comparison
variables even with the exact same internal logic and operation schedule.

## Full PCIe package gate

`tools/package_spare_pcie.py` creates a local experimental package only after
artifact qualification, an explicit CDC disposition and routed gray-pointer
checks all refer to the exact `c0172080` image. It checks every non-information
CDC row is covered once by a reasoned disposition, all evidence hashes,
internal timing/routing, phase/pad review evidence and preserved core files.
The host's `SparePcieProfile` then verifies the resulting package before it is
renamed into place. Report collection alone does not satisfy this gate.

After the fresh reports have been inspected and the CDC review exists:

```sh
python3 tools/package_spare_pcie.py \
  --build build/fedora-vivado/spare-full-pcie-20261017/implementation \
  --qualification build/checks/spare-full-pcie-review-v3-20261017/manifest.json \
  --cdc-review build/checks/spare-full-pcie-package-20261017/cdc-review.json \
  --reference-package bitstreams/ramtest-litedram-ddr800-spare8 \
  --firmware bitstreams/ramtest-spare8-ch0-firmware \
  --out bitstreams/spare-pcie-4gb-ddr800
```

Use the Python environment with the host dependencies (including NumPy).
The command records the completed local packaging step; use a fresh output
directory when repeating it. The output includes `otpu.bit`, matched core files,
CH0 firmware and review evidence; it excludes flash programming files. Keep
the original spare RAM-only reference package alongside it for the calibration
binding. Eleven synthetic receipt checks passed, including rejection of a
collection-only record, missing/duplicate CDC dispositions, a changed image,
negative gray-pointer skew, changed evidence and an unsupported physical-pass
claim. Physical PCIe DMA, native memory/ECC, matmul and LFM remain pending.

The packaged image is `c0172080`, SHA256
`19730b4708653c428cf388999c4d49b7437648dd27d358028999ee98c380a425`.
All 84 manifest-listed files were checked after packaging, and the actual
package plus bundled calibration passed the host's preflight-only command.
These checks did not access or program hardware. The 116 non-information CDC
rows, calibration/reset fan-in, and Gray synchronizer facts matched the
reviewed integration contracts; all 49 skew checks passed (minimum +2.878 ns).
The global management reset remains an excluded operation. Preserved earlier
artifact reports can say `cdc_review: PENDING`; the final disposition is
`evidence/cdc-review.json` and is separately bound by the package manifest.

## Full spare-image runtime qualification

`tools/run_spare_pcie_lfm2.py` is separate from the dual-ECC runner. It accepts
only the reviewed `c0172080` package and the spare transport identity. For
memory/inference it also requires the successful calibration observation from
`tools/run_spare_pcie_calibration.py`, with exact package/firmware/core hashes
and matching live mailbox, phase settings and readiness on both channels.
The CH0-only firmware leaves CH1 idle in its mailbox; CH1's earlier successful
startup calibration is preserved in the receipt. It must not be decoded as a
new combined nine-lane calibration result.

Once the full image has been reviewed, loaded to SRAM, connected through PCIe,
and calibrated using the earlier procedure:

```sh
python3 tools/run_spare_pcie_lfm2.py \
  --package bitstreams/spare-pcie-4gb-ddr800 \
  --transport chestnut --stage identity \
  --out build/results/spare-pcie-identity-1

python3 tools/run_spare_pcie_lfm2.py \
  --package bitstreams/spare-pcie-4gb-ddr800 \
  --transport chestnut --stage memory \
  --calibration-receipt build/results/spare-pcie-calibration-1/manifest.json \
  --out build/results/spare-pcie-memory-1
```

Use `--transport xdma --dev /dev/xdma0` for an established Linux XDMA endpoint.
JTAG alone is insufficient. This tool never programs, recalibrates, clears ECC
counters or writes flash. Use a fresh output directory and exclusive card
ownership; memory/inference stages overwrite both channels.

The memory stage performs two complementary address-sensitive raw passes over
both complete 2 GiB channels, using serialized 4 MiB chunks with 200 ms gaps.
It records each raw result before checking it, uses eight CH0 counters and
nine CH1 counters, and stops on the first error. Average-duty pauses do not
bound peak supply demand. Whole-memory zero initialization follows to create
valid native CH1 ECC contents. A full logical-range native read sweep then
checks execution/coverage counts; only the final 16 KiB native payload is
compared. Six channel-distinct DMA sentinels cover base, upper-half and top
boundaries. This is not exhaustive native payload or partial-write coverage.

After memory qualification, use `--stage inference --model lfm2` with the same
calibration receipt and a fresh output directory. This repeats the memory
stage, then checks physical matmul and exact LFM2 tokens against the existing
ISA reference. Keep the checkpoint and compatible NumPy/PyTorch/Transformers/
safetensors environment available. The pass status retains repeatability as
pending. CH0 remains non-ECC throughout, and no dual-ECC repair is claimed.

Fourteen emulated checks cover live calibration binding, full range/widths,
stop-on-error, zero-before-native ordering, bad native coverage counts and
cleanup failure. They do not establish physical DMA, matmul or LFM execution.
The current sole 12 V / 2 A supply remains an unresolved control; full-image
sustained runtime and the faster compute candidate are not automatically
scheduled by these preparation scripts.

### Normal-lane sparse address follow-up

`tools/probe_ramtest_normal8_sparse.py` reuses the spare schedule's 128 selected
addresses per channel, from zero through `0x7fffffc0`. Its 512 writes and 1,536
reads use distinct address/channel/generation signatures, with lane-6 source
vectors distinct under rotation. It covers 8 KiB of unique locations per
channel distributed across the address space, not the whole capacity.

```sh
python3 tools/probe_ramtest_normal8_sparse.py \
  --package bitstreams/ramtest-litedram-ddr800-normal8-control \
  --calibration-review docs/data/ddr_normal8_ch0_calibration_20261017.json \
  --model build/checks/spare-raw-capture-20261017/manifest.json \
  --out build/results/normal8-sparse-1
```

Use exclusive XVC ownership and the same reviewed initialization. The local
`opentpu-normal8-sparse-20261017.service` waits for an error-free reviewed
control history result and stopped prior XVC child, then runs this schedule
without reload or calibration. `opentpu-normal8-sparse-review-20261017.service`
independently verifies and archives all rows afterward. Four emulated reader
checks and seven malformed-record rejection cases passed before queueing;
those fixtures are not physical results.
