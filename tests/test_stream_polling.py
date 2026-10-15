"""Streaming must notice HALT near its estimate despite oversleeping waits."""
from types import SimpleNamespace

import numpy as np
import pytest

from opentpu.host import board as B
from opentpu.host import regs as R


def make_stream(monkeypatch, halt, expect, hint):
    class Clock:
        now = 0.0

        def __init__(self):
            self.sleeps = []

        def perf_counter(self):
            self.now += 2e-6
            return self.now

        def sleep(self, seconds):
            self.sleeps.append((self.now, seconds))
            self.now += seconds + 0.0013

    clock = Clock()

    class Transport:
        def reg_read(self, offset):
            assert offset == R.R_STATUS
            return R.ST_HALTED if clock.now >= halt else 0

        def mem_read(self, channel, offset, size):
            return np.full(size // 4, B.SENTINEL, np.uint32).view(np.uint8)

    backend = B.BoardBackend.__new__(B.BoardBackend)
    backend.board = SimpleNamespace(t=Transport(), _t_run=0.0)
    backend._stream = (0, 384, 128)
    backend._due = {0: 1.0} if hint else {}
    backend._expect = expect
    monkeypatch.setattr(B, "time", clock)
    return backend, clock


@pytest.mark.parametrize("hint", [False, True])
def test_stream_polling_sees_halt_near_estimate_without_oversleep(monkeypatch, hint):
    backend, clock = make_stream(monkeypatch, halt=0.02, expect=0.02, hint=hint)
    backend._stream_logits(lambda *args: pytest.fail("Sentinel output is not ready"))
    assert backend._seen - 0.02 < 0.3e-3
    assert clock.sleeps                         # sleeps still used before the end


@pytest.mark.parametrize("expect", [0.0, 0.02])
def test_stream_polling_keeps_sleeping_outside_its_bounded_window(monkeypatch, expect):
    backend, clock = make_stream(monkeypatch, halt=0.03, expect=expect, hint=True)
    backend._stream_logits(lambda *args: pytest.fail("No output before the hint"))
    assert backend._seen >= 0.03
    assert any(start > 0.021 for start, _ in clock.sleeps)


@pytest.mark.parametrize("hint", [False, True])
def test_sleep_just_before_window_does_not_hide_halt(monkeypatch, hint):
    backend, clock = make_stream(monkeypatch, halt=0.02, expect=0.02, hint=hint)
    clock.now = 0.0178  # the 17.9 ms polling window starts within the next sleep

    def oversleep(seconds):
        clock.sleeps.append((clock.now, seconds))
        clock.now += seconds + 0.0021

    clock.sleep = oversleep
    backend._stream_logits(lambda *args: pytest.fail("Sentinel output is not ready"))
    assert backend._seen - 0.02 < 0.3e-3
    near = backend._expect - B.POLL_EARLY - 0.03 * backend._expect
    assert all(start + delay <= near + 1e-12
               for start, delay in clock.sleeps if start < near)
