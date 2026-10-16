#!/usr/bin/env python3
"""Physical CH1 correctness and prefill/decode benchmarks through Chestnut USB3.

python tools/chestnut_benchmark.py --model lfm2 --out build/chestnut-bench/lfm2
The default workload matches tools/qual/perf.py: 512 prompt tokens and 64 decode
steps, with host argmax. This CH1 test uses a 1024-token KV capacity and records
both device-cycle throughput and wall time, excluding checkpoint upload.
"""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import numpy as np

from opentpu import quant as Quant
from opentpu.host.board import Board, BoardBackend, device_config, sim_config
from opentpu.host.chestnut import ChestnutTransport
from opentpu.llm import load_spec, model_dir
from opentpu.llm import qwen3 as Q
from tools.chestnut_checkpoints import CHECKPOINTS


def checkpoint_path(name):
    """Use the download catalog for dense, Gemma and MoE checkpoint aliases."""
    return (ROOT/'models'/CHECKPOINTS[name][1] if name in CHECKPOINTS else model_dir(name)).resolve()


def image_choice(spec, cfg, cap, wformat, head_format, resident, *, experts=None, ple_host=None):
    """Mirror Engine's lookup and host-embedding fallback without loading weights."""
    lookup = (resident or getattr(spec, 'embed', 'f32') == 'int8') and Q.has_lookup(spec)
    kw = dict(wformat=wformat, head_format=head_format, lookup=lookup)
    if experts is not None:
        kw['experts'] = experts
    if ple_host is not None:
        kw['ple_host'] = ple_host
    try:
        image = spec.image(cfg, cap, 1, Q.PREFILL_ROWS, **kw)
    except MemoryError:
        if not (lookup and getattr(spec, 'embed', 'f32') == 'int8' and Q.has_embed_host(spec)):
            raise
        image = spec.image(cfg, cap, 1, Q.PREFILL_ROWS, **kw, embed_host=True)
    need = (image.nbytes + 4095) // 4096 * 4096 + 4 * cfg.IMEM_WORDS
    if need > cfg.DRAM_BYTES:
        raise MemoryError(f'Model and program need {need} bytes; CH1 has {cfg.DRAM_BYTES}')
    return image


def choose_profile(spec, cfg, cap, *, experts=None, ple_host=None,
                   resident_options=(True, False)):
    errors = []
    for wformat, head_format in [('int8', None), ('fp4', 'int8'), ('fp4', 'fp4')]:
        for resident in resident_options:
            try:
                image = image_choice(spec, cfg, cap, wformat, head_format, resident,
                                     experts=experts, ple_host=ple_host)
                return dict(wformat=wformat, head_format=head_format, resident=resident,
                            image_bytes=image.nbytes, program_bytes=4*cfg.IMEM_WORDS)
            except (MemoryError, ValueError) as error:
                errors.append(str(error))
    raise MemoryError('; '.join(dict.fromkeys(errors)))


def phase_metrics(tokens, elapsed, stats, core_hz):
    cycles = sum(int(s['cycles']) for s in stats)
    return dict(tokens=tokens, runs=len(stats), cycles=cycles,
                device_seconds=cycles/core_hz, wall_seconds=elapsed,
                device_tok_s=tokens*core_hz/cycles, wall_tok_s=tokens/elapsed)


