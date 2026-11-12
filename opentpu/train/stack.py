"""A stack of transformer layers trained end to end: a small transformer, not one layer.

`layers.py` trains one layer. A *stack* is the same layer repeated, and the only new thing is
the chaining: layer `i`'s `dX` is layer `i-1`'s incoming gradient, so a backward pass runs from
the last layer to the first, each one's `dX` feeding the one below it. That is the whole
difference, and it is what `docs/train.md` 8 calls the multi-layer rung.

    h0 = x
    h1 = layer0(h0) = norm, attention, residual, MLP, residual
    h2 = layer1(h1)
    ...
    y  = head(hn)             (a linear LM head, [V, d])
    loss = softmax_cross_entropy(y, targets)

    dy = dloss
    dn-1 = layer_n-1.backward(dy) -> its gradients and dx, which is dn-2's incoming gradient
    ...
    d0   = layer_0.backward(d1)  -> the bottom's gradients and dx
    dhead = dy^T @ hn            (the head's own gradient, an OUTER accumulation)

One DRAM image holds the whole stack: each layer carves its own region at an offset, so a step
is *one* Machine and *one* image, not one per layer. That is the cost the staged plan named --
"the DRAM to keep both layers' saved activations" -- and the measured answer is 140.2 KiB a
layer at the test shapes, so a 4-layer stack is 561 KiB against the simulator's 1 MiB.

The head is a trainable matrix `[V, d]` (the model's output vocabulary), and its gradient is the
same rank-1 OUTER accumulation every other matrix uses. The loss stays on the host (docs/train.md
2); a stack does not change the split, it just chains more MMs.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import language as ol
from .. import quant as Q
from ..compiler import Affine, QTensor, Tensor
from ..isasim import Config, Machine
from . import kernels as K
from .layers import GAINS, LAYER_W, LayerParams, layer_ref
from .params import AdamW, quant_w, quant_w_t, softmax_xent

HEAD = "head"          # the LM head's name, as a streamed matrix like the layer's own


def _strides(shape) -> tuple:
    shape = tuple(shape)
    st, out = 1, []
    for n in reversed(shape):
        out.append(st)
        st *= n
    return tuple(reversed(out))


@dataclass
class StackParams:
    """A stack's parameters: `n_layers` transformer layers and one LM head, all trainable.

    Each layer is a `LayerParams` (its seven matrices and two gains); the head is a `[V, d]`
    matrix. `q`/`q_t` hold every streamed operand's MX rows, rebuilt after an optimizer step.
    """

    layers: list                     # [LayerParams]
    head: np.ndarray                 # [V, d]
    fmt: str = "int8"
    D: int = 32
    head_q: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        self.quantized()

    def quantized(self) -> None:
        for lay in self.layers:
            lay.quantized()
        self.head_q = {"head": quant_w(self.head, self.fmt, self.D),
                       "head_t": quant_w_t(self.head, self.fmt, self.D)}

    def named(self) -> dict:
        """Every trainable array, keyed by a name a checkpoint and a gradient can share:
        `layer<i>.Wq`, `layer<i>.g1`, ..., `head`."""
        out = {}
        for i, lay in enumerate(self.layers):
            for n, a in lay.named().items():
                out[f"layer{i}.{n}"] = a
        out["head"] = self.head
        return out

    @staticmethod
    def random(n_layers: int, d_hidden: int, d_ff: int, vocab: int, D: int, seed: int = 0,
               fmt: str = "int8") -> "StackParams":
        rng = np.random.default_rng(seed)
        layers = [LayerParams.random(d_hidden, d_ff, D, seed=seed * 97 + i, fmt=fmt)
                  for i in range(n_layers)]
        head = (rng.standard_normal((vocab, d_hidden)) / np.sqrt(d_hidden)).astype(np.float32)
        return StackParams(layers=layers, head=head, fmt=fmt, D=D)


# ------------------------------------------------------------------------------- the head's kernels
@ol.jit
def head_fwd(h, head, y_o):
    """The LM head: `y = h @ head^T`, a [T, d] tile against the streamed [V, d] matrix."""
    ol.store(y_o, K.linear_fwd(ol.load(h), head))


@ol.jit
def head_bwd(h, dl, head_t, dhead_o, dh_o, T, D_):
    """The head's gradient and the residual stream's: `dhead = dl^T h`, `dh = dl @ head`.

    `dhead` is a rank-1 OUTER accumulation over the batch's rows -- the same instruction pattern
    every weight gradient in this package uses, exact fp32; `dh` is one dX MM against the
    head's transpose.
    """
    hv = ol.load(h)
    dlv = ol.load(dl)
    dh_acc = ol.zeros((dlv.cols, D_))
    for t in range(T):
        dh_acc.set(ol.outer(dlv[t, :], hv[t, :], acc=dh_acc))
    ol.store(dhead_o, dh_acc)
    ol.store(dh_o, K.linear_dx(dlv, head_t))


# ------------------------------------------------------------------------------- the stack's DRAM
@dataclass
class StackLayout:
    """The stack's one DRAM image: a slot for every layer and one for the head.

    A slot is `layers.Layout`'s buffers shifted by the slot's byte offset, so the descriptors a
    layer's programs take address the same buffers at a different base. `nbytes` is the whole
    image; a stack of four test-shaped layers is 561 KiB (docs/train.md 5, 8).
    """

    p: StackParams
    cfg: Config
    T: int
    fmt: str
    base: list = field(default_factory=list)      # each layer's byte offset
    head_at: int = 0
    layer_layouts: list = field(default_factory=list)
    nbytes: int = 0
    # the head's own buffers (bytes for its MX rows, words for the fp32 y/dl/dh)
    head_byte: dict = field(default_factory=dict)
    head_word: dict = field(default_factory=dict)
    head_shape: dict = field(default_factory=dict)

    def t(self, i: int, name: str) -> Tensor:
        """Layer i's fp32 buffer, at its slot's offset."""
        from .layers import Layout as LL
        l: LL = self.layer_layouts[i]
        return l.t(name)

    def q(self, i: int, name: str, n: int, k: int) -> QTensor:
        return self.layer_layouts[i].q(name, n, k)


def stack_layout(p: StackParams, cfg: Config, T: int, fmt: str = "int8") -> StackLayout:
    """Carve the whole stack: a `layers.Layout` per layer, then the head's own regions."""
    from .layers import Layout as LL
    sl = StackLayout(p=p, cfg=cfg, T=T, fmt=fmt)
    pos = 0
    for lay in p.layers:
        l = LL(lay, cfg, T, 1, fmt)
        # shift the layer's addresses by this slot's offset
        base = pos
        sl.base.append(base)
        sl.layer_layouts.append(_shifted(l, base))
        pos = -(-(pos + l.nbytes) // 128) * 128
    d = p.layers[0].Wq.shape[0] if p.layers else cfg.D
    V = p.head.shape[0]
    # (the head's MX strides are quant_w's, not d's: its rows are V long)

    sl.head_at = pos
    q_head = quant_w(p.head, fmt, cfg.D)
    q_head_t = quant_w_t(p.head, fmt, cfg.D)
    sl.head_byte["head_data"] = pos
    pos = -(-(pos + q_head.rows.nbytes) // 128) * 128
    sl.head_byte["head_scale"] = pos
    pos = -(-(pos + q_head.scales.nbytes) // 128) * 128
    sl.head_byte["head_t_data"] = pos
    pos = -(-(pos + q_head_t.rows.nbytes) // 128) * 128
    sl.head_byte["head_t_scale"] = pos
    pos = -(-(pos + q_head_t.scales.nbytes) // 128) * 128
    for name, shp in (("y", (T, V)), ("dl", (T, V)), ("dh", (T, d)), ("dhead", (V, d))):
        pos = -(-pos // 128) * 128
        sl.head_word[name] = pos // 4
        sl.head_shape[name] = shp
        pos = -(-(pos + 4 * int(np.prod(shp))) // 128) * 128
    sl.nbytes = -(-pos // 128) * 128
    return sl


def head_dhead(sl: StackLayout, V: int, d: int) -> Tensor:
    """The head's gradient buffer, [V, d], as the descriptor the head's backward stores into."""
    shp = sl.head_shape["dhead"]
    return Tensor(Affine(4 * sl.head_word["dhead"]), shp, _strides(shp))


def _shifted(l, base: int):
    """A layer's `Layout` with every address moved up by `base` bytes (a slot's offset)."""
    for k in l.byte:
        l.byte[k] += base
    for k in l.word:
        l.word[k] = (4 * l.word[k] + base) // 4
    return l


def head_tensor(sl: StackLayout, name: str) -> Tensor:
    shp = sl.head_shape[name]
    return Tensor(Affine(4 * sl.head_word[name]), shp, _strides(shp))


def head_q(sl: StackLayout, name: str, n: int, k: int) -> QTensor:
    D, fmt = sl.cfg.D, sl.fmt
    return QTensor(Affine(sl.head_byte[name + "_data"]), Affine(sl.head_byte[name + "_scale"]),
                   (int(n), int(k)), Q.row_bytes(k, fmt, D), Q.scale_bytes(k, fmt, D), D,
                   wf=Q.mxu_wf(fmt))


# ------------------------------------------------------------------------------- the trainer
class Stack:
    """A whole stack's training step on one DRAM image: every layer, the head, and AdamW.

    The forward pass runs layer by layer (each layer's `y` is the next one's `x`) and then the
    head; the host's loss gives `dy`; the backward pass runs the head and then the layers in
    reverse, each one's `dx` becoming the next one's `dl`. Every gradient -- nine a layer plus
    the head's -- lands in the image, and one AdamW step moves every matrix.

    A step is `n + 1` forward launches and `n + 1` backward launches: a stack cannot be one
    program, because each layer's backward reads the next layer's `dx`, which a previous launch
    wrote to DRAM. That is the shape the card's real multi-program steps already are
    (`docs/host.md`), and `Machine.load` keeps the DRAM between them.
    """

    def __init__(self, p: StackParams, cfg: Config, T: int, optimizer: AdamW | None = None,
                 eps: float = 1e-6, scale: float | None = None, fmt: str = "int8"):
        from .layers import LayerTrainer
        self.p, self.cfg, self.T = p, cfg, T
        self.opt = optimizer or AdamW()
        self.eps = eps
        self.scale = 1.0 / np.sqrt(cfg.D) if scale is None else scale
        self.fmt = fmt
        self.sl = stack_layout(p, cfg, T, fmt)
        self.d = p.layers[0].Wq.shape[0]
        self.V = p.head.shape[0]
        # a LayerTrainer per layer, its buffers moved into the stack's image at the layer's slot
        self.lts = []
        for lay, base in zip(p.layers, self.sl.base):
            # traced at its slot: the layer's Layout is shifted BEFORE its programs are traced,
            # so the programs and the readbacks address the same buffers
            lt = LayerTrainer(lay, cfg, T=T, optimizer=None, eps=eps, scale=self.scale,
                              fmt=fmt, at=base)
            self.lts.append(lt)
        # the head's programs read the LAST layer's y (its slot in the image)
        self.progs = {"head_fwd": [], "head_bwd": []}
        for s_ in range(cfg.S):
            self.progs["head_fwd"].append(head_fwd.trace(cfg, s_, {
                "h": self.lts[-1].lay.t("y"), "head": head_q(self.sl, "head", self.V, self.d),
                "y_o": head_tensor(self.sl, "y")}).finish())
            self.progs["head_bwd"].append(head_bwd.trace(cfg, s_, {
                "h": self.lts[-1].lay.t("y"), "dl": head_tensor(self.sl, "dl"),
                "head_t": head_q(self.sl, "head_t", self.d, self.V),
                "dhead_o": head_dhead(self.sl, self.V, self.d),
                "dh_o": head_tensor(self.sl, "dh"),
                "T": T, "D_": self.d}).finish())
        self.image = np.zeros(self.sl.nbytes, np.uint8)
        self.machine: Machine | None = None
        self._ensure()
        # the layers' readbacks go through the STACK's Machine (one image, one DRAM)
        for lt in self.lts:
            lt.machine = self.machine

    # ---- the image
    def _ensure(self) -> None:
        if self.machine is not None:
            return
        self.write_all(self.image)
        self.machine = Machine(self.cfg, self.lts[0].progs["forward"], [self.image.copy()])

    def write_all(self, img: np.ndarray) -> None:
        """Every layer's MX rows at its slot, and the head's."""
        for lt in self.lts:
            lt.write_params(img)
        def put(at, data):
            b = np.ascontiguousarray(data).view(np.uint8).reshape(-1)
            img[at:at + b.size] = b
        put(self.sl.head_byte["head_data"], self.p.head_q["head"].rows)
        put(self.sl.head_byte["head_scale"], self.p.head_q["head"].scales)
        put(self.sl.head_byte["head_t_data"], self.p.head_q["head_t"].rows)
        put(self.sl.head_byte["head_t_scale"], self.p.head_q["head_t"].scales)

    # ---- the launches
    def _run(self, progs) -> None:
        self.machine.load(progs).run()

    def _dram(self) -> np.ndarray:
        return self.machine.slices[0].dram

    def forward(self, x: np.ndarray) -> np.ndarray:
        """Layer by layer, then the head: returns the logits [T, V]."""
        h = np.asarray(x, np.float32)
        for lt in self.lts:
            lt._write("x", h)
            self._run(lt.progs["forward"])
            h = lt._buffer("y").copy()
        # the last layer's y is already in its slot, which the head's program reads
        self._run(self.progs["head_fwd"])
        return self._buffer_head("y")

    def backward(self, dlogits: np.ndarray) -> dict:
        """The head's gradient, then the layers in reverse; returns every gradient."""
        self._write_head("dl", np.asarray(dlogits, np.float32))
        self._run(self.progs["head_bwd"])
        grads = {"head": self._buffer_head("dhead").copy()}
        # (a copy each time: the buffers are views into DRAM, and the next launch overwrites them)
        dh = self._buffer_head("dh").copy()
        for i in reversed(range(len(self.lts))):
            self.lts[i]._write("dl", dh)
            self._run(self.lts[i].progs["backward"])
            for name in LAYER_W:
                grads[f"layer{i}.{name}"] = self.lts[i]._buffer("d" + name).copy()
            for name in GAINS:
                grads[f"layer{i}.{name}"] = self.lts[i]._buffer("d" + name).copy()
            dh = self.lts[i]._buffer("dx").copy()
        return grads

    def step(self, x: np.ndarray, dlogits: np.ndarray) -> dict:
        """The optimizer over every matrix, then all the MX rows back into the live image."""
        self.forward(x)
        grads = self.backward(dlogits)
        moved = self.opt.update(_S(self.p), grads)
        self.p.quantized()
        self.write_all(self._dram())
        return {"grads": grads, "moved": moved}

    def train_step(self, x: np.ndarray, targets: np.ndarray, loss_fn=softmax_xent) -> dict:
        """A full supervised step: forward, the host's loss, backward, optimizer."""
        logits = self.forward(x)
        loss, dl = loss_fn(logits, targets)
        r = self.step(x, dl)
        return {"loss": loss, **r}

    def _buffer_head(self, name: str) -> np.ndarray:
        shp = self.sl.head_shape[name]
        off = 4 * self.sl.head_word[name]
        return self._dram()[off:off + 4 * int(np.prod(shp))].view(np.float32).reshape(shp)

    def _write_head(self, name: str, data: np.ndarray) -> None:
        off = 4 * self.sl.head_word[name]
        b = np.ascontiguousarray(data, np.float32).view(np.uint8).reshape(-1)
        self._dram()[off:off + b.size] = b


class _S:
    """`StackParams` as the object AdamW updates (it wants `named()` and `quantized()`)."""

    def __init__(self, p: StackParams):
        self.p = p

    def named(self) -> dict:
        return self.p.named()

    def quantized(self) -> None:
        self.p.quantized()



