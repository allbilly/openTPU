# OpenTPU progress

The checkout now lives at `~/openTPU`; shared tooling and other projects are
under `~/ypcb`. [Workspace layout and Git transfer](docs/workspace_layout.md)
records the compatibility aliases and the separation of source from generated
bitstreams/model archives. Current source/docs paths were updated; hashed
build receipts retain their original paths.

## Current priority: permanent CH1 PCIe boot (October 15)

**Permanent CH1 PCIe flash programming, separate readback verification and
JTAG-requested boot from flash have passed.** The run began at 07:44 HKT on
October 15 and took 8.8 minutes. The user explicitly chose to skip
preserving the old flash image; image, physical LFM2, target-ID and flash-part
checks remained enabled. Cold boot with JTAG disconnected and physical PCIe
operation on the other Linux PC remain unverified. No further DRAM diagnosis
was performed.
[Live programming receipt](build/fedora-vivado/permanent-pcie-live-current.json).

The [bitstream index](docs/bitstreams.md) lists every local `.bit`/`.mcs` file.
The standalone USER2 JTAG image that passed LFM2 and the PCIe image now stored
in NOR are separate Vivado builds sharing the compute RTL and CH1 memory core.
The PCIe `.mcs` is the flash representation of its matching PCIe `.bit`.

The programmer has exited; a read-only host check found no local FPGA PCIe
endpoint or XDMA nodes. The next gate needs a physical PCIe connection, on
this Fedora machine or the other Linux PC selected for the test. Save its
initial enumeration before any rescan, then run the matched host bundle; the
updated guide includes both cold-boot evidence directories and inference
commands. [Remaining-requirements audit](build/fedora-vivado/ch1-cold-boot-handoff-current.json).

Physical LFM2.5-230M inference passed over JTAG at 00:36 HKT: **“The capital
of France is Paris.”** All eight tokens matched the freshly executed ISA
reference. ECC stayed enabled with zero corrected or uncorrectable errors.
The user requested CH0 DDR recovery and permanent PCIe boot, then explicitly
deferred DDR repair and prioritized flashing the working CH1 configuration.

| Stage | Current evidence | Time / next step |
| --- | --- | --- |
| CH1 recovery core / full four-port ECC | Generated, firmware and ABI checked; 1,500-cycle ECC comparison passed | Reused; full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 |
| CH1 JTAG synthesis | Passed; saved checkpoint reused | Original build about 22 min through checkpoint |
| CH1 JTAG placement | Passed with zero warnings/errors | 16 min 11 s |
| CH1 JTAG routing | Passed; all 279,334 final nets routed, zero errors | 16 min 25 s |
| Final image checks | Setup +0.072 ns, hold +0.023 ns, pulse +0.264 ns; pins/CRC/CDC and all 30 bus-skew constraints passed | Bitstream generated; no rebuild needed |
| FPGA SRAM / CH1 calibration | Loaded and marker verified; full profile 100 MHz / DDR800, CH1 calibration passed | 8.22 s in the current run |
| New-image physical memory soak | 204 full 2 GiB passes, all nine lanes clean, ECC enabled/zero errors before soak | 91.21 s in the current run |
| Physical matmul | Passed on the FPGA: all 32 output words match ISA exactly; five instructions | 468 cycles in latest run; full 100 MHz compute profile |
| Full LFM2 | PASS on physical CH1: eight tokens exactly match fresh ISA; answer names Paris; ECC enabled and clean | 161.27 s generation wall time after upload; approximately 25.6 device decode tokens/s from 3.91 Mcycles/token at 100 MHz |
| CH0 DDR recovery | Full 2 GiB PRBS fails on lane 6; stricter phase scan and 1,024 common lane framing/tap combinations found no pass. CH1 remains ready | Deferred by user; no more DDR diagnostics queued |
| Permanent PCIe boot | Image review complete for normal operation; memory/compute RTL matches physical LFM2 image, all 39 bus-skew constraints met, MCS matches bitstream | PASS: flash write, separate verify-only operation and JTAG-requested flash boot; cold boot/PCIe host testing next |
| OpenXC7 | Existing routing run preserved at secondary priority | Does not provide the verified hardware result above |

[Permanent PCIe programming and other-PC commands](docs/permanent_pcie_ch1.md).
The matched 490,752,000-byte host archive is prepared. Earlier programming waited five minutes and stopped because the adapter was absent;
that earlier attempt made no hardware access or flash write. The current programmer subsequently completed flash write, verification and JTAG flash boot. Historically the adapter disappeared
at 02:16:22 and again at 02:29:45 HKT while no JTAG test/programmer was running.

[DDR notes and freshly fetched upstream comparison](docs/ddr_calibration_review.md):
origin main is `7e42a626`, while the modified checkout remains at `5b1e646c`.
The latest upstream contains no new PHY or calibration-firmware repair.
The address/pattern diagnostic did not establish aliasing because lane 6's
baseline PRBS reads already failed. The experimental firmware requires a
second pattern during the scan and full-capacity validation before readiness.

The [CPU ISA benchmark](build/fedora-vivado/isa-decode-benchmark-20261014T165200Z/result.json)
measured **0.647 decode tokens/s** with all eight CPU threads. FPGA device
cycles imply **25.6 tokens/s**, about **39.5 times** that rate. JTAG generation
wall throughput was only **0.0496 tokens/s**, including prompt/transfer overhead
and excluding weight upload; PCIe throughput has not been measured here.

The current run already uses LiteDRAM's lane calibration, with both virtual
channels mapped onto physical CH1. Upstream's successful dual-channel builds
are a useful reference for later CH0 recovery; they do not establish a repair
on this card. Service `opentpu-ch1-jtag-lfm2-20261014t120700z.service`
(invocation `ad0bce9949964bb3994fbec5e28da4be`) completed with exit status 0.
The [audited physical pass](build/fedora-vivado/ch1-lfm2-physical-pass-current.json)
binds the bitstream hash, source manifests, full compute identity, exact matmul,
model tokens and ECC result. The standalone JTAG image remains the fallback;
the separate PCIe image has passed its normal-runtime review, permanent programming, verification and JTAG flash boot. Physical PCIe operation remains to be verified.

## Historical build and bring-up notes (October 14)


The original post-synthesis clock check used `ld_sys_clk`, an alias removed by
synthesis. A fresh probe confirmed 100 MHz at `u_ld/MMCME2_ADV/CLKOUT0`.
The resume now uses that pin and reads board clocks before DDR uncertainty
constraints. A first resume also checked Vivado's `NAME` property instead of
`TOP`; that attempt is preserved and the corrected resume checks `TOP`, with
part/top independently verified from the checkpoint XML. Synthesis is not rerun. A further scoped-constraint attempt was stopped before
placement because synthesis merged the three memory-interface clock aliases.
The selected resume binds those constraints to the verified common 100 MHz
clock, sources each instance's constraints, and has reached `opt_design` with
zero critical warnings or errors. The two current services are live and the
DLC10 remains detected as `03fd:0008`. At 18:55 HKT, `opt_design` had
finished with zero warnings, critical warnings and errors; placement had started
with a maximum of eight CPUs and zero pre-placement DRC errors.
[Fresh implementation receipt](build/fedora-vivado/ch1-jtag-resume-live-20261014T105500Z.json).
At 19:06 HKT, global placement had completed and detailed placement was active
under the same service invocation. The queued physical runner had not accessed
hardware. [Verified wait receipt](build/fedora-vivado/ch1-jtag-progress-20261014T110600Z.json).
At 19:08 HKT, the same live build had reached detailed placement of the smaller
logic groups; both exact services/processes remained active with no build
error. [Latest wait receipt](build/fedora-vivado/ch1-jtag-progress-20261014T110800Z.json).
At 19:12 HKT, placement had completed successfully in 16 minutes 11 seconds
with zero warnings/critical warnings/errors. The placed checkpoint part/top
and hash were verified; pre-route physical optimization remained live.
[Placement pass receipt](build/fedora-vivado/ch1-jtag-placement-pass-20261014T111200Z.json).
At 19:14 HKT, pre-route physical optimization had passed in 81 seconds with
zero warnings/critical warnings/errors. Native routing started with up to eight
CPUs; the same build and queued JTAG runtime were confirmed live. No new image
has been programmed, and no physical model output is claimed.
[Routing start receipt](build/fedora-vivado/ch1-jtag-routing-start-20261014T111400Z.json).
At 19:21 HKT, the initial routing pass had completed and rip-up/reroute was
active under the same exact service/PID. Initialization counted 279,299
routable nets; its initial `Failed Nets` field represented still-unrouted nets,
not a terminal routing failure. Final timing remains unqualified. The secondary
PCIe audit now also has CPUWeight 10 to favor the JTAG image.
[Latest routing receipt](build/fedora-vivado/ch1-jtag-route-progress-20261014T112100Z.json).
The JTAG image subsequently completed all offline checks and SRAM programming.
Its first physical run calibrated CH1 and passed 204 full-capacity memory checks.
The host then read VERSION (offset 0x04) while its guard incorrectly treated that
register as STATUS (offset 0x0c), raising a false calibration-loss error before
matmul. The guard now uses the named STATUS register and CALIB0/CALIB1 flags;
six regression tests passed. The same qualified bitstream is being rerun in a
fresh receipt directory. This failure did not establish DDR data loss or USB
disconnection. Physical matmul and model output remain unverified.
[Hardware and guard-fix handoff](build/fedora-vivado/ch1-jtag-hardware-handoff-20261014T114400Z.json).
The corrected run passed real matmul and started the full model upload. Its
measured rate was about 15 kB/s. A short controlled hardware comparison tested
one local RPC per acknowledged command and 6 MHz TCK, using an 8 KiB scratch
region at the end of virtual CH0. All readbacks matched and ECC counters stayed
zero; neither change improved the write rate. The existing acknowledged
three-RPC protocol at 3 MHz was selected and a fresh full model run is live
under unit `opentpu-ch1-jtag-lfm2-20261014t120700z.service`, PID 950546, invocation
`ad0bce9949964bb3994fbec5e28da4be`. Its new memory soak and exact physical
matmul passed. Model transfer is active; inference and ISA token comparison
remain pending. The one-RPC prototype is not used by this run.
[3 MHz comparison](build/fedora-vivado/ch1-jtag-rpc-bench-20261014T120000Z/manifest.json) ·
[6 MHz comparison](build/fedora-vivado/ch1-jtag-rpc-bench-20261014T120400Z/manifest.json) ·
[Current upload measurement](build/fedora-vivado/ch1-lfm2-upload-current.json).
At 20:52 HKT, the same LFM2 process remained live and its upload byte count
had increased. The PCIe offline audit passed route/timing/pins/CRC, and a
read-only probe verified calibration synchronizer properties, clock-mux wiring
and the eight GTX reserved clock pins flagged for pulse-width checking. All
39 PCIe bus-skew constraints met. PCIe CDC/pulse-width review is still partial;
no PCIe image programming or flash work was performed.
[Partial PCIe review](build/fedora-vivado/ch1-pcie-cdc-partial-review-20261014T125200Z.json).
A second read-only probe completed and traced all eight GTX `CLKRSVD[0]`
pulse-width items to the vendor OOB divider output registers. No clock object
was present at those pins. The frozen vendor RTL selects counter bit 1 or 0
(divide-by-4 or divide-by-2). This requires generated-clock/mode review before
the PCIe image review can pass. The currently running JTAG image has no PCIe
GTX/OOB circuitry and its upload was not stopped.
[OOB clock handoff](build/fedora-vivado/ch1-pcie-oob-clock-handoff-20261014T130200Z.json).
A fresh offline clock-model checkpoint now defines all 32 conservative OOB
mode clocks across eight lanes. The previously reported eight pulse-width-clock
items became zero, while numerical setup/hold/pulse timing, all 321,303 routed
nets and all 39 bus-skew constraints still passed. No netlist, placement or
routing operation was performed and the running FPGA image was not changed.
PCIe CDC/vendor-reset review is still pending; this does not authorize flash
or claim physical PCIe operation. The JTAG upload remained active with an
increasing byte count under its original service/process.
[Offline clock-model pass](build/fedora-vivado/ch1-pcie-oob-clock-model-pass-20261014T131900Z.json).
The PCIe CDC review verified calibration/status crossings and the three vendor
reset chains (four ASYNC_REG-marked registers per exported chain, depth five
in the CDC report). The two LiteDRAM clock-generator reset-strobe crossings
still need a pulse-capture/reset-semantics review. No complete PCIe
programming approval was issued. The same JTAG model upload continued with
byte-count progress and no new hardware/transport error.
[Reset review handoff](build/fedora-vivado/ch1-pcie-cdc-reset-review-20261014T132900Z.json).



