// Direct BAR AXI-Lite protocol and CDC/reset checks; no physical hardware.
`timescale 1ns/1ps
module tb_openxc7_pcie_mailbox;
  reg pclk=0,clk=0,prst=1,rst=1;
  always #4 pclk=~pclk;
  always #7 clk=~clk;
  reg [31:0] s_awaddr=0,s_wdata=0,s_araddr=0;
  reg [3:0] s_wstrb=0;
  reg s_awvalid=0,s_wvalid=0,s_bready=0,s_arvalid=0,s_rready=0;
  wire s_awready,s_wready,s_arready,s_bvalid,s_rvalid;
  wire [1:0] s_bresp,s_rresp;
  wire [31:0] s_rdata;
  wire req_valid;
  reg req_ready=0;
  wire [603:0] req;
  reg rsp_valid=0;
  reg [511:0] rsp_data=0;
  reg [7:0] rsp_status=0;
  reg [15:0] rsp_seq=0;
  otpu_pcie_mailbox dut(.*);
  reg [31:0] value;
  reg [603:0] held;
  integer i;
  task ptick; begin @(posedge pclk);#1;end endtask
  task ctick; begin @(posedge clk);#1;end endtask
  task aw(input [31:0] addr);
    begin
      @(negedge pclk);s_awaddr=addr;s_awvalid=1;
      @(posedge pclk);while(!s_awready) @(posedge pclk);
      @(negedge pclk);s_awvalid=0;
    end
  endtask
  task wd(input [31:0] data,input [3:0] strobe);
    begin
      @(negedge pclk);s_wdata=data;s_wstrb=strobe;s_wvalid=1;
      @(posedge pclk);while(!s_wready) @(posedge pclk);
      @(negedge pclk);s_wvalid=0;
    end
  endtask
  task wr(input [31:0] addr,data,input [3:0] strobe,input wfirst,input [1:0] response);
    begin
      if(wfirst) begin wd(data,strobe);repeat(3) ptick();aw(addr);end
      else begin aw(addr);repeat(3) ptick();wd(data,strobe);end
      while(!s_bvalid) ptick();
      if(s_bresp!==response) $fatal(1,"write response %h/%h",addr,s_bresp);
      repeat(3) begin ptick();if(!s_bvalid || s_bresp!==response) $fatal(1,"stalled B changed");end
      @(negedge pclk);s_bready=1;ptick();@(negedge pclk);s_bready=0;
    end
  endtask
  task rd(input [31:0] addr,output [31:0] data,input [1:0] response);
    begin
      @(negedge pclk);s_araddr=addr;s_arvalid=1;
      @(posedge pclk);while(!s_arready) @(posedge pclk);
      @(negedge pclk);s_arvalid=0;
      while(!s_rvalid) ptick();
      data=s_rdata;
      repeat(3) begin ptick();if(!s_rvalid || s_rdata!==data || s_rresp!==response) $fatal(1,"stalled R changed");end
      @(negedge pclk);s_rready=1;ptick();@(negedge pclk);s_rready=0;
    end
  endtask
  task finish_command(input [15:0] seq,input [7:0] status);
    begin
      @(negedge clk);req_ready=1;ctick();@(negedge clk);req_ready=0;
      rsp_seq=seq;rsp_status=status;rsp_data={16{32'h89abcdef}};rsp_valid=1;
      ctick();@(negedge clk);rsp_valid=0;
      repeat(6) ptick();
    end
  endtask
  initial begin
    repeat(4) ptick();@(negedge pclk);prst=0;rst=0;
    rd(0,value,0);if(value!==32'h4f545050) $fatal(1,"identity");
    wr('h10,32'h80000040,4'hf,0,0);
    wr('h10,32'h00001200,4'b0010,1,0);
    rd('h10,value,0);if(value!==32'h80001240) $fatal(1,"byte merge");
    // Invalid full offsets cannot alias the valid target-address register.
    wr('h1010,32'hfeedface,4'hf,1,2);
    rd('h10,value,0);if(value!==32'h80001240) $fatal(1,"high offset aliased");
    rd('h1000,value,2);
    wr('h08,4,4'hf,0,0);
    for(i=0;i<16;i=i+1) wr('h20+4*i,32'h10203000+i,4'hf,i%2,0);
    wr('h0c,32'hffff0f04,4'hf,1,0);
    while(!req_valid) ctick();
    if(req[603:572]!==32'h4f54504a || req[571:556]!==16'hffff || req[555:548]!==4 || req[543:512]!==32'h80001240)
      $fatal(1,"stable crossed command");
    for(i=0;i<16;i=i+1) if(req[32*i+:32]!==32'h10203000+i) $fatal(1,"full crossed payload");
    held=req;
    wr('h10,32'h12345678,4'hf,0,2);
    wr('h20,32'h12345678,4'hf,1,2);
    wr('h0c,32'h00010f03,4'hf,0,2);
    if(req!==held || !req_valid) $fatal(1,"busy write corrupted pending command");
    // Capture busy status, then complete across the asynchronous clock while
    // the read response is stalled: the held AXI response must stay stable.
    @(negedge pclk);s_araddr=8;s_arvalid=1;
    ptick();@(negedge pclk);s_arvalid=0;
    while(!s_rvalid) ptick();value=s_rdata;
    finish_command(16'hffff,2);
    if(s_rdata!==value || !s_rvalid) $fatal(1,"completion changed a stalled read");
    @(negedge pclk);s_rready=1;ptick();@(negedge pclk);s_rready=0;
    rd(8,value,0);if(value!==6) $fatal(1,"done/rejected status");
    rd('h14,value,0);if(value!==32'hffff0002) $fatal(1,"AXI error/sequence propagation");
    for(i=0;i<16;i=i+1) begin rd('h80+4*i,value,0);if(value!==32'h89abcdef) $fatal(1,"result payload");end
    wr(8,4,4'hf,1,0);
    // Malformed partial doorbell is rejected; no additional command crosses.
    wr('h0c,32'h00010f03,4'b0011,0,2);
    repeat(6) ctick();if(req_valid) $fatal(1,"partial doorbell submitted");
    wr(8,4,4'hf,0,0);
    wr('h0c,32'h00010f03,4'hf,0,0);
    while(!req_valid) ctick();
    if(req[571:556]!==1) $fatal(1,"sequence wrap");
    // Shared reset asserts between edges, cancelling both ownership toggles.
    #2;prst=1;rst=1;#1;
    if(req_valid || s_bvalid || s_rvalid) $fatal(1,"asynchronous reset assertion");
    repeat(4) ptick();@(negedge pclk);prst=0;rst=0;
    repeat(6) ctick();if(req_valid) $fatal(1,"old command replayed after reset");
    rd(8,value,0);if(value!==0) $fatal(1,"reset busy/done");
    wr('h10,32'hffffffc0,4'hf,1,0);
    wr('h0c,32'h00020f03,4'hf,0,0);
    while(!req_valid) ctick();
    if(req[543:512]!==32'hffffffc0 || req[571:556]!==2 || req[511:0]!==0) $fatal(1,"fresh post-reset command");
    finish_command(2,0);
    rd(8,value,0);if(value!==2) $fatal(1,"post-reset completion");
    $display("PASS: independent AW/W, strobes, B/R stalls, async stable buses, busy rejection, errors, wrap, reset");
    $finish;
  end
  initial begin #1000000;$fatal(1,"timeout");end
endmodule
