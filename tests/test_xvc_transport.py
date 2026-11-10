"""Exercise the real XVC TCP client against a local USER2/IDCODE endpoint."""
from __future__ import annotations

import socketserver
import struct
import threading
import time

import numpy as np

from opentpu.host.jtag import CH_BYTES, IDCODE, MAGIC, JtagTransport, Xvc


def _recv_exact(sock, count):
    data = bytearray()
    while len(data) < count:
        part = sock.recv(count - len(data))
        if not part:
            raise EOFError
        data.extend(part)
    return bytes(data)


def _check_scan(nbits, tms, tdi, *, prefix, prefix_bits, data_bits):
    assert nbits == prefix_bits + data_bits + 2
    assert tms & ((1 << prefix_bits) - 1) == prefix
    assert (tms >> (prefix_bits + data_bits - 1)) & 0b11 == 0b11
    assert (tms >> (nbits - 1)) & 1 == 0
    assert tdi & ((1 << prefix_bits) - 1) == 0
    assert tdi >> (prefix_bits + data_bits) == 0


class _Tap:
    def __init__(self):
        self.ir = 0
        self.registers = {}
        self.memory = {}
        self.commands = []
        self.scans = 0
        self.response = MAGIC << 536

    def shift(self, nbits, tms, tdi):
        self.scans += 1
        if nbits == 6 and tms == 0b011111 and tdi == 0:
            self.ir = 0
            return 0
        if nbits == 12:
            _check_scan(nbits, tms, tdi, prefix=0b0011, prefix_bits=4, data_bits=6)
            self.ir = (tdi >> 4) & 0x3F
            return 0
        if nbits == 37 and self.ir == 0x09:
            _check_scan(nbits, tms, tdi, prefix=0b001, prefix_bits=3, data_bits=32)
            return IDCODE << 3
        if nbits == 645 and self.ir == 0x03:
            _check_scan(nbits, tms, tdi, prefix=0b001, prefix_bits=3, data_bits=640)
            old_response = self.response
            frame = tdi >> 3
            if frame:
                assert frame >> 572 == MAGIC
                opcode = (frame >> 548) & 0xFF
                address = (frame >> 512) & 0xFFFFFFFF
                sequence = (frame >> 556) & 0xFFFF
                data = frame & ((1 << 512) - 1)
                self.commands.append((opcode, address))
                if opcode == 1:
                    result = self.registers.get(address, 0)
                elif opcode == 2:
                    self.registers[address] = data & 0xFFFFFFFF
                    result = 0
                elif opcode == 3:
                    result = self.memory.get(address, 0)
                elif opcode == 4:
                    assert address % 64 == 0
                    self.memory[address] = data
                    result = 0
                else:
                    raise AssertionError(f"unexpected USER2 opcode {opcode}")
                self.response = MAGIC << 536 | sequence << 520 | result
            return old_response << 3
        raise AssertionError(f"unexpected XVC shift: IR={self.ir:#x}, nbits={nbits}")


class _XvcHandler(socketserver.BaseRequestHandler):
    def handle(self):
        tap = self.server.tap
        try:
            while True:
                opcode = _recv_exact(self.request, 6)
                if opcode == b"getinf":
                    assert _recv_exact(self.request, 2) == b"o:"
                    info = b"xvcServer_v1.0:2048\n"
                    self.request.sendall(info[:2])
                    time.sleep(0.001)
                    self.request.sendall(info[2:])
                    continue
                assert opcode == b"shift:"
                nbits = struct.unpack("<I", _recv_exact(self.request, 4))[0]
                size = (nbits + 7) // 8
                tms = int.from_bytes(_recv_exact(self.request, size), "little")
                tdi = int.from_bytes(_recv_exact(self.request, size), "little")
                tdo = tap.shift(nbits, tms, tdi)
                packed = tdo.to_bytes(size, "little")
                self.request.sendall(packed[:1])
                time.sleep(0.001)
                self.request.sendall(packed[1:])
        except EOFError:
            return
        except Exception as error:  # surface server-thread assertions in the test
            self.server.errors.append(error)


class _XvcServer(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True

    def __init__(self):
        self.tap = _Tap()
        self.errors = []
        super().__init__(("127.0.0.1", 0), _XvcHandler)


def test_xvc_tcp_idcode_user2_register_and_top_channel_ddr_round_trip():
    server = _XvcServer()
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    link = None
    transport = None
    try:
        link = Xvc("127.0.0.1", server.server_address[1], timeout=2.0)
        transport = JtagTransport(link=link, timeout=2.0)

        transport.reg_write(0x44, 0x12345678)
        assert transport.reg_read(0x44) == 0x12345678

        offset = CH_BYTES - 64
        payload = np.arange(64, dtype=np.uint8) ^ np.uint8(0xA5)
        transport.mem_write(1, offset, payload)
        np.testing.assert_array_equal(transport.mem_read(1, offset, 64), payload)

        assert server.tap.commands == [
            (2, 0x44), (1, 0x44), (4, 0xFFFFFFC0), (3, 0xFFFFFFC0),
        ]
        assert server.tap.memory[0xFFFFFFC0] == int.from_bytes(payload.tobytes(), "little")
        assert server.tap.ir == 0x03
    finally:
        if transport is not None:
            transport.close()
        elif link is not None:
            link.close()
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
    assert not worker.is_alive()
    assert server.errors == []
