# OpenXC7 trials against the working Vivado MIG reference

## Exact LiteDRAM mapped-netlist comparison plan, October 12

The earlier working Vivado reference uses MIG/DDR1066. A separate comparison
will import the complete mapped LiteDRAM/DDR800 graph currently used by the
corrected full OpenXC7 route. Retain MCOLS4, ACT_ROWS4, LANES8, VPU_CL2,
MXU_IMPL2 and the 100 MHz target; preserve all live jobs and the working image.

The first export in `full-mapped-vivado-reference-20261012T151415Z` exited 1:
`hierarchy -check` tried to re-elaborate DSP48E1 against an existing opaque
library module lacking parameter declarations. The next export will omit
re-elaboration of the already flat mapped graph, explicitly select the top,
and remove only its four nonfunctional `$scopeinfo` cells. Require exact
equality of every remaining module, cell, parameter, connection, port,
attribute and net name after Yosys writes JSON alongside EDIF. Record native
exit codes and immutable input/output hashes. Export alone is not a Vivado
link, implementation, timing or hardware result.

After the full graph comparison passes, link the EDIF in Vivado with the
same part and package. Validate actual primitive counts and numeric clock
properties before implementation. Any vendor-only library adaptation must
be explicitly recorded and reviewed rather than silently dropping cells
or changing clock ratios. Do not replace the already working MIG reference.

The direct export exited 0 in `full-mapped-edif-20261012T152555Z` and wrote
the full EDIF. The strict comparison correctly rejected 88 removed `signed`
wire metadata fields; every retained cell was identical. A minimal isolated
`read_json`/`write_json` reproduction confirms the installed Yosys JSON reader
drops signed wire declarations, independently of EDIF export. Review only
that exact metadata loss and the four scope cells; reject any other change.
This is a flat primitive graph with explicit connections and no arithmetic
operators to re-elaborate. The EDIF exporter also leaves 18,561 unknown RAM
data/parity input bits unconnected; retain that explicit import limitation
for review instead of claiming complete imported functional equivalence.

`full-mapped-vivado-link-named-20261012T153213Z` now has actual native exit 0
and a linked checkpoint. All 717 DSPs, 620 block RAMs and 179,299 FFs survive;
there are no black boxes. Of the original cells, 2,250 INV cells become LUT1,
two OBUFDS cells become standard macros, and six INV cells are absorbed on
ISERDESE2 CLKB / OSERDESE2 T1 inputs. The clock properties retain 28/14,
36/9 and DDR 8/2 ratios. The original net aliases `ld_sys_clk` and `tck`
do not survive EDIF naming, generating two critical constraint warnings;
automatic generated clocks still establish the 100 MHz core and 400 MHz
DDR clocks, while the JTAG root remains unconstrained.

Next, reopen this linked checkpoint in a separate full reference job.
Verify every absorbed input inversion against its actual driver net and
primitive inversion property, and every INV-to-LUT1 INIT. Add the 6 MHz
JTAG root at BSCANE2/TCK, and assert the automatically derived core period
is 10 ns rather than declaring an unrelated replacement root clock.
Apply the already validated 1,103 mailbox datapath bounds and both
three-stage same-slice synchronizer contracts; keep normal stage timing.
Then run full opt/place/route with eight allowed threads, saving each
checkpoint and actual timing reports. This is an offline reference job;
unknown RAM input semantics, final timing and physical LiteDRAM behavior
still require review, and the working MIG image remains untouched.

The `implementation-boolean-20261012T154902Z` attempt validates all 2,250
INV-to-LUT1 truth tables, all 306 absorbed I/O input inversions and their
actual driver-net identities, and every explicitly configured numeric
clock ratio/phase. All 1,103 mailbox endpoints exist and their bounds apply.
It then exits on a scripting error: HU_SET is read-only after synthesis.
An earlier attempt stopped on the Verilog-style `1'b1` boolean encoding;
the corrected reader accepts that encoding and the actual checks pass.
Both failures are retained, without declaring implementation complete.

