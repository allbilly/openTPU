# Bitstream locations and build differences

Snapshot: October 15, 2026. Repository: `${OTPU_ROOT}`.
All paths below are relative to this repository. The original build-output
inventory contains 22 `.bit`/`.mcs` files, including older experiments and
bundled loader helpers. The tracked release below copies the current PCIe
images into Git. Exact byte sizes and SHA256 hashes of the original outputs are in
[bitstreams.tsv](bitstreams.tsv).

## Tracked PCIe 2 GiB release

The current CH1-only PCIe release is included in
[`bitstreams/ch1-pcie-2gb/`](../bitstreams/ch1-pcie-2gb/). A clone of this branch
contains the built images and matching DDR800 runtime data:

- [`otpu.bit`](../bitstreams/ch1-pcie-2gb/otpu.bit): load the FPGA's volatile SRAM over JTAG.
- [`otpu.mcs`](../bitstreams/ch1-pcie-2gb/otpu.mcs): the same design in BPI x16 NOR programming format.
- [`core/`](../bitstreams/ch1-pcie-2gb/core/): matched calibration tables and the files checked by `openxc7-profile.json`.
- [`manifest.json`](../bitstreams/ch1-pcie-2gb/manifest.json): target, memory mapping, file hashes and measured qualification scope.
- [`evidence/`](../bitstreams/ch1-pcie-2gb/evidence/): preserved offline review and flash-programming receipts.

Verify the release on macOS before selecting an image:

```sh
cd bitstreams/ch1-pcie-2gb
shasum -a 256 -c SHA256SUMS
```

These images were built with Vivado on Fedora. Loading an existing `.bit` on
macOS needs a working JTAG programmer with DLC10/XC7K480T support, rather than
a local Vivado installation. Confirm the expected IDCODE `0x23751093` and
successful configuration completion. A BPI NOR write additionally requires
support for the actual board flash and its x16 interface; successful `.bit`
SRAM loading alone does not establish that support. The Chestnut PCIe DMA
transport is the runtime connection, not a JTAG programmer.

Select the release's `core/` as the transport's `calibration_data`; the
repository's default tables are DDR1066 and differ from this DDR800 image.
Both logical memory channels use physical CH1, for 2 GiB total. This release
does not repair CH0. Model checkpoints and Python environments are separate.
The experimental PHY reset patch is not part of this release.

## The two current designs

The standalone JTAG image and the permanent PCIe image are **separate Vivado
builds**. Both retain full MCOLS4/ACT_ROWS4/LANES8/VPU_CL2/MXU_IMPL2 compute at
100 MHz and the same CH1-only DDR800 memory core with ECC and 2 GiB usable
memory. Each virtual channel has 1 GiB. The host interfaces differ:

| Design | Runtime host connection | Verified hardware result |
| --- | --- | --- |
| Standalone CH1 JTAG | USER2 JTAG for commands, model weights and results | Warm memory, exact matmul and eight LFM2 tokens passed; answer: “The capital of France is Paris.” |
| CH1 PCIe | Gen2 x8 XDMA through a PCIe slot | Flash programming, separate verification and JTAG-requested flash boot passed; cold boot, PCIe enumeration and PCIe inference remain pending |

The [shared RTL comparison](../build/fedora-vivado/ch1-pcie-all-compute-source-match.json)
records 26 matching shared source files. Matching compute/memory sources do
not establish that the separate PCIe host integration has executed physically.

The three current files are:

```text
# Standalone JTAG image that passed LFM2
build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit

# PCIe design, suitable for loading into FPGA SRAM
build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit

# Same PCIe design packaged for permanent BPI x16 NOR programming
build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.mcs
```

## Design choice and storage choice

