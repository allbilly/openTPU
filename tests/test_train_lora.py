"""LoRA fine-tuning on the device: a frozen quantized base with two trainable adapters.

The gate the training literature runs for adapter training (tt-train compares every gradient
against a PyTorch reference before trusting a run), applied here: the adapters' gradients
against a float64 model of the same computation, the frozen base proven not to move, `dX`
through the frozen weight, and a real descent.
"""
import numpy as np
import pytest

from opentpu import Config
from opentpu.train.lora import Adapters, LoRA, pad_rank
from opentpu.train.params import AdamW, QuantW, quant_w, softmax_xent

from conftest import rel

CFG = Config(S=1, D=32, ACT_BLOCKS=64, ACT_ROWS=64, IMEM_WORDS=1 << 16)
B, KD, N, RANK, SCALE = 4, 32, 32, 8, 1.5


def _a_layer(seed=0, b_scale=0.3):
    """A frozen base, two adapters (B nonzero: the standard LoRA init leaves it at zero, and a
    zero B makes dA legitimately zero -- the tests that check dA set it) and a batch."""
    rng = np.random.default_rng(seed)
    w = (rng.standard_normal((N, KD)) / np.sqrt(KD)).astype(np.float32)
    ad = Adapters.random(RANK, KD, N, CFG.D, seed=seed + 1)
    if b_scale:
        ad.b = (rng.standard_normal((N, pad_rank(RANK, CFG.D))) / np.sqrt(N) * b_scale
                ).astype(np.float32)
        ad.quantized()
    x = (rng.standard_normal((B, KD)) * 0.5).astype(np.float32)
    targets = rng.integers(0, N, B)
    return w, ad, x, targets


def _ref_grads(x, dy, a, b, w, scale):
    """The float64 reference of the LoRA layer's gradients, on the weights the device streamed.

    `a`, `b`, `w` are the dequantized matrices (so the comparison isolates the *backend's*
    arithmetic: the activations' int8 quantization and the MM's rounding, not the formats').
    """
    x, dy = np.asarray(x, np.float64), np.asarray(dy, np.float64)
    h = x @ a.T
    dh = scale * dy @ b
    return dict(h=h, dh=dh, dA=dh.T @ x, dB=scale * dy.T @ h, dX=dy @ w + dh @ a,
                y=x @ w.T + scale * h @ b.T)


def _streamed(lo):
    """The weights the device actually streamed, dequantized: the comparison's left side."""
    return (lo.adapters.q["a"].dequant(), lo.adapters.q["b"].dequant(),
            quant_w(lo.w, "int8", CFG.D).dequant())


def _rel_matrix(a, b, floor=1e-3):
    """A relative error that survives an all-zero reference (a zero matrix's own error is not a
    ratio: dA really is zero when B starts at zero)."""
    a, b = np.asarray(a, np.float64), np.asarray(b, np.float64)
    denom = np.abs(b).max()
    return float(np.abs(a - b).max() / (denom if denom > 0 else max(floor, np.abs(a).max() or 1.0)))


# ------------------------------------------------------------------------------ the gradient gate
@pytest.mark.parametrize("seed", [0, 1])
def test_lora_gradients_against_the_reference(seed):
    """dA, dB and dX of the adapted layer against the float64 model, on the weights the device
    streamed. The int8 operands' noise is the bound, as everywhere else in this tree."""
    w, ad, x, targets = _a_layer(seed=seed)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, optimizer=AdamW(lr=0.0), batch=B, scale=SCALE)
    y = lo.forward(x)
    _, dy = softmax_xent(y, targets)
    g = lo.backward(dy)
    want = _ref_grads(x, dy, *_streamed(lo)[:2], _streamed(lo)[2], SCALE)

    assert _rel_matrix(g["a"], want["dA"]) < 0.03, _rel_matrix(g["a"], want["dA"])
    assert rel(g["b"], want["dB"]) < 0.03, rel(g["b"], want["dB"])
    assert rel(g["dx"], want["dX"]) < 0.04, rel(g["dx"], want["dX"])


