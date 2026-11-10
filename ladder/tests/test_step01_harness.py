"""Step 1 — the ladder harness, roadmap and cleaned-up Makefile.

This step adds the reproducible runner/evidence convention and makes the
imported baseline's build surface honest: only targets whose dump bench and
cocotb module exist remain, plus one aggregate `test` target.  The tests here
check the harness itself, so later rungs can trust `ladder/run.py step NN`.
"""
from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
README = ROOT / "ladder/README.md"
RUNNER = ROOT / "ladder/run.py"
EXPECTED_TARGETS = [
    "pe", "systolic", "unified_buffer", "loss_parent", "leaky_relu_parent",
    "leaky_relu_derivative_parent", "bias_parent", "vpu", "tpu", "gradient_descent",
]


def load_runner():
    spec = importlib.util.spec_from_file_location("ladder_runner", RUNNER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_step_table():
    runner = load_runner()
    assert set(runner.STEPS) == set(range(17)), sorted(runner.STEPS)
    for n, meta in runner.STEPS.items():
        assert meta["title"], f"step {n} has no title"
        assert isinstance(meta["heavy"], bool) and isinstance(meta["hardware"], bool)
    # exactly the production/hardware rungs run under the shared-host gate
    assert {n for n, m in runner.STEPS.items() if m["heavy"]} == {9, 10, 11, 12, 13, 14, 15, 16}
    assert {n for n, m in runner.STEPS.items() if m["hardware"]} == {12, 13, 15}


def test_roadmap_lists_every_step():
    text = README.read_text()
    rows = re.findall(r"^\|\s*(\d+)\s*\|", text, re.M)
    numbers = [int(n) for n in rows]
    assert sorted(set(numbers)) == list(range(17)), f"roadmap table steps: {sorted(set(numbers))}"
    for n in range(17):
        assert re.search(rf"^### step {n} — ", text, re.M), f"roadmap has no spec for step {n}"


def test_roadmap_titles_match_runner():
    """Each `### step N — title` heading and the runner's title agree."""
    runner = load_runner()
    text = README.read_text()
    headings = dict(re.findall(r"^### step (\d+) — (.+)$", text, re.M))
    for n, meta in runner.STEPS.items():
        heading = headings.get(str(n))
        assert heading, f"no heading for step {n}"
        assert heading.strip() == meta["title"], (
            f"step {n}: roadmap heading {heading.strip()!r} != runner title {meta['title']!r}")
        # and the table's rung label links to the same step anchor
        assert re.search(rf"^\|\s*{n}\s*\|.*\[.*\]\(#step-{n}-", text, re.M), (
            f"step {n}: table row does not link to its spec")


def test_roadmap_status_icons_are_known():
    text = README.read_text()
    body = text.split("## The rungs", 1)[1].split("## Step specifications", 1)[0]
    icons = re.findall(r"\|\s*(✅|🔨|⏳|🚫)\s*\|", body)
    assert len(icons) == 17, f"{len(icons)} status cells, expected 17 (one per step)"
    assert "✅" in icons


def test_makefile_targets_are_honest():
    """Every remaining `test_*` target has its dump bench and cocotb module."""
    from conftest import makefile_test_targets

    targets = makefile_test_targets()
    assert set(targets) - {"test"} == {f"test_{t}" for t in EXPECTED_TARGETS}, sorted(targets)
    bad = []
    for target, recipe in targets.items():
        if target == "test":
            continue
        module = target[len("test_"):]
        if not (ROOT / f"ladder/toy/test/{target}.py").is_file():
            bad.append(f"{target}: missing test/{target}.py")
        for path in re.findall(r"test/(dump_[A-Za-z0-9_]+\.sv)", recipe):
            if not (ROOT / "ladder/toy/test" / path.split("test/")[-1]).is_file():
                bad.append(f"{target}: missing {path}")
        if not re.search(r"-s\s+" + re.escape(module) + r"\b", recipe):
            bad.append(f"{target}: recipe does not instantiate module {module}")
    assert not bad, "\n".join(bad)


def test_make_aggregate_target(make_env, make_bin):
    r = subprocess.run([make_bin, "-n", "test"], cwd=ROOT / "ladder/toy", env=make_env,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    for target in EXPECTED_TARGETS:
        assert f"test_{target}" in r.stdout, f"`make test` missing test_{target}"


def test_runner_doctor_json():
    r = subprocess.run([sys.executable, str(RUNNER), "doctor", "--json"],
                       cwd=ROOT, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr[-2000:]
    info = json.loads(r.stdout)
    for key in ("utc", "git", "toolchain", "steps", "evidence", "python_candidates"):
        assert key in info, f"doctor JSON missing {key}"
    assert set(info["steps"]) == {f"{n:02d}" for n in range(17)}
    assert info["toolchain"]["pytest"], "doctor found no pytest"
    assert info["toolchain"]["iverilog"], "doctor found no iverilog"
    # the runner must be honest about which step tests exist (later rungs add
    # their own tests, so compare against the files actually present on disk)
    for n in range(17):
        expected = sorted(p.name for p in (ROOT / "ladder/tests").glob(f"test_step{n:02d}_*.py"))
        assert info["steps"][f"{n:02d}"]["tests"] == expected, (
            f"step {n}: doctor lists {info['steps'][f'{n:02d}']['tests']} but disk has {expected}")


def test_evidence_receipts_validate():
    # our own receipt is written after the tests: validate the steps before this one
    r = subprocess.run([sys.executable, str(RUNNER), "evidence-check", "--before", "1"],
                       cwd=ROOT, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-3000:]
    receipt = json.loads((ROOT / "ladder/evidence/step00.json").read_text())
    assert receipt["summary"].startswith("PASS")
    assert receipt["step"] == 0
    assert receipt["tests"], "step 0 receipt has no per-test verdicts"
    assert len(receipt["tests"]) >= 10


def test_host_gate_documented():
    text = README.read_text()
    assert "/tmp/rknpu-heavy.lock" in text
    assert "k10temp" in text
    assert "DLC10" in text


def test_dev_requirements_present():
    req = (ROOT / "ladder/requirements-dev.txt").read_text()
    assert "pytest" in req
