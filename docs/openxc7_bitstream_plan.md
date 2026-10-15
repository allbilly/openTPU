# Prepare an openTPU bitstream with OpenXC7

The [CRC qualification and guarded follow-up](openxc7_bitstream_crc.md)
now verifies both Vivado reference CRC pairs. A separate native fixture copy
passes two CRC checkpoints with all frame data unchanged. A third image
follow-up waits for the full DSP-corrected image and will create a separate
CRC-protected candidate; timing and hardware readiness remain pending.

See the [measured routing plot and conditional estimates](openxc7_routing_estimate.md).
The October 13 23:41 HKT snapshot projects 74–77 additional hours to zero
remaining flags at the recent 1–2 hour rates, or 210 hours at the slower
half-hour rate. Phase changes and congestion retries prevent a dependable
full-routing completion date.

## Current image runtime, October 13

Use the X-Ray virtual environment's executable path literally; do not resolve
its symlink before launching Python. The base interpreter has identical
executable bytes but a different `sys.prefix` and cannot import `fasm`. A real
corrected-DSP fixture assembly caught this before full-route assembly began.
The original failure receipt remains preserved.

[Qualified runtime preparation](../build/fedora-openxc7/image-runtime-fixed-20261013T140000Z/manifest.json)
keeps all original backend/RTL/placement/profile gates and the DSP map. It
extends the assembly inventory with the literal venv command, `pyvenv.cfg`,
1,609 runtime files, and three source variants containing only the invocation
or assembler-filename change. Native imports confirm the correct `sys.prefix`.
The [corrected 64-DSP fixture image](../build/fedora-openxc7/dsp-corrected-fixture-image-runtime-fixed-20261013T140200Z/manifest.json)
then passes strict assembly in about 12 seconds and bit generation in under
one second. Its frames are byte-identical to the actual new native emitter.
Independent packet/payload/ECC comparison covers all 46,336 legal frames.
This does not establish a full-board image, independent CRC or numerical timing.

Only the two waiting image services were replaced, before either had started
assembly. The live native route, observer and hardware watcher retain their
identities. [Intentional waiter replacement receipt](../build/fedora-openxc7/image-followup-runtime-switch-20261013T140400Z/manifest.json).
Current follow-ups consume `image-runtime-fixed-20261013T140000Z/image-preparation.json`
and `dsp-preparation.json`; earlier waiters and preparations are history.


Preserve the running full-design route and completed placement. Use the
[tested Vivado MIG image](vivado_bitstream_guide.md) for hardware work while
OpenXC7 remains under qualification.

Snapshot: October 13, 2026. The requested full profile remains
**MCOLS4 / ACT_ROWS4 / LANES8 / VPU_CL2 / MXU_IMPL2 / core100 MHz / dualDDR800**.
No design-size reduction, lower clock, `--force`, or timing-failure override
is selected.

## Why this design uses LiteDRAM

The installed OpenXC7 backend/database lacks several hard-PHY resources used
by the working MIG implementation, including PHASER and PHY FIFO/control
resources. Importing a Vivado netlist does not add that support. The approved
OpenXC7 path therefore uses LiteDRAM at DDR800, preserving the full accelerator.
The DDR1066 MIG image is the physical functional reference; the separate
Vivado DDR800 LiteDRAM implementation is the matched implementation reference.