The `.mcs` is generated from its matching PCIe `.bit`. It packages the same
configuration data with flash addresses and the BPI byte representation; this
conversion does not synthesize another design. A `.bit` SRAM load lasts until
configuration or power is lost. Programming the matching `.mcs` into NOR
preserves the design for boot. The USER2 JTAG design and PCIe design differ
because their host interfaces were built differently, independently of where
the configuration is stored.

The DLC10 can program either design over JTAG. Runtime commands and model
transfers use the interface included in the chosen design. Temporarily loading
the standalone `.bit` into SRAM leaves the PCIe NOR image intact; booting from
NOR selects the PCIe design again. Model weights reside in volatile DDR and
must be uploaded again after power loss.

## Current hashes, receipts and build helpers

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| [Standalone JTAG .bit](../build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit) | 12,484,177 | `0fc10bf2a6459ca5273b0dc6616e43974209ff0176fa2b95e017626e03f93d21` |
| [PCIe .bit](../bitstreams/ch1-pcie-2gb/otpu.bit) | 12,472,031 | `c7d3891b58d65ba72a3fc67c27c63c8dca3246db55d6504f7a63b636c876d1cf` |
| [PCIe .mcs](../bitstreams/ch1-pcie-2gb/otpu.mcs) | 34,300,540 | `101178a32024ba416f90813afe7672b80e26fb154982d7fec85209bbab2e5f77` |

- [Physical JTAG LFM2 receipt](../build/fedora-vivado/ch1-lfm2-physical-pass-current.json).
- [PCIe image review](../build/fedora-vivado/ch1-pcie-program-review-current.json).
- [Permanent programming receipt](../build/fedora-vivado/ch1-permanent-pcie-audited-current.json): October 15, 07:44–07:52:56 HKT; 8 minutes 47 seconds; backup skipped at the user's request.
- [Standalone build helper](../tools/fedora_build_vivado_ch1_jtag.py) and [resume helper](../tools/fedora_resume_vivado_ch1_jtag.py).
- [PCIe build helper](../tools/fedora_build_vivado_ch1_recovery.py), [frozen build record](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/manifest.json) and [flash programmer](../tools/fedora_flash_ch1_pcie.py).

For programming details and PCIe host/model commands, use
[permanent PCIe boot](permanent_pcie_ch1.md). The
[Vivado guide](vivado_bitstream_guide.md) also retains the older MIG rebuild
procedure. The matched portable host/model archive is
[the PCIe LFM2 host bundle](../build/fedora-vivado/ch1-pcie-flash-host-20261015.tar);
it contains the host/compiler/model and calibration data, with no bitstream.

## Testing on this machine

This Fedora machine can perform JTAG programming and flash checks. LFM2 has
already passed here using the standalone JTAG design. The PCIe design's
runtime needs a physical PCIe link: this machine can host it if the card is
installed in its PCIe slot, or the selected other Linux PC can host it. A
separately powered card with only a DLC10 USB connection supplies JTAG access.
It does not provide the PCIe data link. Cold-boot enumeration and model testing
instructions are in the [PCIe host guide](permanent_pcie_ch1.md#pcie-host-pc).

## Full file inventory

The groups below describe purpose and measured status. Files marked as corrupted
are intentional checker test inputs. The bundled Spartan-6 loader bitstreams
target different FPGA parts and are not YPCB accelerator images.

### Current CH1 images

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit](../build/fedora-vivado/ch1-jtag-resume-20261014T105300Z/otpu-ch1-jtag.bit) | 12,484,177 | Standalone CH1 USER2 JTAG image; physical matmul and LFM2 passed |
| [build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.bit) | 12,472,031 | Current CH1 PCIe SRAM-format image; flash/verify/JTAG boot passed; PCIe inference pending |
| [build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.mcs](../build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z/project/otpu.mcs) | 34,300,540 | Current CH1 PCIe BPI x16 flash-format image; used for permanent programming |

