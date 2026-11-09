"""Ladder step 5 — mini-core VPU: elementwise fp32 in all four B-operand modes.

The mini-core (`rtl/ladder/mini_*.sv`, `sim/ladder/tb_mini.sv`) now executes VOP for the 14
elementwise functions: ADD, SUB, RSUB, MUL, MAX, MIN, COPY, EXP2, RECIP, RSQRT, ABS, FILL,
EXP2SUB and LOG2, each with the FULL / ROW / COL / SCALAR B-operand modes.  The arithmetic is
the product tree's `otpu_fp` package, copied verbatim (rtl/ladder/otpu_fp.sv), so the state the
VPU leaves must be exactly the ISA simulator's (`opentpu/isasim.py`'s `_vop`, the oracle from
step 3): whole TMEM and whole DRAM, word for word, plus the retired-instruction count.

Covered here: fixed golden values per function (so the suite means something on its own),
random and corner-case bit patterns over all functions x modes x shapes compared bit-for-bit
with `isasim`, the four B modes with explicit expectations, unusual strides, the
read-after-write hazard (error 5, the mini-core's own code: `isasim` raises SimError too),
TMEM range errors (code 4) and the functions left to step 8 (reductions / ARGMAX / OUTER).
"""
from __future__ import annotations

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

# fast configuration: the core parameters with a 16 KiB DRAM, so a run's whole-DRAM dump stays
# cheap (the state comparison is still exhaustive: every TMEM word and every DRAM byte).
SMALL = mini.params(DRAM_BYTES=16384)

# DRAM windows for the operands / the ST result, and the TMEM windows the VPU works in.
# TMEM_WORDS is 4096: A [0, 1024), B [1024, 2048), the destination [2048, 3072).
A_DRAM, B_DRAM, OUT_DRAM = 0x0000, 0x1000, 0x2000
A_T, B_T, DST_T = 0, 1024, 2048

FUNCS = [I.V_ADD, I.V_SUB, I.V_RSUB, I.V_MUL, I.V_MAX, I.V_MIN, I.V_COPY, I.V_EXP2,
         I.V_RECIP, I.V_RSQRT, I.V_ABS, I.V_FILL, I.V_EXP2SUB, I.V_LOG2]
# isasim's is_binary(): the functions that read operand B.  The others read A only, so the VPU
# never reads B for them whatever the mode says.
READS_B = {I.V_ADD, I.V_SUB, I.V_RSUB, I.V_MUL, I.V_MAX, I.V_MIN, I.V_FILL, I.V_EXP2SUB}
MODES = [I.B_FULL, I.B_ROW, I.B_COL, I.B_SCALAR]
SHAPES = [(1, 1), (3, 37), (8, 64), (4, 256)]      # (rows, cols)


# ---------------------------------------------------------------------------- helpers
def u32_words(values) -> list[int]:
    """fp32 bit patterns (uint32 list) from Python floats / ints."""
    return [int(x) for x in np.asarray(values, dtype=np.float32).view(np.uint32).reshape(-1)]


def tile_dram(a_words: np.ndarray, b_words: np.ndarray) -> np.ndarray:
    """A DRAM image with the A tile at A_DRAM and the B tile at B_DRAM."""
    dram = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    a = np.asarray(a_words, np.uint32).view(np.uint8).reshape(-1)
    b = np.asarray(b_words, np.uint32).view(np.uint8).reshape(-1)
    dram[A_DRAM:A_DRAM + a.size] = a
    dram[B_DRAM:B_DRAM + b.size] = b
    return dram


def b_tile_size(rows: int, cols: int, bmode: int, brs: int) -> int:
    """Words the B operand occupies in TMEM for this mode (0 for SCALAR)."""
    if bmode == I.B_SCALAR:
        return 0
    if bmode == I.B_FULL:
        return (rows - 1) * brs + cols
    if bmode == I.B_ROW:
        return (rows - 1) * brs + 1
    return cols                                       # B_COL: b + c


