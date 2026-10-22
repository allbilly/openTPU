"""Elapsed observations must retain behavior, ownership and verification gates."""
import json
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from opentpu import isa as I
from opentpu.host import regs as R
from opentpu.host.board import BoardBackend
from opentpu.host.program_verify import ProgramReadbackBoard
from opentpu.isasim import board_config
from tools.host_benchmark_profile import HostProfiler
from tools import benchmark_spare_c0182863 as benchmark


def operation(profile, label, phase='DECODE'):
    return next(row for row in profile.snapshot()['operations']
                if row['phase'] == phase and row['operation'] == label)


def test_nested_elapsed_times_and_instance_restoration():
    timer = SimpleNamespace(now=0.)
    profiler = HostProfiler(lambda: timer.now)

    class Target:
        def inner(self, value):
            timer.now += 3
            return value+1

        def outer(self, value):
            timer.now += 1
            value = self.inner(value)
            timer.now += 2
            return value*2

    target, untouched = Target(), Target()
    original = Target.outer
    profiler.set_phase('DECODE')
    profiler.attach(target, ('inner', 'outer'), 'work')
    assert target.outer(4) == 10
    assert not vars(untouched) and Target.outer is original
    outer = operation(profiler, 'work.outer')
    inner = operation(profiler, 'work.inner')
    assert outer['inclusive_seconds'] == 6 and outer['self_seconds'] == 3
    assert inner['inclusive_seconds'] == inner['self_seconds'] == 3
    assert outer['calls'] == inner['calls'] == 1
    profiler.close()
    assert not vars(target) and Target.outer is original
    result = profiler.snapshot()
    assert result['closed'] and result['active_calls'] == 0
    assert result['attached_methods'] == ['work.inner', 'work.outer']
    assert all(row['complete'] for row in result['phase_intervals'])
    profiler.close()


def test_overlapping_threads_are_measured_without_claiming_wall_partition():
    timer = SimpleNamespace(now=0.)
    profiler = HostProfiler(lambda: timer.now)
    entered = threading.Barrier(3)
    release = threading.Event()
    target = SimpleNamespace(work=lambda: (entered.wait(timeout=2), release.wait(timeout=2)))
    profiler.set_phase('DECODE')
    profiler.attach(target, ('work',), 'worker')
    workers = [threading.Thread(target=target.work) for _ in range(2)]
    for worker in workers:
        worker.start()
    entered.wait(timeout=2)
    assert profiler.snapshot()['active_calls'] == 2
    with pytest.raises(RuntimeError, match='Finish profiled worker calls'):
        profiler.close()
    timer.now = 4
    release.set()
    for worker in workers:
        worker.join(timeout=2)
        assert not worker.is_alive()
    row = operation(profiler, 'worker.work')
    assert row['calls'] == 2
    assert row['inclusive_seconds'] == row['self_seconds'] == 8
    profiler.close()
    phase = next(row for row in profiler.snapshot()['phase_intervals'] if row['phase'] == 'DECODE')
    assert phase['elapsed_seconds'] == 4
    assert 'neither sum is a partition' in profiler.snapshot()['interpretation']


def test_call_keeps_entry_phase_when_operation_spans_a_phase_change():
    timer = SimpleNamespace(now=0.)
    profiler = HostProfiler(lambda: timer.now)

    def work():
        timer.now = 1
        profiler.set_phase('DECODE')
        timer.now = 3

    target = SimpleNamespace(work=work)
    profiler.set_phase('PREFILL')
    profiler.attach(target, ('work',), 'worker')
    target.work()
    assert operation(profiler, 'worker.work', 'PREFILL')['inclusive_seconds'] == 3
    assert not any(row['phase'] == 'DECODE' for row in profiler.snapshot()['operations'])
    profiler.close()


@pytest.mark.parametrize('failure', [RuntimeError('USB error'), KeyboardInterrupt()])
def test_failed_calls_preserve_original_exception_and_existing_override(failure):
    profiler = HostProfiler()

    def fail():
        raise failure

    target = SimpleNamespace(read=fail)
    profiler.set_phase('DECODE')
    profiler.attach(target, ('read',), 'transport')
    with pytest.raises(type(failure)) as raised:
        target.read()
    assert raised.value is failure
    assert operation(profiler, 'transport.read')['failed_calls'] == 1
    assert profiler.snapshot()['active_calls'] == 0
    profiler.close()
    assert target.read is fail


def test_profile_will_not_overwrite_another_method_owner():
    profiler = HostProfiler()
    target = SimpleNamespace(work=lambda: 1)
    profiler.attach(target, ('work',), 'target')
    wrapper = target.work
    with pytest.raises(ValueError, match='already attached'):
        profiler.attach(target, ('work',), 'target')
    other = lambda: 2
    target.work = other
    with pytest.raises(RuntimeError, match='changed ownership'):
        profiler.close()
    assert target.work is other
    target.work = wrapper
    profiler.close()