[Current build](build/fedora-vivado/ch1-jtag-current.json) ·
[Queued physical run](build/fedora-vivado/ch1-jtag-lfm2-current.json) ·
[CH1 recovery instructions](docs/ch1_recovery.md).

Older dated observations below are historical and do not supersede this priority.

<!-- OPEN_TPU_CURRENT_HANDOFF_START -->

<!-- OPEN_TPU_SERIAL_PHASE_MILESTONE -->

At **October 14 00:31 HKT**, the preserved native route finished the horizontal
batches and entered serial cross-partition routing. The remaining connection
count was **385,746**, down **4,655** from 00:26 HKT. The original cross-partition
batch contained 70,693 scheduled nets; the current position could not be read
because the optimized binary's debug parameter was unavailable. This is a
phase transition, not a completed congestion iteration or legal-route proof.
[Phase evidence](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/cross-partition-phase-20261013T163137Z.json).

At **00:36 HKT**, serial routing remained active with **385,302 connections**
remaining, a decrease of **444** over its first observed five-minute interval.
This short interval does not establish a dependable phase completion estimate.

<!-- OPEN_TPU_RESOURCE_CHECK_20261014_0106 -->

The **01:06 HKT** resource check confirmed the same native PID/start and service
invocation. Its cgroup used **11.6 GiB** under the **24 GiB** memory cap, used no
swap, and had zero OOM/max events and zero recent memory pressure. The host had
about **19.5 GiB available RAM**. CPU quota remained unlimited. These measurements
show current memory headroom; they do not qualify timing or delivered CPU clock.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T170612Z.json).

<!-- OPEN_TPU_OBSERVER_RECOVERY_20261014_0146 -->

The **01:41 HKT** observation timed out after 15 seconds and detached from the
same native process; the observer service remained live. Its **01:46 HKT**
observation succeeded with **379,535 connections remaining**, down **191 over
10 minutes** since the last valid sample at 01:36. The router stayed in serial
cross-partition routing. Neither the router nor observer was restarted.
[Timeout receipt](build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/sample-20261013T174126Z/manifest.json) ·
[Recovered sample](build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/sample-20261013T174626Z/manifest.json).

<!-- OPEN_TPU_RESOURCE_CHECK_20261014_0204 -->

The **02:04 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events, and zero recent memory pressure. Host available RAM
remained about **19.5 GiB** and CPU quota was unlimited. This is memory headroom,
not a delivered-frequency or numerical-timing qualification.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T180445Z.json).

<!-- OPEN_TPU_RESOURCE_AND_OBSERVER_20261014_0306 -->

The **03:05 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**19.1 GiB available RAM** and CPU quota remained unlimited.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T190509Z.json).

The **03:06 HKT** observer attempt hit its 15-second timeout and detached. The
same router remained live and CPU-active; no route restart or terminal exit was
recorded. This unsuccessful attempt provides no new valid remaining count.
The last valid snapshot remains **372,824 at 03:01 HKT**, and the observer is
scheduled to attempt another sample at 03:11.
[Timeout receipt](build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/sample-20261013T190626Z/manifest.json).

The **03:11 HKT** sample succeeded without restarting the router or observer.
It measured **371,421 remaining connections**, down **1,403 over 10 minutes**
since the last valid 03:01 observation. Serial cross-partition routing is still
active and the first congestion iteration remains incomplete.
[Recovered sample](build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/sample-20261013T191126Z/manifest.json).

<!-- OPEN_TPU_RESOURCE_CHECK_20261014_0404 -->

The **04:04 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**22.6 GiB available RAM** and CPU quota remained unlimited. These are current
resource measurements; routing legality and numerical timing remain pending.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T200455Z.json).

<!-- OPEN_TPU_RESOURCE_CHECK_20261014_0503 -->

The **05:03 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**22.5 GiB available RAM** and CPU quota remained unlimited. These measurements
show resource headroom; routing legality and numerical timing remain pending.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T210329Z.json).

<!-- OPEN_TPU_SEARCH_QUEUE_AUDIT_20261014_0520 -->

The **05:20 HKT** read-only log audit verified the warning fields against the
pinned router source: they are the forward and backward queue sizes at each
five-million-iteration reporting point. Across 31 warnings in the captured log,
the largest combined queue snapshot was **5,480,671 entries** on
`u_ld.csrbank0_base_r[14]` (2,950,284 forward + 2,530,387 backward). This is
a logged search snapshot, not an all-time peak or cumulative retry count.
The same native process remained alive; no route or observer was restarted.
[Source-qualified queue evidence](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261013T212012Z.json).

<!-- OPEN_TPU_SEARCH_QUEUE_AUDIT_20261014_0602 -->

The **06:02 HKT** source-qualified log audit recorded a larger queue snapshot
of **5,575,442 entries** on `u_ld.csrbank0_errors_r[27]` at **10 million search
iterations** (2,356,623 forward + 3,218,819 backward). The earlier warning for
the same connection at 5 million iterations had 4,485,469 combined entries.
These are queue sizes at logged milestones, not an all-time peak or cumulative
retry count. The same native process remained active and the first congestion
iteration is still unfinished.
[Updated queue evidence](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261013T220216Z.json).

<!-- OPEN_TPU_RESOURCE_CHECK_20261014_0603 -->

The **06:03 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**22.5 GiB available RAM** and CPU quota remained unlimited. These measurements
show resource headroom; routing legality and numerical timing remain pending.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T220319Z.json).

<!-- OPEN_TPU_RESOURCE_CHECK_20261014_0703 -->

The **07:03 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**22.6 GiB available RAM** and CPU quota remained unlimited. These readings
show resource headroom; legal routing and full numerical timing remain pending.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261013T230352Z.json).

<!-- OPEN_TPU_RESOURCE_AND_QUEUE_CHECK_20261014_0803 -->

The **08:04 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**22.5 GiB available RAM** and CPU quota remained unlimited.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261014T000401Z.json).
The **08:03 HKT** source-verified log audit captured **44 search warnings**;
the largest combined queue snapshot remains **5,575,442 entries**. The newest
warning had **3,583,876 entries**, on another activation-memory connection.
These are queue sizes at logged milestones, not all-time peaks or cumulative
retry counts. The route remains active; legal convergence and full timing are
pending. [Queue audit](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261014T000317Z.json).

<!-- OPEN_TPU_RESOURCE_AND_QUEUE_CHECK_20261014_0904 -->

The **09:04 HKT** resource check confirmed the same native PID/start and service
invocation: **11.6 GiB** cgroup memory under the **24 GiB** cap, zero router swap
use, zero OOM/max events and zero recent memory pressure. The host had about
**22.5 GiB available RAM** and CPU quota remained unlimited.
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261014T010419Z.json).
The same check covered **52 source-verified search warnings**; the largest
combined queue snapshot was **5,575,442 entries**, on
`u_ld.csrbank0_errors_r[27]`. The newest warning had **3,122,067 entries**.
These are queue sizes at logged milestones, not all-time peaks or cumulative
retry counts. Legal convergence and full numerical timing remain pending.
[Queue audit](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261014T010419Z.json).

<!-- OPEN_TPU_RESOURCE_AND_QUEUE_CHECK_20261014_0931 -->

The **09:31 HKT** source-qualified audit covered **58 warnings**.
Its largest logged queue snapshot is now **6,605,853 entries**
on `u_ld.csrbank0_errors_r[29]` at **10,000,000 search iterations**.
This records growth during an individual search; it does not prove a global
stall or routing convergence. The same native PID/start and service invocation
remain live. Cgroup memory is **11.62 GiB** under the **24 GiB** cap;
router swap is **0 bytes**, and memory events remain
`low 0; high 0; max 0; oom 0; oom_kill 0; oom_group_kill 0; sock_throttled 0`. Host available RAM is
**22.56 GiB**.
[Queue receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261014T013121Z.json) ·
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261014T013121Z.json).

<!-- OPEN_TPU_RESOURCE_AND_QUEUE_CHECK_20261014_1033 -->

The **10:33 HKT** source-qualified audit covered **66 warnings**, with a largest
logged combined queue snapshot of **6,836,755 entries**. The same native
PID/start and service invocation remain live. Cgroup memory is **11.62 GiB**
under its **24 GiB** cap, with zero router swap use, zero memory-limit/OOM events
and zero recent memory pressure. The host has **22.52 GiB** available RAM and
**283.15 GiB** available disk space. These checks do not qualify numerical timing
or establish a routing-completion deadline.
[Queue receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261014T023300Z.json) ·
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261014T023300Z.json).

<!-- OPEN_TPU_RESOURCE_AND_QUEUE_CHECK_20261014_1132 -->

The **11:32 HKT** source-qualified audit covered **76 warnings**, with a largest
logged combined queue snapshot of **6,870,012 entries**. The same native
PID/start and service invocation remain live. Cgroup memory is **11.62 GiB**
under its **24 GiB** cap, with zero router swap use, zero memory-limit/OOM events
and zero recent memory pressure. The host has **22.51 GiB** available RAM and
**282.91 GiB** available disk space. These checks do not qualify numerical timing
or establish a routing-completion deadline.
[Queue receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/warning-queue-audit-20261014T033240Z.json) ·
[Resource receipt](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261014T033240Z.json).

<!-- OPEN_TPU_PROGRESS_TABLE_START -->
Latest duration snapshot: **October 14 17:47 HKT**. The user explicitly chose
**CH1-only recovery to run LFM2 first**. Full compute dimensions and clocks are
preserved; memory capacity is 2 GiB. Physical CH0 repair and the ongoing OpenXC7
route are separate work. No physical LLM pass or permanent flash is claimed.

