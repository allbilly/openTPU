#!/usr/bin/env python3
"""Run all basic operations on the ISA simulator (or RTL), preserving individual receipts."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys


CASES = [('simple_add', 'simple_add.py', []),
         *[('elementwise_' + op, 'elementwise.py', ['--op', op])
           for op in ['add', 'sub', 'mul', 'max', 'min', 'relu', 'abs']],
         ('gemm', 'gemm.py', []), ('conv', 'conv.py', []),
         ('pooling_max', 'pooling.py', ['--op', 'max']),
         ('pooling_avg', 'pooling.py', ['--op', 'avg']),
         ('softmax', 'softmax.py', []), ('rmsnorm', 'rmsnorm.py', [])]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backend', choices=['isa', 'rtl'], default='isa')
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--out', type=Path, help='fresh parent directory for individual results')
    args = p.parse_args()
    folder = args.out.expanduser().resolve() if args.out else None
    if folder is not None:
        folder.mkdir(parents=True, exist_ok=False)
    summary = dict(status='RUNNING', backend=args.backend, seed=args.seed, cases=[],
                   started_utc=datetime.now(timezone.utc).isoformat(), hardware_accessed=False)

    def save():
        if folder is not None:
            temporary = folder / 'summary.json.tmp'
            temporary.write_text(json.dumps(summary, indent=2) + '\n')
            temporary.replace(folder / 'summary.json')

    save()
    try:
        for name, script, extra in CASES:
            command = [sys.executable, '-B', str(Path(__file__).resolve().parent / script),
                       '--backend', args.backend, '--seed', str(args.seed), *extra]
            if folder is not None:
                command += ['--out', str(folder / name)]
            completed = subprocess.run(command, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
            summary['cases'].append(dict(example=name, returncode=completed.returncode))
            save()
            if completed.returncode:
                raise RuntimeError(f'{name} failed with exit status {completed.returncode}')
        summary['status'] = 'PASS'
    except BaseException as error:
        summary.update(status='FAIL', error=repr(error))
        raise
    finally:
        summary['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    print(f"PASS: {len(CASES)} operation examples on {args.backend}")


if __name__ == '__main__':
    main()