class ParallelQuantization:
    """Split independent rows around the unchanged MXU packer in this process."""
    def __init__(self, workers):
        self.workers = workers
        self.original = Quant.quantize_mxu
        self.local = threading.local()
        if workers > 1:
            Quant.quantize_mxu = self

    def _pack(self, block, fmt, D):
        self.local.active = True
        try:
            return self.original(block, fmt, D)
        finally:
            self.local.active = False

    def __call__(self, W, fmt, D=128):
        if (self.workers == 1 or fmt == 'int8' or W.shape[0] < 128
                or getattr(self.local, 'active', False)):
            return self.original(W, fmt, D)
        blocks = np.array_split(W, min(self.workers, W.shape[0]))
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            pieces = list(pool.map(lambda block: self._pack(block, fmt, D), blocks))
        return tuple(np.concatenate([piece[i] for piece in pieces]) for i in range(2))

    def close(self):
        if Quant.quantize_mxu is self:
            Quant.quantize_mxu = self.original

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def release_engine(engine):
    if engine is None:
        return
    resources = [('drain', engine._drain)]
    pool = getattr(engine, '_pool', None)
    if pool is not None:
        resources.append(('compile pool', lambda: pool.shutdown(wait=True)))
    close = getattr(engine.backend, 'close', None)
    if close is not None:
        resources.append(('backend', close))
    errors = close_resources(resources)
    engine._pool = None
    if errors:
        raise RuntimeError('; '.join(errors))


def close_resources(resources, report=None):
    """Attempt every teardown step and never leave a successful failure receipt."""
    errors = []
    for name, close in resources:
        try:
            close()
        except BaseException as error:
            errors.append(f'{name}: {error!r}')
    if errors and report is not None:
        report.update(status='FAIL_CLEANUP', cleanup_errors=errors)
    return errors


