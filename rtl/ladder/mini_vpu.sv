// Ladder step 5 — mini VPU: the elementwise VOPs in all four B-operand modes, one element per
// clock, bit-exact with opentpu/isasim.py's `_vop` (docs/isa.md "VOP").
//
// The arithmetic is the product tree's `otpu_fp` package (rtl/ladder/otpu_fp.sv, copied verbatim
// from ca05e24f, Apache-2.0): fp_add / fp_sub / fp_mul / fp_max / fp_min / ftz / fabs / fp_exp2
// / fp_recip / fp_rsqrt / fp_log2 are the same functions the production VPU and
// opentpu/fp32.py define, so this unit cannot drift from the oracle.  The functions implemented
// here are ADD, SUB, RSUB, MUL, MAX, MIN, COPY, EXP2, RECIP, RSQRT, ABS, FILL, EXP2SUB, LOG2;
// the reductions, ARGMAX and OUTER are step 8.
//
// Elements are processed row-major, (r, c) = (0,0), (0,1), ... one per cycle.  For element i:
//   A address = a + r*ars + c          (not read by FILL)
//   B address = b + r*brs + c          FULL
//               b + r*brs              ROW
//               b + c                  COL
//               the immediate word     SCALAR (no TMEM read)
//   result    = f(T[A], T[B]) written to dst + r*drs + c.
// The mini-core has one TMEM write port, so a VOP's writes land one per cycle; a later element
// reading an address an earlier element wrote would see stale data.  The ISA simulator rejects
// exactly that (`_check_hazard`: a read after an earlier write), so the VPU marks every written
// address in a bitmap and raises error code 5 when a read hits one.  Range errors are code 4.
`timescale 1ns/1ps
module mini_vpu #(
  parameter int TMEM_WORDS = 4096
) (
  input  logic        clk,
  input  logic        rst,              // synchronous, active high
  input  logic        start,            // one-cycle pulse from the sequencer
  input  logic [7:0]  func,
  input  logic [31:0] dst, a, b,        // TMEM word addresses (register-resolved by the top)
  input  logic [15:0] rows, cols,
  input  logic [15:0] drs, ars, brs,    // destination / A / B strides
  input  logic [1:0]  bmode,
  input  logic [7:0]  flags,            // unread by the elementwise functions; kept for step 8
  input  logic [31:0] imm,              // SCALAR's fp32 word (w7 = R[rd] + w6, resolved by the top)
  output logic        busy,
  output logic        done,             // one-cycle pulse: every write has landed
  output logic        err,              // latched error
  output logic [2:0]  err_code,         // 4 TMEM range, 5 read-after-write hazard
  output logic [31:0] raddr0,           // operand A
  input  logic [31:0] rdata0,
  output logic [31:0] raddr1,           // operand B
  input  logic [31:0] rdata1,
  output logic        we,
  output logic [31:0] waddr,
  output logic [31:0] wdata
);

  import otpu_fp::*;

  // error codes: the TMEM range code is mini_pkg's ERR_TMEM (4); the hazard code is this step's
  localparam logic [2:0] VERR_TMEM = 3'd4;
  localparam logic [2:0] VERR_HAZ  = 3'd5;

  // VOP functions (docs/isa.md / opentpu/isa.py)
  localparam logic [7:0] V_ADD = 8'd0, V_SUB = 8'd1, V_RSUB = 8'd2, V_MUL = 8'd3,
                         V_MAX = 8'd4, V_MIN = 8'd5, V_COPY = 8'd8, V_EXP2 = 8'd9,
                         V_RECIP = 8'd10, V_RSQRT = 8'd11, V_ABS = 8'd12, V_FILL = 8'd13,
                         V_EXP2SUB = 8'd14, V_LOG2 = 8'd15;

  // B-operand modes (isa.B_FULL..B_SCALAR)
  localparam logic [1:0] B_FULL = 2'd0, B_ROW = 2'd1, B_COL = 2'd2, B_SCALAR = 2'd3;

  // ------------------------------------------------------------------ latched configuration
  logic [7:0]  f_func;
  logic [31:0] f_dst, f_a, f_b, f_imm;
  logic [15:0] f_rows, f_cols, f_drs, f_ars, f_brs;
  logic [1:0]  f_bmode;

  // ------------------------------------------------------------------ element counter
  logic [15:0] r, c;              // current element (row-major, one per cycle)
  logic        running;
  logic        done_r;
  logic        err_r;
  logic [2:0]  ecode_r;

  // written-address bitmap: bit x set once an element has written TMEM word x.  A read that hits
  // a set bit is a read-after-write hazard (isasim's `_check_hazard`).
  logic [TMEM_WORDS-1:0] written;

  // ------------------------------------------------------------------ reads this function does
  logic reads_a, reads_b, reads_b_tmem;

  assign reads_a = (f_func != V_FILL);                       // isasim: A read unless FILL
  assign reads_b = (f_func == V_ADD) || (f_func == V_SUB) || (f_func == V_RSUB) ||
                   (f_func == V_MUL) || (f_func == V_MAX) || (f_func == V_MIN) ||
                   (f_func == V_FILL) || (f_func == V_EXP2SUB);   // isa.is_binary()
  assign reads_b_tmem = reads_b && (f_bmode != B_SCALAR);

  // ------------------------------------------------------------------ addresses (64-bit: a
  // register's value plus strides can run past 32 bits, which is an error, not a wrap)
  logic [63:0] addr_a64, addr_b64, addr_d64;
  logic [63:0] tmem_limit;

  assign tmem_limit = TMEM_WORDS;

  always_comb begin
    addr_a64 = {32'd0, f_a} + ({48'd0, r} * {48'd0, f_ars}) + {48'd0, c};
    case (f_bmode)
      B_FULL:  addr_b64 = {32'd0, f_b} + ({48'd0, r} * {48'd0, f_brs}) + {48'd0, c};
      B_ROW:   addr_b64 = {32'd0, f_b} + ({48'd0, r} * {48'd0, f_brs});
      B_COL:   addr_b64 = {32'd0, f_b} + {48'd0, c};
      default: addr_b64 = 64'd0;                       // SCALAR: the immediate, no read
    endcase
    addr_d64 = {32'd0, f_dst} + ({48'd0, r} * {48'd0, f_drs}) + {48'd0, c};
  end

  // ------------------------------------------------------------------ checks (isasim's order:
  // A read range, B read range, hazard, then the destination write range)
  logic range_a, range_b, range_d, hazard, err_now;
  logic [2:0] err_now_code;

  always_comb begin
    range_a = reads_a && (addr_a64 >= tmem_limit);
    range_b = reads_b_tmem && (addr_b64 >= tmem_limit);
    range_d = (addr_d64 >= tmem_limit);
    hazard  = 1'b0;
    if (!range_a && !range_b && reads_a && written[addr_a64]) begin
      hazard = 1'b1;
    end
    if (!range_a && !range_b && reads_b_tmem && written[addr_b64]) begin
      hazard = 1'b1;
    end
    err_now = range_a || range_b || range_d || hazard;
    if (range_a || range_b) begin
      err_now_code = VERR_TMEM;
    end else if (hazard) begin
      err_now_code = VERR_HAZ;
    end else begin
      err_now_code = VERR_TMEM;
    end
  end

  // ------------------------------------------------------------------ the element's arithmetic:
  // exactly isasim's `ops` table, on the product tree's otpu_fp functions
  f32_t va, vb, rv;

  always_comb begin
    va = rdata0;
    vb = (f_bmode == B_SCALAR) ? f_imm : rdata1;
    case (f_func)
      V_ADD:     rv = fp_add(va, vb);
      V_SUB:     rv = fp_sub(va, vb);
      V_RSUB:    rv = fp_sub(vb, va);
      V_MUL:     rv = fp_mul(va, vb);
      V_MAX:     rv = fp_max(va, vb);
      V_MIN:     rv = fp_min(va, vb);
      V_COPY:    rv = ftz(va);
      V_EXP2:    rv = fp_exp2(va);
      V_RECIP:   rv = fp_recip(va);
      V_RSQRT:   rv = fp_rsqrt(va);
      V_ABS:     rv = fabs(va);
      V_FILL:    rv = ftz(vb);
      V_EXP2SUB: rv = fp_exp2(fp_sub(va, vb));
      V_LOG2:    rv = fp_log2(va);
      default:   rv = 32'h0000_0000;
    endcase
  end

  // ------------------------------------------------------------------ TMEM ports (clamped when
  // a range error means the address must not be used; the result is discarded anyway)
  assign raddr0 = (reads_a && !range_a) ? addr_a64[31:0] : 32'd0;
  assign raddr1 = (reads_b_tmem && !range_b) ? addr_b64[31:0] : 32'd0;
  assign we     = running && !err_now;
  assign waddr  = addr_d64[31:0];
  assign wdata  = rv;

  // ------------------------------------------------------------------ status
  assign busy     = running;
  assign done     = done_r;
  assign err      = err_r;
  assign err_code = ecode_r;

  // ------------------------------------------------------------------ element sequencer
  logic last;

  assign last = (r == (f_rows - 16'd1)) && (c == (f_cols - 16'd1));

  always_ff @(posedge clk) begin
    if (rst) begin
      f_func  <= 8'd0;
      f_dst   <= 32'd0;
      f_a     <= 32'd0;
      f_b     <= 32'd0;
      f_imm   <= 32'd0;
      f_rows  <= 16'd0;
      f_cols  <= 16'd0;
      f_drs   <= 16'd0;
      f_ars   <= 16'd0;
      f_brs   <= 16'd0;
      f_bmode <= 2'd0;
      r       <= 16'd0;
      c       <= 16'd0;
      running <= 1'b0;
      done_r  <= 1'b0;
      err_r   <= 1'b0;
      ecode_r <= 3'd0;
      written <= '0;
    end else begin
      done_r <= 1'b0;
      if (start && !running) begin
        f_func  <= func;
        f_dst   <= dst;
        f_a     <= a;
        f_b     <= b;
        f_imm   <= imm;
        f_rows  <= rows;
        f_cols  <= cols;
        f_drs   <= drs;
        f_ars   <= ars;
        f_brs   <= brs;
        f_bmode <= bmode;
        r       <= 16'd0;
        c       <= 16'd0;
        running <= 1'b1;
        err_r   <= 1'b0;
        ecode_r <= 3'd0;
        written <= '0;                  // nothing written by *this* instruction yet
      end else if (running) begin
        if (err_now) begin
          // a bad address or a read-after-write hazard: stop, write nothing further, latch the
          // code (the earlier elements' writes have landed, as they did in isasim)
          err_r   <= 1'b1;
          ecode_r <= err_now_code;
          running <= 1'b0;
        end else begin
          written[addr_d64] <= 1'b1;    // this element's write lands at this edge
          if (last) begin
            running <= 1'b0;
            done_r  <= 1'b1;
          end else if (c == (f_cols - 16'd1)) begin
            c <= 16'd0;
            r <= r + 16'd1;
          end else begin
            c <= c + 16'd1;
          end
        end
      end
    end
  end

endmodule
