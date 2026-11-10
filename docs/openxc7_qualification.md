# OpenXC7 board-image qualification

The complete same-mapped-input Vivado reference now passes its internal
100 MHz route/timing, clock/CDC, pin and memory gates and produces a checked
full dual-DDR800 bitstream. Its reported setup WNS is 0.000 ns with zero
failing endpoints. This reference has not been physically tested and does
not qualify the still-running OpenXC7 route or provisional FF timing model.
[Completed Vivado reference](../build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/manifest.json).

## Corrected-clock backend qualification, 2026-10-12

The current corrected database/native executable now reproduce all five
carry, upper-carry, four-chain DSP, FF-edge and actual full-map MUXF7
witnesses. All five FASM files and strict frame files are byte-identical
to their previously qualified outputs. Complete routed graphs, cells,
parameters, placement and routing metadata also match; only four new,
explicitly disabled reporting settings differ. The FF full/half-period
timing report is identical. Fresh strict assembly passes for all five
witnesses plus the actual clock fixture.
[Native results](../build/fedora-openxc7/clock-primitive-check-20261012T132400Z/manifest.json)
and [independent graph/frame review](../build/fedora-openxc7/clock-primitive-reviewed-20261012T134000Z/manifest.json).

The independent frame review confirms all 12 restored clock cascade feature
bits, including rejection of a flipped physical bit. The actual clock
fixture also passes frames-to-bit conversion, USER2 packet inspection and
independent payload/ECC comparison over all 46,336 legal frames.
[Codec result](../build/fedora-openxc7/clock-codec-check-20261012T133557Z/manifest.json).
This validates the configuration path for the clock fixture; it is not a
full accelerator bitstream or numerical timing signoff.

The full mapped graph is independently verified against the running route's
constrained input, permitting only its two recorded MMCM LOC attributes.
Hardware counts remain 717 DSPs, 514 RAMB36s, 106 RAMB18s, 144 input
serializers, 214 output serializers, one BSCAN, three MMCMs and one PLL.
All original compute dimensions and the core100/dualDDR800 profile remain.
The [full-image preparation](../build/fedora-openxc7/clock-image-prepared-20261012T132214Z/manifest.json)
pins 2,283 source, tool and assembly inputs. The new finalizer verifies the
terminal full route, literal VREF plan, strict frames, USER2 and every frame
payload/ECC value. Its live-route check returns a wait and creates no image
directory or output. Run it after the recorded route succeeds:

```sh
python3 tools/openxc7_clock_image_assemble.py \
  --preparation build/fedora-openxc7/clock-image-prepared-20261012T132214Z/manifest.json \
  --out build/fedora-openxc7/clock-image-finalization-pending
```

Full numerical timing and the remaining physical compiler/model selftest
remain unqualified. An offline assembly result will retain those limitations;
full timing qualification precedes hardware loading.

Current continuation, 2026-10-12: the user resumed OpenXC7 work after obtaining
a working native Vivado MIG image. See [the complete reference
trials](openxc7_vivado_reference.md) for the successful export/import, actual
MIG PHY coverage and pack failures, and independent RTL synthesis limits.
The LiteDRAM DDR800 checkpoints below remain historical and use a different
memory controller from the working DDR1066 reference.

The upstream BUFGCTRL route-through guard is now implemented in an isolated
candidate. Native comparisons cover both K480T clock tiles, three small routes
and explicit corrupt-FASM rejection. Full unchanged-design packing/analysis
preserves all 1103 payload endpoint audits, synchronizer clusters and phase
budgets. This removes a demonstrated routing-policy gap; full implementation
and numerical timing remain pending. The original live jobs remain unchanged
and their eventual output requires this clock-driver gate. See
[the router review](openxc7_router_review.md).

