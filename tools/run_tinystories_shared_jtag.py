#!/usr/bin/env python3
"""Test trained TinyStories on an exact reviewed shared-response JTAG image.

Default is an offline input preflight. --execute uses an already owned XVC
server and image-bound CH0 calibration receipt. No programming or flash writes.
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
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check_oracle_package_binding(oracle, profile, build_id):
    """Bind the offline oracle to the package; it intentionally has no live-board receipt."""
    assert oracle['target_build_id'] == build_id, 'ISA oracle belongs to another image'
    assert oracle['target_bitstream_sha256'] == profile.bitstream_sha256, 'ISA oracle bitstream differs'
    assert oracle['target_package_manifest_sha256'] == profile.manifest_sha256, 'ISA oracle package differs'
    assert oracle.get('oracle_identity_source') == \
        'reviewed c0182902 package/configuration; no physical identity asserted'


def validate_physical_preflight(path, profile, oracle, host, program_reference):
    """Validate completed hardware stages before resuming only the model workload."""
    path = Path(path).resolve()
    receipt = json.loads((path/'manifest.json').read_text())
    assert receipt.get('status') == 'FAIL_SMALL_TRAINED_MODEL_JTAG_TEST'
    assert receipt.get('error') == 'AssertionError()', \
        'Receipt did not stop at the guarded model-image assertion'
    assert receipt.get('build_id') == 'c0182902'
    assert receipt.get('package_sha256') == profile.manifest_sha256
    assert receipt.get('bitstream_sha256') == profile.bitstream_sha256
    assert receipt.get('model_sha256') == oracle['model_sha256']
    assert receipt.get('host_preparation_sha256') == sha(host/'host-preparation.json')
    assert receipt.get('flash_written') is False and receipt.get('programming_performed') is False
    assert receipt.get('actual_token_ids') == [] and 'uploaded_bytes' not in receipt
    assert receipt.get('initialization_chunks') == 2048, 'Required DDR initialization did not finish'
    assert receipt.get('program_fetch_inputs', {}).get('reference_sha256') == sha(program_reference)

    live = receipt.get('live_config', {})
    expected = oracle.get('config', {})
    for key in ('S', 'D', 'MCOLS', 'ACT_BLOCKS', 'ACT_ROWS', 'TMEM_WORDS',
                'IMEM_WORDS', 'LANES', 'PAIR', 'DSTEP', 'STREAM', 'SEQ_WC'):
        assert live.get(key) == expected.get(key), f'Prior physical preflight config differs: {key}'
    assert live.get('SEQ_WC') is True

    fetch = receipt.get('program_fetch', {})
    assert fetch.get('status') == 'PASS_PHYSICAL_1371_INSTRUCTION_FETCH_AND_65_EXACT_WORDS'
    assert fetch.get('exact_match') is True and fetch.get('instructions') == 1371
    assert fetch.get('actual_output_sha256') == fetch.get('expected_output_sha256')
    fetch_receipt = json.loads((path/'program-fetch/manifest.json').read_text())
    assert fetch_receipt.get('status') == fetch.get('status')
    program_load = json.loads((path/'programs/program-000001.json').read_text())
    assert program_load.get('status') == 'PASS_PROGRAM_READBACK_AND_LOAD_COMPLETION'
    assert program_load.get('waitc') is True and program_load.get('imem_load_finished') is True
    assert program_load.get('program_sha256') == fetch.get('program_sha256')
    assert program_load.get('actual_sha256') == program_load.get('expected_sha256')

    matmul = receipt.get('matmul', {})
    assert matmul.get('physical') is True and matmul.get('exact_match') is True
    assert matmul.get('actual_instructions') == matmul.get('expected_instructions') == 5
    matmul_load = json.loads((path/'programs/program-000002.json').read_text())
    assert matmul_load.get('status') == 'PASS_PROGRAM_READBACK_AND_LOAD_COMPLETION'
    assert matmul_load.get('waitc') is True and matmul_load.get('imem_load_finished') is True
    assert matmul_load.get('actual_sha256') == matmul_load.get('expected_sha256')

    calibration = receipt.get('calibration', {})
    assert calibration.get('snapshot'), 'Prior run lacks an image-bound calibration snapshot'
    return dict(receipt_sha256=sha(path/'manifest.json'), receipt_path=str(path/'manifest.json'),
                initialization_chunks=receipt['initialization_chunks'],
                fetch_output_sha256=fetch['actual_output_sha256'],
                fetch_program_load_sha256=program_load['actual_sha256'],
                matmul_exact=True, matmul_program_load_sha256=matmul_load['actual_sha256'],
                calibration_receipt_sha256=calibration.get('receipt_sha256'),
                calibration_snapshot=calibration['snapshot'])


def validate_partial_model_upload(path, profile, oracle, oracle_path, preflight):
    """Bind a continuation to an image fully written and partly read back before cancellation."""
    path = Path(path).resolve()
    receipt_path = path/'manifest.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt.get('status') == 'FAIL_SMALL_TRAINED_MODEL_JTAG_TEST'
    assert receipt.get('error') == 'SystemExit(143)', 'Upload receipt did not end at cancellation'
    assert receipt.get('build_id') == 'c0182902'
    assert receipt.get('package_sha256') == profile.manifest_sha256
    assert receipt.get('bitstream_sha256') == profile.bitstream_sha256
    assert receipt.get('oracle_sha256') == sha(oracle_path)
    assert receipt.get('expected_upload_image_bytes') == oracle['upload_image_bytes']
    assert receipt.get('flash_written') is False and receipt.get('programming_performed') is False
    assert receipt.get('actual_token_ids') == [] and 'weight_mismatch_offset' not in receipt
    size = oracle['upload_image_bytes'][0]
    assert receipt.get('uploaded_bytes') == receipt.get('upload_expected_bytes') == size
    verified = receipt.get('verified_image_bytes', 0)
    chunk = 256 << 10
    assert 0 < verified < size and verified % chunk == 0
    assert 'uploaded_image_readback_sha256' not in receipt
    expected_runner_sha = 'ca19e7ca99bf3e85aa9e1ad1317351e264f4ebdf3685c87148e02b69a3838b33'
    assert any(Path(name).name == 'run_tinystories_shared_jtag.py' and digest == expected_runner_sha
               for name, digest in receipt.get('sources', {}).items()), \
        'Partial-readback receipt was not produced by the expected guarded runner'
    prior_preflight = receipt.get('reused_physical_preflight', {})
    assert prior_preflight.get('receipt_sha256') == preflight['receipt_sha256']
    assert prior_preflight.get('initialization_chunks') == 2048
    assert prior_preflight.get('fetch_output_sha256') == \
        'dd03a527b23a6132be0f93094e4032cbe03e3378c61cc061f9bf3d75a6331787'
    assert prior_preflight.get('matmul_exact') is True
    assert prior_preflight.get('calibration_snapshot') == receipt.get('calibration', {}).get('snapshot')
    assert not list((path/'programs').glob('program-*.json')), \
        'Inference/program activity began after model upload'
    return dict(receipt_path=str(receipt_path), receipt_sha256=sha(receipt_path),
                runner_sha256=expected_runner_sha, uploaded_bytes=size,
                verified_prefix_bytes=verified, remaining_readback_bytes=size-verified,
                upload_seconds=receipt.get('upload_seconds'),
                preflight_receipt_sha256=prior_preflight['receipt_sha256'],
                calibration_snapshot=receipt['calibration']['snapshot'])


def validate_cancelled_readback(path, profile, oracle, oracle_path, prior_upload):
    """Bind a user-authorized skip to a completed write and a verified image prefix."""
    path = Path(path).resolve()
    receipt_path = path/'manifest.json'
    receipt = json.loads(receipt_path.read_text())
    size = oracle['upload_image_bytes'][0]
    assert receipt.get('status') == 'FAIL_SMALL_TRAINED_MODEL_JTAG_TEST'
    assert receipt.get('error') == 'KeyboardInterrupt()', 'Expected the read-only verification cancellation'
    assert receipt.get('build_id') == 'c0182902'
    assert receipt.get('package_sha256') == profile.manifest_sha256
    assert receipt.get('bitstream_sha256') == profile.bitstream_sha256
    assert receipt.get('oracle_sha256') == sha(oracle_path)
    assert receipt.get('model_sha256') == oracle['model_sha256']
    assert receipt.get('expected_upload_image_bytes') == [size]
    assert receipt.get('upload_expected_bytes') == size
    assert receipt.get('upload_bytes_written_this_attempt') == 0
    assert receipt.get('upload_bytes_reused_from_prior_attempt') == size
    verified = receipt.get('verified_image_bytes', 0)
    assert verified >= prior_upload['verified_prefix_bytes']
    assert verified < size and verified % (256 << 10) == 0
    assert receipt.get('uploaded_image_readback_sha256') is None
    assert receipt.get('actual_token_ids') == []
    assert receipt.get('flash_written') is False and receipt.get('programming_performed') is False
    assert receipt.get('partial_upload_resume', {}).get('receipt_sha256') == prior_upload['receipt_sha256']
    assert receipt.get('partial_upload_resume', {}).get('preflight_receipt_sha256') == \
        prior_upload['preflight_receipt_sha256']
    assert receipt.get('calibration', {}).get('snapshot') == prior_upload['calibration_snapshot']
    assert any(Path(name).name == 'run_tinystories_shared_jtag.py' and digest ==
               '02efc047a5a6058744ecb306982e156fa9eb6dbdc0cad29d12c549fd063938f1'
               for name, digest in receipt.get('sources', {}).items())
    assert not list((path/'programs').glob('program-*.json'))
    return dict(receipt_path=str(receipt_path), receipt_sha256=sha(receipt_path),
                verified_prefix_bytes=verified, image_bytes=size,
                unverified_bytes=size-verified, uploaded_image_sha256=oracle['upload_image_sha256'][0],
                full_image_hash_verified=False, flash_written=False, programming_performed=False,
                calibration_snapshot=receipt['calibration']['snapshot'])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-id', required=True, help='Exact selected c-prefixed image ID')
    for name in ('host-tree', 'package', 'model', 'oracle', 'out'):
        p.add_argument('--'+name, type=Path, required=True)
    p.add_argument('--calibration-receipt', type=Path)
    p.add_argument('--program-load-reference', type=Path,
                   default=ROOT/'build/checks/spare-shared-program-load-20261018-v1/manifest.json')
    p.add_argument('--xvc-host', default='localhost')
    p.add_argument('--xvc-port', type=int, default=3721)
    p.add_argument('--reuse-physical-preflight', type=Path,
                   help='Resume after a receipt with completed DDR, fetch and matmul tests')
    p.add_argument('--reuse-partial-upload', type=Path,
                   help='Continue readback of an exactly uploaded image after a verified prefix')
    p.add_argument('--cancelled-readback-receipt', type=Path,
                   help='Receipt proving a complete prior write and a verified prefix')
    p.add_argument('--skip-resumed-image-readback', action='store_true',
                   help='User-authorized inference without the full model-image checksum')
    p.add_argument('--execute', action='store_true')
    a = p.parse_args()
    assert not a.reuse_physical_preflight or a.execute, \
        '--reuse-physical-preflight requires --execute'
    assert not a.reuse_partial_upload or (a.execute and a.reuse_physical_preflight), \
        '--reuse-partial-upload requires --execute and --reuse-physical-preflight'
    assert not a.skip_resumed_image_readback or (a.execute and a.reuse_partial_upload and
        a.cancelled_readback_receipt), '--skip-resumed-image-readback requires execute and both receipts'
    assert not a.cancelled_readback_receipt or a.skip_resumed_image_readback, \
        '--cancelled-readback-receipt is only used for the explicit skip path'
    assert re.fullmatch(r'c[0-9a-f]{7}', a.build_id), 'Invalid exact build ID'
    host = a.host_tree.resolve()
    sys.path[:0] = [str(host), str(host/'tools'), str(ROOT/'tools')]
    import numpy as np
    from unittest.mock import patch
    from opentpu.host import board as board_module
    from opentpu.host.program_verify import ProgramReadbackBoard
    image_host = importlib.import_module('opentpu.host.spare_'+a.build_id)
    assert Path(image_host.__file__).resolve().is_relative_to(host), 'Imported another host profile'
    if hasattr(image_host, 'SparePcieProfile'):
        SparePcieProfile, SpareJtagTransport = image_host.SparePcieProfile, image_host.SpareJtagTransport
    else:
        assert a.build_id == 'c0182902', 'Unsupported exact-image profile API'
        SparePcieProfile = image_host.SpareC0182902Profile
        SpareJtagTransport = image_host.SpareC0182902JtagTransport
    from opentpu.llm import load_spec
    from opentpu.llm.qwen3 import Engine, load_weights
    from fedora_matmul_check import matmul_check
    from spare_program_fetch_check import inputs as fetch_inputs, program_fetch_check
    runtime = importlib.import_module('spare_runtime_'+a.build_id)
    assert Path(runtime.__file__).resolve().is_relative_to(host), 'Imported another runtime helper'
    check_calibration_receipt, calibration_snapshot = runtime.check_calibration_receipt, runtime.calibration_snapshot
    require_idle_for_test = runtime.require_idle_for_test
    a.out.mkdir(parents=True, exist_ok=False)
    state = dict(status='OFFLINE_SMALL_MODEL_INPUT_PREFLIGHT', hardware_accessed=False,
                 flash_written=False, programming_performed=False, build_id=a.build_id,
                 actual_token_ids=[], sources={str(Path(__file__).resolve()):sha(__file__)})
    transport = board = backend = None

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
        for name, digest in h['generated_sources'].items():
            assert sha(host/name) == digest, name
        oracle = json.loads(a.oracle.read_text())
        assert oracle['status'] == 'PASS_TRAINED_TINYSTORIES_INT8_ISA_ORACLE_PHYSICAL_PENDING'
        profile = SparePcieProfile(a.package)
        check_oracle_package_binding(oracle, profile, a.build_id)
        assert sha(a.model/'model.safetensors') == oracle['model_sha256']
        assert sha(a.model/'config.json') == oracle['model_config_sha256']
        for name, digest in oracle['source_hashes'].items():
            source = host/name if (host/name).exists() else ROOT/name
            assert sha(source) == digest, 'ISA oracle source differs: '+name
        assert str(importlib.import_module('opentpu').__file__).startswith(str(host)+'/')
        state.update(oracle_sha256=sha(a.oracle), model_sha256=oracle['model_sha256'],
                     expected_token_ids=oracle['expected_token_ids'],
                     expected_upload_image_bytes=oracle['upload_image_bytes'],
                     host_preparation_sha256=sha(host/'host-preparation.json'))
        fetch_binding, _, _ = fetch_inputs(a.program_load_reference)
        state['program_fetch_inputs'] = fetch_binding
        state['sources'][str(ROOT/'tools/spare_program_fetch_check.py')] = sha(ROOT/'tools/spare_program_fetch_check.py')
        state['sources'][str(ROOT/'tools/fedora_matmul_check.py')] = sha(ROOT/'tools/fedora_matmul_check.py')
        if not a.execute:
            state['status'] = 'PASS_SMALL_JTAG_MODEL_INPUTS_REVIEWED_IMAGE_AND_PHYSICAL_TEST_PENDING'
            return
        assert a.calibration_receipt, '--execute requires the exact successful calibration receipt'
        state.update(package_sha256=profile.manifest_sha256,
                     bitstream_sha256=profile.bitstream_sha256, status='OPENING_JTAG', hardware_accessed=None)
        save()
        transport = SpareJtagTransport(profile, a.xvc_host, a.xvc_port)
        state['hardware_accessed'] = True
        checked = check_calibration_receipt(a.calibration_receipt, profile, transport)
        state['calibration'] = checked
        before = calibration_snapshot(transport)
        board = ProgramReadbackBoard(transport, calibrate=False, program_receipts=a.out/'programs')
        identity = board.info()
        cfg = board_module.device_config(identity, DRAM_BYTES=1 << 32)
        state.update(identity=identity, live_config=asdict(cfg), status='CHECKING_LIVE_ARITHMETIC_CONFIG')
        save()
        for key in ('S', 'D', 'MCOLS', 'ACT_BLOCKS', 'ACT_ROWS', 'TMEM_WORDS',
                    'IMEM_WORDS', 'LANES', 'PAIR', 'DSTEP', 'STREAM', 'SEQ_WC'):
            assert getattr(cfg, key) == oracle['config'][key], 'ISA arithmetic config differs: '+key
        reuse = None
        if a.reuse_physical_preflight:
            reuse = validate_physical_preflight(a.reuse_physical_preflight, profile, oracle,
                                                host, a.program_load_reference)
            assert reuse['calibration_receipt_sha256'] == checked['receipt_sha256']
            assert reuse['calibration_snapshot'] == before, \
                'Live calibration differs from the completed physical preflight'
            require_idle_for_test(transport)
            previous_dir = a.reuse_physical_preflight.resolve()
            previous = json.loads((previous_dir/'manifest.json').read_text())
            state.update(reused_physical_preflight=reuse,
                         initialization_chunks=reuse['initialization_chunks'],
                         program_fetch=previous['program_fetch'], matmul=previous['matmul'],
                         status='REUSING_COMPLETED_PHYSICAL_PREFLIGHT')
            save()
        else:
            state.update(identity=identity, status='REQUIRED_MEMORY_INITIALIZATION')
            save()
            board.scrub(force=True)
            state['initialization_chunks'] = len(transport.scrub_log)
            state['status'] = 'PHYSICAL_PROGRAM_FETCH_REGRESSION_BEFORE_MODEL_UPLOAD'
            save()
            state['program_fetch'] = program_fetch_check(board, a.program_load_reference, a.out/'program-fetch')
            save()
            state['matmul'] = matmul_check(board)
            assert state['matmul']['exact_match']
        if a.reuse_partial_upload:
            assert reuse is not None
            partial = validate_partial_model_upload(a.reuse_partial_upload, profile, oracle,
                                                    a.oracle, reuse)
            assert partial['calibration_snapshot'] == before, \
                'Live calibration differs from the partial-upload receipt'
            require_idle_for_test(transport)
            state['partial_upload_resume'] = partial
            if a.skip_resumed_image_readback:
                cancelled = validate_cancelled_readback(a.cancelled_readback_receipt, profile,
                                                        oracle, a.oracle, partial)
                assert cancelled['calibration_snapshot'] == before, \
                    'Live calibration differs from the cancelled-readback receipt'
                state['cancelled_readback'] = cancelled
                state['status'] = 'ADOPTING_UPLOADED_IMAGE_WITH_PARTIAL_READBACK'
            else:
                state['status'] = 'CONTINUING_VERIFIED_MODEL_IMAGE_READBACK'
            save()
        state['status'] = 'RESUMING_TRAINED_MODEL_IMAGE_READBACK' if a.reuse_partial_upload else \
            'UPLOADING_TRAINED_MODEL_THROUGH_JTAG'
        save()

        def physical_backend(config, images):
            nonlocal backend
            assert [len(image) for image in images] == oracle['upload_image_bytes']
            hashes = [hashlib.sha256(image.tobytes()).hexdigest() for image in images]
            assert hashes == oracle['upload_image_sha256'], 'Physical image differs from ISA initial image'
            if a.reuse_partial_upload:
                if a.skip_resumed_image_readback:
                    skipped = state['cancelled_readback']
                    class AdoptedImageBackend(board_module.BoardBackend):
                        def __init__(self):
                            self._initialize(config, images, transport=transport, model=str(a.model), status=False,
                                             board=board, image_prepared=True,
                                             program_receipts=a.out/'programs')
                    backend = AdoptedImageBackend()
                    state.update(upload_expected_bytes=len(images[0]),
                                 upload_bytes_written_this_attempt=0,
                                 upload_bytes_reused_from_prior_attempt=len(images[0]),
                                 image_upload_reused_without_rewrite=True,
                                 full_image_readback_skipped_by_user=True,
                                 verified_image_prefix_bytes=skipped['verified_prefix_bytes'],
                                 full_image_readback_sha256=None,
                                 status='PHYSICAL_TINYSTORIES_INFERENCE_RUNNING_WITHOUT_FULL_IMAGE_CHECKSUM')
                    save()
                    return backend
                resume = state['partial_upload_resume']
                prefix = resume['verified_prefix_bytes']
                assert 0 < prefix < len(images[0]) and prefix % (256 << 10) == 0
                readback = hashlib.sha256()
                # The prior receipt proves that each byte in this prefix compared equal.
                readback.update(images[0][:prefix].tobytes())
                state.update(upload_expected_bytes=len(images[0]),
                             upload_bytes_written_this_attempt=0,
                             upload_bytes_reused_from_prior_attempt=len(images[0]),
                             verified_image_bytes=prefix,
                             upload_image_sha256=hashes,
                             status='VERIFYING_RESUMED_UPLOADED_MODEL_IMAGE')
                save()
                for offset in range(prefix, len(images[0]), 256 << 10):
                    nbytes = min(256 << 10, len(images[0])-offset)
                    expected_chunk = images[0][offset:offset+nbytes]
                    got = board.read(offset, nbytes)
                    if not np.array_equal(got, expected_chunk):
                        expected_chunk.tofile(a.out/'weight-mismatch.expected.bin')
                        got.tofile(a.out/'weight-mismatch.actual.bin')
                        state['weight_mismatch_offset'] = offset
                        raise RuntimeError('Resumed model-image readback differs; inference withheld')
                    readback.update(got.tobytes())
                    state['verified_image_bytes'] = offset+nbytes
                    save()
                assert readback.hexdigest() == hashes[0]
                state.update(uploaded_image_readback_sha256=readback.hexdigest(),
                             image_upload_reused_without_rewrite=True,
                             prior_upload_seconds=resume['upload_seconds'],
                             status='RESUMED_MODEL_IMAGE_READBACK_PASS')

                class AdoptedImageBackend(board_module.BoardBackend):
                    def __init__(self):
                        self._initialize(config, images, transport=transport, model=str(a.model), status=False,
                                         board=board, image_prepared=True,
                                         program_receipts=a.out/'programs')

                backend = AdoptedImageBackend()
                state['status'] = 'PHYSICAL_TINYSTORIES_INFERENCE_RUNNING'
                save()
                return backend

            started = time.monotonic()
            state.update(uploaded_bytes=0, upload_expected_bytes=len(images[0]))
            save()
            original_write = transport.mem_write

            def measured_write(channel, offset, data):
                # Bound each serial transfer so progress is saved while a
                # channel's multi-megabyte contiguous image is still uploading.
                for start in range(0, len(data), 256 << 10):
                    part = data[start:start+(256 << 10)]
                    original_write(channel, offset+start, part)
                    state['uploaded_bytes'] += len(part)
                    state['upload_seconds'] = time.monotonic()-started
                    save()

            # Reuse the exclusively held verified Board; every load_program
            # passes ProgramReadbackBoard before any IMEM load control write.
            with patch.object(board_module, 'Board', lambda *args, **kwargs: board), \
                 patch.object(transport, 'mem_write', measured_write):
                backend = board_module.BoardBackend(config, images, transport=transport, status=False)
            state['upload_seconds'] = time.monotonic()-started
            assert state['uploaded_bytes'] == len(images[0]), 'Incomplete or unexpected model upload extent'
            state['status'] = 'VERIFYING_UPLOADED_MODEL_IMAGE'
            save()
            readback = hashlib.sha256()
            for offset in range(0, len(images[0]), 256 << 10):
                nbytes = min(256 << 10, len(images[0])-offset)
                got = board.read(offset, nbytes)
                if not np.array_equal(got, images[0][offset:offset+nbytes]):
                    images[0][offset:offset+nbytes].tofile(a.out/'weight-mismatch.expected.bin')
                    got.tofile(a.out/'weight-mismatch.actual.bin')
                    state['weight_mismatch_offset'] = offset
                    raise RuntimeError('Initial image readback differs; inference withheld')
                readback.update(got.tobytes())
                state['verified_image_bytes'] = offset+nbytes
                save()
            assert readback.hexdigest() == hashes[0]
            state['uploaded_image_readback_sha256'] = readback.hexdigest()
            state['status'] = 'PHYSICAL_TINYSTORIES_INFERENCE_RUNNING'
            save()
            return backend

        def token(token_id):
            state['actual_token_ids'].append(int(token_id))
            save()

        engine = Engine(load_spec(a.model), load_weights(a.model), cap=oracle['context_capacity'],
                        cfg=cfg, backend=physical_backend, rows=1, pipeline=False,
                        wformat='int8', resident=False, prog_cache=False)
        got = engine.generate(oracle['prompt_token_ids'], max_new=len(oracle['expected_token_ids']), on_token=token)
        assert got == oracle['expected_token_ids'], 'Physical greedy tokens differ from exact ISA'
        transport.guard()
        assert calibration_snapshot(transport) == before, 'Calibration changed'
        state.update(status='PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS',
                     model_stats=engine.stats, calibration_unchanged=True,
                     limitations='Small trained model acceptance; original LFM230M/Mac regression and PCIe bandwidth remain pending')
        print(state['status'], flush=True)
    except BaseException as error:
        state.update(status='FAIL_SMALL_TRAINED_MODEL_JTAG_TEST', error=repr(error))
        raise
    finally:
        original_error = sys.exc_info()[0] is not None
        errors = []
        for resource in (backend, board, transport):
            if resource is not None:
                try:
                    resource.close()
                except BaseException as error:
                    errors.append(dict(resource=type(resource).__name__, error=repr(error)))
        if errors:
            state.update(status='FAIL_SMALL_MODEL_CLEANUP', cleanup_errors=errors)
        save()
        if errors and not original_error:
            raise RuntimeError('Small-model cleanup failed; see preserved receipt')


if __name__ == '__main__':
    main()
