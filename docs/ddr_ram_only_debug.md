# CH0 diagnosis with a RAM-only baseline

**Historical October 16–17 experiments.** Current disposition is recorded in
[HANDOFF.md](../HANDOFF.md): c0182800/c0182863 fixed-clock artifacts are retained,
and the c01848 runtime-clock effort was abandoned. The experiment order and
commands below are preserved records, not an active build or hardware plan.
New bitstreams require both JTAG and PCIe runtime interfaces under
[the repository policy](../AGENTS.md#mandatory-interfaces-in-every-bitstream);
the older RAM-only implementation paths are retired. `--prepare-only` remains
historical source preparation with `implementation_admitted=false`; MIG
preparation can generate vendor IP, but neither mode admits a new bitstream.

The reconstruction examples also depend on local helper scripts, generated
cores, reference packages and review receipts that are not all published in
Git. A fresh clone does not supply those dependencies. Preserve their original
paths and hashes when examining the historical receipts; these examples do not
authorize regenerating an image or overwriting a preserved package.

The first physical experiment is a dedicated RAM-only MIG image. The historical
MIG/JTAG image contains `otpu_native_sys`, so it does not establish this baseline.
The new diagnostic has vendor MIG, its example traffic generator, counters and
USER2 JTAG status. It has no OpenTPU compute engine or PCIe endpoint.

The first built address image is packaged at
[`bitstreams/ramtest-mig-ddr800-address/`](../bitstreams/ramtest-mig-ddr800-address/),
BUILD_ID `c0161001`. Its route/timing, 242 board-reference pin assignments,
packet/CRC and four bus-skew checks passed. Vendor CDC findings and their review
are preserved. Fedora SRAM loading and USER2 readback now work through DLC10.
The October 16 physical observations below reproduce CH0 corrected errors.

The [October 16 upstream branch review](ddr_upstream_branch_review.md) checks all
190 live branch heads against `~/upstream_openTPU`, including DDR source-tree
digests and fix ancestry. This is an inventory and scoped source comparison,
not a manual review of every change in every branch. The two highlighted
September PHY fixes are already present. Runtime channel switching and the
matched PHY comparisons below are complete. The current lead is reproducible
pattern-dependent lane-6 corruption. Earlier narrow tags suggested column-A8
coupling, but fresh full-tag tests also failed the row-A8 control.

## Image preparation status

| Experiment | Image status |
| --- | --- |
| MIG DDR800, both channels, address | Packaged; CH0 corrected errors reproduced twice, CH1 clean |
| MIG DDR800, CH0-only / CH1-only address traffic | Both packaged; each passed a separate five-minute observation |
| MIG DDR800, both channels, other patterns | Zeros, ones, walking one, walking zero and PRBS each passed five minutes |
| Same-image LiteDRAM pattern changes | Corrected `c0172031` image passed five minutes of address traffic, then failed CH0 after a complete zero refill with unchanged calibration. CH1 stayed clean. Sequence stopped; later patterns were not run |
| MIG DDR800 with runtime channel switching | Built and packaged as `ramtest-mig-ddr800-runtime`, `c0161100`; both-channel failure reproduced; original and reversed eight-phase sequences completed with CH0 errors persisting while CH1 was paused |
| Matched RAM-only LiteDRAM DDR800 | ABI 2 built, reviewed within documented timing scope, and physically exercised; CH0 ECC and comparison errors, CH1 clean; ABI 1 wrapper stall quarantined |
| Same-image LiteDRAM channel switching | Eight phases completed without controller reset or recalibration; CH0 errors persisted with CH1 idle and reading |
| Warm CH0 rescan | Failed in both the original baseline and registered-read image: no common CK phase and no passing lane-6 position; no refill or recovery pass |
| RAM-only LiteDRAM reset / registered-read comparisons | Both images packaged. Reset comparison: pass/pass/pass. Registered-read comparison: baseline fail, candidate five-minute pass, baseline fail. Subsequent reloads: one five-minute pass, then a CH0 failure; stopped with evidence saved |
| Small raw write-once/read-repeat region | One 64-byte location passed 128 reads. Three 64 KiB regions all failed initial verification and repeated reads on lane 6; normal-ECC payload capture remains separate work |
| Full-system CH1-mapped serializer-reset candidate | Built and packaged; physical comparison pending |
| Mixed traffic, retention and normal ECC checks | Mixed traffic failed on CH0; fresh-load 60-second normal-refresh retention screen passed. Controlled LiteDRAM CH1 single/double-bit error reporting passed; MIG injection and saturation remain untested |
| Aligned first read mismatch capture | ABI 3 `c0162030` packaged. Natural CH0 observation showed corrected-only errors. Deliberate CH1 double-bit injection captured the exact address `0x4000`, expected zero data and modeled returned payload with no queue faults |
| Power-cycle observation | Same registered-read image passed ten minutes on both channels, 1,623 full read traversals each at final drain, zero ECC/comparison errors. Die 49.71–50.69°C. Off duration was not measured; repeatability and controlled cold starts remain open |
| Retained zeros through raw BIST | No writes or recalibration: captured CH0 beat failed 32/32 reads; captured/middle/high regions failed all repeated reads, confined to physical lane 6 (DQ48–55). Low 64 KiB and all CH1 controls were clean |
| Bounded rewrite and read-only follow-up | One raw zero write cleared the captured beat; it later passed 64/64 reads. The unrewritten +2 KiB address alternated 58 clean/6 bad reads with no writes/recalibration. Neighboring CH0 addresses failed 64/64; CH1 stayed clean. Larger rewrite remains unperformed |
| Distinct raw address-pair patterns | Two locations 2 KiB apart interfere only on lane 6. Reversing writes reverses the observed coupling; grouped reads retain it. The same effect appears near the bottom of RAM. Earlier address traffic has a lane-6 blind spot for this pair; no full-capacity repair established |
| Row-A8 control | Distinct raw lane-6 tags at `0x62203000`/`0x63203000` retained: 32 immediate and 64 final reads passed at each location. No row-A8 coupling observed in this short test |
| Focused MIG address-pair comparison | `c0171101` built, independently reviewed and packaged as `ramtest-mig-ddr800-a8-focused`. Two fresh SRAM-load runs each passed all four pairs/both write orders: 16 writes and 2,048 reads per channel, zero ECC/payload errors. This covers seven locations per channel, not all 4 GiB |
| Fresh LiteDRAM raw pair comparison | Completed and reviewed on a fresh `c0172031` load/calibration, with native generators held reset. CH0 failed 688/2,048 raw reads, confined to lane 6; CH1 passed 2,048/2,048. Full-tag row-A8 control also failed. CH0 payload tags/physical pairs match MIG; raw check bits, timing and image/calibration differ |
| Retained raw tags, lane-6 read-delay comparison | Completed and reviewed: no clean setting from taps 18–26. Untouched tap 22 failed 55/64 one-tag reads, same-tap replay 50/64 and final replay 51/64; zero-tag/CH1 controls clean. No DRAM writes or bitslip changes; original delay commands replayed |
| Retained raw tags, lane-6 framing comparison | Completed and reviewed: all eight uniform lane framings failed. Original bitslip 3 failed 49/64 one-tag reads before changes and 50/64 after replay; CH1 controls clean. Input delay and RAM contents unchanged; original framing commands replayed |
| Passive first raw-word capture image | `c0172032` built, base/extension reviews passed and packaged. Physical run completed: CH0 69/512 raw reads bad, CH1 0/512; all 69 captured lane-6 bytes changed from `ff` to `00` across all eight transfers. All 160 original CSRs and firmware are unchanged |
| Retained high word, changing only the low neighbor | Completed and reviewed in the same `c0172032` load/calibration. High-word errors per 128 reads: zero neighbor 96, A5 neighbor 102, identical ones neighbor 0, zero again 32. Every bad lane-6 vector matches the neighbor's data; low/CH1 controls clean. Equal tags hide the failure |
| Same-image lane-6 read-window comparison | Completed; copying candidate tap 24/bitslip 4 into the failing baseline did not recover it. Original tap/bitslip commands were replayed, but the earlier error behavior did not return |
| Full dual-channel OpenTPU | Built, independently reviewed and packaged as `dual-pcie-4gb-ddr800-reset`, 100 MHz compute/DDR800. Setup +0.020 ns, hold +0.029 ns; all 116 CDC findings reviewed within recorded limits, ten additional CSR pointer skew checks passed. Package checksums and host identity gate passed; physical restoration pending |

The independent CH1 approximately 150 MHz candidate is now built, independently
reviewed and packaged at
[`bitstreams/ch1-pcie-2gb-core150/`](../bitstreams/ch1-pcie-2gb-core150/).
`NoTimingRelaxation` routing closed setup at +0.003 ns and hold at +0.018 ns,
with no failing endpoints. The packet/CRC, pins, complete route, both PCIe
OOB clock modes and scoped CDC reviews passed, including all 49 skew checks.
Actual compute is 148.837209 MHz; DDR800 and CH1-only 2 GiB mapping are retained.
Physical runtime qualification is pending. It does not diagnose or repair CH0.
Failed earlier attempts and the build procedure remain in the
[compute-clock guide](ch1_compute_clock.md).

All 20 currently specified image packages, including the existing CH1 release,
the diagnostic variants, full dual-channel candidate and compute-clock
candidate, are present. The October 17 package audit verified all 895 declared
checksum entries. Image preparation is complete for these experiments;
extended cold/warm qualification, repeatable CH0 recovery and full PCIe
runtime testing remain separate incomplete gates. No flash was written.

### Focused MIG comparison of column-A8 pairs

The new `c0171101` diagnostic retains both full 2 GiB vendor MIG controllers
at DDR800, with ECC correction enabled. It replaces the broad example traffic
generator with a bounded program over seven unique 64-byte ECC words per
channel. Three bank-1 pairs differ only in column A8, and a fourth is the row-A8
control. Each pair runs in both write orders, with immediate and grouped
low/high/low reads. Channel-distinct complementary tags avoid the earlier
lane-6 address-pattern blind spot. There are 16 full-width writes and 2,048
reads per channel, with 100 ms gaps between operations. The two channels run
in parallel and nominal completion takes about 207 seconds after calibration.

MIG and LiteDRAM use different address maps. The MIG byte-address pairs are
`0x10001000/0x10001800`, `0x18001000/0x18001800`, and
`0x1c641000/0x1c641800`; the row control is `0x1c441000/0x1c641000`.
They preserve the physical bank/row/column used in the LiteDRAM investigation.
This small experiment does not qualify all 4 GiB and cannot replace the later
full-range, thermal, startup and full-system tests.

The frozen protocol model passed all 19 trials, including production read
counts, command/data stalls, data/ECC inputs, timeouts, reset/calibration loss,
synthetic lane-6 aliasing and the serial status interface. Two deliberately
broken variants were detected. The host decoder also passed checks using
snapshots exported by that RTL simulation, including rejection of all eleven
incorrect header fields before any snapshot request. The models do not
simulate the vendor PHY or ECC decoder. The image is now built and packaged at
[`bitstreams/ramtest-mig-ddr800-a8-focused/`](../bitstreams/ramtest-mig-ddr800-a8-focused/).
Independent review passed: 47,318/47,318 nets routed, setup +0.905 ns,
hold +0.035 ns, all 242 ports matched, 100 MHz UI clocks and four held-payload
skew constraints verified. A single additional bare `_rep` mailbox register
was traced to the expected held request bit and reviewed within the existing
toggle protocol. The first physical observation (local-only `docs/data/ddr_mig_address_pairs_20261017.json`)
passed all four pairs and both write orders on both channels, with exactly
16 writes, 2,048 returned reads and 512 returned reads per pair per channel.
There were zero corrected events, uncorrectable events and payload mismatches.
Die temperature was 43.31–45.89°C, lower than the retained LiteDRAM experiment.
A second fresh SRAM-load observation (local-only `docs/data/ddr_mig_address_pairs_repeat_20261017.json`)
also passed the complete program with zero errors, at die 41.96–45.77°C.
Power stayed on between these two loads; they are not controlled cold starts.
This is evidence against
permanent aliasing at those physical locations under all operating conditions;
it does not exclude an intermittent hardware fault or establish a LiteDRAM fix.
The compared data tags, ECC path, image/calibration and die temperatures differ.
No full-capacity repair is established.

To rebuild from the repository root, use fresh output directories:

```bash
python3 tools/fedora_build_ramtest_mig.py --ddr-mts 800 --channels both \
  --pattern address --build-id c0171101 --prepare-only \
  --out build/vivado/mig-a8-focused
python3 tools/fedora_build_ramtest_mig_pairs.py \
  --build build/vivado/mig-a8-focused --prepare-only
python3 tools/check_ramtest_mig_pairs.py --build build/vivado/mig-a8-focused \
  --out build/checks/mig-a8-focused-model
python3 tools/check_ramtest_mig_pairs_host.py \
  --model build/checks/mig-a8-focused-model/manifest.json \
  --out build/checks/mig-a8-focused-host
python3 tools/fedora_build_ramtest_mig_pairs.py --build build/vivado/mig-a8-focused \
  --model-review build/checks/mig-a8-focused-model/manifest.json
python3 tools/fedora_review_ramtest_mig_pairs.py --build build/vivado/mig-a8-focused \
  --model build/checks/mig-a8-focused-model/manifest.json \
  --host-model build/checks/mig-a8-focused-host/manifest.json \
  --out build/checks/mig-a8-focused-review
python3 tools/fedora_package_ramtest_mig_pairs.py --build build/vivado/mig-a8-focused \
  --model build/checks/mig-a8-focused-model/manifest.json \
  --host-model build/checks/mig-a8-focused-host/manifest.json \
  --review build/checks/mig-a8-focused-review/manifest.json \
  --out bitstreams/ramtest-mig-ddr800-a8-focused-new
```

The independent review opens the routed checkpoint and confirms the 100 MHz
UI clocks behind the timing profile, synchronizer properties, all 242 board
ports, route/setup/hold/pulse timing, packet/CRC checks and four held-payload
skew constraints. Any new CDC finding requires a separate review. No tool in
this build/review/package sequence opens the hardware.

After a package passes review, preserve the previous failing-state receipts
and load its bitstream into volatile SRAM. With the existing XVC server running:

```bash
python3 tools/probe_ramtest_mig_pairs.py \
  --package bitstreams/ramtest-mig-ddr800-a8-focused-new \
  --seconds 300 --interval 5 --out build/results/mig-a8-focused-1
```

The reader saves both channels' progress, corrected/uncorrectable event counts,
payload comparisons, the first captured event and FPGA die temperature. The
only host write is a snapshot request; the FPGA itself writes the seven test
locations. Evidence remains sticky through later UI reset/calibration loss,
which halts the program. Reloading is needed to repeat it. A focused PASS does
not establish full-capacity recovery. Reproducing the same coupling with MIG
would strengthen suspicion of shared board/DRAM behavior; a MIG pass would
justify further LiteDRAM-specific experiments. Neither result alone identifies
the defective component or proves a repair.

### Fresh LiteDRAM raw pair comparison and read-delay follow-up

After both focused MIG runs passed, the exact `c0172031` image was loaded
again. Its configuration-time calibration completed, and the native traffic
generators stayed reset and paused. A new modeled raw BIST program uses the
same physical pairs, write orders and read counts as the MIG test: 16 writes
and 2,048 reads per channel. CH0 uses zero/one payload tags. Raw check bits
and host-driven access timing differ from the native ECC MIG experiment.

The completed raw observation (local-only `docs/data/ddr_litedram_fresh_address_pairs_20261017.json`)
has 16 writes and 2,048 reads per channel. CH0 failed 688 reads, confined to
lane 6 (DQ48–55), while CH1 had zero errors. By case, CH0 failed 99 low-column,
176 middle-column, 215 upper-column and 198 row-A8-control reads, each out
of 512. Die temperature was 45.53–49.09°C. The original low-pair cohorts
contained 320 clean zero-tag reads and 99 errors among 192 one-tag reads.
Repeated identical reads sometimes pass, so a static stored-data/alias
explanation alone is insufficient. The full-tag row control now fails too:
column-A8 specificity does not hold across these patterns/calibrations. Its
earlier narrow-tag pass cannot exclude a read-capture/data-pattern problem.
This does not prove which physical read/write/command mechanism is failing.
The test bypasses native ECC, and its raw DQ mask is an OR across eight DDR
transfers, not a captured returned word. Native ECC counters remain zero
because the native generators are inactive. All seven written locations need
native reinitialization before inference.

Use this only on a fresh SRAM load with no native test traffic started:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python \
  tools/check_ramtest_litedram_focused_pairs.py \
  --core bitstreams/ramtest-litedram-ddr800-runtime-pattern/core \
  --out build/checks/fresh-ld-pair-model
python3 tools/probe_ramtest_litedram_focused_pairs.py \
  --package bitstreams/ramtest-litedram-ddr800-runtime-pattern \
  --model build/checks/fresh-ld-pair-model/manifest.json \
  --out build/results/fresh-ld-pairs
```

The first command requires the pinned LiteX/Migen environment. The hardware
reader requires NumPy and the existing XVC connection. Its preconditions
reject any native traffic, nonzero native counters or a different core/image.
It does not request calibration, start native traffic or clear counters.
Preserve the complete transaction stream and calibration before/after records.

The follow-up probe is `tools/probe_ramtest_litedram_raw_taps.py`. Its
control model passed all 32 input-delay values and invalid-input rejections,
and checks that both raw BIST call sites issue reads only. It requires the
completed reviewed fresh raw failure before hardware access. It reads retained
low/high tags, changes only CH0 lane-6 read delay around the recorded tap,
and includes an untouched baseline and same-tap replay. That replay can
distinguish reset/reapplication sensitivity from a different delay selection.
Original delay commands are replayed at the end; direct tap-state readback
and behavioral restoration are not claimed. It changes no bitslip or write
settings. A short clean delay setting is a candidate for subsequent testing,
not a full-capacity repair. The
completed read-delay comparison (local-only `docs/data/ddr_litedram_raw_taps_20261017.json`)
found no clean nearby setting: all eight alternate taps from 18 through 26
(excluding the original 22) failed. Untouched tap 22 failed 55/64 one-tag
reads, same-tap replay failed 50/64, and the final original replay failed
51/64. Every zero-tag read and CH1 control was clean. All 1,408 CH0 reads
and the exact selected-lane reset/increment command sequences were reviewed.
Die temperature was 48.72–49.09°C. No DRAM writes, bitslip changes or
recalibration occurred. Original delay commands were replayed; their physical
tap count cannot be read back here. This rules out the tested nearby-delay
adjustments as an observed recovery, not all possible read/framing settings.
The following framing comparison and subsequent command/write timing work
use the retained tags, with no inference.

The subsequent framing comparison (local-only `docs/data/ddr_litedram_raw_framing_20261017.json`)
also found no clean setting among all eight uniform lane-6 read framings.
At the untouched bitslip 3, 49/64 one-tag reads failed. Same-value replay
and final original replay each failed 50/64. Some alternate framings also
made zero-tag reads fail; all CH1 controls stayed clean. Input delay remained
at its previously commanded value, no DRAM writes or recalibration occurred,
and original framing commands were replayed. These are command replays,
not direct readback of the hardware setting. The experiment does not cover
every per-bit combination or command/write timing.

### Passive first raw-word capture image

The next diagnostic, `c0172032`, adds held status for the first raw 576-bit
BIST return, its start sequence, base, mode, seed and return count. This will
show the eight individual 72-bit DDR transfers rather than just an OR mask.
It records the first return, not the first error: use single-word reads to
correlate its payload with the BIST error counters. The observer has no
connection that drives native command/data/ready outputs.

`tools/litedram/raw_capture_bist.py` subclasses the original BIST. Its model
compares command/data outputs and counters against an unchanged base under
identical stalls, clean/injected reads, multiword reads, writes, new epochs
and late stray returns. All seven epochs passed. The host model checked
610 payloads through actual 18-word big-endian CSR packing, 24 transfer/seed
injections, torn epoch/metadata rejection and comparator/payload disagreement.
These models do not simulate physical DDR timing.

The generated core retains all 160 original CSR addresses, widths and access
types. Seven read-only fields are appended to each BIST bank; the old host
ABI is preserved. The full two-channel PHY/native port ABI, 100 MHz UI,
DDR800 and read latency 8 are retained. Its 10,232-byte calibration firmware
is byte-for-byte identical to the matched baseline (SHA256
`4ced07abf3982ad12cb833ee87f5921c80ef5538d10670adc39a5c8c1e73f46b`).
The ordinary core validator remains unchanged; the dedicated preparation
driver additionally checks the exact 14-register extension.

Core generation passed at
`build/fedora-vivado/litedram-ddr800-raw-capture-core-v3-20261017/`.
The RAM-only implementation at
`build/fedora-vivado/ram-only-litedram-ddr800-raw-capture-20261017/` completed.
The normal image review and separate routed capture-register/clock review
passed. Setup slack is +0.097 ns, hold +0.048 ns; all 71,359 routable nets
are complete. The image is packaged at
[`bitstreams/ramtest-litedram-ddr800-raw-capture/`](../bitstreams/ramtest-litedram-ddr800-raw-capture/).
The physical single-word capture experiment (local-only `docs/data/ddr_litedram_raw_capture_20261017.json`)
completed and was independently reviewed. Each channel received four writes
and 512 single-word reads at `0x3000`/`0x3800`, in both write orders. CH0 had
69 bad reads; CH1 had zero. Every bad CH0 capture returned `00` instead of `ff`
on lane 6 in all eight DDR transfers, with all other raw bits matching.
The lower zero-tag location passed all 320 reads; the upper one-tag location
failed 69 of 192 reads, including immediate and grouped reads in both orders.
The full captured payloads agree with the independent BIST error signatures.
This reproduces the lane-6 symptom in the new implementation, but does not
isolate write corruption, read selection/capture, or an electrical fault.

Die temperature was 48.11–49.09°C. Calibration records remained unchanged:
CH0 phase -39, reported common window 179 ps, lane-6 tap 19/bitslip 3;
CH1 reported 1,853 ps. These are calibration measurements, not external pad
timing qualification. The native generators remained reset/paused and raw
writes bypassed ECC; normal memory still needs full ECC reinitialization.
Access gaps, placement and calibration differ from the older image, so the
error rates are not a controlled comparison. The first load wrapper stopped
after successful programming because it expected an IDCODE string absent
from the loader log. The continuation performed no reload and verified live
JTAG IDCODE and image identity before issuing any BIST write. Both records
are preserved with the observation.

#### Retained high word while changing only the low neighbor

The same-load follow-up (local-only `docs/data/ddr_litedram_raw_neighbor_tags_20261017.json`)
kept the upper word at `0x3800` unchanged and rewrote only the lower neighbor
at `0x3000`. No reload, recalibration or PHY adjustment occurred. Each phase
read the low word 32 times, the retained high word 128 times and the retained
CH1 control 16 times:

| Low-neighbor tag | High-word errors / 128 | Bad lane-6 bytes across eight transfers |
| --- | --- | --- |
| Retained zero | 96 | `00 00 00 00 00 00 00 00` |
| A5 seed | 102 | `a5 d2 69 b4 5a 2d 96 4b` |
| All ones, matching the high word | 0 | Identical tags hide lane aliasing; no repair established |
| Zero again | 32 | `00 00 00 00 00 00 00 00` |

Every bad capture matched the low neighbor's lane-6 data exactly; other raw
bits matched the high word. All 128 low-word reads and 64 CH1 controls were
clean. The run completed only three CH0 low-word writes and 704 raw reads,
with unchanged calibration and native generators still reset/paused. Die
temperature was 48.85–49.22°C. This excludes a permanently stuck-zero lane
as the explanation of these captures, but does not distinguish stored-data
corruption from per-lane read selection/capture faults or intermittent board
hardware. Because the low word was read before the high-word group, retained
read data is still a possible mechanism. A useful next discriminator is to
change the neighbor's tag without reading that neighbor before high-word reads.

The first follow-up attempt stopped before any DDR write because live mailbox
integer channel keys were compared directly with saved JSON string keys.
Normalizing the representation corrected the guard; saved calibration values
were identical. Its failed wrapper and source are preserved under
`build/hardware-test/litedram-raw-neighbor-tags-20261017/`; the successful run
and archived observation use the `v2` directory. This was a host comparison
failure, not a calibration change.

#### Frozen core generation and rebuild

The preparation uses a frozen generator copy with one import replacement;
the baseline PHY, BIST and calibration sources are preserved. The first two
attempts retained their failure logs: an old compiler wrapper mounted the
previous checkout path, then the replacement lacked matching binutils.
The complete task-local gcc/objcopy/objdump wrappers use the existing pinned
container image and mount only this output writable. They are recorded by
hash. A fresh machine needs working RV32I compiler/binutils and the pinned
LiteX/Migen environment, as with the ordinary core preparation.

To rebuild, use fresh output directories from the repository root. The
`--rv-cc` compiler must have matching `objcopy` and `objdump` beside it:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python \
  tools/check_ramtest_raw_capture_bist.py --out build/checks/raw-capture-model
build/fedora-openxc7/litedram-environment/venv/bin/python \
  tools/check_ramtest_raw_capture_host.py --out build/checks/raw-capture-host
python3 tools/fedora_prepare_litedram_raw_capture.py \
  --model build/checks/raw-capture-model/manifest.json \
  --rv-cc /path/to/riscv64-elf-gcc --out build/vivado/raw-capture-core
python3 tools/fedora_build_ramtest_mig.py --ddr-mts 800 --channels both \
  --pattern address --build-id c0161001 --prepare-only --out build/vivado/raw-capture-donor
python3 tools/fedora_build_ramtest_litedram.py --core build/vivado/raw-capture-core/core \
  --traffic-build build/vivado/raw-capture-donor --build-id c0172032 \
  --capture-first-read \
  --capture-model-review bitstreams/ramtest-litedram-ddr800-runtime-pattern/evidence/source/read-capture-model.json \
  --runtime-pattern-reset-fix \
  --pattern-restart-model-review bitstreams/ramtest-litedram-ddr800-runtime-pattern/evidence/source/pattern-restart-model.json \
  --out build/vivado/ram-raw-capture
python3 tools/fedora_review_ramtest_litedram.py --build build/vivado/ram-raw-capture \
  --out build/vivado/ram-raw-capture/offline-review.json
python3 tools/fedora_review_ramtest_raw_capture.py --build build/vivado/ram-raw-capture \
  --preparation build/vivado/raw-capture-core/manifest.json \
  --base-review build/vivado/ram-raw-capture/offline-review.json \
  --model build/checks/raw-capture-model/manifest.json \
  --host-model build/checks/raw-capture-host/manifest.json \
  --out build/checks/raw-capture-extension
python3 tools/fedora_package_ramtest_raw_capture.py --build build/vivado/ram-raw-capture \
  --preparation build/vivado/raw-capture-core/manifest.json \
  --base-review build/vivado/ram-raw-capture/offline-review.json \
  --extension-review build/checks/raw-capture-extension/manifest.json \
  --model build/checks/raw-capture-model/manifest.json \
  --host-model build/checks/raw-capture-host/manifest.json \
  --out build/packages/ramtest-litedram-ddr800-raw-capture-reconstruction
```

The two image reviews must pass before packaging or programming. This sequence
does not open hardware. The original core/profile validator is unchanged;
the dedicated capture preparation checks the exact backward-compatible CSR
extension, real RV32I firmware, complete core ports and reference CPU.

### Background full-system build

The full 4 GiB integration candidate finished building at
`build/fedora-vivado/dual-pcie-ddr800-reset-20261016/`, BUILD_ID `c0160002`.
It retains the full accelerator and Gen2 x8 PCIe, uses the same dual-channel
core as the RAM-only reset candidate, and keeps compute at 100 MHz and DDR800.
The recorded route has 320,678 of 320,678 routable nets complete and zero
routing errors; setup, hold and pulse-width gates passed. Independent image
and scoped CDC reviews passed. The package is now available at
[`bitstreams/dual-pcie-4gb-ddr800-reset/`](../bitstreams/dual-pcie-4gb-ddr800-reset/).
All 50 checksum entries and the actual host package-validation path passed.
This does not establish physical memory operation or close the external DDR
pad timing gap. The build used two workers:

```bash
python3 tools/fedora_build_vivado_pcie_ddr800.py \
  --core bitstreams/ramtest-litedram-ddr800-reset/core \
  --core-mhz 100 --build-id c0160002 --threads 2 \
  --out build/vivado/dual-pcie-ddr800-reset
```

Use a fresh output directory. The builder freezes its driver and sources and
requires route, setup, hold, pulse-width and DRC gates before image generation.
This background build does not select a proven CH0 repair or program the card.
Every fresh build needs its own independent review. Physical memory/compute/PCIe
qualification remains the final debug-plan step.

The completed independent review of this exact build uses
`tools/fedora_qualify_ch1_image.py --memory-profile dual`, requiring both physical
channels, 4 GiB capacity and calibration mask 3. It checks the frozen generated
core against its generator and the historical four-port ECC model source;
the original two-port test must differ only by the reviewed four-port expansion.
The CH1 recovery core is explicitly rejected in this mode. Packet/CRC, pin,
route, internal timing and PCIe OOB clock checks passed.
CDC review and physical qualification remain separate gates; the job never
programs the card. LiteDRAM external DDR pad timing is still an open limitation.

The completed CDC collection records the actual routed reset and calibration
synchronizer fan-in, register properties, timing exceptions and missing pad
delays. It also compares every non-information CDC row with the packaged CH1
reset candidate. To repeat this collection after independent qualification:

```bash
python3 tools/fedora_collect_pcie_cdc.py \
  --build build/vivado/dual-pcie-ddr800-reset \
  --qualification build/vivado/dual-pcie-review/manifest.json \
  --reference-cdc bitstreams/ch1-pcie-2gb-ch0-reset/evidence/oob-cdc.rpt.gz \
  --out build/vivado/dual-pcie-cdc-evidence
```

Use the actual build and qualification directories, and a fresh output
directory. `CDC_EVIDENCE_COLLECTED_REVIEW_PENDING` means evidence is available;
it does not approve the crossings or permit packaging as a reviewed image.
Differences in calibration-ready wiring are expected between CH1-only and
dual-channel mappings, but must be checked against this routed checkpoint.

Also check CSR FIFO pointer skew on the exact routed checkpoint:

```bash
python3 tools/fedora_check_litedram_csr_gray.py \
  --qualification build/vivado/dual-pcie-review/manifest.json \
  --out build/vivado/dual-pcie-csr-gray
```

This adds ten analysis-only skew assertions in a separate Vivado session and
checks all thirty pointer bits and both synchronizer stages. It changes no
bitstream or saved routing. For the packaged image, all 49 original/additional
assertions passed; minimum slack was 3.248 ns. The manual review accounts for
all 116 non-information rows, retains the ban on the unused global reset CSR,
and explicitly relies on the generated vendor IP contract for encrypted
SmartConnect internals. It is not a formal proof or a physical DDR result.

After reviewing the collected paths and recording explanations for every
non-information CDC row, the dedicated packager accepts the exact reviewed
build and evidence:

```bash
python3 tools/fedora_package_dual_pcie.py \
  --build build/vivado/dual-pcie-ddr800-reset \
  --qualification build/vivado/dual-pcie-review/manifest.json \
  --cdc-review build/vivado/dual-pcie-cdc-review.json \
  --out build/packages/dual-pcie-4gb-ddr800-reset-reconstruction
```

The CDC review must bind the qualification, collection and CSR gray-pointer
review hashes, list every reviewed non-information row and group those rows
with explanations. This is
a separate review result, not the collector's manifest. Packaging checks all
bound files, timing, routing, skew, capacity, core files and the MCS payload;
it includes the `.bit`, matched host core and evidence. The package remains
experimental with external DDR pad timing and physical qualification pending.
The current CH1 LFM2 runner and Chestnut transport enforce the CH1-only mapping;
they cannot qualify this 4 GiB candidate. The separate
dual-channel host runner (local-only `docs/ddr_dual_pcie_runtime.md`) now checks the reviewed
package and live identity, both physical 2 GiB bounds, full-range raw BIST,
native ECC read coverage, DMA sentinels and exact matmul/LFM2 output.
Its software checks passed; physical operation remains pending. It requires
runtime PCIe/XDMA or Chestnut access in addition to the JTAG programming path.

## Measured evidence, October 16

### Follow-up after reported power cycle, October 17 HKT

The user confirmed power on. Cable initialization and FPGA IDCODE detection
succeeded, then the exact registered-read image `c0162012` was loaded into
SRAM. Both full 2 GiB channels passed five minutes of address-pattern traffic
and another five minutes without reload, recalibration or counter clearing.
Final paused/drained counters showed 1,623 full read traversals per channel,
zero corrected/uncorrectable ECC errors, zero payload mismatches and zero
watchdog/lane errors. Die temperature was 49.71–50.69°C.

The saved observation and compressed receipts (local-only `docs/data/ddr_power_cycle_20261017.json`)
include the calibration state and comparison with earlier passing and failing
loads of this exact image. CH0 selected different phase/framing settings;
its reported window was 179 ps versus 379 ps in the earlier failed reload.
Window width alone therefore still does not predict reliability. Power-off
duration was not measured and the first die reading was already 49.71°C,
so this is not a controlled cold-start result. A usable initialization does
not establish a repeatable repair or exclude marginal hardware.

After saving and draining this observation, the configurable-pattern image
`c0172031` passed five minutes of address traffic, including 811 full read
traversals at drain. The next epoch refilled both full 2 GiB channels with zeros
and failed CH0; CH1 stayed clean. The controller was neither reset nor
recalibrated, and the recorded calibration remained identical. Only diagnostic
generators/observers were reset for the new epoch. The first failing sample
was at die 50.32°C. Later patterns were not run.

The same-image failure receipts (local-only `docs/data/ddr_runtime_patterns_20261017.json`)
preserve the first mismatch at byte address `0x63203000`, expected zeros and
returned `0x0000060000000000` in each 64-bit word. Address tracking was valid,
with no queue or command-protocol errors. Final drained CH0 counters were
46,998,732 corrected beats, 41,124,391 uncorrectable beats and 90,691,585
comparison-error cycles. These categories are not independent counts of
faulty DRAM cells. This transition removes reprogramming/recalibration as
confounders, but still changes the data pattern, diagnostic state and fill.

Subsequent raw read-only observations (local-only `docs/data/ddr_retained_zero_20261017.json`)
kept native traffic paused and preserved its capture/counters/calibration.
The captured 64-byte beat failed all 32 reads with raw mask `0x3000000000000`
(DQ48/49). The surrounding and middle 64 KiB regions each failed 960 of 1,024
beats per read; the high region failed all 1,024. All these errors were on
physical byte lane 6. The low 64 KiB and every CH1 control read were clean.
Die temperature during this observation was 48.48–49.09°C.

An ECC model shows that retaining only lane 6 from the preceding address
pattern would reproduce the captured payload and the aggregate masks/counts
in the captured, middle and high regions. It would also predict errors in the
low region, which was clean. This is a partial old-data fingerprint, not proof
of a stored-data fault.

The bounded rewrite (local-only `docs/data/ddr_single_zero_rewrite_20261017.json`) read individual
addresses before changing memory. Middle/captured/high address masks matched
their old lane-6 address byte; low probes stayed clean. One full-width raw zero
write to `0x63203000` then cleared 32 consecutive reads of that beat, while
neighboring locations and middle/high controls retained their old masks.
All 69 CH1 control reads passed. Calibration, native counters and the captured
first mismatch were unchanged; die temperature was 48.48–49.09°C. This is local
recovery of a disposable location, not a full-memory repair or a native-path pass.

A proposed 64 KiB raw rewrite stopped before any write because its precheck
found 958 failing beats rather than the predicted 959. The subsequent
read-only sweep (local-only `docs/data/ddr_zero_region_inspection_20261017.json`) read all 1,024
beats individually. Its masks matched the old lane-6 data except the deliberately
rewritten beat and one more clean location at `0x63203800` (+2 KiB). That second
address had no individual pre-write observation, so address aliasing is not
established. Repeated burst counts varied between 958 and 959 without writes.
CH1 stayed clean, calibration/native state remained unchanged, and die
temperature was 48.60–49.22°C. Static retained data alone is not yet a sufficient
explanation; compare repeated reads at these addresses before changing PHY
settings or clearing the rest of the failing contents.

That repeated-address check (local-only `docs/data/ddr_zero_suspect_repeats_20261017.json`) then
completed without writes or recalibration. The rewritten `0x63203000` passed
64/64 reads. The unrewritten `0x63203800` returned zero raw mismatch mask 58
times and `0x3000000000000` six times. Neighboring `0x63203040` and `0x63203840`
each retained that bad mask on 64/64 reads. All corresponding CH1 reads passed.
Die temperature remained 48.60–49.22°C; native counters/capture and calibration
were unchanged. This supplies a small reproducible read/address-stability
experiment. It does not identify whether controller/PHY timing, DRAM address
capture, signal integrity or a component fault is responsible. Keep the card
powered and the native generators paused to preserve this state.

### Distinct address pairs expose lane-6 coupling

The read-order experiment (local-only `docs/data/ddr_zero_read_order_20261017.json`) found 50 bad
CH0 reads out of 448 at the suspect address, including repeated reads alone
and reads after clean/bad/far primers. All corresponding CH1 reads passed.
It showed no deterministic dependency on the immediately preceding read.

The next two-location pattern test (local-only `docs/data/ddr_address_pair_20261017.json`) wrote
one raw 64-byte beat at each of `0x63203000` (L) and `0x63203800` (H), using
modeled raw address patterns that differ on DQ5, DQ30 and DQ55. L passed all
32 immediate reads after its write. After writing H, L failed 64/64 reads on
DQ55 alone, exactly the difference between these patterns on physical lane 6.
H passed 60/64 reads; its four failures were also confined to lane 6.

The reverse-order test (local-only `docs/data/ddr_address_pair_reverse_20261017.json`) first read
L, H and L in separate groups of 64. L failed all 128 grouped reads on DQ55,
so a single previous-read substitution does not explain this result. Writing
H and then L made L pass 64/64 reads and H fail 64/64: 51 had DQ55 differences
and 13 had DQ48/49/55 differences. Calibration and native counters/capture
were unchanged; die temperature was 48.48–49.34°C.

The pinned address/pattern models (local-only `docs/data/ddr_address_coverage_20261017.json`)
map both addresses to bank 1, row `0x6320`,
with columns `0x200` and `0x300`: **only DDR column A8 changes**. The platform
declares A8 at FPGA pin AJ25; that is source information, not an electrical
measurement. These observations strongly implicate unreliable lane-6
addressing/capture associated with A8. They do not yet distinguish an external
chip/board fault from PHY or command timing.

The low-region pair (local-only `docs/data/ddr_address_pair_low_20261017.json`) at `0x3000` and
`0x3800` reproduced the coupling in the same image and calibration. L passed
32/32 immediately after its write, then failed 64/64 on DQ55 after H's write;
H passed 53/64 final reads. This pair is inside the first 64 MiB used by the
calibration source's BIST, so limited high-address coverage cannot be the sole
explanation. The middle-region pair (local-only `docs/data/ddr_address_pair_middle_20261017.json`)
at `0x40003000`/`0x40003800` reproduced the same L failure on DQ55 in 64/64
reads after H's write. H passed 55/64; all nine failures remained on lane 6.
Both comparisons retained the same calibration/native state and were measured
at die 48.60–49.22°C.

The earlier repeated-address payload encodes the same lane-6 byte (`0x03`)
at the original L/H pair. That pattern therefore cannot detect this particular
one-lane alias. Its ten-minute pass remains a valid observation for that
pattern, but is insufficient to qualify unique physical addressing or full
4 GiB reliability. Address-sensitive qualification must distinguish each
address bit within every physical lane.

Only the bounded test locations were deliberately rewritten; the rest of the
failing data and original native capture remain preserved. These raw patterns
are not native ECC codewords. Keep native traffic paused until the next
controlled experiment or a documented reload/refill.

The row-A8 control (local-only `docs/data/ddr_address_pair_row_a8_20261017.json`) compared
`0x62203000`/`0x63203000`: bank 1 and column `0x200` match, while row `0x6220`
versus `0x6320` changes only row A8. Separately modeled seeds give lane 6
distinct tags. Both locations passed all 32 immediate and 64 final reads;
CH1 controls remained clean, calibration/native state was unchanged, and die
temperature was 48.48–49.09°C. This weakens a generally disconnected/stuck-low
A8-pin explanation. Column-command timing and internal column addressing
remain possible; the short row test does not qualify all row bits or cells.

### Next focused comparison with the independent MIG PHY

The existing MIG images provide the RAM-only baseline and full-range traffic,
but their repeated-address data is insufficient to reproduce this precise
lane-specific pair test. A new focused comparison is being prepared at
`build/fedora-vivado/ram-only-mig-ddr800-a8-focused-20261017/`, intended BUILD_ID
`c0171101`. No implementation or ready bitstream is implied by this directory.
Vendor IP generation has now finished;
targeted logic, its model and implementation remain pending. The saved test
specification maps the same physical pairs into MIG's `BANK_ROW_COLUMN`
layout, which differs from the LiteDRAM layout above.

The required image retains both full 2 GiB, 72-bit ECC controllers at DDR800,
with no accelerator/PCIe. Its targeted generator must initialize complete
64-byte words before reading them, write distinct tags at pairs, capture
immediate/grouped/reversed-order results and separate corrected/uncorrectable
ECC from payload comparisons. Derive the MIG row/bank/column map from its
generated configuration; do not assume the LiteDRAM high-address layout.
Use the existing held-snapshot USER2 transport, a distinct diagnostic identity
and explicit tested-address counts. A successful small pair test must not be
reported as full-capacity qualification.

Before implementation, model command/write-data stalls, delayed reads, exact
addresses/tags, error capture, calibration gating, ECC pulses and completion.
Freeze those sources and retain full timing/route/CRC/pin/CDC review before
programming. Only the IP/source preparation step has started. Physical
comparison should follow saved LiteDRAM evidence, then neighboring column-bit
controls and warm initialization repeats. Choose further PHY or slower-clock
experiments from those results; full 4 GiB restoration remains last.

The saved physical observations (local-only `docs/data/ddr_ram_only_20261016.json`) retain image
hashes, timelines and compressed original receipts. These were powered-card
SRAM reloads on Fedora, not controlled cold starts.

| Image and traffic | Observation | What remains unresolved |
| --- | --- | --- |
| MIG, both channels, address (`c0161001`) | CH0 corrected errors in two loads; CH1 zero errors. Repeat was clean through 45.7 seconds, then reported 30,151,467 corrected read beats at 51.3 seconds / 49.96 C | Traffic, calibration state, pattern and temperature dependence are not isolated |
| MIG, CH0-only address (`c0161010`) | Five minutes, zero corrected/uncorrectable/compare errors; die 44.42–49.46 C | Different implementation and reload from the both-channel image |
| MIG, CH1-only address (`c0161011`) | Five minutes, zero errors; die 44.42–49.96 C | Same limitation |
| MIG, both channels, zeros (`c0161020`) | Five minutes, zero errors; die reached 53.28 C | Pattern and implementation both differ from address image |
| MIG, both channels, ones (`c0161021`) | Five minutes, zero errors; die reached 53.65 C | Same limitation as zeros |
| MIG, both channels, walking one (`c0161025`) | Five minutes, zero errors; die reached 53.52 C | A separate implementation and initialization; not a causal pattern comparison |
| MIG, both channels, walking zero (`c0161026`) | Five minutes, zero errors; die reached 53.77 C | Same limitation as walking one |
| MIG, both channels, PRBS (`c0161027`) | Five minutes, zero errors; die reached 54.88 C | Same limitation: distinct implementation and initialization |
| Runtime MIG address (`c0161100`) | New image reproduced CH0 corrected errors between 53.683 and 59.215 seconds; first observed error at die 50.82 C; CH1 clean | Same-image read switching then showed errors persisting with CH1 paused; initial write corruption remains possible |
| LiteDRAM ABI 1 (`c0162000`) | Both calibration CPUs reported success; no accepted memory commands or data on either channel | Diagnostic wrapper stalled; **not a DDR data-error result** |
| LiteDRAM ABI 2 (`c0162010`) | Both full fills and hundreds of full-range read passes completed; CH0 corrected, uncorrectable and comparison errors; CH1 clean | A short calibration pass did not establish sustained native-port reliability |
| Same ABI 2 image and calibration | `CH0 → both → CH0 → both → CH1 → both → CH1 → both`, 20 seconds per phase; similar CH0 error rates in its active phases, CH1 clean; die 48.97–50.32 C | Concurrent CH1 reads are not required to sustain these errors; initial concurrent writes could still have corrupted stored data |
| Warm CH0 rescan in ABI 2 | Saved earlier CH0 common window 246 ps and CH1 1853 ps; rescan at die 49.34–49.71 C failed: lane 6 had no passing CK phase | No demonstrated warm recovery; failed scan fields for later calibration stages are not valid new tap/framing measurements |
| Raw CH0 reads after a new baseline load | At byte `0x10000`, one 64-byte location passed initial verification and 128 repeated reads while CH1 alternated idle/read | Narrow raw-port observation with ECC bypassed; does not qualify full capacity or the native ECC path |
| Same loaded image, three larger raw regions | 64 KiB at `0`, `0x40000000`, and `0x7fff0000`: all initial verifies and all 384 repeated reads failed; errors confined to DQ48–55, lane 6; die 48.36–49.46 C, CH1 ECC remained clean | Error counts/masks varied without rewriting, but none of these larger regions began with a clean verification. No full returned payload capture; write-time corruption and read-time errors are not cleanly separated |
| Fresh baseline before reset comparison (`c0162010`, unchanged image hash) | Both channels passed five minutes of full-range native ECC address traffic, then paused and drained cleanly | A new calibration selected different CH0 phase, write bitslip and read framing. This is evidence of variation between initializations, not proof that any one setting causes the difference |
| Serializer-reset candidate (`c0162011`) | Both channels passed the same five-minute test with zero corrected, uncorrectable and comparison errors, then drained cleanly | The baseline passed too, so this does not demonstrate a repair |
| Baseline loaded again after reset candidate (`c0162010`) | Both channels passed another five-minute full-range test and drained cleanly; CH0 write bitslip returned to all 0 | All-0 write bitslip occurs in both passing and failing loads; the bitslip value alone does not explain the failure |
| Fresh baseline mixed read/write screen | CH0 SEC/DED errors and 227,405 comparison-error cycles in the drained record after full initialization; CH1 clean | Initial snapshot and later ECC CSR reads are not simultaneous; use the drained record to establish the failure after initialization |
| Fresh baseline retention screen | Full-range reads passed before and after a 60-second pause with normal refresh; zero ECC and comparison errors | One passing load; does not establish reliability across initialization or temperature |
| Baseline / registered-read / baseline | First baseline failed; registered-read image passed five minutes and 806 full-range read-command passes per channel; final baseline failed with 70,463 SEC events, 17 DED events and 17 comparison-error cycles in the drained record | Candidate and final baseline shared write phase -2 and write bitslips `[0,0,0,0,6,6,6,6,6]`, but read taps/framing and implementation differ. Lane 6 selected tap 24/bitslip 4 in the candidate, tap 8/bitslip 3 in the failing baseline |
| Retained baseline, lane-6 window switching | Four 20-second read phases: original setting had 109 comparison errors; alternate, original again and alternate again mismatched almost every returned payload | No writes or controller resets occurred. Reapplying original register commands did not recover the original behavior; this is not a clean reversible A/B result or a demonstrated repair. Traffic left paused; reload before further normal qualification |
| ABI 3 capture image, original baseline PHY (`c0162030`) | Both channels filled completely; CH0 reported 7,210 corrected errors at a sampled 48.23 C. Drained record had 17 full-range read-command passes, zero DED/comparison errors and no capture queue fault; CH1 clean | Corrected-only events leave the post-ECC payload correct, so no first-mismatch record was expected. This load remains a failed memory qualification |
| Same ABI 3 image, retained contents, 120 more seconds of reads | CH0 corrected count increased from 7,210 to 18,422. Both channels reached 355 accumulated full-range read-command passes; no DED, comparison error or capture queue fault. Die 48.48–50.57 C during continuation; CH1 clean | No new writes, controller resets, counter clears or recalibration. This natural-error run did not exercise positive mismatch capture; the separate CH1 injection below did |
| Registered-read reload repeat 1 | Both channels passed another five-minute full-range address test; zero SEC/DED/compare errors; 814 full-range read-command passes after drain | Same bitstream as the previous candidate pass; a different calibration epoch |
| Registered-read reload repeat 2 | CH0 failed; drained record after complete fill and two full-range read-command passes showed 664,155 SEC events, 653,002 DED events and 659,492 comparison-error cycles; CH1 clean; die 47.86 C after drain | Five-cycle sequence stopped on the second reload. The registered-read change alone is not a repeatable repair |
| Same failed registered-read image, warm CH0 rescan | CH1 read-only warm-up passed; CH0 stayed paused. Rescan at die 48.97–49.09 C failed: lane 6 had no passing position across all 113 phase steps | No subsequent refill/recovery test; failed scan fields are not valid new operating settings |
| Deliberate LiteDRAM CH1 ECC injection | One 64-byte location at `0x4000`; raw patterns verified before native reads. Clean case: zero errors. Single-bit case: 5 SEC events, no mismatch. Double-bit case: 6 DED events, first mismatch at `0x4000`, expected zeros and returned `0x60` in each 64-bit word | Instrumentation check only: eight codewords each received zero/one/two deliberate flips. The location was restored and verified as raw zero, traffic paused; reload/refill before normal qualification. This validates physical mismatch capture on CH1, not CH0 reliability or counter saturation |

The calibration records provide a useful next comparison:

| Baseline initialization | CH0 common window | Reported `dqs_steps` | CH0 per-lane write bitslip | Observation |
| --- | --- | --- | --- | --- |
| Earlier native full-range test | 246 ps | -28 | All 0 | CH0 ECC/compare errors |
| Raw-region experiment | 156 ps | -51 | All 0 | Lane-6 errors in three 64 KiB regions |
| Fresh native test before reset comparison | 156 ps | +26 | All 6 | Both channels clean for five minutes |
| Serializer-reset candidate | 402 ps | +32 | All 6 | Both channels clean for five minutes |
| Fresh native baseline after reset comparison | 156 ps | -48 | All 0 | Both channels clean for five minutes |

Read tap/framing settings also changed. A reported window width alone did not
predict these outcomes. The raw and native tests use different data paths and
patterns, so their settings are a lead for controlled follow-up, not a direct
A/B proof. The reset candidate must be compared against repeated baseline
loads because a reload alone can produce a passing result.

The MIG address repeat completed a full write and clean full-range reads before
the corrected errors appeared. Correction remained enabled, so payload
comparisons stayed clean even during the error storm. Counts denote read beats
with a correction indication, not individual bad bits. These observations do
not identify a physical DQ lane. The older full-system lane-6 report below is a
different experiment.

LiteDRAM's same-image sequence was a read-traffic comparison after the initial
fill. It did not vary the other channel's write activity. The full-range and
drained snapshots establish genuine native traffic; the earliest traffic
snapshot and later ECC CSR reads are not cycle-coherent and must not be used
to claim that ECC errors occurred before initialization. The warm rescan saved
the old counters and calibration maps before changing state. It failed, so
the planned fresh fill was not run and traffic remains stopped in that receipt.

**CH0 is intermittent; a defective card has not been established.** Separate
single-channel passes do not establish that simultaneous traffic causes the
failure. The zeros pass above the address run's failing die temperature also
prevents assigning a single temperature threshold from these runs. FPGA die
temperature is not DRAM package temperature.

The registered-read comparison logged a die temperature of 46.02–50.45 C
during its passing five-minute observation. The following baseline failed at
a sampled 48.97 C (48.60 C after draining). The separate MIG PRBS image passed
with a sampled peak of 54.88 C, while the MIG address repeat first reported
errors at 49.96 C. These are measured temperatures from different images and
initializations, not a controlled thermal A/B experiment. DRAM package
temperature and repeatable cold-start behavior remain unmeasured.

A genuine MIG ECC event after valid initialization cannot be explained solely
by a bug specific to LiteDRAM's custom PHY. Shared board, clock/reset,
configuration and instrumentation paths still need investigation; this does
not establish a defective DRAM chip.

## Revised experiment order

Physical CH0 previously failed on byte lane 6, DQ48–55, with both the full-system
MIG DDR3-1066 image and the full-system LiteDRAM DDR3-800 image. Retraining could
briefly pass, and errors recurred while warm. These experiments differ in speed
and integration. They do not prove a defective DRAM chip.

| Order | Experiment | Requirement before interpreting the result |
| --- | --- | --- |
| 0 | Validate image identity, initialization and instrumentation | Matched hash/ABI/core/firmware; full-width initialization; accepted commands, write data and returned/compared reads; separate ECC and comparison counts |
| 1 | Preserve the RAM-only MIG failure | Save first failing snapshot and earlier clean samples before reset, counter clear or reload; already reproduced, controlled cold starts still pending |
| 2 | Same-image channel switching | Reproduce the failure in the new controllable MIG image first; initialize both controllers once, pause/drain application traffic only, and reverse the phase order in another run; no recalibration or controller reset |
| 3 | Small write-once/read-repeatedly discriminator | Establish a verified-good region, repeatedly read it without rewriting, and switch the other channel's traffic; distinguish fill-time corruption from read-time errors with separately controlled fill conditions and aligned captures |
| 4 | Pattern coverage plus short mixed/retention screens | Runtime address/channel-distinct data, complementary patterns and all 2 GiB/channel; a pattern change starts a new initialized epoch; idle keeps normal refresh enabled |
| 5 | Matched RAM-only LiteDRAM DDR800 | First demonstrate that the corrected wrapper actually transfers and compares data; match rate, geometry, ECC, address range and traffic as closely as possible; record unmatched implementation constraints |
| 6 | Controlled warm recovery | Save counters, pass maps, phase/tap/framing settings; stop and drain traffic, deliberately rescan while warm; reinitialize and repeat only if calibration succeeds. First ABI 2 rescan failed on lane 6 |
| 7 | One PHY change per comparison, selected by evidence | Reset experiment for initialization/reset sensitivity; `rd_reg` experiment for the read/bitslip/ECC fabric path; preserve generated latency and timing evidence |
| 8 | Extended qualification | Multiple cold starts and warm initializations, full-range patterns, warm concurrent/mixed traffic and refresh-on retention; require zero corrected, uncorrectable and comparison deltas |
| 9 | Full 4 GiB OpenTPU last | Requalify memory in the full image, then DMA, exact matmul and LFM; retain the CH1 release as fallback |

Temperature is a dimension of these experiments, not a later substitute for
them. Label cold power-on/calibration, warming without recalibration, warm
reprogramming, and warm recalibration separately. Reprogramming changes more
than calibration alone. Five cold starts and five warm initializations are an
initial screening budget, not a reliability guarantee. Do not require a
cooldown before the warm-failure capture or warm-rescan comparison.

Rescan recovery alone establishes sensitivity to that procedure. A thermal
calibration explanation needs corresponding movement in measured windows or
selected settings. A fixed bad signature alone does not prove a defective
DRAM component. If controlled tests keep implicating a shared physical path,
board power/clock measurements or a second card become useful discriminators.

### Next diagnostic image: runtime MIG control

The runtime control implementation (local-only `docs/ddr_runtime_traffic.md`) has passed its
generated-top, vendor-traffic and serial-control model checks. Vivado
implementation and the scoped offline review passed; the image is packaged.
The physical both-channel baseline reproduced CH0 corrected errors. The first
eight switching phases and the reversed-order sequence completed with errors
persisting when CH1 was paused. CH1 remained clean in these observations.
It keeps both DDR800 controllers, independent pause/resume and drained-state
reporting, and the existing full-range address pattern. Pattern,
fixed data/channel seed, address range and throttling are subsequent runtime
controls; they must not delay this first switching test. Both controllers stay calibrated
and refreshed when one traffic generator is idle. Drain accepted commands and
data before changing modes; keep the measured active channel's transaction
rate and data unchanged. Snapshot error deltas at every boundary and record
the actual accepted traffic rate to detect interference with the control.

Initialize and verify both channels before the switching sequence. Pausing a
channel must preserve its contents, counters and calibration. Changing pattern
or range requires an explicit new fill/verify epoch after saving earlier
evidence. Include a small fixed region for repeated reads and leave OpenTPU's
64-byte interleaver out of this lower-level experiment. Treat runtime settings
crossing the two UI clock domains as an implementation and timing-review task.

Adding runtime control changes placement and routing relative to `c0161001`.
First check whether this new image reproduces CH0 errors under the original
both-channel conditions. If it stays clean, record that implementation
sensitivity and repeat the baseline; do not conclude that channel switching
fixed the problem. If errors already exist before a phase, the experiment can
show whether switching sustains or changes them, but cannot identify their
original cause. Reverse phase order in a separate retained-calibration run;
starting the CH1 phases later in the first run does not remove time dependence.

The current full-range fill-once/read-repeatedly flow is not the small-region
read/write discriminator. That experiment still needs verified address/data
capture and region control. Compare cleanly verified data with later reads,
then repeat after a new explicit fill with the other channel idle. Keep these
fill conditions separate from read-phase switching. Extend the other channel
to write and mixed traffic only after the read-only control works. AMD describes
the small-write/continuous-read method in
[UG586](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Determining-If-a-Data-Error-is-Due-to-the-Write-or-Read).

Existing per-pattern images remain screening tools. They cannot replace the
same-image comparison because each build changes implementation as well as
the intended test variable. The current screening queue can finish; further
PHY variant implementations follow discriminating observations.

### Instrumentation limits and acceptance

The current MIG wrapper connects enabled correction and both eight-bit ECC
status buses to the observer. The observer samples them only with valid read
data. An entire valid full-width fill and retired read prefix are required;
uninitialized or unreturned data cannot satisfy a pass. The hardware error
storm demonstrates a live nonzero status path, but controlled single/double
error injection and counter-saturation behavior are **not yet validated**.
The generated interface has `ECC_TEST="OFF"`; do not assume an injection
port exists. The DQ48 model injection below validates the comparison detector,
not the MIG hardware ECC decoder. AMD describes distinct reporting/injection
facilities in [UG586](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Single-Error-and-Double-Error-Reporting);
availability must be checked against the actual generated interface.

The separate LiteDRAM ABI 3 CH1 hardware injection check now validates the
clean, corrected-only and uncorrectable cases, including exact first-mismatch
address and payload. It uses the existing raw BIST to write modeled codewords
at one disposable location; see the procedure and scope (local-only `docs/ddr_ram_only_litedram.md#controlled-ecc-and-capture-reporting-check`).
CH0 injection, MIG injection and saturation are not covered by that result.

MIG and LiteDRAM here share adapted vendor traffic/checking logic, so they are
not wholly independent test harnesses. Preserve that common dependency when
comparing their results. Their native ECC observations provide additional
evidence, but their counter definitions and sampling differ: compare each
against its own zero-error gate, not raw counter totals across controllers.

Each phase records image/core/firmware identity, test range and bytes, pattern
and seed, DDR/controller rate and measured traffic, initialization history,
elapsed time, temperature, error deltas and available first-error metadata.
MIG's existing vendor first-error address/data pipeline is unverified; do not
infer faulty DQ bits from corrected returned data or claim trustworthy failing
addresses until the capture alignment has been demonstrated.

Full-system restoration requires reviewed timing and relevant CDC paths,
working checking/counters, full usable capacity, zero observed corrected,
uncorrectable and comparison errors, repeatable startup/warm behavior and
extended mixed/retention coverage. The experimental LiteDRAM build's missing
external DDR pad delay budgets remain a qualification gap even if internal
timing passes. LLM output alone cannot satisfy these memory gates.

AMD recommends starting with its example design and checking both calibration
and data comparison:
[UG586 hardware debugging](https://docs.amd.com/r/en-US/ug586_7Series_MIS/Debugging-Common-Hardware-Issues).

## What counts as a pass

The vendor example's default address window is too small for this board's full
capacity. The builder changes each generator to native addresses
`0x00000000..0x0fffffff`. One native BL8 command accesses 64 payload bytes and
advances the native address by eight. The last accepted address must therefore
be `0x0ffffff8`, corresponding to byte offset `0x7fffffc0`.

The observer counts complete consecutive write and read command sequences,
independently of total traffic counts. Repeated reads of a small region cannot
satisfy the full-pass checks. Data-return and comparison counts must also cover
at least 33,554,432 beats. The host freezes a command-count target from a
snapshot containing a full read traversal, then waits until returned and
compared counts reach that target. Pending read data cannot be mistaken for a
completed test. Both corrected and uncorrectable ECC counts must
remain zero. MIG correction remains enabled; corrected data alone cannot hide
an error from the verdict. The cumulative bad byte-lane mask and failed-compare
cycle count are retained. Deliberate DQ48 corruption checks these detectors and
their coherent snapshot. The vendor first-error address/expected/actual record
is also saved, but its pipelines were found misaligned in injection testing.
It is marked unverified and is not used to identify failing bits or addresses.

The generated example's legacy burst-boundary expressions mix byte-oriented
quantities with native addresses. A stalled-port simulation showed clipped read
bursts with skipped ranges; the full-pass counter rejected them. The builder
retains a two-expression `vendor-traffic-bounds.patch` using exclusive native
ends (`address + burst_commands * 8 <= end + 1`). This correction is limited to
the traffic generator for this 4:1/BL8 configuration. MIG controller/PHY RTL is
unchanged. The generated traffic source is snapshotted before implementation.

The model also exposed two pattern-specific example issues. The PRBS LFSR
advanced under write backpressure without an accepted payload; a traffic-only
patch gates mode-7 PRBS advancement on actual write/read transfers. Fixed mode
kept its BRAM address at slot 8 while its ready condition waited for slot 7;
the zeros/ones build corrects that readiness condition. Each generated change
is retained as a patch beside the build. These corrections affect the test
generator, and provide no evidence of a repaired physical DDR channel.

The vendor's default watchdogs assume mixed reads and writes. They are disabled
for this fill-once/read-repeatedly mode. The observer instead latches a failure
after 65,536 UI cycles without an accepted command, or without returned read data
after initialization. A new snapshot requires the selected channel's UI clock
to be alive; missing acknowledgment is a failed acquisition.

These counters prove the observed pattern coverage. They do not establish all
patterns, cold starts, warm conditions, retention or full OpenTPU operation.

## Build on Fedora

Requires Vivado with Kintex-7 support and Python 3. The XML pin/configuration
reference is tracked at
[`boards/ypcb-00338/ramtest/mig-ddr3-1066.prj`](../boards/ypcb-00338/ramtest/mig-ddr3-1066.prj).
It is copied from the previously exercised MIG image, with all pin selections
preserved. The builder derives DDR3-800 using a 2500-ps period, 800-MHz MMCM VCO,
CL6 and CWL5. Vivado generates vendor RTL locally; generated vendor source is
not required in Git.

```bash
python3 tools/fedora_build_ramtest_mig.py \
  --vivado /home/fedora/vivado/2026.1/Vivado/bin/vivado \
  --ddr-mts 800 --channels both --pattern address --build-id c0161001 \
  --out build/ramtest-mig-800-address
```

Choose a new output directory for every attempt. `--prepare-only` generates IP
and the diagnostic source without synthesis/implementation. `--channels 0` or
`--channels 1` isolates traffic. `--pattern` accepts the six patterns listed
above. `--ddr-mts 1066` retains the original timing configuration. Assign a
distinct `--build-id` to each image so receipts identify the exact experiment.

Outputs include source snapshots/hashes, generation/build logs, routed checkpoint,
timing/route/CDC/bus-skew/IO/DRC reports and `ramtest.bit`. Completion requires the
manifest status `RAM_ONLY_BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING`; preparation or
synthesis alone is insufficient. Review CDC and independently check packet CRC
before transferring an image. The tool never accesses a card or writes flash.

### Build the remaining MIG variants

The sequential suite adds the seven DDR800 images below. The both-channel
address baseline is already packaged and is not rebuilt by this command.

| Variant | Traffic channels | BUILD_ID |
| --- | --- | --- |
| Address | CH0 only | `c0161010` |
| Address | CH1 only | `c0161011` |
| Zeros | Both | `c0161020` |
| Ones | Both | `c0161021` |
| Walking one | Both | `c0161025` |
| Walking zero | Both | `c0161026` |
| PRBS | Both | `c0161027` |

```bash
python3 tools/fedora_build_ramtest_suite.py \
  --out build/ramtest-mig800-suite
```

Use a fresh output directory. Each image has separate generated IP, frozen
sources, implementation reports and packet/CRC checks. The suite runs one
builder at a time and preserves failures. Its aggregate manifest distinguishes
queued, building, failed and built images. Completed children still require
their own pin/CDC review and packaging before transfer; the suite never labels
them physically tested.

Review each completed child before packaging, for example:

```bash
python3 tools/fedora_review_ramtest_mig.py \
  --build build/ramtest-mig800-suite/ch0-address \
  --out build/ramtest-mig800-suite/ch0-address/offline-review.json
```

This checks the exact image and frozen source hashes, DDR geometry, all 242
board-reference pins, timing coverage, route, CRC and four bus-skew paths.
The two critical vendor reset findings must match exactly. Held-payload warnings
must match the reviewed address image after narrowly normalizing Vivado's choice
of snapshot mux input bit and replicated mailbox capture register names. This
requires identical protocol/constraint sources and four passing skew checks.
Other new findings stop the review for investigation.

The active October 16 queue is now
`build/fedora-vivado/ramtest-mig-suite-priority-20261016/`. It builds the RAM
diagnostics immediately following the user's debug-first priority; the
already-running compute-clock attempt continues independently. The earlier
queue, which waited for compute packaging, was superseded before any child
build started. Its manifests and logs remain preserved. The optional
`--wait-unit UNIT.service` can defer a future suite until an existing service
terminates; it never restarts that service.
A separate job reviews and packages each successful child under
`bitstreams/ramtest-mig-ddr800-<variant>/`; it does not stage, commit or push.
Inspect the queue's `manifest.json` and `package-manifest.json` for actual
progress. Pending jobs are not completed images.

### Matched LiteDRAM comparisons

The new RAM-only LiteDRAM procedure (local-only `docs/ddr_ram_only_litedram.md`) uses the normal
ECC user ports and retains the real calibration CPU. One image can select the
six patterns, either or both traffic channels, mixed address-pattern traffic,
and a pause with normal refresh followed by another complete read pass. This
is distinct from the fill-once MIG image and the full-system reset candidate.
The baseline, isolated reset and registered-read images are built and packaged
with their independent reviews and stated external DDR timing limitation.
The baseline/reset/baseline physical comparison completed with three passes.
The registered-read comparison completed fail/pass/fail, with the failed states
saved before drain/reload. This motivates repeated comparison and a same-image
lane-6 read-window experiment; it does not yet establish a reliable repair.

The memory-test observer has a focused RTL simulation in
`tests/test_ramtest_mig.py`. Exercise the actual generated vendor traffic logic
with Icarus Verilog using:

```bash
python3 tools/check_ramtest_traffic.py \
  --ip build/ramtest-mig-800-address/ip/otpu_mig_ddr3/otpu_mig_ddr3/example_design/rtl/traffic_gen \
  --out build/ramtest-vendor-model-check
```

Add `--simulator verilator` to use Verilator. That model uses a 128-KiB window, separate command/write-data queues and
independent stalls. It checks all six patterns and deliberate read-data
corruption. It is a traffic-generator/observer simulation, not a DRAM PHY or
physical 2-GiB test.

## Establish Mac programming and status access

The Mac does not need Vivado to load a completed image. Its cable/programmer and
USER2 readback path have not yet been identified. An optional inventory helper
is available; the user declined this inventory, so it is not a prerequisite:

```bash
python3 tools/mac_fpga_setup_check.py --out build/mac-fpga-setup.json
```

The tool only checks versions, selected Python packages, USB
product names/VID/PIDs and hashes of the existing Chestnut scripts. It does not
open USB endpoints, inspect shell history, collect USB serial numbers or change
the FPGA. Inventory success does not prove programming support.

Load the reviewed `.bit` into SRAM with the identified JTAG tool. Retain the
working CH1 NOR contents. This image has no PCIe endpoint, so the Chestnut PCIe
adapter cannot read its status. It needs a cable backend exposing USER2; the
existing host protocol uses a localhost XVC server, not a vendor-specific Mac
driver. A normal openFPGALoader installation must not be assumed to support
XPCU-to-XVC without checking its build and cable backend.

### DLC10: reuse the Mac flasher's working source

Upstream's [XVC server constructor](https://github.com/trabucayre/openFPGALoader/blob/master/src/xvc_server.cpp)
does not select the XPCU backend. This repository's existing
`tools/fedora_prepare_xvc.py` adds mixed TMS/TDI transfers through the XPCU
encoder, selects that backend, checks USB transfer failures and binds the server
to localhost. Its compiler and pkg-config paths are now configurable for Mac
builds. A firmware file and the Mac-specific USB fixes must come from the
**same source checkout that already programs the card successfully**. The
preparer copies tracked source into a fresh directory; it leaves that donor
and its binaries intact. It does not access the cable.

With CMake, a C++ compiler, pkg-config, libusb and libftdi installed:

```bash
python3 tools/fedora_prepare_xvc.py \
  --donor /absolute/path/to/your/working/openFPGALoader \
  --out build/mac-xpcu-xvc --jobs 4 --no-select
```

Require `SERVER_COMPILED_PROTOCOL_PASS_PHYSICAL_NOT_RUN` in the resulting
manifest. The included protocol model checks partial-byte transfers, mailbox
frames, buffer boundaries and USB failures. A Fedora build/model pass does
not establish Mac USB operation. There is no dependency on Fedora's `~/ypcb`
when `--donor` is supplied. Reuse the working Mac flasher's cable initialization
and firmware path; do not run the Fedora-specific `dlc10-init.sh` on Mac.

Once the reviewed address-test image is available, these are the DLC10 commands
from the repository root. Replace the firmware path with the one used by the
working Mac flasher:

```bash
XPCU_LOADER="$PWD/build/mac-xpcu-xvc/binary/openFPGALoader"
XPCU_FW="/absolute/path/to/working/xusb_xp2.hex"
"$XPCU_LOADER" --cable xilinxPlatformCableUsb --freq 6000000 \
  --probe-firmware "$XPCU_FW" --detect
```

Require a single FPGA with IDCODE `0x23751093`. Load the `.bit` with
`--write-sram`, then run the server in a separate terminal:

```bash
"$XPCU_LOADER" --cable xilinxPlatformCableUsb --freq 6000000 \
  --probe-firmware "$XPCU_FW" --write-sram /absolute/path/to/reviewed/ramtest.bit
"$XPCU_LOADER" --cable xilinxPlatformCableUsb --freq 6000000 \
  --probe-firmware "$XPCU_FW" --xvc --port 3721
```

Leave the server in the foreground while collecting snapshots. SRAM loading
does not write the working CH1 NOR image. A completed programming log and a
successful `RAMT` readback are separate requirements. These commands remain
unverified on the Mac until their actual logs are returned.

After that server and SRAM load are established, use the Mac environment that
already has NumPy:

```bash
build/chestnut-lfm/venv/bin/python tools/probe_ramtest_mig.py \
  --host localhost --port 3721 --expect-build-id c0161001 \
  --seconds 300 --out build/ramtest-mig800-address-cold-1
```

The reader verifies the `RAMT` identity, ABI and expected build ID before issuing
a status-snapshot request. It does not reset, retrain or write memory. Save
`manifest.json` and `samples.jsonl` for each run. Use fresh directories for warm
and cold repetitions. A missing XVC endpoint is a transport failure and provides
no evidence about DDR.

## Interpret the comparison

| Result at matched speed and test conditions | Next investigation |
| --- | --- |
| RAM-only MIG passes, RAM-only LiteDRAM fails | LiteDRAM reset, training, PHY timing and implementation |
| Both fail on the same physical byte lane | Shared pin configuration, board power, signal integrity, FPGA IO and DRAM path |
| Both pass RAM-only but full OpenTPU fails | Integration, clocks, resets, concurrent load and memory-interface traffic |

Repeated failure with two controllers strengthens the case for a shared
electrical/card problem. Confirming the component responsible still needs
measurements or comparison with another card.

## Local DDR references checked in `~/ypcb` (October 16)

The reference scan inspected the actual archives, test source and saved results.
`${YPCB_ROOT}` is normally `~/ypcb`; no donor checkout was modified.

| Reference | Useful material | Evidence and limitations |
| --- | --- | --- |
| `ref/LC480T/YPCB-00338-1P1/XC7K480T_MEMTest.zip` and `XC7K480T_platform.zip` | Matching supplied `.bit`, `.mmi`, ELF and hardware platform; independent MIG/CPU reference | The supplied test covers only 4 KiB/channel. Its final success message is unconditional; inspect every individual result. This older platform has DDR at 0/0x80000000, local BRAM at 0x100000000 and an ELF64 MicroBlaze application. Keep its image, MMI, BSP and ELF together. |
| `projects/ypcb_00338_1p1_hack/scripts/fedora_ddr_full_core.h` | Full-capacity address/complement algorithm with distinct data for each channel; fills both channels before verifying either | The built `ddr_full.elf` exists, but its readiness receipt says `HOST_READY` and `physical_test: NOT_RUN`. The separate 4-KiB diagnostic's hardware attempt stalled in CPU startup with no DDR result. |
| `projects/bonetto-soc/boards/ypcb-00338/README.md` and DDR SERDES probes | Historical lane fault, direct physical-lane selection, IDELAY sweeps and raw DQ/DQS capture ideas | Historical workaround used 32-bit data and bypassed physical lane 3. The current init-only probe blocks DDR reads/writes; zero idle captures do not prove memory data works. Our observed failure is lane 6. |

The archived MEMTest `.bit` SHA256 is
`1fff925c98ef2d5abdb3b21d9cf58fb24c4eb42e90a81230513d182a30bba2e6`
(18,735,115 bytes, header date May 15, 2024), distinct from the newer staged
TiferKing baseline. Its matching `.mmi` offers an offline ELF-to-BRAM merge
route on Fedora, subject to a separate image/ELF/map audit and a working output
reader on the Mac. This image is a CPU/MIG system, not our minimal RAM-only top.

The failing lane's eight DQ pins and both DQS pins match the LC480T
`MEMORY_CH0.ucf` reference exactly. This confirms another pin-reference match;
it does not measure the electrical path or establish a card defect.

These references add two follow-up checks to the plan:

1. Use the full-core algorithm's **channel-distinct address data and complement**
   for the eventual 4-GiB host-visible mapping test. Fill both channels before
   reading either, so a shared/aliased channel cannot appear to be two memories.
   The first MIG address-pattern image does not establish this cross-channel
   aliasing check.
2. If matched MIG/LiteDRAM runs still fail lane 6, add **raw lane-6 DQ/DQS
   capture and a delay sweep** to separate missing activity from bad sampling.
   Preserve each capture's traffic, tap and temperature conditions.
