// SPDX-License-Identifier: Apache-2.0
// Model the BSCANE2 fabric signals, then exercise the real 640-bit mailbox and
// RAM CSR service across independent clocks. No FPGA/USB access is performed.
`timescale 1ns/1ps
module BSCANE2 #(parameter JTAG_CHAIN=2)(
  output reg TCK=0, CAPTURE=0, SHIFT=0, UPDATE=0, SEL=0, TDI=0,
  input TDO, output DRCK, RESET, RUNTEST
);
  assign DRCK=TCK;
  assign RESET=0;
  assign RUNTEST=0;
endmodule

module tb_status;
  reg clk=0;
  always #10 clk=~clk;
  reg rst=1;
  reg [2047:0] data0=0, data1=0;
  reg [1:0] ack=0;
  wire [1:0] request;
  wire [2:0] led;
  ramtest_jtag dut(.clk(clk),.rst(rst),.snapshot0(data0),.snapshot1(data1),
                  .snapshot_ack(ack),.snapshot_request(request),.led(led));

  task cycle(input cap,input sh,input upd,input selected,input bit_in);
    begin
      dut.u_bscan.TCK=0;
      dut.u_bscan.CAPTURE=cap;dut.u_bscan.SHIFT=sh;dut.u_bscan.UPDATE=upd;
      dut.u_bscan.SEL=selected;dut.u_bscan.TDI=bit_in;
      #83;dut.u_bscan.TCK=1;#83;
    end
  endtask
  task scan(input [639:0] frame, output [639:0] response);
    integer bit_index;
    begin
      response=0;
      cycle(1,0,0,1,0);
      for(bit_index=0;bit_index<640;bit_index=bit_index+1) begin
        response[bit_index]=dut.u_bscan.TDO;
        cycle(0,1,0,1,frame[bit_index]);
      end
      cycle(0,0,1,1,0);
      cycle(0,0,0,0,0);
    end
  endtask
  reg [15:0] sequence_number=0;
  task command(input [7:0] opcode,input [31:0] address,input [31:0] value,
               output [31:0] answer, output [7:0] status);
    reg [639:0] frame,response;
    integer polls;
    begin
      sequence_number=sequence_number+1'b1;
      frame=0;
      frame[31:0]=value;frame[543:512]=address;frame[547:544]=15;
      frame[555:548]=opcode;frame[571:556]=sequence_number;frame[603:572]=32'h4f54504a;
      scan(frame,response);
      polls=0;
      while(response[535:520]!=sequence_number && polls<5) begin
        scan(0,response);polls=polls+1;
      end
      if(response[535:520]!=sequence_number || response[567:536]!=32'h4f54504a)
        $fatal(1,"mailbox sequence/magic mismatch");
      answer=response[31:0];status=response[519:512];
    end
  endtask
  reg [31:0] answer;
  reg [7:0] status;
  initial begin
    repeat(10) @(negedge clk);rst=0;
    command(1,0,0,answer,status);
    if(status!=0 || answer!=32'h52414d54) $fatal(1,"RAM identity missing");
    command(2,'h100,123,answer,status);
    if(status!=1 || request!=0) $fatal(1,"unsupported write changed snapshots");
    command(2,'h24,1,answer,status);
    if(status!=0 || request!=1) $fatal(1,"snapshot request missing");
    command(1,'h18,0,answer,status);
    if(status!=0 || answer!=1) $fatal(1,"snapshot busy missing");
    command(1,'h100,0,answer,status);
    if(status!=1) $fatal(1,"read of busy snapshot accepted");
    command(2,'h24,1,answer,status);
    if(status!=2 || request!=1) $fatal(1,"busy request overwritten");
    data0[0+:32]=32'h11112222;data0[2016+:32]=32'h77778888;
    data1[0+:32]=32'h33334444;
    @(negedge clk);ack[0]=request[0];
    repeat(10) @(negedge clk);
    command(1,'h100,0,answer,status);
    if(status!=0 || answer!=32'h11112222) $fatal(1,"channel0 first word wrong");
    command(1,'h1fc,0,answer,status);
    if(status!=0 || answer!=32'h77778888) $fatal(1,"channel0 last word wrong");
    command(1,'h200,0,answer,status);
    if(status!=0 || answer!=32'h33334444) $fatal(1,"channel1 selection wrong");
    command(1,'h101,0,answer,status);
    if(status!=1) $fatal(1,"unaligned read accepted");
    command(2,'h24,2,answer,status);
    if(status!=0 || request!=3) $fatal(1,"channel1 request wrong");
    command(1,'h100,0,answer,status);
    if(status!=0 || answer!=32'h11112222) $fatal(1,"channel1 blocked channel0");
    command(1,'h200,0,answer,status);
    if(status!=1) $fatal(1,"channel1 busy read accepted");
    $display("PASS_RAM_STATUS_SERIAL_MAILBOX_BUSY_WORDS_AND_CHANNELS");$finish;
  end
  initial begin #10000000;$fatal(1,"timeout");end
endmodule
