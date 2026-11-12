"""LoRA fine-tuning on openTPU: a frozen weight plus two trainable adapters.

This is docs/train.md 8's rung 4, and it is the shape the quantized-training projects converge
on: the base weight is frozen and quantized (one int8/4-bit copy, the same one inference
streams), and two small matrices around it are what the optimizer moves.

    y = x @ W^T + scale * (x @ A^T) @ B^T          W frozen [N, K]

    A [r, K] and B [N, r], r the adapter's rank -- small enough that the two gradient
    accumulations, which are the expensive part of a step on this machine, are the cheap ones.

Why this is the cheap rung: a frozen layer's backward costs *two* gradients of `[r, K]` and
`[N, r]` elements instead of one of `[N, K]`, and the OUTER passes that produce them are
`r x K + N x r` multiplications a row instead of `N x K`. The base `dX` still needs its MM
through `W` (the layer below has to see the gradient), but a layer that *feeds* nothing needs
only `dy @ B` and `dy @ W`.

The rank is a reduction dim of the second MM (`docs/isa.md` "Weight formats": the MXU streams
whole `D`-byte chunks), so the host pads `r` to a whole `D`-block and the padded rows carry
zeros: `A`'s rows and `B`'s columns past the real rank are 0, so they contribute nothing to
either the forward or the gradients.

QLoRA is the same layer with the frozen base in a *4-bit* format (`base_fmt`, one of
`fp4`/`nvfp4`/`int4`) and the adapters in int8: the base streams at 4.25-4.5 bits a weight
instead of 8.25 (`docs/quant.md` has the formats' costs), which is what lets a bigger base fit
the same image. The two are separate streamed operands over separate DRAM regions, so the MM
reads each at its own stride and there is no layout conflict; the adapters stay int8 because
`QST` -- the device's own quantizer -- writes int8 only (`docs/train.md` 4), so a gradient the
device produces can only be streamed back in int8.

The host owns what it owns everywhere else (docs/train.md 6): the fp32 master copies of `A`
and `B`, AdamW over them, the re-quantization of the two adapters into the image, and the loss.
The frozen weight is quantized once and never written again, which is the whole point of the
frozen-base design.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .. import language as ol
from .. import quant as Q
from ..compiler import Affine, QTensor, Tensor
from ..isasim import Config, Machine
from . import kernels as K
from .params import AdamW, quant_w, quant_w_t, softmax_xent


def pad_rank(rank: int, D: int) -> int:
    """The rank's padded width: whole D-blocks, because the rank is an MM's reduction dim."""
    if rank < 1:
        raise ValueError(f"LoRA rank {rank}: a rank is at least 1")
    return -(-rank // D) * D


def check_rank(rank: int, kdim: int, n: int, D: int) -> int:
    """The padded rank, refusing a rank Lora cannot express: `A` is `[r, K]` and `B` is `[N, r]`,
    and the low-rank term is `[B, N]`, so the padded rank must not exceed the layer's own widths
    (a rank above `N` would make the product `[B, r]` and the residual add a shape mismatch).
    """
    rp = pad_rank(rank, D)
    for name, dim in (("K", kdim), ("N", n)):
        if rp > dim:
            raise ValueError(f"LoRA rank {rank} padded to {rp} exceeds the layer's {name} = {dim}"
                             f": the adapter's rank is a reduction dim, and the padded width has "
                             f"to fit inside both of the layer's dimensions")
    return rp


@dataclass
class Adapters:
    """The two trainable matrices of a LoRA layer, as fp32 master copies, with their MX forms.

    `a` is [r, K] (the down projection) and `b` is [N, r] (the up projection), `r` padded to a
    D-block (`pad_rank`) with the padding rows/columns at zero. The quantized forms the MM
    streams are rebuilt after every optimizer step, and their transposes -- which the backward
    pass's dX and dA MMs stream -- are kept beside them (`quant_w_t`).
    """

    a: np.ndarray            # [r, K]
    b: np.ndarray            # [N, r]
    fmt: str = "int8"
    D: int = 32
    q: dict = field(default_factory=dict, repr=False)
    q_t: dict = field(default_factory=dict, repr=False)

    def __post_init__(self):
        rp = self.a.shape[0]
        if rp > self.b.shape[0]:
            raise ValueError(f"Adapters: the padded rank {rp} exceeds N = {self.b.shape[0]}: a "
                             f"rank above the layer's output width is not a low-rank adapter "
                             f"(lora.check_rank says which dimension refused it)")
        self.quantized()

    def quantized(self) -> None:
        self.q = {"a": quant_w(self.a, self.fmt, self.D), "b": quant_w(self.b, self.fmt, self.D)}
        self.q_t = {"a": quant_w_t(self.a, self.fmt, self.D),
                    "b": quant_w_t(self.b, self.fmt, self.D)}

    def named(self) -> dict:
        return {"a": self.a, "b": self.b}

    @staticmethod
    def random(rank: int, kdim: int, n: int, D: int, seed: int = 0,
               fmt: str = "int8") -> "Adapters":
        """LoRA's standard initialization: A gets the base init's scale, B starts at zero, so the
        adapted layer begins exactly as the frozen one does (a fine-tune that starts by perturbing
        the base is a different experiment)."""
        rp = check_rank(rank, kdim, n, D)
        rng = np.random.default_rng(seed)
        a = np.zeros((rp, kdim), np.float32)
        a[:rank] = (rng.standard_normal((rank, kdim)) / np.sqrt(kdim)).astype(np.float32)
        b = np.zeros((n, rp), np.float32)          # zero: the adapter is a no-op at step 0
        return Adapters(a, b, fmt, D)


@dataclass
class LoRA:
    """One LoRA-adapted linear layer, trained on the device: the frozen weight, the adapters,
    the optimizer and the step's two programs.

    The step is `Trainer`'s shape (docs/train.md 2): a forward program (`y` and the bottleneck
    `h`), the host's loss and its gradient `dy`, and a backward program that produces the
    adapters' gradients and (optionally) `dX`. The frozen weight is in the image as its MX rows
    and its transpose, exactly as the inference kernels would carry it.
    """

    w: np.ndarray                  # the frozen base [N, K], fp32 (only its MX form is streamed)
    adapters: Adapters
    base_fmt: str = "int8"         # QLoRA: the frozen base in a 4-bit format ("fp4"/"nvfp4"), the
                                   # adapters in int8 -- the two are separate streamed operands
    cfg: Config = field(default_factory=Config)
    optimizer: AdamW = field(default_factory=AdamW)
    batch: int = 4
    scale: float = 1.0
    seed: int = 0
    # the step's DRAM and programs
    byte: dict = field(default_factory=dict)
    word: dict = field(default_factory=dict)
    shape: dict = field(default_factory=dict)
    image: np.ndarray | None = None
    progs: dict = field(default_factory=dict)
    machine: Machine | None = None
    pos: int = 0

    # ---- the layout
    def _carve(self) -> None:
        """The step's DRAM: the frozen weight's rows and transpose, the adapters' rows and
        transposes, the batch's fp32 buffers and the adapters' gradients."""
        N, KD = self.w.shape            # the frozen base [N, K]
        N2, R = self.adapters.b.shape   # b is [N, rp]: N2 is the layer's output width, R the rank
        R = self.adapters.a.shape[0]    # a is [rp, K]
        D, fmt = self.cfg.D, self.adapters.fmt
        B = self.batch

        def cb(name: str, n: int) -> None:
            self.pos = -(-self.pos // 128) * 128
            self.byte[name] = self.pos
            self.pos = -(-(self.pos + n) // 128) * 128

        def cw(name: str, shp) -> None:
            self.pos = -(-self.pos // 128) * 128
            self.word[name] = self.pos // 4
            self.shape[name] = tuple(shp)
            self.pos = -(-(self.pos + 4 * int(np.prod(shp))) // 128) * 128

        for name, (n, k), f in (("w", (N, KD), self.base_fmt), ("w_t", (KD, N), self.base_fmt),
                                ("a", (R, KD), fmt), ("a_t", (KD, R), fmt),
                                ("b", (N2, R), fmt), ("b_t", (R, N2), fmt)):
            cb(name + "_data", n * Q.row_bytes(k, f, D))
            cb(name + "_scale", n * Q.scale_bytes(k, f, D))
        for name, shp in (("x", (B, KD)), ("dy", (B, N2)), ("y", (B, N2)), ("h", (B, R)),
                          ("dA", (R, KD)), ("dB", (N2, R)), ("dX", (B, KD))):
            cw(name, shp)

    @property
    def nbytes(self) -> int:
        return -(-self.pos // 128) * 128

    def t(self, name: str) -> Tensor:
        s = self.shape[name]
        st, out = 1, []
        for n in reversed(s):
            out.append(st)
            st *= n
        return Tensor(Affine(4 * self.word[name]), s, tuple(reversed(out)))

    def q(self, name: str, n: int, k: int) -> QTensor:
        """A streamed operand's MX rows. The frozen base's format is `base_fmt` (QLoRA puts it in
        a 4-bit format); the adapters' is theirs. The two are separate QTensors over separate
        DRAM regions, which is why the MM reads each at its own stride."""
        D = self.cfg.D
        fmt = self.base_fmt if name in ("w", "w_t") else self.adapters.fmt
        return QTensor(Affine(self.byte[name + "_data"]), Affine(self.byte[name + "_scale"]),
                       (int(n), int(k)), Q.row_bytes(k, fmt, D), Q.scale_bytes(k, fmt, D), D,
                       wf=Q.mxu_wf(fmt))

    def _put(self, img: np.ndarray, at: int, data: np.ndarray) -> None:
        b = np.ascontiguousarray(data).view(np.uint8).reshape(-1)
        img[at:at + b.size] = b

    def build_image(self) -> np.ndarray:
        """The step's DRAM image: the frozen weight and both adapters in their MX rows."""
        self._carve()
        img = np.zeros(self.nbytes, np.uint8)
        self.write_adapter(img)
        wq, wt = quant_w(self.w, self.base_fmt, self.cfg.D), \
            quant_w_t(self.w, self.base_fmt, self.cfg.D)
        for name, q in (("w", wq), ("w_t", wt)):
            self._put(img, self.byte[name + "_data"], q.rows)
            self._put(img, self.byte[name + "_scale"], q.scales)
        return img

    def write_adapter(self, img: np.ndarray) -> None:
        """Rewrite the two adapters' MX rows -- and their transposes, which the backward pass
        streams -- in a live image after an optimizer step. The frozen weight is never touched.
        """
        for name, qt_name, base in (("a", "a_t", "a"), ("b", "b_t", "b")):
            q = self.adapters.q[base]
            self._put(img, self.byte[name + "_data"], q.rows)
            self._put(img, self.byte[name + "_scale"], q.scales)
            qt = self.adapters.q_t[base]
            self._put(img, self.byte[qt_name + "_data"], qt.rows)
            self._put(img, self.byte[qt_name + "_scale"], qt.scales)

    # ---- the programs
    def compile(self) -> None:
        self.image = self.build_image()
        N, KD = self.w.shape            # the frozen base [N, K]
        N2, R = self.adapters.b.shape   # b is [N, rp]: N2 is the layer's output width, R the rank
        R = self.adapters.a.shape[0]    # a is [rp, K]
        B = self.batch
        self.progs = {"forward": [], "backward": []}
        for s in range(self.cfg.S):
            self.progs["forward"].append(_lora_fwd_prog.trace(self.cfg, s, {
                "x": self.t("x"), "w": self.q("w", N, KD),
                "a": self.q("a", R, KD), "b": self.q("b", N2, R),
                "y_o": self.t("y"), "h_o": self.t("h"), "scale": self.scale,
                "B": B, "R": R}).finish())
            self.progs["backward"].append(_lora_bwd_prog.trace(self.cfg, s, {
                "x": self.t("x"), "dy": self.t("dy"), "h": self.t("h"),
                "a_t": self.q("a_t", KD, R), "b_t": self.q("b_t", R, N2),
                "w_t": self.q("w_t", KD, N),
                "dA_o": self.t("dA"), "dB_o": self.t("dB"), "dX_o": self.t("dX"),
                "scale": self.scale, "B": B, "R": R, "KD": KD, "N": N2}).finish())

    def _dram(self) -> np.ndarray:
        if self.machine is not None:
            return self.machine.slices[0].dram
        return self.image

    def _buffer(self, name: str) -> np.ndarray:
        shp = self.shape[name]
        off = 4 * self.word[name]
        return self._dram()[off:off + 4 * int(np.prod(shp))].view(np.float32).reshape(shp)

    def _write(self, name: str, data: np.ndarray) -> None:
        off = 4 * self.word[name]
        b = np.ascontiguousarray(data, np.float32).view(np.uint8).reshape(-1)
        self._dram()[off:off + b.size] = b

    def forward(self, x: np.ndarray) -> np.ndarray:
        """The adapted layer's output for a batch: `y = x @ W^T + scale * (h @ B^T)`."""
        self._ensure_machine()
        self._write("x", np.asarray(x, np.float32))
        self.machine.load(self.progs["forward"]).run()
        return self._buffer("y").copy()

    def backward(self, dy: np.ndarray) -> dict:
        """The adapters' gradients and `dX` for the incoming gradient `dy` of the layer's output.

        Returns {"a", "b", "dx"}: the two master-copy-shaped gradients and the input's gradient.
        """
        self._ensure_machine()
        self._write("dy", np.asarray(dy, np.float32))
        self.machine.load(self.progs["backward"]).run()
        return {"a": self._buffer("dA").copy(), "b": self._buffer("dB").copy(),
                "dx": self._buffer("dX").copy()}

    def step(self, grads: dict) -> dict:
        """Apply the optimizer to the adapters' gradients and rewrite them into the live image."""
        self._ensure_machine()
        moved = self.optimizer.update(_P(self.adapters), grads)
        self.adapters.quantized()
        self.write_adapter(self.machine.slices[0].dram)
        return {"moved": moved}

    def train_step(self, x: np.ndarray, targets: np.ndarray, loss_fn=softmax_xent) -> dict:
        """A full step on a batch: forward, the host's loss and its `dy`, backward, optimizer.

        The loss is the host's (docs/train.md 2: a row group's exponentiation), so this takes
        `targets` and `loss_fn` rather than a `dy` produced elsewhere.
        """
        y = self.forward(x)
        loss, dy = loss_fn(y, targets)
        grads = self.backward(dy)
        moved = self.step(grads)["moved"]
        return {"loss": loss, "grads": grads, "moved": moved}

    def _ensure_machine(self) -> None:
        if self.machine is None:
            if self.image is None:
                self.compile()
            self.machine = Machine(self.cfg, self.progs["forward"], [self.image.copy()])


