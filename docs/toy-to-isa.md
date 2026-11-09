# From the toy machine to the openTPU ISA

Step 0 imported [tiny-tpu](https://www.tinytpu.com/) verbatim; step 2 writes down its
actual interface ([toy-isa.md](toy-isa.md)); step 3 imports the openTPU software contract
this ladder builds the rest of the machines against. This page is the map between the two
worlds, and the argument for why the imported bit-exact ISA simulator is the oracle for
steps 4–8.

Nothing in this step touches RTL. The ladder adopts three artefacts from the product tree
at `ca05e24f` (Apache-2.0, kept verbatim):

| artefact | what it is |
| --- | --- |
| [isa.md](isa.md) | the ISA contract: every instruction, field, flag and arithmetic rule |
| `opentpu/isa.py` | the Python encoder/decoder for that contract (8 × 32-bit words) |
| `opentpu/isasim.py` | the bit-exact machine: slices, TMEM/ACT RAM/DRAM, every opcode |
| `opentpu/fp32.py` | the fp32 arithmetic `isasim` and the RTL both implement |
| `opentpu/quant.py` | the weight/activation quantization the MXU formats use |

The Apache-2.0 license text the product tree ships travels with the package as
`opentpu/LICENSE`; the files themselves are byte-identical to `ca05e24f` (step 3 commits
them unchanged, no header edits).

## The toy machine, in openTPU terms

The toy is a fixed-function training accelerator for the 2→2→1 XOR MLP. The authoritative
description of its ports, UB layout and Q8.8 semantics is [toy-isa.md](toy-isa.md) (step 2);
what matters here is how each piece has to change to become a general inference machine.

| toy (step 0–2) | openTPU ISA (step 3 contract) | where it goes in the ladder |
| --- | --- | --- |
| **Q8.8 fixed point** (`signed [15:0]`, 8 fractional bits, saturating) in every PE, UB word and VPU stage | **fp32** IEEE-754 binary32 as `docs/isa.md` "Arithmetic" defines it: roundTiesToEven, flush-to-zero, defined exp2 / recip / rsqrt / log2 sequences; int8 only inside the MXU's exact integer accumulation | step 5 (VPU) and step 7 (MXU epilogue) |
| **2 × 2 systolic array** of Q8.8 MACs, one MAC per PE per cycle, data staggered by hand | **systolic MXU** of `MCOLS` × `D` int8 lanes: a stationary ACT-RAM operand and a streamed weight operand, exact integer per (row, D-block) products, per-block power-of-two scales, one fp32 epilogue per output | step 7 |
| **128-word unified buffer** (16-bit words, one read pointer, transpose), written by the host or the VPU | **TMEM** 32-bit word-addressed fp32 scratchpad (64K–128K words on the card) plus a **DRAM** image (4 GiB on the card) and **ACT RAM** (int8 blocks + scale records); explicit `LD` / `ST` / `QACT` / `QST` moves between them | steps 4 and 6 |
| **94-bit microcode word** decoded straight into datapath control; the control unit is not instantiated in `tpu.sv` (see step 1's README correction) | **8 × 32-bit instruction**, `w0 = opcode[7:0] \| ra[11:8] \| rb[15:12] \| rc[19:16] \| rd[23:20] \| flags[31:24]`, `w1..w7` immediates; addresses are `R[x] + w`, so loops and run-time positions come from registers | step 4 |
| no real control flow: fixed test sequences drive the datapath | **sequencer**: `R0–R15` (`R0` = 0), `LI/ADDI/LOOP/HALT`, nested loops (depth 4), `BAR`/`GATHER`, `HALT CHAIN`; each instruction is one of the units' commands (`otpu_pkg.cmd_t`), units overlap when their footprints do not conflict | step 4 |
| **VPU as four hard-wired bias / leaky-ReLU / loss / derivative pathways**, selected by a 4-bit control field | **VOP**: 20 defined ops (`ADD…FILL`, `EXP2`, `RECIP`, `RSQRT`, `LOG2`, `EXP2SUB`, reductions `RSUM/RMAX/RSSQ/RDOT/ARGMAX`, `OUTER`) with FULL/ROW/COL/SCALAR B modes over TMEM | steps 5 and 8 |
| host writes UB words and drives a testbench over the toy's port list | **host contract**: a program image in DRAM, `PROG_ADDR/PROG_N`, `CTRL.LOAD`, run arguments `R8–R15`, `CTRL.RUN`, `CAPS`/`CFG_*` registers; in `isasim` the same model is `Machine(cfg, programs, drams, args=…)` plus the `WAITW` host hook | step 10–11 |

## What the ISA contract actually pins down

Three properties make it a usable oracle rather than a second implementation:

1. **Encodings are total.** Every byte in an 8-word instruction has a meaning; field widths
   overflow as `ValueError`, not a truncation (`opentpu/isa.py` `_check`). The hand-assembled
   step-3 program re-derives `w0` for `LI R1, 3` from `docs/isa.md` and checks it against the
   encoder.
2. **Semantics are bit-exact, including the arithmetic corners.** fp32 results are defined
   down to the bit: flush-to-zero, signed zeros under roundTiesToEven, the composite
   `exp2/recip/rsqrt/log2` instruction sequences and their ulp bounds, `q8`'s saturating
   round-half-to-even, the MXU's exact integer accumulation and its window drops. `tests/
   test_isa.py` and `tests/test_fp.py` in the product tree are the executable form; step 3's
   `ladder/tests/test_step03_fp32.py` keeps every non-RTL check.
3. **Memory model is explicit.** TMEM is word-addressed fp32; DRAM is byte-addressed,
   little-endian, word-aligned; ACT RAM is int8 blocks plus scale records; `LD`/`ST`/`QACT`/
   `QST` are the only moves. An unaligned access or an out-of-range address is a `SimError`,
   not undefined behaviour.

## Why `isasim` is the oracle for steps 4–8

The ladder's mini-core rungs are small, readable machines in `rtl/ladder/`, written one unit
at a time:

- **step 4** ISA sequencer + TMEM + `LD/ST`,
- **step 5** VPU elementwise fp32,
- **step 6** quantizer + ACT RAM,
- **step 7** MXU (int8 MM),
- **step 8** reductions and ARGMAX.

Each rung is accepted the same way the product RTL is accepted in `tests/test_rtl.py`: the
same program and the same DRAM image go through the mini-core and through `isasim`, and the
**TMEM and DRAM contents of every slice must be identical, bit for bit**. No tolerances, no
statistical agreement: the arithmetic is defined, so any difference is a design bug in the
mini-core (or in the contract, which step 3 freezes).

That is the whole reason step 3 exists before any RTL: once the oracle is in-tree and tested,
steps 4–8 never have to invent an expected value. They generate programs (hand-written and
randomized), run both machines, and compare.

```
            hand-written / randomized program + DRAM image
                          |                         |
                  rtl/ladder/mini-core        opentpu/isasim.py
                  (Icarus, steps 4-8)         (bit-exact golden model)
                          \                       /
                        TMEM + DRAM bit-identical?
```

From step 9 on, the same comparison runs against the production RTL through
`opentpu/rtlsim.py` and `tb_top`, and from step 14 the LLM stack is held to it token for
token. The ladder does not re-invent the contract; it adopts it once, here, and then holds
every later machine to it.

## What step 3 does not import

`opentpu/compiler.py`, `language.py`, `runtime.py`, `kernels/`, `llm/`, the host drivers and
`rtlsim.py` are deliberately absent: steps 4–8 need only the ISA-level golden model. They
arrive with steps 9–14, when the RTL and host tiers that consume them arrive too. The
production tests that exercise them (the MM-on-ISA and kernel tests of
`tests/test_quant.py`) stay in the product tree and are re-imported with those steps.
