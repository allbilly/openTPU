"""Quantization golden model (opentpu/quant.py, docs/isa.md "Weight formats").

Imported from the production tree at ca05e24f (`tests/test_quant.py`), keeping the
pure quantizer checks that need only the golden stack: the study formats (int8/int4/
mxfp4/nvfp4 rounding and bit costs), the MX MXU's packed element rows and scale rows
(int8 / int4 / fp4 / nvfp4), the row-piece and column-part layout invariants, and the
OCP MXFP4 / NVIDIA NVFP4 checkpoint imports.  The dropped tests compare MM on the ISA
simulator and kernels built with `ol`/the compiler; those subsystems arrive in steps
7 and 10, so their MM-level and kernel-level checks move to those rungs.
"""
from __future__ import annotations

import numpy as np
import pytest

from opentpu import Config, isa as I, quant as Q
from opentpu.isasim import Machine


def _spread(rng, N, K, s=3.0, g=32):
    """Rows with log-normal scales per g elements (offsets up to the window and past it)."""
    return (rng.standard_normal((N, K)) * np.exp(s * rng.standard_normal((N, K // g, 1)))
            .repeat(g, 2).reshape(N, K) * 0.02).astype(np.float32)


def _e2m1(codes):
    v = Q.E2M1[codes & 7]
    return np.where(codes & 8, -v, v)


def test_e2m1_and_e4m3_rounding():
    # ties go to the even code (the even mantissa bit), values past the top saturate
    got = Q.round_to_grid(np.array([0.25, 0.75, 1.25, 1.75, 2.5, 3.5, 5.0, 7.0, 100.0]), Q.E2M1)
    assert got.tolist() == [0, 2, 2, 4, 4, 6, 6, 7, 7]
    assert Q.e4m3(np.array([1.0625, 1.1875, 500.0, 2.0 ** -9])).tolist() == \
        [1.0, 1.25, 448.0, 2.0 ** -9]
    assert len(Q.E4M3) == 127 and Q.E4M3[-1] == 448.0


@pytest.mark.parametrize("fmt,g,bits", [("int8", 128, 8.25), ("int4", 32, 4.5), ("mxfp4", 32, 4.25),
                                        ("nvfp4", 16, 4.5), ("int4k", 32, 4.25)])


def test_formats_bits_and_error(fmt, g, bits):
    rng = np.random.default_rng(0)
    W = (rng.standard_normal((64, 256)) * 0.02).astype(np.float32)
    q = Q.quantize(W, fmt)
    assert q.bits == bits and q.g == g
    assert Q.rel_err(W, q.deq) < (1e-4 if fmt == "int8" else 0.02)


def test_mxfp4_elements_are_e2m1_times_power_of_two():
    W = (np.random.default_rng(1).standard_normal((8, 64))).astype(np.float32)
    q = Q.quantize(W, "mxfp4")
    s = q.scales                                                # [8, 2] powers of two
    assert np.all(np.log2(s) == np.round(np.log2(s)))
    x = np.abs(q.deq.reshape(8, 2, 32) / s[..., None])
    assert np.isin(x, Q.E2M1).all()


# ------------------------------------------------------------------------- the MXU's formats


@pytest.mark.parametrize("fmt", Q.MXU_FORMATS)
def test_layout_and_error(fmt):
    """Element rows and scale rows (docs/isa.md "MM"): int8 a byte an element, Sw then a dw
    byte per block (4-byte words); int4 / fp4 a nibble an element, Sw, a reserved word, then a
    word per block (dw, four 6-bit multipliers, the m search's); nvfp4 Sw, three reserved
    words, then eight E4M3 bytes per block (every one's sign clear). The relative error is the
    format's."""
    rng = np.random.default_rng(2)
    W = _spread(rng, 16, 640, 1.0)
    W[3, 128:256] = 0                                           # an all-zero block
    rows, srows = Q.quantize_mxu(W, fmt, 128)
    K, KB = 640, 5
    assert rows.shape == (16, Q.row_bytes(K, fmt, 128)) and rows.dtype == np.uint8
    assert srows.shape == (16, Q.scale_bytes(K, fmt, 128))
    assert Q.scale_bytes(K, fmt, 128) == {"int8": 4 + 4 * 2, "int4": 8 + 8 * 3,
                                          "fp4": 8 + 8 * 3, "nvfp4": 16 + 16 * 3}[fmt]
    Sw, dw, m = Q.unpack_scales(srows, fmt, KB)
    assert np.array_equal(Q.pack_scales(fmt, Sw, dw=dw[..., 0].astype(np.uint8),
                                        m=m.astype(np.uint8),
                                        e4=srows[:, 16:16 + 8 * KB].reshape(16, KB, 8)
                                        if fmt == "nvfp4" else None), srows)
    if fmt in ("int4", "fp4"):
        assert m.min() >= 1 and m.max() <= Q.MMAX
    if fmt == "nvfp4":
        assert not np.any(srows[:, 16:] & 0x80)
    deq = Q.dequantize_mxu(rows, srows, fmt, K, 128)
    assert np.all(deq[3, 128:256] == 0)
    assert Q.rel_err(W, deq) < {"int8": 0.006, "int4": 0.12, "fp4": 0.1, "nvfp4": 0.09}[fmt]
    if fmt != "int8":
        assert np.array_equal(Q.pack4(Q.unpack4(rows[:, :K // 2])), rows[:, :K // 2])


@pytest.mark.parametrize("fmt", Q.MXU_FORMATS)
def test_quantize_mxu_in_row_pieces_is_the_same(fmt, monkeypatch):
    """quantize_mxu quantizes a tall matrix QUANT_ROWS rows at a time (a big vocabulary's LM
    head): the same bytes and scales as all rows at once."""
    rng = np.random.default_rng(0)
    W = (rng.standard_normal((1000, 512)) * np.exp(rng.standard_normal((1000, 1)))).astype(
        np.float32)
    W[3, :128] = 0
    whole = Q.quantize_mxu(W, fmt)
    monkeypatch.setattr(Q, "QUANT_ROWS", 96)
    pieces = Q.quantize_mxu(W, fmt)
    assert all(np.array_equal(a, b) and a.dtype == b.dtype for a, b in zip(whole, pieces))


@pytest.mark.parametrize("fmt", Q.MXU_FORMATS)
def test_column_parts_are_the_whole_rows(fmt):
    """A matrix stored in column parts (W_down's chunks) keeps its rows' quantization: each
    part's scale rows hold the rows' Sw and its blocks' offsets (and multipliers), so the parts
    stand for the whole rows' columns exactly, as a column slice's k0 reads them."""
    rng = np.random.default_rng(3)
    W = _spread(rng, 8, 1024)
    rows, srows = Q.quantize_mxu(W, fmt, 128)
    whole = Q.dequantize_mxu(rows, srows, fmt, 1024, 128)
    for C in (256, 512):
        parts = Q.column_parts(rows, srows, fmt, 1024, C, 128)
        assert len(parts) == 1024 // C
        for j, (pr, ps) in enumerate(parts):
            assert pr.shape[1] == Q.row_bytes(C, fmt, 128)
            assert ps.shape[1] == Q.scale_bytes(C, fmt, 128)
            assert np.array_equal(Q.dequantize_mxu(pr, ps, fmt, C, 128),
                                  whole[:, j * C:(j + 1) * C])
            assert np.array_equal(Q.part_scales(srows, fmt, j * C // 128, C // 128), ps)


# ------------------------------------------------------------------------- MM on the ISA


def test_import_mxfp4_exact():
    """OCP MXFP4 (E2M1 per element, E8M0 per 32) comes in exactly: as fp4 (fp4x6, m = 2^(e -
    the block's smallest e)) where each 128-block's exponents span at most 5 (all-zero
    sub-blocks have any), as nvfp4 (mantissa-0 E4M3 bytes, subnormals at the bottom) where a
    block spans more but no row more than 17 octaves; past that NotExact. The values are the
    checkpoint's, and the ISA simulator's MM with them is the float64 product."""
    rng = np.random.default_rng(7)
    N, K = 6, 512
    codes = rng.integers(0, 16, (N, K)).astype(np.uint8)
    codes[2, 64:96] &= 8                                        # a zero sub-block (signs only)
    base = rng.integers(110, 140, (N, 1))
    e = base + rng.integers(0, 6, (N, K // 32))                 # a block spans <= 5
    e[2, 2] = 0                                                 # (the zero sub-block's)
    want = _e2m1(codes) * np.exp2(np.repeat(e, 32, 1) - 127.0)
    rows, srows, fmt = Q.import_mxfp4(codes, e)
    assert fmt == "fp4"
    assert np.array_equal(Q.dequantize_mxu(rows, srows, "fp4", K), want)
    e2 = e.copy()
    e2[:, 1] = base[:, 0] + 17                                  # spans 6..17 in a block
    want2 = _e2m1(codes) * np.exp2(np.repeat(e2, 32, 1) - 127.0)
    rows2, srows2, fmt2 = Q.import_mxfp4(codes, e2)
    assert fmt2 == "nvfp4"
    assert np.array_equal(Q.dequantize_mxu(rows2, srows2, "nvfp4", K), want2)
    e3 = e.copy()
    e3[0, 5] = base[0, 0] + 23                                  # a row spans 18 or more
    with pytest.raises(Q.NotExact, match="span"):
        Q.import_mxfp4(codes, e3)
    with pytest.raises(Q.NotExact, match="NaN"):
        Q.import_mxfp4(codes, np.full_like(e, 0xFF))
    # the MM: fp4's sums are the exact products of the imported values (int8 activations with
    # a 127 in every group: offsets 0, nothing dropped); nvfp4's drop what its window does
    # (17 octaves of scales against W = 13): the emulation's sums
    x = rng.integers(-127, 128, (2, K)).astype(np.float32)
    x[:, ::32] = 127
    cfg = Config(S=1, D=128, MCOLS=4)
    for r, s, f, w in ((rows, srows, fmt, want), (rows2, srows2, fmt2, want2)):
        img = np.zeros(1 << 20, np.uint8)
        img[:x.nbytes] = x.view(np.uint8).reshape(-1)
        WA, SA = 1 << 16, 1 << 17
        img[WA:WA + r.size] = r.reshape(-1)
        img[SA:SA + s.size] = s.reshape(-1)
        prog = [I.ld(0, 0, x.size), I.qact(0, 2, 0, K // 128, K),
                I.mm(WA, SA, 4096, N, K // 128, r.shape[1], N, 2, 0, s.shape[1],
                     wf=Q.mxu_wf(f)), I.halt()]
        m = Machine(cfg, [prog], [img]).run().slices[0]
        got = m.tget(4096 + np.arange(2 * N)).reshape(2, N)
        if f == "fp4":
            exact = x.astype(np.float64) @ w.T
        else:
            exact = Q.mx_matmul(Q.fake_act(x, 128), w, Q.group_offsets(s, f, K),
                                I.MX_W[Q.mxu_wf(f)])
        assert np.abs(got - exact).max() <= 2e-7 * np.abs(exact).max()


def test_import_nvfp4_exact():
    """NVFP4 (E2M1, an E4M3 scale per 16, an fp32 per tensor) comes in exactly, each row's
    scales re-based so that its largest has dw 0: subnormal scales renormalize, a largest of
    mantissa 7 is the MXU's 0x7F (15 2^0; NVFP4's NaN code is not a scale here), and a
    subnormal 17 octaves below a row's 448 is an MXU subnormal again (E4M3's own range fits:
    every valid checkpoint comes in). NotExact: a negative or NaN scale."""
    rng = np.random.default_rng(8)
    N, K = 5, 256
    codes = rng.integers(0, 16, (N, K)).astype(np.uint8)
    s = rng.integers(1, 127, (N, K // 16)).astype(np.uint8)    # positive, not NaN
    s[0, :] = rng.integers(1, 8, K // 16)                       # a row of subnormals
    s[1, 0] = 0x77                                              # 480/2: mantissa 7
    s[2, 3] = 0                                                 # a zero scale
    ts = np.float32(0.0123)
    want = _e2m1(codes) * np.repeat(Q.E4M3[s], 16, 1) * np.float64(ts)
    rows, srows = Q.import_nvfp4(codes, s, ts)
    got = Q.dequantize_mxu(rows, srows, "nvfp4", K)
    assert np.array_equal(got, want)
    assert not np.any(srows[:, 16:] & 0x80)
    for bad, what in ((0x80 | 0x30, "negative"), (0x7F, "NaN")):
        b = s.copy()
        b[3, 1] = bad
        with pytest.raises(Q.NotExact, match=what):
            Q.import_nvfp4(codes, b, ts)
    far = s.copy()
    far[4, :] = 0x60                                            # 32
    far[4, 0] = 0x7E                                            # 448 = 1.75 2^8 at the top
    far[4, 1] = 0x01                                            # 2^-9: 17 octaves down
    far[4, 2] = 0x03                                            # 3 2^-9
    rows, srows = Q.import_nvfp4(codes, far, ts)
    assert np.array_equal(Q.dequantize_mxu(rows, srows, "nvfp4", K),
                          _e2m1(codes) * np.repeat(Q.E4M3[far], 16, 1) * np.float64(ts))
    assert srows[4, 17] == 0x01 and srows[4, 18] == 0x03       # MXU subnormals
