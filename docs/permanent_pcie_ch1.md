# Permanent CH1 PCIe boot

The user deferred CH0 DDR repair on October 15 and selected permanent PCIe
programming of the CH1-only image. LFM2 has already passed on the physical
FPGA through the standalone JTAG image; PCIe enumeration and inference on the
other PC remain separate gates.

## PCIe build, JTAG build and flash format

The permanent PCIe image is a separate Vivado build from the standalone JTAG
image that passed LFM2. Both use the same compute RTL and CH1-only DDR800 memory
core, with 2 GiB usable memory. Their runtime host interfaces differ:

| Image | Runtime model/command transfers | Verified result |
| --- | --- | --- |
| `otpu-ch1-jtag.bit` | USER2 JTAG, no PCIe host needed | Physical matmul and eight exact LFM2 tokens passed |
| PCIe `otpu.bit` | Gen2 x8 XDMA over a physical PCIe connection | Offline image review, flash write, separate verification and JTAG-requested flash boot passed; PCIe inference pending |
| PCIe `otpu.mcs` | Same PCIe design, packaged for BPI x16 NOR programming | This is the file used for permanent programming |

The `.mcs` is generated from the matching PCIe `.bit`; converting it does not
build another accelerator. A `.bit` can be loaded into volatile FPGA SRAM;
the matching `.mcs` stores that design in NOR for subsequent boot. Thus the
separate build provides PCIe, while flash storage provides persistence.
JTAG can program either image; that programming connection does not give the
PCIe design the standalone image's USER2 model-transfer interface.

See the [bitstream index](bitstreams.md) for exact paths, hashes, build helpers,
and all 22 local `.bit`/`.mcs` files. Model weights remain in volatile DDR and
must be uploaded again after power loss.

The reviewed image is
`build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit`:
SHA256 `c7d3891b58d65ba72a3fc67c27c63c8dca3246db55d6504f7a63b636c876d1cf`.
Its matching BPI x16 `otpu.mcs` has SHA256
`101178a32024ba416f90813afe7672b80e26fb154982d7fec85209bbab2e5f77`.
The image retains full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 compute at
100 MHz, DDR800, Gen2 x8 XDMA, and 2 GiB usable physical CH1 memory. Each
virtual channel is limited to 1 GiB; BAR0 offset `0x5c` reads `0x08000102`.
The memory core and compute/control RTL match the image that passed physical
LFM2 exactly. [Current image review](../build/fedora-vivado/ch1-pcie-program-review-current.json).

The reset review qualifies configuration startup and normal runtime. The
unused LiteX global SoC reset CSR has an unqualified narrow pulse crossing;
the supported host tools never write it. Use configuration reload or power
cycling instead of that CSR. PCIe reset does not reset the LiteDRAM MMCMs.

## Programming on Linux

`tools/fedora_flash_ch1_pcie.py` checks the image/review and physical LFM2
witnesses, detects one cable and the expected raw IDCODE `0x23751093`, uses
Vivado's flash-access core. By default it reads all 64 MiB of pre-existing
flash twice and requires matching hashes. The origin of that old image is
unverified; it is not known to be factory firmware.

The user explicitly requested skipping the old contents on October 15.
`--skip-backup` records that choice and omits both reads; it retains all image,
physical LFM2, target-ID and flash-part checks. The earlier read-only backup was
intentionally stopped before any erase/write. Vivado's normal configuration-memory
part checking stays enabled; no ID-check bypass is used.

The explicitly authorized workflow erases and writes
the MCS-covered range, verifies it, runs a second verify-only operation, and
requests boot from flash through JTAG. No DRAM diagnostic is performed.

```bash
# Run from the root of your OpenTPU checkout.
python3 tools/ypcb.py program-flash --skip-backup --wait-usb 300
```

Use the [current flash receipt](../build/fedora-vivado/ch1-permanent-pcie-current.json)
to find the run directory. Only
`PASS_PERMANENT_CH1_PCIE_FLASH_VERIFIED_JTAG_BOOT_COLD_PCIE_TEST_PENDING`
establishes programming, verification and JTAG-requested boot. A waiting
process or offline image review is not a flash result. An interrupted write
must be treated as potentially partial and recovered through JTAG.

## Verified flash result

