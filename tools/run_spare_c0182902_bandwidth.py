#!/usr/bin/env python3
"""Native LD read throughput on the exact reviewed c0182902 image.

Reads a fixed logical span with the native LD path and reports device-side
throughput from the FPGA's RUNNING and DRAM counters. The program area and the
output buffer are written; the model image below them is only read, so the
TinyStories image checksum stays valid afterwards. Memory must already be
initialized by the exact image's integration run: this does not scrub, and it
does not qualify full-range payload correctness or long-term retention.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]

# The model image occupies 0..29,226,624; the program area starts at the next
# 4 KiB boundary, exactly where the inference backend puts it.
IMAGE_BYTES = 29226624
PROG_AT = -(-IMAGE_BYTES // 4096) * 4096
SWEEP_CHUNK = 16 << 10
# Outside the measured span, so the sweep never reads the buffer a run rewrote.
SWEEP_OUTPUT = 75 << 20
DEFAULT_SPAN = 64 << 20
MAX_SPAN = 1 << 27            # the ISA model's DRAM cap, for --model-only

# The reviewed package's preparation and the WAITC-corrected test tree that ran the
# accepted TinyStories work; both are exact c0182902 host preparations.
HOST_PREPARATION_STATUSES = (
    'EXACT_C0182902_JTAG_TEST_HOST_PREPARED_EXACT_IMAGE_REVIEW_PASS',
    'EXACT_C0182902_JTAG_TEST_HOST_PREPARED_WAITC_READBACK_CORRECTION',
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def digest_bytes(array):
    return hashlib.sha256(memoryview(array).cast('B')).hexdigest()


def native_read_program(words_module, span):
    I = words_module
    assert 0 < span <= 1 << 32 and span % SWEEP_CHUNK == 0
    program = [I.li(1, 0), I.loop(2, span // SWEEP_CHUNK),
               I.ld(0, 0, SWEEP_CHUNK // 4, ra=1), I.addi(1, 1, SWEEP_CHUNK),
               I.st(SWEEP_OUTPUT, 0, SWEEP_CHUNK // 4), I.halt()]
    plan = dict(logical_bytes=span, chunk_bytes=SWEEP_CHUNK,
                iterations=span // SWEEP_CHUNK, first_address=0,
                last_address=span - SWEEP_CHUNK,
                expected_instructions=4 + 2 * (span // SWEEP_CHUNK),
                expected_b_reads=span // 128,
                expected_b_writes=SWEEP_CHUNK // 128,
                payload_compare_bytes=SWEEP_CHUNK, program_area=PROG_AT,
                output_address=SWEEP_OUTPUT)
    return program, plan


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-id', choices=('c0182902',), required=True)
    p.add_argument('--host-tree', type=Path, required=True)
    p.add_argument('--package', type=Path)
    p.add_argument('--calibration-receipt', type=Path)
    p.add_argument('--xvc-host', default='localhost')
    p.add_argument('--xvc-port', type=int, default=3721)
    p.add_argument('--span', type=int, default=DEFAULT_SPAN)
    p.add_argument('--repeats', type=int, choices=range(1, 11), default=3)
    p.add_argument('--model-only', action='store_true',
                   help='Check the program geometry in the ISA model; no device access')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if not (0 < a.span <= 1 << 32 and a.span % SWEEP_CHUNK == 0):
        p.error('--span must be a positive 16 KiB multiple, at most 4 GiB')
    if not a.model_only and (a.package is None or a.calibration_receipt is None):
        p.error('A physical run requires --package and --calibration-receipt')
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    state = dict(status='CHECKING', hardware_accessed=False, programming_performed=False,
                 flash_written=False, build_id=a.build_id, transport='jtag', span=a.span,
                 runs=[], image_bytes=IMAGE_BYTES, image_region_read_only=True,
                 scope='Native LD read throughput from device RUNNING/DRAM counters; '
                       'final chunk compared, the model image is only read')
    transport = board = None

    def save():
        state['utc'] = datetime.now(timezone.utc).isoformat()
        temporary = out/'manifest.json.tmp'
        temporary.write_text(json.dumps(state, indent=2) + '\n')
        temporary.replace(out/'manifest.json')

    try:
        save()
        host = a.host_tree.resolve()
        sys.path[:0] = [str(host), str(host/'tools'), str(ROOT/'tools')]
        import numpy as np
        from opentpu import isa as I
        from opentpu.host.program_verify import ProgramReadbackBoard as Board
        from opentpu.host.dual_pcie import require
        image_host = importlib.import_module('opentpu.host.spare_' + a.build_id)
        assert Path(image_host.__file__).resolve().is_relative_to(host), \
            'Imported another host profile'
        SpareC0182902Profile = image_host.SpareC0182902Profile
        SpareC0182902JtagTransport = image_host.SpareC0182902JtagTransport
        runtime = importlib.import_module('spare_runtime_' + a.build_id)
        assert Path(runtime.__file__).resolve().is_relative_to(host), \
            'Imported another runtime helper'
        check_calibration_receipt = runtime.check_calibration_receipt
        calibration_snapshot = runtime.calibration_snapshot
        require_idle_for_test = runtime.require_idle_for_test
        state['sources'] = {str(Path(__file__).resolve()): digest(__file__)}
        program, plan = native_read_program(I, a.span if not a.model_only else min(a.span, MAX_SPAN))
        assert PROG_AT > IMAGE_BYTES and PROG_AT % 4096 == 0
        assert PROG_AT + 4*32768 + 32768 < SWEEP_OUTPUT, 'Program area overlaps the output'
        assert SWEEP_OUTPUT >= plan['logical_bytes'], 'The span would read the output buffer'
        state['plan'] = plan
        if a.model_only:
            from opentpu.isasim import Machine, board_config
            span = plan['logical_bytes']
            cfg = board_config(DRAM_BYTES=1 << 27)
            words = np.arange((1 << 27)//8, dtype=np.uint64)
            with np.errstate(over='ignore'):
                words = (words ^ np.uint64(0x13579bdf2468ace1))*np.uint64(0x9e3779b97f4a7c15)
                words ^= words >> np.uint64(29)
            memory = words.astype('<u8').view(np.uint8)
            expected = memory[span-SWEEP_CHUNK:span].copy()
            result = Machine(cfg, [program], [memory]).run().slices[0]
            require(result.icount == plan['expected_instructions'],
                    'ISA instruction coverage differs')
            written = result.dram[SWEEP_OUTPUT:SWEEP_OUTPUT+SWEEP_CHUNK]
            require(np.array_equal(written, expected), 'ISA final chunk differs')
            state.update(status='PASS_NATIVE_READ_BENCHMARK_ISA_GEOMETRY_PHYSICAL_PENDING',
                         model_expected_final_chunk_sha256=digest_bytes(expected),
                         model_actual_final_chunk_sha256=digest_bytes(written),
                         hardware_accessed=False)
            return
        h = json.loads((host/'host-preparation.json').read_text())
        assert h['build_id'] == a.build_id, 'Host preparation belongs to another image'
        # The package copy carries the review-pass preparation; the WAITC-corrected
        # tree records its correction in the status. Both are exact c0182902 hosts.
        require(h['status'] in HOST_PREPARATION_STATUSES, 'Wrong host preparation: ' + h['status'])
        require(h['host_interfaces'] == ['pcie', 'jtag'], 'Both runtime interfaces required')
        require(all(digest(host/name) == value for name, value in h['generated_sources'].items()),
                'Prepared host sources changed')
        state['host_preparation_sha256'] = digest(host/'host-preparation.json')
        profile = SpareC0182902Profile(a.package)
        state.update(package_manifest_sha256=profile.manifest_sha256,
                     bitstream_sha256=profile.bitstream_sha256,
                     status='OPENING_EXACT_JTAG', hardware_access_attempted=True,
                     hardware_accessed=None)
        save()
        transport = SpareC0182902JtagTransport(profile, a.xvc_host, a.xvc_port)
        state['hardware_accessed'] = True
        state['calibration_binding'] = check_calibration_receipt(
            a.calibration_receipt, profile, transport)
        state['calibration_before'] = calibration_snapshot(transport)
        require_idle_for_test(transport)
        board = Board(transport, check=True, calibrate=False,
                      program_receipts=out/'programs')
        state['identity'] = board.info()
        state['ecc_before'] = transport.ecc_state()
        require(state['identity']['build_id'] == int(a.build_id, 16),
                'Live image identity is not c0182902')
        from opentpu.host import regs as R
        state['memory_initialized'] = transport.reg_read(R.R_SCRATCH) == R.DRAM_INIT
        save()
        require(state['memory_initialized'],
                'Memory is not initialized: complete the exact image integration run first; '
                'this benchmark never scrubs.')
        words = np.asarray(I.assemble(program), np.uint32)
        if board.waitc:
            from opentpu import waits as W
            info = board.info()
            entries = W.entries(words, D=info['D'], S=1, prog=program)
        else:
            entries = None
        require(board.waitc and entries is not None,
                'This image takes wait entries; a WAITC-aware load is required')
        board.load_program(PROG_AT, words, entries)
        expected = board.read(plan['last_address'], SWEEP_CHUNK)
        state['expected_final_chunk_sha256'] = digest_bytes(expected)
        state['status'] = 'NATIVE_READ_COUNTER_BENCHMARK_RUNNING'
        save()
        for repeat in range(a.repeats):
            transport.guard()
            before = board.snapshot()
            require(before is not None, 'Performance counters unavailable')
            wall = time.perf_counter()
            stats = board.run(timeout=120)
            wall = time.perf_counter() - wall
            after = board.snapshot()
            require(after is not None, 'Performance counters unavailable')
            delta = {name: after[name] - before[name]
                     for name in ('RUNNING', 'DRAM_RD', 'DRAM_WR')}
            row = dict(repeat=repeat, stats=stats, counter_before=before,
                       counter_after=after, counter_delta=delta,
                       host_run_call_seconds=wall)
            state['runs'].append(row)
            save()
            seconds = delta['RUNNING'] / (state['identity']['core_khz']*1000)
            require(seconds > 0, 'No RUNNING time was counted')
            require(delta['DRAM_RD'] == a.span // 64,
                    f'DRAM read beats differ: {delta["DRAM_RD"]} for {a.span} bytes')
            # Every iteration stores the same chunk, so the card counts one chunk's beats
            # (the reference c0182800/c0182863 runners check the same value).
            require(delta['DRAM_WR'] == SWEEP_CHUNK // 64,
                    f'DRAM write beats differ: {delta["DRAM_WR"]}')
            require(stats['instructions'] == [plan['expected_instructions']],
                    'Instruction count differs')
            require(stats['b_reads'] == plan['expected_b_reads'],
                    f'b_reads differ: {stats["b_reads"]} vs {plan["expected_b_reads"]}')
            require(stats['b_writes'] == SWEEP_CHUNK // 128,
                    f'b_writes differ: {stats["b_writes"]} vs {SWEEP_CHUNK // 128}')
            actual = board.read(SWEEP_OUTPUT, SWEEP_CHUNK)
            row.update(final_chunk_sha256=digest_bytes(actual),
                       exact_final_chunk=bool(np.array_equal(actual, expected)))
            require(np.array_equal(actual, expected), 'Final read chunk differs')
            row.update(device_seconds=seconds,
                       logical_read_gbs=a.span/seconds/1e9,
                       counter_total_gbs=(delta['DRAM_RD']+delta['DRAM_WR'])*64/seconds/1e9)
            transport.guard()
            save()
        state['ecc_after'] = transport.ecc_state()
        state['calibration_after'] = calibration_snapshot(transport)
        require(state['calibration_before'] == state['calibration_after'],
                'Calibration changed during the benchmark')
        for row in (state['ecc_before'], state['ecc_after']):
            require(all(v['ecc_sec_errors'] == 0 and v['ecc_ded_errors'] == 0
                        for v in row.values()), 'ECC counters are not clean')
        require(all(digest(Path(name)) == value for name, value in state['sources'].items()),
                'Benchmark sources changed')
        state.update(status='PASS_OBSERVED_NATIVE_READ_BANDWIDTH_FULL_RANGE_PENDING',
                     median_logical_read_gbs=statistics.median(
                         r['logical_read_gbs'] for r in state['runs']),
                     temperature_after_c=board.info()['temp_c'],
                     model_image_untouched_by_benchmark=True,
                     limitations=[
                         'Synthetic native LD stream; LLM decode and write throughput stay separate.',
                         'Only the final 16 KiB chunk is compared; full-range payload and '
                         'retention qualification remain pending.',
                         'The read span covers the model image read-only plus the program area; '
                         'stores go to an output buffer outside the span.',
                         'Compare only identical spans, repeats and clocks.'])
        print(state['status'], flush=True)
    except BaseException as error:
        state.update(status='FAIL', error=repr(error))
        raise
    finally:
        try:
            if board is not None:
                board.close()
        finally:
            try:
                if transport is not None:
                    transport.close()
            finally:
                save()


if __name__ == '__main__':
    main()