def run(args):
    import torch
    from transformers import AutoTokenizer
    from fedora_matmul_check import matmul_check

    torch.set_num_threads(args.cpu_threads)
    torch.set_num_interop_threads(min(args.cpu_threads, 4))
    output = args.out.resolve()
    output.mkdir(parents=True, exist_ok=False)
    report = dict(status='STARTING', physical=True, model=args.model,
                  transport='Chestnut USB3 control/bulk -> PCIe XDMA',
                  started_utc=datetime.now(timezone.utc).isoformat(),
                  flash_written=False, fpga_programmed=False,
                  prompt_tokens=args.prompt, decode_steps=args.tokens, cap=args.cap,
                  cpu_threads=args.cpu_threads, quant_workers=args.quant_workers,
                  benchmark_method='tools/qual/perf.py: host argmax, logits not streamed',
                  wall_includes='program compilation, transfers, polling and host argmax',
                  wall_excludes='checkpoint loading, quantization, model upload and correctness check',
                  repository_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                                               cwd=ROOT, text=True).strip())
    for name in ('opentpu/host/chestnut.py', 'tools/chestnut_benchmark.py'):
        report.setdefault('sources', {})[name] = hashlib.sha256((ROOT/name).read_bytes()).hexdigest()

    def save():
        tmp = output/'manifest.json.tmp'
        tmp.write_text(json.dumps(report, indent=2)+'\n')
        tmp.replace(output/'manifest.json')

    t = board = engine = reference = quantizer = None
    start = time.perf_counter()
    save()
    try:
        quantizer = ParallelQuantization(args.quant_workers)
        path = checkpoint_path(args.model)
        spec = load_spec(path)
        if args.ple_host:
            os.environ['OTPU_PLE_HOST'] = '1'
        if args.expert_slots is not None and not getattr(spec, 'moe', None):
            raise ValueError('Expert slots require a mixture-of-experts checkpoint')
        report['model_path'] = str(path)
        report['checkpoint'] = []
        for f in sorted(path.glob('*.safetensors')):
            with f.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            report['checkpoint'].append(dict(name=f.name, bytes=f.stat().st_size, sha256=digest))
        if not report['checkpoint']:
            raise FileNotFoundError('No complete safetensors checkpoint at '+str(path))
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        t = ChestnutTransport()
        board = Board(t, calibrate=False)
        info = report['identity'] = board.info()
        cfg = device_config(info, DRAM_BYTES=1 << 31)
        report['config'] = asdict(cfg)
        if args.wformat == 'auto':
            profile = choose_profile(spec, cfg, args.cap, experts=args.expert_slots,
                                     ple_host=True if args.ple_host else None,
                                     resident_options=(False,) if args.no_resident else (True, False))
        else:
            resident = not args.no_resident
            image = image_choice(spec, cfg, args.cap, args.wformat, args.head_format, resident,
                                 experts=args.expert_slots, ple_host=True if args.ple_host else None)
            profile = dict(wformat=args.wformat, head_format=args.head_format, resident=resident,
                           image_bytes=image.nbytes, program_bytes=4*cfg.IMEM_WORDS)
        report['profile'] = profile
        report['profile'].update(expert_slots=args.expert_slots, ple_host=args.ple_host)
        print('Selected profile:', profile, flush=True)
        report['ecc_before'] = t.guard()
        report['status'] = 'MEMORY_AND_MATMUL_PREFLIGHT'
        save()
        board.scrub(force=True)
        report['matmul'] = matmul_check(board)
        if not report['matmul']['exact_match']:
            raise RuntimeError('Physical matmul differs from ISA')
        if report['matmul']['actual_instructions'] != report['matmul']['expected_instructions']:
            raise RuntimeError('Physical matmul instruction count differs from ISA')
        print('Full CH1 initialization/verification and exact matmul passed.', flush=True)
        # A smaller conversion cache keeps the complete large checkpoints usable
        # on an 8 GiB host; tensors and quantization are the standard reader's.
        class Weights(Q.Weights):
            CACHE = 1 << 20
        if getattr(spec, 'moe', None):
            weights = Q.LazyWeights(path)
        elif spec.__class__.__module__.endswith('.gemma4'):
            weights = Q.load_weights(path)
        else:
            weights = Weights(path)
        formats = dict(wformat=profile['wformat'], head_format=profile['head_format'])
        offload = {}
        if args.expert_slots is not None:
            offload = dict(experts=args.expert_slots, pool_file=output/'experts.pool')
        report['status'] = 'MODEL_UPLOAD'
        save()
        engine = Q.Engine(spec, weights, cap=args.cap, cfg=cfg,
                          backend=lambda c, imgs: BoardBackend(c, imgs, transport=t, model=path.name),
                          resident=profile['resident'], **formats, **offload)
        chat = [{'role': 'user', 'content': 'What is the capital of France? Answer in one sentence.'}]
        prompt = tokenizer.apply_chat_template(chat, add_generation_prompt=True,
                                               enable_thinking=False, tokenize=True)
        prompt = list(prompt['input_ids'] if hasattr(prompt, 'keys') else prompt)
        report['status'] = 'PHYSICAL_TOKEN_CHECK'
        save()
        got = engine.generate(prompt, max_new=args.check_tokens,
                              on_token=lambda token: print('PHYSICAL_TOKEN', int(token), flush=True))
        report['correctness'] = dict(prompt_token_ids=prompt, actual_token_ids=got,
                                     text=tokenizer.decode(got, skip_special_tokens=True),
                                     expected_token_ids=None, exact_match=False)
        report['status'] = 'ISA_TOKEN_CHECK'
        save()
        # The reference uses per-position programs and a short cache. It tests
        # the same mathematical model/weight formats as the resident FPGA run.
        rcfg = cfg if offload else sim_config(spec, 256, cfg, wformat=formats['wformat'],
                                             head_format=formats['head_format'])
        reference = Q.Engine(spec, weights, cap=256, cfg=rcfg, **formats, **offload)
        # The immutable lazy table is identical for both runs. Sharing it avoids
        # a second multi-gigabyte FP32 copy on hosts with 8 GiB of RAM.
        reference.embed = engine.embed
        want = reference.generate(prompt, max_new=args.check_tokens)
        report['correctness'].update(expected_token_ids=want, exact_match=got == want)
        release_engine(reference)
        reference = None
        gc.collect()
        if got != want:
            raise RuntimeError(f'Physical tokens {got} differ from ISA {want}')
        print('Physical tokens match ISA:', tokenizer.decode(got, skip_special_tokens=True), flush=True)
        text = (ROOT/'tools/data/austen_pp_ch1.txt').read_text()
        tokens = tokenizer(text)['input_ids'][:args.prompt]
        if len(tokens) != args.prompt:
            raise RuntimeError('Benchmark text has too few prompt tokens')
        engine.reset()
        engine.stats.clear()
        report['status'] = 'PREFILL_BENCHMARK'
        save()
        begin = time.perf_counter()
        logits = engine.prefill(tokens)
        elapsed = time.perf_counter()-begin
        report['prefill'] = phase_metrics(len(tokens), elapsed, engine.stats, info['core_khz']*1000)
        print('Prefill:', report['prefill'], flush=True)
        report['status'] = 'DECODE_BENCHMARK'
        save()
        token = int(np.argmax(logits))
        before = len(engine.stats)
        snapshot0 = board.snapshot()
        decoded = []
        begin = time.perf_counter()
        for step in range(args.tokens):
            token = int(np.argmax(engine.step(token)))
            decoded.append(token)
            if (step+1) % 8 == 0:
                print('Decode progress:', step+1, '/', args.tokens, flush=True)
        engine._drain()
        elapsed = time.perf_counter()-begin
        snapshot1 = board.snapshot()
        report['decode'] = phase_metrics(args.tokens, elapsed, engine.stats[before:], info['core_khz']*1000)
        report['decode']['token_ids'] = decoded
        report['decode']['text'] = tokenizer.decode(decoded, skip_special_tokens=True)
        report['decode']['counters'] = {k: snapshot1[k]-snapshot0[k] for k in snapshot0 if k != 'snaps'}
        report['ecc_after'] = t.guard()
        report['status'] = 'PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK'
        print('Decode:', report['decode'], flush=True)
    except BaseException as error:
        report.update(status='FAIL', error=repr(error))
        import traceback
        traceback.print_exc()
    finally:
        try:
            resources = [('reference', lambda: release_engine(reference)),
                         ('engine', lambda: release_engine(engine))]
            if board is not None:
                resources.append(('board', board.close))
            if quantizer is not None:
                resources.append(('quantizer', quantizer.close))
            close_resources(resources, report)
        finally:
            if t:
                report['transfer_bytes'] = dict(written=t.transferred_write, read=t.transferred_read)
                try:
                    t.close()
                    report['temporary_pci_config_restored'] = True
                except Exception as error:
                    report.update(status='FAIL_RESTORE', restore_error=repr(error))
            report['total_seconds'] = time.perf_counter()-start
            report['finished_utc'] = datetime.now(timezone.utc).isoformat()
            save()
            print(report['status'], output/'manifest.json', flush=True)
    return 0 if report['status'] == 'PASS_PHYSICAL_CH1_MODEL_AND_BENCHMARK' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model', default='lfm2')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--prompt', type=int, default=512)
    parser.add_argument('--tokens', type=int, default=64)
    parser.add_argument('--cap', type=int, default=1024)
    parser.add_argument('--check-tokens', type=int, default=8)
    parser.add_argument('--cpu-threads', type=int, default=8)
    parser.add_argument('--quant-workers', type=int, default=1,
                        help='Parallel rows for CPU weight packing; default keeps the standard serial packer')
    parser.add_argument('--wformat', choices=('auto', 'int8', 'fp4', 'int4'), default='auto')
    parser.add_argument('--head-format', choices=('int8', 'fp4', 'int4'))
    parser.add_argument('--no-resident', action='store_true')
    parser.add_argument('--ple-host', action='store_true', help='Keep Gemma per-layer embedding rows on the host')
    parser.add_argument('--expert-slots', type=int, help='Expert slots per layer; stream other experts from a pool file')
    args = parser.parse_args()
    if min(args.prompt, args.tokens, args.check_tokens, args.cpu_threads, args.quant_workers) < 1 or args.cap < args.prompt+args.tokens:
        parser.error('Positive counts and enough KV capacity are required')
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
