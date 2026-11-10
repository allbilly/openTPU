#!/usr/bin/env python3
"""Implement the complete linked LiteDRAM graph as an offline Vivado reference."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_mapped_edif import TOP, PROFILE
from openxc7_clock_route_vivado import parameter
from openxc7_phy_vivado_timing import library_parameters


def quote(value):
    value = str(value)
    if any(c in value for c in '{}\r\n'):
        raise ValueError('Unsafe Tcl object name')
    return '{' + value + '}'


def prepare_graph(link, review):
    top = json.loads(Path(review['exported_json']['path']).read_text())['modules'][TOP]
    with Path(link['outputs']['cells.tsv']['path']).open() as stream:
        actual = {row['cell']: row for row in csv.DictReader(stream, delimiter='\t')}
    if any(row['is_blackbox'] != '0' for row in actual.values()):
        raise ValueError('Imported blackbox exists')
    missing = {n: c for n, c in top['cells'].items() if n not in actual}
    changed = {n: (c['type'], actual[n]['primitive']) for n, c in top['cells'].items()
               if n in actual and c['type'] != actual[n]['primitive']}
    if len(missing) != 6 or any(c['type'] != 'INV' for c in missing.values()):
        raise ValueError('Unexpected missing mapped cells')
    if Counter(changed.values()) != Counter({('INV', 'LUT1'): 2250, ('OBUFDS', 'OBUFDS_DUAL_BUF'): 2}):
        raise ValueError('Unexpected primitive transformation')
    inv_map = []
    for name, cell in missing.items():
        ibit, = cell['connections']['I']
        obit, = cell['connections']['O']
        sources = [(n, pin) for n, c in top['cells'].items() for pin, bits in c['connections'].items()
                   if bits == [ibit] and c['port_directions'][pin] == 'output']
        sinks = [(n, c['type'], pin, c['parameters'].get('IS_' + pin + '_INVERTED', '0'))
                 for n, c in top['cells'].items() for pin, bits in c['connections'].items()
                 if bits == [obit] and c['port_directions'][pin] == 'input']
        if len(sources) != 1 or not sinks:
            raise ValueError('Absorbed inverter does not have a unique driver and actual loads')
        if any((primitive, pin) not in [('ISERDESE2', 'CLKB'), ('OSERDESE2', 'T1')]
               for _, primitive, pin, _ in sinks):
            raise ValueError('Unexpected absorbed inversion context')
        inv_map.append({'cell': name, 'driver': '/'.join(sources[0]),
                        'sinks': [{'cell': n, 'primitive': primitive, 'pin': pin,
                                   'expected_inversion': 1 - int(raw, 2)}
                                  for n, primitive, pin, raw in sinks]})
    clock_cells = {n: c for n, c in top['cells'].items() if c['type'] in ('MMCME2_ADV', 'PLLE2_ADV')}
    bscan, = [n for n, c in top['cells'].items() if c['type'] == 'BSCANE2']
    core_bits = top['netnames']['ld_sys_clk']['bits']
    core, = [(n, pin) for n, c in top['cells'].items() for pin, bits in c['connections'].items()
             if bits == core_bits and c['port_directions'][pin] == 'output']
    return {'source_cells': len(top['cells']), 'actual_inventory_cells': len(actual),
            'unresolved_blackboxes': 0, 'primitive_changes': dict(Counter(str(v) for v in changed.values())),
            'inv_to_lut1': [n for n, types in changed.items() if types == ('INV', 'LUT1')],
            'absorbed_inverters': inv_map, 'clocks': clock_cells,
            'bscan': bscan, 'core_pin': '/'.join(core)}


def implement(link_path: Path, out: Path):
    link = json.loads(link_path.read_text())
    if link['status'] != 'FULL_MAPPED_VIVADO_LINK_COMPLETE_IMPORT_GRAPH_REVIEW_PENDING' or link['native_exit'] != 0:
        raise ValueError('Completed full Vivado link required')
    if link['profile'] != PROFILE:
        raise ValueError('Full profile changed')
    if describe(link['review']['path']) != link['review']:
        raise ValueError('Reviewed graph receipt changed')
    review = json.loads(Path(link['review']['path']).read_text())
    for descriptor in [link['outputs']['linked.dcp'], link['outputs']['cells.tsv'], review['exported_json'], link['input']]:
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Pinned graph/checkpoint changed')
    contract_path = Path(link_path).parents[1] / 'mailbox-cdc-contract-candidate-20261012T042800Z.json'
    contract = json.loads(contract_path.read_text())
    if contract['profile'] != PROFILE or len(contract['payload_bounds']) != 1103 or len(contract['synchronizers']) != 2:
        raise ValueError('Full mailbox contract scope changed')
    graph = prepare_graph(link, review)
    vref_source = Path(__file__).resolve().parents[1] / 'boards/ypcb-00338/litedram/otpu_litedram.xdc'
    vref_lines = [line for line in vref_source.read_text().splitlines() if line.startswith('set_property INTERNAL_VREF ')]
    vref_banks = []
    for line in vref_lines:
        match = re.fullmatch(r'set_property INTERNAL_VREF 0\.750 \[get_iobanks (\d+)\]', line)
        if not match:
            raise ValueError('Unsupported reference INTERNAL_VREF setting')
        vref_banks.append(int(match.group(1)))
    if sorted(vref_banks) != list(range(11, 19)):
        raise ValueError('Complete dual-DDR INTERNAL_VREF bank scope changed')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'import-review.json').write_text(json.dumps(graph, indent=2) + '\n')
    tcl = ['set_param general.maxThreads 8', 'set_param tcl.collectionResultDisplayLimit 0',
           'open_checkpoint ' + quote(link['outputs']['linked.dcp']['path']),
           'proc primitive_boolean {value} {',
           '    set value [string tolower $value]',
           '    if {$value in {1 true 1\'b1 1\'d1}} {return 1}',
           '    if {$value in {0 false 1\'b0 1\'d0}} {return 0}',
           '    error "Unknown primitive boolean format: $value"',
           '}',
           'set inf [open inversion-review.tsv w]', 'puts $inf "cell\\tport\\tactual_inversion\\tdriver_net_match"']
    for name in graph['inv_to_lut1']:
        tcl += ['set c [get_cells ' + quote(name) + ']',
                'if {[llength $c] != 1 || [get_property REF_NAME $c] != "LUT1"} {error "INV transformation cell missing"}',
                'set init [string tolower [get_property INIT $c]]',
                'if {$init ni {1 01 2\'h1 2\'h01 2\'b01}} {error "INV LUT1 truth table changed"}']
    for inv in graph['absorbed_inverters']:
        tcl += ['set driver [get_pins ' + quote(inv['driver']) + ']',
                'if {[llength $driver] != 1} {error "Absorbed inverter driver missing"}',
                'set dn [get_nets -of_objects $driver]']
        for sink in inv['sinks']:
            tcl += ['set c [get_cells ' + quote(sink['cell']) + ']',
                    'set pin [get_pins ' + quote(sink['cell'] + '/' + sink['pin']) + ']',
                    'if {[llength $c] != 1 || [llength $pin] != 1} {error "Absorbed inversion load missing"}',
                    'set inverted [primitive_boolean [get_property IS_' + sink['pin'] + '_INVERTED $c]]',
                    'set same_net [expr {[get_nets -of_objects $pin] eq $dn}]',
                    'if {$inverted != ' + str(sink['expected_inversion']) + ' || !$same_net} {error "Absorbed I/O input inversion changed"}',
                    'puts $inf [join [list ' + quote(sink['cell']) + ' ' + quote(sink['pin']) + ' $inverted $same_net] "\\t"]']
    tcl += ['close $inf', 'puts "ALL_MAPPED_INV_TRANSFORMATIONS_VALIDATED"',
            'create_clock -name jtag_tck -period 166.666667 [get_pins ' + quote(graph['bscan'] + '/TCK') + ']',
            'set core [get_clocks -of_objects [get_pins ' + quote(graph['core_pin']) + ']]',
            'if {[llength $core] != 1 || abs([get_property PERIOD $core] - 10.0) > 0.000001} {error "Full core 100 MHz clock missing"}',
            'set cpf [open clock-parameters.tsv w]', 'puts $cpf "cell\\tparameter\\tactual"']
    for name, cell in graph['clocks'].items():
        defaults, _ = library_parameters(cell['type'])
        for key, raw in cell['parameters'].items():
            if defaults[key]['kind'] not in ('integer', 'real'):
                continue
            value = parameter(cell['type'], key, raw)
            tcl += ['set c [get_cells ' + quote(name) + ']',
                    'set value [get_property ' + key + ' $c]',
                    'if {abs(double($value) - ' + value + ') > 0.000001} {error "Imported numeric clock parameter changed"}',
                    'puts $cpf [join [list ' + quote(name) + ' ' + key + ' $value] "\\t"]']
    tcl += ['close $cpf']
    tcl += vref_lines
    for row in contract['payload_bounds']:
        delay = row['max_delay_ps'] / 1000
        tcl += ['set source [get_cells ' + quote(row['source_cell']) + ']',
                'set capture [get_cells ' + quote(row['capture_cell']) + ']',
                'if {[llength $source] != 1 || [llength $capture] != 1} {error "Full mailbox endpoint missing"}',
                f'set_max_delay -datapath_only {delay:g} -from $source -to $capture',
                'set_false_path -hold -from $source -to $capture']
    for chain in contract['synchronizers']:
        names = ' '.join(quote(stage['cell']) for stage in chain['stages'])
        tcl += ['set cells [get_cells [list ' + names + ']]',
                'if {[llength $cells] != 3} {error "Full synchronizer stage missing"}',
                'set_property ASYNC_REG TRUE $cells', 'set_property DONT_TOUCH TRUE $cells',
                'create_macro ' + quote(chain['name']),
                'update_macro ' + quote(chain['name']) + ' [list ' +
                ' '.join(quote(stage['cell']) + ' X0Y0' for stage in chain['stages']) + ']',
                'set_false_path -to [get_pins ' + quote(chain['stages'][0]['cell'] + '/D') + ']']
        for stage, bel in zip(chain['stages'], ['AFF', 'BFF', 'CFF'], strict=True):
            tcl += ['set_property BEL ' + bel + ' [get_cells ' + quote(stage['cell']) + ']']
    tcl += ['puts "FULL_CLOCK_AND_1103_MAILBOX_CONSTRAINTS_APPLIED"',
            'report_clocks -file clocks.rpt', 'write_checkpoint -force constrained.dcp',
            'opt_design', 'write_checkpoint -force optimized.dcp', 'report_utilization -file optimized-utilization.rpt',
            'puts "FULL_MAPPED_VIVADO_OPT_COMPLETE"', 'place_design',
            'write_checkpoint -force placed.dcp', 'report_timing_summary -file placed-timing.rpt',
            'report_timing -max_paths 20 -file placed-paths.rpt',
            'puts "FULL_MAPPED_VIVADO_PLACE_COMPLETE"', 'route_design',
            'write_checkpoint -force routed.dcp', 'report_route_status -file route-status.rpt',
            'report_timing_summary -file routed-timing.rpt', 'report_timing -max_paths 20 -file routed-paths.rpt',
            'report_drc -file routed-drc.rpt', 'report_cdc -file routed-cdc.rpt',
            'set sf [open synchronizers.tsv w]', 'puts $sf "chain\\tcell\\tloc\\tbel"']
    for chain in contract['synchronizers']:
        tcl += ['set locations {}']
        for stage in chain['stages']:
            tcl += ['set c [get_cells ' + quote(stage['cell']) + ']',
                    'lappend locations [get_property LOC $c]',
                    'puts $sf [join [list ' + quote(chain['name']) + ' ' + quote(stage['cell']) + ' [get_property LOC $c] [get_property BEL $c]] "\\t"]']
        tcl += ['if {[llength [lsort -unique $locations]] != 1} {error "Full mailbox synchronizer is not in one slice"}']
    tcl += ['close $sf', 'puts "FULL_MAPPED_VIVADO_ROUTE_COMPLETE_REVIEW_PENDING"', 'exit 0']
    (out / 'implement.tcl').write_text('\n'.join(tcl) + '\n')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'implement.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'link': describe(link_path), 'checkpoint': link['outputs']['linked.dcp'],
            'contract': describe(contract_path), 'profile': PROFILE, 'threads': 8, 'helper': describe(__file__),
            'restored_internal_vref_source': describe(vref_source), 'restored_internal_vref_banks': vref_banks,
            'import_review': describe(out / 'import-review.json'), 'hardware_accessed': False,
            'live_full_jobs_changed': False, 'timing_signoff': False, 'accepted_image': False,
            'scope': 'FULL_MAPPED_LITEDRAM_VIVADO_IMPLEMENTATION_REFERENCE_NOT_OPENXC7_OR_HARDWARE_PASS'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-full-vivado-reference-implementation')
        print('FULL_MAPPED_VIVADO_IMPLEMENTATION_STARTED ' + str(out), flush=True)
        with (out / 'implement.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_launcher_pid=child.pid)
            code = child.wait()
        (out / 'implement.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        text = (out / 'implement.log').read_text(errors='replace')
        if code or 'FULL_MAPPED_VIVADO_ROUTE_COMPLETE_REVIEW_PENDING' not in text:
            raise RuntimeError('Full mapped Vivado reference did not complete')
        save(status='FULL_MAPPED_VIVADO_ROUTE_COMPLETE_TIMING_AND_IMPORT_SEMANTICS_REVIEW_PENDING',
             outputs={name: describe(out / name) for name in ['inversion-review.tsv', 'clock-parameters.tsv', 'clocks.rpt',
                      'constrained.dcp', 'optimized.dcp', 'placed.dcp', 'routed.dcp', 'route-status.rpt',
                      'placed-timing.rpt', 'placed-paths.rpt', 'routed-timing.rpt', 'routed-paths.rpt',
                      'routed-drc.rpt', 'routed-cdc.rpt', 'synchronizers.tsv']},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--link', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    implement(args.link.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
