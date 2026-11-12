"""float64 numpy references for the training kernels: the math, not the hardware numerics.

This is `opentpu/reference.py`'s counterpart for training, and its contract is the same: a
function per thing the device computes, in float64, so a test can say what the device's fixed
point `MM` and fp32 `VPU` are allowed to differ from (docs/train.md 7). Every formula here is
the one `opentpu/train/kernels.py` and `opentpu/train/loop.py` derive, checked both by central
differences on this module's own forward and by PyTorch's autograd in float64
(`tests/test_train.py`); a change here that disagrees with the device is a change in the
contract, not a tolerance.

The model is the one the device trains (`params.py`): a SwiGLU block with an RMSNorm and a tied
head. The formulas, in the order the device runs them (`loop.train_fwd`, `loop.train_bwd`):

    r    = 1/sqrt(mean(x^2, axis=-1) + eps)
    xh   = x * r
    xn   = xh * gamma
    g    = xn @ w_gate^T          u = xn @ w_up^T
    sg   = sigmoid(g)             a = (g * sg) * u
    y    = a @ w_down^T + x                       (the residual)
    logits = y @ head^T

    d_head = dlogits^T @ y
    dy    = dlogits @ head
    da    = dy @ w_down
    dg    = da * u * sg * (1 + g * (1 - sg))
    du    = da * (g * sg)
    dxn   = dg @ w_gate + du @ w_up
    dnorm = r * (dxn * gamma - xh * mean((dxn * gamma) * xh))
    dx    = dnorm + dy
    d_gamma = sum over rows of (dxn * xh)
    d_gate  = dg^T @ xn     d_up = du^T @ xn     d_down = dy^T @ a

Two of those are worth stating because they are the ones a from-scratch derivation gets wrong:
`gamma` must be applied to `dxn` *before* the norm's projection (a `gamma` applied after, or a
projection along `xn` instead of `xh`, is 5-10% off against central differences), and `d_gamma`
sums `dxn * xh` over I.  Both are checked in `tests/test_train.py`.
"""
from __future__ import annotations

import numpy as np

from .. import quant as Q


# ---------------------------------------------------------------------------------- activations
def rmsnorm_fwd(x, gamma, eps: float):
    """`xn = x /sqrt(mean(x^2) + eps) * gamma`. Returns (xn, cache) with cache = (xh, r): the
    device keeps `r` from the forward pass for its backward pass (`kernels.rmsnorm_fwd`)."""
    x = np.asarray(x, np.float64)
    r = 1.0 / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)
    xh = x * r
    return (xh * gamma if gamma is not None else xh), (xh, r)


def rmsnorm_bwd(dy, x, gamma, eps: float):
    """The gradients of `rmsnorm_fwd`: (dx, dgamma) given the gradient `dy` with respect to xn.

    Recomputes `r` from `x` (the device keeps it from the forward pass; the two are the same
    values). `gamma` goes inside the projection, see the module docstring.
    """
    x = np.asarray(x, np.float64)
    dy = np.asarray(dy, np.float64)
    r = 1.0 / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)
    xh = x * r
    dxn_g = dy * gamma                       # the gain maps the gradient into x's frame
    dx = r * (dxn_g - np.mean(dxn_g * xh, axis=-1, keepdims=True) * xh)
    dgamma = np.einsum("ij,ij->j", dy, xh)   # a sum over the rows, not along the last axis
    return dx, dgamma


def silu_fwd(x):
    """`x * sigmoid(x)`. Returns (y, sg): the forward keeps the sigmoid for its backward."""
    x = np.asarray(x, np.float64)
    sg = 1.0 / (1.0 + np.exp(-x))
    return x * sg, sg


def silu_bwd(dy, x, sg=None):
    """`dy * silu'(x)` with `silu'(x) = sg * (1 + x * (1 - sg))`."""
    x = np.asarray(x, np.float64)
    dy = np.asarray(dy, np.float64)
    sg = 1.0 / (1.0 + np.exp(-x)) if sg is None else sg
    return dy * (sg * (1.0 + x * (1.0 - sg)))


