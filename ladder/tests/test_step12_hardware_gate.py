"""Step 12 gate — FPGA image and SRAM bring-up (hardware rung).

Read-only gate.  It runs ``ladder/hardware/probe.py`` and then, when the DLC10
cable and the local acceptance artifacts are actually present, checks the
software side this step landed: the imported YPCB Vivado flow is byte-identical
to the recorded product-tree commit, the image keeps both JTAG and PCIe runtime
interfaces, and the reviewed image/model identities on disk match.  The actual
on-card actions (Vivado build receipt, SRAM programming, on-card self-test) are
TODO until the step-12 hardware half can run; they are skipped, never faked.

Behaviour without hardware (the current 2026-11-10 state):
    probe exit 3 -> every test in this file skips with
    ``hardware absent: jtag_cable_absent: ...``; nothing is written.
    The ladder runner records that as BLOCKED (exit 5), not PASS/FAIL.

Hardware is never programmed, flashed or reset by these tests.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]            # .../<worktree root>
LADDER = HERE.parents[1]          # .../ladder
PROBE = LADDER / "hardware" / "probe.py"
HARDWARE_README = LADDER / "hardware" / "README.md"
PROVENANCE = LADDER / "hardware" / "import-provenance.json"
STEP = 12

EXPECTED_BITSTREAM_SHA256 = "3b804b81456f7c075a83e965bd012ec84865293a0ea18e1d55746c1ed79838cf"
EXPECTED_BITSTREAM_BYTES = 13_871_699
EXPECTED_PACKAGE_MANIFEST_SHA256 = "72193faf07305e45503b11331e698b9fd46a86199d4486e250975cc3fb1737be"

IMPORTED_FLOW = [
    "boards/ypcb-00338/Makefile",
    "boards/ypcb-00338/run_vivado.sh",
    "boards/ypcb-00338/vivado/build.tcl",
    "boards/ypcb-00338/vivado/bd_native.tcl",
    "boards/ypcb-00338/constraints/otpu_top_ld.xdc",
    "boards/ypcb-00338/litedram/otpu_litedram.v",
    "tools/litedram/gen_core.py",
    "tools/fedora_bringup.sh",
    "tools/fedora_prepare_xvc.py",
    "tools/fedora_xvc_server.py",
    "tools/fedora_jtag.py",
    "tools/fedora_check_jtag_chain.py",
    "tools/fedora_check_native_image.py",
    "opentpu/host/jtag.py",
    "docs/vivado_bitstream_guide.md",
]

INTERFACE_RTL = [
    "rtl/boards/ypcb-00338/otpu_fpga_top_ld.sv",
    "rtl/boards/ypcb-00338/otpu_jtag_mailbox.sv",
    "rtl/boards/ypcb-00338/otpu_jtag_axi.sv",
    "rtl/boards/ypcb-00338/otpu_pcie_mailbox.sv",
]


def _probe_or_skip() -> dict:
    """Run the read-only probe once per module; skip cleanly when blocked."""
    r = subprocess.run([sys.executable, str(PROBE), "--json"],
                       capture_output=True, text=True, timeout=30)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError:
        pytest.fail(f"hardware probe produced invalid JSON (rc={r.returncode}): "
                    f"{(r.stdout + r.stderr)[-800:]}")
    if r.returncode == 3:          # BLOCKED: outside our control; not a failure
        reasons = "; ".join(f"{b.get('reason')}: {b.get('detail')}"
                            for b in data.get("blocking_reasons", [])) or "no reason given"
        pytest.skip(f"hardware absent: {reasons}")
    if r.returncode == 4:          # UNEXPECTED: wrong/corrupt image or unsafe state
        reasons = "; ".join(f"{u.get('reason')}: {u.get('detail')}"
                            for u in data.get("unexpected", [])) or "no reason given"
        pytest.fail(f"hardware probe reported an unexpected state: {reasons}")
    assert r.returncode == 0, f"probe exit code {r.returncode} is not part of the gate contract"
    return data


@pytest.fixture(scope="module")
def ready() -> dict:
    return _probe_or_skip()


def test_step12_image_and_package_identity(ready):
    """The reviewed image/model on disk is byte-identical to the recorded identities."""
    artifacts = ready["checks"]["artifacts"]
    bit = artifacts["bitstream"]
    assert bit["exists"], f"missing bitstream: {bit['path']}"
    assert bit["sha256_match"] is True, f"bitstream sha256 mismatch: {bit['sha256']}"
    assert bit["sha256"] == EXPECTED_BITSTREAM_SHA256
    assert bit["bytes"] == EXPECTED_BITSTREAM_BYTES, bit["bytes"]
    pkg = artifacts["package_manifest"]
    assert pkg["sha256_match"] is True, f"package manifest sha256 mismatch: {pkg.get('sha256')}"
    assert pkg["sha256"] == EXPECTED_PACKAGE_MANIFEST_SHA256
    assert pkg.get("build_id") == "0xc0182902", pkg.get("build_id")


def test_step12_cable_ready_for_bringup(ready):
    """A DLC10/FT232H is attached and no other process owns the cable."""
    usb = ready["checks"]["usb"]
    assert usb["tool_available"], "lsusb is unavailable; cannot verify the cable"
    assert usb["jtag_cable_present"], usb.get("jtag_candidates")
    owners = ready["checks"]["jtag_owners"]
    assert owners["cable_holder"] is False, owners["processes"]
    assert "k10temp_c" in ready["checks"]["thermal"]  # reported; the runner gates on it


def test_step12_imported_flow_is_byte_identical(ready):
    """Every product-tree file imported by this step matches its recorded hash."""
    record = json.loads(PROVENANCE.read_text())
    assert record["source_commit"] == "ca05e24f", record.get("source_commit")
    files = record["steps"]["12"]["files"]
    assert len(files) >= 90, f"only {len(files)} imported files recorded"
    bad = [rel for rel, digest in files.items()
           if not (ROOT / rel).is_file()
           or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest]
    assert not bad, f"{len(bad)} imported file(s) differ from ca05e24f: {bad[:10]}"


def test_step12_build_flow_present(ready):
    """The YPCB Vivado flow and the documented Fedora helpers are in the tree."""
    missing = [rel for rel in IMPORTED_FLOW if not (ROOT / rel).is_file()]
    assert not missing, f"missing imported flow files: {missing}"
    makefile = (ROOT / "boards/ypcb-00338/Makefile").read_text()
    for target in ("bit:", "impl:", "program:", "program-vivado:"):
        assert target in makefile, f"board Makefile has no {target!r} target"


def test_step12_dual_interface_rule(ready):
    """The image keeps BOTH JTAG and PCIe runtime interfaces (AGENTS.md rule)."""
    rtl_missing = [rel for rel in INTERFACE_RTL if not (ROOT / rel).is_file()]
    assert not rtl_missing, f"missing interface RTL: {rtl_missing}"
    top = (ROOT / "rtl/boards/ypcb-00338/otpu_fpga_top_ld.sv").read_text()
    assert "otpu_jtag_mailbox" in top, "combined top has no JTAG USER2 mailbox"
    assert "otpu_jtag_axi" in top, "combined top has no JTAG AXI bridge"
    assert "otpu_bd_wrapper" in top, "combined top has no block design (PCIe XDMA) wrapper"
    bd = (ROOT / "boards/ypcb-00338/vivado/bd_native.tcl").read_text()
    assert "xdma" in bd.lower(), "block design has no XDMA/PCIe"
    assert "PCIE_GEN" in (ROOT / "boards/ypcb-00338/run_vivado.sh").read_text(), \
        "Vivado flow has no PCIE_GEN knob"
    # and the reviewed package metadata says both interfaces too
    pkg = ready["checks"]["artifacts"]["package_manifest"]
    assert set(pkg.get("interfaces") or []) >= {"pcie", "jtag"}, pkg.get("interfaces")


def test_step12_plan_documents_required_commands(ready):
    """The plan in ladder/hardware/README.md is the executable acceptance recipe."""
    text = HARDWARE_README.read_text()
    for needle in ("dlc10-init", "tools/fedora_bringup.sh program",
                   "tools/fedora_bringup.sh jtag-server", "flash_written: false",
                   "ladder/evidence/step12.json"):
        assert needle in text, f"ladder/hardware/README.md does not document {needle!r}"


def test_step12_build_and_sram_self_test(ready):
    """TODO(step 12): build the ladder image and observe the on-card self-test.

    Not implemented yet: the hardware half needs the DLC10 cable and the card.
    When it lands it must:
      * build the YPCB bitstream from this branch under the shared-host lock
        (Vivado 1.5-4 h) and record timing/DRC/bitstream SHA in
        ladder/evidence/step12.json;
      * program that image into volatile SRAM with
        ``tools/fedora_bringup.sh program`` (never flash);
      * run the on-card self-test / RAM test over the DLC10 XVC runtime and
        observe PASS, then release the cable;
      * keep both JTAG and PCIe runtime interfaces in the image.
    """
    pytest.skip("TODO(step 12): ladder build + SRAM programming + on-card self-test "
                "wait for the DLC10 cable and card; see docs/fpga-flow.md and "
                "ladder/hardware/README.md")