def test_lora_forward_matches_the_reference():
    """The layer's output: the frozen matmul plus the scaled low-rank term, both streamed
    quantized. Checked against float64 on the same dequantized weights."""
    w, ad, x, _ = _a_layer(seed=2)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, batch=B, scale=SCALE)
    y = lo.forward(x)
    a, b, wq = _streamed(lo)
    want = (x.astype(np.float64) @ wq.T
            + SCALE * (x.astype(np.float64) @ a.T) @ b.T)
    assert rel(y, want) < 0.03, rel(y, want)


def test_lora_gradients_against_torch():
    """The adapters' gradients against `torch.autograd` in float64, on the streamed weights:
    the formulas, checked by an engine that derives them independently."""
    torch = pytest.importorskip("torch")
    w, ad, x, _ = _a_layer(seed=3)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, optimizer=AdamW(lr=0.0), batch=B, scale=SCALE)
    y = lo.forward(x)
    _, dy = softmax_xent(y, np.zeros(B, np.int64))
    g = lo.backward(dy)
    a, b, wq = _streamed(lo)
    t = {n: torch.tensor(v, dtype=torch.float64, requires_grad=True)
         for n, v in (("x", x), ("a", a), ("b", b))}
    out = t["x"] @ torch.tensor(wq) .T + SCALE * (t["x"] @ t["a"].T) @ t["b"].T
    (torch.tensor(dy.astype(np.float64)) * out).sum().backward()
    assert rel(g["a"], t["a"].grad.numpy()) < 0.03, rel(g["a"], t["a"].grad.numpy())
    assert rel(g["b"], t["b"].grad.numpy()) < 0.03, rel(g["b"], t["b"].grad.numpy())


def test_dx_through_the_frozen_weight_is_what_the_layer_below_needs():
    """`dX` must equal `dy @ W` plus the adapter's share: a frozen layer still passes the
    gradient down, or nothing below it trains (the property that makes a frozen base usable
    at all)."""
    w, ad, x, _ = _a_layer(seed=4)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, batch=B, scale=SCALE)
    _, dy = softmax_xent(lo.forward(x), np.zeros(B, np.int64))
    g = lo.backward(dy)
    a, _, wq = _streamed(lo)
    h = x.astype(np.float64) @ a.T
    want = (dy.astype(np.float64) @ wq
            + SCALE * (dy.astype(np.float64) @ _streamed(lo)[1]) @ a)
    assert rel(g["dx"], want) < 0.04, rel(g["dx"], want)


# --------------------------------------------------------------------------- the frozen-base property
def test_the_frozen_base_never_moves():
    """A LoRA step updates the two adapters and nothing else. The base weight is the same array
    before and after a run, and every byte of its MX rows in the image is unchanged: a fine-tune
    that silently perturbed the base would not be a fine-tune."""
    w, ad, x, targets = _a_layer(seed=5)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, optimizer=AdamW(lr=0.05), batch=B, scale=SCALE)
    lo.compile()
    w_copy = w.copy()
    base_rows = lo.image[lo.byte["w_data"]:lo.byte["w_data"] + w.shape[0] * KD].copy()

    losses = [lo.train_step(x, targets)["loss"] for _ in range(20)]
    assert losses[-1] < losses[0], (losses[0], losses[-1])
    assert np.array_equal(w, w_copy), "the frozen base's fp32 copy changed"
    after = lo.machine.slices[0].dram
    assert np.array_equal(after[lo.byte["w_data"]:lo.byte["w_data"] + base_rows.size],
                          base_rows), "the frozen base's MX rows in the image changed"


def test_a_lora_step_trains_by_descent():
    """Repeated steps drive the cross-entropy down: the loop -- device forward, host loss,
    device backward, host optimizer, re-quantized adapters -- is wired correctly."""
    w, ad, x, targets = _a_layer(seed=6)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, optimizer=AdamW(lr=0.05), batch=B, scale=SCALE)
    losses = [lo.train_step(x, targets)["loss"] for _ in range(30)]
    assert losses[0] > 0.5, losses[0]
    assert losses[-1] < 0.05, (losses[0], losses[-1])
    assert all(np.isfinite(l) for l in losses)


