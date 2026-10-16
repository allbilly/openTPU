# Chestnut CH1 benchmarks

These are physical measurements on the CH1-only PCIe image: 100 MHz core,
DDR3-800 RAM (400 MHz, 800 MT/s), MCOLS4/ACT_ROWS4/LANES8 and 2 GiB usable DDR.
Chestnut is connected
as USB3 at 10 Gb/s, with a downstream PCIe Gen2 x2 link.

The workload is 512 Austen prompt tokens followed by 64 greedy decode steps,
with a 1024-token KV capacity. Device rates use the FPGA cycle count at
100 MHz. FPGA columns show on-device rates; CPU columns use native elapsed time.
Model loading, conversion/upload and separate correctness checks are excluded.
Each row is one timed pass. These are different conditions from the
README production results on the 4 GiB dual-channel DDR1066 card.

All throughput rates below are tok/s. CPU columns use Q8_0
weights; the same CPU result is repeated for each FPGA weight profile.

| Model | FPGA weights | CPU prefill | FPGA prefill | CPU decode | CPU RAM BW | FPGA decode | FPGA RAM BW |
|:--|:--|--:|--:|--:|--:|--:|--:|
| LFM2.5-230M | INT8 | 1021.21 | 132.22 | 93.31 | 26.22 GB/s (38.4%) | 24.87 | 6.10 GB/s (95.3%) |
| LFM2.5-230M | FP4, INT8 head | 1021.21 | 236.13 | 93.31 | 26.22 GB/s (38.4%) | 37.12 | 6.09 GB/s (95.1%) |
| Qwen3-0.6B | INT8 | 189.57 | 43.47 | 25.24 | 20.01 GB/s (29.3%) | 9.16 | 6.10 GB/s (95.2%) |
| Qwen3.5-0.8B | INT8 | 150.74 | 35.08 | 23.68 | 22.69 GB/s (33.2%) | 7.38 | 6.08 GB/s (95.0%) |
| Qwen3.5-2B | INT8 | 95.20 | 15.23 | 16.40 | 35.72 GB/s (52.3%) | 3.07 | 6.10 GB/s (95.4%) |
| LFM2-2.6B | FP4, INT8 head | 69.04 | 9.33 | 11.81 | 35.34 GB/s (51.8%) | 4.22 | 6.10 GB/s (95.3%) |
| SmolLM3-3B | FP4, INT8 head | 51.98 | 15.61 | 6.60 | 26.03 GB/s (38.1%) | 3.39 | 6.10 GB/s (95.3%) |

FPGA RAM BW is measured decode traffic as a percentage of the single physical
CH1 payload peak: 6.4 GB/s at DDR3-800 on its x64 data bus. The two logical
memory regions share that channel. It uses `(DRAM_RD + DRAM_WR) * 64` bytes
divided by `RUNNING / core_hz`, then by the peak; it excludes host idle time.
The counters cover the decode snapshot interval, following tools/qual/perf.py.

