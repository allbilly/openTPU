#!/usr/bin/env python3
"""Inspect hard-cell timing coverage in the actual himbaechel v6 chip database.

Packed structures/relative pointers follow himbaechel/chipdb.h and relptr.h.
This read-only audit does not invent timing data for missing cells.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct

REQUIRED = ('DSP48E1_DSP48E1', 'OSERDESE2_OSERDESE2',
            'ISERDESE2_ISERDESE2', 'MMCME2_ADV_MMCME2_ADV')


def inspect(chipdb, constids):
    chipdb, constids = Path(chipdb), Path(constids)
    data = chipdb.read_bytes()
    def word(offset, signed=False):
        return struct.unpack_from('<i' if signed else '<I',data,offset)[0]
    def pointer(offset):
        target = offset+word(offset,True)
        if not 0 <= target < len(data):
            raise ValueError('Invalid chipdb relative pointer')
        return target
    def array(offset,stride):
        start,length = pointer(offset),word(offset+4)
        if start+length*stride > len(data):
            raise ValueError('Invalid chipdb array bounds')
        return [start+i*stride for i in range(length)]
    def string(offset):
        return data[offset:data.index(b'\0',offset)].decode()

    header = pointer(0)
    if word(header) != 0x00ca7ca7 or word(header+4) != 6:
        raise ValueError('Audit supports only the checked himbaechel v6 chipdb layout')
    names = ['']+re.findall(r'^X\(([^)]+)\)',constids.read_text(),re.M)
    extra = pointer(header+76)
    if word(extra) != len(names):
        raise ValueError('Source constids do not match this chipdb')
    names += [string(pointer(p)) for p in array(extra+4,4)]
    grades = []
    for grade in array(header+68,32):
        variants = []
        for cell in array(grade+20,12):
            pins = []
            for pin in array(cell+4,24):
                pins.append(dict(name=names[word(pin)],flags=word(pin+4),
                                 combinational_arcs=len(array(pin+8,20)),
                                 register_arcs=len(array(pin+16,56))))
            variants.append(dict(type=names[word(cell)],pins=pins))
        present = {v['type'] for v in variants}
        grades.append(dict(name=names[word(grade)],variants=variants,
                           missing_required=[n for n in REQUIRED if n not in present]))
    missing = sorted({n for grade in grades for n in grade['missing_required']})
    return dict(status='INCOMPLETE_HARD_CELL_TIMING' if missing else 'REQUIRED_VARIANTS_PRESENT_ARCS_NOT_QUALIFIED',
                device=string(pointer(header+20)),version=6,
                chipdb=str(chipdb.resolve()),chipdb_sha256=hashlib.sha256(data).hexdigest(),
                constids=str(constids.resolve()),constids_sha256=hashlib.sha256(constids.read_bytes()).hexdigest(),
                grades=grades,missing=missing,
                note='Missing cell variants are ignored by the default timing lookup. Absence of MMCM arcs also prevents clock-family relationship tracing. Variant presence alone does not qualify register/parameter-dependent arcs or DDR phase margins.')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chipdb',type=Path,required=True)
    ap.add_argument('--constids',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args = ap.parse_args()
    if args.output.exists():
        ap.error('Use a new audit output path')
    report = inspect(args.chipdb,args.constids)
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(report['status']+': '+', '.join(report['missing']))


if __name__=='__main__':
    main()
