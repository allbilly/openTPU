// SPDX-License-Identifier: Apache-2.0
// Passive first-mismatch capture for the 512-bit native ECC read port.
// Each accepted read command produces one in-order 64-byte payload. The vendor
// expected-data output is delayed by two clocks; delay address/data identically.
// This records data AFTER ECC. A corrected error may leave no payload mismatch.
module ramtest_read_capture #(
  parameter integer QUEUE_BITS = 10
) (
  input wire clk, rst,
  input wire command_valid, command_ready,
  input wire [2:0] command,
  input wire [28:0] address,
  input wire read_valid,
  input wire [511:0] read_data, expected_data,
  output wire [1087:0] record
);
  localparam integer DEPTH = 1 << QUEUE_BITS;
  reg [28:0] addresses [0:DEPTH-1];
  reg [QUEUE_BITS-1:0] head=0, tail=0;
  reg [QUEUE_BITS:0] count=0;
  reg overflow=0, underflow=0;
  wire push = command_valid && command_ready && command == 1;
  wire pop = read_valid;
  wire push_ok = push && (count < DEPTH || pop);
  wire pop_ok = pop && (count != 0 || push);
  reg [1:0] valid_pipe=0, address_valid_pipe=0;
  reg [511:0] data0=0, data1=0;
  reg [28:0] address0=0, address1=0;
  reg captured=0, captured_address_valid=0;
  reg [28:0] first_address=0;
  reg [511:0] first_expected=0, first_actual=0;
  wire [31:0] flags = {28'b0, underflow, overflow, captured_address_valid, captured};
  assign record = {first_actual, first_expected, flags, 3'b0, first_address};

  always @(posedge clk) begin
    if (rst) begin
      head<=0; tail<=0; count<=0; overflow<=0; underflow<=0;
      valid_pipe<=0; address_valid_pipe<=0;
      captured<=0; captured_address_valid<=0;
      first_address<=0; first_expected<=0; first_actual<=0;
    end else begin
      if (push && !push_ok) overflow<=1;
      if (pop && !pop_ok) underflow<=1;
      if (push_ok) begin addresses[head]<=address; head<=head+1'b1; end
      if (pop_ok) tail<=tail+1'b1;
      case ({push_ok,pop_ok})
        2'b10: count<=count+1'b1;
        2'b01: count<=count-1'b1;
        default: count<=count;
      endcase
      valid_pipe <= {valid_pipe[0], read_valid};
      address_valid_pipe <= {address_valid_pipe[0], pop_ok && !overflow && !underflow};
      data0<=read_data; data1<=data0;
      if (pop_ok) address0 <= count == 0 ? address : addresses[tail];
      address1<=address0;
      if (!captured && valid_pipe[1] && (data1 != expected_data)) begin
        captured<=1;
        captured_address_valid<=address_valid_pipe[1] && !overflow && !underflow;
        first_address<=address1;
        first_expected<=expected_data;
        first_actual<=data1;
      end
    end
  end
endmodule