| Stage | Status | Time already spent | Remaining estimate |
| --- | --- | --- | --- |
| Vivado MIG JTAG bitstream | Historical basic compute passed; CH0 errors recur warm | About 16 min synthesis + 33 min implementation/export | Reference retained; full CH0 repair deferred |
| Matched DDR800 JTAG image | Native programming passed; compact MM failed and CH0 lane 6 errors recurred | About 2 h 49 min offline implementation | Reference retained; not used to claim LLM success |
| Native host warm calibration | USB disconnected during CSR write 0x160cc, before compute | 53 min 32 s for the interrupted run | No fixed register trigger proven; source driver alone did not cure USB resets |
| On-board warm calibration | CH1 passed in 8.30 s; CH0 lane 6 had no usable window at 53.4 C | About 8 s per physical channel | CH0 excluded from recovery user traffic |
| Physical CH1 warm qualification | PASS: 180 full 2 GiB passes, normal-port data match, ECC zero, 54.26–54.51 C | 90.91 s soak; about 1 min 52 s total controller | Completed for the reference image's physical CH1 |
| CH1 recovery core generation | PASS firmware/Verilog/CSR and port ABI; four virtual native ports share CH1 | Successful isolated generation completed; earlier portability failures retained | Full ECC gate still pending |
| Four-port ECC comparison | Live; cycle 1092 of 1500 with zero errors at 17:45 HKT | More than 100 min; exact child remains CPU-active | Full terminal test pass required before programming |
| CH1-only PCIe Vivado build | Synthesis passed; detail placement active, eight workers requested | About 47 min since 16:59 HKT | Prior native PCIe build: 1 h 47 min total; route and image checks still pending |
| Recovery host and full LFM2 bundle | Seven guards PASS; frozen source/core/checkpoint archive and checksum/CLI checks PASS | Bundle prepared this turn; tests 0.03 s | Full LFM2 host bundle ready; no bitstream included |
| Physical matmul / LFM2 | Not started with recovery image; user confirms bench power/JTAG only | No completed physical recovery-model run | This new image requires PCIe connection on the other Linux PC, plus completed image gates |
| Dual-channel native PCIe reference | Offline route/timing/DRC and bit/MCS creation completed | 1 h 47 min, 14:03–15:50 HKT | Physical use still unverified; it does not bypass CH0 |
| Permanent PCIe flash boot | Not written; conditional on physical LLM success | No flash programming performed | After model success: image qualification, chip identity, backup, programming/verify and cold boot |
| Full OpenXC7 synthesis/mapping | Complete for frozen full design | About 2 min final LUT mapping; frontend/development took longer | Complete |
| Full OpenXC7 placement | Complete and preserved | About 3 h 12 min successful run | Complete |
| Replay and primitive checks | Passed for selected backend | About 3 min latest checks | Full route and numerical timing pending |
| Full FF placement inventory | All 179,299 registers mapped and independently reviewed | About 8 s collection + 18 s review | Routed/electrical context and full timing pending |
| Isolated full OpenXC7 route | Same PID/start; first iteration, serial cross-partition phase; 207,898 flags remain at 14:36 HKT | About 25 h 44 min in this attempt; overall work spans days | No dependable completion ETA; earlier 12:21 projections were conditional flag-clear scenarios |
| Five-minute route diagnostics | Same observer active; no route restart | Brief attachment per sample, every 5 min | Continues while selected native route lives |
| DSP image correction | Primitive differential and full 717-site map passed | About 17 s native probe plus full map review | Guarded image followers wait for successful terminal route |
| OpenXC7 image/CRC pipeline | Guarded original, DSP-corrected and CRC followers waiting | No completed full OpenXC7 image | Route, full timing and image gates remain |
| Documentation | Failure traces and current model-first owner saved | This update | Results will be updated from actual exits and model tokens |

[Vivado bitstream guide](docs/vivado_bitstream_guide.md) ·
[OpenXC7 bitstream plan](docs/openxc7_bitstream_plan.md)

Latest measured routing state (October 14 **14:36:40 HKT**): **207,898**
unique driven sink connections remain without routed flags in iteration 1.
The route is still in serial cross-partition routing; these flags do not prove
congestion legality or final timing. The selected native PID remains 400903,
start ticks 21826315. [Live five-minute measurements](build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/latest.json).


[Measured plot, data and conditional estimate](docs/openxc7_routing_estimate.md)
use 211 compatible snapshots through October 14 12:21 HKT, with 211,813
connections remaining. The two-hour and one-hour rates are about 2,168 and
2,027 connections/hour, projecting **98–104 additional hours (4.1–4.4 days)**
to clear the flags at constant rates. The half-hour rate projects 85 hours.
None of these windows is dominated by one sampling interval. These are
conditional rate projections, not a confidence interval or bitstream deadline;
congestion legality, full timing and image qualification remain pending.

The [complete DSP parameter review](build/fedora-openxc7/dsp-encoding-impact-20261013T120252Z/manifest.json)
identifies upstream encoding differences affecting 403 A-cascade settings,
562 B-cascade settings and 189 missing default MASKs across all 717 DSPs.
These counts overlap; this is parameter-level impact, not frame/hardware proof.
A separate [full DSP-emitter candidate](build/fedora-openxc7/dsp-full-emitter-candidate-20261013T123000Z/manifest.json)
now builds and starts successfully. Its change is confined to the DSP-emitter
function; the active router remains unchanged. Native cascade and strict
frame checks passed. All six register/MASK configurations match 51 selected
configuration bits across all 717 Vivado reference DSPs, with zero mismatches.
[Actual DSP frame comparison](build/fedora-openxc7/dsp-frame-comparison-20261013T131300Z/manifest.json).
Other DSP fields, full-image provenance and numerical timing remain pending.
A [qualified correction map](build/fedora-openxc7/dsp-fasm-correction-prepared-20261013T132700Z/manifest.json)
now covers all 717 preserved-placement DSPs and reproduces every non-comment
feature of the new native witness. The original outputs remain preserved.
[Separate corrected-image follow-up](build/fedora-openxc7/dsp-corrected-image-followup-runtime-20261013T140400Z/manifest.json)
is active and waits for the route and original image pipeline to pass;
then it repeats strict assembly, packet/frame/ECC and source checks.
Its live-route guard returned 2 and created no image. It does not program hardware.

Latest [read-only runtime audit](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/runtime-resource-audit-20261014T033240Z.json)
records no memory-limit/OOM events, zero router swap use, all eight CPUs
allowed and no CPU quota. Host MemAvailable is about 22 GiB, with about
283 GiB of disk space available for remaining route/image outputs. CPUFreq policy
readings are not delivered-clock measurements; privileged turbostat access
was unavailable and perf is not installed. The resource check did not change
the router or host settings.

[Latest Vivado hardware attempt](build/fedora-vivado/physical-jtag-resume-20261014T041625Z/manifest.json)
ended with actual selftest exit 1 at October 14 12:18 HKT. The same verified
MIG image loaded into SRAM with INIT/DONE and responded to physical SMI;
both calibration flags were set. Channel 0's full zero readback then reported
24,886,072 bad beats, 24,789,197 corrected beats and 24,730,483 uncorrectable
beats. No compute/model stage was reached. The XVC owner exited; flash was
untouched. The earlier USB-wait owner also terminated before programming
when initialization found no cable; both failed receipts are preserved.

[Targeted DDR diagnostics](build/fedora-vivado/mig-readback-debug-20261014T042746Z/manifest.json)
preserved the original counters, then checked zero/ones/address/xorshift in
three separated 256 KiB regions on each channel. Channel 0 failed 8 of 12
pairs; channel 1 passed all 12. Mismatch masks concentrate in data bits
48–55, with some masks also including bits 46–47. Counter clearing isolates
trials and does not repair memory or erase the saved failure evidence.
This localizes the failure but does not establish a power, board, read/write
or calibration root cause.

[Same-image retraining trial](build/fedora-vivado/mig-readback-retrain-20261014T042940Z/manifest.json)
was the owner for that completed trial, unit
`opentpu-mig-readback-retrain-20261014t042940z.service`, PID 728731,
invocation `60d10a4872ea4196a2afd9754a9c0df7`. It performs a guarded SRAM
reload of the unchanged original MIG image, repeats the small-region checks,
and runs the full four-pattern memory test only if all small checks pass.
All **24 targeted pairs** and **16 complete memory passes** now pass with zero
data/ECC errors, and normal selftest has also passed its full 4 GiB scrub.
That selftest later stopped at the host pattern stage after USB Device 083
disconnected and returned as Device 084 at 12:32:36 HKT. The run passed both
channel address checks before the disconnect; complete compute/model results
remain pending. The XVC owner is terminal with actual selftest exit 1. This recovery after reloading the same bitstream
is consistent with a transient DDR training/timing-margin issue, but does not
establish a permanent fix or exclude a supply/board cause. Clocks, voltage
settings, BPI flash and the live OpenXC7 route are unchanged.

[Native Vivado read-only chain/mailbox probe](build/fedora-vivado/native-jtag-driver-probe-20261014T043611Z/manifest.json)
passed with the expected single XC7K480T and OpenTPU USER2 magic. A subsequent
[native-driver full-memory trial](build/fedora-vivado/native-jtag-fulltest-20261014T044240Z/manifest.json)
reproduced channel 0 errors at 12:42 HKT: 350,549 bad beats and uncorrectable
beats during the full ones read, while USB remained present. The earlier
reload recovery therefore does not establish stable DDR operation; the data
failure is not specific to the openFPGALoader host driver. MIG already has
internal XADC temperature compensation enabled; it is not simply missing.

[Freshly retrained native-driver session](build/fedora-vivado/native-jtag-retrained-fulltest-20261014T044514Z/manifest.json)
was the owner for that failed reload attempt, unit
`opentpu-native-jtag-retrained-fulltest-20261014t044514z.service`, PID 768779,
invocation `bce821c927244903ae568fb827a00df8`. It uses the frozen guarded SRAM
programmer and then Vivado's native driver at 3 MHz TCK, keeping FPGA clocks,
full compute profile and DDR3-1066 unchanged. Actual full memory and selftest
passes remain required; no failure is bypassed or hidden by counter clearing.
The [native transport helper](tools/fedora_run_vivado_native_jtag.py) passed
five wire-level tests covering scan framing, a fragmented 640-bit response,
error poisoning and invalid/oversized scan rejection. USB `power/control`
currently reads `on` with zero recorded runtime suspend time for Device 084;
that measurement does not prove Device 083's settings before its disconnect.

That reload was interrupted during SRAM loading at 12:45 HKT: the legacy
loader reported `LIBUSB_ERROR_NO_DEVICE` and aborted with actual exit -6.
The receipt is `FAIL` / `SRAM_STARTED`; its printed 100% is not a programming
pass. No flash was written. Stable FPGA configuration is therefore pending a
new successful load. Descriptor errors continued without active JTAG clients;
[USB chronology](build/fedora-vivado/dlc10-usb-recurrence-20261014T045443Z/manifest.json)
preserves the 12:32 automatic Device 083→084 re-enumeration and later failures.
The user manually reconnected the adapter before the 12:54 enumeration.

[Entirely native Vivado programming/test session](build/fedora-vivado/native-vivado-program-and-fulltest-20261014T045031Z/manifest.json)
was the owner for that completed native-load attempt, unit
`opentpu-native-vivado-fulltest-20261014t045031z.service`, PID 770557,
invocation `1bfd28001a9240479f9dcb4104c745f0`. Its frozen-image offline audit
passed with actual exit 0. It waited for USB, then started native chain checks
and native SRAM programming after the manual reconnect. INIT/DONE, expected
USER2 identity, full four-pattern memory checks and the complete physical
selftest/LFM2 comparison remain mandatory. Programming is not yet a verified
pass. Ten software checks passed, including negative Tcl fixtures rejecting
wrong/multiple devices and missing INIT/DONE; native programming remains
unqualified physically until this live attempt completes those gates.

