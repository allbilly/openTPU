// SPDX-License-Identifier: Apache-2.0
// Standalone openXC7 board image: the full MCOLS=4/LANES=8 accelerator,
// dual 72-bit LiteDRAM with its real self-calibration firmware and I2C,
// controlled through BSCANE2 USER2. XADC is read through its dedicated
// JTAG DRP instruction by the host. Adapted from
// otpu_fpga_top_ld.sv; that original PCIe/Vivado build remains available.
// This JTAG image provides no PCIe endpoint and is not XDMA compatible.
module otpu_fpga_top_openxc7_jtag #(
  parameter int MCOLS = 4,                  // MXU columns (activation rows per weight chunk)
  parameter int ACT_ROWS = MCOLS,           // ACT RAM rows (> MCOLS: MM replay, one weight pass)
  parameter int VPU_CL = 2,                 // VPU lanes with the composite functions (exp2, ...)
  parameter int MXU_IMPL = 2,               // MXU dot product: 2 systolic (docs/mxu_systolic.md), 0 adder tree
  parameter int LANES = 8,                  // VPU lanes / TMEM banks (8 or 16)
  parameter int ULANES = 8,                 // TMEM lanes of the MXU and the quantizer
  parameter int CORE_KHZ = 133333,          // core_clk as the block design makes it (CORE_KHZ register)
  parameter logic [31:0] BUILD_ID = 32'h0,  // the git commit (BUILD_ID register)
  parameter int DDR_MTS = 1066,             // the DDR3 data rate the LiteDRAM core runs (DDR_MTS register)
  parameter bit DSTEP = 1'b1,               // the DMA's DSTEP datapath (CAPS bit6; 0: left out)
  parameter int PCIE_GEN = 2                // 1: Gen1 x8, xdma_aclk 125 MHz; 2: Gen2 x8, 250 MHz,
                                            // slices to the bridges (otpu_native_sys XREG),
                                            // the LiteDRAM CSRs on core_clk (bd_native.tcl)
) (
  // board
  input  logic        SYS_CLK,              // 50 MHz, AA28
  output logic [2:0]  led,                  // P30 red, M30 green, N30 yellow
  // I2C, open drain (otpu_ctrl I2C_CTRL / I2C_IN; the host bit-bangs them)
  inout  wire         lm73_scl,             // N24  the LM73 temperature sensor's bus
  inout  wire         lm73_sda,             // N25
  input  logic        lm73_alert_n,         // P25
  inout  wire         smb_scl,              // R26  the PCIe edge connector's SMBus
  inout  wire         smb_sda,              // R27
  // DDR3 channel 0
  inout  wire  [71:0] ddram0_dq,
  inout  wire  [8:0]  ddram0_dqs_p,
  inout  wire  [8:0]  ddram0_dqs_n,
  output logic [14:0] ddram0_a,
  output logic [2:0]  ddram0_ba,
  output logic        ddram0_ras_n,
  output logic        ddram0_cas_n,
  output logic        ddram0_we_n,
  output logic        ddram0_reset_n,
  output logic        ddram0_clk_p,
  output logic        ddram0_clk_n,
  output logic        ddram0_cke,
  output logic        ddram0_cs_n,
  output logic        ddram0_odt,
  // DDR3 channel 1
  inout  wire  [71:0] ddram1_dq,
  inout  wire  [8:0]  ddram1_dqs_p,
  inout  wire  [8:0]  ddram1_dqs_n,
  output logic [14:0] ddram1_a,
  output logic [2:0]  ddram1_ba,
  output logic        ddram1_ras_n,
  output logic        ddram1_cas_n,
  output logic        ddram1_we_n,
  output logic        ddram1_reset_n,
  output logic        ddram1_clk_p,
  output logic        ddram1_clk_n,
  output logic        ddram1_cke,
  output logic        ddram1_cs_n,
  output logic        ddram1_odt
);
  logic        clk50_ib, clk50;
  wire core_clk = ld_sys_clk;
  wire core_rstn = !ld_sys_rst;
  wire xdma_aclk = ld_sys_clk;
  wire xdma_aresetn = !ld_sys_rst;
  logic        ld_sys_clk, ld_sys_rst;
  logic [1:0]  calib;

  // the 50 MHz oscillator on one global buffer: the block design's MMCM and the LiteDRAM core's
  IBUF u_ibuf50 (.I(SYS_CLK), .O(clk50_ib));
  BUFG u_bufg50 (.I(clk50_ib), .O(clk50));

  // ---- control (AXI4-Lite, BD master -> accelerator, core_clk)
  logic [31:0] ctl_awaddr, ctl_araddr, ctl_wdata, ctl_rdata;
  logic [3:0]  ctl_wstrb;
  logic [1:0]  ctl_bresp, ctl_rresp;
  logic ctl_awvalid, ctl_awready, ctl_wvalid, ctl_wready, ctl_bvalid, ctl_bready;
  logic ctl_arvalid, ctl_arready, ctl_rvalid, ctl_rready;
  // ---- the LiteDRAM CSRs (AXI4-Lite, BD master -> the core; xdma_aclk, core_clk at PCIE_GEN 2)
  logic [31:0] mc_awaddr, mc_araddr, mc_wdata, mc_rdata;
  logic [3:0]  mc_wstrb;
  logic [1:0]  mc_bresp, mc_rresp;
  logic mc_awvalid, mc_awready, mc_wvalid, mc_wready, mc_bvalid, mc_bready;
  logic mc_arvalid, mc_arready, mc_rvalid, mc_rready;
  // ---- XDMA's DMA master (AXI4, 128 bits, xdma_aclk)
  logic [3:0]   dm_awid, dm_arid, dm_bid, dm_rid;
  logic [63:0]  dm_awaddr, dm_araddr;
  logic [7:0]   dm_awlen, dm_arlen;
  logic [127:0] dm_wdata, dm_rdata;
  logic [15:0]  dm_wstrb;
  logic [1:0]   dm_bresp, dm_rresp;
  logic dm_awvalid, dm_awready, dm_wlast, dm_wvalid, dm_wready, dm_bvalid, dm_bready;
  logic dm_arvalid, dm_arready, dm_rlast, dm_rvalid, dm_rready;

  // All AXI interfaces use LiteDRAM's 133.333 MHz system clock. This runs
  // from SYS_CLK alone and needs no PCIe reference clock or PERST signal.
  logic tck, capture, shift, update, sel, tdi, tdo;
  (* keep = "true" *) BSCANE2 #(.JTAG_CHAIN(2)) u_bscan (
    .TCK(tck), .DRCK(), .CAPTURE(capture), .SHIFT(shift), .UPDATE(update),
    .SEL(sel), .TDI(tdi), .TDO(tdo), .RESET(), .RUNTEST(), .TMS());
  logic req_valid, req_ready, rsp_valid;
  logic [603:0] req;
  logic [511:0] rsp_data;
  logic [7:0] rsp_status;
  logic [15:0] rsp_seq;
  otpu_jtag_mailbox u_mailbox (
    .clk(core_clk), .rst(ld_sys_rst), .tck, .capture, .shift, .update, .sel,
    .tdi, .tdo, .req_valid, .req_ready, .req,
    .rsp_valid, .rsp_data, .rsp_status, .rsp_seq);
  otpu_jtag_axi u_host (
    .clk(core_clk), .rst(ld_sys_rst), .req_valid, .req_ready, .req,
    .rsp_valid, .rsp_data, .rsp_status, .rsp_seq,
    .l_awaddr({mc_awaddr,ctl_awaddr}), .l_araddr({mc_araddr,ctl_araddr}),
    .l_wdata({mc_wdata,ctl_wdata}), .l_wstrb({mc_wstrb,ctl_wstrb}),
    .l_awvalid({mc_awvalid,ctl_awvalid}), .l_wvalid({mc_wvalid,ctl_wvalid}),
    .l_bready({mc_bready,ctl_bready}), .l_arvalid({mc_arvalid,ctl_arvalid}),
    .l_rready({mc_rready,ctl_rready}), .l_awready({mc_awready,ctl_awready}),
    .l_wready({mc_wready,ctl_wready}), .l_bvalid({mc_bvalid,ctl_bvalid}),
    .l_arready({mc_arready,ctl_arready}), .l_rvalid({mc_rvalid,ctl_rvalid}),
    .l_bresp({mc_bresp,ctl_bresp}), .l_rresp({mc_rresp,ctl_rresp}),
    .l_rdata({mc_rdata,ctl_rdata}),
    .x_awid(dm_awid), .x_arid(dm_arid),
    .x_awaddr(dm_awaddr[31:0]), .x_araddr(dm_araddr[31:0]),
    .x_awlen(dm_awlen), .x_arlen(dm_arlen), .x_awvalid(dm_awvalid),
    .x_arvalid(dm_arvalid), .x_wvalid(dm_wvalid), .x_wlast(dm_wlast),
    .x_bready(dm_bready), .x_rready(dm_rready), .x_wdata(dm_wdata), .x_wstrb(dm_wstrb),
    .x_awready(dm_awready), .x_arready(dm_arready), .x_wready(dm_wready),
    .x_bvalid(dm_bvalid), .x_rvalid(dm_rvalid), .x_rlast(dm_rlast),
    .x_bid(dm_bid), .x_rid(dm_rid), .x_bresp(dm_bresp), .x_rresp(dm_rresp),
    .x_rdata(dm_rdata));
  assign dm_awaddr[63:32] = 0;
  assign dm_araddr[63:32] = 0;

  // UG480's dedicated XADC JTAG DRP needs no fabric XADC instance. The
  // transport reads the real internal sensor in its default mode. Report
  // the absence of a fabric TEMP register through HAS_TEMP below.

  // resets: synchronous, active high, one register each (otpu_mem_ch crosses them registered)
  logic core_rst, xrst;
  always_ff @(posedge core_clk) core_rst <= !core_rstn;
  always_ff @(posedge xdma_aclk) xrst <= !xdma_aresetn;

  // ---- the channels' controller ports (otpu_mem_ch <-> the LiteDRAM core), sys_clk: two per
  // channel, [channel][port] (port 1 = the core's c<n>b_*: the odd banks)
  logic [1:0][1:0]        c_cmd_valid, c_cmd_ready, c_cmd_we, c_wdata_valid, c_wdata_ready;
  logic [1:0][1:0]        c_rdata_valid;
  logic [1:0]             c_ready;
  logic [1:0][1:0][24:0]  c_cmd_addr;
  logic [1:0][1:0][511:0] c_wdata_data, c_rdata_data;
  logic [1:0][1:0][63:0]  c_wdata_we;

  // ---- LiteDRAM: both channels, their CSRs (BAR0 0x10000) and calibration ready bits
  otpu_litedram u_ld (
    .clk50g(clk50), .rst(1'b0), .sys_clk(ld_sys_clk), .sys_rst(ld_sys_rst),
    .ctl_clk(PCIE_GEN == 2 ? core_clk : xdma_aclk), .ctl_rst(PCIE_GEN == 2 ? core_rst : xrst),
    .ctl_awvalid(mc_awvalid), .ctl_awready(mc_awready), .ctl_awaddr(mc_awaddr[15:0]),
    .ctl_wvalid(mc_wvalid), .ctl_wready(mc_wready), .ctl_wdata(mc_wdata), .ctl_wstrb(mc_wstrb),
    .ctl_bvalid(mc_bvalid), .ctl_bready(mc_bready), .ctl_bresp(mc_bresp),
    .ctl_arvalid(mc_arvalid), .ctl_arready(mc_arready), .ctl_araddr(mc_araddr[15:0]),
    .ctl_rvalid(mc_rvalid), .ctl_rready(mc_rready), .ctl_rdata(mc_rdata), .ctl_rresp(mc_rresp),
    .c0_cmd_valid(c_cmd_valid[0][0]), .c0_cmd_ready(c_cmd_ready[0][0]), .c0_cmd_we(c_cmd_we[0][0]),
    .c0_cmd_addr(c_cmd_addr[0][0]), .c0_wdata_valid(c_wdata_valid[0][0]),
    .c0_wdata_ready(c_wdata_ready[0][0]), .c0_wdata_data(c_wdata_data[0][0]),
    .c0_wdata_we(c_wdata_we[0][0]), .c0_rdata_valid(c_rdata_valid[0][0]), .c0_rdata_ready(1'b1),
    .c0_rdata_data(c_rdata_data[0][0]), .c0_ready(c_ready[0]),
    .c0b_cmd_valid(c_cmd_valid[0][1]), .c0b_cmd_ready(c_cmd_ready[0][1]), .c0b_cmd_we(c_cmd_we[0][1]),
    .c0b_cmd_addr(c_cmd_addr[0][1]), .c0b_wdata_valid(c_wdata_valid[0][1]),
    .c0b_wdata_ready(c_wdata_ready[0][1]), .c0b_wdata_data(c_wdata_data[0][1]),
    .c0b_wdata_we(c_wdata_we[0][1]), .c0b_rdata_valid(c_rdata_valid[0][1]), .c0b_rdata_ready(1'b1),
    .c0b_rdata_data(c_rdata_data[0][1]),
    .c1_cmd_valid(c_cmd_valid[1][0]), .c1_cmd_ready(c_cmd_ready[1][0]), .c1_cmd_we(c_cmd_we[1][0]),
    .c1_cmd_addr(c_cmd_addr[1][0]), .c1_wdata_valid(c_wdata_valid[1][0]),
    .c1_wdata_ready(c_wdata_ready[1][0]), .c1_wdata_data(c_wdata_data[1][0]),
    .c1_wdata_we(c_wdata_we[1][0]), .c1_rdata_valid(c_rdata_valid[1][0]), .c1_rdata_ready(1'b1),
    .c1_rdata_data(c_rdata_data[1][0]), .c1_ready(c_ready[1]),
    .c1b_cmd_valid(c_cmd_valid[1][1]), .c1b_cmd_ready(c_cmd_ready[1][1]), .c1b_cmd_we(c_cmd_we[1][1]),
    .c1b_cmd_addr(c_cmd_addr[1][1]), .c1b_wdata_valid(c_wdata_valid[1][1]),
    .c1b_wdata_ready(c_wdata_ready[1][1]), .c1b_wdata_data(c_wdata_data[1][1]),
    .c1b_wdata_we(c_wdata_we[1][1]), .c1b_rdata_valid(c_rdata_valid[1][1]), .c1b_rdata_ready(1'b1),
    .c1b_rdata_data(c_rdata_data[1][1]),
    .ddram0_dq, .ddram0_dqs_p, .ddram0_dqs_n, .ddram0_a, .ddram0_ba, .ddram0_ras_n,
    .ddram0_cas_n, .ddram0_we_n, .ddram0_reset_n, .ddram0_clk_p, .ddram0_clk_n, .ddram0_cke,
    .ddram0_cs_n, .ddram0_odt,
    .ddram1_dq, .ddram1_dqs_p, .ddram1_dqs_n, .ddram1_a, .ddram1_ba, .ddram1_ras_n,
    .ddram1_cas_n, .ddram1_we_n, .ddram1_reset_n, .ddram1_clk_p, .ddram1_clk_n, .ddram1_cke,
    .ddram1_cs_n, .ddram1_odt);
  assign calib = c_ready;                   // STATUS CALIB0/1 (sys_clk; otpu_board syncs them)

  // I2C: each line released (high-Z, pulled up) unless its I2C_CTRL bit drives it low
  logic [3:0] i2c_lo, i2c_lvl;
  IOBUF u_iob_scl0 (.IO(lm73_scl), .I(1'b0), .T(!i2c_lo[0]), .O(i2c_lvl[0]));
  IOBUF u_iob_sda0 (.IO(lm73_sda), .I(1'b0), .T(!i2c_lo[1]), .O(i2c_lvl[1]));
  IOBUF u_iob_scl1 (.IO(smb_scl),  .I(1'b0), .T(!i2c_lo[2]), .O(i2c_lvl[2]));
  IOBUF u_iob_sda1 (.IO(smb_sda),  .I(1'b0), .T(!i2c_lo[3]), .O(i2c_lvl[3]));

  // ---- the accelerator and XDMA on the channels
  logic [2:0] board_led;
  otpu_native_sys #(.MCOLS(MCOLS), .ACT_ROWS(ACT_ROWS), .VPU_CL(VPU_CL), .MXU_IMPL(MXU_IMPL),
                    .LANES(LANES),
                    .ULANES(ULANES), .CORE_KHZ(CORE_KHZ), .BUILD_ID(BUILD_ID), .DDR_MTS(DDR_MTS),
    .DSTEP(DSTEP), .HOSTCAL(1'b1), .HAS_TEMP(1'b0), .XREG(PCIE_GEN == 2)) u_sys (
    .clk(core_clk), .rst(core_rst), .xclk(xdma_aclk), .xrst,
    .calib, .temp(12'b0), .led(board_led), .i2c_lo, .i2c_pin({lm73_alert_n, i2c_lvl}),
    .s_ctl_awaddr(ctl_awaddr[11:0]), .s_ctl_awvalid(ctl_awvalid), .s_ctl_awready(ctl_awready),
    .s_ctl_wdata(ctl_wdata), .s_ctl_wstrb(ctl_wstrb), .s_ctl_wvalid(ctl_wvalid),
    .s_ctl_wready(ctl_wready), .s_ctl_bresp(ctl_bresp), .s_ctl_bvalid(ctl_bvalid),
    .s_ctl_bready(ctl_bready), .s_ctl_araddr(ctl_araddr[11:0]), .s_ctl_arvalid(ctl_arvalid),
    .s_ctl_arready(ctl_arready), .s_ctl_rdata(ctl_rdata), .s_ctl_rresp(ctl_rresp),
    .s_ctl_rvalid(ctl_rvalid), .s_ctl_rready(ctl_rready),
    .x_awvalid(dm_awvalid), .x_awready(dm_awready), .x_awid(dm_awid), .x_awaddr(dm_awaddr[31:0]),
    .x_awlen(dm_awlen), .x_wvalid(dm_wvalid), .x_wready(dm_wready), .x_wdata(dm_wdata),
    .x_wstrb(dm_wstrb), .x_wlast(dm_wlast), .x_bvalid(dm_bvalid), .x_bready(dm_bready),
    .x_bid(dm_bid), .x_bresp(dm_bresp), .x_arvalid(dm_arvalid), .x_arready(dm_arready),
    .x_arid(dm_arid), .x_araddr(dm_araddr[31:0]), .x_arlen(dm_arlen), .x_rvalid(dm_rvalid),
    .x_rready(dm_rready), .x_rid(dm_rid), .x_rdata(dm_rdata), .x_rresp(dm_rresp),
    .x_rlast(dm_rlast),
    .uclk({2{ld_sys_clk}}), .urst({2{ld_sys_rst}}),
    .c_cmd_valid, .c_cmd_ready, .c_cmd_we, .c_cmd_addr, .c_wdata_valid,
    .c_wdata_ready, .c_wdata_data, .c_wdata_we, .c_rdata_valid, .c_rdata_data);

  // Green shows both physical calibration flags, red the heartbeat, yellow compute.
  assign led = {board_led[2] | board_led[1], &calib, board_led[0]};
endmodule
