#!/usr/bin/env python3
"""Load a reviewed CH1 PCIe image into YPCB SRAM with native Vivado JTAG.

Requires completed image and CDC/bus-skew receipts. No flash operations and
no USER2 mailbox: the loaded image's host interface is PCIe XDMA.
"""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
IMAGE_PASS = 'CH1_PCIE_IMAGE_PACKET_CRC_PINS_ROUTE_TIMING_PASS_CDC_REVIEW_PENDING'
REVIEW_PASS = 'CH1_PCIE_IMAGE_CDC_BUS_SKEW_REVIEW_PASS'

TCL = r'''
open_hw_manager
connect_hw_server -url localhost:3122
set targets [get_hw_targets]
if {[llength $targets] != 1} {error "Expected exactly one JTAG target"}
current_hw_target [lindex $targets 0]
set_property PARAM.FREQUENCY 3000000 [current_hw_target]
open_hw_target
set devices [get_hw_devices]
if {[llength $devices] != 1 || [get_property PART [lindex $devices 0]] ne "xc7k480t"} {
    error "Expected single YPCB XC7K480T"
}
close_hw_target
open_hw_target -jtag_mode 1
run_state_hw_jtag RESET
run_state_hw_jtag IDLE
scan_ir_hw_jtag 6 -tdi 09
set ident [scan_dr_hw_jtag 32 -tdi 0]
if {[expr "0x$ident"] != 0x23751093} {error "Unexpected raw IDCODE"}
close_hw_target
open_hw_target
set devices [get_hw_devices]
if {[llength $devices] != 1 || [get_property PART [lindex $devices 0]] ne "xc7k480t"} {
    error "Programming target changed"
}
set device [lindex $devices 0]
set_property PROGRAM.FILE $::env(OTPU_CH1_BIT) $device
program_hw_devices $device
refresh_hw_device $device
set init [get_property REGISTER.IR.BIT4_INIT_COMPLETE $device]
set done [get_property REGISTER.IR.BIT5_DONE $device]
if {![string is boolean -strict $init] || ![string is boolean -strict $done] || !$init || !$done} {
    error "Native programming INIT/DONE failed"
}
close_hw_target
open_hw_target -jtag_mode 1
run_state_hw_jtag RESET
run_state_hw_jtag IDLE
scan_ir_hw_jtag 6 -tdi 09
set ident [scan_dr_hw_jtag 32 -tdi 0]
if {[expr "0x$ident"] != 0x23751093} {error "Post-load IDCODE changed"}
set f [open $::env(OTPU_CH1_PROGRAM_STATUS) w]
puts $f "INIT=1 DONE=1 IDCODE=23751093"
close $f
close_hw_target
disconnect_hw_server
close_hw_manager
exit
'''


def require(ok, message):
    if not ok:
        raise ValueError(message)


def describe(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha)


def artifact_matches(expected, path=None):
    """Accept a preserved path alias while checking the exact recorded content."""
    path = Path(expected['path'] if path is None else path)
    actual = describe(path)
    return (path.resolve() == Path(expected['path']).resolve() and
            actual['bytes'] == expected['bytes'] and actual['sha256'] == expected['sha256'])


def check_receipts(qualification, review):
    q = json.loads(qualification.read_text()); r = json.loads(review.read_text())
    require(q['status'] == IMAGE_PASS and not q['hardware_accessed'], 'Completed offline image audit is required')
    require(r['status'] == REVIEW_PASS and artifact_matches(r['qualification'], qualification),
            'Matching completed CDC/bus-skew review is required')
    require(not r['hardware_accessed'], 'Unexpected review scope')
    for key in ('WNS','WHS','WPWS'):
        require(q['timing'][key] >= 0, 'Timing violation remains')
    for key in ('setup_failing','hold_failing','pulse_failing'):
        require(q['timing'][key] == 0, 'Timing failure remains')
    require(q['route']['routable'] == q['route']['fully_routed'] > 0 and
            q['route']['routing_errors'] == 0 and q['pins_checked'] == 278, 'Image route/pin audit failed')
    require(q['crc']['status'] == 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH' and
            q['crc']['crc_checkpoints'] == 2, 'Image CRC audit failed')
    bit = Path(q['bitstream']['path'])
    require(artifact_matches(q['bitstream'], bit), 'Qualified bitstream changed')
    require(artifact_matches(q['build_manifest']), 'Build receipt changed')
    for item in q['ecc'].values():
        if isinstance(item, dict) and 'path' in item:
            require(artifact_matches(item), 'ECC receipt changed')
    return bit, q, r


