"""Successor calibration must fail closed across bitstream identities."""
import pytest
import json

from opentpu.host import regs as R
from opentpu.host.spare_c0182902 import BUILD_ID, SpareC0182902Profile


class Registers:
    def __init__(self, build_id=BUILD_ID):
        self.values = {
            R.R_ID: R.ID_OTPU,
            R.R_VERSION: (128 << 16) | (4 << 8) | 8,
            R.R_REGMAP: 5,
            R.R_CORE_KHZ: 133333,
            R.R_BUILD_ID: build_id,
            R.R_DDR_MTS: 1066,
            R.R_ACT_ROWS: 4,
            R.R_CAPS: R.CAP_HOSTCAL | R.CAP_DDR | R.CAP_ACT,
        }

    def reg_read(self, offset):
        return self.values.get(offset, 0)


def test_successor_guard_checks_all_c0182902_runtime_identity():
    profile = object.__new__(SpareC0182902Profile)
    result = profile.check_image(Registers())
    assert result[f"{R.R_BUILD_ID:#x}"] == BUILD_ID


def test_successor_guard_rejects_reference_image_build_id():
    profile = object.__new__(SpareC0182902Profile)
    with pytest.raises(ValueError, match="image identity differs"):
        profile.check_image(Registers(build_id=0xC0182863))


def test_successor_profile_rejects_reference_build_id_before_device_access(tmp_path):
    from opentpu.host.spare_c0182902 import PACKAGE_STATUS

    (tmp_path / "manifest.json").write_text(json.dumps({
        "status": PACKAGE_STATUS,
        "build_id_register": "0xc0182863",
    }))
    with pytest.raises(ValueError, match="c0182902"):
        SpareC0182902Profile(tmp_path)
