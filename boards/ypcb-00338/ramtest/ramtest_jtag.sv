// SPDX-License-Identifier: Apache-2.0
// RAM-only register service; same USER2 framing as the existing XVC transport.
module ramtest_jtag #(
  parameter [31:0] BUILD_ID = 32'hc0161001,
  parameter integer DDR_MTS = 800, CHANNEL_MASK = 3, PATTERN = 2
) (
  input wire clk, rst,
  input wire [2047:0] snapshot0, snapshot1,
  input wire [1:0] snapshot_ack,
  output reg [1:0] snapshot_request=0,
  output wire [2:0] led
);
  wire tck, capture, shift, update, sel, tdi, tdo;
  BSCANE2 #(.JTAG_CHAIN(2)) u_bscan(
    .TCK(tck), .CAPTURE(capture), .SHIFT(shift), .UPDATE(update), .SEL(sel),
    .TDI(tdi), .TDO(tdo), .DRCK(), .RESET(), .RUNTEST());
  wire valid;
  wire [603:0] request;
  reg response_valid=0;
  reg [511:0] response_data=0;
  reg [7:0] response_status=0;
  reg [15:0] response_sequence=0;
  otpu_jtag_mailbox u_mailbox(
    .clk(clk), .rst(rst), .tck(tck), .capture(capture), .shift(shift),
    .update(update), .sel(sel), .tdi(tdi), .tdo(tdo), .req_valid(valid),
    .req_ready(!response_valid), .req(request), .rsp_valid(response_valid),
    .rsp_data(response_data), .rsp_status(response_status), .rsp_seq(response_sequence));
  (* ASYNC_REG = "TRUE" *) reg [1:0] ack_s1=0, ack_s2=0, ack_s3=0;
  reg [31:0] ticks=0;
  wire [1:0] busy = snapshot_request ^ ack_s3;
  wire [31:0] address = request[543:512];
  wire [7:0] opcode = request[555:548];
  assign led = {busy != 0, ticks[24], !rst};
  always @(posedge clk) begin
    ticks <= ticks+1'b1;
    ack_s1<=snapshot_ack; ack_s2<=ack_s1; ack_s3<=ack_s2;
    response_valid <= 0;
    if (valid && !response_valid) begin
      response_valid<=1;
      response_data<=0;
      response_status<=0;
      response_sequence<=request[571:556];
      if (opcode == 1 && address[1:0] == 0) begin
        case (address)
          0: response_data[31:0]<=32'h52414d54; // RAMT, distinct from OTPU
          4: response_data[31:0]<=1; // register ABI
          8: response_data[31:0]<=BUILD_ID;
          12: response_data[31:0]<=DDR_MTS;
          16: response_data[31:0]<=CHANNEL_MASK;
          20: response_data[31:0]<=PATTERN;
          24: response_data[31:0]<={30'b0,busy};
          28: response_data[31:0]<=ticks;
          default: begin
            if (address >= 'h100 && address < 'h200 && !busy[0])
              response_data[31:0]<=snapshot0[address[7:2]*32+:32];
            else if (address >= 'h200 && address < 'h300 && !busy[1])
              response_data[31:0]<=snapshot1[address[7:2]*32+:32];
            else response_status<=1;
          end
        endcase
      end else if (opcode == 2 && address == 'h24 && request[547:544] == 15) begin
        if ((busy & request[1:0]) != 0) response_status<=2;
        else snapshot_request<=snapshot_request ^ request[1:0];
      end else response_status<=1;
    end
  end
endmodule
