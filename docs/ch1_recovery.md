# CH1-only recovery for physical LFM2

Physical LFM2.5-230M inference passed on healthy DDR channel 1 at
**October 15, 00:36 HKT**. The FPGA answered **“The capital of France is Paris.”**
All eight tokens matched the fresh ISA reference, and ECC remained enabled
with zero corrected or uncorrectable errors. The
[audited result](../build/fedora-vivado/ch1-lfm2-physical-pass-current.json)
also records the 32-word exact physical matmul and full-capacity memory checks.
The next requested work is CH0 DDR recovery and permanent PCIe boot.
The full compute profile stays MCOLS4, ACT_ROWS4, LANES8, VPU_CL2, MXU_IMPL2,
100 MHz and DDR800. Usable memory is **2 GiB**, with **1 GiB per virtual
channel**. This is a recovery mode, not a repair of physical channel 0.

## First run: JTAG only

Current choice (October 14, 20:29 HKT): keep the card separately powered and
transfer the full LFM2 model through the native Vivado USER2 JTAG mailbox.
The CH1-only standalone image retains the complete compute configuration.
The PCIe image and host bundle below are for later PCIe testing.

[Current JTAG build](../build/fedora-vivado/ch1-jtag-current.json) resumes the
completed synthesis checkpoint. The clock alias removed during synthesis was
replaced by its MMCM output pin; the required frequency remains 100 MHz.
The first resume's `NAME`/`TOP` metadata mismatch is also corrected in the fresh
attempt. Board primary-clock constraints precede DDR generated-clock uncertainty.
The standalone top shares the same 100 MHz clock between core, controller-user
and host-AXI interfaces. Synthesis merges their aliases; the isolated memory
constraint snapshot binds all three to that verified clock and is sourced under
each channel's `current_instance`. Constraint loading now completes without
critical warnings. Placement subsequently passed in 16 minutes 11 seconds
with zero warnings or errors; the correct-part/top placed checkpoint is saved.
Routing and post-route optimization passed. The final image passed all
route/timing/DRC/pin/CRC/CDC and 30 bus-skew checks. See the
[placement receipt](../build/fedora-vivado/ch1-jtag-placement-pass-20261014T111200Z.json). Scoped waivers follow
[AMD's documented current-instance behavior](https://docs.amd.com/r/2023.2-English/ug835-vivado-tcl-commands/create_waiver).

[Automatic physical runner](../build/fedora-vivado/ch1-jtag-lfm2-current.json)
waits for this exact build, checks source/pins/routing/timing/DRC/CRC/CDC, programs
SRAM, calibrates and soaks CH1, verifies compact matmul, and runs full LFM2 with
actual tokens saved as they arrive. It contains no flash operations. The bitstream is now built and qualified, and SRAM programming passed. The
first new-image run calibrated CH1 in 8.26 seconds and passed 204 full-capacity
checks over 92.42 seconds. It stopped before matmul because the software guard
confused VERSION at 0x04 with STATUS at 0x0c. That guard is corrected and six
regression tests passed. Subsequent real matmul matched all 32 output values
and five instructions exactly. The full prepared LFM2 image finished uploading
at approximately 00:33 HKT, and physical generation took 161.27 seconds.
Short hardware comparisons found the existing 3 MHz, three-RPC protocol fastest;
all compared readbacks were exact and ECC counters stayed zero. At 14–15 kB/s,
243 MB takes approximately 4½ hours to upload. The actual eight-token
comparison and final ECC checks have now passed.
See the [hardware handoff](../build/fedora-vivado/ch1-jtag-hardware-handoff-20261014T114400Z.json).

The completed run's observer command is preserved below. It does not restart
the runner or open another JTAG client:

```sh
# Run from the root of your OpenTPU checkout.
python3 -u tools/fedora_observe_ch1_lfm2.py \
  --pid 950546 --invocation ad0bce9949964bb3994fbec5e28da4be \
  --samples 16 --interval 55
```

The observer checks the service invocation, PID and process arguments, reads
the runner's manifests, and writes only separate observation receipts. It
does not start, stop, recalibrate or program the FPGA. Its upload estimate
excludes inference and ISA comparison. A zero observer exit code is not an
inference pass; inspect the actual model result. For a replacement run, verify
and supply its new PID and invocation before observing it.

## Power cycles and model transfer

The completed model upload wrote weights into volatile DDR, not flash. A power
cycle clears them, so the model must be uploaded again. The current FPGA
configuration is also an SRAM load and must be reloaded after power loss.
DDR retains the data while powered and refreshed; resets, calibration tests
or scrubbing can overwrite it. Starting a new Engine with the current host
software loads its model image again.

A qualified PCIe bitstream can later be programmed into configuration flash
to load the FPGA design at power-on. That preserves the design, not the model
weights. With the card installed in a PCIe host and a working boot image,
enumeration does not require model weights to have been loaded.

The host already supports model transfer through the XDMA PCIe transport
(`XdmaTransport`, `/dev/xdma0_h2c_0`). This avoids the current JTAG mailbox's
64-byte acknowledged transfers. The CH1 PCIe image is built, but final
qualification, Linux driver setup and physical PCIe testing remain pending.
Its transfer speed on this card has not yet been measured. Keep the present
JTAG run powered and unchanged until it completes.

## Physical evidence

[Warm CH1 test](../build/fedora-vivado/ch1-physical-warm-soak-20261014T080444Z/manifest.json)
passed at approximately 54 degrees C: 90.91 seconds, 180 full 2 GiB BIST
passes, zero data errors on all nine byte lanes, 24,576 bytes of normal-port
readback, and zero corrected/uncorrectable ECC counters. No compute or model
pass is implied by that memory result.

[On-board warm calibration](../build/fedora-vivado/ddr800-cpu-warm-model-first-20261014T073754Z/calibration.log)
previously completed in 8.11/8.30 seconds per channel at 53.4 degrees C.
CH1 passed; CH0 lane 6 had no passing timing window. USB stayed connected in
that attempt. Earlier reload/recalibration temporarily recovered full 4 GiB
tests, but channel 0 errors returned as the card warmed.

## Upstream DDR recovery reference

The current recovery core already uses the upstream WL7DDRPHY LiteDRAM path
and on-board calibration firmware (`--phy wl --selfcal`). Switching to LiteDRAM
is therefore not a remaining step. The latest physical CH1 result includes
per-lane read taps/bitslips, per-bit framing offsets, write-latency results and
a selected CK phase/window in the
[current model manifest](../build/fedora-vivado/ch1-jtag-lfm2-20261014T120700Z/model/manifest.json).

Upstream records its original CH0 lane 3 and CH1 lane 6–7 issues in
[board.md section 6](https://github.com/FeSens/openTPU/blob/main/docs/board.md),
and later dual-channel calibration and warm qualification in
[litedram.md](https://github.com/FeSens/openTPU/blob/main/docs/litedram.md).
Those are measurements on the developers' card. Our warm CH0 lane 6 failure
does not establish the same cause or prove permanent damage to the memory.

After the current full-model JTAG run, compare the frozen generator, PHY and
calibration firmware with the isolated upstream checkout at `e15b4a44`, record
CH0's cold/warm lane windows and per-bit offsets, and test any candidate change
in a separate SRAM image. Accept dual-channel recovery only after warm memory
tests, clean ECC counters and physical inference pass on this card. Preserve
the working CH1 bitstream and full compute configuration as the fallback.

## Memory mapping

The normal design splits every 128-byte accelerator chunk into two 64-byte
transfers. `CHASH=0` changes hashing; it does not remove interleaving. Allocating
only 243 MB with that image therefore still accesses physical CH0.

The recovery generator connects all four virtual native ports to physical
CH1's crossbar and shared ECC decoder. LiteDRAM arbitrates requests and keeps
each port's responses associated with its requester. Both host DMA and core
requests pass through the same remapping:

```text
physical CH1 beat = (virtual beat << 1) | virtual channel
virtual beat < 2^24
```

The calibration CPU starts with mask `0b10`, selecting physical CH1. Both
virtual ready flags reflect CH1's readiness; physical CH0's own calibration
CSR remains separate. The recovery marker at BAR0 offset `0x5c` is
`0x08000102`: 2048 MiB, ABI 1, physical channel mask 2.

The recovery host rejects transfers beyond 1 GiB in either virtual channel and
compiles the model with a 2 GiB capacity. Its marker check rejects the existing
dual-channel images before recovery tests. Generic tools assuming 4 GiB should
not be used for this image. The full LFM2 prepared image is 242,628,608 bytes.

## Current artifacts and verification

- [Generated recovery core](../build/fedora-vivado/ch1-core-writable-20261014T082631Z/manifest.json):
  firmware, Verilog, matching calibration tables, CSR/port ABI and reference CPU
  checks passed. The firmware occupies 10,232 of 16,384 bytes.
- [Four-port ECC comparison](../build/fedora-vivado/ch1-recovery-prepare-20261014T075931Z/four-port-ecc.log):
  1,500 random cycles against four stock frontends, including ready/valid,
  encoding, corrected/uncorrectable reads and counters. All 1,500 cycles passed;
  `four-port-ecc.exit` is zero and the log ends in `PASS`. Its reported 1,582
  corrected words and 1,548 uncorrectable reads are intentionally injected test
  stimuli. The parent preparation command later failed in an unused generator;
  the selected separately generated core uses these same verified ECC sources.
- [Recovery PCIe Vivado build](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/manifest.json):
  synthesis and placement completed; routing remains in progress as a secondary
  reference. Route/timing/DRC, image and configuration checks remain required
  before that PCIe image may be programmed.
- [Recovery host runner](../tools/fedora_run_ch1_lfm2.py): seven host guard tests
  passed; physical matmul and model execution have not yet run with this image.

Core-generation failures were preserved separately: an import syntax error,
a relocated firmware helper's relative path, and the old compiler container's
read-only output mount. The selected attempt corrects those paths and grants
the compiler write access only to its new output directory. Existing cores,
toolchain wrappers and routed references were preserved.

## Later PCIe run on the other Linux PC

After the recovery image has passed its offline checks and is loaded into SRAM
with the card in a PCIe slot, use the matching host source and model checkpoint.
Install/check the repository's XDMA driver as described in [host.md](host.md).
The card should expose `10ee:7028`, subsystem `10ee:4f54`, class `120000`.

The following is the test command, not evidence of a completed run. `CORE_DIR`
is the copied generated recovery core, including `openxc7-profile.json` and
its five pinned files. Use a fresh result directory:

```bash
cd /path/to/matching/openTPU
build/fedora-venv/bin/python tools/fedora_run_ch1_lfm2.py \
  --dev /dev/xdma0 --core CORE_DIR --out build/ch1-lfm2-results --model lfm2
```

The runner verifies identity/capacity, restarts physical CH1 calibration,
performs a warm full-channel memory test, initializes ECC, verifies matmul
against ISA, and then executes full LFM2. Its eight generated tokens must
match ISA and answer “The capital of France is Paris.” Results are saved before
asserting comparisons. `--preflight-only` checks identity and does not run the
model. No command here writes FPGA SRAM or flash.

Permanent flash remains conditional on physical LLM success, a qualified PCIe
image, confirmed flash identity, a preserved backup, verify and cold boot.

## Git state

The pull fetched `e15b4a44` but left the original worktree at `5b1e646c`
because local changes overlap upstream. A separate clean checkout exists at
`${YPCB_ROOT}/projects/openTPU-upstream-e15b4a44`. Local changes and active jobs
were preserved. The recovery build uses the current matched source snapshot;
the new upstream checkout is not evidence of hardware qualification.

## Portable full LFM2 bundle prepared October 14

The card is currently separately powered with JTAG only, as confirmed by the
user. The recovery image being built uses PCIe for the host, so this image's
physical inference requires installation in the other Linux PC. The existing
JTAG mailbox image still accesses the faulty physical channel 0.

The [matched archive](../build/fedora-vivado/ch1-lfm2-host-20261014T093000Z.tar)
contains the full checkpoint, exact host/compiler snapshot, CH1 core and runtime
package lock. Its checksum inventory and copied CLI checks passed. No bitstream
is included, and no physical inference pass is implied. After qualified SRAM
loading on the PCIe-connected card, extract the archive on the other PC:

```bash
tar -xf ch1-lfm2-host-20261014T093000Z.tar
cd ch1-lfm2-host-20261014T093000Z
./prepare_env.sh
bash opentpu/host/setup_pcie.sh
bash opentpu/host/setup_pcie.sh --rescan
./run_lfm2.sh --dev /dev/xdma0 --out results-lfm2
```

Read `results-lfm2/manifest.json` and retain it. The success status must be
`PASS_PHYSICAL_CH1_RECOVERY_MATMUL_AND_LFM2`. The runner checks physical warm
memory and matmul before generating and comparing full LFM2 tokens.
The checkpoint remains `f630da86651136c9aee893b04b7542007e90fdd718355358e57e7ecc31517cfd`.

The [image audit follower](../build/fedora-vivado/ch1-image-qualification-20261014T093346Z/manifest.json)
is live and waits for full build/ECC completion. Its initial implementation and
parser checks passed; actual recovery-image qualification remains pending.

## Native SRAM loader prepared

[The PCIe SRAM loader](../tools/fedora_program_ch1_sram.py) loads the qualified
bitstream through Vivado's native DLC10 driver. It checks exactly one XC7K480T,
raw IDCODE `0x23751093`, INIT and DONE, then checks IDCODE again. It does not
request a USER2 mailbox after loading this PCIe image. It contains no flash
operations. Eight mocked Tcl guard tests passed; physical loading has not run.

The loader requires completed image qualification and a matching CDC/bus-skew
review receipt. It can perform receipt-only preflight with `--preflight-only`.
The current build/audit are still live, so those programming prerequisites are
pending. After SRAM loading on the PCIe-connected card, run the matching host
bundle as described above. SRAM success alone is not an LFM2 pass.
