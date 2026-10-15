"""The simulated card must preserve its two-channel byte address map."""
import numpy as np
import pytest

from opentpu.host.fake import FakeTransport


@pytest.mark.parametrize("addr,size", [(0, 128), (128, 512), (512, 8192),
                                       (5, 33), (63, 65), (128, 0)])
@pytest.mark.parametrize("strided", [False, True])
def test_fake_memory_put_preserves_byte_addresses_and_surroundings(addr, size, strided):
    card = FakeTransport(ch_bytes=1 << 14, devname=None)
    for channel in card.ch:
        channel.fill(0xA5)
    source = np.random.default_rng(17).integers(0, 256, size * 2, np.uint8)
    data = source[::2] if strided else source[:size]
    expected = [channel.copy() for channel in card.ch]
    for i, value in enumerate(data):
        byte = addr + i
        beat, in_beat = divmod(byte, 64)
        channel = beat % 2
        expected[channel][(beat // 2) * 64 + in_beat] = value
    card._put(addr, data)
    for got, want in zip(card.ch, expected):
        assert np.array_equal(got, want)
