//*****************************************************************************
// (c) Copyright 2023 Advanced Micro Devices, Inc. All rights reserved.
//
// This file contains confidential and proprietary information
// of AMD and is protected under U.S. and international copyright
// and other intellectual property laws.
//
// DISCLAIMER
// This disclaimer is not a license and does not grant any
// rights to the materials distributed herewith. Except as
// otherwise provided in a valid license issued to you by
// AMD, and to the maximum extent permitted by applicable
// law: (1) THESE MATERIALS ARE MADE AVAILABLE "AS IS" AND
// WITH ALL FAULTS, AND AMD HEREBY DISCLAIMS ALL WARRANTIES
// AND CONDITIONS, EXPRESS, IMPLIED, OR STATUTORY, INCLUDING
// BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, NON-
// INFRINGEMENT, OR FITNESS FOR ANY PARTICULAR PURPOSE; and
// (2) AMD shall not be liable (whether in contract or tort,
// including negligence, or under any other theory of
// liability) for any loss or damage of any kind or nature
// related to, arising under or in connection with these
// materials, including for any direct, or any indirect,
// special, incidental, or consequential loss or damage
// (including loss of data, profits, goodwill, or any type of
// loss or damage suffered as a result of any action brought
// by a third party) even if such damage or loss was
// reasonably foreseeable or AMD had been advised of the
// possibility of the same.
//
// CRITICAL APPLICATIONS
// AMD products are not designed or intended to be fail-
// safe, or for use in any application requiring fail-safe
// performance, such as life-support or safety devices or
// systems, Class III medical devices, nuclear facilities,
// applications related to the deployment of airbags, or any
// other applications that could lead to death, personal
// injury, or severe property or environmental damage
// (individually and collectively, "Critical
// Applications"). Customer assumes the sole risk and
// liability of any use of AMD products in Critical
// Applications, subject only to applicable laws and
// regulations governing limitations on product liability.
//
// THIS COPYRIGHT NOTICE AND DISCLAIMER MUST BE RETAINED AS
// PART OF THIS FILE AT ALL TIMES.
//
//*****************************************************************************
//   ____  ____
//  /   /\/   /
// /___/  \  /    Vendor             : AMD
// \   \   \/     Version            : 4.2
//  \   \         Application        : MIG
//  /   /         Filename           : example_top.v
// /___/   /\     Date Last Modified : $Date: 2011/06/02 08:35:03 $
// \   \  /  \    Date Created       : Tue Sept 21 2010
//  \___\/\___\
//
// Device           : 7 Series
// Design Name      : DDR3 SDRAM
// Purpose          :
//   Top-level  module. This module serves as an example,
//   and allows the user to synthesize a self-contained design,
//   which they can be used to test their hardware.
//   In addition to the memory controller, the module instantiates:
//     1. Synthesizable testbench - used to model user's backend logic
//        and generate different traffic patterns
// Reference        :
// Revision History :
//*****************************************************************************

