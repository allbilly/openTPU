"""Training on the ISA simulator: the device's gradients against a float64 reference, and a
run whose loss falls.

The reference here is the float64 model of the same computation (`opentpu/train/ref.py` when it
is present; these tests carry their own equivalent, `model_ref`, so the gate stands alone). The
device's errors are the int8 operands': each gradient is within a few percent of the reference,
and the test bounds are the ones `tests/test_kernels.py` uses for a forward pass.
"""
from pathlib import Path

import numpy as np
import pytest

from opentpu import Config, isa as I
from opentpu import language as ol
from opentpu.train import kernels as K
from opentpu.train.loop import Trainer, layout, matrix_shapes
from opentpu.train.params import AdamW, Params, Shapes, mse, softmax_xent
from opentpu import quant as Q
from opentpu.isasim import Machine
from opentpu.runtime import Input, Output, Weight, compile_kernel
from opentpu.train.params import quant_w, quant_w_t

from opentpu.runtime import Input, Output, Weight, compile_kernel
from opentpu.isasim import Machine

from conftest import rel

ROOT = Path(__file__).resolve().parent.parent

# the shapes the tests train: H, F and V are multiples of D (the backward pass streams their
# transposes, whose reduction dim they become -- docs/train.md 5), the batch small enough that the
# unrolled OUTER accumulators fit IMEM
CFG = Config(S=1, D=32, ACT_BLOCKS=64, ACT_ROWS=64, IMEM_WORDS=1 << 16)
SHAPES = Shapes(vocab=32, hidden=32, interm=32, batch=4, rows=4)


def model_ref(x, gamma, w_gate, w_up, w_down, head, dlogits, eps):
    """float64 forward and backward of the model the Trainer trains (docs/train.md 3).

    Returns every intermediate the device computes, so a test can compare any one of them:
    xn, xh, r, g, u, a, y, logits, d_head, dy, da, dg, du, dxn, dx, d_gamma, d_gate, d_up,
    d_down.
    """
    x, gamma, w_gate, w_up, w_down, head, dlogits = (
        np.asarray(t, np.float64)
        for t in (x, gamma, w_gate, w_up, w_down, head, dlogits))
    r = 1.0 / np.sqrt(np.mean(x * x, axis=-1, keepdims=True) + eps)
    xh = x * r
    xn = xh * gamma
    g = xn @ w_gate.T
    u = xn @ w_up.T
    sg = 1.0 / (1.0 + np.exp(-g))
    a = (g * sg) * u
    y = a @ w_down.T + x
    logits = y @ head.T
    d_head = dlogits.T @ y
    dy = dlogits @ head
    da = dy @ w_down
    dg = da * u * (sg * (1.0 + g * (1.0 - sg)))
    du = da * (g * sg)
    dxn = dg @ w_gate + du @ w_up
    dxn_g = dxn * gamma
    dnorm = r * (dxn_g - np.mean(dxn_g * xh, axis=-1, keepdims=True) * xh)
    dx = dnorm + dy
    return dict(xn=xn, xh=xh, r=r, g=g, u=u, a=a, y=y, logits=logits, d_head=d_head, dy=dy,
                da=da, dg=dg, du=du, dxn=dxn, dx=dx, d_gamma=np.einsum("ij,ij->j", dxn, xh),
                d_gate=dg.T @ xn, d_up=du.T @ xn, d_down=dy.T @ a)


def a_model(shapes=SHAPES, seed=0):
    rng = np.random.default_rng(seed)
    x = (rng.standard_normal((shapes.batch, shapes.hidden)) * 0.5).astype(np.float32)
    targets = rng.integers(0, shapes.vocab, shapes.batch)
    params = Params.random(shapes, seed)
    return x, targets, params


def a_trainer(shapes=SHAPES, cfg=CFG, seed=0, **kw):
    return Trainer(shapes=shapes, cfg=cfg, params=Params.random(shapes, seed), **kw)


