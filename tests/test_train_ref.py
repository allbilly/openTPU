"""`opentpu/train/ref.py`: the float64 training reference, against central differences and
PyTorch's autograd.

The device's gradients are tested against this module, so this module has to be right. Two
independent checks: its own backward formulas against central differences of its own forward
(float64, so the finite difference is the only error), and against `torch.autograd` in float64
-- the engine the training literature validates with, which is what makes an agreement here an
agreement of formulas rather than of conventions.
"""
import numpy as np
import pytest

from opentpu import quant as Q
from opentpu.train import ref

from conftest import rel


def _model(seed=0, B=3, H=32, F=32, V=32):
    rng = np.random.default_rng(seed)
    x = rng.standard_normal((B, H))
    gamma = 1.0 + 0.1 * rng.standard_normal(H)
    w_gate = rng.standard_normal((F, H)) / 4
    w_up = rng.standard_normal((F, H)) / 4
    w_down = rng.standard_normal((H, F)) / 4
    head = rng.standard_normal((V, H)) / 4
    dlogits = rng.standard_normal((B, V)) / B
    return dict(x=x, gamma=gamma, w_gate=w_gate, w_up=w_up, w_down=w_down, head=head,
                dlogits=dlogits, eps=1e-6)


# ------------------------------------------------------- the formulas against finite differences
def test_model_gradients_against_central_differences():
    """Every gradient of `model_fwd_bwd` against central differences of its own forward. The loss
    the differences use is `<dlogits, logits>`, whose derivatives are exactly the dlogits the
    formula takes (a linear loss in the logits is the cleanest probe of the backward graph)."""
    m = _model()
    got = ref.model_fwd_bwd(**m)
    keys = {"x": "dx", "gamma": "d_gamma", "w_gate": "d_gate", "w_up": "d_up",
            "w_down": "d_down", "head": "d_head"}
    h = 1e-6

    for name, key in keys.items():
        value = m[name]
        fd = np.zeros_like(value)
        flat = fd.reshape(-1)
        for i in range(value.size):
            e = np.zeros_like(value).reshape(-1)
            e[i] = h
            e = e.reshape(value.shape)
            args = dict(m)
            args[name] = value + e
            args["dlogits"] = np.zeros_like(m["dlogits"])
            plus = float(np.sum(m["dlogits"] * ref.model_fwd_bwd(**args)["logits"]))
            args[name] = value - e
            minus = float(np.sum(m["dlogits"] * ref.model_fwd_bwd(**args)["logits"]))
            flat[i] = (plus - minus) / (2 * h)
        assert rel(fd, got[key]) < 1e-5, (name, rel(fd, got[key]))


@pytest.mark.parametrize("which,H,F,V", [
    ("rmsnorm", 16, 16, 16), ("swiglu", 16, 16, 16), ("linear", 16, 16, 16)])
