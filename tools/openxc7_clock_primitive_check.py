#!/usr/bin/env python3
"""Re-run exact primitive witnesses with the corrected clock backend/database."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest, configuration
from openxc7_route_wire_memory import run
from fedora_check_jtag_image import select_jtag_backend


def check(full_gate: Path, previous_selection: Path, clock_gate: Path, out: Path, workers: int,
          candidate: Path | None = None, replay_fixture: Path | None = None):
    full = json.loads(full_gate.read_text())
    selected = json.loads(previous_selection.read_text())
    clock = json.loads(clock_gate.read_text())
    if (full['status'] != 'FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS'
            or clock['status'] != 'ALL_54_DEDICATED_CLOCK_ARCS_AND_NATIVE_CLOCK_FIXTURE_MAIN_ROUTE_PASS'
            or full['clock_gate'] != describe(clock_gate)
            or selected['backend_validation'] != 'EXACT_CORRECTION_RECEIPTS_V1'):
        raise ValueError('Completed full/clock gates and original exact primitive selection required')
    for item in [full['binary'], full['chipdb'], selected['correction_strict_receipt']]:
        if describe(item['path']) != item:
            raise ValueError('Pinned executable/database/strict receipt changed')
    binary = full['binary']
    candidate_proof = {}
    if candidate is not None or replay_fixture is not None:
        if candidate is None or replay_fixture is None:
            raise ValueError('Candidate and completed replay fixture are required together')
        backend = json.loads(candidate.read_text())
        replay = json.loads(replay_fixture.read_text())
        if (backend['status'] != 'PLACED_REPLAY_BACKEND_BUILD_PASS_FIXTURE_PENDING'
                or backend['parent_binary'] != full['binary']
                or backend['source_delta'] != ['himbaechel/uarch/xilinx/xilinx.cc']
                or replay['status'] != 'PLACED_REPLAY_CLOCKS_MATRIX_CACHE_BINDINGS_AND_NATIVE_ROUTE_PASS_FULL_ROUTE_PENDING'
                or replay['candidate'] != describe(candidate)
                or replay.get('timing_domain_budgets_identical') is not True):
            raise ValueError('Exact isolated candidate and model-enabled replay qualification differ')
        if describe(backend['binary']['path']) != backend['binary']:
            raise ValueError('Candidate executable changed')
        binary = backend['binary']
        candidate_proof = {'candidate': describe(candidate), 'replay_fixture': describe(replay_fixture),
                           'full_timing_contract_parent_binary': full['binary']}
    select_jtag_backend(previous_selection)
    strict = json.loads(Path(selected['correction_strict_receipt']['path']).read_text())
    prior_jobs = {job['gate']: job for job in strict['jobs']}
    names = ('carry_probe', 'upper_carry_probe', 'cascade_probe', 'ff_edge_probe', 'mux_probe')
    if set(prior_jobs) != set(names) or strict['status'] != 'STRICT_FRAMES_PASS':
        raise ValueError('Original primitive gates are incomplete')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'full_gate': describe(full_gate), 'clock_gate': describe(clock_gate),
            'previous_selection': describe(previous_selection), 'binary': binary,
            'chipdb': full['chipdb'], 'workers': workers, 'helper': describe(__file__),
            'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'EXACT_PRIMITIVE_ROUTES_CONFIGURATION_AND_PRIOR_GRAPH_EQUIVALENCE_NOT_BOARD_TIMING',
            'results': {}, **candidate_proof}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    cfg = configuration()
    env = dict(os.environ, PYTHONPATH=str(cfg['xray']), OTPU_XRAY_DB=str(cfg['database']))

    def native(name):
        previous = selected[name]['manifest']
        if describe(previous['path']) != previous:
            raise ValueError('Original primitive witness changed')
        root = Path(previous['path']).parent
        prefix = 'corrected' if name == 'ff_edge_probe' else 'route'
        argv = json.loads((root / (prefix + '.command.json')).read_text())
        if argv[0] != selected['corrected_backend']['binary']['path']:
            raise ValueError('Original native witness executable differs')
        target = out / name
        target.mkdir()
        inputs = {}
        for flag in ('--json',):
            inputs[argv[argv.index(flag) + 1]] = describe(argv[argv.index(flag) + 1])
        xdc = next(a.split('=', 1)[1] for a in argv if a.startswith('xdc='))
        inputs[xdc] = describe(xdc)
        old_routed = Path(argv[argv.index('--write') + 1])
        old_fasm = Path(next(a.split('=', 1)[1] for a in argv if a.startswith('fasm=')))
        previous_manifest = json.loads(Path(previous['path']).read_text())
        for path in (old_routed, old_fasm):
            pinned = [item for item in previous_manifest['artifacts'].values()
                      if Path(item['path']) == path]
            if len(pinned) != 1 or describe(path) != pinned[0]:
                raise ValueError('Original qualified graph/configuration changed')
        argv[0] = binary['path']
        argv[argv.index('--chipdb') + 1] = full['chipdb']['path']
        for flag in ('--write', '--report'):
            if flag in argv:
                index = argv.index(flag) + 1
                argv[index] = str(target / Path(argv[index]).name)
        for index, arg in enumerate(argv):
            if arg.startswith('fasm='):
                argv[index] = 'fasm=' + str(target / old_fasm.name)
        print('EXACT_PRIMITIVE_NATIVE_STARTED ' + name, flush=True)
        code, elapsed = run(target, 'native', argv)
        if code:
            raise RuntimeError(name + ' native route failed: ' + str(code))
        for item in inputs.values():
            if describe(item['path']) != item:
                raise ValueError('Primitive fixture changed during route')
        routed = target / old_routed.name
        fasm = target / old_fasm.name
        result = {'native_exit': code, 'elapsed_seconds': elapsed, 'inputs': inputs,
                  'previous_manifest': previous, 'routed': describe(routed), 'fasm': describe(fasm),
                  'routed_byte_identical': digest(routed) == digest(old_routed),
                  'fasm_byte_identical': digest(fasm) == digest(old_fasm)}
        if not (result['routed_byte_identical'] and result['fasm_byte_identical']):
            result['functional_evidence'] = 'CHANGED_GRAPH_REQUIRES_FRESH_VALIDATION'
        else:
            result['functional_evidence'] = 'PREVIOUS_FUNCTIONAL_GATE_EXACT_ROUTED_GRAPH_AND_FASM_REPRODUCED'
        (target / 'native-comparison.json').write_text(json.dumps(result, indent=2) + '\n')
        return name, result

    try:
        save(stage='actual-native-primitive-routes')
        with ThreadPoolExecutor(max_workers=workers) as pool:
            info['results'] = dict(pool.map(native, names))
        save(stage='strict-frame-assembly')
        template = json.loads(Path(prior_jobs[names[0]]['command']['path']).read_text())
        if template[template.index('--db-root') + 1] != str(cfg['database']):
            raise ValueError('Strict frame database differs from qualified original')
        info['assembly_tools'] = {'python': describe(template[0]), 'assembler': describe(template[1]),
                                  'database': str(cfg['database']), 'xray': str(cfg['xray'])}
        fasm_inputs = {name: Path(row['fasm']['path']) for name, row in info['results'].items()}
        fasm_inputs['clock_fixture'] = Path(clock['outputs']['clock.fasm']['path'])
        assemblies = {}
        for name, fasm in fasm_inputs.items():
            target = out / name
            target.mkdir(exist_ok=True)
            frames = target / 'probe.frames'
            argv = [*template[:-2], str(fasm), str(frames)]
            # The strict assembler imports the same pinned X-Ray Python library.
            (target / 'strict-frames.command.json').write_text(json.dumps(argv, indent=2) + '\n')
            with (target / 'strict-frames.log').open('w') as log:
                code = subprocess.run(argv, cwd=target, env=env, stdout=log, stderr=subprocess.STDOUT).returncode
            (target / 'strict-frames.exit').write_text(str(code) + '\n')
            if code or not frames.is_file() or not frames.stat().st_size:
                raise RuntimeError(name + ' strict frame assembly failed')
            assemblies[name] = {'exit': code, 'fasm': describe(fasm), 'frames': describe(frames)}
        changed = [name for name, row in info['results'].items()
                   if row['functional_evidence'] == 'CHANGED_GRAPH_REQUIRES_FRESH_VALIDATION']
        if describe(binary['path']) != binary:
            raise ValueError('Primitive executable changed during qualification')
        if candidate_proof and any(describe(item['path']) != item for item in
                                   (candidate_proof['candidate'], candidate_proof['replay_fixture'])):
            raise ValueError('Candidate or replay qualification changed during primitive checks')
        save(status=('ALL_FIVE_EXACT_PRIMITIVE_ROUTES_AND_SIX_STRICT_FRAME_ASSEMBLIES_PASS'
                     if not changed else 'NATIVE_ROUTES_AND_STRICT_FRAMES_PASS_CHANGED_GRAPHS_REQUIRE_VALIDATION'),
             assemblies=assemblies, changed_graphs=changed,
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'changed_graphs': changed}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('full-gate', 'previous-selection', 'clock-gate', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, choices=(1, 2), default=2)
    parser.add_argument('--candidate', type=Path)
    parser.add_argument('--replay-fixture', type=Path)
    args = parser.parse_args()
    check(args.full_gate.resolve(), args.previous_selection.resolve(), args.clock_gate.resolve(),
          args.out.resolve(), args.workers, args.candidate.resolve() if args.candidate else None,
          args.replay_fixture.resolve() if args.replay_fixture else None)


if __name__ == '__main__':
    main()