### Historical Vivado images

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-vivado/mig-jtag-controller-20261010T235833Z/implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit](../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit) | 12,870,600 | Historical dual-channel MIG JTAG image; later warm DDR failures; superseded by CH1 recovery |
| [build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.bit](../build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.bit) | 11,638,155 | Earlier dual-channel DDR800 PCIe build; accesses CH0; superseded by CH1 recovery |
| [build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.mcs](../build/fedora-vivado/pcie-native-ddr800-full-20261014T060325Z/project/otpu.mcs) | 32,007,176 | Earlier dual-channel DDR800 PCIe build; accesses CH0; superseded by CH1 recovery |
| [build/fedora-vivado/physical-jtag-20261010T133821Z/clock-diagnostic-20261010T1435Z/diagnostic.bit](../build/fedora-vivado/physical-jtag-20261010T133821Z/clock-diagnostic-20261010T1435Z/diagnostic.bit) | 11,599,613 | Historical clock diagnostic image; full LFM2 unverified |

### Experimental and test images

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrected-dsp-fixture-with-crc.bit](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrected-dsp-fixture-with-crc.bit) | 18,735,219 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_crc_value.bit](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_crc_value.bit) | 18,735,219 | Deliberately corrupted negative test fixture for image/CRC checker |
| [build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_frame_data.bit](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/corrupt_frame_data.bit) | 18,735,219 | Deliberately corrupted negative test fixture for image/CRC checker |
| [build/fedora-openxc7/clock-codec-check-20261012T133557Z/clock-diagnostic.bit](../build/fedora-openxc7/clock-codec-check-20261012T133557Z/clock-diagnostic.bit) | 18,735,213 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/crc-image-fixture-check-20261013T152400Z/design-with-crc.bit](../build/fedora-openxc7/crc-image-fixture-check-20261013T152400Z/design-with-crc.bit) | 18,735,219 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/dsp-corrected-fixture-image-runtime-fixed-20261013T140200Z/corrected-dsp-fixture.bit](../build/fedora-openxc7/dsp-corrected-fixture-image-runtime-fixed-20261013T140200Z/corrected-dsp-fixture.bit) | 18,735,219 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/dsp-mode-feasibility-20261006T191434Z/probe.bit](../build/fedora-openxc7/dsp-mode-feasibility-20261006T191434Z/probe.bit) | 18,735,198 | Clock/DSP/CRC experiment or test fixture; physical LFM2 unverified |
| [build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/full-mapped-reference.bit](../build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z/full-mapped-reference.bit) | 18,735,238 | OpenXC7-mapped netlist implemented by Vivado; reference image, physical inference unverified |
| [build/fedora-openxc7/pcie-image-checker-validation-20261008T065925Z/corrupt-first-frame.bit](../build/fedora-openxc7/pcie-image-checker-validation-20261008T065925Z/corrupt-first-frame.bit) | 18,735,177 | Deliberately corrupted negative test fixture for image/CRC checker |

### Bundled loader helpers

| File | Bytes | Purpose / status |
| --- | ---: | --- |
| [build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit) | 3,318,013 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181633Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit) | 1,484,501 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit) | 3,318,013 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit](../build/fedora-openxc7/xpcu-xvc-20261006T181726Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit) | 1,484,501 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit](../build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx100fgg484.bit) | 3,318,013 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |
| [build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit](../build/fedora-openxc7/xpcu-xvc-20261011T165026Z/source/spiOverJtag/spiOverJtag_xc6slx45csg324.bit) | 1,484,501 | Third-party Spartan-6 SPI loader helper; targets XC6SLX rather than this XC7K480T |

## Refresh the inventory

The build directories are ignored by Git. Include ignored files when searching:

```bash
# Run from the root of your OpenTPU checkout.
rg --files --hidden --no-ignore build -g '*.bit' -g '*.mcs'
```

This snapshot covers FPGA configuration `.bit` and flash `.mcs` files in this
checkout. Calibration firmware, model data and incomplete old-flash readbacks
also use `.bin`; those are different artifacts and are outside this index.