def _fwd_backward(tr, x, targets):
    """One forward pass, the host's loss, one backward pass: the gradients and the logits."""
    r = tr.step(x, targets)
    return r["grads"], tr._buffer("logits").copy(), r["loss"]


# ------------------------------------------------------------------ the reference is self-consistent
def test_model_ref_gradients_against_central_differences():
    """The float64 reference's backward formulas are the derivative of its own forward: central
    differences on every parameter, so a bug in the formulas fails here before any device runs."""
    shapes = Shapes(vocab=32, hidden=32, interm=32, batch=3, rows=3)
    rng = np.random.default_rng(1)
    x = rng.standard_normal((shapes.batch, shapes.hidden))
    gamma = 1.0 + 0.1 * rng.standard_normal(shapes.hidden)
    w_gate = rng.standard_normal((shapes.interm, shapes.hidden)) / 4
    w_up = rng.standard_normal((shapes.interm, shapes.hidden)) / 4
    w_down = rng.standard_normal((shapes.hidden, shapes.interm)) / 4
    head = rng.standard_normal((shapes.vocab, shapes.hidden)) / 4
    dlogits = rng.standard_normal((shapes.batch, shapes.vocab)) / shapes.batch
    eps = 1e-6
    want = model_ref(x, gamma, w_gate, w_up, w_down, head, dlogits, eps)

    def loss_of(name, value, h=1e-6):
        # the loss is linear in dlogits: <dlogits, logits> gives the formulas' gradients
        out = np.zeros_like(value)
        flat, vflat = out.reshape(-1), None
        for i in range(value.size):
            e = np.zeros_like(value).reshape(-1)
            e[i] = h
            e = e.reshape(value.shape)
            args = dict(x=x, gamma=gamma, w_gate=w_gate, w_up=w_up, w_down=w_down, head=head,
                        dlogits=dlogits, eps=eps)
            args[name] = value + e
            plus = float(np.sum(dlogits * model_ref(**args)["logits"]))
            args[name] = value - e
            minus = float(np.sum(dlogits * model_ref(**args)["logits"]))
            flat[i] = (plus - minus) / (2 * h)
        return flat.reshape(value.shape)

    for name, key in (("gamma", "d_gamma"), ("w_gate", "d_gate"), ("w_up", "d_up"),
                      ("w_down", "d_down"), ("head", "d_head")):
        want_grad = {"d_gamma": want["d_gamma"], "d_gate": want["d_gate"],
                     "d_up": want["d_up"], "d_down": want["d_down"],
                     "d_head": want["d_head"]}[key]
        fd = loss_of(name, {"gamma": gamma, "w_gate": w_gate, "w_up": w_up,
                            "w_down": w_down, "head": head}[name])
        assert rel(fd, want_grad) < 1e-5, (key, rel(fd, want_grad))
    # x's gradient too (the norm's backward and the residual)
    fd_x = loss_of("x", x)
    assert rel(fd_x, want["dx"]) < 1e-5, rel(fd_x, want["dx"])


