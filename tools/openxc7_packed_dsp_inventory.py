#!/usr/bin/env python3
"""Stream a complete packed nextpnr netlist and compare its actual DSP modes."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path
import re

from fedora_openxc7 import describe, digest
from openxc7_dsp_timing_tables import parameter


def cells(path):
    decoder = json.JSONDecoder()
    with path.open() as stream:
        buffer = ''
        while True:
            chunk = stream.read(65536)
            if not chunk: raise ValueError('Packed module cells were not found in the prefix')
            buffer += chunk
            match = re.search(r'"cells"\s*:\s*\{', buffer)
            if match: break
            if len(buffer) > 1024*1024 or not buffer:
                raise ValueError('Packed module cells were not found in the prefix')
        position = match.end()
        def space():
            nonlocal buffer, position
            while True:
                while position < len(buffer) and buffer[position].isspace(): position += 1
                if position < len(buffer): return
                chunk = stream.read(65536)
                if not chunk: raise ValueError('Truncated packed cell object')
                buffer += chunk
        def decode():
            nonlocal buffer, position
            while True:
                try:
                    value, end = decoder.raw_decode(buffer, position)
                    position = end; return value
                except json.JSONDecodeError:
                    chunk = stream.read(65536)
                    if not chunk or len(buffer)-position > 16*1024*1024:
                        raise ValueError('Invalid or unexpectedly large packed cell record')
                    buffer += chunk
        while True:
            if position > 65536: buffer, position = buffer[position:], 0
            space()
            if buffer[position] == '}': return
            name = decode(); space()
            if not isinstance(name,str) or buffer[position] != ':': raise ValueError('Invalid packed cell key')
            position += 1; space(); value = decode()
            if not isinstance(value,dict): raise ValueError('Invalid packed cell payload')
            yield name, value
            space()
            if buffer[position] == '}': return
            if buffer[position] != ',': raise ValueError('Invalid packed cell separator')
            position += 1


def typed(raw, expected):
    if expected['kind'] == 'string':
        if not isinstance(raw,str): raise ValueError('Invalid string DSP parameter')
        return {'kind':'string','value':raw}
    if isinstance(raw,int) and not isinstance(raw,bool): return {'kind':'integer','value':raw}
    if not isinstance(raw,str) or not raw or set(raw)-{'0','1'}:
        raise ValueError('Undefined or nonbinary DSP parameter')
    return {'kind':'integer','value':int(raw,2)}


def inventory(pack_manifest, source_inventory, out):
    pm = json.loads(pack_manifest.read_text()); before = json.loads(source_inventory.read_text())
    if pm['status'] != 'FULL_PACK_EXPORT_PASS_DSP_PROFILE_INVENTORY_PENDING' or pm['native_exit'] != 0:
        raise ValueError('Complete native packing did not succeed')
    if before['dsp_count'] != 717: raise ValueError('Full source DSP count changed')
    defaults = {n:parameter(v) for n,v in before['vendor_defaults_raw'].items()}
    source = {c['name']:{**defaults,**{n:parameter(v) for n,v in c['parameters_raw'].items()}} for c in before['cells']}
    packed = Path(pm['output']); rows, types, changes, extras = [], Counter(), Counter(), Counter()
    declared_profiles, complete_profiles, effective_profiles = defaultdict(list), defaultdict(list), defaultdict(list)
    for name, cell in cells(packed):
        types[cell['type']] += 1
        if cell['type'] != 'DSP48E1_DSP48E1': continue
        if name not in source: raise ValueError('Packed DSP cell was not in the full source inventory: '+name)
        raw = cell['parameters']; actual = {n:typed(raw[n],d) if n in raw else d for n,d in defaults.items()}
        delta = {n:{'source':source[name][n], 'packed':actual[n]} for n in actual if actual[n]!=source[name][n]}
        extra = {n:v for n,v in raw.items() if n not in defaults}
        effective = {n:dict(value) for n,value in actual.items()}
        for param, value in extra.items():
            match = re.fullmatch(r'IS_(ALUMODE|INMODE|OPMODE)\[(\d+)\]_INVERTED',param)
            if not match: raise ValueError('Unsupported extra packed DSP parameter: '+param)
            bus, bit = match.group(1), int(match.group(2))
            if bit >= {'ALUMODE':4,'INMODE':5,'OPMODE':7}[bus]:
                raise ValueError('Packed DSP inversion bit exceeds bus width')
            flag = typed(value,{'kind':'integer','value':0})['value']
            if flag not in (0,1): raise ValueError('Nonboolean packed DSP inversion flag')
            if flag: effective['IS_'+bus+'_INVERTED']['value'] |= 1<<bit
        changes.update(delta.keys()); extras.update(extra.keys())
        row = {'name':name,'parameters_raw':raw,'declared_parameters':actual,'declared_changes':delta,
               'effective_vendor_parameters':effective,
               'extra_packer_parameters':extra,
               'constant_ground_pins':cell.get('attributes',{}).get('DSP_GND_PINS',''),
               'constant_vcc_pins':cell.get('attributes',{}).get('DSP_VCC_PINS','')}
        rows.append(row)
        declared_profiles[json.dumps(actual,sort_keys=True,separators=(',',':'))].append(name)
        complete_profiles[json.dumps(raw,sort_keys=True,separators=(',',':'))].append(name)
        effective_profiles[json.dumps(effective,sort_keys=True,separators=(',',':'))].append(name)
    names = [r['name'] for r in rows]
    if len(rows)!=717 or len(set(names))!=717 or set(names)!=set(source):
        raise ValueError('Complete named DSP inventory differs from source')
    out.mkdir(parents=True,exist_ok=False)
    result = {'status':'COMPLETE_PACKED_DSP_PARAMETERS_RECORDED_NOT_TIMING_QUALIFICATION',
              'observed_utc':datetime.now(timezone.utc).isoformat(),'scope':pm['scope'],'profile':pm['profile'],
              'pack_manifest':describe(pack_manifest),'packed_netlist':describe(packed),
              'source_inventory':describe(source_inventory),'helper':describe(__file__),
              'packed_cell_types':dict(types),'dsp_count':len(rows),
              'declared_parameter_profile_count':len(declared_profiles),
              'complete_packed_parameter_profile_count':len(complete_profiles),
              'effective_vendor_parameter_profile_count':len(effective_profiles),
              'effective_parameter_rule':'FASM writer ORs the declared ALUMODE/INMODE/OPMODE inversion masks with per-bit packer flags',
              'fasm_writer':describe(Path(pm['binary']['path']).parent/'source/himbaechel/uarch/xilinx/fasm.cc'),
              'cells_with_declared_changes':sum(bool(r['declared_changes']) for r in rows),
              'changed_declared_parameters':dict(changes),'extra_packer_parameters':dict(extras),
              'declared_profiles':[{'parameters':json.loads(k),'cells':v} for k,v in declared_profiles.items()],
              'effective_profiles':[{'parameters':json.loads(k),'cells':v} for k,v in effective_profiles.items()],
              'cells':rows,'numerical_timing':'NOT_QUALIFIED','live_full_jobs_changed':False,'hardware_accessed':False}
    (out/'inventory.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ['status','dsp_count','declared_parameter_profile_count',
                                          'complete_packed_parameter_profile_count','cells_with_declared_changes',
                                          'effective_vendor_parameter_profile_count',
                                          'changed_declared_parameters','extra_packer_parameters']},indent=2))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('pack-manifest','source-inventory','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();inventory(args.pack_manifest.resolve(),args.source_inventory.resolve(),args.out.resolve())


if __name__=='__main__':main()
