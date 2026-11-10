"""Ladder step 10 — the production software stack: compiled kernels on the ISA simulator and the
production RTL.

The product's language/compiler/runtime/kernels/examples are imported byte-identically from the
parent commit `ca05e24f` (see `ladder/docs/production-stack.md`).  This suite is the ladder's step-10
contract:

* a compiled kernel end-to-end on the bit-exact ISA simulator against its numpy reference
  (`opentpu.runtime.compile_kernel` + `run`, the same path `examples/` use);
* deterministic compilation (the same kernel compiles to the same program words twice) and a
  fixed-vector exact result;
* `examples/run_all.py --backend isa` PASS in a subprocess (the production CLI over all 14
  example cases);
* the ported production suites in `test_step10_kernels.py` / `test_step10_compiler.py` /
  `test_step10_examples.py`;
* a compiled MLP (and a small attention decode) compiled for the step-9 production Config and
  replayed on the production RTL, compared bit-exactly with the ISA simulator: every DRAM byte
  and TMEM word, as `opentpu.rtlsim` / `ladder.harness.prod` define it.

Heavy part: `opentpu.rtlsim` runs build/run Verilator, so those tests only run through
`python3 ladder/run.py step 10` (the runner takes /tmp/rknpu-heavy.lock and sets LADDER_PY; a
bare pytest invocation skips them).  They reuse `ladder.harness.prod.CFG`, which is exactly the
step-9 Verilator build's key, so no second heavy build is needed.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# The production conftest clears these before opentpu is imported: cached images/programs must
# never mask a drift between the compiler and the simulator.
os.environ.setdefault("OTPU_IMAGE_CACHE", "0")
os.environ["OTPU_IMG_CACHE"] = "0"
os.environ["OTPU_PROG_CACHE"] = "0"

import numpy as np  # noqa: E402
import pytest  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from opentpu import Config  # noqa: E402
from opentpu import isa as I  # noqa: E402
from opentpu import language as ol  # noqa: E402
from opentpu import reference as ref  # noqa: E402
from opentpu.kernels import attention_decode, mlp  # noqa: E402
from opentpu.runtime import (Input, Output, Weight, compile_kernel, run)  # noqa: E402


def rel(a, b) -> float:
    """Relative error of a against the float64 reference (production conftest's helper)."""
    return float(np.linalg.norm(np.asarray(a, np.float64) - b) / np.linalg.norm(b))


def mlp_args(rng, M=4, H=128, Fd=256):
    """The production test_kernels.mlp_args: a small MLP kernel and its float64 reference."""
    h = rng.standard_normal((M, H)).astype(np.float32)
    gamma = (1 + 0.1 * rng.standard_normal(H)).astype(np.float32)
    wg = (rng.standard_normal((Fd, H)) / np.sqrt(H)).astype(np.float32)
    wu = (rng.standard_normal((Fd, H)) / np.sqrt(H)).astype(np.float32)
    wd = (rng.standard_normal((H, Fd)) / np.sqrt(Fd)).astype(np.float32)
    args = dict(h=Input(h), gamma=Input(gamma), w_gate=Weight(wg, 0), w_up=Weight(wu, 0),
                w_down=Weight(wd, 0), out=Output((M, H)), eps=1e-6)
    return args, ref.mlp(h, gamma, wg, wu, wd, 1e-6)


def attn_args(rng, Hq=2, Hkv=1, d=64, T=31, cap=64, block=32):
    q = rng.standard_normal((Hq, d)).astype(np.float32)
    k = rng.standard_normal((Hkv, T, d)).astype(np.float32)
    v = rng.standard_normal((Hkv, T, d)).astype(np.float32)
    args = dict(q=Input(q), kv=__import__("opentpu.runtime", fromlist=["KVCache"]).KVCache(k, v, cap),
                out=Output((Hq, d)), n_q_heads=Hq, n_kv_heads=Hkv, seq_len=T, block=block)
    return args, ref.attention(q, k, v, Hkv)


def have_verilator() -> None:
    import shutil
    if shutil.which("verilator") is None:
        pytest.skip("verilator not installed")


HEAVY = pytest.mark.skipif("LADDER_PY" not in os.environ,
                           reason="production-RTL replay runs only through ladder/run.py (host lock)")


# ---------------------------------------------------------------------------- ISA-only tests
def test_compiled_mlp_isa_vs_numpy():
    """Compile the production MLP kernel, run it on isasim, compare with the float64 reference."""
    args, want = mlp_args(np.random.default_rng(11), M=4)
    compiled, images = compile_kernel(mlp, Config(S=1), **args)
    result = run(compiled, [i.copy() for i in images], "isa")
    assert rel(result.outputs["out"], want) < 0.02


def test_compilation_is_deterministic():
    """The same kernel and arguments compile to the same program words and DRAM images."""
    args, _ = mlp_args(np.random.default_rng(3), M=2)
    a_compiled, a_images = compile_kernel(mlp, Config(S=1), **args)
    args2, _ = mlp_args(np.random.default_rng(3), M=2)
    b_compiled, b_images = compile_kernel(mlp, Config(S=1), **args2)
    assert a_compiled.programs == b_compiled.programs
    assert len(a_images) == len(b_images)
    for x, y in zip(a_images, b_images):
        np.testing.assert_array_equal(x, y)
    # and two ISA runs of the same compiled program leave the same state
    r1 = run(a_compiled, [i.copy() for i in a_images], "isa")
    r2 = run(a_compiled, [i.copy() for i in a_images], "isa")
    for x, y in zip(r1.drams, r2.drams):
        np.testing.assert_array_equal(x, y)
    for x, y in zip(r1.tmems, r2.tmems):
        np.testing.assert_array_equal(x, y)


def test_compiled_simple_add_exact():
    """A fixed vector: the examples' VPU add compiles and runs bit-exactly against numpy."""

    @ol.jit
    def add(a, b, out):
        ol.store(out, ol.load(a) + ol.load(b))

    rng = np.random.default_rng(1)
    a = (rng.integers(-32, 33, 32).astype(np.float32) / 4)
    b = (rng.integers(-32, 33, 32).astype(np.float32) / 4)
    compiled, images = compile_kernel(add, Config(S=1),
                                      a=Input(a), b=Input(b), out=Output(a.shape))
    result = run(compiled, [i.copy() for i in images], "isa")
    np.testing.assert_array_equal(result.outputs["out"], a + b)      # VPU add is exact here
    assert len(compiled.programs[0]) >= 2 and compiled.programs[0][-1].w[0] == 0  # HALT


def test_examples_run_all_isa(tmp_path):
    """`examples/run_all.py --backend isa` over every example case (the production CLI)."""
    out = tmp_path / "examples"
    r = subprocess.run([sys.executable, "-B", str(ROOT / "ladder/examples/run_all.py"),
                        "--backend", "isa", "--seed", "3", "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=600,
                       env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, (r.stdout + r.stderr)[-4000:]
    assert "PASS: 14 operation examples on isa" in r.stdout, r.stdout[-1000:]
    import json
    summary = json.loads((out / "summary.json").read_text())
    assert summary["status"] == "PASS" and len(summary["cases"]) == 14


# ------------------------------------------------------------------- production-RTL tests
@HEAVY
def test_mlp_on_production_rtl_matches_isasim():
    """Compile the MLP for the step-9 production Config; RTL and isasim must be bit-identical."""
    have_verilator()
    from ladder.harness import prod
    cfg = prod.config()
    args, want = mlp_args(np.random.default_rng(11), M=4)
    compiled, images = compile_kernel(mlp, cfg, **args)
    ri = run(compiled, [i.copy() for i in images], "isa")
    rr = run(compiled, [i.copy() for i in images], "rtl")
    for s, (a, b) in enumerate(zip(ri.drams, rr.drams)):
        bad = np.nonzero(a != b)[0]
        assert len(bad) == 0, f"slice {s}: {len(bad)} DRAM bytes differ, first {bad[:8]}"
    for s, (a, b) in enumerate(zip(ri.tmems, rr.tmems)):
        bad = np.nonzero(a != b)[0]
        assert len(bad) == 0, f"slice {s}: {len(bad)} TMEM words differ, first {bad[:8]}"
    assert ri.stats["instructions"] == rr.stats["instructions"]
    assert rel(rr.outputs["out"], want) < 0.02


@HEAVY
def test_attention_decode_on_production_rtl_matches_isasim():
    """A small attention decode on the production RTL vs isasim (same Config/build as step 9)."""
    have_verilator()
    from ladder.harness import prod
    cfg = prod.config()
    args, want = attn_args(np.random.default_rng(7), Hq=2, Hkv=1, T=31, cap=64, block=32)
    compiled, images = compile_kernel(attention_decode, cfg, **args)
    ri = run(compiled, [i.copy() for i in images], "isa")
    rr = run(compiled, [i.copy() for i in images], "rtl")
    for s, (a, b) in enumerate(zip(ri.drams, rr.drams)):
        assert np.array_equal(a, b), f"slice {s}: DRAM differs"
    for s, (a, b) in enumerate(zip(ri.tmems, rr.tmems)):
        assert np.array_equal(a, b), f"slice {s}: TMEM differs"
    assert rel(rr.outputs["out"], want) < 0.03
