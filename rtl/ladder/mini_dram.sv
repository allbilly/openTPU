// Ladder step 4 — behavioural DRAM: byte-addressed, little endian, 32-bit word ports.
//
// State semantics only (the real board has an AXI/DDR controller; later rungs adopt it): one
// combinational 32-bit read port and one synchronous 32-bit write port, so an LD/ST engine can
// move one word per cycle.  The byte array is deliberately named `mem` and is left visible so
// the testbench can $readmemh a DRAM image into it and dump it out again.
`timescale 1ns/1ps
module mini_dram #(
  parameter int DRAM_BYTES = 262144
) (
  input  logic        clk,
  input  logic [31:0] raddr,    // byte address, 4-byte aligned (the core checks)
  output logic [31:0] rdata,
  input  logic [31:0] waddr,    // byte address, 4-byte aligned (the core checks)
  input  logic [31:0] wdata,
  input  logic        we
);

  logic [7:0] mem [0:DRAM_BYTES-1];

  // little endian: byte 0 is the low byte of the word.  A continuous assign (not an always @*
  // process) keeps Icarus from rescheduling the read on every byte the image loader writes.
  assign rdata = {mem[raddr+32'd3], mem[raddr+32'd2], mem[raddr+32'd1], mem[raddr]};

  always_ff @(posedge clk) begin
    if (we) begin
      mem[waddr]   <= wdata[7:0];
      mem[waddr+1] <= wdata[15:8];
      mem[waddr+2] <= wdata[23:16];
      mem[waddr+3] <= wdata[31:24];
    end
  end

endmodule
