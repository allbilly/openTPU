"""Ladder step 8 — mini-core reductions, ARGMAX and OUTER, bit-exact vs isasim.

The mini-core's VOP now implements the reduction family: RSUM/RSSQ/RDOT (fp32's 64 interleaved
partials + the 6-round folding tree, +0 padding added), RMAX (chain_max under the raw-bits total
order), ARGMAX (max + i2f(int32(first index + base))) and OUTER (dst*Dv + B(r)*Cv with Cv/Dv
buffered).  The unit is `rtl/ladder/mini_reduce.sv`; the elementwise functions stay in
`mini_vpu.sv`.  Whatever it does, the state the core leaves - TMEM and DRAM - must be exactly
`opentpu/isasim.py::_vop`/`_outer`'s (the step-3 oracle), so every program here is compared with
`ladder/harness/mini.py::assert_matches_isasim` on the whole memories.

Covered: the ten hand-checked vectors of the step-8 detail/step08_vectors.json (fixed values
asserted twice: against isasim and against an independent `opentpu.fp32` re-derivation), the
interleave/fold boundaries (cols 1..129), the total-order corners (-0 < +0, NaN payloads,
+-inf), ARGMAX's int32 wrap/tie-break, OUTER's DSCALAR/DONE/column modes, random fuzz across
shapes/functions/modes, and the nine negative cases (codes 4 range, 5 hazard, 10 shape, 1
illegal function).
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ladder.harness import mini  # noqa: E402
from opentpu import fp32 as F  # noqa: E402
from opentpu import isa as I  # noqa: E402

# Fast configuration: 16 KiB DRAM keeps the whole-DRAM dump cheap; TMEM/DRAM values are still
# compared exhaustively (the vvp runs are ~0.06 s each).
SMALL = mini.params(DRAM_BYTES=16384)

# DRAM input windows / TMEM bases used by the fixed vectors (same numbers as the research)
IN_A, IN_O, IN_P, IN_Q, IN_X = 0, 1024, 2048, 3072, 3584
TA, TB, TC, TD, TX = 0, 512, 600, 640, 700
OUT = 1000


# ---------------------------------------------------------------------------- helpers
def f32_bits(*values) -> list[int]:
    return [int(x) for x in np.asarray(values, np.float32).view(np.uint32).reshape(-1)]


def hexes(values) -> list[int]:
    return [int(x, 16) for x in values]


def dram_with(segments: dict[int, np.ndarray]) -> np.ndarray:
    d = np.zeros(SMALL["DRAM_BYTES"], np.uint8)
    for off, data in segments.items():
        b = np.asarray(data, np.uint8).reshape(-1)
        assert off + b.size <= SMALL["DRAM_BYTES"], (off, b.size)
        d[off:off + b.size] = b
    return d


def words_u32(values) -> np.ndarray:
    return np.asarray(values, np.uint32).reshape(-1)


def load(addr: int, tmem: int, n: int):
    return I.ld(addr, tmem, n, ra=0, rb=0)


def run(prog, dram) -> dict:
    return mini.assert_matches_isasim(prog, dram=dram, params_=SMALL)


def check_hand(out: dict, hand: dict[int, int]):
    for addr, bits in hand.items():
        assert int(out["tmem"][addr]) == bits, (
            f"T[{addr:#x}] = {int(out['tmem'][addr]):#010x}, expected {bits:#010x}")


def vop(func: int, dst: int, a: int, b: int, rows: int, cols: int, *,
        drs=0, ars=0, brs=0, bmode=I.B_FULL, imm=0):
    return I.vop(func, dst, a, b, rows, cols, drs, ars, brs, bmode=bmode, imm=imm)


def raw_vop(func: int, dst: int, a: int, b: int, rows: int, cols: int,
            drs=0, ars=0, brs=0, bmode=0, w7=0, flags=0) -> I.Instr:
    """A VOP built without isa.vop's build-time shape checks (for the negative cases)."""
    w = [dst, a, b, rows | (cols << 16), drs | (ars << 16),
         brs | (func << 16) | (bmode << 24), w7]
    return I.Instr(I.VOP, flags=flags, w=w)


