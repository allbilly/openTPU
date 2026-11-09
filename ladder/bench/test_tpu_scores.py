"""Step-2 XOR scoreboard cocotb bench: drives the toy TPU through a corrected
forward pass and the imported backward/SGD sequence, records every stage
boundary, then asserts Q8.8 golden values and datapath relations.
"""
import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, FallingEdge, ClockCycles, First, with_timeout
import numpy as np
import json
import os, sys
from toy_golden import (golden, HOST_UB, s16, fadd, fmul, fsub, leaky, LEAKQ, LRQ, INVQ)

### TODO: optimize for clk cycles later: focus on functionality first
# For transposed weight matrices set the start address one address above where the first element of the weight matrix is stored in UB

def to_fixed(val, frac_bits=8):
    """Convert a float to 16-bit fixed point with 8 fractional bits."""
    scaled = int(round(val * (1 << frac_bits)))
    return scaled & 0xFFFF


async def wait_vpu_output_done(dut, timeout_ns=10000):
    """Wait for a VPU output burst to complete on either active output lane."""
    async def wait_done():
        await First(FallingEdge(dut.dbg_vpu_valid_1), FallingEdge(dut.dbg_vpu_valid_2))
        while int(dut.dbg_vpu_valid_1.value) or int(dut.dbg_vpu_valid_2.value):
            await First(FallingEdge(dut.dbg_vpu_valid_1), FallingEdge(dut.dbg_vpu_valid_2))

    await with_timeout(wait_done(), timeout_ns, "ns")


# input:
X = np.array([[0., 0.],
              [0., 1.],
              [1., 0.],
              [1., 1.]])

Y = np.array([0, 1, 1, 0])

# weight layer 1
W1 = np.array([
    [0.2985, -0.5792], 
    [0.0913, 0.4234]
])

# weight layer 2
W2 = np.array([0.5266, 0.2958])

# bias 1
B1 = [-0.4939, 0.189]


B2 = np.array([0.6358])

# learning rate 
learning_rate = 0.75
leak_factor = 0.5

# Expected output from systolic array (Z1 pre bias):
# [-0.5614  1.0294]
# [-0.5792  0.4234]
# [ 0.2985  0.0913]
# [-0.2807  0.5147]

# Expected output from VPU (H1):
# [-0.5277  1.2184]
# [-0.5366  0.6124]
# [-0.0977  0.2803]
# [-0.3873  0.7037]

# H2:
# [[0.7183]
#  [0.5344]
#  [0.6673]
#  [0.64  ]]

# dL/dZ1:
# [[ 0.0946  0.1062]
#  [-0.0613 -0.0689]
#  [-0.0438 -0.0492]
#  [ 0.0843  0.0947]]

