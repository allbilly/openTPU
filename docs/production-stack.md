# The production software stack (ladder step 10)

Step 10 imports the product's compiler, language, runtime, kernels and examples so that the
ladder stops hand-assembling programs: from this rung on a kernel is written in the `ol`
language, compiled to the real ISA and run on the bit-exact ISA simulator
(`opentpu/isasim.py`) or on the production RTL imported at step 9 (`opentpu/rtlsim.py`).

## What was imported (byte-identical unless noted)

From `ca05e24f` (the product tree), tracked files:

| path | role |
| --- | --- |
| `opentpu/language.py` | the Triton-style `ol` language (tiles, loops, `ol.load/store`) |
| `opentpu/compiler.py` | the compiler: tiles → ISA, loops, run variables, peepholes |
| `opentpu/runtime.py` | host runtime: argument placement, `compile_kernel`, `run`, readback |
| `opentpu/waits.py` | the sequencer's wait entries (the compiler emits WAITCs; ISA-only use here) |
| `opentpu/reference.py` | float64 numpy reference for the kernels (used by the tests) |
| `opentpu/kernels/` | `mlp`, `attention_decode`, `attention_layer`, `lib` (rmsnorm/silu/rope), layouts, pieces, vit, deltanet, gather, mailbox (10 files) |
| `examples/` | the 11 small operation examples + `run_all.py` + shared `_common.py` runner |
| `tests/test_kernels.py`, `tests/test_compiler.py`, `tests/test_basic_examples.py` | the production pure-Python suites, ported (see below) |

Already on the ladder: `opentpu/{fp32,quant,isa,isasim}.py` (steps 3-5) and
`opentpu/{rtlsim,simtmp,target}.py`, `targets/` (step 9). The whole import closure of the
software stack is 15 Python files with **numpy only** as a third-party dependency — the
production kernels/compiler are pure numpy, no torch. (`opentpu/kernels/gather.py` imports
`opentpu.qcache` and `kernels/mailbox.py` imports `opentpu.host.offload`; both arrive at later
rungs, and `opentpu/kernels/__init__.py` imports only `attention`/`mlp`, so importing the
kernel package works now. Those two modules fail only if imported directly; they are not used at
step 10.)

### Provenance caveat

`examples/` and `tests/test_basic_examples.py` are **untracked in the product working tree**
(they ship only as files, not in any `ca05e24f` commit). They were copied from
`/home/fedora/openTPU` with these sha256 values recorded for the step-16 convergence decision:

```
37068b9173576fc1dc763eb4491dfa7282c5b7581f219b6efcd07e22ba7f90cf  examples/_common.py
3b0fd763b528356c36f89a1eb03f64bb8733d54817b693bbcceaaa2b1e0d4b46  examples/conv.py
b951a5421854bf2693126bcdd841691ef0508191a073bdb44c000cdbe130073d  examples/elementwise.py
40d4ae9940ccbe9135814d575a3ddb509f53188d215dfd626b9651fca94ac610  examples/gemm.py
f893b6f1a93476546380ce25aa80e369cfc92332916b489804cd1485d3d3bb8f  examples/pooling.py
94ec2a02d0dfa7d0d0c8c8f4420166381cc704395cce864ca79bcdf17eea3737  examples/rmsnorm.py
d1b2c526a759213b7d038bcdfd0350e436d8eb6d0fc4f551165ff8e680ab80c9  examples/run_all.py
a8cf9473c4723c3610f78960b6d1ef07904d1716debc30a8126ed61a9130fe70  examples/simple_add.py
3087f00690589d054f2a0edea9de5ef31f9bd15fba3391fcdbfed8027216032b  examples/softmax.py
796c8fdafcdb1a1f827b9a6c4cdccd04f96f6e5d90eb7a0ab83db7d81df38131  examples/README.md
```
At step 16 the convergence check compares against the *tracked* `ca05e24f` tree; these files are
ladder-only copies and the Lead must decide whether to keep them (`ladder/examples/`) or drop
them from the product-layout parity set. The step-10 contract does not depend on that choice.

## Test contract (`ladder/tests/test_step10_*`)

* `test_step10_compiler_kernels.py` — the ladder's own suite:
  * a compiled MLP on the ISA simulator vs its numpy reference (`rel < 0.02`),
  * compilation determinism (same kernel → same program words and DRAM images) and two runs of
    the same compiled program leaving identical state,
  * a fixed-vector exact result (the examples' VPU add: compiled output == `a + b` exactly),
  * `examples/run_all.py --backend isa` in a subprocess: PASS over all 14 cases,
  * **production-RTL replay** (heavy): the MLP and a small attention decode compiled for
    `ladder.harness.prod.CFG` (the step-9 production Config) and run through
    `opentpu.runtime.run(..., backend="rtl")` = `opentpu.rtlsim`; every DRAM byte and TMEM word
    must equal the ISA simulator's, and the retired-instruction counts must match. The Config is
    exactly the step-9 Verilator build's key, so the step-9 cache is reused (no second build).
    In a fresh worktree the cache is shared by pointing `build/verilator` at the step-9
    worktree's `build/verilator` (a symlink; `rtlsim.build_dir` keys on the sources' tree-relative
    names + contents + parameters + Verilator version, all identical here), so the heavy rung
    costs only the two RTL runs, not a rebuild.
* `test_step10_kernels.py` — the production `tests/test_kernels.py`, byte-for-byte except the
  `rel()` helper is local (the product's conftest imports step-11 host modules).
* `test_step10_compiler.py` — the production `tests/test_compiler.py`, unchanged.
* `test_step10_examples.py` — the production `tests/test_basic_examples.py`, retargeted to this
  tree's `examples/`; the two cases that import `opentpu.host.runtime_transport/runtime_model`
  are skipped until step 11.
* The production `tests/test_target.py` (imports `opentpu.host.board/fake`) and
  `tests/test_formats.py` (imports `opentpu.llm.formats`) are deferred to steps 11 and 14.
  The step-3 ISA/fp32/quant adaptations are kept as-is (the production originals are byte-
  compatible but the step-3 tests are the ladder's recorded contract).

## Heavy / host notes

Everything that touches `opentpu.rtlsim` (the two RTL replays) builds/runs Verilator and is
therefore only executed through `python3 ladder/run.py step 10`, which takes the shared-host
lock `/tmp/rknpu-heavy.lock` after the k10temp check. The tests skip unless the runner is the
parent (`LADDER_PY` set), so a bare `pytest` invocation cannot start an unlocked heavy build.
The ISA-only tests and the examples subprocess run without any lock; the whole step-10 suite is
green in ~60-90 s on this host plus the (cached) RTL runs.

`OTPU_IMAGE_CACHE` / `OTPU_IMG_CACHE` / `OTPU_PROG_CACHE` are forced to 0 before importing
`opentpu`, as the production conftest does: a cached image or program must never mask compiler
drift in the tests.
