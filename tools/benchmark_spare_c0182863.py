"""Benchmark Qwen3.5-2B INT8 in 94.2% of c0182863's 4 GiB through Chestnut.

Reuse the calibration and zero initialization of a completed LFM run in the same
boot. Checks eight tokens against ISA, then times 512 prompt tokens and 32 decode
steps. Every program reads back exactly before IMEM loading. Overwrites memory;
no FPGA programming, flash writes, recalibration or extra memory soak.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]

import numpy as np
from opentpu.host import regs as R
from opentpu.host.board import Board, BoardBackend, device_config, sim_config, dram_layout
from opentpu.host.dual_pcie import require, digest, LOGICAL_BYTES
from opentpu.host.program_verify import ProgramReadbackBoard
from opentpu.host.spare_c0182863 import SparePcieProfile, SpareChestnutTransport
from opentpu.llm import load_spec, model_dir
from opentpu.llm import qwen3 as Q
from chestnut_benchmark import image_choice, phase_metrics, release_engine
from fedora_matmul_check import matmul_check
from spare_runtime_c0182863 import calibration_snapshot, check_calibration_receipt
from chestnut_checkpoints import verify, wanted
from host_benchmark_profile import HostProfiler


def profile_board(profiler, board):
    if profiler is not None:
        profiler.attach(board, ('write', 'read', 'load_program', 'set_args',
                               'start', 'wait', 'snapshot'), 'board')


def profile_backend(profiler, backend):
    if profiler is not None:
        profile_board(profiler, backend.board)
        profiler.attach(backend, ('prepare', 'write', 'read', 'start', 'wait'), 'backend')


def profile_engine(profiler, engine):
    if profiler is not None:
        profiler.attach(engine, ('_compile', '_compile_decode', '_take', '_layer_run',
                                 'step', 'prefill', '_drain'), 'engine')


class ObservedTransport(SpareChestnutTransport):
    def __init__(self, profile):
        self.channel_io = {str(ch): dict(written=0, read=0, max_write_end=0) for ch in (0, 1)}
        super().__init__(profile)

    def mem_write(self, ch, off, data):
        begin = time.perf_counter()
        super().mem_write(ch, off, data)
        row = self.channel_io[str(ch)]
        row['write_seconds'] = row.get('write_seconds', 0) + time.perf_counter()-begin
        n = np.asarray(data).nbytes
        row['written'] += n
        row['max_write_end'] = max(row['max_write_end'], off + n)

    def mem_read(self, ch, off, count, out=None):
        result = super().mem_read(ch, off, count, out)
        self.channel_io[str(ch)]['read'] += count
        return result

def validate_initialization(previous, profile, transport):
    """Require complete zero write/read coverage from this package and live calibration."""
    require(previous.get('status') in (
        'PASS_C0182863_ZERO_INITIALIZATION',
        'PASS_OBSERVED_SPARE_PCIE_MATMUL_LFM2_FULL_MEMORY_QUALIFICATION_PENDING'),
        'Previous full initialization did not pass')
    require(previous['package']['manifest_sha256'] == profile.manifest_sha256,
            'Previous initialization belongs to another package')
    require(previous['calibration_before'] == previous['calibration_after'] ==
            calibration_snapshot(transport), 'Live calibration differs from initialized run')
    chunks = previous['zero_initialization_chunks']
    expected = {(mode, ch, base) for mode in (0, 1) for ch in (0, 1)
                for base in range(0, LOGICAL_BYTES//2, 4 << 20)}
    require(len(chunks) == len(expected) and
            {(row['mode'], row['channel'], row['base']) for row in chunks} == expected,
            'Initialization coverage incomplete or duplicated')
    require(all(row['beats'] == (4 << 20)//64 and row['ticks'] > 0 and
                row['returns'] == (row['beats'] if row['mode'] else 0) and
                not row.get('errors') and not row.get('bits') and not any(row.get('lanes', []))
                for row in chunks), 'Initialization coverage counters or data differ')
    require(transport.reg_read(R.R_SCRATCH) == R.DRAM_INIT, 'Memory initialization marker missing')
    require(not transport.reg_read(R.R_STATUS) &
            (R.ST_RUN | R.ST_LOADING | R.ST_ERROR | R.ST_AXI_ERR),
            'Accelerator must be idle and error free')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', type=Path, default=ROOT/'runtime/c0182863')
    parser.add_argument('--model', default='qwen35-2b')
    parser.add_argument('--calibration-receipt', type=Path, required=True)
    parser.add_argument('--initialization-receipt', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--profile-host', action='store_true',
                        help='Record per-phase host/USB/program/compiler elapsed time; adds instrumentation overhead')
    args = parser.parse_args(argv)
    out = args.out.expanduser().resolve()
    out.mkdir(parents=True, exist_ok=False)
    cal = args.calibration_receipt.expanduser().resolve()
    init = args.initialization_receipt.expanduser().resolve()
    import torch
    from transformers import AutoTokenizer
    torch.set_num_threads(8)
    torch.set_num_interop_threads(4)
    manifest = out / 'manifest.json'
    require(not manifest.exists(), 'Preserve the existing receipt; choose a fresh run directory')
    result = dict(status='STARTING', started_utc=datetime.now(timezone.utc).isoformat(),
                  physical=True, model='Qwen/Qwen3.5-2B', wformat='int8', resident=True,
                  cap=4096, prompt_tokens=512, decode_steps=32,
                  physical_memory_channels=[0, 1], logical_capacity_bytes=LOGICAL_BYTES,
                  transport='Chestnut USB3 -> PCIe XDMA', fpga_programmed=False,
                  flash_written=False, recalibrated=False, ecc_counters_cleared=False,
                  full_memory_qualification=False,
                  repository_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip())
    t = board = engine = reference = None
    profiler = HostProfiler() if args.profile_host else None
    code = 1

    def save(status=None):
        if status:
            if profiler is not None and not profiler.closed:
                profiler.set_phase(status)
            result['status'] = status
            print(status, flush=True)
        if profiler is not None:
            result['host_profile'] = profiler.snapshot()
        result['updated_utc'] = datetime.now(timezone.utc).isoformat()
        temp = out / 'manifest.json.tmp'
        temp.write_text(json.dumps(result, indent=2) + '\n')
        temp.replace(manifest)

    try:
        save('CHECKING_CHECKPOINT_AND_PACKAGE')
        profile = SparePcieProfile(args.package)
        result['package'] = dict(manifest_sha256=profile.manifest_sha256,
                                 bitstream_sha256=profile.bitstream_sha256)
        result['sources'] = {str(p.relative_to(ROOT)): digest(p) for p in
                             (Path(__file__), ROOT/'opentpu/host/spare_c0182863.py',
                              ROOT/'opentpu/host/chestnut.py', ROOT/'opentpu/llm/qwen35.py',
                              ROOT/'opentpu/llm/qwen3.py', ROOT/'opentpu/host/board.py',
                              ROOT/'opentpu/host/program_verify.py', ROOT/'tools/spare_runtime_c0182863.py',
                              ROOT/'tools/chestnut_benchmark.py', ROOT/'tools/chestnut_checkpoints.py',
                              ROOT/'tools/fedora_matmul_check.py', ROOT/'tools/host_benchmark_profile.py')}
        path = model_dir(args.model)
        metadata = json.loads((path / 'download-metadata.json').read_text())
        require(metadata.get('repository') == 'Qwen/Qwen3.5-2B',
                'Use the pinned Qwen3.5-2B checkpoint metadata')
        require(metadata['status'] == 'COMPLETE_VERIFIED', 'Checkpoint download incomplete')
        require(all(verify(path / item['rfilename'], item) for item in metadata['files'] if wanted(item)),
                'Checkpoint differs from pinned hashes')
        result['checkpoint_revision'] = metadata['revision']
        result['checkpoint'] = [dict(name=p.name, bytes=p.stat().st_size, sha256=digest(p))
                                for p in sorted(path.glob('*.safetensors'))]
        spec = load_spec(path)
        tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        t = ObservedTransport(profile)
        if profiler is not None:
            profiler.attach(t, ('reg_read', 'reg_write', 'reg_read_many',
                                'mem_read', 'mem_write', 'poll'), 'transport')
        result['calibration_binding'] = check_calibration_receipt(cal, profile, t)
        previous = json.loads(init.read_text())
        validate_initialization(previous, profile, t)
        result['initialization_reused'] = dict(receipt=str(init), sha256=digest(init),
                                               live_marker=t.reg_read(R.R_SCRATCH))
        result['calibration_before'] = calibration_snapshot(t)
        result['ecc_before'] = t.guard()
        board = ProgramReadbackBoard(t, calibrate=False, program_receipts=out/'programs')
        profile_board(profiler, board)
        result['identity'] = board.info()
        cfg = device_config(result['identity'], DRAM_BYTES=LOGICAL_BYTES)
        result['config'] = asdict(cfg)
        image = image_choice(spec, cfg, 4096, 'int8', None, True)
        prog_at = (image.nbytes + 4095) // 4096 * 4096
        result['memory'] = dram_layout(cfg, image.nbytes, prog_at, image)
        result['memory']['allocated_percent'] = 100 * (prog_at + 4 * cfg.IMEM_WORDS) / cfg.DRAM_BYTES
        require(result['memory']['allocated_percent'] > 90, 'Test must occupy over 90% of FPGA RAM')
        for bucket in (1, 16):
            progs, _ = image.compile_decode(bucket, max((bucket - 1) * 256, spec.conv_k - 1), 256)
            counts = [len(p) for p in progs]
            require(all(n * 8 <= cfg.IMEM_WORDS for n in counts), 'Decode program exceeds IMEM')
            result.setdefault('compile_checks', []).append(dict(bucket=bucket, instructions=counts))
        save('PHYSICAL_MATMUL_CHECK')
        result['matmul'] = matmul_check(board)
        require(result['matmul']['exact_match'] and result['matmul']['actual_instructions'] ==
                result['matmul']['expected_instructions'], 'Physical matmul differs from ISA')
        class Weights(Q.Weights):
            CACHE = 1 << 20
        weights = Weights(path)

        def backend(c, images):
            save('UPLOADING_MODEL_IMAGE')
            begin = time.perf_counter()
            # Keep CHASH and channel-split temporary copies below 4 MiB.
            # The full packed image stays immutable for upload readback checks.
            original_write = Board.write
            done = 0
            transfer_chunk = 4 << 20
            def bounded_write(board, address, data):
                nonlocal done
                flat = np.ascontiguousarray(data).view(np.uint8).reshape(-1)
                for start in range(0, flat.nbytes, transfer_chunk):
                    part = flat[start:start+transfer_chunk]
                    original_write(board, address+start, part)
                    done += part.nbytes
                    if done % (128 << 20) == 0 or done == image.nbytes:
                        result['upload_progress'] = dict(bytes=done, total=image.nbytes,
                            elapsed_seconds=time.perf_counter()-begin)
                        save()
                        print('UPLOAD', done, '/', image.nbytes, flush=True)
            result['upload_chunk_bytes'] = transfer_chunk
            Board.write = bounded_write
            try:
                b = BoardBackend(c, images, transport=t, model=path.name,
                                 program_receipts=out/'model-programs')
            finally:
                Board.write = original_write
            try:
                profile_backend(profiler, b)
                require(b.image_bytes == image.nbytes, 'Actual image differs from capacity plan')
                result['upload'] = dict(bytes=b.image_bytes, seconds=time.perf_counter()-begin)
                checks = result['upload_readback'] = []
                for address in (0, (1 << 31)-4096, 1 << 31, (b.image_bytes-4096)//128*128):
                    expected = images[0][address:address+4096]
                    actual = b.board.read(address, len(expected))
                    row = dict(address=address, bytes=len(expected),
                               expected_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
                               actual_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),
                               exact_match=bool(np.array_equal(expected, actual)))
                    checks.append(row)
                    save()
                    require(row['exact_match'], 'Model upload readback differs')
                print('Uploaded and sampled', b.image_bytes, 'bytes', flush=True)
                return b
            except BaseException:
                b.close()
                raise

        save('PACKING_MODEL_IMAGE')
        engine = Q.Engine(spec, weights, cap=4096, cfg=cfg, backend=backend,
                          resident=True, wformat='int8', pipeline='thread')
        profile_engine(profiler, engine)
        require(engine.resident and engine.device_inputs, 'Resident device-input configuration not active')
        chat = [{'role': 'user', 'content': 'What is the capital of France? Answer in one sentence.'}]
        prompt = tokenizer.apply_chat_template(chat, add_generation_prompt=True,
                                               enable_thinking=False, tokenize=True)
        prompt = list(prompt['input_ids'] if hasattr(prompt, 'keys') else prompt)
        save('PHYSICAL_TOKEN_CHECK')
        def token_seen(token):
            result.setdefault('partial_token_ids', []).append(int(token))
            save()
            print('PHYSICAL_TOKEN', int(token), flush=True)
        got = engine.generate(prompt, max_new=8, on_token=token_seen)
        result['correctness'] = dict(prompt_token_ids=prompt, actual_token_ids=got,
                                     text=tokenizer.decode(got, skip_special_tokens=True), exact_match=False)
        save('ISA_TOKEN_CHECK')
        rcfg = sim_config(spec, 256, cfg, wformat='int8')
        reference = Q.Engine(spec, weights, cap=256, cfg=rcfg, wformat='int8')
        reference.embed = engine.embed
        want = reference.generate(prompt, max_new=8)
        result['correctness'].update(expected_token_ids=want, exact_match=got == want)
        save()
        require(got == want and len(got) == 8 and 'Paris' in result['correctness']['text'],
                'Physical model answer differs from ISA')
        release_engine(reference)
        reference = None
        gc.collect()
        print('Exact physical answer:', result['correctness']['text'], flush=True)
        tokens = tokenizer((ROOT/'tools/data/austen_pp_ch1.txt').read_text())['input_ids'][:512]
        require(len(tokens) == 512, 'Insufficient benchmark prompt tokens')
        engine.reset()
        engine.stats.clear()
        save('PREFILL_BENCHMARK')
        begin = time.perf_counter()
        logits = engine.prefill(tokens)
        require(np.isfinite(logits).all(), 'Nonfinite prefill logits')
        result['prefill'] = phase_metrics(512, time.perf_counter()-begin, engine.stats, result['identity']['core_khz']*1000)
        print('Prefill:', result['prefill'], flush=True)
        save('DECODE_BENCHMARK')
        token = int(np.argmax(logits))
        before = len(engine.stats)
        snap0 = board.snapshot()
        decoded = []
        begin = time.perf_counter()
        for step in range(32):
            logits = engine.step(token)
            require(np.isfinite(logits).all(), 'Nonfinite decode logits')
            token = int(np.argmax(logits))
            decoded.append(token)
            result['decode_steps_completed'] = step+1
            save()
            if (step+1) % 8 == 0:
                print('Decode:', step+1, '/ 32', flush=True)
        engine._drain()
        elapsed = time.perf_counter()-begin
        snap1 = board.snapshot()
        result['decode'] = phase_metrics(32, elapsed, engine.stats[before:], result['identity']['core_khz']*1000)
        result['decode'].update(token_ids=decoded, text=tokenizer.decode(decoded, skip_special_tokens=True),
                                counters={k:snap1[k]-snap0[k] for k in snap0 if k != 'snaps'})
        traffic = 64 * sum(result['decode']['counters'][name] for name in ('DRAM_RD', 'DRAM_WR'))
        result['decode']['device_dram_gb_s'] = traffic / result['decode']['device_seconds'] / 1e9
        print('Decode:', result['decode'], flush=True)
        result['ecc_after'] = t.guard()
        result['calibration_after'] = calibration_snapshot(t)
        require(result['calibration_before'] == result['calibration_after'], 'Calibration changed during inference')
        result['identity_after'] = board.info()
        result['channel_io'] = t.channel_io
        result['upload']['channel_write_seconds'] = sum(v.get('write_seconds',0) for v in t.channel_io.values())
        require(all(v['written'] > image.nbytes//2 for v in t.channel_io.values()), 'Both channels were not loaded')
        require(all(digest(ROOT/name) == value for name,value in result['sources'].items()), 'Test sources changed')
        programs = [json.loads(p.read_text()) for p in sorted(out.glob('*programs/*.json'))]
        require(programs and all(p['status'] == 'PASS_PROGRAM_READBACK_AND_LOAD_COMPLETION' and
                p['expected_sha256'] == p['actual_sha256'] and p['imem_load_finished'] for p in programs),
                'Program readback/load receipts incomplete')
        result['program_readback'] = dict(count=len(programs), all_exact=True, all_loads_finished=True)
        save('PASS_PHYSICAL_SPARE4GB_QWEN35_2B_REFERENCE_AND_BENCHMARK')
        code = 0
    except BaseException as error:
        result.update(status='FAIL', error=repr(error))
        traceback.print_exc()
    finally:
        errors = []
        for name, close in [('reference', lambda:release_engine(reference)),
                            ('engine', lambda:release_engine(engine)),
                            ('board', lambda:board.close() if board else None),
                            ('transport', lambda:t.close() if t else None)]:
            try:
                close()
                if name == 'transport' and t:
                    result['temporary_pci_configuration_restored'] = True
            except BaseException as error:
                errors.append(dict(resource=name, error=repr(error)))
        if profiler is not None:
            try:
                profiler.close()
                result['host_profile'] = profiler.snapshot()
            except BaseException as error:
                errors.append(dict(resource='host_profile', error=repr(error)))
        if t:
            result['channel_io'] = t.channel_io
        if errors:
            result.update(status='FAIL_CLEANUP', cleanup_errors=errors)
            code = 1
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        print(result['status'], manifest, flush=True)
    return code


if __name__ == '__main__':
    raise SystemExit(main())
