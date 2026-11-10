
set dcp [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
set_param general.maxThreads 2
open_checkpoint $dcp
set f [open $out/facts.tsv w]
foreach group {{aw 0 0} {aw 1 1} {w 0 2} {w 1 3} {b 0 4} {b 1 5} {ar 0 6} {ar 1 7} {r 0 8} {r 1 9}} {
    lassign $group channel counter index
    set source_base [format {u_ld/%s_cdc_cdc_graycounter%d_q_reg} $channel $counter]
    set dest_base [format {u_ld/xilinxmultiregimpl%d_regs0_reg} $index]
    set next_base [format {u_ld/xilinxmultiregimpl%d_regs1_reg} $index]
    set sources {}; set destinations {}; set source_periods {}; set dest_periods {}
    for {set bit 0} {$bit < 3} {incr bit} {
        set sname [format {%s[%d]} $source_base $bit]
        set dname [format {%s[%d]} $dest_base $bit]
        set nname [format {%s[%d]} $next_base $bit]
        set src [get_cells -quiet [list $sname]]
        set dst [get_cells -quiet [list $dname]]
        set nxt [get_cells -quiet [list $nname]]
        if {[llength $src] != 1 || [llength $dst] != 1 || [llength $nxt] != 1} {
            error "Missing exact pointer/synchronizer cells: $sname $dname $nname"
        }
        foreach cell [concat $dst $nxt] {
            if {![get_property ASYNC_REG $cell]} {error "Synchronizer lacks ASYNC_REG: $cell"}
        }
        foreach pair [list [list $src $dst] [list $dst $nxt]] {
            lassign $pair launch capture
            set pin [get_pins -of_objects $capture -filter {REF_PIN_NAME == D}]
            set actual [lsort [all_fanin -flat -startpoints_only -to $pin]]
            set expected [get_pins -of_objects $launch -filter {REF_PIN_NAME == C}]
            if {[llength $actual] != 1 || [llength $expected] != 1 ||
                [lindex $actual 0] ne [lindex $expected 0]} {
                error "Unexpected synchronizer fanin: $capture $actual, expected $expected"
            }
            puts $f "FANIN\t$capture\t$actual"
        }
        set sc [get_clocks -of_objects [get_pins -of_objects $src -filter {REF_PIN_NAME == C}]]
        set dc [get_clocks -of_objects [get_pins -of_objects $dst -filter {REF_PIN_NAME == C}]]
        if {[llength $sc] != 1 || [llength $dc] != 1} {error "Ambiguous pointer clock"}
        lappend source_periods [get_property PERIOD $sc]
        lappend dest_periods [get_property PERIOD $dc]
        lappend sources $src
        lappend destinations $dst
        puts $f "BIT\t$channel\t$counter\t$bit\t$src\t$dst\t$sc\t$dc"
    }
    if {[llength [lsort -unique $source_periods]] != 1 || [llength [lsort -unique $dest_periods]] != 1} {
        error "Mixed pointer clock periods"
    }
    set budget [expr {min([lindex $source_periods 0], [lindex $dest_periods 0])}]
    if {$budget <= 0} {error "Invalid pointer period"}
    set_bus_skew -from $sources -to $destinations $budget
    puts $f "GROUP\t$channel\t$counter\t$index\t$budget\t[lindex $source_periods 0]\t[lindex $dest_periods 0]"
}
close $f
report_bus_skew -warn_on_violation -file $out/bus-skew.rpt
report_route_status -file $out/route.rpt
close_design
exit
