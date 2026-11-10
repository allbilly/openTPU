# The board interface (step 11): shell, host stack and the `tb_board` contract

Step 9 imported the production core and its Verilator core harness; step 11 adds the product
tree's **board path** on top of it, byte-identically from `ca05e24f`:

* the RTL shell (`rtl/shell/`: `otpu_board`, `otpu_ctrl`, `otpu_mem_ch`, `otpu_axi_split2`,
  `otpu_afifo`, `otpu_trace`) and the board-model testbench (`sim/verilator/tb_board.sv` with
  the channel models `otpu_chmem.sv`/`otpu_ldn_model.sv`) — all already in the tree since step 9
  imported `rtl/` and `sim/verilator/` wholesale;
* the host driver (`opentpu/host/{__init__,regs,runstate,board,fake,memcal,ddrcal,selfcal,
  checks}.py`), numpy only at import time (no torch, no PCIe/JTAG-only modules).

`ladder/harness/board.py` wraps them for the ladder: a `SimTransport` (the Verilator board
model: two channel images per slice, register operations queued as a script and replayed by
`tb_board` in one simulation per flush), a `Board` on it, `isasim.board_config`-derived
configuration (D = 128, small DRAM for tests), the register/Config identity handshake and the
product's own `checks.run_demo` acceptance helper.

## What the board interface is

* **Logical DRAM.** One logical DRAM; beat `b` of chunk `m` lives on channel `b % 2` at
  `BASE[c] + m * 64` (hashed when the build sets CHASH: `(b % 2) ^ parity(m)`).
  `Board.read`/`Board.write` take arbitrary byte ranges; whole 64-byte beats are
  read-modified-written in the memory path (`split`/`join`/`channel_map`, `otpu_native_dram.sv`).
* **Registers** (`opentpu/host/regs.py`): `ID` = `0x4F545055`, `VERSION` packs D/MCOLS/LANES,
  `REGMAP` = 5, `CAPS`/`CAPS2` (the MX numerics bit29, 4-bit weights, PAIR, DSTEP, the stream
  engine, run arguments, ACT_ROWS, WAITW, GATHER, host-calibrated LiteDRAM, ...), the
  `CYCLES`/`ICOUNT` and activity counters, the trace, the `ARG0..7` run arguments, and the
  `CFG_*` registers from which a host derives its `isasim.Config` (`device_config`; a CFG_HASH
  or numerics mismatch raises `ConfigMismatch`, it is never a warning).
* **Loader and run.** `Board.load(PROG_AT, prog)` writes the image and `PROG_ADDR`/`PROG_N`;
  `CTRL.LOAD` copies it into IMEM; `Board.run()` raises `CTRL.RUN` and polls `STATUS` for
  `HALTED` (or `ERROR`/`WAIT_TO`/`ECC_DED`), returning the per-slice `ICOUNT`, `CYCLES` and the
  memory counters. `PROG_AT = 0x3C0000` keeps the image out of the program's data region.
* **Board model.** `SimTransport` has `devname = None` (no device lock), and every flush is one
  `tb_board` simulation; the channel images persist across flushes, the core starts from reset
  each time. `FakeTransport` is the pure-Python register/memory fake for the address-map,
  channel-map and tenancy tests.

## Test contract (`ladder/tests/test_step11_board.py`)

1. **Pure Python** (no Verilator, seconds): the logical-DRAM interleave and its CHASH variant,
   unaligned read-modify-write through `Board.read`/`Board.write`, the bounded per-call H2C
   writes during a run, the channel map from the CFG registers, and a two-slice fake card's
   per-slice DRAM/loader/ICOUNT.
2. **Board model** (`SimTransport`/`tb_board`, the heavy part): the register identity handshake
   (ID/VERSION/REGMAP/CAPS/CAPS2/CFG_* plus `device_config`, including its refusal of a tampered
   CFG_HASH and of a bitstream without the MX numerics), a full program load -> run -> DRAM
   readback compared **bit for bit** with `opentpu/isasim.py` (the product's own
   `checks.run_demo`), the partial-beat/masked-write case, and a hand-assembled program's
   loader/run/counters path.

The first board call compiles `tb_board` with Verilator, which is the rung's cost; run step 11
through `python3 ladder/run.py step 11` (shared-host lock + thermal gate).  The build cache lives
under `build/verilator/` (gitignored).  On this shared laptop the board harness sets Verilator's
compiler jobs to one (`rtlsim.VFLAGS` `-j 1` instead of step 9's `-j 2`): the host's thermal
guard kills the ~45-source compile above ~95 C, and one compiler job keeps it cool enough to
finish.  The flags are part of `rtlsim`'s build-cache key, so the warm `tb_board_*` cache is
reused deterministically by every later run of this commit.