The entirely native Vivado MIG load completed in about **70 seconds**, with
explicit INIT/DONE 1 and the expected mailbox. Its first memory gate stopped
because calibration flags were not set. A bounded calibration wait was added
and tested; the subsequent loaded-image retry observed both flags set, then
failed the full channel 0 ones read with **427,773 bad beats**, **227,341
corrected beats**, and **427,630 uncorrectable beats**. The saved OR mask is
again concentrated in data bits 48–55, also including 46–47.
[Calibrated native-MIG failure](build/fedora-vivado/native-vivado-loaded-fulltest-20261014T045831Z/manifest.json).
Neither a reload nor changing host drivers has established stable MIG memory.

[Full Vivado DDR800 image preflight](build/fedora-vivado/ddr800-image-preflight-20261014.json)
rechecks all output/source witnesses, matching generated PHY tables and all
243 physical pins against the already exercised reference. Two DDR reset pins
use SSTL15 instead of LVCMOS15 at the same nominal 1.5 V; no other pin-standard
difference was accepted. CRC was independently rechecked: both checkpoints
match. The compute design stays MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 at
100 MHz; this candidate uses the previously planned dual DDR3-800 LiteDRAM
profile rather than the failing MIG DDR3-1066 image. Physical qualification is
still pending; the preflight does not label the image a hardware pass.

The [first DDR800 session](build/fedora-vivado/ddr800-native-matmul-lfm2-20261014T051843Z/manifest.json)
passed programming/calibration/all 12 full raw-memory passes, then failed MM.
The [repeat memory check](build/fedora-vivado/ddr800-native-compute-debug-20261014T052351Z/manifest.json)
failed channel 0 lane 6 before compute. The [warm calibration](build/fedora-vivado/ddr800-warm-calibration-compute-20261014T052803Z/manifest.json)
stopped on USB loss at 13:29:45 HKT; its last request wrote `0x16018`, channel
0 DFII phase-0 write-data word 1. [Exact transaction/kernel evidence](build/fedora-vivado/dlc10-warm-calibration-drop-20261014T061453Z/manifest.json).

The former [model-first run](build/fedora-vivado/ddr800-model-first-20261014T063930Z/manifest.json)
passed native SRAM programming, then failed during host-driven calibration at
15:33 HKT. Its last failed request wrote `0x160cc`, physical CH0 DFII phase-3
write-data word 4. The adapter returned as boot PID `0013`; this is a different
register from the preceding failure. [Saved native-driver USB receipt](build/fedora-vivado/dlc10-native-model-first-drop-20261014T073906Z/manifest.json).

Restarting the on-board calibration CPU avoided the long register-transfer
path and exposed CH0 lane 6's missing window with USB still present. The
[physical CH1 warm test](build/fedora-vivado/ch1-physical-warm-soak-20261014T080444Z/manifest.json)
then passed 180 full-capacity BIST passes and normal-port readback with ECC
zero at approximately 54 C. These are physical CH1 results, not LLM proof.

The [CH1 recovery core](build/fedora-vivado/ch1-core-writable-20261014T082631Z/manifest.json)
retains full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 at 100 MHz and DDR800.
Both virtual channels map to physical CH1: physical beat `(m << 1) | c`.
Logical capacity is 2 GiB. The calibration CPU selects only physical CH1;
virtual ready flags explicitly represent CH1 readiness. No physical CH0 pass
is implied. Host capacity/marker guards have seven passing tests.

The new [recovery Vivado build](build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/manifest.json)
is `opentpu-pcie-ch1-recovery-overlap-20261014t085912z.service`, PID 845827,
invocation `1c7e1494e6d74bd79db464b3fb866c48`. Creation passed; native synthesis
uses eight workers. Its snapshot/cache are isolated. The full four-port ECC
comparison stays live (controller 835164, child 835165); at least 634 cycles
completed without errors in the saved memory observation. This is partial
progress, not a terminal pass. Offline building overlaps that test; FPGA
programming still requires its complete pass plus all implementation/image gates.
[Saved current handoff](build/fedora-vivado/ch1-recovery-handoff-20261014T091111Z/manifest.json).

[CH1 recovery guide and Linux test command](docs/ch1_recovery.md). The other PC
runs Linux and the user will run terminal commands. The recovered PCIe image
needs a PCIe slot for endpoint/compute tests. No card move or new upload is
claimed. Physical LFM2 and the conditional flash/boot verification remain open.

The failed pull fetched upstream e15b4a44 without merging into the modified
original worktree. A clean separate checkout exists at
`${YPCB_ROOT}/projects/openTPU-upstream-e15b4a44`; original changes and active
jobs were preserved. The recovery build uses the matched current snapshot.

**Latest user scope:** run physical matmul and LLM inference. Permanent flash
is authorized **only after successful physical LLM inference**, with the goal
of booting as an openTPU PCIe device without JTAG. The PCIe host will be
**another PC**. Both current bring-up images are JTAG-only; permanently
flashing either would not create a PCIe endpoint. A separately qualified
PCIe-capable image, the actual flash device/boot mode, and hardware PCIe
checks must be prepared for that final operation. No flash command has run.

The corrected DSP fixture exposed a genuine image-runtime bug: resolving the
venv Python symlink selected its base interpreter, losing the `fasm` package.
The [runtime-only correction](build/fedora-openxc7/image-runtime-fixed-20261013T140000Z/manifest.json)
preserves the venv invocation, pins 1,609 runtime files, and leaves all backend,
RTL, placement, profile and DSP qualification data unchanged.
[Actual corrected fixture image](build/fedora-openxc7/dsp-corrected-fixture-image-runtime-fixed-20261013T140200Z/manifest.json)
passes strict frames, exact native frame reproduction, bit generation and
all 46,336 packet/frame/ECC comparisons. It is a 64-DSP fixture, not the full
board image; independent CRC and numerical timing remain unqualified.
The two older image waiters were intentionally stopped before assembly;
[replacement audit](build/fedora-openxc7/image-followup-runtime-switch-20261013T140400Z/manifest.json)
proves the native route PID/start and service invocation were preserved.
Current image services use the runtime-qualified preparation:
`opentpu-replay-image-followup-runtime-20261013t140400z.service` and
`opentpu-dsp-image-followup-runtime-20261013t140400z.service`.

[Full FF absolute-site inventory](build/fedora-openxc7/full-ff-absolute-sites-20261013T150000Z/manifest.json)
and [independent review](build/fedora-openxc7/full-ff-absolute-sites-review-20261013T150200Z/manifest.json)
now pass for all 179,299 registers, 60,533 occupied slices and 60 observed
location classes. All 597,200 database FF BELs in 74,650 slices cross-check
against X-Ray. Every emitted record agrees with the original placement,
reference identities and characterized location class; wrong/missing/duplicate
grid-site corruptions are rejected. Both actual service exits are zero.
This closes native absolute placement coverage, preserving the live router;
routed input-mux/electrical context and full numerical timing remain pending.

[CRC qualification](build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/manifest.json)
matches both CRC checkpoints in both Vivado images. The native writer emits
CRC resets without checks. A separate protected fixture changes only four
packet words and passes two CRC checks plus all 46,336 frame/ECC comparisons;
corrupt frame-data and CRC-value copies are rejected. The actual converter
reproduces that copy exactly and creates no full image while its parent is live.
[Guarded full CRC follow-up](build/fedora-openxc7/crc-image-followup-20261013T153000Z/manifest.json)
is active as `opentpu-crc-image-followup-20261013t153000z.service`
(PID 484066, invocation `40fa0c8974c447ae9d5f34542ba7a065`). It waits for
successful native/DSP parent exits and all full-profile gates, then creates a
separate CRC-protected candidate. The native route and earlier image services
are unchanged; no original bitstream or hardware was touched.

<!-- OPEN_TPU_PROGRESS_TABLE_END -->


- **Authoritative interruption update, October 13 12:50 HKT:** kernel
  global OOM killed PID 157975 at 12:45:33; systemd then stopped the shared
  tmux scope with result `oom-kill`. All five native route PIDs and the
  primitive-check controller are absent, with no terminal route result.
  Earlier running observations below are historical. Launching a primitive
  check while RAM and swap were nearly full was a scheduling error.
  [Preserved host interruption evidence](build/fedora-openxc7/host-oom-process-loss-20261013T045000Z/manifest.json).
  Completed synthesis, placement, exact logical/physical review and replay
  fixture results remain preserved. Recovery will complete primitive checks
  first, then run only the corrected full placement replay in a separate
  memory-limited user service. No FPGA hardware was accessed.
  Recovery primitive qualification completed: all five native routes and
  six strict frame assemblies exit **0**. Independent review confirms exact
  primitive graphs, FASM and frames, plus restored clock bits.
  [New candidate primitive review](build/fedora-openxc7/replay-model-restored-primitives-reviewed-20261013T045600Z/manifest.json).
  The corrected full route has restarted as independent user service
  `opentpu-full-replay-route-20261013t045700z.service`, capped at 24 GiB RAM
  and 8 GiB swap, with all eight CPUs allowed. It reuses the complete
  reviewed placement; no old comparison job was restarted.
  [Current isolated full route](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/manifest.json).
  Installed router source confirms fixed batches of four quadrant workers,
  two vertical workers and two horizontal workers, followed by serial
  cross-partition/retry work. `--threads 8` and affinity 0-7 are present;
  CPU quota is unlimited. A five-second sample found one remaining worker
  at 100% CPU and the main thread waiting after other workers finished.
  Idle cores reflect this algorithm; no router or live job was changed.
  [Actual parallelism evidence](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/cpu-parallelism-check.json).
  Read-only net-search comparison proves the same remaining vertical
  worker moved to a different net between the 13:45 and 14:01 HKT snapshots.
  The latter search had 1,050,310 forward and 843,204 backward queue entries,
  plus 1,131,305 dirty wires. Its batch contains 23,129 nets total; an
  optimized-away loop iterator prevented a remaining-count measurement.
  One local net is deferred to the normal global fallback. This is actual
  search movement, not proof of a completed iteration or convergence.
  The corrected observer exits 0 with no tracer; the first observer's
  expression error is preserved and did not modify/restart the route.
  [Net-search progress comparison](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/router-net-search-progress.json).
  A later read-only snapshot recovered the batch position by reading the
  existing immutable net-pointer array and finding the current net exactly
  once. At 14:08:31 HKT, 21,259 nets preceded the current net and 1,869 nets
  followed it in this worker's 23,129-net batch. The earlier iterator was
  optimized out; no inferior function, mutation or backend patch was needed.
  This is one batch's ordinal progress, not a whole-route percentage or ETA.
  At that snapshot, horizontal/global work and subsequent congestion iterations remained pending.
  [Actual batch position](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/current-batch-position.json).
  A fresh read-only snapshot at October 13 18:01:51 HKT proves the vertical
  batch finished and both horizontal workers are active (worker source line
  1817, main thread joining at line 1820). One worker has 2,461 nets after
  its current net in a 12,139-net batch; the other has 6,206 after its current
  net in a 14,911-net batch. This is batch ordinal progress, not a whole-route
  percentage or convergence result. Cross-partition/fallback routing and
  later congestion iterations remain unproven. Observer exit 0, no tracer,
  unchanged PID/start and continued CPU work confirm the route was preserved.
  [Current routing phase](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/current-routing-phase.json).
  At 18:24:58 HKT, another read-only snapshot proves both horizontal workers
  advanced during the preceding 23 minutes: 773 and 418 additional batch
  positions. Their current positions are 10,450/12,139 and 9,122/14,911,
  leaving 1,688 and 5,788 nets after their current nets respectively. The
  latter active connection has 1,190,258 forward plus 871,218 backward search
  queue entries and 1,585,107 dirty wires. This supports expensive ongoing
  connection search, not stalled-process or convergence claims. Observer
  exit 0, no tracer, unchanged native identity and resumed CPU work verified.
  The original hardware-tested Vivado MIG bitstream was freshly hashed and
  matches its recorded SHA256; JTAG remains absent, so pending physical
  vector/stream/full-model tests cannot start. The recommended next step is
  the usable Vivado image while preserving the OpenXC7 route in background.
  [Horizontal-batch progress comparison](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/horizontal-batch-progress-comparison-20261013T102458Z.json).
  User-requested OOM audit confirms `constraint=CONSTRAINT_NONE,global_oom`:
  the prior failure was host-wide exhaustion, not a smaller cgroup trigger.
  The killed router held about 5.4 GiB RSS; the shared workload scope peaked
  at 33.9 GiB RAM and 23.2 GiB swap, with only 8 KiB system swap free at OOM.
  Linux currently exposes 39.6 GB / 36.9 GiB usable RAM. The new isolated
  native router holds about 11.6 GiB RSS with zero swap; its service counts
  about 15.2 GiB including charged cache, below the later 24 GiB cap. All
  memory-limit/OOM event counters are zero and CPU quota is unlimited.
  Current placement and native PID/start remain unchanged. No RAM, swap,
  worker-count or routing restart change is justified by this measurement.
  [OOM versus current cgroup audit](build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/oom-vs-cgroup-audit.json).
  Image preparation for this exact replay now passes, including candidate
  sources, all 31 frozen RTL inputs, full logical/physical placement review,
  primitive/frame qualification and original assembly database/tool hashes.
  Premature assembly returns **2** while native PID 400903 remains live;
  no full image directory or bitstream has been created.
  [Prepared replay image inputs](build/fedora-openxc7/replay-image-prepared-20261013T050200Z/manifest.json).
  Automatic offline image follow-up is now active as independent unit
  `opentpu-replay-image-followup-20261013t051800z.service` (16 GiB RAM / 4 GiB
  swap limits). It verifies the actual native/controller owner and selected
  route-unit invocation, then waits for native exit **0**, the completed full
  replay receipt and successful controller exit before strict image assembly.
  Its one-shot probe returned **2** with no image created. The route unit now
  retains its exit result with `RemainAfterExit=yes`; daemon reload preserved
  controller PID 400902, native PID 400903 and the original invocation/start.
  No route was restarted. The follow-up performs no hardware or flash action.
  [Automatic image follow-up](build/fedora-openxc7/replay-image-followup-20261013T051800Z/manifest.json).


