"""Hardware-gate helpers for the ladder's hardware rungs (steps 12, 13, 15).

The gate is the read-only probe next door (``ladder/hardware/probe.py``): it
never programs, flashes, resets or starts a cable/XVC server.  Tests call
:func:`run_probe` and then skip (exit 3, BLOCKED) or fail (exit 4, UNEXPECTED);
a READY probe (exit 0) lets the structural checks run.

The constants below pin the reviewed acceptance target the hardware rungs
reproduce (image ``c0182902`` / TinyStories-15M int8) and the exact commands
from ``ladder/hardware/README.md``.  When the ladder builds its own step-12
image, update them together with the same constants in ``probe.py`` and the
step-12/13 gate tests.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]          # worktree root
LADDER = ROOT / "ladder"
PROBE = LADDER / "hardware" / "probe.py"
HARDWARE_README = LADDER / "hardware" / "README.md"
PROVENANCE = LADDER / "hardware" / "import-provenance.json"

XVC_HOST = "127.0.0.1"
XVC_PORT = 3721

# Reviewed production-image acceptance target (the hardware rungs reproduce it).
ACCEPTANCE = {
    "image": "c0182902",
    "core_khz": 133333,
    "ddr_mts": 1066,
    "prompt": "Once upon a time",
    "prompt_token_ids": [1, 9038, 2501, 263, 931],
    "expected_token_ids": [29892, 727, 471, 263, 2217, 7826, 4257, 365],
    "image_bytes": 29_226_624,
    "image_sha256": "d32fd2844e1f5330bfa36bfd43374516fee7b141aefd731ad58eecb0e130e993",
    "bitstream_sha256": "3b804b81456f7c075a83e965bd012ec84865293a0ea18e1d55746c1ed79838cf",
    "package_manifest_sha256": "72193faf07305e45503b11331e698b9fd46a86199d4486e250975cc3fb1737be",
    "model_sha256": "9f74baf73f258f040f0994b9fb67da17eb92cf56b2214f309b5d037c82e1da8b",
}

# Exact commands documented in ladder/hardware/README.md (product-tree paths).
COMMANDS = {
    "probe": "python3 ladder/hardware/probe.py --json",
    "cable_init": "bash /home/fedora/ypcb/dlc10-init.sh",
    "program_sram": "BIT=build/vivado/otpu.bit bash tools/fedora_bringup.sh program",
    "xvc_server": "bash tools/fedora_bringup.sh jtag-server",
    "build_bitstream": "python3 ladder/run.py lock -- make -C boards/ypcb-00338 bit",
    "jtag_diagnostic": ("bash tools/fedora_bringup.sh jtag --litedram-core <generated core> "
                        "smi|memcal|selftest"),
    "calibrate": ("build/fedora-venv/bin/python -B <host-tree>/tools/calibrate_spare_c0182902.py "
                  "--package bitstreams/spare-dual-host-4gb-c0182902-exact-review "
                  "--transport jtag --xvc-host 127.0.0.1 --xvc-port 3721 --out <CALIB>"),
    "oracle": ("build/fedora-venv/bin/python -B tools/check_tinystories_c0182902_model.py "
               "--host-tree <host-tree> --package <package> --model <model> "
               "--tokenizer-path build/checks/tinystories-tokenizer-py314-20261018 --out <ORACLE>"),
    "run": ("PYTHONPATH=<host-tree>:<host-tree>/tools:$PWD/tools build/fedora-venv/bin/python -B "
            "tools/run_tinystories_shared_jtag.py --build-id c0182902 --host-tree <host-tree> "
            "--package <package> --model <model> --oracle <ORACLE>/manifest.json --out <RUN> "
            "--calibration-receipt <CALIB>/manifest.json --xvc-host 127.0.0.1 "
            "--xvc-port 3721 --execute"),
    "repeat": ("tools/repeat_tinystories_shared_jtag.py --prior-run <RUN> "
               "--calibration-receipt <CALIB>/manifest.json ..."),
    "verify": ("tools/verify_tinystories_shared_jtag.py --prefix-receipt <CANCELLED_READBACK> "
               "--run-receipt <RUN> --calibration-receipt <CALIB>/manifest.json ..."),
    "bandwidth": ("tools/run_spare_c0182902_bandwidth.py --span 67108864 --repeats 3 "
                  "--xvc-host 127.0.0.1 --xvc-port 3721 ..."),
}

# Measured on this host (2026-11-10 recon) - used for cost estimates only.
TIMING = {
    "jtag_upload_bytes_per_s_low": 1_887,      # c0182902 full write: 15,488.89 s / 29.2 MB
    "jtag_upload_bytes_per_s_high": 14_000,    # c0182863/c0182800 native path: ~2,070 s / 28.9 MB
    "jtag_readback_bytes_per_s": 1_800,        # documented c0182902 readback rate
    "oracle_seconds": 20,
    "ddr_init_chunks": 2048,
    "vivado_build_hours_low": 1.5,
    "vivado_build_hours_high": 4.0,
}


# The end-to-end LLM acceptance target for step 15: TinyStories-15M int8 on the
# reviewed c0182902 image, as recorded in docs/tinystories_jtag_c0182902.md and
# docs/data/c0182902-tinystories-jtag-20261107.json.  Steps 13 and 15 share the
# JTAG runtime; step 15 adds the model run, the exact token comparison, the warm
# repeat and the optional full readback/bandwidth checks.
LLM_ACCEPTANCE = {
    "image": ACCEPTANCE["image"],
    "model": "build/models/TinyStories-Llama-15M-tiles128-20261018-v2",
    "prompt": ACCEPTANCE["prompt"],
    "prompt_token_ids": ACCEPTANCE["prompt_token_ids"],
    "expected_token_ids": ACCEPTANCE["expected_token_ids"],
    "image_bytes": ACCEPTANCE["image_bytes"],
    "image_sha256": ACCEPTANCE["image_sha256"],
    "bitstream_sha256": ACCEPTANCE["bitstream_sha256"],
    "package_manifest_sha256": ACCEPTANCE["package_manifest_sha256"],
    "model_sha256": ACCEPTANCE["model_sha256"],
    # structural preflight that must pass on the same configured image first
    "preflight": {
        "initialization_chunks": 2048,
        "program_fetch_instructions": 1371,
        "program_fetch_words_compared": 65,
        "matmul_instructions": 5,
        "program_readbacks": 13,
    },
    # the passing run's own record
    "required": {
        "tokens_exact": True,
        "image_sha256_match": True,
        "calibration_unchanged": True,
        "ecc_clean": True,
        "flash_written": False,
    },
    # the warm repeat re-runs generation on the configured image without rewriting it
    "warm_repeat": {
        "image_bytes_written": 0,
        "image_bytes_reused": ACCEPTANCE["image_bytes"],
        "tokens_exact": True,
        "calibration_unchanged": True,
    },
    # optional extra evidence (not required for the token acceptance)
    "optional_checks": {
        "full_image_readback_sha256": ACCEPTANCE["image_sha256"],
        "native_read_bandwidth": {
            "transport": "jtag",
            "span_bytes": 67_108_864,
            "repeats": 3,
            "median_logical_read_gbs": 3.9814,
        },
    },
    "historical_evidence": "docs/data/c0182902-tinystories-jtag-20261107.json",
    "acceptance_doc": "docs/oncard-llm.md",
}


def run_probe(timeout: float = 30) -> tuple[int, dict]:
    """Run the read-only hardware probe; returns (exit_code, report)."""
    r = subprocess.run([sys.executable, str(PROBE), "--json"],
                       capture_output=True, text=True, timeout=timeout)
    try:
        data = json.loads(r.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - probe bug
        raise RuntimeError(f"hardware probe produced invalid JSON (rc={r.returncode}): "
                           f"{(r.stdout + r.stderr)[-800:]}") from exc
    return r.returncode, data


def blocked_detail(data: dict) -> str:
    """One-line reason string from a BLOCKED probe report."""
    items = data.get("blocking_reasons") or []
    return "; ".join(f"{b.get('reason')}: {b.get('detail')}" for b in items) or "no reason given"


def unexpected_detail(data: dict) -> str:
    """One-line reason string from an UNEXPECTED probe report."""
    items = data.get("unexpected") or []
    return "; ".join(f"{u.get('reason')}: {u.get('detail')}" for u in items) or "no reason given"


def python_with_numpy() -> str | None:
    """First local Python that can import numpy (for the imported XVC protocol test)."""
    candidates = [sys.executable, "/usr/bin/python3",
                  str(ROOT / ".venv/bin/python"),
                  "/home/fedora/openTPU/build/fedora-venv/bin/python",
                  "/home/fedora/tiny-tpu/.venv/bin/python"]
    for py in candidates:
        if not Path(py).exists():
            continue
        r = subprocess.run([py, "-c", "import numpy"], capture_output=True, text=True,
                           timeout=30)
        if r.returncode == 0:
            return py
    return None


def xvc_endpoint() -> str:
    return f"{XVC_HOST}:{XVC_PORT}"