Latest evidence, October 12 at 14:38 HKT:30 HKT: isolated opt-in callbacks pass on
the complete design for all 717 DSPs, all 358 serializers and all 20 clock
cells. Each timing backend rebuilt 14 affected files with eight workers.
The latest eight clock configuration cases pass, and the complete native
pack has zero mismatches across 122 clock control checks and 4,746 serializer
checks. Generated clock outputs retain their class; disabled reset arcs
remain explicit model records without fabricated delays. All 20 used
generator periods also pass. See [the PHY timing evidence](openxc7_phy_timing_plan.md).
Exact nominal waveform extraction now verifies all 20 generator outputs'
periods, phases and high times, plus their actual shared ancestry and dynamic
fine-phase groups. Eight parallel native cases pass, and all complete-design
sampler references are present. The one unknown raw JTAG clock is referenced
only by two independently proven constant buffer controls; it remains explicit.
Nominal setup/hold integration now passes actual analyser comparison with
40 vendor register paths and eight native configuration cases. The complete
unchanged accelerator's explicitly unplaced intrinsic analysis exits 0 with
18 domain pairs: 14 known, two dynamic and two unrelated. Sixteen timing-dependent
files rebuilt with eight workers. These are nominal edge-budget checks, with
clock insertion/skew and whole-board numerical timing still unqualified.
The three original complete implementation processes continue with their
unchanged binary and eight-thread requests. Full route/image output remains
pending, along with insertion/skew and dynamic-phase/CDC interpretation, Kintex
fabric data, uncertainty/reset synchronization and full routed path qualification.
The area router now has one running main thread and five five-million-iteration
arc-search warnings. This is live routing evidence, not a terminal route result.

The subsequent complete intrinsic path export exited 0 and identifies all four
unknown crossings: two falling-edge DDR command transfers into shifted clock
domains and the two first-stage JTAG toggle inputs. Both three-register JTAG
chains and their net-level ASYNC_REG annotations survive packing. DDR800's
host/firmware phase wrap needs a 1250 ps phase margin, rather than the donor's
1000 ps default; 25,088 actual host-control moves pass with mocked CSRs.
This is topology/software evidence. The subsequent isolated phase contract
passes 18 actual Vivado snapshot paths and eleven native cases. Its full
unplaced analysis exits 0 with 14 nominal pairs, two conditional DDR pairs at
3750/-3750 ps and two unrelated JTAG pairs. A fresh contract is required on
replay, with root/VCO/source guards. Synchronizer/payload constraints,
skew/jitter and routed checks remain pending; no asynchronous exception was
added and the original route retains its backend.
See [the traced paths and phase review](openxc7_phy_timing_plan.md).

The subsequent full packed mailbox audit verifies all 1103 live request/response
bit crossings and both three-register synchronizer chains, including isolation
of the first two stages from consumer logic. Digital delay tests pass 22
positive cases and detect both injected late payloads. An exact-part vendor
FF-pair probe validates every 20 ns request and 300 ns response datapath-only
requirement, with stand-in enables/clocks. This supplies a complete candidate
constraint list. A new isolated synchronizer importer passes eight native
cases, including two actual placement/routes using both slice sites, and a
full unchanged-design pack with six audited cell/cluster records. The subsequent
direct-datapath importer passes eleven native semantic cases and a complete
audit of all 1103 endpoint limits, with unchanged clusters and phase budgets.
It excludes clock contributions and includes clock-to-Q/data-route/setup,
but generic FF numeric values remain provisional. Full new placement/routing
and numerical timing qualification remain pending. Simulation
and synthesized pair queries do not prove the full
parent's route or physical CDC behavior.

The first target is the full OpenTPU accelerator, both 72-bit DDR channels and
the real self-calibration CPU, controlled over DLC10 JTAG while the card has
separate power. Placement and routing, timing, frame assembly and physical
DDR/compute validation are still required. The PCIe endpoint is a later part of
the complete board preparation.

## First-run memory rate

AMD's [Kintex-7 DS182 v2.19](https://docs.amd.com/v/u/en-US/ds182_Kintex_7_Data_Sheet),
Table 18 note 2, limits memory interfaces using internal VREF to 800 Mb/s.
The FFG1156 package's HR-bank table otherwise permits DDR3-1066 at speed grade
-2. The inherited LiteDRAM XDC selects internal 0.750 V VREF. Its DDR3-1066
configuration therefore exceeds the published limit for that VREF choice.
This is a qualification concern; the table does not predict a particular
card's experimental result.

