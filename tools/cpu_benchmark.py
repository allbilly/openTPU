#!/usr/bin/env python3
"""Benchmark the selected Chestnut models on the native CPU using llama.cpp.

Convert the pinned, already-downloaded checkpoints to GGUF Q8_0 in ~/.cache.
Only this invocation's temporary GGUF files are deleted; HF caches stay intact.
The native runner receives the same HF-tokenized Austen prompt as the FPGA.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
SELECTED = ('lfm2', 'qwen3', 'qwen35', 'qwen35-2b', 'lfm2-2.6b', 'smollm3')


def sha256(path):
    result = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(4*1024*1024), b''):
            result.update(block)
    return result.hexdigest()


def save(path, value):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, indent=2)+'\n')
    temp.replace(path)


def tokens(model, output):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    prompt = tokenizer((ROOT/'tools/data/austen_pp_ch1.txt').read_text())['input_ids'][:512]
    if len(prompt) != 512:
        raise RuntimeError('Expected 512 Austen tokens')
    chat = [{'role': 'user', 'content': 'What is the capital of France? Answer in one sentence.'}]
    chat_ids = tokenizer.apply_chat_template(chat, add_generation_prompt=True,
                                             enable_thinking=False, tokenize=True)
    chat_ids = list(chat_ids['input_ids'] if hasattr(chat_ids, 'keys') else chat_ids)
    (output/'prompt.ids').write_text(' '.join(map(str, prompt))+'\n')
    (output/'chat.ids').write_text(' '.join(map(str, chat_ids))+'\n')
    save(output/'tokens.json', dict(prompt=prompt, chat=chat_ids))


def decode(model, output):
    from transformers import AutoTokenizer
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    row = json.loads((output/'native.json').read_text())
    save(output/'text.json', dict(chat=tokenizer.decode(row['chat_token_ids'], skip_special_tokens=True),
                                decode=tokenizer.decode(row['decode']['token_ids'], skip_special_tokens=True)))


def run(args):
    sys.path.insert(0, str(ROOT))
    from tools.chestnut_checkpoints import CHECKPOINTS
    args.llama_source = args.llama_source.resolve()
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    args.cache.mkdir(parents=True, exist_ok=True)
    brew = Path(subprocess.check_output(['brew', '--prefix'], text=True).strip())
    ggml = Path(subprocess.check_output(['brew', '--prefix', 'ggml'], text=True).strip())
    backends = [ggml/'libexec/libggml-cpu-apple_m1.so', ggml/'libexec/libggml-blas.so']
    if not all(path.is_file() for path in backends):
        raise RuntimeError('Expected installed Apple M1 CPU and BLAS backends')
    compiler = ['clang++', '-O3', '-std=c++17', str(ROOT/'tools/cpu_benchmark.cpp'),
                '-I'+str(brew/'include'), '-L'+str(brew/'lib'), '-lllama', '-lggml', '-lggml-base',
                '-framework', 'CoreFoundation', '-lIOReport',
                '-o', str(output/'cpu_benchmark')]
    subprocess.run(compiler, check=True)
    converter = args.llama_source.resolve()/'convert_hf_to_gguf.py'
    converter_files = [converter, *sorted((args.llama_source/'conversion').rglob('*.py')),
                       *sorted((args.llama_source/'gguf-py/gguf').rglob('*.py'))]
    receipt = dict(status='RUNNING', started_utc=datetime.now(timezone.utc).isoformat(),
                   cpu=platform.processor(), os=platform.platform(),
                   host_memory_bytes=int(subprocess.check_output(['sysctl', '-n', 'hw.memsize'])),
                   cpu_name=subprocess.check_output(['sysctl', '-n', 'machdep.cpu.brand_string'], text=True).strip(),
                   host_power=subprocess.check_output(['pmset', '-g', 'batt'], text=True).strip(),
                   cpu_threads=args.threads, weight_format='GGUF Q8_0',
                   compiler_command=compiler, converter=str(converter), converter_sha256=sha256(converter),
                   converter_revision=subprocess.check_output(['git', '-C', str(args.llama_source),
                                                               'rev-parse', 'HEAD'], text=True).strip(),
                   converter_sources={str(path.relative_to(args.llama_source)): sha256(path)
                                      for path in converter_files},
                   runtime_library_sha256=sha256(brew/'lib/libllama.dylib'),
                   runtime_header_sha256=sha256(brew/'include/llama.h'),
                   sources={name: sha256(ROOT/name) for name in
                            ('tools/cpu_benchmark.py', 'tools/cpu_benchmark.cpp', 'tools/cpu_ioreport.hpp')},
                   backends={str(path): sha256(path) for path in backends},
                   method=dict(prompt_tokens=512, decode_steps=64, context=1024, repeats=1,
                               warmup='full 512-token prefill and one decode step, with memory cleared before timing',
                               sampling='greedy CPU argmax; ignore EOS for the fixed 64 steps',
                               includes='native llama_decode, synchronization and decode argmax/finite checks',
                               excludes='conversion, model loading, chat sanity check, warmup and initial argmax',
                               quantization_caveat='CPU GGUF Q8_0 differs from FPGA INT8/FP4; not numerically identical'),
                   cases=[])
    if args.measure_bandwidth:
        receipt['method']['decode_bandwidth'] = (
            'IOReport AMC Stats PCPU/ECPU DCS RD/WR bytes bracket the timed decode; '
            'all CPU processes included, GPU/I/O clients excluded; nominal base-M1 peak 68.25 GB/s; '
            'snapshot calls excluded from throughput timing')
        receipt['method']['peak_bandwidth_reference'] = 'https://research-information.bris.ac.uk/files/314256436/paper.pdf'
    save(output/'manifest.json', receipt)
    env = dict(os.environ, OMP_NUM_THREADS=str(args.threads), OPENBLAS_NUM_THREADS=str(args.threads),
               HF_HUB_OFFLINE='1', TOKENIZERS_PARALLELISM='false')
    try:
        for name in args.models:
            repo, label = CHECKPOINTS[name]
            model = ROOT/'models'/label
            metadata = json.loads((model/'download-metadata.json').read_text())
            if metadata['status'] != 'COMPLETE_VERIFIED':
                raise RuntimeError(f'{name}: checkpoint is not verified')
            case_dir = output/name
            case_dir.mkdir()
            case = dict(model=name, repository=repo, checkpoint=metadata, status='PREPARING',
                        started_utc=datetime.now(timezone.utc).isoformat())
            receipt['cases'].append(case)
            save(output/'manifest.json', receipt)
            print('CPU_PREPARING', name, flush=True)
            subprocess.run([sys.executable, __file__, '--prepare', str(model), str(case_dir)], check=True, env=env)
            case['prompt_token_ids'] = json.loads((case_dir/'tokens.json').read_text())['prompt']
            case['prompt_sha256'] = sha256(case_dir/'prompt.ids')
            # Leave at least 2 GiB after the conservative conversion-size estimate.
            weight_bytes = sum(path.stat().st_size for path in model.glob('*.safetensors'))
            if shutil.disk_usage(args.cache).free < weight_bytes + 2*1024**3:
                raise RuntimeError(f'{name}: insufficient conversion space with 2 GiB reserve')
            with tempfile.TemporaryDirectory(prefix=name+'-', dir=args.cache) as temp:
                gguf = Path(temp)/'model-q8_0.gguf'
                convert = [sys.executable, str(converter), str(model), '--outtype', 'q8_0', '--outfile', str(gguf)]
                case.update(status='CONVERTING', conversion_command=convert)
                save(output/'manifest.json', receipt)
                with (case_dir/'conversion.log').open('w') as log:
                    subprocess.run(convert, check=True, env=env, stdout=log, stderr=subprocess.STDOUT)
                case.update(gguf_bytes=gguf.stat().st_size, gguf_sha256=sha256(gguf), status='BENCHMARKING')
                save(output/'manifest.json', receipt)
                command = [str(output/'cpu_benchmark'), str(gguf), str(case_dir/'prompt.ids'),
                           str(case_dir/'chat.ids'), str(args.threads), '64', *map(str, backends),
                           str(int(args.measure_bandwidth))]
                case['benchmark_command'] = command
                print('CPU_BENCHMARKING', name, flush=True)
                with (case_dir/'native.json').open('w') as data, (case_dir/'native.log').open('w') as log:
                    subprocess.run(command, check=True, env=env, stdout=data, stderr=log)
                native = json.loads((case_dir/'native.json').read_text())
                case.update(native)
                case['generated_gguf_removed'] = True
            subprocess.run([sys.executable, __file__, '--decode', str(model), str(case_dir)], check=True, env=env)
            case['text'] = json.loads((case_dir/'text.json').read_text())
            case['finished_utc'] = datetime.now(timezone.utc).isoformat()
            save(output/'manifest.json', receipt)
            print('CPU_RESULT', name, json.dumps(dict(prefill=case['prefill'], decode_tok_s=case['decode']['wall_tok_s'],
                                                    chat=case['text']['chat'])), flush=True)
        receipt.update(status='PASS_SELECTED_CPU_SUITE', finished_utc=datetime.now(timezone.utc).isoformat())
    except BaseException as error:
        receipt.update(status='FAIL_CPU_SUITE', error=repr(error))
        raise
    finally:
        save(output/'manifest.json', receipt)


def main():
    if len(sys.argv) == 4 and sys.argv[1] in ('--prepare', '--decode'):
        (tokens if sys.argv[1] == '--prepare' else decode)(Path(sys.argv[2]), Path(sys.argv[3]))
        return
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llama-source', type=Path, required=True, help='Existing llama.cpp checkout containing the converter')
    parser.add_argument('--models', nargs='+', choices=SELECTED, default=list(SELECTED))
    parser.add_argument('--threads', type=int, default=8)
    parser.add_argument('--measure-bandwidth', action='store_true', help='Measure base-M1 CPU DCS DRAM byte counters during decode')
    parser.add_argument('--cache', type=Path, default=Path.home()/'.cache/opentpu-cpu-bench')
    parser.add_argument('--out', type=Path, required=True)
    run(parser.parse_args())


if __name__ == '__main__':
    main()
