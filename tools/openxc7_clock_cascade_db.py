#!/usr/bin/env python3
"""Build a controlled K480T chipdb pair for verified top clock cascade PIPs."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys

from fedora_openxc7 import describe, digest
from openxc7_bufg_route_guard import replace_once
from openxc7_route_wire_memory import run


def build(backend: Path, xray: Path, assembler: Path, installed: Path, out: Path):
    parent = json.loads(backend.read_text())
    if parent['status'] != 'CLOCK_ROUTE_DIAGNOSTIC_BUILD_PASS_NATIVE_QUERY_PENDING':
        raise ValueError('Completed diagnostic parent required')
    inventory = json.loads(Path(parent['source_inventory']['path']).read_text())
    original = Path(parent['source'])
    if any(digest(original / name) != value for name, value in inventory.items()):
        raise ValueError('Pinned generator source changed')
    if describe(parent['binary']['path']) != parent['binary']:
        raise ValueError('Pinned native diagnostic changed')

    family = xray / 'kintex7'
    tile = json.loads((family / 'tile_type_CLK_HROW_TOP_R.json').read_text())
    features = {}
    for line in (family / 'segbits_clk_hrow_top_r.db').read_text().splitlines():
        fields = line.split()
        if fields:
            features[fields[0]] = fields[1:]
    selected = []
    for index in range(32):
        source = f'CLK_HROW_TOP_R_CK_BUFG_CASCIN{index}'
        destination = f'CLK_HROW_TOP_R_CK_BUFG_CASCO{index}'
        name = f'CLK_HROW_TOP_R.{source}->>{destination}'
        pip = tile['pips'][name]
        feature = f'CLK_HROW_TOP_R.{destination}.{source}'
        if pip['is_directional'] != '1' or pip['is_pseudo'] != '0' or not features.get(feature):
            raise ValueError('Unverified cascade connection: ' + name)
        selected.append({'pip': name, 'feature': feature, 'bits': features[feature]})

    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'parent': describe(backend), 'assembler': describe(assembler),
            'installed_database': describe(installed), 'xray': str(xray),
            'xray_revision': subprocess.check_output(['git', '-C', str(xray), 'rev-parse', 'HEAD'], text=True).strip(),
            'helper': describe(__file__), 'restored_tile_type': 'CLK_HROW_TOP_R',
            'restored_pips_per_tile': len(selected), 'hardware_accessed': False,
            'live_full_jobs_changed': False, 'scope': 'CONTROLLED_K480T_CLOCK_CONNECTIVITY_DATABASE_PAIR',
            'variants': {}}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        (out / 'restored-pips.json').write_text(json.dumps(selected, indent=2) + '\n')
        for variant in ('stock', 'fixed'):
            work = out / variant
            work.mkdir()
            source = work / 'source'
            shutil.copytree(original, source)
            copied = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
            if copied != inventory:
                raise ValueError('Source copy differs from pinned parent')
            if variant == 'fixed':
                filters = source / 'himbaechel/uarch/xilinx/gen/filters.py'
                old = ('    if tile_type.startswith("CLK_HROW_TOP"):\n'
                       '        if "CK_BUFG_CASCO" in p.dst_wire().name() and "CK_BUFG_CASCIN" in p.src_wire().name():\n'
                       '            return False')
                new = ('    if tile_type.startswith("CLK_HROW_TOP"):\n'
                       '        if "CK_BUFG_CASCO" in p.dst_wire().name() and "CK_BUFG_CASCIN" in p.src_wire().name():\n'
                       '            # Verified K480T directional cascade channels with known segbits.\n'
                       '            if tile_type == "CLK_HROW_TOP_R":\n'
                       '                for channel in range(32):\n'
                       '                    if (p.src_wire().name() == f"CLK_HROW_TOP_R_CK_BUFG_CASCIN{channel}" and\n'
                       '                            p.dst_wire().name() == f"CLK_HROW_TOP_R_CK_BUFG_CASCO{channel}"):\n'
                       '                        return True\n'
                       '            return False')
                filters.write_text(replace_once(filters.read_text(), old, new))
                updated = {str(p.relative_to(source)): digest(p) for p in source.rglob('*') if p.is_file()}
                changes = sorted(n for n in updated if updated[n] != inventory.get(n))
                if changes != ['himbaechel/uarch/xilinx/gen/filters.py']:
                    raise ValueError('Unrelated generator changes')
            else:
                updated, changes = copied, []
            (work / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
            bba = work / 'chipdb-xc7k480t.bba'
            binary = work / 'chipdb-xc7k480t.bin'
            generator = source / 'himbaechel/uarch/xilinx/gen/xilinx_gen.py'
            argv = [sys.executable, str(generator), '--xray', str(family), '--device', 'xc7k480t',
                    '--metadata', str(source / 'himbaechel/uarch/xilinx/meta/kintex7'),
                    '--constids', str(source / 'himbaechel/uarch/xilinx/constids.inc'), '--bba', str(bba)]
            info['variants'][variant] = {'stage': 'generator', 'source_changes': changes}
            save(stage=variant + '-generation')
            print('CHIPDB_GENERATION_STARTED ' + variant + ' ' + str(work), flush=True)
            code, elapsed = run(work, 'generator', argv)
            if code != 0 or not bba.is_file():
                raise RuntimeError(variant + ' generator failed: ' + str(code))
            info['variants'][variant].update(generator_exit=code, generator_seconds=elapsed, bba=describe(bba))
            save(stage=variant + '-assembly')
            code, elapsed = run(work, 'assembler', [str(assembler), '--le', str(bba), str(binary)])
            if code != 0 or not binary.is_file():
                raise RuntimeError(variant + ' assembler failed: ' + str(code))
            info['variants'][variant].update(assembler_exit=code, assembler_seconds=elapsed,
                                             binary=describe(binary), source_inventory=describe(work / 'source.input.json'))
            if variant == 'stock' and digest(binary) != info['installed_database']['sha256']:
                raise ValueError('Stock database does not reproduce the installed baseline')
            save()
            print('CHIPDB_VARIANT_COMPLETE ' + variant + ' ' + digest(binary), flush=True)
        if digest(installed) != info['installed_database']['sha256']:
            raise ValueError('Installed database changed')
        if info['variants']['fixed']['binary']['sha256'] == info['variants']['stock']['binary']['sha256']:
            raise ValueError('Fixed database unexpectedly identical to stock')
        save(status='STOCK_DATABASE_REPRODUCED_FIXED_CASCADE_DATABASE_BUILD_PASS_NATIVE_QUERY_PENDING',
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('backend', 'xray', 'assembler', 'installed', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    build(*(getattr(args, name).resolve() for name in ('backend', 'xray', 'assembler', 'installed', 'out')))


if __name__ == '__main__':
    main()
