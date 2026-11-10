# Upstream DDR branch review, October 16, 2026

This is a historical branch snapshot and experiment plan. Current disposition
is recorded in [HANDOFF.md](../HANDOFF.md): the fixed-clock c0182800/c0182863
artifacts are retained and the c01848 runtime-clock effort was abandoned.
The proposed builds and priority order below do not schedule new work.

Reference checkout: `~/upstream_openTPU`, upstream `FeSens/openTPU`.
Main was `f237dab2f196855a59a083b1454786df8f01291f`.
All **190 live remote branch heads** were compared with the checkout's remote
refs; all matched. The [saved branch audit](data/ddr-upstream-branches-20261016.json)
records every head, calibration-fix ancestry, calibration-source tree digest,
and DDR-related commits not reachable from main. The scope is the LiteDRAM
tools/generated core plus host DDR calibration and memory calibration.
This inventory and scoped source/ancestry comparison is not a manual audit of
every line in all 190 branches, nor a physical qualification of those branches
or of our card. The live head listing was also reachable during the later
October 16 review; the external review's enumeration failure does not apply to
this saved local inventory.

## What the branches contribute

| Branch or change | Finding | Action for our CH0 investigation |
| --- | --- | --- |
| `litedram-int` (`c8b4d49a`) | Standalone PHY/calibration investigation; the old branch does not contain the integrated core package | Use its measurements and diagnostic methods; no wholesale merge needed |
| `ld-top` (`1b97d90d`) | Full-system integration of the earlier PHY work | Historical comparison, not a new lane-6 repair |
| `d2c1ede8` | Read ISERDES uses static write clocks | Already in our history and shipped DDR800 core; verified generated clocks are `sys4xw0a/sysw0` and channel-1 equivalents |
| `8cbfd3ba` | Per-bit read framing through `dly_sel_bits` | Already present, including the generated DDR800 bit-select logic |
| `ld-cpu` / `ld-cpu2` (`32f2b1ad` / `7c5b08f6`) | Calibration CPU and host-driven hold/release, comparison and rerun tools | Our image already has the CPU; use controlled warm rescans to measure drift |
| `ld-phy` (`e0bef4b4`) | Per-pad serializer resets and registered calibration DFI issue | These older changes are already in our generator; distinguish them from the later reset stage |
| `ld-fmax` / `ld-fmax2` (`1425d078` / `49e7a691`) | CSR/reset/ECC-counter timing work, followed by documentation of remaining paths | Check the actual implemented reset/CSR/read paths rather than transplant an old branch |
| `f2d1023d` | Additional sys-domain register before the serializers' reset registers | Absent from the shipped DDR800 image; already isolated in our built `c0160001` candidate, physical result pending |
| `86bee3c3`, enabled in later main | Optional register after each read bitslip mux (`--rd-reg`) | Available in our generator but disabled in the shipped core. A controlled DDR800 variant with matched generated latency is a useful follow-up |
| `idle-refresh` (`c7911e94`) | Documentation of refresh timing and a proposed test | No automatic temperature recalibration implementation in this branch |
| `ld-2port`, `memeff`, fused variants | Native ports, scheduling and throughput/timing experiments | Keep out of the first fault-isolation comparison |
| `litepcie` (`ca47de35`) | Alternate PCIe transport and driver integration | No isolated CH0 PHY repair; changing transport would complicate the Chestnut comparison |

