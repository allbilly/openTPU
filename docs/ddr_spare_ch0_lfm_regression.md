# CH0 pipelined LFM regression

**Recorded outcome:** the combined JTAG/PCIe c0182800 repair subsequently passed
local TinyStories and Mac LFM/Qwen; c0182863 has separate passing Mac receipts.
See [tested builds and outstanding tests](bitstreams.md#tested-builds-and-outstanding-tests)
for exact images, evidence and remaining qualification. The PCIe-only c0182301
prototype was retired. The c01848 runtime-clock effort was abandoned; the final
[handoff](../HANDOFF.md) supersedes earlier build and hardware plans.

The rest of this page records the October 18 investigation and its original
acceptance plan. The earlier serialized spare-lane image ran the model with
poor bandwidth; c0172300 then failed LFM. The corrected successors' results do
not turn the failed c0172300 image into a qualified image.

The user supplied the Mac run summary for
`build/mac-c0172300-lfm-20261017T153155Z/run.json`: exact live identity and
runtime preflight, CH0 calibration preserving CH1, 4 GiB zero write/readback,
and 32 exact matmul words in 333 cycles. LFM2.5-230M int8 failed after five
cycles with zero retired instructions and no tokens. Of 10,968 program words,
3,161 differed on CH0; CH1's 5,480 words matched. Calibration was unchanged.
Those are user-provided results; the Mac binary dumps are not locally present.
CH0 ECC is disabled; clean counters do not validate its data.

## Concrete integration defect

The image's frozen `otpu_mem_ch.sv` matches the current bridge source. Its
contract is explicit:

- At most one controller response port is valid in a cycle.
- Both response data buses carry the selected beat. The bridge uses
  `c_rdata_data[0]` for either port's tag, including read-modify-write data.
- Port 1's response must therefore also be on port 0's data bus.

The old `NativePortsPipelinedNoECC` connects a separate response FIFO directly
to each user port. Its port 1 valid can accompany stale port 0 data. That
violates the bridge contract even when each FIFO contains the correct data.
The previous isolated-port protocol model compared each port's own data and
could not catch this integration defect. Uniform zeros can also conceal it.

Bank parity selects the bridge port using native beat address bit 7 (8 KiB
per physical channel). A small workload confined to one parity can pass.
A larger program can use port 1; a read error can also corrupt the preserved
bytes of a subsequent partial write. This explains a credible mechanism for
the observed regression, but it does not prove the cause of every Mac mismatch
or exclude other defects without the original dumps and a physical rerun.

## Correction and checks

`tools/litedram/spare_native_pipeline_shared.py` preserves the two raw read
ports, 32 reserved credits per port, exclusive writes and masked RMW. It
arbitrates the internal response FIFO heads, emits one valid per cycle, and
broadcasts that beat on both user data buses. Selection stays fixed when the
chosen consumer stalls. The raw crossbar return is never stalled.

Run with the pinned LiteDRAM Python environment:

```bash
LD_PYTHON=build/fedora-openxc7/litedram-environment/venv/bin/python
"$LD_PYTHON" -B tools/check_spare_shared_pipeline.py \
  --out build/checks/shared-native-fresh
"$LD_PYTHON" -B tools/check_spare_native_bridge.py \
  --out build/checks/shared-bridge-fresh --jobs 2
```

The protocol checks cover credit saturation, long consumer stalls, payload
stability, independent command/data handshakes, both ports, full writes,
zero masks and exclusive partial-write merges. The bridge check generates
adapter Verilog and inserts it between the actual `otpu_mem_ch`, async FIFOs,
DMA split and the behavioral native controller. CH1 retains its reference
path. Byte scoreboards cover bank boundaries, partial DMA writes, backpressure,
cross-master visibility and resets with transactions in flight. The original
adapter must fail, while the serialized control and corrected adapter pass.

The first bridge harness attempt exposed a model restriction: its port parity
assertion was on the raw side, although the serialized adapter legitimately
routes all commands through raw port 0. The corrected harness checks parity
at the bridge output and disables only that assumption behind the adapter.
Address bounds, write-data/mask checks, byte scoreboards and CH1 parity remain.
The failed receipt is retained separately from the corrected test run.

These checks simulate protocol and bridge data flow. They do not model DDR
electrical behavior, qualify routed timing or establish card bandwidth.

The deeper `tools/check_spare_shared_controller.py` check also passed: the
real pinned LiteDRAM controller, crossbar, bank machines, refresher and tuned
multiplexer at DDR800 latencies passed six corrected bridge/DMA scenarios.
The old adapter failed, and the serialized control passed. A sparse data
scoreboard supplies the PHY read bus; this is not electrical DDR simulation.
Receipts are under `build/checks/spare-shared-real-controller-20261018-v1/`.

The matching LFM runner uses `ProgramReadbackBoard`: it compares exact program
bytes after upload and before any instruction-load control write. On mismatch
it saves expected/readback bytes and an error receipt, then withholds loading.
Eight host tests passed, including the reported 1,371-instruction size, partial
tails, both CHASH settings and injected CH0 read corruption. Exact DRAM
readback still does not establish exact IMEM contents or physical execution.

## Historical release and physical-acceptance plan

Existing frozen images keep their identities and inputs. At the user's
request, two running implementations, seven queued implementations, and their
review consumers were cancelled. Eight services have no surviving owned
processes. Completed images and the serialized fallback remain preserved.
Their registered-reset/clock changes did not fix the shared-bus defect.

The first correction was `c0182301`: preparation and synthesis started with
100 MHz compute, DDR800 and the existing capacity, lanes, CH1 ECC and firmware.
It retained only the original PCIe runtime interface and was subsequently
retired before the combined-interface c0182800 repair. Its frozen preparations,
review-worker records and failures remain evidence; they do not describe
currently scheduled work. The acceptance requirements below record the plan
that preceded the later c0182800/c0182863 results.

A corrected image needs a new build ID, exact source-bound bridge/protocol
receipts, numerical timing, routing, pin/CRC/integrity, CDC/Gray review and
packaging. Keep baseline clocks, lane mapping, ECC and calibration unchanged
for the first comparison. Temporary SRAM checks are already authorized when
the card is available; permanent flash needs approval for the exact new image.

On the Mac, preserve the current failure before changing configuration. Verify
address-sensitive data across both bank parities, exact full and tail/partial
transfers, the previously failing program's DRAM readback, and instruction
loading separately. Then repeat exact matmul and LFM tokens against the ISA
reference. A same-path write/read cannot independently localize writes versus
reads; use device-side comparison or another qualified observer when possible.
Measure matched device bandwidth only after correctness passes. No new
standalone full-capacity soak is required.
