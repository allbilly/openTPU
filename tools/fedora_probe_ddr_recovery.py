#!/usr/bin/env python3
"""Recalibrate physical CH0 through the current CH1 image's retained PHY/CSRs.

Preserves FPGA SRAM and flash. Only CH0 calibration/BIST is requested. This
image has no normal CH0 user traffic, so a pass is a PHY/BIST result, not a
dual-channel host or compute pass.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from fedora_run_vivado_native_jtag import NativeLink, TCL, VIVADO
from opentpu.host import jtag, memcal, ddrcal, selfcal, regs as R
from opentpu.host.board import Board

CORE = ROOT / 'build/fedora-vivado/ch1-core-writable-20261014T082631Z/core'
BASE = ROOT / 'build/fedora-vivado'


def stop(proc):
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.wait(timeout=5)
    except ProcessLookupError:
        proc.wait(timeout=5)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--alias', action='store_true', help='Keep current training; diagnose CH0 address aliasing')
    ap.add_argument('--firmware', type=Path, help='Load and verify an isolated experimental firmware manifest')
    args = ap.parse_args()
    require_modes = not (args.alias and args.firmware)
    if not require_modes:
        ap.error('--alias and --firmware are mutually exclusive')
    prefix = 'ddr-recovery-alias-' if args.alias else 'ddr-recovery-firmware-test-' if args.firmware else 'ddr-recovery-initial-'
    out = BASE / (prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir()
    r = dict(status='STARTING', physical=True, physical_channels_tested=[0],
             normal_ch0_user_traffic_available=False, programming='NOT_RUN',
             flash_written=False, started_utc=datetime.now(timezone.utc).isoformat())
    hw = bridge = t = board = None

    def save():
        tmp = out / 'manifest.json.tmp'
        tmp.write_text(json.dumps(r, indent=2) + '\n')
        tmp.replace(out / 'manifest.json')

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    try:
        p = json.loads((CORE / 'openxc7-profile.json').read_text())
        for item in p['files'].values():
            require(hashlib.sha256((CORE / item['name']).read_bytes()).hexdigest()
                    == item['sha256'], 'Core source fingerprint mismatch')
        for name in ('hw_server', 'openFPGALoader', 'xsdb', 'fxload'):
            require(subprocess.run(['pgrep', '-x', name], stdout=subprocess.DEVNULL).returncode == 1,
                    'Cable already owned: ' + name)
        for port in (3122, 3741):
            with socket.socket() as sock:
                require(sock.connect_ex(('127.0.0.1', port)) != 0, 'Native port occupied')
        usb = subprocess.check_output(['lsusb'], text=True)
        require(sum('ID 03fd:' in line for line in usb.splitlines()) == 1, 'Require one JTAG adapter')
        r['usb_at_start'] = usb
        (BASE / 'ddr-recovery-current.json').write_text(json.dumps(dict(out=str(out)), indent=2) + '\n')
        (out / 'bridge.tcl').write_text(TCL)
        with (out / 'hw-server.log').open('w') as log:
            hw = subprocess.Popen([str(VIVADO / 'hw_server'), '-s', 'tcp::3122'],
                                  stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        env = dict(os.environ, OTPU_NATIVE_READY=str(out / 'native-ready.txt'))
        env.pop('OTPU_NATIVE_BIT', None)
        env.pop('OTPU_NATIVE_PROGRAM_STATUS', None)
        with (out / 'vivado.log').open('w') as log:
            bridge = subprocess.Popen([str(VIVADO / 'vivado'), '-mode', 'batch', '-nojournal',
                                       '-nolog', '-source', str(out / 'bridge.tcl')], cwd=out,
                                      env=env, stdout=log, stderr=subprocess.STDOUT,
                                      start_new_session=True)
        r.update(status='NATIVE_CHAIN_CHECK', hw_server_pid=hw.pid, vivado_pid=bridge.pid)
        save()
        deadline = time.monotonic() + 120
        while not (out / 'native-ready.txt').exists():
            require(hw.poll() is None and bridge.poll() is None, 'Native bridge exited')
            require(time.monotonic() < deadline, 'Native bridge ready timeout')
            time.sleep(.5)
        t = jtag.JtagTransport(link=NativeLink(), calibration_data=CORE)
        board = Board(t, check=False, calibrate=False)
        require(t.reg_read(0x5c) == 0x08000102, 'Current CH1 image marker absent')
        require(not t.reg_read(R.R_STATUS) & (R.ST_RUN | R.ST_LOADING), 'Compute must be idle')
        r['identity_before'] = board.info()
        csr = memcal.csr(t)
        c0, c1 = ddrcal.Chan(csr, 0), ddrcal.Chan(csr, 1)
        r['ch1_ready_before'] = c1.r('cal_ready')
        require(r['ch1_ready_before'] == 1, 'Working CH1 must be ready')
        if args.alias:
            require(c0.r('cal_ready') == 1, 'CH0 must retain its previously selected training')
            r['status'] = 'PHYSICAL_CH0_ADDRESS_AND_PATTERN_DIAGNOSTIC_RUNNING'
            r['address_tests'] = []

            def access(base, mode, seed):
                beats = 8192 // 64
                c0.w('bist_base', base // 64)
                c0.w('bist_length', beats)
                c0.w('bist_mode', mode)
                c0.w('bist_seed', seed)
                c0.w('bist_start', 1)
                result = ddrcal.bist_wait(c0, beats, mode, 100000000, timeout=30)
                require(result['beats'] == beats, 'Address diagnostic BIST count mismatch')
                return result

            seed = 0x9e3779b97f4a7c15
            for high in (1 << 20, 1 << 24, 1 << 26, 1 << 28, 1 << 29, 1 << 30, (3 << 29)):
                access(0, 0, 0)
                low_before = access(0, 1, 0)
                access(high, 0, seed)
                high_before = access(high, 1, seed)
                low_after_high = access(0, 1, 0)
                access(0, 0, 0)
                high_after_low = access(high, 1, seed)
                cross = (low_after_high, high_after_low)
                alias = (not low_before.get('errors', 0) and not high_before.get('errors', 0)
                         and all(x.get('lanes', [0] * 9)[6] > 0 and
                                 not any(v for i, v in enumerate(x.get('lanes', [])) if i != 6)
                                 for x in cross))
                row = dict(high_byte_offset=high, bytes=8192, low_before=low_before,
                           high_before=high_before, low_after_high_write=low_after_high,
                           high_after_low_write=high_after_low, bidirectional_lane6_alias=alias)
                r['address_tests'].append(row)
                save()
                print(json.dumps(row), flush=True)
            r['ch1_ready_after'] = c1.r('cal_ready')
            require(r['ch1_ready_after'] == 1, 'CH1 readiness changed during address diagnosis')
            r['alias_indicated'] = any(x['bidirectional_lane6_alias'] for x in r['address_tests'])
            r['status'] = 'PHYSICAL_CH0_ADDRESS_AND_PATTERN_DIAGNOSTIC_COMPLETE_MEMORY_NOT_QUALIFIED'
            print(json.dumps(dict(status=r['status'], alias_indicated=r['alias_indicated'], out=str(out))), flush=True)
            return 0
        require(selfcal.present(csr), 'On-board calibration CPU absent')
        if args.firmware:
            fw = json.loads(args.firmware.read_text())
            image = Path(fw['firmware'])
            require(fw['core'] == str(CORE), 'Experimental firmware core mismatch')
            require(hashlib.sha256(image.read_bytes()).hexdigest() == fw['sha256'],
                    'Experimental firmware hash mismatch')
            r['experimental_firmware'] = fw
            r['status'] = 'EXPERIMENTAL_FIRMWARE_UPLOAD_AND_READBACK'
            save()
            selfcal.load(csr, image.read_bytes(), verify=True)
            r['firmware_upload_readback_pass'] = True
        selfcal.hold(csr)
        csr.w('selfcal_config', 1 | (1 << 8))
        r['status'] = 'PHYSICAL_CH0_CPU_CALIBRATION_RUNNING'
        save()
        selfcal.release(csr)
        r['cpu_state'] = selfcal.wait(csr, timeout=240, poll=.5)
        r['calibration'] = selfcal.result(csr, CORE / 'sdram_init.py')
        if args.firmware:
            csr.w('selfcal_mbox_adr', 1)
            r['running_firmware_id'] = csr.r('selfcal_mbox_dat')
            require(r['running_firmware_id'] == fw['fw_id'], 'Running firmware ID mismatch')
            if fw.get('traffic_diagnostic'):
                raw = selfcal.mailbox(csr, 144, 192)
                require(raw[0] == 0xd16a0001 and raw[5] == 1024,
                        'Traffic diagnostic marker/count mismatch')
                r['lane6_traffic_diagnostic'] = dict(
                    marker=raw[0], best_write_bitslip=raw[1], best_read_bitslip=raw[2],
                    best_read_tap=raw[3], minimum_wrong_beats=raw[4], tests=raw[5],
                    initial_dfi_bad_lanes=raw[6], test_bytes=128*1024,
                    ck_phase=45, pass_tap_masks=raw[16:48])
                r['ch1_ready_after'] = c1.r('cal_ready')
                require(r['ch1_ready_after'] == 1, 'CH1 readiness changed during traffic diagnosis')
                r['status'] = 'PHYSICAL_LANE6_TRAFFIC_FRAMING_DIAGNOSTIC_COMPLETE_MEMORY_NOT_QUALIFIED'
                print(json.dumps(dict(status=r['status'],
                                      diagnostic=r['lane6_traffic_diagnostic'], out=str(out))), flush=True)
                return 0
        r['ch1_ready_after'] = c1.r('cal_ready')
        r['identity_after'] = board.info()
        save()
        require(r['ch1_ready_after'] == 1, 'CH1 readiness changed during CH0-only calibration')
        cal = r['calibration'].get(0, {})
        if cal.get('state') != 'ok' or not cal.get('traffic_checked'):
            r['status'] = 'PHYSICAL_CH0_CALIBRATION_FAILED_DIAGNOSTIC_SAVED'
            print(json.dumps(r, indent=2), flush=True)
            return 2
        r['bist'] = []
        for mode in (0, 1, 2, 3):
            result = ddrcal.bist(c0, 1 << 25, mode, 0x9e3779b97f4a7c15,
                                 100000000, timeout=120)
            r['bist'].append(dict(mode=mode, **result))
            save()
            require(result['beats'] == 1 << 25 and not result.get('errors', 0)
                    and not any(result.get('lanes', [])), 'CH0 full-capacity BIST failed')
        r['status'] = 'PASS_PHYSICAL_CH0_CALIBRATION_AND_RAW_BIST_WARM_NORMAL_PORT_PENDING'
        print(json.dumps(r, indent=2), flush=True)
        return 0
    except Exception as error:
        r.update(status='FAIL', error=repr(error))
        print(json.dumps(r, indent=2), flush=True)
        return 1
    finally:
        if board is not None:
            board.close()
        if t is not None:
            t.close()
        if bridge is not None and bridge.poll() is None:
            try:
                link = NativeLink(timeout=5)
                link.command('QUIT')
                link.close()
                bridge.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                stop(bridge)
        stop(hw)
        r['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
