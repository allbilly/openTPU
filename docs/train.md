# Training on openTPU

openTPU's datapath is built for inference: weights stream once per token, activations are
quantized to int8 in `QACT`, and the `MM` instruction multiplies a stationary int8 tile by a
block-scaled weight row and writes one exact integer per output. None of that changes for
training. What training needs from the machine is a second weight stream — the backward matmul
through the *same* streamed weight, transposed — and a rank-1 accumulation of the weight
gradient, and both are instructions that exist: `MM` with the transposed scale row reads a
frozen quantized weight, and one `VOP OUTER` pass per token accumulates a dW tile in fp32.
The optimizer, the fp32 master copy and the re-quantization of the updated weights stay on the
host, which is where the arithmetic that has no instruction lives (and where a checkpoint has
to be written anyway). This document is the contract for that split: the gradient formulas,
which instruction each one becomes, how the buffers are laid out, what the backward pass does
about the weight quantizer, and what a working first target is. It is written from
`docs/isa.md`'s semantics and from measurements on the ISA simulator; every number is labelled
with how it was obtained.

## 1. Scope and non-goals

Training support means fine-tuning on the existing ISA and RTL: the machine runs the forward
pass and the backward pass of a transformer block (matmuls, RMSNorm, SiLU/SwiGLU, softmax
cross-entropy) and the weight gradients come out of the device in fp32. The host owns the
optimizer state, the fp32 master weights, the loss reduction, the re-quantization of the updated
weights into the image and the checkpoint. There are no new opcodes, no new RTL unit, no new
formats: every instruction named here is in `docs/isa.md`.

The non-goals are as important. This is not a general autograd framework: the backward of each
kernel is written out by hand from the formulas in section 3, as llm.c and the tiny C++ GPT
write it, and there is no graph, no tape, no operator registry. It is not pretraining: section 5
gives the traffic arithmetic, and the OUTER-based dW accumulation costs VPU cycles proportional
to tokens times weights, two to three orders of magnitude away from what pretraining needs. It is
not full-model fine-tuning on day one: section 8 stages the work from one linear layer to a block
to a tiny model, and section 10 says which limits stand.

