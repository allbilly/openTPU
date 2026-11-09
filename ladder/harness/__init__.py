"""Ladder harness package: the per-step glue between RTL simulations and the golden models.

Step 4 adds `mini`, the mini-core runner (rtl/ladder/, sim/ladder/tb_mini.sv) that compares
bit-exactly against opentpu.isasim; later rungs add their own modules next to it.
"""
