#!/usr/bin/env python3
"""Check actual mailbox capture latency with bounded synthetic payload delays."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe, digest


def simulate(inventory: Path, source_proof: Path, out: Path, workers: int):
    inv = json.loads(inventory.read_text())
    if inv['status'] not in ('COMPLETE_PACKED_MAILBOX_PAYLOAD_INVENTORY_PASS_CONTROL_REVIEW_PENDING',
                             'COMPLETE_PACKED_MAILBOX_PAYLOAD_AND_SYNCHRONIZER_TOPOLOGY_PASS_TIMING_PENDING') or inv['payload_crossings'] != 1103:
        raise ValueError('Expected complete packed mailbox inventory')
    proof = json.loads(source_proof.read_text())
    root = Path(__file__).resolve().parents[1]
    source = root / 'rtl/boards/ypcb-00338/otpu_jtag_mailbox.sv'
    if digest(source) != proof['source'][str(source)]:
        raise ValueError('Pinned production mailbox changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(), 'helper': describe(__file__),
            'inventory': describe(inventory), 'source_proof': describe(source_proof), 'production_source': describe(source),
            'workers': workers, 'scope': 'DIGITAL_RTL_WITH_SYNTHETIC_BUS_DELAYS_NOT_ANALOG_METASTABILITY_OR_ROUTED_TIMING',
            'hardware_accessed': False, 'live_full_route_changed': False, 'production_rtl_changed': False}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    def run(name, argv):
        (out / (name + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        with (out / (name + '.log')).open('w') as log:
            code = subprocess.run(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT).returncode
        (out / (name + '.exit')).write_text(str(code) + '\n')
        return name, code

    try:
        text = source.read_text()
        replacements = [('module otpu_jtag_mailbox (', '''module otpu_jtag_mailbox_cdc_probe #(
  parameter integer REQUEST_DELAY_PS=0, RESPONSE_DELAY_PS=0
) ('''), ('req <= held;', 'req <= held_path;'), ('response_tck <= response;', 'response_tck <= response_path;')]
        for old, new in replacements:
            if text.count(old) != 1:
                raise ValueError('Mailbox instrumentation anchor changed')
            text = text.replace(old, new)
        old = '  assign tdo = sr[0];'
        if text.count(old) != 1:
            raise ValueError('Mailbox bus instrumentation anchor changed')
        extra = '''  wire [603:0] held_path;
  wire [567:0] response_path;
  generate for (genvar g=0;g<604;g=g+1) begin
    assign #((REQUEST_DELAY_PS>g%32)?REQUEST_DELAY_PS-g%32:0) held_path[g]=held[g];
  end endgenerate
  generate for (genvar g=0;g<568;g=g+1) begin
    assign #((RESPONSE_DELAY_PS>g%32)?RESPONSE_DELAY_PS-g%32:0) response_path[g]=response[g];
  end endgenerate
'''
        rtl = out / 'mailbox-with-synthetic-bus-delays.sv'
        rtl.write_text('`timescale 1ps/1ps\n' + text.replace(old, extra + old))
        bench = out / 'tb_openxc7_mailbox_cdc.sv'
        shutil.copy2(root / 'boards/ypcb-00338/sim/tb_openxc7_mailbox_cdc.sv', bench)
        variants = {'zero-delay': (0, 0), 'bounded-delay': (20000, 300000),
                    'request-too-late': (50000, 0), 'response-too-late': (0, 800000)}
        save(stage='parallel-compile', instrumented_source=describe(rtl), bench=describe(bench),
             instrumentation='ONLY_BUNDLED_DATA_CONSUMER_WIRES_HAVE_SYNTHETIC_PER_BIT_DELAYS', variants=variants)
        jobs = [(name, ['iverilog', '-g2012', '-s', 'tb_openxc7_mailbox_cdc',
                        '-Ptb_openxc7_mailbox_cdc.REQUEST_DELAY_PS=' + str(delays[0]),
                        '-Ptb_openxc7_mailbox_cdc.RESPONSE_DELAY_PS=' + str(delays[1]),
                        '-o', str(out / (name + '.vvp')), str(bench), str(rtl)]) for name, delays in variants.items()]
        with ThreadPoolExecutor(max_workers=workers) as pool:
            codes = dict(pool.map(lambda job: run('compile-' + job[0], job[1]), jobs))
        if any(codes.values()):
            raise RuntimeError('CDC simulation compilation failed')
        phases = [0, 1, 2, 1201, 2500, 4999, 5000, 5001, 7500, 9998, 9999]
        cases = [(name + '-phase' + str(phase), name, phase, None) for name in ('zero-delay', 'bounded-delay') for phase in phases]
        cases += [('request-too-late', 'request-too-late', 0, 'request payload captured before settling'),
                  ('response-too-late', 'response-too-late', 0, 'response payload captured before settling')]
        save(stage='parallel-phase-and-delay-simulations', cases=cases)
        print(f'RUNNING {len(cases)} CDC simulations with {workers} workers', flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = dict(pool.map(lambda case: run(case[0], ['vvp', str(out / (case[1] + '.vvp')), '+PHASE_PS=' + str(case[2])]), cases))
        observed = []
        for name, variant, phase, rejection in cases:
            log = (out / (name + '.log')).read_text()
            if rejection:
                if results[name] != 1 or rejection not in log:
                    raise ValueError('Late-payload fault was not detected: ' + name)
                continue
            if results[name] != 0:
                raise RuntimeError('CDC phase simulation failed: ' + name)
            match = re.search(r'^PASS\|(.+)$', log, re.M)
            if not match:
                raise ValueError('CDC pass marker missing')
            row = {key: int(value) for key, value in (field.split('=') for field in match[1].split('|'))}
            if row['requests'] != 17 or row['responses'] != 17 or row['phase_ps'] != phase:
                raise ValueError('CDC simulation scope differs')
            observed.append({'variant': variant, **row})
        if describe(source) != info['production_source']:
            raise ValueError('Production mailbox changed during simulation')
        shutil.copy2(__file__, out / 'helper.py')
        save(status='ALL_MAILBOX_DIGITAL_LATENCY_AND_BOUNDED_BUS_DELAY_CASES_PASS', native_results=results, observations=observed,
             summary={'positive_cases': len(observed), 'expected_fault_cases': 2, 'transactions_per_case': 17,
                      'request_datapath_budget_ps': 20000, 'response_datapath_budget_ps': 300000,
                      'minimum_request_capture_ps': min(row['request_min_ps'] for row in observed),
                      'minimum_response_capture_ps': min(row['response_min_ps'] for row in observed)},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({'status': info['status'], 'summary': info['summary']}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        shutil.copy2(__file__, out / 'helper.py')
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('inventory', 'source-proof', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error('Expected one to eight simulation workers')
    simulate(args.inventory.resolve(), args.source_proof.resolve(), args.out.resolve(), args.workers)


if __name__ == '__main__':
    main()
