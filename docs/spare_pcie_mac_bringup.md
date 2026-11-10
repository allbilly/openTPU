# 4 GiB spare-lane OpenTPU: Mac and Chestnut handoff

This is the historical c0172080 procedure. Current disposition is in
[HANDOFF.md](../HANDOFF.md); the retained fixed-clock runtime guides are
[c0182800](mac_c0182800.md) and [c0182863](mac_c0182863.md). The c01848
runtime-clock effort was abandoned. This page does not establish the card's
current identity or schedule another hardware test.

The October 17 integration target was build `c0172080`, 100 MHz compute and DDR800,
with 2 GiB per channel. CH0 uses physical lanes `0,1,2,3,4,5,8,7` without ECC;
CH1 retains ECC. This bypasses physical lane 6. The CH1-only 148.84 MHz image
is a different candidate and is not used here.

The permanent-flash operation is recorded under
`build/hardware-test/spare-flash-no-backup-20261017/` on the programming host.
Programming, independent verification and JTAG-requested boot from flash
passed on October 17 at 07:11 UTC (15:11 HKT); the programmer has released
JTAG. Runtime identity and inference subsequently passed on the Mac as recorded
below; repeated cold/warm qualification remains open. The user
explicitly requested skipping a new backup;
the previous CH1-only bitstream/MCS are preserved separately.

The pulled [Mac receipt](data/spare_pcie_benchmark_20261017.json) demonstrates
working c0172080 with 4 GiB and Qwen3.5-2B: full-range zero initialization and
readback, exact matmul output, and eight tokens matching the ISA reference.
Both physical channels were used and the image occupied 94.16% of capacity.
The local evidence review (local-only `docs/data/spare_pcie_mac_evidence_review_20261017.json`)
matches its package/bitstream hashes and checks counter arithmetic. Distinct
full-range native payload patterns and repeated-start qualification below
remain separate work.

## Before starting

Use a compatible 12 V supply with matching connector/polarity. Record the source
and any input-voltage observations at idle and initial activity. The original
sole 12 V / 2 A adapter has not been electrically qualified. The user now
reports a 12 V / 5 A supply; its input voltage/current remain unmeasured. Stop escalation
if voltage is unstable or the card resets. A full investigation of the old
lane-6 fault is not required before the bounded integration test.

Connect the powered card to the Mac through Chestnut. Fedora has only JTAG;
these tests cannot run there. Keep the complete supplied source tree and both
`bitstreams/spare-pcie-4gb-ddr800/` and
`bitstreams/ramtest-litedram-ddr800-spare8/`. The second package binds the
reviewed eight-lane CH0 firmware. No separate `~/ypcb` checkout or Vivado is
needed for these runtime tests. A compatible Python environment with NumPy and
working libusb/Chestnut is required. Reuse the existing inference environment
for the later PyTorch/Transformers/safetensors stage.

The historical runner depended on the local package directories above and the
following runtime files. Some helper/evidence dependencies remain unpublished;
a Git pull alone does not reconstruct that local package. Do not commit the
generated packages or use an archive as a handoff. The newer fixed-clock guides
linked above use tracked host scripts, small calibration/configuration files
and image metadata for an already programmed card.

- `opentpu/host/spare_pcie.py`, `opentpu/host/dual_pcie.py`, and the
  `opentpu/host/chestnut.py` changes.
- `tools/mac_spare_pcie_bringup.sh`, `tools/run_spare_pcie_calibration.py`,
  `tools/run_spare_pcie_dma.py`, `tools/run_spare_pcie_lfm2.py`, and
  `tools/spare_pcie_runtime.py`.
- Their new local helper dependencies: `tools/probe_ramtest_spare_calibration.py`
  and `tools/spare_range_program.py`.
- This procedure and the flash receipt
  `docs/data/spare_pcie_flash_20261017.json`.

The existing tracked `tools/fedora_prepare_litedram.py` (checksum helper),
`tools/fedora_matmul_check.py` and standard `opentpu/`
runtime remain required. Copying just the `.bit` file or pulling a branch
without these new files does not provide the calibration and test tools.
Model weights are supplied separately from the existing Mac checkpoint.

CH1 calibrates automatically at configuration. **CH0 needs the supplied
volatile eight-lane calibration helper after each power cycle or FPGA reload.**
The `quick` procedure below performs that step. A successful flash write alone
does not make both channels ready for inference.

## Run LFM2 on the Mac

Use the Python environment and local LFM2 checkpoint from the previous working
Mac inference run. From the checkout, choose a fresh result directory:

