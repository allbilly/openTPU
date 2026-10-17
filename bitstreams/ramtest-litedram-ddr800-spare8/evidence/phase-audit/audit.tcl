
set build [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
set bound [lindex $argv 2]
set_param general.maxThreads 2
open_checkpoint $build/routed.dcp
set f [open $out/phase-clocks.tsv w]
foreach ch {0 1} {
    set sys [get_clocks -of_objects [get_pins u_ld/ldmmcm${ch}/CLKIN1]]
    set shifted [get_clocks -of_objects [get_pins u_ld/ldmmcm${ch}/CLKOUT0]]
    if {[llength $sys]!=1 || [llength $shifted]!=1} {error "Missing phase clock"}
    foreach mode {setup hold} {
        set_clock_uncertainty -$mode -from $sys -to $shifted $bound
        set_clock_uncertainty -$mode -from $shifted -to $sys $bound
        puts $f "$ch\t$mode\t$sys\t$shifted\t$bound"
        puts $f "$ch\t$mode\t$shifted\t$sys\t$bound"
    }
    foreach delay {max min} {
        report_timing -delay_type $delay -from $sys -to $shifted -max_paths 10 -file $out/ch${ch}-${delay}-to-shifted.rpt
        report_timing -delay_type $delay -from $shifted -to $sys -max_paths 10 -file $out/ch${ch}-${delay}-from-shifted.rpt
    }
}
close $f
report_timing_summary -report_unconstrained -file $out/timing.rpt
report_clocks -file $out/clocks.rpt
write_checkpoint $out/analyzed.dcp
close_design
exit
