"""Ladder step 14 — LLM in simulation: a torch-free tiny Qwen3 fixture and the ISA<->RTL replay.

The production LLM layer needs no checkpoint and no torch to do real work: `opentpu/llm/`'s
torch/transformers/safetensors imports are all lazy (checkpoint loading and the tests' HF
references), so `import opentpu.llm` and the whole engine/image/ISA/RTL-backend path run on
numpy alone.  This harness therefore builds the same tiny random model the production tests
build (`tests/test_qwen3.py::tiny`) as a plain numpy HF state-dict — same keys, shapes,
distributions and seed — and drives the *real* production engine first on the ISA simulator
(the bit-exact oracle) and then on the production RTL through `opentpu.llm.rtl_backend`.

Golden continuation (deterministic, `/usr/bin/python3`, numpy only; `tests/test_step14_llm_sim.py`
asserts it):

    prompt [811, 85, 179, 236, 181]  ->  greedy [181, 181, 181, 564, 564, 564]
    prefill logits sha256 3621798ad0297b828a17eb209b905cfa19e4e984bcffec71ce51fefc8455b410

The Config is pinned explicitly (not `board_config()`, which reads OTPU_TARGET/OTPU_MCOLS/...
from the environment): the production RTL's Verilator build key depends on every one of its
fields, so a stray environment variable would silently trigger a second multi-minute build.
"""

from __future__ import annotations

import fcntl
import hashlib
import os
from pathlib import Path

import numpy as np

# The step-14 Verilator build is the largest configuration in the ladder (D=128, 16 MiB DRAM,
# 32K instructions).  At the ladder-wide "-j 2" the host's power/thermal guard SIGTERMed
# cc1plus on this shared laptop; build with a single compiler job instead.  VFLAGS is part of
# opentpu.rtlsim's build-cache key, so the deterministic -j 1 build (and the warm cache the
# runner's preflight then finds) is what every later run of this commit reuses.
from opentpu import rtlsim as _rtlsim           # noqa: E402

if "-j" in _rtlsim.VFLAGS:
    _rtlsim.VFLAGS[_rtlsim.VFLAGS.index("-j") + 1] = "1"
# the C++ backend is what heats the package: -O1 (instead of the ladder-wide -O3) compiles this
# largest configuration in a fraction of the time and stays under the host's ~95 C guard, at a
# small simulation-speed cost the 4-token replay does not notice.
if "-O3" in _rtlsim.VFLAGS:
    _rtlsim.VFLAGS[_rtlsim.VFLAGS.index("-O3")] = "-O1"

# Deterministic fresh image/program builds, before opentpu is imported by anything downstream:
# the image caches would hand back a stale quantized image built with different code/constants.
os.environ["OTPU_IMAGE_CACHE"] = "0"
os.environ["OTPU_IMG_CACHE"] = "0"
os.environ["OTPU_PROG_CACHE"] = "0"

# ---------------------------------------------------------------------------- the fixture
SPEC_ARGS = dict(hidden=256, layers=2, n_q=4, n_kv=2, head_dim=128, ffn=512, vocab=1000)
# The tiny model's production-config: the board's D = 128, one slice, 4 MXU columns; 4 ACT
# rows (the lead's step-14 build), 64K TMEM words, 4K-instruction IMEM, 8 banks, 16 MiB DRAM.
CFG_ARGS = dict(S=1, D=128, MCOLS=4, ACT_BLOCKS=128, ACT_ROWS=4, TMEM_WORDS=65536,
                IMEM_WORDS=32768, LANES=8, DRAM_BYTES=1 << 24)

PROMPT = [811, 85, 179, 236, 181]                 # seed-3 token ids (all < vocab)
GREEDY = [181, 181, 181, 564, 564, 564]           # argmax of the prefill logits, then per step
PREFILL_LOGITS_SHA256 = "3621798ad0297b828a17eb209b905cfa19e4e984bcffec71ce51fefc8455b410"
# sha256 of the fp32 logits after each greedy step (i.e. after feeding GREEDY[i]); asserted by
# the light test so the ISA rung alone notices a fixture/spec/engine drift.
STEP_LOGITS_SHA256 = [
    "7f16c560840bece3e11067557738e2241d485d1d76d57029135f49cc42374b7c",
    "46359da142eb17b70905ae39171f1356d0db6c520e0a3561f50368482102f2cf",
    "ad01a1e9df1e31700cd498e93d0b0b2efa761ac86f8700f71783d98468af37d2",
    "10fbece197f28e35dfeb099cdbf81540a597eadbef984586508ade99ea824148",
    "adca36c5811b6e6e837e0da2760faf4587605e9fa2bb94a05788a6fe6a82d7fe",
]
IMAGE_BYTES = 2218112                             # the fixture image size (regression guard)
IMAGE_SHA256 = "3937bafd022ef6c72ba159ad3f3d1d5d2322697d8a85e25a6f035e3bc4f354f8"


