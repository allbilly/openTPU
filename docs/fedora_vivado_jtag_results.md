# Vivado OpenTPU hardware results on Linux

Latest update: **2026-10-14 17:11 HKT**. Physical CH1 passed a warm full-capacity
test with zero ECC/data errors. Its recovery core has generated, and a
CH1-only PCIe Vivado image is building with eight workers. The original
dual-channel PCIe reference completed offline at 15:50 HKT. **Fresh recovery
matmul and physical LFM2 output have not passed.** Native Vivado SRAM
programming passed previously, but CH0 memory errors and USB resets remained.
The earlier October 11 kernel pass explicitly includes an MM instruction and
matched the ISA output; it does not establish full LLM inference.

## Latest CH1-only continuation, 17:11 HKT

The user selected CH1-only recovery before full CH0 repair. Physical CH1
passed a 90.91-second warm soak at about 54 C: 180 complete 2 GiB BIST passes,
normal-port readback and zero ECC errors. The recovery core has generated,
and its full-compute PCIe Vivado image is synthesizing with eight workers.
The ECC comparison remains live. Fresh recovery MM and physical LFM2 have
not passed. [Current CH1 guide](ch1_recovery.md).

## October 14 DDR800 results and PCIe continuation

The [first DDR800 run](../build/fedora-vivado/ddr800-native-matmul-lfm2-20261014T051843Z/manifest.json)
passed native SRAM loading, both channels' calibration, all 12 full-capacity
raw BIST passes and the complete zero scrub. Its compact MM comparison then
failed at 13:21 HKT. That version of the helper raised before saving the output
words, so the evidence cannot distinguish an arithmetic error from a memory
error. The helper now saves both outputs and verifies operands before MM.

The [repeat memory check](../build/fedora-vivado/ddr800-native-compute-debug-20261014T052351Z/manifest.json)
at 52.42 degrees C failed on channel 0: **3,655,885 of 33,554,432 beats**, all
localized to byte lane 6 (bits 48–55). It stopped before compute. The matching
pattern across MIG and LiteDRAM narrows the investigation to that memory
interface, but does not prove a particular chip, timing or power fault.

The [warm host calibration](../build/fedora-vivado/ddr800-warm-calibration-compute-20261014T052803Z/manifest.json)
at 53.03 degrees C stopped at 13:29:46 HKT with a mailbox response error.
Its last request was a write to **0x16018**, the second 32-bit word of channel
0's DFII phase-0 write-data register. Linux disconnected USB Device 116 at
13:29:45, briefly enumerated Device 118 at 13:29:46, then disconnected it at
13:29:50. [Saved trace and kernel correlation](../build/fedora-vivado/dlc10-warm-calibration-drop-20261014T061453Z/manifest.json).
This identifies the request in flight; it does not prove that the write caused
the USB loss. No calibration, memory or compute pass followed in this run.

The [new full PCIe build](../build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/manifest.json)
uses native RTL, MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2, a 100 MHz core,
dual DDR3-800 and XDMA Gen2 x8. Eight workers are enabled. An isolated source
snapshot and IP cache preserve the earlier images and ongoing OpenXC7 route.
The build requires clean route, setup/hold/pulse timing and DRC gates before
writing bit/MCS files. Creating an MCS file does not write flash.

The card must be in the other PC's PCIe slot for endpoint and compute tests.
Current JTAG-only images have no PCIe endpoint. Permanent programming remains
authorized only after physical LLM success with a qualified PCIe image, flash
identification/backup, readback verification and boot testing. No flash has
been written in this session.

## October 14 readback failure and diagnostics

[Latest attempt](../build/fedora-vivado/physical-jtag-resume-20261014T041625Z/manifest.json):
SRAM programmer exit 0, INIT/DONE 1, SMI exit 0, selftest exit 1, XVC exit 0.
Channel 0's zero write issued/completed 33,554,432 beats; its matching read
reported **24,886,072 bad beats**, **24,789,197 corrected beats** and
**24,730,483 uncorrectable beats**. Both calibration flags were already set.
[Selftest console](../build/fedora-vivado/physical-jtag-resume-20261014T041625Z/selftest.log).
No flash write was performed.

