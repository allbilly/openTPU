#!/usr/bin/env python3
"""Compare compiled DSP callbacks with independently validated vendor tables."""
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

from fedora_openxc7 import describe, digest
from openxc7_dsp_timing_tables import parameter


def compare(audit, data):
    models, ports, sequential, combinational = {}, {}, {}, {}
    for line in audit.read_text().splitlines():
        fields = line.split('\t'); tag, cell = fields[:2]
        if tag == 'M': target, key, value = models, cell, int(fields[2])
        elif tag == 'P': target, key, value = ports, (cell, fields[2]), (fields[3], int(fields[4]))
        elif tag == 'R': target, key, value = sequential, (cell, fields[2]), (fields[3], fields[4], *map(int, fields[5:]))
        elif tag == 'C': target, key, value = combinational, (cell, fields[2], fields[3]), tuple(map(int, fields[4:]))
        else: raise ValueError('Unknown native audit record')
        if key in target: raise ValueError('Duplicate native audit record')
        target[key] = value
    want_models, want_ports, want_sequential, want_comb = {}, {}, {}, {}
    for i, cfg in enumerate(data['configurations']):
        cell = cfg['probe_cell']; want_models[cell] = i
        seq_in, seq_out = set(cfg['registered_inputs']), set(cfg['registered_outputs'])
        arcs = {tuple(a[:3]): tuple(a[3:7]) for a in cfg['arcs']}
        comb_out = {key[2] for key in arcs if key[0] == 'comb'}
        for p in data['pin_map'].values():
            pin = p['packed']
            if pin == 'CLK': cls = 'clock_input'
            elif pin in seq_in: cls = 'register_input'
            elif pin in seq_out: cls = 'register_output'
            elif p['direction'] == 'input': cls = 'comb_input'
            elif pin in comb_out: cls = 'comb_output'
            else: cls = 'ignore'
            count = int(pin in seq_in or pin in seq_out)
            want_ports[(cell, pin)] = (cls, count)
            if pin in seq_in:
                s, h = arcs[('setup', 'CLK', pin)], arcs[('hold', 'CLK', pin)]
                want_sequential[(cell, pin)] = ('CLK', cfg['clock_edge'], min(s[0], s[2]), max(s[1], s[3]),
                                               min(h[0], h[2]), max(h[1], h[3]), 0, 0, 0, 0)
            elif pin in seq_out:
                q = arcs[('clkq', 'CLK', pin)]
                want_sequential[(cell, pin)] = ('CLK', cfg['clock_edge'], 0, 0, 0, 0, *q)
        for (kind, source, target), bounds in arcs.items():
            if kind == 'comb': want_comb[(cell, source, target)] = bounds
    for name, actual, expected in [('models', models, want_models), ('port classes', ports, want_ports),
                                   ('sequential checks', sequential, want_sequential), ('combinational arcs', combinational, want_comb)]:
        if actual != expected:
            missing = len(expected.keys()-actual.keys()); extra = len(actual.keys()-expected.keys())
            wrong = [k for k in actual.keys() & expected.keys() if actual[k] != expected[k]]
            examples = [(k, actual.get(k), expected.get(k)) for k in wrong[:3]]
            raise ValueError(f'Native {name} differ: missing={missing}, extra={extra}, wrong={len(wrong)}, examples={examples!r}')
    return dict(configurations=len(models), ports=len(ports), sequential_pins=len(sequential),
                combinational_arcs=len(combinational), mismatches=0)


