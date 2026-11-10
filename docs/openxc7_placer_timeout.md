# XC7 full-design placement timeout overflow

The unchanged full DDR800 design failed placement at 16:09 UTC on
`$6460.genblk1.slice[0].genblk1.carry4$split$muxcy0$PACKED_CARRY4$`.
The carry-padding, DSP-cascade and FF-edge routed probes and their strict
frames passed. No full image was produced.

## Evidence and assessment

The actual packed failing cluster was captured after `prePlace` under GDB
in `build/fedora-openxc7/carry-observable-cluster-20261007T161409Z`.
It has two CARRY4s and thirteen LUT children with distinct locations.
Binding all fifteen members at each of three empty locations passes both
cluster geometry and every member's slice legality. `empty-slice.json`
records the results. This rules out an inherently impossible cluster at
those locations; it does not prove fit in the populated full placement.

The live configuration has 531,351 cells, timeout divisor 8 and a per-cell
limit of 10,000. The upstream constructor squares the cell count using
32-bit signed `int` arithmetic. The mathematical square is 282,333,885,201;
its observed 32-bit wrap is -1,133,956,335. The subsequent division and
`max(10000, ...)` therefore select 10,000 rather than the intended large
conservative limit. Signed overflow is undefined behavior; the wrap
calculation describes this binary's observed result, not a portable contract.
The intended square divided by eight is 35,291,735,650, exceeding the current
configuration field's `int` range.

## Correction plan

In the XC7 `configurePlacerHeap` body, recompute this limit in 64-bit
arithmetic, retain the 10,000 minimum, and saturate one below the `int` maximum. The upstream attempt counter
is also an `int`, and its stopping comparison uses `>`; reserving one step
lets that counter exceed the limit without overflowing.
Honor the existing divisor and its nonpositive setting for disabling this
limit. Log the actual cell count, divisor and selected limit. Preserve all
upstream placement algorithms, priorities and other architecture behavior.
This addresses the confirmed arithmetic bug; it does not establish that
this was the only cause of the failed full placement.

Build an isolated snapshot from the verified carry/DSP/LOC/FF backend,
recompiling only `xilinx.cc` and checking every reused source/header/object.
Check boundary arithmetic and settings behavior using the actual new
configuration body. Require the real carry equivalence/routing/strict-frame
and DSP/FF routing/strict-frame gates on the new binary before starting one
full placement run from the existing mapped checkpoint. Keep all failed
artifacts, compute dimensions, DDR channels and original test assertions.
No synthesis or hardware programming is required for this correction.

Full placement, routing, hard-cell timing qualification, full strict frame
assembly and physical JTAG/DDR/compute acceptance remain incomplete.

## 2026-10-10 isolated correction and probe results

`tools/openxc7_placer_timeout.py` built a fresh isolated backend from the
verified carry-padding/DSP/FF backend. It changed only the XC7
`configurePlacerHeap` implementation and retained the prior carry, DSP, LOC,
and FF-edge corrections. The nine-case arithmetic contract passed with UBSan,
including the full 531,351-cell case, which selects 2,147,483,646 attempts.
The backend is
`build/fedora-openxc7/placer-timeout-backend-20261010T1831HKT/nextpnr-himbaechel`
(SHA256 `b7c15652ebea939e346fb580985240a54762f3feb0948eb285e6c2061b8de759`).
An earlier build attempt remains preserved at
`build/fedora-openxc7/placer-timeout-backend-20261007T164345Z/`; it stopped
before the backend compile because the system GCC UBSan runtime was missing.
The successful run used the installed Clang UBSan runtime and did not change
system packages.

The new binary passed the real carry route plus exhaustive 256-pattern
equivalence check, the four 16-DSP cascade route check, and the FF-edge probe
that reports posedge-to-negedge and negedge-to-posedge timing semantics. The
corrected carry, DSP, and FF FASM each also passed strict Project X-Ray frame
assembly. Receipts are under
`build/fedora-openxc7/placer-timeout-carry-check-20261010T1835HKT/`,
`build/fedora-openxc7/placer-timeout-dsp-check-20261010T1835HKT/`,
`build/fedora-openxc7/placer-timeout-ff-edge-check-20261010T1838HKT/`, and
`build/fedora-openxc7/placer-timeout-strict-frames-20261010T1835HKT.json`.
These results validate the correction on small real XC7 probes; they do not
prove that the full design will place or route. The selected native Vivado
reference remains stopped before constrained routing, and the full OpenXC7
placement has not been rerun with the corrected timeout backend.
