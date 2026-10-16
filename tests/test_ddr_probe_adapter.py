"""The portable snapshot must avoid calibration/BIST and close its transport."""
import json
import hashlib
from pathlib import Path
import shutil
import sys
from types import SimpleNamespace

import pytest

from tools import fedora_probe_ddr_recovery as probe

CORE = Path(__file__).resolve().parents[1] / 'bitstreams/ch1-pcie-2gb/core'


def adapter(tmp_path, marker=0x08000102, busy=False, close_error=False):
    path = tmp_path / 'transport.py'
    calls = tmp_path / 'closed.json'
    path.write_text('''from pathlib import Path
import json
class Link:
    def __init__(self, calibration_data):
        self.calibration_data = calibration_data
        self.writes = []
    def reg_read(self, off):
        values = {0: 0x4f545055, 4: (128 << 16) | (4 << 8) | 8,
                  0x3c: 3, 0x40: (1 << 27) | 8, 0x44: 100000,
                  0x48: 0x5b1e646c, 0x54: 800,
                  0x11800: 1}
        values[0x5c] = MARKER
        values[0x0c] = STATUS
        return values.get(off, 0)
    def reg_read_many(self, offs):
        return [self.reg_read(off) for off in offs]
    def reg_write(self, off, value):
        self.writes.append([off, value])
    def close(self):
        Path(CALLS).write_text(json.dumps(self.writes))
        if CLOSE_ERROR:
            raise OSError('restore failed')
'''.replace('MARKER', str(marker)).replace('STATUS', str(128 if busy else 1 | 8 | 32 | 64))
       .replace('CALLS', repr(str(calls))).replace('CLOSE_ERROR', repr(close_error)))
    return path, calls


def run_snapshot(monkeypatch, tmp_path, **options):
    path, calls = adapter(tmp_path, **options)
    out = tmp_path / 'result'
    monkeypatch.setattr(probe, 'CORE', probe.CORE)
    monkeypatch.setattr(sys, 'argv', ['probe', '--adapter', str(path), '--core', str(CORE),
                                     '--snapshot-only', '--out', str(out)])
    return out, calls


def test_snapshot_reads_physical_channels_without_starting_tests(monkeypatch, tmp_path):
    out, calls = run_snapshot(monkeypatch, tmp_path)
    assert probe.main() == 0
    result = json.loads((out / 'manifest.json').read_text())
    assert result['status'] == 'PASS_PHYSICAL_DDR_CSR_SNAPSHOT_ONLY_MEMORY_NOT_TESTED'
    assert result['physical_channels']['0']['cal_ready'] == 0
    assert result['physical_channels']['1']['cal_ready'] == 1
    assert result['transport_closed']
    assert json.loads(calls.read_text()) == []


@pytest.mark.parametrize('options', [{'marker': 0}, {'busy': True}])
def test_wrong_image_or_active_compute_closes_before_register_writes(monkeypatch, tmp_path, options):
    out, calls = run_snapshot(monkeypatch, tmp_path, **options)
    assert probe.main() == 1
    assert json.loads((out / 'manifest.json').read_text())['status'] == 'FAIL'
    assert json.loads(calls.read_text()) == []


def test_failed_transport_restore_is_a_failed_receipt(monkeypatch, tmp_path):
    out, calls = run_snapshot(monkeypatch, tmp_path, close_error=True)
    with pytest.raises(RuntimeError, match='cleanup failed'):
        probe.main()
    result = json.loads((out / 'manifest.json').read_text())
    assert result['status'] == 'FAIL'
    assert 'restore failed' in result['cleanup_errors'][0]
    assert calls.is_file()


