#!/usr/bin/env python3
"""Recalibrate physical CH0 through the current CH1 image's retained PHY/CSRs.

Preserves FPGA SRAM and flash. Only CH0 calibration/BIST is requested. This
image has no normal CH0 user traffic, so a pass is a PHY/BIST result, not a
dual-channel host or compute pass.
"""
from datetime import datetime, timezone
import argparse
import hashlib
import importlib.util
import inspect
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


def adapter_factory(path, name=None):
    """Load a user's existing transport without opening the cable during discovery."""
    path = path.expanduser().resolve()
    spec = importlib.util.spec_from_file_location('_otpu_ddr_adapter', path)
    if spec is None or spec.loader is None:
        raise ValueError('Cannot load adapter: ' + str(path))
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    if name:
        factory = getattr(module, name)
    else:
        candidates = [(n, c) for n, c in inspect.getmembers(module, inspect.isclass)
                      if c.__module__ == module.__name__ and
                      all(callable(getattr(c, m, None)) for m in ('reg_read', 'reg_write'))]
        if len(candidates) != 1:
            raise ValueError('Choose --factory; adapter transport classes: ' +
                             ', '.join(n for n, _ in candidates))
        name, factory = candidates[0]
    if not callable(factory):
        raise ValueError('Adapter factory is not callable: ' + name)
    return name, factory


