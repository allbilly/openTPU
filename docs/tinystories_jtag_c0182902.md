# TinyStories-15M int8 end-to-end JTAG run on c0182902

Small trained-model acceptance on the exact reviewed dual-interface image
`c0182902` (JTAG USER2 runtime memory/control plus PCIe Gen2 x8, 133.333 MHz
core, DDR1066, 4 GiB, CH0 ECC off / CH1 ECC on, `SEQ_WC` enabled).

Recorded evidence: `docs/data/c0182902-tinystories-jtag-20261107.json`.
Physical run receipts (local, not committed): the paths named by each entry of
that record.

## Result

| Item | Value |
| --- | --- |
| Status | `PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS` |
| Build ID | `c0182902` |
| Package SHA-256 | `72193faf07305e45503b11331e698b9fd46a86199d4486e250975cc3fb1737be` |
| Bitstream SHA-256 | `3b804b81456f7c075a83e965bd012ec84865293a0ea18e1d55746c1ed79838cf` |
| Prompt | `Once upon a time` |
| Expected token IDs | `29892, 727, 471, 263, 2217, 7826, 4257, 365` |
| Actual token IDs | identical (exact match) |
| Calibration after run | unchanged |
| Inference programs read back | 13 of 13 `PASS_PROGRAM_READBACK_AND_LOAD_COMPLETION` with WAITC |
| Warm repeat | `PASS_WARM_REPEAT_PHYSICAL_JTAG_TINYSTORIES_EXACT_ISA_TOKENS`, same tokens |
| Native read | **3.981 GB/s** median over three 64 MiB repeats |
| Full image checksum | `d32fd2844e1f5330bfa36bfd43374516fee7b141aefd731ad58eecb0e130e993` |
| Flash written | no |
| FPGA reconfigured | no |

The checkpoints before the model run also passed on the same image: 2,048 DDR
initialization chunks, a 1,371-instruction synthetic fetch with an exact 65-word
result, and an exact int8 matmul.

The warm repeat ran on the configured image without rewriting it: 0 image bytes
written, all 29,226,624 reused, calibration unchanged, and both channels' ECC
counters zero before and after.

## Native read bandwidth

Measured on the same configured image after the checksum pass, with memory
already initialized by the integration run. No scrub, no programming, no flash.

| Item | Value |
| --- | --- |
| Span read | 64 MiB in 16 KiB chunks, three repeats |
| Median logical read | **3.981 GB/s** (3.9815 / 3.9814 / 3.9814) |
| Device seconds per run | 0.016855 / 0.016856 / 0.016855 |
| DRAM read beats per run | 1,048,576 (= span / 64 bytes, exact) |
| Final 16 KiB chunk | matched on all three repeats |
| Calibration after | unchanged |
| ECC before / after | zero sec and ded on both channels |
| Die temperature | 56.2 °C after the run |
| Model image | untouched; 32 KiB re-read at the program-area boundary matched |

For comparison, the same benchmark on the older retained images measured
2.992 GB/s (c0182800, 100 MHz / DDR800), 4.453 GB/s (c0182863, 148.837 MHz /
DDR1066.667) and 3.033 GB/s (c0182461, 100 MHz / DDR1066.667). c0182902 at
133.333 MHz / DDR1066 gives 3.981 GB/s, between the 100 MHz and 148.837 MHz
images in the same proportion as its compute clock.

Scope: this is a synthetic native LD stream whose throughput comes from the
device's RUNNING and DRAM counters. Only the final 16 KiB chunk is compared,
and the read span covers the model image read-only plus the program area, with
stores going to an output buffer outside the span. It is not an LLM decode
rate, not a write-throughput result, and not full-range payload or retention
qualification.

## Image coverage

The model image is 29,226,624 bytes. It was written in one attempt, which
verified the first 4,194,304 bytes before being cancelled; a continuation
verified up to 15,728,640 bytes. The user then authorized starting inference
without reading the rest, so the passing run itself produced no full-image
checksum.

