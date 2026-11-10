#!/usr/bin/env python3
"""Prepare historical RAM-only YPCB MIG sources for offline analysis.

Requires Vivado with Kintex-7 support on Linux. Generates vendor RTL locally;
no accelerator, PCIe, host DMA or firmware is part of this diagnostic image.
Implementation is retired because new images require both runtime interfaces.
"""
from __future__ import annotations

import argparse
import difflib
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET

try:
    from .workspace_paths import vivado_bin
except ImportError:
    from workspace_paths import vivado_bin

ROOT = Path(__file__).resolve().parents[1]
BOARD = ROOT / 'boards/ypcb-00338/ramtest'
PATTERNS = {'address': (2, 0), 'prbs': (7, 0), 'walking1': (5, 0),
            'walking0': (6, 0), 'zeros': (1, 0), 'ones': (1, 0xffffffff)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def configure(source, target, speed):
    if speed not in (800, 1066):
        raise ValueError('Supported MIG rates are DDR3-800 and DDR3-1066')
    tree = ET.parse(source)
    controllers = tree.getroot().findall('Controller')
    if len(controllers) != 2:
        raise ValueError('Expected exactly two DDR controllers')
    for controller in controllers:
        for key, value in {'DataWidth': '72', 'ECC': 'Enabled', 'RowAddress': '15',
                           'ColAddress': '10', 'BankAddress': '3', 'PortInterface': 'NATIVE',
                           'TimePeriod': '1875', 'MMCM_VCO': '1066',
                           'mrCasLatency': '7', 'mr2CasWriteLatency': '6'}.items():
            if controller.findtext(key) != value:
                raise ValueError(f'Unexpected MIG geometry/interface: {key}')
        if speed == 800:
            for key, value in {'TimePeriod': '2500', 'MMCM_VCO': '800',
                               'mrCasLatency': '6', 'mr2CasWriteLatency': '5'}.items():
                controller.find(key).text = value
    ET.indent(tree, space='  ')
    tree.write(target, encoding='UTF-8', xml_declaration=True)


def patch_traffic_bounds(path):
    """Use native BL8 word units in the 4:1 V7 example's burst bounds.

    The generated legacy boundary expressions combine byte-oriented quantities
    and clip read bursts without changing the sequential address stride. Keep
    the vendor controller/PHY untouched; retain the exact traffic-only diff.
    """
    original = text = path.read_text()
    changes = {
        'else if ( calc_end_addr >= end_addr_i[31:8] )':
            'else if (({1\'b0,addr_out} + (33\'d8 * bl_out)) > ({1\'b0,end_addr_i} + 33\'d1))',
        'else if ((dummy_sub[32] == 0) || (buf_avail_r <= 50 && PORT_MODE == "RD_MODE"))':
            'else if ((({1\'b0,addr_out} + (33\'d8 * bl_out)) > ({1\'b0,end_addr_i} + 33\'d1)) || (buf_avail_r <= 50 && PORT_MODE == "RD_MODE"))',
    }
    for old, new in changes.items():
        if text.count(old) != 1:
            raise ValueError('Generated traffic boundary logic differs from reviewed version')
        text = text.replace(old, new)
    path.write_text(text)
    return ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                      fromfile='a/'+path.name, tofile='b/'+path.name))


