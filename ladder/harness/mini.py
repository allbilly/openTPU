"""Ladder step 4 — the mini-core harness: build the RTL, run a program, compare with isasim.

The mini-core (rtl/ladder/mini_*.sv, sim/ladder/tb_mini.sv) implements the step-4 subset of the
openTPU ISA serially.  This module is the only Python glue the step tests (and later rungs) use:

    from ladder.harness import mini
    out = mini.run([I.li(1, 5), I.halt()])            # RTL result
    mini.assert_matches_isasim(prog)                  # bit-exact TMEM + DRAM vs isasim

The oracle is opentpu/isasim.py, imported in ladder step 3; `run_isasim` builds the matching
one-slice machine and returns its final state.  Everything is plain subprocess + numpy: no
cocotb, no network, no side effects outside ladder/artifacts/.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
RTL_DIR = ROOT / "rtl/ladder"
TB_FILE = ROOT / "sim/ladder/tb_mini.sv"
ARTIFACTS = ROOT / "ladder/artifacts/iverilog"
RUNS = ROOT / "ladder/artifacts/mini-runs"

# The step-4 configuration (spec): S=1, D=32, MCOLS=4, ACT_BLOCKS=16, ACT_ROWS=4, 4096-word
# TMEM and IMEM, 256 KiB DRAM.  The TB parameters and the isasim Config both take these.
DEFAULT_PARAMS = {
    "D": 32,
    "MCOLS": 4,
    "ACT_BLOCKS": 16,
    "ACT_ROWS": 4,
    "TMEM_WORDS": 4096,
    "IMEM_WORDS": 4096,
    "DRAM_BYTES": 262144,
}

RESULT_RE = re.compile(
    r"^RESULT cycles=(\d+) halted=(\d+) error=(\d+) code=(\d+) icount=(\d+)\s*$", re.M)

_build_cache: dict[tuple, Path] = {}


def params(**overrides) -> dict:
    """A full parameter dict with overrides, e.g. mini.params(DRAM_BYTES=16384)."""
    p = dict(DEFAULT_PARAMS)
    p.update(overrides)
    return p


def sources() -> list[Path]:
    # otpu_fp.sv (step 5) is a package: it must be compiled before the modules that import it, so
    # it goes first among the alphabetical RTL sources, which carry the rest of the design.
    rtl = sorted(RTL_DIR.glob("*.sv"))
    return [p for p in rtl if p.name == "otpu_fp.sv"] + \
           [p for p in rtl if p.name != "otpu_fp.sv"] + [TB_FILE]


def _cache_key(sources_: list[Path], flags: list[str]) -> str:
    h = hashlib.sha1()
    for p in sources_:
        h.update(p.name.encode())
        h.update(p.read_bytes())
    h.update("\0".join(flags).encode())
    return h.hexdigest()


def build(params_: dict | None = None, force: bool = False) -> Path:
    """Compile the mini-core + TB with iverilog; return the cached .vvp path.

    The cache is keyed by a SHA-1 of the sources and the iverilog flags (which carry the TB
    parameters), under ladder/artifacts/iverilog/<sha1>/sim.vvp.
    """
    p = dict(DEFAULT_PARAMS if params_ is None else params_)
    srcs = sources()
    missing = [str(s) for s in srcs if not s.exists()]
    if missing:
        raise FileNotFoundError(f"mini-core sources missing: {missing}")
    flags = [f"-Ptb_mini.{k}={v}" for k, v in p.items()]
    digest = _cache_key(srcs, flags)
    key = (digest, force)
    if not force and key in _build_cache and _build_cache[key].exists():
        return _build_cache[key]
    out_dir = ARTIFACTS / digest
    vvp = out_dir / "sim.vvp"
    if not force and vvp.exists():
        _build_cache[key] = vvp
        return vvp
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = ["iverilog", "-g2012", "-s", "tb_mini", *flags, "-o", str(vvp),
           *[str(s) for s in srcs]]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError("iverilog failed:\n" + (proc.stderr or proc.stdout)[-4000:])
    _build_cache[key] = vvp
    return vvp


def _hex_lines(values, width: int) -> str:
    return "".join(f"{int(v):0{width}x}\n" for v in values)


def _read_dump(path: Path, words: bool) -> np.ndarray:
    """Parse a one-per-line hex dump; fast path keeps numpy out of a Python loop."""
    text = path.read_text()
    buf = bytes.fromhex("".join(text.split()))
    if words:
        # 8 hex digits per line = 4 bytes in file order; the word is big-endian in file order
        return np.frombuffer(buf, dtype=">u4").astype(np.uint32).copy()
    return np.frombuffer(buf, dtype=np.uint8).copy()


def run(prog, dram=None, args=None, max_cycles: int = 200000,
        params_: dict | None = None, keep: bool = False) -> dict:
    """Run one program on the mini-core RTL; return {"tmem", "dram", "cycles", ...}.

    prog: list of opentpu.isa.Instr (assembled with isa.assemble) or a flat list of 32-bit
          instruction words (8 per instruction).
    dram: optional uint8 array; shorter than DRAM_BYTES is fine (the rest stays zero).
    args: up to 8 run arguments for R8..R15.
    """
    from opentpu import isa

    p = dict(DEFAULT_PARAMS if params_ is None else params_)
    vvp = build(p)

    if len(prog) and hasattr(prog[0], "encode"):
        words = isa.assemble(list(prog))
    else:
        words = np.asarray(prog, dtype=np.uint32).reshape(-1)
    if len(words) == 0 or len(words) % 8:
        raise ValueError(f"program image must be a multiple of 8 words, got {len(words)}")
    if len(words) > p["IMEM_WORDS"]:
        raise ValueError(f"program of {len(words)//8} instructions does not fit IMEM")
    # pad IMEM to its full size with illegal opcodes: an instruction fetched past the program
    # image then errors (code 1), like isasim's "pc past end of program".  One $readmemh of a
    # full image is much faster than a hierarchical fill loop in Icarus.
    imem = np.full(p["IMEM_WORDS"], 0xFFFF_FFFF, dtype=np.uint32)
    imem[:len(words)] = words

    args = list(args or [])
    if len(args) > 8:
        raise ValueError("at most 8 run arguments")

    RUNS.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="run-", dir=RUNS))
    try:
        prog_path = work / "prog.hex"
        prog_path.write_text(_hex_lines(imem, 8))
        # the DRAM image is also written full size (zeros outside the image): deterministic
        # power-on state without a slow hierarchical fill loop in the TB
        dmem = np.zeros(p["DRAM_BYTES"], dtype=np.uint8)
        if dram is not None:
            d = np.asarray(dram, dtype=np.uint8).reshape(-1)
            if len(d) > p["DRAM_BYTES"]:
                raise ValueError(f"DRAM image of {len(d)} bytes > DRAM_BYTES {p['DRAM_BYTES']}")
            dmem[:len(d)] = d
        dram_path = work / "dram.hex"
        dram_path.write_text(_hex_lines(dmem, 2))
        cmd = [str(vvp), f"+prog={prog_path}", f"+dram={dram_path}", f"+outdir={work}",
               f"+max_cycles={int(max_cycles)}"]
        for k, v in enumerate(args):
            cmd.append(f"+arg{k}={int(v) & 0xFFFFFFFF:08x}")
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=int(os.environ.get("MINI_SIM_TIMEOUT", "1800")))
        if proc.returncode != 0:
            raise RuntimeError(f"vvp failed ({proc.returncode}):\n"
                               f"{(proc.stderr or proc.stdout)[-4000:]}")
        m = RESULT_RE.search(proc.stdout)
        if m is None:
            raise RuntimeError("no RESULT line from tb_mini:\n"
                               + (proc.stdout[-4000:] or proc.stderr[-4000:]))
        out = {
            "cycles": int(m.group(1)),
            "halted": bool(int(m.group(2))),
            "error": bool(int(m.group(3))),
            "code": int(m.group(4)),
            "icount": int(m.group(5)),
        }
        out["tmem"] = _read_dump(work / "tmem.hex", words=True)
        out["dram"] = _read_dump(work / "dram_out.hex", words=False)
        # step 6: the ACT RAM state (quantizer output), dumped by tb_mini
        out["act"] = _read_dump(work / "act.hex", words=False)
        out["ascale"] = _read_dump(work / "ascale.hex", words=True)
        out["adoff"] = _read_dump(work / "adoff.hex", words=True)
        if len(out["act"]) != p["ACT_ROWS"] * p["ACT_BLOCKS"] * p["D"]:
            raise RuntimeError(f"tmem dump has {len(out['tmem'])} words, "
                               f"expected {p['TMEM_WORDS']}")
        if len(out["dram"]) != p["DRAM_BYTES"]:
            raise RuntimeError(f"dram dump has {len(out['dram'])} bytes, "
                               f"expected {p['DRAM_BYTES']}")
        if len(out["ascale"]) != p["ACT_ROWS"] * p["ACT_BLOCKS"]:
            raise RuntimeError(f"ascale dump has {len(out['ascale'])} words, "
                               f"expected {p['ACT_ROWS'] * p['ACT_BLOCKS']}")
        if len(out["adoff"]) != p["ACT_ROWS"] * p["ACT_BLOCKS"]:
            raise RuntimeError(f"adoff dump has {len(out['adoff'])} words")
        if keep or os.environ.get("MINI_KEEP"):
            out["workdir"] = str(work)
            work = None  # type: ignore[assignment]
        return out
    finally:
        if work is not None:
            shutil.rmtree(work, ignore_errors=True)


def isasim_config(params_: dict | None = None):
    """The isasim.Config matching the mini-core's parameters (S=1)."""
    from opentpu import isasim

    p = dict(DEFAULT_PARAMS if params_ is None else params_)
    return isasim.Config(S=1, **p)


