# Prepare and run an openTPU Vivado bitstream on Linux

An [independent CRC audit](openxc7_bitstream_crc.md) now verifies both CRC
checkpoints in each existing Vivado reference image, including the compressed
MIG image. The original files and frozen build receipts are preserved.

For exact locations and build differences, use the [bitstream index](bitstreams.md).
The separate [CH1 PCIe image](permanent_pcie_ch1.md) has now been written to
NOR, verified and booted through a JTAG boot request. Cold power-on boot and
PCIe inference remain to be tested with a physical PCIe connection.

For the successful LFM2 run, follow [CH1-only recovery](ch1_recovery.md):
the user selected a standalone JTAG image that bypasses physical CH0's errors.
Its bitstream completed implementation and all image checks, and was loaded
into FPGA SRAM for that run. CH1 warm memory, exact physical matmul and full LFM2 inference
passed. At October 15, 00:36 HKT, all eight hardware tokens matched the fresh
ISA reference: “The capital of France is Paris.” ECC stayed enabled and clean.
See the [audited physical result](../build/fedora-vivado/ch1-lfm2-physical-pass-current.json).
The older dual-channel images below
are historical references and still touch CH0, even for a small model.

This guide records the frozen inputs and batch stages that produced the earlier
Vivado reference images, plus their checking and loading commands.

