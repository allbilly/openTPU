`timescale 1ns/1ps
module tb_openxc7_mailbox;
  reg clk=0, rst=1, tck=0, capture=0, shift=0, update=0, sel=1, tdi=0;
  always #5 clk=~clk;
  wire tdo, req_valid;
  reg req_ready=0, rsp_valid=0;
  wire [603:0] req;
  reg [511:0] rsp_data=0;
  reg [7:0] rsp_status=0;
  reg [15:0] rsp_seq=0;
  otpu_jtag_mailbox dut (.*);
  reg [639:0] frame,got;
  task pulse; begin #7; tck=1; #7; tck=0; end endtask
  task scan(input [639:0] f,output [639:0] r);
    integer i;
    begin
      capture=1; pulse(); capture=0; shift=1;
      for(i=0;i<640;i=i+1) begin
        tdi=f[i]; r[i]=tdo; pulse();
      end
      shift=0; update=1; pulse(); update=0; pulse();
    end
  endtask
  initial begin
    repeat(4) @(negedge clk); rst=0;
    frame=0; frame[603:572]=32'h4f54504a; frame[571:556]=16'h1234;
    frame[555:548]=4; frame[543:512]=32'h80000040;
    frame[511:0]={16{32'hcafefeed}};
    scan(frame,got);
    repeat(8) @(negedge clk);
    if(!req_valid || req!==frame[603:0]) $fatal(1,"request crossing");
    // Hold ready low while polling: a poll must never replace the command.
    scan(0,got);
    if(!req_valid || req!==frame[603:0]) $fatal(1,"backpressure/poll stability");
    req_ready=1; repeat(2) @(negedge clk); req_ready=0;
    if(req_valid) $fatal(1,"request acknowledge");
    rsp_data=frame[511:0]; rsp_status=2; rsp_seq=16'h1234; rsp_valid=1;
    @(negedge clk); rsp_valid=0;
    // One scan clocks the response toggle through its synchronizer; the next
    // capture gets the stable payload. DR scanning itself cannot alter it.
    scan(0,got); scan(0,got);
    if(got[567:536]!==32'h4f54504a || got[535:520]!==16'h1234 ||
       got[519:512]!==2 || got[511:0]!==frame[511:0]) $fatal(1,"response crossing");
    if(req_valid) $fatal(1,"poll submitted a command");
    $display("PASS: asynchronous mailbox, held request, poll, sequence and full response");
    $finish;
  end
  initial begin #200000; $fatal(1,"timeout"); end
endmodule
