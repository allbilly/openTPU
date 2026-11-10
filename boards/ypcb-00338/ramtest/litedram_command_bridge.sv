// SPDX-License-Identifier: Apache-2.0
// Decouple the MIG example's full/en interface from LiteDRAM arbitration.
// LiteDRAM may assert ready only after valid; the example waits for !full.
module ramtest_litedram_command_bridge (
  input wire clk, rst,
  input wire app_valid,
  output wire app_ready,
  input wire [2:0] app_command,
  input wire [28:0] app_address,
  output wire native_valid,
  input wire native_ready,
  output wire native_write,
  output wire [24:0] native_address,
  output wire busy,
  output reg protocol_error = 0
);
  reg pending = 0;
  reg [2:0] command = 0;
  reg [28:0] address = 0;
  wire supported = command <= 1 && !address[28] && address[2:0] == 0;
  assign native_valid = pending && supported;
  assign app_ready = !pending || (native_valid && native_ready);
  assign native_write = !command[0];
  assign native_address = address[27:3];
  assign busy = pending;
  always @(posedge clk) begin
    if (rst) begin
      pending <= 0;
      protocol_error <= 0;
    end else begin
      if (native_valid && native_ready) pending <= 0;
      if (app_valid && app_ready) begin
        pending <= 1;
        command <= app_command;
        address <= app_address;
        if (app_command > 1 || app_address[28] || app_address[2:0] != 0)
          protocol_error <= 1;
      end
    end
  end
endmodule