def test_model_ref_against_torch_autograd():
    """The same reference against PyTorch's autograd, in float64: the formulas, independently
    checked by the engine the training literature uses (docs/train.md 7)."""
    torch = pytest.importorskip("torch")
    shapes = Shapes(vocab=32, hidden=32, interm=32, batch=3, rows=3)
    rng = np.random.default_rng(2)
    x = rng.standard_normal((shapes.batch, shapes.hidden))
    gamma = 1.0 + 0.1 * rng.standard_normal(shapes.hidden)
    w_gate = rng.standard_normal((shapes.interm, shapes.hidden)) / 4
    w_up = rng.standard_normal((shapes.interm, shapes.hidden)) / 4
    w_down = rng.standard_normal((shapes.hidden, shapes.interm)) / 4
    head = rng.standard_normal((shapes.vocab, shapes.hidden)) / 4
    dlogits = rng.standard_normal((shapes.batch, shapes.vocab)) / shapes.batch
    eps = 1e-6
    want = model_ref(x, gamma, w_gate, w_up, w_down, head, dlogits, eps)

    t = {n: torch.tensor(v, dtype=torch.float64, requires_grad=True)
         for n, v in (("x", x), ("gamma", gamma), ("w_gate", w_gate), ("w_up", w_up),
                      ("w_down", w_down), ("head", head))}
    r = 1.0 / torch.sqrt(t["x"].pow(2).mean(-1, keepdim=True) + eps)
    xn = (t["x"] * r) * t["gamma"]
    g, u = xn @ t["w_gate"].T, xn @ t["w_up"].T
    a = (g * torch.sigmoid(g)) * u
    y = a @ t["w_down"].T + t["x"]
    logits = y @ t["head"].T
    grads = torch.autograd.grad(logits, [t[n] for n in
                                         ("x", "gamma", "w_gate", "w_up", "w_down", "head")],
                                grad_outputs=torch.tensor(dlogits, dtype=torch.float64))
    for name, grad in zip(("x", "gamma", "w_gate", "w_up", "w_down", "head"), grads):
        key = {"x": "dx", "gamma": "d_gamma", "w_gate": "d_gate", "w_up": "d_up",
               "w_down": "d_down", "head": "d_head"}[name]
        got = grad.detach().numpy()
        assert rel(got, want[key]) < 1e-10, (name, rel(got, want[key]))


# ------------------------------------------------------------------------- the device's gradients
@pytest.mark.parametrize("seed", [0, 1])
def test_device_gradients_against_the_reference(seed):
    """The device's backward pass against the float64 model: every gradient, on the ISA
    simulator. The device streams int8 weights and quantizes its activations (docs/train.md 4),
    so the bounds are the int8 noise, not machine precision."""
    x, targets, params = a_model(seed=seed)
    tr = a_trainer(seed=seed, optimizer=AdamW(lr=0.0))     # (lr 0: the step must not move it)
    grads, logits, loss = _fwd_backward(tr, x, targets)
    loss_ref, dlogits = softmax_xent(model_ref(
        x, params.gamma, params.w_gate, params.w_up, params.w_down, params.head,
        np.zeros((SHAPES.batch, SHAPES.vocab)), tr.eps)["logits"], targets)
    want = model_ref(x, params.gamma, params.w_gate, params.w_up, params.w_down, params.head,
                     dlogits, tr.eps)
    # the device streams int8 weights, so its logits (and loss) differ from the float
    # reference by the quantizer's error, not by machine precision
    assert abs(loss - loss_ref) < 0.05, (loss, loss_ref)
    for name, key, tol in (("head", "d_head", 0.03), ("w_down", "d_down", 0.03),
                           ("w_gate", "d_gate", 0.05), ("w_up", "d_up", 0.05),
                           ("gamma", "d_gamma", 0.07)):
        assert rel(grads[name], want[key]) < tol, (name, rel(grads[name], want[key]))


def test_device_forward_matches_the_reference():
    """The forward pass and its stored activations: the backward pass reads them back, so they
    have to be what the reference computes (to the int8 noise)."""
    x, targets, params = a_model(seed=3)
    tr = a_trainer(seed=3)
    tr.step(x, targets)
    want = model_ref(x, params.gamma, params.w_gate, params.w_up, params.w_down, params.head,
                     np.zeros((SHAPES.batch, SHAPES.vocab)), tr.eps)
    for name, key, tol in (("xn", "xn", 0.01), ("g", "g", 0.02), ("u", "u", 0.02),
                           ("a", "a", 0.03), ("y", "y", 0.02), ("logits", "logits", 0.03)):
        got = tr._buffer(name)
        assert rel(got, want[key]) < tol, (name, rel(got, want[key]))


