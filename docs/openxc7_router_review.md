# OpenXC7 router review, 2026-10-12

## Current run and five-minute diagnostics, October 13

The current route is the isolated preserved-placement replay in
`full-congestion-model-restored-isolated-route-20261013T045700Z`, native
PID 400903/start 21826315, backend SHA256
`44e8295a75db215da968abc16980af444a1e3f46c2b07b3313aed0b2b36b5851`.
The earlier simultaneous jobs described in dated sections below were lost
after the host's global OOM; their historical observations do not identify
current processes. No placement restart is required.

See the [current OpenXC7 bitstream plan](openxc7_bitstream_plan.md) for the
complete scope, upstream DSP encoding fixes and image qualification gates.
The new [five-minute observer](../build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/latest.json)
measures unique driven sink-connection flags, deferred worker failures,
observed routed-to-unrouted state transitions and sampled search queues.
Remaining connections decreased 431,793 -> 429,450 -> 427,826 over the first
three samples; no routed-to-unrouted transitions were observed. The cumulative
rip-up-call count is not stored by this running binary, and instantaneous
queue samples do not establish a peak between observations or convergence.

The fresh upstream check still selects `main` at `1e64f410`; the latest
merge fixes DSP48E1 MASK/ZADREG/ZDREG FASM encoding, which the current emitter
lacks. No common router/placer changes appear in the 73-commit comparison.
Retain the ongoing route and validate the encoding changes in a separate
candidate before any OpenXC7 hardware load.
[Saved upgrade review](../build/fedora-openxc7/upstream-upgrade-review-20261013T102959Z/summary.json).
The separate emitter now passes native cascade/strict frames and all six
register/MASK mode comparisons: 51 target bits match all 717 DSPs in the
finished Vivado reference. Other DSP fields and corrected full-image
provenance remain pending; the live router is unchanged.
[Targeted frame evidence](../build/fedora-openxc7/dsp-frame-comparison-20261013T131300Z/manifest.json).

## Live revision and alternatives refresh, October 13 10:55 HKT

