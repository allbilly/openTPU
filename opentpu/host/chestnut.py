"""Chestnut USB3 transport for the permanent CH1 XDMA image.

Uses libusb and Chestnut's documented vendor protocol. PCIe configuration is
saved and restored; this transport never programs the FPGA or its flash.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import struct
import threading
import time
from pathlib import Path

import numpy as np

from . import ddrcal, regs as R
from .runstate import DeviceLock

ROOT = Path(__file__).resolve().parents[2]


class _ChestnutUsb:
    """The control and bulk subset used by the verified Chestnut firmware."""
    def __init__(self):
        library = ctypes.util.find_library('usb-1.0')
        if library is None:
            library = next((str(p) for p in (Path('/opt/homebrew/lib/libusb-1.0.dylib'),
                                              Path('/usr/local/lib/libusb-1.0.dylib')) if p.exists()), None)
        if library is None:
            raise RuntimeError('libusb-1.0 is required (macOS: brew install libusb)')
        self.lib = ctypes.CDLL(library)
        p, i, u8, u16 = ctypes.c_void_p, ctypes.c_int, ctypes.c_uint8, ctypes.c_uint16
        bindings = {
            'libusb_init': (i, [ctypes.POINTER(p)]),
            'libusb_exit': (None, [p]),
            'libusb_get_device_list': (ctypes.c_ssize_t, [p, ctypes.POINTER(ctypes.POINTER(p))]),
            'libusb_free_device_list': (None, [ctypes.POINTER(p), i]),
            'libusb_get_device_descriptor': (i, [p, p]),
            'libusb_open_device_with_vid_pid': (p, [p, u16, u16]),
            'libusb_claim_interface': (i, [p, i]),
            'libusb_release_interface': (i, [p, i]),
            'libusb_close': (None, [p]),
            'libusb_control_transfer': (i, [p, u8, u8, u16, u16, p, u16, ctypes.c_uint]),
            'libusb_bulk_transfer': (i, [p, u8, p, i, ctypes.POINTER(i), ctypes.c_uint]),
            'libusb_strerror': (ctypes.c_char_p, [i]),
        }
        for name, (result, args) in bindings.items():
            fn = getattr(self.lib, name)
            fn.restype, fn.argtypes = result, args
        self.context, self.handle, self.claimed = p(), None, False
        self.check(self.lib.libusb_init(ctypes.byref(self.context)))
        try:
            devices = ctypes.POINTER(p)()
            count = self.check(self.lib.libusb_get_device_list(self.context, ctypes.byref(devices)))
            matches = 0
            try:
                for index in range(count):
                    descriptor = ctypes.create_string_buffer(18)
                    self.check(self.lib.libusb_get_device_descriptor(devices[index], descriptor))
                    if struct.unpack_from('<HH', descriptor.raw, 8) == (0x3801, 1):
                        matches += 1
            finally:
                self.lib.libusb_free_device_list(devices, 1)
            if matches != 1:
                raise RuntimeError(f'Require one Chestnut 3801:0001; found {matches}')
            self.handle = self.lib.libusb_open_device_with_vid_pid(self.context, 0x3801, 1)
            if not self.handle:
                raise OSError('Cannot open Chestnut USB device')
            self.check(self.lib.libusb_claim_interface(self.handle, 0))
            self.claimed = True
        except BaseException:
            self.close()
            raise

    def check(self, result):
        if result < 0:
            raise OSError(f'Chestnut USB: {self.lib.libusb_strerror(result).decode()} ({result})')
        return result

    def control(self, direction, request, value, index, payload=bytes(), size=0, timeout=5000):
        length = size if direction & 0x80 else len(payload)
        buf = ctypes.create_string_buffer(length)
        if payload:
            ctypes.memmove(buf, payload, length)
        count = self.check(self.lib.libusb_control_transfer(
            self.handle, direction, request, value, index, buf, length, timeout))
        if count != length:
            raise OSError(f'Short USB control transfer: {count}/{length}')
        return buf.raw

    def read(self, addr, size):
        if addr < 0 or size < 0 or addr + size > 0x10000:
            raise ValueError('XDATA read wraps the 16-bit window')
        return b''.join(self.control(0xc0, 0xe4, addr + pos, 0, size=min(255, size-pos))
                        for pos in range(0, size, 255))

    def pcie_request(self, fmt_type, address, value=None, size=4, cnt=0):
        if not 1 <= size <= 4 or (address & 3) + size > 4:
            raise ValueError('PCIe access crosses a dword')
        shift = 8 * (address & 3)
        byte_enable = ((1 << size) - 1) << (address & 3)
        aligned = address & ~3
        payload = struct.pack('<III', aligned & 0xffffffff, aligned >> 32,
                              0 if value is None else int(value) << shift)
        self.control(0x40, 0xf0, fmt_type | byte_enable << 8, 0, payload)
        if fmt_type == 0x40:
            return None  # posted memory write
        reply = self.control(0xc0, 0xf0, 0, 0, size=8)
        status, completion = reply[7], (reply[4] >> 5) & 7
        if status or completion:
            raise OSError(f'PCIe completion at {address:#x}: status={status}, completion={completion}')
        return (struct.unpack_from('<I', reply)[0] >> shift) & ((1 << (8*size))-1)

    def pcie_cfg_req(self, off, bus=0, value=None, size=4):
        if not 0 <= bus <= 255 or not 0 <= off < 4096:
            raise ValueError('Invalid PCIe configuration address')
        fmt = (0x44 if value is not None else 4) | int(bus > 0)
        return self.pcie_request(fmt, bus << 24 | off, value, size)

    def scsi_write(self, data):
        data += bytes((-len(data)) % 512)
        if not 0 < len(data) <= 0x80000:
            raise ValueError('Transfer exceeds Chestnut staging SRAM')
        slots = (len(data) + 0x3fff) // 0x4000
        self.control(0x40, 0xf2, len(data)//512, slots << 8)
        buf, actual = ctypes.create_string_buffer(data), ctypes.c_int()
        self.check(self.lib.libusb_bulk_transfer(self.handle, 2, buf, len(data), ctypes.byref(actual), 5000))
        if actual.value != len(data):
            raise OSError(f'Short USB bulk transfer: {actual.value}/{len(data)}')

    def close(self):
        if self.handle:
            if self.claimed:
                self.lib.libusb_release_interface(self.handle, 0)
                self.claimed = False
            self.lib.libusb_close(self.handle)
            self.handle = None
        if self.context:
            self.lib.libusb_exit(self.context)
            self.context = None


class ChestnutTransport:
    # Board objects borrow this lock; PCI configuration and USB teardown must
    # finish in close() before another transport can acquire the device.
    owns_device_lock = True
    ecc = True
    threaded = False
    streams = False
    bandwidth_test = False
    host_idle = 0.001
    CH_BYTES = 1 << 30
    SRAM = 0x200000
    CHUNK = 0x70000
    READ_CHUNK = 4096 - 512

    def __init__(self, *, timeout=30.0):
        self.dev = 'chestnut://3801:0001'
        self.devname = 'chestnut-3801-0001'
        self._dma = threading.RLock()
        self._otpu_lock = DeviceLock(self.devname)
        self.restore = []
        self.usb = None
        self.timeout = timeout
        self.bars = {}
        self.dma_bar = None
        self.failed = False
        self.transferred_write = self.transferred_read = 0
        try:
            self.usb = _ChestnutUsb()
            self.c = self.usb
            if self.c.read(0xb450, 1) != b'\x78':
                raise RuntimeError('Chestnut PCIe link is not up')
            for bus in (0, 1):
                if self.cfg(bus, 0) != 0x24641b21:
                    raise RuntimeError('Unexpected Chestnut bridge topology')
                self.change(bus, 0x18, ((bus + 1) << 8) | (2 << 16))
            if (self.cfg(2, 0), self.cfg(2, 0x2c)) != (0x702810ee, 0x4f5410ee):
                raise RuntimeError('Expected OpenTPU XDMA endpoint')
            cursor = 0x10000000
            off = 0x10
            while off < 0x28:
                original = self.cfg(2, off)
                if original & 1:
                    raise RuntimeError('Unexpected IO BAR')
                is64 = original & 6 == 4
                self.change(2, off, 0xffffffff)
                mask = self.cfg(2, off) & ~15
                self.cfg(2, off, original)
                if is64:
                    raise RuntimeError('Unexpected 64-bit BAR; stop before mapping')
                if mask:
                    size = (-mask) & 0xffffffff
                    cursor = (cursor + size - 1) & -size
                    self.change(2, off, cursor | (original & 15))
                    self.bars[(off - 0x10) // 4] = (cursor, size)
                    cursor += size
                off += 4
            for bus in (0, 1):
                self.change(bus, 0x20, 0x1ff01000)
                self.change(bus, 4, self.cfg(bus, 4, size=2) | 6, size=2)
            self.change(2, 4, self.cfg(2, 4, size=2) | 6, size=2)
            for index, (base, size) in self.bars.items():
                ident = self.read32(base)
                print(f'BAR{index}: base={base:#x}, bytes={size:#x}, ID={ident:#010x}', flush=True)
                if ident >> 16 == 0x1fc0:
                    self.dma_bar = base
            self.user_bar = self.bars[0][0]
            self._check_image()
            if self.dma_bar is None:
                raise RuntimeError('XDMA engine BAR not found')
            for base in (0, 0x1000):
                if self.read32(self.dma_bar + base + 0x40) & 1:
                    raise RuntimeError('An XDMA channel is already busy')
            self._initialize_memory()
        except BaseException:
            self.close()
            raise

    def _check_image(self):
        if self.reg_read(R.R_ID) != R.ID_OTPU or self.reg_read(0x5c) != 0x08000102:
            raise RuntimeError('Expected live CH1 recovery image')

    def _initialize_memory(self):
        # Recovery preserves the committed CSR ABI. No calibration is rerun and
        # no DDR1066 timing table is applied to the live DDR800 controller.
        self.csr = ddrcal.WordCsr(ddrcal.csr_map(ROOT/'opentpu/host/litedram/csr.csv'),
                                 self.reg_read, self.reg_write, base=R.R_MEMCAL)
        if self.csr.r('selfcal_status') >> 16 != 0x5ca1:
            raise RuntimeError('Calibration CSR ABI identity mismatch')
        self.ch = ddrcal.Chan(self.csr, 1)
        self.guard()

    def cfg(self, bus, off, value=None, size=4):
        return self.c.pcie_cfg_req(off, bus=bus, value=value, size=size)

    def change(self, bus, off, value, size=4):
        self.restore.append((bus, off, self.cfg(bus, off, size=size), size))
        self.cfg(bus, off, value, size=size)

    def read32(self, addr):
        return self.c.pcie_request(0, addr, cnt=0)

    def write32(self, addr, value):
        self.c.pcie_request(0x40, addr, int(value) & 0xffffffff, cnt=0)

    def reg_read(self, off):
        with self._dma:
            return self.read32(self.user_bar + off)

    def reg_write(self, off, value):
        if off == R.R_MEMCAL + 0x2000:
            raise RuntimeError('Global SoC reset CSR is unsupported')
        with self._dma:
            self.write32(self.user_bar + off, value)

    def reg_read_many(self, offsets):
        return [self.reg_read(off) for off in offsets]

    def poll(self, off, mask, value, timeout=600, expect=0):
        deadline = time.monotonic() + timeout
        while True:
            current = self.reg_read(off)
            if current & mask == value:
                return current
            if time.monotonic() >= deadline:
                raise TimeoutError(f'OpenTPU register {off:#x}: {current:#x}')
            time.sleep(0.001)

    def guard(self):
        if self.failed:
            raise RuntimeError('Failed DMA transport requires recovery')
        status = self.reg_read(R.R_STATUS)
        if status & 96 != 96 or status & (R.ST_ERROR | R.ST_AXI_ERR):
            raise RuntimeError(f'CH1 not ready: {status:#x}')
        ecc = {n: self.ch.r(n) for n in ('ecc_enable', 'ecc_sec_errors', 'ecc_ded_errors')}
        if ecc != {'ecc_enable': 1, 'ecc_sec_errors': 0, 'ecc_ded_errors': 0}:
            raise RuntimeError(f'CH1 ECC is not clean: {ecc}')
        return ecc

    def scrub(self):
        self.guard()
        for mode in (0, 1):
            result = ddrcal.bist(self.ch, 1 << 25, mode, 0, 100000000, timeout=120)
            print('CH1 full-memory zero scrub/verify:', mode, result, flush=True)
            if result['beats'] != 1 << 25 or result.get('errors') or any(result.get('lanes', [])):
                raise RuntimeError('CH1 scrub failed')
        self.guard()

    def _transfer(self, card, data, count, read=False):
        # Full ECC beats. One descriptor, stored in bridge SRAM below its data.
        if card % 64 or count % 64 or not 0 < count <= self.CHUNK:
            raise ValueError('DMA requires full aligned 64-byte beats')
        engine = self.dma_bar + (0x1000 if read else 0)
        host = self.SRAM + 512
        src, dst = (card, host) if read else (host, card)
        desc = struct.pack('<8I', 0xad4b0013, count, src & 0xffffffff, src >> 32,
                           dst & 0xffffffff, dst >> 32, 0, 0)
        packet = desc.ljust(512, b'\0') + (bytes(count) if read else data)
        try:
            self.write32(engine + 4, 0)
            self.read32(engine + 0x44)
            self.c.scsi_write(packet)
            self.write32(engine + 0x4080, self.SRAM)
            self.write32(engine + 0x4084, 0)
            self.write32(engine + 0x4088, 0)
            before = self.read32(engine + 0x48)
            self.write32(engine + 4, 7)
            deadline = time.monotonic() + 10
            while True:
                status = self.read32(engine + 0x40)
                done = self.read32(engine + 0x48)
                if status & 0xffffffb8:
                    raise RuntimeError(f'XDMA status error: {status:#x}, completed={done}')
                if not status & 1 and done == 1:
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError(f'XDMA timeout: status={status:#x}, completed={done}, before={before}')
            if read:
                return self.c.read(0xf000 + 512, count)
        except BaseException:
            self.failed = True
            raise
        finally:
            self.write32(engine + 4, 0)

    def mem_write(self, ch, off, data):
        a = np.ascontiguousarray(data, dtype=np.uint8).reshape(-1)
        self._range(ch, off, len(a))
        if off % 64 or len(a) % 64:
            start, end = off // 64 * 64, ((off + len(a) + 63) // 64) * 64
            merged = self.mem_read(ch, start, end - start)
            merged[off-start:off-start+len(a)] = a
            off, a = start, merged
        with self._dma:
            for pos in range(0, len(a), self.CHUNK):
                block = a[pos:pos+self.CHUNK].tobytes()
                self._transfer(ch * (1 << 31) + off + pos, block, len(block))
            self.transferred_write += len(a)

    def mem_read(self, ch, off, count, out=None):
        self._range(ch, off, count)
        start, end = off // 64 * 64, ((off + count + 63) // 64) * 64
        result = bytearray()
        with self._dma:
            # Read only the observed 4 KiB SRAM window, below XDATA wrap.
            for pos in range(start, end, self.READ_CHUNK):
                length = min(self.READ_CHUNK, end - pos)
                result.extend(self._transfer(ch * (1 << 31) + pos, None, length, read=True))
            self.transferred_read += count
        a = np.frombuffer(bytes(result[off-start:off-start+count]), np.uint8).copy()
        if out is not None:
            out[:count] = a
            return out
        return a

    def _range(self, ch, off, count):
        if ch not in (0, 1) or off < 0 or count < 0 or off + count > self.CH_BYTES:
            raise ValueError('CH1 recovery permits 1 GiB per virtual channel')

    def close(self):
        errors = []
        if self.usb is not None:
            for bus, off, value, size in reversed(self.restore):
                try:
                    self.cfg(bus, off, value, size=size)
                    if self.cfg(bus, off, size=size) != value:
                        errors.append((bus, off, 'readback mismatch'))
                except Exception as error:
                    errors.append((bus, off, str(error)))
            self.usb.close()
            self.usb = None
        self.restore = []
        if self._otpu_lock:
            self._otpu_lock.release()
            self._otpu_lock = None
        print('Chestnut PCI configuration restored:', not errors, errors, flush=True)
        if errors:
            raise RuntimeError(f'PCI configuration restore failed: {errors}')


if __name__ == '__main__':
    t = ChestnutTransport()
    try:
        print('Identity and ECC ready:', t.guard(), flush=True)
        print('BAR map:', t.bars, flush=True)
    finally:
        t.close()
