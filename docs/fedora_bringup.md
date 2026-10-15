# Linux preparation and first hardware run

Current step-by-step instructions: [Vivado bitstream guide](vivado_bitstream_guide.md)
and [OpenXC7 bitstream plan](openxc7_bitstream_plan.md). See the live
[progress table](../progress.md) for current jobs and elapsed times. The dated
continuation sections below preserve earlier observations and attempts.

The first connection for this workspace is a separately powered YPCB card with
JTAG only. The MicroBlaze/vendor-MIG baseline in
`../ypcb_00338_1p1_hack/docs/FEDORA_BRINGUP.md` is available for diagnosis; the
current requested goal is the standalone OpenTPU USER2 JTAG image and correct
computation. The user now requests completion of the remaining native Vivado
hardware tests, followed by OpenXC7 synthesis and routing using the working
Vivado image as the reference.
PCIe is unnecessary for this first run.
MicroBlaze's MDM JTAG UART remains a separate transport.

## Current continuation, 2026-10-12

The [USB investigation](dlc10_usb_stability.md) records unexpected kernel-level
disconnects, a separately built and software-tested DLC10 alternate-setting
correction, and a scoped autosuspend experiment awaiting root installation.
The latest ten-minute hardware watcher expired without accessing the FPGA;
Fedora still had no enumerated adapter. The full physical model run is pending.

[OpenXC7 reference trials](openxc7_vivado_reference.md) exported and imported
the complete Vivado netlist successfully, then identified a tristate-only
OSERDES packer failure and missing MIG hard-PHY BEL coverage in the installed
backend/database. Full optimization now resolves the earlier MIG elaboration
warnings, but mapped MIG synthesis and backend PHY support remain incomplete.
The user approved continuing the full LiteDRAM implementation against the
working Vivado MIG functional reference. Its independent synthesis inputs and
five corrected-backend gates were revalidated; an eight-thread full route is
active in `build/fedora-openxc7/litedram-vivado-reference-20261011T170600Z/`.
The initial placement iterations completed and main placement is running.
These actual results are distinct from the older failed/interrupted attempts.

## Latest physical result, 2026-10-11

See [Vivado JTAG hardware results](fedora_vivado_jtag_results.md) for the
current result and receipts. The DDR3-1066 native MIG image uploaded successfully
with INIT/DONE, passed all four full-capacity patterns on both 2 GiB channels
with zero readback/ECC errors, and passed the normal all-units and masked-write
compute kernels against the ISA simulator. The complete selftest stopped
during vector checks after the DLC10 USB disconnect at 14:48:03 HKT. Stream
checks and physical LFM2 inference were not reached. The failed selftest and
its XVC server are now terminal; restore stable USB before continuing.

The older DDR800 image and its failed channel-0 tests below are diagnostic
history. Its selected-image pointer is retained for rollback and does not
identify the image programmed for the latest successful memory/kernel tests.

## Original DDR800 image and diagnostic history

Vivado finished routing and bit generation on 2026-10-10 at 20:25:29 HKT. The
full DDR800/100 MHz profile retains MCOLS=4, ACT_ROWS=4 and LANES=8, with 716
DSP48E1s and both DDR channels. All 243 pin/standard pairs were checked, and the
image has zero routing and DRC errors. Setup, hold and pulse-width checks pass;
all 30 bus-skew constraints are met. The image is 11,599,613 bytes, SHA256
`a0a2b5cb2f410b0db7426aaef5d1b603d3c84a30c14a362bf8de61ca835b0a73`.

The selected manifest is `build/fedora-vivado/jtag-current.json`, a symlink to
`../bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-route-bitstream-20261010T121007Z/manifest.json`.
That run also preserves `output/design.bit`, the routed DCP, implementation
reports, native image-check receipt and programming rejection checks.

This is a prepared test candidate. Two CDC-10 Critical findings remain on the
software-reset logic feeding the eight-stage MMCM/PLL reset chains; eight
memory-removal synthesis warnings remain unresolved. Internal timing passed,
but external DDR timing and full-memory integrity remain unqualified.
The card was connected on 2026-10-10 at 21:38 HKT, and this Vivado image was
loaded into volatile SRAM successfully at 21:39:51 HKT. A fresh scan identified
one XC7K480T (`0x23751093`); loader INIT/DONE checks passed. Physical USER2 SMI
reports the expected profile and both calibration bits set. The first full
memory scrub/check failed on channel 0 byte lane 6. Channel 1 subsequently
passed full 2 GiB zero and random-data BISTs. Channel 0 is under calibration
diagnosis. Small vector and matrix computations now match the ISA reference
bit for bit on the FPGA; full-memory and README model qualification remain
incomplete.
OpenXC7 remains stopped. Evidence is in
`../build/fedora-vivado/physical-jtag-20261010T133821Z/`.

Latest state, 2026-10-11 08:03 HKT: DLC10 USB recovered after the user's
reconnection and device-only resets. It enumerated at 480 Mb/s; staged firmware
initialization freshly detected exactly one expected FPGA (`0x23751093`, IR 6).
The independent supplied Vivado MIG SRAM image was loaded. A halted MicroBlaze
with data cache disabled checked 1 KiB at offsets 0, 1 GiB and 2 GiB minus
4 KiB on both channels, with zero, ones and deterministic random data and three
read repetitions. All 54 read cases had zero wrong words and zero corrected or
uncorrectable ECC events after documented status/counter clears. ECC stayed
enabled. Initial writes to previously untouched samples reported ECC events;
those are retained in `data-review.json`. Sparse traffic does not qualify all
4 GiB or dense-load margin. These results make the OpenTPU controller/timing
path the leading suspect, without proving a board or power fault absent.

XADC measured VCCINT 0.991–0.992 V, VCCAUX 1.802–1.805 V and VCCBRAM
0.991–0.993 V across the pre-probe and MIG samples. These readings do not
measure the 12 V input, DDR rail or drawn current. The reported bench supply
settings remain 12 V and a 2 A limit; actual draw and CV/CC state are unknown.

The selected original native OpenTPU SRAM image was restored with INIT/DONE
set. Fresh full 2 GiB zero/random/address reads still failed channel 0, with
167,634 / 3,579,775 / 755,542 bad beats, all on byte lane 6. Channel 1 had zero
errors for all three full patterns. A temporary calibration-CPU CSR probe
matched all 54 host comparisons; it found no reporting mismatch. The exact
original firmware was restored and fully verified, the CPU remains held,
and its PHY settings were unchanged. No bounded compute cases were rerun in
this probe; the earlier fourteen-case pass remains partial evidence. Physical
README model inference is NOT_RUN. No flash, global-reset CSR or DRAM_INIT
marker override was written. Hardware clients have been stopped.

Receipts are in
`build/fedora-vivado/physical-jtag-20261010T133821Z/cold-power-retest-20261010T155620Z/vendor-mig-probe-20261010T233827Z/`,
including `current-review.json`, `data-review.json`, `native-retest/memory-result.json`
and `calibration-csr-probe/result.json`. The original failed USB probe directory
is historical. The user resumed the goal. An isolated Vivado MIG native-interface
candidate is being prepared in
`build/fedora-vivado/mig-jtag-controller-20261010T235833Z/`, using the supplied
DDR3-1066 dual-channel ECC pin/profile XML. IP generation completed; integration,
synthesis/route, complete DDR/ECC tests and model verification remain required.
The selected native manifest and physical image are unchanged.

Two separate SRAM loads reproduced channel-0 lane-6 errors; channel 1 passed
its full-memory patterns on both loads. The later 256 MiB calibration scan
rejected the original DQS phase and two nearby phases, finishing at 22:21 HKT
with no qualified setting. Experimental firmware/clocks are restored by a
fresh selected-image SRAM load. The full pin maps match the vendor MIG project
on both channels. A separate lower-clock diagnostic was tested;
its retained DDR800 firmware/identification/refresh values mean it must not
be treated as a qualified operating profile.

The clock diagnostic reproduced channel-0 lane-6 errors; channel 1 passed its
full patterns again. The original DDR800/100 MHz SRAM image was subsequently
restored successfully. A region scan failed lane 6 throughout channel 0, and
normal JTAG readback near its top returned wrong data. The failed scrub gate
and DRAM_INIT state have not been bypassed.

`build/fedora-vivado/physical-jtag-20261010T133821Z/bounded-compute.py` provides
a limited hardware proof using explicitly initialized and verified buffers.
Five vector runs returned 32 values of 12 for `3 * 4`; three MXU runs of ones
matrices (4x128 times 128x4) returned 16 values of 128. Six additional quantized
MXU runs used two deterministic sets of signed inputs, int8 weights and scales,
with three repetitions each. Every result and retired instruction count
matched the ISA simulator. All fourteen cases passed again after the fifth
original-image SRAM restore, finishing at 23:04:29 HKT. These are physical JTAG results,
not full-memory or model qualification. The JSON receipt and script record
the scope explicitly.

After the user resumed and clarified that only the DLC10 USB was replugged,
another original DDR800/100 MHz native SRAM load completed with INIT/DONE set
at 23:34 HKT. The first USER2 read failed with a USB overflow before any DDR
test. A software USB reset returned ENODEV on the old node; the cable
re-enumerated, and fresh initialization detected the expected single FPGA.
USER2 communication then worked without changing the XVC binary or bitstream.

The subsequent full 2 GiB zero, random and address tests completed on both
channels. Channel 1 had zero errors in all three. Channel 0 had 828,385,
11,134,271 and 4,765,597 bad read beats respectively, all on byte lane 6.
The fourteen bounded compute cases passed again, including all 32 buffer
initialization/readback checks. The XVC server stopped with exit 0 at 23:45
HKT; no cable owners remain and port 3721 is closed. Receipts and logs are in
`build/fedora-vivado/physical-jtag-20261010T133821Z/replug-retest-20261010T153130Z/`;
`build/fedora-vivado/replug-retest-current.json` points there. README model
inference remained NOT_RUN at that stage. A physical card power cycle and
power-source details had been requested. USB-only replugging and SRAM reloads do not cycle
the DDR power rails. No persistent flash was written.

The 23:25 HKT offline follow-up audited all 162 DQ/positive-DQS ports in the
SHA-verified native routed checkpoint. Lane 6 has the same clock sources,
serializer settings, 200 MHz input-delay reference and I/O properties as the
other channel-0 lanes. No lane-specific mismatch was found in this metadata;
external DDR timing and the physical cause remain unqualified. Evidence is
`build/fedora-vivado/physical-jtag-20261010T133821Z/offline-phy-audit-20261010T1508Z/result.json`.
The saved framing scans also have no zero-error point for any individual
lane-6 bit at the scanned settings (`lane6-perbit-review.json`). The later
USB-only replug retest above reproduced the same failing lane. The later
confirmed cold-cycle retest is recorded in the latest-state paragraph above.

At 23:51 HKT an offline ISA run prepared the LFM2.5-230M int8 reference using
the native device configuration, the model check's 256-token capacity and
eight-token limit. It returned `The capital of France is Paris.` with token
IDs `[1098, 5706, 803, 4481, 856, 5242, 523, 7]`, ending at EOS. All eleven
programs fit the 4,096-instruction IMEM. The receipt
`build/fedora-vivado/physical-jtag-20261010T133821Z/replug-retest-20261010T153130Z/lfm2-reference-result.json`
records the local checkpoint/tokenizer and source hashes. This run did not
access hardware; the FPGA has not produced these model tokens. Once full DDR
integrity passes on the restored native image, use:

```sh
build/fedora-venv/bin/python tools/fedora_jtag.py --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core selftest --model lfm2 --tokens 8 --wformat int8
```

The normal selftest must pass its memory and accelerator stages before its
physical model stage; the reference does not bypass the failing DDR gate.

The global software-reset CDC finding has a reproduced pulse-capture
limitation: the exact generated reset logic and sixteen FDCE instance bodies,
simulated with Vivado's installed primitive model, missed a one-cycle 100 MHz
reset pulse in one of the two tested 50 MHz sampling phases. Both clock-generator
chains were affected. Do not write the global-reset bit of LiteDRAM `ctrl_reset`
(CSR offset `0x2000`, host address `0x12000`) on this image; reload volatile SRAM
for a full FPGA reset. The calibration CPU's `selfcal_hold` is a separate
control. The experiment does not clear the CDC finding or qualify hardware.
Its source/model hashes, input files and commands are preserved in
`../../bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/native-reset-cdc-experiment-20261010T124442Z/`.

Check the native image without accessing hardware:

```sh
# Run from the root of your OpenTPU checkout.
bash tools/fedora_bringup.sh native-check --manifest build/fedora-vivado/jtag-current.json
```

The connected card's current goal is OpenTPU computation. The MicroBlaze
baseline remains available for DDR diagnosis using its documented
`scripts/fedora_soc.py run` command. The OpenTPU SRAM load is:

```sh
# Run from the root of your OpenTPU checkout.
bash tools/fedora_bringup.sh program-vivado --manifest build/fedora-vivado/jtag-current.json
```

This command verifies the completed native image before cable access, checks a
fresh single-device XC7K480T chain (`0x23751093`), rechecks image identity after
cable initialization and loads volatile SRAM. It does not write BPI flash.
Wrong-profile and changed-hash manifests were tested and refused before cable
access. The positive loading command passed on the connected card at 21:39:51 HKT.

After loading, start the prepared XVC server in a separate terminal:

```sh
# Run from the root of your OpenTPU checkout.
bash tools/fedora_bringup.sh jtag-server
```

Keep the server terminal open. Its quit prompt requires interactive stdin;
running it with stdin closed causes a clean immediate exit. The current
physical run uses a persistent PTY.

Use the generated DDR800 calibration data matching this native image. Its
existing directory name contains `fedora-openxc7`, but these commands use the
Vivado image and do not invoke OpenXC7 build tools:

```sh
# Run from the root of your OpenTPU checkout.
build/fedora-venv/bin/python tools/fedora_jtag.py --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core smi --json --no-i2c
build/fedora-venv/bin/python tools/fedora_jtag.py --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core memcal cal
build/fedora-venv/bin/python tools/fedora_jtag.py --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core selftest
```

Run these in order and preserve their physical output. Board identity and
calibration-status reads passed on the connected card. Full memory integrity
currently fails on channel 0 lane 6; the selftest stopped at scrub before any
compute stage. A calibration-ready bit alone is insufficient qualification.
MicroBlaze startup without PCIe still requires its powered-board test. The
following sections preserve preparation
and earlier build history; they do not supersede this native-image selection.

`memcal cal` waits for startup self-calibration and calibrates any channel left
unready. Bare `memcal` reports status only. The first-run sequence uses the
explicit calibration action before the compute tests.

A separate host runtime check on 2026-10-10 confirmed that Vivado Lab
2026.1.1 starts successfully and exposes the MicroBlaze MDM UART command.
It used an isolated SDK with the existing wrapper default installation.
The [saved startup result](../../bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/microblaze-xsdb-host-runtime-20261009T205847734298Z/receipt.json)
covers debugger startup and command help; physical CPU and DDR tests remain
pending.


This checkout is `5b1e646cdec9de449ba416952ec854b0b2d973d7`. Its upstream
board defaults are LiteDRAM DDR3-1066 and a 133.33 MHz core. The Fedora first-run
profile uses DDR3-800 and a 100 MHz core, retaining MCOLS=4, LANES=8 and
ACT_ROWS=4. The host reads the configuration from the hardware registers.
Leave `OTPU_MCOLS`/`OTPU_LANES` unset during a physical run.

## Host preparation

```sh
# Run from the root of your OpenTPU checkout.
bash tools/fedora_bringup.sh setup
bash tools/fedora_bringup.sh lint
bash tools/fedora_bringup.sh sim
```

The local Python environment is `build/fedora-venv`. Setup installs the project,
test tools and the CPU build of PyTorch plus Transformers/Safetensors; it does
not download model weights. The resolved package versions are recorded in
`build/fedora-python-requirements.txt`. The `sim` command drives the real
Verilator board model through the same host register/memory API. Its memory
and calibration are simulated; a passing result is not physical DDR evidence.
The Fedora `sim` helper builds the host C++ model with `-O0` to reduce compilation
time. It is for correctness checks, not simulator speed measurements. The
initial optimized attempt was stopped during compilation; its logs and the
compiler change record are preserved in `build/fedora-sim-compiler-plan.json`
and `build/fedora-*-initial-optimized.log`.
The cached precompiled headers from that attempt needed rebuilding for `-O0`;
the failed retry is preserved in `build/fedora-*-stale-pch.log`. Setup skips
eager Python bytecode compilation, which a live stack trace identified as the
long PyTorch installation step on this loaded host; imports compile as needed.

`build/fedora-board-lint.log` records the passing offline Tcl/XDC checks and
Verilator board lint. The PCIe inventory is in `build/fedora-pcie-check.log`.
No card was enumerated and the openTPU XDMA driver and its configuration were
not installed during preparation. `check` intentionally returns nonzero while
these required physical prerequisites are absent:

```sh
bash tools/fedora_bringup.sh check
```

The current preparation status and evidence paths are recorded in
`build/fedora-preparation.json`. The CPU-only random-weight Qwen3 construction
and forward check passed; its result is `build/fedora-model-smoke.json`.
The address-map tests passed all 20 cases in `build/fedora-address-map.xml`.
These are software checks; FPGA and physical-card results remain pending.

The staged Verilator selftest finished with `ALL PASS` and exit code zero in
`build/fedora-selftest-sim.log`. It covered both modeled memory channels,
partial writes, compute kernels, all VPU checks, STREAM modes and DSTEP.
Bandwidth measurement was skipped on the model, and no checkpoint/model stage
was requested. Simulated calibration does not establish physical DDR operation.

The initial host/ISA suite recorded 83 passes, five failures and one skip in
`build/fedora-host-isa.xml`; three simulator monitoring/trace/diagnostic tests
then passed separately in `build/fedora-host-model-tools.xml`. The saved trace
profile and diagnostic report are under `build/fedora-host-model-tools/`.
The diagnostic reported 23 passes and five skips on the model, including a
skipped physical PCIe link check. Four initial failures
concern halt latency or obtaining logits during a simulated run. All four also
failed an isolated rerun, recorded in `build/fedora-host-timing-recheck.xml`;
the original timing assertions remain unchanged. A subsequent probe found that
the ISA test card spent 95 ms preparing memory/events after starting its 60 ms
run clock (`build/fedora-stream-timeline-before.json`). Its clock now starts
after preparation. The fill-gating test, including its stale-logits control,
then passed; the four streamed-logits tests recorded three passes and one failure
in `build/fedora-streamed-logits-recheck.xml`. Both LFM2 streamed-decode contention
cases also passed in `build/fedora-lfm2-stream-recheck.xml`, covering the same
fixture's delayed-fill and held-run behavior. The remaining test's streaming
entry was 140 ms into a 60 ms modeled run
(`build/fedora-stream-timeline-probe.json`). Its logits comparison passed before
the assertion about streaming during the run failed. Host load and reported
CPU frequencies are saved in `build/fedora-host-load-recheck.json`, but they do
not establish the cause of those delays. The terminal rendering failure was
reproduced and fixed by awaiting each app-batched Markdown append before
measuring reply parts.
All three terminal UI tests then passed in `build/fedora-tui-tests.xml`.
The original failure logs are preserved; the suite is not yet an overall pass.

