// SPDX-License-Identifier: Apache-2.0
// RAM-only LiteDRAM diagnostic control and calibration CSR access over USER2.
// LDRT is deliberately distinct from RAMT: ECC counters are read from the
// LiteDRAM CSRs, not the MIG observer's unused ECC pulse fields.
module ramtest_litedram_status #(
  parameter [31:0] BUILD_ID = 32'hc0162010,
  parameter integer DDR_MTS = 800
) (
  input wire clk, rst,
  input wire [1087:0] first_read0, first_read1,
  input wire [2047:0] snapshot0, snapshot1,
  input wire [1:0] snapshot_ack, calibrated,
  input wire [1:0] native_busy, protocol_error,
  output reg [1:0] snapshot_request = 0,
  output reg [1:0] traffic_reset = 3, traffic_pause = 3,
  output reg [3:0] pattern_mode = 2,
  output reg [3:0] instruction_mode = 1,
  output reg [31:0] fixed_data = 0,
  output wire [2:0] led,
  output reg [15:0] ctl_awaddr = 0, ctl_araddr = 0,
  output reg [31:0] ctl_wdata = 0,
  output reg [3:0] ctl_wstrb = 0,
  output reg ctl_awvalid = 0, ctl_wvalid = 0, ctl_bready = 0,
  output reg ctl_arvalid = 0, ctl_rready = 0,
  input wire ctl_awready, ctl_wready, ctl_bvalid, ctl_arready, ctl_rvalid,
  input wire [1:0] ctl_bresp, ctl_rresp,
  input wire [31:0] ctl_rdata
);
  wire tck, capture, shift, update, sel, tdi, tdo;
  BSCANE2 #(.JTAG_CHAIN(2)) u_bscan(
    .TCK(tck), .CAPTURE(capture), .SHIFT(shift), .UPDATE(update), .SEL(sel),
    .TDI(tdi), .TDO(tdo), .DRCK(), .RESET(), .RUNTEST());
  wire valid, ready;
  wire [603:0] request;
  reg response_valid = 0, csr_busy = 0;
  reg [511:0] response_data = 0;
  reg [7:0] response_status = 0;
  reg [15:0] response_sequence = 0;
  assign ready = !response_valid && !csr_busy;
  otpu_jtag_mailbox u_mailbox(
    .clk(clk), .rst(rst), .tck(tck), .capture(capture), .shift(shift),
    .update(update), .sel(sel), .tdi(tdi), .tdo(tdo), .req_valid(valid),
    .req_ready(ready), .req(request), .rsp_valid(response_valid),
    .rsp_data(response_data), .rsp_status(response_status), .rsp_seq(response_sequence));
  (* ASYNC_REG = "TRUE" *) reg [1:0] ack_s1 = 0, ack_s2 = 0, ack_s3 = 0;
  reg [31:0] ticks = 0;
  wire [1:0] busy = snapshot_request ^ ack_s3;
  wire [31:0] address = request[543:512];
  wire [7:0] opcode = request[555:548];
  assign led = {traffic_reset != 3, ticks[25], !rst};

  always @(posedge clk) begin
    ticks <= ticks + 1'b1;
    ack_s1 <= snapshot_ack; ack_s2 <= ack_s1; ack_s3 <= ack_s2;
    response_valid <= 0;
    if (rst) begin
      snapshot_request <= 0;
      traffic_reset <= 3; traffic_pause <= 3;
      pattern_mode <= 2; instruction_mode <= 1; fixed_data <= 0;
      csr_busy <= 0;
      ctl_awvalid <= 0; ctl_wvalid <= 0; ctl_bready <= 0;
      ctl_arvalid <= 0; ctl_rready <= 0;
      response_status <= 0; response_data <= 0; response_sequence <= 0;
    end else if (csr_busy) begin
      if (ctl_awvalid && ctl_awready) ctl_awvalid <= 0;
      if (ctl_wvalid && ctl_wready) ctl_wvalid <= 0;
      if (ctl_arvalid && ctl_arready) ctl_arvalid <= 0;
      if (ctl_bvalid && ctl_bready) begin
        ctl_bready <= 0; csr_busy <= 0;
        response_status <= {6'b0, ctl_bresp}; response_valid <= 1;
      end
      if (ctl_rvalid && ctl_rready) begin
        ctl_rready <= 0; csr_busy <= 0;
        response_data <= {480'b0, ctl_rdata};
        response_status <= {6'b0, ctl_rresp}; response_valid <= 1;
      end
    end else if (valid && ready) begin
      response_valid <= 1;
      response_data <= 0; response_status <= 0;
      response_sequence <= request[571:556];
      if (address[1:0] != 0) response_status <= 1;
      else if ((opcode == 1 || opcode == 2) && address[31:16] == 1) begin
        // This transport uses the same 0x10000 calibration window as OpenTPU.
        // The calibration CPU and the host arbitrate inside the generated core.
        csr_busy <= 1; response_valid <= 0;
        if (opcode == 1) begin
          ctl_araddr <= address[15:0]; ctl_arvalid <= 1; ctl_rready <= 1;
        end else begin
          ctl_awaddr <= address[15:0]; ctl_wdata <= request[31:0];
          ctl_wstrb <= request[547:544];
          ctl_awvalid <= 1; ctl_wvalid <= 1; ctl_bready <= 1;
        end
      end else if (opcode == 1) begin
        case (address)
          0: response_data[31:0] <= 32'h4c445254; // LDRT
          4: response_data[31:0] <= 3;
          8: response_data[31:0] <= BUILD_ID;
          12: response_data[31:0] <= DDR_MTS;
          16: response_data[31:0] <= 3;
          20: response_data[31:0] <= {28'b0, pattern_mode};
          24: response_data[31:0] <= {30'b0, busy};
          28: response_data[31:0] <= ticks;
          'h28: response_data[31:0] <= {30'b0, traffic_reset};
          'h2c: response_data[31:0] <= {30'b0, traffic_pause};
          'h30: response_data[31:0] <= {28'b0, pattern_mode};
          'h34: response_data[31:0] <= fixed_data;
          'h38: response_data[31:0] <= {30'b0, calibrated};
          'h3c: response_data[31:0] <= 100000; // Memory sys clock, kHz.
          'h48: response_data[31:0] <= 32'h52444331; // RDC1 capture layout
          'h40: response_data[31:0] <= {28'b0, instruction_mode};
          'h44: response_data[31:0] <= {14'b0, protocol_error, 14'b0, native_busy};
          default: begin
            if (address >= 'h100 && address < 'h200 && !busy[0])
              response_data[31:0] <= snapshot0[address[7:2]*32+:32];
            else if (address >= 'h200 && address < 'h300 && !busy[1])
              response_data[31:0] <= snapshot1[address[7:2]*32+:32];
            else if (address >= 'h400 && address < 'h488)
              response_data[31:0] <= first_read0[address[7:2]*32+:32];
            else if (address >= 'h500 && address < 'h588)
              response_data[31:0] <= first_read1[address[7:2]*32+:32];
            else response_status <= 1;
          end
        endcase
      end else if (opcode == 2 && request[547:544] == 15) begin
        case (address)
          'h24: begin
            if ((busy & request[1:0]) != 0) response_status <= 2;
            else snapshot_request <= snapshot_request ^ request[1:0];
          end
          'h28: begin
            // The host must pause and drain accepted reads/writes first.
            // Do not permit reset assertion against a running generator.
            if (((request[1:0] & ~traffic_reset) & ~traffic_pause) != 2'b0)
              response_status <= 2;
            else if (((request[1:0] & ~traffic_reset) & native_busy) != 2'b0)
              response_status <= 2;
            else if (((~request[1:0]) & ~calibrated) != 2'b0)
              response_status <= 3;
            else traffic_reset <= request[1:0];
          end
          'h2c: traffic_pause <= request[1:0];
          'h30: begin
            if (traffic_reset != 3) response_status <= 2;
            else if (request[31:0] == 1 || request[31:0] == 2 ||
                     request[31:0] == 5 || request[31:0] == 6 || request[31:0] == 7)
              pattern_mode <= request[3:0];
            else response_status <= 1;
          end
          'h34: begin
            if (traffic_reset != 3) response_status <= 2;
            else fixed_data <= request[31:0];
          end
          'h40: begin
            if (traffic_reset != 3) response_status <= 2;
            else if (request[31:0] == 1 || request[31:0] == 2)
              instruction_mode <= request[3:0];
            else response_status <= 1;
          end
          default: response_status <= 1;
        endcase
      end else response_status <= 1;
    end
  end
endmodule
