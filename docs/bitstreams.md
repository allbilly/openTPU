# Bitstream locations and build differences

Current disposition: [HANDOFF.md](../HANDOFF.md), October 22, 2026. The c01848
runtime-clock effort was abandoned; no continuation is scheduled. The retained
fixed-clock images [c0182800](mac_c0182800.md) (100 MHz / DDR800) and
[c0182863](mac_c0182863.md) (148.837 MHz / DDR1066.667) have separate passing Mac
LFM and Qwen receipts. Both provide 4 GiB and JTAG/PCIe runtime access, using
CH0 lanes `0,1,2,3,4,5,8,7` without ECC and CH1 with ECC. The handoff did not
recheck the card's physical identity or ownership.

The older PCIe-only c0172300 failed Mac LFM with 3,161 CH0 program-readback
word mismatches; see [its failure record](mac_c0172300.md). c0182301 was retired
and c0172462 was rejected for a shared-host reset defect. They are not pending
builds or active hardware candidates.

## Tested builds and outstanding tests

Evidence reviewed October 23, 2026. The table separates completed implementation,
offline review, local SRAM execution, permanent programming and Mac workloads.
The physical results were recorded on October 18–19; this documentation review
did not access the card or establish its current configured image. **Pending
means missing acceptance evidence, not a running or scheduled test.**

All five retained images below contain the full accelerator, **4 GiB**, both
**JTAG USER2 and PCIe memory/control**, and a 250 MHz host clock independent of
PCIe. CH0 uses physical lanes `[0,1,2,3,4,5,8,7]` with ECC disabled; CH1 retains
ECC. DDR rates below are MT/s, not DDR clock frequencies. Each image has its own
completed build, offline review and package; results do not transfer between IDs.

| Build | Compute / DDR rate | What changed | Completed physical evidence | Outstanding tests / disposition |
| --- | --- | --- | --- | --- |
| **[c0182800](mac_c0182800.md)** | 100 MHz / 800 MT/s | Baseline CH0 shared-response repair and registered host reset; CH1 automatic calibration, matching host calibration for CH0 | Local JTAG SRAM/identity, full-memory initialization, program fetch, matmul, exact TinyStories and native-read benchmark; permanent program, independent verify and flash boot; Mac LFM230M and Qwen3.5-2B exact ISA comparisons | Retained tested fallback. Cold/warm repeatability, broader PCIe/reset reliability and controlled comparisons remain open |
| **[c0182863](mac_c0182863.md)** | 148.837209 MHz / 1066.667 MT/s | Faster compute/DDR and quantizer predicate timing correction; same manual CH0/automatic CH1 calibration | Local JTAG SRAM, initialization, program fetch, matmul, exact TinyStories and native-read benchmark; permanent program, independent verify and flash boot; Mac LFM230M and Qwen3.5-2B exact ISA comparisons | Retained tested faster image. Cold/warm repeats, initialization-pause comparison, controlled host/wall-decode profiling and the modeled corner cases below remain open |
| **[c0182600](mac_c0182600.md)** | 100 MHz / 800 MT/s | Both-channel automatic eight-/nine-lane calibration using embedded firmware `c0172608`; corrected CH0 path and both interfaces retained | Local SRAM/startup, full initialization, program fetch, matmul, model readback, eight ISA-exact TinyStories tokens, public JTAG runtime postflight and native-read benchmark | **Mac PCIe/LFM/Qwen acceptance and repeatability pending.** Permanent programming/boot not performed; retain as automatic-startup fallback |
| **[c0182663](mac_c0182663.md)** | 148.837209 MHz / 1066.667 MT/s | Faster automatic-startup successor with embedded firmware `c0172668` and quantizer timing correction | Local SRAM/startup, full initialization, program fetch, matmul, model readback, eight ISA-exact TinyStories tokens, public JTAG runtime postflight and native-read benchmark | **Mac PCIe/LFM/Qwen acceptance and repeatability pending.** Permanent programming/boot not performed; this was the selected automatic-startup Mac candidate |
| **c0182461** | 100 MHz / 1066.667 MT/s | DDR-rate comparison at baseline compute speed; CH1 automatic calibration and matching host calibration for CH0 | Local JTAG SRAM/identity, initialization, program fetch, matmul, exact TinyStories and native-read benchmark | **Mac acceptance and repeatability pending.** Optional comparison only; no recorded permanent programming/boot |

