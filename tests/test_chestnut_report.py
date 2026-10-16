"""Report workloads must match the fixed CPU/FPGA comparison in the docs."""
import json
import sys

import pytest

from tools import chestnut_report as report


@pytest.fixture
def fpga():
    return dict(model='lfm2', status='PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK',
                physical=True, benchmark_method='host argmax',
                prompt_tokens=512, decode_steps=64, cap=1024,
                profile=dict(wformat='int8'), identity={},
                prefill=dict(tokens=512, device_tok_s=132.22),
                decode=dict(tokens=64, device_tok_s=24.87))


@pytest.fixture
def cpu():
    return dict(cases=[dict(model='lfm2', status='PASS_NATIVE_CPU_BENCHMARK',
                           context=1024, prefill=dict(tokens=512, wall_tok_s=1021.21),
                           decode=dict(steps=64, wall_tok_s=93.31))])


def test_matching_workloads_render_comparison(fpga, cpu):
    lines = report.benchmark_table([fpga], {'lfm2': 'LFM2.5-230M'}, cpu)
    assert len(lines) == 3
    assert '| LFM2.5-230M | INT8 | 1021.21 | 132.22 | 93.31 |' in lines[2]


@pytest.mark.parametrize('field,value', [('prompt_tokens', 128), ('decode_steps', 16), ('cap', 256)])
def test_fpga_workload_mismatch_is_rejected(fpga, cpu, field, value):
    fpga[field] = value
    with pytest.raises(ValueError, match='lfm2: incompatible FPGA workload'):
        report.benchmark_table([fpga], {}, cpu)


@pytest.mark.parametrize('phase,key', [('prefill', 'tokens'), ('decode', 'tokens')])
def test_fpga_phase_counts_must_match_workload(fpga, phase, key):
    fpga[phase][key] = 1
    with pytest.raises(ValueError, match='incompatible FPGA workload'):
        report.benchmark_table([fpga], {})


@pytest.mark.parametrize('field', ['prefill', 'decode', 'context'])
def test_cpu_workload_mismatch_is_rejected(fpga, cpu, field):
    row = cpu['cases'][0]
    if field == 'context':
        row[field] = 256
    else:
        row[field]['tokens' if field == 'prefill' else 'steps'] = 1
    with pytest.raises(ValueError, match='lfm2: incompatible CPU workload'):
        report.benchmark_table([fpga], {}, cpu)


def test_failed_runs_do_not_require_completed_workload_fields(fpga, cpu):
    failed = dict(model='other', status='FAIL')
    cpu['cases'].append(failed)
    assert len(report.benchmark_table([failed, fpga], {}, cpu)) == 3


@pytest.mark.parametrize('incompatible', ['fpga', 'cpu'])
def test_invalid_workload_leaves_existing_report_untouched(tmp_path, monkeypatch, fpga, cpu, incompatible):
    run = tmp_path/'runs/lfm2'
    run.mkdir(parents=True)
    if incompatible == 'fpga':
        fpga['prompt_tokens'] = 128
    else:
        cpu['cases'][0]['context'] = 256
    (run/'manifest.json').write_text(json.dumps(fpga))
    cpu_path = tmp_path/'cpu.json'
    cpu_path.write_text(json.dumps(cpu))
    data_path, doc_path = tmp_path/'report.json', tmp_path/'report.md'
    data_path.write_text('existing data')
    doc_path.write_text('existing doc')
    monkeypatch.setattr(sys, 'argv', ['chestnut_report.py', '--runs', str(run.parent),
                                    '--json', str(data_path), '--markdown', str(doc_path),
                                    '--cpu-json', str(cpu_path)])
    with pytest.raises(ValueError, match='incompatible .* workload'):
        report.main()
    assert data_path.read_text() == 'existing data'
    assert doc_path.read_text() == 'existing doc'