//`define SKIP_CALIB
`timescale 1ps/1ps

module ypcb_ramtest_litedram #
  (

   //***************************************************************************
   // Traffic Gen related parameters
   //***************************************************************************
   parameter C0_PORT_MODE             = "BI_MODE",
   parameter C0_DATA_MODE             = 4'd2,
   parameter C0_TST_MEM_INSTR_MODE    = "FIXED_INSTR_R_MODE",
   parameter C0_EYE_TEST              = "FALSE",
                                     // set EYE_TEST = "TRUE" to probe memory
                                     // signals. Traffic Generator will only
                                     // write to one single location and no
                                     // read transactions will be generated.
   parameter C0_DATA_PATTERN          = "DGEN_ALL",
                                      // For small devices, choose one only.
                                      // For large device, choose "DGEN_ALL"
                                      // "DGEN_HAMMER", "DGEN_WALKING1",
                                      // "DGEN_WALKING0","DGEN_ADDR","
                                      // "DGEN_NEIGHBOR","DGEN_PRBS","DGEN_ALL"
   parameter C0_CMD_PATTERN           = "CGEN_SEQUENTIAL",
                                      // "CGEN_PRBS","CGEN_FIXED","CGEN_BRAM",
                                      // "CGEN_SEQUENTIAL", "CGEN_ALL"
   parameter C0_CMD_WDT               = 'h3FF,
   parameter C0_WR_WDT                = 'h1FFF,
   parameter C0_RD_WDT                = 'h3FF,
   parameter C0_SEL_VICTIM_LINE       = 0,
   parameter C0_BEGIN_ADDRESS         = 32'h00000000,
   parameter C0_END_ADDRESS           = 32'h0fffffff,
   parameter C0_PRBS_EADDR_MASK_POS   = 32'hf0000000,

   //***************************************************************************
   // The following parameters refer to width of various ports
   //***************************************************************************
   parameter C0_CK_WIDTH              = 1,
                                     // # of CK/CK# outputs to memory.
   parameter C0_nCS_PER_RANK          = 1,
                                     // # of unique CS outputs per rank for phy
   parameter C0_CKE_WIDTH             = 1,
                                     // # of CKE outputs to memory.
   parameter C0_ODT_WIDTH             = 1,
                                     // # of ODT outputs to memory.
   parameter C0_BANK_WIDTH            = 3,
                                     // # of memory Bank Address bits.
   parameter C0_COL_WIDTH             = 10,
                                     // # of memory Column Address bits.
   parameter C0_CS_WIDTH              = 1,
                                     // # of unique CS outputs to memory.
   parameter C0_DQ_WIDTH              = 72,
                                     // # of DQ (data)
   parameter C0_DQS_WIDTH             = 9,
   parameter C0_DQS_CNT_WIDTH         = 4,
                                     // = ceil(log2(DQS_WIDTH))
   parameter C0_DRAM_WIDTH            = 8,
                                     // # of DQ per DQS
   parameter C0_ECC                   = "ON",
   parameter C0_ECC_TEST              = "OFF",
   //parameter C0_nBANK_MACHS           = 4,
   parameter C0_nBANK_MACHS           = 4,
   parameter C0_RANKS                 = 1,
                                     // # of Ranks.
   parameter C0_ROW_WIDTH             = 15,
                                     // # of memory Row Address bits.
   parameter C0_ADDR_WIDTH            = 29,
                                     // # = RANK_WIDTH + BANK_WIDTH
                                     //     + ROW_WIDTH + COL_WIDTH;
                                     // Chip Select is always tied to low for
                                     // single rank devices

   //***************************************************************************
   // The following parameters are mode register settings
   //***************************************************************************
   parameter C0_BURST_MODE            = "8",
                                     // DDR3 SDRAM:
                                     // Burst Length (Mode Register 0).
                                     // # = "8", "4", "OTF".
                                     // DDR2 SDRAM:
                                     // Burst Length (Mode Register).
                                     // # = "8", "4".

   
   //***************************************************************************
   // The following parameters are multiplier and divisor factors for PLLE2.
   // Based on the selected design frequency these parameters vary.
   //***************************************************************************
   parameter C0_CLKIN_PERIOD          = 5000,
                                     // Input Clock Period
   parameter C0_CLKFBOUT_MULT         = 4,
                                     // write PLL VCO multiplier
   parameter C0_DIVCLK_DIVIDE         = 1,
                                     // write PLL VCO divisor
   parameter C0_CLKOUT0_PHASE         = 0.0,
                                     // Phase for PLL output clock (CLKOUT0)
   parameter C0_CLKOUT0_DIVIDE        = 1,
                                     // VCO output divisor for PLL output clock (CLKOUT0)
   parameter C0_CLKOUT1_DIVIDE        = 2,
                                     // VCO output divisor for PLL output clock (CLKOUT1)
   parameter C0_CLKOUT2_DIVIDE        = 32,
                                     // VCO output divisor for PLL output clock (CLKOUT2)
   parameter C0_CLKOUT3_DIVIDE        = 8,
                                     // VCO output divisor for PLL output clock (CLKOUT3)
   parameter C0_MMCM_VCO              = 800,
                                     // Max Freq (MHz) of MMCM VCO
   parameter C0_MMCM_MULT_F           = 8,
                                     // write MMCM VCO multiplier
   parameter C0_MMCM_DIVCLK_DIVIDE    = 1,
                                     // write MMCM VCO divisor

   //***************************************************************************
   // Simulation parameters
   //***************************************************************************
   parameter C0_SIMULATION            = "FALSE",
                                     // Should be TRUE during design simulations and
                                     // FALSE during implementations

   //***************************************************************************
   // IODELAY and PHY related parameters
   //***************************************************************************
   parameter C0_TCQ                   = 100,
   
   parameter DRAM_TYPE             = "DDR3",

   
   //***************************************************************************
   // System clock frequency parameters
   //***************************************************************************
   parameter C0_nCK_PER_CLK           = 4,
                                     // # of memory CKs per fabric CLK

   

   //***************************************************************************
   // Debug parameters
   //***************************************************************************
   parameter C0_DEBUG_PORT            = "OFF",
                                     // # = "ON" Enable debug signals/controls.
                                     //   = "OFF" Disable debug signals/controls.
      
   //***************************************************************************
   // Traffic Gen related parameters
   //***************************************************************************
   parameter C1_PORT_MODE             = "BI_MODE",
   parameter C1_DATA_MODE             = 4'd2,
   parameter C1_TST_MEM_INSTR_MODE    = "FIXED_INSTR_R_MODE",
   parameter C1_EYE_TEST              = "FALSE",
                                     // set EYE_TEST = "TRUE" to probe memory
                                     // signals. Traffic Generator will only
                                     // write to one single location and no
                                     // read transactions will be generated.
   parameter C1_DATA_PATTERN          = "DGEN_ALL",
                                      // For small devices, choose one only.
                                      // For large device, choose "DGEN_ALL"
                                      // "DGEN_HAMMER", "DGEN_WALKING1",
                                      // "DGEN_WALKING0","DGEN_ADDR","
                                      // "DGEN_NEIGHBOR","DGEN_PRBS","DGEN_ALL"
   parameter C1_CMD_PATTERN           = "CGEN_SEQUENTIAL",
                                      // "CGEN_PRBS","CGEN_FIXED","CGEN_BRAM",
                                      // "CGEN_SEQUENTIAL", "CGEN_ALL"
   parameter C1_CMD_WDT               = 'h3FF,
   parameter C1_WR_WDT                = 'h1FFF,
   parameter C1_RD_WDT                = 'h3FF,
   parameter C1_SEL_VICTIM_LINE       = 0,
   parameter C1_BEGIN_ADDRESS         = 32'h00000000,
   parameter C1_END_ADDRESS           = 32'h0fffffff,
   parameter C1_PRBS_EADDR_MASK_POS   = 32'hf0000000,

   //***************************************************************************
   // The following parameters refer to width of various ports
   //***************************************************************************
   parameter C1_CK_WIDTH              = 1,
                                     // # of CK/CK# outputs to memory.
   parameter C1_nCS_PER_RANK          = 1,
                                     // # of unique CS outputs per rank for phy
   parameter C1_CKE_WIDTH             = 1,
                                     // # of CKE outputs to memory.
   parameter C1_ODT_WIDTH             = 1,
                                     // # of ODT outputs to memory.
   parameter C1_BANK_WIDTH            = 3,
                                     // # of memory Bank Address bits.
   parameter C1_COL_WIDTH             = 10,
                                     // # of memory Column Address bits.
   parameter C1_CS_WIDTH              = 1,
                                     // # of unique CS outputs to memory.
   parameter C1_DQ_WIDTH              = 72,
                                     // # of DQ (data)
   parameter C1_DQS_WIDTH             = 9,
   parameter C1_DQS_CNT_WIDTH         = 4,
                                     // = ceil(log2(DQS_WIDTH))
   parameter C1_DRAM_WIDTH            = 8,
                                     // # of DQ per DQS
   parameter C1_ECC                   = "ON",
   parameter C1_ECC_TEST              = "OFF",
   //parameter C1_nBANK_MACHS           = 4,
   parameter C1_nBANK_MACHS           = 4,
   parameter C1_RANKS                 = 1,
                                     // # of Ranks.
   parameter C1_ROW_WIDTH             = 15,
                                     // # of memory Row Address bits.
   parameter C1_ADDR_WIDTH            = 29,
                                     // # = RANK_WIDTH + BANK_WIDTH
                                     //     + ROW_WIDTH + COL_WIDTH;
                                     // Chip Select is always tied to low for
                                     // single rank devices

   //***************************************************************************
   // The following parameters are mode register settings
   //***************************************************************************
   parameter C1_BURST_MODE            = "8",
                                     // DDR3 SDRAM:
                                     // Burst Length (Mode Register 0).
                                     // # = "8", "4", "OTF".
                                     // DDR2 SDRAM:
                                     // Burst Length (Mode Register).
                                     // # = "8", "4".

   
   //***************************************************************************
   // The following parameters are multiplier and divisor factors for PLLE2.
   // Based on the selected design frequency these parameters vary.
   //***************************************************************************
   parameter C1_CLKIN_PERIOD          = 5000,
                                     // Input Clock Period
   parameter C1_CLKFBOUT_MULT         = 4,
                                     // write PLL VCO multiplier
   parameter C1_DIVCLK_DIVIDE         = 1,
                                     // write PLL VCO divisor
   parameter C1_CLKOUT0_PHASE         = 0.0,
                                     // Phase for PLL output clock (CLKOUT0)
   parameter C1_CLKOUT0_DIVIDE        = 1,
                                     // VCO output divisor for PLL output clock (CLKOUT0)
   parameter C1_CLKOUT1_DIVIDE        = 2,
                                     // VCO output divisor for PLL output clock (CLKOUT1)
   parameter C1_CLKOUT2_DIVIDE        = 32,
                                     // VCO output divisor for PLL output clock (CLKOUT2)
   parameter C1_CLKOUT3_DIVIDE        = 8,
                                     // VCO output divisor for PLL output clock (CLKOUT3)
   parameter C1_MMCM_VCO              = 800,
                                     // Max Freq (MHz) of MMCM VCO
   parameter C1_MMCM_MULT_F           = 8,
                                     // write MMCM VCO multiplier
   parameter C1_MMCM_DIVCLK_DIVIDE    = 1,
                                     // write MMCM VCO divisor

   //***************************************************************************
   // Simulation parameters
   //***************************************************************************
   parameter C1_SIMULATION            = "FALSE",
                                     // Should be TRUE during design simulations and
                                     // FALSE during implementations

   //***************************************************************************
   // IODELAY and PHY related parameters
   //***************************************************************************
   parameter C1_TCQ                   = 100,
   

   
   //***************************************************************************
   // System clock frequency parameters
   //***************************************************************************
   parameter C1_nCK_PER_CLK           = 4,
                                     // # of memory CKs per fabric CLK

   

   //***************************************************************************
   // Debug parameters
   //***************************************************************************
   parameter C1_DEBUG_PORT            = "OFF",
                                     // # = "ON" Enable debug signals/controls.
                                     //   = "OFF" Disable debug signals/controls.
      
   parameter RST_ACT_LOW           = 1
                                     // =1 for active low reset,
                                     // =0 for active high.
   )
  (

   // Inouts
   input SYS_CLK,
   output [2:0] led,
   inout [71:0]                         ddram0_dq,
   inout [8:0]                        ddram0_dqs_n,
   inout [8:0]                        ddram0_dqs_p,

   // Outputs
   output [14:0]                       ddram0_a,
   output [2:0]                      ddram0_ba,
   output                                       ddram0_ras_n,
   output                                       ddram0_cas_n,
   output                                       ddram0_we_n,
   output                                       ddram0_reset_n,
   output                         ddram0_clk_p,
   output                         ddram0_clk_n,
   output                        ddram0_cke,
   
   output            ddram0_cs_n,
   
   
   output                        ddram0_odt,
   

   // Inputs
   
   // Differential system clocks
   

   
      
   // Inouts
   inout [71:0]                         ddram1_dq,
   inout [8:0]                        ddram1_dqs_n,
   inout [8:0]                        ddram1_dqs_p,

   // Outputs
   output [14:0]                       ddram1_a,
   output [2:0]                      ddram1_ba,
   output                                       ddram1_ras_n,
   output                                       ddram1_cas_n,
   output                                       ddram1_we_n,
   output                                       ddram1_reset_n,
   output                         ddram1_clk_p,
   output                         ddram1_clk_n,
   output                        ddram1_cke,
   
   output            ddram1_cs_n,
   
   
   output                        ddram1_odt
   

   // Inputs
   
   // Differential system clocks
   

   
   
   
      

   // System reset - Default polarity of sys_rst pin is Active Low.
   // System reset polarity will change based on the option 
   // selected in GUI.
   );

function integer clogb2 (input integer size);
    begin
      size = size - 1;
      for (clogb2=1; size>1; clogb2=clogb2+1)
        size = size >> 1;
    end
  endfunction // clogb2

  function integer STR_TO_INT;
    input [7:0] in;
    begin
      if(in == "8")
        STR_TO_INT = 8;
      else if(in == "4")
        STR_TO_INT = 4;
      else
        STR_TO_INT = 0;
    end
  endfunction


  localparam C0_DATA_WIDTH            = 64;
  localparam C0_RANK_WIDTH = clogb2(C0_RANKS);
  localparam C0_PAYLOAD_WIDTH         = (C0_ECC_TEST == "OFF") ? C0_DATA_WIDTH : C0_DQ_WIDTH;
  localparam C0_BURST_LENGTH          = STR_TO_INT(C0_BURST_MODE);
  localparam C0_APP_DATA_WIDTH        = 2 * C0_nCK_PER_CLK * C0_PAYLOAD_WIDTH;
  localparam C0_APP_MASK_WIDTH        = C0_APP_DATA_WIDTH / 8;

  //***************************************************************************
  // Traffic Gen related parameters (derived)
  //***************************************************************************
  localparam  C0_TG_ADDR_WIDTH = ((C0_CS_WIDTH == 1) ? 0 : C0_RANK_WIDTH)
                                 + C0_BANK_WIDTH + C0_ROW_WIDTH + C0_COL_WIDTH;
  localparam C0_MASK_SIZE             = C0_DATA_WIDTH/8;
      
  localparam C1_DATA_WIDTH            = 64;
  localparam C1_RANK_WIDTH = clogb2(C1_RANKS);
  localparam C1_PAYLOAD_WIDTH         = (C1_ECC_TEST == "OFF") ? C1_DATA_WIDTH : C1_DQ_WIDTH;
  localparam C1_BURST_LENGTH          = STR_TO_INT(C1_BURST_MODE);
  localparam C1_APP_DATA_WIDTH        = 2 * C1_nCK_PER_CLK * C1_PAYLOAD_WIDTH;
  localparam C1_APP_MASK_WIDTH        = C1_APP_DATA_WIDTH / 8;

  //***************************************************************************
  // Traffic Gen related parameters (derived)
  //***************************************************************************
  localparam  C1_TG_ADDR_WIDTH = ((C1_CS_WIDTH == 1) ? 0 : C1_RANK_WIDTH)
                                 + C1_BANK_WIDTH + C1_ROW_WIDTH + C1_COL_WIDTH;
  localparam C1_MASK_SIZE             = C1_DATA_WIDTH/8;
      

  // Wire declarations
      
  wire [(2*C0_nCK_PER_CLK)-1:0]              c0_app_ecc_multiple_err;
  wire [(2*C0_nCK_PER_CLK)-1:0]              c0_app_ecc_single_err;
  wire [C0_ADDR_WIDTH-1:0]                 c0_app_addr;
  wire [2:0]                            c0_app_cmd;
  wire                                  c0_app_en;
  wire                                  c0_app_rdy;
  wire [C0_APP_DATA_WIDTH-1:0]             c0_app_rd_data;
  wire                                  c0_app_rd_data_end;
  wire                                  c0_app_rd_data_valid;
  wire [C0_APP_DATA_WIDTH-1:0]             c0_app_wdf_data;
  wire                                  c0_app_wdf_end;
  wire [C0_APP_MASK_WIDTH-1:0]             c0_app_wdf_mask;
  wire                                  c0_app_wdf_rdy;
  wire                                  c0_app_sr_active;
  wire                                  c0_app_ref_ack;
  wire                                  c0_app_zq_ack;
  wire                                  c0_app_wdf_wren;
  wire [(64+(2*C0_APP_DATA_WIDTH))-1:0]      c0_error_status;
  wire [(C0_PAYLOAD_WIDTH/8)-1:0] c0_cumlative_dq_lane_error;
  wire                                  c0_mem_pattern_init_done;
  wire [47:0]                           c0_tg_wr_data_counts;
  wire [47:0]                           c0_tg_rd_data_counts;
  wire                                  c0_modify_enable_sel;
  wire [2:0]                            c0_data_mode_manual_sel;
  wire [2:0]                            c0_addr_mode_manual_sel;
  wire [C0_APP_DATA_WIDTH-1:0]             c0_cmp_data;
  reg [63:0]                            c0_cmp_data_r;
  wire                                  c0_cmp_data_valid;
  reg                                   c0_cmp_data_valid_r;
  wire                                  c0_cmp_error;
  wire [(C0_PAYLOAD_WIDTH/8)-1:0]            c0_dq_error_bytelane_cmp;

  wire                                  c0_clk;
  wire                                  c0_rst;

  wire                                  c0_dbg_sel_pi_incdec;
  wire                                  c0_dbg_pi_f_inc;
  wire                                  c0_dbg_pi_f_dec;
  wire                                  c0_dbg_sel_po_incdec;
  wire                                  c0_dbg_po_f_inc;
  wire                                  c0_dbg_po_f_stg23_sel;
  wire                                  c0_dbg_po_f_dec;
  
  
  wire                                  c0_vio_modify_enable;
  wire [3:0]                            c0_vio_data_mode_value;
  wire                                  c0_vio_pause_traffic;
  wire [2:0]                            c0_vio_addr_mode_value;
  wire [3:0]                            c0_vio_instr_mode_value;
  wire [1:0]                            c0_vio_bl_mode_value;
  wire [9:0]                            c0_vio_fixed_bl_value;
  wire [2:0]                            c0_vio_fixed_instr_value;
  wire                                  c0_vio_data_mask_gen;
  wire                                  c0_vio_tg_rst;
  wire                                  c0_vio_dbg_sel_pi_incdec;
  wire                                  c0_vio_dbg_pi_f_inc;
  wire                                  c0_vio_dbg_pi_f_dec;
  wire                                  c0_vio_dbg_sel_po_incdec;
  wire                                  c0_vio_dbg_po_f_inc;
  wire                                  c0_vio_dbg_po_f_stg23_sel;
  wire                                  c0_vio_dbg_po_f_dec;
     
  wire [11:0]                           c0_device_temp;
  
`ifdef SKIP_CALIB
  // skip calibration wires
  wire                          c0_calib_tap_req;
  reg                           c0_calib_tap_load;
  reg [6:0]                     c0_calib_tap_addr;
  reg [7:0]                     c0_calib_tap_val;
  reg                           c0_calib_tap_load_done;
