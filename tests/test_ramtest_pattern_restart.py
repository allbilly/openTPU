"""A same-image pattern change may clear traffic counters only after a clean drain."""
from copy import deepcopy
import hashlib
import json

import pytest

from tools.probe_ramtest_litedram import reset_clean_generators, require_prbs_package
from tools.fedora_build_ramtest_mig import patch_runtime_pattern_reset


def test_runtime_pattern_reset_patch_is_exact_and_fail_closed(tmp_path):
    path = tmp_path / 'mig_7series_v4_2_init_mem_pattern_ctr.v'
    original = "reg       memc_init_done_reg;\n      memc_init_done_reg <= memc_init_done_i;\n"
    path.write_text(original)
    patch = patch_runtime_pattern_reset(tmp_path)
    changed = path.read_text()
    assert 'reg [5:0] runtime_settle_count;' in changed
    assert 'if (rst_i || !memc_init_done_i)' in changed
    assert 'else if (!runtime_settle_count[5])' in changed
    assert patch.startswith('--- a/')
    with pytest.raises(ValueError, match='differs from reviewed source'):
        patch_runtime_pattern_reset(tmp_path)
    assert path.read_text() == changed


def test_runtime_pattern_reset_partial_match_does_not_modify_source(tmp_path):
    path = tmp_path / 'mig_7series_v4_2_init_mem_pattern_ctr.v'
    original = "reg       memc_init_done_reg;\nunknown version\n"
    path.write_text(original)
    with pytest.raises(ValueError):
        patch_runtime_pattern_reset(tmp_path)
    assert path.read_text() == original


def test_prbs_requires_matching_corrected_package(tmp_path):
    core = tmp_path/'core'
    core.mkdir()
    with pytest.raises(ValueError, match='packaged'):
        require_prbs_package(core, 0xc0172031)
    bit = tmp_path/'ramtest.bit'
    bit.write_bytes(b'fixture-bitstream')
    package = dict(status='EXPERIMENTAL_RAM_ONLY_LITEDRAM_IMAGE_PHYSICAL_TESTS_PENDING',
                   build_id='c0172031', runtime_pattern_reset_fix=True,
                   bitstream=dict(sha256=hashlib.sha256(bit.read_bytes()).hexdigest()))
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(package))
    assert require_prbs_package(core, 0xc0172031) == hashlib.sha256(manifest.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match='matching package'):
        require_prbs_package(core, 0xc0162030)
    bit.write_bytes(b'changed')
    with pytest.raises(ValueError, match='hash differs'):
        require_prbs_package(core, 0xc0172031)
    package['runtime_pattern_reset_fix'] = False
    manifest.write_text(json.dumps(package))
    with pytest.raises(ValueError, match='matching package'):
        require_prbs_package(core, 0xc0172031)


class Link:
    def __init__(self):
        self.regs = {0x28: 0, 0x2c: 3, 0x44: 0}
        self.writes = []

    def reg_read(self, address):
        return self.regs[address]

    def reg_write(self, address, value):
        self.writes.append((address, value))
        self.regs[address] = value


def clean_row():
    channel = dict(calibrated=True, initialized=True, ui_reset=False,
        full_write_passes=1, full_read_command_passes=2,
        write_commands=1 << 25, written_beats=1 << 25,
        read_commands=2 << 25, returned_beats=2 << 25, compared_beats=2 << 25,
        ecc={'ecc_enable': 1}, ecc_corrected_beats=0, ecc_uncorrectable_beats=0,
        watchdog_errors=0, compare_error=0, bad_compare_cycles=0, cumulative_bad_byte_lanes=0)
    return dict(traffic_reset=0, traffic_pause=3, native_command_pending=0, protocol_errors=0,
                channels={'0': deepcopy(channel), '1': deepcopy(channel)})


def test_clean_restart_writes_only_traffic_reset():
    link = Link()
    reset_clean_generators(link, clean_row())
    assert link.writes == [(0x28, 3)]


@pytest.mark.parametrize('key,value', [
    ('calibrated', False), ('initialized', False), ('ui_reset', True),
    ('full_write_passes', 0), ('full_read_command_passes', 0),
    ('written_beats', (1 << 25)-1), ('returned_beats', (2 << 25)-1),
    ('compared_beats', (2 << 25)-1), ('ecc_corrected_beats', 1),
    ('ecc_uncorrectable_beats', 1), ('watchdog_errors', 1),
    ('compare_error', 1), ('bad_compare_cycles', 1), ('cumulative_bad_byte_lanes', 1),
    ('ecc', {'ecc_enable': 0}), ('first_read_mismatch', {'queue_overflow': True}),
    ('first_read_mismatch', {'queue_underflow': True}), ('first_read_mismatch', {'captured': True}),
])
def test_unclean_restart_preserves_state(key, value):
    row, link = clean_row(), Link()
    row['channels']['0'][key] = value
    with pytest.raises(ValueError, match='clean, drained'):
        reset_clean_generators(link, row)
    assert not link.writes


@pytest.mark.parametrize('key,value', [('traffic_reset', 1), ('traffic_pause', 1),
    ('native_command_pending', 1), ('protocol_errors', 1), ('channels', {})])
def test_wrong_control_state_is_rejected(key, value):
    row, link = clean_row(), Link()
    row[key] = value
    with pytest.raises(ValueError):
        reset_clean_generators(link, row)
    assert not link.writes


@pytest.mark.parametrize('address,value', [(0x28, 1), (0x2c, 1), (0x44, 1), (0x44, 1 << 16)])
def test_changed_live_control_is_rejected(address, value):
    link = Link()
    link.regs[address] = value
    with pytest.raises(ValueError, match='state changed'):
        reset_clean_generators(link, clean_row())
    assert not link.writes


def test_reset_readback_failure_is_not_a_success():
    class StuckLink(Link):
        def reg_write(self, address, value):
            self.writes.append((address, value))
    link = StuckLink()
    with pytest.raises(ValueError, match='readback differs'):
        reset_clean_generators(link, clean_row())
    assert link.writes == [(0x28, 3)]
