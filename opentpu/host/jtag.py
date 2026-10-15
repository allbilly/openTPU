"""Physical USER2/XVC transport for otpu_fpga_top_openxc7_jtag.

JTAG is deliberately serial: register accesses and whole 64-byte DDR bursts
share one mailbox. This transport is not an XDMA device or a bandwidth proxy.
"""
from __future__ import annotations

import socket
import struct
import threading
import time

import numpy as np

MAGIC = 0x4F54504A
IDCODE = 0x23751093
FRAME_BITS = 640
CH_BYTES = 1 << 31


class Xvc:
    def __init__(self, host="localhost", port=3721, timeout=5.0):
        self.sock = socket.create_connection((host, port), timeout)
        try:
            self.sock.sendall(b"getinfo:")
            info = bytearray()
            while not info.endswith(b"\n"):
                info.extend(self._recv(1))
                if len(info) > 256:
                    raise IOError("Invalid XVC getinfo response")
            name, size = info.decode().strip().split(":")
            if not name.startswith("xvcServer_") or int(size) < FRAME_BITS+5:
                raise IOError("XVC server cannot scan the OpenTPU mailbox frame")
        except BaseException:
            self.close()
            raise

    def _recv(self, n):
        out = bytearray()
        while len(out) < n:
            chunk = self.sock.recv(n-len(out))
            if not chunk:
                raise EOFError("XVC disconnected")
            out.extend(chunk)
        return bytes(out)

    def shift(self, n, tms, tdi):
        size = (n+7)//8
        self.sock.sendall(b"shift:"+struct.pack("<I", n)+
                          tms.to_bytes(size, "little")+tdi.to_bytes(size, "little"))
        return int.from_bytes(self._recv(size), "little")

    def reset(self):
        self.shift(6, 0b011111, 0)

    def scan(self, value, bits=FRAME_BITS, ir=False):
        # Start/end in Run-Test/Idle. The last data bit goes to Exit1;
        # the two trailing clocks enter Update then return to Idle.
        prefix, count = (0b0011, 4) if ir else (0b001, 3)
        tms = prefix | (1 << (count+bits-1)) | (1 << (count+bits))
        out = self.shift(count+bits+2, tms, value << count)
        return (out >> count) & ((1 << bits)-1)

    def close(self):
        self.sock.close()