def open_adapter(factory, core):
    params = inspect.signature(factory).parameters
    accepts_data = 'calibration_data' in params or any(
        p.kind == inspect.Parameter.VAR_KEYWORD for p in params.values())
    transport = factory(calibration_data=core) if accepts_data else factory()
    try:
        transport.calibration_data = core
        if not all(callable(getattr(transport, m, None)) for m in ('reg_read', 'reg_write', 'close')):
            raise ValueError('Adapter must expose reg_read, reg_write and close')
    except Exception:
        if callable(getattr(transport, 'close', None)):
            transport.close()
        raise
    return transport


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
    global CORE
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--core', type=Path, default=CORE, help='Matching CH1 DDR800 core directory')
    ap.add_argument('--out', type=Path, help='Fresh result directory')
    ap.add_argument('--adapter', type=Path, help='Existing Mac/other-host transport .py file')
    ap.add_argument('--factory', help='Adapter class or factory name; auto-detected when unique')
    ap.add_argument('--snapshot-only', action='store_true',
                    help='Read identity, calibration and counters; do not calibrate or start BIST')
    ap.add_argument('--soak-seconds', type=float, default=0,
                    help='After successful CH0 calibration, repeat full-capacity tests for this duration')
    ap.add_argument('--alias', action='store_true', help='Keep current training; diagnose CH0 address aliasing')
    ap.add_argument('--firmware', type=Path, help='Load and verify an isolated experimental firmware manifest')
    args = ap.parse_args()
    CORE = args.core.expanduser().resolve()
    if args.adapter:
        args.adapter = args.adapter.expanduser().resolve()
    if args.factory and not args.adapter:
        ap.error('--factory requires --adapter')
    if not 0 <= args.soak_seconds < float('inf'):
        ap.error('--soak-seconds must be finite and nonnegative')
    if args.snapshot_only and (args.alias or args.firmware or args.soak_seconds):
        ap.error('--snapshot-only cannot be combined with --alias, --firmware or --soak-seconds')
    if args.alias and args.soak_seconds:
        ap.error('--alias cannot be combined with --soak-seconds')
    require_modes = not (args.alias and args.firmware)
    if not require_modes:
        ap.error('--alias and --firmware are mutually exclusive')
    prefix = 'ddr-recovery-alias-' if args.alias else 'ddr-recovery-firmware-test-' if args.firmware else 'ddr-recovery-initial-'
    out = (args.out or BASE / (prefix + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))).resolve()
    out.mkdir(parents=True, exist_ok=False)
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
        require(p.get('physical_user_channels') == [1] and
                p.get('usable_logical_bytes') == 1 << 31 and
                p.get('parameters') == dict(CORE_KHZ=100000, DDR_MTS=800),
                'Require the matched CH1-only DDR800 core')
        for item in p['files'].values():
            require(hashlib.sha256((CORE / item['name']).read_bytes()).hexdigest()
                    == item['sha256'], 'Core source fingerprint mismatch')
        if args.adapter:
            name, factory = adapter_factory(args.adapter, args.factory)
            r['transport'] = dict(kind='adapter', factory=name,
                                  path=str(args.adapter.resolve()),
                                  sha256=hashlib.sha256(args.adapter.read_bytes()).hexdigest())
            t = open_adapter(factory, CORE)
        else:
            t, hw, bridge = native_transport(out, r, save, require)
        board = Board(t, check=False, calibrate=False)
        require(t.reg_read(0x5c) == 0x08000102, 'Current CH1 image marker absent')
        require(t.reg_read(R.R_ID) == R.ID_OTPU, 'OpenTPU identity absent')
        require(not t.reg_read(R.R_STATUS) & (R.ST_RUN | R.ST_LOADING), 'Compute must be idle')
        r['identity_before'] = board.info()
        csr = memcal.csr(t)
        c0, c1 = ddrcal.Chan(csr, 0), ddrcal.Chan(csr, 1)
        r['ch1_ready_before'] = c1.r('cal_ready')
        if args.snapshot_only:
            regs = ddrcal.csr_map(CORE / 'csr.csv')
            fields = ['cal_ready', 'phase_dqs_steps', 'phase_dqs_busy',
                      'wclk_mmcm_locked', 'ecc_enable', 'ecc_sec_errors', 'ecc_ded_errors',
                      'bist_done', 'bist_mode', 'bist_base', 'bist_length',
                      'bist_beats', 'bist_errors', 'bist_lane_bits']
            fields += [f'bist_lane{i}_errors' for i in range(9)]
            r['physical_channels'] = {
                ch: {field: view.r(field) for field in fields if view.name(field) in regs}
                for ch, view in ((0, c0), (1, c1))}
            if selfcal.present(csr):
                r['selfcal_state'] = selfcal.state(csr)
                r['calibration'] = selfcal.result(csr, CORE / 'sdram_init.py')
            r['ch1_ready_after'] = c1.r('cal_ready')
            r['status'] = 'PASS_PHYSICAL_DDR_CSR_SNAPSHOT_ONLY_MEMORY_NOT_TESTED'
            print(json.dumps(dict(status=r['status'], out=str(out))), flush=True)
            return 0
        require(r['ch1_ready_before'] == 1, 'Working CH1 must be ready')
        return probe(args, out, r, t, board, csr, c0, c1, save, require)
    except Exception as error:
        r.update(status='FAIL', error=repr(error))
        print(json.dumps(r, indent=2), flush=True)
        return 1
    finally:
        cleanup_errors = []
        if board is not None:
            try:
                board.close()
            except Exception as error:
                cleanup_errors.append('Board close: ' + repr(error))
        if t is not None:
            try:
                t.close()
                r['transport_closed'] = True
            except Exception as error:
                cleanup_errors.append('Transport close: ' + repr(error))
        if bridge is not None and bridge.poll() is None:
            try:
                link = NativeLink(timeout=5)
                link.command('QUIT')
                link.close()
                bridge.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                stop(bridge)
        stop(hw)
        if cleanup_errors:
            r.update(status='FAIL', cleanup_errors=cleanup_errors)
        r['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        if cleanup_errors:
            raise RuntimeError('Transport cleanup failed; see manifest.json')


def native_transport(out, r, save, require):
    """Retain the original Fedora Vivado/JTAG connection path."""
    hw = bridge = None
    try:
        for name in ('hw_server', 'openFPGALoader', 'xsdb', 'fxload'):
            require(subprocess.run(['pgrep', '-x', name], stdout=subprocess.DEVNULL).returncode == 1,
                    'Cable already owned: ' + name)
        for port in (3122, 3741):
            with socket.socket() as sock:
                require(sock.connect_ex(('127.0.0.1', port)) != 0, 'Native port occupied')
        usb = subprocess.check_output(['lsusb'], text=True)
        require(sum('ID 03fd:' in line for line in usb.splitlines()) == 1, 'Require one JTAG adapter')
        r['usb_at_start'] = usb
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
        return t, hw, bridge
    except BaseException:
        stop(bridge)
        stop(hw)
        raise


def probe(args, out, r, t, board, csr, c0, c1, save, require):
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
    r.update(bist=[], bist_trials=[], soak_seconds_requested=args.soak_seconds,
             status='PHYSICAL_CH0_FULL_CAPACITY_BIST_RUNNING')
    started = time.monotonic()
    trial = 0
    while True:
        seed = (0x9e3779b97f4a7c15 ^ (trial * 0xd1b54a32d192ed03)) & ((1 << 64) - 1)
        for mode in (0, 1, 2, 3):
            result = ddrcal.bist(c0, 1 << 25, mode, seed, 100000000, timeout=120)
            r['bist'].append(dict(trial=trial, seed=hex(seed), mode=mode, **result))
            save()
            require(result['beats'] == 1 << 25 and not result.get('errors', 0)
                    and not any(result.get('lanes', [])) and not result.get('bits', 0),
                    'CH0 full-capacity BIST failed')
        r['ch1_ready_after'] = c1.r('cal_ready')
        require(r['ch1_ready_after'] == 1, 'CH1 readiness changed during CH0 BIST')
        sample = dict(trial=trial, seed=hex(seed), elapsed_seconds=time.monotonic()-started,
                      identity=board.info(), ch1_ready=r['ch1_ready_after'])
        r['bist_trials'].append(sample)
        save()
        if args.soak_seconds:
            print(json.dumps(sample), flush=True)
        if sample['elapsed_seconds'] >= args.soak_seconds:
            break
        trial += 1
    r['status'] = ('PASS_PHYSICAL_CH0_RAW_BIST_SOAK_NORMAL_PORT_PENDING' if args.soak_seconds else
                   'PASS_PHYSICAL_CH0_CALIBRATION_AND_RAW_BIST_WARM_NORMAL_PORT_PENDING')
    print(json.dumps(r, indent=2), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