`endif
      
    // Wire declarations
      
  wire [(2*C1_nCK_PER_CLK)-1:0]              c1_app_ecc_multiple_err;
  wire [(2*C1_nCK_PER_CLK)-1:0]              c1_app_ecc_single_err;
  wire [C1_ADDR_WIDTH-1:0]                 c1_app_addr;
  wire [2:0]                            c1_app_cmd;
  wire                                  c1_app_en;
  wire                                  c1_app_rdy;
  wire [C1_APP_DATA_WIDTH-1:0]             c1_app_rd_data;
  wire                                  c1_app_rd_data_end;
  wire                                  c1_app_rd_data_valid;
  wire [C1_APP_DATA_WIDTH-1:0]             c1_app_wdf_data;
  wire                                  c1_app_wdf_end;
  wire [C1_APP_MASK_WIDTH-1:0]             c1_app_wdf_mask;
  wire                                  c1_app_wdf_rdy;
  wire                                  c1_app_sr_active;
  wire                                  c1_app_ref_ack;
  wire                                  c1_app_zq_ack;
  wire                                  c1_app_wdf_wren;
  wire [(64+(2*C1_APP_DATA_WIDTH))-1:0]      c1_error_status;
  wire [(C1_PAYLOAD_WIDTH/8)-1:0] c1_cumlative_dq_lane_error;
  wire                                  c1_mem_pattern_init_done;
  wire [47:0]                           c1_tg_wr_data_counts;
  wire [47:0]                           c1_tg_rd_data_counts;
  wire                                  c1_modify_enable_sel;
  wire [2:0]                            c1_data_mode_manual_sel;
  wire [2:0]                            c1_addr_mode_manual_sel;
  wire [C1_APP_DATA_WIDTH-1:0]             c1_cmp_data;
  reg [63:0]                            c1_cmp_data_r;
  wire                                  c1_cmp_data_valid;
  reg                                   c1_cmp_data_valid_r;
  wire                                  c1_cmp_error;
  wire [(C1_PAYLOAD_WIDTH/8)-1:0]            c1_dq_error_bytelane_cmp;

  wire                                  c1_clk;
  wire                                  c1_rst;

  wire                                  c1_dbg_sel_pi_incdec;
  wire                                  c1_dbg_pi_f_inc;
  wire                                  c1_dbg_pi_f_dec;
  wire                                  c1_dbg_sel_po_incdec;
  wire                                  c1_dbg_po_f_inc;
  wire                                  c1_dbg_po_f_stg23_sel;
  wire                                  c1_dbg_po_f_dec;
  
  
  wire                                  c1_vio_modify_enable;
  wire [3:0]                            c1_vio_data_mode_value;
  wire                                  c1_vio_pause_traffic;
  wire [2:0]                            c1_vio_addr_mode_value;
  wire [3:0]                            c1_vio_instr_mode_value;
  wire [1:0]                            c1_vio_bl_mode_value;
  wire [9:0]                            c1_vio_fixed_bl_value;
  wire [2:0]                            c1_vio_fixed_instr_value;
  wire                                  c1_vio_data_mask_gen;
  wire                                  c1_vio_tg_rst;
  wire                                  c1_vio_dbg_sel_pi_incdec;
  wire                                  c1_vio_dbg_pi_f_inc;
  wire                                  c1_vio_dbg_pi_f_dec;
  wire                                  c1_vio_dbg_sel_po_incdec;
  wire                                  c1_vio_dbg_po_f_inc;
  wire                                  c1_vio_dbg_po_f_stg23_sel;
  wire                                  c1_vio_dbg_po_f_dec;
     
  wire [11:0]                           c1_device_temp;
  
`ifdef SKIP_CALIB
  // skip calibration wires
  wire                          c1_calib_tap_req;
  reg                           c1_calib_tap_load;
  reg [6:0]                     c1_calib_tap_addr;
  reg [7:0]                     c1_calib_tap_val;
  reg                           c1_calib_tap_load_done;
