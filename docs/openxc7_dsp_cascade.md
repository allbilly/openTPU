# XC7 DSP cascade placement correction

The full DDR800 OpenTPU synthesis passed on 2026-10-07. Placement then failed
on `g_ask[3].g_p[96].u_pe.u_dsp`, the root of a 16-DSP MXU cascade. The failed
run is `build/fedora-openxc7/ddr800-ff-edge-pipeline-20261007T075827Z`.
Its mapped input remains the complete MCOLS=4, ACT_ROWS=4, LANES=8 accelerator
and both 72-bit DDR channels, with 717 DSPs and the real calibration CPU.

## Evidence and assessment

The donor's `pack_dsp_xc7.cc` constrains consecutive DSP pairs to tile rows
exactly five rows apart. The actual xc7k480t chip database has five-row steps
within groups and six-row steps across intervening clock rows. Each examined
DSP column has 64 steps of five rows and 15 steps of six rows. Consequently,
the existing constraints admit zero placements for a 16-DSP cascade, even on
an otherwise empty device. Raising the placement attempt limit cannot fix it.

The two DSP BEL z values, 6 and 25, match the actual database. The database
already contains absolute DSP site coordinates; regenerating it or changing
these z values is unnecessary. The preceding FF clock-edge correction is
independent and must remain present.

## Implementation plan

Use himbaechel's existing virtual `getClusterPlacement` interface for XC7 DSP
clusters. Cache adjacent DSP BELs by their absolute DSP site X/Y coordinates
from the actual database, and follow consecutive site Y values from each
candidate root. This makes placement follow real rows across clock-row gaps.
Retain the current packer's chain order and root alignment. Delegate all
other clusters to the existing upstream implementation. The packer's nominal
tile offsets remain estimates for analytical placement; final legality uses
the actual BEL sequence.

Build this correction in a new isolated source/build directory, retaining the
validated FF edge change and leaving the donor and earlier evidence intact.
Recompile every translation unit depending on the changed Xilinx class
declaration, and record source, object and binary hashes.

Verify the geometry against the actual chip database. Place and route real
16-DSP cascade probes crossing clock rows in left and right DSP tile columns,
and check consecutive site coordinates and dedicated cascade connections.
Then route the unchanged full mapped checkpoint, SHA256
`074ed71da056d131259199dcdd5fdfa78ccfcbd42be852de1a97d8e53f5b3a87`.
No full synthesis replay is required for this backend change.

Successful placement or routing will not establish physical-board operation,
DDR reliability or qualified numerical timing. Strict frame assembly,
hardware tests and the remaining timing-model work remain required.

## Current run and revalidation

The first backend compiled and linked successfully. Its corrected geometry
cache contains 1,908 physical DSP-to-next-DSP entries, and the core dump
confirms all 15 successors exist for the pinned failing probe root. The probe
also exposed a separate LOC handoff defect: Xilinx `apply_loc_constraints`
binds each root before the placer runs, without supplying the placer's `BEL`
attribute. The generic placer's existing pinned-cluster support consequently
does not see these roots. Their 15 children remain unplaced, and `total_hpwl`
throws `dict::at()`. A live GDB breakpoint confirms the new cluster-placement
override was never called before that crash.

Correct this XC7 handoff by setting the resolved `BEL` attribute for each
LOC-constrained DSP cascade root. Preserve the upstream placer's existing
cluster binding algorithm. Reject a root LOC that conflicts with the packer's
absolute DSP z alignment. Only `xilinx.cc` needs this additional body change:
reuse the successful build's other objects after verifying their input/source
hashes, with no class-declaration or full-synthesis change. Rerun the same
four real LOC-constrained probes and strict frame gate before the full route.
The original failed probe helper and both failed controllers are retained.

The corrected LOC backend passed the real probe: all 64 DSPs occupy the
expected consecutive sites, all 2,880 PCOUT-to-PCIN bit connections have
dedicated routing evidence, and both rising/falling FF event pairs remain
correct. Project X-Ray strict frame assembly also exited zero. The successful
probe is in
`build/fedora-openxc7/ddr800-dsp-loc-pipeline-20261007T140941Z/cascade-probe`.
The controller reused the original mapped checkpoint. Packing and initial
analytical placement passed, but main placement failed at 14:52 UTC on
`$7211.genblk1.slice[1].genblk1.carry4$split$muxcy2$PACKED_CARRY4$` after
10,001 attempts. The full run is terminal FAIL, with no routed design or
bitstream. This is a separate carry-placement failure; the passing DSP/FF
probe and strict frames remain valid. Qualified timing and physical-board
operation remain unproven.

A small two-CARRY4 probe with the same padded upper two bits passed actual
placement in `build/fedora-openxc7/carry-padding-repro-20261007T150946Z`.
It therefore does not reproduce the full failure or establish its cause.
The preceding probe failed only because its I/O pins were unconstrained;
both attempts are preserved. The full-design diagnostic captured the actual
root at `XilinxImpl::prePlace` and stopped before analytical placement. Its
pointer is `build/fedora-openxc7/carry-cluster-capture-active.json`.
The root has no outputs; [the carry correction](openxc7_carry_padding.md)
omits only unobserved trailing stages. Its actual routed probe passes all
256 input combinations against the XC7 models. The new controller reuses
the full mapped checkpoint after the required carry/DSP/FF/frame gates.

The completed geometry build is
`build/fedora-openxc7/dsp-cascade-backend-20261007T133043Z`. Its 14 Xilinx-header
dependent translation units were rebuilt with the donor's recorded compiler
options. The database audit is
`build/fedora-openxc7/dsp-cascade-geometry-20261007T1330Z.json`:
1,920 DSP sites; zero fixed-stride 16-DSP roots; 876 consecutive-site roots.

The additional LOC body correction is built separately in
`build/fedora-openxc7/dsp-loc-backend-20261007T140905Z`. The current durable
controller is
`build/fedora-openxc7/ddr800-dsp-loc-pipeline-20261007T140941Z`. It waits for
the backend, routes four separate 16-DSP chains rooted at DSP48_X1Y0,
DSP48_X1Y20, DSP48_X0Y0 and DSP48_X0Y20, checks all 2,880 PCOUT-to-PCIN bit
connections and the retained rising/falling FF events, then assembles the
probe's frames strictly. Only a passing probe advances to the full route
and strict full-image assembly. Its `pipeline.json` records failure as soon
as any required stage fails. Existing source/core/helper hashes are checked
before each stage; the earlier failed pipeline is preserved.

To inspect live state from the checkout:

```sh
cat build/fedora-openxc7/ddr800-pipeline-active.json
cat build/fedora-openxc7/dsp-cascade-backend-active.json
systemctl --user status otpu-dsp-loc-backend-20261007t140905z.service
systemctl --user status otpu-ddr800-dsp-loc-20261007t140941z.service
```

To build a new correction snapshot, supply a new output directory:

```sh
python3 tools/openxc7_dsp_cascade.py \
  --previous build/fedora-openxc7/ff-edge-backend-20261007T071439Z \
  --out build/fedora-openxc7/dsp-geometry-revalidation
python3 tools/openxc7_dsp_loc.py \
  --previous build/fedora-openxc7/dsp-geometry-revalidation \
  --out build/fedora-openxc7/dsp-cascade-backend-revalidation
```

Use `tools/openxc7_dsp_cascade_check.py --help` for a separate actual
mapped/routed probe. All probe and build tools require a new output directory
and preserve their manifests, commands, exit codes and logs.