The static-clock and framing fixes are described in
[d2c1ede](https://github.com/FeSens/openTPU/commit/d2c1ede8) and
[8cbfd3b](https://github.com/FeSens/openTPU/commit/8cbfd3ba).
Their presence does not establish that every board has adequate timing margin.

## Source support versus the core actually built

| Image/core | DDR rate | Read latency | Later serializer-reset stage | Physical scope |
| --- | --- | --- | --- | --- |
| Shipped `ch1-pcie-2gb/core` | 800 MT/s | 8 (`rd_reg` off) | Absent | CH1 fallback; CH0 diagnostics remain |
| Current approximately 150 MHz compute build | 800 MT/s | 8 (`rd_reg` off) | Absent | Same memory core; new compute timing pending |
| Packaged [CH1 reset candidate](../bitstreams/ch1-pcie-2gb-ch0-reset/) | 800 MT/s | 8 (`rd_reg` off) | Present | `c0160001`: CH1 user mapping and raw CH0 diagnostics; physical comparison pending |
| Prepared dual-channel reset-experiment core | 800 MT/s | 8 (`rd_reg` off) | Present | Full 4 GiB source preparation; implementation pending |
| Reference checkout's main core | 1066 MT/s | 9 (`rd_reg` on) | Present | Upstream's own builds/card, not our DDR800 image |

Current main also has a two-stage CSR pipeline (7-cycle access), reset/refresher
timing changes, DDR placement constraints and additional `c0_ded/c1_ded` top
ports. Its generated core is not a drop-in replacement for our pinned port ABI.
Regenerate a deliberate DDR800 experiment and its matching metadata when
testing one change. Editing a host read-latency value cannot enable `rd_reg`.

## Evidence that changes our plan

1. **The named September fixes are already present.** Applying their commits
   again is not the next experiment. Our observed fault is CH0 lane 6; the
   upstream framing observations concerned different DQ bits/lanes.
2. **Automatic temperature rescans remain proposed.** The upstream temperature
   tool can rescan periodically, but that does not prove an automatic runtime
   recovery policy exists. First measure drift without rescanning; then rescan
   deliberately while still warm and record whether the pass window moves.
   Calibration writes its test region, so run it with inference stopped and
   reinitialize the required test range afterwards. Its reset/reinitialization
   steps mean the rest of memory must not be assumed preserved either.
3. **Read-only tests do not cover every failure.** Upstream added
   `tools/qual/turnaround.py` for alternating reads/writes through the normal ECC
   path, and `167fd098` adds ECC snapshots after individual qualification steps.
   Our initial RAM-only image fills once and repeats reads. Mixed traffic is a
   required gate, not an established capability of that first image. Short
   turnaround and normal-refresh retention screens now move earlier in the plan.
4. **Latest main is not automatically the best physical reference.** Upstream
   `ec87de44` records ISA-exact outputs but two corrected CH0 words during heavy
   qualification of r22, and retains the earlier E3 image. Timing closure and
   correct tokens alone are therefore insufficient: require zero corrected
   and uncorrectable ECC events in the observed test scope.

References: [temperature-rescan design](https://github.com/FeSens/openTPU/blob/f237dab2f196855a59a083b1454786df8f01291f/docs/litedram.md#follow-up-temperature-rescans-not-built),
[reset change](https://github.com/FeSens/openTPU/commit/f2d1023ddded0a4d70b8810a715e173ea989efd7),
[per-step ECC logging](https://github.com/FeSens/openTPU/commit/167fd0988bfb5fba9c4cbf15c7a2a3aa59d6914f),
[r22 qualification record](https://github.com/FeSens/openTPU/commit/ec87de4473714fc2bbc4d5cc52734abef2c7c467).

## Revised order and readiness

1. **Validate instrumentation and preserve the RAM-only MIG failure.** CH0
   corrected errors reproduced twice; clean full-range reads preceded the
   failure on the repeat. Controlled cold-start qualification remains pending.
2. **Same-image traffic switching and write-once/repeated-read tests.** The
   separate CH0-only and CH1-only images each passed five minutes, but cannot
   isolate simultaneous traffic from implementation, calibration or temperature.
   The runtime MIG control/traffic model and implementation review passed;
   the image is packaged and reproduced CH0 corrected errors. Its first eight
   switching phases also showed errors persisting with CH1 paused.
   LiteDRAM ABI 2 completed eight same-image read phases: CH0 errors persisted
   with CH1 idle or reading. Initial write corruption remains unresolved.
3. **Pattern coverage and small mixed/normal-refresh retention screens.**
   Separate images remain screening tools. Both-channel zeros and ones passed
   five minutes at higher die temperatures than the address repeat's failure.
   Future causal pattern comparisons should reuse one runtime image.
4. **Matched RAM-only LiteDRAM DDR800 baseline.** ABI 1 stalled before any
   accepted memory command; it is not evidence of DDR data failure. Corrected
   ABI 2 is built and packaged. Its full-range native traffic found CH0 ECC
   and comparison errors with CH1 clean; pause/drain controls worked. External
   DDR pad delay budgets remain a qualification gap.
5. **Controlled warm rescan and conditional PHY comparisons.** Preserve the
   failing state and maps first. The first ABI 2 warm CH0 rescan failed with
   no passing lane-6 phase, so no recovery test followed. The reset-only RAM
   image is packaged and baseline/reset/baseline each passed five minutes.
   The final baseline passed with all-0 write bitslip, also seen in earlier
   failures; bitslip alone is not a discriminator. The registered-read image
   is separately packaged with the original reset. Its physical comparison
   completed baseline fail/candidate five-minute pass/baseline fail. Later
   candidate reloads passed once then failed CH0; warm recalibration in that
   same registered-read image also failed on lane 6. Registered reads alone
   are not a repeatable repair. The earlier
   same-image transfer of the candidate lane-6 read window did not recover the
   baseline and did not behave reversibly when original settings were replayed.
   Keep generated latency and calibration interfaces
   matched, and distinguish implementation changes from initialization variance.
6. **Extended qualification, then full dual-channel OpenTPU last.** Multiple
   cold starts/warm initializations, full capacity, concurrent/mixed traffic,
   retention and zero corrected/uncorrectable/compare deltas precede DMA,
   exact matmul and LFM. The full 4 GiB candidate is building in the background
   at 100 MHz compute/DDR800 with the isolated reset change; an independent
   image review is queued. Hardware qualification remains pending.

The detailed [revised experiment order](ddr_ram_only_debug.md#revised-experiment-order)
is authoritative for gates and current image readiness. No physical defect or
specific LiteDRAM PHY cause has yet been established.

The independent CH1-only compute-clock experiment keeps DDR800 and bypasses CH0.
It does not establish a CH0 repair. See the [RAM-only procedure](ddr_ram_only_debug.md)
and [compute-clock build guide](ch1_compute_clock.md).
