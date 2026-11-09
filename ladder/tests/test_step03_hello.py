"""Step-3 acceptance: a hand-assembled "hello arithmetic" program on the golden ISA simulator.

No compiler and no RTL are involved: every 8-word instruction below is built by hand from
the encodings in docs/isa.md, loaded into the import's `opentpu.isasim.Machine` (the bit-exact
golden model), and its final register, TMEM and DRAM state is checked against the arithmetic
worked out on paper.  This is the smallest end-to-end proof that the golden contract runs in
the ladder tree -- the same `Machine` every mini-core rung (steps 4-8) is compared against.

    DRAM[0x100..] = [1.5, -2.25]        (two fp32 words, byte address 0x100)
    R1 = 3; R2 = 0; T[0] = +0
    LOOP 3:  T[0] = T[0] + 1.0          -> +3.0
             R2 = R2 + 7                -> 21
    LD  DRAM[0x100] -> T[4], T[5]
    T[8], T[9] = [T[4], T[5]] * 2.0     -> [3.0, -4.5]
    ST  T[8], T[9] -> DRAM[0x200]
    HALT
"""
from __future__ import annotations

import numpy as np

from opentpu import Config, isa as I
from opentpu.isasim import Machine


def hello_program() -> list[I.Instr]:
    return [
        I.li(1, 3),                                          # R1 = 3, the loop's count
        I.vop(I.V_FILL, 0, 0, 0, 1, 1, 0, 0, 0, I.B_SCALAR, 0.0),   # T[0] = +0
        I.loop(2, 0, rcount=1),                              # body = 2 instructions, R1 times
        I.vop(I.V_ADD, 0, 0, 0, 1, 1, 0, 0, 0, I.B_SCALAR, 1.0),    # T[0] += 1.0
        I.addi(2, 2, 7),                                     # R2 += 7
        I.ld(0x100, 4, 2),                                   # T[4..5] = DRAM[0x100..0x108)
        I.vop(I.V_MUL, 8, 4, 0, 1, 2, 1, 1, 0, I.B_SCALAR, 2.0),    # T[8..9] = T[4..5] * 2
        I.st(0x200, 8, 2),                                   # DRAM[0x200..] = T[8..9]
        I.halt(),
    ]


def test_hello_arithmetic_on_the_golden_machine():
    dram = np.zeros(1 << 12, np.uint8)
    dram[0x100:0x108] = np.array([1.5, -2.25], np.float32).view(np.uint8)
    s = Machine(Config(S=1), [hello_program()], [dram]).run().slices[0]

    # control flow and the register file: 3 iterations, R2 = 3 x 7
    assert s.halted and s.R[1] == 3 and s.R[2] == 21
    # TMEM is fp32 words: the loop left +3.0 in T[0], and LD copied the backlog bits
    assert np.array_equal(s.tget([0]), np.array([3.0], np.float32))
    assert np.array_equal(s.tmem[4:6], np.array([1.5, -2.25], np.float32).view(np.uint32))
    # the VPU's MUL wrote exact halves: 1.5 * 2 = 3.0, -2.25 * 2 = -4.5
    assert np.array_equal(s.tget([8, 9]), np.array([3.0, -4.5], np.float32))
    # ST put those bits back into DRAM, byte addressed
    assert np.array_equal(s.m32[0x200 // 4:0x208 // 4],
                          np.array([3.0, -4.5], np.float32).view(np.uint32))
    # 9 instruction slots; 13 executed: LI, FILL, LOOP, HALT and 3 x (ADD + ADDI) + LD + VOP
    # + ST (the loop body runs three times)
    assert s.icount == 13
    # nothing after HALT and no uninitialised memory: the rest of DRAM is unchanged
    assert not s.dram[:0x100].any() and not s.dram[0x108:0x200].any() \
        and not s.dram[0x208:].any()


def test_hello_program_is_hand_encodable_from_docs_isa_md():
    """The first instruction's words are the docs/isa.md encoding: w0 packs
    opcode[7:0] | ra[11:8] | rb[15:12] | rc[19:16] | rd[23:20] | flags[31:24], w1 the
    immediate; every instruction is 8 words, so a program image is `8 * len(program)` words."""
    words = I.assemble(hello_program())
    assert words.dtype == np.uint32 and len(words) == 8 * len(hello_program())
    assert words[:8].tolist() == [0x00100002, 3, 0, 0, 0, 0, 0, 0]   # LI R1, 3
    assert [int(x) for x in I.Instr.decode(words[0:8]).encode()] == words[0:8].tolist()
    # the program image the host writes to DRAM is `8 * len(program)` words, byte aligned
    assert words.nbytes == 8 * 4 * len(hello_program()) == 288
