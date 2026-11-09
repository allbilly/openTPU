#!/usr/bin/env python3
"""Ladder runner: run one rung's tests and write its evidence receipt.

Usage (from the repository root):

    python3 ladder/run.py doctor
    python3 ladder/run.py step 0
    python3 ladder/run.py step 9 --heavy            # production-tier step
    python3 ladder/run.py all --from 0
    python3 ladder/run.py evidence-check
    python3 ladder/run.py lock -- <command...>      # run a heavy command gated

Each step's tests live in ladder/tests/test_stepNN_*.py.  The runner executes
them with pytest, records the environment, per-test verdicts and durations in
ladder/evidence/stepNN.json, and returns pytest's exit code.

Heavy steps (production Verilator builds and Vivado) are serialized on this
shared laptop: the runner takes an exclusive flock on $LADDER_HEAVY_LOCK
(default /tmp/rknpu-heavy.lock), waits when the sibling DSH session holds it,
and refuses to start when k10temp is above $LADDER_TEMP_LIMIT_C (default 92
degrees C).  Light steps run without the gate.
"""
from __future__ import annotations

import argparse
import fcntl
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LADDER = ROOT / "ladder"
TESTS = LADDER / "tests"
EVIDENCE = LADDER / "evidence"
HEAVY_LOCK = Path(os.environ.get("LADDER_HEAVY_LOCK", "/tmp/rknpu-heavy.lock"))
TEMP_LIMIT_C = float(os.environ.get("LADDER_TEMP_LIMIT_C", "92"))
TEMP_ABORT_C = float(os.environ.get("LADDER_TEMP_ABORT_C", "97"))
LOCK_WAIT_S = int(os.environ.get("LADDER_LOCK_WAIT_S", str(90 * 60)))

# Behavioural facts about each rung, mirrored in ladder/README.md's table.
# (heavy: needs the production/host gate; hardware: needs the DLC10 cable+card)
STEPS: dict[int, dict] = {
    0: {"title": "tiny-tpu baseline", "heavy": False, "hardware": False},
    1: {"title": "ladder harness, roadmap and Makefile cleanup", "heavy": False, "hardware": False},
    2: {"title": "baseline hardening: authoritative ISA and a real XOR scoreboard", "heavy": False, "hardware": False},
    3: {"title": "openTPU ISA contract", "heavy": False, "hardware": False},
    4: {"title": "mini-core: ISA sequencer + TMEM + LD/ST", "heavy": False, "hardware": False},
    5: {"title": "mini-core VPU (elementwise fp32)", "heavy": False, "hardware": False},
    6: {"title": "mini-core quantizer + ACT RAM", "heavy": False, "hardware": False},
    7: {"title": "mini-core MXU (int8 MM)", "heavy": False, "hardware": False},
    8: {"title": "mini-core reductions and ARGMAX", "heavy": False, "hardware": False},
    9: {"title": "production core adoption", "heavy": True, "hardware": False},
    10: {"title": "compiler, language, kernels, runtime", "heavy": True, "hardware": False},
    11: {"title": "board shell and host interface (simulation)", "heavy": True, "hardware": False},
    12: {"title": "FPGA image and SRAM bring-up (hardware)", "heavy": True, "hardware": True},
    13: {"title": "on-card kernel over JTAG (hardware)", "heavy": True, "hardware": True},
    14: {"title": "LLM layer in simulation", "heavy": True, "hardware": False},
    15: {"title": "LLM inference on the card (hardware)", "heavy": True, "hardware": True},
    16: {"title": "convergence on the production tree", "heavy": True, "hardware": False},
}


def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_or_none(path: Path) -> str | None:
    import hashlib

    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError:
        return None


def run_text(cmd: list[str], timeout: float = 20) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return (r.stdout + r.stderr).strip()


def python_candidates() -> list[Path]:
    """Pythons the runner may use for pytest, in priority order."""
    out: list[Path] = []
    env = os.environ.get("LADDER_PY")
    if env:
        out.append(Path(env))
    out += [ROOT / ".venv/bin/python", LADDER / ".venv/bin/python", Path(sys.executable)]
    seen, uniq = set(), []
    for p in out:
        try:
            key = str(p.resolve())
        except OSError:
            key = str(p)
        if key not in seen:
            seen.add(key)
            uniq.append(p)
    return uniq


