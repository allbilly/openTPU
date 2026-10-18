"""A Qwen benchmark must not reuse partial initialization or another boot."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from opentpu.host import regs as R
from tools import benchmark_spare_c0182800 as bench


@pytest.fixture
def initialized(monkeypatch):
    snapshot = {'mailbox': [0x53435231, 0xc0172068],
                'phase': {'0': 12, '1': 34}, 'ready': {'0': 1, '1': 1}}
    receipt = dict(
        status='PASS_C0182800_ZERO_INITIALIZATION',
        package={'manifest_sha256': 'reviewed-runtime'},
        calibration_before=deepcopy(snapshot), calibration_after=deepcopy(snapshot),
        zero_initialization_chunks=[
            dict(mode=mode, channel=channel, base=base, beats=65536, ticks=70000,
                 returns=65536 if mode else 0, errors=0, bits=0,
                 lanes=[0] * (8 if channel == 0 else 9))
            for mode in (0, 1) for channel in (0, 1)
            for base in range(0, 1 << 31, 4 << 20)])
    regs = {R.R_SCRATCH: R.DRAM_INIT, R.R_STATUS: R.ST_WR_IDLE}
    transport = SimpleNamespace(reg_read=lambda offset: regs[offset])
    profile = SimpleNamespace(manifest_sha256='reviewed-runtime')
    monkeypatch.setattr(bench, 'calibration_snapshot', lambda _: snapshot)
    return receipt, profile, transport, snapshot, regs


@pytest.mark.parametrize('status', [
    'PASS_C0182800_ZERO_INITIALIZATION',
    'PASS_OBSERVED_SPARE_PCIE_MATMUL_LFM2_FULL_MEMORY_QUALIFICATION_PENDING'])
def test_accepts_complete_same_boot_initialization(initialized, status):
    receipt, profile, transport, _, _ = initialized
    receipt['status'] = status
    bench.validate_initialization(receipt, profile, transport)


@pytest.mark.parametrize('fault', [
    'missing_chunk', 'duplicated_chunk', 'short_transfer', 'missing_return',
    'lane_error', 'changed_calibration', 'missing_marker', 'busy', 'other_image'])
def test_rejects_invalid_initialization_before_upload(initialized, fault):
    receipt, profile, transport, snapshot, regs = initialized
    chunks = receipt['zero_initialization_chunks']
    if fault == 'missing_chunk':
        chunks.pop()
    elif fault == 'duplicated_chunk':
        chunks[-1] = dict(chunks[-2])
    elif fault == 'short_transfer':
        chunks[-1]['beats'] -= 1
    elif fault == 'missing_return':
        chunks[-1]['returns'] = 0
    elif fault == 'lane_error':
        chunks[-1]['lanes'][0] = 1
    elif fault == 'changed_calibration':
        snapshot['phase']['0'] += 1
    elif fault == 'missing_marker':
        regs[R.R_SCRATCH] = 0
    elif fault == 'busy':
        regs[R.R_STATUS] |= R.ST_RUN
    elif fault == 'other_image':
        receipt['package']['manifest_sha256'] = 'another-runtime'
    with pytest.raises(ValueError):
        bench.validate_initialization(receipt, profile, transport)


def test_existing_output_is_preserved_before_opening_device(tmp_path, monkeypatch):
    sentinel = tmp_path/'existing-result.json'
    sentinel.write_text('preserve this result')
    monkeypatch.setattr(bench, 'ObservedTransport',
                        lambda _: pytest.fail('device must not be opened'))
    with pytest.raises(FileExistsError):
        bench.main(['--calibration-receipt', 'calibration.json',
                    '--initialization-receipt', 'initialization.json',
                    '--out', str(tmp_path)])
    assert sentinel.read_text() == 'preserve this result'