def spec():
    """The tiny Qwen3 Spec the production tests use, without torch."""
    from opentpu.llm.qwen3 import Spec

    return Spec(**SPEC_ARGS)


def config():
    """The pinned production Config of the tiny-model simulation (RTL and ISA share it)."""
    from opentpu.isasim import Config

    return Config(**CFG_ARGS)


def weights() -> dict:
    """The tiny model's HF state-dict as fp32 numpy arrays, exactly the production recipe.

    `tests/test_qwen3.py::tiny`: `torch.manual_seed(0)`, default init for the linear weights
    (~N(0, 0.02) with the Hugging Face default std, drawn in the same order), norms set to
    `1 + 0.1*randn`, tied LM head.  Uses numpy's PCG64 (`default_rng(0)`), independent of
    numpy's legacy global state.
    """
    f32 = lambda v: np.asarray(v, np.float32)  # noqa: E731
    sp = spec()
    rng = np.random.default_rng(0)
    d, dq, dkv, f = sp.hidden, sp.n_q * sp.head_dim, sp.n_kv * sp.head_dim, sp.ffn
    W = {"model.embed_tokens.weight": f32(rng.normal(0, 0.02, (sp.vocab, d)))}
    for i in range(sp.layers):
        p = f"model.layers.{i}."
        for name, shape in (("self_attn.q_proj", (dq, d)), ("self_attn.k_proj", (dkv, d)),
                            ("self_attn.v_proj", (dkv, d)), ("self_attn.o_proj", (d, dq)),
                            ("mlp.gate_proj", (f, d)), ("mlp.up_proj", (f, d)),
                            ("mlp.down_proj", (d, f))):
            W[p + name + ".weight"] = f32(rng.normal(0, 0.02, shape))
        for name, shape in (("input_layernorm", (d,)), ("post_attention_layernorm", (d,)),
                            ("self_attn.q_norm", (sp.head_dim,)),
                            ("self_attn.k_norm", (sp.head_dim,))):
            W[p + name + ".weight"] = f32(1.0 + 0.1 * rng.normal(0, 1, shape))
    W["model.norm.weight"] = f32(1.0 + 0.1 * rng.normal(0, 1, (d,)))
    return W


def engine(**kw):
    """The production Engine on the ISA backend (the oracle), built from the numpy fixture."""
    from opentpu.llm.qwen3 import Engine

    return Engine(spec(), weights(), cap=256, cfg=config(), **kw)


def logits_sha256(logits) -> str:
    return hashlib.sha256(np.asarray(logits, np.float32).tobytes()).hexdigest()


def logits_bits(logits) -> np.ndarray:
    """The logits as raw fp32 words, the bit-exact compare unit for ISA vs RTL."""
    return np.asarray(logits, np.float32).view(np.uint32)


def image_nbytes(eng) -> int:
    """The bytes of the model image at the start of DRAM (the compared DRAM range)."""
    return int(eng.image.nbytes)


def image_sha256(eng) -> str:
    """sha256 of the model image bytes at the start of DRAM (the bit-exact built image)."""
    n = image_nbytes(eng)
    return hashlib.sha256(np.asarray(eng.backend.machine.slices[0].dram[:n], np.uint8)
                          .tobytes()).hexdigest()


def dram_state(eng, n: int) -> list[np.ndarray]:
    """Copies of each slice's DRAM image `[:n]` (the state a replay starts from)."""
    return [np.asarray(s.dram[:n], np.uint8).copy() for s in eng.backend.machine.slices]


# ---------------------------------------------------------------------------- light: ISA goldens
def isa_golden(tokens: int = len(GREEDY)) -> dict:
    """Prefill the prompt on the ISA simulator and greedy-continue `tokens` tokens.

    Returns the produced token ids, the fed ones, the per-step logits sha256 list, the prefill
    logits sha256, the image size, and a fresh-engine determinism check.
    """
    eng = engine()
    img_sha = image_sha256(eng)          # the built image, before any run writes its DRAM
    logits = np.asarray(eng.prefill(PROMPT), np.float32)
    prefill_sha = logits_sha256(logits)
    produced, fed, step_shas = [], [], []
    for k in range(tokens):
        t = int(np.argmax(logits))
        produced.append(t)
        if k + 1 == tokens:
            break
        fed.append(t)
        logits = np.asarray(eng.step(t), np.float32)
        step_shas.append(logits_sha256(logits))
    again_eng = engine()
    again_img_sha = image_sha256(again_eng)
    again = np.asarray(again_eng.prefill(PROMPT), np.float32)
    return {"produced": produced, "fed": fed, "prefill_sha256": prefill_sha,
            "step_logits_sha256": step_shas, "image_nbytes": image_nbytes(eng),
            "image_sha256": img_sha,
            "deterministic": logits_sha256(again) == prefill_sha and
                             again_img_sha == img_sha,
            "final_logits_sha256": step_shas[-1] if step_shas else prefill_sha}


