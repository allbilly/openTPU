#!/usr/bin/env python3
"""Save measured Chestnut results and model coverage as reviewable repo artifacts."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path


def validate_workloads(cases, cpu=None):
    """Refuse to publish successful runs under an incompatible fixed workload."""
    for row in cases:
        if row['status'] != 'PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK':
            continue
        actual = (row.get('prompt_tokens'), row.get('decode_steps'), row.get('cap'),
                  row.get('prefill', {}).get('tokens'), row.get('decode', {}).get('tokens'))
        if actual != (512, 64, 1024, 512, 64):
            raise ValueError(f'{row["model"]}: incompatible FPGA workload {actual}; '
                             'expected 512 prompt tokens, 64 decode steps, context 1024 '
                             'and matching phase token counts')
    for row in (cpu or {}).get('cases', []):
        if row['status'] != 'PASS_NATIVE_CPU_BENCHMARK':
            continue
        actual = (row.get('prefill', {}).get('tokens'),
                  row.get('decode', {}).get('steps'), row.get('context'))
        if actual != (512, 64, 1024):
            raise ValueError(f'{row["model"]}: incompatible CPU workload {actual}; '
                             'expected 512 prompt tokens, 64 decode steps, context 1024')


def decode_bandwidth(row):
    """64-byte payload beats over RUNNING time, against one physical CH1 peak."""
    counts = row['decode'].get('counters', {})
    info = row['identity']
    if not all(key in counts for key in ('DRAM_RD', 'DRAM_WR', 'RUNNING')):
        return None
    if not counts['RUNNING'] or not info.get('core_khz') or not info.get('ddr_mts'):
        return None
    seconds = counts['RUNNING']/(info['core_khz']*1000)
    transferred = (counts['DRAM_RD']+counts['DRAM_WR'])*64
    # CH1 exposes two logical address regions backed by one physical x64 channel.
    peak = 8*info['ddr_mts']*1e6
    return dict(bytes=transferred, running_seconds=seconds,
                gb_s=transferred/seconds/1e9, peak_gb_s=peak/1e9,
                percent_of_peak=100*transferred/seconds/peak,
                physical_channels=1, beat_bytes=64)


def benchmark_table(cases, model_labels, cpu=None):
    """CPU native throughput, FPGA device throughput, and measured decode bandwidth."""
    validate_workloads(cases, cpu)
    cpu_rows = {row['model']: row for row in (cpu or {}).get('cases', [])
                if row['status'] == 'PASS_NATIVE_CPU_BENCHMARK'}
    order = {name: index for index, name in enumerate(cpu_rows)}
    rows = [row for row in cases if row['status'] == 'PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK']
    if order:
        rows.sort(key=lambda row: (order.get(row['model'], len(order)),
                                   row['profile']['wformat'] != 'int8'))
    lines = ['| Model | FPGA weights | CPU prefill | FPGA prefill | CPU decode | CPU RAM BW | '
             'FPGA decode | FPGA RAM BW |',
             '|:--|:--|--:|--:|--:|--:|--:|--:|']
    for row in rows:
        profile = row['profile']
        fmt = profile['wformat'].upper()
        if profile.get('head_format') and profile['head_format'] != profile['wformat']:
            fmt += ', '+profile['head_format'].upper()+' head'
        p, d = row['prefill'], row['decode']
        baseline = cpu_rows.get(row['model'])
        cp = f'{baseline["prefill"]["wall_tok_s"]:.2f}' if baseline else '—'
        cd = f'{baseline["decode"]["wall_tok_s"]:.2f}' if baseline else '—'
        cpu_bandwidth = baseline['decode'].get('dram_bandwidth') if baseline else None
        cbw = (f'{cpu_bandwidth["gb_s"]:.2f} GB/s ({cpu_bandwidth["percent_of_peak"]:.1f}%)'
               if cpu_bandwidth else '—')
        bandwidth = d.get('dram_bandwidth')
        bw = (f'{bandwidth["gb_s"]:.2f} GB/s ({bandwidth["percent_of_peak"]:.1f}%)'
              if bandwidth else '—')
        label = model_labels.get(row['model'], row['model'])
        lines.append(f'| {label} | {fmt} | {cp} | {p["device_tok_s"]:.2f} | '
                     f'{cd} | {cbw} | {d["device_tok_s"]:.2f} | {bw} |')
    return lines


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=Path, default=Path('build/chestnut-bench'))
    parser.add_argument('--json', type=Path, default=Path('docs/data/chestnut_ch1_20261016.json'))
    parser.add_argument('--markdown', type=Path, default=Path('docs/chestnut_ch1_benchmarks.md'))
    parser.add_argument('--cpu-json', type=Path, default=Path('docs/data/chestnut_cpu_20261016.json'))
    args = parser.parse_args()
    cases = []
    for path in sorted(args.runs.glob('*/manifest.json')):
        row = json.loads(path.read_text())
        if row.get('physical') and 'benchmark_method' in row:
            row['receipt'] = str(path)
            row.pop('model_path', None)
            if row['status'] == 'PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK':
                row['decode']['dram_bandwidth'] = decode_bandwidth(row)
            cases.append(row)
    plan_path = args.runs/'model-plan.json'
    coverage = json.loads(plan_path.read_text()) if plan_path.exists() else []
    model_labels = {row['name']: row['repository'].split('/')[-1] for row in coverage}
    for row in coverage:
        matches = [case for case in cases if case['model'] == row['name']]
        if row.get('excluded_by_user'):
            row['test_status'] = 'EXCLUDED_BY_USER'
        elif any(case['status'] == 'PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK' for case in matches):
            row['test_status'] = 'PASS'
        elif matches:
            row['test_status'] = matches[-1]['status']
        elif row['status'] == 'NOT_RESIDENT_ON_CH1':
            row['test_status'] = 'NOT_RUN_CAPACITY'
        elif (args.runs/('storage-'+row['name']+'.log')).exists():
            row['test_status'] = 'NOT_RUN_STORAGE'
        else:
            row['test_status'] = 'PENDING_DOWNLOAD_OR_RUN'
    output = dict(updated_utc=datetime.now(timezone.utc).isoformat(),
                  scope='Physical CH1-only DDR800 image through Chestnut USB3, 2 GiB usable',
                  excluded_by_user=[row['name'] for row in coverage if row.get('excluded_by_user')],
                  method=dict(prompt_tokens=512, decode_steps=64, kv_capacity=1024,
                              repeats=1, sampling='host argmax; EOS does not end the fixed benchmark',
                              correctness='up to eight chat tokens compared exactly with the ISA simulator',
                              wall_includes='compilation, DMA, polling, full logits reads and argmax',
                              wall_excludes='checkpoint loading, quantization, model upload and correctness check',
                              decode_bandwidth='(DRAM_RD + DRAM_WR) * 64 bytes / (RUNNING / core_hz); '
                                               'percent of one physical x64 CH1 at ddr_mts, 6.4 GB/s at DDR800'),
                  cases=cases, coverage=coverage)
    thermal_path = args.json.with_name('chestnut_ch1_thermal_20261016.json')
    thermal = json.loads(thermal_path.read_text()) if thermal_path.exists() else None
    if thermal:
        output['thermal_diagnostic'] = {key: thermal[key] for key in
            ('status', 'model', 'weights', 'measured_utc', 'active_by_phase',
             'measured_clock_by_phase', 'ecc_after', 'temporary_pci_config_restored')}
        output['thermal_diagnostic']['data'] = str(thermal_path)
    cpu = json.loads(args.cpu_json.read_text()) if args.cpu_json.exists() else None
    validate_workloads(cases, cpu)
    if cpu:
        output['cpu_baseline'] = dict(data=str(args.cpu_json), status=cpu['status'],
                                     cpu_name=cpu['cpu_name'], weight_format=cpu['weight_format'])
    args.json.parent.mkdir(parents=True, exist_ok=True)
    args.json.write_text(json.dumps(output, indent=2)+'\n')
    lines = ['# Chestnut CH1 benchmarks', '',
             'These are physical measurements on the CH1-only PCIe image: 100 MHz core,',
             'DDR3-800 RAM (400 MHz, 800 MT/s), MCOLS4/ACT_ROWS4/LANES8 and 2 GiB usable DDR.',
             'Chestnut is connected',
             'as USB3 at 10 Gb/s, with a downstream PCIe Gen2 x2 link.', '',
             'The workload is 512 Austen prompt tokens followed by 64 greedy decode steps,',
             'with a 1024-token KV capacity. Device rates use the FPGA cycle count at',
             '100 MHz. FPGA columns show on-device rates; CPU columns use native elapsed time.',
             'Model loading, conversion/upload and separate correctness checks are excluded.',
             'Each row is one timed pass. These are different conditions from the',
             'README production results on the 4 GiB dual-channel DDR1066 card.', '',
             'All throughput rates below are tok/s. CPU columns use Q8_0',
             'weights; the same CPU result is repeated for each FPGA weight profile.', '']
    lines += benchmark_table(cases, model_labels, cpu)
    lines += ['', 'FPGA RAM BW is measured decode traffic as a percentage of the single physical',
              'CH1 payload peak: 6.4 GB/s at DDR3-800 on its x64 data bus. The two logical',
              'memory regions share that channel. It uses `(DRAM_RD + DRAM_WR) * 64` bytes',
              'divided by `RUNNING / core_hz`, then by the peak; it excludes host idle time.',
              'The counters cover the decode snapshot interval, following tools/qual/perf.py.']
    if cpu and cpu['method'].get('decode_bandwidth'):
        lines += ['', 'CPU RAM BW is measured with the AMC Stats byte counters',
                  '`PCPU DCS RD/WR` and `ECPU DCS RD/WR`, sampled immediately before and after',
                  'the same 64-step native decode. Snapshot calls are excluded from throughput',
                  'timing. The bandwidth interval includes their timestamp uncertainty, whose',
                  'bounds are saved with the raw before/after counters.',
                  'These counters include all CPU processes and exclude GPU/I/O clients;',
                  'background CPU traffic is included. Percentages use the nominal base-M1',
                  '[68.25 GB/s peak](https://research-information.bris.ac.uk/files/314256436/paper.pdf),',
                  'as listed in the paper\'s platform table. The counter interface follows',
                  '[mactop v2.1.6](https://github.com/metaspartan/mactop/blob/v2.1.6/internal/app/ioreport.go).']
        if cpu.get('counter_checks'):
            lines += ['', 'CPU throughput and bandwidth come from the latest completed counter-enabled',
                      'pass for each model. Initial Qwen3-0.6B and Qwen3.5-0.8B decode rates of',
                      '6.32 and 1.50 tok/s were rechecked against the same GGUF files with the',
                      'original runner, the new runner without counters, and the new runner',
                      'with counters. The large slowdowns did not recur; paired counter-on/off',
                      'decode rates differed by less than 2%. The latest counter-enabled passes',
                      'are shown above. All initial passes and controls remain in the CPU data;',
                      'the cause of the initial slowdowns was not established.']
    else:
        lines += ['', 'CPU RAM bandwidth was not measured; an em dash marks missing data.']
    lines += ['', 'Passing rows require exact ISA token comparison, physical matmul, full CH1',
              'zero initialization/readback, ECC enabled with zero corrected/uncorrectable',
              'errors, and restored temporary PCIe configuration. The full-vocabulary logits',
              'currently return through USB control reads; end-to-end throughput is lower',
              'than the FPGA device rates shown above. End-to-end timings remain in the raw receipts.']
    if cpu:
        lines += ['', '## Native CPU comparison', '',
                  f'The selected models were measured on an {cpu["cpu_name"]} MacBook Air',
                  f'with {cpu["host_memory_bytes"]/2**30:g} GiB RAM, using llama.cpp '
                  f'{cpu["cases"][0]["runtime_version"]}, {cpu["cpu_threads"]} CPU threads and no GPU backend.',
                  'The CPU uses GGUF Q8_0 weights converted from the same pinned HF checkpoints.',
                  'It receives the same 512 HF-tokenized Austen token IDs, then performs 64',
                  'greedy decode steps after that prompt, with a 1024-token context.']
        lines += ['', 'CPU rates are wall-clock measurements from one timed pass after a full',
                  'prefill and one decode warmup. Conversion, loading and the chat sanity check',
                  'are excluded. Decode includes CPU argmax and finite-logit checks; EOS does',
                  'not end the fixed workload. CPU Q8_0 and FPGA INT8/FP4 use different',
                  'quantization and implementations, so these are system baselines rather',
                  'than identical numerical workloads. Host background activity and CPU',
                  'frequency were not controlled. [CPU receipts](data/'+args.cpu_json.name+')',
                  'record checkpoint revisions, token IDs, timings, generated text, runtime',
                  'and converter hashes. The chat sanity check is not an accuracy evaluation',
                  'or an exact FPGA token comparison.', '',
                  'Both Qwen3.5 conversions emitted reciprocal-overflow warnings on weights',
                  'at most 1.18e-37. An audit of the unchanged quantizer confirmed that all',
                  'affected stored FP16 scales are zero and all Q8_0 scales are finite.',
                  'Both audited GGUF files matched the measured files byte for byte.',
                  'The audit receipts are included with the CPU data.']
    lines += ['', '## Model coverage', '',
              '| Checkpoint | Status | CH1 profile or constraint |', '|:--|:--|:--|']
    for row in coverage:
        profile = row.get('profile')
        if profile:
            note = f'{profile["wformat"]}, {profile["image_bytes"]/2**20:.0f} MiB image'
            if row.get('ple_host'):
                note += '; PLE table on host'
            if row.get('expert_slots'):
                note += f'; {row["expert_slots"]} expert slots/layer, host pool'
            if row['test_status'] == 'NOT_RUN_STORAGE':
                note += f'; checkpoint {row["checkpoint_bytes"]/1e9:.2f} GB'
        else:
            note = 'Checked layouts exceed 2 GiB; not a hardware inference pass'
            validation = row.get('capacity_validation')
            if validation:
                needed = validation['minimum_checked']['required_bytes']/2**20
                available = validation['dram_bytes']/2**20
                note = (f'Smallest of {len(validation["layouts"])} checked layouts needs '
                        f'{needed:.0f} MiB including program; CH1 has {available:.0f} MiB')
                if row.get('capacity_limit_accepted_by_user'):
                    note += '; recorded as requested by user'
        lines.append(f'| {row["repository"]} | {row["test_status"]} | {note} |')
    if thermal and thermal['status'] == 'PASS_FPGA_INFERENCE_THERMAL_CHECK':
        lines += ['', '## Temperature during FPGA inference', '',
                  'A separate LFM2.5-230M int8 pass sampled the die sensor while RUN was',
                  'asserted and HALTED was clear both before and after each sensor read.',
                  'The workload was 512 prompt tokens followed by 64 decode steps.', '',
                  '| Phase | Active samples | Temperature range | Measured core clock |',
                  '|:--|--:|--:|--:|']
        for phase, label in [('PREFILL_BENCHMARK', 'Prefill'), ('DECODE_BENCHMARK', 'Decode')]:
            temp = thermal['active_by_phase'][phase]
            clock = thermal['measured_clock_by_phase'][phase]
            lines.append(f'| {label} | {temp["samples"]} | {temp["min_c"]:.2f}–{temp["max_c"]:.2f} °C | '
                         f'{clock["estimate_mhz"]:.3f} MHz |')
        lines += ['', 'Clock estimates use the free-running UPTIME counter and host monotonic',
                  'time, with timestamp bounds around each SNAP write and readback. They span',
                  'each phase, including gaps between kernels. This pass showed no evidence',
                  'of thermal throttling and had zero ECC errors. These readings cover one',
                  'diagnostic pass.', '',
                  'The extra sensor reads affect host timing, so this diagnostic is excluded',
                  'from the throughput table. [Raw sensor and clock data](data/'+thermal_path.name+')',
                  'include the status words, sensor codes, timestamps and counter values.']
    lines += ['', '## Reproduce', '',
              'Install libusb, the `hf` CLI, NumPy, PyTorch, Transformers and safetensors.',
              'Transformers must understand the checkpoint tokenizer configuration.', '',
              '```sh',
              'python tools/chestnut_checkpoints.py --model lfm2',
              'python tools/chestnut_benchmark.py --model lfm2 --out build/chestnut-bench/new-lfm2',
              'python tools/chestnut_report.py', '```', '',
              'For temperature and measured clock readings during inference:', '',
              '```sh',
              'python tools/chestnut_thermal.py --out build/chestnut-thermal/new-lfm2',
              '```', '',
              'For the native Apple M1 CPU baseline, use an existing Homebrew llama.cpp/ggml',
              'installation, clang++, the Python environment above and a llama.cpp checkout',
              'whose converter supports these models:', '',
              '```sh',
              'python tools/cpu_benchmark.py --llama-source /path/to/llama.cpp --measure-bandwidth --out build/cpu-bench/new-suite',
              '```', '',
              'The CPU script converts one cached checkpoint at a time in',
              '`~/.cache/opentpu-cpu-bench` and removes only its temporary GGUF file.',
              'Original HF checkpoints remain in `~/.cache/huggingface/hub`.', '',
              '`chestnut_checkpoints.py` calls `hf download` with a pinned revision into',
              '`~/.cache/huggingface/hub`, verifies published file hashes, and links `models/`',
              'to the cache. `--wformat fp4 --head-format int8` selects FP4 layers.',
              '`--quant-workers 4` packs independent rows in parallel using the standard',
              'quantizer; this affects the excluded checkpoint-preparation phase.',
              'Gemma E2B uses `--ple-host`; MoE models use `--expert-slots K` and a pool file.',
              'No FPGA SRAM or flash programming occurs. The script refuses an unexpected',
              'endpoint/image, dirty ECC, out-of-range memory, busy DMA or global SoC reset.', '',
              'The compact [result data](data/chestnut_ch1_20261016.json) includes source hashes,',
              'checkpoint hashes, tokens, timings, counters and coverage. Per-run logs and',
              'original receipts remain in ignored `build/chestnut-bench/`.']
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text('\n'.join(lines)+'\n')
    print(args.markdown)
    print(args.json)


if __name__ == '__main__':
    main()
