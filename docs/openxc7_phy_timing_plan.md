# Full-design PHY and clock timing

The routed-reference FF grouping is being refined using physical capture
and driver site pins and the driver's BEL, without grouping by location or
measured timing values. The existing 4,002 samples show 522 varying groups
under the earlier grouping, but one varying group with those physical
features included. There are still 875 repeated physical contexts covering
2,118 samples. This is a context hypothesis, not a qualified universal
model. Validate the regrouping against immutable query/results and inspect
the remaining three carry-driven samples, including their input muxes,
control/clock connections and fanout. Do not change the live backend yet.

The independent regrouping now reproduces all 4,002 samples and the earlier
522 varying groups. Adding physical driver BEL and actual capture/driver
site pins leaves one varying group among 2,759 contexts, with 875 repeated
contexts covering 2,118 samples. These keys contain no absolute locations
or measured delays.
[Validated physical grouping](../build/fedora-openxc7/ff-physical-context-validated-20261012T140000Z/manifest.json).

A fresh read-only Vivado query verifies nine actual cells and their drivers,
used site muxes, clock sources, control properties and fanout. All 18 raw
setup/hold arcs match the original reference and all finite path contributions
match those arcs. Examples distinguish `AFFMUX:AX` from `AFFMUX:O5` and
`BFFMUX:O6` from `BFFMUX:BX`, even where the FF BEL/type is identical.
The remaining three carry-driven samples use the same core clock and
`AFFMUX:AX` capture path, but their driver fanouts are 31, 1 and 1; their
small 2–4 ps variation remains an electrical-dependency question, not a
qualified universal model or a proven fanout-only rule.
[Physical query and independent comparison](../build/fedora-openxc7/ff-physical-context-reviewed-20261012T142837Z/manifest.json).

The first unrestricted property query was deliberately stopped after its
clock-net object dump exceeded 2.5 GB. Its failure evidence is retained;
only that isolated diagnostic was terminated. The bounded query collects
explicit properties and visits one net segment per delay query. No reference
checkpoint, running full executable/database, production source or numerical
FF timing model changed.

The complete packed design contains 144 ISERDESE2 cells in one configuration,
214 OSERDESE2 cells in two, three MMCMs in two, one PLL configuration, and
16 BUFGCTRLs in one. Use those exact parameter groups and the declared vendor
primitive ports/defaults to query full Vivado on `xc7k480tffg1156-2`.

1. Preserve the full named-cell inventory and resolve every physical parameter
   from the supplied overrides and primitive library defaults. Record omitted
   simulation frequency-limit constants separately; none are supplied by the
   actual packed design.
   For omitted PLL/MMCM compensation, use the actual FASM writer's INTERNAL
   default. Retain explicit write-MMCM ZHOLD and its buffered feedback rather
   than replacing it with the direct-feedback topology of other generators.
2. Instantiate all seven parameter groups, preserve actual shared CLK/CLKB
   topology, give CLK/CLKDIV their observed 400/100 MHz roles, and retain
   clock-generator parameters and feedback. Export actual cell properties,
   timing arcs, numerical corners and generated-clock properties. Locate
   serializer probes in the actual HR I/O logic; record their physical sites
   explicitly. Full packed I/O cells are IOB33 variants, and live Vivado
   discovery reports 400 ILOGICE3 and 400 OLOGICE3 sites on this part.
3. Compare each declared physical parameter with Vivado. Keep both DDR edges,
   CLK/CLKB/CLKDIV associations, signed requirements, conditional/disabled
   arcs and any unsupported arc types. Query data are not a qualified model.
4. Implement the validated intrinsic callbacks in an isolated backend only.
   Compare actual callbacks and paths with Vivado and then audit the complete
   accelerator's serializer/clock instances.
5. Preserve generated-clock families, ratios, duty cycles and phases in the
   timing engine. Current source derives 50/50 periods, skips buffered feedback
   and does not retain configured 90-degree phases. Validate same-clock,
   divided-clock and phase-offset cases against vendor paths before treating
   full DDR timing as qualified.

Kintex fabric calibration, uncertainty/reset constraints, full routed timing,
strict bitstream checks and physical behavior remain separate requirements.
The complete 4x4/8-lane, 100 MHz accelerator and both DDR800 channels are
retained. The three active implementations keep their current source and
binary while these independent queries and model changes proceed.

Source: [actual full PHY/clock inventory](../build/fedora-openxc7/full-phy-clock-timing-inventory-20261011T231155Z/inventory.json).

The corrected native query completed with exit 0. Its [parameter and arc validation](../build/fedora-openxc7/full-phy-clock-vivado-timing-20261011T234014Z/semantic-summary.json)
checks all seven groups / 378 named cells with zero parameter mismatches and
376 finite timing arcs. Inputs use the actual shared CLK/CLKB net; the source
inversion parameter provides the complementary sampler edge. The raw arcs
include CLK, CLKB, CLKDIV and CLKDIVP checks, signed setup/hold values, hybrid
output behavior and seven MMCM/PLL `Reg Set/Clr` arcs. Those semantics need
explicit handling before a backend import.

Vivado records the 400 MHz write-clock outputs with a 2.500 ns period and
0.625/1.875 ns waveform for the 90-degree outputs. The source clock code does
not retain that offset. Vivado's generated CLKFBOUT periods match their input
periods (10 or 20 ns here), while the current source derives a VCO-rate
feedback-clock constraint. Both differences must be addressed and tested
against vendor paths, including the actual buffered feedback.

The first query synthesized successfully but rejected the nonexistent
ILOGICE2 site selection. Live site discovery and the full packed I/O cell
types establish the actual ILOGICE3/OLOGICE3 HR resources. The second query
completed natively but its ideal direct feedback changed the requested
compensation to INTERNAL. Both attempts and their original helpers are
preserved. The corrected query uses the FASM writer's INTERNAL default for
omitted compensation and retains the explicit ZHOLD write-MMCM configuration
with a feedback buffer. All resulting physical parameters match.

OOC clock-source warnings are retained: intrinsic timing values and generated
waveforms are available, but these probes do not establish placed/routed clock
skew or complete DDR timing. No new timing model was installed in a live job.

