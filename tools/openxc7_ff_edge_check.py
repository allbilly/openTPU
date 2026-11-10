#!/usr/bin/env python3
"""Route the same physical FF chain with baseline and corrected xc7 timing."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import shutil
import subprocess
import time

from fedora_openxc7 import ROOT, PART, configuration, describe, digest

PROBE = '''module ff_edge_probe(input SYS_CLK, input din, output [2:0] led);
  wire clk_ib, clk, rising_q, falling_q, return_q;
  IBUF ib (.I(SYS_CLK), .O(clk_ib));
  BUFG bg (.I(clk_ib), .O(clk));
  (* keep = "true" *) FDRE rise (.C(clk), .CE(1'b1), .R(1'b0), .D(din), .Q(rising_q));
  (* keep = "true" *) FDRE #(.IS_C_INVERTED(1'b1)) fall
      (.C(clk), .CE(1'b1), .R(1'b0), .D(rising_q), .Q(falling_q));
  (* keep = "true" *) FDRE back (.C(clk), .CE(1'b1), .R(1'b0), .D(falling_q), .Q(return_q));
  assign led = {return_q, falling_q, rising_q};
endmodule
'''


def check(backend_active, out, reuse_baseline=None, backend_manifest=None):
    out.mkdir(parents=True, exist_ok=False)
    active = (dict(manifest=str(backend_manifest), service=None)
              if backend_manifest else json.loads(backend_active.read_text()))
    cfg = configuration()
    manifest = dict(status='RUNNING', backend=active,
                    started_utc=datetime.now(timezone.utc).isoformat(),
                    scope='Actual mapped/routed FF clock-edge and full/half-period Fmax semantics; not numerical-delay qualification or a board image',
                    physical_hardware='NOT_RUN', helper=describe(Path(__file__).resolve()))
    mp = out/'manifest.json'

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

    def route(binary, name):
        save(**{name+'_binary':describe(binary)})
        run([str(binary), '--chipdb', str(cfg['chipdb']), '--device', PART,
             '--json', str(out/'synth.json'), '-o', 'xdc='+str(out/'probe.xdc'),
             '-o', 'fasm='+str(out/(name+'.fasm')), '-o', 'delay-matrix=off',
             '--router', 'router2', '--freq', '50', '--threads', '1', '--seed', '1',
             '--detailed-timing-report', '--report', str(out/(name+'.timing.json')),
             '--write', str(out/(name+'.routed.json'))], name)

    try:
        save()
        (out/'probe.v').write_text(PROBE)
        pins = {'SYS_CLK':'AA28', 'din':'R28', 'led[0]':'P30', 'led[1]':'M30', 'led[2]':'N30'}
        xdc = []
        for name, pin in pins.items():
            xdc += [f'set_property PACKAGE_PIN {pin} [get_ports {{{name}}}]',
                    f'set_property IOSTANDARD LVCMOS18 [get_ports {{{name}}}]']
        xdc.append('create_clock -period 20 [get_ports {SYS_CLK}]')
        (out/'probe.xdc').write_text('\n'.join(xdc)+'\n')
        if reuse_baseline:
            previous = json.loads((reuse_baseline/'manifest.json').read_text())
            qualified = json.loads((reuse_baseline/'baseline-qualification.json').read_text())
            assert (reuse_baseline/'baseline.exit').read_text().strip()=='0'
            assert previous['baseline_binary']['sha256']==digest(cfg['nextpnr'])
            assert previous['chipdb']['sha256']==digest(cfg['chipdb'])
            assert (reuse_baseline/'probe.v').read_text()==PROBE
            assert (reuse_baseline/'probe.xdc').read_text()==(out/'probe.xdc').read_text()
            for item in [previous['netlist'], *qualified['evidence'].values()]:
                assert digest(item['path'])==item['sha256'], item['path']
            for name in ['synth.json', 'baseline.routed.json', 'baseline.timing.json',
                         'baseline.fasm', 'baseline.exit', 'baseline.command.json',
                         'baseline.log', 'baseline-qualification.json']:
                shutil.copy2(reuse_baseline/name, out/name)
            save(reused_baseline=dict(directory=str(reuse_baseline),
                                     manifest=describe(reuse_baseline/'manifest.json'),
                                     qualification=describe(reuse_baseline/'baseline-qualification.json')),
                 baseline_binary=describe(cfg['nextpnr']))
        else:
            run([str(cfg['yosys']), '-Q', '-T', '-p',
                 'read_verilog probe.v; synth_xilinx -family xc7 -flatten -nosrl -top ff_edge_probe; check -assert; write_json synth.json'], 'synth')
        data = json.loads((out/'synth.json').read_text())['modules']['ff_edge_probe']['cells']
        assert sum(c['type']=='FDRE' for c in data.values()) == 3
        assert int(data['fall']['parameters']['IS_C_INVERTED'], 2) == 1
        save(netlist=describe(out/'synth.json'), chipdb=describe(cfg['chipdb']))
        if not reuse_baseline:
            route(cfg['nextpnr'], 'baseline')
        if backend_manifest is None:
            save(stage='wait-live-backend')
            while True:
                state = subprocess.run(['systemctl', '--user', 'show', active['service'],
                                        '--property=ActiveState', '--value'], capture_output=True, text=True)
                if state.stdout.strip() not in ('active', 'activating', 'deactivating'):
                    break
                time.sleep(10)
        backend_path = backend_manifest or Path(active['manifest'])
        backend = json.loads(backend_path.read_text())
        has_ff_edge = backend['status'] == 'BACKEND_BUILD_PASS_CLOCK_EDGE_BEHAVIOR_NOT_YET_TESTED'
        has_retained_ff_edge = 'FF_CLOCK_EDGE' in backend.get('retained_corrections', [])
        if not (has_ff_edge or has_retained_ff_edge):
            raise RuntimeError('Backend manifest does not declare the FF clock-edge correction')
        binary = Path(backend['binary']['path'])
        if digest(binary) != backend['binary']['sha256']:
            raise RuntimeError('Backend binary hash mismatch')
        route(binary, 'corrected')
        results = {}
        for name in ('baseline', 'corrected'):
            report = json.loads((out/(name+'.timing.json')).read_text())
            nets = report['detailed_net_timings']
            wanted = [('rise', 'fall'), ('fall', 'back')]
            pairs = {}
            for driver, sink in wanted:
                matches = [(n['event'], e['event']) for n in nets if n['driver']==driver
                           for e in n['endpoints'] if e['cell']==sink and e['port']=='D']
                assert len(matches)==1, (name, driver, sink, matches)
                pairs[driver+'->'+sink] = matches[0]
            expected = [('posedge clk', 'posedge clk')]*2 if name=='baseline' else [
                ('posedge clk', 'negedge clk'), ('negedge clk', 'posedge clk')]
            assert list(pairs.values())==expected, (name, pairs)
            critical = [p for p in report['critical_paths'] if p['from'].endswith(' clk') and p['to'].endswith(' clk')]
            assert len(critical)==1, critical
            path = critical[0]
            delay_ns = sum(s['delay'] for s in path['path'])
            fmax = report['fmax']['clk']
            factor = 1000 if name=='baseline' else 500
            assert math.isclose(delay_ns*fmax['achieved'], factor, rel_tol=1e-5), (name, delay_ns, fmax)
            assert math.isclose(fmax['constraint'], 50), fmax
            modules = json.loads((out/(name+'.routed.json')).read_text())['modules']
            assert list(modules)==['top'], list(modules)
            packed = modules['top']['cells']
            assert packed['fall']['type']=='SLICE_FFX'
            inversion = packed['fall']['parameters']['IS_C_INVERTED']
            assert (int(inversion, 2) if isinstance(inversion, str) else int(inversion))==1
            results[name] = dict(clock_pairs=pairs, critical_path_delay_ns=delay_ns,
                                 achieved_mhz=fmax['achieved'], period_factor_ns_mhz=factor)
        assert digest(out/'synth.json')==manifest['netlist']['sha256']
        save(status='ROUTED_FF_EDGE_AND_FULL_HALF_PERIOD_SEMANTICS_PASS_NUMERICAL_MODEL_NOT_QUALIFIED',
             results=results, artifacts={p.name:describe(p) for p in out.iterdir()
                                        if p.suffix in ('.json', '.fasm', '.xdc', '.v') and p!=mp})
    except Exception as error:
        save(status='FAIL', error=str(error))
        raise
    finally:
        save(finished_utc=datetime.now(timezone.utc).isoformat())
        print(mp)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--backend-active', type=Path, default=ROOT/'build/fedora-openxc7/ff-edge-backend-active.json')
    parser.add_argument('--backend-manifest', type=Path,
                        help='test the exact already-built backend binary in this manifest without waiting for a service')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--reuse-baseline', type=Path, help='reuse an identical, hash-checked routed baseline')
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    check(args.backend_active.resolve(), (args.out or ROOT/'build/fedora-openxc7'/('ff-edge-validation-'+stamp)).resolve(),
          args.reuse_baseline.resolve() if args.reuse_baseline else None,
          args.backend_manifest.resolve() if args.backend_manifest else None)