A later read-only pass closed that gap without re-running inference. Inference
writes only the I/O row area and the six KV cache slots, all of which end at
14,050,304 — below the 15,728,640 bytes already matched. The 13,497,984-byte
suffix was therefore provably untouched, and it read back equal byte for byte:

```
15,728,640 from the earlier readback receipts
+13,497,984 read afterwards
=29,226,624 matched, SHA-256 d32fd284…e130e993 (equal to the offline image)
```

The verification read only; calibration was unchanged and the ECC counters
stayed at zero. Inference and verification therefore ran on the same configured
image, but not in the same process.

## Reproduce

Offline inputs are bound to the reviewed package and model:

```sh
build/fedora-venv/bin/python -B tools/check_tinystories_c0182902_model.py \
  --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --out "$ORACLE_OUT"
```

`$HOST_TREE` is the c0182902 host preparation tree (the package copy is
unmodified; the corrected oracle uses `SEQ_WC=True`). The runner's offline
preflight needs no hardware and performs no flash write:

```sh
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
build/fedora-venv/bin/python -B tools/run_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE_OUT/manifest.json" \
  --out "$PREFLIGHT_OUT" \
  --calibration-receipt "$CALIBRATION_RECEIPT"
```

`--execute` additionally requires an owned XVC connection
(`--xvc-host/--xvc-port`), the image-bound CH0 calibration receipt, and the
corrected oracle. Resuming a completed preflight uses
`--reuse-physical-preflight`; a verified partial upload uses
`--reuse-partial-upload`. The authorized skip path adds
`--cancelled-readback-receipt` and `--skip-resumed-image-readback`, which is
guarded to require both receipts, `--execute`, an idle error-free board, an
unchanged calibration snapshot, and no prior inference program receipts.

Repeating the generation on an already verified image uses
`tools/repeat_tinystories_shared_jtag.py`, which requires a passing prior
receipt and writes no image bytes:

```sh
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
build/fedora-venv/bin/python -B tools/repeat_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE_OUT/manifest.json" --out "$REPEAT_OUT" \
  --prior-run "$PASSING_RUN_DIR" \
  --calibration-receipt "$CALIBRATION_RECEIPT" \
  --xvc-host 127.0.0.1 --xvc-port 3721 --execute
```

Completing image coverage uses `tools/verify_tinystories_shared_jtag.py`, which
requires the inference-written regions to end inside an already verified prefix,
reads only the remaining suffix, and combines both parts into one image hash:

```sh
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
build/fedora-venv/bin/python -B tools/verify_tinystories_shared_jtag.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --model build/models/TinyStories-Llama-15M-tiles128-20261018-v2 \
  --oracle "$ORACLE_OUT/manifest.json" --out "$VERIFY_OUT" \
  --prefix-receipt "$CANCELLED_READBACK_DIR" --run-receipt "$PASSING_RUN_DIR" \
  --calibration-receipt "$CALIBRATION_RECEIPT" \
  --xvc-host 127.0.0.1 --xvc-port 3721 --execute
```

JTAG readback runs at roughly 1.8 KB/s, so a suffix pass takes about 1.5 hours.

The native-read benchmark uses `tools/run_spare_c0182902_bandwidth.py`. It reads
a span and compares only its final 16 KiB chunk; it writes the program area
directly above the model image and an output buffer outside the measured span,
so the image stays byte-identical. It never scrubs, so memory must already be
initialized:

```sh
PYTHONPATH="$HOST_TREE:$HOST_TREE/tools:$PWD/tools" \
build/fedora-venv/bin/python -B tools/run_spare_c0182902_bandwidth.py \
  --build-id c0182902 --host-tree "$HOST_TREE" \
  --package bitstreams/spare-dual-host-4gb-c0182902-exact-review \
  --calibration-receipt "$CALIBRATION_RECEIPT" \
  --xvc-host 127.0.0.1 --xvc-port 3721 \
  --span 67108864 --repeats 3 --out "$BANDWIDTH_OUT"
```

`--model-only` checks the program geometry in the ISA simulator with no device
access.

None of these scripts performs programming or a flash write. Permanent
programming and PCIe runtime/bandwidth qualification remain separate steps.