Keep the original DDR3-1066 source and synthesis for comparison. Generate a
separate DDR3-800 first-run profile with `tools/fedora_prepare_litedram.py`:
100 MHz controller/core clock, CL6/CWL5, both 72-bit channels, ECC, four native
user ports, both BISTs and the VexRiscv calibration CPU. The full MCOLS=4,
ACT_ROWS=4, LANES=8, MXU_IMPL=2 and VPU_CL=2 compute configuration is retained.
The firmware and host init sequence are regenerated together; changing only
the reported DDR_MTS register would be incorrect.

The saved primary PDF is
`build/fedora-openxc7/deps/ds182_Kintex_7_v2.19.pdf`, SHA256
`28cc06afd9a62dadced8c5829c5a4a28d5d66d8d5434a34c94240154bbab80cc`.
The profile's parameters and artifact hashes are checked before synthesis.
Routing inherits that same profile and its clock rate. The host rejects a
DDR calibration profile that disagrees with the loaded image's DDR_MTS before
writing calibration CSRs.

DDR3-800 alone does not establish timing closure. A DDR3-1066 image must also
resolve or explicitly qualify the VREF-rate issue; do not silently turn off
internal VREF without confirming the board's external reference circuitry.

## Actual backend gaps

The complete DDR800 synthesis passed on 2026-10-07, using ABC-fast LUT mapping.
It contains 717 mapped DSPs, 514 RAMB36E1s and 106 RAMB18E1s. Its unchanged
mapped checkpoint is in
`build/fedora-openxc7/ddr800-full-pipeline-20261007T065718Z/synthesis`.
The following placement failed on a 16-DSP MXU cascade: the packer assumes
five tile rows between DSP pairs, but this device also has six-row clock gaps.
The actual database admits zero 16-DSP roots under those fixed offsets and
876 roots when consecutive absolute DSP site coordinates are used.
[The correction plan](openxc7_dsp_cascade.md) records the evidence, isolated
backend rebuild and real cascade-routing checks. A new controller reuses the
full mapped checkpoint; this correction does not require full synthesis again.
The corrected backend passed the four real DSP cascades, both FF edge pairs
and strict probe-frame assembly. Its full-design run subsequently failed
main placement on a CARRY4 after 10,001 attempts, at 14:52 UTC. The captured
full cluster has no outputs: it is an unused comparator-padding tail with
four LUTs feeding only it. An isolated prefix-preserving splitter correction
now passes actual carry routing and all 256 input combinations against the
XC7 primitive models. [The carry plan and evidence](openxc7_carry_padding.md)
record the correction and the strict-frame/DSP/FF gates before another full
implementation. Full routing and the OpenTPU bitstream remain unproven;
the original full mapped checkpoint is retained.

The exact board XADC/BSCAN probe in
`build/fedora-openxc7/xadc-bscan-feasibility-20261006T192721Z` fails placement:
the selected chipdb has no XADC BEL. BSCAN packs successfully. The checked
openXC7 fork source at `bc9b234634cf80756b04ad4ea5f8e7a83293c425` also has no
XADC packer or FASM writer in the examined source files.

The standalone port will retain die-temperature monitoring through the
chip's dedicated [XADC JTAG DRP interface](https://docs.amd.com/r/en-US/ug480_7Series_XADC/DRP-JTAG-Interface).
UG480 specifies that this interface needs no fabric instance: select IR
0x37, submit a 32-bit read command, provide at least ten Run-Test/Idle
clocks, then capture the 16-bit result. The host must restore USER2 while
holding the transport lock. No calibration or configuration writes are
needed for the default internal-sensor measurements.

The FPGA will advertise that it has no fabric temperature register;
`Board.info()` will acquire the actual temperature through the JTAG
transport. All compute dimensions, both DDR channels and their calibration
CPU remain present. The original pre-adaptation diagnostic sources are
saved and hashed, and its running synthesis continues from the unchanged
checkpoint. The adapted DDR800 design requires a new full synthesis and
route. Protocol checks do not establish physical temperature or DDR proof.

The adapted full DDR800 elaboration passed with zero structural problems
and retains 528 explicit DSP48E1 cells, one BSCANE2 and the real VexRiscv
calibration CPU. Its checked checkpoint is in
`build/fedora-openxc7/jtag-ddr800-adapted-elaborate-20261006T195720Z`.

