"""Ladder step 7 — mini-core MXU: int8 MM with MX scales and the fp32 epilogue.

The mini-core (`rtl/ladder/mini_*.sv`, `sim/ladder/tb_mini.sv`) now executes MM (0x20) for the
int8 weight format (WF 0) with the UNIT / ACC / RMAX flags: exact integer block accumulation
with the W = 16 shift window, per-row Sw and per-block dw scale rows (k0 offsets the dw byte
only), four da sub-block bytes per ACT block, and the fp32 epilogue in isasim's association
(y = fp_mul(fp_mul(i2f48(acc), Sw), fp_mul(Sa, 2^-16))).  The state it leaves must be exactly
the ISA simulator's (`opentpu/isasim.py::_mm`, the step-3 oracle): whole TMEM, whole DRAM and,
through step 6's harness dump, the whole ACT RAM (bytes, Sa words, da bytes) — word for word.

Golden vectors: the 10 positive + 16 negative cases generated and double-verified by
`/tmp/ladder-plan/step07_vectors.py` (isan `opentpu/isa.py` LD->QACT->MM programs, run on
isasim, and re-derived independently from the docs/isa.md MM formula with opentpu/fp32.py;
`step07_vectors.json` is its output).  They are embedded below as a zlib+base64 blob: each
positive case carries its program words, the DRAM data it uses (as segments), its expected
icount/TMEM words/ACT state, so this suite is meaningful without the oracle as well.

Also covered: random/fuzz programs (LD -> QACT -> 1-2 MMs, UNIT/ACC/RMAX, ROW and non-ROW
QACT, hand-written scale rows, k0>0, padded rs/srs, ors>=N) compared whole-state against
isasim; a numpy int64 cross-check of the accumulation; the negative cases with the ladder's
error codes 8 (unsupported flag/format) and 9 (bounds/alignment/Sa consistency) and 4 (TMEM);
and the documented serialized ACC limitation (ors >= N).
"""
from __future__ import annotations

import base64
import json
import sys
import zlib
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ladder.harness import mini  # noqa: E402
from opentpu import Config, fp32 as F, isa as I  # noqa: E402
from opentpu.isasim import Machine, SimError  # noqa: E402

# the golden vectors' configuration: D=32, MCOLS=4, ACT_BLOCKS=16, ACT_ROWS=4, 4096-word TMEM,
# 256 KiB DRAM (mini.DEFAULT_PARAMS is exactly that)
SPEC = mini.DEFAULT_PARAMS
D = SPEC["D"]
ACT_ROWS = SPEC["ACT_ROWS"]
ACT_BLOCKS = SPEC["ACT_BLOCKS"]
TMEM_WORDS = SPEC["TMEM_WORDS"]
MCOLS = SPEC["MCOLS"]

IN, WA, SA, OUT = 16384, 0, 8192, 1024      # the golden vectors' DRAM/TMEM layout

# the golden vectors, /tmp/ladder-plan/step07_vectors.json (see the module docstring)
_VECTORS_B64 = (
    "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"
)

VEC = json.loads(zlib.decompress(base64.b64decode("".join(_VECTORS_B64))))
POS = VEC["positive"]
NEG = VEC["negative"]


# ---------------------------------------------------------------------------- fixtures / helpers
def prog_words(case) -> list[int]:
    return [int(w, 16) for w in case["program_words"]]


def dram_image(case) -> np.ndarray:
    """The case's DRAM: zeros plus the fixture's nonzero segments."""
    dram = np.zeros(SPEC["DRAM_BYTES"], dtype=np.uint8)
    for off, h in case["segments"]:
        b = np.frombuffer(bytes.fromhex(h), dtype=np.uint8)
        dram[off:off + len(b)] = b
    return dram


def act_rows(out) -> np.ndarray:
    """The RTL ACT bytes as [ACT_ROWS, ACT_BLOCKS*D] int8."""
    return np.frombuffer(out["act"].tobytes(), dtype=np.int8).reshape(ACT_ROWS, -1)


