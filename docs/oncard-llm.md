# LLM inference on the card over JTAG (ladder step 15)

Step 15 is the ladder's **end-to-end acceptance**: run TinyStories-15M int8 on
the real YPCB-00338 Kintex-7 card over the DLC10/JTAG runtime and reproduce the
acceptance the production branch already recorded for image `c0182902`:

- prompt `"Once upon a time"` (token ids `[1, 9038, 2501, 263, 931]`) →
  greedy continuation tokens `[29892, 727, 471, 263, 2217, 7826, 4257, 365]`,
  exact and in order (decodes `" there was a little girl named L"`);
- 29,226,624-byte int8 model image with SHA-256
  `d32fd2844e1f5330bfa36bfd43374516fee7b141aefd731ad58eecb0e130e993`;
- calibration unchanged, ECC counters clean, warm repeat with **0 image bytes
  written**, `flash_written: false`.

The software side (acceptance tooling, gate test, this recipe, the committed
historical evidence) is in. The hardware assertion is **BLOCKED**: the DLC10
cable and the card are not attached on this host (2026-11-10). A blocked run is
recorded as `BLOCKED` (runner exit 5), never PASS; no skipping path re-creates
the historical PASS.

## Tooling and evidence in this branch

Steps 12/13 imported the YPCB build flow, the Fedora DLC10/XVC helpers, the
JTAG/XVC transport and the c0182902 acceptance drivers. Step 15 adds the two
remaining tracked tools and the LLM gate/plan:

| Path | Role |
| --- | --- |
| `tools/spare_program_fetch_check.py` | the 1,371-instruction fetch / 65-word preflight the runner uses before any model upload |
| `tools/spare_runtime_c0182902.py` | the image-bound CH0 calibration guards (live mailbox/phase/readiness checks) |
| `tools/run_tinystories_shared_jtag.py`, `tools/repeat_tinystories_shared_jtag.py`, `tools/verify_tinystories_shared_jtag.py`, `tools/check_tinystories_c0182902_model.py`, `tools/run_spare_c0182902_bandwidth.py`, `tools/fedora_matmul_check.py` | imported at step 13; the acceptance drivers |
| `docs/tinystories_jtag_c0182902.md`, `docs/data/c0182902-tinystories-jtag-20261107.json` | imported at step 13; the recorded historical PASS |
| `ladder/tests/test_step15_hardware_gate.py` | probe-gated acceptance gate (structural checks when ready, TODO skips for the live run) |
| `ladder/harness/hardware.py` | `LLM_ACCEPTANCE` constants + commands; probe-driven |

All imported files are byte-identical to product commit `ca05e24f` and listed
with SHA-256 in
[`ladder/hardware/import-provenance.json`](../ladder/hardware/import-provenance.json)
(`steps.15.files`); the gate test re-checks them.

## Exact acceptance recipe

Prerequisites (product tree unless noted): the step-12 image built from this
branch, the reviewed package
`bitstreams/spare-dual-host-4gb-c0182902-exact-review/`, the model
`build/models/TinyStories-Llama-15M-tiles128-20261018-v2`, a prepared
`HOST_TREE` (product tree's
`build/handoffs/c0182902-jtag-test-host-20261107-v2/host`), the patched DLC10
loader (`$YPCB_LOADER`), `~/ypcb/dlc10-init.sh`, and a Python with
`sentencepiece` for the oracle (pass
`--tokenizer-path build/checks/tinystories-tokenizer-py314-20261018`; the
`build/fedora-venv` Python 3.14 does not include it).

