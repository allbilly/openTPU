#!/usr/bin/env python3
"""Adopt an existing full JTAG route, then assemble and independently check it.

Never launches synthesis, placement, Vivado or hardware programming. A live
route is a wait condition, not permission to assemble incomplete output.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from fedora_openxc7 import PART, ROOT, configuration, describe, digest, run
from fedora_openxc7_pcie_pipeline import FULL, read, recorded, require, unchanged, write
from fedora_check_jtag_image import TOP, select_jtag_backend, synthesis_witness
from fedora_check_pcie_image import STRUCTURE_CHECKER

PREPARED = 'FULL_JTAG_EXISTING_ROUTE_FINALIZATION_PREPARED'
WAITING = 'WAITING_FOR_LIVE_FULL_JTAG_ROUTE'
ASSEMBLED = 'FULL_CONFIGURATION_ASSEMBLY_PASS_TIMING_QUALIFICATION_INCOMPLETE'
ROUTED = 'ROUTE_PASS_TIMING_QUALIFICATION_INCOMPLETE'
IDENTITY = ('action', 'part', 'parameters', 'litedram', 'source',
            'constraint_source', 'primitive_libraries', 'vref_adapter',
            'helper_sha256', 'tools', 'logic_mapping', 'route_threads')


def now():
    return datetime.now(timezone.utc).isoformat()


def process(pid):
    directory = Path('/proc') / str(pid)
    fields = (directory / 'stat').read_text().split(') ', 1)[1].split()
    require(fields[0] not in ('Z', 'X'), 'Route process is terminal')
    return dict(pid=pid, ppid=int(fields[1]), start_ticks=int(fields[19]),
                boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),
                executable=os.readlink(directory / 'exe'),
                cwd=os.readlink(directory / 'cwd'),
                command=[s.decode() for s in (directory / 'cmdline').read_bytes().split(b'\0') if s])


def live(owner):
    try:
        observed = process(owner['pid'])
    except (OSError, ValueError):
        return None
    return observed if observed == owner else None


def route_identity(info, route):
    require({key:route.get(key) for key in IDENTITY} == info['route_identity'],
            'Adopted route inputs, tools or configuration changed')
    require(route.get('action') == 'jtag-route' and route.get('part') == PART
            and route.get('parameters') == FULL, 'Wrong full standalone route')
    require(route['tools']['nextpnr'] == info['corrected_backend']['binary']
            and route['tools']['chipdb'] == info['chipdb'], 'Route backend/database differs')


def prepare(out, route, selection, route_pid):
    out.mkdir(parents=True, exist_ok=False)
    info = dict(status='RUNNING', stage='prepare', started_utc=now(),
                timing='NOT_QUALIFIED', physical_hardware='NOT_RUN',
                programming='NOT_RUN', flash_written=False)
    mp = out / 'pipeline.json'
    try:
        selected = read(selection)
        require(selected.get('backend_validation') == 'EXACT_CORRECTION_RECEIPTS_V1',
                'Adoption requires the exact merged-backend correction receipts')
        backend, _, inventory = select_jtag_backend(selection)
        info.update(selected)
        info.update(status='RUNNING', stage='prepare', adopted_route_directory=str(route))
        counts = synthesis_witness(info)
        synthesis = read(Path(info['synthesis_directory']) / 'manifest.json')
        rm = read(route / 'manifest.json')
        info['route_identity'] = {key:rm.get(key) for key in IDENTITY}
        route_identity(info, rm)
        require(rm.get('status') in ('RUNNING', ROUTED), 'Route failed or was interrupted')
        require(rm['source'] == synthesis['source']
                and rm['constraint_source'] == synthesis['constraint_source']
                and rm['primitive_libraries'] == synthesis['primitive_libraries']
                and rm['litedram'] == synthesis['litedram'], 'Route differs from full synthesis inputs')
        require(rm['litedram']['manifest'] == str(Path(info['litedram_core']) / 'openxc7-profile.json'),
                'Route used a different generated DDR core')
        require(rm['helper_sha256'] == digest(ROOT / 'tools/fedora_openxc7.py'),
                'Route controller source changed since launch')

        # Verify the entire actual graph, permitting only the two MMCM LOC
        # attributes applied by the recorded route controller.
        design = read(info['mapped_checkpoint']['path'])
        cells = design['modules'][TOP]['cells']
        locs = {'u_ld.ldmmcm0':'MMCME2_ADV_X0Y2', 'u_ld.ldmmcm1':'MMCME2_ADV_X0Y6'}
        for name, loc in locs.items():
            require(cells[name]['type'] == 'MMCME2_ADV', 'Missing DDR write-clock MMCM')
            cells[name]['attributes']['LOC'] = loc
        expected = hashlib.sha256((json.dumps(design) + '\n').encode()).hexdigest()
        del design, cells
        require(digest(route / 'constrained.json') == expected,
                'Route input differs from full mapped graph plus the two MMCM LOCs')
        info['netlist_transform'] = dict(status='FULL_GRAPH_AND_ONLY_TWO_MMCM_LOCS_VERIFIED',
                                       mapped=info['mapped_checkpoint'],
                                       constrained=describe(route / 'constrained.json'), locs=locs)
        command = read(route / 'route.command.json')
        require(command[0] == backend['binary']['path'], 'Route command used a different executable')
        for flag, value in (('--json', str(route / 'constrained.json')),
                            ('--chipdb', info['chipdb']['path']), ('--device', PART),
                            ('--threads', str(rm['route_threads'])),
                            ('--report', str(route / 'timing.json')),
                            ('--write', str(route / 'routed.json'))):
            require(command.count(flag) == 1 and command[command.index(flag)+1] == value,
                    'Route command differs: ' + flag)
        require('xdc=' + str(route / 'openxc7.xdc') in command
                and 'fasm=' + str(route / 'design.raw.fasm') in command,
                'Route command uses different constraints or output')
        info['route_command'] = command
        if rm['status'] == 'RUNNING':
            require(route_pid is not None, 'Live adoption requires the exact nextpnr PID')
            owner = process(route_pid)
            require(owner['command'] == command and owner['executable'] == backend['binary']['path'],
                    'Live route process does not match the recorded command')
            helper = process(owner['ppid'])
            require(helper['cwd'] == str(ROOT) and 'jtag-route' in helper['command']
                    and str(route) in helper['command'], 'Route controller owner differs')
            info['route_owners'] = dict(nextpnr=owner, controller=helper)
        else:
            info['route_owners'] = {}

        cfg = configuration()
        for name in ('chipdb', 'frames2bit', 'fasm2frames'):
            require(describe(cfg[name]) == rm['tools'][name], 'Assembly tool differs from route: ' + name)
        plan = read(route / 'vref-plan.json')
        require(set(plan['inputs']) == {rm['constraint_source']['path'],
                    str(cfg['database'] / PART / 'package_pins.csv'),
                    str(cfg['database'] / 'xc7k480t/tilegrid.json')}, 'Route VREF database differs')
        inventory.update(plan['inputs'])
        inventory.update(rm['source'])
        inventory.update(rm['primitive_libraries'])
        for item in (describe(selection), info['adopted_synthesis_manifest'],
                     info['mapped_checkpoint'], rm['constraint_source'], rm['vref_adapter']):
            recorded(item)
            inventory[item['path']] = item['sha256']
        for name in ('constrained.json', 'openxc7.xdc', 'route.command.json',
                     'vref-plan.json', 'constraint-audit.json', 'hard-cell-timing-audit.json'):
            path = route / name
            inventory[str(path)] = digest(path)
        for name in ('fedora_finalize_jtag_route.py', 'fedora_check_jtag_image.py',
                     'fedora_check_pcie_image.py', 'fedora_openxc7_pcie_pipeline.py',
                     'fedora_openxc7.py', 'fedora_prepare_litedram.py',
                     'fedora_pcie_constraints.py', 'openxc7_vref.py',
                     'openxc7_chipdb_audit.py', 'openxc7_fasm2frames.py'):
            path = ROOT / 'tools' / name
            inventory[str(path)] = digest(path)
        inventory[str(STRUCTURE_CHECKER)] = digest(STRUCTURE_CHECKER)
        python = (cfg['fasm2frames'].parent / 'python').resolve()
        info['assembly_tools'] = dict(python=describe(python),
                                     frames2bit=describe(cfg['frames2bit']),
                                     interpreter=describe(sys.executable),
                                     database=str(cfg['database']), xray=str(cfg['xray']))
        for key in ('python', 'frames2bit', 'interpreter'):
            item = info['assembly_tools'][key]
            inventory[item['path']] = item['sha256']
        for path in cfg['database'].rglob('*'):
            if path.is_file():
                inventory[str(path)] = digest(path)
        for directory in ('prjxray', 'utils'):
            for path in (cfg['xray'] / directory).rglob('*.py'):
                inventory[str(path)] = digest(path)
        shutil.copyfile(__file__, out / 'finalizer-source.py')
        inventory[str(out / 'finalizer-source.py')] = digest(out / 'finalizer-source.py')
        unchanged(inventory)
        info.update(status=PREPARED, stage='prepared', configuration=FULL,
                    mapped_counts=dict(counts), planned_inputs=inventory, updated_utc=now())
        write(out / 'prepared.json', info)
        info['preparation'] = describe(out / 'prepared.json')
        write(mp, info)
        return 0
    except BaseException as error:
        info.update(status='FAIL', error=str(error), updated_utc=now())
        write(mp, info)
        raise


def adopt_artifacts(route, out, rm):
    require((route / 'route.exit').read_text().strip() == '0', 'Native route did not exit zero')
    needed = {'constrained.json', 'openxc7.xdc', 'routed.json', 'timing.json',
              'design.raw.fasm', 'design.fasm', 'vref-audit.json'}
    require(needed <= set(rm.get('artifacts', {})), 'Route lacks complete outputs')
    target = out / 'route'
    target.mkdir(exist_ok=False)
    adopted = dict(rm)
    adopted['adopted_original_manifest'] = describe(route / 'manifest.json')
    adopted['artifacts'] = {}
    for name, item in rm['artifacts'].items():
        require(Path(name).name == name and Path(item['path']).resolve() == route / name,
                'Unexpected route artifact path')
        recorded(item)
        require(item['bytes'] > 0, 'Empty route artifact: ' + name)
        try:
            os.link(route / name, target / name)
        except OSError as error:
            if error.errno != errno.EXDEV:
                raise
            shutil.copyfile(route / name, target / name)
        adopted['artifacts'][name] = describe(target / name)
    write(target / 'manifest.json', adopted)
    return adopted


def assemble(out):
    mp = out / 'pipeline.json'
    current = read(mp)
    require(current['status'] in (PREPARED, WAITING), 'Finalization already ran or failed; use a new directory')
    recorded(current['preparation'])
    info = read(current['preparation']['path'])
    info['preparation'] = current['preparation']

    def save(**fields):
        info.update(fields, updated_utc=now())
        write(mp, info)

    try:
        unchanged(info['planned_inputs'])
        route = Path(info['adopted_route_directory'])
        rm = read(route / 'manifest.json')
        route_identity(info, rm)
        if rm['status'] == 'RUNNING':
            observed = {name:identity for name, owner in info['route_owners'].items()
                        if (identity := live(owner)) is not None}
            if observed:
                save(status=WAITING, stage='wait-route', live_owners=observed,
                     observed_route_status=rm['status'])
                return 2
            # The route can finish between the first read and the owner check.
            rm = read(route / 'manifest.json')
            route_identity(info, rm)
        require(rm['status'] == ROUTED, 'Route has no successful terminal result: ' + rm['status'])
        adopted = adopt_artifacts(route, out, rm)
        inventory = info['planned_inputs']
        for item in [adopted['adopted_original_manifest'], describe(out / 'route/manifest.json'),
                     describe(route / 'route.exit'), *adopted['artifacts'].values()]:
            inventory[item['path']] = item['sha256']
        frames, bit = out / 'design.frames', out / 'design.bit'
        require(not frames.exists() and not bit.exists(), 'Assembly output already exists')
        tools = info['assembly_tools']
        database = Path(tools['database'])
        env = dict(os.environ, PYTHONPATH=tools['xray'], OTPU_XRAY_DB=str(database))
        unchanged(inventory)
        save(status='RUNNING', stage='strict-frames')
        run([tools['python']['path'], str(ROOT / 'tools/openxc7_fasm2frames.py'),
             '--db-root', str(database), '--part', PART, str(out / 'route/design.fasm')],
            out, 'strict-frames', env, frames)
        require(frames.is_file() and frames.stat().st_size > 0, 'Strict assembler produced no frames')
        unchanged(inventory)
        save(stage='frames-to-bit')
        run([tools['frames2bit']['path'], '--part_file=' + str(database / PART / 'part.yaml'),
             '--part_name=' + PART, '--frm_file=' + str(frames), '--output_file=' + str(bit)],
            out, 'frames-to-bit', env)
        require(bit.is_file() and bit.stat().st_size > 0, 'Bitstream assembler produced no output')
        unchanged(inventory)
        save(status=ASSEMBLED, stage='assembled', artifacts={p.name:describe(p) for p in (frames, bit)})
        # Freeze the pipeline presented to the independent checker. Its receipt
        # must not point to a heartbeat/stage file that changes after checking.
        snapshot = out / 'assembled.pipeline.json'
        require(not snapshot.exists(), 'Assembled snapshot already exists')
        write(snapshot, info)
        run([tools['interpreter']['path'], str(ROOT / 'tools/fedora_check_jtag_image.py'),
             '--pipeline', str(snapshot), '--out', str(out / 'independent-image-check.json')],
            out, 'independent-image-check', env)
        unchanged(inventory)
        save(status=ASSEMBLED, stage='independently-checked',
             assembled_snapshot=describe(snapshot),
             independent_check=describe(out / 'independent-image-check.json'))
        return 0
    except BaseException as error:
        save(status='FAIL', error=str(error))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('prepare', 'assemble'))
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--route', type=Path)
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--route-pid', type=int)
    args = parser.parse_args()
    if args.action == 'prepare' and (not args.route or not args.selection):
        parser.error('prepare requires --route and --selection')
    out = args.out.resolve()
    try:
        if args.action == 'prepare':
            result = prepare(out, args.route.resolve(), args.selection.resolve(), args.route_pid)
        else:
            # Prevent two finalizers from writing the same output concurrently.
            with (out / '.assembly.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                result = assemble(out)
        print(read(out / 'pipeline.json')['status'])
        print(out / 'pipeline.json')
        return result
    except Exception as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