def test_parts_against_finite_differences(which, H, F, V):
    """The parts on their own: each function's backward against the derivative of its forward."""
    rng = np.random.default_rng(1)
    x = rng.standard_normal((3, H))
    gamma = 1.0 + 0.1 * rng.standard_normal(H)
    dy = rng.standard_normal((3, H))
    h = 1e-6
    if which == "rmsnorm":
        got = ref.rmsnorm_bwd(dy, x, gamma, 1e-6)
        fd_dx = np.zeros_like(x)
        for i in range(x.size):
            e = np.zeros_like(x).reshape(-1)
            e[i] = h
            e = e.reshape(x.shape)
            f = lambda xx: float(np.sum(dy * ref.rmsnorm_fwd(xx, gamma, 1e-6)[0]))
            fd_dx.reshape(-1)[i] = (f(x + e) - f(x - e)) / (2 * h)
        assert rel(fd_dx, got[0]) < 1e-5, rel(fd_dx, got[0])
        fd_dg = np.zeros_like(gamma)
        for j in range(gamma.size):
            e = np.zeros_like(gamma)
            e[j] = h
            f = lambda gg: float(np.sum(dy * ref.rmsnorm_fwd(x, gg, 1e-6)[0]))
            fd_dg[j] = (f(gamma + e) - f(gamma - e)) / (2 * h)
        assert rel(fd_dg, got[1]) < 1e-5, rel(fd_dg, got[1])
    elif which == "swiglu":
        w_gate = rng.standard_normal((F, H)) / 4
        w_up = rng.standard_normal((F, H)) / 4
        w_down = rng.standard_normal((H, F)) / 4
        dY = rng.standard_normal((3, H))
        got = ref.swiglu_bwd_full(x, gamma, w_gate, w_up, w_down, dY, 1e-6)
        for name, key in (("x", "dx"), ("w_gate", "d_gate"), ("w_up", "d_up"),
                          ("w_down", "d_down")):
            base = {"x": x, "w_gate": w_gate, "w_up": w_up, "w_down": w_down}[name]
            fd = np.zeros_like(base)
            for i in range(base.size):
                e = np.zeros_like(base).reshape(-1)
                e[i] = h
                e = e.reshape(base.shape)

                def f(bb, nm=name):
                    """The loss at this parameter group's value bb, the others fixed."""
                    args = dict(x=None, gamma=gamma, w_gate=w_gate, w_up=w_up, w_down=w_down)
                    if nm == "x":
                        args["x"] = bb
                    else:
                        args["x"], args[nm] = x, bb
                    return float(np.sum(
                        dY * ref.swiglu_fwd(args["x"], args["gamma"], args["w_gate"],
                                            args["w_up"], args["w_down"], 1e-6)[0]))
                fd.reshape(-1)[i] = (f(base + e) - f(base - e)) / (2 * h)
            assert rel(fd, got[key]) < 1e-5, (name, rel(fd, got[key]))
    else:                     # linear
        w = rng.standard_normal((F, H)) / 4
        y, cache = ref.linear_fwd(x, w)
        dy = rng.standard_normal(y.shape)
        dx, dw, db = ref.linear_bwd(dy, cache, w)
        fd_dw = np.zeros_like(w)
        for i in range(w.size):
            e = np.zeros_like(w).reshape(-1)
            e[i] = h
            e = e.reshape(w.shape)
            f = lambda ww: float(np.sum(dy * ref.linear_fwd(x, ww)[0]))
            fd_dw.reshape(-1)[i] = (f(w + e) - f(w - e)) / (2 * h)
        assert rel(fd_dw, dw) < 1e-5, rel(fd_dw, dw)
        fd_dx = np.zeros_like(x)
        for i in range(x.size):
            e = np.zeros_like(x).reshape(-1)
            e[i] = h
            e = e.reshape(x.shape)
            f = lambda xx: float(np.sum(dy * ref.linear_fwd(xx, w)[0]))
            fd_dx.reshape(-1)[i] = (f(x + e) - f(x - e)) / (2 * h)
        assert rel(fd_dx, dx) < 1e-5, rel(fd_dx, dx)


# ------------------------------------------------------------- the formulas against PyTorch
def test_model_gradients_against_torch_autograd():
    """Every gradient against `torch.autograd` in float64. The whole model, one graph: the
    formulas this module states against an engine that derives them."""
    torch = pytest.importorskip("torch")
    m = _model(seed=2)
    got = ref.model_fwd_bwd(**m)
    names = ("x", "gamma", "w_gate", "w_up", "w_down", "head")
    t = {n: torch.tensor(m[n], dtype=torch.float64, requires_grad=True) for n in names}
    eps = m["eps"]
    r = 1.0 / torch.sqrt(t["x"].pow(2).mean(-1, keepdim=True) + eps)
    xh = t["x"] * r
    xn = xh * t["gamma"]
    g, u = xn @ t["w_gate"].T, xn @ t["w_up"].T
    sg = torch.sigmoid(g)
    a = (g * sg) * u
    y = a @ t["w_down"].T + t["x"]
    logits = y @ t["head"].T
    grads = torch.autograd.grad(logits, [t[n] for n in names],
                                grad_outputs=torch.tensor(m["dlogits"], dtype=torch.float64))
    keys = {"x": "dx", "gamma": "d_gamma", "w_gate": "d_gate", "w_up": "d_up",
            "w_down": "d_down", "head": "d_head"}
    for name, gr in zip(names, grads):
        assert rel(gr.detach().numpy(), got[keys[name]]) < 1e-10, \
            (name, rel(gr.detach().numpy(), got[keys[name]]))


