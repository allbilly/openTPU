"""Exact-image guards for the merged c0182902 spare-lane successor.

The existing c0182863 transport remains bound to that image. This module
requires a separately packaged and reviewed c0182902 image; it does not grant
permission to program the card or calibrate an unreviewed bitstream.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from . import regs as R
from .spare_c0182863 import (
    SpareJtagTransport as _ReferenceSpareJtagTransport,
    digest,
    require,
)

BUILD_ID = 0xC0182902
BUILD_ID_HEX = "c0182902"
PACKAGE_STATUS = "EXPERIMENTAL_SPARE_DUAL_HOST_OFFLINE_REVIEW_PASS_EXTERNAL_DDR_TIMING_AND_PHYSICAL_PENDING"
COMPUTE = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2,
               CORE_KHZ=133333, DDR_MTS=1066)
MEMORY = dict(
    physical_user_channels=[0, 1], logical_capacity_bytes=1 << 32,
    virtual_channel_bytes=1 << 31, calibration_mask=3, ddr_mts=1066,
    ecc_channels=[1], ch0_physical_lanes=[0, 1, 2, 3, 4, 5, 8, 7],
    automatic_calibration_channels=[1], host_calibration_channels=[0],
)
CORE_FILES = (
    "otpu_litedram.v", "csr.csv", "sdram_init.py", "sdram_init_ch0.py",
    "otpu_litedram_mem.init",
)


class SpareC0182902Profile:
    """Validate a final, reviewed c0182902 package before opening USER2 JTAG."""

    def __init__(self, package):
        self.package = Path(package).expanduser().resolve()
        require(not (self.package / "runtime.json").is_file(),
                "Calibration requires the full reviewed c0182902 package")
        manifest = self.package / "manifest.json"
        self.data = m = json.loads(manifest.read_text())
        require(m.get("status") == PACKAGE_STATUS and
                m.get("build_id_register") == "0xc0182902",
                "Require a final reviewed c0182902 spare-lane package")
        require(m.get("compute") == COMPUTE and m.get("memory") == MEMORY,
                "c0182902 compute or spare-lane memory configuration differs")

        names = set()
        for item in m.get("files", []):
            name = item["name"]
            path = (self.package / name).resolve()
            require(path.is_relative_to(self.package) and name not in names,
                    "Duplicate or escaping package path")
            names.add(name)
            require(path.stat().st_size == item["bytes"] and digest(path) == item["sha256"],
                    "Packaged file changed: " + name)

        self.core = self.package / "core"
        required = {
            "otpu.bit", "core/variant-profile.json", "core/openxc7-profile.json",
            "core/otpu_litedram.v", "core/otpu_litedram.xdc",
            "core/otpu_litedram_mem.init", "core/csr.csv", "core/sdram_init.py",
            "core/sdram_init_ch0.py", "evidence/exact-image-disposition.json",
            "evidence/bitstream-payload-binding.json",
            "evidence/host-reset-abort-check.json",
            "evidence/adapter-model.json", "evidence/adapter-source.py",
            "evidence/dual-host/otpu_host_reset.sv",
            "evidence/dual-host/otpu_jtag_axi_abort.sv",
            "evidence/dual-host/tb_c0182902_dual_host_reset_abort.sv",
            "evidence/bridge-model.json",
            "evidence/controller-model.json", "calibration/bundle.json",
            "calibration/host-model-review.json", "calibration/selfcal.bin",
        }
        require(required <= names, "Incomplete c0182902 image/calibration review package")
        self.bitstream_sha256 = digest(self.package / "otpu.bit")
        self.manifest_sha256 = digest(manifest)

        profile = json.loads((self.core / "variant-profile.json").read_text())
        require(profile == json.loads((self.core / "openxc7-profile.json").read_text()),
                "Core profile copies disagree")
        require(profile.get("variant") == "spare8-pipelined-shared-ddr1066" and
                profile.get("parameters") == dict(CORE_KHZ=133333, DDR_MTS=1066) and
                profile.get("physical_databits") == [64, 72] and
                profile.get("physical_user_channels") == [0, 1] and
                profile.get("ecc_channels") == [1] and
                profile.get("automatic_calibration_channels") == [1] and
                profile.get("host_calibration_channels") == [0] and
                profile.get("ch0_physical_lanes") == MEMORY["ch0_physical_lanes"],
                "Core profile is not the c0182902 CH0 spare / CH1 ECC design")
        derivative = profile.get("source_derivative", {})
        require(derivative.get("reference_build_id") == "c0182863" and
                derivative.get("derivative_core_sha256") == digest(self.core / "otpu_litedram.v"),
                "Core DED derivative metadata does not match packaged RTL")
        for name in CORE_FILES:
            require("core/" + name in names, "Missing packaged core file: " + name)
        for item in profile["files"].values():
            require(Path(item["name"]).name == item["name"], "Invalid core profile filename")
            path = self.core / item["name"]
            require("core/" + item["name"] in names and path.stat().st_size == item["bytes"] and
                    digest(path) == item["sha256"], "Matched core differs: " + item["name"])
        require(digest(self.core / "sdram_init_ch0.py") == profile["ch0_init_sha256"],
                "CH0 calibration profile changed")

        self._check_exact_image_evidence()
        require(m.get("host") == dict(interfaces=["pcie", "jtag"], jtag_chain=2,
                jtag_max_hz=6000000, host_dma_hz=250000000),
                "Both runtime interfaces must be retained in c0182902")
        self._check_host_evidence()

    def _check_exact_image_evidence(self):
        evidence = self.package / "evidence"
        disposition = json.loads((evidence / "exact-image-disposition.json").read_text())
        payload = json.loads((evidence / "bitstream-payload-binding.json").read_text())
        require(disposition.get("status") == "TARGETED_EXACT_REPLAYED_CHECKPOINT_AUDIT_PASS_WITH_DISPOSITION" and
                disposition.get("build_id") == BUILD_ID_HEX and
                disposition.get("original_bitstream_sha256") == self.bitstream_sha256,
                "Exact-image disposition is missing or names another c0182902 bitstream")
        require(payload.get("status") == "PASS_REPLAYED_CHECKPOINT_BITSTREAM_CONFIGURATION_PAYLOAD_BOUND" and
                payload.get("build_id") == BUILD_ID_HEX and payload.get("payload_identical") is True and
                payload.get("configuration_after_sync_identical") is True,
                "Bitstream payload binding is incomplete")
        original = payload.get("original_bitstream", {})
        replayed = payload.get("replayed_bitstream", {})
        require(original.get("sha256") == self.bitstream_sha256 and
                disposition.get("configuration_payload_sha256") == original.get("payload_sha256") ==
                replayed.get("payload_sha256") and
                original.get("payload_bytes") == replayed.get("payload_bytes"),
                "Payload binding does not match the exact c0182902 review")
        bitstream = (self.package / "otpu.bit").read_bytes()
        payload_bytes = original.get("payload_bytes", 0)
        require(len(bitstream) == original.get("bytes") and 0 < payload_bytes < len(bitstream) and
                hashlib.sha256(bitstream[-payload_bytes:]).hexdigest() == original.get("payload_sha256"),
                "Packaged bitstream configuration payload differs from the reviewed payload")

        audited = disposition.get("audited_files", {})
        require(audited, "Exact-image disposition has no audited report inventory")
        report_root = evidence / "exact-review"
        for name, item in audited.items():
            path = report_root / name
            require(path.is_file() and path.stat().st_size == item.get("bytes") and
                    digest(path) == item.get("sha256"),
                    "Packaged exact-review evidence differs: " + name)

        inventory = disposition.get("cdc_inventory", {})
        require(inventory.get("rows") == 2033 and inventory.get("summary_reconciles") is True,
                "Exact-image CDC inventory is incomplete")
        cdc = (report_root / "cdc.rpt").read_text(errors="replace")
        detail = Counter((kind, severity) for kind, severity in re.findall(
            r"^\s*\d+\s+(CDC-\d+)\s+(Critical|Warning)\b", cdc, re.MULTILINE))
        summary = Counter({(kind, severity): int(count) for kind, severity, count in re.findall(
            r"^\s*(CDC-\d+)\s+(Critical|Warning)\s+(\d+)\b", cdc, re.MULTILINE) if int(count)})
        require(sum(detail.values()) == inventory["rows"] and detail == summary,
                "Packaged CDC report rows do not reconcile with its summary")

        timing = disposition.get("timing", {})
        require(timing.get("WNS_ns", -1) >= 0 and timing.get("WHS_ns", -1) >= 0 and
                timing.get("setup_failing_endpoints") == 0 and
                timing.get("hold_failing_endpoints") == 0 and
                timing.get("all_user_constraints_met") is True,
                "Exact-image timing disposition is not passing")
        require(disposition.get("interface_evidence", {}).get("jtag", {}).get("JTAG_chain") == 2 and
                disposition.get("interface_evidence", {}).get("pcie", {}).get("xdma_runtime_path") == "present" and
                disposition.get("hardware_accessed") is False and
                disposition.get("programming_performed") is False and
                disposition.get("flash_written") is False,
                "Exact-image interface or offline-review disposition differs")

    def _check_host_evidence(self):
        evidence = self.package / "evidence"
        model = json.loads((evidence / "host-reset-abort-check.json").read_text())
        require(model.get("status") == "PASS_FOCUSED_RESET_ABORT_AND_DUAL_HOST_SOURCE_CHECKS" and
                model.get("build_id") == BUILD_ID_HEX and
                model.get("hardware_accessed") is False and model.get("flash_written") is False,
                "Missing c0182902 host reset/abort check receipt")
        integrated = model.get("integrated_host_reset_abort", {})
        require(integrated.get("compile_exit") == 0 and integrated.get("run_exit") == 0,
                "c0182902 integrated reset/abort simulation did not pass")
        integrated_bench = evidence / "dual-host" / "tb_c0182902_dual_host_reset_abort.sv"
        require(integrated.get("bench_sha256") == digest(integrated_bench),
                "Integrated host reset/abort bench differs from package evidence")
        for name, field in (("otpu_host_reset.sv", "host_reset_sha256"),
                            ("otpu_jtag_axi_abort.sv", "jtag_abort_sha256")):
            target = evidence / "dual-host" / name
            require(target.is_file() and integrated.get(field) == digest(target),
                    "Packaged host RTL differs from reviewed evidence: " + name)
        for relative, status in (
            ("adapter-model.json", "PASS_SHARED_PIPELINED_NATIVE_CREDITS_ORDERING_AND_EXCLUSIVE_RMW"),
            ("bridge-model.json", "PASS_ORIGINAL_BRIDGE_DEFECT_REPRODUCED_SHARED_PIPELINE_CORRECTION_VERIFIED"),
            ("controller-model.json", "PASS_SHARED_PIPELINE_REAL_LITEDRAM_CONTROLLER_BRIDGE_REGRESSION"),
        ):
            model_path = evidence / relative
            record = json.loads(model_path.read_text())
            require(record.get("status") == status,
                    "Missing matching c0182902 integration evidence: " + relative)
            profile = json.loads((self.core / "variant-profile.json").read_text())
            shared_sources = [value for name, value in record.get("sources", {}).items()
                              if name.endswith("/spare_native_pipeline_shared.py")]
            require(shared_sources == [profile.get("adapter_source_sha256")] and
                    digest(evidence / "adapter-source.py") == profile.get("adapter_source_sha256"),
                    "Shared-pipeline model/source does not match c0182902 core: " + relative)

    def core_file_digest(self, name):
        require(Path(name).name == name, "Invalid core filename")
        return digest(self.core / name)

    def firmware_model_review(self):
        return json.loads((self.package / "calibration/host-model-review.json").read_text())

    def firmware_model_review_digest(self):
        return digest(self.package / "calibration/host-model-review.json")

    def check_image(self, transport):
        expected = {
            R.R_ID: R.ID_OTPU, R.R_VERSION: (128 << 16) | (4 << 8) | 8,
            R.R_REGMAP: 5, R.R_CORE_KHZ: 133333, R.R_BUILD_ID: BUILD_ID,
            R.R_DDR_MTS: 1066, R.R_ACT_ROWS: 4,
        }
        actual = {off: transport.reg_read(off) for off in expected}
        require(actual == expected, f"c0182902 image identity differs: {actual}")
        required = R.CAP_HOSTCAL | R.CAP_DDR | R.CAP_ACT
        require(transport.reg_read(R.R_CAPS) & required == required,
                "c0182902 runtime capabilities differ")
        return {f"{off:#x}": value for off, value in actual.items()}


class SpareC0182902JtagTransport(_ReferenceSpareJtagTransport):
    """JTAG calibration transport; requires SpareC0182902Profile, never c0182863."""
