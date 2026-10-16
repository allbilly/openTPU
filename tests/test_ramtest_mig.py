"""RAM diagnostic coverage, snapshot decoding and read-only Mac discovery."""
import json
from pathlib import Path
import shutil
import subprocess
import xml.etree.ElementTree as ET

import pytest

from tools.fedora_build_ramtest_mig import BOARD, adapt_example, configure, patch_traffic_bounds
from tools.mac_fpga_setup_check import usb_devices
from tools.probe_ramtest_mig import decode, verdict


def test_usb_inventory_discards_serials_and_locations():
    raw = {'SPUSBDataType': [{'_name': 'bus', '_items': [
        {'_name': 'Platform Cable', 'vendor_id': '0x03fd (Xilinx)',
         'product_id': '0x0008', 'serial_num': 'SECRET', 'location_id': 'PRIVATE'}]}]}
    result = usb_devices(raw)
    assert result == [{'name': 'Platform Cable', 'vendor_id': '0x03fd', 'product_id': '0x0008'}]
    assert 'SECRET' not in json.dumps(result)
    assert 'PRIVATE' not in json.dumps(result)


def test_ddr800_changes_timings_but_preserves_all_board_pins(tmp_path):
    source = BOARD / 'mig-ddr3-1066.prj'
    target = tmp_path / 'ddr800.prj'
    configure(source, target, 800)
    original = ET.parse(source).getroot().findall('Controller')
    changed = ET.parse(target).getroot().findall('Controller')
    for before, after in zip(original, changed):
        assert ET.tostring(before.find('PinSelection')) == ET.tostring(after.find('PinSelection'))
        assert after.findtext('TimePeriod') == '2500'
        assert after.findtext('MMCM_VCO') == '800'
        assert after.findtext('mrCasLatency') == '6'
        assert after.findtext('mr2CasWriteLatency') == '5'


def test_native_bound_patch_changes_only_the_two_reviewed_expressions(tmp_path):
    path = tmp_path / 'cmd_gen.v'
    original = '''else if ( calc_end_addr >= end_addr_i[31:8] )
else if ((dummy_sub[32] == 0) || (buf_avail_r <= 50 && PORT_MODE == "RD_MODE"))
'''
    path.write_text(original)
    patch = patch_traffic_bounds(path)
    assert patch.count("33'd8 * bl_out") == 2
    assert patch.count("33'd1") == 2
    assert 'calc_end_addr >=' not in path.read_text()
    with pytest.raises(ValueError, match='differs'):
        patch_traffic_bounds(path)
    # A full final burst is legal: native end is inclusive, stop is exclusive.
    for native_end in (0x3fff, 0xfffffff):
        for burst in (1, 2, 8, 64, 256):
            address = native_end + 1 - 8 * burst
            assert address + 8 * burst == native_end + 1


def test_vendor_summary_outputs_remain_internal():
    parameters = []
    body = []
    for channel in (0, 1):
        for name in ('END_ADDRESS', 'PRBS_EADDR_MASK_POS', 'TST_MEM_INSTR_MODE',
                     'CMD_PATTERN', 'DATA_MODE'):
            parameters.append(f'parameter C{channel}_{name} = 0,\n')
        body.extend((f'.memc_init_done       (c{channel}_init_calib_complete)',
                     f'.manual_clear_error   (c{channel}_manual_clear_error)',
                     f"assign c{channel}_wdt_en_w              = 1'b1;",
                     ".fixed_data_i         (32'b0),"))
    source = 'module example_top #(\n' + ''.join(parameters) + ''') (
   inout [71:0] c0_ddr3_dq,
   output                                       tg_compare_error,
   output                                       init_calib_complete,
   input c1_sys_clk_n,
   input                                        sys_rst
);
''' + '\n'.join(body) + '\nendmodule\n'
    result = adapt_example(source, 800, 3, 'address', 0xc0161001)
    ports = result.split(');', 1)[0]
    assert 'output                                       tg_compare_error' not in ports
    assert 'output                                       init_calib_complete' not in ports
    assert 'wire tg_compare_error, init_calib_complete;' in result
    assert 'input SYS_CLK,' in ports and 'output [2:0] led,' in ports


def clean_snapshot():
    words = [0] * 64
    words[0] = 1 | 8 | 128
    words[1] = 2
    words[2] = words[4] = words[6] = words[60] = 1 << 25
    words[14] = words[15] = 1
    words[19] = words[21] = 0x0ffffff8
    words[59] = 1
    return words


def test_full_memory_verdict_rejects_small_region_and_ecc_correction():
    words = clean_snapshot()
    assert verdict({'0': decode(words)}) == 'PASS_OBSERVED_FULL_MEMORY_PATTERN'
    words[15] = 0  # Large totals do not prove a full address traversal.
    words[4] = 0xffffffff
    assert verdict({'0': decode(words)}) == 'INCOMPLETE_FULL_MEMORY_TEST'
    words[10] = 1  # A corrected read is still a physical memory error.
    assert verdict({'0': decode(words)}) == 'FAIL_PHYSICAL_RAM_ERRORS'


def test_full_command_pass_waits_until_its_returned_data_has_been_compared():
    words = clean_snapshot()
    words[4] += 32
    channels = {'0': decode(words)}
    assert verdict(channels) == 'INCOMPLETE_RETURNED_DATA_COVERAGE'
    # A prior snapshot recorded this completed full command prefix. A later
    # sample can qualify it while new reads remain outstanding.
    assert verdict(channels, {'0': 1 << 25}) == 'PASS_OBSERVED_FULL_MEMORY_PATTERN'
    assert verdict(channels, {'0': (1 << 25) + 32}) == 'INCOMPLETE_RETURNED_DATA_COVERAGE'
    words[6] += 32
    assert verdict({'0': decode(words)}, {'0': (1 << 25) + 32}) == 'INCOMPLETE_RETURNED_DATA_COVERAGE'
    words[60] += 32
    assert verdict({'0': decode(words)}, {'0': (1 << 25) + 32}) == 'PASS_OBSERVED_FULL_MEMORY_PATTERN'


