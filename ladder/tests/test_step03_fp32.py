"""fp32 golden model (opentpu/fp32.py, docs/isa.md "Arithmetic").

Imported from the production tree at ca05e24f (`tests/test_fp.py`) minus its RTL half:
the production file also drives `sim/verilator/tb_fp.sv` through `opentpu/rtlsim.py`
(`test_rtl_fp_bit_exact`), which belongs to the production tier of a later rung.  The
checks kept here pin the arithmetic semantics the mini-core VPU (step 5) and MXU
epilogue (step 7) must match bit for bit: IEEE-754 binary32 round-to-nearest-even with
flush-to-zero, the defined zero signs, the composite exp2 / recip / rsqrt / log2
sequences and their ulp bounds.
"""
from __future__ import annotations

import numpy as np

from opentpu import fp32 as F

rng = np.random.default_rng(1)


def _zero_sign_cases():
    """(op, a, b) with op 0 add, 1 sub, whose exact result is a zero or flushes to one: x - x,
    -x - -x, x + -x and -x + x at every exponent field with edge mantissas, every pair of signed
    zeros and subnormals (flushed: signed zeros) under add and sub, differences of normals near
    2^-126 that are subnormal (flushed to a zero with the difference's sign), and the infinite
    ones (inf - inf: NaN)."""
    e = np.arange(1, 255, dtype=np.uint32) << 23
    x = F.from_bits(np.concatenate([e, e | 1, e | 0x400000, e | 0x7FFFFF])).copy()
    z = F.from_bits(np.uint32([0, 0x80000000, 1, 0x80000001, 0x7FFFFF, 0x807FFFFF])).copy()
    za, zb = (v.ravel() for v in np.meshgrid(z, z))
    m = F.from_bits(np.uint32(0x00800000) + np.arange(8, dtype=np.uint32)).copy()
    ma, mb = (v.ravel() for v in np.meshgrid(m, m))
    big = F.f32([np.finfo(np.float32).max, np.inf, -np.inf])
    return [(1, x, x), (1, -x, -x), (0, x, -x), (0, -x, x), (0, za, zb), (1, za, zb),
            (1, ma, mb), (1, -ma, -mb), (0, ma, -mb), (0, big, big), (1, big, big),
            (0, big, -big)]


def _ulps(y, ref):
    """|y - ref| in ulps of the binade of ref (float64, normal)."""
    e = np.floor(np.log2(np.abs(ref)))
    return np.abs(y.astype(np.float64) - ref) / np.exp2(np.maximum(e, -126) - 23)


def _binade(e0, sign=0):
    """Every fp32 in [2^e0, 2^(e0+1)), with the sign bit `sign`."""
    return F.from_bits(np.uint32(sign << 31) | np.uint32((e0 + 127) << 23)
                       | np.arange(1 << 23, dtype=np.uint32)).copy()


def test_add_sub_zero_signs_follow_ieee():
    """add / sub against the host's IEEE 754 binary32 adder (roundTiesToEven) with the ISA's flush to
    zero (denormal operands are signed zeros, a denormal result a zero with its sign): bit for bit
    on every zero-sign case, and the rules themselves: x - x = x + (-x) = +0, (-0) + (-0) = -0,
    (-0) - (+0) = -0, (+0) + (-0) = (-0) - (-0) = +0, x + (-0) = x."""
    def ieee(op, a, b):
        a, b = F.ftz(a), F.ftz(b)
        with np.errstate(all="ignore"):
            r = ((a + b) if op == 0 else (a - b)).astype(np.float32)
        den = (np.abs(r) < F.MIN_NORMAL) & (r != 0)
        return F._canon(np.where(den, np.copysign(np.float32(0), r), r).astype(np.float32))
    for op, a, b in _zero_sign_cases():
        got = (F.add if op == 0 else F.sub)(a, b)
        assert np.array_equal(F.bits(got), F.bits(ieee(op, a, b))), (op, a, b)
    x = F.from_bits(np.arange(1, 255, dtype=np.uint32) << 23 | np.uint32(0x2AAAAA)).copy()
    for v in (x, -x):
        assert np.all(F.bits(F.sub(v, v)) == 0) and np.all(F.bits(F.add(v, -v)) == 0)
        assert np.array_equal(F.bits(F.add(v, F.f32(-0.0))), F.bits(v))
    pz, nz = F.f32(0.0), F.f32(-0.0)
    assert F.bits(F.add(nz, nz)) == 0x80000000 and F.bits(F.sub(nz, pz)) == 0x80000000
    assert F.bits(F.add(pz, nz)) == 0 and F.bits(F.sub(nz, nz)) == 0 and F.bits(F.add(nz, pz)) == 0