```sh
# 0. gate — must print status "ready", exit 0; otherwise BLOCKED, stop here
python3 ladder/hardware/probe.py --json

# 1. cable init + volatile SRAM configuration (never the flash)
bash /home/fedora/ypcb/dlc10-init.sh
BIT=build/vivado/otpu.bit bash tools/fedora_bringup.sh program

# 2. reviewed XVC runtime at 127.0.0.1:3721 (foreground)
bash tools/fedora_bringup.sh jtag-server

# 3. image-bound CH0 calibration receipt (host-tree tool)
build/fedora-venv/bin/python -B "$HOST_TREE/tools/calibrate_spare_c0182902.py" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --transport jtag --xvc-host 127.0.0.1 --xvc-port 3721 --out "$CALIB"

# 4. fresh ISA oracle (expected tokens + packed-image hashes; offline, ~20 s)
build/fedora-venv/bin/python -B tools/check_tinystories_c0182902_model.py \
  --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --tokenizer-path build/checks/tinystories-tokenizer-py314-20261018 \
  --out "$ORACLE"

# 5. structural preflight + model run (drop --execute for the offline preflight)
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/run_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE/manifest.json" --out "$RUN" \
  --calibration-receipt "$CALIB/manifest.json" \
  --xvc-host 127.0.0.1 --xvc-port 3721 --execute

# 6. warm repeat — same configured image, 0 image bytes rewritten
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/repeat_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE/manifest.json" --out "$REPEAT" --prior-run "$RUN" \
  --calibration-receipt "$CALIB/manifest.json" \
  --xvc-host 127.0.0.1 --xvc-port 3721 --execute

# 7. optional: full-image coverage and the synthetic native-read benchmark
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/verify_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE/manifest.json" --out "$VERIFY" \
  --prefix-receipt "$CANCELLED_READBACK" --run-receipt "$RUN" \
  --calibration-receipt "$CALIB/manifest.json" \
  --xvc-host 127.0.0.1 --xvc-port 3721 --execute
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/run_spare_c0182902_bandwidth.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --calibration-receipt "$CALIB/manifest.json" \
  --xvc-host 127.0.0.1 --xvc-port 3721 \
  --span 67108864 --repeats 3 --out "$BANDWIDTH"
```

## Acceptance criteria (step 15)

- **Structural preflight on the same configured image:** 2,048 DDR-init
  chunks; 1,371-instruction program fetch with 65 exact words; exact int8
  matmul (5 instructions); 13/13 inference-program readbacks PASS with WAITC.
- **Live identity/config:** `BUILD_ID` and arithmetic config match the oracle
  (133.333 MHz, DDR1066, S=1, D=128, MCOLS=4, ACT_BLOCKS=128, TMEM 65,536
  words, IMEM 32,768 words, LANES=8, PAIR/DSTEP/STREAM/SEQ_WC as recorded).
- **Model run:** actual tokens **exactly**
  `[29892,727,471,263,2217,7826,4257,365]`; uploaded image SHA == oracle
  `upload_image_sha256`; full readback (when done) == `d32fd284…`.
- **Safety/health:** calibration snapshot unchanged; ECC counters 0/0 on both
  channels before and after; temperature recorded; `flash_written: false`.
- **Warm repeat:** same 8 tokens, `image_upload_bytes_written_this_attempt: 0`,
  calibration unchanged.
- **Receipt:** `ladder/evidence/step15.json` plus raw logs under
  `ladder/evidence/hardware/`; the historical PASS is cited, not re-created.

## Historical evidence (cited, not re-created)

The production branch recorded the PASS on this card on 2026-11-07/08 (HKT) for
image `c0182902` (133.333 MHz / DDR1066, 4 GiB, CH0 spare lanes
`[0,1,2,3,4,5,8,7]` ECC off, CH1 ECC, both JTAG and PCIe interfaces):

- [`docs/tinystories_jtag_c0182902.md`](tinystories_jtag_c0182902.md)
- [`docs/data/c0182902-tinystories-jtag-20261107.json`](data/c0182902-tinystories-jtag-20261107.json)

Summary of that record: exact tokens, 13/13 program readbacks, full image hash
`d32fd284…`, warm repeat with 0 bytes written, calibration unchanged, ECC 0/0,
die 56.2 °C, native read 3.981 GB/s (synthetic span; not a decode rate), no
flash write and no FPGA reconfiguration during the run.

