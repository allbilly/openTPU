"""Full DDR/control transport for the open Gen2 x1 PCIe mailbox image.

Uses Linux's uncached sysfs resource0 mapping. It is programmed I/O, with
the same complete 64-byte ECC transfers as USER2; it is not an XDMA engine.
"""
from __future__ import annotations

import ctypes
import hashlib
import json
import mmap
import os
from pathlib import Path
import platform
import re
import threading
import time

from .jtag import JtagTransport

MAGIC = 0x4F545050
ROOT = Path(__file__).resolve().parents[2]


class SysfsBar:
    def __init__(self, bdf, *, sysfs=Path('/sys/bus/pci/devices')):
        if not re.fullmatch(r'[0-9a-fA-F]{4}:[0-9a-fA-F]{2}:[0-9a-fA-F]{2}\.[0-7]', bdf):
            raise ValueError('Select an explicit PCIe BDF, for example 0000:01:00.0')
        device = Path(sysfs)/bdf.lower()
        if int((device/'vendor').read_text(),16) != 0x10ee or int((device/'device').read_text(),16) != 0x0480:
            raise IOError('Selected PCIe device does not match the open YPCB endpoint 10ee:0480')
        if (device/'driver').exists():
            raise IOError('Selected PCIe device has a bound driver; detach it explicitly before PIO access')
        if int((device/'enable').read_text()) == 0:
            raise IOError('Selected PCIe device is disabled; enable it explicitly before PIO access')
        start,end,flags = (int(n,16) for n in (device/'resource').read_text().splitlines()[0].split())
        if not start or end-start+1 != 4096 or not flags & 0x200:
            raise IOError('Selected device does not expose the expected 4 KiB memory BAR0')
        if platform.machine() not in ('x86_64','aarch64'):
            raise IOError('Unsupported host MMIO architecture')
        helper = ROOT/'build/fedora-pcie-mmio'
        metadata = json.loads((helper/'manifest.json').read_text())
        library = helper/'libotpu_mmio.so'
        if (metadata.get('architecture') != platform.machine()
            or metadata.get('source_sha256') != hashlib.sha256((ROOT/'tools/pcie_mmio.c').read_bytes()).hexdigest()
            or metadata.get('library_sha256') != hashlib.sha256(library.read_bytes()).hexdigest()):
            raise IOError('Rebuild the MMIO helper with tools/fedora_prepare_pcie_mmio.py')
        self._helper = ctypes.CDLL(str(library))
        self._helper.otpu_mmio_read32.argtypes = [ctypes.c_void_p,ctypes.c_uint32]
        self._helper.otpu_mmio_read32.restype = ctypes.c_uint32
        self._helper.otpu_mmio_write32.argtypes = [ctypes.c_void_p,ctypes.c_uint32,ctypes.c_uint32]
        self._helper.otpu_mmio_write32.restype = None
        fd = os.open(device/'resource0',os.O_RDWR | os.O_CLOEXEC)
        try:
            self._mapping = mmap.mmap(fd,4096,flags=mmap.MAP_SHARED,prot=mmap.PROT_READ | mmap.PROT_WRITE)
        finally:
            os.close(fd)
        self._words = (ctypes.c_uint32*1024).from_buffer(self._mapping)
        self._base = ctypes.addressof(self._words)

    @staticmethod
    def _offset(off):
        if off % 4 or not 0 <= off < 4096:
            raise ValueError('BAR offset must be an aligned 32-bit word within BAR0')

    def read32(self, off):
        self._offset(off)
        if self._mapping is None:
            raise IOError('BAR mapping is closed')
        return self._helper.otpu_mmio_read32(self._base,off)

    def write32(self, off, val):
        self._offset(off)
        if self._mapping is None:
            raise IOError('BAR mapping is closed')
        self._helper.otpu_mmio_write32(self._base,off,val & 0xffffffff)

    def close(self):
        if self._mapping is not None:
            self._words = None
            self._mapping.close()
            self._mapping = None


class PciePioTransport(JtagTransport):
    """Reuse the validated complete channel/ECC mapping with a PCIe BAR command path."""
    def __init__(self, bdf, timeout=30.0, *, bar=None, calibration_data=None):
        self.calibration_data = Path(calibration_data) if calibration_data else Path(__file__).with_name('litedram')
        self.dev = f'pcie-pio://{bdf}'
        self.devname = 'pcie-pio-'+bdf.lower()
        self.timeout = timeout
        self._dma = threading.RLock()
        self._seq = 0
        self._failed = False
        self._bar = None
        self._otpu_lock = None
        try:
            if bar is None:
                from .runstate import DeviceLock
                self._otpu_lock = DeviceLock(self.devname)
            self._bar = bar if bar is not None else SysfsBar(bdf)
            if self._bar.read32(0) != MAGIC or self._bar.read32(4) != 1:
                raise IOError('OpenTPU PCIe mailbox identity/ABI mismatch')
            if self._bar.read32(8) & 5:
                raise IOError('PCIe mailbox is busy or rejected a command; recover its owner before reconnecting')
            self._seq = self._bar.read32(0x14) >> 16
        except BaseException:
            self.close()
            raise

    def close(self):
        if self._bar is not None:
            self._bar.close()
            self._bar = None
        if self._otpu_lock is not None:
            self._otpu_lock.release()
            self._otpu_lock = None

    def _command(self, opcode, addr, data=0, strobes=15):
        with self._dma:
            if self._failed or self._bar is None:
                raise IOError('PCIe PIO connection needs recovery after a failed transaction')
            self._seq = self._seq % 65535+1
            seq = self._seq
            try:
                if self._bar.read32(8) & 5:
                    raise IOError('PCIe mailbox was busy or rejected a command')
                self._bar.write32(0x10,addr)
                if opcode in (2,4):
                    for i in range(16):
                        self._bar.write32(0x20+4*i,(data >> (32*i)) & 0xffffffff)
                self._bar.write32(0x0c,seq << 16 | strobes << 8 | opcode)
                deadline = time.monotonic()+self.timeout
                while True:
                    state = self._bar.read32(8)  # non-posted read flushes prior posted BAR writes
                    response = self._bar.read32(0x14)
                    if state & 4:
                        raise IOError('PCIe mailbox rejected a staged command')
                    if state & 2 and not state & 1 and response >> 16 == seq:
                        status = response & 255
                        if status:
                            raise IOError(f'PCIe command {opcode} at {addr:#x}: AXI/mailbox status {status}')
                        if opcode in (1,3):
                            words = 1 if opcode == 1 else 16
                            return sum(self._bar.read32(0x80+4*i) << (32*i) for i in range(words))
                        return 0
                    if time.monotonic() >= deadline:
                        raise TimeoutError(f'PCIe command {opcode} at {addr:#x} did not complete')
                    time.sleep(0.001)
            except BaseException:
                self._failed = True
                raise

    def read_die_temperature(self):
        return None

    def poll(self, off, mask, val, timeout=600.0, expect=0.0):
        deadline = time.monotonic()+timeout
        while True:
            value = self.reg_read(off)
            if value & mask == val:
                return value
            if time.monotonic() >= deadline:
                raise TimeoutError(f'PCIe register {off:#x}: {value:#x}, expected {mask:#x}/{val:#x}')
            time.sleep(0.001)