A later controlled-clock regression reproduced a host completion-hint bug:
the callback's processing time was included in the learned piece arrival time.
The host now records arrival before invoking the callback. A slow callback in
one run no longer prevents streaming during the next run. The regression failed
before the correction and passes afterward. The targeted recheck recorded 11
passes and two failures in `build/fedora-stream-completion-after.xml`; the ISA
logits comparison and fill-gating checks passed. The two halt-latency assertions
still fail at their unchanged 0.4 ms and 0.3 ms bounds. The source hashes and
before/after evidence are in `build/fedora-stream-completion-recheck.json`.
These are host software checks against a simulated card, with no physical result.

The subsequent poll correction learns from the last non-HALT read when sleep
overshoot prevents an exact observation. Streaming now checks without sleeping
within the same bounded end window as ordinary polling, then resumes sleeps
for unexpectedly long runs. The simulated card also copies aligned logits in
two channel assignments; its full byte-address and surrounding-memory checks
pass, including strided inputs. Event times and modeled values are unchanged.
The latest targeted run recorded 37 passes and one failure in
`build/fedora-host-polling-final.xml`. Both clock-skew cases pass; the streamed
HALT-latency check still fails against its original 0.3 ms bound. Its delay varies
on this host. Saved traces measure sleep overshoot and simulated status-read
work, but do not establish an exclusive cause. All 13 JTAG protocol checks pass
in `build/fedora-host-polling-jtag.xml`. Source hashes, regression results and
traces are indexed by `build/fedora-host-polling-recheck.json`. Full FPGA fit,
numerical timing qualification and physical operation remain separate gates.

The next correction reuses the first completed HALT read from streaming or a
host hook when finishing the run. It removes a redundant HALT poll and retains
the timestamp taken after the successful read. Outstanding writes, counters,
trace completion and hardware errors are still checked. Four regression cases
failed before the change; all 58 targeted host/JTAG checks now pass in
`build/fedora-first-halt-host.xml`, including the original latency assertions.
The isolated real-clock probe also passes; its records are in
`build/fedora-first-halt-after.json`. This establishes host/model behavior,
not physical PCIe latency. `build/fedora-first-halt-recheck.json` indexes the
source hashes and before/after evidence. The complete host/ISA rerun ended with
124 passes, one failure and one skip in `build/fedora-final-host-isa-recheck.xml`.
All three RTL model-tool checks passed. The streamed HALT-latency test failed
with a 0.812751 ms median against its unchanged 0.3 ms bound; the missing
LFM2.5-230M model caused the skip. `build/fedora-final-host-isa-result.json`
records the terminal result. The earlier targeted pass does not make this full
run a pass. Overall host timing validation remains incomplete.

A controlled-clock check then reproduced sleeps requested just before the
streaming polling window crossing into that window. Both cases failed before
the correction at the same 0.3 ms bound. Pre-window waits are now limited to
the time remaining before the window begins. All 60 targeted host/JTAG checks
pass in `build/fedora-stream-window-boundary-after.xml`, including both new
cases and the original real-clock latency assertions. The earlier full-suite
failure remains saved. A complete rerun, including the RTL model-tool tests,
finished with 126 passes, one failure and one skip after 46 minutes. The
streamed HALT-latency test passed. The short-program-after-long-program latency
test failed with a warmed-run delay of 1.302450 ms against its unchanged 1 ms
limit. The missing LFM2.5-230M model caused the skip. All 171 inventoried inputs
remained unchanged during this run. Its persistent
result is `build/fedora-stream-window-full-host-isa-result.json`;
`build/fedora-stream-window-boundary-recheck.json` records the active run and
source hashes. Overall host timing validation remains incomplete.

