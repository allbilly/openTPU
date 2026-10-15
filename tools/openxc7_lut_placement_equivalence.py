#!/usr/bin/env python3
"""Compare original LUT logic across documented native placement fixups."""
from copy import deepcopy
import re


VCC = [['net', '$PACKER_VCC_NET']]


def canonical_lut(logical, cell, name, audit):
    if cell['type'] != 'SLICE_LUTX':
        return logical
    original = cell['attributes'].get('X_ORIG_TYPE', '')
    match = re.fullmatch(r'LUT([1-6])', original)
    result = deepcopy(logical)
    result['lut_behavior'] = {k: v for k, v in cell['attributes'].items()
                              if k in ('X_LUT_AS_DRAM', 'X_LUT_AS_SRL')}
    connections = result['connections']
    directions = result['port_directions']
    mapping = result['original_mapping']
    bel = cell['attributes'].get('NEXTPNR_BEL', '')

    # The upper half's selector is not an additional logical address/input.
    # Validate its source and actual paired 5LUT before accepting the review.
    extra_a6 = ('A6' in connections and connections['A6']
                and not mapping.get('X_ORIG_PORT_A6'))
    if extra_a6:
        if (connections['A6'] != VCC or directions.get('A6') != 'input'
                or not bel.endswith('6LUT')
                or not (original == 'RAMD32' or match and int(match[1]) <= 5)):
            raise ValueError('Unsupported extra physical A6 selector: ' + name)
        del connections['A6']
        del directions['A6']
        audit.setdefault('a6_selectors', []).append((name, bel, original))

    # Other memory/SRL cells retain strict native topology and all mappings.
    if not match:
        return result
    width = int(match[1])
    logical_ports = {f'I{i}': [] for i in range(width)}
    logical_ports['O'] = []
    logical_directions = {f'I{i}': 'input' for i in range(width)}
    logical_directions['O'] = 'output'
    assigned = set()
    physical_output = None
    for port, values in connections.items():
        names = mapping.get('X_ORIG_PORT_' + port, '').split()
        if not names:
            if values:
                raise ValueError('Connected unmapped logic LUT port: ' + name + '/' + port)
            continue
        for original_port in names:
            if original_port not in logical_ports or original_port in assigned:
                raise ValueError('Unknown or duplicate original LUT port: ' + name)
            if directions[port] != logical_directions[original_port]:
                raise ValueError('Original LUT port direction differs: ' + name)
            if len(values) > 1:
                raise ValueError('Non-scalar native LUT port: ' + name)
            logical_ports[original_port] = values
            assigned.add(original_port)
            if original_port == 'O':
                if port not in ('O5', 'O6'):
                    raise ValueError('Unsupported LUT output relocation: ' + name)
                physical_output = port
    if 'O' not in assigned:
        raise ValueError('Original LUT output mapping missing: ' + name)
    if bel and physical_output == 'O5' and not bel.endswith('5LUT'):
        raise ValueError('O5 output is not assigned to a 5LUT: ' + name)
    if bel and physical_output == 'O6' and not bel.endswith('6LUT'):
        raise ValueError('O6 output is not assigned to a 6LUT: ' + name)
    result['connections'] = logical_ports
    result['port_directions'] = logical_directions
    result['original_mapping'] = {k: v for k, v in mapping.items()
                                  if not k.startswith('X_ORIG_PORT_')}
    audit['logic_luts'] = audit.get('logic_luts', 0) + 1
    return result


def check_selectors(audit, companions, vcc_driver_count):
    if audit.get('a6_selectors') and vcc_driver_count != 1:
        raise ValueError('Exactly one verified pseudo-VCC source required')
    for name, bel, original in audit.get('a6_selectors', []):
        companion = companions.get(bel[:-4] + '5LUT')
        if companion is None:
            raise ValueError('Added A6 selector has no actual 5LUT companion: ' + name)
        kind, memory = companion
        if original == 'RAMD32':
            if not memory:
                raise ValueError('RAM A6 selector has no memory/SRL companion: ' + name)
        elif memory or not re.fullmatch(r'LUT[1-5]', kind):
            raise ValueError('Logic A6 selector has an incompatible 5LUT companion: ' + name)
