#!/usr/bin/env python3
"""Read actual XC7 DSP site geometry and compare cascade placement rules."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import struct


def inspect(chipdb, constids):
    data = Path(chipdb).read_bytes()

    def word(offset, signed=False):
        return struct.unpack_from('<i' if signed else '<I', data, offset)[0]

    def pointer(offset):
        target = offset+word(offset, True)
        if not 0 <= target < len(data):
            raise ValueError('Invalid chipdb relative pointer')
        return target

    def array(offset, stride):
        start, length = pointer(offset), word(offset+4)
        if start+length*stride > len(data):
            raise ValueError('Invalid chipdb array bounds')
        return range(start, start+length*stride, stride)

    header = pointer(0)
    if word(header) != 0x00ca7ca7 or word(header+4) != 6:
        raise ValueError('Expected himbaechel chipdb v6')
    names = ['']+re.findall(r'^X\(([^)]+)\)', Path(constids).read_text(), re.M)
    extra = pointer(header+76)
    if word(extra) != len(names):
        raise ValueError('Constids differ from this chipdb')
    names += [data[pointer(p):data.index(b'\0', pointer(p))].decode()
              for p in array(extra+4, 4)]
    types = list(array(header+28, 40))
    instances = list(array(header+36, 16))
    width, height = word(header+8), word(header+12)
    sites = {}
    locations = {}
    for index, inst in enumerate(instances):
        tile_type = types[word(inst+4)]
        bels = [b for b in array(tile_type+4, 36) if names[word(b+4)] == 'DSP48E1_DSP48E1']
        if not bels:
            continue
        tile_extra = pointer(inst+12)
        tile_sites = list(array(tile_extra+8, 24))
        for bel in bels:
            site = tile_sites[(word(bel+16) >> 8) & 0xffff]
            site_x, site_y = struct.unpack_from('<hh', data, site+4)
            z = struct.unpack_from('<h', data, bel+8)[0]
            record = dict(site_x=site_x, site_y=site_y, tile_x=index % width,
                          tile_y=index//width, z=z, tile_type=names[word(tile_type)],
                          site_name=f'{names[word(site)]}_X{site_x}Y{site_y}')
            if (site_x, site_y) in sites:
                raise ValueError('Duplicate absolute DSP site')
            sites[site_x, site_y] = record
            locations[record['tile_x'], record['tile_y'], z] = record
    roots = [s for s in sites.values() if s['z'] == 6]
    counts = {}
    for length in (2, 4, 8, 16, 32):
        fixed = sum(all((s['tile_x'], s['tile_y']-5*(k//2), 6 if k%2==0 else 25)
                        in locations for k in range(length)) for s in roots)
        actual = sum(all((s['site_x'], s['site_y']+k) in sites for k in range(length)) for s in roots)
        counts[str(length)] = dict(fixed_five_row_roots=fixed, consecutive_site_roots=actual)
    steps = Counter()
    for s in roots:
        nxt = sites.get((s['site_x'], s['site_y']+2))
        if nxt:
            steps[s['tile_y']-nxt['tile_y']] += 1
    candidates = []
    # Several root phases in each DSP tile orientation, all crossing an
    # intervening clock row. These are real sites for constrained route probes.
    for tile_type in ('DSP_L', 'DSP_R'):
        matches = [s for s in roots if s['tile_type'] == tile_type and
                   all((s['site_x'], s['site_y']+k) in sites for k in range(16)) and
                   any(sites[s['site_x'], s['site_y']+k]['tile_y']-
                       sites[s['site_x'], s['site_y']+k+2]['tile_y'] == 6
                       for k in range(0, 14, 2))]
        matches.sort(key=lambda s:(s['site_x'], s['site_y']))
        chosen = []
        for s in matches:
            if len(chosen) == 2:
                break
            if chosen and s['site_y'] < chosen[-1]['site_y']+20:
                continue
            chosen.append(s)
        if len(chosen) != 2:
            raise ValueError('Missing crossing probe candidates for '+tile_type)
        candidates += chosen
    return dict(status='GEOMETRY_AUDIT_PASS_ROUTING_NOT_TESTED',
                chipdb=str(Path(chipdb).resolve()), chipdb_sha256=hashlib.sha256(data).hexdigest(),
                constids=str(Path(constids).resolve()),
                constids_sha256=hashlib.sha256(Path(constids).read_bytes()).hexdigest(),
                grid=dict(width=width, height=height), dsp_sites=len(sites), lower_roots=len(roots),
                pair_tile_row_steps=dict(sorted(steps.items())), placement_candidates=counts,
                crossing_probe_roots=candidates,
                scope='Database geometry only; dedicated cascade routing, bitstream, timing and hardware are not proven')


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chipdb', type=Path, required=True)
    ap.add_argument('--constids', type=Path, required=True)
    ap.add_argument('--output', type=Path, required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('Use a new output path')
    report = inspect(args.chipdb, args.constids)
    args.output.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('constids', 'scope')}, indent=2))
