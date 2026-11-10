`timescale 1ns/1ps
module tb_openxc7_jtag;
  reg clk=0, rst=1;
  always #5 clk=~clk;
  reg req_valid=0;
  wire req_ready, rsp_valid;
  reg [603:0] req=0;
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
  otpu_jtag_axi dut (.*);
  reg [511:0] pattern;
  integer i;
  task tick; begin @(posedge clk); #1; end endtask
  task issue(input [7:0] op,input [31:0] addr,input [15:0] seq);
    begin
      @(negedge clk);
      req={32'h4f54504a,seq,op,4'hf,addr,pattern};
      req_valid=1; tick();
      @(negedge clk); req_valid=0;
    end
  endtask
  task result(input [7:0] status,input [15:0] seq);
    integer k;
    begin
      k=0;
      while (!rsp_valid && k<100) begin tick(); k=k+1; end
      if (!rsp_valid || rsp_status!==status || rsp_seq!==seq)
        $fatal(1,"response: valid=%b status=%d seq=%d expected %d/%d",rsp_valid,rsp_status,rsp_seq,status,seq);
      tick();
    end
  endtask
  initial begin
    for(i=0;i<16;i=i+1) pattern[i*32+:32]=32'h10203000+i;
    repeat(4) tick(); rst=0; tick();
    // Independent AXI-Lite W and AW acceptance, with W accepted first.
    issue(2,32'h200,1);
    repeat(4) tick();
    if(l_awaddr[0]!==32'h200 || l_wdata[0]!==pattern[31:0] || l_wstrb[0]!==4'hf)
      $fatal(1,"register payload");
    l_wready[0]=1; tick(); l_wready[0]=0;
    if(l_wvalid[0] || !l_awvalid[0]) $fatal(1,"independent W handshake");
    repeat(3) tick(); l_awready[0]=1; tick(); l_awready[0]=0;
    l_bvalid[0]=1; tick(); l_bvalid[0]=0; result(0,1);
    // Real LiteDRAM window, response data and AXI error propagation.
    issue(1,32'h10044,2);
    repeat(3) tick();
    if(!l_arvalid[1] || l_arvalid[0] || l_araddr[1]!==32'h10044) $fatal(1,"CSR window");
    l_arready[1]=1; tick(); l_arready[1]=0;
    l_rdata[1]=32'hdeadbeef; l_rresp[1]=2; l_rvalid[1]=1;
    tick(); l_rvalid[1]=0; result(2,2);
    if(rsp_data!==512'hdeadbeef) $fatal(1,"register read value");
    // Four full-width beats, channel-1 address, W accepted before AW.
    issue(4,32'h80000040,3);
    if(x_awaddr!==32'h80000040 || x_awlen!==3 || x_awid!==0) $fatal(1,"write burst address");
    for(i=0;i<4;i=i+1) begin
      repeat(2) tick();
      if(!x_wvalid || x_wdata!==pattern[128*i+:128] || x_wstrb!==16'hffff || x_wlast!==(i==3))
        $fatal(1,"write beat %d",i);
      x_wready=1; tick(); x_wready=0;
    end
    if(x_wvalid || !x_awvalid) $fatal(1,"burst handshakes");
    x_awready=1; tick(); x_awready=0;
    x_bresp=3; x_bvalid=1; tick(); x_bvalid=0; result(3,3);
    // Read burst with gaps; all 512 bits and RLAST ordering are checked.
    issue(3,32'h40,4);
    if(x_araddr!==32'h40 || x_arlen!==3 || x_arid!==0) $fatal(1,"read burst address");
    repeat(3) tick(); x_arready=1; tick(); x_arready=0;
    for(i=0;i<4;i=i+1) begin
      repeat(2) tick();
      x_rdata=pattern[128*i+:128]; x_rlast=(i==3); x_rvalid=1;
      tick(); x_rvalid=0;
    end
    result(0,4); if(rsp_data!==pattern) $fatal(1,"full read value");
    issue(3,32'h41,5); result(4,5);
    issue(1,32'h20000,6); result(6,6);
    issue(99,0,7); result(5,7);
    issue(3,32'h80,8);
    x_arready=1; tick(); x_arready=0;
    x_rvalid=1; x_rlast=1; tick(); x_rvalid=0; result(7,8);
    $display("PASS: AXI-Lite windows, independent handshakes, DDR 64-byte bursts, backpressure, errors");
    $finish;
  end
  initial begin #100000; $fatal(1,"timeout"); end
endmodule
