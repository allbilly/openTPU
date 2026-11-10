// Ladder step 8 — reduction / ARGMAX / OUTER unit for the mini-core.
//
// The elementwise VPU (step 5) is "one element read -> one element write per cycle".  The
// reductions have a different write discipline: one (ARGMAX: two) write(s) per row, at the
// *end* of the row's reads, and the hazard model of isasim's _check_hazard() reflects that.
// OUTER is elementwise but buffers Cv/Dv before writing and hazards on the old destination and
// B(r).  All of it is therefore a separate unit; mini_top routes VOP functions
// {6=OUTER, 16=RSUM, 17=RMAX, 18=RSSQ, 19=RDOT, 20=ARGMAX} here and keeps mini_vpu untouched.
//
// Arithmetic is the step-5 otpu_fp package, so the state left is bit-identical to isasim:
//  * RSUM/RSSQ/RDOT: fp32.interleaved_sum with P=RED_PARTIALS=64: 64 partial chains started at
//    +0, elements taken in steps of 64 left to right, the row padded to a multiple of 64 with
//    *added* +0 terms, then the folding tree x[i] = fp_add(x[i], x[i+64/2/...]) (63 adds);
//    RSSQ/RDOT round each product with fp_mul before the sum.
//  * RMAX: chain_max under otpu_fp's fp_gt()/fp_max() total order (sequential fold = same bits;
//    NaN payloads preserved, -0 < +0).
//  * ARGMAX: per row the max and i2f(int32(first index + sign-extended base w7)).
//  * OUTER: T = old * Dv + B(r) * Cv, two rounded products then one rounded add; Cv/Dv buffered
//    before any write; the old destination is read per element.
// Error codes: 4 TMEM range, 5 read-after-write hazard, 10 VOP shape/flag isasim rejects
// (ARGMAX rows>1 needs drs>=2; OUTER bmode must be ROW and cols<=256), 1 illegal function.
`timescale 1ns/1ps
module mini_reduce #(
  parameter int TMEM_WORDS = 4096
) (
  input  logic        clk,
  input  logic        rst,
  input  logic        start,
  input  logic [7:0]  func,
  input  logic [31:0] dst, a, b, imm,
  input  logic [15:0] rows, cols, drs, ars, brs,
  input  logic [1:0]  bmode,
  input  logic [7:0]  flags,
  output logic        busy,
  output logic        done,
  output logic        err,
  output logic [3:0]  err_code,
  output logic [31:0] raddr0,
  input  logic [31:0] rdata0,
  output logic [31:0] raddr1,
  input  logic [31:0] rdata1,
  output logic        we,
  output logic [31:0] waddr,
  output logic [31:0] wdata
);

  import mini_pkg::*;
  import otpu_fp::ftz;
  import otpu_fp::fp_add;
  import otpu_fp::fp_mul;
  import otpu_fp::fp_max;
  import otpu_fp::fp_gt;
  import otpu_fp::i2f;
  import otpu_fp::F_ZERO;
  import otpu_fp::F_ONE;

  localparam int P = 64;           // RED_PARTIALS

  // ------------------------------------------------------------------ latched configuration
  logic [7:0]  f_func;
  logic [31:0] f_dst, f_a, f_b, f_imm;
  logic [15:0] f_rows, f_cols, f_drs, f_ars, f_brs;
  logic [1:0]  f_bmode;
  logic [7:0]  f_flags;

  // ------------------------------------------------------------------ working state
  typedef enum logic [3:0] {
    S_IDLE      = 4'd0,
    S_CHK       = 4'd1,
    S_ROW       = 4'd2,
    S_ELEM      = 4'd3,
    S_FOLD      = 4'd4,
    S_WRITE     = 4'd5,
    S_ARG_MAX   = 4'd6,
    S_ARG_IDX   = 4'd7,
    S_HAZ       = 4'd8,
    S_LOAD_C    = 4'd9,
    S_LOAD_D    = 4'd10,
    S_OUT_ROW   = 4'd11,
    S_OUT_ELEM  = 4'd12,
    S_DONE      = 4'd13,
    S_ERROR     = 4'd14
  } rstate_t;
  rstate_t rs;

  logic [31:0] r, c, i;
  logic [31:0] fN;                       // padded element count (sums)
  logic [31:0] nreg;                     // current fold-tree round size
  logic [31:0] part [0:P-1];             // interleaved partial sums
  logic [31:0] rmax;                     // RMAX / ARGMAX value (raw bits)
  logic [31:0] rmax_c;                   // ARGMAX first index of the max
  logic [31:0] br;                       // OUTER: B(r)
  logic [31:0] cv [0:255];               // OUTER: buffered Cv
  logic [31:0] dv [0:255];               // OUTER: buffered Dv (column mode)
  logic [31:0] dv_scalar;                // OUTER: DSCALAR
  logic [TMEM_WORDS-1:0] written;        // OUTER: elementwise write bitmap (hazard model)

  // hazard precheck counters (reduction/ARGMAX: (earlier write, later read) pairs)
  logic [15:0] hj, hr;

  // ------------------------------------------------------------------ config-derived sizes
  logic [31:0] c_pad;                    // ceil(f_cols / P) * P
  assign c_pad = (({16'd0, f_cols} + P - 1) / P) * P;

  logic is_sum, is_max, is_arg, is_outer, is_rdot;
  assign is_sum   = (f_func == V_RSUM) || (f_func == V_RSSQ) || (f_func == V_RDOT);
  assign is_max   = (f_func == V_RMAX);
  assign is_arg   = (f_func == V_ARGMAX);
  assign is_outer = (f_func == V_OUTER);
  assign is_rdot  = (f_func == V_RDOT);

  // ------------------------------------------------------------------ address helpers (64-bit)
  logic [63:0] a_max, b_max, w_max, cv_max, dv_max;
  logic [63:0] addr64;
  always @* begin
    a_max  = {32'd0, f_a} + ({32'd0, f_rows} - 64'd1) * {32'd0, f_ars} + {32'd0, f_cols} - 64'd1;
    // B operand's largest index for RDOT/OUTER (OUTER is always ROW mode)
    case (f_bmode)
      2'd0:    b_max = {32'd0, f_b} + ({32'd0, f_rows} - 64'd1) * {32'd0, f_brs}
                      + {32'd0, f_cols} - 64'd1;
      2'd1:    b_max = {32'd0, f_b} + ({32'd0, f_rows} - 64'd1) * {32'd0, f_brs};
      2'd2:    b_max = {32'd0, f_b} + {32'd0, f_cols} - 64'd1;
      default: b_max = 64'd0;
    endcase
    // largest destination word: reductions one per row, ARGMAX a pair per row, OUTER a tile
    w_max = {32'd0, f_dst} + ({32'd0, f_rows} - 64'd1) * {32'd0, f_drs}
            + (is_arg ? 64'd1 : (is_outer ? {32'd0, f_cols} - 64'd1 : 64'd0));
    cv_max = {32'd0, f_imm} + {32'd0, f_cols} - 64'd1;
    dv_max = {32'd0, f_a} + ((f_flags & F_DSCALAR) ? 64'd0 : {32'd0, f_cols} - 64'd1);
  end

  // ------------------------------------------------------------------ read/write ports
  // B operand element address for the current (r,c) in the element loop
  logic [31:0] b_elem;
  always @* begin
    case (f_bmode)
      2'd0:    b_elem = f_b + r * f_brs + c;
      2'd1:    b_elem = f_b + r * f_brs;
      2'd2:    b_elem = f_b + c;
      default: b_elem = 32'd0;
    endcase
  end

  // element term of the sum / the value of the max loop, from the current read data
  logic [31:0] term;
  always @* begin
    term = F_ZERO;
    if (is_sum && c < f_cols) begin
      if (f_func == V_RSUM) begin
        term = rdata0;
      end else if (f_func == V_RSSQ) begin
        term = fp_mul(rdata0, rdata0);
      end else begin
        term = fp_mul(rdata0, (f_bmode == 2'd3) ? f_imm : rdata1);
      end
    end
  end

  // the ci of ARGMAX: int32 truncation of (first index + sign-extended base w7)
  logic [63:0] base64;
  logic [31:0] ci_raw;
  logic signed [31:0] ci_s;
  always @* begin
    base64 = (f_imm[31]) ? {32'hFFFF_FFFF, f_imm} : {32'd0, f_imm};
    ci_raw = 32'(base64 + {32'd0, rmax_c});
    ci_s   = $signed(ci_raw);
  end

  // Dv value of OUTER element c
  logic [31:0] dv_val;
  always @* begin
    if (f_flags & F_DONE) dv_val = F_ONE;
    else if (f_flags & F_DSCALAR) dv_val = dv_scalar;
    else dv_val = dv[c[7:0]];
  end

  always @* begin
    raddr0 = 32'd0;
    raddr1 = 32'd0;
    we     = 1'b0;
    waddr  = 32'd0;
    wdata  = 32'd0;
    case (rs)
      S_ELEM: begin
        if (c < f_cols) begin
          raddr0 = f_a + r * f_ars + c;
          if (is_rdot && f_bmode != 2'd3) raddr1 = b_elem;
        end
      end
      S_WRITE: begin
        we    = 1'b1;
        waddr = f_dst + r * f_drs;
        wdata = is_sum ? part[0] : rmax;
      end
      S_ARG_MAX: begin
        we    = 1'b1;
        waddr = f_dst + r * f_drs;
        wdata = rmax;
      end
      S_ARG_IDX: begin
        we    = 1'b1;
        waddr = f_dst + r * f_drs + 32'd1;
        wdata = i2f(ci_s);
      end
      S_LOAD_C: begin
        raddr0 = f_imm + c;
      end
      S_LOAD_D: begin
        raddr0 = (f_flags & F_DSCALAR) ? f_a : (f_a + c);
      end
      S_OUT_ROW: begin
        raddr1 = f_b + r * f_brs;
      end
      S_OUT_ELEM: begin
        raddr0 = f_dst + r * f_drs + c;
        if (c < f_cols) begin
          we    = 1'b1;
          waddr = f_dst + r * f_drs + c;
          wdata = fp_add(fp_mul(rdata0, dv_val), fp_mul(br, cv[c[7:0]]));
        end
      end
      default: begin
      end
    endcase
  end

  assign busy = (rs != S_IDLE);

  // ------------------------------------------------------------------ hazard precheck (reduce/argmax)
  // A write of row hj happens at the end of row hj; a read of a later row hr must not hit it.
  logic       haz_hit;
  logic [31:0] w_a, w_b;
  always @* begin
    w_a = f_dst + hj * f_drs;
    w_b = w_a + 32'd1;
    haz_hit = 1'b0;
    // A read set of row hr is the contiguous run a + hr*ars + [0, cols)
    if (w_a >= f_a + hr * f_ars && w_a <= f_a + hr * f_ars + f_cols - 32'd1) haz_hit = 1'b1;
    if (is_arg && w_b >= f_a + hr * f_ars && w_b <= f_a + hr * f_ars + f_cols - 32'd1) haz_hit = 1'b1;
    if (is_rdot) begin
      case (f_bmode)
        2'd0: begin
          if (w_a >= f_b + hr * f_brs && w_a <= f_b + hr * f_brs + f_cols - 32'd1) haz_hit = 1'b1;
        end
        2'd1: begin
          if (w_a == f_b + hr * f_brs) haz_hit = 1'b1;
        end
        2'd2: begin
          if (w_a >= f_b && w_a <= f_b + f_cols - 32'd1) haz_hit = 1'b1;
        end
        default: begin
        end
      endcase
    end
  end

  // ------------------------------------------------------------------ sequencer
  integer k;
  always_ff @(posedge clk) begin
    if (rst) begin
      rs <= S_IDLE;
      done <= 1'b0;
      err <= 1'b0;
      err_code <= ERR_NONE;
      f_func <= 8'd0; f_dst <= 32'd0; f_a <= 32'd0; f_b <= 32'd0; f_imm <= 32'd0;
      f_rows <= 16'd0; f_cols <= 16'd0; f_drs <= 16'd0; f_ars <= 16'd0; f_brs <= 16'd0;
      f_bmode <= 2'd0; f_flags <= 8'd0;
      r <= 32'd0; c <= 32'd0; i <= 32'd0; nreg <= 32'd0; fN <= 32'd0;
      rmax <= 32'd0; rmax_c <= 32'd0; br <= 32'd0; dv_scalar <= F_ONE;
      hj <= 16'd0; hr <= 16'd0;
      written <= '0;
      for (k = 0; k < P; k = k + 1) part[k] <= F_ZERO;
      for (k = 0; k < 256; k = k + 1) begin cv[k] <= F_ZERO; dv[k] <= F_ZERO; end
    end else begin
      done <= 1'b0;
      case (rs)
        S_IDLE: begin
          if (start) begin
            f_func  <= func;
            f_dst <= dst; f_a <= a; f_b <= b; f_imm <= imm;
            f_rows <= rows; f_cols <= cols; f_drs <= drs; f_ars <= ars; f_brs <= brs;
            f_bmode <= bmode; f_flags <= flags;
            r <= 32'd0; c <= 32'd0; i <= 32'd0;
            fN <= 32'd0;
            written <= '0;
            rs <= S_CHK;
          end
        end

        // ---- checks in isasim's order (shape 10, range 4, hazard 5, write range 4)
        S_CHK: begin
          fN <= c_pad;
          if (is_outer) begin
            if (f_bmode != 2'd1 || f_cols > 16'd256) begin
              err <= 1'b1; err_code <= ERR_VOP_SHAPE; rs <= S_ERROR;
            end else if (cv_max >= TMEM_WORDS) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else if (!(f_flags & F_DONE) && (dv_max >= TMEM_WORDS)) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else if (b_max >= TMEM_WORDS) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else if (w_max >= TMEM_WORDS) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else begin
              c <= 32'd0;
              rs <= S_LOAD_C;
            end
          end else begin
            if (a_max >= TMEM_WORDS) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else if (is_rdot && f_bmode != 2'd3 && b_max >= TMEM_WORDS) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else if (is_arg && f_rows > 16'd1 && f_drs < 16'd2) begin
              err <= 1'b1; err_code <= ERR_VOP_SHAPE; rs <= S_ERROR;
            end else if (f_rows > 16'd1) begin
              hj <= 16'd0; hr <= 16'd1;
              rs <= S_HAZ;
            end else if (w_max >= TMEM_WORDS) begin
              err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
            end else begin
              rs <= S_ROW;
            end
          end
        end

        // ---- the hazard precheck (rows > 1): (earlier write, later read) pairs
        S_HAZ: begin
          if (haz_hit) begin
            err <= 1'b1; err_code <= ERR_VOP_HAZ; rs <= S_ERROR;
          end else if (hr + 16'd1 >= f_rows) begin
            if (hj + 16'd1 >= f_rows - 16'd1) begin
              // all pairs checked; the write range is checked after the hazard (isasim order)
              if (w_max >= TMEM_WORDS) begin
                err <= 1'b1; err_code <= ERR_TMEM; rs <= S_ERROR;
              end else begin
                rs <= S_ROW;
              end
            end else begin
              hj <= hj + 16'd1;
              hr <= hj + 16'd2;
            end
          end else begin
            hr <= hr + 16'd1;
          end
        end

        // ---- per row: reset the interleaved partials (sums) and the column counter
        S_ROW: begin
          c    <= 32'd0;
          for (k = 0; k < P; k = k + 1) part[k] <= F_ZERO;
          rs   <= S_ELEM;
        end

        // ---- one element per cycle: partial chain / max fold
        S_ELEM: begin
          if (is_sum) begin
            if (c >= fN) begin
              i <= 32'd0; nreg <= 32'd32;
              rs <= S_FOLD;
            end else begin
              part[c % P] <= fp_add(part[c % P], term);
              c <= c + 32'd1;
            end
          end else if (is_max || is_arg) begin
            if (c >= f_cols) begin
              if (is_arg) begin
                rs <= S_ARG_MAX;
              end else begin
                rs <= S_WRITE;
              end
            end else if (c == 32'd0) begin
              rmax <= ftz(rdata0);
              rmax_c <= 32'd0;
              c <= c + 32'd1;
            end else begin
              if (fp_gt(rdata0, rmax)) begin
                rmax   <= ftz(rdata0);
                rmax_c <= c;
              end
              c <= c + 32'd1;
            end
          end else begin
            err <= 1'b1; err_code <= ERR_ILLEGAL; rs <= S_ERROR;
          end
        end

        // ---- the folding tree: 6 rounds (32,16,8,4,2,1), x[i] = fp_add(x[i], x[i+n])
        S_FOLD: begin
          if (i < nreg) begin
            part[i] <= fp_add(part[i], part[i + nreg]);
            i <= i + 32'd1;
          end else if (nreg > 32'd1) begin
            i    <= 32'd0;
            nreg <= nreg >> 1;
          end else begin
            rs <= S_WRITE;
          end
        end

        // ---- write the row's scalar, then the next row
        S_WRITE, S_ARG_MAX, S_ARG_IDX: begin
          if (rs == S_ARG_MAX) begin
            rs <= S_ARG_IDX;
          end else begin
            r <= r + 32'd1;
            if (r + 32'd1 >= f_rows) begin
              rs <= S_DONE;
            end else begin
              rs <= S_ROW;
            end
          end
        end

        // ---- OUTER: buffer Cv (cols reads), then Dv (one or cols reads), before any write
        S_LOAD_C: begin
          if (c >= f_cols) begin
            c <= 32'd0;
            if (f_flags & F_DONE) begin
              dv_scalar <= F_ONE;
              r <= 32'd0; c <= 32'd0;
              rs <= S_OUT_ROW;
            end else begin
              rs <= S_LOAD_D;
            end
          end else begin
            cv[c[7:0]] <= rdata0;
            c <= c + 32'd1;
          end
        end

        S_LOAD_D: begin
          if (f_flags & F_DSCALAR) begin
            dv_scalar <= rdata0;
            r <= 32'd0; c <= 32'd0;
            rs <= S_OUT_ROW;
          end else if (c >= f_cols) begin
            r <= 32'd0; c <= 32'd0;
            rs <= S_OUT_ROW;
          end else begin
            dv[c[7:0]] <= rdata0;
            c <= c + 32'd1;
          end
        end

        S_OUT_ROW: begin
          // B(r) read; the old destination is read per element (it may alias Cv/Dv: buffered)
          if (written[f_b + r * f_brs]) begin
            err <= 1'b1; err_code <= ERR_VOP_HAZ; rs <= S_ERROR;
          end else begin
            br <= rdata1;
            c  <= 32'd0;
            rs <= S_OUT_ELEM;
          end
        end

        S_OUT_ELEM: begin
          if (c >= f_cols) begin
            r <= r + 32'd1;
            if (r + 32'd1 >= f_rows) begin
              rs <= S_DONE;
            end else begin
              rs <= S_OUT_ROW;
            end
          end else if (written[f_dst + r * f_drs + c]) begin
            err <= 1'b1; err_code <= ERR_VOP_HAZ; rs <= S_ERROR;
          end else begin
            written[f_dst + r * f_drs + c] <= 1'b1;
            c <= c + 32'd1;
          end
        end

        S_DONE: begin
          done <= 1'b1;
          rs   <= S_IDLE;
        end

        S_ERROR: begin
          err <= 1'b1;
        end

        default: begin
          err <= 1'b1; err_code <= ERR_ILLEGAL; rs <= S_ERROR;
        end
      endcase
    end
  end

endmodule
