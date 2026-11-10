#!/usr/bin/env python3
"""Qualify reproduced primitive graphs and independently inspect clock frame bits."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path

from fedora_openxc7 import describe, digest


DISABLED_SETTINGS = {
    'xilinx/phase-engine-vivado': '0' * 32,
    'xilinx/phase-domain-audit': ' ',
    'xilinx/mailbox-datapath-active': '0' * 32,
    'xilinx/phase-intrinsic-probe': '0 ',
}


def review(native: Path, out: Path):
    raw = json.loads(native.read_text())
    if raw['status'] != 'NATIVE_ROUTES_AND_STRICT_FRAMES_PASS_CHANGED_GRAPHS_REQUIRE_VALIDATION':
        raise ValueError('Completed actual primitive routes and strict frames required')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'native_gate': describe(native), 'binary': raw['binary'], 'chipdb': raw['chipdb'],
            'helper': describe(__file__), 'hardware_accessed': False, 'full_board_timing': 'NOT_QUALIFIED',
            'scope': 'EXACT_NATIVE_PRIMITIVE_GRAPH_CONFIGURATION_AND_RESTORED_CLOCK_BITS', 'results': {}}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        selection = json.loads(Path(raw['previous_selection']['path']).read_text())
        strict = json.loads(Path(selection['correction_strict_receipt']['path']).read_text())
        jobs = {j['gate']: j for j in strict['jobs']}
        for name, result in raw['results'].items():
            for item in [result['previous_manifest'], result['routed'], result['fasm'],
                         raw['assemblies'][name]['frames'], jobs[name]['frames']]:
                if describe(item['path']) != item:
                    raise ValueError('Native or qualified original artifact changed')
            previous = Path(result['previous_manifest']['path']).parent
            prefix = 'corrected' if name == 'ff_edge_probe' else 'route'
            command = json.loads((previous / (prefix + '.command.json')).read_text())
            old_path = Path(command[command.index('--write') + 1])
            old = json.loads(old_path.read_text())
            new = json.loads(Path(result['routed']['path']).read_text())
            settings_changes = {}
            if old['modules'].keys() != new['modules'].keys():
                raise ValueError('Primitive module set changed')
            for module in old['modules']:
                a, b = old['modules'][module]['settings'], new['modules'][module]['settings']
                changed = {k for k in a.keys() | b.keys() if a.get(k) != b.get(k)}
                if changed != DISABLED_SETTINGS.keys():
                    raise ValueError('Unexpected primitive reporting or tool settings changed')
                for key, expected in DISABLED_SETTINGS.items():
                    if key in a or b.get(key) != expected:
                        raise ValueError('Reporting setting is not the verified disabled default')
                    settings_changes[key] = {'old': None, 'new': b.pop(key)}
            if old != new or not result['fasm_byte_identical']:
                raise ValueError('Actual primitive graph or configuration differs')
            if digest(raw['assemblies'][name]['frames']['path']) != jobs[name]['frames']['sha256']:
                raise ValueError('Actual primitive configuration frames differ')
            info['results'][name] = {'routed_graph_equal': True, 'fasm_byte_identical': True,
                                     'frames_byte_identical': True, 'disabled_reporting_settings': settings_changes,
                                     'previous_functional_gate': result['previous_manifest']}
            if name == 'ff_edge_probe':
                old_report = Path(command[command.index('--report') + 1])
                new_report = native.parent / name / old_report.name
                if json.loads(old_report.read_text()) != json.loads(new_report.read_text()):
                    raise ValueError('Actual full/half-period FF timing report changed')
                info['results'][name]['full_half_period_report_equal'] = True
                info['results'][name]['timing_report'] = describe(new_report)

        clock = raw['assemblies']['clock_fixture']
        for item in clock.values():
            if isinstance(item, dict) and describe(item['path']) != item:
                raise ValueError('Clock frame witness changed')
        database = Path(raw['assembly_tools']['database'])
        grid = json.loads((database / 'xc7k480t/tilegrid.json').read_text())
        features = {}
        for line in (database / 'segbits_clk_hrow_top_r.db').read_text().splitlines():
            fields = line.split()
            if fields:
                features[fields[0]] = fields[1:]
        records = []
        for line in Path(clock['fasm']['path']).read_text().splitlines():
            if '.CLK_HROW_TOP_R_CK_BUFG_CASCO' not in line or '.CLK_HROW_TOP_R_CK_BUFG_CASCIN' not in line:
                continue
            tile, feature = line.split('.', 1)
            tile_data = grid[tile]
            bits = tile_data['bits']['CLB_IO_CLK']
            for token in features[tile_data['type'] + '.' + feature]:
                active = not token.startswith('!')
                frame, offset = map(int, token.lstrip('!').split('_'))
                records.append({'feature': line, 'frame': int(bits['baseaddr'], 16) + frame,
                                'word': bits['offset'] + offset // 32, 'bit': offset % 32,
                                'expected': int(active)})
        if len({r['feature'] for r in records}) != 12:
            raise ValueError('All 12 restored cascade feature records are required')
        required = {r['frame'] for r in records}
        frames = {}
        with Path(clock['frames']['path']).open() as stream:
            for line in stream:
                address, words = line.split()
                address = int(address, 16)
                if address in required:
                    if address in frames:
                        raise ValueError('Duplicate inspected frame address')
                    frames[address] = [int(w, 16) for w in words.split(',')]

        def bits_match(values):
            return all(r['frame'] in values and len(values[r['frame']]) == 101
                       and (values[r['frame']][r['word']] >> r['bit']) & 1 == r['expected'] for r in records)

        if not bits_match(frames):
            raise ValueError('Restored physical clock cascade bits are absent or wrong')
        corrupt = {a: list(words) for a, words in frames.items()}
        first = records[0]
        corrupt[first['frame']][first['word']] ^= 1 << first['bit']
        if bits_match(corrupt):
            raise ValueError('Clock bit verifier accepted a flipped cascade bit')
        (out / 'clock-frame-bits.json').write_text(json.dumps(records, indent=2) + '\n')
        save(status='FIVE_EXACT_PRIMITIVE_GRAPHS_FRAMES_AND_RESTORED_CLOCK_BITS_PASS',
             clock_bits={'features': 12, 'unique_physical_bits': len({(r['frame'], r['word'], r['bit']) for r in records}),
                         'all_match': True, 'flipped_bit_rejected': True,
                         'report': describe(out / 'clock-frame-bits.json')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    review(args.native.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
