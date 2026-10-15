#!/usr/bin/env python3
"""Review a completed full native placement; retain route/timing qualification."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

from fedora_openxc7 import describe, digest
from openxc7_full_congestion_placement import PROFILE
from openxc7_mailbox_inventory import entries
from openxc7_lut_placement_equivalence import canonical_lut, check_selectors


def sync_locations(selected):
    if len(selected) != 3:
        raise ValueError('Exactly three synchronizer FF stages required')
    locations = [c['attributes'].get('NEXTPNR_BEL', '') for c in selected]
    if (any(c['type'] != 'SLICE_FFX' or c['attributes'].get('ASYNC_REG') != 'TRUE'
            for c in selected)
            or any(not re.fullmatch(r'X\d+Y\d+/SLICE_X\d+Y\d+\.[A-D]FF', b) for b in locations)
            or len(set(locations)) != 3
            or len({b.rsplit('.', 1)[0] for b in locations}) != 1):
        raise ValueError('Actual same-slice primary-FF synchronizer placement differs')
    return locations


def signals(path):
    result = {}
    for name, net in entries(path, 'netnames'):
        bits = net['bits']
        if len(bits) != 1 or type(bits[0]) is not int or bits[0] in result:
            raise ValueError('Expected unique single-bit native net records')
        result[bits[0]] = name
    if not result:
        raise ValueError('Native net inventory empty')
    return result


def signatures(path, lut_audit=None):
    """Normalize native wire IDs and unique serialized unconnected bits."""
    names = signals(path)
    highest_net = max(names)
    unconnected = set()

    def bits(values):
        result = []
        for bit in values:
            if type(bit) is not int:
                raise ValueError('Unsupported native wire encoding')
            if bit in names:
                result.append(['net', names[bit]])
            else:
                # jsonwrite.cc emits unique IDs beyond all interned names
                # for disconnected/gap bits. Never merge a reused wire ID.
                if bit <= highest_net or bit in unconnected:
                    raise ValueError('Missing or reused native signal')
                unconnected.add(bit)
                result.append(['unconnected'])
        return result

    ports = {}
    for name, port in entries(path, 'ports'):
        if name in ports:
            raise ValueError('Duplicate top port')
        ports[name] = {'direction': port['direction'], 'offset': port.get('offset', 0),
                       'bits': bits(port['bits'])}
    yield 'ports', ports
    seen = set()
    for name, cell in entries(path, 'cells'):
        if name in seen:
            raise ValueError('Duplicate native cell')
        seen.add(name)
        logical = {'type': cell['type'], 'parameters': cell['parameters'],
                   'port_directions': cell['port_directions'],
                   'connections': {p: bits(v) for p, v in cell['connections'].items()},
                   'original_mapping': {k: v for k, v in cell['attributes'].items()
                                        if k.startswith('X_ORIG_')}}
        if lut_audit is not None:
            if cell['type'] == 'PSEUDO_VCC':
                outputs = [b for port, values in logical['connections'].items()
                           if logical['port_directions'][port] == 'output' for b in values]
                lut_audit.setdefault('vcc_drivers', []).append(outputs)
            logical = canonical_lut(logical, cell, name, lut_audit)
        encoded = json.dumps(logical, sort_keys=True, separators=(',', ':')).encode()
        yield 'cell', (name, hashlib.sha256(encoded).hexdigest(), cell)


def review(trial, out):
    m = json.loads(trial.read_text())
    if m['status'] == 'RUNNING':
        print('PLACEMENT_PENDING: no result reviewed and no output directory created')
        return 2
    if m['status'] != 'FULL_CONGESTION_PLACEMENT_NATIVE_COMPLETE_REVIEW_PENDING' or m.get('native_exit') != 0:
        raise ValueError('Actual completed native placement required')
    if (trial.parent / 'placement.exit').read_text().strip() != '0' or m['profile'] != PROFILE:
        raise ValueError('Native exit or full profile differs')
    required = [m['binary'], m['chipdb'], m['source_proof'],
                *m['full_inputs'].values(), *m['outputs'].values()]
    for record in required:
        if describe(record['path']) != record:
            raise ValueError('Completed placement input or output changed')
    source = json.loads(Path(m['source_proof']['path']).read_text())
    if len(source['source']) != 31 or any(digest(p) != v for p, v in source['source'].items()):
        raise ValueError('Original 31 source files changed')
    contract = json.loads(Path(m['full_inputs']['mailbox-contract']['path']).read_text())
    baseline_record = contract['packed_netlist']
    if describe(baseline_record['path']) != baseline_record:
        raise ValueError('Contract-linked complete packed baseline changed')
    packed = Path(baseline_record['path'])
    pack_gate = packed.parent / 'manifest.json'
    p = json.loads(pack_gate.read_text())
    if (p['native_exit'] != 0 or p['profile'] != PROFILE or p['output'] != str(packed)
            or p['status'] != 'FULL_PACK_EXPORT_PASS_DSP_PROFILE_INVENTORY_PENDING'
            or any(p['inputs'][k] != m['full_inputs'][k] for k in ('constrained.json', 'openxc7.xdc'))):
        raise ValueError('Full packed baseline provenance differs')
    placed = Path(m['outputs']['placed.json']['path'])
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'stage': 'all-native-logical-cells-and-physical-bindings',
            'created_utc': datetime.now(timezone.utc).isoformat(), 'trial': describe(trial),
            'packed_gate': describe(pack_gate), 'packed': baseline_record,
            'placed': m['outputs']['placed.json'], 'helper': describe(__file__),
            'stream_helper': describe(Path(__file__).with_name('openxc7_mailbox_inventory.py')),
            'lut_equivalence_helper': describe(Path(__file__).with_name('openxc7_lut_placement_equivalence.py')),
            'profile': PROFILE, 'hardware_accessed': False, 'live_native_job_changed': False,
            'routing_complete': False, 'timing_signoff': False,
            'scope': 'FULL_NATIVE_LOGICAL_PRESERVATION_AND_PLACEMENT_NOT_ROUTE_OR_TIMING_SIGNOFF'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        baseline, base_types, ports = {}, Counter(), None
        base_audit, placed_audit = {}, {}
        for kind, record in signatures(packed, base_audit):
            if kind == 'ports':
                ports = record
            else:
                name, value, cell = record
                baseline[name] = value
                base_types[cell['type']] += 1
        if base_types['SLICE_FFX'] != 179299:
            raise ValueError('Complete baseline FF scope differs')
        placed_types, bels, sync_cells = Counter(), set(), {}
        wanted_sync = {s['cell'] for c in contract['synchronizers'] for s in c['stages']}
        if len(wanted_sync) != 6:
            raise ValueError('Two complete three-stage synchronizers required')
        ff_sites = Counter()
        companions = {}
        with (out / 'ff-placements.tsv').open('w') as stream:
            stream.write('cell\tbel\tprimitive\tclock_inverted\n')
            for kind, record in signatures(placed, placed_audit):
                if kind == 'ports':
                    if record != ports:
                        raise ValueError('Full top-port topology changed')
                    continue
                name, value, cell = record
                if baseline.pop(name, None) != value:
                    raise ValueError('Cell identity, type, parameter, mapping or connection changed: ' + name)
                typ, attrs = cell['type'], cell['attributes']
                placed_types[typ] += 1
                bel = attrs.get('NEXTPNR_BEL', '')
                if typ not in ('PSEUDO_GND', 'PSEUDO_VCC'):
                    if not bel or bel in bels:
                        raise ValueError('Missing or duplicate native physical assignment: ' + name)
                    bels.add(bel)
                if typ == 'SLICE_LUTX' and bel.endswith('5LUT'):
                    companions[bel] = (attrs.get('X_ORIG_TYPE', ''),
                                       attrs.get('X_LUT_AS_DRAM', '').strip() == '1'
                                       or attrs.get('X_LUT_AS_SRL', '').strip() == '1')
                if typ == 'SLICE_FFX':
                    if len(bel.split('/')) != 2:
                        raise ValueError('Unsupported native FF physical assignment')
                    ff_sites[bel.rsplit('.', 1)[0]] += 1
                    stream.write('\t'.join((name, bel, attrs['X_ORIG_TYPE'],
                                            cell['parameters'].get('IS_C_INVERTED', '0').strip())) + '\n')
                if name in wanted_sync:
                    sync_cells[name] = cell
        if baseline or placed_types != base_types:
            raise ValueError('Complete native cell inventory changed')
        if placed_audit.get('vcc_drivers') != [[['net', '$PACKER_VCC_NET']]]:
            raise ValueError('Exactly one pseudo-VCC source must drive the selector net')
        check_selectors(placed_audit, companions, 1)
        sync = {}
        for chain in contract['synchronizers']:
            selected = [sync_cells[s['cell']] for s in chain['stages']]
            sync[chain['name']] = sync_locations(selected)
        if describe(packed) != baseline_record or describe(placed) != m['outputs']['placed.json']:
            raise ValueError('Native comparison files changed during review')
        save(status='ALL_FULL_NATIVE_LOGICAL_CELLS_PHYSICAL_ASSIGNMENTS_AND_SYNC_CHAINS_PASS_ROUTE_TIMING_PENDING',
             cell_count=sum(base_types.values()), cell_types=dict(base_types),
             physical_bels=len(bels), ff_count=179299, ff_sites=len(ff_sites),
             synchronizers=sync, outputs={'ff-placements.tsv': describe(out / 'ff-placements.tsv')},
             lut_equivalence={'baseline_logic_luts': base_audit.get('logic_luts', 0),
                              'placed_logic_luts': placed_audit.get('logic_luts', 0),
                              'validated_added_a6_selectors': len(placed_audit.get('a6_selectors', [])),
                              'parameter_changes_permitted': False,
                              'original_logical_connections_preserved': True},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'])
        return 0
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--trial', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(review(args.trial.resolve(), args.out.resolve()))


if __name__ == '__main__':
    main()
