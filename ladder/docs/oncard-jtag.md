# On-card kernel over JTAG (ladder step 13)

Step 13 is the first end-to-end **host → image → accelerator → result** loop on
real silicon: using the step-12 image, upload a small program/image over the
JTAG runtime and run a matmul on the YPCB-00338 card; the on-card result must
equal the bit-exact ISA simulator (`opentpu/isasim.py`). Step 15 reuses the
same runtime for the full TinyStories-15M int8 acceptance.

The software side (JTAG/XVC runtime tools and protocol evidence, the exact
acceptance drivers, the historical evidence and this recipe) is committed.
The hardware assertion is **BLOCKED**: the DLC10 cable and the card are not
attached on this host (2026-11-10). The read-only probe records the evidence;
no run is faked.

## What this step imported (byte-identical from `ca05e24f`)

Recorded with SHA-256 in
[`ladder/hardware/import-provenance.json`](../hardware/import-provenance.json)
(`steps.13.files`) and re-checked by the step-13 gate test:

| Group | Paths | Notes |
| --- | --- | --- |
| XVC protocol evidence | `tests/test_xvc_transport.py`, `tests/tb_xpcu_xvc.cpp` | the real XVC TCP client against a local USER2/IDCODE endpoint, and the XPCU encoder/decoder bench against an FX2 USB protocol model |
| Exact-image acceptance drivers | `tools/run_tinystories_shared_jtag.py`, `tools/repeat_tinystories_shared_jtag.py`, `tools/verify_tinystories_shared_jtag.py`, `tools/check_tinystories_c0182902_model.py`, `tools/run_spare_c0182902_bandwidth.py`, `tools/fedora_matmul_check.py` | stdlib-importable at module level; they take a prepared `--host-tree` at run time (see gaps) |
| Historical evidence | `docs/tinystories_jtag_c0182902.md`, `docs/data/c0182902-tinystories-jtag-20261107.json` | the recorded c0182902 PASS this rung reproduces (2026-11-07/08 HKT) |

Already imported at step 12: `opentpu/host/jtag.py` (the USER2/XVC transport),
`tools/fedora_{bringup.sh,prepare_xvc.py,xvc_server.py,jtag.py,check_jtag_chain.py,check_native_image.py}`,
`tools/litedram/` and the YPCB build flow. `ladder/harness/hardware.py` wraps
the probe gate and pins the acceptance constants/commands.

## Acceptance recipe (run when the cable + card are attached)

Prerequisites (product tree unless noted): the step-12 image built from this
branch, the reviewed c0182902 package
`bitstreams/spare-dual-host-4gb-c0182902-exact-review/`, the model
`build/models/TinyStories-Llama-15M-tiles128-20261018-v2`, a prepared
c0182902 `HOST_TREE` (the product tree's
`build/handoffs/c0182902-jtag-test-host-20261107-v2/host` has the frozen tools;
it is a local artifact, not in git), the patched DLC10 `openFPGALoader`
(`$YPCB_LOADER`), `~/ypcb/dlc10-init.sh`, and a Python with `sentencepiece`
for the oracle (`build/fedora-venv/bin/python` is 3.14 without it; pass
`--tokenizer-path build/checks/tinystories-tokenizer-py314-20261018`).

```sh
# 0. gate: must print status "ready", exit 0 (otherwise BLOCKED, stop)
python3 ladder/hardware/probe.py --json

# 1. honestly own the cable: no openFPGALoader/hw_server/xsdb/fxload running
bash /home/fedora/ypcb/dlc10-init.sh                     # volatile cable firmware + detect
BIT=build/vivado/otpu.bit bash tools/fedora_bringup.sh program   # SRAM only, never flash

# 2. reviewed XVC runtime at 127.0.0.1:3721 (foreground)
bash tools/fedora_bringup.sh jtag-server

# 3. image-bound CH0 calibration receipt (host-tree tool; untracked artifact)
build/fedora-venv/bin/python -B "$HOST_TREE/tools/calibrate_spare_c0182902.py" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --transport jtag --xvc-host 127.0.0.1 --xvc-port 3721 --out "$CALIB"

# 4. offline ISA oracle (expected tokens + packed image hashes)
build/fedora-venv/bin/python -B tools/check_tinystories_c0182902_model.py \
  --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --tokenizer-path build/checks/tinystories-tokenizer-py314-20261018 \
  --out "$ORACLE"

# 5. structural preflight + on-card run (drop --execute for the offline preflight)
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/run_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE/manifest.json" --out "$RUN" \
  --calibration-receipt "$CALIB/manifest.json" \
  --xvc-host 127.0.0.1 --xvc-port 3721 --execute

# 6. warm repeat (reuses the configured image; 0 image bytes written) and coverage
tools/repeat_tinystories_shared_jtag.py --prior-run "$RUN" \
  --calibration-receipt "$CALIB/manifest.json" ... --execute
tools/verify_tinystories_shared_jtag.py --run-receipt "$RUN" \
  --prefix-receipt "$CANCELLED_READBACK" --calibration-receipt "$CALIB/manifest.json" ...
tools/run_spare_c0182902_bandwidth.py --span 67108864 --repeats 3 ...
```

