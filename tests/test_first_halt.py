"""A completed HALT read should reach the final wait without another HALT poll."""
from types import SimpleNamespace

import numpy as np
import pytest

from opentpu.host import board as B
from opentpu.host import regs as R


def make_backend(monkeypatch, mode, *, first_idle=True, error=0):
    clock = SimpleNamespace(now=0.03)
    monkeypatch.setattr(B, "time", SimpleNamespace(perf_counter=lambda: clock.now))

    class Transport:
        poll_calls = 0
        poll_exact = False

        def __init__(self):
            self.status_observations = []

        def reg_read(self, offset):
            if offset == R.R_STATUS:
                clock.now += 0.0002
                self.status_observations.append(clock.now)
                idle = first_idle or len(self.status_observations) > 1
                later_error = error if len(self.status_observations) > 1 else 0
                return R.ST_HALTED | (R.ST_WR_IDLE if idle else 0) | later_error
            return 3_000_000 if offset == R.R_CYCLES else 0

        def reg_read_many(self, offsets):
            return [self.reg_read(offset) for offset in offsets]

        def reg_write(self, offset, value):
            pass

        def poll(self, offset, mask, value, timeout=600.0, expect=0.0):
            self.poll_calls += 1
            return self.reg_read(offset)

    board = B.Board.__new__(B.Board)
    board.t = Transport()
    board._trace, board._t_run = None, 0.0
    board.read = lambda addr, size: np.zeros(size, np.uint8)
    backend = B.BoardBackend.__new__(B.BoardBackend)
    backend.board = board
    backend.info = {"core_khz": 100_000}
    backend._stream = (0, 384, 128, 1) if mode == "stream" else None
    backend._due, backend._expects, backend._t0s = {}, {}, {}
    backend._expect, backend._ratio = 0.03, 1.0
    backend._key, backend._running = "program", [[]]
    backend._seen, backend.status = None, None
    backend.host = (lambda: False) if mode == "serve" else None
    return backend


@pytest.mark.parametrize("mode", ["stream", "serve"])
@pytest.mark.parametrize("first_idle", [False, True])
def test_first_halt_avoids_duplicate_poll_and_preserves_first_observation(monkeypatch, mode, first_idle):
    backend = make_backend(monkeypatch, mode, first_idle=first_idle)
    result = backend.wait(feed=lambda *args: None)
    assert result["cycles"] == 3_000_000
    assert backend.board.t.poll_calls == 0
    assert backend.board.t_seen == backend.board.t.status_observations[0]
    assert backend.board.t_seen > 0.03            # timestamp is after the successful read
    assert backend.board.seen_exact is False
    assert len(backend.board.t.status_observations) >= (2 if first_idle else 3)


@pytest.mark.parametrize("error", [R.ST_ERROR, R.ST_AXI_ERR])
def test_first_halt_still_checks_later_hardware_errors(monkeypatch, error):
    backend = make_backend(monkeypatch, "stream", error=error)
    with pytest.raises(RuntimeError):
        backend.wait(feed=lambda *args: None)


def test_first_halt_normal_wait_still_polls(monkeypatch):
    backend = make_backend(monkeypatch, "normal")
    backend.wait()
    assert backend.board.t.poll_calls == 1
    assert backend.board.t_seen == backend.board.t.status_observations[0]
