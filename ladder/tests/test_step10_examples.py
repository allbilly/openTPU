import os

# The production conftest clears these before opentpu is imported: cached images/programs must
# never mask a drift between the compiler and the simulator.
os.environ.setdefault("OTPU_IMAGE_CACHE", "0")
os.environ["OTPU_IMG_CACHE"] = "0"
os.environ["OTPU_PROG_CACHE"] = "0"
"""Step 10 (ported) — the production standalone-CLI/examples tests, retargeted to the ladder
tree's `examples/` directory (the products' examples import the tree's own opentpu package).

The two production cases that import `opentpu.host.runtime_transport` /
`opentpu.host.runtime_model` (the board-shell rung's modules) are kept but skipped until
step 11; the other four cases are pure CLI/CPU checks (no device is opened)."""
from dataclasses import replace
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[2]   # ladder tests live one level deeper
EXAMPLES = ROOT / 'examples'

def invoke(script, *arguments, cwd=None):
    return subprocess.run([sys.executable, '-B', str(EXAMPLES / script), *map(str, arguments)],
                          cwd=cwd or ROOT, env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'},
                          capture_output=True, text=True, timeout=600)

def test_batch_cli_and_artifacts(tmp_path):
    folder = tmp_path / 'batch'
    result = invoke('run_all.py', '--out', folder, cwd=tmp_path)
    assert result.returncode == 0, result.stdout + result.stderr
    summary = json.loads((folder / 'summary.json').read_text())
    assert summary['status'] == 'PASS' and len(summary['cases']) == 14
    for case in summary['cases']:
        saved = folder / case['example']
        receipt = json.loads((saved / 'result.json').read_text())
        assert receipt['status'] == 'PASS'
        assert receipt['hardware_access_attempted'] is False
        assert receipt['hardware_accessed'] is False
        assert receipt['flash_written'] is False
        words = np.fromfile(saved / 'program.bin', dtype='<u4')
        assert len(words) == receipt['instruction_count'] * 8
        assert (saved / 'dram.bin').stat().st_size == 1 << 20
        assert 'HALT' in (saved / 'program.asm').read_text()
        assert all(row['numpy_match'] and row['isa_bit_exact'] for row in receipt['checks'].values())
        np.testing.assert_allclose(np.load(saved / 'out.npy'), np.load(saved / 'out.reference.npy'),
                                   rtol=2e-5, atol=1e-6)
    old_summary = (folder / 'summary.json').read_bytes()
    repeat = invoke('run_all.py', '--out', folder)
    assert repeat.returncode != 0
    assert (folder / 'summary.json').read_bytes() == old_summary

@pytest.mark.parametrize('script,arguments', [
    ('simple_add.py', ['--size', '1']),
    ('elementwise.py', ['--size', '37', '--op', 'mul']),
    ('gemm.py', ['--m', '5', '--n', '7', '--k', '256']),
    ('gemm.py', ['--m', '1', '--n', '1', '--k', '128']),
    ('conv.py', ['--height', '7', '--width', '6', '--channels', '3', '--filters', '5', '--stride', '2']),
    ('conv.py', ['--height', '1', '--width', '1', '--channels', '1', '--kernel', '1', '--filters', '1']),
    ('pooling.py', ['--op', 'avg', '--height', '7', '--width', '6', '--channels', '3', '--kernel', '3']),
    ('pooling.py', ['--op', 'max', '--height', '1', '--width', '1', '--channels', '1', '--kernel', '1']),
    ('softmax.py', ['--rows', '3', '--cols', '37']),
    ('softmax.py', ['--rows', '1', '--cols', '1']),
    ('rmsnorm.py', ['--rows', '3', '--cols', '37']),
    ('rmsnorm.py', ['--rows', '1', '--cols', '1']),
])
def test_edge_shapes(script, arguments):
    result = invoke(script, *arguments, '--seed', '17')
    assert result.returncode == 0, result.stdout + result.stderr
    assert 'PASS' in result.stdout

@pytest.mark.parametrize('script,arguments,message', [
    ('simple_add.py', ['--size', '0'], 'integer from 1'),
    ('gemm.py', ['--k', '129'], 'multiple of'),
    ('softmax.py', ['--rows', '4096', '--cols', '4096'], '8192'),
    ('conv.py', ['--height', '1'], 'kernel must fit'),
    ('conv.py', ['--channels', '16'], '<= 128'),
    ('pooling.py', ['--kernel', '5'], 'kernel must fit'),
    ('simple_add.py', ['--mode', '2'], 'only to --backend fpga'),
    ('simple_add.py', ['--backend', 'fpga'], 'requires --package'),
])
def test_invalid_requests_fail_early(script, arguments, message):
    result = invoke(script, *arguments)
    assert result.returncode == 2
    assert message in result.stderr

