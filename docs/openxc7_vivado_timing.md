# Vivado timing data for OpenXC7

## Full native FF absolute placement, October 13 23:02 HKT

The full preserved placement now has an absolute site/BEL inventory for all
**179,299 registers**, across **60,533 occupied slices** and **60 observed
primitive/edge/site-type/BEL classes**. All classes have entries in the existing
location-specific characterization table; their numerical applicability to
routed cells remains unqualified.

The collector reads the pinned chipdb v6 site metadata and BEL-in-site fields,
checks the schemas/constids against the image preparation, and cross-checks
**all 597,200 fabric FF BELs in 74,650 slices** against the pinned X-Ray grid.
It does not infer absolute site coordinates from the native relative BEL label.
Every occupied FF retains its exact native BEL, primitive, edge and reference
identity. Primary and secondary FF BELs are included. The full mode counts and
all 4,810 selected reference samples agree with the earlier inventory.

An independent review checks every emitted record against the original
placement TSV, reference identity map, X-Ray tile/site kind and characterized
location-class key. Corrupt-grid checks reject wrong slice type, a missing
slice site and a duplicate absolute site. Both native jobs exit 0. The live
route's PID/start and service invocation remain unchanged.

This completes absolute **placement location** coverage. The routed D-input
mux/path, slew/load dependence, clock insertion/skew, asynchronous control
semantics and full numerical model qualification still need to be resolved.
The 174,489 FFs without selected reference arc measurements remain unsampled.
No tables were imported and the running backend was unchanged. Terminal routed
bindings must agree with the preserved placement before this inventory is used.

[Full absolute-site inventory](../build/fedora-openxc7/full-ff-absolute-sites-20261013T150000Z/manifest.json),
[all-record independent review](../build/fedora-openxc7/full-ff-absolute-sites-review-20261013T150200Z/manifest.json),
[actual service exits](../build/fedora-openxc7/full-ff-absolute-sites-review-20261013T150200Z/native-service-exits.json),
[collector](../tools/openxc7_ff_placed_sites.py).


## Complete native/reference FF correspondence, October 13

An independent stream of the full native packed export now verifies all
179,299 FF identities, primitive modes, clock polarities and 896,495 port
mappings against the completed matched-reference inventory. The five actual
modes are FDCE0 (16), FDPE0 (4), FDRE0 (177,176), FDRE1 (402), and FDSE0
(1,701). DEFAULT inversion values are checked against the installed Vivado
primitive library declarations; duplicate/missing identities and unsupported
port maps are rejected. Every selected sample maps to a native cell.

This completes logical correspondence, not native physical input-mux or
routing coverage. Only 4,810 cells have selected reference arc measurements;
174,489 are not individually sampled. Native placement/routed metadata and
model coverage remain required before import. The running backend retains
its existing timing tables. The preplaced replay option closes all touched
FPGA tiles to unlisted cells; an FF-only replay would also exclude unlisted
LUTs/other cells from those tiles and is not a complete placement transfer.

[Full mapping audit](../build/fedora-openxc7/full-ff-native-reference-map-20261012T232714Z/manifest.json),
[current goal evidence](../build/fedora-openxc7/goal-full-native-ff-correspondence-20261012T233618Z/manifest.json).


## Complete same-input FF measurement review, October 13 07:17 HKT

The full routed reference query completes with native exit 0: 179,299 FFs,
1,988 logical groups, 4,810 selected samples and 9,620 max/min queries.
Independent comparison matches all 9,550 finite path contributions with
zero mismatches. It preserves 58 missing timed paths and 12 unconstrained
external-boundary queries as unvalidated, without inserting requirements or
zero delays. Those 12 queries cover BSCANE2 TDI and the five sensor/I2C input
pins. The classifier checks exact inventoried driver/source/endpoint,
reference provenance, capture clock/period and absent vendor requirement.
Seven corrupt-scope cases are rejected; legacy MIG comparison outputs remain
byte identical. The failed initial follow-up and comparator receipts remain.