class _P:
    """`Params`-shaped adapter view for `AdamW.update`, which takes a `named()` mapping."""

    def __init__(self, adapters: Adapters):
        self.adapters = adapters

    def named(self) -> dict:
        return self.adapters.named()

    def quantized(self) -> None:
        self.adapters.quantized()


# ------------------------------------------------------------------------------ the two programs
@ol.jit
def _lora_fwd_prog(x, w, a, b, y_o, h_o, scale, B, R):
    """The forward pass: `y = x @ W^T + scale * (x @ A^T) @ B^T` and the bottleneck `h`.

    `h` is stored because both adapter gradients read it. `B` (the batch) and `R` (the padded
    rank) are compile-time shape constants: the accumulators below need them and a DRAM
    descriptor has no `.rows`/`.cols` (docs/train.md 9).
    """
    xv = ol.load(x)
    h, low = K.lora_fwd(xv, a, b, scale)
    ol.store(h_o, h)
    ol.store(y_o, K.linear_fwd(xv, w) + low)


@ol.jit
def _lora_bwd_prog(x, dy, h, a_t, b_t, w_t, dA_o, dB_o, dX_o, scale, B, R, KD, N):
    """The backward pass: the adapters' gradients (dA [R, KD], dB [N, R]) and `dX` of the layer.

    The two accumulators are the master copies' shapes, and their rows are filled by rank-1
    OUTER passes over the batch -- exact fp32, no transposed operand needed (docs/train.md 3.1).
    """
    xv = ol.load(x)
    dl = ol.load(dy)
    hv = ol.load(h)
    dA = ol.zeros((R, KD))
    dB = ol.zeros((N, R))
    dh, dA, dB = K.lora_bwd(dl, xv, hv, a_t, b_t, scale, dA, dB)
    ol.store(dA_o, dA)
    ol.store(dB_o, dB)
    ol.store(dX_o, K.lora_dx(dl, w_t, dh, a_t))
