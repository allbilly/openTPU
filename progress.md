# OpenTPU progress

**2026-10-22 13:36 HKT: the c01848 runtime-clock effort is abandoned at the user's instruction.**
No further c01848 revisions, implementation, review, packaging or hardware tests are scheduled.

| Item | What changed | Final state |
|---|---|---|
| Active c01848 work | Removed from the todo plan | None; no related live workers |
| Latest corrected source | c0184812 source validation completed | P&R not admitted; no flash-ready new bitstream |
| Fixed-clock fallback | Retain c0182863 and c0182800 artifacts | Preserved; no new hardware operation |
| Sources and results | Preserve all historical evidence | Retained in place |

Exact cancellation evidence and final state: [HANDOFF.md](HANDOFF.md).
Earlier progress tables are preserved under `build/handoffs/history/runtime-clock-abandoned-20261022T053626Z` and in HANDOFF.md.

## Retained bitstream tests — documentation reviewed October 23

These are recorded results, not a fresh hardware run or a scheduled test queue.
All five images below completed build/offline review and preserve full 4 GiB,
spare-lane CH0, CH1 ECC, and both JTAG/PCIe runtime interfaces. Exact bitstream
hashes, calibration methods, evidence links and limitations are in the
[tested-build and outstanding-test table](docs/bitstreams.md#tested-builds-and-outstanding-tests).

| Build | What changed | Tests recorded as passed | Still pending |
| --- | --- | --- | --- |
| c0182800 | CH0 shared-response/reset repair; 100 MHz / DDR800 | Local SRAM/TinyStories/native-read; permanent program/verify/flash boot; Mac LFM/Qwen | Cold/warm repeats and broader reliability/comparisons |
| c0182863 | 148.837 MHz / DDR1066.667; quantizer timing correction | Local SRAM/TinyStories/native-read; permanent program/verify/flash boot; Mac LFM/Qwen | Repeats, faster-startup experiment, wall profiling; later modeled bridge/reset corner findings remain unresolved in this image |
| c0182600 | Both-channel automatic calibration; 100 MHz / DDR800 | Local SRAM/startup/TinyStories/runtime postflight/native-read | Mac PCIe/LFM/Qwen, repeatability; permanent programming/boot not performed |
| c0182663 | Both-channel automatic calibration; 148.837 MHz / DDR1066.667 | Local SRAM/startup/TinyStories/runtime postflight/native-read | Mac PCIe/LFM/Qwen, repeatability; permanent programming/boot not performed |
| c0182461 | DDR1066.667 at 100 MHz compute; optional comparison | Local SRAM/TinyStories/native-read | Mac acceptance and repeatability if selected for comparison; no permanent programming recorded |

The c0182600/c0182663 guides document local preparation. Their matching Mac tools
and runtime bundles remain unpublished and require a separate reviewed handoff
before Mac use; the documentation alone is not a runnable runtime release.
The last recorded permanent image was c0182863; current physical identity and
ownership were not rechecked. Rejected attempts and the abandoned runtime-clock
series are excluded from the pending-test list. Historical receipts remain intact.
