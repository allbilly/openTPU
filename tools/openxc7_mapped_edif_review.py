#!/usr/bin/env python3
"""Review the completed full EDIF export with explicit metadata differences."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil

from fedora_openxc7 import describe
from openxc7_mapped_edif import TOP, PROFILE


def review(export_manifest: Path, out: Path):
    native = json.loads(export_manifest.read_text())
    root = export_manifest.parent
    if native.get('native_exit') != 0 or (root / 'export.exit').read_text().strip() != '0':
        raise ValueError('Actual completed native export required')
    if native['profile'] != PROFILE:
        raise ValueError('Full accelerator scope changed')
    for descriptor in [native['input'], native['xdc']]:
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Pinned input changed')
    before = json.loads(Path(native['input']['path']).read_text())
    after = json.loads((root / 'exported.json').read_text())
    if set(before['modules']) != set(after['modules']):
        raise ValueError('Mapped module inventory differs')
    top = before['modules'][TOP]
    removed = [n for n, c in top['cells'].items() if c['type'] == '$scopeinfo']
    if len(removed) != 4:
        raise ValueError('Scope metadata removal differs')
    for name in removed:
        del top['cells'][name]
    signed = []
    for name, wire in top['netnames'].items():
        actual = after['modules'][TOP]['netnames'].get(name)
        if actual is not None and wire.get('signed') == 1 and 'signed' not in actual:
            candidate = dict(wire)
            del candidate['signed']
            if candidate != actual:
                raise ValueError('Signed wire metadata differs beyond the known JSON reader loss')
            signed.append(name)
            del wire['signed']
    if len(signed) != 88:
        raise ValueError('Known signed-wire loss coverage changed')
    if before['modules'] != after['modules']:
        raise ValueError('Additional mapped graph changes detected')
    if any(c['type'].startswith('$') for c in top['cells'].values()):
        raise ValueError('Unmapped operator exists; signed metadata cannot be ignored')
    unknown = Counter((c['type'], pin) for c in top['cells'].values()
                      for pin, bits in c['connections'].items() for bit in bits if bit in ('x', 'z'))
    allowed = {'RAMB36E1': {'DIADI', 'DIBDI', 'DIPADIP', 'DIPBDIP'},
               'RAMB18E1': {'DIADI', 'DIBDI', 'DIPADIP', 'DIPBDIP'},
               'RAM32M': {'DIA', 'DIB', 'DIC', 'DID'},
               'RAM64M': {'DIA', 'DIB', 'DIC', 'DID'}}
    if any(pin not in allowed.get(primitive, set()) for primitive, pin in unknown):
        raise ValueError('Unexpected unknown primitive control or nonmemory input')
    out.mkdir(parents=True, exist_ok=False)
    report = {'modules': len(before['modules']), 'functional_cells': len(top['cells']),
              'primitive_counts': dict(sorted(Counter(c['type'] for c in top['cells'].values()).items())),
              'ports': len(top['ports']), 'netnames': len(top['netnames']),
              'all_functional_cells_parameters_connections_ports_attributes_and_net_bits_equal': True,
              'removed_scopeinfo': removed, 'removed_signed_wire_metadata': signed,
              'unknown_ram_input_bits': sum(unknown.values()),
              'unknown_pins': [{'primitive': p, 'port': n, 'bits': count} for (p, n), count in sorted(unknown.items())],
              'edif_unknown_policy': 'X_INPUT_BITS_LEFT_UNCONNECTED_IMPORT_REVIEW_REQUIRED'}
    (out / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    info = {'status': 'FULL_MAPPED_GRAPH_REVIEW_PASS_ONLY_EXPLICIT_METADATA_LOSS_VIVADO_LINK_PENDING',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'native_export': describe(export_manifest),
            'input': native['input'], 'xdc': native['xdc'], 'profile': PROFILE, 'helper': describe(__file__),
            'edif': describe(root / 'full.edf'), 'exported_json': describe(root / 'exported.json'),
            'comparison': describe(out / 'comparison.json'), 'summary': report,
            'hardware_accessed': False, 'live_full_jobs_changed': False,
            'imported_graph_equivalence': False, 'timing_signoff': False}
    (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    shutil.copy2(__file__, out / 'helper.py')
    print(info['status'], flush=True)
    print('FUNCTIONAL_CELLS ' + str(report['functional_cells']), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--export', dest='export_manifest', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    review(args.export_manifest.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
