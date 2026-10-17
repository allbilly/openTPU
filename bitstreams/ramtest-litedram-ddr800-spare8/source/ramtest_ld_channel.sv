// SPDX-License-Identifier: Apache-2.0
// Observe the vendor MIG traffic generator. Never drive the memory interface.
module ramtest_ld_channel #(
  parameter integer ENABLED = 1,
  parameter integer PROGRESS_LIMIT = 65535,
  parameter [28:0] LAST_ADDR = 29'h0ffffff8
) (
  input wire [31:0] pattern,
  input wire paused, write_data_valid, write_data_ready,
  input wire clk, ui_rst, calibrated, pattern_initialized, compare_error,
  input wire [2:0] watchdog_errors,
  input wire command_valid, command_ready,
  input wire [2:0] command,
  input wire [28:0] address,
  input wire read_valid, compare_valid, compare_bad,
  input wire [7:0] ecc_single, ecc_multiple,
  input wire [1087:0] error_status,
  input wire [7:0] lane_errors,
  input wire snapshot_request,
  output reg snapshot_ack = 0,
  output reg [2047:0] snapshot = 0
);
  (* ASYNC_REG = "TRUE" *) reg [2:0] request_sync = 0;
  reg [63:0] writes=0, reads=0, returned=0, compared=0, bad=0, ce=0, ue=0;
  reg [31:0] write_passes=0, read_passes=0, write_gaps=0, read_gaps=0;
  reg [28:0] next_write=0, next_read=0;
  reg write_run=0, read_run=0;
  reg [28:0] min_write=29'h1fffffff, max_write=0;
  reg [28:0] min_read=29'h1fffffff, max_read=0;
  reg [63:0] written=0;
  reg [31:0] combined_passes=0, combined_gaps=0;
  reg [28:0] next_command=0;
  reg command_run=0;
  reg [63:0] ticks=0;
  reg [31:0] reset_edges=0;
  reg previous_reset=0;
  reg [15:0] command_idle=0, read_idle=0;
  reg [2:0] progress_errors=0;
  wire accepted = command_valid && command_ready;

  // Each accepted native command addresses one BL8 / 64-byte payload. Address
  // units are 8 payload bytes. Count only uninterrupted 0..LAST_ADDR sequences;
  // totals alone cannot prove that every address was visited.
  always @(posedge clk) begin
    request_sync <= {request_sync[1:0], snapshot_request};
    ticks <= ticks + 1'b1;
    previous_reset <= ui_rst;
    if (ui_rst && !previous_reset) reset_edges <= reset_edges + 1'b1;
    if (ui_rst) begin
      written<=0; combined_passes<=0; combined_gaps<=0; next_command<=0; command_run<=0;
      writes<=0; reads<=0; returned<=0; compared<=0; bad<=0; ce<=0; ue<=0;
      write_passes<=0; read_passes<=0; write_gaps<=0; read_gaps<=0;
      next_write<=0; next_read<=0; write_run<=0; read_run<=0;
      min_write<=29'h1fffffff; min_read<=29'h1fffffff; max_write<=0; max_read<=0;
      command_idle<=0; read_idle<=0; progress_errors<=0;
    end else begin
      // The vendor write watchdog assumes mixed R/W traffic. This diagnostic
      // fills once and then reads continuously, so monitor actual progress here.
      if (ENABLED && calibrated && !paused) begin
        if (accepted) command_idle<=0;
        else if (command_idle >= PROGRESS_LIMIT) progress_errors[0]<=1;
        else command_idle<=command_idle+1'b1;
        if (pattern_initialized) begin
          if (read_valid) read_idle<=0;
          else if (read_idle >= PROGRESS_LIMIT) progress_errors[2]<=1;
          else read_idle<=read_idle+1'b1;
        end
      end

      if (write_data_valid && write_data_ready) written <= written + 1'b1;
      // Mixed traffic uses a shared sequential command address stream. Count
      // complete combined traversals separately from pure read/write passes.
      if (accepted) begin
        if (address == 0) begin command_run<=1; next_command<=8; end
        else if (command_run && address == next_command) begin
          next_command <= address + 8;
          if (address == LAST_ADDR) begin combined_passes<=combined_passes+1'b1; command_run<=0; end
        end else begin command_run<=0; combined_gaps<=combined_gaps+1'b1; end
      end
      if (read_valid) begin
        returned <= returned + 1'b1;
        if (|ecc_single) ce <= ce + 1'b1;
        if (|ecc_multiple) ue <= ue + 1'b1;
      end
      if (compare_valid) compared <= compared + 1'b1;
      if (compare_bad) bad <= bad + 1'b1;
      if (accepted && command == 0) begin
        writes <= writes + 1'b1;
        if (address < min_write) min_write <= address;
        if (address > max_write) max_write <= address;
        if (address == 0) begin write_run<=1; next_write<=8; end
        else if (write_run && address == next_write) begin
          next_write <= address + 8;
          if (address == LAST_ADDR) begin write_passes<=write_passes+1'b1; write_run<=0; end
        end else begin write_run<=0; write_gaps<=write_gaps+1'b1; end
      end
      if (accepted && command == 1) begin
        reads <= reads + 1'b1;
        if (address < min_read) min_read <= address;
        if (address > max_read) max_read <= address;
        if (address == 0) begin read_run<=1; next_read<=8; end
        else if (read_run && address == next_read) begin
          next_read <= address + 8;
          if (address == LAST_ADDR) begin read_passes<=read_passes+1'b1; read_run<=0; end
        end else begin read_run<=0; read_gaps<=read_gaps+1'b1; end
      end
    end
    // Held payload and acknowledgment form a bundled-data CDC handshake. The
    // controller waits for three synchronized acknowledgment stages before read.
    if (request_sync[2] != snapshot_ack) begin
      snapshot <= 0;
      snapshot[0+:32] <= {24'b0, (ENABLED != 0), (watchdog_errors | progress_errors),
                          pattern_initialized, compare_error, ui_rst, calibrated};
      snapshot[32+:32] <= pattern;
      snapshot[64+:64] <= writes;
      snapshot[128+:64] <= reads;
      snapshot[192+:64] <= returned;
      snapshot[256+:64] <= bad;
      snapshot[320+:64] <= ce;
      snapshot[384+:64] <= ue;
      snapshot[448+:32] <= write_passes;
      snapshot[480+:32] <= read_passes;
      snapshot[512+:32] <= write_gaps;
      snapshot[544+:32] <= read_gaps;
      snapshot[576+:32] <= {3'b0,min_write};
      snapshot[608+:32] <= {3'b0,max_write};
      snapshot[640+:32] <= {3'b0,min_read};
      snapshot[672+:32] <= {3'b0,max_read};
      snapshot[704+:1088] <= error_status;
      // LDRT repurposes the unverified vendor address/status words.
      snapshot[704+:32] <= combined_passes;
      snapshot[736+:32] <= combined_gaps;
      snapshot[1792+:32] <= {24'b0,lane_errors};
      snapshot[1824+:64] <= ticks;
      snapshot[1888+:32] <= reset_edges;
      snapshot[1920+:64] <= compared;
      snapshot[1984+:64] <= written;
      snapshot_ack <= request_sync[2];
    end
  end
endmodule
