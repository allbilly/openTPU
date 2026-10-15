#!/usr/bin/env python3
"""Check full JTAG image provenance, USER2 and every configuration frame."""
from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path

from fedora_openxc7 import PART, configuration, describe
from fedora_openxc7_pcie_pipeline import FULL, recorded, require, select_backend, unchanged
from fedora_check_pcie_image import STRUCTURE_CHECKER, compare_frames

TOP = 'otpu_fpga_top_openxc7_jtag'


def select_jtag_backend(pipeline):
    """Use exact-binary correction receipts for the adopted JTAG route.

    Older pipeline formats retain their original pinned-backend policy.
    These gates verify functionality/encoding, never numerical timing.
    """
    info = json.loads(Path(pipeline).read_text())
    if info.get('backend_validation') != 'EXACT_CORRECTION_RECEIPTS_V1':
        return select_backend(pipeline)
    require(info.get('configuration') == FULL, 'Wrong full JTAG profile')
    backend = info['corrected_backend']
    inventory = {}

    def pin(item):
        recorded(item)
        inventory[item['path']] = item['sha256']

    pin(backend['manifest'])
    pin(backend['binary'])
    build = json.loads(Path(backend['manifest']['path']).read_text())
    require(build.get('status') == 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED'
            and build.get('binary') == backend['binary'] and build.get('source') == backend['source'],
            'Backend build identity or terminal status differs')
    require({'CARRY_UNUSED_PADDING', 'DSP_CONSECUTIVE_SITES', 'DSP_LOC_TO_BEL',
             'FF_CLOCK_EDGE', 'CARRY_SECOND_SLICE', 'FINITE_64BIT_TIMEOUT'}
            <= set(build.get('retained_corrections', [])), 'Backend omitted required corrections')
    pin(build['source_inventory'])
    source = Path(build['source'])
    for relative, expected in json.loads(Path(build['source_inventory']['path']).read_text()).items():
        path = source / relative
        require(path.is_file() and describe(path)['sha256'] == expected,
                'Backend source changed: '+relative)
        inventory[str(path)] = expected
    contract = build.get('arithmetic_contract') or {}
    require(contract.get('cases') == 9, 'Timeout arithmetic contract is missing')
    pin(contract['source'])
    pin(contract['log'])
    require('TIMEOUT_CONTRACT_PASS cases=9' in Path(contract['log']['path']).read_text(),
            'Timeout arithmetic contract did not pass')
    pin(info['chipdb'])
    pin(info['correction_strict_receipt'])
    strict = json.loads(Path(info['correction_strict_receipt']['path']).read_text())
    require(strict.get('status') == 'STRICT_FRAMES_PASS' and strict.get('backend_binary') == backend['binary']
            and strict.get('backend_manifest') == backend['manifest'],
            'Strict probe assembly tested a different backend or did not pass')
    expected = dict(carry_probe='CARRY_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS',
                    upper_carry_probe='CARRY_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS',
                    cascade_probe='DSP_CASCADE_16_SITE_PLACEMENT_AND_ROUTING_PASS_STRICT_FRAMES_NOT_TESTED',
                    ff_edge_probe='ROUTED_FF_EDGE_AND_FULL_HALF_PERIOD_SEMANTICS_PASS_NUMERICAL_MODEL_NOT_QUALIFIED',
                    mux_probe='EXTRACTED_MUX_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS')
    jobs = {job['gate']: job for job in strict['jobs']}
    require(set(jobs) == set(expected) and len(jobs) == len(strict['jobs']),
            'Missing or duplicated strict correction gates')
    gates = {}
    for name, status in expected.items():
        gate, job = info[name], jobs[name]
        require(gate['status'] == 'PROBE_ROUTE_AND_STRICT_FRAMES_PASS_NUMERICAL_TIMING_NOT_QUALIFIED',
                'Correction gate is incomplete: '+name)
        require(gate['manifest'] == job['manifest'] and gate['strict_frames'] == job['frames']
                and job['exit_code'] == 0, 'Probe and strict frames differ: '+name)
        for item in (gate['manifest'], gate['strict_frames'], job['fasm'], job['command'], job['exit']):
            pin(item)
        probe = json.loads(Path(gate['manifest']['path']).read_text())
        actual_binary = probe.get('corrected_binary') if name == 'ff_edge_probe' else probe.get('binary')
        require(probe.get('status') == status and actual_binary == backend['binary']
                and probe.get('chipdb') == info['chipdb'], 'Probe tested a different binary/database: '+name)
        directory = Path(gate['manifest']['path']).parent
        prefix = 'corrected' if name == 'ff_edge_probe' else 'route'
        require((directory/(prefix+'.exit')).read_text().strip() == '0', 'Probe route did not exit successfully: '+name)
        command = json.loads((directory/(prefix+'.command.json')).read_text())
        require(command[0] == backend['binary']['path'], 'Probe route executable differs: '+name)
        strict_command = json.loads(Path(job['command']['path']).read_text())
        require(strict_command[-2:] == [job['fasm']['path'], job['frames']['path']]
                and Path(job['exit']['path']).read_text().strip() == '0', 'Strict assembler input/output differs: '+name)
        for item in probe['artifacts'].values():
            pin(item)
        if name in ('carry_probe', 'upper_carry_probe'):
            require(probe.get('patterns') == 256 and probe.get('compared_outputs') == 4,
                    'Carry equivalence coverage differs: '+name)
        if name == 'upper_carry_probe':
            require(probe.get('second_slice_carries') == 8 and probe.get('dedicated_carry_links') == 4
                    and probe.get('in_process_legality') == 'PASS', 'Upper-slice carry geometry/routing is unverified')
            pin(probe['dedicated_carry_routing'])
        if name == 'cascade_probe':
            require(probe.get('placed_dsps') == 64 and len(probe.get('roots', [])) == 4
                    and probe.get('routed_cascade_bits') == 2880, 'Four complete 16-DSP cascades were not checked')
        if name == 'mux_probe':
            require(probe.get('source_netlist') == info['mapped_checkpoint'],
                    'MUX probe does not cover the selected full netlist')
            if probe.get('root_primitive') == 'MUXF7':
                # A full map with no F8 cells needs an actual F7 witness.
                # Verify absence in the selected JSON, rather than trusting counts in a receipt.
                mapped = json.loads(Path(info['mapped_checkpoint']['path']).read_text())['modules'][TOP]
                root = mapped['cells'].get(probe.get('root_cell'))
                require(root is not None and root['type'] == 'MUXF7'
                        and not any(c['type'] == 'MUXF8' for c in mapped['cells'].values()),
                        'F7 witness requires the tested root and zero F8 in the full checkpoint')
                require(probe.get('patterns') == 128 and probe.get('boundary_inputs') == 7
                        and probe.get('f8_absent_in_full_source') is True,
                        'F7 witness did not exhaust all seven-input patterns')
                require(any(c['original_type'] == 'MUXF7'
                            and c['bel'].endswith(('/F7AMUX', '/F7BMUX'))
                            for c in probe.get('mux_placement', {}).values()),
                        'F7 witness has no actual dedicated F7 placement')
            else:
                require(probe.get('patterns') == 256, 'F8 equivalence coverage differs')
        gates[name] = gate
    return backend, gates, inventory


