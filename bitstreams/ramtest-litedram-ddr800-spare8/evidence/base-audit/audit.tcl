
set out [file normalize [lindex $argv 0]]
set reports [file normalize [lindex $argv 1]]
set_param general.maxThreads 2
open_checkpoint $out/routed.dcp
report_timing_summary -report_unconstrained -file $reports/timing.rpt
report_route_status -file $reports/route.rpt
report_io -file $reports/io.rpt
report_cdc -details -file $reports/cdc.rpt
report_bus_skew -file $reports/bus_skew.rpt
report_clocks -file $reports/clocks.rpt
report_drc -file $reports/drc.rpt
check_timing -override_defaults {no_input_delay no_output_delay} -verbose -file $reports/pad-coverage.rpt
set f [open $reports/facts.tsv w]
foreach ref {PCIE_2_1 GTXE2_CHANNEL BSCANE2 DSP48E1 ISERDESE2 OSERDESE2 IDELAYE2 PHASER_IN_PHY PHASER_OUT_PHY} {
    set cells [get_cells -hier -filter [format {REF_NAME == %s} $ref]]
    puts $f "RESOURCE\t$ref\t[llength $cells]"
}
foreach pin {u_ld/MMCME2_ADV/CLKOUT0 u_ld/PLLE2_ADV/CLKOUT0 u_ld/ldmmcm0/CLKOUT1 u_ld/ldmmcm1/CLKOUT1 u_status/u_bscan/TCK} {
    set clocks [get_clocks -of_objects [get_pins $pin]]
    if {[llength $clocks] != 1} {error "Clock count differs at $pin"}
    puts $f "CLOCK\t$pin\t[get_property PERIOD $clocks]"
}
foreach pin {u_ld/FDCE/D u_ld/FDCE_8/D} {
    foreach source [lsort [all_fanin -flat -startpoints_only -to [get_pins $pin]]] {
        puts $f "RESET_FANIN\t$pin\t$source"
    }
}
close $f
close_design
exit
