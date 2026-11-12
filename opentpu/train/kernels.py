"""The device side of training: kernels that run on the openTPU ISA, in `ol`.

Every function here traces into instructions the sequencer runs: an MM, a VOP pass, a QACT, a
QST. The training arithmetic is *manual* backward propagation -- closed-form formulas, no graph,
no vjp registry -- which is why these fit in a few hundred lines instead of an autograd engine
(docs/train.md 2).

The split of work (docs/train.md 2, "the hybrid"):

  on the device     the forward MM, dX = dy @ W, the rank-1 OUTER passes that accumulate
                    dW = sum_t dy[t] x[t]^T, and every elementwise pass (RMSNorm's sums and
                    scales, SiLU, the projection terms; the VOP unit)
  on the host       the softmax and cross entropy of a row group (R x V values, a few KB), the
                    AdamW update on the fp32 master weights, the re-quantization of the updated
                    weights into the image, checkpointing. Those are proportional to the number
                    of parameters, not to the batch's work; the device does the rest.

A gradient matrix is never transposed on the device. `dW = dy^T @ x` is one VOP OUTER pass a
token -- `acc += dy[t][:, None] * x[t][None, :]` -- exact fp32 (two rounded products and a
rounded add), and needs no operand the MXU cannot stream. The MM's own operands are quantized
as the ISA requires: a stationary tile through QACT, a streamed weight in the image's MX format.
The quantizer has no derivative in the backward pass: we take a straight-through estimator, so
the gradient is that of the float computation, and the tests measure what that costs
(docs/train.md 4).

Why dgamma needs a per-row pass and not `ol.sum`: the VOP reductions run along a tile's LAST
axis (docs/isa.md, VOP RSUM/RSSQ), and a gain's gradient sums over the *rows*. It is the same
rank-1 OUTER accumulation the weight gradients use, against a [H] accumulator, so it costs one
VOP pass a row and stays exact.

Row shapes: a kernel works on R rows at a time (R <= the MXU's ACT_ROWS: 8 rows on the card),
with a hardware loop over the batch's row groups. A row group's rows are loaded from DRAM inside
the loop, because a loop variable cannot index a Tile: the body is traced once, so only an
*address* may depend on it (`Tensor[t, :]` lowers to a load at R[reg] + stride * t).
"""
from __future__ import annotations

from .. import language as ol
from ..compiler import QTensor

LOG2E = ol.LOG2E


# ------------------------------------------------------------------------------------ linear
def linear_fwd(x, w: QTensor, bias=None):
    """y = x @ w^T for an [R, K] tile x and a [N, K] QTensor w: the MM the inference kernels
    run (`ol.dot`). x is quantized on the fly (QACT); the accumulation is fp32."""
    y = ol.dot(ol.quantize(x), w)
    return y if bias is None else y + bias[None, :]


def linear_dx(dy, w_t: QTensor):
    """dX = dy @ w, for the [R, N] incoming gradient dy and w as a *transposed* streamed operand
    [K, N] (the host prepares w^T's MX rows beside w's, docs/train.md 3.1).

    It is the forward's MM with the transposed matrix as the streamed weight. N -- the forward's
    output width -- is the reduction dim here, so the host pads the rows to whole D-blocks (the
    MXU needs that anyway), and a tile of dy's rows is the stationary operand.
    """
    return ol.dot(ol.quantize(dy), w_t)


def linear_dw(acc, dy, x):
    """dW += dy^T @ x for one row: an in-place VOP OUTER pass over the whole matrix.

    `acc` is an fp32 [N, K] tile (start it at `ol.zeros`), `dy` an [N] row tile and `x` a [K] row
    tile. OUTER takes two 1-D vectors: `acc += dy[:, None] * x[None, :]`. The pass is exact fp32
    and reads no quantized operand, so the gradient keeps fp32 precision even where the forward
    streamed int8 weights (docs/train.md 5).
    """
    return acc.set(ol.outer(dy, x, acc=acc))


def linear_bwd(dy, x, w_t: QTensor, acc):
    """One row group's linear backward: dX, then the group's rows accumulated into `acc`.

    Returns dx [R, K] and `acc` [N, K] (in place), which the caller passes on to the next group
    and finally to the optimizer. The row loop is Python-level (unrolled): a group is at most
    ACT_ROWS rows, one OUTER instruction each.
    """
    dx = linear_dx(dy, w_t)
    for t in range(dy.rows):
        linear_dw(acc, dy[t, :], x[t, :])
    return dx


# --------------------------------------------------------------------------- norm / activations
def _sigmoid(x):
    """1/(1 + 2^(-x log2 e)): lib.sigmoid's formula (EXP2 then RECIP, no exp/log)."""
    return ol.recip(ol.exp2(x * -LOG2E) + 1.0)


