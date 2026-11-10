"""Ladder step 11 — the board shell and the host interface, in simulation.

Step 9 imported the production core and its `tb_top` harness; step 11 adds the product tree's
board shell (`rtl/shell/`, already in the step-9 `rtl/` import), the board-model testbench
(`sim/verilator/tb_board.sv` with its channel models, also in the step-9 `sim/verilator/`
import) and the host stack that drives it (`opentpu/host/{regs,runstate,board,fake,memcal,
ddrcal,selfcal,checks}.py`, numpy only).  This file is the rung's acceptance, in the product's
own two tiers:

* **pure Python** (no Verilator): the logical-DRAM address map (`split`/`join`, the channel
  interleave and its CHASH hashing), unaligned read-modify-write through the board interface,
  the per-call write behaviour during a run, the channel map from the CFG registers and a
  two-slice fake card (program load/run/ICOUNT over `FakeTransport`);
* **board model** (`SimTransport` / `tb_board`, Verilator; the heavy part of the rung): the
  register identity handshake (ID, VERSION, REGMAP, CAPS/CAPS2, the CFG_* registers and the
  Config the host derives from them, with its CFG_HASH/numerics refusal), and a full
  program load -> run -> DRAM readback through `Board.load`/`Board.run` compared bit for bit
  with `opentpu.isasim.Machine` (the product's own `opentpu/host/checks.py::run_demo`).

The cases are adapted from the product's `tests/test_board.py` (its torch-free part; the file's
module-level `importorskip("torch")` would skip all of it here) and `tests/test_observability.py`
(register map), with attribution.  The Verilator build of `tb_board` happens on the first
`Board` call: run this file through `python3 ladder/run.py step 11` (heavy gate: shared-host
lock + thermal check), never directly.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ladder.harness import board as B  # noqa: E402
from opentpu import isa as I  # noqa: E402
from opentpu.host import regs as R  # noqa: E402
from opentpu.host.board import (BASE, BEAT, Board, ConfigMismatch, SimTransport,  # noqa: E402
                                channel_map, device_config, join, split)
from opentpu.host.checks import demo_image, demo_program, masked_program, PROG_AT  # noqa: E402
from opentpu.host.fake import FakeTransport  # noqa: E402

CFG = B.CFG


@pytest.fixture(scope="session")
def have_verilator():
    import shutil
    if shutil.which("verilator") is None:
        pytest.skip("verilator not installed")
    return True


@pytest.fixture(scope="module")
def model(have_verilator):
    """The board model, built once: the Verilator build is the expensive part of the rung."""
    t = B.transport(ch_bytes=CFG.DRAM_BYTES // 2)
    b = Board(t)
    yield b
    b.close()


# ---------------------------------------------------------------------------- address map
class MemTransport:
    """Two channel memories in RAM and the identity registers (CAPS: CHASH or not): exercises
    the Board's logical-address read/write path only (the product's test helper)."""

    def __init__(self, ch_bytes=1 << 16, chash=False):
        self.ch = [np.zeros(ch_bytes, np.uint8) for _ in range(2)]
        self.regs = {R.R_VERSION: 128 << 16 | 2 << 8 | 8, R.R_REGMAP: 3,
                     R.R_CAPS: R.CAP_CHASH if chash else 0}

    def reg_read_many(self, offs):
        return [self.regs.get(o, 0) for o in offs]

    def mem_write(self, c, off, data):
        self.ch[c][off:off + len(data)] = data

    def mem_read(self, c, off, n):
        return self.ch[c][off:off + n].copy()


def test_split_matches_the_rtl_interleave():
    """Logical beat b lives on channel b % 2 at offset (b // 2) * 64 (otpu_native_dram.sv)."""
    data = np.arange(8 * BEAT, dtype=np.uint32).astype(np.uint8)
    parts = split(256, data)
    for c, off, part in parts:
        assert off == 128
        for k in range(len(part) // BEAT):
            b = 256 // BEAT + 2 * k + c
            assert np.array_equal(part[k * BEAT:(k + 1) * BEAT],
                                  data[(b - 4) * BEAT:(b - 3) * BEAT])
    assert np.array_equal(join([p for _, _, p in parts]), data)
    assert BASE == (0, 0x8000_0000)


def test_split_hashed_interleave():
    """CHASH: logical beat b of chunk m is on channel (b % 2) ^ parity(m) (otpu_native_dram)."""
    data = np.arange(64 * BEAT, dtype=np.uint32).astype(np.uint8)
    parts = split(512, data, chash=True)
    for c, off, part in parts:
        assert off == 256
        for k in range(len(part) // BEAT):
            m = 512 // (2 * BEAT) + k
            b = 2 * m + (c ^ (bin(m).count("1") & 1))
            assert np.array_equal(part[k * BEAT:(k + 1) * BEAT],
                                  data[(b - 8) * BEAT:(b - 7) * BEAT])
    assert np.array_equal(join([p for _, _, p in parts], 512, chash=True), data)


@pytest.mark.parametrize("chash", [False, True])
@pytest.mark.parametrize("addr,n", [(0, 128), (4, 8), (60, 8), (100, 300), (127, 1)])
def test_unaligned_read_modify_write(addr, n, chash):
    """Board.write/read are arbitrary byte ranges: whole 64-byte beats are read-modified-written."""
    rng = np.random.default_rng(addr + n)
    t = MemTransport(chash=chash)
    b = Board(t, check=False)
    ref = rng.integers(0, 256, 1 << 14).astype(np.uint8)
    b.write(0, ref)
    new = rng.integers(0, 256, n).astype(np.uint8)
    b.write(addr, new)
    ref[addr:addr + n] = new
    assert np.array_equal(b.read(0, len(ref)), ref)
    assert np.array_equal(b.read(addr, n), new)
    for beat in range(len(ref) // BEAT):
        c = beat % 2 ^ (chash and bin(beat // 2).count("1") & 1)
        off = (beat // 2) * BEAT
        assert np.array_equal(t.ch[c][off:off + BEAT], ref[beat * BEAT:(beat + 1) * BEAT])


@pytest.mark.parametrize("chash", [False, True])
@pytest.mark.parametrize("addr,n", [(0, 1 << 16), (4096 + 64, 20000)])
def test_writes_during_a_run_move_h2c_per_call(addr, n, chash):
    """A transport with run_h2c (the card's XDMA) takes Board.write's bytes in bounded calls
    while a run is in flight; outside a run, one call per channel (product's case)."""
    class T(MemTransport):
        run_h2c = 4096

        def __init__(self):
            super().__init__(ch_bytes=1 << 17, chash=chash)
            self.calls = []

        def mem_write(self, c, off, data):
            self.calls.append(len(data))
            super().mem_write(c, off, data)

        def reg_write(self, off, val):
            pass

        def reg_read(self, off):
            return R.ST_RUN | R.ST_CALIB0 | R.ST_CALIB1 if off == R.R_STATUS else 0

    rng = np.random.default_rng(n)
    t = T()
    b = Board(t, check=False)
    ref = rng.integers(0, 256, 1 << 17).astype(np.uint8)
    b.write(0, ref)
    assert t.calls == [1 << 16, 1 << 16]
    b.start()
    assert b.in_run
    t.calls = []
    new = rng.integers(0, 256, n).astype(np.uint8)
    b.write(addr, new)
    ref[addr:addr + n] = new
    assert max(t.calls) <= 4096 and sum(t.calls) >= n
    b.in_run = False
    assert np.array_equal(b.read(0, len(ref)), ref)


def test_channel_map_from_the_cfg_registers():
    """Register map 4: channel j = 2s + c (slice s's channel c) at j x the bytes a slice
    addresses per channel; the YPCB-00338's two are BASE, as before map 4."""
    ypcb = {"cfg": {"S": 1, "channels": 2, "channel_bytes": 1 << 31}}
    assert channel_map(ypcb) == BASE == channel_map({"cfg": None}) == channel_map(None)
    bcu = {"cfg": {"S": 2, "channels": 2, "channel_bytes": 1 << 31}}
    assert channel_map(bcu) == (0, 1 << 31, 2 << 31, 3 << 31)


def _bcu_cfg() -> dict:
    """The CFG_* registers of the BCU1525's build (targets/bcu1525.toml; product helper)."""
    from opentpu.target import arch_hash, build_config, load
    t = load("bcu1525")
    a, u, p = t.arch, t.uarch, t.platform
    return dict(S=a["S"], TMEM_WORDS=a["TMEM_WORDS"], IMEM_WORDS=a["IMEM_WORDS"],
                ACT_BLOCKS=a["ACT_BLOCKS"], DRAM_BYTES=a["DRAM_BYTES"],
                channels=p["channels_per_slice"], channel_bytes=p["channel_bytes"],
                MXU_IMPL=u["MXU_IMPL"], TMEM_IMPL=u["TMEM_IMPL"], VPU_CL=u["VPU_CL"],
                ULANES=u["ULANES"], platform=t.platform_id, hash=arch_hash(build_config(t)))


def test_two_slices_on_a_fake_card():
    """A two-slice bitstream (BCU1525 CFG registers) on a fake card: the channel map from the
    registers, each slice's DRAM, the program loader's per-slice lists and ICOUNT."""
    from opentpu.host.board import XdmaTransport
    f = FakeTransport(devname=None, regmap=4, cfg=_bcu_cfg(), ch_bytes=1 << 16)
    b = Board(f, lock=False)
    i = b.info()
    assert b.slices == 2 and len(f.ch) == 4
    assert channel_map(i) == (0, 1 << 31, 2 << 31, 3 << 31)
    assert XdmaTransport.bases == BASE
    x = np.arange(1000, dtype=np.uint32).view(np.uint8)
    b.write(256, x, 1)
    assert not f.ch[0].any() and not f.ch[1].any() and f.ch[2].any() and f.ch[3].any()
    assert np.array_equal(b.read(256, len(x), 1), x)
    y = np.arange(37, dtype=np.uint8)
    b.write(100, y)
    assert np.array_equal(b.read(100, 37), y) and np.array_equal(b.read(256, len(x), 1), x)
    w = np.asarray(I.assemble([I.nop(), I.nop(), I.halt()]), np.uint32)
    b.load_program(4096, w)
    halt = np.asarray(I.assemble([I.halt()]), np.uint32)
    assert f.regs[R.R_PROG_N] == 3
    assert np.array_equal(b.read(4096, 4 * len(w)).view(np.uint32), w)
    assert np.array_equal(b.read(4096, 4 * len(w), 1).view(np.uint32),
                          np.concatenate([halt, np.zeros(len(w) - len(halt), np.uint32)]))
    assert b.run()["instructions"] == [3, 3]
    b.load_program(8192, [halt, w])
    assert np.array_equal(b.read(8192, 4 * len(w), 1).view(np.uint32), w)
    assert np.array_equal(b.read(8192, 4 * len(halt)).view(np.uint32), halt)
    with pytest.raises(ValueError, match="3 programs for a bitstream of 2 slices"):
        b.load_program(8192, [w, w, w])


# ---------------------------------------------------------------------------- board model
def test_board_model_identity(model):
    """The register identity: ID, VERSION, REGMAP, CAPS/CAPS2, BUILD_ID, CORE_KHZ, DDR_MTS, the
    CFG_* registers, and the Config the host derives from them (its CFG_HASH check passes)."""
    v = model.t.reg_read_many([R.R_ID, R.R_VERSION, R.R_REGMAP, R.R_CAPS, R.R_CAPS2,
                               R.R_BUILD_ID, R.R_CORE_KHZ, R.R_DDR_MTS, R.R_ACT_ROWS])
    ident, ver, regmap, caps, caps2, bid, khz, mts, act_rows = v
    assert ident == R.ID_OTPU
    assert ver == (CFG.D << 16) | (CFG.MCOLS << 8) | CFG.LANES
    assert regmap >= 5
    c = R.caps(caps)
    assert c["mx"]                       # the MX numerics (CAPS bit29) the host requires
    for bit in ("trace", "temp", "i2c", "ddr", "w4", "pair", "dstep", "chash", "act_rows",
                "args", "stream", "gen", "waitw"):
        assert c[bit], f"CAPS bit {bit} clear"
    # HOSTCAL (CAPS bit27, host-calibrated LiteDRAM) is the card's; the model's channels are
    # not LiteDRAM, so it is off here (the product's exact-CAPS assertion agrees)
    assert R.caps2(caps2)["gather"] == model.t.gather
    assert bid == B.TB_BUILD_ID
    assert khz == 100_000 and mts == 1066
    info = model.info()
    assert info["regmap"] == regmap and info["calibrated"]
    assert info["D"] == CFG.D and info["MCOLS"] == CFG.MCOLS and info["LANES"] == CFG.LANES
    cfg = info["cfg"]
    assert (cfg["S"], cfg["TMEM_WORDS"], cfg["IMEM_WORDS"], cfg["ACT_BLOCKS"]) == \
        (1, 1 << 16, 1 << 15, 128)
    assert (cfg["DRAM_BYTES"], cfg["channels"], cfg["channel_bytes"]) == (1 << 32, 2, 1 << 31)
    icfg = device_config(info)           # the CFG_HASH/numerics handshake must pass
    assert icfg.D == CFG.D and icfg.MCOLS == CFG.MCOLS and icfg.LANES == CFG.LANES
    assert icfg.S == 1 and icfg.TMEM_WORDS == 1 << 16 and icfg.IMEM_WORDS == 1 << 15
    assert icfg.ACT_BLOCKS == 128 and act_rows == icfg.act_rows


def test_board_model_refuses_a_mismatched_bitstream(model):
    """The identity handshake is a refusal, not a warning: a tampered CFG_HASH or bitstream
    without the MX numerics (CAPS bit29 clear) is a ConfigMismatch (pure dict manipulation on
    the live model's info: no extra simulation)."""
    import copy
    info = copy.deepcopy(model.info())
    good = copy.deepcopy(info)
    device_config(good)                                    # (the honest one passes)
    bad = copy.deepcopy(good)
    bad["cfg"]["hash"] = int(bad["cfg"]["hash"]) ^ 1
    with pytest.raises(ConfigMismatch):
        device_config(bad)
    bad = copy.deepcopy(good)
    bad["caps"] = dict(bad["caps"], mx=False)
    with pytest.raises(ConfigMismatch):
        device_config(bad)


def test_board_model_program_matches_isasim(model):
    """The acceptance: the demo program (LD/ST, VOPs, QACT, MM, QST) is written, loaded and run
    through the board interface and every DRAM byte below PROG_AT equals isasim's Machine; the
    counters move and the run retires the ISA simulator's instruction count."""
    ok, msg, st = B.run_demo(model, CFG)
    assert ok, msg
    # the same program and image on the ISA simulator: the board's ICOUNT and the whole DRAM
    # below PROG_AT must be the simulator's (run_demo checks both; the direct readback below is
    # the ladder's own check of the same state)
    want = B.isa_state([I.ld(0, 0, CFG.TMEM_WORDS)] + demo_program(), demo_image())
    assert st["instructions"][0] == want.icount
    assert st["b_reads"] > 0 and st["a_writes"] > 0 and st["cycles"] > 0
    # the demo's DRAM region is exactly isasim's, byte for byte (run_demo already asserts it)
    img = demo_image()
    sl = B.isa_state([I.ld(0, 0, CFG.TMEM_WORDS)] + demo_program(), img)
    got = model.read(0, PROG_AT)
    assert np.array_equal(got, sl.dram[:PROG_AT])


def test_board_model_partial_beats_and_counters(model):
    """Unaligned/partial DRAM writes reach the model through the channel interleave
    (masked_program: a byte range edited by the host and the card's partial beats), with the
    read/write counters moving (the product's partial-write case)."""
    ok, msg, st = B.run_demo(model, CFG, prog=masked_program())
    assert ok, msg
    assert st["a_writes"] > 500 and st["b_writes"] > 20
    assert np.array_equal(model.read(0, PROG_AT), B.isa_state(
        [I.ld(0, 0, CFG.TMEM_WORDS)] + masked_program(), demo_image()).dram[:PROG_AT])


def test_board_model_load_run_counters(model):
    """A small hand-assembled program through the loader/run/counter path: LOAD, RUN, HALTED,
    ICOUNT/CYCLES and zero ERROR, and the program's own DRAM writes match isasim."""
    prog = [I.vop(I.V_FILL, 0, 0, 0, 1, 1, 0, 0, 0, I.B_SCALAR, 1.0),
            I.li(1, 0x40000),
            I.loop(3, 4),
            I.st(0, 0, 1, ra=1, rb=0),
            I.addi(1, 1, 4),
            I.nop(),
            I.halt()]
    model.write(0x40000, np.zeros(16, np.uint8))
    model.load(PROG_AT, prog)
    st = model.run(timeout=10.0)
    assert st["instructions"][0] == 4 + 3 * 4           # FILL, LI, LOOP, HALT + 4 x (ST, ADDI, NOP)
    stat = st["status"]
    assert stat & R.ST_HALTED and not stat & R.ST_ERROR
    sl = B.isa_state([I.ld(0, 0, CFG.TMEM_WORDS)] + prog,
                     np.zeros(PROG_AT, np.uint8))
    assert np.array_equal(model.read(0x40000, 16), sl.dram[0x40000:0x40010])
