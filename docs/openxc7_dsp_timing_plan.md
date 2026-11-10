# Importing the full-design DSP timing data

The running full OpenTPU route has no numerical DSP timing model. Vivado has
now characterized all 15 complete DSP configurations in the 717-DSP source
checkpoint. Prepare an independently reviewable table before changing the
backend. The current native processes, their binary, and their pinned inputs
continue unchanged.

1. Verify the characterization's native exit, part, parameter comparison,
   source hashes and complete configuration coverage. Retain every declared
   parameter, including mask, pattern, register controls and inversions.
2. Convert each logical bit pin to the packed DSP pin name using the existing
   xc7 packer's bracket-removal rule. Reject ambiguous names, invalid pin
   directions, unsupported arc types and unmatched clocks or transitions.
3. Separate combinational arcs, setup/hold checks and clock-to-output arcs.
   Preserve mixed combinational and sequential behavior on the same pin.
   Keep signed delays, including negative hold values. Convert nanoseconds to
   integer picoseconds with outward rounding, preserving rise/fall bounds
   separately for the fast and slow corners. A derived envelope includes both
   corners; fast-min need not be below slow-max for signed hold checks.
   Record how repeated arcs for an identical pin pair were combined.
4. Process configurations with up to eight CPU workers. Emit parameter-specific
   tables and a provenance manifest; validate coverage against the original
   raw vendor TSV independently. A malformed input must fail without publishing
   a successful table.
5. In a separate, owned backend copy, implement the xc7 timing callbacks for
   those exact configurations. Match every parameter with declared defaults;
   reject unsupported modes rather than inventing delays. Preserve the existing
   fabric falling-edge correction and the non-xilinx architecture interfaces.
6. Validate registered, unregistered and mixed DSP configurations against
   native Vivado paths before using that backend for a new full implementation.

The first table is preparation for step 5, not a qualified backend or a claim
of full-board timing closure. Serializer clock/CLKDIV behavior, both DDR edges,
MMCM phase relationships, the Kintex LUT/FF model, clock uncertainty and reset
constraints remain separate requirements. The complete 100 MHz core and both
DDR800 channels are retained.

Source evidence: [configuration characterization](../build/fedora-openxc7/full-dsp-config-vivado-timing-20261011T213448Z/manifest.json)
and [corrected semantic summary](../build/fedora-openxc7/full-dsp-config-vivado-timing-20261011T213448Z/semantic-summary-v2.json).

Steps 1–4 completed on October 12, 2026: the [prepared tables](../build/fedora-openxc7/full-dsp-timing-tables-20261011T221105Z/manifest.json)
contain all 122,150 arcs with zero differences from the raw vendor bounds.
The standalone stdlib converter is `tools/openxc7_dsp_timing_tables.py` and
accepts `--source`, a new `--out` directory and `--workers 8`. It refuses to
overwrite an existing output. The manifest and copied helper retain exact
input/output hashes; `native.exit` records the actual subprocess exit.

The converter's tests ran with
`python3 -m pytest --noconftest -q tests/test_openxc7_dsp_timing_tables.py`:
18 passed. They cover signed and nonmonotonic hold corners, fractional-picosecond
rounding, hybrid pins, invalid arc directions/types/transitions, malformed
parameters and an independent raw-data corruption check. The stdlib-only
converter does not use the RTL conftest, whose NumPy dependency is absent from
the system Python. Steps 5–6 remain pending.

The isolated backend integration uses an explicit `-o dsp-vivado-timing=on`
option, restricted to the characterized `xc7k480tffg1156-2` part. Generated
constant data retain all 15 parameter signatures and declared vendor defaults.
The normal combinational/class/clocking callbacks use the prepared bounds,
including hybrid pins. Other parts and the option's default off state retain
the previous behavior. Enabling the model rejects an unmatched configuration.
Rebuild every Xilinx translation unit depending on the changed class header,
with up to eight compiler workers, and preserve every unaffected object.

An optional post-pack audit writes the actual callback results for all DSP
input/output pairs and sequential pins. Compare that output with the independently
validated vendor tables, including a defaults-omission case and an unsupported-mode
rejection. These constituent checks precede Vivado path comparisons and complete
PHY/clock timing work; they do not qualify a full OpenTPU image.

The initial isolated backend build and native source-configuration callback
checks completed with exit 0. The [full packed-design inventory](../build/fedora-openxc7/full-packed-dsp-inventory-20261011T223120Z/analysis-effective/inventory.json)
subsequently found 19 effective hardware configurations, rather than the 15
source configurations. All 717 cells have a changed CARRYIN inversion and
additional per-bit inversion flags. The FASM writer combines those flags with
the original bus masks; the timing matcher must apply the same rule.

The 19 effective parameter sets have now been characterized, and the isolated
tables and matcher have been updated. Step 5's DSP callbacks passed both the
19-configuration checks and the complete 717-DSP design audit. The new backend
remains unselected for the live full route. Step 6's path comparisons and the
complete PHY/clock model remain pending. Original source configuration results
and failed fixtures are retained for comparison.

The next query instantiates all 19 effective configurations from the complete
packed inventory, using the same declared primitive ports and vendor defaults.
It checks every declared parameter against actual Vivado properties and saves
all numerical arc corners on the same Kintex-7 part. The new table converter
must take its configuration count from that checked full-scope inventory,
while still requiring all 717 distinct named DSPs. The isolated matcher must
OR per-bit packer inversion flags into the ALUMODE/INMODE/OPMODE masks exactly
as the existing FASM writer does, and reject malformed flags.

After the effective-mode callback checks, run a complete pack-only callback
audit on the unchanged full area input. Require the exact 717 named DSPs and
their expected effective-model assignments. Compare each reported port,
sequential check and combinational arc with the validated vendor tables,
using the independently exported packed netlist to identify present ports.
This verifies the DSP callbacks on the actual accelerator; whole-board timing,
Vivado path comparisons, routing and hardware behavior remain separate gates.

The [complete native DSP audit](../build/fedora-openxc7/full-effective-dsp-native-check-20261011T230049Z/manifest.json)
finished with exit 0 and zero mismatches across 254,649 port classifications,
177,541 sequential pins and 1,842,120 combinational arcs. All 717 named DSPs
map to the expected 19 effective configurations. This is full accelerator
coverage for the DSP callbacks, not a constituent substitute for that check.

The [remaining PHY/clock inventory](../build/fedora-openxc7/full-phy-clock-timing-inventory-20261011T231155Z/inventory.json)
records the exact serializer, MMCM, PLL and BUFGCTRL configurations from the
same complete netlist. Next work is their actual vendor timing and clock-family
semantics, plus Kintex fabric data and full path comparisons. Preserve the
active original route and its source/binary identities throughout that work.
