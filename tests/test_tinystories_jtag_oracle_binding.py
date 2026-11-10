"""The ISA oracle is package-bound, not a live-board identity receipt."""
from types import SimpleNamespace

import pytest

from tools.run_tinystories_shared_jtag import check_oracle_package_binding


def oracle():
    return {
        "target_build_id": "c0182902",
        "target_bitstream_sha256": "bitstream-sha",
        "target_package_manifest_sha256": "package-sha",
        "oracle_identity_source": "reviewed c0182902 package/configuration; no physical identity asserted",
    }


def profile():
    return SimpleNamespace(bitstream_sha256="bitstream-sha",
                           manifest_sha256="package-sha")


def test_package_bound_oracle_does_not_require_physical_identity_receipt():
    check_oracle_package_binding(oracle(), profile(), "c0182902")


def test_package_bound_oracle_rejects_another_bitstream():
    wrong = oracle()
    wrong["target_bitstream_sha256"] = "different-bitstream"
    with pytest.raises(AssertionError, match="bitstream differs"):
        check_oracle_package_binding(wrong, profile(), "c0182902")


def test_package_bound_oracle_rejects_another_image():
    with pytest.raises(AssertionError, match="another image"):
        check_oracle_package_binding(oracle(), profile(), "c0182863")