Physical regrouping covers all 4,810 selected samples in 2,891 physical
contexts. Its 1,277 repeated groups cover 3,196 samples, with zero conflicting
raw signatures within those observed groups. Singleton and unsampled native
contexts are not proven universal; electrical dependence, native physical
mapping, complete native coverage and model import remain pending. The live
backend retains its existing provisional generic FF numbers.

[Query receipt](../build/fedora-openxc7/full-mapped-ff-bounded-20261012T192600Z/manifest.json),
[finite comparison](../build/fedora-openxc7/full-mapped-ff-reviewed-boundaries-20261012T231300Z/manifest.json),
[physical regrouping](../build/fedora-openxc7/full-mapped-ff-physical-context-20261012T231500Z/manifest.json),
[complete evidence](../build/fedora-openxc7/goal-full-ff-reference-complete-20261012T231726Z/manifest.json).

Earlier sections below describe the acquisition and intermediate states.

## Full-reference regrouping and automatic follow-up, October 13 04:25 HKT

The waiting controller was replaced after an exit-contract mismatch was
found: this bounded collector writes `native.exit`, while the first
controller expected `query.exit`. The corrected actual gate is exercised
with native-zero, native-failed, running, failed-query and missing-native-file
cases; a zero legacy file alone is rejected. Only the idle controller was
intentionally stopped, with exit 143; the collector and all route jobs
remain unchanged.
[Exit-contract verification](../build/fedora-openxc7/ff-followup-native-exit-verification-20261012T203416Z/manifest.json).

`openxc7_ff_physical_context.py` now validates the full sample scope from
the completed query and independent comparison receipts. The earlier
hardcoded 4,002-sample MIG requirement is removed; exact FF, group, sample
and max/min counts remain mandatory, with duplicate/missing sample checks.
Its CSV reader preserves the current full-design site-pin fields with the
same 64 MiB field limit as the collector and independent comparator.

The original complete MIG study is replayed with all four numerical output
files byte identical. Wrong sample counts, duplicate sample identifiers and
missing samples are rejected before creating output. The current closed
179,299-FF inventory and all 4,810 sample records also parse, including a
2,272,533-character field.
[Verification receipt](../build/fedora-openxc7/ff-regroup-scope-verification-20261012T202355Z/manifest.json).

The full query has 1,531 / 4,810 completed sample pairs. A separate controller
in tool session 94785, PID 339438/start 18825931, waits for that exact existing
query's completed native receipt, requires the unchanged core100/dualDDR800
profile and all 9,620 path queries, and then runs the full independent
comparator followed by physical-context regrouping. It pins seven local
helper modules and records actual stage exits. It does not restart the
collector, change native route jobs, access hardware or import a model.
[Controller receipt](../build/fedora-openxc7/full-ff-reference-finish-native-exit-20261012T203358Z/manifest.json).

The new regroup status is
`ALL_REFERENCE_SAMPLES_PHYSICAL_CONTEXT_REGROUP_COMPLETE_MODEL_UNQUALIFIED`.
The earlier nine-sample physical query helper still requires its original
MIG receipt and selected cell identifiers; do not use that helper on the
new mapped-input groups. Any remaining variation must be investigated using
the actual new group members before numerical import is qualified.

## Complete same-input reference FF contexts, October 13

The completed full mapped-input Vivado reference now provides the actual
core100/dualDDR800 accelerator checkpoint, rather than the earlier DDR1066
MIG architecture used for the previous FF context study. Query every routed
fabric FF with the existing `openxc7_ff_reference_context.py` helper, retain
its full inventory and take three samples per actual mode/driver/BEL group.
Compare raw arcs with finite max/min timing-path contributions using the
existing independent comparator. Preserve all measured variation and missing
or explicitly ignored paths; do not fit a universal model from a subset.
This is a read-only numerical-reference step for the remaining provisional
OpenXC7 FF model. It preserves both completed Vivado images, full dimensions
and frequencies, and all running native routes. Use eight threads.

