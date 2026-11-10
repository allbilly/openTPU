# Hardware validation plan — ladder steps 12, 13 and 15 (YPCB-00338-1P1)

Status **2026-11-10: BLOCKED — DLC10 cable and card are not attached.** The
software side (this probe, these instructions, the gate tests) is prepared and
verified; the on-card assertions in steps 12/13/15 wait for hardware.

This document is the executable acceptance recipe for the three *hardware*
rungs of [`ladder/README.md`](../README.md). It is read-only until the "Program
SRAM" step; **no command here writes the configuration flash**, and a permanent
flash write needs a separate explicit per-image user approval (repo rule,
`AGENTS.md`).

The product tree that holds the untracked artifacts and host tools is
`/home/fedora/openTPU` (`$PRODUCT_ROOT` below; override with `--repo` or
`LADDER_PRODUCT_ROOT`). The ladder branch itself is a git worktree of that
checkout at `~/openTPU-ladder`.

---

## 1. Gate probe — read-only, run first, every time

```sh
python3 ladder/hardware/probe.py --json
```

Exit codes are the hardware-gate contract:

| exit | status | meaning | ladder runner must record |
| ---: | --- | --- | --- |
| 0 | `ready` | JTAG cable present, no cable owner, artifacts present and hash-verified | run the step's tests |
| 3 | `blocked` | no DLC10/FT232H, missing artifact, or the cable is held | **BLOCKED**, never PASS/FAIL |
| 4 | `unexpected` | artifact hash mismatch / wrong image, missing probe tool, probe failure | **FAIL** (unsafe to proceed) |

The probe observes only: `lsusb` (DLC10 `03fd:0013`/`03fd:0008`, FT232H
`0403:6014`), `lspci` (Xilinx `10ee`, informational — this host is JTAG-only),
`/dev/xdma*`, `/proc` for `openFPGALoader|hw_server|xsdb|fxload` (cable owners,
blocking) and `vivado|vivado_lab` (heavy contention, warning), `/proc/net/tcp*`
for a listener on XVC port 3721, `k10temp` (92 °C runner limit), the shared-host
lock `/tmp/rknpu-heavy.lock`, and the presence/SHA-256 of the known artifacts.
It never programs, flashes, resets or starts a cable/XVC server.

## 2. Preconditions (all must hold before a hardware step starts)

1. Probe exits **0** (`ready`). Current state is 3 (see §9).
2. Exclusive cable ownership: no `openFPGALoader`, `hw_server`, `xsdb`,
   `fxload` process; no sibling-project JTAG work in flight.
3. `LADDER_ALLOW_HARDWARE=1` set for the runner (hardware steps refuse to run
   without it). Heavy work also needs the shared-host lock and k10temp < 92 °C;
   `ladder/run.py` enforces both, waiting up to 90 min for the lock.
4. The exact image/package/model identities below are present and hash-matched
   (probe `checks.artifacts`). These are **local untracked artifacts** of
   `$PRODUCT_ROOT`; a fresh clone must rebuild/re-review or import them.
5. `sentencepiece` for the oracle: `build/fedora-venv/bin/python` is 3.14 and
   has no `sentencepiece`; pass
   `--tokenizer-path build/checks/tinystories-tokenizer-py314-20261018`.
6. The c0182902 oracle output, image-bound CH0 calibration receipt and raw run
   receipts under `/tmp/opencode` were **lost** (2026-11-10 recon). They must be
   regenerated before a live run; do not claim to re-verify their old hashes.

## 3. Exact commands (from `$PRODUCT_ROOT` unless stated)

### 3.1 Cable initialization + detection (never programs)

```sh
bash /home/fedora/ypcb/dlc10-init.sh
```

Uploads the volatile DLC10 boot/overlay firmware, verifies its hashes, requires
exactly one `03fd` cable and detects the FPGA (IDCODE `0x23751093`). It refuses
to run while a cable-owner process exists. Logs go to a `/tmp/dlc10-init.*`
directory.

### 3.2 Program the FPGA SRAM (volatile configuration; this is the only load)

```sh
BIT="bitstreams/spare-dual-host-4gb-c0182902-exact-review/otpu.bit" \
  bash tools/fedora_bringup.sh program
```

`tools/fedora_bringup.sh program` runs `dlc10-init.sh`, then
`tools/fedora_check_jtag_chain.py`, then the patched loader
(`$YPCB_LOADER`, default
`/home/fedora/ypcb/openFPGALoader/build-xpcu-debug/openFPGALoader`):

```sh
<loader> --cable xilinxPlatformCableUsb --freq 6000000 --index-chain 0 <BIT>
```

