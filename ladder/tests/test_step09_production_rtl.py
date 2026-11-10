"""Ladder step 9 — the production core replays the mini-core's programs, bit-exactly.

Step 9 imports the product tree's RTL (`rtl/`, `sim/verilator/`, `sim/tech/`, `targets/`) and
the harness around it (`opentpu/rtlsim.py`, `simtmp.py`, `target.py`, byte-identical to
`ca05e24f` except rtlsim's Verilator `-j 2` ladder edit).  This file is the rung's acceptance:
the *same* hand-assembled program families the mini-core rungs (steps 4-8) proved on the serial
core are replayed on the production core through `opentpu.rtlsim.run`, and every TMEM word, every
DRAM byte and the retired-instruction count must equal the bit-exact golden model
(`opentpu.isasim.Machine`) — the product's own `tests/test_rtl.py` contract, no tolerance.

The families, in the order the ladder built them:

* step 4: LI/ADDI/LOOP/HALT, LD/ST, RLD (addresses and register values are made observable
  through memory);
* step 5: the 14 elementwise VOPs in the FULL/ROW/COL/SCALAR B modes, including the fp32 corner
  words the ISA defines bit for bit;
* step 6: QST (quantized rows + scale records into DRAM) and QACT feeding an MM;
* step 7: int8 MM with UNIT/ACC/RMAX and a scaled case (MX scale rows);
* step 8: RSUM/RMAX/RSSQ/RDOT/ARGMAX.

Programs are written with `opentpu.isa` and use the `prod.CFG` configuration; the Verilator
build is the expensive part (run this file through `python3 ladder/run.py step 9`, which takes
the shared-host lock/thermal gate), while the programs themselves replay in seconds.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ladder.harness import prod  # noqa: E402
from opentpu import fp32 as F  # noqa: E402
from opentpu import isa as I  # noqa: E402

CFG = prod.CFG
D = CFG.D

# DRAM / TMEM windows used by the programs below (inside prod.CFG's 1 MiB / 64K words)
IN_DRAM, W_DRAM, S_DRAM = 0x00000, 0x10000, 0x12000    # fp32 inputs, int8 weights, scale rows
Q_DRAM = 0x20000                                       # QACT/QST inputs and outputs
OUT_DRAM = 0x40000                                     # ST results
A_T, B_T, B2_T, DST_T = 0, 1024, 2048, 4096            # TMEM work windows


# ---------------------------------------------------------------------------- helpers
def f32bits(*values) -> list[int]:
    """fp32 bit patterns as uint32 integers, for the DRAM image and the fixed checks."""
    return [int(x) for x in np.asarray(values, np.float32).view(np.uint32).reshape(-1)]


def bits_of(value) -> list[int]:
    """The fp32 bits of one (scalar or 0-d) value."""
    return [int(x) for x in np.asarray(value, np.float32).view(np.uint32).reshape(-1)]


def put_words(dram: np.ndarray, byte_addr: int, words) -> None:
    """Overlay 32-bit words (uint32 bit patterns) little-endian on the DRAM image."""
    a = np.asarray(words, np.uint32).view(np.uint8)
    dram[byte_addr:byte_addr + a.size] = a


def put_bytes(dram: np.ndarray, byte_addr: int, values) -> None:
    """Overlay raw bytes (e.g. int8 weights) on the DRAM image."""
    a = np.asarray(values, np.uint8).reshape(-1)
    dram[byte_addr:byte_addr + a.size] = a


def run(prog, dram=None, args=None) -> dict:
    """Production RTL vs isasim: bit-identical TMEM + DRAM + icount; returns the RTL state."""
    return prod.assert_matches_isasim(prog, dram=dram, args=args)


def assert_words(got: list[int], want: list[int], what: str = "") -> None:
    g = [int(x) for x in got]
    w = [int(x) for x in want]
    assert g == w, f"{what}: rtl={[hex(x) for x in g[:8]]} want={[hex(x) for x in w[:8]]}"


# ---------------------------------------------------------------------------- step 4 family
def test_control_flow_loops():
    """LI/ADDI/LOOP/HALT: loops write through a register-carried DRAM pointer; nested loops."""
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    prog = [
        I.vop(I.V_FILL, 0, 0, 0, 1, 1, 0, 0, 0, I.B_SCALAR, 1.0),   # T[0] = 1.0
        I.li(1, 0),                                                  # DRAM byte pointer
        I.loop(3, 5),                                                # body 3, five times
        I.st(0, 0, 1, ra=1, rb=0),                                   # M32[R1] = T[0]
        I.addi(1, 1, 4),
        I.nop(),
        I.halt(),
    ]
    out = run(prog, dram)
    assert_words(prod.dram_words(out, 0, 5), [0x3F800000] * 5, "single loop")

    # nested: outer 3, inner 2, one pointer, six writes at 0x100
    prog2 = [
        I.vop(I.V_FILL, 0, 0, 0, 1, 1, 0, 0, 0, I.B_SCALAR, 2.5),
        I.li(1, 0x100),
        I.loop(4, 3),                       # outer body 4 instructions
        I.loop(2, 2),                       # inner body 2
        I.st(0, 0, 1, ra=1, rb=0),
        I.addi(1, 1, 4),
        I.nop(),
        I.halt(),
    ]
    out = run(prog2, dram)
    assert_words(prod.dram_words(out, 0x100, 6), [0x40200000] * 6, "nested loops")


def test_ld_st_copy():
    """LD/ST: DRAM -> TMEM -> DRAM copies with immediate and register addressing."""
    rng = np.random.default_rng(4)
    src = rng.integers(0, 256, 4096, dtype=np.uint8)
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    dram[0:len(src)] = src
    args = [0, 0, 0, 1024, 0, 0, 0, 0]      # R8 DRAM base, R9 TMEM base, R11 TMEM base 1024
    prog = [
        I.ld(0, 16, 8, ra=8, rb=9),         # T[16..23] = M32[0..8)
        I.st(0x4000, 16, 8, ra=8, rb=9),
        I.ld(64, 256, 16, ra=8, rb=9),      # 16 words, both sides register-relative
        I.st(0x8000, 256, 16, ra=8, rb=9),
        I.ld(1024, 0, 16, ra=8, rb=11),     # a second TMEM window
        I.st(0xC000, 0, 16, ra=8, rb=11),
        I.halt(),
    ]
    out = run(prog, dram, args=args)
    assert np.array_equal(out["dram"][0x4000:0x4020], src[0:32])
    assert np.array_equal(out["dram"][0x8000:0x8040], src[64:128])
    assert np.array_equal(out["dram"][0xC000:0xC040], src[1024:1088])


def test_rld_register_values():
    """RLD: f2i truncation, RAW bits and MUL, observed by storing through the converted register.

    T[32..63] is loaded with the identity table 0..31, so "ST T[R1 + 32]" stores exactly R1's
    value; the DRAM words then hold the converted integers.
    """
    words = {0: 0x40200000, 1: 0xC0600000, 2: 0x3F7FFFFF, 3: 0x00000003}   # 2.5, -3.5, <1, RAW 3
    for k in range(32):
        words[128 + k] = k                                              # identity at byte 512
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    for idx, value in words.items():
        put_words(dram, 4 * idx, [value])
    prog = [
        I.ld(0, 0, 4),                       # T[0..3] = the fp32 words
        I.ld(512, 32, 32),                   # T[32..63] = 0..31
        I.rld(1, 0, ra=0),                   # f2i(2.5) = 2
        I.st(0x800, 32, 1, ra=0, rb=1),
        I.rld(2, 1, ra=0),                   # f2i(-3.5) = -3 -> identity[0] = 0
        I.st(0x804, 35, 1, ra=0, rb=2),
        I.rld(3, 2, ra=0),                   # |x| < 1 -> 0
        I.st(0x808, 33, 1, ra=0, rb=3),
        I.rld(4, 3, ra=0, raw=True),         # RAW: the word's bits = 3
        I.st(0x80C, 32, 1, ra=0, rb=4),
        I.rld(5, 0, ra=0, mul=5),            # f2i(2.5) * 5 = 10
        I.st(0x810, 32, 1, ra=0, rb=5),
        I.halt(),
    ]
    out = run(prog, dram)
    assert_words(prod.dram_words(out, 0x800, 5), [2, 0, 1, 3, 10], "RLD")


# ---------------------------------------------------------------------------- step 5 family
def _vop_program(funcs, a_words, b_words, rows, cols, dst_base=DST_T, dst_step=16):
    """LD the A and B tiles, run `funcs` (FULL mode) into separate TMEM windows, ST them."""
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, IN_DRAM, a_words)
    put_words(dram, IN_DRAM + 0x1000, b_words)
    n = rows * cols
    prog = [I.ld(IN_DRAM, A_T, n), I.ld(IN_DRAM + 0x1000, B_T, n)]
    for k, func in enumerate(funcs):
        prog.append(I.vop(func, dst_base + k * dst_step, A_T, B_T, rows, cols, cols, cols, cols,
                          I.B_FULL))
    for k in range(len(funcs)):
        prog.append(I.st(OUT_DRAM + k * 0x100, dst_base + k * dst_step, n))
    prog.append(I.halt())
    return prog, dram


def test_vop_arithmetic_functions():
    """ADD/SUB/RSUB/MUL/MAX/MIN/ABS/COPY/FILL, each on its own output window."""
    a = f32bits([1.5, -2.25, 0.5, -0.0, 3.0, -4.5])
    b = f32bits([2.25, 2.25, -0.25, 0.0, 1.0, 1.5])
    funcs = [I.V_ADD, I.V_SUB, I.V_RSUB, I.V_MUL, I.V_MAX, I.V_MIN, I.V_ABS, I.V_COPY,
             I.V_FILL]
    prog, dram = _vop_program(funcs, a, b, 2, 3)
    out = run(prog, dram)
    assert_words(prod.dram_words(out, OUT_DRAM, 6),
                 f32bits([3.75, 0.0, 0.25, 0.0, 4.0, -3.0]), "ADD")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x100, 6),
                 f32bits([-0.75, -4.5, 0.75, -0.0, 2.0, -6.0]), "SUB")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x200, 6),
                 f32bits([0.75, 4.5, -0.75, 0.0, -2.0, 6.0]), "RSUB")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x300, 6),
                 f32bits([3.375, -5.0625, -0.125, -0.0, 3.0, -6.75]), "MUL")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x400, 6),
                 f32bits([2.25, 2.25, 0.5, 0.0, 3.0, 1.5]), "MAX")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x500, 6),
                 f32bits([1.5, -2.25, -0.25, -0.0, 1.0, -4.5]), "MIN")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x600, 6),
                 f32bits([1.5, 2.25, 0.5, 0.0, 3.0, 4.5]), "ABS")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x700, 6), a, "COPY")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x800, 6), b, "FILL")


def test_vop_composites_and_corners():
    """EXP2/RECIP/RSQRT/LOG2/EXP2SUB, plus the documented fp32 corner words (bit-exact)."""
    vals = [1.0, 2.0, 0.5, 8.0, 0.25, 1.5]
    bvals = [0.0, 0.5, -0.25, 1.0, 2.0, -1.0]
    funcs = [I.V_EXP2, I.V_RECIP, I.V_RSQRT, I.V_LOG2, I.V_EXP2SUB]
    prog, dram = _vop_program(funcs, f32bits(*vals), f32bits(*bvals), 1, 6)
    out = run(prog, dram)
    av = np.asarray(vals, np.float32)
    assert_words(prod.dram_words(out, OUT_DRAM, 6), bits_of(F.exp2(av)), "EXP2")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x100, 6), bits_of(F.recip(av)), "RECIP")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x200, 6), bits_of(F.rsqrt(av)), "RSQRT")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x300, 6), bits_of(F.log2(av)), "LOG2")
    assert int(prod.dram_words(out, OUT_DRAM, 1)[0]) == 0x40000000        # exp2(1) = 2
    assert int(prod.dram_words(out, OUT_DRAM + 0x104, 1)[0]) == 0x3F000000  # recip(2) = 0.5

    # corner words through the elementwise/composite functions: NaN, +-0, denormal, inf (the
    # isasim comparison decides every bit; the ISA defines these sequences exactly)
    corners = np.array([0x00000000, 0x80000000, 0x00000001, 0x7F800000, 0xFF800000,
                        0x7FC00000, 0x00800000, 0x3F800000], np.uint32)
    funcs2 = [I.V_ABS, I.V_COPY, I.V_RECIP, I.V_LOG2, I.V_EXP2, I.V_RSQRT]
    prog2, dram2 = _vop_program(funcs2, corners, np.roll(corners, 3), 1, len(corners))
    run(prog2, dram2)


def test_vop_b_operand_modes():
    """FULL / ROW / COL / SCALAR, with the explicit values the step-5 description derives."""
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    a = np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], np.float32)
    b = np.asarray([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]], np.float32)
    put_words(dram, IN_DRAM, a.view(np.uint32).reshape(-1))
    put_words(dram, IN_DRAM + 0x1000, b.view(np.uint32).reshape(-1))
    put_words(dram, IN_DRAM + 0x2000, np.asarray([10.0, 20.0], np.float32).view(np.uint32))
    put_words(dram, IN_DRAM + 0x2100, np.asarray([100.0, 200.0, 300.0], np.float32)
              .view(np.uint32))
    prog = [
        I.ld(IN_DRAM, A_T, 6),
        I.ld(IN_DRAM + 0x1000, B_T, 6),
        I.ld(IN_DRAM + 0x2000, B_T + 8, 2),            # per-row B words
        I.ld(IN_DRAM + 0x2100, B_T + 16, 3),           # per-column B words
        I.vop(I.V_ADD, DST_T + 0, A_T, B_T, 2, 3, 3, 3, 3, I.B_FULL),
        I.vop(I.V_ADD, DST_T + 16, A_T, B_T + 8, 2, 3, 3, 3, 1, I.B_ROW),
        I.vop(I.V_ADD, DST_T + 32, A_T, B_T + 16, 2, 3, 3, 3, 0, I.B_COL),
        I.vop(I.V_MUL, DST_T + 48, A_T, 0, 2, 3, 3, 3, 0, I.B_SCALAR, 2.5),
        I.st(OUT_DRAM, DST_T + 0, 6),
        I.st(OUT_DRAM + 0x100, DST_T + 16, 6),
        I.st(OUT_DRAM + 0x200, DST_T + 32, 6),
        I.st(OUT_DRAM + 0x300, DST_T + 48, 6),
        I.halt(),
    ]
    out = run(prog, dram)
    assert_words(prod.dram_words(out, OUT_DRAM, 6),
                 f32bits([11.0, 22.0, 33.0, 44.0, 55.0, 66.0]), "FULL")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x100, 6),
                 f32bits([11.0, 12.0, 13.0, 24.0, 25.0, 26.0]), "ROW")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x200, 6),
                 f32bits([101.0, 202.0, 303.0, 104.0, 205.0, 306.0]), "COL")
    assert_words(prod.dram_words(out, OUT_DRAM + 0x300, 6),
                 f32bits([2.5, 5.0, 7.5, 10.0, 12.5, 15.0]), "SCALAR")


# ---------------------------------------------------------------------------- step 6 family
def test_qst_scale_rows_and_bytes():
    """QST: quantized rows + int8 scale records into DRAM, non-ROW and ROW modes."""
    rng = np.random.default_rng(6)
    x = F.ftz((rng.standard_normal((2, 64)) * np.exp2(
        rng.integers(-6, 7, (2, 8))).repeat(8, 1)).astype(np.float32))
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, Q_DRAM, x.view(np.uint32).reshape(-1))
    prog = [I.ld(Q_DRAM, A_T, 128),
            I.qst(A_T, 0x8000, 0x8100, 2, 2, 64, 64, 1),           # non-ROW: scale rows
            I.halt()]
    s = F.quantize(x, axis=1)[1]
    out = run(prog, dram)
    # the recorded row scales are the quantizer's fp32 amax/127 (one record per row: S, then the
    # dw bytes, then pad to 4-byte words); row 1's 8-byte record follows row 0's
    assert_words(prod.dram_words(out, 0x8100, 1), bits_of(s[0]), "QST row 0 scale")
    assert_words(prod.dram_words(out, 0x8108, 1), bits_of(s[1]), "QST non-ROW row 1 scale")
    assert out["dram"][0x8106] == 0 and out["dram"][0x8107] == 0   # the record's pad bytes
    assert np.any(out["dram"][0x8000:0x8080] != 0)                # the data bytes are written

    prog = [I.ld(Q_DRAM, A_T, 128),
            I.qst(A_T, 0x9000, 0x9100, 2, 2, 64, 64, 1, row=True),  # ROW: one S word a row
            I.halt()]
    out = run(prog, dram)
    assert_words(prod.dram_words(out, 0x9100, 1), bits_of(s[0]), "QST ROW scale row 0")
    assert_words(prod.dram_words(out, 0x9104, 1), bits_of(s[1]), "QST ROW scale row 1")


def test_qact_feeds_mm_unit():
    """QACT then a UNIT MM: the quantized ACT bytes are only observable through the MXU."""
    x = np.zeros((2, D), np.float32)
    x[0, 0] = 1.0                                  # row 0: q[0] = 127, amax 1 -> Sa = 1/127
    x[1, 3] = 1.0                                  # row 1: q[3] = 127
    w = np.zeros((2, D), np.int8)
    w[0, 0] = 1                                    # column 0 reads ACT row 0's q[0]
    w[1, 3] = 1                                    # column 1 reads ACT row 1's q[3]
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, Q_DRAM, x.view(np.uint32).reshape(-1))
    put_bytes(dram, W_DRAM, w.view(np.uint8))
    prog = [I.ld(Q_DRAM, A_T, 2 * D),
            I.qact(A_T, 2, 0, 1, D, row=True),
            I.mm(W_DRAM, S_DRAM, DST_T, 2, 1, D, 2, 2, 0, 64, unit=True),
            I.halt()]
    out = run(prog, dram)
    # acc = 127 << 16 for (j == n), 0 elsewhere; Sa = 1/127; Sw = 1
    sa = np.float32(F.quantize(np.array([[1.0] + [0.0] * (D - 1)], np.float32))[1][0])
    one = F.mul(F.mul(F.i2f(np.int64(127 << 16)), np.float32(1.0)),
                F.mul(sa, np.float32(2.0 ** -16)))
    want = int(np.uint32(np.asarray(F.bits(one)).reshape(-1)[0]))
    assert int(out["tmem"][DST_T]) == want
    assert int(out["tmem"][DST_T + 3]) == want              # (j=1, n=1): ors = 2
    assert int(out["tmem"][DST_T + 1]) == 0
    assert int(out["tmem"][DST_T + 2]) == 0


# ---------------------------------------------------------------------------- step 7 family
def test_mm_scaled_with_hand_scale_rows():
    """A scaled int8 MM: hand-written Sw and dw scale rows, ACT from QACT (ROW mode)."""
    rng = np.random.default_rng(7)
    x = np.zeros((D,), np.float32)
    x[:8] = np.array([1, -1, 2, -2, 3, -3, 4, -4], np.float32) * np.float32(1 / 127.0)
    x[-1] = 1.0
    w = rng.integers(-128, 128, (2, 2 * D), dtype=np.int16).astype(np.int8)
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, Q_DRAM, x.view(np.uint32).reshape(-1))
    for n in range(2):
        dram[W_DRAM + n * 64:W_DRAM + n * 64 + 2 * D] = w[n].view(np.uint8)
        put_words(dram, S_DRAM + n * 32, f32bits([0.25, 2.0][n]))
        dram[S_DRAM + n * 32 + 4] = 1                  # dw of block 0
        dram[S_DRAM + n * 32 + 5] = 1                  # dw of block 1
    prog = [I.ld(Q_DRAM, A_T, D),
            I.qact(A_T, 1, 0, 1, D, row=True),
            I.mm(W_DRAM, S_DRAM, DST_T, 2, 1, 64, 2, 1, 0, 32),
            I.halt()]
    run(prog, dram)


def test_mm_acc_and_rmax():
    """UNIT MM, then an ACC MM into the same outputs, with RMAX after both."""
    x = np.zeros((D,), np.float32)
    x[0], x[4], x[9] = 1.0, 0.5, -0.75
    w = np.zeros((2, 2 * D), np.int8)
    w[0, 0], w[0, 5], w[0, 9] = 1, 1, 1
    w[1, 0], w[1, 5], w[1, 9] = -1, 2, 0
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, Q_DRAM, x.view(np.uint32).reshape(-1))
    put_bytes(dram, W_DRAM, w.view(np.uint8))
    prog = [I.ld(Q_DRAM, A_T, D),
            I.qact(A_T, 1, 0, 1, D, row=True),
            I.mm(W_DRAM, S_DRAM, DST_T, 3, 1, D, 4, 1, 0, 64, unit=True, rmax=True),
            I.mm(W_DRAM + D, S_DRAM, DST_T, 3, 1, D, 4, 1, 0, 64, unit=True, acc=True,
                 rmax=True),
            I.halt()]
    out = run(prog, dram)
    ys = np.asarray([int(out["tmem"][DST_T + n]) for n in range(3)], np.uint32).view(np.float32)
    want_max = bits_of(F.chain_max(ys[None, :])[0])[0]
    assert int(out["tmem"][DST_T + 4]) == want_max          # out + M*ors + j, M = 1


# ---------------------------------------------------------------------------- step 8 family
def test_reductions_and_argmax():
    """RSUM/RMAX/RSSQ/RDOT/ARGMAX: the explicit RSUM/ARGMAX values + the whole-state compare."""
    rng = np.random.default_rng(8)
    rows, cols = 3, 100
    tile = F.ftz((rng.standard_normal((rows, cols)) * 0.5).astype(np.float32))
    ones = np.ones((rows, cols), np.float32)
    b = F.ftz(rng.standard_normal((rows, cols)).astype(np.float32))
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, IN_DRAM, tile.view(np.uint32).reshape(-1))
    put_words(dram, IN_DRAM + 0x2000, ones.view(np.uint32).reshape(-1))
    put_words(dram, IN_DRAM + 0x4000, b.view(np.uint32).reshape(-1))
    prog = [
        I.ld(IN_DRAM, A_T, rows * cols),
        I.ld(IN_DRAM + 0x2000, B_T, rows * cols),
        I.ld(IN_DRAM + 0x4000, B2_T, rows * cols),
        I.vop(I.V_RSUM, DST_T + 0, A_T, 0, rows, cols, 1, cols, 0),
        I.vop(I.V_RMAX, DST_T + 8, A_T, 0, rows, cols, 1, cols, 0),
        I.vop(I.V_RSSQ, DST_T + 16, A_T, 0, rows, cols, 1, cols, 0),
        I.vop(I.V_RDOT, DST_T + 24, A_T, B2_T, rows, cols, 1, cols, cols, I.B_FULL),
        I.vop(I.V_RSUM, DST_T + 32, B_T, 0, rows, cols, 1, cols, 0),      # all ones
        I.vop(I.V_ARGMAX, DST_T + 40, A_T, 0, rows, cols, 2, cols, 0, I.B_FULL, -3),
        I.halt(),
    ]
    out = run(prog, dram)
    assert_words(prod.tmem_words(out, DST_T + 32, 3), f32bits([100.0, 100.0, 100.0]),
                 "RSUM of ones")
    for r in range(rows):
        row = tile[r]
        assert int(out["tmem"][DST_T + 8 + r]) == bits_of(
            F.chain_max(row[None, :])[0])[0]                     # RMAX
        idx = int(np.argmax(F._key(row)))
        assert int(out["tmem"][DST_T + 40 + 2 * r]) == bits_of(
            F.chain_max(row[None, :])[0])[0]                     # ARGMAX's maximum
        assert int(out["tmem"][DST_T + 40 + 2 * r + 1]) == bits_of(
            F.i2f(np.int64(idx - 3)))[0]                         # ARGMAX's index + base
        assert int(out["tmem"][DST_T + 16 + r]) < 0x80000000      # RSSQ >= 0


# ---------------------------------------------------------------------------- arguments
def test_run_arguments_and_early_halt():
    """R8..R15 are the run's arguments; HALT stops the slice and icount counts what retired."""
    dram = np.zeros(CFG.DRAM_BYTES, np.uint8)
    put_words(dram, 0x800, [0x11223344])
    prog = [
        I.ld(0, 0, 1, ra=8, rb=9),          # T[R9] = M32[R8]
        I.st(0, 0, 1, ra=10, rb=9),         # M32[R10] = T[R9]
        I.halt(),
        I.li(1, 0x400),                     # never runs
        I.st(0, 0, 1, ra=1, rb=0),
        I.halt(),
    ]
    args = [0x800, 64, 0x1000, 0, 0, 0, 0, 0]
    out = run(prog, dram, args=args)
    assert_words(prod.dram_words(out, 0x1000, 1), [0x11223344], "arguments")
    assert prod.dram_words(out, 0x400, 1) == [0]
    assert out["icount"] == 3
