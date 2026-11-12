"""The training loop: one step is two launches, with the host's loss between them.

A step is two programs (docs/train.md 2, 6):

    forward   the batch as one [B, H] tile: the norm, the SwiGLU block's two matmuls and their
              product, the down matmul and the residual, the head's MM. The activations the
              backward pass needs and the logits go to the step's DRAM.
    backward  the same tile shapes: the head's gradient, three dX matmuls, the SwiGLU backward,
              the norm backward, and every weight gradient accumulated with a VOP OUTER pass.

Between them the host runs `params.softmax_xent` on the forward's logits and writes the logits'
gradient back into DRAM. The optimizer (`params.AdamW`) runs after the backward on the fp32
master copies and re-quantizes the weights, and the next step's image starts from that.

Why the batch is one big tile: an MM with M = B rows streams each weight chunk once for all the
rows (the MXU's replay, docs/isa.md "MM"), so the forward and the three dX matmuls make one pass
over the weights each. The weight gradients are rank-1 OUTER passes -- one a row, because OUTER
takes 1-D vectors -- so those are a Python loop the tracer unrolls: B instructions a matrix. That
is why `Shapes.batch` stays small: the unrolled accumulators are program instructions, and IMEM
on the card holds 4,096 of them.

The kernels are `ol.jit` kernels taking the DRAM descriptors a step's `Layout` makes. `Trainer.step`
implements one program's trace and one full step; `Trainer.run` repeats it, keeping the Machine's
DRAM across steps (`isasim.Machine.load` keeps it, as the card keeps it between runs).

Measured on the ISA simulator with the default shapes (H = F = V = 32, B = 4, D = 32): the
forward and backward pass' gradients against a float64 reference are within 0.8% (the head's
gradient) to 3.0% (the norm's gain) -- the int8 operands' noise -- and a 25-step AdamW run takes
a cross-entropy loss from 3.68 to 0.0000 (tests/test_train.py).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import language as ol
from .. import quant as Q
from ..compiler import Affine, CompileError, QTensor, Tensor
from ..isasim import Config, Machine
from . import kernels as K
from .params import AdamW, Params, Shapes, softmax_xent

# the fp32 buffers of a step: name -> the Shapes field that gives its columns
ACT = {"x": "hidden", "xn": "hidden", "y": "hidden", "g": "interm", "u": "interm",
       "a": "interm", "logits": "vocab", "dlogits": "vocab"}
# the gradients, in the master copies' shapes: name -> the Shapes fields
GRAD = {"d_gate": ("interm", "hidden"), "d_up": ("interm", "hidden"),
        "d_down": ("hidden", "interm"), "d_head": ("vocab", "hidden"),
        "d_gamma": ("hidden",), "dx": ("batch", "hidden")}
# the matrices a forward pass streams; the backward streams their transposes
FWD_W = ("w_gate", "w_up", "w_down", "head")
BWD_W = ("w_gate_t", "w_up_t", "w_down_t", "head_t")
# the gradient buffer a weight's gradient lands in (the head's is d_head, the norm's d_gamma)
GRAD_OF = {"w_gate": "d_gate", "w_up": "d_up", "w_down": "d_down", "head": "d_head"}


def _align(n: int, a: int = 128) -> int:
    """Round up: 128 bytes keeps every DMA and MM operand aligned (the design's D <= 128)."""
    return (n + a - 1) // a * a


def _strides(shape) -> tuple:
    """Row-major element strides of a shape."""
    shape = tuple(shape)
    st, out = 1, []
    for n in reversed(shape):
        out.append(st)
        st *= n
    return tuple(reversed(out))


def matrix_shapes(shapes: Shapes) -> dict:
    """The streamed matrices in this model's shapes, (N, K) for `y = x @ W^T`."""
    H, F, V = shapes.hidden, shapes.interm, shapes.vocab
    return {"w_gate": (F, H), "w_up": (F, H), "w_down": (H, F), "head": (V, H)}


def act_shape(shapes: Shapes, name: str) -> tuple:
    """A fp32 activation buffer's shape, [B, cols]."""
    return (shapes.batch, getattr(shapes, ACT[name]))


def grad_shape(shapes: Shapes, name: str) -> tuple:
    """A gradient buffer's shape: the master copy's (gamma's is a vector)."""
    return tuple(getattr(shapes, d) for d in GRAD[name])


# ------------------------------------------------------------------------------------- layout
@dataclass
class Layout:
    """A step's DRAM. `byte` holds the streamed MX operands' addresses, `word` the fp32 buffers'
    words; one array holds both, the regions disjoint on 128-byte boundaries. `nbytes` is the
    image's size. `t(name)` / `q(name, n, k)` make the descriptors the kernels take as arguments.
    """

    shapes: Shapes
    cfg: Config
    fmt: str = "int8"
    byte: dict = field(default_factory=dict)
    word: dict = field(default_factory=dict)
    shape: dict = field(default_factory=dict)      # a fp32 buffer's shape
    pos: int = 0

    def cb(self, name: str, nbytes: int) -> None:
        self.pos = _align(self.pos)
        self.byte[name] = self.pos
        self.pos = _align(self.pos + nbytes)

    def cw(self, name: str, shape) -> None:
        shape = tuple(shape)
        self.pos = _align(self.pos)
        self.word[name] = self.pos // 4
        self.shape[name] = shape
        self.pos = _align(self.pos + 4 * int(np.prod(shape)))

    @property
    def nbytes(self) -> int:
        return _align(self.pos)

    def t(self, name: str) -> Tensor:
        """A fp32 buffer's descriptor."""
        s = self.shape[name]
        return Tensor(Affine(4 * self.word[name]), s, _strides(s))

    def q(self, name: str, n: int, k: int) -> QTensor:
        """A matrix's MX rows as the MM streams them: [n, k] with the format's strides."""
        D = self.cfg.D
        return QTensor(Affine(self.byte[name + "_data"]), Affine(self.byte[name + "_scale"]),
                       (int(n), int(k)), Q.row_bytes(k, self.fmt, D),
                       Q.scale_bytes(k, self.fmt, D), D, wf=Q.mxu_wf(self.fmt))

    def q_t(self, name: str, n: int, k: int) -> QTensor:
        """A matrix's *transpose* as the backward pass streams it: [n, k], its own MX rows."""
        return self.q(name + "_t", n, k)


def layout(shapes: Shapes, cfg: Config, fmt: str = "int8") -> Layout:
    """Carve a step's DRAM: the streamed matrices (and their transposes), the activations, gamma,
    the one-hot rows and the gradients. docs/train.md 5 has the budget this adds up to."""
    shapes.check(cfg)
    lay = Layout(shapes, cfg, fmt)
    for name, (n, k) in matrix_shapes(shapes).items():
        lay.cb(name + "_data", n * Q.row_bytes(k, fmt, cfg.D))
        lay.cb(name + "_scale", n * Q.scale_bytes(k, fmt, cfg.D))
    for name, (n, k) in matrix_shapes(shapes).items():
        lay.cb(name + "_t_data", k * Q.row_bytes(n, fmt, cfg.D))     # the transpose: [k, n]
        lay.cb(name + "_t_scale", k * Q.scale_bytes(n, fmt, cfg.D))
    for name in ACT:
        lay.cw(name, act_shape(shapes, name))
    lay.cw("gamma", (shapes.hidden,))
    for name in GRAD:
        lay.cw(name, grad_shape(shapes, name))
    return lay


def image(lay: Layout, params: Params, x: np.ndarray | None = None) -> np.ndarray:
    """A step's fresh DRAM image: the streamed matrices' MX bytes at their addresses, gamma and
    the batch's `x` where the kernels read them (zeros elsewhere)."""
    img = np.zeros(lay.nbytes, np.uint8)
    write_weights(img, lay, params)
    if x is not None:
        _put(img, 4 * lay.word["x"], np.asarray(x, np.float32))
    return img


def write_weights(img: np.ndarray, lay: Layout, params: Params) -> None:
    """Rewrite a DRAM image's streamed matrices from the master copies (after an optimizer step;
    the activations and gradients are left alone -- the next forward overwrites what it reads
    first)."""
    for name in FWD_W:
        q = params.q[name]
        _put(img, lay.byte[name + "_data"], q.rows)
        _put(img, lay.byte[name + "_scale"], q.scales)
    for name in BWD_W:
        q = params.q_t[name.removesuffix("_t")]
        _put(img, lay.byte[name + "_data"], q.rows)
        _put(img, lay.byte[name + "_scale"], q.scales)
    _put(img, 4 * lay.word["gamma"], params.gamma)


def _put(img: np.ndarray, at: int, data: np.ndarray) -> None:
    b = np.ascontiguousarray(data).view(np.uint8).reshape(-1)
    img[at:at + b.size] = b


# ----------------------------------------------------------------------------------- the kernels
@ol.jit
def train_fwd(x, gamma, w_gate, w_up, w_down, head, xn_o, g_o, u_o, a_o, y_o, lg_o, eps):
    """The forward pass of one batch tile: the norm, the SwiGLU block, the head.

    The activations the backward pass needs are stored (`xn_o`, `g_o`, `u_o`, `a_o`, `y_o`), and
    the logits with them (`lg_o`). eps is the norm's epsilon, a compile-time constant.
    """
    xv = ol.load(x)                                     # [B, H]
    xn, r = K.rmsnorm_fwd(xv, ol.load(gamma), eps)       # [B, H]
    ol.store(xn_o, xn)
    g = K.linear_fwd(xn, w_gate)                          # [B, F]
    ol.store(g_o, g)
    u = K.linear_fwd(xn, w_up)                           # [B, F]
    ol.store(u_o, u)
    a, sg = K.swiglu_act_fwd(g, u)                       # [B, F]
    ol.store(a_o, a)
    y = K.linear_fwd(a, w_down) + xv                     # [B, H], the residual
    ol.store(y_o, y)
    ol.store(lg_o, K.linear_fwd(y, head))                # [B, V]


@ol.jit
def train_bwd(x, gamma, xn_i, g_i, u_i, a_i, y_i, dl_i, head_t, w_down_t, w_gate_t, w_up_t,
              dx_o, d_head_o, d_gate_o, d_up_o, d_down_o, d_gamma_o, eps):
    """The backward pass of one batch tile: every gradient of the forward pass above.

    The three dX matmuls (`dY`, `dA`, `dXN`) each stream a transposed weight, so each is one MM
    over the whole batch tile. The weight gradients are OUTER accumulations over the batch's rows
    (exact fp32, docs/isa.md VOP OUTER), which is also how the norm's gain accumulates its own --
    a sum over rows, which the VOP reductions do not do.
    """
    xv = ol.load(x)
    xn = ol.load(xn_i)
    g = ol.load(g_i)
    u = ol.load(u_i)
    a = ol.load(a_i)
    y = ol.load(y_i)
    dl = ol.load(dl_i)
    gv = ol.load(gamma)
    B = xn.rows
    H = xn.cols
    # d_head = sum_b dlogits[b][:, None] * y[b][None, :], OUTER passes over the batch
    dh = ol.zeros((dl.cols, H))
    for b in range(B):
        dh.set(ol.outer(dl[b, :], y[b, :], acc=dh))
    ol.store(d_head_o, dh)
    # the dX matmuls: dY = dlogits @ head, dA = dY @ w_down, dXN = dG @ w_gate + dU @ w_up
    dy = K.linear_dx(dl, head_t)
    da = K.linear_dx(dy, w_down_t)
    sg = K._sigmoid(g)
    dg, du = K.swiglu_bwd(da, g, u, sg)
    dxn = K.linear_dx(dg, w_gate_t) + K.linear_dx(du, w_up_t)
    # the norm's backward (K.rmsnorm_bwd holds the formula and its traps) and the residual's
    dnorm, xh = K.rmsnorm_bwd(dxn, xv, ol.rsqrt(ol.sumsq(xv) * (1.0 / H) + eps), gv)
    # the weight gradients, one OUTER pass a row, plus the gain's
    # the accumulators have the master copies' shapes (the transposed operands' are swapped)
    F = a.cols                                       # (the MLP's inner width, from a's columns)
    dwg = ol.zeros((F, H))                           # [F, H], d_gate
    dwu = ol.zeros((F, H))                           # [F, H], d_up
    dwd = ol.zeros((H, a.cols))                      # [H, F], d_down
    dgam = ol.zeros((H,))
    for b in range(B):
        dwg.set(ol.outer(dg[b, :], xn[b, :], acc=dwg))
        dwu.set(ol.outer(du[b, :], xn[b, :], acc=dwu))
        dwd.set(ol.outer(dy[b, :], a[b, :], acc=dwd))
        dgam.set(K.gain_accum(dgam, dxn[b, :], xh[b, :]))
    ol.store(dx_o, dnorm + dy)
    ol.store(d_gate_o, dwg)
    ol.store(d_up_o, dwu)
    ol.store(d_down_o, dwd)
    ol.store(d_gamma_o, dgam)


# --------------------------------------------------------------------------------- the trainer
@dataclass
class Trainer:
    """A step's model, optimizer and DRAM: `train_step` runs one update, `run` repeats it.

    `train_step` traces the two programs once (a step's programs depend only on the shapes and the
    format, not on the weights: the weights are DRAM the image carries) and runs them on the
    backend. The gradients the backward pass left in DRAM go straight to the optimizer, and
    `write_weights` puts the updated matrices back into the image for the next step.
    """

    shapes: Shapes = field(default_factory=Shapes)
    cfg: Config = field(default_factory=Config)
    params: Params | None = None
    optimizer: AdamW = field(default_factory=AdamW)
    fmt: str = "int8"
    eps: float = 1e-6
    backend: str = "isa"
    seed: int = 0
    # built by __post_init__
    lay: Layout = None
    progs: dict = field(default_factory=dict)     # "forward" -> per-slice programs
    image: np.ndarray | None = None
    machine: Machine | None = None

    def __post_init__(self):
        self.shapes.check(self.cfg)
        if self.params is None:
            self.params = Params.random(self.shapes, self.seed)
        if self.lay is None:
            self.lay = layout(self.shapes, self.cfg, self.fmt)
        self._trace()
        self.image = image(self.lay, self.params)

    def _trace(self) -> None:
        """Trace the two programs, one per slice, against this layout's descriptors."""
        lay, cfg, shp = self.lay, self.cfg, self.shapes
        H, F, V = shp.hidden, shp.interm, shp.vocab
        self.progs = {"forward": [], "backward": []}
        for s in range(cfg.S):
            self.progs["forward"].append(
                train_fwd.trace(cfg, s, {
                    "x": lay.t("x"), "gamma": lay.t("gamma"),
                    "w_gate": lay.q("w_gate", F, H), "w_up": lay.q("w_up", F, H),
                    "w_down": lay.q("w_down", H, F), "head": lay.q("head", V, H),
                    "xn_o": lay.t("xn"), "g_o": lay.t("g"), "u_o": lay.t("u"),
                    "a_o": lay.t("a"), "y_o": lay.t("y"), "lg_o": lay.t("logits"),
                    "eps": self.eps}).finish())
            self.progs["backward"].append(
                train_bwd.trace(cfg, s, {
                    "x": lay.t("x"), "gamma": lay.t("gamma"),
                    "xn_i": lay.t("xn"), "g_i": lay.t("g"), "u_i": lay.t("u"),
                    "a_i": lay.t("a"), "y_i": lay.t("y"), "dl_i": lay.t("dlogits"),
                    "head_t": lay.q_t("head", H, V),
                    "w_down_t": lay.q_t("w_down", F, H),
                    "w_gate_t": lay.q_t("w_gate", H, F),
                    "w_up_t": lay.q_t("w_up", H, F),
                    "dx_o": lay.t("dx"), "d_head_o": lay.t("d_head"),
                    "d_gate_o": lay.t("d_gate"),
                    "d_up_o": lay.t("d_up"), "d_down_o": lay.t("d_down"),
                    "d_gamma_o": lay.t("d_gamma"),
                    "eps": self.eps}).finish())
        self._fit()

    def _fit(self) -> None:
        """Refuse programs that do not fit the configuration's IMEM, naming the batch's cost."""
        words = 8 * max(len(p) for ps in self.progs.values() for p in ps)
        if words > self.cfg.IMEM_WORDS:
            raise CompileError(
                f"the step's programs are {words} words of IMEM ({self.cfg.IMEM_WORDS}): a "
                f"batch of {self.shapes.batch} unrolls {self.shapes.batch} OUTER passes a "
                f"gradient; use a smaller Shapes.batch or a larger row group")

    # ---- the DRAM readback the host does between the launches
    def _buffer(self, name: str) -> np.ndarray:
        """A fp32 buffer of the current image, read back as its shape."""
        shp = self.lay.shape[name]
        off = 4 * self.lay.word[name]
        n = int(np.prod(shp))
        return self._dram()[off:off + 4 * n].view(np.float32).reshape(shp)

    def _write(self, name: str, data: np.ndarray) -> None:
        """Write a fp32 buffer into the live DRAM (the host's loss's gradient goes this way)."""
        off = 4 * self.lay.word[name]
        b = np.ascontiguousarray(data, np.float32).view(np.uint8).reshape(-1)
        self._dram()[off:off + b.size] = b

    def gradients(self) -> dict:
        """The gradients the last backward pass left in DRAM, in the master copies' names."""
        grads = {name: self._buffer(buf).copy() for name, buf in GRAD_OF.items()}
        grads["gamma"] = self._buffer("d_gamma").copy()
        return grads

    # ---- the two launches, on whichever backend
    def _run(self, which: str) -> None:
        """Run one of the step's two programs, leaving its DRAM where the next readback or the
        next program finds it.

        The ISA simulator keeps DRAM across `Machine.load`; the RTL model and the card each
        build/load a fresh machine per launch and hand their DRAM images back, so the step carries
        the byte array between launches instead (`SimBackend`, `BoardBackend`).
        """
        progs = self.progs[which]
        if self.machine is not None:                       # (the ISA simulator, kept across)
            self.machine.load(progs).run()
            return
        from .. import rtlsim
        if self.backend == "rtl":
            images = [self.image.copy() for _ in range(self.cfg.S)]
            drams, _, _ = rtlsim.run(self.cfg, progs, images)
            self.image = drams[0]
            return
        raise NotImplementedError(f"backend {self.backend!r}: the ISA simulator and the RTL "
                                  f"model are wired; a card run needs `Board`'s protocol")

    def _dram(self) -> np.ndarray:
        """This step's DRAM byte array, wherever the last launch left it."""
        if self.machine is not None:
            return self.machine.slices[0].dram
        return self.image

    # ---- a step
    def step(self, x: np.ndarray, targets: np.ndarray, loss_fn=softmax_xent) -> dict:
        """One training step on the batch `x` [B, H] and its `targets` [B].

        Runs the forward pass, the host's loss, the backward pass and the optimizer; returns
        {"loss", "grads", "moved"}. The DRAM the Machine holds carries the forward's activations
        to the backward pass (the host writes only the loss's gradient), and the optimizer
        rewrites the matrices into it for the next step.
        """
        if not isinstance(self.optimizer, AdamW):
            raise TypeError("optimizer must be a train_opt:AdamW")
        # the backward pass reads what the forward pass wrote, so the step's DRAM has to survive
        # between the two launches: the ISA simulator's Machine does that itself, the others'
        # images are carried here
        if self.image is None:
            self.image = image(self.lay, self.params, np.zeros((self.shapes.batch,
                                                               self.shapes.hidden),
                                                              np.float32))
        if self.backend == "isa" and self.machine is None:
            self.machine = Machine(self.cfg, [self.progs["forward"][0]],
                                   [self.image.copy()])
        if self.machine is not None:
            self.image = self.machine.slices[0].dram
        self._write("x", np.asarray(x, np.float32))
        self._run("forward")
        logits = self._buffer("logits").copy()
        loss, dlogits = loss_fn(logits, targets)
        self._write("dlogits", dlogits)
        self._run("backward")
        grads = self.gradients()
        moved = self.optimizer.update(self.params, grads)
        write_weights(self._dram(), self.lay, self.params)
        return {"loss": loss, "grads": grads, "moved": moved}

    def run(self, xs: np.ndarray, targets: np.ndarray, steps: int | None = None,
            loss_fn=softmax_xent) -> list:
        """Repeated steps over a fixed batch (`steps` defaults to every epoch's pass over `xs`
        once: one step is one batch). Returns the per-step {"loss", "grads", "moved"} dicts."""
        n = steps or 1
        return [self.step(xs, targets, loss_fn) for _ in range(n)]