def run_vop(func: int, rows: int, cols: int, a_words, b_words=None,
            bmode: int = I.B_FULL, imm: float = 0.0,
            drs: int | None = None, ars: int | None = None,
            brs: int | None = None, params_=SMALL) -> dict:
    """Run one VOP on the mini-core and on isasim; assert every word of the final state matches.

    Program: LD the A tile (and the B tile when the function reads B) into TMEM, the VOP, ST the
    destination window to DRAM, HALT.  The A window is `rows*ars` words, the destination
    `rows*drs`; the comparison is the harness's whole-TMEM + whole-DRAM + icount equality.
    """
    ars = cols if ars is None else ars
    drs = cols if drs is None else drs
    brs = cols if brs is None else brs
    n_a = (rows - 1) * ars + cols
    n_b = b_tile_size(rows, cols, bmode, brs)
    assert n_a <= B_T and n_b <= DST_T - B_T and (rows - 1) * drs + cols <= len(
        range(DST_T, 4096)), "test windows do not fit TMEM"

    prog = [I.ld(A_DRAM, A_T, n_a)]
    if b_words is not None and func in READS_B and bmode != I.B_SCALAR:
        prog.append(I.ld(B_DRAM, B_T, n_b))
    prog += [I.vop(func, DST_T, A_T, B_T, rows, cols, drs, ars, brs, bmode, imm),
             I.st(OUT_DRAM, DST_T, (rows - 1) * drs + cols),
             I.halt()]
    dram = tile_dram(a_words, b_words if b_words is not None else np.zeros(0, np.uint32))
    out = mini.assert_matches_isasim(prog, dram=dram, params_=params_)
    assert out["halted"] and not out["error"]
    return out


def dst_words(out: dict, rows: int, cols: int, drs: int | None = None) -> np.ndarray:
    """The destination tile as raw fp32 bits, read out of DRAM (the ST wrote it there)."""
    drs = cols if drs is None else drs
    n = (rows - 1) * drs + cols
    raw = np.frombuffer(out["dram"][OUT_DRAM:OUT_DRAM + 4 * n].tobytes(), "<u4")
    return raw


def tmem_f32(out: dict, start: int, n: int) -> np.ndarray:
    """n TMEM words as float32 values (the dump is raw 32-bit words)."""
    return out["tmem"][start:start + n].view(np.float32)


# ---------------------------------------------------------------------------- fixed goldens
@pytest.mark.parametrize("func,a,b,want", [
    (I.V_ADD, [1.5], [2.25], [3.75]),
    (I.V_SUB, [1.5], [2.25], [-0.75]),
    (I.V_RSUB, [1.5], [2.25], [0.75]),
    (I.V_MUL, [0.1], [0.2], [np.float32(0.1) * np.float32(0.2)]),
    (I.V_MAX, [1.5], [2.25], [2.25]),
    (I.V_MIN, [1.5], [2.25], [1.5]),
    (I.V_COPY, [-2.5], [0.0], [-2.5]),
    (I.V_EXP2, [1.0], [0.0], [2.0]),
    (I.V_RECIP, [2.0], [0.0], [0.5]),
    (I.V_RSQRT, [4.0], [0.0], [0.5]),
    (I.V_ABS, [-2.5], [0.0], [2.5]),
    (I.V_FILL, [0.0], [7.5], [7.5]),
    (I.V_EXP2SUB, [0.5], [0.25], [F.exp2(np.float32(0.25))]),
    (I.V_LOG2, [8.0], [0.0], [3.0]),
], ids=lambda x: I.OPNAMES.get(x, None) if isinstance(x, int) else None)
def test_fixed_golden_values(func, a, b, want):
    """Concrete TMEM/DRAM words per function, so the suite is meaningful without the oracle."""
    out = run_vop(func, 1, 1, u32_words(a), u32_words(b))
    got = [int(x) for x in dst_words(out, 1, 1)]
    assert got == [int(x) for x in np.asarray(want, np.float32).view(np.uint32)], (
        f"func {func}: got {[hex(x) for x in got]}, "
        f"want {[hex(int(x)) for x in np.asarray(want, np.float32).view(np.uint32)]}")
    # the same words are in the destination TMEM window
    assert [int(x) for x in out["tmem"][DST_T:DST_T + 1]] == got


def test_copy_and_fill_flush_denormals():
    """COPY is ftz(A) and FILL is ftz(B) (docs/isa.md): a denormal flushes to signed zero."""
    a = np.array([0x00000001, 0x80000001, 0x00800000, 0x00000000], np.uint32)
    out = run_vop(I.V_COPY, 1, 4, a)
    assert [int(x) for x in out["tmem"][DST_T:DST_T + 4]] == [0x00000000, 0x80000000,
                                                            0x00800000, 0x00000000]
    b = np.array([0x00000001, 0x80000001, 0x3FC00000, 0x7FC00000], np.uint32)
    out = run_vop(I.V_FILL, 1, 4, np.zeros(4, np.uint32), b)
    assert [int(x) for x in out["tmem"][DST_T:DST_T + 4]] == [0x00000000, 0x80000000,
                                                            0x3FC00000, 0x7FC00000]


