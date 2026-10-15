#!/usr/bin/env python3
"""Audit DSP callbacks on the complete unchanged OpenTPU packed design."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_packed_dsp_inventory import cells


def reference(data, inventory):
    model_by_cell = {name:i for i,c in enumerate(data['configurations'])for name in c['full_design_cells']}
    if len(model_by_cell)!=717:raise ValueError('Full named DSP model scope changed')
    packed=Path(inventory['packed_netlist']['path'])
    if describe(packed)!=inventory['packed_netlist']:raise ValueError('Independent packed netlist changed')
    portsets={}
    for name,cell in cells(packed):
        if cell['type']=='DSP48E1_DSP48E1':portsets[name]=cell['port_directions']
    if set(portsets)!=set(model_by_cell):raise ValueError('Independent packed DSP names differ')
    models=[]
    for c in data['configurations']:
        arcs={tuple(a[:3]):tuple(a[3:7])for a in c['arcs']}
        reg_in,reg_out=set(c['registered_inputs']),set(c['registered_outputs'])
        comb_out={k[2]for k in arcs if k[0]=='comb'}
        types={};seq={}
        for pin in data['pin_map'].values():
            name=pin['packed']
            if name=='CLK':cls='clock_input'
            elif name in reg_in:cls='register_input'
            elif name in reg_out:cls='register_output'
            elif pin['direction']=='input':cls='comb_input'
            elif name in comb_out:cls='comb_output'
            else:cls='ignore'
            types[name]=(cls,int(name in reg_in or name in reg_out))
            if name in reg_in:
                s,h=arcs[('setup','CLK',name)],arcs[('hold','CLK',name)]
                seq[name]=('CLK',c['clock_edge'],min(s[0],s[2]),max(s[1],s[3]),min(h[0],h[2]),max(h[1],h[3]),0,0,0,0)
            elif name in reg_out:seq[name]=('CLK',c['clock_edge'],0,0,0,0,*arcs[('clkq','CLK',name)])
        models.append({'ports':types,'sequential':seq,'comb':{k[1:]:v for k,v in arcs.items()if k[0]=='comb'}})
    return model_by_cell,portsets,models


def compare(audit,data,inventory):
    ids,portsets,models=reference(data,inventory)
    seen_cells=set();totals=Counter();distribution=Counter();cache={};current=None;seen={}
    def expected(cell):
        model=models[ids[cell]];present=portsets[cell]
        key=(ids[cell],tuple(sorted(present)))
        if key not in cache:
            cache[key]={
                'P':{pin:model['ports'][pin]for pin in present},
                'R':{pin:values for pin,values in model['sequential'].items()if pin in present},
                'C':{pair:values for pair,values in model['comb'].items()if pair[0]in present and pair[1]in present},
            }
        return cache[key]
    def finish():
        if current is None:return
        exp=expected(current)
        for tag in ['P','R','C']:
            if seen[tag]!=set(exp[tag]):
                raise ValueError(f'Full DSP {current}: incomplete {tag} callback coverage')
    with audit.open()as stream:
        for line in stream:
            fields=line.rstrip('\n').split('\t');tag,cell=fields[:2]
            if tag=='M':
                finish()
                if cell not in ids or cell in seen_cells or int(fields[2])!=ids[cell]:raise ValueError('Full DSP model assignment differs')
                current=cell;seen_cells.add(cell);distribution[ids[cell]]+=1;seen={'P':set(),'R':set(),'C':set()};continue
            if cell!=current:raise ValueError('Native audit cell records are not contiguous')
            if tag=='P':key,value=fields[2],(fields[3],int(fields[4]))
            elif tag=='R':key,value=fields[2],(fields[3],fields[4],*map(int,fields[5:]))
            elif tag=='C':key,value=(fields[2],fields[3]),tuple(map(int,fields[4:]))
            else:raise ValueError('Unknown full native audit record')
            if key in seen[tag] or expected(cell)[tag].get(key)!=value:
                raise ValueError(f'Full DSP callback mismatch: {cell} {tag} {key!r}')
            seen[tag].add(key);totals[tag]+=1
    finish()
    if seen_cells!=set(ids):raise ValueError('Full named DSP audit did not cover all 717 cells')
    return {'dsp_cells':717,'effective_configurations':len(distribution),'model_distribution':dict(distribution),
            'port_classifications':totals['P'],'sequential_pins':totals['R'],'combinational_arcs':totals['C'],'mismatches':0}


def check(backend,gate,tables,inventory,source,out):
    b=json.loads(backend.read_text());g=json.loads(gate.read_text());t=json.loads((tables/'manifest.json').read_text());inv=json.loads(inventory.read_text())
    if b['status']!='DSP_TIMING_BACKEND_BUILD_PASS_NATIVE_CALLBACK_VALIDATION_PENDING' or g['status']!='ALL_DSP_CONFIGURATION_NATIVE_CALLBACKS_PASS_WHOLE_PHY_AND_VIVADO_PATH_TIMING_PENDING':
        raise ValueError('Effective DSP backend and callback gates are not ready')
    binary=Path(b['binary']['path']);data_path=tables/'dsp-timing-tables.json'
    if describe(binary)!=b['binary']or describe(data_path)!=t['output']:raise ValueError('Backend or table changed')
    data=json.loads(data_path.read_text())
    if data.get('mode_scope')!='ACTUAL_EFFECTIVE_PACKED_HARDWARE_PARAMETERS'or len(data['configurations'])!=19:raise ValueError('Actual packed DSP mode scope changed')
    previous=json.loads(Path(inv['pack_manifest']['path']).read_text())
    for name in ['constrained.json','openxc7.xdc']:
        if describe(source/name)!=previous['inputs'][name]:raise ValueError('Full design input changed')
    out.mkdir(parents=True,exist_ok=False)
    audit=out/'full-dsp-callbacks.tsv'
    argv=[str(binary),'--chipdb',expand_paths('@WORKSPACE@/tiny-gpu/build/ypcb/nextpnr-build/himbaechel/uarch/xilinx/chipdb-xc7k480t.bin'),
          '--device','xc7k480tffg1156-2','--json',str(source/'constrained.json'),'-o','xdc='+str(source/'openxc7.xdc'),
          '--pack-only','--threads','8','--freq','100.0','--seed','1','-o','dsp-vivado-timing=on','-o','dsp-timing-audit='+str(audit)]
    manifest={'status':'RUNNING','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'COMPLETE_UNCHANGED_OPEN_TPU_717_DSP_CALLBACKS_NOT_WHOLE_PHY_TIMING_OR_ROUTE_QUALIFICATION',
              'profile':previous['profile'],'backend':describe(backend),'binary':describe(binary),'gate':describe(gate),'tables':describe(data_path),
              'packed_inventory':describe(inventory),'full_inputs':previous['inputs'],'command':argv,'helper':describe(__file__),
              'live_full_route_changed':False,'numerical_timing':'NOT_QUALIFIED','hardware_accessed':False}
    def save(**fields):
        manifest.update(fields);(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        save(stage='full-native-pack-and-audit');(out/'command.json').write_text(json.dumps(argv,indent=2)+'\n');print('FULL_NATIVE_DSP_AUDIT_STARTED '+str(out),flush=True)
        with(out/'pack.log').open('w')as log:
            child=subprocess.Popen(argv,cwd=out,stdout=log,stderr=subprocess.STDOUT);save(native_pid=child.pid);code=child.wait()
        (out/'pack.exit').write_text(str(code)+'\n');save(native_exit=code)
        if code:raise RuntimeError('Complete native DSP callback audit failed')
        save(stage='compare-vendor-callbacks');result=compare(audit,data,inv)
        shutil.copy2(__file__,out/'helper.py')
        save(status='COMPLETE_717_DSP_NATIVE_CALLBACKS_PASS_WHOLE_PHY_PATH_TIMING_AND_ROUTE_PENDING',
             completed_utc=datetime.now(timezone.utc).isoformat(),comparison=result,audit=describe(audit))
        print(json.dumps({'status':manifest['status'],'comparison':result}),flush=True)
    except Exception as exc:
        save(status='FAIL',error=repr(exc));shutil.copy2(__file__,out/'helper.py');raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['backend','gate','tables','inventory','source','out']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();check(args.backend.resolve(),args.gate.resolve(),args.tables.resolve(),args.inventory.resolve(),args.source.resolve(),args.out.resolve())


if __name__=='__main__':main()
