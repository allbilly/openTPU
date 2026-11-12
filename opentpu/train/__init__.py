"""Training on openTPU: four trainers over one device, and the float64 references they are
tested against.

  `kernels`  the device's passes: linear fwd/dX/dW, the norms, SiLU/SwiGLU, attention, LoRA, and
             the TMEM transpose attention's backward needs
  `params`   fp32 master copies with their MX forms, AdamW, the losses
  `loop`     a SwiGLU block's step: two programs and their DRAM layout (`Trainer`)
  `lora`     a frozen base with two trainable adapters, int8 or QLoRA's 4-bit base
  `layers`   a whole transformer layer -- attention, an MLP, nine trainable groups -- and its
             float64 reference (`layer_ref`)
  `ref`      the block's float64 reference
  `cli`      `otpu-train`

`ref` is importable on its own and imports no framework: it is numpy float64, the ground truth
the device's fixed-point MM and fp32 VPU are tested against, as `opentpu/reference.py` is for
inference. The names below are re-exported so that a test or a script can read
`from opentpu.train import model_fwd_bwd` without depending on the trainer's modules, which are
heavier (they import the compiler and the simulator). `layers.layer_ref` is the whole layer's
equivalent, and it matches `torch.autograd` in float64 to ~1e-16 (`tests/test_train_layers.py`).
"""
from __future__ import annotations

from .ref import (  # noqa: F401
    adamw_step,
    linear_bwd,
    linear_fwd,
    model_fwd_bwd,
    mx_dequantize,
    mx_quantize,
    rmsnorm_bwd,
    rmsnorm_fwd,
    silu_bwd,
    silu_fwd,
    softmax_cross_entropy,
    swiglu_bwd,
    swiglu_bwd_full,
    swiglu_fwd,
)
