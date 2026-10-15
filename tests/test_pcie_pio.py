"""PIO host command/ECC/range tests; injected BARs are not physical PCIe evidence."""
from pathlib import Path

import numpy as np
import pytest

from opentpu.host.pcie_pio import MAGIC, PciePioTransport, SysfsBar


class Bar:
    def __init__(self):
        self.words = {0:MAGIC,4:1,8:0,0x14:65535 << 16}
        self.memory = {}
        self.registers = {}
        self.commands = []
        self.closed = False
        self.error = 0
        self.stale = False
        self.pending = None

    def read32(self, off):
        if off == 8 and self.pending is not None:
            seq,result = self.pending
            self.pending = None
            self.words[8] = 2
            if not self.stale:
                self.words[0x14] = seq << 16 | self.error
                for i in range(16):
                    self.words[0x80+4*i] = result >> (32*i) & 0xffffffff
        return self.words.get(off,0)

    def write32(self, off, value):
        self.words[off] = value
        if off == 0x0c:
            op = value & 255
            addr = self.words[0x10]
            data = sum(self.words.get(0x20+4*i,0) << (32*i) for i in range(16))
            self.commands.append((op,addr,data))
            result = 0
            if op == 1:
                result = self.registers.get(addr,0)
            elif op == 2:
                self.registers[addr] = data & 0xffffffff
            elif op == 3:
                result = self.memory.get(addr,int.from_bytes(bytes(range(64)),'little'))
            elif op == 4:
                assert addr % 64 == 0
                self.memory[addr] = data
            self.words[8] = 1
            self.pending = (value >> 16,result)

    def close(self):
        self.closed = True


def test_both_control_windows_and_final_beats_of_both_full_channels():
    bar = Bar()
    transport = PciePioTransport('0000:01:00.0',bar=bar)
    for off in (0x20,0x10044,0x1fffc):
        transport.reg_write(off,0x12345678)
        assert transport.reg_read(off) == 0x12345678
    payload = np.arange(128,dtype=np.uint8)
    for ch in (0,1):
        transport.mem_write(ch,(1 << 31)-128,payload)
        np.testing.assert_array_equal(transport.mem_read(ch,(1 << 31)-128,128),payload)
    assert {addr for op,addr,_ in bar.commands if op == 4} == {0x7fffff80,0x7fffffc0,0xffffff80,0xffffffc0}
    transport.close()
    assert bar.closed


def test_unaligned_write_preserves_complete_ecc_edge_beats_and_out_buffer():
    bar = Bar()
    transport = PciePioTransport('0000:01:00.0',bar=bar)
    transport.mem_write(1,60,np.arange(12,dtype=np.uint8)+100)
    expected = np.tile(np.arange(64,dtype=np.uint8),2)
    expected[60:72] = np.arange(12,dtype=np.uint8)+100
    output = np.empty(128,np.uint8)
    assert transport.mem_read(1,0,128,output) is output
    np.testing.assert_array_equal(output,expected)
    assert all(addr % 64 == 0 for op,addr,_ in bar.commands if op in (3,4))


def test_invalid_ranges_never_submit_commands():
    bar = Bar()
    transport = PciePioTransport('0000:01:00.0',bar=bar)
    for call in (lambda:transport.mem_read(2,0,1),lambda:transport.mem_read(1,(1 << 31)-1,2),
                 lambda:transport.reg_read(0x20000),lambda:transport.reg_write(3,1),
                 lambda:transport.mem_read(0,0,10,np.empty(9,np.uint8))):
        with pytest.raises(ValueError):
            call()
    assert bar.commands == []


@pytest.mark.parametrize('state',[1,4])
def test_reconnect_refuses_busy_or_rejected_mailbox_without_writes(state):
    bar = Bar()
    bar.words[8] = state
    with pytest.raises(IOError,match='busy or rejected'):
        PciePioTransport('0000:01:00.0',bar=bar)
    assert bar.closed and bar.commands == []


@pytest.mark.parametrize('error,stale',[(2,False),(0,True)])
def test_axi_error_and_stale_sequence_poison_transport(error,stale):
    bar = Bar()
    transport = PciePioTransport('0000:01:00.0',bar=bar,timeout=0)
    bar.error = error
    bar.stale = stale
    with pytest.raises((IOError,TimeoutError)):
        transport.reg_read(0)
    before = len(bar.commands)
    with pytest.raises(IOError,match='needs recovery'):
        transport.reg_write(0,1)
    assert len(bar.commands) == before


def test_sequence_wrap_waits_for_done_before_returning_fresh_data():
    class DelayedBar(Bar):
        def __init__(self):
            super().__init__()
            self.polls = 0

        def read32(self, off):
            if off == 8 and self.pending is not None:
                self.polls += 1
                if self.polls < 3:
                    # A matching sequence alone does not prove completion.
                    self.words[0x14] = 1 << 16
                    self.words[0x80] = 0xdeadbeef
                    return 1
            return super().read32(off)
    bar = DelayedBar()
    bar.registers[0x20] = 0x12345678
    transport = PciePioTransport('0000:01:00.0',bar=bar)
    assert transport.reg_read(0x20) == 0x12345678
    assert transport._seq == 1 and bar.polls == 3


def test_bad_identity_is_closed_without_submission():
    bar = Bar()
    bar.words[0] = 0
    with pytest.raises(IOError,match='identity/ABI'):
        PciePioTransport('0000:01:00.0',bar=bar)
    assert bar.closed and bar.commands == []


def test_native_mmio_helper_on_ordinary_file_has_aligned_word_access(tmp_path):
    # Exercise the compiled helper and mapping lifetime on a normal file.
    # This explicitly does not exercise a real BAR, PCIe fabric or TLP ordering.
    device = tmp_path/'0000:01:00.0'
    device.mkdir()
    for name,value in dict(vendor='0x10ee',device='0x0480',enable='1',resource='0x100000 0x100fff 0x200').items():
        (device/name).write_text(value+'\n')
    (device/'resource0').write_bytes(bytes(4096))
    helper = Path(__file__).resolve().parents[1]/'build/fedora-pcie-mmio/manifest.json'
    if not helper.exists():
        pytest.skip('Build the local MMIO helper first')
    bar = SysfsBar('0000:01:00.0',sysfs=tmp_path)
    for off,value in ((0,0x12345678),(4092,0xaabbccdd)):
        bar.write32(off,value)
        assert bar.read32(off) == value
        assert (device/'resource0').read_bytes()[off:off+4] == value.to_bytes(4,'little')
    for off in (-4,1,4096):
        with pytest.raises(ValueError):
            bar.write32(off,0)
    bar.close()
    bar.close()
    with pytest.raises(IOError,match='closed'):
        bar.read32(0)


def test_unknown_bdf_is_rejected_before_resource_mapping(tmp_path):
    with pytest.raises(ValueError,match='explicit PCIe BDF'):
        SysfsBar('../../devices/target',sysfs=tmp_path)
