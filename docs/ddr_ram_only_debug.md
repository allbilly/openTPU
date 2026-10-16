# CH0 diagnosis with a RAM-only baseline

The first physical experiment is a dedicated RAM-only MIG image. The historical
MIG/JTAG image contains `otpu_native_sys`, so it does not establish this baseline.
The new diagnostic has vendor MIG, its example traffic generator, counters and
USER2 JTAG status. It has no OpenTPU compute engine or PCIe endpoint.

The first built address image is packaged at
[`bitstreams/ramtest-mig-ddr800-address/`](../bitstreams/ramtest-mig-ddr800-address/),
BUILD_ID `c0161001`. Its route/timing, 242 board-reference pin assignments,
packet/CRC and four bus-skew checks passed. Vendor CDC findings and their review
are preserved. Mac loading, status readback and physical RAM results are pending.

## Current evidence and order

Physical CH0 previously failed on byte lane 6, DQ48–55, with both the full-system
MIG DDR3-1066 image and the full-system LiteDRAM DDR3-800 image. Retraining could
briefly pass, and errors recurred while warm. These experiments differ in speed
and integration. They do not prove a defective DRAM chip.

1. Run the RAM-only MIG DDR3-800 address test. Record CH0 and CH1 separately.
2. Run each channel's traffic independently, then both together. Both PHYs remain
   instantiated and calibrate; `--channels` selects the traffic generators.
3. Repeat all patterns over all 2 GiB/channel: address, zeros, ones, walking one,
   walking zero and PRBS. Each pattern is a separate SRAM image, with its own ID.
4. Repeat cold starts and warm sustained reads. Do not retrain during a soak.
   Record the temperature reached; a cool run does not reproduce a warm failure.
5. Compare with RAM-only LiteDRAM at the same DDR3-800 rate and test scope.
6. Once both channels pass, restore full dual-channel OpenTPU and check memory,
   PCIe transfers, matmul and LFM. Keep the working CH1 release as the fallback.

Start with five-minute observations, then longer warm repetition. A fixed time
does not prove a temperature condition. The reported sensor is FPGA die
temperature, not a measurement of the DRAM chips. Idle/retention and mixed
read/write stress are follow-up tests; this first image initializes the selected
pattern once, then repeatedly reads it using the vendor generator.

AMD recommends starting with its example design and checking both calibration
and data comparison:
[UG586 hardware debugging](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Debugging-Common-Hardware-Issues).

## What counts as a pass

The vendor example's default address window is too small for this board's full
capacity. The builder changes each generator to native addresses
`0x00000000..0x0fffffff`. One native BL8 command accesses 64 payload bytes and
advances the native address by eight. The last accepted address must therefore
be `0x0ffffff8`, corresponding to byte offset `0x7fffffc0`.

The observer counts complete consecutive write and read command sequences,
independently of total traffic counts. Repeated reads of a small region cannot
satisfy the full-pass checks. Data-return and comparison counts must also cover
at least 33,554,432 beats. The host freezes a command-count target from a
snapshot containing a full read traversal, then waits until returned and
compared counts reach that target. Pending read data cannot be mistaken for a
completed test. Both corrected and uncorrectable ECC counts must
remain zero. MIG correction remains enabled; corrected data alone cannot hide
an error from the verdict. The cumulative bad byte-lane mask and failed-compare
cycle count are retained. Deliberate DQ48 corruption checks these detectors and
their coherent snapshot. The vendor first-error address/expected/actual record
is also saved, but its pipelines were found misaligned in injection testing.
It is marked unverified and is not used to identify failing bits or addresses.

The generated example's legacy burst-boundary expressions mix byte-oriented
quantities with native addresses. A stalled-port simulation showed clipped read
bursts with skipped ranges; the full-pass counter rejected them. The builder
retains a two-expression `vendor-traffic-bounds.patch` using exclusive native
ends (`address + burst_commands * 8 <= end + 1`). This correction is limited to
the traffic generator for this 4:1/BL8 configuration. MIG controller/PHY RTL is
unchanged. The generated traffic source is snapshotted before implementation.

The model also exposed two pattern-specific example issues. The PRBS LFSR
advanced under write backpressure without an accepted payload; a traffic-only
patch gates mode-7 PRBS advancement on actual write/read transfers. Fixed mode
kept its BRAM address at slot 8 while its ready condition waited for slot 7;
the zeros/ones build corrects that readiness condition. Each generated change
is retained as a patch beside the build. These corrections affect the test
generator, and provide no evidence of a repaired physical DDR channel.

The vendor's default watchdogs assume mixed reads and writes. They are disabled
for this fill-once/read-repeatedly mode. The observer instead latches a failure
after 65,536 UI cycles without an accepted command, or without returned read data
after initialization. A new snapshot requires the selected channel's UI clock
to be alive; missing acknowledgment is a failed acquisition.

These counters prove the observed pattern coverage. They do not establish all
patterns, cold starts, warm conditions, retention or full OpenTPU operation.

## Build on Fedora

