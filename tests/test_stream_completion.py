"""Completion hints must describe the card's output, independent of its consumer."""
from types import SimpleNamespace

import numpy as np
import pytest

from opentpu.host import board as B
from opentpu.host import regs as R


@pytest.mark.parametrize("first_callback_seconds", [0.0, 0.1])
def test_slow_callback_does_not_delay_next_runs_stream(monkeypatch, first_callback_seconds):
    class Clock:
        now = 0.0

        def perf_counter(self):
            return self.now

        def sleep(self, seconds):
            self.now += seconds

    clock = Clock()

    class Transport:
        def reg_read(self, offset):
            assert offset == R.R_STATUS
            return R.ST_HALTED if clock.now >= 0.08 else 0

        def mem_read(self, channel, offset, size):
            assert channel == 1 and size == B.BEAT
            piece = offset // B.BEAT
            ready = (0.005, 0.045)[piece]
            word = B.SENTINEL if clock.now < ready else piece + 1
            return np.full(size // 4, word, np.uint32).view(np.uint8)

    backend = B.BoardBackend.__new__(B.BoardBackend)
    backend.board = SimpleNamespace(
        t=Transport(), _t_run=0.0,
        read=lambda addr, size: np.full(size // 4, addr // 128 + 1,
                                       np.uint32).view(np.uint8),
    )
    backend._stream = (0, 384, 128)
    backend._due = {}
    backend._expect = 0.08
    monkeypatch.setattr(B, "time", clock)

    during = []
    for callback_seconds in (first_callback_seconds, 0.0):
        clock.now = 0.0
        fed = []

        def feed(offset, words):
            assert np.all(words == offset // 128 + 1)
            fed.append(offset)
            clock.sleep(callback_seconds)

        backend._stream_logits(feed)
        during.append(backend.last_stream["during"])
        assert fed == [0, 128][:during[-1]]

    assert during[0] == (1 if first_callback_seconds else 2)
    assert during[1] == 2, (during, backend._due)