# ---------------------------------------------------------------------------- heavy: RTL replay
def rtl_sources():
    """(top, sources, params) of the Verilator build the tiny-model RTL run needs.

    Mirrors `opentpu.rtlsim.build_top(cfg, dram_lat=8, uarch=None, axi=False)`: the behavioural
    DRAM path, the default UARCH, `tb_top`.  The build directory is keyed on the sources,
    params and Verilator version, so this is exactly the runner's warm preflight question.
    """
    from opentpu import rtlsim

    params = rtlsim.top_params(config(), 8, None, False)
    sources = [rtlsim.RTL / s for s in rtlsim.RTL_SOURCES] + [rtlsim.TB / "tb_top.sv"]
    return "tb_top", sources, params


def rtl_build_present() -> tuple[bool, str]:
    """(already compiled?, description) for the tiny-model RTL simulation build."""
    try:
        from opentpu import rtlsim

        top, sources, params = rtl_sources()
        d = rtlsim.build_dir(top, sources, params)
        exe = d / f"V{top}"
        return exe.exists(), f"{exe} ({d.name}, AXI=0, D=128, DRAM=16 MiB)"
    except Exception as e:  # noqa: BLE001 - any failure means "not warm"
        return False, f"preflight failed: {e}"


def warm_ready() -> tuple[bool, str]:
    """`ladder/run.py --warm` preflight hook (same shape as prod.CFG's)."""
    return rtl_build_present()


def under_heavy_gate() -> bool:
    """Whether the shared-host heavy lock (/tmp/rknpu-heavy.lock) is currently held.

    A cold Verilator build must only happen under the runner's flock + thermal gate; a direct
    `pytest` run of the heavy test outside it skips instead of compiling uncontrolled.
    """
    lock = Path(os.environ.get("LADDER_HEAVY_LOCK", "/tmp/rknpu-heavy.lock"))
    if not lock.exists():
        return False
    try:
        fd = os.open(str(lock), os.O_RDWR)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True                      # someone (the runner) holds it
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def runner_gate_ok() -> bool:
    """Whether this process is a `ladder/run.py` run that holds the shared-host heavy gate.

    A cold Verilator compile is only legitimate there; a direct `pytest` on a shared laptop must
    skip instead of compiling uncontrolled (a warm build needs no gate and proceeds anyway).
    """
    return bool(os.environ.get("LADDER_PY")) and under_heavy_gate()


def isa_vs_rtl(steps: int = 4) -> dict:
    """Replay the ISA greedy continuation on the production RTL, one fresh simulation per step.

    For each fed token: snapshot the ISA machine's DRAM image before the step, run the ISA
    oracle step, run the same step on `RtlBackend(cfg, drams, axi=False, boot=False)`, and
    require identical uint32 logits, identical DRAM `[:image.nbytes]` and identical token ids.
    Returns the fed/produced token ids and the per-step digests.  Raises AssertionError with the
    step's logits/DRAM difference otherwise.
    """
    from opentpu.llm.rtl_backend import RtlBackend

    isa = engine()
    logits = np.asarray(isa.prefill(PROMPT), np.float32)
    n = image_nbytes(isa)
    isa_backend = isa.backend
    fed, produced, steps_out = [], [], []
    t = int(np.argmax(logits))
    for k in range(steps):
        p = isa.pos
        drams = dram_state(isa, n)                       # the state before this token
        want = np.asarray(isa.step(t), np.float32)       # ISA oracle
        rtl = RtlBackend(isa.cfg, drams, axi=False, boot=False)
        isa.backend, isa.pos = rtl, p
        got = np.asarray(isa.step(t), np.float32)        # the same token on the RTL
        isa.backend, isa.pos = isa_backend, p + 1
        if not np.array_equal(logits_bits(want), logits_bits(got)):
            bad = np.nonzero(logits_bits(want) != logits_bits(got))[0][:8]
            raise AssertionError(
                f"step {k} (token {t}): logits differ at {bad.tolist()}: "
                f"ISA {[int(logits_bits(want)[i]) for i in bad]} vs "
                f"RTL {[int(logits_bits(got)[i]) for i in bad]}")
        for s, (have, rtl_s) in enumerate(zip(isa.backend.machine.slices, rtl.drams)):
            if not np.array_equal(np.asarray(have.dram[:n], np.uint8),
                                  np.asarray(rtl_s[:n], np.uint8)):
                diff = np.nonzero(np.asarray(have.dram[:n], np.uint8) !=
                                  np.asarray(rtl_s[:n], np.uint8))[0][:8]
                raise AssertionError(
                    f"step {k} (token {t}), slice {s}: DRAM differs at {diff.tolist()}")
        nxt = int(np.argmax(want))
        fed.append(t)
        produced.append(nxt)
        steps_out.append({"token": t, "next": nxt,
                          "logits_sha256": logits_sha256(want),
                          "dram_sha256": hashlib.sha256(
                              np.asarray(rtl.drams[0][:n], np.uint8).tobytes()).hexdigest()})
        t = nxt
    return {"fed": fed, "produced": produced, "steps": steps_out, "image_nbytes": n}