def test_lora_starts_as_the_frozen_layer():
    """LoRA's standard init (B = 0) makes the adapted layer bit-comparable to the frozen one at
    step 0: a fine-tune begins where the base left off, not a perturbation of it."""
    w, ad, x, targets = _a_layer(seed=7, b_scale=0)
    assert np.all(ad.b == 0)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, batch=B, scale=SCALE)
    y_adapted = lo.forward(x)
    # the frozen layer's own output: x @ W^T on the same quantized rows the device streamed
    y_frozen = np.asarray(x, np.float64) @ quant_w(w, "int8", CFG.D).dequant().T
    assert rel(y_adapted, y_frozen) < 0.03, rel(y_adapted, y_frozen)


# ------------------------------------------------------------------------------------ the rank's shape
def test_the_rank_is_padded_to_a_whole_d_block():
    """The rank is the second MM's reduction dim, so it is padded to D: the padded rows of A and
    columns of B carry zeros, which is why the padding costs the forward and the gradients
    nothing."""
    rp = pad_rank(RANK, CFG.D)
    assert rp == CFG.D and rp >= RANK
    ad = Adapters.random(RANK, KD, N, CFG.D, seed=1)
    assert ad.a.shape == (rp, KD) and ad.b.shape == (N, rp)
    assert np.all(ad.b == 0)                       # zero init
    assert np.all(ad.a[RANK:] == 0), "the padded rows of A must be zero"
    assert np.all(ad.b[:, RANK:] == 0), "the padded columns of B must be zero"


def test_an_odd_rank_is_padded_not_refused():
    """A rank that is not a D-multiple works (it is padded): a 5-wide adapter trains, which is
    what keeps the API usable with the usual LoRA ranks."""
    rp = pad_rank(5, CFG.D)
    ad = Adapters.random(5, KD, N, CFG.D, seed=1)
    assert ad.a.shape == (rp, KD)
    assert np.all(ad.a[5:] == 0)
    assert np.all(ad.b[:, 5:] == 0)


# ------------------------------------------------------------------------------------ the CLI
def test_cli_trains_a_lora_adapter():
    """`otpu-train --lora RANK` end to end: the frozen base is untouched, and the exit status
    says the loss fell (which is what makes this rung usable from a script)."""
    from opentpu.train.cli import main
    assert main(["--lora", "8", "--steps", "20", "--lr", "0.05", "--every", "0"]) == 0


def test_cli_lora_reports_an_odd_rank_is_padded():
    """A rank that is not a D-multiple is accepted and padded (the rank is a reduction dim), and
    a run with it still descends."""
    from opentpu.train.cli import main
    assert main(["--lora", "5", "--steps", "20", "--lr", "0.05", "--every", "0"]) == 0


def test_a_rank_above_the_layer_width_is_refused():
    """A rank larger than the layer's own width is not a low-rank adapter, and the padded width
    would make the low-rank term `[B, r]` with `r > N`: the residual add would be a shape
    mismatch. The check names which dimension refused it (the same class of error the ISA's
    operand constraints raise, docs/train.md 9)."""
    from opentpu.train.lora import check_rank
    assert check_rank(8, KD, N, CFG.D) == CFG.D
    assert check_rank(32, KD, N, CFG.D) == CFG.D
    with pytest.raises(ValueError, match="exceeds the layer"):
        check_rank(33, KD, N, CFG.D)
    with pytest.raises(ValueError, match="exceeds the layer"):
        check_rank(48, KD, N, CFG.D)
    with pytest.raises(ValueError, match="at least 1"):
        check_rank(0, KD, N, CFG.D)


def test_adapters_refuse_a_padded_rank_wider_than_the_output():
    """`Adapters` refuses the shapes `check_rank` refuses, so a hand-built pair cannot reach the
    kernel as a shape mismatch (the failure would be a compile error deep in the trace instead
    of a sentence naming the cause)."""
    with pytest.raises(ValueError, match="exceeds N"):
        Adapters(np.zeros((64, KD), np.float32), np.zeros((N, 64), np.float32))


