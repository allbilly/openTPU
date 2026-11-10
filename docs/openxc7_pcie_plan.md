# Full OpenTPU PCIe connection

The pinned `pcie_7x` YPCB Gen2 x1 reference ends at a 256-word RAM. Replace
that RAM with a BAR0 command interface, then connect the existing complete
64-byte AXI transfer engine to OpenTPU control, LiteDRAM calibration CSRs,
and the entire 2 GiB address range of each DDR channel. Keep MCOLS=4,
ACT_ROWS=4, LANES=8, VPU_CL=2 and MXU_IMPL=2. This is programmed I/O over
the open endpoint, with its own Linux sysfs BAR transport; it does not
implement the vendor XDMA protocol or its bandwidth.

The standalone USER2 image currently being placed is an independent first
run. Do not change its 111 hashed inputs or restart its native process.
Add a separate PCIe top, BAR mailbox, preparation/elaboration command and
host transport. Derive the endpoint wrapper from the exact pinned source
with source-hash checks, removing the memory stub. Retain upstream PCIe/GTX
logic and licensing. No FPGA backend changes are part of this step.

BAR0 is 4 KiB. All host MMIO is aligned 32-bit, little endian, uncached.
Offsets: 0x00 identity (OTPP), 0x04 ABI (1), 0x08 busy/done/rejected flags,
0x0c submission (sequence[31:16], byte strobes[11:8], opcode[7:0]),
0x10 target byte address, 0x14 response sequence/status, 0x20..0x5c staged
512-bit write payload and 0x80..0xbc retained read payload. Read status
after submission to flush posted writes. Only one transaction may be in
flight. A busy mailbox cannot have its payload/address overwritten;
rejected writes are visible in status bit 2 (write-one-to-clear when idle).
Completion requires done plus the submitted sequence; reconnect rejects a
busy or rejected mailbox. AXI errors and malformed burst completion remain
visible through the existing transfer engine. DDR unaligned writes use its
existing read/modify/write path, preserving the full physical ECC beat.

Cross the complete stable command and result with synchronized toggles.
Both clock domains share asynchronous reset assertion and synchronous reset
release; link reset also resets the accelerator host AXI interfaces. No
multi-bit command is sampled until its synchronized ownership toggle has
arrived. The host cannot submit another command until completion.

Verification must include independent AXI-Lite AW/W acceptance, stalled
responses, asynchronous clocks, reset during a command, rejection while
busy, sequence wrap, AXI errors, both final channel addresses, unaligned
updates, and actual TLP-to-AXI-to-mailbox simulation. Elaborate the entire
accelerator, both real LiteDRAM channels/firmware and open PCIe endpoint.
These gates prepare integration; full synthesis, placement/routing,
strict frame assembly, timing qualification, physical enumeration and
full-capacity DDR/compute operation still require their own evidence.

## Reference wiring corrections after real endpoint elaboration

The real full run `pcie-full-elaborate-real-20261008T0615Z` failed strict
structural checking on 11 undriven bits. Keep the pinned checkout unchanged;
generate two reviewed source copies alongside the exported endpoint:

- Forward PCIE_2_1's existing `pipe_tx_deemph` and `pipe_tx_margin` outputs
  to the corresponding GTX wrapper ports. Do not replace these controls
  with constants: the hard block supplies the requested transmitter settings.
- Drive `cfg_turnoff_ok_w` with the inverse of application `cfg_turnoff_ok`.
  AMD's [power management port definition](https://docs.amd.com/r/en-US/pg054-7series-pcie/Power-Management-Ports)
  specifies `CFGPMTURNOFFOKN` as active low, while the
  [application acknowledgement](https://docs.amd.com/r/en-US/pg054-7series-pcie/PPM-L3-State)
  is active high.
- Connect the real GTX `EYESCANDATAERROR` output to its exposed lane-zero
  status port; retain the reference's single physical GTX channel.
- Set the endpoint's interrupt message number to zero, matching its
  already-disabled interrupt request inputs.

Hash-check original source files, require each patch anchor exactly once,
record original and generated hashes, and run strict real endpoint elaboration
before repeating the complete accelerator/DDR elaboration. Keep structural
checking and full-scope hardware-instance checking enabled.

Route preparation must retain the vendor YPCB `LVCMOS18` settings for
SYS_CLK, PERST, LEDs and I2C. The PCIe example uses `LVCMOS33` on some of
these ordinary I/O pins; its GTX/refclock package-pin assignments can be
reused after package/differential-pair verification. Do not apply an ordinary
GPIO I/O standard to dedicated GTX pads. DDR source constraints and explicit
750 mV VREF bank selections remain required; timing relationships and CDC
qualification remain separate work.