def synthesis_witness(info):
    """Validate the actual complete mapped checkpoint, without claiming an image."""
    require(info.get('configuration') == FULL, 'Wrong full OpenTPU profile')
    synth = Path(info['synthesis_directory']).resolve()
    synthesis = json.loads((synth / 'manifest.json').read_text())
    require(synthesis.get('status') == 'SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN'
            and synthesis.get('action') == 'jtag-synth' and synthesis.get('part') == PART
            and synthesis.get('parameters') == FULL, 'Wrong terminal full JTAG synthesis')
    recorded(info['adopted_synthesis_manifest'])
    require(Path(info['adopted_synthesis_manifest']['path']).resolve() == synth / 'manifest.json',
            'Synthesis manifest differs from the selected full checkpoint')
    recorded(info['mapped_checkpoint'])
    require(info['mapped_checkpoint'] == synthesis['artifacts']['synth.json']
            and Path(info['mapped_checkpoint']['path']).resolve() == synth / 'synth.json',
            'Mapped checkpoint differs from the full synthesis')
    design = json.loads((synth / 'synth.json').read_text())
    require(TOP in design['modules'], 'Missing full standalone OpenTPU top')
    top = design['modules'][TOP]
    require(int(top.get('attributes', {}).get('blackbox', '0'), 2) == 0,
            'Full OpenTPU top is blackboxed')
    counts = Counter(cell['type'] for cell in top['cells'].values())
    require(not any(cell['type'].startswith(('otpu_', 'VexRiscv')) for cell in top['cells'].values()),
            'Unmapped accelerator or calibration CPU remains')
    for name, count in dict(BSCANE2=1, DSP48E1=717, ISERDESE2=144, OSERDESE2=214,
                            IDELAYE2=144, RAMB18E1=106, RAMB36E1=514).items():
        require(counts[name] == count, 'Full standalone hardware scope differs: ' + name)
    require(counts['XADC'] == counts['PCIE_2_1'] == counts['GTXE2_CHANNEL'] == 0,
            'Unexpected standalone image hardware')
    return counts