The selected immutable checkpoint is
`full-mapped-vivado-bitstream-top-20261012T183600Z/final-routed.dcp`,
141,153,976 bytes, SHA256
`95e7b7df67a501ee06d771dabcae07478fba41c1280826d26987db2b0c0a4680`.
Its completed native image manifest retains the full original profile.
Numerical import into OpenXC7 remains pending actual complete comparison
and route-dependent coverage; this query does not touch FPGA hardware.

The full inventory completes with 179,299 FFs, 1,988 groups and 4,810 samples
(9,620 max/min queries). The first 97 completed pairs have median 0.163 s
between max/min report writes and 3.688 s between successive samples.
The broad snapshot enumerates unrelated AIE and hierarchy-only properties
on ordinary Kintex-7 FF pins, producing repeated unsupported-property
warnings. Prepare a bounded collector that preserves the complete closed
inventory/sample files, every raw timing-arc property and every selected
max/min report, while retaining the meaningful cell/pin electrical and
mode fields rather than unrelated GUI/device-family metadata. Record the
intentional stop of only this owned broad-property query; preserve its
partial measurements and all four original route jobs. Compare the bounded
collector's first completed measurements with the original raw arcs and
path summaries before accepting its completed full result.

The bounded collector is implemented in `openxc7_ff_reference_bounded.py`.
The old query's native exit records an intentional SIGTERM, not a design-fit
failure; its full closed inventory and 181 completed sample pairs remain.
The new query reuses those exact inventoried cells and all 4,810 selected
samples, preserving every raw timing-arc property and both path reports.
Its reader and the independent full comparator now allow the actual large
site-pin lists, with a bounded 64 MiB CSV field limit and no truncation.

The first 20 real samples reproduce 140 raw arc records, 2,240 semantic/
numerical properties and all 40 max/min path summaries exactly. Their
paired receipt is `bounded-ff-prefix-pass-20261012T193926Z`; median original
sample interval is 3.927 s and the bounded collector's measured median is
2.3065 s, about 41% less time. This is a prefix comparison and a measured
collector improvement, not full-model qualification. The complete query
continues in `full-mapped-ff-bounded-20261012T192600Z`, controller session
56447, native PID 328931/start 18431165. At the latest goal review it has
1,531 of 4,810 sample pairs. Run `openxc7_ff_reference_compare.py` on the
actual completed query and retain all context variation before any import.
Both full Vivado images, all 31 sources and all four native route jobs
remain unchanged. Physical testing still awaits USB/JTAG visibility.
[Current goal evidence](../build/fedora-openxc7/goal-bounded-ff-query-20261012T194152Z.json).

Full Vivado 2026.1 exposes `get_speed_models`, `get_timing_arcs` and
`report_timing`, which the earlier Lab 2026.1.1 installation lacked. Actual
part-library queries completed with native exit 0 for `xc7k480tffg1156-2` on
October 12, 2026. The raw numerical data are now available; they have not been
imported into the running backend or qualified as its complete timing model.

| Model family | Raw models exported |
| --- | ---: |
| DSP48E1 | 86,302 |
| MMCME2_ADV | 190 |
| ISERDES | 113 |
| OSERDES | 70 |
| Supporting ILOGIC | 163 |
| Supporting OLOGIC | 186 |

All exported `DELAY`, `FAST_MIN`, `FAST_MAX`, `SLOW_MIN` and `SLOW_MAX` fields
parse as finite numbers. Some values are negative and require their actual
arc semantics. A finite value alone does not prove its interpretation or its
applicability to a particular cell configuration.