# -------------------------------------------------------------------------------------- linear
def linear_fwd(x, w, bias=None):
    """`y = x @ w^T (+ bias)`. Returns (y, cache) with cache = x (the backward's operand)."""
    x = np.asarray(x, np.float64)
    y = x @ np.asarray(w, np.float64).T
    return (y + bias if bias is not None else y), x


def linear_bwd(dy, cache, w):
    """`(dx, dw, db)` of `linear_fwd`: dx = dy @ w, dw = dy^T @ x, db = sum over rows of dy."""
    dy = np.asarray(dy, np.float64)
    x = np.asarray(cache, np.float64)
    w = np.asarray(w, np.float64)
    return dy @ w, dy.T @ x, dy.sum(axis=0)


# ------------------------------------------------------------------------------------- swiglu
def swiglu_fwd(x, gamma, w_gate, w_up, w_down, eps: float):
    """The SwiGLU block with its residual, `kernels/mlp.py`'s structure.

    `xn = rmsnorm(x) * gamma`, `g = xn @ w_gate^T`, `u = xn @ w_up^T`, `a = silu(g) * u`,
    `y = x + a @ w_down^T`. Returns (y, cache); the cache holds every tile the backward pass
    reads (`loop.train_fwd` stores the same ones to DRAM).
    """
    x = np.asarray(x, np.float64)
    xn, (xh, r) = rmsnorm_fwd(x, gamma, eps)
    g = xn @ np.asarray(w_gate, np.float64).T
    u = xn @ np.asarray(w_up, np.float64).T
    sg = 1.0 / (1.0 + np.exp(-g))
    a = (g * sg) * u
    y = x + a @ np.asarray(w_down, np.float64).T
    return y, dict(x=x, xh=xh, r=r, xn=xn, g=g, u=u, sg=sg, a=a)


def swiglu_bwd(dy, cache, gamma, w_gate, w_up, w_down):
    """The gradients of `swiglu_fwd` with the incoming `dy` on the block's output `y`.

    Returns a dict with `dx`, `dgamma` and `d_gate`, `d_up`, `d_down`. The head's own gradient
    (`dy = dlogits @ head`) is the caller's: it is the `dy` this takes.
    """
    dy = np.asarray(dy, np.float64)
    c = cache
    dyw = dy @ np.asarray(w_down, np.float64)
    silu_grad = c["sg"] * (1.0 + c["g"] * (1.0 - c["sg"]))
    dg = dyw * c["u"] * silu_grad
    du = (dy @ np.asarray(w_down, np.float64)) * (c["g"] * c["sg"])
    dxn = dg @ np.asarray(w_gate, np.float64) + du @ np.asarray(w_up, np.float64)
    dxn_g = dxn * gamma
    dx = c["r"] * (dxn_g - np.mean(dxn_g * c["xh"], axis=-1, keepdims=True) * c["xh"]) + dy
    return dict(dx=dx, dgamma=np.einsum("ij,ij->j", dxn, c["xh"]),
                d_gate=dg.T @ c["xn"], d_up=du.T @ c["xn"], d_down=dy.T @ c["a"],
                dg=dg, du=du, dxn=dxn, da=dy @ np.asarray(w_down, np.float64))


def swiglu_bwd_full(x, gamma, w_gate, w_up, w_down, dy, eps: float):
    """`swiglu_fwd` then `swiglu_bwd`: the pair, for a caller holding no cache."""
    y, cache = swiglu_fwd(x, gamma, w_gate, w_up, w_down, eps)
    return swiglu_bwd(dy, cache, gamma, w_gate, w_up, w_down)


