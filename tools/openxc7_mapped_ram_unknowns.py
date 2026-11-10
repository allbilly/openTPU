#!/usr/bin/env python3
"""Audit every EDIF-disconnected RAM input against the complete mapped graph."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from fedora_openxc7 import describe
from openxc7_mapped_edif import TOP, PROFILE


WIDTHS = {0: (0, 0), 1: (1, 0), 2: (2, 0), 4: (4, 0),
          9: (8, 1), 18: (16, 2), 36: (32, 4), 72: (64, 8)}


def number(value):
    if not isinstance(value, str) or not value or set(value) - {'0', '1'}:
        raise ValueError('Mapped RAM width is not a binary integer')
    return int(value, 2)


def unobserved(cell, pin, index, consumers):
    bits = cell['connections'].get(pin, [])
    return index >= len(bits) or (isinstance(bits[index], int) and bits[index] not in consumers)


def classify(cell, pin, index, consumers):
    primitive, params = cell['type'], cell['parameters']
    if primitive in ('RAM32M', 'RAM64M'):
        if pin not in ('DIA', 'DIB', 'DIC', 'DID'):
            return None
        return 'UNUSED_LUTRAM_READ_LANE' if unobserved(cell, 'DO' + pin[-1], index, consumers) else None
    if primitive not in ('RAMB18E1', 'RAMB36E1'):
        return None
    if any(params.get(key, default) != default for key, default in
           [('EN_ECC_READ', 'FALSE'), ('EN_ECC_WRITE', 'FALSE'),
            ('RAM_EXTENSION_A', 'NONE'), ('RAM_EXTENSION_B', 'NONE')]):
        return None
    mode = params.get('RAM_MODE', 'TDP')
    output_for = {'DIADI': 'DOADO', 'DIBDI': 'DOBDO', 'DIPADIP': 'DOPADOP', 'DIPBDIP': 'DOPBDOP'}
    if pin not in output_for:
        return None
    if mode == 'TDP':
        port = 'A' if pin in ('DIADI', 'DIPADIP') else 'B'
        width = number(params['WRITE_WIDTH_' + port])
        if width not in WIDTHS or width > (36 if primitive == 'RAMB36E1' else 18):
            return None
        if width == 0:
            enable = cell['connections'].get('WEA' if port == 'A' else 'WEBWE', [])
            return 'DISABLED_TDP_WRITE_PORT_AND_ZERO_WE' if enable and all(bit == '0' for bit in enable) else None
        count = WIDTHS[width][int(pin.startswith('DIP'))]
        if index >= count:
            return 'OUTSIDE_CONFIGURED_TDP_WRITE_WIDTH'
        # Different aspect ratios can remap a written lane to another output.
        # Do not apply direct lane reasoning unless all active reads match.
        reads = [number(params['READ_WIDTH_' + p]) for p in ('A', 'B')]
        if any(read not in (0, width) for read in reads):
            return None
        outputs = ('DOPADOP', 'DOPBDOP') if pin.startswith('DIP') else ('DOADO', 'DOBDO')
        if all(read == 0 or unobserved(cell, out, index, consumers)
               for read, out in zip(reads, outputs, strict=True)):
            return 'UNUSED_MATCHING_WIDTH_TDP_READ_LANE'
        return None
    if mode == 'SDP':
        width = 72 if primitive == 'RAMB36E1' else 36
        if (number(params['WRITE_WIDTH_A']) != 0 or number(params['WRITE_WIDTH_B']) != width
                or number(params['READ_WIDTH_A']) != width or number(params['READ_WIDTH_B']) != 0):
            return None
        return 'UNUSED_WIDE_SDP_READ_LANE' if unobserved(cell, output_for[pin], index, consumers) else None
    return None


def audit(review_path: Path, out: Path):
    review = json.loads(review_path.read_text())
    if review['status'] != 'FULL_MAPPED_GRAPH_REVIEW_PASS_ONLY_EXPLICIT_METADATA_LOSS_VIVADO_LINK_PENDING':
        raise ValueError('Complete mapped graph review required')
    if review['profile'] != PROFILE:
        raise ValueError('Full profile changed')
    descriptor = review['exported_json']
    if describe(descriptor['path']) != descriptor:
        raise ValueError('Reviewed mapped graph changed')
    top = json.loads(Path(descriptor['path']).read_text())['modules'][TOP]
    consumers = set()
    for cell in top['cells'].values():
        for pin, bits in cell['connections'].items():
            if cell['port_directions'][pin] in ('input', 'inout'):
                consumers.update(bit for bit in bits if isinstance(bit, int))
    for port in top['ports'].values():
        if port['direction'] in ('output', 'inout'):
            consumers.update(bit for bit in port['bits'] if isinstance(bit, int))
    rows = []
    for name, cell in top['cells'].items():
        for pin, bits in cell['connections'].items():
            for index, bit in enumerate(bits):
                if bit not in ('x', 'z'):
                    continue
                reason = classify(cell, pin, index, consumers)
                rows.append({'cell': name, 'primitive': cell['type'], 'port': pin,
                             'index': index, 'literal': bit, 'reason': reason or 'UNRESOLVED'})
    if len(rows) != review['summary']['unknown_ram_input_bits'] or len(rows) != 18561:
        raise ValueError('Full unknown input inventory differs')
    unresolved = [row for row in rows if row['reason'] == 'UNRESOLVED']
    # A negative control: mark an actually unused active read lane as observed.
    # The classifier must reject it instead of relying on an input-only count.
    witness = next((row for row in rows if row['reason'] in
                    ('UNUSED_LUTRAM_READ_LANE', 'UNUSED_WIDE_SDP_READ_LANE')), None)
    if witness is None:
        raise ValueError('No actual unused active-lane witness exists')
    cell = top['cells'][witness['cell']]
    output = ('DO' + witness['port'][-1] if witness['primitive'] in ('RAM32M', 'RAM64M') else
              {'DIADI': 'DOADO', 'DIBDI': 'DOBDO', 'DIPADIP': 'DOPADOP', 'DIPBDIP': 'DOPBDOP'}[witness['port']])
    output_bit = cell['connections'][output][witness['index']]
    bad_consumers = consumers | {output_bit}
    negative_pass = classify(cell, witness['port'], witness['index'], bad_consumers) is None
    if not negative_pass:
        raise ValueError('Observed-lane negative control was not rejected')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'bits.json').write_text(json.dumps(rows, indent=2) + '\n')
    libraries = Path(expand_paths('@VIVADO_ROOT@/data/verilog/src/unisims'))
    info = {'status': 'ALL_18561_DISCONNECTED_RAM_INPUT_BITS_NONOBSERVABLE_IN_MAPPED_GRAPH' if not unresolved else
            'RAM_INPUT_REVIEW_INCOMPLETE_UNRESOLVED_ACTIVE_BITS',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'review': describe(review_path),
            'mapped_graph': descriptor, 'profile': PROFILE, 'helper': describe(__file__),
            'bits': describe(out / 'bits.json'), 'input_bits': len(rows), 'unresolved': len(unresolved),
            'reason_counts': dict(sorted(Counter(row['reason'] for row in rows).items())),
            'negative_observed_lane_control_rejected': negative_pass, 'negative_witness': witness,
            'installed_libraries': {name: describe(libraries / (name + '.v'))
                                    for name in ['RAMB36E1', 'RAMB18E1', 'RAM32M', 'RAM64M']},
            'pin_mapping_source': 'https://docs.amd.com/api/khub/documents/9gZGbqBxtlKXxBfkBt~lAg/content',
            'hardware_accessed': False, 'live_jobs_changed': False, 'full_import_equivalence': False,
            'scope': 'COMPLETE_MAPPED_RAM_UNKNOWN_INPUT_OBSERVABILITY_NOT_TIMING_OR_HARDWARE_PASS'}
    (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    shutil.copy2(__file__, out / 'helper.py')
    print(json.dumps({'status': info['status'], 'input_bits': len(rows), 'unresolved': len(unresolved),
                      'reasons': info['reason_counts'], 'negative_control': negative_pass}), flush=True)
    for row in unresolved[:8]:
        print('UNRESOLVED ' + json.dumps(row), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    audit(args.review.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