def assert_golden_state(out, case) -> None:
    """Every expected word of the fixture's recorded isasim/ref state."""
    assert out["halted"] and not out["error"], (case["name"], out["code"])
    assert out["icount"] == case["icount"], (case["name"], out["icount"], case["icount"])
    for addr_hex, want_hex in case["tmem_words"].items():
        addr = int(addr_hex, 16)
        got = int(out["tmem"][addr])
        assert got == int(want_hex, 16), (
            f"{case['name']}: TMEM[{addr:#x}] rtl={got:08x} golden={int(want_hex, 16):08x}")
    act = act_rows(out)
    for r, h in enumerate(case["act_rows"]):
        want = np.frombuffer(bytes.fromhex(h), dtype=np.int8)
        assert np.array_equal(act[r][:len(want)], want), f"{case['name']}: ACT row {r}"
    for r in range(ACT_ROWS):
        h = case["adoff_rows"][r]
        want = np.frombuffer(bytes.fromhex(h), dtype="<u4", count=2)
        base = r * ACT_BLOCKS
        got = out["adoff"][base:base + 2]
        assert np.array_equal(got, want), f"{case['name']}: adoff row {r}"
    for r in range(ACT_ROWS):
        for b in range(2):
            want = int(case["ascale_bits"][r * 2 + b], 16)
            got = int(out["ascale"][r * ACT_BLOCKS + b])
            assert got == want, f"{case['name']}: ascale[{r}][{b}] rtl={got:08x} golden={want:08x}"


def run_and_compare(case) -> dict:
    """Run the case on the mini-core and on isasim; assert the whole state is bit-identical."""
    prog, dram = prog_words(case), dram_image(case)
    out = mini.run(prog, dram=dram, params_=SPEC)
    golden = mini.run_isasim(prog, dram=dram, params_=SPEC)
    problems = mini.compare(out, golden)
    if not golden["error"] and not out["error"]:
        for name in ("act", "ascale", "adoff"):
            if not np.array_equal(out[name], golden[name]):
                problems.append(f"the ACT RAM's {name} differs from isasim")
    assert not problems, f"{case['name']}:\n" + "\n".join(problems)
    return out


# ---------------------------------------------------------------------------- golden vectors
@pytest.mark.parametrize("case", POS, ids=[c["name"] for c in POS])
def test_golden_vectors(case):
    """The recorded vectors: mini-core state == golden state, and == isasim bit for bit."""
    out = run_and_compare(case)
    assert_golden_state(out, case)
    # the vector's own hand values (from the generator): the identity case's ACT row bytes
    if case["name"] == "unit_identity_m1n1kb1":
        want = [0] + list(range(1, 31)) + [127]
        assert [int(x) for x in act_rows(out)[0][:32]] == want
        assert int(out["tmem"][OUT]) == int(case["tmem_words"]["0400"], 16)


def test_unit_identity_integer_readback():
    """The simplest hand case: ACT q[0..30, 127] times w[3] = 1 with W = 16.

    acc = 3 << 16 (the golden generator's `acc_units`), and the epilogue's three multiplies
    turn it into 0x3cc18306 — a value computed here from the formula, not read from a dump:
    Sa = 1/127 (the row's amax was 1.0), so y = fp32(3 * 2^16) * (1/127 * 2^-16).
    """
    # Sa of a row whose amax is exactly 1.0 is fp32(1/127), the quantizer's row scale
    sa = np.float32(F.quantize(np.array([[1.0] + [0.0] * (D - 1)], np.float32))[1][0])
    assert int(F.bits(sa)) == 0x3C010204
    want = F.mul(F.mul(F.i2f(np.int64(3 << 16)), np.float32(1.0)),
                 F.mul(sa, np.float32(2.0 ** -16)))
    assert int(np.uint32(np.asarray(F.bits(want)).reshape(-1)[0])) == 0x3CC18306