def test_silu_against_torch_autograd():
    """`silu_fwd` and `silu_bwd` against torch's `x * sigmoid(x)`: the forward's value, the
    derivative, and the cached sigmoid the forward keeps (the device reuses it, one EXP2 and one
    RECIP an element saved)."""
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(3)
    x = rng.standard_normal((4, 8))
    y, sg = ref.silu_fwd(x)
    want_y = torch.nn.functional.silu(torch.tensor(x, dtype=torch.float64)).numpy()
    assert rel(y, want_y) < 1e-14, rel(y, want_y)
    assert rel(sg, torch.sigmoid(torch.tensor(x, dtype=torch.float64)).numpy()) < 1e-14
    t = torch.tensor(x, dtype=torch.float64, requires_grad=True)
    dy = rng.standard_normal(x.shape)
    (torch.nn.functional.silu(t) * torch.tensor(dy, dtype=torch.float64)).sum().backward()
    assert rel(t.grad.numpy(), ref.silu_bwd(dy, x)) < 1e-10
    # and with the cached sigmoid, which must give the same gradient
    assert rel(t.grad.numpy(), ref.silu_bwd(dy, x, sg)) < 1e-10


def test_softmax_cross_entropy_against_torch_autograd():
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(4)
    logits = rng.standard_normal((5, 16))
    targets = np.array([1, 3, 5, 7, 9])
    loss, dl = ref.softmax_cross_entropy(logits, targets)
    t = torch.tensor(logits, dtype=torch.float64, requires_grad=True)
    want = torch.nn.functional.cross_entropy(t, torch.tensor(targets), reduction="mean")
    want.backward()
    assert abs(loss - float(want.detach())) < 1e-12, (loss, float(want.detach()))
    assert rel(t.grad.numpy(), dl) < 1e-12


def test_adamw_step_matches_torch_optimizer():
    """The optimizer step against `torch.optim.AdamW`: decoupled weight decay, bias-corrected
    moments, elementwise -- over several steps, so the moments' state is exercised."""
    torch = pytest.importorskip("torch")
    rng = np.random.default_rng(5)
    w0 = {n: rng.standard_normal((4, 6)).astype(np.float32)
          for n in ("a", "b", "c")}
    grads = {n: rng.standard_normal((4, 6)).astype(np.float32) for n in w0}
    lr, wd = 0.05, 0.01
    pars = {n: v.copy() for n, v in w0.items()}
    state = {}
    tp = {n: torch.tensor(v.copy(), dtype=torch.float32, requires_grad=True)
          for n, v in w0.items()}
    topt = torch.optim.AdamW([tp[n] for n in tp], lr=lr, weight_decay=wd)
    for step in range(1, 4):
        ref.adamw_step(pars, grads, state, lr=lr, weight_decay=wd, step=step)
        for n in tp:
            tp[n].grad = torch.tensor(grads[n])
        topt.step()
        topt.zero_grad()
    for n in w0:
        assert np.allclose(pars[n], tp[n].detach().numpy(), atol=1e-6, rtol=1e-5), n


# --------------------------------------------------------------------------- the MX wrappers
@pytest.mark.parametrize("fmt,tol", [("int8", 1e-4), ("int4", 0.02), ("fp4", 0.02),
                                     ("nvfp4", 0.02)])
def test_mx_quantize_dequantize_round_trip(fmt, tol):
    """The reference's view of the weights is the device's: quantized to the format's grid and
    back, within the format's documented error (`tests/test_quant.py`'s bounds)."""
    rng = np.random.default_rng(6)
    w = (rng.standard_normal((32, 32)) * 0.02).astype(np.float32)
    rows, scales = ref.mx_quantize(w, fmt, 32)
    d = ref.mx_dequantize(rows, scales, fmt, 32, 32)
    assert Q.rel_err(w, d) < tol, Q.rel_err(w, d)