def load_common(monkeypatch):
    monkeypatch.syspath_prepend(str(EXAMPLES))
    spec = importlib.util.spec_from_file_location('basic_examples_common_test', EXAMPLES / '_common.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_failure_receipt_is_durable(monkeypatch, tmp_path):
    common = load_common(monkeypatch)
    import simple_add
    p = common.parser('test')
    folder = tmp_path / 'failure'
    args = p.parse_args(['--out', str(folder)])
    a = np.arange(8, dtype=np.float32)
    with pytest.raises(AssertionError):
        common.execute('bad-reference', p, args, simple_add.add,
                       dict(a=common.Input(a), b=common.Input(a), out=common.Output(a.shape)),
                       dict(out=a + a + 1), rtol=0, atol=0)
    receipt = json.loads((folder / 'result.json').read_text())
    assert receipt['status'] == 'FAIL' and 'AssertionError' in receipt['error']
    assert receipt['hardware_accessed'] is False

@pytest.mark.skip(reason='needs opentpu.host.runtime_transport/runtime_model (step 11)')
def test_source_only_package_refused_without_transport(monkeypatch, tmp_path):
    common = load_common(monkeypatch)
    from opentpu.host import runtime_transport
    def forbid_open(*args, **kwargs):
        pytest.fail('device opening attempted before package qualification')
    monkeypatch.setattr(runtime_transport, 'open_runtime_transport', forbid_open)
    package = tmp_path / 'source-only'
    package.mkdir()
    (package / 'manifest.json').write_text(json.dumps({'status': 'SOURCE_PREPARATION_ONLY'}))
    p = common.parser('test')
    args = p.parse_args(['--backend', 'fpga', '--mode', '2', '--package', str(package),
                         '--out', str(tmp_path / 'result')])
    with pytest.raises(Exception, match='reviewed runtime image'):
        common.execute('test', p, args, None, {}, {})
    assert not (tmp_path / 'result').exists()

@pytest.mark.skip(reason='needs opentpu.host.runtime_transport/runtime_model (step 11)')
def test_fpga_adapter_reads_outputs_without_full_capacity_allocation(monkeypatch, tmp_path):
    common = load_common(monkeypatch)
    import simple_add
    from opentpu.host import runtime_model, runtime_transport
    a = np.arange(37, dtype=np.float32)
    compiled, images = common.compile_kernel(simple_add.add, common.config(),
        a=common.Input(a), b=common.Input(a), out=common.Output(a.shape))
    expected = common.run(compiled, images, backend='isa')
    seen = []
    transport = SimpleNamespace(profile=SimpleNamespace(build_id=0xc0184807, bitstream_sha256='a' * 64),
                                close=lambda: seen.append('transport_closed'))
    monkeypatch.setattr(runtime_transport, 'open_runtime_transport', lambda *a, **k: transport)
    monkeypatch.setattr(runtime_model, 'runtime_config', lambda t: replace(compiled.cfg, DRAM_BYTES=1 << 32))
    class Backend:
        def __init__(self, cfg, initial, actual_transport, **kwargs):
            assert cfg.DRAM_BYTES == 1 << 32 and len(initial[0]) == 1 << 20
        def run(self, programs):
            return {'instructions': [len(programs[0])]}
        def read(self, slice_number, address, length):
            assert slice_number == 0 and length == a.nbytes
            seen.append('read_output')
            return expected.drams[0][address:address + length]
        def close(self):
            seen.append('backend_closed')
    monkeypatch.setattr(runtime_model, 'RuntimeBoardBackend', Backend)
    args = SimpleNamespace(transport='jtag', xvc_host='localhost', xvc_port=3721,
                           mode=2, package=tmp_path)
    state = {}
    stages = []
    result = common._fpga(compiled, images, args, tmp_path, state,
                          lambda: stages.append(dict(state)))
    np.testing.assert_array_equal(result.outputs['out'], a + a)
    assert len(result.drams[0]) == 1 << 20
    assert stages[0]['hardware_access_attempted'] is True and stages[0]['hardware_accessed'] is None
    assert stages[-1]['stage'] == 'reading_outputs'
    assert seen == ['read_output', 'backend_closed', 'transport_closed']
