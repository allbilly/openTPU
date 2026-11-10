// Lint-only stand-in for the Vivado-generated block design wrapper of the LiteDRAM build
// (boards/ypcb-00338/vivado/bd_native.tcl, MEM=litedram): the ports Vivado will generate, no
// behaviour. Used by `make lint-ld` to check otpu_fpga_top_ld offline; Vivado builds with the
// real otpu_bd_wrapper.v (and the unisim IBUF, BUFG, IOBUF). M_AXI_DMA is XDMA's M_AXI made
// external (64-bit address, 4-bit IDs, 128-bit data).
module otpu_bd_wrapper (
  input  logic        sys_clk_50,
  input  logic        pcie_refclk_clk_p, pcie_refclk_clk_n, pcie_perstn,
  input  logic [7:0]  pcie_mgt_rxp, pcie_mgt_rxn,
  output logic [7:0]  pcie_mgt_txp, pcie_mgt_txn,
  output logic        pcie_link_up, core_clk, core_clk2x, core_rstn, xdma_aclk, xdma_aresetn,
  output logic [11:0] device_temp,
  output logic        host_aclk, host_locked,
  input  logic        host_rstn, cfg_resetn,
`define STUB_L(P) \
  output logic [31:0] P``_awaddr, P``_araddr, P``_wdata, \
  output logic [3:0]  P``_wstrb, \
  output logic        P``_awvalid, P``_wvalid, P``_bready, P``_arvalid, P``_rready, \
  input  logic        P``_awready, P``_wready, P``_bvalid, P``_arready, P``_rvalid, \
  input  logic [1:0]  P``_bresp, P``_rresp, \
  input  logic [31:0] P``_rdata
  `STUB_L(M_AXI_CTL),
  `STUB_L(M_AXI_MEMCAL),
  `STUB_L(S_AXI_JCTL),
  input  logic [2:0]   S_AXI_JCTL_awprot, S_AXI_JCTL_arprot,
  `STUB_L(S_AXI_JMEMCAL),
  input  logic [2:0]   S_AXI_JMEMCAL_awprot, S_AXI_JMEMCAL_arprot,
  input  logic [3:0]   S_AXI_JDMA_awid, S_AXI_JDMA_arid,
  output logic [3:0]   S_AXI_JDMA_bid, S_AXI_JDMA_rid,
  input  logic [31:0]  S_AXI_JDMA_awaddr, S_AXI_JDMA_araddr,
  input  logic [7:0]   S_AXI_JDMA_awlen, S_AXI_JDMA_arlen,
  input  logic [2:0]   S_AXI_JDMA_awsize, S_AXI_JDMA_arsize, S_AXI_JDMA_awprot, S_AXI_JDMA_arprot,
  input  logic [1:0]   S_AXI_JDMA_awburst, S_AXI_JDMA_arburst,
  input  logic         S_AXI_JDMA_awlock, S_AXI_JDMA_arlock,
  input  logic [3:0]   S_AXI_JDMA_awcache, S_AXI_JDMA_arcache,
  input  logic [3:0]   S_AXI_JDMA_awqos, S_AXI_JDMA_arqos,
  input  logic         S_AXI_JDMA_awvalid, S_AXI_JDMA_arvalid, S_AXI_JDMA_wvalid, S_AXI_JDMA_wlast,
  input  logic         S_AXI_JDMA_bready, S_AXI_JDMA_rready,
  input  logic [127:0] S_AXI_JDMA_wdata,
  input  logic [15:0]  S_AXI_JDMA_wstrb,
  output logic         S_AXI_JDMA_awready, S_AXI_JDMA_arready, S_AXI_JDMA_wready,
  output logic         S_AXI_JDMA_bvalid, S_AXI_JDMA_rvalid, S_AXI_JDMA_rlast,
  output logic [1:0]   S_AXI_JDMA_bresp, S_AXI_JDMA_rresp,
  output logic [127:0] S_AXI_JDMA_rdata,
  output logic [3:0]   M_AXI_DMA_awid, M_AXI_DMA_arid,
  output logic [63:0]  M_AXI_DMA_awaddr, M_AXI_DMA_araddr,
  output logic [7:0]   M_AXI_DMA_awlen, M_AXI_DMA_arlen,
  output logic [2:0]   M_AXI_DMA_awsize, M_AXI_DMA_arsize, M_AXI_DMA_awprot, M_AXI_DMA_arprot,
  output logic [1:0]   M_AXI_DMA_awburst, M_AXI_DMA_arburst,
  output logic         M_AXI_DMA_awlock, M_AXI_DMA_arlock,
  output logic [3:0]   M_AXI_DMA_awcache, M_AXI_DMA_arcache,
  output logic         M_AXI_DMA_awvalid, M_AXI_DMA_arvalid, M_AXI_DMA_wvalid, M_AXI_DMA_wlast,
  output logic         M_AXI_DMA_bready, M_AXI_DMA_rready,
  output logic [127:0] M_AXI_DMA_wdata,
  output logic [15:0]  M_AXI_DMA_wstrb,
  input  logic         M_AXI_DMA_awready, M_AXI_DMA_arready, M_AXI_DMA_wready,
  input  logic         M_AXI_DMA_bvalid, M_AXI_DMA_rvalid, M_AXI_DMA_rlast,
  input  logic [3:0]   M_AXI_DMA_bid, M_AXI_DMA_rid,
  input  logic [1:0]   M_AXI_DMA_bresp, M_AXI_DMA_rresp,
  input  logic [127:0] M_AXI_DMA_rdata
);
`undef STUB_L
endmodule

// The Xilinx primitives (unisim) as otpu_fpga_top_ld uses them
module IOBUF (inout wire IO, input logic I, input logic T, output logic O);
  assign IO = T ? 1'bz : I;
  assign O = IO;
endmodule
module IBUF (input logic I, output logic O);
  assign O = I;
endmodule
module BUFG (input logic I, output logic O);
  assign O = I;
endmodule
module BSCANE2 #(parameter int JTAG_CHAIN = 1) (
  output logic TCK, DRCK, CAPTURE, SHIFT, UPDATE, SEL, TDI, RESET, RUNTEST, TMS,
  input  logic TDO);
  assign {TCK, DRCK, CAPTURE, SHIFT, UPDATE, SEL, TDI, RESET, RUNTEST, TMS} = '0;
endmodule