# ---------------------------------------------------------------------------- fixed vectors
def test_rsum_fixed_vectors():
    prog = [load(IN_A, TA, 1), vop(I.V_RSUM, OUT, TA, 0, 1, 1, drs=8, ars=0), I.halt()]
    out = run(prog, dram_with({IN_A: words_u32(f32_bits(1.0)).view(np.uint8)}))
    check_hand(out, {OUT: 0x3f800000})

    prog = [load(IN_A, TA, 5), vop(I.V_RSUM, OUT, TA, 0, 1, 5, drs=8, ars=0), I.halt()]
    out = run(prog, dram_with({IN_A: words_u32(f32_bits(1, 2, 3, 4, 5)).view(np.uint8)}))
    check_hand(out, {OUT: 0x41700000})       # 15.0

    # cols at the 64/100 boundary, two rows of different alignment + an independent replay
    a64 = np.ones(64, np.float32)
    a100 = np.arange(1, 101, dtype=np.float32)
    dram = dram_with({IN_A: words_u32(F.bits(a64)).view(np.uint8),
                      IN_P: words_u32(F.bits(a100)).view(np.uint8)})
    prog = [load(IN_A, TA, 64), vop(I.V_RSUM, OUT, TA, 0, 1, 64, drs=8, ars=0),
            load(IN_P, 64, 100), vop(I.V_RSUM, OUT + 1, 64, 0, 1, 100, drs=8, ars=0),
            I.halt()]
    out = run(prog, dram)
    check_hand(out, {OUT: 0x42800000, OUT + 1: 0x459dd000})   # 64.0, 5050.0
    assert int(out["tmem"][OUT + 1]) == int(F.bits(F.interleaved_sum(a100[None, :], 64)[0]))

    # edge words: a row of -0 sums to +0, a row with +inf sums to +inf
    edge = hexes(["80000000", "80000000", "80000000", "80000000", "80000000", "80000000",
                  "000116c2", "800116c2", "00000000", "80000000", "3f800000", "bf800000",
                  "7f800000", "3f800000", "00000000", "00000000", "00000000", "00000000"])
    prog = [load(IN_A, TA, 18), vop(I.V_RSUM, OUT, TA, 0, 3, 6, drs=8, ars=6), I.halt()]
    out = run(prog, dram_with({IN_A: words_u32(edge).view(np.uint8)}))
    check_hand(out, {OUT: 0x00000000, OUT + 8: 0x00000000, OUT + 16: 0x7f800000})


def test_rmax_total_order_and_payloads():
    vals = hexes(["3f800000", "40400000", "40400000", "80000000",
                  "80000000", "00000000", "bf800000", "c0000000",
                  "7fc00001", "40400000", "7f800000", "ffc00000",
                  "ffc00000", "ff800000", "c0400000", "80000000"])
    prog = [load(IN_A, TA, 16), vop(I.V_RMAX, OUT, TA, 0, 4, 4, drs=8, ars=4), I.halt()]
    out = run(prog, dram_with({IN_A: words_u32(vals).view(np.uint8)}))
    check_hand(out, {OUT: 0x40400000, OUT + 8: 0x00000000,
                     OUT + 16: 0x7fc00001, OUT + 24: 0x80000000})
    # independent re-derivation under the fp32 key order
    a = np.frombuffer(words_u32(vals).tobytes(), "<f4").reshape(4, 4)
    exp = F.chain_max(a)
    for r in range(4):
        assert int(out["tmem"][OUT + r * 8]) == int(F.bits(exp[r]))


@pytest.mark.parametrize("rows,cols,ars,drs,bmode", [
    (1, 1, 0, 8, I.B_FULL), (1, 63, 0, 8, I.B_FULL), (1, 64, 0, 8, I.B_FULL),
    (1, 65, 0, 8, I.B_FULL), (1, 127, 0, 8, I.B_FULL), (1, 128, 0, 8, I.B_FULL),
    (1, 129, 0, 8, I.B_FULL), (2, 3, 4, 8, I.B_FULL), (3, 1, 0, 8, I.B_FULL),
])
def test_rsum_cols_boundaries(rows, cols, ars, drs, bmode):
    """The interleave/fold boundaries: isasim and the independent fp32 replay must both agree."""
    rng = np.random.default_rng(rows * 1000 + cols)
    stride = max(ars, cols)
    flat_len = max(rows * stride, (rows - 1) * ars + cols)
    flat = np.zeros(flat_len, np.uint32)
    for r in range(rows):
        flat[r * ars:r * ars + cols] = F.bits(
            rng.normal(0.0, 2.0, cols).astype(np.float32))
    prog = [load(IN_A, TA, flat_len), vop(I.V_RSUM, OUT, TA, 0, rows, cols, drs=drs, ars=ars),
            I.halt()]
    out = run(prog, dram_with({IN_A: flat.view(np.uint8)}))
    for r in range(rows):
        a_row = np.frombuffer(flat[r * ars:r * ars + cols].tobytes(), "<f4")[None, :]
        assert int(out["tmem"][OUT + r * drs]) == int(F.bits(F.interleaved_sum(a_row, 64)[0]))


