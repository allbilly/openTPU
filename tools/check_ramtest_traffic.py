#!/usr/bin/env python3
"""Check generated MIG traffic logic with a stalled memory model, not a PHY.

Simulation covers a 128-KiB address window using the same 28-bit native address
geometry as the full-capacity image. Physical 2-GiB coverage is checked on card.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import shutil

try:
    from .fedora_build_ramtest_mig import BOARD, PATTERNS, patch_traffic_bounds, patch_prbs_handshake, patch_constant_ready
except ImportError:
    from fedora_build_ramtest_mig import BOARD, PATTERNS, patch_traffic_bounds, patch_prbs_handshake, patch_constant_ready


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ip', type=Path, required=True, help='generated example_design/rtl/traffic_gen directory')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--simulator', choices=('iverilog', 'verilator'), default='iverilog')
    parser.add_argument('--pattern', choices=(*PATTERNS, 'injected-error'), action='append',
                        help='select individual trials; default runs the complete suite')
    parser.add_argument('--diagnostic-no-stalls', action='store_true',
                        help='isolate backpressure effects; this cannot qualify the stalled-port suite')
    parser.add_argument('--fix-prbs-handshake', action='store_true',
                        help='check the accepted-transfer PRBS correction used by PRBS image builds')
    args = parser.parse_args()
    patterns = args.pattern or [*PATTERNS, 'injected-error']
    vendor = sorted(args.ip.glob('*.v'))
    if len(vendor) < 10:
        parser.error('Expected generated MIG traffic generator Verilog files')
    args.out.mkdir(parents=True, exist_ok=False)
    # Match the diagnostic's traffic-only native-address correction. Preserve
    # the input IP tree and retain a separate patched copy and exact diff.
    local_vendor = args.out / 'traffic_gen'
    shutil.copytree(args.ip, local_vendor)
    cmd_gen = local_vendor / 'mig_7series_v4_2_cmd_gen.v'
    if "else if ( calc_end_addr >= end_addr_i[31:8] )" in cmd_gen.read_text():
        (args.out / 'vendor-traffic-bounds.patch').write_text(patch_traffic_bounds(cmd_gen))
    else:
        expected = "else if (({1'b0,addr_out} + (33'd8 * bl_out)) > ({1'b0,end_addr_i} + 33'd1))"
        if expected not in cmd_gen.read_text():
            raise ValueError('Unrecognized traffic boundary logic')
    vendor = sorted(local_vendor.glob('*.v'))
    if args.fix_prbs_handshake or 'prbs' in patterns:
        if 'input        prbs_advance_i,' not in (local_vendor / 'mig_7series_v4_2_s7ven_data_gen.v').read_text():
            (args.out / 'vendor-prbs-handshake.patch').write_text(patch_prbs_handshake(local_vendor))
    if set(patterns) & {'zeros', 'ones'}:
        if '|| data_mode_i == 1 || data_mode_i == 2 || data_mode_i == 3)' not in (local_vendor / 'mig_7series_v4_2_vio_init_pattern_bram.v').read_text():
            (args.out / 'vendor-constant-ready.patch').write_text(patch_constant_ready(local_vendor))
    for name in ('tb_vendor_traffic.sv', 'ramtest_channel.sv'):
        shutil.copy2(BOARD / name, args.out / name)
    sources = [args.out / 'tb_vendor_traffic.sv', args.out / 'ramtest_channel.sv'] + vendor
    result = dict(status='RUNNING', physical_hardware_test=False, simulation_window_bytes=128 << 10,
                  simulator=args.simulator,
                  independent_stalls=not args.diagnostic_no_stalls,
                  sources={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}, trials=[])
    try:
        for name in patterns:
            mode, fixed = PATTERNS[name] if name != 'injected-error' else (2, 0)
            binary = args.out / name
            command = ['iverilog', '-g2012', '-s', 'tb_vendor_traffic',
                       '-P', f'tb_vendor_traffic.MODE={mode}',
                       '-P', f'tb_vendor_traffic.FIXED_DATA={fixed}',
                       '-P', f'tb_vendor_traffic.INJECT_ERROR={int(name == "injected-error")}',
                       '-P', f'tb_vendor_traffic.STALLS={int(not args.diagnostic_no_stalls)}',
                       '-o', str(binary), *map(str, sources)]
            if args.simulator == 'verilator':
                object_dir = (args.out / (name+'-obj')).resolve()
                command = ['verilator', '--binary', '--timing', '-Wno-fatal', '-j', '2',
                           '--top-module', 'tb_vendor_traffic', '--Mdir', str(object_dir),
                           f'-GMODE={mode}', f'-GFIXED_DATA={fixed}',
                           f'-GINJECT_ERROR={int(name == "injected-error")}',
                           f'-GSTALLS={int(not args.diagnostic_no_stalls)}', *map(str, sources)]
                binary = object_dir / 'Vtb_vendor_traffic'
            with (args.out / f'{name}-compile.log').open('w') as log:
                subprocess.run(command, check=True, stdout=log, stderr=subprocess.STDOUT)
            log_path = args.out / f'{name}.log'
            with log_path.open('w') as log:
                command = ['vvp', '-i', str(binary)] if args.simulator == 'iverilog' else [str(binary)]
                run = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, timeout=180)
            output = log_path.read_text()
            expected = ('PASS_INJECTED_DATA_ERROR_DETECTED' if name == 'injected-error'
                        else 'PASS_VENDOR_TRAFFIC_STALLS_FULL_RANGE')
            trial = dict(pattern=name, returncode=run.returncode, pass_marker=expected in output,
                         fatal_diagnostic=any(s in output for s in ('FATAL:', '%Fatal:', '%Error:'))
                            or ('ERROR:' in output and name != 'injected-error'))
            result['trials'].append(trial)
            print(json.dumps(trial), flush=True)
            if run.returncode or not trial['pass_marker'] or trial['fatal_diagnostic']:
                raise RuntimeError(f'{name} failed; see {args.out}/{name}.log')
        result['status'] = ('DIAGNOSTIC_NO_STALLS_PASS' if args.diagnostic_no_stalls else
            'PASS_VENDOR_TRAFFIC_MODEL_ALL_PATTERNS_STALLS_AND_ERROR_DETECTION'
            if set(patterns) == {*PATTERNS, 'injected-error'} else 'PASS_SELECTED_VENDOR_TRAFFIC_MODEL_TRIALS')
        return 0
    except Exception as error:
        result.update(status='FAIL', error=str(error))
        raise
    finally:
        (args.out / 'manifest.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    raise SystemExit(main())
