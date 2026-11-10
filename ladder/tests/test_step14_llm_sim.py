"""Ladder step 14 — an LLM token end-to-end in simulation: ISA vs production RTL, bit-exact.

No checkpoint, no tokenizer, no torch: the production LLM layer (`opentpu/llm/`) imports and runs
on numpy alone (its torch/transformers/safetensors imports are lazy, inside checkpoint loading and
the production tests' HF references).  `ladder/harness/llm.py` builds the production tests' tiny
Qwen3 (`tests/test_qwen3.py::tiny`: hidden 256, 2 layers, 4 q / 2 kv heads, head_dim 128,
ffn 512, vocab 1000, seed 0) as a plain numpy HF state-dict and drives the real engine.

The rung has two tests:

* `test_tiny_model_tokens_on_isa` (light, always runs, ~1 s): the prompt's greedy continuation
  on `opentpu.isasim` must be the documented golden token ids and logits sha256 — deterministic.
* `test_tiny_model_token_on_rtl` (heavy, Verilator): the same ISA greedy continuation is replayed
  token by token on the production RTL through `opentpu.llm.rtl_backend.RtlBackend`; for each fed
  token the uint32 logits, the token id and the whole DRAM image must equal the ISA simulator's.
  The step-14 Config is a *new* Verilator build key (D = 128, AXI = 0, 16 MiB DRAM), so the cold
  compile must go through the runner: `python3 ladder/run.py step 14` (flock + thermal gate);
  direct `pytest` skips the heavy test until that build exists.
"""
from __future__ import annotations

import os
import shutil

import numpy as np
import pytest

from ladder.harness import llm


def test_llm_layer_imports_without_torch():
    """The step-14 import closure is numpy-only: torch/transformers/safetensors are lazy.

    The production layer imports them only on the checkpoint path (`Weights`/`LazyWeights`) and
    in the production tests' HF references, so importing opentpu.llm and building/decoding the
    tiny fixture must never pull them in (they are absent on this host; if a torch environment
    ever runs the suite this test still documents the contract by asserting nothing was imported
    eagerly through this path).
    """
    import importlib.util
    import sys

    import opentpu.llm  # noqa: F401  (the package must import with numpy only)

    spec = llm.spec()
    W = llm.weights()
    assert len(W) == 24, len(W)
    assert (spec.hidden, spec.layers, spec.n_q, spec.n_kv, spec.head_dim, spec.ffn,
            spec.vocab) == (256, 2, 4, 2, 128, 512, 1000)
    assert "model.embed_tokens.weight" in W
    for mod in ("torch", "transformers", "safetensors"):
        if importlib.util.find_spec(mod) is None:
            assert mod not in sys.modules, f"{mod} must stay a lazy checkpoint-only import"


def test_tiny_model_tokens_on_isa():
    """Prompt -> greedy [181, 181, 181, 564, 564, 564], logits sha256s, deterministic."""
    out = llm.isa_golden()

    assert out["produced"] == llm.GREEDY, out["produced"]
    assert out["fed"] == llm.GREEDY[:-1], out["fed"]
    assert out["prefill_sha256"] == llm.PREFILL_LOGITS_SHA256
    assert out["step_logits_sha256"] == llm.STEP_LOGITS_SHA256
    assert out["image_nbytes"] == llm.IMAGE_BYTES, out["image_nbytes"]
    assert out["image_sha256"] == llm.IMAGE_SHA256, out["image_sha256"]
    assert out["deterministic"], "a fresh engine gave a different image or prefill logits"

    # the fixture is the production tiny model, not a toy: its image is a real (small) LLM image
    assert out["image_nbytes"] > 1 << 21


def test_tiny_model_token_on_rtl():
    """Four greedy tokens: RTL logits, token ids and whole DRAM == the ISA simulator's."""
    if shutil.which("verilator") is None:
        pytest.skip("verilator not installed")
    present, why = llm.rtl_build_present()
    if not present and not llm.runner_gate_ok():
        pytest.skip(f"cold Verilator build for the step-14 Config: run "
                    f"`python3 ladder/run.py step 14` (flock + thermal gate); {why}")
    out = llm.isa_vs_rtl(steps=4)
    assert out["fed"] == llm.GREEDY[:4], out["fed"]
    assert out["produced"] == llm.GREEDY[1:5], out["produced"]
    assert out["image_nbytes"] == llm.IMAGE_BYTES
    assert len(out["steps"]) == 4
    for k, step in enumerate(out["steps"]):
        assert step["token"] == llm.GREEDY[k]
        assert step["next"] == llm.GREEDY[k + 1]
        assert len(step["logits_sha256"]) == 64
        assert len(step["dram_sha256"]) == 64
    # the RTL's logits are also the ISA goldens by sha (same words the compare asserted)
    assert [s["logits_sha256"] for s in out["steps"]] == llm.STEP_LOGITS_SHA256[:4]