Automatic calibration in c0182600/c0182663 does not perform the entire memory
initializer or remove its 2,048 default 200 ms host pauses. The c0182863 shorter-
pause option and host profiler are software preparation; no improved physical
startup or wall-decode result is claimed. The two automatic-startup Mac guides
document prepared local workflows. Their matching host tools and runtime bundles
are excluded from this documentation change and remain unpublished; those files
must be reviewed and published separately before Mac use. Pulling these guides
alone does not provide a runnable automatic-startup handoff.
For c0182600, the completed 2,048-operation initialization is recorded but the
individual chunk counters were not retained; c0182663 retains those counters.
Their public-runtime postflights checked live identity/startup/ECC; the trained
TinyStories results belong to the frozen test hosts, not a separate inference
run through the newly exported public tools. Full-range arbitrary-payload and
retention qualification remain open for these exact integrated images.

The tested workload passes are bounded evidence. A later simulation of the
**exact c0182863 compiled memory bridge** reproduced two other corner cases:
simultaneous accepts publish a Gray counter change from 0 to 3, and a six-bit
pending count wraps at 64 and can release reset with commands still queued.
These are source/module-simulation findings, **not a newly observed Mac failure**;
the earlier LFM/Qwen passes remain valid for their tested runs. The unchanged
c0182863 bitstream does not contain a correction for these cases. See the
[local decision audit](../build/checks/runtime-c0184810-continuation-decision-audit-20261021-v1/decision-evidence.json)
and [exact compiled-source witnesses](../build/checks/runtime-c0184810-continuation-decision-audit-20261021-v1/baseline-corner-cases.json).
External DDR pad timing and broader physical reliability remain unqualified;
offline timing/CDC passes are limited to their recorded scopes.

### Exact retained image identities

The files are local artifacts under `bitstreams/spare-dual-host-4gb-<build>/otpu.bit`.
Their bytes, sizes and package-manifest hashes were checked on October 23.
These are **bitstream SHA256** values, not source fingerprints or checkpoint hashes.

| Build | Bitstream SHA256 |
| --- | --- |
| c0182800 | `df2521d80de1d69ea4ca758821dc67a814b95d67ac851b78727c9154a3104bf2` |
| c0182863 | `03b513a44544009afff9dfb82515bf84c5df84ac6a63673a0882308ce8a323ae` |
| c0182600 | `52ac73cc9e791661d3d2cb3a1c65ffaf872647031c5857c8e43541b848561f6b` |
| c0182663 | `a1571e696d510d4b19adc59534872ceef48398036134d817f00b6b2ebb232acc` |
| c0182461 | `0fc2b933ddd3fd0378941464ae6c8d91e356fb1bb90bf9e446ded6f90817007b` |

### Evidence and exclusions

The small tracked [c0182800 local validation](../runtime/c0182800/local-validation.json)
and [c0182863 local validation](../runtime/c0182863/local-validation.json) preserve
their SRAM checks. The [c0182800 Mac record](data/spare_pcie_benchmark_20261018.json)
and [c0182863 Mac record](data/spare_pcie_benchmark_c0182863_20261018.json) record
the later LFM/Qwen results; raw Mac logs remain on the test host. Packaging-time
`PHYSICAL_PENDING` fields and older programming metadata are preserved historical
receipts, not the latest workload disposition. Use the later same-image evidence
above rather than rewriting those hashed originals.
Permanent [c0182800 program/verify/boot](../build/hardware/flash-c0182800-20261018/closure.json)
and [c0182863 program/verify/boot](../build/hardware/flash-c0182863-20261018T125114Z/closure.json)
have their own completed receipts. These boots were requested through JTAG;
they do not establish cold power-cycle repeatability.

The automatic-startup guides link their local acceptance and benchmark receipts.
For c0182461, retain the [final offline disposition](../build/checks/spare-shared-candidate-final-c0182461-20261018-v1/worker/manifest.json),
[SRAM receipt](../build/hardware/sram-c0182461-20261018-v1/manifest.json),
[TinyStories receipt](../build/hardware/tinystories-c0182461-20261018-v1/manifest.json)
and [native-read receipt](../build/hardware/native-bandwidth-c0182461-20261018-v1/manifest.json).
Links under `build/` describe preserved local evidence, not files supplied by Git.

