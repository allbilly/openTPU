"""Ladder harness package: the per-step glue between RTL simulations and the golden models.

Step 4 adds `mini`, the mini-core runner (rtl/ladder/, sim/ladder/tb_mini.sv) that compares
bit-exactly against opentpu.isasim; step 9 adds `prod`, the production-core harness
(rtl/, sim/verilator/, opentpu/rtlsim.py) that runs the same hand-assembled programs on the
real RTL.  Later rungs add their own modules next to them.
"""
