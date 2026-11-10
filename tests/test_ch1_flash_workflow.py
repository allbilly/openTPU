"""Exercise the real flash Tcl branches with a simulated hardware manager.

No USB, FPGA or NOR flash is accessed.
"""
import os
import shutil
import subprocess
from pathlib import Path
import tempfile

import pytest
from tools.fedora_flash_ch1_pcie import TCL

STUB = r'''
foreach name {open_hw_manager connect_hw_server current_hw_target open_hw_target close_hw_target
              run_state_hw_jtag scan_ir_hw_jtag current_hw_device refresh_hw_device
              create_hw_cfgmem create_hw_bitstream close_hw_manager disconnect_hw_server
              report_property} {
    proc $name args {}
}
proc get_hw_targets {} {return target0}
proc get_hw_devices {} {return dev0}
proc get_cfgmem_parts args {return {part0 part0}}
proc get_property {key obj} {
    switch -- $key {
        PART {return xc7k480t}
        NAME {return mt28gu512aax1e-bpi-x16}
        MEM_DENSITY {return 512}
        DATA_WIDTH {return x16}
        COMPATIBLE_PARTS {return {artix7 kintex7 virtex7}}
        PROGRAM.HW_CFGMEM {return cfg0}
        PROGRAM.HW_CFGMEM_BITFILE {return bridge.bit}
        REGISTER.IR.BIT4_INIT_COMPLETE - REGISTER.IR.BIT5_DONE {return 1}
        default {error "Unexpected property $key"}
    }
}
proc scan_dr_hw_jtag args {return 23751093}
proc set_property args {puts "PROPERTY $args"}
proc program_hw_devices args {puts "SRAM $args"}
proc program_hw_cfgmem args {puts "NOR_OPERATION $args"}
proc readback_hw_cfgmem args {puts "READBACK $args"}
proc boot_hw_device args {puts "BOOT $args"}
proc after args {}
'''


def run(mode, stub=STUB):
    binary = shutil.which('tclsh')
    assert binary, 'tclsh is required for the flash workflow gate'
    env = dict(os.environ, OTPU_FLASH_MODE=mode, OTPU_FLASH_MCS='/tmp/test.mcs',
               OTPU_FLASH_BACKUP_A='/tmp/test-a.bin', OTPU_FLASH_BACKUP_B='/tmp/test-b.bin')
    with tempfile.TemporaryDirectory() as tmp:
        script = Path(tmp) / 'flash-test.tcl'
        script.write_text(stub + '\n' + TCL)
        return subprocess.run([binary, str(script)], text=True,
                              capture_output=True, env=env, timeout=5)


def test_backup_only_reads_nor_twice():
    result = run('backup')
    assert 'PASS_TWO_READONLY_FACTORY_READBACKS' in result.stdout
    assert result.stdout.count('READBACK ') == 2
    assert 'NOR_OPERATION' not in result.stdout
    assert 'PROGRAM.ERASE' not in result.stdout
    assert 'PROGRAM.CFG_PROGRAM' not in result.stdout


def test_program_erases_programs_and_verifies():
    result = run('program')
    assert 'PASS_FLASH_OPERATION_program' in result.stdout
    assert 'PROPERTY PROGRAM.ERASE 1 cfg0' in result.stdout
    assert 'PROPERTY PROGRAM.CFG_PROGRAM 1 cfg0' in result.stdout
    assert 'PROPERTY PROGRAM.VERIFY 1 cfg0' in result.stdout
    assert result.stdout.count('NOR_OPERATION ') == 1


def test_verify_does_not_erase_or_program():
    result = run('verify')
    assert 'PASS_FLASH_OPERATION_verify' in result.stdout
    assert 'PROPERTY PROGRAM.ERASE 0 cfg0' in result.stdout
    assert 'PROPERTY PROGRAM.CFG_PROGRAM 0 cfg0' in result.stdout
    assert 'PROPERTY PROGRAM.VERIFY 1 cfg0' in result.stdout


def test_boot_uses_flash_without_programming():
    result = run('boot')
    assert 'PASS_BOOT_FROM_FLASH_INIT_DONE' in result.stdout
    assert 'BOOT dev0' in result.stdout
    assert 'NOR_OPERATION' not in result.stdout
    assert 'SRAM ' not in result.stdout


@pytest.mark.parametrize('bad_stub', [
    STUB.replace('return 23751093', 'return 12345678'),
    STUB.replace('return x16', 'return x8'),
    STUB.replace('return 512', 'return 256'),
], ids=['wrong_fpga','wrong_width','wrong_density'])
def test_wrong_device_or_part_prevents_flash_operation(bad_stub):
    result = run('program', bad_stub)
    assert 'PASS_FLASH_OPERATION_program' not in result.stdout
    assert 'NOR_OPERATION' not in result.stdout
    assert result.stderr