The implementation the sections describe is in `opentpu/train/`: `kernels.py` (the device's
passes), `params.py` (the master copies, the optimizer, the losses), `loop.py` (a step's two
programs and the DRAM layout), `lora.py` (the frozen-base adapter layer, section 8's rung 4),
`ref.py` (the float64 reference) and `cli.py` (`otpu-train`).

## 2. Training on an inference datapath

A datapath that was built to stream weights forward needs two things to train, and both are
instructions that already exist. The first is the *same* weight read backwards: an MM whose
reduction runs over the layer's output width rather than its input width, which is the forward's
MM with the weight's transpose as the streamed operand. The second is the weight gradient, which
is an outer product accumulated over the batch: `dW = sum_t dy[t] x[t]^T`, and on this machine
that is one `VOP OUTER` pass a token, in fp32, over a tile that stays in TMEM.

Everything else in a step is either a pass the inference kernels already run (`RMSNorm` is `RSSQ`
and `RSQRT`; `SiLU` is `EXP2` and `RECIP`; the softmax is `RMAX`, `EXP2SUB` and `RSUM`) or work
that has no instruction and does not want one:

| Work | Where | Why |
|:--|:--|:--|
| forward `MM`s | device | the inference kernels' own passes |
| `dX = dy @ W` (`MM` on the transposed weight) | device | one pass over the weights, as the forward's |
| `dW = sum_t dy[t] x[t]^T` (`VOP OUTER`) | device | exact fp32, one instruction a token |
| `RMSNorm` / `SiLU` / `SiLU'` (`RSSQ`, `RSQRT`, `EXP2`, `RECIP`, `MUL`) | device | single VOP passes |
| softmax's max and sum (`RMAX`, `EXP2SUB`, `RSUM`) | device \* | one pass each over the logits |
| the normalized exponentiation and its sum | host | a row group's V columns of `exp`/`log`: a few KB |
| AdamW on the fp32 master weights | host | `O(parameters)`, no instruction, and a checkpoint has to be written anyway |
| the updated weights re-quantized into the image | host | the MM streams quantized rows; the master copy is fp32 |
| checkpointing | host | it is the master copy that is saved, not the image |

\* The device *can* compute softmax: the `VOP` has `RMAX`, `EXP2SUB` and `RSUM`, and
`docs/prefill.md` uses exactly those three in the attention kernels. v1 leaves the loss on the
host because it is the one place where the reduction is over a shape (`[B, V]`) the layer
kernels do not otherwise use, and because the backward pass needs the gradient of `V` columns a
row, which the host has already produced. The instruction-level route is the obvious next step
(section 8), not a different design.

The split is the "hybrid" that the ANE-based projects converged on, and here it is also the
cheap one: the host's work is `O(parameters)` a step and the device's is `O(parameters x batch)`,
which is what makes a step worth putting on the device at all.

**The problem the split does not solve.** A backward matmul through a frozen quantized weight is
a dequantization on the critical path, and doing it naively means an fp32 copy of the weight:
exactly the memory the quantization exists to save. `llama.cpp`'s quantized-backward discussion
(issue 30084, October 2026) puts the requirement plainly: dequantize *blockwise*, in the same
pass that multiplies, never materializing the whole matrix. On openTPU this is not a choice --
`MM` streams the quantized rows and dequantizes them in its epilogue by construction
(`docs/isa.md`, "MM": `w m 2^-dw Sw`), and there is no fp32 copy of any weight in the image. A
training step therefore costs the same bytes per weight as the inference step does; the extra
traffic is the transposed operand, which is a second set of quantized rows (section 5).

## 3. The gradient math, instruction by instruction

Write the block as `kernels/mlp.py` writes it, with a head on the end. For a [R, H] batch tile:

    r    = rsqrt(mean(x^2, axis=-1) + eps)          RSSQ, MUL, RSQRT
    xh   = x * r                                    MUL
    xn   = xh * gamma                               MUL
    g    = xn @ w_gate^T     u = xn @ w_up^T        MM, MM
    sg   = sigmoid(g)         a = (g * sg) * u      EXP2, RECIP, MUL, MUL
    y    = a @ w_down^T + x                         MM, ADD
    logits = y @ head^T                             MM

**Linear.** `y = x @ W^T` with `W` a streamed `[N, K]` operand. `dX = dy @ W` is the forward's MM
with `W^T` (`[K, N]`) streamed instead: the reduction becomes `N`, and `N` has to be a multiple
of `D` because the MXU streams whole `D`-byte chunks. `dW = dy^T @ x` does not use an MM at all:
`VOP OUTER` computes `acc = add(mul(acc, Dv(c)), mul(B(r), Cv(c)))` in place, so with `B` per row
and `Cv` a column vector one pass folds a token's contribution into an `[N, K]` tile that stays
in TMEM. It is exact fp32: two rounded products and a rounded add

**RMSNorm.** The forward is the norm's own. The backward is the one formula in this document that
a from-scratch derivation gets wrong, so it is stated with the two traps. With `dh = dy * gamma`
(`dy` the gradient with respect to `xn`):

    dX      = r * (dh - mean(dh * xh) * xh)
    dgamma  = sum over ROWS of (dh * xh)

The projection is along `xh`, not along `xn`, and `gamma` must be applied *before* the projection.
A projection along `xn`, or a `gamma` applied after, is 5-10% off against central differences
(measured on `opentpu/train/ref.py`); the two forms agree only when `gamma` is all ones, which is
why an unweighted norm's backward "works" and a weighted one's does not. `dgamma` sums over rows:
the `VOP` reductions run along a tile's *last* axis, so a sum over `R` rows is not one
instruction. It is the same rank-1 pass the weight gradients use, `MUL` plus `ADD` a row, and it
is what `out[t] += dh[t] * xh[t]` lowers to.

**SiLU and SwiGLU.** `silu'(g) = sg * (1 + g * (1 - sg))`, so `dG = da * u * silu'(g)` and
`dU = da * (g * sg)` (`da` being the gradient of `a = silu(g) * u`). Four VOP passes and the
sigmoid the forward already computed (`sg`), which the loop keeps rather than recomputing.

**Softmax cross entropy.** `loss = mean_b(logsumexp(z_b) - z_b[target_b])` and
`dz = (softmax(z) - onehot(target)) / B`. The `1/B` is in the gradient rather than in the loss,
so a step's accumulated `dW` is already the mean's gradient and the optimizer needs no extra
scale. On the host this is one `np.exp` and one `np.log` a row; on the device it is `RMAX`,
`EXP2SUB` and `RSUM` for the normalizer (section 8's next step).

**Tied head.** `dh = dy @ head` and `d_head = dz^T @ y`. The first is an MM against the head's
transpose, like any `dX`. The second is not an MM on this machine, and it is worth saying why:
as `dz^T @ y` it would need `dz`'s transpose as a stationary operand (a transpose the device
cannot do) or the batch padded to a whole `D`-block (a batch of 1 would cost a `D`-wide tile of
zeros). As `B` OUTER passes -- `d_head += dz[b][:, None] * y[b][None, :]` -- it needs neither,
and it is exact fp32. `B` instructions for a `[V, H]` matrix, which is why the batch is small.

**AdamW.** On the host, on the fp32 master copies: `w *= 1 - lr * wd`, then
`w -= lr * mhat / (sqrt(vhat) + eps)` with `mhat = m / (1 - beta1^t)` and the like for `v`.
Elementwise and `O(parameters)`; `tests/test_train_ref.py` compares it against
`torch.optim.AdamW` over several steps.

## 4. Quantization in the backward pass

The forward's operands are quantized: the stationary tile by `QACT` to int8 with a per-row fp32
scale and per-sub-block power-of-two offsets, and the streamed weight by the image's MX format
(`docs/isa.md`, "Weight formats"; `docs/quant.md` has what each costs). None of them is
differentiable in any useful sense: the quantization is a rounding, so its derivative is zero
almost everywhere and undefined at the boundaries. A backward pass therefore takes the
**straight-through estimator**: the gradient is that of the float computation, and the quantizer
is treated as the identity. This is stated as a fact of the datapath, not an assumption about
what is best, because it is what the machine makes possible: the epilogue's dequantization
(`i2f(acc) * Sw[n] * (Sa * 2^-W)`) is linear in the accumulated integer, and the gradient flows
back through the fp32 factors that surround it.

Two consequences are real and are not hidden here.

- **A row's scale is one number.** A weight row's `Sw` is shared by the whole row, so a gradient
  that would move one element of the row moves the scale too; the update the optimizer applies
  is in the master copy's fp32 elements, and the re-quantization at the next step decides a new
  `Sw` from the whole row again. A row whose elements all move the same way keeps its
  quantization; a row whose elements move apart loses resolution, and the loss is the format's
  (`docs/quant.md`). Nothing in the optimizer sees this.
- **The drop window clips.** An MM drops a group whose two offsets add up to more than `W`
  (`sh > W`: `docs/isa.md`, "MM"), which is at most 7e-5 of the groups by the format scans
  (`docs/mx_mxu.md` 3.3). A dropped group contributes nothing to the forward, so with the
  straight-through estimate its gradient is the gradient of the value the MM did not compute --
  small, and the scans' measurement is why it is acceptable at v1's tolerances.
- **The 4-bit formats have no device-side quantizer at all.** `QST` writes `q8` bytes only
  (`isasim._qst` -> `fp32.quantize_mx`), so a matrix the *device* computes (a `dX`, a `dA`) can be
  quantized back into a streamed operand in int8, or left at unit scale in fp32, and not in
  `int4`/`fp4`/`nvfp4`. Weights the host quantizes can be any of the four formats; activations
  and transposed gradients the device produces are int8 or unit-scale. That is why the training
  path's streamed weights are int8 by default, and why 4-bit training is a documented option for
  the weights only.

The error the estimate costs is measured, not assumed (section 7): with the device's int8
operands, every gradient of the block lands within 0.3% to 2.8% of the float64 reference across
five seeds, which is the int8 noise the inference kernels already live with
(`tests/test_kernels.py` allows 2-3% a matmul).

## 5. Data layout and the memory budget of a step

One DRAM array holds a step's whole state, and the two programs address it through descriptors
built from a `Layout`'s offsets (`opentpu/train/loop.py`):

    byte-addressed       the streamed matrices' element rows and scale rows: the four the forward
                         streams (w_gate, w_up, w_down, head) and the four transposes the backward
                         streams (w_gate^T, w_up^T, w_down^T, head^T)
    fp32, word-addressed  x, xn, y [B, H]; g, u, a [B, F]; logits and dlogits [B, V]; gamma [H]
    fp32                 the gradients: d_gate, d_up [F, H]; d_down [H, F]; d_head [V, H];
                         d_gamma [H]; dx [B, H]

For the test configuration (`Config(D=32, ACT_BLOCKS=64, ACT_ROWS=64)` and `Shapes(H=F=V=32, B=4)`)
that is 30.8 KiB; for the card's `D=128` with `H=128, F=256, V=128` it is 708 KiB. The weights
dominate, and they are the same bytes the inference image would hold, plus the four transposed
copies (`K x N` rows instead of `N x K`, quantized on their own -- a matrix's transpose is not a
view of its rows, and every matrix's rows get their own `Sw`).

**What fits where.** A step's forward and backward matmuls need one tile in TMEM at a time:
`[B, F]` for the gate and up outputs, `[B, V]` for the logits, and one `[N, K]` tile for each
gradient accumulator. That last one is the size that matters: `[F, H]` is `F * H` words, which
for the card's `H=128, F=256` is 32,768 of TMEM's 65,536 -- half of it for one accumulator, and
a step has three (d_gate, d_up [F, H] and d_down [H, F]), plus the transposed operands' tiles.
So the block's *widths* are bounded by TMEM at `D=128`: a full-width block does not compile on the
card's configuration, and the smallest block that does is not yet measured (this is the honest
state: the shapes the tests run are `D=32`, and the card-size numbers are `shapes.check`'s
refusals, not measurements). Section 10 says what that means for the plan.

The batch is a row group at a time on the card (`ACT_ROWS` is 4 there), so `Shapes.batch` must
be reachable in groups and `Shapes.rows` is at most `ACT_ROWS`; the ISA simulator's
`ACT_ROWS=64` is what lets the tests unroll a batch of 4 or 8 in one program.

**The traffic arithmetic for pretraining**, which is why section 1 calls it a non-goal: the
`dW` accumulation is one `VOP` pass over an `[N, K]` tile *per token*, so its cost is
`tokens x weights` VPU cycles -- where the forward's is `tokens x weights` MXU cycles. A VPU
pass covers a tile over `LANES` words a cycle, and the MXU multiplies `MCOLS x D` a cycle: at the
card's 4 columns and 128 depth the MXU is ~128 multiply-accumulates a cycle where the VPU's
OUTER is 1 element a cycle (8 lanes at 8 words). That is the factor-of-two-orders statement: the
gradient's accumulation, not its arithmetic, is what a pretraining budget cannot afford. For a
fine-tune of a few thousand steps on a block, it is the whole point -- the memory traffic is the
same as inference's and the arithmetic is amortized over the batch.

## 6. The host's job

The host owns five things, and each one is there for a reason.

1. **The fp32 master copies.** The image holds quantized rows; the optimizer needs the values it
   is updating. `Params` (`params.py`) keeps both, and `Params.quantized()` rebuilds the second
   after every update. A checkpoint saves the first (`cli.py`), because that is the state a
   resume needs and the image is a function of it.
2. **AdamW** (`params.AdamW`). Decoupled weight decay, bias-corrected moments, on the master
   copies in place. `O(parameters)` a step.
3. **The loss.** `softmax_xent` on the forward's logits, and its gradient written back into the
   step's DRAM (`Layout.t("dlogits")`). The one thing that must happen *between* the two
   launches.
4. **The re-quantization.** After the update, every streamed matrix's rows and both transposed
   copies, written into the image at their addresses (`loop.write_weights`). This is the step's
   whole ordering constraint: the image must be rewritten before the next forward pass reads it,
   and nothing else may write those bytes meanwhile.
5. **Checkpoints** (`np.savez` of the master copies, gamma, the moments and the step).

The ordering rules are the ones the card's memory model imposes anyway (`docs/host.md`): a
program load and a run happen in that order, the DRAM the Machine holds carries the forward's
activations to the backward pass without the host touching them, and the host writes only the
one buffer the loss produced. `Trainer.step` is that sequence: run the forward program, read the
logits back, write `dlogits`, run the backward program, read the gradients, update, rewrite the
weights.

The device never sees an unquantized operand and the host never sees an integer one, which is
what keeps the split honest: a step's gradients are fp32 because the accumulations are, and the
next step's forward is quantized because the MM's operands are.

## 7. Validation methodology

Four checks, from cheapest to strongest, and all four are in `tests/test_train.py` and
`tests/test_train_ref.py`.

1. **The reference against itself.** `ref.py`'s backward against central differences of its own
   forward, in float64: the finite difference is the only error, so a formula that is wrong fails
   here before any device runs. This is what caught the `gamma`-inside-the-projection bug (the
   naive form is 5-10% off).
2. **The reference against PyTorch.** The same graph in `torch.float64` with `autograd`, every
   gradient compared (`tests/test_train_ref.py`). The point is not that torch is more correct
   than central differences; it is that torch is *independently* derived, so agreement means the
   formulas are right and not that two copies of the same mistake agree.
3. **The device against the reference.** Every gradient of a step, the ISA simulator's DRAM
   against `ref.model_fwd_bwd`, over five seeds on the default shapes (H = F = V = 32, B = 4,
   D = 32). Two columns, because two questions are being asked: the device against the plain
   float64 model, which is the number a reader means by "how far is the device from the math",
   and the device against the reference *re-run on the quantized weights the device streamed*
   (`QuantW.dequant()`), which is the number that says whether the backward pass itself is
   right -- a large second column would be a bug in the gradient, not the format.

   | Gradient | vs float64 | vs the weights the device streamed |
   |:--|--:|--:|
   | d_head (the tied head) | 0.9-1.7% | 0.7-0.9% |
   | d_down | 0.9-1.3% | 0.8-1.3% |
   | d_gate | 0.9-2.1% | 0.9-1.6% |
   | d_up | 0.3-2.0% | 0.4-2.0% |
   | dgamma (the norm's gain) | 0.3-2.8% | 0.4-2.5% |
   | dX | 0.7-2.1% | 0.9-2.6% |

   (The max-absolute-error metric a test uses is the loose one: with nothing but int8 arithmetic
   a single element can be off by two quantization steps and still leave the matrix's direction
   alone. The bounds the tests assert are 2% for the head's and `w_down`'s gradients, 3% for
   `w_gate`/`w_up`/`dx` and 7% for `dgamma`, matching the int8 noise `tests/test_kernels.py`
   allows a forward matmul.)

4. **Convergence.** A step that produces correct gradients still might not descend: the
   optimizer's scale, the quantization's dead zones and the re-quantization's history all affect
   whether repeated steps reduce the loss. So the gate runs a real descent. Measured: 25 steps of
   AdamW at lr 0.05 on a fixed batch of 4, cross entropy from 4.08 to 0.000 (the synthetic task
   has a reachable optimum, which is what makes "0.000" the right answer rather than "it fell
   4.08 to 1.2"). `otpu-train` on `tools/data/austen_pp_ch1.txt` (a byte-level next-byte model):
   5.10 to 0.0003 in 30 steps.

**Training versus deploying.** A repository can train on a GPU and export to an accelerator and
honestly call that "NPU training"; nothing in the device has executed a backward pass. The
distinction this document holds itself to is that the checklist above reads the *device's* DRAM
for the gradients: if the ISA simulator's `d_gate` buffer is right, an MM ran here. A run on the
card is the same programs with the same tests (`tools/...`); nothing about the numbers is
inferred from a host-side model.

## 8. The first working target, and the staged plan

What exists today, and the gate: three trained things, each gated by the same four checks (a
float64 reference against central differences, the reference against PyTorch, the device
against the reference, and a real descent).

- **a block** (`loop.py`): a `RMSNorm`, a `SwiGLU` MLP, a residual and a tied head, all
  parameters trained. `D = 32`, `H = F = V = 32`, batch 4; a 25-step descent takes the
  cross-entropy from 4.0821 to zero.
- **LoRA and QLoRA** (`lora.py`): a frozen base with two trainable adapters, in int8 or with the
  base in a 4-bit format.
- **a whole transformer layer** (`layers.py`): attention, an MLP, and *every* parameter --
  nine trainable groups. `D = 32`, `d = 32`, `F = 64`, `T = 32`; AdamW at lr 0.02 takes the
  cross-entropy from 3.8151 to 0.0001 in 25 steps, and every one of the ten gradients is within
  1.0% to 2.8% of the float64 reference (section 7's table).
- **a stack of layers** (`stack.py`): the layer above repeated and chained -- each layer's `dX`
  feeds the one below it -- plus an LM head over a vocabulary. It is a whole model, small enough
  for the simulator: one DRAM image holds every layer (140 KiB a layer at the test shapes, 439
  KiB for three), a step is n forward launches plus n + 1 backward launches with `Machine.load`
  between them, and every matrix in every layer trains. `D = 32`, two layers, `T = 32`; AdamW at
  lr 0.02 takes the cross-entropy from 4.0844 to 0.0000 in 40 steps, and every gradient of the
  whole graph is within 1.9% to 3.0% of `torch.autograd` in float64 run on the same quantized
  weights (`tests/test_train_stack.py`). Three layers reach 0.0000 from 4.6594.

**Full training** is `layers.py`, and it is what separates a toy block from a fine-tune: the
attention's backward pass is the part that has no analogue in an inference datapath's
arithmetic. It is written out by hand, as llm.c writes GPT-2's:

    dh1    = d(norm2) + dy                        the residual's two paths
    d(o)   = dh1 @ Wo                             dWo = dh1^T o     (not d(o)^T o -- see 9)
    dV     = P^T d(o)                             dP  = d(o) v^T
    dS     = P * (dP - rowsum(P * dP))             the softmax's backward: MUL, RSUM, SUB
    dQ     = dS k^T * scale                       dK  = dS^T q^T * scale
    dxn1   = dQ @ Wq + dK @ Wk + dV @ Wv

The three pieces that cost the work, and each is an ISA primitive:

- **the transposes.** `P^T` and `dS^T` have no instruction (`docs/isa.md`'s VOP has none); they
  are one VOP pass a row via a flat 1-D tile and `Tile.column()`, exact fp32 (`transpose_tile`).
  `v^T`, `dO^T`, `q^T` and `k^T` are transposed the same way and then **`QST`'d into DRAM**, so
  the MM streams them: the device quantizes and transposes its own tiles, and no host round trip
  is on the path. (A *weight's* transpose is a different matrix and would be wrong here --
  section 9's trap.)
- **the score matrix.** `S = q k^T` is `dot(q, k)` -- the MM's row-wise dot product already is
  that contraction, and `k` streams from its own QST region.
- **the softmax's backward.** `dS = P * (dP - rowsum(P*dP))`: one `MUL`, one `RSUM`, one `SUB`,
  one `MUL`, the same three instructions `docs/prefill.md`'s attention uses forward.

Cost: 381 instructions a forward pass and 1,213 a backward pass at the default shapes, 140 KiB
of DRAM. Measured on the ISA simulator.

**QLoRA** is `--lora` with the frozen base in a 4-bit format (`base_fmt`): the base streams at
4.25-4.5 bits a weight instead of int8's 8.25 (`docs/quant.md`), the adapters stay int8. The
two are separate streamed operands over separate DRAM regions, so the MM reads each at its own
stride; the adapters stay int8 because `QST` writes int8 only (section 4), so a gradient the
device produces can only be streamed back in int8. Measured at `r = 8`, `K = N = 64`, batch 4,
each format with its own fresh adapter: forward 0.5-0.8%, dA 0.6-1.0%, the base's own quantized
error 0.40-0.55%, the base's fp32 copy unchanged over a 25-step descent, and the loss falls
(4.14-4.48 to zero). `otpu-train --qlora RANK --base-fmt nvfp4|fp4|int4` runs it.

The staged plan beyond what exists:

1. **The head and the loss on the device** (rung 3, not started). Replace the host's
   `softmax_xent` with `RMAX`, `EXP2SUB`, `RSUM` and an `ARGMAX`-indexed gather for `d_head`'s
   scatter. Removes the one buffer the host writes between the launches. The `VOP` already has
   the three instructions; the work is the vocab-row reduction and the scatter.
2. **A multi-layer stack** (done: `stack.py`). A layer's `dX` feeds the one below it, which is
   the same backward pass with `dX` in place of the loss's gradient, so the chaining adds no
   instruction -- only the DRAM to keep every layer's saved activations (140 KiB a layer at the
   test shapes, one image for the whole stack, 439 KiB for three). The head is a trainable
   `[V, d]` matrix whose gradient is the same OUTER accumulation every other matrix uses. A
   step is `n` forward launches and `n + 1` backward launches; the stack cannot be one program,
   because each layer's backward reads DRAM a previous launch wrote.
3. **A real checkpoint's block** (not started). The block at a model's `H` and `F` with the
   card's `D = 128`: the TMEM bound of section 5 is the blocker, and the fix is a row-grouped
   `dW` (accumulate `[N, K]` in DRAM through `ST`/`LD` between groups), not a bigger TMEM.
4. **The KV cache's backward** (not started). `kv_append` exists for inference; a fine-tune over
   sequences needs the cache's gradient and the sliding window's.
5. **LoRA on a real model.** The inference kernels' own layers (`kernels/attention.py`,
   `kernels/mlp.py`), with the adapters' `dW` in the places `offload.md` and `serve.md` already
   stream weights.

## 9. Non-obvious traps

Four things that cost time in this work, each of them a property of the ISA rather than a bug.

- **A tile's shape is not a matrix's shape.** An MM's output has an odd row stride (`N + 1`) so
  that the streamed row's results land in distinct TMEM banks (`compiler.Builder.dot`), so
  `Tile.reshape` on it refuses: only a contiguous tile reshapes. Copy into a `dense=True` tile
  first (`ol.empty(shape, dense=True)`).
- **A hardware loop cannot index a tile.** `ol.range(n)` yields a loop object, not an integer,
  and the body is traced once, so `x[t, :]` has no loop-dependent form. Load the row from DRAM
  inside the loop (`ol.load(dy[t, :])` on a `Tensor`) -- which is the pattern `loop.py`'s
  unrolled accumulators use. The unrolled form (`for b in range(B)`) is what the batch's
  OUTER accumulations take, and it is why the batch is small.
- **`VOP OUTER` takes 1-D vectors and at most 256 columns.** `dW += dy[b][:, None] * x[b][None, :]`
  is `ol.outer(dy[b, :], x[b, :], acc=dW)`, and its column vectors are held in 256-word buffers
  (`isa.OUTER_MAX_COLS`): a `[N, K]` accumulation with `K > 256` is a compile error, not a slow
  pass -- "outer(acc=...) supports up to 256 columns". Measured: `K = 256` traces, `K = 320`
  refuses. So a block's `F` and `H` must both be at most 256 for the weight gradients to be one
  pass each, and `Shapes.check` says so. The rung-5 fix (a gradient wider than 256 columns) is
  two accumulators and two static stores, which is the same pass twice, not a different
  instruction.
- **A device-computed matrix can be streamed, but only as int8 or unit-scale.** `QST` writes
  `q8` bytes (`fp32.quantize_mx`), so a `QST`-ed region can be rebuilt as a `QTensor` with the
  format's `row_bytes`/`scale_bytes` strides -- and its bytes match
  `quant.quantize_mxu`'s for int8 exactly, scale rows included (verified in code: uint8 vs int8
  comparison is the trap, compare `.view(np.int8)` on both sides). There is no `QST` path for
  `int4`, `fp4` or `nvfp4`; section 4 says what that means.
- **A weight's transpose is not a computed tile's transpose.** This is the bug that cost the
  longest in the full layer. `dK = dS^T q^T` needs `q^T`, the transpose of the *computed* query
  tile -- not `Wq`'s transpose, which is a different matrix (`q = xn1 Wq^T`, so `q^T = Wq xn1^T`,
  and only the first is what the MM must stream). The same distinction for `k^T`, `v^T` and
  `dO^T`: each is the transpose of a tile the forward computed, so each is transposed in TMEM and
  `QST`'d into its own region. Passing the projection matrix's transpose compiles, runs, and is
  wrong by ~100% -- the shapes match and only the values do not.
- **`dW` of a residual projection is `dh^T @ o`, not `d(o)^T @ o`.** For `h = x + o Wo^T` the
  gradient of `o` is `dh @ Wo` and the gradient of `Wo` is `dh^T @ o`: two different expressions
  that both mention `o` and `dh`. Deriving one and using it for the other is a 100% error that
  the torch cross-check caught in one line (`layer_ref`, section 7).
- **A finite difference of an fp32 parameter is the rounding's, not the derivative's.** `1e-6`
  added to an fp32 value near 1 stores as `1.013e-6` (a ~1.3% perturbation), so a central
  difference of a float32 model is off by several percent no matter how right the formula is.
  The reference's FD checks use float64 parameters (`tests/test_train_layers.py`).

## 10. Limits and what is not here

- **Throughput.** A step is a few hundred instructions and runs on the ISA simulator for
  seconds; nothing here has been measured on the card. The OUTER-based `dW` accumulation is
  1 element a VPU lane-cycle against the MXU's ~128 multiply-accumulates a cycle, so a step's
  gradient work is the slow part, and how slow is unmeasured.
- **The card's `D = 128` shapes do not compile yet** (section 5): a block's `[F, H]` accumulators
  are half of TMEM each. The fix is a row-grouped accumulator, and it is section 8 rung 5.
- **No attention backward, no MoE backward, no `KV` cache gradient, no expert-parallel or
  pipeline-parallel training.** The block is the whole model: a residual stream of bytes.
- **No autograd.** Adding a layer means writing its backward by hand (section 3). That is the
  design (section 1), not a stage of it.
- **The loss is off-device** (section 2's table): the `softmax`'s exponentiation and its reduction
  are host work in v1.
- **The vocabulary is a `D`-multiple**, because the head's gradient streams its transpose. A
  byte-level model's 256 tokens need `D` dividing 256, which `D = 128` does and `D = 32` needs
  256 to be padded.
- **No fp32 weights on the device.** Every forward MM streams a quantized matrix; a "fp32
  training" mode would need a different streamed format and there is none (`docs/isa.md`).
- **A step's weight gradients are at most 256 columns wide** (`VOP OUTER`'s column buffers;
  section 9). `H` and `F` are therefore at most 256, which is a block of about 200K parameters
  at its largest and is what the tests' shapes sit under.
- **One batch a step, one step at a time.** No gradient accumulation across micro-batches, no
  data parallelism across slices (`GATHER` exists and a gradient's reduction across slices does
  not), no pipeline parallelism.