The first physical BEL searches for logical names `ISERDESE2` and `OSERDESE2`
returned zero matches. Those original results are preserved. A subsequent
query discovered the physical ILOGIC/OLOGIC resources, including IFF, OUTFF
and TFF BELs, and exported serializer models using the vendor's model-name
patterns. No artificial zero-delay serializer models were inserted.

The complete, hash-verified 452,692,109-byte pre-LUT checkpoint contains all
717 DSP48E1 cells. An inventory resolving its declared vendor defaults found
13 distinct register/input profiles and 143 cells with `PREG=0`. This extends
the earlier inventory of explicit RTL DSP instances to include synthesized
DSPs. Timing must account for these actual configurations and mixed registered
and combinational paths.

Grouping every declared parameter, including control registers and inversions,
produces 15 complete configurations. A subsequent native Vivado query
instantiated every one on the exact part, completed with exit 0, and captured
122,150 timing arcs. Comparison of all declared parameters against Vivado's
actual cell properties found zero mismatches, and every recorded delay is
finite. Several `PREG=0` configurations have both clock-to-output and
combinational paths on 104 output pins; some input pins likewise have both
setup/hold checks and combinational paths. The existing timing engine supports
these combinations through its separate sequential and combinational APIs.
Backend integration and complete numerical qualification remain pending.

The first derived semantic summary missed combinational pin sets because it
expected uppercase `Combinational`; the vendor's TYPE is lowercase. The
original summary is retained, and `semantic-summary-v2.json` corrects those
sets. Original parameters, arc counts, TYPE values and numerical data were
unaffected. The raw query also retains warnings from reading unrelated
OOC-incompatible cell properties; the actual DSP parameter comparisons pass.

An eight-worker preparation now emits exact-configuration packed-pin timing
tables in integer picoseconds. The 122,150 table arcs cover all 717 source DSPs;
an independent pass over the original vendor property TSV found zero bound
mismatches. The converter retains all fast/slow rise/fall corners and mixed
sequential/combinational pin behavior. The 18 standalone converter tests pass.
These tables are ready for integration into a separate backend; the live
backend has not imported them.

The first preparation incorrectly assumed that fast-min would always be below
slow-max. It stopped with exit 1 on valid signed hold checks and is preserved
under `full-dsp-timing-tables-20261011T220934Z/`. There are 998 such hold arcs.
The corrected preparation retains each corner and derives an envelope across
both. For example, a PCIN hold check keeps fast -78 ps and slow -330 ps, with
an envelope of [-330, -78] ps. No negative requirement was clipped to zero.

A separate opt-in backend now compiles these source-configuration tables.
All 14 header-dependent translation units rebuilt with eight compiler workers;
compile, link and startup exits are 0. Its actual native callbacks match all
15 source configurations: 6,255 port classifications, 3,489 sequential pins
and 117,024 combinational arcs, with zero mismatches. Omitting 287 declared
defaults produces the same results. Default-off behavior passes, and unsupported
modes and the wrong speed grade produce the expected explicit native exit 125.
These are constituent callback checks, not full-board path qualification.

A subsequent complete OpenTPU pack-only export also exited 0 and produced a
1,704,613,926-byte packed netlist. Streaming all 464,200 packed cells confirmed
the same complete set of 717 named DSPs. Packing changed
`IS_CARRYIN_INVERTED` from 0 to 1 on every DSP and added per-bit ALUMODE,
INMODE and OPMODE inversion flags. The existing FASM writer ORs those flags
with the declared bus masks. Applying that exact rule yields 19 effective
vendor configurations, covering all 717 DSPs. The 15 source configurations
are therefore insufficient for the actual packed timing model. Characterize
the 19 effective configurations next, then implement the same mask resolution
in the isolated backend's signature matcher.

The first callback fixture removed external I/O and inadvertently left its
DSP inputs undriven. Constant packing changed its parameters, so the model
correctly rejected it. The corrected fixture uses 3,931 fabric driver LUTs
to retain the reference parameters while avoiding external I/O placement.
Both the original rejection and corrected results are preserved. This fixture
does not replace the complete packed-design inventory or qualify its timing.

