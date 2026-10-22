# Spare-lane 4 GiB builds with JTAG and PCIe

**Historical October 17 combined-interface preparations.** c0172462 was
rejected for its shared-host reset defect; the c0172300 Mac CH0 failure also
invalidated the earlier independent-response pipeline. The later
c0182800/c0182863 repairs have separate passing Mac receipts, and the
c0182600/c0182663 startup variants have local JTAG results. See
[tested builds and outstanding tests](bitstreams.md#tested-builds-and-outstanding-tests)
and the final [HANDOFF.md](../HANDOFF.md) disposition. The c01848 runtime-clock
effort was abandoned. None of the old queues, build commands or proposed
acceptance steps below is a current implementation or hardware-test plan.

## Historical queue snapshot

Checkpoint: October 17, 2026. The background service at that time was
`opentpu-spare4gb-dual-host-parallel-20261017.service`. The existing c0172300
implementation, independent review and package were complete; the later Mac
LFM failure was not yet observed. The user requested parallel builds and
selected c0172462 before its subsequent rejection.
Two frozen source snapshots were assigned concurrent slots, with the other two
entering freed slots in the recorded order below. Each used two threads.
The combined-host block-design checks passed before launch. The old sequential
build/review/source waiters were stopped and superseded; their logs remain.
No flash programming occurs in this queue.

| Order | Build ID | Compute clock | DDR data rate | Host access | Build milestone |
| --- | --- | --- | --- | --- | --- |
| Final review rejected | c0172462 | 148.837 MHz, requested 150 | DDR1066, actual 1066.667 MT/s | JTAG USER2 and PCIe | 80%, implementation and collection complete; decoded shared-reset defect prevents approval; successor c0172862 queued |
| Baseline at snapshot | c0172800 | 100 MHz | DDR800 | JTAG USER2 and PCIe | 40% at snapshot: synthesis complete, placement running; registered-reset correction included |
| Parallel slot at snapshot | c0172450 | 148.837 MHz, requested 150 | DDR800 | JTAG USER2 and PCIe | 60% at snapshot: routed; final timing/build work running |
| Implementation at snapshot | c0172461 | 100 MHz | DDR1066, actual 1066.667 MT/s | JTAG USER2 and PCIe | 40% at snapshot: synthesis complete; implementation running |

Percentages count completed milestones: frozen sources, synthesis, routing,
bitstream generation, and review/package. They do not predict remaining time
or indicate physical qualification. c0172300 remains a separate PCIe-only,
100 MHz/DDR800 comparison; its completed package is preserved separately.
The baseline c0172800 was implementing in its own slot at that snapshot; it
replaced c0172400's reset circuit while retaining the same clocks, full 4 GiB
and combined interfaces. See the
historical image comparison (local-only `docs/ddr_lane6_debug_plan.md#baseline-image-differences`)
for the exact functional and readiness differences.

All four candidates keep the complete accelerator, 4 GiB address space,
CH0 physical byte lanes `[0,1,2,3,4,5,8,7]` with CH0 ECC disabled, and CH1 ECC.
CH0 uses two raw native ports and 32 read credits per port. Writes and partial
read-modify-write operations remain globally exclusive; this change does not
claim pipelined write performance.

Startup firmware still calibrates CH1 only. Each candidate requires a matching
eight-lane CH0 host calibration helper after reload. Automatic mixed-width
startup is separate pending firmware work. Existing exact-image helpers must
not have their identity guards bypassed to accept these new IDs.

## Combined host fabric

`tools/dual_host_source.py` changes an isolated board snapshot. It adds the
existing USER2 mailbox protocol and a JTAG AXI bridge, alongside XDMA:

- A two-input SmartConnect arbitrates 128-bit PCIe and JTAG memory traffic.
  The common host DMA path runs at an independent 250 MHz from the board's
  50 MHz oscillator; absence of the PCIe reference clock does not stop it.
- A three-input control SmartConnect routes PCIe control and JTAG register/
  calibration requests to the existing control, calibration and XADC windows.
- SmartConnect retains upstream transaction IDs internally. Its generated
  downstream interface has no ID signals; the native adapter uses constant
  ID zero. The generated wrapper must agree with this connection.
- Configuration-time core reset depends on the board clock lock, independently
  of PCIe PERST. A PCIe reset transition causes a bounded shared-host reset.
  An absent/reset endpoint does not continuously hold JTAG access in reset.
- An interrupted JTAG AXI request returns status `0x80` with its original
  sequence number. Accepted writes are not rolled back. Stop workloads before
  deliberate reset or recalibration and coordinate host writes to shared memory.

USER2 keeps the existing command ABI: register access and 64-byte memory
read/write requests, one outstanding JTAG command. Calibration CSRs remain at
`0x10000`. Physical memory channel selection is byte-address bit 31, 2 GiB
per channel. JTAG TCK is constrained to at most 6 MHz. JTAG throughput is not
intended to match PCIe throughput.

Focused reset and AXI-abort simulations passed. The generated baseline block
design, all 158 connected wrapper ports, clock selection and reset polarity
checks passed without critical warnings. These checks do not replace full
implementation, CDC review or testing with PCIe disconnected and connected.

## Historical reconstruction commands

These commands preserve the old source workflow and local dependencies. They
are not a supported way to recreate a current candidate: the original adapter
and rejected identities must not re-enter the hardware plan. Preserve existing
source snapshots and receipts; the current result table above identifies the
later corrected images.

Prerequisites are Vivado with Kintex-7/XDMA support, the pinned LiteDRAM Python
environment, the reviewed DDR800 pipeline preparation and protocol model, and
the focused host-reset/JTAG-abort model receipt. Follow
[the pipeline preparation instructions](ddr_spare_pipeline.md) first. The
combined-host preparer validates these inputs; arbitrary unreviewed cores are
rejected. Keep the Python virtual-environment executable path rather than
resolving its symlink to the bare interpreter.

Prepare one DDR800 candidate, choosing a fresh output directory:

```bash
python3 -B tools/prepare_spare_dual_pcie.py \
  --baseline build/fedora-vivado/spare-full-pcie-pipeline-20261017 \
  --core build/fedora-vivado/spare-full-pcie-pipeline-20261017/core \
  --adapter-model build/checks/spare-native-pipeline-v2-20261017/manifest.json \
  --host-model build/checks/dual-host-rtl-20261017/manifest.json \
  --build-id c0172400 --threads 2 \
  --out build/vivado/spare-dual-c0172400-new
```

Select c0172450 for the faster compute clock. For DDR1066, first generate the
pipelined memory core and verify its firmware/settings binding:

```bash
python3 -B tools/prepare_spare_pipeline_ddr1066_core.py \
  --reference build/fedora-vivado/spare-full-pcie-ddr1066-20261017 \
  --firmware-model build/checks/spare4gb-ddr1066-firmware-20261017/manifest.json \
  --adapter-model build/checks/spare-native-pipeline-v2-20261017/manifest.json \
  --out build/vivado/spare-dual-ddr1066-core-new
```

Then use that output's `core/` as `--core`, selecting c0172461 or c0172462.
The DDR1066 firmware is c0172168; DDR800 uses c0172068. The preparer checks
that startup ROM, initialization data and all non-comment CSR rows match the
reviewed firmware configuration. That binding is not physical calibration.

Implement the frozen snapshot, independently of later working-tree changes:

```bash
prep=build/vivado/spare-dual-c0172400-new
prep_sha=$(sha256sum "$prep/manifest.json" | cut -d ' ' -f 1)
python3 -B tools/run_spare_dual_snapshot.py \
  --preparation "$prep" --preparation-sha256 "$prep_sha"
```

`--check-only` validates inputs without starting Vivado. A full run creates
`implementation/`, checks the generated wrapper, runs synthesis and routing,
and requires nonnegative setup/hold/pulse timing, zero failing timing endpoints,
complete routing, and no DRC errors or critical warnings before writing
`implementation/project/otpu.bit` and `otpu.mcs`. It never opens hardware.
Existing directories and changed source hashes fail closed.

## Historical background queue inspection

```bash
systemctl --user status opentpu-spare4gb-dual-host-parallel-20261017.service
cat build/fedora-vivado/spare-dual-host-parallel-20261017/manifest.json
```

The frozen schedule and commands are in
`build/fedora-vivado/spare-dual-host-parallel-20261017/`. Selected source snapshots
are `build/fedora-vivado/spare-dual-host-c0172400-v3-20261017/` and the
corresponding `c0172450`, `c0172461`, `c0172462` directories with the same
`-v3-20261017` suffix. Earlier preparation attempts are preserved.

The queue verifies frozen source hashes and copies each selected source
snapshot rather than recopying the working tree. It admits at most two
implementations at once and retains a 10 GiB available-memory threshold before
adding a second job. Existing jobs continue if memory availability changes.
The four implementations are independent: a failure in one does not skip
another. Logs and failure receipts remain available.

## Qualification after implementation

Implementation outputs remain experimental. Each new image needs its own
timing, clock, pad, bitstream/CRC and CDC disposition, including the new mailbox,
SmartConnect and reset paths. c0172300's PCIe-only collectors and BSCAN-count
assumptions cannot approve these combined images unchanged. A package and
exact-image calibration/host handoff follow that review.

The user had selected c0172462 as the first faster candidate before its
rejection. The following acceptance plan is retained as history. Each candidate
would need to pass its exact offline
gates before loading. Verify JTAG with PCIe absent,
PCIe/Chestnut access, coordinated use of both interfaces, reset recovery,
DMA and partial writes, matmul/reference inference, and matched device bandwidth
counters. Successful source generation is not measured bandwidth improvement.
Original lane-6 diagnosis and CH0 ECC restoration remain last in the plan.

### Bounded integration before model upload

`tools/run_spare_dual_integration.py` prepares the first physical check through
JTAG, Chestnut or XDMA. It requires the exact reviewed package, matching host
tree and successful calibration receipt. It reuses the package's small DMA,
logical-boundary and native QST byte-mask checks, then compares a compact
matmul against the ISA reference. It initializes the output and program
padding as complete interleaved beats before partial writes. This avoids
reading undefined CH1 ECC during a partial program upload.

The proposed command below was never an approval of c0172462. Its final review
rejected the image; retain the command as protocol documentation only:

```bash
python3 -B tools/run_spare_dual_integration.py \
  --build-id c0172462 --host-tree "$DUAL_HOST_TREE" \
  --package "$DUAL_IMAGE_PACKAGE" \
  --calibration-receipt "$DUAL_CALIBRATION_RECEIPT" \
  --transport jtag --xvc-host localhost --xvc-port 3721 \
  --out build/hardware-test/c0172462-bounded-integration-new
```

The runner overwrites its sentinel/work/program regions, clears the global
DRAM-initialization marker and never asserts that the entire memory is
initialized. It performs no full-range RAM loop, programming, calibration or
automatic recovery. Inference initialization follows separately. A passing
selected-interface run does not establish concurrent-host/reset behavior or
peak bandwidth.

Host import/hash checks passed for all eight queued clock combinations.
The sparse host-memory/ISA model passed 22 DMA/masked-write comparisons and
the matmul using 45,824 bytes of initialized physical memory. It also rejected
the partial program upload before working-region initialization. Its receipt
is `build/checks/spare-dual-integration-model-20261017/manifest.json`; this is
software evidence, not FPGA execution. Actual package preflight and physical
execution still require the completed reviewed image.

### Prepared review and host tools

The combined-host artifact/CDC collectors are now prepared for all four IDs.
A separate background worker,
`opentpu-spare4gb-dual-host-review-saved-skew-20261017.service`, observes the exact
implementation owner's per-image completion receipts and collects each
successful image's evidence sequentially. It now reviews the already built
c0172400 first, followed by c0172462, c0172450 and c0172461, while implementations
continue. The user's first faster-image physical priority remains c0172462.
Its schedule and logs are
under `build/checks/saved-skew-review-stream-dual-host-20261017/run/`. The former
whole-queue review/source waiters were superseded before they started any audit.

The artifact checks retain the existing timing, routing, CRC, pad, phase and
PCIe OOB-mode gates. They additionally require USER2, the independent host
clock, mailbox max-delay paths and the reset/toggle synchronizers. Skew
coverage is derived from each actual routed checkpoint: all 28 native-memory
groups must preserve their endpoints and appropriate clock budgets, and both
held mailbox payloads must retain their bounds. Every declared skew group,
including interconnect IP groups, must pass. Counts alone do not approve CDC.

Separate host trees are prepared at
`build/handoffs/spare-dual-host-c0172400-v2-20261017/host/`, and corresponding
paths for the other three IDs. They support `--transport jtag`, `chestnut`
or `xdma`. JTAG additionally accepts `--xvc-host` and `--xvc-port`; it requires
an already running XVC server and never programs the FPGA. Match the package
and firmware to the exact build ID. JTAG uses the same device-memory guards;
its serialized transfer rate is not a bandwidth measurement.

The generated helpers' imports, shell syntax, rejection of the existing
c0172080 package, and a software-only JTAG cross-burst read/write model passed.
The model uses the uint8 array API used by the DMA runner. Positive acceptance
of a new package and physical host execution remain pending.

To reproduce preparation for an existing frozen source snapshot:

```bash
python3 -B tools/prepare_spare_dual_review.py \
  --preparation build/vivado/spare-dual-c0172400-new \
  --out build/checks/spare-dual-review-new
python3 -B tools/prepare_spare_dual_host.py \
  --preparation build/vivado/spare-dual-c0172400-new \
  --out build/handoffs/spare-dual-host-new
```

The review preparation writes exact artifact/CDC/Gray-pointer commands to its
manifest. Execute them in the listed order after implementation succeeds.
The host preparation creates an isolated `host/` tree and records its generated
files; it does not modify the existing baseline transport or approve a package.

### Package preparation and source collection

Exact-image packagers are prepared at
`build/checks/spare-dual-packager-c0172400-20261017/`, with corresponding
directories for the three other IDs. Their CLI imports passed, and all four
reject the existing c0172080 implementation. Firmware-only fixtures also
passed the generated calibration helpers' bindings at DDR800 and DDR1066.
Those fixtures deliberately use zero image hashes and are not image packages.

The packager requires the actual completed implementation, artifact review,
CSR Gray-pointer review, selected source comparison and a new explicit CDC
disposition covering every reported non-information row. It copies the exact
pipeline/reset model evidence, calibration firmware, core and isolated host
tree. The existing baseline's CDC approval cannot satisfy these gates.

Prepare a packager for a fresh frozen snapshot and host tree:

```bash
python3 -B tools/prepare_spare_dual_packager.py \
  --preparation build/vivado/spare-dual-c0172400-new \
  --host-tree build/handoffs/spare-dual-host-new/host \
  --out build/checks/spare-dual-packager-new
```

After implementation, record the selected source contracts with:

```bash
python3 -B tools/collect_spare_dual_cdc_source.py \
  --preparation build/vivado/spare-dual-c0172400-new \
  --reference bitstreams/spare-pcie-4gb-ddr800 \
  --out build/checks/spare-dual-review-new/source-comparison.json
```

The current source collector runs as the fourth job for each image in
`opentpu-spare4gb-dual-host-review-saved-skew-20261017.service`, immediately after
that image's artifact, CDC and Gray-pointer collections. It does not wait for
all other builds to finish. Collection remains separate
from the manual CDC disposition. Preliminary source checks pass for all four
snapshots: unchanged selected native RTL, all five complete CSR FIFO blocks,
512 FIFO-operation lines and 50 synchronizer lines after one-to-one RAM naming.

Run a generated packager's `--help` for its exact arguments. DDR800 firmware
uses the reviewed RAM-only reference package and firmware bundle. DDR1066
uses the original reviewed DDR1066 generation directory, its `calibration/`
directory and `--firmware-model` receipt; only identical initialization,
startup ROM and non-comment CSR rows permit reuse with the new native adapter.
The output remains experimental and requires physical validation.

## Matched device-bandwidth comparison

After an image is reviewed, packaged, calibrated and initialized for inference,
use `tools/run_spare_dual_bandwidth.py` for a repeatable native-read measurement.
It supports the existing c0172080 baseline, PCIe-only c0172300 and the four
combined-host IDs. This does not program, calibrate, initialize all DRAM or run
another standalone memory soak. It requires the existing initialization marker
and exact-image calibration receipt. Run it with compute idle; it overwrites
the program at logical `0x3c0000` and a 16 KiB output at `0x400000`, so reload
the model/program before the next inference run if those allocations matter.

For a future packaged c0172400 on the Mac, from the checkout root:

```bash
python3 -B tools/run_spare_dual_bandwidth.py \
  --build-id c0172400 \
  --host-tree "$DUAL_HOST_TREE" \
  --package "$DUAL_IMAGE_PACKAGE" \
  --calibration-receipt "$DUAL_CALIBRATION_RECEIPT" \
  --transport chestnut --span 67108864 --repeats 3 \
  --out build/benchmarks/c0172400-native-read
```

Set those three variables to the **reviewed package's isolated host tree**,
its image package and the successful calibration JSON from the current FPGA
configuration. The current prepared c0172400 host tree is
`build/handoffs/spare-dual-host-c0172400-v2-20261017/host/`; it is not yet a
physically qualified package. For c0172300 the prepared host tree is
`build/handoffs/spare4gb-host-c0172300-20261017/`.

For comparison with the currently packaged baseline, after its usual Mac
calibration and inference initialization:

```bash
python3 -B tools/run_spare_dual_bandwidth.py \
  --build-id c0172080 --host-tree . \
  --package bitstreams/spare-pcie-4gb-ddr800 \
  --calibration-receipt "$BASELINE_CALIBRATION_RECEIPT" \
  --transport chestnut --span 67108864 --repeats 3 \
  --out build/benchmarks/c0172080-native-read
```

Use fresh output paths and identical span/repeat settings. The baseline and
c0172300 have PCIe memory access only; combined images also permit `--transport
jtag --xvc-host localhost --xvc-port 3721` with an existing XVC server. JTAG
transport time is not the accelerator's memory bandwidth.

The result saves 64-bit `RUNNING`, `DRAM_RD` and `DRAM_WR` snapshots, exact
instruction/beat counts, the final 16 KiB payload comparison, calibration
binding and temperature. `median_logical_read_gbs` uses device running cycles
and the image's compute clock. `host_run_call_seconds` is recorded separately.
The workload reads both channels, but compares only its final chunk; it is not
a full-range correctness check, an LLM benchmark or a write-throughput test.
Follow with the same model, prompt, KV/resident settings and token counts for
the inference comparison. No physical improvement has been measured yet.

## Mixed-width automatic startup: separate firmware revision

The four frozen combined-host builds still calibrate CH1 at startup and need
their exact CH0 helper. The offline mixed-width firmware is now compiled for
both DDR operating points, using one shared calibration implementation with
channel-specific lane counts, DFI word counts and patterns:

| Firmware ID | DDR rate | RV32I binary | Current gate |
| --- | --- | --- | --- |
| c0172608 | DDR800 | 10,824 bytes | Seven host/reference cases and exact RV32 CPU/CSR-trace comparison passed |
| c0172668 | DDR1066 | 10,820 bytes | Seven host/reference cases and exact RV32 CPU/CSR-trace comparison passed |

Both fit the existing 16 KiB firmware memory and satisfy its linker stack
reservation. CH0 retains the reviewed eight-lane four-word data framing and
one-beat phase check. CH1 retains nine-lane five-word framing and its reference
64 MiB phase check. The boot entry honors both channel mask bits and preserves
the existing combined mailbox/state layout. These are implementation details
under software review, not observed automatic calibration on the card.

The sources and binaries are isolated under
`build/checks/spare-mixed-selfcal-ddr800-v2-20261017/` and
`build/checks/spare-mixed-selfcal-ddr1066-20261017/`. The original failed DDR800
preparation is preserved separately. No queued implementation, current SRAM
configuration or permanent flash has been changed.

To reproduce against an appropriate generated core and the reviewed spare
reference sources, with a working RV32I toolchain:

```bash
python3 -B tools/prepare_spare_mixed_selfcal.py \
  --core "$GENERATED_SPARE_CORE" \
  --reference-package bitstreams/ramtest-litedram-ddr800-spare8 \
  --rv-cc "$RV32_GCC" --firmware-id c0172608 \
  --out build/checks/spare-mixed-startup-new
python3 -B tools/check_spare_mixed_selfcal.py \
  --build build/checks/spare-mixed-startup-new \
  --out build/checks/spare-mixed-startup-model-new
```

Use c0172668 with the DDR1066 core. The checker exercises the actual boot
entry through software CSR callbacks, comparing each channel with its own
host calibration reference. Cases cover both channels, per-bit framing, a
failed calibration on either channel, either channel selected alone and an
empty channel mask. This does not execute the RV32 CPU or establish physical
startup behavior. After software review, integration into a new image needs
an explicit source/profile/host-binding update, a new build identity and
routed-image review; the existing four-build queue is preserved.

Both seven-case host comparisons completed successfully. Their receipts are
`build/checks/spare-mixed-selfcal-ddr800-model-v2-20261017/manifest.json` and
`build/checks/spare-mixed-selfcal-ddr1066-model-v2-20261017/manifest.json`.
The earlier checker attempts are preserved: they stopped when a channel-only
case exposed that the existing decoder omits idle channels from its result
dictionary. The corrected checker verifies that absence and the mailbox idle
bits; it does not change the firmware or relax a calibration result.

Isolated core copies now contain the new startup words:

| DDR rate | Preparation directory | Source change |
| --- | --- | --- |
| DDR800 | `build/fedora-vivado/spare-mixed-startup-core-ddr800-v2-20261017/` | 2,606 of 4,096 startup words changed |
| DDR1066 | `build/fedora-vivado/spare-mixed-startup-core-ddr1066-20261017/` | 2,605 of 4,096 startup words changed |

Every RTL character outside the firmware-memory initialization is identical
to its pipelined parent core. The CSR map, DDR settings, native adapter, CPU
logic and timing constraints are unchanged. The new profile records both
automatic channels and is deliberately rejected by existing CH1-only profile
tools; it has not silently entered the frozen build queue.

Reproduce a boot-core copy after a successful matching host-model review:

```bash
python3 -B tools/prepare_spare_mixed_boot_core.py \
  --core "$GENERATED_SPARE_CORE" \
  --firmware build/checks/spare-mixed-startup-new \
  --model build/checks/spare-mixed-startup-model-new/manifest.json \
  --out build/vivado/spare-mixed-boot-core-new
```

This prepares memory-core source only. An actual automatic-startup OpenTPU
image, its host decoding/binding, routed review and physical boot test remain
pending. It does not add another standalone RAM test.

The actual mixed-width binaries also completed on the reference VexRiscv RTL
with simulated PHY CSR responses. Both channels became ready and every PHY
write matched the independent host references: 1,063,484 writes in each test.
DDR800 completed in 116,000,616 simulated cycles and DDR1066 in 118,000,626.
Receipts are `build/checks/spare-mixed-selfcal-ddr800-rv32-20261017/manifest.json`
and `build/checks/spare-mixed-selfcal-ddr1066-rv32-20261017/manifest.json`.

These CPU runs explicitly selected a phase-scan stride of eight. Reset-default
stride-one execution, the physical analog interface and automatic startup in
a complete new FPGA image remain separate gates. Reproduce the bounded CPU
test after the matching seven-case host comparison:

```bash
python3 -B tools/run_spare_mixed_selfcal_rv32.py \
  --firmware-build build/checks/spare-mixed-startup-new \
  --host-review build/checks/spare-mixed-startup-model-new/manifest.json \
  --out build/checks/spare-mixed-startup-rv32-new
```

Reset-default comparisons completed separately at both DDR rates under
`opentpu-spare4gb-mixed-fw800-default-rv32-20261017.service` and
`opentpu-spare4gb-mixed-fw1066-default-rv32-20261017.service`. They start the
CPU without host writes to hold/config, verify reset configuration `0x103`,
and compare against a stride-one reference. Both passed with ready mask 3
and an exact 6,946,294-write PHY trace. DDR800 completed in 780,003,926
simulated cycles and DDR1066 in 797,004,011. Their manifests are under
`build/checks/spare-mixed-selfcal-ddr800-default-rv32-20261017/` and the
corresponding `ddr1066-default` directory. Add `--reset-default` to the
command above, choosing a fresh output directory. The model still supplies
the PHY responses; a passing CPU run cannot establish physical calibration.

The exact previous runner source is archived at
`build/checks/spare-mixed-selfcal-rv32-source-v1-20261017/`, matching the SHA
recorded by both completed stride-eight runs. The current tool adds explicit
host-selected and reset-default modes; existing receipts were not rewritten.
Its exact completed reset-default version is archived separately under
`build/checks/spare-mixed-default-rv32-source-20261017/`.

### Bind the prepared core to the completed CPU evidence

`tools/spare_mixed_startup_profile.py` now checks the prepared core against
its original strict pipelined profile, every embedded startup word, the
compiled firmware, the seven-case host comparison, and both completed CPU
runs. It verifies the retained CPU RTL and simulation-library hashes as well
as the model's target binary and memory settings. All RTL outside the 4,096
initialization words must remain identical to the parent core. CH0 remains
non-ECC with the spare lane; CH1 retains ECC.

Both operating points passed this source gate. Receipts are under
`build/checks/spare-mixed-startup-core-ddr800-binding-v2-20261017/` and
`build/checks/spare-mixed-startup-core-ddr1066-binding-v2-20261017/`.
Wrong-rate CPU evidence, using the older host-selected run as reset-default
evidence, and an original CH1-only core are rejected. The older bounded
receipts omit startup-mode fields; only their exact archived runner hash
establishes the hardcoded stride-eight mode. They cannot satisfy the separate
reset-default requirement.

For a fresh preparation, point the following variables at its matching
boot-core preparation and two completed CPU runs:

```bash
python3 -B tools/spare_mixed_startup_profile.py \
  --preparation "$MIXED_BOOT_CORE_PREPARATION" \
  --bounded-rv32 "$MIXED_BOUNDED_CPU_RUN" \
  --default-rv32 "$MIXED_DEFAULT_CPU_RUN" \
  --out build/checks/spare-mixed-source-binding-new
```

If a model source has since changed, add `--source-copy` with its preserved
source file. Its content must match the model receipt's hash. This gate reads
the existing artifacts; it does not alter their profiles or mark an image
ready for implementation. Separate full-image identity, host decoding/binding,
routed review and physical startup gates are required. The eight queued clock
combinations retain their existing startup firmware.

### Separately identified automatic-startup image builds

Two full-image source snapshots now integrate that firmware with the existing
combined-host design. They use existing clock targets:

| Build ID | Parent | Compute / DDR | Startup | Build status |
| --- | --- | --- | --- | --- |
| c0172662 | c0172462 | 148.837 MHz / 1066.667 MT/s | Both channels, firmware c0172668 | 20%, frozen and queued after the eight clock builds |
| c0172600 | c0172400 | 100 MHz / 800 MT/s | Both channels, firmware c0172608 | 20%, frozen and queued after the eight clock builds |

The snapshots are under
`build/fedora-vivado/spare-dual-host-c0172662-mixed-v1-20261017/` and the
corresponding `c0172600` directory. The new build ID is passed to the existing
project generator. Compared with each parent snapshot, only the generated
memory RTL's firmware words and its two profile JSON files differ. The full
accelerator, pipeline, DDR settings, lane map, ECC configuration, host/reset
logic and constraints are retained. The implementation runner's main flow and
wrapper check are identical by AST comparison; the pre-bit timing/routing gate
is byte-identical. Fresh-process source checks passed for both snapshots, and
the mixed-image runner rejects an original CH1-only preparation.

The original `opentpu-spare4gb-mixed-startup-queue-20261017.service` waited for
the combined-host and faster-DDR queues. It was superseded while waiting, with
no implementation child interrupted, by the priority queue described below.
That queue retains these frozen preparations and the same two-implementation
limit and memory admission threshold. The latest user authorization selects
c0172400 for the first baseline SRAM test and permanent flash after its review
and SRAM integration pass; c0172462 remains first among faster candidates.
The original schedule and logs remain under
`build/fedora-vivado/spare-mixed-startup-queue-20261017/`. There are eight clock
combinations, two startup-firmware variants and two separately identified
reset corrections; no additional compute-clock targets were added.

Reproduce source preparation using a matching parent snapshot and completed
firmware/CPU evidence:

```bash
python3 -B tools/prepare_spare_mixed_dual.py \
  --reference "$FROZEN_COMBINED_HOST_PARENT" \
  --startup-preparation "$MIXED_BOOT_CORE_PREPARATION" \
  --bounded-rv32 "$MIXED_BOUNDED_CPU_RUN" \
  --default-rv32 "$MIXED_DEFAULT_CPU_RUN" \
  --out build/vivado/spare-mixed-dual-new
```

Add `--source-copy` for any required archived CPU-model source. The output's
`run-mixed-snapshot.py` accepts the same `--preparation`,
`--preparation-sha256` and optional `--check-only` arguments as the original
runner. It rechecks the firmware/core/CPU binding before and after a full
implementation. Existing CH1-only source and host guards remain unchanged.

These are prepared sources, not completed bitstreams. Exact startup-aware
host helpers are prepared as described below. Package creation, dedicated
routed review and physical startup testing remain pending. The source-contract receipt is
`build/checks/spare-mixed-dual-snapshots-20261017/manifest.json`.

### Startup-aware host helpers

The matching host trees are prepared at
`build/handoffs/spare-mixed-host-c0172662-v1-20261017/host/` and
`build/handoffs/spare-mixed-host-c0172600-v1-20261017/host/`. They use separate
image/package guards from the original eight clock candidates. The startup
observer is `tools/check_startup_spare_<build-id>.py`; it retrieves the
embedded firmware's completed results and checks both channels, the exact
firmware identity, reset-default configuration and current readiness/ECC
state. It selects mailbox addresses but does not hold/release the CPU, upload
firmware, start calibration or clear error counters.

The runtime accepts that observer's receipt through the existing
`--calibration-receipt` argument. It rejects the old CH0-upload receipt and
requires unchanged live mailbox/phase/readiness plus the exact package and
firmware binding. CH0 is decoded with eight lanes and CH1 with nine. These
images do not use `calibrate_spare_<build-id>.py` or a separate CH0 firmware
upload.

After the new image is implemented, reviewed, packaged and loaded, run the
observer and bounded integration from its matching host tree:

```bash
python3 -B tools/check_startup_spare_c0172662.py \
  --package "$DUAL_IMAGE_PACKAGE" --transport jtag \
  --out build/startup/c0172662-new
python3 -B tools/run_spare_dual_integration.py \
  --build-id c0172662 --host-tree . --package "$DUAL_IMAGE_PACKAGE" \
  --calibration-receipt build/startup/c0172662-new/manifest.json \
  --transport jtag --out build/integration/c0172662-new
```

The JTAG commands require an existing exclusive XVC server. Use `chestnut`
on the Mac or `xdma` on a compatible Linux PCIe host. The matching Mac wrapper
defaults to LFM inference:

```bash
SPARE_PACKAGE="$DUAL_IMAGE_PACKAGE" SPARE_MODEL="$LFM_CHECKPOINT" \
  SPARE_OUT=build/mac-c0172662-new bash tools/mac_spare_c0172662.sh lfm
```

It checks identity, observes startup, initializes memory for inference and
runs matmul/LFM reference checks. The optional `quick` stage uses only the
bounded DMA/masked-write/matmul runner. Package lookup supports either a
checkout layout or a packaged `host/` directory; environment variables can
select the package, Python, model and fresh result directory. The old manual
helpers continue to apply to the original eight clock images.

Preparation imports, shell syntax, bounded-runner host checks and original
package rejection passed at both rates. The saved CPU-model mailboxes also
passed the new startup decoding/receipt flow, with eight rejection cases per
image and no host startup-control or memory writes. Those are firmware-only
fixtures with zero image hashes and no `.bit`; they do not prove acceptance
of a completed image package or physical startup. The receipts are under
`build/checks/spare-mixed-startup-host-model-v2-20261017/`. The first fixture
attempt omitted the fake CSR registry required by the existing API; its
failure is preserved separately.

Reproduce an isolated host preparation using its exact original parent host
tree:

```bash
python3 -B tools/prepare_spare_mixed_host.py \
  --preparation "$MIXED_FULL_IMAGE_PREPARATION" \
  --template "$EXACT_PARENT_HOST_TREE" \
  --out build/handoffs/spare-mixed-host-new
```

### Routed collectors for automatic-startup images

The matching artifact/CDC/Gray-pointer/source collectors are prepared under
`build/checks/spare-mixed-review-c0172662-v1-20261017/` and the corresponding
`c0172600` directory. Their numerical and routed checks retain each parent's
main-function contracts after accounting for the new identity, result status
and exact core guard. The guard accepts the selected mixed-width core and
rejects its original CH1-only parent. The source collector binds the unchanged
host/reset model through its preserved descriptor; it does not assume an
unprovided model file exists in the new preparation's root.

`opentpu-spare4gb-mixed-startup-review-complete-cdc-20261017.service` is waiting for
the exact mixed-startup build owner. It collects each completed variant in
order, using one Vivado audit at a time while the later build can continue.
Its schedule and logs are under
`build/checks/complete-cdc-review-stream-mixed-startup-20261017/`. Failed implementations are
recorded rather than approved. Every actual CDC row, clock, fanin and skew
group still needs an explicit per-image disposition before packaging.

Reproduce preparation from a matching parent review directory:

```bash
python3 -B tools/prepare_spare_mixed_review.py \
  --preparation "$MIXED_FULL_IMAGE_PREPARATION" \
  --template-review "$EXACT_PARENT_REVIEW_PREPARATION" \
  --out build/checks/spare-mixed-review-new
```

The output manifest lists four commands: artifact/timing collection, CDC,
CSR Gray-pointer review and source comparison. CLI imports and source
contracts passed; actual routed collection remains pending. The contract
receipt is `build/checks/spare-mixed-review-contracts-20261017/manifest.json`.

### Exact automatic-startup packaging

Packager scripts are prepared under
`build/checks/spare-mixed-packager-c0172662-v1-20261017/generated/` and the
corresponding `c0172600` directory. They retain all 40 parent routed approval
assertions, with the new build identities, result types and automatic channel
mask. Existing implementations are rejected. The packager requires the actual
completed image, artifact/Gray reviews and a complete explicit CDC disposition;
preparing the script does not create an image package.

The startup payload includes its exact RV32 binary/ELF, firmware source and
configuration, the seven-case host review and both completed CPU-model
receipts, RTL, initialization data and simulation artifacts. Source mappings
preserve the hashes of the original model inputs, including the archived
bounded-runner version. The CPU simulation libraries are evidence files;
Mac inference does not load them. The exact-image startup-aware host tree and
its mailbox-model receipt are included alongside the adapter/reset evidence.

The actual startup copier produced firmware-only fixtures accepted by both
matching host bindings. Those fixtures have zero image hashes and no `.bit`.
They do not constitute a positive image-package acceptance or a physical
startup result. Receipts are under
`build/checks/spare-mixed-startup-copy-20261017/`; assertion/source contracts
are under `build/checks/spare-mixed-packager-contracts-20261017/`.

Prepare scripts for a fresh exact source/host/review set:

```bash
python3 -B tools/prepare_spare_mixed_packager.py \
  --preparation "$MIXED_FULL_IMAGE_PREPARATION" \
  --host-tree "$MIXED_EXACT_HOST_TREE" \
  --host-model "$MIXED_HOST_MAILBOX_MODEL_RECEIPT" \
  --review-preparation "$MIXED_ROUTED_REVIEW_PREPARATION" \
  --out build/checks/spare-mixed-packager-new
```

After the required image reviews and manual CDC disposition pass, the
generated `package-dual-host-image.py` takes `--dual-preparation`, `--build`,
`--qualification`, `--cdc-review` and a fresh `--out` package directory. It
selects embedded startup data from the fixed source preparation; no external
CH0-upload firmware argument is used. Final exact host-profile acceptance and
source revalidation occur before the local package directory is published.
Packaging performs no hardware access or flash programming.

## Complete CDC detail coverage

All twelve current candidates use corrected review preparations under
`build/checks/saved-skew-<build-id>-20261017/review/`. The original ten exact
packagers remain under `build/checks/complete-cdc-<build-id>-20261017/packager/`;
the two reset corrections use
`build/checks/spare-registered-complete-cdc-<build-id>-20261017/packager/`.
The earlier preparation directories in the generation examples above remain
templates. Use the corrected directories for collection and packaging.

The historical CDC reader required leading whitespace before a detail-row
number. Vivado's three-character number field loses that padding at row 100,
so larger detail tables were partially skipped. In c0172400's raw report it
read 708 findings instead of 1,995, omitting 1,287 warning rows. The corrected
`tools/cdc_report_rows.py` accepts all row numbers and requires detail counts
to match the report's Critical/Warning summary. Checks cover actual reports,
rows 100 and 1,000, and rejection of a report with a missing detail row.

The completed c0172080 and c0172300 PCIe-only OOB reports each retain all
116 findings with both readers. No combined-host candidate had been approved
or physically tested using the incomplete reader. The three former review
streams were stopped and superseded; the FPGA build queues continued unchanged.

The replacement workers preserve their exact build-owner identities and use
one audit at a time within each stream:

| Stream | Current service |
| --- | --- |
| Four original combined-host candidates | `opentpu-spare4gb-dual-host-review-saved-skew-20261017.service` |
| Immediate baseline reset correction | `opentpu-spare4gb-registered-reset-review-baseline-first-20261017.service` |
| Faster reset correction | `opentpu-spare4gb-registered-faster-review-baseline-first-20261017.service` |
| Four faster-DDR experiments | `opentpu-spare4gb-overclock-review-baseline-first-20261017.service` |
| Two automatic-startup variants | `opentpu-spare4gb-mixed-startup-review-baseline-first-20261017.service` |

For fresh preparations, freeze the corrected consumers before running them:

```bash
python3 -B tools/prepare_complete_cdc_review.py \
  --review-preparation "$ORIGINAL_REVIEW_PREPARATION" \
  --out build/checks/review-complete-cdc-new
python3 -B tools/prepare_complete_cdc_review.py \
  --packager-preparation "$ORIGINAL_PACKAGER_DIRECTORY" \
  --out build/checks/packager-complete-cdc-new
```

The original packager directory must contain `package-dual-host-image.py`.
Keep `cdc_report_rows.py` beside each frozen consumer. These clones preserve
the implementation/numerical gates and every packager check assertion; they
replace the reader and result paths. All ten packagers were checked at runtime
against the complete 1,995-row report. Actual OOB/Gray/fanin/skew collection and
an explicit disposition of every finding remain required before approval.

Evidence: `build/checks/complete-cdc-parser-20261017/`,
`build/checks/complete-cdc-preparations-20261017/` and
`build/checks/complete-cdc-consumers-20261017/`. The preliminary raw report
inventory is `build/checks/spare-dual-c0172400-preliminary-20261017/raw-cdc-inventory-v2.json`;
it is not a CDC approval.

### Saved collection aliases in checkpoint constraints

Vivado can save a `get_cells` collection in an `_xlnx_shared_iN` variable and
use that variable in `set_bus_skew`. The first complete-row baseline audit
finished its Vivado commands but its Python checker rejected the mailbox
bound because it searched for literal endpoint names in the command. The
constraints were present; this was a checker-format failure.

`tools/spare_dual_saved_constraints.py` resolves supported collection aliases
within their saved scope, rejects undefined or unsupported forms, and then
runs the original coverage checks unchanged. The actual 62 constraints retain
28 native-memory groups, two mailbox groups and 32 IP groups. The proof also
rejects a wrong bound, a missing alias definition and an incorrect endpoint.
It does not approve the reset crossing or any other CDC finding.

To extend a complete-row review preparation in a fresh directory:

```bash
python3 -B tools/prepare_spare_saved_skew_review.py \
  --review-preparation build/checks/review-complete-cdc-new \
  --out build/checks/review-saved-collections-new
```

The current streams bind this corrected collector. The previous streams
are preserved as superseded evidence; implementation jobs were not restarted.
Their proof and initial launch records are
`build/checks/spare-saved-skew-reader-20261017/manifest.json` and
`build/checks/spare-saved-skew-review-workers-20261017/manifest.json`. The later
priority-queue launch record below supersedes the overclock/startup workers.

### Additional routed host-boundary evidence

`tools/collect_spare_dual_boundary_facts.py` opens a completed checkpoint and
records the combinational cones of every critical endpoint, primitive/clock
and control facts for every scalar CDC endpoint, and the existing twelve
host-synchronizer and two held-payload timing checks. It preserves the
checkpoint and constraints. Use a fresh output directory:

```bash
python3 -B tools/collect_spare_dual_boundary_facts.py \
  --preparation "$DUAL_PREPARATION" \
  --out build/checks/dual-host-boundaries-new
```

This supplements the exact image's mandatory artifact/OOB/CDC/Gray collection.
It does not replace that collection, issue a CDC disposition, approve a
package, or test hardware. The first execution targets the already built
c0172400 baseline, now selected for the first new physical baseline test.
That execution completed with 4,148 distinct scalar endpoint records covering
all 1,995 raw findings, eight distinct critical destination cones, twelve
host-synchronizer checks and two passing mailbox payload bounds. Its evidence
is `build/checks/spare-dual-c0172400-boundary-facts-20261017/`. The mailbox
request path has 19.039 ns slack against a 20 ns bound; the response path has
332.245 ns slack against a 333.333 ns bound. These are raw-checkpoint results,
separate from the mandatory OOB checks and the pending manual disposition.

### Source-reset decode review finding

The routed c0172400 fanins confirm that `host_reset_sync_reg[0]/D` receives
the combinational nonzero decode of the seven-bit reset counter, along with
configuration/lock state. The existing functional reset test checks stable
values after source-clock edges. It does not test differing arrival times
of counter bits at the destination clock domain.

A separate model supplies a 500 ps intermediate zero during a `64 -> 63`
counter transition. The original source admits a one-cycle destination reset
release; a registered source reset does not. Both versions pass the original
functional reset sequence. This is a logical counterexample under an explicit
skew assumption, not a routed-delay simulation, a measured pulse width, or an
observed FPGA failure. The initial test fixture missed the destination edge;
its failure is preserved separately from the corrected v2 model.

The correction is in `rtl/boards/ypcb-00338/otpu_host_reset_registered.sv`.
It starts asserted and registers the reset decision in the core domain, with
one additional source cycle before normal release. It preserves bounded
reset behavior when PCIe is absent. Existing frozen preparations and running
implementations have not been modified.

Evidence is under `build/checks/spare-host-reset-cdc-counterexample-v2-20261017/`
and `build/checks/spare-registered-host-reset-source-20261017/`. Two frozen
correction snapshots are now prepared:

| Snapshot | Parent | Clock setting | Implementation |
| --- | --- | --- | --- |
| c0172800 | c0172400 | 100 MHz / DDR800 | Synthesis running in an immediate baseline slot |
| c0172862 | c0172462 | 148.837 MHz / DDR1066 | First job in the remaining seven-image queue |

`tools/prepare_spare_registered_reset.py` derives each snapshot from a checked
parent. It verifies that the reset module is the only changed RTL file, keeps
the original numerical gate byte for byte, assigns a distinct image ID, runs
the functional/skew cases against the actual frozen module, and preserves the
new module in both the frozen source and fresh-generation overlay. These are
correction preparations, not additional compute-clock targets or approved
images. Existing frozen image contents remain unchanged. Reset recovery must
receive an explicit disposition before a combined-host image is approved.

The two correction snapshots now also have exact isolated host trees under
`build/handoffs/spare-registered-host-<id>-v1-20261017/host/` and complete-row
review/packager preparations under
`build/checks/spare-registered-complete-cdc-<id>-20261017/`. Both packagers
retain all forty check assertions, with check-function syntax identical to
the parent after image-ID normalization. Both actual consumers parse all
1,995 baseline CDC findings, and both host profiles reject the old image
package. These are preparation/negative-binding checks; no corrected bitstream
or positively accepted corrected image package exists yet. The receipt is
`build/checks/spare-registered-host-review-package-contracts-20261017/manifest.json`.

### Reset disposition and priority queue

c0172400's corrected artifact audit passed with +0.053 ns setup, +0.013 ns hold,
zero failing endpoints, complete routing and no unclocked or unconstrained
internal endpoints under the reviewed OOB clock model. Its CDC, Gray-pointer
and source collectors also completed. Collection does not approve the reset
contract: four actual CDC-10 rows originate in the decoded reset counter.

The explicit reset disposition withholds combined-host approval for that
source. It requires the registered-source implementation and a fresh routed
review, rather than a waiver based on the stable-edge functional model.
This is a model/routed-topology finding; no physical reset failure is claimed.
The receipt is
`build/checks/spare-host-reset-disposition-20261017/manifest.json`.
The user's c0172400 programming authorization remains recorded for that exact
image; it has not been transferred to the correction's new ID.

`opentpu-spare4gb-reset-baseline-20261017.service` now builds c0172800
immediately in an additional baseline slot. At admission, approximately 14.9 GB
of RAM was available after releasing the completed ET-SOC test's owned servers.
This temporary overlap permits three OpenTPU implementations, each configured
for two threads. The original four-image queue and its review continue unchanged.

`opentpu-spare4gb-after-reset-baseline-20261017.service` waits for both the
original four-image owner and the immediate baseline owner, then builds at most
two jobs at a time, checking available memory before admitting the second:

1. c0172862 faster reset correction.
2. c0173120, c0173130, c0173133 and c0173160 DDR-rate experiments.
3. c0172662 and c0172600 automatic-startup experiments.

All eight frozen source checks passed before launch. The former waiting
eight-image producer and its three waiting reviewers were stopped and preserved;
no implementation child or c0172400 review was interrupted. The
old experimental sources still contain the original reset circuit and need
that finding resolved before physical approval. Their build results alone
will not establish the correction.

Schedules and live job state are under
`build/fedora-vivado/spare-reset-baseline-20261017/` and
`build/fedora-vivado/spare-after-reset-baseline-20261017/`. Exact service
identities and the preserved receipts are in
`build/checks/spare-reset-baseline-priority-20261017/manifest.json`.
The progress refresh helper now selects these workers and all twelve review/
packager preparations, preserving the original authorization and evidence.
