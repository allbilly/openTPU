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
// RLD and LD/ST.  Everything else latches ERR_ILLEGAL.  Error codes are in mini_pkg.
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
  logic [2:0]  ecode;
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
  logic [31:0] w1, w2, w3;    // payload words 1..3 (w4..w7 unused in this subset)

  assign op = iw[0][7:0];
  assign ra = iw[0][11:8];
  assign rb = iw[0][15:12];
  assign rc = iw[0][19:16];
  assign rd = iw[0][23:20];
  assign fl = iw[0][31:24];
  assign w1 = iw[1];
  assign w2 = iw[2];
  assign w3 = iw[3];

  // R0 reads as 0; writes to R0 are dropped
  function automatic logic [31:0] rget(input logic [3:0] r);
    rget = (r == 4'd0) ? 32'd0 : R[r];
  endfunction

  // ------------------------------------------------------------------ FSM
  typedef enum logic [2:0] {
    ST_FETCH  = 3'd0,
    ST_EXEC   = 3'd1,
    ST_LDST   = 3'd2,
    ST_ADV    = 3'd3,
    ST_HALTED = 3'd4,
    ST_ERROR  = 3'd5
  } state_t;
  state_t st;

  // ------------------------------------------------------------------ memory ports
  logic [31:0] dram_raddr, dram_rdata, dram_waddr, dram_wdata;
  logic        dram_we;
  logic [31:0] tmem_raddr, tmem_rdata, tmem_waddr, tmem_wdata;
  logic        tmem_we;

  // ST reads TMEM; LD writes TMEM.  RLD reads TMEM while it executes.
  assign tmem_raddr = ((st == ST_LDST) && !ldst_ld) ? (ldst_t + ldst_i)
                                                   : (rget(ra) + w1);
  assign dram_raddr = ((st == ST_LDST) && ldst_ld) ? (ldst_d + (ldst_i << 2)) : 32'd0;
  assign dram_waddr = ldst_d + (ldst_i << 2);
  assign dram_wdata = tmem_rdata;
  assign dram_we    = (st == ST_LDST) && !ldst_ld && (ldst_i < ldst_n);
  assign tmem_waddr = ldst_t + ldst_i;
  assign tmem_wdata = dram_rdata;
  assign tmem_we    = (st == ST_LDST) && ldst_ld && (ldst_i < ldst_n);

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
    rld_base = (fl & F_RAW) ? tmem_rdata : f2i(tmem_rdata);
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
    .waddr(dram_waddr), .wdata(dram_wdata), .we(dram_we)
  );

  mini_tmem #(.TMEM_WORDS(TMEM_WORDS)) tmem (
    .clk(clk), .raddr(tmem_raddr), .rdata(tmem_rdata),
    .waddr(tmem_waddr), .wdata(tmem_wdata), .we(tmem_we)
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

            default: begin
              // VOP, MM, QACT, QST, WAITW, DSTEP, STREAM, GATHER: later rungs
              err   <= 1'b1;
              ecode <= ERR_ILLEGAL;
              st    <= ST_ERROR;
            end
          endcase
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
  assign error_code = {29'd0, ecode};
  assign icount     = icnt;

endmodule
