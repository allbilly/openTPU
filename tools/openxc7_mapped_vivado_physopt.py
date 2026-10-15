#!/usr/bin/env python3
"""Optimize the complete placed reference and reroute at its original targets."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_mapped_edif import PROFILE
from openxc7_mapped_route_review import timing_summary, route_summary


def optimize(baseline_path: Path, out: Path, mode='postplace'):
    baseline = json.loads(baseline_path.read_text())
    if baseline['status'] != 'FULL_VIVADO_ROUTE_PASS_TIMING_FAIL_FULL_SCOPE_OPTIMIZATION_REQUIRED':
        raise ValueError('Reviewed full timing-failing baseline required')
    if baseline['profile'] != PROFILE:
        raise ValueError('Full accelerator scope changed')
    if mode not in ('postplace', 'postroute'):
        raise ValueError('Unsupported physical optimization mode')
    checkpoint = baseline['checkpoints']['placed.dcp' if mode == 'postplace' else 'routed.dcp']
    if describe(checkpoint['path']) != checkpoint:
        raise ValueError('Immutable placed checkpoint changed')
    route_manifest = baseline['native_route']
    if describe(route_manifest['path']) != route_manifest:
        raise ValueError('Completed baseline receipt changed')
    source = json.loads(Path(route_manifest['path']).read_text())
    visited = set()
    while 'contract' not in source:
        parent = source.get('baseline')
        if not parent or parent['path'] in visited or describe(parent['path']) != parent:
            raise ValueError('Original contract provenance is missing or changed')
        visited.add(parent['path'])
        parent_review = json.loads(Path(parent['path']).read_text())
        origin = parent_review['native_route']
        if describe(origin['path']) != origin:
            raise ValueError('Original native reference receipt changed')
        source = json.loads(Path(origin['path']).read_text())
    contract = json.loads(Path(source['contract']['path']).read_text())
    if describe(source['contract']['path']) != source['contract'] or contract['profile'] != PROFILE:
        raise ValueError('Full mailbox contract changed')
    out.mkdir(parents=True, exist_ok=False)
    optimized_name = 'physopt-placed.dcp' if mode == 'postplace' else 'physopt-routed.dcp'
    tcl = ['set_param general.maxThreads 8', 'set_param tcl.collectionResultDisplayLimit 0',
           'open_checkpoint {' + checkpoint['path'] + '}',
           'set core [get_clocks u_ld.crg_s7mmcm_clkout]',
           'if {[llength $core] != 1 || abs([get_property PERIOD $core] - 10.0) > 0.000001} {error "Full core target changed"}',
           'report_timing_summary -file before-physopt-timing.rpt',
           'phys_opt_design -directive AggressiveExplore',
           'write_checkpoint -force ' + optimized_name,
           'report_timing_summary -file after-physopt-timing.rpt',
           'report_timing -max_paths 20 -file after-physopt-paths.rpt',
           'puts "FULL_' + mode.upper() + '_PHYSOPT_COMPLETE"']
    if mode == 'postplace':
        tcl += ['route_design']
    tcl += ['write_checkpoint -force routed.dcp',
           'report_route_status -file route-status.rpt',
           'report_timing_summary -file routed-timing.rpt',
           'report_timing -max_paths 20 -file routed-paths.rpt',
           'report_drc -file routed-drc.rpt', 'report_cdc -file routed-cdc.rpt',
           'report_clocks -file clocks.rpt',
           'set core [get_clocks u_ld.crg_s7mmcm_clkout]',
           'if {[llength $core] != 1 || abs([get_property PERIOD $core] - 10.0) > 0.000001} {error "Full core target changed after optimization"}',
           'set sf [open synchronizers.tsv w]', 'puts $sf "chain\\tcell\\tloc\\tbel"']
    for chain in contract['synchronizers']:
        tcl += ['set locations {}']
        for stage in chain['stages']:
            name = stage['cell']
            if any(char in name for char in '{}\r\n'):
                raise ValueError('Unsupported exact cell name')
            tcl += ['set c [get_cells {' + name + '}]',
                    'if {[llength $c] != 1 || [get_property LOC $c] == ""} {error "Synchronizer cell missing"}',
                    'lappend locations [get_property LOC $c]',
                    'puts $sf [join [list {' + chain['name'] + '} {' + name + '} [get_property LOC $c] [get_property BEL $c]] "\\t"]']
        tcl += ['if {[llength [lsort -unique $locations]] != 1} {error "Full three-stage synchronizer left one slice"}']
    tcl += ['close $sf', 'puts "FULL_PHYSOPT_REFERENCE_ROUTE_COMPLETE_REVIEW_PENDING"', 'exit 0']
    (out / 'physopt.tcl').write_text('\n'.join(tcl) + '\n')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'physopt.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'baseline': describe(baseline_path), 'checkpoint': checkpoint, 'profile': PROFILE,
            'helper': describe(__file__), 'threads': 8,
            'optimization': 'POSTPLACE_AGGRESSIVE_EXPLORE_THEN_FULL_ROUTE' if mode == 'postplace' else
                            'POSTROUTE_AGGRESSIVE_EXPLORE_AUTOMATIC_ROUTE_UPDATE',
            'original_contract': describe(Path(source['contract']['path'])),
            'retiming_selected': False, 'targets_changed': False, 'hardware_accessed': False,
            'working_mig_reference_changed': False, 'live_openxc7_jobs_changed': False,
            'accepted_image': False, 'timing_signoff': False,
            'scope': 'FULL_SAME_MAPPED_DESIGN_PHYSICAL_OPTIMIZATION_REFERENCE_NOT_OPENXC7_OR_HARDWARE_PASS'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-' + mode + '-physical-optimization-and-routing')
        print('FULL_MAPPED_PHYSOPT_REFERENCE_STARTED ' + str(out), flush=True)
        with (out / 'physopt.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_launcher_pid=child.pid)
            code = child.wait()
        (out / 'physopt.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        text = (out / 'physopt.log').read_text(errors='replace')
        if code or 'FULL_PHYSOPT_REFERENCE_ROUTE_COMPLETE_REVIEW_PENDING' not in text:
            raise RuntimeError('Full postplace optimization/reference route incomplete')
        before = timing_summary(out / 'before-physopt-timing.rpt')
        after = timing_summary(out / 'after-physopt-timing.rpt')
        final = timing_summary(out / 'routed-timing.rpt')
        route = route_summary(out / 'route-status.rpt')
        route_pass = route['fully routed nets'] == route['routable nets'] and route['nets with routing errors'] == 0
        if not route_pass:
            raise ValueError('Optimized full reference has incomplete routing')
        numerical_pass = (final['wns_ns'] >= 0 and final['whs_ns'] >= 0 and final['wpws_ns'] >= 0
                          and all(final[k] == 0 for k in ['setup_failing_endpoints', 'hold_failing_endpoints', 'pulse_failing_endpoints']))
        if describe(checkpoint['path']) != checkpoint:
            raise ValueError('Immutable baseline placed checkpoint changed during optimization')
        save(status='FULL_PHYSOPT_REFERENCE_ROUTE_AND_NUMERICAL_TIMING_PASS_IMPORT_CDC_REVIEW_PENDING' if numerical_pass else
             'FULL_PHYSOPT_REFERENCE_ROUTE_PASS_TIMING_FAIL_REVIEW_REQUIRED',
             before_physopt=before, after_physopt=after, routed_timing=final, route=route,
             numerical_timing_pass=numerical_pass,
            outputs={name: describe(out / name) for name in [optimized_name, 'routed.dcp', 'before-physopt-timing.rpt',
                      'after-physopt-timing.rpt', 'after-physopt-paths.rpt', 'route-status.rpt', 'routed-timing.rpt',
                      'routed-paths.rpt', 'routed-drc.rpt', 'routed-cdc.rpt', 'clocks.rpt', 'synchronizers.tsv']},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'before': before, 'after': after, 'routed': final}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--mode', choices=['postplace', 'postroute'], default='postplace')
    args = parser.parse_args()
    optimize(args.baseline.resolve(), args.out.resolve(), args.mode)


if __name__ == '__main__':
    main()
