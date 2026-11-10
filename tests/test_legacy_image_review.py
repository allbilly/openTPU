"""Historical image tools must keep complete evidence and refuse new builds."""
import importlib
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))

from tools.cdc_report_rows import cdc_rows as shared_cdc_rows
from tools.fedora_review_ramtest_mig import cdc_rows as legacy_cdc_rows


def report(detail=None, warning_count=3):
    # Real Vivado detail formatting: 100 and 1000 have no leading padding.
    rows = [
        '  1  CDC-10  Critical  Combinational logic detected before a synchronizer  1  False Path  reset/C  sync/PRE',
        ' 99  CDC-15  Warning  Clock enable controlled CDC structure detected  0  Max Delay Datapath Only  held[1]/C  req[1]/D',
        '100  CDC-15  Warning  Clock enable controlled CDC structure detected  0  Max Delay Datapath Only  held[2]/C  req[2]/D',
        '1000  CDC-15  Warning  Clock enable controlled CDC structure detected  0  Max Delay Datapath Only  held[3]/C  req[3]/D',
    ]
    if detail is not None:
        rows = detail
    return ('CDC-10  Critical  1  Combinational logic\n'
            f'CDC-15  Warning  {warning_count}  Clock enable controlled CDC\n' +
            '\n'.join(rows) + '\n')


def test_cdc_parsers_preserve_unpadded_three_and_four_digit_rows():
    old, shared = legacy_cdc_rows(report()), shared_cdc_rows(report())
    assert old == shared
    assert len(old) == 4
    assert [row[-1] for row in old] == ['sync/PRE', 'req[1]/D', 'req[2]/D', 'req[3]/D']


@pytest.mark.parametrize('reader', [legacy_cdc_rows, shared_cdc_rows])
def test_cdc_truncated_detail_inventory_is_rejected(reader):
    with pytest.raises(ValueError, match='Incomplete CDC details'):
        reader(report().rsplit('\n', 2)[0] + '\n')


@pytest.mark.parametrize('reader', [legacy_cdc_rows, shared_cdc_rows])
@pytest.mark.parametrize('warning_count', [0, 3])
def test_cdc_malformed_unpadded_row_is_rejected_even_with_zero_summary(reader, warning_count):
    with pytest.raises(ValueError, match='format'):
        reader(report(detail=['1000  CDC-15  Warning  missing fields'], warning_count=warning_count))


@pytest.mark.parametrize('reader', [legacy_cdc_rows, shared_cdc_rows])
def test_cdc_missing_or_duplicated_summary_is_rejected(reader):
    with pytest.raises(ValueError, match='summary'):
        reader('\n'.join(report().splitlines()[2:]))
    with pytest.raises(ValueError, match='Duplicate CDC summary'):
        reader(report() + 'CDC-15  Warning  3  repeated summary\n')


@pytest.mark.parametrize('name', [
    'fedora_build_ramtest_suite', 'fedora_build_ramtest_mig',
    'fedora_build_vivado_pcie_ddr800',
])
def test_legacy_implementation_is_rejected_before_side_effects(name, tmp_path, monkeypatch, capsys):
    module = importlib.import_module('tools.' + name)
    output = tmp_path / 'must-not-exist'
    monkeypatch.setattr(sys, 'argv', [name, '--out', str(output)])

    def forbidden(*args, **kwargs):
        pytest.fail('Retired builder reached subprocess or source-profile access')

    for method in ('run', 'Popen', 'check_output'):
        monkeypatch.setattr(module.subprocess, method, forbidden)
    if hasattr(module, 'profile'):
        monkeypatch.setattr(module, 'profile', forbidden)
    with pytest.raises(SystemExit) as stopped:
        module.main()
    assert stopped.value.code == 2
    assert 'both JTAG and PCIe runtime memory/control interfaces' in capsys.readouterr().err
    assert not output.exists()
