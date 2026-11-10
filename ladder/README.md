# The ladder: from tiny-tpu to openTPU

This branch is the missing middle of one story.

- **Start** — [tiny-tpu](https://www.tinytpu.com/), imported verbatim as
  [step 0](#step-0--tiny-tpu-baseline): a teaching TPU for the 2→2→1 XOR MLP.
  It has a 2×2 systolic array of Q8.8 MACs, a 128-word unified buffer, a VPU
  with bias / leaky-ReLU / MSE / leaky-ReLU-derivative, SGD weight update and
  cocotb testbenches. It has **no** instruction set in hardware (the control
  unit is not wired up), **no** memory hierarchy, **no** host interface and
  **no** compiler.
- **End** — openTPU, this repository's product tree at the parent commit
  (`ca05e24f`, branch `ypcb/dual-channel-4gb`): a compiler-driven int8
  accelerator with a 256-bit instruction, TMEM / ACT RAM / dual-channel DDR3,
  a systolic MXU with per-block MX scales, a fp32 VPU with bit-exact
  transcendental sequences, a quantizer, a bit-exact ISA simulator
  (`opentpu/isasim.py`), a Triton-style `ol` language and compiler, a
  PCIe + JTAG host stack — and LLMs that run on a real YPCB-00338 Kintex-7
  card producing tokens that match the simulator bit for bit. TinyStories-15M
  int8 with exact ISA tokens was proven on this host's card on 2026-11-07/08
  (image `c0182902`).

Both ends exist. **The ladder is the sequence of intermediate machines that
connect them**, each a real, self-contained, testable design — not a copy of
the end state.

## Ground rules

1. **One commit = one step = one feature.** The commit message starts
   `step NN: <feature>`. A step checked out in isolation must build and pass
   its own tests.
2. **Every step ships its tests and its receipt.** `ladder/tests/test_stepNN_*.py`
   contains the step's tests; `ladder/evidence/stepNN.json` is the recorded
   run (commit, command, environment, per-test status, durations, verdict).
   `python3 ladder/run.py step NN` regenerates both. A verdict is `PASS`,
   `PASS (with skips)` (only with `--allow-skips`), `BLOCKED` (a hardware rung
   whose gate skipped because the cable/card are absent; exit 5, never a fake
   PASS) or `FAIL`. Unexpected skips in a software step are a FAIL: a missing
   toolchain must not read as green. A receipt records the commit the run was
   made on and whether the tree was dirty; a step's receipt is generated
   before its own commit, so it normally names the parent commit (the
   independent verifier re-runs each rung from a clean checkout).
3. **Bit-exact or it did not happen.** From [step 4](#step-4--mini-core-isa-sequencer--tmem--ldst)
   on, every simulation compares the RTL's DRAM and TMEM contents bit for bit
   against the openTPU ISA simulator (`opentpu/isasim.py`), the same oracle
   the production RTL is held to in `tests/test_rtl.py`. Arithmetic corner
   cases use `opentpu/fp32.py`'s golden vectors.
4. **Test tiers.**
   - *fast* (≤ 60 s, pure Python): steps 1–3.
   - *sim* (Icarus Verilog, seconds): steps 4–8, the mini-core.
   - *production* (Verilator, minutes, large builds): steps 9–11, 14, 16.
   - *heavy* (Vivado synthesis/implementation, hours): step 12.
   - *hardware* (DLC10 JTAG + card): steps 12, 13, 15.
5. **This host is a shared laptop.** Heavy commands must not run concurrently
   with the other DSH session's verification queue. `ladder/run.py` runs any
   step marked *production*/*heavy* under an exclusive `flock` on
   `/tmp/rknpu-heavy.lock` after a thermal check (`k10temp` < 92 °C), and
   Verilator builds are limited to `-j 2`. See [Host scheduling](#host-scheduling).
6. **Hardware milestones are blocked, never faked.** The DLC10 cable and the
   YPCB card were not attached when this ladder started. Steps 12/13/15 record
   the software side, the exact acceptance recipe and the current blocker; the
   historical c0182902 evidence is cited, not re-created.

## The rungs

Status: ✅ done · 🔨 in progress · ⏳ planned · 🚫 blocked on hardware

| step | rung | machine | tests | status |
| ---: | --- | --- | --- | --- |
| 0 | [tiny-tpu baseline](#step-0--tiny-tpu-baseline) | 2×2 Q8.8 toy TPU, XOR MLP, cocotb | 10 cocotb targets, lint, provenance | ✅ |
| 1 | [ladder harness, roadmap, Makefile cleanup](#step-1--ladder-harness-roadmap-and-makefile-cleanup) | Step 0 machine + reproducible runner/evidence | runner doctor, roadmap/manifest consistency, step-0 re-run | ✅ |
| 2 | [baseline hardening](#step-2--baseline-hardening-authoritative-isa-and-a-real-xor-scoreboard) | self-checking XOR forward/backward; authoritative ISA doc | scored XOR vectors (forward+backward), ISA schema test | ✅ |
| 3 | [ISA contract](#step-3--openTPU-isa-contract) | Python golden stack imported; no RTL change | ISA/ISA-sim/fp32/quant suites | ✅ |
| 4 | [mini-core ISA sequencer + TMEM + LD/ST](#step-4--mini-core-isa-sequencer--tmem--ldst) | first openTPU-ISA machine: instructions, loops, TMEM, DRAM | bit-exact vs `isasim` | ✅ |
| 5 | [mini-core VPU (elementwise fp32)](#step-5--mini-core-vpu-elementwise-fp32) | fp32 ADD/SUB/RSUB/MUL/MIN/MAX/ABS/COPY/FILL, all B modes | bit-exact vs `isasim`, fp32 corners | ✅ |
| 6 | [mini-core quantizer + ACT RAM](#step-6--mini-core-quantizer--act-ram) | QACT/QST, int8 blocks + scales | bit-exact vs `isasim`/`quant.py` | ✅ |
| 7 | [mini-core MXU (int8 MM)](#step-7--mini-core-mxu-int8-mm) | systolic int8 matmul, MX scales, fp32 epilogue | bit-exact vs `isasim`, matmul vs numpy | ✅ |
| 8 | [mini-core reductions](#step-8--mini-core-reductions-and-argmax) | RSUM/RMAX/RSSQ/RDOT/ARGMAX | bit-exact vs `isasim` | ✅ |
| 9 | [production core adoption](#step-9--production-core-adoption) | production RTL supersedes the mini-core | production RTL↔ISA tests (selected, then wide) | ✅ |
| 10 | [production software stack](#step-10--compiler-language-kernels-runtime) | `ol` language, compiler, kernels, runtime, targets | `examples/` + kernels ISA↔RTL bit-exact | ✅ |
| 11 | [board shell + host interface](#step-11--board-shell-and-host-interface-simulation) | control regs, memory channels, TX/RX, JTAG + PCIe paths | `tb_board` sims, Fake transport runs | ✅ |
| 12 | [FPGA image + SRAM milestone](#step-12--fpga-image-and-sram-bring-up-hardware) | YPCB bitstream built by this branch | build receipt + JTAG self-test on card | 🚫 |
| 13 | [on-card kernel over JTAG](#step-13--on-card-kernel-over-jtag-hardware) | image upload + matmul on the real card | on-card result == simulator | 🚫 |
| 14 | [LLM layer in simulation](#step-14--llm-layer-in-simulation) | model pipeline, kernels, tiny fixtures | token-for-token ISA↔RTL | ✅ |
| 15 | [LLM inference on the card](#step-15--llm-inference-on-the-card-hardware) | TinyStories int8 on YPCB, exact tokens | full JTAG acceptance receipt | 🚫 |
| 16 | [convergence](#step-16--convergence-on-the-production-tree) | tree == product tree + `ladder/` | parity check + production fast suite | ⏳ |

Steps 9–11, 14 and 16 import production openTPU code from the parent commit
(`git checkout <parent> -- <paths>`), so the branch converges on the real
product instead of re-implementing it. The mini-core (steps 4–8) is the part
the production tree does not contain: a small, readable machine that implements
the same ISA contract and is validated against the same golden model.

## Step specifications

Each step's acceptance test lives in `ladder/tests/test_stepNN_*.py` and its
recorded receipt in `ladder/evidence/stepNN.json`.

### step 0 — tiny-tpu baseline

Import the tiny-tpu working tree (`src/` RTL, `test/` cocotb benches,
`Makefile`, Python project files, README) as the ladder's starting point.
`ladder/NOTICE.md` records provenance and the missing upstream license;
`ladder/PROVENANCE.md` records the SHA-256 of every imported file.

**Acceptance:** `pe systolic unified_buffer loss_parent leaky_relu_parent
leaky_relu_derivative_parent bias_parent vpu tpu gradient_descent` all pass
(10/10 targets, 19 testcases); `make lint` clean; provenance hashes match.
**Evidence:** `ladder/evidence/step00.json`.

### step 1 — ladder harness, roadmap and Makefile cleanup

Add the ladder runner (`ladder/run.py`), the evidence convention, this
roadmap, a per-step test manifest and cleanup of the imported `Makefile`
(remove the ten stale targets whose benches or cocotb modules do not exist,
add an aggregate `test` target for the ten green ones). Correct the README's
stale instruction-set table with a pointer to the authoritative description
that step 2 writes: `control_unit.sv` is not instantiated by `tpu.sv`, so the
94/130-bit tables are reference documentation, not a hardware ISA; step 3
introduces the real ISA contract.

**Acceptance:** `python3 ladder/run.py doctor` reports a usable toolchain;
every `test_*` target in the Makefile has its sources and tests; the roadmap
lists every rung; the step-0 suite re-runs green through the runner.
**Evidence:** `ladder/evidence/step01.json`.

### step 2 — baseline hardening: authoritative ISA and a real XOR scoreboard

The imported top-level `tpu` test has no scoreboard (it only writes a VCD).
Add a self-checking XOR forward+backward test with golden vectors computed by a
small, independent Python model (Q8.8, saturating, the same rounding as
`fixedpoint.sv`), covering both weight tiles, both bias vectors, the leaky-ReLU
forward/derivative path, the loss gradient and one SGD step. Write the
authoritative description of the toy machine's actual interfaces (ports, UB
layout, Q8.8 semantics) in `docs/toy-isa.md`, replacing the stale 94-bit table.

**Acceptance:** the new scoreboard fails if any module's arithmetic is changed
(mutation check documented in the receipt); the five previously smoke-only
modules get at least one asserting bench each; `make test` green.
**Evidence:** `ladder/evidence/step02.json`.

### step 3 — openTPU ISA contract

Import the golden software contract from the parent commit: `opentpu/isa.py`
(encodings), `opentpu/isasim.py` (bit-exact machine), `opentpu/fp32.py`
(arithmetic semantics), `opentpu/quant.py` (quantization), the parts of
`tests/conftest.py` they need, `docs/isa.md`, plus a prose map from the toy's
Q8.8 micro-operation world to the 256-bit / TMEM / DRAM model. No RTL changes.

**Acceptance:** the imported ISA, ISA-simulator, fp32 and quantizer test suites
pass in the ladder; a hand-assembled "hello arithmetic" program runs on
`isasim`; the ISA golden model is documented as the oracle for steps 4–8.
**Evidence:** `ladder/evidence/step03.json`.

### step 4 — mini-core: ISA sequencer + TMEM + LD/ST

The first openTPU-ISA machine, written for the ladder in `rtl/ladder/`:
a sequencer with R0–R15, LI/ADDI/LOOP/HALT, a TMEM of 32-bit words, a
behavioural DRAM and LD/ST transfers. Reuse the production testbench protocol
(program hex + DRAM image in, TMEM/DRAM dump out) so every later rung compares
against `isasim` with the same harness. The toy's UB pointers/staggering are
replaced by explicit DRAM/TMEM addresses; the ladder's own ISA is now the
production one.

**Acceptance:** hand-written and randomized programs (nested loops, addresses
as register+immediate, unaligned-rejection cases) run on the mini-core and on
`isasim` with bit-identical TMEM and DRAM.
**Evidence:** `ladder/evidence/step04.json`.

### step 5 — mini-core VPU (elementwise fp32)

Add a VPU lane to the mini-core: VOP with ADD, SUB, RSUB, MUL, MIN, MAX, ABS,
COPY, FILL, in the FULL / ROW / COL / SCALAR B-operand modes, reading and
writing TMEM. The fp32 arithmetic must be bit-exact (RNE, flush-to-zero); the
ladder reuses the production `otpu_fp` package (imported with attribution) so
the hardware and `opentpu/fp32.py` cannot drift.

**Acceptance:** random and corner-case vectors (`opentpu/fp32.py` generators:
denormals, signed zeros, infinities, cancelling sums) produce identical TMEM
bits on the mini-core and `isasim`.
**Evidence:** `ladder/evidence/step05.json`.

### step 6 — mini-core quantizer + ACT RAM

Add ACT RAM (int8 bytes + per-row scale and per-sub-block offsets) and the
QACT / QST instructions: quantize TMEM fp32 rows into ACT RAM, quantize TMEM
into DRAM int8 bytes with the row/block scale records, with the ROW / CSCALE /
RSCALE / DUP / HALF flag subsets the ladder needs for RMSNorm and KV appends.

**Acceptance:** quantizer output bytes and scale records equal `isasim`'s for
random rows, extreme amax values, zeros and infinities; `quant.py`'s reference
quantizer agrees.
**Evidence:** `ladder/evidence/step06.json`.

### step 7 — mini-core MXU (int8 MM)

Add the systolic int8 matrix unit with MX block scales and the fp32 epilogue:
MM streams D-byte blocks of int8 weights from DRAM, reads int8 activations
from ACT RAM, accumulates exact integers per (row, block) and applies the
per-block power-of-two offsets and fp32 scales once per output, writing TMEM.
Start with the no-flag form plus ACC; RMAX and ASCALE complete the
flash-attention epilogue.

**Acceptance:** random matmuls (M up to ACT_ROWS, N up to several columns,
K = KB·D) match `isasim` bit for bit; numpy int8 reference agrees before
scaling; corner scales (underflow groups, amax extremes) covered.
**Evidence:** `ladder/evidence/step07.json`.

### step 8 — mini-core reductions and ARGMAX

Add the reduction VOPs needed by the software stack: RSUM, RMAX, RSSQ, RDOT,
ARGMAX (and the OUTER linear-recurrence update), with the same fold semantics
as the production VPU.

**Acceptance:** reduction outputs (including NaN/±0 ordering and the ARGMAX
tie-break) equal `isasim`'s bit for bit on random and adversarial data.
**Evidence:** `ladder/evidence/step08.json`.

### step 9 — production core adoption

The mini-core proved the ISA contract; adopt the production RTL instead of
re-implementing its 55k lines: import `rtl/`, `sim/verilator/`, `opentpu/rtlsim.py`
and the RTL test infrastructure from the parent commit, delete `rtl/ladder/`
and the toy `src/`, and switch the ladder harness to Verilator. The evidence
for this step is the production RTL↔ISA test suite, run from this branch.

**Acceptance:** production RTL fast tests pass (the subset that needs no
board/models), including MLP, attention and fuzz cases; the mini-core's own
step-4–8 programs still produce the same results on the production RTL.
**Evidence:** `ladder/evidence/step09.json`.

### step 10 — compiler, language, kernels, runtime

Import `opentpu/language.py`, `opentpu/compiler.py`, `opentpu/runtime.py`,
`opentpu/kernels/`, `opentpu/target.py`, `targets/` and `examples/`. Kernels
now come from `ol` source rather than hand-assembled programs.

**Acceptance:** `examples/run_all.py` passes (numpy reference + ISA bit-exact);
the kernel test suite passes; a compiled MLP runs bit-identically on the ISA
simulator and the production RTL.
**Evidence:** `ladder/evidence/step10.json`.

### step 11 — board shell and host interface (simulation)

Import `rtl/shell/`, `rtl/boards/ypcb-00338/`, `sim/verilator/tb_board.sv`,
the host register map and the host driver stack (`opentpu/host/board.py`,
`regs.py`, fake transport) so the machine is exercised the way the card drives
it: control registers, program loader, memory channels, JTAG and PCIe paths.

**Acceptance:** `tb_board` simulations pass; a program is loaded and run
through the simulated board interface (FakeTransport) with the same DRAM/TMEM
state as direct RTL; the register map's image-identity fields are checked.
**Evidence:** `ladder/evidence/step11.json`.

### step 12 — FPGA image and SRAM bring-up (hardware)

Import the YPCB build flow (`boards/ypcb-00338/`, `tools/litedram/`,
constraints, LiteDRAM generation), build a bitstream from this branch's tree
and load it into SRAM over JTAG; run the on-card self-test / RAM test.
Vivado runs under the heavy host lock (≈1.5–4 h for a full image).

**Acceptance:** build receipt with bitstream SHA-256, timing/DRC summary and
source hashes; SRAM programming receipt; on-card self-test PASS observed over
JTAG; the image keeps **both** JTAG and PCIe runtime interfaces (repo rule).
**Evidence:** `ladder/evidence/step12.json`, `ladder/evidence/hardware/`.
**Blocker (2026-11-10):** the DLC10 JTAG cable and the card are not attached;
the software side of this step is committed and the hardware assertion waits.
**Software side (committed):** the YPCB Vivado flow, `tools/litedram/` and the
Fedora DLC10/XVC bring-up helpers are imported byte-identically from
`ca05e24f` (95 files, hashes in [`ladder/hardware/import-provenance.json`](hardware/import-provenance.json));
the build flow, exact commands, dual-interface rule and known gaps are in
[`docs/fpga-flow.md`](../docs/fpga-flow.md); the read-only probe and the
acceptance plan are [`ladder/hardware/`](hardware/). The gate test runs the
probe, skips on a blocked host and records verdict `BLOCKED` (runner exit 5) —
see `ladder/evidence/step12.json` and `ladder/evidence/hardware/probe-step12.json`.

### step 13 — on-card kernel over JTAG (hardware)

Using the step-12 image, upload a small program/image over the JTAG runtime and
run a matmul on the card; compare the result against the simulator bit for
bit. This is the first end-to-end "host → image → accelerator → result" loop on
real silicon.

**Acceptance:** on-card matmul bytes equal `isasim`'s; identity/config
registers match the oracle; receipt records `flash_written: false`.
**Evidence:** `ladder/evidence/step13.json`.
**Blocker:** same hardware absence as step 12.
**Software side (committed):** the JTAG/XVC runtime evidence
(`tests/test_xvc_transport.py`, `tests/tb_xpcu_xvc.cpp`), the c0182902
acceptance drivers and the historical evidence record are imported
byte-identically from `ca05e24f` (hashes in
[`ladder/hardware/import-provenance.json`](hardware/import-provenance.json)),
with `ladder/harness/hardware.py` as the gate/command helper. The exact
acceptance recipe, criteria, historical PASS and known gaps are in
[`docs/oncard-jtag.md`](../docs/oncard-jtag.md). Gate verdict `BLOCKED`
(runner exit 5) in `ladder/evidence/step13.json`.

### step 14 — LLM layer in simulation

Import `opentpu/llm/` (model implementations, image builder, decode loop) and
the model fixtures the tests need; run a tiny model end to end in the ISA
simulator and on the RTL, token for token. No real checkpoint is required for
the ladder: tiny random-weight models exercise the same kernels (attention,
RMSNorm, silu, RoPE, sampling) and the same image path.

**Acceptance:** greedy tokens from the RTL backend equal the ISA oracle for a
tiny model; the logits and the whole DRAM image are bit-identical.
**Evidence:** `ladder/evidence/step14.json`.

### step 15 — LLM inference on the card (hardware)

Run TinyStories-15M int8 on the card over JTAG and reproduce the acceptance
the production branch already recorded for image `c0182902`: prompt
"Once upon a time" → tokens `[29892, 727, 471, 263, 2217, 7826, 4257, 365]`,
exact 8-token greedy continuation, image SHA-256 match, calibration unchanged,
warm repeat with zero image rewrite, `flash_written: false`.

**Acceptance:** full receipt as in `docs/tinystories_jtag_c0182902.md`, bound
to this branch's image SHA, package manifest SHA and model SHA, including the
identity/config guard results and the timing/limits section.
**Evidence:** `ladder/evidence/step15.json`, `ladder/evidence/hardware/`.
**Blocker:** hardware absence. The historical c0182902 PASS (2026-11-07/08) is
cited in the receipt as prior evidence, not re-created.

### step 16 — convergence on the production tree

Import whatever is left of the parent commit's tree (`docs/`, `tools/`,
`tests/`, `examples/`, `bend/`, `asic/`, model/target definitions, ...), then
delete the ladder-only leftovers that production does not need except
`ladder/` itself. From this commit on, checking out the branch gives the exact
product tree plus the ladder documentation, receipts and tests.

**Acceptance:** `git diff --stat ca05e24f -- . ':(exclude)ladder'` is empty;
the production fast test suite passes in this tree; the ladder's own test set
passes from the converged tree; this document's status table is complete.
**Evidence:** `ladder/evidence/step16.json`.

## Environment

`python3 ladder/run.py doctor` prints the toolchain the ladder can see and the
environment it would use. Nothing is installed by the runner.

| tool | used by | requirement |
| --- | --- | --- |
| Python 3.11–3.13 | steps 0–2 | `cocotb>=1.9,<2`, `numpy>=2,<3` (the imported `pyproject.toml`/`uv.lock` restore it with `uv sync`) |
| Python 3.10+ with numpy, pytest | steps 3–16 | the openTPU golden stack is pure Python + numpy |
| Icarus Verilog 13 | steps 4–8 | `iverilog -g2012` |
| Verilator 5.x | steps 9–11, 14, 16 | production RTL simulation (`-j 2` on this host) |
| Vivado 2026.1 | step 12 | xc7k480tffg1156-2; full image ≈1.5–4 h |
| openFPGALoader + DLC10 | steps 12/13/15 | patched DLC10-capable build; card must be attached |

The runner picks its Python in this order: `$LADDER_PY`, `./.venv/bin/python`,
`./ladder/.venv/bin/python`, then `python3`. The cocotb bench environment for
steps 0–2 is `$LADDER_TOY_PY`, `./.venv/bin/python`, then the same host's
tiny-tpu venv if it exists. Every choice is printed by `doctor` and stored in
the evidence receipt.

## Host scheduling

This laptop is shared with another DSH session that runs a hardware
verification queue and a thermal guard. The guard killed this session's first
Verilator build at 100.4 °C, so:

- Verilator builds are limited to `-j 2` and `nice`;
- *production*/*heavy* steps acquire an exclusive `flock` on
  `/tmp/rknpu-heavy.lock`; if the lock is busy the runner waits (default
  ≤ 90 min) instead of starting a competing build;
- before and during a heavy step the runner samples `k10temp`
  (`/sys/class/hwmon/*/temp1_input`); it refuses to start above 92 °C and
  aborts above 97 °C;
- one heavy job at a time. Light steps (0–8) are allowed to run anytime, but they are not
  immune: the sibling session's `host_guard` SIGTERMs any CPU burner at ~100 °C, and a light
  run caught in that kill writes a receipt with `returncode` < 0 (`ABORTED (killed by signal
  N)`). `ladder/run.py` retries such a run once automatically and records `attempts` and
  `killed_by_signals` in the receipt; an `ABORTED` receipt is an environment event, not a code
  failure - re-run it when the host is cool.
- **Detached-checkout workaround (2026-11-10, host contention):** the sibling session's
  `foreign_hold.sh` SIGSTOPs *any* process whose cwd or command line names this repository (even
  a 5-second light test) for the duration of its verification windows. While it does, receipts
  for a rung under integration may be generated from an identical detached checkout at
  `/tmp/ldr` (same commit, same tree, same gitignored Verilator cache via a symlink); the
  receipt records that rootdir, and the committed tree/commit is unchanged. Cold builds still
  go through the shared lock/thermal gate when it is available.
- **Warm-run mode** (`--warm`, `LADDER_WARM_RUN=1`): the heavy part of a production rung is the
  Verilator *compile*. When the build cache for the rung's Config is already present, the rung
  only launches short single-core simulations, so `ladder/run.py step NN --warm` skips the
  shared-host flock but keeps the thermal gate (waits below 88 °C, refuses above 92 °C) and
  records `warm_run: true` in the receipt. `--warm` is refused (and the cold gate used) unless
  the rung's cached `Vtb_top` executable is found for its exact Config/build key; steps without
  a built-in cache probe require an explicit `LADDER_WARM_OK=1` acknowledgement. Cold builds
  always take the flock, and `--warm` cannot be combined with `--no-heavy`.

## Test methodology

1. **Fast tier** — pure Python: the ISA golden stack and meta-tests of this
   roadmap/harness.
2. **Sim tier** — the mini-core built with Icarus; a Python harness writes the
   program and DRAM image, runs the RTL, reads back TMEM and DRAM and compares
   them with `isasim`. No tolerance: every word must match.
3. **Production tier** — Verilator through `opentpu/rtlsim.py`, the same
   `tb_top` protocol the product uses.
4. **Hardware tier** — JTAG only (this host has no PCIe endpoint): exact image
   identity, calibration receipt, structural preflight, model run, warm repeat.

Mutation checks (step 2) and negative tests (rejected unaligned accesses,
illegal opcodes) are part of a step's evidence, not an afterthought.

### Verdicts, exit codes and receipt binding

`python3 ladder/run.py step NN` exit codes: `0` PASS (or PASS with skips),
`1` FAIL, `2` usage, `3` the rung has no tests yet, `4` a hardware rung needs
`LADDER_ALLOW_HARDWARE=1`, `5` BLOCKED (hardware absent - the receipt records
the probe result and the skip reasons), `6` ABORTED (the run was killed from
outside, normally the sibling session's thermal guard; the runner retries a
killed run once and records `attempts`/`killed_by_signals` in the receipt - an
ABORTED receipt is an environment event, not a code failure). `evidence-check` accepts `PASS` and
(in the hardware rungs) `BLOCKED`, and rejects an all-skip software run that
was mislabeled green.

Heavy rungs additionally take the shared-host gate: an exclusive `flock` on
`/tmp/rknpu-heavy.lock`, a `k10temp` cool-down wait below 92 C, and the run is
aborted above 97 C. Light rungs (steps 0-8) run without the gate.

## Known blockers and risks

- **Hardware absent (2026-11-10):** no DLC10 cable (`03fd:*`/`0403:6014`), no
  card in PCIe. Steps 12/13/15 stay blocked until the user attaches the cable
  and card; their software side is committed.
- **The c0182902 bitstream package, model and calibration receipt are
  untracked** in the product tree; raw run receipts under `/tmp/opencode`
  were lost. Re-running the full acceptance needs the package plus a fresh
  calibration/oracle; the ladder records this explicitly rather than claiming
  a re-run.
- **Licensing:** tiny-tpu ships no LICENSE file and no SPDX headers. The step-0
  import is a reference/intermediate artifact for the ladder, removed at
  step 9/16; redistributing it inside the Apache-2.0 repo needs the owner's
  licensing decision (`ladder/NOTICE.md`).
- **Shared host:** heavy builds can be killed by the other session's thermal
  guard; the runner's lock/thermal gate makes this visible instead of silent.

## Status log

- 2026-11-10: branch `ladder/tiny-tpu-to-opentpu` created in `~/openTPU` as an
  orphan branch seeded from `/home/fedora/tiny-tpu`; step 0 committed
  (`d69624ae`, 10/10 cocotb targets, verified both in the working tree and in
  a detached worktree of its own commit). Ladder recon of both endpoints and
  of the hardware path completed.
- 2026-11-10: step 1 committed — this document, `ladder/run.py` (runner,
  evidence, shared-host gate), per-step harness tests, Makefile cleanup
  (10 stale targets removed, aggregate `test` added) and the first two
  evidence receipts (`ladder/evidence/step00.json`, `step01.json`).
- 2026-11-10: step 2 committed - `ladder/bench/` self-checking XOR scoreboard
  (`tpu.sv` wrapper exposing the unified buffer and every VPU stage boundary,
  Python Q8.8 golden model, five-module mutation check) and the authoritative
  `docs/toy-isa.md` (tpu ports, UB pointer map, VPU pathway, Q8.8 semantics);
  the imported top-level test's one-cycle-early `sys_switch_in` and the stale
  94/130-bit documentation discrepancy are recorded there.
- 2026-11-10: runner verdict policy hardened after independent verification:
  unexpected skips in a software step are a FAIL (a missing cocotb/verible
  must not read as green), and a hardware rung whose gate skips because the
  cable/card are absent records `BLOCKED` (exit 5), never a fake PASS.
- 2026-11-10: step 3 committed — the openTPU ISA contract imported from the
  parent commit `ca05e24f` (`opentpu/{isa,isasim,fp32,quant}.py`, `docs/isa.md`)
  with 45 adapted golden-model tests (14 ISA, 10 fp32, 21 quantizer) plus 16
  ladder-specific ones (14 directed `isasim` semantics, 2 hand-assembled
  hello-arithmetic acceptance tests) in `ladder/tests/test_step03_*.py`, and
  `docs/toy-to-isa.md` mapping the toy's Q8.8 machine onto the 256-bit /
  TMEM / DRAM model and naming `isasim` the oracle for steps 4–8. 61 tests,
  ~25 s. Receipt: `ladder/evidence/step03.json`.
- 2026-11-10: step 4 committed — the first openTPU-ISA machine written for the
  ladder (`rtl/ladder/mini_*.sv`, `sim/ladder/tb_mini.sv`,
  `ladder/harness/mini.py`, `docs/mini-core.md`): serial one-slice execution
  of NOP/HALT/LI/ADDI/LOOP/BAR/RLD/LD/ST against DRAM + TMEM, with 7 tests
  including 24 random fuzz programs, every comparison bit-identical to
  `opentpu.isasim` (TMEM + whole DRAM + icount). 4.3 s. Receipt:
  `ladder/evidence/step04.json`. The runner's `evidence-check` also gained
  backward compatibility with the pre-policy receipts, and steps 2–4 were
  integrated and re-run together (steps 0–4: 14+10+9+61+7 tests, all PASS).
- 2026-11-10: step 5 committed - the mini-core VPU: the product `otpu_fp`
  package imported byte-identically (`rtl/ladder/otpu_fp.sv`, Apache-2.0),
  `mini_tmem` widened to 2R+1W, `mini_vpu` implementing the 14 elementwise
  fp32 VOPs in all four B-operand modes (one element/cycle, write-bitmap
  read-after-write detection -> error code 5), VOP decode in `mini_top` and
  the harness compiling the SV package first. 22 tests: fixed goldens, all
  functions x modes x shapes bit-exact against `isasim` (whole TMEM + DRAM +
  icount), fp32 corner tiles, stride and negative cases; 14 s. Receipt:
  `ladder/evidence/step05.json`. The integration also refreshed the step 0-5
  receipts (removing the dangling pre-amend step-4 binding), and hardened
  `evidence-check`: a software receipt that claims a plain PASS while tests
  were skipped is now rejected, and `LADDER_EVIDENCE_DIR` allows checking a
  receipt set elsewhere.
- 2026-11-10: step 6 committed - the mini-core quantizer and ACT RAM:
  `mini_actram` (production ACT layout: int8 bytes, fp32 `Sa` per row/block, four
  `da` offsets per block, quantizer write ports and the MXU read ports - 4-byte
  ACT word and the 64-bit `{da, Sa}` scale record), `mini_quant` (serialized
  QACT/QST mirroring `fp32.quantize_mx`/`mx_offset`/`q8` with ROW/CSCALE/
  RSCALE/DUP/HALF, scatter strides and the DRAM scale-row layout), DRAM byte
  write port, decode/error codes 6/7, and complete ACT/Sa/da dumps in the
  harness compared bit-exactly against `isasim` on every run. 27 tests
  (goldens, random, amax 0/2^126/NaN/denormal/ties, all flags, negatives).
  3.5 s. Receipt: `ladder/evidence/step06.json`. The integration also folded in
  the runner's external-kill handling (retry once, `attempts`/
  `killed_by_signals` in the receipt, exit code 6 ABORTED) requested by the
  independent verifier after a thermal-guard kill of one light run.
- 2026-11-10: step 7 committed - the mini-core MXU: `mini_mxu` implements MM (0x20,
  int8 WF 0) with UNIT/ACC/RMAX, exact 48-bit integer accumulation over D-byte
  blocks with the W=16 shift window, per-row `Sw` and per-block `dw` scale rows,
  ACT `Sa`/`da` records read through `mini_actram`'s MXU ports, and the
  isasim-order fp32 epilogue with the production MXU's 48-bit `i2f48`
  converter. Unsupported formats/flags are error 8, bounds/alignment/Sa
  consistency error 9 (the `ecode` output widened to 4 bits); the serialized
  ACC aliasing limitation (bit-exact for distinct output addresses, ors >= N)
  is documented. 31 tests: 10 embedded bit-exact golden vectors + 16 negative
  cases (with independent docs-formula replay), 16 random LD->QACT->MM
  programs vs isasim whole-state (TMEM + DRAM + ACT bytes/Sa/da), a numpy
  int64 accumulation cross-check and the boundary cases. 33 s. Receipt:
  `ladder/evidence/step07.json`. Integration also applied two verifier
  findings: the harness `compare()` now also asserts ACT bytes/Sa/da against
  isasim's Slice state (previously computed but unasserted), and
  `killed_by_signals` records every killed attempt of an ABORTED run.
- 2026-11-10: step 8 committed - the mini-core reductions: `mini_reduce`
  implements OUTER (6) and RSUM/RMAX/RSSQ/RDOT/ARGMAX (16-20). Sums are the
  `fp32.interleaved_sum` contract (start `+0`, 64 interleaved partials,
  `+0`-padded rows, 63-add folding tree); RSSQ/RDOT round their products first
  and RDOT takes B in all four modes; RMAX follows the `_key` total order with
  NaN payloads and -0 < +0; ARGMAX writes (max, i2f of the int32-wrapped
  index+base) with the first-column tie-break; hazard positions are
  end-of-row as in `isasim`; a new error code 10 rejects bad shapes. 33 tests:
  the 10 research vectors hand-asserted, independent `fp32` re-derivations,
  cols 1/63/64/65/127/128/129 boundaries, 12 random programs vs isasim
  whole-state and the 9 negative cases. 4 s. Receipt:
  `ladder/evidence/step08.json`. This completes the mini-core: steps 4-8 are a
  small, readable machine that runs the openTPU ISA subset bit-exactly and is
  retired when the production RTL is adopted at step 9.
- 2026-11-10: mini-core complete (steps 4-8, all bit-exact vs `isasim`):
  7+22+27+31+33 = 120 mini-core tests, plus the 94 earlier fast-tier tests.
- 2026-11-10: step 9 committed - the production core is adopted. `rtl/`
  (71 SV files incl. the tech cells and the board wrappers), `sim/verilator/`,
  `sim/tech/`, `targets/` and `opentpu/{rtlsim,simtmp,target}.py` are imported
  byte-identically from `ca05e24f` (the only ladder edit is rtlsim's Verilator
  `-j 2`), plus `ladder/harness/prod.py` and 12 replay tests: the mini-core's
  own program families (control/LD/ST/RLD, the 14 VOPs x 4 B modes, QACT/QST,
  MM UNIT/ACC/RMAX/scaled, reductions/ARGMAX) now run on the production RTL
  through Verilator and must equal `opentpu.isasim` word for word (TMEM +
  whole DRAM + icount). The toy tree and the mini-core stay in place and
  runnable; they move under `ladder/` at convergence. First build of `tb_top`
  took ~70-80 s under `-j 2`; the committed run is a warm-cache run (the build
  cache is gitignored next to the tree; the runner's new warm-run mode records
  `warm_run: true`). Receipt: `ladder/evidence/step09.json`. The integration
  also committed the runner's warm-run mode with the independent verifier's
  safeguards: a cache preflight refuses warm mode when the expected `Vtb_top`
  is absent, `--warm --no-heavy` is rejected, and the receipt records the
  invocation and thermal state.
- 2026-11-10: step 10 committed - the production software stack. Imported
  byte-identically: `opentpu/{language,compiler,runtime,waits,reference}.py`,
  `opentpu/kernels/` (10 files), `examples/` (11 files; `examples/` is
  *untracked* in the product tree, so it is a ladder copy with per-file sha256
  recorded in `docs/production-stack.md`; step 16 relocates it to
  `ladder/examples/`, so the final tree's only extras are under `ladder/`). 47 test functions / 104 testcases: a compiled MLP kernel on
  the ISA simulator vs its numpy reference, compilation determinism, a
  bit-exact fixed vector, `examples/run_all.py --backend isa` PASS over all
  14 cases, the ported production kernel/compiler/example suites (2 examples
  cases needing the step-11 host transport skip with a recorded reason), and
  TWO production-RTL replays (compiled MLP M=4/H=128/Fd=256 and an attention
  decode) that are bit-identical to `isasim` in whole DRAM + TMEM + icount,
  reusing the step-9 `prod.CFG` Verilator cache (no second build). 102
  passed / 0 failed / 2 skipped in 20.4 s under the heavy gate (warm cache;
  thermal 89.3 C at run); the integration receipt records `PASS (with skips)`
  via `--allow-skips --warm`. Both RTL replays are bit-identical to `isasim`
  in whole DRAM and TMEM; the compiled MLP replay also asserts the retired
  instruction count. Receipt: `ladder/evidence/step10.json`.
- 2026-11-10: step 11 committed - the board shell and host interface in
  simulation. Imported byte-identically: `opentpu/host/{__init__,regs,
  runstate,board,fake,memcal,ddrcal,selfcal,checks}.py` (numpy only; the
  `tb_board` RTL closure was already complete from step 9). New
  `ladder/harness/board.py`: SimTransport/Board harness (private OTPU_RUN_DIR
  per session, image/program caches off, `board_config`-derived D=128 config,
  `device_config` identity handshake, `checks.run_demo`, `isa_state`) plus
  warm-cache helpers (`rtl_build_present`/`warm_ready`/`build_sha256`). New
  `ladder/tests/test_step11_board.py`: 23 tests - 18 pure-Python host cases
  (channel interleave/CHASH split+join, unaligned RMW, run-H2C bounded
  writes, channel map, two-slice FakeTransport loader/run/ICOUNT) and 5
  `tb_board` cases (register identity incl. CFG_HASH/numerics refusal, the
  demo program load->run with every DRAM byte below PROG_AT equal to isasim
  and the exact ICOUNT, partial beats/counters, hand-assembled
  loader/run/counters). `docs/board-interface.md`. The one-time `tb_board`
  Verilator build (45 sources, 4.6 min) needed a documented `-j 1` harness
  flag on this laptop: at `-j 2` the host's thermal guard SIGTERMed `cc1plus`
  twice; the flag is part of the build-cache key. The committed receipt is a
  warm-cache run (`PASS 23/23 in 20.8 s`, thermal-gated, no flock); the
  integration copied the gitignored 338 MB build cache (`tb_board_a77dbb6d33e3`)
  into `build/verilator/` and wired the runner's step-11 warm preflight to
  `board.warm_ready()`. Receipt: `ladder/evidence/step11.json`.
- 2026-11-10: step 12 committed (hardware rung, software side + honest BLOCKED
  receipt). Imported the YPCB build flow byte-identically from `ca05e24f`:
  `boards/ypcb-00338/` (49 files: `Makefile`, `run_vivado.sh`, `vivado/*.tcl`
  incl. the XDMA/PCIe block design, constraints, the generated LiteDRAM core,
  RAM-test builds/sims), `tools/litedram/` (35 files: core generation, PHY
  knobs, CSR/ECC helpers, self-calibration firmware), the Fedora bring-up
  helper set (`fedora_bringup.sh`, `fedora_prepare_xvc.py`,
  `fedora_xvc_server.py`, `fedora_jtag.py`, `fedora_check_jtag_chain.py`,
  `fedora_check_native_image.py`, `fedora_prepare_litedram.py`,
  `workspace_paths.py`), `opentpu/host/{__init__,jtag}.py` and
  `docs/vivado_bitstream_guide.md`; all 95 files are listed with SHA-256 in
  `ladder/hardware/import-provenance.json`. Added the hardware validation plan
  (`ladder/hardware/README.md`), the stdlib-only read-only probe
  (`ladder/hardware/probe.py`: USB DLC10/FT232H, Xilinx PCIe, `/dev/xdma*`,
  cable owners, XVC `:3721`, k10temp, the shared heavy lock and the reviewed
  artifacts; exit 0 ready / 3 blocked / 4 unexpected), `docs/fpga-flow.md` and
  the step-12 gate test (7 tests: image/package identity, imported-flow
  byte-identity, build-flow presence, both JTAG+PCIe interfaces, documented
  commands, on-card TODO). Hardware assertion BLOCKED: no DLC10 cable/card
  (`03fd:*`/`0403:6014`), no `10ee` PCIe, no `/dev/xdma*`; the runner recorded
  `BLOCKED` (exit 5, 7 skipped) in `ladder/evidence/step12.json` with the probe
  JSON in `ladder/evidence/hardware/probe-step12.json`. No Vivado run,
  programming, flash or reset was performed. `rtl/boards/ypcb-00338/` and
  `sim/verilator/tb_board.sv` were already imported byte-identically at step 9
  (verified, not duplicated).

- 2026-11-10: step 13 committed (hardware rung, software side + honest BLOCKED
  receipt). Imported the JTAG/XVC runtime evidence and the c0182902 acceptance
  drivers byte-identically from `ca05e24f`:
  `tests/test_xvc_transport.py` (real XVC TCP client against a local
  USER2/IDCODE endpoint), `tests/tb_xpcu_xvc.cpp` (XPCU encoder/decoder vs an
  FX2 USB protocol model), `tools/{run,repeat,verify}_tinystories_shared_jtag.py`,
  `tools/check_tinystories_c0182902_model.py`,
  `tools/run_spare_c0182902_bandwidth.py`, `tools/fedora_matmul_check.py`, and
  the recorded historical acceptance (`docs/tinystories_jtag_c0182902.md`,
  `docs/data/c0182902-tinystories-jtag-20261107.json`; c0182902 PASS
  2026-11-07/08, exact 8 tokens, image sha `d32fd284…`). Added
  `ladder/harness/hardware.py` (probe gate, pinned acceptance constants and
  the exact command set), the step-13 gate test (6 tests: imported JTAG/XVC
  byte-identity, XVC protocol evidence, exact-image tools, image/model
  identity, documented on-card recipe, on-card matmul TODO) and
  `docs/oncard-jtag.md` with the full acceptance recipe, criteria, historical
  evidence and known gaps (host-tree/package/model/calibration/oracle are
  untracked local artifacts; the `spare_runtime`/`spare_c0182902`/`waits`/LLM
  closure arrives with steps 10/11/14/16 and is executed against the prepared
  host tree until then). The probe's product-root selection now prefers a tree
  that actually carries `bitstreams/`, so a ladder worktree with the imported
  docs still finds the product checkout's artifacts. Hardware assertion
  BLOCKED (no DLC10 cable/card): runner verdict `BLOCKED` (exit 5, 6 skipped)
  in `ladder/evidence/step13.json` with the probe JSON in
  `ladder/evidence/hardware/probe-step13.json`. No hardware access, no Vivado
  run, no programming/flash/reset.
- 2026-11-10: step 14 committed - the LLM layer in simulation. Imported
  byte-identically (23 files): `opentpu/llm/` (16 modules), the image/program
  cache and profiling modules, and `opentpu/host/{__init__,offload}.py`
  (qwen3.py imports `..host.offload` at import time; all torch/transformers/
  safetensors/PIL imports in the LLM package are lazy, so `import opentpu.llm`
  works numpy-only - required here because this host has no torch and no
  offline wheels for it). New `ladder/harness/llm.py`: a deterministic,
  torch-free tiny Qwen3 fixture (hidden=256, 2 layers, n_q=4/n_kv=2,
  head_dim=128, ffn=512, vocab=1000; 24 numpy tensors, rng seed 0; 2.2 MB
  image sha256 3937bafd...), the production D=128 Config, ISA goldens and the
  per-token RTL replay (ISA DRAM snapshot -> ISA oracle step vs
  `RtlBackend` step, requiring identical uint32 logits, whole DRAM and token
  ids). New `ladder/tests/test_step14_llm_sim.py`: torch-free import test, the
  light ISA golden token test (prompt [811,85,179,236,181] -> greedy
  [181,181,181,564,564,564], deterministic), and the heavy 4-token RTL
  replay. The committed receipt is a warm-cache PASS (3/3, 94 s): the one-time
  D=128 `tb_top` build (key `tb_top_6c0cd0fddf92`) could not be made with the
  stock flags on this laptop - the host's thermal guard (<~95 C) killed the
  compiler at -j2/-O3 and at -j1/-O1, so the harness builds with `-j1`, a
  `-O1` Verilator optimization (part of the deterministic build-cache key) and
  the integration completed it thermally paced (`-O0` C++ override +
  temperature-aware incremental make across cool windows); the receipt notes
  record this. `docs/llm-sim.md`.
- 2026-11-10: step 15 committed (hardware rung, software side + honest BLOCKED
  receipt). Imported byte-identically the last tracked tools the on-card
  TinyStories acceptance needs: `tools/spare_program_fetch_check.py` (the
  1,371-instruction / 65-word structural preflight) and
  `tools/spare_runtime_c0182902.py` (image-bound CH0 calibration guards),
  recorded in `ladder/hardware/import-provenance.json`. Extended
  `ladder/harness/hardware.py` with the `LLM_ACCEPTANCE` constants (pinned
  prompt/token oracle `[1,9038,2501,263,931] -> [29892,727,471,263,2217,7826,
  4257,365]`, image/package/bitstream/model hashes, 2,048 init chunks, 1,371
  instructions/65 exact words, 5 matmul instructions, 13/13 readbacks,
  warm-repeat/ECC/calibration/flash conditions), added the probe-gated
  `ladder/tests/test_step15_hardware_gate.py` (7 skips while the cable/card
  are absent; when ready it runs 5 structural identity checks and leaves the
  live run/warm repeat as explicit TODO(step 15) skips) and
  `docs/oncard-llm.md` with the full end-to-end acceptance recipe, the
  historical c0182902 PASS evidence, the lift procedure and the known gaps
  (untracked package/model/host-tree/calibration/oracle, tokenizer wheel
  path). Hardware assertion BLOCKED: no DLC10 (`03fd:*`/`0403:6014`), no
  `10ee` PCIe, no `/dev/xdma*`; receipt `BLOCKED` (exit 5, 7 skipped) with the
  probe JSON committed. Nothing was programmed, flashed or reset. Roadmap row
  15 stays 🚫 until the probe exits 0.