def toy_python_candidates() -> list[Path]:
    """Pythons with cocotb for steps 0-2, in priority order."""
    out: list[Path] = []
    env = os.environ.get("LADDER_TOY_PY")
    if env:
        out.append(Path(env))
    out += [ROOT / ".venv/bin/python", LADDER / ".venv/bin/python",
            Path("/home/fedora/tiny-tpu/.venv/bin/python")]
    return [p for p in out if p.exists()]


def module_version(py: Path, module: str) -> str | None:
    if not py.exists():
        return None
    r = subprocess.run([str(py), "-c", f"import {module}; print(getattr({module}, '__version__', 'ok'))"],
                       capture_output=True, text=True, timeout=60)
    return r.stdout.strip() if r.returncode == 0 else None


def pick_toy_python() -> Path | None:
    """The first candidate Python that can import cocotb (the steps 0-2 benches)."""
    for py in toy_python_candidates():
        if py.exists() and module_version(py, "cocotb"):
            return py
    return None


def pick_python(need: tuple[str, ...] = ()) -> tuple[Path, dict]:
    """The first candidate that can import every module in `need`, with its versions."""
    tried = {}
    for py in python_candidates():
        vers = {m: module_version(py, m) for m in need} if need else {}
        tried[str(py)] = vers
        if all(v for v in vers.values()):
            return py, {"tried": tried}
    # fall back to the first existing candidate so doctor can explain the gap
    for py in python_candidates():
        if py.exists():
            return py, {"tried": tried}
    return Path(sys.executable), {"tried": tried}


def thermal_c() -> float | None:
    temps = []
    for hw in Path("/sys/class/hwmon").glob("hwmon*"):
        try:
            name = (hw / "name").read_text().strip()
            raw = (hw / "temp1_input").read_text().strip()
        except OSError:
            continue
        if name in {"k10temp", "zenpower", "coretemp"}:
            temps.append(int(raw) / 1000.0)
    return max(temps) if temps else None


