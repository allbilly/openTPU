// Ladder step 5 — TMEM: a flat array of 32-bit words, two read ports + one write port per cycle.
//
// The production TMEM is banked (LANES banks, docs/isa.md); the mini-core runs one slice with a
// serial instruction stream, so any port count is a legal schedule of the same state machine.
// Step 4 needed one read + one write port (LD/ST and RLD); step 5's VPU reads operand A and
// operand B in the same cycle, hence the second read port.  `mem` stays visible so the
// testbench can dump it.
`timescale 1ns/1ps
module mini_tmem #(
  parameter int TMEM_WORDS = 4096
) (
  input  logic        clk,
  input  logic [31:0] raddr0,   // word index; the core checks the range
  output logic [31:0] rdata0,
  input  logic [31:0] raddr1,   // the VPU's operand B
  output logic [31:0] rdata1,
  input  logic [31:0] waddr,
  input  logic [31:0] wdata,
  input  logic        we
);

  logic [31:0] mem [0:TMEM_WORDS-1];
  integer i;

  initial begin
    for (i = 0; i < TMEM_WORDS; i = i + 1) begin
      mem[i] = 32'h0000_0000;
    end
  end

  // continuous assigns, not always @* processes: see mini_dram.sv
  assign rdata0 = mem[raddr0];
  assign rdata1 = mem[raddr1];

  always_ff @(posedge clk) begin
    if (we) begin
      mem[waddr] <= wdata;
    end
  end

endmodule
