# Basic OpenTPU operations

Small, standalone examples in the same style as the RK3588 examples: generate
inputs, compile an operation, execute it, and compare every output with NumPy.
Run commands from the checkout root using Python 3.10 or newer with this project's
dependencies installed (`python -m pip install -e .`).

The default backend is the bit-exact **ISA simulator**. It executes the emitted
OpenTPU instructions; NumPy supplies the independent expected result.

```sh
python examples/simple_add.py
python examples/elementwise.py --op relu --size 37
python examples/gemm.py --m 5 --n 7 --k 256
python examples/conv.py
python examples/pooling.py --op max
python examples/pooling.py --op avg
python examples/softmax.py --rows 3 --cols 37
python examples/rmsnorm.py --rows 3 --cols 37
python examples/run_all.py --out build/examples/basic-ops-001
```

| Example | Operation executed on OpenTPU | Data/layout |
| --- | --- | --- |
| `simple_add.py` | Vector addition | FP32 vectors |
| `elementwise.py` | Add, subtract, multiply, maximum, minimum, ReLU, absolute value | FP32 vectors; select with `--op` |
| `gemm.py` | Quantize activations, streamed int8 matrix multiplication | `A[M,K] @ W[N,K].T`; K is a multiple of 128 |
| `conv.py` | Int8 GEMM over host-extracted patches | Valid NHWC cross-correlation, no padding; output `[OH*OW,filters]` |
| `pooling.py` | Row maximum or sum/scale over host-extracted windows | Valid NHWC max/average pooling; flattened output |
| `softmax.py` | Row max, EXP2, sum, reciprocal | Stable FP32 row softmax |
| `rmsnorm.py` | Square, row sum, RSQRT, learned scale | FP32 rows; epsilon `1e-6` |

Use `--help` on each script for shapes and options. Individual tensors are limited
to 8,192 elements to keep these demonstrations small. Large reductions may also
reach compiler resource limits. Convolution limits `kernel² * channels` to 128
and pads that reduction dimension with zeros. Its patch extraction and pooling's
window extraction run on the host; these examples do not claim native convolution
or pooling instructions.

GEMM and convolution use integer-valued FP32 fixtures containing 127 in each
quantization block. Their activation and weight scales are exactly one, allowing
an exact integer NumPy comparison. Arbitrary floating-point tensors would require
a reference that accounts for quantization error. Other examples use exact
comparisons or small FP32 tolerances recorded in each result.

## Instructions and saved results

```sh
python examples/gemm.py --show-program --out build/examples/gemm-001
```

Each **fresh** `--out` directory contains:

- `program.asm` and little-endian `program.bin`: the emitted instructions.
- `dram.bin`: the initial 1 MiB logical memory image, including inputs/weights.
- `out.npy` and `out.reference.npy`: actual and NumPy reference arrays.
- `result.json`: backend, configuration, hashes, instruction count, numerical
  checks, timings and PASS/FAIL state. Existing directories are never overwritten.

The batch runner saves a `summary.json` and one directory per operation. It stops
on the first failure. `run_wall_seconds` includes the ISA reference run and any
backend startup; it is not a device throughput measurement.

## RTL simulation

```sh
python examples/simple_add.py --backend rtl --out build/examples/rtl-add-001
```

This uses the project's Verilator backend and additionally requires bit-exact
agreement with ISA output. Verilator and a C++ toolchain are required. A missing
simulation cache triggers the project's parallel RTL build, so schedule it around
priority FPGA implementation jobs. ISA validation and RTL validation are separate
results; the initial examples validation covers ISA only.

## Physical runtime image

The optional `--backend fpga` path uses `ReviewedRuntimeProfile` and
`RuntimeBoardBackend`, including exact image/software package checks, exclusive
transport ownership, mode-bound calibration, complete zero/parity initialization,
full uploaded-image verification and mandatory program readback. It requires a
qualified **runtime-clock** image and its matching host sources. Fixed-clock
`c01826xx`/`c01828xx` packages are not accepted by this adapter, and neither is
c0182902, whose reviewed package binds through `SpareC0182902Profile` and the
c0182902 JTAG tools instead.

Physical execution of these examples has not been qualified. See `HANDOFF.md`
for current image readiness. Once the exact image and package are qualified,
an invocation has this form:

```sh
python examples/simple_add.py --backend fpga \
  --package "$RUNTIME_PACKAGE" --transport jtag --mode 2 \
  --xvc-host 127.0.0.1 --xvc-port 3721 \
  --out build/examples/jtag-add-001
```

`RUNTIME_PACKAGE` must identify that reviewed package; a source preparation is
rejected before device opening. The matching full source checkout can be selected
with `OTPU_EXAMPLES_SOURCE_ROOT` when it differs from this checkout. The adapter
validates live geometry against the compiled example and reads back only outputs,
without allocating a 4 GiB host array.

Modes are `0`: 100 MHz/DDR800, `1`: 148.837 MHz/DDR800, `2`: 100 MHz/DDR1066,
`3`: 148.837 MHz/DDR1066. Select `--transport chestnut` on the Mac or
`--transport xdma --dev /dev/xdma0` for Linux XDMA. JTAG requires the existing
reviewed XVC/runtime connection; these scripts do not start a cable server.

Activation changes runtime clock mode and replaces model/program memory. A new
model attachment requires the backend's SAFE state or a destructive DDR-mode
transition; follow the exact image's reviewed workflow. Running separate scripts
does not bypass that requirement. The batch runner therefore supports ISA/RTL
only. These examples never configure SRAM or write permanent flash.
