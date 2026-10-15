# XC7 carry clusters in both slices

The full DDR800 design is still running in main placement on the corrected
timeout backend. No new failure or full placement result has been reported.
Its synthesis, source snapshots and earlier passing gates remain preserved.

## Evidence and assessment

The actual chipdb contains 74,650 CARRY4 sites: 37,325 at z=15 in the first
slice and 37,325 at z=79 in the second. Both occur in the same logic tiles.
`carry-site-audit.json` records counts, coordinates and the database hash.

`pack_carry.cc` assigns the root and child carries absolute z=15 and its
LUT children absolute positions in 0..63. The upstream generic
`BaseArch::getClusterPlacement` coerces the proposed root location to the
root's absolute z before placing the children. The current XC7 override
specializes DSPs and delegates all carry clusters to that generic method.
Thus a proposed second-slice root is relocated to the first slice rather
than exercising the second carry column.

This is a confirmed restriction on candidate sites. It is not yet proof
of the particular full placement failure or the cause of the current long
search. The earlier full failing cluster passed empty first-slice checks;
second-slice legality and actual dedicated carry routing need verification.

The small GDB diagnostic failed before startup: this session's sandbox
denied ptrace. Its exact command, source and error remain in
`carry-second-site-diagnostic`. No placement ran in that diagnostic.

## Plan before code

Extend only the existing XC7 cluster-placement override for CARRY4 roots.
Use upstream generic placement to obtain the unchanged x/y geometry, then
translate every target's z by the selected slice offset, 0 or 64. Require
each translated BEL to exist and support its cell type, and require the
returned root to equal the proposed root. Preserve the DSP specialization,
carry observability correction, FF edges and finite timeout arithmetic.
Do not replace upstream placement, routing or legality algorithms.

Build an isolated snapshot, changing only `xilinx.cc` and its porting docs.
Reuse hash-verified headers, sources and objects and recompile one translation
unit. Keep the currently running full design and all original inputs intact.

Add an optional in-process probe for small test netlists only. For each packed
carry root, record the generic method's first-slice coercion, test the new
second-slice placement by binding and validating every member in an empty
location, then unbind it and pin that root to the verified upper-slice BEL.
Normal placement and routing must subsequently exercise these pinned roots.
The option is absent in normal full builds and rejects large netlists.

Require actual second-slice carry routing, the existing 256-pattern/four-output
equivalence check, decoded placements in the second slice and strict frames.
Also require the normal carry and DSP/FF routed gates on the new binary.
Only then consider a full run with this correction from the unchanged full
mapped checkpoint. Do not claim physical fit, timing or board execution from
the probe. No synthesis of the full design or programming is required.

## Probe option registration correction

The first forced-upper probe stopped before placement because the XC7 command
parser rejected the unregistered `carry-upper-probe=on` option. Preserve that
failed run. Register the existing verification option in XC7 getUArchOptions,
then build a new immutable backend snapshot and rerun actual routed gates.
Normal full builds omit the option; no placement algorithm changes are needed.

## Full-run promotion after completed gates

The registered second-slice probe routed successfully. Its corrected checker
accepts actual physical BEL names (`SLICE_X1Ynnn/CARRY4`); the completed route
is reused only after binary, database and input hashes and route exit checks.
All 256 input patterns/four outputs pass, eight carries occupy the second
slice, and four CO3-to-CIN links use dedicated COUT_N routing. Upper-probe
strict frames pass. Normal carry and 64-DSP/2,880-bit cascade/FF-edge routed
gates pass on the same binary; their strict frames are finishing.

After all three strict frame gates pass, retire only the owned older backend
process by confirmed PID and command identity, preserving its logs and
checkpoint. This promotion is justified by the verified carry geometry
correction, rather than quiet output or an observation timeout. A live
backtrace confirms the old run is in strict legalisation and has advanced to
a LUT cluster; the geometry restriction is not proven to be its sole cause.

Create a new controller manifest with the unchanged full DDR800 configuration,
full mapped checkpoint and LiteDRAM firmware. Reuse the just-completed routed
gates after verifying their binary/database/input/artifact hashes, exits,
actual upper-slice placements, dedicated routing and frame files. Do not
repeat these gates or full synthesis. Run the existing full route, strict
frame assembly, frames2bit and independent bitstream checker in sequence.
Record RUNNING/FAIL/assembled states, input hashes and command/exit logs; keep
numerical timing and physical execution explicitly unqualified.

## Source helpers and current result

`tools/openxc7_carry_sites.py` preserves the validated builder; its C++ bodies
match the tested backend. `tools/openxc7_carry_sites_check.py` forces the small
probe into the second slice, checks all four dedicated carry links and runs
the 256-pattern/four-output comparison. The source checker was revalidated
against the actual matching completed route, without repeating placement.

The selected backend passed upper and normal carry routing/equivalence,
64-DSP/2,880-bit cascade routing, both FF edge events and all three strict
frame assemblies. Current backend/pipeline paths are recorded in
`build/fedora-openxc7/implementation-active.json`. The promoted full run
reuses the unchanged mapped synthesis and hash-checked completed gates.

To rebuild the correction, use the completed **timeout-corrected predecessor**
directory as `--previous`, and new output directories for each command:

```sh
python3 tools/openxc7_carry_sites.py --previous /path/to/timeout-backend --out /path/to/new-backend
python3 tools/openxc7_carry_sites_check.py --backend-manifest /path/to/new-backend/manifest.json --out /path/to/new-probe
```

The probe does not assemble frames or program hardware. Its dedicated pinout
is a routing test fixture. Full reroutes must set `OTPU_NEXTPNR` and
`OTPU_NEXTPNR_SOURCE` from the selected backend manifest and retain the same
full mapped checkpoint and DDR800 LiteDRAM core. The current controller
records those exact commands and all planned input hashes in its pipeline
directory; it performs strict frame assembly and independent image checks
only after the full route succeeds. Full fit, timing and physical operation
remain unproven.
