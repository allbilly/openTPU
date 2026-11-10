# CH1 PCIe compute clock experiment

**Historical c0160150 experiment.** Current disposition is in
[HANDOFF.md](../HANDOFF.md); c0182800/c0182863 fixed-clock artifacts are retained
and the c01848 runtime-clock effort was abandoned. This older PCIe-only image
lacks JTAG runtime memory/control access. Its implementation commands below are
retired under the [combined-interface policy](../AGENTS.md#mandatory-interfaces-in-every-bitstream),
and this page does not schedule its programming or a new build.

This experiment requested 150 MHz compute while retaining the existing full
MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 accelerator, XDMA Gen2 x8, and CH1-only
2 GiB memory mapping. The generated DDR800 core is reused byte for byte from
[`bitstreams/ch1-pcie-2gb/core/`](../bitstreams/ch1-pcie-2gb/core/).

The current MMCM plan has an 800 MHz VCO and output-divider steps of 1/8.
Requesting 150 MHz selects divide 5.375: **148.837209 MHz actual**, represented
by `CORE_KHZ=148837`. The memory-controller user clock remains 100 MHz and the
physical DDR clock remains 400 MHz (DDR3-800). A higher compute clock does not
increase memory bandwidth by the same percentage.

BUILD_ID is `c0160150`; the CH1 memory marker at BAR0+`0x5c` remains
`0x08000102`. This image is experimental until physical memory, matmul and
LFM2 checks pass at its new clock. Low operating temperature alone does not
establish timing margin or correct results.

## Preserved local package

The built experimental image and matched host core are retained locally at
[`bitstreams/ch1-pcie-2gb-core150/`](../bitstreams/ch1-pcie-2gb-core150/).
This generated package is not supplied by a fresh Git clone.
SHA256 of `otpu.bit` is
`0e37ae05f1eabd3835acd8722b30ad35b1fa6292ffd19fef11bac365809ae423`.

The final strict numerical gate passed: setup `+0.003 ns`, hold `+0.018 ns`,
pulse-width slack `0.000 ns`, zero failing endpoints in all three categories,
and 322,651/322,651 routable nets complete with zero routing errors.
Independent packet/CRC, 278 board-reference pins, accelerator inventory,
implemented clocks and both PCIe OOB clock-mode reviews passed. Fresh CDC
review covers all 118 non-info findings, with the same crossing inventory as
the trusted 100 MHz reference. Ten exact routed CSR Gray-pointer groups and
all 49 original/additional skew assertions passed, minimum slack 2.984 ns.
The six memory-core files are byte-identical to the 100 MHz release.

This was an offline-reviewed SRAM candidate. Physical DMA, matmul and LFM2
operation at the faster clock, and external DDR pad timing, remain unqualified.
The small positive setup margin is not a physical performance result. The
unused global LiteX reset CSR at `R_MEMCAL+0x2000` must not be written; use
configuration reload or a power cycle for whole-design reset.

## Preserved implementation attempts

All attempts retained the full RTL, DDR800 core and requested clock. Their
directories are under `build/fedora-vivado/`:

| Directory | Final observation |
| --- | --- |
| `ch1-pcie-core150-20261016T100026Z` | Setup -0.165 ns, TNS -24.736 ns, 532 failures; hold +0.034 ns; rejected |
| `ch1-pcie-core150-postroute-v2-20261016` | Same final setup/hold; rejected |
| `ch1-pcie-core150-netdelay-20261016` | `ExtraNetDelay_high` placement and optimization improved setup to -0.023 ns, TNS -0.134 ns, 12 failures; hold +0.024 ns; rejected |
| `ch1-pcie-core150-setup-reroute-20261017` | Targeted reroute worsened setup; checkpoint restored; final -0.023 ns and 12 failures; rejected |
| `ch1-pcie-core150-no-relax-20261017` | `NoTimingRelaxation` route from the preserved placed/optimized checkpoint passed final timing; packaged |

The original worst path spent 4.356 ns of its 5.976 ns data delay in routing.
AMD documents the placement directive in
[UG835](https://docs.amd.com/r/en-US/ug835-vivado-tcl-commands/place_design)
and the routing strategy among
[7 Series implementation strategies](https://docs.amd.com/r/en-US/ug904-vivado-implementation/Implementation-Strategies-7-Series-UltraScale-and-UltraScale).
Vivado's exported Python environment prevented one numerical-gate invocation;
running that unchanged gate with system Python `-E` correctly rejected the
negative setup slack. No timing gate was relaxed.

The guarded `core150-extra-timing-followup-20261017` fallback ended with
`NO_RELAX_PASSED_NEW_PLACEMENT_SKIPPED`; no extra placement is running.
Fresh routed CDC/fan-in and pointer-skew evidence, plus the manual review,
are retained in `core150-cdc-followup-20261017/` and copied into the package.

## Historical build procedure on Linux

The commands in this section record the original workflow, not an executable
current build path. The legacy PCIe builder now rejects implementation before
creating outputs or invoking Vivado. Its `--prepare-only` mode retains source
preparation with `implementation_admitted=false`; it does not make this
single-interface design eligible for a build or programming. The retained
timing-continuation examples likewise do not authorize a new implementation.

The original workflow also requires unpublished local helpers:
`tools/fedora_optimize_vivado_pcie_timing.py`,
`tools/fedora_collect_pcie_cdc.py`,
`tools/fedora_check_litedram_csr_gray.py` and
`tools/fedora_package_ch1_compute.py`. The reference CDC report used below is
retained in the original local package; it is an input to reconstruction, not
an output available from a fresh clone. Preserve these dependencies and their
recorded hashes when inspecting the original receipts. Their presence does
not restore implementation admission.

Use full Vivado 2026.1 with XC7K480T device/license support, Python 3.11 or
newer, and Git. Loading an existing image on a Mac does not require Vivado;
building it requires the Linux Vivado installation. The pinned DDR core
avoids dependencies on LiteX/Migen, a RISC-V compiler, or the `~/ypcb` tree.
The independent image review also needs `g++` to build its CRC checker when
that executable is not already cached.

The historical invocation ran from the repository root with fresh outputs:

```bash
export VIVADO_ROOT="$HOME/vivado/2026.1/Vivado"
source "$VIVADO_ROOT/settings64.sh"

python3 tools/fedora_build_vivado_pcie_ddr800.py \
  --core bitstreams/ch1-pcie-2gb/core \
  --core-mhz 150 --build-id c0160150 \
  --out build/vivado/ch1-pcie-core150
```

The builder records requested and actual compute frequencies separately from
the memory clocks. It freezes all RTL and constraints, records their hashes
and the source diff, then runs synthesis and implementation with eight workers.
Use `--threads 2` to lower the worker/job limit when running concurrent builds.
The pre-bitstream gate requires complete routing, nonnegative setup/hold/pulse
slack, zero failing endpoints and no Error/Critical Warning DRCs. A timing
failure stops image generation; partial implementation is not a usable image.

Successful outputs include `project/otpu.bit`, matching BPI x16
`project/otpu.mcs`, `project/final-routed.dcp`, reports and `manifest.json`.
Build completion alone does not establish physical operation at the new clock.

If an attempt fails timing after preserving `project/final-routed.dcp`, a
fresh continuation can reuse that checkpoint without changing the failed
attempt or weakening its gates:

```bash
python3 tools/fedora_optimize_vivado_pcie_timing.py \
  --build build/vivado/ch1-pcie-core150 \
  --out build/vivado/ch1-pcie-core150-postroute
```

To place again from the original attempt's optimized checkpoint, use a new
output directory and the explicit directive:

```bash
python3 tools/fedora_optimize_vivado_pcie_timing.py \
  --build build/vivado/ch1-pcie-core150 \
  --placement-directive ExtraNetDelay_high \
  --out build/vivado/ch1-pcie-core150-netdelay
```

After a failed placement attempt has preserved `replaced-physopt.dcp`, route
that placed checkpoint again with the timing-focused directive:

```bash
python3 tools/fedora_optimize_vivado_pcie_timing.py \
  --build build/vivado/ch1-pcie-core150-netdelay \
  --route-directive NoTimingRelaxation \
  --out build/vivado/ch1-pcie-core150-no-relax
```

This mode is mutually exclusive with `--placement-directive` and
`--setup-reroute`. It requires a terminal failed parent and a fresh output
directory. It preserves the failed attempt and retains all strict gates.

This accepts only a terminal failed CH1 DDR800 implementation. It verifies
frozen sources and runs additional physical optimization, then fresh reports
and the same strict pre-bitstream gate. A failed continuation is still not a
programming artifact. Qualify its output directory separately if it succeeds.

## Historical independent-review procedure

These commands document the evidence workflow for a completed historical
implementation. Offline review helpers remain available, but a review pass
does not admit a new single-interface build or hardware operation.

```bash
python3 tools/fedora_qualify_ch1_image.py \
  --build build/vivado/ch1-pcie-core150 \
  --reference-release bitstreams/ch1-pcie-2gb \
  --core-khz 148837 --review-oob-clocks \
  --out build/vivado/ch1-pcie-core150-review
```

This checks the new packets/CRCs, board pins, full accelerator/DDR primitive
inventory, route, timing, implemented compute and memory clocks, and PCIe OOB
clock modes/bus skew. Historical ECC-model evidence is reused only when all
six packaged memory-core files are identical. It is recorded as historical;
the new compute clock still needs its own hardware checks. Read the fresh CDC
report and compare every critical crossing with the known 100 MHz image before
selecting the new image for programming. The qualification status retains
`CDC_REVIEW_PENDING` until that review is completed separately.

Collect the fresh routed evidence, using the reviewed 100 MHz release's
CDC report retained inside this package as the reference:

```bash
python3 - <<'PY'
import gzip, hashlib
from pathlib import Path
source = Path('bitstreams/ch1-pcie-2gb-core150/evidence/reference-100mhz-cdc.rpt.gz')
report = gzip.decompress(source.read_bytes())
assert hashlib.sha256(report).hexdigest() == '552c5e642980fd7ae4c8b8c82aeb64c75a8210115a484155162b765b74d222ab'
Path('build/vivado/reference-100mhz-cdc.rpt').write_bytes(report)
PY
python3 tools/fedora_collect_pcie_cdc.py \
  --build build/vivado/ch1-pcie-core150 \
  --qualification build/vivado/ch1-pcie-core150-review/manifest.json \
  --reference-cdc build/vivado/reference-100mhz-cdc.rpt \
  --out build/vivado/ch1-pcie-core150-cdc
python3 tools/fedora_check_litedram_csr_gray.py \
  --qualification build/vivado/ch1-pcie-core150-review/manifest.json \
  --out build/vivado/ch1-pcie-core150-gray
```

After the exact routed CDC collection and CSR gray-pointer review complete,
record a manual review covering every critical/warning row from the fresh
OOB CDC report. Each row needs an explanation based on its actual source,
destination, clock, synchronizers and timing exception. Preserve the ban on
the unused global reset CSR and the external-pad/physical qualification limits.
The dedicated compute packager requires that review and both bound evidence
manifests; its row-coverage checks reject omitted/duplicated findings:

```bash
python3 tools/fedora_package_ch1_compute.py --build build/vivado/ch1-pcie-core150 \
  --qualification build/vivado/ch1-pcie-core150-review/manifest.json \
  --cdc-review build/vivado/ch1-pcie-core150-cdc-review.json \
  --out build/packages/ch1-pcie-2gb-core150-reconstruction
```

Any reconstruction output must be a fresh directory; never replace the
preserved `bitstreams/ch1-pcie-2gb-core150/` evidence. The historical command
requires a completed matching image qualification, fresh CDC
collection, all ten CSR pointer groups and 49 original/additional passing skew
assertions. It retains all six memory-core files byte for byte from the
100 MHz release. It checks the generated MCS against the bitstream, and
packages the SRAM `.bit`, matched core and review evidence. It does not
program hardware or claim operation at the new compute clock. A queued
package command is not a ready image.

## Historical physical-comparison procedure

This comparison remains unqualified and is not in the current hardware plan.
The steps below describe the former candidate's interface and checks only.

Load the candidate `.bit` into volatile SRAM using a JTAG loader supporting
the XC7K480T. Use the same matched DDR800 `core/` directory. Keep the existing
100 MHz PCIe release available for recovery; use SRAM first for this experiment.
Chestnut supplies runtime PCIe access; FPGA configuration requires a separate
JTAG programming path. The Mac's exact loader has not been verified here.

After loading, require these identity registers:

| BAR0 offset | Register | Expected value |
| --- | --- | --- |
| `0x44` | CORE_KHZ | `148837` |
| `0x48` | BUILD_ID | `0xc0160150` |
| `0x5c` | Memory profile | `0x08000102` |

Run the same full-memory checks, DMA round trips, ISA-exact matmul, and LFM2
prompt/token comparison used for the 100 MHz baseline. Record ECC counters,
temperature, model/quantization/prompt, tokens and elapsed time for both images.
Use the actual clock register when converting device cycles to seconds.

The repository's Linux XDMA runner now accepts the expected compute frequency:

```bash
python3 tools/fedora_run_ch1_lfm2.py \
  --dev /dev/xdma0 --core bitstreams/ch1-pcie-2gb-core150/core \
  --core-khz 148837 --build-id c0160150 \
  --out build/results/ch1-pcie-core150-lfm2
```

That command also needs the existing LFM2 checkpoint and Python dependencies.
For the Mac, use the tracked `opentpu.host.chestnut.ChestnutTransport`, added in
`75fecaef`. After loading the candidate image, first check identity:

```bash
build/chestnut-lfm/venv/bin/python tools/fedora_run_ch1_lfm2.py \
  --chestnut \
  --core bitstreams/ch1-pcie-2gb-core150/core \
  --core-khz 148837 --build-id c0160150 --preflight-only \
  --out build/results/ch1-pcie-core150-identity
```

`--preflight-only` checks the image identity and releases the transport without
calibrating, running BIST, writing model data or doing inference. It needs the
matched core and transport dependencies, but not the model checkpoint. For the
full warm-memory, matmul and LFM2 comparison, remove `--preflight-only` and use
a fresh output directory. That full run writes test data and retrains CH1, so
inference must be stopped first.

An existing transport script can alternatively be selected with `--adapter PATH`.
If that script defines several transport classes, specify
`--transport-class ClassName`. The class must expose the register/memory/close
transport API and accept either no constructor arguments or `calibration_data`.
The original Mac-local `transport.py` and `run_lfm2.py` remain separate from
Git. The tracked Chestnut implementation and this runner remove that dependency.
The [100 MHz Mac benchmark receipts](chestnut_ch1_benchmarks.md) are now in Git;
physical inference at the new compute frequency remains pending.
