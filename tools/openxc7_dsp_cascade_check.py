#!/usr/bin/env python3
"""Map and route four real 16-DSP cascades across XC7 clock-row gaps."""
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re
import subprocess

from fedora_openxc7 import ROOT, PART, configuration, describe, digest


def check(backend_manifest, geometry, modes, out):
    out.mkdir(parents=True, exist_ok=False)
    mp = out/'manifest.json'
    manifest = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                    physical_hardware='NOT_RUN', helper=describe(Path(__file__).resolve()),
                    scope='Real 16-DSP cascade placement/routing across clock rows; full accelerator, numerical timing and physical hardware not validated')

    def save(**fields):
        manifest.update(fields)
        mp.write_text(json.dumps(manifest, indent=2)+'\n')

    def run(argv, name):
        save(stage=name)
        (out/(name+'.command.json')).write_text(json.dumps(argv, indent=2)+'\n')
        with (out/(name+'.log')).open('w') as log:
            result = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
        (out/(name+'.exit')).write_text(str(result.returncode)+'\n')
        if result.returncode:
            raise RuntimeError(name+' exited '+str(result.returncode))

    try:
        save()
        cfg = configuration()
        backend = json.loads(backend_manifest.read_text())
        if backend['status'] != 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED':
            raise RuntimeError('Backend build has not passed')
        binary = Path(backend['binary']['path'])
        if digest(binary) != backend['binary']['sha256']:
            raise RuntimeError('Backend binary changed')
        audit = json.loads(geometry.read_text())
        if digest(cfg['chipdb']) != audit['chipdb_sha256']:
            raise RuntimeError('Geometry audit chipdb differs')
        mode_list = json.loads(modes.read_text())
        roots = audit['crossing_probe_roots']
        if len(roots) != 4:
            raise RuntimeError('Expected four crossing roots')
        verilog = ['module dsp_cascade_probe(input SYS_CLK, output [2:0] led);',
                   'wire clk_ib,clk; IBUF ib(.I(SYS_CLK),.O(clk_ib)); BUFG bg(.I(clk_ib),.O(clk));',
                   "reg [47:0] count=1; always @(posedge clk) count<=count+1;",
                   "wire rise_q,fall_q,back_q;",
                   "(* keep=1 *) FDRE rise(.C(clk),.CE(1'b1),.R(1'b0),.D(count[0]),.Q(rise_q));",
                   "(* keep=1 *) FDRE #(.IS_C_INVERTED(1'b1)) fall(.C(clk),.CE(1'b1),.R(1'b0),.D(rise_q),.Q(fall_q));",
                   "(* keep=1 *) FDRE back(.C(clk),.CE(1'b1),.R(1'b0),.D(fall_q),.Q(back_q));",
                   'wire [47:0] p0,p1,p2,p3;']
        xdc = []
        for name, pin in {'SYS_CLK':'AA28','led[0]':'P30','led[1]':'M30','led[2]':'N30'}.items():
            xdc += [f'set_property PACKAGE_PIN {pin} [get_ports {{{name}}}]',
                    f'set_property IOSTANDARD LVCMOS18 [get_ports {{{name}}}]']
        xdc.append('create_clock -period 20 [get_ports {SYS_CLK}]')
        for chain, root in enumerate(roots):
            xdc.append(f'set_property LOC {root["site_name"]} [get_cells {{dsp_c{chain}_0}}]')
            for index in range(16):
                params = dict(mode_list[0 if chain < 2 else 2]['parameters'])
                params['PREG'] = '0' if index==15 else '1'
                param_text = ',\n'.join('.'+k+'('+re.sub(r"(\d+)'([01xz]+)", r"\1'b\2", v)+')'
                                       for k,v in params.items())
                pcin = "48'b0" if index==0 else f'pc_c{chain}_{index-1}'
                pcwire = f'pc_c{chain}_{index}'
                verilog.append(f'wire [47:0] {pcwire};')
                pout = f'p{chain}' if index==15 else f'unused_p_c{chain}_{index}'
                if index != 15:
                    verilog.append(f'wire [47:0] {pout};')
                verilog.append(f'''(* keep=1 *) DSP48E1 #(
{param_text}
) dsp_c{chain}_{index} (
.CLK(clk), .A(count[29:0]), .B(count[17:0]), .C(48'b0), .D(count[24:0]),
.ACIN(30'b0), .BCIN(18'b0), .PCIN({pcin}), .CARRYCASCIN(1'b0), .MULTSIGNIN(1'b0),
.CARRYIN(1'b0), .CARRYINSEL(3'b0), .ALUMODE(4'b0),
.OPMODE(7'b{"0000101" if index==0 else "0010101"}), .INMODE(5'b0),
.CEA1(1'b1), .CEA2(1'b1), .CEB1(1'b1), .CEB2(1'b1), .CEC(1'b1), .CED(1'b1),
.CEAD(1'b1), .CEM(1'b1), .CEP(1'b1), .CEALUMODE(1'b1), .CECARRYIN(1'b1),
.CECTRL(1'b1), .CEINMODE(1'b1), .RSTA(1'b0), .RSTB(1'b0), .RSTC(1'b0),
.RSTD(1'b0), .RSTM(1'b0), .RSTP(1'b0), .RSTALUMODE(1'b0),
.RSTALLCARRYIN(1'b0), .RSTCTRL(1'b0), .RSTINMODE(1'b0), .PCOUT({pcwire}), .P({pout}));''')
        verilog += ['assign led={^(p2^p3),^p1,(^p0)^back_q};', 'endmodule']
        (out/'probe.v').write_text('\n'.join(verilog)+'\n')
        (out/'probe.xdc').write_text('\n'.join(xdc)+'\n')
        save(backend=describe(backend_manifest), binary=describe(binary), chipdb=describe(cfg['chipdb']),
             geometry=describe(geometry), modes=describe(modes), roots=roots)
        run([str(cfg['yosys']), '-Q', '-T', '-p',
             'read_verilog probe.v; synth_xilinx -family xc7 -flatten -nosrl -top dsp_cascade_probe; check -assert; write_json synth.json'], 'synth')
        cells = json.loads((out/'synth.json').read_text())['modules']['dsp_cascade_probe']['cells']
        if sum(c['type']=='DSP48E1' for c in cells.values()) != 64:
            raise RuntimeError('Probe does not retain all 64 DSPs')
        run([str(binary), '--chipdb', str(cfg['chipdb']), '--device', PART,
             '--json', str(out/'synth.json'), '-o', 'xdc='+str(out/'probe.xdc'),
             '-o', 'fasm='+str(out/'probe.fasm'), '-o', 'delay-matrix=off',
             '--router', 'router2', '--freq', '50', '--threads', '1', '--seed', '1',
             '--detailed-timing-report',
             '--report', str(out/'timing.json'), '--write', str(out/'routed.json')], 'route')
        routed = json.loads((out/'routed.json').read_text())['modules']['top']
        placements = []
        for chain, root in enumerate(roots):
            for index in range(16):
                cell = routed['cells'][f'dsp_c{chain}_{index}']
                expected = f'DSP48_X{root["site_x"]}Y{root["site_y"]+index}/DSP48E1'
                if cell['type'] != 'DSP48E1_DSP48E1' or cell['attributes']['NEXTPNR_BEL'] != expected:
                    raise RuntimeError('Incorrect cascade BEL: '+str(cell['attributes']))
                placements.append(dict(cell=f'dsp_c{chain}_{index}', bel=expected))
        # Every PCOUT bit must connect exactly to the next DSP's matching
        # PCIN bit and retain the router's connectivity evidence.
        cascade_nets = []
        routed_by_bit = {n['bits'][0]:n for n in routed['netnames'].values() if len(n['bits'])==1}
        for chain in range(4):
            for index in range(15):
                source = routed['cells'][f'dsp_c{chain}_{index}']['connections']
                sink = routed['cells'][f'dsp_c{chain}_{index+1}']['connections']
                for bit in range(48):
                    srcbit = source[f'PCOUT{bit}'][0]
                    if sink[f'PCIN{bit}'] != [srcbit]:
                        raise RuntimeError('Cascade connectivity changed')
                    net = routed_by_bit[srcbit]
                    route = net['attributes'].get('ROUTING', '').strip()
                    if not route or not ('PCOUT' in route or 'PCIN' in route):
                        raise RuntimeError('Missing dedicated cascade route evidence')
                    if re.search(r'/(?:[NESW][LR]?\d|IMUX|BYP|LOGIC_OUTS)', route):
                        raise RuntimeError('Cascade uses general routing: '+route)
                    cascade_nets.append(dict(chain=chain, hop=index, bit=bit, routing=route))
        (out/'cascade-connectivity.json').write_text(json.dumps(cascade_nets, indent=2)+'\n')
        (out/'placements.json').write_text(json.dumps(placements, indent=2)+'\n')
        timing = json.loads((out/'timing.json').read_text())
        ff_events = {}
        for driver, sink, wanted in [('rise','fall',('posedge clk','negedge clk')),
                                     ('fall','back',('negedge clk','posedge clk'))]:
            events = [(n['event'], e['event']) for n in timing['detailed_net_timings']
                      if n['driver']==driver for e in n['endpoints'] if e['cell']==sink and e['port']=='D']
            if events != [wanted]:
                raise RuntimeError('Fabric FF edge correction lost: '+str(events))
            ff_events[driver+'->'+sink] = events[0]
        save(status='DSP_CASCADE_16_SITE_PLACEMENT_AND_ROUTING_PASS_STRICT_FRAMES_NOT_TESTED',
             placed_dsps=len(placements), routed_cascade_bits=len(cascade_nets),
             retained_ff_edge_events=ff_events,
             artifacts={p.name:describe(p) for p in out.iterdir()
                        if p.suffix in ('.json','.v','.xdc','.fasm') and p!=mp})
    except Exception as error:
        save(status='FAIL', error=str(error))
        raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())
        print(mp)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--backend-manifest', type=Path, required=True)
    ap.add_argument('--geometry', type=Path, required=True)
    ap.add_argument('--modes', type=Path, required=True)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    check(args.backend_manifest.resolve(), args.geometry.resolve(), args.modes.resolve(), args.out.resolve())
