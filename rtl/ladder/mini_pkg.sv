// Ladder step 4 — mini-core package: the openTPU instruction encoding, flags and error codes.
//
// The encodings are the production ones (opentpu/isa.py, docs/isa.md); the mini-core only
// implements the step-4 subset, everything else is an illegal-opcode error.  Kept in a package
// so every later rung (VPU, quantizer, MXU, reductions) extends the same tables instead of
// redefining them.
`timescale 1ns/1ps
package mini_pkg;

  // ---- opcodes (docs/isa.md, opentpu/isa.py)
  localparam logic [7:0] OP_NOP   = 8'h00;
  localparam logic [7:0] OP_HALT  = 8'h01;
  localparam logic [7:0] OP_LI    = 8'h02;
  localparam logic [7:0] OP_ADDI  = 8'h03;
  localparam logic [7:0] OP_LOOP  = 8'h04;
  localparam logic [7:0] OP_BAR   = 8'h05;
  localparam logic [7:0] OP_RLD   = 8'h06;
  localparam logic [7:0] OP_LD    = 8'h10;
  localparam logic [7:0] OP_ST    = 8'h11;

  // ---- flags
  localparam logic [7:0] F_RAW    = 8'h01;   // RLD: the word's bits, no fp32 -> int conversion
  localparam logic [7:0] F_MUL    = 8'h02;   // RLD: times R[rb] + w3 (mod 2^32)
  localparam logic [7:0] F_BOUND  = 8'h04;   // RLD: w4 <= value <= w5 (the hardware ignores it)
  localparam logic [7:0] F_CHAIN  = 8'h01;   // HALT: chain to a program in DRAM (not in step 4)

  // ---- error codes (mini_top's error_code output)
  localparam logic [2:0] ERR_NONE    = 3'd0;
  localparam logic [2:0] ERR_ILLEGAL = 3'd1;  // illegal/unimplemented opcode, bad HALT CHAIN...
  localparam logic [2:0] ERR_DRAM    = 3'd2;  // bad DRAM word address (unaligned or out of range)
  localparam logic [2:0] ERR_LOOP    = 3'd3;  // LOOP error (empty body, nested end clash, depth)
  localparam logic [2:0] ERR_TMEM    = 3'd4;  // TMEM index out of range

  localparam int LOOP_DEPTH = 4;              // docs/isa.md: loops nest 4 deep

  // RLD's conversion of fp32 bits to a 32-bit word (isa.f2i): truncation toward zero; values
  // below 1 in magnitude (denormals, +-0) give 0; |x| >= 2^31, infinities and NaN give
  // 0x80000000.  Integers of up to 24 significant bits come out exact.
  function automatic logic [31:0] f2i(input logic [31:0] bits);
    logic [7:0]  e;
    logic [31:0] m, v;
    e = bits[30:23];
    if (e < 8'd127) begin
      return 32'd0;
    end else if (e >= 8'd158) begin           // 127 + 31: |x| >= 2^31 (and inf/NaN)
      return 32'h8000_0000;
    end else begin
      m = {1'b1, bits[22:0]};                 // the implicit leading one
      if (e >= 8'd150) begin
        v = m << (e - 8'd150);                // e - 150 is 0..7 here: v < 2^31
      end else begin
        v = m >> (8'd150 - e);
      end
      return bits[31] ? (32'd0 - v) : v;      // truncate toward zero, two's complement
    end
  endfunction

endpackage