Vivado subsequently characterized all 19 effective packed configurations with
native exit 0, zero parameter mismatches and 152,458 timing arcs. The updated
eight-worker converter verified every bound against the original vendor TSV.
A new isolated backend applies the same per-bit bus-mask rule as FASM. All
19 actual configuration checks pass, including 7,923 port classifications,
4,415 sequential pins and 145,910 combinational arcs. Aggregate masks, split
packer flags and omitted defaults produce identical results; malformed flags,
unknown modes and an uncharacterized speed grade are explicitly rejected.

The complete unchanged OpenTPU input was then packed with that backend and
the timing option enabled. Native exit 0 and an independent comparison against
the original full packed netlist confirm all 717 named DSP assignments. The
actual callbacks match 254,649 port classifications, 177,541 sequential pins
and 1,842,120 combinational arcs, with zero mismatches. The complete 4x4/8-lane,
100 MHz core and both DDR800 channels were retained. This validates the DSP
callbacks on the actual accelerator; it does not qualify full-board timing or
replace the still-live original implementation.

The same complete packed netlist now supplies the remaining PHY and clock
parameter inventory: 144 ISERDESE2 cells in one configuration, 214 OSERDESE2
cells in two, three MMCMs in two, one PLL configuration and 16 BUFGCTRLs in
one. Characterize those actual configurations and their clock relationships
next; they have not been integrated as complete timing models.

All seven PHY/clock configurations have now been queried with full Vivado on
the exact part. After correcting HR site selection and feedback/default
compensation, the native query exited 0; all parameters match and all 376
timing arcs are finite. It also exports generated-clock properties, including
the 400 MHz clocks' 0.625 ns quarter-period offset. Existing clock derivation
loses that phase and assigns VCO-rate feedback periods where Vivado reports
input-rate feedback clocks. These remain implementation and path-validation
requirements. Multi-clock serializer checks and clock-generator reset arcs
are preserved, not replaced with zero-delay models. See the [PHY timing plan](openxc7_phy_timing_plan.md).

An isolated opt-in clock-feedback correction now traces buffered feedback and
uses feedback-counter periods. Its full-design pack and independent period
comparison passed all 20 used clock outputs across the four generators. A
full-design off-mode control reproduces the original incorrect direct feedback
periods and missing buffered feedback constraints. The corrected source is
unselected for the active route; generated-clock phases/families and remaining
clock intrinsic/reset semantics require implementation and path validation.

Serializer intrinsic callbacks are now implemented in a further isolated
opt-in backend. All 14 affected files rebuilt with eight compiler workers;
eight independent native cases pass. The complete unchanged design then
packed and audited with native exit 0: all 358 serializers match their expected
three modes, with zero differences from the raw vendor reference across
6,174 port classifications, 4,746 sequential checks, 288 falling-edge checks
and 162 combinational arcs. Shared CLK/CLKB sampling, CLKDIV checks, signed
corner bounds, missing/tied-clock filtering and hybrid outputs are preserved.
All 20 used clock output periods still match. These are verified intrinsic
callbacks; clock families/phases, uncertainty, fabric data and complete routed
paths remain unqualified. The live full route retains its original backend.

A further isolated clock backend now imports all 287 enabled MMCM/PLL/BUFGCTRL
arcs from the remaining four groups. Seven constraint-disabled Reg Set/Clr arcs
remain explicit records, with no fabricated propagation delays. All eight
native configuration cases pass. The complete unchanged design also passes:
20 clock cells, 294 port classes, 122 sequential checks, 20 generated outputs,
16 falling-edge checks and 54 propagation arcs, zero mismatches. The same
native run revalidates all 358 serializers, and all 20 used generator periods
still match. Clock ancestry, phase/duty relationships, dynamic fine-phase
behavior and complete routed path qualification remain pending.

