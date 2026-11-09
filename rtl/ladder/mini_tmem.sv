// Ladder step 4 — TMEM: a flat array of 32-bit words, one read + one write port per cycle.
//
// The production TMEM is banked (LANES banks, docs/isa.md); the mini-core runs one slice with
// one access per cycle, which is a legal schedule of the same state machine (step 5's VPU
// widens the ports, not the state).  `mem` stays visible so the testbench can dump it.
`timescale 1ns/1ps
module mini_tmem #(
  parameter int TMEM_WORDS = 4096
) (
  input  logic        clk,
  input  logic [31:0] raddr,    // word index; the core checks the range
  output logic [31:0] rdata,
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

  // continuous assign, not an always @* process: see mini_dram.sv
  assign rdata = mem[raddr];

  always_ff @(posedge clk) begin
    if (we) begin
      mem[waddr] <= wdata;
    end
  end

endmodule
