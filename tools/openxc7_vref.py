#!/usr/bin/env python3
"""Apply the YPCB's literal DDR VREF constraints to nextpnr's FASM.

The backend currently selects 675 mV for every single-ended SSTL input.
This adapter selects 750 mV using the actual package and tile-grid metadata.
It never drops unknown features; the resulting file still needs strict X-Ray
assembly and independent timing qualification before it is a board image.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

PART = 'xc7k480tffg1156-2'


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bank_plan(xdc, database):
    """Resolve explicit bank voltages and every DDR pin against the device DB."""
    database = Path(database)
    package = database/PART/'package_pins.csv'
    tilegrid = database/'xc7k480t/tilegrid.json'
    xdc = Path(xdc)
    text = xdc.read_text()
    rows = list(csv.DictReader(package.open()))
    pins = {r['pin']: r for r in rows}
    grid = json.loads(tilegrid.read_text())
    voltages = {}
    properties = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if 'INTERNAL_VREF' in line:
            m = re.fullmatch(r'set_property INTERNAL_VREF (0\.750) \[get_iobanks (\d+)\]', line)
            if not m:
                raise ValueError('Unsupported VREF constraint: '+line)
            bank = int(m[2])
            if bank in voltages:
                raise ValueError(f'Duplicate VREF constraint for bank {bank}')
            voltages[bank] = 750
        m = re.fullmatch(r'set_property (LOC|IOSTANDARD) (\S+) \[get_ports \{([^}]+)\}\]', line)
        if m:
            entry = properties.setdefault(m[3], {})
            if m[1] in entry:
                raise ValueError('Duplicate DDR port property: '+m[3])
            entry[m[1]] = m[2]
    if not voltages or not properties:
        raise ValueError('Missing literal DDR/VREF constraints')
    ddr_banks = set()
    assigned_pins = set()
    for port, props in properties.items():
        if not port.startswith(('ddram0_', 'ddram1_')):
            raise ValueError('Unexpected port in DDR constraints: '+port)
        if props.get('IOSTANDARD') not in ('SSTL15', 'DIFF_SSTL15') or props.get('LOC') not in pins:
            raise ValueError('Missing/unsupported DDR pin or I/O standard: '+port)
        if props['LOC'] in assigned_pins:
            raise ValueError('DDR pins overlap: '+props['LOC'])
        assigned_pins.add(props['LOC'])
        ddr_banks.add(int(pins[props['LOC']]['bank']))
    if not ddr_banks <= voltages.keys():
        raise ValueError('DDR bank lacks an explicit 750 mV constraint')
    banks = {}
    for bank, mv in sorted(voltages.items()):
        bank_rows = [r for r in rows if int(r['bank']) == bank]
        # All YPCB DDR banks are left-side HR banks with 50 I/O pads. Require
        # that geometry, rather than guessing a tile from its printed name.
        tiles = [grid[r['tile']] for r in bank_rows]
        cols = {t['grid_x'] for t in tiles}
        if len(bank_rows) != 50 or len(cols) != 1 or any(not t['type'].startswith('LIOB33') for t in tiles):
            raise ValueError(f'Unsupported package geometry for VREF bank {bank}')
        ymin, ymax = min(t['grid_y'] for t in tiles), max(t['grid_y'] for t in tiles)
        matches = [n for n, t in grid.items() if t['type'] == 'HCLK_IOI3'
                   and t['grid_x'] == next(iter(cols))+1 and ymin < t['grid_y'] < ymax]
        if len(matches) != 1:
            raise ValueError(f'Cannot uniquely resolve VREF bank {bank}')
        tile = matches[0]
        feature = f'{tile}.VREF.V_{mv}_MV'
        segbits = database/('segbits_'+grid[tile]['type'].lower()+'.db')
        key = grid[tile]['type']+f'.VREF.V_{mv}_MV'
        if not any(line.split()[0] == key for line in segbits.read_text().splitlines() if line.strip()):
            raise ValueError('VREF feature absent from strict database: '+feature)
        banks[tile] = dict(bank=bank, millivolts=mv, feature=feature,
                           used_by_ddr=bank in ddr_banks,
                           segbits_sha256=sha256(segbits))
    return dict(banks=banks, ddr_port_count=len(properties),
                inputs={str(p.resolve()):sha256(p) for p in (xdc, package, tilegrid)})


def correct_fasm(text, plan):
    """Replace only the known backend selection; reject conflicting voltages."""
    seen = set()
    output = []
    changes = []
    for line in text.splitlines():
        if '.VREF.' not in line or line.lstrip().startswith('#'):
            output.append(line)
            continue
        # Bare features and explicit =1 mean the same thing. Reject ranges,
        # zero assignments, annotations and duplicate/conflicting selections.
        m = re.fullmatch(r'\s*(\S+)\.VREF\.V_(\d+)_MV(?:\s*=\s*1)?\s*(?:#.*)?', line)
        if not m or m[1] not in plan['banks']:
            raise ValueError('Unexpected VREF feature: '+line)
        tile, mv = m[1], int(m[2])
        if tile in seen or mv not in (675, 750):
            raise ValueError('Duplicate/conflicting VREF selection: '+line)
        seen.add(tile)
        target = plan['banks'][tile]['feature']
        output.append(target)
        if mv != 750:
            changes.append(dict(bank=plan['banks'][tile]['bank'], old=line.strip(), new=target))
    for tile, info in plan['banks'].items():
        if tile in seen:
            continue
        if info['used_by_ddr']:
            raise ValueError(f'Backend omitted VREF for populated DDR bank {info["bank"]}')
        output.append(info['feature'])
        changes.append(dict(bank=info['bank'], old=None, new=info['feature'],
                            reason='explicit constraint on a bank without DDR pins'))
    return '\n'.join(output)+'\n', changes


def apply(raw, target, xdc, database, audit):
    raw, target = Path(raw), Path(target)
    plan = bank_plan(xdc, database)
    text, changes = correct_fasm(raw.read_text(), plan)
    target.write_text(text)
    report = dict(status='VREF_CONSTRAINTS_APPLIED_STRICT_ASSEMBLY_PENDING',
                  input=str(raw.resolve()), input_sha256=sha256(raw),
                  output=str(target.resolve()), output_sha256=sha256(target),
                  plan=plan, changes=changes,
                  timing_qualification='NOT_ESTABLISHED_BY_VREF_CORRECTION')
    Path(audit).write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--raw', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--xdc', type=Path, required=True)
    ap.add_argument('--database', type=Path, required=True)
    ap.add_argument('--audit', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists() or args.audit.exists() or args.raw.resolve() == args.output.resolve():
        ap.error('Use new output/audit paths; the original backend FASM is retained')
    report = apply(args.raw, args.output, args.xdc, args.database, args.audit)
    print(f'Applied 750 mV to {len(report["plan"]["banks"])} banks; {len(report["changes"])} corrections')


if __name__ == '__main__':
    main()
