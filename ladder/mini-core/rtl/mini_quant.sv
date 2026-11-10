// Ladder step 6 — quantizer: QACT (TMEM -> ACT RAM) and QST (TMEM -> DRAM int8 + scale row).
//
// Serialized on purpose (timing is irrelevant for the ladder, state is everything): one
// element per cycle, one row at a time, two passes over the row:
//
//   pass 1  read x, ftz, apply RSCALE/CSCALE, track the row's amax and each group's a
//   pass 2  re-read x (same bits), q = otpu_fp::q8(x * invg), write ACT bytes / DRAM bytes
//
// exactly mirroring opentpu/fp32.py::quantize_mx + mx_offset + q8 and the ISA simulator's
// _quant_rows/_qact/_qst (the oracle).  Groups are D/NSUB elements for QACT (4 sub-block
// offsets per D-block) and D for QST; ROW mode sets every offset to 0.  QACT writes the
// scale record (Sa, da) into the ACT RAM, QST writes the int8 bytes plus its scale row
// (S little endian, then one offset byte per K-block, zero padded to 4 bytes).
`timescale 1ns/1ps
module mini_quant #(
  parameter int D          = 32,
  parameter int MCOLS      = 4,
  parameter int ACT_BLOCKS = 16,
  parameter int ACT_ROWS   = 4,
  parameter int TMEM_WORDS = 4096,
  parameter int DRAM_BYTES = 262144
) (
  input  logic        clk,
  input  logic        rst,

  input  logic        start,      // one cycle, operands latched below
  input  logic        is_qst,     // 0 = QACT (0x21), 1 = QST (0x22)
  input  logic [31:0] src, rows, kb, srs, ab, cscale, rscale, dst, sdst, drs, es,
  input  logic [7:0]  flags,

  // TMEM read ports (port 0: the row data / the RSCALE word, port 1: the CSCALE word)
  output logic [31:0] tmem_raddr0,
  output logic [31:0] tmem_raddr1,
  input  logic [31:0] tmem_rdata0,
  input  logic [31:0] tmem_rdata1,

  // ACT RAM write ports (quantizer side)
  output logic        act_we,
  output logic [31:0] act_row,
  output logic [31:0] act_lin,
  output logic [7:0]  act_data,
  output logic        act_we2,
  output logic [31:0] act_row2,
  output logic [31:0] act_lin2,
  output logic [7:0]  act_data2,
  output logic        s_we,
  output logic [31:0] s_row,
  output logic [31:0] s_block,
  output logic [31:0] s_data,
  output logic        d_we,
  output logic [31:0] d_row,
  output logic [31:0] d_block,
  output logic [31:0] d_data,

  // DRAM byte write port (QST data bytes and the scale row)
  output logic        dram_we,
  output logic [31:0] dram_waddr,
  output logic [7:0]  dram_wdata,

  output logic        busy,
  output logic        done,
  output logic        err,
  output logic [2:0]  err_code
);

  import mini_pkg::*;
  // explicit otpu_fp imports: both packages have a constant named F_HALF
  import otpu_fp::ftz;
  import otpu_fp::fabs;
  import otpu_fp::fp_mul;
  import otpu_fp::fp_recip;
  import otpu_fp::q8;
  import otpu_fp::F_ONE;
  import otpu_fp::F_127;
  import otpu_fp::F_INV127;

  localparam int NSUB   = 4;
  localparam int MAXG   = ACT_BLOCKS * NSUB;       // enough groups for every QACT row
  localparam int ROW_B  = ACT_BLOCKS * D;         // ACT bytes in a row

  // ---- configuration (latched from start)
  logic        cfg_qst;
  logic [31:0] cfg_src, cfg_rows, cfg_kb, cfg_srs, cfg_ab, cfg_cscale, cfg_rscale;
  logic [31:0] cfg_dst, cfg_sdst, cfg_drs, cfg_es;
  logic [7:0]  cfg_fl;

  logic [31:0] n_elem;        // KB*D
  logic [31:0] gsize;         // D/NSUB (QACT) or D (QST)
  logic [31:0] ngroups;       // KB*NSUB (QACT) or KB (QST)
  logic [31:0] ne;            // QST bytes written per row (HALF: n_elem/2)
  logic [31:0] slen;          // QST scale-row length in bytes
  logic [31:0] row_mode, dup, half;

  // ---- working state
  logic [31:0] r, c, g, b, k;    // row / element / group / block / scale byte counters
  logic [31:0] amax;
  logic [31:0] s_val, inv_val, rfac;
  logic [31:0] gmax [0:MAXG-1];
  logic [31:0] dval [0:MAXG-1];  // the per-group offset (uint8 domain)
  logic [31:0] invg [0:MAXG-1];  // fp32 inv * 2^d
  logic [31:0] dbyte [0:ACT_BLOCKS-1];

  logic [31:0] taddr;            // current element's TMEM address
  logic [31:0] scaled_bits;      // x after ftz and the RSCALE/CSCALE multiplies
  logic [7:0]  q_byte;

  // ================================================================== helpers
  // isasim's mx_offset(): (exp(amax) - exp(a)) - (mant(a) > mant(amax)), clipped to [0, 31];
  // 0 where a is 0.
  function automatic logic [7:0] d_offset(input logic [31:0] a_bits, input logic [31:0] amax_bits);
    logic signed [31:0] d;
    if (a_bits == 32'd0) begin
      return 8'd0;
    end
    d = $signed({24'd0, amax_bits[30:23]}) - $signed({24'd0, a_bits[30:23]})
        - ((a_bits[22:0] > amax_bits[22:0]) ? 32'sd1 : 32'sd0);
    if (d < 32'sd0) d = 32'sd0;
    if (d > 32'sd31) d = 32'sd31;
    return d[7:0];
  endfunction

  // fp32 2^d (d <= 31): a normal power of two.
  function automatic logic [31:0] pow2d(input logic [31:0] d);
    return 32'h3F80_0000 + (d << 23);
  endfunction

  // the scaled value of the current element: ftz -> *rscale -> *cscale (isasim's order)
  function automatic logic [31:0] scale_x(input logic [31:0] raw);
    logic [31:0] x;
    x = ftz(raw);
    // CSCALE/RSCALE are QACT-only flags: QST's F_HALF (0x2) shares the F_CSCALE bit
    if (!cfg_qst && (cfg_fl & F_RSCALE)) x = fp_mul(x, rfac);
    if (!cfg_qst && (cfg_fl & F_CSCALE)) x = fp_mul(x, tmem_rdata1);
    return x;
  endfunction

  // ================================================================== bounds checks
  // Computed combinationally before the first read; mirror the oracle's order and ranges.
  logic [63:0] tmax, dmax, smax;
  logic        chk_err;
  logic [2:0]  chk_code;
  logic [31:0] c_n_elem, c_ne, c_slen, c_gsize, c_ngroups;

  always @* begin
    // config-derived sizes, usable before the Q_CHK latches have settled
    c_n_elem   = cfg_kb * D;
    c_ne       = (cfg_fl & F_HALF) ? (cfg_kb * D) / 2 : cfg_kb * D;
    c_slen     = (cfg_fl & F_ROW) ? 32'd4 : 32'd4 + 4 * ((cfg_kb + 32'd3) / 32'd4);
    c_gsize    = cfg_qst ? D : D / NSUB;
    c_ngroups  = cfg_qst ? cfg_kb : cfg_kb * NSUB;
    chk_err  = 1'b0;
    chk_code = ERR_NONE;
    tmax     = 64'd0;
    dmax     = 64'd0;
    smax     = 64'd0;
    if (cfg_qst) begin
      if (half && !row_mode) begin
        chk_err = 1'b1; chk_code = ERR_QST;      // HALF needs ROW mode
      end else begin
        // source rows: src + (rows-1)*srs + n_elem-1 < TMEM_WORDS
        tmax = {32'd0, cfg_src} + ({32'd0, cfg_rows} - 64'd1) * {32'd0, cfg_srs}
               + {32'd0, c_n_elem} - 64'd1;
        if (tmax >= TMEM_WORDS) begin
          chk_err = 1'b1; chk_code = ERR_ACT;     // TMEM range violation
        end else begin
          // data bytes: dst + (rows-1)*drs + (ne-1)*es < DRAM_BYTES
          dmax = {32'd0, cfg_dst} + ({32'd0, cfg_rows} - 64'd1) * {32'd0, cfg_drs}
                 + ({32'd0, c_ne} - 64'd1) * {32'd0, cfg_es};
          // scale row: 4-byte aligned and sdst + rows*slen - 1 < DRAM_BYTES
          smax = {32'd0, cfg_sdst} + {32'd0, cfg_rows} * {32'd0, c_slen} - 64'd1;
          if (dmax >= DRAM_BYTES) begin
            chk_err = 1'b1; chk_code = ERR_QST;
          end else if (cfg_sdst[1:0] != 2'd0 || smax >= DRAM_BYTES) begin
            chk_err = 1'b1; chk_code = ERR_QST;
          end
        end
      end
    end else begin
      // ACT bounds (DUP uses two row sets, both inside MCOLS)
      if (((cfg_fl & F_DUP) ? (2 * cfg_rows > MCOLS) : (cfg_rows > ACT_ROWS)) ||
          cfg_ab + cfg_kb > ACT_BLOCKS) begin
        chk_err = 1'b1; chk_code = ERR_ACT;
      end else begin
        tmax = {32'd0, cfg_src} + ({32'd0, cfg_rows} - 64'd1) * {32'd0, cfg_srs}
               + {32'd0, c_n_elem} - 64'd1;
        if (tmax >= TMEM_WORDS) begin
          chk_err = 1'b1; chk_code = ERR_ACT;
        end else if ((cfg_fl & F_CSCALE) &&
                     ({32'd0, cfg_cscale} + {32'd0, c_n_elem} - 64'd1) >= TMEM_WORDS) begin
          chk_err = 1'b1; chk_code = ERR_ACT;
        end else if ((cfg_fl & F_RSCALE) &&
                     ({32'd0, cfg_rscale} + {32'd0, cfg_rows} - 64'd1) >= TMEM_WORDS) begin
          chk_err = 1'b1; chk_code = ERR_ACT;
        end
      end
    end
  end

  // ================================================================== FSM
  typedef enum logic [3:0] {
    Q_IDLE      = 4'd0,
    Q_CHK       = 4'd1,
    Q_ROW_BEGIN = 4'd2,
    Q_AN_READ   = 4'd3,
    Q_AN_FIN    = 4'd4,
    Q_AN_GROUP  = 4'd5,
    Q_EMIT_READ = 4'd6,
    Q_EMIT_SCAL = 4'd7,
    Q_OVERLAP   = 4'd8,
    Q_ROW_NEXT  = 4'd9,
    Q_DONE      = 4'd10,
    Q_ERROR     = 4'd11
  } qstate_t;
  qstate_t qs;

  // overlap check state (QST): element index co and scale row rs, one address per cycle
  logic [31:0] co, rs;
  logic        dupph;
  logic        ovl_hit;
  logic [31:0] ovl_addr, ovl_base;

  // ---- the current element's TMEM address and scaled abs bits (for the unsigned amax)
  logic [31:0] ax_scaled, ax_abs;
  always @* begin
    taddr     = cfg_src + r * cfg_srs + c;
    ax_scaled = scale_x(tmem_rdata0);
    ax_abs    = {1'b0, ax_scaled[30:0]};       // fabs: the sign bit cleared
  end

  // ---- overlap: any data byte address equals any scale-row byte address
  always @* begin
    ovl_hit  = 1'b0;
    ovl_addr = cfg_dst + r * cfg_drs + co * cfg_es;
    ovl_base = cfg_sdst + rs * slen;
    if (ovl_addr >= ovl_base && ovl_addr < ovl_base + slen) begin
      ovl_hit = 1'b1;
    end
  end

  assign busy = (qs != Q_IDLE);

  // ---- defaults for the write ports (overridden by the active state)
  always @* begin
    act_we   = 1'b0; act_row = 32'd0; act_lin = 32'd0; act_data  = 8'd0;
    act_we2  = 1'b0; act_row2 = 32'd0; act_lin2 = 32'd0; act_data2 = 8'd0;
    s_we     = 1'b0; s_row = 32'd0; s_block = 32'd0; s_data = 32'd0;
    d_we     = 1'b0; d_row = 32'd0; d_block = 32'd0; d_data = 32'd0;
    dram_we    = 1'b0; dram_waddr = 32'd0; dram_wdata = 8'd0;
    tmem_raddr0 = 32'd0;
    tmem_raddr1 = 32'd0;
    q_byte = 8'd0;
    case (qs)
      Q_ROW_BEGIN: begin
        if (!cfg_qst && (cfg_fl & F_RSCALE)) tmem_raddr0 = cfg_rscale + r;
      end
      Q_AN_READ: begin
        tmem_raddr0 = taddr;
        if (!cfg_qst && (cfg_fl & F_CSCALE)) tmem_raddr1 = cfg_cscale + c;
      end
      Q_EMIT_READ: begin
        tmem_raddr0 = taddr;
        if (!cfg_qst && (cfg_fl & F_CSCALE)) tmem_raddr1 = cfg_cscale + c;
        q_byte = q8(fp_mul(scale_x(tmem_rdata0), invg[(cfg_qst ? (c / D) : (c / gsize))]));
        if (cfg_qst) begin
          if (c < ne) begin
            dram_we    = 1'b1;
            dram_waddr = cfg_dst + r * cfg_drs + c * cfg_es;
            dram_wdata = q_byte;
          end
        end else begin
          act_we    = 1'b1;
          act_row   = r;
          act_lin   = cfg_ab * D + c;
          act_data  = q_byte;
          if (cfg_fl & F_DUP) begin
            act_we2   = 1'b1;
            act_row2  = r + cfg_rows;
            act_lin2  = cfg_ab * D + c;
            act_data2 = q_byte;
          end
        end
      end
      Q_EMIT_SCAL: begin
        if (cfg_qst) begin
          dram_we    = 1'b1;
          dram_waddr = cfg_sdst + r * slen + k;
          if (k < 4) begin
            dram_wdata = s_val[8*k +: 8];
          end else if (k < 4 + cfg_kb) begin
            dram_wdata = dbyte[k - 4];
          end else begin
            dram_wdata = 8'd0;
          end
        end else begin
          s_we    = 1'b1;
          s_row   = dupph ? (r + cfg_rows) : r;
          s_block = cfg_ab + b;
          s_data  = s_val;
          d_we    = 1'b1;
          d_row   = dupph ? (r + cfg_rows) : r;
          d_block = cfg_ab + b;
          d_data  = {dval[b*NSUB+3][7:0], dval[b*NSUB+2][7:0],
                     dval[b*NSUB+1][7:0], dval[b*NSUB+0][7:0]};
        end
      end
      default: begin
      end
    endcase
  end

  // ================================================================== sequencer
  integer j;
  always_ff @(posedge clk) begin
    if (rst) begin
      qs <= Q_IDLE;
      done <= 1'b0;
      err  <= 1'b0;
      err_code <= ERR_NONE;
      cfg_qst <= 1'b0;
      r <= 32'd0; c <= 32'd0; g <= 32'd0; b <= 32'd0; k <= 32'd0;
      co <= 32'd0; rs <= 32'd0; dupph <= 1'b0;
      amax <= 32'd0; s_val <= 32'd0; inv_val <= 32'd0; rfac <= 32'd0;
      row_mode <= 32'd0; dup <= 32'd0; half <= 32'd0;
      n_elem <= 32'd0; gsize <= 32'd0; ngroups <= 32'd0; ne <= 32'd0; slen <= 32'd0;
      for (j = 0; j < MAXG; j = j + 1) begin
        gmax[j] <= 32'd0;
        dval[j] <= 32'd0;
        invg[j] <= 32'd0;
      end
      for (j = 0; j < ACT_BLOCKS; j = j + 1) begin
        dbyte[j] <= 32'd0;
      end
    end else begin
      done <= 1'b0;
      case (qs)
        Q_IDLE: begin
          if (start) begin
            cfg_qst    <= is_qst;
            cfg_src    <= src;    cfg_rows <= rows;  cfg_kb  <= kb;   cfg_srs <= srs;
            cfg_ab     <= ab;     cfg_cscale <= cscale; cfg_rscale <= rscale;
            cfg_dst    <= dst;    cfg_sdst <= sdst;  cfg_drs <= drs;  cfg_es  <= es;
            cfg_fl     <= flags;
            qs         <= Q_CHK;
          end
        end

        Q_CHK: begin
          n_elem  <= c_n_elem;
          gsize   <= c_gsize;
          ngroups <= c_ngroups;
          ne      <= c_ne;
          slen    <= c_slen;
          row_mode <= (cfg_fl & F_ROW) ? 32'd1 : 32'd0;
          dup      <= (cfg_fl & F_DUP) ? 32'd1 : 32'd0;
          half     <= (cfg_fl & F_HALF) ? 32'd1 : 32'd0;
          r  <= 32'd0;
          c  <= 32'd0;
          b  <= 32'd0;
          dupph <= 1'b0;
          k  <= 32'd0;
          co <= 32'd0;
          rs <= 32'd0;
          if (chk_err) begin
            err      <= 1'b1;
            err_code <= chk_code;
            qs       <= Q_ERROR;
          end else if (cfg_qst) begin
            qs <= Q_OVERLAP;
          end else begin
            qs <= Q_ROW_BEGIN;
          end
        end

        // ---- per row: latch the RSCALE factor, reset the row's running maxima
        Q_ROW_BEGIN: begin
          rfac <= (!cfg_qst && (cfg_fl & F_RSCALE)) ? tmem_rdata0 : F_ONE;
          amax <= 32'd0;
          c    <= 32'd0;
          qs   <= Q_AN_READ;
        end

        // ---- pass 1: read x, scale it, track amax and the group maxima
        Q_AN_READ: begin
          if (c >= n_elem) begin
            qs <= Q_AN_FIN;
          end else begin
            // amax / group max: unsigned compare of the fabs bit patterns (NaN above +inf)
            if ((c % gsize) == 32'd0) begin
              gmax[c / gsize] <= ax_abs;
            end else if (ax_abs > gmax[c / gsize]) begin
              gmax[c / gsize] <= ax_abs;
            end
            if (ax_abs > amax) begin
              amax <= ax_abs;
            end
            c <= c + 32'd1;
          end
        end

        // ---- row S/inv, then the per-group offsets and invg (one group per cycle)
        Q_AN_FIN: begin
          if (amax == 32'd0) begin
            s_val   <= 32'd0;
            inv_val <= 32'd0;
          end else begin
            s_val   <= fp_mul(amax, F_INV127);
            inv_val <= fp_mul(F_127, fp_recip(amax));
          end
          g  <= 32'd0;
          c  <= 32'd0;
          qs <= Q_AN_GROUP;
        end

        Q_AN_GROUP: begin
          if (g >= ngroups) begin
            c  <= 32'd0;
            qs <= Q_EMIT_READ;
          end else begin
            if (row_mode || gmax[g] == 32'd0) begin
              dval[g] <= 32'd0;
              invg[g] <= fp_mul(inv_val, F_ONE);
            end else begin
              dval[g] <= {24'd0, d_offset(gmax[g], amax)};
              invg[g] <= fp_mul(inv_val, pow2d({24'd0, d_offset(gmax[g], amax)}));
            end
            if (cfg_qst) begin
              dbyte[g] <= (row_mode || gmax[g] == 32'd0)
                          ? 32'd0 : {24'd0, d_offset(gmax[g], amax)};
            end
            g <= g + 32'd1;
          end
        end

        // ---- pass 2: re-read x, q = q8(x * invg), write ACT bytes / DRAM bytes
        Q_EMIT_READ: begin
          if (c >= n_elem) begin
            c  <= 32'd0;
            b  <= 32'd0;
            k  <= 32'd0;
            qs <= Q_EMIT_SCAL;
          end else begin
            c <= c + 32'd1;
          end
        end

        // ---- the scale record: ACT (Sa + packed da) or the DRAM scale row (S + offset bytes)
        Q_EMIT_SCAL: begin
          if (cfg_qst) begin
            if (k + 32'd1 >= slen) begin
              qs <= Q_ROW_NEXT;
            end else begin
              k <= k + 32'd1;
            end
          end else begin
            if (b + 32'd1 >= cfg_kb) begin
              if (dup && !dupph) begin
                // second copy of the scale record at row + rows (QACT DUP)
                dupph <= 1'b1;
                b     <= 32'd0;
              end else begin
                dupph <= 1'b0;
                qs    <= Q_ROW_NEXT;
              end
            end else begin
              b <= b + 32'd1;
            end
          end
        end

        // ---- QST scale/data overlap: at least one byte address must not coincide
        Q_OVERLAP: begin
          if (ovl_hit) begin
            err      <= 1'b1;
            err_code <= ERR_QST;
            qs       <= Q_ERROR;
          end else if (rs + 32'd1 >= cfg_rows) begin
            if (co + 32'd1 >= ne) begin
              qs <= Q_ROW_BEGIN;
            end else begin
              co <= co + 32'd1;
              rs <= 32'd0;
            end
          end else begin
            rs <= rs + 32'd1;
          end
        end

        Q_ROW_NEXT: begin
          if (r + 32'd1 >= cfg_rows) begin
            qs <= Q_DONE;
          end else begin
            r  <= r + 32'd1;
            qs <= Q_ROW_BEGIN;
          end
        end

        Q_DONE: begin
          done <= 1'b1;
          qs   <= Q_IDLE;
        end

        Q_ERROR: begin
          err <= 1'b1;
        end

        default: begin
          err      <= 1'b1;
          err_code <= ERR_ILLEGAL;
          qs       <= Q_ERROR;
        end
      endcase
    end
  end

endmodule
