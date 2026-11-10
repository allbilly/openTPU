"""Wire-level checks for the Vivado native JTAG adapter; no hardware used."""
import socket
import threading
import unittest
import os
from pathlib import Path
import subprocess
import tempfile
from unittest.mock import Mock, patch
from tools.fedora_run_vivado_native_jtag import NativeLink, TCL, wait_for_calibration


class Endpoint:
    def __init__(self, replies):
        self.replies = replies
        self.requests = []
        self.server = socket.socket()
        self.server.bind(('127.0.0.1', 0))
        self.server.listen()
        self.port = self.server.getsockname()[1]
        self.thread = threading.Thread(target=self.serve, daemon=True)
        self.thread.start()

    def serve(self):
        with self.server, self.server.accept()[0] as conn:
            conn.settimeout(2)
            conn.sendall(b'READY\n')
            with conn.makefile('rb') as reader:
                for reply in self.replies:
                    self.requests.append(reader.readline().decode().strip())
                    # Fragment deliberately: the client must retain the full line.
                    midpoint = len(reply)//2
                    conn.sendall(reply[:midpoint])
                    conn.sendall(reply[midpoint:])

    def finish(self):
        self.thread.join(3)
        assert not self.thread.is_alive()


class NativeLinkTests(unittest.TestCase):
    def test_scan_reset_and_idle_commands(self):
        endpoint = Endpoint([b'OK 0\n', b'OK 15\n', b'OK 23751093\n', b'OK 0\n'])
        link = NativeLink(port=endpoint.port)
        try:
            link.reset()
            self.assertEqual(link.scan(9, 6, ir=True), 0x15)
            self.assertEqual(link.scan(0, 32), 0x23751093)
            self.assertEqual(link.shift(16, 0, 0), 0)
        finally:
            link.close()
        endpoint.finish()
        self.assertEqual(endpoint.requests, ['RESET', 'SCAN IR 6 9',
                                            'SCAN DR 32 0', 'IDLE 16'])

    def test_full_width_fragmented_mailbox_response(self):
        value = (1 << 639) | (0x4f54504a << 536) | 0x1234
        endpoint = Endpoint([f'OK {value:x}\n'.encode()])
        link = NativeLink(port=endpoint.port)
        try:
            self.assertEqual(link.scan(0), value)
        finally:
            link.close()
        endpoint.finish()

    def test_error_poisoning_prevents_another_command(self):
        endpoint = Endpoint([b'ERR native hardware disappeared\n'])
        link = NativeLink(port=endpoint.port)
        try:
            with self.assertRaises(OSError):
                link.scan(0, 32)
            with self.assertRaisesRegex(OSError, 'needs recovery'):
                link.reset()
        finally:
            link.close()
        endpoint.finish()
        self.assertEqual(endpoint.requests, ['SCAN DR 32 0'])

    def test_oversized_tdo_is_rejected(self):
        endpoint = Endpoint([b'OK 100000000\n'])
        link = NativeLink(port=endpoint.port)
        try:
            with self.assertRaisesRegex(OSError, 'exceeds'):
                link.scan(0, 32)
            self.assertTrue(link.failed)
        finally:
            link.close()
        endpoint.finish()

    def test_invalid_scans_are_rejected_before_hardware(self):
        endpoint = Endpoint([])
        link = NativeLink(port=endpoint.port)
        try:
            for value, bits, ir in [(0, 641, False), (64, 6, True),
                                    (0, 5, True), (-1, 32, False)]:
                with self.assertRaises(ValueError):
                    link.scan(value, bits, ir)
            with self.assertRaises(ValueError):
                link.shift(16, 1, 0)
        finally:
            link.close()
        endpoint.finish()
        self.assertEqual(endpoint.requests, [])


class TclGuardTests(unittest.TestCase):
    """Exercise the actual Tcl guards with native tool calls mocked out."""
    def run_guard(self, *, devices=1, idcode='23751093', init=1, done=1):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            mailbox = f'{0x4f54504a << 536:x}'
            mock = f'''
foreach name {{open_hw_manager connect_hw_server current_hw_target set_property
              open_hw_target close_hw_target run_state_hw_jtag refresh_hw_device
              disconnect_hw_server close_hw_manager}} {{proc $name args {{}}}}
proc get_hw_targets {{}} {{return target}}
proc get_hw_devices {{}} {{return {{{' '.join(['device']*devices)}}}}}
proc get_property {{name device}} {{
    switch -- $name {{
        PART {{return xc7k480t}}
        REGISTER.IR.BIT4_INIT_COMPLETE {{return {init}}}
        REGISTER.IR.BIT5_DONE {{return {done}}}
        default {{error "Unexpected property"}}
    }}
}}
proc scan_ir_hw_jtag args {{return 0}}
proc scan_dr_hw_jtag {{length args}} {{
    if {{$length == 32}} {{return {idcode}}}
    return {mailbox}
}}
proc program_hw_devices args {{
    set f [open $::env(MOCK_PROGRAM_CALLED) w]; puts $f called; close $f
}}
rename socket real_socket
proc socket args {{return mock_listener}}
rename close real_close
proc close {{channel}} {{if {{$channel ne "mock_listener"}} {{real_close $channel}}}}
rename vwait real_vwait
proc vwait args {{}}
'''
            (root/'guard.tcl').write_text(mock+TCL)
            env = dict(os.environ, OTPU_NATIVE_READY=str(root/'ready'),
                       OTPU_NATIVE_BIT=str(root/'image.bit'),
                       OTPU_NATIVE_PROGRAM_STATUS=str(root/'program-status'),
                       MOCK_PROGRAM_CALLED=str(root/'program-called'))
            result = subprocess.run(['tclsh', str(root/'guard.tcl')], env=env,
                                    capture_output=True, text=True, timeout=5)
            return result.returncode, (root/'program-called').exists(), (root/'ready').exists()

    def test_expected_chain_and_init_done_reach_ready(self):
        self.assertEqual(self.run_guard(), (0, True, True))

    def test_multiple_devices_rejected_before_programming(self):
        self.assertEqual(self.run_guard(devices=2), (1, False, False))

    def test_wrong_idcode_rejected_before_programming(self):
        self.assertEqual(self.run_guard(idcode='23751092'), (1, False, False))

    def test_init_failure_prevents_memory_endpoint(self):
        self.assertEqual(self.run_guard(init=0), (1, True, False))

    def test_done_failure_prevents_memory_endpoint(self):
        self.assertEqual(self.run_guard(done=0), (1, True, False))


class CalibrationGateTests(unittest.TestCase):
    def test_waits_for_both_channels_and_records_intermediate_flags(self):
        transport = Mock()
        transport.reg_read.side_effect = [0, 32, 96]
        observed = []
        with patch('tools.fedora_run_vivado_native_jtag.time.sleep'):
            self.assertEqual(wait_for_calibration(transport, observe=observed.append), 96)
        self.assertEqual(observed, [0, 32, 96])

    def test_timeout_does_not_bypass_one_missing_channel(self):
        transport = Mock()
        transport.reg_read.return_value = 32
        with self.assertRaises(TimeoutError):
            wait_for_calibration(transport, timeout=0)

    def test_running_compute_is_rejected(self):
        transport = Mock()
        transport.reg_read.return_value = 96 | 128
        with self.assertRaises(OSError):
            wait_for_calibration(transport)


if __name__ == '__main__':
    unittest.main()

