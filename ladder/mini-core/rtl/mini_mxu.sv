// Ladder step 7 — mini MXU: the int8 MM (WF = 0) with MX scales and the fp32 epilogue,
// bit-exact with opentpu/isasim.py's `_mm` / `_mx_scales` (docs/isa.md "MM", "Weight formats").
//
// One element per cycle, fully serialized; timing is not part of the contract, state is.  For
// every output y[j][n] (stationary ACT row j, streamed weight row n):
//
//   acc = 0                                              exact integer, signed 48-bit (< 2^47)
//   for k in 0..KB-1:                                    ACT block ab+k, weight block k
//     for g in 0..3:                                     the D/4 sub-blocks of a D-byte block
//       c  = sum over the 8 elements of ACT[j][(ab+k)*D + g*8 + i] * w[n][k*D + g*8 + i]
//       sh = 16 - dw[n][k0+k] - da[j][ab+k][g]           dw, da unsigned bytes: sh is signed
//       acc = acc + (sh >= 0 ? c << sh : 0)              groups past the W = 16 window drop
//   y = fp_mul(fp_mul(i2f48(acc), Sw[n]), fp_mul(Sa[j][ab], 2^-16))
//   if ACC: y = fp_add(T[out + j*ors + n], y)
//   T[out + j*ors + n] = y
//   if RMAX: the row's maximum of the written y; after all M*N outputs,
//            T[out + M*ors + j] = rmax[j]
//
// The arithmetic is the product tree's `otpu_fp` package (fp_mul / fp_add / fp_gt): the
// epilogue's three multiplies are isasim's association, each its own rounded operation.  The
// accumulator-to-fp32 conversion is the production MXU's `i2f48` (round to nearest even; the
// ISA keeps |acc| < 2^47, so the result is normal or +0; same algorithm as rtl/mxu/otpu_mxu.sv's
// otpu_mx_lane) because otpu_fp::i2f is 32-bit only.
//
// Only the int8 weight format (WF 0) and the flags UNIT / ACC / RMAX are in this rung: PAIR,
// RSC, ASCALE and the 4-bit / NVFP4 formats latch error 8 (unsupported), so a program that
// relies on them fails instead of computing wrong bits.  Bounds / alignment / scale-row checks
// mirror isasim's _mm/_mx_scales and latch error 9; an ACT row whose blocks hold different Sa
// (two QACTs) is also error 9, checked before any TMEM write; output words outside TMEM are
// error 4.
//
// Documented serialized limitation (docs/mini-core.md): isasim reads every old ACC value before
// writing any output, while this unit reads T[addr] just before writing addr.  It is bit-exact
// as long as the M*N output addresses are distinct, i.e. ors >= N (the production convention;
// the step-7 test vectors all satisfy it).
`timescale 1ns/1ps
module mini_mxu #(
  parameter int D          = 32,
  parameter int MCOLS      = 4,
  parameter int ACT_BLOCKS = 16,
  parameter int ACT_ROWS   = 4,
  parameter int TMEM_WORDS = 4096,
  parameter int DRAM_BYTES = 262144
) (
  input  logic        clk,
  input  logic        rst,              // synchronous, active high
  input  logic        start,            // one-cycle pulse from the sequencer
  // resolved instruction fields (the top adds R[ra/rb/rc] to the payload words)
  input  logic [31:0] sa, ssa, out, rs, srs,
  input  logic [15:0] n, ors,
  input  logic [7:0]  kb, k0, m, ab,
  input  logic [7:0]  flags,
  output logic        busy,
  output logic        done,             // one-cycle pulse: every write has landed
  output logic        err,
  output logic [3:0]  err_code,         // 4 TMEM, 8 unsupported, 9 bounds/alignment
  // DRAM read port: streamed weight words and the scale row
  output logic [31:0] dram_raddr,
  input  logic [31:0] dram_rdata,
  // ACT RAM read ports (step 6's mini_actram): a 32-bit word of four int8 bytes at
  // act[row][block*D/4 + word], and the (row, block) scale record {da[3:0], Sa}
  output logic [31:0] act_row,
  output logic [31:0] act_word,
  input  logic [31:0] act_rdata,
  output logic [31:0] rec_row,
  output logic [31:0] rec_block,
  input  logic [63:0] rec_rdata,
  // TMEM: one read (the ACC value being accumulated into) + one write port
  output logic [31:0] tmem_raddr,
  input  logic [31:0] tmem_rdata,
  output logic [31:0] tmem_waddr,
  output logic [31:0] tmem_wdata,
  output logic        tmem_we
);

  import otpu_fp::*;

  localparam logic [3:0] MXERR_TMEM   = 4'd4;
  localparam logic [3:0] MXERR_UNSUP  = 4'd8;
  localparam logic [3:0] MXERR_BOUNDS = 4'd9;

  // MM flags (docs/isa.md, opentpu/isa.py)
  localparam logic [7:0] MF_UNIT   = 8'h01;
  localparam logic [7:0] MF_ACC    = 8'h02;
  localparam logic [7:0] MF_RMAX   = 8'h04;
  localparam logic [7:0] MF_ASCALE = 8'h08;
  localparam logic [7:0] MF_PAIR   = 8'h40;
  localparam logic [7:0] MF_RSC    = 8'h80;
  localparam logic [7:0] MF_WF     = 8'h30;      // flags[5:4]

  localparam int NW = D / 4;                     // 32-bit ACT words per D-byte block
  localparam int SZ = D / 4;                     // int8 elements per sub-block (8 at D = 32)
  localparam int W  = 16;                        // the int8 shift window
  localparam logic [31:0] TWO_M16 = 32'h3780_0000;   // fp32 2^-16
  localparam logic [63:0] TMEM_LIM = TMEM_WORDS;
  localparam logic [63:0] DRAM_LIM = DRAM_BYTES;

  // ------------------------------------------------------------------ latched configuration
  logic [31:0] f_sa, f_ssa, f_out, f_rs, f_srs;
  logic [15:0] f_n, f_ors;
  logic [7:0]  f_kb, f_k0, f_m, f_ab, f_flags;
  logic        f_unit, f_acc, f_rmax;

  // ------------------------------------------------------------------ loop counters / state
  logic [15:0] n_i;            // output column
  logic [7:0]  j_i;            // output row
  logic [7:0]  k_i;            // block
  logic [7:0]  g_i;            // sub-block
  logic [7:0]  cj_i, ck_i;     // the Sa-consistency walk (every ACT row's blocks)
  logic [1:0]  h_i;            // 32-bit ACT word inside the sub-block (2 words = 8 elements)
  logic        running, done_r, err_r;
  logic [3:0]  ecode_r;

  // per-row / per-column / per-block scratch
  logic [31:0] sw_r;           // Sw[n] (1.0 when UNIT)
  logic [31:0] sa_first;       // the first Sa the consistency walk saw for this row
  logic [31:0] sa_scaled;      // fp_mul(Sa[j][ab], 2^-16)
  logic [7:0]  dw_r;           // dw[n][k0+k] (0 when UNIT)
  logic [31:0] da_r;           // the four da bytes of (j, ab+k)
  logic signed [47:0] acc;     // the exact accumulator
  logic signed [31:0] part;    // the first half of a sub-block's sum (4 products)
  logic [31:0] y_r;            // this output's fp32 bits
  logic [31:0] rmax_r [0:3];   // RMAX's per-row maxima (M <= MCOLS = 4)
  logic        rmax_init [0:3];

  // ------------------------------------------------------------------ FSM
  typedef enum logic [3:0] {
    M_IDLE     = 4'd0,
    M_CHK      = 4'd1,   // field checks (combinational), then the ACT Sa walk
    M_CHK_SA   = 4'd2,   // the bitwise Sa consistency walk over every (row, block)
    M_CHK_TMEM = 4'd3,   // the output TMEM range check
    M_ROW      = 4'd4,   // per j: Sa' = fp_mul(Sa[j][ab], 2^-16)
    M_COL      = 4'd5,   // per n: Sw[n], acc = 0
    M_BLK      = 4'd6,   // per k: dw[n][k0+k] and the (j, ab+k) scale record
    M_GRP      = 4'd7,   // per g: two 32-bit ACT words of four int8 products each
    M_EPI      = 4'd8,   // i2f48 and the three rounded multiplies (+ ACC)
    M_WR       = 4'd9,   // write the output word
    M_NEXTK    = 4'd10,  // next block, or the output's epilogue
    M_NEXTN    = 4'd11,  // next column, or the next row / the row maxima
    M_RMAX     = 4'd12,  // write out + M*ors + j after every output
    M_DONE     = 4'd13,
    M_ERROR    = 4'd14
  } mstate_t;
  mstate_t st;

  // ------------------------------------------------------------------ field checks (isasim's
  // _mm/_mx_scales order; everything after the 32-bit register+immediate wrap is 64-bit)
  logic [63:0] w_end64, kb_end64, scl_end64, dw_end64, out_end64, rmax_end64;
  logic        bad_unsup, bad_bounds, bad_tmem;

  always @* begin
    w_end64    = {32'd0, f_sa}
                 + ({48'd0, (f_n - 16'd1)} * {32'd0, f_rs})
                 + {32'd0, (f_kb * 32'(D))};
    kb_end64   = {56'd0, (f_ab + f_kb)};
    scl_end64  = {32'd0, f_ssa}
                 + ({48'd0, (f_n - 16'd1)} * {32'd0, f_srs}) + 64'd4;
    dw_end64   = {32'd0, f_ssa}
                 + ({48'd0, (f_n - 16'd1)} * {32'd0, f_srs})
                 + 64'd4 + {56'd0, f_k0} + {56'd0, f_kb};
    out_end64  = {32'd0, f_out}
                 + ({48'd0, (f_m - 8'd1)} * {48'd0, f_ors})
                 + {48'd0, (f_n - 16'd1)};
    rmax_end64 = {32'd0, f_out}
                 + ({48'd0, f_m} * {48'd0, f_ors})
                 + {48'd0, (f_m - 8'd1)};
    bad_unsup  = ((f_flags & MF_WF) != 8'd0)
                 || ((f_flags & (MF_PAIR | MF_RSC | MF_ASCALE)) != 8'd0);
    bad_bounds = (f_n == 16'd0) || (f_kb == 8'd0) || (f_m == 8'd0)
                 || (f_m > ACT_ROWS)
                 || (kb_end64 > {56'd0, ACT_BLOCKS})
                 || ((f_m > MCOLS) && f_rmax)
                 || (f_sa % D != 0) || (f_rs % D != 0)
                 || (w_end64 > DRAM_LIM)
                 || (!f_unit && ((f_ssa % 4 != 0) || (f_srs % 4 != 0)))
                 || (!f_unit && (scl_end64 > DRAM_LIM))
                 || (!f_unit && (dw_end64 > DRAM_LIM));
    bad_tmem   = (out_end64 >= TMEM_LIM) || (f_rmax && (rmax_end64 >= TMEM_LIM));
  end

  // ------------------------------------------------------------------ status
  assign busy = running;
  assign done = done_r;
  assign err  = err_r;

  // ------------------------------------------------------------------ the accumulator to fp32:
  // the production MXU's epilogue converter (rtl/mxu/otpu_mxu.sv, otpu_mx_lane): signed 48-bit
  // to fp32, round to nearest even.  |x| < 2^47 -> normal or +0.
  function automatic logic [5:0] lzc48(input logic [47:0] xb);
    if (xb[47:16] != 0) return lzc32(xb[47:16]);
    return 6'd32 + 6'(lzc32({xb[15:0], 16'd0}));
  endfunction

  function automatic logic [31:0] i2f48(input logic signed [47:0] x);
    logic        s, z;
    logic [47:0] g, nrm;
    logic [5:0]  lz;
    logic [23:0] mm;
    logic [24:0] mr;
    logic        gr, sty;
    logic [8:0]  e;
    if (x == 48'sd0) return 32'h0000_0000;
    s   = x[47];
    g   = s ? (~x + 48'd1) : x;
    z   = (g == 48'd0);
    lz  = lzc48(g);
    nrm = g << lz;
    e   = 9'd174 - 9'(lz);
    mm  = nrm[47:24];
    gr  = nrm[23];
    sty = |nrm[22:0];
    mr  = {1'b0, mm} + ((gr && (sty || mm[0])) ? 25'd1 : 25'd0);
    if (mr[24]) e = e + 9'd1;
    return z ? 32'h0000_0000 : {s, e[7:0], mr[22:0]};
  endfunction

  // ------------------------------------------------------------------ int8 products
  function automatic logic signed [31:0] muls8(input logic [7:0] p, input logic [7:0] q);
    logic signed [31:0] sp, sq;
    sp = {{24{p[7]}}, p};
    sq = {{24{q[7]}}, q};
    return sp * sq;
  endfunction

  logic signed [31:0] quad;         // the four products of one 32-bit ACT/weight word
  logic signed [31:0] grp_sum;      // the whole sub-block sum (8 products)

  always @* begin
    quad = muls8(dram_rdata[7:0],   act_rdata[7:0])
         + muls8(dram_rdata[15:8],  act_rdata[15:8])
         + muls8(dram_rdata[23:16], act_rdata[23:16])
         + muls8(dram_rdata[31:24], act_rdata[31:24]);
  end

  assign grp_sum = part + quad;

  // the sub-block's shift: 16 - dw - da, both unsigned bytes -> signed, possibly < 0
  logic [7:0]         da_byte;
  logic signed [11:0] sh;
  always @* begin
    da_byte = (da_r >> {g_i[1:0], 3'd0}) & 32'h0000_00FF;     // byte g of the record
    sh = 12'sd16 - $signed({4'd0, dw_r}) - $signed({4'd0, da_byte});
  end

  // the scale record as its two halves: the Sa word and the four da bytes (da[g] in byte g)
  wire [31:0] sa_word = rec_rdata[31:0];
  wire [31:0] da_word = rec_rdata[63:32];

  // ------------------------------------------------------------------ address selection
  logic [31:0] dw_addr32;
  assign dw_addr32 = f_ssa + ({16'd0, n_i} * f_srs) + 32'd4 + {24'd0, f_k0} + {24'd0, k_i};

  always @* begin
    dram_raddr = 32'd0;
    act_row    = 32'd0;
    act_word   = 32'd0;
    rec_row    = 32'd0;
    rec_block  = 32'd0;
    case (st)
      M_CHK_SA: begin
        rec_row   = {24'd0, cj_i};
        rec_block = {24'd0, f_ab} + {24'd0, ck_i};
      end
      M_ROW: begin
        rec_row   = {24'd0, j_i};
        rec_block = {24'd0, f_ab};
      end
      M_COL: dram_raddr = f_unit ? 32'd0 : (f_ssa + ({16'd0, n_i} * f_srs));
      M_BLK: begin
        // the dw byte: read its containing 32-bit word (the byte itself need not be aligned;
        // the word is in range once dw_end64 passed)
        dram_raddr = f_unit ? 32'd0 : {dw_addr32[31:2], 2'b00};
        rec_row    = {24'd0, j_i};
        rec_block  = {24'd0, f_ab} + {24'd0, k_i};
      end
      M_GRP: begin
        act_row    = {24'd0, j_i};
        act_word   = (({24'd0, f_ab} + {24'd0, k_i}) * NW) + ({24'd0, g_i} * 32'd2) + {30'd0, h_i};
        dram_raddr = f_sa + ({16'd0, n_i} * f_rs) + (k_i * D) + (g_i * SZ) + (h_i * 4);
      end
      default: ;
    endcase
  end

  // the output word / the RMAX word
  logic [31:0] out_addr32, rmax_addr32;
  assign out_addr32  = f_out + ({16'd0, j_i} * f_ors) + {16'd0, n_i};
  assign rmax_addr32 = f_out + ({16'd0, f_m} * f_ors) + {24'd0, j_i};

  // TMEM: the ACC read of the output word being replaced, and the two write kinds
  assign tmem_raddr = (st == M_EPI) ? out_addr32 : 32'd0;

  logic        we_now;
  logic [31:0] waddr_now, wdata_now;
  always @* begin
    we_now    = 1'b0;
    waddr_now = out_addr32;
    wdata_now = y_r;
    case (st)
      M_WR: begin
        we_now    = 1'b1;
        waddr_now = out_addr32;
        wdata_now = y_r;
      end
      M_RMAX: begin
        we_now    = 1'b1;
        waddr_now = rmax_addr32;
        wdata_now = rmax_r[j_i[1:0]];
      end
      default: ;
    endcase
  end

  assign tmem_we    = we_now;
  assign tmem_waddr = waddr_now;
  assign tmem_wdata = wdata_now;

  // ------------------------------------------------------------------ the epilogue (isasim's
  // association: (i2f48(acc) * Sw) * (Sa * 2^-16), each multiply separately rounded)
  logic [31:0] epi_mul, epi_y, y_next;
  always @* begin
    epi_mul = fp_mul(i2f48(acc), sw_r);
    epi_y   = fp_mul(epi_mul, sa_scaled);
    y_next  = f_acc ? fp_add(tmem_rdata, epi_y) : epi_y;
  end

  // ------------------------------------------------------------------ sequencer
  integer z;
  always_ff @(posedge clk) begin
    if (rst) begin
      f_sa <= 32'd0; f_ssa <= 32'd0; f_out <= 32'd0; f_rs <= 32'd0; f_srs <= 32'd0;
      f_n <= 16'd0; f_ors <= 16'd0;
      f_kb <= 8'd0; f_k0 <= 8'd0; f_m <= 8'd0; f_ab <= 8'd0; f_flags <= 8'd0;
      f_unit <= 1'b0; f_acc <= 1'b0; f_rmax <= 1'b0;
      n_i <= 16'd0; j_i <= 8'd0; k_i <= 8'd0; g_i <= 8'd0; cj_i <= 8'd0; ck_i <= 8'd0;
      h_i <= 2'd0;
      running <= 1'b0; done_r <= 1'b0; err_r <= 1'b0; ecode_r <= 4'd0;
      sw_r <= F_ONE; sa_first <= 32'd0; sa_scaled <= 32'd0; dw_r <= 8'd0; da_r <= 32'd0;
      acc <= 48'sd0; part <= 32'sd0; y_r <= 32'd0; st <= M_IDLE;
      for (z = 0; z < 4; z = z + 1) begin
        rmax_r[z] <= 32'd0;
        rmax_init[z] <= 1'b0;
      end
    end else begin
      done_r <= 1'b0;
      case (st)
        M_IDLE: begin
          if (start && !running) begin
            f_sa <= sa; f_ssa <= ssa; f_out <= out; f_rs <= rs; f_srs <= srs;
            f_n <= n; f_ors <= ors;
            f_kb <= kb; f_k0 <= k0; f_m <= m; f_ab <= ab; f_flags <= flags;
            f_unit <= (flags & MF_UNIT) != 0;
            f_acc  <= (flags & MF_ACC)  != 0;
            f_rmax <= (flags & MF_RMAX) != 0;
            n_i <= 16'd0; j_i <= 8'd0; k_i <= 8'd0; g_i <= 8'd0; h_i <= 2'd0;
            cj_i <= 8'd0; ck_i <= 8'd0;
            acc <= 48'sd0; part <= 32'sd0;
            for (z = 0; z < 4; z = z + 1) begin
              rmax_r[z] <= 32'd0;
              rmax_init[z] <= 1'b0;
            end
            running <= 1'b1;
            err_r <= 1'b0;
            ecode_r <= 4'd0;
            st <= M_CHK;
          end
        end

        // ---- checks 0-6 (combinational), then hand over to the ACT Sa walk
        M_CHK: begin
          if (bad_unsup) begin
            err_r <= 1'b1; ecode_r <= MXERR_UNSUP; running <= 1'b0; st <= M_ERROR;
          end else if (bad_bounds) begin
            err_r <= 1'b1; ecode_r <= MXERR_BOUNDS; running <= 1'b0; st <= M_ERROR;
          end else begin
            cj_i <= 8'd0;
            ck_i <= 8'd0;
            st   <= M_CHK_SA;
          end
        end

        // ---- check 7: every ACT row's KB blocks must hold the same Sa bits (one QACT row).
        // The srec read is combinational; block ab's word is latched in the ck = 0 cycle and
        // the rest compare against it.
        M_CHK_SA: begin
          if (ck_i == 8'd0) begin
            sa_first <= sa_word;
            ck_i     <= 8'd1;
          end else if (ck_i < f_kb) begin
            if (sa_word != sa_first) begin
              err_r <= 1'b1; ecode_r <= MXERR_BOUNDS; running <= 1'b0; st <= M_ERROR;
            end else begin
              ck_i <= ck_i + 8'd1;
            end
          end else begin
            ck_i <= 8'd0;
            if (cj_i + 8'd1 < f_m) begin
              cj_i <= cj_i + 8'd1;
            end else begin
              st <= M_CHK_TMEM;
            end
          end
        end

        // ---- check 8: every output word (and the RMAX words) inside TMEM; no write has
        // happened yet, so an error leaves the state untouched like isasim's tput check
        M_CHK_TMEM: begin
          if (bad_tmem) begin
            err_r <= 1'b1; ecode_r <= MXERR_TMEM; running <= 1'b0; st <= M_ERROR;
          end else begin
            j_i <= 8'd0;
            st  <= M_ROW;
          end
        end

        // ---- per row j: Sa' = fp_mul(Sa[j][ab], 2^-16) (the record read is combinational)
        M_ROW: begin
          sa_scaled <= fp_mul(sa_word, TWO_M16);
          n_i       <= 16'd0;
          rmax_init[j_i] <= 1'b0;
          st        <= M_COL;
        end

        // ---- per column n: Sw[n] (UNIT: 1.0, no read) and a fresh accumulator
        M_COL: begin
          sw_r <= f_unit ? F_ONE : dram_rdata;
          acc  <= 48'sd0;
          k_i  <= 8'd0;
          st   <= M_BLK;
        end

        // ---- per block k: dw[n][k0+k] (UNIT: 0) and the (j, ab+k) scale record (Sa + da)
        M_BLK: begin
          dw_r <= f_unit ? 8'd0
                         : ((dram_rdata >> {dw_addr32[1:0], 3'd0}) & 32'h0000_00FF);
          da_r <= da_word;
          g_i  <= 8'd0;
          h_i  <= 2'd0;
          part <= 32'sd0;
          st   <= M_GRP;
        end

        // ---- one sub-block: two 32-bit ACT words, four int8 products each; then the shifted
        // group sum folds into the accumulator (sh < 0: past the window, drop the group)
        M_GRP: begin
          if (h_i == 2'd0) begin
            part <= quad;
            h_i  <= 2'd1;
          end else begin
            h_i <= 2'd0;
            if (sh >= 12'sd0) begin
              acc <= acc + ({{16{grp_sum[31]}}, grp_sum} <<< sh[4:0]);
            end
            g_i <= g_i + 8'd1;
            if (g_i == 8'd3) begin
              st <= M_NEXTK;
            end
          end
        end

        // ---- the epilogue of one output (ACC reads the old word through the TMEM read port)
        M_EPI: begin
          y_r <= y_next;
          st  <= M_WR;
        end

        // ---- write the output word and fold it into its row's maximum
        M_WR: begin
          if (f_rmax) begin
            if (!rmax_init[j_i[1:0]] || !fp_gt(rmax_r[j_i[1:0]], y_r)) begin
              rmax_r[j_i[1:0]]    <= y_r;
              rmax_init[j_i[1:0]] <= 1'b1;
            end
          end
          st <= M_NEXTN;
        end

        // ---- next block, or this output's epilogue after the last one
        M_NEXTK: begin
          if (k_i + 8'd1 < f_kb) begin
            k_i <= k_i + 8'd1;
            st  <= M_BLK;
          end else begin
            st <= M_EPI;
          end
        end

        // ---- next column, or (after the last column) the next row / the row maxima
        M_NEXTN: begin
          if (n_i + 16'd1 < f_n) begin
            n_i <= n_i + 16'd1;
            st  <= M_COL;
          end else if (j_i + 8'd1 < f_m) begin
            j_i <= j_i + 8'd1;
            st  <= M_ROW;
          end else if (f_rmax) begin
            j_i <= 8'd0;
            st  <= M_RMAX;
          end else begin
            st <= M_DONE;
          end
        end

        // ---- RMAX: T[out + M*ors + j] = the row's maximum, after every output write
        M_RMAX: begin
          if (j_i + 8'd1 < f_m) begin
            j_i <= j_i + 8'd1;
          end else begin
            st <= M_DONE;
          end
        end

        M_DONE: begin
          done_r  <= 1'b1;
          running <= 1'b0;
          st      <= M_IDLE;
        end

        M_ERROR: begin
          err_r <= 1'b1;
        end

        default: st <= M_IDLE;
      endcase
    end
  end

  assign err_code = ecode_r;

endmodule
