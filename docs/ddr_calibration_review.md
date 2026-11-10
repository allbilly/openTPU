# DDR calibration review, updated October 17, 2026

## Historical October 17 handoff

Current disposition is in [HANDOFF.md](../HANDOFF.md). The fixed-clock
c0182800/c0182863 artifacts are retained, and the c01848 runtime-clock effort
was abandoned on October 22. The hardware location, experiment order and
readiness statements below describe the October 17 observation, not live state
or authorization for another test. Some linked evidence remains local only.

The revised lane-6 plan (local-only `docs/ddr_lane6_debug_plan.md`) recorded the experiment
order then. Exact neighbor-data substitution had been captured, but its location
in the write/storage/read path remains unresolved. Historical hypotheses below
must be read together with the subsequent full-tag row-control failures.

The card is now connected to Fedora through a DLC10 USB/JTAG programmer.
Volatile SRAM loading and USER2 readback work; Fedora has no live FPGA PCIe
endpoint. Current RAM-only results and the revised experiment order are in
the [RAM debug plan](ddr_ram_only_debug.md#measured-evidence-october-16).
Mac PCIe inference was previously measured separately. The working PCIe
image and matched DDR800 data are tracked in
[`bitstreams/ch1-pcie-2gb/`](../bitstreams/ch1-pcie-2gb/). This image bypasses
physical CH0 and provides 2 GiB through physical CH1.

The source branch is `ypcb/ch1-bringup-local`; `origin` is
`https://github.com/allbilly/openTPU.git`, and `upstream` is FeSens/openTPU.
The [build guide](vivado_bitstream_guide.md#rebuild-the-current-ch1-pcie-release-on-fedora)
includes the complete Fedora build and Mac loading procedure. A separate
full PCIe candidate finished building at
`build/fedora-vivado/ch0-reset-pcie-20261016`, with BUILD_ID `c0160001`.
It adds the upstream serializer-reset register, keeps the CH1 fallback mapping
and retains raw physical CH0 diagnostics. Its independent packet/CRC, pin,
resource, route, timing and bus-skew checks passed. Critical CDC review is now
complete for the documented startup and normal-operation scope. The image,
matched core and evidence are packaged at
[`bitstreams/ch1-pcie-2gb-ch0-reset/`](../bitstreams/ch1-pcie-2gb-ch0-reset/).
Mac loading and physical tests remain pending. No CH0 repair is established.

The [dedicated RAM-only MIG baseline](ddr_ram_only_debug.md) reproduced CH0
corrected errors. Separate-image isolated traffic passes do not establish a
concurrency cause. Same-image switching and matched LiteDRAM comparisons are
now complete; both retain CH0 failures. The latest raw pattern tests expose
lane-6 coupling between two addresses differing only in DDR column A8.
Writing the upper address changes the lower address's lane-6 readback;
reversing writes reverses that coupling, including during grouped reads.
The effect also occurs near the bottom of RAM, inside calibration's tested
range. The earlier repeated-address pattern gives this pair identical lane-6
bytes and therefore misses this failure. See the
[bound observations and limits](ddr_ram_only_debug.md#distinct-address-pairs-expose-lane-6-coupling).
The same row-A8 control subsequently retained distinct tags at both locations
for 64 final reads each. This weakens a generally stuck/disconnected A8-pin
explanation and focuses attention on column-command timing or internal column
addressing. The independent focused MIG image now passed its first bounded
comparison at the same physical locations, with zero ECC/payload errors in
2,048 reads per channel. A second fresh SRAM load also passed. Die temperature
was lower (43.31–45.89°C first, 41.96–45.77°C second), and data tags and the ECC path also differ. This
strengthens the case for a LiteDRAM-specific timing/initialization investigation
without excluding intermittent hardware. No repair is established. The older full-system
MIG image includes the accelerator.

The subsequent fresh LiteDRAM comparison used the same physical pairs and
CH0 zero/one payload tags as focused MIG, with native generators held reset.
It failed 688 of 2,048 raw reads on lane 6, including the full-tag row-A8
control; CH1 passed all 2,048 reads. Raw check bits, access timing and die
temperatures differ from MIG. The previous narrow-tag row pass therefore
does not establish column-only behavior. A read-only lane-6 input-delay
comparison on the retained raw contents found no clean setting at taps 18–26;
same-tap replay did not recover it. Bitslip and command/write timing were
unchanged. See the
reviewed raw result (local-only `docs/data/ddr_litedram_fresh_address_pairs_20261017.json`).

The subsequent retained-data framing scan also found no clean setting among
all eight uniform lane-6 bitslips. Nearby delay and uniform framing changes
therefore have not recovered the failure. The new passive raw-capture image
`c0172032` is built, independently reviewed and packaged at
[`bitstreams/ramtest-litedram-ddr800-raw-capture/`](../bitstreams/ramtest-litedram-ddr800-raw-capture/).
Its physical observation (local-only `docs/data/ddr_litedram_raw_capture_20261017.json`) reproduced
the symptom: 69/512 CH0 reads failed and CH1 passed 512/512. Every failing
capture has lane 6 returning `00` instead of `ff` in all eight raw DDR transfers;
all other raw bits match. Die temperature was 48.11–49.09°C, and calibration
records stayed unchanged. This does not yet separate write corruption,
read capture/selection, or an electrical fault. The two-location raw test
does not qualify native ECC or full capacity.

The retained-high-word neighbor-tag comparison (local-only `docs/data/ddr_litedram_raw_neighbor_tags_20261017.json`)
then changed only the lower word in the same load/calibration. High-word
errors were 96/128 with a zero neighbor, 102/128 with A5 data, 0/128 with
identical ones and 32/128 after returning the neighbor to zero. Every bad
lane-6 vector matched the neighbor's data; other lanes and CH1 controls were
clean. This is data-dependent lane interference, not a permanently stuck-zero
lane. Equal tags conceal the failure. Stored-data corruption, read-path
selection/capture and intermittent hardware remain alternatives.

The [latest upstream branch review](ddr_upstream_branch_review.md) checks all
190 live heads against `~/upstream_openTPU`. Static read clocks and per-bit
framing are already present; the shipped DDR800 core still has `rd_reg` off
and predates the later serializer-reset stage. The updated plan includes
controlled warm rescans, mixed traffic and ECC snapshots after each stage.

### Historical upstream comparison on October 15

At the time of this comparison, `origin` was `https://github.com/FeSens/openTPU`
and HEAD was `5b1e646cdec9de449ba416952ec854b0b2d973d7`.
A read-only upstream comparison fetched main at
`7e42a626f714edd07867702c38c954082d51f587` (520 reachable commits ahead of HEAD).
No merge, stash, reset or update to the modified working files was performed.
The previous isolated donor checkout remains at `e15b4a44`.

## What the upstream notes establish

Read [LiteDRAM sections 7, 8 and 10](litedram.md), especially the later card
results rather than its initial assessment. [Board section 6](board.md) records
an older controller's CH0 lane 3 and CH1 lanes 6–7 problems. Those are historical
developer observations; our present failure is physical CH0 lane 6.

The qualified LiteDRAM design uses per-lane write-latency calibration, static
read clocks, per-bit read framing, one MMCM per channel, and CK phase selection
using traffic tests. Group 1 is left at offset zero: earlier nonzero offsets
broke the serializer clock alignment. The firmware scans all phases with a
64 MiB write/read test; a passing short DFI check alone is insufficient.

The developers recorded zero errors on both full 2 GiB channels during a
35-minute test near 54–55 C, with rescans every five minutes. A later fused
image passed qualification at 65–68 C. These qualify their images/card, not ours.
Automatic temperature-triggered rescans remain labeled **not built** in the
follow-up section. A rescan overwrites its test region, so a runtime integration
must reserve that region or preserve and restore its contents.

The same PHY and calibration firmware already exist at our HEAD. Between HEAD
and `e15b4a44`, `ddrcal.py` adds a phase-shift timeout; it does not repair data
errors. From `e15b4a44` to freshly fetched main, those PHY/firmware/host
calibration files are unchanged. The new LiteDRAM note explains that the
optional read-register latency is handled inside the bitstream; changing a host
latency constant is not a recovery method. That comparison found no new
calibration-firmware fix. The later
[`f2d1023d` serializer-reset change](https://github.com/FeSens/openTPU/commit/f2d1023ddded0a4d70b8810a715e173ea989efd7)
is isolated in the new candidate; its effect on our lane-6 failure is untested.

## Measurements on this card

The CH1-only JTAG image passed physical LFM2 with exact ISA tokens and clean
ECC. Its retained CH0 PHY, controller and BIST allow diagnosis, but CH0 has no
normal host/compute traffic in this image.

### Continue diagnosis through Chestnut on macOS

The current PCIe CH1 recovery image retains physical CH0's calibration/BIST
registers in BAR0. Use the Mac's existing Chestnut adapter to access them;
normal logical channel 0 DMA addresses access physical CH1 in this image.
The portable probe accepts the existing adapter file and its transport class,
so these diagnostics do not need Vivado on macOS.

After the inference process has exited, first collect a snapshot using the
working Mac Python environment:

```sh
build/chestnut-lfm/venv/bin/python tools/fedora_probe_ddr_recovery.py \
  --adapter build/chestnut-lfm/transport.py \
  --core bitstreams/ch1-pcie-2gb/core \
  --snapshot-only --out build/chestnut-ch0-snapshot
```

The tool detects a unique adapter class with `reg_read` and `reg_write`.
If several exist, select the actual transport with `--factory ClassName`.
The snapshot checks OpenTPU identity, DDR800 profile and the CH1 recovery
marker, rejects active compute/loading, and records both physical channels'
calibration flags, BIST/ECC counters and available temperature. It does not
start calibration or BIST, reset the FPGA, clear counters or program flash.
Reading the calibration mailbox selects its read address.

To repeat the saved physical CH0 calibration and full-capacity test sequence:

```sh
build/chestnut-lfm/venv/bin/python tools/fedora_probe_ddr_recovery.py \
  --adapter build/chestnut-lfm/transport.py \
  --core bitstreams/ch1-pcie-2gb/core \
  --out build/chestnut-ch0-baseline
```

This second command changes physical CH0's training and overwrites its test
memory. It selects CH0 alone for the calibration CPU, checks that CH1 remains
ready, and only runs the four full 2 GiB PRBS/address BIST stages after
calibration reports success. It stops on the first error and preserves the
result. It does not access CH1 through the normal model ports or load another
FPGA image. Calibration success alone is not a pass.

If that baseline passes, repeat with `--soak-seconds 300` and a fresh `--out`
directory. The probe then repeats all four full-capacity modes with changing
PRBS seeds for at least five minutes, saves the available FPGA temperature
and CH1 readiness after each complete trial, and stops on the first failure.
It performs no mid-soak retraining. FPGA temperature is not a direct DRAM-chip
temperature measurement. This still tests the raw CH0 BIST port; dual-channel
normal host/compute traffic is a separate qualification.

Use fresh result directories for cold and warm trials. Return each
`manifest.json`, especially `status`, `identity_before`, `calibration`, `bist`
and `ch1_ready_before`/`ch1_ready_after`. These are new measurements on this
card; the historical receipts below remain unchanged. A passing raw CH0 test
still needs warm repetition and a full dual-channel host/compute test before
claiming CH0 is repaired.

### Portable calibration-firmware follow-ups

[`bitstreams/ch0-diagnostics/`](../bitstreams/ch0-diagnostics/) includes the two
previously exercised diagnostic CPU programs, rebuilt byte-for-byte from the
same C experiments. These `.bin` files run inside the existing FPGA image's
calibration CPU; they are not FPGA bitstreams and are not JTAG flasher inputs.
Mac use requires neither Vivado nor a RISC-V compiler. Their previous physical
results remain failures to recover CH0, rather than evidence of a repair.

| Directory | Firmware ID | Purpose |
| --- | --- | --- |
| `strict-calibration` | `0xd0150001` | Check a second PRBS seed at every scan phase and all 2 GiB with PRBS/address patterns before setting CH0 ready |
| `lane6-traffic-scan` | `0xd0150002` | Sweep 1,024 common lane-6 write/read framing and read-tap combinations at CK phase 45; always leave CH0 unready |

Verify these files after transfer with
`(cd bitstreams/ch0-diagnostics && shasum -a 256 -c SHA256SUMS)`.
For the stricter follow-up, run:

```sh
build/chestnut-lfm/venv/bin/python tools/fedora_probe_ddr_recovery.py \
  --adapter build/chestnut-lfm/transport.py \
  --core bitstreams/ch1-pcie-2gb/core \
  --firmware bitstreams/ch0-diagnostics/strict-calibration/manifest.json \
  --soak-seconds 300 --out build/chestnut-ch0-strict
```

The loader checks the firmware hash and a fingerprint of the complete generated
firmware configuration, including CSR addresses, PHY constants, init commands
and test patterns. It supports a different checkout path on the Mac. It uploads
and reads back the CPU memory before release, selects physical CH0 alone and
checks CH1 readiness. If training fails, it saves the failure and skips the
subsequent soak. The override stays in CPU memory until FPGA reconfiguration;
it does not update NOR. Use a configuration reload to restore the embedded
default firmware before comparing a later baseline.

The traffic-only follow-up uses the same command with
`--firmware bitstreams/ch0-diagnostics/lane6-traffic-scan/manifest.json`, a fresh
`--out`, and without `--soak-seconds`. Its receipt contains
`lane6_traffic_diagnostic`; finding the best failing combination is not a pass.
It does not test every per-bit framing choice or identify an electrical fault.

Rebuild either diagnostic on Fedora with the RV32I/ILP32 toolchain described
in the [build guide](vivado_bitstream_guide.md#regenerate-the-ch1-ddr-core-when-changing-the-phy):

```bash
python3 tools/fedora_prepare_ddr_recovery_firmware.py \
  --core bitstreams/ch1-pcie-2gb/core \
  --rv-cc /path/to/toolchain/bin/riscv64-unknown-elf-gcc \
  --out build/ch0-strict-firmware
```

Add `--traffic-scan` and select a fresh `--out` to build the other program.
The output manifest and `firmware/selfcal.bin` can be transferred together;
`firmware_relative` resolves the binary beside that manifest. No FPGA rebuild
is required for these CPU-firmware experiments.

The [fresh CH0 probe](../build/fedora-vivado/ddr-recovery-initial-20261014T171217Z/manifest.json)
reported calibration OK in 8.21 seconds at 53.5–53.7 C, with only a 6-step /
134 ps common phase window. The subsequent full 2 GiB PRBS read failed on
16,813,039 beats, exclusively lane 6. CH1 stayed ready. This is a calibration
false positive, not a repaired channel.

The [address/pattern diagnostic](../build/fedora-vivado/ddr-recovery-alias-20261014T172742Z/manifest.json)
tested 8 KiB blocks at offsets from 1 MiB to 1.5 GiB. PRBS reads already failed
on lane 6 before cross-writes. Some cross-writes disturbed other regions on
that lane, but clean baseline reads were absent, so the experiment does not
establish bidirectional address aliasing or its cause.

An isolated experimental firmware adds the failing fixed PRBS seed at every
scan phase and full-capacity PRBS/address validation after final training,
before raising `cal_ready`. Its CSR/init header exactly matches the current
core. Production source and the bitstream are preserved. Build and physical
test receipts are separate; neither a compiled firmware nor a calibration
ready flag establishes a memory repair. The
[stricter physical scan](../build/fedora-vivado/ddr-recovery-firmware-test-20261014T173506Z/manifest.json)
completed in 10.72 seconds after a verified firmware upload. Lane 6 failed
at all scanned phases with the added PRBS seed, so the firmware correctly
kept CH0 unready. CH1 remained ready. The
[traffic-framing diagnostic](../build/fedora-vivado/ddr-recovery-firmware-test-20261014T174011Z/manifest.json)
then completed 1,024 combinations at CK phase 45: four lane-6 write bitslips,
eight read bitslips and 32 read-delay taps, with a 128 KiB PRBS test. None passed;
the minimum was 512 wrong beats out of 2,048. The initial short DFI test had
reported no bad lanes. This rules out a simple common lane-6 framing/tap choice
in this particular sweep; per-bit framing and other clocks/electrical causes
are not ruled out. CH0 remains unready and CH1 remains ready.

## Web search: solutions for this board model

The October 15 search covered the exact YPCB-00338-1P1 name, LiteX/LiteDRAM
board support, the reverse-engineered Vivado projects, and English/Chinese
DDR failure reports. No public fix for our exact CH0 lane-6 symptom was found.

| Primary source | Applicable evidence | Limitation |
| --- | --- | --- |
| [openTPU LiteDRAM card results](https://github.com/FeSens/openTPU/blob/main/docs/litedram.md#8-write-leveling-by-clock-groups-wl7ddrphy-2026-09-29) | Per-lane write latency, static read clocks, per-bit read framing and traffic-selected CK phase restored full-width operation on the same model | Already included in our image; their successful board tests do not qualify our card |
| [LiteX board target](https://github.com/litex-hub/litex-boards/blob/master/litex_boards/targets/ypcb_00338_1p1.py) | A7DDRPHY workaround for HR banks without ODELAY; only lanes 0–3 enabled with an explicit TODO for the rest | Reduced-width workaround, not full dual-channel recovery |
| [TiferKing MIG board project](https://github.com/TiferKing/ypcb_00338_1p1_hack/blob/main/ypcb003381p1/1.0/mig_01.prj) | Board-specific dual-controller pin/configuration reference for Xilinx MIG | Does not demonstrate a long warm full-capacity test of our card |
| [Independent MicroBlaze bring-up](https://qiita.com/okakousuke1124/items/e01263353e326de4cad0) | The author reports DDR tests on both channels using the board-reference design | Limited test region; not an exhaustive 4 GiB stress qualification |
| [AMD UG586: common hardware issues](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Debugging-Common-Hardware-Issues) | Use the MIG example design and require both calibration completion and no data-compare errors | General 7-series procedure, not a model-specific repair |
| [AMD UG586: isolate data errors](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Isolating-the-Data-Error) | Compare actual/expected data, affected DQ/DQS groups, addresses, patterns, temperature and reset reproducibility | Pattern dependence can arise from timing or electrical faults; it does not establish one cause |

The next discriminating experiment is a dedicated RAM-only MIG baseline, then
a matched RAM-only LiteDRAM test at DDR3-800. The historical MIG reference
contains the accelerator and does not establish the RAM-only baseline. Test
all 2 GiB per physical channel, retain first-error/lane/ECC evidence, and repeat
cold and warm. The [RAM-only debug plan and build procedure](ddr_ram_only_debug.md)
describes the images, full-address coverage counters and Mac JTAG access gate.
A clean matched MIG result would point toward the LiteDRAM implementation or
calibration; the same lane failure with both controllers would strengthen the
case for pin/electrical/card investigation. Neither outcome alone proves the
precise fault. Keep the working CH1 image as the inference fallback.

## Remaining gates

Recover a phase/training choice that passes multiple patterns over all 2 GiB;
repeat while warm and inspect margins. Then validate both physical channels
and normal host/compute traffic using a full dual-channel image. The existing
CH1 PCIe release subsequently passed NOR programming, separate verification
and a JTAG-requested flash boot on October 15, as recorded in the
[PCIe guide](permanent_pcie_ch1.md). Cold power-on boot and full PCIe inference
still need saved results. The new reset candidate has not been loaded or
tested on the card; its physical results must be recorded separately.