The clean donor checkout is on `main` at
`c68c13582e972292c86a5025140d52e713384cbc`. Both active corrected full-design
jobs execute the locally patched binary with SHA256
`d4a0cdf08dcaf28e82120c1ba0b03e03c20f5f885646c307696c7cb3fd348a3a`.
They are not clean latest-upstream builds. The fresh GitHub API check reports
upstream's default branch as `main`, with head
`1e64f41043ca9df9b39ff23e3ee4c7fff2767042`, 73 commits ahead of our base.
The comparison changes no `common/route/` or `common/place/` files. Architecture
fixes may affect particular designs; this comparison does not demonstrate a
general routing speed improvement.
[Exact comparison](https://github.com/openXC7/nextpnr/compare/c68c13582e972292c86a5025140d52e713384cbc...1e64f41043ca9df9b39ff23e3ee4c7fff2767042).
[Saved live API results](../build/fedora-openxc7/router-web-refresh-20261013T025510Z/summary.json).

All eight listed fork default branches have zero additional commits relative
to current upstream. Topic branches contain distinct work: cavearr's
`review/congestion-spread` and sirmick's `xc7v-congestion-spread` modify heap
placement, while `placer-heap-timeout-overflow` also carries upstream router
changes and a 64-bit placement-timeout fix. Its divergence requires reviewing
individual changes rather than substituting the whole branch. The current
candidate already includes the adapted per-wire memory reduction and the
BUFGCTRL route-through guard. Its clean c68c135 donor already contains the
RUDY congestion-spreading implementation; the separate full placement trial
enables it. At the latest log inspection refinement had reached iteration 45,
but native placement and routing had not completed.

[Issue 59](https://github.com/openXC7/nextpnr/issues/59) reports router1 taking
1,711 seconds on a 46-BRAM Artix design, versus 12.9 seconds for router2 on the
same newer build. Our full route explicitly uses router2. The last completed
full routing pass has 484,951 overused wires, and individual arc searches have
logged five-million-iteration warnings. This establishes severe search cost
and congestion in this run; it does not identify the issue-59 regression as
our cause or establish a hardware fault.

The practical implemented reference remains Vivado. Legacy nextpnr-xilinx is
archived and requires its own matching database; F4PGA/VPR has no published
YPCB/K480T board target; current RWRoute supports UltraScale, UltraScalePlus
and Versal, excluding Series 7. No reviewed alternative demonstrates faster
completion of this unchanged full OpenTPU design. Existing jobs remain live.

## Full congestion-placement comparison plan

Inspection of the actual candidate's source and `--help` confirms that
congestion-aware heap placement is already available in the c68c135 base.
It is not enabled by the current static-placement command. The next trial
uses the same executable, corrected chip database, frozen full netlist,
XDC, clock/CDC contracts and 100 MHz/dual-DDR800 profile, selecting heap
placement with `--placer-heap-congestion-spread` and weight 0.5. It requests
all eight CPUs. No backend port or new compilation is necessary.

The trial stops naturally after placement (`--no-route`), exports the
complete placed netlist, and retains its native exit and timing report.
Completion is only placement evidence; numerical timing, routing,
bitstream and physical tests remain separate requirements. Existing
routes remain running. The placed result must be reviewed before starting
another memory-intensive full router. No clock, design-size or timing-fail
override is introduced.

The deployed `common/place/placer_heap.cc` main loop has no fixed iteration
count. It continues while there are fewer than five consecutive iterations
without a new best legal wire length and the solved wire length is at most
80% of the legal wire length. It then restores the saved best placement,
checks every binding and BEL's legality, and runs refinement before
returning. This command does not enable `--parallel-refine`, so the default
refinement path applies. A completed main iteration is not a completed
placement. No stopping policy or live backend was changed.

The deployed `placer1.cc` initializes refinement temperature to `1e-7`,
which the log rounds to `0.000000`. Each iteration performs 15 sweeps over
automatically placed cells and chain roots. It stops when the temperature
is at most `1e-7` and one complete iteration fails to produce a new minimum
wire-length cost. Periodic iteration messages appear before that iteration's
work; they show an iteration reached, not necessarily completed. After the
loop, native BEL-validity checks and timing analysis still run before return.
There is no fixed refinement iteration limit. The log has reached iteration
50, with no native exit or placed export yet.
[Verified deployed stopping rule](../build/fedora-openxc7/full-congestion-heap-placement-20261013T001000Z/refinement-stop-rule.json).

The full trial is now live under
`build/fedora-openxc7/full-congestion-heap-placement-20261013T001000Z/`.
All four initial analytic iterations completed, followed by eight logged
congestion-map builds. Two read-only debugger snapshots at 08:13 and 08:15
HKT found 172,690 then 165,930 queued legalizer tasks and 81,000 intervening
legalizer visits. The current FF changed. Each observation detached cleanly
and confirmed CPU execution resumed. Queue entries may include displaced
cells being revisited; these counters do not count unique unplaced cells or
prove eventual convergence.
[Actual search comparison](../build/fedora-openxc7/full-congestion-placement-search-20261013T001532Z/comparison.json)

The completed-output reviewer `tools/openxc7_full_placement_review.py`
checks all cells against the immutable packed baseline linked by the CDC
contract. Connections are normalized by native net name, with unique
unconnected serialized bits kept distinct from missing/reused signals.
Cell types, all parameters, original primitive/port mappings and top-port
connections must match. All non-pseudo cells must have unique physical
assignments, and the six synchronizer FFs must occupy the required primary
FFs in two slices. This is not routing, physical legality or timing signoff.

The normalizer passed a complete 464,200-cell/35-port-group replay. A wrong
parameter key in the first auxiliary clock-polarity summary was caught,
rejected and preserved. The corrected replay matches all 179,299 FF modes,
including 402 inverted-clock FDREs, and the complete logical hash remains
identical. The running-trial guard returns 2 without creating a review
directory. [Complete corrected baseline](../build/fedora-openxc7/full-placement-logical-baseline-polarity-corrected-20261013T003513Z/manifest.json)

## Current revision and alternatives, October 13 08:03 HKT

At 08:23 HKT, a further read-only snapshot found both original full-router
workers on different nets from the 07:57 snapshot: VPU `s_fd[210]` and
`u_sys.n_rdata[412]` replaced the earlier tensor-memory and activation-RAM
searches. The process remained in iteration 2. This is evidence of advancing
individual searches, without a completed iteration or convergence claim.
Debugger exit 0, no remaining tracer and resumed CPU execution were verified.
[Actual comparison](../build/fedora-openxc7/full-route-search-progress-20261013T002306Z/comparison.json)

A fresh GitHub API check confirms upstream `main` at
`1e64f41043ca9df9b39ff23e3ee4c7fff2767042`. Our clean donor remains on
`main` at `c68c13582e972292c86a5025140d52e713384cbc`; the live executable
is a patched candidate derived from that base, not a clean latest-main build.
The 73 newer commits change no `common/route/` files. All eight listed
fork default branches have zero additional commits relative to upstream.
The congestion-spread and heap-timeout topic branches are separate
experiments, without a demonstrated full OpenTPU/K480T speedup.
[Fresh API responses](../build/fedora-openxc7/router-web-current-20261013T000055Z/)
preserve the repository, head, comparison and fork checks.

The running command explicitly selects `--router router2 --threads 8`.
A read-only debugger snapshot found iteration 2 with two workers searching
data nets: their forward/backward queues contained 156,860/188,664 and
24,868/29,480 entries. This confirms active routing searches, but does not
prove convergence. The debugger detached with `TracerPid=0`, and process
CPU time advanced afterward. No target functions were called and no build
was restarted.
[Snapshot receipt](../build/fedora-openxc7/full-route-search-progress-20261012T235726Z/manifest.json)

Vivado is the already demonstrated implementation alternative for the
same mapped input. The archived nextpnr-xilinx backend is a comparison
candidate, without evidence that it fixes this full design. F4PGA/VPR
publishes supported boards without YPCB/K480T, so it needs target work.
RWRoute's current supported-family list excludes Series 7. Current evidence
does not identify a faster drop-in open router for this board.

## Upstream and fork refresh, October 13 04:18 HKT

Fresh GitHub API reads now report OpenXC7's default branch as `main`, head
`1e64f41043ca9df9b39ff23e3ee4c7fff2767042`, 73 commits ahead of our clean
`c68c13582e972292c86a5025140d52e713384cbc` donor. There are no changed
`common/route/` files in that comparison. The latest merge is DSP packing
PR 101; it is not a demonstrated general router speed improvement.
[Exact comparison](https://github.com/openXC7/nextpnr/compare/c68c13582e972292c86a5025140d52e713384cbc...1e64f41043ca9df9b39ff23e3ee4c7fff2767042).

All eight fork default branches are compared again and have zero additional
commits relative to that head. Selected branch reads confirm cavearr's
`review/congestion-spread` and sirmick's `xc7v-congestion-spread` and
`placer-heap-timeout-overflow` topics remain available. These experimental
placement changes do not establish full OpenTPU/K480T speedup, and the live
route uses static placement. The live executable hash remains
`d4a0cdf08dcaf28e82120c1ba0b03e03c20f5f885646c307696c7cb3fd348a3a`.

Current RapidWright source lists UltraScale, UltraScalePlus and Versal in
RWRoute's supported families, excluding Series 7. The older maintainer
comment's narrower list should not be treated as the current family census.
[Current source](https://github.com/Xilinx/RapidWright/blob/master/src/com/xilinx/rapidwright/rwroute/RWRoute.java).

## First main routing pass complete, October 13 03:48 HKT

The corrected full route now logs its first complete main iteration:
`iter=1 wires=9587162 overused=484951 overuse=530491 archfail=NA`.
The run remains live and congestion still needs repair. The `NA` field is
not evidence of zero architecture failures; no completed route/timing/FASM
output exists yet. Both native session handles are pending and exact PID/
start identities plus CPU progression remain confirmed. The full same-input
FF query has 408 of 4,810 sample pairs, with every planned max/min query
retained. All 31 source hashes and the immutable reference checkpoint match.
USB still contains no Xilinx adapter, so physical testing cannot resume.
[Current complete goal evidence](../build/fedora-openxc7/goal-router-iteration-and-ff-wait-20261012T194802Z.json).

## Same-input reference complete; current router observation, October 13 02:54 HKT

The full same-mapped-input Vivado reference now routes all 397,867 routable
nets and passes internal setup/hold/pulse timing at the original 100 MHz
target, with reported WNS 0.000 ns and zero failing endpoints. Its full
dual-DDR800 bitstream passes native generation, DRC, all 905 pin-property
checks and independent packet/device inspection. Physical testing remains
pending and its success does not qualify OpenXC7's own numerical model.
[Completed reference](../build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/manifest.json).

A fresh guarded read-only snapshot of the unchanged corrected router PID
261549/start 15880662 finds source 72832:460 and sink 125763:2720, different
from the earlier 17:10 UTC source/sink pair. The router is still serial
ordinary-data bounding-box search (`is_mt=false`, `const_mode=false`),
iteration 1, with 117,072 visited wires, forward/backward queues 64,705 /
72,218 and search allowance 5,375,000. This proves search advancement, not
full convergence. No net-name recovery or inferior function call is used.
GDB exits 0, TracerPid becomes zero and CPU ticks advance after detach.
[Actual snapshot](../build/fedora-openxc7/full-clock-router-current-counters-20261012T185438Z/manifest.json).

The subsequent native-session poll remains pending. All four retained job
PID/start identities and 31 frozen source hashes still match, the reference
bitstream hash remains unchanged, and USB detects no Xilinx cable. No full
OpenXC7 route/timing/FASM output or physical compiler pass exists yet.
[Current complete goal review](../build/fedora-openxc7/goal-full-router-verified-wait-20261012T185638Z.json).

## Fresh user-requested review, October 13 01:45 HKT

The fresh GitHub responses confirm current `openXC7/nextpnr` main at
`f9e07df89945ded95873948277dc0b11cd10c58e`. The clean donor checkout remains
on main at `c68c13582e972292c86a5025140d52e713384cbc`; the corrected running
job uses its separately patched `d4a0cdf0...` binary and `f98dc64e...`
database. This is a main-based local candidate, not latest main or legacy
master. The comparison has 70 additional commits and no `common/route/`
changes. [Fresh repository, PR and revision evidence](../build/fedora-openxc7/router-user-query-20261012T174504Z/summary.json).

All eight current fork default branches have zero commits ahead of OpenXC7
main. Selected topic branches remain separate: cavearr's
`review/congestion-spread` and sirmick's `xc7v-congestion-spread` change the
heap placer behind an experimental flag, whereas our current job uses
the static placer. Neither establishes full OpenTPU/K480T performance.
The sirmick timeout branch and original YosysHQ main contain router memory,
legality-check and unavailable-wire fixes but are substantially diverged;
they require individual compatibility review. The per-wire memory change
is already adapted and tested locally. [All default-branch comparisons](../build/fedora-openxc7/router-user-query-20261012T174504Z/fork-review-summary.json)
and [selected performance topics](../build/fedora-openxc7/router-user-query-20261012T174504Z/topic-summary.json).

[Issue 59](https://github.com/openXC7/nextpnr/issues/59) demonstrates a
router1 regression on an Artix-7 reproducer: 1,711 seconds versus 37.9
seconds for legacy router1, while newer router2 takes 12.9 seconds. Our
active job already uses router2. A different
[openPCIE project](https://github.com/chili-chips-ba/openPCIE/blob/main/4.build/hw_build.openXC7/README.md)
reports an infinite loop in the legacy router's `route_xilinx_const` and a
working older revision. Our newer backend's observed serial searches have
changing wire endpoints and `const_mode=false`; that legacy report is not
evidence that our current job has the same failure. No claim of a universal
45x router2 slowdown or a proven drop-in faster fork is supported.

Practical options remain Vivado, or a controlled nextpnr patch/placement
comparison. Legacy nextpnr-xilinx is archived; F4PGA's published boards lack
this YPCB/K480T target; RapidWright's maintainer says RWRoute does not
support Series 7 and its older Router does not scale well. Existing live
jobs and donor checkouts were preserved. The same-mapped-input Vivado
reference now routes all 397,854 routable nets, with setup WNS -0.245 ns
and 125 failing endpoints; hold and pulse checks pass. Post-route physical
optimization is running at the unchanged full scope and 100 MHz target.
[Completed reference review](../build/fedora-openxc7/full-reference-physopt-route-reviewed-20261012T173923Z/manifest.json)
and [post-route job](../build/fedora-openxc7/full-mapped-vivado-postroute-20261012T174600Z/manifest.json).

## Current corrected full router, October 13 01:10 HKT

Three guarded read-only snapshots confirm the corrected full job is now
in its serial route_arc phase (`is_mt=false`, ordinary data, bounding-box
search), after its earlier parallel workers. The source/destination wire
pairs change between observations: 52855:341 to 103210:373, then
105172:453 to 5149:2720, then 58724:341 to 106472:460. Visited-wire counts
are 64,680, 891,313 and 339,243 respectively, with search allowances
4,125,000, 8,850,000 and 4,000,000. This is real search advancement;
iteration remains 1 and full convergence/timing is unproven.
[First serial counters](../build/fedora-openxc7/full-clock-router-counters-20261012T170615Z/manifest.json),
[second serial snapshot](../build/fedora-openxc7/full-clock-router-serial-net-20261012T170820Z/manifest.json),
[third snapshot](../build/fedora-openxc7/full-clock-router-netdata-20261012T171022Z/manifest.json).
Current net-name recovery is optimized out; do not reuse the earlier MXU/LUT
net names as if they identify these current searches. All observers disable
inferior function calls, detach normally and verify TracerPid zero.

The active backend's `preplaced` reader assigns locked BEL attributes and
closes every referenced tile to other cells. It expects the same packed
native cells, including packer-created LUTs. A partial Vivado cell placement
cannot be blindly used as a hint file: it would freeze tiles while unmatched
native cells still need room. Any placement comparison or import needs an
explicit packing/cluster compatibility review rather than this raw replay.
No replay or router settings were changed in the running jobs.

The actual complete route already uses its measured delay matrix: 1,164
of 2,401 offsets from three sources, 1,237 interpolated structural holes,
window 24 and out-of-window rates 10.5/12.7 ps per tile in X/Y. The matrix
is not disabled in this job. Its quality on these long searches remains a
separate question; the public router1 report alone does not diagnose them.

## User-requested alternatives refresh, 23:20 HKT

The [fresh repository and comparison responses](../build/fedora-openxc7/router-query-refresh-20261012T152035Z/summary.json)
confirm default branch `main`, head `f9e07df89945ded95873948277dc0b11cd10c58e`,
70 commits ahead of the donor `c68c13582e972292c86a5025140d52e713384cbc`.
The comparison changes 21 files and no `common/route/` file. The running
corrected full job uses the isolated `d4a0cdf0...` executable and `f98dc64e...`
database, rather than a clean latest-main build. Its PID/start identity still
matches, and no terminal route, timing or FASM output exists.

The current candidate already incorporates the tested PR 81 clock-buffer
guard, the adapted upstream router2 visited-state memory change (256 MiB
saved locally), early explicit clock LOC handling, and the controlled
clock-cascade database correction. Dedicated-clock failures are now zero;
large data-routing searches remain active. These fixes establish specific
correctness and memory improvements, not full-design convergence or speedup.

[Issue 59](https://github.com/openXC7/nextpnr/issues/59) is evidence of a
router1 regression: 1,711 s versus legacy 37.9 s on its 46-RAMB36 test.
Router2 takes 12.9 s on that same test, and our job already uses router2.
[Upstream draft PR 1827](https://github.com/YosysHQ/nextpnr/pull/1827)
addresses router1 congestion on ECP5; it is not a demonstrated fix for our
Xilinx router2 job. The earlier saved topic-branch review identifies
cavearr's congestion-driven heap-placement prototype; it remains an
experimental placement comparison, with no full OpenTPU/K480T speed result.

The [legacy OpenXC7 repository](https://github.com/openXC7/nextpnr-xilinx)
is archived. [F4PGA's published boards](https://f4pga.org/#supported-boards)
do not include this YPCB/K480T target; an independent VPR flow would need
porting and verification. A
[RapidWright maintainer](https://github.com/Xilinx/RapidWright/discussions/1198)
states that RWRoute supports UltraScale+/Versal, not Series 7, while the
older Series-7 Router does not scale well. No demonstrated faster drop-in
open router was found for the complete retained design.

The new fork list was fetched, but fresh per-fork comparison requests hit
GitHub's unauthenticated API rate limit. Earlier same-day branch snapshots
remain available above; the refresh does not claim a new exhaustive fork
audit. Existing builds and source checkouts were left unchanged.

## Current full-route counters, 23:04 HKT

The corrected full job remains PID 261549/start 15880662, with two active
router workers and a coordinator waiting for them. A guarded read-only GDB
snapshot, with inferior function calls disabled, identifies actual data
searches: the MXU `lv2` valid-control net and a LUT-data net. Their visited
wire counts are 458,310 and 169,394, with forward/backward queues of
156,595/180,410 and 99,081/32,850. Their configured bounded-search limits
are 8,650,000 and 4,975,000 iterations. This identifies expensive graph
search; it does not establish convergence or a routing failure.
[Exact native counter snapshot](../build/fedora-openxc7/full-clock-router-counters-20261012T145302Z/manifest.json).

The coordinator's cached critical-path and Fmax reports are empty. The
saved `full.paths.json` is explicitly unplaced/intrinsic-only: its worst
reported core path totals 5,568 ps, including zero routing delay. It cannot
identify the path behind the post-placement 50.97 MHz estimate. The final
routed report is required before choosing a timing change. All debugger
observers detached with TracerPid zero; no inferior function or full-job
restart was performed.
[Cache observation](../build/fedora-openxc7/full-clock-router-observe-20261012T144621Z/manifest.json)
and [current full-job/source/USB review](../build/fedora-openxc7/goal-router-counter-and-timing-review-20261012T150411Z.json).

## Latest research, 19:55 HKT

Before assembling a full result from the new clock backend, re-run the
five exact carry/upper-carry/DSP/FF/mux native witnesses with its executable
and database. Keep each fixture, seed and options unchanged. Reuse prior
functional evidence only when the actual routed graph and FASM are identical;
otherwise decode and validate the changed graph. Run strict frame assembly
on fresh FASM, including the actual clock fixture containing the restored
cascade features. Retain the original backend receipts and live jobs.

That exact-backend review is now complete: all five native routes succeed;
their FASM and configuration frames reproduce the earlier qualified outputs
byte for byte. Routed JSON differs only by four explicitly disabled reporting
settings, with every actual circuit/placement/routing field unchanged. The
FF timing report is identical. All six strict assemblies pass, and an
independent checker verifies all 12 restored clock feature bits in the clock
frames and rejects an injected bit flip. See the current
[image qualification and prepared finalizer](openxc7_qualification.md).

The fresh [GitHub API snapshot](../build/fedora-openxc7/router-web-review-20261012T115534Z/summary.json)
confirms that the default branch is `main`, not `master`. Our donor checkout
is still `c68c13582e972292c86a5025140d52e713384cbc`; the live full jobs use
the separately patched `static-double-exp-backend-20261011T183100Z` binary.
Current OpenXC7 main is `f9e07df89945ded95873948277dc0b11cd10c58e`, 70
commits ahead, with no `common/route/` changes in that comparison. Original
YosysHQ main is `837d0eedfc2ee5342b3f80922c083f6b0126aa6f`; its router
changes require individual compatibility review rather than replacing the
whole fork router.

All eight [fork default branches](../build/fedora-openxc7/router-web-review-20261012T115534Z/fork-comparisons.json)
have zero additional commits relative to current OpenXC7 main. Selected
clock-related branches and
[performance topics](../build/fedora-openxc7/router-web-review-20261012T115534Z/fork-performance-topics.json)
were also checked. `xc7v-congestion-spread` and cavearr's
`review/congestion-spread` contain an experimental congestion-aware heap
placement change; they change placement, not the general router, and no
full OpenTPU/K480T performance result was established by this review.
[Prototype commit](https://github.com/cavearr/nextpnr/commit/be04d6866235d8d73e34e50ba67fdfa72cf15b56).
The sirmick heap-timeout branch includes original-upstream router commits
and a 64-bit placement-timeout correction; it is substantially diverged,
not a demonstrated drop-in solution. This is a selected-topic review,
not an exhaustive audit of every branch.

The [upstream per-wire memory change](https://github.com/YosysHQ/nextpnr/commit/914e84257dff480b652bd6156e9944441ec3e4ff)
has already been adapted in an isolated candidate. All six native small
routes passed; each stock/compact pair produced identical routed netlists,
FASM and clock policy. Its allocated wire table saves 268,435,456 bytes
(256 MiB). This does not establish a full-design speedup, and the original
full jobs still use the earlier binary.
[Local validation](../build/fedora-openxc7/router-wire-memory-native-check-20261012T102600Z/manifest.json).

### Concrete clock connectivity suspect from Vivado

The controlled database experiment will build two private databases from
the same pinned generator, metadata and Project X-Ray input. First require
the stock binary to match the installed database byte for byte. The fixed
variant changes only the filter for the 32 same-index `CLK_HROW_TOP_R`
`CK_BUFG_CASCIN` to `CK_BUFG_CASCO` connections, after checking that every
connection is directional and has a segbits feature. Keep all other filters
and no-config-bit availability checks. Run the same early-LOC clock fixture
against both databases with the same diagnostic executable and seed.
Compare every clock arc and preserve the original full jobs/database.

The [actual clock diagnostic in Vivado](../build/fedora-openxc7/clock-prototype-vivado-route-20261012T113500Z/manifest.json)
retained all 54 cells and routed all 14 generator-to-buffer connections,
with native exit 0. All 80 exported physical PIP records map to installed
segbits or ppips. Twelve records, two on each of the six channel-1 MMCM
connections, are top-half `CK_BUFG_CASCIN` to `CK_BUFG_CASCO` cascade PIPs.
The current OpenXC7 and YosysHQ database generators both explicitly filter
these connections out. Exact current source copies are saved in the latest
API snapshot directory. [Physical PIP comparison](../build/fedora-openxc7/clock-vivado-pip-feature-comparison-20261012T114000Z/manifest.json).

The controlled experiment now confirms that this filtered connectivity
caused the six channel-1 dedicated-clock failures. The private stock rebuild
reproduces the installed database byte for byte, SHA256 `790e05a8...`.
The fixed database, SHA256 `f98dc64e36fb3a62a7f82a14654a045b19e8b5bbf042580b5ce674b242849a7c`,
changes only the verified filter. The generator census adds exactly 32
expressible PIPs; unmapped and unchecked counts remain 1,115 and 615.
[Controlled database pair](../build/fedora-openxc7/clock-cascade-database-20261012T120218Z/manifest.json).

The same executable, seed and 54-arc clock fixture fail six dedicated arcs
with stock and zero with fixed. Exactly the six channel-1 arcs improve;
no other arc regresses. The clock fixture then completes the native main
router with exit 0. Its FASM contains all 12 restored cascade settings,
and all 16 driven global clock spines have configured buffers. All 32
forbidden buffer route-through PIPs remain blocked. These are actual clock
topology and configuration checks, not full-accelerator timing signoff.
[Native comparison and complete clock route](../build/fedora-openxc7/clock-cascade-native-check-20261012T121820Z/manifest.json).

Both unsupported and occupied explicit clock LOCs are rejected with the
intended error, before the diagnostic route-stop marker.
[Negative LOC checks](../build/fedora-openxc7/clock-loc-negative-20261012T120300Z/manifest.json).
The early clock LOC correction had already changed six channel-0 dedicated
arcs from failure to success in an otherwise identical native diagnostic.
[LOC comparison](../build/fedora-openxc7/clock-loc-native-ab-20261012T112800Z/manifest.json).

The corrected database and early LOC option also pass the complete
MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2, core100/dualDDR800 pack and
analysis. All 1,103 mailbox limits, two synchronizer clusters and 18
domain-pair budgets match the prior full results exactly.
[Full-design qualification](../build/fedora-openxc7/full-clock-cascade-check-20261012T122000Z/manifest.json).

A new full placement/route is running in
`full-clock-cascade-route-20261012T122322Z`: PID **261549**, start ticks
**15880662**, tool session **61317**. It uses the corrected database and
the tested early-LOC option, requests eight threads and allows CPUs 0–7.
Its original full source, dimensions, 100 MHz core and both DDR channels
are retained. Generic FF numerical timing remains unqualified; no accepted
OpenXC7 image or new physical pass exists.
[Candidate and job](../build/fedora-openxc7/clock-cascade-candidate-20261012T122414Z.json).

The three original full PID/start identities and all 31 source hashes still
match. Their original executable and database remain untouched. The area
trial remains in main routing; static and delay remain in legalization.
No Xilinx USB adapter was detected at 20:24 HKT, so the remaining Vivado
physical vector/stream/compiler-model selftest cannot yet run.
[Current complete goal review](../build/fedora-openxc7/goal-clock-cascade-route-review-20261012T122414Z.json).


The current full OpenTPU route uses an isolated `nextpnr-himbaechel` binary,
SHA256 `2bfd62e16b981999c12b0738321456bbaf865be0a0caffcc0f4dfe9265962efe`,
based on **openXC7/nextpnr main c68c13582e972292c86a5025140d52e713384cbc**
(2026-09-30), with local xc7 fixes. This is not the legacy nextpnr-xilinx
master branch. The clean donor checkout still reports that revision; the
isolated build lineage also records it.

The upstream comparison snapshot at 14:02 HKT on 2026-10-12 reports **68 commits ahead** at
`d3acad91cf686a480579ef69b5f62d8f141df480`. No file under `common/route/`
changes in that comparison. An update therefore supplies architecture and
configuration fixes, not evidence of a new general router2 algorithm.
[Upstream comparison](https://github.com/openXC7/nextpnr/compare/c68c13582e972292c86a5025140d52e713384cbc...d3acad91cf686a480579ef69b5f62d8f141df480).

Raw public repository metadata, commit comparison, open PRs and issue bodies
are saved in
[router-alternatives-review-20261012T060242Z](../build/fedora-openxc7/router-alternatives-review-20261012T060242Z/sources.json).
No original checkout, live binary or source-pinned design was updated.

## Directly relevant patch

[PR 81](https://github.com/openXC7/nextpnr/pull/81), commit
`a17bd29c1270`, merged on 2026-10-10, prevents routes through the I0/I1-to-O
pseudo pip of an unconfigured BUFGCTRL. The old tile-wide check allows an
unbound slot when another buffer in that tile is bound. The FASM writer then
omits the unbound buffer's configuration, yielding a physically dead route.
The author reports XC7K480T evidence and a working four-hart Linux SoC using
the same c68c135 base. The original running source and pre-guard isolated
timing backend lack this guard; the new candidate is tested below. This is
a correctness fix; no speedup is established for
OpenTPU.

Next implementation: add this upstream guard in a fresh isolated source and
binary, preserving the existing packer, timing models and live jobs. Rebuild
the changed xilinx.cc only; verify both unbound-slot rejection and normal
buffer input/output routing on the actual K480T chipdb. Include a strict
post-route FASM audit before accepting any image. Do not alter the running
process or treat an old routed result as qualified by a later patch.

[PR 73](https://github.com/openXC7/nextpnr/pull/73) also calibrates fabric
timing, but its measured values explicitly apply to Virtex-7. Importing them
into this Kintex-7 design would be unjustified. Our exact-part FF calibration
remains necessary.

## Reported performance problems

[Issue 59](https://github.com/openXC7/nextpnr/issues/59) reports himbaechel
router1 taking 1711 seconds versus 37.9 seconds for legacy nextpnr-xilinx
0.9.7 router1 on a 46-RAMB36 Artix-7 test. The same newer backend's router2
takes 12.9 seconds on that test. Disabling the delay matrix helps router1
but does not close the gap. No fix is proposed in that issue. This is direct
evidence of a router1 regression; it does not show router2 is 45 times slower
on our K480T design.

[Issue 1732](https://github.com/YosysHQ/nextpnr/issues/1732) separately reports
long main-router loops and poor Fmax for GateMate. Placement changes help
some cases. It concerns another architecture, so it is supporting context,
not a diagnosis of this card. A broad statement that every OpenXC7 router is
weak would go beyond the evidence.

Fresh read-only live snapshots confirm our router is in serial route_arc
search, rather than waiting for USB or a thread lock. At 13:51 HKT the actual
net is `u_sys.n_rdata[723]`, a fabric data connection, with 153323 explored
wires, forward/backward queues of 135403/155658, and a 3700000-iteration
bounded-search allowance. Its global wire map has 49324697 entries. Source
and destination wires differ from the 13:46 snapshot, establishing that the
search has advanced. These two samples do not prove eventual convergence.
[Latest snapshot](../build/fedora-openxc7/route-hotspot-review-20261012T055125Z/gdb.log).

The previous long-search warnings also identify widely separated ordinary
LUT/FF connections. Dedicated DDR clock routing failures are a separate
observation. The current route is configured with eight threads and CPU
affinity 0-7, but this serial stage cannot use eight simultaneous workers.

## Alternatives

| Option | Applicability to the complete YPCB design |
| --- | --- |
| Current openXC7/nextpnr fork with selected upstream fixes | Closest match to our existing chipdb, packer, timing work and Kintex target; first choice for controlled comparison. |
| Legacy nextpnr-xilinx 0.9.7 | A useful separate performance baseline, not a drop-in binary for the himbaechel chipdb. It needs a matching legacy chipdb/metadata/bitstream flow and full primitive and DDR verification. |
| F4PGA/VPR | Independent routing approach, but no ready YPCB/K480T board target was found in the published supported-board list; a port and device-model validation would be additional work. |
| RapidWright RWRoute | Its current source supports UltraScale, UltraScalePlus and Versal, excluding Series 7; it does not provide a Kintex-7 replacement. |

The [legacy repository](https://github.com/openXC7/nextpnr-xilinx) is archived
and directs development to openXC7/nextpnr. The
[openPCIE author's pinned-version investigation](https://github.com/chili-chips-ba/openPCIE/blob/main/4.build/hw_build.openXC7/README.md)
also documents a legacy router2 constant-routing loop at bab26c2 and a working
older revision. Our fresh snapshot has const_mode=false and changes nets,
so that specific loop is not established here.

[F4PGA supported boards](https://f4pga.org/#supported-boards) and
[RWRoute limitations](https://www.rapidwright.io/docs/Implementation_Basics.html)
were checked live. No alternative was shown to complete the full unchanged
OpenTPU design at 100 MHz with dual DDR800. Retain those requirements in
every comparison; small probes and successful synthesis are not completion.

## Isolated guard implementation plan

Build two immutable variants from the latest verified timing backend: one
retains the old pip policy for the comparison only, and one adds the exact
upstream PR 81 guard. Both add an optional post-placement audit of every
tile-routing pip in both CLK_BUFG tiles, with the real bound-buffer slots.
Rebuild xilinx.cc only; no header, packer or timing-engine ABI changes.
Use an eight-worker compiler pool, then compare complete native pip policies
after identical small placements. Differences must be limited to the upstream
I0/I1-to-O predicate; ordinary buffer input and output routes must remain legal.
Complete fixed-backend routes with two placement seeds and independently check
every emitted global-spine driver has matching buffer configuration. The stock
variant is verification-only and cannot be selected as a qualified image backend.
Native route comparisons are limited to two concurrent processes for memory;
this does not restrict their eight-thread/CPU-affinity allowance. These tests
are offline architecture probes and leave the full accelerator requirements
and every live complete implementation unchanged.

The [preferred build pair](../build/fedora-openxc7/bufg-route-guard-backend-20261012T062600Z/manifest.json)
compiled and linked both variants, each rebuilding xilinx.cc only. The fixed
variant contains the exact upstream guard plus the optional audit. The stock
variant retains the prior policy and is verification-only. An initial pair
introduced a compiler lifetime warning in the audit; a named IdString removes
that warning in this preferred build. The first pair is retained unvalidated.

[Native comparisons](../build/fedora-openxc7/bufg-route-guard-native-check-20261012T063300Z/manifest.json)
pass for two normal placement seeds and an explicitly pinned bottom-tile
case. Each compares all 480 tile-routing pips across both K480T clock-buffer
tiles. All 32 input-to-output pseudo pips are unavailable with the fixed
policy. The old policy permits 16 in the occupied tile, of which 14 belong
to unbound slots. Exactly those 16 permissions change; the other 448 pip
policies and placements match. The bottom case places actual buffers at
BUFGCTRL_X0Y0/X0Y1, exercising the previously unoccupied tile with real
bindings. Three fixed-backend placements and routes complete with native
exit 0. Each FASM drives two global spines from two configured buffer slots,
with no unconfigured driver. These remain small architecture probes using
stand-in LUT clock sources, not functional board images or speed benchmarks.

The [full unchanged-design analysis](../build/fedora-openxc7/full-bufg-route-guard-check-20261012T063600Z/manifest.json)
then completes with native exit 0. Its complete 1103-endpoint datapath audit,
both synchronizer clusters and all 18 phase-domain budgets exactly match the
previous backend. The full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2,
100 MHz/dual-DDR800 profile is retained. The FF numbers remain provisional
and the analysis explicitly has zero data-route delay. No full placement,
route or routed numerical timing qualification is established by this pack.

The [clock-driver FASM negative checks](../build/fedora-openxc7/bufg-fasm-negative-check-20261012T063700Z/manifest.json)
reject missing buffer configuration, an extra unconfigured spine driver,
truncation and removal of every driven spine. The separately exercised CLI
returns exit 1 and a FAIL manifest for corrupted input, while the real native
FASM passes. Run this gate on every full candidate, including any output of
the preserved original route:

```sh
python3 tools/openxc7_bufg_route_guard.py audit-fasm \
  --fasm /path/to/full/design.raw.fasm \
  --out build/fedora-openxc7/new-clock-driver-audit
```

This command checks clock-driver configuration only. A pass does not replace
the other source, routing, timing, image or hardware gates. The fixed backend
is now available for subsequent complete implementation; the original live
jobs, input design, source and executable remain untouched.

## Fresh upstream and fork check, 15:34 HKT

The [API refresh](../build/fedora-openxc7/router-alternatives-refresh-20261012T073600Z/summary.json)
confirms upstream default branch `main`, head `d3acad91cf686a480579ef69b5f62d8f141df480`,
68 commits newer than our donor `c68c13582e972292c86a5025140d52e713384cbc`.
The comparison changes 21 files and no file under `common/route/`.
PR 81 is merged, dated October 10. Current open PR titles concern FASM,
BRAM, transceiver/IO, serializers and LUTRAM; they do not advertise a new
general router algorithm.

The [eight fork-main comparisons](../build/fedora-openxc7/router-alternatives-refresh-20261012T073600Z/fork-comparison.json)
cover HeroesLament, codex-hil, sirmick, DuClare, gHashTag, kammoh, cavearr and
jrrk2. Every main branch is behind current upstream with zero additional
commits. This checks their main branches only; it does not rule out work on
topic branches. No independently demonstrated faster drop-in K480T router
was identified in this review.

The live full route now reports its first congestion iteration: 9,951,740
wires, 564,545 overused wires and total overuse 624,939. Its original
PID/start identity still matches, and a three-second sample measures about
199% CPU. The two other full jobs each consume approximately one core in
strict placement legalization. No full route has exited or produced its
terminal outputs. These observations show active software work and unresolved
congestion; they do not establish eventual convergence or a speedup from PR 81.

## Original upstream check, 18:06 HKT

A fresh [OpenXC7 comparison](../build/fedora-openxc7/router-upstream-refresh-20261012T100700Z/summary.json)
now reports head `f9e07df89945ded95873948277dc0b11cd10c58e`, **70 commits**
ahead of our c68c135 donor. PR 100 merged at 16:29 HKT and makes FASM writes
atomic, preserving the previous file on error. No common/route file changed
within this OpenXC7 comparison.

The original **YosysHQ/nextpnr** upstream is a separate comparison. Its head
is `837d0eedfc2ee5342b3f80922c083f6b0126aa6f`, with 52 commits after the
shared ancestor and 177 commits unique to our fork-side base. These counts
describe divergence; YosysHQ main is not a compatible replacement merely
because it is newer. Its generic router files do differ.
[API comparison and direct source diffs](../build/fedora-openxc7/router-upstream-refresh-20261012T100700Z/upstream-core-summary.json).

Relevant original-upstream patches:

- [914e84257dff](https://github.com/YosysHQ/nextpnr/commit/914e84257dff480b652bd6156e9944441ec3e4ff)
  reduces redundant per-wire state. This is worth a controlled memory and
  runtime comparison on our large routing table, but no speedup is measured.
- [6f71bc280b17](https://github.com/YosysHQ/nextpnr/commit/6f71bc280b17805ee7687cad6dfdcdcb504d01d1)
  skips RESERVED_UNAVAILABLE wires during sink reservation, fixing an
  out-of-range abort reported for ECP5 locked clocks. Our running job has not
  exhibited that abort. Our fork uses different locked-tree reservation
  semantics, so the patch does not apply directly.

Do not replace our whole router2 file with the original-upstream version:
the direct diff would remove our locked-tree branching, BSCAN bounding-box
handling, bounding-box budgets and congestion smoothing. Before a memory
backport, isolate the visited-state representation changes, preserve those
features and reservation semantics, and measure sizeof(PerWireData) in both
variants. Compare real native routes/FASM across the same seeds, retained
clock guards and timing-constraint audits before considering a full job.
This is a concrete next comparison, not a validated router candidate yet.

## Isolated visited-state backport plan

Adapt only the upstream cost-sentinel/visited-flag representation from
914e84257dff. Preserve our locked-tree reservation behavior, unavailable-wire
checks, BSCAN bounding-box handling, budget and smoothing code. Guard the
compact representation with a private compile flag; default builds retain
the previous representation, including non-Xilinx builds. A and B sources
are identical; only the compact flag differs. Rebuild router2.cc only and
reuse hash-verified unchanged objects and headers from the validated PR 81
backend. Record actual sizeof(PerWireData), wire count and vector capacity.

The sentinel must not silently alias a legitimate stored cost: reject its
exact value before a visit write in the compact build. Preserve all other
float values and comparison semantics. Validate controlled native routes
at two seeds and both clock tiles, including exact FASM equality, final
placed/routed netlist equality and identical clock routing policy. Keep
route concurrency within available memory while allowing all eight CPUs.
Then repeat the complete existing 1,103-mailbox and generated-clock/phase
constraint audit with the compact binary. Measure memory; do not extrapolate
a wall-time speedup from small routing cases. Existing full jobs and design
scope remain unchanged, and their eventual images still require all gates.

## Completed memory backport and native comparison

The [isolated pair](../build/fedora-openxc7/router-wire-memory-backend-20261012T102400Z/manifest.json)
compiled router2.cc in both variants with an eight-worker pool, then linked
and passed native startup. All headers and other translation units remain
hash-verified parent objects. The default and compact sources are identical;
the private OPENXC7_ROUTER_COMPACT_VISITS define alone selects the new visit
representation. Locked-tree reservations and all existing bounding-box,
smoothing and BUFG guard logic are preserved. Non-opt-in builds keep the
previous representation. The unavailable flag is retained, so this is a
selected adaptation rather than the entire original-upstream patch.

[All six native routes pass](../build/fedora-openxc7/router-wire-memory-native-check-20261012T102600Z/manifest.json):
two seeds plus pinned bottom clock buffers, each in both variants. The
same-seed FASM and complete routed netlists are byte-identical. All 480
clock routing policy rows match, all 32 through-buffer pips remain blocked,
both clock tiles are exercised, and every driven spine has a configured
buffer. These are controlled clock/data stand-ins, not FPGA board images.

Actual sizeof(PerWireData) falls from **56 to 52 bytes**. Each case has
49,324,697 wires and vector capacity 67,108,864. Allocated wire-state bytes
fall from **3,758,096,384 to 3,489,660,928**, an exact **268,435,456 bytes
(256 MiB)** reduction. This measures the vector allocation, not total RSS.
Native case elapsed times are retained, but concurrent small cases do not
establish a full-design routing speedup or convergence improvement.

The [complete compact-backend audit](../build/fedora-openxc7/full-router-wire-memory-check-20261012T103000Z/manifest.json)
also exits 0. All 1,103 mailbox datapaths, two synchronizer clusters, 18
clock/phase domain pairs and complete path audits match the previous
guarded backend, with zero audit changes. Full MCOLS=4/ACT_ROWS=4/LANES=8,
100 MHz core and both DDR800 channels are preserved. This is a complete
unplaced pack/analysis with zero route delay; generic FF numbers and full
routed timing remain unqualified. The compact backend is a validated
candidate for further implementation work. Original full jobs still use
their original executable, and no new complete route or image is claimed.

## Channel-1 dedicated clock investigation plan

The original full route still reports six failed channel-1 MMCM-to-BUFG
dedicated arcs before its congested main loop. Their net aliases match
the complete packed design's u_ld.ldmmcm1 outputs and feedback; its explicit
physical LOC is MMCME2_ADV_X0Y6. Native wire coordinates and local BEL names
are not sufficient to infer its clock half or global BUFG site index.

Build a diagnostic clock-only fixture from the actual top module in the
area constrained JSON, retaining all four generator parameter sets, 16
buffers, their interconnections and explicit locations, the real SYS_CLK
pad AA28 and BSCAN. Add FF clock loads and hold removed reset/power/phase/DRP
control inputs inactive. This fixture investigates graph connectivity and
placement; it is not a reduced OpenTPU image or a replacement final design.

The preplacer find_bel_with_short_route traverses downhill PIPs without an
availability check, whereas route_clocks checks PIP availability. Investigate
this concrete policy difference in an isolated diagnostic backend. Export
each clock arc's physical source/sink sites, canonical wires, dedicated BFS
result and visited count, then intentionally stop before the main router.
Native exit 125 with the explicit diagnostic-complete marker is expected;
it must not be represented as route success. Compare default placement with
controlled actual physical BUFG locations before changing placement policy.
Preserve all full jobs, input RTL, reference checkpoint and hardware state.

The default diagnostic reproduces 12 failed MMCM-to-BUFG arcs across the two
DDR generators. Controlled buffer pinning makes all six channel-0 arcs
dedicated-routable, while all six channel-1 arcs fail for both I0 and I1.
Next export raw versus policy-filtered forward reachability from the actual
used generator outputs before clock binding. Retain every rejected boundary
PIP name and raw flags, physical reachable BUFG sites/inputs, visited counts
and any diagnostic traversal limit. This tests the architecture policy
directly without relaxing it for a route or creating a board image.

A concrete ordering defect is now observed: the default probe preplaces
ldmmcm0 at native X8Y199 and chooses its buffers from that position, then
applies its explicit MMCME2_ADV_X0Y2 LOC later, moving the generator to
X8Y303 without recomputing those choices. Add an opt-in early application
of explicit clock-cell LOC constraints before clock preplacement, leaving
other LOC handling unchanged. Compare the same prototype and retained
generator locations before accepting the fix. The forward diagnostics hit
their million-node limit, so missing forward targets are not proof of
unreachability. Flagged no-bitstream-config boundary PIPs are retained;
their necessity needs comparison with an exact Vivado clock-route reference.

### Early clock LOC native result

The [isolated diagnostic backend](../build/fedora-openxc7/clock-loc-diagnostic-backend-20261012T112100Z/manifest.json)
compiled and linked with unchanged headers, retaining the compact router and
all existing routing guards. The opt-in clock-loc-contract applies explicit
clock-cell locations before downstream buffer preplacement; other LOC
handling is unchanged.

The [independent same-binary off/on comparison](../build/fedora-openxc7/clock-loc-native-ab-20261012T112800Z/manifest.json)
covers the same 54 actual clock arcs and exact prototype input. With the
option off, 12 dedicated arcs fail. With it on, all six ldmmcm0 output/feedback
arcs succeed and only the six ldmmcm1 arcs remain failed. All other dedicated
outcomes are unchanged. Both explicit generator sites remain X0Y2/X0Y6;
buffer locations change, as expected when choices use the correct source.
Native exit 125 is the deliberate post-audit stop, not a complete route pass.

Pinned I0/I1 diagnostics and raw/policy forward traversals are retained.
Every forward traversal reaches its million-node bound; no missing target
is treated as proof of graph unreachability. Rejected boundary edges include
PIP_CFG_NO_BITS clock-performance and frequency-rebuffer PIPs. Their use
in a real MMCM-to-BUFG route is unproven, so no availability guard is relaxed.
Next compare the exact clock prototype in Vivado and export its physical
PIPs, then investigate source/pin/database differences for channel 1. The
early-LOC code still needs negative/location-conflict checks and a complete
full-source audit before becoming a production candidate. All original jobs,
source RTL and physical hardware state are preserved.

The next reference uses the exact 54-cell default clock prototype in a new
Vivado scratch directory. Render primitive parameters using the local
primitive library's declared types, preserve all instances with DONT_TOUCH,
retain the two explicit MMCM LOCs and SYS_CLK AA28/20 ns constraints, and
hold the same removed controls inactive. Retain native default compensation
INTERNAL where omitted. Record any explicit treatment of omitted input pins.
Synthesize/place/route only this diagnostic, verify instance retention and
both MMCM sites, then export each actual MMCM-output-to-BUFG net's physical
PIPs and route status. Do not generate/program a bitstream or overwrite the
working full MIG checkpoint. Compare real PIPs with the chipdb's rejected
edges before proposing database or availability-policy changes.

## Completed placement and logical review, October 13

The full congestion-aware placement completed with native exit 0 after
refinement iteration 72. Its placed JSON is 1,783,556,291 bytes, SHA256
`90b5c3e6bf76ae48c8ded61336c8bb6df95ef71e81269aaac29fe6698c05d18b`.
The initial strict physical-port comparison failed at a RAMD32 cell with an
added A6 tie to `$PACKER_VCC_NET`; its failed receipt and exact reviewer are
preserved. The deployed `xilinx_place.cc` explicitly adds this tie for paired
LUTs and remaps logic LUT inputs through original-port metadata, including
O6-to-O5 output relocation. The reviewer will compare original logical LUT
ports and unchanged parameters, and require each introduced unmapped A6 tie
to be VCC on a 6LUT with its actual 5LUT companion. All other cell checks,
full counts, source hashes, physical assignments and CDC checks remain
required. This plan is not yet a logical-review pass or routing qualification.

The final full review passes with 464,200 unchanged logical cells, 464,198
unique non-pseudo assignments, 179,299 FFs in 60,533 actual slice sites,
239,714 logic LUTs and 63,860 validated extra A6 selector ties. Both actual
mailbox chains occupy AFF/BFF/CFF within one slice each. The intermediate
reviewer compared a site-qualified BEL token with an unqualified FF name;
that parser was corrected and seven corrupt placements reject, including
two different slices within the same tile. Both failed receipts remain.
[Final full review](../build/fedora-openxc7/full-congestion-placement-reviewed-final-20261013T033000Z/manifest.json).

The next route must load the reviewed placed JSON using `--no-pack --no-place`,
retaining the full profile and clock/CDC contracts. The deployed `preRoute()`
reconstructs cell tags and constant nets, and the native frontend restores
all BEL bindings. However, measured delay-matrix construction is currently
in `prePlace()` only, so route-only reload otherwise falls back to its tuned
formula. The plan is an isolated xc7 backend change that restores the same
matrix build/cache behavior for a loaded placement, followed by a small
placement-reload routing comparison, immutable input checks and a full
router admission check. No original backend or running job will be changed.
[Replay preparation](../build/fedora-openxc7/full-congestion-route-replay-preparation-20261013T033400Z/manifest.json).

Replay preparation also confirms that `jsonwrite.cc` and the native JSON
frontend do not serialize generated `ClockConstraint` objects. The packed
netlist has only the external/base clocks from XDC after reload. The isolated
xc7 `preRoute()` change will therefore call the existing
`XilinxPacker::generate_constraints()` for a loaded placement, retaining the
qualified clock-feedback mode, then run the same delay-matrix build/cache
logic as `prePlace()`. It will not repack, replace BELs, change parameters or
change logical connections. The fixture must prove restored generated clock
periods/high/low values, matrix cache equality, native routing and unchanged
placements. The full image still requires complete route and numerical
timing qualification. Only `himbaechel/uarch/xilinx/xilinx.cc` is changed in
the isolated source copy; all other source and link inputs are hash checked.

The first replay fixture failed its generated-clock comparison: `xdc` is
parsed by the pack stage, so skipping packing left the reloaded design with
no base constraints. Its native exit was 0 but its clock audit was empty;
the fixture therefore rejected it. The corrected isolated candidate also
reapplies the unchanged XDC before regenerating derived clock constraints.
The initial candidate and failed fixture receipt remain preserved.

The replay candidate also offers an optional exact native binding audit
prefix. `preRoute` and `postRoute` write every non-pseudo cell and its
`Context::nameOfBel` value before and after routing. The fixture compares
both tables with the complete original placed JSON bindings; it does not
rely on the routed export's different site/bel spelling or on just a BEL
lane suffix. The hook is disabled unless explicitly requested. It changes
only audit output and is intended to cover all full-design bindings on replay.

Reapplying the full XDC on a loaded placement was rejected by the original
parser because PACKAGE_PIN and IOSTANDARD already exist. That native exit
125 and failed fixture are preserved. The corrected replay instead requires
an explicit `placed-replay-clock-xdc` file containing exactly the one-line
`create_clock` commands extracted from the immutable original XDC. Reviewed
pin properties and physical assignments remain in the placed JSON. Unknown
XDC commands reject extraction; no new IO property is applied at route time.
Full input-XDC hash equality remains required, and native before/after binding
audits must match every original non-pseudo assignment.

All three clock-only replay cases completed with native exit 0, matching
39 generated constraints and exact pre/post native bindings. Rebuilt and
cached matrices produced byte-identical FASM. The explicit disabled-matrix
case used different routing PIPs/features (32 removed, 35 added), which is
allowed because its estimate changes. An overstrict test requiring all
three images to be identical was rejected and preserved. The corrected
check requires rebuilt/cached equivalence, while disabled mode must retain
all clocks, bindings and native clock-driver legality and must not build a
matrix. A fresh complete run is in progress under the qualified-native-check
receipt; these small fixtures do not prove full accelerator timing closure.

The corrected 57-cell replay fixture passes all 39 restored clock checks,
exact native bindings and matrix rebuild/cache comparison. The full route
from the reviewed placement has started under PID 394196/start 21535138,
controller session 38127. The 38-clock full audit preserves SYS/core/JTAG
periods and 2.5 ns PHY/10 ns channel clocks. All 464,198 native reloaded
bindings match the original reviewed JSON. No completed main route iteration
or native full image exists yet. The phase-domain coverage summary is
10 known/2 unknown versus the previous run's 16/2; numerical timing remains
unqualified and that difference needs review. Original route jobs remain
untouched.

The newest full replay trial was intentionally stopped after source review
confirmed that `initialize_dsp_timing`, `initialize_clock_timing` and
`initialize_serdes_timing` run only in the pack stage. Skipping packing
left the unique_ptr timing models unset, causing the domain-pair count
to drop from 16 known/2 unknown to 10/2. Native exit -15 is the requested
SIGTERM, not a fit failure. The four original jobs remain untouched, and
the fully reviewed placement is retained. The next isolated replay source
will call those existing initializers, regenerate nominal waveform metadata
and revalidate the supplied software-phase and mailbox-datapath contracts.
No cell placement, connectivity or parameter change is authorized by this
restoration. Qualification must compare complete domain pairs and budget
values with the original full-design gate before the main route is accepted.

The model-enabled replay fixture rejected before placement because its raw
clock-only prototype represents PWRDWN as non-inverted constant zero, whereas
all four characterized full-design clock primitives use inverted constant
one after packing. The effective inactive value is identical. The next fixture
will explicitly derive this polarity from the frozen full clock inventory,
verify the XOR equality for all four controls and stage a separate diagnostic
JSON. Original full-design inputs, characterized timing tables and previous
fixture receipts remain unchanged. This prepares a valid model-enabled test;
it does not extend timing models to unsupported configurations.

A separate native pack-only diagnostic completed with exit 0. It confirms the
prototype additionally packs tied-low RST, PSEN and PSINCDEC as inverted
constant one, whereas the full-design model expects non-inverted dynamic
inputs. The model-enabled fixture will expose these as diagnostic inputs;
this changes the diagnostic control behavior and is not described as logical
equivalence to the old held-inactive prototype. Clock generators, parameters,
locations, frequency targets and the original full accelerator remain fixed.
The diagnostic fixture is never a hardware image.

The strengthened fixture completed with native exit 0 in every case. It uses
an existing core-clock register output for diagnostic RST/PSEN/PSINCDEC
controls; a trial adding unbuffered I/O inputs was rejected and preserved.
The full-run controller will now require the model-enabled domain-equivalence
receipt and a hash-pinned full timing-contract reference. It must compare all
18 full-design domain pairs and budgets, including 16 known and two unrelated
pairs, and confirm reimport of all 1103 mailbox limits before accepting replay.
These checks preserve existing numerical timing limitations and do not imply
route convergence or timing signoff.

The model-restored full replay entered its main router loop with both live
guards passing. A fresh streaming audit confirms all 464198 loaded native
bindings exactly match the reviewed placement. Before any replay image may
be assembled, the primitive checker will optionally accept an isolated
candidate plus its completed model-enabled replay receipt, verify the
candidate's exact parent and sole xc7 source delta, then rerun the five
existing primitive witnesses and strict frame assemblies with that candidate.
The original full timing-contract reference remains explicitly attributed
to the parent binary. Existing static-route/image manifests are preserved.
The checker is not live and its source is not in the old assembly inventory.
One fixture at a time limits memory while the full routers remain live.

At 12:45:33 HKT the kernel recorded global OOM and killed native PID 157975.
The user service log then recorded OOM failure and stopped the shared tmux
scope; all five native route PIDs, their controllers and the new primitive
check disappeared without terminal route receipts. No route or timing result
is accepted. The primitive check was launched with approximately 3 GiB RAM
available and almost no free swap; its device-wide router allocation exceeded
that headroom. Scheduling that check concurrently was an avoidable error.
Evidence is preserved under host-oom-process-loss-20261013T045000Z.
Recovery runs primitive qualification sequentially in an independent user
service (8 GiB RAM cap, 4 GiB swap cap), then only the latest model-restored
full route from the preserved reviewed placement in a separate service
(24 GiB RAM cap, 8 GiB swap cap). All eight CPUs remain available. Historical
comparison jobs will not be relaunched. Old manifests and unknown exit codes
remain preserved with explicit process-loss receipts; no result is invented.

Image preparation for the placement replay requires a separate adapter:
the frozen static-route preparation helper and its inventory will remain
unchanged. The adapter retains complete mapped-graph/LOC provenance, source
hashes, full profile, assembly database and tool pinning. It additionally
requires the candidate's five-primitive/frame review, the full-placement
review, the actual restored 18-domain/1103-limit gates and exact loaded
bindings on the selected live native owner. Its route command must use the
reviewed placed JSON with no-pack/no-place, not the static command. The
assembler may accept this preparation only after the corresponding replay
controller records actual native route exit 0 and all full binding/domain
checks. Packet/frame/ECC checks retain their existing strict behavior and
numerical timing remains explicitly unqualified until separately validated.

The image follow-up will run as a separate user service with 16 GiB RAM
and 4 GiB swap limits. It watches the selected route unit invocation and
exact saved native PID/start identity. It must wait through live routing
and controller finalization, reject failed/lost terminal results, and invoke
the existing strict image assembler only after both the full replay receipt
and user-service exit prove actual success. The prepared input manifest and
assembler source are pinned at watcher startup. A one-shot check while the
current route is live must return 2 without creating an image. No hardware
programming or BPI flash action is part of this follow-up.

The retained-result probe returns 2 on the actual live route with no image
created. The automatic image follow-up is now running separately and waiting.
A task-specific RemainAfterExit=yes drop-in preserves the route service's
result after exit; daemon reload kept its MainPID, invocation/start identity
and native owner unchanged. Live source inspection showed that completed
transient units otherwise discard their invocation/start fields, so the
watcher verifies the retained monotonic start plus the live invocation.
It also validates the native owner's cgroup and controller PPID at startup.
The latest 40-second sample advanced 7969 CPU ticks, retained zero native
swap use and produced no full terminal route outputs. USB remains absent.
