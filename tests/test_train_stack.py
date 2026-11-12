"""A stack of transformer layers trained end to end on one device image.

`layers.py` trains one layer; this is what "full training" means for a model: several layers
chained, each one's `dX` feeding the one below it, plus an LM head. The gate the training
literature runs is applied to the whole graph: the stack's ten-plus gradients per layer against
`torch.autograd` in float64, on the same quantized weights the device streamed.
"""
import numpy as np
import pytest

from opentpu import Config, quant as Q
from opentpu.train import stack as SK
from opentpu.train.layers import LayerParams, layer_ref
from opentpu.train.params import AdamW
from opentpu.train.stack import HEAD, Stack, StackParams, stack_layout

from conftest import rel

CFG = Config(S=1, D=32, ACT_BLOCKS=128, ACT_ROWS=32, IMEM_WORDS=1 << 16)
D_, FF, T, V = 32, 64, 32, 32
SCALE = 1.0 / np.sqrt(D_)
MATRICES = ("Wq", "Wk", "Wv", "Wo", "Wg", "Wu", "Wd")
GAINS = ("g1", "g2")


def _a_stack(n=2, seed=0):
    rng = np.random.default_rng(seed)
    p = StackParams.random(n, D_, FF, V, CFG.D, seed=seed + 1)
    x = (rng.standard_normal((T, D_)) * 0.5).astype(np.float32)
    targets = rng.integers(0, V, T)
    return p, x, targets


def _qparams(stack_p):
    """The layers as the device streamed them: each matrix dequantized from its MX rows."""
    return [LayerParams(**{n: np.asarray(lay.q[n].dequant(), np.float32) for n in MATRICES},
                        g1=lay.g1, g2=lay.g2, D=CFG.D) for lay in stack_p.layers]


def _trainer(p, **kw):
    kw.setdefault("scale", SCALE)
    return Stack(p, CFG, T=T, eps=1e-6, **kw)


# --------------------------------------------------------------------- the stack against torch
@pytest.mark.parametrize("n_layers", [1, 2, 3])
def test_stack_gradients_against_torch_autograd(n_layers):
    """Every gradient of the whole stack -- each layer's nine groups and the head's -- against
    `torch.autograd` in float64 on the weights the device streamed. The bounds are the int8
    operands' noise (docs/train.md 7); a chaining bug would be a 100% error, as the probes that
    built this showed."""
    torch = pytest.importorskip("torch")
    p, x, targets = _a_stack(n=n_layers, seed=0)
    st = _trainer(p, optimizer=AdamW(lr=0.0))
    logits = st.forward(x)
    _, dl = SK.softmax_xent(logits, targets)
    g = st.backward(dl)

    def qp(lay):
        return {n: np.asarray(lay.q[n].dequant(), np.float64) for n in MATRICES} | {
            "g1": lay.g1.astype(np.float64), "g2": lay.g2.astype(np.float64)}

    tt = [{n: torch.tensor(v, requires_grad=True) for n, v in qp(lay).items()}
          for lay in p.layers]
    th = torch.tensor(p.head.astype(np.float64), requires_grad=True)
    tx = torch.tensor(x.astype(np.float64), requires_grad=True)

    def norm(v, g_, eps=1e-6):
        r = 1.0 / torch.sqrt(v.pow(2).mean(-1, keepdim=True) + eps)
        return (v * r) * g_

    def layer(h, t):
        xn = norm(h, t["g1"])
        q_, k_, v_ = xn @ t["Wq"].T, xn @ t["Wk"].T, xn @ t["Wv"].T
        pm = torch.softmax((q_ @ k_.T) * SCALE, -1)
        h1 = h + (pm @ v_) @ t["Wo"].T
        xn2 = norm(h1, t["g2"])
        gg, uu = xn2 @ t["Wg"].T, xn2 @ t["Wu"].T
        sg = torch.sigmoid(gg)
        return h1 + ((gg * sg) * uu) @ t["Wd"].T

    h = tx
    for t in tt:
        h = layer(h, t)
    logits_t = h @ th.T
    torch.nn.functional.cross_entropy(logits_t, torch.tensor(targets)).backward()

    assert rel(g["head"], th.grad.numpy()) < 0.04, rel(g["head"], th.grad.numpy())
    for i, t in enumerate(tt):
        for n in MATRICES + GAINS:
            assert rel(g[f"layer{i}.{n}"], t[n].grad.numpy()) < 0.06, \
                (i, n, rel(g[f"layer{i}.{n}"], t[n].grad.numpy()))