`endif
      
  

//***************************************************************************
	wire                            c0_init_calib_complete;
	wire                            c0_tg_compare_error;
	wire                            c1_init_calib_complete;
	wire                            c1_tg_compare_error;

  assign init_calib_complete = c0_init_calib_complete & c1_init_calib_complete;
  assign tg_compare_error = c0_tg_compare_error | c1_tg_compare_error;



      
      
// Start of User Design top instance
//***************************************************************************
// The User design is instantiated below. The memory interface ports are
// connected to the top-level and the application interface ports are
// connected to the traffic generator module. This provides a reference
// for connecting the memory controller to system.
//***************************************************************************


  wire ld_sys_rst;
  wire [1:0] ld_traffic_reset, ld_traffic_pause;
  wire [1:0] ld_native_busy, ld_protocol_error;
  wire [3:0] ld_pattern, ld_instruction;
  wire [31:0] ld_fixed_data;
  wire [15:0] ld_awaddr, ld_araddr;
  wire [31:0] ld_wdata, ld_rdata;
  wire [3:0] ld_wstrb;
  wire [1:0] ld_bresp, ld_rresp;
  wire ld_awvalid, ld_awready, ld_wvalid, ld_wready, ld_bvalid, ld_bready;
  wire ld_arvalid, ld_arready, ld_rvalid, ld_rready;
  assign c1_clk = c0_clk;

  wire c0_native_cmd_ready;
  wire c0_native_cmd_valid, c0_native_write;
  wire [24:0] c0_native_address;
  assign c0_rst = ld_sys_rst | ld_traffic_reset[0];
  assign c0_app_ecc_single_err = 0;
  assign c0_app_ecc_multiple_err = 0;
  ramtest_litedram_command_bridge u_cmd_bridge0 (
    .clk(c0_clk), .rst(c0_rst), .app_valid(c0_app_en), .app_ready(c0_app_rdy),
    .app_command(c0_app_cmd), .app_address(c0_app_addr),
    .native_valid(c0_native_cmd_valid), .native_ready(c0_native_cmd_ready),
    .native_write(c0_native_write), .native_address(c0_native_address),
    .busy(ld_native_busy[0]), .protocol_error(ld_protocol_error[0]));

  wire c1_native_cmd_ready;
  wire c1_native_cmd_valid, c1_native_write;
  wire [24:0] c1_native_address;
  assign c1_rst = ld_sys_rst | ld_traffic_reset[1];
  assign c1_app_ecc_single_err = 0;
  assign c1_app_ecc_multiple_err = 0;
  ramtest_litedram_command_bridge u_cmd_bridge1 (
    .clk(c1_clk), .rst(c1_rst), .app_valid(c1_app_en), .app_ready(c1_app_rdy),
    .app_command(c1_app_cmd), .app_address(c1_app_addr),
    .native_valid(c1_native_cmd_valid), .native_ready(c1_native_cmd_ready),
    .native_write(c1_native_write), .native_address(c1_native_address),
    .busy(ld_native_busy[1]), .protocol_error(ld_protocol_error[1]));

  otpu_litedram u_ld (
    .clk50g(control_clk),
    .rst(1'b0),
    .sys_clk(c0_clk),
    .sys_rst(ld_sys_rst),
    .ctl_clk(c0_clk),
    .ctl_rst(ld_sys_rst),
    .ctl_awaddr(ld_awaddr),
    .ctl_araddr(ld_araddr),
    .ctl_wdata(ld_wdata),
    .ctl_rdata(ld_rdata),
    .ctl_wstrb(ld_wstrb),
    .ctl_bresp(ld_bresp),
    .ctl_rresp(ld_rresp),
    .ctl_awvalid(ld_awvalid),
    .ctl_awready(ld_awready),
    .ctl_wvalid(ld_wvalid),
    .ctl_wready(ld_wready),
    .ctl_bvalid(ld_bvalid),
    .ctl_bready(ld_bready),
    .ctl_arvalid(ld_arvalid),
    .ctl_arready(ld_arready),
    .ctl_rvalid(ld_rvalid),
    .ctl_rready(ld_rready),
    .c0_cmd_valid(c0_native_cmd_valid),
    .c0_cmd_ready(c0_native_cmd_ready),
    .c0_cmd_we(c0_native_write),
    .c0_cmd_addr(c0_native_address),
    .c0_wdata_valid(c0_app_wdf_wren),
    .c0_wdata_ready(c0_app_wdf_rdy),
    .c0_wdata_data(c0_app_wdf_data),
    .c0_wdata_we(~c0_app_wdf_mask),
    .c0_rdata_valid(c0_app_rd_data_valid),
    .c0_rdata_ready(1'b1),
    .c0_rdata_data(c0_app_rd_data),
    .c0_ready(c0_init_calib_complete),
    .c0b_cmd_valid(1'b0),
    .c0b_cmd_ready(),
    .c0b_cmd_we(1'b0),
    .c0b_cmd_addr(25'b0),
    .c0b_wdata_valid(1'b0),
    .c0b_wdata_ready(),
    .c0b_wdata_data(512'b0),
    .c0b_wdata_we(64'b0),
    .c0b_rdata_valid(),
    .c0b_rdata_ready(1'b1),
    .c0b_rdata_data(),
    .ddram0_dq(ddram0_dq),
    .ddram0_dqs_p(ddram0_dqs_p),
    .ddram0_dqs_n(ddram0_dqs_n),
    .ddram0_a(ddram0_a),
    .ddram0_ba(ddram0_ba),
    .ddram0_ras_n(ddram0_ras_n),
    .ddram0_cas_n(ddram0_cas_n),
    .ddram0_we_n(ddram0_we_n),
    .ddram0_reset_n(ddram0_reset_n),
    .ddram0_clk_p(ddram0_clk_p),
    .ddram0_clk_n(ddram0_clk_n),
    .ddram0_cke(ddram0_cke),
    .ddram0_cs_n(ddram0_cs_n),
    .ddram0_odt(ddram0_odt),
    .c1_cmd_valid(c1_native_cmd_valid),
    .c1_cmd_ready(c1_native_cmd_ready),
    .c1_cmd_we(c1_native_write),
    .c1_cmd_addr(c1_native_address),
    .c1_wdata_valid(c1_app_wdf_wren),
    .c1_wdata_ready(c1_app_wdf_rdy),
    .c1_wdata_data(c1_app_wdf_data),
    .c1_wdata_we(~c1_app_wdf_mask),
    .c1_rdata_valid(c1_app_rd_data_valid),
    .c1_rdata_ready(1'b1),
    .c1_rdata_data(c1_app_rd_data),
    .c1_ready(c1_init_calib_complete),
    .c1b_cmd_valid(1'b0),
    .c1b_cmd_ready(),
    .c1b_cmd_we(1'b0),
    .c1b_cmd_addr(25'b0),
    .c1b_wdata_valid(1'b0),
    .c1b_wdata_ready(),
    .c1b_wdata_data(512'b0),
    .c1b_wdata_we(64'b0),
    .c1b_rdata_valid(),
    .c1b_rdata_ready(1'b1),
    .c1b_rdata_data(),
    .ddram1_dq(ddram1_dq),
    .ddram1_dqs_p(ddram1_dqs_p),
    .ddram1_dqs_n(ddram1_dqs_n),
    .ddram1_a(ddram1_a),
    .ddram1_ba(ddram1_ba),
    .ddram1_ras_n(ddram1_ras_n),
    .ddram1_cas_n(ddram1_cas_n),
    .ddram1_we_n(ddram1_we_n),
    .ddram1_reset_n(ddram1_reset_n),
    .ddram1_clk_p(ddram1_clk_p),
    .ddram1_clk_n(ddram1_clk_n),
    .ddram1_cke(ddram1_cke),
    .ddram1_cs_n(ddram1_cs_n),
    .ddram1_odt(ddram1_odt)
  );
// End of User Design top instance


//***************************************************************************
// The traffic generation module instantiated below drives traffic (patterns)
// on the application interface of the memory controller
//***************************************************************************

  mig_7series_v4_2_traffic_gen_top #
    (
     .TCQ                 (C0_TCQ),
     .SIMULATION          (C0_SIMULATION),
     .FAMILY              ("VIRTEX7"),
     .MEM_TYPE            (DRAM_TYPE),
     .TST_MEM_INSTR_MODE  (C0_TST_MEM_INSTR_MODE),
     //.BL_WIDTH            (C0_BL_WIDTH),
     .nCK_PER_CLK         (C0_nCK_PER_CLK),
     .NUM_DQ_PINS         (C0_PAYLOAD_WIDTH),
     .MEM_BURST_LEN       (C0_BURST_LENGTH),
     .MEM_COL_WIDTH       (C0_COL_WIDTH),
     .PORT_MODE           (C0_PORT_MODE),
     .DATA_PATTERN        (C0_DATA_PATTERN),
     .CMD_PATTERN         (C0_CMD_PATTERN),
     .DATA_WIDTH          (C0_APP_DATA_WIDTH),
     .ADDR_WIDTH          (C0_TG_ADDR_WIDTH),
     .MASK_SIZE           (C0_MASK_SIZE),
     .BEGIN_ADDRESS       (C0_BEGIN_ADDRESS),
     .DATA_MODE           (C0_DATA_MODE),
     .END_ADDRESS         (C0_END_ADDRESS),
     .PRBS_EADDR_MASK_POS (C0_PRBS_EADDR_MASK_POS),
     .SEL_VICTIM_LINE     (C0_SEL_VICTIM_LINE),
     .CMD_WDT             (C0_CMD_WDT),
     .RD_WDT              (C0_RD_WDT),
     .WR_WDT              (C0_WR_WDT),
     .EYE_TEST            (C0_EYE_TEST)
     )
    c0_u_traffic_gen_top
      (
       .clk                  (c0_clk),
       .rst                  (c0_rst),
       .tg_only_rst          (c0_po_win_tg_rst | c0_vio_tg_rst),
       .manual_clear_error   (1'b0),
       .memc_init_done       (c0_init_calib_complete && 1'b1),
       .memc_cmd_full        (~c0_app_rdy),
       .memc_cmd_en          (c0_app_en),
       .memc_cmd_instr       (c0_app_cmd),
       .memc_cmd_bl          (),
       .memc_cmd_addr        (c0_app_addr),
       .memc_wr_en           (c0_app_wdf_wren),
       .memc_wr_end          (c0_app_wdf_end),
       .memc_wr_mask         (c0_app_wdf_mask),
       .memc_wr_data         (c0_app_wdf_data),
       .memc_wr_full         (~c0_app_wdf_rdy),
       .memc_rd_en           (),
       .memc_rd_data         (c0_app_rd_data),
       .memc_rd_empty        (~c0_app_rd_data_valid),
       .qdr_wr_cmd_o         (),
       .qdr_rd_cmd_o         (),
       .vio_pause_traffic    (c0_vio_pause_traffic),
       .vio_modify_enable    (c0_vio_modify_enable),
       .vio_data_mode_value  (c0_vio_data_mode_value),
       .vio_addr_mode_value  (c0_vio_addr_mode_value),
       .vio_instr_mode_value (c0_vio_instr_mode_value),
       .vio_bl_mode_value    (c0_vio_bl_mode_value),
       .vio_fixed_bl_value   (c0_vio_fixed_bl_value),
       .vio_fixed_instr_value(c0_vio_fixed_instr_value),
       .vio_data_mask_gen    (c0_vio_data_mask_gen),
       .fixed_addr_i         (32'b0),
       .fixed_data_i         (ld_fixed_data),
       .simple_data0         (32'b0),
       .simple_data1         (32'b0),
       .simple_data2         (32'b0),
       .simple_data3         (32'b0),
       .simple_data4         (32'b0),
       .simple_data5         (32'b0),
       .simple_data6         (32'b0),
       .simple_data7         (32'b0),
       .wdt_en_i             (c0_wdt_en_w),
       .bram_cmd_i           (39'b0),
       .bram_valid_i         (1'b0),
       .bram_rdy_o           (),
       .cmp_data             (c0_cmp_data),
       .cmp_data_valid       (c0_cmp_data_valid),
       .cmp_error            (c0_cmp_error),
       .wr_data_counts       (c0_tg_wr_data_counts),
       .rd_data_counts       (c0_tg_rd_data_counts),
       .dq_error_bytelane_cmp (c0_dq_error_bytelane_cmp),
       .error                (c0_tg_compare_error),
       .error_status         (c0_error_status),
       .cumlative_dq_lane_error (c0_cumlative_dq_lane_error),
       .cmd_wdt_err_o         (c0_cmd_wdt_err_w),
       .wr_wdt_err_o          (c0_wr_wdt_err_w),
       .rd_wdt_err_o          (c0_rd_wdt_err_w),
       .mem_pattern_init_done   (c0_mem_pattern_init_done)
       );
//***************************************************************************
// The traffic generation module instantiated below drives traffic (patterns)
// on the application interface of the memory controller
//***************************************************************************

  mig_7series_v4_2_traffic_gen_top #
    (
     .TCQ                 (C1_TCQ),
     .SIMULATION          (C1_SIMULATION),
     .FAMILY              ("VIRTEX7"),
     .MEM_TYPE            (DRAM_TYPE),
     .TST_MEM_INSTR_MODE  (C1_TST_MEM_INSTR_MODE),
     //.BL_WIDTH            (C1_BL_WIDTH),
     .nCK_PER_CLK         (C1_nCK_PER_CLK),
     .NUM_DQ_PINS         (C1_PAYLOAD_WIDTH),
     .MEM_BURST_LEN       (C1_BURST_LENGTH),
     .MEM_COL_WIDTH       (C1_COL_WIDTH),
     .PORT_MODE           (C1_PORT_MODE),
     .DATA_PATTERN        (C1_DATA_PATTERN),
     .CMD_PATTERN         (C1_CMD_PATTERN),
     .DATA_WIDTH          (C1_APP_DATA_WIDTH),
     .ADDR_WIDTH          (C1_TG_ADDR_WIDTH),
     .MASK_SIZE           (C1_MASK_SIZE),
     .BEGIN_ADDRESS       (C1_BEGIN_ADDRESS),
     .DATA_MODE           (C1_DATA_MODE),
     .END_ADDRESS         (C1_END_ADDRESS),
     .PRBS_EADDR_MASK_POS (C1_PRBS_EADDR_MASK_POS),
     .SEL_VICTIM_LINE     (C1_SEL_VICTIM_LINE),
     .CMD_WDT             (C1_CMD_WDT),
     .RD_WDT              (C1_RD_WDT),
     .WR_WDT              (C1_WR_WDT),
     .EYE_TEST            (C1_EYE_TEST)
     )
    c1_u_traffic_gen_top
      (
       .clk                  (c1_clk),
       .rst                  (c1_rst),
       .tg_only_rst          (c1_po_win_tg_rst | c1_vio_tg_rst),
       .manual_clear_error   (1'b0),
       .memc_init_done       (c1_init_calib_complete && 1'b1),
       .memc_cmd_full        (~c1_app_rdy),
       .memc_cmd_en          (c1_app_en),
       .memc_cmd_instr       (c1_app_cmd),
       .memc_cmd_bl          (),
       .memc_cmd_addr        (c1_app_addr),
       .memc_wr_en           (c1_app_wdf_wren),
       .memc_wr_end          (c1_app_wdf_end),
       .memc_wr_mask         (c1_app_wdf_mask),
       .memc_wr_data         (c1_app_wdf_data),
       .memc_wr_full         (~c1_app_wdf_rdy),
       .memc_rd_en           (),
       .memc_rd_data         (c1_app_rd_data),
       .memc_rd_empty        (~c1_app_rd_data_valid),
       .qdr_wr_cmd_o         (),
       .qdr_rd_cmd_o         (),
       .vio_pause_traffic    (c1_vio_pause_traffic),
       .vio_modify_enable    (c1_vio_modify_enable),
       .vio_data_mode_value  (c1_vio_data_mode_value),
       .vio_addr_mode_value  (c1_vio_addr_mode_value),
       .vio_instr_mode_value (c1_vio_instr_mode_value),
       .vio_bl_mode_value    (c1_vio_bl_mode_value),
       .vio_fixed_bl_value   (c1_vio_fixed_bl_value),
       .vio_fixed_instr_value(c1_vio_fixed_instr_value),
       .vio_data_mask_gen    (c1_vio_data_mask_gen),
       .fixed_addr_i         (32'b0),
       .fixed_data_i         (ld_fixed_data),
       .simple_data0         (32'b0),
       .simple_data1         (32'b0),
       .simple_data2         (32'b0),
       .simple_data3         (32'b0),
       .simple_data4         (32'b0),
       .simple_data5         (32'b0),
       .simple_data6         (32'b0),
       .simple_data7         (32'b0),
       .wdt_en_i             (c1_wdt_en_w),
       .bram_cmd_i           (39'b0),
       .bram_valid_i         (1'b0),
       .bram_rdy_o           (),
       .cmp_data             (c1_cmp_data),
       .cmp_data_valid       (c1_cmp_data_valid),
       .cmp_error            (c1_cmp_error),
       .wr_data_counts       (c1_tg_wr_data_counts),
       .rd_data_counts       (c1_tg_rd_data_counts),
       .dq_error_bytelane_cmp (c1_dq_error_bytelane_cmp),
       .error                (c1_tg_compare_error),
       .error_status         (c1_error_status),
       .cumlative_dq_lane_error (c1_cumlative_dq_lane_error),
       .cmd_wdt_err_o         (c1_cmd_wdt_err_w),
       .wr_wdt_err_o          (c1_wr_wdt_err_w),
       .rd_wdt_err_o          (c1_rd_wdt_err_w),
       .mem_pattern_init_done   (c1_mem_pattern_init_done)
       );


   //*****************************************************************
   // Default values are assigned to the debug inputs of the traffic
   // generator
   //*****************************************************************
   assign c0_vio_modify_enable = 1'b1;
   assign c0_vio_data_mode_value = ld_pattern;
   assign c0_vio_addr_mode_value   = 3'b011;
   assign c0_vio_instr_mode_value = ld_instruction;
   assign c0_vio_bl_mode_value = 2'b01;
   assign c0_vio_fixed_bl_value = 8'd64;
   assign c0_vio_data_mask_gen     = 1'b0;
   assign c0_vio_pause_traffic = ld_traffic_pause[0];
   assign c0_vio_fixed_instr_value = 3'b001;
   assign c0_dbg_clear_error       = 1'b0;
   assign c0_po_win_tg_rst         = 1'b0;
   assign c0_vio_tg_rst            = 1'b0;
   assign c0_wdt_en_w              = 1'b0;

   assign c0_dbg_sel_pi_incdec       = 'b0;
   assign c0_dbg_sel_po_incdec       = 'b0;
   assign c0_dbg_pi_f_inc            = 'b0;
   assign c0_dbg_pi_f_dec            = 'b0;
   assign c0_dbg_po_f_inc            = 'b0;
   assign c0_dbg_po_f_dec            = 'b0;
   assign c0_dbg_po_f_stg23_sel      = 'b0;

      
`ifdef SKIP_CALIB
  //***************************************************************************
  // Skip calib test logic
  //***************************************************************************

  reg[3*DQS_WIDTH-1:0]        po_coarse_tap;
  reg[6*DQS_WIDTH-1:0]        po_stg3_taps;
  reg[6*DQS_WIDTH-1:0]        po_stg2_taps;
  reg[6*DQS_WIDTH-1:0]        pi_stg2_taps;
  reg[5*DQS_WIDTH-1:0]        idelay_taps;
  reg[11:0]                   cal_device_temp;


  always @(posedge clk) begin
    // tap values from golden run (factory)
    po_coarse_tap   <= #TCQ 'h2;
    po_stg3_taps    <= #TCQ 'h0D;
    po_stg2_taps    <= #TCQ 'h1D;
    pi_stg2_taps    <= #TCQ 'h1E;
    idelay_taps     <= #TCQ 'h08;
        cal_device_temp <= #TCQ 'h000;
  end

  always @(posedge clk) begin
    if (rst)
      c0_calib_tap_load <= #TCQ 1'b0;
    else if (c0_calib_tap_req)
      c0_calib_tap_load <= #TCQ 1'b1;
  end

  always @(posedge clk) begin
    if (rst) begin
      c0_calib_tap_addr      <= #TCQ 'd0;
      c0_calib_tap_val       <= #TCQ po_coarse_tap[3*c0_calib_tap_addr[6:3]+:3]; //'d1;
      c0_calib_tap_load_done <= #TCQ 1'b0;
    end else if (c0_calib_tap_load) begin
      case (c0_calib_tap_addr[2:0])
        3'b000: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b001;
          c0_calib_tap_val       <= #TCQ po_stg3_taps[6*c0_calib_tap_addr[6:3]+:6]; //'d19;
        end
        3'b001: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b010;
          c0_calib_tap_val       <= #TCQ po_stg2_taps[6*c0_calib_tap_addr[6:3]+:6]; //'d45;
        end
        3'b010: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b011;
          c0_calib_tap_val       <= #TCQ pi_stg2_taps[6*c0_calib_tap_addr[6:3]+:6]; //'d20;
        end
        3'b011: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b100;
          c0_calib_tap_val       <= #TCQ idelay_taps[5*c0_calib_tap_addr[6:3]+:5]; //'d1;
        end
        3'b100: begin
          if (c0_calib_tap_addr[6:3] < DQS_WIDTH-1) begin
            c0_calib_tap_addr[2:0] <= #TCQ 3'b000;
            c0_calib_tap_val       <= #TCQ po_coarse_tap[3*(c0_calib_tap_addr[6:3]+1)+:3]; //'d1;
            c0_calib_tap_addr[6:3] <= #TCQ c0_calib_tap_addr[6:3] + 1;
          end else begin
            c0_calib_tap_addr[2:0] <= #TCQ 3'b110;
            c0_calib_tap_val       <= #TCQ cal_device_temp[7:0];
            c0_calib_tap_addr[6:3] <= #TCQ 4'b1111;
          end
        end
        3'b110: begin
            c0_calib_tap_addr[2:0] <= #TCQ 3'b111;
            c0_calib_tap_val       <= #TCQ {4'h0,cal_device_temp[11:8]};
            c0_calib_tap_addr[6:3] <= #TCQ 4'b1111;
        end
        3'b111: begin
            c0_calib_tap_load_done <= #TCQ 1'b1;
        end
      endcase
    end
  end


