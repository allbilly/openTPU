"""Shared fixtures for the ladder step tests.

The ladder's tests are deliberately plain: every step runs from the repository
root with `python3 ladder/run.py step NN`; no network, no device access, no
side effects outside `sim_build/`, `waveforms/`, `.pytest_cache/` and
`ladder/artifacts/`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LADDER = ROOT / "ladder"
TOY_PY_CANDIDATES = [
    os.environ.get("LADDER_TOY_PY"),
    str(ROOT / ".venv/bin/python"),
    str(LADDER / ".venv/bin/python"),
    "/home/fedora/tiny-tpu/.venv/bin/python",
]


def _first_existing(paths) -> Path | None:
    for p in paths:
        if p and Path(p).exists():
            return Path(p)
    return None


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return ROOT


@pytest.fixture(scope="session")
def toy_python() -> Path:
    """A Python that has cocotb (steps 0-2 benches). Skips with a clear reason."""
    py = _first_existing(TOY_PY_CANDIDATES)
    if py is None:
        pytest.skip("no cocotb Python found; set LADDER_TOY_PY (see ladder/run.py doctor)")
    r = subprocess.run([str(py), "-c", "import cocotb, numpy"], capture_output=True, text=True)
    if r.returncode != 0:
        pytest.skip(f"{py} cannot import cocotb/numpy: {r.stderr.strip()[-300:]}")
    return py


@pytest.fixture(scope="session")
def make_env(toy_python: Path) -> dict:
    """Environment for `make`: the cocotb Python's bin dir first on PATH."""
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(toy_python.parent), env.get("PATH", "")])
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # keep each step's build output out of the shared repo root
    env.setdefault("SIM_BUILD_DIR", "sim_build")
    return env


@pytest.fixture(scope="session")
def make_bin() -> str:
    make = shutil.which("make")
    if make is None:
        pytest.skip("make not installed")
    return make


def run_make(target: str, env: dict, *, timeout: int = 600, extra: list[str] | None = None):
    cmd = [shutil.which("make") or "make", "-s", target, *(extra or [])]
    return subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=timeout)


def read_makefile() -> str:
    return (ROOT / "Makefile").read_text()


def makefile_test_targets() -> dict[str, str]:
    """Map `test_<name>` target -> the recipe body, from the current Makefile."""
    import re

    text = read_makefile()
    targets: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        m = re.match(r"^(test_[A-Za-z0-9_]+):", line)
        if m:
            current = m.group(1)
            targets[current] = []
        elif current and (line.startswith("\t") or not line.strip() or line.startswith("#")):
            targets[current].append(line)
        else:
            current = None
    return {k: "\n".join(v) for k, v in targets.items()}