The original default ABC mapper remains a comparison run. The actual
DDR800 build can use `--abc-fast`: Yosys's documented LUT script
`strash; dretime; if` replaces the default SAT-intensive optimisation
sequence. The complete xc7 memory, arithmetic, I/O, FF and finalisation
stages remain, with the same LUT costs and full compute dimensions. A
`pre-lut.il` checkpoint permits subsequent mapping refinements. This is
a mapping-quality tradeoff: actual area, placement and timing must still
pass. It is not a qualified board image or a reduced accelerator.

The current nextpnr donor revision is
`c68c13582e972292c86a5025140d52e713384cbc`. Its v6 xc7k480t chipdb contains
only 12 timing variants. `tools/openxc7_chipdb_audit.py` records the exact
database and source constid hashes and missing variants.

A read-only query of the installed Vivado Lab 2026.1.1 found no registered
`get_speed_models`, `get_timing_arcs` or `report_timing` commands. The transcript
and command capabilities are indexed by
`build/fedora-openxc7/lab-timing-query-capability.json`. That installation cannot
supply the missing timing models through those queries; qualification remains
pending.

On October 12, full Vivado 2026.1 provided raw speed-model data for the exact
Kintex-7 part, including DSPs, MMCMs and both serializer families. The actual
native queries and complete DSP configuration inventory are recorded in
[Vivado timing data](openxc7_vivado_timing.md). The running backend remains
unchanged; parameter, clock and complete numerical timing qualification are
still pending.

- DSP48E1, OSERDESE2, ISERDESE2 and MMCME2_ADV have no timing variants. The
  default lookup in `himbaechel/arch.cc` classifies cells without a timing
  index as ignored.
- The generated SLICE_FFX timing arcs all specify a rising CK edge. Packing
  retains `IS_C_INVERTED`, including the DDR PHY's falling-edge registers,
  but the donor Xilinx implementation has no `getPortClockingInfo` override.
  Its generic API returns the stored chipdb edge. The isolated correction
  described below now applies the inversion to these clocking checks.
- Missing MMCM arcs also prevent the timing engine's clock-driver traversal
  from relating its outputs. Frequency propagation does not establish the
  phase relationships needed by the DDR controller/capture clocks.
- The generator uses provisional fixed LUT/FF delays and Artix-7 carry/mux
  and BRAM SDF data for Kintex-7. Adding the four missing names would not
  qualify the existing numerical model.
- The backend does not apply the original DDR clock uncertainty or reset
  max-delay constraints. Their omission is recorded in each routing audit.

The full elaborated compute array contains 528 explicit DSP48E1 cells in
four A/B/D/M/P register configurations, including 44 with PREG=0. A universal
registered-P timing model would be wrong. The read PHY uses DDR sampling,
and serializer data/control pins use different clocks; its model must retain
CLK versus CLKDIV semantics and both sampling edges.

## Required implementation and evidence

Backend changes belong in an owned isolated source/build directory, preserving
the donor.

`tools/openxc7_ff_edge.py` builds the first correction in a separate directory.
It overrides Xilinx `getPortClockingInfo` for packed `SLICE_FFX` cells, applying
`IS_C_INVERTED` to CK-associated timing checks while preserving the database's
delay values. It rebuilds every translation unit whose recorded dependencies
include the changed class declaration, and snapshots the other linked objects.
The routed three-register comparison passed both rising-to-falling and
falling-to-rising paths. The baseline incorrectly reports both as rising-to-rising;
the corrected binary reports the actual edges and halves the Fmax period factor
for the same modeled path delay. Evidence is in
`build/fedora-openxc7/ff-edge-validation-recovered-20261007T074816Z/manifest.json`.
This change does not qualify the numerical timing model, add missing
hard-cell timing, or change the pinned full-design diagnostic pipeline.

```sh
python3 tools/openxc7_ff_edge.py
```

The full-design controller now waits for the existing DDR800 synthesis to
finish, verifies its mapped checkpoint, and routes it with this checked binary.
The source and input hashes remain pinned; synthesis is not replayed for this
backend transition. The active controller is recorded in
`build/fedora-openxc7/ddr800-pipeline-active.json`.

