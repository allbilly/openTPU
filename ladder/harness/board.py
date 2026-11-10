"""Ladder step 11 — board-shell and host-interface harness (`tb_board` / `SimTransport`).

Step 11 imports the product tree's host stack (`opentpu/host/{regs,runstate,board,fake,
memcal,ddrcal,selfcal,checks}.py`, numpy only; the RTL shell and `sim/verilator/tb_board.sv`
with its channel models came with step 9's `rtl/`+`sim/verilator/` import).  This module is the
ladder's thin harness around it:

* `config()` — the ISA configuration the board model implements (`opentpu.isasim.board_config`,
  D = 128 ... with a small `DRAM_BYTES` for the tests, like the product's `sim_board_config()`);
* `transport()` / `board()` — a `SimTransport` (the Verilator model of the board: two channel
  images per slice, the register script replayed at each flush) and a `Board` on it.  The first
  `Board` call builds `sim/verilator/tb_board.sv` with Verilator through `opentpu.rtlsim`
  (cached under `build/verilator`), which is why step 11 is a heavy rung;
* `checks.run_demo` re-exported for the product's own acceptance path: the demo program
  (LD/ST, VOPs, QACT, MM, QST) runs through the board's loader/run/counters and the whole DRAM
  below `PROG_AT` is compared with `opentpu.isasim.Machine` bit for bit;
* `identity()` — the register-map/identity handshake (`ID`, `VERSION`, `REGMAP`, `CAPS`,
  `CAPS2`, `CFG_*`, `BUILD_ID`, `CORE_KHZ`, `DDR_MTS`) and `device_config(info)`, the Config a
  host derives from the bitstream's registers (it refuses a CFG_HASH / numerics mismatch).

Everything here is numpy-only at import time (no torch, no PCIe/JTAG modules); the run-state
directory is private to this pytest session (`OTPU_RUN_DIR`) and the image/program caches are
off, so the ladder tests never touch another session's device locks or caches.
"""
from __future__ import annotations

import atexit
import os
import shutil
import tempfile
from pathlib import Path

import numpy as np

# A private run-state directory for this process (before the host modules read it), so the
# shared /tmp/otpu device locks and fake-board state of the sibling sessions cannot collide.
if not os.environ.get("OTPU_RUN_DIR"):
    _dir = tempfile.mkdtemp(prefix="otpu-run-ladder11-")
    os.environ["OTPU_RUN_DIR"] = _dir
    atexit.register(shutil.rmtree, _dir, True)
for _k in ("OTPU_IMAGE_CACHE", "OTPU_IMG_CACHE", "OTPU_PROG_CACHE"):
    os.environ[_k] = "0"

from opentpu import isa as I, isasim, rtlsim                    # noqa: E402

# The tb_board Verilator build is the heavy part of this rung: ~45 RTL/sim sources through
# Verilator's C++ backend.  On this shared laptop the host's power/thermal guard kills the
# compile when it sustains ~95 C, and step 9's ladder edit (VFLAGS "-j 2") still lets the
# compiler heat the package past that.  The board harness therefore builds the model with a
# single compiler job: the same deterministic flags every run (VFLAGS is part of
# opentpu.rtlsim's build-cache key, so the warm cache this produces is reused by any later run
# of this commit), just slower to compile and cool enough to finish.
if "-j" in rtlsim.VFLAGS:
    _i = rtlsim.VFLAGS.index("-j")
    rtlsim.VFLAGS[_i + 1] = "1"
from opentpu.host import checks                                # noqa: E402
from opentpu.host import regs as R                             # noqa: E402
from opentpu.host.board import Board, SimTransport, device_config   # noqa: E402

TB_BUILD_ID = 0x0B0A4D00        # tb_board.sv's default BUILD_ID register


def config(**kw) -> isasim.Config:
    """The board model's ISA configuration: `board_config` with a small DRAM for the tests
    (the product's `tests/conftest.py::sim_board_config`), SEQ_WC from the simulated uarch."""
    kw.setdefault("DRAM_BYTES", 1 << 22)
    kw.setdefault("SEQ_WC", bool(rtlsim.UARCH.get("SEQ_WC")))
    return isasim.board_config(**kw)


CFG = config()