[Targeted diagnostics](../build/fedora-vivado/mig-readback-debug-20261014T042746Z/manifest.json)
saved those counters before isolating new trials. Zero, ones, address and
xorshift patterns were written/read in three separated 256 KiB regions per
channel. Channel 0 failed **8/12** pairs; channel 1 passed **12/12**. Data
mismatch masks concentrate in bits 48–55, sometimes including bits 46–47.
This is consistent with a localized memory-interface problem but does not
identify the physical chip/pin or distinguish write timing, read timing,
training, supply or board causes. Clearing ECC counters isolates trials;
it is not a fix.

A [guarded same-image reload/retraining trial](../build/fedora-vivado/mig-readback-retrain-20261014T042940Z/manifest.json)
recovered the failure: all 24 small-region pairs passed, followed by all 16
full-memory passes with zero corrected/uncorrectable ECC or data errors.
Summed full BIST hardware time was **4.94 seconds**. The normal selftest then
passed its 4 GiB scrub and both channel address checks, then stopped at the
host pattern stage when Linux disconnected USB Device 083 at 12:32:36 HKT.
The adapter returned immediately as Device 084; XVC reported
`LIBUSB_ERROR_NO_DEVICE`, and the selftest exited 1. A transient DDR
training/timing-margin problem is a working hypothesis; the reload result
does not establish a permanent repair or identify the physical cause.
The original image, clocks and power settings are unchanged; BPI flash is
untouched. AMD's [MIG debugging guidance](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Debugging-DDR3/DDR2-Designs)
recommends isolating calibration/data errors using memory-test/debug evidence;
poor calibration can produce normal-operation errors even after training
completes ([OCLKDELAYED guidance](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Debugging-OCLKDELAYED-Calibration-Failures)).

## October 11 historical physical results

## Board and image

- YPCB-00338-1P1, XC7K480T; one JTAG device, IDCODE `0x23751093`, IR length 6.
- Separately powered card, DLC10 USB/JTAG only; native Vivado build.
- OpenTPU: D=128, MCOLS=4, LANES=8, core 100 MHz, register map 3,
  build ID `5b1e646c`.
- Two native-interface Vivado MIG DDR3-1066 channels, 2 GiB each, with ECC.
- SRAM programming finished at 13:57:45 HKT with actual exit 0 and
  `INIT=1, DONE=1`. No BPI flash write was performed.

Candidate directory:
`build/fedora-vivado/mig-jtag-controller-20261010T235833Z/`.

[Programmed bitstream](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit):
12,870,600 bytes, SHA256
`0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f`.
The [pre-program offline audit](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/offline-audit.json)
passed before the hardware load.

## Verified physical results

| Check | Result | Evidence and scope |
| --- | --- | --- |
| JTAG identity and SRAM upload | PASS | One expected FPGA; loader exit 0 and INIT/DONE acknowledgement. |
| OpenTPU identity/configuration | PASS | ID `0x4f545055`; expected dimensions, clocks and build ID. |
| DDR calibration | PASS | Both channel calibration flags set. |
| Full 4 GiB memory test | PASS | Four patterns, write and read, on both complete 2 GiB channels; zero readback, corrected ECC or uncorrectable ECC errors. |
| Normal selftest scrub | PASS | Complete 4 GiB zero write/read with ECC initialized through the normal scrub hook. |
| Register and channel address checks | PASS | Scratch-register patterns and both raw-channel address/region checks. |
| Host pattern and partial writes | PASS | Six logical regions, 2,106,514 bytes; 200 partial writes on each channel. |
| Normal compute kernels | PASS | Both the all-units and masked-write programs matched the ISA simulator. |
| PCIe bandwidth | SKIPPED | Serial JTAG transport; PCIe throughput was not measured. |
| Extended vector checks (`vops`) | INTERRUPTED | XVC disconnected after a USB disconnect; this stage has no completed pass. |
| Stream checks | NOT RUN | The selftest stopped before this stage. |
| Full LFM2 model/token comparison | NOT RUN | The selftest stopped before model initialization and inference. |
| Complete normal selftest | FAIL | Actual command exit 1 after loss of the USB/JTAG connection. |