Requires Vivado with Kintex-7 support and Python 3. The XML pin/configuration
reference is tracked at
[`boards/ypcb-00338/ramtest/mig-ddr3-1066.prj`](../boards/ypcb-00338/ramtest/mig-ddr3-1066.prj).
It is copied from the previously exercised MIG image, with all pin selections
preserved. The builder derives DDR3-800 using a 2500-ps period, 800-MHz MMCM VCO,
CL6 and CWL5. Vivado generates vendor RTL locally; generated vendor source is
not required in Git.

```bash
python3 tools/fedora_build_ramtest_mig.py \
  --vivado /home/fedora/vivado/2026.1/Vivado/bin/vivado \
  --ddr-mts 800 --channels both --pattern address --build-id c0161001 \
  --out build/ramtest-mig-800-address
```

Choose a new output directory for every attempt. `--prepare-only` generates IP
and the diagnostic source without synthesis/implementation. `--channels 0` or
`--channels 1` isolates traffic. `--pattern` accepts the six patterns listed
above. `--ddr-mts 1066` retains the original timing configuration. Assign a
distinct `--build-id` to each image so receipts identify the exact experiment.

Outputs include source snapshots/hashes, generation/build logs, routed checkpoint,
timing/route/CDC/bus-skew/IO/DRC reports and `ramtest.bit`. Completion requires the
manifest status `RAM_ONLY_BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING`; preparation or
synthesis alone is insufficient. Review CDC and independently check packet CRC
before transferring an image. The tool never accesses a card or writes flash.

The memory-test observer has a focused RTL simulation in
`tests/test_ramtest_mig.py`. Exercise the actual generated vendor traffic logic
with Icarus Verilog using:

```bash
python3 tools/check_ramtest_traffic.py \
  --ip build/ramtest-mig-800-address/ip/otpu_mig_ddr3/otpu_mig_ddr3/example_design/rtl/traffic_gen \
  --out build/ramtest-vendor-model-check
```

Add `--simulator verilator` to use Verilator. That model uses a 128-KiB window, separate command/write-data queues and
independent stalls. It checks all six patterns and deliberate read-data
corruption. It is a traffic-generator/observer simulation, not a DRAM PHY or
physical 2-GiB test.

## Establish Mac programming and status access

The Mac does not need Vivado to load a completed image. Its cable/programmer and
USER2 readback path have not yet been identified. An optional inventory helper
is available; the user declined this inventory, so it is not a prerequisite:

```bash
python3 tools/mac_fpga_setup_check.py --out build/mac-fpga-setup.json
```

The tool only checks versions, selected Python packages, USB
product names/VID/PIDs and hashes of the existing Chestnut scripts. It does not
open USB endpoints, inspect shell history, collect USB serial numbers or change
the FPGA. Inventory success does not prove programming support.

Load the reviewed `.bit` into SRAM with the identified JTAG tool. Retain the
working CH1 NOR contents. This image has no PCIe endpoint, so the Chestnut PCIe
adapter cannot read its status. It needs a cable backend exposing USER2; the
existing host protocol uses a localhost XVC server, not a vendor-specific Mac
driver. A normal openFPGALoader installation must not be assumed to support
XPCU-to-XVC without checking its build and cable backend.

### DLC10: reuse the Mac flasher's working source

Upstream's [XVC server constructor](https://github.com/trabucayre/openFPGALoader/blob/master/src/xvc_server.cpp)
does not select the XPCU backend. This repository's existing
`tools/fedora_prepare_xvc.py` adds mixed TMS/TDI transfers through the XPCU
encoder, selects that backend, checks USB transfer failures and binds the server
to localhost. Its compiler and pkg-config paths are now configurable for Mac
builds. A firmware file and the Mac-specific USB fixes must come from the
**same source checkout that already programs the card successfully**. The
preparer copies tracked source into a fresh directory; it leaves that donor
and its binaries intact. It does not access the cable.

With CMake, a C++ compiler, pkg-config, libusb and libftdi installed:

```bash
python3 tools/fedora_prepare_xvc.py \
  --donor /absolute/path/to/your/working/openFPGALoader \
  --out build/mac-xpcu-xvc --jobs 4 --no-select
```

Require `SERVER_COMPILED_PROTOCOL_PASS_PHYSICAL_NOT_RUN` in the resulting
manifest. The included protocol model checks partial-byte transfers, mailbox
frames, buffer boundaries and USB failures. A Fedora build/model pass does
not establish Mac USB operation. There is no dependency on Fedora's `~/ypcb`
when `--donor` is supplied. Reuse the working Mac flasher's cable initialization
and firmware path; do not run the Fedora-specific `dlc10-init.sh` on Mac.

Once the reviewed address-test image is available, these are the DLC10 commands
from the repository root. Replace the firmware path with the one used by the
working Mac flasher:

