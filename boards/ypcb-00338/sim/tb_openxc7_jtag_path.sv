`timescale 1ns/1ps
module tb_openxc7_jtag_path;
  reg clk=0, rst=1, tck=0, capture=0, shift=0, update=0, sel=1, tdi=0;
  always #5 clk=~clk;

  wire tdo, req_valid, req_ready, rsp_valid;
  wire [603:0] req;
  wire [511:0] rsp_data;
  wire [7:0] rsp_status;
  wire [15:0] rsp_seq;

  wire [1:0][31:0] l_awaddr,l_araddr,l_wdata;
  wire [1:0][3:0] l_wstrb;
  wire [1:0] l_awvalid,l_wvalid,l_bready,l_arvalid,l_rready;
  reg [1:0] l_awready=0,l_wready=0,l_bvalid=0,l_arready=0,l_rvalid=0;
  reg [1:0][1:0] l_bresp=0,l_rresp=0;
  reg [1:0][31:0] l_rdata=0;

  wire [3:0] x_awid,x_arid;
  wire [31:0] x_awaddr,x_araddr;
  wire [7:0] x_awlen,x_arlen;
  wire x_awvalid,x_arvalid,x_wvalid,x_wlast,x_bready,x_rready;
  wire [127:0] x_wdata;
  wire [15:0] x_wstrb;
  reg x_awready=0,x_arready=0,x_wready=0,x_bvalid=0,x_rvalid=0,x_rlast=0;
  reg [3:0] x_bid=0,x_rid=0;
  reg [1:0] x_bresp=0,x_rresp=0;
  reg [127:0] x_rdata=0;

  otpu_jtag_mailbox u_mailbox (.*);
  otpu_jtag_axi axi_bridge (.*);

  reg [639:0] frame, response;
  reg [511:0] pattern;
  integer i, cycles;

  task tick_clk; begin @(posedge clk); #1; end endtask
  task pulse_tck; begin #7; tck=1; #7; tck=0; end endtask
  task scan(input [639:0] tx, output [639:0] rx);
    integer bitno;
    begin
      capture=1; pulse_tck(); capture=0; shift=1;
      for(bitno=0;bitno<640;bitno=bitno+1) begin
        tdi=tx[bitno]; rx[bitno]=tdo; pulse_tck();
      end
      shift=0; update=1; pulse_tck(); update=0; pulse_tck();
    end
  endtask
  task send(input [7:0] opcode,input [31:0] address,input [15:0] seqnum);
    begin
      frame=0;
      frame[603:572]=32'h4f54504a;
      frame[571:556]=seqnum;
      frame[555:548]=opcode;
      frame[547:544]=4'hf;
      frame[543:512]=address;
      frame[511:0]=pattern;
      scan(frame,response);
    end
  endtask
  task poll_response(output [639:0] rx);
    begin
      repeat(3) @(negedge clk);
      scan(640'b0,rx);
      scan(640'b0,rx);
    end
  endtask
  task wait_rsp;
    begin
      cycles=0;
      while(!rsp_valid && cycles<100) begin tick_clk(); cycles=cycles+1; end
      if(!rsp_valid) $fatal(1,"AXI bridge did not return a mailbox response");
    end
  endtask

  initial begin
    for(i=0;i<16;i=i+1) pattern[i*32+:32]=32'h10203000+i;
    repeat(4) tick_clk(); rst=0;

    // USER2 serial command -> async mailbox -> LiteDRAM CSR read -> response.
    send(1,32'h00010044,16'h1234);
    cycles=0;
    while(!l_arvalid[1] && cycles<100) begin tick_clk(); cycles=cycles+1; end
    if(!l_arvalid[1] || l_arvalid[0] || l_araddr[1]!==32'h00010044)
      $fatal(1,"serial register request did not reach AXI-Lite window 1");
    @(negedge clk); l_arready[1]=1;
    @(negedge clk); l_arready[1]=0;
    l_rdata[1]=32'hdeadbeef; l_rresp[1]=0; l_rvalid[1]=1;
    @(negedge clk); l_rvalid[1]=0;
    wait_rsp();
    poll_response(response);
    if(response[567:536]!==32'h4f54504a || response[535:520]!==16'h1234 ||
       response[519:512]!==0 || response[511:0]!=={480'b0,32'hdeadbeef})
      $fatal(1,"serial register response data/status/sequence mismatch");

    // USER2 serial command -> async mailbox -> four-beat DDR read -> response.
    send(3,32'h00000040,16'h1235);
    cycles=0;
    while(!x_arvalid && cycles<100) begin tick_clk(); cycles=cycles+1; end
    if(!x_arvalid || x_araddr!==32'h40 || x_arlen!==3 || x_arid!==0)
      $fatal(1,"serial DDR request did not reach the four-beat AXI burst");
    @(negedge clk); x_arready=1;
    @(negedge clk); x_arready=0;
    for(i=0;i<4;i=i+1) begin
      @(negedge clk);
      x_rdata=pattern[128*i+:128]; x_rresp=0; x_rid=0;
      x_rlast=(i==3); x_rvalid=1;
      @(negedge clk); x_rvalid=0;
    end
    wait_rsp();
    poll_response(response);
    if(response[567:536]!==32'h4f54504a || response[535:520]!==16'h1235 ||
       response[519:512]!==0 || response[511:0]!==pattern)
      $fatal(1,"serial DDR response data/status/sequence mismatch");

    // USER2 serial command -> async mailbox -> accelerator AXI-Lite write.
    send(2,32'h00000200,16'h1236);
    cycles=0;
    while(!(l_awvalid[0] && l_wvalid[0]) && cycles<100) begin
      tick_clk(); cycles=cycles+1;
    end
    if(!l_awvalid[0] || !l_wvalid[0] || l_awaddr[0]!==32'h200 ||
       l_wdata[0]!==pattern[31:0] || l_wstrb[0]!==4'hf)
      $fatal(1,"serial register write payload did not reach AXI-Lite window 0");
    // Preserve independent AXI-Lite acceptance; write data arrives first.
    @(negedge clk); l_wready[0]=1;
    @(negedge clk); l_wready[0]=0;
    if(l_wvalid[0] || !l_awvalid[0]) $fatal(1,"serial W handshake");
    @(negedge clk); l_awready[0]=1;
    @(negedge clk); l_awready[0]=0;
    l_bresp[0]=0; l_bvalid[0]=1;
    @(negedge clk); l_bvalid[0]=0;
    wait_rsp();
    poll_response(response);
    if(response[567:536]!==32'h4f54504a || response[535:520]!==16'h1236 ||
       response[519:512]!==0 || response[511:0]!==0)
      $fatal(1,"serial register write response mismatch");

    // USER2 serial command -> async mailbox -> four-beat DDR write -> response.
    send(4,32'h80000040,16'h1237);
    cycles=0;
    while(!(x_awvalid && x_wvalid) && cycles<100) begin
      tick_clk(); cycles=cycles+1;
    end
    if(!x_awvalid || x_awaddr!==32'h80000040 || x_awlen!==3 || x_awid!==0)
      $fatal(1,"serial DDR write did not reach the expected AXI burst");
    for(i=0;i<4;i=i+1) begin
      if(!x_wvalid || x_wdata!==pattern[128*i+:128] || x_wstrb!==16'hffff ||
         x_wlast!==(i==3)) $fatal(1,"serial DDR write beat %0d",i);
      @(negedge clk); x_wready=1;
      @(negedge clk); x_wready=0;
    end
    if(x_wvalid || !x_awvalid) $fatal(1,"serial DDR write data/address handshakes");
    @(negedge clk); x_awready=1;
    @(negedge clk); x_awready=0;
    x_bid=0; x_bresp=0; x_bvalid=1;
    @(negedge clk); x_bvalid=0;
    wait_rsp();
    poll_response(response);
    if(response[567:536]!==32'h4f54504a || response[535:520]!==16'h1237 ||
       response[519:512]!==0 || response[511:0]!==0)
      $fatal(1,"serial DDR write response mismatch");
    if(req_valid) $fatal(1,"mailbox retained a completed request");
    $display("PASS: USER2 mailbox to AXI-Lite and DDR read/write round trips");
    $finish;
  end
  initial begin #300000; $fatal(1,"timeout"); end
endmodule
