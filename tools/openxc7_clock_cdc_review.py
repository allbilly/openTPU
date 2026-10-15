#!/usr/bin/env python3
"""Review traced unknown crossings and the actual DDR800 phase-control contract."""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
from fractions import Fraction
import importlib.util
import json
from pathlib import Path
import re

from fedora_openxc7 import describe


def review(root: Path, inventory: Path, paths: Path, out: Path):
    if out.exists():
        raise ValueError('Review output already exists')
    base = root / 'build/fedora-openxc7'
    inv = json.loads(inventory.read_text())
    packed_gate = base / 'full-packed-dsp-inventory-20261011T223120Z/manifest.json'
    gate = json.loads(packed_gate.read_text())
    packed_inventory = packed_gate.parent / 'analysis-effective/inventory.json'
    packed_provenance = json.loads(packed_inventory.read_text())
    packed_path = Path(inv['packed']['path'])
    if not packed_path.is_absolute():
        packed_path = root / packed_path
    if (gate['native_exit'] != 0 or str(packed_path.resolve()) != gate['output']
            or describe(packed_gate) != packed_provenance['pack_manifest']
            or describe(packed_path) != packed_provenance['packed_netlist']):
        raise ValueError('Original packed input changed')
    path_gate = json.loads((paths.parent / 'manifest.json').read_text())
    if path_gate['status'] != 'FULL_UNPLACED_UNKNOWN_PATH_EXPORT_PASS_CDC_REVIEW_PENDING' or describe(paths) != path_gate['results']['full-analysis']['paths']:
        raise ValueError('Actual full path evidence changed')
    nets, ffs = inv['packed']['nets'], inv['selected_ffs']
    bygroup = {group: (name, cell) for name, cell in ffs.items() for group in cell['groups']}
    chains = {}
    for sync, toggle, clock in [('rq_sync', 'req_toggle', 'core_clk'), ('rs_sync', 'rsp_toggle', 'tck')]:
        previous = bygroup['u_mailbox.' + toggle][1]
        rows = []
        for i in range(3):
            net = 'u_mailbox.' + sync + f'[{i}]'
            name, cell = bygroup[net]
            if (nets[net]['attributes']['ASYNC_REG'] != 'TRUE' or cell['connections']['D'] != previous['connections']['Q']
                    or cell['connections']['CK'] != nets[clock]['bits'] or cell['parameters'].get('IS_C_INVERTED', '0').strip('0')):
                raise ValueError('Synchronizer chain or annotation mismatch')
            rows.append({'stage': i, 'cell': name, 'D': cell['connections']['D'], 'Q': cell['connections']['Q'],
                         'clock': clock, 'net_ASYNC_REG': 'TRUE', 'cell_ASYNC_REG': cell['attributes'].get('ASYNC_REG')})
            previous = cell
        chains[sync] = rows
    traced = {}
    for path in json.loads(paths.read_text())['paths']:
        launch, capture = path['launch'], path['capture']
        if (launch, capture) not in [('tck', 'core_clk'), ('core_clk', 'tck'),
                                     ('core_clk', 'u_ld.sysc0_clk'), ('core_clk', 'u_ld.sysc1_clk')]:
            continue
        source = next(s['from'] for s in path['segments'] if s['type'] == 'clk-to-q')
        sink = next(s['to'] for s in reversed(path['segments']) if s['type'] == 'setup')
        if capture in ('tck', 'core_clk'):
            chain = chains['rq_sync' if capture == 'core_clk' else 'rs_sync']
            if sink['cell'] != chain[0]['cell'] or sink['port'] != 'D':
                raise ValueError('Unknown JTAG path does not enter the first synchronizer')
        else:
            if (path['launch_edge'] != 'falling' or source['parameters']['IS_C_INVERTED'] != '1'
                    or source['connections']['CK'] != 'core_clk' or sink['type'] != 'OSERDESE2_OSERDESE2'
                    or sink['connections']['CLKDIV'] != capture or sink['connections'][sink['port']] != source['connections']['Q']):
                raise ValueError('Unknown DDR path is not a direct falling-edge command-register crossing')
        traced[capture + '<-' + launch] = {'source': source['cell'], 'sink': sink['cell'], 'sink_port': sink['port']}
    if len(traced) != 4:
        raise ValueError('Missing full unknown path')
    config = base / 'ddr800-prepare-20261006T185112Z/core/sdram_init.py'
    tree = ast.parse(config.read_text())
    phy = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)
               and any(isinstance(target, ast.Name) and target.id == 'phy' for target in node.targets))
    if phy['sys_hz'] != 100000000 or phy['vco_hz'] != 800000000 or phy['phy'] != 'wl':
        raise ValueError('Expected complete DDR800 WL profile')
    period = round(56 * phy['vco_hz'] / (4 * phy['sys_hz']))
    header = config.parent / 'selfcal_fw/selfcal_cfg.h'
    if period != 112 or not re.search(r'^#define WRAP 112$', header.read_text(), re.M):
        raise ValueError('Generated firmware phase range differs')
    host = root / 'opentpu/host/ddrcal.py'
    spec = importlib.util.spec_from_file_location('phase_review_ddrcal', host)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class CSR:
        def __init__(self, position):
            self.position, self.writes = position, 0

        def r(self, name):
            if name == 'phase_dqs_busy':
                return 0
            if name != 'phase_dqs_steps':
                raise ValueError('Unexpected mock CSR read')
            return self.position & 0xffffffff

        def w(self, name, value):
            if name != 'phase_dqs_shift' or value not in (0, 1):
                raise ValueError('Unexpected mock CSR write')
            self.position += 1 if value else -1
            self.writes += 1
            if not -56 <= self.position < 56:
                raise ValueError('Actual host move leaves its phase contract')

    checks, writes = 0, 0
    for start in range(-56, 56):
        for target in range(-112, 112):
            csr = CSR(start)
            controller = module.dqs_phase(csr, phy)
            if controller.wrap != 112:
                raise ValueError('Host factory does not wrap this PHY')
            controller.move(target)
            if csr.position != (target + 56) % 112 - 56:
                raise ValueError('Actual host target normalization differs')
            checks += 1
            writes += csr.writes
    step = Fraction(10**12, int(phy['vco_hz']) * 56)
    result = {'status': 'FOUR_UNKNOWN_PATHS_IDENTIFIED_MAILBOX_CHAIN_AND_HOST_PHASE_BOUNDS_REVIEWED',
              'created_utc': datetime.now(timezone.utc).isoformat(),
              'scope': 'UNPLACED_TOPOLOGY_AND_SOFTWARE_PHASE_CONTRACT_NOT_ROUTED_CDC_OR_HARDWARE_PROOF',
              'inputs': {'helper': describe(__file__), 'mailbox_inventory': describe(inventory), 'packed_gate': describe(packed_gate),
                         'packed_inventory': describe(packed_inventory),
                         'full_path_check': describe(paths.parent / 'manifest.json'), 'phy_settings': describe(config),
                         'firmware_header': describe(header), 'host_phase_source': describe(host)},
              'traced_unknown_paths': traced, 'mailbox_chains': chains,
              'mailbox_result': 'ALL_SIX_FFS_PRESENT_ASYNC_REG_RETAINED_ON_Q_NETS_NOT_CELL_ATTRIBUTES',
              'dynamic_phase': {'period_steps': period, 'allowed_steps': [-56, 55], 'step_ps': str(step),
                                'min_phase_ps': str(-56 * step), 'max_phase_ps': str(55 * step),
                                'host_move_checks': checks, 'host_mock_shift_writes': writes,
                                'nominal_setup_budget_ps': str(Fraction(5000) - 56 * step),
                                'nominal_hold_edge_ps': str(Fraction(-5000) + 55 * step),
                                'conservative_symmetric_bound_ps': 1250,
                                'bound_scope': 'HOST_AND_FIRMWARE_WRAP_CONTRACT_RAW_CSR_HARDWARE_DOES_NOT_ENFORCE_BOUND',
                                'engine_bound_imported': False},
              'vendor_phase_definition': 'https://docs.amd.com/v/u/en-US/ug472_7Series_Clocking',
              'hardware_accessed': False, 'constraints_changed': False, 'full_routed_timing': 'NOT_QUALIFIED'}
    out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'artifact': str(out), 'status': result['status'], 'dynamic_phase': result['dynamic_phase']}), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('root', 'inventory', 'paths', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    review(args.root.resolve(), args.inventory.resolve(), args.paths.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