# ---------------------------------------------------------------------------- B modes
def test_b_operand_modes():
    """FULL adds elementwise; ROW broadcasts row r; COL broadcasts column c; SCALAR the imm."""
    a = u32_words(np.array([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], np.float32))
    # FULL: B is the same 2x3 tile
    b = u32_words(np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], np.float32))
    out = run_vop(I.V_ADD, 2, 3, a, b, bmode=I.B_FULL)
    assert [float(x) for x in tmem_f32(out, DST_T, 6)] == \
        [11.0, 22.0, 33.0, 44.0, 55.0, 66.0]
    # ROW: B[r] is one word, added to every column of row r
    b_row = u32_words([10.0, 20.0])
    out = run_vop(I.V_ADD, 2, 3, a, b_row, bmode=I.B_ROW, brs=1)
    assert [float(x) for x in tmem_f32(out, DST_T, 6)] == \
        [11.0, 12.0, 13.0, 24.0, 25.0, 26.0]
    # COL: B[c] is one word, added to every row of column c
    b_col = u32_words([100.0, 200.0, 300.0])
    out = run_vop(I.V_ADD, 2, 3, a, b_col, bmode=I.B_COL)
    assert [float(x) for x in tmem_f32(out, DST_T, 6)] == \
        [101.0, 202.0, 303.0, 104.0, 205.0, 306.0]
    # SCALAR: the immediate word, no TMEM read (b is a don't-care address)
    out = run_vop(I.V_MUL, 2, 3, a, bmode=I.B_SCALAR, imm=2.5)
    assert [float(x) for x in tmem_f32(out, DST_T, 6)] == \
        [2.5, 5.0, 7.5, 10.0, 12.5, 15.0]


def test_strides():
    """Unusual A/destination row strides: a padded A tile, a spread-out destination window."""
    rng = np.random.default_rng(0)
    rows, cols, ars, drs, brs = 3, 5, 7, 8, 2
    a = rng.integers(0, 1 << 32, rows * ars, dtype=np.uint32)        # padding words are read too
    b = rng.integers(0, 1 << 32, (rows - 1) * brs + 1, dtype=np.uint32)
    out = run_vop(I.V_ADD, rows, cols, a, b, bmode=I.B_ROW, ars=ars, drs=drs, brs=brs)
    # the destination addresses are dst + r*drs + c: the padding between rows is untouched (0)
    t = out["tmem"]
    for rr in range(rows):
        for cc in range(cols):
            assert t[DST_T + rr * drs + cc] != 0
        if rr + 1 < rows:
            assert t[DST_T + rr * drs + cols] == 0


# ---------------------------------------------------------------------------- randomized
def _rand_words(rng: np.random.Generator, n: int) -> np.ndarray:
    """Random fp32 words: half uniform bit patterns, half well-scaled normals, a few edges."""
    w = rng.integers(0, 1 << 32, n, dtype=np.uint32)
    e = rng.integers(100, 161, n, dtype=np.uint32)      # 2^-27 .. 2^33: composites stay in range
    m = rng.integers(0, 1 << 23, n, dtype=np.uint32)
    s = rng.integers(0, 2, n, dtype=np.uint32)
    good = ((s << 31) | (e << 23) | m).astype(np.uint32)
    w = np.where(rng.random(n) < 0.6, good, w)
    edges = np.array([0x00000000, 0x80000000, 0x00000001, 0x80000001, 0x00800000, 0x7F800000,
                      0xFF800000, 0x3F800000, 0xBF800000], np.uint32)
    w[::17] = edges[: len(w[::17])] if len(w[::17]) <= len(edges) else edges[0]
    return w


def test_random_functions_and_modes():
    """All 14 functions x all 4 B modes x four shapes, random words: bit-exact vs isasim."""
    rng = np.random.default_rng(5)
    for fi, func in enumerate(FUNCS):
        for mi, bmode in enumerate(MODES):
            rows, cols = SHAPES[(fi + mi) % len(SHAPES)]
            ars = cols
            drs = cols
            brs = cols if bmode == I.B_FULL else 1
            n_a = (rows - 1) * ars + cols
            a = _rand_words(rng, n_a)
            nb = b_tile_size(rows, cols, bmode, brs)
            b = _rand_words(rng, nb) if nb else np.zeros(0, np.uint32)
            imm = float(F.from_bits(np.uint32(int(rng.integers(0, 1 << 32)))))
            out = run_vop(func, rows, cols, a, b if nb else None, bmode=bmode, imm=imm,
                          ars=ars, drs=drs, brs=brs)
            assert not out["error"], (func, bmode)


