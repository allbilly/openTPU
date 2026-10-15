# Bitstream CRC qualification and full-image follow-up

The independent checker matches **both CRC checkpoints in each completed
Vivado image**: the original DDR1066 MIG image and the matched DDR800 reference.
It checks actual register/data writes, including the MIG image's compressed
and multiple-frame-write sequence. No original bitstream was changed.

The X-Ray-generated corrected-DSP fixture has **zero CRC checkpoints** and
three CRC resets. The pinned `configuration.cc` generator emits that sequence.
Its earlier `NOT_CHECKED` receipt remains accurate; frame ECC and CRC are
separate checks. AMD documents CRC-register writes as comparisons against the
calculated bitstream CRC, and RCRC as a reset, in
[UG470](https://docs.amd.com/api/khub/documents/FOs3lXmlcWxBhTIFxVKyGA/content).

## Qualified offline conversion

A separate fixture copy replaces the two CRC resets after frame loading with
CRC checkpoints. The first initialization reset is preserved. Only four
32-bit words change: two packet headers and their CRC values. All other bytes,
including frame data, file size and packet boundaries, remain unchanged.

The new copy passes both CRC checks and an independent comparison of all
**46,336 legal frames**, **4,683,168 payload words**, frame ECC, implicit-zero
frames and padding. Copies with a flipped bit in real frame payload or a
stored CRC value fail. Four Project X-Ray known-answer vectors also pass.
The production converter reproduces the qualified copy byte for byte. Its
full-image guard returns 2 while the actual parent is live and creates no output.

This is a 64-DSP fixture, not a full accelerator image. It establishes the CRC
conversion and unchanged-frame behavior for the pinned native writer sequence;
full numerical timing and physical execution remain unqualified. The initial
frame comparison used an incorrect part-database directory and failed before
comparison. That receipt is preserved. The successful check uses the pinned
`xc7k480tffg1156-2/part.json`.

- [CRC arithmetic, both Vivado images, fixture conversion and corrupt-copy checks](../build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/manifest.json)
- [Actual converter fixture](../build/fedora-openxc7/crc-image-fixture-check-20261013T152400Z/manifest.json)
- [Converter reproduction and live-parent guard](../build/fedora-openxc7/crc-image-converter-qualification-20261013T152500Z/manifest.json)
- [C++ checker](../tools/openxc7_bitstream_crc.cc)
- [Guarded converter](../tools/openxc7_bitstream_crc_image.py)

## Current full-design follow-up

The active service is `opentpu-crc-image-followup-20261013t153000z.service`,
controller PID 484066, invocation `40fa0c8974c447ae9d5f34542ba7a065`.
It has a 4 GiB memory cap and 1 GiB swap cap and waits for the existing
`opentpu-dsp-image-followup-runtime-20261013t140400z.service`.

Before conversion it requires unchanged parent/native service invocations,
actual successful exits, the completed full DSP image, all 717 corrected DSPs,
preserved VREF and the full source/tool/database inventory. It creates a separate
candidate and repeats complete CRC, packet/frame/ECC and provenance checks.
The full profile remains MCOLS4 / ACT_ROWS4 / LANES8 / VPU_CL2 / MXU_IMPL2 /
core100 MHz / dualDDR800.

[Live follow-up receipt](../build/fedora-openxc7/crc-image-followup-20261013T153000Z/manifest.json).
The eventual file is
`build/fedora-openxc7/crc-image-followup-20261013T153000Z/image/design-with-crc.bit`.
It does not exist while routing and upstream image work remain incomplete.

The expected final status is
`FULL_DSP_CORRECTED_IMAGE_CRC_CHECKPOINTS_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED`.
This is an offline gate. Hardware readiness remains false pending full timing
and configuration qualification; the follow-up never programs hardware.

The native route, original image follow-ups and Vivado hardware watcher retain
their identities. The CRC checker, converter and follow-up sources are pinned
while this service is live.
