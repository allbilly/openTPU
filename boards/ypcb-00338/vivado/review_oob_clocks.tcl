# Analyze the Gen2 x8 XDMA OOB divider clocks in an opened routed design.
# This adds analysis clocks only: no netlist, placement or routing changes.
# The caller supplies an existing fresh result directory in the variable out.
set regs [lsort [get_cells -hier -filter {NAME =~ */oobclk_div.oobclk_reg}]]
if {[llength $regs] != 8} {error "Expected eight PCIe OOB output registers"}
set f [open $out/oob-clocks.tsv w]
set x [open $out/oob-generated.xdc w]
set lane 0
foreach reg $regs {
    if {[get_property REF_NAME $reg] ne "FDRE"} {error "OOB register type differs"}
    set c [get_pins $reg/C]
    set q [get_pins $reg/Q]
    if {[llength [get_clocks -quiet -of_objects $q]]} {
        error "Unexpected pre-existing OOB output clock"
    }
    set masters [get_clocks -quiet -of_objects $c]
    if {[llength $masters] != 2} {error "Expected both 125/250 MHz OOB master clocks"}
    set periods {}
    foreach master $masters {
        set p [get_property PERIOD $master]
        lappend periods [format %.3f $p]
        if {abs($p - 4.0) > 0.0001 && abs($p - 8.0) > 0.0001} {
            error "Unexpected OOB source period: $p"
        }
        foreach divider {2 4} {
            # Cover both counter-bit selections for both masters, including
            # mode-transition combinations rather than only paired steady modes.
            set name otpu_oob_lane${lane}_master[lindex [split $master /] end]_div$divider
            create_generated_clock -name $name -add -source $c -master_clock $master \
                -divide_by $divider $q
            puts $f "$reg\t$master\t$p\t$divider\t$name\t[get_property PERIOD [get_clocks $name]]"
            puts $x "create_generated_clock -name [list $name] -add -source \[get_pins [list $c]\] -master_clock [list $master] -divide_by $divider \[get_pins [list $q]\]"
        }
    }
    if {[lsort $periods] ne {4.000 8.000}} {error "Missing OOB master frequency"}
    incr lane
}
close $f
close $x
report_timing_summary -report_unconstrained -file $out/oob-timing.rpt
check_timing -override_defaults {pulse_width_clock} -verbose -file $out/oob-pulse-clock-pins.rpt
report_bus_skew -file $out/oob-bus-skew.rpt
report_clocks -file $out/oob-clocks.rpt
report_cdc -details -file $out/oob-cdc.rpt
report_route_status -file $out/oob-route.rpt
