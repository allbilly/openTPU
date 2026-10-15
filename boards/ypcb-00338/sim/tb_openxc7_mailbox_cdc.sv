`timescale 1ps/1ps
// Digital latency/bundled-data check. The runner supplies a temporary copy
// with synthetic bus delays; this does not simulate analog metastability.
module tb_openxc7_mailbox_cdc;
  parameter integer REQUEST_DELAY_PS = 0;
  parameter integer RESPONSE_DELAY_PS = 0;
  localparam integer TCK_PERIOD_PS = 166668;
  reg clk=0, rst=1, tck=0, capture=0, shift=0, update=0, sel=1, tdi=0;
  always #5000 clk=~clk;
  integer phase_ps=0;
  initial begin
    if (!$value$plusargs("PHASE_PS=%d", phase_ps)) phase_ps=0;
    #(phase_ps);
    forever #(TCK_PERIOD_PS/2) tck=~tck;
  end
  wire tdo, req_valid;
  reg req_ready=0, rsp_valid=0;
  wire [603:0] req;
  reg [511:0] rsp_data=0;
  reg [7:0] rsp_status=0;
  reg [15:0] rsp_seq=0;
  otpu_jtag_mailbox_cdc_probe #(.REQUEST_DELAY_PS(REQUEST_DELAY_PS),
    .RESPONSE_DELAY_PS(RESPONSE_DELAY_PS)) dut (.*);
  reg [639:0] frame=0, got=0;
  reg [603:0] expected_request=0;
  reg [567:0] expected_response=0;
  reg old_valid=0, old_rs_seen=0;
  integer requests=0, responses=0;
  time request_launch=0, response_launch=0;
  time request_min=64'hffffffffffffffff, request_max=0;
  time response_min=64'hffffffffffffffff, response_max=0;
  time elapsed_ps;

  always @(posedge tck)
    if (sel && update && dut.sr[603:572]==32'h4f54504a && dut.sr[555:548]!=0)
      request_launch=$time;
  always @(posedge clk) begin
    if (rsp_valid) response_launch=$time;
    #1;
    if (req_valid && !old_valid) begin
      elapsed_ps=$time-request_launch;
      if (elapsed_ps < 30000 || elapsed_ps > 40001)
        $fatal(1,"request capture latency differs: %0t",elapsed_ps);
      if (req !== expected_request)
        $fatal(1,"request payload captured before settling");
      if (elapsed_ps<request_min) request_min=elapsed_ps;
      if (elapsed_ps>request_max) request_max=elapsed_ps;
      requests=requests+1;
    end
    old_valid=req_valid;
  end
  always @(posedge tck) begin
    #1;
    if (dut.rs_seen != old_rs_seen) begin
      elapsed_ps=$time-response_launch;
      if (elapsed_ps < 3*TCK_PERIOD_PS || elapsed_ps > 4*TCK_PERIOD_PS+1)
        $fatal(1,"response capture latency differs: %0t",elapsed_ps);
      if (dut.response_tck !== expected_response)
        $fatal(1,"response payload captured before settling");
      if (elapsed_ps<response_min) response_min=elapsed_ps;
      if (elapsed_ps>response_max) response_max=elapsed_ps;
      responses=responses+1;
    end
    old_rs_seen=dut.rs_seen;
  end

  task scan(input [639:0] value, output [639:0] result);
    integer bit_index;
    begin
      @(negedge tck); capture=1; shift=0; update=0;
      @(negedge tck); capture=0; shift=1;
      for (bit_index=0;bit_index<640;bit_index=bit_index+1) begin
        tdi=value[bit_index]; result[bit_index]=tdo;
        @(negedge tck);
      end
      shift=0; update=1;
      @(negedge tck); update=0;
    end
  endtask

  integer transaction, word_index;
  initial begin
    repeat(4) @(negedge clk); rst=0;
    for (transaction=1;transaction<=17;transaction=transaction+1) begin
      frame=0;
      for (word_index=0;word_index<16;word_index=word_index+1)
        frame[word_index*32 +: 32] = (transaction[0] ? 32'haaaaaaaa : 32'h55555555)
          ^ (32'h01010101*word_index) ^ transaction;
      frame[543:512]=32'h12345678 ^ (transaction[0] ? 32'hffffffff : 32'h00000000);
      frame[547:544]=transaction[0] ? 4'hf : 4'h0;
      frame[555:548]=transaction[0] ? 8'haa : 8'h55;
      frame[571:556]=16'h96a5 ^ (transaction[0] ? 16'hffff : 16'h0000) ^ transaction;
      frame[603:572]=32'h4f54504a;
      expected_request=frame[603:0];
      scan(frame,got);
      wait(req_valid);
      // Hold backpressure before acknowledge; source and destination payloads
      // must remain stable under the supported one-outstanding-command flow.
      repeat(8) begin
        @(negedge clk);
        if (req !== expected_request || !req_valid) $fatal(1,"held request changed");
      end
      req_ready=1; repeat(2) @(negedge clk); req_ready=0;
      // Vary core completion by 0..16 cycles, spanning a whole TCK period.
      // Replies may complete at any TCK phase, unlike an immediate echo.
      repeat(transaction-1) @(negedge clk);
      rsp_data=~frame[511:0]; rsp_status=transaction & 7;
      rsp_seq=frame[571:556] ^ 16'ha55a;
      expected_response={32'h4f54504a,rsp_seq,rsp_status,rsp_data};
      rsp_valid=1; @(negedge clk); rsp_valid=0;
      wait(responses==transaction);
      scan(0,got);
      if (got[567:0] !== expected_response || req_valid)
        $fatal(1,"response scan or zero-poll protocol differs");
    end
    if (requests!=17 || responses!=17) $fatal(1,"transaction scope incomplete");
    $display("PASS|phase_ps=%0d|requests=%0d|responses=%0d|request_min_ps=%0t|request_max_ps=%0t|response_min_ps=%0t|response_max_ps=%0t",
      phase_ps,requests,responses,request_min,request_max,response_min,response_max);
    $finish;
  end
  initial begin #40000000000; $fatal(1,"CDC simulation timeout"); end
endmodule
