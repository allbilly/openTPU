// Ladder step 4 — mini-core testbench: load a program image + DRAM image, run, dump the
// memories, print one RESULT line.  This is the protocol every later rung reuses (step 3's
// golden ISA stack is driven by ladder/harness/mini.py).
//
// Plusargs:
//   +prog=<file>        IMEM image, 8 hex words per instruction, one word per line
//   +dram=<file>        DRAM image, 2 hex digits per byte, one byte per line (optional)
//   +outdir=<dir>       where tmem.hex / dram_out.hex are written
//   +max_cycles=<n>     give up after n cycles without halt/error (default 200000)
//   +arg0..+arg7=<hex>  the run's arguments, R8..R15
// Sizes are parameters, overridden by the harness with iverilog -P.
`timescale 1ns/1ps
module tb_mini #(
  parameter int D          = 32,
  parameter int MCOLS      = 4,
  parameter int ACT_BLOCKS = 16,
  parameter int ACT_ROWS   = 4,
  parameter int TMEM_WORDS = 4096,
  parameter int IMEM_WORDS = 4096,
  parameter int DRAM_BYTES = 262144
);

  logic        clk = 1'b0;
  logic        rst = 1'b1;
  logic [31:0] rinit [8];
  logic        all_halted;
  logic        any_error;
  logic [31:0] error_code;
  logic [31:0] icount;

  mini_top #(
    .D(D), .MCOLS(MCOLS), .ACT_BLOCKS(ACT_BLOCKS), .ACT_ROWS(ACT_ROWS),
    .TMEM_WORDS(TMEM_WORDS), .IMEM_WORDS(IMEM_WORDS), .DRAM_BYTES(DRAM_BYTES)
  ) dut (
    .clk(clk), .rst(rst), .rinit(rinit),
    .all_halted(all_halted), .any_error(any_error),
    .error_code(error_code), .icount(icount)
  );

  always #5 clk = ~clk;

  reg [1023:0] prog_path, dram_path, outdir_path;
  reg [31:0]   arg_val;
  integer      max_cycles, cycles, i, fd;
  integer      have_dram;

  initial begin
    max_cycles   = 200000;
    have_dram    = 1'b0;
    prog_path    = "prog.hex";
    dram_path    = "dram.hex";
    outdir_path  = ".";

    // R8..R15 default to 0; the harness writes full-size images (prog.hex padded with illegal
    // opcodes, dram.hex padded with zeros), so no hierarchical fill loops are needed here --
    // they are an order of magnitude slower than the run itself in Icarus.
    for (i = 0; i < 8; i = i + 1) begin
      rinit[i] = 32'd0;
    end

    if (!$value$plusargs("prog=%s", prog_path)) begin
      $display("ERROR: tb_mini needs +prog=<file>");
      $finish;
    end
    if ($value$plusargs("dram=%s", dram_path)) begin
      have_dram = 1'b1;
    end
    if ($value$plusargs("outdir=%s", outdir_path)) begin
      outdir_path = outdir_path;
    end
    if (!$value$plusargs("max_cycles=%d", max_cycles)) begin
      max_cycles = 200000;
    end

    if ($value$plusargs("arg0=%h", arg_val)) rinit[0] = arg_val;
    if ($value$plusargs("arg1=%h", arg_val)) rinit[1] = arg_val;
    if ($value$plusargs("arg2=%h", arg_val)) rinit[2] = arg_val;
    if ($value$plusargs("arg3=%h", arg_val)) rinit[3] = arg_val;
    if ($value$plusargs("arg4=%h", arg_val)) rinit[4] = arg_val;
    if ($value$plusargs("arg5=%h", arg_val)) rinit[5] = arg_val;
    if ($value$plusargs("arg6=%h", arg_val)) rinit[6] = arg_val;
    if ($value$plusargs("arg7=%h", arg_val)) rinit[7] = arg_val;

    $readmemh(prog_path, dut.imem);
    if (have_dram) begin
      $readmemh(dram_path, dut.dram.mem);
    end

    // reset: 3 cycles, then run until the machine halts, errors or the cycle budget runs out.
    // Sampling on the negedge keeps the TB off the DUT's posedge (race-free).
    repeat (3) @(negedge clk);
    rst = 1'b0;

    cycles = 0;
    while (!all_halted && !any_error && (cycles < max_cycles)) begin
      @(negedge clk);
      cycles = cycles + 1;
    end

    // memory dumps: tmem.hex is 8 hex digits per word, dram_out.hex 2 per byte, one per line
    fd = $fopen($sformatf("%0s/tmem.hex", outdir_path), "w");
    for (i = 0; i < TMEM_WORDS; i = i + 1) begin
      $fwrite(fd, "%08x\n", dut.tmem.mem[i]);
    end
    $fclose(fd);

    fd = $fopen($sformatf("%0s/dram_out.hex", outdir_path), "w");
    for (i = 0; i < DRAM_BYTES; i = i + 1) begin
      $fwrite(fd, "%02x\n", dut.dram.mem[i]);
    end
    $fclose(fd);

    // step 6: the ACT RAM state (int8 bytes, the fp32 scales, the packed uint8 offsets)
    fd = $fopen($sformatf("%0s/act.hex", outdir_path), "w");
    for (i = 0; i < ACT_ROWS * ACT_BLOCKS * D; i = i + 1) begin
      $fwrite(fd, "%02x\n", dut.actram.act[i]);
    end
    $fclose(fd);

    fd = $fopen($sformatf("%0s/ascale.hex", outdir_path), "w");
    for (i = 0; i < ACT_ROWS * ACT_BLOCKS; i = i + 1) begin
      $fwrite(fd, "%08x\n", dut.actram.ascale[i]);
    end
    $fclose(fd);

    fd = $fopen($sformatf("%0s/adoff.hex", outdir_path), "w");
    for (i = 0; i < ACT_ROWS * ACT_BLOCKS; i = i + 1) begin
      $fwrite(fd, "%08x\n", dut.actram.adoff[i]);
    end
    $fclose(fd);

    fd = $fopen($sformatf("%0s/result.txt", outdir_path), "w");
    $fclose(fd);

    $display("RESULT cycles=%0d halted=%0d error=%0d code=%0d icount=%0d",
             cycles, all_halted, any_error, error_code, icount);
    $finish;
  end

endmodule
