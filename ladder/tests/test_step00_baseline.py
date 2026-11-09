"""Step 0 — the imported tiny-tpu baseline builds and its benches pass.

This is the acceptance test of the imported starting point: the ten cocotb
targets the upstream working tree reports green, the repository's lint target,
and the provenance hashes of every imported file.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

BASELINE_TARGETS = [
    "pe",
    "systolic",
    "unified_buffer",
    "loss_parent",
    "leaky_relu_parent",
    "leaky_relu_derivative_parent",
    "bias_parent",
    "vpu",
    "tpu",
    "gradient_descent",
]


@pytest.mark.parametrize("target", BASELINE_TARGETS)
def test_cocotb_target_passes(target, make_env, make_bin, repo_root):
    r = subprocess.run([make_bin, "-s", f"test_{target}"], cwd=repo_root, env=make_env,
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, (
        f"make test_{target} failed\n--- stdout tail ---\n{r.stdout[-3000:]}\n"
        f"--- stderr tail ---\n{r.stderr[-3000:]}")
    xml = repo_root / "results.xml"
    assert xml.is_file(), f"make test_{target} did not write results.xml"
    root = ET.parse(xml).getroot()
    failures = root.findall(".//failure") + root.findall(".//error")
    assert not failures, f"{len(failures)} cocotb testcases failed in results.xml"
    cases = root.findall(".//testcase")
    assert cases, "results.xml contains no testcases"


def test_make_lint(make_env, make_bin, repo_root):
    if not __import__("shutil").which("verible-verilog-lint"):
        pytest.skip("verible-verilog-lint not installed")
    r = subprocess.run([make_bin, "-s", "lint"], cwd=repo_root, env=make_env,
                       capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert "0 findings" in (r.stdout + r.stderr) or r.stdout.strip() == "", r.stdout[-1000:]


def _root_commit(repo_root: Path) -> str:
    r = subprocess.run(["git", "rev-list", "--max-parents=0", "HEAD"], cwd=repo_root,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return r.stdout.split()[0]


def test_provenance_hashes(repo_root):
    """The recorded SHA-256s are exactly the files committed by step 0, not later edits."""
    root = _root_commit(repo_root)
    prov = repo_root / "ladder/PROVENANCE.md"
    rows = re.findall(r"\| `([^`]+)` \| \d+ \| `([0-9a-f]{64})` \|", prov.read_text())
    assert len(rows) >= 40, f"only {len(rows)} provenance rows"
    bad = []
    for rel, digest in rows:
        r = subprocess.run(["git", "cat-file", "-p", f"{root}:{rel}"], cwd=repo_root,
                           capture_output=True, timeout=60)
        if r.returncode != 0:
            bad.append(f"{rel}: not in the step-0 commit")
        elif hashlib.sha256(r.stdout).hexdigest() != digest:
            bad.append(f"{rel}: hash mismatch against the step-0 commit")
    assert not bad, "\n".join(bad)


def test_step0_commit_is_the_import(repo_root):
    """The root commit is the import commit and contains the expected file counts."""
    r = subprocess.run(["git", "log", "--format=%s", "-1", _root_commit(repo_root)],
                       cwd=repo_root, capture_output=True, text=True, timeout=60)
    assert r.stdout.strip().startswith("step 0:"), r.stdout
    files = subprocess.run(["git", "ls-tree", "-r", "--name-only", _root_commit(repo_root)],
                           cwd=repo_root, capture_output=True, text=True, timeout=60).stdout.split()
    for prefix, count in (("src/", 16), ("test/", 24)):
        assert sum(1 for f in files if f.startswith(prefix)) == count, f"{prefix} count"


def test_imported_rtl_is_complete(repo_root):
    src = sorted((repo_root / "src").glob("*.sv"))
    assert len(src) == 16, [p.name for p in src]
    tests = sorted((repo_root / "test").glob("test_*.py"))
    assert len(tests) == 10, [p.name for p in tests]
    dumps = sorted((repo_root / "test").glob("dump_*.sv"))
    assert len(dumps) == 14, [p.name for p in dumps]
    readme = (repo_root / "README.md").read_text()
    assert "tiny-tpu" in readme.lower()
