#!/usr/bin/env python3
"""Export the complete mapped OpenXC7 graph to EDIF without re-elaboration."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe


TOP = 'otpu_fpga_top_openxc7_jtag'
PROFILE = {'MCOLS': 4, 'ACT_ROWS': 4, 'LANES': 8, 'VPU_CL': 2,
           'MXU_IMPL': 2, 'CORE_KHZ': 100000, 'DDR_MTS': 800}


def export(gate_path: Path, out: Path):
    gate = json.loads(gate_path.read_text())
    if gate['status'] != 'FULL_CORRECTED_CLOCK_DATABASE_ALL_1103_DATAPATH_AND_CLOCK_CONTRACT_INVARIANTS_PASS':
        raise ValueError('Completed corrected full-design gate required')
    if gate['profile'] != PROFILE:
        raise ValueError('Complete accelerator profile changed')
    original = gate['full_inputs']['constrained.json']
    xdc = gate['full_inputs']['openxc7.xdc']
    for descriptor in [original, xdc]:
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Pinned full input changed')
    out.mkdir(parents=True, exist_ok=False)
    script = '\n'.join([
        'read_json ' + original['path'],
        'select -module ' + TOP,
        'select -assert-count 4 t:$scopeinfo',
        'delete t:$scopeinfo',
        'select -clear',
        'write_edif -top ' + TOP + ' -attrprop -pvector bra ' + str(out / 'full.edf'),
        'write_json ' + str(out / 'exported.json'),
    ]) + '\n'
    (out / 'export.ys').write_text(script)
    argv = [expand_paths('@YOSYS@'), '-Q', '-T', '-s', str(out / 'export.ys')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'gate': describe(gate_path), 'input': original, 'xdc': xdc, 'profile': PROFILE,
            'helper': describe(__file__), 'yosys': describe(argv[0]),
            'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'FULL_MAPPED_GRAPH_EDIF_EXPORT_NOT_VIVADO_IMPLEMENTATION_OR_HARDWARE_PASS'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-edif-and-json-export')
        print('EXACT_MAPPED_EDIF_STARTED ' + str(out), flush=True)
        with (out / 'export.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            ticks = Path('/proc') / str(child.pid) / 'stat'
            save(native_pid=child.pid, native_start_ticks=int(ticks.read_text().split(') ', 1)[1].split()[19]))
            code = child.wait()
        (out / 'export.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code:
            raise RuntimeError('Full mapped EDIF export failed')
        save(stage='complete-mapped-graph-comparison')
        before = json.loads(Path(original['path']).read_text())
        after = json.loads((out / 'exported.json').read_text())
        if set(before['modules']) != set(after['modules']):
            raise ValueError('Export changed module inventory')
        if TOP not in before['modules']:
            raise ValueError('Full mapped top missing')
        for name, module in before['modules'].items():
            if name != TOP and int(module.get('attributes', {}).get('blackbox', '0'), 2) != 1:
                raise ValueError('Unexpected nonopaque mapped submodule: ' + name)
        top = before['modules'][TOP]
        removed = {n: c for n, c in top['cells'].items() if c['type'] == '$scopeinfo'}
        if len(removed) != 4:
            raise ValueError('Nonfunctional metadata removal scope differs')
        for name in removed:
            del top['cells'][name]
        differences = [name for name in before['modules']
                       if before['modules'][name] != after['modules'][name]]
        if differences:
            raise ValueError('Export changed mapped graph: ' + repr(differences[:10]))
        if describe(original['path']) != original or describe(xdc['path']) != xdc:
            raise ValueError('Pinned full input changed during export')
        counts = dict(sorted(Counter(c['type'] for c in top['cells'].values()).items()))
        review = {'all_modules_equal_except_four_scopeinfo': True,
                  'modules': len(before['modules']), 'functional_cells': len(top['cells']),
                  'ports': len(top['ports']), 'netnames': len(top['netnames']),
                  'primitive_counts': counts, 'removed_scopeinfo_cells': list(removed),
                  'parameters_connections_attributes_ports_and_netnames_equal': True}
        (out / 'graph-comparison.json').write_text(json.dumps(review, indent=2) + '\n')
        save(status='FULL_MAPPED_GRAPH_IDENTICAL_EDIF_EXPORT_PASS_VIVADO_LINK_PENDING',
             comparison=review,
             outputs={name: describe(out / name) for name in ['full.edf', 'exported.json', 'graph-comparison.json']},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
        print('FUNCTIONAL_CELLS ' + str(review['functional_cells']), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--gate', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    export(args.gate.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
