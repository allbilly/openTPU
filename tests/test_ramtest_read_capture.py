"""Address tracking failures must be visible; post-ECC payload is not a syndrome."""
from pathlib import Path
import shutil
import subprocess

import pytest

from tools.probe_ramtest_litedram import corrected_only, decode_first_read

ROOT = Path(__file__).resolve().parents[1]


def test_corrected_only_continuation_stops_on_other_failures():
    from copy import deepcopy
    channel = dict(calibrated=True, initialized=True, ui_reset=False, watchdog_errors=0,
                   compare_error=False, bad_compare_cycles=0, ecc_corrected_beats=7,
                   ecc_uncorrectable_beats=0, cumulative_bad_byte_lanes=0,
                   ecc={'ecc_enable': 1},
                   first_read_mismatch=dict(captured=False, queue_overflow=False, queue_underflow=False))
    row = {'channels': {'0': channel}}
    assert corrected_only(row)
    assert not corrected_only({'channels': {}})
    for key in ('ui_reset', 'watchdog_errors', 'compare_error', 'bad_compare_cycles',
                'ecc_uncorrectable_beats', 'cumulative_bad_byte_lanes'):
        changed = deepcopy(row)
        changed['channels']['0'][key] = 1
        assert not corrected_only(changed)
    for key in ('calibrated', 'initialized', 'ecc_corrected_beats'):
        changed = deepcopy(row)
        changed['channels']['0'][key] = 0
        assert not corrected_only(changed)
    for key in ('captured', 'queue_overflow', 'queue_underflow'):
        changed = deepcopy(row)
        changed['channels']['0']['first_read_mismatch'][key] = True
        assert not corrected_only(changed)
    changed = deepcopy(row)
    changed['channels']['0']['ecc']['ecc_enable'] = 0
    assert not corrected_only(changed)


def test_decode_payload_and_scope():
    words = [0x80, 3] + [0x01234567]*16 + [0x01234567]*16
    words[19] ^= 1 << 16
    record = decode_first_read(words)
    assert record['byte_address'] == '0x400' and record['address_valid']
    assert bytes.fromhex(record['returned_payload_xor']) == b'\0'*6+b'\x01'+b'\0'*57
    assert 'after ECC' in record['scope']
    words[1] = 7
    assert not decode_first_read(words)['address_valid']
    words[1] = 8
    assert decode_first_read(words)['queue_underflow']
    assert not decode_first_read(words)['captured']
    words[1] = 16
    with pytest.raises(ValueError):
        decode_first_read(words)


def test_queue_failure_and_reset(tmp_path):
    if not shutil.which('iverilog') or not shutil.which('vvp'):
        pytest.skip('Icarus Verilog is required')
    tb=tmp_path/'tb.sv'
    tb.write_text(r'''
module tb;
  reg clk=0,rst=1,command_valid=0,command_ready=1,read_valid=0;
  always #5 clk=~clk;
  reg [2:0] command=1;
  reg [28:0] address=0;
  reg [511:0] read_data=0,expected_data=0;
  wire [1087:0] record;
  ramtest_read_capture #(.QUEUE_BITS(2)) dut(.*);
  initial begin
    repeat(3) @(negedge clk);rst=0;
    repeat(5) begin command_valid=1;@(negedge clk);address=address+8;end
    command_valid=0;
    if(!record[34] || record[35]) $fatal(1,"Overflow not detected");
    rst=1;repeat(2) @(negedge clk);rst=0;
    if(record[63:32]!==0) $fatal(1,"Reset did not clear flags");
    read_valid=1;read_data=512'h1;
    @(negedge clk);read_valid=0;
    repeat(4) @(negedge clk);
    if(record[63:32]!==9 || record[1087:576]!==512'h1)
      $fatal(1,"Underflow capture did not invalidate address");
    rst=1;repeat(2) @(negedge clk);rst=0;
    command_valid=1;read_valid=1;address=29'h10;read_data=512'h2;
    @(negedge clk);command_valid=0;read_valid=0;
    repeat(4) @(negedge clk);
    if(record[63:32]!==3 || record[31:0]!==32'h10 || record[1087:576]!==512'h2)
      $fatal(1,"Simultaneous empty queue push/pop lost address");
    $display("PASS overflow underflow reset empty-bypass");$finish;
  end
  initial begin #10000;$fatal(1,"Timeout");end
endmodule
''')
    binary=tmp_path/'test.vvp'
    subprocess.run(['iverilog','-g2012','-s','tb','-o',str(binary),str(tb),
                    str(ROOT/'boards/ypcb-00338/ramtest/read_capture.sv')],check=True,capture_output=True,text=True)
    result=subprocess.run(['vvp',str(binary)],check=True,capture_output=True,text=True,timeout=10)
    assert 'PASS overflow underflow reset empty-bypass' in result.stdout
