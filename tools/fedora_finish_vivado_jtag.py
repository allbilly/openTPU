#!/usr/bin/env python3
"""Resume full qualified Vivado hardware tests after the DLC10 reappears.

Owns the cable for the guarded SRAM load and subsequent physical selftest.
Keeps the XVC server's stdin open, records actual exits, and never writes flash.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import socket
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
QUALIFIED = ROOT/'build/fedora-vivado/mig-jtag-controller-20261010T235833Z'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--wait-usb', type=int, default=600)
    ap.add_argument('--xvc-manifest', type=Path,
                    help='use a separately qualified XVC binary without changing xvc-ready.json')
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists():
        ap.error('Choose a new receipt directory')
    if args.wait_usb < 0:
        ap.error('--wait-usb must be nonnegative')
    out.mkdir(parents=True)
    manifest = dict(status='WAITING_FOR_USB', flash_written=False,
                    candidate=str(QUALIFIED), started_utc=datetime.now(timezone.utc).isoformat(),
                    required=['normal selftest including vops and stream',
                              'physical LFM2 eight-token comparison against ISA'])
    server = None
    server_log = None

    def save():
        temporary = out/'manifest.json.tmp'
        temporary.write_text(json.dumps(manifest,indent=2)+'\n')
        temporary.replace(out/'manifest.json')

    def run(stage, command):
        manifest['status'] = stage.upper()+'_RUNNING'
        (out/f'{stage}.command.json').write_text(json.dumps(command,indent=2)+'\n')
        print('START '+stage,flush=True)
        with (out/f'{stage}.log').open('w') as log:
            child = subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
            manifest['child_pid'] = child.pid
            save()
            code = child.wait()
        manifest.pop('child_pid',None)
        (out/f'{stage}.exit').write_text(f'{code}\n')
        manifest[stage+'_exit'] = code
        save()
        if code:
            raise RuntimeError(f'{stage} exited {code}; see {out/f"{stage}.log"}')

    try:
        save()
        deadline = time.monotonic()+args.wait_usb
        while True:
            usb = subprocess.run(['lsusb'],capture_output=True,text=True,check=True).stdout
            (out/'lsusb-latest.txt').write_text(usb)
            cables = [line for line in usb.splitlines() if 'ID 03fd:' in line]
            manifest.update(observed_utc=datetime.now(timezone.utc).isoformat(),usb_cables=cables)
            save()
            if cables:
                if len(cables) != 1:
                    raise RuntimeError('Expected exactly one Xilinx cable')
                break
            if time.monotonic() >= deadline:
                manifest['status'] = 'WAIT_USB_EXPIRED_NO_HARDWARE_ACCESSED'
                print(manifest['status'],flush=True)
                return 2
            time.sleep(min(5,max(0,deadline-time.monotonic())))
        # The frozen candidate's programmer performs both full offline audits
        # and the exact expected chain check before volatile SRAM loading.
        run('program',['python3',str(QUALIFIED/'program_candidate.py'),
                       '--out',str(out/'programming')])
        command = ['python3',str(ROOT/'tools/fedora_xvc_server.py'),'--port','3721']
        if args.xvc_manifest:
            command += ['--manifest',str(args.xvc_manifest.resolve())]
        (out/'xvc.command.json').write_text(json.dumps(command,indent=2)+'\n')
        server_log = (out/'xvc.log').open('w')
        server = subprocess.Popen(command,cwd=ROOT,stdin=subprocess.PIPE,
                                  stdout=server_log,stderr=subprocess.STDOUT)
        manifest['xvc_pid'] = server.pid
        save()
        deadline = time.monotonic()+120
        while True:
            if server.poll() is not None:
                raise RuntimeError('XVC exited before accepting clients')
            try:
                with socket.create_connection(('127.0.0.1',3721),timeout=0.5):
                    break
            except OSError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('XVC startup timeout')
                time.sleep(0.5)
        python = str(ROOT/'build/fedora-venv/bin/python')
        host = str(QUALIFIED/'mig_host.py')
        run('smi',[python,'-u',host,'--receipt',str(out/'smi.json'),'smi'])
        identity = json.loads((out/'smi.json').read_text())
        manifest['identity_receipt'] = identity
        save()
        run('selftest',[python,'-u',host,'--receipt',str(out/'selftest.json'),
                        'selftest','--model','lfm2','--tokens','8','--wformat','int8'])
        receipt = json.loads((out/'selftest.json').read_text())
        rows = receipt.get('model_checks',[])
        if not rows or not all(row.get('exact_match') for row in rows):
            raise RuntimeError('Physical model token comparison is absent or failed')
        manifest.update(status='PASS_FULL_PHYSICAL_SELFTEST_AND_LFM2',model_checks=rows)
        print(manifest['status'],flush=True)
        return 0
    except Exception as error:
        manifest.update(status='FAIL',error=repr(error))
        print(manifest['error'],flush=True)
        return 1
    finally:
        if server is not None:
            if server.poll() is None:
                try:
                    server.stdin.write(b'\n')
                    server.stdin.flush()
                    server.wait(timeout=15)
                except (BrokenPipeError,OSError,subprocess.TimeoutExpired):
                    server.terminate()
                    try:
                        server.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        server.kill()
                        server.wait()
            manifest['xvc_exit'] = server.returncode
            (out/'xvc.exit').write_text(f'{server.returncode}\n')
        if server_log is not None:
            server_log.close()
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