Nominal waveform extraction now passes on the complete unchanged accelerator.
All 20 generator outputs match the vendor period/phase/high-time data and
share the actual SYS_CLK ancestry. Four outputs retain their write-MMCM
fine-phase groups. Eight parallel native cases also verify source phase/duty,
inverted outputs, missing/ambiguous clocks, feedback guards and default-off
behavior. The complete inventory has 38 known clock nets and one unknown raw
BSCAN TCK; its only two API references are independently proven constant
buffer controls. The sampler callbacks are initialized before extraction and
both sampler clocks have 792 references. These are nominal waveform data;
phase-aware engine budgets, clock skew and full routed timing remain pending.

Nominal phase-edge integration now passes actual analyser checks against
40 vendor register paths, including quarter-phase, clock division, both edges
and non-50% primary duty. The isolated backend rebuilt 16 timing-dependent
files with eight workers. Eight native cases pass, preserving unknown source
and dynamic relative phase relationships. A complete unchanged-design intrinsic
analysis also exits 0: 18 clock-domain pairs, 14 known nominal budgets, two
dynamic and two unrelated. This explicitly unplaced analysis does not qualify
clock insertion/skew, uncertainty, fabric numbers or full routed timing.

The small single-LUT design and 5,912-byte checkpoint only open the vendor
part library for these queries. The three live complete OpenTPU implementation
runs retain MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2, a 100 MHz core
and both DDR800 channels. Their selected backend and input inventories were
not modified. The original heap attempt separately failed placement with
native exit 125; its evidence remains preserved.

Before numerical qualification, match the raw conditional models to the
actual pins and parameters, validate both DDR edges and CLK/CLKDIV behavior,
retain MMCM clock-family phase relationships, and address the existing
provisional LUT/FF models and omitted clock uncertainty/reset constraints.
Compare resulting paths with full Vivado evidence. Raw model availability
does not establish timing closure for the complete routed accelerator.

Evidence, including exact Tcl sources, native exits, hashes and raw tables:

