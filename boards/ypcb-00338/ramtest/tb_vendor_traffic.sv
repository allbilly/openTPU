// SPDX-License-Identifier: Apache-2.0
// Exercise the actual generated vendor traffic generator against a queued,
// independently stalled native-port memory model. This is not a DRAM PHY test.
`timescale 1ps/1ps
module tb_vendor_traffic;
  parameter integer MODE=2, FIXED_DATA=0, INJECT_ERROR=0, STALLS=1, COMMAND_BRIDGE=0, CAPTURE_READS=0;
  reg clk=0; always #5000 clk=~clk;
  reg rst=1, calibrated=0;
  wire en, wr_en, wr_end, cmp_valid, cmp_bad, error, initialized;
  wire [2:0] command;
  wire [31:0] address;
  wire [511:0] wr_data, cmp_data;
  wire [63:0] wr_mask;
  wire [1087:0] error_status;
  wire [7:0] lanes;
  wire [2:0] watchdog;
  reg [511:0] rd_data=0;
  reg rd_valid=0;
  reg [11:0] read_valid_pipe=0;
  reg [511:0] read_data_pipe[0:11];
  reg [31:0] random_bits=32'h1234abcd;
  reg [511:0] memory [0:2047];
  reg [31:0] cmd_addr [0:1023];
  reg [2:0] cmd_op [0:1023];
  reg [511:0] data_queue [0:1023];
  reg [63:0] mask_queue [0:1023];
  integer cmd_in=0, cmd_out=0, data_in=0, data_out=0;
  integer model_reads=0;
  reg [28:0] first_bad_address=0;
  reg [511:0] first_bad_expected=0;
  wire model_full = (STALLS && !random_bits[0]) || (cmd_in-cmd_out >= 512);
  wire cmd_full, model_accept;
  wire [31:0] model_address;
  wire [2:0] model_command;
  generate if (COMMAND_BRIDGE) begin : native_bridge
    wire app_ready, native_valid, native_write, busy, protocol_error;
    wire [24:0] native_address;
    wire native_ready = native_valid && !model_full;
    ramtest_litedram_command_bridge bridge(
      .clk(clk), .rst(rst), .app_valid(en), .app_ready(app_ready),
      .app_command(command), .app_address(address[28:0]),
      .native_valid(native_valid), .native_ready(native_ready),
      .native_write(native_write), .native_address(native_address),
      .busy(busy), .protocol_error(protocol_error));
    assign cmd_full = !app_ready;
    assign model_accept = native_valid && native_ready;
    assign model_address = {4'b0,native_address,3'b0};
    assign model_command = native_write ? 3'd0 : 3'd1;
    always @(posedge clk) if (!rst && protocol_error) $fatal(1,"Command bridge protocol error");
  end else begin : direct_port
    assign cmd_full = model_full;
    assign model_accept = en && !cmd_full;
    assign model_address = address;
    assign model_command = command;
  end endgenerate
  wire wr_full = (STALLS && !random_bits[3]) || (data_in-data_out >= 512);
  integer i, j, cycles=0;
  reg done=0;
  always @(posedge clk) begin
    random_bits <= {random_bits[30:0], random_bits[31]^random_bits[21]^random_bits[1]^random_bits[0]};
    // MIG's returned data arrives after the command/expected-pattern pipelines.
    // Keep a realistic fixed UI latency while allowing independent port stalls.
    rd_valid<=read_valid_pipe[11];
    rd_data<=read_data_pipe[11];
    read_valid_pipe[0]<=0;
    for(j=1;j<12;j=j+1) begin
      read_valid_pipe[j]<=read_valid_pipe[j-1];
      read_data_pipe[j]<=read_data_pipe[j-1];
    end
    if (!rst) begin
      if (model_accept) begin
        if(model_command == 1 && observer.reads < 32) begin
          $display("READ_TRACE n=%0d addr=%h expected=%h mode=%0d",observer.reads,address,observer.next_read,tg.tg_addr_mode);
          $fflush();
        end
        if (model_address[31:14] != 0 || model_address[2:0] != 0) $fatal(1,"unaligned/out-of-range command");
        cmd_addr[cmd_in%1024]<=model_address; cmd_op[cmd_in%1024]<=model_command; cmd_in<=cmd_in+1;
      end
      if (wr_en && !wr_full) begin
        if(data_in < 8) begin $display("WRITE_TRACE n=%0d data=%h",data_in,wr_data[63:0]);$fflush();end
        data_queue[data_in%1024]<=wr_data; mask_queue[data_in%1024]<=wr_mask; data_in<=data_in+1;
        if (!wr_end) $fatal(1,"BL8 write missing end");
      end
      if (cmd_out < cmd_in) begin
        if (cmd_op[cmd_out%1024] == 0 && data_out < data_in) begin
          for (i=0;i<64;i=i+1)
            if (!mask_queue[data_out%1024][i])
              memory[cmd_addr[cmd_out%1024]>>3][i*8+:8] <= data_queue[data_out%1024][i*8+:8];
          cmd_out<=cmd_out+1;data_out<=data_out+1;
        end else if (cmd_op[cmd_out%1024] == 1) begin
          read_valid_pipe[0]<=1;
          read_data_pipe[0]<=memory[cmd_addr[cmd_out%1024]>>3] ^ ((INJECT_ERROR && model_reads>=17) ? 512'h1000000000000 : 512'b0);
          if (INJECT_ERROR && model_reads==17) begin
            first_bad_address<=cmd_addr[cmd_out%1024];
            first_bad_expected<=memory[cmd_addr[cmd_out%1024]>>3];
          end
          model_reads<=model_reads+1;
          cmd_out<=cmd_out+1;
        end
      end
    end
  end
  mig_7series_v4_2_traffic_gen_top #(
    .TCQ(100),.SIMULATION("FALSE"),.FAMILY("VIRTEX7"),.MEM_TYPE("DDR3"),
    .TST_MEM_INSTR_MODE("FIXED_INSTR_R_MODE"),.nCK_PER_CLK(4),.NUM_DQ_PINS(64),
    .MEM_BURST_LEN(8),.MEM_COL_WIDTH(10),.DATA_WIDTH(512),.ADDR_WIDTH(28),.MASK_SIZE(8),
    .BEGIN_ADDRESS(0),.END_ADDRESS(32'h00003fff),.PRBS_EADDR_MASK_POS(32'hffffc000),
    .DATA_MODE(MODE),.DATA_PATTERN("DGEN_ALL"),.CMD_PATTERN("CGEN_SEQUENTIAL"),.PORT_MODE("BI_MODE")
  ) tg (
    .clk(clk),.rst(rst),.tg_only_rst(1'b0),.manual_clear_error(1'b0),.memc_init_done(calibrated),
    .memc_cmd_full(cmd_full),.memc_cmd_en(en),.memc_cmd_instr(command),.memc_cmd_addr(address),
    .memc_wr_en(wr_en),.memc_wr_end(wr_end),.memc_wr_mask(wr_mask),.memc_wr_data(wr_data),
    .memc_wr_full(wr_full),.memc_rd_data(rd_data),.memc_rd_empty(!rd_valid),
    .vio_pause_traffic(1'b0),.vio_modify_enable(COMMAND_BRIDGE != 0),.vio_data_mode_value(MODE[3:0]),
    .vio_addr_mode_value(3'b011),.vio_instr_mode_value(4'd1),.vio_bl_mode_value(COMMAND_BRIDGE ? 2'b01 : 2'b10),
    .vio_fixed_bl_value(COMMAND_BRIDGE ? 10'd64 : 10'd16),.vio_fixed_instr_value(3'b001),.vio_data_mask_gen(1'b0),
    .fixed_addr_i(32'b0),.fixed_data_i(FIXED_DATA),.simple_data0(32'b0),.simple_data1(32'b0),
    .simple_data2(32'b0),.simple_data3(32'b0),.simple_data4(32'b0),.simple_data5(32'b0),
    .simple_data6(32'b0),.simple_data7(32'b0),.wdt_en_i(1'b0),.bram_cmd_i(39'b0),.bram_valid_i(1'b0),
    .cmp_data(cmp_data),.cmp_data_valid(cmp_valid),.cmp_error(cmp_bad),.error(error),
    .error_status(error_status),.cumlative_dq_lane_error(lanes),
    .cmd_wdt_err_o(watchdog[0]),.wr_wdt_err_o(watchdog[1]),.rd_wdt_err_o(watchdog[2]),
    .mem_pattern_init_done(initialized));
  wire [2047:0] snapshot;
  reg request=0;
  wire ack;
  wire [1087:0] capture_record;
  generate if (CAPTURE_READS) begin : first_read_capture
    ramtest_read_capture capture(
      .clk(clk), .rst(rst), .command_valid(en), .command_ready(!cmd_full),
      .command(command), .address(address[28:0]), .read_valid(rd_valid),
      .read_data(rd_data), .expected_data(cmp_data), .record(capture_record));
  end else begin
    assign capture_record=0;
  end endgenerate
  ramtest_channel #(.LAST_ADDR(29'h3ff8),.PATTERN(MODE)) observer (
    .clk(clk),.ui_rst(rst),.calibrated(calibrated),.pattern_initialized(initialized),
    .compare_error(error),.watchdog_errors(watchdog),.command_valid(en),.command_ready(!cmd_full),
    .command(command),.address(address[28:0]),.read_valid(rd_valid),.compare_valid(cmp_valid),
    .compare_bad(cmp_bad),.ecc_single(8'b0),.ecc_multiple(8'b0),.error_status(error_status),
    .lane_errors(lanes),.snapshot_request(request),.snapshot_ack(ack),.snapshot(snapshot));
  initial begin : run_test
    repeat(20) @(negedge clk);rst=0;
    repeat(20) @(negedge clk);calibrated=1;
    while(cycles < 100000 && !done) begin
      @(negedge clk);cycles=cycles+1;
      if(cycles%5000 == 0) begin
        $display("TRAFFIC_PROGRESS cycles=%0d writes=%0d reads=%0d gaps=%0d/%0d commands=%0d returned=%0d compared=%0d",
          cycles,observer.write_passes,observer.read_passes,observer.write_gaps,observer.read_gaps,
          observer.reads,observer.returned,observer.compared);
        $fflush();
      end
      if(error || |watchdog) begin
        if(INJECT_ERROR && error) begin
          // The vendor summary record's data/address pipelines are not aligned
          // with its error pulse. Qualify the actual sticky byte-lane detector
          // and observer instead; preserve the summary record as unverified.
          repeat(8) @(negedge clk);
          if(lanes !== 8'h40 || observer.bad == 0)
            $fatal(1,"injected DQ48 corruption missing from sticky lane/cycle counts");
          request=1;wait(ack);#1;
          if(snapshot[1792+:32] !== 32'h40 || snapshot[256+:64] == 0)
            $fatal(1,"injected error missing from coherent snapshot");
          if(CAPTURE_READS) begin
            if(capture_record[63:32] !== 32'd3 ||
               capture_record[31:0] !== {3'b0,first_bad_address} ||
               capture_record[575:64] !== first_bad_expected ||
               capture_record[1087:576] !== (first_bad_expected ^ 512'h1000000000000))
              $fatal(1,"first read capture misaligned flags=%h addr=%h expected_addr=%h",capture_record[63:32],capture_record[31:0],first_bad_address);
            $display("PASS_FIRST_READ_CAPTURE_ALIGNED address=%h",first_bad_address);
          end
          $display("PASS_INJECTED_DATA_ERROR_DETECTED");done=1;
        end else $fatal(1,"vendor traffic compare/watchdog failure mode=%0d",MODE);
      end
      if(observer.write_passes>=1 && observer.read_passes>=2 && observer.compared>=4096) begin
        if(INJECT_ERROR) $fatal(1,"injected error missed");
        if(CAPTURE_READS && capture_record[63:32] !== 0) $fatal(1,"false first read capture or address queue error");
        request=1;wait(ack);#1;
        $display("PASS_VENDOR_TRAFFIC_STALLS_FULL_RANGE mode=%0d writes=%0d reads=%0d compared=%0d",MODE,
          snapshot[448+:32],snapshot[480+:32],snapshot[1920+:64]);done=1;
      end
    end
    if(!done) $fatal(1,"coverage timeout mode=%0d writes=%0d reads=%0d commands=%0d returns=%0d compared=%0d",
      MODE,observer.write_passes,observer.read_passes,observer.reads,observer.returned,observer.compared);
    $finish;
  end
endmodule
