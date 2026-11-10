#!/usr/bin/env python3
"""Query exact full-design serializer and clock configurations with Vivado."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe, digest


LIMITS={'CLKIN_FREQ_MAX','CLKIN_FREQ_MIN','CLKPFD_FREQ_MAX','CLKPFD_FREQ_MIN','VCOCLK_FREQ_MAX','VCOCLK_FREQ_MIN'}
PRIMITIVES={'ISERDESE2_ISERDESE2':'ISERDESE2','OSERDESE2_OSERDESE2':'OSERDESE2',
            'MMCME2_ADV_MMCME2_ADV':'MMCME2_ADV','PLLE2_ADV_PLLE2_ADV':'PLLE2_ADV','BUFGCTRL':'BUFGCTRL'}


def declarations(checkpoint):
    result={};active=None
    with checkpoint.open()as stream:
        for line in stream:
            if line.startswith('module '):
                name=line.split()[1].lstrip('\\');active=name if name in PRIMITIVES.values()else None
                if active:result[active]={'ports':[]}
            elif active and line=='end\n':active=None
            elif active and line.startswith('  wire '):
                fields=line.split();direction=next((d for d in ['input','output','inout']if d in fields),None)
                if direction:
                    result[active]['ports'].append({'name':fields[-1].lstrip('\\'),'direction':direction,
                        'width':int(fields[fields.index('width')+1])if 'width'in fields else 1,'signed':'signed'in fields})
    if set(result)!=set(PRIMITIVES.values()):raise ValueError('Primitive port declarations are incomplete')
    return result


def library_parameters(primitive):
    library=Path(expand_paths('@YOSYS_SHARE@/xilinx'))
    path=library/('cells_sim.v'if primitive=='BUFGCTRL'else 'cells_xtra.v');text=path.read_text()
    match=re.search(r'^module '+re.escape(primitive)+r'\b.*?^endmodule',text,re.M|re.S)
    if not match:raise ValueError('Primitive library declaration not found')
    params={}
    for kind,name,value in re.findall(r'^\s*parameter\s+(?:(real|integer|\[[^\]]+\])\s+)?(\w+)\s*=\s*([^;]+);',match.group(),re.M):
        if name in LIMITS:continue
        value=value.strip()
        if value.startswith('"'):typed={'kind':'string','value':json.loads(value)}
        elif kind=='real':typed={'kind':'real','value':value}
        elif "'"in value:
            bits=re.fullmatch(r"(\d+)'b([01]+)",value)
            if not bits:raise ValueError('Unsupported primitive binary default')
            typed={'kind':'integer','value':int(bits[2],2),'width':int(bits[1])}
        else:typed={'kind':'integer','value':int(value)}
        params[name]=typed
    return params,describe(path)


def render(value):
    if value['kind']=='string':return json.dumps(value['value'])
    if value['kind']=='real':return str(value['value'])
    if 'width'in value:return f"{value['width']}'b"+format(value['value'],f"0{value['width']}b")
    return str(value['value'])


def build_probe(inventory,checkpoint):
    declarations_by_type=declarations(checkpoint);configs=[];libraries={}
    for packed_type,primitive in PRIMITIVES.items():
        defaults,lib=library_parameters(primitive);libraries[primitive]=lib
        if primitive=='BUFGCTRL':defaults['SIM_DEVICE']={'kind':'string','value':'7SERIES'}
        for group in inventory['profiles'][packed_type]:
            params={name:dict(value)for name,value in defaults.items()}
            for name,item in group['parameters'].items():
                if name not in params:raise ValueError('Unexpected actual primitive parameter '+name)
                if params[name]['kind']=='real':params[name]['value']=str(item['value'])
                elif params[name]['kind']=='integer':params[name]['value']=int(item['value'])
                else:params[name]['value']=item['value']
            # The actual bitstream writer defaults omitted clock-generator
            # compensation to INTERNAL, rather than the simulation library's
            # ZHOLD default. Explicit write-MMCM ZHOLD is retained.
            if primitive in ['MMCME2_ADV','PLLE2_ADV']and 'COMPENSATION'not in group['parameters']:
                params['COMPENSATION']['value']='INTERNAL'
            configs.append({'probe_cell':f'phy_{len(configs):02d}','primitive':primitive,'packed_type':packed_type,
                            'parameters':params,'full_design_cells':group['cells'],'ports':declarations_by_type[primitive]['ports']})
    if len(configs)!=7 or sum(len(c['full_design_cells'])for c in configs)!=378:raise ValueError('Full PHY/clock scope changed')
    declarations_top=[];wires=[];instances=[];clocks=[]
    for cfg in configs:
        name,primitive=cfg['probe_cell'],cfg['primitive'];connections=[]
        buffered_feedback=primitive in ['MMCME2_ADV','PLLE2_ADV']and cfg['parameters']['COMPENSATION']['value']=='ZHOLD'
        if buffered_feedback:
            wires.append('wire '+name+'_feedback;')
            wires.append('BUFG '+name+'_feedback_buffer (.I('+name+'_CLKFBOUT), .O('+name+'_feedback));')
        for port in cfg['ports']:
            pin=port['name'];signal=name+'_'+pin;width=port['width']
            # CLK/CLKB share a net in the actual deserializer; its inversion
            # parameter supplies the complementary sampling edge.
            if primitive=='ISERDESE2'and pin=='CLKB':connections.append('.CLKB('+name+'_CLK)');continue
            if primitive in ['MMCME2_ADV','PLLE2_ADV']and pin=='CLKFBIN':connections.append('.CLKFBIN('+name+('_feedback'if buffered_feedback else '_CLKFBOUT')+')');continue
            bus=f' [{width-1}:0]'if width>1 else ''
            signed=' signed'if port['signed']else ''
            declarations_top.append(f"    {port['direction']} wire{signed}{bus} {signal}");connections.append(f'.{pin}({signal})')
            period=None
            if primitive in ['ISERDESE2','OSERDESE2']:
                if pin=='CLK':period='2.5'
                elif pin=='CLKDIV':period='10.0'
            elif primitive in ['MMCME2_ADV','PLLE2_ADV']:
                if pin=='CLKIN1':period=cfg['parameters']['CLKIN1_PERIOD']['value']
                elif pin in ['DCLK','PSCLK']:period='10.0'
            elif primitive=='BUFGCTRL'and pin in ['I0','I1']:period='10.0'
            if period:clocks.append(f'create_clock -name {signal} -period {period} [get_ports {signal}]')
        params=',\n'.join('    .'+key+'('+render(value)+')'for key,value in sorted(cfg['parameters'].items()))
        instances.append('(* DONT_TOUCH = "TRUE" *) '+primitive+' #(\n'+params+'\n) '+name+' (\n    '+',\n    '.join(connections)+'\n);')
    rtl='module phy_configs(\n'+',\n'.join(declarations_top)+'\n);\n'+'\n'.join(wires+instances)+'\nendmodule\n'
    return configs,libraries,rtl,clocks


def query(inventory_path,checkpoint,out):
    inv=json.loads(inventory_path.read_text());configs,libs,rtl,clocks=build_probe(inv,checkpoint)
    out.mkdir(parents=True,exist_ok=False)
    (out/'phy_configs.v').write_text(rtl);(out/'configurations.json').write_text(json.dumps({'configs':configs,'library_defaults':libs,'inventory':describe(inventory_path),'checkpoint':describe(checkpoint),'excluded_simulation_defaults':sorted(LIMITS)},indent=2)+'\n')
    (out/'plan.md').write_text('Query all seven exact physical parameter groups covering every full-design serializer, MMCM, PLL and BUFGCTRL. Preserve CLK/CLKB sharing, CLK/CLKDIV frequency roles and clock feedback. Record actual HR serializer sites (ILOGICE3/OLOGICE3), parameters, arc properties and generated clocks. This is constituent vendor data, not a replacement full design, route, bitstream or complete timing qualification.\n')
    config_tcl=[]
    for cfg in configs:
        config_tcl.append('set wanted('+cfg['probe_cell']+') {'+' '.join(sorted(cfg['parameters']))+'}')
        config_tcl.append('set primitive('+cfg['probe_cell']+') '+cfg['primitive'])
    tcl='''set_param general.maxThreads 8
create_project -in_memory -part xc7k480tffg1156-2
read_verilog phy_configs.v
synth_design -top phy_configs -part xc7k480tffg1156-2 -mode out_of_context
'''+ '\n'.join(clocks+config_tcl)+'''
set cells [lsort [get_cells -filter {NAME =~ phy_* && REF_NAME != BUFG}]]
puts "PHY_CELL_COUNT|[llength $cells]"
if {[llength $cells] != 7} {error "Full PHY/clock configuration coverage changed"}
set cf [open cell-properties.tsv w]
puts $cf "cell\tproperty\tvalue"
set af [open timing-arcs.tsv w]
puts $af "cell\tarc\tproperty\tvalue"
array set used {}
foreach cell $cells {
    set type $primitive($cell)
    set site_type $type
    if {$type == "ISERDESE2"} {set site_type ILOGICE3}
    if {$type == "OSERDESE2"} {set site_type OLOGICE3}
    set sites [get_sites -filter "SITE_TYPE == $site_type"]
    if {![info exists used($site_type)]} {set used($site_type) 0}
    if {[llength $sites] <= $used($site_type)} {error "No physical site for $cell ($site_type)"}
    set site [lindex $sites $used($site_type)]
    incr used($site_type)
    set_property LOC $site $cell
    puts "PHY_SITE|$cell|$site|$site_type"
    foreach property [concat {REF_NAME LOC} $wanted($cell)] {
        set value [get_property $property $cell]
        puts $cf "$cell\t$property\t$value"
    }
    set arcs [get_timing_arcs -of_objects $cell]
    puts "PHY_ARCS|$cell|[llength $arcs]"
    foreach arc $arcs {
        foreach property [lsort [list_property $arc]] {
            set value [get_property $property $arc]
            set value [string map [list "\t" "\\t" "\n" "\\n" "\r" "\\r"] $value]
            puts $af "$cell\t$arc\t$property\t$value"
        }
    }
}
close $cf
close $af
set kf [open clock-properties.tsv w]
puts $kf "clock\tproperty\tvalue"
foreach clock [lsort [get_clocks]] {
    foreach property [lsort [list_property $clock]] {
        set value [get_property $property $clock]
        puts $kf "$clock\t$property\t$value"
    }
}
close $kf
report_clocks -file clocks.rpt
write_checkpoint phy-configs-characterized.dcp
puts "FULL_PHY_CLOCK_CONFIGURATIONS_QUERIED_NOT_TIMING_QUALIFICATION"
exit 0
'''
    (out/'query.tcl').write_text(tcl)
    argv=[expand_paths('@VIVADO_BIN@/vivado'),'-mode','batch','-nojournal','-nolog','-notrace','-source',str(out/'query.tcl')]
    info={'status':'RUNNING','created_utc':datetime.now(timezone.utc).isoformat(),'scope':'EXACT_FULL_DESIGN_PHY_CLOCK_PARAMETER_GROUPS_NOT_WHOLE_TIMING_QUALIFICATION',
          'part':'xc7k480tffg1156-2','threads':8,'profiles':7,'full_design_cells':378,'source_inventory':describe(inventory_path),
          'helper':describe(__file__),'inputs':{n:digest(out/n)for n in ['plan.md','phy_configs.v','configurations.json','query.tcl']},
          'command':argv,'live_source_or_backend_changed':False,'hardware_accessed':False,'numerical_timing':'NOT_QUALIFIED'}
    def save(**fields):info.update(fields);(out/'manifest.json').write_text(json.dumps(info,indent=2)+'\n')
    try:
        save();print('VIVADO_PHY_QUERY_STARTED '+str(out),flush=True)
        with(out/'query.log').open('w')as log:
            child=subprocess.Popen(argv,cwd=out,stdout=log,stderr=subprocess.STDOUT);save(native_pid=child.pid);code=child.wait()
        (out/'query.exit').write_text(str(code)+'\n');save(native_exit=code)
        if code:raise RuntimeError('Native PHY/clock timing query failed')
        save(status='FULL_PHY_CLOCK_QUERY_PASS_SEMANTICS_VALIDATION_PENDING',completed_utc=datetime.now(timezone.utc).isoformat(),
             outputs={n:describe(out/n)for n in ['cell-properties.tsv','timing-arcs.tsv','clock-properties.tsv','clocks.rpt','phy-configs-characterized.dcp']})
        print(info['status'],flush=True)
    except Exception as exc:save(status='FAIL',error=repr(exc));raise
    finally:shutil.copy2(__file__,out/'helper.py')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['inventory','checkpoint','out']:parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();query(args.inventory.resolve(),args.checkpoint.resolve(),args.out.resolve())


if __name__=='__main__':main()