## Current blocker and lift procedure

The DLC10 JTAG cable and the YPCB card are **not attached** (2026-11-10):

```sh
$ python3 ladder/hardware/probe.py --json
{ "status": "blocked", "exit_code": 3,
  "blocking_reasons": [{"reason": "jtag_cable_absent",
    "detail": "no 03fd:* DLC10 / 0403:6014 FT232H device in lsusb"}], ... }
```

No DLC10/FT232H on USB, no `10ee` Xilinx PCIe endpoint, no `/dev/xdma*`. The
step-15 gate skips and the runner records `BLOCKED` (exit 5) in
`ladder/evidence/step15.json` with the probe JSON in
`ladder/evidence/hardware/probe-step15.json`.

**Lift:** attach the DLC10 cable to the powered card → re-run
`python3 ladder/hardware/probe.py --json` until it exits 0 → run the recipe
above in order (record the probe JSON and every receipt directory) → commit the
step-15 PASS receipt with the full image/oracle hashes. The card's SRAM
configuration is volatile: a power cycle or reconfiguration discards the image
and the loaded model, so reprogram + recalibrate first.

## Cost / time (measured on this host, 2026-11-10 recon)

| action | cost |
| --- | --- |
| ISA oracle (offline) | ≈20 s |
| structural preflight + image upload, 29.2 MB | upload measured 15,488.89 s ≈ **4h18m** on c0182902 (older images ≈14 kB/s → ~35 min) |
| full image readback (optional), 29.2 MB | ≈4.5 h at the documented ~1.8 kB/s; the passing run skipped it and closed coverage in a later 13.5 MB suffix pass ≈1.5 h |
| inference compute | negligible (≈0.3 M device cycles/token); wall time is JTAG round-trips |
| warm repeat | no image upload; generation/preflight only |
| native-read benchmark (optional) | 3 × 64 MiB spans; synthetic throughput, not a decode rate |

## Known gaps (documented, not invented)

- **Untracked local artifacts (product tree):** the c0182902 bitstream package,
  the model directory, the image-bound calibration receipt, the oracle output,
  the prepared `HOST_TREE` and the raw `/tmp/opencode` run receipts (lost).
  They must be regenerated/reused locally; none is in git.
- **Calibration receipt must be regenerated:** `calibrate_spare_c0182902.py`
  exists only in the package/handoff host trees in the product tree (not
  tracked in the repo), and the old receipt hash `39827b92…` cannot be
  re-verified. `tools/spare_runtime_c0182902.py` is imported here for its
  guards, but its import closure (`opentpu/host/{regs,selfcal,dual_pcie}`) is
  the step-11/16 host stack.
- **`sentencepiece`:** missing from `build/fedora-venv` (Python 3.14); the
  cp314 wheel under `build/checks/tinystories-tokenizer-py314-20261018` works
  via `--tokenizer-path`.
- **Model preparation tool not tracked:** `tools/prepare_tinystories_tiles.py`
  exists in the product working tree but is untracked at `ca05e24f`, so it
  cannot be imported byte-identically here; the prepared model artifact is the
  pinned `9f74baf7…` directory.
- **Host-local prerequisites, not vendored:** Vivado 2026.1, the patched DLC10
  loader, `~/ypcb/dlc10-init.sh`, `build/fedora-openxc7/xvc-ready.json`, and
  the external `../bonetto-soc` checker used by the native-image helper.
- **Step 14 owns the LLM layer (`opentpu/llm/`)** and step 11 the host board
  stack; the acceptance drivers are executed against the prepared `HOST_TREE`
  until those imports converge at step 16.

See [`docs/oncard-jtag.md`](oncard-jtag.md) for the shared JTAG runtime recipe
and [`docs/fpga-flow.md`](fpga-flow.md) for the image build flow.
