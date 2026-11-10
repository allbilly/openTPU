// TLP/AXI protocol test. AXI response models below are not physical DDR or PCIe PHY evidence.
`timescale 1ns/1ps
module tb_openxc7_pcie;
  reg clk=0, rst=1;
  always #5 clk=~clk;
  wire req_valid, req_ready, rsp_valid;
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
  otpu_jtag_axi dut (.*);
  reg pclk=0;
  always #4 pclk=~pclk;
  reg [63:0] rxdata=0;
  reg [1:0] rxkeep=0;
  reg rxlast=0,rxvalid=0,txready=0;
  wire rxready,txvalid,txlast;
  wire [63:0] txdata;
  wire [1:0] txkeep;
  wire [32:0] txuser;
  wire [31:2] al_waddr,al_araddr;
  wire [31:0] al_wdata,al_rdata;
  wire al_wvalid,al_wready,al_arvalid,al_arready,al_rvalid,al_rready;
  wire [31:0] p_awaddr,p_wdata,p_araddr,p_rdata;
  wire [3:0] p_wstrb;
  wire p_awvalid,p_awready,p_wvalid,p_wready,p_bvalid,p_bready;
  wire p_arvalid,p_arready,p_rvalid,p_rready;
  wire [1:0] p_bresp,p_rresp;
  axis_pcie_to_al_us #(.ADDR_WIDTH(32),.BUS_WIDTH(64),.ULTRA_SCALE(0),.TKEEP_WIDTH(2),.DWISBE(1)) u_tlp (
    .clk(pclk),.rst_n(!rst),.cfg_completer_id(16'h0100),
    .s_axis_rx_tdata(rxdata),.s_axis_rx_tkeep(rxkeep),.s_axis_rx_tlast(rxlast),.s_axis_rx_tvalid(rxvalid),
    .s_axis_rx_tuser(88'b0),.s_axis_rx_tready(rxready),
    .m_axis_tx_tready(txready),.m_axis_tx_tdata(txdata),.m_axis_tx_tkeep(txkeep),.m_axis_tx_tlast(txlast),
    .m_axis_tx_tvalid(txvalid),.m_axis_tx_tuser(txuser),
    .m_al_waddr(al_waddr),.m_al_wdata(al_wdata),.m_al_wvalid(al_wvalid),.m_al_wready(al_wready),
    .m_al_araddr(al_araddr),.m_al_arvalid(al_arvalid),.m_al_arready(al_arready),
    .m_al_rdata(al_rdata),.m_al_rvalid(al_rvalid),.m_al_rready(al_rready));
  axil_to_al u_axil (
    .clk(pclk),.rst_n(!rst),
    .s_axi_awaddr(p_awaddr),.s_axi_wdata(p_wdata),.s_axi_araddr(p_araddr),.s_axi_rdata(p_rdata),.s_axi_wstrb(p_wstrb),
    .s_axi_awvalid(p_awvalid),.s_axi_awready(p_awready),.s_axi_wvalid(p_wvalid),.s_axi_wready(p_wready),
    .s_axi_bvalid(p_bvalid),.s_axi_bready(p_bready),.s_axi_bresp(p_bresp),
    .s_axi_arvalid(p_arvalid),.s_axi_arready(p_arready),.s_axi_rvalid(p_rvalid),.s_axi_rready(p_rready),.s_axi_rresp(p_rresp),
    .m_al_waddr(al_waddr),.m_al_wdata(al_wdata),.m_al_wvalid(al_wvalid),.m_al_wready(al_wready),
    .m_al_araddr(al_araddr),.m_al_arvalid(al_arvalid),.m_al_arready(al_arready),
    .m_al_rdata(al_rdata),.m_al_rvalid(al_rvalid),.m_al_rready(al_rready));
  otpu_pcie_mailbox u_bar (
    .pclk,.prst(rst),.clk,.rst,
    .s_awaddr({20'b0,p_awaddr[11:0]}),.s_araddr({20'b0,p_araddr[11:0]}),.s_wdata(p_wdata),.s_wstrb(p_wstrb),
    .s_awvalid(p_awvalid),.s_awready(p_awready),.s_wvalid(p_wvalid),.s_wready(p_wready),
    .s_bvalid(p_bvalid),.s_bready(p_bready),.s_bresp(p_bresp),
    .s_arvalid(p_arvalid),.s_arready(p_arready),.s_rvalid(p_rvalid),.s_rready(p_rready),.s_rresp(p_rresp),.s_rdata(p_rdata),
    .req_valid,.req_ready,.req,.rsp_valid,.rsp_data,.rsp_status,.rsp_seq);
  reg [511:0] pattern;
  task sendbeat(input [63:0] data,input [1:0] keep,input last);
    begin
      @(negedge pclk);rxdata=data;rxkeep=keep;rxlast=last;rxvalid=1;
      @(posedge pclk);while(!rxready) @(posedge pclk);
      @(negedge pclk);rxvalid=0;
    end
  endtask
  task writeword(input [31:0] offset,input [31:0] data);
    begin
      // Host BAR base 0xf0000000, 3DW MemWr, full first byte enable.
      sendbeat({32'h12345a0f,32'h40000001},2'b11,0);
      sendbeat({data,32'hf0000000+offset},2'b11,1);
    end
  endtask
  task readword(input [31:0] offset,output [31:0] data);
    reg [63:0] held;
    begin
      txready=0;
      sendbeat({32'h12345a0f,32'h00000001},2'b11,0);
      sendbeat({32'b0,32'hf0000000+offset},2'b01,1);
      @(negedge pclk);while(!txvalid) @(negedge pclk);
      if(txdata[31:0]!==32'h4a000001 || txdata[63:48]!==16'h0100 || txkeep!==3 || txlast)
        $fatal(1,"completion first header %h",txdata);
      held=txdata; repeat(3) begin @(negedge pclk);if(txdata!==held || !txvalid) $fatal(1,"TX stalled header changed");end
      txready=1;@(posedge pclk);@(negedge pclk);txready=0;
      while(!txvalid) @(negedge pclk);
      if(txdata[31:8]!==24'h12345a || txdata[6:0]!==offset[6:0] || txkeep!==3 || !txlast)
        $fatal(1,"completion second header %h",txdata);
      data=txdata[63:32];held=txdata;
      repeat(3) begin @(negedge pclk);if(txdata!==held || !txvalid) $fatal(1,"TX stalled payload changed");end
      txready=1;@(posedge pclk);@(negedge pclk);txready=0;
    end
  endtask
  integer i;
  task tick; begin @(posedge clk); #1; end endtask
  task issue(input [7:0] op,input [31:0] addr,input [15:0] seq);
    integer j;
    begin
      writeword('h10,addr);
      for(j=0;j<16;j=j+1) writeword('h20+4*j,pattern[32*j+:32]);
      writeword('h0c,{seq,4'b0,4'hf,op});
      while(!req_valid) tick();
      tick();
    end
  endtask
  task result(input [7:0] status,input [15:0] seq);
    reg [31:0] st,r;
    integer k;
    begin
      k=0;st=0;
      while(!st[1] && k<100) begin readword('h08,st);k=k+1;end
      readword('h14,r);
      if(!st[1] || st[0] || st[2] || r!=={seq,8'b0,status})
        $fatal(1,"BAR response state=%h seq/status=%h expected %d/%d",st,r,status,seq);
      tick();
    end
  endtask
  initial begin
    for(i=0;i<16;i=i+1) pattern[i*32+:32]=32'h10203000+i;
    repeat(4) tick(); rst=0; tick();
    begin : identity
      reg [31:0] value;
      readword(0,value);if(value!==32'h4f545050) $fatal(1,"mailbox identity");
      readword(4,value);if(value!==1) $fatal(1,"mailbox ABI");
    end
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
    // Full 32-bit DDR address reaches the final 64-byte beat of each channel.
    for(i=0;i<2;i=i+1) begin
      issue(3,(i==0 ? 32'h7fffffc0 : 32'hffffffc0),9+i);
      if(x_araddr !== (i==0 ? 32'h7fffffc0 : 32'hffffffc0)) $fatal(1,"full channel address");
      x_arready=1;tick();x_arready=0;
      begin : final_channel_read
        integer j;
        for(j=0;j<4;j=j+1) begin
          x_rdata=128'h112233445566778899aabbccddeeff00;x_rvalid=1;x_rlast=(j==3);
          tick();x_rvalid=0;tick();
        end
      end
      result(0,9+i);
      begin : payload_check
        integer j;reg [31:0] value;
        for(j=0;j<16;j=j+1) begin
          readword('h80+4*j,value);
          if(value!==32'(128'h112233445566778899aabbccddeeff00 >> (32*(j%4)))) $fatal(1,"BAR DDR data %d",j);
        end
      end
    end
    $display("PASS: real 3DW TLP RX/TX, AL/AXI-Lite, async BAR command path, full channel ends; AXI-Lite windows, independent handshakes, DDR 64-byte bursts, backpressure, errors");
    $finish;
  end
  initial begin #1000000; $fatal(1,"timeout"); end
endmodule
