#!/usr/bin/env python3
"""Characterize every effective packed OpenTPU DSP configuration with Vivado."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe, digest
from openxc7_dsp_timing_tables import raw_arcs


def raw_parameter(name, item, defaults):
    if item['kind']=='string': return json.dumps(item['value'])
    value=item['value']; match=re.fullmatch(r"(\d+)'[01]+",defaults[name])
    if match:
        width=int(match.group(1))
        if not 0<=value<1<<width: raise ValueError('Parameter exceeds declared width')
        return f"{width}'"+format(value,f'0{width}b')
    return str(value)


def verilog(configs):
    ports=configs['ports']; declarations=['    input wire clk']; body=[]
    for config in configs['configurations']:
        name=config['probe_cell']; connections=[]
        for port in ports:
            if port['name']=='CLK': connections.append('    .CLK(clk)'); continue
            width=port['width']; bus=f' [{width-1}:0]'if width>1 else ''
            signed=' signed'if port['signed']else ''
            signal=name+'_'+port['name']
            declarations.append(f"    {port['direction']} wire{signed}{bus} {signal}")
            connections.append(f"    .{port['name']}({signal})")
        params=[]
        for key,raw in sorted(config['parameters_raw'].items()):
            value=re.sub(r"^(\d+)'([01]+)$",r"\1'b\2",raw)
            params.append(f'    .{key}({value})')
        body.append('(* DONT_TOUCH = "TRUE" *) DSP48E1 #(\n'+',\n'.join(params)+'\n) '+name+' (\n'+',\n'.join(connections)+'\n);')
    return 'module dsp_configs(\n'+',\n'.join(declarations)+'\n);\n'+'\n'.join(body)+'\nendmodule\n'


def property_value(name,value,expected):
    if expected['kind']=='string':
        if name=='USE_DPORT'and value in ('0','1'): return 'TRUE'if value=='1'else 'FALSE'
        return value
    match=re.fullmatch(r"(\d+)'([bBhHdDoO])([0-9a-fA-F]+)",value)
    if match:
        width,radix,digits=match.groups();number=int(digits,{'b':2,'h':16,'d':10,'o':8}[radix.lower()])
        if number>=1<<int(width): raise ValueError('Vivado parameter exceeds declared width')
        return number
    return int(value)


def summarize(out,configs):
    props=defaultdict(dict)
    with(out/'cell-properties.tsv').open()as stream:
        next(stream)
        for line in stream:
            cell,key,value=line.rstrip('\n').split('\t',2);props[cell][key]=value
    mismatches=[]
    for config in configs['configurations']:
        cell=config['probe_cell']
        for name,expected in config['effective_vendor_parameters'].items():
            actual=property_value(name,props[cell][name],expected)
            if actual!=expected['value']:mismatches.append({'cell':cell,'parameter':name,'expected':expected['value'],'actual':actual})
    summary={'status':'DSP_CONFIG_PARAMETERS_AND_VENDOR_ARCS_RECORDED_NOT_BACKEND_TIMING_QUALIFICATION',
             'observed_utc':datetime.now(timezone.utc).isoformat(),'complete_configurations':configs['complete_configurations'],
             'full_design_instances':717,'parameter_mismatches':mismatches,'nonfinite_or_non_numeric_delays':[],
             'arc_types':Counter(),'total_arcs':0,'configurations':{},'summary_revision':2,
             'mode_scope':'ACTUAL_EFFECTIVE_PACKED_HARDWARE_PARAMETERS','live_backend_changed':False,'numerical_timing':'NOT_QUALIFIED'}
    pin_sets={}
    for config in configs['configurations']:
        name=config['probe_cell']; p=config['effective_vendor_parameters']
        summary['configurations'][name]={'full_design_instances':len(config['full_design_cells']),
            **{n:p[n]['value']for n in ['PREG','AREG','BREG','MREG']},'arc_types':Counter(),'enabled_arc_types':Counter(),'disabled_arcs':0}
        pin_sets[name]={n:set()for n in ['register_output_pins','combinational_output_pins','registered_input_pins','combinational_input_pins']}
    raw=out/'timing-arcs.tsv';raw_sha=digest(raw)
    with(out/'timing-arcs-compact.json').open('w')as compact:
        header={'source_tsv_sha256':raw_sha,'part':'xc7k480tffg1156-2','units':'ns','timing_qualification':'NOT_QUALIFIED'}
        compact.write(json.dumps(header,separators=(',',':'))[:-1]+',"arcs":[');first=True
        for cell,properties in raw_arcs(raw):
            if cell not in summary['configurations']:raise ValueError('Unexpected characterized DSP cell')
            prefix=cell+'/'
            if not properties['FROM_PIN'].startswith(prefix)or not properties['TO_PIN'].startswith(prefix):raise ValueError('Timing pin belongs to another cell')
            delays={name:float(value)for name,value in properties.items()if name.startswith('DELAY_')}
            if not delays or any(not math.isfinite(v)for v in delays.values()):raise ValueError('Invalid timing delay field')
            if any(properties[n]not in('0','1')for n in ['IS_DISABLED','IS_USER_DISABLED']):raise ValueError('Invalid disabled-arc flag')
            disabled=any(properties[n]=='1'for n in ['IS_DISABLED','IS_USER_DISABLED']);kind=properties['TYPE']
            source,target=properties['FROM_PIN'][len(prefix):],properties['TO_PIN'][len(prefix):]
            arc={'cell':cell,'from':source,'to':target,'type':kind,'transition':properties['TRANSITION'],
                 'sense':properties.get('SENSE',''),'disabled':disabled,'delays_ns':delays}
            if not first:compact.write(',')
            compact.write(json.dumps(arc,separators=(',',':')));first=False
            summary['arc_types'][kind]+=1;summary['total_arcs']+=1;s=summary['configurations'][cell];s['arc_types'][kind]+=1
            if disabled:s['disabled_arcs']+=1;continue
            s['enabled_arc_types'][kind]+=1;sets=pin_sets[cell]
            if kind=='Reg Clk to Q':sets['register_output_pins'].add(target)
            elif kind in('setup','hold'):sets['registered_input_pins'].add(target)
            elif kind=='combinational':sets['combinational_output_pins'].add(target);sets['combinational_input_pins'].add(source)
            else:raise ValueError('Unsupported vendor DSP arc type')
        compact.write(']}\n')
    for name,sets in pin_sets.items():
        if not summary['configurations'][name]['arc_types']:raise ValueError('DSP configuration has no timing arcs')
        summary['configurations'][name].update({key:sorted(value)for key,value in sets.items()})
        summary['configurations'][name]['hybrid_output_pins']=sorted(sets['register_output_pins']&sets['combinational_output_pins'])
        summary['configurations'][name]['hybrid_input_pins']=sorted(sets['registered_input_pins']&sets['combinational_input_pins'])
    (out/'semantic-summary-v2.json').write_text(json.dumps(summary,indent=2)+'\n')
    if mismatches:raise ValueError('Actual Vivado DSP parameters differ from packed modes')
    return summary


def characterize(inventory,template,out):
    packed=json.loads(inventory.read_text());old=json.loads((template/'configurations.json').read_text())
    source=Path(old['source_inventory']);original=json.loads(source.read_text())
    if digest(source)!=old['source_inventory_sha256']or packed['dsp_count']!=717 or packed['effective_vendor_parameter_profile_count']!=19:
        raise ValueError('Full packed/source configuration scope changed')
    groups=sorted(packed['effective_profiles'],key=lambda c:(-len(c['cells']),json.dumps(c['parameters'],sort_keys=True)))
    names=[n for c in groups for n in c['cells']]
    if len(names)!=717 or len(set(names))!=717:raise ValueError('Full named DSP coverage changed')
    configs={'source_inventory':str(source),'source_inventory_sha256':digest(source),'packed_inventory':describe(inventory),
             'source_checkpoint':packed['packed_netlist'],'dsp_total':717,'complete_configurations':19,'ports':old['ports'],
             'mode_scope':'ACTUAL_EFFECTIVE_PACKED_HARDWARE_PARAMETERS','configurations':[]}
    for i,c in enumerate(groups):
        configs['configurations'].append({'probe_cell':f'dsp_{i:02d}','full_design_cells':c['cells'],
            'effective_vendor_parameters':c['parameters'],
            'parameters_raw':{n:raw_parameter(n,v,original['vendor_defaults_raw'])for n,v in c['parameters'].items()}})
    out.mkdir(parents=True,exist_ok=False)
    plan='Characterize all 19 effective hardware DSP configurations from the complete packed OpenTPU netlist, preserving all 717 named DSPs. Resolve bus inversion masks exactly as the existing FASM writer. Compare all 30 parameters against actual Vivado properties and export every timing corner. This constituent query does not replace the full accelerator, change live inputs, qualify whole-board timing or access hardware.\n'
    (out/'plan.md').write_text(plan);(out/'configurations.json').write_text(json.dumps(configs,indent=2)+'\n');(out/'dsp_configs.v').write_text(verilog(configs))
    tcl=(template/'query.tcl').read_text()
    if tcl.count('[llength $cells] != 15')!=1:raise ValueError('Unexpected original query coverage check')
    (out/'query.tcl').write_text(tcl.replace('[llength $cells] != 15','[llength $cells] != 19'))
    argv=[expand_paths('@VIVADO_BIN@/vivado'),'-mode','batch','-nojournal','-nolog','-notrace','-source',str(out/'query.tcl')]
    manifest={'status':'RUNNING','created_utc':datetime.now(timezone.utc).isoformat(),'command':argv,'cwd':str(out),
              'scope':'ALL_EFFECTIVE_PACKED_717_DSP_CONFIGURATIONS_NOT_FULL_ROUTE_OR_TIMING_QUALIFICATION',
              'part':'xc7k480tffg1156-2','threads':8,'complete_configurations':19,'full_design_dsp_count':717,
              'inputs':{name:digest(out/name)for name in ['plan.md','configurations.json','dsp_configs.v','query.tcl']},
              'packed_inventory':describe(inventory),'helper':describe(__file__),'full_job_inputs_changed':False,'hardware_accessed':False,'numerical_timing':'NOT_QUALIFIED'}
    def save(**fields):
        manifest.update(fields);(out/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        save();print('VIVADO_QUERY_STARTED '+str(out),flush=True)
        with(out/'query.log').open('w')as log:
            child=subprocess.Popen(argv,cwd=out,stdout=log,stderr=subprocess.STDOUT);save(native_pid=child.pid);code=child.wait()
        (out/'query.exit').write_text(str(code)+'\n');save(native_exit=code)
        if code:raise RuntimeError('Native Vivado query failed')
        summary=summarize(out,configs);shutil.copy2(__file__,out/'helper.py')
        save(status='ALL_EFFECTIVE_PACKED_DSP_CONFIGURATIONS_CHARACTERIZED_RAW_TIMING_NOT_QUALIFIED',completed_utc=datetime.now(timezone.utc).isoformat(),
             total_arcs=summary['total_arcs'],parameter_mismatches=0,
             outputs={name:describe(out/name)for name in ['cell-properties.tsv','timing-arcs.tsv','timing-arcs-compact.json','semantic-summary-v2.json','dsp-configs-characterized.dcp']})
        print(manifest['status']+' arcs='+str(summary['total_arcs']),flush=True)
    except Exception as exc:
        save(status='FAIL',error=repr(exc));shutil.copy2(__file__,out/'helper.py');raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in('inventory','template','out'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();characterize(args.inventory.resolve(),args.template.resolve(),args.out.resolve())


if __name__=='__main__':main()