def test_snapshot_is_detached_and_disabled_helpers_leave_objects_alone():
    profiler = HostProfiler()
    target = SimpleNamespace(work=lambda: 1)
    profiler.set_phase('DECODE')
    profiler.attach(target, ('work',), 'target')
    target.work()
    snapshot = profiler.snapshot()
    snapshot['operations'][0]['calls'] = 100
    assert operation(profiler, 'target.work')['calls'] == 1
    profiler.close()
    benchmark.profile_board(None, object())
    benchmark.profile_backend(None, object())
    benchmark.profile_engine(None, object())


def test_invalid_attachment_does_not_leave_partially_wrapped_methods():
    profiler = HostProfiler()
    original = lambda: 1
    target = SimpleNamespace(work=original, capability=True)
    with pytest.raises(TypeError, match='not callable'):
        profiler.attach(target, ('work', 'capability'), 'target')
    assert target.work is original and not profiler.attachments
    profiler.close()


def test_readonly_target_rolls_back_other_methods():
    profiler = HostProfiler()

    class Target:
        def work(self):
            return 1

        @property
        def readonly(self):
            return lambda: 2

    target = Target()
    with pytest.raises(AttributeError):
        profiler.attach(target, ('work', 'readonly'), 'target')
    assert not vars(target) and not profiler.attachments
    profiler.close()


def test_saved_wrapper_still_forwards_after_profile_is_closed():
    profiler = HostProfiler()
    target = SimpleNamespace(work=lambda value: value+1)
    profiler.attach(target, ('work',), 'target')
    saved = target.work
    profiler.close()
    assert saved(3) == 4 and not profiler.snapshot()['operations']


class MemoryTransport:
    devname = None

    def __init__(self):
        self.channels = [np.zeros(1 << 19, np.uint8) for _ in range(2)]
        self.regs = {R.R_ID: R.ID_OTPU, R.R_VERSION: 128 << 16 | 2 << 8 | 8,
                     R.R_REGMAP: 3, R.R_CAPS: R.CAP_CHASH}
        self.events = []
        self.corrupt = False

    def reg_read(self, off):
        return self.regs.get(off, 0)

    def reg_read_many(self, offsets):
        return [self.reg_read(off) for off in offsets]

    def reg_write(self, off, value):
        self.events.append(('register', off, value))
        self.regs[off] = value

    def poll(self, off, mask, value, *args):
        return value

    def mem_write(self, channel, off, data):
        self.channels[channel][off:off+len(data)] = data

    def mem_read(self, channel, off, size):
        self.events.append(('read', channel, off))
        data = self.channels[channel][off:off+size].copy()
        if self.corrupt and channel == 0:
            data[0] ^= 1
        return data


@pytest.mark.parametrize('corrupt', [False, True])
def test_actual_backend_retains_program_comparison_and_withheld_load(tmp_path, corrupt):
    transport = MemoryTransport()
    backend = BoardBackend(board_config(DRAM_BYTES=1 << 20, MCOLS=2),
                           [np.zeros(128, np.uint8)], transport=transport,
                           status=False, program_receipts=tmp_path/'programs')
    profiler = HostProfiler()
    original_load = ProgramReadbackBoard.load_program
    profiler.set_phase('DECODE')
    benchmark.profile_backend(profiler, backend)
    transport.corrupt = corrupt
    transport.events.clear()
    try:
        program = [[I.li(1, 0), I.nop(), I.nop(), I.halt()]]
        if corrupt:
            with pytest.raises(RuntimeError, match='readback differs before IMEM load'):
                backend.start(program)
            assert not any(event[0] == 'register' for event in transport.events)
            assert (tmp_path/'programs/program-000001.expected.bin').is_file()
            assert (tmp_path/'programs/program-000001.actual.bin').is_file()
        else:
            backend.start(program)
            load = ('register', R.R_CTRL, R.CTRL_LOAD)
            run = ('register', R.R_CTRL, R.CTRL_RUN)
            assert transport.events.index(load) < transport.events.index(run)
            assert any(event[0] == 'read' for event in transport.events[:transport.events.index(load)])
        receipt = json.loads((tmp_path/'programs/program-000001.json').read_text())
        assert receipt['imem_load_requested'] is not corrupt
        assert receipt['imem_load_finished'] is not corrupt
        assert operation(profiler, 'board.load_program')['failed_calls'] == int(corrupt)
        assert ProgramReadbackBoard.load_program is original_load
    finally:
        backend.close()
        profiler.close()
