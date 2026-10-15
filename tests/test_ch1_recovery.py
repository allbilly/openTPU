"""Prevent a recovery host from silently aliasing the missing half of memory."""
from unittest.mock import Mock
import pytest
from tools.fedora_run_ch1_lfm2 import check_range,check_marker,VIRTUAL_BYTES,MEMORY_PROFILE


def test_both_virtual_channels_allow_the_last_complete_beat():
    for channel in (0,1):
        check_range(channel,VIRTUAL_BYTES-64,64)


@pytest.mark.parametrize('channel,offset,length',[
    (0,VIRTUAL_BYTES,64),(1,VIRTUAL_BYTES-32,64),
    (2,0,64),(0,-1,64),
])
def test_aliasing_or_invalid_transfers_are_rejected(channel,offset,length):
    with pytest.raises(ValueError):check_range(channel,offset,length)


def test_old_dual_channel_image_is_rejected_before_recovery_tests():
    transport=Mock()
    transport.reg_read.return_value=0
    with pytest.raises(ValueError):check_marker(transport)
    transport.reg_read.assert_called_once_with(0x5c)
    transport.mem_write.assert_not_called()


def test_explicit_recovery_marker_is_required():
    transport=Mock()
    transport.reg_read.return_value=MEMORY_PROFILE
    check_marker(transport)