def rmsnorm_fwd(x, gamma, eps: float):
    """xn = x /sqrt(mean(x^2) + eps) * gamma, the kernels.lib formula exactly: RSSQ for the mean
    square, RSQRT for the scale, MUL passes for it and for gamma."""
    r = ol.rsqrt(ol.sumsq(x) * (1.0 / x.cols) + eps)
    return (x * r[:, None]) * gamma[None, :], r


def rmsnorm_bwd(dy, x, r, gamma):
    """dX of `x -> xn = rmsnorm(x) * gamma` for an [R, H] tile, given the forward's `r`.

    With `xh = x * r` (so `xn = xh * gamma`) and `dh = dy * gamma` -- dy being the gradient with
    respect to `xn`:

        dX = r * (dh - mean(dh * xh) * xh)

    The second term is the projection the norm's scale makes: it must be along `xh`, and `gamma`
    must be inside `dh`, so that the projection sees the gradient the gain maps. (A projection
    along `xn` instead, or a `gamma` applied after, is 5-10% off against central differences --
    measured; `tests/test_train.py::test_model_ref_gradients_against_central_differences` keeps
    it.)

    Returns (dx, xh). The gain's gradient is `dgamma = sum_r dy[r] * xh[r]`: a sum over ROWS,
    which the VOP reductions do not do (they run along a tile's last axis), so the caller
    accumulates it with one pass a row, the same rank-1 OUTER pass the weight gradients use.
    """
    n = 1.0 / x.cols
    xh = x * r[:, None]
    dh = dy * gamma[None, :]
    proj = ol.sum(dh * xh, axis=1) * n
    return (dh - xh * proj[:, None]) * r[:, None], xh


def _silu_grad(g):
    """silu'(g) = sigmoid(g) * (1 + g * (1 - sigmoid(g)))."""
    sg = _sigmoid(g)
    return sg * (1.0 + g * (1.0 - sg))


def silu_bwd(dy, g):
    """dX of `silu(g) = g * sigmoid(g)` at the forward's input g: dy * silu'(g)."""
    return dy * _silu_grad(g)


def swiglu_act_fwd(g, u):
    """The SwiGLU product `a = silu(g) * u`: silu(g), then a MUL. Returns (a, sg), so the
    backward pass reuses the forward's sigmoid (one EXP2 and one RECIP an element saved)."""
    sg = _sigmoid(g)
    return (g * sg) * u, sg


def swiglu_bwd(da, g, u, sg):
    """dG and dU of `a = silu(g) * u`, given da (a's gradient), the forward's g, u and its
    sigmoid sg:

        dG = da * u * silu'(g)        dU = da * silu(g)
    """
    dg = (da * u) * (sg * (1.0 + g * (1.0 - sg)))
    du = da * (g * sg)
    return dg, du


# ---------------------------------------------------------------------------------- reductions
def gain_accum(acc, row_grad, row_value):
    """`acc += row_grad * row_value` for two [H] rows: one VOP OUTER pass, the gain gradient's
    accumulation over the batch's rows (docs/train.md 3.2). Exact fp32."""
    return acc.set(acc + row_grad * row_value)


# ------------------------------------------------------------------------------------ adapters
def lora_fwd(x, a: QTensor, b: QTensor, scale: float):
    """The low-rank term of a LoRA layer: `(x @ A^T) @ B^T * scale`, two MMs. Returns
    (h, low) with h = x @ A^T [R, r] -- the bottleneck the adapters' gradients both need.

    A is [r, K], B is [N, r], so the first MM gives [R, r] and the second [R, N]. The second
    streams B's rows, and its reduction dim is the rank r, which the host pads to a whole
    D-block (the MXU streams whole D-byte chunks, docs/isa.md "Weight formats"). Only the
    adapters are trainable, so only their two gradients exist for a frozen layer -- which is
    what makes adapter training cheap (docs/train.md 3.4, 8).
    """
    h = ol.dot(ol.quantize(x), a)                     # [R, r]
    return h, ol.dot(ol.quantize(h), b) * scale       # [R, N]


def lora_bwd(dy, x, h, a_t: QTensor, b_t: QTensor, scale: float, dA, dB):
    """The adapters' gradients for a frozen `y = x @ W^T + scale * (x @ A^T) @ B^T`.

    `dA` and `dB` are fp32 accumulators of the master copies' shapes ([r, K] and [N, r]); both
    are filled by rank-1 OUTER passes over the batch's rows, so they are exact fp32 and need no
    transposed operand:

        dB = scale * dy^T @ h        (a row: dy[t][:, None] * h[t][None, :])
        dA = scale * (dy @ B)^T @ x  (a row: dh[t][:, None] * x[t][None, :])

    Returns `dh = scale * dy @ B` [R, r], which is what a trainable layer *below* this one needs
    for its own `dX` (`lora_dx`).
    """
    dsc = dy * scale                                  # scale * dy, the factor both grads carry
    dh = ol.dot(ol.quantize(dy), b_t) * scale         # [R, r] = scale * dy @ B
    for t in range(dy.rows):
        dB.set(ol.outer(dsc[t, :], h[t, :], acc=dB))  # dB += scale * dy[t] h[t]^T
        dA.set(ol.outer(dh[t, :], x[t, :], acc=dA))   # dA += dh[t] x[t]^T
    return dh, dA, dB