```bash
XPCU_LOADER="$PWD/build/mac-xpcu-xvc/binary/openFPGALoader"
XPCU_FW="/absolute/path/to/working/xusb_xp2.hex"
"$XPCU_LOADER" --cable xilinxPlatformCableUsb --freq 6000000 \
  --probe-firmware "$XPCU_FW" --detect
```

Require a single FPGA with IDCODE `0x23751093`. Load the `.bit` with
`--write-sram`, then run the server in a separate terminal:

```bash
"$XPCU_LOADER" --cable xilinxPlatformCableUsb --freq 6000000 \
  --probe-firmware "$XPCU_FW" --write-sram /absolute/path/to/reviewed/ramtest.bit
"$XPCU_LOADER" --cable xilinxPlatformCableUsb --freq 6000000 \
  --probe-firmware "$XPCU_FW" --xvc --port 3721
```

Leave the server in the foreground while collecting snapshots. SRAM loading
does not write the working CH1 NOR image. A completed programming log and a
successful `RAMT` readback are separate requirements. These commands remain
unverified on the Mac until their actual logs are returned.

After that server and SRAM load are established, use the Mac environment that
already has NumPy:

```bash
build/chestnut-lfm/venv/bin/python tools/probe_ramtest_mig.py \
  --host localhost --port 3721 --expect-build-id c0161001 \
  --seconds 300 --out build/ramtest-mig800-address-cold-1
```

The reader verifies the `RAMT` identity, ABI and expected build ID before issuing
a status-snapshot request. It does not reset, retrain or write memory. Save
`manifest.json` and `samples.jsonl` for each run. Use fresh directories for warm
and cold repetitions. A missing XVC endpoint is a transport failure and provides
no evidence about DDR.

## Interpret the comparison

| Result at matched speed and test conditions | Next investigation |
| --- | --- |
| RAM-only MIG passes, RAM-only LiteDRAM fails | LiteDRAM reset, training, PHY timing and implementation |
| Both fail on the same physical byte lane | Shared pin configuration, board power, signal integrity, FPGA IO and DRAM path |
| Both pass RAM-only but full OpenTPU fails | Integration, clocks, resets, concurrent load and memory-interface traffic |

Repeated failure with two controllers strengthens the case for a shared
electrical/card problem. Confirming the component responsible still needs
measurements or comparison with another card.

## Local DDR references checked in `~/ypcb` (October 16)

The reference scan inspected the actual archives, test source and saved results.
`${YPCB_ROOT}` is normally `~/ypcb`; no donor checkout was modified.

| Reference | Useful material | Evidence and limitations |
| --- | --- | --- |
| `ref/LC480T/YPCB-00338-1P1/XC7K480T_MEMTest.zip` and `XC7K480T_platform.zip` | Matching supplied `.bit`, `.mmi`, ELF and hardware platform; independent MIG/CPU reference | The supplied test covers only 4 KiB/channel. Its final success message is unconditional; inspect every individual result. This older platform has DDR at 0/0x80000000, local BRAM at 0x100000000 and an ELF64 MicroBlaze application. Keep its image, MMI, BSP and ELF together. |
| `projects/ypcb_00338_1p1_hack/scripts/fedora_ddr_full_core.h` | Full-capacity address/complement algorithm with distinct data for each channel; fills both channels before verifying either | The built `ddr_full.elf` exists, but its readiness receipt says `HOST_READY` and `physical_test: NOT_RUN`. The separate 4-KiB diagnostic's hardware attempt stalled in CPU startup with no DDR result. |
| `projects/bonetto-soc/boards/ypcb-00338/README.md` and DDR SERDES probes | Historical lane fault, direct physical-lane selection, IDELAY sweeps and raw DQ/DQS capture ideas | Historical workaround used 32-bit data and bypassed physical lane 3. The current init-only probe blocks DDR reads/writes; zero idle captures do not prove memory data works. Our observed failure is lane 6. |

The archived MEMTest `.bit` SHA256 is
`1fff925c98ef2d5abdb3b21d9cf58fb24c4eb42e90a81230513d182a30bba2e6`
(18,735,115 bytes, header date May 15, 2024), distinct from the newer staged
TiferKing baseline. Its matching `.mmi` offers an offline ELF-to-BRAM merge
route on Fedora, subject to a separate image/ELF/map audit and a working output
reader on the Mac. This image is a CPU/MIG system, not our minimal RAM-only top.

The failing lane's eight DQ pins and both DQS pins match the LC480T
`MEMORY_CH0.ucf` reference exactly. This confirms another pin-reference match;
it does not measure the electrical path or establish a card defect.

These references add two follow-up checks to the plan:

1. Use the full-core algorithm's **channel-distinct address data and complement**
   for the eventual 4-GiB host-visible mapping test. Fill both channels before
   reading either, so a shared/aliased channel cannot appear to be two memories.
   The first MIG address-pattern image does not establish this cross-channel
   aliasing check.
2. If matched MIG/LiteDRAM runs still fail lane 6, add **raw lane-6 DQ/DQS
   capture and a delay sweep** to separate missing activity from bad sampling.
   Preserve each capture's traffic, tap and temperature conditions.