- October 13: full congestion-aware placement completed with native exit **0**.
  It retains the full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 design,
  core **100 MHz** and dual **DDR800**. Main analytic placement took
  **7,448.08 s**; refinement stopped at iteration **72** after **3,957.39 s**.
  Native placement legality checks and export completed. The placed netlist
  is **1,783,556,291 bytes**, SHA256
  `90b5c3e6bf76ae48c8ded61336c8bb6df95ef71e81269aaac29fe6698c05d18b`.
  [Completed native placement](build/fedora-openxc7/full-congestion-heap-placement-20261013T001000Z/manifest.json).
  The initial reviewer rejected an added A6-to-VCC tie on a RAMD32 cell;
  its failed receipt and exact original helper are preserved. Deployed
  post-placement code explicitly performs this and logic-LUT original-port
  remapping. A revised reviewer checks unchanged logical connections and
  parameters, actual VCC source and compatible paired 5LUTs, alongside all
  full-design counts, physical bindings and synchronizer checks.
  Its captured RAMD32 and independent LUT permutation tests pass; ten
  corruption cases reject. These checks are not the full-design result.
  The complete final review **passes**: all **464,200** cells and their
  original logical connections/parameters are preserved, **464,198**
  non-pseudo physical assignments are unique, and all **179,299** FFs
  are exported across **60,533** distinct slice sites. Both three-stage
  synchronizers occupy actual AFF/BFF/CFF sites in one slice per chain.
  All **63,860** added A6 selector ties have verified VCC sources and
  actual compatible 5LUT companions. A reviewer BEL-name parsing error
  was corrected; its failed receipt is retained, and both real chains
  plus seven corrupt placement cases were checked.
  [Completed final full review](build/fedora-openxc7/full-congestion-placement-reviewed-final-20261013T033000Z/manifest.json).
  The next route will reuse this placement. Source inspection shows
  route-only reload skips building the measured delay-estimate matrix;
  an isolated xc7 backend now builds successfully with XDC processing,
  derived-clock regeneration and measured matrix/cache restoration.
  It also exports exact native bindings before and after routing. The
  first fixture rejected an empty clock audit because XDC originally ran
  only during packing. Reapplying pin properties then rejected duplicate
  attributes; both receipts and candidates are retained. The corrected
  replay uses a hash-pinned clock-only extraction of the original XDC,
  preserving already-reviewed pin properties and bindings.
  [Audited replay backend](build/fedora-openxc7/placed-replay-clock-only-backend-20261013T040500Z/manifest.json).
  The corrected **57-cell** clock-topology fixture **passes**, restoring
  all **39** constraints, preserving exact native bindings and producing
  identical FASM for rebuilt/cached measured matrices. Explicit matrix-off
  mode retains clocks/bindings and routes successfully with different PIPs;
  an overstrict test requiring that image to be identical is retained as a
  failed receipt.
  [Qualified replay fixture](build/fedora-openxc7/placed-replay-qualified-native-check-20261013T041000Z/manifest.json).
  The first full placement-replay route was intentionally stopped after
  source inspection confirmed that reload skipped the pack-only clock,
  DSP and SERDES timing-model initializers. Its **10 known / 2 unknown**
  phase-domain pairs differed from the reference **16 / 2**, so the
  attempt is not accepted as equivalent. Native exit **-15** records the
  intentional stop, rather than a device fit failure. Exact reload of all
  **464,198** non-pseudo bindings had passed before this stop.
  [Stopped full placement replay](build/fedora-openxc7/full-congestion-placed-route-20261013T041500Z/intentional-stop-reason.json).
  An isolated model-restoration backend compiled successfully. Its initial
  model-enabled fixtures rejected different packed clock-control modes:
  tying RST/PSEN/PSINCDEC low adds inversion parameters absent from the
  full design. These failed receipts are preserved. The corrected fixture
  uses an existing core-clock register for those diagnostic controls and
  verifies equivalent inactive PWRDWN polarity against the full inventory.
  Every native case now exits **0**: all **57** cells, **39** clock
  constraints and **16** diagnostic timing-domain pairs are preserved,
  including identical budgets and exact physical bindings. Measured matrix
  rebuilt/cached cases produce identical FASM; disabled-matrix routing
  also passes its defined checks. These are fixture results, not a full
  accelerator route or numerical timing pass.
  [Compiled model-restoration backend](build/fedora-openxc7/placed-replay-model-restored-backend-20261013T042500Z/manifest.json).
  [Model-enabled replay fixture](build/fedora-openxc7/placed-replay-model-restored-register-check-20261013T044500Z/manifest.json).
  The full-route controller now requires this model-enabled receipt and
  the original full **18** timing-domain pairs (**16** known / **2**
  unrelated) with identical budgets, plus reimport of all **1,103** mailbox
  datapath limits. It also requires 14 GiB available RAM when free swap
  is below 2 GiB. Existing four comparison jobs remain unchanged.
  A new model-restored replay trial has started with native PID **398248**
  / start **21736439**; controller session **9309**.
  Current verified stage is `full-native-routing`. The complete **18**
  timing-domain pairs and budgets match (**16** known / **2** unrelated),
  and all **1,103** mailbox limits were reimported. Both live replay guards
  pass; route convergence and image generation remain pending.
  [Current model-restored trial](build/fedora-openxc7/full-congestion-model-restored-route-20261013T045000Z/manifest.json).
  [Exact loaded bindings](build/fedora-openxc7/full-congestion-placed-route-20261013T041500Z/loaded-placement-check.json).
  [Original failed review](build/fedora-openxc7/full-congestion-placement-reviewed-pending/manifest.json).
  [Revised full review](build/fedora-openxc7/full-congestion-placement-equivalence-reviewed-20261013T032600Z/manifest.json).
  Routing, numerical timing, native image assembly and hardware execution
  remain pending. The original route jobs continue unchanged.

- Full native FF correspondence now passes independently: **179,299** FF
  identities, primitives and clock polarities match the routed reference,
  and all **896,495** original port mappings match after streaming the full
  packed export. Actual installed primitive-library defaults justify the
  reference DEFAULT clock-inversion values. No native backend was changed.
  Native placement/input-mux mapping and numerical coverage remain pending;
  **174,489** reference FFs have no individually selected arc measurement.
  [Full mapping audit](build/fedora-openxc7/full-ff-native-reference-map-20261012T232714Z/manifest.json).
  Existing `preplaced` replay reserves every touched tile for listed cells,
  so an FF-only location map cannot stand in for complete site-compatible
  placement transfer. The current full route remains active and unchanged.
  [Current complete goal evidence](build/fedora-openxc7/goal-full-native-ff-correspondence-20261012T233618Z/manifest.json).

<!-- OPEN_TPU_LIVE_OBSERVATION_START -->
- Latest authoritative observation: **2026-10-14T09:11:11 UTC / 17:11:11 HKT**.
  The CH1 warm-test controller and generated-core controller are terminal exit 0.
  Recovery Vivado controller **845827** and exact ECC comparison child **835165**
  are live. The native OpenXC7 router remains **400903**, start **21826315**;
  its 17:06 HKT sample has **204,010** remaining routed flags in iteration 1.
  Only a pre-build dependency waiter was stopped to overlap synthesis and ECC;
  no placement/router or hardware run was restarted. No flash was written.
  [Observation receipt](build/fedora-vivado/ch1-recovery-handoff-20261014T091111Z/manifest.json).
<!-- OPEN_TPU_LIVE_OBSERVATION_END -->

- October 13 07:17 HKT: the complete same-input FF query has native exit
  **0**, inventories **179,299** registers in **1,988** logical groups and
  finishes all **9,620** max/min path queries.
  FF sample pairs: **4,810 / 4,810**.
  [Completed query](build/fedora-openxc7/full-mapped-ff-bounded-20261012T192600Z/manifest.json).
- Independent review matches all **9,550** finite path contributions to
  the raw vendor timing arcs with **zero mismatches**. It retains **58**
  absent timed paths and **12** unconstrained external-boundary queries
  (JTAG TDI and five sensor/I2C inputs) as unvalidated. These are not zero
  delays or numerical passes. The first comparison failed on those missing
  requirements; its receipts remain preserved. The updated classifier
  rejects seven corrupt-source/endpoint/clock/receipt cases and reproduces
  both old MIG comparison outputs byte for byte.
  [Completed comparison](build/fedora-openxc7/full-mapped-ff-reviewed-boundaries-20261012T231300Z/manifest.json).
- Physical regrouping finishes with **2,891** observed contexts, **1,277**
  repeated groups covering **3,196** samples and **zero** conflicting
  signatures among the observed repeated groups. This covers all selected
  samples; it does not sample every FF individually or establish universal
  context coverage. Native FF model import, native physical mapping and
  external-boundary timing qualification remain pending.
  [Complete physical regrouping](build/fedora-openxc7/full-mapped-ff-physical-context-20261012T231500Z/manifest.json).
  [Complete reference evidence](build/fedora-openxc7/goal-full-ff-reference-complete-20261012T231726Z/manifest.json).
