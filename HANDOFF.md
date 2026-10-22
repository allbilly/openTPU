# OpenTPU session handoff — 22 October 2026 (HKT)

## 0. Final disposition — abandoned by user, 2026-10-22 13:36 HKT

The user ended the c01848 runtime-clock effort: "we spent 3 days and 12revision
on this task already, give it up". **Do not resume, schedule another revision,
start P&R, continue qualification/packaging or program hardware for this effort
without a new explicit instruction.** This replaces the earlier pause/resume plan.

| Item | What changed | Final state |
|---|---|---|
| Runtime-clock effort | User ended the c01848 series | Abandoned; removed from the active plan |
| c0184812 corrected source | Local hazard/cache/stream and host/reset timing corrections; full 4 GiB, both interfaces and all four modes retained | Synthesis, 12 modeled traffic cases, native control/reset and four static clock reviews passed; P&R never admitted; no bitstream |
| Workers | Exact service and cgroup audit | All 106 related retained services have MainPID 0 and no cgroup processes; no live work to stop; no jobs restarted |
| Evidence | Frozen sources, checkpoints, logs, receipts and component proofs | Preserved in place; no cleanup/deletion |
| Working fixed-clock images | c0182863 and c0182800 historical baseline artifacts | Preserved; physical card state/ownership not rechecked; no programming performed |

Cancellation receipt: `build/handoffs/runtime-clock-abandoned-by-user-20261022.json`.
Canonical final state: `build/handoffs/runtime-structural-timing-correction-current-20261022.json`.
The progress refresh helper now observes the cancellation marker and cannot
restore this effort to the active plan. Earlier task and resume tables below
are historical only. No Git stage/commit/push or branch operation was performed.

## Historical paused state — 2026-10-22 13:29 HKT

**Goal paused.** The latest question asks why the work took so long; it does not
resume implementation. c0184812 is the concrete corrected source identity.
Fresh receipts confirm synthesis, all 12 modeled full-system cases, native
control/reset-cone reviews and four static clock views PASS. **Placement/routing
has not been admitted. No new bitstream is ready to flash.**

| Task | What changed | Verified state |
|---|---|---|
| **Current: c0184812 timing correction** | Preserve full accelerator, 4 GiB, JTAG + PCIe and all four clock/DDR modes | **Paused; placement/routing not admitted** |
| Exact source synthesis | Local hazard updates, one-hot read cache, separate same-cycle stream result registers, host AXI stage and first-lane predecode | PASS; final routed timing remains unproven |
| Modeled full-system RTL | Current complete source and unchanged traffic scoreboards | All 12 cases PASS; vendor/DDR boundaries modeled |
| Native control and reset | Actual synthesized CSR/reset/ack bindings and critical cones | Both reviews PASS; remaining CDC/routed review pending |
| Four static clock views | 100/148.837 MHz × DDR800/1066; preserve reset release/data timing | Source reviews PASS; routed timing/CDC pending |
| Bitstream, package and hardware | Exact reviewed c0184812 required | No new bitstream; SRAM/TinyStories/examples/Mac tests pending |

The preceding full implementation c0184811 took approximately 3 hours 40 minutes
(21 October 23:32 HKT to 22 October 03:13 HKT). It finished 7/7 implementation
milestones but failed final setup: WNS -0.182 ns, 659 endpoints. Its real timing
failure required structural corrections; it was not a continuing build or a
simulator-license failure. Review-tool mistakes and overextended offline checking
also caused avoidable agent delay. A source review PASS does not establish routed
or physical correctness.

Exact pause receipt: `build/handoffs/c0184812-paused-state-20261022T052948Z.json`.
Current canonical: `build/handoffs/runtime-structural-timing-correction-current-20261022.json`.
Source fingerprint (not a bitstream hash):
`bf9e97899886ac56043288121a958edfcb627ce1b23d4f17af6c5656843f89a4`.

All five tracked c0184812 services are now inactive with MainPID 0 and saved PASS
receipts. No worker was killed or restarted during this refresh. Unrelated jobs
were not changed. No hardware/flash, Git staging/commit/push or branch operation
was performed. The card's current physical ownership/identity was not rechecked.

- source_synthesis: `opentpu-c0184812-source-synthesis-20261022-v1.service`; `build/fedora-vivado/runtime-netlist-c0184812-20261022-v1/run/manifest.json`.
- full_top_traffic: `opentpu-c0184812-native-traffic-20261022-v1.service`; `build/checks/runtime-structural-timing-native-traffic-c0184812-preparation-20261022-v1/run/manifest.json`.
- native_control: `opentpu-c0184812-source-native-review-20261022-v1.service`; `build/checks/runtime-global-timing-source-owner-c0184812-20261022-v1/run/manifest.json`.
- native_reset_cones: `opentpu-c0184812-reset-and-critical-cone-review-20261022-v1.service`; `build/checks/runtime-c0184812-reset-cones-owner-20261022-v1/run/manifest.json`.
- four_static_clock_views: `opentpu-c0184812-source-static-clock-views-20261022-v1.service`; `build/checks/runtime-full-static-views-c0184812-20261022-v1/owner-run/manifest.json`.

**Resume only after explicit user instruction:** verify these receipts and launch
identities; add the current c0184812 owner roles and dispatch to the progress
refresh helper (it still describes the earlier correction); complete the exact
remaining source/CDC requirements; admit nominal-target c0184812 placement/routing
when its technical prerequisites pass. Retarget exact routed review/generation/
package owners during implementation, then complete applicable offline gates and
already authorized exclusive SRAM/TinyStories/examples testing before the Mac
acceptance workflow. Preserve both runtime interfaces and every requested mode.
Permanent flash remains a separate exact-image authorization.

## Historical authoritative snapshot — 22 October 09:18 HKT

Verified 2026-10-22 09:18 HKT. **Current task: real timing-path correction. No successor
full image identity or implementation has been admitted.** c0184811 finished all
7/7 implementation milestones with native exit 0, but its exact final global
setup report fails. It is ineligible for generation, packaging or programming.
No bitstream was generated and this session performed no hardware operation.

| Current task | What changed | Evidence / next action |
|---|---|---|
| **Priority: timing-path correction** | Keep full accelerator, 4 GiB, all four modes and JTAG + PCIe | All659 original failing endpoints collected and accounted; address complete path families before a successor build |
| Local memory hazard update | Per-bucket count/nonzero updates use their own bucket state rather than global indexed reads | All-state formal equivalence PASS for64 buckets/six-bit counters, arbitrary pointers/flags and simultaneous increment/decrement |
| Stream result locality | Separate same-cycle Y/Q result registers using the existing two-output adder primitive | Enabled-cycle schedule and arithmetic unchanged; timing improvement unproven |
| Corrected RTL behavior | Actual three changed RTL files in an isolated complete test source | All15 existing native-memory and stream/VOP regressions PASS in544.73s; modeled memory only |
| Native register/control proof | Actual current mapped component checkpoint and primitive/pin graph | All256 distinct result pairs proved;266 initialized register relations and one LUT relation;12 negative/control checks and exact raw-table replay PASS |
| Host/reset/remaining compute | Three host paths,11 CH0 reset recovery/removal paths and remaining compute families | Corrections/ownership review still required; do not waive ordinary paths, reduce clocks/interfaces or repeat an identical implementation |
| Generation/package/SRAM/Mac | Exact reviewed successor required | Pending; previous tool preparation remains historical/reference evidence, not a flash-ready image |
| Existing examples | Current retained compiler/host source | Fresh14 ISA examples plus24 unchanged software checks passed; physical examples pending |

**Exact rejected image:** c0184811, source fingerprint
`e20fbb81d2d54fe6f7e9a5b9e9ca887345576b6ee979d113927a52306e7e2b92`;
final routed checkpoint SHA256
`5823950cbbf6ccdf3216cdacd3cff757c665fcb6f101bda0c376726f1a1dadbe`.
This is a checkpoint hash, not a bitstream hash. Final original WNS **-0.182ns**,
TNS **-37.448ns**, **659 setup endpoints**; hold +0.024ns, no hold/pulse failures.
All334303 routable nets are routed. This is a real timing failure, not a parser
or simulator-license failure. It is not a newly observed physical CH0 data failure.

| Path family in original view | Failing endpoints | Worst setup |
|---|---:|---:|
| runtime_compute | 645 | -0.149ns |
| 250MHz independent host path | 3 | -0.182ns |
| AON memory_reset to CH0 reset PRE: writeclocks0_outs0 | 2 | -0.089ns |
| AON memory_reset to CH0 reset PRE: writeclocks0_outs2 | 9 | -0.012ns |

The11 reset paths have a natural2.500ns recovery/removal requirement. Local
PHY/pad/reset-output scope passed separately; that does not waive these global
paths. Any assertion exception requires exact initialized/reset-chain ownership
and preserved release/data timing evidence, under a new reviewed constraint scope.
No reset exception or timing relaxation was applied here.

| Complete native timing view | Setup WNS | Failing endpoints |
|---|---:|---:|
| Mode0:100MHz/DDR800 | -0.182ns | 3 |
| Mode1:148.837MHz/DDR800 | -0.182ns | 648 |
| Mode2:100MHz/DDR1066 | -0.182ns | 14 |
| Mode3:148.837MHz/DDR1066 | -0.182ns | 659 |
| Actual fast-divider1 | -0.182ns | 649 |
| Actual fast-divider3 | -0.182ns | 660 |

All six native views completed with exit0; the numerical reader correctly rejected
them. The host250MHz failure persists in the100MHz modes, so those views do not
provide a programming fallback. Implementation-only extra0.050ns uncertainty was
restored to the original operating requirement; this target strategy did not close
the image. Do not launch another identical full build or repeat the old route
recovery attempts. Preserve the working fixed-clock baseline artifacts.

**Current correction source and evidence:**

- Canonical: `build/handoffs/runtime-setup-headroom-successor-current-20261021.json`.
- Exact setup rejection: `build/checks/runtime-c0184811-final-setup-failure-20261022-v1/manifest.json`.
- Complete six-view disposition: `build/checks/runtime-c0184811-six-view-timing-disposition-20261022-v1/manifest.json`.
- All659 endpoint collection: `build/checks/runtime-c0184811-all-failing-paths-20261022-v1/run/manifest.json`.
- Complete group/family accounting: `build/checks/runtime-c0184811-complete-path-family-analysis-20261022-v1/manifest.json`.
- Isolated corrected source: `build/checks/runtime-timing-correction-components-20261022-v1/source`.
- Changed real RTL only: `rtl/mem/otpu_native_dram.sv`, `rtl/vpu/otpu_fpipe.sv`, `rtl/vpu/otpu_se_tail.sv` under that source.
- Real RTL owner/result: `build/checks/runtime-timing-correction-components-20261022-v1/launch.json` and `run/manifest.json`.
- Formal update proof: `build/checks/runtime-local-hazard-update-formal-20261022-v1/manifest.json`.
- Native mapping facts/checkpoint: `build/checks/runtime-timing-correction-vpu-native-map-20261022-v2/run/manifest.json`.
- Native equivalence proof: `build/checks/runtime-timing-correction-enable-equivalence-20261022-v1/manifest.json`.
- Raw-table proof-model replay: `build/checks/runtime-timing-correction-enable-equivalence-20261022-v1/native-model-replay.json`.

The first native map checker compared CE-driver names and rejected equivalent
replicated enables. Its failure receipt is preserved. A fresh fact collector saved
the actual checkpoint before validation; independent native graph/state induction
proved the initialized copies and their CE/D controls equivalent. This was a
review-tool assumption failure; it did not establish an RTL functional defect.
A portable netlist-parser attempt rejected valid named module-port alias syntax;
its log remains preserved. The accepted proof instead uses actual native property
and edge tables, rebuilt exactly into its proof model. No assumed name aliases.
Component verification does not establish new full-image timing or hardware.

Six idle qualification followers were stopped only after checking exact job/launch
hashes, live PID/start ticks/arguments and absence of children. Existing native
numerical/PHY/finding collectors were retained. Proof:
`build/handoffs/c0184811-waiting-qualification-superseded-20261022-v1.json`.
Frozen old tools/receipts and unrelated jobs remain intact.

**Resume order:** inspect current canonical/live handles and the corrected source;
finish host-path, reset ownership and remaining compute-path corrections. Retain
the all-state hazard and actual-RTL/native evidence with exact input hashes.
Assign a successor identity only for a concrete full preparation, retaining
716-DSP/full accelerator, 4GiB, CH0 lanes `[0,1,2,3,4,5,8,7]`, CH1 ECC only,
JTAG USER2 runtime DDR/control/calibration/status plus PCIe Gen2x8, independent
host clock, all100/148.837MHz × DDR800/1066 modes, boot mode2 and mode-bound
c0172608/c0172668 firmware. No clocks, capacity, interfaces or latency were
reduced in these component prototypes.

Run fresh exact current source/native gates before successor P&R admission;
current component proofs or historical image scopes never transfer whole-image
qualification. Retarget the tested twelve-scope review/generation/package tools
with explicit producer/version bindings and actual new facts. Complete every
finding/object and source/routed waiver disposition, then real bitstream
header/device/packet CRC and package validation. Already authorized exclusive
SRAM/four-mode TinyStories/examples and selected Mac LFM/Qwen acceptance remain.
Permanent flash requires exact-image authorization after its applicable checks.

No new full bitstream build is queued or running. This session did not touch
hardware/flash, stage/commit/push Git files or create a branch. The original Git
index still matches `build/handoffs/mac-c0182863-results-pull-20261018-v1/index.after`.
c0182863 remains the last recorded permanent image; recheck exclusive ownership
and live identity before any future hardware operation. Keep c0182800 fallback.

## Historical authoritative snapshot — 21 October 18:58 HKT

Verified 2026-10-21 18:58 HKT. **Current task: one bounded global-router recovery on an isolated
diagnostic copy. No new full implementation has been admitted.** The user briefly
paused and resumed this goal; the latest instruction is active. Background jobs
were revalidated before work continued.

The original c0184810 implementation **finished all 7/7 milestones** with native
exit 0 and a saved final checkpoint. Its final setup result fails: **WNS -0.026 ns,
TNS -1.786 ns, 123 endpoints**, all in `runtime_compute`. Hold minimum is +0.009 ns,
with no hold or pulse failures. The original image is ineligible for generation,
packaging, programming and workload testing. No bitstream was generated or loaded.
This is a real implementation timing finding, not a parser or license failure.

| Active task | What changed | Current evidence / next action |
|---|---|---|
| **CURRENT: bounded global route recovery** | One normal `route_design` pass on the isolated targeted-reroute diagnostic; original clocks/interfaces/RTL retained | Current owner is resource capped and has a 40-minute native timeout; finish this bounded investigation before selecting successor work |
| Source correctness | Single-step accepted-write publication, native idle waits for publication, seven-bit maximum-backlog count | Public native/AXI checks and 65,600-write wrap test passed; full 12-case modeled top, 247 host cases, 32 trained ISA tokens and 224 extracted reset checks passed |
| Completed source acceptance | All four 1,776-row source-purpose inventories and scoped warning/native intake | PASS; this source acceptance does not waive the final setup failure |
| Current PHY/pad/reset scope | Same 4 GiB, full accelerator, both JTAG USER2 and PCIe, all four modes | Exact routed PHY review PASS; this scope is separate from failed global timing |
| Reader/decision preparation | Exact native objects, vendor/CDC/provenance and saved-data replay | Preserve frozen tools and receipts; waiting failed-image qualification followers were stopped; retarget only after a reviewed successor strategy exists |
| Examples | Matching current compiler/host sources | 14 ISA cases and 24 software checks pass; no RTL/physical example qualification |
| Physical TinyStories / Mac | Reviewed exact successor image and matching tools required | Pending; no permanent-flash authorization exists for a successor |

Current implementation identity/configuration remains c0184810,
`xc7k480tffg1156-2`, 4 GiB, CH0 physical lanes `[0,1,2,3,4,5,8,7]`, CH1 ECC only,
both JTAG runtime DDR/control/calibration/status and PCIe Gen2 x8, modes
100/148.837 MHz × DDR800/1066, boot mode 2 and image/mode-bound two-channel
c0172608/c0172668 firmware. Nothing was removed or downclocked to obtain a pass.

| Timing view | Setup WNS | Failing setup endpoints | Hold / pulse |
|---|---:|---:|---|
| Mode 0: 100 MHz / DDR800 | +0.013 ns | 0 | PASS |
| Mode 1: 148.837 MHz / DDR800 | -0.026 ns | 123 | PASS |
| Mode 2: 100 MHz / DDR1066 | +0.026 ns | 0 | PASS |
| Mode 3: 148.837 MHz / DDR1066 | -0.026 ns | 123 | PASS |
| Actual fast-divider views 1 and 3 | -0.026 ns | 124 each | PASS |

The requested four-mode image remains required. Passing the 100 MHz views alone
does not qualify it. Complete numerical disposition:
`build/checks/runtime-c0184810-six-view-timing-disposition-20261021-v1/manifest.json`.

**Preserved original checkpoint:**
`build/fedora-vivado/runtime-implementation-c0184810-20261021-v2/run/final-routed.dcp`
SHA256 `2393356c7720e867aefeac7b6096c5347c5381332709c152477135bb95f975a8`.
Source fingerprint (not bitstream SHA):
`563139cbf626432aee8d83ec2095b4d674e02f3cd87125d4bacf96b5bf5bcf58`.
Final setup disposition:
`build/checks/runtime-c0184810-final-setup-failure-20261021-v1/manifest.json`.

The first critical path is a weight register to DSP A input, 3.970 ns data delay
including 3.711 ns routing (93.5%). Another failing path is quantizer index to TMEM,
with a deeper carry/LUT cone. These are accelerator routing/timing paths; do not
claim they are a newly measured CH0 memory failure. Exact extracted path evidence:
`build/checks/runtime-c0184810-critical-path-route-analysis-20261021-v1/manifest.json`.

**Bounded diagnostic state:** the first targeted pass routed 183 selected nets but
worsened compute WNS to -2.415 ns. It did not relax clock or constraint commands.
Seven selected objects were already legal `INTRASITE` nets before reroute; the
raw `SELECTED_UNROUTED` metric must not be described as seven missing routes.
The original first diagnostic and its receipt stay immutable. Classification note:
`build/checks/runtime-c0184810-intrasite-diagnostic-classification-20261021-v1/manifest.json`.
The single normal-router recovery starts from that diagnostic copy, not the
original final checkpoint. It has one pass and a 40-minute native limit. Neither
diagnostic is a programming-qualified image. After this bounded investigation,
choose a deterministic correction under its own identity; do not silently launch
another identical full build, relax timing limits or discard a requested interface.

Six idle waiting qualification followers were stopped after checking exact PID,
start ticks, command, job/receipt hashes and absence of children. Their frozen
inputs/receipts remain preserved. Already executing numerical, PHY and native
finding collections were retained for evidence. The numerical reader correctly
rejected real setup failures; PHY passed. Exact stopped-worker evidence:
`build/handoffs/c0184810-waiting-qualification-superseded-20261021-v1.json`.

| Live current owner | PID | State | Exact launch |
|---|---|---|---|
| current_route_recovery | 2624537 | RUNNING_C0184810_SINGLE_GLOBAL_ROUTE_RECOVERY_DIAGNOSTIC_NOT_AN_IMAGE | `build/checks/runtime-c0184810-route-recovery-diagnostic-20261021-v1/launch.json` |

Canonical: `build/handoffs/runtime-write-accept-successor-current-20261021.json`.
Use `build/handoffs/update-c0184810-canonical.py` to preserve the root witness chain.
Use `runtime-clock-live-status.py` for current identities and
`refresh-dual-interface-progress-20261018.py` for the main todo table. The refresh
helper now follows the setup rejection and diagnostic rather than restoring
stale programming eligibility. The current registered role map includes completed
source evidence; a receipt's old RUNNING/WAIT label alone never proves a live job.

**Next executable work:** monitor the exact recovery owner; disposition its actual
routing/timing/constraint result immediately. Preserve the shared counter fix and
working fallback. Any prepared successor must retain the full requested scope,
get its own identity and pass applicable source/routed/integrity/package checks,
then authorized exclusive temporary SRAM / four-mode TinyStories and Mac work.
Permanent flash still requires exact-image authorization. Do not ask again for
already authorized temporary programming or invent local PCIe gates on JTAG-only
Fedora. No hardware, flash, Git staging, commit, push or new branch occurred.
The original index is preserved against
`build/handoffs/mac-c0182863-results-pull-20261018-v1/index.after`.

Generation v2 saved-data replay/decision components passed 24 software controls.
The isolated PHY child and complete 80,019-row finding/object intake replay were
preflighted with complete historical fixtures; these are component tests only,
not current image qualification. No valid generation gate, accepted final finding
ledger or package was admitted for the failed image. Retain these tools for the
actual successor without importing historical qualification.

## Historical snapshot before final setup disposition

The following saved snapshot predates the final timing rejection and bounded
diagnostics above. Its RUNNING/queued labels and worker handles are historical.

Verified 2026-10-21 16:35 HKT. **Current task: c0184810 initial routing completed and its checkpoint is saved; post-route physical optimization is running (4/7 completed milestones).**
Synthesis/linked collection, current native control/reset/cone review and all four
source clock views passed. The exact native checkpoint/intent intake passed and physical implementation
started: optimization, placement, pre-route physical optimization and initial
routing completed; `post_route_physical_optimization` is running. This is4/7 completed
implementation milestones (57% of milestones, not a remaining-time estimate). Full RTL12, host247, trained ISA32 and224 extracted
reset checks passed. No bitstream, hardware operation or flash write exists.

| Task | What changed | Current evidence / remaining work |
|---|---|---|
| **CURRENT: c0184810 implementation** | Same frozen counter/reset-correction source, full accelerator/4GiB/four modes/JTAG+PCIe | All source acceptance gates passed; initial routed checkpoint saved; post-route physical optimization running;4/7 milestones |
| Native correction binding | Single-step publication sources and maximum-backlog counter width | All64 actual write-counter CDC sources and28 pending-command bits verified; unchanged source and completed native probe reused |
| Initial source purposes | Actual current1650-row report and496 vendor selectors; fresh immutable review tools | PASS: all1650 initial current source purposes assigned after exact four-mode context and fresh native vendor probes |
| Additional source purposes | Derive current additional rows independently in every mode | PASS: all126 additional findings assigned in every mode, all four1776-row inventories closed; no prior-image qualification imported |
| Source warnings/final source acceptance | Scoped warning/native constant proof and complete source reconciliation | PASS: scoped warnings/native intake and final source acceptance complete; source closure remains separate from routed approval |
| Routed structural collection | Same c0184810 source; all58 skew groups, four-mode64 write-publication paths and28 pending bits, fresh removed-field dependency graph | 83 reader guards and17 Tcl completeness checks passed; native source API preflight PASS (58 groups/2536 queries,64 timed crossings,28 pending bits); routed collection follows implementation/numerical release |
| Complete skew reconciliation | Same exact source and routed image, original bounds retained | 12 guards passed; current v1 owner scheduled after structural producer release; complete original/four-mode bound reconciliation with fresh dependency proof |
| Routed vendor retention | Complete current496-row source scope, FIFO controls and317 receiver/enable registers | 36 guards plus actual current source facts passed; exact v1 owner follows source acceptance and routed structural release |
| Routed CDC reconciliation | Original plus four intent/OOB views; current fanin and initialized ordinary-replica proof | 41 guards passed, including all four current1776-row source contexts; current v2 native owner follows vendor release and shares all-source waiver export |
| Full source waiver reference | All, unwaived and waived CDC scopes and native waiver exports for original/four modes | 9 context guards passed; mandatory collection shares the current CDC v2 source checkpoint opens; source/routed provenance disposition remains |
| Complete technical intake | All45 report scopes,30 complete native object sets, current source waiver reference and exact review releases | 10 controls passed; current v1 owner scheduled; no finding decision or image approval is inferred |
| Current review provenance | Full frozen source fingerprint, exact producer releases, native completions, child receipts and complete output inventories | 23 controls plus actual current source/host closed bindings passed; exact cohort owner is scheduled; no technical decision or generation approval is inferred |
| Examples | Match the current c0184810 host/compiler source | All14 ISA cases passed with program/image/output hashes matching earlier fixtures;24 unchanged software checks passed; RTL and physical examples pending |
| Routed review/package/hardware | Six global numerical views, full PHY trace, complete findings/objects and remaining structural CDC | Current v2 routed followers scheduled; packaging and physical TinyStories/Mac remain pending |

**Metadata-only recovery, no image revision:** the corrected source contract already
contains `ordinary_core_reset_distribution`. A copied reviewer stripped that key
before comparing its supplemental contract and falsely rejected otherwise equal
records. Native probe exit0, exact checkpoint hash, all64 publication paths and
all source files were preserved. Source-review v3 uses a strict complete-object
comparison (five guards) and reuses those exact closed native tables. It passed.
Synthesis was not repeated; the old implementation worker had never started
physical implementation. Fresh v2 followers bind the recovered source receipt.
All failed receipts remain at their original paths; no gate or numerical bound
was relaxed. Image ID stays c0184810.

Initial-purpose admission then exposed stale child-directory/source-review paths
in copied tooling. Failed wrappers/SELECTED receipts remain preserved. The v5
preparer performs all ready software stages against completed current facts
before admitting its actual v4 child, and every stage passed. Native selectors
match the complete semantic identity (endpoints, clocks, exception and depth);
report row numbers are observations derived freshly, not identities across images.
The current source-purpose chain uses fresh v5 library/output directories and
source-review v3. Do not reactivate the superseded wrappers or reuse their failed
receipts as current approval.

**Current canonical:** `build/handoffs/runtime-write-accept-successor-current-20261021.json`.
Update through `build/handoffs/update-c0184810-canonical.py` so its witness propagates
through the preserved source9/8 lineage. Full implementation directory is now
`build/fedora-vivado/runtime-implementation-c0184810-20261021-v2`.
The immutable source job remains `runtime-netlist-c0184810-20261021-v1`.
Read current process identities with `build/handoffs/runtime-clock-live-status.py`;
refresh the main todo table with `refresh-dual-interface-progress-20261018.py`.

| Current role | PID | Ownership | Latest receipt status | Exact launch witness |
|---|---|---|---|---|
| source_synthesis | 2565689 | released | PASS_COMPLETE_RUNTIME_SOURCE_SYNTHESIS_AND_NETLIST_COLLECTION_REVIEW_REQUIRED | `build/fedora-vivado/runtime-netlist-c0184810-20261021-v1/launch.json` |
| full_current_native_traffic | 2564863 | released | PASS_C0184810_CURRENT_FULL_SOURCE_NATIVE_TRAFFIC_12_CASES_PHYSICAL_GATES_PENDING | `build/checks/runtime-global-timing-native-traffic-c0184810-preparation-20261021-v1/launch.json` |
| source_native_review | 2580407 | released | PASS_C0184810_SOURCE_CONTROL_COHERENT_CSR_RESET_AND_ACK_NATIVE_BINDING_ALL_MODE_CDC_PENDING | `build/checks/runtime-global-timing-source-owner-c0184810-20261021-v3/launch.json` |
| reset_and_critical_cone_review | 2581295 | released | PASS_C0184810_CURRENT_CRITICAL_CONES_AND_SHARED_CONTROL_RESET_NATIVE_BINDING_REMAINING_CDC_OPEN | `build/checks/runtime-c0184810-reset-cones-owner-20261021-v2/launch.json` |
| source_static_clock_views | 2581297 | released | PASS_C0184810_FOUR_FULL_SOURCE_STATIC_VIEWS_AND_IMMEDIATE_REVIEW_CDC_ROUTING_PENDING | `build/checks/runtime-full-static-views-c0184810-20261021-v2/launch.json` |
| current_full_implementation | 2581303 | live | C0184810_FULL_NATIVE_IMPLEMENTATION_RUNNING | `build/fedora-vivado/runtime-implementation-c0184810-20261021-v2/launch.json` |
| host_source_preparation | 2568400 | released | PASS_C0184810_HOST_27_PROTOCOL_105_TRANSPORT_47_BACKEND_50_RETIRED_18_DISTRIBUTION_AND_ACTUAL_SOURCE_ONLY_GUARDS | `build/checks/runtime-host-c0184810-preparation-20261021-v1/launch.json` |
| isa_model_reference | 2568586 | released | PASS_C0184810_FOUR_MODE_32_TOKEN_TRAINED_ISA_REFERENCE_HARDWARE_PENDING | `build/checks/runtime-model-reference-c0184810-preparation-20261021-v1/launch.json` |
| current_routed_numerical | 2581355 | live | WAIT_C0184810_EXACT_IMPLEMENTATION_RELEASE_FOR_NUMERICAL | `build/checks/runtime-routed-numerical-owner-c0184810-20261021-v2/launch.json` |
| current_routed_phy | 2581361 | live | WAIT_C0184810_EXACT_IMPLEMENTATION_RELEASE_FOR_PHY | `build/checks/runtime-routed-phy-owner-c0184810-20261021-v2/launch.json` |
| current_native_findings | 2581363 | live | WAIT_C0184810_EXACT_IMPLEMENTATION_RELEASE_FOR_WAIVER | `build/checks/runtime-routed-waiver-owner-c0184810-20261021-v2/launch.json` |
| current_scope_reconciliation | 2581365 | live | WAIT_C0184810_EXACT_NATIVE_SCOPE_AND_OBJECT_FACTS_OWNER_RELEASE | `build/checks/runtime-routed-scope-reconciliation-owner-c0184810-20261021-v2/launch.json` |
| host_native_binding | 2581367 | released | PASS_C0184810_MATCHED_DISTRIBUTION_HOST_GUARDS_CPU_MODE_DATA_AND_TRAINED_ISA_REFERENCE_HARDWARE_PENDING | `build/checks/runtime-c0184810-host-admission-binding-20261021-v2/launch.json` |
| source_control_intent_audit | 2581299 | released | PASS_C0184810_CURRENT_FOUR_MODE_CONTROL_INTENT_AND_1360_PRESERVED_PATHS_PROTOCOL_AND_ROUTING_GATES_PENDING | `build/checks/runtime-control-intent-current-c0184810-20261021-v2/launch.json` |
| source_post_intent_context | 2581301 | released | PASS_C0184810_FOUR_MODE_CDC_CONTEXT_INVENTORY_ONLY_ALL_PURPOSE_DISPOSITIONS_REQUIRED | `build/checks/runtime-control-cdc-context-c0184810-preparation-20261021-v2/launch.json` |
| additional_source_purposes | 2584847 | released | PASS_C0184810_CURRENT_NATIVE_ADDITIONAL_PURPOSES_AND_ALL_FOUR_SOURCE_INVENTORIES_ROUTED_PHYSICAL_PENDING | `build/checks/runtime-c0184810-additional-purpose-owner-20261021-v4/launch.json` |
| current_initial_source_purpose | 2583877 | released | PASS_C0184810_ALL_1650_INITIAL_SOURCE_CDC_PURPOSES_REVIEWED_ADDITIONAL_ALL_MODE_AND_ROUTING_PENDING | `build/checks/runtime-c0184810-source-purpose-owner-20261021-v4/launch.json` |
| source_warning_native_intake | 2585412 | released | PASS_C0184810_SOURCE_WARNINGS_AND_EXISTING_NATIVE_INTAKE_BOUND_TO_EXACT_SOURCE_ROUTED_GATES_PENDING | `build/checks/runtime-c0184810-source-post-review-owner-20261021-v1/launch.json` |
| current_source_acceptance | 2599721 | released | PASS_C0184810_ALL_CURRENT_SOURCE_REVIEWS_CORRECTED_CURRENT_BASELINE_AND_EXACT_MODE_INVENTORIES_ROUTED_PHY_PACKAGE_PENDING | `build/checks/runtime-c0184810-source-acceptance-20261021-v2/launch.json` |
| current_routed_structure | 2595627 | live | WAIT_C0184810_EXACT_IMPLEMENTATION_RELEASE_FOR_STRUCTURAL_COLLECTION | `build/checks/runtime-routed-structure-owner-c0184810-20261021-v1/launch.json` |
| current_routed_skew | 2597330 | live | WAIT_C0184810_EXACT_ROUTED_STRUCTURAL_COMPONENT_RELEASE_FOR_SKEW_RECONCILIATION | `build/checks/runtime-routed-skew-owner-c0184810-20261021-v1/launch.json` |
| current_routed_vendor | 2601218 | live | WAIT_C0184810_SOURCE_CONTRACT_AND_ROUTED_FACTS_FOR_VENDOR_REVIEW | `build/checks/runtime-routed-vendor-owner-c0184810-20261021-v1/launch.json` |
| current_routed_cdc | 2610061 | live | WAIT_C0184810_CURRENT_ROUTED_VENDOR_RELEASE_FOR_EXACT_CDC_NATIVE_CONTEXT | `build/checks/runtime-routed-cdc-owner-c0184810-20261021-v2/launch.json` |
| current_final_technical_intake | 2610525 | live | WAIT_C0184810_EXACT_CURRENT_ROUTED_OWNERS_FOR_TECHNICAL_INTAKE | `build/checks/runtime-final-review-intake-c0184810-20261021-v1/launch.json` |
| current_review_provenance | 2613412 | live | WAIT_C0184810_ALL_EXACT_CURRENT_REVIEW_RELEASES_FOR_PROVENANCE | `build/checks/runtime-current-review-provenance-owner-c0184810-20261021-v1/launch.json` |

**New exact structural owner:** `runtime-routed-structure-owner-c0184810-20261021-v1`
completed its native API preflight on the exact current source checkpoint: all58
skew groups and2536 native queries resolve;64 publication paths retain the7.5ns
bound (source estimated minimum slack+6.985ns); all28 pending-counter bits and the
unused status-chain fanout passed. This is source adapter evidence, not routed
timing or physical DDR qualification. Its fresh immutable tools passed83 controls, including rejecting the old six-bit
backlog counter, missing/foreign Gray sources, changed7.5ns bounds, incomplete
reset coverage and unsupported/observable removed-field graphs. All58 original
skew groups are inventoried. Every routed missing vendor endpoint is recorded,
with complete current-source fanout/LUT-INIT evidence collected for disposition;
none inherits an older image's removed-field approval. The routed collector
waits for the exact implementation and numerical owner to release its native
memory slot. This scheduling avoids a fourth simultaneous large Vivado review.
The exact `runtime-routed-skew-owner-c0184810-20261021-v1` is scheduled after
structural component release. Its12 guards reject incomplete group inventories,
missing/currently observable roots, lost sequential dependencies and partially
missing live groups; no whole live bound is discarded for an absent alias. It
reconciles all58 original source groups against original and four-mode saved/native
reports. A component PASS is explicitly separate from complete structural CDC/skew,
vendor operating contracts, global finding/provenance disposition and image
approval. No new implementation or source synthesis was started for this work.

**Source closure now complete:** all four native intent modes and the complete
before/after inventories passed. All1650 initial and126 additional source purposes
per mode are assigned; scoped36-warning/native intake and final source acceptance
passed. The source-only conditions and physical/vendor-model limits remain.

The final-source consumer had one stale integration receipt literal (`v5`) while
both the real producer and protocol consumer use the fresh current `v3` output.
Four binding guards pass. Only that literal changed in source-acceptance v2;
the waiting v1 owner was stopped with no child/native/hardware operation. Old
receipts and the exact replacement proof remain at
`build/handoffs/c0184810-source-acceptance-binding-replacement-20261021-v1.json`.
The new owner finished PASS. No RTL, synthesis, placement or routing was restarted.

**Routed vendor review:** current-source1262 endpoint facts and all496 selected
rows pass the new reader. Its36 guards include active receiver retention, FIFO
clock/enable/reset ownership, missing paths, nonfinite timing, unknown omissions
and source-to-route reset/clock ownership changes. The exact owner is
`runtime-routed-vendor-owner-c0184810-20261021-v1`.

**Routed CDC reconciliation:**41 controls pass, including every1776-row current
source mode. The exact `runtime-routed-cdc-owner-c0184810-20261021-v2` waits for
vendor/structural release, derives every current semantic report delta, and collects
fresh source/routed fanin and ordinary-register inputs for the original and four
mode intent/OOB contexts. A replica requires matching source and routed origin,
primitive, INIT, clock/data/enable/reset, polarity and unmarked ordinary state;
no historical14-change or104-omission count becomes current approval. Every
clock, depth, exception, destination and multiplicity is retained. Remaining
all-scope finding/waiver/object disposition, final provenance, generation/package
binding and physical execution still must finish.

**Full waived-scope reference added without duplicate checkpoint reads:** source
acceptance assigns1776 unwaived findings per mode; it does not by itself dispose
the much larger waived scopes. Fresh source-reference tooling passed9 exact-context
guards. The queued CDC v2 collector now also exports all/unwaived/waived source
CDC reports and native waiver definitions/statistics for the original and all four
modes, during the same source DCP opens. The reference reader must reconcile all
three scopes and match each unwaived view to the already closed current source
intent exactly. This is collection/reference evidence, not waiver approval.

The prior CDC v1 follower was still waiting, with no native child or consumed
routed artifact. Its job/tools/receipt remain frozen. A fresh v2 owner,41 controls,
and source-reference9 controls replace only that waiting follower; the hardware
source, image ID, synthesis and implementation stay unchanged. Exact evidence:
`build/handoffs/c0184810-cdc-source-reference-rebinding-20261021-v1.json`.

**Final technical intake is now scheduled:**
`runtime-final-review-intake-c0184810-20261021-v1` waits for all11 exact source /
routed producers, then revalidates all45 report scopes and30 complete native
object sets and binds the new source waiver reference. Its10 controls reject
wrong/aliased producers, incomplete native object identities and missing scope
membership. It preserves ambiguous identical report semantics explicitly rather
than inventing an individual waived/unwaived classification. All finding
technical decisions start UNREVIEWED; this intake grants no waiver, generation,
package or hardware qualification. The active task must complete the actual
current technical dispositions as soon as the evidence closes.

Next remaining preparation: final current finding/waiver/object policy and actual
provenance closure, then replace the generation77 component-fixture bindings with
the exact current multi-owner review schema and matching package/execution tools.
The old generation preparation remains explicitly unadmitted. Do not attempt to
use its old monolithic/composite numerical producer paths as current qualification.

**Exact current review provenance is scheduled:**
`runtime-current-review-provenance-owner-c0184810-20261021-v1` waits for the12
source/routed scope producers, including complete technical intake. Its23 controls
reject wrong-image/old-job receipts, live producers, missing native completions,
changed frozen inputs, unbound native outputs, mismatched children/checkpoints and
premature whole-image qualification. Actual closed current source and host
producers passed this binding check. The recomputed source fingerprint remains
`563139cbf626432aee8d83ec2095b4d674e02f3cd87125d4bacf96b5bf5bcf58`.
This is the source fingerprint, not a bitstream SHA. The authority binds the exact
current registered job/launch hashes. The eventual cohort receipt explicitly
leaves every technical finding/waiver decision and bitstream generation denied.

Initial routing completed and `routed-before-postopt.dcp` was saved. The live
implementation is now `post_route_physical_optimization`,4/7 completed milestones
(57%, not an ETA). That intermediate checkpoint and its timing are not the final
reviewed artifact. Post-route optimization, PCIe margin/hold repair and final
reports must finish, followed by all exact routed reviews. No new FPGA build was
started, and no source or currently frozen worker input was changed.

Current examples evidence:
`build/checks/basic-operation-examples-c0184810-binding-20261021-v1/manifest.json`.
All14 default ISA cases passed freshly with matching current sources. Programs,
initial images and outputs exactly match the prior passing fixtures. The24
software-test receipt remains bound to unchanged example/test files. The existing
FPGA examples adapter requires the eventual reviewed runtime-clock package;
c0182863 fixed-clock qualification does not satisfy that adapter. No physical
example run or current c0184810 image qualification is claimed.

Next: finish current implementation while source-purpose/warning acceptance
runs. Prepare the remaining full structural routed CDC/skew/provenance and
package/execution bindings during the build, preserving all original limits.
At exact implementation completion the already scheduled numerical/PHY/finding
collectors run immediately. Final disposition still requires every applicable
scope; the global timing collector alone does not establish structural CDC/skew
approval. Continue to authorized exclusive temporary SRAM/four-mode TinyStories
once the exact image is ready. Permanent flash remains a separate exact-image
operation. No additional image or new branch, Git stage/commit/push, hardware or
flash action occurred. The original Git index remains preserved.

The user asked whether the revision count warrants stopping. The evidence audit
and recommendation below are retained: six complete native implementations total
19.28 worker-hours, source9 timing feasibility, and both shared bridge corner
cases reproduced in the prior tested baseline RTL. This is a recommendation to
use source10 as a decision point, not a user cancellation or pause.

## Earlier source/preparation snapshot (superseded by the live state above)

Verified 2026-10-21 13:11 HKT. **Current task: c0184810 source synthesis is running; full-top RTL12, host247 and trained ISA32 passed. Actual placement/routing is queued behind the remaining exact native source gates.**

This turn made concrete progress: corrected the Gray publication contract and a
maximum-backlog reset counter overflow, ran public-interface regressions, created
the complete fresh project and started its exact workers. No bitstream or hardware
operation has occurred. The full goal stays active.

| Task | What changed | Current evidence / next action |
|---|---|---|
| **CURRENT: c0184810 complete build** | Single-step Gray write publication; native idle waits for publication; parameter-sized pending-command counts; full 716-DSP accelerator / 4 GiB / four modes / JTAG + PCIe retained | Source synthesis running; actual placement/routing owner queued behind six native/source gates; 0/7 implementation milestones, not an ETA |
| Public-interface correction tests | Both independent masters, stopped clocks, resets, queued writes and 16-bit wrap | Native/AXI tests pass; 65,600 native writes exact; native and AXI 64-write reset backlog cases pass |
| Matching host and trained reference | Exact new build identity; retired c0184809 rejection; source-only access remains closed | **247 software cases and 32 trained ISA tokens passed**; actual hardware qualification pending |
| Required final review and packaging | Six numerical timing views, full PHY reset tracing, all finding/waiver scopes and typed objects | Four exact review/reconciliation workers are scheduled at implementation completion; numerical29 / PHY36 / scope46 reader guards passed. Structural CDC/provenance and generation/package preparation remain; no ready image |

**Configuration:** xc7k480tffg1156-2; 716 DSP; 4 GiB; CH0 lanes
[0,1,2,3,4,5,8,7]; CH1 ECC only; both JTAG USER2 DDR/control/calibration/status and
PCIe Gen2 x8 memory/control; modes100/148.837 MHz × DDR800/1066; boot mode2;
both-channel mode-bound c0172608/c0172668 firmware. No clock, lane or ECC changes.

**Why the delay:** roughly two days across the c018480x family, including design
and review-tool corrections. The latest parent implementation completed
05:27:17–07:53:15 HKT on October21 (2h25m58s, all7/7). This is distinct from image
qualification. No measured remaining-time estimate supports a completion ETA.

**Two concrete source issues and their evidence:**
1. Accepted totals can advance by two in a source cycle; directly publishing
   Gray(accepted) can change two bits. The exact bridge public witness shows
   0000→0003. Actual generated CH0 has a mutually exclusive shared selector;
   CH1's independent-bank ready functions permit dual acceptance. These tests
   establish a CDC contract defect, not measured metastability or physical
   corruption and not the old c0172300 CH0 read-adapter failure's cause.
2. A six-bit outstanding-command count wraps at64. The public test queued64
   stalled writes, pulsed native reset and observed hold drop while commands
   remained. The new count uses `$clog2(2*(OQ+1)+1)` (7bits atOQ32). Native and
   AXI tests now hold through the drain and count fresh writes/responses exactly.

Original witness and integration proof:
`build/checks/runtime-c0184809-write-accept-gray-witness-20261021-v1/manifest.json`;
`build/checks/runtime-c0184809-integrated-write-accept-exclusivity-20261021-v1/manifest.json`.
The additional failed maximum-backlog witness is preserved in
`build/checks/runtime-write-accept-serialization-c0184810-preparation-20261021-v2/max-backlog-run.log`.
The exact corrected source/tests and PASS receipt are in **v3** of that preparation:
`verification.json`, `publication-bound.json`. The finite queue abstraction checks
2,344 states/13,660 transitions, and all65,536 Gray successors. It proves a
conservative lag bound67 under the stated one-insertion/two-accept queue contract;
it is explicitly not a whole-RTL formal proof. Exact native CDC constraints add
only the possible publication-MSB register aliases without changing any limits.
The fresh source review must verify all64 write-counter destination bits and
their real registered sources, source clocks and active per-period bounds.

**Fresh project:** `build/fedora-vivado/spare-runtime-full-top-c0184810-20261021-v1`;
`spare-runtime-project-c0184810-20261021-v1`. Exactly three full-top parent files
changed: top build ID, memory bridge and its scoped CDC constraints. All other
full-top files match the parent; the actual project was freshly generated.
Actual project audit47/47 and owned-control source inventory266 passed. Matching
host247 and trained four-mode ISA32 passed with exact c0184810 sources. The
**All12 full-top behavioral-boundary cases passed**, including exact matmul in all
four modes, real PCIe/JTAG frontends and reset/drain transitions. Native full
accelerator/top sources are retained; encrypted full XDMA and physical DDR/PHY
behavior remain explicit simulation boundaries. OwnerPID2564863 released PASS.

**Exact background handles:**
- Source synthesis PID2565689, unit `opentpu-c0184810-source-synthesis-20261021-v1.service`;
  job/launch/receipt under `build/fedora-vivado/runtime-netlist-c0184810-20261021-v1/`.
- Full-top RTL owner PID2564863, unit `opentpu-c0184810-native-traffic-20261021-v1.service`;
  `build/checks/runtime-global-timing-native-traffic-c0184810-preparation-20261021-v1/`.
- Fresh source/native review PID2567899, unit `opentpu-c0184810-source-native-review-20261021-v2.service`;
  `build/checks/runtime-global-timing-source-owner-c0184810-20261021-v2/`.
  v1 was stopped while waiting, before any native probe, to correct the actual
  hierarchy prefix to `u_sys/u_ch0` / `u_sys/u_ch1`; no synthesis restarted.
- Reset/cone review PID2567980, unit `opentpu-c0184810-reset-and-critical-cone-review-20261021-v1.service`;
  `build/checks/runtime-c0184810-reset-cones-owner-20261021-v1/`.
- Four-mode source review PID2568032, unit `opentpu-c0184810-source-static-clock-views-20261021-v1.service`;
  `build/checks/runtime-full-static-views-c0184810-20261021-v1/` (21 reader guards).
- Conditional implementation owner PID2568229, unit `opentpu-c0184810-full-implementation-20261021-v1.service`;
  `build/fedora-vivado/runtime-implementation-c0184810-20261021-v1/` (4 worker guards/Tcl complete).
  It waits for installed placement API proof, exact synthesis, source/native,
  reset/cones, full-top12 and four-mode source review. The API proof is explicitly
  an unchanged-command/installed-tool component proof from the parent, not image
  qualification. Actual physical implementation has not started.
- Matching host owner PID2568400 and ISA owner PID2568586 released PASS;
  `build/checks/runtime-host-c0184810-preparation-20261021-v1/run/manifest.json`,
  `build/checks/runtime-model-reference-c0184810-preparation-20261021-v1/owner-run/manifest.json`.

**Review preparations and scheduled exact owners:**
- Numerical tools `build/checks/runtime-routed-numerical-preparation-c0184810-20261021-v1`,
  29 parser/parameter guards. Four nominal views plus actual-fast-divider5.375
  views1/3 retain the strict period and0.095ns setup-uncertainty floor. The four
  physically unused DDR clock outputs have metadata only; no orphan timing
  objects are created. Global setup/hold/pulse/route/clock coverage are reviewed;
  this scope explicitly does not qualify full bus-skew or structural CDC coverage.
- PHY tools `build/checks/runtime-pad-reset-review-preparation-c0184810-20261021-v1`,
  36 guards, generated from this exact compiled source. The old reviewer assumed
  42 buffered paths/37 LUTs from the previous route. That is no longer a new-image
  assumption: all1364 per-mode SERDES reset raw/logical drivers and every inserted
  LUT1's INIT/input chain must reconcile. Nonidentity buffers, omitted driver/node
  data and changed logical sources fail. All2032 timed reset paths and3ns SERDES
  bounds,278 board pins,180 DDR pad connections/nine disabled high-Z lanes and both
  runtime interfaces remain mandatory. The prior exact route is only a parser fixture.
- Native finding collector `build/checks/runtime-waiver-review-preparation-c0184810-20261021-v1`
  and reader `runtime-waiver-scope-reader-c0184810-20261021-v1`,46 guards. All45
  CDC/DRC/methodology reports across original+four modes and all/unwaived/waived
  scopes,30 typed violation-object sets and full exported waiver provenance are
  required. Collection/reconciliation grant no waiver or image approval.
- Numerical owner PID2574965, unit `opentpu-c0184810-routed-numerical-review-20261021-v1.service`,
  `build/checks/runtime-routed-numerical-owner-c0184810-20261021-v1/`.
- PHY owner PID2574967, unit `opentpu-c0184810-routed-phy-review-20261021-v1.service`,
  `build/checks/runtime-routed-phy-owner-c0184810-20261021-v1/`.
- Native finding owner PID2574969, unit `opentpu-c0184810-routed-waiver-review-20261021-v1.service`,
  `build/checks/runtime-routed-waiver-owner-c0184810-20261021-v1/`.
- Scope owner PID2575019, unit `opentpu-c0184810-routed-scope-reconciliation-20261021-v1.service`,
  `build/checks/runtime-routed-scope-reconciliation-owner-c0184810-20261021-v1/`.

The first three owners verify and wait for the exact successful implementation
process to release, then collect its same hashed routed checkpoint immediately.
This read-only collection scheduling no longer waits serially behind unrelated
review scopes. It does not remove any source, numerical, skew, CDC, PHY, finding,
integrity or package gate before generation or hardware. Scope reconciliation
waits for its exact native-fact collector to release. All12 current role job/launch
witnesses are bound by the canonical manifest and selected by the live-status reader.

**Additional current preparation:** generation guards in
`build/checks/runtime-bitstream-generation-preparation-c0184810-20261021-v1/`
passed77 cases. Four new explicit correction gates and strict integer/Boolean
image identity fields are required; the actual c0184810 source fingerprint is
`563139cbf626432aee8d83ec2095b4d674e02f3cd87125d4bacf96b5bf5bcf58`
(source identity, not a bitstream checksum). Exact final source/structural CDC/
provenance and package/execution bindings remain; generation is not admitted.
The two initial fixture failures are preserved: a previous image's expected
source fingerprint and old-ID schema fixture were updated for this exact source;
no numerical limit or approval requirement changed.

Host/native correction binding owner
`build/checks/runtime-c0184810-host-admission-binding-20261021-v1/`, unit
`opentpu-c0184810-host-admission-binding-20261021-v1.service`, waits for the
current source-native owner to release. It will verify all64 actual write-count
CDC sources and all28 expected native pending-command bits, then bind host247,
exact trained reference and source-only device-refusal evidence. It cannot
qualify routing or authorize a device open. Canonical now pins13 current roles.

**Continuation decision audit (user requested):**
`build/checks/runtime-c0184810-continuation-decision-audit-20261021-v1/decision-evidence.json`.
Six actual implementations reached all seven phases with native exit0 and a final
routed checkpoint; summed worker elapsed time19.28hours. This does not mean six
qualified images. Source-only revisions and review-tool repairs explain part of
the additional project time. Latest c0184809 four-mode setup slack is
+0.049/+0.030/+0.011/+0.011ns; timing feasibility is demonstrated under its
constraints, not transferred to source10 or physical behavior.

The exact compiled c0182863 bridge also reproduces both public-interface corner
cases: direct Gray publication0→3 on simultaneous accepts, and six-bit pending
count wrapping at64 then releasing reset with commands queued. Baseline CH1 ready
expressions match the audited source9 functions. These are module simulation and
source/integration evidence, not a new Mac hardware failure; previous physical
Mac LFM/Qwen passes remain valid for those tested runs. Shared correctness fixes
remain useful even if runtime clock switching is later deferred.

Recommendation: finish the already-running source10 implementation/review as a
bounded decision point, then require exact-image hardware evidence before further
promotion. Reassess before another broad reset/clock architecture change. A
fixed-clock backport retaining the full accelerator/4GiB/JTAG+PCIe is an alternative
scope decision, not an admitted replacement. The user has not cancelled source10
or authorized a pause. No additional image was started; current workers continue.

Current canonical: `build/handoffs/runtime-write-accept-successor-current-20261021.json`.
Update it with `build/handoffs/update-c0184810-canonical.py`, which propagates its
witness through the preserved source9/8 lineage. Both the live-status reader and
progress refresh now select source10; a refresh must not restore source9 as an
active test candidate or call the actual admitted queue source preparation only.
Commands: `build/fedora-venv/bin/python -B build/handoffs/runtime-clock-live-status.py`
and `build/fedora-venv/bin/python -B build/handoffs/refresh-dual-interface-progress-20261018.py`.

Next: finish matching final-review preparations while the source and native gates
advance automatically to placement/routing. Immediately review the exact fresh
routed image when it finishes; then integrity/package and already-authorized
exclusive temporary SRAM/four-mode TinyStories. Preserve numerical/CDC/PHY
limits and every native finding/waiver scope. Permanent flash remains a separate
exact-image authorization. c0184809 executor v7 remains stopped before generation;
its frozen source and all native evidence remain historical below. No hardware,
flash, Git staging/commit/push or branch operation occurred; original index preserved.

## Earlier final-review snapshot (superseded by the CDC blocker above)

Verified 2026-10-21 12:02 HKT. **Current task: explicit final technical
finding/waiver disposition.** All offline evidence is collected and reconciled;
no implementation/native report rerun is needed. No c0184809 bitstream, package,
SRAM configuration or flash write exists. Full goal remains active; no pause.

**NEW COMPLETED: exact composite numerical/control/CDC structural review.**
`runtime-composite-final-numerical-owner-c0184809-20261021-v1`, PID 2530066 released,
standard PASS numerical status. Immutable routed reader v4 passed 108 guards.
All 54 active skew groups per mode preserve endpoint sets/budgets and saved
histories after the four exact graph-proven unobservable source groups are
accounted for. All source control bounds, 133 live receiving stages, 256 Gray
paths, reset/CSR/providers and active vendor structures pass. Vendor coverage:
496 original rows = 392 actual reviewed + 104 proven unused; 25 enable sources,
active FIFO minimum native slack2.480ns. Full native composite has119 files;
original failed whole collector remains native_exit1, explicitly recorded.
`runtime-composite-provenance-c0184809-20261021-v1` pins the exact actual producer
job/owner, all seven source/scope receipts and every native file;8 mutation/
actual-producer guards pass. Do not relabel the old failed native collection.

**NEW COMPLETED: actual fast compute hardware-state timing envelope.**
`runtime-c0184809-actual-fast-compute-envelope-20261021-v1/manifest.json`, native0.
Exact current routed copies in modes1/3 use real fractional divider5.375, same
strict6.718ns declared period and extra0.006ns setup uncertainty. Native reports
show **0.095ns** setup uncertainty, setup **+0.030/+0.011ns**, hold **+0.015ns**,
zero setup/hold/pulse/clock coverage failures, complete routing. Canonical DCP
is unchanged. TIMING-1 conservative-boot-divider warnings now have actual-state
native support; no unsupported jitter assumption is needed.
Current actual routed MMCM probe confirms M16/D1, compute divider8, memory
**divider6**, input20ns, consistent with boot mode2(core100/DDR1066). This is
separate from generated IP nominal defaults8/8. Runtime TCK constraint166.666ns;
matching XVC launcher requests6MHz. Native lock sync max/min paths all pass:
min setup6.717ns, hold0.177ns, max data delay0.578ns.

**NEW COMPLETED: all actual native finding/waiver/object scopes.**
Collector `runtime-routed-waiver-owner-c0184809-20261021-v6`, PID2522151 released,
native0, all5 views(original+4 modes). Report inventory v6 PID2532117 completed.
Current scope reconciliation is **v8 PID2544687 released PASS**, using immutable
`runtime-waiver-scope-reader-c0184809-20261021-v3`, **46 guards**. Prior v6/v7
reader failures are preserved: native waived-endpoint auxiliary count table and
inline XDCV report-local reference IDs were unsupported. Corrections preserve
every crossing/object/endpoint/budget; all actual scopes reconcile, including
multibit waived endpoint counts(CDC-6:28 rows/188 endpoints). No native rerun.

**Current final intake v7 PID2544852 released READY.**
`runtime-final-review-intake-c0184809-20261021-v7/run/intake/` holds45 revalidated
report scopes,30 full native object sets, **80,019** explicit all-scope finding
entries. Do not confuse default/unwaived CDC inventory(1,672 per view) with all
crossings: all-scope CDC has14,552 rows per view including12,880 waived rows.
Existing17 user waiver definitions and their valid/ignored source conditions
must be explicitly reviewed. No DRC/methodology waiver is inferred.

**ROOT FINAL TECHNICAL WORK IS STARTED, NOT COMPLETE.**
`runtime-final-technical-disposition-work-c0184809-20261021-v1/`
contains `finding-decisions.partial.json`, `manifest.json` and the actual review
script. **6,763 entries** have scoped offline technical decisions; **73,256**
remain UNREVIEWED and block generation. Accepted, with native object criteria:
DSP pipeline recommendations(DSP48E1 objects), RAM mapping/output-register
recommendations, exact PDCN unusedI1, TIMING-1 actual fast-state envelope, exact
TCK6MHz CKLD scope, exact two PLL synchronizer placement advisories. Hardware
qualification remains pending; these decisions are not blanket rule waivers.

**NEXT ROOT ACTION:** finish final technical decisions from actual object scopes.
Remaining CDC classes are mainly the existing native-memory FIFO waiver flows
(CDC-1/13/15/26), Gray-count CDC-6 and34 unwaived Critical contexts. Source waiver
contracts are in frozen `boards/.../constraints/otpu_mem_ch.tcl` and actual native
`.../native/<view>/{valid,ignored}-waivers.rpt`, `user-waiver-definitions.xdc`:
FIFO RAM heads are sampled only after pointer crossing/not-empty; no overwrite
until return pointer; input arbitration loads qualified byFIFO valid/c_cmd_valid;
u_ar data consumed onlyn_rvalid;u_xr onlyx_rvalid;Gray counts change onebit/source
cycle with actual skew bounds. Inspect exact frozen RTL gate/credit/reset logic,
actual current 54 skew groups and complete native contexts before accepting.
Do not execute exported waiver Tcl or grant a new waiver to silence a finding.
Remaining DRC:130 BUFC-1 entries and5 aggregate RTSTAT-10 entries need exact full
object/source-intent review. Remaining methodology:60 TIMING-54 scoped clock
constraints;70 LUTAR async-reset alerts; TIMING9/11, auto-clock references,
conservative interclock uncertainty, synchronous-pair maxdelay warnings, 10k+
object exception advisory, route guidance, replication original/replica coverage
and intentional clock-constraint overwrite advisories. Do not approve by rule
name alone. Current NUM108/PHY proof and source operating-contract receipts are
available to bind actual affected paths/objects. Preserve all numerical limits.

**Matching executable workflow already prepared/admitted:**
Generation/package/SRAM/JTAG **v3** guards66/19/6/13 plus composite provenance8;
actual package/JTAG self-hash checks pass. Actual executor v7 PID **2548435** is
armed behind exact final disposition, using final intake v7. Three actual
entrypoint source-only/fake-disposition controls passed before generation/USB.
Commands: `runtime-c0184809-execution-preparation-20261021-v4/commands.json`.
Future bit path (NOT generated):
`runtime-qualified-execution-c0184809-20261021-v7/run/generation/otpu.bit`.
Once every final decision is verified, create exact
`runtime-final-disposition-c0184809-20261021-v1/manifest.json`, bind actual six
review roles, approved composite job/native inputs, exact source/host/runtime
gates and released owner hashes. Policy v3 explicitly verifies this composite;
old whole collector remains failed1. Executor will do CRC/package/preflight,
exclusive already-authorized temporary SRAM and four-mode trained TinyStories.
**Permanent c0184809 flash is not authorized.** No extra temporary permission
is needed. Matching Mac source proposal stays local/unapplied/uncommitted;
no generated large artifact commits or archives. Git index remains unchanged.

**COMPLETED: all four corrected global timing/clock-coverage views.** Owner
`runtime-unused-clock-coverage-owner-c0184809-20261021-v3`, PID 2502737 released.
Actual setup WNS by mode 0/1/2/3: **+0.049/+0.030/+0.011/+0.011 ns**. Hold
**+0.015 ns** in every mode, zero setup/hold/pulse failures, complete routing,
zero disconnected/generated-clock coverage errors. All used clock waveforms/
ancestry and original global numerical metrics remain identical. Only four
physically zero-net unused DDR CLKOUT5/6 definitions are omitted, with original
MMCM parameter/waveform observations retained explicitly as metadata. No real
endpoint, numerical limit or timing exception is loosened. Actual constraint
serialization uses half-up decimal rounding (-2.8125 -> -2.813); strict parser
v5 passed 12 controls against every real mode. Completed clean modes 0/1 from
v2 were reused with byte/hash checks; only 2/3 reran. Do not replay these views.

**COMPLETED: exact four-mode routed PHY/pad/reset scope.** Owner
`runtime-routed-phy-owner-c0184809-20261021-v7`, PID 2502739 released. All
**2,032** reset timing paths passed, minimum slack **+0.049 ns**, original 3 ns
SERDES bound unchanged. All 341 logical SERDES reset sources match source;
42 paths include 37 native LUT1 INIT=2'h2 identity buffers inserted by routing.
Resolver verifies only noninverting buffers, records their actual native chains
in every mode and retains all source/pad/clock/placement/timing checks. Fresh
selectors were regenerated from exact current compiled source; 30 guards passed.
Actual board pin map, full accelerator, JTAG USER2 and PCIe x8 scope passed.

Canonical completion witnesses:
- `build/checks/runtime-unused-clock-coverage-owner-c0184809-20261021-v3/run/manifest.json`
- `build/checks/runtime-routed-phy-owner-c0184809-20261021-v7/run/manifest.json`

**CDC/optimization dispositions:** all 34 Critical groups retain the exact clock
pairs, destinations, depths, exceptions and multiplicities. Native source/routed
fanin tables each have 1,852 rows over six changed receivers and differ only by
one proven ordinary state replica with identical C/D/CE/R/INIT. The PDCN-1569
LUT4 INIT=16'hAFAA does not depend on I1 for any of its 16 input assignments;
actual physical I1=A2 mapping confirmed. These scoped technical dispositions are
in `runtime-c0184809-critical-representatives-and-pdcn-disposition-20261021-v1`.

**New rigorous raw-net observability proof:** `runtime-c0184809-removed-vendor-observability-probe-20261021-v1`
traverses actual physical connectivity, LUT INIT Boolean dependencies and
conservative FF/one-bit-memory state dependencies; it does not depend on timing
arc/case exclusions. 140 selected outputs, 807 visited outputs; no unknown
boundary is silently ignored. The initial restricted graph proved 104 payload fields and three skew groups
unobservable. The completed extension below proves all four groups: the two
guard response FFs only feed the closed internal graph. All 36 original
registers of the four skew groups are absent after routing. Source saved skew history plus current rate
bounds has 60 commands / 58 active groups; routed has 56 / 54. Apply only the exact native-proven group dispositions below; preserve the
complete remaining source endpoint sets and budgets.
Do not relax `constraints.reconcile` history, endpoint or numerical gates.
`runtime-c0184809-unobservable-vendor-field-disposition-20261021-v1/manifest.json`.

**COMPLETED: all four removed skew groups are now structurally justified.**
The zero-constant hypothesis was deliberately NOT accepted: native/BDD attempts
remain unproven and are retained. The actual response values can vary, but their
only apparent external destinations were two ordinary PCIe response data FFs.
Extending raw dependency traversal through exactly those FFs produced **809
outputs, zero live boundaries**. The guard FFs feed only the closed internal
feedback graph; no constant-zero assumption was made. All 140 selected FF outputs
(104 payload fields + 36 source/destination FFs of four skew groups) are therefore
unobservable. Exact technical proof:
`runtime-c0184809-unobservable-vendor-field-disposition-20261021-v2/manifest.json`.
No source/RAM/clock/interface change is implied. Preserve original skew budgets
and filter only these four exact source groups with their proof.

**COMPLETED: missing mode-3 metadata tail and explicit vendor inventory.**
`runtime-c0184809-routed-tail-recovery-20261021-v1/manifest.json`, native exit 0.
17 fresh data files include mode3 clock/Gray/divider, provider, control placement/
pins and physical resource/interface facts. Vendor availability records **200
missing pins** (104 read-data FF endpoints and 96 one-bit RAM clock endpoints),
104 missing timing pairs, and all 317 expected receiver/enable targets. Inventory
alone grants no approval; reject any omission outside exact proven scopes.

**COMPLETED: all missing vendor data/clock/path endpoints are explained.**
Expanded raw connectivity proof v3 finished natively: **244 roots, 913 visited
outputs, zero live boundaries**, including all 104 source one-bit RAM data
outputs. Every one of the **200** missing pin records (104 read FF D endpoints,
96 RAM CLK endpoints) and **104** missing timing pairs maps to these exact
unobservable source scopes. No unknown endpoint is omitted and no zero-constant
assumption is needed. Technical receipt:
`runtime-c0184809-removed-vendor-endpoint-disposition-20261021-v3/manifest.json`.
This closes the optimization-removal investigation; it does not replace full
numerical/CDC composition or the final native finding/object dispositions.

**CURRENT final finding/object collection is actually running:**
`runtime-routed-waiver-owner-c0184809-20261021-v6`, PID **2522151**, unit
`opentpu-c0184809-current-final-finding-object-collection-20261021-v6.service`.
It is admitted against the exact successful four-mode global clock/timing and
PHY scopes, and still grants no image approval. It collects all original + four
mode CDC/DRC/methodology reports, all/unwaived/waived scopes, complete typed native
violation objects and waiver provenance (45 report scopes, 30 object sets).
Fresh scope reconciler v6 PID **2523112**, unit
`opentpu-c0184809-current-final-scope-reconciliation-20261021-v6.service`, is armed
behind that exact collector. No source or build restart is required.

The original full collector v5 ended natively at 09:25:16 with missing vendor
payload bit132 after mode3 global reports were written. Modes 0/1/2 markers exist;
mode3 marker does not. **Do not append a marker or claim original native_exit=0.**
All four healthy global report scopes are independently closed and bound in
`runtime-c0184809-four-mode-closed-report-scope-20261021-v1/manifest.json`.
Root `registers.tsv` (31 MB), target/cone tables and some endpoint facts are closed;
mode3 root clock/Gray/divider tails and later provider/physical/control exports
need the separate recovery above. Build a truthful composite final numerical
receipt from closed scopes + fresh tail + completed clean clock/PHY receipts.
Do not replay implementation or completed mode timing to fix reader assumptions.

**Important remaining execution work (in order):**
1. Complete the started final technical disposition:80,019 rows total,6,763
   accepted/73,256 unreviewed in the partial decision file. Preserve raw native
   evidence and exact object sets; resolve every remaining source/operating
   condition. All source/routed/native inventory scopes have completed.
2. Independently revalidate full decisions, waiver provenance, exact composite
   numeric/PHY/source/host bindings and runtime gates; then create the final
   disposition consumed by the already armed executor v7. Do not infer image
   approval from global timing or a rule-name whitelist.
3. Continue through actual reviewed bit/CRC/package, exclusive authorized SRAM
   and exact four-mode trained TinyStories. Inspect live hardware ownership,
   preserve permanent fallback, and keep all hardware outcomes separate.
4. Commit/publish only matching authorized small Mac source/metadata/guide after
   preservation-aware integration; do not commit large bit/DCP/weights/logs.
   New permanent flash requires exact-image authorization after the concrete
   reviewed/SRAM result, hash and command are available. Goal stays active.

Current canonical: `build/handoffs/runtime-global-timing-successor-current-20261021.json`.
Read live owner identities with `build/handoffs/runtime-clock-live-status.py`.
No SRAM/flash or other hardware access occurred. All old evidence and frozen
worker inputs are retained; Git index remains unchanged. No pause request.

**Avoid huge tool output:** generated vendor Tcl contains single lines hundreds
of KB long. Never `head`/`sed` those lines without character bounds; use Python
line length/prefix summaries. Source path includes `boards/.../litedram` while
runtime top source is under `rtl/boards`; verify actual paths before remapping.

Source synthesis/linked collection, all 12 complete RTL cases and current native
control/reset prerequisites passed. No bitstream exists and no hardware was accessed.

Intermediate placement timing: setup -0.425 ns (4478 endpoints), hold -0.648 ns
(4943 endpoints), zero pulse failures. These are before physical optimization/
routing and grant no timing/image qualification. The unchanged build continues
toward strict final routed acceptance. Observation receipt:
`build/checks/runtime-c0184809-placement-timing-observation-20261021-v1/manifest.json`.

Physical optimization completed and routing started 06:38:54 HKT. Closed before-route
report: setup -0.727 ns/TNS -36.541 ns/424 failing endpoints; hold -0.648 ns/
THS -274.462 ns/4848 failing endpoints; zero pulse failures. This is an intermediate
estimate, not routed qualification. All final max/min/coverage gates remain.
`build/checks/runtime-c0184809-pre-route-timing-observation-20261021-v1/manifest.json`.

Configuration remains full 716-DSP accelerator, 4 GiB, CH0 lanes [0,1,2,3,4,5,8,7],
CH1-only ECC, JTAG USER2 plus full PCIe Gen2x8 runtime memory/control, four
100/148.837 MHz x DDR800/1066 modes, boot mode 2 and mode-bound c0172608/c0172668
firmware. Hardware RTL differs from c0184808 only in BUILD_ID. Global placement
uses ExtraTimingOpt; original Explore/tns_cleanup routing and all limits remain.
The original marked two-stage reset synchronizer, ordinary distribution stage
with one additional release cycle and memory-selection MAX_FANOUT=32 are retained.

| Task | What changed | Current evidence / remaining work |
|---|---|---|
| **CURRENT: c0184810 source correction** | Single-step write-count Gray publication; full accelerator / 4 GiB / four modes / JTAG + PCIe retained | Targeted native/AXI and 65,600-write wrap tests passed; reset/constraints and complete-source integration next; build not admitted |
| Source synthesis and linked netlist | Fresh exact current project | PASS; completed 05:16:58 HKT, no synthesis/linked-collection restart |
| Complete source RTL and matching software | Actual accelerator/top and both frontends, modeled vendor/DDR boundaries; current host identity | All 12 RTL cases passed, exact 32-word matmul in every mode; 624,318 reset checks, 7 wiring observations; host 242 cases and 32 trained ISA tokens passed |
| Current native control/reset | Added separately validated ordinary-reset descriptor to complete metadata; unchanged hardware | PASS: 266 owned bits, 48 ordinary distribution replicas, current ACK and all critical/reset cones; 224 current extracted reset checks passed |
| Four-mode source clock review | Exact current Gray baseline; actual slow-memory divider states | PASS: all 4 modes, 64 clocks, 256 scalar Gray paths; actual current9 baseline and memory dividers [8,8,6,6] verified; four-mode intent and context also passed |
| Current source-purpose/vendor review | Fresh current native properties and actual component/full-model evidence; no qualification copied | Current owner v4; PASS: all 1,650 initial source findings and 126 additional findings per mode assigned; current integration and vendor probes passed |
| Additional source, warnings and final source acceptance | Complete additional four-mode inventory; 36 explicit warning rows; actual current-baseline authority | PASS: current warning/intake and final source acceptance v6; all 1,776 findings in each of four modes assigned, zero unassigned, no waivers; routed/physical remains pending |
| Final routed review | Exact routed MMCM states/uncertainty plus all original max/min/Gray/control/CDC gates | Actual full-review v5 running; 100 reader guards passed; 133 live receiving pairs plus one native-proven unused pair accounted for |
| Routed PHY/report/waiver/scope review | Regenerated current-source pad/PHY selectors; complete actual report/object scope | Actual followers armed; PHY 25, report inventory 14 and scope 33 guards passed; all native routed reviews pending |
| Generation/package/SRAM/JTAG preparation | Current host/mode data and mandatory source/clock acceptance before generation | Generation 51, package 19, SRAM 6 and JTAG 13 guards passed; qualified executor armed behind exact final technical disposition; no generation/package/programming started |
| Final technical review and hardware | Explicit disposition of every real finding/object; packet/CRC and package checks before authorized temporary SRAM | Final intake worker armed; technical disposition and physical tests pending; no ready bitstream |

Current canonical (all exact current jobs, service names, launch identities and
hashes): `build/handoffs/runtime-global-timing-successor-current-20261021.json`.
Read live status with:
`PYTHONDONTWRITEBYTECODE=1 build/fedora-venv/bin/python -B build/handoffs/runtime-clock-live-status.py`.
Refresh helper reports actual implementation separately from source review and
calculates completed milestones as started phase markers minus the active phase
(until terminal completion); this is not elapsed progress or remaining time.

Current owners/directories: exact current launch/PID/job bindings are authoritative
in the canonical manifest and live helper; do not resurrect superseded services.
- Completed source synthesis remains v1, native source/reset v2, clock/intent/
  context v2, and initial/additional source-purpose owners v4. Their actual
  successful native evidence is retained without replay.
- Current warning and final source acceptance are v6, under
  `runtime-c0184809-source-post-review-owner-20261021-v6` and
  `runtime-c0184809-source-acceptance-20261021-v6` in `build/checks/`.
- Implementation remains v2, owner PID 2442285. Immediate final-base timing owner
  remains `build/checks/runtime-base-finalization-owner-c0184809-20261021-v2`.
- Full routed/PHY/report/waiver/scope/intake/execution watchers are now v4. Only
  idle dependency watchers were replaced; no native collector or programming
  operation was interrupted and implementation was never restarted.

Review/preparation corrections, with original frozen failures preserved:
1. The frozen original9 source contract correctly owns 266 annotated bits but
   omitted `ordinary_core_reset_distribution`. Preserve it unchanged. A new
   one-field supplement is bound to the exact current source and 224 reset checks,
   then verified against all 48 actual current native replicas. Native source v2
   passed using that supplement, reusing the already successful exact probe.
   `build/checks/runtime-contract-supplement-c0184809-20261021-v1/manifest.json`.
   Original source validation/annotated ownership still uses the frozen base;
   ordinary-distribution review uses the verified supplemental descriptor.
2. Fresh contract emitter now enforces the exact ordinary-reset source pattern
   and emits its descriptor before admission. Actual regeneration produced exactly
   the native-validated supplemental contract:
   `build/checks/runtime-contract-preparer-c0184809-correction-20261021-v1/manifest.json`.
3. A wrong previous-image Gray baseline pointer was corrected before freezing the
   fresh v2 clock reviewer. Its own current9 source baseline is mandatory. No v1
   clock native collection had run, and the unused standalone correction owner
   is retired. No completed current native collection was repeated.
4. Source-only recovery also fixed folder-only references (absolute-path-only
   replacement was insufficient), and removed exactly three prematurely created
   empty output directories. Initial purpose owner v4 reuses its verified guard,
   then passed inventory and the complete initial non-vendor purpose stages.
   Source-only recovery never restarted the running implementation/shared reviews.
   Preserve `runtime-c0184809-review-chain-recovery-20261021-v1` and
   `runtime-c0184809-purpose-reference-recovery-20261021-v1` under `build/checks/`.
5. Corrected clock analysis has 36 warnings: the prior 28 plus exactly 8 named-clock
   overwrites. Fresh warning tools preserve strict native ground-net checks and
   require exact overwrite syntax/counts plus actual current 64-clock/256-Gray/
   four-mode divider proof. Six new negative/positive guards passed. Unknown
   warnings remain failures; no timing/CDC gate or numerical limit was relaxed.

Four-mode active-intent and complete before/after CDC inventory passed. All 1744
preserved records (1,360 original plus 384 ordinary-distribution checks) matched;
all four actual inventories retain every prior finding. This is source-only
evidence; full source-purpose and routed/physical qualification remain pending.

**Current final-review and execution preparation:**

- full_four_mode_routed_review: `build/checks/runtime-routed-finalization-owner-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-full-four-mode-routed-review-20261021-v4.service`, PID 2480702.
- routed_phy_review: `build/checks/runtime-routed-phy-owner-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-routed-phy-review-20261021-v4.service`, PID 2480704.
- routed_report_inventory: `build/checks/runtime-routed-inventory-owner-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-routed-report-inventory-20261021-v4.service`, PID 2480706.
- routed_waiver_review: `build/checks/runtime-routed-waiver-owner-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-routed-waiver-review-20261021-v4.service`, PID 2480709.
- routed_scope_reconciliation: `build/checks/runtime-routed-scope-reconciliation-owner-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-routed-scope-reconciliation-20261021-v4.service`, PID 2480711.
- final_technical_intake: `build/checks/runtime-final-review-intake-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-final-technical-intake-20261021-v4.service`, PID 2480713.
- qualified_execution: `build/checks/runtime-qualified-execution-c0184809-20261021-v4`,
  service `opentpu-c0184809-clock-corrected-qualified-execution-20261021-v4.service`, PID 2480715.

Actual v4 full routed collector uses v2 routed tools and the corrected unused-only
clock helper, retaining every original clock/Gray/control/receiving/recovery/skew/
setup/hold/pulse/route/coverage gate. 86 controls passed. V2 PHY tools regenerated
from current9 source retain every pad/reset/clock/3 ns SERDES limit; 25 controls
passed. Report 14 and scope 33 reader controls remain. Source acceptance v6 and the
released exact base/implementation proofs are mandatory prerequisites.

Actual corrective proof:
`build/checks/runtime-c0184809-unused-ddr-clock-view-api-probe-20261021-v2/manifest.json`.
Corrected helper:
`build/checks/runtime-routed-review-preparation-c0184809-20261021-v2/clocks.tcl`.
All 4 mode native evidence, all 45 finding scopes and 30 complete native object
collections still must close. Final intake publishes UNREVIEWED findings; root
must disposition the actual data before generation. No approval is inferred.

Matching preparations passed generation 51/package 19/SRAM 6/JTAG 13 checks and
three real executor invalid-disposition cases. The actual v4 executor is waiting
for final technical disposition; no generation/FPGA access/flash occurred.
Exact commands/future paths are in:
`build/checks/runtime-c0184809-execution-preparation-20261021-v1/commands.json`.
Current future bit path:
`build/checks/runtime-qualified-execution-c0184809-20261021-v4/run/generation/otpu.bit`.
Full package `bitstreams/spare-runtime-dual-host-4gb-c0184809`, small runtime
`runtime/c0184809`; none is currently a reviewed generated output. Preserve all
native failed/corrected receipts and do not create future output dirs early.

Mac source delivery proposal is prepared without changing public source:
`build/handoffs/c0184809-mac-source-proposal-20261021-v1/manifest.json` and
`matching-host-source.patch` alongside it. Six source/test files total 81,244 bytes;
`git apply --check` passed. Private pytest harness configuration was excluded.
The patch is unapplied, unstaged, uncommitted and unpublished; it contains no
bitstream/checkpoint/model/log archive. Source proof hashes remain unchanged.
After exact image qualification, reconcile/stage only matching ordinary runtime
files/configuration/guide under existing Git authorization. Earlier push request
was answered Keep commit local; do not publish without new authorization.

Read-only local JTAG availability at 06:44 HKT: exactly one initialized DLC10
`03fd:0008` is visible and no conventional cable process was observed. No JTAG
scan, FPGA identity read, lease acquisition or programming was performed. This
does not establish FPGA power/configuration or exclusive hardware ownership;
recheck at the already-authorized reviewed SRAM step.
`build/handoffs/c0184809-local-jtag-availability-20261021-v1/manifest.json`.

Independent current vendor-contract recheck completed during routing:
`build/checks/runtime-c0184809-vendor-contract-doc-recheck-20261021-v1/manifest.json`.
Primary AMD PG247 Clocking/Resets pages (release 2026-06-24) were refreshed. Current
native source has 328 asynchronous converter registers and 0 synchronous-converter
registers on the managed control branch. Source common-reset hold is 16 AON cycles
at 50 MHz (320 ns), with 64-cycle host hold. This matches retained engineering
conditions, not physical qualification. Independent endpoint resets are unsupported;
reset overlap/handshake clamping and physical clock-stop/restart/PCIe recovery
remain explicit conditions. No existing source proof or gate was altered/waived.
Routing is currently in rip-up/reroute global iteration 0; exact owner PID 2442285
and active service were reverified. This routing subphase is not a milestone or
remaining-time estimate. The canonical input hashes/identity remain unchanged.

Current routing timing-difficulty inventory was saved and reconciled against the
already-armed exact PHY selectors:
`build/checks/runtime-c0184809-routing-tight-pin-observation-20261021-v1/manifest.json`.
136 unique pins: 133 internal PCIe userclk1 TX/RX BRAM pins, plus three DDR
serializer reset pins under writeclocks1_outs2:
`u_ld/OSERDESE2_174/RST`, `u_ld/OSERDESE2_175/RST`, `u_ld/OSERDESE2_177/RST`.
All three DDR endpoints already have exact source/target timed_reset_path checks
with the unchanged 3.0 ns SERDES maximum in the current generated PHY review.
The frozen PCIe margin repair remains scheduled after routing/post-route
optimization. This intermediate inventory grants no timing qualification and
requires no source/constraint edit or restart. Final base, all-mode and PHY gates
must independently pass. Actual routing owner PID 2442285 and rising CPU usage
were reverified during rip-up/reroute iteration 0; no worker reported an error.

Routing completed successfully in 64m25s. The exact saved before-postopt report
passed the unchanged strict numerical reader: setup WNS +0.011 ns, TNS 0, zero
setup failures; hold WHS +0.015 ns, THS 0, zero hold failures; zero pulse failures.
The routed-before-postopt checkpoint/report/reader are hashed in:
`build/checks/runtime-c0184809-routed-before-postopt-observation-20261021-v1/manifest.json`.
Planned post-route optimization and PCIe margin step completed; final base report passed. This completed
numerical stage is NOT final image/four-mode/PHY/CDC/artifact approval; all final
gates stay mandatory. No generation, FPGA access, programming or flash occurred.
Implementation owner PID 2442285 released after successful terminal completion; frozen source/job/checkpoint remain unchanged.

Native routed-clock facts are closed under
`build/checks/runtime-c0184809-routed-ddr-clock-pruning-probe-20261021-v1/facts.tsv`.
Outputs 5/6 on both channels have no physical nets/loads; this is not a missing
used clock. The bare automatic-clock rename form cannot create a pruned clock;
that failed API attempt is preserved. The corrected explicit generated-edge
form was tested against the real routed design, preserves all used clocks and
has exact primitive/phase/duty/no-net guards. No numerical limits were relaxed.
Fresh review recovery evidence:
`build/checks/runtime-c0184809-routed-unused-clock-review-recovery-20261021-v1/`.

User-requested Vortex switch: the exact offline CAD service was stopped after
OpenTPU implementation finished. No hardware programmer was active; native
programming was not interrupted. Original interrupted 15 receipt, prior progress,
service/PID identity and outputs remain in the Vortex folder:
`/home/fedora/vortex/build_ypcb_tcu32/opentpu-priority-return-c0184809-20261021/`.
Vortex progress and build-root notice record the coordination request. Interactive
Codex and shell remain open. Recheck exclusive JTAG ownership before authorized
SRAM work; do not infer hardware readiness from USB enumeration alone.

**Next executable work:** let current v4 four-mode routed collection and v4
PHY/finding/object/scope reviews close, inspecting any real tool or timing finding
immediately. Source work and implementation are finished; do not resume/rebuild
them for review fixes. Preserve exact frozen tools, old failures and verified
native output; use fresh corrections when needed. When final intake is ready,
review all actual finding/object decisions and write the exact final disposition.
The qualified v4 executor then performs generation/independent CRC/package/
preflight and already-authorized exclusive temporary SRAM/four-mode TinyStories.
Permanent flash still requires this exact image's checksum/review/SRAM evidence
and the user's exact-image approval; none is granted for c0184809.

The c018480x family has taken roughly two days across source/reset/CDC corrections,
physical implementations and timing experiments; tool/preparation mistakes added
avoidable delay. Latest prior completed layout missed setup by 0.033 ns/eight
endpoints; historical rejected images stay out of the active table. No reliable
remaining-time estimate is supported. No hardware/flash, Git staging/commit/push
or branch change occurred. Original NUL-delimited index snapshot remains identical.

## Historical c0184808 targeted-route snapshot (superseded)

Verified 2026-10-21 03:10 HKT. **Current task: targeted routing of the five original source data
nets covering all eight original setup failures.** Service
`opentpu-c0184808-data-net-reroute-diagnostic-20261021-v1.service`, PID 2419969,
is live. Exact frozen job/worker/launch/receipt:
`build/checks/runtime-data-net-reroute-diagnostic-c0184808-20261021-v1`.

This trial opens the unchanged ORIGINAL full c0184808 checkpoint, not the failed
five-register placement result. It retains every original selected cell location,
logical connection, RTL, clock period/waveform, full accelerator, 4 GiB and both
JTAG/PCIe runtime interfaces. It verifies the original eight-path/five-driver
scope, unique ordinary FDRE Q nets and exact fanouts (36,16,49,9,18), rejects
synchronizers/fixed routing/clock loads, then runs exactly:
`route_design -unroute -nets $selected`;
`route_design -nets $selected -auto_delay`.
This exact command sequence was actually executed successfully for this exact
image's PCIe margin repair. That proves API use, not this new trial's timing.
The current trial changes only those five ordinary data-net routes; no cell
placement, clocks, RTL or numerical limits are edited. Driver plan:
`build/checks/runtime-data-net-reroute-diagnostic-c0184808-20261021-v1/drivers.tsv`.
It saves an unrouted-five-net checkpoint before routing for recovery. All source
logical snapshots, source/end locations, clocks and full resources must match
after routing. Full strict fastest-view/OOB timing, route and coverage remain.
No bitstream can be generated and no image/hardware qualification is granted.

**Next:** immediately inspect complete native warnings/critical warnings and all
strict numerical reports when the trial releases. Require zero failing setup/
hold/pulse endpoints, complete routing and coverage, unchanged clocks/placements/
logical connections/resources/interfaces. A useful diagnostic result still
requires a distinct successor identity and fresh full source/runtime/model/four-
mode CDC/PHY/artifact/package gates before authorized SRAM/TinyStories testing.
Never promote a rejected image or diagnostic, relax a gate, or edit frozen inputs.
If unsuccessful, use the actual remaining failing paths to select the next
measured correction. No successor full-image source/bitstream build is admitted;
no permanent-flash permission exists for a successor.

Completed/dispositioned evidence:
- Original c0184808 completed seven native milestones, then failed exact final
  setup -0.033 ns, TNS -0.120 ns, eight endpoints; hold +0.006 ns, zero hold/pulse
  failures; all 333,712 routable nets complete. Independent numerical review
  confirmed rejection. Later reviews/generation were not admitted; owners released.
  `build/checks/runtime-c0184808-final-timing-rejection-20261021-v1/manifest.json`.
- Original full path/source inventory: eight paths, five ordinary FDRE drivers;
  eight reader guards. Worst driver has nine direct sinks.
  `build/checks/runtime-c0184808-failing-path-inventory-owner-20261021-v1/run/inventory-review.json`.
- Clock_opt/TNS cleanup produced no improvement; original and OOB setup still
  -0.033 ns/eight failures. Clocks/waveforms and outputs unchanged. Disposition:
  `build/checks/runtime-clock-skew-diagnostic-c0184808-20261021-v1/disposition.json`.
- Two equivalent arithmetic proposals passed formal proof for all 98 known-bit
  helper inputs and 262,144 complete footprint cases each; component global/
  product-path deltas +0.118/-0.323 ns and +0.053/-0.267 ns were mixed. Neither
  selected. Dispositions under `runtime-footprint-carry-save-component-20261021-v2`
  and `-v3`. Original package/source remains unchanged.
- Native region/free-site probe collected sixteen endpoints and 312 candidates.
  Both worst paths cross X1Y4 -> X1Y3. Saved-output audit corrected an owner marker
  label mismatch, verified all 617 inputs/closed outputs and original strict path
  reader, with no native rerun or gate change:
  `build/checks/runtime-c0184808-placement-region-reader-recovery-20261021-v1/manifest.json`.
- Five-register move trial: all moves, primitive/INIT/inversion/logical pin checks
  and original clocks/resources passed, but closed setup regressed to -0.696 ns,
  TNS -20.418 ns, 225 endpoints. Hold +0.006 ns passed. Of 30 detailed worst paths,
  28 start at moved al_i[3], plus the two sequencer paths; clock skew improved but
  route delay increased. Geometry alone did not predict a good route. Not selected:
  `build/checks/runtime-placement-diagnostic-c0184808-20261021-v2/disposition.json`.
  The original placement remains untouched. A documented preserve+Explore option
  incompatibility was resolved with an actual successful preserve-only component
  API run (4,188 complete nets); v2 resumed from the retained moved checkpoint,
  repeating neither placement nor original implementation. Failed v1 is preserved.
- Component port-object comparisons were similarly corrected with an actual
  same-checkpoint probe (691 equal names, unequal native handles). Explicit sorted
  name/direction strings matched all ports and the completed baseline was reused.
  Failed tools/receipts remain preserved. Component/OOC evidence is never board/
  interface/DDR/inference qualification.

Canonical lineage:
`build/handoffs/runtime-reset-distribution-correction-current-20261020.json`.
Live-status/refresh helpers select the actual data-net trial. Rejected images stay
out of the active table. All frozen original source/tools/evidence are unchanged.
No bitstream, hardware, flash, commit/push/branch operation. Permanent c0182863 and
fallback artifacts remain; current SRAM identity was not refreshed. Existing
staged work is preserved.

## Historical c0184808 implementation/source state (superseded)

Verified 2026-10-21 01:13 HKT. **Current task: c0184808 full implementation is running,
currently `routed_checkpoint_and_reports`.** 6/7 implementation milestones are complete
(86% on the seven-milestone scale, not an elapsed-time estimate).

The image retains the full 716-DSP accelerator, 4 GiB, spare CH0 lanes
[0,1,2,3,4,5,8,7], CH1-only ECC, JTAG USER2 and full PCIe x8 runtime memory/control,
and all four 100/148.837 MHz x DDR800/1066 modes (boot mode 2). Firmware remains
mode-bound c0172608/c0172668. The correction adds an ordinary reset-distribution
stage after the unchanged marked two-stage synchronizer, with asynchronous
assertion and one additional release cycle. MAX_FANOUT=32 memory-selection/hold
attributes change no memory logic or latency. Original timing/CDC/PHY limits remain.

Completed evidence for this exact source:
- Independent 78-file compiled-source comparison, 224 extracted reset checks,
  fresh vendor project and all 46 source gates passed.
- Complete synthesis and linked-netlist collection passed without implementation
  reuse. All 266 annotated control/provider bits remain explicitly owned.
- Native source and complete critical-cone/reset reviews passed. All 48 ordinary
  FDPE distribution replicas have the expected C/PRE polarity, clock, preset,
  constant D/CE, INIT and AON publication sender. Maximum direct fanout is 65;
  post-placement policy handles residual ordinary outputs above 64, excluding
  every ASYNC_REG synchronizer. Current source has 1,650 non-info CDC rows;
  this inventory is not full CDC qualification.
- All four exact source clock/Gray views passed (64 clocks, 256 scalar Gray paths).
- Full actual source/top/accelerator and both frontends passed all 12 connected
  traffic cases, including exact 32-word matmul in every mode, 624,318 reset
  checks and seven consumer-wiring observations. Vendor clock/fabric/DDR/PHY
  boundaries are explicitly modeled and remain separate physical gates.
- Matching private host passed 237 software cases and source-only transport
  refusals. Fresh TinyStories reference passed 32 ISA tokens through modes
  0,1,3,2; image 28,909,056 bytes, SHA256
  74facccd6c0e3f7e76676617a3b7a4074c1efb784d675ac1b5bdb08dca980950.

**Actual implementation owner:**
- Root `build/fedora-vivado/runtime-implementation-c0184808-20261020-v2`.
- Service `opentpu-c0184808-place-route-20261020-v2.service`, PID 2350230.
- Job SHA256 33cb50c9c6f29d201dd3d4bb4496a3af900360605c50e295193238fbe0972743.
- Exact launch/start ticks/native command are in `launch.json` and `run/manifest.json`.
- The worker waited for exact successful source/reset gates, copied the unchanged
  linked checkpoint, passed native resource/interface/clock/pin/control and ordinary
  distribution recovery/removal intake, then started actual opt/place/route.
- Source reviewers run concurrently. This admission permits placement/routing only;
  generation, package and hardware require every remaining final gate.

**Current reviewers / exact folders under `build/checks/`:**
- Completed `runtime-reset-distribution-source-owner-c0184808-20261020-v2`.
- Completed `runtime-c0184808-reset-cones-owner-20261020-v2`.
- Completed `runtime-full-static-views-c0184808-20261020-v2` (owner-job/owner-run).
- Completed `runtime-control-intent-current-c0184808-20261020-v3`;
  service `opentpu-c0184808-control-intent-20261020-v3.service`, PID 2350101.
  It retains 44 bounds, 24 reset cuts, eight LOCKED cuts, 134 interstage edges and
  adds explicit before/after preservation of every ordinary distribution PRE path.
- Completed `runtime-control-cdc-context-c0184808-preparation-20261020-v2`, PID 2350103.
- Completed `runtime-c0184808-source-purpose-owner-20261020-v3`, PID 2365526; all 1,650 initial source purposes assigned.
  Inventory/selected/reset/drain and fresh host/PCIe/core-reset purposes passed;
  remaining native vendor probes and complete ledger follow four-mode context.
- Waiting `runtime-routed-finalization-owner-c0184808-20261020-v1`, PID 2352144;
  exact start identity is in `launch.json`. Its service is
  `opentpu-c0184808-numerical-20261020-v1.service`. The exact owner is admitted,
  with 106 reader guards passed. On implementation release it immediately checks
  base numerical timing, then all four routed views, including ordinary distribution
  topology/effective polarity and every recovery/removal path. Other PHY/findings/
  object-scope/integrity/package gates have their own admitted followers below.

Two review-tool issues were preserved and corrected in fresh tools: empty FDPE
cell polarity fields were resolved using native C/PRE pin IS_INVERTED=0 on every
replica; whole-top component comparison now allows only the exact already tested
reset-distribution block and identity delta, with every other byte unchanged.
The source synthesis was not restarted. Earlier stopped follower/implementation
receipts and frozen tools remain immutable; current owners above supersede them.
Recovery/preparation scripts and evidence:
`build/checks/runtime-c0184808-followup-preparation-20261020-v1`.

**Additional preparation and admitted followers (this continuation):**
- Four-mode additional CSR/native source-purpose closure is admitted behind the
  current initial vendor-purpose owner. Current selectors must match every actual
  mode; prior-image qualification is never imported.
- Current 28-warning/native-constant review is scheduled behind source closure.
  It reuses the completed same-image native implementation intake rather than
  starting a duplicate placement/routing job.
- Exact routed PHY tools regenerated from c0184808 provider source passed 25
  guards; complete report and scope/object readers passed 14 and 33 guards.
- Generation/package/SRAM/JTAG workflow tools passed 43/19/6/13 checks. Together
  the seven final-tool groups passed 153 guards; all seven Tcl files are complete
  and the matching XVC dry run passed without opening hardware.
- Generation now requires every ordinary distribution replica's routed topology
  and recovery/removal proof. Generation/package/host metadata require exactly one
  extra release cycle as an integer, rejecting bool/float substitutes.
- Independent sha256sum verified all 551 immutable source/project inputs. Complete
  source fingerprint (not a bitstream hash):
  7d884ba0022b1de1b5c6fed4d3b62dc467a3267236e82d4c7c27703cb60f4ccd.
- Qualified execution has three additional boundary guards: source-only metadata
  waits without launching anything; fake approval and failed upstream evidence are
  rejected before generation or hardware access.

New current owners, all under `build/checks/` with exact job/launch/receipt files:
- `runtime-c0184808-additional-purpose-owner-20261020-v2`, PID 2365532;
  service `opentpu-c0184808-additional-purpose-20261020-v2.service`.
- `runtime-c0184808-source-post-review-owner-20261020-v2`, PID 2365534;
  service `opentpu-c0184808-source-warning-20261020-v2.service`.
- `runtime-routed-phy-owner-c0184808-20261020-v1`, PID 2356463.
- `runtime-routed-inventory-owner-c0184808-20261020-v1`, PID 2356623.
- `runtime-routed-waiver-owner-c0184808-20261020-v1`, PID 2356626.
- `runtime-routed-scope-reconciliation-owner-c0184808-20261020-v1`, PID 2356628.
- `runtime-final-review-intake-c0184808-20261020-v2`, PID 2365536.
- `runtime-qualified-execution-owner-c0184808-20261020-v2`, PID 2365538;
  service `opentpu-c0184808-qualified-execution-20261020-v2.service`.
  It waits for exact explicit final technical disposition, then independently
  validates it before generation, package, loader preflight and already authorized
  exclusive local-JTAG SRAM/four-mode TinyStories execution. Permanent flash is
  excluded. It waits for a free initialized DLC10 and preserves other owners.

**Latest completed work:**
- All current source/control/vendor/CSR/constant-warning reviews passed. Each of
  the four actual post-intent source reports has 1,776/1,776 conditionally assigned
  findings, with zero unassigned rows (7,104 records total). This remains source
  qualification; final routed/physical checks are separate.
- Independent literal-table audit reconciled 1,744 unchanged source timing records
  and all 44 active inbound bounds in each mode.
- The payload protocol reader had stale clock/traffic evidence paths. Fresh v3
  tools bind the completed v2 clock view, exact current 42-file model and a measured
  78-file source-integration proof. The successful native vendor facts were reused;
  neither synthesis nor implementation was restarted. All failed/frozen owners
  remain preserved. Recovery: `build/checks/runtime-c0184808-protocol-reader-recovery-20261020-v1`.
- Native SmartConnect audit found 328 actual asynchronous-converter registers and
  no synchronous converter on the managed compute branch. Clock metadata is
  148,837,209 Hz; the source reset stretcher holds at least 16 AON cycles. AMD PG247
  clock/reset requirements were checked; analog pulse/clock-stop/PCIe recovery
  remain physical conditions. Receipt:
  `build/checks/runtime-c0184808-vendor-contract-audit-20261020-v1/manifest.json`.
- The matching ordinary Mac code export has 83 files / 1,656,735 bytes. Its relocated
  user-facing launcher reproduced all 32 ISA tokens and the exact initial-image
  hash on Fedora. Actual macOS execution is not tested. Guide/inventory:
  `build/checks/runtime-c0184808-mac-source-preparation-20261020-v1`.
  Source remains local, uncommitted and unpublished; no archives or large artifacts.

**Next executable work:**
1. Monitor actual routing; source reviews are complete. The immediate numerical,
   four-mode routed, PHY, full finding/object and final-intake followers are admitted.
2. As soon as exact final intake is ready, root must immediately review and disposition
   every actual finding/waiver/object. Do not leave this pending for unrelated work.
3. Write final approval only if every raw evidence and gate passes. Its required input
   is `build/checks/runtime-final-disposition-c0184808-20261020-v1/manifest.json`.
   The qualified v2 pipeline then generates, packages and performs the already
   authorized exclusive local-JTAG SRAM/four-mode TinyStories workflow. It excludes
   permanent flash and waits for a free initialized local DLC10.
4. Future bitstream (does not exist yet):
   `build/checks/runtime-qualified-execution-owner-c0184808-20261020-v2/run/generation/otpu.bit`.
   Future full package: `bitstreams/spare-runtime-dual-host-4gb-c0184808`;
   future small Mac runtime: `runtime/c0184808`. Matching code must be delivered in
   ordinary scoped Git files; keep source outside the runtime's hashed inventory.
5. A reader failure requires a fresh corrected reader and preserved receipt. Reuse
   completed synthesis/routing when unchanged. A real negative routed result rejects
   the exact image and requires a measured correction without weakening limits.
6. If qualified execution waits for Vortex, inspect and perform the user's authorized
   sibling stop/handback, finishing atomic programming first and keeping Vortex
   evidence there. Missing/uninitialized JTAG is a technical prerequisite.
7. Exact-image permanent approval and Mac PCIe/LFM acceptance remain separate.
   No c0184808 bitstream or physical qualification exists yet.

Preparation/evidence roots:
`build/checks/runtime-c0184808-remaining-review-preparation-20261020-v1`,
`build/checks/runtime-c0184808-protocol-reader-recovery-20261020-v1`.

Canonical: `build/handoffs/runtime-reset-distribution-correction-current-20261020.json`.
Root: `build/handoffs/runtime-full-top-preparation-current-20261018.json`.
Live verifier: `build/handoffs/runtime-clock-live-status.py` (checks exact tickets/PIDs).
Refresh: `build/handoffs/refresh-dual-interface-progress-20261018.py` (active table only).
No image RTL changes, Git staging/commit/push, branch operation, hardware access
or flash programming occurred during this continuation. The existing Git index
is preserved. Basic examples remain local/uncommitted: 14 ISA cases and 24 software
checks passed; see `examples/README.md`; RTL/physical examples remain pending.

## Historical c0184807 implementation observations (superseded)


Verified 2026-10-20 20:38 HKT. **Current task: c0184807 final checkpoint/reports are running; PCIe repair attempt was not retained.**
The user explicitly requested: "can u start/queue placement/routing". Implementation
v4 is admitted and running under its own persistent service. All current source
reviews have now passed independently of placement/routing.
Its current native operation is `routed_checkpoint_and_reports`;
6/7 implementation milestones are complete: optimization, placement/report,
physical optimization/report, routing/report, post-route optimization/report and
the PCIe repair decision. Completing a repair attempt does not establish timing success.
The seven milestones are optimization, placement/report, physical optimization,
routing, post-route optimization, PCIe clock-margin repair and final reports.
These counts are completed milestones, not an ETA.

Actual implementation:
- Root: `build/fedora-vivado/runtime-implementation-c0184807-20261020-v4`.
- Service: `opentpu-c0184807-place-route-20261020-v4.service`.
- Exact admission/job/launch/run receipts are in that root. It first validates the
  same source checkpoint, 716 DSPs, 278 board ports, JTAG USER2/PCIe x8, clocks,
  active input bounds and all 36 ordinary targets before `opt_design`.
- Memory reserve remains 11 GiB; service high/max are 14/16 GiB, swap max 4 GiB.
- Source synthesis, RTL, clocks, firmware, lane/ECC mapping and the selected
  physical policy were not changed. The extra native target property checks are
  preserved; an authored Tcl list-format issue was caught before optimization,
  corrected in fresh v4, and evaluated by real Tcl to contain exactly 32 measured
  targets. The superseded v3 receipt/output is preserved; no placed work was lost.

The four-mode source intent audit completed all four modes and all 1,360 path
preservation checks. The complete initial 1,650-finding source purpose ledger also
passed. Additional CSR/all-mode closure and the source warning/native-intake audit
have passed independently of placement/routing. Their existing numerical/endpoint/coverage
limits remain unchanged. Source post-review service:
`opentpu-c0184807-source-post-review-20261020-v3.service`.

All final followers are rebound to the actual v4 implementation:
- Numerical: `runtime-routed-finalization-owner-c0184807-20261020-v3`.
- PHY, report inventory, waiver/object facts, scope reconciliation: matching
  `runtime-routed-*-owner-c0184807-20261020-v3` directories and services.
- Final intake: `runtime-final-review-intake-c0184807-20261020-v2`; its required
  producers explicitly include the complete source audit, all source purposes,
  and independent source warning/native-intake review, as well as actual routed
  reviews. Concurrent execution grants no generation or hardware qualification.

The old serial-admission scheduler and waiting followers were verified idle and
superseded without touching the active source-review chain or other projects.
Their frozen jobs/receipts remain historical. Do not start a duplicate v2 build.
The persistent v2 source recovery after the host OOM/tool-session interruption is
preserved. Source/static/model/host proofs, 98 routed-reader guards and 140 delivery
-tool guards remain separate from actual routed qualification.

Configuration: c0184807; full 716-DSP accelerator; 4 GiB; CH0 lanes
[0,1,2,3,4,5,8,7]; CH1 ECC only; JTAG USER2 runtime memory/control plus PCIe Gen2 x8;
four 100/148.837 MHz x DDR800/1066 modes, boot mode 2; both-channel mode-bound
c0172608/c0172668 firmware. Source DCP SHA256:
838936f0eb10516f1cb48960ce7f5b2a54f0ad358753c7dac644460ff89621ec.
There is no generated/qualified runtime bitstream yet; physical timing improvement
and physical runtime transitions remain unproven.

Canonical: `build/handoffs/runtime-fanout-correction-current-20261020.json`.
Root: `build/handoffs/runtime-full-top-preparation-current-20261018.json`.
Bounded live check: `build/handoffs/runtime-clock-live-status.py`.

Next: track actual native optimization/placement/routing milestones, and immediately
execute the exact numerical/PHY/findings/
waiver/object final disposition. Then generate, verify CRC/integrity, package and
perform already authorized exclusive SRAM/four-mode TinyStories acceptance.
Every final source/routed/package/hardware gate is retained. Permanent flash still
requires approval for this exact image. No hardware programming, Git staging,
commit, push or branch creation occurred.

While implementation runs, the requested `examples/` folder is prepared in the
style of `~/rk3588/examples`: add/elementwise, int8 GEMM, host-lowered convolution
and pooling, softmax and RMSNorm, plus `run_all.py` and `README.md`. All 14 default
ISA cases and 24 software checks passed. Evidence:
`build/checks/basic-operation-examples-20261020-v1/manifest.json` and
`build/examples/basic-ops-20261020-v1/summary.json`. RTL and physical execution
are separate and pending. These new files are local and uncommitted; the existing
Git index is preserved.

Matching c0184807 host/compiler sources also passed all 14 operation examples;
emitted programs, initial images and outputs match the main checkout byte for
byte. Exact source and artifact bindings:
`build/checks/basic-operation-examples-c0184807-binding-20261020-v1/manifest.json`.
The matching-source continuation passed before placement finished. At 18:24 HKT,
the existing implementation owner is live in physical optimization. The placed
checkpoint/report are closed; intermediate setup is -0.734 ns and hold -0.557 ns.
These negative estimates precede physical optimization/routing and do not qualify
or finally reject the image. Exact evidence:
`build/checks/runtime-c0184807-placed-timing-observation-20261020-v1/manifest.json`.
Final routed review, generation and hardware qualification remain pending.

At 18:56 HKT, routing is active. The general and selected physical optimization
passes completed; all 36 exact selected ordinary compute nets were optimized,
adding 246 instances. The targeted pass had zero warnings/critical warnings/errors.
The closed global pre-route report measures setup -0.519 ns (1,102 failing
endpoints) and hold -0.557 ns (4,933 failing endpoints). Internal optimizer
zero-slack estimates do not replace these report values. Routing, post-route
optimization, PCIe repair and exact final review must still pass.
Evidence: `build/checks/runtime-c0184807-pre-route-timing-observation-20261020-v3/manifest.json`.
Observation v1/v2 receipts preserve read-scope/parser failures; they were not
implementation failures. V3 binds only the executed selected-net pass, handles
Vivado's separate runtime-marker wording and rejects duplicate native events.
No frozen worker, source, clock, qualification gate or hardware state was changed.

At 20:02 HKT, routing and the closed before-postopt report are complete, and the
same native worker has entered post-route physical optimization. The closed report
has setup -0.161 ns / TNS -6.847 ns / 154 failing setup endpoints, hold +0.015 ns /
zero failing hold endpoints, and zero failing pulse-width endpoints. The router's
timing Critical Warning is preserved and has not been waived. This remains an
intermediate setup failure: post-route optimization, PCIe margin repair and exact
final numerical/CDC/PHY/findings/object review are still required before generation.
Evidence: `build/checks/runtime-c0184807-routing-completion-observation-20261020-v1/manifest.json`.
Before-postopt DCP SHA256:
2fb0df51106e3410e7189be7d79c4143d133967e50381cf5dea57b286a883ae4.
Bounded live wait observations between milestones are preserved in
`build/handoffs/runtime-c0184807-verified-waits-20261020.jsonl`. These verified live
waits are not a blocked goal or a stopped build. No bitstream/hardware qualification
is claimed, and no hardware, flash, Git index, commit or push was changed.

At 20:14 HKT, the closed after-postopt report confirms setup -0.077 ns / TNS
-4.057 ns / 119 failing setup endpoints; hold +0.007 ns with zero hold failures;
and zero pulse-width failures. The post-route pass completed with zero warnings,
critical warnings and errors. The exact six-net PCIe userclk1 repair is active.
Compute setup is still unqualified; only the final closed report and exact
numerical review can establish its disposition. Evidence:
`build/checks/runtime-c0184807-postopt-completion-observation-20261020-v1/manifest.json`.
After-postopt DCP SHA256:
f928c089e9366ca4417c27fb835f2d56362e80bbee09e893c66071d7ccfb13b8.

The exact c0184807 read-only failing-path collector/reader is prepared under
`build/checks/runtime-c0184807-failing-path-inventory-preparation-20261020-v1`.
Eight reader guards passed; Tcl completeness passed without native execution.
The positive native fixture is predecessor evidence for reader validation only,
and an empty inventory against the current 119-failure intermediate report is
rejected. This is source preparation, not an admitted native collection or build.
If final numerical review rejects c0184807, bind its released owners, final
checkpoint/report and exact rejection before immediately collecting every failing
endpoint/source. If final timing passes, leave this diagnostic unused.

At 20:38 HKT, the PCIe attempt is closed and was **not retained**: userclk1 improved
-0.044 -> +0.050 ns, but other-clock setup worsened -0.077 -> -0.098 ns; hold stayed
+0.007 ns, and no selected nets were unrouted. The unchanged non-regression rule
reopened `run/pre_userclk1.dcp` (SHA256
c50d97eb93ba3b54781f1102f0c5b6b332365fdc4875ac31bd49e658beb69cea).
The same native worker is writing the final checkpoint and complete reports.
Evidence: `build/checks/runtime-c0184807-pcie-repair-disposition-observation-20261020-v1/manifest.json`.
Wait for exact native completion and immediate numerical disposition. If final
setup remains negative, reject this exact image and admit the prepared read-only
complete failing-endpoint/source inventory after upstream owners release. Keep
all exact source, configuration, interface, numerical, CDC, PHY and package gates.

## 1. Current todo progress

| Priority / task | Compute / DDR | What changed / purpose | Build completion | Current result / next action |
| --- | --- | --- | --- | --- |
| **CURRENT: timing-path correction** | All four operating modes retained | Preserve full accelerator, 4 GiB and JTAG+PCIe; inspect complete host/compute/reset path families before selecting source/constraint changes | PASS_C0184811_ALL_ORIGINAL_FAILING_PATHS_COLLECTED_CORRECTION_REQUIRED; no new full implementation admitted | Verify a real correction before successor placement/routing; final review, packaging and hardware tests remain |
| Timing-correction component prototype | Same interfaces, capacity, operating clocks and enabled-cycle latency | Local hazard-counter next-state updates; separate same-cycle stream Y/Q result registers | Isolated component source only; no successor full image identity or P&R admission | Host/reset and remaining compute paths still require correction; whole-image timing improvement is unproven |
| Corrected-component functional verification | Actual modified RTL; original ISA outputs and enabled-cycle schedule | All-state proof of current64-bucket/six-bit hazard update; complete native-memory and stream/VOP regressions | Formal equivalence PASS; all15 real RTL cases PASS | Component behavior only; runtime interfaces, DDR and new whole-image timing remain unqualified |
| Native register/control equivalence | Actual mapped VPU netlist and native pin/primitive graph | Distinct result copies, configured state/polarity, clock/reset, replicated enable logic and data ownership | All256 result pairs proved;266 initialized register relations and one LUT relation;12 reader controls PASS | Original name-only check preserved as a tool failure; native equivalence does not establish placement/routing timing |
| **4: corrected automatic startup c0182663** | 148.837 MHz / DDR1066 | JTAG/PCIe, automatic eight-/nine-lane startup and qualified quantizer predicate timing cut | 100% exact review/package; local JTAG acceptance and result audits passed | Local JTAG acceptance complete; native read 4.452521 GB/s; selected Mac LFM/PCIe and repeatability pending; permanent program/verify/boot prepared, exact-image authorization pending |
| Qualified automatic-startup candidate `c0182600` | 100 MHz / DDR800 | JTAG/PCIe; repaired CH0 pipeline; both-channel embedded calibration | 100%: exact review/package; SRAM/TinyStories and live public runtime passed | c0182600 SRAM/startup/TinyStories and public-runtime postflight passed; native read 2.991732 GB/s; JTAG released; Mac LFM/PCIe and repeatability pending |
| **1: Mac startup time** | c0182863 | Existing FPGA BIST already zeroes/verifies memory; fixed host pauses dominate startup | Measured 450.4 s baseline; opt-in pacing source and 56 tests passed; 200 ms default unchanged | Publish only on authorization, then compare full same-image default versus explicit 20 ms Mac LFM receipts; retain all verification and failed evidence |
| **2: Mac wall decode** | c0182863 | New matched workload: device decode/bandwidth +33.7%, wall decode -8.0% | Optional benchmark timing instrumentation prepared; 12 profiler/backend tests passed (68 combined); physical cause remains unisolated | Run the same Mac benchmark with --profile-host after fresh same-boot calibration/initialization, then inspect transfers, verification/loading, polling and compile/future waits without disabling checks |
| **3: Current-image repeatability** | c0182863 | Current image passed LFM230M and Qwen with exact ISA/program checks | Cold/warm repeatability remains pending | Repeat exact workload and preserve per-run evidence; keep c0182800 fallback artifacts |
| Exact XDMA completion mapping | Full vendor simulation | Actual selected Gen2 x8 XDMA model; source and behavioral-boundary checks remain distinct | Installed simulator permits 50000 instances; exact model needs 467267 | Full encrypted-model completion injection remains license-blocked; no full vendor simulation pass claimed |
| Completed CH0/LFM baseline `c0182800` | 100.000 MHz / DDR800.000 | Shared CH0 response bus, registered reset, combined JTAG/PCIe; 100 MHz baseline | 100%: Mac Chestnut LFM230M and Qwen3.5-2B passed; published results pulled; cold/warm repeatability and matched A/B pending | Original Mac LFM230M and Qwen3.5-2B passed; preserve working baseline; cold/warm repeatability and matched comparison remain pending |
| Current Mac baseline `c0182863` | 148.837 MHz / DDR1066.667 | Registered quantizer nonzero predicate; shared CH0 response bus, registered reset and JTAG/PCIe retained | 100%: Mac Chestnut LFM230M and Qwen3.5-2B passed; exact ISA tokens and programs; cold/warm repeatability pending | Mac LFM230M/Qwen3.5-2B passed; Qwen 15.383497 GB/s, 7.732011 device tok/s, 0.566775 wall tok/s. Cold/warm repeats and wall-regression diagnosis pending |
| Optional reference `c0182461` | 100.000 MHz / DDR1066.667 | Shared CH0 response bus, registered reset, JTAG/PCIe; 100 MHz compute / DDR1066.667 | 100%: Local JTAG TinyStories and native-read benchmark passed; original Mac LFM/PCIe acceptance pending | Keep offline/JTAG-qualified reference; no immediate Mac promotion. Use only if a selected controlled DDR/compute comparison requires it |
| Candidate native read benchmark | c0182461 / c0182863 | Same three 64 MiB native streams; completed exact-image integration is required before replacing program/output memory | c0182461 3.033203 GB/s; c0182863 4.452533 GB/s | Both exact-image benchmarks passed; original Mac LFM/PCIe acceptance and matched single-channel comparison remain pending |
| TinyStories JTAG validation | c0182800 | Trained 15M model padded to the existing tiles; 28,909,056-byte int8 image | PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS; 28,909,056/28,909,056 bytes uploaded | All image bytes and 15 program readback/load checks exact; eight ISA tokens matched; calibration unchanged |
| Native read benchmark | c0182800 | Three 64 MiB native LD streams; FPGA cycle/beat counters and final 16 KiB comparisons | PASS_OBSERVED_NATIVE_READ_BANDWIDTH_FULL_SYSTEM_QUALIFICATION_PENDING | Median 2.991651 GB/s; synthetic combined-channel result, Mac PCIe bandwidth remains pending |
| Matched one-/two-channel performance | Qwen3.5-2B INT8 | Measured current dual-channel versus prior CH1 run; cache/residency/step counts differ | Observed 1.885x bandwidth, 1.884x device decode and 1.168x wall decode; 32 tokens match prior prefix | Controlled A/B still pending; separate measured runs do not establish a general speedup |
| Original LFM230M / Mac acceptance | c0182800 | Original CH0 regression tested through Chestnut on the flashed image | PASS: eight exact ISA tokens; 14 exact program readbacks; calibration unchanged and ECC clean | Cold/warm repeatability and broader payload qualification remain pending |
| Matching Mac Git handoff | c0182800 | Original 24-file handoff published; Mac results and benchmark tools published in successor | Existing branch fast-forwarded to 00a277ac; local staged/working changes preserved | Published and pulled; backup and conflict resolution receipt retained |
| Vortex hardware return | Recorded handback | Sibling work stopped for the selected OpenTPU tests; preserve permanent flash | c0182600 local tests completed and JTAG released | Recheck exclusive hardware ownership before the next SRAM operation |
| Early DDR write-clock VCO gate | Source preparation check | Read exact generated MMCM settings and core profile; reject device VCO violations before core generation or implementation | Sixteen regressions, four saved-core controls and normal valid/invalid generation passed; ordinary/mixed full-image preparer and frozen-worker checks passed | Source VCO gate only; full primitive/DRP, numerical timing and physical DDR review remain required; no new image admitted |
| Matching Mac Git handoff c0182863 | c0182863 | Small exact-image runtime, DDR1066 firmware binding, mandatory program readback and portable instructions | 20 files / 162,405 bytes; normal Git-checkout preflight and corruption/identity checks passed | Commit 4fe69e9a on existing ypcb/dual-channel-4gb; observed on origin; no push by this session |
| Permanent flash c0182863 | c0182863 | Existing BPI16 MCS checked against exact bitstream and completed 40-gate SRAM receipt; native program/verify/boot workflow | Program, independent verify, flash boot INIT/DONE and live USER2 identity passed; JTAG released | Permanent contents unchanged; card now on Fedora for temporary c0182600 SRAM test; prior Mac LFM/Qwen passed |
| Mac flash guide update | c0182863 | Exact MCS checksum, JTAG/Vivado program, separate verify, boot and Mac identity steps; Chestnut-only limitation explicit | Two-file commit f432e10 on existing branch; runtime payloads unchanged | Observed on origin; Mac can pull the guide update; no push by this session |
| Requested LFM repeat | c0182863 current Mac image | Published exact-image Chestnut result imported and audited against Git source and image bindings | PASS: eight ISA tokens, 14 exact program readbacks; all 2,048 initialization chunks validated | Physical result from Mac; raw receipts remain there; cold/warm repeatability pending |
| Current Mac performance comparison | c0182863 versus c0182800 | Same Qwen checkpoint, allocation, settings and all 32 benchmark tokens; faster compute/DDR and quantizer correction change together | Device decode/bandwidth +33.7%; wall prefill +7.6%; wall decode -8.0% in one pass | Host conditions uncontrolled; diagnose wall overhead and repeat before attributing causes |
| Current: initialization latency | c0182863; host update only | Existing FPGA zero/write verification; 2,048 fixed 200 ms pauses total 409.6 s. Add durable chunk progress and failure evidence | Four-file commit cd6562a; clean checkout: 22 tests and preflight passed | Observed on origin; Mac can pull; no push by this session. Faster pacing and automatic full-memory startup remain unqualified; calibration-only candidates do not remove these pauses |
| Original lane 6 / CH0 ECC | Diagnostic history | Deferred behind usable spare-lane integration | Deferred last | No new standalone RAM soak |
| Matching Mac runtime c0182600 | c0182600 | Automatic startup observer and exact runtime bindings; no large artifacts required | 20 source/config/guide files; 199757 bytes; 37 software checks and live JTAG identity/startup/ECC passed | Local uncommitted files; Mac pull cannot retrieve them yet. Mac LFM/PCIe acceptance pending |
| Optional permanent preparation c0182600 | Reviewed SRAM-qualified fallback | Existing 36,364,976-byte BPI16 MCS checked against exact reviewed bitstream and completed SRAM receipt | Byte roundtrip and complete no-hardware flash preflight passed; command prepared | Not selected, authorized or executed for permanent flash; current c0182863 flash unchanged |
| Basic operation examples | ISA simulator; optional RTL/reviewed runtime adapter | Standalone add/elementwise, int8 GEMM, lowered convolution/pooling, softmax and RMSNorm; commands and durable results | 14 fresh c0184811-source ISA cases PASS with exact bound programs/images/outputs; 24 unchanged software checks passed | examples/README.md; generated evidence stays under build/; RTL and physical execution pending |

## Historical snapshot: c0184806 before final numerical rejection

This superseded snapshot preserves the earlier source, worker and review locations.
Use the current state and todo table above.

Snapshot verified 2026-10-20 13:51 HKT. **c0184806 full implementation is admitted and running**
under `build/fedora-vivado/runtime-implementation-c0184806-20261020-v1`, unified
session 14119. Current operation: `routed_checkpoint_and_reports`; 6/7 completed operation milestones.
The scale is opt, place, physical optimization, route, post-route optimization,
PCIe clock-margin repair and final checkpoint/reports; counts are not an ETA.
No c0184806 bitstream exists and no programmable runtime image is qualified yet.

Canonical state: `build/handoffs/runtime-command-distribution-correction-current-20261020.json`.
Root: `build/handoffs/runtime-full-top-preparation-current-20261018.json`.
Admission: `build/fedora-vivado/runtime-implementation-c0184806-20261020-v1/admission.json`.
Admission checked 370 inputs; the worker pins those plus the admission receipt (371 inputs). Verify launch PID/start ticks/invocation and the
latest atomic receipt rather than old RUNNING text before acting. Never edit
any pinned tool or input while a worker is active.

Image scope is unchanged: complete accelerator (716 DSPs), 4 GiB,
CH0 physical lanes [0,1,2,3,4,5,8,7], ECC on CH1 only, JTAG USER2 and PCIe x8,
four 100/148.837 MHz × DDR800/1066 modes, boot mode 2 and mode-bound firmware
c0172608/c0172668. The selected correction replicates four measured ordinary
compute drivers before routing; no synchronizer/CDC register is targeted.
Its policy selection does not assert positive timing. Every exact c0184806
all-mode numerical, CDC, PHY, DRC/waiver, source/identity, packet/CRC and package
gate remains mandatory before temporary SRAM execution.

Placed checkpoint and intermediate report are now complete. Placed setup is
-0.730 ns and hold -0.544 ns; these are estimates before physical optimization
and routing, not final numerical disposition. Evidence:
`build/checks/runtime-c0184806-placed-timing-observation-20261020-v1/manifest.json`.

Physical optimization and selected four-net replication are complete. The optimized
checkpoint is saved; four nets were optimized and ten cells added with no native
warnings/errors. These are before-route observations; that report was negative
(setup -0.785 ns, hold -0.318 ns), so no numerical/image qualification is claimed.
Evidence: `build/checks/runtime-c0184806-pre-route-timing-observation-20261020-v1/manifest.json`.

Implementation status checked 2026-10-20 13:51 HKT: routing, post-route optimization
and PCIe setup-margin/hold repair are complete. The exact final routed checkpoint
is saved; its complete reports are being generated. Current operation is
`routed_checkpoint_and_reports`, with 6/7 completed operation milestones (not an ETA).
The native post-repair check measured userclk1 setup +0.082 ns, hold +0.025 ns
and zero unrouted nets. It still measured setup -0.159 ns on other clocks.
These checks do not qualify the image: the actual closed final numerical report
and exact current review must decide the remaining compute timing finding.
The numerical owner is live and follows this exact producer immediately at release.
No bitstream, reviewed package or hardware execution is claimed. All remaining
numerical, CDC, PHY, findings/waiver/object, integrity and package gates apply.
Evidence: `build/handoffs/final-reports-state-update-20261020-v1/manifest.json`.

Completed source/admission evidence:

- Fresh source/project 46 gates; synthesis and linked-netlist collection passed.
  All 78 compiled files were checked: 76 unchanged, two readonly identity literals
  changed. Current conditional source signatures and protocol facts were rereviewed.
- Current control/reset/CSR/ACK bindings cover 258 runtime + eight provider bits,
  134 receiving edges and 1,343 ACK source records entirely memory-clocked.
- Four source clock/Gray views: 64 clock observations and 256 scalar paths.
  Control intent preserved 1,360 paths, 44 incoming bounds, 24 asynchronous
  assertion pins and eight raw locked inputs.
- All nine initial CDC purpose groups assign 1,650 findings; the fresh additional
  CSR/reset review assigns every one of 1,776 post-intent findings in each of
  four modes. This is conditional source coverage, not routed/physical qualification.
- All 12 full-top traffic cases passed with 42 real source files and an explicit
  313-port behavioral vendor boundary. Full encrypted vendor/DDR simulation and
  physical clock transitions are not claimed.
- Private host phases: 27 protocol / 105 transport / 47 backend / 30 retired-ID
  cases; actual source-only data cannot open any supported transport.
- Fresh trained TinyStories-Llama-15M reference: all 32 tokens in modes 0,1,3,2
  (positions 13,21,13,21); complete 28,909,056-byte image SHA256
  74facccd6c0e3f7e76676617a3b7a4074c1efb784d675ac1b5bdb08dca980950.
- Current 28 scoped warning occurrences were dispositioned against the closed
  current native constant-net facts. Exact current native input audit passed
  active bounds, resources, interfaces, board pins and checkpoint identity.

Final review and later workflow owners:

- Numerical review is armed and waiting for this implementation to release:
  `build/checks/runtime-routed-finalization-owner-c0184806-20261020-v2`.
  Supervisor: `build/checks/runtime-c0184806-final-review-admission-owner-20261020-v2`,
  session 88734. Its startup requires the producer's first receipt; no build restart.
- Four-mode routed PHY/pad/reset review is armed after the numerical gate:
  `build/checks/runtime-routed-phy-owner-c0184806-20261020-v1`, session 24730.
- Prepared tool guards: 69 routed, 25 PHY/pad, 13 original/OOB coverage,
  16 current-worker native completion, 35 bitstream gates, 14 package,
  six SRAM and 13 JTAG workflow. All are preparation tests; no image or physical
  qualification is transferred. Current package tests use the matching private
  c0184806 host/runner and real mode data. XVC --dry-run was actually checked
  without hardware. Preserve exact tested tools and native CRC checker.
- Packaging and SRAM tasks remain explicitly owned by the active OpenTPU task;
  current preparations/commands are bound in the canonical manifest. Complete
  actual routed finding/waiver/scope and operating-contract dispositions before
  generation. Package full and small runtime data, then use standing temporary
  SRAM scope only with exclusive hardware ownership. Permanent flash still
  needs approval for the exact image; no existing approval is extended to c0184806.


Remaining final evidence collectors are executable and armed on the current image:

- Report inventory: `build/checks/runtime-routed-inventory-owner-c0184806-20261020-v1`,
  session 65388. The reader passed 14 tests on real report fixtures and rejects
  incomplete summaries/details, partial design scope and truncated finding numbers.
- Native waiver/object scopes: `build/checks/runtime-routed-waiver-owner-c0184806-20261020-v1`,
  session 97652. It waits for current numerical success, PHY release and 8 GiB
  available memory before native collection, so heavy review children are serialized.
  Original and all four mode views must export all/waived/unwaived CDC, DRC and
  methodology reports plus complete native affected-object properties/counts.
- Scope reconciliation: `build/checks/runtime-routed-scope-reconciliation-owner-c0184806-20261020-v1`,
  session 59733. Its reader passed 33 guards, including real complete-object
  fixtures rather than a 15-item display sample. It preserves findings above row
  1000 and every native scope identity. Reconciliation grants no technical waiver.

The final technical disposition remains owned by the active OpenTPU task. As
soon as these exact receipts close, review every actual finding, waiver provenance
and operating-contract condition before generation. Tool tests and source-level
assignments are not actual routed/image qualification.

The older isolated v4 comparison was intentionally stopped to release resources
for the admitted priority build. It stopped during routing, not as a timing or
hardware result. Its registered target facts and replicated checkpoint are
unchanged and are bound by the immutable c0184806 admission. Cancellation receipt:
`build/checks/runtime-command-critical-fanout-cancellation-20261020-v4/manifest.json`.
Do not restart it or treat its resulting SIGTERM wrapper failure as image rejection.
Original source/routed failures and every prototype receipt remain preserved.

Preserved review-tool corrections:

- Warning v1 had a Tcl argument mismatch; v2 reran the same source checkpoint
  with the corrected contract. A later admission check caught v2's final timestamp
  update after immediate review. Fresh closed-producer disposition is
  `build/checks/runtime-vendor-constant-disposition-c0184806-20261020-v3/final-disposition.json`.
  No source/implementation restart was needed.
- Copied routed readers initially missed c0184806 ID support; original 66-test
  receipt was preserved. Corrected readers passed 69 guards including actual
  current 258+8-bit native facts.
- Numerical follower v1 raced the implementation's first receipt publication.
  Both failed receipts remain; v2 waits for that receipt and follows the same
  running implementation. Source, firmware, clocks and numerical gates unchanged.

A separate carry-lookahead decoder alternative was prepared privately in
`build/checks/runtime-mxu-pair-lookahead-experiment-20261020-v1`. SAT proved all
KBa/format/PAIR inputs equivalent, including 16-bit wrap, and detected a deliberate
negative. Isolated Yosys xc7 mapping removed four CARRY4 cells. This is not full
Vivado timing, a queued bitstream or an image; it is not in c0184806. Retain as a
possible correction only if actual final timing calls for it.

Resume: observe this exact implementation; let its numerical and PHY followers
run immediately; finish exact routed findings/waivers/scope and operating-contract
disposition; generate/CRC/package only on exact pass; then perform authorized
exclusive SRAM and four-mode TinyStories checks. Keep Mac LFM/PCIe acceptance,
wall profiling and cold/warm repeats distinct. No hardware was accessed, no
flash changed, and no index/commit/push changed during this continuation.

### Selected Mac candidate and physical fallback

c0182663 remains locally qualified: 148.837 MHz, DDR1066, 4 GiB, both JTAG/PCIe,
automatic both-channel calibration firmware c0172668; same lane/ECC mapping.
Exact bitstream SHA256:
a1571e696d510d4b19adc59534872ceef48398036134d817f00b6b2ebb232acc.
Exact MCS SHA256:
4b471e9008e7f6d3239c0c2093776b466b64bbea9cab57d43b193e6b8ff03ee8.
Review/package, local SRAM INIT/DONE/IDCODE, startup, full initialization,
exact native program fetch, matmul, complete model readback and eight trained
TinyStories ISA tokens passed. Native read median was 4.452521 GB/s, 1.4883x the
two-channel c0182600 benchmark; this is not a single-channel/PCIe/decode result.
Current qualification receipts:

- `build/hardware/c0182663-sram-acceptance-owner-20261019-v1/run/manifest.json`
- `build/hardware/tinystories-c0182663-20261019-v1/manifest.json`
- `build/checks/c0182663-local-qualification-20261019-v1/manifest.json`
- `build/checks/c0182663-native-bandwidth-disposition-20261019-v1/manifest.json`

Last verified board state was volatile c0182663 and permanent c0182863. This
continuation has not opened the hardware; establish actual current identity and
exclusive ownership before board work. The benchmark overwrote program/output
memory, so resident model reuse must not be assumed. Permanent c0182663 approval
is still pending; no authorization file or write exists. The user's skip-backup
preference remains in force. Prepared permanent workflow:
`build/handoffs/c0182663-permanent-preparation-current-20261019.json`.
Mac runtime/guide preparation is local, uncommitted and unpublished: 20 files,
200,221 bytes; `docs/mac_c0182663.md` and
`build/handoffs/c0182663-mac-runtime-current-20261019.json`. A Mac git pull cannot
retrieve unpublished work. No branch, stage, commit or push was created here;
keep existing commits local unless pushing is authorized. Preserve unrelated
index/worktree entries, including the existing staged files. Bitstreams, model
weights, checkpoints and large generated outputs must not be committed.

Other open milestones remain: c0182863 startup pacing comparison (450.4 s
baseline includes 409.6 s fixed pauses), controlled host/decode profiling,
cold/warm repeats and selected Mac acceptance. c0182800 and c0182863 already
passed original Mac LFM230M/Qwen checks. Keep c0182600 fallback and c0182461 only
as an optional comparison. Original lane 6/CH0 ECC restoration stays last;
no extra standalone RAM soak. Vortex hardware work remains stopped for OpenTPU.

This handoff was reconstructed after a progress-refresher variable collision
from the untouched progress chronology, the preserved working handoff and
current canonical receipts. Historical source files and build evidence were
not modified. Recovery provenance:
`build/handoffs/handoff-restoration-20261020-v1/manifest.json`.



## 2. Preserved recent preparation chronology

The current state above supersedes dated running/pending statements below.

# OpenTPU progress

**Live experimental status checked October 20, 01:38 HKT:** the completed c0184805
implementation has its final numerical disposition: setup -0.137 ns, 27 failing
endpoints; hold +0.025 ns and all 333,051 routable nets complete. It is ineligible
for generation/package/programming. Exact source and routed evidence is retained:
`build/checks/runtime-c0184805-final-timing-rejection-20261020-v1/manifest.json`.

**Current task: command-distribution correction.** Native diagnostic v2 is
running on an isolated copy of the final checkpoint: unroute, force selected
ordinary register replication, then full routing and PCIe OOB analysis. The
installed API sequence passed its separate native fixture. The first diagnostic
failed because forced replication is unsupported in post-route mode; its
receipt/log remain unchanged. No original implementation was restarted.
Successor **c0184806 has a separately checked 78-file identity source baseline**
and a fresh full-top generator output. Seventy-six files are unchanged; only
the top default and saved-project generic identities changed. Fresh vendor
project generation and all 46 saved-source gates passed, matching this exact
78-file baseline. The current control inventory accounts for all 266 bits and
134 receiving edges. **Fresh c0184806 full-source synthesis/netlist validation
is running** with 551 frozen input files; full implementation remains
unadmitted. Source job/session: `runtime-netlist-c0184806-20261020-v1` / 21612.
The physical correction policy still requires the current routing evidence.
Canonical successor preparation:
`build/handoffs/runtime-command-distribution-correction-current-20261020.json`. Both host
interfaces, all four clock modes, full accelerator and 4 GiB remain required.
c0182663 remains the locally qualified Mac candidate, pending its exact-image
permanent-flash authorization, Git publication and Mac acceptance.

The following dated sequence preserves earlier preparation states; the live
manifest and refreshed todo table supersede those earlier pending statements.

The re-entrant router returned successfully with estimated setup -0.139 ns
and hold +0.025 ns. The repair was retained, the final checkpoint was written,
and exact reports are running: 6/7 implementation milestones complete. This
estimate does not qualify the image.

October 20 pulse-coverage review-order correction: the original native report
has eight pulse-clock coverage entries before PCIe OOB analysis. The fresh
numerical owner v4 keeps that inventory provisional and requires all four
actual OOB views, including verbose zero-gap pulse coverage, before releasing
later review stages. Thirteen guards passed, including the unchanged negative
setup rejection. Only verified WAIT owners were replaced: numerical/PHY/raw
facts v4, inventory/scope v3. Implementation was neither changed nor restarted.
`build/checks/runtime-base-oob-order-owner-correction-c0184805-20261020-v1/manifest.json`.

An isolated command-fanout replication diagnostic is registered and waiting for
12 GiB available memory. It has not launched native Vivado and cannot generate
a bitstream. The original implementation and five final-review workers remain
unchanged. Its job/launch/receipt are recorded in the canonical current manifest.

Routed review preparation/owners v2 correct the stale reset-cone proof path.
All 65 original reader guards and one actual-current-proof regression passed.
Only WAIT workers were replaced; the implementation was neither changed nor
restarted. See
`build/checks/runtime-c0184805-routed-proof-pointer-correction-20261019-v1/manifest.json`.

Five exact review workers are armed: numerical/control/CDC, PHY/pad/reset,
complete native waiver/object facts, report inventory and scope/object reconciliation. Installed waiver
commands passed a separate native fixture; current-image qualification remains
pending. The current bitstream gate passed 35 guards and requires complete
routed evidence, current CSR ownership and all upstream owner releases.
Placed timing remains intermediate: setup -1.083 ns, hold -0.524 ns. Physical
optimization/routing must finish and final original numerical gates must pass.
Preparation/observation receipts:
`build/checks/runtime-bitstream-generation-preparation-c0184805-20261019-v1/manifest.json`;
`build/checks/runtime-c0184805-placed-timing-observation-20261019-v1/manifest.json`.

Matching package/SRAM preparation is now tested: 14 package-producer guards
and six hardware-free SRAM guards passed. Full/small package compatibility
used synthetic review/bitstream fixtures and transfers no image qualification.
The producer requires actual final technical contracts and CRC-checked output;
the loader requires the full exact package and exclusive local JTAG ownership.
No actual c0184805 package or programming operation has been produced.
Receipts/commands:
`build/checks/runtime-package-preparation-c0184805-20261019-v1/manifest.json`;
`build/checks/runtime-package-preparation-c0184805-20261019-v1/commands.json`;
`build/checks/runtime-sram-preparation-c0184805-20261019-v1/manifest.json`.

Physical optimization finished; routing is active. Latest intermediate timing:
setup -0.261 ns, hold -0.310 ns, pulse 0.000 ns. Final routed review is pending.
`build/checks/runtime-c0184805-physopt-timing-observation-20261019-v1/manifest.json`.

The post-SRAM exclusive JTAG workflow passed 13 offline guards: exact local
model/reference/image binding, all 32 tokens through modes 0,1,3,2, context
preservation/reload, and mocked success/failure XVC/lease release. No physical
run has occurred. Commands:
`build/checks/runtime-jtag-workflow-preparation-c0184805-20261019-v1/commands.json`.
The waiver-scope reader passed 22 original/actual-empty-report guards; a live
read-only placed-checkpoint probe is collecting the full-design waiver-scope
formats. Probe session 45579 and its exact launch/receipt are recorded in
`build/checks/runtime-waiver-format-probe-c0184805-20261019-v1/`.

**Current experimental work: c0184805 coherent CSR reset correction.**
Post-route optimization improved setup to -0.148 ns (TNS -3.557 ns); hold is
+0.025 ns and pulse 0.000 ns. PCIe userclk1 margin repair is active. Setup
qualification remains open until the exact final report passes.
`build/checks/runtime-c0184805-postroute-optimization-observation-20261020-v1/manifest.json`.

The first route has setup -0.177 ns and hold +0.025 ns. Post-route optimization
is active; setup paths are in runtime_compute command distribution. Final
numerical qualification remains pending.

A separate 10-guard native-completion classifier preserves the original
wrapper receipt while recognizing only its exact nonfinal Route 35-39 warning.
It cannot approve timing. Final numerical limits are unchanged, and the
bitstream gate (35 guards) requires the actual successful final numerical
review. Numerical/PHY/object-fact owners now use v3, report inventory v2 and
scope reconciliation v2; all replaced workers were verified WAIT-only.
Implementation and frozen inputs remain unchanged.
`build/checks/runtime-nonfinal-warning-owner-correction-c0184805-20261020-v1/manifest.json`.

October 20 review correction: grouped Vivado messages display only samples of
affected objects. Native export was verified with 32 reset pins beyond the
15-name display cap. A fresh complete-object collector replaced only the old
WAIT worker; implementation is unchanged. Five exact review workers are now
armed, including automatic full-object reconciliation. Scope/object readers
passed 33 guards; the bitstream gate passed 32 and now requires the actual
complete-object receipt and six upstream owner releases. Package/SRAM/model
workflow checks passed again (14 / 6 / 13); actual programming remains pending.
`build/checks/runtime-review-object-completeness-correction-c0184805-20261020-v1/manifest.json`.

The new reset owner passed 56 cases with the actual generated AW FIFO slice,
including 28 stopped-memory-clock cases. All 28 deliberately one-sided reset
faults were detected. Its memory-domain reset asserts asynchronously; AON
admission remains reset until memory has clocked through reset and its release
has crossed back. A source-only complete memory provider is now emitted: both
FIFO pointer banks use this ownership, management request/response state is
flushed, and all 16 CSR banks are gated during reset. Full generated-provider
protocol tests, shared CSR/selfcal abort/recovery review, complete top/source
integration and all original source/routed/hardware gates are still required.
No c0184805 synthesis or implementation job has been admitted.
Current manifest: `build/handoffs/runtime-csr-reset-correction-current-20261019.json`.

The complete generated management path has now passed all 144 reset cases
with the calibration CPU held: all five real FIFOs, AXI/Wishbone, shared bus,
and the actual scratch CSR are retained. Cases cover both memory periods,
nonzero/wrapped empty pointers, partial AW or W, pending B/R, in-flight work,
stopped-clock reset and exact fresh traffic. Verilator fixture boundaries are
explicit; the unrelated vendor PHY/PLL behavior is not qualified. Source delta
review also proves the external ABI and CPU RTL unchanged, all other 25 bundle
files identical, and DDR reset/calibration assignment lines unchanged. There
is no extra SRAM strobe gate to add: both unused strobe nets have no consumer.
The next real software-model owner is running shared-bus/reset checks using a
finite injected calibration-side Wishbone requester. This is separate from
actual firmware recovery qualification; complete top/source review is pending.
`build/checks/runtime-csr-full-provider-c0184805-20261019-v3/run/manifest.json`;
`build/checks/runtime-csr-shared-master-c0184805-20261019-v1/launch.json`
(session 62394).

The shared CSR-bus/reset model also finished: all 48 cases passed, including
36 with a calibration-side request outstanding at reset. This uses a finite
injected requester at the CPU bus boundary and does not qualify CPU firmware
recovery. The exact complete successor source candidate is now prepared
(67 copied files, unchanged parent RTL except BUILD_ID, selected corrected
provider and unchanged 26-file memory bundle except its Verilog). Its selected
42-file accelerator/top model is actually compiling/running all four modes
under session 23704. The checker is byte-identical to the predecessor; only
the bench's two expected identity literals changed. Normal source/project/
266-bit ownership/host tool integration is still required before source
synthesis admission. This is a software model, not a queued Vivado job.
`build/fedora-vivado/spare-runtime-csr-reset-c0184805-20261019-v1/manifest.json`;
`build/checks/runtime-csr-reset-c0184805-traffic-preparation-20261019-v1/launch.json`.

Normal c0184805 preparation is now complete. Its 42 selected RTL files and
entire memory bundle match the tested candidate exactly. All 46 saved-project
checks, 28 source/identity guards, 266-bit/134-edge source ownership and 23
native-reader guards passed. Matching host tests passed 27 protocol, 105
transport/legacy, 47 model backend and 25 retired-identity cases (204 total).
The fresh trained CPU/ISA reference matched all eight tokens in each of modes
0,1,3,2 and retained the exact initial-image digest and prior reference tokens.
Source-only host data still cannot open hardware.

The exact source-synthesis/linked-collection job is admitted and actually
running (session 73474). Its worker/process invocation and priority release
were verified; 24.9 GB was available at admission, above its 11 GiB requirement.
All 46 project gates and original numerical/interface checks remain. This
admits source synthesis only: no placement/routing, bitstream or hardware load.
Current source job: `build/fedora-vivado/runtime-netlist-c0184805-20261019-v1`;
source admission: `build/fedora-vivado/runtime-netlist-c0184805-20261019-v1/admission.json`.
The collector retains the exact prior eight GTX/clock/top-level-register checks
and now explicitly exports all eight provider bits plus their INIT properties.
Current-source native/fanin/CDC/all-mode review follows collection immediately.
Earlier preparation-only descriptions above are historical milestones.

The matching source-native review owner is admitted and actually waiting
(session 23348) for exact source synthesis/collection to finish and release.
It then opens only that checkpoint, probes current reset producers and the
CSR release inverter, checks all 266 owned bits/134 edges, refuses raw/non-memory
sources at ordinary memory ACK, and inventories the complete current CDC
report. It cannot program hardware or admit a full implementation. Its gate
retains current artifact hashes, exact owner PID/start ticks/command, all eight
provider INIT properties, source/publication checks and strict CSR reset wiring.
`build/checks/runtime-csr-reset-source-owner-c0184805-20261019-v1/launch.json`.

Source synthesis completed successfully: native exit 0, no nested IP errors,
and actual late-constraint observations of 6.718 ns compute / 7.500 ns memory.
The completed synthesis DCP was independently hashed. Linked collection is
running; no placement/routing is admitted.
`build/checks/runtime-c0184805-source-synthesis-completion-20261019-v1/manifest.json`.

Four further owners are now actually running/waiting in order after source
review: full Critical/reset/ordinary-ACK and CSR release fanins (session 72300),
four static clock/Gray views with immediate review (97611), current control
intent in all four modes (77338), and complete before/after CDC context (50049).
The intent keeps all 43 existing data policies byte-for-byte, adds one bounded
inverted memory-reset observation, and covers 44 data inputs / 24 exact async
assertion pins / eight raw LOCKED first stages. All 134 receiving edges remain
timed: 1,360 ordinary/interstage/Gray preservation facts across four modes.
The context reader passed six historical-report guards. It inventories newly
exposed findings and never treats exposure or inventory as purpose approval.
Every current reported row still needs disposition before implementation.
`build/checks/runtime-control-intent-c0184805-preparation-20261019-v1/manifest.json`.

Source synthesis and linked collection both finished successfully, native
exit 0 with all eight new/current provider INIT properties exported. Native
review v2 passed all 258 runtime + eight provider bits. The CSR stages are
actual FDPE/FDCE receivers with the correct INIT, shared reset source, clocks,
direct stages and exact memory-tail inversion. Ordinary ACK has only local
memory-clocked sources and both local PLL samples in its real fanin.

A real 312,010-byte NETS field exceeded Python csv's 131,072-byte default limit.
This was a review-tool limitation, not an FPGA defect. Literal TSV parsing now
preserves every field and rejects malformed rows/headers; six guards include
the actual current export. Original receipts were retained. All five v1
owners were stopped while verified WAIT-only with no native review child;
the source worker was not stopped or restarted. Fresh v2 owners are bound
throughout: source review (19665, completed), Critical/reset/fanin (90078,
running), static views (82447), intent audit (61332), CDC context (12034).
No RTL, numerical limit or constraint changed for this correction.
`build/checks/runtime-c0184805-tsv-reader-correction-20261019-v1/manifest.json`;
`build/checks/runtime-csr-reset-source-owner-c0184805-20261019-v2/run/manifest.json`.

The full Critical/reset/fanin collector passed, including shared control reset
at both actual core PRE stages and the CSR memory/AON release and assertion
sources. All four static clock/Gray views passed (64 clock facts, 256 Gray
facts). Fresh source-only protocol tests passed 144 reset cases/two faults,
144 real drain-fanout cases/one fault, 18 host-reset cases/two faults and 64
PCIe-status/fence cases/one fault. Fresh current vendor probes and reviews
passed; every one of the initial 1,650 reported source findings now has a
disjoint conditional purpose assignment (15 Critical, 1,635 Warning, zero
unassigned). After-intent additions are still separate and unapproved.
`build/checks/runtime-cdc-source-ledger-c0184805-20261019-v1/manifest.json`.

The complete current CSR probe passed all 30 Gray-pointer bits / 60 sampler
stages, exact source/receiver domains, unconditional enables and direct Q/D
connections. Every sampler's actual reset cone includes its corresponding
local coherent-reset tail and only local clocked sources. This is source
structure, not routed skew/latency or physical qualification. All 28 current
static-view warnings were independently disposed using fresh native ground-net
properties; the quantizer's real registered predicate is retained.
`build/checks/runtime-csr-native-structure-c0184805-20261019-v1/final-disposition.json`.

The read-only implementation intake is actually running (session 81576), with
all 44 data bounds / 24 assertion pins / eight LOCKED inputs and the exact
current checkpoint. Its audit mode cannot optimize/place/route/write a
bitstream. No full implementation job/admission exists yet. The four-mode
control audit and complete before/after CDC context remain active; the first
mode already retains all 340 recorded ordinary/stage/Gray requirements/slacks.
`build/fedora-vivado/runtime-implementation-c0184805-20261019-v1/input-audit-launch.json`.

The read-only implementation intake finished successfully: exact checkpoint,
part/top, board pins/voltage, USER2, eight PCIe GTX lanes, full hierarchy and
all 44 incoming active bounds pass. It performed no opt/place/route or bitgen.
`build/fedora-vivado/runtime-implementation-c0184805-20261019-v1/input-audit-manifest.json`.

The first completed post-intent mode has 1,776 reported rows: every initial
1,650 row is retained plus 126 additional findings (19 Critical, 107 Warning).
All 126 now have current, scoped conditional source-purpose reviews: 96 CSR
payload paths, 10 CSR pointer groups, one memory-rate Gray group, three memory
reset rows, three memory-local PHY-release rows, 11 held PHY/status rows, one
unsupported global-reset row and one coherent CSR preset row. Fresh current
payload/RAM/enable facts, reset properties and fanins bind the proof. Constant
VCC enables have no all_fanin startpoints; the collector was corrected to
record their actual VCC leaf and require all 96 rows, preserving its first
header-only receipt and reusing valid Critical-cone data without repeating it.
The exact compiled local-PHY fragment also passed 16 stopped-clock cases and
16 deliberately bypassed-source controls under a fresh current binding.
`build/checks/runtime-post-intent-purpose-c0184805-20261019-v1/manifest.json`.

All-four-mode source-purpose closure is admitted and actually waiting (session
94344). It must match every current report row to these exact proofs; any
mode-specific missing/new/changed unreviewed finding fails closed. Mode-0
purpose coverage alone does not admit implementation. The full implementation
admission tool is prepared, and its actual check refused to create a job while
intent/context/all-mode-purpose gates remain incomplete. No implementation
job.json or admission.json exists.
`build/fedora-vivado/runtime-implementation-c0184805-20261019-v1/pending-source-gates.json`.

All four current source modes passed the complete control-intent audit:
1,360 preserved ordinary/interstage/Gray facts, all 44 active incoming bounds,
24 exact async assertion pins and eight LOCKED first-stage inputs. Both full
before/after CDC inventories and exact source-purpose closure passed. Each
mode reports 1,776 findings, all assigned, zero unassigned; this remains source
purpose qualification and does not substitute for routed/physical checks.
The exact input audit is also PASS and all upstream owners released.

Full native implementation was admitted after all original/frozen source,
current-review job/receipt, host, checkpoint and owner checks passed. The
actual implementation worker/native process is running (session 91642),
starting with exact checkpoint/interface/pin/active-bound intake before opt.
The seven implementation operation markers are starts; completed milestones
are earlier finished operations, not elapsed-time or remaining-time estimates.
Routing, final review, bitstream and physical checks remain separate.
`build/fedora-vivado/runtime-implementation-c0184805-20261019-v1/admission.json`;
`build/fedora-vivado/runtime-implementation-c0184805-20261019-v1/launch.json`.

Optimization finished and placement is actually running. Current routed
review collectors/readers are prepared with 65 passing guards: actual report
parsers, exact per-mode post-intent CDC baselines, all 44 active input bounds,
134 max/min receiving-stage paths per mode, all eight provider INIT/reset/
inversion/ACK bindings and retained Gray/numerical/skew/OOB/interface checks.
The six allowed identity reset/status assertion cuts are literal and bounded;
new tests still reject Gray, reset-data or status second-stage cuts. No current
routed result or optimization removal/replication is silently qualified.

The finalization owner is actually waiting (session 72494) for the exact
implementation to finish and release. It immediately checks base routed
setup/hold/pulse, routing and internal coverage. Real numerical failure rejects
this exact image and blocks bitgen; a report-reader failure stays a tool issue.
On numerical pass it starts the current four-mode routed collection/review.
The separate exact PHY/pad/reset owner waits for that numerical pass (73071).
Its tools were regenerated from current compiled source and passed 25 guards;
341 SERDES, 163 reset copies, 180 pad connections and all 2,032 reset timing
paths remain required. Both review owners keep bitgen disallowed until all
remaining final gates have their separate exact dispositions.
`build/checks/runtime-routed-finalization-owner-c0184805-20261019-v1/launch.json`;
`build/checks/runtime-routed-phy-owner-c0184805-20261019-v1/launch.json`.

The predecessor is retired because an exact generated-FIFO counterexample
proved a real reset defect: all 28 control-only reset cases fabricated queued
requests from a previously empty FIFO with nonzero pointers, while 28 coherent
reset controls stayed empty. The source top can produce this one-sided reset
on host reset and compute-lock transitions. Its implementation admission is
permanently disabled; evidence is retained. The in-flight read-only CDC context
collector may finish as diagnostic evidence and cannot admit an image.
`build/checks/runtime-c0184804-csr-reset-rejection-20261019-v1/manifest.json`.
The following predecessor descriptions are historical, not the active plan.

**Historical c0184804 update — 19 October, 20:07 HKT:** source synthesis,
native ACK/provider review, all four static clock/Gray views, read-only native
implementation intake and the four-mode active-intent audit passed. All 1,344
ordinary/interstage/Gray preservation checks passed. Both final read-only audit
owners have finished and released ownership.

The following CDC reconciliation refused implementation admission: each
post-intent static view contains all 1,650 original findings plus the same 125
additional findings (18 Critical, 107 Warning). Their exact per-mode inventory
is saved; no finding is waived. These additions require supported clock/reset/
provider-purpose disposition before placement/routing can start. This result
has not yet established either a parser defect or a new RTL defect. No
c0184804 implementation, bitstream, programming or physical inference exists.
Receipt: `build/checks/runtime-c0184804-post-intent-cdc-delta-20261019-v1/manifest.json`.
Earlier running/waiting descriptions below are historical and superseded by
this update.

**Historical c0184804 source: memory-provider PLL-lock correction.**
Deeper native fanin of the ordinary memory ACK proved that both raw generated
PHY PLL LOCKED outputs still reached its D input through PHY idle. This
violates the real participant's synchronous-input contract. The exact source
received immediate rejection; no implementation, bitstream or hardware load
was admitted. It is removed from active progress rows; evidence is retained.
Rejection: `build/checks/runtime-c0184803-raw-phy-lock-rejection-20261019-v1/manifest.json`.

The complete successor source is prepared. Only BUILD_ID and the selected
memory provider change: two per-channel, two-stage memory-clocked lock samples
replace raw LOCKED in PHY idle. Local pipeline and DQS busy terms remain
immediate; the existing memory-local PHY-release sample and independent raw
AON proofs remain. No clock, DDR rate, capacity, lane/ECC mapping, firmware,
interface or accelerator feature changes. All four 100/148.837 MHz and
DDR800/1066 modes, 4 GiB and JTAG/PCIe are retained.

The exact new provider fragment with the unchanged real drain participant
passed 16 cases across both memory periods and eight phases. All 16 deliberate
raw-lock bypasses and all 16 delayed-busy aggregate faults were caught; the
latter would otherwise fabricate an early ACK. Stopped-clock qualification,
independent channels, immediate pipeline/DQS busy masking and fresh stable
ACK/rearm were checked. This is logical component evidence, not PHY timing.
The fresh complete 42-file native/ISA model finished exit 0: all 12 cases
and exact 32-word/five-instruction matmul in all four modes passed. Independent
source/provider/model review passed. Normal top emission matches all 42 tested
RTL files and the complete selected memory byte-for-byte; 20 identity/provider
guards, vendor project assembly, all 45 saved-project checks, explicit source
ownership of 258 runtime + four generated bits / 132 interstage edges and
native input/observer/exclusion audit passed. Full source synthesis has now
finished successfully, with the actual 6.718 ns compute / 7.500 ns memory
constraint-stage observations and no native/nested-IP errors. The exact full
checkpoint and every original/frozen input hash passed completion review.
Linked netlist/CDC collection also completed successfully in the unchanged
source worker (session 72486). The corrected complete 262-bit source review
passed; current native fanin and dependent all-mode reviews are active. The fresh
collector explicitly includes the four generated provider registers; eight
reader fault controls passed. Matching host source/data now passed 27 protocol + 97 transport + 47
backend + 20 retired-image cases (191 total, including 24 binding rejection
cases). The real trained TinyStories CPU/ISA runner passed eight tokens in
each of modes 0,1,3,2, preserving the prior initial model-image digest and
exact reference token sequences. This is CPU evidence, not physical inference.
Source-only metadata cannot open a device.

Read-only completion owners are admitted and actually waiting: current
258-runtime-plus-four-provider-bit/publication review and complete CDC
inventory (completed corrected review), ordinary ACK/native sampler fanin (17605), four static
clock/Gray views with immediate review (95653), and current four-mode control
intent audit (51552). The fanin owner now refuses any raw MMCM/non-memory
source at ordinary memory ACK D and requires both real local PLL observations
in its cone. The intent audit covers all 132 local stage edges (max/min),
64 Gray inputs and ordinary samples: 336 preservation checks per mode /
1,344 total. Every clocked path into all 43 bounded control receivers must
exist and retain its actual maximum-delay requirement in every mode. All
20 exact reset assertion pins and eight exact raw LOCKED receivers are
validated before any analysis exception. These are source/native tools,
not image approval; ordinary data, PHY/Gray, routed and physical gates remain.
The first current-intent owner was replaced while verified WAIT-only, before
any native child, to also save post-intent CDC/exception reports in each mode.
Its original job/receipt and supersession are retained. The same numerical
limits and source synthesis worker remain unchanged; current owner is v2.

Exact c0184804 future implementation and bitstream-writer tools are prepared
as source only. The implementation intake verifies all 43 clocked control
input bounds are present/active before optimization, retains all original
directives, exports post-intent CDC/exception baselines, and saves routed
snapshots/timing before and after post-route optimization and before margin
repair. The bitstream writer passed 19 schema/negative guards and refuses
actual source-only receipts before output creation/native launch. It requires
all actual four-mode routed/PHY/Gray/finding/waiver/source/host gates, 262
owned bits, 132 receiving edges, exact ACK/43-input/20-assertion/eight-LOCKED
intent and released owners. These preparations admit no implementation,
bitstream or hardware operation.
`build/checks/runtime-implementation-flow-c0184804-preparation-20261019-v1/manifest.json`;
`build/checks/runtime-bitstream-generation-preparation-c0184804-20261019-v1/manifest.json`.

A read-only post-intent CDC reconciliation owner is also actually waiting
(session 78813), with six reader guards passed. It requires every original
structure/clock/severity row and the exact expected exception labels at the
71 reviewed control endpoints (43 data, 20 assertion, eight raw LOCKED).
Other exception changes, missing/new findings, clock or severity changes
fail review. Current reports remain required; historical/synthetic fixtures
qualify only this reader. Source/components also freshly passed the selected
reset 144 cases/two faults, host reset 18/two faults and PCIe status 64/one
fault; actual source-purpose disposition remains.
`build/checks/runtime-control-cdc-reconciliation-c0184804-preparation-20261019-v2/launch.json`.


**No c0184804 placement/routing or bitstream generation is admitted.**

Linked source collection completed successfully. Runtime 258-bit/130-edge
review passed, but the first generated-provider reviewer refused different
reset-register names. Native collection then proved the two actual
`crg_reset0` copies are FDRE INIT=1 with identical complete C/CE/D/R drivers,
clock views and origin. This was a reviewer name-identity assumption, not
a source/implementation defect. Fresh v2 readers keep all constraints and
require exact native-copy equivalence; 15 reader tests plus four input
subtests passed. The corrected complete 258+4-bit source review and original
complete CDC inventory are adopted without repeating synthesis/native work.
The initial dependent review chain correctly refused that failed parent;
its receipts remain. Current ordinary-ACK/native sampler collector is v2
(session 17605); all dependent owners were rebound to the corrected
review: fanin v2 (17605), static views v2 (95653), intent v3 (51552), CDC
reconciliation v2 (78813). Their old failed receipts remain historical. No implementation is admitted by this correction.
`build/checks/runtime-provider-reset-review-correction-c0184804-20261019-v1/manifest.json`.
The corrected native sampler/reset/ordinary-ACK collection finished exit 0.
All 1374 startpoint records at ordinary memory ACK D are local memory-clocked
registers (no raw MMCM or non-memory source); both new local lock observations
actually feed qualification, and only the designated first-stage inputs sample
the raw MMCM LOCKED pins. Shared-reset and existing PHY-release bindings pass.
This proves the targeted compiled topology, not routed or physical timing.
Four-mode clock/Gray collection is now active.
`build/checks/runtime-c0184804-ordinary-ack-source-disposition-20261019-v1/manifest.json`.
The current four-static-view collector/reviewer finished successfully: all
64 clock observations and 256 scalar Gray facts/bounds match. Fresh native
vendor clock-mux/payload/receiver checks and current reset/drain/host/status/
observation/abort source reviews passed. All 1,650 reported source findings
(15 Critical, 1,635 Warning) now have disjoint conditional purpose assignments,
with zero unassigned rows. This is not complete/routed CDC or physical
qualification. Current active-bound/intent and exact post-intent label
reconciliation remain mandatory before implementation intake.
`build/checks/runtime-cdc-source-ledger-c0184804-20261019-v1/manifest.json`.
The separate native implementation intake finished successfully read-only
(session 66089, now closed): exact current checkpoint, part/top, board pins/voltage, USER2,
eight PCIe transceivers/lanes, full hierarchy and all active clocked control
input bounds are checked with the reset-copy-aware helper. It invokes only
`audit`, never opt/place/route/bitstream. Actual implementation remains
unadmitted until current four-mode intent/CDC and native intake gates pass.
`build/fedora-vivado/runtime-implementation-c0184804-20261019-v1/input-audit-launch.json`.
All 28 current static-view warnings received exact disposition: 24 expected
explicit clock-view messages and four occurrences of one vendor ground net.
Fresh native properties prove that net is GROUND, with two pins, no external
input and one physical GND/G driver. Optional valid See source annotations
were preserved by the corrected reader. The current quantizer source and
actual registered predicate are retained. No ordinary timing limit is waived.

The current implementation admission gate is prepared. Its check against
the actual incomplete four-mode intent receipt refused admission before
creating admission.json or job.json. Placement/routing are still unadmitted.
`build/fedora-vivado/runtime-implementation-c0184804-20261019-v1/pending-admission-check.json`;
`build/checks/runtime-vendor-constant-c0184804-20261019-v1/final-disposition.json`.






Current state: `build/handoffs/runtime-phy-lock-correction-current-20261019.json`;
source: `build/fedora-vivado/spare-runtime-phy-lock-c0184804-20261019-v1/manifest.json`;
provider test: `build/checks/runtime-phy-lock-provider-c0184804-20261019-v1/manifest.json`;
full model owner: `build/checks/runtime-phy-lock-c0184804-traffic-preparation-20261019-v1/launch.json`.
Current source synthesis owner: `build/fedora-vivado/runtime-netlist-c0184804-20261019-v1/launch.json`; admission/job in the same folder.
Synthesis completion: `build/checks/runtime-c0184804-source-synthesis-completion-20261019-v1/manifest.json`.
Source/model review: `build/checks/runtime-phy-lock-c0184804-source-review-20261019-v1/manifest.json`.
Explicit source contract: `build/checks/runtime-control-source-c0184804-20261019-v1/manifest.json`.
Matching host: `build/checks/runtime-c0184804-host-preparation-20261019-v1/manifest.json`.
Completion owners: `build/checks/runtime-c0184804-review-owner-20261019-v2/launch.json`;
`build/checks/runtime-c0184804-reset-cones-owner-20261019-v2/launch.json`;
`build/checks/runtime-full-static-views-c0184804-20261019-v2/launch.json`;
`build/checks/runtime-control-intent-current-c0184804-20261019-v3/launch.json`.
The normal portable memory preparation also ran successfully and reproduced
the entire tested memory bundle byte-for-byte:
`tools/prepare_spare_runtime_phy_lock_core.py`; receipt
`build/fedora-vivado/spare-runtime-phy-lock-memory-core-c0184804-20261019-v1/manifest.json`.
Normal full-project/host source integration and explicit generated-memory
ownership inventory now passed. Actual current native ownership/ACK closure,
source/protocol/CDC/all-mode and intake review remain; this memory-source
preparation itself is not a queued build.


**Earlier c0184803 source/review chronology (superseded; evidence retained).**
The full parent source tree is preserved. Only the BUILD_ID and board-control
local PHY-release synchronization changed; all selected 42 RTL files, 4 GiB,
four compute/DDR modes, lane/ECC mapping, startup firmware and both JTAG/PCIe
interfaces remain. The memory participant now uses a two-stage mclk sample of
the aggregate PHY-released level; the independent raw AON held proof stays
available while memory clocks are stopped. No ordinary ACK-data path is waived.

The exact new fragment and unchanged real drain participant passed 16 logical
cases across 10/7.5 ns memory periods and eight offsets, with all 16 deliberate
raw-proof bypass negatives detected and stopped-clock ownership checked.
The complete 42-file connected native/ISA model has now finished exit 0 and
released its owner. All 12 cases passed, including all 32 ISA matmul words and
five retired instructions in each of the four compute/DDR modes. The actual
313-port boundary, both host frontends and all selected RTL were retained;
vendor/DDR boundaries remain behavioral models. Independent source-delta and
completed-model review passed: exactly two source files changed, and the fresh
owned inventory has 56 annotated members / 258 bits, including the new mclk pair.
Normal project assembly and all 44 saved-XPR checks have now passed. The new
source contract contains 56 members / 258 bits and 130 interstage edges; the
original 129 edges remain unchanged. Native input/observer/exclusion audit
passed. Exact full source synthesis has now completed successfully and saved
its full-design checkpoint, with actual fastest-clock observations 6.718 ns
compute / 7.500 ns memory and no native/nested-IP errors. Original/frozen input
hashes remain exact. Linked netlist/CDC collection is now running in the same
unchanged source worker (unified session 70238; exact launch identity below).
Matching host source/data now passed 27 protocol + 89 transport + 47 backend
+ 15 retired-image rejection cases (178 total, including 16 shared-reset/local-PHY
review/data rejection cases). The real trained TinyStories CPU/ISA runner also
passed eight tokens in each of modes 0,1,3,2, using the established explicit
prompt IDs; the initial 28,909,056-byte image hash matches the prior reference.
The first fresh command omitted those IDs and hit an unavailable optional
tokenizer converter before inference; that failed receipt is preserved, and
the corrected run uses a fresh v2 output directory. No physical inference is
claimed by this CPU result. Source-only host data still cannot open a device.

Read-only completion owners are admitted and running: source/publication and
complete CDC inventory (session 77125), native shared-reset/local-PHY-stage plus
ordinary memory-ACK fanin collection (13367), then four static clock/Gray views
and immediate review (92785). Each waits for its exact successful predecessor
and ownership release; none restarts synthesis or admits implementation.
Actual control/reset/first-stage/source/CDC/all-mode disposition remains required.
No simulator worker is still running for the completed 12-case model test.
**No c0184803 placement/routing or bitstream generation is admitted.**

Deeper timing/intent review accounts for every one of the 128 first-stage
candidates in the 258-bit / 130-interstage-edge source contract: 43 bounded
inputs, ten constant-data asynchronous-reset chains, six additional MMCM
LOCKED inputs, four already checked mailbox/external status chains, 64
registered Gray inputs and one unused read-only status bit. A fresh source-only
helper validates exact two-stage/clock/reset/driver ownership before any
constraint is applied. It retains the original 42 input bounds (including the
4 ns bounds), adds only the new local PHY sample input and proposes scoped
asynchronous assertion/LOCKED-input intent. Native/protocol review and normal
implementation integration are still pending. A read-only predecessor fixture
is running to test those structural guards and unchanged ordinary/Gray/PHY/
interstage timing; it cannot qualify c0184803.

The saved predecessor diagnostic also contains 30 sampled ordinary compute
setup failures, worst -1.143 ns. The new PHY sampler alone does not establish
full timing closure. These are ordinary data paths and cannot be cut as CDC;
fresh placement/routing and the original zero-failing-endpoint gates remain
mandatory. Evidence: `build/checks/runtime-memory-proof-ordinary-timing-scope-c0184803-20261019-v1/manifest.json`;
control preparation: `build/checks/runtime-control-intent-c0184803-preparation-20261019-v2/manifest.json`.
The first predecessor fixture correctly stopped before any new exception when
the prototype required FDRE for the two runtime-identity LOCKED receivers,
which actually use asynchronous-clear FDCE cells. This was a review-tool
schema error, not a new implementation failure. Fresh v2 binds exactly four
FDRE/R and two FDCE/CLR pairs, retaining every ownership/numerical gate; the
original failure is preserved. The corrected native fixture finished exit 0: all ten reset pairs / 20 assertion
pins and six LOCKED inputs (four FDRE/R, two FDCE/CLR) passed; all four fault
controls were detected; 188 ordinary/interstage/Gray timing requirements and
slacks were identical before and after the in-memory hypothesis. The new-image
helper refused the predecessor missing its local PHY pair before any
constraint was applied. This remains historical diagnostic tool evidence,
not current c0184803 qualification. Disposition:
`build/checks/runtime-control-intent-prior-native-disposition-20261019-v1/manifest.json`.

A fresh c0184803 implementation flow is prepared as source only: it applies
the reviewed exact control intent before optimization and preserves placed,
physopt and both pre/post-physopt routed snapshots/timing before margin repair.
The original opt/place/physopt/route directives and every final gate remain.
No implementation is admitted/queued by this preparation.
`build/checks/runtime-implementation-flow-c0184803-preparation-20261019-v1/manifest.json`.

The exact current c0184803 control-intent native owner is admitted read-only and
actually waiting for the successful four-static-view owner and release. It
will open the same new linked checkpoint in all four modes, validate all 43
bounded inputs, 20 reset assertion pins and six LOCKED inputs, and compare
all 130 receiving-stage edges (max/min), all 64 Gray inputs and ordinary
ACK/PHY/quantizer/core samples before/after. This is 332 preservation checks
per mode / 1,328 total; current source/protocol/CDC and routed qualification
remain separate. Session 68795, exact owner/job:
`build/checks/runtime-control-intent-current-c0184803-20261019-v1/launch.json`.




Current source/proofs:
`build/handoffs/runtime-memory-local-proof-correction-current-20261019.json`;
`build/fedora-vivado/spare-runtime-memory-proof-c0184803-20261019-v1/manifest.json`;
`build/checks/runtime-memory-local-proof-c0184803-20261019-v1/manifest.json`;
`build/checks/runtime-memory-local-proof-c0184803-traffic-preparation-20261019-v1/launch.json`;
`build/checks/runtime-memory-local-proof-c0184803-native-traffic-20261019-v2/manifest.json`.
Independent review: `build/checks/runtime-memory-local-proof-c0184803-source-review-20261019-v1/manifest.json`.
Source synthesis owner: `build/fedora-vivado/runtime-netlist-c0184803-20261019-v1/launch.json`; admission and job in the same folder.
Synthesis completion: `build/checks/runtime-c0184803-source-synthesis-completion-20261019-v1/manifest.json`.
Matching host: `build/checks/runtime-c0184803-host-preparation-20261019-v1/manifest.json`.
Completion review owners: `build/checks/runtime-c0184803-review-owner-20261019-v1/launch.json`;
`build/checks/runtime-c0184803-reset-cones-owner-20261019-v1/launch.json`;
`build/checks/runtime-full-static-views-c0184803-20261019-v1/launch.json`.
The normal public synthesis preparer now also accepts an exactly recorded, terminal and released priority owner; all 40 queue/clock/observer guards passed. The already running frozen synthesis worker remains byte-identical to its qualified predecessor.

The exact predecessor final artifact received immediate numerical disposition:
all 332,711 nets routed, no route errors, hold +0.031 ns and zero hold/pulse
failures, but setup -1.913 ns / 19,773 failing endpoints. It is ineligible for
packaging/programming. Its native implementation finished exit 0; its worker
correctly emitted NEEDS_TECHNICAL_DISPOSITION on Route 35-39 timing failure.
Dependent numerical/PHY promotion owners refused further promotion; the
original-report inventory remains diagnostic evidence. No bitstream or flash
write occurred. Final disposition is preserved at
`build/checks/runtime-final-numerical-disposition-c0184802-20261019-v1/manifest.json`.
It is removed from active candidate/progress rows; dependency history remains.

**Earlier c0184802 source/build chronology (superseded; evidence retained).**
Full 12-case integration and four exact ISA modes passed; normal project
43-check review passed. Complete source synthesis/linked collection and 256-bit control/publication
review passed. Native shared-reset binding and all four static views passed. All 1,650
current source rows have conditional purpose assignments; routed/physical
qualification remains. Exact implementation-input audit passed; full implementation is admitted
and its native worker has started. Routed/bitstream/physical review remains.

The current c0184802 routed-review owner is now admitted and actually running,
waiting for successful exact implementation completion AND release of that
worker. Current PID 1964803, unified session 47384; its current identity
is pinned in launch.json. All 58 preparation/owner guards passed. The bounded
saved-constraint reader was checked against actual c0182663 routed output
(62 saved/report groups) solely to validate the parser; no image qualification
transfers. It handles scoped literal cell/pin aliases and rejects unsupported
or unresolved expressions without Tcl evaluation. Current c0184802 source
contains 58 original skew commands; every original and per-mode added group
must reconcile with fresh routed saved endpoints, budgets and detailed reports.

The read-only collector covers four runtime modes, all 32 PCIe OOB clock views
per mode, 256 scalar routed Gray timing paths, 256 owned control bits, both
core shared-reset assertion cones, and fresh vendor payload/enable structures.
Timing/setup/hold/pulse/route/skew and full contextual CDC signature checks
run immediately after collection. A changed crossing or numerical failure
gets a technical-disposition receipt; it cannot restart implementation,
generate a bitstream or touch hardware. Full routed DDR-pad/DRC/vendor-contract
final disposition remains the active OpenTPU goal's immediate next task,
followed by exact bitstream/integrity/package and already authorized SRAM tests.
Owner: `build/checks/runtime-routed-review-owner-c0184802-20261019-v2/launch.json`;
receipt: `build/checks/runtime-routed-review-owner-c0184802-20261019-v2/run/manifest.json`.
These current states supersede the earlier source-only timeline below.

The PCIe margin repair's selected-net reroute completed, then found -0.069 ns
hold and entered the existing re-entrant full-route hold repair. The exact
implementation remains live; a generated final-routed.dcp and terminal
review receipt are still pending. Keep the original inputs unchanged.

The saved pre_userclk1.dcp is a completed routed/post-physopt checkpoint,
not the final margin-repair result. An identical bounded first-stage analysis
is now running against that exact routed snapshot (unified session 36568;
current native PID 1979323, start ticks 74820217). This distinguishes
actual routed input/ordinary paths from the earlier placed/physopt sample.
The inputs pin the snapshot and original implementation/repair-script hashes;
no cell, placement, routing or hardware modification is performed.
`build/checks/runtime-control-cdc-routed-analysis-c0184802-20261019-v1/launch.json`;
`build/checks/runtime-control-cdc-routed-analysis-c0184802-20261019-v1/preparation.json`.

A reusable 42-entry constraint helper is also prepared as source only. It
retains the same verified boundary/source/replica/identity-buffer checks and
numerical bounds. Its Tcl helpers are namespaced and the global clock command
is preserved. No constraint is applied by sourcing it, no normal project is
integrated, no corrected image identity is selected and no Vivado build is
admitted/queued by this preparation. Exact native/source-protocol and final
routed review remain required before integration or image promotion.
`build/checks/runtime-control-cdc-constraint-helper-preparation-20261019-v1/manifest.json`.
Current final task schedule:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v9/manifest.json`.

The bounded CDC timing-model diagnostic finished exit 0; this is not image
qualification. It verified all 42 selected boundaries before changing any
analysis object, including the actual identity truth tables of three LUT1
hold-fix buffers. All 36 registered-source paths, 1,657 predicate launch paths
and 84 local receiving-stage max/min paths were measured. One registered
path remains negative: admission_source_reg[0]/C to p_allow_meta_reg[0]/D,
requirement 4.000 ns and slack -1.171 ns. Keep that finding; do not relax the
budget merely to pass. Six before/after ordinary memory-ACK, PHY reset and
quantizer requirements/slacks are identical. The source, netlist, placement,
routing and hardware were never changed by this diagnostic. Raw-predicate
protocol and asynchronous reset-control timing disposition remains mandatory.
`build/checks/runtime-control-cdc-bounded-analysis-c0184802-20261019-v2/manifest.json`;
`build/checks/runtime-control-cdc-bounded-analysis-c0184802-20261019-v2/run/ordinary-preservation.tsv`.
The first diagnostic version is preserved as superseded; v2 changed only
batching of identical constraint updates to avoid repeated timing-graph work.

The actual implementation completed route_design and post-route optimization
and is in pcie_userclk1_margin_repair. A prior save was an intermediate margin-
repair checkpoint, not the final routed receipt; final-routed.dcp and the
required terminal reports are still pending. Do not promote/program the image
from intermediate timing or a file-save log. Existing exact review owners
continue to wait for their successful terminal prerequisites and process release.
Current final task schedule:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v8/manifest.json`.

The native control-boundary audit completed for all 53 non-Gray/non-constant
candidates. Fifty-two source pairs survive and each first Q feeds only its
declared next-stage D; all 104 local interstage max/min queries are present.
The one absent pair is p_status bit 3: exact frozen top-source checking proves
its synchronized bit has no functional reads (only bits 0/2 and 0/1 are used).
This is explicit unused-status pruning, not loss of an accelerator/host feature.
Two physical producer replicas match original primitive, INIT, every data/
enable/reset/clock input driver and clock. Three source paths also contain
implementation hold-fix buffers; actual identity LUT truth tables are checked
before any analysis-model modification. The first audit's name-retention
failure and the pre-launch tab/interactive-Tcl check issue are preserved;
fresh v2 completed without modifying implementation or hardware.
`build/checks/runtime-control-cdc-native-boundaries-c0184802-20261019-v2/manifest.json`;
`build/checks/runtime-control-cdc-native-boundaries-c0184802-20261019-v2/unused-status-bit.json`;
`build/checks/runtime-control-cdc-native-boundaries-c0184802-20261019-v2/replica-equivalence.json`.

A separate read-only timing hypothesis is running against the completed
physopt DCP: 36 registered boundaries get min(source, receiver period) bounds;
six scalar supervisory predicates get a diagnostic 20 ns propagation budget.
Actual sequential C launch pins retain clock-to-Q, exact target D pins limit
scope, and local interstage paths plus ordinary memory-ACK/PHY/quantizer samples
must retain their exact prior requirements/slacks. All existing Gray, mailbox,
constant reset-data paths and MMCM LOCKED-only inputs are excluded. No global
clock group or whole-domain exception is added. These are analysis objects
only; source/protocol/final four-mode routed qualification is still pending.
AMD UG903 2026.1 confirms datapath-only bounds need explicit -from startpoints
and remove phase/skew-derived hold checks on the selected asynchronous paths.
`build/checks/runtime-control-cdc-bounded-analysis-c0184802-20261019-v2/guidance.json`.
The exact v1 diagnostic process was replaced solely to batch all identical
constraint updates before timing queries; prior artifacts/inputs are preserved.
Current native PID 1977804, start ticks 74725370, unified session 89863;
`build/checks/runtime-control-cdc-bounded-analysis-c0184802-20261019-v2/launch.json`.
All original implementation/numerical/PHY/report inventory workers stay intact.
Current final task schedule:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v7/manifest.json`.

The next concrete CDC investigation now has an executable source classifier
and exact endpoint inventory: 256 owned registers / 129 same-clock stage
connections yield 127 first stages. Of these, 64 Gray stages remain protected
by their existing max-delay/skew gates and ten constant-data reset stages are
excluded from normal data reclassification. The remaining 39 registered-source
and 14 raw/combinational stages require their individual native protocol,
existing-exception, first-Q fanout and replica-equivalence review. Every item
has exactly one declared receiving-stage connection; no new timing constraint
has been applied and no successor image/build job is prepared or queued.
The inventory includes only non-info CDC rows; absent CDC rows do not prove
missing constraints. A root GND/G classification correction is preserved in
v2; the v1 investigative inventory also applied no constraints.
`build/checks/runtime-control-cdc-constraint-investigation-c0184802-20261019-v2/manifest.json`;
`build/checks/runtime-control-cdc-constraint-investigation-c0184802-20261019-v2/classify.py`.
Current final task schedule:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v6/manifest.json`.

The completed c0184802 physopt checkpoint received a separate read-only timing
probe (unified session 73211, closed exit 0). Ten exact endpoints produced 20
setup/hold reports with pinned checkpoint/source/tool hashes. Several first-
stage runtime synchronizers are analysed with only 0.018/0.020 ns related-clock
setup windows and fail setup/hold. These targeted CDC constraints require
technical review; same-domain receiving stages and ordinary consumer paths
must keep their numerical gates. The sampled memory-drain ack D path launches
from AON memory_reset and remains an ordinary timed consumer requiring separate
source/protocol/timing disposition. A sampled PHY reset path passes its 3 ns
maximum but has failing hold; the retained quantizer sample passes setup/hold.
The permission publisher also has an implementation replica; if retained in
the final DCP, verify equivalent registered clock/data/reset/initialization
rather than classify a different valid cell name as an FPGA logic defect.
`build/checks/runtime-physopt-control-timing-probe-c0184802-20261019-v1/manifest.json`;
`build/checks/runtime-physopt-control-timing-probe-c0184802-20261019-v1/paths.json`.
These are pre-route diagnostic findings. The existing implementation remains
unchanged, and final routed disposition is still pending. Next substantive
work is the targeted first-stage CDC constraint/equivalence review using the
exact 256-bit owned-control contract; no broad clock-group waiver is approved.

Exact bitstream generation/integrity tools are prepared, 19 guards and Tcl
completeness passed. They require actual final routed disposition and every
upstream owner release, then write only the exact DCP's bitstream and validate
its runtime header/packets plus independent CRC. The source-only host/CDC and
other fixed-image bitstreams were rejected in preflight. No bitstream job is
admitted or queued and no new bitstream exists. Small normalized artifact/CDC/
mode/source receipts and matched host/firmware package follow actual integrity.
`build/checks/runtime-bitstream-generation-preparation-c0184802-20261019-v1/manifest.json`.
Current final task schedule:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v5/manifest.json`.

Routing is now running; placement and pre-route physical optimization finished.
Pre-route DRC reported zero Errors, which is separate from final routed DRC
and methodology finding disposition. A read-only final report-inventory owner
is admitted and running: PID 1966023, unified session 12562. It waits
for exact implementation and numerical report/process closure, then inventories
both original reports plus all eight mode reports when collection completed.
A failed upstream result remains failed; closed diagnostic reports can still
be inventoried without approving the image. All summary/detail/identifier/total
counts must reconcile, under whole-design/unlimited scope. Fourteen reader
checks used actual completed 787-DRC/644-methodology reports only as fixtures;
critical findings and the reported waiver count remain explicit. Nine owner
release/diagnostic-scope guards passed. The current source's findings and
waiver provenance still require immediate technical disposition by this goal.
Owner: `build/checks/runtime-report-inventory-c0184802-20261019-v1/launch.json`;
receipt: `build/checks/runtime-report-inventory-c0184802-20261019-v1/owner-run/manifest.json`.
Final task schedule:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v4/manifest.json`.

Placement and pre-route physical optimization completed; routing is current.
The exact runtime PHY pad/reset reviewer tools are
prepared, with 25 source/reader guards and Tcl completeness passed. They bind
the actual compiled runtime core/profile rather than the older fixed-clock
variant metadata. Scope: four common async-assert/release domains, 163 retained
FDPE pad reset copies, all 341 OSERDES/ISERDES endpoints, 10 clock anchors,
2,032 required routed reset paths across all four modes (retaining the existing
3 ns SERDES bound), 180 physical pad connections and nine high-Z disabled
buffers. Full 278-pin map, complete accelerator resources, USER2 and PCIe x8
are checked separately. Source tool preparation remains separate from actual
native routed qualification. The read-only owner is now admitted and waiting
for exact numerical-review completion/release; this is not a queued FPGA build.
`build/checks/runtime-pad-reset-review-preparation-c0184802-20261019-v1/manifest.json`.
The runtime PHY owner has 14 ownership guards in addition to 25 source/reader
guards. Current PID 1965434, unified session 54329; native collection
waits for all four exact numerical modes and owner release. A failed upstream
review refuses promotion without restarting implementation. Final DRC/methodology
and vendor/clock/reset contract disposition remains the active goal's next task.
Owner: `build/checks/runtime-phy-pad-routed-c0184802-20261019-v1/launch.json`;
receipt: `build/checks/runtime-phy-pad-routed-c0184802-20261019-v1/run/manifest.json`.
Current scheduled finalization tasks:
`build/checks/runtime-finalization-preparation-c0184802-20261019-v3/manifest.json`.

A fresh native probe of Vivado's actual saved-versus-active constraint behavior
found that repeated set_bus_skew definitions remain in write_xdc history while
report_bus_skew contains only the latest exact endpoint-pair definition. The
v1 wait-only reviewer was superseded before any native collection; its exact
PID was verified and only that waiter was stopped. No implementation/source
input was changed. Fresh v2 preserves all historical endpoint/budget checks,
then separately verifies the latest active endpoint/budget map and its complete
report inventory. Only reconcile() and its five new guards differ; collector,
other reader functions, setup/hold/pulse/route limits and worker are unchanged.
Actual probe: baseline 2 saved/2 active, repeated 4/2, later mode 6/2.
`build/checks/runtime-skew-active-constraints-probe-20261019-v1/manifest.json`;
`build/checks/runtime-routed-review-preparation-c0184802-20261019-v2/correction.json`.

Current implementation observation (19 October, 14:52 HKT): exact worker remains
live in route_design. Latest router timing is intermediate and still failing;
no final route/timing qualification exists. Congestion rerouting is active.
INFO: [Route 35-416] Intermediate Timing Summary | WNS=-2.007 | TNS=-7372.953| WHS=-1.824 | THS=-16843.096|
Targeted pre-route CDC findings are recorded separately. Preserve the unchanged
implementation through final disposition; the image is not ready to program.
`build/checks/runtime-implementation-observation-c0184802-20261019-v4/manifest.json`.

The c0184801 source is retired after exact reset-contract review reproduced
an unexpected-memory-lock-loss case: SmartConnect control reset asserts for
16 AON cycles, but the directly connected core AXI endpoint remains out of
reset for the entire interval. Its controller takes RUN to FAULT without
asserting compute_reset. AMD PG247 requires reset intervals to overlap across
the interconnect and its directly connected masters/slaves; ordering may differ.
This is an exact source-prefix counterexample, not an observed silicon failure.
The earlier 15 conditional Critical-purpose dispositions did not waive this
separate reset-coherence gate. All earlier receipts and source inputs are retained.
Spec: https://docs.amd.com/r/en-US/pg247-smartconnect/Resets
Evidence:
`build/checks/runtime-smartconnect-reset-overlap-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-c0184801-reset-contract-rejection-20261019-v1/manifest.json`.

c0184802 adds the registered shared control_reset to compute_arst. The focused
counterexample passes with that predicate. The new complete source differs
only in this predicate and its distinct BUILD_ID literal; all other selected
42-file accelerator/top bytes, the three permission publisher FFs, 313-port
BD boundary, JTAG/PCIe, 4 GiB, four clock modes, lane/ECC mapping and startup
firmware are retained. Global-only participant/rate-counter and accepted
Clocking Wizard transaction ownership remain independent. This keeps the core
endpoint reset whenever SmartConnect is flushed without resetting the AON
configuration engine.
Source preparation:
`build/fedora-vivado/spare-runtime-reset-coherence-c0184802-20261019-v1/manifest.json`.
The exact full native integration test finished successfully; unified
session 96302 is closed. Historical checker PID 1936593 and exact launch:
`build/checks/runtime-reset-coherence-c0184802-traffic-preparation-20261019-v1/launch.json`;
`build/checks/runtime-reset-coherence-c0184802-native-traffic-20261019-v1/manifest.json`.
The checker is byte-identical to the prior frozen checker; only two expected
identity literals changed in its private bench. Source generation initially
counted all 45 .sv files instead of the selected 42 (three unused top variants).
That count guard was corrected before launch; no source bytes changed for it.
The initial source preparation required matching normal project/host tools
and new exact source synthesis/complete CDC/all-mode review; progress on
those gates is recorded below. No qualification transfers from c0184801;
no bitstream implementation is admitted or queued. The active OpenTPU goal
owns native completion review and preparation of the next source gates.
This does not affect qualified c0182663 or permanent c0182863.

The c0184802 complete native integration model finished exit 0, all 12 cases.
Modes 2/3/1/0 activated through epochs 1..4; each retired five instructions
and matched all 32 fresh ISA output words. Both actual host frontends, CH0/CH1
native transfers, accepted-response drain, partial native write tails and
in-flight accelerator reads passed in the modeled vendor/DDR environment.
Independent exact-correction/source review passed, including all 42 frozen
files and the two allowed top changes; six review guards passed. No actual
vendor/DDR/physical qualification is inferred. Review:
`build/checks/runtime-reset-coherence-c0184802-native-review-20261019-v1/run/manifest.json`.

Fresh source synthesis/netlist collection is admitted and actually started;
implementation remains refused. Exact worker PID 1939770, unified session
79935, job SHA256
`0e8734feb1ad604a207f81bc3c9552b2402e8c3eaad58489e19f5ab41a4e9391`.
Absolute paths are recorded in the current launch; the first attempt supplied
a relative --job path, so Vivado could not open its Tcl file and no synthesis
run began. That failed receipt is preserved under run/ with
startup-path-disposition.json. The unchanged job/worker was launched with
absolute paths into fresh run-v2/; a native run-begin marker was verified.
No implementation or hardware was accessed. Current owner/receipt:
`build/fedora-vivado/runtime-netlist-c0184802-20261019-v1/launch.json`;
`build/fedora-vivado/runtime-netlist-c0184802-20261019-v1/run-v2/manifest.json`.
The fresh source-project audit passed with no Errors/Critical warnings and
confirmed retained implementation exclusion, late Tcl synthesis observer,
correct c0184802 generics and fastest synthesis envelope. Snapshot/worker
inputs are immutable. Higher-priority c0182663's exact finalization owner and
all children are terminal/released; the source worker retains the 11 GiB
available-memory gate. There is still no admitted bitstream implementation.

On exact collection completion, the active OpenTPU goal owns immediate current-
source publication, reset, full 256-bit control and complete CDC disposition,
plus all four static clock/Gray views. Prepare matching c0184802 host identity
while synthesis runs. Earlier-source reviews are dependency/reference evidence
only. Current pointer:
`build/handoffs/runtime-reset-coherence-correction-current-20261019.json`.

The matching ordinary runtime host sources now require c0184802 and the shared
control/core reset proof. A reviewed source receipt must explicitly include
shared_control_endpoint_reset; host metadata must bind the corresponding
shared_control_compute_reset_clamp. Every existing artifact/complete CDC/
four-mode/source/firmware/model/program-readback gate remains. Both retired
runtime identities are rejected before opening hardware. The 26 preceding
host/tool/test files were preserved before edits; they are historical evidence
only and do not qualify the new image. No active synthesis input was modified.

Offline checks passed: 27 host protocol, 81 transport (including eight new
missing/false reset-proof cases), 47 model/backend and 10 retired-identity
cases. Both exact DDR firmware/CPU proofs and CSR/PHY data are bound to the
new normal top; exported nine small source/data files total 93,700 bytes.
The actual trained TinyStories 15M/tile128 checkpoint/compiler/ISA run passed
eight tokens in each requested mode 0/1/3/2, with compute-only continuation
and destructive-DDR context restart. Initial image remains 28,909,056 bytes,
SHA256 74facccd6c0e3f7e76676617a3b7a4074c1efb784d675ac1b5bdb08dca980950.
This export cannot open a device and is not a reviewed runtime image. No
physical inference, clock transition or bandwidth result is inferred.
Evidence:
`build/checks/runtime-c0184802-host-preparation-20261019-v1/manifest.json`;
`build/handoffs/runtime-host-c0184802-mode-data-20261019-v1/manifest.json`;
`build/checks/runtime-model-reference-c0184802-20261019-v1/manifest.json`.

A read-only automatic review owner is running, unified session 70265. It pins
the exact c0184802 source worker/job, fresh 256-bit source contract, strict
publication reviewer and complete row/summary parser. Thirteen publication
controls and eight owner-state checks passed. It waits for the successful
native source receipt AND release of the exact source process before starting
owned-control/publication review and complete CDC inventory. Any failure
gets a technical-disposition receipt; it cannot restart synthesis or waive CDC.
Current owner:
`build/checks/runtime-c0184802-review-owner-20261019-v1/launch.json`;
`build/checks/runtime-c0184802-review-owner-20261019-v1/run/manifest.json`.

A second read-only owner, unified session 25392, waits for that exact review
owner's successful receipt and process release. It derives every Critical
receiver from the new inventory and explicitly adds both core reset assertion
stages plus mode/permission inputs. It will collect fresh native startpoints
and verify that control_reset_reg/C is an actual AON FDRE source of BOTH
core-reset PRE pins, sharing the same assertion driver. No earlier cone count
or source qualification is reused. Failure produces a technical-disposition
receipt; no synthesis restart or hardware operation is possible. Owner:
`build/checks/runtime-c0184802-reset-cones-owner-20261019-v1/launch.json`;
`build/checks/runtime-c0184802-reset-cones-owner-20261019-v1/run/manifest.json`.

The c0184802 four-mode source clock/Gray collector tools are prepared from
the previously validated idempotent clock helper and unchanged rate helper.
Only current source/checkpoint paths and marker identity changed. They are
prepared tools, not an admitted or queued Vivado build. Exact successful
current source, publication/inventory and reset-fanin prerequisites remain
required before collection; routing/physical qualification is separate.
`build/checks/runtime-full-static-views-c0184802-20261019-v1/preparation.json`.

The exact four-mode collection/review owner is now running and waiting for the
current native shared-reset proof and that owner's release. Unified session
39781; its worker pins the current source/review/probe identities and tools.
It will create a fresh collection job from the actual current DCP hash, collect
all 64 clock observations and 256 Gray paths, then immediately run the exact
independent reviewer. Fourteen reader/helper controls passed; old fixture data
is used only to test the reader, not to qualify c0184802. Original and final
saved bounds, all actual C/Q/D path sets, DDR quadrature and helper-delta checks
remain unchanged. Complete CDC, routed timing and physical transitions are
not waived. This is a read-only source analysis owner, not a queued FPGA build.
Owner and current receipt:
`build/checks/runtime-full-static-views-c0184802-20261019-v1/launch.json`;
`build/checks/runtime-full-static-views-c0184802-20261019-v1/owner-run/manifest.json`.

Complete c0184802 source synthesis passed exit 0. All native IP/main run
receipts have zero Errors/Critical warnings; logic optimization reported 460
ordinary warnings, which are not a full CDC disposition. The actual synthesis
clock observer verified compute 6.718 ns and memory 7.500 ns. Saved complete
source checkpoint SHA256:
29a4407c508eb6889f695a2f04884b321b3976a7929ed51effde4f0d124fad7a.
Linked collection is the next current phase; its successful final receipt and
owner release remain required for the waiting exact reviewers. Completion:
`build/checks/runtime-c0184802-source-synthesis-completion-20261019-v1/manifest.json`.

The ordinary synthesis log has now been inventoried separately. Its internal
summary reports 460 warnings, while 722 literal WARNING lines span repeated
compiler phases. The preceding source reports 592 internally, also with 722
literal lines and the same per-ID line counts. Several IDs are explicitly
capped at 100 messages, so identical log counts cannot establish complete or
equivalent findings. The 40 changed literal warnings comprise one identical
48-to-17 trim with only a hierarchical label change, plus 39 constant-port
messages from different capped subsets. No image qualification or CDC waiver
is inferred. All current numerical/netlist/source/routed gates remain.
`build/checks/runtime-c0184802-synthesis-warning-inventory-20261019-v1/manifest.json`;
`build/checks/runtime-c0184802-synthesis-warning-inventory-20261019-v1/interpretation.json`.
The linked collector has exported register and control-pin tables and is now
running the complete detailed CDC report. Exact owners remain live; do not
replace the source or restart synthesis based on quiet report output.


The strict current mode-3 held-payload/Gray reviewer is prepared with 17
passing controls. Its numerical/endpoint/parser functions are unchanged;
only run-v2 artifact paths differ and the old source-specific CLI is omitted.
Old actual fixture data tests the reader only, not the new image. A read-only
owner, session 37697, waits for current source/publication/inventory AND the
actual shared-reset native binding, then runs the exact current-artifact review.
It cannot waive unrelated CDC or authorize synthesis, implementation or hardware.
`build/checks/runtime-selected-cdc-c0184802-preparation-20261019-v1/manifest.json`;
`build/checks/runtime-selected-cdc-c0184802-preparation-20261019-v1/launch.json`;
`build/checks/runtime-selected-cdc-c0184802-preparation-20261019-v1/owner-run/manifest.json`.

A fresh exact c0184802 reset-release component passed all 144 cases and both
behavioral negative controls. The top fragment was extracted byte-for-byte
from the current normal source and matched the actual synthesis snapshot.
The bench changes only the shared-control-flush expected mask: 0x041 (core
and PCIe Lite), replacing the old 0x040 (PCIe Lite only). All four clock modes,
four assertion phases and nine reset sources were exercised, including 16
shared-control-flush cases. Stopped clocks hold reset; release needs two local
edges. Real rate counters remain global-reset-only. This is logical component
evidence; native reset-purpose, recovery/removal/pulse, coherent vendor reset
and physical gates remain separate. Evidence:
`build/checks/runtime-reset-release-c0184802-20261019-v1/run/manifest.json`.

Exact c0184802 linked collection and source publication/control review passed.
All 256 owned annotated bits and 129 direct stage/reset/clock connections are
bound; all three AON permission publishers feed their eight intended inputs.
The new complete report reconciles 1,650 rows: 15 Critical/1,635 Warning in ten
clock pairs. No prior-source inventory is substituted. The native current
probe collected 20 targets/94 startpoints and verified control_reset_reg/C
as an AON FDRE source of BOTH core reset assertion stages with a shared driver.

Actual current source-purpose reviews passed conditionally: 1,137 selected
mailbox/Gray Warning rows, six asynchronous-reset Critical rows, two real
registered drain fanouts, the host-reset observer, two independently fenced
PCIe statuses and two independent core reset-held observations. Fresh 144-case
real-drain fanout, 64-case false-status and 18-case host-reset components plus
their behavioral negatives are bound; current six/eight/nine/eight native
review controls passed. The host-reset v1 reviewer accidentally read the
preserved failed-start run/ receipt; v2 changes only run-v2 artifact paths,
retains predicate/clock/endpoint guards and passed actual review. Preserve
that tool failure; it is not an FPGA defect or synthesis restart.

Current c0184802 ledger: 1,150 conditional rows; **2 Critical/498 Warning**
remain. The two Critical rows are the vendor BUFGCTRL clock selection.
A fresh exact current property probe is running; it will bind the actual
new frozen/compiled vendor pipe source to the unchanged 40-case primitive
component, not transfer image qualification. Four-mode native clock/Gray
collection has completed mode 0 and remains active. Other CDC, complete
vendor reset/handshake, routed timing and physical gates remain mandatory.
Evidence:
`build/checks/runtime-cdc-remaining-c0184802-20261019-v1/manifest.json`;
`build/checks/runtime-reset-coherence-netlist-final-c0184802-20261019-v1/manifest.json`;
`build/checks/runtime-c0184802-reset-cones-owner-20261019-v1/run/manifest.json`;
`build/checks/runtime-vendor-clockmux-c0184802-20261019-v1/run/manifest.json`.

Subsequent current reviews completed: the actual current BUFGCTRL properties
and both frozen/compiled vendor pipe source bytes match the retained 40-case
primitive component; six native guards passed. Mode/permission/temperature
purpose and eight guards passed. Fresh combined native payload collection
and structural review passed all 496 selected rows, 1,262 endpoints, 491
supplied 4 ns timing paths, 25 local enable sources and 317 receiver/control
stage targets. Thirteen structural guards passed. Quantizer source and actual
e_nz FDRE retention were verified in this current netlist, without importing
other-image timing or hardware qualification.

All four complete-source static clock/DDR phase/Gray views and the immediate
independent review passed (64 clock observations, 256 paths; 14 reviewer
controls). All 28 exact analysis warnings were scoped: 24 explicit clock-view
messages and four repeats of one native typed-GROUND net with one physical
GND/G leaf driver and no external input. The fresh constant proof and six
binding guards passed. Other timing/CDC is not waived by that warning finding.

The vendor payload runtime-contract reviewer binds the actual generated BD,
all three interface clocks, shared control/core endpoint reset, DATA reset/
abort ownership and real source/tail fences. The original checker counted one
PCIe-held-reset user where both the guard and participant legitimately use it;
v2 fixes only that multiplicity, preserves the failed receipt and passed eight
controls and actual review. Generated SmartConnect/XPM internals are accepted
under the explicit vendor IP integration contract, not formally proved here.
Coherent reset/pulse requirements, independent-reset limitations and all
routed/physical acceptance remain mandatory. No fixed-image management-reset
exclusion was imported.

Current c0184802 source ledger: all 1,650 rows assigned exactly once,
conditionally; zero unassigned source rows. This is NOT complete routed CDC
or physical qualification. Native implementation input audit is now running
against an exact copied full linked checkpoint. Its first checker used the
file-derived current-design NAME as though it were the RTL top. Native
inspection showed NAME checkpoint_source-linked and TOP otpu_fpga_top_runtime;
a fresh audit asserts TOP while retaining part/clock/interface/hierarchy/
voltage checks. Source, constraints and checkpoint bytes are unchanged.
No implementation is admitted until that exact audit passes.
Evidence:
`build/checks/runtime-cdc-remaining-c0184802-20261019-v4/manifest.json`;
`build/checks/runtime-full-static-views-final-c0184802-20261019-v1/manifest.json`;
`build/checks/runtime-vendor-payload-reset-contract-c0184802-20261019-v2/run/manifest.json`;
`build/fedora-vivado/runtime-implementation-c0184802-20261019-v1/input-audit-correction.json`.

The corrected native input audit passed exit 0. Native design TOP is the full
otpu_fpga_top_runtime; its file-derived NAME is checkpoint_source-linked.
The actual input retains the exact part, five mandatory clocks, full source
hierarchy, JTAG USER2 and eight exact PCIe GTX lane locations plus configuration
voltage. The full implementation was immediately admitted from the exact
copied linked checkpoint, without restarting synthesis or changing RTL,
clocks, lane/ECC mapping, firmware or constraints. All 1,650 current source
rows are assigned once conditionally; four source clock/Gray views and
current native/source/host gates are pinned by the immutable ticket.

Implementation worker is live, unified session 70051, PID 1953057; native
Vivado PID 1953524. Exact job SHA256:
7b130359c34bc1af18ea27d1c29c81c9cb5226a4245b34dfff4b119f51b63878.
It retains the 11 GiB available-memory admission gate, current input hashes
and phase records. The initial inline preparer failed on a string/Path helper
before writing any job; the persisted preparer normalizes every path and
passed all gates. That preparation failure is retained separately.
Current implementation operation is recorded by the worker, not inferred
from an old manifest; verify identity before declaring live/terminal.
`build/fedora-vivado/runtime-implementation-c0184802-20261019-v1/launch.json`;
`build/fedora-vivado/runtime-implementation-c0184802-20261019-v1/run/manifest.json`;
`build/fedora-vivado/runtime-implementation-c0184802-20261019-v1/admission.json`.

The workflow optimizes, places, physically optimizes and routes the complete
runtime design, retains checkpoint/report failures, and applies the existing
PCIe userclk1 margin repair without relaxing timing. It stops at an exact
routed checkpoint for review: no bitstream generation, hardware access or
flash is admitted by this worker. The active OpenTPU goal owns preparation
and immediate execution of all-four-mode routed setup/hold/pulse/CDC/Gray/
reset/source/IO review, final disposition, then bitstream creation/CRC/package
and the already authorized exact-image SRAM tests. Those remain separate
milestones; permanent c0182863 and volatile c0182663 are unchanged.

Observed implementation milestone (2026-10-19T05:24:56.110535+00:00): opt_design
completed and place_design started; the native log reached IO/clock placement
and placer netlist model construction. The canonical refresh now includes this
exact runtime job and reports one active implementation. This is placement
progress, not timing closure, a ready bitstream, or hardware qualification.




A current six-reset-purpose reviewer is prepared against these new component
results and the fresh native cone data; it has not run before those current
artifacts and ownership prerequisites succeed.




Latest synthesis observation (2026-10-19T04:23:27.325390+00:00): all eight generated IP runs
have end markers without error markers. The main top was 12m46s into
synthesis after those prerequisites; native PID 1943483 was using 102% CPU,
with two active optimization children at 73.1%/75.9%. This is an observed
process/milestone record, not an ETA or a claim based only on old log text.
No placement, routing or bitstream generation has started. Recheck the exact
source receipt/owner before reporting a later state. Observation:
`build/checks/runtime-c0184802-host-preparation-20261019-v1/synthesis-observation.json`.




Normal source/project tools now emit c0184802, require both registered
permission publication and the shared control/core reset clamp, and reject
both retired identities for new assembly. Nine identity controls passed.
The freshly generated normal top and private correction match all 42 selected
RTL files byte-for-byte. Normal project assembly and an independent 43-check
source/guard audit passed; the fresh control inventory contains 12 instances,
54 annotated members and 256 bits. No source synthesis or implementation ran
as part of assembly. Matching host identity remains to be updated.
Evidence:
`build/checks/runtime-c0184802-normal-tool-preparation-20261019-v1/manifest.json`;
`build/checks/runtime-project-c0184802-source-review-20261019-v1/manifest.json`;
`build/checks/runtime-control-source-c0184802-20261019-v1/manifest.json`.
The complete source validation snapshot is prepared. Its first read-only
audit failed because the preparation used a non-checksum placeholder and
left its observer file absent; this is a preparation failure, not an FPGA
finding. The exact hook checksum guard refused that placeholder. A fresh
audit-work-v2 used a valid checksum and an absent permit marker; its
source-project/hook-property audit passed and session 59560 is closed.
The audit could not admit synthesis; original failed logs are preserved.



**Current priority: c0182663 exact offline review/package and local JTAG
TinyStories acceptance passed; permanent-flash preparation is complete.**
Both numerical gates passed: setup +0.006 ns, hold +0.011 ns, zero failing
setup/hold/pulse endpoints and all 334,737 routable nets complete. Exact
artifact/CRC/CDC/Gray/source/boundary disposition and packaging passed.
Bitstream SHA256:
`a1571e696d510d4b19adc59534872ceef48398036134d817f00b6b2ebb232acc`.
Package: `bitstreams/spare-dual-host-4gb-c0182663`.

**Current hardware: c0182663 volatile SRAM; workload idle and JTAG released.
Permanent c0182863 is unchanged.** SRAM verification, live identity, automatic eight-/
nine-lane startup, fresh ISA/preflight and full 4 GiB initialization passed.
All 2,048 initialization counters were retained and audited. Native fetch
matched 1,371 instructions/65 words in 1,503 cycles; matmul matched all 32
words/five instructions in 336 cycles. All 28,909,056 model bytes were uploaded
and read back exactly. Eight exact ISA tokens, 15 program readbacks and 13
model-program retired counts passed, followed by independent receipt review
and public-runtime live startup/ECC checks. Native read median: 4.452521 GB/s,
1.4883x the two-channel c0182600 benchmark; this does not establish PCIe or LLM
decode speed. The benchmark replaced program/output memory. Qualification:
`build/checks/c0182663-local-qualification-20261019-v1/manifest.json`.
Original workload evidence:
`build/hardware/tinystories-c0182663-20261019-v1/manifest.json`.

Permanent MCS/command and no-hardware flash preflight passed. Exact-image
program/independent-verify/boot approval is pending; no authorization file or
permanent write was made. Existing skip-backup preference is retained:
`build/handoffs/c0182663-permanent-preparation-current-20261019.json`.
Mac PCIe/LFM/Qwen acceptance and cold/warm repeats remain pending.

Mac runtime/guide: 20 local files, 200,221 bytes; 37 offline guards and ordinary
checkout/installed preflight passed. Uncommitted/unpushed; Mac pull cannot
retrieve them yet. Inventory:
`build/handoffs/c0182663-mac-runtime-current-20261019.json`.

**Active runtime source correction: c0184801.** The prior unregistered
permission decoder is retired after a WAIT_CAL -> INITIALIZE output-skew
counterexample captured premature permission in 12/80 receiver phases. The
registered candidate captured none and retained legal progress in all 80.
This is source/timing-sensitivity evidence, not observed DDR corruption.
Three AON permission registers now precede cross-domain receivers; both hosts,
4 GiB, clocks, lane/ECC mapping and full accelerator are retained. Only the
full top and distinct source identity differ. Full 42-file/313-port native
integration simulation and scoped review passed all 12 cases, four epochs and
four exact 5-instruction/32-word ISA numerical runs with unchanged model scope;
actual vendor/memory/clock bodies remain separate. Unified session 98092 finished
exit 0. Simulation/review:
`build/checks/runtime-admission-c0184801-native-traffic-20261019-v1/manifest.json`.
Normal c0184801 source project assembly and independent 41-check audit passed;
six identity controls also passed. No implementation is admitted. Matching host
identity/tool binding is prepared; full CDC/all-mode routed/physical gates remain.
Fresh complete-source synthesis, linked collection and owned/publication
netlist review passed after 35 guards and actual private-project audit. Service
`opentpu-runtime-netlist-c0184801-20261019-v1.service`, PID 1919861, invocation
`1bdbea41cc974c5dadcd7a5b88aea003`; 551 frozen/153 original inputs remain pinned.
No full bitstream implementation is admitted. Matching c0184801 host identity,
normal source/data export and offline compiled TinyStories ISA path are prepared:
27 protocol/73 transport/47 backend cases plus five retired-identity guards
passed; eight real-checkpoint ISA tokens were produced in each mode segment
0,1,3,2. Nine exported source/data files total 93,548 bytes plus metadata.
This source data is not a reviewed package and cannot authorize hardware access.
Prior host sources were preserved byte-exact for retired-source references;
no old-source qualification transfers. Current host proof:
`build/checks/runtime-c0184801-host-preparation-20261019-v1/manifest.json`.
Export: `build/handoffs/runtime-host-c0184801-mode-data-20261019-v1/manifest.json`.
No physical transition or model performance result is inferred.
Current: `build/handoffs/runtime-admission-correction-current-20261019.json`.
Owner/receipt: `build/fedora-vivado/runtime-netlist-c0184801-20261019-v1/launch.json`.

Fresh c0184801 full-source synthesis passed with exit 0, zero Errors/Critical
Warnings and actual analysis clocks compute 6.718 ns / memory 7.500 ns. Saved
source checkpoint SHA256:
`3d35c32d403e0c26e7c2718ff6734e471ac171d624c5be1ff16ceae4b3e83569`.
Exact linked collection and the owned/publication review also passed; no
implementation is admitted. This source checkpoint does not qualify routing or hardware.
Clock observation evidence:
`build/checks/runtime-c0184801-source-clock-observation-20261019-v1/manifest.json`.

Fresh c0184801 netlist review is prepared and assigned to the active OpenTPU
owner immediately after the exact synthesis/collection succeeds. Thirteen
controls passed; the actual retired-source netlist was correctly rejected for
missing permission source registers, and premature execution was refused.
The prepared review checks three AON publication FFs, eight direct receiver
inputs, all 256 owned control bits and 129 stage connections. Actual new
netlist/full CDC/routed review remains pending. Preparation:
`build/checks/runtime-admission-netlist-review-c0184801-preparation-20261019-v1/manifest.json`.

The completed exact netlist/CDC review owner ran under
`opentpu-runtime-review-c0184801-20261019-v1.service` (invocation
`978bf481f62e4093a80ba2d937d890e0`, initial PID 1924031). Nine owner controls
passed. It checked the exact source process, waited for successful collection
and release, then passed the prepared netlist review and complete CDC
inventory. It could not implement or access hardware. Completed owner/receipt:
`build/checks/runtime-c0184801-review-owner-20261019-v1/launch.json`;
`build/checks/runtime-c0184801-review-owner-20261019-v1/run/manifest.json`.

The real PCIe control guard, PCIe source drain participant and held drain
join passed 64 false sampled-status cases (four modes/four phase offsets).
False idle/closure could not bypass the real outstanding-response/admission
proof; loss of sampled idle failed closed. A deliberately bypassed source-ack
negative control correctly failed. These are source-bound component tests
with DMA/core/memory otherwise idle and no PCIe reset or metastability model;
they grant no complete CDC/routed/hardware approval. Receipt:
`build/checks/runtime-pcie-status-fence-20261019-v1/run/manifest.json`.

Exact c0184801 complete source synthesis and linked collection finished with
exit 0; both source and automatic review services are inactive/MainPID 0. The
actual owned-control/publication review passed all 256 bits/129 stage links
and three source FFs/eight receivers. All 1,650 CDC rows were inventoried:
15 Critical/1,635 Warning. Relative to the retired-source report, exactly four
admission CDC-10 rows disappeared and one three-bit permission CDC-6 warning
was added; the new bus warning remains open. The new exact mode-3 review
reverified 1,136 held payload bits and 64 Gray scalar paths against current
C/Q/D pins and saved numerical constraints. It conditionally accounts for
1,137 findings; 513 remain open (15 Critical/498 Warning). No qualification
was imported from the retired source. Current receipts:

- `build/checks/runtime-admission-netlist-final-c0184801-20261019-v1/manifest.json`
- `build/checks/runtime-complete-cdc-inventory-c0184801-20261019-v1/manifest.json`
- `build/checks/runtime-selected-cdc-c0184801-20261019-v1/manifest.json`
- `build/checks/runtime-cdc-remaining-c0184801-20261019-v1/manifest.json`

Read-only native critical-cone collection completed on the exact new
linked checkpoint: all Critical receivers, two mode bits and three publisher
D inputs (19 targets). Service
`opentpu-runtime-cdc-cones-c0184801-20261019-v1.service`, initial PID 1925168,
invocation `9cdac961d84649be9672dbda682e662a`. Owner/current receipt:
`build/checks/runtime-cdc-critical-cones-c0184801-20261019-v1/launch.json`;
`build/checks/runtime-cdc-critical-cones-c0184801-20261019-v1/run/manifest.json`.

The new native critical/mode/publication cone collector completed with
exit 0, zero Errors/Critical Warnings, 19 targets and 88 startpoint records;
its service is inactive/MainPID 0. Immediate publisher input-domain review
passed all 47 D-cone startpoints (17/15/15): every source is a registered AON
50 MHz clock pin. Six missing/duplicate/clock/class/startpoint negative guards
passed. Combined with the actual three source FFs/eight direct registered-Q
receiver bindings, this supports the addressed decoder repair. Routed AON
setup/hold and the new permission-bus warning remain separate open gates.
Receipt: `build/checks/runtime-publication-source-domain-c0184801-20261019-v1/manifest.json`.

Full c0184801 checkpoint static-mode analysis and its review completed: four complete
clock/DDR phase views and 256 source-period Gray paths. Source synthesis is
not restarted and no implementation or hardware is touched. Original v1
analysis failed at Constraints 18-851 because the full linked checkpoint
already held named user-generated clock views. This is a helper/context
failure, not a synthesis/design rejection. The failed receipt is preserved.
Fresh v2 guards only the redundant rename in its private analysis helper;
all other text and numerical/source/ancestry/DDR/Gray checks are unchanged.
Current service `opentpu-runtime-full-static-c0184801-20261019-v2.service`,
initial PID 1925764, invocation `f4c80fd4fa5142ae921b02b92a9a644a`.
Owner: `build/checks/runtime-full-static-views-c0184801-20261019-v2/launch.json`.
Receipt: `build/checks/runtime-full-static-views-c0184801-20261019-v2/run/manifest.json`.
Correction: `build/checks/runtime-full-static-views-c0184801-20261019-v2/correction.json`.
The active OpenTPU goal owns exact independent review immediately on completion;
routed numerical timing, full CDC and actual physical transitions remain open.

All four complete-source static timing views finished successfully, and
exact independent review passed: 64 clock/DDR phase observations and 256
registered Gray paths. Both original mode-3 and final selected-mode numerical
bounds/clock definitions were retained and checked. Fourteen reader/binding
controls passed. A test import-path collision was corrected by restoring the
parser search path; prior review/test receipts remain preserved. Current final:
`build/checks/runtime-full-static-views-final-c0184801-20261019-v3/manifest.json`;
preparation/tests: `build/checks/runtime-full-static-views-review-c0184801-preparation-20261019-v3/manifest.json`.
Source synthesis and placement/routing were not repeated. This qualifies only
full-source clock/Gray timing objects, not complete CDC, routed numerical
timing or physical transitions. All 28 native warnings were inventoried:
24 deliberate clock-view warnings are accepted in this exact analysis scope;
four repetitions of the vendor refclk_buf constant-net warning still need
separate current native driver evidence. Warning inventory:
`build/checks/runtime-full-static-views-c0184801-20261019-v2/warning-inventory.json`.

Registered drain-request fanout review conditionally accounts for exactly
two Critical CDC-11 rows. The actual common AON Q, both two-stage PCIe chains
and real DMA tail/participant/join coupling were checked. The tail requires
closed admission and completed accepted headers/W/B/R state; the other request
copy cannot bypass it. All 144 real-RTL skew/release cases passed, and bypassing
the real tail correctly failed. This is conditional source/structural review
under the held four-phase protocol, not an unbounded metastability proof or
a waiver of reset/abort/routed/physical gates. Current evidence:
`build/checks/runtime-drain-fanout-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-drain-fanout-disposition-c0184801-20261019-v1/run/manifest.json`.
The updated ledger has 1,139 conditional findings and 511 still open:
13 Critical/498 Warning. Original 513-row ledger is preserved. Current:
`build/checks/runtime-cdc-remaining-c0184801-20261019-v2/manifest.json`.
No full CDC or bitstream implementation admission is granted.

The first exact vendor constant-net probe finished exit 1 because the
optimized net had no physical leaf-driver pins. Its failed receipt is retained;
this is a representation/diagnostic blocker, not evidence of a logic conflict.
Completed v2 collected actual properties and diagnostic segment/port/driver counts and driver
classes from the same unchanged linked checkpoint. It grants no warning/CDC
approval by collecting properties. Unified exec session 34166, initial worker
PID 1927966/start ticks 72662236. Current owner:
`build/checks/runtime-vendor-constant-c0184801-20261019-v2/launch.json`;
receipt: `build/checks/runtime-vendor-constant-c0184801-20261019-v2/run/manifest.json`.
Do not restart on observation timeout; inspect this exact session/worker.
This read-only diagnostic cannot configure hardware or implement a design.

Vendor constant v2 property collection completed exit 0 and observed
`TYPE=GROUND`, `DRIVER_COUNT=3`, `PIN_COUNT=2`. Its zero segment/leaf-driver
counts came from the diagnostic querying segments using a net object; those
counts are not accepted as proof of absent physical drivers. This is a probe
query defect, not an image rejection. Fresh v3 uses the actual pins, includes
the exact target net explicitly, and rejects an empty pin/segment collection.
Unified exec session 91554, initial worker PID 1928140/start ticks 72677873.
Current owner: `build/checks/runtime-vendor-constant-c0184801-20261019-v3/launch.json`;
receipt: `build/checks/runtime-vendor-constant-c0184801-20261019-v3/run/manifest.json`.
All prior properties/failures are preserved. No constant-net warning approval
is granted until the corrected current facts are reviewed.

Corrected constant-net v3 collection and its immediate final review passed.
The actual nonempty net/segment collection has `TYPE=GROUND`, two pins, no
external input driver and exactly one physical `GND/G` leaf driver. The
reported DRIVER_COUNT remains three; no conflicting physical logic driver
was found. Six empty/missing/duplicate/type/external/logic-driver checks
passed. The four repetitions of this exact warning are dispositioned for
the same checkpoint used in all static views. All 28 static-view warnings
are now accounted for within their clock/one-ground-net scope. Evidence:
`build/checks/runtime-vendor-constant-c0184801-20261019-v3/final-disposition.json`;
`build/checks/runtime-vendor-constant-c0184801-20261019-v3/review-preparation.json`.
Unified session 91554 finished exit 0 and is closed. No Vivado/source worker
is left running by these tasks. Earlier diagnostic query defects/facts and
clock-review failures remain preserved. Source implementation stays guarded;
511 CDC findings remain open (13 Critical/498 Warning), including reset,
status, metadata/permission and vendor/boundary findings. Other vendor/routed/
physical gates have not been waived.

Current fast quantizer source matches the qualified registered-predicate
source SHA256 `346fab71ab5f7106b515c2ea311196d7792ff98ea8bcc9a2d89c09d4b994c6d8`.
The actual current netlist retains `u_sys/u_board/u_slice/u_quant/e_nz_reg`
as FDRE on runtime_compute. This is source/structural retention only, not
older-image timing/hardware qualification: `build/checks/runtime-quantizer-retention-c0184801-20261019-v1/manifest.json`.

The selected eight reset chains were extracted byte-exact, with both real
rate-counter modules retained (WINDOW_CYCLES=32 only for reset tests). All
144 stopped-clock assertion/hold/two-edge release and counter-ownership cases
passed across four modes/nine reset sources/four stimulus delays. Two deliberate
asynchronous-release/managed-counter-reset violations were caught. Six exact
Critical PRE findings were conditionally dispositioned against actual shared-
preset FDPE pairs, constant enables, zero-first-stage/direct-Q release and
current raw source cones. Six binding guards passed. This does not qualify
analog pulse widths/metastability, routed recovery/removal/interstage timing,
full accepted-transaction reset coherence or physical transitions. Receipts:
`build/checks/runtime-reset-release-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-reset-disposition-c0184801-20261019-v1/run/manifest.json`.
Current ledger: 1,145 conditional findings; 505 still open (7 Critical/498
Warning). All prior ledgers remain preserved:
`build/checks/runtime-cdc-remaining-c0184801-20261019-v3/manifest.json`.

Read-only native vendor clock-mux property collection completed on the exact
current checkpoint, for both CDC-13 rows: actual BUFGCTRL/launch register,
control pins and fanin. It grants no vendor finding approval. Unified exec
session 17027, initial worker PID 1930203/start ticks 72832804. Owner/current
receipt: `build/checks/runtime-vendor-clockmux-c0184801-20261019-v1/launch.json`;
`build/checks/runtime-vendor-clockmux-c0184801-20261019-v1/run/manifest.json`.
Inspect this exact session/worker; never restart solely on observation expiry.
The worker reuses a read-only property-collector body whose legacy scope text
says constant-net; its actual ticket/Tcl/markers/targets are clock-mux-specific.
No source synthesis or bitstream implementation/hardware operation is started.

Vendor clock-mux collection completed exit 0 and was reviewed immediately.
The actual dedicated BUFGCTRL has both enables high, both IGNORE inputs low,
all relevant inversions disabled and native SIM_DEVICE=7SERIES. S1 comes
directly from its registered selector; source/fanin and output-clock feedback
match the compiled vendor RTL, whose S0 is complementary. Both frozen and
actual compiled pipe-clock sources have SHA256
`71f0390788ba91529871d810c057cc04a3a9dad3aebfeadc6d36a7d013d212c9`.
The vendor selector changes only when all eight synchronized lane requests
agree; otherwise it holds the existing selection. This is lane consensus,
not an eight-cycle timer. The verbatim selected logic and installed vendor
7SERIES BUFGCTRL/glbl model passed 40 cases across ideal 125/250 MHz phase
offsets, mixed lane requests and source-level reset. A deliberately substituted
fabric mux produced a one-ns pulse and correctly failed. Zero-time functional
scheduling events are ignored; no physical pulse/jitter claim is made.
Six native-property/pin binding guards passed. Exactly two vendor CDC-13 rows
are conditionally dispositioned for this dedicated clock-control purpose;
GT/MMCM/XDMA body, link/reset, routed clock/pulse and physical acceptance
remain mandatory separate gates. Evidence:
`build/checks/runtime-vendor-clockmux-model-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-vendor-clockmux-disposition-c0184801-20261019-v1/run/manifest.json`.
Unified session 17027 finished exit 0 and is closed. At this review stage,
the ledger had 1,147 conditional findings and 503 open (5 Critical/498 Warning):
`build/checks/runtime-cdc-remaining-c0184801-20261019-v4/manifest.json`.
No source/Vivado worker is left running by these checks, and no bitstream
implementation or hardware programming has started.

Current vendor/boundary payload native collection completed successfully: 491 DMA
FIFO payload warnings (five PCIe S00 channel nodes: AR105/AW105/W148/B2/R131),
four 32-bit SmartConnect control payload warnings and one 12-bit temperature
bus warning. This covers 496 warning rows and 1,262 scalar source/receiver
endpoints, including actual cell/clock/enable/data facts and 491 source timing
requirements. Source clock pairs for the DMA FIFO paths are PCIe userclk2
and the fixed independent 250 MHz host clock, not managed core/memory clocks.
No fixed-image review qualification or global-management-reset exclusion is
imported. Actual runtime reset/abort/drain and all routed/physical gates remain.
Unified exec session 77647 finished exit 0 and is closed; initial worker
PID 1931976/start ticks 72975217. No collection worker remains active.
Owner/current receipt:
`build/checks/runtime-vendor-payload-facts-c0184801-20261019-v1/launch.json`;
`build/checks/runtime-vendor-payload-facts-c0184801-20261019-v1/run/manifest.json`.
This is read-only source evidence collection, not implementation or hardware.
All collected input/output hashes were rechecked. Actual review has started:
1,262 cell facts, 1,262 clock facts, 1,542 control facts and 631 data facts;
all 491 FIFO source timing requirements are 4.000 ns. These are source
estimates, not routed numerical qualification. Review-start receipt:
`build/checks/runtime-vendor-payload-facts-c0184801-20261019-v1/review-start.json`.

The exact host-reset observer and two independently fenced PCIe status
findings now passed conditional source-purpose review. Host reset retained
two actual AON ASYNC_REG stages, the registered output and seven-bit
64-cycle hold counter. Eighteen real-RTL cases, shortened-hold/raw-output
negative controls and eight binding guards passed. The PCIe status predicates
contain only the expected 9/4 PCIe-clocked startpoints and two AON stages.
False sampled idle/closure cannot replace the separate real PCIe source
acknowledgment, local closed/idle predicates and actual DMA-tail proof.
The existing 64-case held-response test and bypassed-ACK negative are bound
to the exact synthesis source; nine further binding guards passed.
All native collection job/input/output hashes and the exact linked checkpoint
were independently verified. Evidence:
`build/checks/runtime-host-reset-hold-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-host-reset-disposition-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-pcie-status-disposition-c0184801-20261019-v1/run/manifest.json`.
The current ledger has 1,150 conditional findings and **500 still open
(2 Critical/498 Warning)**; the two Critical rows are duplicated core
reset-status observations. No bitstream implementation is admitted.
Analog pulse/metastability behavior, coherent accepted-transaction reset/abort,
routed interstage/predicate timing and physical transitions remain separate
mandatory gates. Arbitrarily short unobserved reset pulses are not promised
to trigger a restart. Current ledger:
`build/checks/runtime-cdc-remaining-c0184801-20261019-v5/manifest.json`.

The last two Critical source-purpose findings, duplicated core reset-held
observations, passed exact native binding and independent-consumer review.
Both copies launch from the actual registered compute Q and retain two AON
ASYNC_REG stages. The admission copy only inhibits access until memory is
permitted and resets are observed clear. The manager copy requires held reset
with actual drain release before configuration and cancels on lost proof.
They do not form an atomic data word. All three current manager RTL modules
are byte-identical to the retained 21-case component test, including missing
reset acknowledgment and proof-loss transaction-boundary cases; no prior
image qualification transfers. Eight new binding/consumer guards passed.
Current ledger: **1,152 conditional findings, 498 open Warning rows, zero
open Critical rows**. Every Critical disposition is conditional source scope;
no routed, DDR, vendor-body, coherent reset/abort or physical gate is waived.
No bitstream implementation is admitted. Evidence:
`build/checks/runtime-core-reset-fanout-disposition-c0184801-20261019-v1/run/manifest.json`;
`build/checks/runtime-cdc-remaining-c0184801-20261019-v6/manifest.json`.

Vendor-payload review found that the 491 FIFO payload endpoints reduce to
five distinct enable fanins with 25 actual sequential startpoints. The source
timing estimates have minimum slack +3.082 ns (4.000 ns requirement); this
does not qualify routing. A fresh read-only native probe now collects those
25 enable-source clocks, both stages of all four 32-bit vendor control payload
banks, and all three temperature sample stages: 317 scalar targets total.
Worker session 7658, initial native PID 1934479; verify launch identity and
latest receipt before reporting it live or terminal. Exact producer/owner:
`build/checks/runtime-vendor-payload-controls-c0184801-20261019-v1/launch.json`;
`build/checks/runtime-vendor-payload-controls-c0184801-20261019-v1/run/manifest.json`.
The worker and unified session 7658 finished exit 0 and are closed.
Immediate exact structural review completed: all 491 actual RAMD32-to-FDRE
data paths and all 25 local registered enable clocks match FIFO ownership;
all four 32-bit vendor payload banks retain both ASYNC_REG FDRE stages,
constant enables, inactive reset and exact source/first-Q data binding.
All 12 temperature bits retain two synchronizer stages and the third sample.
All producer job/input/output hashes were revalidated. Thirteen review guards
passed, rejecting missing paths/stages, nonlocal enable clocks, relaxed
requirements, negative slack, unknown rows and incomplete inventory.
Structural receipt:
`build/checks/runtime-vendor-payload-structural-review-c0184801-20261019-v1/run/manifest.json`.
This does not disposition the warnings: runtime SmartConnect request/ACK and
FIFO reset/clock ownership, the temperature consumer, and separate mode and
permission semantics still require review. The active OpenTPU goal owns this
next source-protocol disposition. All **498 Warning rows remain open**; all
15 Critical rows have conditional source-purpose dispositions. No bitstream
implementation or hardware programming was performed.











The active OpenTPU goal owns the next exact CDC technical dispositions:
registered drain-request fanout, duplicated reset-status observations,
asynchronous reset assertion/synchronous release, PCIe sampled status and
reset aggregation, the two mode/permission bus warnings, and the unchanged
vendor/SmartConnect/temperature boundary findings. Use frozen selected source
files: the runtime host-reset module is the registered variant renamed to
`otpu_host_reset`, not the unrelated Root original of the same module name.
At that earlier stage all 513 findings were open; the later conditional
fanout disposition below updates the current ledger. No blanket waiver or
new bitstream admission was granted.

The active OpenTPU owner must disposition these actual findings next. No full
CDC/all-mode routed approval, implementation, bitstream or hardware operation
is admitted.




Prior source retirement:
`build/checks/runtime-admission-c0184800-source-rejection-20261019-v1/manifest.json`.
The following runtime results are historical reference/dependency evidence;
qualification does not transfer to the new source correction.

Full-runtime **native source synthesis, corrected linked collection and owned-
control review passed. Full CDC/routed/physical qualification remains open.**
The original `opentpu-runtime-netlist-validation-20261019-v5.service` is terminal,
MainPID 0. Completed service `opentpu-runtime-linked-recovery-20261019-v1.service` (MainPID 0)
reuses its exact DCP with helper/board-order corrections, complete top control
pin export and eight GTX/four clock assertions. Current identity/receipt:
`build/fedora-vivado/runtime-linked-recovery-20261019-v1/launch.json`.
No source synthesis or implementation was restarted. The observer executes as a
late synthesis-only Tcl constraint file. All 35 guards, fresh actual-IP
synthesis/linked-boot filtering and native full-project property/guard checks
passed. Clock limits remain compute 6.718 ns / memory 7.500 ns. The complete
547-file source snapshot is unchanged; 551 frozen and 160 original inputs are
pinned. The actual v5 complete-source constraint-loading observation now passed:
compute 6.718 ns / memory 7.500 ns. An immutable log prefix and exact worker/job
hashes are retained in `build/checks/runtime-full-source-clock-observation-20261019-v1/manifest.json`.
Native synthesis completed with exit 0, zero errors/Critical Warnings, and the
actual fastest-clock observations retained. Saved DCP SHA256:
`dcf3cbeaf7629222d74768202be804cc40db1b085545c0d15204f187d882293b`.
Completion: `build/checks/runtime-full-source-synthesis-completion-20261019-v1/manifest.json`.
Linked-netlist/reset/CDC review is pending.
No full implementation or hardware operation is admitted. Preserve the Root
preparer/tests while active. Current receipt:
`build/fedora-vivado/spare-runtime-netlist-validation-20261019-v5/run/manifest.json`.
Admission: `build/checks/runtime-netlist-job-admission-20261019-v5/manifest.json`.
The recovered owned-control review passed all 256 annotated bits and 129 direct
stage/reset/clock connections, with linked receiver clocks present. All 156
checkpoint/vendor inputs match the preserved source synthesis. Fifty-two
corruption/lineage/pin-format controls passed; the original 31 are retained.
Relative-path and actual output-Q reader failures are preserved and corrected
without numerical gate changes. Actual review:
`build/checks/runtime-control-netlist-final-20261019-v4/manifest.json`.
The exact recovered CDC report is fully inventoried: 1,653 rows, including 19
Critical and 1,634 Warning. Every row still needs technical disposition; this
register/clock structure result grants no complete CDC or routed approval.
Linked preflight also found source-analysis helper-directory and board GTX
constraint-order defects. The helper-only analysis finished report/checkpoint
collection with four unresolved GTX Critical Warnings despite native exit 0.
A fresh NORMAL-order/eight-lane GTX check passed with zero native Errors/
Critical Warnings and all eight sites verified (unified session 81917 closed).
The normal project generator now emits the native-checked helper/order fixes;
all function ASTs, numerical bounds and admission guards are unchanged.
`build/checks/runtime-normal-project-constraint-emission-fix-20261019-v1/manifest.json`.
Preserve v5 synthesis; recover only linked analysis after
its owner releases. The first invalid read-only preflight's exact owned process
tree was stopped and its failures preserved; v5 remained untouched. Current:
`build/handoffs/runtime-linked-constraint-correction-current-20261019.json`.
The complete CDC/context inventory reader passed eight controls on an actual
1,993-row format; it grants no crossing approval. Generated-memory startpoint
warnings and all actual runtime CDC/timing findings remain undisposed.
The representative runtime report is fully inventoried: 1,653 rows, including
19 Critical and 1,634 Warning across ten clock pairs. No CDC approval was given.
`build/checks/runtime-complete-cdc-inventory-preflight-20261019-v1/manifest.json`.
The selected actual mode-3 mailbox/Gray binding review conditionally accounts
for 1,137 findings: 1,136 held-payload paths plus the reported compute Gray
aggregate; all 64 Gray scalar paths and 1,200 total native path facts were
checked against saved bounds and collected pins. Seventeen controls passed.
Four optimized response-status bits were accounted for from actual source
constants. Complete CDC approval remains false: 516 findings are open, including
all 19 Critical and 497 Warning. Scoped review/remaining ledger:
`build/checks/runtime-selected-cdc-disposition-20261019-v3/manifest.json`;
`build/checks/runtime-cdc-remaining-ledger-20261019-v1/manifest.json`.
Critical/mode/reset cone extraction completed: 20 receivers/105 startpoint
records, plus two generated reset LUT5 cones; unified session 45037 is closed.
`build/checks/runtime-cdc-critical-cones-20261019-v2/manifest.json`.
The reset selector wildcard included two non-sequential LUTs. The native
sequential-only check passed with all 163 valid FF launches/341 SERDES RST targets
and the original 3.000 ns clock-aware bound retained. Timing estimates are
synthesized, not routed signoff. The fresh runtime-project preparer now fixes
only its copied XDC; nine source controls passed. Fresh normal assembly and its
41-check independent source/guard audit passed, retaining both interfaces,
962 XDMA parameters and all 42 clock HDL dependencies. No synthesis or
implementation started. Existing memory-core RTL/firmware and bitstreams remain
unchanged. Combined result:
`build/checks/runtime-project-reset-selector-fix-20261019-v1/manifest.json`.
New source-only project/review:
`build/fedora-vivado/spare-runtime-project-20261019-v5/manifest.json`;
`build/checks/runtime-project-source-review-20261019-v5/manifest.json`.
The selector probe is finished (session 42729 closed), with current state in
`build/handoffs/runtime-wlrst-selector-current-20261019.json`. Mode/valid
publication timing and all 19 Critical/497 remaining Warning CDC findings
still need disposition. This is source preparation, not an admitted bitstream.
The earlier XDC/POST-hook failures and synthesis DCPs remain preserved. The
first correction's file-type case check also failed before synthesis and is
retained; the succeeding native test used the observed `TCL` enum.

The refreshed complete TODO table is in [HANDOFF.md](HANDOFF.md#2-todo-progress-table).



## 3. Preserved historical working handoff

The following is the unchanged saved October 18 handoff, retained as history.

# OpenTPU session handoff — 18 October 2026

## 0. Current authoritative state

**Current card: c0182863 is permanently programmed, independently verified
and booted from flash.** Fresh live USER2 identity passed: c0182863,
148.837 MHz compute, DDR1066, 4 GiB, CH0 lanes `0,1,2,3,4,5,8,7`, CH1 ECC.
The identity client and XVC server exited zero; no cable client remains and the
exclusive JTAG lease was rechecked free. It is ready to power off/move to the
Mac. CH1 automatic startup calibration is ready; CH0 awaits the matching Mac
helper. No new DDR/inference workload or physical cold power cycle ran after
flash. Mac LFM/PCIe qualification remains pending for this image.

User authorization: "fpga connected jtag, flash the image permant", applied to
the already selected c0182863 bitstream SHA256
`03b513a44544009afff9dfb82515bf84c5df84ac6a63673a0882308ce8a323ae`.
Program, separate verify and boot phases all exited zero. Backup was skipped
under the standing user preference; local c0182800 fallback artifacts remain.
Current pointer: `build/handoffs/c0182863-permanent-operation-current-20261018.json`.
Closure: `build/hardware/flash-c0182863-20261018T125114Z/closure.json`.
Independent closure audit:
`build/hardware/flash-c0182863-controller-20261018T125114Z/closure-audit.json`.
Native exec `89010` and successful identity exec `74740` are finished. The first
identity launcher exited before the client because XVC saw stdin EOF; its
receipt/logs are preserved. The corrected launcher kept stdin open and closed
the server with a newline. No flash phase was repeated. Socket-closure messages
after the successful client are dispositioned in the closure audit; both client
and server exited zero and the lease is free. Older missing-JTAG and
c0182800-current-card notes below describe historical state.

**Goal active. The priority c0182800 CH0/LFM repair passed Mac acceptance.**
Preserve it as the working baseline while completing repeatability, queued
candidate reviews and runtime integration. Both JTAG and PCIe runtime
memory/control remain mandatory in every new image. No pause is pending.

**c0182800 is the prior programmed image and proven Mac fallback.**
The original local USER2 identity passed: c0182800, 100 MHz compute, DDR800,
4 GiB. The Mac subsequently completed calibration and physical LFM230M/Qwen
tests through Chestnut. **LFM230M matched all eight ISA tokens with 14 exact
program readbacks. Qwen3.5-2B matched eight ISA tokens and all 137 program
readbacks, measuring 11.507794 GB/s, 5.784015 device tokens/s and 0.616103 wall
tokens/s.** Calibration remained unchanged and ECC counters stayed clean.
Keep c0182800 artifacts as the working baseline. The selected successor
c0182863 (148.837 MHz / DDR1066.667) is now permanently flashed locally.
Cold/warm repeatability remains pending. The user has transferred the c0182863
MCS, but confirmed the Mac has **Chestnut only and no JTAG cable**. These images
have no PCIe flash controller: the exact frozen source audit confirms JTAG is
required for permanent programming. The detailed guide/metadata correction is
commit `f432e104c9644fbebd2ebc635cb5f8c0acd3a269` on the existing branch.
It was kept local by this session; a fresh read-only check now observes the exact
commit on origin, so the Mac can pull the guide update. No push was run by this
session. Keep the explicit no-push instruction. Publication observation:
`build/handoffs/c0182863-flash-guide-publication-observed-20261018-v1/manifest.json`.
Access receipt:
`build/handoffs/mac-c0182863-programming-access-20261018.json`.

The user also requested another LFM test. No Mac SSH destination is configured,
and this Fedora host has no Chestnut attached. The fresh c0182863 repeat command
is prepared, **not executed**, in
`build/handoffs/mac-c0182863-lfm-repeat-20261018.sh`; its receipt records the
pending SSH-destination question. Do not substitute an ISA-only test for this
requested physical rerun.
Closure: `build/hardware/flash-c0182800-20261018/closure.json`.
Mac source handoff is committed locally as `959881a36195174b7d0c6afe81fa7573c5043b73`
on the existing `ypcb/dual-channel-4gb` branch: 24 checked files, 165,978 bytes.
It is now published. The Mac results and matching benchmark tools were published
in `00a277ac6db618308a04a5a090907ab0acb6fbd0`; this checkout fast-forwarded to
that commit on the same branch. That pull created no branch, commit or push.
The subsequently authorized c0182863 handoff is committed as
`4fe69e9a11c6ad0d923cbfcd2b5bba12327b6caf` on the same existing branch:
20 files, 162,405 bytes, including matching firmware, LFM/Qwen tools and the
guide. A clean committed checkout passed preflight, 16 package guards and
14 tests. **The user explicitly requested keeping this commit local; do not
push or ask again unless the user changes that instruction.** A fresh read-only
remote check subsequently observed this exact commit on origin; no push was run
by this session. Observation: `build/handoffs/c0182863-publication-observed-20261018-v1/manifest.json`. Bitstream and
BPI16 MCS paths/hashes are in `runtime/c0182863/programming.json` and
`docs/mac_c0182863.md`. No c0182863 flash or Mac runtime result is claimed.
The conflicting local README stages, runtime backend changes and untracked
program-verification tests were preserved and combined with upstream.
Pull backup/receipt: `build/handoffs/mac-results-pull-20261018-v1/manifest.json`.
The current authorized index-entry baseline follows the scoped c0182863 commit:
`build/handoffs/c0182863-jtag-flash-guide-commit-20261018-v1/index.after`;
compare modes/object IDs/stages, not raw index bytes. Earlier index snapshots
and branch-correction receipts remain historical.
Mac evidence: `docs/data/spare_pcie_benchmark_20261018.json`.
Independent image/token/source/counter audit:
`build/checks/mac-c0182800-published-result-audit-20261018-v1/manifest.json`.

### Early DDR write-clock VCO gate completed

The terminal c0183160 implementation was rejected before bitstream emission for
two real AVAL-46 violations: both write-clock MMCMs targeted 1600 MHz VCO while
the XC7K480T-2 device report permits 600–1440 MHz. Its final setup was -0.843 ns
with 11,761 failing endpoints; pulse-width slack was -0.158 ns with six failing
endpoints. All 333,693 routable nets were routed, but those numerical/DRC
findings forbid programming. No bitstream exists. The exact source, routed
checkpoint and reports are retained in
`build/checks/c0183160-clock-and-timing-rejection-20261018/manifest.json`.
Its collectors skipped the failed implementation, and its boundary/final
review services are terminal; nothing is left pending manual review.
Rejected images stay out of the active progress table.

`tools/check_spare_memory_clock_limits.py` now reads both exact generated
write-MMCM instances and their source/profile bindings, without evaluating
Verilog expressions. The public high-rate core preparer checks before and
after generation. Sixteen unit cases and four actual saved-core controls
passed: valid source VCO plans remain accepted and the invalid DDR1600 source
is rejected. The ordinary preparer also rejects it before creating a generation
directory. A complete valid DDR1333 source regeneration passed the new gate;
firmware bytes and all CSR rows remained exact. Verilog code is identical after
string-preserving removal of generated comments; changed revision/date/hierarchy
comments and raw digests are recorded. The initial overly strict metadata audit
is preserved and corrected without regenerating again or restarting Vivado.

The same gate now runs at full-image source preparation and worker preflight,
including mixed-startup preparations. Fresh ordinary/mixed tool-validation
fixtures (`c018fffe`/`c018fffd`, under `build/checks/` only) passed the normal
preparation command and their frozen workers from an unrelated working
directory. Both ship the exact checker sidecar. An already prepared invalid
core is rejected before either source preparation or implementation starts.
Both currently running mixed-startup cores also pass the read-only VCO check.
These fixtures have no queue admission, implementation or hardware operation.
Proof: `build/checks/ddr-mmcm-vco-image-admission-20261018-v1/manifest.json`.

No existing frozen input was changed, no implementation was restarted, and no
corrected DDR1600 image has been prepared or admitted. A successor needs legal
clock generation, matching calibration and complete setup/hold/pulse review
under its own identity. Source VCO success does not reopen previously rejected
images or qualify electrical DDR/DRP behavior. Current checkpoint:
`build/handoffs/ddr-mmcm-vco-progress-20261018.json`.

### Full runtime source-synthesis validation admitted

A persistent synthesis-only validation worker is now admitted behind all ten
existing priority implementations. It retains the full accelerator, 4 GiB
memory, real clock IPs and both JTAG/PCIe runtime interfaces in a private copy.
Sixteen admission/ownership cases and actual Vivado project relocation/guard
checks passed. The worker waits for the exact producer and children to finish
and release ownership, plus 11 GiB available memory. It launches no
implementation, bitstream generation or hardware action. Full runtime-image
implementation remains unadmitted; this is a separate source-validation job.

Service: `opentpu-runtime-netlist-validation-20261018-v1.service`, invocation
`84d24923ed654771a21da14f7912deba`, main PID `1821524` at admission. Revalidate
live identity and the receipt before reporting it running or terminal.
Launch: `build/fedora-vivado/spare-runtime-netlist-validation-20261018-v1/launch.json`.
Receipt: `build/fedora-vivado/spare-runtime-netlist-validation-20261018-v1/run/manifest.json`.
Checkpoint: `build/handoffs/runtime-netlist-validation-progress-20261018.json`.
After synthesis, collect actual reset/CDC bindings and disposition any finding;
reuse its completed checkpoint for parser-only corrections. No netlist coverage
or routed qualification is claimed by admission.

### Connected full-top control fixture passed scoped review

A fresh full-top connected-control check includes all 42 selected native/runtime
RTL files, byte-identical to the audited source project v4. It connects real
USER2 serialization/mailbox, the actual PCIe control guard, top reset prefix and
AON identity. BD routing/clock crossing, clock-IP and generated memory bodies
are explicit behavioral boundaries. The eight authored cases cover both hosts,
held PCIe responses, accepted-read aborts, exact USER2 sequences and subsequent
AON reachability. It does not qualify native traffic, vendor completion mapping,
activation or physical transitions.

Current source/checker: `tools/check_spare_runtime_top_control.py` and
`boards/ypcb-00338/sim/tb_runtime_full_top_control.sv`.
All eight cases passed; compiler and simulation returned zero. Exec session
`87844` finished successfully; no test worker remains. Exact final receipt:
`build/checks/runtime-full-top-connected-control-20261018-v3/manifest.json`.
Independent project/source binding:
`build/checks/runtime-connected-control-project-binding-20261018-v1/manifest.json`.
Scoped final disposition:
`build/checks/runtime-connected-control-disposition-20261018-v1/manifest.json`.
The actual top preserved held PCIe responses across lock-edge control flush,
returned errors for interrupted reads, kept USER2 abort sequence ownership and
accepted fresh identity reads afterward. Both AON paths remained reachable
after memory-lock loss. This is a completed connected-control subgate; the full
both-host native-traffic/mode-transition gate remains open.
Earlier v1/v2 fixture failures are preserved: the memory-port reader omitted
`reg` outputs, then the bench omitted explicit unused board-pin connections.
Neither was an FPGA source defect or an implementation rejection. Frozen FPGA
sources and active implementation inputs are unchanged.
Checkpoint: `build/handoffs/runtime-connected-control-work-20261018.json`.

### Latest software progress: runtime model runner

The source/execute-gated dense-model CLI and activation/reclock backend are
prepared. Fresh receipts bind the current root sources: 27 host-protocol cases,
73 transport cases and 47 backend/protocol/CLI cases passed. The actual padded
TinyStories checkpoint completed its offline ISA reference for modes `0,1,3,2`,
eight tokens per segment, with positions `13,21,13,21`. The first and third
segments reproduce the eight fixed-image physical-test tokens; the initial
28,909,056-byte image SHA256 remains
`74facccd6c0e3f7e76676617a3b7a4074c1efb784d675ac1b5bdb08dca980950`.
The reference allocated 32 MiB for the tested image/program footprint. No
hardware access or physical runtime transition occurred.

Current selector: `build/handoffs/runtime-full-top-preparation-current-20261018.json`.
Work receipt: `build/handoffs/runtime-model-runner-work-20261018.json`.
Model/backend proof: `build/checks/runtime-model-backend-20261018-v5/manifest.json`.
Compiled reference: `build/checks/runtime-tinystories-model-reference-20261018-v6/manifest.json`.
Mode-data export: `build/handoffs/runtime-host-mode-data-20261018-v12/manifest.json`.
The canonical refresh helper passed with these bindings. Older source receipts
below are historical. Fresh 27/73/47-case receipts and the four-segment actual
TinyStories ISA reference passed after merging the upstream program-receipt
constructor with the local runtime attachment path. The published Mac results
were not rerun on hardware during this Fedora audit.

Remaining runtime gates are actual connected both-host/native request/abort
races, all-mode timing/Gray/CDC disposition, actual final-review packaging,
then a separately admitted implementation and physical transitions. c0184800
is still source preparation, not a queued build. Keep the goal active and
preserve permanently programmed c0182800 for Mac acceptance.

### Runtime PCIe control-flush correction

Two exact RTL reproductions showed that source-only full-top v6 could discard
an accepted PCIe AON read or a buffered response when a clock-edge reset flushed
the guard without resetting its XDMA source. This is a real source integration
finding; no runtime implementation was admitted. Preserve v6 and its finding:
`build/checks/runtime-pcie-control-flush-loss-20261018-v1/manifest.json`.

The selected full-top v7 uses a separate source reset and target abort. Its
new guard passed strict lint and 28 cases; accepted partial writes and buffered
responses survive target reset with explicit error completion and no replay.
Fresh v7 structural elaboration, 11 exact-prefix reset cases and four-mode/ten
vendor-clock measurements passed. Updated mode data and the actual TinyStories
ISA reference are bound above. Correction receipt:
`build/handoffs/runtime-pcie-control-abort-correction-20261018.json`.
Connected both-host/native traffic, host handling of aborted control requests,
all-mode timing/CDC and physical transitions remain required. c0182800 and its
unchanged, unpublished 24-file Mac worktree are outside this runtime correction.

### Runtime JTAG completed-abort diagnosis

A fresh regression reproduced another source issue: the legacy JTAG transport
poisoned the whole connection even after a matching mailbox response explicitly
reported a coherent control abort. The runtime adapter now retries only AON
reads with status `0x80`, at most eight attempts. Writes and data operations are
never retried. Other completed errors disable further mutations and data access
while retaining read-only AON diagnosis. Ambiguous timeout/corrupt-link behavior
remains fail-closed; the fixed-image base behavior is unchanged.

The 66-case transport suite includes a START applied before its response aborts:
the SDK sent it once, refused further mutations and read the resulting state.
All 47 model/backend cases and the actual compiled TinyStories reference passed
with the fresh host binding. The runner records interrupted AON read counts.
Receipt: `build/handoffs/runtime-host-control-abort-correction-20261018.json`.
Connected PCIe/Chestnut completion-error handling and full both-host/native
traffic remain pending; this does not qualify a runtime image or physical
transition. Root prototype changes are outside the unchanged Mac handoff.

### Runtime Chestnut completion errors and exact IP preparation

The 73-case transport suite now includes actual Chestnut packet/reply code with
modeled USB responses. `PcieCompletionError` preserves bridge and completion
status separately. Completed target errors block writes/data and permit only
AON diagnosis. Uncertain USB/bridge/reserved replies require reconnection.
No PCIe requests or posted writes are retried. The 47-case backend suite and
actual TinyStories ISA reference passed with fresh source bindings above.
Receipt: `build/handoffs/runtime-chestnut-completion-correction-20261018.json`.

Actual XDMA error-completion mapping remains pending. Its runtime BD uses
XDMA 4.2 revision 4, Gen2 x8, AXI128 at 250 MHz and AXI-Lite enabled. An isolated
example preparation recreates its user overrides and requires every resolved
component parameter to match before example generation/export. The original
BD/XCI is never opened for writing. Current worker/receipt:
`build/checks/runtime-xdma-gen2-example-20261018-v4/manifest.json`, exec 30162,
completed with exit zero and strict error-log checks. The actual `board` top
is exported and all 962 resolved endpoint parameters match both before and
after example generation.
This is IP simulation preparation, not a full OpenTPU image or admitted build.
v1 failed before Vivado launch because the helper selected its bin directory;
v2 confirmed that a BD-owned XCI is locked in a standalone context. Preserve
both tool-failure receipts; neither is an FPGA implementation rejection.
v3's zero exit hid `exportsim-Tcl-70` because the parent project had no simulation
top. Its native receipt is preserved and explicitly rejected by
`build/checks/runtime-xdma-gen2-example-export-disposition-20261018-v1/manifest.json`.
v4 opens the actual generated example project, verifies its `board` top and
rejects ERROR lines even when Vivado returns zero. No implementation was restarted.

The actual vendor endpoint/Root Port completion check finished without starting
simulation:
`build/checks/runtime-xdma-completion-map-20261018-v1/manifest.json`, exec 20073.
Compilation and single-thread elaboration passed. The installed simulator then
reported a BASIC limit of 50,000 instances for this 467,267-instance model;
the wrapper correctly rejected its zero native exit because simulation never
started. No error completions were observed. Disposition:
`build/checks/runtime-xdma-completion-license-disposition-20261018-v1/manifest.json`.
The full compiled model is preserved with 240 file hashes in
`build/handoffs/runtime-xdma-licensed-resume-inputs-20261018.json` for a future
run with suitable simulator capacity in a fresh output directory.
The authored fragment is prepared to inject target RRESP
`OKAY,SLVERR,OKAY,DECERR,OKAY`, observe target handshakes and received TLP tags,
status and length, and check successful read data after each error. This is a
tool-license prerequisite for the future runtime-clock design, not a failure
of c0182800 or a requirement for its Mac LFM run. The user requested an
explanation of the license question; availability of another license remains
unknown. Continue independent offline work and preserve c0182800 for the Mac.

### Runtime rate-counter constraint component

The synthesized rate-counter component passed four mode views with 64 scalar
Gray paths each (256 total). Saved max-delay/bus-skew constraints use valid
register clock-pin startpoints and a conservative fast compute period of
6.718 ns. The reader reconciled both CDC Warning rows per view with each
summary and checked all saved bounds against the source proof. Receipts:
`build/checks/runtime-rate-gray-constraints-20261018-v2/manifest.json` and
`build/checks/runtime-rate-gray-cdc-review-20261018-v2/manifest.json`.
The first tool failure is preserved; the correction reused its successful
synthesis checkpoint. Full-top constraint integration, routed numerical bounds
and complete clock/reset/CDC disposition remain pending. No runtime image was
admitted and no hardware was accessed by these checks.

### Runtime clock-leaf static timing views

The next source component gate passed using the actual generated runtime MMCM
bodies, both exact DDR write-clock MMCM instances and the AON identity/rate RTL.
All four static views account for both runtime outputs and fourteen DDR outputs:
64 clock observations, DDR quadrature and 256 scalar Gray paths. Saved clock
definitions and max-delay/bus-skew bounds match the complete two-warning CDC
inventory in every view. Receipts:
`build/checks/runtime-clock-static-views-20261018-v2/manifest.json` and
`build/checks/runtime-clock-static-view-review-20261018-v1/manifest.json`.

The first constraint attempt was rejected for eight Critical clock-override
warnings despite completing its numerical checks. The correction renames each
automatic output clock, then updates the same named timing object; its bounded
noncritical messages are explicitly dispositioned with the observed pins and
one-clock-per-pin checks. The successful component synthesis was reused; no
implementation was restarted. The static fast compute period is conservatively
6.718 ns versus the physical target of 6.71875 ns. No hardware clock was changed.

The new clock and Gray constraint sidecars still require integration into a
fresh full-top preparation with all reset/CDC constraints. Full-top/routed
timing, connected traffic and physical transitions remain pending; c0184800
has not been admitted as a build. Checkpoint:
`build/handoffs/runtime-clock-static-view-progress-20261018.json`.

### Full runtime Vivado project assembly

The structural v7 snapshot still contained the inherited fixed-top project
entry and its fixed clock/reset constraints. A separate actual runtime project
has now been assembled in
`build/fedora-vivado/spare-runtime-project-20261018-v4/project/runtime_board.xpr`.
It selects the complete runtime top/native accelerator, the actual runtime
memory core and ROM, the matching AON BD and both dynamic clock IPs. The new
clock/Gray, mailbox, synthesis-only clock envelope and prepared runtime-native
constraint sources are included.
All 962 XDMA component parameters and all
42 regenerated clock HDL dependencies match the selected references. The
313-port wrapper differs only in its export-timestamp comment.

Strict project creation exposed a historical reviewer gap: the BD generator
attempted to set read-only Master `ID_WIDTH`, and the old checker ignored the
Critical warning behind a zero native exit. The first project receipt and old
BD review remain preserved. The generator now sets the Slave width and checks
both inherited/return interfaces after validation: ID 4, data 128, address 64,
250 MHz. The fresh BD checker rejects ERROR and Critical-warning lines; its
new receipt has none. This was a source-generator/reviewer correction, not an
FPGA implementation rejection.

The selected project passed 41 independent saved-XPR/source checks. Both full-image
synthesis and implementation are unstarted, and their saved pre-run hooks
refuse this unadmitted preparation. The old native/mailbox constraints are
preserved but disabled. Their replacements now use the AON CSR clock and narrow
reset endpoints; complete native netlist binding is still pending. The synthesis
clock envelope passed the actual-IP component check. Full reset/CDC bindings,
connected traffic, all-mode routed timing and packaging remain
required. c0184800 is source preparation, not a queued or running build.

Receipts:
`build/fedora-vivado/spare-runtime-project-20261018-v4/manifest.json`,
`build/checks/runtime-project-source-audit-20261018-v4/manifest.json`,
`build/checks/runtime-aon-bd-vendor-20261018-v2/manifest.json`.
Checkpoint: `build/handoffs/runtime-project-assembly-progress-20261018.json`.
Preserve c0182800 as the qualified baseline; no hardware was accessed by this work.

### Runtime mailbox and native constraint integration

Actual selected mailbox and registered host-reset RTL passed isolated Vivado
synthesis and endpoint binding. All 604 request bits use the actual 50 MHz AON
receiver and a 40 ns held-payload bound; all 536 response bits use a conservative
6 MHz JTAG timing view and a 333.332 ns bound. Valid register C-to-D startpoints
include clock-to-Q. The two three-stage toggle chains and two two-stage
supervisor chains retain six normally timed internal paths; exceptions name
only their first-stage D pins.

The complete CDC inventory has 1,142 Warning rows: 1,140 held payloads and two
external supervisor inputs. Every row is reconciled with its summary and saved
constraints. Vivado's multiline `_xlnx_shared_iN` pin-list aliases are resolved
within scope without executing Tcl; unresolved and cross-scope aliases are
rejected. The source disposition retains the one-outstanding-command/held-data
contract and does not qualify routed numerical timing or complete-image CDC.
Receipts: `build/checks/runtime-mailbox-aon-constraints-20261018-v1/manifest.json`
and `build/checks/runtime-mailbox-aon-cdc-review-20261018-v1/manifest.json`.

Prepared native constraints explicitly select the AON CSR clock. The inherited
memory-to-all-AON-register reset cut would also cover runtime CSR return data,
so it is replaced by a first-D-only exception on the actual eight-stage reset
chain. Internal stages stay timed; bridge/generated-memory constraint files
remain byte-exact. The fixed top's global TIMING-9 waiver is not imported into
the expanded runtime design. These native selectors still need full-netlist
binding and routed numerical/CDC review. Source preparation:
`build/fedora-vivado/spare-runtime-native-constraints-20261018-v2/manifest.json`.

The selected full project v3 includes both replacements and passed its 39-check
audit. The audit's previous relative-path receipt-writing failure is preserved
at `build/checks/runtime-project-source-audit-20261018-v2/manifest.json`; correcting
the reader required no FPGA rebuild. Current checkpoint:
`build/handoffs/runtime-mailbox-native-constraint-progress-20261018.json`.

### Runtime synthesis clock envelope and control-source inventory

The actual complete Clocking Wizard IPs were synthesized in the isolated
clock/rate component. Actual synthesis constraint loading observed the fastest
analysis periods, compute 6.718 ns and memory 7.5 ns. A copied linked timing
view excluded those synthesis-only boundary definitions and restored the
unchanged boot MMCM parameters: multiplier 16, compute divider 8 and memory
divider 6. The fastest implementation mode then rebound correctly. No full
native synthesis, implementation run, placement, routing or hardware operation
was performed by this component proof. Receipt:
`build/checks/runtime-synthesis-envelope-review-20261018-v1/manifest.json`.

Earlier attempts are preserved: different clock names caused Critical override
messages; after-checkpoint hooks inspected an already filtered timing view;
and `launch_runs -to_step init_design` was unsupported. The final reader reused
the completed successful synthesis and opened a fresh copied linked view.
Cloned-XCI output-directory leakage from the first attempt was also recorded;
the correction recreates IP from exact user settings, checks all 256 component
parameters per IP and bounds generated output paths to the new preparation.
Original runtime source artifacts remained unchanged.

Project v4 registers the checked envelope only for synthesis; implementation
uses the separate static mode constraints. Its saved-XPR/source audit passed
41 checks. The runtime-owned control inventory covers 12 actual instances,
54 annotated members and 256 pre-optimization register bits. This is a source
contract for later netlist matching: equivalent-register merges and constant
removal must be resolved, and existing bridge/memory/vendor crossings retain
their separate inventories. Source count is not routed CDC coverage.
Inventory: `build/fedora-vivado/spare-runtime-control-cdc-contract-20261018-v2/manifest.json`.

The next gates remain complete native netlist/reset/CDC binding, actual connected
both-host traffic, all-mode routed timing and the real final-review/package
producer. c0184800 remains unadmitted. Current checkpoint:
`build/handoffs/runtime-synthesis-envelope-progress-20261018.json`.

**c0182863 local SRAM/JTAG qualification and native benchmark passed; JTAG released.**
Its historical SRAM state was superseded by the authorized c0182800 permanent
flash and boot. Only scoped Mac Git publication remains unapproved; each
image's workload qualification is preserved separately.

c0182800 completed implementation and exact offline review/package. Build:
100 MHz compute, DDR800, 4 GiB, CH0 lanes `[0,1,2,3,4,5,8,7]` without ECC, CH1
ECC. Shared CH0 response bus, registered reset, independent 250 MHz host clock,
USER2 runtime access and XDMA/Chestnut. Package:
`bitstreams/spare-dual-host-4gb-c0182800/`.
Bitstream SHA256:
`df2521d80de1d69ea4ca758821dc67a814b95d67ac851b78727c9154a3104bf2`.
Package manifest SHA256:
`1c936f343bda648b4120e65bf1507999129c8b9bed67e8bab1e457828e161c3d`.

| Stage | Exact current evidence | Outcome |
| --- | --- | --- |
| Build and artifact review | `build/fedora-vivado/spare-shared-dual-c0182800-20261018/implementation/manifest.json`; `build/checks/spare-shared-dual-review-c0182800-20261018-v2/review/artifacts/manifest.json` | PASS; 333,903/333,903 nets, CRC, 278 pins, 180 DDR pad connections, nine disabled buffers; setup +0.049 ns, hold +0.013 ns |
| Exact CDC/Gray/source/boundary disposition and package | `build/checks/spare-shared-final-c0182800-20261018/worker-v2/manifest.json`; `cdc-review.json` in its parent | PASS; all 1,993 non-info rows; 4,146 scalar endpoints; 62 original and ten additional Gray skew bounds pass, minimum +3.302 ns |
| SRAM load | `build/hardware/sram-c0182800-20261018/manifest.json` | PASS; INIT=1 DONE=1 IDCODE=23751093; no flash write |
| Live USER2 identity with PCIe absent | `build/hardware/identity-c0182800-20261018-v2/manifest.json` | PASS; c0182800, 100 MHz, DDR800, full geometry |
| CH0 calibration preserving CH1 | `build/hardware/calibration-c0182800-20261018/manifest.json` | PASS; both ready, clean ECC counters, CH1 phase unchanged; native counters remained zero |
| Required zero/parity initialization | `build/hardware/tinystories-c0182800-20261018-v2/manifest.json` | PASS; 2,048 on-card BIST chunks across full 4 GiB; host did not upload 4 GiB |
| Native program-fetch regression | `build/hardware/tinystories-c0182800-20261018-v2/program-fetch/manifest.json` | PASS; exact program readback, 1,371 retired instructions, 65 exact output words, 1,496 cycles |
| Physical int8 matmul | Current TinyStories manifest | PASS; 32/32 output words, five instructions, 333 cycles |
| Trained TinyStories model | Current TinyStories manifest | PASS; all 28,909,056 uploaded bytes and SHA256 exact; all eight ISA tokens exact; 15 program readback/load checks passed; calibration unchanged |
| Native read throughput | `build/hardware/native-bandwidth-c0182800-20261018/manifest.json` | PASS; three 64 MiB native reads, median 2.991651 GB/s from FPGA counters; synthetic combined-channel result, separate from PCIe bandwidth |
| Original LFM2.5-230M / PCIe acceptance | `docs/data/spare_pcie_benchmark_20261018.json` | PASS: eight exact LFM tokens, 14 exact program readbacks; Qwen3.5-2B also passed with 137 exact programs and 11.507794 GB/s device traffic |
| Permanent flash | `build/hardware/flash-c0182800-20261018/closure.json` | PASS: native program, independent verify, flash boot INIT/DONE and live c0182800 identity; JTAG released |
| Mac Git handoff | `build/handoffs/mac-results-pull-20261018-v1/manifest.json` | Published original handoff 959881a; Mac results/tools pulled at 00a277ac on the existing branch; local work preserved |

### Retired cross-project progress file

The stale Bonetto `progress.md` was removed at the user's request on October 18.
Its 140,325 bytes of mixed MicroBlaze and early OpenTPU history are preserved
unchanged in `build/handoffs/history/bonetto-progress-retired-20261018/progress.md`.
The adjacent `manifest.json` records the original path and SHA256. Current
OpenTPU status belongs in this handoff and the checkout's `progress.md`.

### Immediate execution and ownership

The physical TinyStories run **finished PASS**, exec session 4108 exited zero;
PID 1597109 is gone. Its exact source/launch and failed predecessor remain
preserved. All eight tokens matched, all model bytes and their SHA256 matched,
15 programs passed readback/load completion, and calibration/ECC/cleanup guards
passed. Final small receipt:
`build/handoffs/c0182800-local-validation-20261018.json`.

The owned XVC server was closed gracefully after the runtime client finished.
Exec session 39527 exited zero, PID 1594506 is gone, and the exclusive JTAG lease
was acquired/released to verify it is free. Closure receipt:
`build/hardware/xvc-c0182800-20261018-v3/shutdown.json`.
The native server logs a closed listener as Bad file descriptor during normal
interactive shutdown; this happened after all clients closed and exited zero.
That was the c0182800 release. c0182461 subsequently passed its own local tests
and released JTAG. The completed c0182863 SRAM workflow is recorded below as
historical evidence. c0182800 was subsequently permanently flashed, verified
and booted; JTAG is now free. Keep Vortex excluded.

The XVC server must keep stdin open: systemd's default EOF made the first daemon
start exit normally. The old `ypcb_ref/openTPU` compatibility alias is absent.
The selected existing portable server has identical reviewed binary SHA256
`bfa6bf97aab867a580b0954d85a684fdeef363cb995713210d4249dbc0b7b709`.
`build/fedora-openxc7/xvc-ready.json` now selects that portable preparation;
the old selector is preserved. No server binary or FPGA image was changed.

The first TinyStories attempt stopped before initialization because its old ISA
oracle inherited PAIR/DSTEP/STREAM=False defaults, while live CAPS enable all
three. The flags were **not waived**. New oracle:
`build/checks/tinystories-int8-isa-20261018-v2/manifest.json`, derived from the
successful live identity receipt. It passed with all three flags True; the
28,909,056-byte initial image and eight expected tokens are unchanged:
`[29892,727,471,263,2217,7826,4257,365]`.
The current preflight is
`build/checks/tinystories-dual-required-preflight-20261018-v5/manifest.json`.
Archived checker/runner sources and failed receipts are preserved in the v1
oracle/test folders. Do not edit checker/runner/model sources hashed by the
current physical run. The original model and mathematically padded checkpoint
remain separate; FP32 equivalence and int8 ISA evidence are preserved.

### Completed c0182461 physical workflow

c0182461 completed implementation and exact independent review/package, then
the authorized SRAM load. Configuration: 100 MHz compute, DDR1066.667, 4 GiB,
CH0 lanes `[0,1,2,3,4,5,8,7]` without ECC, CH1 ECC, shared CH0 response bus,
registered reset, independent 250 MHz host clock and both JTAG/PCIe interfaces.
Bitstream SHA256:
`0fc2b933ddd3fd0378941464ae6c8d91e356fb1bb90bf9e446ded6f90817007b`.
Package manifest SHA256:
`a41477049bf79295dcf2ac72668441f66cd7f830d0ab5322ba0957965f124246`.
Exact final setup +0.044 ns and hold +0.019 ns after automatic userclk1 hold
repair/rerouting; final review/package PASS:
`build/checks/spare-shared-candidate-final-c0182461-20261018-v1/worker/manifest.json`.

SRAM INIT/DONE/IDCODE passed:
`build/hardware/sram-c0182461-20261018-v1/manifest.json`.
Exec session 28094 exited zero. Programmer exited zero; the owned hw_server was
intentionally stopped with SIGTERM (`-15`), not a programming failure. Owned
auxiliary servers closed. Live USER2 identity passed with PCIe absent, CH0
calibration preserved CH1 phase/native counters, and the fresh ISA oracle passed.
Calibration phases: CH0 +52, CH1 raw 4294967248 (-48).

The physical TinyStories process **finished PASS**, exec session **96932** exited
zero and PID 1702653 is gone. Exact launch/receipt:
`build/handoffs/c0182461-hardware-session-20261018.json` and
`build/hardware/tinystories-c0182461-20261018-v1/manifest.json`.
Required full zero/parity initialization passed all 2,048 on-card BIST chunks;
the host did not upload 4 GiB. Program fetch retired 1,371 instructions and
matched all 65 words in 1,482 cycles. Matmul matched 32/32 words in 326 cycles.
The 28,909,056-byte trained-model upload completed at 03:43:24 UTC. Full model
readback completed exactly at 04:22:49 UTC. All eight physical tokens matched
the exact ISA: `[29892,727,471,263,2217,7826,4257,365]`. All 15 program readbacks
and load-completion checks passed; calibration stayed unchanged and cleanup
passed. The image readback SHA256 is
`74facccd6c0e3f7e76676617a3b7a4074c1efb784d675ac1b5bdb08dca980950`.

Its prepared native benchmark then passed three 64 MiB reads at median
**3.033203267833535 GB/s**, using actual FPGA counters and final 16 KiB output
comparisons. Receipt: `build/hardware/native-bandwidth-c0182461-20261018-v1/manifest.json`.
Exec session **22116** exited zero. This is synthetic combined-channel native
read throughput; it does not qualify PCIe bandwidth or original Mac LFM230M.
The benchmark overwrote the prior model program/output memory.

The owned XVC server (old PID 1701834, start ticks 64302094, TCK 6 MHz) closed
gracefully after all clients exited. PTY exec session **56323** exited zero;
the exclusive shared lease was acquired/released to verify it was free.
Closure: `build/hardware/xvc-c0182461-20261018-v1/shutdown.json`.
Small final summary: `build/handoffs/c0182461-local-validation-20261018.json`.
Its 15-/17-check hardware audits are historical c0182461 scope. Use the generic
checker against the current session after its SRAM/identity/calibration stages;
do not rerun the old hardcoded c0182461 audit after switching images.

The actual review used `spare-shared-dual-review-c0182461-20261018-v2`, while
the first prepared SRAM command accidentally named v1. The command registry is
corrected and now explicitly bound to the final worker's actual package schedule:
`build/checks/candidate-sram-command-binding-20261018-v1/manifest.json`.
No implementation or review was restarted for that preparation-only correction.

The matching native-read benchmark is prepared in
`build/handoffs/shared-native-benchmark-preparation-20261018.json` for c0182461
and c0182863. Both exact host trees passed its ISA geometry check. A deliberate
attempt with the still-running c0182461 integration receipt failed before any
transport was opened. The new helper requires completed exact-image model-byte,
token, calibration and package evidence before it can overwrite program/output
memory. c0182461's command subsequently executed and passed as recorded above.
c0182863 subsequently passed its integration and benchmark; both clients and
its owned XVC server exited zero and the lease was verified free.

### Active c0182863 physical workflow

The corrected final-review/package worker passed, and hardware-free SRAM
preflight replayed all 40 package checks. The exact programming command started
after c0182461's successful workload/benchmark, client/server cleanup and lease
release. Temporary SRAM only; permanent c0172300 is unchanged.

Session registry: `build/handoffs/c0182863-hardware-session-20261018.json`.
Hardware selector: `build/handoffs/current-shared-hardware-session-20261018.json`.
SRAM receipt: `build/hardware/sram-c0182863-20261018-v1/manifest.json`.
Programmer exec session **77557** exited zero; old PID 1726668 is gone. SRAM
INIT/DONE/IDCODE passed. The programmer exited zero and its owned hw_server was
intentionally stopped with SIGTERM (-15); no peer hardware servers remained.
Live USER2 identity passed with PCIe absent: c0182863, core_khz=148837, DDR1066,
full geometry and PAIR/DSTEP/STREAM flags. CH0 calibration passed with phase
+52, preserving CH1 raw phase 4294967249 (-47) and zero native counts. The
fresh exact-image ISA oracle passed with the expected 28,909,056-byte image and
eight tokens; exec session **8351** exited zero.

Physical TinyStories **passed**: all 28,909,056 uploaded bytes and SHA256
matched, all 15 program readback/load receipts passed, and all eight tokens
matched the ISA. Calibration was unchanged. Client session **27387** exited
zero; PID 1728346 is gone. Initialization passed all 2,048 on-card chunks;
fetch retired 1,371 instructions with 65 exact words in 1,503 cycles; int8
matmul matched 32/32 words in 337 cycles.

The prepared native benchmark then executed and passed three 64 MiB reads:
median **4.452532693 GB/s** from FPGA counters and exact final 16 KiB chunks.
Session **27852** exited zero; PID 1754180 is gone. This is about 1.468x the
c0182461 result on the same dual-channel synthetic workload. Single-channel
speedup, PCIe transfer rates and LFM230M acceptance remain unverified.

Owned XVC session **10861** exited zero after all clients finished; PID 1727374
is gone. The shared lease was acquired/released to verify it is free. Closure:
`build/hardware/xvc-c0182863-20261018-v1/shutdown.json`.
Final local summary: `build/handoffs/c0182863-local-validation-20261018.json`.
The generic 17-check scope/identity audit passed in
`build/checks/current-shared-hardware-c0182863-20261018-v3/manifest.json`.
The board remains last verified as c0182863 SRAM; permanent c0172300 unchanged.

### c0182863 small Mac runtime and permanent-operation preparation

The matching small DDR1066 runtime export is prepared in
`build/handoffs/mac-runtime-c0182863-20261018-v1/` using
`tools/export_spare_shared_runtime.py`. It preserves the exact frozen full
profile/transport guards and calibration algorithm. Omitted netlist and review
artifacts remain explicitly recorded build bindings; raw firmware/core config
files retain their original hashes. Private build paths are omitted from the
published review summaries. Runtime manifest SHA256:
`d1c66d9b07061093c001de6bc570e6cf081ae3b7514d1038d4972d032c0796b0`.

The clean normal Git worktree is `build/handoffs/c0182863-mac-git-20261018`,
branch `ypcb/c0182863-mac-runtime`, base
`b3cfcb24a64516c247b7ea9d5eedb3764707b99c`. It contains 21 scoped files,
163,640 bytes total, largest 34,840, including matching Mac docs and a small
portable `HANDOFF.md`. Its normal-path preflight passed without device access.
Sixteen offline checks passed: full-package/runtime firmware-binding parity,
unchanged calibration and transport/ECC/reset guard ASTs, mandatory program
readback for bandwidth, wrong image/clock/calibration rejection, and corrupted
CSR/firmware/runtime-file rejection. Receipt:
`build/checks/mac-runtime-c0182863-guards-20261018-v1/manifest.json`.
Proposal: `build/handoffs/mac-runtime-c0182863-git-proposal-20261018.json`.
The common-source review also passed: 73 common files match the frozen host
byte for byte. Only the build preparer differs; its runtime `sha`, `phy_config`
and `csr_registers` functions have identical AST. Unrelated build-generator
changes remain excluded from the Mac payload. Receipt:
`build/checks/mac-runtime-c0182863-common-sources-20261018-v1/manifest.json`.
No stage, commit or push; this branch is not available to the Mac yet. Do not
substitute the separate pending c0182800 publication authorization.

The existing implementation's BPI16 MCS was compared byte for byte with the
reviewed c0182863 bitstream and checked against its completed modern SRAM
receipt, then copied into
`build/hardware/flash-preparation-c0182863-20261018-v1/otpu.mcs`.
MCS SHA256: `ce318208e248992fd3ae37d3682f44096937db13c989e2376f21ce0228aef0d4`;
36,200,992 bytes. No extra implementation or cable access occurred.

`tools/flash_spare_shared.py` understands the modern SRAM receipt while retaining
the original native BPI program/independent-verify/boot Tcl. Hardware-free flash
preflight passed in `build/checks/flash-c0182863-preflight-20261018-v1/`.
Nine actual-receipt/corruption/native-Tcl checks passed in
`build/checks/shared-flash-receipt-guards-20261018-v1/`.
Exact prepared command and conditions:
`build/handoffs/c0182863-permanent-operation-plan-20261018.json`.
This permanent operation is not authorized or executed. The current JTAG
workload retains exclusive ownership. Permanent programming still requires
explicit approval for this exact image/checksum; skip-backup preserves the
standing preference. Mac cold boot, PCIe/LFM and bandwidth remain separate.

### Active implementation and review owners

- Producer `opentpu-dual-required-queue-20261018.service`, invocation
  `aa048135477b4ff39c640e66f412d554`, PID 1523449. Existing c0182800 was adopted
  without restart; its actual zero exit was observed before the obsolete held
  parent was released. Old PIDs 1505353/1505360 are gone. Never resume that old
  producer or retired c0182301 workers.
- Main collectors `opentpu-dual-required-dual-collectors-20261018.service`,
  invocation `39b3a7d45f85427e82a797938f6e0f3f`; baseline collection passed.
  Rate/mixed collectors retain their current launch records under
  `build/checks/spare-dual-required-{rate,mixed}-collectors-20261018/`.
- Exact baseline boundary v2 invocation `14dc991e80e24b5483262d4eccc5b2a7` and
  final/package v2 invocation `b758b15f65ac4a1281a433da6b1756d6` finished PASS.
  The first boundary preparation lacked two sibling witness files and failed
  before Vivado; v2 froze the identical helpers. No gate or implementation was
  changed to fix the preparation failure.
- The priority resource hold was released after strict package acceptance.
  Its receipt says `SECONDARY_IMPLEMENTATIONS_RESUMED_AFTER_PRIORITY_RESOURCE_RELEASE`;
  24 saved process identities resumed. c0182862 subsequently failed its real
  pre-bit setup gate: -0.319 ns, 1,819 failing endpoints, no bitstream produced.
  Its parent/implementation finished with exit 1 and downstream collectors
  correctly stopped before qualification. c0182450 also failed its real pre-bit
  gate (-0.506 ns); the priority supervisor recorded exit 1 and started c0182863
  at the freed slot. c0182461 subsequently finished and passed exact review;
  c0182863 finished implementation at 03:39:07 UTC on October 18. Final setup
  +0.004 ns and hold +0.012 ns passed, with 334,799/334,799 nets routed and no
  failing timing endpoints. Bit SHA256:
  `03b513a44544009afff9dfb82515bf84c5df84ac6a63673a0882308ce8a323ae`.
  Exact review and packaging now passed in the corrected v2 final worker;
  all five completed collections were reused unchanged. Physical results remain
  pending. The supervisor resumed
  original producer admissions. c0183120 and c0183130 are now implementing;
  four other original variants wait. Verify live stages; do not restart the
  completed c0182863 build or manually manipulate the old producer.

**Vortex execution is held at the user's request.** A new Vortex v6 build and
repeated standalone Codex resumes appeared after the first stop. The continuous
owner `opentpu-vortex-exclusion-c0182800-20261018.service`, invocation
`250133c2c3b24410bc6d1768ca8fc21e`, stops Vortex workers while leaving idle
terminals and the shared app server alone. Its code/logs/receipts are in
`../vortex/build_ypcb_vivado32/openTPU-return-20261018/exclusion-v1/`.
Do not kill the shared app server (PID 1130093); it serves other projects too.
The guard waits for any identified/unknown atomic programmer instead of
interrupting it. Keep all Vortex results there. Do not automatically resume
Vortex after the OpenTPU test; honor the user's priority until changed.

### Progress reconciliation and matching SRAM tools

The file-only refresh previously retained contradictory old fields: Vortex as
the SRAM image, TinyStories physically pending, an old-adapter programming hold
and a superseded pause/resume order. Those values are preserved under
`historical_progress_fields`; current fields now derive from the completed
c0182800 physical receipts. The original c0172300 failure identity remains
separate from the corrected image. Local JTAG repair evidence does not establish
original Mac LFM or PCIe acceptance. An unowned board's present identity is not
inferred from the saved identity receipt.
Audit: `build/checks/progress-state-reconciliation-20261018-v1/manifest.json`;
43 checks passed, including bit/MCS hashes, all 23 Mac payload files and the
unchanged root Git index. The saved pre-correction manifests/helper remain there.

c0182863 matching SRAM preparation:
`build/handoffs/c0182863-sram-programming-preparation-20261018.json`.
The legacy loader rejected valid complete-CDC wrapper metadata before any device
access (`build/checks/c0182863-sram-host-preflight-20261018-v1/`). This is a
programming-tool schema failure, not an FPGA rejection. The fresh
`tools/program_spare_shared_sram.py` resolves the frozen parent, verifies the
reader-only AST change and retains all 40 package gates. Host preflight v3,
completed-c0182800 full-gate replay v2, and three negative guards passed.
It acquires the exclusive JTAG lease and defers signals across atomic SRAM
programming. No additional user approval is required for authorized temporary
SRAM checks. c0182863 has now passed its own implementation, exact review/package
and all 40 reviewed SRAM preflight gates. Hardware-free receipt:
`build/checks/c0182863-reviewed-sram-preflight-20261018-v1/manifest.json`.
Its next physical workflow waits for the current valid c0182461 client and
benchmark to finish and release the exclusive XVC/JTAG owner.
No implementation or active review-worker source was changed for this tool fix.

### Flash and Git preparation; no approval yet

The BPI16 MCS is prepared and exact-byte checked in
`build/hardware/flash-preparation-c0182800-20261018/`.
MCS SHA256:
`a733ebdb222134bbdb6d220a103d7292fc10e46368de8ae81e4a648691ca97f2`.
`tools/flash_spare_c0182800.py` retains native part checks, exact image/SRAM
binding, separate program/verify/boot phases and explicit exact-image approval.
It requires the exclusive lease and defers interrupts across the atomic flash
operation. Positive offline preflight:
`build/hardware/flash-preflight-c0182800-20261018-v2/manifest.json`.
The negative test mocked every device dependency and proved missing approval
is rejected before any native process/socket/lease call:
`build/checks/flash-c0182800-authorization-negative-20261018/negative-test.json`.
Honor the user's existing skip-old-backup preference. Do not create a positive
authorization file or run permanent programming without explicit approval for
this exact image/checksum/operation. Do not introduce a local PCIe runtime gate
for the selected flash-here/test-on-Mac workflow.

The small runtime export passed in
`build/handoffs/mac-runtime-c0182800-20261018-v1/`. Its runtime metadata digest:
`310e2856d29c0eb2b8f917b8b8a72537bc3d63546a2c3f6d84aaf3524a155093`.
The ordinary Git payload is prepared in isolated worktree on branch `ypcb/c0182800-mac-runtime`
`build/handoffs/c0182800-mac-git-20261018` from HEAD b3cfcb24. The original root
index is unchanged. New runtime files, mandatory-interface AGENTS policy,
shared-adapter/reset sources and `docs/mac_c0182800.md` are reviewable there.
No tar/zip/archive handoff, new large artifacts, weights, staging, commit or push.
The final local-validation receipt and Mac documentation are updated. The
scoped payload is 24 files / 165,986 bytes, largest 35,606; normal preflight v4 passed.
The concrete permanent operation is recorded in
`build/handoffs/c0182800-permanent-operation-plan-20261018.json`.
The user explicitly approved c0182800 permanent flash; program, independent
verify, flash boot and fresh identity have completed successfully. Scoped
commit/push remains unapproved. The current publication question covers the
24-file payload; elapsed time and preselected options are not approval.

### Matching speed-candidate runtime preparation

The c0182800 physical run finished PASS. Matching host,
firmware binding and complete-CDC packager preparation passed for c0182450,
c0182862 and c0182461. Registry:
`build/handoffs/shared-combined-runtime-preparation-20261018.json`.
Each host passed all nine evidence guards. Both DDR1066 candidates passed six
actual firmware-copy/binding cases using their model-reviewed c0172168 binary,
including wrong-image ID/hash, wrong bridge-proof hash and corrupted firmware
rejection. c0182450's actual DDR800 copier/binder also passed. These fixtures
use a zero image hash and contain no bitstream; they do not approve a package
or establish physical DDR1066 operation.

Current host trees:
`build/handoffs/spare-shared-dual-host-c0182450-20261018-v3/host/`,
`build/handoffs/spare-shared-dual-host-c0182862-20261018-v1/host/`, and
`build/handoffs/spare-shared-dual-host-c0182461-20261018-v1/host/`.
The c0182450 display-command metadata was normalized in a fresh copy; executable
bytes remain unchanged. Complete-reader packagers are under each corresponding
`build/checks/spare-shared-dual-packager-<id>-20261018-vN/complete-cdc/`.
The DDR1066 packagers preserve every existing binary/model/configuration/CSR
check and add the corrected adapter/bridge/controller proof bindings.
All source snapshots and active implementation workers remain unchanged.

Matching c0182461 and c0182863 local JTAG workflows are now prepared in
`build/handoffs/shared-jtag-candidate-workflows-20261018.json`. These are six-stage
command sequences, **not admitted hardware jobs**: exact reviewed SRAM load,
owned XVC with stdin held open, live identity, CH0 calibration preserving CH1,
fresh exact-image ISA oracle, and physical TinyStories with complete weight and
program readback. Both matching SRAM host preflights passed. The reusable tools
are `tools/check_tinystories_shared_model.py` and
`tools/run_tinystories_shared_jtag.py`; the certified c0182800 tools are unchanged.
The new normal path replayed the completed baseline's ISA run and reproduced
the same image hashes, geometry, logits hash and eight tokens in 15.6 seconds.
Its runner input preflight passed; a c0182800 oracle presented for c0182461 was
rejected before any socket/device call. These are tool-preparation results,
not successor-image physical qualification. Keep the existing isolated tokenizer
path `build/checks/tinystories-tokenizer-py314-20261018`; the first new invocation
used a nonexistent target and its import failure is preserved under the baseline
v1 folder. The successful fresh proof is
`build/checks/tinystories-shared-oracle-baseline-20261018-v2/manifest.json`.

Additional boundary audits are now scheduled immediately after each exact
main collection, without hardware access:

| Image | Boundary unit | Invocation |
| --- | --- | --- |
| c0182862 | `opentpu-shared-boundary-c0182862-v1-20261018.service` | `c91480fade324cb8ae3db52f4561bf2f` |
| c0182450 | `opentpu-shared-boundary-c0182450-v1-20261018.service` | `6de45540c60a41b8b339948e5f1843f7` |
| c0182461 | `opentpu-shared-boundary-c0182461-v1-20261018.service` | `558389d96144402f9e9453037cbe4cc2` |

Their launch records are in the runtime-preparation registry. The fresh waiter
accepts a terminal collector's cleared invocation only after its exact image
has a completed collection receipt. Numerical, endpoint and source checks
remain unchanged. Final disposition still belongs to the active OpenTPU goal;
do not use c0182800's fixed-clock approver unchanged for a faster image.

### Higher-DDR runtime preparation

All four requested higher-rate host/firmware/package preparations now passed:
c0183120 (DDR1200), c0183130 (DDR1300), c0183133 (DDR1333) and c0183160 (DDR1600).
Registry: `build/handoffs/shared-combined-runtime-preparation-20261018.json`.
Each actual host passed nine source/model guard cases; each firmware copier and
binder passed six cases with wrong-ID/hash/proof and corrupted-binary rejection.
Complete CDC readers retain all original package/timing/pin/endpoint gates.
These are source/component preparations, not ready images or physical results.

New helpers: `prepare_spare_shared_rate_host.py`,
`prepare_spare_shared_rate_packager.py`, `spare_shared_rate_package_support.py`,
`spare_shared_rate_firmware.py`, and
`check_spare_shared_rate_calibration_binding.py` under `tools/`.
The inherited firmware descriptor in each corrected preparation names an
uncopied calibration directory. Active preparations were not modified. The
new helper resolves the verified original parent, requires the existing binary
hash/size and unchanged initialization/ROM/CSR rows, and retains every compiled
firmware/model/dependency check before rebinding to the corrected image.
The first c0183120 packager preparation used an ambiguous import marker; its
failure is preserved in v1. v2 corrected the anchored generator marker without
changing or restarting implementation. Other rates use their v1 packagers.

Current host folders are `build/handoffs/spare-shared-rate-host-<id>-20261018-v1/host/`;
packagers are `build/checks/spare-shared-rate-packager-<id>-20261018-vN/complete-cdc/`.
Exact final disposition still needs the selected image's completed routed
collection. Do not reuse c0182800's fixed-clock approval unchanged.

Four additional boundary collectors are armed after the exact rate-family
collector invocation `1df58610623b4c089d5bdf794fc00298`. Their current launch
records and service invocation IDs are in the runtime-preparation registry.
Units: `opentpu-shared-rate-boundary-<id>-v1-20261018.service`; evidence roots:
`build/checks/spare-shared-rate-boundary-<id>-20261018-v1/`.
All four are verified live and waiting for their exact main collection.

### Shared/mixed-startup runtime preparation

Both remaining startup variants now have exact matching host and packager
preparations. Registry:
`build/handoffs/shared-combined-runtime-preparation-20261018.json`.
`tools/prepare_spare_shared_mixed_host.py` derives from the shared/registered
parent, verifies its complete source inventory, transforms only the six exact
image-specific files, retains mandatory program readback, and exposes only the
automatic-startup observer for the new image. Common legacy helpers remain
unchanged; the new image has no host calibration entry point.

Current hosts: `build/handoffs/spare-shared-mixed-host-<id>-20261018-v1/host/`.
Actual copier/startup binding passed for c0182600 in
`build/checks/spare-shared-mixed-startup-binding-c0182600-20261018-v1/`.
The full two-image mailbox replay passed in
`build/checks/spare-shared-mixed-startup-host-model-20261018-v1/`.
Each image decoded 8/9 lanes, accepted its automatic receipt, rejected eight
corrupt/inconsistent cases and issued zero startup-control or memory writes.
Fixtures use a zero image hash; they are not positive image-package or hardware
startup results. The existing seven-case firmware and both actual RV32 model
proofs remain byte-bound; no physical startup claim was transferred.

`tools/spare_shared_mixed_package_support.py` retains the original checked
firmware/CPU-model copying, then binds the shared core and unchanged firmware
under a distinct shared-startup source-binding status. Exact core/profile/ROM
and source hashes are verified. Packagers:
`build/checks/spare-shared-mixed-packager-c0182600-20261018-v2/complete-cdc/` and
`build/checks/spare-shared-mixed-packager-c0182662-20261018-v1/complete-cdc/`.
The first c0182600 preparation failed only while formatting a README's parent
ID; that failed receipt is preserved. v2 uses the verified host parent identity.
No implementation was changed/restarted. Mixed final routed disposition and
physical automatic startup remain pending. Extra boundary collection now uses each exact frozen mixed snapshot guard,
through `tools/prepare_spare_shared_mixed_boundary_review.py`. Both collectors
are scheduled after the exact mixed main collection, invocation
`27191c9212c84dfcaf0b747fba33eba0`:

| Image | Boundary unit | Invocation |
| --- | --- | --- |
| c0182600 | `opentpu-shared-mixed-boundary-c0182600-v1-20261018.service` | `194651a4fd72440389b7212e47e3aaa2` |
| c0182662 | `opentpu-shared-mixed-boundary-c0182662-v1-20261018.service` | `17930b2a21084ad99ff1d20424dd41c9` |

Their launch records are in the runtime-preparation registry. Both exact
workers are live and waiting. No baseline-only snapshot guard is substituted.

### Per-image global-reset API exclusion

`tools/check_spare_global_reset_exclusion.py` now checks each actual successor
host module using objects whose every device-attribute access fails. All nine
successor hosts rejected both zero and one writes to the unsupported global
SoC reset CSR through JTAG, Chestnut and XDMA: 54 cases total, with no constructor
or hardware access. Source hashes and receipts are recorded per image in
`build/handoffs/shared-combined-runtime-preparation-20261018.json` under
`reset_exclusion`. Receipts: `build/checks/shared-global-reset-exclusion-<id>-20261018.json`.
This supports the documented operating exclusion only; the actual selected
image's routed reset fanins and CDC disposition remain mandatory.

### Scheduled candidate final disposition and packaging

All nine successor boundary streams now have exact final-disposition/package
workers, launched under `opentpu-shared-candidate-final-<id>-v1-20261018.service`.
Current source, launch, service invocation and receipt witnesses are in
`build/handoffs/shared-combined-runtime-preparation-20261018.json` under
`final_execution_launch`. All are verified live and waiting for exact boundary
collection. No successor has been approved or programmed by this scheduling.

`tools/review_spare_shared_speed_cdc.py` checks the selected exact ID/profile,
actual core and DDR-user periods, original Gray budget and unchanged structural
fanins/endpoints. It retains the full 1,993-row inventory gate and all existing
package/timing/source/pin/CRC checks. `spare_cdc_clock_facts.py` normalizes only
verified numeric period fields for baseline structural comparison; wrong
periods, weakened Gray bounds and changed fanins reject. Real c0182800 evidence
replayed through the derived checker passed, with negative/parser-only speed
cases in `build/checks/speed-review-baseline-preflight-20261018/`.
This does not transfer clock-specific image qualification.

Mixed startup has a separate `review_spare_shared_mixed_cdc.py` with exact mixed
IDs, both automatic channels and shared/mixed artifact/source/disposition
statuses. Its CPU/startup/package bindings remain checked by the prepared
mixed packager. Final workers never program hardware or reuse the already
released priority resource hold. Any new finding/tool failure must be inspected
immediately, preserved and corrected in a fresh worker; do not edit their
hashed source/tools while active or restart implementation for parser failures.

### Observed native read throughput after correctness passed

A short counter-based native LD benchmark passed on the same c0182800 SRAM
configuration, without reconfiguration, recalibration or memory initialization.
`tools/run_spare_c0182800_bandwidth.py` retains the existing counter/instruction/
final-chunk checks and adds mandatory program readback. Its ISA geometry check
passed first. Physical evidence:
`build/hardware/native-bandwidth-c0182800-20261018/manifest.json` and
`postflight.json`.

Three 64 MiB logical reads measured 2.991651, 2.991727 and 2.991642 GB/s from
FPGA RUNNING/DRAM counters; median **2.991651 GB/s**. Each run counted 1,048,576
64-byte physical read beats, 256 write beats and 8,196 retired instructions.
Final 16 KiB output comparisons passed. Calibration/ECC guards remained clean.
This checks read throughput and final-chunk consistency only, not full-range
numerical reliability or a controlled speedup versus the earlier image. JTAG
run-call wall time is recorded separately. Original Mac LFM230M and PCIe/Chestnut
bandwidth remain pending.

The benchmark overwrote its program/output locations inside the previous model
image; do not reuse the old model without re-uploading it. Its completed trained
inference pass remains immutable evidence. Benchmark exec session 47349 exited
zero; XVC session 40907 exited zero and PID 1624077 is gone. Exclusive JTAG lease
release was verified in the postflight receipt. No hardware client is active.
The pending flash/publication approval questions and their offered 23-file Git
payload remain unchanged.

### Corrected runtime-clock memory component

The older runtime memory component was checked and still selected the defective
independent-response adapter. A fresh generation completed in
`build/fedora-vivado/spare-runtime-shared-memory-core-20261018-v1/` using
`tools/prepare_spare_runtime_shared_core.py`. Its parent is the frozen corrected
shared DDR1066 generator. The new preparer binds all eight native, ten bridge
and eight real-controller regression cases and rejects the old parent or altered
proofs before generation. Five negative binding checks passed in
`build/checks/runtime-shared-input-binding-20261018-v1/`.

The generated core retains the four external clock/reset/readiness/hold inputs,
existing CSR map, full geometry, spare mapping and CH1 ECC. The complete pinned
numerical timing envelope matched before generation. Six simulations of actual
SelfCal hold/arbitration logic passed in
`build/checks/runtime-shared-calibration-hold-20261018-v1/`: startup hold,
in-flight ack/error completion, suppression of subsequent requests and both
hold sources. The CPU was a bus-driving stub; this is not clock-switch, CDC,
firmware or physical transition qualification.

Generation exec session 83901 exited zero; both recorded process identities are
gone. `completion.json` binds the generation and model receipts. The request and
audit records now select this corrected component and preserve the old component
as superseded evidence. Complete top/controller integration, a full-image
preparation and Vivado admission remain **false**. c0182800, the offered Mac
payload, active fixed-clock sources and FPGA configuration were unchanged.

The legacy `prepare_spare_runtime_core.py` entry now delegates to the strict
shared preparer. Its original source is preserved under
`build/handoffs/runtime-independent-component-retirement-20261018/`.
The real legacy CLI rejected the old parent before creating any output:
`build/checks/runtime-legacy-entry-rejection-20261018-v1/manifest.json`.

### Runtime-clock register/sequencer component

`rtl/boards/ypcb-00338/otpu_runtime_clock_ctrl.sv` now provides the always-on
AXI-Lite register protocol and transition state machine. Exact frozen-source
lint and 21 RTL simulation cases passed:
`build/checks/runtime-clock-control-component-20261018-v2/manifest.json`.
The prior 12-case component and exact sources remain preserved in v1.
Runnable checker: `tools/check_spare_runtime_clock_ctrl.py`; bench:
`boards/ypcb-00338/sim/tb_runtime_clock_ctrl.sv`.

The component handles independent AW/W arrival, response backpressure, stale
acknowledgment rejection, drain-before-reset, compute-only DDR preservation,
destructive DDR reinitialization/model reload, fault visibility and recovery.
Drain timeout does not reset accepted transactions. Maintenance phases do not
impose a short timeout on slow model uploads. Reset requests are registers.

This is **not** complete always-on top integration or implemented MMCM DRP/CDC.
The external drain/status/configuration engines are modeled in the bench.
Initialization/model commands are host attestations; matching checks and
fresh drain handshakes remain mandatory in the final image. Configured-rate
registers are not independent frequency measurements. The fixed-clock USER2
front end still needs moving from compute to always-on control; map the new
register window to both JTAG and PCIe. Request/audit records now bind this
component proof and preserve full-image/Vivado-admission flags as false.

### Configuration engine and actual generated clock-IP model

The configuration-engine RTL `rtl/boards/ypcb-00338/otpu_runtime_clock_config.sv`
passed lint and 13 protocol tests in
`build/checks/runtime-clock-configuration-component-20261018-v2/manifest.json`.
It writes/verifies all 23 setting words, checks old lock, starts the documented
LOAD operation, requires a new unlock/relock and checks LOAD clearing. It keeps
AXI requests/data stable until accepted and drains an issued transaction before
canceling. The parent sequencer must supply deadlines and cancel on fault.
The v1 bench hit an Icarus variable-index slice limitation; v2 used equivalent
mask expressions in the bench only. The DUT and failed receipt are preserved.
The protocol model covers all four presets, read/write errors, corrupted
readback, stale lock, partial-write/read cancellation and compute-only isolation.

Actual generated vendor-IP verification **passed** in
`build/checks/runtime-clock-ip-actual-20261018-v4/manifest.json`: all four
reconfigurations and ten period checks, actual AXI/VHDL/DRP/UNISIM code, including
fractional division and return to integer settings. Service
`opentpu-runtime-clock-ip-model-v4-20261018.service`, invocation
`70db64690ee84aa7b3661710d4b20c4f`, completed with exit 0/MainPID 0.
Launch/frozen checker: `build/checks/runtime-clock-ip-actual-20261018-v4-launch/`.
This is clock-IP model evidence, not physical DDR or inference qualification.

The old IP manifest omitted 12 included `.vh` headers. The new model receipt
binds them, and `prepare_spare_runtime_clocks.py` now inventories them for future
preparations. Prior tool/source evidence is preserved in
`build/handoffs/runtime-clock-ip-header-inventory-fix-20261018/`.
Attempt v1 rejected `--mt 1` before elaboration; v2 used `--mt off` but its
wrapper canceled after 180 seconds. Native PIDs 1632785/1632820 were later
confirmed gone and no snapshot kernel existed. v1/v2 failed receipts and
checker sources are preserved. v3 has no canceling elaboration deadline and
was launched only after the v2 native process was authoritatively gone. It was
later technically superseded after an isolated bench reproduction identified
the dynamic-clock-event compilation problem described below; its evidence remains.

The original integration finding in
`build/checks/runtime-control-reset-integration-finding-20261018.json` now has an
exact component disposition:
`build/checks/runtime-control-reset-integration-disposition-20261018.json`.
The corrected controller separates AXI `bus_reset` from sequencer `rst`, flushes
half-transactions, suppresses command acceptance on the flush edge and preserves
accepted clock requests. A data-path `fabric_abort` faults/invalidates activation
without resetting or releasing an owned configuration engine. Its FAULT state
must drive the configuration engine's transaction-boundary cancellation input.

Review also found two unsafe recovery assumptions: a stale high drain could be
accepted after a fault, and an old reset checkpoint survived new maintenance
traffic. Both are corrected. Fault recovery now needs a fresh low/high drain
unless a still-valid checkpoint proves no intervening clients; entering
calibration/maintenance invalidates that checkpoint. The new v2 proof runs all
prior 12 cases plus nine reset/abort/recovery cases, with all 21 passing lint and
RTL simulation. This does not qualify actual reset sources, CDC or board routing.

Request/audit records mark the component finding resolved and retain the original
finding and v1 proof. Actual both-host integration, drain/CDC and vendor-engine
integration remain unfinished. c0182800 and the offered 23-file Mac payload are
unchanged; no new programming/publication approval was received. Full-image,
Vivado-admission and physical-transition flags remain false.

### Connected controller/configuration subsystem

The two actual RTL components are now connected in
`rtl/boards/ypcb-00338/otpu_runtime_clock_manager.sv`. The parent FAULT state and
fabric abort drive engine cancellation; engine idle/done/error feed the control
state machine. The subsystem retains the separate endpoint reset. It passed
lint and 13 combined cases:
`build/checks/runtime-clock-manager-connected-20261018-v1/manifest.json`.
Runnable checker `tools/check_spare_runtime_clock_manager.py` freezes all three
RTL files and `boards/ypcb-00338/sim/tb_runtime_clock_manager.sv`.

All four modes activate through configuration, calibration, initialization and
reload attestations in the bench. Additional cases cover repeated compute-only
changes, endpoint reset while the actual engine owns a partial write, abort and
parent timeout with an in-flight AXI request, readback error propagation, stale
lock, model-upload abort/drain, flushed-command suppression and cancellation
during the second clock's write. The bench models clock-IP, calibration and
native-drain boundaries; the source hashes match the exact 21-case control and
13-case configuration components. It is not actual vendor-IP or board execution.

The runtime request/audit and refresh helper bind these proofs. Full top,
both-host always-on routing, native drain/CDC, actual-rate measurement and
physical DDR/inference transitions remain unfinished. The following actual
vendor-IP-connected manager model now strengthens the earlier behavioral test.

Next executable steps:

1. Preserve the completed TinyStories pass and owned-server closure. Do not
   restart or repeat already passed tests without a new concern.
2. Obtain the exact c0182800 permanent program/verify/boot authorization and the
   separate scoped Mac-runtime commit/push authorization. The bitstream, MCS,
   SRAM/result evidence, byte-checked command and isolated Git payload are ready.
   Never interpret a status question or SRAM scope as permanent approval.
3. If approved, finish flash program/verify/boot and live identity, then publish
   authorized ordinary Git files and provide Mac pull/run commands. Never use
   an archive or require the large bitstream on an already flashed Mac card.
4. Continue ready exact reviews and host/package preparations for corrected
   clock/startup candidates. Do not leave completed images pending behind
   unfinished experiments. Runtime clock transitions remain a separate incomplete
   feature; original lane-6 diagnosis/CH0 ECC stay last.

### c0182862 rejection and c0182863 source correction

The actual final report and unchanged pre-bit gate rejected c0182862. Receipt:
`build/checks/c0182862-setup-rejection-20261018/manifest.json`.
Setup -0.319 ns / TNS -213.112 ns / 1,819 failing endpoints; hold +0.034 ns,
zero hold/pulse failures. Both final reports and checkpoint hashes are preserved.
The worst path is quantizer `e_reg[27]` to TMEM `pw_a_reg[3][0][4]`, 14 logic
levels, 6.966 ns data path (6.141 ns route). No `.bit` or package exists; do not
program it or waive timing. Boundary/final-worker incomplete receipts reflect
the rejected implementation, not a CDC parser failure. The queue admitted
c0182461 after the exact c0182862 wrapper exited. The refresh helper records the
technical rejection and now selects c0182450 as the first unrejected faster
candidate, rather than restoring c0182862 as a hardware target.

The reserved successor is c0182863 at the same 148.837 MHz / DDR1066.667,
4 GiB, lane mapping/ECC/firmware and JTAG/PCIe interfaces. The quantizer keeps
`e_nz` beside the offset, computed from the exact 32-bit next value, removing the
wide zero comparison from the reader/grant path. No pipeline cycle is added;
an RTL assertion checks the predicate while busy. Root RTL and active frozen
sources were not edited. Isolated source/model:
`build/checks/quant-reader-nonzero-c0182863-20261018-v2/`.
All 38 MCOLS=4/ACT_ROWS=4/LANES=8 board cases matched ISA DRAM and retired
instructions, including QACT/QST, fused scaling, matmul and two stall/seed sets.
The v2 numerical service invocation `18f8a0a129b44bfd8f938008e2c4cf14`
finished PASS. v1 failed before compilation when an imported memory address
shadowed the output-directory variable; its stale original manifest, external
terminal disposition, worker and journal are preserved in v1. RTL was unchanged
between these launcher attempts.

Complete frozen FPGA source preparation now exists in
`build/fedora-vivado/spare-shared-dual-c0182863-20261018/` via
`tools/prepare_spare_quant_reader_successor.py`. It requires the 38-case proof,
checks for retained synchronous `e_nz` registers after synthesis and preserves
all route/setup/hold/pulse/DRC gates. A copy of the unchanged timing/route gate
runs before optional long reports; it never weakens the final pre-bit gate.
Five Tcl preparation cases passed against real positive/negative reports in
`build/checks/c0182863-preparation-gates-20261018/` (Vivado cell queries mocked).
They do not establish synthesis or timing closure.

Matching host/calibration/complete-reader packager preparation, nine host guard
cases and six real firmware-binding cases passed. Registry:
`build/handoffs/quant-reader-c0182863-runtime-preparation-20261018.json`.
Host tree `build/handoffs/spare-shared-dual-host-c0182863-20261018-v1/host/`;
packager `build/checks/spare-shared-dual-packager-c0182863-20261018-v1/complete-cdc/`.
c0182863 **finished implementation successfully at 03:39:07 UTC**. Its old
wrapper PID 1664090, start ticks `63419114`, exited zero. The supervisor had
admitted it after observing c0182450's real wait status 256 (exit 1). Supervisor
`opentpu-c0182863-priority-implementation-v1-20261018.service`, invocation
`901c33306c1a4ab1bcea81f89a908a13`, MainPID 1656704; launch/frozen worker:
`build/checks/c0182863-priority-admission-20261018/`. Its live receipt is
`run/manifest.json`, now `PRIORITY_IMPLEMENTATION_COMPLETE_EXACT_REVIEW_DUE`.
It released producer PID 1523449 after exact completion. The producer admitted
c0183120 and c0183130 within the global two-implementation limit. Existing
child exits were observed from their exact retained Linux wait statuses
and written into the legacy completion receipt, so collectors can review a
finished image while the producer is held. Zero/nonzero/signal exit decoding
was verified against actual kernel children. No frozen queue/source file was
modified. A unique admission lock prevents a duplicate priority owner.

The exact seven-phase review/package workflow **finished PASS** in
`build/checks/spare-shared-candidate-final-c0182863-20261018-v2/worker/manifest.json`.
Its unit was `opentpu-c0182863-review-pipeline-v2-20261018.service`, invocation
`ea435d4e86bc4ca9ac0ae6392cafed9d`. All five v1 evidence collections completed
successfully. The first final reviewer then hit `KeyError('bytes')` because the
synthesis producer records path/checksum/register-count without a size. This was
a reader schema failure before technical disposition, not an FPGA rejection.
The immutable v1 worker/log/source remain preserved. Fresh v2 retained every
other reviewer line and all existing gates; the new reader always checks the
recorded content checksum and also checks size when present. Five actual-schema
and wrong-hash/size/register guards passed. Future producer preparation now
records the size too; no active/frozen producer or implementation was changed.
V2 reused all five exact completed collections without rerunning Vivado, then
completed final disposition and packaging immediately. The reviewer requires
the 38-case proof, exact quantizer source and retained-register synthesis receipt;
all existing numerical/endpoint/package gates remain. Replay against the actual
completed c0182800 reports passed as a tool preflight, not c0182863 qualification.
Six global-reset exclusion cases also passed. This review owner never starts a
build or accesses hardware. Package:
`bitstreams/spare-dual-host-4gb-c0182863/`, manifest SHA256
`143554ed99423f024344a916e5b6c7ee1e53d210a78bfa5d9b534762bd1dbdfb`.
Bit SHA256 remains
`03b513a44544009afff9dfb82515bf84c5df84ac6a63673a0882308ce8a323ae`.
It retains 148.837209 MHz compute / DDR1066.667 / 4 GiB, CH0 spare lanes
`[0,1,2,3,4,5,8,7]`, CH0 ECC off / CH1 ECC on, c0172160 startup and c0172168
CH0 calibration, registered reset and both JTAG/PCIe runtime paths. All 1,993
non-info CDC rows were dispositioned, all 40 package/SRAM gates passed, and
physical qualification remains separate. Full failure/fix disposition:
`build/checks/spare-shared-candidate-final-c0182863-20261018-v2/disposition.json`.

The preparation registry now records actual admission/review launch hashes;
the refresh helper tracks them, the global implementation count and the held
producer, and will not restore old "not admitted" or c0182862 hardware targets.
Do not restart the finished c0182863 implementation or duplicate its completed
review owner. The matching SRAM commands now bind the successful v2 review;
execute after the current c0182461 hardware workflow releases ownership. No programming or
publication approval has been received for any new permanent operation.

### AXI admission guard and remaining native tail

`rtl/boards/ypcb-00338/otpu_axi_ordered_drain.sv` passed 22 cases in
`build/checks/runtime-axi-admission-drain-20261018-v1/manifest.json`.
It preserves AXI payloads and presented stalled addresses, backpressures W until
an AW header exists, tracks lengths/ordered IDs/responses, detects protocol or
late requests, keeps admission closed across reset/reclock and requires a fresh
separate downstream-tail handshake. This is for the selected ordered fabric;
bind that contract and all CDC/reset handshakes during full integration.
The exact production `otpu_sfifo` body is extracted for the unit check; only its
existing FPGA declaration-initialization style warning is narrowly scoped off.
The original full-file warning inventory is checked separately; new guard lint
warnings remain fatal and no numerical/image gate is changed.

Source audit `build/checks/runtime-native-tail-source-audit-20261018.json`
records why B/n_wdone does not prove raw DDR completion: the counter follows
native command acceptance, while the shared adapter can still hold its write.
The complete held native/bridge/PHY drain handshake remains unimplemented and
unqualified. The fresh core observations below expose the actual pending state;
they do not complete that handshake. The request/audit and progress helper retain
`full_native_drain_qualified=false`; the AXI component is not a complete barrier
or runtime-clock image.

Fresh full memory core:
`build/fedora-vivado/spare-runtime-activity-memory-core-20261018-v1/`.
`tools/prepare_spare_runtime_activity_core.py` retains the complete two-channel
data path and CSR rows and adds four two-bit outputs: `runtime_native_idle`,
`runtime_controller_idle`, `runtime_phy_idle` and `runtime_tail_error`.
`tools/litedram/runtime_native_observer.py` observes actual adapter FSM/FIFOs,
raw accepted-command/data events (including BIST), bank queue locks/timing
controllers, scheduler/refresher FSMs and the PHY's real command/read/write/OE
pipelines. Refresh remains enabled. These are observations, not a held drain ACK.

`build/checks/runtime-native-activity-controller-20261018-v4/manifest.json`
finished PASS, exec session 5120 exited zero; PID 1674860 is gone. All 28 actual
controller cases passed across both rates/shared and ECC paths. Cases establish
late-payload and response-buffer holds, zero-mask/RMW completion, both ECC
encoders and BIST done preceding real controller recovery; periodic refresh
continues. Four fail-closed guards and a no-native-endpoint-driver check passed
in `build/checks/runtime-native-error-guards-20261018-v2/`. Twenty source/ABI
checks passed in `build/checks/runtime-activity-core-lineage-20261018-v2/`.
The model supplies zero PHY read data and does not simulate the new physical
PHY taps or board bridge/CDC. Canonical registry:
`build/handoffs/runtime-native-activity-current-20261018.json`.

Failed checker predecessors are preserved: v1 hit pinned Migen's write-only
memory lowering limitation; v2 had an observation bound shorter than the actual
two-period refresh postponing; v3 sampled registered handshakes before Migen's
commit and duplicated a ready-high command. v4 adds only unused simulation read
outputs for write-only ports, derives the refresh bound from real settings and
samples on the opposite testbench edge, with exact ECC command-count assertions.
No data-path logic, controller timing or error check was relaxed for these fixes.

The first 16-case vendor reset probe covered the data-clock reset copy and
passed. It did not cover the command path's extra falling-edge register.
The extended actual MMCM/BUFG/FDRE command-path probe reproduced a missed reset
in six of sixteen cases:
`build/checks/runtime-reset-clock-order-actual-ip-20261018-v2-command-path/`.
That supersedes the earlier limited no-defect disposition. The two older runtime
memory-core preparations are retained as component parents/evidence and are
ineligible for direct full-runtime integration.

The source correction is now complete in a fresh full core:
`build/fedora-vivado/spare-runtime-async-phy-memory-core-20261018-v2/`.
`tools/litedram/runtime_phy_reset.py` asynchronously asserts serializer reset
from the independent memory-reset/clock-readiness signals and PHY clock lock.
One common two-stage release chain per CLKDIV domain feeds registered pad
copies, so release is coherent. Actual asserted/released status is exported
for each channel. The first generation attempt failed on a repeated platform
resource request; the corrected preparer looks up the already reserved inputs.
That failed preparation and the first probe's compile failure remain preserved.

The corrected graph passed 96 actual vendor cases across both paths, both
rates, three command-clock phases and eight assertion offsets. The generated
core passed 211 source/graph/ABI checks: four common chains, 163 pad reset copies
and 341 actual serializer endpoints with matching CLKDIV domains. Receipts:
`build/checks/runtime-phy-async-reset-20261018-v4/manifest.json` and
`build/checks/runtime-async-phy-core-source-review-20261018-v2/manifest.json`.
Final source disposition:
`build/checks/runtime-phy-reset-correction-disposition-20261018-v3.json`.
The corrected core is selected for source integration; full board/reset/CDC,
all-mode timing and physical transitions are unqualified. Fixed-clock images
and active frozen implementation sources are unchanged.

Fresh bridge observations are prepared by
`tools/prepare_spare_runtime_bridge_observer.py` in
`build/checks/runtime-bridge-observer-preparation-20261018-v1/`.
Removing only the new ports and observation blocks restores the production
bridge byte-for-byte. Core/host/native idle and native-error outputs are
registered in their own domains. The numerical/CDC regression finished PASS:
`build/checks/runtime-bridge-observer-numerical-20261018-v1/manifest.json`,
exec session 52488 exited zero. Seven cases retain the original scoreboards and
also require both channels' three local idle observations after traffic ends.
Lint matches the baseline's five known filename/unused-signal warnings, with no
new warnings. These are local observations, not a held drain ACK; the actual
fresh request/ack, admission closure, memory-core state and CDC must be joined
next. No full runtime image is prepared or admitted.

### Held drain join and guarded manager components

`rtl/boards/ypcb-00338/otpu_runtime_drain_domain.sv` and
`otpu_runtime_drain_join.sv` implement local four-phase participants and an
always-on owner. Core/host source acknowledgments precede the memory-tail probe.
Fresh low requests, stable idle, stale ACK rejection, absent clocks, late work,
errors, release and guarded retry passed 22 cases at all four clock combinations:
`build/checks/runtime-held-drain-join-20261018-v1/manifest.json`.
The native hold-safe contract permits background refresh after user work drains.
Participant resets are supervisor resets, independent of functional source
resets held during maintenance. The Icarus enum-ternary prototype failure is
preserved; explicit branches retain identical behavior.

The production bridge/adapter/raw-accounting integration passed seven cases:
`build/checks/runtime-held-drain-connected-bridge-20261018-v4/manifest.json`.
Cases include delayed posted writes, mid-traffic resets, compute held during
host upload and host held during native work. The first fixture's default
cycle-39 reset release defeated its initial hold stimulus; its coverage
disposition is preserved. Correcting the fixture reproduced the older observer's
maintenance deadlock. A reset-release transition then exposed a one-cycle host
idle gap. The selected fresh observer remembers coherent holds through release:
`build/checks/runtime-bridge-quiescence-preparation-20261018-v3/`.
Production data-path source remains byte-exact after removing only observations.

`rtl/boards/ypcb-00338/otpu_runtime_clock_guarded_manager.sv` gates clock work on
actual drain release and compute/PHY reset acknowledgment. Lost proof cancels
only after the owned AXI transaction ends. Held fence faults keep the control
plane available; retry is restricted to a faulted activation with an idle clock
engine. A latched fence fault also blocks new configuration from SAFE.
All 13 prior cases and eight new guard cases passed:
`build/checks/runtime-guarded-clock-manager-20261018-v1/manifest.json`.

Canonical registry: `build/handoffs/runtime-held-drain-current-20261018.json`.
Actual both-host guards, CSR/BIST/PHY/reset wiring, full top, all-mode timing/CDC
and physical transitions remain unqualified. The connected test uses behavioral
native controllers and testbench admission closure. No full runtime image is
prepared or admitted.

### Connected runtime control and final calibration mailbox

The assembled `otpu_runtime_board_control.sv` joins the actual held-drain
controller and guarded clock manager. Twenty assembled cases passed:
`build/checks/runtime-board-control-assembly-20261018-v1/manifest.json`.
These are component simulations; the complete dual-host board is not connected.

Calibration-ready and the state CSR can precede the firmware's final mailbox
store. The new read-only observer watches that actual CPU mailbox write before
reporting success. Twelve actual SelfCal bus/hold/mailbox cases passed in
`build/checks/runtime-calibration-final-mailbox-20261018-v2/manifest.json`.
The v1 test's incorrect external-hold/reset expectation is preserved separately.
The selected generated memory component is now
`build/fedora-vivado/spare-runtime-cal-status-memory-core-20261018-v1/`;
217 generated-source/reset/ABI checks passed in
`build/checks/runtime-cal-status-core-source-review-20261018-v1/manifest.json`.
Selector: `build/handoffs/runtime-board-control-current-20261018.json`.
Full top, both-host admission/routing, mode firmware, measured-rate identity,
all-mode timing constraints and physical transitions remain unfinished. This
is not a complete image or an admitted Vivado build.

### Full runtime board source integration now started

Current selector:
`build/handoffs/runtime-full-top-preparation-current-20261018.json`.
The fresh full source tree starts from frozen c0182863 (including its quantizer
correction) in
`build/fedora-vivado/spare-runtime-board-integration-20261018-v1/source/`.
It connects the tested quiescent/held bridge observations through both channels
of `otpu_native_sys` and exports registered actual execution-idle, execution-error
and functional-reset-held state from the complete accelerator. Full native
subsystem elaboration passed; removing the observation additions restores the
original board/native datapath source byte for byte. This is not full-top
elaboration, all-mode timing or a native-drain qualification.

The AON BD source is prepared in
`build/fedora-vivado/spare-runtime-aon-bd-20261018-v1/` via
`tools/prepare_spare_runtime_bd.py`. Compute clock/reset are external; JTAG,
calibration, XADC and the new runtime-control window use 50 MHz AON routing;
the independent 250 MHz host DMA clock and full PCIe paths remain. Raw PCIe
DMA/control masters leave the BD before SmartConnect buffering so the complete
top can install actual upstream guards. A guard only after SmartConnect cannot
prove that its hidden accepted/posted work has drained. Tcl source completeness
passed. Actual Vivado BD validation and wrapper generation subsequently passed
in `build/checks/runtime-aon-bd-vendor-20261018-v1/manifest.json`: all 12 runtime
interfaces, four clock ports, separate reset nets and 16 control address-map
segments matched. Exec session **51860** exited zero. This ran at nice 10 with
one Vivado thread, without synthesis, implementation or hardware access.
Full-top guard connections and all-mode timing/CDC remain pending.

Both-channel mode firmware is rebuilding against the selected runtime core's
actual CSR map, with the original firmware IDs allowed only after exact binary
reproduction. DDR800 reproduced c0172608 SHA256
`f93adc92ece3cbd6b467540723082f112d2647e91e9638347d3aa87acd82b8ab`;
all seven host-reference cases and actual reference RV32 RTL execution passed.
DDR1066 compilation reproduced c0172668 SHA256
`39d9d35e144192e19cd6f2091094d8456cc1de96ec93743d872d82c88a5cf9a4`;
its seven host checks and actual reference CPU execution also passed. Both modes
are complete in `build/checks/runtime-mode-firmware-20261018-v2/manifest.json`;
exec session **56746** exited zero and PID 1715635 is gone. The host
explicitly sets channel mask 3 and stride 1 (`selfcal_config=0x103`) while held;
this does not rely on the old CH1-only boot default. Receipt:
`build/checks/runtime-mode-firmware-20261018-v2/manifest.json`.
The completed worker's exact start ticks/argv and source hashes remain in the
selector. Both firmware binaries retain their existing identities by exact bytes.
The first preparation-only attempt used `variant-profile.json` instead of the
runtime core's `runtime-profile.json`; its failed source/receipt are preserved
under v1. No generated core, FPGA implementation or hardware was changed.

The full top still needs upstream guards and fresh source acknowledgments for
both hosts, coherent data/control aborts, actual manager/clock/memory hookup,
independent rate measurements/static identity, all-mode constraints and matching
transition host tools. Do not label these partial sources an admitted build.

Deeper elaboration also exposed the fixed ABI2 read-address overlap at `0x60`
and `0x64`: writes set ARG0/1, while reads return lane/ECC identity instead of
argument readback. The supplied `Board.set_args` path only writes arguments;
existing TinyStories/ISA results and identity guards remain valid. Direct actual
control RTL simulation reproduced both read aliases, verified all eight
argument writes, and verified all eight reads after removing the two aliases in
the fresh runtime source. Receipt:
`build/checks/runtime-argument-map-20261018-v2/manifest.json`.
The active native source tree for the future runtime top is now that receipt's
`source/`, including all previous observation integration. Its replacement
lane/ECC identity must be wired in the unfinished AON endpoint and matching
host profile. Fixed-clock builds/packages and the loaded SRAM image were not
modified. The first check's restoration assertion selected the earlier write
case; its failed fixture/source are preserved in v1. Actual RTL was unchanged
between those fixture attempts.

The prepared 23-file Mac Git payload now documents these fixed-image read/write
semantics in its existing `docs/mac_c0182800.md`. No runtime code changed. Total
size is 164,604 bytes, largest 35,606; its normal Git-worktree preflight v3 passed
without opening a device. The prior proposal is preserved before this doc-only
revision. No stage, commit or push occurred, and the root index is unchanged.

The full-top JTAG frontend now has a separately reviewed control-abort variant:
`rtl/boards/ypcb-00338/otpu_runtime_jtag_axi_control_abort.sv`.
It retains data-abort isolation, adds coherent flushing of AXI-Lite requests
when the AON control fabric/endpoint resets, and exports AON-local data-idle
state. A control-only flush leaves an independently owned DMA transaction
intact. Strict lint, the original 24 direct/15 serial cases and ten added cases
passed: 31 direct plus 18 serial/controller cases total. The actual clock
controller retained its pending transition across its bus reset, with both
target clocks stopped and no fabricated activation. Receipt:
`build/checks/runtime-jtag-separate-control-abort-20261018-v1/manifest.json`.
The old frontend/proofs remain unchanged. The full top must bind this abort to
the matching actual control fabric and endpoint reset; board CDC/timing and
physical transitions remain unqualified.

Current hardware selection now comes from
`build/handoffs/current-shared-hardware-session-20261018.json`.
The refresh helper follows the selected session's exact receipt paths and
process identities, so it can advance from c0182461 to c0182863 without
restoring stale image IDs. The generic hardware consistency checker passed 17
checks on c0182461 in `build/checks/current-shared-hardware-c0182461-20261018-v2/`.
The prepared c0182863 session is not selected until the current hardware work
and XVC owner finish. Preserve permanent c0182800 authorization scope separately.

### Clock-IP test-tool correction and actual connected-manager pass

The read-only v3 GDB sample had no symbols and did not establish a defect.
A later interface-only comparative experiment did: the unchanged bench stalled
in elaboration even with vendor IP removed, with XSim sensitivity warnings for
`@(posedge runtime_clk[target])` inside an automatic task. Changing only the two
event-control statements to explicit `[0]`/`[1]` clock edges removed the warnings
and elaborated in 2.82 seconds. Settling/sample counts, four transitions, ten
period checks and tolerances were unchanged. Diagnostics:
`build/checks/runtime-clock-ip-tb-elaboration-diagnostic-20261018-v2/` and
`...-v3-static/`. The first diagnostic's library-name error is preserved in v1.
These stubs were never used for clock qualification.

After the comparative reproduction, the original v3 service and its exact
native process were stopped and confirmed gone; the obsolete dynamic-event
diagnostic group was also stopped. v3's original manifest/bench/checker, static
event diff and `completion-disposition.json` are preserved. Its cancellation was
for an isolated test-tool defect, not merely an observation deadline. The
current helper/request/audit select v4 and cannot restore v3 as live.

The real manager/controller/configuration-engine RTL was then connected to both
actual generated Clocking Wizard IPs in
`boards/ypcb-00338/sim/tb_runtime_clock_manager_ip.sv`. Checker:
`tools/check_spare_runtime_clock_manager_ip.py`; result:
`build/checks/runtime-clock-manager-actual-ip-20261018-v1/manifest.json`.
All four mode activations (0,1,3,2; epochs 1..4) and ten output-period checks
passed. Measured model periods were exactly 10 ns, 6.718750 ns and 7.5 ns for
100/148.837209 MHz compute and 100/133.333333 MHz memory-controller clocks.
The real engine verified all setting words and required fresh unlock/relock;
compute-only changes preserved the memory clock/reset. This confirms actual
vendor-IP protocol integration. Native drain, calibration and PHY readiness
were modeled, and no board/workload clock transition was performed. Full-image,
Vivado-admission and physical-qualification flags for this runtime feature stay
false. Both public benches use static clock events; all frozen attempts remain.

c0182450 has a terminal real setup rejection (-0.506 ns, 3,846 failing endpoints)
in `build/checks/c0182450-setup-finding-20261018/`. Its worst path is sequencer
`sstarted_reg[1]` to `g_cmd[0].q_reg[195]_rep`, separate from c0182862's quantizer
path. Its unchanged pre-bit gate rejected the image, the wrapper exited 1 and
no bitstream was emitted. Reports and final checkpoint hash are preserved.
Do not qualify/program it. The priority supervisor recorded its exact exit,
kept the legacy collector receipt current and started c0182863 without exceeding
two live implementations. c0182863's project creation has completed; synthesis
and final image gates remain pending.

The canonical refresh entry is
`build/handoffs/refresh-dual-interface-progress-20261018.py`; its legacy entry
forwards to it. It tracks current v2 boundary/final owners, the live physical
launch and continuous Vortex exclusion. Retired PCIe-only c0182301 remains a
historical source/model/firmware dependency, never an active programming target.

### Complete runtime top source connected, not admitted

The current source-only runtime target is `c0184800`, in
`build/fedora-vivado/spare-runtime-full-top-20261018-v6/source`.
The complete accelerator, corrected shared-response 4 GiB memory-core interface,
both PCIe guards before SmartConnect, AON USER2/control/identity and actual clock
configuration engine are connected. Structural elaboration passed with all 313
exact BD ports. Vendor/memory/clock IP bodies are black boxes for this gate;
this does not substitute for implementation or physical transition evidence.

Actual-rate/identity RTL passed 23 functional cases. Nine actual accelerator
CSR/argument/loader cases passed, and the complete native subsystem elaborated.
Its idle observation now covers accepted LOAD and both loader-pending cycles.
The AON capability source is the actual accelerator CAPS constant; configured
core/DDR reports are separate from the measured source-edge rates.

Reset review of the first connected top caught a decoded control-reset counter
and participant reset release before an initially stopped clock began. Fresh
v5 uses registered global/control resets and independent reset-release chains
for each participant. The byte-exact reset prefix plus registered host-reset
RTL passed nine cases, including PCIe absence and managed/unexpected lock loss.
Prior source preparations and checker failures are preserved. Early checker
failures included unrelated unused tops and non-ANSI vendor-header handling;
the corrected reader retains fatal missing-port and implicit-net checks.

Receipts:

- `build/checks/runtime-aon-identity-20261018-v2/manifest.json`
- `build/fedora-vivado/spare-runtime-native-status-20261018-v2/manifest.json`
- `build/fedora-vivado/spare-runtime-full-top-20261018-v5/manifest.json`
- `build/checks/runtime-full-top-elaboration-20261018-v4/manifest.json`
- `build/checks/runtime-full-top-reset-prefix-20261018-v2/manifest.json`

Next owner: active OpenTPU goal. Complete connected race/transition models,
all-mode timing/Gray/CDC constraints and the AON host initialization/model
workflow, then freeze/admit the full image. `full_runtime_image_prepared`,
`full_native_drain_qualified` and `vivado_enqueued` remain false.

The selected v6 also handles compute MMCM lock edges with the same coherent
control flush as memory lock edges. Unexpected compute unlock faults the
activation, while managed unlock preserves configuration-engine ownership.
The reset-prefix model passed 11 cases after this correction. The actual board
controller, held join and guarded manager also passed four modes and ten
measured periods with generated vendor IP, stalled control/host/native fences,
and the byte-exact top control-flush fragment. An injected unexpected compute
unlock left the AON fault read reachable and DDR reset low. These checks model
external traffic/PHY/calibration; they do not qualify actual both-host/native
traffic or physical transitions.

Latest receipts:

- `build/checks/runtime-full-top-elaboration-20261018-v5/manifest.json`
- `build/checks/runtime-full-top-reset-prefix-20261018-v4/manifest.json`
- `build/checks/runtime-board-control-actual-ip-20261018-v3/manifest.json`

The first extended-clock test had a declaration-order fixture error before
simulation; its failed receipt is preserved separately from the successful v3.
No FPGA implementation was started or restarted for that fixture correction.

### Runtime AON host protocol and exact mode data

`opentpu/host/runtime_clock.py` implements the source-only runtime host protocol
without opening a device or programming the FPGA. Destructive DDR transitions
upload and verify the exact mode firmware while held, select both channels and
stride one, wait for the hardware final-mailbox completion, zero/verify all
4 GiB including CH1 parity, and upload/read back the complete CHASH model image
before MODEL_DONE. It uses no legacy core CSR during maintenance. Compute-only
changes preserve this connection's verified resident model and signal that the
runner must reload IMEM/arguments and restore the verified DRAM-init marker.

All mutations are serialized in-process. Failure prevents further mutation;
read-only AON snapshots remain available when the underlying transport is alive.
Fresh rate checks precede MODEL_DONE, and readiness/ECC checks include the final
initialization chunk and the completed model readback. A new connection does
not trust a previous connection's unverified model residency.

The exact SDK, existing firmware helper and CHASH mapper passed 25 host tests:
`build/checks/runtime-aon-host-protocol-20261018-v2/manifest.json`.
Hardware registers, CPU effects, BIST and DMA are modeled in these tests.
The small source/data preparation
`build/handoffs/runtime-host-mode-data-20261018-v6/manifest.json` binds the exact
mode binaries to their successful RV32 CPU receipts, active full-core CSR map,
eight-/nine-lane PHY configs, common structural latency and CL6/CWL5 or
CL7/CWL6. Its metadata explicitly grants no hardware-opening authority.

The reviewed-image transport factory and complete compiled-model/program
runner still need integration. This does not admit c0184800 to Vivado or claim
physical runtime transitions. The current selector, refresh helper and table
retain these gates separately from the passed protocol/data preparation.

### Runtime AON transport/profile source components

`opentpu/host/runtime_transport.py` now provides exact-reviewed-profile JTAG,
Chestnut and XDMA adapters. Source-only mode-data preparations are ineligible
for device opening. Full and small runtime package contracts require the same
actual artifact, CDC/Gray/reset, all-mode and connected-source review bindings;
small Mac runtimes do not require a local bitstream. No c0184800 package yet
satisfies these gates.

The new JTAG adapter reaches the AON bank without widening old-image address
semantics. Chestnut has a default-preserving BAR identity address hook; the
runtime subclass probes AON while compute can be held reset. Constructors
create local CSR wrappers without touching the denied memory/calibration bank
in SAFE. DDR I/O requires an allowed phase, memory validity, ready channels,
locked clocks and clean ECC. Premature core CSR requests are rejected before
poisoning AON access. Board wrappers retain the device lock through final
transport teardown across transitions.

The component suite plus existing Chestnut/JTAG tests passed 59 checks:
`build/checks/runtime-aon-transports-20261018-v3/manifest.json`.
USB/JTAG/XDMA and normalized review inputs are synthetic test fixtures; this
is not a physical PCIe/DDR or real-runtime-package qualification. The first
extended constructor fixture returned an incorrect unused-BAR mask; its
failure/source are preserved separately and the corrected fixture passed.

Current small host-mode source/data:
`build/handoffs/runtime-host-mode-data-20261018-v6/manifest.json`.
It binds the exact prepared CPU-proved firmware and pins all nine shared host
source files, including the changed Chestnut hook. An older checkout fails
preflight before opening hardware. The prepared c0182800 Mac worktree remains
separate and unchanged by these prototype transport/source changes.

Next: connect actual final-review packaging to the profile contract, finish
the compiled-model/program runner and remaining connected-traffic/all-mode
source gates. The runtime image remains unadmitted. Preserve c0182800 hardware
for Mac acceptance; perform no additional programming without a user request.

### Always-on serial clock-control component

Fresh RTL `rtl/boards/ypcb-00338/otpu_runtime_jtag_axi.sv` provides three independent
AXI-Lite destinations: accelerator, calibration and AON clock control at
`0x20000`. Closed data admission returns `0x81`; a coherent data-fabric flush
returns `0x80` for interrupted data transactions without canceling the AON
control transaction. An admission change alone does not cancel issued AXI work.
The existing fixed-clock frontend and all active frozen build inputs are intact.

`build/checks/runtime-jtag-control-component-20261018-v1/manifest.json` passed
strict frontend/controller lint, 24 direct request cases and 15 actual serial
mailbox/controller cases with both target-clock signals held low. The serial
bench verifies real mode-register writes, START/configuration wait, fault
visibility and recovery; its absent configuration engine, PCIe/native/PHY and
target clocks are not substitutes for a full transition. The reproducible
checker is `tools/check_spare_runtime_jtag_control.py`.

The full top still needs an independent AON clock/reset domain, the third control
destination and PCIe access, static identity/actual-rate reporting, real native/
controller/BIST drain, reset/CDC and mode-specific firmware integration. No full
runtime image is prepared or admitted, and no physical transition is qualified.
Continue this actual board-source integration while fixed-clock implementations
run. When a fixed-clock image passes its own review/package, execute its matching
already-authorized SRAM workflow promptly; do not wait for runtime-clock work.

## 1. Objective, scope and authorization

The working objective is usable **full 4 GiB OpenTPU**, with CH0's unreliable
physical byte lane 6 bypassed by lane 8, improved CH0 read bandwidth, combined
PCIe/JTAG memory access, and qualified compute/DDR clock candidates.
The user also requested one image that changes compute and DDR clocks at
runtime. That feature is only partially prepared, as detailed below.

The intended sequence is usable integration and performance first;
**original lane-6 root cause and restoration of CH0 ECC remain last**.

The user's standing instructions, also captured in `AGENTS.md`, are:

- Finish preparation autonomously: code, firmware, builds, collection, exact
  final review, packaging, host tools and runnable instructions.
- Temporary SRAM configuration and requested SRAM checks require no new
  approval, provided exact technical gates and exclusive ownership are met.
- **Permanent flash writes require explicit approval for that exact image and
  operation.** Approval for one image does not transfer to another successor.
  Do not repeat an already granted approval for the same exact operation.
- Honor the selected host: Fedora had JTAG only; the Mac has Chestnut for
  PCIe data access. Do not invent a Fedora PCIe gate for an explicitly approved
  flash-here/test-on-Mac workflow.
- No old-flash backup was requested for the c0172300 operation.
- **No more standalone RAM soaks.** The user stopped them after successful
  full-capacity evidence. Small transfer, mask, program-upload, numerical and
  inference checks are the useful next work.
- Keep original lane diagnosis deferred even though the current new-image
  regression is again channel-specific. These are separate investigations
  until evidence links them.
- No tar/tgz/zip/archive handoffs, including an archive recommended as a
  workaround. Use normal Git source/configuration/metadata files.
- Do not commit large bitstreams, checkpoints, generated netlists, weights,
  caches or logs. Keep local artifacts and record identity/hash/build commands.
- Preserve unrelated staged, unstaged and untracked changes. No broad
  `git add .`, reset, stash, clean or bulk deletion.
- A recorded request is not a queued implementation. A generated bitstream is
  not automatically reviewed, packaged, programmed or physically qualified.
- A paused agent does not imply that existing background builds should stop.

## 2. TODO progress table

**Priority CH0/LFM regression acceptance passed on c0182800 through Mac/Chestnut.**
**Next Mac candidate: c0182863. Preserve the working baseline, verify
repeatability, review queued candidates and complete runtime integration.**

Rejected candidates are omitted from the displayed table at the user's request;
their immutable reports remain in the historical build/review records.

Build percentages count completed milestones: 20% frozen preparation,
40% synthesis, 60% completed routing, 80% bitstream produced, 100% exact
review/package. They are not time estimates or physical qualification.
An image rejected at final review stays at 80% on this scale.

| Priority / task | Compute / DDR | What changed / purpose | Build completion | Current result / next action |
| --- | --- | --- | --- | --- |
| **1: CH0 data-path repair `c0182800`** | 100.000 MHz / DDR800.000 | Shared CH0 response bus, registered reset, combined JTAG/PCIe; 100 MHz baseline | 100%: Mac Chestnut LFM230M and Qwen3.5-2B passed; published results pulled; cold/warm repeatability and matched A/B pending | Original Mac LFM230M and Qwen3.5-2B passed; preserve working baseline; cold/warm repeatability and matched comparison remain pending |
| `c0182863` | 148.837 MHz / DDR1066.667 | Registered quantizer nonzero predicate; shared CH0 response bus, registered reset and JTAG/PCIe retained | 100%: Local JTAG TinyStories and native benchmark passed; clients closed; Mac LFM/PCIe pending | Authorized permanent operation: PASS_C0182863_PERMANENT_PROGRAM_VERIFY_FLASH_BOOT_LIVE_IDENTITY_AND_JTAG_RELEASE; Mac LFM/PCIe remains pending |
| `c0182461` | 100.000 MHz / DDR1066.667 | Shared CH0 response bus, registered reset, JTAG/PCIe; 100 MHz compute / DDR1066.667 | 100%: Local JTAG TinyStories and native-read benchmark passed; original Mac LFM/PCIe acceptance pending | Local SRAM/identity/calibration, initialization, program fetch, matmul, full model readback and eight ISA tokens passed; original Mac LFM/PCIe remains pending |
| `c0182600` | 100.000 MHz / DDR800.000 | Shared CH0 response, registered reset and JTAG/PCIe; automatic eight-/nine-lane mixed-width startup at DDR800, unchanged CPU-verified firmware bytes | 60%: Exact review/package blocked; diagnose preserved receipt before disposition | Exact per-image review/package and physical qualification remain pending |
| `c0182662` | 148.837 MHz / DDR1066.667 | Shared CH0 response, registered reset and JTAG/PCIe; automatic eight-/nine-lane mixed-width startup at DDR1066, unchanged CPU-verified firmware bytes | 40%: Exact review/package blocked; diagnose preserved receipt before disposition | Exact per-image review/package and physical qualification remain pending |
| Candidate native read benchmark | c0182461 / c0182863 | Same three 64 MiB native streams; completed exact-image integration is required before replacing program/output memory | c0182461 3.033203 GB/s; c0182863 4.452533 GB/s | Both exact-image benchmarks passed; original Mac LFM/PCIe acceptance and matched single-channel comparison remain pending |
| TinyStories JTAG validation | c0182800 | Trained 15M model padded to the existing tiles; 28,909,056-byte int8 image | PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS; 28,909,056/28,909,056 bytes uploaded | All image bytes and 15 program readback/load checks exact; eight ISA tokens matched; calibration unchanged |
| Native read benchmark | c0182800 | Three 64 MiB native LD streams; FPGA cycle/beat counters and final 16 KiB comparisons | PASS_OBSERVED_NATIVE_READ_BANDWIDTH_FULL_SYSTEM_QUALIFICATION_PENDING | Median 2.991651 GB/s; synthetic combined-channel result, Mac PCIe bandwidth remains pending |
| Matched one-/two-channel performance | Qwen3.5-2B INT8 | Measured current dual-channel versus prior CH1 run; cache/residency/step counts differ | Observed 1.885x bandwidth, 1.884x device decode and 1.168x wall decode; 32 tokens match prior prefix | Controlled A/B still pending; separate measured runs do not establish a general speedup |
| Original LFM230M / Mac acceptance | c0182800 | Original CH0 regression tested through Chestnut on the flashed image | PASS: eight exact ISA tokens; 14 exact program readbacks; calibration unchanged and ECC clean | Cold/warm repeatability and broader payload qualification remain pending |
| Matching Mac Git handoff | c0182800 | Original 24-file handoff published; Mac results and benchmark tools published in successor | Existing branch fast-forwarded to 00a277ac; local staged/working changes preserved | Published and pulled; backup and conflict resolution receipt retained |
| Vortex hardware return | Separate session | User requested all Vortex work stop when the priority OpenTPU build finishes | VORTEX_WORK_STOPPED_FOR_PRIORITY_OPENTPU | Vortex stopped; c0182863 permanent program/verify/boot/live identity passed and JTAG released |
| Runtime clock transitions | Separate feature | Corrected shared core, AXI drain front end, actual vendor-IP manager and isolated AON JTAG control; both interfaces mandatory | Actual board control/held drain and exact control-flush prefix passed four modes/ten vendor-clock periods, source/native fence stalls and unexpected compute-unlock fault; full traffic/PHY qualification pending | Not a complete image or admitted Vivado build |
| Native runtime activity | Separate feature | Fresh full memory core exports actual adapter/raw/controller/PHY activity; data path and CSR rows preserved | Both rates/shared and ECC paths: 28 controller cases; four fail-closed guards; 20 lineage checks passed | Integrate actual board bridge/host drain and held CDC acknowledgment; full native barrier remains unqualified |
| Runtime PHY reset correction | Separate feature | Independent async assertion and one common release chain per CLKDIV domain; actual pad assertion/release status | Command path reproduced six original failures; corrected graph passed 96 vendor cases and 211 generated-core checks | Corrected source core selected; full board reset/CDC and all-mode timing remain pending |
| Runtime bridge observations | Separate feature | Original bridge data path retained; registered core/host/native idle and native-error outputs | Seven numerical/CDC cases passed and both channels reached local idle | Fresh request/ack and actual admission closure must still be joined with the memory-core state |
| Held drain / clock start gates | Separate feature | Source-domain acknowledgments precede memory-tail proof; coherent held sources and actual reset/release gates supported | 22 cases at four clock combinations; seven real bridge/adapter tail cases; 21 guarded-manager cases passed | Bind real admission, CSR/BIST/PHY and both-host board routing; full runtime image remains unprepared |
| Runtime upstream PCIe Lite guard | Separate feature | Guard raw PCIe control before SmartConnect; independent target abort returns errors without discarding accepted source requests or held responses | 28 split-channel, backpressure, reset and target-abort cases plus strict lint passed; source correction connected in full top v7 | Complete connected both-host traffic and vendor CDC/reset qualification remain pending |
| Runtime AON identity / measured clocks | Separate feature | Count actual source edges from independent 50 MHz reference; lane/ECC metadata moved outside arguments | 23 actual-rate/identity cases and strict lint passed; nine real accelerator CSR/loader cases passed | Complete top wiring and all-mode timing/CDC pending |
| Runtime AON host protocol and mode data | Separate feature | Mode firmware upload/readback, both-channel initialization, verified model upload; compute-only preserves resident DDR and checks the activation epoch | 27 host protocol cases passed; exact DDR800/1066 CPU-proved binaries and runtime CSR/PHY data bound | Transport/profile components passed 73 checks; actual review packaging and physical transitions remain pending |
| Runtime transport/profile components | Separate feature | AON JTAG/PCIe access, 11 shared source bindings; JTAG read aborts retry at most eight times, writes never retry; completed Chestnut target errors allow only AON diagnosis, uncertain links require reconnection | 73 runtime/legacy boundary checks passed with modeled hardware | Actual reviewed runtime package, exact XDMA completion mapping, connected both-host traffic and physical transitions remain pending; c0182800 Mac worktree unchanged |
| Runtime compiled-model runner | Separate feature | Verified initial image, mandatory program readback, fresh IMEM/argument caches after compute reset; DDR changes reload weights and reset context | 47 modeled backend/protocol/CLI checks and four-segment TinyStories ISA reference passed | Source/execute-gated CLI prepared; actual runtime image, connected traffic, timing/CDC and physical transitions remain pending |
| Exact XDMA completion mapping | Separate verification | Selected Gen2 x8 XDMA 4.2 revision 4; exported endpoint retains all 962 component parameters | BLOCKED_FULL_XDMA_SIMULATION_BY_BASIC_INSTANCE_LICENSE_LIMIT; phase simulate | Inject target errors and inspect actual completions; no physical or complete-image qualification |
| Runtime rate-counter constraints | Separate component check | Registered Gray buses; valid register C startpoints and conservative fast timing period of 6.718 ns | All four views: 64 scalar paths per view, saved max-delay/bus-skew bounds and complete two-warning CDC inventories checked | Routed numerical bounds, full-top clock overlay and complete reset/CDC disposition remain pending |
| Runtime clock propagation constraints | Separate component check | Actual runtime MMCM leaves and both generated DDR write-clock MMCMs; preserve generated-clock ancestry and quadrature | Four timing views passed: 64 clock observations, 256 Gray paths and reconciled source CDC inventories | Full-top integration, reset/CDC constraints, routed numerical timing and physical transitions remain pending |
| Runtime mailbox constraints | Separate source/component gate | Independent AON receiver; per-bit held-payload bounds and first-stage-only synchronizer exceptions | 1,140 payload paths, six timed internal paths and all 1,142 CDC Warning rows reconciled; saved aliases resolved | Full-top endpoint binding, routed numerical bounds and connected traffic remain pending |
| Runtime synthesis clock settings | Actual-IP component gate | Fastest-mode synthesis-only clocks at real clock-IP boundaries; preserve boot MMCM configuration | Actual synthesis loading observed 6.718 / 7.5 ns; linked timing view filters those definitions and restores unchanged boot clocks | Component gate passed and source integrated; full-image synthesis and routed validation remain pending |
| Runtime control CDC source inventory | Preparation for complete netlist matching | Twelve real control instances and 54 annotated register members, 256 pre-optimization bits | Source inventory complete; includes merge/constant-removal matching rule and explicit memory/vendor exclusions | Actual surviving netlist endpoints and complete CDC contracts remain unqualified |
| Runtime full Vivado project | Source preparation c0184800 | Actual runtime/native top, memory, corrected AON BD and clock IP; synthesis clock, clock/Gray/mailbox and narrowed native-reset sources included | Actual project assembly and 41 saved-project/source checks passed; 962 XDMA parameters and 42 clock HDL dependencies exact | Full implementation remains unadmitted; see separate full-design source-synthesis validation below |
| Full runtime source integration | Separate feature | Tested bridge observations connected through full native subsystem; actual execution/reset state exported; AON BD exposes raw PCIe masters for upstream guards | Complete top connected and structurally elaborated against 313 exact BD ports; 11 exact-prefix reset cases and actual vendor-clock four-mode model passed | Connected transition/race proof, all-mode timing/CDC and AON host workflow remain required; c0184800 is source only, not an admitted build |
| Original lane 6 / CH0 ECC | Diagnostic history | Deferred behind usable spare-lane integration | Deferred last | No new standalone RAM soak |
| Runtime complete-netlist validation | Admitted synthesis-only source check | Full accelerator, 4 GiB memory, actual clock IPs and JTAG/PCIe retained; frozen private project, implementation guard intact | RUNTIME_NETLIST_VALIDATION_WAITING_FOR_PRIORITY_QUEUE; 16 admission cases and actual private-project Vivado audit passed | Waiting for all priority implementations to finish; inspect surviving CDC/reset bindings, no bitstream or hardware operation |
| Runtime full-top control integration | Separate connected-control check | Complete selected top/native RTL, serialized USER2, PCIe guard and actual AON identity; explicit behavioral vendor boundaries | Eight connected read/abort cases passed and scoped review complete | Full native traffic, actual vendor interconnect/XDMA, mode activation and physical qualification remain pending |
| Early DDR write-clock VCO gate | Source preparation check | Read exact generated MMCM settings and core profile; reject device VCO violations before core generation or implementation | Sixteen regressions, four saved-core controls and normal valid/invalid generation passed; ordinary/mixed full-image preparer and frozen-worker checks passed | Source VCO gate only; full primitive/DRP, numerical timing and physical DDR review remain required; no new image admitted |
| Matching Mac Git handoff c0182863 | c0182863 | Small exact-image runtime, DDR1066 firmware binding, mandatory program readback and portable instructions | 20 files / 162,405 bytes; normal Git-checkout preflight and corruption/identity checks passed | Commit 4fe69e9a on existing ypcb/dual-channel-4gb; observed on origin; no push by this session |
| Permanent flash c0182863 | c0182863 | Existing BPI16 MCS checked against exact bitstream and completed 40-gate SRAM receipt; native program/verify/boot workflow | Program, independent verify, flash boot INIT/DONE and live USER2 identity passed; JTAG released | Ready to power off/move to Mac; cold power cycle and Mac LFM/PCIe remain pending |
| Mac flash guide update | c0182863 | Exact MCS checksum, JTAG/Vivado program, separate verify, boot and Mac identity steps; Chestnut-only limitation explicit | Two-file commit f432e10 on existing branch; runtime payloads unchanged | Observed on origin; Mac can pull the guide update; no push by this session |
| Requested LFM repeat | c0182863 current selected image | Fresh identity, calibration, initialization, matmul and exact ISA token/program checks through Chestnut | Command prepared; physical rerun not started | Mac SSH destination pending; this Fedora host has no Chestnut |

**Cancellation executed October 18:** two affected running implementations
(c0172800 and c0172461), seven queued implementations (c0172862, c0173120,
c0173130, c0173133, c0173160, c0172600, c0172662), and their review/queue
consumers were stopped. Eight exact services have MainPID 0 and no surviving
owned processes. c0172450 and c0172462 had already completed implementation;
their outputs and prior review receipts remain historical. They were removed
from the active test list because they inherit the same adapter defect.

Cancellation receipt:
`build/handoffs/cancel-old-pipeline-20261018/manifest.json`.
Retired PCIe-only prototype launch (historical dependency):
`build/fedora-vivado/spare-shared-pcie-c0182301-20261018/launch.json`.
Current producer: `build/fedora-vivado/spare-dual-required-queue-20261018/launch.json`.
Current CH0 regression/verification record:
`build/handoffs/ch0-lfm-current.json`.
The refresh helper now preserves the new priority and removes retired images
and stopped service handles from active lists. Original frozen queues and
all evidence remain on disk. Unrelated KohakuTPU/Vivado and nextpnr work was
not stopped.

The repair name refers to the CH0 defect that caused the LFM regression.
It is independent of model choice. c0182301 has PCIe runtime access and no
USER2/BSCAN bridge; JTAG supports configuration/status only on this image.
c0182800 adds the required USER2 memory/control bridge for local TinyStories
weight upload and inference. Changing host scripts cannot add that bridge.

### Small trained-model test preparation

- Download: `build/models/TinyStories-Llama-15M/`, pinned HF revision
  `6cc2bab8c4a55cce6f7532317af84a94bb340d5e`; receipt
  `build/checks/tinystories-download-20261018/manifest.json`.
- Separate padded checkpoint: `build/models/TinyStories-Llama-15M-tiles128-20261018-v2/`.
  FP32 equivalence receipt: `conversion.json`; maximum logit error 0.0000582,
  all seven sequences and three greedy continuations passed. The original
  safetensors keeps one tied embedding alias; the conversion reconstructs it.
  The failed initial alias assumption is preserved in the original output folder.
- Int8 oracle: `build/checks/tinystories-int8-isa-20261018-v1/manifest.json`.
  Initial image 28,909,056 bytes; eight expected tokens
  `[29892,727,471,263,2217,7826,4257,365]`. Arithmetic geometry, TMEM and IMEM
  match the board; ISA RAM was bounded to 128 MiB. Physical results remain pending.
- Exact c0182800 host helpers:
  `build/handoffs/spare-dual-required-host-c0182800-20261018/host/`.
  The inherited display command was corrected; generated executable sources
  remain byte-identical to the version-2 helpers.
  Packager preparation:
  `build/checks/spare-dual-required-packager-c0182800-20261018/`.
  Their CLI/import gates passed. The first generated guard rejected the fresh
  reset test label `functional` because it inherited `host-reset`; this was a
  host evidence-schema defect, not an FPGA failure. Version 1 is preserved.
  Version 2 changes only that label contract; nine component guard checks pass,
  including corrupted source/model rejection. The actual firmware copier and
  generated calibration binding also passed against the frozen inputs, using
  a zero-image-hash fixture with no bitstream. Receipts:
  `build/checks/spare-shared-dual-host-binding-20261018-original/`,
  `build/checks/spare-shared-dual-host-binding-20261018-v2/`, and
  `build/checks/spare-shared-dual-calibration-binding-20261018-v1/`.
  These are component checks; no combined-host image package is approved yet.
- `tools/run_tinystories_jtag.py` preflight passed under
  `build/checks/tinystories-dual-required-preflight-20261018/`. Execution requires
  the exact reviewed package, an exclusively owned XVC server and successful
  image-bound CH0 calibration. It initializes memory, checks matmul, uploads
  the model via JTAG, compares every initial-image byte and every program before
  execution, then requires exact equality with all eight ISA tokens.
- No weights are committed. No hardware inference result or upload-time estimate
  follows from these offline checks. The original LFM230M/Mac acceptance remains.

### Corrected higher-rate admissions and queue ownership

Four memory cores were regenerated with only the corrected adapter. The complete
SDRAM initialization, startup ROM, non-comment CSR rows and CH0 helper firmware
remain identical to each rate-specific parent. Fresh full-source preparations
passed their complete hash inventory and registered reset functional/skew checks.
New immutable tickets are `05-c0183120.job.json` through `08-c0183160.job.json`
under `build/fedora-vivado/spare-shared-corrections-queue-20261018/admissions/`.
Admission receipt: `build/handoffs/admit-shared-higher-rates-20261018.json`.
Matching complete CDC/saved-collection-aware artifact, Gray and source
collectors were prepared and passed CLI/import gates for all four higher
rates. Their worker is
`opentpu-shared-rate-collectors-20261018.service`; receipts are under
`build/checks/spare-shared-rate-collectors-20261018/`. Exact final disposition
remains owned by the active OpenTPU goal as each collection becomes ready.
These are admitted implementations, not physical rate qualification. The generic
DDR800 controller proof does not qualify the higher-rate electrical interfaces.

The first higher-rate source preparation failed because its parent retains the
host model through `source-check.host_rtl_model`, rather than a root copy.
The failed partial c0183120 preparation is preserved and was never admitted.
`tools/prepare_spare_shared_successor_v2.py` verifies that inherited descriptor
and derives fresh preparations with `-v2-20261018` in their paths. The original
active worker/preparer inputs were not changed.

The queue now uses a runtime systemd `KillMode=process` override so a producer
observation failure cannot implicitly kill a valid in-flight implementation.
No implementation was restarted or stopped. Exact service identity is unchanged.
Receipt: `build/handoffs/shared-queue-child-preservation-20261018.json`.
If the producer becomes terminal, inspect its control group, child PID/command
and implementation receipt before replacing or declaring any child stopped.
Only the eight original affected services remain cancelled; do not resurrect them.

### Shared mixed-width startup successors

Fresh c0182600 and c0182662 preparations are admitted at priorities 9 and 10.
The parent firmware's seven host cases and both archived actual RV32 execution
modes were revalidated. New shared cores contain the identical 4,096 startup
words, with every RTL character outside those words unchanged from the shared
parent. Memory settings, pin constraints, startup helper data, non-comment CSR
rows, lane mapping and ECC configuration remain exact. A CSV comment header
may differ; both complete meaningful rows and decoded register maps are checked.

Preparations: `build/fedora-vivado/spare-shared-mixed-c0182600-20261018/` and
`build/fedora-vivado/spare-shared-mixed-c0182662-20261018/`. Their frozen runners
check every source, unchanged timing gate, registered reset and startup/core/CPU
binding at launch and after implementation. This reuses unchanged firmware
execution evidence; it does not claim a new physical startup observation.

Admission receipt: `build/handoffs/admit-shared-mixed-startup-20261018.json`.
The requested ten-successor set is closed in `admissions.closed.json`; all are
real immutable tickets. The queue remains bounded to two global implementations.
Dynamic clock-transition support is a separate deferred feature, not an admitted
fixed-clock build. Exact mixed-startup collectors passed CLI/import checks and are scheduled under
`opentpu-shared-mixed-collectors-20261018.service`; receipt:
`build/checks/spare-shared-mixed-collectors-20261018/launch.json`. Exact
startup-aware host/package preparation remains pending.

### Current Vortex return and combined SRAM preparation

The other Vortex Codex controller was identified in its own checkout. No native
Vortex hardware programmer was live at that observation. The user explicitly
requested all Vortex work stop when the priority combined-interface build ends.
The watcher `opentpu-priority-vortex-return-c0182800-v3-20261018.service`
(invocation `542755d8d5864b4da5aa6438aef38626`) waits on the exact new producer.
It stops the Vortex controller's scheduling, allows observed native or wrapper
programming operations to finish, then ends Vortex-owned work and releases the
hardware. It configures no image and writes no flash. Its request, launch and
live receipt are in
`../vortex/build_ypcb_vivado32/openTPU-return-20261018/` (live `run-v3/`).
Inspect any ambiguous remaining owner before a new SRAM load.

The old c0182301 SRAM/flash entry points now reject all execution before touching
hardware; their original sources and negative-control receipts are preserved
under `build/handoffs/retire-pcie-only-c0182301-20261018/`. New
`tools/program_spare_c0182800_sram.py` requires the reviewed combined-interface
package, its exact packaged host metadata and an explicit shared JTAG lease.
Its CLI/import preparation passed. Actual preflight/programming still awaits the
exact c0182800 final review/package; no SRAM pass is implied by tool preparation.

### Priority memory reservation (temporary secondary-build pause)

The host had about 4 GiB available and roughly 19 GiB swap in use while final
priority timing cleanup and the faster synthesis overlapped. The resource owner
`opentpu-priority-review-resources-c0182800-20261018.service` (invocation
`025e72aaefae41e2a813fc9dc6015619`) pauses secondary implementation processes
inside the **new** producer's control group, excluding that producer observer.
c0182800 stays in the original control group and is not paused. Its adopted
exit status, collector start and Vortex-return trigger can still advance.

State/PID identities: `build/checks/priority-review-resources-c0182800-20261018/run/manifest.json`.
Frozen sources/checkpoints remain intact; no implementation was restarted.
If another secondary admission starts after c0182800 finishes, it is also held
until the priority review/package work is complete. This is a resource pause,
not a goal pause or a successful build being described as stopped.

**Required resume step:** after the priority's exact offline review/package
finishes, the active goal writes
`build/checks/priority-review-resources-c0182800-20261018/release.json` with
`{"build_id":"c0182800","release_secondary_implementations":true}` and the
actual review receipt/outcome. The resource owner validates saved PID start
identities and resumes its paused processes. Do not leave this hold behind
once priority review no longer needs the memory. If a new correction needs the
reservation, record that explicit decision and current owner instead.

## 3. Hardware identity and where the card is

**Current connection: local JTAG only**, explicitly confirmed by the user.
DLC10 initialization and IDCODE `0x23751093` passed. The authorized Vortex
SRAM configuration/status check passed (`INIT=1 DONE=1`), then released JTAG;
no GPU workload or DDR training was run. Vortex remains in SRAM, while the
permanent OpenTPU c0172300 image is unchanged. Results are in
`../vortex/build_ypcb_vivado32/hardware-check-20261018/`. Switch to the reviewed
priority OpenTPU image as soon as it is ready. No local PCIe endpoint or Mac
remote session is available. c0182301 is PCIe-only; local JTAG inference uses
the corrected combined-access c0182800 successor.

Last locally observed permanent image:

| Field | Value |
| --- | --- |
| Board / FPGA | YPCB-00338 / XC7K480T FFG1156 -2 |
| Physical JTAG IDCODE | `0x23751093` |
| Build ID | `0xc0172300` |
| Bitstream | `bitstreams/spare-pcie-4gb-pipeline-ddr800/otpu.bit` |
| Bitstream SHA256 | `669a7382ff9f9f1391b163ff0fcd5971ded8e378d7668c737c1692819a1323aa` |
| Compute / DDR | 100 MHz / DDR800: 400 MHz DDR clock, 800 MT/s |
| Capacity | 4 GiB total, two 2 GiB channels |
| CH0 logical byte groups -> physical groups | `[0,1,2,3,4,5,8,7]`; physical lane 6 bypassed |
| ECC | CH0 off; CH1 on |
| CH0 adapter | Two raw native read ports, 32 read credits per port; writes and partial-write RMW remain exclusive |
| Host access | PCIe via Chestnut/XDMA; **no JTAG memory interface** |
| Startup | CH1 automatic; separate exact eight-lane CH0 calibration helper |
| Supply most recently reported | 12 V / 5 A, replacing earlier 12 V / 2 A |

SRAM load verified INIT/DONE and IDCODE. Permanent program/verify, separate
verification and JTAG-triggered flash boot passed on 17 October at
14:39:39 UTC / 22:39 HKT. No old-flash backup was made, per the user.
No permanent write was performed after that operation.

Programming receipt:
[`build/fedora-vivado/spare-pipeline-c0172300-flash-20261017/manifest.json`](build/fedora-vivado/spare-pipeline-c0172300-flash-20261017/manifest.json).
Move-to-Mac record:
[`build/handoffs/c0172300-ready-for-mac-20261017.json`](build/handoffs/c0172300-ready-for-mac-20261017.json).

The flash receipt is not a subsequent live interrogation of the Mac card.
Get the Mac identity receipt to bind the new failure to the running image.
This exact live identity is expected by the c0172300 profile:

```text
R_ID           = ID_OTPU
R_VERSION      = (128 << 16) | (4 << 8) | 8
R_REGMAP       = 3
R_CORE_KHZ     = 100000
R_BUILD_ID     = 0xc0172300
R_DDR_MTS      = 800
R_ACT_ROWS     = 4
register 0x5c  = 0x10000203
register 0x60  = 0x78543210
register 0x64  = 2
required caps  = CAP_HOSTCAL | CAP_DDR | CAP_ACT
```

## 4. Evidence so far: what is established, and what is not

### Earlier full-capacity spare-lane operation

The original c0172080 spare-lane PCIe image operated full 4 GiB on the Mac.
The copied benchmark evidence identifies Qwen3.5-2B, complete zero
initialization/readback on both channels, exact matmul and eight generated
tokens matching the ISA reference. The model occupied 94.16% of 4 GiB.

Useful evidence:

- `docs/data/spare_pcie_benchmark_20261017.json`
- `docs/data/spare_pcie_mac_evidence_review_20261017.json`
- `docs/data/spare_pcie_mac_qwen2b_reported_20261017.json` is the **earlier,
  less complete user report**; prefer the later benchmark/evidence review for
  the stronger binding. The original Mac run folder was not present here.

On Fedora, spare RAM-only c0172070 also passed bounded native/partial-write
and full-range tests on the user-reported 12 V / 5 A supply:

- Native sequence: 1,160 responses, 560 partial writes, zero bad responses/bytes.
- Two PRNG generations across both channels: 4 GiB written and 4 GiB checked
  per channel, zero errors. Recorded die temperature 48.85–49.83 C.
- Another bounded repeat with retained calibration passed.
- A 60-second refresh-on retention interval followed by full 4 GiB readback
  without rewriting/recalibrating passed; recorded 48.85–49.59 C.
- Evidence under `build/hardware-test/spare-12v5a-repeat-20261017T084954Z/`,
  `spare-12v5a-repeat2-20261017/` and
  `spare-12v5a-prng-retention-20261017/`.

These results justify pursuing the spare-lane path. They do not transfer
qualification to the new pipelined adapter, different implementation or clocks.
The latest c0172300 program mismatch is a real new obstacle to qualify, even
though capacity and an earlier working image were already demonstrated.

### Why pipelining was added

The old adapter accepted one CH0 operation, waited for command/data/response,
then returned to IDLE before accepting another. Both user ports shared that
single FSM; the second raw port was disabled. Each accelerator 128-byte chunk
uses a 64-byte half from each channel, so CH0 limited chunk completion.

The reported device bandwidth dropped from about 6.10 GB/s on the earlier
CH1-only run to about 0.888 GB/s on the spare dual-channel run, with traffic
per token within 0.053% and roughly 6.88x as many device decode cycles.
Different KV/resident-decode settings mean that was not a fully controlled
bitstream A/B. Separate host/USB overhead was reported at 1.55 s/token.

The source finding is recorded in
`docs/data/spare_pcie_serial_read_bottleneck_20261017.json`.
The new source is `tools/litedram/spare_native_pipeline.py` and its protocol
model evidence is under
`build/checks/spare-native-pipeline-v2-20261017/manifest.json`.
Passing that model is not physical proof that c0172300 uploads large LFM
programs correctly.

DDR800 has a theoretical 6.4 GB/s data payload per 64-bit channel, 12.8 GB/s
aggregate. Actual throughput depends on concurrency, adapter/controller
efficiency, compute, access mix and host overhead. **Two channels do not
guarantee twice the observed LLM bandwidth.** A matched device-counter test
remains pending after correctness is restored.

### Original lane-6 investigation, retained for later

The original configuration exhibited CH0 lane-6 errors, including returned
data matching a neighboring/previously accessed tag. Equal tags could hide
that symptom. The sequence/address/write history was not fully disentangled,
and after-PHY-alignment/pre-ECC capture did not isolate electrical sampling
from writes or alignment. MIG and LiteDRAM failures were not proven to be
identical mechanisms.

Upstream per-bit read-framing work and lane-bypass precedents were relevant
research leads, not proof of the exact cause. A full independent audit of all
remote branches was not established by the pasted research. Local branch/code
review artifacts are under `docs/ddr_upstream_branch_review.md` and
`docs/data/ddr-upstream-branches-20261016.json`; read their scope limitations.

The bypass recovers capacity while sacrificing CH0's existing ECC. It does
not establish repaired lane 6 or restoration of 4 GiB with ECC on both channels.
The latest pipelined-image mismatch must not be relabeled as proof that the
original physical lane is bad: that lane is currently bypassed.

### Power and temperature

- Earlier tests used a user-reported 12 V / 2 A supply only; its nameplate
  limit is 24 W. Later tests used 12 V / 5 A, nominally 60 W.
- Actual card-input voltage/current and DRAM rails were not measured here.
  No controlled supply A/B established that power caused or cured the fault.
- User has a multimeter; pad identification and probing were deferred to later.
- A 42.8 C read-only FPGA temperature was an earlier observation, not current
  Mac telemetry. RAM-only and sibling-project temperatures are historical.
- Low FPGA die temperature alone does not establish DRAM timing or power margin.

## 5. First resumed investigation: CH0 program mismatch

This is a proposed concrete resume procedure. **It was not executed while
writing this handoff.** It is targeted to the latest failure and is not a new
request to repeat a full-capacity soak.

### 5.1 Collect and preserve the exact Mac artifacts

Obtain, as ordinary files rather than an archive:

1. The actual run directory and command/environment, including:
   - `$SPARE_OUT/identity/manifest.json`
   - `$SPARE_OUT/calibration/manifest.json`
   - `$SPARE_OUT/lfm/manifest.json`
   - terminal traceback and all saved error/status/counter registers.
2. Expected compiled program words and raw program readback, with:
   - logical program byte address, unpadded/padded lengths and word dtype;
   - expected/readback hashes and first mismatch offsets/values;
   - physical CH0/CH1 offsets or the exact mapping calculation;
   - compiler/image configuration, source revision and model checkpoint ID.
3. Any trace/failing PC, instruction word, error/status register, LOAD state,
   instruction counts and read/write counters from the failed execution.
4. On Mac, `git rev-parse HEAD`, `git status --short --branch`, Python executable
   and actual imported paths for the compiler, board and Chestnut modules.
   Do not assume the active virtual environment imports the intended checkout.

Do not power-cycle, recalibrate, overwrite the program area or run bandwidth
before preserving useful failure evidence. The documented fresh-run workflow
requires a fresh configuration before calibration; that is separate from
first retrieving the already saved state.

The user tried an offline recompile that failed with
`opentpu.compiler.CompileError: TMEM exhausted`. Another comparison attempt
failed with `ValueError: cannot reshape array of size 10968 into shape (16)`.
A later comparison reported the 3,161 CH0-only differences. These intermediate
errors are not evidence of a successful faithful recompile or an instruction
count. Reconstruct the exact original compiler/device configuration and save
the final successful comparison command before drawing further conclusions.

### 5.2 Verify mapping and byte representation first

Relevant source entry points:

| Component | Path / entry point |
| --- | --- |
| Runtime identity/guards | `opentpu/host/spare_c0172300.py` |
| Chestnut transfer | `opentpu/host/chestnut.py`, especially `_transfer` |
| Logical channel mapping | `opentpu/host/board.py`: `swapped`, `hash_swap`, `split`, `join` |
| Host upload/readback | `Board.write`, `Board.read` |
| DRAM -> IMEM loading | `Board.load_program` |
| LLM program assembly/execution | `BoardBackend.prepare`, `BoardBackend.start`; `opentpu/llm/qwen3.py` |
| Failure reporting | Board run/counter/error handling in `board.py` |
| c0172300 runner | `tools/run_lfm_spare_c0172300.py` |
| New adapter | `tools/litedram/spare_native_pipeline.py` and the exact frozen/generated image sources |

The normal map interleaves 64-byte channel beats inside 128-byte logical
chunks. `split` requires aligned logical ranges and uses channel offset
`logical_address // 2`. CHASH can swap the two halves based on chunk parity;
compare using the **actual Board CHASH setting**, not an assumed even/odd
word partition. Do not apply the swap twice. Direct physical transport
addresses are not logical Board addresses.

`Board.write` widens unaligned writes and reads the edge chunks before
merging; program tails may exercise that path. `Board.load_program` writes
the little-endian uint32 program to DRAM, sets program address/count and
requests IMEM loading. This gives distinct boundaries to compare.

Keep expected bytes, padding, lengths, endianness and hashes explicit. A bad
comparison shape or channel mapping can manufacture an apparent mismatch;
conversely, uniform zero initialization can conceal real displacement.

### 5.3 Use a small discriminating reproducer

After preserving receipts and when authorized work is resumed:

- Write a distinctive sequence to a disposable, initialized program-sized
  region. Every beat should identify its channel/offset/generation.
- Test physical CH0 and CH1 separately, then the equivalent logical
  interleaved upload. Start with aligned full chunks, then the actual failing
  length/tail and partial-write edges.
- Read the same data repeatedly without rewriting to look for variable or
  stale readback. Reverse write order or change the source data separately.
- Compare small versus large transfers and serialized versus pipelined
  transactions, with unchanged clocks/calibration and exact byte counts.
- Locate first/last mismatches and periodicity relative to 64/128-byte beats,
  native credits/FIFO depth, transfer descriptors, host chunk boundaries and
  the final partial chunk. Repeated values should be matched against earlier
  beats to identify potential substitution, not just counted as wrong.
- Keep only one exclusive card client and preserve accepted request/response
  order. Do not clear errors or silently retry until evidence is captured.

**A same-path host write/read comparison cannot by itself separate write
corruption from read corruption.** Localize with an independent observer:
device-side comparison/checksum, a trusted alternate path, or instrumented
native read/write boundaries. A paired write/read can also conceal symmetric
errors, so use identifiable address-sensitive data and independent evidence.

c0172300 lacks JTAG memory access. c0172800 could supply another observation
path only after its own review and hardware qualification; it is not yet
available as a trusted oracle. Fedora currently has no direct access to the
Mac's Chestnut transport. Do not pretend this local handoff performed such
cross-checks.

Once DRAM program bytes are trustworthy, distinguish correct DRAM readback
from correct IMEM contents/loading, then inspect the first decoded instruction,
PC/opcode and capabilities. A clean instruction stream with an unsupported
opcode would direct attention toward compiler/ISA configuration. Current
evidence does not establish that branch because readback already differs.

### 5.4 Acceptance for a fix

The exact previously failing program must upload/read/execute correctly;
matmul must remain exact; LFM must produce reference-matching tokens. Follow
with the matched device-bandwidth check. Bind evidence to image identity,
source/runtime versions and calibration state. A hardware RTL change needs
a new identity, fresh implementation and exact review; a host-only change
needs a scoped small-file commit and Mac rerun. Do not preselect a rebuild
before localizing which component is wrong.

## 6. c0172300 Mac workflow and Git status

### Branch and published commits

Current branch: **`ypcb/dual-channel-4gb`**.
It was renamed from `ypcb/ch1-bringup-local` as this became full 4 GiB work.

Current local HEAD and local origin-tracking tip:
`b3cfcb24a64516c247b7ea9d5eedb3764707b99c`.
An earlier direct remote check confirmed publication; this handoff did not
fetch or query the remote again. User performed the push, not the agent.

| Commit | Purpose |
| --- | --- |
| `32c76020` | Earlier full 4 GiB spare-lane image / Mac LFM bring-up |
| `0e33cb9c` | Mac full-capacity benchmark and serialized CH0 bandwidth notes |
| `9b899a9b148a652bcfc5f63ba780bdcbf35b7481` | Small c0172300 runtime/host helpers and Git handoff rules |
| `b3cfcb24a64516c247b7ea9d5eedb3764707b99c` | New branch name and Mac checkout instructions |

Published Mac checkout commands:

```bash
git fetch origin
git switch ypcb/dual-channel-4gb
git pull --ff-only
```

If local edits block a pull, inspect and preserve them before merging. There
was an earlier Mac/Fedora README conflict. Do not discard local notes or
blindly stash the entire dirty checkout.

### Runtime files already in Git

The c0172300 delivery contains 20 small files, 125,824 bytes total at its
commit, largest about 17 KiB. No bitstream/netlist/Vivado installation or
separate `~/ypcb` checkout is required on the Mac for the already-flashed card.

```text
docs/mac_c0172300.md
opentpu/host/spare_c0172300.py
tools/calibrate_spare_c0172300.py
tools/export_spare_c0172300_runtime.py
tools/mac_spare_c0172300.sh
tools/run_bandwidth_spare_c0172300.py
tools/run_dma_spare_c0172300.py
tools/run_lfm_spare_c0172300.py
tools/spare_runtime_c0172300.py
runtime/c0172300/runtime.json
runtime/c0172300/reviewed-image.json
runtime/c0172300/core/csr.csv
runtime/c0172300/core/sdram_init.py
runtime/c0172300/core/sdram_init_ch0.py
runtime/c0172300/core/otpu_litedram_mem.init
runtime/c0172300/calibration/selfcal.bin
runtime/c0172300/calibration/bundle.json
runtime/c0172300/calibration/host-model-review.json
runtime/c0172300/calibration/pipeline-binding.json
AGENTS.md  # committed version predates subsequent local rule additions
```

Runtime manifest digest:
`4decfea1b1e0e4ba607b9f248b5621dc8c7f4bfdc928143fbc7beef3856f35d7`.
Original reviewed manifest digest:
`0353630aa96b1de734f9712af0140d6c7a2faeda809add9f9cd6aaa0b46be624`.
CH0 calibration binary digest:
`fe4fc9caba63e8b97ac1ce978dd0b67d9c532ce154f57a3582fb6228c4686e8e`.

The runtime path validates pinned small files and original review metadata.
It **does not rehash an absent bitstream/netlist or attest current flash
contents**. `core_file_digest('otpu_litedram.v')` in runtime-only mode returns
the reviewed metadata hash, explicitly not a fresh local netlist hash.
Do not weaken these guards to accept other image IDs.

Shared compiler/host sources matched the frozen host tree at preparation.
A clean checkout containing tracked Python sources plus the selected small
files passed runtime/calibration preflight and bandwidth CLI imports without
opening hardware. Those historical checks are preparation evidence, not a
resolution of the new Mac failure.

### Existing launch command, for a fresh run after debugging is resumed

Full instructions: [`docs/mac_c0172300.md`](docs/mac_c0172300.md).

```bash
export SPARE_PYTHON=/path/to/working/python
export SPARE_MODEL=/path/to/LFM2/checkpoint
export SPARE_OUT=build/mac-c0172300-lfm-new
bash tools/mac_spare_c0172300.sh preflight
bash tools/mac_spare_c0172300.sh lfm
```

`lfm` performs identity, exact CH0 calibration, full memory initialization,
matmul and LFM/ISA comparison. It does not add a standalone RAM soak.
Use a fresh output directory and the checkpoint-compatible Python environment
(NumPy, PyTorch, Transformers, safetensors, libusb). Recent Mac output used
`build/chestnut-lfm/venv/bin/python`; do not assume it exists on Fedora.

The calibration helper expects a fresh configuration with no prior native
traffic. Save the failed state before power-cycling for another fresh attempt.
Do not automatically recalibrate on every failure. The wrapper has longer
legacy `memory`/`full` stages, but the user did not request more such soaks.

After a successful correctness run, in the same configuration:

```bash
bash tools/mac_spare_c0172300.sh bandwidth
```

It runs three 64 MiB native-read streams, checks instruction/traffic counts
and final 16 KiB payload, and separates device time from USB/host call time.
It overwrites program/output memory, so do not run it before preserving the
current failure and reload the model afterward. It is not a full-range
payload proof or guaranteed 2x speedup.

### Local work that has not been published

This handoff, the latest `AGENTS.md` additions, runtime sweep preparation,
reset-gate/final-disposition tools, and many local documentation/source
changes are uncommitted. Do not tell the Mac to pull them until a separately
authorized scoped commit and push actually happen.

Git status was captured before this handoff under
`build/handoffs/session-handoff-20261017/git-status-before.txt`, with staged
names and unstaged diff statistics alongside. The index already contained
older staged generated artifacts, including a `.bit` and netlist files.
**Do not commit the existing index wholesale.** This handoff did not stage,
commit, unstage or push anything. Prior scoped commits used an isolated
index; preserve unrelated stage entries if following that pattern again.

## 7. Historical background jobs and ownership (superseded by section 2)

At the 15:47 UTC snapshot these eight services were **active/running**.
Main PIDs were checked with `/proc` and exact command lines saved. A review
service being active can mean it is waiting; it does not mean its image is
approved or its collector is currently consuming CPU.

| Service name (all end in `.service`) | Invocation ID | Purpose |
| --- | --- | --- |
| `opentpu-spare4gb-dual-host-parallel-20261017` | `a72edb62699645a08b36773f9d70a44c` | Original combined-host queue; c0172461 still implementing |
| `opentpu-spare4gb-reset-baseline-20261017` | `027acf41ed65417584dee778d4060170` | Registered-reset baseline c0172800 implementation |
| `opentpu-spare4gb-after-reset-baseline-20261017` | `7a79e6ab9252419ca809356f7551ce55` | Waits predecessor queues, then c0172862 and six experiments |
| `opentpu-spare4gb-dual-host-review-saved-skew-20261017` | `f499fb3d11ee4fd99307df517cd05a42` | Exact artifact/CDC/Gray/source collection |
| `opentpu-spare4gb-registered-reset-review-baseline-first-20261017` | `ce36d6a9808c4f60a2c32539db8fe8bc` | Corrected baseline evidence collection |
| `opentpu-spare4gb-registered-faster-review-baseline-first-20261017` | `c6d112cd484c4acc8cb3d02914efe79d` | Corrected faster evidence collection |
| `opentpu-spare4gb-overclock-review-baseline-first-20261017` | `9a01b64bf9d74e55acf73e514183fa6d` | Higher-DDR review queue |
| `opentpu-spare4gb-mixed-startup-review-baseline-first-20261017` | `858466afa3364a9f8abc57e16b88d32d` | Mixed-width automatic-startup review queue |

**Failed, not running:**
`opentpu-spare4gb-final-dispositions-20261017.service`, invocation
`46e000d04910439891c9a1724fe345f6`.
Its c0172450 failure is detailed in section 8. c0172461 remains waiting in
that stopped worker's manifest and will need a corrected/replacement worker.

**Terminal preparation/review services:** c0172462 final review, runtime
memory-core generation and runtime clock-IP preparation were inactive/dead
at the snapshot. Their receipts, not absence of a service, establish their
terminal result. Do not restart completed jobs simply because the unit is
no longer active.

Read-only monitoring commands for a resumed session:

```bash
systemctl --user show opentpu-spare4gb-dual-host-parallel-20261017.service \
  -p ActiveState -p SubState -p MainPID -p InvocationID -p Result
systemctl --user show opentpu-spare4gb-reset-baseline-20261017.service \
  -p ActiveState -p SubState -p MainPID -p InvocationID -p Result
systemctl --user show opentpu-spare4gb-after-reset-baseline-20261017.service \
  -p ActiveState -p SubState -p MainPID -p InvocationID -p Result
journalctl --user -u opentpu-spare4gb-final-dispositions-20261017.service \
  -n 50 --no-pager
```

Queue directories, each with frozen schedule and current manifest:

```text
build/fedora-vivado/spare-dual-host-parallel-20261017/
build/fedora-vivado/spare-reset-baseline-20261017/
build/fedora-vivado/spare-after-reset-baseline-20261017/
build/checks/saved-skew-review-stream-dual-host-20261017/
build/checks/final-disposition-workers-20261017/
```

At the snapshot the after-baseline queue was waiting for the original queue;
c0172862 was not itself running. Do not describe it as resumed routing.
Any future scheduling change must preserve frozen inputs, service invocation
ownership and the current queue's accounting; do not launch duplicates.

Resource snapshot: 36 GiB RAM total, approximately 6.6 GiB available, 14 GiB
swap used out of 23 GiB. This changes over time; use `free -h` before admitting
more work. Other-session KohakuTPU Vivado and a long-running OpenTPU nextpnr
routing job were also live. **Do not stop or modify those unrelated jobs.**
Older routing snapshots can be valuable measurement evidence, not disposable
cache. A previous user assertion of 20 GiB free is not current telemetry.

## 8. Reset hazard and exact review state

### The defect

The original combined-host reset logic asynchronously crossed a decoded
multi-bit reset countdown. Source-bit skew can glitch the decode during
counter transitions. A synchronizer after a combinational decode does not
make that source glitch impossible. The corrected design registers the
source reset before crossing into the receiving domains.

The counterexample used modeled 500 ps source-bit skew; it is **not a
measured physical reset glitch on this card**. This defect is in the new
combined-host design, not an automatic revocation of c0172300's PCIe-only
offline review, and not proof of the new Mac corruption's cause.

Evidence:

- `build/checks/spare-host-reset-cdc-counterexample-v2-20261017/manifest.json`
- `build/checks/spare-host-reset-disposition-20261017/manifest.json`
- Registered-reset preparations via `tools/prepare_spare_registered_reset.py`.

### c0172462: terminal rejection

Receipt:
`build/checks/c0172462-final-review-20261017/manifest.json`.

```text
status: FINAL_REVIEW_REJECTED_SHARED_HOST_RESET_SOURCE_CORRECTION_REQUIRED
bitstream SHA256:
ee090fd32c4797f3ff73da931e78c6411eb74d95982f70201091d944095ed225
setup slack: +0.032 ns
hold slack:  +0.013 ns
minimum checked Gray skew slack: +3.109 ns
fully routed nets: 334686 / 334686
raw non-info CDC rows: 1995, summary/detail counts reconciled
decisive rejecting reset crossings: 4 CDC-10 rows
```

The exact routed fanin included all seven countdown bits, lock and
configuration reset. Actual/frozen reset source matched the prior hazardous
source hash:
`217e8956f060890a8543dbdaa16d198397fa763d5e85117619222108844b3198`.
The other 1,991 CDC rows were **not blanket-approved**. Rejection is a valid
terminal outcome; passing numerical timing does not waive this defect.

Grouped inventory is saved at
`build/checks/c0172462-final-review-20261017/inventory-groups.json`.
Avoid dumping thousands of bit-level rows into the conversation.

### c0172450: new final-review blocker discovered during this handoff

The build completed at **15:13:08 UTC**. Its exact bitstream SHA256 is
`c1592fdf83dbbab5a75e8d4855b83c6f98643a414b2431e4c6437f7082f5affe`.
The automatic final review tried at **15:34:24 UTC** and failed closed:

```text
build/checks/c0172450-final-review-20261017/manifest.json
status: FINAL_REVIEW_INCOMPLETE
error: ValueError('Exact routed reset crossings differ from the reviewed hazardous topology')

build/checks/final-disposition-workers-20261017/run/manifest.json
status: FINAL_DISPOSITION_WORKER_INCOMPLETE
error: ValueError('Reset gate needs further review: c0172450')
```

The source design remains suspect, but the checker did **not** prove that
this routed topology equals the already reviewed c0172462 case. Do not
misreport this as a terminal approved or rejected disposition. Inspect the
exact raw report and routed fanin, classify the difference, and adapt a
fresh review preparation if justified. Preserve the failed receipts and
frozen tools. Do not merely relax the expected row count/topology assertion.

Evidence folder:
`build/checks/saved-skew-c0172450-20261017/review/`, containing `artifacts/`,
`cdc/`, `gray/` and `source-comparison.json`.

The failed worker's frozen schedule contains the exact commands for both
c0172450 and c0172461:
`build/checks/final-disposition-workers-20261017/schedule.json`.
c0172461 has no final-review receipt yet. After fixing the review workflow,
use a fresh worker/output identity, update canonical handles, and ensure the
ready c0172461 does not remain indefinitely unprocessed.

### Review/tool pitfalls already encountered

- The old CDC parser missed rows numbered 100/1000 and above. The current
  parser is `tools/cdc_report_rows.py`. Reconcile every detailed Critical
  and Warning row with the report summary; fail closed on omissions.
- Saved Vivado constraints use `_xlnx_shared_iN` aliases. Resolve aliases in
  scope using the saved-constraint reader; do not reject valid syntax as an
  implementation failure or execute arbitrary report text.
- Collection completion is not a positive final CDC disposition. Unknown
  mailbox, reset, FIFO, SmartConnect and management crossings still need
  actual technical treatment.
- A parser-only fix must not restart a completed implementation. A real
  source defect requires a corrected source/image identity and new build.
- Frozen tools already hashed by live workers are immutable. Put fixes into
  fresh output/preparation directories and record the supersession.

## 9. Artifact and source map for fixed-clock builds

| Image | Frozen preparation / primary local artifact root |
| --- | --- |
| c0172300 | `build/fedora-vivado/spare-full-pcie-pipeline-20261017/`; package `bitstreams/spare-pcie-4gb-pipeline-ddr800/` |
| c0172462 | `build/fedora-vivado/spare-dual-host-c0172462-v3-20261017/` |
| c0172450 | `build/fedora-vivado/spare-dual-host-c0172450-v3-20261017/` |
| c0172461 | `build/fedora-vivado/spare-dual-host-c0172461-v3-20261017/` |
| c0172800 | `build/fedora-vivado/spare-dual-host-c0172800-registered-reset-v1-20261017/` |
| c0172862 | Follow the frozen after-baseline schedule; exact registered-reset preparation is already recorded there |
| c0173120 / 3130 / 3133 / 3160 | `build/fedora-vivado/spare-dual-host-c017<id>-ddr<rate>-20261017/`; use queue schedule for exact spelling |

Within a fixed preparation the implementation writes beneath
`implementation/`; the bitstream is typically `implementation/project/otpu.bit`.
Do not treat old `.bit` existence as terminal review success. Follow the
manifest's exact path and checksum.

For c0172800 and c0172862, exact host/review/packager contracts are recorded
in `registered_reset_exact_preparations` of
`build/handoffs/lane6-plan-current.json`. Representative paths:

```text
build/handoffs/spare-registered-host-c0172800-v1-20261017/host/host-preparation.json
build/checks/saved-skew-c0172800-20261017/review/manifest.json
build/checks/spare-registered-complete-cdc-c0172800-20261017/packager/manifest.json
```

The same pattern exists for c0172862. Prepared contracts are not created
packages or successful hardware runs. Read their manifests and model receipts.

Main source entry points for future fresh builds:

```text
tools/litedram/spare_native_pipeline.py       CH0 pipelined native adapter
tools/check_spare_native_pipeline.py         adapter protocol model
tools/dual_host_source.py                    combined JTAG/PCIe snapshot changes
tools/prepare_spare_dual_pcie.py             combined fixed-clock preparation
tools/prepare_spare_registered_reset.py      registered-reset successors
tools/run_spare_dual_snapshot.py             implement a frozen preparation
tools/prepare_spare_saved_skew_review.py     exact saved-constraint review preparation
tools/run_spare_dual_reviews.py              evidence collector orchestration
tools/review_spare_dual_reset_gate.py         exact reset final disposition
tools/run_spare_final_dispositions.py        waiting/final-disposition worker
tools/run_spare_dual_integration.py          bounded transfer/mask/matmul check
tools/run_spare_dual_bandwidth.py            exact-image bandwidth helper
tools/prepare_spare_overclock.py             higher-DDR frozen experiments
tools/prepare_spare_mixed_selfcal.py          mixed-width calibration firmware
tools/prepare_spare_mixed_dual.py             mixed-startup full image preparation
```

Documentation/build recipes:

- `docs/ddr_spare_pipeline.md`
- `docs/ddr_spare_dual_host.md`
- `docs/ddr_spare_speed_builds.md`
- `docs/ddr_spare_native_probe.md`
- `docs/ddr_lane6_debug_plan.md`
- `docs/vivado_bitstream_guide.md`

**Known stale documentation:** `docs/ddr_spare_pipeline.md` still contains
old archive handoff suggestions; replace those with the small-file Git
workflow when documentation work resumes. Several plan tables still say
c0172800 is synthesizing, c0172450 is routing, c0172462 is running, or the
permanent image is c0172080. This handoff and live receipts supersede those
status claims. Do not copy their retired c0172400 examples into a new active
build without applying the selected registered-reset correction and identity.

The higher-DDR and mixed-startup snapshots also inherit the original reset
design in several cases. A new clock or startup feature does not remove that
known issue. Their exact final review must address it; use new corrected
identities where a source correction is required, without mutating active
frozen trees.

## 10. Runtime compute + DDR clock sweep: actual preparation

This is the user's request for **one full image**, not a list of separate
fixed-clock images. Initial requested compute modes are 100 and
148.837209 MHz; initial DDR modes are 800 and 1066.667 MT/s. Preserve full
4 GiB, CH0 spare mapping/no ECC, CH1 ECC, pipelined reads, registered reset
and PCIe plus JTAG access.

The first experimental DDR transition can be destructive: stop work, drain,
change/relock clocks, reinitialize/recalibrate, initialize ECC and reload
the model. Live model preservation was not promised.

### Completed source-level components

| Component | Source | Actual saved result |
| --- | --- | --- |
| Shared conservative timing envelope | `tools/litedram/runtime_timing.py` | `build/checks/runtime-ddr-timing-envelope-20261017/manifest.json` |
| Corrected external-clock full memory core | `tools/litedram/runtime_core_parts.py`, `tools/prepare_spare_runtime_shared_core.py` | `build/fedora-vivado/spare-runtime-shared-memory-core-20261018-v1/manifest.json` |
| Actual calibration hold logic | `tools/check_spare_runtime_calibration_hold.py` | `build/checks/runtime-shared-calibration-hold-20261018-v1/manifest.json`; six cases pass |
| Always-on AXI protocol and transition sequencer | `rtl/boards/ypcb-00338/otpu_runtime_clock_ctrl.sv` | `build/checks/runtime-clock-control-component-20261018-v2/manifest.json`; lint and 21 RTL reset/abort/recovery cases pass; external engines/top not integrated |
| AXI clock configuration engine | `rtl/boards/ypcb-00338/otpu_runtime_clock_config.sv` | `build/checks/runtime-clock-configuration-component-20261018-v2/manifest.json`; lint and 13 modeled protocol cases pass; vendor-IP integration pending |
| Connected control/configuration subsystem | `rtl/boards/ypcb-00338/otpu_runtime_clock_manager.sv` | `build/checks/runtime-clock-manager-connected-20261018-v1/manifest.json`; lint and 13 combined cases pass; vendor-IP/calibration/drain boundaries modeled |
| Dynamic compute/memory clock IP | `tools/prepare_spare_runtime_clocks.py` | `build/fedora-vivado/spare-runtime-clock-ip-20261017/manifest.json` |

The current request/audit records are:

```text
build/handoffs/runtime-clock-sweep-request-20261017.json
build/handoffs/runtime-clock-sweep-design-audit-20261017.json
docs/runtime_clock_sweep.md
```

Their deliberately separate flags are:

```text
runtime_timing_prepared               = true
runtime_memory_core_hdl_prepared      = true
runtime_calibration_hold_prepared     = true
clock_ip_prepared                    = true
full_runtime_image_prepared           = false
hdl_prepared (complete image)         = false
vivado_enqueued                       = false
```

Do not misreport the last three as true because component HDL was generated.

### Timing envelope details

Derived from the pinned LiteDRAM module and current custom PHY:

| Setting | DDR800 | DDR1066.667 |
| --- | --- | --- |
| Controller/sys clock | 100 MHz | 133.333333 MHz |
| DRAM CL / CWL | 6 / 5 | 7 / 6 |
| Structural read / write latency | 8 / 1 sys cycles | 8 / 1 sys cycles |
| Controller CWL cycle count | 2 | 2 |
| Read / write phase CSR | 3 / 3 | 2 / 2 |
| Half-sys8x tap estimate | 8 | 6 |

Common minimum-cycle counters:
`tRP=3, tRCD=3, tWR=3, tWTR=2, tRFC=23, tFAW=7, tCCD=1,
tRRD=2, tRC=8, tRAS=6, tZQCS=16`.
Refresh is a **maximum interval**, so `tREFI=780` is bounded at the slow
100 MHz mode: 7.8 us slow / 5.85 us fast. ZQCS request timing also uses
the slowest 100 MHz reference. This is source/numerical evidence, not a
physical timing-margin or transition proof.

### Generated memory core

The corrected shared-response generation completed with status:
`EXPERIMENTAL_FULL_RUNTIME_MEMORY_CORE_GENERATED_TOP_AND_IMPLEMENTATION_PENDING`.
It preserves both complete channels, full capacity, adapter/CSR map and
64/72-bit physical buses. It adds four top-level inputs:

```text
runtime_sys_clk
runtime_mem_reset
runtime_clock_ready
runtime_calibration_hold
```

`ExternalSysCRG` accepts external sys/reset/readiness and retains an independent
200 MHz IDELAY PLL from the board's 50 MHz source. The calibration hold is
synchronized with two stages initialized held. A private copied `calcpu.py`
uses the external hold along with the existing CSR hold, allowing an accepted
access to finish before holding, so fixed-rate boot firmware cannot start
against the wrong mode during transition.

The generated initial mode is DDR1066 with embedded CH1 firmware c0172160;
10,232 bytes compiled inside the 16 KiB limit. This is not automatic
mixed-width startup or a complete runtime transition implementation.
The earlier no-hold v1 and hold-enabled v2 generations are preserved historical
evidence. Both use the retired independent-response adapter and must not be
selected for a new image. The corrected October 18 component supersedes them.

### Generated clock IP

Installed Vivado Clocking Wizard 6.0 source generation completed, with:

- `runtime_compute_clk`: initial 100 MHz, MMCM M16/D1/O8.
- `runtime_memory_clk`: initial 133.333333 MHz, M16/D1/O6.
- Board reference 50 MHz, initial VCO 800 MHz, dynamic reconfiguration,
  `Enable_AXI`, `AXI_DRP=false`, `No_buffer`.
- Compute fast target 800/5.375 = 148.837209 MHz via fractional divider.

Only IP sources were generated: no full-board synthesis/routing or runtime
DRP sequence has been demonstrated. Downstream write-clock generation also
needs reset/relock when its input rate changes.

### Remaining complete-image work, in dependency order

1. An always-on 50 MHz control path available through both PCIe/JTAG even
   when compute and memory clocks stop. Current JTAG mailbox uses compute
   clock, so simply adding MMCM DRP is insufficient.
2. Integrate the prepared AXI register/sequencer component and actual validated
   MMCM configuration engine. Its 21-case component proof does not substitute
   for both-host routing, drain/CDC and complete-image checks.
3. Block new clients, drain accepted transactions/responses, and coordinate
   registered resets and calibration holds/acknowledgments.
4. Connect compute-only and destructive DDR transition state/fault handling to
   the real clocks, drain barriers and target reset synchronizers; retain a
   reachable control path and evidence on a failed transition.
5. Mode-specific DRAM initialization commands, CL/CWL, phase/tap values and
   matching eight-/nine-lane calibration firmware loading/release.
6. Wait for relevant MMCM/write-clock/IDELAY readiness, calibrate required
   channels, initialize memory/ECC and reload model before releasing clients.
7. Actual-rate/status reporting; do not leave static CORE_KHZ/DDR_MTS values
   that describe the old operating point after a change.
8. Transition/abort models and all-mode timing/CDC constraints/disposition,
   including any measured-rate counter crossings.
9. Frozen full top/source preparation, real implementation queue admission,
   synthesis/route/bitstream, exact independent review and package.
10. SRAM transitions plus numerical/reference inference and performance/power
    comparison. Permanent programming is a separate exact-image approval.

### Reproduction prerequisites and commands

Pinned Python environment:
`build/fedora-openxc7/litedram-environment/venv/bin/python` (Python 3.11).
Do not resolve its symlink to the bare interpreter and lose venv packages.
Pins recorded by `boards/ypcb-00338/litedram/core.json`:

```text
migen     e19524c963a8342952840983047557707fbe0b6a
litex     fad9b3759f24a877a71925b7fcfc8b6748c97d62
litedram  7b28f53b1f4c1732b4b503a844a4d5a0cc56416b
```

The prepared compiler container identity is
`7a9b5cf5977e9e09126101c2c2c9b642b3517c3d7894668c36b1d7c550a573b7`.
New generation wrappers mount the new output writable and repository read-only;
old wrappers do not automatically have write access to new directories.

Fresh-directory reproduction, **not commands to execute while paused**:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python -B \
  tools/litedram/runtime_timing.py \
  --out build/checks/runtime-ddr-timing-new

python3 tools/prepare_spare_runtime_shared_core.py \
  --pipeline-preparation build/fedora-vivado/spare-shared-ddr1066-core-20261018 \
  --timing-envelope build/checks/runtime-ddr-timing-new/manifest.json \
  --adapter-model build/checks/spare-shared-native-20261018-v1/manifest.json \
  --bridge-model build/checks/spare-shared-bridge-20261018-v2/manifest.json \
  --controller-model build/checks/spare-shared-real-controller-20261018-v1/manifest.json \
  --out build/vivado/runtime-memory-core-new

build/fedora-openxc7/litedram-environment/venv/bin/python -B \
  tools/check_spare_runtime_calibration_hold.py \
  --preparation build/vivado/runtime-memory-core-new \
  --out build/checks/runtime-calibration-hold-new

python3 tools/prepare_spare_runtime_clocks.py \
  --out build/vivado/runtime-clock-ip-new
```

Existing successful components need not be regenerated merely because the
session changed. Verify their receipts and use them as inputs to the missing
top/controller work.

## 11. Sibling project work already completed or stopped

These were temporary SRAM tasks while OpenTPU builds ran. Keep their results
in their own projects, not as new OpenTPU evidence:

- **tiny-tpu 150 MHz quick physical XOR test passed**: 95 PASS samples,
  no failure samples, 22 heartbeat transitions. FPGA temperature 38.39 C
  before / 39.25 C after (two measurements, not a sampled continuous range).
  Report: `../tiny-tpu/HARDWARE_TEST_20261017.md`.
  Receipt: `../tiny-tpu/ypcb_demo/artifacts/hardware-quick150-20261017/manifest.json`.
- ET-SOC temporary SRAM work was stopped/released when switching to the ready
  OpenTPU c0172300 path. Report: `../etsoc/HARDWARE_TEST_20261017.md`.
  Read its own report for result scope; do not invent an ET-SOC qualification.
- Both former SRAM states are historical. The later c0172300 flash operation
  superseded them. Do not tell the user that tiny-tpu or ET-SOC is still the
  current card image.
- A separate KohakuTPU implementation and old nextpnr routing activity were
  observed live. They belong to other work and must be left alone.

## 12. Resume order and completion criteria

After explicit resume:

1. **Refresh state read-only:** goal, branch, dirty index, services, invocation
   IDs, live children and terminal receipts. Do not trust stale RUNNING fields.
2. **Preserve/obtain the Mac failure evidence**, then verify expected-vs-read
   bytes/mapping and localize the CH0 write/read/IMEM boundary with small tests.
3. **Repair exact final disposition for c0172450/c0172461** in a fresh review
   preparation; retain c0172462's terminal rejection. Complete c0172800 review
   and package promptly when its implementation/evidence are ready.
4. **Fix the demonstrated regression**, host or RTL as evidence requires.
   Use distinct image identities for RTL fixes and do not mutate frozen jobs.
5. **Run already authorized exact SRAM integration** on available hardware
   after technical gates. If the card stays on Mac, prepare small Git handoff
   files and commands for that host; do not label missing physical access as
   missing user approval.
6. **Prove inference and bandwidth** at baseline clocks before interpreting
   clock experiments. Match model/prompt/token/KV/settings and separate
   device counters from USB/host wall time.
7. **Continue corrected faster candidate c0172862**, then useful clock-isolation
   variants/higher-DDR experiments; correct inherited reset defects first.
8. **Finish automatic mixed-width startup** and the actual runtime sweep top/
   transition controller. Do not describe components as a ready full image.
9. **Review small-file Git publication scope** only when committing/publishing
   is requested/authorized. Remove stale archive instructions without adding
   generated binaries to Git. Keep unrelated existing stage entries intact.
10. **Last**, if still requested, investigate physical lane 6 and original ECC.

Practical milestone: full 4 GiB spare-lane OpenTPU uploads the exact program,
passes transfer/mask/matmul checks, produces reference-matching LFM tokens,
and shows measured pipelined bandwidth under the reviewed image. A prior
successful Qwen run, a clean ECC counter, a short matmul or a `.bit` file alone
does not satisfy this milestone for a different image.

For each candidate, separately record source preparation, implementation,
artifact integrity, timing/CDC disposition, package, SRAM load, flash write/
boot (if approved), calibration, actual memory/data correctness, inference
and performance. Close rejected tasks with evidence; do not leave them
indefinitely listed as manual review pending.

## 13. Record precedence, saved state and remaining uncertainties

**Record precedence for this handoff:**

1. Latest user instructions, including pause and the latest Mac failure.
2. Live exact service/process and terminal receipt evidence for the same image.
3. This timestamped handoff and its read-only snapshot.
4. Older canonical progress JSON, Markdown tables and historical reports.

The pre-existing progress files include stale fields; specifically they had
`goal_status: active`, old c0172300 runtime-pending wording, an apparently
waiting final-disposition worker, and historical c0172080/tiny-tpu state.
Handoff housekeeping overlays the paused goal/new failure/review blocker;
do not infer that every historical nested field has been rewritten.

Important saved paths:

```text
HANDOFF.md                                            this document
progress.md                                           preserved older log with current pointer
AGENTS.md                                             repo rules plus current handoff pointer
build/handoffs/session-handoff-20261017/observations.json
build/handoffs/session-handoff-20261017/mac-lfm-failure-user-report.json
build/handoffs/session-handoff-20261017/receipt-*.json   point-in-time copies
build/handoffs/session-handoff-20261017/git-status-before.txt
build/handoffs/session-handoff-20261017/git-staged-before.txt
build/handoffs/session-handoff-20261017/git-diff-stat-before.txt
build/handoffs/lane6-plan-current.json
build/handoffs/spare4gb-live-progress-20261017.json
build/handoffs/refresh-complete-cdc-progress-20261017.py
build/handoffs/pause-after-next-compaction-20261017.json
build/handoffs/compaction-pause-resume-20261017.md
```

The refresh helper is a status generator, not the goal authority. Inspect it
before rerunning: it can retain older classifications and must not turn a
user-paused goal active, erase the Mac failure, restore c0172400 to the active
plan or turn c0172462 back into manual-review-pending.

Still unknown:

- Raw Mac identity, actual imported source versions and full failure receipts.
- Whether the CH0 program mismatch originates in host transfer, writes,
  read-return ordering/capture, partial writes, memory, or later IMEM loading.
- Whether the new pipeline achieves the intended bandwidth once correct.
- Positive final timing/CDC/package result for c0172800/c0172862 and any
  higher-DDR/mixed-startup candidate.
- Complete runtime transition/controller RTL and its real implementation.
- Current physical supply voltage/current/noise and the original lane-6 cause.

There is a credible path to a usable 4 GiB configuration because an earlier
spare-lane image and full-capacity tests worked. **The new failure prevents a
claim that the current pipelined image is reliable.** No probability of repair
was established, and original ECC restoration is a different, later goal.

**Historical end state at handoff creation: goal paused and background builds
left running. The October 18 resumed state and cancellations are in section 2.**


### 20 October 2026: current review and finished timing experiment

Verified the original owner processes released and exact terminal receipts. The c0184806 four-mode control-intent audit passed all 1,360 preserved-path checks; the complete before/after inventory retains all prior findings, with 1,776 findings after intent in each mode. Inventory is not a purpose disposition. Fresh reset, vendor clock-mux and drain-request reviews passed conditionally (3 of 9 initial purpose groups); the six remaining groups and additional all-mode purpose closure are open. Synthesis, 12 full-top modeled traffic cases and the trained 32-token ISA reference had already passed. No c0184806 full implementation has been admitted.

The isolated post-route AggressiveExplore/cleanup experiment completed native exit 0, but final setup is -0.087 ns, TNS -0.600 ns across 33 endpoints; hold +0.024 ns, no hold/pulse failures. Final disposition: `build/checks/runtime-command-postroute-disposition-c0184805-20261020-v3/manifest.json`. This is a completed diagnostic, never a programmable candidate. Select a real timing correction while finishing the current source purpose review. No hardware accessed, no flash changed, no files staged/committed/pushed; pre-existing index unchanged.
