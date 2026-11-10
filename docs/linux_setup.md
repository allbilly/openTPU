# Linux setup and workspace paths

The host tools target Linux and do not select a distribution or package manager.
Install the prerequisites using your distribution's tools. Kernel and hardware
compatibility still need to be verified on the actual PCIe host.

## PCIe runtime host

Vivado and a JTAG cable are optional for a card that already boots its design
from flash. The runtime host needs:

- A compatible PCIe slot, the card's required power and cooling.
- Python 3.10 or newer with virtual-environment support.
- Kernel headers matching the running kernel; a matching C compiler, `make`,
  `git` and `patch` for the pinned XDMA driver. DKMS is optional.
- The matched OpenTPU host/compiler and model checkpoint.

The driver installer detects the kernel build tree and compiler. It binds the
Xilinx XDMA PCIe driver; similarly named in-kernel platform drivers may serve
different hardware.

Use the [PCIe host instructions](permanent_pcie_ch1.md#pcie-host-pc) to capture
cold enumeration, install the matched runtime and run LFM2. The tested model
and driver installer are also available in the locally prepared host archive.
Git does not include model weights or generated bitstreams.

## FPGA build/programming host

Building the reference design requires full Vivado with support for XC7K480T.
JTAG programming requires a compatible cable and the hardware server. The
experimental open-source flow has separate dependencies and qualification
steps in the [OpenXC7 plan](openxc7_bitstream_plan.md).

Run from your checkout root. Public entry points are distribution-neutral:

```bash
python3 tools/ypcb.py --help
python3 tools/ypcb.py build-jtag --help
python3 tools/ypcb.py build-pcie --help
python3 tools/ypcb.py review-pcie --help
python3 tools/ypcb.py program-sram --help
python3 tools/ypcb.py program-flash --help
python3 tools/ypcb.py run-lfm2 --help
```

These commands use the existing implementation helpers. Historical helper,
build-directory and receipt filenames are retained for provenance; they do
not restrict which Linux distribution can run the tools. `--help` does not
program hardware. Actual programming still requires the reviewed image and
its qualification records.

## Configurable tool locations

Scripts discover their checkout from their own file; cloning into another
directory does not require source edits. External executables are found on
`PATH` or through explicit configuration:

| Variable | Meaning |
| --- | --- |
| `VIVADO_ROOT` or `XILINX_VIVADO` | Vivado installation root |
| `OTPU_VIVADO_BIN` or `VIVADO_BIN` | Directory containing Vivado executables |
| `OTPU_YOSYS` | Yosys executable |
| `OTPU_YOSYS_SHARE` | Yosys data directory |
| `OTPU_SLANG` | Slang Yosys plugin |
| `OTPU_WORKSPACE_ROOT` | Parent containing optional neighbouring tool/donor checkouts |
| `YPCB_ROOT` | Shared YPCB tooling checkout |

Set only the overrides needed for your installation. The optional local folder
organization is documented in [workspace layout](workspace_layout.md). Current
documentation uses relative links and variables rather than a developer's
absolute home directory.
