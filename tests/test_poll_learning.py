"""Clock learning must use register observations without learning sleep overshoot."""
from types import SimpleNamespace

import numpy as np
import pytest

from opentpu.host import board as B
from opentpu.host import regs as R


class Clock:
    now = 0.0

    def perf_counter(self):
        self.now += 2e-6
        return self.now

    def sleep(self, seconds):
        self.now += seconds + (0.002 if seconds <= 0.0001 else 0.0001)


def make_backend(clock):
    class Transport:
        poll = B.XdmaTransport.poll

        def reg_read(self, offset):
            assert offset == R.R_STATUS
            return R.ST_WR_IDLE | (R.ST_HALTED if clock.now >= 0.03 else 0)

        def reg_read_many(self, offsets):
            return [R.ST_HALTED | R.ST_WR_IDLE] + [0] * (len(offsets) - 1)

        def reg_write(self, offset, value):
            pass

    board = B.Board.__new__(B.Board)
    board.t = Transport()
    board._trace = None
    board._t_run = 0.0
    backend = B.BoardBackend.__new__(B.BoardBackend)
    backend.board = board
    backend._seen = None
    backend._ratio = 1.0
    return backend


def test_poll_learning_recovers_from_a_short_estimate_and_oversleep(monkeypatch):
    clock = Clock()
    backend = make_backend(clock)
    monkeypatch.setattr(B, "time", clock)
    expect, late = 0.0, []
    dev = 0.03 * 0.97
    for _ in range(12):
        clock.now = 0.0
        backend.board.wait(expect=expect)
        expect = backend._next_expect(dev)
        late.append(backend.board.t_seen - 0.03)
        if not backend.board.seen_exact:
            assert backend._ratio <= 0.03 / dev
    assert backend._ratio > 1.02
    assert np.median(late[4:]) < 0.4e-3, late


def test_poll_learning_clears_old_lower_bound_on_a_late_first_read(monkeypatch):
    clock = Clock()
    backend = make_backend(clock)
    backend.board.t.poll_false_at = 0.0305
    clock.now = 0.0312
    monkeypatch.setattr(B, "time", clock)
    backend.board.wait()
    assert backend.board.t_not_halted is None
    backend._next_expect(0.03 * 0.97)
    assert backend._ratio == 1.0


@pytest.mark.parametrize("seen, lower, exact, want", [
    (1.05, None, False, 1.0),    # late first observation gives no lower bound
    (1.05, 0.99, False, 1.0),    # failed read did not prove the estimate too short
    (1.05, 1.02, False, 1.02),   # proved lower bound excludes the sleep's overshoot
    (1.20, 1.02, False, 1.02),   # a huge wake delay does not discard a valid lower bound
    (1.20, 1.11, False, 1.0),    # the clock-ratio guard still rejects gross deviations
    (0.98, 0.97, False, 0.99),   # upper-bound downward learning remains smoothed
    (1.04, None, True, 1.02),    # exact upward learning remains smoothed
])
def test_poll_learning_respects_observation_bounds(seen, lower, exact, want):
    backend = B.BoardBackend.__new__(B.BoardBackend)
    backend._ratio, backend._seen = 1.0, None
    dev, start = 0.03, 1.0
    backend.board = SimpleNamespace(_t_run=start, t_seen=start + seen * dev,
                                    t_not_halted=None if lower is None else start + lower * dev,
                                    seen_exact=exact)
    assert backend._next_expect(dev) == pytest.approx(want * dev)
    assert backend._ratio == pytest.approx(want)
