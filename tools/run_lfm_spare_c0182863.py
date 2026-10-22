#!/usr/bin/env python3
"""Observe the reviewed c0182863 spare-lane 4 GiB image over PCIe/Chestnut.

Identity reads FPGA state. Other stages overwrite both channels. The lfm
stage initializes memory and compares matmul/LFM2 with the ISA; memory and
inference additionally run the longer raw-pattern and native read sweeps.
Chestnut temporarily maps and restores PCIe configuration. No programming,
recalibration, ECC counter clearing, or flash writes are performed.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from functools import partial
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT/'tools')]

import numpy as np
from opentpu import isa as I
from opentpu.host import ddrcal, selfcal, regs as R
from opentpu.host.board import device_config
from opentpu.host.program_verify import ProgramReadbackBoard as Board
from opentpu.host.dual_pcie import CH_BYTES, LOGICAL_BYTES, require, digest
from opentpu.host.spare_c0182863 import (SparePcieProfile, SpareChestnutTransport,
    SpareXdmaTransport, SpareJtagTransport, initialization_pause)
from spare_runtime_c0182863 import calibration_snapshot, check_calibration_receipt, raw_range
from fedora_matmul_check import matmul_check

SWEEP_CHUNK = 16 << 10
SWEEP_OUTPUT = 4 << 20
PROGRAM_AT = 0x3c0000


def native_read_program(span=LOGICAL_BYTES, chunk=SWEEP_CHUNK):
    require(0 < span <= LOGICAL_BYTES and 0 < chunk <= 64 << 10 and
            chunk % 128 == 0 and span % chunk == 0, 'Invalid native sweep geometry')
    program = [I.li(1, 0), I.loop(2, span//chunk),
               I.ld(0, 0, chunk//4, ra=1), I.addi(1, 1, chunk),
               I.st(SWEEP_OUTPUT, 0, chunk//4), I.halt()]
    return program, dict(logical_bytes=span, chunk_bytes=chunk, iterations=span//chunk,
                         first_address=0, last_address=span-chunk,
                         expected_instructions=4+2*(span//chunk),
                         expected_b_reads=span//128, expected_b_writes=chunk//128,
                         payload_compare_bytes=chunk,
                         scope='Full logical-range native reads, ECC on CH1 only; only final zero chunk payload is compared')


def dma_alias_checks(transport):
    """Write every sentinel before reading any, exposing channel/half aliases."""
    offsets = (0, 1 << 30, CH_BYTES-4096)
    patterns, records = {}, []
    for ch in (0, 1):
        for off in offsets:
            words = np.arange(1024, dtype=np.uint32) ^ np.uint32((off//4) ^ ((ch+1)*0x13579bdf))
            data = words.astype('<u4').view(np.uint8)
            patterns[ch, off] = data
            transport.mem_write(ch, off, data)
    for (ch, off), expected in patterns.items():
        actual = transport.mem_read(ch, off, len(expected))
        record = dict(channel=ch, offset=off, bytes=len(expected),
                      expected_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
                      actual_sha256=hashlib.sha256(actual.tobytes()).hexdigest(),
                      exact_match=bool(np.array_equal(actual, expected)))
        records.append(record)
    return records


def zero_initialize(board, transport, out, result, save, *, experimental_pause_seconds=None):
    """Persist complete verification with default or explicitly selected pacing."""
    pause = initialization_pause(experimental_pause_seconds)
    require(getattr(transport, 'scrub_progress', None) is None,
            'Initialization progress already has an owner')
    result['zero_initialization_policy'] = dict(chunk_bytes=4 << 20,
        pause_seconds_per_chunk=pause, planned_pause_seconds=2048*pause,
        experimental=experimental_pause_seconds is not None,
        faster_pacing_physically_qualified=False, full_write_and_read_verification_required=True)
    path = out/'zero-initialization-chunks.jsonl'
    result['zero_initialization_progress'] = dict(completed_chunks=0, total_chunks=2048,
        elapsed_seconds=0, pause_seconds_per_chunk=pause, all_chunks_validated=False,
        initialization_complete=False)
    save()
    started = time.monotonic()
    with path.open('x', buffering=1) as stream:
        def record(progress):
            progress = dict(progress)
            row = progress.pop('chunk')
            stream.write(json.dumps(dict(progress=progress, chunk=row))+'\n')
            result['zero_initialization_progress'].update(progress)
            done, total = progress['completed_chunks'], progress['total_chunks']
            if done == 1 or done % 16 == 0 or done == total:
                save()
            if done == 1 or done % 128 == 0 or done == total:
                print(f"Zero initialization: {done}/{total} chunks validated "
                      f"({100*done/total:.1f}%), {progress['elapsed_seconds']:.1f} s; "
                      f"CH{row['channel']} {'verify' if row['mode'] else 'write'}", flush=True)
        transport.scrub_progress = record
        missing = object()
        original_scrub = vars(transport).get('scrub', missing)
        if experimental_pause_seconds is not None:
            transport.scrub = partial(transport.scrub, experimental_pause_seconds=experimental_pause_seconds)
        try:
            board.scrub(force=True)
            progress = result['zero_initialization_progress']
            require(progress['completed_chunks'] == progress['total_chunks'] == 2048 and
                    transport.reg_read(R.R_SCRATCH) == R.DRAM_INIT,
                    'Initialization returned without complete coverage and marker')
            result['zero_initialization_progress'].update(
                all_chunks_validated=True, initialization_complete=True)
        finally:
            if experimental_pause_seconds is not None:
                if original_scrub is missing:
                    del transport.scrub
                else:
                    transport.scrub = original_scrub
            del transport.scrub_progress
            # Failed/interrupting chunks stay in the manifest even though only
            # successfully validated chunks advance the progress journal.
            result['zero_initialization_chunks'] = list(getattr(transport, 'scrub_log', []))
            result['zero_initialization_progress']['elapsed_seconds'] = time.monotonic()-started
            result['zero_initialization_chunks_file'] = path.name
            result['zero_initialization_chunks_sha256'] = digest(path)
            save()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--package', type=Path, required=True)
    ap.add_argument('--xvc-host',default='localhost')
    ap.add_argument('--xvc-port',type=int,default=3721)
    ap.add_argument('--transport', choices=('xdma', 'chestnut', 'jtag'), default='xdma')
    ap.add_argument('--dev', default='/dev/xdma0')
    ap.add_argument('--stage', choices=('identity', 'lfm', 'memory', 'inference'), default='identity')
    ap.add_argument('--experimental-init-pause-ms', type=int, choices=(0, 5, 20, 50, 200),
                    help='Explicit LFM-only pacing experiment; default remains 200 ms per verified 4 MiB operation')
    ap.add_argument('--calibration-receipt', type=Path)
    ap.add_argument('--model', default='lfm2')
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args(argv)
    if args.experimental_init_pause_ms is not None and args.stage != 'lfm':
        ap.error('--experimental-init-pause-ms requires --stage lfm')
    if args.stage != 'identity' and args.calibration_receipt is None:
        ap.error('--calibration-receipt is required for lfm/memory/inference')
    out = args.out.expanduser().resolve()
    if out.exists():
        ap.error('Choose a fresh output directory')
    out.mkdir(parents=True)
    result = dict(status='VALIDATING_PACKAGE', physical_hardware_accessed=False,
                  physical_hardware_access_attempted=False,
                  physical_tests_performed=False, stage=args.stage,
                  programming='NOT_RUN', flash_written=False, recalibration_requested=False,
                  ecc_counters_cleared=False, physical_memory_channels=[0, 1],
                  logical_capacity_bytes=LOGICAL_BYTES, ecc_channels=[1], ch0_physical_lanes=[0,1,2,3,4,5,8,7], raw_bist=[], observations=[], model_checks=[],
                  started_utc=datetime.now(timezone.utc).isoformat())
    transport = board = None
    code = 1

    def save():
        p = out/'manifest.json.tmp'
        p.write_text(json.dumps(result, indent=2)+'\n')
        p.replace(out/'manifest.json')

    def observe(label):
        row = dict(label=label, utc=datetime.now(timezone.utc).isoformat(),
                   status=transport.reg_read(R.R_STATUS), ecc=transport.ecc_state(),
                   fpga_die_c=board.info()['temp_c'])
        result['observations'].append(row)
        save()
        return row

    try:
        save()
        profile = SparePcieProfile(args.package)
        result['package'] = dict(path=str(profile.package), manifest_sha256=profile.manifest_sha256,
                                 bitstream_sha256=profile.bitstream_sha256)
        result['sources'] = {str(p.relative_to(ROOT)): digest(p) for p in
            (Path(__file__), ROOT/'opentpu/host/dual_pcie.py', ROOT/'opentpu/host/spare_c0182863.py',
             ROOT/'tools/spare_runtime_c0182863.py', ROOT/'tools/spare_range_program.py', ROOT/'opentpu/host/chestnut.py',
             ROOT/'tools/fedora_matmul_check.py', ROOT/'opentpu/host/program_verify.py')}
        if args.stage in ('lfm', 'inference'):
            from importlib.metadata import version
            from opentpu.llm import model_dir
            model = model_dir(args.model).resolve()
            require(json.loads((model/'config.json').read_text()).get('model_type') in ('lfm2', 'lfm2_moe'),
                    'An LFM2 checkpoint is required')
            result['model_inputs'] = [dict(name=name, bytes=(model/name).stat().st_size,
                                          sha256=digest(model/name)) for name in
                ('config.json', 'tokenizer.json', 'tokenizer_config.json', 'model.safetensors')]
            result['python_runtime'] = dict(executable=sys.executable,
                packages={name: version(name) for name in ('numpy', 'torch', 'transformers', 'safetensors')})
        result['physical_hardware_access_attempted'] = True
        # A constructor can access USB/registers before failing its identity
        # checks. Preserve uncertainty until it returns, rather than claim
        # that a failed open left the device untouched.
        result['physical_hardware_accessed'] = None
        result['status'] = 'OPENING_TRANSPORT'
        save()
        transport = (SpareJtagTransport(profile,args.xvc_host,args.xvc_port) if args.transport == 'jtag' else SpareChestnutTransport(profile) if args.transport == 'chestnut'
                     else SpareXdmaTransport(profile, args.dev))
        result['physical_hardware_accessed'] = True
        board = Board(transport, check=True, calibrate=False, program_receipts=out/'programs')
        result['identity'] = board.info()
        result['calibration_state_before'] = selfcal.state(transport.csr)
        result['calibration_before'] = calibration_snapshot(transport)
        observe('initial')
        if args.stage == 'identity':
            result['status'] = 'PASS_SPARE_PCIE_IDENTITY_ONLY_MEMORY_NOT_TESTED'
        else:
            status = transport.reg_read(R.R_STATUS)
            require(not status & (R.ST_RUN | R.ST_LOADING), 'Memory tests require idle compute')
            result['calibration_binding'] = check_calibration_receipt(args.calibration_receipt, profile, transport)
            result['physical_tests_performed'] = True
            if args.stage != 'lfm':
                result['status'] = 'SPARE_RAW_RANGE_RUNNING'
                save()
                with (out/'raw-chunks.jsonl').open('w', buffering=1) as stream:
                    def record_chunk(row):
                        stream.write(json.dumps(row)+'\n')
                        result['raw_chunks_completed'] = row['ordinal']+1
                        if row['ordinal'] % 16 == 0:
                            observe('raw-chunk-'+str(row['ordinal']))
                        else:
                            save()
                    result['raw_range'] = raw_range(transport, record_chunk)
                result['raw_chunks_sha256'] = digest(out/'raw-chunks.jsonl')
            result['status'] = 'SPARE_ZERO_INITIALIZATION_RUNNING'
            save()
            # Raw address patterns are not native ECC codewords. Fully initialize
            # both channels before any native instruction/program load.
            zero_initialize(board, transport, out, result, save,
                experimental_pause_seconds=(None if args.experimental_init_pause_ms is None
                                            else args.experimental_init_pause_ms/1000))
            observe('after-zero-initialization')
            if args.stage != 'lfm':
                result['status'] = 'SPARE_NATIVE_READ_SWEEP_RUNNING'
                save()
                program, plan = native_read_program()
                result['native_read_sweep'] = plan
                board.load_program(PROGRAM_AT, np.asarray(I.assemble(program), dtype=np.uint32))
                stats = board.run(timeout=300)
                plan['actual'] = stats
                observe('after-full-native-read-sweep')
                transport.guard()
                require(stats['instructions'] == [plan['expected_instructions']] and
                        stats['b_reads'] == plan['expected_b_reads'] and stats['b_writes'] == plan['expected_b_writes'],
                        'Full native read sweep coverage counters differ')
                actual = board.read(SWEEP_OUTPUT, SWEEP_CHUNK)
                plan['final_chunk_zero'] = bool(np.all(actual == 0))
                save()
                require(plan['final_chunk_zero'], 'Final native read chunk differs from initialized zero')
                result['dma_alias_checks'] = dma_alias_checks(transport)
                save()
                require(all(r['exact_match'] for r in result['dma_alias_checks']), 'DMA channel/half boundary data differs')
                observe('after-dma-alias-checks')
                result['memory_scope'] = dict(raw_bist_unique_bytes_per_channel=CH_BYTES, raw_complementary_passes=2,
                    native_read_bytes=LOGICAL_BYTES, native_ecc_channels=[1], dma_payload_compare_bytes=6*4096,
                    native_final_chunk_compare_bytes=SWEEP_CHUNK,
                    full_native_payload_comparison=False, cold_warm_repeatability_qualified=False)
            else:
                result['memory_scope'] = dict(zero_initialization_verified=True, native_ecc_channels=[1],
                    raw_complementary_passes=0, native_read_bytes=0,
                    full_native_payload_comparison=False, cold_warm_repeatability_qualified=False,
                    scope='Initialization followed by matmul/model checks; full-memory pattern qualification is separate')
            if args.stage in ('lfm', 'inference'):
                if args.stage == 'inference':
                    board.scrub(force=True)
                result['status'] = 'SPARE_PHYSICAL_MATMUL_RUNNING'
                save()
                result['matmul'] = matmul_check(board)
                save()
                require(result['matmul']['exact_match'] and result['matmul']['actual_instructions'] ==
                        result['matmul']['expected_instructions'], 'Physical matmul differs from ISA')
                transport.guard()

                def record_model(check):
                    result['model_checks'].append(dict(check, physical=True, physical_memory_channels=[0, 1]))
                    save()

                def record_token(token):
                    result.setdefault('actual_partial_token_ids', []).append(int(token))
                    save()

                transport.record_model_check = record_model
                transport.record_model_token = record_token
                from opentpu.host.checks import model_check
                result['status'] = 'SPARE_PHYSICAL_LFM2_RUNNING'
                save()
                ok, message = model_check(transport, device_config(result['identity'], DRAM_BYTES=LOGICAL_BYTES),
                                          args.model, 8, False, wformat='int8',
                                          program_receipts=out/'model-programs')
                result['model_message'] = message
                save()
                require(ok and result['model_checks'] and all(r['exact_match'] and r['actual_token_ids'] and
                        r['actual_token_ids'] == r['expected_token_ids'] and 'Paris' in r['text']
                        for r in result['model_checks']), 'Exact physical LFM2 answer absent')
            observe('final')
            transport.guard()
            result['calibration_state_after'] = selfcal.state(transport.csr)
            result['calibration_after'] = calibration_snapshot(transport)
            require(result['calibration_state_before'] == result['calibration_state_after'] and
                    result['calibration_before'] == result['calibration_after'],
                    'Calibration changed during the observation')
            require(all(digest(ROOT/name)==value for name,value in result['sources'].items()), 'Runtime sources changed')
            result['status'] = ('PASS_OBSERVED_SPARE_PCIE_MATMUL_LFM2_FULL_MEMORY_QUALIFICATION_PENDING'
                                if args.stage == 'lfm' else
                                'PASS_OBSERVED_SPARE_PCIE_MEMORY_MATMUL_LFM2_REPEATABILITY_PENDING'
                                if args.stage == 'inference' else
                                'PASS_OBSERVED_SPARE_PCIE_MEMORY_REPEATABILITY_PENDING')
        code = 0
    except Exception as error:
        result.update(status='FAIL', error=repr(error))
        print(result['error'], flush=True)
        if transport is not None and board is not None:
            try:
                observe('failure-preserved')
                result['calibration_at_failure'] = calibration_snapshot(transport)
            except Exception as observation_error:
                result['failure_observation_error'] = repr(observation_error)
    except KeyboardInterrupt:
        result.update(status='INTERRUPTED', error='KeyboardInterrupt; no recovery writes requested')
        code = 130
    finally:
        errors = []
        for name, resource in (('board', board), ('transport', transport)):
            if resource is not None:
                try:
                    resource.close()
                except Exception as error:
                    errors.append(dict(resource=name, error=repr(error)))
        if errors:
            result.update(status='FAIL_CLEANUP', cleanup_errors=errors)
            code = 1
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
    return code


if __name__ == '__main__':
    raise SystemExit(main())
