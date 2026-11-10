#!/usr/bin/env python3
"""Export the pinned open YPCB PCIe endpoint's AXI-Lite master, without its RAM stub."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REVISION = 'cd1c33f53401d6ce1b6ec35da17884455477c2e9'
REFERENCE = 'src/aximm-minimal/pcie_7x_top_aximm.v'
REFERENCE_SHA = 'bda9ffbab55e7c8cca7a232e250cb653429d947e8c4d9dada322cf9092e199a5'
SOURCES = ['xilinx_pcie_mmcm.v', 'axil_to_al.v', 'axis_pcie_to_al_us.v',
           'pcie_7x.v', 'pcie_axi_rx.v', 'pcie_axi_tx.v', 'pcie_block.v',
           'pcie_brams.v', 'pcie_tx_thrtl_ctl.v', 'pipe_wrapper_gtx.v']


def sha(data):
    return hashlib.sha256(data).hexdigest()


def prepare(dependency: Path, out: Path):
    dependency = dependency.resolve()
    out = out.resolve()
    revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=dependency, text=True).strip()
    if revision != REVISION:
        raise ValueError('PCIe dependency revision differs from the reviewed YPCB reference')
    inputs = {}
    for name in [REFERENCE, 'pcie_7x_ypcb_k480t.xdc'] + ['src/'+s for s in SOURCES]:
        path = dependency/name
        data = path.read_bytes()
        original = subprocess.check_output(['git', 'show', REVISION+':'+name], cwd=dependency)
        if data != original:
            raise ValueError('Pinned PCIe source was modified: '+str(path))
        inputs[str(path)] = sha(data)
    source = (dependency/REFERENCE).read_text()
    if sha(source.encode()) != REFERENCE_SHA:
        raise ValueError('PCIe reference wrapper hash differs')
    if source.count('module pcie_7x_top_aximm #') != 1 or source.count('// Instantiate axil_minimum') != 1:
        raise ValueError('Unexpected endpoint wrapper structure')
    source = source.replace('module pcie_7x_top_aximm #', 'module otpu_pcie_endpoint #', 1)
    # The exported wrapper is specifically for YPCB: make its defaults match
    # the original YPCB wrapper's explicit GTX/Gen2/device-ID overrides.
    for old,new in [('parameter ENABLE_GEN2         = 0','parameter ENABLE_GEN2         = 1'),
                    ('parameter GT_DEVICE           = "GTP"','parameter GT_DEVICE           = "GTX"'),
                    ("parameter CFG_DEV_ID          = 16'h9999","parameter CFG_DEV_ID          = 16'h0480")]:
        if source.count(old) != 1:
            raise ValueError('Unexpected PCIe wrapper parameter declaration: '+old)
        source = source.replace(old,new,1)
    ports = '''
  output wire m_clk, m_reset,
  output wire [31:0] m_awaddr, m_wdata, m_araddr,
  output wire [3:0] m_wstrb,
  output wire m_awvalid, m_wvalid, m_bready, m_arvalid, m_rready,
  input wire m_awready, m_wready, m_bvalid, m_arready, m_rvalid,
  input wire [1:0] m_bresp, m_rresp,
  input wire [31:0] m_rdata,
'''
    source = source.replace('  output      pci_exp_txp,', ports+'  output      pci_exp_txp,', 1)
    start = source.index('// Instantiate axil_minimum')
    end = source.index('`endif', start)
    connections = ['assign m_clk = user_clk;', 'assign m_reset = user_reset_q || !user_lnk_up_q;']
    connections.append("assign cfg_pciecap_interrupt_msgnum = 5'd0; // interrupts are disabled")
    for name in ['awaddr','wdata','araddr','wstrb','awvalid','wvalid','bready','arvalid','rready']:
        connections.append(f'assign m_{name} = s_axi_{name};')
    for name in ['awready','wready','bvalid','arready','rvalid','bresp','rresp','rdata']:
        connections.append(f'assign s_axi_{name} = m_{name};')
    source = source[:start]+'// OpenTPU connects this master to its complete command interface.\n'+'\n'.join(connections)+'\n'+source[end:]
    if 'axil_minimum axil_minimum_inst' in source:
        raise ValueError('RAM stub survived endpoint export')
    source = '// Derived from the pinned CERN-OHL-P pcie_7x reference; see manifest.json.\n'+source
    out.mkdir(parents=True, exist_ok=True)
    wrapper = out/'otpu_pcie_endpoint.v'
    wrapper.write_text(source)
    patches = {}
    generated = {}
    def patch_source(name, edits):
        original = dependency/'src'/name
        body = original.read_text()
        for anchor,replacement in edits:
            if body.count(anchor) != 1:
                raise ValueError('Unexpected source correction anchor in '+name)
            body = body.replace(anchor,replacement,1)
        target = out/name
        target.write_text(body)
        generated[name] = str(target)
        patches[name] = dict(original=str(original),original_sha256=sha(original.read_bytes()),
                             generated=str(target),generated_sha256=sha(target.read_bytes()))
    anchor = '  assign        cfg_received_func_lvl_rst = ~cfg_received_func_lvl_rst_n;'
    patch_source('pcie_block.v',[(anchor,
        '''  // Preserve hard-block transmitter control and active-low PM acknowledgement.
  assign pipe_tx_deemph_gt = pipe_tx_deemph;
  assign pipe_tx_margin_gt = pipe_tx_margin;
  assign cfg_turnoff_ok_w = ~cfg_turnoff_ok;

'''+anchor)])
    patch_source('pipe_wrapper_gtx.v',[
        ('.EYESCANDATAERROR               (),',
         '.EYESCANDATAERROR               (PIPE_EYESCANDATAERROR[0]),')])
    report = dict(status='ENDPOINT_MASTER_EXPORTED_NOT_IMPLEMENTED_OR_PHYSICALLY_TESTED',
                  revision=revision, inputs=inputs,
                  wrapper=dict(path=str(wrapper), sha256=sha(wrapper.read_bytes())),
                  sources=[generated.get(s,str(dependency/'src'/s)) for s in SOURCES]+[str(wrapper)],
                  reviewed_source_corrections=patches,
                  bar0_bytes=4096, link='Gen2 x1 GTX', protocol='OpenTPU PIO mailbox ABI 1',
                  xdma_compatible=False, hardware='NOT_RUN')
    (out/'manifest.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dependency', type=Path, default=ROOT/'build/fedora-openxc7/deps/pcie_7x')
    ap.add_argument('--out', type=Path, default=ROOT/'build/fedora-openxc7/pcie-endpoint')
    args = ap.parse_args()
    report = prepare(args.dependency, args.out)
    print(report['status'])
    print(args.out/'manifest.json')


if __name__ == '__main__':
    main()
