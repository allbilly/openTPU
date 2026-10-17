
set dcp [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
set_param general.maxThreads 2
open_checkpoint $dcp
set f [open $out/facts.tsv w]
foreach name {u_ld/FDCE/D u_ld/FDCE_8/D u_sys/u_board/cal_s1_reg[0]/D u_sys/u_board/cal_s1_reg[1]/D u_sys/u_board/cal_s2_reg[0]/D u_sys/u_board/cal_s2_reg[1]/D} {
    set pin [get_pins -quiet [list $name]]
    if {[llength $pin] != 1} {error "Expected exactly one routed pin: $name"}
    foreach source [lsort [all_fanin -flat -startpoints_only -to $pin]] {
        puts $f "FANIN\t$name\t$source"
    }
    set cell [get_cells -of_objects $pin]
    puts $f "CELL\t$name\t[get_property REF_NAME $cell]\t[get_property ASYNC_REG $cell]"
    foreach clock [get_clocks -of_objects [get_pins -of_objects $cell -filter {REF_PIN_NAME == C}]] {
        puts $f "CLOCK\t$name\t$clock\t[get_property PERIOD $clock]"
    }
}
close $f
report_cdc -details -file $out/cdc.rpt
report_exceptions -file $out/exceptions.rpt
check_timing -override_defaults {no_input_delay no_output_delay} -verbose -file $out/pad-coverage.rpt
close_design
exit