Success shows `isc_done 1` / `init 1` / `done 1` in the loader output. This
does **not** touch the BPI flash. Power-cycling the card discards the image.

### 3.3 Start the reviewed XVC runtime server (foreground; port 3721)

```sh
bash tools/fedora_bringup.sh jtag-server
```

Validates `build/fedora-openxc7/xvc-ready.json` (reviewed binary
`build/fedora-openxc7/portable-xpcu-xvc-20261016/binary/openFPGALoader`,
sha256 `bfa6bf97…`) and the DLC10 boot firmware hash
(`4fe1a679efcc7ed7c01e738beaf29d8a1f1201731780dfc026f724a88aee527a`), rejects
active cable owners, then binds `127.0.0.1:3721`. If the binary is missing, run
`bash tools/fedora_bringup.sh xvc-build` once (`tools/fedora_prepare_xvc.py`,
offline build). Generic read-only USER2 diagnostics:
`bash tools/fedora_bringup.sh jtag smi|memcal|selftest`.

### 3.4 Step 12 — ladder image build + SRAM bring-up

The ladder tree must first import the YPCB build flow (`boards/ypcb-00338/`,
`tools/litedram/`, constraints, LiteDRAM generation) and the host tools from the
product branch `ypcb/dual-channel-4gb` (see §8). Then:

```sh
# heavy: shared-host lock + k10temp gate are enforced by the runner
python3 ladder/run.py lock -- make -C boards/ypcb-00338 bit \
    BIT=../../ladder/artifacts/step12/otpu.bit
# then program + observe the on-card self-test over XVC (3.1-3.3), e.g.
BIT=ladder/artifacts/step12/otpu.bit bash tools/fedora_bringup.sh program
```

Acceptance requires a build receipt (bitstream SHA-256, timing/DRC summary,
source hashes), the SRAM programming result, and an on-card self-test PASS
observed over JTAG, with **both** JTAG and PCIe runtime interfaces retained.
Until this flow lands in the ladder tree the step-12 test skips with a TODO.

### 3.5 Steps 13/15 — JTAG runtime acceptance (TinyStories target)

After 3.1–3.3 (and the step-12 image), with `$HOST_TREE` and `$CALIB` fresh:

```sh
HOST_TREE=/home/fedora/openTPU/build/handoffs/c0182902-jtag-test-host-20261107-v2/host
# a) image-bound CH0 calibration (host-tree tool; NOT tracked in git)
build/fedora-venv/bin/python -B "$HOST_TREE/tools/calibrate_spare_c0182902.py" \
    --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
    --transport jtag --xvc-host 127.0.0.1 --xvc-port 3721 --out "$CALIB"
# b) offline ISA oracle
build/fedora-venv/bin/python -B tools/check_tinystories_c0182902_model.py \
    --host-tree "$HOST_TREE" \
    --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
    --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
    --tokenizer-path build/checks/tinystories-tokenizer-py314-20261018 \
    --out "$ORACLE_OUT"
# c) structural preflight + model run over XVC (drop --execute for preflight only)
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/run_tinystories_shared_jtag.py \
    --build-id c0182902 --host-tree "$HOST_TREE" \
    --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
    --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
    --oracle "$ORACLE_OUT/manifest.json" --out "$RUN_OUT" \
    --calibration-receipt "$CALIB/manifest.json" \
    --xvc-host 127.0.0.1 --xvc-port 3721 --execute
# d) warm repeat (reuses the configured image; 0 image bytes written)
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
  build/fedora-venv/bin/python -B tools/repeat_tinystories_shared_jtag.py \
    --build-id c0182902 --host-tree "$HOST_TREE" \
    --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
    --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
    --oracle "$ORACLE_OUT/manifest.json" --out "$REPEAT_OUT" \
    --prior-run "$RUN_OUT" --calibration-receipt "$CALIB/manifest.json" \
    --xvc-host 127.0.0.1 --xvc-port 3721 --execute
# e) full-image coverage and native-read benchmark
... tools/verify_tinystories_shared_jtag.py   (prefix receipt + passing run receipt)
... tools/run_spare_c0182902_bandwidth.py --span 67108864 --repeats 3
```

## 4. Acceptance criteria (what counts as hardware PASS)

