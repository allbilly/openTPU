#!/usr/bin/env python3
"""Observe one identified CH1 LFM2 service without accessing JTAG or changing it."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'build/fedora-vivado'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pid', required=True, type=int)
    ap.add_argument('--invocation', required=True)
    ap.add_argument('--samples', type=int, default=16)
    ap.add_argument('--interval', type=float, default=55)
    a = ap.parse_args()
    if a.samples < 1 or not 0 < a.interval <= 55:
        ap.error('Use positive samples and an interval of at most 55 seconds')
    pointer = json.loads((BASE / 'ch1-jtag-lfm2-current.json').read_text())
    out = Path(pointer['out'])
    unit = pointer['unit']
    baseline = None
    for sample in range(a.samples):
        run = json.loads((out / 'manifest.json').read_text())
        model = json.loads((out / 'model/manifest.json').read_text())
        props = ['SubState', 'MainPID', 'InvocationID', 'ExecMainStatus']
        cmd = ['systemctl', '--user', 'show', unit]
        for prop in props:
            cmd.extend(['-p', prop])
        service = dict(line.split('=', 1) for line in
                       subprocess.check_output(cmd, text=True).splitlines())
        live = (service['SubState'] == 'running' and
                service['MainPID'] == str(a.pid) and
                service['InvocationID'] == a.invocation)
        if live:
            try:
                argv = Path(f'/proc/{a.pid}/cmdline').read_bytes().split(b'\0')
                live = str(out.resolve()).encode() in argv
            except FileNotFoundError:
                live = False
        now = datetime.now(timezone.utc)
        # This run's completed matmul setup wrote 6,656 bytes before the image.
        written = max(0, run.get('write_bytes', 0) - 6656)
        total = 242628608
        uploaded = min(total, written)
        phase = 'IMAGE_UPLOAD' if uploaded < total else 'POST_UPLOAD_LFM2'
        tokens = model.get('actual_partial_token_ids', [])
        errors = [run.get('error'), model.get('error')]
        elapsed = 0 if baseline is None else time.monotonic() - baseline[1]
        rate = ((uploaded - baseline[0]) / elapsed
                if baseline is not None and elapsed > 0 else None)
        eta = (total - uploaded) / rate if rate and rate > 0 else None
        receipt = dict(
            status=('VERIFIED_WAIT_LIVE_FULL_LFM2_IMAGE_UPLOAD' if phase == 'IMAGE_UPLOAD'
                    else 'VERIFIED_WAIT_LIVE_POST_UPLOAD_LFM2') if live and not any(errors)
                    else run['status'],
            phase=phase, observed_utc=now.isoformat(), service=service,
            process_identity_verified=live, upload_bytes=uploaded,
            prepared_image_bytes=total, post_upload_write_bytes=max(0, written - total),
            window_seconds=elapsed, window_bytes_per_second=rate,
            estimated_upload_seconds_remaining=eta,
            estimate_scope='Upload only; inference and ISA verification remain pending',
            physical_matmul_pass=model.get('matmul', {}).get('exact_match', False),
            physical_model_verified=run.get('physical_model_verified', False),
            actual_partial_token_ids=tokens, errors=errors,
            flash_written=run.get('flash_written', False))
        with (BASE / 'ch1-lfm2-upload-observations.jsonl').open('a') as f:
            f.write(json.dumps(receipt) + '\n')
        # Keep the previous useful throughput window until two samples exist.
        if baseline is not None or not live or tokens or any(errors):
            p = BASE / 'ch1-lfm2-upload-current.json'
            tmp = p.with_suffix('.observer.tmp')
            tmp.write_text(json.dumps(receipt, indent=2) + '\n')
            tmp.replace(p)
        print(json.dumps(dict(
            HKT=now.astimezone().strftime('%H:%M:%S'), live=live, phase=phase,
            upload_MB=round(uploaded / 1e6, 2), percent=round(uploaded / total * 100, 2),
            rate_kB_s=round(rate / 1000, 2) if rate is not None else None,
            upload_eta_minutes=round(eta / 60, 1) if eta is not None else None,
            tokens=tokens, status=run['status'], errors=errors)), flush=True)
        if not live or any(errors):
            return 0 if run.get('physical_model_verified') and not any(errors) else 2
        if tokens or uploaded >= total:
            return 0
        if baseline is None:
            baseline = (uploaded, time.monotonic())
        if sample < a.samples - 1:
            time.sleep(a.interval)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
