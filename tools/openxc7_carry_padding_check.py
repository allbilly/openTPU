#!/usr/bin/env python3
"""Route carry observability probes and check packed logic against XC7 models.

Exhaust all 256 combinations of the eight input bits after translating the
actual routed LUT/IOB/CARRY connectivity and original LUT pin mappings.
No bitstream is generated and no hardware is programmed.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import configuration, describe, digest

RTL = '''module carry_padding_probe(input [3:0] a,b, output [3:0] led);
wire [3:0] pc0,pc1,fc0,fc1,fo1,xc0,xc1;
(* keep=1 *) CARRY4 padded_lo(.CI(1'b0),.CYINIT(1'b0),.DI(b),.S(a),.CO(pc0));
(* keep=1 *) CARRY4 padded_hi(.CI(pc0[3]),.CYINIT(1'b0),.DI({2'b00,b[1:0]}),.S({2'b00,a[1:0]}),.CO(pc1));
(* keep=1 *) CARRY4 full_lo(.CI(1'b0),.CYINIT(1'b0),.DI(b),.S(a),.CO(fc0));
(* keep=1 *) CARRY4 full_hi(.CI(fc0[3]),.CYINIT(1'b0),.DI(b),.S(a),.CO(fc1),.O(fo1));
(* keep=1 *) CARRY4 fanout_lo(.CI(1'b0),.CYINIT(1'b0),.DI(b),.S(a),.CO(xc0));
(* keep=1 *) CARRY4 fanout_hi(.CI(xc0[3]),.CYINIT(1'b0),.DI({2'b00,b[1:0]}),.S({2'b00,a[1:0]}),.CO(xc1));
assign led={xc1[0]^xc1[1],fo1[3],fc1[3],pc1[1]};
endmodule
'''


def packed_verilog(design):
    """Decode the actual packed graph, including physical-to-original LUT pins."""
    cells = design['cells']
    bits = sorted({b for c in cells.values() for bs in c['connections'].values()
                   for b in bs if isinstance(b, int)} |
                  {b for p in design['ports'].values() for b in p['bits'] if isinstance(b, int)})
    lines = ['module carry_packed_netlist(input [3:0] a,b, output [3:0] led);']
    lines += [f'wire n{b};' for b in bits]
    def signal(b):
        if isinstance(b, int):
            return f'n{b}'
        if b in ('0', '1'):
            return "1'b"+b
        raise RuntimeError('Unknown bit in routed graph: '+str(b))
    for port, p in design['ports'].items():
        if port not in ('a','b','led') or len(p['bits']) != 4:
            raise RuntimeError('Unexpected packed top interface')
        for index, bit in enumerate(p['bits']):
            lhs, rhs = signal(bit), f'{port}[{index}]'
            if p['direction'] == 'output':
                lhs, rhs = rhs, lhs
            lines.append(f'assign {lhs}={rhs};')
    for index, (name, c) in enumerate(cells.items()):
        typ = c['type']; con = c['connections']
        def get(port, default="1'b0"):
            bs = con.get(port, [])
            if len(bs) > 1:
                raise RuntimeError('Packed scalar port is a bus: '+name+'.'+port)
            return signal(bs[0]) if bs else default
        def drive(port, expression):
            if con.get(port):
                lines.append(f'assign {get(port)}={expression};')
        if typ == 'PAD':
            continue
        if typ in ('PSEUDO_GND','PSEUDO_VCC'):
            drive('Y', "1'b"+str(int(typ == 'PSEUDO_VCC')))
        elif typ.endswith('_INBUF_EN'):
            drive('OUT', get('PAD'))
        elif typ.endswith('_OUTBUF'):
            drive('OUT', get('IN'))
        elif typ == 'SLICE_LUTX':
            output = [p for p in ('O5','O6') if con.get(p)]
            if not output:
                # The packer can leave an unconsumed XORCY as a LUT. It
                # contributes no value to the observable routed graph.
                continue
            if len(output) != 1:
                raise RuntimeError('Unexpected packed LUT outputs: '+name)
            attrs = c['attributes']; orig = attrs['X_ORIG_TYPE']
            match = re.fullmatch(r'LUT([1-6])', orig)
            if not match:
                raise RuntimeError('Unsupported original LUT type: '+orig)
            logical = {}
            for port in con:
                for orig_port in attrs.get('X_ORIG_PORT_'+port, '').split():
                    m = re.fullmatch(r'I([0-5])', orig_port)
                    if m:
                        logical[int(m[1])] = get(port)
            width = int(match[1])
            if set(logical) != set(range(width)):
                raise RuntimeError('Missing original LUT input mapping: '+name)
            init = int(c['parameters']['INIT'], 2)
            lines.append(f'wire [{(1 << width)-1}:0] lut{index}={(1 << width)}\'h{init & ((1 << (1 << width))-1):x};')
            addr = '{'+','.join(logical[i] for i in reversed(range(width)))+'}'
            drive(output[0], f'lut{index}[{addr}]')
        elif typ == 'CARRY4':
            cin = '('+get('CIN')+'|'+get('CYINIT')+')'
            for bit in range(4):
                s, di = get('S'+str(bit)), get('DI'+str(bit))
                wire = f'carry{index}_{bit}'
                lines.append(f'wire {wire}=({s})?({cin}):({di});')
                drive('O'+str(bit), f'({s})^({cin})')
                drive('CO'+str(bit), wire)
                cin = wire
        else:
            raise RuntimeError('Unsupported routed cell: '+typ)
    lines.append('endmodule')
    return '\n'.join(lines)+'\n'


def check(backend_manifest, out, adopt_routed=None):
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    scope='Real carry probe synthesis/routing and exhaustive post-route logical equivalence',
                    physical_hardware='NOT_RUN', bitstream='NOT_GENERATED', helper=describe(Path(__file__).resolve()))
    def save(**fields):
        manifest.update(fields);mp.write_text(json.dumps(manifest, indent=2)+'\n')
    def run(argv, stage):
        save(stage=stage)
        (out/(stage+'.command.json')).write_text(json.dumps(argv, indent=2)+'\n')
        with (out/(stage+'.log')).open('w') as log:
            r = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(r.returncode)+'\n')
        if r.returncode:
            raise RuntimeError(stage+' exited '+str(r.returncode))
    try:
        save()
        bm = json.loads(backend_manifest.read_text())
        if bm['status'] != 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED':
            raise RuntimeError('Backend build did not pass')
        binary = Path(bm['binary']['path'])
        if digest(binary) != bm['binary']['sha256']:
            raise RuntimeError('Backend binary changed')
        cfg = configuration()
        save(backend_manifest=describe(backend_manifest), binary=bm['binary'], chipdb=describe(cfg['chipdb']),
             yosys=describe(cfg['yosys']))
        (out/'probe.v').write_text(RTL)
        # The last three pins come from this board's actual DDR address XDC.
        # This is a routing diagnostic only; it never generates/programs an image.
        ports = [f'a[{i}]' for i in range(4)]+[f'b[{i}]' for i in range(4)]+[f'led[{i}]' for i in range(4)]
        pins = ['AA28','P30','N30','N24','N25','P25','R26','R27','M30','AK27','AN23','AL24']
        xdc = []
        for i, (port, pin) in enumerate(zip(ports,pins)):
            xdc += [f'set_property PACKAGE_PIN {pin} [get_ports {{{port}}}]',
                    f'set_property IOSTANDARD {"LVCMOS18" if i < 9 else "SSTL15"} [get_ports {{{port}}}]']
        (out/'probe.xdc').write_text('\n'.join(xdc)+'\n')
        if adopt_routed:
            prior = json.loads((adopt_routed/'manifest.json').read_text())
            if (adopt_routed/'route.exit').read_text().strip() != '0':
                raise RuntimeError('Adopted probe did not actually route successfully')
            if prior['binary']['sha256'] != bm['binary']['sha256'] or prior['chipdb']['sha256'] != digest(cfg['chipdb']):
                raise RuntimeError('Adopted route backend/database differs')
            for name in ['probe.v','probe.xdc']:
                if digest(out/name) != digest(adopt_routed/name):
                    raise RuntimeError('Adopted route input differs: '+name)
            names = ['synth.json','routed.json','probe.fasm','synth.log','synth.exit',
                     'synth.command.json','route.log','route.exit','route.command.json']
            evidence = {}
            for name in names:
                evidence[name] = describe(adopt_routed/name)
                shutil.copyfile(adopt_routed/name,out/name)
                if digest(out/name) != evidence[name]['sha256']:
                    raise RuntimeError('Adopted artifact changed during copy: '+name)
            save(adopted_route=dict(manifest=describe(adopt_routed/'manifest.json'),
                                   actual_route_exit=0,artifacts=evidence))
        else:
            run([str(cfg['yosys']),'-Q','-T','-p',
                 'read_verilog probe.v; synth_xilinx -family xc7 -flatten -nosrl -top carry_padding_probe; check -assert; write_json synth.json'], 'synth')
            run([str(binary),'--chipdb',str(cfg['chipdb']),'--device','xc7k480tffg1156-2',
                 '--json',str(out/'synth.json'),'-o','xdc='+str(out/'probe.xdc'),'-o','fasm='+str(out/'probe.fasm'),
                 '-o','delay-matrix=off','--placer','heap','--router','router2','--threads','1','--seed','1',
                 '--write',str(out/'routed.json')], 'route')
        save(stage='post-route-observability')
        design = json.loads((out/'routed.json').read_text())['modules']['top']
        counts = Counter(c['type'] for c in design['cells'].values())
        users = Counter(b for c in design['cells'].values() for p, bs in c['connections'].items()
                        if c['port_directions'][p] in ('input','inout') for b in bs)
        users.update(b for p in design['ports'].values() if p['direction'] == 'output' for b in p['bits'])
        dead = [n for n,c in design['cells'].items() if c['type'] == 'CARRY4' and not any(
                users[b] for p,bs in c['connections'].items() if c['port_directions'][p] == 'output' for b in bs)]
        save(cell_counts=dict(counts), unused_carry_clusters=dead)
        if dead:
            raise RuntimeError('Unused carry clusters remain: '+str(dead))
        if 'Omitted ' not in (out/'route.log').read_text():
            raise RuntimeError('Corrected splitter was not exercised')
        (out/'packed.v').write_text(packed_verilog(design))
        (out/'tb.v').write_text('''module tb;
reg [3:0] a,b;wire [3:0] expected,actual;integer i;
carry_padding_probe reference(a,b,expected);carry_packed_netlist implementation(a,b,actual);
initial begin
 for(i=0;i<256;i=i+1) begin
  {a,b}=i;#1;
  if(actual!==expected) begin
   $display("FAIL a=%h b=%h expected=%h actual=%h",a,b,expected,actual);$fatal(1);
  end
 end
 $display("EXHAUSTIVE_EQUIVALENCE_PASS patterns=256 outputs=4");$finish;
end
endmodule
''')
        models = Path(cfg['yosys']).parent.parent/'share/yosys/xilinx/cells_sim.v'
        if not models.is_file():
            raise RuntimeError('XC7 primitive simulation models not found')
        save(reference_models=describe(models))
        run([shutil.which('iverilog'),'-g2012','-s','tb','-o',str(out/'simulation'),
             str(models),str(out/'probe.v'),str(out/'packed.v'),str(out/'tb.v')], 'simulation-compile')
        run([shutil.which('vvp'),str(out/'simulation')], 'exhaustive-equivalence')
        if 'EXHAUSTIVE_EQUIVALENCE_PASS patterns=256 outputs=4' not in (out/'exhaustive-equivalence.log').read_text():
            raise RuntimeError('Missing exhaustive equivalence marker')
        save(status='CARRY_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS', patterns=256, compared_outputs=4,
             numerical_timing='NOT_QUALIFIED', artifacts={name:describe(out/name) for name in ['synth.json','routed.json','probe.fasm','packed.v']})
    except Exception as e:
        save(status='FAIL', error=str(e));raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat());print(mp)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--backend-manifest', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--adopt-routed', type=Path, help='Reuse a matching probe with actual route exit zero')
    args = ap.parse_args()
    check(args.backend_manifest.resolve(), args.out.resolve(),
          args.adopt_routed.resolve() if args.adopt_routed else None)
