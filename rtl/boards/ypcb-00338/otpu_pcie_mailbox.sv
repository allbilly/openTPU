// SPDX-License-Identifier: Apache-2.0
// BAR0 AXI-Lite slave -> complete command port of otpu_jtag_axi.
// pclk and clk may be unrelated. Both resets must assert together;
// otpu_fpga_top_openxc7_pcie supplies a shared asynchronous reset source.
module otpu_pcie_mailbox (
  input logic pclk, prst, clk, rst,
  input logic [31:0] s_awaddr, s_wdata, s_araddr,
  input logic [3:0] s_wstrb,
  input logic s_awvalid, s_wvalid, s_bready, s_arvalid, s_rready,
  output wire s_awready, s_wready, s_arready,
  output logic s_bvalid, s_rvalid,
  output logic [1:0] s_bresp, s_rresp,
  output logic [31:0] s_rdata,
  output logic req_valid,
  input logic req_ready,
  output logic [603:0] req,
  input logic rsp_valid,
  input logic [511:0] rsp_data,
  input logic [7:0] rsp_status,
  input logic [15:0] rsp_seq
);
  logic awheld, wheld;
  logic [31:0] awaddr, wdata, address;
  logic [3:0] wstrb;
  logic [511:0] payload, result;
  logic [23:0] result_status;
  logic busy, done, rejected;
  logic [603:0] command_hold;
  logic request_toggle, response_toggle;
  logic [535:0] response_hold;
  (* ASYNC_REG = "TRUE" *) logic [1:0] request_sync, response_sync;
  logic request_seen, response_seen;

  assign s_awready = !prst && !awheld && !s_bvalid;
  assign s_wready = !prst && !wheld && !s_bvalid;
  assign s_arready = !prst && !s_rvalid;

  function automatic [31:0] merged(input [31:0] oldval, newval, input [3:0] lanes);
    for (integer i=0; i<4; i=i+1)
      merged[8*i+:8] = lanes[i] ? newval[8*i+:8] : oldval[8*i+:8];
  endfunction

  // The entire command_hold remains stable until the response is received.
  // Synchronize only its ownership toggle, then capture the stable bus.
  always_ff @(posedge clk or posedge rst) begin
    if (rst) begin
      request_sync <= 0; request_seen <= 0;
      req_valid <= 0; req <= 0;
      response_toggle <= 0; response_hold <= 0;
    end else begin
      request_sync <= {request_sync[0], request_toggle};
      if (req_valid && req_ready) req_valid <= 0;
      if (request_sync[1] != request_seen && !req_valid) begin
        req <= command_hold;
        req_valid <= 1;
        request_seen <= request_sync[1];
      end
      if (rsp_valid) begin
        response_hold <= {rsp_seq, rsp_status, rsp_data};
        response_toggle <= !response_toggle;
      end
    end
  end

  always_ff @(posedge pclk or posedge prst) begin
    if (prst) begin
      awheld <= 0; wheld <= 0; awaddr <= 0; wdata <= 0; wstrb <= 0;
      address <= 0; payload <= 0; result <= 0; result_status <= 0;
      busy <= 0; done <= 0; rejected <= 0;
      command_hold <= 0; request_toggle <= 0;
      response_sync <= 0; response_seen <= 0;
      s_bvalid <= 0; s_bresp <= 0;
      s_rvalid <= 0; s_rresp <= 0; s_rdata <= 0;
    end else begin
      response_sync <= {response_sync[0], response_toggle};
      if (response_sync[1] != response_seen) begin
        result <= response_hold[511:0];
        result_status <= response_hold[535:512];
        response_seen <= response_sync[1];
        busy <= 0; done <= 1;
      end
      if (s_bvalid && s_bready) s_bvalid <= 0;
      if (s_rvalid && s_rready) s_rvalid <= 0;
      if (s_awvalid && s_awready) begin awaddr <= s_awaddr; awheld <= 1; end
      if (s_wvalid && s_wready) begin wdata <= s_wdata; wstrb <= s_wstrb; wheld <= 1; end
      if (awheld && wheld && !s_bvalid) begin
        awheld <= 0; wheld <= 0; s_bvalid <= 1; s_bresp <= 0;
        // Decode the complete BAR offset. High address bits never alias.
        if (awaddr[1:0] != 0 || awaddr >= 4096) s_bresp <= 2;
        else if (busy) begin rejected <= 1; s_bresp <= 2; end
        else if (awaddr == 'h08) begin
          if (wstrb[0] && wdata[2]) rejected <= 0;
        end else if (awaddr == 'h10) address <= merged(address,wdata,wstrb);
        else if (awaddr >= 'h20 && awaddr < 'h60)
          payload[32*((awaddr-'h20)>>2)+:32] <=
            merged(payload[32*((awaddr-'h20)>>2)+:32],wdata,wstrb);
        else if (awaddr == 'h0c && wstrb == 4'hf) begin
          command_hold <= {32'h4f54504a,wdata[31:16],wdata[7:0],wdata[11:8],address,payload};
          request_toggle <= !request_toggle;
          busy <= 1; done <= 0;
        end else begin rejected <= 1; s_bresp <= 2; end
      end
      if (s_arvalid && s_arready) begin
        s_rvalid <= 1; s_rresp <= 0; s_rdata <= 0;
        if (s_araddr[1:0] != 0 || s_araddr >= 4096) s_rresp <= 2;
        else case (s_araddr)
          'h00: s_rdata <= 32'h4f545050;
          'h04: s_rdata <= 1;
          'h08: s_rdata <= {29'b0,rejected,done,busy};
          'h10: s_rdata <= address;
          'h14: s_rdata <= {result_status[23:8],8'b0,result_status[7:0]};
          default: begin
            if (s_araddr >= 'h20 && s_araddr < 'h60)
              s_rdata <= payload[32*((s_araddr-'h20)>>2)+:32];
            else if (s_araddr >= 'h80 && s_araddr < 'hc0)
              s_rdata <= result[32*((s_araddr-'h80)>>2)+:32];
            else s_rresp <= 2;
          end
        endcase
      end
    end
  end
endmodule