CPU RAM BW is measured with the AMC Stats byte counters
`PCPU DCS RD/WR` and `ECPU DCS RD/WR`, sampled immediately before and after
the same 64-step native decode. Snapshot calls are excluded from throughput
timing. The bandwidth interval includes their timestamp uncertainty, whose
bounds are saved with the raw before/after counters.
These counters include all CPU processes and exclude GPU/I/O clients;
background CPU traffic is included. Percentages use the nominal base-M1
[68.25 GB/s peak](https://research-information.bris.ac.uk/files/314256436/paper.pdf),
as listed in the paper's platform table. The counter interface follows
[mactop v2.1.6](https://github.com/metaspartan/mactop/blob/v2.1.6/internal/app/ioreport.go).

CPU throughput and bandwidth come from the latest completed counter-enabled
pass for each model. Initial Qwen3-0.6B and Qwen3.5-0.8B decode rates of
6.32 and 1.50 tok/s were rechecked against the same GGUF files with the
original runner, the new runner without counters, and the new runner
with counters. The large slowdowns did not recur; paired counter-on/off
decode rates differed by less than 2%. The latest counter-enabled passes
are shown above. All initial passes and controls remain in the CPU data;
the cause of the initial slowdowns was not established.

Passing rows require exact ISA token comparison, physical matmul, full CH1
zero initialization/readback, ECC enabled with zero corrected/uncorrectable
errors, and restored temporary PCIe configuration. The full-vocabulary logits
currently return through USB control reads; end-to-end throughput is lower
than the FPGA device rates shown above. End-to-end timings remain in the raw receipts.

## Native CPU comparison

The selected models were measured on an Apple M1 MacBook Air
with 8 GiB RAM, using llama.cpp 0.5.0, 8 CPU threads and no GPU backend.
The CPU uses GGUF Q8_0 weights converted from the same pinned HF checkpoints.
It receives the same 512 HF-tokenized Austen token IDs, then performs 64
greedy decode steps after that prompt, with a 1024-token context.

CPU rates are wall-clock measurements from one timed pass after a full
prefill and one decode warmup. Conversion, loading and the chat sanity check
are excluded. Decode includes CPU argmax and finite-logit checks; EOS does
not end the fixed workload. CPU Q8_0 and FPGA INT8/FP4 use different
quantization and implementations, so these are system baselines rather
than identical numerical workloads. Host background activity and CPU
frequency were not controlled. [CPU receipts](data/chestnut_cpu_20261016.json)
record checkpoint revisions, token IDs, timings, generated text, runtime
and converter hashes. The chat sanity check is not an accuracy evaluation
or an exact FPGA token comparison.

Both Qwen3.5 conversions emitted reciprocal-overflow warnings on weights
at most 1.18e-37. An audit of the unchanged quantizer confirmed that all
affected stored FP16 scales are zero and all Q8_0 scales are finite.
Both audited GGUF files matched the measured files byte for byte.
The audit receipts are included with the CPU data.

## Model coverage

| Checkpoint | Status | CH1 profile or constraint |
|:--|:--|:--|
| google/gemma-4-E2B | EXCLUDED_BY_USER | fp4, 1387 MiB image; PLE table on host |
| google/gemma-4-E4B | EXCLUDED_BY_USER | Checked layouts exceed 2 GiB; not a hardware inference pass |
| LiquidAI/LFM2.5-230M | PASS | int8, 501 MiB image |
| LiquidAI/LFM2-2.6B | PASS | fp4, 1902 MiB image |
| LiquidAI/LFM2.5-8B-A1B | EXCLUDED_BY_USER | int8, 1680 MiB image; 4 expert slots/layer, host pool |
| microsoft/Phi-4-mini-instruct | EXCLUDED_BY_USER | fp4, 2022 MiB image |
| Qwen/Qwen3-0.6B | PASS | int8, 1248 MiB image |
| Qwen/Qwen3.5-0.8B | PASS | int8, 1751 MiB image |
| Qwen/Qwen3.5-2B | PASS | int8, 1885 MiB image |
| Qwen/Qwen3.5-35B-A3B | EXCLUDED_BY_USER | fp4, 1841 MiB image; 8 expert slots/layer, host pool |
| Qwen/Qwen3.5-4B | NOT_RUN_CAPACITY | Smallest of 32 checked layouts needs 2215 MiB including program; CH1 has 2048 MiB; recorded as requested by user |
| HuggingFaceTB/SmolLM3-3B | PASS | fp4, 1730 MiB image |

## Temperature during FPGA inference

A separate LFM2.5-230M int8 pass sampled the die sensor while RUN was
asserted and HALTED was clear both before and after each sensor read.
The workload was 512 prompt tokens followed by 64 decode steps.

| Phase | Active samples | Temperature range | Measured core clock |
|:--|--:|--:|--:|
| Prefill | 20 | 54.38–56.85 °C | 100.000 MHz |
| Decode | 64 | 54.38–56.11 °C | 100.000 MHz |

Clock estimates use the free-running UPTIME counter and host monotonic
time, with timestamp bounds around each SNAP write and readback. They span
each phase, including gaps between kernels. This pass showed no evidence
of thermal throttling and had zero ECC errors. These readings cover one
diagnostic pass.

The extra sensor reads affect host timing, so this diagnostic is excluded
from the throughput table. [Raw sensor and clock data](data/chestnut_ch1_thermal_20261016.json)
include the status words, sensor codes, timestamps and counter values.

## Reproduce

Install libusb, the `hf` CLI, NumPy, PyTorch, Transformers and safetensors.
Transformers must understand the checkpoint tokenizer configuration.

```sh
python tools/chestnut_checkpoints.py --model lfm2
python tools/chestnut_benchmark.py --model lfm2 --out build/chestnut-bench/new-lfm2
python tools/chestnut_report.py
```

For temperature and measured clock readings during inference:

```sh
python tools/chestnut_thermal.py --out build/chestnut-thermal/new-lfm2
```

For the native Apple M1 CPU baseline, use an existing Homebrew llama.cpp/ggml
installation, clang++, the Python environment above and a llama.cpp checkout
whose converter supports these models:

```sh
python tools/cpu_benchmark.py --llama-source /path/to/llama.cpp --measure-bandwidth --out build/cpu-bench/new-suite
```

The CPU script converts one cached checkpoint at a time in
`~/.cache/opentpu-cpu-bench` and removes only its temporary GGUF file.
Original HF checkpoints remain in `~/.cache/huggingface/hub`.

`chestnut_checkpoints.py` calls `hf download` with a pinned revision into
`~/.cache/huggingface/hub`, verifies published file hashes, and links `models/`
to the cache. `--wformat fp4 --head-format int8` selects FP4 layers.
`--quant-workers 4` packs independent rows in parallel using the standard
quantizer; this affects the excluded checkpoint-preparation phase.
Gemma E2B uses `--ple-host`; MoE models use `--expert-slots K` and a pool file.
No FPGA SRAM or flash programming occurs. The script refuses an unexpected
endpoint/image, dirty ECC, out-of-range memory, busy DMA or global SoC reset.

The compact [result data](data/chestnut_ch1_20261016.json) includes source hashes,
checkpoint hashes, tokens, timings, counters and coverage. Per-run logs and
original receipts remain in ignored `build/chestnut-bench/`.