@cocotb.test()
async def test_tpu_scores(dut): 
    
    # Create a clock
    clock = Clock(dut.clk, 10, units="ns")
    cocotb.start_soon(clock.start())

    events = {"sys": [], "bias": [], "lr": [], "loss": [], "lrd": [], "hcache": [], "vpu": [], "gd": [], "ub_writes": [], "rdcmd": [], "stream": [], "cyc": [0]}
    async def monitor():
        UB = lambda: [ (int(dut.ub_flat.value) >> (16*i)) & 0xffff for i in range(64) ]
        prev_wr = None
        prev_rd = None
        while True:
            await RisingEdge(dut.clk)
            events["cyc"][0] += 1
            cyc = events["cyc"][0]
            events.setdefault("mon", []).append([cyc,
                int(dut.dbg_bias_in_1.value), int(dut.dbg_bias_in_2.value),
                int(dut.dbg_bias_scalar_1.value), int(dut.dbg_bias_scalar_2.value),
                int(dut.dbg_lr_in_1.value), int(dut.dbg_lr_in_2.value), int(dut.dbg_lr_leak.value),
                int(dut.dbg_loss_in_1.value), int(dut.dbg_loss_in_2.value),
                int(dut.dbg_loss_Y_1.value), int(dut.dbg_loss_Y_2.value), int(dut.dbg_loss_inv.value),
                int(dut.dbg_lrd_in_1.value), int(dut.dbg_lrd_in_2.value),
                int(dut.dbg_lrd_H_1.value), int(dut.dbg_lrd_H_2.value),
                int(dut.dbg_gd_valid_0.value), int(dut.dbg_grad_0.value), int(dut.dbg_old_0.value),
                int(dut.dbg_gd_valid_1.value), int(dut.dbg_grad_1.value), int(dut.dbg_old_1.value),
                int(dut.dbg_gd_done_0.value), int(dut.dbg_gd_upd_0.value),
                int(dut.dbg_gd_done_1.value), int(dut.dbg_gd_upd_1.value),
                int(dut.dbg_gd_bw.value), int(dut.dbg_gd_ptr.value)])
            sv = [int(dut.u_tpu.ub_inst.ub_rd_input_valid_out_0.value), int(dut.u_tpu.ub_inst.ub_rd_input_data_out_0.value), int(dut.u_tpu.ub_inst.ub_rd_input_valid_out_1.value), int(dut.u_tpu.ub_inst.ub_rd_input_data_out_1.value)]
            wv = [int(dut.u_tpu.ub_inst.ub_rd_weight_valid_out_0.value), int(dut.u_tpu.ub_inst.ub_rd_weight_data_out_0.value), int(dut.u_tpu.ub_inst.ub_rd_weight_valid_out_1.value), int(dut.u_tpu.ub_inst.ub_rd_weight_data_out_1.value)]
            if sv[0] or sv[2] or wv[0] or wv[2]:
                events["stream"].append([cyc, sv, wv])
            pe = [int(dut.dbg_w11.value), int(dut.dbg_w12.value), int(dut.dbg_w21.value), int(dut.dbg_w22.value),
                  int(dut.dbg_pe_en.value), int(dut.dbg_start1.value), int(dut.dbg_start2.value),
                  int(dut.dbg_switch.value), int(dut.dbg_accept1.value), int(dut.dbg_accept2.value),
                  int(dut.dbg_pev11.value), int(dut.dbg_pev12.value)]
            if any(pe[5:10]) or pe[0] or pe[1] or pe[2] or pe[3]:
                events.setdefault("pe", []).append([cyc] + pe)
            t = int(dut.ub_flat.value)
            ub = [ (t >> (16*i)) & 0xffff for i in range(64) ]
            if int(dut.dbg_sys_valid_21.value) or int(dut.dbg_sys_valid_22.value):
                events["sys"].append([cyc, int(dut.dbg_sys_valid_21.value), int(dut.dbg_sys_data_21.value), int(dut.dbg_sys_valid_22.value), int(dut.dbg_sys_data_22.value)])
            if int(dut.dbg_bias_valid_1.value) or int(dut.dbg_bias_valid_2.value):
                events["bias"].append([cyc, int(dut.dbg_bias_valid_1.value), int(dut.dbg_bias_z_1.value), int(dut.dbg_bias_valid_2.value), int(dut.dbg_bias_z_2.value)])
            if int(dut.dbg_lr_valid_1.value) or int(dut.dbg_lr_valid_2.value):
                events["lr"].append([cyc, int(dut.dbg_lr_valid_1.value), int(dut.dbg_lr_1.value), int(dut.dbg_lr_valid_2.value), int(dut.dbg_lr_2.value)])
            if int(dut.dbg_loss_valid_1.value) or int(dut.dbg_loss_valid_2.value):
                events["loss"].append([cyc, int(dut.dbg_loss_valid_1.value), int(dut.dbg_loss_1.value), int(dut.dbg_loss_valid_2.value), int(dut.dbg_loss_2.value)])
            if int(dut.dbg_lrd_valid_1.value) or int(dut.dbg_lrd_valid_2.value):
                events["lrd"].append([cyc, int(dut.dbg_lrd_valid_1.value), int(dut.dbg_lrd_1.value), int(dut.dbg_lrd_valid_2.value), int(dut.dbg_lrd_2.value)])
            if int(dut.dbg_hcache_1.value) or int(dut.dbg_hcache_2.value):
                events["hcache"].append([cyc, int(dut.dbg_hcache_1.value), int(dut.dbg_hcache_2.value)])
            if int(dut.dbg_vpu_valid_1.value) or int(dut.dbg_vpu_valid_2.value):
                events["vpu"].append([cyc, int(dut.dbg_vpu_valid_1.value), int(dut.dbg_vpu_out_1.value), int(dut.dbg_vpu_valid_2.value), int(dut.dbg_vpu_out_2.value)])
            if int(dut.dbg_gd_done_0.value) or int(dut.dbg_gd_done_1.value):
                events["gd"].append([cyc, int(dut.dbg_gd_done_0.value), int(dut.dbg_gd_upd_0.value), int(dut.dbg_gd_done_1.value), int(dut.dbg_gd_upd_1.value), int(dut.dbg_old_0.value), int(dut.dbg_old_1.value), int(dut.dbg_grad_0.value), int(dut.dbg_grad_1.value), int(dut.dbg_gd_bw.value), int(dut.dbg_gd_ptr.value)])
            if events["gd"] or events["sys"]:
                pass
            w = int(dut.dbg_wr_ptr.value)
            if prev_wr is not None and w != prev_wr:
                events["ub_writes"].append([cyc, w])
            prev_wr = w
            rd = [int(dut.ub_rd_start_in.value), int(dut.ub_rd_transpose.value), int(dut.ub_ptr_select.value), int(dut.ub_rd_addr_in.value), int(dut.ub_rd_row_size.value), int(dut.ub_rd_col_size.value)]
            if prev_rd is not None and rd != prev_rd:
                events["rdcmd"].append([cyc, rd])
            prev_rd = rd
        # unreachable
    ct = cocotb.start_soon(monitor())


    # rst the DUT (device under test)
    dut.rst.value = 1
    dut.ub_wr_host_data_in[0].value = 0
    dut.ub_wr_host_data_in[1].value = 0
    dut.ub_wr_host_valid_in[0].value = 0
    dut.ub_wr_host_valid_in[1].value = 0
    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.learning_rate_in.value = 0
    dut.vpu_data_pathway.value = 0
    dut.sys_switch_in.value = 0
    dut.vpu_leak_factor_in.value = 0
    dut.inv_batch_size_times_two_in.value = 0
    await RisingEdge(dut.clk)

    dut.rst.value = 0
    dut.learning_rate_in.value = to_fixed(learning_rate)
    dut.vpu_leak_factor_in.value = to_fixed(leak_factor)
    dut.inv_batch_size_times_two_in.value = to_fixed(2/len(X))
    await RisingEdge(dut.clk)

    # Load X, Y, W1, B1, W2, B2 (in that order)
    dut.ub_wr_host_data_in[0].value = to_fixed(X[0][0])
    dut.ub_wr_host_valid_in[0].value = 1
    await RisingEdge(dut.clk)

    for i in range(len(X) - 1):
        dut.ub_wr_host_data_in[0].value = to_fixed(X[i + 1][0])
        dut.ub_wr_host_valid_in[0].value = 1
        dut.ub_wr_host_data_in[1].value = to_fixed(X[i][1])
        dut.ub_wr_host_valid_in[1].value = 1
        await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = to_fixed(Y[0])
    dut.ub_wr_host_valid_in[0].value = 1
    dut.ub_wr_host_data_in[1].value = to_fixed(X[3][1])
    dut.ub_wr_host_valid_in[1].value = 1
    await RisingEdge(dut.clk)

    for i in range(len(Y) - 1):
        dut.ub_wr_host_data_in[0].value = to_fixed(Y[i + 1])
        dut.ub_wr_host_valid_in[0].value = 1
        dut.ub_wr_host_data_in[1].value = 0
        dut.ub_wr_host_valid_in[1].value = 0
        await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = to_fixed(W1[0][0])
    dut.ub_wr_host_valid_in[0].value = 1
    dut.ub_wr_host_data_in[1].value = 0
    dut.ub_wr_host_valid_in[1].value = 0
    await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = to_fixed(W1[1][0])
    dut.ub_wr_host_valid_in[0].value = 1
    dut.ub_wr_host_data_in[1].value = to_fixed(W1[0][1])
    dut.ub_wr_host_valid_in[1].value = 1
    await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = to_fixed(B1[0])
    dut.ub_wr_host_valid_in[0].value = 1
    dut.ub_wr_host_data_in[1].value = to_fixed(W1[1][1])
    dut.ub_wr_host_valid_in[1].value = 1
    await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = to_fixed(W2[0])
    dut.ub_wr_host_valid_in[0].value = 1
    dut.ub_wr_host_data_in[1].value = to_fixed(B1[1])
    dut.ub_wr_host_valid_in[1].value = 1
    await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = to_fixed(B2[0])
    dut.ub_wr_host_valid_in[0].value = 1
    dut.ub_wr_host_data_in[1].value = to_fixed(W2[1])
    dut.ub_wr_host_valid_in[1].value = 1
    await RisingEdge(dut.clk)

    dut.ub_wr_host_data_in[0].value = 0
    dut.ub_wr_host_valid_in[0].value = 0
    dut.ub_wr_host_data_in[1].value = 0
    dut.ub_wr_host_valid_in[1].value = 0
    await RisingEdge(dut.clk)


    # Load W1^T into systolic array (reading W1 from UB to top of systolic array)
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 1
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 12
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # EXPERIMENT: delay switch until weight load is fully accepted
    for _ in range(2):
        dut.ub_rd_start_in.value = 0
        dut.sys_switch_in.value = 0
        await RisingEdge(dut.clk)
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)
    # Load X into systolic array (reading X from UB to left side of systolic array)
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 2
    dut.vpu_data_pathway.value = 0b1100     # Set VPU datapathway to do forward pass
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)
    
    # Read B1 from UB for 4 clock cycles
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 2
    dut.ub_rd_addr_in.value = 16
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 2
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await wait_vpu_output_done(dut)  # wait until last value of vpu is done

    # Load in W2^T
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 1
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 18
    dut.ub_rd_row_size.value = 1
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Load in H1
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 21
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 2
    dut.vpu_data_pathway.value = 0b1111     # Set VPU datapathway to the transition pathway from forward pass to backward pass
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)

    # Read B2 from UB for 4 clock cycles because we have a batch size of 4
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 2
    dut.ub_rd_addr_in.value = 20
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 1
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Reading Y values for the loss modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 3
    dut.ub_rd_addr_in.value = 8
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 1
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Read biases (B2) from UB to gradient descent modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 5
    dut.ub_rd_addr_in.value = 20
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 1
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    await wait_vpu_output_done(dut)

    # Load in W2 from UB to top of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 18
    dut.ub_rd_row_size.value = 1
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Load in dL/dZ from UB to left side of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 29
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 1
    dut.vpu_data_pathway.value = 0b0001
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)

    # Read H1 from UB to VPU (activation derivative modules) for 4 clock cycles
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 4
    dut.ub_rd_addr_in.value = 21
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 2
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    # Read biases (B1) from UB to gradient descent modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 5
    dut.ub_rd_addr_in.value = 16
    dut.ub_rd_row_size.value = 4
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await wait_vpu_output_done(dut)

    # NOW CALCULATING LEAF NODES (Weight gradients, requires tiling)
    
    # Calculating W1 gradients (W1 before W2)
    # Load first X inputs tile into top of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Load first (dL/dZ1)^T tile into left side of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 1
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 33
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    dut.vpu_data_pathway.value = 0b0000
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)

    # Read weights (W1) from UB to gradient descent modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 6
    dut.ub_rd_addr_in.value = 12
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await wait_vpu_output_done(dut)

    # Load second H1 tile into top of systolic array (we are calculating dL/dW2 first)
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 4
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Load second (dL/dZ1)^T tile into left side of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 1
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 37
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    dut.vpu_data_pathway.value = 0b0000
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)

    # Read weights (W1) from UB to gradient descent modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 6
    dut.ub_rd_addr_in.value = 12
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await wait_vpu_output_done(dut)

    # Now calculating W2 gradients
    # Load first H1 tile into top of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 21
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Load first (dL/dZ2)^T tile into left side of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 1
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 29
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 1
    dut.vpu_data_pathway.value = 0b0000
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)

    # Read weights (W2) from UB to gradient descent modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 6
    dut.ub_rd_addr_in.value = 18
    dut.ub_rd_row_size.value = 1
    dut.ub_rd_col_size.value = 2
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await wait_vpu_output_done(dut)

    # Load second H1 tile into top of systolic array (we are calculating dL/dW2 first)
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 1
    dut.ub_rd_addr_in.value = 25
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 2
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await RisingEdge(dut.clk)

    # Load second (dL/dZ2)^T tile into left side of systolic array
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 1
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 31
    dut.ub_rd_row_size.value = 2
    dut.ub_rd_col_size.value = 1
    dut.vpu_data_pathway.value = 0b0000
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    dut.sys_switch_in.value = 1
    await RisingEdge(dut.clk)

    # Read weights (W2) from UB to gradient descent modules in VPU
    dut.ub_rd_start_in.value = 1
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 6
    dut.ub_rd_addr_in.value = 18
    dut.ub_rd_row_size.value = 1
    dut.ub_rd_col_size.value = 2
    dut.sys_switch_in.value = 0
    await RisingEdge(dut.clk)

    dut.ub_rd_start_in.value = 0
    dut.ub_rd_transpose.value = 0
    dut.ub_ptr_select.value = 0
    dut.ub_rd_addr_in.value = 0
    dut.ub_rd_row_size.value = 0
    dut.ub_rd_col_size.value = 0
    await wait_vpu_output_done(dut)



    await ClockCycles(dut.clk, 10)
    t = int(dut.ub_flat.value)
    ub = [s16((t >> (16*i)) & 0xffff) for i in range(64)]

    # ---------------- scoreboard ----------------
    g = golden()
    checks = {}

    def ck(name):
        checks[name] = checks.get(name, 0) + 1

    # 1. Host load: X/Y words keep their Q8.8 golden values to the end of the
    # run (the parameter words 12..20 are rewritten by the SGD step and are
    # checked against the golden trajectory below).
    host = [s16(v) for v in HOST_UB]
    assert ub[0:12] == host[0:12], (
        "host UB X/Y load mismatch: RTL vs golden\nRTL   %r\nGOLD  %r"
        % (ub[0:12], host[0:12]))
    ck("host_ub")

    # 2. Layer-1 forward: bias + leaky-ReLU of all four XOR inputs (UB 21..28)
    h1 = [s16(v) for row in g["H1"] for v in row]
    assert ub[21:29] == h1, (
        "forward layer-1 mismatch: RTL vs golden Q8.8\nRTL   %r\nGOLD  %r"
        % (ub[21:29], h1))
    ck("forward_h1")

    mon = {e[0]: e for e in events["mon"]}
    B_IN1, B_IN2, B_SC1, B_SC2 = 1, 2, 3, 4
    LR1, LR2, LEAK = 5, 6, 7
    L_IN1, L_IN2, L_Y1, L_Y2, L_INV = 8, 9, 10, 11, 12
    D_IN1, D_IN2, D_H1, D_H2 = 13, 14, 15, 16

    # 3. bias_child arith: z(t) = fxp_add(sys(t-1), bias_ub(t-1))
    for e in events["bias"]:
        prev = mon.get(e[0] - 1)
        if prev is None:
            continue
        if e[1]:
            assert s16(e[2]) == fadd(s16(prev[B_IN1]), s16(prev[B_SC1])), (e[0], "bias0")
            ck("bias")
        if e[3]:
            assert s16(e[4]) == fadd(s16(prev[B_IN2]), s16(prev[B_SC2])), (e[0], "bias1")
            ck("bias")

    # 4. leaky_relu_child arith: x>=0 ? x : fxp_mul(x, leak)
    for e in events["lr"]:
        prev = mon.get(e[0] - 1)
        if prev is None:
            continue
        if e[1]:
            assert s16(e[2]) == leaky(s16(prev[LR1]), s16(prev[LEAK])), (e[0], "lr0")
            ck("leaky_relu")
        if e[3]:
            assert s16(e[4]) == leaky(s16(prev[LR2]), s16(prev[LEAK])), (e[0], "lr1")
            ck("leaky_relu")

    # 5. loss_child arith: (2/N) * (H - Y)
    for e in events["loss"]:
        prev = mon.get(e[0] - 1)
        if prev is None:
            continue
        if e[1]:
            exp = fmul(fsub(s16(prev[L_IN1]), s16(prev[L_Y1])), s16(prev[L_INV]))
            assert s16(e[2]) == exp, (e[0], "loss0", s16(e[2]), exp)
            ck("loss_gradient")
        if e[3]:
            exp = fmul(fsub(s16(prev[L_IN2]), s16(prev[L_Y2])), s16(prev[L_INV]))
            assert s16(e[4]) == exp, (e[0], "loss1", s16(e[4]), exp)
            ck("loss_gradient")

    # 6. leaky_relu_derivative_child arith: H>=0 ? x : fxp_mul(x, leak)
    for e in events["lrd"]:
        prev = mon.get(e[0] - 1)
        if prev is None:
            continue
        if e[1]:
            exp = (s16(prev[D_IN1]) if s16(prev[D_H1]) >= 0
                   else fmul(s16(prev[D_IN1]), s16(prev[LEAK])))
            assert s16(e[2]) == exp, (e[0], "lrd0")
            ck("leaky_relu_derivative")
        if e[3]:
            exp = (s16(prev[D_IN2]) if s16(prev[D_H2]) >= 0
                   else fmul(s16(prev[D_IN2]), s16(prev[LEAK])))
            assert s16(e[4]) == exp, (e[0], "lrd1")
            ck("leaky_relu_derivative")

    # 7. gradient_descent arith and SGD trajectory into the UB parameter words
    V0, G0, O0, V1, G1, O1 = 17, 18, 19, 20, 21, 22
    DN0, U0, DN1, U1, BW, PTR = 23, 24, 25, 26, 27, 28
    exp_ub = host + [0] * (64 - 21)
    prev = None
    for e in events["mon"]:
        if prev is not None:
            # writes performed at this clock edge from the previous cycle's state
            if prev[BW]:
                p = prev[PTR]
                for i in (1, 0):
                    if prev[DN0 if i == 0 else DN1]:
                        exp_ub[p] = s16(prev[U0 if i == 0 else U1])
                        p += 1
            else:
                for i in (0, 1):
                    if prev[DN0 if i == 0 else DN1]:
                        exp_ub[prev[PTR] + i] = s16(prev[U0 if i == 0 else U1])
            # registered update from the previous cycle's valid gradient
            for i, (v, gr, old, dn, up) in enumerate((
                    (V0, G0, O0, DN0, U0), (V1, G1, O1, DN1, U1))):
                if prev[v]:
                    sub_a = s16(prev[up]) if (prev[BW] == 0 and prev[dn]) else s16(prev[old])
                    exp = fsub(sub_a, fmul(s16(prev[gr]), LRQ))
                    got = s16(e[up])
                    assert got == exp, (e[0], "gd", i, got, exp)
                    ck("sgd_update")
        prev = e
    assert ub[0:21] == exp_ub[0:21], (
        "UB parameter words after SGD mismatch\nRTL   %r\nGOLD  %r"
        % (ub[0:21], exp_ub[0:21]))
    ck("sgd_ub")

    # 8. every stage above must have been exercised
    for stage in ("host_ub", "forward_h1", "bias", "leaky_relu", "loss_gradient",
                  "leaky_relu_derivative", "sgd_update", "sgd_ub"):
        assert checks.get(stage, 0) > 0, "scoreboard stage never exercised: " + stage
    print("SCOREBOARD_CHECKS", json.dumps(checks))
    print("UB_PARAMS", json.dumps(ub[12:20]))
    out = os.environ.get("LADDER_SCOREBOARD_OUT")
    if out:
        with open(out, "w") as fh:
            json.dump({"checks": checks, "ub_params": ub[12:20],
                       "forward_h1": ub[21:29]}, fh)

