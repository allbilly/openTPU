"""Directed `opentpu.isasim` semantics: LI/ADDI/LOOP/HALT, TMEM, LD/ST, run arguments.

The production `tests/test_isa.py` (imported beside this file as `test_step03_isa.py`)
covers the encodings and the wider instruction set.  This file adds the small directed
checklist that the ladder's mini-core rungs (steps 4-8) replay against `isasim`: control
flow and the register file, word-addressed TMEM, byte-addressed and word-aligned DRAM,
instruction counting, and the run arguments (`R8..R15`, docs/isa.md "Arguments") that the
board programs and later the resident decode loop use.
"""
from __future__ import annotations

import numpy as np
import pytest

from opentpu import Config, isa as I
from opentpu.isasim import Machine, SimError


def run1(prog, dram=None, cfg=Config(S=1), args=None):
    return Machine(cfg, [prog], [dram], args=args).run().slices[0]


# ------------------------------------------------------------------------- control flow
def test_li_addi_and_the_register_file():
    prog = [I.li(0, 99), I.li(1, 7), I.addi(2, 1, 35), I.addi(3, 0, 9), I.halt()]
    s = run1(prog)
    assert s.R[0] == 0                      # LI to R0 writes nothing
    assert s.R[1] == 7 and s.R[2] == 42
    assert s.R[3] == 9                      # R0 reads as 0
    assert s.reg(0) == 0


def test_registers_are_32_bit_words():
    prog = [I.li(1, 0xFFFFFFFE), I.addi(2, 1, 4), I.halt()]
    s = run1(prog)
    assert s.R[1] == 0xFFFFFFFE and s.R[2] == 0x00000002     # mod 2^32, as the board's


def test_loop_body_runs_count_times_and_nests():
    # outer: 4 iterations of (R1 += 2; inner: 3 x R2 += 1, then a NOP so the inner body ends
    # before the outer one -- docs/isa.md LOOP forbids bodies ending on the same instruction)
    prog = [I.li(1, 0), I.li(2, 0),
            I.loop(4, 4),                   # body = 4 instructions, 4 iterations
            I.addi(1, 1, 2),
            I.loop(1, 3),                   # inner: body = 1 instruction, 3 iterations
            I.addi(2, 2, 1),
            I.nop(),
            I.halt()]
    s = run1(prog)
    assert s.R[1] == 8 and s.R[2] == 12
    # li, li, loop, halt + 4 x (addi + loop + 3 x addi + nop)
    assert s.icount == 3 + 1 + 4 * (2 + 3 + 1)


def test_loop_count_comes_from_the_register_field():
    # LOOP count = R[ra] + w2 (docs/isa.md): R1 + 0 = 5
    prog = [I.li(1, 5), I.loop(1, 0, rcount=1), I.addi(2, 2, 3), I.halt()]
    assert run1(prog).R[2] == 15


def test_loop_zero_count_skips_the_body():
    prog = [I.li(1, 0), I.loop(1, 0, rcount=1), I.addi(2, 2, 3), I.halt()]
    s = run1(prog)
    assert s.R[2] == 0 and s.icount == 3     # li, loop, halt


def test_halt_is_final_for_the_slice():
    prog = [I.li(1, 1), I.halt(), I.li(1, 2), I.li(2, 3)]
    s = run1(prog)
    assert s.halted and s.R[1] == 1 and s.R[2] == 0
    assert s.icount == 2                    # nothing after HALT runs


def test_pc_past_the_program_end_is_an_error():
    with pytest.raises(SimError, match="past end of program"):
        run1([I.nop()])


# ------------------------------------------------------------------------- TMEM
def test_tmem_is_32_bit_word_addressed():
    prog = [I.vop(I.V_FILL, 3, 0, 0, 1, 4, 1, 0, 0, I.B_SCALAR, 2.5), I.halt()]
    s = run1(prog)
    assert np.array_equal(s.tget([3, 4, 5, 6]), np.full(4, 2.5, np.float32))
    assert np.array_equal(s.tmem[3:7],
                          np.array([0x40200000] * 4, np.uint32))   # 2.5 as raw fp32 bits


def test_tmem_index_out_of_range_is_an_error():
    cfg = Config(S=1, TMEM_WORDS=64)
    with pytest.raises(SimError, match="TMEM index out of range"):
        run1([I.vop(I.V_FILL, 64, 0, 0, 1, 1, 0, 0, 0, I.B_SCALAR, 1.0), I.halt()], cfg=cfg)


# ------------------------------------------------------------------------- DRAM (LD / ST)
def test_ld_st_round_trip_is_bit_exact():
    # +0, -0, 1.5, a NaN, +inf and the smallest normal: the raw bits must survive LD and ST
    words = np.array([0x00000000, 0x80000000, 0x3FC00000, 0x7FC00000, 0x7F800000, 0x00800000],
                     np.uint32)
    dram = np.zeros(1 << 12, np.uint8)
    dram[0x100:0x100 + 4 * len(words)] = words.view(np.uint8)
    s = run1([I.ld(0x100, 7, 6), I.st(0x300, 7, 6), I.halt()], dram)
    assert np.array_equal(s.tmem[7:13], words)                       # DRAM -> TMEM: verbatim
    assert np.array_equal(s.dram[0x300:0x300 + 24], words.view(np.uint8))


def test_dram_is_byte_addressed_but_word_aligned():
    dram = np.zeros(1 << 12, np.uint8)
    dram[0x204:0x208] = np.array([0x11223344], np.uint32).view(np.uint8)
    s = run1([I.ld(0x204, 2, 1), I.st(0x408, 2, 1), I.halt()], dram)
    assert s.tmem[2] == 0x11223344 and s.dram[0x408:0x40C].tobytes() == \
        np.array([0x11223344], np.uint32).tobytes()


def test_unaligned_dram_access_is_refused():
    for prog in ([I.ld(2, 0, 1), I.halt()], [I.st(6, 0, 1), I.halt()]):
        with pytest.raises(SimError, match="bad DRAM word address"):
            run1(prog)


def test_ld_past_the_end_of_dram_is_refused():
    cfg = Config(S=1, DRAM_BYTES=4096)
    with pytest.raises(SimError, match="bad DRAM word address"):
        run1([I.ld(4092, 0, 2), I.halt()], cfg=cfg)


# ------------------------------------------------------------------------- run arguments
def test_run_arguments_fill_r8_to_r15():
    """Machine(..., args): the run's arguments are R8..R15 at the start (docs/isa.md
    "Arguments"); an unwritten one is 0."""
    prog = [I.addi(1, 8, 1), I.addi(2, 15, 2), I.addi(3, 10, 0), I.halt()]
    args = [10, 0, 0, 0, 0, 0, 0, 20]
    s = run1(prog, args=args)
    assert s.R[8] == 10 and s.R[15] == 20
    assert s.R[1] == 11 and s.R[2] == 22 and s.R[3] == 0
    assert run1(prog).R[8] == 0                       # no args: every argument reads 0
