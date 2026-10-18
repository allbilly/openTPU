# c0182800 Mac runtime handoff

The card was permanently programmed with c0182800, independently verified,
booted from flash and read back as c0182800 on October 18. JTAG was released;
it is ready to power off and move to the Mac. Compute is 100 MHz, DDR800,
capacity 4 GiB, CH0 spare lane 8 with ECC off, CH1 ECC on. Both JTAG and PCIe
runtime memory/control are retained.

Follow [the matching Mac instructions](docs/mac_c0182800.md). The Mac helper
checks the exact live image, calibrates CH0 while preserving CH1, initializes
memory and compares LFM2.5-230M against the ISA. CH0 is deliberately uncalibrated
after fresh boot until that helper runs. Local SRAM TinyStories passed all
eight tokens and exact model/program readback; original Mac LFM remains pending.

This branch is prepared locally and remains unpublished until authorized.
Bitstreams, routed netlists, checkpoints, weights and large logs stay out of Git.
The small runtime metadata contains the image checksum and review binding.
