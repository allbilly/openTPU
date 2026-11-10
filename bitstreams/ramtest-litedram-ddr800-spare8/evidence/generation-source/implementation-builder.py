#!/usr/bin/env python3
"""Build a RAM-only DDR800 LiteDRAM image through the normal native ECC ports.

Reuse the generated MIG traffic source and coverage observer from an address
preparation, replacing only its memory controller and status service. The
result contains neither the OpenTPU accelerator nor PCIe. No hardware access.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

sys.path.insert(0, '/home/fedora/openTPU/tools')
from ramtest_variant_profile import profile, FILES
from fedora_build_ramtest_mig import patch_prbs_handshake, patch_constant_ready, patch_runtime_pattern_reset

ROOT = Path('/home/fedora/openTPU')
BOARD = ROOT / 'boards/ypcb-00338/ramtest'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace(text, old, new, count=1):
    if text.count(old) != count:
        raise ValueError('Unexpected traffic source layout: ' + old[:100])
    return text.replace(old, new)


def controller():
    declarations = '''
  wire ld_sys_rst;
  wire [1:0] ld_traffic_reset, ld_traffic_pause;
  wire [1:0] ld_native_busy, ld_protocol_error;
  wire [3:0] ld_pattern, ld_instruction;
  wire [31:0] ld_fixed_data;
  wire [15:0] ld_awaddr, ld_araddr;
  wire [31:0] ld_wdata, ld_rdata;
  wire [3:0] ld_wstrb;
  wire [1:0] ld_bresp, ld_rresp;
  wire ld_awvalid, ld_awready, ld_wvalid, ld_wready, ld_bvalid, ld_bready;
  wire ld_arvalid, ld_arready, ld_rvalid, ld_rready;
  assign c1_clk = c0_clk;
'''
    connections = ['.clk50g(control_clk)', ".rst(1'b0)", '.sys_clk(c0_clk)', '.sys_rst(ld_sys_rst)',
                   '.ctl_clk(c0_clk)', '.ctl_rst(ld_sys_rst)']
    for name in ('awaddr', 'araddr', 'wdata', 'rdata', 'wstrb', 'bresp', 'rresp',
                 'awvalid', 'awready', 'wvalid', 'wready', 'bvalid', 'bready',
                 'arvalid', 'arready', 'rvalid', 'rready'):
        connections.append(f'.ctl_{name}(ld_{name})')
    for ch in (0, 1):
        c = f'c{ch}'
        declarations += f'''
  wire {c}_native_cmd_ready;
  wire {c}_native_cmd_valid, {c}_native_write;
  wire [24:0] {c}_native_address;
  assign {c}_rst = ld_sys_rst | ld_traffic_reset[{ch}];
  assign {c}_app_ecc_single_err = 0;
  assign {c}_app_ecc_multiple_err = 0;
  ramtest_litedram_command_bridge u_cmd_bridge{ch} (
    .clk({c}_clk), .rst({c}_rst), .app_valid({c}_app_en), .app_ready({c}_app_rdy),
    .app_command({c}_app_cmd), .app_address({c}_app_addr),
    .native_valid({c}_native_cmd_valid), .native_ready({c}_native_cmd_ready),
    .native_write({c}_native_write), .native_address({c}_native_address),
    .busy(ld_native_busy[{ch}]), .protocol_error(ld_protocol_error[{ch}]));
'''
        signals = dict(cmd_valid=f'{c}_native_cmd_valid',
                       cmd_ready=f'{c}_native_cmd_ready', cmd_we=f'{c}_native_write',
                       cmd_addr=f'{c}_native_address', wdata_valid=f'{c}_app_wdf_wren',
                       wdata_ready=f'{c}_app_wdf_rdy', wdata_data=f'{c}_app_wdf_data',
                       wdata_we=f'~{c}_app_wdf_mask', rdata_valid=f'{c}_app_rd_data_valid',
                       rdata_ready="1'b1", rdata_data=f'{c}_app_rd_data',
                       ready=f'{c}_init_calib_complete')
        connections += [f'.{c}_{name}({signal})' for name, signal in signals.items()]
        idle = dict(cmd_valid="1'b0", cmd_ready='', cmd_we="1'b0", cmd_addr="25'b0",
                    wdata_valid="1'b0", wdata_ready='', wdata_data="512'b0", wdata_we="64'b0",
                    rdata_valid='', rdata_ready="1'b1", rdata_data='')
        connections += [f'.{c}b_{name}({signal})' for name, signal in idle.items()]
        for name in ('dq', 'dqs_p', 'dqs_n', 'a', 'ba', 'ras_n', 'cas_n', 'we_n', 'reset_n',
                     'clk_p', 'clk_n', 'cke', 'cs_n', 'odt'):
            connections.append(f'.ddram{ch}_{name}(ddram{ch}_{name})')
    return declarations + '\n  otpu_litedram u_ld (\n    ' + ',\n    '.join(connections) + '\n  );\n'


def adapt_top(text, build_id, capture_first_read=False):
    text = replace(text, 'module ypcb_ramtest_mig #', 'module ypcb_ramtest_litedram #')
    start = text.index('  otpu_mig_ddr3 u_otpu_mig_ddr3')
    end = text.index('// End of User Design top instance', start)
    text = text[:start] + controller() + text[end:]
    # LiteDRAM uses the 50 MHz oscillator and its own 200 MHz reference PLL.
    # Remove the MIG-only differential reference pads from the top interface.
    text = '\n'.join(line for line in text.split('\n')
                     if not re.fullmatch(r'\s*input\s+c[01]_sys_clk_[pn],?\s*', line))
    header, rest = text.split(');', 1)
    lines = header.split('\n')
    for index in range(len(lines)-1, -1, -1):
        code = lines[index].split('//', 1)[0].rstrip()
        if code:
            if code.endswith(','):
                position = lines[index].index(',', len(code)-1)
                lines[index] = lines[index][:position] + lines[index][position+1:]
            break
    text = '\n'.join(lines) + ');' + rest
    for ch in (0, 1):
        for old, new in dict(addr='a', ck_p='clk_p', ck_n='clk_n', dq='dq', dqs_p='dqs_p',
                             dqs_n='dqs_n', ba='ba', ras_n='ras_n', cas_n='cas_n', we_n='we_n',
                             reset_n='reset_n', cke='cke', cs_n='cs_n', odt='odt').items():
            text = re.sub(r'\bc' + str(ch) + '_ddr3_' + old + r'\b', f'ddram{ch}_{new}', text)
        for name in ('clk_p', 'clk_n', 'cke', 'cs_n', 'odt'):
            text = re.sub(r'(output\s+)\[[^\]]+\](\s+ddram' + str(ch) + '_' + name + r'\b)',
                          r'\1\2', text)
        for name, value in {'modify_enable': "1'b1", 'data_mode_value': 'ld_pattern',
                            'instr_mode_value': 'ld_instruction',
                            'bl_mode_value': "2'b01", 'fixed_bl_value': "8'd64",
                            'pause_traffic': f'ld_traffic_pause[{ch}]'}.items():
            expression = rf'assign c{ch}_vio_{name}\s*=\s*[^;]+;'
            text, count = re.subn(expression, f'assign c{ch}_vio_{name} = {value};', text)
            if count != 1:
                raise ValueError('Missing VIO control: ' + name)
        text = replace(text, f'ramtest_channel #(.ENABLED(1), .PATTERN(2)) u_observer{ch}',
                       f'ramtest_ld_channel #(.ENABLED(1)) u_observer{ch}')
        text = replace(text, f'.clk(c{ch}_clk), .ui_rst(c{ch}_rst),',
                       f'.clk(c{ch}_clk), .ui_rst(c{ch}_rst), .pattern({{28\'b0,ld_pattern}}),\n'
                       f'    .paused(ld_traffic_pause[{ch}]), .write_data_valid(c{ch}_app_wdf_wren),\n'
                       f'    .write_data_ready(c{ch}_app_wdf_rdy),')
    text = replace(text, ".fixed_data_i         (32'h00000000),", '.fixed_data_i         (ld_fixed_data),', count=2)
    start = text.index('  ramtest_jtag #(')
    end = text.index(';', start) + 1
    status = f'''  ramtest_litedram_status #(.BUILD_ID(32'h{build_id:08x}), .DDR_MTS(800)) u_status (
    .clk(c0_clk), .rst(ld_sys_rst), .snapshot0(snapshot0), .snapshot1(snapshot1),
    .snapshot_ack(snap_ack), .snapshot_request(snap_request), .led(led),
    .calibrated({{c1_init_calib_complete,c0_init_calib_complete}}),
    .native_busy(ld_native_busy), .protocol_error(ld_protocol_error),
    .traffic_reset(ld_traffic_reset), .traffic_pause(ld_traffic_pause),
    .pattern_mode(ld_pattern), .instruction_mode(ld_instruction), .fixed_data(ld_fixed_data),
    .ctl_awaddr(ld_awaddr), .ctl_araddr(ld_araddr), .ctl_wdata(ld_wdata), .ctl_rdata(ld_rdata),
    .ctl_wstrb(ld_wstrb), .ctl_bresp(ld_bresp), .ctl_rresp(ld_rresp),
    .ctl_awvalid(ld_awvalid), .ctl_awready(ld_awready), .ctl_wvalid(ld_wvalid), .ctl_wready(ld_wready),
    .ctl_bvalid(ld_bvalid), .ctl_bready(ld_bready), .ctl_arvalid(ld_arvalid), .ctl_arready(ld_arready),
    .ctl_rvalid(ld_rvalid), .ctl_rready(ld_rready));'''
    text = text[:start] + status + text[end:]
    if capture_first_read:
        blocks = []
        for ch in (0, 1):
            blocks.append(f'''
  wire [1087:0] first_read_record{ch};
  ramtest_read_capture u_read_capture{ch} (
    .clk(c{ch}_clk), .rst(c{ch}_rst),
    .command_valid(c{ch}_app_en), .command_ready(c{ch}_app_rdy),
    .command(c{ch}_app_cmd), .address(c{ch}_app_addr),
    .read_valid(c{ch}_app_rd_data_valid), .read_data(c{ch}_app_rd_data),
    .expected_data(c{ch}_cmp_data), .record(first_read_record{ch}));
''')
        text = replace(text, '  ramtest_litedram_status #(', ''.join(blocks)+'  ramtest_litedram_status #(')
        text = replace(text, '    .native_busy(ld_native_busy), .protocol_error(ld_protocol_error),',
                       '    .first_read0(first_read_record0), .first_read1(first_read_record1),\n'
                       '    .native_busy(ld_native_busy), .protocol_error(ld_protocol_error),')
    return text


def capture_status(text):
    text = replace(text, '  input wire [2047:0] snapshot0, snapshot1,',
                   '  input wire [1087:0] first_read0, first_read1,\n'
                   '  input wire [2047:0] snapshot0, snapshot1,')
    text = replace(text, '4: response_data[31:0] <= 2;', '4: response_data[31:0] <= 3;')
    text = replace(text, "          'h40: response_data[31:0] <= {28'b0, instruction_mode};",
                   "          'h48: response_data[31:0] <= 32'h52444331; // RDC1 capture layout\n"
                   "          'h40: response_data[31:0] <= {28'b0, instruction_mode};")
    text = replace(text, "            else response_status <= 1;\n          end\n        endcase\n      end else if (opcode == 2",
                   "            else if (address >= 'h400 && address < 'h488)\n"
                   "              response_data[31:0] <= first_read0[address[7:2]*32+:32];\n"
                   "            else if (address >= 'h500 && address < 'h588)\n"
                   "              response_data[31:0] <= first_read1[address[7:2]*32+:32];\n"
                   "            else response_status <= 1;\n          end\n        endcase\n      end else if (opcode == 2")
    return text


LATE = r'''
create_clock -name jtag_tck -period 166.666667 [get_pins u_status/u_bscan/TCK]
foreach name {rq_sync rs_sync} {
    set all [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${name}_reg*"]
    set first {}
    foreach c $all {if {[regexp {\[0\]$} [get_property NAME $c]]} {lappend first $c}}
    if {[llength $all] != 3 || [llength $first] != 1} {error "Missing mailbox synchronizer $name"}
    set_property ASYNC_REG TRUE $all
    set_property DONT_TOUCH TRUE $all
    set_false_path -to [get_pins -of_objects $first -filter {REF_PIN_NAME == D}]
}
foreach {from_name to_name bound} {held req 20.000 response response_tck 166.666667} {
    set source [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${from_name}_reg*"]
    set target [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${to_name}_reg*"]
    if {![llength $source] || ![llength $target]} {error "Missing held mailbox payload"}
    set_max_delay -datapath_only -from $source -to $target $bound
    set_bus_skew -from $source -to $target $bound
}
set core [get_clocks -of_objects [get_pins u_ld/MMCME2_ADV/CLKOUT0]]
if {[llength $core] != 1 || abs([get_property PERIOD $core]-10.0)>0.001} {error "DDR800 sys clock differs"}
set regs50 [filter [all_registers -clock sys_clk_50] {NAME =~ u_ld/*}]
if {[llength $regs50] != 16} {error "LiteDRAM clock-reset chain count changed"}
set_false_path -from $core -to $regs50
'''

BUILD = r'''
set out [file normalize [lindex $argv 0]]
set_param general.maxThreads 2
if {[llength $argv] > 1} {
open_checkpoint [lindex $argv 1]
} else {
create_project ramtest_litedram $out/project -part xc7k480tffg1156-2 -force
read_verilog $out/core/otpu_litedram.v
add_files -norecurse $out/core/otpu_litedram_mem.init
set_property FILE_TYPE {Memory Initialization Files} [get_files otpu_litedram_mem.init]
foreach f [glob $out/source/*.sv] {read_verilog -sv $f}
foreach f [glob $out/source/traffic_gen/*.v] {read_verilog $f}
read_xdc $out/core/otpu_litedram.xdc
read_xdc $out/board.xdc
set_property verilog_define {SYNTHESIS} [current_fileset]
set_property top ypcb_ramtest_litedram [current_fileset]
synth_design -top ypcb_ramtest_litedram -part xc7k480tffg1156-2 -flatten_hierarchy rebuilt -retiming
write_checkpoint -force $out/synth.dcp
}
source $out/late.tcl
opt_design -directive Explore
place_design -directive Explore
phys_opt_design -directive AggressiveExplore
route_design -directive Explore -tns_cleanup
phys_opt_design -directive AggressiveExplore
file mkdir $out/reports
report_timing_summary -report_unconstrained -file $out/reports/timing.rpt
report_route_status -file $out/reports/route.rpt
report_drc -file $out/reports/drc.rpt
report_cdc -details -file $out/reports/cdc.rpt
report_bus_skew -file $out/reports/bus_skew.rpt
report_io -file $out/reports/io.rpt
report_clocks -file $out/reports/clocks.rpt
report_utilization -hierarchical -file $out/reports/utilization.rpt
foreach {ref expected} {PCIE_2_1 0 GTXE2_CHANNEL 0 BSCANE2 1 DSP48E1 0 ISERDESE2 136 OSERDESE2 205 IDELAYE2 136 PHASER_IN_PHY 0 PHASER_OUT_PHY 0} {
    set count [llength [get_cells -hier -filter "REF_NAME == $ref"]]
    if {$count != $expected} {error "Unexpected primitive $ref: $count instead of $expected"}
}
foreach mode {max min} {
    set path [get_timing_paths -delay_type $mode -max_paths 1]
    if {![llength $path] || [get_property SLACK $path] < 0} {error "RAM-only LiteDRAM $mode timing failed"}
}
set f [open $out/reports/timing.rpt]; set timing [read $f]; close $f
if {![regexp {All user specified timing constraints are met} $timing]} {error "Timing summary has violations"}
foreach violation [get_drc_violations -quiet] {
    if {[get_property SEVERITY $violation] in {Error {Critical Warning}}} {error "Blocking DRC: $violation"}
}
write_checkpoint -force $out/routed.dcp
write_bitstream -force $out/ramtest.bit
close_project
exit
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--core', type=Path, required=True, help='Checked full dual-channel DDR800 core')
    parser.add_argument('--traffic-build', type=Path, required=True, help='Prepared/built both-channel MIG address source')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--build-id', type=lambda value: int(value, 16), default=0xc0162010)
    parser.add_argument('--vivado', default='/home/fedora/vivado/2026.1/Vivado/bin/vivado')
    parser.add_argument('--cxx', default='g++')
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--capture-first-read', action='store_true',
                        help='Build LDRT ABI 3 with passive aligned first-mismatch read capture')
    parser.add_argument('--capture-model-review', type=Path,
                        help='Completed all-pattern/stalls/injected-error capture simulation manifest')
    parser.add_argument('--runtime-pattern-reset-fix', action='store_true',
                        help='Delay diagnostic initialization until runtime pattern controls settle after reset')
    parser.add_argument('--pattern-restart-model-review', type=Path,
                        help='Completed same-image six-pattern restart model for the exact patched traffic source')
    parser.add_argument('--reuse-synthesis', type=Path,
                        help='Prior build with identical RTL/core/pins and a completed synth.dcp; constraints are reapplied')
    args = parser.parse_args()
    if args.capture_first_read != bool(args.capture_model_review):
        parser.error('--capture-first-read requires --capture-model-review and vice versa')
    if args.runtime_pattern_reset_fix != bool(args.pattern_restart_model_review):
        parser.error('--runtime-pattern-reset-fix requires --pattern-restart-model-review and vice versa')
    if args.runtime_pattern_reset_fix and not args.capture_first_read:
        parser.error('Runtime pattern reset fix currently requires the ABI 3 capture model')
    if not 0 <= args.build_id <= 0xffffffff:
        parser.error('--build-id must fit a 32-bit register')
    core, traffic, out = args.core.resolve(), args.traffic_build.resolve(), args.out.resolve()
    checked = profile(core)
    metadata = json.loads((core / 'openxc7-profile.json').read_text())
    if (checked['parameters'] != dict(CORE_KHZ=100000, DDR_MTS=800) or
            metadata.get('physical_user_channels', [0, 1]) != [0, 1]):
        parser.error('Use a full two-channel DDR800 core; the CH1 fallback is not suitable')
    source = json.loads((traffic / 'manifest.json').read_text())
    if source['ddr_mts'] != 800 or source['channels'] != 3 or source['pattern'] != 'address':
        parser.error('Use the both-channel DDR800 address preparation as the traffic donor')
    for name, expected in source['snapshot_source_sha256'].items():
        if sha(traffic / 'source' / name) != expected:
            raise ValueError('Traffic donor snapshot changed: ' + name)
    out.mkdir(parents=True, exist_ok=False)
    receipt = dict(status='PREPARING_RAM_ONLY_LITEDRAM', build_id=f'{args.build_id:08x}',
                   started_utc=datetime.now(timezone.utc).isoformat(), hardware_accessed=False,
                   physical_tests_performed=False, ddr_mts=800, sys_hz=100000000,
                   physical_user_channels=[0, 1], bytes_per_channel=1 << 31,
                   ecc_path='CH0 512-bit non-ECC with partial-write RMW; CH1 ECC; port B idle',
                   identity='LDRT', abi=3 if args.capture_first_read else 2, cpu_calibration_retained=True,
                   capture_first_read=args.capture_first_read,
                   runtime_pattern_reset_fix=args.runtime_pattern_reset_fix,
                   donor_manifest_sha256=sha(traffic / 'manifest.json'),
                   source_core_manifest_sha256=sha(core / 'openxc7-profile.json'),
                   source_builder_sha256=sha(Path(__file__)))

    def save():
        receipt['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temporary = out / 'manifest.json.tmp'
        temporary.write_text(json.dumps(receipt, indent=2) + '\n')
        temporary.replace(out / 'manifest.json')

    def run(command, name):
        (out / (name + '.command.json')).write_text(json.dumps(list(map(str, command)), indent=2) + '\n')
        with (out / (name + '.log')).open('w') as log:
            result = subprocess.run(list(map(str, command)), cwd=out, stdout=log, stderr=subprocess.STDOUT)
        receipt[name + '_exit'] = result.returncode
        save()
        if result.returncode:
            raise RuntimeError(name + ' failed; see ' + str(out / (name + '.log')))

    save()
    try:
        snapshot = out / 'source'
        snapshot.mkdir()
        shutil.copytree(traffic / 'source/traffic_gen', snapshot / 'traffic_gen')
        (out / 'vendor-prbs-handshake.patch').write_text(patch_prbs_handshake(snapshot / 'traffic_gen'))
        (out / 'vendor-constant-ready.patch').write_text(patch_constant_ready(snapshot / 'traffic_gen'))
        if args.runtime_pattern_reset_fix:
            (out / 'vendor-runtime-pattern-reset.patch').write_text(patch_runtime_pattern_reset(snapshot / 'traffic_gen'))
        original = (traffic / 'source/ypcb_ramtest_mig.sv').read_text()
        top = adapt_top(original, args.build_id, args.capture_first_read)
        (snapshot / 'ypcb_ramtest_litedram.sv').write_text(top)
        (out / 'controller-and-status.patch').write_text(''.join(difflib.unified_diff(
            original.splitlines(True), top.splitlines(True), fromfile='a/ypcb_ramtest_mig.sv',
            tofile='b/ypcb_ramtest_litedram.sv')))
        observer = (BOARD / 'ramtest_channel.sv').read_text()
        observer = replace(observer, 'module ramtest_channel #(', 'module ramtest_ld_channel #(')
        observer = replace(observer, '  parameter integer PATTERN = 2,\n', '')
        observer = replace(observer, '  input wire clk, ui_rst, calibrated, pattern_initialized, compare_error,',
                           '  input wire [31:0] pattern,\n'
                           '  input wire paused, write_data_valid, write_data_ready,\n'
                           '  input wire clk, ui_rst, calibrated, pattern_initialized, compare_error,')
        observer = replace(observer, 'snapshot[32+:32] <= PATTERN;', 'snapshot[32+:32] <= pattern;')
        observer = replace(observer, '  reg [63:0] ticks=0;',
                           '  reg [63:0] written=0;\n'
                           '  reg [31:0] combined_passes=0, combined_gaps=0;\n'
                           '  reg [28:0] next_command=0;\n'
                           '  reg command_run=0;\n  reg [63:0] ticks=0;')
        observer = replace(observer, '      writes<=0; reads<=0; returned<=0; compared<=0; bad<=0; ce<=0; ue<=0;',
                           '      written<=0; combined_passes<=0; combined_gaps<=0; next_command<=0; command_run<=0;\n'
                           '      writes<=0; reads<=0; returned<=0; compared<=0; bad<=0; ce<=0; ue<=0;')
        observer = replace(observer, '      if (ENABLED && calibrated) begin',
                           '      if (ENABLED && calibrated && !paused) begin')
        observer = replace(observer, '      if (read_valid) begin', '''
      if (write_data_valid && write_data_ready) written <= written + 1'b1;
      // Mixed traffic uses a shared sequential command address stream. Count
      // complete combined traversals separately from pure read/write passes.
      if (accepted) begin
        if (address == 0) begin command_run<=1; next_command<=8; end
        else if (command_run && address == next_command) begin
          next_command <= address + 8;
          if (address == LAST_ADDR) begin combined_passes<=combined_passes+1'b1; command_run<=0; end
        end else begin command_run<=0; combined_gaps<=combined_gaps+1'b1; end
      end
      if (read_valid) begin''')
        observer = replace(observer, '      snapshot[704+:1088] <= error_status;',
                           '      snapshot[704+:1088] <= error_status;\n'
                           '      // LDRT repurposes the unverified vendor address/status words.\n'
                           '      snapshot[704+:32] <= combined_passes;\n'
                           '      snapshot[736+:32] <= combined_gaps;')
        observer = replace(observer, '      snapshot[1920+:64] <= compared;',
                           '      snapshot[1920+:64] <= compared;\n'
                           '      snapshot[1984+:64] <= written;')
        (snapshot / 'ramtest_ld_channel.sv').write_text(observer)
        shutil.copy2(BOARD / 'litedram_status.sv', snapshot / 'litedram_status.sv')
        if args.capture_first_read:
            status_file = snapshot/'litedram_status.sv'
            status_file.write_text(capture_status(status_file.read_text()))
            shutil.copy2(BOARD/'read_capture.sv', snapshot/'read_capture.sv')
        shutil.copy2(BOARD / 'litedram_command_bridge.sv', snapshot / 'litedram_command_bridge.sv')
        if args.capture_first_read:
            model = json.loads(args.capture_model_review.read_text())
            if (model.get('status') != 'PASS_VENDOR_TRAFFIC_MODEL_ALL_PATTERNS_STALLS_AND_ERROR_DETECTION'
                    or not all(model.get(k) for k in
                               ('independent_stalls', 'litedram_command_bridge', 'capture_first_read'))):
                raise ValueError('Complete read-capture model qualification is required')
            require_names = {'address', 'zeros', 'ones', 'walking1', 'walking0', 'prbs', 'injected-error'}
            if {t['pattern'] for t in model['trials']} != require_names or any(
                    t['returncode'] or not t['pass_marker'] or t['fatal_diagnostic'] for t in model['trials']):
                raise ValueError('Read-capture simulation coverage differs')
            tested = {Path(p).name: digest for p, digest in model['sources'].items()}
            for tested_file in [snapshot/'read_capture.sv', snapshot/'litedram_command_bridge.sv',
                                *sorted((snapshot/'traffic_gen').glob('*.v'))]:
                if tested.get(tested_file.name) != sha(tested_file):
                    raise ValueError('Implemented capture/traffic source differs from model: '+tested_file.name)
            shutil.copy2(args.capture_model_review, snapshot/'read-capture-model.json')
            receipt['capture_model_review_sha256'] = sha(snapshot/'read-capture-model.json')
        if args.runtime_pattern_reset_fix:
            model = json.loads(args.pattern_restart_model_review.read_text())
            if (model.get('status') != 'PASS_SAME_IMAGE_PATTERN_RESTART_MODEL_ALL_SIX_AND_RETURN_TO_ADDRESS'
                    or not all(model.get(k) for k in ('runtime_pattern_reset_fix', 'independent_stalls',
                        'command_bridge', 'first_read_capture', 'calibration_ready_retained'))
                    or model.get('memory_model_reset_between_patterns') is not False
                    or len(model.get('epoch_results', [])) != 7):
                raise ValueError('Complete same-image pattern restart model is required')
            tested = {Path(p).name: digest for p, digest in model['source_hashes'].items()}
            for tested_file in [snapshot/'read_capture.sv', snapshot/'litedram_command_bridge.sv',
                                *sorted((snapshot/'traffic_gen').glob('*.v'))]:
                if tested.get(tested_file.name) != sha(tested_file):
                    raise ValueError('Implemented pattern restart source differs from model: '+tested_file.name)
            shutil.copy2(args.pattern_restart_model_review, snapshot/'pattern-restart-model.json')
            receipt['pattern_restart_model_review_sha256'] = sha(snapshot/'pattern-restart-model.json')
        shutil.copy2(ROOT / 'rtl/boards/ypcb-00338/otpu_jtag_mailbox.sv', snapshot / 'otpu_jtag_mailbox.sv')
        shutil.copy2(Path(__file__), snapshot / 'builder.py')
        shutil.copy2(ROOT / 'tools/openxc7_bitstream_crc.cc', snapshot / 'openxc7_bitstream_crc.cc')
        (out / 'core').mkdir()
        for name in list(FILES.values()) + ['openxc7-profile.json', 'variant-profile.json'] + ['sdram_init_ch0.py']:
            shutil.copy2(core / name, out / 'core' / name)
        board = ['create_clock -name sys_clk_50 -period 20.0 [get_ports SYS_CLK]',
                 'set_property LOC MMCME2_ADV_X0Y2 [get_cells u_ld/ldmmcm0]',
                 'set_property LOC MMCME2_ADV_X0Y6 [get_cells u_ld/ldmmcm1]',
                 'set_property CFGBVS GND [current_design]',
                 'set_property CONFIG_VOLTAGE 1.8 [current_design]',
                 'set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]',
                 'set_property BITSTREAM.CONFIG.UNUSEDPIN PULLNONE [current_design]']
        for port, pad in {'SYS_CLK': 'AA28', 'led[0]': 'P30', 'led[1]': 'M30', 'led[2]': 'N30'}.items():
            board += [f'set_property PACKAGE_PIN {pad} [get_ports {{{port}}}]',
                      f'set_property IOSTANDARD LVCMOS18 [get_ports {{{port}}}]']
        board += ['set_false_path -to [get_ports {led[*]}]']
        (out / 'board.xdc').write_text('\n'.join(board) + '\n')
        (out / 'late.tcl').write_text(LATE)
        (out / 'build.tcl').write_text(BUILD)
        receipt['frozen_files'] = {str(p.relative_to(out)): sha(p) for directory in (snapshot, out / 'core')
                                   for p in sorted(directory.rglob('*')) if p.is_file()}
        receipt['frozen_files'].update({name: sha(out / name) for name in ('board.xdc', 'late.tcl', 'build.tcl')})
        checkpoint = None
        if args.reuse_synthesis:
            prior = args.reuse_synthesis.resolve()
            previous = json.loads((prior / 'manifest.json').read_text())
            prior_checkpoint = prior / 'synth.dcp'
            if not prior_checkpoint.is_file():
                raise ValueError('Prior synthesis checkpoint is missing')
            for name, expected in receipt['frozen_files'].items():
                if name in ('source/builder.py', 'late.tcl', 'build.tcl'):
                    continue
                if (previous['frozen_files'].get(name) != expected or
                        sha(prior / name) != expected):
                    raise ValueError('Cannot reuse synthesis after input changed: ' + name)
            checkpoint = out / 'reused-synth.dcp'
            shutil.copy2(prior_checkpoint, checkpoint)
            receipt['reused_synthesis'] = dict(build=str(prior),
                manifest_sha256=sha(prior / 'manifest.json'), checkpoint_sha256=sha(checkpoint),
                scope='Identical RTL, memory initialization, board pins and core constraints; late constraints reapplied')
        receipt['status'] = 'RAM_ONLY_LITEDRAM_SOURCE_PREPARED_IMPLEMENTATION_NOT_RUN'
        save()
        if args.prepare_only:
            return 0
        receipt['status'] = 'RAM_ONLY_LITEDRAM_IMPLEMENTATION_RUNNING'
        save()
        command = [args.vivado, '-mode', 'batch', '-nojournal', '-nolog', '-source', out / 'build.tcl',
                   '-tclargs', out]
        if checkpoint is not None:
            command.append(checkpoint)
        run(command, 'build')
        if checkpoint is not None and sha(checkpoint) != receipt['reused_synthesis']['checkpoint_sha256']:
            raise ValueError('Reused synthesis checkpoint changed during implementation')
        for name, expected in receipt['frozen_files'].items():
            if sha(out / name) != expected:
                raise ValueError('Frozen source changed during build: ' + name)
        from check_vivado_bitstream import parse_bitstream
        receipt['bitstream_sha256'] = sha(out / 'ramtest.bit')
        receipt['packet_check'] = parse_bitstream((out / 'ramtest.bit').read_bytes())
        run([args.cxx, '-std=c++17', '-O2', snapshot / 'openxc7_bitstream_crc.cc', '-o', out / 'check-crc'], 'crc-compile')
        run([out / 'check-crc', out / 'ramtest.bit'], 'crc')
        receipt['crc'] = json.loads((out / 'crc.log').read_text())
        if receipt['crc']['status'] != 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH':
            raise ValueError('Independent bitstream CRC failed')
        receipt['status'] = 'RAM_ONLY_LITEDRAM_BITSTREAM_BUILT_CDC_AND_PHYSICAL_REVIEW_PENDING'
        return 0
    except Exception as error:
        receipt.update(status='FAIL', error=str(error))
        print(error, file=sys.stderr)
        return 1
    finally:
        save()
        print(out / 'manifest.json')


if __name__ == '__main__':
    raise SystemExit(main())