def patch_prbs_handshake(directory):
    """Advance mode-7 PRBS only when its write/read payload is transferred."""
    originals = {}

    def change(name, old, new, count=1):
        path = directory / name
        text = path.read_text()
        if text.count(old) != count:
            raise ValueError('Generated PRBS handshake differs from reviewed source: '+name)
        originals.setdefault(name, text)
        path.write_text(text.replace(old, new))

    change('mig_7series_v4_2_s7ven_data_gen.v', '   input        data_rdy_i,',
           '   input        data_rdy_i,\n   input        prbs_advance_i,')
    change('mig_7series_v4_2_s7ven_data_gen.v', '.clk_en_i        (data_clk_en),',
           ".clk_en_i        ((data_mode_i == 4'd7) ? prbs_advance_i : data_clk_en),")
    change('mig_7series_v4_2_wr_data_gen.v', '   .data_rdy_i         (data_rdy_i    ),',
           '   .data_rdy_i         (data_rdy_i    ),\n   .prbs_advance_i     (data_rdy_i && data_valid_o),')
    change('mig_7series_v4_2_rd_data_gen.v', '   .data_rdy_i         (data_rdy_i    ),',
           '   .data_rdy_i         (data_rdy_i    ),\n   .prbs_advance_i     (data_rdy_i),', count=2)
    return ''.join(''.join(difflib.unified_diff(text.splitlines(True),
                   (directory / name).read_text().splitlines(True), fromfile='a/'+name, tofile='b/'+name))
                   for name, text in originals.items())


def patch_constant_ready(directory):
    """The mode-1 BRAM stays at slot 8; its readiness cannot wait for slot 7."""
    path = directory / 'mig_7series_v4_2_vio_init_pattern_bram.v'
    original = path.read_text()
    old = '|| data_mode_i == 2  || data_mode_i == 3)'
    if original.count(old) != 1:
        raise ValueError('Generated fixed-pattern readiness differs from reviewed source')
    patched = original.replace(old, '|| data_mode_i == 1 || data_mode_i == 2 || data_mode_i == 3)')
    path.write_text(patched)
    return ''.join(difflib.unified_diff(original.splitlines(True), patched.splitlines(True),
                                      fromfile='a/'+path.name, tofile='b/'+path.name))


def patch_runtime_pattern_reset(directory):
    """Delay traffic initialization until runtime controls settle after reset.

    The legacy generator can see calibration-ready throughout its own reset.
    Its initialization pulse then precedes the synchronized runtime controls,
    leaving the first burst length/stride inconsistent with the chosen pattern.
    Keep the controller/calibration signal untouched; delay only the example's
    local initialization state machine for 32 clocks after generator reset.
    """
    path = directory / 'mig_7series_v4_2_init_mem_pattern_ctr.v'
    original = text = path.read_text()
    changes = {
        'reg       memc_init_done_reg;':
            'reg       memc_init_done_reg;\nreg [5:0] runtime_settle_count;',
        '      memc_init_done_reg <= memc_init_done_i;':
            '''      // Diagnostic startup only: memory stays calibrated and refreshed.
      if (rst_i || !memc_init_done_i) begin
          runtime_settle_count <= 0;
          memc_init_done_reg <= 0;
      end else if (!runtime_settle_count[5]) begin
          runtime_settle_count <= runtime_settle_count + 1'b1;
          memc_init_done_reg <= 0;
      end else begin
          memc_init_done_reg <= 1;
      end''',
    }
    for old, new in changes.items():
        if text.count(old) != 1:
            raise ValueError('Generated runtime reset differs from reviewed source: '+path.name)
        text = text.replace(old, new)
    path.write_text(text)
    return ''.join(difflib.unified_diff(original.splitlines(True), text.splitlines(True),
                                      fromfile='a/'+path.name, tofile='b/'+path.name))


