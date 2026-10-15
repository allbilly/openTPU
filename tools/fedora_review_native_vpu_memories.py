#!/usr/bin/env python3
"""Audit named VPU memories and shared LUT packing in a native funcsim netlist.

This is structural evidence only. It does not clear synthesis warnings or prove
complete functional equivalence, routed behavior, or physical FPGA operation.
"""
import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def memories(path):
    module, collecting, result = "", None, []
    start = re.compile(r"^\s*(RAM[A-Z0-9]+)\s+#\(")
    with path.open() as stream:
        for line in stream:
            if line.startswith("module "):
                module = line.split()[1]
            if module not in ("otpu_vpu", "otpu_se_tail"):
                continue
            if collecting is None:
                match = start.match(line)
                if match:
                    collecting = (match[1], [line])
            else:
                collecting[1].append(line)
                if line.rstrip().endswith(");"):
                    body = "".join(collecting[1])
                    name = re.search(r"\)\s+\\?([^\s]+)\s*\(", body)
                    if name is None:
                        raise ValueError("Cannot identify memory instance")
                    result.append(dict(module=module, type=collecting[0],
                                       name=name[1], body=body))
                    collecting = None
    if collecting is not None or not result:
        raise ValueError("Incomplete or empty native memory inventory")
    return result


def port(cell, name):
    match = re.search(r"\." + re.escape(name) + r"\((.*?)\)(?:,|;|\))",
                      cell["body"], re.S)
    if match is None:
        raise ValueError(f"Missing {name} in {cell['name']}")
    return match[1].strip()


def bit_slice(expression):
    match = re.fullmatch(r"\\([^\s]+)\s+\[(\d+):(\d+)\]", expression)
    if match is None:
        raise ValueError(f"Unsupported data expression: {expression}")
    return match[1], int(match[2]), int(match[3])


def audit(cells):
    arrays = []
    families = [("otpu_vpu", "g_cbuf", ("cbuf", "dbuf")),
                ("otpu_se_tail", "g_buf", ("kb", "kb2", "qb", "vb", "gb")),
                ("otpu_vpu", "g_rbuf", ("rb",))]
    for module, prefix, names in families:
        for name in names:
            for lane in range(8):
                stem = f"{prefix}[{lane}].{name}_reg"
                selected = [c for c in cells if c["module"] == module
                            and c["name"].startswith(stem)]
                if not selected:
                    raise ValueError(f"No retained source-named memory: {stem}")
                covered, shared = set(), []
                for cell in selected:
                    match = re.fullmatch(re.escape(stem) + r"_0_31_(\d+)_(\d+)", cell["name"])
                    if match:
                        covered.update(range(int(match[1]), int(match[2]) + 1))
                    elif cell["name"] == stem and cell["type"] == "RAMB18E1":
                        covered.update(range(32))
                    else:
                        raise ValueError(f"Unsupported named memory fragment: {cell['name']}")
                named_coverage = sorted(covered)
                if covered != set(range(32)):
                    # Vivado packs the upper two bits of three same-control lane
                    # memories into one RAM32M. Follow data and control ports.
                    low = next(c for c in selected if c["name"] == stem + "_0_31_0_5")
                    read_net, _, _ = bit_slice(port(low, "DOA"))
                    write_net, _, _ = bit_slice(port(low, "DIA"))
                    for cell in cells:
                        if cell["module"] != module or cell["type"] != "RAM32M":
                            continue
                        for letter in "ABC":
                            output = port(cell, "DO" + letter)
                            try:
                                net, high, low_bit = bit_slice(output)
                            except ValueError:
                                continue
                            if net != read_net or not set(range(low_bit, high + 1)) - covered:
                                continue
                            input_net, input_high, input_low = bit_slice(port(cell, "DI" + letter))
                            checks = [input_net == write_net,
                                      (input_high, input_low) == (high, low_bit),
                                      port(cell, "ADDR" + letter) == port(low, "ADDRA")]
                            checks += [port(cell, field) == port(low, field)
                                       for field in ("ADDRD", "WCLK", "WE")]
                            if not all(checks):
                                raise ValueError(f"Shared memory wiring mismatch: {stem}")
                            covered.update(range(low_bit, high + 1))
                            shared.append(dict(primitive=cell["name"], read_port="DO" + letter,
                                               write_port="DI" + letter, output=output,
                                               input=port(cell, "DI" + letter),
                                               bits=[low_bit, high], controls_match=True))
                if covered != set(range(32)):
                    raise ValueError(f"Unresolved data bit storage: {stem}: {sorted(covered)}")
                arrays.append(dict(module=module, array=stem, depth_words=32, width_bits=32,
                                   original_name_bit_coverage=named_coverage,
                                   final_bit_coverage=sorted(covered), shared_memory_ports=shared,
                                   named_primitives=[{k: c[k] for k in ("name", "type")} for c in selected]))
    assert len(arrays) == 64
    delay = [c for c in cells if c["module"] == "otpu_se_tail" and c["name"].startswith("ub_reg_")]
    if len(delay) != 4 or any(c["type"] != "RAMB36E1" for c in delay):
        raise ValueError("Missing native stream delay buffer BRAMs")
    return arrays, [{k: c[k] for k in ("name", "type")} for c in delay]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--netlist", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    cells = memories(args.netlist)
    arrays, delay = audit(cells)
    report = dict(status="NAMED_VPU_ARRAY_STORAGE_AND_SHARED_PACKING_AUDIT_PASS_FULL_FUNCTION_UNPROVEN",
                  captured_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  netlist=str(args.netlist.resolve()), netlist_sha256=digest(args.netlist),
                  checker_sha256=digest(Path(__file__)), named_array_count=len(arrays),
                  arrays_requiring_shared_packing=len([a for a in arrays if a["shared_memory_ports"]]),
                  arrays=arrays, stream_delay_buffer=delay,
                  synthesis_removal_warnings_cleared=False, physical_test="NOT_RUN",
                  limitations=["Structural storage/wiring evidence only",
                               "Eight removed intermediate aliases remain unmapped",
                               "Complete VPU arithmetic and control behavior remains unproven",
                               "No gate-level equivalence or physical compute result"])
    args.out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "named_array_count",
                                            "arrays_requiring_shared_packing")}, indent=2))


if __name__ == "__main__":
    main()
