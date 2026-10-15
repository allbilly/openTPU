#!/usr/bin/env python3
"""Run the qualified CH1 image using one local RPC per acknowledged command.

The FPGA mailbox, 3 MHz TCK, 16 idle clocks and completion checks are unchanged.
The Tcl bridge performs the request/idle/poll loop without three Python round trips.
No commands are pipelined; a failed command poisons the transport.
"""
from pathlib import Path
import hashlib
import json
import sys

import fedora_run_ch1_jtag_lfm2 as runner
from fedora_run_vivado_native_jtag import NativeLink
from opentpu.host.jtag import MAGIC


COMMAND_PROC = r'''
proc otpu_command {frame} {
    if {![regexp {^[0-9a-fA-F]{1,151}$} $frame]} {error "Bad command frame"}
    set word [expr "0x$frame"]
    set seq [expr {($word >> 556) & 0xffff}]
    set op [expr {($word >> 548) & 0xff}]
    if {($word >> 572) != 0x4f54504a || $seq == 0 || $op < 1 || $op > 4} {
        error "Bad command header"
    }
    scan_dr_hw_jtag 640 -tdi $frame
    runtest_hw_jtag -wait_state IDLE -end_state IDLE -tck 16
    set deadline [expr {[clock milliseconds] + 30000}]
    while {1} {
        set raw [scan_dr_hw_jtag 640 -tdi 0]
        if {![regexp {^[0-9a-fA-F]{1,160}$} $raw]} {error "Bad response frame"}
        set reply [expr "0x$raw"]
        if {(($reply >> 536) & 0xffffffff) != 0x4f54504a} {error "Mailbox response magic mismatch"}
        if {(($reply >> 520) & 0xffff) == $seq} {
            set status [expr {($reply >> 512) & 0xff}]
            if {$status != 0} {error "Mailbox command failed with status $status"}
            return [string range $raw end-127 end]
        }
        if {[clock milliseconds] >= $deadline} {error "Mailbox command timed out"}
        after 1
    }
}
'''


def bridge_tcl(original):
    marker='proc drop {channel} {'
    assert original.count(marker)==1
    result=original.replace(marker,COMMAND_PROC+'\n'+marker,1)
    marker='            QUIT {'
    assert result.count(marker)==1
    return result.replace(marker,'''            COMMAND {
                if {[llength $fields] != 2} {error "Bad command fields"}
                set result [otpu_command [lindex $fields 1]]
            }
'''+marker,1)


class CommandTransport(runner.CalibratedJtagTransport):
    def _command(self,opcode,addr,data=0,strobes=15):
        with self._dma:
            if self._failed or self.link is None:
                raise IOError('JTAG connection needs recovery after a failed transaction')
            self._seq=self._seq%65535+1
            frame=data|addr<<512|strobes<<544|opcode<<548|self._seq<<556|MAGIC<<572
            try:
                result=self.link.command(f'COMMAND {frame:x}')
                if not 0<=result<1<<512:
                    raise IOError('Mailbox response data exceeds 512 bits')
                return result
            except BaseException:
                self._failed=True
                raise


def main():
    runner.CalibratedJtagTransport=CommandTransport
    runner.LfmNativeLink=NativeLink
    runner.TCL=bridge_tcl(runner.TCL)
    if '--out' in sys.argv:
        out=Path(sys.argv[sys.argv.index('--out')+1]).resolve()
        witness=out.with_name(out.name+'-transport-inputs.json')
        inputs=[runner.describe(Path(__file__)),runner.describe(Path(runner.__file__))]
        witness.write_text(json.dumps(dict(protocol='One outstanding acknowledged command',
            tck_hz=3000000,idle_clocks=16,files=inputs,
            bridge_sha256=hashlib.sha256(runner.TCL.encode()).hexdigest()),indent=2)+'\n')
    return runner.main()


if __name__=='__main__':
    raise SystemExit(main())