def adapt_example(text, speed, mask, pattern, build_id):
    """Fail closed if the generated vendor example no longer matches this ABI."""
    mode, fixed = PATTERNS[pattern]

    def replace(old, new):
        nonlocal text
        if text.count(old) != 1:
            raise ValueError('Unexpected generated MIG example: ' + old[:100])
        text = text.replace(old, new)

    replace('module example_top #', 'module ypcb_ramtest_mig #')
    # The example has one Inouts heading per controller; add ports at the first.
    pos = text.index('   inout [71:0]')
    text = text[:pos] + '   input SYS_CLK,\n   output [2:0] led,\n' + text[pos:]
    # The vendor example exposes summary outputs for an arbitrary carrier.
    # Keep their assignments internal; this board reports status through USER2
    # and its explicitly pinned LEDs, without allocating undocumented I/O pins.
    for name in ('tg_compare_error', 'init_calib_complete'):
        replace(f'   output                                       {name},\n', '')
    replace('   input                                        sys_rst\n',
            '   input                                        ramtest_unused_reset\n')
    # The reset pin is removed from the external interface. The board oscillator
    # releases MIG's active-low reset after 4096 50-MHz cycles after configuration.
    replace('   input                                        ramtest_unused_reset\n', '')
    text = re.sub(r'(input\s+c1_sys_clk_n),', r'\1', text, count=1)
    for channel in (0, 1):
        prefix = f'C{channel}_'
        values = {'END_ADDRESS': "32'h0fffffff", 'PRBS_EADDR_MASK_POS': "32'hf0000000",
                  'TST_MEM_INSTR_MODE': '"FIXED_INSTR_R_MODE"', 'CMD_PATTERN': '"CGEN_SEQUENTIAL"',
                  'DATA_MODE': f"4'd{mode}"}
        for key, value in values.items():
            expression = rf'(parameter\s+{prefix}{key}\s*=\s*)[^,\n]+'
            text, count = re.subn(expression, lambda m: m[1] + value, text)
            if count != 1:
                raise ValueError(f'Missing exact generated parameter {prefix}{key}')
        c = f'c{channel}'
        replace(f'.memc_init_done       ({c}_init_calib_complete)',
                f'.memc_init_done       ({c}_init_calib_complete && 1\'b{(mask >> channel) & 1})')
        replace(f'.manual_clear_error   ({c}_manual_clear_error)',
                ".manual_clear_error   (1'b0)")
        replace(f'assign {c}_wdt_en_w              = 1\'b1;',
                f'assign {c}_wdt_en_w              = 1\'b0;')
    # Both vendor traffic generators receive the selected constant.
    if text.count(".fixed_data_i         (32'b0),") != 2:
        raise ValueError('Expected exactly two fixed-data inputs')
    text = text.replace(".fixed_data_i         (32'b0),", f".fixed_data_i         (32'h{fixed:08x}),")
    if text.count('endmodule') != 1:
        raise ValueError('Expected one generated top module')
    extra = '''
  wire tg_compare_error, init_calib_complete;
  wire osc_ibuf, control_clk;
  IBUF u_osc_ibuf(.I(SYS_CLK), .O(osc_ibuf));
  BUFG u_osc_bufg(.I(osc_ibuf), .O(control_clk));
  reg [12:0] startup = 0;
  always @(posedge control_clk) if (!startup[12]) startup <= startup + 1'b1;
  wire sys_rst = startup[12];
  wire [1:0] snap_request, snap_ack;
  wire [2047:0] snapshot0, snapshot1;
'''
    for ch in (0, 1):
        c = f'c{ch}'
        extra += f'''
  ramtest_channel #(.ENABLED({(mask >> ch) & 1}), .PATTERN({mode})) u_observer{ch} (
    .clk({c}_clk), .ui_rst({c}_rst), .calibrated({c}_init_calib_complete),
    .pattern_initialized({c}_mem_pattern_init_done), .compare_error({c}_tg_compare_error),
    .watchdog_errors({{{c}_rd_wdt_err_w,{c}_wr_wdt_err_w,{c}_cmd_wdt_err_w}}),
    .command_valid({c}_app_en), .command_ready({c}_app_rdy),
    .command({c}_app_cmd), .address({c}_app_addr),
    .read_valid({c}_app_rd_data_valid), .compare_valid({c}_cmp_data_valid),
    .compare_bad({c}_cmp_error), .ecc_single({c}_app_ecc_single_err),
    .ecc_multiple({c}_app_ecc_multiple_err), .error_status({c}_error_status),
    .lane_errors({c}_cumlative_dq_lane_error),
    .snapshot_request(snap_request[{ch}]), .snapshot_ack(snap_ack[{ch}]),
    .snapshot(snapshot{ch}));
'''
    extra += f'''
  ramtest_jtag #(.BUILD_ID(32'h{build_id:08x}), .DDR_MTS({speed}),
                 .CHANNEL_MASK({mask}), .PATTERN({mode})) u_status (
    .clk(control_clk), .rst(!sys_rst), .snapshot0(snapshot0), .snapshot1(snapshot1),
    .snapshot_ack(snap_ack), .snapshot_request(snap_request), .led(led));
'''
    return text.replace('endmodule', extra + '\nendmodule')


