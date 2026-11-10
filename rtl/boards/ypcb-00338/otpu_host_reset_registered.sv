// SPDX-License-Identifier: Apache-2.0
// Register reset in the core domain before it crosses to the host domain.
// Keep the host usable when PCIe is absent; reset on either PCIe transition.
module otpu_host_reset_registered #(
  parameter int PULSE_CYCLES = 64
) (
  input logic clk,
  input logic cfg_rst,
  input logic host_locked,
  input logic pcie_resetn,
  output logic host_rst = 1'b1
);
  localparam int CW = $clog2(PULSE_CYCLES + 1);
  (* ASYNC_REG = "TRUE" *) logic [1:0] lock_sync = 0;
  (* ASYNC_REG = "TRUE" *) logic [1:0] pcie_sync = 0;
  logic pcie_seen = 0;
  logic [CW-1:0] remaining = CW'(PULSE_CYCLES);
  always_ff @(posedge clk) begin
    if (cfg_rst) begin
      lock_sync <= 0;
      pcie_sync <= 0;
      pcie_seen <= 0;
      remaining <= CW'(PULSE_CYCLES);
      host_rst <= 1'b1;
    end else begin
      lock_sync <= {lock_sync[0],host_locked};
      pcie_sync <= {pcie_sync[0],pcie_resetn};
      pcie_seen <= pcie_sync[1];
      if (!lock_sync[1] || pcie_seen != pcie_sync[1]) begin
        remaining <= CW'(PULSE_CYCLES);
        host_rst <= 1'b1;
      end else if (remaining != 0) begin
        remaining <= remaining - 1'b1;
        host_rst <= 1'b1;
      end else begin
        host_rst <= 1'b0;
      end
    end
  end
endmodule