Pinned identities (VERIFIED local hashes): image `c0182902`; bitstream
`3b804b81456f7c075a83e965bd012ec84865293a0ea18e1d55746c1ed79838cf`;
package manifest `72193faf07305e45503b11331e698b9fd46a86199d4486e250975cc3fb1737be`;
model `9f74baf73f258f040f0994b9fb67da17eb92cf56b2214f309b5d037c82e1da8b`;
image content `d32fd2844e1f5330bfa36bfd43374516fee7b141aefd731ad58eecb0e130e993`
(29,226,624 B); prompt "Once upon a time" (ids `[1,9038,2501,263,931]`).

- **Step 12:** build receipt with bitstream SHA-256 + timing/DRC + source
  hashes; SRAM programming receipt; on-card self-test/RAM-test PASS over JTAG;
  image keeps both JTAG and PCIe runtime interfaces; `flash_written: false`.
- **Step 13:** live BUILD_ID/config registers match the oracle; on-card matmul
  bytes == `opentpu/isasim.py` bit for bit; image-bound calibration receipt
  matches the live calibration snapshot; ECC clean; `flash_written: false`.
- **Step 15:** structural preflight (2,048 init chunks, 1,371-instruction fetch
  with 65 exact words, exact int8 matmul, 13/13 program readbacks with WAITC);
  greedy tokens `[29892,727,471,263,2217,7826,4257,365]` exactly equal the ISA
  oracle; uploaded-image SHA == oracle upload hash and full readback ==
  `d32fd284…`; calibration unchanged; ECC 0/0 both channels; warm repeat with
  0 image bytes written; `flash_written: false`. Receipt in
  `ladder/evidence/step15.json` + raw logs in `ladder/evidence/hardware/`,
  citing (not re-creating) the 2026-11-07/08 c0182902 PASS in
  `docs/tinystories_jtag_c0182902.md` / `docs/data/c0182902-tinystories-jtag-20261107.json`.

## 5. Cost / time estimates (measured on this host, 2026-11-10 recon)

| action | cost |
| --- | --- |
| read-only probe | < 1 s (hashes 160 MiB of artifacts) |
| full Vivado synth+impl+bitstream (step 12) | ≈1.5-4 h under the heavy lock (c0182902 measured 1h32m; c0184811 3h40m) |
| SRAM programming, 13.9 MB image | minutes (`--freq 6000000`; scripts allow 180 s) |
| ISA oracle (offline) | 11-20 s |
| JTAG model-image upload, 29.2 MB | measured 15,488.89 s ≈ **4h18m** on c0182902 (older images ≈14 kB/s → ~35 min) |
| full image readback, 29.2 MB | ≈4.5 h at the documented ~1.8 kB/s; passing run skipped it (13.5 MB suffix pass ≈1.5 h) |
| DDR init 2,048 chunks (200 ms pacing) | ≈7 min + overhead |
| inference compute | negligible (≈0.3 M device cycles/token); wall time is JTAG round-trips |
| warm repeat | no image upload; the rest above |

## 6. Risks and failure modes

- **Hardware absent** (current blocker) — steps stay blocked; never substitute
  a skip for a PASS.
- **Untracked artifacts / lost raw receipts** — package, model, oracle and
  calibration receipt are local-only; `/tmp/opencode` receipts are gone.
- **Volatile SRAM** — power loss or reconfiguration discards the image *and*
  the loaded model; reprogram + recalibrate before inference.
- **Identity guards** — bitstream/package/model/image SHA mismatches and
  calibration snapshots are hard stops (probe exit 4 / runner FAIL).
- **Transport slowness** — full-image verification is multi-hour; plan the
  readback in a separate authorized session.
- **USB/DLC10 flakiness** — use the reviewed xpcu/XVC path, not native Vivado
  `hw_server` libusb, for runtime; replug the cable after an "Unable to read
  constant" error.
- **Shared host** — sibling project's Vivado jobs hold `/tmp/rknpu-heavy.lock`
  and can push k10temp toward the 92 °C limit; serialize via
  `python3 ladder/run.py lock -- ...` and never kill the sibling job.
- **Flash** — permanent programming is explicitly out of scope here and needs
  an explicit per-image user approval.

## 7. Probe / gate integration

`ladder/tests/test_step12_hardware_gate.py`, `test_step13_hardware_gate.py` and
`test_step15_hardware_gate.py` run the probe in-process-subprocess and
`pytest.skip("hardware absent: <reasons>")` whenever it exits 3; exit 4 is a
test failure. With hardware present the structural identity checks run and the
not-yet-implemented on-card actions skip with `TODO(step NN)`. The runner must
map: probe 3 → step BLOCKED, probe 4 → step FAIL, and for hardware steps never
record PASS while any test is skipped (the runner at this ladder tip already
implements that policy: BLOCKED verdict, exit 5, `evidence-check` accepts it;
see `ladder/README.md` "Verdicts, exit codes and receipt binding").

