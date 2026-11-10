# The ladder mini-core (step 4): an openTPU-ISA machine

This document describes `rtl/ladder/mini_*.sv` — the first real openTPU-ISA machine written for
the ladder, and the base the next rungs (reductions) extend.  Step 4 built the sequencer,
TMEM, DRAM and LD/ST; step 5 adds the VPU (section [The VPU](#the-vpu-step-5)), step 6 the
quantizer + ACT RAM and step 7 the MXU (section [The MXU](#the-mxu-step-7)).  Its job is
narrow and strict: run the step-4 instruction subset one instruction at a time and leave exactly
the state the openTPU ISA simulator leaves (`opentpu/isasim.py`, the golden model imported in
step 3), so that every later unit can be trusted bit for bit before the production RTL replaces
this core in step 9.

The machine model is the openTPU one from `docs/isa.md`, with the production concurrency
removed on purpose:

* one slice (`S=1`), one instruction at a time, no scoreboard, no overlap;
* one TMEM read port and one TMEM write port (a legal schedule of the production banked TMEM);
* a behavioural, byte-addressed DRAM (no AXI; a synchronisation-free stand-in for the DDR
  controller);
* `BAR` is a no-op (with one slice the collective is already complete);
* `HALT CHAIN` is rejected (the board's program chaining is not part of this rung);
* everything outside the subset is an illegal-opcode error (later rungs add it).

What is *not* simplified is state: registers, PC, TMEM, DRAM and the retired-instruction count
after a run are bit-identical to `isasim` — that is what `ladder/tests/test_step04_core.py`
asserts, on fixed programs and on 24 random ones.

## Block diagram

```
                      +-------------------------------------------------------+
                      |                       mini_top                        |
  IMEM image          |  +---------+   +-----------+   +--------------------+  |
  (prog.hex) -------->|  |  imem   |-->|  fetch    |-->|  instruction       |  |
  $readmemh           |  | 8 words |   | 8 words   |   |  register w0..w7   |  |
                      |  | /instr  |   | per cycle |   +---------+----------+  |
                      |  +---------+   +-----------+             |             |
                      |                                          v             |
                      |  +---------+   +-----------+   +--------------------+  |
                      |  | loop    |<->| sequencer |<->|  decode / execute  |  |
                      |  | stack   |   | FSM       |   |  (LI/ADDI/LOOP/    |  |
                      |  | depth 4 |   |           |   |   BAR/RLD/HALT)    |  |
                      |  +---------+   +-----+-----+   +---------+----------+  |
                      |                      |                   |             |
                      |        +-------------+------+    +-------+--------+    |
                      |        | R0..R15 (R0 == 0)  |    | LD/ST engine   |    |
                      |        | R8..R15 = rinit    |    | 1 word / cycle |    |
                      |        +-------------+------+    +-------+--------+    |
                      |                      |                   |             |
                      |            +---------v-------+   +-------v---------+   |
                      |            |  mini_tmem      |   |  mini_dram      |   |
                      |            |  [32b] words    |   |  byte array,    |   |
                      |            |  1R + 1W        |   |  LE, 1R + 1W    |   |
                      |            +-----------------+   +-----------------+   |
                      +-------------------------------------------------------+
                              ^ rinit[8]      all_halted / any_error / error_code / icount
                              |
                         tb_mini (sim/ladder/tb_mini.sv)
                 +prog +dram +outdir +max_cycles +arg0..+arg7
                 -> tmem.hex, dram_out.hex, one RESULT line
                              |
                       ladder/harness/mini.py  <->  opentpu.isasim (oracle)
```

`mini_pkg.sv` holds the shared tables: the openTPU opcodes and flags used by this rung, the
error codes, the loop depth and `f2i()`, RLD's fp32-to-int conversion, in SystemVerilog.

## The sequencer

The FSM is deliberately boring; the state semantics are the point.

| state     | cycles | what happens |
|-----------|--------|--------------|
| `ST_FETCH`  | 8      | word *i* of the instruction at `pc` (`imem[8*pc+i]`) is latched, `i = 0..7`.  `pc >= IMEM_WORDS/8` means the program image is over: error 1. |
| `ST_EXEC`   | 1      | decode `w0` (op/ra/rb/rc/rd/flags) and execute: register writes, PC change for `LOOP`, error detection, or start the LD/ST engine / halt.  `icount++` happens here, so an instruction that errors is counted once, exactly like `isasim`. |
| `ST_LDST`   | n      | one 32-bit word per cycle (`n` = LD/ST's word count) through the TMEM and DRAM ports. |
| `ST_ADV`    | 1      | the ISA's `advance()`: `pc+1`, or the innermost loop's back edge / loop exit. |
| `ST_HALTED` | —      | latched after `HALT`; `all_halted` stays 1. |
| `ST_ERROR`  | —      | latched after an error; `error_code` holds one of the codes below. |

So an ordinary instruction costs 11 cycles; an `n`-word LD/ST costs 11 + n.  That is much slower
than production (which overlaps fetch/execute and streams LD/ST through a DMA), and irrelevant:
no test looks at cycles, only at the final state.

Loop stack entries are `(start pc, body-end pc, remaining count)`; the count is latched at `LOOP`
(`R[ra] + w2 mod 2^32`) so a body that modifies the count register still terminates.  The
advance rule is `isasim`'s: if the current `pc` is the innermost body's end, either go back to the
body start with `count-1`, or pop and continue after the body.  `LOOP` checks are performed in
the oracle's order: empty body (w1 = 0), an inner body ending on the same instruction as an
enclosing one, count 0 (skip before the depth check), stack overflow (depth 4).

## Instruction subset

Encodings are the production ones: `w0 = op | ra<<8 | rb<<12 | rc<<16 | rd<<20 | flags<<24`,
then `w1..w7` (`opentpu/isa.py`, `docs/isa.md`).  Addresses and counts are `R[x] + word`.

| op    | name | step-4 semantics |
|-------|------|------------------|
| 0x00 | NOP  | — |
| 0x01 | HALT | stop the slice; `icount` includes it.  Flag bit 0 (`CHAIN`) is rejected with error 1. |
| 0x02 | LI   | `R[rd] = w1` (rd = 0 drops the write) |
| 0x03 | ADDI | `R[rd] = R[ra] + w1` mod 2^32 |
| 0x04 | LOOP | body = next `w1` instructions, run `R[ra] + w2` times (0 skips the body); depth 4; nesting rules as `isasim` |
| 0x05 | BAR  | no-op with one slice (the collective is already complete, then advance) |
| 0x06 | RLD  | `R[rd] = f2i(T[R[ra] + w1])`; flag 0 `RAW`: the word's bits; flag 1 `MUL`: times `R[rb] + w2` mod 2^32; flag 2 `BOUND` is ignored by the hardware (the simulator checks `w3 <= v <= w4`; the waits pass uses it) |
| 0x10 | LD   | `T[R[rb] + w2 + i] = M32[R[ra] + w1 + 4i]`, `i < w3` |
| 0x11 | ST   | `M32[R[ra] + w1 + 4i] = T[R[rb] + w2 + i]`, `i < w3` |
| 0x30 | VOP  | step 5: the 14 elementwise functions in the 4 B modes (the VPU section); the reductions / ARGMAX / OUTER are step 8 and error 1 here |
| 0x21 | QACT | step 6: quantize TMEM rows into ACT RAM (the quantizer section) |
| 0x22 | QST  | step 6: quantize TMEM rows into DRAM int8 bytes + scale records |
| 0x20 | MM   | step 7: int8 (WF 0) matmul with MX scales and the fp32 epilogue; UNIT/ACC/RMAX (the MXU section); other formats/flags are error 8 |
| other |      | error 1 (WAITW/DSTEP/STREAM/GATHER arrive in step 8+) |

`R0` reads as 0 and writes to it are dropped.  `R8..R15` start with the run's arguments
(`+arg0..+arg7`, the `rinit[8]` port); `R1..R7` start at 0.  `LD`/`ST` with `w3 = 0` are no-ops
(isasim's range checks are vacuous).  The `n` word addresses are checked as a block before the
transfer starts, in `isasim`'s order: DRAM first (error 2), then TMEM (error 4).

## Error model

| code | meaning |
|------|---------|
| 0 | no error |
| 1 | illegal/unimplemented opcode, `HALT CHAIN`, program image over, fetch past the loaded program |
| 2 | bad DRAM word address: unaligned (not a multiple of 4) or the transfer runs past `DRAM_BYTES` |
| 3 | `LOOP` error: empty body, nested bodies ending on the same instruction, stack depth exceeded |
| 4 | TMEM index out of range (`R[ra] + w`, an LD/ST range, or a VOP operand/destination outside `TMEM_WORDS`) |
| 5 | VOP read-after-write hazard: a later element reads a TMEM word an earlier element of the same VOP wrote (the ISA simulator rejects this; a one-write-port machine would compute different bits) |
| 6 | QACT/QST TMEM range, or QACT ACT RAM bounds (step 6) |
| 7 | QST data/scale range or overlap, bad scale address (step 6) |
| 8 | MM flag/format the mini-core does not implement: PAIR, RSC, ASCALE, the 4-bit / NVFP4 weight formats (step 9) |
| 9 | MM bounds/alignment/scale-row checks, or an ACT row whose K-blocks hold different Sa (two QACTs) |

The codes are the ladder's own; the ISA's error *condition* is the oracle's (`isasim` raises
`SimError` for all of them, except that the hardware-ignored `RLD BOUND` field is only checked by
isasim).  Once an error latches, `any_error` stays 1 and the machine does not run further.

Two cases are deliberately the mini-core's own reading of the ISA:

* **HALT CHAIN** — the production board loads the next program from DRAM; step 4 has no
  program loader, so a `HALT` with the CHAIN flag errors with code 1 instead of chaining.
* **Fetching past the program image** — the board's loader can only place a program inside IMEM.
  `tb_mini` pads the IMEM image with `0xFFFFFFFF`, so falling off the end is an illegal opcode
  (error 1); `isasim` raises "pc past end of program".  Both stop the machine; the tests only
  require the mini-core to error.

## The VPU (step 5)

`rtl/ladder/mini_vpu.sv` executes the elementwise VOPs: **ADD, SUB, RSUB, MUL, MAX, MIN, COPY,
EXP2, RECIP, RSQRT, ABS, FILL, EXP2SUB, LOG2**.  The arithmetic is the product tree's `otpu_fp`
package, copied verbatim from `ca05e24f` (`rtl/ladder/otpu_fp.sv`, Apache-2.0, unmodified); it is
the same combinational set the production VPU and `opentpu/fp32.py` define — `fp_add`, `fp_sub`,
`fp_mul`, `fp_max`, `fp_min`, `ftz`, `fabs`, `fp_exp2`, `fp_recip`, `fp_rsqrt`, `fp_log2` — so
the hardware and the golden model cannot drift.  The reductions, ARGMAX and OUTER are step 8;
a function outside this set is an illegal instruction (error 1).

The unit has a `start / busy / done / err` interface and owns both TMEM read ports and the write
port while it runs (`mini_tmem` is 2R+1W from step 5 on).  Elements are processed row-major,
`(r, c) = (0,0), (0,1), ..., (rows-1, cols-1)`, one per clock; latency is not part of the
contract, state is.  For element `i`:

* **A** = `a + r*ars + c` (read through TMEM port 0; `FILL` reads no A);
* **B** by `bmode`: `FULL` `b + r*brs + c`, `ROW` `b + r*brs` (one word per row, broadcast over
  the columns), `COL` `b + c` (one word per column, broadcast over the rows), `SCALAR` the
  immediate word `w7 = R[rd] + w6` (no TMEM read; `COPY`, `EXP2`, `RECIP`, `RSQRT`, `ABS`,
  `LOG2` read no B at all, whatever the mode);
* the result is written to `dst + r*drs + c`.

The register-relative fields are resolved exactly as `isa.vop()` encodes and `isasim._vop`
decodes them: `dst/a/b = R[ra/rb/rc] + w1..w3`, the shape and strides are immediates
(`rows|cols<<16`, `drs|ars<<16`, `brs|func<<16|bmode<<24`), and the immediate word is
register-relative (`R[rd] + w7`, 32-bit wrap).

**Hazard rule.**  The ISA lets no element read an address an earlier element of the same VOP
wrote: `isasim._check_hazard` raises `SimError("VOP read-after-write hazard")` before it
applies any write.  The VPU marks every destination address it writes in a one-bit-per-TMEM-word
bitmap and, for each element, checks the A and B addresses it actually reads against the marks
from earlier elements.  A hit latches **error code 5** and stops the unit; a read or write
outside `TMEM_WORDS` is **error code 4** (checked per element, in `isasim`'s order: A, B,
hazard, destination).  Both cases leave the machine in `ST_ERROR`, exactly what a test needs to
prove the core rejects the program instead of silently computing different bits.

The step-5 tests (`ladder/tests/test_step05_vpu.py`) compare the whole TMEM and the whole DRAM
bit for bit against `isasim` for all 14 functions x 4 modes x four shapes on random words, for
the documented fp32 corner cases, with fixed golden values per function (so the suite is
meaningful without the oracle), with explicit expectations for each B mode and for unusual
strides, and with the hazard and range negatives (codes 5 and 4).  The package itself was
checked against `opentpu/fp32.py` on 84 322 random/corner vectors, all 14 operations, before the
unit was wired in (0 mismatches; this check is not part of the committed suite because the
mini-core tests already exercise it through VOP).

## The MXU (step 7)

`rtl/ladder/mini_mxu.sv` implements MM for the **int8 weight format (WF 0)** with the flags
**UNIT / ACC / RMAX**: exact integer accumulation over D-byte K-blocks, the MX scales, and the
fp32 epilogue.  PAIR, RSC, ASCALE and the 4-bit / NVFP4 formats are rejected with error 8, so a
program that relies on them fails instead of computing wrong bits.  The arithmetic is
`docs/isa.md` "MM" / "Weight formats", i.e. `opentpu/isasim.py::_mm` / `_mx_scales`, the golden
model imported in step 3 (`opentpu/fp32.py` for the epilogue, `rtl/ladder/otpu_fp.sv` for the
hardware, both bit-exact).

For every output `y[j][n]` (stationary ACT row `j`, streamed weight row `n`):

```
acc = 0                                                    exact signed 48-bit (< 2^47)
for k in 0..KB-1:                                          ACT block ab+k, weight block k
  for g in 0..3:                                           the D/4 = 8-element sub-blocks
    c  = sum_i ACT[j][(ab+k)*D + g*8+i] * w[n][k*D + g*8+i]   exact, |c| < 2^17
    sh = 16 - dw[n][k0+k] - da[j][ab+k][g]                 unsigned bytes: sh is signed
    acc = acc + (sh >= 0 ? c << sh : 0)                    sh < 0: the group drops
y = fp_mul(fp_mul(i2f48(acc), Sw[n]), fp_mul(Sa[j][ab], 2^-16))
if ACC: y = fp_add(T[out + j*ors + n], y)
T[out + j*ors + n] = y
if RMAX: the row maximum of the written y (total order of flushed values, `otpu_fp::fp_gt`);
         after all M*N outputs, T[out + M*ors + j] = rmax[j]
```

The epilogue's association is load-bearing: `Sa * 2^-16` is its own rounded multiply
(`0x37800000`), not a folded exponent, so a denormal `Sa` or a NaN result rounds exactly as
`opentpu/fp32.py` does.  `i2f48` is the production MXU's accumulator converter
(`rtl/mxu/otpu_mxu.sv`'s `otpu_mx_lane`): 48-bit signed, round to nearest even with guard and
sticky, exponent carry; `otpu_fp::i2f` is 32-bit and would truncate the accumulator, so the
mini-core carries its own copy of the converter.

Scale sources (WF 0): `Sw[n]` is the fp32 word at `ssa + n*srs`; `dw[n][k]` is the byte at
`ssa + n*srs + 4 + k0 + k` (the `k0` offset applies to the `dw` byte and never to the weights);
`Sa[j][ab+k]` and its four `da[j][ab+k][g]` bytes come from step 6's ACT RAM.  The MXU reads
the ACT through mini_actram's MXU ports: a 32-bit word of four int8 bytes per cycle
(`act[row][block*D/4 + word]`) and the (row, block) scale record `{da3, da2, da1, da0, Sa}`;
the streamed weights and scale rows come from the DRAM read port one 32-bit word (four int8
bytes) or one byte at a time.  `UNIT` reads no scale row at all (no alignment or range checks
on `ssa`/`srs`, `Sw = 1.0`, `dw = 0`) but still uses the ACT `Sa`/`da`.

**Checks, in isasim's order.**  The unit validates before any TMEM write (the `M_CHK` /
`M_CHK_SA` / `M_CHK_TMEM` states), mirroring `_mm`/`_mx_scales`:

| # | check | code |
|---|-------|------|
| 0 | unsupported flag/format (PAIR, RSC, ASCALE, WF != 0) | 8 |
| 1 | `N == 0` or `KB == 0` | 9 |
| 2 | `not (0 < M <= ACT_ROWS)` or `ab + KB > ACT_BLOCKS` | 9 |
| 3 | `M > MCOLS` with RMAX (ASCALE is code 8) | 9 |
| 4 | `sa % D`, `rs % D`, or `sa + (N-1)*rs + KB*D > DRAM_BYTES` (all 64-bit) | 9 |
| 5 | non-UNIT only: `ssa % 4`, `srs % 4`, `ssa + (N-1)*srs + 4 > DRAM_BYTES`, or a `dw` byte past DRAM | 9 |
| 6 | an ACT row's K-blocks hold different `Sa` bits (two QACTs on one row) | 9 |
| 7 | an output word (`out + (M-1)*ors + N-1`) or an RMAX word outside TMEM | 4 |

All address math after the 32-bit `R[x]+w` wrap is 64-bit, like isasim's Python integers, so a
huge `sa`/`srs` is rejected instead of wrapping into range.

**Documented serialized limitation.**  isasim reads every old ACC value before writing any
output, while the serialized unit reads `T[addr]` just before writing `addr`.  The state is
bit-identical while the `M*N` output addresses are distinct, i.e. `ors >= N` (the production
convention; every step-7 vector and fuzz case satisfies it).  A program with aliasing output
rows would need an `M*N` pre-read buffer.

The step-7 tests (`ladder/tests/test_step07_mm.py`, 31 tests, Icarus only) run the 10 positive
golden vectors from `/tmp/ladder-plan/step07_vectors.json` through the mini-core and assert the
recorded TMEM/ACT/ascale/adoff state, plus whole-state equality with isasim; 16 negative vectors
(13 isasim-rejected cases with codes 9/4 and 3 mini-only unsupported cases with code 8); 16+
random LD->QACT->MM programs fuzzed against isasim; a numpy int64 cross-check of the integer
accumulation; the UNIT-skips-scale-checks case; and the `ors == N` ACC boundary.

## Testbench protocol (`sim/ladder/tb_mini.sv`)

`tb_mini` is the reusable board stand-in; every later rung drives the core through the same
protocol (and `ladder/harness/mini.py` is the same Python side):

| plusarg | meaning |
|---------|---------|
| `+prog=<file>` | IMEM image: 8 hex words per instruction, one 32-bit word per line (the harness pads it to `IMEM_WORDS` with `0xffffffff`) |
| `+dram=<file>` | DRAM image: 2 hex digits per byte, one byte per line (the harness always writes a full-size image, zero-padded) |
| `+outdir=<dir>` | where the dumps go |
| `+max_cycles=<n>` | cycle budget; if it expires the TB prints `halted=0 error=0` (default 200000) |
| `+arg0..+arg7=<hex>` | the run's arguments, latched into `R8..R15` at reset |

The TB resets for 3 cycles, then samples on the negedge while `!all_halted && !any_error` and
`cycles < max_cycles` (negedge sampling keeps it off the DUT's posedge and race-free), then
writes:

* `tmem.hex` — `TMEM_WORDS` lines, 8 hex digits per word;
* `dram_out.hex` — `DRAM_BYTES` lines, 2 hex digits per byte;
* `RESULT cycles=<n> halted=<0|1> error=<0|1> code=<n> icount=<n>`.

Sizes are module parameters (`D`, `MCOLS`, `ACT_BLOCKS`, `ACT_ROWS`, `TMEM_WORDS`, `IMEM_WORDS`,
`DRAM_BYTES`, defaults D=32, MCOLS=4, ACT_BLOCKS=16, ACT_ROWS=4, TMEM_WORDS=4096, IMEM_WORDS=4096,
DRAM_BYTES=262144) and are passed with `iverilog -P`; the same values go into `isasim.Config`.

Two Icarus notes that shaped the RTL/TB and are worth keeping:

* TMEM/DRAM read ports are **continuous assigns**, not `always @*` processes.  An `always @*`
  process is rescheduled by every byte the image loader writes through the hierarchical array,
  which made a 16 KiB image take longer to load than the whole simulation (0.9 s vs 10 ms).
* The TB does **no** hierarchical fill loops: the harness writes full-size images and one
  `$readmemh` per memory.  Per-element hierarchical writes are roughly 40 us each in Icarus.

## Python harness (`ladder/harness/mini.py`)

* `build(params_=..., force=False)` — `iverilog -g2012 -s tb_mini` over `rtl/ladder/*.sv` +
  `sim/ladder/tb_mini.sv`, cached under `ladder/artifacts/iverilog/<sha1 of sources+flags>/`.
* `run(prog, dram=None, args=None, max_cycles=200000, params_=...)` — assembles `prog` with
  `opentpu.isa.assemble` (or takes raw instruction words), writes the full-size `prog.hex` and
  `dram.hex`, runs `vvp`, parses the `RESULT` line and the dumps, and returns
  `{"tmem", "dram", "cycles", "halted", "error", "code", "icount"}`.  Scratch files live under
  `ladder/artifacts/mini-runs/` and are removed afterwards.
* `run_isasim(prog, dram=None, args=None, params_=...)` — the oracle: a one-slice
  `opentpu.isasim.Machine` with the matching `Config`, returning the final state or
  `{"error": True, "message": ...}` when it raises `SimError`.
* `assert_matches_isasim(...)` — runs both and asserts bit-identical TMEM and whole DRAM (and
  equal `icount`); on a mismatch it raises an `AssertionError` listing the first differing
  addresses with the RTL and isasim values.  `assert_errors(...)` asserts the mini-core errors
  with a given code, and by default that isasim raises `SimError` for the same program.

Typical use:

```python
from ladder.harness import mini
from opentpu import isa as I

out = mini.assert_matches_isasim([I.li(1, 5), I.halt()])
```

## What is exact, what is not

| aspect | production | mini-core (step 4) |
|--------|-----------|--------------------|
| architectural state (R, PC, TMEM, DRAM) | `docs/isa.md` | **exact**, bit-for-bit vs `isasim` |
| instruction encodings / semantics of the subset | `opentpu/isa.py` | **exact** |
| retired-instruction count (`icount`) | counts issued instructions | **exact** for the subset (errors counted like `isasim`) |
| error conditions | as `docs/isa.md` | **exact conditions**, ladder-local codes (1-4) |
| latency / cycles | overlapped fetch, DMA, banks, scoreboard | serial: 11 cycles per instruction + 1/word for LD/ST |
| concurrency | slices, BAR/GATHER, wait counts, chaining | single slice, BAR no-op, no chain |
| DRAM interface | AXI / DDR controller | behavioural byte array, 1R+1W |
| TMEM banking / ports | LANES banks, 3R+1W per bank | flat 2R+1W |
| VPU arithmetic | `otpu_fp` / `opentpu/fp32.py` | **exact**, the same `otpu_fp` package (step 5) |
| quantizer | `opentpu/fp32.py::quantize_mx` | **exact** bytes/scales vs isasim's `_quant_rows` (step 6) |
| MXU | `opentpu/fp32.py` + `_mm` / `_mx_scales` | **exact** for WF 0 with UNIT/ACC/RMAX (step 7); other formats are step 9 |

Later rungs keep the machine and the harness, add the missing units (step 5 VPU, 6 quantizer +
ACT RAM, 7 MXU, 8 reductions/ARGMAX), and step 9 swaps the whole mini-core for the production
RTL, comparing through the same `+prog`/`+dram`/dumps protocol.

## Files

| file | role |
|------|------|
| `rtl/ladder/mini_pkg.sv` | opcodes, flags, error codes, `f2i()` |
| `rtl/ladder/mini_dram.sv` | behavioural byte-addressed DRAM, 1 read + 1 write port, visible `mem` |
| `rtl/ladder/mini_tmem.sv` | TMEM word array, 1R+1W, visible `mem` |
| `rtl/ladder/mini_top.sv` | IMEM, registers, PC, loop stack, FSM, LD/ST engine, VOP decode, status |
| `rtl/ladder/mini_vpu.sv` | the elementwise VPU: 14 functions, 4 B modes, hazard bitmap, TMEM 2R1W master |
| `rtl/ladder/mini_quant.sv` | the quantizer: QACT/QST, MX row quantization (step 6) |
| `rtl/ladder/mini_actram.sv` | ACT RAM: int8 bytes + Sa/da scale records, quantizer write/MXU read ports (step 6) |
| `rtl/ladder/mini_mxu.sv` | the int8 MXU: exact block accumulation, MX scale rows, fp32 epilogue, RMAX (step 7) |
| `rtl/ladder/otpu_fp.sv` | the product tree's fp32 package, copied verbatim (`ca05e24f`, Apache-2.0) |
| `sim/ladder/tb_mini.sv` | testbench / board protocol |
| `ladder/harness/mini.py` | build, run, oracle comparison |
| `ladder/tests/test_step04_core.py` | the step-4 acceptance suite |

## Running the step

```
python3 ladder/run.py step 4            # pytest via the ladder runner, writes the receipt
python3 -m pytest -v ladder/tests/test_step04_core.py   # directly
python3 ladder/run.py step 5            # the VPU suite (22 tests, ~14 s, Icarus only)
python3 ladder/run.py step 6            # the quantizer suite (Icarus only)
python3 ladder/run.py step 7            # the MXU suite (31 tests, ~33 s, Icarus only)
python3 -m pytest -v ladder/tests/test_step05_vpu.py    # directly
python3 -m pytest -v ladder/tests/test_step07_mm.py     # directly
```

The suite is light (7 tests, ~4 s): instruction semantics with concrete expected bytes, an 8/16/8-
word LD/ST copy compared on the full 256 KiB spec DRAM, single/nested/three-deep loops with
carried pointers and zero-count skips, argument registers and `ADDI` address arithmetic, the error
model, `HALT` placement, and 24 random programs fuzzed against `isasim`.

## Step 6 — quantizer and ACT RAM (QACT, QST)

Step 6 adds the production quantizer and the ACT RAM it writes (`rtl/ladder/mini_quant.sv`,
`rtl/ladder/mini_actram.sv`).  The arithmetic is `opentpu/fp32.py::quantize_mx` +
`mx_offset` + `q8` exactly (the tails of `fixedpoint`-free fp32 from step 5's `otpu_fp`
package: `ftz`, `fp_mul`, `fp_recip`, `q8`, `F_INV127`), and the ISA semantics are
`opentpu/isasim.py::_quant_rows/_qact/_qst`; the oracle is still the same ISA simulator.

**QACT (0x21)** quantizes `rows x KB*D` TMEM words starting at `R[ra]+w1` into the ACT RAM:
`x = ftz(T[src + r*srs + c])`, optionally `* T[cscale + c]` (CSCALE) and `* T[rscale + r]`
(RSCALE) in isasim's order, `amax` = unsigned max of the sign-cleared fp32 bits, row scale
`Sa = amax * inv127`, inverse `inv = 127 * recip(amax)` (both 0 for an all-zero row), a
power-of-two offset per group (`D/NSUB` elements: `d = exp(amax)-exp(a) - (mant(a) >
mant(amax))`, 0 in ROW mode, clipped to [0,31]), and `q = q8(x * inv * 2^d)` written as the
ACT int8 bytes.  The scale record of each (row, block) is `Sa` plus the four sub-block
`da` bytes; `DUP` writes the same bytes and records to rows `r+rows` as well.

**QST (0x22)** quantizes groups of `D` elements and writes `rows*KB*D` int8 bytes to DRAM at
`dst + r*drs + c*es` (HALF: only the first `KB*D/2` bytes of each row), then the scale row at
`sdst + r*len`: `len = 4` in ROW mode (just `S`, little endian) else `4 + 4*ceil(KB/4)` bytes
(`S`, then one offset byte per K-block, zero padded).  `sdst` must be 4-byte aligned and the
data/scale byte ranges must not overlap.

The quantizer is a serial engine (one element per cycle, two passes over each row: amax, then
the q bytes) hung off the sequencer as state `ST_QUANT`; it owns both TMEM read ports while it
runs and writes DRAM through a new byte-write port on `mini_dram.sv`.  New error codes:
**6** `ERR_ACT` (QACT ACT RAM bounds, QACT/QST TMEM range), **7** `ERR_QST` (QST data/scale
range, overlap or a misaligned scale address) — both fit the 3-bit `ecode`; step 7's codes 8/9
will need it widened to 4 bits.

### ACT RAM layout and ports

`mini_actram #(D, ACT_BLOCKS, ACT_ROWS)` holds the production layout, flat so the testbench can
dump it: `act [ACT_ROWS][ACT_BLOCKS*D]` int8 bytes, `ascale [ACT_ROWS][ACT_BLOCKS]` fp32 `Sa`,
`adoff [ACT_ROWS][ACT_BLOCKS]` one word of four uint8 `da` bytes.  Ports:

* quantizer: one ACT byte (plus a second port for `DUP`), one `Sa` word and one packed `da`
  word per cycle;
* MXU (step 7): combinational read ports — `(row, lin)` byte read, `(row, block)` `Sa` and
  `da` reads, **`(row, word)` 32-bit read of four consecutive int8 bytes** (byte 0 in bits
  `[7:0]`), and **`(row, block)` 64-bit scale-record read `{da3,da2,da1,da0, Sa}`**.

`tb_mini` now also dumps `act.hex`, `ascale.hex` and `adoff.hex`, and `ladder/harness/mini.py`
compares all three against `isasim`'s `Slice.act/ascale/adoff` on every run (the step-4/5
programs simply leave them all zero).
