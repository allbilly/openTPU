#!/usr/bin/env python3
"""Stream and inventory every surviving packed JTAG bundled-data crossing."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

from fedora_openxc7 import describe


def entries(path: Path, member: str):
    """Read entries from the single-module packed export without loading it all."""
    pattern = re.compile('"' + re.escape(member) + r'"\s*:\s*\{')
    decoder = json.JSONDecoder()
    with path.open() as stream:
        buffer = ''
        while True:
            chunk = stream.read(65536)
            if not chunk:
                raise ValueError('Missing packed object: ' + member)
            buffer += chunk
            match = pattern.search(buffer)
            if match:
                position = match.end()
                break
            buffer = buffer[-256:]

        def space():
            nonlocal buffer, position
            while True:
                while position < len(buffer) and buffer[position].isspace():
                    position += 1
                if position < len(buffer):
                    return
                chunk = stream.read(65536)
                if not chunk:
                    raise ValueError('Truncated packed object')
                buffer += chunk

        def decode():
            nonlocal buffer, position
            while True:
                try:
                    value, end = decoder.raw_decode(buffer, position)
                    position = end
                    return value
                except json.JSONDecodeError:
                    chunk = stream.read(65536)
                    if not chunk or len(buffer) - position > 16 * 1024 * 1024:
                        raise ValueError('Invalid packed record')
                    buffer += chunk

        while True:
            if position > 65536:
                buffer, position = buffer[position:], 0
            space()
            if buffer[position] == '}':
                return
            name = decode()
            space()
            if not isinstance(name, str) or buffer[position] != ':':
                raise ValueError('Invalid packed key')
            position += 1
            space()
            value = decode()
            if not isinstance(value, dict):
                raise ValueError('Invalid packed record type')
            yield name, value
            space()
            if buffer[position] == '}':
                return
            if buffer[position] != ',':
                raise ValueError('Invalid packed separator')
            position += 1


def inventory(packed_gate: Path, out: Path):
    before = json.loads(packed_gate.read_text())
    if before['status'] != 'FULL_PACK_EXPORT_PASS_DSP_PROFILE_INVENTORY_PENDING' or before['native_exit'] != 0:
        raise ValueError('Full native packing has not passed')
    source = Path(before['output'])
    pin = json.loads((packed_gate.parent / 'analysis-effective/inventory.json').read_text())
    if describe(packed_gate) != pin['pack_manifest'] or describe(source) != pin['packed_netlist']:
        raise ValueError('Pinned full packed export changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'helper': describe(__file__), 'packed_gate': describe(packed_gate), 'packed_netlist': pin['packed_netlist'],
            'profile': before['profile'], 'scope': 'COMPLETE_PACKED_MAILBOX_TOPOLOGY_NOT_ROUTE_TIMING_OR_HARDWARE_PROOF',
            'hardware_accessed': False, 'live_full_route_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='all-packed-netnames')
        pattern = re.compile(r'^(?P<base>u_mailbox\.(?:held|req|response|response_tck|rq_sync|rs_sync)|req)\[(?P<index>\d+)\]$')
        groups = defaultdict(dict)
        extra = {}
        for name, net in entries(source, 'netnames'):
            match = pattern.fullmatch(name)
            if match:
                base, index = match['base'], int(match['index'])
                if base == 'req':
                    base = 'u_mailbox.req'
                if index in groups[base]:
                    raise ValueError('Duplicate canonical mailbox bit')
                groups[base][index] = {'name': name, **net}
            elif name in ('u_mailbox.req_toggle', 'u_mailbox.rsp_toggle', 'core_clk', 'tck', '$PACKER_GND_NET', '$PACKER_VCC_NET'):
                extra[name] = net
        (out / 'nets.json').write_text(json.dumps({'groups': groups, 'extra': extra}, indent=2) + '\n')
        if not all(name in groups for name in ('u_mailbox.held', 'u_mailbox.req', 'u_mailbox.response', 'u_mailbox.response_tck', 'u_mailbox.rq_sync', 'u_mailbox.rs_sync')):
            raise ValueError('Missing canonical packed mailbox group; inspect nets.json')
        expected_indices = {
            'u_mailbox.held': set(range(572)), 'u_mailbox.req': set(range(572)),
            'u_mailbox.response': set(range(515)) | set(range(520, 536)),
            'u_mailbox.response_tck': set(range(515)) | set(range(520, 536)),
            'u_mailbox.rq_sync': set(range(3)), 'u_mailbox.rs_sync': set(range(3))}
        if any(set(groups[group]) != indices for group, indices in expected_indices.items()):
            raise ValueError('Full mailbox live bit coverage differs from the audited profile')
        bit_refs = defaultdict(list)
        for group, bits in groups.items():
            for index, value in bits.items():
                for bit in value['bits']:
                    if isinstance(bit, int):
                        bit_refs[bit].append((group, index))
        selected, drivers, users = {}, defaultdict(list), defaultdict(list)
        types = Counter()
        save(stage='all-packed-cells', net_groups={name: len(bits) for name, bits in groups.items()})
        for name, cell in entries(source, 'cells'):
            types[cell['type']] += 1
            relevant = False
            for port, bits in cell['connections'].items():
                direction = cell['port_directions'][port]
                for bit in bits:
                    if bit in bit_refs:
                        relevant = True
                        entry = {'cell': name, 'port': port, 'type': cell['type'], 'direction': direction}
                        (drivers if direction == 'output' else users)[bit].append(entry)
            if relevant:
                selected[name] = cell
        crossings = []
        for source_group, capture_group, source_clock, capture_clock in [
                ('u_mailbox.held', 'u_mailbox.req', 'tck', 'core_clk'),
                ('u_mailbox.response', 'u_mailbox.response_tck', 'core_clk', 'tck')]:
            if set(groups[source_group]) != set(groups[capture_group]):
                raise ValueError('Packed source/capture payload index sets differ: ' + source_group)
            for index, net in sorted(groups[capture_group].items()):
                if len(net['bits']) != 1:
                    raise ValueError('Packed payload is not scalar')
                bit = net['bits'][0]
                owners = drivers[bit]
                if len(owners) != 1 or owners[0]['type'] != 'SLICE_FFX' or owners[0]['port'] != 'Q':
                    raise ValueError('Payload capture lacks a unique FF driver')
                capture_name = owners[0]['cell']
                capture = selected[capture_name]
                source_bit = groups[source_group][index]['bits']
                if capture['connections']['D'] != source_bit or capture['connections']['CK'] != extra[capture_clock]['bits']:
                    raise ValueError('Payload capture is not the matching direct source bit')
                owners = drivers[source_bit[0]]
                if len(owners) != 1 or owners[0]['type'] != 'SLICE_FFX' or owners[0]['port'] != 'Q':
                    raise ValueError('Payload source lacks a unique FF driver')
                source_name = owners[0]['cell']
                if selected[source_name]['connections']['CK'] != extra[source_clock]['bits']:
                    raise ValueError('Payload source clock differs')
                if (selected[source_name]['parameters'].get('IS_C_INVERTED', '0').strip('0') or
                        capture['parameters'].get('IS_C_INVERTED', '0').strip('0')):
                    raise ValueError('Payload has an unexpected falling-edge register')
                crossings.append({'direction': source_group + '->' + capture_group, 'index': index,
                                  'source_cell': source_name, 'source_port': 'Q', 'source_net': groups[source_group][index]['name'],
                                  'capture_cell': capture_name, 'capture_port': 'D', 'capture_net': net['name'],
                                  'source_clock': source_clock, 'capture_clock': capture_clock,
                                  'source_ff': selected[source_name], 'capture_ff': capture})
        chains = {}
        for group, clock in [('u_mailbox.rq_sync', 'core_clk'), ('u_mailbox.rs_sync', 'tck')]:
            stages = []
            for index in range(3):
                net = groups[group][index]
                bit = net['bits'][0]
                owner = drivers[bit]
                if (len(owner) != 1 or owner[0]['type'] != 'SLICE_FFX' or owner[0]['port'] != 'Q'
                        or net['attributes'].get('ASYNC_REG') != 'TRUE'):
                    raise ValueError('Synchronizer stage or annotation missing')
                cell = selected[owner[0]['cell']]
                if cell['connections']['CK'] != extra[clock]['bits'] or cell['parameters'].get('IS_C_INVERTED', '0').strip('0'):
                    raise ValueError('Synchronizer clock or edge differs')
                if index:
                    if cell['connections']['D'] != groups[group][index - 1]['bits']:
                        raise ValueError('Synchronizer chain connection differs')
                if index < 2:
                    following = drivers[groups[group][index + 1]['bits'][0]]
                    if users[bit] != [{'cell': following[0]['cell'], 'port': 'D', 'type': 'SLICE_FFX', 'direction': 'input'}]:
                        raise ValueError('An early synchronizer stage escapes to other logic')
                stages.append({'index': index, 'cell': owner[0]['cell'], 'net': net['name'],
                               'clock': clock, 'users': users[bit], 'ff': cell})
            chains[group] = stages
        (out / 'synchronizer-chains.json').write_text(json.dumps(chains, indent=2) + '\n')
        (out / 'payload-crossings.json').write_text(json.dumps(crossings, indent=2) + '\n')
        (out / 'selected-cells.json').write_text(json.dumps(selected, indent=2) + '\n')
        (out / 'payload-users.json').write_text(json.dumps({str(bit): value for bit, value in users.items()}, indent=2) + '\n')
        shutil.copy2(__file__, out / 'helper.py')
        counts = dict(Counter(row['direction'] for row in crossings))
        save(status='COMPLETE_PACKED_MAILBOX_PAYLOAD_AND_SYNCHRONIZER_TOPOLOGY_PASS_TIMING_PENDING',
             packed_cell_types=dict(types), selected_cells=len(selected), payload_crossings=len(crossings), direction_counts=counts,
             payloads=describe(out / 'payload-crossings.json'), nets=describe(out / 'nets.json'),
             synchronizer_chains=describe(out / 'synchronizer-chains.json'),
             optimized_fields={'request': 'unused magic bits 572..603',
                               'response': 'constant status bits 515..519 and magic bits 536..567'},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'payload_crossings': len(crossings), 'directions': counts}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--packed-gate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    inventory(args.packed_gate.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