The full memory test completed 16 passes: ones, address, xorshift and zero;
write and read for each pattern on each channel. Every pass covered
33,554,432 64-byte beats from channel offset zero, with issued and completed
counts equal to the expected count, status 6, and all error counters zero.
This result covers both complete channels, rather than only the small regions
used in earlier vendor-reference probes.

The normal kernel stage reported:

```text
[PASS] kernel  all units: 9124 cycles (b_reads=2137, a_writes=132);
               partial writes: 10865 cycles (b_writes=33, a_writes=903)
```

The kernel test assembles the instruction programs, executes them on the FPGA
and ISA simulator, checks retired instruction counts, and compares the DRAM
output byte for byte. See [`run_demo`](../opentpu/host/checks.py).
Its 1342.4-second wall time includes host data loading and complete output
readback through JTAG; it is not the FPGA's execution cycle count.

## What is proven about the compiler

The instruction assembler and physical kernel execution path worked for the
two normal kernel programs. Separately, the saved LFM2 compiler/ISA-simulator
run completed using the real model weights and produced its expected tokens.
The combined path from the compiled LFM2 model through FPGA execution and
returned tokens remains unverified because the physical selftest did not
reach its model stage.

The [saved ISA reference](../build/fedora-vivado/physical-jtag-20261010T133821Z/replug-retest-20261010T153130Z/lfm2-reference-result.json)
uses LFM2.5-230M, int8 weights, context capacity 256 and up to eight new tokens.
For the prompt “What is the capital of France? Answer in one sentence.” its
expected text is **“The capital of France is Paris.”**, with token IDs:

```text
[1098, 5706, 803, 4481, 856, 5242, 523, 7]
```

These are simulator reference results. No physical LFM2 output was obtained
in this run. The failed physical receipt contains an empty `model_checks` list.

## Run receipts and disconnect

All physical receipts are under
`build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/`:

- [SRAM programming result](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/result.json)
- [Physical SMI/calibration receipt](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/physical-smi.json)
- [Complete memory test receipt](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/physical-memory.json)
- [Normal selftest console](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/physical-selftest.console.log)
- [Failed selftest receipt](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/physical-selftest.json)
- [Selftest command exit](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/physical-selftest.command.exit)
- [XVC server log](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/xvc-server-tty.log)
- [USB failure snapshot](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/usb-failure-snapshot.json)
- [Hardware run review and receipt hashes](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-jtag-20261011T055654Z/hardware-run-review.json)

The kernel recorded USB Device 035 disconnecting at **14:48:03 HKT**, followed
by descriptor timeouts (`-110`). XVC reported `LIBUSB_ERROR_IO`, and the host
reported `EOFError: XVC disconnected`. The final receipt's recovery error
comes from the already-poisoned JTAG connection; the console preserves the
original failure. This does not establish a vector arithmetic mismatch or
identify a board/power fault.

Selftest session 77894 is terminal, exit 1. The XVC server was then shut down
through its normal terminal input, session 93293, exit 0. No hardware client
remains from this run. Earlier successful results are historical evidence;
the USB connection must be restored before further hardware checks.

## Continue the complete model test

After restoring a stable cable connection, start the verified XVC server in
a persistent terminal and check the loaded image's identity and calibration.
If the card was power-cycled or the expected MIG image is absent, use the
candidate's guarded `program_candidate.py` with a new receipt directory
before starting XVC. Do not start an initializer while another cable client
is active.

The complete command used in this run was:

```bash
# Run from the root of your OpenTPU checkout.
build/fedora-venv/bin/python -u \
  build/fedora-vivado/mig-jtag-controller-20261010T235833Z/mig_host.py \
  --receipt /path/to/new/physical-selftest.json \
  selftest --model lfm2 --tokens 8 --wformat int8
```

Choose a new existing output directory; preserve the failed receipt. A full
pass requires actual exit 0, every required normal stage passing, healthy ECC,
and a nonempty `model_checks` record with matching physical and ISA token IDs.
The PCIe bandwidth stage remains explicitly skipped on JTAG.