def test_mul_rounds_on_the_subnormal_grid_before_the_flush():
    # 2^-126 - 2^-150 is a tie on the subnormal grid: it rounds to 2^-126, which is kept
    assert F.bits(F.mul(F.f32(0.5), F.from_bits(np.uint32(0x00FFFFFF)))) == 0x00800000
    assert F.bits(F.mul(F.f32(-0.5), F.from_bits(np.uint32(0x00FFFFFF)))) == 0x80800000
    assert F.bits(F.mul(F.f32(0.5), F.from_bits(np.uint32(0x00FFFFFE)))) == 0


def test_recip_rsqrt_every_exponent():
    """recip and rsqrt within 2e-7 of the exact value for every exponent field, wherever the
    result is a normal number (unscaled, rsqrt failed at fields 1 and >= 252, recip near 2^126)."""
    m = np.concatenate([[0, 1, 0x7FFFFF, 0x400000, 0x7311C3], rng.integers(0, 1 << 23, 3000)])
    x = F.from_bits(np.array([(e << 23) | int(k) for e in range(1, 255) for k in m], np.uint32))
    xd = x.astype(np.float64)
    r = F.recip(x).astype(np.float64)
    ok = xd < 2.0 ** 126
    assert np.max(np.abs(r[ok] * xd[ok] - 1)) < 2e-7
    assert np.all(r[~ok] == 0)
    assert np.all(F.recip(-x)[ok] == -F.recip(x)[ok])
    q = F.rsqrt(x).astype(np.float64)
    assert np.max(np.abs(q * np.sqrt(xd) - 1)) < 2e-7
    assert np.all(F.rsqrt(-x) == 0)


def test_q8_nan_is_zero():
    assert F.q8(F.from_bits(np.uint32([0x7FC00000, 0xFFC00000]))).tolist() == [0, 0]
    # a tiny amax: inv = 127 * recip(amax) is +inf, and the zeros (0 * inf) quantize to 0
    x = np.zeros((1, 32), np.float32)
    x[0, 5] = F.from_bits(np.uint32(0x01000000))
    q, s = F.quantize(x, axis=1)
    assert q[0].tolist() == [0] * 5 + [127] + [0] * 26 and s[0] == 0


def test_mm_partials_have_no_pad_terms():
    """MM's isum_4 adds no +0 pad terms (a -0 partial, from a sum that flushed, stays -0);
    the VOP sums pad with +0 terms (added: -0 becomes +0). otpu_mxu's order, written out."""
    m = F.f32(2.0 ** -126)
    t = F.f32([-1.5 * m] * 4 + [m] * 4 + [-0.0, -0.0])              # KB = 10

    def mxu(t):
        pacc = []
        for k in range(len(t)):
            pacc.append(F.add(F.f32(0) if k < 4 else pacc[k - 4], t[k]))
        C = len(t)
        cy = lambda i: F.add(pacc[i], pacc[i - 2] if i >= 2 else F.f32(0))
        return F.add(cy(C - 2) if C >= 2 else F.f32(0), cy(C - 1))
    assert F.bits(mxu(t)) == 0x80000000
    assert F.bits(F.interleaved_sum(t[None, :], F.MM_PARTIALS, pad=-0.0)[0]) == 0x80000000
    assert F.bits(F.interleaved_sum(t[None, :], F.MM_PARTIALS)[0]) == 0
    r = np.random.default_rng(4)
    for _ in range(2000):
        C = int(r.integers(1, 20))
        v = F.ftz((r.integers(-3, 4, C) * 0.5 * m).astype(np.float32))
        assert F.bits(mxu(v)) == F.bits(F.interleaved_sum(v[None, :], 4, pad=-0.0)[0])


def test_model_accuracy():
    x = F.f32(np.linspace(-30, 30, 10001))
    assert np.max(np.abs(F.exp2(x) / np.exp2(x.astype(np.float64)) - 1)) < 2e-6
    p = F.f32(np.exp(rng.uniform(-40, 40, 10000)))
    assert np.max(np.abs(F.recip(p) * p.astype(np.float64) - 1)) < 1e-6
    assert np.max(np.abs(F.rsqrt(p) * np.sqrt(p.astype(np.float64)) - 1)) < 1e-6
    q, s = F.quantize(F.f32(rng.standard_normal((16, 32))), axis=1)
    assert np.all(np.abs(q) <= 127) and np.all(s > 0)