## 8. Import status in the ladder tree (step 12/13)

Step 12 imported these byte-identically from product commit `ca05e24f`
(`ypcb/dual-channel-4gb`); every hash is recorded in
`ladder/hardware/import-provenance.json` and re-checked by the step-12 gate
test when hardware is present (95 files):

- `boards/ypcb-00338/` (49 files): the full Vivado flow — `Makefile`,
  `run_vivado.sh`, `vivado/*.tcl` (including `bd_native.tcl` with the XDMA/PCIe
  block design), constraints, the generated LiteDRAM core, RAM-test builds and
  board simulations.
- `tools/litedram/` (35 files): core generation, PHY knobs, CSR/ECC helpers and
  the self-calibration firmware.
- `tools/fedora_bringup.sh`, `tools/fedora_prepare_xvc.py`,
  `tools/fedora_xvc_server.py`, `tools/fedora_jtag.py`,
  `tools/fedora_check_jtag_chain.py`, `tools/fedora_check_native_image.py`,
  `tools/fedora_prepare_litedram.py`, `tools/workspace_paths.py`.
- `opentpu/host/__init__.py`, `opentpu/host/jtag.py` (JTAG/XVC transport used
  by `tools/fedora_jtag.py` and the XVC protocol tests).
- `docs/vivado_bitstream_guide.md`; `rtl/boards/ypcb-00338/` and
  `sim/verilator/tb_board.sv` were already imported byte-identically at step 9.
- Step 13 adds `tests/tb_xpcu_xvc.cpp` and `tests/test_xvc_transport.py` (the
  XVC transport protocol evidence) plus `ladder/harness/hardware.py`.

See [`docs/fpga-flow.md`](../../docs/fpga-flow.md) for the build flow, exact
commands, the dual-interface rule and the known gaps.

**Known gaps (documented, not invented):** the c0182902 bitstream package,
model, image-bound calibration receipt and oracle are untracked local artifacts
of the product tree (step 15/16 scope); `tools/run_tinystories_shared_jtag.py`
and its `spare_runtime_*`/`opentpu/llm` closure are tracked at `ca05e24f` but
pull the compiler/LLM/host stacks imported at steps 10/11/14, so they are not
part of this rung yet; `tools/fedora_check_native_image.py` refers to an
external `../bonetto-soc/scripts/fedora-check-vivado-bitstream.py`; and the
openXC7-native actions of `tools/fedora_bringup.sh` are outside the Vivado flow
imported here. Host-local prerequisites (Vivado 2026.1, the patched DLC10
loader, `~/ypcb/dlc10-init.sh`, `build/fedora-openxc7/xvc-ready.json`) are not
vendored.

## 9. Current blocker evidence (2026-11-10, read-only)

Exact probes that establish "blocked":

```sh
lsusb | grep -Ei '03fd:|0403:6014'        # no output: no DLC10, no FT232H
lsusb                                      # only hubs, camera 30c9:0014, BT 0bda:c123
lspci -nn | grep -i '10ee'                 # no output: no Xilinx PCIe endpoint
ls /dev/xdma* 2>/dev/null                  # no such file
python3 ladder/hardware/probe.py --json    # exit 3, status blocked,
                                           # reason jtag_cable_absent
```

Observed on 2026-11-10: `probe.py` exits 3 with
`jtag_cable_absent: no 03fd:* DLC10 / 0403:6014 FT232H device in lsusb`; no
Xilinx PCIe device; no `/dev/xdma*`; no XVC listener on 3721. It also reported
transient warnings (not hardware absence): a sibling-project Vivado synthesis
run held `/tmp/rknpu-heavy.lock` and k10temp was 89.8-93.5 °C (runner limit
92 °C). The last recorded attachment of the card was the 2026-10-17 tiny-tpu
physical test (DLC10 `03fd:0008`); c0182902 was exercised 2026-11-06/08.

**Lift procedure:** attach the DLC10 cable to the powered card → re-run
`python3 ladder/hardware/probe.py --json` until exit 0 → follow §3 in order.
Record the probe JSON in `ladder/evidence/hardware/` with the step receipt.

## 10. Receipts

- `ladder/evidence/step12.json` — build + SRAM programming + on-card self-test.
- `ladder/evidence/step13.json` — on-card matmul vs `isasim`.
- `ladder/evidence/step15.json` — full TinyStories JTAG acceptance.
- `ladder/evidence/hardware/` — raw probe JSON, loader logs, XVC run logs,
  calibration/oracle files, image readback hashes, token comparisons.
