"""Exercise SRAM loader chain/completion guards in Tcl without real hardware."""
import os
from pathlib import Path
import subprocess
import tempfile
import pytest

from tools.fedora_program_ch1_sram import TCL


def run_guard(*, targets=1, devices=1, part='xc7k480t', ident='23751093',
              post_ident='23751093', init=1, done=1):
    with tempfile.TemporaryDirectory() as temporary:
        root=Path(temporary)
        mock=f'''
foreach name {{open_hw_manager connect_hw_server current_hw_target set_property
               open_hw_target close_hw_target run_state_hw_jtag refresh_hw_device
               disconnect_hw_server close_hw_manager}} {{proc $name args {{}}}}
proc get_hw_targets {{}} {{return {{{' '.join(['target']*targets)}}}}}
proc get_hw_devices {{}} {{return {{{' '.join(['device']*devices)}}}}}
proc get_property {{name device}} {{
    switch -- $name {{
        PART {{return {part}}}
        REGISTER.IR.BIT4_INIT_COMPLETE {{return {init}}}
        REGISTER.IR.BIT5_DONE {{return {done}}}
        default {{error "Unexpected property"}}
    }}
}}
set scanned 0
proc scan_ir_hw_jtag {{length args}} {{
    if {{$length != 6 || $args ne "-tdi 09"}} {{error "Unexpected instruction scan"}}
    return 0
}}
proc scan_dr_hw_jtag {{length args}} {{
    global scanned
    if {{$length != 32}} {{error "Mailbox scan forbidden in PCIe loader"}}
    incr scanned
    if {{$scanned == 1}} {{return {ident}}}
    return {post_ident}
}}
proc program_hw_devices args {{
    set f [open $::env(MOCK_PROGRAM_CALLED) w]; puts $f called; close $f
}}
'''
        (root/'guard.tcl').write_text(mock+TCL)
        env=dict(os.environ,OTPU_CH1_BIT=str(root/'image.bit'),
                 OTPU_CH1_PROGRAM_STATUS=str(root/'complete'),MOCK_PROGRAM_CALLED=str(root/'called'))
        result=subprocess.run(['tclsh',str(root/'guard.tcl')],env=env,capture_output=True,text=True,timeout=5)
        return result.returncode,(root/'called').exists(),(root/'complete').read_text() if (root/'complete').exists() else None


def test_expected_pcie_image_load_does_not_require_a_mailbox():
    code,called,complete=run_guard()
    assert (code,called,complete)==(0,True,'INIT=1 DONE=1 IDCODE=23751093\n')


@pytest.mark.parametrize('change',[
    dict(targets=2),dict(devices=2),dict(part='xc7k325t'),dict(ident='03751093'),
])
def test_wrong_or_ambiguous_target_is_rejected_before_programming(change):
    code,called,complete=run_guard(**change)
    assert code != 0 and not called and complete is None


@pytest.mark.parametrize('change',[dict(init=0),dict(done=0),dict(post_ident='03751093')])
def test_failed_configuration_cannot_produce_a_success_receipt(change):
    code,called,complete=run_guard(**change)
    assert code != 0 and called and complete is None