- The full same-input Vivado bitstream is complete offline:
  [full-mapped-reference.bit](build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/full-mapped-reference.bit),
  **18,735,238 bytes**, SHA256
  `a2a242dc7edfd80de81e4c9c9224a242b0a6f72d04c999a9875b5d6b82834b7d`.
  Full scope remains MCOLS4 / ACT_ROWS4 / LANES8 / VPU_CL2 / MXU_IMPL2,
  core **100 MHz**, dual DDR3 **800 MT/s**. The original working DDR1066
  MIG image remains preserved. The same-input reference has all **397,867**
  routable nets routed, zero errors, WNS **0.000 ns**, WHS **+0.034 ns**
  and WPWS **+0.264 ns**, with zero failing endpoints. Native bit generation,
  DRC, 243 ports / 905 properties, USER2 and packet checks pass. Independent
  packet CRC checking is not implemented; hardware is still pending.
  [Image receipt](build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/manifest.json).
- The corrected full OpenXC7 route remains live in session **61317**,
  PID **261549** / start **15880662**. The latest complete logged iteration
  is 1: **9,587,162** used wires, **484,951** overused, aggregate overuse
  **530,491**, `archfail=NA`. No terminal route/timing/FASM/image exists.
  A read-only snapshot at 08:23 HKT found both router workers on different
  data nets from the 07:57 snapshot, confirming that those individual
  searches finished or were left. The run remains in iteration 2; net
  changes do not establish congestion convergence or numerical timing.
  Debugger exit was 0, it detached with no tracer, and CPU execution resumed.
  [Actual router search comparison](build/fedora-openxc7/full-route-search-progress-20261013T002306Z/comparison.json).
  Original comparison jobs 157975/9968368, 148107/9503156 and 157970/9967810
  remain live and unchanged. Continue bounded checks with
  `python3 build/fedora-openxc7/goal_route_wait.py --wait-seconds 55`.
  The earlier FF query and follow-up controllers have finished; do not
  restart them or treat their missing PIDs as a stalled route.
- USB enumeration still contains no Xilinx JTAG adapter. Remaining original
  MIG hardware vops/stream/selftest and eight-token LFM2 exact ISA comparison
  await cable detection. No hardware was accessed in this continuation.
  All 31 frozen source hashes and the reference checkpoint match.

<!-- OPEN_TPU_CURRENT_HANDOFF_END -->


Active objective: finish pending physical OpenTPU tests with the qualified
Vivado image, then synthesize and route with OpenXC7 using it as the reference.

The Vivado MIG image is preserved under
`build/fedora-vivado/mig-jtag-controller-20261010T235833Z/`.
Bitstream SHA256:
`0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f`.
Earlier actual SRAM programming, full 4 GiB patterns/ECC and two ISA-matched
compute kernels passed. USB disconnected during vector checks; stream and
physical LFM2 token comparison remain pending.

The earlier hardware watcher is terminal: exit 2,
`WAIT_USB_EXPIRED_NO_HARDWARE_ACCESSED`, Oct 12 00:42:05 HKT.
No new programming or physical computation occurred in that attempt.

A replacement bounded watcher started at 01:18:09 HKT with the corrected XVC
manifest and a 1800-second USB wait. PID 139871; tool session 57211; directory
`build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-usb-fixed-watch-20261011T171809Z/`.
It reached its actual terminal exit 2 at 01:48:09 HKT:
`WAIT_USB_EXPIRED_NO_HARDWARE_ACCESSED`. The process is absent, tool session
57211 is terminal, and no programmer or selftest started. Its terminal receipt
is `process-exit.json` in that directory. Do not repeat the unchanged watch
until an adapter appears or the USB path changes. No USB rule was installed
automatically.

The latest USB event disconnected before JTAG software ran and then failed
descriptor/setup requests with `-71`. Software/firmware compatibility is
plausible; a board/12 V power fault is not established. A descriptor-aware
DLC10 driver was built using eight workers and passed the actual-driver USB
selection test and existing XPCU protocol test. It remains a separate candidate:
`build/fedora-openxc7/xpcu-xvc-20261011T165026Z/manifest.json`.
SHA256: `b87703a39c2fa068aacd15d22f15d6d83a868f47c84ba1523d713022b2d57def`.
The original selected XVC and donor files are preserved. Physical stability is
not tested. The scoped no-autosuspend rule passed udev verification but was not
installed because unattended sudo requires a password.

The complete Vivado DCP reference export and Yosys netlist import passed.
The OpenXC7 MIG pack trial failed on a tristate-only OSERDES. Actual chipdb audits
and six actual placement probes also demonstrate absent PHASER/PHY_CONTROL/
IN_FIFO/OUT_FIFO BEL support. Independent frozen-RTL frontend elaboration ran,
but its first strict undriven-signal check failed. A subsequent full flatten/
optimization audit now passes the strict check with the complete top and MIG
primitives retained; no explicit unknown-signal tie-offs were added. An empty-top
intermediate blackbox result was rejected and preserved. No independent mapped
MIG output or full OpenXC7 route/bitstream was produced by these trials.

The user approved continuing the full LiteDRAM OpenXC7 implementation against
the working Vivado MIG functional reference. A new controller is active in
`build/fedora-openxc7/litedram-vivado-reference-20261011T170600Z/` (actual start
01:04:45 HKT). Controller PID 138687; route wrapper PID 138736; exact nextpnr
PID 138789. Latest merged backend SHA256:
`975e6dbd3cb87e8e4cac71fc2e4b68b9afa0b1695c0a5b1ebd85e551485577d2`.
Its five correction gates, 1563 pinned inputs, unchanged full independent
synthesis, shared reference sources and Vivado offline audit were revalidated.
Eight threads are requested and all eight CPUs are allowed. The four initial
placement iterations completed; main placement is active. No full route result
or bitstream exists yet. Preserve the live job; do not restart it from a quiet
log. The controller proceeds to existing guarded assembly/image checks only
after successful full routing. No hardware client is running.

Two read-only placer counter observations at 01:14:17 and 01:16:39 HKT confirm
2851 additional legalizer calls and 2851 fewer queued entries on the same exact
nextpnr process. Both observers detached normally and the process resumed;
no inputs changed and no job restarted. These counters include repeated/rip-up
placements and are not a completion percentage or ETA. Counter receipts and
the active controller manifest are in the route directory. Tool session 31485
owns the full implementation controller; poll that same session and verify
PID/start identity before any replacement. The current serial stage explains
why eight requested threads do not mean eight CPUs busy throughout placement.

A third read-only observation at 01:29:27 HKT confirmed the same process and
captured 1,170,723 legalizer calls with 201,084 queued entries. Since 01:16:39,
the queue decreased by another 52,408 entries while calls increased by
1,123,925, reflecting repeated placements. The observer exited 0 and detached;
the process resumed with no tracer. Placement and routing remain unfinished.
At 01:28:44, the existing USB watcher still reported no cable and no hardware
access. Its original 1800-second deadline remains unchanged.

Latest counter check: 02:05:02 HKT, same nextpnr PID/start identity, observer
exit 0 and normal detach. The queue is 172,098 entries and calls are 1,940,267;
the queue decreased by 2,174 entries since 02:00:45. A bounded read-only count
of all 300,290 cells in the current legalizer vector found 128,191 bound and
172,099 unbound cells, with no unexpected BEL values. Unbound cells include
106,790 LUT roots and 65,291 flip-flop roots, plus 17 DSP roots and one clock
buffer. Macro children are outside this vector; this is a current-pass snapshot,
not an overall completion percentage. The receipt is
`placer-counter-20261011T180502Z.json` in the active build directory. Comparing
both complete snapshots confirms 2,174 additional bound flip-flops. Its memory
read took under one second, the observer detached and the same job resumed.
No full route or new hardware result exists. A request to
test the prepared driver through a different physical USB port is pending;
no new USB connection events were logged during this hardware watch. The route
remained live at 01:48:48 HKT; preserve PID 138789 and session 31485.

Exact receipts, commands and limits:

- [Physical Vivado results](docs/fedora_vivado_jtag_results.md).
- [USB diagnosis and controlled fixes](docs/dlc10_usb_stability.md).
- [OpenXC7 reference trials and remaining backend work](docs/openxc7_vivado_reference.md).

Resume USB stability testing first, one cable owner at a time. The prepared
physical controller accepts `--xvc-manifest` to test the corrected candidate
without replacing the original pointer. Preserve full normal selftest/model
comparison requirements and choose fresh receipt directories. Full model
upload over the measured JTAG link takes several hours. SRAM programming is
volatile; flash has not been written.

## Eight-core settings, corrected static retry and preserved pull, 2026-10-12 02:44 HKT

The full heap placement remains live (native PID 138789, start ticks 8930713,
controller tool session 31485). The latest read-only snapshot is
`build/fedora-openxc7/litedram-vivado-reference-20261011T170600Z/placer-counter-20261011T184144Z.json`:
133,592 of the current 300,290 solve cells were bound and 166,698 unbound.
This is 4,886 more bound FF roots than the 02:09:40 snapshot, with 2,447,929
legalizer calls including repeated placements. It is not a completion percentage
or ETA. The observer detached and TracerPid returned to 0. Its wrapper exited 1
because a case-sensitive check expected “Detached” rather than the actual
“detached” message; the raw counters remain valid and the native job resumed.
The original job requests eight threads but its current legalizer is serial.

An independent full static attempt failed at 02:16:41 HKT with native exit -6
on a finite-value assertion. Its prepared inputs were byte-identical to the
heap attempt. Actual core evidence showed finite coordinates whose float
exponentials overflowed. A new isolated complete backend evaluates those two
exponentials in double precision; assertions and full logic remain required.
The only changed source is `common/place/placer_static.cc`. Existing pinned
backend/source files and the live heap job were preserved.

Corrected backend:
`build/fedora-openxc7/static-double-exp-backend-20261011T183100Z/manifest.json`.
Binary SHA256:
`2bfd62e16b981999c12b0738321456bbaf865be0a0caffcc0f4dfe9265962efe`.
Compile and link exited 0. The five actual lower/upper carry, DSP cascade,
FF edge and extracted MUX checks were rerun concurrently against this exact
binary. All native routes and all five concurrent strict-frame assemblies
exited 0. Exact-binary selection and the complete synthesis witness passed.
The qualification receipt and selected backend are under
`build/fedora-openxc7/static-precision-qualification-20261011T183800Z/`.
The initial MUX invocation had an incorrectly copied cell name and failed;
`mux_probe_retry` uses the exact prior manifest's name and passed. The failed
receipt is retained and is not selected.

