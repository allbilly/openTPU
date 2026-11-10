# RAM-only MIG DDR3-800 address diagnostic

Experimental SRAM image for investigating the physical CH0 fault. Build ID
`c0161001`, status identity `RAMT` (`0x52414d54`), snapshot ABI 1.

The image contains two vendor MIG controllers, their traffic generators and
USER2 JTAG status. Each channel has 2 GiB payload capacity, 72 physical DQ pins
and ECC enabled. Both channels run address-pattern traffic: initialize memory
once, then repeat full-range reads. Corrected ECC events fail the test as well
as uncorrectable events and data mismatches. The image contains no accelerator
or PCIe endpoint.

## Qualification scope

Read `manifest.json` and `evidence/offline-review.json` for this exact image's
hash, timing, route, pin, CRC and CDC review. **Physical RAM tests and Mac
programming/status readback are pending.** A completed build does not establish
that either channel passes on the card or that CH0 has been repaired.

The traffic model covers 128 KiB with independent command/data stalls. It is
separate from the physical 2-GiB/channel coverage counters. Deliberate DQ48
corruption checks the sticky lane mask, failed-compare count and their snapshot.
The vendor's first-error address/data record is misaligned and marked
unverified; use the sticky lane/ECC/cycle counts for this initial experiment.

The retained CDC report includes vendor reset-combiner and temperature-bus
findings, plus held mailbox payloads. The review records their scope and the
four constrained payload crossings. It does not claim an empty CDC report.

## Verify and load on Mac

```bash
cd bitstreams/ramtest-mig-ddr800-address
shasum -a 256 -c SHA256SUMS
```

Load `ramtest.bit` into volatile SRAM using the working JTAG programmer. The
Mac does not need Vivado. Keep the CH1 PCIe image in NOR. This RAM-only image
requires USER2 JTAG status access; Chestnut's PCIe runtime adapter cannot read
it. The [Mac procedure](../../docs/ddr_ram_only_debug.md#establish-mac-programming-and-status-access)
includes the existing XPCU server extension and its build commands.

With the RAM image loaded and its local XVC server running, from the repository
root and the Mac environment already containing NumPy:

```bash
build/chestnut-lfm/venv/bin/python tools/probe_ramtest_mig.py \
  --host localhost --port 3721 --expect-build-id c0161001 \
  --seconds 300 --out build/ramtest-address-cold-1
```

Return that run's `manifest.json` and `samples.jsonl`. Repeat with a fresh output
directory while warm, without retraining during the observation. The FPGA die
sensor does not measure the DRAM chips' temperatures.

## Rebuild on Fedora

From the repository root, with Vivado 2026.1 and Kintex-7 support:

```bash
python3 tools/fedora_build_ramtest_mig.py \
  --ddr-mts 800 --channels both --pattern address --build-id c0161001 \
  --out build/ramtest-mig800-address-rebuild
```

The output directory must be new. The builder generates the vendor RTL from
the tracked MIG XML, snapshots source, implements the design and checks timing,
DRC, expected PHY structure, packet contents, independent CRC and bus skew.
Review the generated reports. Require manifest status
`RAM_ONLY_BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING`.

Other patterns, isolated channel traffic, cold/warm repetitions and a matched
RAM-only LiteDRAM image remain follow-up experiments in the
[debug plan](../../docs/ddr_ram_only_debug.md).