def test_latched_bad_lane_alone_is_a_failure():
    words = clean_snapshot()
    words[56] = 64
    assert verdict({'0': decode(words)}) == 'FAIL_PHYSICAL_RAM_ERRORS'


def test_decode_marks_vendor_error_record_unverified_and_retains_lane_counters():
    words = clean_snapshot()
    words[7] = 1
    words[22] = 0x200
    words[40+1] = 0xff0000  # DQ48..55 of first 64-bit payload word.
    words[56] = 1 << 6
    result = decode(words)
    assert result['returned_beats'] == (1 << 32) + (1 << 25)
    assert result['vendor_error_record']['native_address'] == '0x200'
    assert result['vendor_error_record']['alignment_verified'] is False
    assert 'first_error_bad_dq_bits' not in result
    assert result['cumulative_bad_byte_lanes'] == 64


def test_observer_counts_only_complete_sequential_passes_and_holds_snapshot(tmp_path):
    compiler = shutil.which('iverilog')
    if compiler is None:
        pytest.skip('Icarus not installed')
    tb = tmp_path / 'tb.sv'
    tb.write_text('''
module tb;
reg clk=0; always #5 clk=~clk;
reg rst=1, en=0, rv=0, request=0;
reg [2:0] cmd=0;
reg [28:0] addr=0;
reg [7:0] ce=0;
wire ack;
wire [2047:0] snapshot;
ramtest_channel #(.LAST_ADDR(24),.PROGRESS_LIMIT(64)) dut(
 .clk(clk),.ui_rst(rst),.calibrated(1'b1),.pattern_initialized(1'b1),
 .compare_error(1'b0),.watchdog_errors(3'b0),.command_valid(en),.command_ready(1'b1),
 .command(cmd),.address(addr),.read_valid(rv),.compare_valid(rv),.compare_bad(1'b0),
 .ecc_single(ce),.ecc_multiple(8'b0),.error_status(1088'b0),.lane_errors(8'b0),
 .snapshot_request(request),.snapshot_ack(ack),.snapshot(snapshot));
task send(input [2:0] c,input [28:0] a);
 begin @(negedge clk); en=1;cmd=c;addr=a;rv=(c==1); @(negedge clk);en=0;rv=0;end
endtask
task snap;
 begin @(negedge clk);request=~request;wait(ack==request);#1;end
endtask
reg [2047:0] held;
initial begin
 repeat(4) @(negedge clk);rst=0;
 send(0,0);send(0,8);send(0,16);send(0,24);
 send(1,0);send(1,8);send(1,16);send(1,24);snap();
 if(snapshot[448+:32]!=1 || snapshot[480+:32]!=1) $fatal(1,"full coverage missing");
 held=snapshot;
 send(1,0);send(1,16);send(1,24);
 if(snapshot!==held) $fatal(1,"snapshot changed without request");
 ce=1;@(negedge clk);rv=1;@(negedge clk);rv=0;ce=0;snap();
 if(snapshot[480+:32]!=1 || snapshot[544+:32]!=2) $fatal(1,"gap counted as full pass");
 if(snapshot[320+:64]!=1) $fatal(1,"corrected ECC error lost");
 @(negedge clk);dut.returned=64'hffffffff;rv=1;
 @(negedge clk);rv=0;snap();
 if(snapshot[192+:64]!=64'h100000000) $fatal(1,"counter did not carry into bit32");
 repeat(70) @(negedge clk);snap();
 if((snapshot[0+:32] & 32'h50)!=32'h50) $fatal(1,"missing command/read progress watchdogs");
 $display("PASS_RAM_OBSERVER_COVERAGE_SNAPSHOT_ECC_COUNTERS");$finish;
end
initial begin #10000;$fatal(1,"timeout");end
endmodule
''')
    binary = tmp_path / 'observer'
    subprocess.run([compiler, '-g2012', '-s', 'tb', '-o', str(binary), str(tb),
                    str(BOARD / 'ramtest_channel.sv')], check=True, capture_output=True)
    result = subprocess.run(['vvp', str(binary)], check=True, capture_output=True, text=True)
    assert 'PASS_RAM_OBSERVER_COVERAGE_SNAPSHOT_ECC_COUNTERS' in result.stdout


def test_status_service_uses_serial_mailbox_and_protects_busy_snapshots(tmp_path):
    compiler = shutil.which('iverilog')
    if compiler is None:
        pytest.skip('Icarus not installed')
    root = Path(__file__).resolve().parents[1]
    binary = tmp_path / 'status'
    subprocess.run([compiler, '-g2012', '-s', 'tb_status', '-o', str(binary),
                    str(BOARD / 'tb_status.sv'), str(BOARD / 'ramtest_jtag.sv'),
                    str(root / 'rtl/boards/ypcb-00338/otpu_jtag_mailbox.sv')],
                   check=True, capture_output=True)
    result = subprocess.run(['vvp', str(binary)], check=True, capture_output=True, text=True)
    assert 'PASS_RAM_STATUS_SERIAL_MAILBOX_BUSY_WORDS_AND_CHANNELS' in result.stdout
