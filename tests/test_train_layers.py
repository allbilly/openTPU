"""Full training: a whole transformer layer -- attention, an MLP, and every parameter -- trained
on the device, checked against the float64 reference and against PyTorch's autograd.

This is docs/train.md 8's rung 6, and it is what "full training" means here: no frozen base, no
adapters. The layer is `opentpu/kernels/attention.py`'s shape with its backward pass written out
by hand, exactly as llm.c writes GPT-2's (docs/train.md 1).

The gate the training literature runs (tt-train compares every gradient against a PyTorch
reference before trusting a run) is applied twice: `layer_ref` against `torch.autograd` in
float64, and the device's DRAM against `layer_ref`.
"""
import numpy as np
import pytest

from opentpu import Config
from opentpu.train import kernels as km
from opentpu.train.layers import (GAINS, LAYER_W, LayerParams, LayerTrainer, Layout,
                                  layer_ref)
from opentpu.train.params import AdamW, softmax_xent

from conftest import rel

CFG = Config(S=1, D=32, ACT_BLOCKS=128, ACT_ROWS=32, IMEM_WORDS=1 << 16)
DH, FF, T = 32, 64, 32          # (DH and FF are multiples of D: they become reduction dims)
SCALE = 1.0 / np.sqrt(DH)


def _a_layer(seed=0):
    rng = np.random.default_rng(seed)
    p = LayerParams.random(DH, FF, CFG.D, seed=seed + 1)
    x = (rng.standard_normal((T, DH)) * 0.5).astype(np.float32)
    dl = (rng.standard_normal((T, DH)) * 0.2).astype(np.float32)
    return p, x, dl


def _trainer(p, **kw):
    kw.setdefault("scale", SCALE)
    return LayerTrainer(p, CFG, T=T, eps=1e-6, **kw)


def _qparams(p):
    """The layer's parameters as the device streamed them: each matrix dequantized from its MX
    rows, so a comparison isolates the device's arithmetic from the format's error."""
    return LayerParams(**{n: np.asarray(p.q[n].dequant(), np.float32) for n in LAYER_W},
                       g1=p.g1, g2=p.g2, D=CFG.D)


def _rel(a, b, floor=1e-30):
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    denom = np.abs(b).max()
    return float(np.abs(a - b).max() / (denom if denom > floor else 1.0))


# ------------------------------------------------------------------ the reference is correct
def test_layer_ref_against_torch_autograd():
    """`layer_ref`'s backward against `torch.autograd` in float64: every gradient of the layer,
    from an engine that derives them independently. This must be exact (~1e-15), and it is the
    check that caught the `dWo` bug (`dWo = dh1^T o`, not `d(o)^T o`)."""
    torch = pytest.importorskip("torch")
    p, x, dl = _a_layer(seed=0)
    R = layer_ref(x, p, SCALE, dl)

    names = list(LAYER_W) + list(GAINS)
    t = {n: torch.tensor(getattr(p, n).astype(np.float64), requires_grad=True) for n in names}
    tx = torch.tensor(x.astype(np.float64), requires_grad=True)
    eps = 1e-6

    def norm(v, g):
        r = 1.0 / torch.sqrt(v.pow(2).mean(-1, keepdim=True) + eps)
        return (v * r) * g

    xn1 = norm(tx, t["g1"])
    q, k, v = xn1 @ t["Wq"].T, xn1 @ t["Wk"].T, xn1 @ t["Wv"].T
    s = (q @ k.T) * SCALE
    pm = torch.softmax(s, -1)
    o = pm @ v
    h1 = tx + o @ t["Wo"].T
    xn2 = norm(h1, t["g2"])
    g, u = xn2 @ t["Wg"].T, xn2 @ t["Wu"].T
    sg = torch.sigmoid(g)
    a = (g * sg) * u
    y = h1 + a @ t["Wd"].T
    (torch.tensor(dl.astype(np.float64)) * y).sum().backward()

    for n in names:
        assert rel(R["d" + n], t[n].grad.numpy()) < 1e-12, (n, rel(R["d" + n], t[n].grad.numpy()))
    assert rel(R["dx"], tx.grad.numpy()) < 1e-12, rel(R["dx"], tx.grad.numpy())


def test_layer_ref_gradients_against_central_differences():
    """The reference's own formulas against central differences of its own forward, so a formula
    that is wrong fails here even without torch."""
    p, x, dl = _a_layer(seed=1)
    R = layer_ref(x, p, SCALE, dl)
    h = 1e-6
    for name in ("g1", "g2"):
        base = getattr(p, name).astype(np.float64)
        fd = np.zeros_like(base)
        for i in range(base.size):
            e = np.zeros_like(base)
            e.flat[i] = h
            plus = layer_ref(x, _with(p, name, base + e), SCALE, dl)
            minus = layer_ref(x, _with(p, name, base - e), SCALE, dl)
            fd.flat[i] = (float((dl * plus["y"]).sum()) - float((dl * minus["y"]).sum())) / (2 * h)
        assert rel(fd, R["d" + name]) < 1e-5, (name, rel(fd, R["d" + name]))


