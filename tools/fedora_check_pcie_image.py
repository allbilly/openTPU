#!/usr/bin/env python3
"""Check full PCIe image provenance, features and every configuration frame."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import re
import struct

from fedora_openxc7 import PART, ROOT, describe, digest
from fedora_openxc7_pcie_pipeline import FULL, TOP, recorded, require, unchanged

STRUCTURE_CHECKER = ROOT.parent / 'bonetto-soc/scripts/fedora-check-bitstream.py'


def parse_bitstream(data):
    spec = importlib.util.spec_from_file_location('ypcb_bit_structure', STRUCTURE_CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.parse_bitstream(data)


def ecc(words):
    value = 0
    for index,word in enumerate(words):
        if index == 50:
            word &= 0xffffe000
        base = index * 32 + (0x1360 if index > 37 else 0x1340 if index > 6 else 0x1320)
        while word:
            bit = word & -word
            value ^= base + bit.bit_length() - 1
            word ^= bit
    value ^= (value & 0xfff).bit_count() % 2 << 12
    return value & 0x1fff


def legal_frames(part):
    addresses = set()
    buses = {'CLB_IO_CLK':0, 'BLOCK_RAM':1, 'CFG_CLB':2}
    for half,region in part['global_clock_regions'].items():
        require(half in ('top','bottom'), 'Unknown configuration half')
        for row,config in region['rows'].items():
            for kind,bus in config['configuration_buses'].items():
                require(kind in buses, 'Unknown configuration bus')
                for column,description in bus['configuration_columns'].items():
                    base = (buses[kind] << 23 | (half == 'bottom') << 22 |
                            int(row) << 17 | int(column) << 7)
                    addresses.update(base+minor for minor in range(description['frame_count']))
    require(addresses, 'Empty legal frame table')
    return addresses


def compare_frames(bit, frames_path, part_path):
    """Independent payload/ECC comparison; accepts any exact-part donor image."""
    data = Path(bit).read_bytes()
    parsed = parse_bitstream(data)
    part = json.loads(Path(part_path).read_text())
    allowed = legal_frames(part)
    frames = {}
    with Path(frames_path).open() as source:
        for line in source:
            address,text = line.split()
            address = int(address,16)
            words = [int(word,16) for word in text.split(',')]
            require(address in allowed and address not in frames, 'Illegal or duplicate frame address')
            require(len(words) == 101 and all(0 <= word <= 0xffffffff for word in words),
                    'Incorrect configuration frame size/word')
            frames[address] = words
    require(frames, 'Empty strict frames')
    implicit = len(allowed-frames.keys())
    payload = memoryview(data)[parsed['payload_offset']:]
    fdri = [p for p in parsed['packets'] if p['opcode'] == 2 and p['register'] == 2 and p['words']]
    far = [p for p in parsed['packets'] if p['opcode'] == 2 and p['register'] == 1 and p['words']]
    require(len(fdri) == 1 and far and far[0]['words'] == 1, 'Unexpected frame packet layout')
    require(struct.unpack_from('>I',payload,far[0]['data_offset'])[0] == min(allowed),
            'Wrong initial frame address')
    packet = fdri[0]
    cursor = packet['data_offset']
    end = cursor + packet['words']*4
    frame_struct = struct.Struct('>101I')
    addresses = sorted(allowed)
    padding = 0
    for index,address in enumerate(addresses):
        require(cursor+404 <= end, 'Truncated frame payload')
        expected = list(frames.get(address, [0]*101))
        expected[50] = expected[50] & 0xffffe000 | ecc(expected)
        actual = frame_struct.unpack_from(payload,cursor)
        require(actual == tuple(expected), f'Frame payload or ECC mismatch: {address:08x}')
        cursor += 404
        last_row = index == len(addresses)-1 or address >> 17 != addresses[index+1] >> 17
        if last_row:
            require(cursor+808 <= end and bytes(payload[cursor:cursor+808]) == bytes(808),
                    'Incorrect configuration row padding')
            cursor += 808
            padding += 2
    require(cursor == end, 'Unexpected trailing frame payload')
    return dict(status='ALL_LEGAL_FRAME_DATA_AND_ECC_MATCH', frames_compared=len(allowed),
                explicit_frames=len(frames), implicit_zero_frames=implicit,
                padding_frames=padding, frame_payload_words=packet['words'],
                structure=parsed, crc='NOT_CHECKED')


def pcie_features(path):
    text = Path(path).read_text()
    require(not re.search(r'\.BSCAN\.JTAG_CHAIN_[1-4]\b',text),
            'Standalone mailbox feature found in PCIe image')
    pcie = set(re.findall(r'^([A-Za-z0-9_]+)\.PCIE\.',text,re.M))
    gtx = set(re.findall(r'^([A-Za-z0-9_]+)\.GTXE2_CHANNEL\.',text,re.M))
    require(len(pcie) == len(gtx) == 1, 'PCIe/GTX configuration features missing or duplicated')
    tile = next(iter(pcie))
    for name,width,value in [('BAR0',32,0xfffff000),('LINK_CAP_MAX_LINK_SPEED',4,2),
                            ('LINK_CAP_MAX_LINK_WIDTH',6,1)]:
        pattern = (r'^'+re.escape(tile+'.PCIE.'+name)+r'\['+str(width-1)+r':0\] = '+
                   str(width)+r"'b([01]{"+str(width)+r'})$')
        matches = re.findall(pattern,text,re.M)
        require(len(matches) == 1 and int(matches[0],2) == value,
                'PCIe FASM setting differs: '+name)
    return dict(status='GEN2_X1_4K_BAR_AND_GTX_FEATURES_PASS',pcie_tile=tile,gtx_tile=next(iter(gtx)))


def check(pipeline):
    pipeline = Path(pipeline).resolve()
    directory = pipeline.parent
    info = json.loads(pipeline.read_text())
    require(info.get('status') == 'FULL_PCIE_CONFIGURATION_ASSEMBLY_PASS_TIMING_NOT_QUALIFIED',
            'Full PCIe configuration assembly has not completed')
    require(info.get('configuration') == FULL and info.get('top') == TOP and info.get('part') == PART,
            'Wrong full image profile')
    unchanged(info['planned_inputs'])
    for name in ('design.bit','design.frames'):
        item = info['artifacts'][name]
        require(Path(item['path']).resolve() == directory/name, 'Wrong assembly artifact path')
        recorded(item)
    recorded(info['route_manifest'])
    route_path = Path(info['route_manifest']['path'])
    require(route_path == directory/'route/manifest.json', 'Wrong route manifest path')
    route = json.loads(route_path.read_text())
    require(route.get('status') == 'FULL_PCIE_ROUTE_PASS_TIMING_NOT_QUALIFIED' and
            route.get('configuration') == FULL and route.get('top') == TOP, 'Full PCIe route did not pass')
    for item in route['artifacts'].values():
        recorded(item)
    features = pcie_features(directory/'route/design.fasm')
    comparison = compare_frames(directory/'design.bit',directory/'design.frames',
                                Path(info['database'])/PART/'part.json')
    require(comparison['structure']['header']['a'].split(';',1)[0] == str(directory/'design.frames'),
            'Bitstream header refers to different frames')
    return dict(status='FULL_PCIE_IMAGE_PACKET_FRAME_AND_PROVENANCE_PASS_TIMING_NOT_QUALIFIED',
                pipeline=describe(pipeline),configuration=FULL,top=TOP,features=features,
                frame_comparison=comparison,checker=describe(Path(__file__)),
                structure_checker=describe(STRUCTURE_CHECKER),timing='NOT_QUALIFIED',
                physical_hardware='NOT_RUN',programming='NOT_RUN',flash_written=False)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--pipeline',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args = ap.parse_args()
    require(not args.out.exists(), 'Output report already exists')
    try:
        report = check(args.pipeline)
    except Exception as error:
        report = dict(status='FAIL',error=str(error),timing='NOT_QUALIFIED',physical_hardware='NOT_RUN')
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status'])
    print(args.out)
    return 0 if report['status'].startswith('FULL_PCIE_IMAGE_PACKET_FRAME_AND_PROVENANCE_PASS') else 1


if __name__ == '__main__':
    raise SystemExit(main())