The new complete static retry started at 02:40:10 HKT:
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/`.
Controller tool session 28636; native PID 148107, start ticks 9503156.
Actual command includes `--placer static --threads 8`. It has nine native
threads (main plus eight workers), and passed the old overflow point, reaching
iteration 120 at 02:43:25 HKT. A bounded sample at 02:41:49 showed CPU time on
all eight workers but only 2.81 equivalent busy cores across the host because
serial stages dominate. This is actual measured usage, not a claim of 800%
utilization. Both full jobs remain incomplete; no new routed design, FASM,
accepted image or numerical timing/physical result exists. The new controller
will perform existing guarded assembly and independent image checks only after
successful full routing. All backend qualification probes are prerequisites,
not substitutes for the full design.

The user's pull fetched origin/main at 700639b but aborted the checkout merge.
HEAD remains 5b1e646. Upstream changes include board RTL moves and shell changes;
merging now would invalidate running source checks. A verified local backup
contains the binary tracked diff and all 82 nonignored untracked files:
`build/fedora-openxc7/local-work-before-upstream-20261011T184100Z/`.
No stash, checkout change, commit, reset or push was performed. Generated build
artifacts and frozen reference/source bundles remain in place.

At 02:38:16 HKT, lsusb still showed no Xilinx adapter. The previous corrected
USB-driver watcher is terminal, and no hardware client is running. Full normal
Vivado selftest and physical LFM2 inference still await USB reconnection; saved
compiler/ISA expected output is not FPGA inference proof. Timing and physical
operation of any future LiteDRAM OpenXC7 image require separate validation.
Detailed placer evidence: [static trial and correction](docs/openxc7_static_placer.md).

At 03:00:08 HKT, the corrected static run remains live in full logic
legalization. It completed RAM/DSP legalization after iteration 473, resumed
logic spreading, and entered logic legalization after iteration 656. The queue
started with 300,727 entries; the latest read-only observation found 127,223
queued entries. Of 350,153 unique concrete representatives in this placer's
vector, 222,955 were bound and 127,198 unbound. The count has zero unexpected
BEL values and includes 168,352 bound FF and 51,462 bound LUT representatives.
These representatives exclude some macro children; this is not a count of the
whole design or an overall completion percentage, and the queue can grow after
rip-ups. GDB exited 0, detached and TracerPid returned to 0; no native calls or
source changes occurred. The detailed snapshot is
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/static-legalizer-20261011T190005Z.json`.
Use the actual snapshot named by that directory's `resume-state.json` if the
receipt timestamp differs. Earlier observer attempts failed to read optimized
locals or an ambiguous anonymous DWARF type; both detached normally, the
process continued and their failure receipts are preserved.

The corrected static netlist, XDC, VREF plan and board constraint audit are
byte-identical to the original full heap run. The hard-cell timing audit differs
only in its `constids` source path: both referenced files have identical bytes
and every other audit field matches. Exact comparisons are in the new run's
`equivalent-route-inputs.json`. The initial comparison used an incorrect audit
filename and was preserved separately; byte equality of all five files is not
claimed. The complete synthesis, accelerator and both DDR channels remain
selected. At 02:53:35, lsusb still detected no Xilinx USB adapter. Neither full
implementation nor the pending physical normal selftest/model run is complete.

The 03:05:23 HKT snapshot of the same static legalizer found 309,483 bound
and 40,670 unbound representatives, versus 222,955/127,198 at 03:00:08.
Both snapshots cover the same complete vector of 350,153 unique concrete
representatives with no unexpected BEL values. This confirms 86,528 additional
bound representatives. All 170,144 FF representatives in this vector are bound;
40,254 LUT and 416 SELMUX representatives remain unbound. The queue is 40,693
entries. Global macro children remain outside this counting scope. Observer
exit 0, normal detach and TracerPid 0 were verified. Receipt:
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/static-legalizer-20261011T190521Z.json`.
The guarded read-only wrapper `run-static-observer.py` in that directory can
repeat the same observation after verifying native PID/executable/start identity.
Full route and accepted image remain incomplete; preserve both live jobs.

At 03:10:42 HKT, the same static legalizer has 311,378 bound and 38,775
unbound concrete representatives, with 38,798 queued entries. This adds 1,895
bound representatives since 03:05:23; late legalization has slowed markedly.
The remaining representatives are 38,374 LUT and 401 SELMUX cells. All FF,
carry, RAM and DSP representatives in this vector remain bound. The count is
not an overall completion percentage. The unchanged observer exited 0,
detached and verified TracerPid 0. The receipt is
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/static-legalizer-20261011T191039Z.json`.
Both full native jobs and their original tool sessions remain live. No native
route exit, routed graph, FASM or accepted OpenXC7 bitstream has completed.
No new USB adapter was observed. This turn made verified full-stage and
binding progress while waiting on the same live jobs; the full goal is active.


At 03:47 HKT on 2026-10-12, both complete native placements remain live
with their exact original process start identities. Both native commands request
`--threads 8` and can execute on CPUs 0-7. A bounded 10-second CPU measurement
shows heap used 0.995 busy cores and static used 0.790; all eight static workers
were idle during this serial strict-legalization interval. Thread configuration
is already all cores; eight requested workers do not make this stage parallel.
CPU, memory and I/O pressure were low in this interval. The receipt is
`build/fedora-openxc7/cpu-thread-check-20261011T194700Z.json`.

The same static placer's 03:47:17 HKT read-only snapshot has 313,637 bound
and 36,516 unbound concrete representatives, up 2,259 bound since 03:10:42.
Remaining representatives are 36,130 LUT and 386 SELMUX. Observer exited 0,
detached and verified TracerPid=0. This is measured late placement progress,
not full implementation completion or an overall completion percentage.

The saved full standard ABC mapping was freshly qualified and attempted as a
complete static route, but exited 125 before placement with 22 combinational
loops; its controller exited 1. That failure is preserved under
`build/fedora-openxc7/litedram-default-static-vivado-reference-20261011T192700Z`.
The first proposed custom area script incorrectly used commas as command
separators, executing only strash and producing 907,726 raw LUTs. Its native
and boundary/clock receipts are preserved but the candidate is not selected.
A new immutable helper `tools/fedora_openxc7_cut_mapping.py` uses pinned literal
ABC script files and verifies all three actual commands in the native log.
Two full corrected remaps now run concurrently from the same complete pre-LUT
checkpoint, retaining all source files and full compute/memory dimensions:
`build/fedora-openxc7/jtag-ddr800-area-cut-20261011T194900Z` (session 45212,
Yosys PID 155618/start ticks 9911133) and
`build/fedora-openxc7/jtag-ddr800-delay-cut-20261011T194900Z` (session 51443,
Yosys PID 155623/start ticks 9911259). These jobs use independent output
folders and preserve both existing placements. Full route, strict assembly
and independent bitstream verification still must pass before accepting an
OpenXC7 image. No timing loops are bypassed. Full Vivado normal selftest and
physical model inference still await the missing Xilinx USB adapter. HEAD
remains 5b1e646; the fetched upstream changes are not merged into pinned builds.


Both corrected full cut mappings completed native synthesis with exit 0.
The log observer expected individually echoed commands inside ABC `source`,
so both wrappers exited 1. Their failed receipts remain unchanged. Separate
adopted synthesis directories verify the pinned three-command ABC file,
actual source invocation and completion marker, native exit, every input hash,
full hardware counts and all 1,748 BSCAN clock sinks. No synthesis was rerun;
the immutable JSON is hard-linked to a separate accepted manifest.
Area candidate: 184,539 raw LUTs, 3,092 F7 and zero F8 cells; adopted directory
`build/fedora-openxc7/jtag-ddr800-area-cut-adopted-20261011T195400Z`.
Delay-recovery candidate: 181,546 raw LUTs, 28,836 F7 and 10,431 F8 cells;
adopted directory `build/fedora-openxc7/jtag-ddr800-delay-cut-adopted-20261011T195400Z`.
These results preserve full dimensions and both DDR channels but do not prove
fit, timing, full functional equivalence or a legal whole-chip timing graph.
The next fresh exact-binary witness is a real F7 subtree with all 128 unique
seven-input vectors for the full no-F8 candidate. Existing F8 witness policy is
retained. The updated image checker verifies zero F8 in the selected full JSON
and its actual F7 root/BEL before accepting that alternative witness. The checker
is absent from both running controllers' pinned inputs; all new selections pin
its new source. Original probe helpers and live route/backend helpers remain
unchanged. Both full original placements still run; FPGA USB is still absent.


At 2026-10-12 04:00:51 HKT, both new full cut-mapped static implementations are live.
The area trial has native PID 157975/start ticks 9968368, tool session 23263;
the delay trial has native PID 157970/start ticks 9967810, session 91723.
Both use the exact corrected backend 2bfd62e1..., `--placer static --threads 8`,
CPUs 0-7 and nine native threads. Both working Vivado reference audits exited 0,
and both passed the normal whole-design timing-graph checks and entered static
analytical placement. These are complete accelerator/dual-DDR implementations,
with existing full heap and fast-static placements still preserved and live.

The area trial's actual pre-spacer COMB estimate is 83.29%, versus 93.76%
in the original fast mapping; the delay trial is 93.53%. The area trial packs
270,142 SLICE_LUTX cells versus 300,747 in the original. This is a measurable
reduction in placement density for the unchanged full source/dimensions, but
neither count nor the estimate proves placement, routing, numerical timing or
physical operation. No timing loops were overridden. Both full routes and
accepted images remain incomplete.

Fresh actual MUX witnesses passed: the no-F8 source's F7 gate covered all 128
unique seven-input patterns and placed an actual SLICE_X0Y236/F7AMUX; the delay
source's F8 gate covered all 256 eight-input patterns. Both strict-frame
assemblies exited 0. The four unchanged exact-backend carry/upper-carry/DSP/FF
receipts are reused honestly; the prior F8 receipt remains preserved. Normal
selection/synthesis witness checks passed and each new selection pins 19
mapping/qualification evidence files, including the changed checker. Previously
qualified F8 selections still pass the unchanged F8 policy. New qualification
and full pipeline folders use prefixes `area-cut-` / `delay-cut-` and suffix
`20261011T195541Z`. Exact hashes, native arguments, process start identities and
sessions are in `build/fedora-openxc7/full-cut-trials-resume-20261011T195541Z.json`.
Preserve all four running implementations. Original failed mapping wrappers,
the 22-loop standard-mapping attempt and the unusable script experiment remain
retained. USB is still absent, and native full normal selftest plus actual model
inference remain pending. The goal is active, not complete or blocked.


The 04:00:18 HKT 15-second CPU sample confirms activity on all eight cores:
per-core busy percentages were 89.9, 72.9, 66.0, 82.6, 80.7, 63.2, 68.0
and 94.5 (host mean 77.2%). Both new static jobs accumulated CPU time on
all nine native threads; all eight workers participated. Original heap/static
jobs each used about one busy core in their current serial legalization phase.
This measures current usage, not a promise of constant 800% CPU consumption.
Memory pressure was zero in this sample and approximately 4.7 GiB remained
available. Actual receipt:
`build/fedora-openxc7/cpu-parallel-static-20261011T200018Z.json`.
All four controllers' complete pinned-input inventories were freshly checked
unchanged after the scoped checker addition; exact checks are saved in
`build/fedora-openxc7/full-cut-input-verification-20261011T200018Z.json`.
The new area/delay trials reached iterations 99/91 respectively. Neither full
route, accepted OpenXC7 image nor the pending physical model run is complete.
All four full implementations continue with eight threads requested.


At 04:04-04:06 HKT on 2026-10-12, all four exact native processes remain
live, and the new area/delay analytical placers have advanced to iterations
350/330. No native route exit or routed/FASM/image artifact exists yet.
The original heap's bounded read-only snapshot at 04:05:49 finds 149,617 bound
and 150,673 unbound entries in its same 300,290-cell solve vector, versus
133,592/166,698 at 02:41:44. The additional 16,025 bindings are FF entries;
LUT counts remain 44,489 bound/106,790 unbound. Its current search has 3,536,293
aggregate attempts and is still on FF placement. This confirms actual progress
in the original quiet-log job. The new reusable `run-heap-observer.py` checks
its exact PID/start/executable, records actual GDB exit 0 and handles lowercase
'detached'; the existing read-only GDB source remains unchanged.