The next attempt uses documented
[create_macro/update_macro XDC commands](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/update_macro)
to group each three-FF chain at the same relative slice, with AFF/BFF/CFF
BELs. It does not try to assign the read-only RTL RPM properties.
[AMD's constraint guidance](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Defining-Sets-of-Design-Elements)
explicitly distinguishes these commands from HDL-only U_SET/HU_SET/RLOC.
Restore the eight existing INTERNAL_VREF 0.750 bank assignments omitted
from the native-parser XDC, pinning their board-file provenance. No physical
electrical signoff or FPGA programming is implied by these offline settings.

The full `implementation-macros-20261012T155458Z` job now passes all import
inversion checks, all 64 explicitly configured numeric clock parameters,
the 100 MHz core assertion and the complete mailbox/macro constraints.
`clocks.rpt` includes `jtag_tck`, period 166.667 ns, at `u_bscan/TCK`.
`constrained.dcp` is saved (62,014,469 bytes), and optimization is running.
Native PID 280056/start 17151693, controller session 6784, max threads 8.
The first opt/place/route result and final timing review are pending;
no bitstream is generated or programmed by this reference job.

Update after midnight October 13: `optimized.dcp` is saved (40,626,107
bytes), and full placement has started. The post-opt report retains
179,299 FFs and 717 DSPs, with 200,520 LUTs (67.15%) and 567 BRAM tiles
(59.37%). This is the complete original 4x4x8, core100/dualDDR800 scope.
No placement, routed timing or new hardware pass is claimed yet.

## RAM unknown-input review plan, October 13

The full reference import leaves 18,561 original RAM data/parity `x` bits
unconnected. Audit every one against the unchanged complete mapped graph.
Count input and output-port consumers across all functional cells and top
ports. For TDP block RAM, discharge only explicitly disabled write ports
with constant-zero write enables, data/parity bits outside configured width,
or an unread lane whose active read widths match the write width. For the
actual wide SDP modes, use the documented low/high data and parity output
mapping and require the corresponding output bit to have no consumer. For
RAM32M/RAM64M, require the same lane of DOA/B/C/D to be unused. Reject
ECC/cascade modes that could couple otherwise unused input bits into outputs.
Any unmatched bit remains unresolved; do not infer a full import equivalence
pass from an incomplete count. Pin the installed primitive declarations and
keep this a read-only graph review, without changing running jobs.

The wide SDP pin mapping comes from AMD UG473, table 1-15:
[7-series memory resource guide](https://docs.amd.com/api/khub/documents/9gZGbqBxtlKXxBfkBt~lAg/content).
The live pack log and source already confirm six IDELAYCTRL replicas in
OpenXC7, matching Vivado's six-controller placement; no replication patch
is indicated by the original single mapped RTL cell.

The complete RAM-input review in
`full-mapped-ram-unknown-review-20261012T161209Z` resolves all 18,561 bits:
17,316 belong to disabled TDP write ports with zero write enables, 649
to unused LUTRAM read lanes, 16 to unused matching-width TDP read lanes,
and 580 to unused wide-SDP read lanes. An actual active-lane negative
control is rejected when its output is marked observed. This resolves
the disconnected-input observability question in the mapped graph;
full imported parameter/connectivity equivalence and timing remain separate.

Next query all explicitly configured parameters of all 620 block RAMs and
5,003 RAM32M/RAM64M cells in the linked Vivado checkpoint. Compare known
initialization bits, widths, register modes and other explicit settings
against the reviewed complete JSON. Preserve source initialization `x`
bits as don't-care masks, and reject unknown actual bits wherever the
source specifies a value. Retain missing-property or mismatch results;
do not treat a successful native query alone as parameter equivalence.

## Full placement result, October 13

The full same-input reference completed placement and entered routing.
The [immutable placed result review](../build/fedora-openxc7/full-mapped-placed-reference-review-20261012T163134Z/manifest.json)
pins the optimized/placed checkpoints and both actual timing reports.
Setup WNS is -0.441 ns, hold WHS -0.550 ns and pulse WPWS +0.264 ns.
These use post-placement route estimates; they are not routed signoff.

The worst of the 20 saved paths runs from
`$auto$ff.cc:337:slice$493455/C` through the LiteDRAM channel-1
bank-machine row bit 7 logic to `$auto$ff.cc:337:slice$491784/CE`.
Its 29 logic levels contribute 1.616 ns; estimated data routing contributes
8.526 ns (84.066%), for 10.142 ns data delay. The clock domain is the
unchanged automatically related 100 MHz core clock. This actual report
identifies a controller critical path; the OpenXC7 50.97 MHz estimate
remains numerically unqualified and lacks a comparable saved placed path.
Keep routing live before choosing an RTL or implementation optimization.

`full-mapped-memory-parameters-20261012T162344Z` is the separate read-only
complete memory query, controller session 30171. A partial observation has
9,877 matching parameter rows across 1,339 cells, no missing properties and
no mismatches. Complete native exit and all 5,623-cell parameter coverage
remain required before marking that review complete.

## Timing closure plan after the first complete route

The first full route now completes with native exit 0, all 397,534 routable
nets routed and zero routing errors. Final STA has setup WNS -0.931 ns,
TNS -411.681 ns across 1,741 failing endpoints; hold WHS is +0.030 ns
with no hold violations, and pulse WPWS is +0.264 ns. This is a complete
route, but not a 100 MHz timing pass or a qualified board image.

Keep the baseline artifacts immutable. Run physical optimization in a new
directory from the saved placed checkpoint, then route the complete design
again. Use `phys_opt_design -directive AggressiveExplore` with max threads 8,
preserving the original 100 MHz core, dual DDR800, clocks and mailbox/macro
constraints. No retiming option or frequency/size reduction is selected.
Save before/after physical-optimization timing and the new routed result,
then independently compare route completeness, setup/hold/pulse timing and
synchronizer locations. Keep memory import review separate and pending.

AMD recommends the post-place opportunity here: its
[physical optimization guidance](https://docs.amd.com/r/en-US/ug904-vivado-implementation/Physical-Optimization)
notes limited benefit from post-route optimization for a large number of
failing paths. The selected
[AggressiveExplore directive](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/phys_opt_design)
does not select the explicit retiming options. This is a controlled full
implementation attempt, not a claimed timing improvement.

The [independent terminal review](../build/fedora-openxc7/full-mapped-route-reviewed-20261012T165055Z/manifest.json)
confirms complete route/zero errors, the exact final timing numbers and both
three-stage synchronizers remaining in one slice. The separate native
[memory review](../build/fedora-openxc7/full-mapped-memory-parameters-20261012T162344Z/manifest.json)
also completes with exit 0: all 105,612 parameter rows across 5,623 cells
match, with 1,335,120 defined source bits checked and 20,825,136 recorded
source don't-care bits. No missing properties, duplicate/missing rows or
mismatches were found.

The [full CDC/clock coverage review](../build/fedora-openxc7/full-mapped-cdc-reviewed-20261012T165711Z/manifest.json)
verifies all nine reported clock-pair rows and 4,127 safe endpoints, with
zero unsafe/unknown/missing-ASYNC_REG endpoints. The two asynchronous JTAG
rows have 532 and 573 endpoints, covering the 1,103 direct payload bounds
and two first-stage synchronizer inputs. All internal no-clock,
unconstrained-endpoint, multiple-clock and pulse-clock checks are zero.
This is conditional on the already documented command payload protocol;
it does not eliminate the failing core setup timing or imply hardware proof.

`full-mapped-vivado-physopt-20261012T165232Z` is the new isolated full attempt,
native PID 300886/start 17495639, controller session 9744. It preserves
the old placed/routed results and working MIG image. Initial post-place
WNS -0.441 ns improves through -0.398, -0.356 and -0.272 ns in actual
optimization logs; critical-cell optimization is still running. These are
intermediate estimates; final routed timing and unchanged protocol/clock
coverage remain required. All 31 frozen design sources still match.

Update 01:15 HKT: full post-place physical optimization completes and the
next full route has started. The
[immutable before/after timing review](../build/fedora-openxc7/full-mapped-postplace-physopt-review-20261012T171514Z/manifest.json)
records setup WNS -0.441 to +0.003 ns, TNS -232.541 to zero and setup
violating endpoints 1,236 to zero. Hold WHS is -0.236 ns with 3,628
violating endpoints; pulse WPWS remains +0.264 ns. The 106,079,013-byte
optimized placed checkpoint and both actual timing reports are pinned.
These remain placement estimates; final routed setup/hold, clock/CDC
coverage and hardware validation are pending. No target or scope changed.

Before generating a bitstream from the optimized result, independently
review its terminal native exit, every immutable report/checkpoint hash,
complete routing, final setup/hold/pulse timing, all internal clock checks,
the actual CDC rows and both same-slice synchronizers. Verify the unchanged
core/DDR/JTAG clock periods and link the completed 5,623-cell memory review.
Keep hardware readiness and bitstream integrity separate; no intermediate
positive setup estimate substitutes for the terminal routed report.

The reviewer now accepts both terminal baseline and physical-optimization
schemas, using their actual exit files. Its real baseline exercise in
`full-reference-final-gate-baseline-20261012T172332Z` passes clock/CDC,
synchronizer and full memory-parameter checks but correctly keeps setup
failure as the result. The new route is live, with intermediate setup
WNS +0.118 ns and overlaps reducing from 59,874 to 12,506. Final setup,
hold and pulse timing remain unproven until the terminal route is reviewed.

The new route subsequently reaches zero overlaps in global iteration 0,
then enters global iteration 1 for timing optimization. Its intermediate
setup WNS is -0.777 ns with TNS -258.858 ns. The earlier positive placement
estimate does not establish routed timing closure. Preserve the full target
and wait for terminal reports; no bitstream is accepted or programmed.

The next global iteration improves intermediate WNS to -0.546 ns and
TNS to -70.411 ns; global iteration 2 is still active. These are progress
measurements, not a completed 100 MHz timing result.

The post-place optimized reroute now terminates with native exit 0.
The independent full gate confirms all 397,854 routable nets routed,
zero errors, unchanged clocks, safe CDC and same-slice synchronizers.
Final setup WNS is -0.245 ns, TNS -8.311 ns with 125 failing endpoints;
hold WHS is +0.034 ns and pulse WPWS +0.264 ns, with no hold/pulse failures.
Preserve this result in `full-reference-physopt-route-reviewed-20261012T173923Z`.

The next controlled attempt opens that actual routed checkpoint and runs
post-route AggressiveExplore physical optimization on the much smaller
remaining failing set. Use the original scope/targets, max threads 8 and
no explicit retiming. Post-route physical optimization updates routing
automatically; review complete routing afterward rather than discarding
the improved existing routes in a fresh full default reroute. If routes
remain incomplete, retain a failure receipt and repair them explicitly.
Pin the original mailbox contract through the validated reference chain.

### Final full mapped-reference bitstream export

Prepare a separate `openxc7_mapped_vivado_bitstream.py` exporter while the
post-route optimization remains live. Require the completed full route
review to pass setup, hold, pulse, clocks, CDC, synchronizers and imported
memory checks; independently rerun that review on its pinned native receipt.
Follow the hashed implementation/link lineage to the exact source XDC.
Keep all 243 package pins and IO standards identical to that source, both
DDR channels and the unchanged full 100 MHz scope. Restore only the design
configuration properties CFGBVS GND and CONFIG_VOLTAGE 1.8 from the board's
existing `otpu_top_ld.xdc`; verify the existing eight 0.750 V internal VREF
settings and BSCANE2 USER2. These are reference constraints, not new physical
measurements. Reject native Error/Critical Warning DRC violations, preserve
the final checkpoint and reports, and use normal Vivado bitstream generation
without severity overrides. Reuse the existing independent .bit packet and
device checker, recording its CRC-check limitation explicitly. This export
does not access hardware or replace the already working MIG reference.

The exporter is now implemented. Source extraction covers exactly 243
ports and 905 pin properties. Boolean pullups accept Vivado's equivalent
Boolean representations without weakening other property comparisons.
The actual -0.245 ns failing full review is rejected before creating an
export directory or launching native Vivado; its retained guard receipt is
`mapped-reference-bitstream-guard-20261012T175541Z`. Positive native export
now runs in `full-mapped-vivado-bitstream-20261012T183200Z`, session 4592,
after independently rerunning the completed full reference review.

The post-route optimization terminates with actual native exit 0. Its
completed full gate in `full-reference-postroute-reviewed-20261012T183107Z`
confirms all 397,867 routable nets routed with zero errors, WNS 0.000 ns,
TNS 0.000 ns, WHS +0.034 ns and WPWS +0.264 ns, with zero failing setup,
hold and pulse endpoints. Original clocks, CDC safety, both same-slice
synchronizers and the imported memory review pass. The full scope and
100 MHz / dual-DDR800 targets remain unchanged; external DDR calibration
and physical hardware behavior remain pending. The earlier intermediate
WNS reports below are historical, not the terminal result.

The first export stops before bitstream generation because its guard queries
the internal design `NAME` rather than the module `TOP`. The preserved DCP
`dcp.xml` records the exact expected top and part; the existing native-route
script also uses `get_property TOP [current_design]`. Correct that property,
add an offline DCP metadata check, and retry in a fresh output directory.
Retain the failed native exit/log/helper and unchanged successful route.

That correction is implemented. Offline positive preflight confirms the
real DCP metadata, all 243 ports / 905 properties and six pinned lineage
descriptors. The fresh export runs in
`full-mapped-vivado-bitstream-top-20261012T183600Z`, controller session 2253.
The successful full route remains unchanged; this retry does not repeat
placement or routing or access hardware.

The corrected export now completes with actual native exit 0. The native
bitstream precondition DRC reports zero Errors, and generation ends with
zero Critical Warnings or Errors. The final route and timing reproduce the
completed full review exactly; all 905 package-property checks pass.
The independent packet/device checker passes. Its explicit CRC limitation
remains `NOT_CHECKED`; no independent CRC or physical pass is claimed.

The generated `full-mapped-reference.bit` is 18,735,238 bytes, SHA256
`a2a242dc7edfd80de81e4c9c9224a242b0a6f72d04c999a9875b5d6b82834b7d`.
The final checkpoint is 141,153,976 bytes. All final recorded output hashes
and 31 frozen full-design source hashes are rechecked. This is the exact
mapped-input LiteDRAM reference at full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/
MXU_IMPL2, core100/dualDDR800; the original working DDR1066 MIG reference
is preserved. The native numerical result does not qualify OpenXC7's own
full route or timing model, and the new image has not been programmed.
All four OpenXC7 PID/start identities remain live with advancing CPU ticks,
but no full native route/timing/FASM output exists. USB still detects no
Xilinx cable. Original MIG vops/stream and eight-token physical compiler/
ISA comparison, plus full OpenXC7 image completion, remain pending.
[Completed export](../build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/manifest.json)
and [current complete goal evidence](../build/fedora-openxc7/goal-full-mapped-reference-bitstream-20261012T184530Z.json).

The October 13 02:07 HKT goal turn is a verified wait: the same native
session 59986 is pending, actual PID/start identities still match and CPU
ticks advance for the optimization plus all four retained OpenXC7 trials.
All 31 full-design source hashes remain unchanged. No final optimized
checkpoint/timing result or full OpenXC7 route output exists yet. USB still
contains no Xilinx adapter and the fresh kernel query reports no new cable
events. No native job was restarted or modified.
[Current wait evidence](../build/fedora-openxc7/goal-postroute-verified-wait-20261012T180726Z.json).

At October 13 02:21 HKT, the same optimization advances intermediate core
WNS to -0.024 ns. The same five PID/start identities remain live and CPU
ticks advance, all 31 source hashes still match, and no Xilinx USB adapter
is detected. This remains a verified wait for terminal full-scope reports;
there is no accepted new image or completed OpenXC7 route.
[Latest wait evidence](../build/fedora-openxc7/goal-postroute-verified-wait-20261012T182110Z.json).

Updated 2026-10-12 HKT. The user requested completion of the pending physical
Vivado tests, followed by OpenXC7 synthesis and routing using that image as the
reference. The working Vivado image is preserved. Reference export and full
Yosys netlist import succeeded; independent RTL synthesis and full OpenXC7
implementation have not passed for the MIG design.

The user subsequently approved continuing the full LiteDRAM implementation with
the working Vivado MIG image as its functional reference. The new route uses
the latest merged and verified backend, retaining the complete accelerator and
both memory channels. Its directory is
`../build/fedora-openxc7/litedram-vivado-reference-20261011T170600Z/`.
Actual start was 01:04:45 HKT; the directory suffix is not the wall-clock start.
The controller revalidated all five correction gates and 1563 pinned inputs,
the full independent synthesis checkpoint, unchanged sources, and the original
Vivado offline image audit. It requests eight threads. A live observation
confirmed exact nextpnr PID 138789, all eight CPUs allowed, and advancing CPU
time. The initial four placement iterations completed; full placement/routing
is still running. Preserve this live job; do not launch a duplicate.

At 01:14:17 and 01:16:39 HKT, two bounded read-only observations captured the
actual strict-legalizer counters. Calls increased by 2851 and queued entries
decreased by 2851. Both observers exited 0, detached, and verified the same
process resumed with no tracer. This demonstrates forward progress during a
quiet log interval. Queue entries are not unique unplaced cells; repeated or
rip-up placements prevent interpreting these counts as a percentage or ETA.
The receipts are `placer-counter-20261011T171416Z.json` and
`placer-counter-20261011T171638Z.json` in the active route directory.

The next observation at 01:29:27 HKT captured 1,170,723 calls and 201,084 queued
entries on the same process, another 52,408-entry queue decrease. Calls include
repeated placements: they increased by 1,123,925 during this interval. The
observer again exited 0 and detached normally. Its receipt is
`placer-counter-20261011T172927Z.json`; placement/routing remained unfinished.

A detailed bounded read-only snapshot at 02:00:45 HKT counted all 300,290 cells
in the current legalizer vector: 126,017 bound and 174,273 unbound. Unbound
roots comprise 106,790 LUTs, 67,465 flip-flops, 17 DSPs and one clock buffer.
Macro children are outside this vector, so these are current-pass counts, not
overall completion figures. The queue has one fewer entry because its current
cell has been popped. The memory read took under one second; the observer
exited 0, detached, and confirmed the same process resumed without a tracer.
Receipt: `placer-counter-20261011T180045Z.json` in the active build directory.
Both LUT and flip-flop placement remain; a sampled flip-flop alone does not
describe the whole remaining workload.

The complete 02:05:02 snapshot of the same vector found 128,191 bound cells,
2,174 more than at 02:00:45; the increase is entirely in flip-flops. Both
snapshots have zero unexpected BEL values and normal observer detach. This
confirms actual binding progress beyond queue-size observations. Receipt:
`placer-counter-20261011T180502Z.json`. It remains a current-pass measurement.

`tools/fedora_resume_openxc7_reference.py` owns this attempt and records stage
commands, child PIDs, logs and actual exits. After successful full routing it
invokes the existing guarded finalizer for strict frames, bitstream assembly
and independent image checks. No hardware is programmed. Current backend SHA:
`975e6dbd3cb87e8e4cac71fc2e4b68b9afa0b1695c0a5b1ebd85e551485577d2`.
All 25 shared frozen RTL files match except `otpu_mem_ch.sv`, whose difference
is the native single-port MIG adapter. The memory profiles remain explicitly
different: LiteDRAM DDR800 versus MIG DDR1066. Identical shared compute sources
do not constitute a complete functional or physical equivalence proof.

## Reference and physical limits

Reference directory: `../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/`.
It retains the full MCOLS=4, ACT_ROWS=4, LANES=8 accelerator, 100 MHz core,
DDR3-1066, both 72-bit ECC memory channels and USER2 JTAG access.

| Artifact | SHA256 |
| --- | --- |
| `implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit` | `0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f` |
| `routed.dcp` | `43287be1e6e59e88e09d1cca6a78959c4d406d1daaf8a9b51cad24b5c4ada0f7` |

The image was programmed into SRAM on Oct 11 and passed all four full-capacity
patterns on both 2 GiB channels with zero readback/ECC errors. The normal
all-units and masked-write kernels matched the ISA simulator. USB failure
interrupted vector operations; stream checks and physical LFM2 token comparison
remain pending. See [physical receipts](fedora_vivado_jtag_results.md) and the
[USB investigation](dlc10_usb_stability.md). The saved compiler/ISA model output
is reference evidence, not a physical inference pass.

The Oct 12 hardware resume watcher reached its actual terminal exit 2 at
00:42:05 HKT. Its status is `WAIT_USB_EXPIRED_NO_HARDWARE_ACCESSED`; no new FPGA
load or physical computation occurred. Receipt:
`../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-resume-20261011T163700Z/`.

The subsequent corrected-driver watcher ran from 01:18:09 to 01:48:09 HKT and
also reached actual exit 2, `WAIT_USB_EXPIRED_NO_HARDWARE_ACCESSED`. Its process
is absent and session 57211 is terminal. No FPGA load, XVC session or physical
selftest started. Receipt:
`../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-usb-fixed-watch-20261011T171809Z/process-exit.json`.
The full LiteDRAM route remained live independently of this USB timeout.

## Export and backend import

`tools/fedora_openxc7_vivado_reference.py` opens the frozen routed DCP read-only
in Vivado with eight threads and exports the full functional primitive netlist,
EDIF, primitive counts, ports and physical cell locations. These exports are
kept separately from the qualified image.

| Trial directory under `build/fedora-openxc7/` | Actual result |
| --- | --- |
| `vivado-mig-reference-20261011T162400Z` | Vivado export exit 0; initial Verilog import rejected the unused appended `glbl` module. |
| `vivado-mig-reference-20261011T163500Z` | Full Yosys import exit 0; pack exit 125 on explicit PULLUP cells. |
| `vivado-mig-reference-20261011T163720Z` | Reused complete import; normalized five pad pullups; pack exit 125 on a tristate-only OSERDES. |

The frontend uses `-D GLBL` to omit the unused simulation startup module and
imports installed hardware primitive declarations as opaque cells. It retains
716 DSP48E1, 558 RAMB36E1, 31 RAMB18E1 and every required MIG hard cell. This is
Vivado synthesis followed by Yosys import; it is not independent OpenXC7
synthesis or an equivalence proof.

Five explicit simulation-style PULLUP cells were converted to the corresponding
pad `PULLTYPE=PULLUP` XDC properties. All 247 exported package-pin/IO-standard
pairs are retained. The latest pack run binds the DDR delay primitives using
those physical pins before failing on an OSERDESE2 driving only the tristate
path. The installed packer requires OQ or OFB data outputs. The physical cell
was retained; removing it would invalidate the DDR interface.

The exact backend is:

```text
${YPCB_ROOT}/projects/bonetto-soc/build/opentpu-placer-recovery-20261007T165149Z/carry-sites-backend-v2/nextpnr-himbaechel
SHA256 8628624e01f6c007e9235cb323532a32264e353dcfd26a790ec5a4a9e6418a51
```

The exact chip database is:

```text
${OTPU_WORKSPACE_ROOT}/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin
SHA256 790e05a88e8406b4da69d4fb6a158317e2621c85aa8452973edc85a8a4be1492
```

## Hard-PHY resource coverage

An actual database audit and six actual one-cell placement trials establish a
separate blocker. Each probe keeps its primitive and invokes the real backend
with `--no-route --threads 8`. These are capability tests, not working DDR tests.

| Primitive | Required by the full reference | BELs in this database | Probe exit |
| --- | ---: | ---: | ---: |
| PHASER_IN_PHY | 18 | 0 | 125 |
| PHASER_OUT_PHY | 24 | 0 | 125 |
| PHASER_REF | 6 | 0 | 125 |
| PHY_CONTROL | 6 | 0 | 125 |
| IN_FIFO | 18 | 0 | 125 |
| OUT_FIFO | 24 | 0 | 125 |

All six trials report no remaining BEL capable of implementing their primitive.
The audit also finds no related BEL types that could substitute for them.
Receipts: `vivado-mig-reference-20261011T162400Z/chipdb-mig-resource-audit.json`,
`primitive-probe-results.json` and `primitive-probes/`.
`tools/openxc7_mig_resources.py` preserves a reproducible version of this audit.

Fixing the OSERDES packer alone therefore cannot enable full MIG routing.
This installed backend/database needs physical PHY resources, primitive packing,
routing and configuration-bit support. Earlier LiteDRAM DDR800 checkpoints use
a different memory PHY; their placement history must remain distinct from the
working Vivado DDR1066 MIG reference. The reference can guide a LiteDRAM port's
functional validation without making those two controllers identical.

## Independent frozen-RTL synthesis trial

`tools/fedora_openxc7_vivado_mig.py` imports the complete frozen accelerator RTL
and actual generated MIG RTL. It copies sources into an isolated trial directory
and records all normalizations:

- Removes only MIG simulation `$display` statements unsupported by the frontend.
- Represents the three core MMCM real-valued overrides as decimal strings,
  matching Yosys's primitive-parameter representation.
- Imports the actual installed vendor IDELAYE2_FINEDELAY port/parameter
  declaration, retaining the opaque physical primitive.

Latest receipt: `../build/fedora-openxc7/mig-rtl-synth-20261011T163720Z/`.
Full frontend elaboration wrote `frontend.il`. The process/cleanup stage then
failed `check -assert` with 2661 used-but-undriven warnings. A separate read-only
flatten/cleanup audit still reported 778, including MIG lane/debug/padding
signals. The next audit, `mig-elaboration-audit-20261011T165813Z`, applied
`proc; flatten; opt -full` to the same frozen frontend checkpoint. Full
optimization removed the inactive signals. With only primitive whitebox
models made opaque, the strict check then exited 0 and reported zero problems.
The preserved top contains 79241 coarse cells, including all required PHASER,
PHY_CONTROL and memory-FIFO cells. No explicit undriven-signal tie-offs were
added. `strict-elaboration-result.json` pins the actual graph and log hashes.

An intermediate audit mistakenly selected all modules for blackboxing and
therefore produced an empty top. Its exit 0 was explicitly invalidated and its
output is preserved as `invalidated-blackboxed-top.json`. The final result
checks that the top remains present, unblackboxed and populated, and that all
required MIG resource types remain. This does not count the invalidated result
as a pass. The reusable helper now performs full optimization before its strict
check and targets only whitebox primitive models.

No independent **mapped MIG** `synth.json` was produced. The selected LiteDRAM
checkpoint has separate successful independent synthesis evidence and is the
one used for the active full route.

Yosys 0.65 uses the installed Slang plugin. The tested invocation requires
`LD_PRELOAD=/usr/lib64/libstdc++.so.6` for that plugin's runtime. Eight threads
are requested where the installed tools support them; Yosys passes do not all
parallelize.

## Resume commands and remaining gates

Use a new output directory for each trial. Existing files are receipts, including
failed attempts, and should not be overwritten.

```bash
# Run from the root of your OpenTPU checkout.
python3 tools/fedora_openxc7_vivado_reference.py \
  --reference build/fedora-vivado/mig-jtag-controller-20261010T235833Z \
  --reuse-export build/fedora-openxc7/vivado-mig-reference-20261011T163500Z \
  --reuse-import build/fedora-openxc7/vivado-mig-reference-20261011T163500Z \
  --out build/fedora-openxc7/vivado-mig-reference-NEW_TIMESTAMP
```

Repeating this unchanged currently reproduces the OSERDES packing error.
Resource coverage needs an implementation change before a successful full route
can be expected. The independent RTL command is:

```bash
python3 tools/fedora_openxc7_vivado_mig.py \
  --reference build/fedora-vivado/mig-jtag-controller-20261010T235833Z \
  --out build/fedora-openxc7/mig-rtl-synth-NEW_TIMESTAMP
```

Outstanding work: stable USB and full physical Vivado model comparison;
successful full LiteDRAM placement/routing, timing and configuration assembly,
then its own physical memory/compute comparison. Keeping MIG for an additional
OpenXC7 implementation would still need mapped synthesis and backend PHY
support. No full OpenXC7 route or OpenXC7 board bitstream has passed yet. The
LiteDRAM full route is active; the MIG reference/audit trials are terminal and
no hardware client remains.

At 02:44 HKT on 2026-10-12, the full heap job remains active. A separately
qualified complete backend fixes a core-confirmed float exponential overflow
in the alternative static placer. All five actual exact-binary correction
checks and strict frame assemblies passed concurrently. The complete static
retry requests eight threads and has passed the prior crash point. No full
OpenXC7 route or accepted image has completed. See
[the static placer evidence](openxc7_static_placer.md) and the latest
[progress handoff](../progress.md) for exact paths and live process identities.