def _with(p, name, value):
    """`p` with one parameter replaced, as FLOAT64 (a finite difference of 1e-6 is below the
    resolution of an fp32 value near 1: the perturbation would round, and the difference would
    be the rounding's, not the derivative's)."""
    d = {n: getattr(p, n).astype(np.float64) for n in list(LAYER_W) + list(GAINS)}
    d[name] = value.astype(np.float64)
    return LayerParams(D=CFG.D, **d)


# ------------------------------------------------------------------------- the device's forward
@pytest.mark.parametrize("seed", [0, 1])
def test_the_full_layer_forward_matches_the_reference(seed):
    """Every intermediate the forward stores, against the float64 reference: the backward pass
    reads them back, so a wrong one would silently corrupt every gradient."""
    p, x, _ = _a_layer(seed=seed)
    tr = _trainer(p)
    out = tr.forward(x)
    R = layer_ref(x, p, SCALE, np.zeros((T, DH)))
    for name in ("xn1", "P", "O", "h1", "xn2", "g", "u", "a", "y"):
        assert rel(out[name], R[name]) < 0.03, (name, rel(out[name], R[name]))


# ------------------------------------------------------------------------ the device's gradients
@pytest.mark.parametrize("seed", [0, 1])
def test_every_devices_gradient_matches_the_reference(seed):
    """All ten gradients of the full layer, the device's DRAM against `layer_ref` run on the same
    quantized weights the device streamed. The int8 operands' noise is the bound: the reference
    without the formats is the second column of docs/train.md 7's table."""
    p, x, dl = _a_layer(seed=seed)
    tr = _trainer(p, optimizer=AdamW(lr=0.0))
    tr.forward(x)
    g = tr.backward(dl)
    RQ = layer_ref(x, _qparams(p), SCALE, dl)
    for name in LAYER_W:
        assert _rel(g[name], RQ["d" + name]) < 0.04, (name, _rel(g[name], RQ["d" + name]))
    for name in GAINS:
        assert _rel(g[name], RQ["d" + name]) < 0.05, (name, _rel(g[name], RQ["d" + name]))
    assert _rel(g["dx"], RQ["dx"]) < 0.04, _rel(g["dx"], RQ["dx"])


# ------------------------------------------------------------------------------- the descent
def test_the_full_layer_trains_by_descent():
    """Repeated steps drive the cross-entropy down: the whole loop -- forward, host loss,
    backward, AdamW on nine parameter groups, re-quantized into the image -- is wired."""
    p, x, _ = _a_layer(seed=3)
    rng = np.random.default_rng(3)
    targets = rng.integers(0, DH, T)
    tr = _trainer(p, optimizer=AdamW(lr=0.02))
    losses = [tr.train_step(x, targets)["loss"] for _ in range(40)]
    assert losses[0] > 0.5, losses[0]
    assert losses[-1] < 0.05, (losses[0], losses[-1])
    assert all(np.isfinite(l) for l in losses)


def test_the_full_layers_parameters_actually_move():
    """Every one of the nine trainable groups receives a gradient and moves: a layer whose gain
    or one projection silently got a zero gradient would still train the MLP's other paths."""
    p, x, dl = _a_layer(seed=4)
    before = {n: getattr(p, n).copy() for n in list(LAYER_W) + list(GAINS)}
    tr = _trainer(p, optimizer=AdamW(lr=0.05))
    r = tr.step(x, dl)
    for n in list(LAYER_W) + list(GAINS):
        assert np.any(r["grads"][n] != 0), f"{n}: no gradient"
        assert not np.array_equal(getattr(p, n), before[n]), f"{n}: did not move"
    assert set(r["moved"]) == set(list(LAYER_W) + list(GAINS))


# --------------------------------------------------------------------------- the layout's budget
def test_the_layout_is_disjoint_and_aligned():
    """Every buffer starts on a 128-byte boundary and none overlaps: a weight region overlapping
    an activation would corrupt a step silently."""
    p = LayerParams.random(DH, FF, CFG.D, seed=5)
    lay = Layout(p, CFG, T, 1, "int8")
    spans = [(lay.byte[n], lay.byte[n] + 4, n) for n in lay.byte]
    for name, shp in lay.shape.items():
        start = 4 * lay.word[name]
        spans.append((start, start + 4 * int(np.prod(shp)), name))
    spans.sort()
    for (a, e, na), (b, f, nb) in zip(spans, spans[1:]):
        assert e <= b, f"{na} overlaps {nb}"
    assert all(s % 128 == 0 for s, _, _ in spans)


# ------------------------------------------------------------------------------------ the CLI
def test_cli_trains_a_whole_layer():
    """`otpu-train --layer` end to end: the full-training path, from the entry point a user
    calls. The exit status says the loss fell."""
    from opentpu.train.cli import main
    assert main(["--layer", "--steps", "15", "--lr", "0.02", "--hidden", "32", "--interm", "64",
                 "--batch", "32", "--every", "0"]) == 0
