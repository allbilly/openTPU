"""A whole transformer layer trained on the device: attention, an MLP, and every parameter's
gradient.

This is docs/train.md 8's rung 6 (`full training`, not just adapters): the layer
`opentpu/kernels/attention.py` runs for inference, with its backward pass written out by hand in
the module below. The pieces are `kernels.py`'s: `attention_fwd`/`attention_bwd` for the head,
`linear_fwd`/`linear_dx`/`linear_dw` for the projections and the MLP, `rmsnorm_fwd`/
`rmsnorm_bwd` for the two norms, and `swiglu_*` for the activation.

    h1 = x + attn(rmsnorm(x) * g1) @ Wo^T        (q, k, v from the same normalized input)
    y  = h1 + mlp(rmsnorm(h1) * g2)              (a SwiGLU MLP, as kernels/mlp.py)

Every matrix is trainable: Wq, Wk, Wv, Wo, Wg, Wu, Wd, and the two gains. The gradients are the
same OUTER accumulations as the block's (`dW = sum_t dy[t] x[t]^T`), one per projection, so a
step costs seven `[., .]` accumulations instead of one.

Why the transposes are the host's: the MM streams a matrix's rows, and the layer's backward
needs `K^T`, `Q^T`, `V^T` and `dO^T` (`attention_bwd`'s document explains the orientations).
The host quantizes each matrix and its transpose as two separate `QuantW`s -- every matrix's
rows get their own scale, so a transpose is not a view (docs/train.md 5).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import language as ol
from .. import quant as Q
from ..compiler import Affine, QTensor, Tensor, current
from ..isasim import Config, Machine
from . import kernels as K
from .params import AdamW, quant_w, quant_w_t, softmax_xent

# the trainable matrices of one layer, (N, K) for y = x @ W^T
LAYER_W = ("Wq", "Wk", "Wv", "Wo", "Wg", "Wu", "Wd")
GAINS = ("g1", "g2")


def _strides(shape) -> tuple:
    shape = tuple(shape)
    st, out = 1, []
    for n in reversed(shape):
        out.append(st)
        st *= n
    return tuple(reversed(out))


@dataclass
class LayerParams:
    """One transformer layer's parameters as fp32 master copies, with their MX forms.

    `[N, K]` matrices for the MM (`y = x @ W^T`), and the two norms' gains as vectors. The
    quantized forms include each matrix's transpose, rebuilt after every optimizer step.
    """

    Wq: np.ndarray
    Wk: np.ndarray
    Wv: np.ndarray
    Wo: np.ndarray
    Wg: np.ndarray
    Wu: np.ndarray
    Wd: np.ndarray
    g1: np.ndarray
    g2: np.ndarray
    fmt: str = "int8"
    D: int = 32
    q: dict = field(default_factory=dict, repr=False)
    q_t: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.quantized()

    def quantized(self) -> None:
        self.q = {n: quant_w(getattr(self, n), self.fmt, self.D) for n in LAYER_W}
        self.q_t = {n: quant_w_t(getattr(self, n), self.fmt, self.D) for n in LAYER_W}

    def named(self) -> dict:
        return {**{n: getattr(self, n) for n in LAYER_W},
                **{n: getattr(self, n) for n in GAINS}}

    @staticmethod
    def random(d_hidden: int, d_ff: int, D: int, seed: int = 0,
               fmt: str = "int8") -> "LayerParams":
        """A layer at the scaled init `kernels/` uses, with unit-scale norm gains."""
        rng = np.random.default_rng(seed)

        def w(n: int, k: int) -> np.ndarray:
            return (rng.standard_normal((n, k)) / np.sqrt(k)).astype(np.float32)

        return LayerParams(Wq=w(d_hidden, d_hidden), Wk=w(d_hidden, d_hidden),
                           Wv=w(d_hidden, d_hidden), Wo=w(d_hidden, d_hidden),
                           Wg=w(d_ff, d_hidden), Wu=w(d_ff, d_hidden),
                           Wd=w(d_hidden, d_ff),
                           g1=(1.0 + 0.1 * rng.standard_normal(d_hidden)).astype(np.float32),
                           g2=(1.0 + 0.1 * rng.standard_normal(d_hidden)).astype(np.float32),
                           fmt=fmt, D=D)


# ------------------------------------------------------------------------------ the FP32 reference
def layer_ref(x, p: LayerParams, scale: float, dlogits, eps: float = 1e-6) -> dict:
    """float64 forward and backward of the layer: every intermediate and every gradient.

    The reference the device's step is tested against (docs/train.md 7). It is the same graph the
    kernels trace, so a disagreement is a bug in one of the two, not a tolerance.
    """
    x = np.asarray(x, np.float64)
    dl = np.asarray(dlogits, np.float64)
    g1, g2 = p.g1.astype(np.float64), p.g2.astype(np.float64)
    W = {n: getattr(p, n).astype(np.float64) for n in LAYER_W}

    def norm(v, g):
        r = 1.0 / np.sqrt(np.mean(v * v, axis=-1, keepdims=True) + eps)
        return (v * r) * g, v * r, r

    xn1, xh1, r1 = norm(x, g1)
    q, k, v = xn1 @ W["Wq"].T, xn1 @ W["Wk"].T, xn1 @ W["Wv"].T
    s = (q @ k.T) * scale
    s = s - s.max(-1, keepdims=True)
    pm = np.exp(s)
    pm = pm / pm.sum(-1, keepdims=True)
    o = pm @ v
    h1 = x + o @ W["Wo"].T
    xn2, xh2, r2 = norm(h1, g2)
    gg, uu = xn2 @ W["Wg"].T, xn2 @ W["Wu"].T
    sg = 1.0 / (1.0 + np.exp(-gg))
    a = (gg * sg) * uu
    y = h1 + a @ W["Wd"].T

    # ---- backward, from dlogits on y
    dy = dl
    da = dy @ W["Wd"]
    dg = (da * uu) * (sg * (1.0 + gg * (1.0 - sg)))
    du = da * (gg * sg)
    dxn2 = dg @ W["Wg"] + du @ W["Wu"]
    dxn2_g = dxn2 * g2
    dnorm2 = r2 * (dxn2_g - np.mean(dxn2_g * xh2, axis=-1, keepdims=True) * xh2)
    dh1 = dnorm2 + dy                                  # the residual's own gradient
    do_ = dh1 @ W["Wo"]                                # the gradient of o = P v
    dV = pm.T @ do_
    dO = do_
    dP = dO @ v.T
    dS = pm * (dP - np.sum(dP * pm, axis=-1, keepdims=True))
    dQ = (dS @ k) * scale
    dK = (dS.T @ q) * scale
    dxn1 = dQ @ W["Wq"] + dK @ W["Wk"] + dV @ W["Wv"]
    dxn1_g = dxn1 * g1
    dnorm1 = r1 * (dxn1_g - np.mean(dxn1_g * xh1, axis=-1, keepdims=True) * xh1)
    dx = dnorm1 + dh1                                   # (dh1 already carries the residual)

    return dict(
        xn1=xn1, xh1=xh1, r1=r1, q=q, k=k, v=v, S=s, P=pm, O=o, h1=h1,
        xn2=xn2, xh2=xh2, r2=r2, g=gg, u=uu, a=a, y=y,
        dy=dy, da=da, dg=dg, du=du, dxn2=dxn2, dh1=dh1, dO=dO, dV=dV, dP=dP, dS=dS,
        dQ=dQ, dK=dK, dxn1=dxn1, dx=dx,
        dWq=dQ.T @ xn1, dWk=dK.T @ xn1, dWv=dV.T @ xn1, dWo=dh1.T @ o,
        dWg=dg.T @ xn2, dWu=du.T @ xn2, dWd=dy.T @ a,
        dg1=np.einsum("ij,ij->j", dxn1, xh1), dg2=np.einsum("ij,ij->j", dxn2, xh2))


# ------------------------------------------------------------------------------- the step's DRAM
def _strides_(shape) -> tuple:
    shape = tuple(shape)
    st, out = 1, []
    for n in reversed(shape):
        out.append(st)
        st *= n
    return tuple(reversed(out))


class Layout:
    """One layer's step in DRAM: every streamed matrix (and its transpose), the saved
    activations, and every gradient.

    The matrices are byte-addressed MX rows (the MM streams bytes); the activations and the
    gradients are fp32 words. Each buffer starts on a 128-byte boundary, so every DMA and every
    MM operand is aligned (`D <= 128`).
    """

    def __init__(self, p: LayerParams, cfg: Config, T: int, batch: int, fmt: str):
        self.p, self.cfg, self.T, self.batch, self.fmt = p, cfg, T, batch, fmt
        self.D = cfg.D
        self.byte: dict = {}
        self.word: dict = {}
        self.shape: dict = {}
        self.pos = 0
        (N, K), (FF, _) = p.Wq.shape, p.Wg.shape
        self.N, self.K, self.FF = N, K, FF
        # the seven matrices, and the transposes the backward pass streams
        for name in LAYER_W:
            n, k = getattr(p, name).shape
            self._cb(name + "_data", n * Q.row_bytes(k, fmt, self.D))
            self._cb(name + "_scale", n * Q.scale_bytes(k, fmt, self.D))
            self._cb(name + "_t_data", k * Q.row_bytes(n, fmt, self.D))
            self._cb(name + "_t_scale", k * Q.scale_bytes(n, fmt, self.D))
        # the regions the device QSTs its own tiles into: k (streamed by the score MM, [DH,T]
        # as rows of T), and v^T / dO^T ([DH, T] each, streamed by the P/dS MMs)
        self._cb("k_data", N * Q.row_bytes(T, fmt, self.D))
        self._cb("k_scale", N * Q.scale_bytes(T, fmt, self.D))
        # v itself, as the score/value MM's operand for dP = dO v^T ([T, DH] rows of DH)
        self._cb("vv_data", T * Q.row_bytes(N, fmt, self.D))
        self._cb("vv_scale", T * Q.scale_bytes(N, fmt, self.D))
        for name in ("qT", "kT", "vT", "doT"):
            self._cb(name + "_data", N * Q.row_bytes(T, fmt, self.D))
            self._cb(name + "_scale", N * Q.scale_bytes(T, fmt, self.D))
        # the saved activations (fp32) and the gradients
        for name, shp in (("x", (T, K)), ("xn1", (T, K)), ("q", (T, N)), ("v", (T, N)),
                          ("P", (T, T)),
                          ("O", (T, N)), ("h1", (T, K)), ("xn2", (T, K)), ("g", (T, FF)),
                          ("u", (T, FF)), ("a", (T, FF)), ("y", (T, K)), ("dl", (T, K)),
                          ("g1", (K,)), ("g2", (K,)),
                          ("dWq", (N, K)), ("dWk", (N, K)), ("dWv", (N, K)), ("dWo", (N, N)),
                          ("dWg", (FF, K)), ("dWu", (FF, K)), ("dWd", (K, FF)),
                          ("dg1", (K,)), ("dg2", (K,)), ("dx", (T, K))):
            self._cw(name, shp)

    def _cb(self, name: str, n: int) -> None:
        self.pos = -(-self.pos // 128) * 128
        self.byte[name] = self.pos
        self.pos = -(-(self.pos + n) // 128) * 128

    def _cw(self, name: str, shp) -> None:
        self.pos = -(-self.pos // 128) * 128
        self.word[name] = self.pos // 4
        self.shape[name] = tuple(shp)
        self.pos = -(-(self.pos + 4 * int(np.prod(shp))) // 128) * 128

    @property
    def nbytes(self) -> int:
        return -(-self.pos // 128) * 128

    def t(self, name: str) -> Tensor:
        s = self.shape[name]
        return Tensor(Affine(4 * self.word[name]), s, _strides_(s))

    def q(self, name: str, n: int, k: int) -> QTensor:
        D, fmt = self.D, self.fmt
        return QTensor(Affine(self.byte[name + "_data"]), Affine(self.byte[name + "_scale"]),
                       (int(n), int(k)), Q.row_bytes(k, fmt, D), Q.scale_bytes(k, fmt, D), D,
                       wf=Q.mxu_wf(fmt))


# ------------------------------------------------------------------------------ the two programs
@ol.jit
def layer_fwd(x, g1, g2, Wq, Wk, Wv, Wo, Wg, Wu, Wd, k_d, k_s, vv_d, vv_s,
              qT_d, qT_s, kT_d, kT_s,
              vT_d, vT_s, xn1_o, v_o, P_o, O_o,
              h1_o, xn2_o, g_o, u_o, a_o, y_o, scale, eps, T, DH, FF, srs, rb, N_rb):
    """The layer's forward pass, storing what the backward pass reads back.

    `Wk` streams the keys as the score MM's operand (`S = q k^T` is `dot(q, Wk)`); `vT_d`/`vT_s`
    are the DRAM region the *device's own* transposed V is QST'd into (`vT`), which the second
    MM then streams -- the device transposes and quantizes its own tensor, so no host round trip
    is on the path.

    `P` (the softmax) is stored for the backward pass; `xn1`/`xn2` because the projections'
    gradients are outer products against them; `g`/`u`/`a` because the MLP's backward needs the
    forward's activation values (manual backpropagation has no graph to re-run them from).
    """
    xv = ol.load(x)                                      # [T, DH]
    xn1, r1 = K.rmsnorm_fwd(xv, ol.load(g1), eps)
    ol.store(xn1_o, xn1)
    q = K.linear_fwd(xn1, Wq)                            # [T, DH]
    k = K.linear_fwd(xn1, Wk)
    b = current()
    # q^T and k^T: the backward's dK/dQ MMs stream them (the device transposes + quantizes its
    # own tiles; a weight's transpose is a different matrix and would be wrong here)
    b.store_quantized(K.transpose_tile(q, T, DH), Affine.of(qT_d.base),
                      Affine.of(qT_s.base), rb, 1, row_scale=False)
    b.store_quantized(K.transpose_tile(k, T, DH), Affine.of(kT_d.base),
                      Affine.of(kT_s.base), rb, 1, row_scale=False)
    # k is a QST region the score MM streams (the device quantizes its own key tile)
    b.store_quantized(k, Affine.of(k_d.base), Affine.of(k_s.base), rb, 1, row_scale=False)
    k_q = QTensor(Affine.of(k_d.base), Affine.of(k_s.base), (DH, T), rb, srs, DH, wf=0)
    v = K.linear_fwd(xn1, Wv)
    ol.store(v_o, v)
    b.store_quantized(v, Affine.of(vv_d.base), Affine.of(vv_s.base), N_rb, 1, row_scale=False)
    # S = q k^T (the MM's row-wise dot), the softmax, then O = P v -- v transposed on the device
    s = ol.dot(ol.quantize(q), k_q) * scale
    mx = ol.max(s, axis=1)
    p = ol.exp2((s - mx[:, None]) * ol.LOG2E)
    p = p * ol.recip(ol.sum(p, axis=1))[:, None]
    ol.store(P_o, p)
    vT = K.transpose_tile(v, T, DH)                      # [DH, T] in TMEM
    b = current()
    b.store_quantized(vT, Affine.of(vT_d.base), Affine.of(vT_s.base), rb, 1, row_scale=False)
    vt_q = QTensor(Affine.of(vT_d.base), Affine.of(vT_s.base), (DH, T), rb, srs, DH, wf=0)
    O = ol.dot(ol.quantize(p), vt_q)
    ol.store(O_o, O)
    h1 = xv + K.linear_fwd(O, Wo)                        # [T, DH]
    ol.store(h1_o, h1)
    xn2, r2 = K.rmsnorm_fwd(h1, ol.load(g2), eps)
    ol.store(xn2_o, xn2)
    g = K.linear_fwd(xn2, Wg)                            # [T, FF]
    ol.store(g_o, g)
    u = K.linear_fwd(xn2, Wu)
    ol.store(u_o, u)
    a, sg = K.swiglu_act_fwd(g, u)
    ol.store(a_o, a)
    ol.store(y_o, h1 + K.linear_fwd(a, Wd))


@ol.jit
def layer_bwd(x, g1, g2, dl, xn1_i, v_i, vQ, P_i, O_i, h1_i, xn2_i, g_i, u_i, a_i,
              Wq_t, Wk_t, Wv_t, Wo_t, Wd_t, Wg_t, Wu_t, doT_d, doT_s, vv_d, vv_s,
              qT_d, qT_s, kT_d, kT_s,
              dWq_o, dWk_o, dWv_o, dWo_o, dWg_o, dWu_o, dWd_o, dg1_o, dg2_o, dx_o,
              scale, eps, T, DH, FF, srs, rb, N_rb, N_srs):
    """The layer's backward pass: every matrix's gradient, both gains', and `dx`.

    The seven weight gradients are OUTER accumulations over the batch's rows (exact fp32, no
    transposed operand needed). The dX matmuls stream the host's transposed weights. `dO`'s
    transpose -- which `dV = P^T dO` needs -- is transposed and QST'd on the device, the same
    path the forward used for `v`.

    `qT`/`kT` are q's and k's transposes as streamed operands; `doT` is dO's, QST'd on the
    device into `doT_d`/`doT_s` before the MMs that read it.
    """
    xv = ol.load(x)
    dlv = ol.load(dl)
    xn1, P, O, h1, xn2 = (ol.load(t_) for t_ in (xn1_i, P_i, O_i, h1_i, xn2_i))
    vv = ol.load(v_i)
    gv, uv, av = ol.load(g_i), ol.load(u_i), ol.load(a_i)
    D_ = DH
    # ---- the MLP's backward ----
    # dA = dY @ Wd: the gradient of the MLP's product a [T, FF], not of the layer's output
    da = K.linear_dx(dlv, Wd_t)
    dg, du = K.swiglu_bwd(da, gv, uv, K._sigmoid(gv))
    dxn2 = K.linear_dx(dg, Wg_t) + K.linear_dx(du, Wu_t)
    dnorm2, xh2 = K.rmsnorm_bwd(dxn2, h1, ol.rsqrt(ol.sumsq(h1) * (1.0 / D_) + eps),
                                ol.load(g2))
    dh1 = dnorm2 + dlv                                   # the residual's own gradient
    # ---- the attention's backward ----
    do_ = K.linear_dx(dh1, Wo_t)                         # d(o) = dh1 @ Wo
    doT = K.transpose_tile(do_, T, DH)                   # [DH, T]
    b = current()
    b.store_quantized(doT, Affine.of(doT_d.base), Affine.of(doT_s.base), rb, 1, row_scale=False)
    doT_q = QTensor(Affine.of(doT_d.base), Affine.of(doT_s.base), (DH, T), rb, srs, DH, wf=0)
    dV = ol.dot(ol.quantize(K.transpose_tile(P, T, T)), doT_q)
    vQ = QTensor(Affine.of(vv_d.base), Affine.of(vv_s.base), (T, DH),
                 N_rb, N_srs, DH, wf=0)
    dP = ol.dot(ol.quantize(do_), vQ)                     # [T, T] = dO v^T
    dS = P * (dP - ol.sum(P * dP, axis=1)[:, None])      # the softmax's backward
    # dQ = dS k^T and dK = dS^T q^T: both stream the *computed* k/q transposes the forward
    # QST'd into DRAM (not the projection matrices' transposes)
    kT_q = QTensor(Affine.of(kT_d.base), Affine.of(kT_s.base), (DH, T), rb, srs, DH, wf=0)
    qT_q = QTensor(Affine.of(qT_d.base), Affine.of(qT_s.base), (DH, T), rb, srs, DH, wf=0)
    dQ = ol.dot(ol.quantize(dS), kT_q) * scale           # [T, DH]
    dK = ol.dot(ol.quantize(K.transpose_tile(dS, T, T)), qT_q) * scale
    dxn1 = (K.linear_dx(dQ, Wq_t) + K.linear_dx(dK, Wk_t) + K.linear_dx(dV, Wv_t))
    dnorm1, xh1 = K.rmsnorm_bwd(dxn1, xv, ol.rsqrt(ol.sumsq(xv) * (1.0 / D_) + eps),
                                ol.load(g1))
    ol.store(dx_o, dnorm1 + dh1)
    # ---- the seven weight gradients, one OUTER pass a row each ----
    # the accumulators have the master copies' shapes: Wg/Wu are [FF, DH], dWd is [DH, FF]
    dWq = ol.zeros((DH, DH))
    dWk = ol.zeros((DH, DH))
    dWv = ol.zeros((DH, DH))
    dWo = ol.zeros((DH, DH))
    dWg = ol.zeros((FF, DH))
    dWu = ol.zeros((FF, DH))
    dWd = ol.zeros((DH, FF))
    dg1 = ol.zeros((DH,))
    dg2 = ol.zeros((DH,))
    for t in range(T):
        dWq.set(ol.outer(dQ[t, :], xn1[t, :], acc=dWq))
        dWk.set(ol.outer(dK[t, :], xn1[t, :], acc=dWk))
        dWv.set(ol.outer(dV[t, :], xn1[t, :], acc=dWv))
        dWo.set(ol.outer(dh1[t, :], O[t, :], acc=dWo))
        dWg.set(ol.outer(dg[t, :], xn2[t, :], acc=dWg))
        dWu.set(ol.outer(du[t, :], xn2[t, :], acc=dWu))
        dWd.set(ol.outer(dlv[t, :], av[t, :], acc=dWd))
        dg1.set(K.gain_accum(dg1, dxn1[t, :], xh1[t, :]))
        dg2.set(K.gain_accum(dg2, dxn2[t, :], xh2[t, :]))
    ol.store(dWq_o, dWq); ol.store(dWk_o, dWk); ol.store(dWv_o, dWv); ol.store(dWo_o, dWo)
    ol.store(dWg_o, dWg); ol.store(dWu_o, dWu); ol.store(dWd_o, dWd)
    ol.store(dg1_o, dg1); ol.store(dg2_o, dg2)


# ------------------------------------------------------------------------------------- the trainer
class LayerTrainer:
    """One transformer layer's training step: the two programs, the DRAM, the optimizer.

    `step` runs the forward and the backward and hands the seven matrices' and two gains'
    gradients to AdamW; `train_step` adds the host's loss between them, which is the same hybrid
    every other step in this package uses (docs/train.md 2). The frozen/adapted variants are
    `lora.py`'s; this one trains every parameter of the layer, which is docs/train.md 8's rung 6.
    """

    def __init__(self, params: LayerParams, cfg: Config, T: int, optimizer: AdamW | None = None,
                 eps: float = 1e-6, scale: float | None = None, fmt: str = "int8",
                 at: int = 0):
        self.p, self.cfg, self.T = params, cfg, T
        self.opt = optimizer or AdamW()
        self.eps = eps
        self.scale = 1.0 / np.sqrt(cfg.D) if scale is None else scale
        self.fmt = fmt
        self.lay = Layout(params, cfg, T, 1, fmt)
        if at:                              # a stack slot: every address moves up by `at` bytes
            for k in self.lay.byte:
                self.lay.byte[k] += at
            for k in self.lay.word:
                self.lay.word[k] = (4 * self.lay.word[k] + at) // 4
        self.srs = Q.scale_bytes(T, fmt, cfg.D)
        self.rb = Q.row_bytes(T, fmt, cfg.D)
        self.progs: dict = {"forward": [], "backward": []}
        self.image = self._image()
        self.machine: Machine | None = None
        self._trace()

    def _raw(self, at: int, n: int) -> Tensor:
        """A byte region as a flat word-addressed descriptor (the QST target's address: QST
        writes bytes, so the descriptor only carries the address and its length)."""
        return Tensor(Affine(at), (n,), (1,))

    def _image(self) -> np.ndarray:
        img = np.zeros(self.lay.nbytes, np.uint8)

        def put(at: int, data: np.ndarray) -> None:
            b = np.ascontiguousarray(data).view(np.uint8).reshape(-1)
            img[at:at + b.size] = b

        return img

    def write_params(self, img: np.ndarray) -> None:
        """The seven matrices and their transposes as MX rows, plus the two gains, at their
        addresses. Called once at the start and again after every optimizer step."""
        def put(at: int, data: np.ndarray) -> None:
            b = np.ascontiguousarray(data).view(np.uint8).reshape(-1)
            img[at:at + b.size] = b

        for name in LAYER_W:
            q, qt = self.p.q[name], self.p.q_t[name]
            put(self.lay.byte[name + "_data"], q.rows)
            put(self.lay.byte[name + "_scale"], q.scales)
            put(self.lay.byte[name + "_t_data"], qt.rows)
            put(self.lay.byte[name + "_t_scale"], qt.scales)
        for name in GAINS:
            put(4 * self.lay.word[name], getattr(self.p, name))

    def _trace(self) -> None:
        lay, T = self.lay, self.T
        N, K, FF = lay.N, lay.K, lay.FF
        for s in range(self.cfg.S):
            self.progs["forward"].append(layer_fwd.trace(self.cfg, s, {
                "x": lay.t("x"), "g1": lay.t("g1"), "g2": lay.t("g2"),
                "Wq": lay.q("Wq", N, K), "Wk": lay.q("Wk", N, K), "Wv": lay.q("Wv", N, K),
                "Wo": lay.q("Wo", N, N), "Wg": lay.q("Wg", FF, K), "Wu": lay.q("Wu", FF, K),
                "Wd": lay.q("Wd", K, FF),
                "k_d": self._raw(lay.byte["k_data"], N * self.rb),
                "k_s": self._raw(lay.byte["k_scale"], N * self.srs),
                "vv_d": self._raw(lay.byte["vv_data"], T * Q.row_bytes(N, self.fmt, self.cfg.D)),
                "vv_s": self._raw(lay.byte["vv_scale"], T * Q.scale_bytes(N, self.fmt, self.cfg.D)),
                "qT_d": self._raw(lay.byte["qT_data"], N * self.rb),
                "qT_s": self._raw(lay.byte["qT_scale"], N * self.srs),
                "kT_d": self._raw(lay.byte["kT_data"], N * self.rb),
                "kT_s": self._raw(lay.byte["kT_scale"], N * self.srs),
                "vT_d": self._raw(lay.byte["vT_data"], N * self.rb),
                "vT_s": self._raw(lay.byte["vT_scale"], N * self.srs),
                "xn1_o": lay.t("xn1"), "v_o": lay.t("v"), "P_o": lay.t("P"), "O_o": lay.t("O"),
                "h1_o": lay.t("h1"), "xn2_o": lay.t("xn2"), "g_o": lay.t("g"), "u_o": lay.t("u"),
                "a_o": lay.t("a"), "y_o": lay.t("y"),
                "scale": self.scale, "eps": self.eps, "T": T, "DH": N, "FF": FF,
                "srs": self.srs, "rb": self.rb, "N_rb": self.rb}).finish())
            self.progs["backward"].append(layer_bwd.trace(self.cfg, s, {
                "x": lay.t("x"), "g1": lay.t("g1"), "g2": lay.t("g2"), "dl": lay.t("dl"),
                "xn1_i": lay.t("xn1"), "v_i": lay.t("v"),
                "vQ": QTensor(Affine(lay.byte["vT_data"]), Affine(lay.byte["vT_scale"]),
                              (N, T), self.rb, self.srs, self.cfg.D, wf=0),
                "P_i": lay.t("P"), "O_i": lay.t("O"),
                "h1_i": lay.t("h1"), "xn2_i": lay.t("xn2"), "g_i": lay.t("g"),
                "u_i": lay.t("u"), "a_i": lay.t("a"),
                "Wq_t": lay.q("Wq_t", K, N), "Wk_t": lay.q("Wk_t", K, N),
                "Wv_t": lay.q("Wv_t", K, N), "Wo_t": lay.q("Wo_t", N, N),
                "Wd_t": lay.q("Wd_t", FF, K), "Wg_t": lay.q("Wg_t", K, FF),
                "Wu_t": lay.q("Wu_t", K, FF),
                "doT_d": self._raw(lay.byte["doT_data"], N * self.rb),
                "doT_s": self._raw(lay.byte["doT_scale"], N * self.srs),
                "vv_d": self._raw(lay.byte["vv_data"], T * Q.row_bytes(N, self.fmt, self.cfg.D)),
                "vv_s": self._raw(lay.byte["vv_scale"], T * Q.scale_bytes(N, self.fmt, self.cfg.D)),
                "N_srs": self.srs,
                "qT_d": self._raw(lay.byte["qT_data"], N * self.rb),
                "qT_s": self._raw(lay.byte["qT_scale"], N * self.srs),
                "kT_d": self._raw(lay.byte["kT_data"], N * self.rb),
                "kT_s": self._raw(lay.byte["kT_scale"], N * self.srs),
                "dWq_o": lay.t("dWq"), "dWk_o": lay.t("dWk"), "dWv_o": lay.t("dWv"),
                "dWo_o": lay.t("dWo"), "dWg_o": lay.t("dWg"), "dWu_o": lay.t("dWu"),
                "dWd_o": lay.t("dWd"), "dg1_o": lay.t("dg1"), "dg2_o": lay.t("dg2"),
                "dx_o": lay.t("dx"),
                "scale": self.scale, "eps": self.eps, "T": T, "DH": N, "FF": FF,
                "srs": self.srs, "rb": self.rb, "N_rb": self.rb}).finish())

    # ---- the readbacks and the step
    def _buffer(self, name: str) -> np.ndarray:
        off = 4 * self.lay.word[name]
        shp = self.lay.shape[name]
        d = self.machine.slices[0].dram
        return d[off:off + 4 * int(np.prod(shp))].view(np.float32).reshape(shp)

    def _write(self, name: str, data: np.ndarray) -> None:
        off = 4 * self.lay.word[name]
        b = np.ascontiguousarray(data, np.float32).view(np.uint8).reshape(-1)
        self.machine.slices[0].dram[off:off + b.size] = b

    def _ensure(self) -> None:
        if self.machine is None:
            self.write_params(self.image)
            self.machine = Machine(self.cfg, self.progs["forward"], [self.image.copy()])

    def forward(self, x: np.ndarray) -> dict:
        """The layer's forward pass: returns every stored tile the backward pass reads."""
        self._ensure()
        self._write("x", np.asarray(x, np.float32))
        self.machine.load(self.progs["forward"]).run()
        return {n: self._buffer(n).copy() for n in ("y", "xn1", "P", "O", "h1", "xn2", "g", "u",
                                                    "a")}

    def backward(self, dlogits: np.ndarray) -> dict:
        """Every gradient of the layer, from the loss's gradient on the layer's output."""
        self._ensure()
        self._write("dl", np.asarray(dlogits, np.float32))
        self.machine.load(self.progs["backward"]).run()
        out = {n: self._buffer(n).copy() for n in ("dWq", "dWk", "dWv", "dWo", "dWg", "dWu",
                                                   "dWd", "dg1", "dg2", "dx")}
        return {"Wq": out["dWq"], "Wk": out["dWk"], "Wv": out["dWv"], "Wo": out["dWo"],
                "Wg": out["dWg"], "Wu": out["dWu"], "Wd": out["dWd"], "g1": out["dg1"],
                "g2": out["dg2"], "dx": out["dx"]}

    def step(self, x: np.ndarray, dlogits: np.ndarray) -> dict:
        """The optimizer's update of every parameter, then the new MX rows into the live image."""
        self.forward(x)
        grads = self.backward(dlogits)
        moved = self.opt.update(self.p, grads)
        self.p.quantized()
        self.write_params(self.machine.slices[0].dram)
        return {"grads": grads, "moved": moved}

    def train_step(self, x: np.ndarray, targets: np.ndarray, loss_fn=softmax_xent) -> dict:
        """A full supervised step: forward, the host's loss, backward, optimizer."""
        out = self.forward(x)
        loss, dl = loss_fn(out["y"], targets)
        r = self.step(x, dl)
        return {"loss": loss, **r}
