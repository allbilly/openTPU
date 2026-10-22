# Runtime compute and DDR clock sweep preparation

**Final disposition: abandoned on October 22, 2026.** The user ended the c01848
runtime-clock effort. c0184811 completed implementation but failed setup timing;
c0184812 passed its recorded source checks, with placement/routing never admitted
and no bitstream. See [HANDOFF.md](../HANDOFF.md) and the
[tested builds and outstanding tests](bitstreams.md#tested-builds-and-outstanding-tests).
This document does not resume implementation, review, packaging or hardware work.

The c0182600 and c0182663 fixed-clock startup images subsequently passed local
JTAG tests; their Mac acceptance remains separate. c0182800/c0182863 have
recorded Mac LFM/Qwen passes. Physical card identity and ownership were not
rechecked for this documentation update.

## Historical October 18–19 preparation snapshots

The sections below preserve the earlier source design, component evidence and
proposed next steps. References to current owners, running jobs, pending
integration or build commands describe those snapshots, not a live queue.
The October 18 selector `build/handoffs/todo-priority-current-20261018.json`
does not override the final disposition at the top of HANDOFF.md.

This is preparation for one full 4 GiB spare-lane OpenTPU image with runtime
compute and memory clock selection. The full memory-core HDL has been generated
with an external clock/reset/lock interface and synchronized calibration hold.
**The complete runtime image, clock-control integration and Vivado implementation
are not prepared yet.** The existing fixed-clock builds continue.

Current component selector:
`build/handoffs/runtime-board-control-current-20261018.json`.
The connected board-control assembly passed 20 cases; the actual final
calibration-mailbox observer passed 12 cases; the generated memory core passed
217 source/reset/ABI checks. The mailbox observer waits for the CPU's final
state write because raw calibration-ready and the state CSR can become visible
earlier. These component results do not qualify the complete board, all-mode
timing/CDC or a physical clock transition.

Full source integration now starts from the frozen corrected 148.837 MHz
design in `build/fedora-vivado/spare-runtime-board-integration-20261018-v1/`.
Both actual native bridges export their tested observations through the native
subsystem, and the full accelerator exports registered idle/error/reset-held
state. Native-subsystem elaboration passed. The accompanying AON BD source in
`build/fedora-vivado/spare-runtime-aon-bd-20261018-v1/` exposes the raw PCIe
masters before SmartConnect queues, for upstream admission/drain guards. Tcl
source completeness was followed by actual Vivado validation and wrapper
generation in `build/checks/runtime-aon-bd-vendor-20261018-v1/`: 12 interfaces,
four clock ports, reset nets and 16 control-window address-map segments matched.
Full-top guards, clock/reset ownership and all-mode timing/CDC remain pending.
Current owners, firmware jobs and remaining full-top work are in
`build/handoffs/runtime-full-top-preparation-current-20261018.json`.

Both mode-specific, both-channel firmware binaries now reproduce their existing
IDs/checksums and pass seven host cases plus actual reference RV32 execution
against the selected runtime CSR map. The separate JTAG control-abort variant
passes 31 direct and 18 serial/controller cases, including a control-bus reset
that preserves the active transition engine. Its data-idle output is local to
AON. The full top must connect control-abort and bus-reset to the same coherent
control fabric/endpoint reset; those tests do not qualify board CDC or DDR.

The always-on AXI register bank and transition sequencer now exist as the
separate `rtl/boards/ypcb-00338/otpu_runtime_clock_ctrl.sv` component. Lint and
21 RTL simulation cases passed in
`build/checks/runtime-clock-control-component-20261018-v2/`, including AXI reset
isolation, abort ownership and fresh-drain/checkpoint recovery. The original
12-case proof and source remain preserved in v1.
Its drain/status signals and MMCM configuration engine are modeled boundaries;
the component is not connected to a complete board image yet. Reproduce with:

```bash
python3 tools/check_spare_runtime_clock_ctrl.py \
  --out build/checks/runtime-clock-control-new
```

The separate always-on JTAG frontend now has three AXI-Lite destinations:
accelerator, calibration and the clock-control window at `0x20000`. New data
accesses return `0x81` while admission is closed. A coherent data-fabric abort
returns `0x80` for an interrupted data access and preserves the independent
clock-control transaction. Closing admission alone never cancels an issued
AXI request. The clock-control endpoint must have its own always-on reset and
routing; a shared data-fabric reset must not reset that endpoint.

Strict lint, 24 frontend request cases and 15 serial mailbox/actual-controller
cases passed in `build/checks/runtime-jtag-control-component-20261018-v1/`.
The connected bench holds both target-clock signals low and covers mode access,
blocked data requests, START, visible configuration wait/fault and recovery.
It instantiates neither PCIe nor DDR. This is a component proof; the complete
board's two host paths and CDC/reset/native-tail integration remain unfinished.
The existing fixed-clock image sources remain unchanged. Reproduce with:

```bash
python3 tools/check_spare_runtime_jtag_control.py \
  --out build/checks/runtime-jtag-control-new
```

The current component is
`build/fedora-vivado/spare-runtime-shared-memory-core-20261018-v1/`.
It selects the corrected shared-response CH0 adapter and binds the native,
bridge and real-controller regression evidence. Five invalid-input cases were
rejected before generation. Six simulations of its actual calibration hold
logic passed, using a CPU bus-driver stub. These checks cover holding at startup,
draining an accepted bus request through acknowledgment or error, blocking new
requests and requiring both hold sources to release. They do not qualify clock
switching, asynchronous crossings or physical execution.

The older `spare-runtime-memory-core-hold-v2-20261017` component contains the
retired independent-response adapter. Preserve it as historical evidence;
do not use it for a new image.

The older `tools/prepare_spare_runtime_core.py` command now delegates to the
strict shared preparer. A legacy-entry regression confirmed that the old parent
is rejected before creating an output directory. The original tool source is
preserved with the component-retirement receipt.

The initial modes are 100 / 148.837209 MHz compute and DDR800 / DDR1066.667.
The image must retain both PCIe and JTAG access, the pipelined two-port CH0
shared-response adapter, registered shared reset, CH0 spare lane 8 without ECC
and CH1 with ECC.
The first DDR transition procedure may discard memory contents and reload the
model after reinitialization. Separate fixed-clock images do not implement this
requested runtime feature.

## One controller timing envelope

The pinned LiteDRAM source and the current WL7DDRPHY support a useful shared
structure for these first two DDR modes:

| Setting | DDR800 | DDR1066.667 |
|---|---:|---:|
| Controller clock | 100 MHz | 133.333333 MHz |
| DRAM CL / CWL | 6 / 5 | 7 / 6 |
| Read / write pipeline latency | 8 / 1 controller cycles | 8 / 1 controller cycles |
| Controller CWL cycle count | 2 | 2 |
| PHY read / write phase CSR | 3 / 3 | 2 / 2 |
| Half-cycle IDELAY tap estimate | 8 | 6 |

`tools/litedram/runtime_timing.py` derives these values from the same module and
latency functions used by the existing generator. It chooses the larger cycle
count for each minimum timing requirement. Refresh uses a maximum interval, so
it is bounded at the slowest clock instead. The prepared common `tREFI` is 780
cycles: 7.8 microseconds at DDR800 and 5.85 microseconds at DDR1066.667.
The current read/write structures can therefore share these cycle latencies;
the mode-specific DRAM commands and PHY phase settings still need selection.

Reproduce this source-level preparation with the pinned environment:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python -B \
  tools/litedram/runtime_timing.py \
  --out build/checks/runtime-ddr-timing-new
```

This writes numerical configuration metadata and source hashes. It does not
generate HDL, simulate DRAM or establish physical timing margin. ZQCS request
timing must also use the slowest controller clock as its reference.

## Full memory-core source preparation

The isolated generator retains both complete memory channels, CH0's two-port
pipeline and spare-lane mapping, CH1 ECC, native ports, raw calibration BIST and
the existing CSR map. Four new inputs connect it to the future board-level
clock controller: `runtime_sys_clk`, `runtime_mem_reset`,
`runtime_clock_ready` and `runtime_calibration_hold`.

Calibration hold passes through a two-stage synchronizer initialized to hold.
It uses the same between-access draining behavior as the existing software
hold. Before a frequency change, the controller must hold calibration and wait
for acknowledgment. After the new clocks run, software keeps the CSR hold set
while loading the matching firmware and phase settings. Only then can it release
the external hold and start calibration. This prevents boot-rate firmware from
running against the other rate's uninitialized settings.

The corrected hold-enabled core generation finished under
`build/fedora-vivado/spare-runtime-shared-memory-core-20261018-v1/`. Its unchanged
CSR map and full port inventory were checked during generation. This remains
source/interface evidence; the hold crossing and complete transition need
simulation and routed timing/CDC review.

Reproduce in fresh output directories:

```bash
python3 tools/prepare_spare_runtime_shared_core.py \
  --pipeline-preparation build/fedora-vivado/spare-shared-ddr1066-core-20261018 \
  --timing-envelope build/checks/runtime-ddr-timing-new/manifest.json \
  --adapter-model build/checks/spare-shared-native-20261018-v1/manifest.json \
  --bridge-model build/checks/spare-shared-bridge-20261018-v2/manifest.json \
  --controller-model build/checks/spare-shared-real-controller-20261018-v1/manifest.json \
  --out build/vivado/runtime-memory-core-new

build/fedora-openxc7/litedram-environment/venv/bin/python -B \
  tools/check_spare_runtime_calibration_hold.py \
  --preparation build/vivado/runtime-memory-core-new \
  --out build/checks/runtime-calibration-hold-new

python3 tools/prepare_spare_runtime_clocks.py \
  --out build/vivado/runtime-clock-ip-new
```

The clock IP preparer uses the installed Kintex-7 Clocking Wizard with dynamic
AXI control, a 50 MHz reference and an 800 MHz initial VCO. It generates source
for separate compute and memory clocks. It does not synthesize or route a board
image, implement the transition controller or validate runtime programming.

The next generated memory component adds activity observations in
`build/fedora-vivado/spare-runtime-activity-memory-core-20261018-v1/`.
Generate a fresh copy with `tools/prepare_spare_runtime_activity_core.py` using
the same arguments as the shared-core preparer above and a new output directory.
It preserves the full data path and every CSR CSV row except the generated
timestamp comment. Four two-bit outputs expose native, controller and PHY idle
and held protocol errors. These signals cover the actual shared adapter state,
ECC endpoints, raw crossbar completions/BIST, bank queue locks/timers and PHY
control pipelines. They do not stop refresh or implement a drain acknowledgment.

The real-controller model passed 28 cases across both rates and both channel
types; four fail-closed guards and 20 source/ABI checks also passed. Reproduce:

```bash
build/fedora-openxc7/litedram-environment/venv/bin/python -B \
  tools/check_spare_runtime_native_activity.py \
  --out build/checks/runtime-native-activity-new
```

Its PHY read bus is zero-filled. The physical PHY tap observations, board
bridge/native FIFO drain and held CDC acknowledgment still need full integration
and review. The checked registry is
`build/handoffs/runtime-native-activity-current-20261018.json`.

The first actual vendor reset probe covered the data-clock copy and passed
16 cases. Extending it to the command path's falling-edge stage reproduced six
missed assertions in sixteen cases. The earlier limited no-defect disposition
is superseded; the older runtime cores are retained as component evidence.

The selected corrected memory core is now
`build/fedora-vivado/spare-runtime-async-phy-memory-core-20261018-v2/`.
Its independent reset/clock-lock request asynchronously presets the serializer
reset copies. Each CLKDIV domain has a common two-stage release synchronizer
feeding the pad copies; assertion/release status is exported per channel.
The vendor graph passed 96 path/rate/phase/offset cases, and 211 generated-core
checks verified four shared chains, 163 pad copies and 341 serializer endpoints.
These are source/model results; full board reset/CDC and all-mode timing remain
required. Reproduce the corrected preparation using
`tools/prepare_spare_runtime_async_phy_core.py` with the activity-core arguments
and `--reset-proof` pointing to the matching successful vendor-check receipt.
The checker is `tools/check_spare_runtime_phy_reset.py`; generated-source binding
is checked by `tools/check_spare_runtime_async_core.py`.

The production bridge now also has a fresh observation-only derivative. All
original data-path source is preserved byte-for-byte. Seven production
numerical/CDC cases passed, also requiring both channels' local core/host/native
idle outputs at completion. This still does not implement the fresh held tail
acknowledgment or prove actual admission closure. Preparation and check tools:
`tools/prepare_spare_runtime_bridge_observer.py` and
`tools/check_spare_runtime_bridge_observer.py`.

## Clock control and transitions still to implement

### Prepared register and sequencer component

The proposed control window is BAR0 offset `0x20000`; no existing image exposes
this new register bank. Its AXI-Lite clock must remain running independently of
compute and memory. The current fixed-clock USER2 front end still runs from the
compute clock, so its relocation and both-interface routing remain required.

| Local offset | Register | Meaning |
| --- | --- | --- |
| `0x00` | ID | `0x4f545243` |
| `0x08` | Status | Phase in bits 3:0, active-valid bit 8, initialized/model-valid bit 9 |
| `0x0c` | Fault | Sticky transition failure code |
| `0x10` | Requested mode | Bit 0 selects 148.837209 MHz compute; bit 1 selects DDR1066; clear bits select 100 MHz and DDR800 |
| `0x14` | Active mode | Last successfully activated mode; check active-valid |
| `0x18` | Command | Full-strobe write of a command below |
| `0x1c` | Configuration target | Latched target mode and destructive-memory-change flag |
| `0x20`, `0x24` | Configured rates | Compute Hz and DDR thousands of transfers/s; not independent frequency measurements |
| `0x28` | Activation epoch | Increments only after successful activation |
| `0x2c`, `0x30` | Phase age | Low/high halves of the always-on cycle count |

Commands are `0x43540001` start, `0x43540002` calibrate,
`0x43540003` initialization done, `0x43540004` model ready and
`0x43540005` recover to the safe state. Unsupported modes, partial command
writes, commands in the wrong phase and stale drain acknowledgments are
rejected. Mode writes are frozen during a transition. Read and write responses
stay stable under AXI backpressure; address and data can arrive in either order.

Before resetting active clients, the sequencer requires compute idle, the
calibration hold acknowledgment and a new drain acknowledgment. The external
barrier must stop new host transactions and new workload launches while allowing
accepted bursts, responses and an already-running program to finish. It must
account for every channel and drop its acknowledgment when the request drops.
This barrier and its CDC logic have not been implemented by the component.

Compute-only changes preserve DDR and require relock before activation. A DDR
change requires configuration, lock/PHY readiness, mode-specific firmware setup,
both calibrated channels, memory initialization, model reload and a final drain.
`INIT_DONE` and `MODEL_DONE` attest to checks performed by matching host tools;
the RTL does not verify memory or model contents. Firmware/model preparation
phases intentionally have no short automatic timeout. Automatic operations and
calibration have separate configurable timeouts in always-on clock cycles.

Reset requests are registered. A drain timeout blocks new traffic without
resetting transactions still in flight. Fault status remains readable, and
recovery requires a saved safe checkpoint or verified drain. Clock failure
during maintenance prevents workload release. These behaviors passed the
21-case component testbench; actual drain logic, MMCM transactions, asynchronous
crossings, target reset synchronizers and complete-image behavior remain open.

### Remaining integration

An ordered AXI admission/drain component also passed 22 cases:
`rtl/boards/ypcb-00338/otpu_axi_ordered_drain.sv`, checked by
`tools/check_spare_axi_drain.py`. It retains all payload/sideband fields, finishes
presented stalled addresses and their bursts, tracks ordered IDs/lengths and
responses, and requests a fresh downstream-tail acknowledgment. Keep its separate
`admission_enable` low throughout reclock/reset, even after the drain request
falls. Protocol errors and late work prevent qualification.

This component requires the selected per-master ordered response contract and
reviewed handshake CDC/reset integration. The exact production FIFO body is
used; only its existing FPGA declaration-initialization lint style warning is
scoped off in that module. Other guard warnings remain fatal. It does not
establish native/adapter/controller/BIST or PHY drain. B/n_wdone counters follow
native command acceptance; a raw write can remain pending after that interface
completion. Source audit:
`build/checks/runtime-native-tail-source-audit-20261018.json`.
The actual full-board tail and runtime-image qualification remain pending.

The held drain join requests core/host source proofs before probing memory.
Its protocol model passed 22 cases at all four clock combinations. The connected
production bridge/adapter/raw-accounting model passed seven cases, including
posted writes and compute/host held in reset. Functional source resets must not
reset the participants. The selected observer preserves coherent empty-source
proof through reset release; an unsolicited reset still invalidates model state.
The guarded clock manager passed 21 controller/engine cases and waits for actual
release/reset proof before configuration, retaining AXI ownership on proof loss.
These component models do not qualify full board timing/CDC or physical
transitions. Registry: `build/handoffs/runtime-held-drain-current-20261018.json`.

The controller and configuration engine are now wired together in
`rtl/boards/ypcb-00338/otpu_runtime_clock_manager.sv`. The parent FAULT state and
fabric abort drive the engine's transaction-boundary cancellation input; its
idle/done/error responses feed the sequencer. The manager's endpoint reset
flushes only the host register interface, preserving an accepted transition.

Lint and 13 connected-component cases passed in
`build/checks/runtime-clock-manager-connected-20261018-v1/`: all four modes,
repeated compute-only changes, endpoint reset during an owned write, abort and
timeout during partial AXI writes, readback failure propagation, stale-lock
timeout, upload abort/drain, flushed-command suppression and abort during the
second clock's write. The test uses both actual RTL components. Clock-IP,
calibration and native-drain boundaries remain behavioral models; this does not
qualify vendor-IP integration, DDR behavior or the complete board image.

```bash
python3 tools/check_spare_runtime_clock_manager.py \
  --out build/checks/runtime-clock-manager-new
```

The separate configuration engine now exists in
`rtl/boards/ypcb-00338/otpu_runtime_clock_config.sv`. Lint and 13 protocol cases
passed in `build/checks/runtime-clock-configuration-component-20261018-v2/`.
It writes and verifies all 23 setting words, checks initial lock, triggers
reconfiguration, observes a new lock-low/lock-high sequence and checks LOAD
clearing. Compute-only requests leave the memory IP untouched. AXI errors or
readback mismatches stop the sequence. Cancellation waits for an issued AXI
transaction to finish; the parent owns its deadline and drives cancellation on
fault. These are component tests with an AXI model, not vendor-IP integration.

The register fields and trigger follow the generated IP and
[AMD's register map](https://docs.amd.com/r/en-US/pg065-clk-wiz/Register-Space).
For the 50 MHz input, M16/D1 gives an 800 MHz VCO. The compute dividers are 8
and 5.375, the latter encoded as integer 5 plus thousandths 375. Memory uses
dividers 8 and 6. The generated wrapper derives fractional-enable from the
fractional field; returning to an integer divider must clear it too.

The actual-IP test passed under
`opentpu-runtime-clock-ip-model-v4-20261018.service`. Source/launch:
`build/checks/runtime-clock-ip-actual-20261018-v4-launch/`; receipt:
`build/checks/runtime-clock-ip-actual-20261018-v4/manifest.json`.
It compiled the real AXI/VHDL/DRP/UNISIM code and passed four reconfigurations
and ten output-period checks, including fractional enable and integer return.

The connected manager also passed against the actual vendor IP:
`build/checks/runtime-clock-manager-actual-ip-20261018-v1/manifest.json`.
All four compute/memory mode combinations activated with correct epochs and ten
period checks (10 ns, 6.718750 ns and 7.5 ns). Its actual configuration engine
wrote/verified the settings and waited for fresh unlock/relock. Compute-only
changes preserved memory clock/reset. Native drain, calibration and PHY readiness
remain behavioral boundaries; DDR write-clock MMCMs, full-board integration and
physical/inference transitions are not qualified by these tests.

The new checker binds 12 `.vh` dependencies omitted from the old clock-IP
manifest. Future `prepare_spare_runtime_clocks.py` inventories include them.
The original preparation and tool are preserved. The first test attempt failed
before elaboration because XSim requires `--mt off` for serial execution. The
second wrapper timed out; both recorded native process identities subsequently
disappeared and no usable snapshot existed. Those failures are preserved.
The later v3 bench had an isolated XSim elaboration problem: dynamic clock-index
events inside an automatic task reproduced the stall/sensitivity warnings even
with vendor IP removed. Explicit static clock edges elaborated in 2.82 seconds
with the same transitions/samples/tolerances. The obsolete workers were stopped
only after that comparison; their original evidence and diff are preserved.
v4 then passed with the actual IP. This was a test-tool correction, not a failed
FPGA implementation or a relaxation of numerical checks.

The current controller separates `bus_reset` from its configuration-time `rst`.
Assert `bus_reset` coherently with the AXI master to flush incomplete AW/W and
responses while preserving a latched mode and accepted clock transition. Pulse
`fabric_abort` when the data path cancels accepted traffic: it faults the
activation, invalidates model status and prevents a new configuration request.
An already-owned configuration engine must finish or cancel at an AXI boundary
before recovery. The parent must connect its FAULT state to engine cancellation.

The correction also rejects a stale high drain acknowledgment during recovery.
Entering maintenance invalidates an older reset checkpoint, so a calibration
fault cannot bypass a fresh drain and hold acknowledgment. Nine additional
cases passed, alongside the prior twelve. Component disposition:
`build/checks/runtime-control-reset-integration-disposition-20261018.json`.
The original finding remains preserved. Actual reset/abort sources, CDC and
both-interface integration are still required. This runtime component change
does not alter c0182800.

AMD supports MMCM frequency changes through the dynamic reconfiguration port;
the reset/reconfiguration/lock sequence must be implemented explicitly.
[AMD XAPP888](https://docs.amd.com/v/u/en-US/xapp888_7Series_DynamicRecon).

The controller must remain reachable from an independent board clock while the
compute or memory clocks stop. The fixed-clock images' JTAG mailbox runs on the
compute clock. The new frontend/controller component is checked on an always-on
50 MHz clock; the complete runtime top still needs that domain and the third
independent control destination, including PCIe access. Retain the prepared reset
correction; the rejected decoded-reset design is not a suitable base.

Before a DDR change, stop compute, reject new memory work and drain accepted
transactions. Hold the affected logic in reset, change and verify the clocks,
then reinitialize DRAM with the selected CL/CWL and PHY phases. Calibrate the
eight-lane CH0 and nine-lane CH1 with their matching frequency settings, fully
initialize memory/ECC and reload the model. Keep normal memory traffic blocked
until every required step succeeds. An error must remain visible without
silently releasing memory clients.

Remaining preparation includes complete core/top and both-host routing,
native/controller/BIST tail and reset/CDC integration, mode-specific firmware,
transition models, actual-rate reporting, timing/CDC constraints and review for
every allowed mode. A failed or stalled transition must leave the control path
usable. Synthesis, routing, exact image review, SRAM execution and reference
inference then remain separate gates. Permanent flash writes need exact-image
approval under `AGENTS.md`.

## Connected runtime top source, October 18

The complete source-only `c0184800` top is now connected in the preparation
selected by `build/handoffs/runtime-full-top-preparation-current-20261018.json`.
It structurally elaborates against all 313 actual BD ports, with exact-header
black boxes for vendor/memory bodies. Actual identity/rate RTL passed 23 cases;
actual native CSR/capability/loader bindings passed nine cases. Corrected
registered AON reset and per-domain participant reset release passed nine
byte-exact top-prefix cases. The full accelerator and both runtime interfaces
remain present. This is not an admitted implementation or a qualified runtime
image: connected races/transitions, all-mode timing/CDC, the AON host workflow,
implementation and physical transitions remain required.

The current full-top v6 additionally flushes control coherently on either
compute or memory lock edges. Unexpected compute unlock faults activation;
managed unlock preserves the in-flight configuration engine. Eleven exact
reset-prefix cases passed. Actual board control, held drain and generated
Clocking Wizard IP passed all four modes and ten period checks, including
stalled control/host/native boundaries and the exact top control-flush logic.
A modeled unexpected compute unlock left the AON fault register reachable and
DDR reset low. Full both-host/native traffic, PHY/calibration, timing/CDC and
physical-transition qualification remain separate gates.

## Prepared AON host protocol and mode data

The source in `opentpu/host/runtime_clock.py` passed 27 host protocol cases.
It verifies live AON identity, serializes mutations, uses the matching held
mode firmware, requires complete both-channel initialization, reads back the
whole logical model image and checks fresh rates/ECC before MODEL_DONE.
Compute-only changes preserve verified resident DDR and validate the completed
activation epoch. The model backend restores IMEM, arguments and its verified
memory-init marker. The controller opens no device.

`tools/prepare_spare_runtime_host.py` exports small mode data bound to the
actual DDR800/1066 RV32 CPU receipts and exact active memory CSR/PHY profiles.
Its source-only metadata cannot authorize hardware opening. Transport and
compiled-model runner components are prepared; actual reviewed-image packaging,
all-mode constraints and connected traffic/physical qualification remain required.

## Runtime transport/profile contract

`opentpu/host/runtime_transport.py` provides the source components for JTAG,
Chestnut and XDMA. Before opening a device, both full and small package forms
must bind the exact bitstream/source digests, both interfaces, all four clock
modes, full spare-lane memory profile and complete artifact/CDC/all-mode/source
review gates. Small Mac exports keep the same review binding without a `.bit`.
Source-only mode data cannot open a transport.

The runtime JTAG subclass permits AON access; the Chestnut subclass probes the
AON identity when the core bank is reset. Existing Chestnut default probing is
unchanged. Constructors defer memory/calibration CSR access until an allowed
phase. DDR operations check AON state/locks, full channel range and clean ECC;
early core requests leave AON usable. Device ownership survives Board wrapper
cleanup until final transport close. Eleven actual host source hashes prevent
using an older inherited transport with newer adapters.

The runtime/profile plus existing transport suite passed 73 modeled checks.
It does not provide a real qualified runtime package: actual final-review
packaging, connected traffic, all-mode timing/CDC and physical transitions
remain pending.

Reproduce the host-mode preparation after the named protocol and transport
checks pass, using a fresh output directory:

```bash
"${SPARE_PYTHON:-python3}" -B tools/prepare_spare_runtime_host.py \
  --firmware-proof build/checks/runtime-mode-firmware-20261018-v2/manifest.json \
  --top-preparation build/fedora-vivado/spare-runtime-full-top-20261018-v7 \
  --host-proof build/checks/runtime-aon-host-protocol-20261018-v3/manifest.json \
  --transport-proof build/checks/runtime-aon-transports-20261018-v6/manifest.json \
  --model-proof build/checks/runtime-model-backend-20261018-v4/manifest.json \
  --out build/handoffs/runtime-host-mode-data-new
```

This prepares data and source bindings only. It opens no device and does not
create the reviewed runtime package required by `open_runtime_transport`.

## Compiled-model runner

`tools/run_spare_runtime_model.py` prepares a real checkpoint's int8 image and
ISA reference before opening a device. Offline preparation requires the bound
source mode data. `--execute` additionally requires an actual reviewed runtime
package; source-only preparations are rejected before transport opening. The
runner never programs SRAM or configuration flash.

`RuntimeBoardBackend` calibrates, initializes both channels, uploads and fully
reads back the initial image before attaching the Engine. Each program is read
back before LOAD. A compute-only change preserves DDR and Engine context while
rebuilding the Board wrapper and IMEM/argument caches. A DDR change reloads the
original verified image and restarts context and prompt. Device ownership stays
with the transport across wrapper changes. Model/program mismatches save
bounded failing data and withhold execution; cleanup failures produce a failed
receipt and a nonzero exit. Active expert-offload sessions are not supported by
this dense-model transition runner.

The backend/protocol/CLI suite passed 47 modeled cases. The actual padded
TinyStories checkpoint passed an offline four-segment ISA reference for modes
`0,1,3,2`: eight tokens per segment, with positions `13,21,13,21`. The initial
28,909,056-byte image has the same SHA256 as the earlier physical fixed-clock
test. The ISA backend allocates 32 MiB for this tested image/program footprint;
the compiler retains the full hardware arithmetic/layout configuration. This
does not test physical memory capacity or clock transitions, and continuation
contexts do not establish a matched performance comparison.

Reproduce offline with a local padded checkpoint and fresh output directory:

```bash
"${SPARE_PYTHON:-python3}" -B tools/run_spare_runtime_model.py \
  --model "$SPARE_MODEL" \
  --source-data build/handoffs/runtime-host-mode-data-20261018-v11 \
  --prompt-ids 1,9038,2501,263,931 --modes 0,1,3,2 \
  --tokens-per-mode 8 --cap 128 --out build/runtime-model-reference-new
```

Actual runtime-image review, connected traffic, all-mode timing/CDC and physical
inference across transitions remain required. Preserve the permanently flashed
c0182800 for the selected Mac LFM test.

## PCIe control target abort

The source-only v6 top reset the PCIe control admission guard whenever the
downstream control fabric reset. The XDMA source remained live. Two RTL
reproductions demonstrated that this discarded an accepted AON read or a
buffered response under source backpressure. That preparation is ineligible
for implementation admission; its sources and finding remain preserved.

Full-top v7 uses `otpu_runtime_axil_guard_control_abort`. The guard's source
reset follows the PCIe source reset, while an independent `target_abort`
follows the control-fabric reset. It preserves buffered responses, returns
SLVERR for canceled issued requests and retains partial AW/W ownership until
both halves can receive one error response. It does not replay canceled
payloads after the target restarts. The downstream fabric/endpoints must
flush coherently with `target_abort`.

The new guard passed strict lint and 28 RTL cases, including partial writes,
independent reads/writes, repeated aborts and stopped-source restart. The v7
top passed structural elaboration, 11 exact reset-prefix cases and the actual
vendor-clock four-mode/ten-period model. Fresh host-mode data and the compiled
TinyStories ISA reference bind v7. Complete connected both-host/native traffic,
transport handling of aborted control operations, all-mode timing/CDC and
physical transitions remain unqualified. No runtime build has been admitted.

## Runtime JTAG control-abort responses

The fixed-image JTAG transport retains its existing fail-closed behavior. Its
new `JtagCommandError` subtype records opcode, address and status only after a
fresh matching mailbox response completes. The runtime adapter distinguishes
that completed error from a timeout, corrupt response or broken link.

For the runtime image, only AON reads interrupted with coherent-abort status
`0x80` retry, at most eight attempts. Writes and data operations never retry.
Any other completed command error disables further mutations and data access
while retaining read-only AON diagnosis. Ambiguous timeouts still poison the
link and require diagnosis/reconnection. The model-run manifest records the
number of interrupted AON reads.

The 73-case transport suite includes an applied START whose response aborts:
the SDK sends START once, blocks subsequent mutations and can inspect the
resulting maintenance state. The 47-case model/backend suite and the actual
TinyStories ISA reference also pass with the updated source binding. These
are modeled host results; connected PCIe/Chestnut error handling and full
both-host/native traffic remain separate pending gates.

For Chestnut, `PcieCompletionError` preserves the bridge status and PCIe
completion status as separate fields. A completed target error blocks all
further writes/data operations while permitting AON diagnosis. Uncertain USB,
bridge or reserved completion results require reconnection before further
register access. No PCIe reads or posted writes are retried. The suite uses
the actual packet encoder/reply decoder with modeled USB replies; it does not
establish how the selected XDMA IP maps a target AXI error to a completion.

An isolated simulation preparation uses the runtime BD's exact XDMA 4.2
revision 4 configuration: Gen2 x8, 128-bit AXI at 250 MHz and AXI-Lite enabled.
It recreates the user overrides in a fresh project and requires every resolved
component parameter to match. The original BD is not opened for writing. Example generation
is separate from simulation, completion-error mapping, full-system review and
physical qualification.

The exact exported vendor endpoint and Root Port model subsequently compiled
and elaborated. Simulation did not start: the installed simulator reported a
BASIC limit of 50,000 instances, while this model contains 467,267. No target
error-to-completion mapping was observed. This is a simulator prerequisite for
the future runtime-clock design; the flashed c0182800 Mac workflow does not use
this simulator. The full compiled snapshot and hashes are preserved in
`build/handoffs/runtime-xdma-licensed-resume-inputs-20261018.json` for reuse in a
fresh output directory with suitable simulator capacity.

An independent synthesis-level rate-counter check passed four clock-mode
views, 64 scalar Gray paths per view, with saved max-delay and bus-skew bounds.
The report reader reconciled both CDC Warning rows in every view with their
summary and all endpoint bindings. This component proof does not qualify
full-top clocks, reset crossings or routed timing. Current receipts are
`build/checks/runtime-rate-gray-constraints-20261018-v2/manifest.json` and
`build/checks/runtime-rate-gray-cdc-review-20261018-v2/manifest.json`.

The clock-view sidecar in
`boards/ypcb-00338/constraints/otpu_runtime_clocks.tcl` preserves generated-clock
ancestry and selects all four static analysis modes. Its fast compute analysis
period is 6.718 ns, conservatively below the physical 6.71875 ns target; it does
not reconfigure hardware. The companion check retains actual generated runtime
MMCM bodies, both exact DDR write-clock MMCM instances and the AON rate RTL.
It checked 16 outputs per mode, including the DDR quadrature outputs, and all
256 Gray paths across four views. The saved clock/Gray constraints and complete
CDC inventories were independently reconciled. Receipts:
`build/checks/runtime-clock-static-views-20261018-v2/manifest.json` and
`build/checks/runtime-clock-static-view-review-20261018-v1/manifest.json`.

The first clock-definition attempt was rejected for Critical override messages.
The correction reused its successful synthesis checkpoint and explicitly
dispositions the bounded messages from renaming and updating the same output
clock object. No Critical warning was accepted. This is still a clock-leaf
component check: the complete native accelerator, AXI/DRP behavior, full-top
reset/CDC integration, routed timing and physical transitions remain required.

## Full runtime project source assembly

`tools/prepare_spare_runtime_project.py` assembles the actual full vendor
project from the selected top, runtime memory, AON BD and generated clock IP.
The completed project selects `otpu_fpga_top_runtime`, retains the full native
accelerator, both hosts, 4 GiB spare-lane memory and ROM, and includes the
clock/Gray constraint sidecars. All 962 XDMA component parameters and all 42
clock HDL dependencies match the selected references. The complete 313-port
wrapper matches after removing only its export-timestamp comment.

The first strict project attempt caught a Critical warning previously missed
by the BD checker: the Master interface inherits a read-only ID width. The
corrected generator configures the Slave return and verifies both interfaces
after validation (ID 4, data 128, address 64, 250 MHz). The fresh BD check rejects
ERROR/Critical messages even on native exit zero. Both original receipts remain
preserved. No FPGA implementation was rejected by this source-tool finding.

The selected v4 project passed 41 source/configuration checks, including actual
run hooks and their refusal of unadmitted work. The inherited fixed-top native
and mailbox constraints are preserved but disabled. Corrected runtime sources
are included; complete netlist/reset/CDC bindings, the synthesis clock envelope,
connected traffic, all-mode routed timing and final packaging still precede
an admitted implementation. The assembled project has not run synthesis or
implementation.

Reproduce the source preparation in a fresh directory:

```bash
python3 tools/prepare_spare_runtime_project.py \
  --top-preparation build/fedora-vivado/spare-runtime-full-top-20261018-v7 \
  --clock-preparation build/fedora-vivado/spare-runtime-clock-ip-20261017 \
  --bd-preparation build/fedora-vivado/spare-runtime-aon-bd-20261018-v2 \
  --bd-review build/checks/runtime-aon-bd-vendor-20261018-v2/manifest.json \
  --clock-review build/checks/runtime-clock-static-view-review-20261018-v1/manifest.json \
  --native-constraints-preparation build/fedora-vivado/spare-runtime-native-constraints-20261018-v2 \
  --mailbox-constraints-check build/checks/runtime-mailbox-aon-constraints-20261018-v1/manifest.json \
  --mailbox-constraints-review build/checks/runtime-mailbox-aon-cdc-review-20261018-v1/manifest.json \
  --synthesis-clock-review build/checks/runtime-synthesis-envelope-review-20261018-v1/manifest.json \
  --out build/vivado/runtime-project-new
```

Current receipts:
`build/fedora-vivado/spare-runtime-project-20261018-v4/manifest.json`,
`build/checks/runtime-project-source-audit-20261018-v4/manifest.json` and
`build/checks/runtime-aon-bd-vendor-20261018-v2/manifest.json`.

The mailbox source/component proof accounts for 604 request bits and 536
response bits, using two actual receiver cycles as the held-data bound: 40 ns
for AON and 333.332 ns for the conservative 6 MHz JTAG view. All six internal
paths of the four synchronizer chains remain timed. The reader reconciles all
1,142 Warning rows with the native facts and saved bounds, including scoped
multiline pin-list aliases. This conditional source disposition retains the
one-outstanding-command protocol and still requires full-top/routed proof.

The native source preparation replaces the old CSR-clock assumption with AON
and narrows the memory-domain reset exception to the first D of the actual
eight-stage reset pipeline. The old broad exception would cut CSR return data
once those registers also run on AON. The remaining reset stages stay timed;
existing memory/bridge constraints are preserved. The inherited global TIMING-9
waiver is not imported. Actual full-netlist selectors and numerical bounds
remain unqualified until the complete synthesis/routed review.

## Verified synthesis clock envelope

`otpu_runtime_synthesis.xdc` defines the fastest analysis periods at the actual
clock-IP boundaries while retaining the IP's existing clock names. The full
project registers it for synthesis and excludes it from implementation. The
actual-IP component test observed compute 6.718 ns and memory 7.5 ns during
synthesis constraint loading. A copied linked timing view excluded those
definitions, restored unchanged boot parameters (multiplier 16, dividers 8/6)
and accepted the separate fastest implementation mode. Hardware configuration
values were not changed by the timing definitions.

The check preserves failed attempts and reuses the completed component
synthesis. Post-checkpoint hooks already see the filtered timing view, so they
cannot observe synthesis-only clocks; the observation occurs during constraint
loading. `init_design` is not a supported `launch_runs` stopping point in this
installed tool. The final reader opens a fresh copied linked view without
launching an implementation run. No placement, routing or full native synthesis
was performed. Receipt:
`build/checks/runtime-synthesis-envelope-review-20261018-v1/manifest.json`.

The source inventory in
`build/fedora-vivado/spare-runtime-control-cdc-contract-20261018-v2/` enumerates
all annotated runtime-owned control registers: 12 actual instances, 54 members
and 256 pre-optimization bits. It records separate ownership for existing
bridge, generated-memory and vendor crossings. Actual surviving netlist
endpoints, equivalence merges, constant removal and full CDC contracts still
need matching; this source inventory creates no waivers or routed qualification.

## Complete-design source-synthesis validation

The full runtime project now has an admitted synthesis-only validation job,
separate from full image implementation. A frozen private copy retains the
native accelerator, 4 GiB memory, exact clock IPs and JTAG/PCIe interfaces.
The persistent worker waits behind the original admitted implementation queue
and requires its exact service/children to release ownership, plus 11 GiB
available memory. Its admission passed 16 ownership/integrity cases and an
actual Vivado open-project check of relocation and both original run guards.

Only the private synthesis hook is replaced after admission. The implementation
hook continues to refuse execution. The job preserves the synthesis checkpoint
before opening a linked timing view for register, reset, clock and CDC evidence.
Any selector or reader finding needs explicit disposition using that checkpoint;
source synthesis and collection do not establish complete CDC coverage, routed
timing or physical transitions. The job creates no bitstream and accesses no
hardware. Full runtime implementation remains unadmitted.

The reproducible helper is `tools/prepare_spare_runtime_netlist_validation.py`.
The selected launch/receipt and current owner are recorded in
`build/handoffs/runtime-netlist-validation-progress-20261018.json`.

## Connected full-top control check

The selected complete top passed eight connected read/abort cases using all
42 native/runtime RTL files unchanged. The real USER2 mailbox/serialization,
PCIe guard, top reset wiring and AON identity are connected. Independent source
binding checks match the audited full project and all 313 vendor boundary ports.
The tests cover both host frontends, a buffered PCIe response surviving a
lock-edge control flush, errors for interrupted accepted reads, exact USER2
abort sequence ownership and subsequent identity reads on both paths.

The BD read routing/arbitration, generated memory and clock-IP bodies are
explicit behavioral boundaries. Native transactions, writes, real vendor
completion mapping, mode activation, actual clock reconfiguration and physical
behavior are not qualified by this check. Full both-host/native traffic remains
an admission prerequisite. Reproduce the scoped check with
`tools/check_spare_runtime_top_control.py`; its selected result and independent
disposition are in `build/handoffs/runtime-connected-control-work-20261018.json`.

## Early DDR write-clock VCO check

`tools/check_spare_memory_clock_limits.py` checks the exact generated DDR
write-clock MMCM settings against the core profile and the XC7K480T-2 VCO
range reported by Vivado AVAL-46: 600–1440 MHz. The source reader inventories
both instances, accepts bounded numeric literals only, and rejects inconsistent
period/profile or primitive/input bindings. The high-rate source preparer now
checks before and after generation, so an inherited 1600 MHz VCO plan is
rejected before another full core or implementation is started.

This gate passed sixteen regression cases, four saved-core controls and the
ordinary preparer's valid and invalid paths. A complete valid source generation
retained exact firmware bytes and CSR rows; its Verilog code matched after
excluding generated revision/date/hierarchy comments. Raw hashes and the
preserved metadata-audit correction remain recorded in
`build/handoffs/ddr-mmcm-vco-progress-20261018.json`.

The ordinary and mixed-startup full-image source preparers also run this gate,
and freeze its checker beside their worker. Worker preflight rechecks the exact
core and stored gate binding, including previously prepared inputs. Two isolated
source-validation fixtures passed normal preparation and frozen-worker checks
from an unrelated working directory; invalid source was rejected before source
preparation or implementation. No validation fixture was admitted to Vivado.

This is source VCO validation. Actual input clocks, other primitive limits,
DRP behavior, all numerical timing/CDC and electrical DDR checks remain
mandatory. Changing the clock plan requires a fresh image identity and its
matching calibration/review evidence. Existing frozen jobs are unchanged.


## Registered-admission source successor

The current source correction is `c0184801`. It registers always-on permission
signals before crossing to PCIe, host, compute and memory clocks. The complete
native integration model retains both runtime host interfaces and the full
accelerator; its vendor, memory and clock boundary bodies remain modeled.
A source preparation or offline ISA result does not authorize hardware access.

Use matching `c0184801` runtime profile, host metadata and model runner sources.
The host rejects retired runtime identities and requires the exact artifact,
CDC, mode and source review receipts before opening a transport. Both DDR mode
firmware/configuration sets remain image-bound; model and program readback stay
mandatory. The source-data export alone cannot satisfy the reviewed package
contract. Follow `HANDOFF.md` for the current build, review and physical status.