def check(backend, tables, characterization, out):
    build = json.loads(backend.read_text()); tm = json.loads((tables/'manifest.json').read_text())
    if build['status'] != 'DSP_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING':
        raise ValueError('Expected the new DSP backend build')
    binary = Path(build['binary']['path'])
    if describe(binary) != build['binary'] or describe(tables/'dsp-timing-tables.json') != tm['output']:
        raise ValueError('Backend or vendor table changed')
    data = json.loads((tables/'dsp-timing-tables.json').read_text())
    configs = json.loads((characterization/'configurations.json').read_text())
    cm = json.loads((characterization/'manifest.json').read_text())
    rtl = characterization/'dsp_configs.v'
    if digest(rtl) != cm['inputs']['dsp_configs.v']:
        raise ValueError('Characterized RTL changed')
    defaults_raw = json.loads(Path(configs['source_inventory']).read_text())['vendor_defaults_raw']
    defaults = {n: parameter(raw) for n, raw in defaults_raw.items()}
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(status='RUNNING', scope='ALL_FULL_DESIGN_DSP_CONFIGURATIONS_NATIVE_CALLBACKS_NOT_FULL_ROUTE_OR_PATH_QUALIFICATION',
                    started_utc=datetime.now(timezone.utc).isoformat(), backend=describe(backend), binary=describe(binary),
                    table_manifest=describe(tables/'manifest.json'), table=describe(tables/'dsp-timing-tables.json'),
                    rtl=describe(rtl), helper=describe(__file__), physical_hardware='NOT_RUN', numerical_timing='NOT_QUALIFIED')
    def save(**fields):
        manifest.update(fields);(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    def run(stage, argv):
        save(stage=stage);(out/(stage+'.command.json')).write_text(json.dumps(argv,indent=2)+'\n')
        with (out/(stage+'.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(result.returncode)+'\n')
        return result.returncode
    try:
        save()
        raw_json = out/'probe.yosys.json'
        script = f'read_verilog -lib +/xilinx/cells_sim.v; read_verilog {rtl}; hierarchy -check -top dsp_configs; select dsp_configs; write_json -selected {raw_json}'
        if run('yosys', ['yosys', '-p', script]): raise RuntimeError('DSP source elaboration failed')
        design = json.loads(raw_json.read_text()); top = design['modules']['dsp_configs']
        if len(top['cells']) != len(data['configurations']) or any(c['type'] != 'DSP48E1' for c in top['cells'].values()):
            raise ValueError('Source elaboration changed DSP configuration count')
        # Retain driven DSP pins while removing external I/O placement. Without
        # these fixture drivers, pack_constants treats the former top-level
        # inputs as undriven and changes DSP inversion parameters.
        input_bits = sorted({bit for p in top['ports'].values() if p['direction']=='input'
                             for bit in p['bits'] if isinstance(bit,int)})
        for bit in input_bits:
            top['cells'][f'fixture_driver_{bit}'] = {
                'hide_name': 0, 'type': 'LUT1', 'parameters': {'INIT':'10'},
                'attributes': {'keep':'1'}, 'port_directions': {'I0':'input','O':'output'},
                'connections': {'I0':['0'],'O':[bit]},
            }
        top['ports'] = {}
        probe = out/'probe.callbacks.json';probe.write_text(json.dumps(design,separators=(',',':'))+'\n')
        chipdb = expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin')
        def command(source, audit, part='xc7k480tffg1156-2', enabled=True):
            argv = [str(binary), '--chipdb', chipdb, '--device', part, '--json', str(source), '--pack-only', '--threads', '8']
            if enabled: argv += ['-o','dsp-vivado-timing=on']
            if audit: argv += ['-o', 'dsp-timing-audit='+str(audit)]
            return argv
        audit = out/'all-configurations.callbacks.tsv'
        if run('all-configurations',command(probe,audit)): raise RuntimeError('Native DSP callback audit failed')
        result = compare(audit,data);save(all_configurations=result)
        by_name = {c['probe_cell']:c for c in data['configurations']}
        removed = 0
        for name, cell in top['cells'].items():
            if name not in by_name: continue
            for param in list(cell['parameters']):
                if by_name[name]['parameters'][param] == defaults[param]:
                    del cell['parameters'][param];removed += 1
        omitted = out/'probe.defaults-omitted.json';omitted.write_text(json.dumps(design,separators=(',',':'))+'\n')
        audit_defaults = out/'defaults-omitted.callbacks.tsv'
        if run('defaults-omitted',command(omitted,audit_defaults)): raise RuntimeError('Native DSP default resolution failed')
        save(defaults_omitted=compare(audit_defaults,data), declared_defaults_removed=removed)
        # Represent the same physical bus inversions as the actual packer/FASM
        # convention, rather than only the vendor's aggregate parameters.
        widths={'ALUMODE':4,'INMODE':5,'OPMODE':7}
        for name,cell in top['cells'].items():
            if name not in by_name: continue
            for bus,width in widths.items():
                key='IS_'+bus+'_INVERTED';mask=by_name[name]['parameters'][key]['value']
                cell['parameters'][key]='0'*width
                for bit in range(width):
                    cell['parameters'][f'IS_{bus}[{bit}]_INVERTED']='1'if mask&(1<<bit)else '0'
        split=out/'probe.split-bus-masks.json';split.write_text(json.dumps(design,separators=(',',':'))+'\n')
        audit_split=out/'split-bus-masks.callbacks.tsv'
        if run('split-bus-masks',command(split,audit_split)): raise RuntimeError('Native DSP packer mask resolution failed')
        save(split_bus_masks=compare(audit_split,data))
        if run('default-off',command(probe,None,enabled=False)): raise RuntimeError('Default-off behavior failed')
        first_cell=data['configurations'][0]['probe_cell']
        flag='IS_ALUMODE[0]_INVERTED';saved_flag=top['cells'][first_cell]['parameters'][flag]
        top['cells'][first_cell]['parameters'][flag]='10'
        malformed=out/'probe.malformed-mask-flag.json';malformed.write_text(json.dumps(design,separators=(',',':'))+'\n')
        code=run('malformed-mask-flag',command(malformed,None))
        if code!=125 or 'Malformed DSP bus inversion flag'not in(out/'malformed-mask-flag.log').read_text():
            raise ValueError('Malformed packer bus inversion flag was not explicitly rejected')
        top['cells'][first_cell]['parameters'][flag]=saved_flag
        top['cells'][data['configurations'][0]['probe_cell']]['parameters']['USE_SIMD'] = 'TWO24'
        unsupported = out/'probe.unsupported-mode.json';unsupported.write_text(json.dumps(design,separators=(',',':'))+'\n')
        code = run('unsupported-mode',command(unsupported,None))
        if code != 125 or 'Unsupported DSP timing configuration' not in (out/'unsupported-mode.log').read_text():
            raise ValueError('Unsupported DSP configuration was not explicitly rejected')
        code = run('wrong-speed-grade',command(probe,None,part='xc7k480tffg1156-1'))
        if code != 125 or 'characterized only for xc7k480tffg1156-2' not in (out/'wrong-speed-grade.log').read_text():
            raise ValueError('Uncharacterized speed grade was not explicitly rejected')
        shutil.copy2(__file__,out/'helper.py')
        save(status='ALL_DSP_CONFIGURATION_NATIVE_CALLBACKS_PASS_WHOLE_PHY_AND_VIVADO_PATH_TIMING_PENDING',
             completed_utc=datetime.now(timezone.utc).isoformat(), expected_unsupported_mode_exit=125,
             expected_wrong_speed_grade_exit=125, default_off_exit=0,
             expected_malformed_mask_flag_exit=125, fixture_input_drivers=len(input_bits),
             configuration_scope=data.get('mode_scope','SOURCE_PARAMETERS'),
             audits=[describe(audit),describe(audit_defaults),describe(audit_split)])
        print(manifest['status'],flush=True)
        return manifest
    except Exception as error:
        save(status='FAIL',error=repr(error));raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('backend','tables','characterization','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();check(args.backend.resolve(),args.tables.resolve(),args.characterization.resolve(),args.out.resolve())


if __name__ == '__main__':main()
