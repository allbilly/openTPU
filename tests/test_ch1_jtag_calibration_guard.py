"""Regression for the real VERSION/STATUS mix-up after a passing CH1 soak."""
from unittest.mock import patch
import pytest
from opentpu.host import regs as R
from opentpu.host.jtag import JtagTransport
from tools.fedora_run_ch1_jtag_lfm2 import CalibratedJtagTransport


def transport(armed=True):
    t=object.__new__(CalibratedJtagTransport)
    t.guard_calibration=armed
    return t


def test_full_compute_version_does_not_trigger_a_calibration_failure():
    # The actual D128/MCOLS4/LANES8 word has neither ready bit set.
    value=(128<<16)|(4<<8)|8
    with patch.object(JtagTransport,'reg_read',return_value=value) as read:
        assert transport().reg_read(R.R_VERSION)==value
        read.assert_called_once_with(0x04)


@pytest.mark.parametrize('value',[0,R.ST_CALIB0,R.ST_CALIB1])
def test_missing_virtual_ready_flags_stop_before_host_recalibration(value):
    with patch.object(JtagTransport,'reg_read',return_value=value) as read:
        with pytest.raises(IOError,match='refusing host recalibration of physical CH0'):
            transport().reg_read(R.R_STATUS)
        read.assert_called_once_with(0x0c)


def test_both_virtual_channels_ready_permits_status_reads():
    value=R.ST_CALIB0|R.ST_CALIB1|R.ST_HALTED
    with patch.object(JtagTransport,'reg_read',return_value=value):
        assert transport().reg_read(R.R_STATUS)==value


def test_initial_uncalibrated_identity_can_be_read_before_guard_is_armed():
    with patch.object(JtagTransport,'reg_read',return_value=0):
        assert transport(armed=False).reg_read(R.R_STATUS)==0
