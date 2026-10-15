# XC7 unused carry padding

The full DDR800 OpenTPU run failed main placement at 14:52 UTC on
`$7211.genblk1.slice[1].genblk1.carry4$split$muxcy2$PACKED_CARRY4$`.
The preceding full synthesis, DSP cascade routing and strict probe-frame
assembly passed. Their artifacts and the failed full run remain preserved.

## Evidence and assessment

The actual full-design cluster was captured under GDB at
`XilinxImpl::prePlace`, after packing and before placement. Its saved data is
`build/fedora-openxc7/carry-cluster-capture-20261007T151238Z/cluster.json`.
The capture finished successfully at 15:19 UTC, and the diagnostic process
was then stopped before placement.

The failing root has no connected O or CO output. Its four LUT children are
one-input ground feed-throughs at distinct z positions 0, 1, 16 and 17,
each feeding only this root. The root's CYINIT consumes the preceding carry's
observable CO[5], but produces no observable result. This is an unused
two-bit padded tail of the six-bit comparator at `rtl/seq/otpu_seq.sv:217`.
It has no child carry, FF or externally consumed LUT output.

The current splitter always creates all four MUXCY/XORCY stages of every
mapped CARRY4, even when the upper output nets have no users. That introduces
this unused carry cluster and its four LUTs. A small padded probe passes on
the old backend, so these observations do not prove an intrinsically illegal
cluster or establish why the full placer exhausted its search. They do prove
that the offending padded stages contribute nothing to the design's outputs.

## Correction plan

Before splitting each CARRY4, find the highest O or CO bit whose net has a
user. Retain every stage up through that bit, including lower bits needed to
compute it. Split only that prefix. A CO[3] feeding the next CARRY4 counts as
a user and preserves the entire preceding primitive. An intermediate carry
output used by other logic also remains observable. A primitive with no
output users needs no stages. Do not prune a bit merely because its inputs
are constant; observability is the criterion.

Apply this body-only change in an isolated backend snapshot retaining the
verified DSP geometry, pinned LOC handoff and FF edge corrections. Recompile
`pack_carry.cc` only, with all reused source/header/object hashes checked;
leave the donor and earlier artifacts untouched. Record how many unused
stages are omitted.

Validate actual packed and placed carry probes, including padded and full
chains, intermediate carry fanout and observable sum outputs. Check the
retained logic's behavior and the absence of unused tail clusters. Retain
the real DSP/FF routing and strict-frame gate. Only then reuse the unchanged
full mapped checkpoint for another full implementation run.

This is an optimization of unobservable intermediate logic. It changes no
compute dimensions, DDR channels, interfaces, memory capacity or calibration
software. Full fit, routing, timing qualification, bitstream assembly and
physical-board operation still require their own evidence.

## Current build and revalidation

The isolated backend build passed at 15:27 UTC. It rebuilt one translation
unit and retained the verified DSP/LOC/FF changes. The output is
`build/fedora-openxc7/carry-padding-backend-20261007T152543Z`, with binary
SHA256 `e56b743e7946ba795375367548d0d4e2217cdd2871e9cbadcd631149575adfe7`.
Build success alone does not prove correct carry behavior.

The durable controller
`build/fedora-openxc7/ddr800-carry-verified-pipeline-20261007T153650Z` first
routes a real probe with a padded six-bit chain, a complete eight-bit chain,
an observable sum and intermediate carry fanout. It reconstructs the actual
routed LUT/carry connectivity, using the backend's original LUT pin mappings,
and compares four outputs against the installed XC7 simulation models for
all 256 combinations of the eight input bits. It rejects any remaining
unobserved carry cluster. Strict probe frames and the existing real DSP/FF
gate must then pass before the unchanged full mapped checkpoint is routed.
No full synthesis is repeated and no probe bitstream is generated.

Actual probe routing passed, with eight CARRY4s, 47 LUT cells and no unused
carry clusters. All 256 input combinations matched all four XC7-reference
outputs. The successful comparison is in the controller's `carry-probe`.
Strict frame assembly also passed, producing 51,490,824 bytes with SHA256
`caa6e7161de45e24e73e350539b90de3ec71b830ed17e95ccea8945aadb35b9e`.
The DSP/FF regression and its strict frames also passed on the new binary.
Full implementation from the original mapped checkpoint failed at 16:09 UTC
on a different, observable two-CARRY4 cluster, `$6460...muxcy0`.
The actual cluster passes geometry and slice legality in three empty
locations. A confirmed overflow in the full design's placement attempt-limit
calculation is assessed in [openxc7_placer_timeout.md](openxc7_placer_timeout.md).
Full placement/routing, the bitstream, timing qualification and physical-board
operation remain unproven.

The full mapped checkpoint exercised the corrected splitter: it omitted
3,842 unobserved trailing stages and formed 2,827 carry chains. The packer's
reported CARRY4 count fell from 9,836 to 9,127, and its SLICE_LUTX cell count
fell from 308,427 to 300,747. These are packed-cell counts, not physical LUT6
utilization. All 717 DSPs and 179,299 flip-flops remain. Packing success and
these resource savings do not establish full placement or routing success.
Earlier comparison-helper failures are retained: one rejected an unused
outputless LUT, and another used a SystemVerilog keyword as a module name.
Both helper versions and failed manifests are archived. The corrected
comparison adopts the already successful routed probe only after verifying
its backend/database, source/constraints and artifact hashes; it does not
repeat synthesis or routing or turn a failed comparison into a passing one.

Inspect `build/fedora-openxc7/ddr800-pipeline-active.json` and the selected
controller's `pipeline.json` for current state. Revalidation requires new
output directories:

```sh
python3 tools/openxc7_carry_padding.py \
  --previous build/fedora-openxc7/dsp-loc-backend-20261007T140905Z \
  --out build/fedora-openxc7/carry-backend-revalidation
python3 tools/openxc7_carry_padding_check.py \
  --backend-manifest build/fedora-openxc7/carry-backend-revalidation/manifest.json \
  --out build/fedora-openxc7/carry-probe-revalidation
```
