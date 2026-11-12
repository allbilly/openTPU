"""Parameters, their MX-quantized forms, the optimizer, and the losses of a training step.

The device streams a matrix in an MXU format (docs/isa.md, "Weight formats"), so a trainable
matrix exists twice: once as the host's fp32 master copy, which the optimizer updates, and once
as the bytes the MM reads (`QuantW`). The master copy is what a checkpoint saves and what AdamW
moves; the quantized form is rebuilt from it every step, which is what makes the update visible
to the device at all (docs/train.md 6).

A gradient is always fp32: the OUTER passes that accumulate `dW` are exact fp32 (docs/isa.md,
VOP OUTER), so the optimizer sees the gradient of the float computation even though the forward
streamed int8 weights. That is the straight-through estimator, stated as a fact of the datapath
rather than an assumption (docs/train.md 4).

Why the optimizer is on the host: the update is O(parameters) and a step's device work is
O(parameters x batch). Moving the update to the device would save nothing and would need an fp32
copy of every parameter in the image, where the MM wants the quantized one. The hybrid split --
device matmuls, host optimizer -- is the shape the ANE-based projects converged on, and it is
the cheaper one here (docs/train.md 2).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import quant as Q


# -------------------------------------------------------------------------------------- shapes
@dataclass(frozen=True)
class Shapes:
    """The model and batch a step trains.

    `vocab` V, `hidden` H, `interm` F. The backward pass streams transposed operands whose
    reduction dims are H, F and V (docs/train.md 3.1), and the MXU streams whole D-byte chunks,
    so all three must be multiples of the configuration's D. `rows` is the row group the
    kernel's hardware loop walks: at most the configuration's ACT_ROWS.
    """

    vocab: int = 32
    hidden: int = 32
    interm: int = 32
    batch: int = 4
    rows: int = 4

    def check(self, cfg) -> None:
        """Refuse the shapes the ISA's operand constraints cannot serve, naming the dimension."""
        for name, n in (("hidden", self.hidden), ("interm", self.interm), ("vocab", self.vocab)):
            if n % cfg.D:
                raise ValueError(f"{name} {n} is not a multiple of the MXU depth D={cfg.D}: the "
                                 f"backward pass streams its transpose, whose reduction dim it "
                                 f"becomes (docs/train.md 3.1)")
        if self.rows < 1:
            raise ValueError(f"rows {self.rows}: a row group is at least one row")
        if self.rows > self.batch:
            raise ValueError(f"rows {self.rows} exceeds the batch {self.batch}")
        if self.rows > cfg.act_rows:
            raise ValueError(f"rows {self.rows}: the MXU's stationary operand holds ACT_ROWS = "
                             f"{cfg.act_rows} rows")
        # the weight gradients are VOP OUTER accumulations, and OUTER holds its column vectors
        # in 256-word buffers (docs/isa.md, OUTER; isa.OUTER_MAX_COLS): a gradient whose K
        # exceeds that is not one pass
        for name, k in (("w_gate/w_up (H)", self.hidden), ("w_down (F)", self.interm),
                        ("head (H)", self.hidden)):
            if k > 256:
                raise ValueError(f"the gradient of {name} has K={k} columns: a VOP OUTER "
                                 f"accumulation holds at most 256 (docs/train.md 9)")

    @property
    def groups(self) -> int:
        """The row groups a batch is walked in (`ceil(batch / rows)`)."""
        return -(-self.batch // self.rows)


# ------------------------------------------------------------------------------- quantized form
@dataclass
class QuantW:
    """A [N, K] matrix in an MXU format: its element rows and their scale rows as
    `quant.quantize_mxu` writes them, with the strides the MM reads them at.

    `cols` is K, the dimension the MM reduces over, so `row_bytes`/`scale_bytes` -- and therefore
    the strides -- depend on it. A matrix and its transpose are two different `QuantW`s, quantized
    separately: every matrix's rows get their own scales, so the transpose is not a view.
    """

    rows: np.ndarray            # [N, row_bytes] uint8
    scales: np.ndarray          # [N, scale_bytes] uint8
    fmt: str
    D: int
    cols: int

    @property
    def n(self) -> int:
        return self.rows.shape[0]

    @property
    def rs(self) -> int:
        return Q.row_bytes(self.cols, self.fmt, self.D)

    @property
    def srs(self) -> int:
        return Q.scale_bytes(self.cols, self.fmt, self.D)

    @property
    def wf(self) -> int:
        return Q.mxu_wf(self.fmt)

    @property
    def shape(self) -> tuple:
        return (self.n, self.cols)

    def dequant(self) -> np.ndarray:
        """The fp32 matrix the MM multiplies against: the format's own error, undone."""
        return Q.dequantize_mxu(self.rows, self.scales, self.fmt, self.cols, self.D)


def quant_w(w: np.ndarray, fmt: str, D: int) -> QuantW:
    """Quantize a [N, K] fp32 matrix into a `QuantW`."""
    w = np.ascontiguousarray(w, np.float32)
    if w.ndim != 2:
        raise ValueError("a weight must be 2-D [N, K]")
    rows, scales = Q.quantize_mxu(w, fmt, D)
    return QuantW(rows, scales, fmt, D, w.shape[1])


def quant_w_t(w: np.ndarray, fmt: str, D: int) -> QuantW:
    """The `QuantW` a backward pass streams for a [N, K] matrix: its transpose as a [K, N]
    operand, quantized on its own rather than as a view (see `QuantW`)."""
    return quant_w(np.ascontiguousarray(w, np.float32).T, fmt, D)


# ------------------------------------------------------------------------------- parameters
MATRICES = ("w_gate", "w_up", "w_down", "head")


@dataclass
class Params:
    """The trainable matrices of the small model, as fp32 master copies.

    The model is `kernels/mlp.py`'s SwiGLU block with an output head:

        xn = rmsnorm(x) * gamma
        a  = silu(xn @ w_gate^T) * (xn @ w_up^T)
        y  = x + a @ w_down^T
        lg = y @ head^T

    `gamma` is a vector (the norm's gain) and has its own gradient; the matrices are 2-D. The
    optimizer updates these arrays in place, and `quantized` rebuilds what the device streams.
    """

    w_gate: np.ndarray          # [F, H]
    w_up: np.ndarray            # [F, H]
    w_down: np.ndarray          # [H, F]
    head: np.ndarray            # [V, H]
    gamma: np.ndarray           # [H]
    fmt: str = "int8"
    D: int = 32
    q: dict = field(default_factory=dict, repr=False)      # name -> QuantW (the forward's)
    q_t: dict = field(default_factory=dict, repr=False)    # name -> QuantW (the backward's)

    def __post_init__(self):
        self.quantized()

    def quantized(self) -> None:
        """(Re)build the MX forms after an optimizer step: the matrices and their transposes."""
        self.q = {n: quant_w(getattr(self, n), self.fmt, self.D) for n in MATRICES}
        self.q_t = {n: quant_w_t(getattr(self, n), self.fmt, self.D) for n in MATRICES}

    def named(self) -> dict:
        """The trainable arrays, in the order a checkpoint writes them (gamma first, so the
        matrices a test compares are contiguous)."""
        return {"gamma": self.gamma, **{n: getattr(self, n) for n in MATRICES}}

    def grads(self) -> dict:
        """Zero gradient buffers, in the same shapes (and dtype: the master copy is fp32)."""
        return {n: np.zeros_like(a) for n, a in self.named().items()}

    @staticmethod
    def random(shapes: Shapes, seed: int = 0) -> "Params":
        """A small model at a sane initialization (the scaled init `kernels/` uses)."""
        rng = np.random.default_rng(seed)
        H, F, V = shapes.hidden, shapes.interm, shapes.vocab
        return Params(
            w_gate=(rng.standard_normal((F, H)) / np.sqrt(H)).astype(np.float32),
            w_up=(rng.standard_normal((F, H)) / np.sqrt(H)).astype(np.float32),
            w_down=(rng.standard_normal((H, F)) / np.sqrt(F)).astype(np.float32),
            head=(rng.standard_normal((V, H)) / np.sqrt(H)).astype(np.float32),
            gamma=(1.0 + 0.1 * rng.standard_normal(H)).astype(np.float32))


# --------------------------------------------------------------------------------- the optimizer
@dataclass
class AdamW:
    """AdamW on the fp32 master copies, matching `torch.optim.AdamW`: decoupled weight decay
    (`w *= 1 - lr * wd`), then the bias-corrected moments.

    `update` takes the gradients a step produced and moves every matrix in place; a matrix
    without a gradient is left alone (a frozen layer's).
    """

    lr: float = 1e-2
    betas: tuple = (0.9, 0.999)
    eps: float = 1e-8
    weight_decay: float = 0.01
    step: int = 0
    m: dict = field(default_factory=dict, repr=False)
    v: dict = field(default_factory=dict, repr=False)

    def update(self, params: Params, grads: dict) -> dict:
        """One update of every matrix with a gradient; returns each one's relative move."""
        self.step += 1
        b1, b2 = self.betas
        moved = {}
        for name, w in params.named().items():
            g = grads.get(name)
            if g is None or not np.any(g):
                continue
            g = np.asarray(g, np.float32)
            if g.shape != w.shape:
                raise ValueError(f"{name}: gradient {g.shape} for a weight of {w.shape}")
            if name not in self.m:
                self.m[name] = np.zeros_like(w)
                self.v[name] = np.zeros_like(w)
            m, v = self.m[name], self.v[name]
            m *= b1
            m += (1.0 - b1) * g
            v *= b2
            v += (1.0 - b2) * (g * g)
            mh = m / (1.0 - b1 ** self.step)
            vh = v / (1.0 - b2 ** self.step)
            if self.weight_decay:
                w *= 1.0 - self.lr * self.weight_decay
            w -= self.lr * mh / (np.sqrt(vh) + self.eps)
            moved[name] = float(np.abs(g).max() / (np.abs(w).max() + 1e-30))
        params.quantized()
        return moved


# ------------------------------------------------------------------------------------- losses
def softmax_xent(logits: np.ndarray, targets: np.ndarray) -> tuple[float, np.ndarray]:
    """Cross entropy of a [B, V] logits group, and its [B, V] gradient. The host's part of a
    step: V columns of exp and log a row, a few KB, versus the MMs the device runs.

        loss    = mean_b( logsumexp(logits[b]) - logits[b, target[b]] )
        dlogits = (softmax(logits) - onehot(targets)) / B
    """
    logits = np.asarray(logits, np.float64)
    targets = np.asarray(targets, np.int64).reshape(-1)
    B = logits.shape[0]
    if targets.shape[0] != B:
        raise ValueError(f"{targets.shape[0]} targets for {B} rows")
    mx = logits.max(axis=1, keepdims=True)
    lse = mx[:, 0] + np.log(np.exp(logits - mx).sum(axis=1))
    loss = float(np.mean(lse - logits[np.arange(B), targets]))
    p = np.exp(logits - lse[:, None])
    p[np.arange(B), targets] -= 1.0
    return loss, (p / B).astype(np.float32)


def mse(logits: np.ndarray, targets: np.ndarray) -> tuple[float, np.ndarray]:
    """Mean squared error and its gradient: a regression head, the tests' second objective
    (it needs no vocabulary axis and its optimum is analytic)."""
    d = np.asarray(logits, np.float64) - np.asarray(targets, np.float64)
    return float((d * d).mean()), (2.0 * d / d.size).astype(np.float32)
