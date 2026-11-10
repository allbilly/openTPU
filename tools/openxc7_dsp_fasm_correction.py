#!/usr/bin/env python3
"""Preserve native routing while applying independently checked DSP FASM bits."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import struct

from fedora_openxc7 import describe
from openxc7_mailbox_inventory import entries


FIELDS = {'ZAREG_2_ACASCREG_1', 'ZBREG_2_BCASCREG_1', 'ZADREG[0]',
          'ZDREG[0]', 'USE_DPORT[0]', 'MASK[45:0]'}
PREFIX = re.compile(r'^([^\.\s]+\.DSP48\.DSP_[01])\.(.*)$')
PROFILE = {'MCOLS': 4, 'ACT_ROWS': 4, 'LANES': 8, 'VPU_CL': 2,
           'MXU_IMPL': 2, 'CORE_KHZ': 100000, 'DDR_MTS': 800}


def target(line):
    match = PREFIX.fullmatch(line.strip())
    if not match:
        return None
    prefix, suffix = match.groups()
    field = suffix.split(' = ', 1)[0]
    if field not in FIELDS:
        if field.startswith('MASK['):
            raise ValueError('Unexpected DSP MASK syntax: ' + line.strip())
        return None
    return prefix, suffix


def vectors(path):
    result = {}
    for line in path.read_text().splitlines():
        item = target(line)
        if item:
            prefix, suffix = item
            # Both native writers emit USE_DPORT twice. Preserve the exact
            # observed multiplicity instead of inventing a stricter grammar.
            result.setdefault(prefix, []).append(suffix)
    return {k: sorted(v) for k, v in result.items()}


def rewrite(source, records):
    observed = vectors(source)
    expected = {r['prefix']: r['old'] for r in records}
    if len(expected) != len(records) or observed != expected:
        raise ValueError('Actual old DSP target features differ from native witnesses')
    original = source.read_text()
    preserved = ''.join(line for line in original.splitlines(keepends=True) if not target(line))
    if preserved and not preserved.endswith('\n'):
        raise ValueError('Native FASM must end in a newline')
    replacement = ''.join(r['prefix'] + '.' + suffix + '\n'
                          for r in sorted(records, key=lambda r: r['prefix']) for suffix in r['new'])
    return preserved + replacement


def signature(params):
    values = {k: int(params[k], 2) for k in ('AREG', 'ACASCREG', 'BREG', 'BCASCREG', 'ADREG', 'DREG')}
    if params['USE_DPORT'] not in ('TRUE', 'FALSE'):
        raise ValueError('Unexpected USE_DPORT encoding')
    values.update(USE_DPORT=params['USE_DPORT'] == 'TRUE', MASK_present='MASK' in params)
    if int(params.get('MASK', '0011' + '1' * 44), 2) != (1 << 46) - 1:
        raise ValueError('Full profile MASK differs from qualified modes')
    return json.dumps(values, sort_keys=True)


def grid_sites(grid):
    result = {}
    for tile, data in grid.items():
        for site, kind in data.get('sites', {}).items():
            if kind == 'DSP48E1':
                result[site] = tile + '.DSP48.DSP_' + str(int(site.rsplit('Y', 1)[1]) % 2)
    return result


def native_dsp_sites(chipdb, constids, sites):
    """Check internal BEL names against actual Xilinx tile/site metadata."""
    data = chipdb.read_bytes()
    word = lambda p: struct.unpack_from('<I', data, p)[0]

    def pointer(p):
        target = p + struct.unpack_from('<i', data, p)[0]
        if not 0 <= target < len(data):
            raise ValueError('Invalid chipdb relative pointer')
        return target

    def array(p, stride):
        start, length = pointer(p), word(p + 4)
        if start + length * stride > len(data):
            raise ValueError('Invalid chipdb array')
        return range(start, start + length * stride, stride)

    header = pointer(0)
    if word(header) != 0x00ca7ca7 or word(header + 4) != 6:
        raise ValueError('Expected qualified himbaechel chipdb v6')
    names = [''] + re.findall(r'^X\(([^)]+)\)', constids.read_text(), re.M)
    extra = pointer(header + 76)
    if word(extra) != len(names):
        raise ValueError('Chipdb constids differ')
    names += [data[pointer(p):data.index(b'\0', pointer(p))].decode() for p in array(extra + 4, 4)]
    types = list(array(header + 28, 40))
    width = word(header + 8)
    result = {}
    for index, inst in enumerate(array(header + 36, 16)):
        tile_type = types[word(inst + 4)]
        bels = [p for p in array(tile_type + 4, 36) if names[word(p + 4)] == 'DSP48E1_DSP48E1']
        if not bels:
            continue
        tile_extra = pointer(inst + 12)
        tx, ty = struct.unpack_from('<hh', data, tile_extra + 4)
        xilinx_tile = names[word(tile_extra)] + f'_X{tx}Y{ty}'
        tile_sites = list(array(tile_extra + 8, 24))
        native_tile = names[word(inst)] + f'X{index % width}Y{index // width}'
        for bel in bels:
            site = tile_sites[(word(bel + 16) >> 8) & 0xffff]
            sx, sy = struct.unpack_from('<hh', data, site + 4)
            site_name = names[word(site)] + f'_X{sx}Y{sy}'
            prefix = xilinx_tile + '.DSP48.DSP_' + str(sy % 2)
            if sites.get(site_name) != prefix:
                raise ValueError('Native chipdb and X-Ray DSP site mapping differ')
            native_bel = native_tile + '/' + names[word(bel)]
            if native_bel in result:
                raise ValueError('Duplicate native DSP BEL')
            result[native_bel] = {'site': site_name, 'prefix': prefix}
    if len(result) != 1920:
        raise ValueError('Complete native DSP site map required')
    return result


def save(out, data):
    (out / 'manifest.json').write_text(json.dumps(data, indent=2) + '\n')


def prepare(old_gate, new_gate, frame_gate, impact, placement_review, image_preparation, grid, out):
    old, new, frames, review, image = [json.loads(p.read_text()) for p in
                                     (old_gate, new_gate, frame_gate, placement_review, image_preparation)]
    if (old['status'] != 'OLD_AND_NEW_NATIVE_SIX_MODE_CELLS_PLACEMENT_ROUTED_NETS_IDENTICAL_PASS_FASM_DIFFERENTIAL_PENDING'
            or new['status'] != 'ALL_SIX_FULL_PROFILE_REGISTER_MASK_MODES_NATIVE_EMISSION_AND_STRICT_FRAMES_PASS_VIVADO_FRAME_COMPARISON_PENDING'
            or frames['status'] != 'SIX_REGISTER_MASK_NATIVE_FRAME_CONFIGURATIONS_MATCH_VIVADO_REFERENCE_PASS_FULL_IMAGE_PENDING'
            or frames['vendor_cells_compared'] != 717 or frames['mismatching_reference_cells'] != 0
            or review['status'] != 'ALL_FULL_NATIVE_LOGICAL_CELLS_PHYSICAL_ASSIGNMENTS_AND_SYNC_CHAINS_PASS_ROUTE_TIMING_PENDING'
            or image['status'] != 'FULL_PLACED_REPLAY_SOURCE_AND_ASSEMBLY_INPUTS_PREPARED_WAITING_FOR_ROUTE'
            or image['placement_review'] != describe(placement_review)
            or image['profile'] != PROFILE or review['profile'] != PROFILE):
        raise ValueError('Completed native differential, vendor frame and full-placement proofs required')
    candidate = json.loads(Path(image['candidate']['path']).read_text())
    constids = Path(candidate['source']) / 'himbaechel/uarch/xilinx/constids.inc'
    frozen = [describe(p) for p in (old_gate, new_gate, frame_gate, impact, placement_review, image_preparation, grid, constids)]
    frozen += [image['candidate'], image['chipdb']]
    frozen += list(old['outputs'].values()) + list(new['outputs'].values()) + [frames['comparison'], review['placed']]
    frozen += old['inputs'] + new['inputs'] + frames['inputs']
    frozen = list({r['path']: r for r in frozen}.values())
    for item in frozen:
        if describe(item['path']) != item:
            raise ValueError('Pinned qualification input changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'inputs': frozen, 'helper': describe(__file__), 'image_preparation': describe(image_preparation),
            'profile': PROFILE, 'hardware_accessed': False, 'live_route_changed': False,
            'scope': 'NATIVE_DIFFERENTIAL_FASM_CORRECTION_AND_FULL_717_DSP_SITE_MAP_NOT_COMPLETED_FULL_IMAGE'}
    save(out, info)
    try:
        sites = grid_sites(json.loads(grid.read_text()))
        native_sites = native_dsp_sites(Path(image['chipdb']['path']), constids, sites)
        original = json.loads(Path(old['outputs']['routed.json']['path']).read_text())['modules']['top']
        updated = json.loads(Path(new['outputs']['routed.json']['path']).read_text())['modules']['top']
        for key in ('cells', 'netnames', 'ports'):
            if original[key] != updated[key]:
                raise ValueError('Native old/new fixture graph differs: ' + key)
        old_vectors, new_vectors = [vectors(Path(g['outputs']['probe.fasm']['path'])) for g in (old, new)]
        modes, fixture = {}, []
        for name, cell in original['cells'].items():
            if cell['type'] != 'DSP48E1_DSP48E1':
                continue
            prefix = sites[cell['attributes']['NEXTPNR_BEL'].split('/')[0]]
            mode = {'old': old_vectors[prefix], 'new': new_vectors[prefix]}
            key = signature(cell['parameters'])
            if key in modes and modes[key] != mode:
                raise ValueError('One mode has inconsistent native target emission')
            modes[key] = mode
            fixture.append({'cell': name, 'prefix': prefix, **mode})
        if len(modes) != 6 or len(fixture) != 64:
            raise ValueError('Incomplete actual native mode coverage')
        transformed = rewrite(Path(old['outputs']['probe.fasm']['path']), fixture)
        actual = Path(new['outputs']['probe.fasm']['path']).read_text()
        features = lambda s: sorted(line.strip() for line in s.splitlines() if line.strip() and not line.startswith('#'))
        if features(transformed) != features(actual):
            raise ValueError('Corrected old FASM differs from actual new native FASM')
        # Real old native input with one missing register bit must be rejected.
        damaged = out / 'negative-missing-feature.fasm'
        lines = Path(old['outputs']['probe.fasm']['path']).read_text().splitlines(keepends=True)
        counts = Counter(target(line) for line in lines if target(line))
        index = next(i for i, line in enumerate(lines) if target(line) and counts[target(line)] == 1)
        damaged.write_text(''.join(lines[:index] + lines[index + 1:]))
        try:
            rewrite(damaged, fixture)
        except ValueError:
            negative_rejected = True
        else:
            raise ValueError('Damaged old FASM accepted')
        (out / 'fixture-corrected.fasm').write_text(transformed)
        full = {r['cell']: r for r in json.loads(impact.read_text())}
        if len(full) != 717 or any(r['inversion_differences'] for r in full.values()):
            raise ValueError('Full design has uncovered DSP inversion differences')
        records, scanned = [], 0
        for name, cell in entries(Path(review['placed']['path']), 'cells'):
            scanned += 1
            if cell['type'] != 'DSP48E1_DSP48E1':
                continue
            if name not in full or cell['parameters'] != full[name]['parameters']:
                raise ValueError('Full placed DSP parameters differ from frozen impact review')
            bel = cell['attributes']['NEXTPNR_BEL']
            if bel not in native_sites:
                raise ValueError('Full-placement DSP BEL absent from qualified native chipdb')
            site, prefix = native_sites[bel]['site'], native_sites[bel]['prefix']
            key = signature(cell['parameters'])
            if key not in modes:
                raise ValueError('Unqualified full design mode')
            records.append({'cell': name, 'site': site, 'prefix': prefix, 'mode': key, **modes[key]})
        if scanned != 464200 or len(records) != 717 or len({r['prefix'] for r in records}) != 717:
            raise ValueError('Full cell/site coverage differs')
        (out / 'full-dsp-map.json').write_text(json.dumps(records, indent=2) + '\n')
        for item in frozen:
            if describe(item['path']) != item:
                raise ValueError('Input changed during preparation')
        info.update(status='NATIVE_DIFFERENTIAL_FASM_REPRODUCTION_AND_FULL_717_DSP_CORRECTION_MAP_PASS_ROUTE_PENDING',
                    full_cells_scanned=scanned, full_dsps=len(records), fixture_dsps=len(fixture),
                    mode_population=dict(Counter(r['mode'] for r in records)),
                    all_native_noncomment_features_reproduced=True, missing_target_feature_rejected=negative_rejected,
                    outputs={n: describe(out / n) for n in ('full-dsp-map.json', 'fixture-corrected.fasm')})
        save(out, info)
        print(info['status'], flush=True)
    except Exception as exc:
        info.update(status='FAIL', error=repr(exc))
        save(out, info)
        raise


def correct(prepared, out):
    proof = json.loads(prepared.read_text())
    if proof['status'] != 'NATIVE_DIFFERENTIAL_FASM_REPRODUCTION_AND_FULL_717_DSP_CORRECTION_MAP_PASS_ROUTE_PENDING':
        raise ValueError('Completed native differential and full DSP map required')
    if proof['helper'] != describe(__file__):
        raise ValueError('Qualified correction helper changed')
    image = json.loads(Path(proof['image_preparation']['path']).read_text())
    route = Path(image['route_directory'])
    terminal = json.loads((route / 'manifest.json').read_text())
    if terminal['status'] == 'RUNNING':
        print('WAITING_FOR_VERIFIED_TERMINAL_FULL_ROUTE', flush=True)
        return 2
    if (terminal['status'] != 'FULL_PLACED_REPLAY_NATIVE_ROUTE_AND_CLOCK_DRIVER_GATE_PASS_IMAGE_TIMING_PENDING'
            or terminal['native_exit'] != 0 or (route / 'route.exit').read_text().strip() != '0'
            or terminal['binary'] != image['binary'] or terminal['chipdb'] != image['chipdb']
            or terminal['profile'] != PROFILE or terminal['physical_assignments'] != 464198
            or terminal['mailbox_limits_reimported'] != 1103
            or terminal['restored_domain_gate'] != {'domain_pairs': 18, 'known': 16, 'unknown': 2, 'budgets_identical': True}):
        raise ValueError('Successful unchanged full native route required')
    frozen = proof['inputs'] + list(proof['outputs'].values()) + list(terminal['outputs'].values())
    for item in frozen:
        if describe(item['path']) != item:
            raise ValueError('Full route/correction provenance changed')
    source = Path(terminal['outputs']['design.raw.fasm']['path'])
    records = json.loads(Path(proof['outputs']['full-dsp-map.json']['path']).read_text())
    transformed = rewrite(source, records)
    out.mkdir(parents=True, exist_ok=False)
    target_path = out / 'design.dsp-corrected.raw.fasm'
    target_path.write_text(transformed)
    for item in frozen:
        if describe(item['path']) != item:
            raise ValueError('Input changed during correction')
    result = {'status': 'FULL_717_DSP_TARGET_FASM_CORRECTION_PASS_STRICT_IMAGE_AND_TIMING_PENDING',
              'preparation': describe(prepared), 'terminal_route': describe(route / 'manifest.json'),
              'original_fasm': describe(source), 'corrected_fasm': describe(target_path),
              'helper': describe(__file__), 'full_dsps': 717, 'all_other_lines_preserved': True,
              'profile': PROFILE, 'hardware_accessed': False, 'numerical_timing': 'NOT_QUALIFIED'}
    save(out, result)
    print(result['status'], flush=True)
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='action', required=True)
    prep = sub.add_parser('prepare')
    for name in ('old-gate', 'new-gate', 'frame-gate', 'impact', 'placement-review', 'image-preparation', 'grid', 'out'):
        prep.add_argument('--' + name, type=Path, required=True)
    correction = sub.add_parser('correct')
    for name in ('prepared', 'out'):
        correction.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    values = {k: v.resolve() for k, v in vars(args).items() if k != 'action'}
    if args.action == 'prepare':
        prepare(**values)
        return 0
    return correct(**values)


if __name__ == '__main__':
    raise SystemExit(main())