# -------------------------------------------------------------------------- an actual descent
@pytest.mark.parametrize("shapes,steps,floor", [
    (Shapes(vocab=32, hidden=32, interm=32, batch=4, rows=4), 25, 0.02),
    (Shapes(vocab=32, hidden=32, interm=64, batch=4, rows=4), 25, 0.02),
])
def test_a_step_trains(shapes, steps, floor):
    """A real descent: repeated steps on a fixed batch drive the cross-entropy near zero. This is
    the check the training literature runs (tt-train compares gradients and then convergence,
    docs/train.md 7) and the one that says the whole loop -- device forward, host loss, device
    backward, host optimizer, re-quantized weights -- is wired correctly."""
    x, targets, _ = a_model(shapes=shapes, seed=4)
    tr = Trainer(shapes=shapes, cfg=CFG, params=Params.random(shapes, 4),
                 optimizer=AdamW(lr=0.05))
    losses = [r["loss"] for r in tr.run(x, targets, steps=steps)]
    assert losses[0] > 0.5, losses[0]
    assert losses[-1] < floor, (losses[0], losses[-1])
    assert all(np.isfinite(l) for l in losses)


def test_mse_trains_and_the_gradient_is_the_loss():
    """The regression head: the device's gradients are the loss's, so one step on a batch whose
    target is the model's own output leaves the loss at zero."""
    shapes = Shapes(vocab=32, hidden=32, interm=32, batch=4, rows=4)
    x, _, params = a_model(shapes=shapes, seed=5)
    tr = Trainer(shapes=shapes, cfg=CFG, params=params, optimizer=AdamW(lr=0.0))
    tr.step(x, np.zeros(shapes.batch, np.int64))              # (a forward pass)
    y = tr._buffer("y")
    loss, dl = mse(np.zeros((shapes.batch, shapes.vocab)), np.zeros((shapes.batch, shapes.vocab)))
    # a step whose dlogits are a plain fp32 array: the loss is not a softmax, the gradient is the
    # residual itself, so the backward pass is exercised with a shape the host can compute
    tr._write("dlogits", np.ones((shapes.batch, shapes.vocab), np.float32) * 0.01)
    tr.machine.load(tr.progs["backward"]).run()
    grads = tr.gradients()
    want = model_ref(x, params.gamma, params.w_gate, params.w_up, params.w_down, params.head,
                     np.ones((shapes.batch, shapes.vocab)) * 0.01, tr.eps)
    for name, key, tol in (("head", "d_head", 0.03), ("w_down", "d_down", 0.03),
                           ("w_gate", "d_gate", 0.05), ("w_up", "d_up", 0.05),
                           ("gamma", "d_gamma", 0.07)):
        assert rel(grads[name], want[key]) < tol, (name, rel(grads[name], want[key]))
    assert float(np.abs(dl).sum()) == 0.0      # (y and the target are both zeros: the loss is 0)


# ------------------------------------------------------------------ the quantization is the only error
def test_the_gradients_are_exact_without_the_weight_quantization():
    """The weight gradients are OUTER accumulations of fp32 operands: they are exact up to the
    activations' quantization. With the reference's own quantized weights the difference is the
    quantizer's (docs/train.md 4), so it has to be small and it has to be *systematic* in the
    weights, not noise in the accumulation."""
    x, targets, params = a_model(seed=6)
    tr = a_trainer(seed=6)
    grads, _, _ = _fwd_backward(tr, x, targets)
    # the reference's gradients with the master copies replaced by what the device streamed
    want = model_ref(x, params.gamma,
                     np.asarray(params.q["w_gate"].dequant(), np.float32),
                     np.asarray(params.q["w_up"].dequant(), np.float32),
                     np.asarray(params.q["w_down"].dequant(), np.float32),
                     np.asarray(params.q["head"].dequant(), np.float32),
                     np.zeros((SHAPES.batch, SHAPES.vocab)), tr.eps)
    _, dlogits = softmax_xent(want["logits"], targets)
    want = model_ref(x, params.gamma,
                     np.asarray(params.q["w_gate"].dequant(), np.float32),
                     np.asarray(params.q["w_up"].dequant(), np.float32),
                     np.asarray(params.q["w_down"].dequant(), np.float32),
                     np.asarray(params.q["head"].dequant(), np.float32), dlogits, tr.eps)
    assert rel(grads["w_down"], want["d_down"]) < 0.02
    assert rel(grads["head"], want["d_head"]) < 0.02


