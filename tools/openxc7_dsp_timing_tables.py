#!/usr/bin/env python3
"""Prepare exact-configuration xc7 DSP timing tables without editing a backend."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
import hashlib
import json
import os
from pathlib import Path
import re


KINDS = {"combinational": "comb", "Reg Clk to Q": "clkq",
         "setup": "setup", "hold": "hold"}
BOUND_FIELDS = tuple(f"DELAY_{corner}_{bound}_{edge}"
                     for edge in ("RISE", "FALL")
                     for corner in ("FAST", "SLOW")
                     for bound in ("MIN", "MAX"))
PART = "xc7k480tffg1156-2"


def digest(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def parameter(raw):
    if raw.startswith('"'):
        value = json.loads(raw)
        if not isinstance(value, str):
            raise ValueError("Invalid string parameter")
        return {"kind": "string", "value": value}
    match = re.fullmatch(r"(\d+)'([01]+)", raw)
    if match:
        width, bits = match.groups()
        if len(bits) != int(width):
            raise ValueError("Invalid binary parameter width")
        return {"kind": "integer", "value": int(bits, 2)}
    if re.fullmatch(r"-?\d+", raw):
        return {"kind": "integer", "value": int(raw)}
    raise ValueError(f"Unresolved parameter {raw!r}")


def full_configuration_coverage(configs):
    """Require the complete named configuration grouping from its source inventory."""
    source = Path(configs["source_inventory"])
    if digest(source) != configs["source_inventory_sha256"]:
        raise ValueError("Full source DSP inventory changed")
    inventory = json.loads(source.read_text())
    if inventory["dsp_count"] != 717:
        raise ValueError("Full source DSP count changed")
    if "packed_inventory" in configs:
        evidence = configs["packed_inventory"]
        packed_path = Path(evidence["path"])
        if digest(packed_path) != evidence["sha256"] or packed_path.stat().st_size != evidence["bytes"]:
            raise ValueError("Effective packed DSP inventory changed")
        packed = json.loads(packed_path.read_text())
        if packed["dsp_count"] != 717 or configs.get("mode_scope") != "ACTUAL_EFFECTIVE_PACKED_HARDWARE_PARAMETERS":
            raise ValueError("Effective packed DSP scope changed")
        expected = {json.dumps(c["parameters"], sort_keys=True): set(c["cells"])
                    for c in packed["effective_profiles"]}
    else:
        defaults = {n: parameter(raw) for n, raw in inventory["vendor_defaults_raw"].items()}
        expected = defaultdict(set)
        for cell in inventory["cells"]:
            params = {**defaults, **{n: parameter(raw) for n, raw in cell["parameters_raw"].items()}}
            expected[json.dumps(params, sort_keys=True)].add(cell["name"])
    actual = {}
    for config in configs["configurations"]:
        params = {n: parameter(raw) for n, raw in config["parameters_raw"].items()}
        key = json.dumps(params, sort_keys=True)
        if key in actual:
            raise ValueError("Duplicate full DSP parameter configuration")
        actual[key] = set(config["full_design_cells"])
    if actual != expected or configs["complete_configurations"] != len(expected):
        raise ValueError("DSP configurations do not cover the complete source grouping")
    return len(expected)


def pin_map(ports):
    pins, packed = {}, set()
    for port in ports:
        if port["direction"] not in ("input", "output") or port["width"] < 1:
            raise ValueError("Invalid DSP port declaration")
        for bit in range(port["width"]):
            name = port["name"] if port["width"] == 1 else f"{port['name']}[{bit}]"
            target = name.replace("[", "").replace("]", "")
            if name in pins or target in packed:
                raise ValueError("Ambiguous packed DSP pin")
            pins[name] = {"packed": target, "direction": port["direction"]}
            packed.add(target)
    return pins


def picoseconds(value, upper):
    value = Decimal(str(value)) * 1000
    if not value.is_finite():
        raise ValueError("Nonfinite timing delay")
    return int(value.to_integral_value(rounding=ROUND_CEILING if upper else ROUND_FLOOR))


def normalize_arc(arc, pins, clock_inverted):
    kind = KINDS.get(arc["type"])
    if kind is None:
        raise ValueError(f"Unsupported DSP arc type {arc['type']!r}")
    source, target = pins[arc["from"]], pins[arc["to"]]
    if source["direction"] != "input":
        raise ValueError("DSP arc does not start at an input")
    if target["direction"] != ("input" if kind in ("setup", "hold") else "output"):
        raise ValueError("DSP arc has an invalid endpoint direction")
    if kind == "comb":
        if arc["from"] == "CLK" or set(arc["transition"].split()) != {"ff", "rf", "rr", "fr"}:
            raise ValueError("Unsupported combinational clock or transition semantics")
    else:
        expected = {"fr", "ff"} if clock_inverted else {"rr", "rf"}
        if arc["from"] != "CLK" or set(arc["transition"].split()) != expected:
            raise ValueError("Unsupported DSP clock or transition semantics")
    for value in arc["delays_ns"].values():
        if not Decimal(str(value)).is_finite():
            raise ValueError("Nonfinite timing field")
    corners = tuple(picoseconds(arc["delays_ns"][field], i % 2 == 1)
                    for i, field in enumerate(BOUND_FIELDS))
    if any(corners[i] > corners[i + 1] for i in range(0, len(corners), 2)):
        raise ValueError("Reversed delay bounds")
    bounds = (min(corners[0], corners[2]), max(corners[1], corners[3]),
              min(corners[4], corners[6]), max(corners[5], corners[7]), *corners)
    return (kind, source["packed"], target["packed"]), bounds


def merge_bounds(previous, current):
    return tuple((max if i % 2 else min)(a, b)
                 for i, (a, b) in enumerate(zip(previous, current)))


def convert_configuration(task):
    config, arcs, pins = task
    params = {key: parameter(value) for key, value in config["parameters_raw"].items()}
    inverted = params["IS_CLK_INVERTED"]["value"]
    if inverted not in (0, 1):
        raise ValueError("Invalid DSP clock inversion")
    grouped, copies, types = {}, Counter(), Counter()
    disabled = 0
    for arc in arcs:
        key, bounds = normalize_arc(arc, pins, inverted)
        types[arc["type"]] += 1
        if not isinstance(arc["disabled"], bool):
            raise ValueError("Invalid disabled-arc value")
        if arc["disabled"]:
            disabled += 1
            continue
        grouped[key] = merge_bounds(grouped[key], bounds) if key in grouped else bounds
        copies[key] += 1
    seq_inputs = {key[2] for key in grouped if key[0] == "setup"}
    if seq_inputs != {key[2] for key in grouped if key[0] == "hold"}:
        raise ValueError("Incomplete setup/hold pair")
    seq_outputs = {key[2] for key in grouped if key[0] == "clkq"}
    comb_inputs = {key[1] for key in grouped if key[0] == "comb"}
    comb_outputs = {key[2] for key in grouped if key[0] == "comb"}
    return {
        "probe_cell": config["probe_cell"], "parameters": params,
        "parameters_raw": config["parameters_raw"],
        "full_design_cells": config["full_design_cells"],
        "clock_port": "CLK", "clock_edge": "falling" if inverted else "rising",
        "source_arc_count": len(arcs), "source_arc_types": dict(types),
        "disabled_arc_count": disabled,
        "registered_inputs": sorted(seq_inputs), "registered_outputs": sorted(seq_outputs),
        "hybrid_inputs": sorted(seq_inputs & comb_inputs),
        "hybrid_outputs": sorted(seq_outputs & comb_outputs),
        "arcs": [[*key, *grouped[key], copies[key]] for key in sorted(grouped)],
    }


def raw_arcs(path):
    """Read original vendor property rows, independently of the compact JSON."""
    current, properties = None, {}
    with path.open() as stream:
        if stream.readline().rstrip("\n") != "cell\tarc\tproperty\tvalue":
            raise ValueError("Unexpected raw timing TSV header")
        for line in stream:
            cell, identity, prop, value = line.rstrip("\n").split("\t", 3)
            key = (cell, identity)
            if current is not None and key != current:
                yield current[0], properties
                properties = {}
            if prop in properties:
                raise ValueError("Duplicate raw timing property")
            current, properties[prop] = key, value
        if current is not None:
            yield current[0], properties


def validate_raw(path, tables, pins):
    """Check every prepared bound directly against the raw vendor TSV."""
    actual = {t["probe_cell"]: {tuple(a[:3]): tuple(a[3:]) for a in t["arcs"]} for t in tables}
    expected, counts, excluded = defaultdict(dict), Counter(), Counter()
    for cell, props in raw_arcs(path):
        if cell not in actual:
            raise ValueError("Uncharacterized raw DSP cell")
        counts[cell] += 1
        if props["IS_DISABLED"] not in ("0", "1") or props["IS_USER_DISABLED"] not in ("0", "1"):
            raise ValueError("Unsupported raw disabled-arc semantics")
        if props["IS_DISABLED"] == "1" or props["IS_USER_DISABLED"] == "1":
            excluded[cell] += 1
            continue
        prefix = cell + "/"
        if not props["FROM_PIN"].startswith(prefix) or not props["TO_PIN"].startswith(prefix):
            raise ValueError("Raw DSP pin belongs to another cell")
        source, target = props["FROM_PIN"][len(prefix):], props["TO_PIN"][len(prefix):]
        key = (KINDS[props["TYPE"]], pins[source]["packed"], pins[target]["packed"])
        # Convert the original decimal strings rather than the compact floats.
        values = []
        for i, field in enumerate(BOUND_FIELDS):
            value = Decimal(props[field]) * Decimal(1000)
            if not value.is_finite():
                raise ValueError("Nonfinite raw timing delay")
            values.append(int(value.to_integral_value(rounding=ROUND_CEILING if i % 2 else ROUND_FLOOR)))
        if any(values[i] > values[i + 1] for i in range(0, len(values), 2)):
            raise ValueError("Reversed raw timing corner bounds")
        values = [min(values[0], values[2]), max(values[1], values[3]),
                  min(values[4], values[6]), max(values[5], values[7]), *values]
        if key in expected[cell]:
            previous = expected[cell][key]
            values = [(max if i % 2 else min)(previous[i], value) for i, value in enumerate(values)]
            copies = previous[12] + 1
        else:
            copies = 1
        expected[cell][key] = (*values, copies)
    for table in tables:
        cell = table["probe_cell"]
        if counts[cell] != table["source_arc_count"] or excluded[cell] != table["disabled_arc_count"]:
            raise ValueError(f"Raw arc count differs for {cell}")
        if actual[cell] != expected[cell]:
            raise ValueError(f"Raw vendor timing bounds differ for {cell}")
    return {"raw_arcs_checked": sum(counts.values()), "bound_mismatches": 0,
            "raw_tsv_sha256": digest(path)}


def prepare(source, out, workers):
    out.mkdir(parents=True, exist_ok=False)
    manifest = {"status": "RUNNING", "created_utc": datetime.now(timezone.utc).isoformat(),
                "source": str(source), "workers": workers, "part": PART,
                "backend_changed": False, "hardware_accessed": False,
                "numerical_timing": "NOT_QUALIFIED", "helper_sha256": digest(Path(__file__))}
    mp = out / "manifest.json"
    def save(**fields):
        manifest.update(fields)
        mp.write_text(json.dumps(manifest, indent=2) + "\n")
    try:
        save()
        vendor = json.loads((source / "manifest.json").read_text())
        if vendor["native_exit"] != 0 or vendor["part"] != PART:
            raise ValueError("Vendor characterization did not complete for the exact part")
        for name, expected in vendor["inputs"].items():
            if Path(name).name != name or digest(source / name) != expected:
                raise ValueError("Vendor characterization input changed")
        configs = json.loads((source / "configurations.json").read_text())
        semantics = json.loads((source / "semantic-summary-v2.json").read_text())
        compact = json.loads((source / "timing-arcs-compact.json").read_text())
        raw = source / "timing-arcs.tsv"
        if compact["part"] != PART or compact["units"] != "ns" or digest(raw) != compact["source_tsv_sha256"]:
            raise ValueError("Vendor timing provenance mismatch")
        if semantics["parameter_mismatches"] or semantics["nonfinite_or_non_numeric_delays"]:
            raise ValueError("Vendor parameter or numerical validation failed")
        count = full_configuration_coverage(configs)
        if vendor["complete_configurations"] != count or semantics["complete_configurations"] != count or configs["dsp_total"] != 717:
            raise ValueError("Full DSP configuration scope changed")
        rows = configs["configurations"]
        names = [c["probe_cell"] for c in rows]
        cells = [name for c in rows for name in c["full_design_cells"]]
        if len(names) != count or len(set(names)) != count or len(cells) != 717 or len(set(cells)) != 717:
            raise ValueError("Incomplete or duplicate full-design DSP coverage")
        pins = pin_map(configs["ports"])
        groups = {name: [] for name in names}
        for arc in compact["arcs"]:
            groups[arc["cell"]].append(arc)
        tasks = [(c, groups[c["probe_cell"]], pins) for c in rows]
        with ProcessPoolExecutor(max_workers=workers) as pool:
            tables = list(pool.map(convert_configuration, tasks))
        for table in tables:
            reference = semantics["configurations"][table["probe_cell"]]
            if table["source_arc_types"] != reference["arc_types"]:
                raise ValueError("Arc types differ from the validated vendor summary")
        validation = validate_raw(raw, tables, pins)
        if validation["raw_arcs_checked"] != semantics["total_arcs"]:
            raise ValueError("Complete raw arc coverage failed")
        data = {"part": PART, "units": "ps", "arc_fields": ["kind", "from", "to", "min_rise", "max_rise",
                "min_fall", "max_fall", *[f.lower().removeprefix("delay_") for f in BOUND_FIELDS],
                "source_copies"], "pin_map": pins, "configurations": tables,
                "numerical_timing": "NOT_QUALIFIED", "raw_validation": validation}
        if "packed_inventory" in configs:
            data.update(mode_scope=configs["mode_scope"], packed_inventory=configs["packed_inventory"])
        result = out / "dsp-timing-tables.json"
        result.write_text(json.dumps(data, separators=(",", ":")) + "\n")
        save(status="FULL_DSP_TABLES_PREPARED_RAW_BOUNDS_VERIFIED_BACKEND_NOT_QUALIFIED",
             completed_utc=datetime.now(timezone.utc).isoformat(),
             complete_configurations=len(tables), full_design_instances=len(cells),
             raw_arc_count=validation["raw_arcs_checked"],
             table_arc_count=sum(len(t["arcs"]) for t in tables), raw_validation=validation,
             inputs={n: digest(source / n) for n in ("manifest.json", "configurations.json",
                     "semantic-summary-v2.json", "timing-arcs-compact.json", "timing-arcs.tsv")},
             output={"path": str(result), "bytes": result.stat().st_size, "sha256": digest(result)})
        return manifest
    except Exception as exc:
        save(status="FAIL", error=str(exc))
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=len(os.sched_getaffinity(0)))
    args = parser.parse_args()
    if not 1 <= args.workers <= len(os.sched_getaffinity(0)):
        parser.error("Worker count must fit the available CPU affinity")
    result = prepare(args.source.resolve(), args.out.resolve(), args.workers)
    print(json.dumps({k: result[k] for k in ("status", "workers", "complete_configurations",
                                           "full_design_instances", "raw_arc_count", "table_arc_count")}))


if __name__ == "__main__":
    main()