Updated: October 16, 2026; the frozen reference procedures date from October 13.
Repository: `${OTPU_ROOT}`.
Run commands from the checkout root and set external tool locations as described
in [portable workspace paths](workspace_layout.md#portable-paths-and-external-tools).
The FPGA is an **XC7K480T-2, FFG1156**, on a YPCB-00338-1P1 card.

For the current CH0 investigation, start with the separate
[RAM-only MIG build and Mac test procedure](ddr_ram_only_debug.md). That image
isolates memory from the accelerator and PCIe; it is not an inference image.

## Rebuild the current CH1 PCIe release on Fedora

The built release lives in [`bitstreams/ch1-pcie-2gb/`](../bitstreams/ch1-pcie-2gb/).
Its `.bit`, matching BPI x16 `.mcs`, DDR800 core, calibration tables and
qualification receipts are included in Git. The source used for this release
is on `ypcb/ch1-bringup-local`; upstream `main` is a different design revision.

This is the complete accelerator: MCOLS4, ACT_ROWS4, LANES8, VPU_CL2,
MXU_IMPL2, 100 MHz core, DDR800 and XDMA Gen2 x8. Both logical channels use
physical CH1, with 1 GiB each and 2 GiB total. Physical CH0's PHY and diagnostic
CSRs remain present, but it carries no normal model traffic. This configuration
bypasses the unresolved CH0 lane-6 problem.

### Build from the shipped DDR800 core

Use Linux with full Vivado 2026.1 and device/license support for
`xc7k480tffg1156-2`, Git and Python 3.11 or newer. Vivado Lab alone cannot
synthesize or implement the design. This path uses the exact generated core
shipped with the release; Migen, LiteX, LiteDRAM, the RISC-V compiler, model
weights and the optional `~/ypcb` tooling tree are not build dependencies here.

Run from a clone of this branch on the Fedora build machine:

```bash
export VIVADO_ROOT="$HOME/vivado/2026.1/Vivado" # adjust for your installation
source "$VIVADO_ROOT/settings64.sh"
vivado -version

python3 tools/fedora_build_vivado_pcie_ddr800.py \
  --core bitstreams/ch1-pcie-2gb/core \
  --out build/vivado/ch1-pcie-rebuild
```

Choose a fresh `--out` directory for each attempt. The helper checks the core's
hashes, complete port/CPU ABI, DDR800 parameters, CH1 address mapping and
capacity. It snapshots the full RTL and constraints, adds the CH1 recovery
marker `0x08000102` at register `0x5c`, creates the XDMA project, and runs full
synthesis and implementation with eight workers. It neither connects to the
card nor programs SRAM or NOR. The release's old source BUILD_ID value is kept
by default; `--build-id` selects a distinct hexadecimal value for experiments.

For a source preparation check before a long build, use `--prepare-only` with
a different fresh output directory. This creates the snapshot and manifest;
it does not run implementation. The actual historical PCIe build took about
2 hours 23 minutes including project/IP preparation. Runtime varies with the
machine and implementation result.

Expected outputs:

```text
build/vivado/ch1-pcie-rebuild/
  manifest.json                  status, source hashes and actual stage exits
  source/                        frozen RTL, generated DDR core and constraints
  create.command.json / create.log / create.exit
  build.command.json / build.log / build.exit
  project/otpu.bit               FPGA SRAM configuration
  project/otpu.mcs               matching BPI x16 NOR programming image
  project/final-routed.dcp       implemented design checkpoint
  project/pre-bit-gates.json     numerical timing and routing checks
  project/reports/               timing, route, DRC, CDC and other reports
```

A completed build requires zero `create.exit` and `build.exit`, manifest status
`FULL_NATIVE_VIVADO_PCIE_CH1_RECOVERY_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING`,
all routable nets fully routed, zero routing errors, nonnegative setup/hold/pulse
slack and no failing endpoints. The Tcl gate rejects Error/Critical Warning
DRCs before bitstream generation. Fresh pin, packet/CRC, CDC and bus-skew
reviews are still required for the new output, followed by hardware tests.
The preserved release's receipts describe its original files; they do not
qualify a rebuild. A rebuild may produce different bytes and hashes.

### Regenerate the CH1 DDR core when changing the PHY

Only PHY/controller experiments need this step. Use the versions pinned by
[`boards/ypcb-00338/litedram/core.json`](../boards/ypcb-00338/litedram/core.json):

```bash
python3.11 -m venv build/litedram-env
build/litedram-env/bin/python -m pip install \
  'git+https://github.com/m-labs/migen@e19524c963a8342952840983047557707fbe0b6a' \
  'git+https://github.com/enjoy-digital/litex@fad9b3759f24a877a71925b7fcfc8b6748c97d62' \
  'git+https://github.com/enjoy-digital/litedram@7b28f53b1f4c1732b4b503a844a4d5a0cc56416b' \
  pythondata-cpu-vexriscv==1.0.1.post407 \
  pythondata-software-compiler-rt==0.0.post6206 \
  pythondata-software-picolibc==1.7.9.post181 PyYAML==6.0.3 pyserial==3.5
```

Supply an installed GCC toolchain supporting `-march=rv32i -mabi=ilp32`,
including the matching libgcc, objcopy and objdump. The three executables must
share a prefix and directory. A toolchain without RV32I/ILP32 runtime support
cannot link this calibration CPU's firmware. If using a container-backed
compiler, mount the selected output directory writable in that container.

```bash
python3 tools/fedora_prepare_ch1_recovery.py \
  --python "$PWD/build/litedram-env/bin/python" \
  --rv-cc /path/to/toolchain/bin/riscv64-unknown-elf-gcc \
  --out build/vivado/ch1-new-core

python3 tools/fedora_build_vivado_pcie_ddr800.py \
  --core build/vivado/ch1-new-core/core \
  --out build/vivado/ch1-new-core-pcie
```

The preparation command copies the generator, includes its matching host CSR
parser, tests the four-port ECC adapter, builds the real calibration firmware,
and checks the generated CSR/port ABI and firmware capacity. Its manifest must
report `CH1_RECOVERY_CORE_AND_FOUR_PORT_ECC_PASS_IMPLEMENTATION_PENDING` before
starting the board build. It preserves the reference embedded CPU when the
packaged CPU data differs while the complete CPU port ABI matches.

### Isolated serializer-reset experiment for CH0

The current release already contains static read clocks, per-bit read framing
and a serializer reset register per pad. Upstream commit
[`f2d1023d`](https://github.com/FeSens/openTPU/commit/f2d1023ddded0a4d70b8810a715e173ea989efd7)
adds a sys-clock register before those reset paths. The
[isolated patch](../boards/ypcb-00338/experiments/ch0-serializer-reset.patch)
changes that one PHY input stage. It is a timing candidate, not a proven CH0
repair. It does not appear in the current release images.

For a new experiment, make an isolated source checkout of this documented
revision, apply that patch there, regenerate the CH1 DDR800 core as above, then
build the complete PCIe image using the new core and `--build-id c0160001`.
With the pinned environment and an RV32I/ILP32 compiler installed:

```bash
export OTPU_CHECKOUT="$PWD"
export OTPU_EXPERIMENT="$PWD/build/ch0-reset-experiment"
export OTPU_RV_CC="/path/to/toolchain/bin/riscv64-unknown-elf-gcc"
mkdir "$OTPU_EXPERIMENT"
git worktree add --detach "$OTPU_EXPERIMENT/source" HEAD
git -C "$OTPU_EXPERIMENT/source" apply \
  "$OTPU_CHECKOUT/boards/ypcb-00338/experiments/ch0-serializer-reset.patch"

python3 "$OTPU_EXPERIMENT/source/tools/fedora_prepare_ch1_recovery.py" \
  --python "$OTPU_CHECKOUT/build/litedram-env/bin/python" \
  --rv-cc "$OTPU_RV_CC" --out "$OTPU_EXPERIMENT/memory"

python3 "$OTPU_EXPERIMENT/source/tools/fedora_build_vivado_pcie_ddr800.py" \
  --core "$OTPU_EXPERIMENT/memory/core" \
  --build-id c0160001 --out "$OTPU_EXPERIMENT/pcie"
```

Preserve the known working release as a fallback. Before testing on the Mac,
qualify the experiment's own implementation, image integrity and constraints.
The retained physical CH0 calibration/BIST CSRs allow raw CH0 tests even though
normal logical channel 0 transfers go to physical CH1 in this recovery design.

The independent image checker uses the packet parser and CRC source included
in `tools/`. A GNU C++ compiler is needed if the local CRC executable is not
already available. For a freshly generated experiment:

```bash
python3 tools/fedora_qualify_ch1_image.py \
  --build "$OTPU_EXPERIMENT/pcie" \
  --generation "$OTPU_EXPERIMENT/memory" \
  --ecc-preparation "$OTPU_EXPERIMENT/memory" \
  --expect-serializer-reset-stage --review-oob-clocks \
  --out "$OTPU_EXPERIMENT/qualification"
```

This checks the actual implemented reset registers as well as source hashes,
the full ECC comparison, packet/CRC, pins, routing and numerical timing.
`--review-oob-clocks` adds analysis clocks covering both divide-by-2/divide-by-4
modes for both PCIe master frequencies on all eight lanes. It checks internal
clock coverage, pulse clocks and all 39 bus-skew constraints without modifying
the netlist or routing. Raw and modeled reports are saved separately.
Its success status still leaves fresh CDC and interface-constraint review
pending; the checked in release's final review cannot qualify a different
implemented design.

### Prepare the full dual-channel follow-up

The recovery image's normal model traffic uses physical CH1. A raw CH0 BIST
pass therefore needs a subsequent image that uses both physical channels for
normal host/compute traffic. From the same isolated patched source checkout,
prepare that core with the pinned environment and compiler from above:

```bash
python3 "$OTPU_EXPERIMENT/source/tools/fedora_prepare_litedram.py" \
  --python "$OTPU_CHECKOUT/build/litedram-env/bin/python" \
  --rv-cc "$OTPU_RV_CC" --out "$OTPU_EXPERIMENT/dual-memory"

python3 "$OTPU_EXPERIMENT/source/tools/fedora_build_vivado_pcie_ddr800.py" \
  --core "$OTPU_EXPERIMENT/dual-memory/core" \
  --build-id c0160002 --prepare-only --out "$OTPU_EXPERIMENT/dual-prepare"
```

This prepares two physical 72-bit channels with ECC, 2 GiB per channel and
4 GiB total, while keeping the full accelerator and 100 MHz / DDR800 profile.
The calibration mask is 3, each normal channel has its own physical ready
flag, and the CH1 recovery marker is absent. Inspect those fields in the
preparation manifest. The command does not implement or program an image.
After CH0 passes raw cold/warm testing, select another fresh output directory
and omit `--prepare-only` to launch the full PCIe build. Its 4 GiB image review,
memory/compute tests and inference results must be saved separately; the
CH1-only qualification cannot establish dual-channel operation.

### Load a completed image from macOS

Copy or pull the release directory, then verify it with macOS's built-in tool:

```sh
cd bitstreams/ch1-pcie-2gb
shasum -a 256 -c SHA256SUMS
```

Use `otpu.bit` with the already working Mac JTAG/SRAM programmer. It must
support the cable and XC7K480T, detect raw IDCODE `0x23751093`, and verify
configuration completion. Vivado is needed on Fedora to build a changed
design; it is not needed on macOS to send an existing bitstream through a
working programmer. The `.mcs` targets the board's parallel BPI x16 NOR;
permanent programming requires additional flash-device and verification
support in the Mac tool. The Chestnut PCIe runtime transport is separate.

Set the inference transport's `calibration_data` to the matching release's
`core/`. After power loss, upload model weights again into volatile DDR.
Use a new experiment's own `core/` when testing that image.

## 1. Choose the correct image

| Image | Compute configuration | Memory | Evidence |
| --- | --- | --- | --- |
| CH1 Vivado JTAG, tested LFM2 image | MCOLS4, ACT_ROWS4, LANES8, VPU_CL2, MXU_IMPL2; 100 MHz | Healthy physical CH1 only, 2 GiB usable, DDR800, ECC | SRAM/calibration/full-capacity soak, exact matmul and eight-token exact LFM2 inference passed; final ECC counters zero |
| CH1 Vivado PCIe, stored in NOR | Same compute dimensions and 100 MHz; Gen2 x8 XDMA host | Same CH1-only 2 GiB DDR800 core with ECC | Offline review, permanent flash programming, separate verification and JTAG-requested flash boot passed; cold boot/PCIe inference pending |
| Vivado MIG JTAG | MCOLS4, ACT_ROWS4, LANES8, VPU_CL2, MXU_IMPL2; 100 MHz; 716 DSPs | Two 2 GiB DDR3-1066 channels with ECC | SRAM programming, full 4 GiB memory tests and basic compute passed on the FPGA |
| Matched Vivado LiteDRAM reference | Same compute dimensions and 100 MHz; 717 DSPs | Dual DDR3-800 LiteDRAM | Full implementation, timing, pin and packet checks passed; this image has not been tested on the FPGA |

Current qualified standalone image:

```text
build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit
```

Size: 12,484,177 bytes. SHA256:

```text
0fc10bf2a6459ca5273b0dc6616e43974209ff0176fa2b95e017626e03f93d21
```

[Current physical run](../build/fedora-vivado/ch1-jtag-lfm2-current.json) records
the selected image and exact service/command. That service completed with exit
status 0. This standalone image uses USER2 JTAG for model I/O. The separate
PCIe build and its matching `.mcs` have now been permanently programmed; use
the [PCIe flash guide](permanent_pcie_ch1.md) for that result and the pending
PCIe host test. The `.mcs` is the flash representation of the PCIe `.bit`.

MIG means **Memory Interface Generator**, AMD/Xilinx's memory-controller and
PHY IP. Here it initializes, calibrates and accesses the external DDR3 memory.
See [AMD's MIG guide](https://docs.amd.com/r/en-US/ug586_7Series_MIS).

The tested MIG image is:

```text
build/fedora-vivado/mig-jtag-controller-20261010T235833Z/
  implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit
```

Its size is **12,870,600 bytes** and SHA256 is:

```text
0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f
```

The [physical results](fedora_vivado_jtag_results.md) provide the test receipts.
The complete selftest and physical LFM2 inference remain unfinished: USB/JTAG
disconnected during vector tests, before stream and model checks. The older
README inside the frozen candidate describes earlier build stages; use these
current results when deciding what has passed.

## 2. Set up the tools and check the existing image

Use full Vivado, rather than the separate Vivado Lab installation:

```bash
# Run from the root of your OpenTPU checkout.
source "${VIVADO_ROOT}/settings64.sh"
vivado -version

OTPU_MIG_REF="$PWD/build/fedora-vivado/mig-jtag-controller-20261010T235833Z"
OTPU_AUDIT="$PWD/build/fedora-vivado/mig-audit-$(date -u +%Y%m%dT%H%M%SZ).json"
python3 "$OTPU_MIG_REF/check_candidate.py" --out "$OTPU_AUDIT"
```

Expected result: actual exit **0** and
`PASS_MIG_NATIVE_IMAGE_OFFLINE_AUDIT`. This check accesses no FPGA. It verifies
frozen sources/IP/runtime witnesses, the exact bitstream, complete routing,
timing coverage, pins, clocks, configuration, CDC and warning reviews.
It passed again during this documentation update:
[fresh audit](../build/fedora-vivado/documentation-audit-20261013T104657Z/result.json).

The tested build has all **290,292 routable nets** routed, zero routing errors,
setup WNS **+0.235 ns**, hold WHS **+0.026 ns**, and pulse WPWS **+0.264 ns**.
Its audit checks **247 top-level pins/standards**. These values belong to the
MIG image; the matched LiteDRAM reference has a different port count.

## 3. Rebuild the successful frozen MIG design, when needed

These are the same parameterized Tcl stages and final frozen inputs used for
the successful build. The example prepares a **new output directory**, keeping
the tested reference intact. This fresh rebuild was not rerun while writing
the guide. A newly built image needs its own signoff and receipts.

Run another substantial build after the current OpenXC7 attempt finishes:
earlier concurrent routes exhausted the host's RAM and swap.

```bash
# Run from the root of your OpenTPU checkout.
source "${VIVADO_ROOT}/settings64.sh"
OTPU_MIG_REF="$PWD/build/fedora-vivado/mig-jtag-controller-20261010T235833Z"
OTPU_VIVADO_BUILD="$PWD/build/fedora-vivado/mig-rebuild-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir "$OTPU_VIVADO_BUILD"
cp -a "$OTPU_MIG_REF/source" "$OTPU_MIG_REF/constraints" "$OTPU_VIVADO_BUILD/"
for name in otpu_mig_ddr3.prj expected-port-constraints.tsv generate-ip.tcl \
            synthesize.tcl implement.tcl audit-checkpoint.tcl threads.tcl; do
  cp "$OTPU_MIG_REF/$name" "$OTPU_VIVADO_BUILD/$name"
done

otpu_vivado_stage() {
  local receipt="$1" script="$2" code=0
  vivado -mode batch -nojournal \
    -log "$OTPU_VIVADO_BUILD/$receipt-vivado.log" \
    -source "$OTPU_VIVADO_BUILD/$script" \
    -tclargs "$OTPU_VIVADO_BUILD" || code=$?
  printf '%s\n' "$code" > "$OTPU_VIVADO_BUILD/$receipt-command.exit"
  return "$code"
}

otpu_vivado_stage ip-generation generate-ip.tcl && \
otpu_vivado_stage synthesis synthesize.tcl && \
otpu_vivado_stage implementation implement.tcl
```

What the stages do:

1. **IP generation:** generate MIG 4.2 for both DDR3-1066 ECC channels from
   the preserved board XML. The supplied board profile's AXI interface was
   changed to native for this adapter; its DDR pin mapping was retained.
2. **Synthesis:** build `otpu_fpga_top_vivado_mig_jtag` from the frozen RTL,
   preserve the full compute dimensions, and save `synth.dcp`.
3. **Implementation:** load the corrected late memory/CDC constraints,
   use `Performance_ExplorePostRoutePhysOpt`, route, write the bitstream,
   and export `routed.dcp` and `reports/`.

The scripts request **eight jobs** and `general.maxThreads=8`. Vivado stages
have different amounts of parallel work, so eight continuously busy cores
are not a completion criterion. In the successful MIG run, synthesis took
about **16 minutes** and implementation/export about **33 minutes**, excluding
IP preparation, earlier failed attempts and independent reviews.

The resulting bitstream path is the same relative path as the tested image:

```text
implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit
```

Preserve the final corrected `constraints/otpu_mem_ch.tcl`. It resolves the
host clock from the actual synthesized FIFO clock pin; the historical
`otpu_mem_ch.before-shared-clock-fix.tcl` is not the build constraint.
The frozen source also includes the explicit input-net and declaration-order
fixes that allowed Vivado synthesis to complete.

For a rebuild, require exit 0, complete routing, no DRC errors, nonnegative
setup/hold/pulse margins, the full pin/clock/profile audit, and fresh CDC and
warning coverage. Save source/IP hashes, bitstream hash and final reports.
The existing `check_candidate.py` is deliberately tied to the original
reference and its witnesses; copying an old passing JSON receipt does not
qualify a rebuilt image.

The repository's general `make bit` flow in `boards/ypcb-00338` builds the
upstream LiteDRAM/PCIe design. Its default core clock is 133.33 MHz and DDR
profile is 1066. It is a separate recipe from this tested standalone
100 MHz MIG JTAG image.

## 4. Load the tested image and finish hardware validation

For the separately powered card, **JTAG is sufficient** for programming,
commands, data upload and result readback. PCIe is unnecessary for this
workflow. Serial JTAG model transfers can take hours.

```bash
# Run from the root of your OpenTPU checkout.
lsusb
OTPU_HW_RUN="$PWD/build/fedora-vivado/mig-hardware-$(date -u +%Y%m%dT%H%M%SZ)"
python3 tools/fedora_finish_vivado_jtag.py \
  --xvc-manifest build/fedora-openxc7/xpcu-xvc-20261011T165026Z/manifest.json \
  --wait-usb 300 \
  --out "$OTPU_HW_RUN"
```

The helper waits for one Xilinx cable, repeats the exact image audit, checks
one FPGA with IDCODE **0x23751093 / IR length 6**, and loads **volatile SRAM**.
It requires INIT/DONE, starts the qualified localhost XVC server on port 3721,
checks identity, and runs the normal selftest with LFM2, int8 weights and
eight output tokens. It owns and closes the cable/server; it writes no BPI
flash and changes no bench-supply setting.

Success requires actual exit **0**,
`PASS_FULL_PHYSICAL_SELFTEST_AND_LFM2`, and a nonempty `model_checks` array
whose rows all have `exact_match=true`. DDR calibration, full scrub, vector,
stream and compute checks must pass before model execution. Keep failure
receipts when USB disappears; a completed bitstream build does not prove
these physical tests passed.

Current hardware status: no Xilinx adapter is detected by Fedora. USB
reconnection is the next requirement for running these commands successfully.
See [DLC10 USB investigation](dlc10_usb_stability.md).

## 5. Use the matched reference for OpenXC7 comparison

The separately implemented DDR800 reference is:

```text
build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/
  full-mapped-reference.bit
```

Its [manifest](../build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/manifest.json)
records all **397,867 routable nets** routed, WNS **0.000 ns**, WHS
**+0.034 ns**, WPWS **+0.264 ns**, and the full image provenance. Implementation
through final bitstream took about **2h49m**, including timing-closure passes.
This is a completed Vivado image, not an OpenXC7 result or physical test pass.

Continue with the [OpenXC7 bitstream plan](openxc7_bitstream_plan.md) and the
live [progress table](../progress.md).

## Historical guarded hardware continuation, October 13

The existing complete-test helper now runs in a separate user service, with
a 24-hour USB wait from 21:36 HKT. It polls every five seconds and uses the
previously tested MIG bitstream and the separately qualified XVC candidate.
When exactly one Xilinx USB adapter appears, the programmer repeats its
offline image audit and exact YPCB chain check before volatile SRAM loading.
It then runs normal selftest, including vops/stream, and the physical LFM2
int8 eight-token comparison against the ISA result. Flash is untouched.

```bash
systemctl --user status opentpu-vivado-hardware-resume-20261013t134000z.service
cat build/fedora-vivado/physical-jtag-resume-20261013T134000Z/manifest.json
```

[Hardware continuation receipt](../build/fedora-vivado/physical-jtag-resume-20261013T134000Z/manifest.json).
This watcher later terminated before programming when initialization found no
cable. Its receipt is preserved; it is no longer the cable owner. At startup no cable was visible, no programming
command had started, and status was `WAITING_FOR_USB`. The service has an
8 GiB memory limit and 2 GiB swap limit, with all CPUs available. A later
`PASS_FULL_PHYSICAL_SELFTEST_AND_LFM2` receipt must include native test exits
of zero and nonempty model checks with `exact_match: true`. A running watcher
is not a physical-test pass.

## Current hardware diagnosis, October 14

The [fresh physical attempt](../build/fedora-vivado/physical-jtag-resume-20261014T041625Z/manifest.json)
loaded the same image successfully and passed physical identity/calibration
checks, but failed the normal DDR scrub on channel 0. Compute and inference
were not reached. [Targeted checks](../build/fedora-vivado/mig-readback-debug-20261014T042746Z/manifest.json)
then found channel 0 failures concentrated in one data-byte position while
channel 1 passed all tested patterns/regions.

That trial is terminal after a USB dropout during the host pattern stage.
Its cable owner was `opentpu-mig-readback-retrain-20261014t042940z.service`. Its
[receipt](../build/fedora-vivado/mig-readback-retrain-20261014T042940Z/manifest.json)
records a guarded SRAM reload of the unchanged reference image followed by
targeted diagnostics, full memory checks and normal selftest in that order.
Later stages run only if the earlier gates pass. Do not start another cable
client while it is active. See the [dated physical results](fedora_vivado_jtag_results.md).

The same-image reload recovered the current failure: 24 targeted pairs, all
16 full-memory passes and the normal full scrub passed with zero errors.
The complete selftest subsequently stopped on USB loss. Recovery by reloading does not prove stable
training across future boots. The new diagnostic helper preserves pre-clear
counters and rejects any failed memory gate before starting compute:

```bash
# Run from the root of your OpenTPU checkout.
build/fedora-venv/bin/python -u tools/fedora_debug_vivado_mig.py \
  --out build/fedora-vivado/NEW_UNIQUE_RECEIPT_DIRECTORY \
  --xvc-manifest build/fedora-openxc7/xpcu-xvc-20261011T165026Z/manifest.json \
  --reload --full-after-small --selftest-after-full
```

This is the command pattern for a future session. Choose a new output
directory and ensure the current cable owner has exited before running it.
It reuses the frozen bitstream and checks the expected physical identity;
it does not rebuild the image, change clocks or write flash.

### Native Vivado-driver comparison

A read-only native chain/mailbox probe passed, but a later native-driver
full-memory trial reproduced channel 0 errors. That retry failed during legacy-loader SRAM upload. Its owner was
`opentpu-native-jtag-retrained-fulltest-20261014t044514z.service`; its
[receipt](../build/fedora-vivado/native-jtag-retrained-fulltest-20261014T044514Z/manifest.json)
records a fresh guarded SRAM reload followed by native-driver memory, compute
and model gates. Full-profile clocks remain unchanged. Future sessions can
use the tested native helper after the current cable owner exits:

```bash
# Run from the root of your OpenTPU checkout.
source "${VIVADO_ROOT}/settings64.sh"
build/fedora-venv/bin/python -u tools/fedora_run_vivado_native_jtag.py \
  --out build/fedora-vivado/NEW_UNIQUE_NATIVE_RECEIPT_DIRECTORY --reload
```

The helper starts and cleans up only its own native hardware server/Vivado
processes. It does not clear ECC counters, bypass memory checks or write flash.
A clean memory gate is still required before compute; changing the host driver
is not a demonstrated repair for the DDR fault.

The current sole owner is
`opentpu-native-vivado-fulltest-20261014t045031z.service`, with
[receipt](../build/fedora-vivado/native-vivado-program-and-fulltest-20261014T045031Z/manifest.json).
The helper's `--reload` now performs the frozen offline audit, one-device/raw
IDCODE check and SRAM load entirely through native Vivado, followed by explicit
INIT/DONE and USER2 checks before memory tests. Its `--wait-usb` option can
wait for two consecutive stable USB samples. Ten wire/Tcl guard fixtures pass;
physical native-programming qualification is still pending. It keeps all
FPGA clocks and the full compute/DDR profile unchanged and never writes flash.

## Current full-profile DDR800 test and later PCIe boot

Native MIG programming passed INIT/DONE, but memory errors recurred after
calibration. The [current DDR800/native-driver session](../build/fedora-vivado/ddr800-native-matmul-lfm2-20261014T051843Z/manifest.json)
uses the completed full-compute Vivado LiteDRAM reference after checking
image/source pins, PHY tables, timing witnesses and both CRC checkpoints.
It tests full memory, a compact physical MM comparison, and the complete
normal selftest/LFM2 path in that order. Core frequency and compute sizes
remain unchanged; DDR800 is the previously selected full LiteDRAM profile.

The user's later permanent-flash authorization is conditional on physical
LLM inference passing. Their PCIe host is another PC. Neither JTAG-only
bring-up bitstream can enumerate as a PCIe device after flashing: build and
qualify a PCIe-capable full image, verify its physical behavior and the actual
flash/boot profile, then perform that authorized permanent operation.
No flash command has run during the current tests.