class JtagTransport:
    """Board transport API, backed by physical XVC/JTAG scans.

    The XVC endpoint must expose the selected Kintex-7 as a single TAP. The
    IDCODE is verified before USER2 is accessed. Failed/time-out transactions
    poison the connection so a later command cannot overwrite an in-flight
    mailbox request. Reconnect only after resolving the board-side condition.
    """
    host_idle = 0.001
    ecc = True
    bandwidth_test = False

    def __init__(self, host="localhost", port=3721, timeout=30.0, *, link=None, calibration_data=None):
        from pathlib import Path
        self.calibration_data = Path(calibration_data) if calibration_data else Path(__file__).with_name('litedram')
        self.dev = f"jtag://{host}:{port}"
        self.devname = f"jtag-{host}-{port}"
        self.timeout = timeout
        self._dma = threading.RLock()
        self._seq = 0
        self._failed = False
        self.link = None
        self._otpu_lock = None
        try:
            if link is None:
                from .runstate import DeviceLock
                self._otpu_lock = DeviceLock(self.devname)
            self.link = link or Xvc(host,port,min(timeout,5.0))
            self.link.reset()
            self.link.scan(0x09, 6, ir=True)
            ident = self.link.scan(0, 32)
            if ident != IDCODE:
                raise IOError(f"Expected selected xc7k480t IDCODE {IDCODE:#x}, got {ident:#x}")
            self.link.scan(0x03, 6, ir=True)
            response = self.link.scan(0)
            if (response >> 536) & 0xffffffff != MAGIC:
                raise IOError("OpenTPU USER2 mailbox is absent; program its JTAG image first")
            # Continue after the retained completion sequence. A random first
            # sequence could equal it and accept an old response on reconnect.
            self._seq = (response >> 520) & 0xffff
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.link is not None:
            self.link.close()
            self.link = None
        if self._otpu_lock is not None:
            self._otpu_lock.release()
            self._otpu_lock = None

    def _command(self, opcode, addr, data=0, strobes=15):
        with self._dma:
            if self._failed or self.link is None:
                raise IOError("JTAG connection needs recovery after a failed transaction")
            self._seq = self._seq % 65535+1
            seq = self._seq
            frame = data | addr << 512 | strobes << 544 | opcode << 548 | seq << 556 | MAGIC << 572
            try:
                self.link.scan(frame)
                deadline = time.monotonic()+self.timeout
                while True:
                    r = self.link.scan(0)
                    if (r >> 536) & 0xffffffff != MAGIC:
                        raise IOError("JTAG mailbox response magic mismatch")
                    if (r >> 520) & 0xffff == seq:
                        status = (r >> 512) & 0xff
                        if status:
                            raise IOError(f"JTAG command {opcode} at {addr:#x}: status {status}")
                        return r & ((1 << 512)-1)
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f"JTAG command {opcode} at {addr:#x} did not complete")
                    time.sleep(0.001)
            except BaseException:
                self._failed = True
                raise

    def reg_read(self, off):
        if off % 4 or not (0 <= off < 0x1000 or 0x10000 <= off < 0x20000):
            raise ValueError("Register address must be aligned in control or LiteDRAM CSR window")
        return self._command(1, off) & 0xffffffff

    def reg_write(self, off, val):
        if off % 4 or not (0 <= off < 0x1000 or 0x10000 <= off < 0x20000):
            raise ValueError("Register address must be aligned in control or LiteDRAM CSR window")
        self._command(2,off,val & 0xffffffff)

    def reg_read_many(self, offs):
        return [self.reg_read(off) for off in offs]

    def read_die_temperature(self):
        """Read the real chip sensor through UG480's dedicated JTAG DRP.

        Its default internal-sensor mode needs no fabric instance or control
        writes. The read is pipelined; actual idle TCK cycles allow the DRP
        arbitrator to complete before Capture-DR. Restore USER2 atomically.
        """
        from . import regs as R
        with self._dma:
            if self._failed or self.link is None:
                raise IOError("JTAG connection needs recovery after a failed transaction")
            try:
                try:
                    self.link.scan(0x37, 6, ir=True)
                    self.link.scan(1 << 26, 32)  # DRP Read, status address 0
                    self.link.shift(16, 0, 0)   # UG480 requires at least ten RTI states
                    raw = self.link.scan(0, 32) & 0xffff  # capture result, submit NOP
                finally:
                    self.link.scan(0x03, 6, ir=True)
            except BaseException:
                self._failed = True
                raise
            if raw in (0, 0xffff):
                return None  # not yet sampled, unavailable, or bypass data
            return round(R.temp_c(raw >> 4), 2)

    @staticmethod
    def _range(ch, off, n):
        if ch not in (0,1) or off < 0 or n < 0 or off+n > CH_BYTES:
            raise ValueError("DDR range outside the selected 2 GiB channel")
        return ch*CH_BYTES+off

    def mem_read(self,ch,off,n,out=None):
        base = self._range(ch,off,n)
        buf = np.empty(n,np.uint8) if out is None else out
        mv = memoryview(buf).cast("B")
        if len(mv) < n:
            raise ValueError("Output buffer too small")
        with self._dma:
            pos=0
            while pos<n:
                addr=base+pos
                offset=addr % 64
                k=min(64-offset,n-pos)
                beat=self._command(3,addr-offset).to_bytes(64,"little")
                mv[pos:pos+k]=beat[offset:offset+k]
                pos+=k
        return buf

    def mem_write(self,ch,off,data):
        src=memoryview(np.ascontiguousarray(data,np.uint8).reshape(-1)).cast("B")
        base=self._range(ch,off,len(src))
        with self._dma:
            pos=0
            while pos<len(src):
                addr=base+pos
                offset=addr % 64
                k=min(64-offset,len(src)-pos)
                beat=bytearray(64) if offset==0 and k==64 else bytearray(
                    self._command(3,addr-offset).to_bytes(64,"little"))
                beat[offset:offset+k]=src[pos:pos+k]
                self._command(4,addr-offset,int.from_bytes(beat,"little"))
                pos+=k

    def poll(self,off,mask,val,timeout=600.0,expect=0.0):
        deadline=time.monotonic()+timeout
        while True:
            value=self.reg_read(off)
            if value & mask == val:
                return value
            if time.monotonic() >= deadline:
                raise TimeoutError(f"JTAG register {off:#x}: {value:#x}, expected {mask:#x}/{val:#x}")
            time.sleep(0.001)

    def scrub(self):
        """Initialize and check all 4 GiB with the existing native hardware BIST.

        The BIST's zero seed stays zero in xorshift mode. It writes all 72 raw
        data/ECC bits as zero, which is the valid ECC encoding of zero data.
        Only CSR commands travel over JTAG; data stays on the DDR native ports.
        """
        from . import ddrcal, memcal, regs as R
        state = self.reg_read(R.R_STATUS)
        required = R.ST_CALIB0 | R.ST_CALIB1
        if state & required != required or state & (R.ST_RUN | R.ST_LOADING):
            raise IOError("DDR scrub requires both calibrated channels and an idle accelerator")
        c = memcal.csr(self)
        beats = CH_BYTES // 64
        with self._dma:
            for ch in (0,1):
                chan = ddrcal.Chan(c,ch)
                for mode in (0,1):
                    res = ddrcal.bist(chan,beats,mode,0,133333333,timeout=120.0)
                    if res['beats'] != beats or res.get('errors',0):
                        raise IOError(f"DDR channel {ch} BIST scrub/check failed: {res}")
