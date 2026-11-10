# Pipelined CH0: full 4 GiB performance candidate

**Historical failed c0172300 image.** Mac LFM stopped with 3,161 CH0 program
word mismatches; CH1 matched. The combined-interface c0182800/c0182863 repairs
later passed their own Mac tests. c0172462 was rejected and the c01848
runtime-clock effort was abandoned. See the
[tested builds and outstanding tests](bitstreams.md#tested-builds-and-outstanding-tests)
and [c0172300 failure record](mac_c0172300.md).
The source/review and programming snapshots below preserve October 17 history;
their old queues and pending checks are not an active hardware plan.
The generated package and build receipts linked below remain local artifacts;
they are not delivered by this documentation publication.

Build `c0172300` retains 100 MHz compute, DDR800, the full OpenTPU compute
profile and both 2 GiB channels. CH0 uses physical lanes `0,1,2,3,4,5,8,7`
without ECC; CH1 retains ECC. Its bitstream and independent artifact/CDC
reviews have passed, and the experimental package is available at
[`bitstreams/spare-pcie-4gb-pipeline-ddr800/`](../bitstreams/spare-pcie-4gb-pipeline-ddr800/).
The later Mac failure supersedes the original pending physical status. At the user's
request, the original-adapter 148.84 MHz/DDR800 routing and its waiting review
jobs were stopped. The two unstarted DDR1066 variants with that adapter were
also removed from the queue. Their files and 22 saved implementation
checkpoints remain preserved. The combined JTAG/PCIe c0172462 implementation
had finished and its independent review was running at that snapshot. Baseline
c0172800, faster-compute c0172450 and faster-RAM c0172461 were implementing;
the superseded c0172400 has been retired from the active plan. See
[the combined-host builds](ddr_spare_dual_host.md).
Each image requires its own review and qualification.

## Historical c0172300 hardware handoff

The user requested switching from temporary ET-SOC work to this ready image
and testing PCIe/inference on the Mac after permanent programming. ET-SOC's
tests have exited and released JTAG. The exact c0172300 image loaded into SRAM
with INIT=1, DONE=1 and physical FPGA IDCODE `0x23751093` on October 17.
Its BPI16 MCS was independently compared with the packaged bitstream; it has
one image at offset zero, the expected FPGA IDCODE and no IPROG command.
Permanent programming/verification, a separate verification pass and JTAG
boot all passed at 22:39 HKT under
`build/fedora-vivado/spare-pipeline-c0172300-flash-20261017/`. INIT/DONE were
asserted after boot, and JTAG was released. At that October 17 handoff the card
was ready to move to the Mac; the subsequent LFM failure is recorded above.
The exact historical transfer receipt is
`build/handoffs/c0172300-ready-for-mac-20261017.json`.

This is the explicitly authorized experimental flash-then-test-on-Mac path.
It does not require PCIe DMA or LLM validation on the JTAG-only build host.
No old-flash backup is taken, following the user's existing preference.
Mac cold boot, CH0 calibration, DMA, matmul, reference inference and measured
bandwidth remain separate pending results. A cold power-cycle boot has not
yet been observed; it is part of the Mac handoff rather than the completed
JTAG-initiated boot.

The later [Git runtime handoff](mac_c0172300.md) supplies the matching small
host/calibration files for a card already carrying c0172300; no bitstream,
generated core or archive transfer is required. Older local transfer artifacts
remain historical evidence. Do not publish their generated image contents.
The command below records the failed image's workflow, not a requested rerun:

```bash
SPARE_PYTHON=/path/to/existing/python \
SPARE_MODEL=/path/to/LFM2/checkpoint \
SPARE_OUT=build/mac-c0172300-lfm-1 \
bash tools/mac_spare_c0172300.sh lfm
```

Use a fresh `SPARE_OUT`. The command checks identity, calibrates CH0,
initializes memory, checks matmul and compares LFM2 with its reference.
Keep all result manifests even if a step fails. Device bandwidth should then
be compared with c0172080 at matching workload settings; USB wall time is a
separate measurement. This procedure starts no additional standalone RAM soak.

## Read adapter change

`spare_native_pipeline.py` (local-only `tools/litedram/spare_native_pipeline.py`)
keeps both CH0 raw ports active. Each user has a queued command path and
32 response credits. A credit is reserved at command acceptance and released
only when the user consumes its data. Raw DRAM responses are never stalled.
A pending write stops new reads and drains both read pipelines. Full writes
and partial read/merge/write operations then run exclusively across both users.
Raw BIST must remain idle during native traffic.

Eight native-interface simulations passed, including each port alone, dual
streams, prolonged response backpressure, independent command/data stalls and
mixed writes to shared addresses. Returned payloads, full-width physical writes
and final memory matched exactly. With fixed 24-cycle raw latency, the same
512-read model workload took 14,341 cycles on the original adapter and 546
on the pipeline. This is protocol evidence, not a physical bandwidth prediction.

The first checker run hit pinned Migen's unsupported write-only FIFO RAM read
destination. The failure is preserved. The passing checker adds unused read
destinations only to its simulation fragment; generated hardware is unchanged.
The passing receipt is `build/checks/spare-native-pipeline-v2-20261017/manifest.json`.

## Build and boot behavior

The generated CSR map, both DDR initialization files and startup memory bytes
match the reviewed DDR800 reference. `tools/prepare_spare_pipeline_pcie.py`
freezes the new full-image driver and records its command and source hashes
under `build/fedora-vivado/spare-full-pcie-pipeline-20261017/`.
An initial copied-driver import failure was corrected in a new driver; the
failed manifest and original command remain preserved. No regeneration or
modification of the validated core was needed for that import correction.

**This candidate still starts with CH1-only calibration firmware `c0172060`.**
It uses nine-lane boot firmware with channel mask `cfg & 2`. CH0 still needs
the eight-lane `c0172068` host helper after configuration. Automatic mixed-width
startup for eight-lane CH0 and nine-lane CH1 is a separate firmware integration
and is not included in this build.

Routing/timing/pulse/DRC, CRC, pads/phase/reset, CDC/Gray review, packaging and
new exact-image host binding remain required. Then compare Mac correctness and
device bandwidth with the original at identical clocks, model, prompt and
token count. Record the reported 1.55 seconds/token of extra host/USB work
separately from device time. Keep the working baseline available for recovery.

## Review preparation and current checkpoint

Synthesis, main routing and targeted PCIe timing cleanup completed on October
17. The bitstream and independent review/package are now complete: 100% of
the five offline build milestones. Physical performance remains pending.
Final setup slack is +0.044 ns and hold slack
is +0.022 ns, with no failing endpoints or routing errors. The 13,309,211-byte
`implementation/project/otpu.bit` has SHA-256
`669a7382ff9f9f1391b163ff0fcd5971ded8e378d7668c737c1692819a1323aa`.
The new exact-ID artifact and CDC collectors are
prepared under `build/checks/spare-pipeline-review-v2-20261017/`. The review unit
has passed the exact completed-build dependency and is collecting numerical
timing/route, phase/reset/pad, packet/CRC, CDC fanin and Gray-pointer skew
evidence sequentially. It does not grant CDC approval or access hardware.

That evidence collection has now completed. The exact disposition accounted
for all 116 non-information CDC rows, preserving the source-proven FIFO
storage mapping and both unused-reset fanins. All 49 skew checks passed with
minimum slack +2.594 ns. The generated exact-image packager independently
accepted the evidence, and every one of the package's 88 checksums was then
verified. This approves the documented offline operating scope, including the
unused-reset restriction; it is not measured pipeline throughput or a physical
DDR timing qualification. No hardware or permanent flash was changed.

The preliminary source comparison resolved the five CSR FIFO RAMs from their
actual consumers. It matched all 512 selected FIFO lines, 50 synchronizer
lines and five complete width/depth/storage blocks after a checked one-to-one
RAM-name substitution. The mapping is recorded in
`build/checks/spare-pipeline-source-preliminary-20261017.json`. The subsequent
exact routed disposition is now in the completed package's evidence directory.

`tools/prepare_spare_pipeline_review.py` prepares the exact collectors;
`tools/run_spare_pipeline_review.py` runs the gated sequence;
`tools/collect_spare_pipeline_cdc_source.py` records the selected source
contracts. Use fresh output directories for each attempt. Preserve failures
and the original checkpoints.

The final normal-mode timing report now has +0.044 ns setup and +0.022 ns
hold slack, with zero failing setup/hold/pulse endpoints. The preliminary
normal-mode CDC inventory has the same 116 non-information rows as the
baseline after five source-proven FIFO storage renamings and two reset
report launch selections. This is not the final OOB-mode CDC disposition.

`tools/review_spare_pipeline_cdc.py` requires the completed exact-image
artifact, fanin, Gray-pointer and source evidence. It permits only the five
verified FIFO name substitutions and the two unused-reset representative
source choices; complete routed fanins/clocks must still match. Every other
row or fact change stops the review. The generated packager independently
checks the disposition before it can be published.

The release worker `opentpu-spare4gb-pipeline-release-20261017.service`
completed the exact collection dependency, applied those gates and packaged
c0172300. Its frozen inputs and logs are under
`build/checks/spare-pipeline-release-20261017/`. It does not program hardware,
flash, commit or push. The completed offline package is
`bitstreams/spare-pcie-4gb-pipeline-ddr800/`; its later Mac LFM test failed as
recorded at the top of this page.

The second review waiter handles systemd removing a normally completed
transient build unit. It accepts that missing handle only with the exact
terminal build status, then checks every source and output. A different live
invocation is rejected. The original waiting attempt and its logs remain in
`build/checks/spare-pipeline-review-20261017/`.

## Image-specific Mac helpers and firmware

The prepared host tree is
`build/handoffs/spare4gb-host-c0172300-20261017/`. Its calibration, DMA and
LFM2 helpers import a separate `spare_c0172300` profile, which requires the
new pipeline package identity and review statuses. CLI imports and shell
syntax passed; the new profile rejected the actual c0172080 baseline package.
The historical command was `bash tools/mac_spare_c0172300.sh lfm` from the
prepared host tree. The original local transfer/preflight receipts remain
preserved; use [the Git runtime guide](mac_c0172300.md) for the later published
small-file handoff and recorded failure. Model checkpoints and the working
Python/libusb environment remain separate. Preserved local transfer artifacts
are not the current handoff method or evidence of physical correctness.

The pipeline changes generated Verilog and FIFO RAM names. Its CSR CSV differs
from the reference only in the generated comment header. Both initialization
files, startup firmware memory and all non-comment CSR rows match exactly.
The new binding therefore checks those calibration contracts and binds the
complete new core hashes, native-adapter source/model receipt, reviewed
c0172068 firmware and actual bitstream hash. It keeps the original RAM-only
reference package and firmware guards. CH0 startup is still a host step.

`tools/prepare_spare_pipeline_packager.py` prepares a separate packager under
`build/checks/spare4gb-packager-c0172300-20261017/`. Its CLI imports passed.
It retains the numerical timing/route/CRC/pad and 49-assertion Gray checks,
requires a new CDC disposition, and writes the image-bound firmware metadata
only while packaging the reviewed bitstream. That package has now been created.

## Rebuild from source

Use the pinned LiteX/Migen environment and compiler container described in
[the build guide](vivado_bitstream_guide.md). Vivado and the licensed target
device support are required on the build host. These commands use fresh output
directories; model weights and hardware access are not part of this build.

```bash
export PYTHONDONTWRITEBYTECODE=1
LD_PY=build/fedora-openxc7/litedram-environment/venv/bin/python
"$LD_PY" -B tools/check_spare_native_pipeline.py \
  --out build/checks/spare-pipeline-new
python3 -B tools/prepare_spare_pipeline_pcie.py \
  --python "$LD_PY" \
  --reference-package bitstreams/ramtest-litedram-ddr800-spare8 \
  --firmware bitstreams/ramtest-spare8-ch0-firmware \
  --adapter-model build/checks/spare-pipeline-new/manifest.json \
  --threads 2 --out build/vivado/spare-pipeline-new
python3 - <<'PY'
import json, subprocess
with open('build/vivado/spare-pipeline-new/build.command.json') as stream:
    subprocess.run(json.load(stream), check=True)
PY
```

Generation freezes the adapter and generator sources, checks the reference
calibration configuration and prepares the full OpenTPU driver. Implementation
runs synthesis, optimization, placement and routing, then the strict pre-bit
timing/DRC gates. A generated `.bit` still needs the independent reviews below.

After the implementation command exits successfully, prepare and execute the
artifact/CDC collectors:

```bash
python3 -B tools/prepare_spare_pipeline_review.py \
  --preparation build/vivado/spare-pipeline-new \
  --out build/checks/spare-pipeline-review-new
python3 - <<'PY'
import json, subprocess
with open('build/checks/spare-pipeline-review-new/manifest.json') as stream:
    review = json.load(stream)
for command in [review['artifact_command'], *[job['command'] for job in review['jobs']]]:
    subprocess.run(command, check=True)
PY
```

For a background build, `tools/run_spare_pipeline_review.py` can instead wait
on the exact live build service and invocation. Collection records evidence;
review actual routed paths, clocks, fanins and operating assumptions before
producing the new CDC disposition. Do not reuse a baseline approval receipt.

Prepare the separate host and packager:

```bash
python3 -B tools/prepare_spare_pipeline_host.py \
  --preparation build/vivado/spare-pipeline-new \
  --out build/handoffs/spare-pipeline-host-new
python3 -B tools/prepare_spare_pipeline_packager.py \
  --preparation build/vivado/spare-pipeline-new \
  --host-tree build/handoffs/spare-pipeline-host-new \
  --out build/checks/spare-pipeline-packager-new
```

The generated packager's `--help` lists the completed build, qualification,
new CDC review, reference package, firmware and output arguments. It rejects
incomplete reviews. Keep the generated host tree with the final package.
Programming and physical DMA/matmul/reference-inference qualification are
separate actions after offline review.