def run(command, out, name):
    (out / f'{name}.command.json').write_text(json.dumps(list(map(str, command)), indent=2)+'\n')
    with (out / f'{name}.log').open('w') as log:
        code = subprocess.run(list(map(str, command)), stdout=log, stderr=subprocess.STDOUT).returncode
    (out / f'{name}.exit').write_text(str(code)+'\n')
    if code:
        raise RuntimeError(f'{name} exited {code}; see {out}/{name}.log')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--vivado', default=str(vivado_bin() / 'vivado'))
    parser.add_argument('--cxx', default='g++', help='compiler for the independent packet CRC audit')
    parser.add_argument('--ddr-mts', type=int, choices=(800, 1066), default=800)
    parser.add_argument('--channels', choices=('0', '1', 'both'), default='both')
    parser.add_argument('--pattern', choices=PATTERNS, default='address')
    parser.add_argument('--build-id', type=lambda s: int(s, 16), default=0xc0161001)
    parser.add_argument('--prepare-only', action='store_true',
                        help='generate historical IP/source only; ineligible for new-image implementation')
    args = parser.parse_args()
    if not args.prepare_only:
        parser.error('RAM-only implementation is retired: every new image requires '
                     'both JTAG and PCIe runtime memory/control interfaces. '
                     'Use --prepare-only only for historical source analysis.')
    if not 0 <= args.build_id <= 0xffffffff:
        parser.error('--build-id must fit in 32 bits')
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    mask = {'0': 1, '1': 2, 'both': 3}[args.channels]
    manifest = dict(status='GENERATING_MIG_IP', started_utc=datetime.now(timezone.utc).isoformat(),
                    implementation_admitted=False, mandatory_runtime_interfaces_satisfied=False,
                    admission_reason='Historical RAM-only source lacks PCIe and accelerator runtime control',
                    physical_tests_performed=False, purpose='RAM-only vendor MIG reference',
                    ddr_mts=args.ddr_mts, channels=mask, pattern=args.pattern,
                    build_id=f'{args.build_id:08x}', bytes_per_channel=1 << 31,
                    native_address_last='0x0ffffff8', sources={})
    mp = out / 'manifest.json'

    def save():
        mp.write_text(json.dumps(manifest, indent=2)+'\n')

    save()
    try:
        snapshot = out / 'source'
        snapshot.mkdir()
        for path in (BOARD / 'ramtest_channel.sv', BOARD / 'ramtest_jtag.sv',
                     BOARD / 'ramtest.xdc', BOARD / 'ramtest_cdc.tcl',
                     BOARD / 'build.tcl', BOARD / 'mig-ddr3-1066.prj',
                     ROOT / 'tools/openxc7_bitstream_crc.cc',
                     ROOT / 'rtl/boards/ypcb-00338/otpu_jtag_mailbox.sv', Path(__file__)):
            shutil.copy2(path, snapshot / path.name)
            manifest['sources'][str(path.relative_to(ROOT))] = sha(path)
        configure(snapshot / 'mig-ddr3-1066.prj', out / 'otpu_mig_ddr3.prj', args.ddr_mts)
        (out / 'generate.tcl').write_text('''set out [lindex $argv 0]
create_project ramtest_ip $out/ip-project -part xc7k480tffg1156-2 -force
file mkdir $out/ip
create_ip -name mig_7series -vendor xilinx.com -library ip -version 4.2 -module_name otpu_mig_ddr3 -dir $out/ip
set_property CONFIG.XML_INPUT_FILE $out/otpu_mig_ddr3.prj [get_ips otpu_mig_ddr3]
generate_target all [get_ips otpu_mig_ddr3]
report_ip_status -file $out/ip-status.rpt
close_project
exit
''')
        run([args.vivado, '-mode', 'batch', '-nojournal', '-nolog', '-source', out / 'generate.tcl',
             '-tclargs', out], out, 'generate')
        vendor = out / 'ip/otpu_mig_ddr3/otpu_mig_ddr3/example_design/rtl/example_top.v'
        manifest['vendor_example_sha256'] = sha(vendor)
        cmd_gen = vendor.parent / 'traffic_gen/mig_7series_v4_2_cmd_gen.v'
        manifest['traffic_bounds_original_sha256'] = sha(cmd_gen)
        (out / 'vendor-traffic-bounds.patch').write_text(patch_traffic_bounds(cmd_gen))
        if args.pattern == 'prbs':
            (out / 'vendor-prbs-handshake.patch').write_text(patch_prbs_handshake(cmd_gen.parent))
        if args.pattern in ('zeros', 'ones'):
            (out / 'vendor-constant-ready.patch').write_text(patch_constant_ready(cmd_gen.parent))
        manifest['traffic_bounds_patched_sha256'] = sha(cmd_gen)
        shutil.copytree(vendor.parent / 'traffic_gen', snapshot / 'traffic_gen')
        top = snapshot / 'ypcb_ramtest_mig.sv'
        top.write_text(adapt_example(vendor.read_text(), args.ddr_mts, mask, args.pattern, args.build_id))
        manifest['generated_top_sha256'] = sha(top)
        manifest['generated_prj_sha256'] = sha(out / 'otpu_mig_ddr3.prj')
        manifest['snapshot_source_sha256'] = {str(p.relative_to(snapshot)): sha(p)
                                               for p in sorted(snapshot.rglob('*')) if p.is_file()}
        manifest['status'] = 'RAM_ONLY_SOURCE_PREPARED_IMPLEMENTATION_NOT_RUN'
        save()
        if not args.prepare_only:
            manifest['status'] = 'RAM_ONLY_IMPLEMENTATION_RUNNING'
            save()
            run([args.vivado, '-mode', 'batch', '-nojournal', '-nolog', '-source', snapshot / 'build.tcl',
                 '-tclargs', out], out, 'build')
            for name, expected in manifest['snapshot_source_sha256'].items():
                if sha(snapshot / name) != expected:
                    raise RuntimeError('Frozen RAM test source changed during implementation: '+name)
            manifest['bitstream_sha256'] = sha(out / 'ramtest.bit')
            # Container/packet validation is independent from Vivado completion.
            from check_vivado_bitstream import parse_bitstream
            manifest['packet_check'] = parse_bitstream((out / 'ramtest.bit').read_bytes())
            run([args.cxx, '-std=c++17', '-O2', snapshot / 'openxc7_bitstream_crc.cc',
                 '-o', out / 'check-crc'], out, 'crc-compile')
            run([out / 'check-crc', out / 'ramtest.bit'], out, 'crc')
            manifest['crc'] = json.loads((out / 'crc.log').read_text())
            if manifest['crc']['status'] != 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH':
                raise RuntimeError('Independent bitstream CRC audit did not pass')
            skew = re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',
                              (out / 'reports/bus_skew.rpt').read_text(), re.M)
            if len(skew) != 4 or any(kind != 'MET' or float(value) < 0 for kind, value in skew):
                raise RuntimeError('RAM-test held-payload bus-skew checks did not all pass')
            manifest['bus_skew'] = dict(constraints=len(skew), minimum_slack_ns=min(float(x[1]) for x in skew))
            manifest['status'] = 'RAM_ONLY_BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING'
    except Exception as error:
        manifest.update(status='FAIL', error=str(error))
        print(error, file=sys.stderr)
        return 1
    finally:
        manifest['updated_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        print(mp)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
