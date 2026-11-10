"""Step 15 gate — LLM inference on the card over JTAG (hardware rung).

Read-only gate.  Step 15 re-proves on the card the acceptance the production
branch recorded for image `c0182902`: TinyStories-15M int8, prompt
"Once upon a time" -> 8 exact greedy tokens
[29892, 727, 471, 263, 2217, 7826, 4257, 365], full 29,226,624-byte image
SHA-256 match (`d32fd284…`), calibration unchanged, warm repeat without
rewriting the image, `flash_written: false`.

It runs the shared hardware probe first (see `ladder/harness/hardware.py`):

    probe exit 3 (BLOCKED) -> pytest.skip("hardware absent: ...")   [current state]
    probe exit 4           -> pytest.fail(...)   (wrong/corrupt image, unsafe)
    probe exit 0 (READY)   -> the structural identity/evidence checks below
                              run; the live model run, warm repeat and optional
                              full-readback/bandwidth checks are TODO until the
                              cable and the card are attached.

No test in this file programs, flashes or resets the FPGA.  The historical
c0182902 PASS is cited as prior evidence; a skip never re-creates it.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ladder.harness.hardware import (
    LLM_ACCEPTANCE,
    PROVENANCE,
    ROOT,
    blocked_detail,
    run_probe,
    unexpected_detail,
)

ONCARD_DOC = ROOT / "ladder/docs/oncard-llm.md"
HISTORICAL = ROOT / LLM_ACCEPTANCE["historical_evidence"]

PROMPT = "Once upon a time"
PROMPT_TOKEN_IDS = [1, 9038, 2501, 263, 931]
EXPECTED_TOKEN_IDS = [29892, 727, 471, 263, 2217, 7826, 4257, 365]
EXPECTED_IMAGE_SHA256 = "d32fd2844e1f5330bfa36bfd43374516fee7b141aefd731ad58eecb0e130e993"
EXPECTED_BITSTREAM_SHA256 = "3b804b81456f7c075a83e965bd012ec84865293a0ea18e1d55746c1ed79838cf"
EXPECTED_PACKAGE_MANIFEST_SHA256 = "72193faf07305e45503b11331e698b9fd46a86199d4486e250975cc3fb1737be"
EXPECTED_MODEL_SHA256 = "9f74baf73f258f040f0994b9fb67da17eb92cf56b2214f309b5d037c82e1da8b"
EXPECTED_IMAGE_BYTES = 29_226_624


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


def test_step15_provenance_byte_identical(ready):
    """The remaining LLM-acceptance tools imported by this step match their hashes."""
    record = json.loads(PROVENANCE.read_text())
    assert record["source_commit"] == "ca05e24f", record.get("source_commit")
    files = record["steps"]["15"]["files"]
    assert len(files) >= 2, f"only {len(files)} step-15 files recorded"
    bad = [rel for rel, digest in files.items()
           if not (ROOT / rel).is_file()
           or hashlib.sha256((ROOT / rel).read_bytes()).hexdigest() != digest]
    assert not bad, f"{len(bad)} imported file(s) differ from ca05e24f: {bad[:10]}"


def test_step15_acceptance_constants_are_pinned(ready):
    """The gate constants match the recorded acceptance record exactly."""
    assert LLM_ACCEPTANCE["image"] == "c0182902"
    assert LLM_ACCEPTANCE["prompt"] == PROMPT
    assert LLM_ACCEPTANCE["prompt_token_ids"] == PROMPT_TOKEN_IDS
    assert LLM_ACCEPTANCE["expected_token_ids"] == EXPECTED_TOKEN_IDS
    assert LLM_ACCEPTANCE["image_bytes"] == EXPECTED_IMAGE_BYTES
    assert LLM_ACCEPTANCE["image_sha256"] == EXPECTED_IMAGE_SHA256
    assert LLM_ACCEPTANCE["bitstream_sha256"] == EXPECTED_BITSTREAM_SHA256
    assert LLM_ACCEPTANCE["package_manifest_sha256"] == EXPECTED_PACKAGE_MANIFEST_SHA256
    assert LLM_ACCEPTANCE["model_sha256"] == EXPECTED_MODEL_SHA256
    assert LLM_ACCEPTANCE["preflight"] == {
        "initialization_chunks": 2048, "program_fetch_instructions": 1371,
        "program_fetch_words_compared": 65, "matmul_instructions": 5,
        "program_readbacks": 13,
    }
    assert LLM_ACCEPTANCE["warm_repeat"]["image_bytes_written"] == 0
    assert LLM_ACCEPTANCE["required"]["flash_written"] is False


def test_step15_image_and_model_identity(ready):
    """The reviewed image/package/model on disk are byte-identical to the record."""
    artifacts = ready["checks"]["artifacts"]
    assert artifacts["bitstream"]["sha256"] == EXPECTED_BITSTREAM_SHA256
    assert artifacts["bitstream"]["sha256_match"] is True
    assert artifacts["package_manifest"]["sha256"] == EXPECTED_PACKAGE_MANIFEST_SHA256
    assert artifacts["package_manifest"]["sha256_match"] is True
    assert artifacts["model"]["sha256"] == EXPECTED_MODEL_SHA256
    assert artifacts["model"]["sha256_match"] is True
    assert artifacts["model_dir"]["exists"] is True


def test_step15_historical_acceptance_record(ready):
    """The committed c0182902 acceptance record is internally consistent."""
    record = json.loads(HISTORICAL.read_text())
    assert record["status"] == "PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS"
    assert record["build_id"] == "c0182902"
    assert record["hardware_accessed"] is True
    assert record["flash_written"] is False
    assert record["programming_performed"] is False
    tokens = record["tokens"]
    assert tokens["expected_token_ids"] == EXPECTED_TOKEN_IDS
    assert tokens["actual_token_ids"] == EXPECTED_TOKEN_IDS
    assert tokens["exact_match"] is True
    image = record["image_transfer"]
    assert image["image_bytes"] == EXPECTED_IMAGE_BYTES
    assert image["full_image_readback_sha256"] == EXPECTED_IMAGE_SHA256
    assert image["offline_image_sha256"] == EXPECTED_IMAGE_SHA256
    assert image["full_image_checksum_verified"] is True
    assert record["program_readback"]["count"] == 13
    assert record["program_readback"]["all_pass"] is True
    assert record["calibration_unchanged"] is True
    assert record["warm_repeat"]["status"] == "PASS_WARM_REPEAT_PHYSICAL_JTAG_TINYSTORIES_EXACT_ISA_TOKENS"
    assert record["warm_repeat"]["image_upload_bytes_written_this_attempt"] == 0
    assert record["warm_repeat"]["actual_token_ids"] == EXPECTED_TOKEN_IDS


def test_step15_llm_recipe_is_documented(ready):
    """ladder/docs/oncard-llm.md is the executable end-to-end acceptance recipe."""
    text = ONCARD_DOC.read_text()
    for needle in ("/home/fedora/ypcb/dlc10-init.sh", "tools/fedora_bringup.sh program",
                   "tools/fedora_bringup.sh jtag-server", "calibrate_spare_c0182902.py",
                   "check_tinystories_c0182902_model.py", "run_tinystories_shared_jtag.py",
                   "repeat_tinystories_shared_jtag.py", "verify_tinystories_shared_jtag.py",
                   "Once upon a time", "29892", "d32fd284", "warm repeat",
                   "flash_written: false", "blocker"):
        assert needle in text, f"ladder/docs/oncard-llm.md does not document {needle!r}"


def test_step15_live_model_run_expected_tokens(ready):
    """TODO(step 15): run the live model and compare the 8 tokens exactly.

    Not implemented yet: the hardware half needs the cable, the step-12 image
    in SRAM, the image-bound calibration receipt and the fresh ISA oracle.
    When it lands it must:
      * run the structural preflight on the same configured image (2,048 init
        chunks, 1,371-instruction fetch / 65 exact words, exact int8 matmul,
        13/13 program readbacks with WAITC);
      * run greedy generation for prompt "Once upon a time" (ids
        [1,9038,2501,263,931]) with max_new=8 and require actual ==
        [29892,727,471,263,2217,7826,4257,365] token for token;
      * require uploaded-image SHA == oracle upload hash and, when the full
        readback is done, image SHA d32fd284…; calibration snapshot unchanged,
        ECC 0/0 both channels, temperature recorded;
      * record ladder/evidence/step15.json + raw logs in
        ladder/evidence/hardware/ with flash_written: false.
    """
    pytest.skip("TODO(step 15): live TinyStories model run waits for the DLC10 "
                "cable and card; see ladder/docs/oncard-llm.md")


def test_step15_warm_repeat_and_optional_evidence(ready):
    """TODO(step 15): warm repeat with zero image rewrite + optional extra evidence.

    When the hardware half lands it must re-run the generation on the already
    configured image (0 image bytes written, same tokens, calibration
    unchanged), and may record the optional full-image readback (sha
    d32fd284…) and the synthetic native-read bandwidth span (64 MiB, 3
    repeats; not an LLM decode rate).  Neither optional check replaces the
    exact-token acceptance.
    """
    pytest.skip("TODO(step 15): warm repeat / optional readback+bandwidth wait for "
                "the DLC10 cable and card; see ladder/docs/oncard-llm.md")
