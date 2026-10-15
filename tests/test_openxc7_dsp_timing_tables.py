"""Check signed vendor timing bounds and reject unsupported DSP semantics."""
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "openxc7_dsp_timing_tables",
    Path(__file__).resolve().parents[1] / "tools/openxc7_dsp_timing_tables.py")
timing = importlib.util.module_from_spec(spec)
spec.loader.exec_module(timing)


def pins():
    return timing.pin_map([
        {"name": "CLK", "width": 1, "direction": "input"},
        {"name": "A", "width": 2, "direction": "input"},
        {"name": "P", "width": 2, "direction": "output"},
    ])


def arc(kind, source, target, minimum, maximum):
    return {"type": kind, "from": source, "to": target, "disabled": False,
            "transition": "ff rf rr fr" if kind == "combinational" else "rr rf",
            "delays_ns": dict(zip(timing.BOUND_FIELDS, [minimum, maximum] * 4))}


def test_negative_hold_and_fractional_ps_round_outwards():
    key, bounds = timing.normalize_arc(arc("hold", "CLK", "A[0]", -.0051, .0071), pins(), 0)
    assert key == ("hold", "CLK", "A0")
    assert bounds[:4] == (-6, 8, -6, 8)


def test_nonmonotonic_negative_hold_corners_are_retained():
    record = arc("hold", "CLK", "A[0]", -.078, -.078)
    for field in timing.BOUND_FIELDS:
        if "SLOW" in field:
            record["delays_ns"][field] = -.330
    _, bounds = timing.normalize_arc(record, pins(), 0)
    assert bounds[:4] == (-330, -78, -330, -78)
    assert bounds[4:] == (-78, -78, -330, -330, -78, -78, -330, -330)


def test_mixed_registered_and_combinational_pins_are_preserved():
    config = {"probe_cell": "dsp", "parameters_raw": {"IS_CLK_INVERTED": "1'0"},
              "full_design_cells": ["original"]}
    arcs = [arc("setup", "CLK", "A[0]", .1, .2), arc("hold", "CLK", "A[0]", -.01, .02),
            arc("Reg Clk to Q", "CLK", "P[0]", .3, .4),
            arc("combinational", "A[0]", "P[0]", .5, .6)]
    table = timing.convert_configuration((config, arcs, pins()))
    assert table["hybrid_inputs"] == ["A0"]
    assert table["hybrid_outputs"] == ["P0"]
    assert len(table["arcs"]) == 4
    assert table["clock_edge"] == "rising"


@pytest.mark.parametrize("change", [
    {"type": "recovery"}, {"from": "P[0]"}, {"to": "P[0]"},
    {"transition": "fr ff"}, {"to": "A[2]"},
])
def test_unsupported_arc_semantics_fail(change):
    record = arc("hold", "CLK", "A[0]", -.005, .007)
    record.update(change)
    with pytest.raises((ValueError, KeyError)):
        timing.normalize_arc(record, pins(), 0)


def test_missing_hold_is_rejected():
    config = {"probe_cell": "dsp", "parameters_raw": {"IS_CLK_INVERTED": "0"},
              "full_design_cells": ["original"]}
    with pytest.raises(ValueError, match="setup/hold"):
        timing.convert_configuration((config, [arc("setup", "CLK", "A[0]", .1, .2)], pins()))


@pytest.mark.parametrize("minimum,maximum", [("nan", .1), (0, "inf"), (.2, .1)])
def test_nonfinite_or_reversed_bounds_are_rejected(minimum, maximum):
    with pytest.raises(ValueError):
        timing.normalize_arc(arc("combinational", "A[0]", "P[0]", minimum, maximum), pins(), 0)


@pytest.mark.parametrize("value", ["4'001x", "4'001", '"unterminated', "1.2"])
def test_unresolved_parameters_are_rejected(value):
    with pytest.raises(ValueError):
        timing.parameter(value)


def test_full_width_mask_is_not_truncated():
    assert timing.parameter("48'" + "1" * 48) == {"kind": "integer", "value": (1 << 48) - 1}


def test_independent_raw_validation_detects_corrupted_bounds(tmp_path):
    raw = tmp_path / "raw.tsv"
    props = {"TYPE": "hold", "FROM_PIN": "dsp/CLK", "TO_PIN": "dsp/A[0]",
             "IS_DISABLED": "0", "IS_USER_DISABLED": "0"}
    props.update(dict(zip(timing.BOUND_FIELDS, ["-0.005", "0.007"] * 4)))
    raw.write_text("cell\tarc\tproperty\tvalue\n" + "".join(
        f"dsp\tarc0\t{key}\t{value}\n" for key, value in props.items()))
    table = {"probe_cell": "dsp", "source_arc_count": 1, "disabled_arc_count": 0,
             "arcs": [["hold", "CLK", "A0", -5, 7, -5, 7, *([-5, 7] * 4), 1]]}
    assert timing.validate_raw(raw, [table], pins())["bound_mismatches"] == 0
    table["arcs"][0][3] = 0
    with pytest.raises(ValueError, match="bounds differ"):
        timing.validate_raw(raw, [table], pins())