The first clock correction is an isolated opt-in feedback derivation change.
Trace feedback through clock buffers only when exactly one connected,
nonconstant input is available, with a bounded visited-net check. Preserve
the existing feedback-divider calculation and derive CLKFBOUT from the actual
feedback-counter divide rather than treating it as a VCO output. Export the
resulting period/high/low constraints for an independent full-design check.
The default off path retains prior behavior. This correction does not yet
implement generated-clock phase/family analysis or serializer callbacks.

That isolated [feedback backend](../build/fedora-openxc7/clock-feedback-vivado-backend-20261011T235202Z/manifest.json)
compiled and linked with unchanged headers and two rebuilt translation units.
The complete unchanged accelerator then packed successfully with the correction
and DSP timing enabled. Its [period comparison](../build/fedora-openxc7/full-clock-feedback-native-check-20261011T235505Z/period-comparison.json)
checks all 20 used clock outputs across the four clock generators with zero
mismatches. Both buffered write-MMCM feedback clocks are now derived at 100 MHz;
the direct PLL and core-MMCM feedback clocks are derived at 50 MHz.

A complete [control run with the correction off](../build/fedora-openxc7/full-clock-feedback-off-check-20261012T000011Z/on-off-comparison.json)
also exited 0. It reproduces the prior 555/714 ps direct feedback periods and
missing buffered feedback constraints; the on case produces 20,000 ps and
10,000 ps respectively. The model remains unselected for the live full route.
Serializer intrinsic callbacks, generated-clock phase/family relationships,
Kintex fabric data, uncertainty/reset handling and vendor path comparisons
remain pending. This component check does not establish full timing closure.

Serializer integration now targets all three exact ISERDESE2/OSERDESE2
parameter groups and all 358 named serializer cells. Preserve each input's
multiple clock checks, apply the declared clock inversion to its sampling
edge, and retain hybrid sequential/combinational outputs. Callback clock counts
include only connected, nonconstant clock ports. Unknown modes are rejected.
Build and test this in a separate opt-in backend, retaining the verified DSP
callbacks and feedback correction.

Actual [input path reports](../build/fedora-openxc7/vivado-serializer-clock-edge-check-20261012T000455Z/sampler-paths.rpt)
confirm capture at both 1.250 ns and 2.500 ns for the shared 2.500 ns sampler
clock. Actual [output path reports](../build/fedora-openxc7/vivado-serializer-output-edge-check-20261012T000740Z/output-paths.rpt)
retain the CLK launch arc and half-cycle/full-cycle DDR capture requirements.
Use those observed associations, rather than inventing an additional launch
arc. Full clock-family phase, uncertainty and routed skew remain unqualified.

The isolated [serializer backend](../build/fedora-openxc7/serdes-vivado-timing-backend-20261012T001818Z/manifest.json)
rebuilt all 14 header-dependent translation units with eight compiler workers;
compilation, linking and startup exited 0. It imports all 82 intrinsic arcs
for the three characterized serializer modes, retaining signed fast/slow
rise/fall bounds and applying the declared clock inversions. Multiple clock
checks and hybrid combinational/sequential outputs remain available through
their respective callbacks. Missing or constant clock inputs create no domain.
The option `-o serdes-vivado-timing=on` is off by default and rejects unsupported
configurations, invalid option values and uncharacterized speed grades.

Eight independent [native configuration cases](../build/fedora-openxc7/serdes-vivado-timing-native-check-20261012T002225Z/manifest.json)
ran with eight workers. All characterized configurations and omitted defaults
match the raw vendor reference: 82 port classifications, 47 sequential checks,
three falling-edge checks and four combinational arcs. Missing and tied
CLKDIVP cases each remove exactly one reset clock check. Default-off behavior
passes; mode, option and speed-grade rejections produce the expected exit 125.
These fixtures use packed serializer cells for callback testing. The first
fixture failed Yosys elaboration on an unrelated BUFGCTRL SIM_DEVICE property;
its helper and logs are preserved. The corrected fixture contains the exact
characterized serializer declarations only.

The separate [complete design audit](../build/fedora-openxc7/full-serdes-vivado-timing-native-check-20261012T002324Z/manifest.json)
uses the unchanged full source/XDC and actual I/O packer: native and controller
exit 0. All 358 named serializers match their expected modes (144 input,
162/52 output), with zero mismatches across 6,174 port classifications,
4,746 sequential checks, 288 multi-clock pins, 288 falling-edge checks and
162 combinational arcs. The full 4x4/8-lane, 100 MHz, dual-DDR800 scope remains.
DSP timing and the feedback correction are enabled in this complete audit.
An independent [period check](../build/fedora-openxc7/full-serdes-vivado-timing-native-check-20261012T002324Z/period-comparison.json)
also confirms all 20 used generator outputs still have the expected periods.

The active full implementations retain their original source and binary.
Clock-generator intrinsic/reset semantics, generated-clock families and phases,
Kintex fabric calibration, uncertainty and complete routed path comparisons
remain required before treating the new backend as qualified.

Clock intrinsic integration targets the remaining four exact parameter groups:
two MMCM modes, one PLL mode and one BUFGCTRL mode, covering all 20 actual
cells. Preserve all 287 enabled arcs, flatten only the packer's bus-pin names,
resolve real-valued parameters numerically and retain signed clock delays.
Keep MMCM/PLL outputs classified as generated clocks. BUFGCTRL input-to-output
propagation remains combinational, with CE/S checks against their documented
clock edges. Filter absent or constant reference clocks as in the serializer
callbacks. Reject uncharacterized configurations and speed grades.

