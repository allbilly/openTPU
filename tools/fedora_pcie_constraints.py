#!/usr/bin/env python3
"""Prepare complete YPCB PCIe/DDR pin constraints from checked board sources.

Pin coverage is checked against the complete RTL top. Generated clock periods
are diagnostic constraints; phase relationships, I/O margins and CDC still
need qualification after full implementation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
import re

from fedora_openxc7 import ROOT,configuration
from fedora_prepare_litedram import profile
from openxc7_vref import bank_plan

ORDINARY = {'SYS_CLK':'SYS_CLK','sys_rst_n':'pcie_perstn',
            'led[0]':'led_3bits_tri_o[0]','led[1]':'led_3bits_tri_o[1]','led[2]':'led_3bits_tri_o[2]',
            'lm73_scl':'iic_lm73_scl_io','lm73_sda':'iic_lm73_sda_io','lm73_alert_n':'alert_lm73_tri_i',
            'smb_scl':'iic_pcie_scl_io','smb_sda':'iic_pcie_sda_io'}
GT = {'sys_clk_p':'J8','sys_clk_n':'J7','pci_exp_rxp':'H6','pci_exp_rxn':'H5',
      'pci_exp_txp':'F2','pci_exp_txn':'F1'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def properties(text):
    result = {}
    pattern = r'set_property (PACKAGE_PIN|LOC|IOSTANDARD|SLEW|IN_TERM|PULLUP) (\S+) \[get_ports (?:\{([^}]+)\}|([^\]\s]+))\]'
    for line in text.splitlines():
        match = re.fullmatch(pattern,line.strip())
        if match:
            kind,value,braced,bare = match.groups()
            port = braced or bare
            if kind in result.setdefault(port,{}):
                raise ValueError('Duplicate pin property: '+port+'/'+kind)
            result[port][kind] = value
    return result


def top_bits(text):
    text = re.sub(r'//[^\n]*','',text)
    match = re.search(r'\bmodule\s+otpu_fpga_top_openxc7_pcie\s*#\s*\(',text)
    if not match:
        raise ValueError('Missing complete PCIe top')
    def group(start):
        depth = 1
        end = start+1
        while end < len(text) and depth:
            depth += (text[end] == '(')-(text[end] == ')')
            end += 1
        if depth:
            raise ValueError('Unbalanced top declaration')
        return text[start+1:end-1],end
    _,end = group(match.end()-1)
    start = end+len(text[end:])-len(text[end:].lstrip())
    if text[start] != '(':
        raise ValueError('Missing PCIe top port group')
    declarations,_ = group(start)
    bits = set()
    current = None
    for declaration in declarations.split(','):
        match = re.fullmatch(r'\s*(?:(input|output|inout)\s+(?:(?:logic|wire|reg)\s+)?'
                             r'(?:\[\s*(\d+)\s*:\s*(\d+)\s*\]\s*)?)?'
                             r'([A-Za-z_][A-Za-z_0-9]*)\s*',declaration)
        if not match:
            raise ValueError('Unsupported top port declaration: '+declaration)
        direction,high,low,name = match.groups()
        if direction:
            current = (int(high),int(low)) if high is not None else None
        if current is None:
            names = [name]
        else:
            names = [f'{name}[{n}]' for n in range(min(current),max(current)+1)]
        if bits.intersection(names):
            raise ValueError('Duplicate top port')
        bits.update(names)
    return bits


def prepare(core,out,database=None):
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh constraint output directory')
    dram = profile(Path(core))
    database = Path(database or configuration()['database'])
    vendor = ROOT/'boards/ypcb-00338/constraints/vendor_ypcb003381p1.xdc'
    reference = ROOT/'build/fedora-openxc7/deps/pcie_7x/pcie_7x_ypcb_k480t.xdc'
    top = ROOT/'rtl/boards/ypcb-00338/otpu_fpga_top_openxc7_pcie.sv'
    package = database/'xc7k480tffg1156-2/package_pins.csv'
    pins = {r['pin']:r for r in csv.DictReader(package.open())}
    vp,rp,dp = [properties(p.read_text()) for p in (vendor,reference,dram['xdc'])]
    assignments = {}
    overrides = []
    for port,source in ORDINARY.items():
        p = vp.get(source,{})
        if p.get('IOSTANDARD') != 'LVCMOS18' or p.get('PACKAGE_PIN') not in pins:
            raise ValueError('Missing vendor 1.8 V board mapping: '+source)
        assignments[port] = {'PACKAGE_PIN':p['PACKAGE_PIN'],'IOSTANDARD':'LVCMOS18'}
        example = 'clk_50' if port == 'SYS_CLK' else port
        if rp.get(example,{}).get('IOSTANDARD') == 'LVCMOS33':
            overrides.append(dict(port=port,pin=p['PACKAGE_PIN'],example_standard='LVCMOS33',selected_standard='LVCMOS18',source=str(vendor)))
        if port.startswith(('lm73_','smb_')) or port == 'sys_rst_n':
            assignments[port]['PULLUP'] = 'true'
    for port,pin in GT.items():
        if rp.get(port,{}).get('PACKAGE_PIN') != pin or pin not in pins:
            raise ValueError('GT package pin differs from reviewed reference: '+port)
        assignments[port] = {'PACKAGE_PIN':pin}
    functions = {p:pins[v]['pin_function'] for p,v in GT.items()}
    for positive,negative in [('sys_clk_p','sys_clk_n'),('pci_exp_rxp','pci_exp_rxn'),('pci_exp_txp','pci_exp_txn')]:
        p,n = functions[positive],functions[negative]
        if p.replace('P','N',1) != n or pins[GT[positive]]['bank'] != pins[GT[negative]]['bank']:
            raise ValueError('GT differential pair differs from package database')
    if len({pins[p]['bank'] for p in GT.values()}) != 1:
        raise ValueError('PCIe lane and refclock do not belong to the same GT bank')
    for port,p in dp.items():
        if not port.startswith(('ddram0_','ddram1_')) or p.get('LOC') not in pins:
            raise ValueError('Unsupported DDR port mapping: '+port)
        assignments[port] = {('PACKAGE_PIN' if k == 'LOC' else k):v for k,v in p.items()}
    bits = top_bits(top.read_text())
    if set(assignments) != bits:
        raise ValueError('Pin coverage differs from complete top: '+str(dict(missing=sorted(bits-set(assignments)),extra=sorted(set(assignments)-bits))))
    used = [p['PACKAGE_PIN'] for p in assignments.values()]
    if len(set(used)) != len(used):
        raise ValueError('Board/DDR/GT pin assignments overlap')
    plan = bank_plan(dram['xdc'],database)
    literal_ddr = re.compile(r'set_property (LOC|IOSTANDARD|SLEW|IN_TERM) \S+ \[get_ports \{[^}]+\}\]')
    omitted = [dict(line=n,text=s) for n,s in enumerate(dram['xdc'].read_text().splitlines(),1)
               if s.strip() and not s.startswith('#') and not literal_ddr.fullmatch(s)]
    lines = ['# Complete PCIe top pin assignments; numerical timing is not qualified.']
    for port,p in assignments.items():
        lines.extend(f'set_property {k} {v} [get_ports {{{port}}}]' for k,v in p.items())
    core_period = 1e6/dram['parameters']['CORE_KHZ']
    lines += ['create_clock -period 20 [get_ports {SYS_CLK}]',
              'create_clock -period 10 [get_ports {sys_clk_p}]',
              f'create_clock -period {core_period} [get_nets {{ld_sys_clk}}]',
              'create_clock -period 8 [get_nets {pcie_clk}]']
    out.mkdir(parents=True)
    target = out/'openxc7.xdc'
    target.write_text('\n'.join(lines)+'\n')
    report = dict(status='COMPLETE_RTL_PIN_COVERAGE_PASS_IMPLEMENTATION_AND_TIMING_PENDING',
                  constrained_bits=len(bits),ddr_bits=len(dp),dedicated_gt_pins=functions,
                  package_gt_bank=pins[GT['sys_clk_p']]['bank'],ordinary_io_voltage_overrides=overrides,
                  parameters=dram['parameters'],vref_plan=plan,omitted_ddr_constraints=omitted,
                  inputs={str(p):sha(p) for p in (vendor,reference,top,dram['xdc'],package,Path(__file__))},
                  output=dict(path=str(target),sha256=sha(target)),hardware='NOT_RUN',timing='NOT_QUALIFIED',
                  note='All RTL pad bits assigned. Generated-clock/DDR phase/reset/CDC constraints remain unqualified; validate synthesized net names before routing.')
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--litedram-core',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    args = ap.parse_args()
    report = prepare(args.litedram_core,args.out)
    print(report['status'])
    print(args.out/'manifest.json')


if __name__ == '__main__':
    main()