def soak(monkeypatch, tmp_path, fail_at=None):
    calls = []
    saved = []
    writes = []
    csr = SimpleNamespace(w=lambda name, value: writes.append((name, value)))
    chan = SimpleNamespace(r=lambda name: 1)
    board = SimpleNamespace(info=lambda: dict(temp_c=55.0))
    for name in ('hold', 'release'):
        monkeypatch.setattr(probe.selfcal, name, lambda csr: None)
    monkeypatch.setattr(probe.selfcal, 'present', lambda csr: True)
    monkeypatch.setattr(probe.selfcal, 'wait', lambda *a, **kw: dict(done=True))
    monkeypatch.setattr(probe.selfcal, 'result', lambda *a: {0: dict(state='ok', traffic_checked=True)})
    ticks = iter((0.0, 0.5, 1.0))
    monkeypatch.setattr(probe, 'time', SimpleNamespace(monotonic=lambda: next(ticks)))

    def bist(csr, beats, mode, seed, hz, timeout):
        calls.append((beats, mode, seed))
        bad = len(calls) == fail_at
        return dict(beats=beats, errors=int(bad), lanes=[0]*6+[int(bad), 0, 0],
                    bits=0xff << 48 if bad else 0)
    monkeypatch.setattr(probe.ddrcal, 'bist', bist)
    args = SimpleNamespace(alias=False, firmware=None, soak_seconds=1.0)
    result = {}
    def require(ok, message):
        if not ok:
            raise ValueError(message)
    def save():
        saved.append(json.loads(json.dumps(result)))
    return args, result, board, csr, chan, calls, saved, writes, require, save


def test_soak_uses_changing_seeds_and_records_temperature(monkeypatch, tmp_path):
    args, result, board, csr, chan, calls, saved, writes, require, save = soak(monkeypatch, tmp_path)
    assert probe.probe(args, tmp_path, result, None, board, csr, chan, chan, save, require) == 0
    assert result['status'] == 'PASS_PHYSICAL_CH0_RAW_BIST_SOAK_NORMAL_PORT_PENDING'
    assert [c[1] for c in calls] == [0, 1, 2, 3]*2
    assert all(c[0] == 1 << 25 for c in calls)
    assert len({c[2] for c in calls}) == 2
    assert [r['identity']['temp_c'] for r in result['bist_trials']] == [55.0, 55.0]
    assert result['bist_trials'][-1]['elapsed_seconds'] == 1.0
    assert writes == [('selfcal_config', 1 | (1 << 8))]


def test_soak_stops_and_saves_first_failing_read(monkeypatch, tmp_path):
    args, result, board, csr, chan, calls, saved, writes, require, save = soak(monkeypatch, tmp_path, fail_at=2)
    with pytest.raises(ValueError, match='full-capacity BIST failed'):
        probe.probe(args, tmp_path, result, None, board, csr, chan, chan, save, require)
    assert len(calls) == 2
    assert saved[-1]['bist'][-1]['lanes'][6] == 1
    assert result['bist_trials'] == []


def firmware_manifest(tmp_path):
    data = bytes(range(64))
    image = tmp_path/'firmware/selfcal.bin'
    image.parent.mkdir()
    image.write_bytes(data)
    metadata = dict(firmware='/old/fedora/checkout/selfcal.bin',
                    firmware_relative='firmware/selfcal.bin', sha256=hashlib.sha256(data).hexdigest(),
                    core='/old/fedora/checkout/core',
                    core_config_sha256=probe.firmware_config.configuration_sha256(CORE))
    manifest = tmp_path/'manifest.json'
    manifest.write_text(json.dumps(metadata))
    return manifest, image, data


def test_firmware_configuration_survives_transfer_to_another_host(tmp_path):
    manifest, image, data = firmware_manifest(tmp_path)
    moved_core = tmp_path/'different-core-directory-name'
    moved_core.mkdir()
    for name in ('csr.csv', 'sdram_init.py'):
        shutil.copy2(CORE/name, moved_core/name)
    fw, actual = probe.checked_firmware(manifest, moved_core)
    assert actual == data
    assert fw['core'] != str(moved_core)


def test_firmware_rejects_changed_bytes(tmp_path):
    manifest, image, data = firmware_manifest(tmp_path)
    image.write_bytes(data+b'x')
    with pytest.raises(ValueError, match='hash mismatch'):
        probe.checked_firmware(manifest, CORE)


def test_firmware_rejects_a_changed_calibration_register(tmp_path):
    manifest, image, data = firmware_manifest(tmp_path)
    moved_core = tmp_path/'wrong-core'
    moved_core.mkdir()
    shutil.copy2(CORE/'sdram_init.py', moved_core/'sdram_init.py')
    csv = (CORE/'csr.csv').read_text()
    old = 'csr_register,cal_ready,0x00001000,1,rw'
    assert csv.count(old) == 1
    (moved_core/'csr.csv').write_text(csv.replace(old, 'csr_register,cal_ready,0x00001004,1,rw'))
    with pytest.raises(ValueError, match='configuration mismatch'):
        probe.checked_firmware(manifest, moved_core)