The **c01848 runtime-clock series is abandoned**, not pending hardware testing.
c0184811 completed implementation but failed setup timing (WNS -0.182 ns,
659 failing endpoints); it produced no eligible bitstream. c0184812 passed source
checks but never entered placement/routing and has no bitstream. Earlier
single-interface images, canceled pipeline candidates and rejected timing/CDC
variants below are historical records, not alternatives in the pending-test table.

| Rejected build attempts | Recorded blocker | Test disposition |
| --- | --- | --- |
| [c0182450](../build/checks/c0182450-setup-finding-20261018/manifest.json), [c0182862](../build/checks/c0182862-setup-rejection-20261018/manifest.json), [c0182662](../build/checks/c0182662-final-timing-rejection-20261019-v1/manifest.json) | Final setup timing failed | No bitstream produced; not awaiting physical tests |
| [c0183120](../build/checks/c0183120-setup-rejection-20261018/manifest.json), [c0183130](../build/checks/c0183130-setup-rejection-20261018/manifest.json), [c0183133](../build/checks/c0183133-setup-rejection-20261018/manifest.json) | Higher-rate attempts failed final setup timing | No bitstream produced; not awaiting physical tests |
| [c0183160](../build/checks/c0183160-clock-and-timing-rejection-20261018/manifest.json) | MMCM VCO limit, setup and pulse-width violations | No bitstream produced; not awaiting physical tests |

## Historical inventory and local artifacts

