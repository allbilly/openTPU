#!/usr/bin/env python3
"""Route an actual MUXF7 subtree from a full no-F8 map and exhaust its truth table.

Boundary nets are independent probe inputs. This diagnoses the extracted
packing case; it does not establish full-design fit, timing, or board operation.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import configuration, describe, digest, route_threads


def extract(design, root):
    cells = design['cells']
    if root not in cells or cells[root]['type'] != 'MUXF7':
        raise RuntimeError('Root must be an existing MUXF7 cell')
    drivers = {b: n for n, c in cells.items() for p, bs in c['connections'].items()
               if c['port_directions'][p] == 'output' for b in bs if isinstance(b, int)}
    kept = {}

    def visit(name):
        if name in kept:
            return
        c = cells[name]
        kept[name] = c
        if c['type'] in ('MUXF7', 'MUXF8'):
            for p in ('I0', 'I1'):
                child = drivers.get(c['connections'][p][0])
                if child and (re.fullmatch(r'LUT[1-6]', cells[child]['type']) or
                              cells[child]['type'] in ('MUXF7', 'MUXF8')):
                    visit(child)

    visit(root)
    outputs = {b for c in kept.values() for p, bs in c['connections'].items()
               if c['port_directions'][p] == 'output' for b in bs}
    inputs = sorted({b for c in kept.values() for p, bs in c['connections'].items()
                     if c['port_directions'][p] == 'input' for b in bs
                     if isinstance(b, int)} - outputs)
    if not 1 <= len(inputs) <= 8:
        raise RuntimeError('Probe requires one to eight inputs for an exhaustive test and known board pins')
    return kept, inputs, cells[root]['connections']['O'][0]


def reference_verilog(cells, inputs, output):
    bits = sorted({b for c in cells.values() for bs in c['connections'].values()
                   for b in bs if isinstance(b, int)})
    lines = [f'module mux_cluster_probe(input [{len(inputs)-1}:0] x, output y);']
    lines += [f'wire n{b};' for b in bits]
    lines += [f'assign n{b}=x[{i}];' for i, b in enumerate(inputs)]
    lines.append(f'assign y=n{output};')
    for i, (name, c) in enumerate(cells.items()):
        params = []
        for p, value in c['parameters'].items():
            if not re.fullmatch('[01]+', value):
                raise RuntimeError('Unsupported parameter value: '+name+'.'+p)
            params.append(f'.{p}({len(value)}\'h{int(value,2):x})')
        connections = []
        for p, bs in c['connections'].items():
            if len(bs) != 1 or (isinstance(bs[0], str) and bs[0] not in ('0', '1')):
                raise RuntimeError('Unsupported scalar connection: '+name+'.'+p)
            s = f'n{bs[0]}' if isinstance(bs[0], int) else "1'b"+bs[0]
            connections.append(f'.{p}({s})')
        parameter_text = ' #('+','.join(params)+')' if params else ''
        lines.append(f'(* keep=1 *) {c["type"]}{parameter_text} c{i}('+','.join(connections)+');')
    return '\n'.join(lines+['endmodule'])+'\n'


def packed_verilog(design, width):
    cells = design['cells']
    bits = sorted({b for c in cells.values() for bs in c['connections'].values()
                   for b in bs if isinstance(b, int)} |
                  {b for p in design['ports'].values() for b in p['bits'] if isinstance(b, int)})
    lines = [f'module mux_packed_netlist(input [{width-1}:0] x, output y);']
    lines += [f'wire n{b};' for b in bits]

    def signal(b):
        if isinstance(b, int):
            return f'n{b}'
        if b in ('0', '1'):
            return "1'b"+b
        raise RuntimeError('Unknown routed bit: '+str(b))

    if set(design['ports']) != {'x', 'y'}:
        raise RuntimeError('Unexpected routed probe interface')
    for port, p in design['ports'].items():
        for i, b in enumerate(p['bits']):
            terminal = f'x[{i}]' if port == 'x' else 'y'
            left, right = (signal(b), terminal) if p['direction'] == 'input' else (terminal, signal(b))
            lines.append(f'assign {left}={right};')
    for i, (name, c) in enumerate(cells.items()):
        typ, con = c['type'], c['connections']

        def get(p):
            if len(con.get(p, [])) != 1:
                raise RuntimeError('Missing routed scalar port: '+name+'.'+p)
            return signal(con[p][0])

        def drive(p, expr):
            if con.get(p):
                lines.append(f'assign {get(p)}={expr};')

        if typ == 'PAD':
            continue
        if typ in ('PSEUDO_GND', 'PSEUDO_VCC'):
            drive('Y', "1'b"+str(int(typ == 'PSEUDO_VCC')))
        elif typ.endswith('_INBUF_EN'):
            drive('OUT', get('PAD'))
        elif typ.endswith('_OUTBUF'):
            drive('OUT', get('IN'))
        elif typ == 'SELMUX2_1':
            drive('OUT', f'({get("S0")})?({get("1")}):({get("0")})')
        elif typ == 'SLICE_LUTX':
            attrs = c['attributes']
            match = re.fullmatch(r'LUT([1-6])', attrs.get('X_ORIG_TYPE', ''))
            if not match:
                raise RuntimeError('Unsupported packed LUT: '+name)
            lut_width = int(match[1])
            logical = {}
            for p in con:
                for original in attrs.get('X_ORIG_PORT_'+p, '').split():
                    m = re.fullmatch(r'I([0-5])', original)
                    if m:
                        logical[int(m[1])] = get(p)
            if set(logical) != set(range(lut_width)):
                raise RuntimeError('Missing original LUT input map: '+name)
            output_ports = [p for p in ('O5', 'O6') if con.get(p)]
            if len(output_ports) != 1:
                raise RuntimeError('Unexpected packed LUT output count: '+name)
            init = int(c['parameters']['INIT'], 2) & ((1 << (1 << lut_width))-1)
            lines.append(f'wire [{(1<<lut_width)-1}:0] lut{i}={(1<<lut_width)}\'h{init:x};')
            address = '{'+','.join(logical[j] for j in reversed(range(lut_width)))+'}'
            drive(output_ports[0], f'lut{i}[{address}]')
        else:
            raise RuntimeError('Unsupported routed cell: '+typ)
    return '\n'.join(lines+['endmodule'])+'\n'


def check(args):
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    physical_hardware='NOT_RUN', bitstream='NOT_GENERATED',
                    scope='Exact extracted MUX subtree; independent boundary inputs; full fit and timing not qualified')

    def save(**updates):
        manifest.update(updates)
        (out/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')

    def run(command, stage):
        save(stage=stage)
        (out/(stage+'.command.json')).write_text(json.dumps(command, indent=2)+'\n')
        with (out/(stage+'.log')).open('w') as log:
            result = subprocess.run(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(result.returncode)+'\n')
        if result.returncode:
            raise RuntimeError(stage+' exited '+str(result.returncode))

    try:
        shutil.copyfile(Path(__file__), out/'helper-source.py')
        save(helper=describe(Path(__file__).resolve()), helper_snapshot=describe(out/'helper-source.py'),
             source_netlist=describe(args.netlist), root_cell=args.root_cell)
        bm = json.loads(args.backend_manifest.read_text())
        binary = Path(bm['binary']['path'])
        if digest(binary) != bm['binary']['sha256']:
            raise RuntimeError('Backend binary changed')
        cfg = configuration()
        save(backend_manifest=describe(args.backend_manifest), binary=bm['binary'], chipdb=describe(cfg['chipdb']),
             route_threads=route_threads())
        netlist = json.loads(args.netlist.read_text())
        modules = [v for v in netlist['modules'].values() if str(v.get('attributes', {}).get('top', '0')).endswith('1')]
        if len(modules) != 1:
            raise RuntimeError('Expected one flattened top module')
        source_counts=Counter(c['type'] for c in modules[0]['cells'].values());assert source_counts['MUXF8']==0,'F7-only witness requires zero F8 in the actual full checkpoint'
        kept, inputs, output = extract(modules[0], args.root_cell);assert len(inputs)==7
        save(root_primitive='MUXF7',source_mux_counts={t:source_counts[t] for t in ['MUXF7','MUXF8']},f8_absent_in_full_source=True)
        (out/'extracted.json').write_text(json.dumps(dict(cells=kept, inputs=inputs, output=output), indent=2)+'\n')
        (out/'probe.v').write_text(reference_verilog(kept, inputs, output))
        del netlist, modules
        save(original_cell_types=dict(Counter(c['type'] for c in kept.values())), boundary_inputs=len(inputs))
        pins = ['AA28', 'P30', 'N30', 'N24', 'N25', 'P25', 'R26', 'R27', 'M30']
        ports = [f'x[{i}]' for i in range(len(inputs))]+['y']
        xdc = []
        for port, pin in zip(ports, pins):
            xdc += [f'set_property PACKAGE_PIN {pin} [get_ports {{{port}}}]',
                    f'set_property IOSTANDARD LVCMOS18 [get_ports {{{port}}}]']
        (out/'probe.xdc').write_text('\n'.join(xdc)+'\n')
        run([str(cfg['yosys']), '-Q', '-T', '-p', 'read_verilog probe.v; synth_xilinx -family xc7 -flatten -nosrl -top mux_cluster_probe; check -assert; write_json synth.json'], 'synth')
        run([str(binary), '--chipdb', str(cfg['chipdb']), '--device', 'xc7k480tffg1156-2',
             '--json', str(out/'synth.json'), '-o', 'xdc='+str(out/'probe.xdc'), '-o', 'fasm='+str(out/'probe.fasm'),
             '-o', 'delay-matrix=off', '--placer', 'heap', '--router', 'router2', '--threads', str(route_threads()),
             '--seed', '1', '--write', str(out/'routed.json')], 'route')
        design = json.loads((out/'routed.json').read_text())['modules']['top']
        muxes = {n: dict(original_type=c['attributes'].get('X_ORIG_TYPE'), bel=c['attributes'].get('NEXTPNR_BEL'))
                 for n, c in design['cells'].items() if c['type'] == 'SELMUX2_1'}
        if len(muxes) < sum(c['type'] in ('MUXF7', 'MUXF8') for c in kept.values()):
            raise RuntimeError('Extracted MUX primitive count was not retained')
        if not any(c['original_type'] == 'MUXF7' and c['bel'].endswith(('/F7AMUX','/F7BMUX')) for c in muxes.values()):
            raise RuntimeError('No actual F7MUX placement')
        save(mux_placement=muxes)
        (out/'packed.v').write_text(packed_verilog(design, len(inputs)))
        patterns = 1 << len(inputs)
        (out/'tb.v').write_text(f'''module tb;
reg [{len(inputs)-1}:0] x; wire expected,actual; integer i;
mux_cluster_probe reference(x,expected); mux_packed_netlist implementation(x,actual);
initial begin
 for(i=0;i<{patterns};i=i+1) begin
  x=i; #1;
  if(actual!==expected) begin
   $display("FAIL x=%h expected=%b actual=%b",x,expected,actual); $fatal(1);
  end
 end
 $display("EXHAUSTIVE_MUX_EQUIVALENCE_PASS patterns={patterns}"); $finish;
end
endmodule
''')
        models = cfg['share']/'xilinx/cells_sim.v'
        save(reference_models=describe(models))
        run([shutil.which('iverilog'), '-g2012', '-s', 'tb', '-o', str(out/'simulation'),
             str(models), str(out/'probe.v'), str(out/'packed.v'), str(out/'tb.v')], 'simulation-compile')
        run([shutil.which('vvp'), str(out/'simulation')], 'exhaustive-equivalence')
        if f'EXHAUSTIVE_MUX_EQUIVALENCE_PASS patterns={patterns}' not in (out/'exhaustive-equivalence.log').read_text():
            raise RuntimeError('Missing exhaustive equivalence marker')
        save(status='EXTRACTED_MUX_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS', patterns=patterns,
             artifacts={n: describe(out/n) for n in ['extracted.json', 'probe.v', 'synth.json', 'routed.json', 'probe.fasm', 'packed.v']})
    except Exception as error:
        save(status='FAIL', error=str(error))
        raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())
        print(out/'manifest.json')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--netlist', type=Path, required=True)
    parser.add_argument('--backend-manifest', type=Path, required=True)
    parser.add_argument('--root-cell', required=True)
    parser.add_argument('--out', type=Path, required=True)
    check(parser.parse_args())
