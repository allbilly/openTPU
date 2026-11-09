`timescale 1ns/1ps
`default_nettype none
module tpu_scores (
  input logic clk,
  input logic rst,
  input logic [15:0] ub_wr_host_data_in [0:1],
  input logic ub_wr_host_valid_in [0:1],
  input logic ub_rd_start_in,
  input logic ub_rd_transpose,
  input logic [8:0] ub_ptr_select,
  input logic [15:0] ub_rd_addr_in,
  input logic [15:0] ub_rd_row_size,
  input logic [15:0] ub_rd_col_size,
  input logic [15:0] learning_rate_in,
  input logic [3:0] vpu_data_pathway,
  input logic sys_switch_in,
  input logic [15:0] vpu_leak_factor_in,
  input logic [15:0] inv_batch_size_times_two_in,
  output logic [1023:0] ub_flat,
  output logic [15:0] dbg_sys_data_21,
  output logic [15:0] dbg_sys_data_22,
  output logic dbg_sys_valid_21,
  output logic dbg_sys_valid_22,
  output logic [15:0] dbg_bias_z_1,
  output logic [15:0] dbg_bias_z_2,
  output logic dbg_bias_valid_1,
  output logic dbg_bias_valid_2,
  output logic [15:0] dbg_lr_1,
  output logic [15:0] dbg_lr_2,
  output logic dbg_lr_valid_1,
  output logic dbg_lr_valid_2,
  output logic [15:0] dbg_loss_1,
  output logic [15:0] dbg_loss_2,
  output logic dbg_loss_valid_1,
  output logic dbg_loss_valid_2,
  output logic [15:0] dbg_lrd_1,
  output logic [15:0] dbg_lrd_2,
  output logic dbg_lrd_valid_1,
  output logic dbg_lrd_valid_2,
  output logic [15:0] dbg_hcache_1,
  output logic [15:0] dbg_hcache_2,
  output logic [15:0] dbg_vpu_out_1,
  output logic [15:0] dbg_vpu_out_2,
  output logic dbg_vpu_valid_1,
  output logic dbg_vpu_valid_2,
  output logic [15:0] dbg_old_0,
  output logic [15:0] dbg_old_1,
  output logic [15:0] dbg_grad_0,
  output logic [15:0] dbg_grad_1,
  output logic dbg_gd_valid_0,
  output logic dbg_gd_valid_1,
  output logic dbg_gd_done_0,
  output logic dbg_gd_done_1,
  output logic [15:0] dbg_gd_upd_0,
  output logic [15:0] dbg_gd_upd_1,
  output logic dbg_gd_bw,
  output logic [15:0] dbg_gd_ptr,
  output logic [15:0] dbg_wr_ptr,
  output logic [15:0] dbg_rd_col_size,
  output logic dbg_rd_col_valid,
  output logic [15:0] dbg_w11, dbg_w12, dbg_w21, dbg_w22,
  output logic [1:0] dbg_pe_en,
  output logic dbg_start1, dbg_start2, dbg_switch, dbg_accept1, dbg_accept2,
  output logic dbg_pev11, dbg_pev12, dbg_pev21, dbg_pev22,
  output logic dbg_col_size_valid,
  output logic [15:0] dbg_col_size,
  output logic [15:0] dbg_bias_in_1, dbg_bias_in_2,
  output logic [15:0] dbg_bias_scalar_1, dbg_bias_scalar_2,
  output logic [15:0] dbg_lr_in_1, dbg_lr_in_2,
  output logic [15:0] dbg_lr_leak,
  output logic [15:0] dbg_loss_in_1, dbg_loss_in_2,
  output logic [15:0] dbg_loss_Y_1, dbg_loss_Y_2,
  output logic [15:0] dbg_loss_inv,
  output logic [15:0] dbg_lrd_in_1, dbg_lrd_in_2,
  output logic [15:0] dbg_lrd_H_1, dbg_lrd_H_2
);
  tpu #(.SYSTOLIC_ARRAY_WIDTH(2)) u_tpu (
    .clk(clk), .rst(rst),
    .ub_wr_host_data_in(ub_wr_host_data_in), .ub_wr_host_valid_in(ub_wr_host_valid_in),
    .ub_rd_start_in(ub_rd_start_in), .ub_rd_transpose(ub_rd_transpose),
    .ub_ptr_select(ub_ptr_select), .ub_rd_addr_in(ub_rd_addr_in),
    .ub_rd_row_size(ub_rd_row_size), .ub_rd_col_size(ub_rd_col_size),
    .learning_rate_in(learning_rate_in), .vpu_data_pathway(vpu_data_pathway),
    .sys_switch_in(sys_switch_in), .vpu_leak_factor_in(vpu_leak_factor_in),
    .inv_batch_size_times_two_in(inv_batch_size_times_two_in));

  genvar gi;
  generate for (gi = 0; gi < 64; gi = gi + 1) begin : g_ub
    assign ub_flat[gi*16 +: 16] = u_tpu.ub_inst.ub_memory[gi];
  end endgenerate
  assign dbg_sys_data_21 = u_tpu.sys_data_out_21;
  assign dbg_sys_data_22 = u_tpu.sys_data_out_22;
  assign dbg_sys_valid_21 = u_tpu.sys_valid_out_21;
  assign dbg_sys_valid_22 = u_tpu.sys_valid_out_22;
  assign dbg_bias_z_1 = u_tpu.vpu_inst.bias_z_data_out_1;
  assign dbg_bias_z_2 = u_tpu.vpu_inst.bias_z_data_out_2;
  assign dbg_bias_valid_1 = u_tpu.vpu_inst.bias_valid_1_out;
  assign dbg_bias_valid_2 = u_tpu.vpu_inst.bias_valid_2_out;
  assign dbg_lr_1 = u_tpu.vpu_inst.lr_data_1_out;
  assign dbg_lr_2 = u_tpu.vpu_inst.lr_data_2_out;
  assign dbg_lr_valid_1 = u_tpu.vpu_inst.lr_valid_1_out;
  assign dbg_lr_valid_2 = u_tpu.vpu_inst.lr_valid_2_out;
  assign dbg_loss_1 = u_tpu.vpu_inst.loss_data_1_out;
  assign dbg_loss_2 = u_tpu.vpu_inst.loss_data_2_out;
  assign dbg_loss_valid_1 = u_tpu.vpu_inst.loss_valid_1_out;
  assign dbg_loss_valid_2 = u_tpu.vpu_inst.loss_valid_2_out;
  assign dbg_lrd_1 = u_tpu.vpu_inst.lr_d_data_1_out;
  assign dbg_lrd_2 = u_tpu.vpu_inst.lr_d_data_2_out;
  assign dbg_lrd_valid_1 = u_tpu.vpu_inst.lr_d_valid_1_out;
  assign dbg_lrd_valid_2 = u_tpu.vpu_inst.lr_d_valid_2_out;
  assign dbg_hcache_1 = u_tpu.vpu_inst.last_H_data_1_out;
  assign dbg_hcache_2 = u_tpu.vpu_inst.last_H_data_2_out;
  assign dbg_vpu_out_1 = u_tpu.vpu_data_out_1;
  assign dbg_vpu_out_2 = u_tpu.vpu_data_out_2;
  assign dbg_vpu_valid_1 = u_tpu.vpu_valid_out_1;
  assign dbg_vpu_valid_2 = u_tpu.vpu_valid_out_2;
  assign dbg_old_0 = u_tpu.ub_inst.value_old_in[0];
  assign dbg_old_1 = u_tpu.ub_inst.value_old_in[1];
  assign dbg_grad_0 = u_tpu.ub_inst.ub_wr_data_in[0];
  assign dbg_grad_1 = u_tpu.ub_inst.ub_wr_data_in[1];
  assign dbg_gd_valid_0 = u_tpu.ub_inst.grad_descent_valid_in[0];
  assign dbg_gd_valid_1 = u_tpu.ub_inst.grad_descent_valid_in[1];
  assign dbg_gd_done_0 = u_tpu.ub_inst.grad_descent_done_out[0];
  assign dbg_gd_done_1 = u_tpu.ub_inst.grad_descent_done_out[1];
  assign dbg_gd_upd_0 = u_tpu.ub_inst.value_updated_out[0];
  assign dbg_gd_upd_1 = u_tpu.ub_inst.value_updated_out[1];
  assign dbg_gd_bw = u_tpu.ub_inst.grad_bias_or_weight;
  assign dbg_gd_ptr = u_tpu.ub_inst.grad_descent_ptr;
  assign dbg_wr_ptr = u_tpu.ub_inst.wr_ptr;
  assign dbg_rd_col_size = u_tpu.ub_rd_col_size_out;
  assign dbg_rd_col_valid = u_tpu.ub_rd_col_size_valid_out;
  assign dbg_bias_in_1 = u_tpu.vpu_inst.bias_data_1_in;
  assign dbg_bias_in_2 = u_tpu.vpu_inst.bias_data_2_in;
  assign dbg_bias_scalar_1 = u_tpu.vpu_inst.bias_scalar_in_1;
  assign dbg_bias_scalar_2 = u_tpu.vpu_inst.bias_scalar_in_2;
  assign dbg_lr_in_1 = u_tpu.vpu_inst.lr_data_1_in;
  assign dbg_lr_in_2 = u_tpu.vpu_inst.lr_data_2_in;
  assign dbg_lr_leak = u_tpu.vpu_inst.lr_leak_factor_in;
  assign dbg_loss_in_1 = u_tpu.vpu_inst.loss_data_1_in;
  assign dbg_loss_in_2 = u_tpu.vpu_inst.loss_data_2_in;
  assign dbg_loss_Y_1 = u_tpu.vpu_inst.Y_in_1;
  assign dbg_loss_Y_2 = u_tpu.vpu_inst.Y_in_2;
  assign dbg_loss_inv = u_tpu.vpu_inst.inv_batch_size_times_two_in;
  assign dbg_lrd_in_1 = u_tpu.vpu_inst.lr_d_data_1_in;
  assign dbg_lrd_in_2 = u_tpu.vpu_inst.lr_d_data_2_in;
  assign dbg_lrd_H_1 = u_tpu.vpu_inst.lr_d_H_in_1;
  assign dbg_lrd_H_2 = u_tpu.vpu_inst.lr_d_H_in_2;
  assign dbg_w11 = u_tpu.systolic_inst.pe11.weight_reg_active;
  assign dbg_w12 = u_tpu.systolic_inst.pe12.weight_reg_active;
  assign dbg_w21 = u_tpu.systolic_inst.pe21.weight_reg_active;
  assign dbg_w22 = u_tpu.systolic_inst.pe22.weight_reg_active;
  assign dbg_pe_en = u_tpu.systolic_inst.pe_enabled;
  assign dbg_start1 = u_tpu.systolic_inst.sys_start_1;
  assign dbg_start2 = u_tpu.systolic_inst.sys_start_2;
  assign dbg_switch = u_tpu.systolic_inst.sys_switch_in;
  assign dbg_accept1 = u_tpu.systolic_inst.sys_accept_w_1;
  assign dbg_accept2 = u_tpu.systolic_inst.sys_accept_w_2;
  assign dbg_pev11 = u_tpu.systolic_inst.pe_valid_out_11;
  assign dbg_pev12 = u_tpu.systolic_inst.pe_valid_out_12;
  assign dbg_pev21 = u_tpu.sys_valid_out_21;
  assign dbg_pev22 = u_tpu.sys_valid_out_22;
  assign dbg_col_size_valid = u_tpu.ub_rd_col_size_valid_out;
  assign dbg_col_size = u_tpu.ub_rd_col_size_out;
endmodule
module dump();
initial begin
  $dumpfile("waveforms/tpu_scores.vcd");
  $dumpvars(0, tpu_scores);
end
endmodule