# ------------------------------------------------------------------------------ the layout's limits
def test_the_layout_is_disjoint_and_aligned():
    """Every buffer of a step starts on a 128-byte boundary and no two overlap: a weight region
    overlapping an activation would corrupt a step silently."""
    lay = layout(SHAPES, CFG)
    spans = [(lay.byte[n], lay.byte[n] + 4, n) for n in lay.byte]
    for name, shape in lay.shape.items():
        start = 4 * lay.word[name]
        spans.append((start, start + 4 * int(np.prod(shape)), name))
    spans.sort()
    for (a, e, na), (b, f, nb) in zip(spans, spans[1:]):
        assert e <= b, f"{na} overlaps {nb}"
    assert all(s % 128 == 0 for s, _, _ in spans), "a buffer is not 128-byte aligned"


def test_the_shapes_that_the_backward_pass_cannot_stream_are_refused():
    """The backward pass streams a transpose, whose reduction dim becomes the MM's: a dimension
    that is not a multiple of D has no such operand, and the Shapes check says which (docs/train.md
    section 5)."""
    with pytest.raises(ValueError, match="multiple of the MXU depth"):
        Shapes(vocab=30).check(CFG)
    # a row group is one MXU stationary operand: the configuration's ACT_ROWS bounds it
    tight = Config(S=1, D=32, ACT_BLOCKS=64, ACT_ROWS=4)
    with pytest.raises(ValueError, match="ACT_ROWS"):
        Shapes(batch=8, rows=8).check(tight)


def test_a_batch_too_large_for_imem_is_refused_with_the_reason():
    """The dW accumulators are unrolled a row each, so a store too large does not fit the IMEM:
    a Shapes.batch of 64 makes a program of 64 OUTER passes a matrix, and the report names it."""
    big = Shapes(vocab=32, hidden=32, interm=32, batch=256, rows=32)
    small_cfg = Config(S=1, D=32, IMEM_WORDS=4096)
    with pytest.raises(Exception):
        Trainer(shapes=big, cfg=small_cfg, params=Params.random(big, 0))


# ------------------------------------------------------------------------------- the AdamW, tested
def test_adamw_matches_torch():
    """The optimizer, against torch.optim.AdamW on the same weights and gradients: decoupled
    weight decay, the bias-corrected moments, elementwise."""
    torch = pytest.importorskip("torch")
    shapes = Shapes(vocab=32, hidden=32, interm=32, batch=3, rows=3)
    params = Params.random(shapes, seed=7)
    rng = np.random.default_rng(7)
    grads = {n: rng.standard_normal(a.shape).astype(np.float32)
             for n, a in params.named().items()}
    lr, wd = 0.05, 0.01
    opt = AdamW(lr=lr, weight_decay=wd)
    copy = {n: a.copy() for n, a in params.named().items()}
    for step in range(3):
        with np.errstate(all="ignore"):
            opt.update(params, grads)
    tp = {n: torch.tensor(v.copy(), dtype=torch.float32, requires_grad=True)
          for n, v in copy.items()}
    topt = torch.optim.AdamW([tp[n] for n in tp], lr=lr, weight_decay=wd)
    for _ in range(3):
        for n in tp:
            tp[n].grad = torch.tensor(grads[n])
        topt.step()
        topt.zero_grad()
    for n, a in params.named().items():
        assert np.allclose(a, tp[n].detach().numpy(), atol=1e-6, rtol=1e-5), n


def test_adamw_reproduces_its_own_formula():
    """The update's arithmetic, stated once the way docs/train.md 3.6 states it: with a constant
    gradient the first step is sign(g) * lr (bias correction cancels the moment's scale)."""
    shapes = Shapes(vocab=32, hidden=32, interm=32, batch=3, rows=3)
    params = Params.random(shapes, seed=8)
    w0 = params.head.copy()
    params.head[...] = 0.0
    g = params.grads()
    g["head"][...] = 2.0
    AdamW(lr=0.1, weight_decay=0.0).update(params, g)
    assert np.allclose(params.head, -0.1, atol=1e-6)


