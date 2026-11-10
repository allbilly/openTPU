# The toy machine: authoritative interface and arithmetic description

This document describes the **step-0/1/2 toy machine** — the imported tiny-tpu
2×2 Q8.8 TPU — as it actually exists in this tree. It is the authoritative
reference for everything the ladder's first rungs assert.

> **The upstream instruction-set tables are documentation, not a hardware ISA.**
> `README.md` (as imported from tiny-tpu) contains a 94-bit instruction table,
> and `docs/verification_plan.md` a 130-bit table; `src/control_unit.sv` decodes
> a 130-bit word, and the demo RTL copies elsewhere decode an 88-bit word.
> **None of these is a hardware ISA:** `src/tpu.sv` never instantiates
> `control_unit.sv`, has no instruction memory, no program counter and no
> decoder, and the cocotb benches drive the `tpu` ports cycle by cycle. The
> three widths are stale/divergent upstream reference material only. The ladder
> introduces its real ISA at step 3 (`docs/isa.md`, `opentpu/isa.py`).

## 1. Top-level ports (`src/tpu.sv`, `SYSTOLIC_ARRAY_WIDTH = 2`)

| port | dir | width | meaning |
| --- | --- | --- | --- |
| `clk`, `rst` | in | 1 | single clock domain, synchronous reset |
| `ub_wr_host_data_in[0:1]` | in | 2×16 | host write data, one word per lane |
| `ub_wr_host_valid_in[0:1]` | in | 2×1 | host write strobes |
| `ub_rd_start_in` | in | 1 | pulse a unified-buffer read command |
| `ub_rd_transpose` | in | 1 | transpose the read (weights) |
| `ub_ptr_select` | in | 9 | which UB read channel to start (see §3) |
| `ub_rd_addr_in` | in | 16 | UB start address |
| `ub_rd_row_size` | in | 16 | rows to stream |
| `ub_rd_col_size` | in | 16 | columns to stream |
| `learning_rate_in` | in | 16 | Q8.8 SGD learning rate |
| `vpu_data_pathway` | in | 4 | VPU routing, see §5 |
| `sys_switch_in` | in | 1 | copy PE shadow weights to active weights |
| `vpu_leak_factor_in` | in | 16 | Q8.8 leaky-ReLU slope |
| `inv_batch_size_times_two_in` | in | 16 | Q8.8 2/N for the MSE gradient |

There is **no** memory-mapped host interface, no `done`/`busy`/`error` output,
no interrupt and no instruction bus: a "program" is the cycle-by-cycle port
stimulus applied by a testbench. The only observability is the unified-buffer
contents and internal signals (the benches use both).

## 2. Datapath structure

`tpu.sv` wires exactly three child blocks:

* `systolic` — 2×2 MAC array of `pe` (Q8.8 `fxp_mul` + `fxp_add`, shadow weight
  register switched by `sys_switch_in`, per-column enable from the weight-read
  command's column size);
* `unified_buffer` — 128×16-bit memory with a host write port, a VPU write
  port, seven read channels and two `gradient_descent` instances (one per
  feature column);
* `vpu` — `bias_parent` → `leaky_relu_parent` → `loss_parent` →
  `leaky_relu_derivative_parent`, two lanes (one per feature column), each
  child one clock of pipeline latency, outputs registered in `vpu.sv`.

All datapath signals are signed 16-bit Q8.8 words; there is no backpressure
(other than `valid`).

## 3. Unified buffer layout and pointer map

`ub_memory[0:127]`, 16-bit words, row-major matrices. Host writes append at a
single linear write pointer (`wr_ptr`, reset 0); the write loop runs from lane 1
down to lane 0, so for a 2-column matrix **column 1 is stored at the lower
address**. The imported `test/test_tpu.py` host-load order is:

| addr | contents |
| --- | --- |
| 0–7 | `X` (4×2, row-major) |
| 8–11 | `Y` (4) |
| 12–15 | `W1` (2×2, row-major) |
| 16–17 | `B1` (2) |
| 18–19 | `W2` (2) |
| 20 | `B2` (1) |
| 21–28 | `H1` (VPU forward-pass output, written by the RTL) |
| 29–32 | `dL/dZ2` (transition output) |
| 33–40 | `dL/dZ1` (backward-pass output) |
| 41–52 | weight-gradient tiles (RTL scratch) |

Read commands are started with `ub_rd_start_in` and select a channel with
`ub_ptr_select`:

| `ub_ptr_select` | channel | consumers |
| --- | --- | --- |
| 0 | activation/input read (`X`, `H1`, `dL/dZ`) | west side of systolic array |
| 1 | weight read | top of systolic array; also sets PE column enable (`col_size`) |
| 2 | bias read | bias modules in the VPU |
| 3 | `Y` read | loss modules |
| 4 | `H` read | leaky-ReLU-derivative modules |
| 5 | bias-gradient read | bias `gradient_descent` instances |
| 6 | weight-gradient read | weight `gradient_descent` instances |

Streaming details that callers must respect:

* A read starts streaming two cycles after the command edge; lane 1 data trails
  lane 0 by one cycle (this is the systolic stagger).
* Weight reads with `ub_rd_transpose = 1` load starting at
  `addr + col_size − 1` and skip `col_size + 1`; the upstream test's comment
  "set the start address one address above…" refers to that rotation.
* A channel stops after `row_size + col_size` stream cycles (not
  `row_size × col_size`): the caller tiles explicitly.
* `ub_ptr_select == 1` also drives the systolic array's column-enable sideband
  (`1 → column 0 only`, `2 → both columns`, otherwise none).

## 4. Q8.8 fixed-point semantics (`src/fixedpoint.sv` defaults)

Every `fxp_*` instance in the toy RTL uses the library defaults `WII = WIF = 8`
(and `ROUND = 1`), i.e. **signed 16-bit Q8.8**: 1 sign bit, 7 integer bits, 8
fraction bits. Resolution is `1/256 = 0.00390625`; representable range is
`[-128, +127.99609375]`. Python conversion: `word = round(value * 256) & 0xffff`.

Arithmetic (all results are 16-bit, signed, saturating — never wrapping):

* `fxp_mul(a, b)` — 32-bit signed product `a*b` (Q16.16), arithmetic shift right
  by 8, then **`+1` when the dropped bit 7 is set** (round-half-up on the floored
  value; exact `fxp_zoom` rule), then saturate to `[-32768, 32767]`. E.g.
  `fxp_mul(1, 128) = 1`, `fxp_mul(100·256, 2·256) = 32767`.
* `fxp_add(a, b)` — saturating 16-bit addition; `fxp_addsub(..., sub=1)` —
  saturating subtraction. `OVERFLOW` is asserted when saturation occurs and is
  sticky where it is exported.
* `leaky_relu_child`: `x >= 0 ? x : fxp_mul(x, leak_factor)`; the derivative
  child uses `H >= 0 ? d : fxp_mul(d, leak_factor)`.
* `loss_child`: `fxp_mul(fxp_addsub(H, Y, sub=1), inv_batch_size_times_two)`.

`ladder/bench/toy_golden.py` is an independent Python implementation of exactly
these rules; `ladder/tests/test_step02_scoreboard.py` unit-tests it against
the saturation/rounding corners listed above.

## 5. VPU pathway encoding

`vpu_data_pathway[3:0]` enables the four elementwise stages in order; its value
is registered at the VPU output, so every stage adds one clock of latency:

| bits | stage | 1 = stage active |
| --- | --- | --- |
| [3] | bias addition | `z = sys_data + bias` |
| [2] | leaky ReLU | `h = leaky(z)` |
| [1] | MSE loss gradient | `g = (2/N)·(h − Y)`, caches `h` as `last_H` |
| [0] | leaky-ReLU derivative | `g' = H>=0 ? g : leak·g` |

Common pathways: `4'b1100` forward pass (sys → bias → ReLU → UB),
`4'b1111` transition (sys → bias → ReLU → loss → derivative → UB),
`4'b0001` backward pass (sys → derivative → UB), `4'b0000` pass-through.

## 6. What the step-2 bench checks (and the one upstream defect it fixes)

`ladder/bench/` adds `dump_tpu_scores.sv` (a `tpu_scores` wrapper that
instantiates `tpu.sv` and exposes the unified buffer plus every stage boundary)
and `test_tpu_scores.py` (the cocotb scoreboard). Run it with:

```sh
source .venv/bin/activate
iverilog -o sim_build/tpu_scores.vvp -s tpu_scores -s dump -g2012 src/*.sv \
         ladder/bench/dump_tpu_scores.sv
PYTHONPATH=ladder/bench MODULE=test_tpu_scores COCOTB_TEST_MODULES=test_tpu_scores \
  COCOTB_RESOLVE_X=ZEROS LADDER_SCOREBOARD_OUT=/tmp/step02.json \
  vvp -M "$(cocotb-config --lib-dir)" -m "$(cocotb-config --lib-name vpi icarus)" \
      sim_build/tpu_scores.vvp
```

or, as the ladder runs it, `python3 ladder/run.py step 2` (which also runs the
mutation checks). The bench asserts, with independent Q8.8 golden values and
the raw RTL's own stage inputs:

1. **Host load** — UB words 0–11 (`X`, `Y`) equal the Q8.8 golden layout.
2. **Layer-1 forward** — UB 21–28 equals the golden bias+leaky-ReLU result of
   all four XOR inputs `00/01/10/11`:
   `[-63, 48, -137, 156, -25, 71, -99, 179]`.
3. **bias**, **leaky-ReLU**, **loss gradient** `(2/N)(H−Y)` and
   **leaky-ReLU-derivative** arithmetic, checked cycle by cycle against the
   Python Q8.8 operators.
4. **SGD** — every `gradient_descent` update (`old − lr·grad`, including the
   bias-accumulation mode) and the resulting UB parameter words for both weight
   tiles and both bias vectors.

Each of the five modules the imported baseline left smoke-only (`pe`,
`systolic`, `vpu`, `unified_buffer`, `gradient_descent`) is covered: the
step-2 tests mutate each one and require the scoreboard to fail.

**Upstream defect fixed by the bench:** the imported `test/test_tpu.py` pulses
`sys_switch_in` on the same cycle as the second weight-accept, one cycle earlier
than the standalone `test/test_systolic.py` usage. The PE then copies the first
streamed weight into both array rows, so the top-level bench silently computes
`(x0+x1)·w` instead of a dot product (observed `H1 = [s0,s1,s1,2·s1]`). The
step-2 bench delays the switch until both weight words are accepted and
re-aligns the activation/bias streams; with that fix the RTL reproduces the
golden layer-1 result above. The backward/SGD phases keep the upstream stimulus
order and are checked at the datapath level (every stage operation, every SGD
update and the final parameter words); a full ideal-backprop golden comparison
needs the same timing correction applied to those phases and is deferred with
the rest of the sequence-level work to a later rung.

## 7. Known limitations of the toy machine

* No instruction fetch/decode in hardware (see the note at the top).
* Fixed 2×2 array, 128-word single-cycle UB, Q8.8 only; no tiling engine, no
  on-chip memory hierarchy, no host transport, no compiler, no status/CSR.
* One clock per streamed word per channel and hand-written systolic stagger:
  throughput is a teaching-toy rate, not an accelerator rate.
* `fixedpoint.sv` is an embedded third-party-style library with no license text;
  see `ladder/NOTICE.md` for the provenance and licensing caveat.