def test_corner_vectors():
    """The documented fp32 corner cases as A and B tiles, all functions x modes, vs isasim."""
    corners = np.array([
        0x00000000, 0x80000000,                         # +0, -0
        0x00000001, 0x80000001, 0x007FFFFF,             # denormals
        0x00800000, 0x80800000,                         # +-MIN_NORMAL
        0x3F800000, 0xBF800000,                         # +-1
        0x3F800001, 0x3F7FFFFF,                         # 1 + ulp, 1 - ulp
        0x40000000, 0x40400000,                         # 2, 3
        0x3E800000, 0x3D000000,                         # 0.25, 0.03125
        0x7F800000, 0xFF800000,                         # +-inf
        0x7FC00000, 0xFFC00000,                         # NaN words
        0x42FE0000, 0xC2FC0000,                         # 127, -126 (exp2's edges)
        0x4B000000, 0x4B7FFFFF,                         # 2^23, 2^24 - 128
        0x7E800000, 0x7F000000,                         # 2^126, 2^128 (recip/exp2 edges)
        0x00800001, 0x4EFFFFFF,                         # small normal, large finite
    ], np.uint32)
    for func in FUNCS:
        for bmode in MODES:
            rows, cols = 2, len(corners)
            a = np.concatenate([corners, corners[::-1]])
            nb = b_tile_size(rows, cols, bmode, cols if bmode == I.B_FULL else 1)
            if nb:
                b = np.concatenate([corners[::-1], corners])
                b = b[:nb] if bmode == I.B_FULL else b[:nb]
            else:
                b = None
            run_vop(func, rows, cols, a, b, bmode=bmode, imm=float(F.from_bits(corners[0])))
            # the harness compared the whole state; the run also has to have halted cleanly
    # the mixed ones that overflow/flush do not error: just the ISA's arithmetic


# ---------------------------------------------------------------------------- errors
def test_hazard_is_error_5():
    """A later element reading an earlier element's write is VOP's read-after-write hazard.

    isasim raises SimError ("VOP read-after-write hazard"); the mini-core must fail with the
    ladder's code 5 (a wrong program would otherwise compute different bits).
    """
    # one row: dst = A + 1, so element 0 writes the address element 1 reads
    prog = [I.ld(A_DRAM, A_T, 4),
            I.vop(I.V_ADD, A_T + 1, A_T, B_T, 1, 4, 1, 1, 1, I.B_SCALAR, 1.0), I.halt()]
    mini.assert_errors(prog, code=5, params_=SMALL)
    # two rows: row 0's first write lands on row 1's first A element (dst = A + cols)
    prog2 = [I.ld(A_DRAM, A_T, 8),
             I.vop(I.V_MUL, A_T + 4, A_T, B_T, 2, 4, 4, 4, 1, I.B_SCALAR, 1.0), I.halt()]
    mini.assert_errors(prog2, code=5, params_=SMALL)
    # and a BO operand hazard: dst overlaps the row-broadcast B words
    prog3 = [I.ld(A_DRAM, A_T, 4), I.ld(B_DRAM, B_T, 2),
             I.vop(I.V_ADD, B_T, A_T, B_T, 2, 4, 4, 4, 1, I.B_ROW), I.halt()]
    mini.assert_errors(prog3, code=5, params_=SMALL)


def test_range_errors_are_code_4():
    """A TMEM read or write outside the array is error 4 (isasim raises the same condition)."""
    # A read out of range
    mini.assert_errors([I.vop(I.V_COPY, DST_T, 4094, 0, 1, 4, 1, 4, 0, I.B_SCALAR, 0.0),
                        I.halt()], code=4, params_=SMALL)
    # destination write out of range (element 1 writes 4096)
    mini.assert_errors([I.vop(I.V_FILL, 4095, 0, 0, 1, 4, 1, 1, 0, I.B_SCALAR, 1.0),
                        I.halt()], code=4, params_=SMALL)
    # B read out of range in FULL mode
    prog = [I.ld(A_DRAM, A_T, 4),
            I.vop(I.V_ADD, DST_T, A_T, 4094, 1, 4, 4, 4, 4, I.B_FULL), I.halt()]
    mini.assert_errors(prog, code=4, params_=SMALL)


def test_unimplemented_vop_is_illegal():
    """The reductions/ARGMAX/OUTER are step 8; isasim runs them, the mini-core rejects (code 1)."""
    rsum = I.vop(I.V_RSUM, DST_T, A_T, B_T, 1, 4, 1, 4, 4)
    out = mini.run([I.ld(A_DRAM, A_T, 4), rsum, I.halt()], params_=SMALL)
    assert out["error"] and out["code"] == 1
    assert not mini.run_isasim([I.ld(A_DRAM, A_T, 4), rsum, I.halt()],
                               params_=SMALL)["error"]
    # a zero shape is not a VOP (isa.vop() refuses it; a raw word must be rejected, not hang)
    out = mini.run([I.Instr(0x30), I.halt()], params_=SMALL)
    assert out["error"] and out["code"] == 1
