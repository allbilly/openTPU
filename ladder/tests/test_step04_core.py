"""Ladder step 4 — the mini-core: bit-exact openTPU-ISA sequencer + TMEM + DRAM + LD/ST.

The mini-core (`rtl/ladder/mini_*.sv`, `sim/ladder/tb_mini.sv`) runs the step-4 subset of the
openTPU ISA serially: NOP/HALT/LI/ADDI/LOOP/BAR/RLD/LD/ST.  Latency is deliberately not
production's, but the *state* it leaves behind must be exactly the ISA simulator's
(`opentpu/isasim.py`, imported in step 3): TMEM and the whole DRAM word for word, plus the
retired-instruction count.

Covered here: instruction semantics (LI/ADDI/RLD with f2i/RAW/MUL, loops, LD/ST, argument
registers, r0, the error model), HALT placement, and random programs fuzzed against isasim.
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
from opentpu import isa as I  # noqa: E402

# fast configuration: same core parameters, 16 KiB DRAM so the whole-DRAM dump stays cheap.
SMALL = mini.params(DRAM_BYTES=16384)
# the spec's configuration: 256 KiB DRAM, compared in full by the LD/ST test.
SPEC = mini.DEFAULT_PARAMS


# ---------------------------------------------------------------------------- helpers
def f32(*values) -> list[int]:
    """fp32 bit patterns (the words RLD converts), from Python floats."""
    a = np.asarray(values, dtype=np.float32).view(np.uint32) if len(values) > 1 else \
        np.asarray([values[0]], dtype=np.float32).view(np.uint32)
    return [int(x) for x in a.reshape(-1)]


def u32(x: int) -> int:
    return int(x) & 0xFFFFFFFF


def _put_u32(dram: np.ndarray, byte_off: int, value: int) -> None:
    """Overlay one little-endian 32-bit word on a uint8 DRAM image (numpy-2 safe)."""
    dram[byte_off:byte_off + 4] = np.frombuffer(u32(value).to_bytes(4, "little"), dtype=np.uint8)


def _dram_with_words(n: int, words: dict[int, int], prefix: np.ndarray | None = None) -> np.ndarray:
    """A DRAM image: `prefix` bytes (or zeros), with `words[word_index] = value` overlaid."""
    dram = np.zeros(n, dtype=np.uint8)
    if prefix is not None:
        p = np.asarray(prefix, dtype=np.uint8).reshape(-1)
        dram[: len(p)] = p
    for idx, value in words.items():
        _put_u32(dram, 4 * idx, value)
    return dram


def _slots(out: dict, start: int, count: int) -> list[int]:
    return [int(x) for x in np.frombuffer(out["dram"][start:start + 4 * count].tobytes(), "<u4")]


# ---------------------------------------------------------------------------- instructions
def test_li_addi_rld_semantics():
    """LI/ADDI/RLD: f2i truncation, negatives, |x|<1, |x|>=2^31, RAW bits, MUL; concrete results.

    Registers are observed the only way the ISA lets them be: as a TMEM address.  T[32..63] is
    loaded with the identity table 0..31, so "ST T[R1 + 32]" stores exactly R1's value.
    """
    fp = [2.5, -3.5, 0.999, -0.0, 1e30, float("inf"), 1.5, 16777216.0]
    words = {k: b for k, b in enumerate(f32(*fp))}
    words[8] = 3                     # bits 0x00000003: f2i -> 0 (denormal), RAW -> 3
    for k in range(32):
        words[128 + k] = k           # identity table at DRAM byte 512
    dram = _dram_with_words(SMALL["DRAM_BYTES"], words)

    prog = [
        I.ld(0, 0, 8, ra=0, rb=0),        # T[0..7]  = the fp32 patterns
        I.ld(512, 32, 32, ra=0, rb=0),    # T[32..63] = 0..31 identity
        I.ld(32, 8, 1, ra=0, rb=0),       # T[8] = bits 3
        # f2i(2.5) = 2 (truncation toward zero, not rounding)
        I.rld(1, 0, ra=0),
        I.st(1024, 32, 1, ra=0, rb=1),    # out[0] = T[32 + 2] = 2
        # f2i(-3.5) = -3: -3 + 35 = 32 -> identity[0] = 0 (a +3 would have stored 6)
        I.rld(2, 1, ra=0),
        I.st(1028, 35, 1, ra=0, rb=2),    # out[1] = 0
        # 0 < |x| < 1 gives 0: 0 + 33 -> identity[1] = 1
        I.rld(3, 2, ra=0),
        I.st(1032, 33, 1, ra=0, rb=3),    # out[2] = 1
        # RAW: the word's bits, no conversion: 3
        I.rld(5, 8, ra=0, raw=True),
        I.st(1036, 32, 1, ra=0, rb=5),    # out[3] = 3
        # MUL: f2i(2.5) * 5 = 10
        I.rld(6, 0, ra=0, mul=5),
        I.st(1040, 32, 1, ra=0, rb=6),    # out[4] = 10
        # MUL of a value that is 0 after the conversion: f2i(bits 3) * 5 = 0
        I.rld(7, 8, ra=0, mul=5),
        I.st(1044, 32, 1, ra=0, rb=7),    # out[5] = 0
        # BOUND satisfied: the simulator checks it, the hardware ignores it, same result
        I.rld(7, 0, ra=0, mul=5, bound=(0, 100)),
        I.st(1048, 32, 1, ra=0, rb=7),    # out[6] = 10
        # LI/ADDI: 4 + 4 = 8 -> identity[8] = 8
        I.li(9, 4),
        I.addi(9, 9, 4),
        I.st(1052, 32, 1, ra=0, rb=9),    # out[7] = 8
        # ADDI by -4 (two's complement): -4 + 36 = 32 -> identity[0] = 0 (a +4 gives 40 -> 8)
        I.li(10, 0),
        I.addi(10, 10, -4),
        I.st(1056, 36, 1, ra=0, rb=10),   # out[8] = 0
        # ADDI by 16: 0 + 16 = 16 -> identity[16] = 16
        I.li(11, 0),
        I.addi(11, 11, 16),
        I.st(1060, 32, 1, ra=0, rb=11),   # out[9] = 16
        # rd = 0 writes nothing: R0 stays 0, so T[0 + 32] = 0
        I.rld(0, 0, ra=0),
        I.addi(0, 0, 4),
        I.st(1064, 32, 1, ra=0, rb=0),    # out[10] = 0
        I.halt(),
    ]
    out = mini.assert_matches_isasim(prog, dram=dram, params_=SMALL)
    assert _slots(out, 1024, 11) == [2, 0, 1, 3, 10, 0, 10, 8, 0, 16, 0]
    # no loops: every instruction retires exactly once
    assert out["icount"] == len(prog)
    assert out["halted"] and not out["error"]
    # the fp32 words themselves went through DRAM -> TMEM unchanged
    assert [u32(x) for x in out["tmem"][0:8]] == f32(*fp)

    # the hardware ignores RLD's BOUND flag (it is the waits pass's / isasim's check): a value
    # outside the declared bound must not stop the mini-core, while isasim raises SimError.
    unbound = [I.ld(0, 0, 1), I.rld(1, 0, ra=0, bound=(0, 1)), I.st(1024, 32, 1, ra=0, rb=1),
               I.halt()]
    out = mini.run(unbound, dram=dram, params_=SMALL)
    assert out["halted"] and not out["error"], out
    assert mini.run_isasim(unbound, dram=dram, params_=SMALL)["error"], \
        "isasim checks RLD BOUND; the hardware does not"


def test_ld_st_copy():
    """LD/ST copy DRAM -> TMEM -> DRAM with register and register+immediate addressing.

    Runs at the spec's 256 KiB DRAM and compares the whole DRAM and TMEM with isasim.
    """
    rng = np.random.default_rng(4)
    src = rng.integers(0, 256, size=4096, dtype=np.uint8)
    # make the pattern deterministic and nonzero, and distinct from the untouched DRAM
    src = np.asarray([((7 * k + 3) & 0xFF) for k in range(4096)], dtype=np.uint8)
    dram = np.zeros(SPEC["DRAM_BYTES"], dtype=np.uint8)
    dram[0:len(src)] = src
    # R8 = 0 (DRAM source base), R9 = 0 (TMEM offset base), R10 = 0 (DRAM destination base),
    # R11 = 1024 (second TMEM offset base).  Every address below is R[arg] + immediate.
    args = [0, 0, 0, 1024, 0, 0, 0, 0]
    prog = [
        # 8-word copy, register addressing only
        I.ld(0, 16, 8, ra=8, rb=9),
        I.st(4096, 16, 8, ra=10, rb=9),
        # 16-word copy, register + immediate addressing on both sides
        I.ld(64, 256, 16, ra=8, rb=9),
        I.st(8192, 256, 16, ra=10, rb=9),
        # copy into a second TMEM window and back to a third DRAM region
        I.ld(1024, 0, 16, ra=8, rb=11),
        I.st(12288, 0, 16, ra=10, rb=11),
        # n = 8 is the ISA maximum; n = 0 is a legal no-op
        I.ld(2048, 512, 8, ra=8, rb=9),
        I.st(16384, 512, 8, ra=10, rb=9),
        I.ld(0, 0, 0, ra=8, rb=9),
        I.st(0, 0, 0, ra=10, rb=9),
        I.halt(),
    ]
    out = mini.assert_matches_isasim(prog, dram=dram, args=args, params_=SPEC)
    assert out["halted"] and not out["error"]
    assert out["icount"] == len(prog)
    # concrete: the copies are exact, and the n = 0 instructions moved nothing
    outd = out["dram"]
    assert np.array_equal(outd[4096:4096 + 32], src[0:32])
    assert np.array_equal(outd[8192:8192 + 64], src[64:128])
    assert np.array_equal(outd[12288:12288 + 64], src[1024:1088])
    assert np.array_equal(outd[16384:16384 + 32], src[2048:2080])
    assert np.array_equal(outd[0:256], src[0:256])  # n = 0 ST did not overwrite the source
    assert np.all(out["tmem"][16:24] == np.frombuffer(src[0:32].tobytes(), "<u4"))
    assert np.all(out["tmem"][256:272] == np.frombuffer(src[64:128].tobytes(), "<u4"))


def test_loops():
    """Single/nested loops with loop-carried pointers, zero-count skip, HALT in a body, body 1."""
    # -- single loop: copy 5 words, the source and destination pointers carried in registers
    src = np.arange(40, dtype=np.uint8) * 3
    dram = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    dram[0:len(src)] = src
    prog = [
        I.li(1, 5),                 # loop count in R1
        I.li(2, 0),                 # source byte pointer
        I.li(3, 2048),              # destination byte pointer
        I.loop(4, 0, rcount=1),     # body 4, five iterations
        I.ld(0, 0, 1, ra=2, rb=0),
        I.st(0, 0, 1, ra=3, rb=0),
        I.addi(2, 2, 4),
        I.addi(3, 3, 4),
        I.halt(),
    ]
    out = mini.assert_matches_isasim(prog, dram=dram, params_=SMALL)
    assert np.array_equal(out["dram"][2048:2068], src[0:20])
    assert out["icount"] == 4 + 5 * 4 + 1

    # -- nested two deep: outer 2 x inner 3 copies; pointers carried inside the bodies
    dram2 = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    dram2[0:40] = src
    prog2 = [
        I.li(1, 2),                 # outer count
        I.li(4, 3),                 # inner count
        I.li(2, 0),                 # source pointer
        I.li(3, 3072),              # destination pointer
        I.loop(5, 0, rcount=1),     # outer body 5
        I.loop(2, 0, rcount=4),     # inner body 2 (ends at the ST, not at the outer end)
        I.ld(0, 0, 1, ra=2, rb=0),
        I.st(0, 0, 1, ra=3, rb=0),
        I.addi(2, 2, 4),
        I.addi(3, 3, 4),
        I.halt(),
    ]
    out2 = mini.assert_matches_isasim(prog2, dram=dram2, params_=SMALL)
    # outer iteration 1 copies source word 0 to 3072 three times (the pointer only moves in
    # the outer body); iteration 2 copies source word 1 to 3076
    assert np.array_equal(out2["dram"][3072:3076], src[0:4])
    assert np.array_equal(out2["dram"][3076:3080], src[4:8])

    # -- nested three deep, 2 x 2 x 2 copies
    prog3 = [
        I.li(1, 2), I.li(2, 2), I.li(3, 2),
        I.li(4, 0),                 # source pointer
        I.li(5, 4096),              # destination pointer
        I.loop(7, 0, rcount=1),     # L1 body 7
        I.loop(5, 0, rcount=2),     # L2 body 5
        I.loop(3, 0, rcount=3),     # L3 body 3
        I.ld(0, 0, 1, ra=4, rb=0),
        I.st(0, 0, 1, ra=5, rb=0),
        I.addi(4, 4, 4),
        I.addi(5, 5, 4),
        I.nop(),
        I.halt(),
    ]
    out3 = mini.assert_matches_isasim(prog3, dram=dram2, params_=SMALL)
    assert out3["icount"] > 8 * 3

    # -- zero-count: a count of R[0]+0 skips; R[ra]+w2 wraps mod 2^32 (-2 + 2 = 0) skips too
    dram3 = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    _put_u32(dram3, 0, 0x11223344)
    prog4 = [
        I.ld(0, 0, 1, ra=0, rb=0),      # T[0] = M32[0], nonzero
        I.loop(2, 0),                   # count 0: skip the body
        I.li(2, 4),
        I.st(0, 0, 1, ra=2, rb=0),      # would write M32[4] = T[0]
        I.li(3, -2),                    # R3 = 0xFFFFFFFE
        I.loop(2, 2, rcount=3),         # R3 + 2 = 0 mod 2^32: skip
        I.li(2, 8),
        I.st(0, 0, 1, ra=2, rb=0),      # would write M32[8]
        I.li(2, 12),
        I.st(0, 0, 1, ra=2, rb=0),      # runs: M32[12] = T[0]
        I.halt(),
    ]
    out4 = mini.assert_matches_isasim(prog4, dram=dram3, params_=SMALL)
    assert out4["dram"][4:8].tobytes() == b"\x00\x00\x00\x00"
    assert out4["dram"][8:12].tobytes() == b"\x00\x00\x00\x00"
    assert out4["dram"][12:16].tobytes() == b"\x44\x33\x22\x11"

    # -- a body of length one, and a loop whose body HALTed (the machine stops mid-loop)
    prog5 = [I.li(1, 3), I.li(2, 0), I.loop(1, 0, rcount=1), I.addi(2, 2, 4),
             I.st(0, 0, 1, ra=2, rb=0), I.halt()]
    out5 = mini.assert_matches_isasim(prog5, dram=dram3, params_=SMALL)
    assert out5["icount"] == 2 + 1 + 3 + 1 + 1   # LI, LI, LOOP, 3x ADDI, ST, HALT

    prog6 = [I.li(1, 5), I.li(2, 0), I.loop(2, 0, rcount=1), I.addi(2, 2, 4), I.halt(),
             I.li(3, 1), I.halt()]
    out6 = mini.assert_matches_isasim(prog6, params_=SMALL)
    assert out6["halted"] and not out6["error"]
    assert out6["icount"] == 5, "LI, LI, LOOP, ADDI, HALT of the first iteration"

    # -- LOOP errors (isasim raises SimError for each; the mini-core must error too)
    mini.assert_errors([I.loop(0, 3), I.halt()], code=3, params_=SMALL)          # empty body
    mini.assert_errors([I.loop(4, 1), I.nop(), I.nop(), I.loop(1, 0), I.nop(),    # bodies end
                        I.halt()], code=3, params_=SMALL)                        # on one pc
    # five nested loops: the fourth pushes, the fifth overflows the depth-4 stack
    deep = [
        I.loop(10, 1), I.loop(8, 1), I.loop(6, 1), I.loop(4, 1), I.loop(2, 1),
        I.nop(), I.nop(), I.nop(), I.nop(), I.nop(), I.nop(), I.halt(),
    ]
    mini.assert_errors(deep, code=3, params_=SMALL)


def test_address_arithmetic():
    """R8..R15 arguments as bases, ADDI by 4/16/-4, unaligned DRAM and TMEM range errors."""
    rng = np.random.default_rng(11)
    data = rng.integers(0, 256, size=4096, dtype=np.uint8)
    dram = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    dram[0:len(data)] = data
    # R8..R15: DRAM bases 0, 64, 128, 192 then TMEM bases 1024, 2048, 0, 0
    args = [0, 64, 128, 192, 1024, 2048, 0, 0]
    prog = [
        # argument registers as both bases: T[R12 + 0] <- M32[R8 + 0]
        I.ld(0, 0, 4, ra=8, rb=12),
        # ... and a DRAM base taken from another argument with an immediate offset
        I.ld(0, 0, 4, ra=9, rb=13),
        # ADDI computes a TMEM base: 2048 - 4 = 2044
        I.li(14, 2048),
        I.addi(14, 14, -4),
        I.ld(64, 0, 4, ra=9, rb=14),
        # ADDI by 16: 1016 + 16 = 1032
        I.li(15, 1016),
        I.addi(15, 15, 16),
        I.ld(16, 0, 4, ra=8, rb=15),
        # copy all four windows back out with argued/immediate addresses
        I.st(4096, 0, 4, ra=8, rb=12),
        I.st(8192, 2044, 4, ra=8, rb=0),
        I.st(12288, 1032, 4, ra=8, rb=0),
        # r0: writes are dropped and it always reads as 0 (copy M32[0] to M32[0])
        I.li(0, 99),
        I.addi(0, 0, 4),
        I.rld(0, 0, ra=0),
        I.ld(0, 0, 1, ra=0, rb=6),
        I.st(0, 0, 1, ra=0, rb=6),
        # our DRAM base argument R11 is still 192 from the run's arguments
        I.ld(0, 0, 1, ra=11, rb=6),
        I.st(14336, 0, 1, ra=8, rb=6),
        I.halt(),
    ]
    out = mini.assert_matches_isasim(prog, dram=dram, args=args, params_=SMALL)
    outd = out["dram"]
    assert np.array_equal(outd[4096:4112], data[0:16])
    assert np.array_equal(outd[4096:4112], outd[0:16])
    assert np.array_equal(outd[8192:8208], data[128:144])
    assert np.array_equal(outd[12288:12304], data[16:32])
    assert np.array_equal(outd[14336:14340], data[192:196])
    assert np.all(out["tmem"][1024:1028] == np.frombuffer(data[0:16].tobytes(), "<u4"))

    # TMEM range: indices 4095 and 4096 run past TMEM_WORDS = 4096
    mini.assert_errors([I.st(0, 4095, 2), I.halt()], code=4, params_=SMALL)
    mini.assert_errors([I.ld(0, 4096, 1), I.halt()], code=4, params_=SMALL)
    # ... including when the base comes from an argument register
    mini.assert_errors([I.ld(0, 0, 1, ra=0, rb=12), I.halt()], code=4, params_=SMALL,
                       args=[0, 0, 0, 0, 4096])
    # unaligned DRAM word address: error code 2, from an immediate and from an argument
    mini.assert_errors([I.st(2, 0, 1), I.halt()], code=2, params_=SMALL)
    mini.assert_errors([I.st(0, 0, 1, ra=8), I.halt()], code=2, params_=SMALL,
                       args=[2, 0, 0, 0])
    # out of range DRAM (the last word of the image is 16380..16383, two words do not fit)
    mini.assert_errors([I.st(16380, 0, 2), I.halt()], code=2, params_=SMALL)
    # the DRAM check comes before the TMEM check, like isasim's
    mini.assert_errors([I.st(2, 4096, 1), I.halt()], code=2, params_=SMALL)


# ---------------------------------------------------------------------------- fuzz
def _gen_fuzz_program(rng: random.Random) -> tuple[list, np.ndarray, list[int]]:
    """A random program over the supported subset with statically valid addresses.

    R1/R3 are DRAM pointers and R2/R4 TMEM bases; they are only set by LI, so every LD/ST
    address is in range by construction.  R5..R7 are scratch (ADDI/RLD).  LOOP counts come from
    R0 + immediate, so nesting terminates; an inner body never ends on its enclosing body's last
    instruction (the ISA's nesting rule), because a NOP follows every nested loop.
    """
    n = SMALL["DRAM_BYTES"]
    dram = np.zeros(n, dtype=np.uint8)
    dram[0:1024] = np.frombuffer(rng.randbytes(1024), dtype=np.uint8)
    for k in range(64):                        # identity table, so RLD values stay small
        _put_u32(dram, 8192 + 4 * k, k)
    args = [rng.randrange(0, 1024, 4) for _ in range(8)]

    def simple_op():
        r = rng.random()
        if r < 0.08:
            return I.nop()
        if r < 0.16:
            return I.bar()
        if r < 0.42:                            # LD/ST between the tracked windows
            dreg, treg = rng.choice([(1, 2), (3, 4), (1, 4), (3, 2)])
            nwords = rng.randint(1, 8)
            doff = rng.randrange(0, 33, 4)
            toff = rng.randrange(0, 65, 4)
            if rng.random() < 0.5:
                return I.ld(doff, toff, nwords, ra=dreg, rb=treg)
            return I.st(doff, toff, nwords, ra=dreg, rb=treg)
        if r < 0.55:                            # RLD from the identity table into scratch
            rd = rng.choice([5, 6, 7])
            return I.rld(rd, rng.randrange(0, 64), ra=0, raw=rng.random() < 0.5,
                         mul=rng.choice([None, None, 1, 3, 5]))
        if r < 0.62:                            # scratch-register arithmetic
            reg = rng.choice([5, 6, 7])
            return I.addi(reg, reg, rng.choice([-16, -4, 4, 16]))
        return I.nop()

    def block(depth: int):
        items = [simple_op() for _ in range(rng.randint(1, 4))]
        if depth < 3 and rng.random() < 0.5:
            body = block(depth + 1)
            items.insert(rng.randrange(len(items) + 1), ("loop", rng.choice([0, 1, 2, 3]), body))
        return items

    def flatten(items) -> list:
        out = []
        for item in items:
            if isinstance(item, tuple):
                _, count, body = item
                body_instrs = flatten(body)
                out.append(I.loop(len(body_instrs), count))
                out.extend(body_instrs)
                out.append(I.nop())             # keep the two body-end pcs distinct
            else:
                out.append(item)
        return out

    prog = [
        I.ld(8192, 0, 64, ra=0, rb=0),          # T[0..63] = 0..63
        I.li(1, rng.randrange(0, 900, 4)),
        I.li(2, rng.randrange(0, 2500, 4)),
        I.li(3, rng.randrange(0, 900, 4)),
        I.li(4, rng.randrange(0, 2500, 4)),
        I.li(5, rng.randrange(0, 64)),
        I.li(6, rng.randrange(0, 64)),
        I.li(7, rng.randrange(0, 64)),
    ]
    prog += flatten(block(0))
    prog.append(I.halt())
    return prog, dram, args


def test_fuzz_against_isasim():
    """>= 20 random programs from the supported op set, bit-exact on TMEM and the whole DRAM."""
    rng = random.Random(0x51DE4)
    accepted = 0
    attempts = 0
    while accepted < 24 and attempts < 200:
        attempts += 1
        prog, dram, args = _gen_fuzz_program(rng)
        if len(prog) > 240:
            continue
        golden = mini.run_isasim(prog, dram=dram, args=args, params_=SMALL, max_steps=30000)
        if golden["error"]:
            continue                         # a rejected random shape; draw another
        out = mini.run(prog, dram=dram, args=args, params_=SMALL)
        problems = mini.compare(out, golden)
        assert not problems, (f"random program #{accepted} (seed 0x51DE4, attempt {attempts}) "
                              f"differs:\n" + "\n".join(problems))
        accepted += 1
    assert accepted >= 20, f"only {accepted} random programs ran"


# ---------------------------------------------------------------------------- HALT / errors
def test_halt_before_end():
    """HALT stops the slice: later instructions never run, icount counts the executed ones."""
    dram = np.zeros(SMALL["DRAM_BYTES"], dtype=np.uint8)
    _put_u32(dram, 0, 0x55667788)
    prog = [
        I.ld(0, 0, 1, ra=0, rb=0),      # T[0] = M32[0]
        I.st(64, 0, 1, ra=0, rb=0),     # M32[64] = T[0]
        I.halt(),                       # stop here
        I.li(1, 128),
        I.st(0, 0, 1, ra=1, rb=0),      # would write M32[128]
        I.li(2, 256),
        I.halt(),
    ]
    out = mini.assert_matches_isasim(prog, dram=dram, params_=SMALL)
    assert out["halted"] and not out["error"]
    assert out["icount"] == 3
    assert out["dram"][64:68].tobytes() == b"\x88\x77\x66\x55"
    assert out["dram"][128:132].tobytes() == b"\x00\x00\x00\x00"
    assert out["dram"][256:260].tobytes() == b"\x00\x00\x00\x00"


def test_error_reporting():
    """Unimplemented-in-mini opcodes error with code 1; HALT CHAIN too."""
    # VOP (0x30): part of the ISA (step 8 implements it), but not of the mini-core yet.  isasim
    # executes it, so this is an RTL-only assertion: the mini-core must reject it.
    out = mini.run([I.Instr(0x30), I.halt()], params_=SMALL)
    assert out["error"] and out["code"] == 1
    assert not mini.run_isasim([I.Instr(0x30), I.halt()], params_=SMALL)["error"]
    # WAITW (0x07) is also implemented by isasim and not by the mini-core: error 1
    out = mini.run([I.Instr(0x07), I.halt()], params_=SMALL)
    assert out["error"] and out["code"] == 1
    # a truly undefined opcode is an error for both
    mini.assert_errors([I.Instr(0x77), I.halt()], code=1, params_=SMALL)
    # MM (0x20) is in the ISA and step 7 implements it: an all-zero MM word has N = KB = 0,
    # which both the ISA encoder refuses and the MXU's own checks reject before any write
    # (error 9, the bounds/alignment code; isasim raises "MM: N and KB must be at least 1")
    mini.assert_errors([I.Instr(0x20), I.halt()], code=9, params_=SMALL)
    # HALT CHAIN: not in the mini-core (and isasim rejects a chain to zero instructions)
    mini.assert_errors([I.halt(chain=True), I.halt()], code=1, params_=SMALL)
    # an instruction fetched past the end of the program image: the padded IMEM words are
    # illegal opcodes, which errors like isasim's "pc past end of program"
    mini.assert_errors([I.li(1, 1)], code=1, params_=SMALL)