def stop_group(process):
    """Close every owned loader child, including a surviving hw_server wrapper."""
    if process is None:
        return None
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    deadline = time.monotonic()+10
    while time.monotonic() < deadline:
        process.poll()
        try:
            os.killpg(process.pid, 0)
        except ProcessLookupError:
            break
        time.sleep(.1)
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    return process.wait(timeout=10)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--qualification',required=True,type=Path)
    ap.add_argument('--review',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--vivado-bin',type=Path,default=Path(expand_paths('@VIVADO_BIN@')))
    ap.add_argument('--preflight-only',action='store_true',help='Check receipts only; no hardware access')
    a = ap.parse_args(); out = a.out.resolve()
    require(not out.exists(), 'Choose a fresh programming receipt directory')
    out.mkdir(parents=True)
    record = dict(status='STARTING',hardware_accessed=False,physical_model_verified=False,
        flash_written=False,programming='NOT_RUN',started_utc=datetime.now(timezone.utc).isoformat())
    hw = vivado = None
    def save():
        tmp=out/'manifest.json.tmp'; tmp.write_text(json.dumps(record,indent=2)+'\n'); tmp.replace(out/'manifest.json')
    try:
        save();bit,q,r=check_receipts(a.qualification.resolve(),a.review.resolve())
        record.update(bitstream=describe(bit),qualification=describe(a.qualification),review=describe(a.review))
        if a.preflight_only:
            record['status']='PASS_OFFLINE_PROGRAMMING_PREFLIGHT_HARDWARE_NOT_ACCESSED';return 0
        for name in ('hw_server','openFPGALoader','xsdb','fxload'):
            require(subprocess.run(['pgrep','-x',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode == 1,
                    'Active cable owner: '+name)
        with socket.socket() as sock:
            require(sock.connect_ex(('127.0.0.1',3122)) != 0, 'Hardware server port already owned')
        usb = subprocess.check_output(['lsusb'],text=True)
        cables = [line for line in usb.splitlines() if 'ID 03fd:' in line]
        require(len(cables) == 1 and any('ID '+x in cables[0] for x in ('03fd:0008','03fd:0013')),
                'Exactly one supported DLC10 USB cable is required')
        for name in ('vivado','hw_server'):
            require((a.vivado_bin/name).is_file(), 'Missing native tool: '+name)
        record.update(status='NATIVE_SRAM_PROGRAMMING_RUNNING',usb_at_start=usb);save()
        (out/'program.tcl').write_text(TCL)
        with (out/'hw-server.log').open('w') as log:
            hw=subprocess.Popen([str(a.vivado_bin/'hw_server'),'-s','tcp::3122'],stdout=log,
                                stderr=subprocess.STDOUT,start_new_session=True)
        env=dict(os.environ,OTPU_CH1_BIT=str(bit),OTPU_CH1_PROGRAM_STATUS=str(out/'program-status.txt'))
        command=[str(a.vivado_bin/'vivado'),'-mode','batch','-nojournal','-nolog','-source',str(out/'program.tcl')]
        (out/'program.command.json').write_text(json.dumps(command,indent=2)+'\n')
        with (out/'vivado.log').open('w') as log:
            vivado=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            record.update(hw_server_pid=hw.pid,vivado_pid=vivado.pid,hardware_accessed=True);save()
            code=vivado.wait(timeout=600)
        require(code == 0, 'Native SRAM programming failed; see vivado.log')
        require((out/'program-status.txt').read_text().strip() == 'INIT=1 DONE=1 IDCODE=23751093',
                'Fresh programming completion receipt absent')
        require(describe(bit) == q['bitstream'], 'Image changed during programming')
        record.update(status='PASS_NATIVE_CH1_PCIE_SRAM_INIT_DONE_IDCODE_LFM2_NOT_RUN',
                      programming='PASS_VOLATILE_SRAM',pcie_host_test='PENDING')
        return 0
    except Exception as error:
        record.update(status='FAIL',error=repr(error));print(record['error'],flush=True);return 1
    finally:
        record['vivado_exit']=stop_group(vivado)
        record['hw_server_exit']=stop_group(hw)
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__ == '__main__':
    raise SystemExit(main())