//****************skip calib test logic end**********************************
`endif    
   //*****************************************************************
   // Default values are assigned to the debug inputs of the traffic
   // generator
   //*****************************************************************
   assign c1_vio_modify_enable = 1'b1;
   assign c1_vio_data_mode_value = ld_pattern;
   assign c1_vio_addr_mode_value   = 3'b011;
   assign c1_vio_instr_mode_value = ld_instruction;
   assign c1_vio_bl_mode_value = 2'b01;
   assign c1_vio_fixed_bl_value = 8'd64;
   assign c1_vio_data_mask_gen     = 1'b0;
   assign c1_vio_pause_traffic = ld_traffic_pause[1];
   assign c1_vio_fixed_instr_value = 3'b001;
   assign c1_dbg_clear_error       = 1'b0;
   assign c1_po_win_tg_rst         = 1'b0;
   assign c1_vio_tg_rst            = 1'b0;
   assign c1_wdt_en_w              = 1'b0;

   assign c1_dbg_sel_pi_incdec       = 'b0;
   assign c1_dbg_sel_po_incdec       = 'b0;
   assign c1_dbg_pi_f_inc            = 'b0;
   assign c1_dbg_pi_f_dec            = 'b0;
   assign c1_dbg_po_f_inc            = 'b0;
   assign c1_dbg_po_f_dec            = 'b0;
   assign c1_dbg_po_f_stg23_sel      = 'b0;

      
`ifdef SKIP_CALIB
  //***************************************************************************
  // Skip calib test logic
  //***************************************************************************

  reg[3*DQS_WIDTH-1:0]        po_coarse_tap;
  reg[6*DQS_WIDTH-1:0]        po_stg3_taps;
  reg[6*DQS_WIDTH-1:0]        po_stg2_taps;
  reg[6*DQS_WIDTH-1:0]        pi_stg2_taps;
  reg[5*DQS_WIDTH-1:0]        idelay_taps;
  reg[11:0]                   cal_device_temp;


  always @(posedge clk) begin
    // tap values from golden run (factory)
    po_coarse_tap   <= #TCQ 'h2;
    po_stg3_taps    <= #TCQ 'h0D;
    po_stg2_taps    <= #TCQ 'h1D;
    pi_stg2_taps    <= #TCQ 'h1E;
    idelay_taps     <= #TCQ 'h08;
        cal_device_temp <= #TCQ 'h000;
  end

  always @(posedge clk) begin
    if (rst)
      c0_calib_tap_load <= #TCQ 1'b0;
    else if (c0_calib_tap_req)
      c0_calib_tap_load <= #TCQ 1'b1;
  end

  always @(posedge clk) begin
    if (rst) begin
      c0_calib_tap_addr      <= #TCQ 'd0;
      c0_calib_tap_val       <= #TCQ po_coarse_tap[3*c0_calib_tap_addr[6:3]+:3]; //'d1;
      c0_calib_tap_load_done <= #TCQ 1'b0;
    end else if (c0_calib_tap_load) begin
      case (c0_calib_tap_addr[2:0])
        3'b000: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b001;
          c0_calib_tap_val       <= #TCQ po_stg3_taps[6*c0_calib_tap_addr[6:3]+:6]; //'d19;
        end
        3'b001: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b010;
          c0_calib_tap_val       <= #TCQ po_stg2_taps[6*c0_calib_tap_addr[6:3]+:6]; //'d45;
        end
        3'b010: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b011;
          c0_calib_tap_val       <= #TCQ pi_stg2_taps[6*c0_calib_tap_addr[6:3]+:6]; //'d20;
        end
        3'b011: begin
          c0_calib_tap_addr[2:0] <= #TCQ 3'b100;
          c0_calib_tap_val       <= #TCQ idelay_taps[5*c0_calib_tap_addr[6:3]+:5]; //'d1;
        end
        3'b100: begin
          if (c0_calib_tap_addr[6:3] < DQS_WIDTH-1) begin
            c0_calib_tap_addr[2:0] <= #TCQ 3'b000;
            c0_calib_tap_val       <= #TCQ po_coarse_tap[3*(c0_calib_tap_addr[6:3]+1)+:3]; //'d1;
            c0_calib_tap_addr[6:3] <= #TCQ c0_calib_tap_addr[6:3] + 1;
          end else begin
            c0_calib_tap_addr[2:0] <= #TCQ 3'b110;
            c0_calib_tap_val       <= #TCQ cal_device_temp[7:0];
            c0_calib_tap_addr[6:3] <= #TCQ 4'b1111;
          end
        end
        3'b110: begin
            c0_calib_tap_addr[2:0] <= #TCQ 3'b111;
            c0_calib_tap_val       <= #TCQ {4'h0,cal_device_temp[11:8]};
            c0_calib_tap_addr[6:3] <= #TCQ 4'b1111;
        end
        3'b111: begin
            c0_calib_tap_load_done <= #TCQ 1'b1;
        end
      endcase
    end
  end


