"""Voltage selection must preserve unrelated FASM and reject unsafe input."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('openxc7_vref',
    Path(__file__).resolve().parents[1]/'tools/openxc7_vref.py')
vref = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vref)


@pytest.fixture
def plan():
    return dict(banks={
        'HCLK_IOI3_X1Y26':dict(bank=11,feature='HCLK_IOI3_X1Y26.VREF.V_750_MV',used_by_ddr=True),
        'HCLK_IOI3_X1Y182':dict(bank=14,feature='HCLK_IOI3_X1Y182.VREF.V_750_MV',used_by_ddr=False),
    })


def test_bank_voltage_preserves_unrelated_configuration_and_is_idempotent(plan):
    raw='# original route\nCLBLL_L_X2Y0.SLICE_X0.ALUT.INIT[63:0] = 64\'hdeadbeef\nHCLK_IOI3_X1Y26.VREF.V_675_MV\n'
    fixed, changes=vref.correct_fasm(raw,plan)
    assert fixed.splitlines()[:2] == raw.splitlines()[:2]
    assert '.V_675_MV' not in fixed
    assert fixed.splitlines()[2:] == [x['feature'] for x in plan['banks'].values()]
    assert {c['bank'] for c in changes} == {11,14}
    assert vref.correct_fasm(fixed,plan) == (fixed,[])


@pytest.mark.parametrize('raw',[
    '', # Missing a populated DDR bank must not be silently repaired.
    'HCLK_IOI3_X1Y26.VREF.V_675_MV\nHCLK_IOI3_X1Y26.VREF.V_750_MV',
    'HCLK_IOI3_X1Y26.VREF.V_900_MV',
    'HCLK_IOI3_X1Y26.VREF.V_675_MV = 0',
    'HCLK_IOI3_X1Y390.VREF.V_675_MV',
])
def test_missing_conflicting_or_unrequested_bank_voltage_is_rejected(raw,plan):
    with pytest.raises(ValueError):
        vref.correct_fasm(raw,plan)


def test_explicit_one_and_comments_are_supported(plan):
    fixed,_=vref.correct_fasm('HCLK_IOI3_X1Y26.VREF.V_675_MV = 1 # backend\n',plan)
    assert 'HCLK_IOI3_X1Y26.VREF.V_750_MV\n' in fixed