## Acceptance criteria (step 13)

- Live `BUILD_ID` / arithmetic config registers match the oracle; the
  image-bound calibration receipt matches the live calibration snapshot.
- On-card matmul output bytes equal `opentpu/isasim.py` bit for bit (every
  output word; no tolerance).
- ECC counters clean, calibration unchanged, `flash_written: false`.
- Receipt in `ladder/evidence/step13.json` (raw probe JSON, loader/XVC logs and
  the matmul comparison in `ladder/evidence/hardware/`).
- Step 15 additionally requires prompt "Once upon a time" (ids
  `[1,9038,2501,263,931]`) → tokens
  `[29892,727,471,263,2217,7826,4257,365]` exactly, image SHA-256
  `d32fd284…e130e993` match and the warm repeat.

## Historical evidence this rung reproduces

The production branch recorded a PASS on the same card on 2026-11-07/08 (HKT)
for image `c0182902` (133.333 MHz / DDR1066, 4 GiB, JTAG + PCIe, 29,226,624-byte
model image, exact 8-token continuation, warm repeat, full image checksum
`d32fd284…`, calibration unchanged, `flash_written: false`):
[`docs/tinystories_jtag_c0182902.md`](../../docs/tinystories_jtag_c0182902.md) and
[`docs/data/c0182902-tinystories-jtag-20261107.json`](../../docs/data/c0182902-tinystories-jtag-20261107.json).
The step-13/15 receipts cite this record; they do not re-create it by a skip.

## Current blocker (2026-11-10)

```sh
$ python3 ladder/hardware/probe.py --json
{ "status": "blocked", "exit_code": 3,
  "blocking_reasons": [{"reason": "jtag_cable_absent",
    "detail": "no 03fd:* DLC10 / 0403:6014 FT232H device in lsusb"}], ... }
```

No DLC10 cable/FT232H on USB, no `10ee` Xilinx PCIe endpoint, no `/dev/xdma*`.
The step-13 gate skips and the runner records `BLOCKED` (exit 5) in
`ladder/evidence/step13.json` with the probe JSON in
`ladder/evidence/hardware/probe-step13.json`. The hardware assertion resumes
when the probe exits 0 — then run the recipe above.

## Known gaps (documented, not invented)

- **Runtime closure of the imported drivers:** `tools/spare_runtime_c0182902.py`
  and `opentpu/host/spare_c0182902.py` (with `opentpu/host/{regs,selfcal,dual_pcie,board,chestnut,spare_c0182863}.py`),
  `tools/spare_program_fetch_check.py` (+ `opentpu/waits.py`) and the
  `opentpu/llm/` stack are tracked at `ca05e24f` but belong to the step-10/11/14
  imports, so they are not part of this rung. Until they are imported, the
  acceptance drivers run against the prepared `--host-tree` copy of the frozen
  product tools, not against this branch's own modules.
- **Untracked acceptance artifacts (product tree):** the c0182902 bitstream
  package, model directory, image-bound calibration receipt, oracle output and
  the prepared host tree are local-only; the raw `/tmp/opencode` run receipts
  are gone (2026-11-10 recon). They must be regenerated/reused locally.
- **`opentpu/host/spare_c0182902.py` is tracked but not imported here** (its
  closure is the step-11 host stack); the calibration step above uses the
  host-tree copy instead.
- **Host-local prerequisites, not vendored:** Vivado 2026.1, the patched DLC10
  loader, `~/ypcb/dlc10-init.sh`, `build/fedora-openxc7/xvc-ready.json` and the
  `sentencepiece` wheel under `build/checks/`.
- `tools/fedora_bringup.sh jtag ...` needs an explicit `--litedram-core`
  argument in the ladder tree (its default core selection reads product-tree
  build manifests); the `smi`/`memcal`/`selftest` modules arrive with the
  step-11 host stack.
- See [`docs/fpga-flow.md`](fpga-flow.md) for the build-flow gaps.