The remaining inventory records October 15–17 experiments. Its pending tests,
queues and loading/rebuild commands describe that historical scope, not current
work. Several linked packages and raw receipts exist only on the original build
host; a Git pull does not retrieve them. New images must satisfy the
[combined-interface requirement](../AGENTS.md#mandatory-interfaces-in-every-bitstream).
Legacy PCIe-only and RAM-only implementation entrypoints reject new builds;
their retained preparation/review helpers do not admit an implementation.

All paths below are repository-relative. The original build-output inventory
contains 22 `.bit`/`.mcs` files, including older experiments and bundled loader
helpers. Its exact byte sizes and hashes are in [bitstreams.tsv](bitstreams.tsv).
Previously committed release files remain historical; new generated bitstreams,
netlists and large build outputs must remain local.

For `bitstreams/ch1-pcie-2gb-ch0-reset/`, the publishable files are historical
metadata, small runtime files and review evidence. The 12,469,503-byte `otpu.bit`
and 8,177,677-byte `core/otpu_litedram.v` are retained locally and excluded from
Git. The original `manifest.json`, `SHA256SUMS` and package README are preserved
byte for byte, including their descriptions of the original complete local
package. Consequently, its full checksum command requires those local artifacts
and is not a fresh-clone check. Their SHA256 values are respectively
`40173515ee16b6b0b127a856139b023529e6dbf53ab1e301b1a3002847df62fc` and
`d6e2b3ad975da064a1941bf1a077e914e09859104b5d1be0a55fa837ebcd3508`.
The frozen package README/build snapshots retain the historical reconstruction
inputs and commands; the PCIe-only implementation path is now retired. Preserve
those originals when examining the evidence. This package has no JTAG runtime
memory/control interface and is not selected for programming or a new rebuild.

Mac runtime handoffs for the retained fixed-clock images use the small tracked
host/configuration files linked above; transferring a bitstream or local build
package is not a prerequisite for a card already carrying the matching image.

## Tracked PCIe 2 GiB release

The separate [CH0 diagnostic CPU firmware](../bitstreams/ch0-diagnostics/)
is documented in [the DDR handoff](ddr_calibration_review.md#portable-calibration-firmware-follow-ups).
Those `.bin` files load through calibration CSRs inside the existing design;
they are not FPGA programming images.

The current CH1-only PCIe release is included in
[`bitstreams/ch1-pcie-2gb/`](../bitstreams/ch1-pcie-2gb/). A clone of this branch
contains the built images and matching DDR800 runtime data:

- [`otpu.bit`](../bitstreams/ch1-pcie-2gb/otpu.bit): load the FPGA's volatile SRAM over JTAG.
- [`otpu.mcs`](../bitstreams/ch1-pcie-2gb/otpu.mcs): the same design in BPI x16 NOR programming format.
- [`core/`](../bitstreams/ch1-pcie-2gb/core/): matched calibration tables and the files checked by `openxc7-profile.json`.
- [`manifest.json`](../bitstreams/ch1-pcie-2gb/manifest.json): target, memory mapping, file hashes and measured qualification scope.
- [`evidence/`](../bitstreams/ch1-pcie-2gb/evidence/): preserved offline review and flash-programming receipts.

Verify the release on macOS before selecting an image:

```sh
cd bitstreams/ch1-pcie-2gb
shasum -a 256 -c SHA256SUMS
```

These images were built with Vivado on Fedora. Loading an existing `.bit` on
macOS needs a working JTAG programmer with DLC10/XC7K480T support, rather than
a local Vivado installation. Confirm the expected IDCODE `0x23751093` and
successful configuration completion. A BPI NOR write additionally requires
support for the actual board flash and its x16 interface; successful `.bit`
SRAM loading alone does not establish that support. The Chestnut PCIe DMA
transport is the runtime connection, not a JTAG programmer.

Select the release's `core/` as the transport's `calibration_data`; the
repository's default tables are DDR1066 and differ from this DDR800 image.
Both logical memory channels use physical CH1, for 2 GiB total. This release
does not repair CH0. Model checkpoints and Python environments are separate.
The experimental PHY reset patch is not part of this release.
The incoming `75fecaef` commit adds the tracked Chestnut transport and
[October 16 Mac runtime receipts](chestnut_ch1_benchmarks.md). They record
ISA-exact LFM2 and other model checks on this 100 MHz PCIe design with zero ECC
errors. These runtime results are separate from the historical flash receipt.

## Experimental RAM-only DDR800 diagnostic

Three additional local packages completed offline review on October 17:
[command/PHY trace](../bitstreams/ramtest-litedram-ddr800-phy-trace/),
[DDR667](../bitstreams/ramtest-litedram-ddr667/), and
[CH0 lane-8 replacement](../bitstreams/ramtest-litedram-ddr800-spare8/).
See their [build and review guide](ddr_lane6_experiment_builds.md).
They are not committed or pushed. Physical observations are recorded in the
current lane-6 plan (local-only `docs/ddr_lane6_debug_plan.md`): the trace reproduced the fault,
DDR667 did not recover reliably across reloads, and the spare configuration
passed targeted checks. The spare image retains capacity but removes CH0 ECC.

Three further local packages are available:

| Package | Build ID | Scope and evidence |
| --- | --- | --- |
| [Spare native probe](../bitstreams/ramtest-litedram-ddr800-spare8-native-probe/) | `c0172070` | CH0 lane 8 replaces lane 6; native partial-write checks, two full raw 4 GiB passes and refresh-on retention passed; complete OpenTPU/ECC qualification remains open |
| [Normal-lane control](../bitstreams/ramtest-litedram-ddr800-normal8-control/) | `c0172090` | Same eight-byte CH0 datapath using physical lanes 0–7, without CH0 ECC; targeted physical tests reproduced lane-6 failures |
| [Lane-6 termination control](../bitstreams/ramtest-litedram-ddr800-normal8-lane6-term50/) | `c0172090` (inherited) | Changes ten lane-6 DQ/DQS input-termination properties from nominal 40 to 50 ohms; unchanged logic, placement and routing reviewed; both settings failed the physical comparison |

The [registered-read raw-capture package](../bitstreams/ramtest-litedram-ddr800-registered-capture/)
(`c0172200`) is also built and reviewed. It keeps all nine original lanes and
both native ECC paths, with read latency 9. Internal setup/hold slacks are
+0.100/+0.044 ns. Its matched distinct-tag hardware experiment is queued;
no physical repair is claimed. See the build and test procedure (local-only `docs/ddr_registered_capture.md`).

All three run DDR800 with a 100 MHz controller and preserve CH1 ECC circuitry.
The control's bitstream SHA256 is
`68cdb97135cb2f8cd8f3689f81e876bc445e94c1c5b54e4a4051c700a288a1be`.
See the [native probe/control guide](ddr_spare_native_probe.md) for matched
firmware, rebuilding and test procedures. None of these packages is a full PCIe
accelerator image. The full spare-lane PCIe integration is now packaged below;
the already built CH1 compute candidate is a separate experiment.

The termination variant retains its parent's CSR build ID. Identify it using
its bitstream SHA256 and SRAM-load receipt, not that ID alone:
`155b392fb9bfc4099ad19f63e68d79e4743733020422fb93b26b5c51597e1152`.
Its build and comparison guide (local-only `docs/ddr_input_termination_control.md`) describes
the original-40 / candidate-50 / original-40 sequence. A completed build does
not establish a memory repair. These three packages remain local and unpublished.

### Experimental spare-lane full 4 GiB PCIe image

[`spare-pcie-4gb-ddr800/`](../bitstreams/spare-pcie-4gb-ddr800/) contains
`c0172080`, full OpenTPU at 100 MHz compute and DDR800, with XDMA Gen2 x8.
CH0 uses lanes `0,1,2,3,4,5,8,7` without ECC; CH1 retains ECC. Offline
implementation, artifact and clock-crossing reviews passed. Setup slack is
+0.039 ns and hold slack +0.012 ns; all 49 reviewed skew checks pass.
External DDR pad timing and physical full-system operation remain unqualified.

The SRAM bitstream SHA256 is
`19730b4708653c428cf388999c4d49b7437648dd27d358028999ee98c380a425`.
Keep its `core/`, `calibration/` and original RAM-only spare reference package
together. Startup calibrates CH1 only; the bound host calibration procedure
must initialize CH0 before memory qualification. See the package README and
[build/runtime guide](ddr_spare_native_probe.md). This package is local,
uncommitted and unpushed. No flash image is included. The RAM-only passes do
not establish PCIe DMA, matmul or LLM correctness for this implementation.

The locally packaged
[`ramtest-mig-ddr800-a8-focused`](../bitstreams/ramtest-mig-ddr800-a8-focused/)
image (`c0171101`, RAMA ABI 4) targets the lane-6 column-address coupling found
on CH0. It preserves the physical bank/row/column across MIG and LiteDRAM's
different address maps. Offline model, implementation and independent review
passed; the first physical observation passed all 2,048 reads and 16 writes per
channel with zero ECC/payload errors, and a second fresh SRAM load passed too. This bounded seven-word
test does not qualify all 4 GiB. Its README includes rebuild, review and status
reader commands. The package is local and has not been committed or pushed.

[`bitstreams/ramtest-mig-ddr800-address/`](../bitstreams/ramtest-mig-ddr800-address/)
contains the dedicated MIG address-pattern image, BUILD_ID `c0161001`, its
checksums and offline review. It tests 2 GiB per physical channel with ECC and
USER2 status, and contains no accelerator or PCIe endpoint. The build, complete
route, timing, board-reference pins and independent packet/CRC checks passed.
Fedora DLC10 SRAM loading and USER2 readback work. CH0 corrected errors were
reproduced with this image; see the saved physical observations (local-only `docs/data/ddr_ram_only_20261016.json`)
and [build/debug plan](ddr_ram_only_debug.md).

The [CH0-only address](../bitstreams/ramtest-mig-ddr800-ch0-address/),
[CH1-only address](../bitstreams/ramtest-mig-ddr800-ch1-address/),
[both-channel zeros](../bitstreams/ramtest-mig-ddr800-zeros/) and
[ones](../bitstreams/ramtest-mig-ddr800-ones/) images are also packaged locally.
Each isolated address run and the zeros, ones, walking-one, walking-zero and
PRBS runs passed five-minute observations.
These new packages are not yet committed.
Queued builds are not programming artifacts. Their identities,
rebuild commands and current preparation status are in the
[image preparation table](ddr_ram_only_debug.md#image-preparation-status).
The first LiteDRAM diagnostic stalled before accepting memory commands; its
ABI 1 package is quarantined under its build directory. The corrected
ABI 2 wrapper and reader (local-only `docs/ddr_ram_only_litedram.md`) are built and packaged.
Physical full-range and same-image read switching found CH0 errors with CH1
clean. A warm CH0 rescan then failed on lane 6. The next MIG causal experiment
uses runtime channel switching (local-only `docs/ddr_runtime_traffic.md`); its control model
and implementation review passed. The locally packaged
[`ramtest-mig-ddr800-runtime`](../bitstreams/ramtest-mig-ddr800-runtime/)
image reproduced CH0 corrected errors and completed both original and reversed
eight-phase switching sequences. The RAM-only
[serializer-reset image](../bitstreams/ramtest-litedram-ddr800-reset/) is now
packaged (`c0162011`); baseline/reset/baseline each passed five minutes, which
does not establish that the reset change fixes CH0. The separate
[registered-read image](../bitstreams/ramtest-litedram-ddr800-rdreg/) is also
packaged (`c0162012`). Its physical comparison completed baseline fail,
candidate five-minute pass, baseline fail. Two later candidate reloads produced
a five-minute pass followed by a CH0 failure; warm CH0 rescan then failed on
lane 6. Registered reads alone are not a repeatable repair. Mixed traffic failed on CH0;
a fresh-load normal-refresh retention screen passed. An ABI 3 image with
aligned first-read mismatch capture (`c0162030`) is packaged at
[`ramtest-litedram-ddr800-capture`](../bitstreams/ramtest-litedram-ddr800-capture/).
Its first physical load reproduced CH0 corrected errors with no post-ECC
payload mismatch or queue fault. A separate CH1 single/double-bit injection
validated ECC reporting and captured the exact mismatching address and data.
CH0 stability remains unresolved.

Runtime pattern changes exposed a separate diagnostic startup fault: the
existing LiteDRAM traffic source issued an out-of-range write when switching
to PRBS. A correction delaying diagnostic initialization until runtime controls
settle passed the seven-epoch transition model in both Verilator and Icarus,
plus the complete Icarus pattern/capture suite. Image `c0172031` is built,
independently reviewed and packaged at
[`ramtest-litedram-ddr800-runtime-pattern`](../bitstreams/ramtest-litedram-ddr800-runtime-pattern/).
Package checksums and host PRBS admission passed; its controller/core files
match the baseline. Physical tests and external DDR pad timing remain pending.
The host rejects PRBS starts on older LiteDRAM
packages. See same-image pattern changes (local-only `docs/ddr_ram_only_litedram.md#change-patterns-without-reloading-or-recalibrating`).

## Experimental CH0 reset comparison

[`bitstreams/ch1-pcie-2gb-ch0-reset/`](../bitstreams/ch1-pcie-2gb-ch0-reset/)
contains the already-built 100 MHz PCIe candidate, BUILD_ID `c0160001`, its
matched DDR800 core and offline review. It adds the later serializer-reset
stage while retaining CH1-only 2 GiB user mapping and raw CH0 diagnostics.
Critical CDC and bus-skew review is complete for its documented scope.
Physical loading and tests are pending; it establishes no CH0 repair and does
not provide the matched RAM-only LiteDRAM comparison. Its README includes
Mac snapshot and Fedora rebuild commands. The working CH1 release is separate.

## Full 4 GiB integration candidate

The 100 MHz compute/DDR800 dual-channel reset candidate (`c0160002`) is packaged
at [`bitstreams/dual-pcie-4gb-ddr800-reset/`](../bitstreams/dual-pcie-4gb-ddr800-reset/).
Routed timing, independent image review and scoped CDC review passed, including
ten additional routed CSR pointer skew checks. Package checksums and the host
package-validation path passed. This remains an experimental SRAM-load candidate;
external DDR pad timing and physical runtime qualification are pending.
The dual-channel host procedure (local-only `docs/ddr_dual_pcie_runtime.md`) documents separate
identity, memory and LFM2 stages over XDMA or Chestnut. Host software checks
have passed; physical operation and repeatable recovery of CH0 remain pending.

## Compute clock experiment

The [150 MHz compute experiment](ch1_compute_clock.md) is packaged at
[`bitstreams/ch1-pcie-2gb-core150/`](../bitstreams/ch1-pcie-2gb-core150/),
BUILD_ID `c0160150`. Its actual MMCM clock is 148.837209 MHz. It retains the
full accelerator, Gen2 x8 PCIe, CH1-only 2 GiB mapping and all six memory-core
files unchanged from the tested 100 MHz release. The final route has setup
slack +0.003 ns, hold +0.018 ns and zero failing endpoints; packet/CRC, pin,
both PCIe OOB clock-mode and scoped CDC reviews passed. All 49 original and
additional pointer-skew checks passed, minimum slack 2.984 ns. The package
contains the SRAM `.bit`, matched core, hashes and review evidence. Physical
DMA/matmul/LFM2 operation at the new clock and external DDR pad timing remain
unqualified. This experiment does not restore CH0. The failed earlier attempts
and complete Fedora build/review procedure are retained in the linked guide.

## The two 100 MHz designs

The standalone JTAG image and the permanent PCIe image are **separate Vivado
builds**. Both retain full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 compute at
100 MHz and the same CH1-only DDR800 memory core with ECC and 2 GiB usable
memory. Each virtual channel has 1 GiB. The host interfaces differ:

| Design | Runtime host connection | Verified hardware result |
| --- | --- | --- |
| Standalone CH1 JTAG | USER2 JTAG for commands, model weights and results | Warm memory, exact matmul and eight LFM2 tokens passed; answer: “The capital of France is Paris.” |
| CH1 PCIe | Gen2 x8 XDMA endpoint; Mac Chestnut bridge negotiated Gen2 x2 | Flash/boot receipt retained; October 16 Mac receipts record physical matmul, ISA-exact model tokens and zero ECC errors |

The [shared RTL comparison](../build/fedora-vivado/ch1-pcie-all-compute-source-match.json)
records 26 matching shared source files. Matching compute/memory sources do
not establish that the separate PCIe host integration has executed physically.

The three current files are:

```text
# Standalone JTAG image that passed LFM2
build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit

# PCIe design, suitable for loading into FPGA SRAM
build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit

# Same PCIe design packaged for permanent BPI x16 NOR programming
build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.mcs
```

## Design choice and storage choice

The `.mcs` is generated from its matching PCIe `.bit`. It packages the same
configuration data with flash addresses and the BPI byte representation; this
conversion does not synthesize another design. A `.bit` SRAM load lasts until
configuration or power is lost. Programming the matching `.mcs` into NOR
preserves the design for boot. The USER2 JTAG design and PCIe design differ
because their host interfaces were built differently, independently of where
the configuration is stored.

The DLC10 can program either design over JTAG. Runtime commands and model
transfers use the interface included in the chosen design. Temporarily loading
the standalone `.bit` into SRAM leaves the PCIe NOR image intact; booting from
NOR selects the PCIe design again. Model weights reside in volatile DDR and
must be uploaded again after power loss.

## Current hashes, receipts and build helpers

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| [Standalone JTAG .bit](../build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit) | 12,484,177 | `0fc10bf2a6459ca5273b0dc6616e43974209ff0176fa2b95e017626e03f93d21` |
| [PCIe .bit](../bitstreams/ch1-pcie-2gb/otpu.bit) | 12,472,031 | `c7d3891b58d65ba72a3fc67c27c63c8dca3246db55d6504f7a63b636c876d1cf` |
| [PCIe .mcs](../bitstreams/ch1-pcie-2gb/otpu.mcs) | 34,300,540 | `101178a32024ba416f90813afe7672b80e26fb154982d7fec85209bbab2e5f77` |

- [Physical JTAG LFM2 receipt](../build/fedora-vivado/ch1-lfm2-physical-pass-current.json).
- [PCIe image review](../build/fedora-vivado/ch1-pcie-program-review-current.json).
- [Permanent programming receipt](../build/fedora-vivado/ch1-permanent-pcie-audited-current.json): October 15, 07:44–07:52:56 HKT; 8 minutes 47 seconds; backup skipped at the user's request.
- [Standalone build helper](../tools/fedora_build_vivado_ch1_jtag.py) and [resume helper](../tools/fedora_resume_vivado_ch1_jtag.py).
- [PCIe build helper](../tools/fedora_build_vivado_ch1_recovery.py), [frozen build record](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/manifest.json) and [flash programmer](../tools/fedora_flash_ch1_pcie.py).

For programming details and PCIe host/model commands, use
[permanent PCIe boot](permanent_pcie_ch1.md). The
[Vivado guide](vivado_bitstream_guide.md) also retains the older MIG rebuild
procedure. The matched portable host/model archive is
[the PCIe LFM2 host bundle](../build/fedora-vivado/ch1-pcie-flash-host-20261015.tar);
it contains the host/compiler/model and calibration data, with no bitstream.

## Testing on this machine

The card is currently connected to Fedora through DLC10 USB/JTAG. SRAM
programming, USER2 readback and RAM-only observations are measured here;
there is no live FPGA PCIe endpoint on this Fedora host.
LFM2 previously passed on Fedora using the standalone JTAG design and now has
tracked Mac Chestnut receipts for the PCIe design. Runtime needs a physical
PCIe link: this machine can host it if the card is
installed in its PCIe slot, or the selected other Linux PC can host it. A
separately powered card with only a DLC10 USB connection supplies JTAG access.
It does not provide the PCIe data link. Cold-boot enumeration and model testing
instructions are in the [PCIe host guide](permanent_pcie_ch1.md#pcie-host-pc).

## Full file inventory

The groups below describe purpose and measured status. Files marked as corrupted
are intentional checker test inputs. The bundled Spartan-6 loader bitstreams
target different FPGA parts and are not YPCB accelerator images.

### Current CH1 images

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit](../build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit) | 12,484,177 | Standalone CH1 USER2 JTAG image; physical matmul and LFM2 passed |
| [build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit) | 12,472,031 | Current CH1 PCIe SRAM-format image; flash/verify/JTAG boot passed; PCIe inference pending |
| [build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.mcs](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.mcs) | 34,300,540 | Current CH1 PCIe BPI x16 flash-format image; used for permanent programming |

### Historical Vivado images

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-vivado/mig-jtag-controller-20261010T235833Z/implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit) | 12,870,600 | Historical dual-channel MIG JTAG image; later warm DDR failures; superseded by CH1 recovery |
| [build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.bit](../build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.bit) | 11,638,155 | Earlier dual-channel DDR800 PCIe build; accesses CH0; superseded by CH1 recovery |
| [build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.mcs](../build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.mcs) | 32,007,176 | Earlier dual-channel DDR800 PCIe build; accesses CH0; superseded by CH1 recovery |
| [build/fedora-vivado/physical-jtag-20261010T133821Z/clock-diagnostic-20261010T1435Z/diagnostic.bit](../build/fedora-vivado/physical-jtag-20261010T133821Z/clock-diagnostic-20261010T1435Z/diagnostic.bit) | 11,599,613 | Historical clock diagnostic image; full LFM2 unverified |

### Experimental and test images

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrected-dsp-fixture-with-crc.bit](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrected-dsp-fixture-with-crc.bit) | 18,735,219 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_crc_value.bit](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_crc_value.bit) | 18,735,219 | Deliberately corrupted negative test fixture for image/CRC checker |
| [build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_frame_data.bit](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_frame_data.bit) | 18,735,219 | Deliberately corrupted negative test fixture for image/CRC checker |
| [build/fedora-openxc7/clock-codec-check-20261012T133557Z/clock-diagnostic.bit](../build/fedora-openxc7/clock-codec-check-20261012T133557Z/clock-diagnostic.bit) | 18,735,213 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/crc-image-fixture-check-20261013T152400Z/design-with-crc.bit](../build/fedora-openxc7/crc-image-fixture-check-20261013T152400Z/design-with-crc.bit) | 18,735,219 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/dsp-corrected-fixture-image-runtime-fixed-20261013T140200Z/corrected-dsp-fixture.bit](../build/fedora-openxc7/dsp-corrected-fixture-image-runtime-fixed-20261013T140200Z/corrected-dsp-fixture.bit) | 18,735,219 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/dsp-mode-feasibility-20261006T191434Z/probe.bit](../build/fedora-openxc7/dsp-mode-feasibility-20261006T191434Z/probe.bit) | 18,735,198 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/full-mapped-reference.bit](../build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/full-mapped-reference.bit) | 18,735,238 | OpenXC7-mapped netlist implemented by Vivado; reference image, physical inference unverified |
| [build/fedora-openxc7/pcie-image-checker-validation-20261008T065925Z/corrupt-first-frame.bit](../build/fedora-openxc7/pcie-image-checker-validation-20261008T065925Z/corrupt-first-frame.bit) | 18,735,177 | Deliberately corrupted negative test fixture for image/CRC checker |

### Bundled loader helpers

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit) | 3,318,013 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit) | 1,484,501 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit) | 3,318,013 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit) | 1,484,501 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit](../build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit) | 3,318,013 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit](../build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit) | 1,484,501 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |

## Refresh the inventory

The build directories are ignored by Git. Include ignored files when searching:

```bash
# Run from the root of your OpenTPU checkout.
rg --files --hidden --no-ignore build -g '*.bit' -g '*.mcs'
```

This snapshot covers FPGA configuration `.bit` and flash `.mcs` files in this
checkout. Calibration firmware, model data and incomplete old-flash readbacks
also use `.bin`; those are different artifacts and are outside this index.


## Matched MIG address/write-order diagnostic

[`ramtest-mig-ddr800-a8-order`](../bitstreams/ramtest-mig-ddr800-a8-order/)
is c0171102, a reviewed RAM-only DDR800 image with both original ECC channels.
It performs 24 writes and 512 reads per channel using distinctive beat tags
at four locations. Build/package complete; physical qualification pending.
See build and readback instructions (local-only `docs/ddr_mig_a8_order.md`). It does not contain
PCIe or OpenTPU and does not qualify the full memory capacity.