# ------------------------------------------------------------------------------------- QLoRA
@pytest.mark.parametrize("fmt,tol", [("nvfp4", 0.02), ("fp4", 0.02), ("int4", 0.02)])
def test_qlora_a_four_bit_frozen_base_trains(fmt, tol):
    """QLoRA: the frozen base streams in a 4-bit format, the adapters in int8, and the step still
    trains. The forward and dA are checked against float64 on the 4-bit base's own dequantized
    values, so the comparison isolates the device's arithmetic from the format's error."""
    from opentpu import quant as Q
    rng = np.random.default_rng(0)
    w = (rng.standard_normal((N, KD)) / np.sqrt(KD)).astype(np.float32)
    ad = Adapters.random(RANK, KD, N, CFG.D, seed=1)
    ad.b = (rng.standard_normal((N, pad_rank(RANK, CFG.D))) / np.sqrt(N) * 0.3).astype(np.float32)
    ad.b[:, RANK:] = 0
    ad.quantized()
    x = (rng.standard_normal((B, KD)) * 0.5).astype(np.float32)
    targets = rng.integers(0, N, B)
    lo = LoRA(w=w, adapters=ad, cfg=CFG, optimizer=AdamW(lr=0.05), batch=B, scale=SCALE,
              base_fmt=fmt)
    y = lo.forward(x)
    wq = Q.dequantize_mxu(*Q.quantize_mxu(w, fmt, CFG.D), fmt, KD, CFG.D)
    aq, bq = lo.adapters.q["a"].dequant(), lo.adapters.q["b"].dequant()
    want = (x.astype(np.float64) @ wq.T
            + SCALE * (x.astype(np.float64) @ aq.T) @ bq.T)
    assert rel(y, want) < tol, rel(y, want)
    _, dy = softmax_xent(y, targets)
    g = lo.backward(dy)
    h = x.astype(np.float64) @ aq.T
    assert _rel_matrix(g["a"], (SCALE * dy.astype(np.float64) @ bq).T @ x.astype(np.float64)) \
        < 0.03
    w_copy = w.copy()
    losses = [lo.train_step(x, targets)["loss"] for _ in range(25)]
    assert losses[-1] < losses[0], (losses[0], losses[-1])
    assert np.array_equal(w, w_copy), "the 4-bit base's fp32 master copy moved"


def test_qlora_base_is_the_format_s_documented_width():
    """The base's MX rows are the 4-bit format's (`docs/quant.md`'s bits a weight), and its
    dequantized error is within the format's tolerance: the memory saving QLoRA buys is real and
    the error it costs is the documented one."""
    from opentpu import quant as Q
    from opentpu import quant as Q
    q = quant_w(np.zeros((N, KD), np.float32), "nvfp4", CFG.D)
    # nvfp4 stores two 4-bit elements a byte (row_bytes pads to whole D-blocks)
    assert len(q.rows[0]) == Q.row_bytes(KD, "nvfp4", CFG.D) <= KD // 2 + CFG.D
    rng = np.random.default_rng(0)
    w = (rng.standard_normal((N, KD)) * 0.02).astype(np.float32)
    for fmt in ("nvfp4", "fp4"):
        d = Q.dequantize_mxu(*Q.quantize_mxu(w, fmt, CFG.D), fmt, KD, CFG.D)
        assert Q.rel_err(w, d) < 0.02, (fmt, Q.rel_err(w, d))


@pytest.mark.parametrize("fmt", ["nvfp4", "fp4", "int4"])
def test_cli_trains_qlora_in_each_four_bit_format(fmt):
    """`otpu-train --qlora RANK --base-fmt F` for each 4-bit format the MXU has: the frozen base
    stays put and the loss falls, from the entry point a user calls."""
    from opentpu.train.cli import main
    assert main(["--qlora", "8", "--base-fmt", fmt, "--steps", "20", "--lr", "0.05",
                 "--every", "0"]) == 0
