# DLC10 USB disconnect investigation, 2026-10-12

Latest observation: **2026-10-14 14:15 HKT**. The native Vivado driver also
lost USB during warm DDR800 calibration. The last request at 13:29:45.709 HKT
was a CSR write to `0x16018`, channel 0's DFII phase-0 write-data register
(second 32-bit word). Linux recorded a disconnect at 13:29:45, a brief return
as `03fd:0008` at 13:29:46, then another disconnect at 13:29:50. Calibration
did not finish; no compute/model test ran in that attempt.

[Transaction/kernel receipt](../build/fedora-vivado/dlc10-warm-calibration-drop-20261014T061453Z/manifest.json)
preserves the last 64 requests and subsequent USB events. USB address setup
also failed with `-71` on port `1-2` at 13:31:52; at 13:49:52 the adapter
briefly appeared there as `03fd:0013` and disconnected immediately. No Xilinx
adapter was present in the 14:11 HKT scan. These observations identify the
operation interrupted and show later enumeration failures, including after
the controller exited. They do not establish that a particular FPGA test
caused the disconnect. Both native Vivado and the corrected loader have now
exhibited this problem.

The adapter repeatedly disappears from Linux USB enumeration. A secure connector
does not establish that the USB controller, adapter firmware, signal quality or
USB supply is stable. The current evidence does not identify a board fault or
insufficient 12 V input power. A driver compatibility fix has been built and
tested in software; physical stability is still unverified.

## Local evidence

The recorded kernel events separate deliberate firmware re-enumeration from
unexpected disconnects:

| HKT | Event | Interpretation |
| --- | --- | --- |
| Oct 11 13:56–13:57 | `03fd:0013` boot upload, then `03fd:0008` re-enumeration | Expected initialization; do not count this as a spontaneous failure. |
| Oct 11 13:56–13:58 | Repeated `selecting invalid altsetting 1` | The loader requests an alternate USB setting absent from this firmware. |
| Oct 11 14:48:03 | Device 035 disconnect; descriptor reads fail with `-110` | Interrupted the normal OpenTPU selftest during vector operations. |
| Oct 12 00:19:58 | Device 046 enumerates as `03fd:0013`, without string descriptors | Adapter becomes visible again. |
| Oct 12 00:20:47 | Device 046 disconnect; subsequent setup/descriptor requests fail with `-71` | Occurred before any JTAG client was started in this turn. |

