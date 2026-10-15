# Full-design static placer trial and overflow correction

The original heap implementation remains active. An independent full-design
static placement attempt started at 02:15:46 HKT on 2026-10-12 in
`build/fedora-openxc7/litedram-static-vivado-reference-20261011T181500Z`.
It used the same checked backend and independently synthesized complete design.
All five prepared inputs, including the 319 MB constrained netlist and complete
board XDC, were byte-identical to the heap attempt. Only `--placer static`
changed. The normal Vivado reference audit exited 0.

The native process aborted with signal 6 at 02:16:41 HKT on
`std::isfinite(port.max_exp.at(axis))` in `common/place/placer_static.cc:916`.
Its actual native exit is -6; the worker and controller exited 1. This is a
failed implementation attempt, with no routed design or bitstream.

The preserved core confirms finite net bounds: Y=26.5 to Y=383.5. The initial
wirelength coefficient is 0.5, giving an extreme centered exponent of 89.25.
Both Y exponential sums are positive infinity. The source computes exponents
as floats and calls the float overload of `std::exp`, despite storing results
and sums as doubles. An exponent of 89.25 exceeds the finite float range;
its double exponential remains finite. Coordinate corruption was not observed
in these net bounds. Individual optimized local variables were unavailable.
Evidence: the failed attempt's `static-overflow-inspect.log` and
`static-overflow-values.json`.

The proposed correction evaluates both exponentials in double precision in an
isolated copy of the complete checked backend source. The finite-value
assertions, all nets, full accelerator, both memory channels and physical
packing/configuration rules remain required. Existing pinned sources and the
live heap executable are preserved.

Before using the corrected backend for a full retry, record its source delta,
compile/link inputs and binary hash, then rerun the five mandatory carry,
upper-carry, DSP-cascade, FF-edge and MUX qualification gates against that exact
binary. Retry the same complete static design with the existing guarded image
assembly. A successful build or removal of the first assertion alone does not
prove placement, routing, timing, configuration or physical operation.

The correction is now built and qualified for the five required backend
encoding/functional gates. Compile and link both exited 0. The isolated binary
SHA256 is `2bfd62e16b981999c12b0738321456bbaf865be0a0caffcc0f4dfe9265962efe`.
All five checks and their strict frame assemblies ran concurrently and passed
against that exact binary. The qualified selection is
`build/fedora-openxc7/static-precision-qualification-20261011T183800Z/qualified-jtag-backend.json`.
These checks do not qualify numerical timing or a complete board image.

The full corrected retry started at 02:40:10 HKT in
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z`.
Its actual command requests eight threads; main plus eight workers exist.
It reached iteration 120 at 02:43:25 HKT, passing the original overflow point.
A five-second sample observed CPU time on all eight workers but 2.81 equivalent
busy cores across the host. The static algorithm parallelizes wirelength
cell gradients, while other work and strict legalization remain serial.
Both the new full static retry and the original full heap job are preserved.
Placement, routing and accepted bitstream remain unfinished.

At 03:00:08 HKT, the corrected static run remains live in full logic
legalization. It completed RAM/DSP legalization after iteration 473, resumed
logic spreading, and entered logic legalization after iteration 656. The queue
started with 300,727 entries; the latest read-only observation found 127,223
queued entries. Of 350,153 unique concrete representatives in this placer's
vector, 222,955 were bound and 127,198 unbound. The count has zero unexpected
BEL values and includes 168,352 bound FF and 51,462 bound LUT representatives.
These representatives exclude some macro children; this is not a count of the
whole design or an overall completion percentage, and the queue can grow after
rip-ups. GDB exited 0, detached and TracerPid returned to 0; no native calls or
source changes occurred. The detailed snapshot is
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/static-legalizer-20261011T190005Z.json`.
Use the actual snapshot named by that directory's `resume-state.json` if the
receipt timestamp differs. Earlier observer attempts failed to read optimized
locals or an ambiguous anonymous DWARF type; both detached normally, the
process continued and their failure receipts are preserved.

The corrected static netlist, XDC, VREF plan and board constraint audit are
byte-identical to the original full heap run. The hard-cell timing audit differs
only in its `constids` source path: both referenced files have identical bytes
and every other audit field matches. Exact comparisons are in the new run's
`equivalent-route-inputs.json`. The initial comparison used an incorrect audit
filename and was preserved separately; byte equality of all five files is not
claimed. The complete synthesis, accelerator and both DDR channels remain
selected. At 02:53:35, lsusb still detected no Xilinx USB adapter. Neither full
implementation nor the pending physical normal selftest/model run is complete.


At 04:04-04:06 HKT on 2026-10-12, all four exact native processes remain
live, and the new area/delay analytical placers have advanced to iterations
350/330. No native route exit or routed/FASM/image artifact exists yet.
The original heap's bounded read-only snapshot at 04:05:49 finds 149,617 bound
and 150,673 unbound entries in its same 300,290-cell solve vector, versus
133,592/166,698 at 02:41:44. The additional 16,025 bindings are FF entries;
LUT counts remain 44,489 bound/106,790 unbound. Its current search has 3,536,293
aggregate attempts and is still on FF placement. This confirms actual progress
in the original quiet-log job. The new reusable `run-heap-observer.py` checks
its exact PID/start/executable, records actual GDB exit 0 and handles lowercase
'detached'; the existing read-only GDB source remains unchanged.

The original fast-static snapshot at 04:04:33 remains 313,637 bound/36,516
unbound concrete representatives, unchanged since 03:47:17. It is consuming
CPU in a legalizer search, not terminal; this records no new binding progress
for that interval. Both observers exited 0, detached, and left TracerPid=0.
No native functions were called and no placement state was written. The vector
scopes are different and neither is an overall design completion percentage.
The snapshots are respectively
`build/fedora-openxc7/litedram-vivado-reference-20261011T170600Z/placer-counter-20261011T200546Z.json` and
`build/fedora-openxc7/litedram-static-double-vivado-reference-20261011T184000Z/static-legalizer-20261011T200429Z.json`.

Live lsusb and kernel-log refresh still show no Xilinx adapter or subsequent
USB recovery since the 00:20:47 disconnect/00:20:50 enumeration failure.
No hardware client was started. Full native normal selftest/model inference
still requires the adapter. The previous turn made concrete full-mapping and
qualification progress; this continuation is a verified wait on live full jobs.
The goal remains active while meaningful software work continues.


At 04:17 HKT, the full area-mapped implementation completed strict logic
legalization of the 306,321-entry queue and entered simulated annealing
placement refinement. The native log reports post-legalization HPWL 9,526,925
(delta 1,170,542). This is the actual normal full-stage completion, with all
source/dimensions, dual DDR and backend legality assertions retained. It is
not route completion, timing qualification or a ready bitstream. The exact
process is still PID 157975/start ticks 9968368, tool session 23263. Receipt:
`build/fedora-openxc7/area-cut-static-vivado-reference-20261011T195541Z/logic-legalization-pass.json`.
The preceding 04:13:51 read-only snapshot covered all 356,094 unique concrete
representatives in this candidate's vector, with 173,013 bound/183,081 unbound,
all carry/RAM/DSP representatives bound and zero unexpected BEL values; it was
an intermediate snapshot, not the final legalization result. Its observer
exited 0, detached and verified TracerPid=0. The later native log establishes
that this phase completed. No route exit, routed JSON, FASM or accepted image
exists yet. The other complete implementations remain live; JTAG USB is still
absent. This continuation now records concrete full-stage progress rather than
only a wait. Preserve the running full controller and let its normal guarded
routing/assembly/image checks complete.