The [native reset-arc query](../build/fedora-openxc7/vivado-clock-reset-semantics-20261012T003246Z/reset-arcs.tsv)
and [disabled timing report](../build/fedora-openxc7/vivado-clock-reset-semantics-20261012T003246Z/disabled-timing.rpt)
confirm seven Reg Set/Clr arcs are disabled by constraints in the characterized
vendor checkpoint. Retain them as explicit disabled records; do not import
their zero placeholders as real propagation delays. AMD documents the report's
constraint reason in [UG835](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/report_disable_timing).
MMCM reset is asynchronous and the block re-enables synchronously on release,
as specified in [UG953](https://docs.amd.com/r/en-US/ug953-vivado-7series-libraries/MMCME2_ADV).
This component import does not qualify board reset synchronization, clock
phase/family analysis or complete setup/hold timing.

The [clock backend](../build/fedora-openxc7/clock-vivado-timing-backend-20261012T003653Z/manifest.json)
compiled all 14 affected translation units with eight workers and passed
link/startup checks. All eight [native configuration cases](../build/fedora-openxc7/clock-vivado-timing-native-check-20261012T004052Z/manifest.json)
pass, including omitted defaults, alternate real-number formatting and tied
DCLK. Unsupported modes, nonfinite real parameters and the wrong speed grade
are explicitly rejected. The characterized cases match 204 port classes,
136 clock checks, 33 generated outputs, 68 propagation arcs and seven disabled
reset records. No disabled placeholder was exposed as an enabled delay.

The [complete design clock audit](../build/fedora-openxc7/full-clock-vivado-timing-native-check-20261012T004143Z/manifest.json)
then exited 0 with DSP, serializer, feedback and clock timing enabled. All
20 actual clock cells match: 294 port classes, 122 sequential checks,
20 generated output ports, 16 falling-edge checks, 54 propagation arcs and
10 explicit model records for the vendor-disabled reset arcs, zero mismatches.
The same native run rechecked all 358 serializers with zero mismatches.
Its [20-output period comparison](../build/fedora-openxc7/full-clock-vivado-timing-native-check-20261012T004143Z/period-comparison.json)
also passes. The original full implementation processes retain their binary.

Next, preserve static phase, duty cycle and clock ancestry through the actual
clock generators and buffers. The timing engine currently stops ancestry at
generated-clock outputs and assigns cycle budgets only when launch/capture
use the same clock net. Its domain-pair delay routine also selects the capture
domain for the launch variable; validate and correct that selection in the
isolated timing work. Compare same-clock, divided-clock, quarter-phase and
both-edge setup/hold paths with vendor reports, preserving unrelated clocks
and accounting for dynamic fine-phase controls. Kintex fabric calibration,
uncertainty/reset constraints and full routed timing remain unqualified.

The next isolated step extracts exact nominal waveforms before changing the
timing engine. Use rational picosecond periods, phases and high times so
fractional counters do not create spurious clock relationships after rounding.
Trace the selected MMCM/PLL input through unambiguous clock buffers and actual
I/O input cells. Keep the shared source root, configured phases, inverted
outputs, duty cycle and dynamic fine-phase group. Honor explicit primary XDC
waveforms. Preserve the previous default-off behavior and reject unsupported
option/part combinations. A missing source constraint or ambiguous clock mux
is an explicit unknown, not an invented period or clock family.

Audit every used clock reference in the complete accelerator, including
serializer strobes, and compare all 20 used generator outputs with the vendor
waveforms. Separate known nominal waveforms from unknown external clocks and
dynamic relative phases. Once these data pass, use exact clock-edge arithmetic
to validate setup/hold cycle budgets against vendor paths, then integrate those
budgets and the corrected launch-domain selection. Clock insertion/skew,
uncertainty, dynamic calibration and board timing remain separate requirements.

The corrected [waveform backend](../build/fedora-openxc7/clock-family-vivado-backend-20261012T013334Z/manifest.json)
rebuilds four changed translation units, with an eight-worker limit and no
class-header changes. It extracts waveforms after all DSP, serializer and
clock timing callbacks are initialized. Periods, high times and nominal phases
are rational picoseconds, preserving fractional counters. Explicit XDC source
waveforms and independent clock declarations on buffer outputs are retained;
missing or ambiguous sources remain explicit unknowns. Feedback must match the
characterized direct/buffered CLKFBOUT topology.

Eight [native waveform cases](../build/fedora-openxc7/clock-family-native-check-20261012T013626Z/manifest.json)
ran with eight workers. Baseline and shifted-source cases match all 33 connected
generator outputs in the constituent probes. The [actual shifted-source query](../build/fedora-openxc7/vivado-primary-clock-waveform-check-20261012T010951Z/clock-waveforms.tsv)
uses a 10 ns primary clock with 1.25/3.75 ns edges. Generated phases retain
the source's 1.25 ns offset, while MMCM output duty cycles follow their own
parameters. Inverted clocks are compared modulo their exact period.
Missing input constraints, ambiguous inputs and invalid feedback stay unknown;
invalid options and nonfinite primary waveforms are explicitly rejected.
Default-off behavior emits no waveform metadata.

The [complete accelerator waveform audit](../build/fedora-openxc7/full-clock-family-native-check-20261012T013712Z/manifest.json)
exited 0 on the unchanged source/profile/XDC with all intrinsic timing options
enabled. All 20 used generator outputs match the vendor periods, phases and
high times, share the actual SYS_CLK ancestor, and retain four fine-phase
outputs in the two write-MMCM groups. It inventories 39 clock nets: 38 known,
one unknown. Both sampler clocks are known and each has 792 API references,
proving their callbacks were initialized before extraction.

The remaining unknown is the raw BSCAN TCK before its buffer. The explicitly
constrained buffered TCK is known. An [independent control proof](../build/fedora-openxc7/full-clock-family-native-check-20261012T013712Z/unknown-clock-control-proof.json)
accounts for both raw-clock API references: the buffer's S0 and CE0 controls,
both tied to the packed VCC net. This does not invent a source-clock period or
claim full setup/hold qualification. The timing engine, clock insertion/skew,
uncertainty, dynamic phase calibration and complete routed paths remain pending.

The first fixture used an already-packed export whose constant-net markers
were not populated during re-packing; its failed comparison is preserved.
The corrected fixtures use the driven pre-pack input. An earlier complete
extractor run occurred before serializer initialization and recorded zero
sampler references. The initialization order and explicit buffer-clock
boundary handling were corrected; the latest full comparison requires positive
sampler references. All original full implementation jobs remain unchanged.

Phase-engine integration uses the exact waveform metadata to calculate the
smallest positive setup edge separation and the corresponding preceding hold
edge. Honor rising/falling edges, duty cycle and rational clock ratios. Only
clocks with a common source and identical dynamic-phase group have a known
relative phase; unrelated clocks and independently shifted groups stay unknown.
Keep clock insertion/skew qualification separate from these nominal budgets.

Add explicit per-domain-pair hold offsets and a known-phase flag, use the actual
launch domain in delay analysis, and update setup/hold slack, critical-path
requirements and duty-dependent same-clock Fmax reporting consistently. Gate
the changes with the xc7 opt-in setting and preserve default/non-xilinx behavior.
Rebuild every translation unit that includes the changed timing header from
recorded dependency files. Compare actual compiled analyser budgets against
the vendor register paths before auditing the complete accelerator. A pack-only
intrinsic analysis must be labeled as unplaced and cannot prove routed timing.

The [actual register-path query](../build/fedora-openxc7/vivado-phase-edge-paths-validated-20261012T021143Z/manifest.json)
now validates all 40 setup/hold edge relations across ten circuits and two
primary waveforms. Every declared MMCM parameter matches after normalizing
vendor boolean and Verilog-literal representations. The completed native query
was revalidated from unchanged RTL/Tcl and saved property/path files; it was
not rerun for the final format-only validator correction. Earlier validator
failures are preserved. A register's vendor startpoint is its clock pin C.

Examples are 625/-1875 ps setup/hold edge offsets for the forward quarter-phase
case, 1875/-625 ps in reverse, and 2500/-7500 ps for rising-to-falling capture
on the shifted primary clock's 25% duty cycle. The minimum positive difference
uses the exact rational clock-period GCD, before conservative integer-ps rounding.

The isolated [phase-engine backend](../build/fedora-openxc7/phase-engine-vivado-backend-20261012T022403Z/manifest.json)
rebuilt 16 translation units with eight workers: 13 timing-header dependants
from recorded dependency files and three changed Xilinx files. Compile, link
and startup passed. Its opt-in nominal budgets update setup/hold slack, path
requirements, same-clock duty-dependent Fmax and the setup-slack histogram;
delay analysis uses the actual launch domain. Existing insertion-delay behavior
is retained and remains numerically unqualified. Unknown or independently
shifted phase relationships receive no fabricated nominal budget.

Eight [native analyser cases](../build/fedora-openxc7/phase-engine-native-check-20261012T022527Z/manifest.json)
ran with eight workers and pass. Actual analyser budgets match all 40 vendor
edge relations. Missing source constraints, unrelated sources and dynamic
relative phases stay unknown; invalid options and audit-with-engine-off are
explicitly rejected. The test originally ran before the framework assigned
generic FF timing indices, yielding no domain pairs. Architecture timing data
are now assigned before nominal extraction and the explicit intrinsic probe.
The framework's normal later assignment remains idempotent.

The [complete accelerator intrinsic analysis](../build/fedora-openxc7/full-phase-engine-native-check-20261012T022758Z/manifest.json)
then exited 0 on unchanged full source/XDC/profile. Its actual analyser has
18 domain pairs: 14 known, two with dynamic relative phase and two with
unrelated sources. The smallest known setup budget is 5000 ps. This is explicitly
unplaced intrinsic analysis with routing-delay updates disabled only for that
probe; the temporary probe setting is cleared afterward. It does not establish
route/timing closure or an accepted image. The original implementations retain
their source and binary. Next: dynamic/CDC interpretation, insertion/skew and
uncertainty/reset constraints, Kintex fabric calibration, and full routed checks.

For the unresolved relationships, add an opt-in unplaced path export in a new
owned backend. Preserve the timing engine and upstream placed-report writer.
Export its actual CriticalPath segments, named cell types, source/ASYNC_REG
attributes and pin connections, without requesting locations for unplaced
cells. Reject this export unless the explicit post-pack phase probe is enabled.
Rebuild only the two changed Xilinx translation units with an eight-worker
pool; retain every other verified object and the original live jobs. Validate
the export against the existing vendor-edge fixtures, then run the same full
source/XDC analysis and require a path for every unresolved domain pair.
Use those paths to identify the relevant RTL and calibration/handshake limits;
do not substitute false paths for missing CDC or dynamic-phase evidence.

The isolated [path exporter](../build/fedora-openxc7/phase-path-vivado-backend-20261012T025000Z/manifest.json)
compiled its two changed Xilinx files, linked and started successfully. Eight
[native export cases](../build/fedora-openxc7/phase-path-native-check-20261012T025100Z/manifest.json)
passed, including unchanged vendor-validated nominal budgets and rejection of
an absent probe, an existing output and an unwritable output. The
[complete unchanged-design run](../build/fedora-openxc7/full-phase-path-native-check-20261012T025150Z/manifest.json)
exited 0 and exported 17 critical paths, including all four unresolved pairs.
It records cell types, parameters, source attributes and pin connections;
it does not enumerate every CDC endpoint or use placed geometry.

| Unresolved pair | Actual critical path | Required interpretation |
| --- | --- | --- |
| core falling to sysc0 rising | `u_ld.FDRE_72/Q` to `u_ld.OSERDESE2_9/D8` | Channel-0 command data; bounded calibration phase |
| core falling to sysc1 rising | `u_ld.FDRE_401/Q` to `u_ld.OSERDESE2_132/D8` | Channel-1 command data; bounded calibration phase |
| tck rising to core rising | `u_mailbox.req_toggle` to `rq_sync[0]/D` | First stage of the request toggle synchronizer |
| core rising to tck rising | `u_mailbox.rsp_toggle` to `rs_sync[0]/D` | First stage of the response toggle synchronizer |

The [CDC and phase review](../build/fedora-openxc7/full-clock-cdc-review-20261012T025800Z.json)
freshly verifies the original full packed-netlist SHA. Both three-register JTAG
chains are intact and clocked correctly. All six Q nets retain `ASYNC_REG=TRUE`;
the attribute is absent from the corresponding cell records. Its absence on a
cell alone therefore does not establish lost metadata. The current placer and
timing sources have no ASYNC_REG handling. Placement proximity, synchronizer
resolution time and held-payload timing still require explicit verification;
a worst toggle path does not cover all payload bits.

The actual DDR800 settings are 100 MHz sys and 800 MHz VCO, with both host and
generated firmware selecting WRAP=112. AMD
[UG472, interpolated fine phase shift](https://docs.amd.com/v/u/en-US/ug472_7Series_Clocking)
defines a step as 1/56 VCO period. The resulting operational interval is
-56 through +55 steps: -1250 through 34375/28 ps. The actual host controller
passed 25,088 mocked moves from every allowed initial position, including
936,544 intermediate shift writes, with no step outside that interval.
This checks software phase control, not MMCM behavior on the board.

For the traced falling-to-rising DDR command paths, the phase-only minimum
setup allowance is 3750 ps and the latest preceding hold edge is
-105625/28 ps. A conservative symmetric phase margin is 1250 ps; the donor's
default 1000 ps uncertainty is insufficient for this DDR800 wrap contract.
The current OpenXC7 XDC contains only its three primary clocks and no imported
uncertainty constraint. Raw phase CSRs do not enforce the software bound.
These numbers remain conditional on the supported calibration control flow,
and exclude clock insertion/skew, jitter and cell/route delays. At the path-review
stage no bound was imported into the engine and no timing exception was added.
The following integration addresses the phase contract; next, preserve and
constrain the actual synchronizers and held payloads, and qualify full routed
clock/reset timing and Kintex fabric delays.

The next integration uses an explicit JSON software phase contract, rather
than assuming all independently shifted clocks have a fixed relationship.
Validate generated-clock snapshots at -1250, 0 and +1250 ps with Vivado's
actual forward/reverse register paths and a common fine-phase-group path.
Preserve the exact source MMCM configuration; snapshots represent declared
clock waveforms, not measurements of a running MMCM. Import bounds only for
named MMCM groups with the expected clock root and exact device. Require the
phase engine to be enabled and keep absent, stale, malformed or unmatched
contracts explicit failures. Same-group shifts cancel; different bounded
groups use the full difference interval. If the interval crosses a capture
edge, retain an unknown relationship instead of inventing a positive budget.

The software contract yields conditional setup/hold budgets only. It must
remain distinct from routed skew, jitter and physical behavior, and raw CSR
writes remain outside its operating contract. Rebuild the three changed files
in a new owned backend with an eight-worker pool. Compare actual native domain
budgets and critical-path requirements against the vendor snapshots, including
default-off behavior, unknown sources, invalid contracts and edge-crossing
intervals. Then run the full unchanged netlist and require the two DDR command
pairs to gain conditional budgets while both JTAG source pairs stay unrelated.
Do not select the prototype for a full route until the other timing gates pass.

The [Vivado snapshot query](../build/fedora-openxc7/vivado-phase-bound-snapshots-20261012T031000Z/manifest.json)
exited 0. All 18 actual register setup/hold paths match the declared -1250, 0
and +1250 ps clock snapshots, including both directions and common-group
cancellation. All original MMCM parameters remain identical. The minimum
forward/reverse setup allowance is 3750 ps, and the latest preceding hold edge
is -3750 ps under the conservative symmetric bound. These are declared
generated-clock snapshots, not measurements of dynamic hardware. AMD
[UG835 create_generated_clock](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/create_generated_clock)
supports the explicit edge shifts used here. The first query failed because
`-master_clock` requires `-add`; the corrected single-source query omits that
option and preserves the failed output.

The latest [isolated backend](../build/fedora-openxc7/phase-bound-vivado-backend-20261012T032300Z/manifest.json)
rebuilt three affected translation units with an eight-worker pool and passed
compile, link and startup. Its optional `phase-bound-contract` JSON requires
the exact part, expected root, named MMCM, confirmed CLKIN1 selection and VCO,
finite integer bounds and an explicit software-only runtime assumption. Bounds
on a replayed input are cleared; a fresh contract must be supplied again.
The original source, objects and live native jobs remain unchanged. Same-group
shifts cancel; crossing a capture edge leaves the relationship unknown.

Eleven [native contract cases](../build/fedora-openxc7/phase-bound-native-check-20261012T032530Z/manifest.json)
ran with eight workers and pass. The actual analyser and exported path
requirements match the vendor envelope for the bounded forward/reverse cases.
No contract and stale input attributes keep those pairs unknown; zero bounds
preserve their nominal 5000/-5000 ps edges; oversized intervals stay unknown.
Wrong roots, unmatched groups, a stale VCO, fractional bounds, alternate source
selection and engine-off use are explicitly rejected. Common-group timing
remains 2500/0 ps.

The [complete unchanged-design run](../build/fedora-openxc7/full-phase-bound-native-check-20261012T032600Z/manifest.json)
then exited 0. Each write-MMCM contract matches four actual clock nets. The
18-domain analysis contains 14 unchanged nominal pairs, two conditional DDR
command pairs at 3750/-3750 ps and the two unchanged unrelated JTAG pairs.
Both conditional critical-path requirements match the vendor envelope; 17
critical paths are exported. These are unplaced, conditional software timing
budgets. They do not qualify route delays, clock insertion/skew, jitter,
synchronizer or held-payload timing, serializer reset arrival or board behavior.
No asynchronous exception was added and the prototype is not selected by the
live full route. Next: exhaustive CDC and reset constraints, insertion/skew
semantics and Kintex fabric/route delay comparison before a qualified full run.

For JTAG, inventory the entire packed mailbox, including every surviving held
request bit and response bit. Stream the full netlist, preserve source and
capture bit indices, verify direct source-Q to capture-D connections and
opposite clocks, and record every toggle-chain register and control fanout.
Require all identified bundled-data endpoints to have exactly one source.
Distinguish optimized-away fields from missing or unexpected crossings.
Derive a conservative datapath budget from the three-stage toggle protocol
and validate the earliest capture in simulation across clock phase offsets;
digital simulation does not model metastability. Keep the source payload held
until the supported one-outstanding-command handshake completes.

Retain synchronous timing between synchronizer stages. A later isolated
implementation must preserve their annotations/placement and enforce bounded
payload datapath timing, with per-endpoint coverage and vendor comparison.
The current XDC parser does not implement set_max_delay, so emitting that
command alone would not constrain an OpenXC7 implementation. Do not replace
this work with a broad asynchronous clock-group exception. AMD
[UG903 asynchronous signals](https://docs.amd.com/r/en-US/ug903-vivado-using-constraints/Constraining-Asynchronous-Signals)
describes datapath-only maximum delays for asynchronous crossings that require
a delay bound; setup/hold cell arcs and actual path coverage still need review.

The [complete packed mailbox inventory](../build/fedora-openxc7/full-mailbox-payload-inventory-20261012T035800Z/manifest.json)
now verifies every surviving direct bundled-data crossing: 572 request bits
and 531 response bits, 1103 total. Source and capture index sets match, each
has one source-Q to destination-D connection, and both registers use the
expected opposite rising-edge clocks. Request magic bits 572..603 are unused
downstream and optimized away; response magic bits 536..567 and constant
status bits 515..519 have no dynamic register pairs. All six synchronizer
stages retain their Q-net annotations. Each of the first two stages feeds only
the following register's D; only stage three escapes to consumer logic.

The [digital latency test](../build/fedora-openxc7/mailbox-cdc-latency-sim-20261012T035500Z/manifest.json)
passes 22 positive cases at eleven TCK phase offsets, with 17 transactions per
case and core completion delays spanning 0..16 cycles (one full TCK period).
It tests 20 ns request and 300 ns response payload delays, including differing
per-bit arrivals, full frames, backpressure and zero polls. The observed
minimum capture latencies are 30.010 ns and 500.831 ns. Both deliberately late
payloads are detected by the appropriate coherency check. The earlier echo
test did not span all response completion phases; its output is preserved.
Production RTL stays unchanged; the temporary simulation copy only inserts
consumer bus delays. This does not model analog metastability or prove routed
delays, source clock skew or jitter.

The [exact-part vendor pair query](../build/fedora-openxc7/vivado-mailbox-datapath-20261012T042500Z/manifest.json)
then exited 0 and validates all 1103 datapath-only requirements: 20 ns on
572 requests and 300 ns on 531 responses. It reconstructs the actual FDRE
pairs and initialization modes, with stand-in clock and enable ports; it is
not synthesis or placement of the complete parent design. Undefined INIT on
572 request-capture FDREs resolves to the primitive default zero, matching
the existing FASM writer. The earlier undefined-INIT validator failure and
the native-success/minimum-path validator failure are preserved.

The example vendor report includes 0.233 ns clock-to-Q, 0.189 ns unplaced net
delay and 0.093 ns capture setup; slack is 20 - 0.233 - 0.189 - 0.093 =
19.485 ns. Clock skew and jitter are excluded. AMD
[UG835 set_max_delay](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/set_max_delay)
documents this datapath-only calculation and its hold exception. Raw minimum
queries return false-path objects with infinite slack; adding
`-no_report_unconstrained` returns zero constrained hold paths. The original
zero-object assumption was too strict and was corrected from actual reports.

The [candidate mailbox contract](../build/fedora-openxc7/mailbox-cdc-contract-candidate-20261012T042800Z.json)
names all 1103 source/capture pairs and both three-stage synchronizers, retains
the packed source fingerprint and requires the one-outstanding-command hold
protocol. Native import is explicitly unimplemented. Next, implement per-endpoint
datapath delay enforcement, excluding clock delay contributions and including
source clock-to-Q and capture setup. Preserve normal synchronous setup/hold
between stages and constrain the three synchronizer registers together.
Compare actual compiled slack/path requirements and placement against the
vendor/component evidence, then re-audit every full-design endpoint. No broad
clock-group waiver or live-job modification has been made.

Implement synchronizer placement first in a new isolated backend. Validate
each named three-stage chain against packed FF types, rising-edge clock,
constant enable/reset, direct next-stage connectivity, Q-net ASYNC_REG and
absence of conflicting clusters or locations. The first two Q nets must feed
only the following D. Copy annotations onto the six cells and use upstream
relative cluster offsets 0/16/32. Restrict roots to primary A/B FFs in either
slice and verify every child stays in the same physical slice. Preserve the
existing carry/DSP cluster handling and timing engine; add no timing exception.

Rebuild only pack.cc and xilinx.cc with an eight-worker pool. Native probes must
exercise both slice sites, reject invalid topology/annotations/controls and
prove actual placement and routing. Then pack the full unchanged accelerator
and audit the two clusters plus unchanged phase-domain budgets. This imports
only synchronizer placement from the candidate contract; payload datapath
enforcement remains separate and cannot be claimed from a placement pass.

The [synchronizer placement backend](../build/fedora-openxc7/mailbox-sync-backend-20261012T050000Z/manifest.json)
rebuilt pack.cc and xilinx.cc with an eight-worker pool; compile, link and
startup passed. It validates each chain against the actual packed cells,
constant controls, positive-edge clock, Q-net annotations, direct links and
early-stage fanout. It copies ASYNC_REG onto the six cells and creates two
relative clusters. Its placement callback permits only primary A/B roots and
requires all three members to stay in the same physical slice. Existing carry
and DSP placement paths and the timing engine are retained.

All eight [native cases](../build/fedora-openxc7/mailbox-sync-native-check-20261012T050300Z/manifest.json)
pass: default-off, cluster packing, two completed routes and four explicit
topology/annotation/clock/fanout rejections. Actual routes place the request
chain at SLICE_X1Y397/X1Y399 and the response chain at SLICE_X0Y392/X0Y395,
with each using A/B/C primary FFs. Both slice sites are therefore exercised.
These use stand-in LUT clock sources and are architecture placement/routing
probes, not functional board images or full-design timing qualification.

An initial build failed on Property string conversion and indexed-store
access; corrected source and failed output are preserved. The first fixed-root
probe used physical site/BEL names where the existing preplaced reader expects
internal tile/BEL names, causing an exception before packing. An isolated
GDB reproduction identified that mismatch. The successful probes use normal
placement with two seeds; no live process or preplaced implementation was
changed. A read-only chipdb lookup maps, for example, SLICE_X0Y225/AFF to
X10Y181/SLICE_X0Y0.AFF. This is a probe-input correction, not a replay feature fix.

The [complete unchanged-design pack](../build/fedora-openxc7/full-mailbox-sync-pack-20261012T050430Z/manifest.json)
then exited 0. A direct C++ audit records all six actual cluster parents,
children and offsets 0/16/32, plus cell-level annotations. The normal pack-only
JSON omits those cluster fields, so the explicit audit provides the evidence.
All 18 phase-domain budgets are unchanged, including both conditional DDR
pairs. Full physical placement/routing of the new clusters remains pending.
Only the synchronizer portion of the candidate contract is imported; all 1103
payload datapath limits still need native timing enforcement. No timing
exception was introduced and all original full implementation jobs retain
their source and binary. Next: enforce and audit the per-endpoint datapath
limits, then complete clock/reset and Kintex timing qualification for a full run.

For native payload timing, support only the verified direct FF-Q to FF-D pairs
in this contract. Validate exact part, positive-edge clocks with different
known roots, direct connectivity, unique source/capture mapping, normal
synchronous FF modes and the explicit held-payload protocol. Require the
phase engine and clear stale imported payload tags before processing a fresh
contract. Keep synchronizer input/stage timing outside these payload tags.

Apply each maximum to both the source-Q and capture-D timing records using
clock-to-Q plus data route plus capture setup, excluding clock route and
clock-to-clock contributions. Include violations in placement/router slack
and criticality; report the same requirement on critical paths. Do not change
nominal phase-domain budgets or manufacture a phase relationship between
unrelated clocks. Export every bound endpoint's actual analyser slack.

In explicit unplaced probes, inject data and clock route delays to test data
delay sensitivity, clock-delay invariance, positive criticality on violations
and truthful path requirements. This validates timing semantics while existing
generic FF numerical data remain unqualified. Compare requirements with the
1103 vendor pair records and audit all full-design endpoints, including the
two synchronizer clusters and unchanged nominal/conditional phase budgets.
Rebuild only timing.cc, pack.cc and xilinx.cc; no timing class layout changes
are needed. Preserve default/non-xilinx behavior and every live original job.

The [isolated datapath backend](../build/fedora-openxc7/mailbox-datapath-backend-20261012T053500Z/manifest.json)
rebuilt timing.cc, pack.cc and xilinx.cc with an eight-worker pool; compile,
link and startup pass. The optional importer validates the direct FF pairs,
known independent roots, positive edges, FDRE modes, unique mappings and the
held-payload protocol. It rejects synchronizer tags and related-clock paths.
Stale payload tags are cleared unless a fresh contract is validated.
Activation also requires process-local Context validation, so serialized flags
alone cannot enable a limit when packing/validation is skipped. Its initial
pointer-pool build error was corrected to a standard pointer set; failed
artifacts are preserved.

For each imported pair, source-Q and capture-D slack use the declared maximum
minus clock-to-Q, cached data-route delay and capture setup. Clock route and
clock-to-clock contributions are excluded. Violations drive source/capture
criticality even though the nominal clock relationship stays unrelated.
Critical-path requirements and segments use the same maximum and cached route
delay. No phase-domain budget is changed and normal synchronizer stage timing
remains outside these tags. The importer is limited to the verified direct
pairs, not a general XDC maximum-delay implementation.

Eleven [native semantic cases](../build/fedora-openxc7/mailbox-datapath-native-check-20261012T053700Z/manifest.json)
pass. Injecting 40000 ps of data route reduces slack by exactly 40000 ps;
100000/25000 ps of source/capture clock route changes neither slack nor
criticality. A request violation has -20450 ps slack, criticality 1 at both
ends and a truthful 20000 ps path requirement, without clock segments.
Default-off and stale-input cases retain no payload tags. Related roots,
wrong nets, fractional maxima, duplicate pairs and synchronizer-tag attempts
are rejected. The FF model still uses provisional 350 ps clock-to-Q and
100 ps setup, so these are semantic tests and do not calibrate Kintex FFs.

The [complete unchanged accelerator](../build/fedora-openxc7/full-mailbox-datapath-check-20261012T053800Z/manifest.json)
then exited 0 with every endpoint audited: 572 maxima of 20000 ps and 531 of
300000 ps. Source and capture slacks agree, both synchronizer clusters are
unchanged and all 18 nominal/conditional/unrelated phase budgets are unchanged.
The minimum intrinsic slack is 19550 ps with explicitly zero data-route delay.
This validates full endpoint coverage and constraint application; it does not
prove routed slack or physical CDC behavior. The latest complete run used the
same process-validation backend and final eleven-case gate.
All original complete implementations retain their source and binary.
Next: Kintex FF/fabric numerical calibration, clock insertion/skew/jitter and
serializer reset constraints, then a qualified full placement/route and image.

The next calibration step inventories every SLICE_FFX in the same pinned full
packed export. The read-only scan found 179299 registers: 177176 rising FDRE,
402 falling FDRE, 1701 FDSE, 16 FDCE and four FDPE. No latch or data/reset
inversion occurs. Preserve all named registers and their effective clock edge,
reset mode, original port mapping and INIT distribution in the inventory.

Query Vivado for these five modes with both INIT values, initially unplaced
and then explicitly placed into AFF/BFF/CFF/DFF and A5FF/B5FF/C5FF/D5FF, in
both SLICEL and SLICEM at five distributed site samples. Use actual placement
and verify the resulting BEL object; LOC constraints alone are insufficient
evidence of placement. The documented command is
[place_cell](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/place_cell).
Use stand-in data/control inputs to keep every primitive and timing pin live.
These are intrinsic timing probes, not parent-design implementation or images.

Retain all fast/slow, min/max and rise/fall corner values, negative holds,
transition metadata, disabled arcs and recovery/removal/set-clear arc types.
Compare the raw records across INIT, position, site and primary/secondary BEL
before selecting an import rule. Do not replace an asynchronous control with
an invented synchronous check or zero delay. Record unsupported placement or
arc semantics explicitly and leave native import pending until resolved.
Parameter, coverage and finite-data checks must pass before importing tables.
Preserve every live complete implementation and its source/binary. Vivado and
independent calibration checks may use eight workers; no scope is reduced.

The [complete FF inventory](../build/fedora-openxc7/full-ff-timing-inventory-20261012T054200Z/manifest.json)
passed for all 179299 named registers and five modes. The
[validated vendor query](../build/fedora-openxc7/full-ff-vivado-timing-validated-20261012T055100Z/manifest.json)
passed 810 measurements: ten unplaced and 800 real placements, both INIT
values, two slice types, eight FF BEL positions and five distributed samples.
Actual BEL objects match every requested position; parameter and finite-data
checks have zero mismatches. All 5994 raw arcs are retained, including 324
recovery, 324 removal and 324 explicit vendor-disabled set/clear records.

The first validator rejected valid single-transition asynchronous arcs and
the site-qualified BEL property representation. Those failed validations
are preserved. Corrections validate the applicable transition only, retain
the vendor disable flags and compare both qualified BEL and actual BEL
object. They reuse immutable native-exit-0 query output; no synthesis or
physical query was repeated merely to fix the validator.

[Location-specific tables](../build/fedora-openxc7/ff-location-timing-tables-20261012T055500Z/manifest.json)
then passed 85 mode/location comparisons: 80 placed classes plus five
unplaced classes, 629 arc records and 34 explicit disabled records. All ten
INIT/position measurements within each placed class agree. Across classes
the numerical values differ, so importing one generic value is insufficient.
Fast/slow and min/max values, negative setup/hold values and missing opposite
transitions remain explicit. Native callbacks, asynchronous-control engine
semantics and path comparisons are pending; these tables do not yet replace
the provisional numerical values or qualify full routed timing.

The concurrent [router review](openxc7_router_review.md) found upstream PR 81,
missing from our backend, and 68 newer commits. Preserve current jobs and
test the upstream BUFGCTRL route guard in a fresh backend before accepting
an image. General router2 code has not changed in that upstream comparison.

Before FF callback import, reconcile a concrete numerical discrepancy: the
stand-alone unplaced FDRE data-setup arc has slow max 15 ps, while the earlier
direct mailbox report uses a 93 ps setup check. The CQ value is 233 ps in
both. Re-open the immutable mailbox and FF characterization checkpoints,
query the same cells before/after timing update and path extraction, and
export timing-arc, path and pin properties. Compare actual checks rather than
assuming the raw arc query equals the path contribution. Use
[update_timing](https://docs.amd.com/r/2021.1-English/ug835-vivado-tcl-commands/update_timing)
explicitly; AMD documents automatic updates for commands needing timing data.
For the five used FF modes, exercise data, enable, synchronous reset/set and
asynchronous recovery/removal paths with stated stand-in input/output timing.
Retain sparse transitions and vendor-disabled preset/clear propagation.
Any context/slew dependence must be quantified before an import rule is
selected. Keep existing tables, checkpoints and live jobs unchanged.

### FF path/context result, 2026-10-12 15:36 HKT

The immutable mailbox and five-mode FF checkpoints were queried without
resynthesis. [Context query](../build/fedora-openxc7/ff-path-context-vivado-20261012T065400Z/manifest.json)
completed 222 real path queries; the [controlled driver query](../build/fedora-openxc7/ff-driver-context-vivado-20261012T070700Z/manifest.json)
completed 50 more. The [independent comparison](../build/fedora-openxc7/ff-path-context-validated-20261012T073850Z/manifest.json)
matches all 262 finite path contributions to raw vendor arcs, including
99 setup, 87 hold, eight recovery, eight removal and 60 clock-to-Q checks.
Ten min paths under datapath-only exceptions are explicitly ignored: Vivado
reports infinite slack and False Path, with empty corresponding TSV properties.
They are not successful hold checks.

For the same unplaced rising FDRE, its immediate D driver changes slow-corner
setup/hold checks: primary input 15/115 ps, FF Q 93/52 ps, LUT O -43/162 ps.
Fast-corner values are -10/44, 62/-13 and -40/69 ps respectively. Negative
values are retained. Full timing updates and path extraction leave raw arcs
unchanged in the same context. Reset/set case analysis does not change D
checks. Datapath-only exceptions do not change intrinsic checks; changing
the LUT's upstream source from FF Q to a primary input does not change the
capture checks. The immediate logical driver is therefore a demonstrated
context factor. Physical pin and routing-boundary interpretation remains
unproven and is not encoded as a backend rule.

The [complete control inventory](../build/fedora-openxc7/full-ff-control-context-inventory-20261012T065100Z/manifest.json)
covers 179,299 FFs in ten mode/control groups. The [complete D-driver inventory](../build/fedora-openxc7/full-ff-data-driver-inventory-20261012T071400Z/manifest.json)
covers the same cells in 184 mode/driver/port groups and 13 driver types;
108,629 D inputs are FF-driven and 51,204 LUT-driven. Remaining inputs come
from carry, DSP, BRAM, SERDES, clocks, IO, JTAG, constants or selection muxes.
There are no unknown or conflicting drivers.

The existing 85 location/mode tables remain valid for their original
port-driven probes, but are insufficient as universal FF native models.
Native callback import awaits qualified driver and physical pin coverage.
The existing generic FF model and all three original full jobs are unchanged.
These results qualify this vendor comparison, not full routed timing or hardware.

Next, open the completed full Vivado reference `routed.dcp` read-only.
Inventory every actual FDRE/FDSE/FDCE/FDPE data driver and its placed BEL.
Group by primitive, clock inversion, capture BEL, driver primitive/port and
whether the driver shares the capture site. Query up to three actual cells
per group, retaining their routed physical BEL/site-pin mappings and max/min
data paths. Compare effective path checks with each selected cell's raw arcs.
This supplies real routed context evidence; it does not equate the MIG
reference netlist with the distinct LiteDRAM/OpenXC7 netlist or automatically
qualify a universal native callback. Retain the immutable checkpoint hash,
all inventory names, missing/ignored paths, native exit and raw artifacts.
Do not synthesize, route, modify the reference checkpoint or touch hardware.

### Completed routed reference comparison

The [native query](../build/fedora-openxc7/full-ff-reference-context-20261012T075300Z/manifest.json)
exited 0. Its checkpoint hash matches the completed MIG image's offline
qualification record. All **112,352** actual reference FD* cells are inventoried:
111,533 FDRE, 670 FDSE, 141 FDPE and eight FDCE. There are 1,985
mode/BEL/driver/port/site groups and 4,002 selected actual cells, with up to
three samples per group. The raw IS_C_INVERTED property is retained as
DEFAULT when absent; no implicit inversion is invented from its empty value.
Physical D BEL mappings and routed site pins are retained for every sample.
Logical GND/VCC drivers are identified as constants, with no fabricated BEL.

The [independent comparison](../build/fedora-openxc7/full-ff-reference-validated-20261012T100700Z/manifest.json)
checks all 8,004 max/min path queries: **7,901 finite checks match** the
sampled cell's raw vendor arcs; 70 have no timed path and 33 are explicitly
ignored False Paths. Zero finite comparisons mismatch. These missing/ignored
paths are retained and do not prove successful setup or hold checks.

**522 groups have more than one numeric setup/hold signature**, despite
sharing the selected primitive/BEL/driver/port/site grouping. Thus neither
those group keys nor the earlier port-driven tables establish one universal
FF timing model. The extra numerical dependence is observed; its physical
or electrical cause is not yet established. Native callback mapping and
context coverage remain pending. This reference contains MIG and different
optimization results; its 112,352 cells are not the OpenXC7 mapping's 179,299.

The first native export was retained as a failure: a high-fanout net exceeded
Vivado's 500-item text-conversion limit. The completed revision sets the
documented tcl.collectionResultDisplayLimit to zero and retains all entries.
No reference checkpoint, RTL, live original job, FPGA SRAM or flash changed.
