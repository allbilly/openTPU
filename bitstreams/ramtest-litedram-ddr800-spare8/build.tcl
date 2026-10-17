
set out [file normalize [lindex $argv 0]]
set_param general.maxThreads 2
if {[llength $argv] > 1} {
open_checkpoint [lindex $argv 1]
} else {
create_project ramtest_litedram $out/project -part xc7k480tffg1156-2 -force
read_verilog $out/core/otpu_litedram.v
add_files -norecurse $out/core/otpu_litedram_mem.init
set_property FILE_TYPE {Memory Initialization Files} [get_files otpu_litedram_mem.init]
foreach f [glob $out/source/*.sv] {read_verilog -sv $f}
foreach f [glob $out/source/traffic_gen/*.v] {read_verilog $f}
read_xdc $out/core/otpu_litedram.xdc
read_xdc $out/board.xdc
set_property verilog_define {SYNTHESIS} [current_fileset]
set_property top ypcb_ramtest_litedram [current_fileset]
synth_design -top ypcb_ramtest_litedram -part xc7k480tffg1156-2 -flatten_hierarchy rebuilt -retiming
write_checkpoint -force $out/synth.dcp
}
source $out/late.tcl
opt_design -directive Explore
place_design -directive Explore
phys_opt_design -directive AggressiveExplore
route_design -directive Explore -tns_cleanup
phys_opt_design -directive AggressiveExplore
file mkdir $out/reports
report_timing_summary -report_unconstrained -file $out/reports/timing.rpt
report_route_status -file $out/reports/route.rpt
report_drc -file $out/reports/drc.rpt
report_cdc -details -file $out/reports/cdc.rpt
report_bus_skew -file $out/reports/bus_skew.rpt
report_io -file $out/reports/io.rpt
report_clocks -file $out/reports/clocks.rpt
report_utilization -hierarchical -file $out/reports/utilization.rpt
foreach {ref expected} {PCIE_2_1 0 GTXE2_CHANNEL 0 BSCANE2 1 DSP48E1 0 ISERDESE2 136 OSERDESE2 205 IDELAYE2 136 PHASER_IN_PHY 0 PHASER_OUT_PHY 0} {
    set count [llength [get_cells -hier -filter "REF_NAME == $ref"]]
    if {$count != $expected} {error "Unexpected primitive $ref: $count instead of $expected"}
}
foreach mode {max min} {
    set path [get_timing_paths -delay_type $mode -max_paths 1]
    if {![llength $path] || [get_property SLACK $path] < 0} {error "RAM-only LiteDRAM $mode timing failed"}
}
set f [open $out/reports/timing.rpt]; set timing [read $f]; close $f
if {![regexp {All user specified timing constraints are met} $timing]} {error "Timing summary has violations"}
foreach violation [get_drc_violations -quiet] {
    if {[get_property SEVERITY $violation] in {Error {Critical Warning}}} {error "Blocking DRC: $violation"}
}
write_checkpoint -force $out/routed.dcp
write_bitstream -force $out/ramtest.bit
close_project
exit