```bash
export SPARE_PYTHON=python3
export SPARE_MODEL=/path/to/LFM2.5-230M
export SPARE_OUT=build/mac-spare4gb-lfm-1
bash tools/mac_spare_pcie_bringup.sh lfm
```

Set `SPARE_PYTHON` to the environment's Python path if needed. This single
command checks the local software/checkpoint before hardware access, verifies
the live image identity, calibrates CH0, initializes and verifies zero memory
so CH1 has valid ECC contents, compares a small matmul with the ISA reference,
and runs an eight-token LFM2 prefill/decode comparison against that reference.
Initialization is required before inference and can take several minutes.
The command does not run the longer complementary-pattern, full native read
sweep or USB payload qualification. Its passing status explicitly leaves
full-memory qualification pending.

Keep `identity/manifest.json`, `calibration/manifest.json` and `lfm/manifest.json`
under `SPARE_OUT`. On a failure, preserve those results and report the first
error. Repeating startup calibration requires a fresh FPGA configuration;
do not repeatedly reload or recalibrate to hide a failure.

## Separate qualification: small DMA and native byte masks

The following procedures are for memory qualification. Start them on a fresh
power-up/configuration with a fresh result directory, separately from the LFM2
startup command above.

From the extracted checkout, select the Python used by the working Mac
inference environment, and a fresh result directory:

```bash
export SPARE_PYTHON=python3
export SPARE_OUT=build/mac-spare4gb-1
bash tools/mac_spare_pcie_bringup.sh quick
```

Set `SPARE_PYTHON` to the environment's absolute Python path if needed. The
script stops on any failure. Preserve the logs and failed manifest. It:

1. Validates the entire image package and reads the actual card identity,
   clocks, capacity, lane map and ECC profile through Chestnut.
2. Uploads/read-verifies all 4,096 firmware words and calibrates CH0, preserving
   the successful CH1 startup state. This overwrites disposable memory.
3. Checks distinct DMA data on each channel at base, 4 KiB, 1 GiB and the top
   4 KiB. All sentinels are written before any is read. It checks logical
   interleaving at zero, around 2 GiB and at the top of the 4 GiB range.
4. Checks partial host writes and untouched bytes. Those calls use software
   merge into full DDR beats and are labeled accordingly.
5. Runs a small native QST program that emits byte-masked writes across both
   interleaved channels. It compares changed and preserved data/scale bytes
   against the ISA simulator. This tests the hardware partial-write path.

Zero payload mismatches and clean CH1 ECC are required. CH0 without ECC does
not permit a few errors. The calibration receipt must remain bound to the
same package and live calibration; after a power cycle, rerun `quick` with a
fresh `SPARE_OUT`.

## Full payload coverage through native DMA

After `quick` passes on the same powered initialization:

```bash
bash tools/mac_spare_pcie_bringup.sh full
```

This writes every payload byte of both 2 GiB channels with channel/address-
dependent data, then reads all bytes in reverse chunk order and compares them.
CH1 uses its native ECC path. It records a SHA256 per 1 MiB transfer and stops
at the first mismatch. Chestnut transfers the entire 4 GiB in each direction;
this can take substantially longer than FPGA-side BIST. The manifest and
`operations.jsonl` show progress. It does not establish sustained simultaneous
compute/traffic or long-term reliability.

## Memory, matmul and LFM2 reference checks

Use the existing local LFM2 checkpoint; the bundle does not duplicate weights:

```bash
export SPARE_MODEL=/path/to/LFM2.5-230M
bash tools/mac_spare_pcie_bringup.sh inference
```

The inference stage first runs the established complementary raw address
tests, fully initializes ECC contents, checks the full logical native-read
coverage and DMA sentinels, then compares physical matmul and LFM2 output with
the ISA reference. Preserve generated token IDs and all model-check records.
The existing memory stage can be run separately with `memory`; inference
repeats it. Raw BIST bypasses ECC, and the native read sweep compares only its
last payload chunk, which is why the separate `full` DMA payload comparison
above is required. Logical data/program writes use both interleaved channels.

The immediate Mac action can be the single `lfm` command. Complete memory
qualification still requires clean `quick`, `full` and inference results on
the baseline image. Repeated cold/warm starts, retention, concurrent compute and
memory traffic, sustained operation and power observations remain qualification
work in this historical scope. The subsequent pipelined c0172300 failed on CH0;
the c0182800/c0182863 successors have their own passing receipts. Refer to
HANDOFF.md for final disposition instead of reviving this earlier priority order.

Return every stage's `manifest.json` and retain the corresponding logs and
`operations.jsonl`. A failure should be reported before power-cycling or
rerunning calibration, so its state and first error remain available.
