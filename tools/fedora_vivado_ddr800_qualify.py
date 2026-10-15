#!/usr/bin/env python3
"""Recheck the completed full Vivado DDR800 image and its host PHY tables."""
from pathlib import Path
import csv
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
IMAGE = ROOT/'build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z'
MIG = ROOT/'build/fedora-vivado/mig-jtag-controller-20261010T235833Z'
CORE = ROOT/'build/fedora-openxc7/ddr800-prepare-20261006T185112Z/core'
PROFILE = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2,
               CORE_KHZ=100000, DDR_MTS=800)


def describe(path):
    path = Path(path).resolve()
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            digest.update(block)
    return dict(path=str(path), bytes=path.stat().st_size, sha256=digest.hexdigest())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def qualify():
    from fedora_prepare_litedram import profile
    d = json.loads((IMAGE/'manifest.json').read_text())
    require(d['status'] == 'FULL_MAPPED_REFERENCE_BITSTREAM_TIMING_DRC_PINS_PACKET_PASS_HARDWARE_PENDING'
            and d['profile'] == PROFILE and d['part'] == 'xc7k480tffg1156-2'
            and d['native_exit'] == 0, 'Completed full Vivado reference required')
    pins = []
    for item in list(d['outputs'].values())+[d[k] for k in
                ('review', 'package_constraints', 'configuration_constraints')]:
        require(describe(item['path']) == item, 'Reference input/output changed: '+item['path'])
        pins.append(item)
    timing = d['final_timing']
    require(all(timing[k] == 0 for k in ('setup_failing_endpoints',
            'hold_failing_endpoints', 'pulse_failing_endpoints')), 'Timing gate failed')
    packet = json.loads((IMAGE/'packet-check.json').read_text())
    require(packet['status'] == 'PASS' and packet['sha256'] ==
            d['outputs']['full-mapped-reference.bit']['sha256'], 'Image packet gate failed')
    selected = profile(CORE)
    require(selected['parameters'] == dict(CORE_KHZ=100000, DDR_MTS=800),
            'Wrong matching PHY profile')
    pins.append(describe(selected['manifest']))
    adopted = json.loads((ROOT/'build/fedora-openxc7/jtag-ddr800-area-cut-adopted-20261011T195400Z/manifest.json').read_text())
    require(Path(adopted['litedram']['data']) == CORE and adopted['parameters'] == PROFILE,
            'Mapped design and selected host core differ')
    native = {}
    for row in csv.DictReader((IMAGE/'pins.tsv').open(), delimiter='\t'):
        native.setdefault(row['port'], {})[row['property']] = row['value']
    require(len(native) == 243 and all({'PACKAGE_PIN', 'IOSTANDARD'} <= set(v)
            for v in native.values()), 'Incomplete physical pin witness')
    # Expand the original reference's scalar, grouped and wildcard port settings.
    lines = []
    for path in (MIG/'constraints/board-jtag.xdc',
                 MIG/'ip/otpu_mig_ddr3/otpu_mig_ddr3/user_design/constraints/otpu_mig_ddr3.xdc'):
        pins.append(describe(path))
        lines.extend(re.findall(
            r'set_property\s+(PACKAGE_PIN|IOSTANDARD)\s+(\S+)\s+\[get_ports\s+(?:\{([^}]+)\}|([^\s\]]+))\]',
            path.read_text()))
    original = {}
    for prop, value, grouped, scalar in lines:
        if prop == 'PACKAGE_PIN':
            for name in (grouped or scalar).split():
                original.setdefault(name, {})[prop] = value
    for prop, value, grouped, scalar in lines:
        if prop == 'IOSTANDARD':
            for pattern in (grouped or scalar).split():
                expression = re.escape(pattern).replace(r'\*', '.*')
                for name in original:
                    if re.fullmatch(expression, name):
                        original[name][prop] = value
    by_pin = {v['PACKAGE_PIN']: (name, v['IOSTANDARD']) for name, v in original.items()
              if 'IOSTANDARD' in v}
    comparison = []
    for name, v in native.items():
        pin, standard = v['PACKAGE_PIN'], v['IOSTANDARD']
        require(pin in by_pin, 'Pin absent from the physically exercised reference: '+pin)
        previous, old_standard = by_pin[pin]
        allowed = (pin in ('AD31', 'F18') and old_standard == 'LVCMOS15'
                   and standard == 'SSTL15' and name.endswith('reset_n'))
        require(standard == old_standard or allowed, 'Unexpected electrical standard: '+pin)
        comparison.append(dict(pin=pin, native_port=name, reference_port=previous,
                               native_standard=standard, reference_standard=old_standard))
    config = Path(d['configuration_constraints']['path']).read_text()
    require(dict(re.findall(r'set_property (CFGBVS|CONFIG_VOLTAGE) (\S+) \[current_design\]',
                            config)) == dict(CFGBVS='GND', CONFIG_VOLTAGE='1.8'),
            'Configuration voltage settings differ')
    return dict(status='FULL_VIVADO_DDR800_IMAGE_TABLES_AND_REFERENCE_PIN_COMPARISON_PASS_HARDWARE_PENDING',
                profile=PROFILE, bitstream=d['outputs']['full-mapped-reference.bit'],
                calibration_core=str(CORE), pins=pins, pin_comparison=comparison,
                reset_standard_changes='Two existing 1.5 V DDR reset pins: LVCMOS15 to SSTL15',
                electrical_measurements='No new measurements; same reference pins and nominal voltages',
                hardware_accessed=False, flash_written=False)

