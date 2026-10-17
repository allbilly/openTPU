# CH0 calibration firmware for the lane-8 spare image

Experimental **firmware**, not an FPGA bitstream. `selfcal.bin` runs in the
existing calibration CPU RAM of `../ramtest-litedram-ddr800-spare8/ramtest.bit`
(build `c0172060`). Its firmware ID is `c0172068`.

It calibrates only CH0 with eight physical byte groups and four CSR words per
DFI phase. Each phase's raw BIST check writes and reads one 64-byte word.
CH1's existing nine-lane calibration must finish before this override is used.
CH0 has no ECC in this configuration. A passing calibration does not qualify
memory capacity, partial writes or sustained traffic.

The compiled RV32I image is 9,156 bytes. The same C code compiled for the host
matched an independently adapted Python calibration reference for ordinary,
per-bit framing and missing-lane-window scenarios. All CSR write sequences
matched (over 1.5 million writes); the failed-lane case correctly failed.
This model does not execute the RV32 binary or test a physical FPGA.

## Rebuild

From the repository root, with a compatible RV32I cross compiler:

```bash
python3 tools/prepare_ramtest_spare_calibration.py \
  --package bitstreams/ramtest-litedram-ddr800-spare8 \
  --out build/spare-ch0-firmware-new --rv-cc /path/to/riscv64-elf-gcc
python3 tools/check_ramtest_spare_calibration.py \
  --build build/spare-ch0-firmware-new \
  --out build/checks/spare-ch0-firmware-new
```

The cross compiler's matching objcopy and objdump must also be available.
A container wrapper must mount the output directory writable. Host model
checks require a C compiler and the repository Python dependencies.

## Loading boundary

A matched host procedure must check the loaded bitstream ID and package hash,
wait for CH1 calibration, stop native traffic, save CH1's results, and hold the
calibration CPU. `opentpu.host.selfcal.load` writes and verifies firmware RAM;
setting the channel mask to CH0 and releasing the CPU starts calibration.
Save the new mailbox using `core/sdram_init.py`, which describes eight lanes.
Do not run a generic nine-lane calibration command against CH0.

The override is volatile: reconfiguring the FPGA restores its packaged
CH1-only firmware. This package does not authorize or perform flash writes.
Physical upload and memory validation are pending.