The original fast-static snapshot at 04:04:33 remains 313,637 bound/36,516
unbound concrete representatives, unchanged since 03:47:17. It is consuming
CPU in a legalizer search, not terminal; this records no new binding progress
for that interval. Both observers exited 0, detached, and left TracerPid=0.
No native functions were called and no placement state was written. The vector
scopes are different and neither is an overall design completion percentage.
The snapshots are respectively
`build/fedora-openxc7/litedram-vivado-reference-20261011T170600Z/placer-counter-20261011T200546Z.json` and
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/static-legalizer-20261011T200429Z.json`.

Live lsusb and kernel-log refresh still show no Xilinx adapter or subsequent
USB recovery since the 00:20:47 disconnect/00:20:50 enumeration failure.
No hardware client was started. Full native normal selftest/model inference
still requires the adapter. The previous turn made concrete full-mapping and
qualification progress; this continuation is a verified wait on live full jobs.
The goal remains active while meaningful software work continues.


At 04:13 HKT, the full area-mapped static run reached iteration 600,
completed RAM/DSP legalization (1,962 queued entries, post-legalization HPWL
4,653,124), and entered strict logic legalization with 306,321 queued entries.
The full delay-mapped run also completed its RAM/DSP legalization (post HPWL
4,356,256) and reached iteration 600 while continuing logic spreading.
Both exact native processes and original two implementations remain live;
normal full timing-graph checks were retained and no input/helper/backend was
changed during placement. No route exit, routed JSON, FASM or image exists yet.
The stage receipt is `build/fedora-openxc7/full-cut-stage-progress-20261011T2013Z.json`.
A two-minute live-process monitor also recorded repeated CPU/log progress for
all four implementations and no USB adapter. Receipt:
`build/fedora-openxc7/live-full-jobs-20261011T200735Z.json`.

The original frozen route/assembly pipeline was reviewed for the new mappings:
it verifies the complete constrained JSON differs only by the two recorded
MMCM LOCs, exact full source/core/backend identity, native route exit 0,
required route artifacts, strict FASM/frame assembly, every encoded frame and
USER2 image structure. It does not accept incomplete live-route output. The
new no-F8/F7 selection preserves these normal full-image checks. Numerical
timing, CRC and physical behavior remain separate limits of its status.
The hardware continuation still runs the complete normal selftest including
vops/stream and physical eight-token LFM2/ISA comparison; no stages are skipped
to produce a pass. That continuation cannot start while USB is absent.


At 04:17 HKT, the full area-mapped implementation completed strict logic
legalization of the 306,321-entry queue and entered simulated annealing
placement refinement. The native log reports post-legalization HPWL 9,526,925
(delta 1,170,542). This is the actual normal full-stage completion, with all
source/dimensions, dual DDR and backend legality assertions retained. It is
not route completion, timing qualification or a ready bitstream. The exact
process is still PID 157975/start ticks 9968368, tool session 23263. Receipt:
`build/fedora-openxc7/area-cut-static-vivado-reference-20261011T195541Z/logic-legalization-pass.json`.
The preceding 04:13:51 read-only snapshot covered all 356,094 unique concrete
representatives in this candidate's vector, with 173,013 bound/183,081 unbound,
all carry/RAM/DSP representatives bound and zero unexpected BEL values; it was
an intermediate snapshot, not the final legalization result. Its observer
exited 0, detached and verified TracerPid=0. The later native log establishes
that this phase completed. No route exit, routed JSON, FASM or accepted image
exists yet. The other complete implementations remain live; JTAG USB is still
absent. This continuation now records concrete full-stage progress rather than
only a wait. Preserve the running full controller and let its normal guarded
routing/assembly/image checks complete.


At 04:22:49 HKT, a bounded read-only observation of the exact area process
finds it in SAPlacer::compute_cost_changes, with current wirelength estimate
14,764,740 versus the initial refinement log's 15,734,909. Its current timing
cost is 1,108.04 versus the initially rounded 1,449. These are internal placer
costs, not routed timing or MHz. Current counters are n_move=87,443 and
n_accept=34,940; the source resets them each outer iteration, so they are not
whole-run totals or completion percentages. The actual temperature is
8.145e-8; `%f` logs round that small nonzero value to 0.000000. GDB exited 0,
detached and verified TracerPid=0, with no native function calls or state writes.
Some optimized locals were unavailable and their errors are retained. Receipt:
`build/fedora-openxc7/area-cut-static-vivado-reference-20261011T195541Z/refinement-observe-20261011T202248Z.json`.

The original full logic-legalization pass's exact log prefix was copied to
`logic-legalization-frozen.log` and its SHA256 verified equal to the original
observation's recorded hash. A new immutable receipt
`logic-legalization-frozen-evidence.json` references that frozen prefix;
the original phase observation and live log are preserved. Use the frozen
receipt referenced by the full-job resume state for later evidence checks.

The compiled static placer calls serial placer1_refine after its parallel
analytical work; it does not call the separate parallel_refine implementation.
All eight threads remain requested, but this phase cannot sustain eight busy
cores through that flag. The live job and all pinned source/helpers were
preserved. No routed graph, accepted OpenXC7 image or numerical timing pass
exists yet; full Vivado normal selftest and actual LFM2 still await USB.


Final live check at 04:25:57 HKT: all four native PID/start identities still
match and no native route exit exists. Area refinement advanced through logged
iterations 5 and 10; at iteration 10 its wirelength estimate is 14,590,901 and
its rounded timing cost is 1,037. These are internal placement metrics. The
area implementation still has no completed routed graph/FASM/accepted image.
No Xilinx USB adapter is enumerated. The original full controllers and tool
sessions 31485, 28636, 23263 and 91723 remain live and are preserved. Updated
resume state is `build/fedora-openxc7/full-cut-trials-resume-20261011T195541Z.json`.
Tracked whitespace checks pass. The goal remains active: full routing/image
verification and remaining physical selftest/model comparisons are unfinished.


At 04:42:34 HKT, the full area-mapped implementation is live in refinement
at logged iteration 25, wirelength estimate 14,061,735 and rounded timing cost
892. Its native PID/start identity still matches 157975/9968368; no route exit,
routed graph, FASM or accepted image exists. The delay-mapped trial remains
live in strict logic legalization. Original two native implementations and
their owning sessions remain live. A six-minute read-only monitor confirms
continued CPU/log advancement in the exact area process and no USB adapter;
receipt `build/fedora-openxc7/area-refinement-live-20261011T203045Z.json`.

Actual process/parent PSS measurement at 04:37:51 finds the four native jobs
using roughly 6.2, 6.2, 7.7 and 6.2 GiB, plus their wrappers; approximately
3.9 GiB is available and current memory pressure is zero. The original heap's
sleeping wrapper has about 1.1 GiB swapped; the four native jobs have zero swap.
No further full trial is launched into this measured footprint. Receipt:
`build/fedora-openxc7/full-jobs-memory-20261011T203751Z.json`.
The pending physical receipt was freshly read: its full normal selftest is
actual FAIL/exit 1 and model_checks is empty; full physical completion is still
unproven. The separate full-memory receipt remains PASS and SRAM programming
receipt remains PASS_SRAM_PROGRAMMED_INIT_DONE, both with flash_written=false.

A current-state block now appears first in this repository's progress.md,
with exact live-job/proof links; all historical observations are preserved below.
The preceding goal turn made full-stage progress; this continuation is a verified
wait on live, advancing full jobs. The goal remains active, not complete or
blocked while software work can progress. No source-pinned build was restarted,
no hardware client ran, and no checkout, commit, stash, merge or push occurred.


Latest live check at 04:48:20 HKT confirms all four exact native identities
and live RUNNING controllers. Area refinement reached logged iteration 35,
wirelength estimate 13,928,108 and rounded timing cost 837. No native route
exit or accepted OpenXC7 image exists, and no Xilinx USB device is present.
Live receipt `build/fedora-openxc7/goal-continuation-live-20261011T204820Z.json`.
All 31 full-design source files were freshly hash-checked unchanged across
all four route inventories; HEAD/origin remain 5b1e646/700639b. The source
verification is `build/fedora-openxc7/full-source-verification-20261011T2049Z.json`.
The same software jobs continue; no narrower source/profile or replacement
process was used. This continuation is a verified wait, not a claim that the
requested full route/image or physical normal selftest/model run is complete.

<!-- CH1_LFM2_HOST_BUNDLE_20261014 -->

The user requested LFM2 execution and confirmed the card is still separately
powered with JTAG only. The new CH1-only image uses XDMA PCIe for host access;
there is no XDMA device on this Fedora machine. No physical LFM2 run has started.
The current design retains full compute dimensions and uses healthy physical
CH1 only. JTAG can transfer compute data with a mailbox image, but the older
mailbox image still uses both physical DDR channels.

A [matched full LFM2 host bundle](build/fedora-vivado/ch1-lfm2-host-20261014T093000Z.tar)
now contains the complete LFM2.5-230M checkpoint, frozen host/compiler source,
CH1 calibration core and pinned Python package versions. It contains no bitstream.
The seven capacity/image-marker tests passed, all bundle checksums passed, and
the copied runner's CLI imports succeeded. The runner records the checkpoint
hashes and Python runtime before accessing the card. The compact matmul checker
is copied into a standalone helper so this bundle does not import the older
JTAG hardware drivers.

The [queued image audit](build/fedora-vivado/ch1-image-qualification-20261014T093346Z/manifest.json)
waits for this exact live Vivado build and full four-port ECC comparison. It will
check packet/CRC integrity, routed checkpoint pins and GTX sites, route/timing
and DRC, and export fresh CDC/bus-skew evidence for review. It never accesses or
programs hardware. The previous native PCIe image was used only to validate the
parsers; its packet and CRC checks are not evidence for the new recovery image.

The completed CH1 warm-test helper left an idle owned hw_server process. Its
terminal controller, exact process/cgroup and lack of clients were verified
before stopping only that owned server. The same DLC10 USB device remained
connected afterward. This cleanup is not a diagnosis of the earlier USB resets.
[Cleanup receipt](build/fedora-vivado/ch1-warm-cable-owner-cleanup-20261014T093432Z/manifest.json).

[Current LFM2 handoff pointer](build/fedora-vivado/ch1-lfm2-run-handoff-current.json).

<!-- CH1_NATIVE_SRAM_LOADER_20261014 -->

A [native CH1 PCIe SRAM loader](tools/fedora_program_ch1_sram.py) is prepared.
Eight actual Tcl guard tests passed with hardware calls mocked: ambiguous chains
and wrong part/IDCODE cannot program; failed INIT/DONE or post-load IDCODE cannot
produce a completion receipt. The PCIe image does not contain a USER2 mailbox,
so this loader checks INIT/DONE and the raw FPGA identity without requiring a
mailbox. It accepts only a completed image audit and matching CDC/bus-skew review.
Neither prerequisite is complete yet, so it has not accessed hardware.
No flash commands are present. Owned native-tool process groups are closed to
avoid leaving an idle hw_server after completion.

The [loader handoff pointer](build/fedora-vivado/ch1-loader-handoff-current.json)
records fresh live-build process identities and increasing CPU ticks, the exact
ECC test's live cycle/error count, helper/test hashes and the test scope. Physical
matmul, LFM2 and permanent PCIe boot remain unverified.
