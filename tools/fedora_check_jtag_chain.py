#!/usr/bin/env python3
"""Check the fresh initializer log before programming the single YPCB FPGA.

This reads a file only. It neither detects nor programs hardware. The caller
must capture a successful invocation of dlc10-init.sh for the intended board.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

EXPECTED_IDCODE = 0x23751093
EXPECTED_IR_LENGTH = 6


def require(condition, message):
    if not condition:
        raise ValueError(message)


def check_text(text):
    # main.cpp emits these fields with printf/cout. Driver diagnostics may use
    # terminal colors; only SGR sequences are removed, not other control data.
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    counts, indices, idcodes, lengths = [], [], [], []
    fields = [
        ('found', r'found\s+(\d+)\s+devices', counts, 10),
        ('index', r'index\s+(\d+):', indices, 10),
        ('idcode', r'idcode\s+0x([0-9a-fA-F]{1,8})', idcodes, 16),
        ('irlength', r'irlength\s+(\d+)', lengths, 10),
    ]
    for number, line in enumerate(text.splitlines()):
        line = line.strip()
        for prefix, pattern, destination, base in fields:
            if re.match(r'^'+prefix+r'\b', line):
                match = re.fullmatch(pattern, line)
                require(match is not None, 'Malformed JTAG '+prefix+' field')
                destination.append((number, int(match[1], base)))
                break
    require(len(counts) == 1 and counts[0][1] == 1, 'Require exactly one detected JTAG device')
    require(len(indices) == 1 and indices[0][1] == 0, 'Require exactly one JTAG index zero')
    require(len(idcodes) == 1 and idcodes[0][1] == EXPECTED_IDCODE,
            'Require only the expected YPCB IDCODE 0x23751093')
    require(len(lengths) == 1 and lengths[0][1] == EXPECTED_IR_LENGTH,
            'Require the expected six-bit JTAG IR length')
    require(counts[0][0] < indices[0][0] < idcodes[0][0] < lengths[0][0],
            'JTAG detection fields are out of order')
    return dict(status='SINGLE_EXPECTED_YPCB_CHAIN_LOG_PASS', device_count=1,
                index=0, idcode='0x23751093', ir_length=6,
                scope='Parsed log only; freshness and successful detection belong to the caller',
                programming='NOT_RUN', flash_written=False)


def check(path):
    path = Path(path).resolve()
    raw = path.read_bytes()
    result = check_text(raw.decode('utf-8', errors='strict'))
    result['log'] = dict(path=str(path), bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--init-log', required=True, type=Path)
    args = parser.parse_args()
    try:
        result = check(args.init_log)
    except (ValueError, OSError) as error:
        parser.exit(1, 'JTAG chain guard failed: '+str(error)+'\n')
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