On October 15 the explicit `--skip-backup` run completed in 8.8 minutes:
program/verify, a separate verify-only operation, and JTAG-requested boot from
flash all returned exit zero and their actual success acknowledgements.
INIT and DONE were asserted after boot. [Audited flash receipt](../build/fedora-vivado/ch1-permanent-pcie-audited-current.json).
The selected bitstream and MCS hashes still match the reviewed files.

This result does not establish cold power-on boot or PCIe enumeration on the
other PC. The eight-token physical LFM2 proof was from the standalone JTAG
image with identical compute/memory RTL; PCIe inference is the next test.

## PCIe host PC

The PCIe host can be this Fedora machine if the card is connected to its PCIe
slot. The selected plan uses the other Linux PC. A separately powered card
connected only through the DLC10 has no PCIe data link; JTAG flash checks and
the earlier standalone JTAG inference do not verify the PCIe runtime path.

The matched host/model/core archive is
`build/fedora-vivado/ch1-pcie-flash-host-20261015.tar`, 490,752,000 bytes,
SHA256 `b1064fb45b51a54d85ae81bafb2ec0187d938523bda1e098d595446a0f7b9e3a`.
It contains host/compiler source, the full LFM2 checkpoint, calibration tables
and the pinned-driver installer. It never programs the FPGA.

The archive was extracted into a fresh directory and checked independently:
all checksums passed, the CLI started, and its own host/compiler/model produced
the eight verified ISA tokens using isolated Python and eight CPU threads.
[Portable host receipt](../build/fedora-vivado/ch1-pcie-portable-audit-current.json).
This establishes portable software execution; physical PCIe remains untested.

Flash verification has passed. Power off the card and the other PC, install
the card, and start the PC with JTAG disconnected. Copy the archive there and
verify its SHA256 against the value above before extracting it:

```bash
sha256sum ch1-pcie-flash-host-20261015.tar
tar -xf ch1-pcie-flash-host-20261015.tar
cd ch1-pcie-flash-host-20261015
mkdir boot-evidence-1
date -Is > boot-evidence-1/time.txt
uname -a > boot-evidence-1/kernel.txt
cat /proc/sys/kernel/random/boot_id > boot-evidence-1/boot-id.txt
lspci -Dnn | tee boot-evidence-1/lspci.txt
lspci -t > boot-evidence-1/pci-tree.txt
grep -Ei '10ee:7028|xilinx' boot-evidence-1/lspci.txt
```

Capture this initial enumeration before driver installation, a rescan, or a
warm reboot. Record that the card's power was off before startup and JTAG was
disconnected. A new Linux boot ID alone does not prove that FPGA power was
removed. The expected endpoint is `10ee:7028`, subsystem `10ee:4f54`, class
`120000` (processing accelerator).

When that endpoint is present, install the matched host and driver, then run:

```bash
set -o pipefail
./prepare_env.sh
bash opentpu/host/setup_pcie.sh | tee boot-evidence-1/driver-install.txt
bash opentpu/host/setup_pcie.sh --check | tee boot-evidence-1/driver-check.txt
./run_lfm2.sh --dev /dev/xdma0 --out results-lfm2-cold-boot
```

Select the actual XDMA device index if it is not zero. Driver setup uses sudo
and requires the running kernel's headers/build tools; see [host setup](host.md).
The normal installer binds an already enumerated card; a rescan is not required
for that path. If the endpoint is absent or the ID reads `0xffffffff`, retain
the initial evidence and kernel logs before attempting the documented recovery:

```bash
sudo dmesg > boot-evidence-1/dmesg-before-rescan.txt
bash opentpu/host/setup_pcie.sh --rescan | tee boot-evidence-1/rescan.txt
```

A successful rescan is recovery evidence; it does not establish enumeration
during the original cold boot. Configuration rate and host boot ordering can
affect cold enumeration; a missing endpoint alone does not prove failed flash
programming.

The required runtime status is `PASS_PHYSICAL_CH1_RECOVERY_MATMUL_AND_LFM2` in
`results-lfm2-cold-boot/manifest.json`: warm CH1 memory checks, exact matmul,
eight hardware tokens equal to ISA, Paris in the answer, ECC enabled and zero
corrected/uncorrectable errors. Save those results and then repeat after a
second cold power cycle without JTAG to verify persistent boot. Use fresh
`boot-evidence-2` and `results-lfm2-cold-boot-2` directories for that run. Retain
both boot-evidence directories and both model result directories for review.

Flash preserves the FPGA design. DDR model weights remain volatile and are
uploaded again over PCIe after power loss; they are not stored in NOR.
