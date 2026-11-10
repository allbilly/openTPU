#!/usr/bin/env python3
"""Finish verification of the TinyStories image suffix on the exact c0182902 image.

Combines the prefix verified by the cancelled readback receipt with a fresh read
of the remaining bytes, so every image byte has matched in some receipt. The
suffix is outside every runtime-written region (the I/O row area and the KV
cache slots), which are all below the prefix boundary. No programming or flash.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
import re
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CHUNK = 256 << 10


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_inputs(prefix_receipt, run_receipt, profile, oracle, oracle_path, model):
    prefix = json.loads((Path(prefix_receipt).resolve()/'manifest.json').read_text())
    run = json.loads((Path(run_receipt).resolve()/'manifest.json').read_text())
    assert prefix.get('status') == 'FAIL_SMALL_TRAINED_MODEL_JTAG_TEST'
    assert prefix.get('error') == 'KeyboardInterrupt()'
    assert prefix.get('upload_expected_bytes') == prefix.get('upload_bytes_reused_from_prior_attempt') \
        == oracle['upload_image_bytes'][0]
    verified = prefix.get('verified_image_bytes')
    assert verified and verified % CHUNK == 0 and verified < oracle['upload_image_bytes'][0]
    assert prefix.get('uploaded_image_readback_sha256') is None
    accepted_run_statuses = ('PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS',
                             'PASS_WARM_REPEAT_PHYSICAL_JTAG_TINYSTORIES_EXACT_ISA_TOKENS')
    assert run.get('status') in accepted_run_statuses, 'Not a passing c0182902 TinyStories run'
    assert run.get('actual_token_ids') == oracle['expected_token_ids']
    if run['status'] == accepted_run_statuses[-1]:
        # The repeat ran on the contents the cancelled readback left behind, and wrote nothing.
        assert run.get('image_upload_bytes_written_this_attempt') == 0
        assert run.get('image_bytes_reused_from_prior_run') == oracle['upload_image_bytes'][0]
        assert run.get('image_not_rewritten') is True
    for receipt in (prefix, run):
        assert receipt.get('build_id') == 'c0182902'
        assert receipt.get('package_sha256') == profile.manifest_sha256
        assert receipt.get('bitstream_sha256') == profile.bitstream_sha256
        assert receipt.get('oracle_sha256') == sha(oracle_path)
        assert receipt.get('model_sha256') == sha(model/'model.safetensors')
        assert receipt.get('flash_written') is False
        assert receipt.get('programming_performed') is False
    return dict(prefix_receipt_sha256=sha(Path(prefix_receipt).resolve()/'manifest.json'),
                run_receipt_sha256=sha(Path(run_receipt).resolve()/'manifest.json'),
                prefix_verified_bytes=verified,
                calibration_snapshot=run['calibration']['snapshot'],
                calibration_receipt_sha256=run['calibration']['receipt_sha256'])


def runtime_written_ranges(engine_image, cfg, cap):
    """Byte ranges inference writes: the I/O row area and every KV cache slot."""
    img = engine_image
    d, D = img.spec.head_dim, cfg.D
    from opentpu.llm.qwen3 import k_scale_bytes
    sizes = {'k': cap * d, 'ks': cap * k_scale_bytes(d, D), 'vt': d * cap, 'vs': 4 * cap}
    spans = [[0, img.layer0]]
    for li, (base, us, it, eo) in img.loc.items():
        lofs = img.bofs[img.lf[li]]
        blk = base + it * us + eo
        for per_head in lofs['kvs']:
            for desc in per_head:
                for name, size in sizes.items():
                    spans.append([blk + desc[name], blk + desc[name] + size])
    merged = []
    for s, e in sorted(spans):
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return merged


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-id', required=True)
    for name in ('host-tree', 'package', 'model', 'oracle', 'out', 'prefix-receipt',
                 'run-receipt'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--calibration-receipt', type=Path)
    p.add_argument('--xvc-host', default='localhost')
    p.add_argument('--xvc-port', type=int, default=3721)
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    assert re.fullmatch(r'c[0-9a-f]{7}', a.build_id), 'Invalid exact build ID'
    host = a.host_tree.resolve()
    sys.path[:0] = [str(host), str(host/'tools'), str(ROOT/'tools')]
    import numpy as np
    from opentpu.host import board as board_module
    from opentpu.host.program_verify import ProgramReadbackBoard
    image_host = importlib.import_module('opentpu.host.spare_'+a.build_id)
    assert Path(image_host.__file__).resolve().is_relative_to(host)
    SparePcieProfile = image_host.SpareC0182902Profile
    SpareJtagTransport = image_host.SpareC0182902JtagTransport
    from opentpu.llm import load_spec
    from opentpu.llm.qwen3 import Engine, load_weights
    runtime = importlib.import_module('spare_runtime_'+a.build_id)
    check_calibration_receipt = runtime.check_calibration_receipt
    calibration_snapshot = runtime.calibration_snapshot
    require_idle_for_test = runtime.require_idle_for_test
    a.out.mkdir(parents=True, exist_ok=False)
    state = dict(status='OFFLINE_SUFFIX_VERIFICATION_PREFLIGHT', hardware_accessed=False,
                 flash_written=False, programming_performed=False, build_id=a.build_id,
                 sources={str(Path(__file__).resolve()): sha(__file__)})
    transport = board = None

    def save():
        state['utc'] = datetime.now(timezone.utc).isoformat()
        temporary = a.out/'manifest.json.tmp'
        temporary.write_text(json.dumps(state, indent=2)+'\n')
        temporary.replace(a.out/'manifest.json')

    try:
        save()
        h = json.loads((host/'host-preparation.json').read_text())
        assert h['build_id'] == a.build_id and h['program_readback_required']
        assert h['host_interfaces'] == ['pcie','jtag'], 'Both runtime interfaces required'
        oracle = json.loads(a.oracle.read_text())
        assert oracle['status'] == 'PASS_TRAINED_TINYSTORIES_INT8_ISA_ORACLE_PHYSICAL_PENDING'
        profile = SparePcieProfile(a.package)
        assert oracle['target_build_id'] == a.build_id
        assert oracle['target_bitstream_sha256'] == profile.bitstream_sha256
        assert oracle['target_package_manifest_sha256'] == profile.manifest_sha256
        assert sha(a.model/'model.safetensors') == oracle['model_sha256']
        assert str(importlib.import_module('opentpu').__file__).startswith(str(host)+'/')
        prior = validate_inputs(a.prefix_receipt, a.run_receipt, profile, oracle, a.oracle, a.model)
        state['prior'] = prior
        state.update(oracle_sha256=sha(a.oracle), model_sha256=oracle['model_sha256'],
                     package_sha256=profile.manifest_sha256,
                     bitstream_sha256=profile.bitstream_sha256)
        from opentpu.isasim import board_config
        run = json.loads((a.run_receipt.resolve()/'manifest.json').read_text())
        recorded = run.get('live_config')
        assert recorded, 'Passing run receipt lacks its live arithmetic config'
        assert recorded.get('SEQ_WC') is True, \
            'Recorded config is not this image\'s WAITC arithmetic configuration'
        cfg = board_config(**{k: recorded[k] for k in (
            'S', 'D', 'MCOLS', 'ACT_BLOCKS', 'TMEM_WORDS', 'DRAM_BYTES',
            'IMEM_WORDS', 'LANES', 'PAIR', 'DSTEP', 'STREAM', 'ACT_ROWS', 'SEQ_WC')})
        captured = {}

        class Stop(Exception):
            pass

        def backend(config_, images):
            captured['images'] = [np.array(image, np.uint8, copy=True) for image in images]
            raise Stop

        engine = Engine.__new__(Engine)
        try:
            Engine.__init__(engine, load_spec(a.model), load_weights(a.model),
                            cap=oracle['context_capacity'], cfg=cfg, backend=backend,
                            rows=1, pipeline=False, wformat='int8', resident=False,
                            prog_cache=False)
        except Stop:
            pass
        images = captured['images']
        size = len(images[0])
        assert [len(image) for image in images] == oracle['upload_image_bytes']
        assert hashlib.sha256(images[0].tobytes()).hexdigest() == oracle['upload_image_sha256'][0]
        start = prior['prefix_verified_bytes']
        written = runtime_written_ranges(engine.image, cfg, oracle['context_capacity'])
        max_written = max(e for _, e in written)
        assert max_written <= start, \
            f'Runtime-written state reaches {max_written}, above the verified prefix {start}'
        state.update(image_bytes=size, image_sha256=oracle['upload_image_sha256'][0],
                     suffix_start=start, suffix_bytes=size-start,
                     runtime_written_max_end=max_written,
                     runtime_written_ranges=written,
                     status='SUFFIX_OUTSIDE_RUNTIME_WRITTEN_REGIONS')
        save()
        if not a.execute:
            state['status'] = 'PASS_SUFFIX_VERIFICATION_INPUTS_BOUND_PHYSICAL_PENDING'
            return
        assert a.calibration_receipt, '--execute requires the exact successful calibration receipt'
        state.update(status='OPENING_JTAG', hardware_accessed=None)
        save()
        transport = SpareJtagTransport(profile, a.xvc_host, a.xvc_port)
        state['hardware_accessed'] = True
        checked = check_calibration_receipt(a.calibration_receipt, profile, transport)
        state['calibration'] = checked
        before = calibration_snapshot(transport)
        board = ProgramReadbackBoard(transport, calibrate=False,
                                     program_receipts=a.out/'programs')
        identity = board.info()
        state.update(identity=identity, live_config=asdict(
            board_module.device_config(identity, DRAM_BYTES=1 << 32)),
            status='CHECKING_LIVE_STATE')
        save()
        assert checked['receipt_sha256'] == prior['calibration_receipt_sha256']
        assert before == prior['calibration_snapshot'], 'Live calibration differs from the run'
        require_idle_for_test(transport)
        state['ecc_before'] = transport.ecc_state()
        for ch, row in state['ecc_before'].items():
            assert row['ecc_sec_errors'] == 0 and row['ecc_ded_errors'] == 0, f'ECC on {ch}'

        readback = hashlib.sha256()
        # The prefix bytes were verified byte-for-byte against this same image earlier.
        readback.update(images[0][:start].tobytes())
        state.update(prefix_covered_by_prior_receipt=True,
                     status='VERIFYING_IMAGE_SUFFIX', verified_suffix_bytes=0)
        save()
        for offset in range(start, size, CHUNK):
            nbytes = min(CHUNK, size-offset)
            want = images[0][offset:offset+nbytes]
            got = board.read(offset, nbytes)
            if not np.array_equal(got, want):
                want.tofile(a.out/'suffix-mismatch.expected.bin')
                got.tofile(a.out/'suffix-mismatch.actual.bin')
                state['suffix_mismatch_offset'] = offset
                raise RuntimeError('Image suffix differs from the ISA image; coverage incomplete')
            readback.update(got.tobytes())
            state['verified_suffix_bytes'] = offset+nbytes-start
            save()
        digest = readback.hexdigest()
        assert digest == oracle['upload_image_sha256'][0], 'Combined image hash differs'
        transport.guard()
        assert calibration_snapshot(transport) == before, 'Calibration changed'
        state['ecc_after'] = transport.ecc_state()
        for ch, row in state['ecc_after'].items():
            assert row['ecc_sec_errors'] == 0 and row['ecc_ded_errors'] == 0, f'ECC after on {ch}'
        state.update(status='PASS_FULL_TINYSTORIES_IMAGE_COVERAGE_VERIFIED',
                     full_image_sha256=digest,
                     full_image_bytes_matched=size,
                     prefix_from_prior_receipt=start,
                     suffix_read_this_attempt=size-start,
                     calibration_unchanged=True)
        print(state['status'], flush=True)
    except BaseException as error:
        state.update(status='FAIL_SUFFIX_VERIFICATION', error=repr(error))
        raise
    finally:
        errors = []
        for resource in (board, transport):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(dict(resource=type(resource).__name__, error=repr(error)))
        if errors:
            state.update(status='FAIL_SUFFIX_VERIFICATION_CLEANUP', cleanup_errors=errors)
        save()
        if errors and sys.exc_info()[0] is None:
            raise RuntimeError('Suffix verification cleanup failed; see receipt')


if __name__ == '__main__':
    main()