def test_the_stack_matches_the_layer_reference_layer_by_layer():
    """Each layer's own gradients, against `layer_ref` fed exactly the `dl` that layer received:
    the chaining is right if every link is, and this isolates which link would be wrong."""
    p, x, _ = _a_stack(n=2, seed=1)
    st = _trainer(p, optimizer=AdamW(lr=0.0))
    st.forward(x)
    dl1 = (np.random.default_rng(3).standard_normal((T, D_)) * 0.2).astype(np.float32)
    q = _qparams(p)
    y0 = st.lts[0]._buffer("y").copy()
    for i in (1, 0):
        st.lts[i]._write("dl", dl1)
        st._run(st.lts[i].progs["backward"])
        R = layer_ref(x if i == 0 else y0, q[i], SCALE, dl1)
        for n in ("Wq", "Wg", "Wd"):
            assert rel(st.lts[i]._buffer("d" + n), R["d" + n]) < 0.05, \
                (i, n, rel(st.lts[i]._buffer("d" + n), R["d" + n]))


# ---------------------------------------------------------------------------- the descent
@pytest.mark.parametrize("n_layers", [2, 3])
def test_a_stack_trains_by_descent(n_layers):
    """Repeated steps drive the cross-entropy down: a whole stack -- n layers chained, an LM
    head, AdamW over every matrix -- trains, which is what "full training" means here."""
    p, x, targets = _a_stack(n=n_layers, seed=2)
    st = _trainer(p, optimizer=AdamW(lr=0.02))
    losses = [st.train_step(x, targets)["loss"] for _ in range(40)]
    assert losses[0] > 0.5, losses[0]
    assert losses[-1] < 0.05, (losses[0], losses[-1])
    assert all(np.isfinite(l) for l in losses)


def test_every_matrix_in_the_stack_moves():
    """Every layer's seven matrices and two gains, and the head, get a nonzero gradient and move:
    a layer whose gain silently got a zero gradient would still train the rest."""
    p, x, targets = _a_stack(n=2, seed=3)
    before = {k: v.copy() for k, v in p.named().items()}
    st = _trainer(p, optimizer=AdamW(lr=0.05))
    r = st.train_step(x, targets)
    assert set(r["moved"]) == set(p.named()), "a matrix without a gradient"
    for k in p.named():
        assert np.any(r["grads"][k] != 0), f"{k}: zero gradient"
        assert not np.array_equal(p.named()[k], before[k]), f"{k}: did not move"


def test_a_single_layer_stack_is_one_layer():
    """A stack of one is `layers.py`'s layer plus a head: the chaining adds nothing when there is
    nothing to chain, and its loss is the layer's own."""
    p, x, targets = _a_stack(n=1, seed=4)
    st = _trainer(p, optimizer=AdamW(lr=0.0))
    logits = st.forward(x)
    R = layer_ref(x, p.layers[0], SCALE, np.zeros((T, D_)))
    want = R["y"] @ p.head.astype(np.float64).T
    assert rel(logits, want) < 0.04, rel(logits, want)


# ------------------------------------------------------------------------- the layout and the memory
@pytest.mark.parametrize("n_layers", [1, 2, 3, 4])
def test_the_stack_fits_one_image_and_the_slots_are_disjoint(n_layers):
    """Every layer gets its own slot of one DRAM image, the slots do not overlap, and the whole
    stack fits the simulator's DRAM -- the cost docs/train.md 8 named ("the DRAM to keep both
    layers' saved activations") and the number it is."""
    p = StackParams.random(n_layers, D_, FF, V, CFG.D, seed=5)
    sl = stack_layout(p, CFG, T)
    # each slot's start, in increasing order, and no slot's buffers reach into the next one
    starts = sorted(sl.base)
    assert starts == sl.base
    for i in range(len(sl.base) - 1):
        assert sl.base[i + 1] > sl.base[i]
    assert sl.head_at > sl.base[-1]
    assert sl.nbytes <= CFG.DRAM_BYTES, (sl.nbytes, CFG.DRAM_BYTES)
    # a layer's every buffer lies inside its own slot
    for i, lay in enumerate(sl.layer_layouts):
        lo = sl.base[i]
        hi = sl.base[i + 1] if i + 1 < len(sl.base) else sl.head_at
        for name in lay.byte:
            assert lo <= lay.byte[name] < hi, (i, name)
        for name in lay.word:
            assert lo <= 4 * lay.word[name] < hi, (i, name)


def test_four_layers_fit_the_simulator():
    """The measured budget: 140 KiB a layer, so four fit the 1 MiB simulator image with room to
    spare -- which is why a stack is a real option here and not an aspiration."""
    p = StackParams.random(4, D_, FF, V, CFG.D, seed=6)
    sl = stack_layout(p, CFG, T)
    per_layer = sl.base[1] - sl.base[0] if len(sl.base) > 1 else sl.nbytes
    assert sl.nbytes < CFG.DRAM_BYTES
    assert 100 < per_layer / 1024 < 200, per_layer / 1024      # ~140 KiB measured


# ------------------------------------------------------------------------------------- the CLI
def test_cli_trains_a_stack():
    """`otpu-train --stack N` end to end: a whole stack, from the entry point a user calls."""
    from opentpu.train.cli import main
    assert main(["--stack", "2", "--steps", "15", "--lr", "0.02", "--hidden", "32",
                 "--interm", "64", "--batch", "32", "--vocab", "32", "--every", "0"]) == 0
