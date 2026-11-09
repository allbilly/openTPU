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
  localparam logic [7:0] OP_VOP   = 8'h30;
  localparam logic [7:0] OP_QACT  = 8'h21;
  localparam logic [7:0] OP_QST   = 8'h22;

  // ---- flags
  localparam logic [7:0] F_RAW    = 8'h01;   // RLD: the word's bits, no fp32 -> int conversion
  localparam logic [7:0] F_MUL    = 8'h02;   // RLD: times R[rb] + w3 (mod 2^32)
  localparam logic [7:0] F_BOUND  = 8'h04;   // RLD: w4 <= value <= w5 (the hardware ignores it)
  localparam logic [7:0] F_CHAIN  = 8'h01;   // HALT: chain to a program in DRAM (not in step 4)
  // QACT / QST flags (opentpu/isa.py: F_ROW/F_CSCALE/F_RSCALE/F_DUP, QST: F_ROW/F_HALF)
  localparam logic [7:0] F_ROW    = 8'h01;   // QACT/QST: row mode, every offset 0
  localparam logic [7:0] F_CSCALE = 8'h02;   // QACT: multiply by the per-column TMEM factors
  localparam logic [7:0] F_RSCALE = 8'h04;   // QACT: multiply by the per-row TMEM factors
  localparam logic [7:0] F_DUP    = 8'h08;   // QACT: also write ACT rows rows..2*rows-1
  localparam logic [7:0] F_HALF   = 8'h02;   // QST ROW mode: write only the first half of a row

  // ---- error codes (mini_top's error_code output)
  localparam logic [2:0] ERR_NONE    = 3'd0;
  localparam logic [2:0] ERR_ILLEGAL = 3'd1;  // illegal/unimplemented opcode, bad HALT CHAIN...
  localparam logic [2:0] ERR_DRAM    = 3'd2;  // bad DRAM word address (unaligned or out of range)
  localparam logic [2:0] ERR_LOOP    = 3'd3;  // LOOP error (empty body, nested end clash, depth)
  localparam logic [2:0] ERR_TMEM    = 3'd4;  // TMEM index out of range
  localparam logic [2:0] ERR_VOP_HAZ = 3'd5;  // VOP read-after-write hazard
  localparam logic [2:0] ERR_ACT     = 3'd6;  // QACT/QST TMEM range, QACT ACT RAM bounds
  localparam logic [2:0] ERR_QST     = 3'd7;  // QST data/scale range or overlap, bad scale address

  // VOP functions the step-5 VPU implements (docs/isa.md "VOP"); the reductions / ARGMAX /
  // OUTER are step 8, anything else is an illegal instruction for this rung.
  localparam logic [7:0] V_ADD = 8'd0, V_SUB = 8'd1, V_RSUB = 8'd2, V_MUL = 8'd3,
                         V_MAX = 8'd4, V_MIN = 8'd5, V_COPY = 8'd8, V_EXP2 = 8'd9,
                         V_RECIP = 8'd10, V_RSQRT = 8'd11, V_ABS = 8'd12, V_FILL = 8'd13,
                         V_EXP2SUB = 8'd14, V_LOG2 = 8'd15;

  function automatic logic is_elementwise(input logic [7:0] f);
    case (f)
      V_ADD, V_SUB, V_RSUB, V_MUL, V_MAX, V_MIN, V_COPY, V_EXP2, V_RECIP, V_RSQRT, V_ABS,
      V_FILL, V_EXP2SUB, V_LOG2: return 1'b1;
      default: return 1'b0;
    endcase
  endfunction

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


  // isasim/fp32.mx_offset(): the group's power-of-two offset.  `a` and `amax` are the
  // sign-cleared fp32 bit patterns (a NaN is above +inf); d = (exp(amax) - exp(a)) -
  // (mant(a) > mant(amax)), clipped to [0, 31], 0 where a is 0.
  function automatic logic [7:0] mx_offset(input logic [31:0] a, input logic [31:0] amax);
    logic signed [31:0] d;
    if (a == 32'd0) begin
      return 8'd0;
    end
    d = $signed({24'd0, amax[30:23]}) - $signed({24'd0, a[30:23]})
        - ((a[22:0] > amax[22:0]) ? 32'sd1 : 32'sd0);
    if (d < 32'sd0) d = 32'sd0;
    if (d > 32'sd31) d = 32'sd31;
    return d[7:0];
  endfunction

endpackage
