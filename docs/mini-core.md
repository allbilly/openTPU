# The ladder mini-core (step 4): an openTPU-ISA machine

This document describes `rtl/ladder/mini_*.sv` — the first real openTPU-ISA machine written for
the ladder, and the base the next rungs (quantizer, MXU, reductions) extend.  Step 4 built the
sequencer, TMEM, DRAM and LD/ST; step 5 adds the VPU (section [The VPU](#the-vpu-step-5)).  Its job is
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
| other |      | error 1 (MM/QACT/QST/WAITW/DSTEP/STREAM/GATHER arrive in steps 6-9) |

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
| `rtl/ladder/otpu_fp.sv` | the product tree's fp32 package, copied verbatim (`ca05e24f`, Apache-2.0) |
| `sim/ladder/tb_mini.sv` | testbench / board protocol |
| `ladder/harness/mini.py` | build, run, oracle comparison |
| `ladder/tests/test_step04_core.py` | the step-4 acceptance suite |

## Running the step

```
python3 ladder/run.py step 4            # pytest via the ladder runner, writes the receipt
python3 -m pytest -v ladder/tests/test_step04_core.py   # directly
python3 ladder/run.py step 5            # the VPU suite (22 tests, ~14 s, Icarus only)
python3 -m pytest -v ladder/tests/test_step05_vpu.py    # directly
```

The suite is light (7 tests, ~4 s): instruction semantics with concrete expected bytes, an 8/16/8-
word LD/ST copy compared on the full 256 KiB spec DRAM, single/nested/three-deep loops with
carried pointers and zero-count skips, argument registers and `ADDI` address arithmetic, the error
model, `HALT` placement, and 24 random programs fuzzed against `isasim`.