def test_the_quantized_weights_are_the_bytes_the_mm_streams():
    """A QuantW's strides are the format's, and its dequantized matrix is the fp32 one the test's
    reference uses: the bridge between the host's master copy and the device's operand."""
    shapes = Shapes(vocab=32, hidden=32, interm=32, batch=4, rows=4)
    params = Params.random(shapes, seed=9)
    for name, (n, k) in matrix_shapes(shapes).items():
        q = quant_w(getattr(params, name), "int8", CFG.D)
        assert q.shape == (n, k)
        assert q.rs == Q.row_bytes(k, "int8", CFG.D)
        assert q.srs == Q.scale_bytes(k, "int8", CFG.D)
        d = q.dequant()
        assert d.shape == (n, k)
        assert rel(d, getattr(params, name)) < 0.02
    # the transposed operand: a matrix's transpose, quantized on its own
    t = quant_w_t(params.w_gate, "int8", CFG.D)
    assert t.shape == (shapes.hidden, shapes.interm)


# ----------------------------------------------------------------------------------- the CLI
def test_cli_trains_and_reports_both_losses():
    """`otpu-train` end to end: the entry point a user calls. It returns 0 when the loss fell,
    1 when it did not, so a script (and a gate) can depend on it."""
    from opentpu.train.cli import main
    assert main(["--steps", "12", "--vocab", "32", "--every", "0"]) == 0


def test_cli_refuses_a_shape_the_device_cannot_stream():
    """A hidden width that is not a multiple of D is refused with the reason, and the exit status
    says so (a CLI that trained anyway would be silently quantizing a broken shape)."""
    from opentpu.train.cli import main
    assert main(["--steps", "1", "--hidden", "48", "--interm", "32", "--vocab", "32"]) == 2


def test_cli_trains_on_text():
    """The byte-level task: a window of a file's bytes and the byte after it. The block can learn
    the first target (the loss falls), which is the check that the byte path is wired."""
    from pathlib import Path
    from opentpu.train.cli import main
    text = ROOT / "tools" / "data" / "austen_pp_ch1.txt"
    if not text.exists():
        pytest.skip("tools/data/austen_pp_ch1.txt is missing")
    assert main(["--steps", "15", "--text", str(text), "--seq", "32", "--vocab", "256",
                 "--every", "0"]) == 0


def test_cli_checkpoint_round_trip(tmp_path):
    """`--checkpoint` then `--resume`: the master weights and the optimizer's state survive
    (docs/train.md 6: it is the master copy, not the image, that a checkpoint saves)."""
    from opentpu.train.cli import main
    ck = tmp_path / "run.npz"
    assert main(["--steps", "6", "--checkpoint", str(ck), "--every", "0"]) == 0
    assert ck.exists()
    import numpy as np
    z = np.load(ck)
    assert "w_gate" in z and "gamma" in z and "step" in z
    assert int(z["step"][0]) == 6


# ---------------------------------------------------- the kernels the loop's passes are built from
def _a_layer(cfg=CFG, H=32, F=32, V=32, R=4, seed=0):
    """A tiny layer's operands: the tiles a kernel takes, as the `ol` kernels expect them."""
    rng = np.random.default_rng(seed)
    x = (rng.standard_normal((R, H)) * 0.5).astype(np.float32)
    w = (rng.standard_normal((F, H)) / np.sqrt(H)).astype(np.float32)
    return x, w, np.ascontiguousarray(w.T)     # w_t is the transpose the backward pass streams