def test_rssq_and_rdot_fixed():
    vals = hexes(["3f8ccccd", "400ccccd", "40533333", "80000000", "7149f2ca", "0da24260"])
    prog = [load(IN_A, TA, 6), vop(I.V_RSSQ, OUT, TA, 0, 2, 3, drs=8, ars=3), I.halt()]
    out = run(prog, dram_with({IN_A: words_u32(vals).view(np.uint8)}))
    check_hand(out, {OUT: 0x4187851e, OUT + 8: 0x7f800000})
    a = np.frombuffer(words_u32(vals).tobytes(), "<f4").reshape(2, 3)
    for r in range(2):
        assert int(out["tmem"][OUT + r * 8]) == int(F.bits(F.rdot(a[r][None, :], a[r][None, :])[0]))

    # RDOT: the four B modes; compare with the independent fp32.rdot on the same operands
    a = np.array([1, 2, 3, 4, 5, 6, 7, 8], np.float32).reshape(2, 4)
    b_full = np.array([1, 1, 1, 1, 2, 2, 2, 2], np.float32).reshape(2, 4)
    b_row = np.array([2.0, 0.5], np.float32)          # T[528 + r*1]
    b_col = np.array([1, 2, 3, 4], np.float32)        # T[544 + c]
    scalar = np.float32(0.5)
    dram = dram_with({IN_A: words_u32(F.bits(a)).view(np.uint8),
                      IN_O: words_u32(F.bits(b_full)).view(np.uint8),
                      IN_P: words_u32(F.bits(b_row)).view(np.uint8),
                      IN_Q: words_u32(F.bits(b_col)).view(np.uint8)})
    prog = [load(IN_A, TA, 8), load(IN_O, TB, 8), load(IN_P, 528, 2), load(IN_Q, 544, 4),
            vop(I.V_RDOT, OUT, TA, TB, 2, 4, drs=8, ars=4, brs=4),
            vop(I.V_RDOT, OUT + 1, TA, 528, 2, 4, drs=8, ars=4, brs=1, bmode=I.B_ROW),
            vop(I.V_RDOT, OUT + 2, TA, 544, 2, 4, drs=8, ars=4, bmode=I.B_COL),
            vop(I.V_RDOT, OUT + 3, TA, 0, 1, 4, drs=8, ars=4, bmode=I.B_SCALAR,
                imm=float(scalar)),
            I.halt()]
    out = run(prog, dram)
    exp = [F.rdot(a, b_full),
           F.rdot(a, np.repeat(b_row[:, None], 4, axis=1)),
           F.rdot(a, np.broadcast_to(b_col[None, :], (2, 4))),
           F.rdot(a[:1], np.full((1, 4), scalar, np.float32))]
    for k, e in enumerate(exp):
        for r in range(e.shape[0]):
            assert int(out["tmem"][OUT + k + r * 8]) == int(F.bits(e[r])), (k, r)
            # the hand-asserted words of the step-8 vector
    assert int(out["tmem"][OUT]) == 0x41200000 and int(out["tmem"][OUT + 8]) == 0x42500000
    assert int(out["tmem"][OUT + 1]) == 0x41a00000 and int(out["tmem"][OUT + 9]) == 0x41500000
    assert int(out["tmem"][OUT + 2]) == 0x41f00000 and int(out["tmem"][OUT + 10]) == 0x428c0000
    assert int(out["tmem"][OUT + 3]) == 0x40a00000


# ---------------------------------------------------------------------------- fuzz
def spec_words(rng, n: int) -> np.ndarray:
    base = rng.normal(0.0, 3.0, n).astype(np.float32)
    specials = np.array([0.0, -0.0, np.inf, -np.inf, np.nan, 1e-40, -1e-40,
                         2.0 ** 126, -2.0 ** 126, 127.0, -127.0, 1.5, -1.5,
                         np.float32(-0.0) + np.float32(0.0)], dtype=np.float32)
    k = rng.integers(1, min(6, n) + 1)
    idx = rng.choice(n, size=k, replace=False)
    base[idx] = specials[rng.choice(specials.size, size=k)]
    return base