def test_exp2_error_bound():
    """exp2 (docs/isa.md: minimax coefficients) within 1.3 ulp where f = x - floor(x) is exact
    (every fp32 in [0.5, 1) and (-1, -0.5]) and 1.65 ulp where x + 1 rounds to f (every fp32 in
    (-0.5, -0.25] and (-2^-8, -2^-10]: the worst binades), and on samples of [-126, 128). The
    Taylor coefficients were 13 ulp off near f = 1."""
    r = np.random.default_rng(5)
    for x, bound in ((_binade(-1), 1.3), (_binade(-1, 1), 1.3),
                     (_binade(-2, 1), 1.65), (_binade(-9, 1), 1.65), (_binade(-10, 1), 1.65),
                     (F.f32(r.uniform(-126, 128, 1 << 22)), 1.65)):
        u = _ulps(F.exp2(x), np.exp2(x.astype(np.float64)))
        assert u.max() < bound, (u.max(), x[np.argmax(u)])


def test_exp2_exact_at_integers_and_monotone():
    """exp2(i) = 2^i for every integer in [-126, 127] (C0 = 1); non-decreasing over every fp32 in
    [0.25, 1), around every integer and on [-2^-22, 0] (p(f) <= 2 as f reaches 1, also where x + 1
    rounds to 1), and on a sorted sample of [-126, 128)."""
    i = np.arange(-126, 128)
    assert np.array_equal(F.exp2(i.astype(np.float32)), np.exp2(i).astype(np.float32))
    x = np.concatenate([_binade(-2), _binade(-1)])
    assert np.all(np.diff(F.exp2(x).astype(np.float64)) >= 0)
    k = np.arange(-125, 128).astype(np.float32)[:, None]
    x = np.concatenate([np.nextafter(k, np.float32(-np.inf)), k,
                        np.nextafter(k, np.float32(np.inf))], axis=1).astype(np.float32)
    assert np.all(np.diff(F.exp2(x).astype(np.float64), axis=1) >= 0)
    x = np.concatenate([-_binade(-23)[::-1], -_binade(-24)[::-1], -_binade(-25)[::-1], F.f32([0])])
    y = F.exp2(x)
    assert np.all(np.diff(y.astype(np.float64)) >= 0) and y[-1] == 1.0
    r = np.random.default_rng(6)
    x = np.sort(F.f32(r.uniform(-126, 128, 1 << 21)))
    assert np.all(np.diff(F.exp2(x).astype(np.float64)) >= 0)


def test_recip_error_bound():
    """recip (docs/isa.md: on the significand, two Newton steps and a correction step) within
    1.2 ulp: every fp32 in [1, 2) of both signs, and samples of every exponent field 1..252 (the
    result's field is 127 - field away). Exact at every power of two (the plain Newton step's
    fixed point is 1 ulp low: recip(1) was 0.99999994)."""
    for s in (0, 1):
        x = _binade(0, s)
        u = _ulps(F.recip(x), 1 / x.astype(np.float64))
        assert u.max() < 1.2, (u.max(), x[np.argmax(u)])
    r = np.random.default_rng(7)
    e = np.repeat(np.arange(1, 253, dtype=np.uint32), 4096)
    x = F.from_bits((r.integers(0, 2, len(e)).astype(np.uint32) << np.uint32(31))
                    | (e << np.uint32(23)) | r.integers(0, 1 << 23, len(e)).astype(np.uint32))
    ref = 1 / x.astype(np.float64)
    ok = np.abs(ref) >= 2.0 ** -126
    u = _ulps(F.recip(x)[ok], ref[ok])
    assert u.max() < 1.2, (u.max(), x[ok][np.argmax(u)])
    p = np.exp2(np.arange(-126, 126)).astype(np.float32)
    for s in (1, -1):
        assert np.array_equal(F.recip(s * p), (s / p.astype(np.float64)).astype(np.float32))


def test_rsqrt_error_bound():
    """rsqrt (docs/isa.md: two Newton steps and a correction step) within 1.05 ulp: every fp32 in
    [1, 4), and samples of every exponent field (the scaled ranges, fields 1..2 and 250..254,
    included). Exact at every power of four (rsqrt(1) was 0.99999994)."""
    x = np.concatenate([_binade(0), _binade(1)])
    u = _ulps(F.rsqrt(x), 1 / np.sqrt(x.astype(np.float64)))
    assert u.max() < 1.05, (u.max(), x[np.argmax(u)])
    r = np.random.default_rng(8)
    e = np.repeat(np.arange(1, 255, dtype=np.uint32), 4096)
    x = F.from_bits((e << np.uint32(23)) | r.integers(0, 1 << 23, len(e)).astype(np.uint32))
    u = _ulps(F.rsqrt(x), 1 / np.sqrt(x.astype(np.float64)))
    assert u.max() < 1.05, (u.max(), x[np.argmax(u)])
    p = np.exp2(np.arange(-126, 128, 2)).astype(np.float32)
    assert np.array_equal(F.rsqrt(p), (1 / np.sqrt(p.astype(np.float64))).astype(np.float32))
