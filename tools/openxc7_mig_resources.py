#!/usr/bin/env python3
"""Audit actual MIG BEL coverage and run minimal backend placement probes."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import struct
import subprocess

REQUIRED = ('PHASER_IN_PHY','PHASER_OUT_PHY','PHASER_REF','PHY_CONTROL','IN_FIFO','OUT_FIFO')


def inspect(chipdb, constids):
    data = chipdb.read_bytes()
    def word(offset,signed=False):
        return struct.unpack_from('<i' if signed else '<I',data,offset)[0]
    def pointer(offset):
        target = offset+word(offset,True)
        if not 0 <= target < len(data):
            raise ValueError('Invalid relative pointer')
        return target
    def array(offset,size):
        start,length = pointer(offset),word(offset+4)
        if start+length*size > len(data):
            raise ValueError('Invalid array bounds')
        return [start+i*size for i in range(length)]
    def string(offset):
        return data[offset:data.index(b'\0',offset)].decode()
    header = pointer(0)
    if word(header) != 0xca7ca7 or word(header+4) != 6:
        raise ValueError('Expected the checked himbaechel v6 layout')
    names = ['']+re.findall(r'^X\(([^)]+)\)',constids.read_text(),re.M)
    extra = pointer(header+76)
    if word(extra) != len(names):
        raise ValueError('Source constids do not match chipdb')
    names += [string(pointer(p)) for p in array(extra+4,4)]
    types,counts = array(header+28,40),Counter()
    for instance in array(header+36,16):
        for bel in array(types[word(instance+4)]+4,36):
            counts[names[word(bel+4)]] += 1
    return dict(scope='ACTUAL_CHIPDB_BEL_TYPES',
                required={name:counts[name] for name in REQUIRED},
                related={name:count for name,count in sorted(counts.items())
                         if any(key in name for key in ('PHASER','PHY_CONTROL','IN_FIFO','OUT_FIFO'))},
                all_bel_counts=dict(sorted(counts.items())))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--chipdb',type=Path,required=True)
    ap.add_argument('--constids',type=Path,required=True)
    ap.add_argument('--backend',type=Path,required=True)
    ap.add_argument('--out',type=Path,required=True)
    ap.add_argument('--threads',type=int,default=8)
    args = ap.parse_args()
    out = args.out.resolve()
    if out.exists():
        ap.error('Choose a fresh output directory')
    out.mkdir(parents=True)
    report = inspect(args.chipdb,args.constids)
    (out/'chipdb-mig-resource-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    results = []
    for kind in REQUIRED:
        p = out/kind
        p.mkdir()
        design = dict(creator='Capability probe; no functional DDR qualification',modules={
            'top':dict(attributes={'top':'1'},ports={},netnames={},cells={
                'probe':dict(type=kind,parameters={},attributes={'keep':'1'},
                             port_directions={},connections={})})})
        (p/'design.json').write_text(json.dumps(design,indent=2)+'\n')
        command = [str(args.backend.resolve()),'--chipdb',str(args.chipdb.resolve()),
                   '--device','xc7k480tffg1156-2','--json',str(p/'design.json'),
                   '--no-route','--threads',str(args.threads),'--write',str(p/'placed.json')]
        (p/'command.json').write_text(json.dumps(command,indent=2)+'\n')
        with (p/'run.log').open('w') as log:
            run = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=60)
        (p/'command.exit').write_text(f'{run.returncode}\n')
        results.append(dict(primitive=kind,exit_code=run.returncode,
                            tail=(p/'run.log').read_text().splitlines()[-12:]))
        print(kind+': exit '+str(run.returncode),flush=True)
    (out/'primitive-probe-results.json').write_text(json.dumps(results,indent=2)+'\n')


if __name__ == '__main__':
    main()
