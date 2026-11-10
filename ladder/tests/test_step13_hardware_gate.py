"""Step 13 gate — on-card kernel over JTAG (hardware rung).

Read-only gate.  It runs the hardware probe (see ``ladder/harness/hardware.py``)
and then, when the DLC10 cable and the local acceptance artifacts are actually
present, checks the software side this step landed: the JTAG/XVC runtime tool
files and the XVC protocol evidence are byte-identical to the product commit,
the reviewed image/model identities match, the historical c0182902 acceptance
record is committed, and the documented on-card recipe is in the tree.  The
actual on-card matmul (the first host -> image -> accelerator -> result loop on
real silicon) is TODO until the step-12 image exists and the cable is attached;
it is skipped, never faked.

Behaviour without hardware (the current 2026-11-10 state):
    probe exit 3 -> every test in this file skips with
    ``hardware absent: jtag_cable_absent: ...``; nothing is written.
    The ladder runner records that as BLOCKED (exit 5), not PASS/FAIL.

No test in this file programs, flashes or resets the FPGA.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from ladder.harness.hardware import (
    ACCEPTANCE,
    PROVENANCE,
    ROOT,
    blocked_detail,
    python_with_numpy,
    run_probe,
    unexpected_detail,
)

XVC_TEST = ROOT / "tests/test_xvc_transport.py"
XVC_BENCH = ROOT / "tests/tb_xpcu_xvc.cpp"
ONCARD_DOC = ROOT / "docs/oncard-jtag.md"

# The c0182902 acceptance drivers imported at this step (stdlib-importable at
# module level; their host-tree/runtime closure is documented in
# docs/oncard-jtag.md).
EXACT_IMAGE_TOOLS = [
    "tools/run_tinystories_shared_jtag.py",
    "tools/repeat_tinystories_shared_jtag.py",
    "tools/verify_tinystories_shared_jtag.py",
    "tools/check_tinystories_c0182902_model.py",
    "tools/run_spare_c0182902_bandwidth.py",
    "tools/fedora_matmul_check.py",
]

HISTORICAL_EVIDENCE = "docs/data/c0182902-tinystories-jtag-20261107.json"


def _gate() -> dict:
    """Run the probe once per module; skip (blocked) or fail (unexpected)."""
    code, data = run_probe()
    if code == 3:
        pytest.skip(f"hardware absent: {blocked_detail(data)}")
    if code == 4:
        pytest.fail(f"hardware probe reported an unexpected state: {unexpected_detail(data)}")
    assert code == 0, f"probe exit code {code} is not part of the gate contract"
    return data


@pytest.fixture(scope="module")
def ready() -> dict:
    return _gate()


def test_step13_jtag_runtime_imports_are_byte_identical(ready):
    """The JTAG runtime tools and XVC evidence match their recorded product hashes."""
    record = json.loads(PROVENANCE.read_text())
    assert record["source_commit"] == "ca05e24f", record.get("source_commit")
    files = record["steps"]["13"]["files"]
    assert len(files) >= 10, f"only {len(files)} step-13 files recorded"
    bad = [rel for rel, digest in files.items()
           if not (ROOT / rel).is_file()
           or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest]
    assert not bad, f"{len(bad)} imported file(s) differ from ca05e24f: {bad[:10]}"


def test_step13_xvc_protocol_evidence_passes(ready):
    """The imported XVC transport test passes against its local USER2 endpoint."""
    assert XVC_BENCH.is_file(), f"missing XVC protocol bench: {XVC_BENCH}"
    assert XVC_TEST.is_file(), f"missing XVC transport test: {XVC_TEST}"
    assert (ROOT / "opentpu/host/jtag.py").is_file(), "missing JTAG/XVC transport"
    py = python_with_numpy()
    if py is None:
        pytest.skip("no local Python with numpy for the imported XVC protocol test")
    r = subprocess.run([py, "-m", "pytest", "-q", "-p", "no:cacheprovider", str(XVC_TEST)],
                       cwd=ROOT, capture_output=True, text=True, timeout=300,
                       env={**__import__("os").environ, "PYTHONPATH": str(ROOT),
                            "PYTHONDONTWRITEBYTECODE": "1"})
    assert r.returncode == 0, f"XVC transport protocol test failed:\n{r.stdout[-3000:]}" \
                              f"\n{r.stderr[-1500:]}"


def test_step13_exact_image_tools_present(ready):
    """The c0182902 acceptance drivers imported at this step are present."""
    missing = [rel for rel in EXACT_IMAGE_TOOLS if not (ROOT / rel).is_file()]
    assert not missing, f"missing acceptance tool files: {missing}"
    for rel in EXACT_IMAGE_TOOLS:
        source = (ROOT / rel).read_text()
        assert "#!" in source.splitlines()[0] or '"""' in source[:400], \
            f"{rel} does not look like the product tool"


def test_step13_image_and_model_identity(ready):
    """The image/model/token oracle this rung must reproduce is pinned and present."""
    artifacts = ready["checks"]["artifacts"]
    assert artifacts["bitstream"]["sha256"] == ACCEPTANCE["bitstream_sha256"]
    assert artifacts["model"]["sha256"] == ACCEPTANCE["model_sha256"]
    assert artifacts["model"]["sha256_match"] is True
    evidence = json.loads((ROOT / HISTORICAL_EVIDENCE).read_text())
    assert evidence["status"] == "PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS"
    assert evidence["build_id"] == ACCEPTANCE["image"]
    assert evidence["tokens"]["expected_token_ids"] == ACCEPTANCE["expected_token_ids"]
    assert evidence["tokens"]["actual_token_ids"] == ACCEPTANCE["expected_token_ids"]
    assert evidence["image_transfer"]["offline_image_sha256"] == ACCEPTANCE["image_sha256"]
    assert evidence["flash_written"] is False


def test_step13_oncard_recipe_is_documented(ready):
    """docs/oncard-jtag.md is the executable acceptance recipe for the on-card run."""
    text = ONCARD_DOC.read_text()
    for needle in ("tools/fedora_bringup.sh program", "tools/fedora_bringup.sh jtag-server",
                   "--xvc-port 3721", "run_tinystories_shared_jtag.py",
                   "repeat_tinystories_shared_jtag.py", "flash_written: false",
                   "c0182902", "once upon a time"):
        assert needle in text, f"docs/oncard-jtag.md does not document {needle!r}"


def test_step13_oncard_matmul_equals_isasim(ready):
    """TODO(step 13): upload and run a matmul on the card; compare with isasim.

    Not implemented yet: the hardware half needs the step-12 image in SRAM and
    the DLC10 cable.  When it lands it must:
      * own the cable exclusively (no openFPGALoader/hw_server/xsdb/fxload);
      * start the reviewed XVC server (``tools/fedora_bringup.sh jtag-server``)
        and use the matching image-bound calibration receipt;
      * upload the step-12 image's program/image data over USER2 JTAG, run the
        matmul, and compare every output word with ``opentpu/isasim.py``;
      * record identity/config registers, calibration snapshot, ECC counters
        and ``flash_written: false`` in ladder/evidence/step13.json.
    """
    pytest.skip("TODO(step 13): on-card matmul vs isasim waits for the step-12 image "
                "and the DLC10 cable; see docs/oncard-jtag.md")