class HeavyGate:
    """Exclusive shared-host lock + thermal gate for production/heavy steps."""

    def __init__(self, wait_s: int = LOCK_WAIT_S, lock_path: Path = HEAVY_LOCK):
        self.wait_s = wait_s
        self.path = lock_path
        self.fd = None

    def __enter__(self):
        t = thermal_c()
        if t is not None and t > TEMP_LIMIT_C:
            print(f"[ladder] host at {t:.1f} C > {TEMP_LIMIT_C:.0f} C; waiting for cool-down", flush=True)
            deadline = time.time() + self.wait_s
            while time.time() < deadline:
                time.sleep(30)
                t = thermal_c()
                if t is None or t <= TEMP_LIMIT_C:
                    break
                print(f"[ladder] host at {t:.1f} C; waiting", flush=True)
            else:
                raise SystemExit(f"[ladder] host stayed above {TEMP_LIMIT_C:.0f} C for {self.wait_s}s")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o666)
        deadline = time.time() + self.wait_s
        printed = False
        while True:
            try:
                fcntl.flock(self.fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() > deadline:
                    os.close(self.fd)
                    self.fd = None
                    raise SystemExit(f"[ladder] {self.path} stayed busy for {self.wait_s}s; not starting")
                if not printed:
                    print(f"[ladder] waiting for the shared host lock {self.path} ...", flush=True)
                    printed = True
                time.sleep(10)
        print(f"[ladder] host lock held ({self.path}); thermal={thermal_c()}", flush=True)
        return self

    def __exit__(self, *exc):
        if self.fd is not None:
            fcntl.flock(self.fd, fcntl.LOCK_UN)
            os.close(self.fd)
            self.fd = None
        return False


def toolchain() -> dict:
    py, _ = pick_python(("pytest",))
    toy_py = pick_toy_python()
    tools = {
        "python": str(py),
        "python_version": run_text([str(py), "--version"]) if py.exists() else None,
        "pytest": module_version(py, "pytest"),
        "numpy": module_version(py, "numpy"),
        "toy_python": str(toy_py) if toy_py else None,
        "cocotb": module_version(toy_py, "cocotb") if toy_py else None,
        "iverilog": run_text(["iverilog", "-V"]).split("\n")[0] if shutil.which("iverilog") else None,
        "verilator": run_text(["verilator", "--version"]) if shutil.which("verilator") else None,
        "vivado": run_text(["which", "vivado"]) if shutil.which("vivado") else None,
        "git": run_text(["git", "rev-parse", "--short", "HEAD"]),
        "thermal_c": thermal_c(),
        "heavy_lock": str(HEAVY_LOCK),
        "heavy_lock_held": heavy_lock_held(),
        "nproc": os.cpu_count(),
    }
    return tools


def heavy_lock_held() -> bool:
    if not HEAVY_LOCK.exists():
        return False
    try:
        fd = os.open(str(HEAVY_LOCK), os.O_RDWR)
    except OSError:
        return False
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    except BlockingIOError:
        return True
    finally:
        os.close(fd)


def step_tests(n: int) -> list[Path]:
    return sorted(TESTS.glob(f"test_step{n:02d}_*.py"))


def git_state() -> dict:
    return {
        "commit": run_text(["git", "rev-parse", "HEAD"]) or None,
        "short": run_text(["git", "rev-parse", "--short", "HEAD"]) or None,
        "branch": run_text(["git", "rev-parse", "--abbrev-ref", "HEAD"]) or None,
        "dirty": bool(run_text(["git", "status", "--porcelain"])),
    }


TEST_LINE = re.compile(r"^(ladder/tests/\S+?::\S+?)\s+(PASSED|FAILED|SKIPPED|ERROR)", re.M)


def parse_pytest(stdout: str) -> dict:
    verdicts = [{"test": m.group(1), "status": m.group(2)} for m in TEST_LINE.finditer(stdout)]
    passed = sum(1 for v in verdicts if v["status"] == "PASSED")
    failed = sum(1 for v in verdicts if v["status"] in {"FAILED", "ERROR"})
    skipped = sum(1 for v in verdicts if v["status"] == "SKIPPED")
    durations = {}
    for line in stdout.splitlines():
        m = re.match(r"^([\d.]+)s\s+(call|setup|teardown)\s+(ladder/tests/\S+)", line.strip())
        if m:
            durations.setdefault(m.group(3), 0.0)
            durations[m.group(3)] += float(m.group(1))
    return {"verdicts": verdicts, "passed": passed, "failed": failed, "skipped": skipped,
            "skipped_tests": [v["test"] for v in verdicts if v["status"] == "SKIPPED"],
            "durations_s": durations}


def run_step(n: int, extra: list[str], *, heavy: bool | None = None, quiet: bool = False,
             allow_skips: bool = False) -> int:
    extra_hardware_allow_skips = allow_skips or bool(os.environ.get("LADDER_ALLOW_SKIPS"))
    if n not in STEPS:
        print(f"[ladder] no such step: {n} (have 0..{max(STEPS)})", file=sys.stderr)
        return 2
    tests = step_tests(n)
    meta = STEPS[n]
    if not tests:
        print(f"[ladder] step {n} ({meta['title']}) has no tests yet: "
              f"expected ladder/tests/test_step{n:02d}_*.py", file=sys.stderr)
        return 3
    if meta["hardware"] and not os.environ.get("LADDER_ALLOW_HARDWARE"):
        print(f"[ladder] step {n} is a hardware rung; it needs the DLC10 cable+card.", file=sys.stderr)
        print("[ladder] its gate tests run with LADDER_ALLOW_HARDWARE=1 and record BLOCKED "
              "(exit 5) when the card/cable are absent; they never fake a PASS.", file=sys.stderr)
        return 4
    py, _ = pick_python(("pytest",))
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(
        [str(ROOT), str(TESTS), env.get("PYTHONPATH", "")]).strip(os.pathsep)
    env.setdefault("LADDER_PY", str(py))
    toy_py = pick_toy_python()
    if toy_py:
        env.setdefault("LADDER_TOY_PY", str(toy_py))
        env["PATH"] = os.pathsep.join([str(toy_py.parent), env.get("PATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd = [str(py), "-m", "pytest", "-v", "-p", "no:cacheprovider",
           "--durations=0", *[str(t) for t in tests], *extra]
    if not quiet:
        print(f"[ladder] step {n}: {meta['title']}")
        print(f"[ladder] {py} -m pytest {' '.join(str(t) for t in tests)}")
    started = time.time()
    gate = HeavyGate() if (meta["heavy"] if heavy is None else heavy) else None
    try:
        if gate:
            gate.__enter__()
        proc = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True,
                              timeout=int(os.environ.get("LADDER_STEP_TIMEOUT", "10800")))
        rc = proc.returncode
        stdout, stderr = proc.stdout, proc.stderr
    finally:
        if gate:
            gate.__exit__(None, None, None)
    duration = time.time() - started
    parsed = parse_pytest(stdout)
    if not quiet:
        print(stdout[-12000:])
        if rc:
            print(stderr[-4000:])
    # ---- verdict policy -------------------------------------------------------------------
    # PASS: every collected test passed.  FAIL: a failure/error, a run that collected nothing,
    # or skips in a software step (a missing cocotb/verible/... toolchain must not read as PASS;
    # --allow-skips or LADDER_ALLOW_SKIPS=1 opts out explicitly).  BLOCKED: a hardware rung whose
    # gate tests all skip because the cable/card are absent (probe exit 3); recorded, never PASS.
    allow_skips = bool(extra_hardware_allow_skips)
    if rc != 0 or parsed["failed"]:
        verdict, out_rc = "FAIL", (rc or 1)
    elif meta["hardware"] and parsed["skipped"]:
        # the on-card action (or the whole gate) skipped: blocked on the cable/card, not a PASS
        verdict, out_rc = "BLOCKED", 5
    elif parsed["passed"] == 0:
        verdict, out_rc = "FAIL (no tests passed)", 1
    elif parsed["skipped"] and not allow_skips:
        verdict, out_rc = "FAIL (unexpected skips; set --allow-skips / LADDER_ALLOW_SKIPS=1)", 1
    elif parsed["skipped"]:
        verdict, out_rc = "PASS (with skips)", 0
    else:
        verdict, out_rc = "PASS", 0
    receipt = {
        "schema": 1,
        "step": n,
        "title": meta["title"],
        "heavy": bool(meta["heavy"] if heavy is None else heavy),
        "hardware": meta["hardware"],
        "utc": utc(),
        "duration_s": round(duration, 3),
        "command": f"python3 ladder/run.py step {n}" + (" --heavy" if meta["heavy"] else ""),
        "command_argv": cmd,
        "git": git_state(),
        "toolchain": toolchain(),
        "returncode": rc,
        "tests": parsed["verdicts"],
        "passed": parsed["passed"],
        "failed": parsed["failed"],
        "skipped": parsed["skipped"],
        "skipped_tests": parsed["skipped_tests"],
        "test_durations_s": {k: round(v, 3) for k, v in parsed["durations_s"].items()},
        "summary": verdict,
        "stdout_tail": stdout[-6000:],
        "stderr_tail": stderr[-2000:],
        "notes": os.environ.get("LADDER_STEP_NOTES", ""),
    }
    if rc == 0 and not parsed["verdicts"]:
        receipt["summary"] = "FAIL (exit 0, but no test verdicts were parsed)"
        verdict, out_rc = receipt["summary"], 1
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    out = EVIDENCE / f"step{n:02d}.json"
    out.write_text(json.dumps(receipt, indent=1) + "\n")
    if not quiet:
        print(f"[ladder] step {n}: {receipt['summary']} "
              f"({parsed['passed']} passed, {parsed['failed']} failed, "
              f"{parsed['skipped']} skipped, {duration:.1f}s)"
              f" -> {out.relative_to(ROOT)}")
    return out_rc


def evidence_check(before: int | None = None) -> int:
    bad = []
    checked = 0
    for out in sorted(EVIDENCE.glob("step*.json")):
        m = re.match(r"step(\d\d)\.json$", out.name)
        if before is not None and m and int(m.group(1)) >= before:
            continue
        checked += 1
        try:
            d = json.loads(out.read_text())
        except (OSError, json.JSONDecodeError) as e:  # noqa: BLE001
            bad.append(f"{out.name}: not JSON ({e})")
            continue
        for key in ("schema", "step", "title", "utc", "command", "git", "toolchain",
                    "returncode", "tests", "summary"):
            if key not in d:
                bad.append(f"{out.name}: missing {key}")
        m = re.match(r"step(\d\d)\.json$", out.name)
        if m and int(m.group(1)) not in STEPS:
            bad.append(f"{out.name}: unknown step")
        if m and int(m.group(1)) in STEPS and d.get("title") != STEPS[int(m.group(1))]["title"]:
            bad.append(f"{out.name}: title does not match the runner's step table")
        verdict = str(d.get("summary", "")).split()[0]
        bad_verdicts = {"PASS", "BLOCKED"}
        hardware_rung = bool(d.get("hardware"))
        if verdict not in bad_verdicts:
            bad.append(f"{out.name}: recorded verdict is {d.get('summary')!r}")
        if verdict == "BLOCKED" and not hardware_rung:
            bad.append(f"{out.name}: a BLOCKED receipt must be a hardware rung")
        # schema 1 receipts written before the skip/BLOCKED policy do not carry the
        # counts; derive them from the verdict list instead of failing old receipts.
        if "tests" in d and not all(k in d for k in ("passed", "failed", "skipped")):
            verdicts = d["tests"]
            d.setdefault("passed", sum(1 for v in verdicts if v.get("status") == "PASSED"))
            d.setdefault("failed", sum(1 for v in verdicts
                                         if v.get("status") in {"FAILED", "ERROR"}))
            d.setdefault("skipped", sum(1 for v in verdicts if v.get("status") == "SKIPPED"))
    if bad:
        print("[ladder] evidence check FAILED:")
        for b in bad:
            print("  -", b)
        return 1
    print(f"[ladder] evidence check PASS ({checked} receipts)")
    return 0


def doctor(args) -> int:
    info = {
        "utc": utc(),
        "git": git_state(),
        "toolchain": toolchain(),
        "steps": {f"{n:02d}": {**meta, "tests": [t.name for t in step_tests(n)]}
                  for n, meta in STEPS.items()},
        "evidence": sorted(p.name for p in EVIDENCE.glob("step*.json")),
        "python_candidates": [str(p) for p in python_candidates()],
        "toy_python_candidates": [str(p) for p in toy_python_candidates()],
    }
    if args.json:
        print(json.dumps(info, indent=1))
    else:
        tc = info["toolchain"]
        print(f"ladder doctor - {info['utc']}")
        print(f"  git          {tc['git']} ({info['git']['branch']}, dirty={info['git']['dirty']})")
        print(f"  python       {tc['python']} ({tc['python_version']}); "
              f"pytest={tc['pytest']}, numpy={tc['numpy']}")
        print(f"  toy python   {tc['toy_python']} (cocotb={tc['cocotb']})")
        print(f"  iverilog     {tc['iverilog']}")
        print(f"  verilator    {tc['verilator']}")
        print(f"  vivado       {tc['vivado']}")
        print(f"  thermal      {tc['thermal_c']} C; heavy lock {tc['heavy_lock']} "
              f"held={tc['heavy_lock_held']}")
        done = [p.name for p in EVIDENCE.glob("step*.json")]
        print(f"  evidence     {len(done)} receipt(s): {', '.join(done) or 'none'}")
        print("  steps        " + " ".join(
            f"{n:02d}{'' if step_tests(n) else '(todo)'}" for n in sorted(STEPS)))
    if args.strict:
        tc = info["toolchain"]
        missing = [k for k in ("pytest",) if not tc[k]]
        if missing:
            print(f"[ladder] doctor: missing {missing}", file=sys.stderr)
            return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    d = sub.add_parser("doctor")
    d.add_argument("--json", action="store_true")
    d.add_argument("--strict", action="store_true")

    s = sub.add_parser("step")
    s.add_argument("n", type=int)
    s.add_argument("--heavy", action="store_true", help="force the shared-host lock/thermal gate")
    s.add_argument("--no-heavy", action="store_true", help="skip the gate (not recommended)")
    s.add_argument("--quiet", action="store_true")
    s.add_argument("--allow-skips", action="store_true",
                   help="record a software step's unexpected skips as PASS (with skips)")

    a = sub.add_parser("all")
    a.add_argument("--from", dest="start", type=int, default=0)
    a.add_argument("--to", dest="end", type=int, default=max(STEPS))
    a.add_argument("--allow-skips", action="store_true")

    e = sub.add_parser("evidence-check")
    e.add_argument("--before", type=int, default=None,
                   help="only receipts for steps < N (a step's own receipt is written after its tests)")

    lk = sub.add_parser("lock")
    lk.add_argument("command", nargs=argparse.REMAINDER)

    args = ap.parse_args(argv)
    if args.cmd == "doctor":
        return doctor(args)
    if args.cmd == "step":
        heavy = True if args.heavy else (False if args.no_heavy else None)
        return run_step(args.n, [], heavy=heavy, quiet=args.quiet, allow_skips=args.allow_skips)
    if args.cmd == "all":
        for n in range(args.start, args.end + 1):
            if not step_tests(n):
                print(f"[ladder] step {n}: no tests yet, skipping")
                continue
            rc = run_step(n, [], allow_skips=args.allow_skips)
            if rc != 0:
                return rc
        return 0
    if args.cmd == "evidence-check":
        return evidence_check(args.before)
    if args.cmd == "lock":
        cmd = args.command
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        if not cmd:
            print("[ladder] lock: no command given", file=sys.stderr)
            return 2
        with HeavyGate():
            return subprocess.run(cmd, cwd=ROOT).returncode
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
