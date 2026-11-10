#!/usr/bin/env python3
"""Build a fresh TinyStories ISA oracle bound to the reviewed c0182902 package.

This is an offline model/ISA run. Its package-derived configuration is not a
physical identity receipt and does not qualify DDR or authorize programming.
"""
import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import importlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host-tree', type=Path, required=True)
    parser.add_argument('--package', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--tokenizer-path', type=Path)
    args = parser.parse_args()

    host = args.host_tree.resolve()
    sys.path[:0] = [str(host), str(host/'tools'), str(ROOT/'tools')]
    if args.tokenizer_path:
        sys.path.insert(0, str(args.tokenizer_path.resolve()))
    import numpy as np
    import sentencepiece as spm

    host_record = json.loads((host/'host-preparation.json').read_text())
    assert host_record['build_id'] == 'c0182902'
    assert host_record['host_interfaces'] == ['pcie', 'jtag']
    assert host_record['program_readback_required'] is True
    for name, expected in host_record['generated_sources'].items():
        assert sha(host/name) == expected, 'Frozen c0182902 host source changed: '+name

    image_host = importlib.import_module('opentpu.host.spare_c0182902')
    assert Path(image_host.__file__).resolve().is_relative_to(host), 'Imported another image profile'
    profile = image_host.SpareC0182902Profile(args.package)
    assert profile.data['build_id_register'] == '0xc0182902'
    assert profile.data['host']['interfaces'] == ['pcie', 'jtag']
    assert profile.data['compute'] == dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2,
                                           MXU_IMPL=2, CORE_KHZ=133333, DDR_MTS=1066)
    core_profile = json.loads((profile.core/'variant-profile.json').read_text())
    assert core_profile['parameters'] == dict(CORE_KHZ=133333, DDR_MTS=1066)
    assert core_profile['physical_databits'] == [64, 72]
    assert core_profile['ecc_channels'] == [1]
    assert core_profile['ch0_physical_lanes'] == [0, 1, 2, 3, 4, 5, 8, 7]

    from opentpu import isa
    from opentpu.isasim import board_config
    from opentpu.llm import load_spec
    from opentpu.llm.qwen3 import Engine, IsaBackend, emulated_logits, load_weights

    # These fields are the image's reviewed design configuration, not values
    # read from a physical card. The offline ISA memory is capped at 128 MiB.
    cfg = board_config(S=1, D=128, MCOLS=4, ACT_BLOCKS=128, TMEM_WORDS=65536,
                       IMEM_WORDS=32768, LANES=8, DRAM_BYTES=1 << 27,
                       PAIR=True, DSTEP=True, STREAM=True, ACT_ROWS=0, SEQ_WC=True)
    expected_config = dict(S=1, D=128, MCOLS=4, ACT_BLOCKS=128, TMEM_WORDS=65536,
                           DRAM_BYTES=1 << 27, IMEM_WORDS=32768, LANES=8, PAIR=True,
                           DSTEP=True, STREAM=True, ACT_ROWS=0, SEQ_WC=True)
    assert {k: v for k, v in asdict(cfg).items() if k in expected_config} == expected_config

    args.out.mkdir(parents=True, exist_ok=False)
    state = dict(status='TRAINED_SMALL_MODEL_ISA_CHECK_RUNNING', hardware_accessed=False,
                 flash_written=False, programming_performed=False, target_build_id='c0182902',
                 programs=[], target_bitstream_sha256=profile.bitstream_sha256,
                 target_package_manifest_sha256=profile.manifest_sha256,
                 oracle_identity_source='reviewed c0182902 package/configuration; no physical identity asserted')
    started = time.monotonic()

    def save():
        state['utc'] = datetime.now(timezone.utc).isoformat()
        state['elapsed_seconds'] = round(time.monotonic()-started, 3)
        temporary = args.out/'manifest.json.tmp'
        temporary.write_text(json.dumps(state, indent=2)+'\n')
        temporary.replace(args.out/'manifest.json')

    class RecordedIsa(IsaBackend):
        def __init__(self, selected_cfg, images):
            state['upload_image_bytes'] = [len(image) for image in images]
            state['upload_image_sha256'] = [hashlib.sha256(image.tobytes()).hexdigest()
                                            for image in images]
            super().__init__(selected_cfg, images, adopt=True)

        def run(self, programs, args=None):
            descriptions = []
            for program in programs:
                words = isa.assemble(program)
                assert len(words) <= cfg.IMEM_WORDS, 'Program exceeds c0182902 IMEM'
                descriptions.append(dict(instructions=len(program), words=len(words),
                                         sha256=hashlib.sha256(words.tobytes()).hexdigest()))
            result = super().run(programs, args)
            state['programs'].append(dict(slices=descriptions, result=result))
            save()
            return result

    try:
        conversion = args.model/'conversion.json'
        conversion_data = json.loads(conversion.read_text())
        assert conversion_data['status'] == 'PASS_TRAINED_TINYSTORIES_TILE_PADDING_FP32_REFERENCE'
        for item in conversion_data['files']:
            assert sha(item['path']) == item['sha256']
        spec = load_spec(args.model)
        spec.check(cfg)
        source_names = (
            'opentpu/llm/llama.py', 'opentpu/llm/qwen3.py', 'opentpu/compiler.py',
            'opentpu/isa.py', 'opentpu/isasim.py', 'opentpu/fp32.py', 'opentpu/quant.py',
            'tools/check_tinystories_c0182902_model.py',
        )
        source_hashes = {}
        for name in source_names:
            source = host/name if (host/name).is_file() else ROOT/name
            source_hashes[name] = sha(source)
        state.update(model=str(args.model.resolve()), conversion_sha256=sha(conversion),
                     package_manifest_sha256=profile.manifest_sha256,
                     host_preparation_sha256=sha(host/'host-preparation.json'),
                     config=asdict(cfg), model_spec=asdict(spec),
                     model_sha256=sha(args.model/'model.safetensors'),
                     model_config_sha256=sha(args.model/'config.json'), source_hashes=source_hashes,
                     limitations=['ISA DRAM is capped at 128 MiB; arithmetic, TMEM and IMEM match the reviewed c0182902 configuration.',
                                  'FP32 conversion equivalence and int8 arithmetic are separate checks.',
                                  'No physical identity, DDR operation, JTAG upload, FPGA execution or bandwidth result.'])
        save()
        tokenizer = spm.SentencePieceProcessor(model_file=str(args.model/'tokenizer.model'))
        prompt = 'Once upon a time'
        tokens = [spec.bos] + tokenizer.encode(prompt)
        weights = load_weights(args.model)
        engine = Engine(spec, weights, cap=128, cfg=cfg, backend=RecordedIsa,
                        rows=1, pipeline=False, wformat='int8', resident=False, prog_cache=False)
        reference = emulated_logits(spec, weights, tokens)
        actual = np.array([engine.step(token) for token in tokens])
        cosine = ((actual*reference).sum(-1) / np.linalg.norm(actual, axis=-1) /
                  np.linalg.norm(reference, axis=-1))
        assert np.isfinite(actual).all() and float(cosine.min()) > 0.9995, cosine.tolist()
        state.update(int8_emulation_min_logit_cosine=float(cosine.min()), prompt=prompt,
                     prompt_token_ids=tokens, context_capacity=128, quantization='int8',
                     prompt_logits_sha256=hashlib.sha256(actual.tobytes()).hexdigest())
        logits = actual[-1]
        generated = []
        for _ in range(8):
            token = int(logits.argmax())
            generated.append(token)
            state['expected_token_ids'] = generated
            save()
            if token in spec.eos:
                break
            logits = engine.step(token)
        state.update(status='PASS_TRAINED_TINYSTORIES_INT8_ISA_ORACLE_PHYSICAL_PENDING',
                     decoded=tokenizer.decode(tokens[1:]+generated), physical_token_comparison_pending=True,
                     image_bytes=engine.image.nbytes)
        print(json.dumps({k: state[k] for k in
                          ('status', 'target_bitstream_sha256', 'expected_token_ids', 'decoded')}), flush=True)
    except BaseException as error:
        state.update(status='FAIL_C0182902_TINYSTORIES_ISA_CHECK', error=repr(error))
        raise
    finally:
        save()


if __name__ == '__main__':
    main()