# ------------------------------------------------------------------------------------ the model
def model_fwd_bwd(x, gamma, w_gate, w_up, w_down, head, dlogits, eps: float):
    """The whole forward pass and the whole backward pass of the model the device trains.

    Returns a dict of every intermediate and every gradient, the keys the tests compare against
    the device's DRAM: xn, xh, r, g, u, a, y, logits, d_head, dy, da, dg, du, dxn, dx, d_gamma,
    d_gate, d_up, d_down (and d_head, the tied head's own matrix gradient).
    """
    x = np.asarray(x, np.float64)
    dlogits = np.asarray(dlogits, np.float64)
    y, c = swiglu_fwd(x, gamma, w_gate, w_up, w_down, eps)
    head = np.asarray(head, np.float64)
    logits = y @ head.T
    d_head = dlogits.T @ y
    dy = dlogits @ head
    grads = swiglu_bwd(dy, c, gamma, w_gate, w_up, w_down)
    out = {k: c[k] for k in ("xn", "xh", "r", "g", "u", "a")}
    out.update(y=y, logits=logits, d_head=d_head, dy=dy)
    out.update({k: grads[k] for k in ("da", "dg", "du", "dxn", "dx", "dgamma", "d_gate",
                                      "d_up", "d_down")})
    out["d_gamma"] = out.pop("dgamma")
    return out


# ------------------------------------------------------------------------------------- losses
def softmax_cross_entropy(logits, targets):
    """Cross entropy, mean over the rows, and its gradient.

        loss    = mean_b( logsumexp(logits[b]) - logits[b, target[b]] )
        dlogits = (softmax(logits) - onehot(targets)) / B
    """
    logits = np.asarray(logits, np.float64)
    targets = np.asarray(targets, np.int64).reshape(-1)
    B = logits.shape[0]
    mx = logits.max(axis=1, keepdims=True)
    lse = mx[:, 0] + np.log(np.exp(logits - mx).sum(axis=1))
    loss = float(np.mean(lse - logits[np.arange(B), targets]))
    p = np.exp(logits - lse[:, None])
    p[np.arange(B), targets] -= 1.0
    return loss, p / B


# ------------------------------------------------------------------------------------ AdamW
def adamw_step(params, grads, state, lr: float, beta1: float = 0.9, beta2: float = 0.999,
               eps: float = 1e-8, weight_decay: float = 0.01, step: int = 1) -> dict:
    """One AdamW update, in place, matching `torch.optim.AdamW`: decoupled weight decay
    (`w *= 1 - lr * wd`), then the bias-corrected moments' step.

    `state` is a dict with "m" and "v" dicts of the moments (created here when missing), so a
    caller can run it step after step. Returns the state (and updates `params` in place).
    """
    b1, b2 = beta1, beta2
    state.setdefault("m", {})
    state.setdefault("v", {})
    for name, w in params.items():
        g = grads.get(name)
        if g is None:
            continue
        w = np.asarray(w, np.float32) if w.dtype != np.float32 else w
        m = state["m"].setdefault(name, np.zeros_like(w))
        v = state["v"].setdefault(name, np.zeros_like(w))
        m *= b1
        m += (1.0 - b1) * g
        v *= b2
        v += (1.0 - b2) * (g * g)
        mh = m / (1.0 - b1 ** step)
        vh = v / (1.0 - b2 ** step)
        if weight_decay:
            w *= 1.0 - lr * weight_decay
        w -= lr * mh / (np.sqrt(vh) + eps)
        params[name] = w
    return state


# ----------------------------------------------------------------------- the MX quantization
def mx_quantize(w, fmt: str, D: int):
    """A [N, K] matrix in an MXU format: `(rows, scales)` as `quant.quantize_mxu` makes them --
    the bytes the device's MM streams (`params.quant_w`)."""
    return Q.quantize_mxu(np.ascontiguousarray(w, np.float32), fmt, D)


def mx_dequantize(rows, scales, fmt: str, K: int, D: int, rsc: bool = False):
    """The fp32 matrix a QuantW stands for: `quant.dequantize_mxu` (docs/isa.md "Weight
    formats"), which is what a reference has to use to see the same weights the device did."""
    return Q.dequantize_mxu(rows, scales, fmt, K, D, rsc=rsc)