def check(pipeline):
    pipeline = Path(pipeline).resolve()
    directory = pipeline.parent
    info = json.loads(pipeline.read_text())
    require(info.get('status') == 'FULL_CONFIGURATION_ASSEMBLY_PASS_TIMING_QUALIFICATION_INCOMPLETE',
            'Full JTAG configuration assembly has not completed')
    require(info.get('configuration') == FULL, 'Wrong full OpenTPU profile')
    require(info.get('stage') in ('assembled', 'independently-checked', 'independent-bitstream-check'),
            'Full JTAG pipeline has not reached image verification')
    unchanged(info['planned_inputs'])
    backend, gates, _ = select_jtag_backend(pipeline)
    counts = synthesis_witness(info)
    route_path = directory / 'route/manifest.json'
    route = json.loads(route_path.read_text())
    require(route.get('status') == 'ROUTE_PASS_TIMING_QUALIFICATION_INCOMPLETE'
            and route.get('parameters') == FULL and route.get('part') == PART,
            'Full standalone route did not pass')
    require(route['tools']['nextpnr'] == backend['binary'], 'Routed backend differs')
    require(route['litedram']['manifest'] == str(Path(info['litedram_core']) / 'openxc7-profile.json'),
            'Routed DDR profile differs')
    for item in route['artifacts'].values():
        recorded(item)
    for name in ('design.bit', 'design.frames'):
        item = info['artifacts'][name]
        require(Path(item['path']).resolve() == directory / name, 'Wrong assembly artifact path')
        recorded(item)
    spec = importlib.util.spec_from_file_location('ypcb_jtag_bit_structure', STRUCTURE_CHECKER)
    structure = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(structure)
    user2 = structure.check(directory / 'design.bit', directory / 'route/design.fasm', 2, pipeline)
    frames = compare_frames(directory / 'design.bit', directory / 'design.frames',
                            configuration()['database'] / PART / 'part.json')
    unchanged(info['planned_inputs'])
    return dict(status='FULL_JTAG_IMAGE_PACKET_FRAME_AND_PROVENANCE_PASS_TIMING_NOT_QUALIFIED',
                pipeline=describe(pipeline), configuration=FULL, top=TOP, mapped_counts=dict(counts),
                backend=backend, correction_gates=gates, user2_check=user2, frame_comparison=frames,
                checker=describe(Path(__file__)), frame_checker=describe(Path(__file__).with_name('fedora_check_pcie_image.py')),
                structure_checker=describe(STRUCTURE_CHECKER), crc='NOT_CHECKED', timing='NOT_QUALIFIED',
                physical_hardware='NOT_RUN', programming='NOT_RUN', flash_written=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pipeline', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.exists(), 'Output report already exists')
    try:
        report = check(args.pipeline)
    except Exception as error:
        report = dict(status='FAIL', error=str(error), crc='NOT_CHECKED', timing='NOT_QUALIFIED',
                      physical_hardware='NOT_RUN', programming='NOT_RUN', flash_written=False)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2) + '\n')
    print(report['status'])
    print(args.out)
    return 0 if report['status'].startswith('FULL_JTAG_IMAGE_PACKET_FRAME_AND_PROVENANCE_PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