JTAG transfers measured roughly 12–15 kB/s in this run. The model's
242,628,608-byte image alone would take approximately 4.5–5.6 hours at that
rate, in addition to other test traffic. The FPGA's local BIST does not upload
4 GiB through USB, which is why full-capacity BIST completed much faster.


## Native Vivado transport comparison, October 14

The [read-only chain/mailbox probe](../build/fedora-vivado/native-jtag-driver-probe-20261014T043611Z/manifest.json)
passed through Vivado 2026.1's own cable driver. The expected single FPGA,
raw IDCODE and USER2 mailbox magic matched. No image was programmed in this
probe.

A [later native-driver full-memory trial](../build/fedora-vivado/native-jtag-fulltest-20261014T044240Z/manifest.json)
reproduced channel 0 errors: 350,549 bad/uncorrectable beats on the full ones
read at 12:42 HKT. This separates the DDR data failure from the choice of
openFPGALoader versus native Vivado driver; it does not identify the physical
root cause or settle the separate USB dropout. The generated MIG already
enables internal XADC temperature monitoring on channel 0 and shares that
measurement with channel 1.

The [fresh native-driver retry](../build/fedora-vivado/native-jtag-retrained-fulltest-20261014T044514Z/manifest.json)
performs the same guarded SRAM load and then runs the full four-pattern
memory test and normal selftest over native JTAG. It preserves the full
compute profile, 100 MHz core and dual DDR3-1066. TCK is 3 MHz. No flash or
power settings are changed. The helper's localhost RPC allows only fixed
reset, idle and numeric IR/DR scan commands, with failed responses poisoning
the connection. Five wire-level checks passed before this retry started.

## Entirely native Vivado load/test path, October 14 12:54 HKT

The earlier native-test retry still used the historical openFPGALoader
programmer; that load was interrupted by USB loss and actual loader exit -6.
Its printed 100% was not a verified upload. The user then manually reconnected
USB. The current
[native Vivado load/test receipt](../build/fedora-vivado/native-vivado-program-and-fulltest-20261014T045031Z/manifest.json)
uses Vivado for both SRAM programming and subsequent IR/DR transactions.
The original image offline audit passed again. Exactly one FPGA and raw
IDCODE are required before `program_hw_devices`; the new code requires
`REGISTER.IR.BIT4_INIT_COMPLETE` and `REGISTER.IR.BIT5_DONE` before exposing
its memory-test endpoint. These properties are documented in AMD's
[hardware-device reference](https://docs.amd.com/r/en-US/ug912-vivado-properties/HW_DEVICE).
Ten wire-level/Tcl-guard tests passed without hardware access. Real native
SRAM programming and full memory/selftest passes are still pending.

## Full-profile DDR800 candidate and requested compute tests

The native MIG load passed explicit INIT/DONE, but the
[calibrated retest](../build/fedora-vivado/native-vivado-loaded-fulltest-20261014T045831Z/manifest.json)
reported 427,773 bad beats on channel 0's full ones read. The mismatch mask
again centers on bits 48–55. No compute stage ran in that attempt.

The [DDR800 image preflight](../build/fedora-vivado/ddr800-image-preflight-20261014.json)
rechecked frozen image/source witnesses, matching PHY tables and 243 physical
pins; its two CRC checkpoints match. The full compute design and 100 MHz
core remain intact, using the previously planned DDR3-800 LiteDRAM profile.
The [current physical session](../build/fedora-vivado/ddr800-native-matmul-lfm2-20261014T051843Z/manifest.json)
requires healthy full memory before a two-row, 16-output, 256-reduction int8
MM test. All 128 output bytes and retired instructions must match ISA. It
then runs the complete normal selftest with eight physical LFM2 tokens.
The compact MM ISA reference passed; physical results are still pending.

The user authorizes permanent flashing after a successful physical LLM test
and intends to use a PCIe slot in another PC. The current bring-up images
have no PCIe endpoint. Permanent standalone PCIe boot therefore needs a
separate qualified PCIe image and flash/boot-profile checks. No permanent
flash has been written.