def transport(ch_bytes: int | None = None, native=None, seed: int = 3, stall: int = 30,
              params: dict | None = None) -> SimTransport:
    """The Verilator model of the board (the channel images hold 2 x ch_bytes per slice)."""
    ch = CFG.DRAM_BYTES // 2 if ch_bytes is None else ch_bytes
    p = {"BUILD_ID": TB_BUILD_ID, "CORE_KHZ": 100_000, "DDR_MTS": 1066}
    p.update(params or {})
    return SimTransport(ch_bytes=ch, stall=stall, seed=seed, params=p, native=native)


def board(t: SimTransport | None = None) -> Board:
    """A Board on the board model (devname None: no device lock; check/identity on)."""
    return Board(t or transport())


# ---------------------------------------------------------------------------- build cache probing
# The tb_board build is the rung's one cold cost.  These helpers compute the exact cache entry
# SimTransport would build -- same sources, parameters and (harness-set) VFLAGS, i.e. the same
# opentpu.rtlsim.build_dir key -- without compiling, so the ladder runner's warm mode can skip
# the shared-host flock when the cached Vtb_board already exists (the same idea as step 9/14's
# warm preflights).
class _Captured(Exception):
    pass


def tb_build() -> tuple[Path, Path]:
    """(cache directory, Vtb_board executable) of this harness's tb_board build, from
    rtlsim.build_dir: the SimTransport flush is intercepted at the build step (before any
    compile), its sources/params captured, the key recomputed."""
    t = transport()
    rec: dict = {}

    def spy(top, sources, params=None):
        rec.update(top=top, sources=[Path(s) for s in sources], params=dict(params or {}))
        raise _Captured

    t.queue_read(0)                            # (an empty script returns before the build)
    orig = rtlsim.build_dir
    rtlsim.build_dir = spy                     # type: ignore[assignment]
    try:
        try:
            t.flush()
        except _Captured:
            pass
    finally:
        rtlsim.build_dir = orig                # type: ignore[assignment]
    assert rec, "SimTransport did not reach the Verilator build step"
    d = rtlsim.build_dir(rec["top"], rec["sources"], rec["params"])
    return d, d / f"V{rec['top']}"


def rtl_build_present() -> bool:
    """Whether the tb_board Verilator build this harness uses is already compiled (warm).

    The ladder runner's warm-mode preflight for step 11 calls this (the same contract as the
    step-9 prod harness's preflight): true means a cached Vtb_board exists for the exact
    sources/params/flags this harness builds with, so the shared-host flock can be skipped."""
    try:
        return tb_build()[1].exists()
    except Exception:                          # noqa: BLE001 - no Verilator: not warm either
        return False


build_present = rtl_build_present          # (alias: earlier spelling)


def build_sha256() -> str | None:
    """SHA-256 of the cached Vtb_board executable (None when it is not built)."""
    import hashlib
    d, exe = tb_build()
    if not exe.exists():
        return None
    h = hashlib.sha256()
    with open(exe, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def warm_ready() -> tuple[bool, str]:
    """(ready, why) for the ladder runner's warm mode: the exact tb_board build is cached."""
    try:
        d, exe = tb_build()
    except Exception as e:                     # noqa: BLE001
        return False, f"could not compute the tb_board build key: {e}"
    if exe.exists():
        return True, f"{d.name}/{exe.name} is cached"
    return False, f"no cached {exe} (cold Verilator build: use the heavy gate)"


def identity(b: Board) -> dict:
    """The register identity + the Config the host derives from it (the step-11 handshake)."""
    info = b.info()
    ident = b.t.reg_read(R.R_ID)
    cfg = device_config(info)                      # refuses a CFG_HASH/numerics mismatch
    return {"id": ident, "info": info, "cfg": cfg}


def run_demo(b: Board, cfg: isasim.Config | None = None, prog=None, img=None):
    """The product's own acceptance: run the demo program through the board's loader, run it and
    compare every DRAM byte below PROG_AT with the ISA simulator (checks.run_demo)."""
    return checks.run_demo(b, cfg or CFG, prog=prog, img=img)


def isa_state(prog, img=None, cfg: isasim.Config | None = None):
    """The reference state of `prog` on the same image: an isasim Machine over the DRAM the
    board model holds (`DRAM_BYTES` 8 MiB, as run_demo does)."""
    c = cfg or CFG
    n = min(c.DRAM_BYTES, 1 << 23)
    ref = np.zeros(n, np.uint8)
    if img is not None:
        ref[:len(img)] = np.asarray(img, np.uint8)
    return isasim.Machine(isasim.Config(**{**c.__dict__, "DRAM_BYTES": n}),
                          [list(prog)], [ref]).run().slices[0]