The real [LiquidAI LFM2.5-230M checkpoint](https://huggingface.co/LiquidAI/LFM2.5-230M)
is now prepared at `models/LFM2.5-230M`, pinned to revision
`40cb2ad3b3044d5a41eee083a6103c8b523afa45`. All eight files match the
upstream Git/LFS metadata, including the 459,401,112-byte safetensors file;
132 tensors are readable. Preparation evidence is in
`build/fedora-lfm2-model-prepare-fixed-20261008T070908Z/manifest.json`.
The initial preparation failure used an incorrect hidden-size assumption;
its source, log and failure report remain saved. The corrected run reused
the downloaded files and verified the model's actual 1024-wide configuration.

Four supplemental checks passed with no skips or changed inputs in
`build/fedora-lfm2-real-host-tests-20261008T071156Z/manifest.json`: the
previously skipped decode-profile test, the real model's 4K-context program
fit, all 16 resident attention-bucket programs on the test's two-column
configuration, and greedy ISA generation against Hugging Face.
The profile test uses a fake card; the token comparison
uses the ISA simulator and real weights. These results remove the missing
checkpoint condition. The earlier full-suite latency failure remains saved
and unresolved; this supplemental run is not a new full-suite pass.

A separate compiler check uses the complete four-column/eight-lane/four-row
profile with PAIR, DSTEP and STREAM, int8 weights/head and a 4K context.
All 16 resident programs fit: the largest has 1,526 instructions against
4,096 available, and the planned model image is 569,191,424 bytes within
4 GiB. The argument/address registers remain disjoint. Its report is
`build/fedora-lfm2-full-profile-programs-20261008T073621Z.json`.
This is full-profile model layout/compiler evidence; physical execution
remains pending.

The terminal failure is `test_a_short_run_after_a_long_one_is_seen_soon`.
A separate instrumented run of that unchanged test failed at
1.417 ms against the warmed-run 1 ms limit. The same test passed under two
controlled-clock scenarios, with zero and 2.1 ms sleep overshoot. These probes
do not establish the cause of the full-suite failure. Their results and source
fingerprints are indexed by `build/fedora-short-after-long-recheck.json`.
The original latency assertions remain unchanged.

A later bounded active-polling candidate reproduced voluntary-sleep latency
under controlled clocks, but failed the original real-clock case in both
focused runs: 65 passes/one cold-delay failure, then 66 passes/one warmed-delay
failure. The candidate is isolated and the production polling/test sources
were restored to the hashes of the completed 126-pass/one-failure run. Its
failed reports are indexed by `build/fedora-short-poll-recheck.json`; no full
rerun was started for this unvalidated candidate.

Analysis of the saved instrumented failure finds a 1.437 ms gap between the
last running-status read and the next voluntary sleep. Modeled completion
falls inside that gap; the observation was already 1.199 ms late before that
sleep started. Removing the final sleep cannot make this recorded run meet
the unchanged 1 ms warm limit. This does not identify the initiating host
condition or prove the cause of the separate full-suite failure. The analysis
and its unchanged source hashes are in
`build/fedora-short-after-long-assessment.json`. Further speculative polling
changes are deferred while the full FPGA implementation continues.

Recorded host observations on 2026-10-08 show all eight cores around 400 MHz,
below the exposed 1.4 GHz minimum despite the performance governor. The saved
SMU telemetry independently reports eight 400 MHz clocks, `PROCHOT_CPU` and
`PROCHOT_GFX` (raw mask `0x600`), with core temperatures around 49–50 C.
This constrains build performance, but does not establish the exclusive cause
of a particular failed latency assertion. The initiating protection condition
is unresolved. The raw observations are indexed by the completion audit.

Repeat this targeted selection without rebuilding the FPGA:

```sh
build/fedora-venv/bin/python -m pytest -q \
  tests/test_first_halt.py tests/test_fake_memory.py tests/test_stream_polling.py \
  tests/test_poll_learning.py tests/test_stream_completion.py tests/test_host.py \
  tests/test_jtag_transport.py \
  -k 'first_halt or fake_memory or stream_polling or sleep_just_before_window or poll_learning or slow_callback or streamed or halt_is_seen_soon_when_core_khz_is_off or jtag'
```

To repeat the complete host/ISA selection, including the three RTL model-tool
tests, use the local environment and the same model compiler settings:

```sh
MAKEFLAGS='--load-average=4 OPT_FAST=-O0 OPT_SLOW=-O0 OPT_GLOBAL=-O0' \
  build/fedora-venv/bin/python -m pytest -q tests/test_isa.py tests/test_host.py \
  tests/test_first_halt.py tests/test_fake_memory.py tests/test_stream_polling.py \
  tests/test_poll_learning.py tests/test_stream_completion.py
```

The model-tool tests can take substantially longer than the software tests.
The saved JUnit reports above retain the assertions and outcomes of this run.

The pinned XDMA driver source and kernel build artifacts are staged under
`build/fedora-pcie/`. The kernel-devel RPM is extracted locally rather than
installed, and its Fedora digest/signature verification is preserved in the
preparation log. Driver source is Xilinx `dma_ip_drivers` commit
`b8466090b4e812e191da9e9305ffb11cb7ace768` with this checkout's
`opentpu/host/pcie/xdma-otpu.patch`. Installing/binding the module is a separate
step on the eventual PCIe host, whose kernel may differ.

Rebuild the module without root privileges, installation or loading:

```sh
python3 tools/fedora_prepare_xdma.py
```

This uses the running kernel's installed headers, or downloads and verifies its
matching Fedora kernel-devel RPM and extracts it under `build/`. Its manifest
records the module hash, kernel vermagic and openTPU module tag. Use
`--kernel-root /path/to/kernel/build --kernel RELEASE` for an existing build tree.

## openXC7 build and standalone transport

The selected build route is now openXC7. `tools/fedora_openxc7.py` reuses the
native Yosys, Slang, nextpnr-himbaechel, exact xc7k480t chip database and Project
X-Ray installations already on this Fedora host. Each stage creates a fresh
directory under `build/fedora-openxc7/`, with input hashes, a RUNNING/PASS/FAIL
manifest, the exact command and log. No simulation/lint stand-in enters synthesis.
The earlier sv2v conversion exposed an array-reference frontend failure;
Slang reads the original SystemVerilog. Its hardware primitive declarations
come from the installed Yosys libraries, with behavioral bodies excluded.

```sh
bash tools/fedora_bringup.sh openxc7 check
bash tools/fedora_bringup.sh build
# Full accelerator + checked dual-channel DDR800 synthesis, using ABC's fast mapper.
# The mapped netlist still needs placement, timing and frame assembly.
# Later implementation, after synthesis:
bash tools/fedora_bringup.sh openxc7 jtag-route --netlist /path/to/synth.json
```

The standalone top is `otpu_fpga_top_openxc7_jtag`: MCOLS=4, ACT_ROWS=4,
LANES=8, systolic MXU, VPU_CL=2, DSTEP, both 72-bit ECC DDR3 channels
and their self-calibration CPU. The selected first-run profile regenerates
both channels and firmware for DDR3-800. Core and host interfaces use its
100 MHz clock, generated from the board's 50 MHz oscillator.
It needs neither a PCIe reference clock nor PERST. I2C remains connected.
The host reads the real internal XADC through its dedicated JTAG DRP
instruction; the fabric temperature capability is disabled because this
backend has no XADC placement resource. `Board.info()` and `smi` use that
physical sideband sensor. USER2 transfers control/CSR words or complete 64-byte DDR
bursts; the host merges partial updates before writing a whole beat.

The two RTL protocol benches passed: independent/stalled AXI handshakes,
register windows, 512-bit read/write payloads, errors and asynchronous mailbox
polling. A fresh Icarus rerun on 2026-10-10 passed both benches against the
current checkout; logs, compiled simulations and exact source hashes are in
`build/fedora-openxc7/jtag-rtl-live-20261010T1031HKT/`. Seven host-transport
tests and seven related host regressions passed.
Evidence is in `build/fedora-openxc7/{jtag-axi-test,jtag-mailbox-test,host-regression}.log`;
the later reconnect/voltage selection regressions are recorded in
`build/fedora-openxc7/host-vref-regression-final.log`.
On 2026-10-10, all 13 tests in `tests/test_jtag_transport.py` passed against the
fake mailbox, covering packet/range handling, sequence recovery, calibration
write guards and XADC-to-USER2 restoration. The saved log and JUnit report are
`build/fedora-openxc7/jtag-transport-pytest-20261010.{log,xml}`.
A fresh 10:36 HKT rerun passed all 13 tests with zero skips or failures. Its
log, JUnit report and post-test source hashes are in
`build/fedora-openxc7/jtag-transport-pytest-live-20261010T1036HKT/`; the
JUnit case count and all three source hashes were independently rechecked.
The broader `bash tools/fedora_bringup.sh check` ran at 10:38 HKT: Python and
OpenXC7 tool checks passed (`TOOLS_READY_BOARD_BUILD_NOT_RUN`), then the
combined command exited 1 at `otpu-setup --check`. That portion reported no
OpenTPU image, kernel headers, card-specific XDMA setup, PCIe card or JTAG
cable. This is the PCIe-host preflight finding for the current JTAG-only
setup; it does not test or invalidate USER2 JTAG. Its log and scoped result
are in `build/fedora-openxc7/host-check-live-20261010T1038HKT/`.
These are protocol/software results. Full synthesis, placement, routing,
timing, strict frame assembly and the physical card remain separate stages.
The first full board elaboration found three undriven variables in unused
VexRiscv feature cones. The build now lowers and removes unused logic before
its strict check; it does not replace those signals with arbitrary constants.

Full DDR800 synthesis passed on 2026-10-07. As of 2026-10-09, the full
implementation uses static placement with the corrected carry-padding, DSP
geometry, FF clock-edge, pinned-cluster and exponential-precision backend.
The broad completion audit at
`build/fedora-openxc7/current-completion-audit.json` is a historical snapshot
from 2026-10-09 22:16 HKT; it predates the native Vivado implementation run
described below. The full OpenXC7 static route then terminated unsuccessfully:
`otpu-full-static-exp-jtag-20261009t084508z.service` exited with status 1 at
2026-10-10 04:20 HKT. After iteration 656 and strict legalization of 300,727
cells, it failed to place a `SELMUX2_1` cell after 2,147,483,647 attempts.
The exact route log (`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/pipeline-full-static-exp-jtag-20261009T084508Z/route/route.log`)
and terminal pipeline manifest (`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/pipeline-full-static-exp-jtag-20261009T084508Z/pipeline.json`)
preserve the result. This route did not produce an OpenTPU image. The failed
service can be inspected with:

```sh
systemctl --user status otpu-full-static-exp-jtag-20261009t084508z.service
```

The similarly named `native-donor-crc-protected.bit` in the Bonetto build is a
CRC-test derivative of the SoDLA image, not an OpenTPU candidate; its
provenance record (`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/xc7-configuration-crc/validation-20261009T022614Z/native-donor-protected.json`)
identifies the source image.

The static placer needed two explicit double conversions in its wirelength
exponentials. The original numerical functions reproduced float overflow in
eight cases; all twelve corrected cases passed against an independent
long-double reference with UBSan. Fresh carry, upper-carry, DSP/FF routing and
strict-frame gates passed with the corrected binary. Actual full-design
initialization now passes and optimization iterations advance. Search limits,
full array dimensions, dual ECC DDR channels and the VexRiscv calibration CPU
remain unchanged. Full fit, routing, image assembly, numerical timing and board
operation remain unproven.

Historical observations of the static optimizer showed progress through
iterations 349,550 and 656, then strict legalization. The run's terminal error
above supersedes those intermediate observations; they do not establish legal
placement or timing.

The completed standard-ABC remap is separately adopted at
`build/fedora-openxc7/jtag-default-remap-verified-20261009T092326Z`.
Its native synthesis exited successfully. The original wrapper rejected a
renamed autogenerated BUFG cell; a separate audit verified its exact BSCAN
clock source and all 1,748 flip-flop clock sinks, including their parameters and
attributes. The original failure is retained alongside the verified adoption.
The candidate has 164,116 raw LUTs versus 183,414 in the original mapping, with
the same 717 DSPs and full DDR/memory hardware. Its full implementation config
is staged separately and has not launched a competing route.

The original board constraints are tracked separately from those twelve
LiteDRAM requirements. A complete-mapping audit records fifty-one statement
sites in the board XDC and its two unmanaged Tcl files: two clocks, seven false
paths, twenty-eight maximum delays and fourteen bus-skew constraints. It checks
all three complete mappings. In each, the core, both channels, host AXI and
LiteDRAM CSR clocks resolve to the same mapped system-clock bit; all 2,994
source-attributed channel/FIFO registers and the registers driving retained
channel signal aliases pass that exact clock check. This preserves ordinary
synchronous timing requirements and does not waive the original constraints.

The actual mailbox chains retain three stages per direction in both JTAG
mappings and two in PCIe. Forty-two corruption checks pass on the extracted
chains. The reports also retain both calibration stages, all five I2C inputs'
two stages, the sixteen LiteDRAM registers on the 50 MHz clock, complete held
payload widths and PCIe's two three-stage asynchronous reset chains. Mailbox
and I2C first-stage timing, payload settling bounds, reset recovery/removal and
numerical setup/hold qualification remain pending. No additional constraint
is applied by this audit. `board-cdc-complete-mapping-current.json` in the
Bonetto build directory indexes the actual reports and preserved failed
identity checks.

An isolated successor source now implements the original board I2C first-stage
cell exception. It changes only the existing XC7 capture-classification method,
requires distinct metadata bound to the original board XDC and exact selector,
and leaves clock inputs, launch outputs and second-stage registers subject to
their original behavior. Its extracted-method UBSan contract passes 2,700 board
cases and eighteen malformed-metadata rejections, plus the unchanged 271-case,
twelve-rejection DDR contract. All three actual complete-mapping selections
retain the five first stages and five later stages; twenty-one selection
corruptions are rejected. `xc7-board-i2c-first-stage-current.json` indexes this
source and its actual contract reports. These tests use the extracted method
with controlled API types. The real native backend build, packing and native
timing API checks have not run; the source is not selected by the running
full implementation.

Complete copies now add six explicit metadata fields to the five actual I2C
first-stage registers in each of the three full mappings. Readback verifies
that every byte outside those five attribute objects is unchanged; removing
the added fields restores each existing complete DDR copy SHA. The thirty-four
DDR annotations and all five untagged second-stage cells remain unchanged.
Seventy-one corruption rejections pass per complete mapping, 213 total.
`board-i2c-complete-copy-current.json` in the Bonetto build directory indexes
the copies and actual proofs. Native packing and timing API use remain pending;
these copies are not inputs to the running placement and qualify no timing.

An isolated native successor build is prepared with 3,145 frozen inputs and
ten rejected invalid configurations. It waits for the actual predecessor
build, all three native DDR API cases and complete-design packing gates. It
then recompiles only the changed XC7 source, reuses the fourteen actually
rebuilt declaration-dependent objects and all other exact native link inputs,
and saves compile/link/version evidence. Its live controller uses Nice=19,
CPUWeight=10 and the shared implementation lock.
`xc7-board-i2c-native-build-current-owner.json` indexes its configuration.
Native compilation and combined I2C/DDR API and packing checks remain pending.

All twelve original DDR timing requirements have concrete mapped endpoint
sets for both checkpoints. The first-stage CDC selector is retained on
register nets and resolves to 30 actual FDRE cells. A packing-binding checker
preserves original cell selectors, limits and clock-pin semantics, uses
`X_ORIG_TYPE`/`X_ORIG_PORT_*` provenance and retained net aliases, and verifies
actual constant drivers. Its existing routed-probe check covers 35 flip-flops,
175 port connections and eleven corruption rejections. Actual full packed
binding remains pending. These preparations apply zero timing constraints;
complete device min/max models and timing-engine support remain required.

Actual connection tracing now covers both original maximum-delay requirements
in all three complete mappings, including PCIe. Each of the 358 SERDES RST
endpoints connects directly to one selected write-leveling register Q; the
asynchronous reset constraint covers two direct first-Q to second-D connections.
No intervening LUT/mux or unresolved connection was found. The witnesses preserve
the register C/Q boundary and destination clock ports. Native clock-to-Q, routed
delays and applicable skew remain unmeasured, so the original 3 ns and 2 ns bounds
have not passed. AMD [UG903 Path Segmentation](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Path-Segmentation)
explains why replacing a C-pin start with Q changes timing semantics. The
`ddr-max-delay-connectivity-current.json` pointer in the Bonetto build directory
indexes the actual complete-cell graphs and preserved failed module-count check.

Separate copies of both complete mapped checkpoints now carry metadata for
the two original DDR false-path commands: all capture inputs of thirty
first-stage FDRE cells and PRE only on four FDPE cells. Decoded readback proves
that every original cell field is preserved; every byte outside those thirty-four
attribute objects is identical, and restoring the objects reproduces each
original checkpoint's SHA256. Twenty-eight corruption checks passed, including
an unrelated-byte edit in an actual full checkpoint. The rendering helpers and
receipts are in the Bonetto build directory; the current pointer is
`xc7-ddr-false-path-full-copy-current.json`. The standalone
`verify_xc7_ddr_false_path_copy.py` command accepts a rendering manifest, its
externally recorded SHA256, and a fresh output report to recheck the actual copy.
Native packing-preservation checks now pass for all thirty-four selected DDR
cells extracted from each actual full copy. Each case preserves all 170 port
bindings, original attributes and parameters, the string metadata, and the
clock/Q/PRE provenance; seventeen native-output corruption checks passed per
mapping. These are component checks with explicit cut-boundary drivers, using
the predecessor binary whose packer sources exactly match the queued backend.
They do not invoke the new timing override or prove either complete design's
packing. Evidence is indexed by `xc7-ddr-native-metadata-packing-current.json`
in the Bonetto build directory.
The isolated native backend rebuild remains queued behind the current full
implementation. Full native packing and timing-engine use of the metadata,
fresh route/frame gates and complete numerical timing remain pending. These copies
are not inputs to the running implementation and apply zero timing constraints
to it; the other ten original DDR requirements remain unimplemented.

A standalone native timing-API check is now prepared and queued behind that
exact backend build. It replaces only the CLI entry object and links the
recorded native architecture, packer, frontend and kernel objects. For each
mapping it will load and pack the actual selected-cell input, query all 170
ports before and after annotation, require 94 capture inputs to be ignored,
preserve 76 other ports and all 136 clocking-info records, and exercise twelve
native provenance rejections. Fourteen preparation rejection checks passed;
the existing input and packed artifacts also confirm all 34 cell names and
170 port names needed by the verifier. Its owner is
`xc7-ddr-native-api-current-owner.json` in the Bonetto build directory. Its
compile, link and actual native API checks have not run. This is a component
semantic gate; complete-design packing, the other DDR requirements, numerical
timing, fresh routed/frame checks and hardware operation remain pending.

The complete-design packing gate is separately prepared and supervised by
`otpu-full-ddr-native-packing-20261009t141120z.service`. It freezes forty-seven
inputs and requires all three actual selected-register API cases and the exact
native backend build to pass before taking the shared implementation lock.
Eight preparation rejection checks passed. It will revalidate each complete
metadata copy against its original bytes, pack the entire primary JTAG,
verified-default JTAG and PCIe designs with their original prepared pin/clock
XDCs, then check all 566 original DDR cells and 1,380 port bindings per mapping.
The checks also retain the full 717-DSP/SERDES/transport scope and thirty-four
exception targets. `full-ddr-native-packing-current-owner.json` in the Bonetto
build directory indexes its frozen configuration, preparation and live owner.
No complete native packing command has run yet; this gate does not prove
placement, routing, timing qualification, a bitstream or hardware operation.

The following records describe the preserved precursor runs. The two-slice
probe placed eight carries in the second
slice, verified four dedicated carry links and passed all 256 input patterns
for four outputs. Normal carry and 64-DSP/2,880-bit cascade/FF-edge regressions
also passed. All three probes passed strict frame assembly. These are small
backend correction tests; full placement/routing, image assembly, timing
qualification and physical DDR/compute remain unproven. The current run
reuses the completed full mapped checkpoint and fresh hash-checked gates.

The original managed controller session disappeared while its native placer
and route wrapper remained live. A systemd supervisor adopted those exact
processes after validating their identities and all 111 planned input hashes.
It waited for a verified route PASS before continuing strict frame conversion,
bit assembly and the independent checker. Synthesis and routing were not
restarted. The supervisor is now terminal with the failed original placer;
inspect the preserved service with:

```sh
systemctl --user status otpu-full-route-adopt-20261008t0400z.service
```

The historical pointer records this service. Its guard evidence is saved under the
selected build directory in `adopt-live-route-guards.json` and
`adopt-live-route-observation.json`.

At 2026-10-08 08:50 UTC, a bounded read-only snapshot of the same placer
captured 2,312,210 strict-legalizer calls and 167,850 remaining queue entries.
The call count includes repeated placements after cells are unbound and
requeued; queue entries are not a percentage-complete measure. The snapshot
and confirmed detach/resumed CPU activity are recorded in
`placer-member-counter-20261008T085007Z.json` under the selected build
directory. An earlier observer queried these class members as local variables
and failed; its report remains saved. The corrected observer reads the
members through `this`, with inferior function calls disabled. Placement
inputs, algorithms and the original process remain unchanged.

A second bounded snapshot at 10:42 UTC captured 2,522,238 legalizer calls and
165,959 queue entries, with the original process detached and resumed. The
slow queue reduction prompted a standard-ABC mapping comparison from the exact
full DDR800 `pre-lut.il`, under
`build/fedora-openxc7/jtag-ddr800-abc-default-remap-20261008T1059Z`. Its 45 input
hash guards and `resume-sequence-check.json` preserve the full profile and the
original post-checkpoint sequence while replacing ABC-fast with standard ABC.
The separate service `otpu-jtag-abc-default-remap-20261008t1059z.service` ran at
Nice=10. The remap is now terminal; its verified adoption is described above.
The original PCIe synthesis completed successfully on 2026-10-09; its actual
mapped resource and pin checks are described below. Full placement, timing
qualification and a full image remain unproven.

The remap had a separate image handoff service,
`otpu-jtag-remap-full-image-20261008t1225z.service`, also at Nice=10. It failed
its original process-identity guard and is retained as terminal evidence;
it did not launch an image build. Its control
records are in the Bonetto checkout under
`build/opentpu-placer-recovery-20261007T165149Z/jtag-remap-image-handoff-20261008T1225Z`.
The handoff checks 128 frozen inputs and the exact original synthesis processes,
waits for a successful terminal remap, and verifies the full-profile mapping
comparison before starting placement. It reuses the verified carry/DSP backend
and strict-frame assembly stages. Five rejection checks passed: partial profile,
reused PID, unfinished synthesis, changed input and duplicate image output.
The prospective full image directory is
`build/fedora-openxc7/jtag-remap-full-image-20261008T1225Z`; it is created only after
the remap passes. After assembly, the existing USER2 check and an independent
comparison of every legal configuration frame, ECC word and row-padding frame
must pass. CRC, timing qualification and physical operation remain unverified.

After the current full static JTAG image assembles, its driver runs the
independent static-backend checker and CRC preparation automatically. The base
image can also be checked explicitly with:

```sh
python3 ${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/check_static_exp_jtag_image.py \
  --pipeline ${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/pipeline-full-static-exp-jtag-20261009T084508Z/pipeline.json \
  --out build/fedora-openxc7/full-jtag-image-verification.json
```

For the verified standard-ABC candidate, use the output pipeline recorded in
`verified-default-full-prepared.json` in the Bonetto build directory, after
that implementation has actually run and assembled its full image. Its
current output directory has not been created. The historical
`tools/fedora_check_jtag_image.py` checker is bound to the earlier backend;
it is not the checker selected by the current static driver.
The checker binds the full mapped checkpoint, backend and all three correction
receipts to the route, USER2 selection, strict frames and exact bitstream. It
compares every legal frame, ECC word and row-padding frame. Its preflight
rejected the actual running pipeline, a partial profile and a premature stage;
the actual full mapped checkpoint and immutable backend receipts passed their
checks. The shared frame comparison code retains its cached 46,336-frame donor
validation and corruption-rejection evidence. A full OpenTPU image has not yet
been available for this check. CRC, timing and physical operation remain pending.

The original primary JTAG pipeline had a separate automatic validation service,
`otpu-primary-jtag-image-check-20261008t172414z.service`. It is now terminal
with the failed original implementation. It waited for the exact
original adopted supervisor to exit successfully and for the pipeline to reach
`independently-checked`, then runs the full checker above. It pins 11 checker
inputs and the original 111 planned-input hashes; changed inputs, a reused
supervisor PID, unsuccessful service exit, premature assembly and duplicate
watchers or reports are rejected. Sixteen handoff guard checks passed. These
checks cover the handoff, not the unfinished full image.

`build/fedora-openxc7/jtag-primary-image-check-current-owner.json` points to its
control directory in the Bonetto checkout. That directory contains
`preflight.json`, `state.json`, `supervisor.log` and, only after actual validation,
`full-jtag-image-check.json`. The service neither restarted the builds nor loaded
the FPGA. Inspect its preserved terminal state with:

```sh
systemctl --user status otpu-primary-jtag-image-check-20261008t172414z.service
```

[The carry-site plan](openxc7_carry_sites.md) and
`tools/openxc7_carry_sites{,_check}.py` preserve the correction and its checks.

The README's `make bit` quickstart uses Vivado and its board host path uses
PCIe. The openXC7 standalone flow above adds the build port and USER2 JTAG
transport needed for the separately powered first connection.

The current backend ignores bank `INTERNAL_VREF` and several Vivado timing
commands. Its FASM writer emits 675 mV for SSTL15, whereas the source constraints
specify 750 mV. `tools/openxc7_vref.py` resolves all 234 DDR pins and the eight
constrained banks against the actual package/tile database, corrects that known
selection and preserves the original FASM. It rejects missing VREF on populated
DDR banks, conflicting selections and unsupported voltage constraints.
Seven voltage-adapter tests passed. A voltage-only fixture also passed strict
Project X-Ray assembly; direct frame inspection confirmed the common/750 mV
bits set and the 675 mV bit clear in all eight banks. This fixture is not a board
design or a programming image. Its evidence is
`build/fedora-openxc7/vref-validation-20261006/validation.json`.

The read-only chipdb audit found just 12 timing variants: fabric LUT/FF,
carry/mux and BRAM modes. There are no timing variants for DSP48E1, OSERDESE2,
ISERDESE2 or MMCME2_ADV in this actual database. The default timing lookup
ignores cells without a variant, and missing MMCM arcs prevent clock-family
relationship tracing. This prevents qualification of DDR phase margins and
DSP paths from the current backend's Fmax report. The exact audit is
`build/fedora-openxc7/chipdb-timing-audit.json`; repeat it with
`tools/openxc7_chipdb_audit.py`. The available X-Ray DSP/I/O timing files are
Artix-7 data, so borrowing those values does not establish Kintex-7 speed-grade
signoff. `jtag-route` retains literal I/O properties, collects detailed timing,
applies the checked VREF correction and audits omitted constraints. Full-image
diagnostic assembly follows a successful route; timing qualification and
physical programming remain pending. No OpenTPU
`.bit` or physical DDR/compute pass is claimed. Failed attempts are retained.

The inherited 1066 Mb/s image uses internal VREF. AMD's
[DS182 Table 18 note 2](https://docs.amd.com/v/u/en-US/ds182_Kintex_7_Data_Sheet)
lists an 800 Mb/s limit for that choice. A separate first-run profile regenerates
both DDR channels and their real calibration firmware at DDR3-800, with the
controller/core at 100 MHz and the full compute-array dimensions retained:

```sh
python3 tools/fedora_prepare_litedram.py
# Use the generated core directory printed in that run's manifest:
python3 tools/fedora_openxc7.py jtag-elaborate --litedram-core /absolute/path/to/run/core
python3 tools/fedora_openxc7.py jtag-synth --litedram-core /absolute/path/to/run/core
```

The generator requires the Python environment pinned by `core.json` and a
compiler with an RV32I/ILP32 runtime. This host's environment is under
`build/fedora-openxc7/litedram-environment/`: Python 3.11.15, the three pinned
Migen/LiteX/LiteDRAM commits, and the reused `et-platform:sysemu-release` GCC
15.2.0. That image has an RV64-only runtime, so LiteX/Compiler-RT arithmetic
helpers are compiled as RV32I and linked with the firmware. The environment's
install commands, compiler wrappers, runtime build script, object-architecture
log and manifests preserve the rebuild inputs. The software-data packages are
`pythondata-cpu-vexriscv==1.0.1.post407`,
`pythondata-software-compiler-rt==0.0.post6206` and the version recorded in
`install.log` for `pythondata-software-picolibc`.

The Fedora `build` and `jtag` commands select the checked core associated with
`build/fedora-openxc7/ddr800-pipeline-active.json`, which references the current
full implementation. The `openxc7 check` and `openxc7 jtag-route` wrapper
commands select the verified backend from `implementation-active.json`.
Selection checks the full DDR800 parameters, passing normal/upper carry and
DSP/frame gates, the probe/backend binary identity and unchanged source
inventory. Explicit `OTPU_NEXTPNR` or `OTPU_NEXTPNR_SOURCE` overrides retain
the low-level helper's behavior. `openxc7 check` also uses the selected DDR800
core. Its current read-only result is
`build/fedora-openxc7/selected-backend-entrypoint-check-20261007T1905Z/manifest.json`.
This checks preparation inputs without starting another full build.
`build` uses the fast LUT
mapper on the full circuit. Supply `--litedram-core` or `OTPU_LITEDRAM_CORE`
to select another generated profile. An absent or invalid selected profile
stops these commands before synthesis or a JTAG connection; they do not fall
back to the upstream DDR1066 configuration. The low-level Python helpers keep
that original reference default for explicit diagnostic use.

Routing inherits the selected profile from the synthesis manifest. When this
image is eventually loaded, give the host the same profile:

```sh
tools/fedora_bringup.sh jtag --litedram-core /absolute/path/to/run/core smi
tools/fedora_bringup.sh jtag --litedram-core /absolute/path/to/run/core memcal
tools/fedora_bringup.sh jtag --litedram-core /absolute/path/to/run/core selftest
```

For the selected first-run image, the wrapper supplies that same directory:

```sh
tools/fedora_bringup.sh jtag smi
tools/fedora_bringup.sh jtag memcal
tools/fedora_bringup.sh jtag selftest
```

Calibration checks the loaded image's DDR_MTS against the supplied init
sequence before any calibration writes. The original 1066 files are retained
and remain the helper's default for the existing diagnostic build. See
[openxc7_qualification.md](openxc7_qualification.md) for the frequency choice,
the confirmed falling-edge timing defect and the remaining qualification work.

The existing loader's XVC server does not support XPCU/DLC10, and its cable
driver lacks the mixed TMS/TDI scan method. `tools/fedora_prepare_xvc.py`
captures the locally working loader and its existing USB/firmware fixes into
an isolated build under this checkout, then adds that method and cable case.
The donor checkout and binaries are preserved. The server binds to localhost
and propagates USB transfer failure to the client. The real cable encoder and
decoder passed a mocked-FX2 protocol test covering partial bytes, 640-bit
mailbox scans, non-byte-aligned multi-buffer reads and USB failure. This does
not establish physical cable operation.

```sh
bash tools/fedora_bringup.sh xvc-build
```

Once a JTAG image has been assembled and qualified, program its SRAM image,
then start the verified server in a separate terminal. The server helper
requires a matching binary hash and passing compile/protocol manifest, and
runs the existing DLC10 initialization/IDCODE checks first. It exposes the raw
single-device chain, which the transport checks against the expected IDCODE.
Then the normal host APIs can use the physical transport:

```sh
BIT=/path/to/qualified/otpu.bit bash tools/fedora_bringup.sh program
# Separate terminal; keep the server running:
bash tools/fedora_bringup.sh jtag-server
# Main terminal:
build/fedora-venv/bin/python tools/fedora_jtag.py smi --json --no-i2c
build/fedora-venv/bin/python tools/fedora_jtag.py memcal
build/fedora-venv/bin/python tools/fedora_jtag.py selftest
```

After the complete qualified USER2 image is loaded and its status/selftest
checks pass, the prepared checkpoint can use the same physical transport:

```bash
PYTHONPATH=. build/fedora-venv/bin/python tools/fedora_chat.py \
  --transport jtag \
  --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core \
  --prompt 'What is the capital of France? Answer in one sentence.' \
  --greedy --cap 256 --max-new 8 --wformat int8 --head-format int8
```

The entry point delegates to the existing chat interface and `BoardBackend`,
using `JtagTransport` or `PciePioTransport` in place of its direct XDMA open.
It checks the loaded full accelerator geometry, 100 MHz core and DDR800
readback before creating the model backend. `BoardBackend` performs the
existing calibration/ECC scrub and model loading flow; the wrapper closes
the backend and transport on exit. Model loading crosses the selected link,
so this serial path has no PCIe throughput claim. Physical model inference
has not run.

Eight modeled-board integration checks passed in
`build/fedora-physical-chat-validation-20261008T072602Z/manifest.json`.
They cover both transport selections, delegation to the actual `BoardBackend`,
geometry/clock/DDR-rate rejection before image writes, backend/transport
cleanup after an exception, and invalid CLI options. The modeled image is
64 bytes; these checks establish wrapper behavior, while real-model parity
is recorded separately above. Neither result establishes physical inference.

The transport verifies the selected Kintex-7 IDCODE and mailbox magic first.
On reconnect it continues after the retained completion sequence, so an old
response cannot satisfy the first command. The wrap/reconnect regression passed.
Both channels' whole 4 GiB ECC initialization and readback use LiteDRAM's
native BIST, with only CSR commands crossing JTAG. Initialization is recorded
only after both channels complete without errors. Selftest skips its PCIe
bandwidth threshold on this serial transport and reports that skip explicitly.
No physical command above has run in this preparation.

The eventual open PCIe path is pinned locally at
`build/fedora-openxc7/deps/pcie_7x`, commit
`cd1c33f53401d6ce1b6ec35da17884455477c2e9`. Its
[upstream YPCB GTX/openXC7 design](https://github.com/regymm/pcie_7x)
supports Gen2 x1, rather than the existing XDMA Gen2 x8 interface. A separate
full accelerator PCIe top now connects its BAR transport to control, calibration
CSRs and both complete DDR channels. It still needs full implementation and
physical validation. The prepared XDMA module applies to the original XDMA
image, not this alternative endpoint.

The pinned PCIe example advertises a 4 KiB BAR0 and instantiates
`axil_minimum`, a 256-word memory that decodes only address bits `[9:2]`.
It therefore aliases higher AXI addresses within that memory. It has no
OpenTPU control, LiteDRAM CSR or dual-DDR connection. The existing XDMA host
transport maps 256 KiB of registers and opens separate host-to-card and
card-to-host DMA devices. Neither that host interface nor its FPGA datapath
is supplied by the example. The integration below removes that stub; the
current full JTAG build remains the standalone first image and does not
provide PCIe.

### Open endpoint with full programmed-I/O access

`otpu_fpga_top_openxc7_pcie.sv` retains the full 4-column/8-lane accelerator,
both physical 72-bit ECC DDR channels, and the real calibration CPU/firmware.
Its 4 KiB BAR0 commands carry arbitrary 32-bit DDR byte addresses, so each
2 GiB channel remains fully reachable. `otpu_pcie_mailbox.sv` crosses the
PCIe and DDR clocks, rejects changes while a command is busy, and retains
completion data/sequence/error status. The full 64-byte transfer engine
is shared with USER2. `PciePioTransport` provides the same Board API, including
unaligned read/modify/write and full-capacity native BIST scrub/check.
The [protocol plan](openxc7_pcie_plan.md) defines the register map and gates.

The matching host path uses Linux's uncached `resource0` mmap, supported by
the [kernel PCI sysfs interface](https://www.kernel.org/doc/html/latest/PCI/sysfs-pci.html).
An aligned volatile 32-bit helper supplies memory barriers and little-endian
word accesses. It verifies an explicit `10ee:0480` BDF, an enabled 4 KiB BAR,
an unbound driver, mailbox identity and ABI before submitting commands.
It does not enable devices, detach drivers or scan hardware automatically.
This is programmed I/O; it provides no vendor XDMA engine or bandwidth claim.

Prepare the pinned endpoint and local MMIO helper without hardware:

```bash
# Run from the root of your OpenTPU checkout.
python3 tools/fedora_prepare_pcie.py
python3 tools/fedora_prepare_pcie_mmio.py
```

Elaborate the complete design in a fresh output directory:

```bash
python3 tools/fedora_openxc7_pcie.py elaborate \
  --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core \
  --out build/fedora-openxc7/pcie-full-elaborate-new
```

The same helper accepts `synth --from-elaborated PATH/TO/elaborated.il` for
full synthesis in a fresh directory, reusing a successful checkpoint after
checking its full-scope witness, hash, complete source inventory, revision
and DDR/core parameters. PCIe Verilog is parsed with `-defer`; its real
endpoint wrapper is then loaded after Slang's port declaration. Otherwise
the unused default GTP branch or a blackboxed endpoint prototype can survive
the mixed frontend. The exported wrapper defaults match the reference YPCB
wrapper's GTX/Gen2/0480 overrides.

The initial failed elaboration remains in
`build/fedora-openxc7/pcie-full-elaborate-20261008T0600Z`. The first deferred
attempt passed the structural check but retained an endpoint blackbox; its
manifest in `build/fedora-openxc7/pcie-full-elaborate-deferred-20261008T0605Z`
is explicitly rejected. The stronger full-scope guard rejects it, and the
corrected endpoint check contains one actual `PCIE_2_1`, one `GTXE2_CHANNEL`
and no GTP channel. These results are in
`build/fedora-openxc7/pcie-parameter-probe`. The subsequent real-body run in
`build/fedora-openxc7/pcie-full-elaborate-real-20261008T0615Z` failed the
strict structural check on 11 undriven bits. Reviewed generated copies now
connect the GTX transmit controls, power-management acknowledgement and
eye-scan status, and select interrupt message zero with interrupts disabled.
The pinned dependency checkout remains unchanged; the endpoint preparation
manifest records each original and generated source hash.

The complete corrected elaboration passed in
`build/fedora-openxc7/pcie-full-elaborate-wiring-20261008T0632Z`. Its reachable
hardware includes one `PCIE_2_1`, one `GTXE2_CHANNEL`, 528 accelerator DSPs,
144 input and 214 output DDR serializers, four MMCMs and the real calibration
CPU. The checkpoint hash and all original/generated source hashes were
rechecked before starting full synthesis in
`build/fedora-openxc7/pcie-full-synth-20261008T064724Z`.
That synthesis ran under
`otpu-pcie-full-synth-20261008t064724z.service`; its manifest and
`build/fedora-openxc7/pcie-synthesis-current-owner.json` retain the launch
command and log. The terminal result is recorded in its synthesis manifest.
Elaboration proves complete hierarchy coverage;
implementation, timing and hardware validation remain pending.

Full PCIe synthesis completed successfully at 2026-10-09 12:19 UTC. Its
390,453,818-byte mapped checkpoint passed original/generated source and
DDR800 profile verification. The actual netlist contains 717 DSPs, 106
RAMB18E1s, 518 RAMB36E1s and 165,404 raw LUTs. Full mapped PCIe/GTX instances,
Gen2 x1 and 4 KiB BAR0 settings, DDR/accelerator resources, clock targets and
all 250 synthesized pad bits passed the preparation checks. Prepared inputs
are saved under
`build/fedora-openxc7/pcie-full-inputs-prepared-20261009T122602Z`; its
`pipeline.json` records `FULL_PCIE_IMPLEMENTATION_INPUTS_PREPARED_IMPLEMENTATION_NOT_RUN`.

The current synthesis-to-image handoff is supervised by
`otpu-pcie-pinned-exe-image-20261009t084118z.service`. It verified the exact
original synthesis's successful terminal result and is waiting for the shared
implementation resource held by the JTAG run. Its guard configuration, state,
log and future image directory are indexed by
`pcie-pinned-exe-image-current-owner.json` in the Bonetto build directory.
The original observer and its failure are preserved separately. Comparison
with the current static backend found identical packing, architecture and
HeAP code; the code differences are confined to the static-placement path.
The existing PCIe handoff therefore retains its verified HeAP backend.
Full native PCIe implementation, image checks and timing qualification
remain pending.

The completed full PCIe netlist also passed resolution of all twelve original
DDR timing commands: its endpoint package contains 566 actual cells and 1,380
port bindings, including thirty first-stage registers traced from ten annotated
register nets. Thirteen corrupted packages were rejected. The package is indexed
by `pcie-mapped-ddr-timing-current.json` in the Bonetto build directory. Full native
packing and application remain pending; this preparation applies zero timing
constraints and does not qualify numerical timing.

A separate complete PCIe checkpoint now carries only the two original DDR
false-path annotations on those thirty-four selected cells. Independent readback
confirmed all other 390,443,028 bytes unchanged and logical restoration to the
original full checkpoint hash. Twenty-eight actual-cell/whole-file corruption
checks and three wrong-top checks passed. Native packing of its actual selected
DDR component preserved all 170 ports and passed seventeen output-corruption
checks. The source remains unchanged; no complete-design packing or timing
application is claimed. `pcie-ddr-false-path-copy-current.json` in the Bonetto
build directory indexes the copy, source diff, failure and actual reports.

Its real native timing API case is prepared and supervised by
`otpu-pcie-ddr-native-api-20261009t132706z.service`, indexed by
`pcie-ddr-native-api-current-owner.json`. Six preparation rejection checks passed,
and the exact input/packed cell names and ports were verified. It waits for the
existing driver build and both JTAG API cases to pass, then uses that same real
executable and the shared implementation lock. Actual PCIe API execution remains
pending; the other ten DDR requirements, full timing, image and hardware checks
remain pending.

```sh
systemctl --user status otpu-pcie-pinned-exe-image-20261009t084118z.service
```

Prepare the complete PCIe top's pin constraints without hardware:

```bash
python3 tools/fedora_pcie_constraints.py \
  --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core \
  --out build/fedora-openxc7/pcie-constraints-new
```

`build/fedora-openxc7/pcie-constraints-20261008T0635Z/manifest.json` checks
all 250 top-level pad bits, including all 234 DDR bits. Ordinary GPIO keeps
the vendor's LVCMOS18 settings and LED ordering. The PCIe reference clock
and GTX differential pairs are checked against both the reference design
and the exact package pin table. These constraints still require validation
against the synthesized netlist, clock/CDC review and numerical timing
qualification before implementation can establish a usable image.

The separate PCIe implementation pipeline requires a terminal successful
full synthesis, matching original/generated source hashes, the exact DDR800
profile and the verified backend with its three correction receipts. It
checks the mapped PCIe/GTX instances, accelerator/DDR resources, 4 KiB BAR0,
Gen2 x1 settings, all 250 synthesized pad bits and the clock targets before
starting native placement/routing. Its `prepare` action saves those inputs;
`route` runs implementation; `build` also converts strict frames, assembles
the image and invokes the independent checker.

For a later manual rebuild, after the managed implementations have finished,
use a fresh output directory:

```bash
python3 tools/fedora_openxc7_pcie_pipeline.py build \
  --synthesis build/fedora-openxc7/pcie-full-synth-20261008T064724Z \
  --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core \
  --backend-selection ${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/pipeline-carry-sites-v2/pipeline.json \
  --out build/fedora-openxc7/pcie-full-image-new
```

`fedora_check_pcie_image.py` binds the bitstream, strict frames and full route
to that pipeline, checks PCIe/GTX configuration features and compares every
legal configuration frame, its ECC and row padding against the assembled
payload. CRC and numerical timing remain separate unqualified checks.
Full PCIe synthesis and input preparation have passed; native implementation
is queued and no PCIe OpenTPU bitstream has been built. The standalone JTAG
pipeline continues under its original owner.

The checker validation is saved in
`build/fedora-openxc7/pcie-image-checker-validation-20261008T065925Z/manifest.json`.
It compared all 46,336 legal frames, including ECC and row padding, against
the cached VeriGPU image and rejected a deliberately corrupted first frame.
It also rejected that donor's JTAG FASM and the then-unfinished OpenTPU
synthesis, and verified the selected backend's three correction receipts.
Mapped OpenTPU pin/resource validation has now passed on the completed
synthesis. The complete PCIe image check remains pending until implementation.

Protocol revalidation, using the already prepared host environment:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 tools/fedora_check_pcie.py \
  --out build/fedora-openxc7/pcie-protocol-new
```

All 24 PIO/USER2 host checks passed, including 11 PIO checks and the compiled
helper on an ordinary mapped file. Both RTL benches passed: independent AW/W acceptance, byte
strobes, stalled B/R and TLP completions, asynchronous command/data ownership,
busy rejection, reset, sequence wrap, AXI errors and final addresses of both
full channels. The checked command records every subprocess exit, source
hashes, JUnit and raw logs in a fresh directory; it rejects skipped host cases
and absent RTL completion markers. Current results are indexed by
`build/fedora-openxc7/pcie-protocol-20261008T0608Z/manifest.json`.
The TLP bench uses the actual pinned packet decoder and AXI
bridge; AXI responses are modeled, so this is protocol evidence rather than
DDR, GTX or PCIe physical evidence. Full synthesis and mapped resource/pin
checks have passed. Placement/routing, PCIe clock/CDC constraint qualification,
strict frames, timing and a PCIe image are still pending. Nothing has been
programmed or enumerated on a card.

After those image gates and actual enumeration on a PCIe host, the prepared
transport entry point is:

```bash
PYTHONPATH=. build/fedora-venv/bin/python tools/fedora_pcie_pio.py \
  --bdf 0000:01:00.0 \
  --litedram-core build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core smi
```

Substitute the card's actual BDF. The same entry point accepts `memcal` and
`selftest`; the generated calibration profile must match the loaded image.
The current separately powered JTAG setup cannot exercise this PCIe path.

After the complete PCIe image and its physical status/selftest checks pass,
the same chat wrapper accepts `--transport pcie-pio --bdf 0000:01:00.0` with
the matching `--litedram-core` and the model/prompt options above. Substitute
the actual enumerated BDF. The ordinary `otpu-chat --backend board` command
continues to select the original XDMA transport.

## Original Vivado build

Full Vivado 2026.1 is now installed at
`${VIVADO_ROOT}/bin/vivado`, alongside Vivado Lab. Its version
command succeeds after loading the interactive shell environment. An isolated
first batch preflight exited 42 before Tcl ran because no valid license was
found. That failure is preserved. The user-requested retry on 2026-10-10
(Hong Kong time) detected a valid BASIC license and completed actual synthesis
for `xc7k480tffg1156-2` with exit 0. Its one-register probe verifies tool and
device access; it is not an OpenTPU synthesis or timing result.

[AMD's current 2026.1 licensing table](https://www.amd.com/en/products/software/adaptive-socs-and-fpgas/vivado/vivado-licensing-options.html)
lists 7 Series support in the free BASIC tier with annual renewal. The older
paid-license requirement in the upstream board guide should be checked against
that current table. The successful retry is recorded in
`vivado-2026-native-retry-20261009T155933Z/receipt.json` under the Bonetto build
directory.

The user selected a full Vivado reference first, then openXC7. The prepared
standalone USER2 JTAG reference snapshots all 31 exact source/data files from
the original full DDR3-800 synthesis, with MCOLS=4, ACT_ROWS=4, LANES=8,
VPU_CL=2, MXU_IMPL=2 and a 100 MHz core. It includes the real calibration CPU
and firmware. The original DDR XDC and memory-channel Tcl are retained;
recorded board changes remove absent PCIe/temperature selectors, deduplicate
the shared CSR clock query and add the JTAG mailbox constraints. Tcl structure,
source hashes and launcher syntax passed offline checks. The first full native
Vivado synthesis/export completed on 2026-10-09 22:33 UTC with exit 0. The
original run used the exact full generics and `general.maxThreads 1`; its run
log and actual scope report remain under
`vivado-full-jtag-reference-20261009T154026Z/` in the Bonetto build directory.
Its log still contains 44 constraint-command errors and 34 critical warnings,
so the generated checkpoint is a synthesis reference, not an implementation
or timing pass. The exported checkpoint, EDIF, Verilog and reports are indexed
by `vivado-full-jtag-reference-current.json`. The original user service ended
successfully; inspect its receipt with:

```sh
systemctl --user show otpu-vivado-full-jtag-reference-20261009t160758z.service \
  --property=ActiveState,SubState,Result,ExecMainStatus
cat ${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-reference-20261009T154026Z/native-command.exit
```

The persistent native monitor recorded the synthesis process identities,
CPU progress and log phases every 45 seconds. Its service has ended; its saved
`current.json`, `events.jsonl` and `terminal.json` remain indexed by
`vivado-native-monitor-current.json`. Its actual process-progress check passed.

The full native synthesis service started with CPU weight 10 and nice 19.
Its runtime CPU weight was first raised to 100 for the selected Vivado-first
priority; that command and its measurements remain recorded in
`native-vivado-cpu-priority-20261009T175504Z/` under the Bonetto build directory.
A later runtime adjustment raised the weight from 100 to 1000. The original
synthesis process has since exited successfully; the checkpoint review runs as
a separate read-only successor using the same saved FPGA source configuration.
The paired short samples delivered about 72% and 94% of one CPU respectively,
while all core clocks still reported about 400 MHz. A sustained speedup or
completion estimate has not been established. The later command, rollback
to weight 100 and scheduling measurements are recorded in
`native-vivado-cpu-priority-followup-20261009T185929Z/` under the same directory.
[Linux's CPU controller documentation](https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html#cpu-interface-files)
describes the weight as a relative share of CPU time during contention.

The launcher preserves a failed or completed attempt and refuses to replay it.
The first native stage produces a full synthesis checkpoint, EDIF, functional
netlist and reports; implementation and bitstream generation remain required
subsequent work. No FPGA programming command is included.

The full native JTAG synthesis completed with exit 0 and produced
`full-jtag-synth.dcp`, EDIF, functional Verilog and synthesis reports under
`vivado-full-jtag-reference-20261009T154026Z/` in the Bonetto build directory.
The frozen scope report records the full 4-column/8-lane profile, both 72-bit
DDR channels, 716 DSP48E1s and 562 RAMB36E1s plus 34 RAMB18E1s. The parent
Vivado log for this original reference records 44 constraint-command errors and
34 critical warnings. The scoped channel constraints searched for distinct
`uclk`/`xclk` clocks, but the standalone JTAG top ties `core_clk`, `xdma_aclk`
and both channel `uclk` inputs to `ld_sys_clk`. The corrected v2 implementation
copy binds those aliases to the retained `clk` clock and updates the top-level
constraint Tcl accordingly. Its pre-placement DRC reported zero errors; through
the 11:09:18 HKT log update, the corrected implementation log contains no
`ERROR` or `CRITICAL WARNING` entries. This addresses the missing-clock
constraint failures for this tied-clock JTAG profile; routed timing and CDC
reports still need review. The separate memory-removal warning review remains
open, as noted below. Synthesis success is not a routed image or timing pass.
The reference checkpoint, EDIF and Verilog exports completed by 06:33 HKT on
2026-10-10 with exit code 0. Their logged write times were 4:33, 1:11 and 2:36
respectively (about 8:20 combined); this export step is complete, while
placement is a separate, much longer implementation stage.

Actual read-only checkpoint inspection is running from the saved checkpoint in
`native-checkpoint-inspection-20261009T225142545555Z/`. The first collector
attempt is preserved in `native-checkpoint-inspection-20261009T223335871292Z/`;
it stopped because its guard compared Vivado's design label with the top-module
name. A fresh successor now checks the `TOP` property and uses four threads.
At 2026-10-09 23:03:42 UTC, Vivado had reopened the checkpoint and logged
`TOP=otpu_fpga_top_openxc7_jtag` and `PART=xc7k480tffg1156-2`; evidence
collection was active, with BRAM and primitive records not yet written. The
independent owner/CPU observation and continuation state are in
`native-inspection-followthrough-successor-20261009T225104987733Z/`.

The physical DLC10 XVC server is already built at the binary path recorded in
`build/fedora-openxc7/xvc-ready.json`. On 2026-10-10 at 10:59 HKT,
`bash tools/fedora_bringup.sh jtag-server --dry-run` rechecked the binary and
probe-firmware hashes and saved the exact initializer/server command pair in
`build/fedora-openxc7/jtag-server-dry-run-live-20261010T1059HKT.json` (SHA256
`07ce728641c9dd9b7402d0aa18d854b8e85f493ba268dc9a12359cac95d43801`). The host
USB list shows no JTAG adapter, so no chain scan or physical operation has run.
The standalone USER2 XVC host transport can carry OpenTPU commands and results
without PCIe, after a qualified image is loaded; serial JTAG has no PCIe
bandwidth claim.

After successful full synthesis, the collector saves BRAM initialization,
width and write-mode properties, BRAM pin connections, mapped hierarchy,
primitive counts, DDR ports, clocks and a deeper utilization report in a fresh
directory. Its JSON encoding and Tcl structure checks passed. Collection
still requires review: reconstruct all 4096 firmware words and their address
and data mapping, verify the full accelerator and calibration CPU, and explain
every `Synth 8-13374` memory-removal warning before routing. The collector
does not change the reference project or generate an FPGA image.

A physical BRAM initialization decoder is prepared in
`native-bram-decoder-preparation-20261009T195220Z/` under the Bonetto build
directory and indexed by `native-bram-decoder-preparation-current.json`.
At preparation time its guard rejected the then-running reference without
creating an output. Eight invalid-evidence checks passed. The successor's
owned controller runs the decoder only after corrected checkpoint collection
completes. The actual AMD UNISIM library comparison
then passed all 15 isolated RAM cases: 225,280 port/address reads through both
ports, covering all true dual port widths and all four complete firmware byte
lanes. Actual elaboration and simulation both exited zero; every case marker
and the final completion marker were verified. The result and full-firmware
fixture check are recorded in
`native-bram-decoder-conformance-result-20261009T201137Z/` under the same build
directory. The earlier failed elaboration and its logs are preserved; the
successful successor uses the required `xelab --mt off` option.

After actual checkpoint collection, `decode_bram.py` exports every captured
RAMB18E1/RAMB36E1 data and parity initialization plane to fresh binary files.
It requires complete initialization properties and unchanged actual source,
checkpoint and evidence hashes. The frozen source has one `u_ld` LiteDRAM
instance serving both DDR channels and one `VexRiscv` calibration CPU/memory.
Use the actual mapped pin connections and netlist to reconstruct all 4096
firmware words and both memory ports; raw initialization decoding and isolated
library fixtures leave full firmware wiring, accelerator scope, timing and
physical operation pending. Usage and the AMD memory-format references are
in that stage's README.

The native synthesis lists `selfcal_mem_reg` as 4K x 32 using four RAMB36
blocks; this is preliminary inference evidence. Eight memory-removal warnings
remain under review, including `i_26`. The earlier frozen collector preparation
recorded seven warnings and remains unchanged; its historical count does not
limit the current review. The current warning list and preliminary RAM report
are saved with the conformance result above. A partial source correlation for
one warning is not enough to close the full set. Review every warning and the
completed mapped netlist before treating implementation as qualified or
generating an image.

The corrected full native implementation is running in
`vivado-full-jtag-implementation-corrected-v2-20261010T001951Z/` under the
Bonetto build directory. Its pre-placement DRC reported zero errors. At the
2026-10-10 10:28 HKT live check, Vivado PID 1729232 remained active in
`place_design`, Phase 2.5.2 Physical Synthesis In Placer. The last placer log
update, at 10:24:05, contains a physical-synthesis summary of 2,301 LUT
combines, with no new cells and no DSP/BRAM register or high-fanout changes; it
does not establish a placement or timing pass. At 10:28 the process had
accumulated about 2h57m of CPU time over 2h06m elapsed and used about 5.3 GiB
resident memory. Host CPU pressure was elevated (CPU PSI `some` avg10 22.60,
avg60 37.24), while memory pressure was zero and 18 GiB remained available.
This confirms CPU activity but provides no reliable completion estimate. A
10-second `/proc` sample at 10:18 showed four workers each accumulating
3.55-3.84 seconds of CPU time; the process had no cgroup CPU quota or
throttling in that sample. Placement has not completed, and this run has no
placed checkpoint, routed result or bitstream yet.
At 10:40 the same process was still active in `place_design`; its log had not
advanced since the 10:29:07 Phase 2.5.2 completion line. Vivado's
`elapsed = 1:22:59` at that point is cumulative within `place_design`, not the
duration of Phase 2.5.2. The `.place_design.begin.rst` marker exists,
`.place_design.end.rst` is absent, and there is still no placed checkpoint,
routed result or bitstream. The process had accumulated about 3h20m of CPU time
over 2h18m elapsed and used about 5.3 GiB resident memory. CPU time continued
increasing while the log was quiet, confirming active computation but giving
no reliable finish estimate.

At 10:51 HKT the same worker (PID 1729232) remained live at 2h29m elapsed,
3h40m CPU time and about 5.1 GiB RSS. Its log advanced at 10:49:09 and recorded
`Phase 2 Global Placement` complete with 1:42:59 elapsed inside `place_design`.
The overall `place_design` run has not completed: `.place_design.end.rst`, a
placed checkpoint, routed output and a bitstream are absent. A fresh 10-second
`/proc` sample accumulated 1,457 CPU ticks (`CLK_TCK=100`, about 1.46 active CPU
cores), confirming it continued computing. No reliable finish estimate is
available.

At 10:54 HKT, Vivado had advanced into `Phase 3 Detail Placement`; the log
records `Phase 3.1 Commit Multi Column Macros` complete at 10:54:02, with
1:47:54 cumulative elapsed inside `place_design`. PID 1729232 was still live at
2h32m elapsed and 3h44m CPU time. The overall placement completion marker,
placed checkpoint, routed output and bitstream remained absent.
At 10:57 HKT the worker was still active at 2h35m elapsed, 3h49m CPU time and
about 5.1 GiB RSS. A fresh 10-second `/proc` sample accumulated 1,044 ticks
(`CLK_TCK=100`, about 1.04 active CPU cores). The log advanced at 10:57:50 into
`Phase 3.2 Commit Most Macros & LUTRAMs`, which had not logged completion by
10:58. Placement completion and image outputs remained absent. CPU PSI `some`
avg10 was 20.44; the worker was active but no completion estimate is available.
At 11:04 HKT the same worker remained live at 2h42m elapsed, 3h57m CPU time and
about 5.1 GiB RSS. It still logged `Phase 3.2 Commit Most Macros & LUTRAMs`,
last updated at 10:57:50; `.place_design.end.rst` and an output image remained
absent. CPU usage continued to increase while the log was quiet, confirming
active computation but giving no finish estimate.
At 11:05:40 the log confirmed Phase 3.2 complete, followed by completed Phase
3.3 Area Swap Optimization and Phase 3.4 Pipeline Register Optimization. A
30-second `/proc` sample ending 11:06:21 measured 1.78 active CPU cores. At
11:06:32 PID 1729232 remained live at 2h44m elapsed, 4h00m CPU time and about
5.1 GiB RSS. `.place_design.end.rst`, a placed/routed checkpoint and a bitstream
were still absent; the worker is progressing, but the log provides no finish
estimate. At 11:09:18 HKT, PID 1729232 remained live at 2h47m elapsed, 4h04m
CPU time and about 5.1 GiB RSS; the log had advanced to Phase 3.5 Fast
Optimization. At 11:14:56 HKT it was still in Phase 3.5, live at 2h52m elapsed
and 4h14m CPU time. A fresh 30-second `/proc` sample measured 1.30 active CPU
cores. At 11:15:22 HKT the log confirmed Phase 3.5 complete and entered Phase
3.6 Small Shape Detail Placement; PID 1729232 remained live at 2h53m elapsed
and 4h14m CPU time. `.place_design.end.rst` and bitstream outputs remained
absent. Placement is advancing, but there is still no reliable finish estimate.
At 11:35 HKT the log confirmed Phase 3.8 and all of Phase 3 Detail Placement
complete, then entered Phase 4 Post Placement Optimization and Clean-Up, Phase
4.1 Post Commit Optimization. At 11:36 PID 1729232 was still live at 3h14m
elapsed, 4h36m CPU time and about 5.3 GiB RSS. The placement completion marker,
routed checkpoint and bitstream were still absent. This is measurable progress;
placement, routing, report review and bitgen still remain, with no reliable
completion estimate. At 11:43 the same worker remained live at 3h20m elapsed
and 4h47m CPU time; the log had not advanced past Phase 4.1 since 11:35, but
CPU time continued increasing. `.place_design.end.rst`, the routed checkpoint
and a bitstream remained absent. At 11:45 the log advanced to Phase 4.1.1.1,
BUFG Insertion, and began the Physical Synthesis Task; Vivado reported up to
four CPUs for `phys_opt_design`. At 11:46 PID 1729232 remained live at 3h24m
elapsed, 4h53m CPU time and about 5.3 GiB RSS. Placement completion, the
routed checkpoint and a bitstream were still absent. At 11:47 the physical
synthesis initialization phase completed with estimated `WNS=0.157 ns` and
`TNS=0.000`; this is an intermediate estimate, not final timing signoff. At
11:48 the worker remained live at 3h26m elapsed and 4h57m CPU time. BUFG
insertion then finished after examining three candidate nets and inserting
none because of placement/routing conflicts; Phase 4.1.1.2 Post Placement
Timing Optimization began. Both `.place_design.end.rst` and
`.route_design.end.rst` remained absent. At 11:51 Phase 4.1.1.2 completed with
post-placement timing summary `WNS=0.539`, followed by Phase 4.2 cleanup. The
placer then warned that the design is highly congested and may have difficulty
routing. PID 1729232 remained live at 3h28m elapsed and 5h00m CPU time, with
`.place_design.end.rst` still absent. The WNS is not final timing signoff; the
congestion warning requires detailed analysis before qualification.
At 11:51:46 HKT the run log then recorded `place_design completed successfully`
with 79 infos, four warnings, zero critical warnings and zero errors. The
placed utilization report records `Design State: Fully Placed`: 145,841 LUTs
(48.84%), 47,376 slices (63.46%), 579 block-RAM tiles (60.63%) and 716 DSPs
(37.29%). The four warnings are the congestion warning and three 1 ps XDC
rounding notices. After the placement reports, the run wrote PlaceDB and
RouteStorage, then PlaceStorage, netlist/device caches and `Write Physdb
Complete` by 11:54 HKT. The Vivado worker remained active in this save phase;
no routed checkpoint or bitstream had appeared, and detailed congestion
analysis was still pending. At 12:06 the pre-route `phys_opt_design` step
completed successfully with estimated `WNS=0.539 ns`, `TNS=0.000`, no setup
violation and no netlist modification; the step reported 90 infos, four
warnings, zero critical warnings and zero errors. It wrote updated placement
and route databases. These remain pre-route results; routing and routed timing
are still pending. A separate one-thread `report_design_analysis -congestion`
run is reading a copied placed checkpoint from
`build/fedora-openxc7/congestion-analysis-20261010T1154HKT/`. Its SHA256 is
`0ce369486f97abecb480a07aea9a68359b4fb08fd2546e78e89b4272204cdcd4`, matching
the completed 82,508,855-byte source checkpoint. At 12:07 Vivado was still
loading that checkpoint and analyzing 18,146 UNISIM elements; no detailed
congestion report had been written yet. By 12:08 UNISIM translation had
completed and the analysis process was preparing the placed netlist. The main
run also wrote updated PlaceStorage and `Write Physdb Complete` at 12:08 after
pre-route `phys_opt_design`; a `route_design` command had not yet appeared.
At 12:09:41 the main log began `Starting Routing Task`, entered Route Phase 1
Build RT Design and reported up to four CPUs for `route_design`. This marks the
start of actual routing, not route completion.
At 12:15:42 HKT PID 1729232 remained live at 3h53m elapsed, 5h42m CPU time
and about 5.3 GiB RSS. Its CPU time continued increasing, but the route log
was still at Phase 1 Build RT Design; no routed checkpoint, route report or
bitstream existed. The copied-checkpoint congestion analysis also remained
live (PID 1768334, 20m elapsed, about 8m CPU time and 1.99 GiB RSS), still
preparing the placed netlist; `congestion.rpt` had not been written. These
processes are active, but neither provides a reliable completion estimate.
The first congestion-analysis attempt exited at 12:23:04 after loading the
copied checkpoint because its `current_design` name assertion did not match;
it produced no report and did not touch the implementation run. A retry uses
the same verified placed checkpoint (SHA256
`0ce369486f97abecb480a07aea9a68359b4fb08fd2546e78e89b4272204cdcd4`) and
checks the device part plus retained VPU hierarchy. At 12:25:40 the retry
process was live, still loading the checkpoint, with no report yet. The main
implementation log had advanced into Route Phase 2.1 Fix Topology Constraints
and Phase 2.2 Pre Route Cleanup; routing is still incomplete.
At 12:27:47 the route log had entered Phase 2.3 Update Timing; PID 1729232
was still live at 4h05m elapsed and 5h59m CPU time. The corrected congestion
retry remained in `open_checkpoint` (2m52s elapsed, 1m48s CPU, about 0.95 GiB
RSS), with no report or error yet.
At 12:29:33 PID 1729232 was still live at 4h07m elapsed and 6h01m CPU time,
with the log at Phase 2.3 Update Timing and CPU time continuing to advance.
The retry remained in `open_checkpoint` at 4m38s elapsed and 2m33s CPU time
(about 1.05 GiB RSS); `congestion.rpt` had not appeared.

The generated memory-warning paths do not appear as literal paths in the frozen
RTL. The hash-verified review referenced by the implementation manifest
confirms all eight targets are absent as exact names and descendants in the
saved mapped hierarchy and primitive inventory. That checkpoint retains the
VPU hierarchy, 716 DSP48E1, 562 RAMB36E1, 34 RAMB18E1 and both 72-bit DDR
interfaces. The review does not map the removed instances to specific source
functions, so it cannot establish that their removal is harmless or prove full
functional retention; keep all eight warnings open. The review is
`native-memory-removal-warning-review-20261010T075500HKT/review.json` under the
Bonetto build directory. At 10:45 HKT, host CPU pressure was high (CPU PSI
`some` avg10 45.92), so a second Vivado process was deferred to avoid
competing with placement.

A bounded RTL-versus-ISA check of `tests/test_se_vpu.py` completed on
2026-10-10 at 11:42 HKT: all 10 cases passed across both WBUF settings, covering
elementwise operations, reductions and stream overlap. Verilator and generated
C++ compilation were capped at one low-priority worker. The saved log is
`build/fedora-openxc7/se-vpu-rtl-isa-j1-20261010T1120HKT/pytest.log` (SHA256
`1b574e1d535bc616499034b6dcee99d04802ce6654611d58f9e4870ba405ae85`). This
source-RTL simulation is useful VPU functional evidence; it does not map the
eight removed synthesis instances to source functions, qualify the synthesized
netlist, or establish physical board operation. Keep those warnings open.

A fresh integrity check passed all 66 recorded
reference/constraint inputs, the synth log, implementation XDC and Tcl, and
the pre-launch project copy. Vivado has since rewritten the live project path
and launch metadata; the saved pre-launch copy still matches its manifest hash.
The run continues through routing and post-route physical optimization, then
saves timing, clock, CDC, bus-skew, exception, DRC and resource reports. Its
Tcl explicitly excludes bitstream generation. A routed result still requires
setup/hold timing, unconstrained-path, memory-warning and constraint review
before image generation and board testing.

The current `${YPCB_ROOT}` reuse review confirmed that its MicroBlaze
board XML, pin XML and all three MIG project files match the prepared baseline.
Its existing DLC10 loader remains useful for the later hardware connection.
The LC480T memory-test bitstream differs from our prepared baseline and was
not substituted. Its historical XDMA routed report has three setup failures
(WNS -0.005 ns); it provides no OpenTPU timing qualification. The review and
current native-run receipt are saved in
`native-vivado-resumed-status-20261009T161527Z/` under the Bonetto build
directory. Its CPU readings are historical; the current placement is active
under CPU pressure, and no reliable completion estimate has been established.

There is no completed local OpenTPU image. The upstream releases and public
Actions artifact APIs returned no downloadable images during earlier
preparation; the historical response is saved in
`build/fedora-upstream-actions-artifacts.json`.

On a suitable build host, source the full Vivado settings.

The unchanged upstream source is also archived in
`build/fedora-build-bundle/opentpu-5b1e646c-source.tar.gz`, with a SHA256 manifest
and `BUILD.txt`. That bundle's recipe explicitly sets `BUILD_ID=5b1e646c`, because
an extracted archive has no Git metadata. It contains build inputs, not a
finished FPGA image.
The accompanying `fedora-chat-ui.patch` contains the local host UI fix above;
its hash and a dry-run against the archived source are recorded alongside the
bundle. `BUILD.txt` explains applying that patch before host software setup.
The separate `fedora-stream-test.patch` carries the test-model clock fix for
host test revalidation, with a hash and dry-run against the archived source.
Neither patch changes FPGA RTL or constraints.

The board Makefile's `build-vivado` command builds `otpu_fpga_top_ld` from
`boards/ypcb-00338/vivado/create_project.tcl`. That is the PCIe-host design; it
is not the standalone `otpu_fpga_top_openxc7_jtag` image selected for the first
separately powered, JTAG-only run. Do not use its `build/vivado/otpu.bit` for
that run.

The standalone JTAG image is being implemented in the corrected native project
under `../bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/` with
`TOP=otpu_fpga_top_openxc7_jtag`. Its implementation Tcl saves the routed
checkpoint and qualification reports but intentionally stops before bitstream
generation. The current `build/vivado/otpu.bit` is absent; after route and
report review, generate and structurally check a `.bit` from that standalone
project before using the SRAM-only `program` command below.

For a PCIe-host image from a normal Git checkout, build with:

```sh
cd /path/to/openTPU
bash tools/fedora_bringup.sh build-vivado
# build/vivado/otpu.bit and build/vivado/reports/
```

Keep the reports and exact source revision with the image. Require successful
implementation, closed setup/hold timing and no unconstrained paths before
using an image. If reusing a supplied image, preserve its hash and producer's
build reports; the host's BUILD_ID/VERSION/CAPS readback will identify what
actually runs. Do not substitute the MicroBlaze baseline bitstream for an
OpenTPU accelerator image or the PCIe-host OpenTPU image for the standalone
JTAG-only image.

From the openTPU repository root, run the independent structural check for a
native Vivado `.bit` using the Bonetto checkout:

```sh
python3 ../bonetto-soc/scripts/fedora-check-vivado-bitstream.py \
  --bit build/vivado/otpu.bit \
  --out "build/vivado/native-bit-structural-check-$(date -u +%Y%m%dT%H%M%SZ).json"
```

It checks the YPCB device/package header, configuration IDCODE, packet bounds,
frame-data presence and START/DESYNC markers. Vivado may omit speed grade from
the `.bit` header, so confirm `-2` from the XPR/XSA and implementation reports.
The check does not establish CRC, DRC, timing closure or physical operation.

## When a PCIe host is available

The commands below program FPGA SRAM and then install/configure the PCIe driver
using the upstream setup script. They do not write BPI flash. The `program`
command finishes and releases the DLC10 before another JTAG tool uses it.

On the eventual Fedora PCIe host, the setup script needs installed headers for
that machine's running kernel. The locally extracted headers used above do not
satisfy its system-header check. Install the prerequisites there:

```sh
sudo dnf install gcc make git patch dkms "kernel-devel-$(uname -r)"
```

```sh
# Run from the root of your OpenTPU checkout.
BIT=/absolute/path/to/otpu.bit bash tools/fedora_bringup.sh program
bash tools/fedora_bringup.sh pcie
bash tools/fedora_bringup.sh pcie --rescan
bash tools/fedora_bringup.sh check
bash tools/fedora_bringup.sh selftest
bash tools/fedora_bringup.sh diag
```

`otpu-setup` requests sudo for driver/system configuration. It uses the existing
module, udev and driver option workflow documented in [host.md](host.md). Keep
the PCIe status, configuration registers, both channel calibration results and
all selftest/diagnostic output. Missing device files, incomplete calibration or
failed memory/compute checks are failures, even if JTAG programming succeeds.

After those pass, download a model supported by [host.md](host.md) and run its
model stage. No physical OpenTPU or model result has been established on this
machine during preparation.

For the selected separately powered, JTAG-only first run, a host check at
12:34 HKT on 2026-10-10 produced
`build/fedora-openxc7/check-20261010T043408Z/manifest.json` with status
`TOOLS_READY_BOARD_BUILD_NOT_RUN`; it records no bitstream and no physical
test. The `fedora_bringup.sh check` command as a whole exits nonzero because
`otpu-setup --check` also requires the PCIe driver's matching kernel headers,
udev configuration and an enumerated OpenTPU card. Those PCIe host conditions
are not required for the JTAG-only run. The documented `jtag --help` entry
passes with the repository venv, and the `program` command was verified to
refuse a missing bitstream before running the DLC10 initializer. No JTAG
programming was attempted; the host still has no DLC10 cable and the standalone
Vivado bitstream is not yet built.
At 12:35:09 the congestion retry had completed `open_checkpoint`, loaded the
XC7K480T device and begun sorting the 18,146-UNISIM netlist; it had not written
`congestion.rpt`. PID 1772452 was live at 10m14s elapsed, 4m32s CPU and about
1.7 GiB RSS. The main route PID 1729232 remained live in Phase 2.3 Update
Timing at 4h12m elapsed and 6h11m CPU time.
At 12:36:28 the retry completed UNISIM transformation in 38 CPU seconds but
was still preparing the checkpoint for analysis; no congestion report existed.
The route remained in Phase 2.3 with its CPU time still advancing.
At 12:37:46 the retry advanced to `Preparing netlist for logic optimization`
(PID 1772452: 12m51s elapsed, 5m36s CPU and about 1.8 GiB RSS); the report was
still absent. The main implementation remained in Phase 2.3 at 4h15m elapsed
and 6h16m CPU time.
At 12:38:59 the retry completed `Read ShapeDB` after translating 18,146
UNISIM elements; it had not written `congestion.rpt`. PID 1772452 remained live
at 14m04s elapsed, 6m00s CPU and about 1.9 GiB RSS. The main route remained in
Phase 2.3 at 4h16m elapsed and 6h19m CPU time, with CPU time still increasing.
At 12:42:28 the main route emitted an intermediate timing summary at the end
of Phase 2.3: WNS `0.549 ns`, TNS `0.000 ns`, WHS `-1.292 ns` and THS
`-12419.576 ns`. This is not post-route timing signoff; route completion and
post-route hold review remain required. PID 1729232 was still live at 4h20m
elapsed and 6h24m CPU time. The congestion retry was still preparing its
netlist, with no report yet (PID 1772452: 17m33s elapsed, 7m39s CPU, about
1.7 GiB RSS).
At 12:45:41 the main route process was still live (PID 1729232: 4h23m elapsed,
6h30m CPU, about 148% CPU). Its latest log remains in Phase 2.3 Update Timing
with the intermediate summary above; no final route report or native `.bit`
exists. The congestion retry was also live (PID 1772452: 20m47s elapsed,
8m32s CPU, about 1.8 GiB RSS); its latest log was restoring timing data, and
`congestion.rpt` was still absent.
At 12:46:51-12:47:01 a passive 10-second host sample found all eight CPU
frequency readings near 399 MHz despite the `performance` governor, 1.4-2.0
GHz policy and 2.0 GHz `bios_limit`; `tuned` was using
`throughput-performance`. CPU PSI `some avg10` ranged from 62.91% to 48.46%,
while memory PSI stayed near zero with 13.39 GiB available. The main route and
congestion processes accumulated 997 and 348 CPU ticks in that interval.
Sensors read about 51 C CPU temperature. This confirms CPU under-delivery and
host contention during the run, but does not identify the cause of the 399 MHz
limit; privileged turbostat, SMU and ThinkLMI values were unavailable. No host
settings were changed.
At 12:47:54 the main router advanced to Phase 2.4, `Update Timing for Bus
Skew`; a recheck at 12:48:02 showed it live in Phase 2.4.1 (PID 1729232,
4h25m elapsed and 6h34m CPU). This is forward progress, but the final timing
and bitstream are still pending. The congestion retry remained live at 23m08s
elapsed and 9m03s CPU (PID 1772452); its log still ended at `Restoring timing
data from binary archive`, and no `congestion.rpt` existed.

The active Vivado Tcl is a route-and-report pass: on success it writes
`full-jtag-routed.dcp`, timing/DRC/CDC and related reports, and marks
qualification review pending. It deliberately does not call `write_bitstream`.
The separate bit-generation step remains gated on reviewing final hold/setup
timing and the eight unresolved synthesis memory-removal warnings.
At 12:53:10 both jobs were still live: the route remained in Phase 2.4.1 with
4h30m elapsed and 6h42m CPU (its log was last updated at 12:47:31); the
congestion retry had 28m15s elapsed and 10m10s CPU (its log was last updated
at 12:45:11 and still ended at `Restoring timing data from binary archive`).
CPU time continued to increase in both jobs, but neither had produced its final
output: no routed checkpoint, bitstream or `congestion.rpt` existed.
At 12:54:57 Phase 2.4.1 completed an update and emitted another intermediate
timing summary: WNS `0.549 ns`, TNS `0.000 ns`, WHS `-1.253 ns`, THS
`-1536.386 ns`. Hold timing improved from the previous intermediate summary
but remains negative, so this is not signoff. PID 1729232 remained live at
4h32m elapsed and 6h45m CPU time. The congestion retry remained live at 30m03s
elapsed and 10m30s CPU time; its log was still restoring timing data and no
report had appeared.
At 12:56:13 the congestion retry had advanced through timing-data restoration
and was reading the placement database (PID 1772452, 31m19s elapsed,
10m59s CPU, 2.8 GiB RSS, nice 19); `congestion.rpt` was still pending. The main
route remained live in Phase 2.4.1 at 4h33m elapsed and 6h46m CPU time, with
the intermediate hold summary above and no routed checkpoint or bitstream.
At 12:59:00 the main route completed Phase 2.4 bus-skew timing and advanced to
Phase 2.5, `Soft Constraint Pins - Fast Budgeting` (PID 1729232, 4h36m elapsed,
6h49m CPU; Vivado reported 7.0 GB peak memory). The prior intermediate hold
summary remains negative and final timing is pending. The congestion retry was
still live at 34m06s elapsed and 11m57s CPU; its latest log remained at
`Read PlaceDB`, with no `congestion.rpt` yet.
At 12:59:25 a read-only `vmstat` sample showed the host fully busy (0% idle,
94-97% user and 3-6% system CPU) with a run queue of 16-20. Later one-second
samples showed no swap-in/out and 0% I/O wait. About 10 GiB remained available;
memory pressure was near zero despite 10.4 GiB already allocated to swap. This
supports CPU contention as the current throughput constraint, not active
swap-in or I/O wait.
At 13:00:47 the main router advanced through Global Routing into Phase 4.1,
`Initial Net Routing Pass` (PID 1729232, 4h38m elapsed, 6h53m CPU). Its
278,185 failed-net count was logged during router initialization, before the
initial routing pass, so it is not a final unrouted-net result. At 13:00:55 the
congestion retry completed reading place storage and physical databases and
finished XDEF restoration/UNISIM transformation (PID 1772452, 36m01s elapsed,
12m19s CPU, about 3.0 GiB RSS); the report remained pending.
At 13:01:53 the congestion retry completed `open_checkpoint` and verified
`PART=xc7k480tffg1156-2` and VPU hierarchy `u_sys/u_board/u_slice/u_vpu` in
`loaded-design.txt`. It had reached `report_design_analysis -congestion`, but
`congestion.rpt` was not yet present (PID 1772452: 37m07s elapsed, 12m31s CPU,
about 3.1 GiB RSS). The main route remained live in Phase 4.1 at 4h39m elapsed
and 6h55m CPU time.
At 13:02:15 `report_design_analysis -congestion` completed in 1m19s. The
input checkpoint hashes passed `sha256sum -c checkpoint.sha256`; the copied
placed DCP SHA256 is `0ce369486f97abecb480a07aea9a68359b4fb08fd2546e78e89b4272204cdcd4`.
The report found two placement congestion windows: North/global level 6 at
115% (RAMB 76%, DSP 89%, led by memory/MXU/sequence cells) and West/global
level 5 at 110% (RAMB 80%, DSP 78%, led by memory/DMA/MXU cells). The report
is saved at
`build/fedora-openxc7/congestion-analysis-20261010T1223HKT-retry/congestion.rpt`
(SHA256 `ef7e184170d64384302c3653142878d97a0d19c1152419b63bb52bbeff25d703`).
This is placement-congestion evidence from the saved placed checkpoint, not
final route or timing signoff; the full route remains active in Phase 4.1.
Vivado logged `close_design` and exit at 13:04:02; the congestion process had
terminated by 13:04:22, leaving the report and its input/hash evidence intact.
At 13:10:38 the main implementation remained live in Phase 4.1 (PID 1729232,
4h48m elapsed, 7h08m CPU, about 5.7 GiB RSS). The route log had not advanced
since 12:59:21; CPU time continued increasing. No final routed checkpoint,
timing report or `.bit` had been produced.
At 13:12:32 a fresh read-only sample found all eight CPU frequencies near
399.25 MHz, CPU PSI `some avg10=56.40%`, and a run queue of 16-20. The host was
94-96% user CPU and 4-6% system CPU with 0% idle/I/O wait; later one-second
samples had no swap-in/out, and memory/I/O PSI stayed near zero. The Vivado
route process remained active at 4h50m elapsed and 7h10m CPU time. This
confirms active CPU-bound work and continued low clock delivery, with no I/O
wait indication; the cause of the clock limit remains undetermined.
At 13:17:33 the main route remained live in Phase 4.1 at 4h55m elapsed and
7h18m CPU time. CPU time increased by about 2m15s over the prior 72 seconds,
but the route log remained unchanged since 12:59:21. No route-end marker,
routed checkpoint, timing report or `.bit` existed.
At 13:19:39 Phase 4.1 completed after 1h09m elapsed/1h49m CPU within the
router, and Vivado advanced to Phase 5, `Rip-up And Reroute`, Global Iteration
0, Phase 5.1.1 `Update Timing`. PID 1729232 remained live at 4h57m elapsed and
7h21m CPU time. This is routing progress; final route signoff and bitgen are
still pending.
At 13:25:06 the router was still live (PID 1729232, 5h02m elapsed, 7h30m CPU,
about 5.7 GiB RSS). The log had updated at 13:23:41 and remained in Phase 5.1.1
`Update Timing`; Vivado warned that congestion was preventing all nets from
routing and that it would prioritize routing every net over timing optimization.
This is an active router warning, not a final unrouted-net result. No route-end
marker, routed checkpoint, final timing report or `.bit` existed. The prior
source-function review of all eight BRAM/URAM-removal warnings remains open; its
mapped-hierarchy check confirms their absence but does not establish that their
removal is functionally harmless.
At 13:29 HKT, the host-only JTAG transport suite passed again using
`build/fedora-venv/bin/python -m pytest -q tests/test_jtag_transport.py`:
13 passed in 0.51s. The fake-mailbox test log is
`build/fedora-openxc7/jtag-transport-host-20261010T132907HKT/pytest.log`
(SHA256 `065abfd913015cfc908fee27bcec5abfac73c5c7f93861971550512f3bf9c65b`).
This validates packet, range, ECC, XADC and board-scrub host behavior against
the test doubles; it is not a physical JTAG or accelerator test. At 13:29:18
PID 1729232 remained active at 5h06m elapsed and 7h36m CPU. The route log had
not advanced since 13:23:41 and remained in Phase 5.1.1 `Update Timing`; no
route-end marker, routed checkpoint, final timing report or `.bit` existed.
At 13:30:40 the router advanced to Phase 5.2, Global Iteration 1. At 13:31:03
PID 1729232 was still live at 5h08m elapsed, 7h40m CPU, about 5.7 GiB RSS, and
149% CPU. This is continued routing progress after the congestion-heavy timing
update. A search of the active run directory found no routed checkpoint,
bitstream, route-end marker or final timing report; post-route signoff remains
pending.
At 13:32 HKT, a second host-only suite passed 36 tests in 2.06s, covering fake
memory writes and first-halt/stream completion and polling behavior. The saved
log is `build/fedora-openxc7/host-behavior-20261010T133200HKT/pytest.log`
(SHA256 `ca9226fcd29b294bc11283fc9deebb7d99ddc001f14d76364afbaa342809bd19`).
These tests use host-side test doubles and do not touch the board. At 13:34:05
PID 1729232 remained active at 5h11m elapsed, 7h45m CPU, 149% CPU and about
5.7 GiB RSS. The route log remained in Phase 5.2 Global Iteration 1, last
updated at 13:30:40; CPU time continued to advance. A fresh artifact search
still found no routed checkpoint, route-end marker, final timing report or
bitstream.
At 13:35:05 and 13:35:15 a saved host sample showed the route process CPU time
increasing by 16 seconds over 10 seconds at about 149% CPU, with 5.7 GiB RSS.
All eight CPU cores averaged 399,252 kHz; CPU PSI `some avg10` was 48.76% then
48.34%, while `full` remained 0. This confirms CPU-bound routing under low
clock delivery, but does not identify why the host clocks are capped. Evidence:
`build/fedora-openxc7/route-host-sample-20261010T133504HKT/sample.txt`
(SHA256 `f9ed4ce246ec48b36abab050f1da51d862397a30e4a3e496f9ace9a1f99e8890`).
At 13:35:23 the router was still active at 5h12m elapsed and 7h47m CPU; its
log remained in Phase 5.2 Global Iteration 1 and no final implementation
artifact had appeared.
At 13:36 HKT, two Icarus RTL simulations passed using the prepared JTAG-only
path. `tb_openxc7_jtag` passed AXI-Lite windows, independent AW/W handshakes,
DDR 64-byte bursts, backpressure and AXI error cases; its saved output is
`build/fedora-openxc7/jtag-axi-rtl-20261010T133614HKT/sim.log` (SHA256
`645f8b3635984657155c3908e816b28009348d2ae82e94af4ac36de97b77290c`).
`tb_openxc7_mailbox` passed asynchronous request/response crossing, held-request
polling, sequence and response checks; its output is
`build/fedora-openxc7/jtag-mailbox-rtl-20261010T133632HKT/sim.log` (SHA256
`f5e4717c3ce193deaea77b62b9b087bebdd0baa813cf3d1352799ce4f99089cc`). These
test the RTL blocks separately with simulated interfaces; they do not prove
integrated bitstream behavior or physical JTAG operation. At 13:39:40 PID
1729232 remained active at 5h17m elapsed and 7h53m CPU, about 149% CPU and
5.7 GiB RSS. The route log remained in Phase 5.2 Global Iteration 1 and had not
changed since 13:30:40. A fresh search found no routed checkpoint, route-end
marker, final timing report or bitstream.
At 13:38:46 the OpenTPU `program` guard was exercised with its default image
absent. `tools/fedora_bringup.sh program` returned 2 with `Missing OpenTPU
bitstream` before it could start the DLC10 initializer. The saved guard output
is `build/fedora-openxc7/program-guard-20261010T133846HKT/result.log`
(SHA256 `d851eb20568f40bd38b01daa7723010fe723bacb6a1ed2c82f792dbe0645710a`).
This confirms the no-image guard only; it is not a cable or hardware check.
At 13:42 HKT, `make -C boards/ypcb-00338 sim-jtag` passed all three Icarus
benches: AXI-Lite/DDR bridge, asynchronous USER2 mailbox and the new combined
serial-to-AXI path. The combined bench sends a serial CSR read through the
mailbox CDC into AXI-Lite and a four-beat DDR read through the bridge, then
checks sequence, status and response data. The saved aggregate output is
`build/fedora-openxc7/sim-jtag-target-20261010T134254HKT/make.log` (SHA256
`441a9062e693d4acb254f4673eb9e7996e13b3ecd5203e9b613a2793a0cec144`). This
simulates the USER2 signals and bridge modules separately from the full FPGA
top and does not test BSCANE2 or physical JTAG.
At 13:45:12 PID 1729232 remained active at 5h22m elapsed, 8h00m CPU and 148%
CPU, with about 5.7 GiB RSS. Its route log was still in Phase 5.2 Global
Iteration 1, unchanged since 13:30:40; CPU time continued to advance. A fresh
search found no routed checkpoint, route-end marker, final timing report or
bitstream.
At 13:46 HKT, the combined USER2 path bench was extended to cover accelerator
AXI-Lite writes and four-beat DDR writes as well as the prior reads. The
`sim-jtag` target passed all three benches; the integration bench checked
independent AW/W handshakes, full-width DDR write beats, completion responses,
sequences and payloads. The saved output is
`build/fedora-openxc7/sim-jtag-target-20261010T134619HKT/make.log` (SHA256
`8a6ee9906d9b49cfe93cbce333b8a3c6f042a83d364ef4cac2f4f1a63b7e0a75`). This
still simulates the mailbox and AXI bridge separately from the full FPGA top;
it does not model BSCANE2 or prove physical JTAG operation.
At 13:48:54–13:49:04 HKT, PID 1729232 was still routing at 5h26m elapsed,
8h08m CPU, 149% average CPU and 5.7 GiB RSS. The saved 10-second host sample
shows all eight cores near 399.25 MHz, CPU PSI `some avg10` falling from 42.92%
to 30.73%, negligible memory/I/O PSI and about 13.9 GiB available. Process CPU
time advanced 11 seconds. The run log remained in Phase 5.2 Global Iteration 1,
unchanged since 13:30:40. No routed checkpoint, route-end marker, final timing
report or `.bit` existed, and USB enumeration found no Digilent, FTDI or Xilinx
adapter. Evidence: `build/fedora-openxc7/route-host-sample-20261010T1350HKT.txt`
(SHA256 `38a930acbe9c9e38b6d271421aed7ca8414c637ffd4fec9e7731b28e6f8f8e23`).

## 2026-10-10 17:03 HKT — native Vivado route recovery

The earlier full-Vivado implementation run was interrupted by a Fedora reboot.
Its completed placement/pre-route checkpoint was preserved, then Vivado was
reset to `route_design` and relaunched from that checkpoint at 16:42 HKT. The
active route worker (PID 6738 at the last check) was in Phase 5.4, Global
Iteration 3, using about 214% CPU and 5.7 GiB RSS. The router reduced overlaps
from 94,634 to zero in iteration 1 (interim WNS -0.230 ns), then from 662 to
zero in iteration 2 (WNS -0.012 ns, TNS -0.021 ns); iteration 3 had 124 overlaps
in the latest run log. These are in-progress values. There is still no route-end
marker, final timing report or bitstream. Keep the live run intact and recheck
the route log and run markers before acting. The native project and recovery
logs are under `${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/`.

The eight `Synth 8-13374` BRAM/URAM-unreachable warnings remain unresolved;
source-level function and harmlessness have not yet been established. The
separately powered JTAG-only board test also remains pending because no JTAG
adapter is enumerated on the host.

## 2026-10-10 17:20 HKT — route completion and I/O constraint blocker

The resumed native Vivado `route_design` completed successfully at 17:10 HKT.
The route stage took 1,288 seconds elapsed (21m32s), 47m04s aggregate CPU, and
peaked at 6.75 GiB. It routed all 278,219 routable nets, with zero routing
errors and zero final overlaps. Post-route timing reports WNS +0.086 ns, TNS 0,
WHS +0.017 ns, and THS 0. All user timing constraints in this checkpoint are
met. The route log and reports are under
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-implementation-corrected-v2-20261010T001951Z/project/native_full_jtag.runs/impl_1/`.

Routing took the longest because the large design has 278k routable nets and
needed several global rip-up/reroute iterations to clear congestion. The earlier
implementation attempt was interrupted by a Fedora reboot after spending hours
in congestion recovery; the resumed route from the preserved placed checkpoint
then took 21m32s. This points to routing pressure plus the interrupted attempt,
not the synthesis/export stage.

The route is not a valid bitstream candidate yet. In the project, the DDR XDC
with pin and I/O-standard assignments is synthesis-only; the implementation
XDC has only a timing exception. The routed DRC consequently flags 234/243
ports for unspecified I/O standard and location. A probe that read the full
corrected DDR XDC after routing showed sample DDR pin properties, but left the
checkpoint partially routed and still reported 117 unconstrained ports, two
bank-voltage conflicts (BIVC-1), PLCK-87, 67 PLIDC-8 errors, and placement
conflicts from the XDC. This late application does not fix the implementation.
Reconcile the board pin/bank constraints and apply them before a fresh
placement/route; do not generate or load a bitstream from this checkpoint.

## 2026-10-10 17:54 HKT — constrained placement checkpoint preserved

The earlier route used an implementation XDC without the DDR pin assignments.
A read-only audit on the synthesized checkpoint then verified that the full
DDR XDC's 234 package-pin assignments match the two supplied MIG pin files.
With `board-jtag.xdc`, the corrected DDR XDC and `jtag-clock.xdc` applied before
placement, Vivado DRC reported no errors and all 243 top-level ports had pin
and I/O-standard constraints. The audit reports are under
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/constraint-validation-20261010T1727HKT/`.

A fresh implementation in the isolated constrained project started around
17:35 HKT from the saved synthesis checkpoint. `opt_design` and post-opt DRC
passed with zero errors; `place_design` completed in 10m42s elapsed (25m18s
aggregate CPU, about 6.1 GiB peak memory). `phys_opt_design` completed
successfully. The user-requested stop canceled the implementation script at
17:50 HKT before `route_design` began. No routed checkpoint or bitstream was
produced by this run.

The placed checkpoint is preserved at
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-implementation-constrained-20261010T1732HKT/project/native_full_jtag.runs/impl_1/otpu_fpga_top_openxc7_jtag_placed.dcp`
(82,514,099 bytes; SHA256
`f4bb60dae19ed150a9d9ae8dc769f37e1f0ab9654d3dc7ab75e13ef0ec04eaf0`). The
full run log is alongside it at `runme.log`. To finish the native reference,
resume implementation from this placed checkpoint, complete routing, then
review final DRC/timing and bitstream checks before continuing the selected
OpenXC7 route. The eight BRAM/URAM-unreachable synthesis warnings remain
unresolved. A 17:52 HKT USB check still found no JTAG adapter, so there is no
physical programming or USER2 test result.

## 2026-10-10 17:56 HKT — full native synthesis runtime

The saved Vivado 2026.1 synthesis log shows `synth_design` completed
successfully in 5h18m42s elapsed (3h46m04s CPU); the entire Vivado session ran
from 00:12:49 to 05:40:55 HKT, including project setup and reports. Writing
the synthesis checkpoint took another 5m24s after `synth_design` completed;
5m24s was not the total synthesis time. The generated script set the synthesis
thread limit to one and Vivado logged a CPU frequency of 399.251 MHz at
startup. Peak synthesized-design PSS was 6.46 GiB. The mapped design contains
716 DSP48E1s, 562 RAMB36E1s and
34 RAMB18E1s. The concrete throughput cause is in the run configuration:
`native-reference.tcl` set `general.maxThreads 1`, and Vivado's generated
synthesis script retained that one-thread limit. It also launched one
synthesis run with `-jobs 1`. This limited the large design's synthesis to one
thread. Vivado logged 399.251 MHz at startup, but that is only one frequency
observation and does not quantify its effect over the entire run.

Authoritative log:
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-reference-20261009T154026Z/project/native_full_jtag.runs/synth_1/runme.log`
(SHA256
`97343fd22e1d5fba38ef2ea8f641ef42c99929d3f4621271138392c97c09bc6e`). The
constrained implementation later reused this synthesis checkpoint, completing
placement in 10m42s before it was stopped ahead of routing.

## 2026-10-10 17:59 HKT — route-only resume prepared

To preserve the completed placement and avoid rerunning placement, a separate
route-only Tcl script is prepared at
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-implementation-constrained-20261010T1732HKT/resume-route-from-placed.tcl`
(SHA256
`1c5540caf6b14d56838966f1ab54d16c47e8e9fdebd17ffd91d42b8bfc691c01`). It
opens the placed DCP, checks the design name and that all 243 top-level ports
have LOC and I/O-standard constraints, then routes with a four-thread limit and
writes route status, DRC, timing and a routed checkpoint into a new output
directory. It does not generate a bitstream. Tcl parsing and the checkpoint / output-directory preconditions passed; the script has not been run.

When implementation resumes, the command is:

```sh
${VIVADO_ROOT}/bin/vivado -mode batch \
  -source ${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-implementation-constrained-20261010T1732HKT/resume-route-from-placed.tcl
```

## 2026-10-10 18:04 HKT — host JTAG path rechecked

The focused host tests were rerun with the repository's `build/fedora-venv`:
`tests/test_jtag_transport.py` and `tests/test_openxc7_vref.py` passed all 20
tests. `make -C boards/ypcb-00338 sim-jtag` also passed the AXI-Lite, async
mailbox, and USER2-to-AXI/DDR read/write benches. These tests do not include the
full FPGA top, BSCANE2, or physical JTAG chain. The logs, USB enumeration and
FPGA-process snapshot are saved in
`build/fedora-openxc7/host-recheck-20261010T1804HKT/`; no JTAG adapter was
enumerated and no FPGA build or programming command ran.

## 2026-10-10 18:11 HKT — broad suite left incomplete

The full repository pytest run collected 1,511 cases. I interrupted it after
43 passing progress markers because it was spending several minutes in the
broader RTL/model checks. The process exited 130 without a final summary; this
is not a full-suite pass. The partial output and explicit status are saved in
`build/fedora-openxc7/full-suite-20261010T1806HKT/`. The focused JTAG tests
and three board-path RTL benches above passed separately.

## 2026-10-10 18:15 HKT — compute path over USER2 JTAG audited

The prepared transport supports accelerator work and output readback without
PCIe. `tools/fedora_jtag.py selftest` supplies `JtagTransport` to the existing
staged self-test. Its kernel stage writes the program and input to DDR, starts
the core through control registers, waits for completion, reads output DDR and
compares it with the ISA simulator. `tools/fedora_chat.py --transport jtag`
selects the same transport for inference and checks the loaded full DDR800
profile before constructing `BoardBackend`. The data path is serial and has
no PCIe bandwidth claim. This is a source-path audit, not a board result.

At 18:15 HKT, `bash tools/fedora_bringup.sh jtag-server --dry-run` revalidated
the XVC binary and DLC10 firmware and emitted the expected initializer/server
commands. The saved receipt is
`build/fedora-openxc7/host-recheck-20261010T1804HKT/jtag-server-dry-run-20261010T1814HKT.json`
(SHA256 `07ce728641c9dd9b7402d0aa18d854b8e85f493ba268dc9a12359cac95d43801`).
Dry-run did not initialize or scan the cable; USB enumeration still finds no
JTAG adapter.

## 2026-10-10 18:18 HKT — XVC TCP transport rechecked

A new local loopback regression now exercises the actual Python XVC socket
client instead of injecting a mailbox object directly. It checks split TCP
replies, TAP scan entry/exit framing, selected IDCODE, USER2 register access,
and a DDR write/read at the upper boundary of channel 1. The focused JTAG and
OpenXC7 host tests passed 21 cases, and the three USER2/AXI RTL benches passed
again. Logs and exact source hashes are under
`build/fedora-openxc7/jtag-xvc-recheck-20261010T1818HKT/`. The endpoint is a
local emulator; this does not verify the physical XVC server, BSCANE2, or the
card's JTAG pins. USB enumeration still finds no adapter.

## 2026-10-10 18:23 HKT — full-board-model kernel parity

`tests/test_board.py::test_program_on_board_model` passed in 204.89 seconds.
It ran the accelerator RTL through the Verilator `tb_board` model and compared
the modeled DDR output against the ISA simulator. The first build is preserved
in `build/verilator/tb_board_665f39be259f/`; the test log and a receipt with
the exact configuration, executable hash and source hashes are in
`build/fedora-openxc7/board-kernel-sim-20261010T1819HKT/`. This adds full-board
compute evidence to the separate XVC host and USER2/AXI bridge tests. The
simulation does not include BSCANE2 or physical JTAG and does not prove the
card's DDR calibration or compute output.

## 2026-10-10 18:29 HKT — staged self-test on the full board model

`bash tools/fedora_bringup.sh sim` passed the complete staged
`otpu-selftest --sim --bw-mib 1`: link, configuration, calibration on both
channels, register and DDR address/pattern checks, kernels, VPU operations, and
streaming. Bandwidth was skipped by design on the model. The log and exit code
are in `build/fedora-openxc7/full-selftest-20261010T182553HKT/`. This is
Verilator model evidence only; it does not prove card calibration, JTAG, or
physical compute.

## 2026-10-10 18:35 HKT — full-design placer timeout correction probes

An isolated XC7 nextpnr backend now computes the full-design placement retry
limit in 64-bit arithmetic and saturates it at `INT_MAX - 1`. The
UBSan-instrumented arithmetic contract passed nine cases, including 531,351
cells, on the build recorded in
`build/fedora-openxc7/placer-timeout-backend-20261010T1831HKT/` (binary SHA256
`b7c15652ebea939e346fb580985240a54762f3feb0948eb285e6c2061b8de759`). On that
exact binary, the CARRY4 routing/equivalence probe passed all 256 input
combinations, four 16-DSP cascades routed, and the FF-edge/full-half-period
timing semantics probe passed. Strict Project X-Ray frame assembly passed for
all three corrected probes; the receipts are in
`build/fedora-openxc7/placer-timeout-strict-frames-20261010T1835HKT.json`.
This validates the isolated correction gates only. Full-design placement and
routing, numerical timing qualification, full-image frame assembly, and
physical board tests are still pending.

## 2026-10-10 18:42 HKT — native Vivado/OpenXC7 synthesis cross-check

The Vivado and OpenXC7 synthesis inputs match byte-for-byte across all 31
RTL/generated-core files and use the same full-compute DDR800 profile. Both
netlists retain the VexRiscv calibration CPU and JTAG BSCANE2 block. Vivado
mapped 716 DSP48E1s and 1,158 RAMB18 equivalents; OpenXC7 mapped 717 DSP48E1s
and 1,134 equivalents. These small mapping differences do not establish
functional equivalence or timing. The machine-readable comparison is
`build/fedora-openxc7/vivado-synthesis-crosscheck-20261010T1842HKT.json`.

The native Vivado synthesis itself completed in 5h18m42s elapsed. Its reference
script set `general.maxThreads 1`, limiting synthesis parallelism; the startup
log reported 399.251 MHz. These are observed conditions, without a controlled
comparison quantifying either condition's contribution to elapsed time. Saving
the synthesis checkpoint took a further 5m24s. A later constrained Vivado attempt
placed the design in 10m42s and was stopped before routing. The resumed earlier
route took 21m32s after the first route attempt had stalled during congestion
recovery. The prepared constrained route-only resume remains unrun. The eight
unreachable BRAM/URAM synthesis warnings remain unresolved, and neither route
is a current bitstream candidate.

## 2026-10-10 18:48 HKT — timeout-corrected full JTAG route started

The current source files still match all 31 inputs recorded by the completed
DDR800 synthesis, and the mapped netlist hash is unchanged. The corrected
nextpnr backend passed the timeout arithmetic, carry, DSP cascade, FF-edge and
strict-frame probes. The normal OpenXC7 tool/profile check also passed.

A two-thread full JTAG-profile placement and route was started in
`build/fedora-openxc7/timeout-corrected-full-jtag-route-20261010T1048Z/` from
the existing 462 MB DDR800 mapped netlist. The command explicitly supplies the
timeout-corrected backend because `build/fedora-openxc7/implementation-active.json`
still selects the earlier carry-sites binary. The log confirms the corrected
full-design attempt limit and that initial analytic placement began. No
placement or routing result exists yet; this output is not a candidate image.
Timing qualification, full-design strict frame assembly and physical board
validation remain pending. This command uses the default `heap` placer; the
earlier full static-placement experiment explicitly used `--placer static` and
failed legalization on a `SELMUX2_1` cell after reaching the same cap. The
heap route is a distinct placer experiment, and the timeout correction alone
does not guarantee a fit.

## 2026-10-10 19:18 HKT — all-core full route and exact failing MUX probe

At the user's request, the two-thread route was interrupted and preserved; its
manifest records `INTERRUPTED_SUPERSEDED_BY_ALL_CORE_RUN`. The replacement uses
the same full DDR800 netlist and backend in
`build/fedora-openxc7/timeout-corrected-full-jtag-route-all-cores-20261010T1903HKT/`.
`OTPU_THREADS=all` resolves to the job's CPU affinity; the recorded command uses
`--threads 8`, all eight CPUs are allowed, and cgroup CPU quotas are unlimited.
The current strict-legalizer stage is serial. A ten-second measurement showed
approximately one CPU in use, 13.6% aggregate host utilization, negligible
CPU/memory pressure and reported clocks of about 1.6–4.2 GHz. This is a current
snapshot, not a diagnosis of the older 400 MHz observation.

Two read-only counter observations at 19:16:25 and 19:17:46 HKT showed 3,370
additional legalizer calls and 3,370 fewer queued entries. Calls can repeat and
queue entries need not represent unique unplaced cells; this confirms forward
progress without establishing percent complete, an ETA, or full fit. The
original process resumed normally after both observations. Its route is still
running and no full-design FASM or bitstream exists yet.

`tools/openxc7_mux_cluster_check.py` extracts the exact MUXF8 subtree named in
the earlier full static failure. It preserves the original LUT6, two MUXF7
cells and constant branches, with the eight boundary nets as independent
inputs. On the same backend, this tree placed in actual F7/F8 BELs, routed,
matched all 256 input patterns against XC7 primitive models and passed strict
frame assembly. The final helper recheck emitted byte-identical FASM and reused
the verified strict-frame result. The final receipt and tested helper snapshot
are in `build/fedora-openxc7/extracted-mux8-verified-20261010T1916HKT/`.
This isolates one packing case; full-design fit, numerical timing and hardware
operation remain unproven. No probe bitstream was built. MicroBlaze remains
host-ready, but the fresh USB scan still found no JTAG adapter. Vivado remains
stopped at the user's request.

## 2026-10-10 19:55 HKT — merged corrections verified; replacement route active

The `b7c15652...` backend had omitted the previously validated second-slice
carry placement correction. Its lower carry probe could not detect that gap;
the upper-slice diagnostic and source comparison identified it. The correction
is restored in `build/fedora-openxc7/merged-carry-sites-backend-20261010T1935HKT/`.
Binary SHA256:
`975e6dbd3cb87e8e4cac71fc2e4b68b9afa0b1695c0a5b1ebd85e551485577d2`.
The build retains carry padding, DSP site/LOC handling, FF-edge and 64-bit
timeout corrections. Lower carry, upper carry, DSP cascade, FF-edge and the
extracted MUXF8 probes all passed on this exact binary. Strict frame assembly
passed for all five; the aggregate receipt is
`build/fedora-openxc7/merged-correction-strict-frames-20261010T1943HKT.json`.
This does not prove full-design fit, numerical timing or physical operation.

`tools/fedora_check_jtag_image.py` now supports exact correction receipts for
the JTAG profile: it pins the selected build/source, all five probe identities,
strict-frame outputs and full synthesis configuration. Actual selection
verification passed, with substitutions of a different binary and reduced
compute profile both rejected. The receipt is
`build/fedora-openxc7/merged-carry-sites-backend-20261010T1935HKT/selection-verification.json`.
Byte-compilation and whitespace checks passed. PCIe checker policy is unchanged.

After these checks passed, the previous all-core run was interrupted and
preserved as `INTERRUPTED_SUPERSEDED_BY_RESTORED_CARRY_CORRECTION`. Its replacement
started at 19:49:39 HKT from the same full DDR800 mapped netlist, with eight
threads, in
`build/fedora-openxc7/merged-full-jtag-route-all-cores-20261010T114939Z/`.
At 19:54 HKT, nextpnr PID 43460 remained live with about 4m35s elapsed, 141%
lifetime-average CPU and 6.2 GiB RSS. Its log had entered the main analytical
placer after four initial iterations; the manifest was `RUNNING`. This is
placement activity, not a route result or image. Do not launch competing full
placement or rebuild synthesis. Vivado remains stopped, and physical tests
remain pending without a JTAG adapter.

## 2026-10-10 20:07 HKT — Vivado selected now; OpenXC7 deferred

The user selected Vivado and explicitly deferred OpenXC7. Its exact nextpnr
process was interrupted and preserved; the last full-run manifest records
`INTERRUPTED_USER_SELECTED_VIVADO`. Do not restart OpenXC7 while this priority
remains in force.

The native Vivado reference resumed from the correctly constrained placed DCP
under the durable user service
`otpu-vivado-jtag-resume-20261010t120727z.service`. Run directory:
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-route-bitstream-20261010T120727Z/`.
The controller is PID 45600 and actual Vivado PID 45658. At 20:08 HKT it remained
live while loading the placed checkpoint, with up to eight threads enabled.
All 31 original/native source snapshot pairs and the full DDR800/100 MHz
configuration were verified before launch. Synthesis and placement are reused.

The saved native script checks the exact device/top, all 243 pin/standard
pairs, 1.8 V/GND configuration, USER2 and both DDR serializer sets before
physical optimization/routing. It records DRC, timing, bus-skew and CDC reports
and writes the bitstream after setup/hold and DRC gates pass. Its controller
checks input hashes and independently validates the resulting .bit container.
The new run has not yet produced a bitstream. Native synthesis's eight
memory-removal warnings still need review; physical compute remains untested.

JTAG and separate card power can be connected now. PCIe is unnecessary for this
standalone USER2 image. The USB scan still found no adapter; identify the cable
and target before any later SRAM load, and preserve BPI flash.

The initial 20:07 native resume stopped after opening its DCP because the
controller checked the checkpoint display `NAME` against the RTL module. Its
guard now checks the design's `TOP` property; failed evidence is preserved.
The current replacement started at 20:10:07 HKT under
`otpu-vivado-jtag-resume-20261010t121007z.service` in
`${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/vivado-full-jtag-route-bitstream-20261010T121007Z/`.
It uses the unchanged placed checkpoint, sources, 243-pin inventory and eight
threads. No bitstream was produced by the failed first attempt.

At 20:12 HKT the replacement was confirmed live as actual Vivado PID 45917
(controller 45860). Its checks passed on the actual checkpoint: the RTL TOP,
part, all 243 board pin/standard pairs, 1.8 V/GND configuration, USER2 and both
complete DDR serializer sets. It retained all 716 native DSPs and 562/34
RAMB36/RAMB18 blocks. Pre-route DRC reported warnings only, with zero errors;
physical optimization started at 20:11:32 HKT. Routing and .bit creation remain
pending. The current run's checkpoint audit, pre-route DRC report and exact
live-process receipt record these observations.


## Isolated MIG OpenTPU integration, 2026-10-11 08:16 HKT

The new candidate is `build/fedora-vivado/mig-jtag-controller-20261010T235833Z/`
in openTPU. It retains the full compute dimensions and USER2 transport, with
Vivado MIG DDR3-1066 ECC, a single existing native port per channel, hardware
full-memory write/read BIST and ECC reporting. Five memory-bridge simulations,
1,325 asynchronous diagnostic transactions (including injected data/ECC faults
and read ownership) and six host failure-gate tests passed. These are offline
checks. Vivado IP generation completed; actual native synthesis is running,
unified exec 86906, synthesis PID 43204 started at 08:12:45 HKT; parent PID
42941. Configured eight cores; Vivado reports seven helpers plus the main.
Check exact PID/start and log progress before any restart. Candidate README
records the continuation and required implementation/pin/timing/CDC audit, full
DDR/ECC test and normal accelerator/model test. The selected manifest and
physical native FPGA image are unchanged. No physical model run or flash write.


## Current recheck and MIG build, 2026-10-11 08:26 HKT

A final fresh verbose JTAG scan exited 0 and the existing strict chain parser
passed: exactly one XC7K480T, IDCODE 0x23751093, IR 6. The non-verbose scan
also detected it, but omitted the count field expected by the parser; its
parser rejection is not a cable fault. The successful receipt is
`vendor-mig-probe-20261010T233827Z/latest-chain-verbose-result.json`. Hardware
clients stopped after detection; USB remains 03fd:0008 at 480 Mb/s.

The isolated MIG candidate's declaration order was corrected. Its first
synthesis was intentionally terminated with exit143; a brief second attempt
exited1 because Vivado requires explicit input net types under default_nettype
none. Both terminal logs/directories are preserved. Inputs now use input wire,
and the 1,325-transaction diagnostic passed again. All five memory-bridge
scenarios also passed after moving declarations. Corrected native synthesis
is progressing past RTL elaboration with no adapter declaration warnings.
Current unified exec session91458, parent Vivado PID46234 started08:21:58 HKT,
synthesis PID46367 started08:22:08 HKT. Sessions86906 and32121 and their PIDs
are historical/terminal. Follow candidate manifest, README, stage.txt and
synth_1/runme.log; the build uses eight available cores. The original selected
native-image restore checker passed again. No new FPGA image was loaded; full
physical model inference remains NOT_RUN. The resumed goal remains active.


## Fresh connection check and MIG implementation, 2026-10-11 08:42 HKT

A fresh JTAG scan passed: exactly one XC7K480T, IDCODE 0x23751093,
IR6 and the expected chain-end marker. USB cable enumeration is 03fd:0008.
Receipt: `build/fedora-vivado/connection-recheck-20261011T003146Z/result.json`.
No image was loaded in this recheck. The physical original DDR800 image remains;
its full channel-0 memory failure is unresolved and physical model inference is
NOT_RUN. The sparse supplied-MIG pass remains separate from full-capacity proof.

The isolated MIG candidate synthesis session91458 exited0 at08:38:15 HKT.
It retained all716 compute DSPs. Checkpoint reopening exposed a late constraint
lookup error because synthesis merged the JTAG host clock with the identical
core clock. The isolated constraint now resolves the host FIFO register clock
and requires it to equal the core clock; both channels loaded with no errors
or critical warnings. No RTL resynthesis was necessary. The initial error log
and old constraint remain preserved. All247 package pins and I/O standards,
configuration properties, USER2, both complete PHYs and all expected core/UI/
input/JTAG clock periods passed the synthesized-checkpoint audit. The MIG
reference reset standards are LVCMOS15; both expected reset rows were corrected.
Twenty-four unchanged upstream snapshots and the exact single-port bridge patch
were reviewed;94 generated MIG inputs were frozen for the independent checker.

Implementation is running with eight available cores: unified exec72196,
parentVivadoPID48404 started08:39:05 HKT, startticks3015012; implementation
PID48637 startedSun Oct 11 08:40:35 2026. Candidate:
`build/fedora-vivado/mig-jtag-controller-20261010T235833Z/`.
Follow its manifest, README, stage.txt, implementation-console.log and
impl_1/runme.log. Do not start a duplicate job or restart based on log silence.
After terminal exit0, run the new dedicated check_candidate.py and review all
remaining CDC paths. SRAM programming, both full2GiB/channel pattern/ECC tests,
normal accelerator tests and exact README model-token comparison remain.
The selected manifest and original checker are unchanged. No flash, global
reset CSR or DRAM_INIT override was written. The goal remains active.


## MIG routing and exact model receipt, 2026-10-11 09:08 HKT

Previous goal turn made progress: corrected shared-clock lookup and launched
implementation. The same live job72196 / parent48404 / child48637 advanced
through placement and physical optimization, and is now routing with a maximum
of8 CPUs. Initial routing completed; overlap refinement is progressing.
Intermediate WNS+0.548ns is not final timing; hold repair remains in progress.
Do not duplicate or restart this confirmed live job. No new FPGA image was
loaded; full memory/model qualification remains NOT_RUN for the new candidate.

A separate read-only synthesized CDC audit exited0 (session87736). Its first
attempt17605 exited1 because standalone synthesis-DCP use needs early clock
constraints reimported; only that audit setup was fixed, and both attempt logs
are preserved. The current audit imported the same board/MIG/JTAG clocks and
all late constraints successfully. Its detailed parser accounted for3366
endpoints. All3312 non-Info endpoints were source-reviewed in six groups: held
CSR requests1628, held CSR responses68, return-FIFO heads into AXI skid buffers512,
held JTAG requests572, responses531 and the vendor temperature-word filter1.
The temperature RTL uses five ASYNC_REG stages and a saturating stability
counter; multi-bit synchronization alone was not accepted as atomic. Source
witnesses and endpoint keys are in preflight-cdc-source-review.json. Final
routed CDC endpoint coverage and all final timing/route checks remain required;
this pre-route receipt is not a programming pass. The original DDR800 checker
stays unchanged. The dedicated candidate checker now parses detailed reports
and requires every critical/warning endpoint key covered by the final review.

The normal model check now prints actual/ISA token arrays and optionally records
them through the physical transport. mig_host.py saves those arrays and refuses
a successful model stage without one nonempty exact comparison. It logs successful
64-byte memory-transfer progress every10s. The six host failure-gate tests still
pass. All8 model files and6 numerical source files match the saved ISA reference:
expected tokens[1098,5706,803,4481,856,5242,523,7], text
“The capital of France is Paris.” Runtime source witnesses were saved.

The SRAM-only program_candidate.py is prepared. After implementation exits0
and final route/timing/CDC audits pass, use a new programming receipt directory;
it audits before USB access, runs the strict existing DLC10 initializer/chain
parser, rechecks the same bitstream and manifest, then requires INIT/DONE after
SRAM loading. Start the existing verified localhost XVC server only after that
process exits. Run both full2GiB/channel pattern/ECC tests, followed by the normal
selftest with --model lfm2 --tokens8 --wformat int8 and verify captured exact tokens.
No flash, global-reset CSR, failed-memory bypass, selected-image change or new
physical computation occurred in this turn. Goal remains active.


## Final MIG image qualified; USB reconnect needed, 2026-10-11 09:22 HKT

Native implementation session72196 completed with actualexit0 at09:13HKT.
All final reports/checkpoint are complete. Independent audit PASS: all290292
routable nets fullyrouted, zeroerrors, WNS+0.235ns/WHS+0.026ns/WPWS+0.264ns,
all30bus-skew bounds met. All247pins/standards, 716DSPs, both complete MIG PHYs
and expected clocks/configuration pass. Newbit12,870,600bytes SHA256
0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f.
Candidate ../openTPU/build/fedora-vivado/mig-jtag-controller-20261010T235833Z/.
Final CDC reviewed all3312 non-Info endpoints. All1945 changed representative
fan-in rows were checked against actual final paths/protocols/clock domains;
no unmatched endpoint remained. Extra read-only audit93810 exited0; all755
methodology and725DRC entries reviewed. Replica audit9428 exited0: all32 copied
FIFO address registers have no first-stage Gray synchronizer fanout. No new
placement/routing job is running; do not rebuild the qualified image.

Fresh JTAG scan at09:11HKT exited0: one0x23751093/IR6, expected chain-end.
Kernel logged DLC10 disconnect at09:13HKT followed by USB descriptor error-71;
current lsusb has no03fd cable and sysfs1-2 is absent. Actual programmer attempt
physical-jtag-20261011T011921Z exited1 at cable initialization ('No DLC10 found'),
before SRAM programming. No new FPGA image/flash write occurred. The user was
asked to reconnect the cable USB end, with FPGA power settings unchanged.
This is a missing USB adapter at this point, not evidence of a card/power fault.

Once oneDLC10 returns, use candidate program_candidate.py --out NEWDIR (newpath),
then existing verified tools/fedora_xvc_server.py. Check both MIG calibration
flags; run full memtest, then normal selftest --model lfm2 --tokens8 --wformatint8.
The normal model check captures exact actual/ISA tokens and refuses a missing
comparison. Receipts also include full BIST scrub results;6host gates still pass.
Full physical memory/model qualification is NOT_RUN for this candidate. Original
selected DDR800 manifest/bit/checker remain available unchanged for SRAM rollback.
Goal stays active; no failed-memory bypass, DRAM_INIT override or globalresetCSR.

The additional 60-second USB observation also found no DLC10. A software port-reset attempt could not execute because sudo requires a password; no port state was written. The port remains enabled (disable=0). No background hardware client remains. See the failed programming directory usb-disconnect-result.json for current USB/kernel evidence. Resume after physical USB replug.


## USB connection still unavailable, 2026-10-11 09:27 HKT

The previous goal turn made concrete progress by completing native implementation and the final offline audits. This continuation found the same external USB blocker. Fedora logged a fresh connection attempt at 09:24 HKT, but it again ended with descriptor error -71 and no enumerated DLC10. A further 45-second observation also found no adapter; receipt: ../openTPU/build/fedora-vivado/usb-enumeration-recheck-20261011T012617Z/result.json. The complete image audit passed again with the same bitstream SHA256. No image was loaded and no physical model computation ran. The user was asked to connect the USB end directly to a different Fedora port. This is the second consecutive goal turn with the same blocker; the goal remains active. No live build or hardware client is pending.


## Goal blocked on DLC10 USB, 2026-10-11 09:28 HKT

The previous goal continuation made no hardware progress because the DLC10 did not enumerate. A fresh third consecutive check again found no Xilinx USB adapter and no live build or hardware client. The qualified bitstream still has SHA256 0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f. The goal was set to blocked after the required three-turn audit. No SRAM programming, full physical DDR qualification or README model comparison has run for this candidate. Resume after the cable USB connection is restored; use a new programmer receipt directory, then XVC, full memory tests and the complete normal model selftest. Do not rebuild the qualified image or bypass the failed-memory gates.


## User resumed; intermittent USB connection, 2026-10-11 12:59 HKT

User reconnected and explicitly set the goal active. The full image audit passed again with the same qualified MIG bitstream. Device030 did enumerate as03fd:0013 at12:51:08HKT, but disconnected at12:51:31. The actual SRAM-programmer attempt at12:51:46 therefore exited1 before programming because no DLC10 was present. Its receipt is physical-jtag-20261011T045146Z/result.json. Kernel then recorded a further descriptor error-71. An automatic loader watched for120seconds and would have started the strict programmer as soon as one adapter stabilized; session42839 is now terminal, actualexit1, zero programming attempts. Receipt auto-program-20261011T045413Z/state.json. No image or flash was written, no new memory/model test ran, and no client remains. The user was asked to reconnect once and leave USB connected. This resumed run starts a fresh blocker audit at1; the old three-turn blocked record is retained as history. Goal remains active.


## Automatic USB loader still waiting, 2026-10-11T13:05:33.598747+08:00

A single bounded 900-second watch is live: session 71592, PID 80732, started at 13:02:07 HKT and due to stop observing at 13:17:07 HKT. Receipt: ../openTPU/build/fedora-vivado/mig-jtag-controller-20261010T235833Z/auto-program-20261011T050206Z/state.json; fresh USB/PID evidence is live-recheck.json in the same directory. The fresh scan has no Xilinx USB device; the watcher state is WAITING_FOR_DLC10 with 0 attempts. The quoted Device 030 was recorded by the kernel at 12:51:08 HKT and disconnected at 12:51:31 HKT. Programming has not started. Preserve this watcher; do not start a duplicate initializer or mutate the candidate manifest during a programming attempt. Once SRAM programming returns actual exit 0 and INIT/DONE, start XVC, check both MIG calibration flags, run full DDR/ECC tests, then the normal LFM2 selftest and exact ISA token comparison. The goal remains active pending a stable USB connection.


## Resumed goal blocked on USB, 2026-10-11T13:08:50.399636+08:00

Three consecutive resumed goal turns confirmed the same missing DLC10 USB connection. The previous turn was a verified wait on session 71592; the fresh third check again found no Xilinx adapter. update_goal returned status blocked. Evidence: ../openTPU/build/fedora-vivado/mig-jtag-controller-20261010T235833Z/auto-program-20261011T050206Z/goal-turn-3-usb-audit.json. The qualified bitstream SHA256 is unchanged. SRAM programming, full DDR/ECC tests and physical LFM2 token comparison have not started as of this check.

The existing bounded watcher (session 71592, PID 80732) is preserved. It observes until 13:17:07 HKT and can still start the already-authorized guarded SRAM loader if exactly one adapter returns. Do not mistake this blocked goal status for a terminal watcher. On user resume, poll the same session and inspect its actual state, attempt result and command exit before launching any initializer. If it already loaded SRAM with exit 0 and INIT/DONE, continue directly with XVC, both calibration checks, complete DDR/ECC patterns and normal LFM2 selftest with exact ISA token comparison. Otherwise wait for stable USB and choose a new receipt directory only after the existing job is terminal. The candidate manifest was left unchanged to preserve the initializer hash guard.


## Vivado MIG image programmed; full DDR passes, 2026-10-11T14:04:11.030364+08:00

Device 033 was present as 03fd:0013. The old 900-second watcher was confirmed terminal (actual exit 1, zero attempts) before any new initializer started. The new guarded SRAM programmer completed actual exit 0 at 13:57:45 HKT, expected IDCODE 0x23751093 and INIT=1/DONE=1. New physical receipts: ${OTPU_ROOT}/build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z. Flash was not written; the selected old DDR800 pointer is retained only for rollback.

The first XVC invocation exited on stdin EOF; it was confirmed terminal before a persistent PTY invocation started. Live XVC session 93293/PID 92002 listens on 127.0.0.1:3721. Physical SMI exited 0: OpenTPU ID, D=128/MCOLS=4/LANES=8, 100 MHz, DDR3-1066, build 5b1e646c, both calibration flags true. The complete memtest exited 0: all 16 write/read passes (ones, address, xorshift, zero) cover all 33554432 64-byte beats on each 2 GiB channel, zero bad/corrected/uncorrectable beats, status 6 throughout. This is full 4 GiB physical memory evidence.

The complete normal selftest --model lfm2 --tokens 8 --wformat int8 is running: session 77894/PID 92284, console physical-selftest.console.log in the receipt directory. Link/config/calibration/scrub/register/address stages have passed. Pure JTAG writes measure about 15 kB/s; the 242628608-byte model weights alone are expected to take roughly 4.5 hours at that observed rate, after the remaining normal checks. Preserve this live command and XVC; do not start a second cable client or reset/reprogram the FPGA. Final hardware compute/model token comparison is still unproven. On resume poll the same handles and inspect actual terminal exit, full_memory_scrub, ECC and model_checks before declaring success. Latest process/stage evidence is candidate physical-status.json.


## Physical kernels passed; USB interrupted full selftest, 2026-10-11T14:52:52.621788+08:00

The normal selftest passed host address/region/pattern checks, 200 partial writes per channel, and both compute kernel programs. The all-units program completed 9124 cycles and the masked-write program 10865 cycles; both matched complete ISA reference output and retired instruction counts. The compiler/ISA LFM2 reference is saved, but physical LFM2 inference has not run.

At 14:48:03 HKT the kernel recorded Device 035 disconnecting, followed by USB descriptor timeouts (-110). XVC reported LIBUSB_ERROR_IO; the selftest stopped during vops with EOFError: XVC disconnected. Session 77894 is terminal, actual exit 1; final receipt has model_checks=[] and retains all four successful full 4 GiB scrub results. Stream/model stages were not reached. The failed XVC server was shut down normally via terminal input, session 93293 actual exit 0. Both processes are absent; no hardware client remains. Restore stable USB before any new initializer or full test. Earlier full 4 GiB pattern/ECC and kernel passes remain historical physical evidence, not a completed full-model result.

Documentation: ${OTPU_ROOT}/docs/fedora_vivado_jtag_results.md. Fresh failure/process evidence and hashed terminal receipts are in ${OTPU_ROOT}/build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/usb-failure-snapshot.json and hardware-run-review.json. No flash write, global reset or DRAM_INIT override occurred.
