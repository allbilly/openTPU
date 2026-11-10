# FPGA build flow for the YPCB-00338 card (ladder step 12)

This step lands the **software side** of the YPCB-00338 Kintex-7 image: the
Vivado build flow, the LiteDRAM/self-calibration generation tools and the
Fedora DLC10/JTAG bring-up helpers, imported byte-identically from the product
tree (`ypcb/dual-channel-4gb` @ `ca05e24f`). The image build and the on-card
SRAM self-test are **hardware assertions** and stay blocked until the DLC10
cable and the card are attached — see
[`ladder/hardware/README.md`](../ladder/hardware/README.md) and the current
probe evidence below.

The imported files are listed with their SHA-256 in
[`ladder/hardware/import-provenance.json`](../ladder/hardware/import-provenance.json)
and re-checked by `ladder/tests/test_step12_hardware_gate.py` when hardware is
present.

## What was imported (95 files, byte-identical)

| Group | Paths | Purpose |
| --- | --- | --- |
| Board build flow | `boards/ypcb-00338/` (49 files) | `Makefile` (`bit`, `impl`, `program`, `program-vivado`, `flash`, `lint`, `sim-jtag`), Vivado Tcl (`vivado/build.tcl`, `create_project.tcl`, `core_clock.tcl`, …), constraints (`constraints/*.xdc`, `*.tcl`), the generated LiteDRAM core (`litedram/otpu_litedram.v`, `.xdc`, `_mem.init`), RAM-test builds and board simulations |
| LiteDRAM tooling | `tools/litedram/` (35 files) | core generation (`gen_core.py`), DRAM-PHY knobs, CSR/ECC helpers, the self-calibration firmware (`selfcal_fw/`) |
| Fedora bring-up helpers | `tools/fedora_bringup.sh`, `tools/fedora_prepare_xvc.py`, `tools/fedora_xvc_server.py`, `tools/fedora_jtag.py`, `tools/fedora_check_jtag_chain.py`, `tools/fedora_check_native_image.py`, `tools/fedora_prepare_litedram.py`, `tools/workspace_paths.py` | the actions in `ladder/hardware/README.md`: `program`, `program-vivado`, `jtag-server`, `xvc-build`, `build-vivado`, `jtag` |
| JTAG transport | `opentpu/host/__init__.py`, `opentpu/host/jtag.py` | the USER2/XVC transport used by `tools/fedora_jtag.py` and the XVC protocol tests |
| Reference doc | `docs/vivado_bitstream_guide.md` | the product tree's Vivado rebuild/audit guide |

Already present from step 9 (verified byte-identical, not re-imported):
`rtl/boards/ypcb-00338/` (10 SV files) and `sim/verilator/tb_board.sv`.

## Exact build commands (from the ladder tree root)

Vivado must be installed locally (`vivado` 2026.1, `xc7k480tffg1156-2`; a full
image is ≈1.5–4 h and runs under the shared-host lock). Nothing below is run
while the card is absent.

```sh
# 1. build the bitstream from this branch's tree (heavy: host lock + k10temp gate)
python3 ladder/run.py lock -- make -C boards/ypcb-00338 bit
#    variant knobs: TARGET=ypcb-00338:m4, MCOLS=4|8, CORE_MHZ=133.33|100, FAST=1,
#    PCIE_GEN=1|2 (see boards/ypcb-00338/Makefile and run_vivado.sh)
#    output: build/vivado/otpu.bit (SHA-256 recorded in the step-12 receipt)
#
# 2. (when the cable is attached) load it into volatile SRAM over DLC10 — never flash
BIT=build/vivado/otpu.bit bash tools/fedora_bringup.sh program
#
# 3. start the reviewed XVC server at 127.0.0.1:3721
bash tools/fedora_bringup.sh jtag-server
#
# 4. observe the on-card self-test / RAM test over JTAG (step-12 acceptance)
#    (the exact observer command is defined by the step-12 implementation and the
#     image's RAM-test hook; it does not exist until the cable is attached)
```

The old production path `.mcs`/`make flash` is **out of scope**: permanent
configuration-flash writes need an explicit per-image user approval
(`AGENTS.md`), and this rung only requires SRAM configuration.

## Repo rule: both runtime interfaces in every image

`AGENTS.md` requires every new bitstream to keep **both** the JTAG USER2 and
the PCIe runtime memory/control interfaces; a JTAG-only or PCIe-only image is
ineligible for packaging, programming or the hardware test plan. The step-12
image is built from the combined board top (`rtl/boards/ypcb-00338/`,
`otpu_fpga_top_ld.sv` + the shell), and the gate test checks the imported RTL
and package metadata for both interfaces.

## Current blocker (2026-11-10)

The DLC10 JTAG cable and the YPCB card are **not attached** on this host. The
read-only probe records the exact evidence; no build, program, flash or reset
was performed:

```sh
$ python3 ladder/hardware/probe.py --json
{ "status": "blocked", "exit_code": 3,
  "blocking_reasons": [{"reason": "jtag_cable_absent",
    "detail": "no 03fd:* DLC10 / 0403:6014 FT232H device in lsusb"}], ... }
```

The full probe JSON is committed with the receipt at
`ladder/evidence/hardware/probe-step12.json`; the step-12 receipt
(`ladder/evidence/step12.json`) records verdict `BLOCKED` (runner exit 5) —
never PASS. The hardware assertion resumes when the probe exits 0; then run
the build/SRAM/self-test sequence in
[`ladder/hardware/README.md`](../ladder/hardware/README.md) §3 and record the
receipt with the bitstream SHA-256, timing/DRC summary and source hashes.

## Known gaps (documented, not invented)

- **Host-local prerequisites outside the repo:** `vivado` 2026.1, the patched
  DLC10 openFPGALoader (`$YPCB_LOADER`, default
  `~/ypcb/openFPGALoader/build-xpcu-debug/openFPGALoader`), the cable
  initializer (`~/ypcb/dlc10-init.sh`) and the reviewed XVC binary/manifest
  (`build/fedora-openxc7/xvc-ready.json`). The ladder tree does not vendor
  them; the step-12 gate skips until they and the cable are present.
- **`bash tools/fedora_bringup.sh jtag ...`** needs a `--litedram-core`
  argument (or `OTPU_LITEDRAM_CORE`): without it the script's default
  `selected_core` reads product-tree build manifests
  (`build/fedora-openxc7/ddr800-pipeline-active.json`) that are not part of the
  ladder tree. The generated core from `tools/litedram/gen_core.py` is the
  ladder-side replacement.
- **openXC7-native actions** of `tools/fedora_bringup.sh` (`build`, `openxc7`)
  reference `tools/fedora_openxc7.py`, which is not imported here: this rung
  uses the Vivado flow. They arrive with the openXC7 path or at convergence
  (step 16).
- **`tools/fedora_check_native_image.py`** references an external
  `../bonetto-soc/scripts/fedora-check-vivado-bitstream.py` helper that is not
  in the product tree; the Vivado `make bit` path does not need it.
- The exact acceptance recipe for the on-card image is in
  [`ladder/hardware/README.md`](../ladder/hardware/README.md) §3–§4; the
  c0182902 package/model identities it pins are untracked local artifacts of
  the product tree (documented gap, step 15/16).