The remaining implementation should:

1. Honor FF clock inversion and test the period/half-period budgets on a small
   rising-to-falling and falling-to-rising circuit before routing the board.
2. Add parameter-dependent DSP arcs and SERDES/IDELAY/control-clock models
   with source provenance, conservative minimum/maximum bounds and coverage
   for every used port. DS182 Tables 27–29, 35, 41 and 42 are primary inputs;
   tabulated maxima alone do not provide all required hold-delay bounds.
3. Relate generated clocks, static phases and the firmware's dynamically
   calibrated phase range. Apply the DDR setup/hold uncertainty and reset
   path limits, plus the actual JTAG synchronizer constraints.
4. Report setup and hold, ignored/unconstrained endpoints and model coverage
   for the exact mapped/routed netlist. A successful router exit is not this
   report.
5. Apply the verified 0.750 V VREF adapter to the full routed FASM, run strict
   frame assembly, and retain source/tool/frame/bitstream hashes. The existing
   VREF-only fixture proves the voltage bits, not a board image.
6. With the physical card connected, verify IDCODE, both-channel calibration,
   full-address DDR BIST/ECC and the accelerator selftest. Keep simulation and
   physical results separate.

This checklist records the concrete qualification work. No OpenTPU bitstream
or physical DDR/compute pass is claimed by the current preparation artifacts.

## Update, 2026-10-12 15:36 HKT

The original full route now reaches congestion iteration 1 with 564,545
overused wires. All three PID/start identities and all 31 source files still
match; no native terminal route output exists. The separately validated
PR 81 backend is not installed in those live jobs. Current upstream main
is 68 commits newer than the donor, with no general router source changes;
the eight reviewed fork main branches have no additional commits.
[Current review](../build/fedora-openxc7/goal-full-router-and-ff-context-review-20261012T073643Z.json).

The independent FF comparison passes 262 finite contributions across 272
vendor path queries, with ten explicitly ignored datapath-only hold paths.
Immediate D-driver topology changes the capture setup/hold checks in the
same FF. The original port-driven 85 tables therefore remain insufficient
for universal native FF timing. Complete inventories cover all 179,299 FF
control and data-driver contexts. These vendor comparisons do not qualify
the full route; native FF context import and physical pin coverage remain
pending. [FF context evidence and limits](openxc7_phy_timing_plan.md).

## Update, 2026-10-12 18:12 HKT

The completed full routed Vivado reference checkpoint retains its qualified
hash. Its complete 112,352-FF inventory yields 1,985 context groups and
4,002 actual placed samples. All 7,901 finite contributions in 8,004 path
queries match raw vendor arcs; 70 untimed and 33 ignored paths remain
explicitly separate. Numeric values vary within 522 groups, so this does
not qualify a universal native FF callback or the distinct 179,299-FF
OpenXC7 mapping. [Completed reference comparison](../build/fedora-openxc7/full-ff-reference-validated-20261012T100700Z/manifest.json).

Current OpenXC7 upstream main is 70 commits newer than our donor. The
original YosysHQ upstream separately has per-wire memory and reserved-wire
changes. Direct replacement would remove our existing router extensions;
an isolated selected backport and native comparison are required before
use. All three original implementation identities remain live, with no
terminal route output or accepted OpenXC7 image. No hardware was accessed.

## Compact router backend

The selected upstream visited-state memory adaptation is compiled in an
isolated opt-in backend. Six actual same-seed route cases produce identical
FASM, complete routed netlists and clock routing policies. The K480T wire
state vector uses 256 MiB less allocation, with sizeof(PerWireData) 52 bytes
instead of 56. This is not a total-RSS or full-design runtime measurement.
[Native comparison](../build/fedora-openxc7/router-wire-memory-native-check-20261012T102600Z/manifest.json).

The unchanged complete source also packs and audits with native exit 0;
all 1,103 mailbox limits, two clusters and 18 domain-pair budgets match the
parent. No new full placement/route, numerical timing closure, image or
hardware execution is established. Original full jobs remain unchanged.
[Full audit](../build/fedora-openxc7/full-router-wire-memory-check-20261012T103000Z/manifest.json).
