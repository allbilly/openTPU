#!/usr/bin/env python3
"""Map the full frozen FF placement to absolute sites without changing routing.

Location-class table coverage is an inventory, not numerical model validation.
Routed input-mux, slew/load, clock and full timing qualification remain pending.
"""
from __future__ import annotations

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct

from fedora_openxc7 import describe, digest

PROFILE = {'MCOLS': 4, 'ACT_ROWS': 4, 'LANES': 8, 'VPU_CL': 2,
           'MXU_IMPL': 2, 'CORE_KHZ': 100000, 'DDR_MTS': 800}
MODES = {('FDCE', 0): 16, ('FDPE', 0): 4, ('FDRE', 0): 177176,
         ('FDRE', 1): 402, ('FDSE', 0): 1701}


def checked(record):
    if describe(record['path']) != record:
        raise ValueError('Pinned input changed: ' + record['path'])
    return Path(record['path'])


def unique_rows(path, key):
    with path.open() as stream:
        rows = list(csv.DictReader(stream, delimiter='\t'))
    result = {row[key]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError('Duplicate inventory identity: ' + str(path))
    return result


def physical_bels(chipdb, constids, grid):
    """Read chipdb v6 POD fields and cross-check every fabric FF with X-Ray."""
    data = chipdb.read_bytes()

    def word(offset):
        return struct.unpack_from('<I', data, offset)[0]

    def pointer(offset):
        target = offset + struct.unpack_from('<i', data, offset)[0]
        if not 0 <= target < len(data):
            raise ValueError('Invalid relative database pointer')
        return target

    def array(offset, stride):
        start, length = pointer(offset), word(offset + 4)
        if start + length * stride > len(data):
            raise ValueError('Invalid database array extent')
        return range(start, start + length * stride, stride)

    header = pointer(0)
    if word(header) != 0x00ca7ca7 or word(header + 4) != 6:
        raise ValueError('Qualified himbaechel database v6 required')
    names = [''] + re.findall(r'^X\(([^)]+)\)', constids.read_text(), re.M)
    extra = pointer(header + 76)
    if word(extra) != len(names):
        raise ValueError('Database constids differ')
    names += [data[pointer(p):data.index(b'\0', pointer(p))].decode()
              for p in array(extra + 4, 4)]
    xray_sites = {}
    for tile, value in grid.items():
        for site, kind in value.get('sites', {}).items():
            if kind in ('SLICEL', 'SLICEM'):
                if site in xray_sites:
                    raise ValueError('Duplicate X-Ray slice site')
                xray_sites[site] = (tile, kind)
    types = list(array(header + 28, 40))
    width = word(header + 8)
    result, absolute = {}, set()
    for index, inst in enumerate(array(header + 36, 16)):
        tile_type = types[word(inst + 4)]
        bels = [p for p in array(tile_type + 4, 36) if names[word(p + 4)] == 'SLICE_FFX']
        if not bels:
            continue
        tile_extra = pointer(inst + 12)
        tx, ty = struct.unpack_from('<hh', data, tile_extra + 4)
        tile = names[word(tile_extra)] + f'_X{tx}Y{ty}'
        native_tile = names[word(inst)] + f'X{index % width}Y{index // width}'
        sites = list(array(tile_extra + 8, 24))
        for bel in bels:
            site_key = word(bel + 16)
            site = sites[(site_key >> 8) & 0xffff]
            sx, sy = struct.unpack_from('<hh', data, site + 4)
            rx, ry = struct.unpack_from('<hh', data, site + 8)
            prefix = names[word(site)]
            site_name = prefix + f'_X{sx}Y{sy}'
            variants = list(array(site + 16, 4))
            kind = names[word(variants[site_key & 0xff])]
            in_site = names[word(pointer(bel + 32))]
            local_name = names[word(bel)]
            if (prefix != 'SLICE' or not re.fullmatch(r'[A-D]5?FF', in_site)
                    or kind not in ('SLICEL', 'SLICEM')
                    or local_name != prefix + f'_X{rx}Y{ry}.' + in_site
                    or xray_sites.get(site_name) != (tile, kind)):
                raise ValueError('Native/X-Ray physical FF metadata disagree: ' + site_name)
            native = native_tile + '/' + local_name
            key = (site_name, in_site)
            if native in result or key in absolute:
                raise ValueError('Duplicate native or absolute FF BEL')
            absolute.add(key)
            result[native] = {'site': site_name, 'site_type': kind,
                              'bel_in_site': in_site, 'tile': tile}
    if {site for site, _ in absolute} != set(xray_sites) or len(absolute) != 8 * len(xray_sites):
        raise ValueError('Complete eight-BEL-per-slice database coverage differs')
    return result


def run(image_path, identity_path, table_path, out):
    image, identity, tables = [json.loads(p.read_text()) for p in (image_path, identity_path, table_path)]
    if (image['profile'] != PROFILE or identity['profile'] != PROFILE
            or identity['status'] != 'ALL_179299_NATIVE_REFERENCE_FF_IDENTITIES_MODES_POLARITIES_AND_PORT_MAPPINGS_MATCH_PHYSICAL_COVERAGE_PENDING'
            or identity['native_timing_import_permitted'] is not False
            or tables['status'] != 'ALL_85_FF_LOCATION_MODE_TABLES_PREPARED_NATIVE_IMPORT_PENDING'):
        raise ValueError('Full frozen profile and completed inventory proofs required')
    review_path = checked(image['placement_review'])
    review = json.loads(review_path.read_text())
    if (review['status'] != 'ALL_FULL_NATIVE_LOGICAL_CELLS_PHYSICAL_ASSIGNMENTS_AND_SYNC_CHAINS_PASS_ROUTE_TIMING_PENDING'
            or review['profile'] != PROFILE or review['ff_count'] != 179299):
        raise ValueError('Completed full FF placement review required')
    checked(review['placed'])
    placed = checked(review['outputs']['ff-placements.tsv'])
    identities = checked(identity['outputs']['identity-map.tsv'])
    table_file = checked(tables['outputs']['ff-timing-tables.json'])
    models = json.loads(table_file.read_text())['models']
    candidate = json.loads(checked(image['candidate']).read_text())
    source = Path(candidate['source'])
    inventory = json.loads(checked(image['planned_inputs']).read_text())
    grid = Path(image['assembly_tools']['database']) / 'xc7k480t/tilegrid.json'
    schema = [source / 'himbaechel/chipdb.h', source / 'himbaechel/uarch/xilinx/extra_data.h',
              source / 'himbaechel/uarch/xilinx/constids.inc', grid]
    for path in schema:
        if inventory.get(str(path)) != digest(path):
            raise ValueError('Pinned database schema or X-Ray grid changed')
    chipdb = checked(image['chipdb'])
    inputs = [describe(p) for p in (image_path, identity_path, table_path, review_path,
                                   placed, identities, table_file, *schema)] + [image['chipdb'], review['placed']]
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
               'inputs': inputs, 'helper': describe(__file__), 'profile': PROFILE,
               'hardware_accessed': False, 'live_backend_changed': False,
               'native_timing_import_permitted': False,
               'scope': 'ALL_179299_NATIVE_FF_ABSOLUTE_PLACEMENT_AND_LOCATION_CLASS_INVENTORY_NOT_ROUTED_INPUT_MUX_OR_NUMERICAL_TIMING'}

    def save(**fields):
        receipt.update(fields)
        (out / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')

    try:
        save()
        locations = physical_bels(chipdb, schema[2], json.loads(grid.read_text()))
        cells = unique_rows(placed, 'cell')
        reference = unique_rows(identities, 'cell')
        if len(cells) != 179299 or cells.keys() != reference.keys():
            raise ValueError('Complete FF identity coverage differs')
        model_keys = {(m['primitive'], m['clock_inverted'], m['site_type'], m['bel']): i
                      for i, m in enumerate(models) if m['site_type'] != 'UNPLACED'}
        mode_counts, location_counts = Counter(), Counter()
        records, occupied = [], set()
        for name, cell in sorted(cells.items()):
            ref = reference[name]
            mode = (cell['primitive'], int(cell['clock_inverted']))
            if mode != (ref['primitive'], int(ref['clock_inverted'])) or mode not in MODES:
                raise ValueError('FF primitive or edge differs from full identity proof')
            location = locations[cell['bel']]
            key = (*mode, location['site_type'], location['bel_in_site'])
            absolute = (location['site'], location['bel_in_site'])
            if absolute in occupied or key not in model_keys:
                raise ValueError('Duplicate occupied FF or absent characterized location class')
            occupied.add(absolute)
            mode_counts[mode] += 1
            location_counts[key] += 1
            records.append({'cell': name, 'primitive': mode[0], 'clock_inverted': mode[1],
                            'native_bel': cell['bel'], **location,
                            'location_table_index': model_keys[key],
                            'reference_site': ref['reference_loc'], 'reference_bel': ref['reference_bel'],
                            'selected_reference_sample': ref['selected_sample']})
        if dict(mode_counts) != MODES or len({r['site'] for r in records}) != review['ff_sites']:
            raise ValueError('Full mode or occupied-slice counts differ')
        fields = list(records[0])
        output = out / 'ff-absolute-sites.tsv'
        with output.open('w', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, delimiter='\t')
            writer.writeheader()
            writer.writerows(records)
        summary = {'ff_count': len(records), 'occupied_slice_sites': review['ff_sites'],
                   'database_ff_bels_crosschecked': len(locations),
                   'database_slice_sites_crosschecked': len(locations) // 8,
                   'observed_location_classes': len(location_counts),
                   'location_class_counts': [{'primitive': k[0], 'clock_inverted': k[1],
                       'site_type': k[2], 'bel': k[3], 'count': v} for k, v in sorted(location_counts.items())],
                   'selected_reference_samples': sum(bool(r['selected_reference_sample']) for r in records),
                   'routed_input_mux_and_electrical_coverage': 'PENDING_TERMINAL_NATIVE_ROUTE',
                   'full_numerical_timing_qualified': False}
        summary_file = out / 'summary.json'
        summary_file.write_text(json.dumps(summary, indent=2) + '\n')
        save(status='ALL_179299_PLACED_FF_ABSOLUTE_SITES_AND_LOCATION_CLASSES_MATCH_NATIVE_XRAY_AND_REFERENCE_IDENTITIES_ROUTE_CONTEXT_PENDING',
             summary=summary, outputs={p.name: describe(p) for p in (output, summary_file)},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': receipt['status'], 'summary': summary}, indent=2), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image-preparation', 'identity-proof', 'location-tables', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    run(args.image_preparation.resolve(), args.identity_proof.resolve(), args.location_tables.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
