#!/usr/bin/env python3
"""Diagnose the loaded Vivado MIG image without programming or changing clocks.

Preserve existing counters before clearing them for each diagnostic trial.
Counter clearing isolates trials; it is never reported as a memory repair.
The qualified XVC helper owns the cable until this process finishes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / 'build/fedora-vivado/mig-jtag-controller-20261010T235833Z'
sys.path.insert(0, str(ROOT))
from opentpu.host import regs as R


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--xvc-manifest', type=Path, required=True)
    ap.add_argument('--full-after-small', action='store_true')
    ap.add_argument('--reload', action='store_true',
                    help='Guarded SRAM reload of the same frozen image before diagnostics')
    ap.add_argument('--selftest-after-full', action='store_true')
    args = ap.parse_args()
    if args.selftest_after_full and not args.full_after_small:
        ap.error('--selftest-after-full requires --full-after-small')
    out = args.out.resolve()
    if out.exists():
        ap.error('Choose a new output directory')
    out.mkdir(parents=True)
    receipt = dict(status='STARTING', physical=True, flash_written=False,
                   fpga_programmed=False, clocks_changed=False,
                   started_utc=datetime.now(timezone.utc).isoformat(),
                   counter_clear_scope='Per-trial isolation after saved snapshots; not a repair',
                   trials=[], full_memory_passes=[])
    server = transport = None

    def save():
        tmp = out / 'manifest.json.tmp'
        tmp.write_text(json.dumps(receipt, indent=2) + '\n')
        tmp.replace(out / 'manifest.json')

    def require(ok, message):
        if not ok:
            raise RuntimeError(message)

    def idle():
        state = transport.reg_read(R.R_STATUS)
        required = R.ST_CALIB0 | R.ST_CALIB1
        require(state & required == required and not state &
                (R.ST_RUN | R.ST_LOADING), 'Both channels must be calibrated and compute idle')
        for ch in (0, 1):
            require(not transport.reg_read(transport.base(ch) + 8) & 1,
                    'Diagnostic channel is busy')

    def snapshot():
        offsets = [8, 0x0c, 0x10, 0x1c, 0x20, 0x24, 0x28, 0x2c,
                   0x34, 0x38, 0x3c, 0x40]
        names = ['status', 'start', 'length', 'issued', 'completed',
                 'corrected_beats', 'uncorrectable_beats', 'bad_beats',
                 'cycles', 'first_bad_beat', 'bad_bits_low', 'bad_bits_high']
        return [dict(channel=ch, **dict(zip(names, transport.reg_read_many(
            [transport.base(ch) + off for off in offsets])))) for ch in (0, 1)]

    def clear():
        idle()
        for ch in (0, 1):
            transport.reg_write(transport.base(ch) + 0x30, 1)
        transport.ecc_health()

    try:
        for owner in ('openFPGALoader', 'hw_server', 'xsdb', 'fxload'):
            require(subprocess.run(['pgrep', '-x', owner], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL).returncode != 0,
                    f'Another cable owner is active: {owner}')
        with socket.socket() as s:
            require(s.connect_ex(('127.0.0.1', 3721)) != 0, 'XVC port already owned')
        for path in (CAND/'mig_host.py', CAND/'source/rtl/boards/ypcb-00338/otpu_mig_diag.sv',
                     ROOT/'opentpu/host/jtag.py', ROOT/'tools/fedora_xvc_server.py'):
            receipt.setdefault('inputs', []).append(dict(path=str(path),
                sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        if args.reload:
            receipt['status'] = 'GUARDED_SAME_IMAGE_SRAM_RELOAD_RUNNING'
            save()
            command = [sys.executable, str(CAND/'program_candidate.py'),
                       '--out', str(out/'programming')]
            (out/'program.command.json').write_text(json.dumps(command, indent=2)+'\n')
            with (out/'program.log').open('w') as program_log:
                result = subprocess.run(command, cwd=ROOT, stdout=program_log,
                                        stderr=subprocess.STDOUT, timeout=240)
            receipt['program_exit'] = result.returncode
            (out/'program.exit').write_text(f'{result.returncode}\n')
            require(result.returncode == 0, 'Guarded SRAM reload failed')
            programmed = json.loads((out/'programming/result.json').read_text())
            require(programmed['status'] == 'PASS_SRAM_PROGRAMMED_INIT_DONE' and
                    programmed['flash_written'] is False, 'SRAM programming receipt failed')
            receipt['fpga_programmed'] = True
        command = [sys.executable, str(ROOT/'tools/fedora_xvc_server.py'),
                   '--manifest', str(args.xvc_manifest.resolve()), '--port', '3721']
        (out/'xvc.command.json').write_text(json.dumps(command, indent=2)+'\n')
        log = (out/'xvc.log').open('w')
        server = subprocess.Popen(command, cwd=ROOT, stdin=subprocess.PIPE,
                                  stdout=log, stderr=subprocess.STDOUT)
        receipt.update(status='XVC_STARTING', xvc_pid=server.pid)
        save()
        deadline = time.monotonic() + 120
        while True:
            require(server.poll() is None, 'XVC exited during startup')
            try:
                with socket.create_connection(('127.0.0.1', 3721), timeout=.5):
                    break
            except OSError:
                require(time.monotonic() < deadline, 'XVC startup timeout')
                time.sleep(.5)
        spec = importlib.util.spec_from_file_location('qualified_mig_host', CAND/'mig_host.py')
        host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(host)
        transport = host.MigJtagTransport()
        identity = {name: transport.reg_read(off) for name, off in
                    [('id', R.R_ID), ('regmap', R.R_REGMAP), ('core_khz', R.R_CORE_KHZ),
                     ('build', R.R_BUILD_ID), ('ddr_mts', R.R_DDR_MTS)]}
        require(identity == dict(id=0x4f545055, regmap=3, core_khz=100000,
                                 build=0x5b1e646c, ddr_mts=1066), 'Unexpected loaded image')
        receipt.update(identity=identity, temperature_c=transport.read_die_temperature(),
                       initial_channels=snapshot(), status='SMALL_REGION_DIAGNOSTICS_RUNNING')
        idle()
        save()
        # Three separated 256 KiB regions per channel; paired write/read for
        # zero, ones, address and xorshift, including the final channel region.
        for ch in (0, 1):
            for start in (0, (1 << 24), (1 << 25) - 4096):
                for pattern in (0, 1, 2, 3):
                    trial = dict(channel=ch, start=start, beats=4096, pattern=pattern,
                                 before_clear=snapshot(), passes=[])
                    receipt['trials'].append(trial)
                    save()
                    clear()
                    try:
                        for read in (False, True):
                            trial['passes'].append(transport.bist(ch, pattern, read,
                                                   start=start, beats=4096, timeout=15))
                        trial['status'] = 'PASS'
                    except OSError as error:
                        require(not transport._failed, 'JTAG transaction failed; recovery required')
                        trial.update(status='FAIL', error=repr(error))
                    trial['after'] = snapshot()
                    save()
        failures = sum(trial['status'] != 'PASS' for trial in receipt['trials'])
        receipt['failed_small_trials'] = failures
        require(failures == 0, f'{failures} small-region memory trials failed; compute not attempted')
        if args.full_after_small:
            receipt['before_full_counter_clear'] = snapshot()
            clear()
            receipt['status'] = 'FULL_FOUR_PATTERN_MEMORY_TEST_RUNNING'
            save()
            for ch in (0, 1):
                for pattern in (1, 2, 3, 0):
                    for read in (False, True):
                        receipt['full_memory_passes'].append(transport.bist(ch, pattern, read))
                        save()
            receipt['final_ecc'] = transport.ecc_health()
            receipt['status'] = 'PASS_SMALL_REGIONS_AND_FULL_FOUR_PATTERN_MEMORY_TEST'
        else:
            receipt['status'] = 'PASS_SMALL_REGIONS_ONLY_FULL_MEMORY_PENDING'
        if args.selftest_after_full:
            transport.close()
            transport = None
            command = [sys.executable, '-u', str(CAND/'mig_host.py'), '--receipt',
                       str(out/'selftest.json'), 'selftest', '--model', 'lfm2',
                       '--tokens', '8', '--wformat', 'int8']
            (out/'selftest.command.json').write_text(json.dumps(command, indent=2)+'\n')
            with (out/'selftest.log').open('w') as selftest_log:
                child = subprocess.Popen(command, cwd=ROOT, stdout=selftest_log,
                                         stderr=subprocess.STDOUT)
                receipt.update(status='FULL_PHYSICAL_SELFTEST_RUNNING', child_pid=child.pid)
                save()
                code = child.wait()
            receipt.pop('child_pid', None)
            receipt['selftest_exit'] = code
            (out/'selftest.exit').write_text(f'{code}\n')
            require(code == 0, 'Full physical selftest failed; see selftest.log')
            checked = json.loads((out/'selftest.json').read_text())
            rows = checked.get('model_checks', [])
            require(checked['status'] == 'PASS' and rows and
                    all(row.get('exact_match') and row.get('actual_token_ids') for row in rows),
                    'Exact physical model result is absent or failed')
            receipt.update(status='PASS_FULL_PHYSICAL_SELFTEST_AND_LFM2', model_checks=rows)
        return 0
    except Exception as error:
        receipt.update(status='FAIL', error=repr(error))
        print(receipt['error'], flush=True)
        return 1
    finally:
        if transport is not None:
            try:
                receipt['final_channels'] = snapshot()
            except Exception as error:
                receipt['final_snapshot_error'] = repr(error)
            transport.close()
        if server is not None:
            if server.poll() is None:
                try:
                    server.stdin.write(b'\n')
                    server.stdin.flush()
                    server.wait(timeout=15)
                except (OSError, subprocess.TimeoutExpired):
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
            receipt['xvc_exit'] = server.returncode
            (out/'xvc.exit').write_text(f'{server.returncode}\n')
            log.close()
        receipt['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
