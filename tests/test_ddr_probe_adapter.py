"""The portable snapshot must avoid calibration/BIST and close its transport."""
import json
from pathlib import Path
import sys

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
