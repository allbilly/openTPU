# LLM inference in simulation (ladder step 14)

This rung puts a real language model on the production core in simulation: a tiny Qwen3 decodes
a prompt greedily on the ISA simulator, and the same tokens are replayed on the production RTL
through the product's own `opentpu.llm.rtl_backend.RtlBackend`.  For every decoded token the
**logits (raw fp32 words), the token id and the whole DRAM image must be identical** between the
two.  No checkpoint, no tokenizer and no `torch` are involved: the model is the production
tests' tiny random one, built as a numpy state-dict.

## Why a random tiny model is enough

The product's real checkpoints are not in the tree (they live in `models/`, gitignored and
downloaded separately), and the production LLM tests that build reference models in
`torch`/`transformers` cannot run on a numpy-only host (see below).  But the ISA simulator is the
*oracle*: whatever the model's weights are, the RTL must produce bit-identical results.  The
production tests already build tiny random models of every architecture
(`tests/test_qwen3.py::tiny`, `test_lfm2.py::tiny`, `test_qwen35.py::_tiny_model`, ...) for
exactly this reason — a small random model still runs the whole network path (embedding, RoPE,
GQA attention, QK-norm, MLP, int8 MX scales, quantized image, LM head) and is small enough to
run on the RTL in a simulation.

The ladder's fixture reproduces `tests/test_qwen3.py::tiny` without torch: the same
`Spec(hidden=256, layers=2, n_q=4, n_kv=2, head_dim=128, ffn=512, vocab=1000)`, the same HF
`state_dict` keys and shapes, `np.random.default_rng(0)` instead of `torch.manual_seed(0)`, linear
weights `~N(0, 0.02)`, norms `1 + 0.1*randn`, tied LM head.  `opentpu.llm.qwen3.Engine` takes that
dict directly — `load_spec`/`load_weights` (and with them safetensors/torch) are only the
checkpoint path and are skipped entirely.  Token ids are ordinary integers below `vocab`; greedy
decoding is `np.argmax` on the logits, so no tokenizer is needed either.

## Torch/transformers dependency verdict (verified)

Every `torch`, `transformers`, `safetensors` and `PIL` import in `opentpu/llm/` is **lazy**
(inside checkpoint loading in `Weights`/`LazyWeights`, multimodal image handling, or the tests'
HF reference models); `import opentpu.llm` and the engine/image/ISA/RTL path run with numpy only.
On this host `/usr/bin/python3` has numpy + pytest and **no** torch/transformers/safetensors
(no repo venv, no cached wheels, no network), so:

* the production tiny-model tests are `pytest.importorskip("torch")`/`transformers` and **skip**
  here — they are not part of this rung;
* a `torch` venv is not needed and cannot be built offline; if one ever exists, the production
  tests can serve as an extra HF cross-check, but the ladder's acceptance only compares the ISA
  oracle with the RTL.

## The token path and the exactness contract

Fixture: `ladder/harness/llm.py`.

1. **Fixture + image** — numpy weights and `Config(S=1, D=128, MCOLS=4, ACT_BLOCKS=128,
   ACT_ROWS=4, TMEM_WORDS=65536, IMEM_WORDS=32768, LANES=8, DRAM_BYTES=1<<24)`; `Engine(...,
   cap=256)`.  The Config is pinned explicitly instead of `board_config()`: the RTL Verilator
   build key includes every field and the environment (`OTPU_TARGET`, `OTPU_MCOLS`,
   `OTPU_LANES`, `OTPU_ACT_ROWS`, `OTPU_AXI`, ...), so relying on it would make the rung's build
   depend on the caller's shell.  The image is 2,218,112 bytes at the start of DRAM.
2. **ISA oracle** — prefill the prompt `[811, 85, 179, 236, 181]` on `opentpu.isasim` (the real
   production engine), then decode greedily.  The fixture's deterministic result is
   `[181, 181, 181, 564, 564, 564]`, prefill logits sha256 `3621798a...`.
3. **RTL replay** — for each fed token, snapshot the ISA machine's DRAM image, run the ISA step,
   then run the *same* token from the same DRAM image on
   `RtlBackend(cfg, drams, axi=False, boot=False)`, and compare: `uint32` logits (all 1000
   words), the token id (`argmax`), and the whole DRAM `[:image.nbytes]` (weights, quantized
   image and KV cache).  Four tokens are replayed; any difference is reported with the differing
   logits indices / DRAM byte addresses.
4. **Cache determinism** — `OTPU_IMAGE_CACHE`/`OTPU_IMG_CACHE`/`OTPU_PROG_CACHE` are forced to
   `0` by the harness before opentpu is imported, so both backends see a freshly built,
   bit-identical image and freshly compiled programs (the production `tests/conftest.py` does
   the same for its suite).

The light test (`test_tiny_model_tokens_on_isa`) asserts the golden tokens, the per-step logits
sha256s and that a fresh engine reproduces the prefill logits — so a fixture/engine drift is
caught without a Verilator build.  The heavy test (`test_tiny_model_token_on_rtl`) is the
exactness proof; it is a heavy rung (`ladder/run.py` step 14: flock + thermal gate).

## Heavy build notes

The tiny model runs with the board's D = 128 (the production MXU depth), so its Verilator build
is a **new build key**: `tb_top` with `S=1, D=128, MCOLS=4, ACT_BLOCKS=128, ACT_ROWS=4,
TMEM_WORDS=65536, IMEM_WORDS=32768, DRAM_WORDS=4_194_304, DRAM_LAT=8, LANES=8, AXI=0` (+ the
default `UARCH`), i.e. the behavioural-DRAM path, not the AXI board path.  The first run is a
cold Verilator compile (~minutes, 1-2 GB under `build/verilator/` in the tree); it must go
through the runner so the shared-host lock and the k10temp gate protect the laptop:

```
python3 ladder/run.py step 14            # cold: gate + build + both tests, writes the receipt
python3 ladder/run.py step 14 --warm     # later: build already present; thermal-only, no flock
```

`--warm`'s preflight asks `ladder.harness.llm.rtl_build_present()` (the exact `rtlsim.build_dir`
of this Config); the runner's generic fallback (no built-in probe for step 14) requires
`LADDER_WARM_OK=1`, which is unnecessary once the probe is wired.  A direct `pytest` of the
heavy test never compiles: without the runner's lock/`LADDER_PY` marker it skips with the
instruction to use the runner (a warm build proceeds without a gate).

Expected rung wall time: the ISA test ~1 s; the heavy test four single-token simulations on the
cached build (seconds each), plus the one-time compile.  Disk: 16 MiB DRAM images in the
simulation temp dir; the Verilator build tree is the large artefact.