def lora_dx(dy, w_t: QTensor, dh, a_t: QTensor):
    """`dX` of a LoRA layer: `dy @ W + scale * (dy @ B) @ A`, given `dh` from `lora_bwd`.

    The frozen part is the plain `linear_dx`; the adapter's is one more MM against A^T. Only
    two MMs a batch tile, against the three the frozen weight's `dX` alone would not cost.
    """
    return ol.dot(ol.quantize(dy), w_t) + ol.dot(ol.quantize(dh), a_t)


# ---------------------------------------------------------------------------------- attention
def transpose_tile(t, rows: int, cols: int):
    """A [rows, cols] TMEM tile as [cols, rows], bit-exact: one VOP pass a row.

    The ISA has no transpose instruction (docs/isa.md's VOP list has no such function), and
    attention's backward needs `P^T` and `dS^T` (the two `[T, T]` score matrices). The recipe is
    the one a 1-D tile makes possible: a row of the source as a flat `[cols]` tile, copied into
    a column of the destination (`Tile.column()` gives the `[cols, 1]` view). `cols` VOP passes,
    exact, no quantized operand.

    It is `docs/train.md` 9's trap in reverse: `reshape` needs a contiguous tile and an MM's
    output has an odd row stride, but a 1-D tile has no stride at all, which is what makes the
    copy legal.
    """
    out = ol.empty((cols, rows))
    for c in range(rows):
        v = ol.empty((cols,))
        v.set(t[c, :])
        out[:, c:c + 1].set(v.column())
    return out


def attention_fwd(q, k, v_t: QTensor, scale: float):
    """Scaled dot-product attention for one head: `S = q k^T / sqrt(d)`, `P = softmax(S)`,
    `O = P v`. Returns (O, P), P kept for the backward pass.

    The three matmuls are `docs/isa.md`'s own operations, and each has the ISA's primitive:

        S    = dot(q, k)                 an MM: the streamed rows are k's, the reduction is d
        max  = VOP RMAX, exp = EXP2SUB   the softmax's subtract-and-exponentiate in one pass
        sum  = VOP RSUM, then RECIP      the normalizer, then one MUL a row
        O    = dot(P, v_t)               an MM: the reduction is the sequence length, so v
                                         streams as its TRANSPOSE (the host's QTensor)

    `q` [T, d], `k` [T, d] as a QTensor, `v_t` v^T as a [d, T] QTensor, `scale` 1/sqrt(d).
    """
    s = ol.dot(ol.quantize(q), k) * scale                     # [T, T]
    mx = ol.max(s, axis=1)                                    # VOP RMAX
    p = ol.exp2((s - mx[:, None]) * ol.LOG2E)                 # EXP2SUB
    p = p * ol.recip(ol.sum(p, axis=1))[:, None]              # RSUM, RECIP, MUL
    return ol.dot(ol.quantize(p), v_t), p


def attention_bwd(p, dO, v, k_t: QTensor, q_t: QTensor, do_t: QTensor, scale: float,
                  T: int):
    """The gradients of `attention_fwd`, every orientation from `dot`'s contract.

    `dot(a[M,K], w[N,K]) -> [M,N]` reduces over the second axis of both, so:

        dV  = dot(P^T,   dO^T)   reduction T   -> [T, d]
        dP  = dot(dO,    v)      reduction d   -> [T, T]
        dS  = P * (dP - rowsum(P*dP))            the softmax's backward, VOP MUL/SUB/RSUM
        dQ  = dot(dS,    k^T)    reduction T   -> [T, d]
        dK  = dot(dS^T,  q^T)    reduction T   -> [T, d]

    Returns (dQ, dK, dV). `p` is the forward's softmax, `v` the value tile, and the transposed
    operands are the host's QTensors; `do_t` is dO^T. The two `P^T`/`dS^T` come from
    `transpose_tile`.
    """
    dV = ol.dot(ol.quantize(transpose_tile(p, T, T)), do_t)
    dP = ol.dot(ol.quantize(dO), v)                           # [T, T] = dO v^T
    dS = p * (dP - ol.sum(p * dP, axis=1)[:, None])
    dQ = ol.dot(ol.quantize(dS), k_t) * scale
    dK = ol.dot(ol.quantize(transpose_tile(dS, T, T)), q_t) * scale
    return dQ, dK, dV
