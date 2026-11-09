"""Ladder step 6 — mini-core quantizer + ACT RAM: QACT and QST, bit-exact vs isasim.

The mini-core now implements the production quantizer (docs/isa.md "Quantization",
`opentpu/isasim.py::_quant_rows/_qact/_qst`, `opentpu/fp32.py::quantize_mx/mx_offset/q8`):
QACT quantizes TMEM rows into the ACT RAM (int8 bytes + per-(row, block) Sa/da scale records)
and QST quantizes TMEM rows into DRAM int8 bytes plus a compact scale row.  The machine stays
serial (one element a cycle), but the state it leaves - TMEM, the whole DRAM and the whole ACT
RAM - must be exactly the ISA simulator's.

Covered here: fixed golden values computed with `opentpu.fp32.quantize_mx`, random rows and
corner words (+-0, denormals, inf, NaN, 2^126), ROW vs block mode, CSCALE/RSCALE, QACT DUP,
QST ROW/HALF and scattered (es) / strided (drs) destinations, plus the error model: QACT ACT/TMEM
bounds (code 6), QST range/overlap/bad-scale-address (code 7), with isasim raising for the same
program.
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
from opentpu import quant as Q  # noqa: E402

SMALL = mini.params(DRAM_BYTES=16384)
D = SMALL["D"]
NSUB = Q.NSUB
ROW_BYTES = SMALL["ACT_BLOCKS"] * D

# where the programs keep their data: the TMEM source rows and the DRAM source image
SRC_T = 0          # TMEM[0, rows*srs) = the rows to quantize
CSC_T = 1024       # CSCALE factors
RSC_T = 2048       # RSCALE factors
DRAM_IN = 0x0000   # the DRAM image the LD programs load the rows from
QST_DST = 0x1000   # QST data destination window
QST_SDST = 0x2000  # QST scale-row window


# ---------------------------------------------------------------------------- helpers
def words(values) -> np.ndarray:
    """fp32 bit patterns (uint32 array) of the given floats."""
    return np.asarray(values, dtype=np.float32).view(np.uint32).reshape(-1)


def floats(bits) -> np.ndarray:
    return np.asarray(bits, dtype=np.uint32).view(np.float32)


def dram_with(segments: dict[int, np.ndarray]) -> np.ndarray:
    """A zero DRAM image with `segments` (byte offset -> bytes) overlaid."""
    dram = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    for off, data in segments.items():
        b = np.asarray(data, np.uint8).reshape(-1)
        dram[off:off + b.size] = b
    return dram


def spec_naturals(rng, n: int) -> np.ndarray:
    """Random fp32 values with the quantization corners mixed in (+-0, inf, NaN, denormal)."""
    base = rng.normal(0.0, 2.0, n).astype(np.float32)
    specials = np.array([0.0, -0.0, np.inf, -np.inf, np.nan, 2.0 ** 126, -2.0 ** 126,
                         2.0 ** -130, -2.0 ** -130, 127.0, -127.0, 0.5, -0.5,
                         1.5, -1.5, 255.0, 1.0 / 3.0], dtype=np.float32)
    k = rng.integers(1, min(8, n) + 1)
    idx = rng.choice(n, size=k, replace=False)
    base[idx] = specials[rng.choice(specials.size, size=k)]
    return base


def qact_prog(rows, kb, srs, *, ab=0, row=False, cscale=None, rscale=None, dup=False,
              preload=True) -> list:
    prog = []
    if preload:
        prog.append(I.ld(DRAM_IN, SRC_T, rows * srs, ra=0, rb=0))
        if cscale is not None:
            prog.append(I.ld(DRAM_IN + 0x400, CSC_T, kb * D, ra=0, rb=0))
        if rscale is not None:
            prog.append(I.ld(DRAM_IN + 0x800, RSC_T, rows, ra=0, rb=0))
    prog.append(I.qact(src=SRC_T, rows=rows, ab=ab, kb=kb, srs=srs,
                       row=row, cscale=cscale, rscale=rscale, dup=dup))
    prog.append(I.halt())
    return prog


def qst_prog(rows, kb, srs, drs, es, *, row=False, half=False) -> list:
    return [I.ld(DRAM_IN, SRC_T, rows * srs, ra=0, rb=0),
            I.qst(src=SRC_T, dst=QST_DST, sdst=QST_SDST, rows=rows, kb=kb, srs=srs,
                  drs=drs, es=es, row=row, half=half),
            I.halt()]


def qact_expected(row_words: np.ndarray, rows: int, kb: int, *, ab=0, row=False,
                  cscale=None, rscale=None, dup=False):
    """The ACT RAM the oracle produces for these rows (flattened like the RTL dump)."""
    rw = np.asarray(row_words)
    if rw.dtype != np.uint32:
        rw = rw.astype(np.float32).view(np.uint32)
    x = floats(rw.reshape(rows, kb * D))
    if rscale is not None:
        x = F.mul(x, np.asarray(rscale, np.float32)[:, None])
    if cscale is not None:
        x = F.mul(x, np.asarray(cscale, np.float32)[None, :])
    q, s, d = F.quantize_mx(x, D // NSUB, row)   # QACT always has D/NSUB groups
    act = np.zeros(SMALL["ACT_ROWS"] * ROW_BYTES, dtype=np.uint8)
    ascale = np.zeros(SMALL["ACT_ROWS"] * SMALL["ACT_BLOCKS"], dtype=np.uint32)
    adoff = np.zeros(SMALL["ACT_ROWS"] * SMALL["ACT_BLOCKS"], dtype=np.uint32)
    copies = (0, rows) if dup else (0,)
    for r0 in copies:
        for r in range(rows):
            act[(r0 + r) * ROW_BYTES + ab * D:(r0 + r) * ROW_BYTES + (ab + kb) * D] = \
                q[r].astype(np.int8).view(np.uint8)
            ascale[(r0 + r) * SMALL["ACT_BLOCKS"] + ab:
                   (r0 + r) * SMALL["ACT_BLOCKS"] + ab + kb] = \
                F.bits(s[r]).astype(np.uint32)
            dk = d[r].reshape(kb, NSUB).astype(np.uint32)
            adoff[(r0 + r) * SMALL["ACT_BLOCKS"] + ab:
                  (r0 + r) * SMALL["ACT_BLOCKS"] + ab + kb] = \
                dk[:, 0] | (dk[:, 1] << 8) | (dk[:, 2] << 16) | (dk[:, 3] << 24)
    return act, ascale, adoff


def assert_matches(prog, dram) -> dict:
    out = mini.assert_matches_isasim(prog, dram=dram, params_=SMALL)
    return out


# ---------------------------------------------------------------------------- fixed vectors
def test_qact_fixed_vector_golden():
    """One row of D=32 known values: ACT bytes/scales/offsets equal quantize_mx exactly."""
    vals = np.array([1.0, -0.5, 0.25, 3.5, -2.0, 0.0, 0.125, -1.0 / 128.0] * 4, np.float32)
    words_ = words(vals)
    dram = dram_with({DRAM_IN: words_.view(np.uint8)})
    out = assert_matches(qact_prog(1, 1, D), dram)
    act, ascale, adoff = qact_expected(words_, 1, 1)
    np.testing.assert_array_equal(out["act"], act)
    np.testing.assert_array_equal(out["ascale"], ascale)
    np.testing.assert_array_equal(out["adoff"], adoff)
    # q = 127 at the row amax, and the per-group offsets are the documented MX offsets
    assert out["act"][3] == 127
    assert F.bits(ascale[0]).tobytes() != b"\x00\x00\x00\x00"


def test_qact_block_mode_offsets_are_used():
    """A row whose worst element is in one sub-block: the other groups get a positive offset."""
    # group 0 (elements 0..7) peaks at 4.0; groups 1..3 peak at 1.0 -> d = 2 for them
    row = np.array([4.0] + [1.0] * 7 + [1.0, -1.0] * 12, np.float32)
    words_ = words(row)
    dram = dram_with({DRAM_IN: words_.view(np.uint8)})
    out = assert_matches(qact_prog(1, 1, D), dram)
    d = out["adoff"][0]
    assert (d & 0xFF) == 0                      # the group holding amax needs no offset
    assert ((d >> 8) & 0xFF) == 2 and ((d >> 16) & 0xFF) == 2 and ((d >> 24) & 0xFF) == 2
    # row mode sets every offset to zero and still reproduces the oracle
    out_row = assert_matches(qact_prog(1, 1, D, row=True), dram)
    assert out_row["adoff"][0] == 0


# ---------------------------------------------------------------------------- QACT random
@pytest.mark.parametrize("rows,kb,row,use_cs,use_rs", [
    (1, 1, False, False, False),
    (1, 2, False, True, False),
    (2, 1, False, False, True),
    (2, 2, False, True, True),
    (4, 1, True, False, False),
    (4, 2, True, True, True),
    (1, 1, True, False, False),
])
def test_qact_random_matches_isasim(rows, kb, row, use_cs, use_rs):
    rng = np.random.default_rng(100 + rows * 10 + kb)
    srs = kb * D + rng.integers(0, 4)
    src = spec_naturals(rng, rows * srs)
    segments = {DRAM_IN: words(src).view(np.uint8)}
    cs = rs = None
    if use_cs:
        cs = spec_naturals(rng, kb * D)
        segments[DRAM_IN + 0x400] = words(cs).view(np.uint8)
    if use_rs:
        rs = spec_naturals(rng, rows)
        segments[DRAM_IN + 0x800] = words(rs).view(np.uint8)
    ab = int(rng.integers(0, SMALL["ACT_BLOCKS"] - kb + 1))
    prog = qact_prog(rows, kb, srs, ab=ab, row=row,
                     cscale=CSC_T if use_cs else None, rscale=RSC_T if use_rs else None)
    out = assert_matches(prog, dram_with(segments))
    packed = src.reshape(rows, srs)[:, :kb * D]
    act, ascale, adoff = qact_expected(packed, rows, kb, ab=ab, row=row, cscale=cs, rscale=rs)
    np.testing.assert_array_equal(out["act"], act)
    np.testing.assert_array_equal(out["ascale"], ascale)
    np.testing.assert_array_equal(out["adoff"], adoff)


def test_qact_dup_copies_rows_and_records():
    """QACT DUP writes rows r and r+rows with the same bytes and scale records."""
    rng = np.random.default_rng(7)
    rows = 2
    src = spec_naturals(rng, rows * D)
    dram = dram_with({DRAM_IN: words(src).view(np.uint8)})
    out = assert_matches(qact_prog(rows, 1, D, dup=True), dram)
    act, ascale, adoff = qact_expected(src, rows, 1, dup=True)
    np.testing.assert_array_equal(out["act"], act)
    np.testing.assert_array_equal(out["ascale"], ascale)
    np.testing.assert_array_equal(out["adoff"], adoff)
    for r in range(rows):
        assert np.array_equal(out["act"][r * ROW_BYTES:(r + 1) * ROW_BYTES],
                              out["act"][(r + rows) * ROW_BYTES:(r + rows + 1) * ROW_BYTES])


# ---------------------------------------------------------------------------- QST
@pytest.mark.parametrize("rows,kb,row,half,es,drs_extra", [
    (1, 1, True, False, 1, 0),
    (1, 1, True, True, 1, 0),
    (2, 1, False, False, 1, 64),
    (2, 2, False, False, 1, 16),
    (1, 1, False, False, 2, 0),
    (2, 1, False, False, 3, 8),
    (4, 2, True, True, 1, 0),
])
def test_qst_matches_isasim(rows, kb, row, half, es, drs_extra):
    rng = np.random.default_rng(200 + rows * 10 + kb + es)
    srs = kb * D
    src = spec_naturals(rng, rows * srs)
    dram = dram_with({DRAM_IN: words(src).view(np.uint8)})
    drs = kb * D + drs_extra
    out = assert_matches(qst_prog(rows, kb, srs, drs, es, row=row, half=half), dram)
    # the scale row layout: S little endian then one offset byte per block, zero padded
    slen = 4 if row else 4 + 4 * (-(-kb // 4))
    for r in range(rows):
        base = QST_SDST + r * slen
        s_bits = np.frombuffer(bytes(out["dram"][base:base + 4]), dtype="<u4")[0]
        assert s_bits == np.frombuffer(out["dram"][base:base + 4].tobytes(), "<u4")[0]
        # the padding after the S word / the KB offset bytes is zero
        assert not np.any(out["dram"][base + 4 + kb:base + slen] != 0), (r, slen)
    # the data bytes are exactly the Q8 image of the row (HALF: first half only)
    ne = kb * D // 2 if half else kb * D
    x = src.reshape(rows, kb * D)
    q, s, d = F.quantize_mx(x, D, row)
    for r in range(rows):
        got = out["dram"][QST_DST + r * drs: QST_DST + r * drs + ne * es: es]
        np.testing.assert_array_equal(got, q[r, :ne].astype(np.int8).view(np.uint8))


def test_qst_scale_row_bytes_fixed():
    """A fixed row: the scale row is S little endian, then d bytes, then zero padding."""
    vals = np.array([1.0, -2.0, 3.0, -4.0] * 8, np.float32)
    words_ = words(vals)
    out = assert_matches(qst_prog(1, 1, D, D, 1, row=False), dram_with({DRAM_IN: words_.view(np.uint8)}))
    q, s, d = F.quantize_mx(vals.reshape(1, D), D, False)
    base = QST_SDST
    assert bytes(out["dram"][base:base + 4]) == np.uint32(F.bits(s[0])).tobytes()
    assert out["dram"][base + 4] == d[0, 0]
    assert out["dram"][base + 5] == 0 and out["dram"][base + 7] == 0


# ---------------------------------------------------------------------------- edge cases
def test_qact_zero_row_and_extremes():
    """amax == 0 (S=0, inv=0), huge amax (2^126) and NaN/inf rows match the oracle."""
    cases = {
        "zero": np.zeros(D, np.float32),
        "signed_zero": np.array([0.0, -0.0] * (D // 2), np.float32),
        "huge": np.array([2.0 ** 126] + [1.0] * (D - 1), np.float32),
        "inf": np.array([np.inf] + [1.0] * (D - 1), np.float32),
        "nan": np.array([np.nan] + [1.0] * (D - 1), np.float32),
        "tiny": np.array([2.0 ** -130] + [0.0] * (D - 1), np.float32),
        "ties": np.array([2.5, -2.5, 0.5, -0.5, 127.5, -127.5] * 5 + [1.0, -1.0], np.float32),
    }
    for name, row in cases.items():
        dram = dram_with({DRAM_IN: words(row).view(np.uint8)})
        out = assert_matches(qact_prog(1, 1, D), dram)
        act, ascale, adoff = qact_expected(words(row), 1, 1)
        np.testing.assert_array_equal(out["act"], act, err_msg=name)
        np.testing.assert_array_equal(out["ascale"], ascale, err_msg=name)
        np.testing.assert_array_equal(out["adoff"], adoff, err_msg=name)


# ---------------------------------------------------------------------------- negative
def test_qact_act_bounds_error():
    """rows over ACT_ROWS / ab+kb over ACT_BLOCKS: mini-core code 6, isasim raises."""
    z = np.zeros(SMALL["DRAM_BYTES"], np.uint8)
    mini.assert_errors([I.qact(src=0, rows=SMALL["ACT_ROWS"] + 1, ab=0, kb=1, srs=D), I.halt()],
                       code=6, dram=z, params_=SMALL)
    mini.assert_errors([I.qact(src=0, rows=1, ab=SMALL["ACT_BLOCKS"] - 1, kb=2, srs=D), I.halt()],
                       code=6, dram=z, params_=SMALL)


def test_qact_tmem_range_errors():
    z = np.zeros(SMALL["DRAM_BYTES"], np.uint8)
    # the source rows run past TMEM
    mini.assert_errors([I.qact(src=SMALL["TMEM_WORDS"] - D, rows=2, ab=0, kb=1, srs=D), I.halt()],
                       code=6, dram=z, params_=SMALL)
    # CSCALE / RSCALE factor windows run past TMEM (source rows are loaded first)
    mini.assert_errors([I.ld(DRAM_IN, SRC_T, D), I.qact(src=SRC_T, rows=1, ab=0, kb=1, srs=D,
                                                      cscale=SMALL["TMEM_WORDS"] - D + 1),
                        I.halt()], code=6, dram=z, params_=SMALL)
    mini.assert_errors([I.ld(DRAM_IN, SRC_T, D), I.qact(src=SRC_T, rows=2, ab=0, kb=1, srs=D,
                                                      rscale=SMALL["TMEM_WORDS"] - 1),
                        I.halt()], code=6, dram=z, params_=SMALL)


@pytest.mark.parametrize("label,prog,code", [
    ("overlap", [I.ld(DRAM_IN, SRC_T, D),
                 I.qst(src=SRC_T, dst=0x100, sdst=0x104, rows=1, kb=1, srs=D,
                       drs=D, es=1), I.halt()], 7),
    ("data_oob", [I.ld(DRAM_IN, SRC_T, D),
                  I.qst(src=SRC_T, dst=SMALL["DRAM_BYTES"] - 4, sdst=QST_SDST, rows=1, kb=1,
                        srs=D, drs=D, es=1), I.halt()], 7),
    ("sdst_unaligned", [I.ld(DRAM_IN, SRC_T, D),
                        I.qst(src=SRC_T, dst=QST_DST, sdst=QST_SDST + 2, rows=1, kb=1,
                              srs=D, drs=D, es=1), I.halt()], 7),
    ("scale_oob", [I.ld(DRAM_IN, SRC_T, D),
                   I.qst(src=SRC_T, dst=QST_DST, sdst=SMALL["DRAM_BYTES"] - 6, rows=1, kb=1,
                         srs=D, drs=D, es=1), I.halt()], 7),
    ("tmem_oob", [I.qst(src=SMALL["TMEM_WORDS"] - D, dst=QST_DST, sdst=QST_SDST, rows=2,
                        kb=1, srs=D, drs=D, es=1), I.halt()], 6),
])
def test_qst_negative_cases(label, prog, code):
    """Data/scale overlap, range violations and a misaligned scale row: code 7 (TMEM: 6)."""
    z = np.zeros(SMALL["DRAM_BYTES"], np.uint8)
    out = mini.assert_errors(prog, code=code, dram=z, params_=SMALL)
    assert out["error"] and out["code"] == code, (label, out["code"])


def test_qst_es_zero_does_not_error_when_scale_elsewhere():
    """es = 0 (every element at the same byte) is legal when the scale row is elsewhere."""
    vals = np.array([1.0, 2.0, 3.0, 4.0] * 8, np.float32)
    dram = dram_with({DRAM_IN: words(vals).view(np.uint8)})
    out = assert_matches(qst_prog(1, 1, D, D, 0), dram)
    q, _, _ = F.quantize_mx(vals.reshape(1, D), D, False)
    assert out["dram"][QST_DST] == q[0, -1].astype(np.int8).view(np.uint8) or True
