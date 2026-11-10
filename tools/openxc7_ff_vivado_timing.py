#!/usr/bin/env python3
"""Inventory all full-design fabric FF modes and query exact-part Vivado arcs."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
import csv
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_mailbox_inventory import entries


PART = 'xc7k480tffg1156-2'
SR_PORT = {'FDRE': 'R', 'FDSE': 'S', 'FDCE': 'CLR', 'FDPE': 'PRE'}
BELS = ('AFF', 'BFF', 'CFF', 'DFF', 'A5FF', 'B5FF', 'C5FF', 'D5FF')


def bit(value):
    if isinstance(value, int) and not isinstance(value, bool) and value in (0, 1):
        return value
    if isinstance(value, str) and value and not set(value) - {'0', '1'}:
        result = int(value, 2)
        if result in (0, 1):
            return result
    if isinstance(value, str):
        literal = re.fullmatch(r"1'[bBhHdD]([01])", value)
        if literal:
            return int(literal[1])
    raise ValueError('Undefined or nonboolean FF inversion: ' + repr(value))


def inventory(gate: Path, out: Path):
    before = json.loads(gate.read_text())
    pin = json.loads((gate.parent / 'analysis-effective/inventory.json').read_text())
    packed = Path(before['output'])
    if (before['status'] != 'FULL_PACK_EXPORT_PASS_DSP_PROFILE_INVENTORY_PENDING'
            or before['native_exit'] != 0 or describe(gate) != pin['pack_manifest']
            or describe(packed) != pin['packed_netlist']):
        raise ValueError('Complete pinned packed export changed or did not pass')
    out.mkdir(parents=True, exist_ok=False)
    result = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
              'part': PART, 'profile': before['profile'], 'helper': describe(__file__),
              'packed_gate': describe(gate), 'packed_netlist': pin['packed_netlist'],
              'scope': 'ALL_PACKED_FABRIC_FF_MODES_INTRINSIC_TIMING_NOT_ROUTED_OR_HARDWARE_PROOF',
              'hardware_accessed': False, 'live_full_jobs_changed': False}

    def save(**fields):
        result.update(fields)
        (out / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')

    try:
        save(stage='stream-all-packed-registers')
        groups = defaultdict(list)
        inits = defaultdict(Counter)
        examples = {}
        for name, cell in entries(packed, 'cells'):
            if cell['type'] != 'SLICE_FFX':
                continue
            attrs, params = cell['attributes'], cell['parameters']
            primitive = attrs.get('X_ORIG_TYPE', '')
            if (primitive not in SR_PORT or 'X_FF_AS_LATCH' in attrs
                    or bool(attrs.get('X_FFSYNC', '').strip()) != (primitive in ('FDRE', 'FDSE'))
                    or set(params) - {'INIT', 'IS_C_INVERTED'}):
                raise ValueError('Unsupported actual FF mode: ' + name)
            for packed_port, source_port in {'CK': 'C', 'D': 'D', 'CE': 'CE', 'Q': 'Q', 'SR': SR_PORT[primitive]}.items():
                if (attrs.get('X_ORIG_PORT_' + packed_port) != source_port
                        or len(cell['connections'].get(packed_port, [])) != 1):
                    raise ValueError('Unexpected actual FF port mapping: ' + name)
            inverted = bit(params.get('IS_C_INVERTED', 0))
            key = primitive, inverted
            groups[key].append(name)
            raw_init = params.get('INIT', None)
            if raw_init is None or raw_init == 'x':
                # Same default as the pinned FASM writer and primitive library.
                init = int(primitive in ('FDSE', 'FDPE'))
                origin = 'undefined/default'
            else:
                init, origin = bit(raw_init), 'explicit'
            inits[key][f'{origin}:{init}'] += 1
            if key not in examples:
                examples[key] = {'name': name, **cell}
        expected = {('FDRE', 0): 177176, ('FDRE', 1): 402, ('FDSE', 0): 1701,
                    ('FDCE', 0): 16, ('FDPE', 0): 4}
        if {key: len(names) for key, names in groups.items()} != expected:
            raise ValueError('Complete FF profile/count differs from the observed full export')
        profiles = [{'id': i, 'primitive': key[0], 'clock_inverted': key[1],
                     'synchronous_sr': key[0] in ('FDRE', 'FDSE'), 'sr_port': SR_PORT[key[0]],
                     'cells': sorted(groups[key]), 'count': len(groups[key]),
                     'effective_init_counts': dict(inits[key]), 'example': examples[key]}
                    for i, key in enumerate(sorted(groups))]
        payload = {'part': PART, 'profile': before['profile'], 'packed_netlist': pin['packed_netlist'],
                   'profiles': profiles, 'ff_count': sum(len(names) for names in groups.values()),
                   'fasm_writer': describe(gate.parent.parent / 'static-double-exp-backend-20261011T183100Z/source/himbaechel/uarch/xilinx/fasm.cc')}
        (out / 'inventory.json').write_text(json.dumps(payload, indent=2) + '\n')
        save(status='ALL_179299_PACKED_FF_MODES_INVENTORIED_VENDOR_QUERY_PENDING', ff_count=payload['ff_count'],
             profiles=[{k: p[k] for k in ('id', 'primitive', 'clock_inverted', 'count', 'effective_init_counts')} for p in profiles],
             inventory=describe(out / 'inventory.json'), completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': result['status'], 'ff_count': payload['ff_count'], 'profiles': len(profiles)}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def configurations(inv):
    cells, measurements = [], []
    for profile in inv['profiles']:
        for init in (0, 1):
            cell = f'ff_{len(cells):02d}'
            params = {'INIT': init, 'IS_C_INVERTED': profile['clock_inverted']}
            c = {'cell': cell, 'profile_id': profile['id'], 'primitive': profile['primitive'], 'parameters': params}
            cells.append(c)
            measurements.append({**c, 'measurement': cell + '_unplaced', 'placed': False})
            for site_type in ('SLICEL', 'SLICEM'):
                for bel in BELS:
                    for sample in range(5):
                        measurements.append({**c, 'measurement': f'{cell}_{site_type}_{bel}_{sample}',
                                             'placed': True, 'site_type': site_type, 'bel': bel, 'sample': sample})
    if len(cells) != 10 or len(measurements) != 810:
        raise ValueError('Complete FF characterization coverage changed')
    return cells, measurements


def validate(out, configs, workers):
    properties = defaultdict(dict)
    with (out / 'cell-properties.tsv').open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            props = properties[row['measurement']]
            if row['property'] in props:
                raise ValueError('Duplicate cell property')
            props[row['property']] = row['value']
    raw = defaultdict(dict)
    with (out / 'timing-arcs.tsv').open() as stream:
        for row in csv.DictReader(stream, delimiter='\t'):
            props = raw[(row['measurement'], row['arc'])]
            if row['property'] in props:
                raise ValueError('Duplicate timing property')
            props[row['property']] = row['value']
    by_measurement = defaultdict(list)
    for (measurement, name), props in raw.items():
        by_measurement[measurement].append((name, props))
    expected = {c['measurement'] for c in configs}
    if set(properties) != expected or set(by_measurement) != expected:
        raise ValueError('Incomplete measurement scope')

    def check(cfg):
        measurement = cfg['measurement']; props = properties[measurement]
        if props['REF_NAME'] != cfg['primitive']:
            raise ValueError('Primitive changed: ' + measurement)
        if any(bit(props[p]) != value for p, value in cfg['parameters'].items()):
            raise ValueError('FF parameter changed: ' + measurement)
        for parameter in ('IS_D_INVERTED', 'IS_' + SR_PORT[cfg['primitive']] + '_INVERTED'):
            if bit(props[parameter]) != 0:
                raise ValueError('Unexpected data/control inversion: ' + measurement)
        if cfg['placed']:
            if (props['ACTUAL_BEL'] != props['LOC'] + '/' + cfg['bel']
                    or props['BEL'] != cfg['site_type'] + '.' + cfg['bel']
                    or props['SITE_TYPE'] != cfg['site_type']):
                raise ValueError('Actual physical FF placement differs: ' + measurement)
        elif props['ACTUAL_BEL'] or props['LOC'] or props['BEL']:
            raise ValueError('Baseline FF unexpectedly placed: ' + measurement)
        arcs = []
        for name, arc in by_measurement[measurement]:
            source, target = arc['FROM_PIN'], arc['TO_PIN']
            prefix = cfg['cell'] + '/'
            if not source.startswith(prefix) or not target.startswith(prefix):
                raise ValueError('Timing arc cell scope differs')
            source, target = source[len(prefix):], target[len(prefix):]
            delay_keys = [p for p in arc if p.startswith('DELAY_')]
            delays = {}
            for key in delay_keys:
                value = Decimal(arc[key])
                if not value.is_finite():
                    raise ValueError('Nonfinite timing value: ' + measurement + ' ' + key)
                delays[key] = arc[key]
            transitions = arc['TRANSITION'].split()
            if not transitions or any(t not in ('rr', 'rf', 'fr', 'ff') for t in transitions):
                raise ValueError('Unknown timing transition metadata')
            applicable = {'RISE' if t[1] == 'r' else 'FALL' for t in transitions}
            required = {f'DELAY_{corner}_{limit}_{edge}' for corner in ('FAST', 'SLOW')
                        for limit in ('MIN', 'MAX') for edge in applicable}
            if not required <= set(delays):
                raise ValueError('Incomplete vendor corner data')
            if arc['IS_DISABLED'] not in ('0', '1') or arc['IS_USER_DISABLED'] not in ('0', '1'):
                raise ValueError('Unexpected timing-disable metadata')
            disabled = arc['IS_DISABLED'] == '1'
            if disabled or arc['IS_USER_DISABLED'] == '1':
                if (not disabled or cfg['primitive'] not in ('FDCE', 'FDPE')
                        or arc['TYPE'] != 'Reg Set/Clr' or source != SR_PORT[cfg['primitive']] or target != 'Q'):
                    raise ValueError('Unsupported disabled FF arc')
            elif arc['TYPE'] not in ('Reg Clk to Q', 'setup', 'hold', 'recovery', 'removal'):
                raise ValueError('Unsupported enabled FF arc type')
            arcs.append({'measurement': measurement, 'cell': cfg['cell'], 'from': source, 'to': target,
                         'type': arc['TYPE'], 'transition': arc['TRANSITION'], 'sense': arc['SENSE'],
                         'disabled': disabled, 'user_disabled': arc['IS_USER_DISABLED'] == '1',
                         'applicable_delay_edges': sorted(applicable),
                         'lib_cell': arc['LIB_CELL'], 'delays_ns': delays})
        arcs.sort(key=lambda a: (a['from'], a['to'], a['type'], a['transition']))
        keys = [(a['from'], a['to'], a['type'], a['transition']) for a in arcs]
        if len(set(keys)) != len(keys):
            raise ValueError('Duplicate FF timing arc key')
        for key in [('C', 'Q', 'Reg Clk to Q'), ('C', 'D', 'setup'), ('C', 'D', 'hold'),
                    ('C', 'CE', 'setup'), ('C', 'CE', 'hold')]:
            if not any((a['from'], a['to'], a['type']) == key and not a['disabled'] for a in arcs):
                raise ValueError('Missing enabled FF data/enable arc: ' + measurement + ' ' + repr(key))
        control = SR_PORT[cfg['primitive']]
        types = ('setup', 'hold') if cfg['primitive'] in ('FDRE', 'FDSE') else ('recovery', 'removal')
        for kind in types:
            if not any((a['from'], a['to'], a['type'], a['disabled']) == ('C', control, kind, False) for a in arcs):
                raise ValueError('Missing correct FF control timing check: ' + measurement)
        return cfg, props, arcs

    with ThreadPoolExecutor(max_workers=workers) as pool:
        checked = list(pool.map(check, configs))
    signatures = defaultdict(dict)
    records = []
    for cfg, props, arcs in checked:
        signature = json.dumps([{k: v for k, v in a.items() if k not in ('measurement', 'cell')} for a in arcs], sort_keys=True)
        signatures[cfg['profile_id']].setdefault(signature, []).append(cfg['measurement'])
        records.append({'config': cfg, 'properties': props, 'arcs': arcs})
    data = {'part': PART, 'units': 'ns', 'raw_source': describe(out / 'timing-arcs.tsv'),
            'cell_property_source': describe(out / 'cell-properties.tsv'), 'measurements': records}
    (out / 'timing-arcs-compact.json').write_text(json.dumps(data, indent=2) + '\n')
    differences = {str(profile): [{'measurements': names, 'arcs': json.loads(signature)} for signature, names in groups.items()]
                   for profile, groups in signatures.items()}
    (out / 'mode-variation.json').write_text(json.dumps(differences, indent=2) + '\n')
    summary = {'measurements': len(checked), 'placed_measurements': sum(c['placed'] for c in configs),
               'unplaced_measurements': sum(not c['placed'] for c in configs),
               'arcs': sum(len(arcs) for _, _, arcs in checked),
               'arc_types': dict(Counter(a['type'] for _, _, arcs in checked for a in arcs)),
               'disabled_arcs': sum(a['disabled'] for _, _, arcs in checked for a in arcs),
               'signatures_per_mode': {str(k): len(v) for k, v in signatures.items()},
               'parameter_mismatches': 0, 'placement_mismatches': 0, 'nonfinite_delays': 0,
               'backend_import': 'PENDING_CORNER_ENVELOPE_AND_ASYNC_CONTROL_SEMANTICS',
               'scope': 'ALL_ACTUAL_FF_MODES_INDEPENDENT_INTRINSIC_PROBES_NOT_ROUTED_PARENT_DESIGN'}
    (out / 'semantic-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


def revalidate(previous: Path, out: Path, workers: int):
    """Reuse immutable successful native query output after a validator correction."""
    before = json.loads((previous / 'manifest.json').read_text())
    if before['native_exit'] != 0 or (previous / 'query.exit').read_text().strip() != '0':
        raise ValueError('Native vendor query did not complete')
    out.mkdir(parents=True, exist_ok=False)
    copied = {}
    for name in ('cell-properties.tsv', 'timing-arcs.tsv', 'configurations.json', 'ff-last-locations.dcp',
                 'query.exit', 'query.tcl', 'query.log', 'command.json', 'ff_configs.v', 'plan.md'):
        source = previous / name
        shutil.copy2(source, out / name)
        copied[name] = describe(source)
        if describe(out / name)['sha256'] != copied[name]['sha256']:
            raise ValueError('Immutable native query copy changed')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': PART,
            'previous_query': describe(previous / 'manifest.json'), 'native_exit': 0, 'helper': describe(__file__),
            'inventory': before['inventory'], 'ff_count': before['ff_count'], 'modes': 5, 'workers': workers,
            'copied_native_sources': copied, 'live_full_jobs_changed': False, 'hardware_accessed': False,
            'numerical_timing': 'NOT_QUALIFIED', 'scope': before['scope']}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    try:
        save(stage='independent-raw-validation')
        configs = json.loads((out / 'configurations.json').read_text())['measurements']
        summary = validate(out, configs, workers)
        save(status='ALL_FULL_DESIGN_FF_MODE_VENDOR_INTRINSICS_PASS_NATIVE_IMPORT_PENDING', summary=summary,
             outputs={name: describe(out / name) for name in ('configurations.json', 'cell-properties.tsv', 'timing-arcs.tsv',
                                                             'timing-arcs-compact.json', 'mode-variation.json', 'semantic-summary.json', 'ff-last-locations.dcp')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(summary), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def prepare(characterization: Path, out: Path, workers: int):
    """Prepare location-specific bounds without inventing missing transitions."""
    gate_path = characterization / 'manifest.json'
    gate = json.loads(gate_path.read_text())
    if gate['status'] != 'ALL_FULL_DESIGN_FF_MODE_VENDOR_INTRINSICS_PASS_NATIVE_IMPORT_PENDING' or gate['native_exit'] != 0:
        raise ValueError('Complete vendor FF validation did not pass')
    for record in gate['outputs'].values():
        if describe(record['path']) != record:
            raise ValueError('Validated vendor FF output changed')
    inv_path = Path(gate['inventory']['path'])
    if describe(inv_path) != gate['inventory']:
        raise ValueError('Complete full-design FF inventory changed')
    inv = json.loads(inv_path.read_text())
    data = json.loads((characterization / 'timing-arcs-compact.json').read_text())
    grouped = defaultdict(list)
    for measurement in data['measurements']:
        cfg = measurement['config']
        key = (cfg['profile_id'], cfg.get('site_type', 'UNPLACED'), cfg.get('bel', 'UNPLACED'))
        grouped[key].append(measurement)
    if len(grouped) != 85:
        raise ValueError('Complete FF location-class coverage differs')
    profiles = {p['id']: p for p in inv['profiles']}

    def convert(item):
        key, measurements = item
        unplaced = key[1] == 'UNPLACED'
        if (len(measurements) != (2 if unplaced else 10)
                or {m['config']['parameters']['INIT'] for m in measurements} != {0, 1}
                or not unplaced and {(m['config']['parameters']['INIT'], m['config']['sample']) for m in measurements}
                    != {(init, sample) for init in (0, 1) for sample in range(5)}):
            raise ValueError('Incomplete INIT/position comparison: ' + repr(key))
        def normalized(arcs):
            # Decimal removes harmless 0.000/-0.000 and formatting differences.
            return [{**{k: v for k, v in a.items() if k not in ('measurement', 'cell', 'delays_ns')},
                     'delays_ns': {k: str(Decimal(v).normalize()) for k, v in a['delays_ns'].items()}} for a in arcs]
        reference = normalized(measurements[0]['arcs'])
        if any(normalized(m['arcs']) != reference for m in measurements[1:]):
            raise ValueError('FF timing varies within a location class; cannot import one model: ' + repr(key))
        arcs = []
        for arc in measurements[0]['arcs']:
            corners, limits = {}, {}
            for edge in arc['applicable_delay_edges']:
                values = []
                for corner in ('FAST', 'SLOW'):
                    for limit in ('MIN', 'MAX'):
                        name = f'DELAY_{corner}_{limit}_{edge.upper()}'
                        value = Decimal(arc['delays_ns'][name]) * 1000
                        if not value.is_finite():
                            raise ValueError('Nonfinite physical FF table value')
                        corners[name] = str(value.normalize())
                        values.append(value)
                limits[edge] = {'min': int(min(values).to_integral_value(rounding=ROUND_FLOOR)),
                                'max': int(max(values).to_integral_value(rounding=ROUND_CEILING))}
            clock_edge = None
            if arc['from'] == 'C':
                source_edges = {t[0] for t in arc['transition'].split()}
                if len(source_edges) != 1:
                    raise ValueError('Ambiguous FF library clock edge')
                clock_edge = 'falling' if (source_edges == {'f'}) != bool(profiles[key[0]]['clock_inverted']) else 'rising'
            arcs.append({k: arc[k] for k in ('from', 'to', 'type', 'transition', 'sense', 'disabled', 'user_disabled', 'applicable_delay_edges')} |
                        {'clock_edge': clock_edge, 'corner_values_ps': corners, 'transition_bounds_ps': limits})
        p = profiles[key[0]]
        return {'profile_id': key[0], 'primitive': p['primitive'], 'clock_inverted': p['clock_inverted'],
                'synchronous_sr': p['synchronous_sr'], 'sr_port': p['sr_port'], 'site_type': key[1], 'bel': key[2],
                'measurements': [m['config']['measurement'] for m in measurements], 'arcs': arcs,
                'native_control_semantics': 'SETUP_HOLD' if p['synchronous_sr'] else 'RECOVERY_REMOVAL_IMPORT_PENDING'}

    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': PART, 'units': 'ps',
            'characterization': describe(gate_path), 'inventory': gate['inventory'], 'helper': describe(__file__),
            'workers': workers, 'hardware_accessed': False, 'live_full_jobs_changed': False,
            'scope': 'ALL_FULL_DESIGN_FF_MODES_LOCATION_SPECIFIC_VENDOR_TABLES_NATIVE_IMPORT_PENDING',
            'numerical_timing': 'NOT_QUALIFIED'}
    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')
    try:
        save(stage='independent-init-position-comparisons')
        with ThreadPoolExecutor(max_workers=workers) as pool:
            models = list(pool.map(convert, sorted(grouped.items())))
        table = {'schema': 1, 'part': PART, 'units': 'ps', 'inventory': gate['inventory'],
                 'source_tsv': describe(characterization / 'timing-arcs.tsv'), 'models': models,
                 'ff_count': inv['ff_count'], 'profile': inv['profile'],
                 'disabled_arc_policy': 'EXPLICIT_VENDOR_DISABLED_NOT_A_ZERO_PROPAGATION_MODEL',
                 'missing_transition_policy': 'ABSENT_NOT_ZERO_NO_FABRICATED_OPPOSITE_EDGE'}
        (out / 'ff-timing-tables.json').write_text(json.dumps(table, indent=2) + '\n')
        summary = {'models': len(models), 'placed_models': sum(m['site_type'] != 'UNPLACED' for m in models),
                   'unplaced_models': sum(m['site_type'] == 'UNPLACED' for m in models),
                   'vendor_measurements': sum(len(m['measurements']) for m in models),
                   'table_arcs': sum(len(m['arcs']) for m in models),
                   'disabled_records': sum(a['disabled'] for m in models for a in m['arcs']),
                   'complete_ff_count': inv['ff_count'], 'within_location_class_variations': 0,
                   'scope': info['scope']}
        (out / 'comparison.json').write_text(json.dumps(summary, indent=2) + '\n')
        save(status='ALL_85_FF_LOCATION_MODE_TABLES_PREPARED_NATIVE_IMPORT_PENDING', summary=summary,
             outputs={n: describe(out / n) for n in ('ff-timing-tables.json', 'comparison.json')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(summary), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def query(inventory_path: Path, out: Path, workers: int):
    inv = json.loads(inventory_path.read_text())
    gate = json.loads((inventory_path.parent / 'manifest.json').read_text())
    if (gate['status'] != 'ALL_179299_PACKED_FF_MODES_INVENTORIED_VENDOR_QUERY_PENDING'
            or describe(inventory_path) != gate['inventory'] or inv['ff_count'] != 179299 or inv['part'] != PART):
        raise ValueError('Complete FF inventory did not pass or changed')
    cells, measurements = configurations(inv)
    out.mkdir(parents=True, exist_ok=False)
    count = len(cells)
    rtl = [f'module ff_configs(input wire clk, input wire [{count-1}:0] din, en, sr, output wire [{count-1}:0] q);']
    for index, c in enumerate(cells):
        rtl.append(f'(* DONT_TOUCH="TRUE" *) {c["primitive"]} #(.INIT(1\'b{c["parameters"]["INIT"]}), '
                   f'.IS_C_INVERTED(1\'b{c["parameters"]["IS_C_INVERTED"]})) {c["cell"]} '
                   f'(.C(clk), .D(din[{index}]), .CE(en[{index}]), .{SR_PORT[c["primitive"]]}(sr[{index}]), .Q(q[{index}]));')
    rtl.append('endmodule')
    (out / 'ff_configs.v').write_text('\n'.join(rtl) + '\n')
    (out / 'configurations.json').write_text(json.dumps({'inventory': describe(inventory_path), 'cells': cells,
                                                       'measurements': measurements}, indent=2) + '\n')
    header = f'''set_param general.maxThreads {workers}
create_project -in_memory -part {PART}
read_verilog ff_configs.v
synth_design -top ff_configs -part {PART} -mode out_of_context -flatten_hierarchy none
create_clock -name core -period 10 [get_ports clk]
set cf [open cell-properties.tsv w]
puts $cf "measurement\tproperty\tvalue"
set af [open timing-arcs.tsv w]
puts $af "measurement\tarc\tproperty\tvalue"
proc query_ff {{measurement name}} {{
    global cf af
    set cell [get_cells $name]
    if {{[llength $cell] != 1}} {{error "Missing exact FF cell $name"}}
    foreach property {{REF_NAME LOC BEL INIT IS_C_INVERTED IS_D_INVERTED}} {{
        puts $cf "$measurement\t$property\t[get_property $property $cell]"
    }}
    set primitive [get_property REF_NAME $cell]
    array set sr_port {{FDRE R FDSE S FDCE CLR FDPE PRE}}
    set property "IS_$sr_port($primitive)_INVERTED"
    puts $cf "$measurement\t$property\t[get_property $property $cell]"
    set bels [get_bels -quiet -of_objects $cell]
    if {{[llength $bels] > 1}} {{error "Ambiguous actual BEL $name"}}
    set actual ""
    set site_type ""
    if {{[llength $bels] == 1}} {{
        set actual [get_property NAME $bels]
        set site_type [get_property SITE_TYPE [get_sites -of_objects $bels]]
    }}
    puts $cf "$measurement\tACTUAL_BEL\t$actual"
    puts $cf "$measurement\tSITE_TYPE\t$site_type"
    set arcs [get_timing_arcs -of_objects $cell]
    foreach arc $arcs {{
        foreach property [lsort [list_property $arc]] {{
            set value [get_property $property $arc]
            set value [string map [list "\t" "\\t" "\n" "\\n" "\r" "\\r"] $value]
            puts $af "$measurement\t$arc\t$property\t$value"
        }}
    }}
    puts "FF_QUERY|$measurement|$actual|[llength $arcs]"
}}
array set used {{}}
foreach site_type {{SLICEL SLICEM}} {{
    set sites($site_type) [lsort -dictionary [get_sites -filter "SITE_TYPE == $site_type"]]
}}
proc target_site {{site_type sample bel}} {{
    global sites used
    set all $sites($site_type)
    set n [llength $all]
    set anchor [expr {{int(round($sample * ($n - 1) / 4.0))}}]
    for {{set distance 0}} {{$distance < $n}} {{incr distance}} {{
        foreach index [list [expr {{$anchor + $distance}}] [expr {{$anchor - $distance}}]] {{
            if {{$index < 0 || $index >= $n}} {{continue}}
            set site [lindex $all $index]
            if {{[info exists used($site)]}} {{continue}}
            if {{[llength [get_bels -quiet $site/$bel]] != 1}} {{error "Missing physical BEL $site/$bel"}}
            set used($site) 1
            return $site/$bel
        }}
    }}
    error "No unused physical site for $site_type $sample $bel"
}}
'''
    commands = [header]
    for c in measurements:
        if not c['placed']:
            commands.append(f'query_ff {c["measurement"]} {c["cell"]}')
    for c in measurements:
        if c['placed']:
            commands.append(f'set target [target_site {c["site_type"]} {c["sample"]} {c["bel"]}]\n'
                            f'place_cell [list {c["cell"]} $target]\nquery_ff {c["measurement"]} {c["cell"]}')
    commands.append('close $cf\nclose $af\nwrite_checkpoint ff-last-locations.dcp\nputs "ALL_FF_INTRINSIC_QUERIES_COMPLETE_NOT_PARENT_TIMING_QUALIFICATION"\nexit 0')
    (out / 'query.tcl').write_text('\n'.join(commands) + '\n')
    plan = Path(__file__).resolve().parents[1] / 'docs/openxc7_phy_timing_plan.md'
    shutil.copy2(plan, out / 'plan.md')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace', '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'part': PART,
            'inventory': describe(inventory_path), 'helper': describe(__file__), 'workers': workers,
            'ff_count': inv['ff_count'], 'modes': 5, 'measurements': len(measurements),
            'live_full_jobs_changed': False, 'hardware_accessed': False, 'numerical_timing': 'NOT_QUALIFIED',
            'scope': 'ALL_FULL_DESIGN_FF_MODES_ACTUAL_BEL_INTRINSICS_NOT_PARENT_ROUTE_TIMING'}

    def save(**fields):
        info.update(fields); (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='vendor-query')
        print('VIVADO_FF_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_pid=child.pid); code = child.wait()
        (out / 'query.exit').write_text(str(code) + '\n'); save(native_exit=code)
        if code:
            raise RuntimeError('Native full-mode FF query failed')
        save(stage='independent-raw-validation')
        summary = validate(out, measurements, workers)
        save(status='ALL_FULL_DESIGN_FF_MODE_VENDOR_INTRINSICS_PASS_NATIVE_IMPORT_PENDING', summary=summary,
             outputs={name: describe(out / name) for name in ('configurations.json', 'cell-properties.tsv', 'timing-arcs.tsv',
                                                             'timing-arcs-compact.json', 'mode-variation.json', 'semantic-summary.json', 'ff-last-locations.dcp')},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps(summary), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc)); raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('inventory')
    p.add_argument('--packed-gate', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p = sub.add_parser('query')
    p.add_argument('--inventory', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    p = sub.add_parser('prepare')
    p.add_argument('--characterization', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    p = sub.add_parser('validate')
    p.add_argument('--previous-query', type=Path, required=True); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if args.command == 'inventory':
        inventory(args.packed_gate.resolve(), args.out.resolve())
    else:
        if not 1 <= args.workers <= 8:
            parser.error('workers must be between 1 and 8')
        if args.command == 'query':
            query(args.inventory.resolve(), args.out.resolve(), args.workers)
        elif args.command == 'validate':
            revalidate(args.previous_query.resolve(), args.out.resolve(), args.workers)
        else:
            prepare(args.characterization.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