The Linux [USB error-code documentation](https://docs.kernel.org/driver-api/usb/error-codes.html)
defines `-110` as a transfer timeout and `-71` as a protocol/no-response error.
The latter can indicate device/firmware or cable faults; the controller often
cannot distinguish them. These codes do not prove a loose connector, an FPGA
fault, a bench-supply fault or a Fedora kernel regression.

At capture time Fedora ran `7.2.9-200.fc44.x86_64`, libusb `1.0.30-1.fc44`,
and tuned's `throughput-performance` profile. TLP was absent and usbguard was
inactive. Existing Xilinx udev rules grant device access without automatically
loading firmware. No competing cable client was found. The subsequent ten-minute
hardware watcher expired without accessing hardware at 00:42:05 HKT.

A subsequent thirty-minute watcher using the corrected XVC manifest also
expired at 01:48:09 HKT with actual exit 2 and no hardware accessed. No adapter
enumerated, and no programmer or XVC client started. The corrected driver is
therefore still untested physically. Terminal receipt:
`../build/fedora-vivado/mig-jtag-controller-20261010T235833Z/physical-usb-fixed-watch-20261011T171809Z/process-exit.json`.

Snapshot: `../build/fedora-vivado/dlc10-usb-diagnosis-20261011T165052Z/`.
Its kernel log, USB topology, privilege check, rule validation and PM attributes
are saved with hashes. An initial broad process search also matched compiler
commands; `cable-owners.json` records the separate exact process-name check.

## Similar software reports and the local correction

The [YPCB DLC10 alternate-setting patch](https://raw.githubusercontent.com/FeSens/inspur-adventures/main/patches/openfpgaloader-xpcu-skip-missing-alt.patch)
reports firmware exposing interface 0 with only alternate setting 0. It inspects
the descriptor before selecting alternate setting 1. Our old loader requested
setting 1 unconditionally, matching Fedora's warning. Linux tolerated the missing
setting sufficiently to complete earlier memory and kernel tests, so removing
the invalid request is a compatibility correction, not a proven disconnect cure.

An [upstream DLC10 report](https://github.com/trabucayre/openFPGALoader/pull/730)
also describes firmware/PID detection timeouts. Its author tested macOS; the
maintainer warns that skipping firmware solely because PID is `0013` breaks
other DLC10 variants. That blanket change was not applied. The working staged
boot/overlay firmware remains unchanged.

The isolated corrected driver is:

```text
build/fedora-openxc7/xpcu-xvc-20261011T165026Z/manifest.json
build/fedora-openxc7/xpcu-xvc-20261011T165026Z/binary/openFPGALoader
SHA256 b87703a39c2fa068aacd15d22f15d6d83a868f47c84ba1523d713022b2d57def
```

Compilation used eight workers and exited 0. Both tests exited 0: the existing
mixed TMS/TDI encoder/decoder test, and a new test exercising the actual FX2
driver against libusb responses. The latter verifies that an absent setting is
skipped, an advertised setting is selected, and descriptor/transfer failures
preserve the driver's failure/fallback behavior. No cable was opened by these
tests. The old donor checkout, old binary, firmware, qualified FPGA image and
`xvc-ready.json` selection were preserved.

Rebuild in a fresh directory:

```bash
# Run from the root of your OpenTPU checkout.
python3 tools/fedora_prepare_xvc.py --jobs 8 --no-select \
  --usb-altsetting-patch ${YPCB_ROOT}/ref/inspur-adventures/patches/openfpgaloader-xpcu-skip-missing-alt.patch
```

For a controlled test, `tools/fedora_xvc_server.py --manifest PATH` accepts the
new manifest. Its initializer still uses the historical loader, so an old
alternate-setting warning can still appear during initialization. Only the
subsequent XVC session uses the corrected binary. Do not edit the frozen
programmer's hash-guarded inputs to hide this distinction.

## Scoped power-management experiment

The kernel's global autosuspend delay is 2 seconds. This does **not** prove the
DLC10 was autosuspended: its per-device `power/control` was unavailable after
disconnection, and non-hub devices normally default to `on`. The USB root hub
currently permits runtime suspend. An open usbfs handle normally prevents the
adapter being considered idle. See the kernel's
[USB power-management documentation](https://docs.kernel.org/driver-api/usb/power-management.html).

To rule out device autosuspend when it next enumerates, a narrowly matched rule
is prepared and passed `udevadm verify`. It has **not** been installed: unattended
sudo on this host requires a password. Run:

```bash
sudo install -m 0644 ${OTPU_ROOT}/tools/99-ypcb-dlc10-no-autosuspend.rules /etc/udev/rules.d/99-ypcb-dlc10-no-autosuspend.rules
sudo udevadm control --reload-rules
```

Then reconnect the adapter. The rule applies to both its `0013` and `0008` states
and writes only the device's `power/control=on`. Verify the actual setting:

```bash
for device in /sys/bus/usb/devices/*; do
  if test -f "$device/idVendor" && test "$(cat "$device/idVendor")" = 03fd; then
    printf '%s: ' "$device"
    cat "$device/idProduct" "$device/power/control" "$device/power/runtime_status"
  fi
done
```

Rollback removes only this new rule, reloads udev rules, then reconnects:

```bash
sudo rm /etc/udev/rules.d/99-ypcb-dlc10-no-autosuspend.rules
sudo udevadm control --reload-rules
```

This rule cannot repair USB enumeration errors or force a vanished adapter to
return. Do not reset/unbind the whole xHCI controller or alter unrelated USB
devices to work around this failure.

## Next physical comparison

1. Use a different physical USB port, preferably on the other root controller,
   while keeping the board's power settings unchanged. Observe idle USB before
   starting JTAG. The previous topology had no external hub.
2. With exactly one stable adapter, compare native Vivado's read-only chain scan
   with the corrected XVC session, one cable owner at a time. This distinguishes
   application-specific failures from disconnects present with either driver.
3. If it still disappears while idle, compare the same adapter on another host
   or a self-powered USB 2 hub. AMD's
   [DLC10 DS593](https://docs.amd.com/api/khub/documents/TI9ts12CeuAeBtQpR7HWBw/content)
   identifies the cable as USB bus powered and specifies sufficient USB power
   for high-speed enumeration. That supports a controlled USB-path experiment;
   it does not establish a power fault on this host.
4. Resume the qualified Vivado image and the complete normal model selftest
   once USB is stable. Historical full 4 GiB/ECC and two kernel passes remain
   valid evidence; vector/stream/model completion is pending.

The prepared controller supports explicit selection without replacing the old
pointer:

```bash
python3 tools/fedora_finish_vivado_jtag.py --wait-usb 600 \
  --xvc-manifest build/fedora-openxc7/xpcu-xvc-20261011T165026Z/manifest.json \
  --out build/fedora-vivado/physical-usb-fixed-NEW_TIMESTAMP
```

Choose a new receipt path and confirm no existing cable client or watcher is
running. This invokes the existing guarded volatile-SRAM programmer and retains
full selftest and exact physical LFM2/ISA token-comparison requirements. Flash
is not written.


The 04:13 HKT continuation confirms the former DLC10 host port is enabled
(`disable=0`), currently active, and reports `over_current_count=0`; its root hub
is active and authorized with authorized_default=1. No Xilinx device is present.
This excludes a currently disabled/suspended/overcurrent-disabled host port
in the inspected state; it does not identify the earlier disconnect cause or
prove cable, firmware, USB supply, FPGA supply or board health under traffic.
No sysfs settings, firmware or USB controller were changed. Live receipt:
`../build/fedora-openxc7/usb-port-live-20261011T201303Z.json`.
The corrected driver remains physically untested pending enumeration.

## October 14 physical comparison

The corrected XVC driver successfully loaded/accessed the real FPGA. After
a same-image retraining recovery and full memory passes, its selftest was
interrupted at **12:32:36 HKT** by Linux reporting Device 083 disconnected,
then Device 084 enumerating immediately as `03fd:0008`. XVC reported
`LIBUSB_ERROR_NO_DEVICE`; no USB initialization command was running then.
[Physical session](../build/fedora-vivado/mig-readback-retrain-20261014T042940Z/manifest.json).
The corrected driver therefore does not eliminate all physical disconnects.

Device 084 currently reports `power/control=on`, runtime status `active` and
zero accumulated suspended time. That measurement is for the replacement
node and does not establish Device 083's pre-disconnect runtime state.

A [native Vivado chain/mailbox scan](../build/fedora-vivado/native-jtag-driver-probe-20261014T043611Z/manifest.json)
passed without programming. A subsequent native-driver memory test failed
with channel 0 DDR data/ECC errors while USB remained present; it is too
short to qualify long USB stability. A fresh guarded reload and full native
selftest is now running under
`opentpu-native-jtag-retrained-fulltest-20261014t044514z.service`. Neither
USB adapter failure, USB supply, board supply nor software origin has been
established as the cause of the dropout.

At 12:45 HKT the next legacy-loader SRAM upload also lost USB. Its actual
exit was -6 after `LIBUSB_ERROR_NO_DEVICE` and an abort; the apparent 100%
progress bar did not prove configuration. The kernel then logged repeated
descriptor protocol/time-out errors with no JTAG client running. The user
manually reconnected USB before the 12:54 enumeration.
[Saved chronology](../build/fedora-vivado/dlc10-usb-recurrence-20261014T045443Z/manifest.json).

The current owner is
`opentpu-native-vivado-fulltest-20261014t045031z.service`. Its
[receipt](../build/fedora-vivado/native-vivado-program-and-fulltest-20261014T045031Z/manifest.json)
records a guarded attempt using native Vivado for programming and subsequent
JTAG tests. Long USB stability and complete compute/model results remain
pending. A secure physical connection does not establish the precise traffic
or firmware condition that caused the observed dropout.