# ---------------------------------------------------------------------------- fuzz
def _rand_fp32(rng, n):
    """Random fp32 words: half good-scaled normals (composites stay in range), half raw bits,
    with a few documented corners mixed in."""
    w = rng.integers(0, 1 << 32, n, dtype=np.uint32)
    e = rng.integers(100, 161, n, dtype=np.uint32)
    m = rng.integers(0, 1 << 23, n, dtype=np.uint32)
    s = rng.integers(0, 2, n, dtype=np.uint32)
    good = ((s << 31) | (e << 23) | m).astype(np.uint32)
    w = np.where(rng.random(n) < 0.6, good, w)
    edges = np.array([0x00000000, 0x80000000, 0x00000001, 0x7F800000, 0xFF800000, 0x3F800000,
                      0xBF800000, 0x40000000], np.uint32)
    for k in range(0, n, 23):
        w[k] = edges[(k // 23) % len(edges)]
    return w


def build_fuzz_program(rng, *, n_mm: int = 1) -> tuple[list, np.ndarray]:
    """A random LD -> QACT -> MM(s) -> HALT program and its DRAM image.

    Everything is in range by construction: the ACT rows come from the QACT, the weights and
    scale rows sit in their own DRAM windows, the output TMEM window is computed from the
    shape.  The MM(s) use only features the golden vectors prove (int8 WF, UNIT/ACC/RMAX,
    ors >= N)."""
    rows = int(rng.integers(1, ACT_ROWS + 1))
    kb = int(rng.integers(1, 3))
    ab = int(rng.integers(0, ACT_BLOCKS - kb + 1))
    n = int(rng.integers(1, 5))
    m = int(rng.integers(1, rows + 1))
    ors = int(rng.integers(n, n + 4))
    rs = int(rng.choice([32, 64, 96]))
    srs = int(rng.choice([16, 32, 64]))
    k0 = int(rng.integers(0, 2))
    unit = bool(rng.integers(0, 2))
    rmax = bool(rng.integers(0, 2)) and m <= MCOLS
    row_mode = bool(rng.integers(0, 2))
    out = int(rng.integers(1024, 1024 + (TMEM_WORDS - 1024 - (m + 2) * ors - n)))

    dram = np.zeros(SPEC["DRAM_BYTES"], dtype=np.uint8)
    # the QACT input: rows x kb*D fp32 words at IN
    x = _rand_fp32(rng, rows * kb * D).view(np.float32)
    # make the row ampitudes varied but finite: scale every 8 words by 2^k
    scale = np.exp2(rng.integers(-8, 9, size=(rows * kb * D) // 8, dtype=np.int32)).astype(
        np.float32)
    with np.errstate(over="ignore", invalid="ignore"):
        x = (x * np.repeat(scale, 8)).astype(np.float32)
    x = F.ftz(x)
    dram[IN:IN + x.nbytes] = x.view(np.uint8)
    # streamed int8 weights at WA, one rs-byte row a weight row (the rest of the row is padding)
    for wrow in range(n):
        base = WA + wrow * rs
        w = rng.integers(-128, 128, kb * D, dtype=np.int16).astype(np.int8)
        dram[base:base + kb * D] = w.view(np.uint8)
        if not unit:
            sb = SA + wrow * srs
            sw_bits = np.array([int(rng.choice([0x3F800000, 0x3F000000, 0x40000000,
                                                0x3E800000, 0xBF800000, 0x40400000]))],
                               np.uint32)
            dram[sb:sb + 4] = sw_bits.view(np.uint8)
            for k in range(kb):
                dram[sb + 4 + k0 + k] = int(rng.integers(0, 18))   # dw 0..17: sh 16..-1

    prog = [I.ld(IN, 0, rows * kb * D),
            I.qact(0, rows, ab, kb, kb * D, row=row_mode)]
    # one or two MMs: the second one (ACC) adds into the first one's output
    for i in range(n_mm):
        prog.append(I.mm(WA, SA, out, n, kb, rs, ors, m, ab, srs,
                         unit=unit, acc=(i > 0), rmax=rmax and i == n_mm - 1))
    prog.append(I.halt())
    return prog, dram


def test_fuzz_against_isasim():
    """>= 16 random programs, whole TMEM + DRAM + ACT state bit-identical to isasim."""
    rng = np.random.default_rng(0x57DE7)
    accepted = attempts = 0
    while accepted < 16 and attempts < 80:
        attempts += 1
        prog, dram = build_fuzz_program(rng, n_mm=int(rng.integers(1, 3)))
        out = mini.run(prog, dram=dram, params_=SPEC)
        golden = mini.run_isasim(prog, dram=dram, params_=SPEC)
        if golden["error"]:
            continue                       # a rejected random shape: draw another
        problems = mini.compare(out, golden)
        for name in ("act", "ascale", "adoff"):
            if not np.array_equal(out[name], golden[name]):
                problems.append(f"the ACT RAM's {name} differs from isasim")
        assert not problems, (f"random program #{accepted} (attempt {attempts}):\n"
                              + "\n".join(problems))
        accepted += 1
    assert accepted >= 16, f"only {accepted} random programs ran"


def test_numpy_cross_check_unit():
    """UNIT: whatever the ACT bytes and weights are, acc = sum_i act_i * w_i and the epilogue is
    the three fp32 multiplies.  Checks the addressing/accumulation order independently of
    isasim's vectorized MM code (the ACT bytes themselves come from the oracle)."""
    rng = np.random.default_rng(11)
    rows, kb, n, m, rs, ors, ab = 2, 2, 2, 2, 64, 3, 1
    x = F.ftz(rng.standard_normal(rows * kb * D).astype(np.float32) * 0.5)
    dram = np.zeros(SPEC["DRAM_BYTES"], dtype=np.uint8)
    dram[IN:IN + x.nbytes] = x.view(np.uint8)
    w = rng.integers(-128, 128, size=(n, kb * D)).astype(np.int8)
    for k in range(n):
        dram[WA + k * rs:WA + k * rs + kb * D] = w[k].view(np.uint8)
    out_addr = 1024
    prog = [I.ld(IN, 0, rows * kb * D), I.qact(0, rows, ab, kb, kb * D, row=True),
            I.mm(WA, SA, out_addr, n, kb, rs, ors, m, ab, 64, unit=True), I.halt()]
    out = mini.run(prog, dram=dram, params_=SPEC)
    golden = mini.run_isasim(prog, dram=dram, params_=SPEC)
    assert not out["error"] and not golden["error"]
    # the oracle's ACT bytes/scales (the quantizer, not the MXU)
    act = np.asarray(golden["act"], np.uint8).reshape(ACT_ROWS, ACT_BLOCKS * D).view(np.int8)
    ascale = golden["ascale"].astype(np.uint32).view(np.float32).reshape(ACT_ROWS, ACT_BLOCKS)
    adoff = np.asarray(golden["adoff"], np.uint32).reshape(ACT_ROWS, ACT_BLOCKS)
    wrows = np.stack([np.frombuffer(dram[WA + k * rs:WA + k * rs + kb * D].tobytes(), np.int8)
                      for k in range(n)])
    for j in range(m):
        sa = np.float32(ascale[j, ab])
        for kk in range(n):
            acc = 0
            for blk in range(kb):
                for g in range(4):
                    c = int(np.dot(act[j][(ab + blk) * D + g * 8:(ab + blk) * D + (g + 1) * 8]
                                   .astype(np.int64),
                                   wrows[kk][blk * D + g * 8:blk * D + (g + 1) * 8].astype(np.int64)))
                    da = int(adoff[j, ab + blk] >> (8 * g) & 0xFF)
                    sh = 16 - da
                    if sh >= 0:
                        acc += c << sh
            want = F.mul(F.mul(F.i2f(np.int64(acc)), np.float32(1.0)),
                         F.mul(sa, np.float32(2.0 ** -16)))
            want_bits = int(np.uint32(np.asarray(F.bits(want)).reshape(-1)[0]))
            got = int(out["tmem"][out_addr + j * ors + kk])
            assert got == want_bits, (j, kk, hex(got), hex(want_bits))


def test_unit_skips_scale_row_checks():
    """UNIT reads no scale rows: an unaligned/garbage ssa and srs must not error (detail 1.2/6).
    The ACT Sa and da still apply and the result equals isasim's."""
    rng = np.random.default_rng(3)
    x = F.ftz(rng.standard_normal(D).astype(np.float32))
    dram = np.zeros(SPEC["DRAM_BYTES"], dtype=np.uint8)
    dram[IN:IN + x.nbytes] = x.view(np.uint8)
    w = rng.integers(-128, 128, D, dtype=np.int16).astype(np.int8)
    dram[WA:WA + D] = w.view(np.uint8)
    # ssa=1, srs=2: neither is 4-byte aligned, and they must not be used at all
    prog = [I.ld(IN, 0, D), I.qact(0, 1, 0, 1, D, row=False),
            I.mm(WA, 1, OUT, 1, 1, D, 16, 1, 0, 2, unit=True), I.halt()]
    out = mini.run(prog, dram=dram, params_=SPEC)
    golden = mini.run_isasim(prog, dram=dram, params_=SPEC)
    assert not out["error"] and not golden["error"], (out["code"],)
    assert not mini.compare(out, golden)


# ---------------------------------------------------------------------------- errors
@pytest.mark.parametrize("case", NEG, ids=[c["name"] for c in NEG])
def test_negative_vectors(case):
    """The bad programs: the mini code from the golden plan, and isasim's own verdict."""
    prog, dram = prog_words(case), dram_image(case)
    out = mini.run(prog, dram=dram, params_=SPEC)
    assert out["error"], f"{case['name']}: the mini-core did not error"
    assert out["code"] == case["mini_code"], (
        f"{case['name']}: mini code {out['code']}, expected {case['mini_code']}")
    golden = mini.run_isasim(prog, dram=dram, params_=SPEC)
    if case["mini_only"]:
        # unsupported formats/flags: isasim implements them, the mini-core rejects them
        assert not golden["error"], f"{case['name']}: isasim should accept this program"
    else:
        assert golden["error"], f"{case['name']}: isasim should raise SimError"


def test_acc_serialized_read_before_write():
    """The documented serialized limitation: isasim reads all ACC values before writing, so the
    serialized core is bit-exact only for distinct output addresses (ors >= N).  This is the
    (passing) ors == N boundary; a program with ors < N aliasing its rows is out of scope."""
    rng = np.random.default_rng(7)
    x = F.ftz(rng.standard_normal(2 * D).astype(np.float32))
    dram = np.zeros(SPEC["DRAM_BYTES"], dtype=np.uint8)
    dram[IN:IN + x.nbytes] = x.view(np.uint8)
    w = rng.integers(-128, 128, 2 * D, dtype=np.int16).astype(np.int8)
    dram[WA:WA + 2 * D] = w.view(np.uint8)
    prog = [I.ld(IN, 0, 2 * D), I.qact(0, 2, 0, 1, D, row=True),
            I.mm(WA, SA, OUT, 2, 1, D, 2, 2, 0, 64, unit=True),
            I.mm(WA, SA, OUT, 2, 1, D, 2, 2, 0, 64, unit=True, acc=True), I.halt()]
    out = mini.run(prog, dram=dram, params_=SPEC)
    golden = mini.run_isasim(prog, dram=dram, params_=SPEC)
    assert not out["error"] and not golden["error"]
    assert not mini.compare(out, golden)