def run_isasim(prog, dram=None, args=None, params_: dict | None = None,
               max_steps: int = 2_000_000) -> dict:
    """Run the same program on the openTPU ISA simulator (the golden model).

    Returns the final state on success, or {"error": True, "message": ...} when isasim raises
    SimError (bad address, loop error, illegal opcode, pc past the end, ...).
    """
    from opentpu import isa, isasim

    p = dict(DEFAULT_PARAMS if params_ is None else params_)
    cfg = isasim_config(p)
    if len(prog) and hasattr(prog[0], "encode"):
        prog = list(prog)
    else:
        words = np.asarray(prog, dtype=np.uint32).reshape(-1)
        prog = [isa.Instr.decode(words[8 * k: 8 * k + 8]) for k in range(len(words) // 8)]
    d = None
    if dram is not None:
        d = np.asarray(dram, dtype=np.uint8).reshape(-1)
    machine = isasim.Machine(cfg, [prog], [d], args=list(args or []))
    try:
        machine.run(max_steps=max_steps)
    except isasim.SimError as e:
        return {"error": True, "message": str(e), "halted": False, "icount": None,
                "tmem": None, "dram": None}
    s = machine.slices[0]
    # the ACT RAM state in the same flat form the RTL dump uses
    act = np.asarray(s.act, dtype=np.int8).reshape(-1).view(np.uint8).copy()
    ascale = np.asarray(s.ascale, dtype=np.float32).reshape(-1).view(np.uint32).copy()
    ad = np.asarray(s.adoff, dtype=np.uint8).reshape(-1, 4).astype(np.uint32)
    adoff = ad[:, 0] | (ad[:, 1] << 8) | (ad[:, 2] << 16) | (ad[:, 3] << 24)
    return {"error": False, "message": "", "halted": s.halted, "icount": s.icount,
            "tmem": s.tmem.copy(), "dram": s.dram.copy(),
            "act": act, "ascale": ascale, "adoff": adoff.astype(np.uint32).copy()}


def _diffs(name: str, rtl: np.ndarray, isa: np.ndarray, fmt: str, limit: int = 8) -> tuple[int, str]:
    bad = np.nonzero(rtl.reshape(-1) != isa.reshape(-1))[0]
    lines = [f"  {name}[{int(i)}]: rtl={fmt % int(rtl.reshape(-1)[i])} "
             f"isasim={fmt % int(isa.reshape(-1)[i])}" for i in bad[:limit]]
    if len(bad) > limit:
        lines.append(f"  ... and {len(bad) - limit} more differing {name} entries")
    return len(bad), "\n".join(lines)


def compare(out: dict, golden: dict, check_icount: bool = True) -> list[str]:
    """Return a list of human-readable differences between an RTL run and an isasim run."""
    problems = []
    if golden["error"]:
        if not out["error"]:
            problems.append("isasim raises SimError, the mini-core did not error")
        return problems
    if out["error"]:
        problems.append(f"the mini-core errored (code {out['code']}), isasim completed")
        return problems
    if not out["halted"]:
        problems.append(f"the mini-core did not halt (cycles={out['cycles']})")
    if check_icount and out["icount"] != golden["icount"]:
        problems.append(f"icount: rtl={out['icount']} isasim={golden['icount']}")
    nt, dt = _diffs("tmem", out["tmem"], golden["tmem"], "%08x")
    nd, dd = _diffs("dram", out["dram"], golden["dram"], "%02x")
    if nt:
        problems.append(f"TMEM differs in {nt} word(s):\n{dt}")
    if nd:
        problems.append(f"DRAM differs in {nd} byte(s):\n{dd}")
    # the quantizer's ACT RAM state (int8 bytes, fp32 Sa words, packed da offsets), when both
    # sides dumped it: the step-6/7 tests compare this against the ISA simulator's Slice state.
    for name, fmt in (("act", "%02x"), ("ascale", "%08x"), ("adoff", "%08x")):
        if name in golden and name in out and golden[name] is not None and out[name] is not None:
            n, d = _diffs(name, out[name], golden[name], fmt)
            if n:
                problems.append(f"ACT {name} differs in {n} entry(ies):\n{d}")
    return problems


def assert_matches_isasim(prog, dram=None, args=None, params_: dict | None = None,
                          max_cycles: int = 200000, check_icount: bool = True) -> dict:
    """Run on the mini-core and on isasim; assert bit-identical TMEM and whole DRAM."""
    p = dict(DEFAULT_PARAMS if params_ is None else params_)
    out = run(prog, dram=dram, args=args, max_cycles=max_cycles, params_=p)
    golden = run_isasim(prog, dram=dram, args=args, params_=p)
    problems = compare(out, golden, check_icount=check_icount)
    if problems:
        raise AssertionError("mini-core != isasim:\n" + "\n".join(problems))
    return out


def assert_errors(prog, code: int | None = None, dram=None, args=None,
                  params_: dict | None = None, max_cycles: int = 200000,
                  isasim_errors: bool = True) -> dict:
    """Run on the mini-core; assert it latched an error (and optionally the code).

    With isasim_errors (default), also assert isasim raises SimError for the same program: the
    ISA's error model is the oracle's, the mini-core only has to report *an* error and the code
    the ladder assigns it.
    """
    p = dict(DEFAULT_PARAMS if params_ is None else params_)
    out = run(prog, dram=dram, args=args, max_cycles=max_cycles, params_=p)
    if not out["error"]:
        raise AssertionError(
            f"the mini-core did not error (halted={out['halted']}, cycles={out['cycles']}, "
            f"icount={out['icount']})")
    if code is not None and out["code"] != code:
        raise AssertionError(f"mini-core error code {out['code']}, expected {code}")
    if isasim_errors:
        golden = run_isasim(prog, dram=dram, args=args, params_=p)
        if not golden["error"]:
            raise AssertionError("isasim completed but the mini-core errored")
    return out