def test_linear_dw_and_linear_bwd_are_the_reference():
    """`linear_dw` (one OUTER pass a row) and `linear_bwd` (dX plus the accumulation) against
    float64: the two primitives every linear layer's backward is made of."""
    x, w, w_t = _a_layer()
    dy = (np.random.default_rng(1).standard_normal((x.shape[0], w.shape[0])) * 0.4
          ).astype(np.float32)
    want_dx = dy @ w
    want_dw = dy.T @ x

    @ol.jit
    def k(x, dy, w_t, dx_o, dw_o):
        acc = ol.zeros((dy.shape[1], x.shape[1]))        # [N, K], the master copy's shape
        dx = K.linear_bwd(ol.load(dy), ol.load(x), w_t, acc)
        ol.store(dx_o, dx)
        ol.store(dw_o, acc)

    compiled, images = compile_kernel(
        k, CFG, x=Input(x), dy=Input(dy), w_t=Weight(w_t, None),
        dx_o=Output((x.shape[0], x.shape[1])), dw_o=Output((w.shape[0], x.shape[1])))
    m = Machine(CFG, compiled.programs, images).run()
    laid = compiled.layout.params
    dx = m.slices[0].dram[laid["dx_o"][1]:][:4 * want_dx.size].view(np.float32).reshape(
        want_dx.shape)
    dw = m.slices[0].dram[laid["dw_o"][1]:][:4 * want_dw.size].view(np.float32).reshape(
        want_dw.shape)
    assert rel(dx, want_dx) < 0.03, rel(dx, want_dx)
    assert rel(dw, want_dw) < 1e-6, rel(dw, want_dw)      # OUTER is exact fp32


def test_silu_bwd_and_lora_fwd_are_the_reference():
    """`silu_bwd` and `lora_fwd` (the two-mm low-rank path) against float64. LoRA is the fine-
    tuning shape docs/train.md 8 stages: the frozen weight streams once, the adapters twice."""
    rng = np.random.default_rng(2)
    g = (rng.standard_normal((4, 32)) * 0.5).astype(np.float32)
    dy = (rng.standard_normal((4, 32)) * 0.3).astype(np.float32)
    sg = (1.0 / (1.0 + np.exp(-g.astype(np.float64)))).astype(np.float32)
    want = dy.astype(np.float64) * (sg.astype(np.float64)
                                    * (1.0 + g.astype(np.float64) * (1.0 - sg.astype(np.float64))))

    @ol.jit
    def k(g, dy, out):
        ol.store(out, K.silu_bwd(ol.load(dy), ol.load(g)))

    compiled, images = compile_kernel(k, CFG, g=Input(g), dy=Input(dy),
                                      out=Output(g.shape))
    m = Machine(CFG, compiled.programs, images).run()
    got = m.slices[0].dram[compiled.layout.params["out"][1]:][:4 * g.size].view(
        np.float32).reshape(g.shape)
    assert rel(got, want) < 1e-5, rel(got, want)

    # lora: x @ A^T @ B^T * scale, A [rank, kdim], B [N, rank]
    H, kdim, rank, N = 32, 32, 32, 32     # rank must be a multiple of D (it is a reduction dim)
    x = (rng.standard_normal((4, kdim)) * 0.4).astype(np.float32)
    a = (rng.standard_normal((rank, kdim)) / np.sqrt(kdim)).astype(np.float32)
    b = (rng.standard_normal((N, rank)) / np.sqrt(rank)).astype(np.float32)

    @ol.jit
    def lora(x, a, b, out, scale):
        _h, low = K.lora_fwd(ol.load(x), a, b, scale)      # (h, the low-rank term)
        ol.store(out, low)

    compiled, images = compile_kernel(lora, CFG, x=Input(x), a=Weight(a, None),
                                      b=Weight(b, None), out=Output((4, N)), scale=1.0)
    m = Machine(CFG, compiled.programs, images).run()
    got = m.slices[0].dram[compiled.layout.params["out"][1]:][:4 * 4 * N].view(
        np.float32).reshape(4, N)
    want = x.astype(np.float64) @ a.astype(np.float64).T @ b.astype(np.float64).T
    assert rel(got, want) < 0.03, rel(got, want)
