"""Ladder step 16 — convergence: the branch tip is the product tree, byte for byte, plus ladder/.

The whole point of the ladder: from this commit on, checking out the branch gives the exact
product tree at `ca05e24f` (the parent commit that runs LLMs on the YPCB card) and every path
that exists on top of it is under `ladder/` (roadmap, evidence, tests, docs, the imported toy
TPU and mini-core educational material).

These tests are the ladder's definition of done:

* every tracked path of `ca05e24f` exists with the same blob sha (working tree vs product);
* every tracked path not in `ca05e24f` starts with `ladder/`;
* `git diff --stat ca05e24f -- . ':(exclude)ladder'` is empty;
* the relocated trees are present (`ladder/toy/{src,test,Makefile,README.md}`,
  `ladder/mini-core/{rtl,sim}`, `ladder/docs/*`, `ladder/examples/`);
* the roadmap is complete (17 rows; 0-11 ✅, 12/13/15 🚫 blocked, 14/16 ✅) with the final
  status-log entry, and the evidence receipts + hardware probe JSONs are all present;
* `python3 ladder/run.py evidence-check` passes.

The step-14 heavy receipt belongs to the Lead's step-14 amendment (this branch tip contains the
step-14 WIP commit); the receipt check therefore requires steps 0-13 and 15 (and 16 once the
runner writes it) and treats step 14 as optional here.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LADDER = ROOT / "ladder"
PRODUCT = "ca05e24f"
EXTRAS_OK = ("ladder/",)


def git(*args: str, check: bool = True) -> str:
    r = subprocess.run(["git", "-C", str(ROOT), *args], capture_output=True, text=True,
                       timeout=120)
    if check and r.returncode:
        raise AssertionError(f"git {' '.join(args)} failed: {r.stderr[-2000:]}")
    return r.stdout


def _product_paths() -> set[str]:
    return set(git("ls-tree", "-r", "--name-only", PRODUCT).split())


def _tip_paths() -> set[str]:
    """The tip's tracked paths (the index: identical to the commit once this step is committed)."""
    return set(git("ls-files").split())


# ---------------------------------------------------------------- product parity
def test_every_product_path_is_byte_identical():
    product = _product_paths()
    assert product, f"{PRODUCT} not found in this repository"
    missing, mismatched = [], []
    for path in sorted(product):
        want = git("rev-parse", f"{PRODUCT}:{path}").strip()
        try:
            got = git("hash-object", path).strip()
        except AssertionError:
            missing.append(path)
            continue
        if want != got:
            mismatched.append(path)
    assert not missing, f"{len(missing)} product paths are missing:\n" + "\n".join(missing[:40])
    assert not mismatched, (f"{len(mismatched)} product paths differ from {PRODUCT}:\n"
                            + "\n".join(mismatched[:40]))


def test_extras_are_only_under_ladder():
    product, tip = _product_paths(), _tip_paths()
    extras = sorted(tip - product)
    bad = [p for p in extras if not p.startswith(EXTRAS_OK)]
    assert not bad, f"{len(bad)} tracked path(s) outside ladder/:\n" + "\n".join(bad[:40])
    assert extras, "the branch adds nothing on top of the product tree: no ladder/ files?"


def test_git_diff_against_the_product_is_empty():
    out = git("diff", "--stat", PRODUCT, "--", ".", ":(exclude)ladder")
    assert out.strip() == "", f"diff vs {PRODUCT} outside ladder/:\n{out[-4000:]}"


# ---------------------------------------------------------------- relocation
def test_relocated_trees_are_present():
    toy = LADDER / "toy"
    assert (toy / "Makefile").is_file()
    assert len(list((toy / "src").glob("*.sv"))) == 16
    assert len(list((toy / "test").glob("test_*.py"))) == 10
    assert len(list((toy / "test").glob("dump_*.sv"))) == 14
    assert "tiny-tpu" in (toy / "README.md").read_text().lower()
    assert (toy / "verible.rules").is_file()
    mini = LADDER / "mini-core"
    assert len(list((mini / "rtl").glob("*.sv"))) == 10
    assert (mini / "sim" / "tb_mini.sv").is_file()
    for doc in ("toy-isa.md", "toy-to-isa.md", "mini-core.md", "fpga-flow.md",
                "oncard-jtag.md", "oncard-llm.md", "production-stack.md",
                "board-interface.md", "llm-sim.md"):
        assert (LADDER / "docs" / doc).is_file(), f"ladder/docs/{doc} missing"
    assert (LADDER / "examples" / "run_all.py").is_file()
    # the toy Makefile is the imported one, still with its ten honest targets
    makefile = (toy / "Makefile").read_text()
    targets = sorted(re.findall(r"^(test_[A-Za-z0-9_]+):", makefile, re.M))
    assert len(targets) == 10, targets


# ---------------------------------------------------------------- roadmap + evidence
def _roadmap_rows() -> dict[int, tuple[str, str]]:
    text = (LADDER / "README.md").read_text()
    rows = {}
    for m in re.finditer(r"^\|\s*(\d+)\s*\|.*?\|\s*(✅|🔨|⏳|🚫)\s*\|\s*$", text, re.M):
        rows[int(m.group(1))] = m.group(2)
    return rows


def test_roadmap_is_complete_and_honest():
    rows = _roadmap_rows()
    assert sorted(rows) == list(range(17)), sorted(rows)
    for n in range(12):
        assert rows[n] == "✅", f"step {n} is {rows[n]}, expected ✅"
    assert rows[14] == "✅"          # step-14 WIP receipt is the Lead's amendment
    assert rows[16] == "✅"
    for n in (12, 13, 15):
        assert rows[n] == "🚫", f"hardware rung {n} must stay 🚫 (blocked), got {rows[n]}"
    # the hardware rungs' probe receipts are committed
    for n in (12, 13, 15):
        probe = LADDER / "evidence" / "hardware" / f"probe-step{n}.json"
        assert probe.is_file(), f"{probe.relative_to(ROOT)} missing"
        data = json.loads(probe.read_text())
        assert data.get("schema") is not None, f"{probe.name} is not a probe receipt"
    # and the final status-log entry exists
    text = (LADDER / "README.md").read_text()
    assert re.search(r"^- 2026-11-10: step 16 ", text, re.M), "no step-16 status-log entry"


def test_evidence_receipts_are_present_and_honest():
    expect = {}
    for n in list(range(14)) + [15]:
        expect[n] = "BLOCKED" if n in (12, 13, 15) else "PASS"
    for n, verdict in expect.items():
        p = LADDER / "evidence" / f"step{n:02d}.json"
        assert p.is_file(), f"missing {p.relative_to(ROOT)}"
        d = json.loads(p.read_text())
        assert d["step"] == n and d["title"], p.name
        assert str(d["summary"]).startswith(verdict), (
            f"{p.name}: summary {d['summary']!r} does not start with {verdict}")
    # step 14 is the Lead's step-14 amendment: optional here
    step14 = LADDER / "evidence" / "step14.json"
    if step14.is_file():
        assert str(json.loads(step14.read_text())["summary"]).startswith("PASS")
    r = subprocess.run([sys.executable, str(LADDER / "run.py"), "evidence-check"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    assert "evidence check PASS" in r.stdout, r.stdout[-1000:]