- [Full Vivado command capabilities](../build/fedora-openxc7/full-vivado-timing-capability-20261011T210715Z/manifest.json).
- [DSP/MMCM query](../build/fedora-openxc7/full-vivado-xc7-speed-query-20261011T210909Z/manifest.json) and [numeric field validation](../build/fedora-openxc7/full-vivado-xc7-speed-query-20261011T210909Z/raw-model-summary.json).
- [Preserved empty serializer BEL query](../build/fedora-openxc7/full-vivado-serdes-speed-query-20261011T211355Z/manifest.json).
- [Serializer and I/O logic query](../build/fedora-openxc7/full-vivado-iologic-speed-query-20261011T211752Z/manifest.json) and [numeric field validation](../build/fedora-openxc7/full-vivado-iologic-speed-query-20261011T211752Z/raw-model-summary.json).
- [Full DSP parameter inventory](../build/fedora-openxc7/full-dsp-timing-parameter-inventory-20261011T211922Z.json).
- [All complete DSP configuration queries](../build/fedora-openxc7/full-dsp-config-vivado-timing-20261011T213448Z/manifest.json) and [validated parameter/arc semantics](../build/fedora-openxc7/full-dsp-config-vivado-timing-20261011T213448Z/semantic-summary-v2.json).
- [Prepared DSP tables and independent raw validation](../build/fedora-openxc7/full-dsp-timing-tables-20261011T221105Z/manifest.json), [converter test receipt](../build/fedora-openxc7/full-dsp-timing-tables-20261011T221105Z/tests.json) and [integration plan](openxc7_dsp_timing_plan.md).
- [Isolated DSP backend build](../build/fedora-openxc7/dsp-vivado-timing-backend-20261011T222148Z/manifest.json) and [actual native callback comparison](../build/fedora-openxc7/dsp-vivado-timing-native-check-20261011T222902Z/manifest.json).
- [Complete packed OpenTPU export](../build/fedora-openxc7/full-packed-dsp-inventory-20261011T223120Z/manifest.json) and [effective hardware DSP inventory](../build/fedora-openxc7/full-packed-dsp-inventory-20261011T223120Z/analysis-effective/inventory.json).
- [All 19 effective Vivado configurations](../build/fedora-openxc7/effective-dsp-config-vivado-timing-20261011T224449Z/manifest.json), [verified timing tables](../build/fedora-openxc7/effective-dsp-timing-tables-20261011T225032Z/manifest.json), [mask-aware backend](../build/fedora-openxc7/effective-dsp-vivado-timing-backend-20261011T225248Z/manifest.json) and [native configuration checks](../build/fedora-openxc7/effective-dsp-vivado-timing-native-check-20261011T225533Z/manifest.json).
- [Complete 717-DSP callback comparison](../build/fedora-openxc7/full-effective-dsp-native-check-20261011T230049Z/manifest.json) and [remaining PHY/clock configurations](../build/fedora-openxc7/full-phy-clock-timing-inventory-20261011T231155Z/inventory.json).
- [Corrected PHY/clock vendor query](../build/fedora-openxc7/full-phy-clock-vivado-timing-20261011T234014Z/manifest.json) and [parameter/arc/waveform validation](../build/fedora-openxc7/full-phy-clock-vivado-timing-20261011T234014Z/semantic-summary.json).
- [Isolated serializer backend](../build/fedora-openxc7/serdes-vivado-timing-backend-20261012T001818Z/manifest.json), [eight native configuration cases](../build/fedora-openxc7/serdes-vivado-timing-native-check-20261012T002225Z/manifest.json) and [complete 358-serializer callback comparison](../build/fedora-openxc7/full-serdes-vivado-timing-native-check-20261012T002324Z/manifest.json).
- [Actual eight-core build CPU sample](../build/fedora-openxc7/all-cores-serdes-build-live-20261012T001902Z.json).
- [Clock intrinsic backend](../build/fedora-openxc7/clock-vivado-timing-backend-20261012T003653Z/manifest.json), [eight native clock cases](../build/fedora-openxc7/clock-vivado-timing-native-check-20261012T004052Z/manifest.json) and [complete clock/serializer audit](../build/fedora-openxc7/full-clock-vivado-timing-native-check-20261012T004143Z/manifest.json).
- [Vendor disabled-reset report](../build/fedora-openxc7/vivado-clock-reset-semantics-20261012T003246Z/disabled-timing.rpt).
- [Corrected nominal waveform backend](../build/fedora-openxc7/clock-family-vivado-backend-20261012T013334Z/manifest.json), [eight native waveform cases](../build/fedora-openxc7/clock-family-native-check-20261012T013626Z/manifest.json) and [complete accelerator waveform comparison](../build/fedora-openxc7/full-clock-family-native-check-20261012T013712Z/manifest.json).
- [Actual shifted-primary vendor waveforms](../build/fedora-openxc7/vivado-primary-clock-waveform-check-20261012T010951Z/clock-waveforms.tsv) and [constant-control proof for the unknown raw JTAG clock](../build/fedora-openxc7/full-clock-family-native-check-20261012T013712Z/unknown-clock-control-proof.json).
- [Forty actual vendor register-edge relations](../build/fedora-openxc7/vivado-phase-edge-paths-validated-20261012T021143Z/manifest.json), [isolated phase engine](../build/fedora-openxc7/phase-engine-vivado-backend-20261012T022403Z/manifest.json), [eight native analyser cases](../build/fedora-openxc7/phase-engine-native-check-20261012T022527Z/manifest.json) and [complete unplaced intrinsic analysis](../build/fedora-openxc7/full-phase-engine-native-check-20261012T022758Z/manifest.json).
- [Native process and heap failure review](../build/fedora-openxc7/full-native-terminal-review-20261011T212045Z.json).
