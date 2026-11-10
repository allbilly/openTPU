"""Exercise the probe's complete host control paths without opening hardware."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

from opentpu.host import ddrcal, jtag, selfcal
from tools import probe_ramtest_litedram as P


class Link:
    def __init__(self):
        self.regs = {0:0x4c445254, 4:3, 8:0xc0172031, 12:800, 16:3, 0x3c:100000,
                     0x28:0, 0x2c:3, 0x30:2, 0x34:0, 0x38:3, 0x40:1,
                     0x44:0, 0x48:0x52444331}
        self.raw = {}
        for channel in (0, 1):
            words = [0]*64
            words[0] = 1 | 8 | 128  # calibrated, initialized, enabled
            words[1] = 2
            for index in (2, 4, 6, 60, 62):
                words[index] = 1 << 25
            words[14] = words[15] = words[59] = 1
            self.raw[channel] = words
        self.writes = []
        self.closed = False
        self.stuck_pause = False
        self.close_error = None
        self.snapshot_error = None

    def reg_read(self, address):
        if 0x100 <= address < 0x300:
            return self.raw[(address-0x100)//0x100][(address % 0x100)//4]
        return self.regs.get(address, 0)

    def reg_write(self, address, value):
        self.writes.append((address, value))
        if address == 0x24 and self.snapshot_error is not None:
            raise self.snapshot_error
        if not (address == 0x2c and self.stuck_pause):
            self.regs[address] = value

    def read_die_temperature(self):
        return 42.

    def close(self):
        self.closed = True
        if self.close_error:
            raise self.close_error


@pytest.fixture
def probe(tmp_path, monkeypatch):
    core = tmp_path/'core'
    core.mkdir()
    for name in P.CORE_FILENAMES:
        (core/name).write_text("phy = {'sys_hz':100000000}\n" if name == 'sdram_init.py' else name+'\n')
    profile = dict(status='GENERATED_PROFILE_PASS_IMPLEMENTATION_NOT_RUN', part='xc7k480tffg1156-2',
                   parameters=dict(CORE_KHZ=100000, DDR_MTS=800),
                   files={name:dict(name=name, bytes=(core/name).stat().st_size,
                       sha256=hashlib.sha256((core/name).read_bytes()).hexdigest())
                       for name in P.CORE_FILENAMES})
    profile_path = core/'openxc7-profile.json'
    profile_path.write_text(json.dumps(profile))
    link, calls, opened = Link(), [], []
    ecc = {ch:dict(ecc_enable=1, ecc_sec_errors=0, ecc_ded_errors=0) for ch in (0, 1)}
    calibration = dict(done=True, channels={ch:('ok', '') for ch in (0, 1)})
    state = SimpleNamespace(core=core, profile=profile, profile_path=profile_path,
                            link=link, calls=calls, opened=opened, ecc=ecc,
                            calibration=calibration, open_error=None, sleep_error=None, now=0., sleeps=[])

    def open_link(*args, **kwargs):
        opened.append((args, kwargs))
        if state.open_error:
            raise state.open_error
        return link

    class Channel:
        def __init__(self, csr, channel):
            self.channel = channel

        def r(self, name):
            return ecc[self.channel][name]

        def w(self, name, value):
            calls.append(('channel_write', self.channel, name, value))
            assert name == 'ecc_clear' and value == 1
            ecc[self.channel].update(ecc_sec_errors=0, ecc_ded_errors=0)

    def sleep(seconds):
        state.sleeps.append(seconds)
        if state.sleep_error:
            raise state.sleep_error
        state.now += seconds

    monkeypatch.setattr(jtag, 'JtagTransport', open_link)
    monkeypatch.setattr(ddrcal, 'csr_map', lambda path:{})
    monkeypatch.setattr(ddrcal, 'WordCsr', lambda *a, **k:SimpleNamespace(
        w=lambda name,value:calls.append(('csr_write', name, value))))
    monkeypatch.setattr(ddrcal, 'Chan', Channel)
    monkeypatch.setattr(selfcal, 'state', lambda csr:deepcopy(calibration))
    monkeypatch.setattr(selfcal, 'wait', lambda *a, **k:deepcopy(calibration))
    monkeypatch.setattr(selfcal, 'result', lambda *a:{ch:dict(state='ok') for ch in (0, 1)})
    monkeypatch.setattr(selfcal, 'hold', lambda csr:calls.append(('hold',)))
    monkeypatch.setattr(selfcal, 'release', lambda csr:calls.append(('release',)))
    monkeypatch.setattr(P, 'time', SimpleNamespace(monotonic=lambda:state.now, sleep=sleep))

    def run(action='status', *extra):
        out = tmp_path/'result'
        monkeypatch.setattr(sys, 'argv', ['probe', '--core', str(core), '--expect-build-id', 'c0172031',
            '--out', str(out), '--action', action, '--seconds', '0', *extra])
        return P.main()

    state.run = run
    state.receipt = lambda:json.loads((tmp_path/'result/manifest.json').read_text())
    state.controls = lambda:[item for item in link.writes if item[0] != 0x24]
    return state


@pytest.mark.parametrize('change', ['omit-csr', 'duplicate', 'escape', 'changed-csr', 'wrong-profile'])
def test_bad_core_is_rejected_before_any_transport_access(probe, change):
    if change == 'omit-csr':
        del probe.profile['files']['csr.csv']
    elif change == 'duplicate':
        probe.profile['files']['extra'] = probe.profile['files']['csr.csv']
    elif change == 'escape':
        probe.profile['files']['csr.csv']['name'] = '../csr.csv'
    elif change == 'changed-csr':
        (probe.core/'csr.csv').write_text('modified unreviewed CSR addresses')
    else:
        probe.profile['parameters']['DDR_MTS'] = 1066
    probe.profile_path.write_text(json.dumps(probe.profile))
    assert probe.run('recalibrate') == 1
    assert not probe.opened and not probe.calls and not probe.link.writes
    assert probe.receipt()['physical_hardware_access_attempted'] is False


@pytest.mark.parametrize('address,value', [(0, 0), (4, 1), (8, 0xc0172030),
                                         (12, 1066), (16, 1), (0x3c, 133333), (0x48, 0)])
def test_wrong_live_identity_or_abi_closes_without_control_writes(probe, address, value):
    probe.link.regs[address] = value
    assert probe.run('start') == 1
    assert probe.link.closed and not probe.link.writes and not probe.calls
    assert probe.receipt()['physical_hardware_accessed'] is True


def test_failed_open_records_attempt_and_uncertain_hardware_access(probe):
    probe.open_error = OSError('mailbox absent after opening cable')
    assert probe.run() == 1
    result = probe.receipt()
    assert result['physical_hardware_access_attempted'] is True
    assert result['physical_hardware_accessed'] is None


def test_status_only_requests_snapshots_and_keeps_calibration_untouched(probe):
    assert probe.run() == 0
    assert probe.link.closed and not probe.controls() and not probe.calls
    assert all(address == 0x24 for address, _ in probe.link.writes)
    assert probe.receipt()['status'] == 'PASS_OBSERVED_FULL_MEMORY_PATTERN'


def test_disabled_requested_channel_cannot_be_omitted_from_passing_verdict(probe):
    probe.link.raw[0][0] &= ~128
    assert probe.run() == 1
    assert 'not enabled' in probe.receipt()['error']
    assert probe.link.closed and not probe.controls()


def test_sampling_interval_cannot_extend_bounded_observation(probe):
    assert probe.run('status', '--seconds', '1', '--interval', '60') == 0
    assert probe.sleeps == [1.] and probe.now == 1.


def test_pause_requires_readback_then_drains_without_reset(probe):
    probe.link.regs[0x2c] = 0
    assert probe.run('pause', '--channels', '1') == 0
    assert probe.controls() == [(0x2c, 2)] and not probe.calls
    assert probe.receipt()['status'] == 'PAUSED_DRAINED_NO_RETRAIN'


def test_ignored_pause_is_not_reported_as_drained(probe):
    probe.link.regs[0x2c] = 0
    probe.link.stuck_pause = True
    assert probe.run('pause') == 1
    assert probe.link.closed and 'pause readback' in probe.receipt()['error']


@pytest.mark.parametrize('defect', ['clean', 'ded', 'capture', 'watchdog', 'protocol', 'unfinished-write'])
def test_corrected_only_continuation_rejects_other_epochs_before_unpausing(probe, defect):
    probe.ecc[0]['ecc_sec_errors'] = 1
    if defect == 'clean':
        probe.ecc[0]['ecc_sec_errors'] = 0
    elif defect == 'ded':
        probe.ecc[0]['ecc_ded_errors'] = 1
    elif defect == 'capture':
        probe.link.regs[0x404] = 1
    elif defect == 'watchdog':
        probe.link.raw[0][0] |= 16
    elif defect == 'protocol':
        probe.link.regs[0x44] = 1 << 16
    else:
        probe.link.raw[0][62] -= 1
    assert probe.run('resume', '--capture-after-corrected') == 1
    assert probe.link.closed and not probe.controls() and not probe.calls


def test_corrected_only_continuation_stays_a_failure_without_clearing_evidence(probe):
    probe.ecc[0]['ecc_sec_errors'] = 7
    assert probe.run('resume', '--capture-after-corrected') == 1
    assert probe.controls() == [(0x2c, 0)] and not probe.calls
    assert probe.receipt()['status'] == 'FAIL_PHYSICAL_RAM_ERRORS'
    assert probe.ecc[0]['ecc_sec_errors'] == 7


@pytest.mark.parametrize('mixed', [False, True])
def test_sticky_capture_is_a_failure_even_without_vendor_compare_counters(probe, mixed):
    probe.link.regs[0x404] = 1
    if mixed:
        probe.link.regs[0x40] = 2
    assert probe.run() == 1
    result = probe.receipt()
    assert result['status'] == 'FAIL_PHYSICAL_RAM_ERRORS'
    assert result['samples'][-1]['channels']['0']['first_read_mismatch']['captured']


def test_start_writes_only_selected_controls_after_calibration(probe):
    probe.link.regs[0x28] = 3
    assert probe.run('start', '--channels', '1', '--pattern', 'zeros') == 0
    assert probe.controls() == [(0x30, 1), (0x34, 0), (0x40, 1), (0x28, 1), (0x2c, 1)]
    assert not probe.calls and probe.receipt()['traffic_started_by_this_command']


@pytest.mark.parametrize('action', ['start', 'recalibrate'])
def test_failed_calibration_state_blocks_start_and_ecc_clear_despite_stale_ready(probe, action):
    probe.link.regs[0x28] = 3
    probe.calibration['channels'][0] = ('error', 'lane scan failed')
    assert probe.run(action) == 1
    assert not any(event[0] == 'channel_write' for event in probe.calls)
    if action == 'start':
        assert not probe.controls()
    assert 'calibration CPU result failed' in probe.receipt()['error']


def test_recalibration_clears_only_selected_ecc_after_saved_success(probe):
    probe.ecc[0]['ecc_sec_errors'] = 7
    assert probe.run('recalibrate', '--channels', '0') == 0
    assert probe.controls() == [(0x2c, 3), (0x28, 3)]
    assert probe.calls == [('hold',), ('csr_write', 'selfcal_config', 257),
                           ('release',), ('channel_write', 0, 'ecc_clear', 1)]
    result = probe.receipt()
    assert result['after_recalibration']['channels']['0']['ecc_corrected_beats'] == 7
    assert result['after_ecc_clear']['channels']['0']['ecc_corrected_beats'] == 0


def test_restart_keeps_calibration_and_ecc_and_leaves_both_channels_paused(probe):
    assert probe.run('restart') == 0
    assert probe.controls() == [(0x2c, 3), (0x28, 3), (0x30, 2), (0x34, 0),
                                (0x40, 1), (0x28, 0), (0x2c, 0), (0x2c, 3)]
    assert not probe.calls and probe.link.regs[0x2c] == 3
    result = probe.receipt()
    assert result['calibration_before_restart'] == result['calibration_after_restart']


def test_capture_latched_during_restart_drain_overrides_earlier_pass(probe):
    original_write = probe.link.reg_write
    released = False

    def latch_on_drain(address, value):
        nonlocal released
        original_write(address, value)
        if (address, value) == (0x2c, 0):
            released = True
        elif released and (address, value) == (0x2c, 3):
            probe.link.regs[0x404] = 1

    probe.link.reg_write = latch_on_drain
    assert probe.run('restart') == 1
    assert probe.receipt()['status'] == 'FAIL_PHYSICAL_RAM_ERRORS'
    assert not probe.calls and probe.link.closed


def test_interruption_replaces_prior_pass_and_closes_transport(probe):
    probe.sleep_error = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        probe.run('status', '--seconds', '30')
    assert probe.link.closed and not probe.controls()
    assert probe.receipt()['status'] == 'FAIL_INTERRUPTED'


def test_restart_failure_requests_pause_without_reset_or_clearing_counters(probe):
    original_write = probe.link.reg_write

    def fail_after_release(address, value):
        original_write(address, value)
        if (address, value) == (0x2c, 0):
            probe.link.snapshot_error = OSError('snapshot failed')

    probe.link.reg_write = fail_after_release
    assert probe.run('restart') == 1
    assert probe.controls()[-1] == (0x2c, 3)
    assert probe.link.closed and not probe.calls
    assert probe.receipt()['restart_failure_pause'] == 'Pause read back; drainage unproven'


def test_cleanup_failure_never_leaves_a_success_receipt(probe):
    probe.link.close_error = OSError('close failed')
    with pytest.raises(RuntimeError, match='cleanup failed'):
        probe.run()
    assert probe.receipt()['status'] == 'FAIL'
    assert probe.receipt()['cleanup_error'] == 'close failed'


def test_cleanup_interruption_saves_failure_and_propagates(probe):
    probe.link.close_error = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt):
        probe.run()
    assert probe.link.closed and probe.receipt()['status'] == 'FAIL_INTERRUPTED'


def test_restart_pause_interruption_still_closes_and_saves(probe):
    original_write = probe.link.reg_write

    def interrupt_cleanup(address, value):
        if (address, value) == (0x2c, 3) and probe.link.snapshot_error:
            raise KeyboardInterrupt()
        original_write(address, value)
        if (address, value) == (0x2c, 0):
            probe.link.snapshot_error = OSError('snapshot failed')

    probe.link.reg_write = interrupt_cleanup
    with pytest.raises(KeyboardInterrupt):
        probe.run('restart')
    assert probe.link.closed and probe.receipt()['status'] == 'FAIL_INTERRUPTED'
    assert not probe.calls
