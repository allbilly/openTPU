"""Chestnut's hardware boundaries and cleanup, without a connected device."""
import struct
from types import SimpleNamespace

import numpy as np
import pytest

from opentpu import quant as Quant
from opentpu.host import chestnut as C
from opentpu.host.board import Board, BoardBackend
from opentpu.host.runstate import DeviceBusy, DeviceLock
from tools.chestnut_benchmark import ParallelQuantization, close_resources, phase_metrics, release_engine


def test_subword_configuration_write_keeps_dword_byte_enables():
    usb = C._ChestnutUsb.__new__(C._ChestnutUsb)
    calls = []
    def control(*args, **kwargs):
        calls.append((args, kwargs))
        return bytes(8)
    usb.control = control
    usb.pcie_cfg_req(6, bus=2, value=0x1234, size=2)
    args = calls[0][0]
    assert args[:4] == (0x40, 0xf0, 0x0c45, 0)
    assert struct.unpack('<III', args[4]) == (0x02000004, 0, 0x12340000)
    assert calls[1] == ((0xc0, 0xf0, 0, 0), {'size': 8})


def test_posted_memory_write_never_reads_a_stale_completion():
    usb = C._ChestnutUsb.__new__(C._ChestnutUsb)
    calls = []
    usb.control = lambda *args, **kwargs: calls.append(args)
    usb.pcie_request(0x40, 0x10000000, 0x89abcdef)
    assert len(calls) == 1
    assert struct.unpack('<III', calls[0][4]) == (0x10000000, 0, 0x89abcdef)


@pytest.mark.parametrize('reply', [bytes(7)+b'\x01', bytes(4)+b'\x20'+bytes(3)])
def test_unsuccessful_pcie_completion_cannot_become_model_data(reply):
    usb = C._ChestnutUsb.__new__(C._ChestnutUsb)
    usb.control = lambda direction, *args, **kwargs: reply if direction == 0xc0 else b''
    with pytest.raises(OSError, match='PCIe completion'):
        usb.pcie_request(0, 0x10000000)


def test_xdata_wrap_is_rejected_before_usb_io():
    usb = C._ChestnutUsb.__new__(C._ChestnutUsb)
    usb.control = lambda *args, **kwargs: pytest.fail('USB must remain untouched')
    with pytest.raises(ValueError, match='wraps'):
        usb.read(0xfff0, 32)


@pytest.mark.parametrize('channel', [0, 1])
def test_ch1_virtual_capacity_never_aliases_the_missing_half(channel):
    t = C.ChestnutTransport.__new__(C.ChestnutTransport)
    t._range(channel, (1 << 30)-64, 64)
    with pytest.raises(ValueError):
        t._range(channel, 1 << 30, 64)


def test_partial_initialization_restores_pci_configuration(monkeypatch):
    initial = {(0, 0x18): 0, (1, 0x18): 0, (2, 0x10): 4}
    state = dict(initial)
    closed, released = [], []
    class Usb:
        def read(self, addr, size):
            return b'\x78'
        def pcie_cfg_req(self, off, bus=0, value=None, size=4):
            if value is not None:
                state[bus, off] = value
                return
            if off == 0:
                return 0x24641b21 if bus < 2 else 0x702810ee
            if bus == 2 and off == 0x2c:
                return 0x4f5410ee
            return state.get((bus, off), 0)
        def close(self):
            closed.append(True)
    monkeypatch.setattr(C, '_ChestnutUsb', Usb)
    monkeypatch.setattr(C, 'DeviceLock', lambda name: SimpleNamespace(release=lambda: released.append(True)))
    with pytest.raises(RuntimeError, match='64-bit BAR'):
        C.ChestnutTransport()
    assert state == initial
    assert closed == [True] and released == [True]


