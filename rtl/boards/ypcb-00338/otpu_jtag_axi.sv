// SPDX-License-Identifier: Apache-2.0
// One mailbox command -> one AXI-Lite access or a four-beat 128-bit AXI burst.
// Whole 64-byte writes avoid the physical ECC controller's sub-beat write path.
// AXI-Lite window 0 is the accelerator; window 1 is LiteDRAM's calibration CSR.
module otpu_jtag_axi (
  input logic clk, rst,
  input logic req_valid,
  output wire req_ready,
  input logic [603:0] req,
  output logic rsp_valid,
  output logic [511:0] rsp_data,
  output logic [7:0] rsp_status,
  output logic [15:0] rsp_seq,
  output logic [1:0][31:0] l_awaddr, l_araddr, l_wdata,
  output logic [1:0][3:0] l_wstrb,
  output logic [1:0] l_awvalid, l_wvalid, l_bready, l_arvalid, l_rready,
  input logic [1:0] l_awready, l_wready, l_bvalid, l_arready, l_rvalid,
  input logic [1:0][1:0] l_bresp, l_rresp,
  input logic [1:0][31:0] l_rdata,
  output wire [3:0] x_awid, x_arid,
  output logic [31:0] x_awaddr, x_araddr,
  output wire [7:0] x_awlen, x_arlen,
  output logic x_awvalid, x_arvalid, x_wvalid,
  output wire x_wlast,
  output logic x_bready, x_rready,
  output wire [127:0] x_wdata,
  output wire [15:0] x_wstrb,
  input logic x_awready, x_arready, x_wready, x_bvalid, x_rvalid, x_rlast,
  input logic [3:0] x_bid, x_rid,
  input logic [1:0] x_bresp, x_rresp,
  input logic [127:0] x_rdata
);
  typedef enum logic [2:0] {IDLE, LWRITE, LREAD, XWRITE, XREAD, DONE} state_t;
  state_t state;
  logic window;
  logic [1:0] beat;
  logic [511:0] data;
  assign req_ready = state == IDLE;
  assign x_awid = 0;
  assign x_arid = 0;
  assign x_awlen = 3;
  assign x_arlen = 3;
  assign x_wstrb = 16'hffff;
  assign x_wdata = data[128*beat +: 128];
  assign x_wlast = beat == 3;
  always_ff @(posedge clk) begin
    rsp_valid <= 0;
    if (rst) begin
      state <= IDLE;
      l_awvalid <= 0; l_wvalid <= 0; l_bready <= 0;
      l_arvalid <= 0; l_rready <= 0;
      x_awvalid <= 0; x_wvalid <= 0; x_bready <= 0;
      x_arvalid <= 0; x_rready <= 0;
      rsp_data <= 0; rsp_status <= 0; rsp_seq <= 0;
      data <= 0; beat <= 0; window <= 0;
      l_awaddr <= 0; l_araddr <= 0; l_wdata <= 0; l_wstrb <= 0;
      x_awaddr <= 0; x_araddr <= 0;
    end else case (state)
      IDLE: if (req_valid) begin
        rsp_seq <= req[571:556];
        rsp_data <= 0; rsp_status <= 0;
        data <= req[511:0];
        beat <= 0;
        window <= req[528]; // byte address bit 16
        case (req[555:548])
          1, 2: begin
            if (req[513:512] != 0) begin rsp_status <= 4; state <= DONE; end
            else if (!(req[543:512] < 32'h1000 || req[543:528] == 16'h0001))
              begin rsp_status <= 6; state <= DONE; end
            else if (req[555:548] == 1) begin
              l_araddr[req[528]] <= req[543:512];
              l_arvalid[req[528]] <= 1;
              l_rready[req[528]] <= 1;
              state <= LREAD;
            end else begin
              l_awaddr[req[528]] <= req[543:512];
              l_wdata[req[528]] <= req[31:0];
              l_wstrb[req[528]] <= req[547:544];
              l_awvalid[req[528]] <= 1;
              l_wvalid[req[528]] <= 1;
              l_bready[req[528]] <= 1;
              state <= LWRITE;
            end
          end
          3, 4: begin
            if (req[517:512] != 0) begin rsp_status <= 4; state <= DONE; end
            else if (req[555:548] == 3) begin
              x_araddr <= req[543:512];
              x_arvalid <= 1; x_rready <= 1; state <= XREAD;
            end else begin
              x_awaddr <= req[543:512];
              x_awvalid <= 1; x_wvalid <= 1; x_bready <= 1;
              state <= XWRITE;
            end
          end
          default: begin rsp_status <= 5; state <= DONE; end
        endcase
      end
      LWRITE: begin
        if (l_awvalid[window] && l_awready[window]) l_awvalid[window] <= 0;
        if (l_wvalid[window] && l_wready[window]) l_wvalid[window] <= 0;
        if (l_bvalid[window] && l_bready[window]) begin
          l_bready[window] <= 0;
          rsp_status <= {6'b0,l_bresp[window]}; state <= DONE;
        end
      end
      LREAD: begin
        if (l_arvalid[window] && l_arready[window]) l_arvalid[window] <= 0;
        if (l_rvalid[window] && l_rready[window]) begin
          l_rready[window] <= 0;
          rsp_data <= {480'b0,l_rdata[window]};
          rsp_status <= {6'b0,l_rresp[window]}; state <= DONE;
        end
      end
      XWRITE: begin
        if (x_awvalid && x_awready) x_awvalid <= 0;
        if (x_wvalid && x_wready) begin
          if (beat == 3) x_wvalid <= 0;
          else beat <= beat + 1;
        end
        if (x_bvalid && x_bready) begin
          x_bready <= 0;
          rsp_status <= x_bid == 0 ? {6'b0,x_bresp} : 8'd7;
          state <= DONE;
        end
      end
      XREAD: begin
        if (x_arvalid && x_arready) x_arvalid <= 0;
        if (x_rvalid && x_rready) begin
          rsp_data[128*beat +: 128] <= x_rdata;
          if (x_rresp != 0) rsp_status <= {6'b0,x_rresp};
          if (x_rid != 0 || x_rlast != (beat == 3)) rsp_status <= 7;
          if (x_rlast || beat == 3) begin x_rready <= 0; state <= DONE; end
          else beat <= beat + 1;
        end
      end
      DONE: begin rsp_valid <= 1; state <= IDLE; end
      default: state <= IDLE;
    endcase
  end
endmodule
