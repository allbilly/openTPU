"""Ladder step 9 — production-core harness: build, run and compare the product RTL.

Step 9 imports the production core (`rtl/`, `sim/verilator/`, `sim/tech/`, `targets/` and
`opentpu/{rtlsim,simtmp,target}.py`, byte-identical to `ca05e24f` except `rtlsim.py`'s
Verilator `-j 2` ladder edit).  This module is the ladder side of it:

* `CFG` — one small production configuration (the product RTL's parameters all come from the
  `Config`; `rtlsim`'s default UARCH is the console build: WIN 32, RPB 4, WPB 2, systolic MXU);
* `build()` — compile `sim/verilator/tb_top.sv` with Verilator through `opentpu.rtlsim`
  (cached under `build/verilator`, keyed on the sources, parameters, Verilator version and
  VFLAGS; the one ladder edit is `-j 2` because this laptop is shared);
* `run()` — run one hand-assembled program on the RTL and return the final TMEM, DRAM and
  retired-instruction count of the single slice;
* `run_isasim()`, `compare()`, `assert_matches_isasim()` — the tolerance-free comparison with
  the bit-exact golden model (`opentpu.isasim.Machine`), the same oracle the product's own
  `tests/test_rtl.py` uses: every TMEM word and every DRAM byte must be identical.

Everything here needs the Verilator build, which is why step 9 is a heavy rung: run the tests
through `python3 ladder/run.py step 9` so the runner takes the shared-host lock and the
thermal gate.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from opentpu import isa as I, isasim, rtlsim

# One small production configuration for the ladder's replay tests.  The production RTL's
# parameters are settled by this Config (rtlsim.top_params) plus rtlsim's default UARCH; D = 32
# keeps the behavioural DRAM (the AXI board path needs D = 128), while 64K TMEM words and 1 MiB
# of DRAM hold every program the mini-core rungs used, with room to spare.  The same Config goes
# to the RTL and to isasim, so "the same machine" is being compared.
CFG = isasim.Config(S=1, D=32, MCOLS=8, ACT_BLOCKS=64, ACT_ROWS=8,
                    TMEM_WORDS=1 << 16, IMEM_WORDS=1 << 12, DRAM_BYTES=1 << 20, LANES=8)

# The production core overlaps its units, so these replays finish in far fewer cycles than the
# serial mini-core's; a generous ceiling only bounds a broken program.
MAX_CYCLES = 2_000_000

_built: Path | None = None


def config() -> isasim.Config:
    """The Config of the production simulation (RTL and isasim share it)."""
    return CFG


def build(force: bool = False) -> Path:
    """Compile the production Verilator top (cached by rtlsim under build/verilator)."""
    global _built
    if force or _built is None:
        _built = rtlsim.build_top(CFG)
    return _built


def run(prog, dram=None, args=None, max_cycles: int = MAX_CYCLES) -> dict:
    """Run one program on the production RTL; return {"tmem", "dram", "cycles", "icount"}.

    prog: a list of `opentpu.isa.Instr` (S = 1: one program).
    dram: the DRAM image as uint8 (shorter than DRAM_BYTES is zero-padded; None all zero).
    args: up to 8 run arguments (R8..R15 at the start, docs/isa.md "Arguments").
    """
    img = np.zeros(CFG.DRAM_BYTES, np.uint8)
    if dram is not None:
        d = np.asarray(dram, np.uint8).reshape(-1)
        if len(d) > CFG.DRAM_BYTES:
            raise ValueError(f"DRAM image of {len(d)} bytes > DRAM_BYTES {CFG.DRAM_BYTES}")
        img[:len(d)] = d
    drams, tmems, stats = rtlsim.run(CFG, [list(prog)], [img], max_cycles=max_cycles,
                                     args=list(args or []))
    return {"tmem": np.asarray(tmems[0], np.uint32),
            "dram": np.asarray(drams[0], np.uint8)[:CFG.DRAM_BYTES],
            "cycles": stats["cycles"],
            "icount": stats["instructions"][0] if stats.get("instructions") else None}


def run_isasim(prog, dram=None, args=None) -> dict:
    """The same program and DRAM on the golden model (`opentpu.isasim.Machine`)."""
    d = None if dram is None else np.asarray(dram, np.uint8).reshape(-1)
    m = isasim.Machine(CFG, [list(prog)], [d], args=list(args or [])).run()
    s = m.slices[0]
    return {"tmem": s.tmem.copy(), "dram": s.dram.copy(), "icount": s.icount}


def _diffs(name: str, rtl: np.ndarray, isa: np.ndarray, fmt: str,
           limit: int = 8) -> tuple[int, str]:
    bad = np.nonzero(rtl.reshape(-1) != isa.reshape(-1))[0]
    lines = [f"  {name}[{int(i)}]: rtl={fmt % int(rtl.reshape(-1)[i])} "
             f"isasim={fmt % int(isa.reshape(-1)[i])}" for i in bad[:limit]]
    if len(bad) > limit:
        lines.append(f"  ... and {len(bad) - limit} more differing {name} entries")
    return len(bad), "\n".join(lines)


def compare(out: dict, golden: dict, check_icount: bool = True) -> list[str]:
    """Differences between an RTL run and an isasim run (empty: bit-identical state)."""
    problems = []
    if check_icount and out["icount"] != golden["icount"]:
        problems.append(f"icount: rtl={out['icount']} isasim={golden['icount']}")
    nt, dt = _diffs("TMEM", out["tmem"], golden["tmem"], "%08x")
    nd, dd = _diffs("DRAM", out["dram"], golden["dram"], "%02x")
    if nt:
        problems.append(f"TMEM differs in {nt} word(s):\n{dt}")
    if nd:
        problems.append(f"DRAM differs in {nd} byte(s):\n{dd}")
    return problems


def assert_matches_isasim(prog, dram=None, args=None, max_cycles: int = MAX_CYCLES,
                          check_icount: bool = True) -> dict:
    """Run on the production RTL and on isasim; assert bit-identical TMEM, DRAM and icount."""
    out = run(prog, dram=dram, args=args, max_cycles=max_cycles)
    golden = run_isasim(prog, dram=dram, args=args)
    problems = compare(out, golden, check_icount=check_icount)
    if problems:
        raise AssertionError("production RTL != isasim:\n" + "\n".join(problems))
    return out


def tmem_words(out: dict, start: int, n: int) -> list[int]:
    """The TMEM words [start, start+n) as uint32 integers."""
    return [int(x) for x in out["tmem"][start:start + n]]


def dram_words(out: dict, byte_addr: int, n: int) -> list[int]:
    """The little-endian 32-bit words [byte_addr, byte_addr+4n) as uint32 integers."""
    return [int(x) for x in np.frombuffer(
        out["dram"][byte_addr:byte_addr + 4 * n].tobytes(), dtype="<u4")]