@pytest.mark.parametrize('restore_failure', [False, True])
def test_board_cleanup_keeps_lock_through_pci_restore_and_usb_close(tmp_path, monkeypatch, restore_failure):
    monkeypatch.setenv('OTPU_RUN_DIR', str(tmp_path/'locks'))
    t = C.ChestnutTransport.__new__(C.ChestnutTransport)
    t.devname = 'chestnut-cleanup-test'
    lock = t._otpu_lock = DeviceLock(t.devname)
    t.restore = [(2, 0x10, 0x10000000, 4), (0, 0x18, 0, 4)]
    calls, state = [], {}

    def assert_locked():
        with pytest.raises(DeviceBusy):
            DeviceLock(t.devname)

    def cfg(bus, off, value=None, size=4):
        assert_locked()
        if value is not None:
            calls.append(('restore', bus))
            if restore_failure and bus == 0:
                raise OSError('restore failed')
            state[bus, off] = value
        return state.get((bus, off), 0)

    def usb_close():
        assert_locked()
        calls.append(('usb close',))

    t.cfg = cfg
    t.usb = SimpleNamespace(close=usb_close)
    board = Board(t, check=False)
    backend = BoardBackend.__new__(BoardBackend)
    backend.board = Board(t, check=False)
    backend.status = None
    backend.close()
    board.close()
    board.close()
    assert t._otpu_lock is lock
    assert_locked()
    if restore_failure:
        with pytest.raises(RuntimeError, match='PCI configuration restore failed'):
            t.close()
    else:
        t.close()
    assert calls == [('restore', 0), ('restore', 2), ('usb close',)]
    assert t._otpu_lock is None and t.usb is None
    next_owner = DeviceLock(t.devname)
    next_owner.release()
    t.close()


def test_board_cleanup_still_releases_ordinary_transport_lock(tmp_path, monkeypatch):
    monkeypatch.setenv('OTPU_RUN_DIR', str(tmp_path/'locks'))
    t = SimpleNamespace(devname='ordinary-transport')
    board = Board(t, check=False)
    board.close()
    assert t._otpu_lock is None
    next_owner = DeviceLock(t.devname)
    next_owner.release()


def test_throughput_uses_total_cycles_and_separate_wall_duration():
    result = phase_metrics(512, 8, [{'cycles': 100000000}, {'cycles': 300000000}], 100000000)
    assert result['device_seconds'] == 4
    assert result['device_tok_s'] == 128
    assert result['wall_tok_s'] == 64


def test_teardown_failure_cannot_leave_a_pass_or_skip_other_resources():
    calls = []
    def broken():
        calls.append('broken')
        raise RuntimeError('cleanup failed')
    report = dict(status='PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK')
    close_resources([('first', broken), ('second', lambda: calls.append('second'))], report)
    assert calls == ['broken', 'second']
    assert report['status'] == 'FAIL_CLEANUP'
    assert 'cleanup failed' in report['cleanup_errors'][0]


def test_drain_failure_still_closes_compile_pool_and_backend():
    calls = []
    def broken():
        raise RuntimeError('pending compile failed')
    engine = SimpleNamespace(_drain=broken,
                             _pool=SimpleNamespace(shutdown=lambda wait: calls.append('pool')),
                             backend=SimpleNamespace(close=lambda: calls.append('backend')))
    with pytest.raises(RuntimeError, match='pending compile failed'):
        release_engine(engine)
    assert calls == ['pool', 'backend']
    assert engine._pool is None


@pytest.mark.parametrize('fmt', ['fp4', 'int4'])
def test_parallel_weight_packing_preserves_every_byte_and_scale(fmt):
    weights = np.random.default_rng(42).normal(size=(129, 384)).astype(np.float32)
    weights[0] = 0
    weights[1] = -0.0
    weights[2] *= np.float32(1e-20)
    weights[3] *= np.float32(1e20)
    original = Quant.quantize_mxu
    expected = original(weights, fmt, 128)
    with ParallelQuantization(4):
        actual = Quant.quantize_mxu(weights, fmt, 128)
    assert Quant.quantize_mxu is original
    assert all(np.array_equal(got, want) for got, want in zip(actual, expected))


def test_failed_parallel_pack_restores_standard_packer():
    original = Quant.quantize_mxu
    with pytest.raises(ValueError, match='not a multiple'):
        with ParallelQuantization(4):
            Quant.quantize_mxu(np.ones((129, 129), np.float32), 'fp4', 128)
    assert Quant.quantize_mxu is original
