#!/usr/bin/env python3
"""Read-only hardware readiness probe for ladder steps 12/13/15.

This script only *observes* the host: it runs `lsusb`/`lspci`, reads `/proc`,
`/sys/class/hwmon`, `/dev` and the known local artifacts, and hashes files.
It never programs/flashes/resets the FPGA, never starts a cable or XVC server,
and never writes anything.

Exit codes (the hardware gate contract):
    0  READY          - JTAG cable present, no conflicting owner, the known
                        acceptance artifacts are present with matching hashes.
    3  BLOCKED        - a precondition outside our control is missing:
                        no DLC10/FT232H cable, missing local artifact, or a
                        busy JTAG owner.  Not a failure: the ladder records
                        BLOCKED (see ladder/hardware/README.md, README.txt).
    4  UNEXPECTED     - an inconsistent/unsafe state: artifact hash mismatch
                        (wrong or corrupt image), a required probe tool is
                        missing, or the probe itself failed.

Usage:
    python3 ladder/hardware/probe.py            # human summary
    python3 ladder/hardware/probe.py --json     # machine-readable report
    python3 ladder/hardware/probe.py --repo /home/fedora/openTPU
    python3 ladder/hardware/probe.py --no-hash  # skip 160 MiB of sha256 (dev)

The JSON report is the gate input for
ladder/tests/test_step12_hardware_gate.py, test_step13_hardware_gate.py and
test_step15_hardware_gate.py; see ladder/hardware/README.md.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SCHEMA = 1
XVC_PORT = 3721

# USB IDs of the two cables this board is used with (docs/board.md):
#   Xilinx Platform Cable USB II (DLC10)  03fd:0013 / 03fd:0008
#   FTDI FT232H (Digilent HS2 style)     0403:6014
JTAG_USB_IDS = {"03fd:0013", "03fd:0008", "0403:6014"}
XILINX_PCI_VENDOR = "10ee"

# Processes that own the JTAG cable: /home/fedora/ypcb/dlc10-init.sh and
# tools/fedora_xvc_server.py refuse to start while any of these exists.
CABLE_OWNER_NAMES = {
    "openFPGALoader", "openfpgaloader",
    "hw_server", "xsdb", "fxload",
}
# Heavy tools that may contend for the shared host / cable but do not by
# themselves own the DLC10 (a sibling project can legitimately run Vivado; the
# ladder runner serializes on /tmp/rknpu-heavy.lock instead).
HEAVY_PROCESS_NAMES = {"vivado", "vivado_lab"}

# The exact reviewed acceptance image + model (recon 2026-11-10).  These are
# local, untracked artifacts of the product tree; hashes are the identity
# guards documented in docs/tinystories_jtag_c0182902.md.
EXPECTED = {
    "bitstream": {
        "path": "bitstreams/spare-dual-host-4gb-c0182902-exact-review/otpu.bit",
        "bytes": 13_871_699,
        "sha256": "3b804b81456f7c075a83e965bd012ec84865293a0ea18e1d55746c1ed79838cf",
    },
    "package_manifest": {
        "path": "bitstreams/spare-dual-host-4gb-c0182902-exact-review/manifest.json",
        "sha256": "72193faf07305e45503b11331e698b9fd46a86199d4486e250975cc3fb1737be",
    },
    "model": {
        "path": "build/models/TinyStories-Llama-15M-tiles128-20261018-v2/model.safetensors",
        "bytes": 147_875_464,
        "sha256": "9f74baf73f258f040f0994b9fb67da17eb92cf56b2214f309b5d037c82e1da8b",
    },
    "evidence_json": {
        "path": "docs/data/c0182902-tinystories-jtag-20261107.json",
        "sha256": None,  # tracked doc; identity is the embedded status, not a pinned hash
    },
    "evidence_md": {"path": "docs/tinystories_jtag_c0182902.md", "sha256": None},
}

# The acceptance oracle for step 15, from docs/data/c0182902-tinystories-jtag-20261107.json.
ACCEPTANCE = {
    "steps": [12, 13, 15],
    "image": "c0182902",
    "core_khz": 133333,
    "ddr_mts": 1066,
    "prompt": "Once upon a time",
    "prompt_token_ids": [1, 9038, 2501, 263, 931],
    "expected_token_ids": [29892, 727, 471, 263, 2217, 7826, 4257, 365],
    "expected_image_sha256": "d32fd2844e1f5330bfa36bfd43374516fee7b141aefd731ad58eecb0e130e993",
    "expected_bitstream_sha256": EXPECTED["bitstream"]["sha256"],
    "expected_image_bytes": 29_226_624,
    "xvc_port": XVC_PORT,
    "thermal_limit_c": 92.0,
    "heavy_lock": "/tmp/rknpu-heavy.lock",
}

PRODUCT_ROOT_FALLBACK = Path("/home/fedora/openTPU")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_text(cmd: list[str], timeout: float = 5.0) -> tuple[bool, str]:
    """Run a read-only command; never raises.  Returns (tool_available, text)."""
    exe = shutil.which(cmd[0])
    if not exe:
        return False, ""
    try:
        r = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return True, ""
    return True, (r.stdout + r.stderr).strip()


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(chunk), b""):
            h.update(block)
    return h.hexdigest()


def find_product_root(explicit: str | None) -> tuple[Path, str]:
    """Locate the openTPU product tree that holds bitstreams/, build/, docs/.

    The ladder worktree itself does not contain those untracked artifacts, so
    the probe accepts an explicit --repo, LADDER_PRODUCT_ROOT, the tree the
    probe file lives in (parents[2]), then the known product checkout.
    """
    env = os.environ.get("LADDER_PRODUCT_ROOT")
    here = Path(__file__).resolve()
    candidates: list[tuple[Path, str]] = []
    if explicit:
        candidates.append((Path(explicit).expanduser(), "--repo"))
    if env:
        candidates.append((Path(env).expanduser(), "LADDER_PRODUCT_ROOT"))
    if len(here.parents) >= 3:
        candidates.append((here.parents[2], "probe-file"))
    candidates.append((PRODUCT_ROOT_FALLBACK, "fallback"))
    for path, source in candidates:
        try:
            if (path / "bitstreams").is_dir() or (path / "docs" / "tinystories_jtag_c0182902.md").is_file():
                return path.resolve(), source
        except OSError:
            continue
    # nothing matched: report the first candidate so the JSON says what was tried
    first = candidates[0][0] if candidates else PRODUCT_ROOT_FALLBACK
    return first, "missing"


# --------------------------------------------------------------------------- #
# individual checks (all read-only)
# --------------------------------------------------------------------------- #
def check_usb() -> dict:
    available, text = run_text(["lsusb"])
    devices = []
    for line in text.splitlines():
        m = re.search(r"ID\s+([0-9a-fA-F]{4}):([0-9a-fA-F]{4})\s*(.*)$", line)
        if not m:
            continue
        usb_id = f"{m.group(1).lower()}:{m.group(2).lower()}"
        devices.append({"id": usb_id, "description": m.group(3).strip(),
                        "line": line.strip()})
    candidates = [d for d in devices
                  if d["id"] in JTAG_USB_IDS or "Platform Cable" in d["description"]]
    return {
        "tool_available": available,
        "device_count": len(devices),
        "devices": devices,
        "jtag_cable_present": bool(candidates),
        "jtag_candidates": candidates,
        "expects": sorted(JTAG_USB_IDS),
    }


def check_pcie() -> dict:
    available, text = run_text(["lspci", "-nn"])
    if not available:
        available, text = run_text(["lspci"])
    devices = [line.strip() for line in text.splitlines()]
    xilinx = [d for d in devices if XILINX_PCI_VENDOR in d.lower()
              or "xilinx" in d.lower()]
    return {
        "tool_available": available,
        "xilinx_devices": xilinx,
        "note": ("PCIe is not required for the JTAG-only ladder path (steps 12/13/15 "
                 "run over DLC10; docs/bitstreams.md). Informational only."),
    }


def check_dev_nodes() -> dict:
    nodes = sorted(str(p) for p in Path("/dev").glob("xdma*"))
    return {
        "xdma": nodes,
        "note": ("/dev/xdma* exists only when a PCIe-hosted image enumerates; "
                 "JTAG-only bring-up does not need it."),
    }


def check_jtag_owners() -> dict:
    procs = []
    for entry in Path("/proc").iterdir():
        if not entry.name.isdigit():
            continue
        try:
            comm = (entry / "comm").read_text().strip()
            raw = (entry / "cmdline").read_bytes()
        except OSError:
            continue
        argv = [a.decode("utf-8", "replace") for a in raw.split(b"\0") if a]
        bases = {comm, Path(argv[0]).name} if argv else {comm}
        hit_cable = bases & CABLE_OWNER_NAMES
        hit_heavy = bases & HEAVY_PROCESS_NAMES
        if hit_cable or hit_heavy:
            role = "cable-owner" if hit_cable else "heavy"
            name = sorted(hit_cable or hit_heavy)[0]
            procs.append({"pid": int(entry.name), "name": name, "comm": comm,
                          "role": role, "argv": argv[:8]})
    cable = [p for p in procs if p["role"] == "cable-owner"]
    heavy = [p for p in procs if p["role"] == "heavy"]
    return {
        "busy": bool(procs),
        "cable_holder": bool(cable),
        "heavy_running": bool(heavy),
        "processes": procs,
        "checked": sorted(CABLE_OWNER_NAMES | HEAVY_PROCESS_NAMES),
    }


def check_xvc(port: int = XVC_PORT) -> dict:
    """LISTEN sockets on the XVC port, parsed from /proc/net/tcp{,6}."""
    listeners = []
    for name in ("tcp", "tcp6"):
        path = Path("/proc/net") / name
        try:
            lines = path.read_text().splitlines()
        except OSError:
            continue
        for line in lines[1:]:
            fields = line.split()
            if len(fields) < 4 or fields[3] != "0A":
                continue
            try:
                hex_ip, hex_port = fields[1].split(":")
                if int(hex_port, 16) != port:
                    continue
            except ValueError:
                continue
            listeners.append({"family": name, "local_address": fields[1]})
    return {
        "port": port,
        "listening": bool(listeners),
        "listeners": listeners,
        "note": ("An already-listening XVC server is not an error, but its owner "
                 "must be the reviewed tools/fedora_xvc_server.py before a run."),
    }


def check_thermal() -> dict:
    sensors = []
    for hw in sorted(Path("/sys/class/hwmon").glob("hwmon*")):
        try:
            name = (hw / "name").read_text().strip()
            raw = (hw / "temp1_input").read_text().strip()
        except OSError:
            continue
        if name not in {"k10temp", "zenpower", "coretemp"}:
            continue
        sensors.append({"name": name, "temp_c": round(int(raw) / 1000.0, 2)})
    peak = max((s["temp_c"] for s in sensors), default=None)
    limit = ACCEPTANCE["thermal_limit_c"]
    return {
        "sensors": sensors,
        "k10temp_c": peak,
        "limit_c": limit,
        "ok": None if peak is None else peak <= limit,
    }


def check_heavy_lock(path: str = ACCEPTANCE["heavy_lock"]) -> dict:
    import fcntl

    p = Path(path)
    if not p.exists():
        return {"path": path, "exists": False, "held": False}
    try:
        fd = os.open(str(p), os.O_RDWR)
    except OSError as exc:
        return {"path": path, "exists": True, "held": None, "error": repr(exc)}
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(fd, fcntl.LOCK_UN)
            held = False
        except BlockingIOError:
            held = True
    finally:
        os.close(fd)
    return {"path": path, "exists": True, "held": held}


def check_artifact(root: Path, spec: dict, want_hash: bool = True) -> dict:
    path = root / spec["path"]
    out = {
        "path": str(path),
        "exists": False,
        "bytes": None,
        "bytes_expected": spec.get("bytes"),
        "sha256": None,
        "sha256_expected": spec.get("sha256"),
        "sha256_match": None,
    }
    try:
        out["exists"] = path.is_file()
        if not out["exists"]:
            return out
        out["bytes"] = path.stat().st_size
        if want_hash:
            out["sha256"] = sha256_file(path)
            if spec.get("sha256") is not None:
                out["sha256_match"] = out["sha256"] == spec["sha256"]
        elif spec.get("sha256") is not None:
            out["sha256_match"] = None  # not verified in --no-hash mode
    except OSError as exc:
        out["error"] = repr(exc)
    return out


def check_artifacts(root: Path, want_hash: bool = True) -> dict:
    report: dict = {"product_root": str(root), "missing": [], "mismatched": []}
    for name in ("bitstream", "package_manifest", "model", "evidence_json", "evidence_md"):
        spec = EXPECTED[name]
        item = check_artifact(root, spec, want_hash=want_hash or name != "model")
        report[name] = item
        if not item["exists"]:
            report["missing"].append(spec["path"])
        elif item.get("sha256_match") is False:
            report["mismatched"].append(spec["path"])

    # Parse the small metadata files we already hashed (or would have).
    pkg = report["package_manifest"]
    if pkg["exists"]:
        try:
            data = json.loads(Path(pkg["path"]).read_text())
            pkg["build_id"] = data.get("build_id_register") or data.get("build_id")
            pkg["interfaces"] = data.get("host", {}).get("interfaces") or data.get("interfaces")
            pkg["status"] = data.get("status")
        except (OSError, ValueError) as exc:
            pkg["parse_error"] = repr(exc)

    ev = report["evidence_json"]
    if ev["exists"]:
        try:
            data = json.loads(Path(ev["path"]).read_text())
            ev["status"] = data.get("status")
            ev["build_id"] = data.get("build_id")
            ev["expected_token_ids"] = data.get("tokens", {}).get("expected_token_ids")
            ev["actual_token_ids"] = data.get("tokens", {}).get("actual_token_ids")
            ev["exact_match"] = data.get("tokens", {}).get("exact_match")
            ev["image_sha256"] = data.get("image_transfer", {}).get("offline_image_sha256")
            ev["flash_written"] = data.get("flash_written")
            ev["programming_performed"] = data.get("programming_performed")
        except (OSError, ValueError) as exc:
            ev["parse_error"] = repr(exc)

    model_dir = root / EXPECTED["model"]["path"].rsplit("/", 1)[0]
    report["model_dir"] = {
        "path": str(model_dir),
        "exists": model_dir.is_dir(),
        "files": sorted(p.name for p in model_dir.glob("*")) if model_dir.is_dir() else [],
    }
    return report


# --------------------------------------------------------------------------- #
# classification
# --------------------------------------------------------------------------- #
def classify(checks: dict) -> tuple[str, int, list, list]:
    blocked: list[dict] = []
    unexpected: list[dict] = []

    usb = checks["usb"]
    if not usb["tool_available"]:
        unexpected.append({"reason": "lsusb_unavailable",
                           "detail": "cannot determine whether the DLC10/FT232H cable is attached"})
    elif not usb["jtag_cable_present"]:
        blocked.append({"reason": "jtag_cable_absent",
                        "detail": "no 03fd:* DLC10 / 0403:6014 FT232H device in lsusb"})

    artifacts = checks["artifacts"]
    for path in artifacts.get("missing", []):
        blocked.append({"reason": "artifact_missing", "detail": path})
    for path in artifacts.get("mismatched", []):
        unexpected.append({"reason": "artifact_hash_mismatch", "detail": path})

    owners = checks["jtag_owners"]
    if owners["cable_holder"]:
        who = ", ".join(f"{p['name']}(pid {p['pid']})" for p in owners["processes"]
                        if p["role"] == "cable-owner")
        blocked.append({"reason": "jtag_owner_busy",
                        "detail": f"release the cable before running: {who}"})

    status = "unexpected" if unexpected else ("blocked" if blocked else "ready")
    code = {"ready": 0, "blocked": 3, "unexpected": 4}[status]
    warnings: list[dict] = []
    if owners["heavy_running"]:
        who = ", ".join(f"{p['name']}(pid {p['pid']})" for p in owners["processes"]
                        if p["role"] == "heavy")
        warnings.append({"reason": "heavy_tool_running",
                         "detail": f"{who} is running; heavy steps serialize on the host lock"})
    thermal = checks["thermal"]
    if thermal.get("ok") is False:
        warnings.append({"reason": "thermal_above_limit",
                         "detail": f"k10temp {thermal.get('k10temp_c')} C > "
                                   f"{thermal.get('limit_c')} C; the runner waits for cool-down"})
    lock = checks["heavy_lock"]
    if lock.get("held"):
        warnings.append({"reason": "heavy_lock_held",
                         "detail": f"{lock.get('path')} is held; the runner waits up to 90 min"})
    xvc = checks["xvc"]
    if xvc.get("listening"):
        warnings.append({"reason": "xvc_already_listening",
                         "detail": f"port {xvc.get('port')} has a listener; confirm its owner "
                                   f"is the reviewed XVC server before programming"})
    return status, code, blocked, unexpected, warnings


def build_report(args) -> dict:
    root, root_source = find_product_root(args.repo)
    checks = {
        "usb": check_usb(),
        "pcie": check_pcie(),
        "dev_nodes": check_dev_nodes(),
        "jtag_owners": check_jtag_owners(),
        "xvc": check_xvc(args.port),
        "thermal": check_thermal(),
        "heavy_lock": check_heavy_lock(),
        "artifacts": check_artifacts(root, want_hash=not args.no_hash),
    }
    status, code, blocked, unexpected, warnings = classify(checks)
    summary = []
    for item in blocked:
        summary.append(f"BLOCKED: {item['reason']}: {item['detail']}")
    for item in unexpected:
        summary.append(f"UNEXPECTED: {item['reason']}: {item['detail']}")
    for item in warnings:
        summary.append(f"WARNING: {item['reason']}: {item['detail']}")
    if status == "ready":
        summary.append("READY: JTAG cable present, artifacts verified, no busy owner; "
                       "proceed with the step-12/13/15 commands in ladder/hardware/README.md")
    return {
        "schema": SCHEMA,
        "utc": utc(),
        "host": os.uname().nodename if hasattr(os, "uname") else "unknown",
        "probe": "ladder/hardware/probe.py",
        "product_root": str(root),
        "product_root_source": root_source,
        "status": status,
        "exit_code": code,
        "blocking_reasons": blocked,
        "unexpected": unexpected,
        "warnings": warnings,
        "summary": summary,
        "checks": checks,
        "acceptance": ACCEPTANCE,
        "read_only": True,
        "duration_s": None,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="Read-only gate probe for ladder hardware steps 12/13/15.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--json", action="store_true", help="print the JSON report only")
    ap.add_argument("--repo", default=None,
                    help="openTPU product tree (default: infer, then /home/fedora/openTPU)")
    ap.add_argument("--port", type=int, default=XVC_PORT, help="XVC port (default 3721)")
    ap.add_argument("--no-hash", action="store_true",
                    help="skip hashing the 147 MiB model (dev only; not a gate decision)")
    args = ap.parse_args(argv)

    started = time.monotonic()
    try:
        report = build_report(args)
    except Exception as exc:  # noqa: BLE001 - probe must never crash on a read
        report = {
            "schema": SCHEMA, "utc": utc(), "host": "unknown",
            "probe": "ladder/hardware/probe.py", "status": "unexpected",
            "exit_code": 4,
            "blocking_reasons": [],
            "unexpected": [{"reason": "probe_exception", "detail": repr(exc)}],
            "warnings": [],
            "summary": [f"UNEXPECTED: probe_exception: {exc!r}"],
            "checks": {}, "acceptance": ACCEPTANCE, "read_only": True,
        }
    report["duration_s"] = round(time.monotonic() - started, 3)

    if args.json:
        print(json.dumps(report, indent=1))
    else:
        print(f"ladder hardware probe - {report['utc']}")
        print(f"  product root  {report['product_root']} ({report['product_root_source']})")
        c = report["checks"]
        usb = c.get("usb", {})
        print(f"  usb           jtag_cable={usb.get('jtag_cable_present')} "
              f"devices={usb.get('device_count')} "
              f"{[d['id'] for d in usb.get('jtag_candidates', [])]}")
        pcie = c.get("pcie", {})
        print(f"  pcie          xilinx={pcie.get('xilinx_devices')}")
        print(f"  /dev/xdma*    {c.get('dev_nodes', {}).get('xdma')}")
        owners = c.get("jtag_owners", {})
        print(f"  jtag owners   cable_holder={owners.get('cable_holder')} "
              f"heavy={owners.get('heavy_running')} "
              f"{[p['name'] for p in owners.get('processes', [])]}")
        xvc = c.get("xvc", {})
        print(f"  xvc :{xvc.get('port')}   listening={xvc.get('listening')}")
        th = c.get("thermal", {})
        print(f"  k10temp       {th.get('k10temp_c')} C (limit {th.get('limit_c')})")
        lock = c.get("heavy_lock", {})
        print(f"  heavy lock    exists={lock.get('exists')} held={lock.get('held')}")
        a = c.get("artifacts", {})
        for name in ("bitstream", "package_manifest", "model"):
            it = a.get(name, {})
            print(f"  {name:<14}{'ok' if it.get('sha256_match') else 'CHECK':>6}  {it.get('path')}")
        print("  " + ("; ".join(report["summary"]) or "no findings"))
        print(f"  status        {report['status'].upper()} (exit {report['exit_code']})")
    return report["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
