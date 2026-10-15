#!/usr/bin/env python3
"""Produce a separate CRC-protected image after its upstream offline gates pass.

The live full-image path returns 2 before creating output. Fixture scope is
explicit and cannot establish a complete board image or timing qualification.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import struct
import subprocess
from concurrent.futures import ThreadPoolExecutor

from fedora_openxc7 import describe, digest
from fedora_check_pcie_image import compare_frames

PROFILE = {'MCOLS': 4, 'ACT_ROWS': 4, 'LANES': 8, 'VPU_CL': 2,
           'MXU_IMPL': 2, 'CORE_KHZ': 100000, 'DDR_MTS': 800}
QUALIFIED = 'BOTH_VIVADO_REFERENCE_CRC_PAIRS_MATCH_NATIVE_FIXTURE_CRC_INSERTION_AND_FULL_FRAME_ECC_PRESERVATION_PASS_CORRUPT_COPIES_REJECTED_FULL_NATIVE_ROUTE_PENDING'
FULL_PARENT = 'FULL_DSP_CORRECTED_IMAGE_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED'


def pin(record):
    if describe(record['path']) != record:
        raise ValueError('Pinned image/qualification input changed: ' + record['path'])
    return Path(record['path'])


def prepare(qualification, parent_path, fixture, out):
    parent = None
    if parent_path is not None:
        parent = json.loads(parent_path.read_text())
        if parent['status'] in ('WAITING_FOR_NATIVE_ROUTE_AND_ORIGINAL_OFFLINE_IMAGE', 'RUNNING'):
            print('FULL_DSP_IMAGE_PENDING: CRC output was not created', flush=True)
            return 2
        if (parent['status'] != FULL_PARENT or parent['profile'] != PROFILE
                or parent['corrected_dsp_count'] != 717 or not parent['preserved_parent_vref']
                or parent['hardware_ready'] is not False):
            raise ValueError('Complete full-scope DSP image required before CRC conversion')
    proof = json.loads(qualification.read_text())
    if proof['status'] != QUALIFIED:
        raise ValueError('Native CRC/frame witness and both vendor reference checks required')
    for record in proof['inputs']:
        pin(record)
    for record in proof['records'].values():
        pin(record['source'])
    for record in proof['negative_cases'].values():
        pin(record['input'])
    pin(proof['packet_frame_ecc'])
    checker = next(pin(r) for r in proof['inputs'] if Path(r['path']).name == 'check-crc')
    part = next(pin(r) for r in proof['inputs'] if Path(r['path']).name == 'part.json')
    if fixture:
        bit = pin(proof['records']['native_fixture']['source'])
        frames = next(pin(r) for r in proof['inputs'] if Path(r['path']).name == 'probe.frames')
        inputs = [describe(qualification), describe(bit), describe(frames), describe(part)]
    else:
        bit = pin(parent['artifacts']['design.bit'])
        frames = pin(parent['artifacts']['design.frames'])
        pin(parent['artifacts']['design.fasm'])
        inputs = [describe(qualification), describe(parent_path), *parent['artifacts'].values(),
                  parent['full_source_inventory'], *parent['inputs']]
        for record in inputs:
            pin(record)
        inventory = json.loads(pin(parent['full_source_inventory']).read_text())
        with ThreadPoolExecutor(max_workers=8) as pool:
            if not all(pool.map(lambda pair: digest(pair[0]) == pair[1], inventory.items())):
                raise ValueError('Full parent source/tool/database inventory changed')
    out.mkdir(parents=True, exist_ok=False)
    receipt = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
               'qualification': describe(qualification), 'inputs': inputs,
               'helper': describe(__file__), 'checker': describe(checker),
               'scope': '64_DSP_FIXTURE' if fixture else 'FULL_DSP_CORRECTED_BOARD_IMAGE',
               'profile': None if fixture else PROFILE, 'original_image_changed': False,
               'live_route_changed': False, 'hardware_accessed': False,
               'hardware_ready': False, 'numerical_timing': 'NOT_QUALIFIED'}

    def save(**fields):
        receipt.update(fields)
        (out / 'manifest.json').write_text(json.dumps(receipt, indent=2) + '\n')

    def check(stage, path, expected_exit):
        argv = [str(checker), str(path)]
        (out / (stage + '.command.json')).write_text(json.dumps(argv, indent=2) + '\n')
        result = subprocess.run(argv, capture_output=True, text=True)
        (out / (stage + '.log')).write_text(result.stdout + result.stderr)
        (out / (stage + '.exit')).write_text(str(result.returncode) + '\n')
        if result.returncode != expected_exit:
            raise ValueError(stage + ' CRC checker exit differs from qualified policy')
        return json.loads(result.stdout)

    try:
        save()
        old = check('source-crc', bit, 2)
        resets = old['resets']
        if (old['status'] != 'NO_CRC_CHECKPOINTS_RESET_ONLY' or old['crc_checkpoints'] != 0
                or old['fdri_words'] != 4683168 or len(resets) != 3
                or [r['fdri_words_since_reset'] for r in resets] != [0, 4683168, 0]):
            raise ValueError('Source CRC/reset layout differs from qualified native writer')
        original = bit.read_bytes()
        data = bytearray(original)
        changes = []
        for reset in resets[1:]:
            h, v = reset['header_file_offset'], reset['value_file_offset']
            if (v != h + 4 or struct.unpack_from('>I', data, h)[0] != 0x30008001
                    or struct.unpack_from('>I', data, v)[0] != 7):
                raise ValueError('Unexpected CRC-reset packet at replacement offset')
            struct.pack_into('>I', data, h, 0x30000001)
            struct.pack_into('>I', data, v, reset['computed_crc_before_reset'])
            changes.append({'header_offset': h, 'value_offset': v,
                            'crc': reset['computed_crc_before_reset']})
        changed_bytes = {i for change in changes for i in range(change['header_offset'], change['value_offset'] + 4)}
        if len(data) != len(original) or any(a != b and i not in changed_bytes
                for i, (a, b) in enumerate(zip(original, data))):
            raise ValueError('Bytes outside the four qualified CRC packet words changed')
        result_bit = out / 'design-with-crc.bit'
        result_bit.write_bytes(data)
        verified = check('protected-crc', result_bit, 0)
        if verified['crc_checkpoints'] != 2 or verified['fdri_words'] != old['fdri_words']:
            raise ValueError('Complete two-checkpoint CRC coverage differs')
        payload = compare_frames(result_bit, frames, part)
        if payload['frames_compared'] != 46336 or payload['frame_payload_words'] != old['fdri_words']:
            raise ValueError('Complete packet/frame/ECC coverage differs')
        frame_receipt = out / 'packet-frame-ecc.json'
        frame_receipt.write_text(json.dumps(payload, indent=2) + '\n')
        for record in inputs:
            pin(record)
        save(status=('FIXTURE' if fixture else 'FULL_DSP_CORRECTED_IMAGE') + '_CRC_CHECKPOINTS_PACKET_FRAME_ECC_AND_PROVENANCE_PASS_TIMING_UNQUALIFIED',
             changed_word_pairs=changes, preserved_all_other_bytes=True, crc=verified,
             outputs={p.name: describe(p) for p in (result_bit, frame_receipt)},
             completed_utc=datetime.now(timezone.utc).isoformat())
        (out / 'native.exit').write_text('0\n')
        print(receipt['status'], flush=True)
        return 0
    except Exception as error:
        save(status='FAIL', error=repr(error))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--qualification', type=Path, required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--parent-image', type=Path)
    group.add_argument('--fixture', action='store_true')
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    return prepare(args.qualification.resolve(), args.parent_image.resolve() if args.parent_image else None,
                   args.fixture, args.out.resolve())


if __name__ == '__main__':
    raise SystemExit(main())