See [MIG compatibility evidence](openxc7_vivado_reference.md#hard-phy-resource-coverage).

## Milestones and acceptance evidence

| Step | Current state | Evidence needed to proceed |
| --- | --- | --- |
| Freeze full RTL, generated DDR core, XDC and tool/database revisions | Done | Source hashes and full configuration agree |
| Independently synthesize/map the full design with Yosys | Done | Native exit 0; complete compute, DSP/BRAM/PHY inventory and source equivalence |
| Qualify carry, clock, DSP, serializer and placement replay corrections | Selected replay/primitive gates passed | Exact tested backend/database, logical graph and timing-domain restoration |
| Full congestion-aware placement | Done, about 3h12m | All 464,200 logical cells preserved; 464,198 non-pseudo bindings reviewed |
| Route from saved placement | Running | Native exit 0; full routed JSON, timing report and FASM; final binding/clock-driver checks |
| Resolve upstream DSP FASM fixes | Six register/MASK mode frame checks passed | 51 target bits match all 717 Vivado reference DSPs; other fields and corrected full image pending |
| Qualify numerical timing for the full routed design | Pending | Full clock/CDC/FF/DSP/PHY coverage, setup/hold/pulse and phase/skew checks |
| Assemble and check the full OpenXC7 image | Prepared, waiting for route | Strict FASM-to-frames, packet/frame/ECC and full provenance checks |
| Execute on the FPGA | Pending | Guarded SRAM load, full DDR/ECC tests, kernels/vectors/stream, compiled model tokens matching ISA |

Passing a primitive fixture or a subset of timing paths does not replace a
full-design result. The queued assembler produces an **offline, timing-unqualified
candidate**; it does not authorize hardware programming.

The [full FF absolute-site inventory](openxc7_vivado_timing.md#full-native-ff-absolute-placement-october-13-2302-hkt)
now covers all 179,299 preserved-placement registers. Its 60 observed location
classes exist in the characterization table, and all 597,200 fabric FF BELs
cross-check with X-Ray. This closes placement-location coverage; routed input-mux,
electrical and full numerical timing coverage remain pending. The live router
and prepared image pipeline are unchanged.

## Preserve and observe the current run

Completed placement:

```text
build/fedora-openxc7/full-congestion-heap-placement-20261013T001000Z/placed.json
SHA256 90b5c3e6bf76ae48c8ded61336c8bb6df95ef71e81269aaac29fe6698c05d18b
```

Active route directory:

```text
build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/
```

Native PID **400903**, start ticks **21826315**, started October 13 at
**12:54 HKT**. The command reloads the reviewed placement with
`--no-pack --no-place --router router2 --threads 8 --freq 100.0`.
Its [manifest](../build/fedora-openxc7/full-congestion-model-restored-isolated-route-20261013T045700Z/manifest.json)
pins the entire actual command's input lineage. Inspect processes before
interpreting historical `RUNNING` manifests.

```bash
# Run from the root of your OpenTPU checkout.
systemctl --user status opentpu-full-replay-route-20261013t045700z.service
systemctl --user status opentpu-replay-image-followup-runtime-20261013t140400z.service
systemctl --user status opentpu-route-metrics-20261013t104000z.service
python3 build/fedora-openxc7/goal_current_route_wait.py --wait-seconds 45
```

The route has a **24 GiB RAM / 8 GiB swap** service limit, all eight CPUs
allowed, and no CPU quota. Router2 hardcodes sequential worker batches of
**4 quadrant / 2 vertical / 2 horizontal**, followed by serial cross-partition
and retry work. The current horizontal phase can occupy two cores. Changing
`--threads` does not change those fixed batch counts.

The previous failure was **global host OOM**, with RAM and swap exhausted by
concurrent jobs. It was not a smaller cgroup limit. The current isolated route
has memory headroom and zero swap usage. Keep one substantial router running;
additional swap is not justified by the current measurements.

### Measure routing progress every five minutes

The active read-only observer is
`opentpu-route-metrics-20261013t104000z.service`. Its
[latest sample](../build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/latest.json)
and per-sample receipts record:

1. **Remaining connections:** unique `(driven net, physical sink wire)` pairs
   without a routed flag. Duplicate logical arcs to one sink are combined.
   This measures routing state, with final congestion/legality still pending.
2. **Retry evidence:** deferred failures across all nine routing batches,
   active-worker counts kept separately, per-net congestion failure counts,
   and previously routed connections now missing a routed flag.
   The running binary stores no cumulative rip-up-call counter. Observed
   routed-to-unrouted transitions are a **lower bound**, not an exact total;
   a rip-up and reroute between samples can be invisible.
3. **Search size:** largest forward/backward queue and largest combined queue
   across active workers, plus sampled maxima and dirty-wire counts.
   These are instantaneous samples, not the maximum between samples.

The observer briefly stops the process for a consistent read-only memory
snapshot, detaches, verifies the same PID/start and resumed execution, and
compares connection identities before counting state transitions. It calls
no functions in the inferior and modifies no routing state. Initial complete
samples took about 11 seconds; the observer is capped at 2 GiB RAM.

| Sample, October 13 HKT | Remaining connections | Change | Observed routed-to-unrouted | Deferred active-worker failures | Largest combined queue |
| --- | ---: | ---: | ---: | ---: | ---: |
| 18:40 | 431,793 | Baseline | Baseline | 2 | 2,337,200 |
| 18:45 | 429,450 | -2,343 | 0 | 2 | 1,402,686 |
| 18:50 | 427,826 | -1,624 | 0 | 2 | 1,160,546 |
| 18:55 | 426,306 | -1,520 | 0 | 2 | 452,503 |
| 19:00 | 423,717 | -2,589 | 0 | 2 | 475,529 |
| 19:05 | 422,013 | -1,704 | 0 | 2 | 272,130 |
| 19:16 | 420,031 | -957 | 0 | 2 | 627,357 |
| 19:26 | 419,009 | -515 | 0 | 0 | 1,022,399 |
| 19:36 | 418,115 | -173 | 0 | 0 | 838,127 |
| 19:46 | 416,467 | -1,395 | 0 | 0 | 84,470 |
| 19:51 | 416,384 | -83 | 0 | 0 | 171,988 |

This first comparison supports useful progress. It does not establish eventual
convergence or a trustworthy ETA. If remaining connections flatten over several
samples while failed-net evidence and queue sizes grow, investigate the
specific nets, bounding boxes, search budgets, congestion costs and heuristics
before deciding whether a new routing experiment is warranted.

At 19:12 and 19:16 HKT, the expanded observer read all nine batch contexts:
**31 deferred failed nets** total (28 quadrant, 1 vertical, 2 horizontal).
Earlier counts of 2 cover only active workers; they are not comparable to
the new all-batch total. These are pending local failures awaiting serial
fallback, not terminal failures or a cumulative rip-up count. The serial
cross-partition batch contains 70,693 scheduled nets; that batch size is not
an independently measured count of unrouted connections.
[Expanded coverage review](../build/fedora-openxc7/routing-five-minute-observer-20261013T104000Z/all-batch-coverage-review.json).

Queue values are now acquired directly from `route_net` frames, which also
exist during serial cross-partition/fallback routing. That acquisition path
was exercised on both live parallel workers; the actual serial phase remains
pending. Prior observer sources were archived before replacing the observer
only. The native route PID/start, controller and service invocation remain
unchanged, and the five-minute schedule is active.

At 19:26 HKT the 12,139-net horizontal worker had finished. One worker
remained, with 4,592 nets after its current net in the 14,911-net batch. The
all-batch deferred count remained 31; the active-worker count fell to zero
because its two failures are now in a completed worker's batch. Serial
cross-partition work and fallback retries still follow. This is a batch
milestone rather than a whole-route completion percentage.

## Upstream upgrade plan

The fresh [upstream review](../build/fedora-openxc7/upstream-upgrade-review-20261013T102959Z/summary.json)
checked `main` at **1e64f41043ca9df9b39ff23e3ee4c7fff2767042**, committed
October 12 at **20:10 UTC**. Our recorded base is **c68c135**, with local
qualified changes; this is not a clean latest-main binary. Upstream is 73
commits ahead, with no changes under `common/route/` or `common/place/` in
that comparison. Architecture changes may affect particular designs, but
the comparison demonstrates no general routing speedup.

The [latest merge](https://github.com/openXC7/nextpnr/commit/1e64f41043ca9df9b39ff23e3ee4c7fff2767042)
fixes DSP48E1 `MASK`, `ZADREG` and `ZDREG` FASM encoding. The active emitter
lacks these specific changes. They matter to correct configuration of the
717 DSPs, and must be reviewed before using an OpenXC7 image on hardware.

Prepare changes in a separate candidate source tree and binary. Retain the
current route's backend, database and outputs. Validate every affected DSP
parameter combination against Vivado, preserve the clock/carry/serializer
corrections, rerun affected primitive/frame checks, and re-pin full-image
provenance. Do not overwrite the live executable or silently replace its
assembler inputs. Whether an upgraded emitter can reuse routed JSON must be
proved on a complete replay; a checkpoint's existence alone is insufficient.

A [separate three-fix patch](../build/fedora-openxc7/dsp-encoding-fix-staged-20261013T105859Z/dsp-encoding.patch)
is now staged against the exact active emitter. Its dry-run context check
passed and the original source hash is unchanged. It has not been applied,
built or qualified. Additional upstream DSP-emitter differences still need
review; these three changes are not a claim of complete DSP configuration
coverage.

The subsequent [complete 717-DSP parameter review](../build/fedora-openxc7/dsp-encoding-impact-20261013T120252Z/manifest.json)
scanned all 464,200 packed cells and verified the packed input's SHA256.
It found differences from upstream's expected encoding on **403 A-cascade
register settings**, **562 B-cascade register settings**, and **189 DSPs
whose default MASK is omitted**. ZADREG/ZDREG changes from the latest merge
do not change this particular full design's recorded configurations. Counts
overlap across features; they must not be added to obtain a DSP cell total.
This is parameter-level impact analysis, not measured native FASM, frame,
timing or physical arithmetic qualification.

A [full DSP-emitter function patch](../build/fedora-openxc7/dsp-full-emitter-staged-20261013T120704Z/dsp-full-emitter.patch)
now supersedes the three-fix patch for candidate preparation. Its replacement
function matches the reviewed upstream commit exactly; the downloaded source
was checked against its Git blob hash. All non-DSP-emitter source bytes are
preserved. Patch-context dry run passed and the active source hash is unchanged.
The patch was not installed in the live backend. A separate
[DSP-emitter candidate](../build/fedora-openxc7/dsp-full-emitter-candidate-20261013T123000Z/manifest.json)
has now compiled and linked successfully, with CLI startup exit 0. The build
took about 29 seconds and peaked at 1.65 GiB under a 4 GiB service cap. It
recompiled only `fasm.cc`, verified and reused the other cached inputs, and
preserved all 1,515 source files except the reviewed DSP-emitter function.
The live router's binary, source, placement and invocation remain unchanged.
The targeted native DSP register/MASK emission and actual Vivado frame
comparison now pass, as detailed below. Other fields and corrected full-image
provenance remain pending; these checks do not qualify an FPGA image.

## Finish the route and build the image

The queued follow-up checks native exit **0**, the full terminal route receipt,
successful retained systemd service result, and all pinned inputs before
calling `tools/openxc7_clock_image_assemble_runtime.py`. Its output directory is:

```text
build/fedora-openxc7/replay-image-followup-runtime-20261013T140400Z/image/
```

The route must produce `route.exit`, `routed.json`, `timing.json`, and
`design.raw.fasm`. Assembly must pass strict feature mapping, packet structure,
frame data, ECC and source provenance. Current numerical timing remains
unqualified; independent CRC verification is also not yet implemented.
Review the newly identified DSP fixes before treating any assembled result
as a final candidate.

After full timing/configuration qualification, use a fresh guarded SRAM
programmer for that exact OpenXC7 image, then repeat the same full hardware
checks used for Vivado. Compare returned data and model tokens against the
ISA reference. A plausible model response is insufficient.

Overall OpenXC7 work has already taken **days**, including development and
interrupted runs. The earlier 12–24-hour routing allowance was a low-confidence
planning estimate, not a promised completion time. Update estimates from
observed connection progress and completed congestion iterations, while
keeping transfer time and hardware validation separate.

See the current [progress table](../progress.md),
[Vivado hardware receipts](fedora_vivado_jtag_results.md), and
[router investigation](openxc7_router_review.md).

### DSP-emitter qualification now in progress

First run the saved 64-DSP, four-chain cascade witness with the separately
built emitter and the corrected clock database. Keep every input, seed,
constraint and non-emitter backend component fixed. Compare native cell
parameters, connections, BELs and net routing against the qualified parent,
then assemble the resulting FASM strictly. Any configuration difference must
be confined to DSP features; unchanged routing must be demonstrated rather
than assumed. This witness covers its actual DSP modes, not all 717 full-board
instances. Next cover the six full-board register/MASK configurations and
compare DSP configuration bits to a Vivado-generated reference at matching
sites. The live full route and its pinned image preparation remain unchanged.

### Targeted DSP encoding qualification completed, October 13

The separate candidate reproduced the saved 64-DSP cascade's cells,
connections, BELs and routes exactly. Only 96 DSP FASM features were added;
strict assembly exited zero. [Native cascade receipt](../build/fedora-openxc7/dsp-emitter-cascade-check-20261013T125000Z/manifest.json).

A fixed-placement native probe then exercised all six full-board
AREG/ACASCREG, BREG/BCASCREG, ADREG/DREG, USE_DPORT and MASK configurations.
All 294 cell parameters, all 64 DSP connections by named net, and all
non-pseudo BEL bindings survived reload and routing; strict assembly exited
zero. JSON bit numbers change during reload and empty ports disappear, so
raw numeric connection equality is inappropriate. The initial failed
comparison is preserved; the corrected review checks named DSP connectivity.
[Six-mode native review](../build/fedora-openxc7/dsp-emitter-six-config-reviewed-20261013T131100Z/manifest.json).
This establishes the DSP witness, not whole-fabric graph equivalence.

Vivado opened the completed full DDR800 reference checkpoint and exported
register/MASK properties and locations for all 717 DSPs. The six mode counts
are 8, 392, 128, 3, 152 and 34, matching the packed full-design inventory.
The comparison reads actual uncompressed Vivado configuration payload and
strictly assembled native frames using the pinned Project X-Ray feature
coordinates. All 51 selected bits per configuration match all 717 reference
DSPs, with zero mismatches. The 136 vendor frames containing these target
bits pass ECC; an intentionally corrupted target-frame copy is rejected.
[Actual frame comparison](../build/fedora-openxc7/dsp-frame-comparison-20261013T131300Z/manifest.json).

Coverage is specifically ZAREG_2_ACASCREG_1, ZBREG_2_BCASCREG_1, ZADREG,
ZDREG, USE_DPORT and the 46 encoded MASK bits. Other DSP fields, the full
OpenXC7 image, numerical timing and physical execution remain pending. The
generic native-frame ECC routine does not qualify every Vivado frame; its
out-of-scope discrepancies are retained in the comparison receipt. Neither
independent configuration CRC nor whole-Vivado-image ECC was claimed.

Next preserve the terminal full route and qualify corrected full-image DSP
configuration with fresh provenance. Do not silently replace the binary or
source pinned by the live router and queued old-emitter assembler. This
DSP-only emitter change provides no demonstrated router speed improvement.

### Preserve routing when correcting full-image DSP encoding

The candidate changes only the DSP FASM writer. Qualify a separate FASM
correction step using actual old-emitter and new-emitter native output for
the same six-mode placed fixture. Require identical native cell parameters,
BELs and routed nets, and require the corrected old FASM to reproduce every
non-comment feature of the new native FASM. Pin the native old/new mode
vectors and the all-717-DSP Vivado frame comparison.

Prepare an exact map from all 717 DSPs in the reviewed full placement to
physical FASM prefixes. A later correction may replace only the 51 reviewed
register/MASK feature bits at those DSPs, after checking the old features
against the observed old-emitter vectors. Preserve every other FASM line.
Reject unexpected configurations, duplicate sites, missing features, changed
source hashes or incomplete native route receipts. Reassemble and inspect
the corrected full image with fresh provenance; keep the original native
FASM and the existing queued assembler unchanged. This path must pass the
small native differential fixture before being used on a terminal full route.

The native differential correction is now qualified. It reproduces all
non-comment new-emitter features for the exact 64-DSP fixture and rejects
a removed register feature. Streaming all 464,200 placed cells yields an
exact 717-DSP correction map. Internal BEL names are resolved through the
qualified chip database and cross-checked against all 1,920 X-Ray DSP sites;
internal site labels are not assumed to be absolute board coordinates.
[Prepared full DSP correction](../build/fedora-openxc7/dsp-fasm-correction-prepared-20261013T132700Z/manifest.json).

A separate follow-up may assemble the corrected image only after the native
route and existing offline image pipeline succeed. It verifies the original
image's source/database/tool inventory, retains original outputs, preserves
all unrelated FASM lines including the validated VREF configuration, and
repeats strict frames, packet, payload/ECC and provenance checks. It must
report numerical timing and hardware readiness as pending.

The separate follow-up is now active:

```bash
systemctl --user status opentpu-dsp-image-followup-runtime-20261013t140400z.service
cat build/fedora-openxc7/dsp-corrected-image-followup-runtime-20261013T140400Z/manifest.json
```

[Corrected-image follow-up receipt](../build/fedora-openxc7/dsp-corrected-image-followup-runtime-20261013T140400Z/manifest.json).
It pins both original service invocations and native PID/start identity.
A direct call to the qualified correction tool while the route was live
returned 2 and created no output directory. The follow-up is waiting; its
full-image assembly branch has not executed, and no FPGA image is yet
qualified by this new branch. The active route, five-minute observer and
original image follow-up remain unchanged.
