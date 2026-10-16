# DDR calibration review, October 15, 2026

The working Fedora checkout uses `origin` = `https://github.com/FeSens/openTPU`
for both fetch and push. HEAD remains `5b1e646cdec9de449ba416952ec854b0b2d973d7`.
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
latency constant is not a recovery method. There is no newly fetched DDR
calibration fix to apply blindly.

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

Use fresh result directories for cold and warm trials. Return each
`manifest.json`, especially `status`, `identity_before`, `calibration`, `bist`
and `ch1_ready_before`/`ch1_ready_after`. These are new measurements on this
card; the historical receipts below remain unchanged. A passing raw CH0 test
still needs warm repetition and a full dual-channel host/compute test before
claiming CH0 is repaired.

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

The next discriminating experiment is a matched warm, full-capacity/pattern
test on CH0 using the existing Vivado MIG reference, with expected/actual data
and lane information saved. A clean MIG result would point toward the LiteDRAM
implementation/calibration; the same lane failure with both controllers would
strengthen the case for pin/electrical/card-level investigation. Neither outcome
alone proves the precise fault. Keep the working CH1 image as the inference
fallback while this is resolved.

## Remaining gates

Recover a phase/training choice that passes multiple patterns over all 2 GiB;
repeat while warm and inspect margins. Then validate both physical channels
and normal host/compute traffic using a full dual-channel image. Permanent
PCIe programming also requires the PCIe image's remaining reset review,
actual flash identification, a verified factory backup, flash verification,
and cold-boot/PCIe tests on the other Linux PC. No flash write has occurred.