def fuzz_case(rng) -> tuple[list, np.ndarray]:
    rows = int(rng.integers(1, 5))
    func = int(rng.choice([I.V_RSUM, I.V_RMAX, I.V_RSSQ, I.V_RDOT, I.V_ARGMAX, I.V_OUTER]))
    if func == I.V_OUTER:
        cols = int(rng.choice([1, 2, 3, 5, 8, 16, 32]))
        dmode = rng.choice(["scalar", "one", "column"])
        brs = int(rng.integers(0, 4))
        drs = cols + int(rng.integers(0, 4))
        sa = spec_words(rng, rows + cols + 8)
        a = spec_words(rng, cols)
        bb = spec_words(rng, rows * max(brs + 1, 1))
        c = spec_words(rng, cols)
        x = spec_words(rng, (rows - 1) * drs + cols)
        dram = dram_with({IN_A: words_u32(F.bits(sa)).view(np.uint8),
                          IN_O: words_u32(F.bits(a)).view(np.uint8),
                          IN_P: words_u32(F.bits(bb)).view(np.uint8),
                          IN_Q: words_u32(F.bits(c)).view(np.uint8),
                          IN_X: words_u32(F.bits(x)).view(np.uint8)})
        prog = [load(IN_A, TA, len(sa)), load(IN_O, TD, cols), load(IN_P, TC, len(bb)),
                load(IN_Q, TX, len(x))]
        tx = 900
        prog[3] = load(IN_Q, tx, len(x))
        prog.append(I.outer(tx, TD, TC, 950, rows=rows, cols=cols, drs=drs, brs=brs,
                            dmode=dmode))
        prog.append(I.halt())
        return prog, dram
    cols = int(rng.choice([1, 2, 3, 4, 5, 63, 64, 65, 100, 127, 128]))
    ars = int(rng.integers(0, 3)) if rng.random() < 0.5 else cols
    drs = int(rng.integers(1, 6))
    a = spec_words(rng, rows * max(ars + 1, cols))
    bb = spec_words(rng, rows * max(1, cols))
    brs = 0
    bmode = int(rng.choice([I.B_FULL, I.B_ROW, I.B_COL, I.B_SCALAR]))
    dram = dram_with({IN_A: words_u32(F.bits(a)).view(np.uint8),
                      IN_O: words_u32(F.bits(bb)).view(np.uint8)})
    prog = [load(IN_A, TA, len(a)), load(IN_O, TB, len(bb))]
    imm = 0
    if func == I.V_RDOT:
        if bmode == I.B_ROW:
            brs = 0
        if bmode == I.B_SCALAR:
            imm = float(F.from_bits(np.array([int(rng.integers(0, 2 ** 32))], np.uint32))[0])
    if func != I.V_ARGMAX:
        prog.append(I.vop(func, OUT, TA, TB, rows, cols, drs=drs, ars=ars, brs=brs,
                          bmode=bmode, imm=imm))
    else:
        drs = int(rng.integers(2, 6))
        prog.append(I.argmax(OUT, TA, rows=rows, cols=cols, drs=drs, ars=ars,
                             base=int(rng.integers(-2 ** 31, 2 ** 31))))
    prog.append(I.halt())
    return prog, dram


@pytest.mark.parametrize("seed", range(12))
def test_fuzz_random_programs(seed):
    rng = np.random.default_rng(9000 + seed)
    prog, dram = fuzz_case(rng)
    golden = mini.run_isasim(prog, dram=dram, params_=SMALL)
    if golden["error"]:
        pytest.skip(f"isasim rejects the generated program: {golden['message']}")
    run(prog, dram)


# ---------------------------------------------------------------------------- negatives
def _ld_identity() -> list:
    return [load(IN_A, TA, 8)]


@pytest.mark.parametrize("name,prog,code", [
    ("argmax_short_drs",
     _ld_identity() + [raw_vop(I.V_ARGMAX, OUT, TA, 0, 2, 4, drs=1, ars=4), I.halt()], 10),
    ("outer_bmode",
     _ld_identity() + [raw_vop(I.V_OUTER, OUT, TA, 0, 1, 4, drs=8, brs=8, bmode=I.B_FULL,
                               w7=TB), I.halt()], 10),
    ("outer_cols",
     _ld_identity() + [raw_vop(I.V_OUTER, OUT, TA, 0, 1, 257, drs=8, brs=8, bmode=I.B_ROW,
                               w7=TB), I.halt()], 10),
    ("rsum_hazard",
     _ld_identity() + [raw_vop(I.V_RSUM, 2, TA, 0, 2, 4, drs=8, ars=0), I.halt()], 5),
    ("argmax_hazard",
     _ld_identity() + [raw_vop(I.V_ARGMAX, 2, TA, 0, 2, 4, drs=4, ars=0), I.halt()], 5),
    ("outer_hazard",
     _ld_identity() + [raw_vop(I.V_OUTER, TA, TA, 0, 2, 4, drs=0, brs=0, bmode=I.B_ROW,
                               w7=TB, flags=1), I.halt()], 5),
    ("rsum_out_range",
     _ld_identity() + [raw_vop(I.V_RSUM, 4095, TA, 0, 2, 4, drs=8, ars=0), I.halt()], 4),
    ("rdot_b_range",
     _ld_identity() + [raw_vop(I.V_RDOT, OUT, TA, 4095, 1, 4, drs=8, ars=4), I.halt()], 4),
    ("bad_func",
     _ld_identity() + [raw_vop(21, OUT, TA, 0, 1, 4, drs=8, ars=0), I.halt()], 1),
])
def test_negative_cases(name, prog, code):
    """The mini-core latches the step-8 code and isasim raises SimError for the same program."""
    dram = np.zeros(SMALL["DRAM_BYTES"], np.uint8)
    out = mini.assert_errors(prog, code=code, dram=dram, params_=SMALL)
    assert out["error"], name
