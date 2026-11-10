#!/usr/bin/env python3
"""Warm repeat of the trained TinyStories generation on an already uploaded image.

Reads the image already in DDR and runs the same prompt again without rewriting
it, so a second identical token stream shows the run is repeatable on the same
configured image. No programming and no flash writes.
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


def validate_prior_run(path, profile, oracle, oracle_path):
    """Bind the repeat to a completed, exact-token run of the same image."""
    path = Path(path).resolve()
    receipt_path = path/'manifest.json'
    receipt = json.loads(receipt_path.read_text())
    assert receipt.get('status') == 'PASS_PHYSICAL_JTAG_TINYSTORIES_INT8_EXACT_ISA_TOKENS'
    assert receipt.get('build_id') == 'c0182902'
    assert receipt.get('package_sha256') == profile.manifest_sha256
    assert receipt.get('bitstream_sha256') == profile.bitstream_sha256
    assert receipt.get('oracle_sha256') == sha(oracle_path)
    assert receipt.get('model_sha256') == oracle['model_sha256']
    expected = oracle['expected_token_ids']
    assert receipt.get('expected_token_ids') == expected
    assert receipt.get('actual_token_ids') == expected, 'Prior run did not match the exact ISA tokens'
    assert receipt.get('calibration_unchanged') is True
    assert receipt.get('flash_written') is False and receipt.get('programming_performed') is False
    assert receipt.get('full_image_readback_skipped_by_user') is True
    verified = receipt.get('verified_image_prefix_bytes')
    assert verified == 15728640 and receipt.get('full_image_readback_sha256') is None
    calibration = receipt.get('calibration', {})
    assert calibration.get('snapshot'), 'Prior run lacks an image-bound calibration snapshot'
    assert any(Path(name).name == 'run_tinystories_shared_jtag.py' and digest ==
               '59fd25f37167dc164f3549188c313bd415b9e45106e328ddead0461ee1859530'
               for name, digest in receipt.get('sources', {}).items()), \
        'Prior run was not produced by the expected committed runner'
    return dict(receipt_path=str(receipt_path), receipt_sha256=sha(receipt_path),
                verified_image_prefix_bytes=verified,
                calibration_snapshot=calibration['snapshot'],
                calibration_receipt_sha256=calibration.get('receipt_sha256'),
                expected_token_ids=expected)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build-id', required=True, help='Exact selected c-prefixed image ID')
    for name in ('host-tree', 'package', 'model', 'oracle', 'out', 'prior-run'):
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
    assert Path(image_host.__file__).resolve().is_relative_to(host), 'Imported another host profile'
    SparePcieProfile = image_host.SpareC0182902Profile
    SpareJtagTransport = image_host.SpareC0182902JtagTransport
    from opentpu.llm import load_spec
    from opentpu.llm.qwen3 import Engine, load_weights
    runtime = importlib.import_module('spare_runtime_'+a.build_id)
    assert Path(runtime.__file__).resolve().is_relative_to(host), 'Imported another runtime helper'
    check_calibration_receipt = runtime.check_calibration_receipt
    calibration_snapshot = runtime.calibration_snapshot
    require_idle_for_test = runtime.require_idle_for_test
    a.out.mkdir(parents=True, exist_ok=False)
    state = dict(status='OFFLINE_WARM_REPEAT_PREFLIGHT', hardware_accessed=False,
                 flash_written=False, programming_performed=False, build_id=a.build_id,
                 actual_token_ids=[], sources={str(Path(__file__).resolve()): sha(__file__)})
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
        assert oracle['target_build_id'] == a.build_id
        assert oracle['target_bitstream_sha256'] == profile.bitstream_sha256
        assert oracle['target_package_manifest_sha256'] == profile.manifest_sha256
        assert sha(a.model/'model.safetensors') == oracle['model_sha256']
        assert sha(a.model/'config.json') == oracle['model_config_sha256']
        for name, digest in oracle['source_hashes'].items():
            source = host/name if (host/name).exists() else ROOT/name
            assert sha(source) == digest, 'ISA oracle source differs: '+name
        assert str(importlib.import_module('opentpu').__file__).startswith(str(host)+'/')
        prior = validate_prior_run(a.prior_run, profile, oracle, a.oracle)
        state['prior_run'] = prior
        state.update(oracle_sha256=sha(a.oracle), model_sha256=oracle['model_sha256'],
                     expected_token_ids=oracle['expected_token_ids'],
                     expected_upload_image_bytes=oracle['upload_image_bytes'],
                     package_sha256=profile.manifest_sha256,
                     bitstream_sha256=profile.bitstream_sha256)
        if not a.execute:
            state['status'] = 'PASS_WARM_REPEAT_INPUTS_BOUND_PHYSICAL_TEST_PENDING'
            return
        assert a.calibration_receipt, '--execute requires the exact successful calibration receipt'
        state.update(status='OPENING_JTAG', hardware_accessed=None)
        save()
        transport = SpareJtagTransport(profile, a.xvc_host, a.xvc_port)
        state['hardware_accessed'] = True
        checked = check_calibration_receipt(a.calibration_receipt, profile, transport)
        state['calibration'] = checked
        before = calibration_snapshot(transport)
        board = ProgramReadbackBoard(transport, calibrate=False, program_receipts=a.out/'programs')
        identity = board.info()
        cfg = board_module.device_config(identity, DRAM_BYTES=1 << 32)
        state.update(identity=identity, live_config=asdict(cfg), status='CHECKING_LIVE_STATE')
        save()
        for key in ('S', 'D', 'MCOLS', 'ACT_BLOCKS', 'ACT_ROWS', 'TMEM_WORDS',
                    'IMEM_WORDS', 'LANES', 'PAIR', 'DSTEP', 'STREAM', 'SEQ_WC'):
            assert getattr(cfg, key) == oracle['config'][key], 'ISA arithmetic config differs: '+key
        assert checked['receipt_sha256'] == prior['calibration_receipt_sha256']
        assert before == prior['calibration_snapshot'], 'Live calibration differs from the prior run'
        require_idle_for_test(transport)
        state['ecc_before'] = transport.ecc_state()
        for ch, row in state['ecc_before'].items():
            assert row['ecc_sec_errors'] == 0 and row['ecc_ded_errors'] == 0, \
                f'ECC not clean on {ch}'
        state['status'] = 'WARM_REPEAT_INFERENCE_PREPARED'
        save()

        def physical_backend(config, images):
            nonlocal backend
            assert [len(image) for image in images] == oracle['upload_image_bytes']
            hashes = [hashlib.sha256(image.tobytes()).hexdigest() for image in images]
            assert hashes == oracle['upload_image_sha256'], 'Model image differs from the ISA oracle'
            class AdoptedImageBackend(board_module.BoardBackend):
                def __init__(self):
                    self._initialize(config, images, transport=transport, model=str(a.model),
                                     status=False, board=board, image_prepared=True,
                                     program_receipts=a.out/'programs')
            backend = AdoptedImageBackend()
            state.update(image_upload_bytes_written_this_attempt=0,
                         image_bytes_reused_from_prior_run=len(images[0]),
                         image_readback_reused_from_prior_run=True,
                         status='WARM_REPEAT_INFERENCE_RUNNING')
            save()
            return backend

        def token(token_id):
            state['actual_token_ids'].append(int(token_id))
            save()

        engine = Engine(load_spec(a.model), load_weights(a.model), cap=oracle['context_capacity'],
                        cfg=cfg, backend=physical_backend, rows=1, pipeline=False,
                        wformat='int8', resident=False, prog_cache=False)
        got = engine.generate(oracle['prompt_token_ids'],
                              max_new=len(oracle['expected_token_ids']), on_token=token)
        assert got == oracle['expected_token_ids'], 'Warm-repeat tokens differ from exact ISA'
        transport.guard()
        assert calibration_snapshot(transport) == before, 'Calibration changed'
        state['ecc_after'] = transport.ecc_state()
        for ch, row in state['ecc_after'].items():
            assert row['ecc_sec_errors'] == 0 and row['ecc_ded_errors'] == 0, \
                f'ECC not clean after run on {ch}'
        state.update(status='PASS_WARM_REPEAT_PHYSICAL_JTAG_TINYSTORIES_EXACT_ISA_TOKENS',
                     calibration_unchanged=True, image_not_rewritten=True)
        print(state['status'], flush=True)
    except BaseException as error:
        state.update(status='FAIL_WARM_REPEAT_JTAG_TEST', error=repr(error))
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
            state.update(status='FAIL_WARM_REPEAT_CLEANUP', cleanup_errors=errors)
        save()
        if errors and not original_error:
            raise RuntimeError('Warm-repeat cleanup failed; see preserved receipt')


if __name__ == '__main__':
    main()
