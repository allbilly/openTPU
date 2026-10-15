#!/usr/bin/env python3
"""Verify completed full cut maps whose nested ABC commands were not echoed."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path

import fedora_openxc7_cut_mapping as mapping
from fedora_openxc7 import describe, digest
from fedora_openxc7_pcie_pipeline import FULL, unchanged
from fedora_check_jtag_image import synthesis_witness


def adopt(source, out):
    source = source.resolve()
    original_manifest = source / 'manifest.json'
    m = json.loads(original_manifest.read_text())
    assert m['status'] == 'FULL_CUT_MAPPING_FAILED'
    assert m['error'] == "AssertionError('ABC did not separately execute every selected command')"
    assert m['native_yosys_exit'] == 0
    assert (source / 'synth.exit').read_text().strip() == '0'
    unchanged(m['remap_inputs'])
    abc_file = source / 'mapping.abc'
    command = mapping.VARIANTS[m['mapping_variant']]
    assert abc_file.read_text() == 'strash;\ndretime;\n' + command + ';\n'
    log = (source / 'synth.log').read_text()
    assert 'ABC: + source ' + str(abc_file) + ' ' in log
    assert 'ABC: + write_blif ' in log and 'ABC: YOSYS_ABC_DONE' in log
    assert 'ABC RESULTS:' in log and '$lut cells:' in log
    errors = ['ABC: Error:', 'ABC: ** cmd error:', 'ABC: Unknown command',
              'ERROR:', 'ABC: Cannot open', 'ABC: Aborting']
    assert not any(error in log for error in errors), 'Native log contains an error'
    assert describe(source / 'synth.log') == m['artifacts']['synth.log']
    assert describe(source / 'synth.exit') == m['artifacts']['synth.exit']
    baseline_path = Path(m['baseline_manifest']).parent / 'synth.json'
    baseline = mapping.load_top(baseline_path)
    candidate = mapping.load_top(source / 'synth.json')
    ports = lambda t: {n: (v['direction'], len(v['bits'])) for n, v in t['ports'].items()}
    assert ports(baseline) == ports(candidate)
    a, b = mapping.hard(baseline), mapping.hard(candidate)
    assert all(a[n] == b[n] for n in set(a) & set(b))
    ca, cb = mapping.clock_binding(baseline), mapping.clock_binding(candidate)
    assert {k: v for k, v in ca.items() if k != 'cell'} == {k: v for k, v in cb.items() if k != 'cell'}
    if ca['cell'] != cb['cell']:
        assert set(a) - set(b) == {ca['cell']} and set(b) - set(a) == {cb['cell']}
    else:
        assert a == b
    counts = Counter(c['type'] for c in candidate['cells'].values())
    summary = dict(
        status='FULL_CUT_MAPPING_SCOPE_CLOCK_AND_NATIVE_SOURCE_EXECUTION_VERIFIED_FIT_PENDING',
        configuration=FULL, variant=m['mapping_variant'],
        native_yosys_exit=0, wrapper_exit=1,
        original_failure=describe(original_manifest), literal_script=describe(abc_file),
        nested_commands_individually_echoed=False,
        script_source_invocation='PRESENT', abc_completion_marker='PRESENT',
        board_ports_identical=True, hard_identity_bijection={cb['cell']: ca['cell']},
        clock_sink_count=len(cb['output_sinks']), baseline_clock_binding=ca,
        candidate_clock_binding=cb, counts=dict(counts),
        raw_luts=sum(counts['LUT' + str(i)] for i in range(1, 7)),
        dimensions_changed=False, numerical_timing='NOT_QUALIFIED', physical_hardware='NOT_RUN',
    )
    out.mkdir(parents=True, exist_ok=False)
    os.link(source / 'synth.json', out / 'synth.json')
    os.link(source / 'otpu_litedram_mem.init', out / 'otpu_litedram_mem.init')
    mapping.write(out / 'adoption.json', summary)
    evidence = [describe(original_manifest), describe(__file__), describe(mapping.__file__),
                describe(source / 'synth.json'), describe(source / 'synth.log'),
                describe(source / 'synth.exit'), describe(source / 'synth.command.json'),
                describe(abc_file), describe(source / 'synth.ys')]
    m['remap_inputs'].update({i['path']: i['sha256'] for i in evidence})
    m['artifacts']['synth.json'] = describe(out / 'synth.json')
    m['artifacts']['adoption.json'] = describe(out / 'adoption.json')
    m.update(status='SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN', stage='verified-full-cut-adoption',
             adoption_driver=describe(__file__), adoption_evidence=evidence,
             original_failed_manifest=describe(original_manifest), finished_utc=mapping.now())
    m.pop('error')
    mapping.write(out / 'manifest.json', m)
    witness = dict(configuration=FULL, synthesis_directory=str(out),
                   adopted_synthesis_manifest=describe(out / 'manifest.json'),
                   mapped_checkpoint=m['artifacts']['synth.json'])
    actual_counts = synthesis_witness(witness)
    assert dict(actual_counts) == dict(counts)
    unchanged(m['remap_inputs'])
    result = dict(status='FULL_CUT_MAPPING_ADOPTION_PASS_IMPLEMENTATION_NOT_RUN',
                  finished_utc=mapping.now(), manifest=describe(out / 'manifest.json'),
                  adoption=describe(out / 'adoption.json'), counts=dict(counts),
                  raw_luts=summary['raw_luts'], mapped_checkpoint=witness['mapped_checkpoint'],
                  original_native_exit=0, original_wrapper_exit=1,
                  numerical_timing='NOT_QUALIFIED', physical_hardware='NOT_RUN')
    mapping.write(out / 'adoption-result.json', result)
    print(result['status'], 'raw_luts', result['raw_luts'], 'MUXF8', counts['MUXF8'], flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    adopt(args.source, args.out.resolve())