//****************skip calib test logic end**********************************
`endif    


  wire tg_compare_error, init_calib_complete;
  wire osc_ibuf, control_clk;
  IBUF u_osc_ibuf(.I(SYS_CLK), .O(osc_ibuf));
  BUFG u_osc_bufg(.I(osc_ibuf), .O(control_clk));
  reg [12:0] startup = 0;
  always @(posedge control_clk) if (!startup[12]) startup <= startup + 1'b1;
  wire sys_rst = startup[12];
  wire [1:0] snap_request, snap_ack;
  wire [2047:0] snapshot0, snapshot1;

  ramtest_ld_channel #(.ENABLED(1)) u_observer0 (
    .clk(c0_clk), .ui_rst(c0_rst), .pattern({28'b0,ld_pattern}),
    .paused(ld_traffic_pause[0]), .write_data_valid(c0_app_wdf_wren),
    .write_data_ready(c0_app_wdf_rdy), .calibrated(c0_init_calib_complete),
    .pattern_initialized(c0_mem_pattern_init_done), .compare_error(c0_tg_compare_error),
    .watchdog_errors({c0_rd_wdt_err_w,c0_wr_wdt_err_w,c0_cmd_wdt_err_w}),
    .command_valid(c0_app_en), .command_ready(c0_app_rdy),
    .command(c0_app_cmd), .address(c0_app_addr),
    .read_valid(c0_app_rd_data_valid), .compare_valid(c0_cmp_data_valid),
    .compare_bad(c0_cmp_error), .ecc_single(c0_app_ecc_single_err),
    .ecc_multiple(c0_app_ecc_multiple_err), .error_status(c0_error_status),
    .lane_errors(c0_cumlative_dq_lane_error),
    .snapshot_request(snap_request[0]), .snapshot_ack(snap_ack[0]),
    .snapshot(snapshot0));

  ramtest_ld_channel #(.ENABLED(1)) u_observer1 (
    .clk(c1_clk), .ui_rst(c1_rst), .pattern({28'b0,ld_pattern}),
    .paused(ld_traffic_pause[1]), .write_data_valid(c1_app_wdf_wren),
    .write_data_ready(c1_app_wdf_rdy), .calibrated(c1_init_calib_complete),
    .pattern_initialized(c1_mem_pattern_init_done), .compare_error(c1_tg_compare_error),
    .watchdog_errors({c1_rd_wdt_err_w,c1_wr_wdt_err_w,c1_cmd_wdt_err_w}),
    .command_valid(c1_app_en), .command_ready(c1_app_rdy),
    .command(c1_app_cmd), .address(c1_app_addr),
    .read_valid(c1_app_rd_data_valid), .compare_valid(c1_cmp_data_valid),
    .compare_bad(c1_cmp_error), .ecc_single(c1_app_ecc_single_err),
    .ecc_multiple(c1_app_ecc_multiple_err), .error_status(c1_error_status),
    .lane_errors(c1_cumlative_dq_lane_error),
    .snapshot_request(snap_request[1]), .snapshot_ack(snap_ack[1]),
    .snapshot(snapshot1));


  wire [1087:0] first_read_record0;
  ramtest_read_capture u_read_capture0 (
    .clk(c0_clk), .rst(c0_rst),
    .command_valid(c0_app_en), .command_ready(c0_app_rdy),
    .command(c0_app_cmd), .address(c0_app_addr),
    .read_valid(c0_app_rd_data_valid), .read_data(c0_app_rd_data),
    .expected_data(c0_cmp_data), .record(first_read_record0));

  wire [1087:0] first_read_record1;
  ramtest_read_capture u_read_capture1 (
    .clk(c1_clk), .rst(c1_rst),
    .command_valid(c1_app_en), .command_ready(c1_app_rdy),
    .command(c1_app_cmd), .address(c1_app_addr),
    .read_valid(c1_app_rd_data_valid), .read_data(c1_app_rd_data),
    .expected_data(c1_cmp_data), .record(first_read_record1));
  ramtest_litedram_status #(.BUILD_ID(32'hc0172060), .DDR_MTS(800)) u_status (
    .clk(c0_clk), .rst(ld_sys_rst), .snapshot0(snapshot0), .snapshot1(snapshot1),
    .snapshot_ack(snap_ack), .snapshot_request(snap_request), .led(led),
    .calibrated({c1_init_calib_complete,c0_init_calib_complete}),
    .first_read0(first_read_record0), .first_read1(first_read_record1),
    .native_busy(ld_native_busy), .protocol_error(ld_protocol_error),
    .traffic_reset(ld_traffic_reset), .traffic_pause(ld_traffic_pause),
    .pattern_mode(ld_pattern), .instruction_mode(ld_instruction), .fixed_data(ld_fixed_data),
    .ctl_awaddr(ld_awaddr), .ctl_araddr(ld_araddr), .ctl_wdata(ld_wdata), .ctl_rdata(ld_rdata),
    .ctl_wstrb(ld_wstrb), .ctl_bresp(ld_bresp), .ctl_rresp(ld_rresp),
    .ctl_awvalid(ld_awvalid), .ctl_awready(ld_awready), .ctl_wvalid(ld_wvalid), .ctl_wready(ld_wready),
    .ctl_bvalid(ld_bvalid), .ctl_bready(ld_bready), .ctl_arvalid(ld_arvalid), .ctl_arready(ld_arready),
    .ctl_rvalid(ld_rvalid), .ctl_rready(ld_rready));

endmodule


