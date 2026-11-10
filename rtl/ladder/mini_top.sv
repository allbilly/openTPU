// Ladder step 4 — mini-core v0: an openTPU-ISA sequencer with registers, TMEM, DRAM and
// LD/ST, written for the ladder (docs/mini-core.md).
//
// It is deliberately serial: fetch the eight words of an instruction, execute it to
// completion, advance.  There is no overlap, no scoreboard and no AXI: the *state* it leaves
// (TMEM, DRAM, registers, pc) is exactly the ISA simulator's (opentpu/isasim.py), which is what
// the step-4 tests compare bit for bit.  Steps 5-8 add the VPU, quantizer, MXU and reductions to
// this core; step 9 adopts the production RTL and retires it.
//
// Instruction subset (docs/isa.md): NOP, HALT (CHAIN -> error), LI, ADDI, LOOP, BAR (S=1 no-op),
// RLD, LD/ST, (step 5) the elementwise VOPs in all four B-operand modes, (step 6) QACT/QST and
// (step 7) the int8 MM with its scales and fp32 epilogue.  Everything else latches
// ERR_ILLEGAL.  Error codes are in mini_pkg (4 bits from step 7: codes 8/9).  The arithmetic
// units reuse the product tree's otpu_fp package, so the state they leave is bit-identical to
// isasim's.
`timescale 1ns/1ps
module mini_top #(
  parameter int D          = 32,      // MXU depth == quantization block (kept for the config)
  parameter int MCOLS      = 4,       // MXU columns == max stationary rows (config, unused here)
  parameter int ACT_BLOCKS = 16,      // ACT RAM depth (config, unused until step 6)
  parameter int ACT_ROWS   = 4,       // ACT RAM rows (config, unused until step 6)
  parameter int TMEM_WORDS = 4096,    // TMEM depth in 32-bit words
  parameter int IMEM_WORDS = 4096,    // instruction memory in 32-bit words (8 per instruction)
  parameter int DRAM_BYTES = 262144   // DRAM size in bytes
) (
  input  logic        clk,
  input  logic        rst,            // synchronous, active high
  input  logic [31:0] rinit [8],      // R8..R15 start with the run's arguments
  output logic        all_halted,
  output logic        any_error,
  output logic [31:0] error_code,
  output logic [31:0] icount          // instructions retired (errors counted, like isasim)
);

  import mini_pkg::*;

  localparam int INSTR_WORDS = IMEM_WORDS / 8;   // instructions IMEM can hold

  // ------------------------------------------------------------------ memories
  logic [31:0] imem [0:IMEM_WORDS-1];
  logic [31:0] R    [0:15];

  // one instruction: 8 words, loaded serially by the fetch state
  logic [31:0] iw [0:7];

  // ------------------------------------------------------------------ machine state
  logic [31:0] pc;            // instruction index
  logic [2:0]  fidx;          // fetch word counter 0..7

  logic        halted;
  logic        err;
  logic [3:0]  ecode;
  logic [31:0] icnt;

  integer k;               // reset-loop variable (in the sequencer below)

  // LOOP stack: start pc, body-end pc (inclusive), remaining count
  logic [31:0] lstart [0:LOOP_DEPTH-1];
  logic [31:0] lend   [0:LOOP_DEPTH-1];
  logic [31:0] lcount [0:LOOP_DEPTH-1];
  logic [2:0]  ldepth;

  // LD/ST multi-cycle engine: one word per cycle once started
  logic        ldst_ld;
  logic [31:0] ldst_d;        // DRAM byte address of word 0
  logic [31:0] ldst_t;        // TMEM word index of word 0
  logic [31:0] ldst_n;        // words
  logic [31:0] ldst_i;        // current word

  // ------------------------------------------------------------------ decode
  logic [7:0]  op;
  logic [3:0]  ra, rb, rc, rd;
  logic [7:0]  fl;
  logic [31:0] w1, w2, w3, w4, w5, w6, w7;   // payload words w1..w7

  assign op = iw[0][7:0];
  assign ra = iw[0][11:8];
  assign rb = iw[0][15:12];
  assign rc = iw[0][19:16];
  assign rd = iw[0][23:20];
  assign fl = iw[0][31:24];
  assign w1 = iw[1];
  assign w2 = iw[2];
  assign w3 = iw[3];
  assign w4 = iw[4];
  assign w5 = iw[5];
  assign w6 = iw[6];
  assign w7 = iw[7];

  // R0 reads as 0; writes to R0 are dropped
  function automatic logic [31:0] rget(input logic [3:0] r);
    rget = (r == 4'd0) ? 32'd0 : R[r];
  endfunction

  // ------------------------------------------------------------------ FSM
  typedef enum logic [3:0] {
    ST_FETCH  = 4'd0,
    ST_EXEC   = 4'd1,
    ST_LDST   = 4'd2,
    ST_ADV    = 4'd3,
    ST_HALTED = 4'd4,
    ST_ERROR  = 4'd5,
    ST_VOP    = 4'd6,
    ST_QUANT  = 4'd7,
    ST_MM     = 4'd8
  } state_t;
  state_t st;

  // ------------------------------------------------------------------ memory ports
  logic [31:0] dram_raddr, dram_rdata, dram_waddr, dram_wdata;
  logic        dram_we;
  logic [31:0] tmem_raddr0, tmem_rdata0, tmem_raddr1, tmem_rdata1, tmem_waddr, tmem_wdata;
  logic        tmem_we;
  logic [31:0] vpu_raddr0, vpu_raddr1, vpu_waddr, vpu_wdata;
  logic        vpu_we, vpu_busy, vpu_done, vpu_err;
  logic [2:0]  vpu_err_code;

  // QACT/QST quantizer + ACT RAM (step 6)
  logic        q_start, q_is_qst, q_busy, q_done, q_err;
  logic [2:0]  q_err_code;
  logic [31:0] q_src, q_rows, q_kb, q_srs, q_ab, q_cscale, q_rscale;
  logic [31:0] q_dst, q_sdst, q_drs, q_es;
  logic [31:0] q_raddr0, q_raddr1, q_rdata0, q_rdata1;
  logic        q_act_we, q_act_we2, q_s_we, q_d_we, q_dram_we;
  logic [31:0] q_act_row, q_act_lin, q_act_row2, q_act_lin2;
  logic [7:0]  q_act_data, q_act_data2;
  logic [31:0] q_s_row, q_s_block, q_s_data, q_d_row, q_d_block, q_d_data;
  logic [31:0] q_dram_waddr;
  logic [7:0]  q_dram_wdata;
  logic [31:0] act_rrow, act_rlin, act_rrow_s, act_rblock_s, act_rrow_d, act_rblock_d;
  logic [7:0]  act_rdata;
  logic [31:0] act_rdata_s, act_rdata_d;
  logic [31:0] act_rrow_w, act_rword, act_rdata_w;
  logic [31:0] act_rrow_rec, act_rblock_rec;
  logic [63:0] act_rdata_rec;

  // MM / MXU (step 7)
  logic        m_start, m_busy, m_done, m_err;
  logic [3:0]  m_err_code;
  logic [31:0] m_sa, m_ssa, m_out, m_rs, m_srs;
  logic [15:0] m_n, m_ors;
  logic [7:0]  m_kb, m_k0, m_m, m_ab;
  logic [31:0] m_dram_raddr, m_tmem_raddr, m_tmem_waddr, m_tmem_wdata;
  logic        m_tmem_we;
  logic [31:0] m_act_row, m_act_word, m_rec_row, m_rec_block;

  // the ACT RAM's MXU read ports: the quantizer's byte/single-record ports stay idle
  assign act_rrow = 32'd0; assign act_rlin = 32'd0;
  assign act_rrow_s = 32'd0; assign act_rblock_s = 32'd0;
  assign act_rrow_d = 32'd0; assign act_rblock_d = 32'd0;
  assign act_rrow_w = (st == ST_MM) ? m_act_row : 32'd0;
  assign act_rword  = (st == ST_MM) ? m_act_word : 32'd0;
  assign act_rrow_rec   = (st == ST_MM) ? m_rec_row : 32'd0;
  assign act_rblock_rec = (st == ST_MM) ? m_rec_block : 32'd0;

  // ST reads TMEM (port 0) and LD writes it; RLD reads TMEM while it executes; the VPU owns
  // both read ports and the write port while it runs; the quantizer owns both read ports
  // (port 0 row data, port 1 the CSCALE factors) while QACT/QST run.
  assign tmem_raddr0 = (st == ST_VOP) ? vpu_raddr0
                     : (st == ST_MM) ? m_tmem_raddr
                     : (st == ST_QUANT) ? q_raddr0
                     : ((st == ST_LDST) && !ldst_ld) ? (ldst_t + ldst_i)
                     : (rget(ra) + w1);
  assign tmem_raddr1 = (st == ST_VOP) ? vpu_raddr1
                     : (st == ST_QUANT) ? q_raddr1 : 32'd0;
  assign dram_raddr = (st == ST_MM) ? m_dram_raddr
                    : ((st == ST_LDST) && ldst_ld) ? (ldst_d + (ldst_i << 2)) : 32'd0;
  assign dram_waddr = ldst_d + (ldst_i << 2);
  assign dram_wdata = tmem_rdata0;
  assign dram_we    = (st == ST_LDST) && !ldst_ld && (ldst_i < ldst_n);
  assign tmem_waddr = (st == ST_VOP) ? vpu_waddr
                    : (st == ST_MM) ? m_tmem_waddr : (ldst_t + ldst_i);
  assign tmem_wdata = (st == ST_VOP) ? vpu_wdata
                    : (st == ST_MM) ? m_tmem_wdata : dram_rdata;
  assign tmem_we    = (st == ST_VOP) ? vpu_we
                    : (st == ST_MM) ? m_tmem_we
                    : (st == ST_LDST) && ldst_ld && (ldst_i < ldst_n);

  // ------------------------------------------------------------------ operand math
  // Python (isasim) computes reg+imm in 32 bits (wrap), then indexes in 64 bits for the range
  // checks; mirror that so "huge" addresses are rejected instead of wrapping into range.
  logic [31:0] e_d32, e_t32, e_n;
  logic [63:0] e_dend, e_tend;

  always @* begin
    e_d32  = rget(ra) + w1;
    e_t32  = rget(rb) + w2;
    e_n    = w3;
    e_dend = {32'd0, e_d32} + ({32'd0, e_n} << 2);   // d + 4n: one past the last word
    e_tend = {32'd0, e_t32} + {32'd0, e_n};          // t + n
  end

  // RLD's value, before the optional MUL: the word's bits (RAW) or f2i(bits)
  logic [31:0] rld_base, rld_val, rld_idx;
  always @* begin
    rld_base = (fl & F_RAW) ? tmem_rdata0 : f2i(tmem_rdata0);
    rld_val  = (fl & F_MUL) ? (rld_base * (rget(rb) + w2))
                            : rld_base;
    rld_idx  = rget(ra) + w1;                        // 32-bit wrap, like isasim
  end

  // a LOOP whose body ends on the same instruction as an enclosing body would skip that
  // body's back edge: an error (docs/isa.md; isasim: "...end on the same instruction")
  logic end_clash;
  integer kc;              // separate loop variable: `k` belongs to the sequencer's reset loops
  always @* begin
    end_clash = 1'b0;
    for (kc = 0; kc < LOOP_DEPTH; kc = kc + 1) begin
      if ((kc < ldepth) && (lend[kc] == (pc + w1))) begin
        end_clash = 1'b1;
      end
    end
  end

  // ------------------------------------------------------------------ submodules
  mini_dram #(.DRAM_BYTES(DRAM_BYTES)) dram (
    .clk(clk), .raddr(dram_raddr), .rdata(dram_rdata),
    .waddr(dram_waddr), .wdata(dram_wdata), .we(dram_we),
    .bwaddr(q_dram_waddr), .bwdata(q_dram_wdata),
    .bwe((st == ST_QUANT) && q_dram_we)
  );

  mini_actram #(.D(D), .ACT_BLOCKS(ACT_BLOCKS), .ACT_ROWS(ACT_ROWS)) actram (
    .clk(clk),
    .we(st == ST_QUANT ? q_act_we : 1'b0), .wrow(q_act_row), .wlin(q_act_lin),
    .wdata(q_act_data),
    .we2(st == ST_QUANT ? q_act_we2 : 1'b0), .wrow2(q_act_row2), .wlin2(q_act_lin2),
    .wdata2(q_act_data2),
    .swe(st == ST_QUANT ? q_s_we : 1'b0), .srow(q_s_row), .sblock(q_s_block),
    .sdata(q_s_data),
    .dwe(st == ST_QUANT ? q_d_we : 1'b0), .drow(q_d_row), .dblock(q_d_block),
    .ddata(q_d_data),
    .rrow(act_rrow), .rlin(act_rlin), .rdata(act_rdata),
    .rrow_s(act_rrow_s), .rblock_s(act_rblock_s), .rdata_s(act_rdata_s),
    .rrow_d(act_rrow_d), .rblock_d(act_rblock_d), .rdata_d(act_rdata_d),
    .rrow_w(act_rrow_w), .rword(act_rword), .rdata_w(act_rdata_w),
    .rrow_rec(act_rrow_rec), .rblock_rec(act_rblock_rec), .rdata_rec(act_rdata_rec)
  );

  // the quantizer's operand and flag fields come straight from the instruction words (the
  // operands are register-relative, resolved like isa.py's qact()/qst() encoders)
  assign q_src    = rget(ra) + w1;
  assign q_rows   = (op == OP_QACT) ? {24'd0, w2[7:0]}   : {16'd0, w4[15:0]};
  assign q_kb     = (op == OP_QACT) ? (w2 >> 16)         : (w4 >> 16);
  assign q_ab     = (op == OP_QACT) ? {24'd0, w2[15:8]}   : 32'd0;
  assign q_srs    = (op == OP_QACT) ? w3                 : w5;
  assign q_cscale = (fl & F_CSCALE) ? w4 : 32'd0;
  assign q_rscale = (fl & F_RSCALE) ? w5 : 32'd0;
  assign q_dst    = rget(rb) + w2;
  assign q_sdst   = rget(rc) + w3;
  assign q_drs    = w6;
  assign q_es     = w7;
  assign q_is_qst = (op == OP_QST);
  assign q_start  = (st == ST_EXEC) && ((op == OP_QACT) || (op == OP_QST));

  mini_quant #(
    .D(D), .MCOLS(MCOLS), .ACT_BLOCKS(ACT_BLOCKS), .ACT_ROWS(ACT_ROWS),
    .TMEM_WORDS(TMEM_WORDS), .DRAM_BYTES(DRAM_BYTES)
  ) quant (
    .clk(clk), .rst(rst), .start(q_start), .is_qst(q_is_qst),
    .src(q_src), .rows(q_rows), .kb(q_kb), .srs(q_srs), .ab(q_ab),
    .cscale(q_cscale), .rscale(q_rscale),
    .dst(q_dst), .sdst(q_sdst), .drs(q_drs), .es(q_es), .flags(fl),
    .tmem_raddr0(q_raddr0), .tmem_raddr1(q_raddr1),
    .tmem_rdata0(q_rdata0), .tmem_rdata1(q_rdata1),
    .act_we(q_act_we), .act_row(q_act_row), .act_lin(q_act_lin), .act_data(q_act_data),
    .act_we2(q_act_we2), .act_row2(q_act_row2), .act_lin2(q_act_lin2),
    .act_data2(q_act_data2),
    .s_we(q_s_we), .s_row(q_s_row), .s_block(q_s_block), .s_data(q_s_data),
    .d_we(q_d_we), .d_row(q_d_row), .d_block(q_d_block), .d_data(q_d_data),
    .dram_we(q_dram_we), .dram_waddr(q_dram_waddr), .dram_wdata(q_dram_wdata),
    .busy(q_busy), .done(q_done), .err(q_err), .err_code(q_err_code)
  );

  // the quantizer reads TMEM through the core's two read ports
  assign q_rdata0 = tmem_rdata0;
  assign q_rdata1 = tmem_rdata1;

  mini_tmem #(.TMEM_WORDS(TMEM_WORDS)) tmem (
    .clk(clk), .raddr0(tmem_raddr0), .rdata0(tmem_rdata0),
    .raddr1(tmem_raddr1), .rdata1(tmem_rdata1),
    .waddr(tmem_waddr), .wdata(tmem_wdata), .we(tmem_we)
  );

  // ------------------------------------------------------------------ VOP operands
  // The register-relative fields, resolved exactly like isa.py's vop() encoder and isasim's
  // _vop: dst/a/b are R[x] + w, the shape and strides are immediates, the immediate word is
  // w7 = R[rd] + w6 (the last payload word, register-relative).
  logic [31:0] v_dst, v_a, v_b, v_imm;
  logic [15:0] v_rows, v_cols, v_drs, v_ars, v_brs;
  logic [7:0]  v_func;
  logic [1:0]  v_bmode;

  always @* begin
    v_dst   = rget(ra) + w1;
    v_a     = rget(rb) + w2;
    v_b     = rget(rc) + w3;
    v_rows  = w4[15:0];
    v_cols  = w4[31:16];
    v_drs   = w5[15:0];
    v_ars   = w5[31:16];
    v_brs   = w6[15:0];
    v_func  = w6[23:16];
    v_bmode = w6[25:24];
    v_imm   = rget(rd) + w7;
  end

  // A VOP whose shape is zero or whose function is not elementwise (the reductions, ARGMAX,
  // OUTER: step 8) is an illegal instruction for this rung.  isa.vop() refuses a zero shape
  // too, so no compiled program can reach it.
  logic vop_ok;
  assign vop_ok = (w4[15:0] != 16'd0) && (w4[31:16] != 16'd0) && is_elementwise(w6[23:16]);
  assign vpu_start = (st == ST_EXEC) && (op == OP_VOP) && vop_ok;

  mini_vpu #(.TMEM_WORDS(TMEM_WORDS)) vpu (
    .clk(clk), .rst(rst), .start(vpu_start),
    .func(v_func), .dst(v_dst), .a(v_a), .b(v_b),
    .rows(v_rows), .cols(v_cols), .drs(v_drs), .ars(v_ars), .brs(v_brs),
    .bmode(v_bmode), .flags(fl), .imm(v_imm),
    .busy(vpu_busy), .done(vpu_done), .err(vpu_err), .err_code(vpu_err_code),
    .raddr0(vpu_raddr0), .rdata0(tmem_rdata0),
    .raddr1(vpu_raddr1), .rdata1(tmem_rdata1),
    .we(vpu_we), .waddr(vpu_waddr), .wdata(vpu_wdata)
  );

  // ------------------------------------------------------------------ MM operands (step 7)
  // The register-relative fields exactly as isa.mm() encodes and isasim._mm decodes them:
  // sa/ssa/out are R[ra/rb/rc] + w1..w3, the rest are payload immediates.
  assign m_sa  = rget(ra) + w1;
  assign m_ssa = rget(rb) + w2;
  assign m_out = rget(rc) + w3;
  assign m_n   = w4[15:0];
  assign m_kb  = w4[23:16];
  assign m_k0  = w4[31:24];
  assign m_rs  = w5;
  assign m_ors = w6[15:0];
  assign m_m   = w6[23:16];
  assign m_ab  = w6[31:24];
  assign m_srs = w7;
  assign m_start = (st == ST_EXEC) && (op == OP_MM);

  mini_mxu #(
    .D(D), .MCOLS(MCOLS), .ACT_BLOCKS(ACT_BLOCKS), .ACT_ROWS(ACT_ROWS),
    .TMEM_WORDS(TMEM_WORDS), .DRAM_BYTES(DRAM_BYTES)
  ) mxu (
    .clk(clk), .rst(rst), .start(m_start),
    .sa(m_sa), .ssa(m_ssa), .out(m_out), .rs(m_rs), .srs(m_srs),
    .n(m_n), .ors(m_ors), .kb(m_kb), .k0(m_k0), .m(m_m), .ab(m_ab), .flags(fl),
    .busy(m_busy), .done(m_done), .err(m_err), .err_code(m_err_code),
    .dram_raddr(m_dram_raddr), .dram_rdata(dram_rdata),
    .act_row(m_act_row), .act_word(m_act_word), .act_rdata(act_rdata_w),
    .rec_row(m_rec_row), .rec_block(m_rec_block), .rec_rdata(act_rdata_rec),
    .tmem_raddr(m_tmem_raddr), .tmem_rdata(tmem_rdata0),
    .tmem_waddr(m_tmem_waddr), .tmem_wdata(m_tmem_wdata), .tmem_we(m_tmem_we)
  );

  // ------------------------------------------------------------------ sequencer
  always_ff @(posedge clk) begin
    if (rst) begin
      pc        <= 32'd0;
      fidx      <= 3'd0;
      st        <= ST_FETCH;
      halted    <= 1'b0;
      err       <= 1'b0;
      ecode     <= ERR_NONE;
      icnt      <= 32'd0;
      ldepth    <= 3'd0;
      ldst_ld   <= 1'b0;
      ldst_d    <= 32'd0;
      ldst_t    <= 32'd0;
      ldst_n    <= 32'd0;
      ldst_i    <= 32'd0;
      for (k = 0; k < 16; k = k + 1) begin
        R[k] <= 32'd0;
      end
      for (k = 0; k < 8; k = k + 1) begin
        R[8+k] <= rinit[k];
      end
      for (k = 0; k < LOOP_DEPTH; k = k + 1) begin
        lstart[k] <= 32'd0;
        lend[k]   <= 32'd0;
        lcount[k] <= 32'd0;
        iw[k]     <= 32'd0;
      end
      iw[4] <= 32'd0;
      iw[5] <= 32'd0;
      iw[6] <= 32'd0;
      iw[7] <= 32'd0;
    end else begin
      case (st)
        // ---- fetch one of the instruction's eight words per cycle
        ST_FETCH: begin
          if (pc >= INSTR_WORDS) begin
            // ran past the program image (the board's loader cannot place it there)
            err   <= 1'b1;
            ecode <= ERR_ILLEGAL;
            st    <= ST_ERROR;
          end else begin
            iw[fidx] <= imem[(pc << 3) + {29'd0, fidx}];
            if (fidx == 3'd7) begin
              fidx <= 3'd0;
              st   <= ST_EXEC;
            end else begin
              fidx <= fidx + 3'd1;
            end
          end
        end

        // ---- decode and execute to completion (except the serial LD/ST engine)
        ST_EXEC: begin
          icnt <= icnt + 32'd1;      // isasim counts the instruction before it can raise
          case (op)
            OP_NOP: begin
              st <= ST_ADV;
            end

            OP_HALT: begin
              if (fl & F_CHAIN) begin
                // HALT CHAIN restarts from a DRAM image; not in the mini-core
                err   <= 1'b1;
                ecode <= ERR_ILLEGAL;
                st    <= ST_ERROR;
              end else begin
                halted <= 1'b1;
                st     <= ST_HALTED;
              end
            end

            OP_LI: begin
              if (rd != 4'd0) begin
                R[rd] <= w1;
              end
              st <= ST_ADV;
            end

            OP_ADDI: begin
              if (rd != 4'd0) begin
                R[rd] <= rget(ra) + w1;
              end
              st <= ST_ADV;
            end

            OP_LOOP: begin
              // checks in isasim's order: empty body, enclosing-body end clash, count 0 (which
              // skips before the depth check), then the stack overflow
              if (w1 == 32'd0) begin
                err   <= 1'b1;
                ecode <= ERR_LOOP;
                st    <= ST_ERROR;
              end else if (end_clash) begin
                err   <= 1'b1;
                ecode <= ERR_LOOP;
                st    <= ST_ERROR;
              end else if ((rget(ra) + w2) == 32'd0) begin
                pc <= pc + 32'd1 + w1;
                st <= ST_FETCH;
              end else if (ldepth >= LOOP_DEPTH) begin
                err   <= 1'b1;
                ecode <= ERR_LOOP;
                st    <= ST_ERROR;
              end else begin
                lstart[ldepth] <= pc + 32'd1;
                lend[ldepth]   <= pc + w1;
                lcount[ldepth] <= rget(ra) + w2;
                ldepth         <= ldepth + 3'd1;
                pc             <= pc + 32'd1;
                st             <= ST_FETCH;
              end
            end

            OP_BAR: begin
              // S=1: the collective has every slice already, so it completes immediately
              st <= ST_ADV;
            end

            OP_RLD: begin
              if (rld_idx >= TMEM_WORDS) begin
                err   <= 1'b1;
                ecode <= ERR_TMEM;
                st    <= ST_ERROR;
              end else begin
                // BOUND is the simulator's/waits pass's check; the hardware ignores it
                if (rd != 4'd0) begin
                  R[rd] <= rld_val;
                end
                st <= ST_ADV;
              end
            end

            OP_VOP: begin
              if (!vop_ok) begin
                err   <= 1'b1;
                ecode <= ERR_ILLEGAL;
                st    <= ST_ERROR;
              end else begin
                // vpu_start was high this cycle: the VPU latched the operands
                st <= ST_VOP;
              end
            end

            OP_LD, OP_ST: begin
              if (e_n == 32'd0) begin
                // zero words: isasim's range checks pass vacuously
                st <= ST_ADV;
              end else if (e_d32[1:0] != 2'd0 || (e_dend > DRAM_BYTES)) begin
                err   <= 1'b1;
                ecode <= ERR_DRAM;
                st    <= ST_ERROR;
              end else if (e_tend > TMEM_WORDS) begin
                err   <= 1'b1;
                ecode <= ERR_TMEM;
                st    <= ST_ERROR;
              end else begin
                ldst_ld <= (op == OP_LD);
                ldst_d  <= e_d32;
                ldst_t  <= e_t32;
                ldst_n  <= e_n;
                ldst_i  <= 32'd0;
                st      <= ST_LDST;
              end
            end

            OP_MM: begin
              // m_start was high this cycle: the MXU latched the operands; it does its own
              // bounds checks (codes 8/9) and the ACT Sa consistency walk before any write
              st <= ST_MM;
            end

            OP_QACT, OP_QST: begin
              // q_start was high this cycle: the quantizer latched the operands; it does its
              // own bounds checks and reports ERR_ACT/ERR_QST
              st <= ST_QUANT;
            end

            default: begin
              // WAITW, DSTEP, STREAM, GATHER: later rungs
              err   <= 1'b1;
              ecode <= ERR_ILLEGAL;
              st    <= ST_ERROR;
            end
          endcase
        end

        // ---- VOP: the VPU runs one element per cycle; wait for its done or its error
        ST_VOP: begin
          if (vpu_err) begin
            err   <= 1'b1;
            ecode <= vpu_err_code;
            st    <= ST_ERROR;
          end else if (vpu_done) begin
            st <= ST_ADV;
          end
        end

        // ---- QACT/QST: the quantizer runs to completion (serialized, one element a cycle)
        ST_QUANT: begin
          if (q_err) begin
            err   <= 1'b1;
            ecode <= q_err_code;
            st    <= ST_ERROR;
          end else if (q_done) begin
            st <= ST_ADV;
          end
        end

        // ---- MM: the MXU runs one element per cycle; wait for its done or its error
        ST_MM: begin
          if (m_err) begin
            err   <= 1'b1;
            ecode <= m_err_code;
            st    <= ST_ERROR;
          end else if (m_done) begin
            st <= ST_ADV;
          end
        end

        // ---- LD/ST: one 32-bit word per cycle (DRAM read combinational, write synchronous)
        ST_LDST: begin
          if (ldst_i >= ldst_n) begin
            st <= ST_ADV;
          end else begin
            ldst_i <= ldst_i + 32'd1;
            if ((ldst_i + 32'd1) == ldst_n) begin
              st <= ST_ADV;
            end
          end
        end

        // ---- advance: pc+1, or the innermost loop's back edge / exit (isasim's advance())
        ST_ADV: begin
          if ((ldepth != 3'd0) && (lend[ldepth - 3'd1] == pc)) begin
            if (lcount[ldepth - 3'd1] > 32'd1) begin
              lcount[ldepth - 3'd1] <= lcount[ldepth - 3'd1] - 32'd1;
              pc <= lstart[ldepth - 3'd1];
            end else begin
              ldepth <= ldepth - 3'd1;
              pc     <= pc + 32'd1;
            end
          end else begin
            pc <= pc + 32'd1;
          end
          st <= ST_FETCH;
        end

        ST_HALTED: begin
          halted <= 1'b1;
        end

        ST_ERROR: begin
          err <= 1'b1;
        end

        default: begin
          err   <= 1'b1;
          ecode <= ERR_ILLEGAL;
          st    <= ST_ERROR;
        end
      endcase
    end
  end

  // ------------------------------------------------------------------ status
  assign all_halted = halted;
  assign any_error  = err;
  assign error_code = {28'd0, ecode};
  assign icount     = icnt;

endmodule
