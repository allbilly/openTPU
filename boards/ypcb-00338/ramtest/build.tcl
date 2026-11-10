set out [file normalize [lindex $argv 0]]
set_param general.maxThreads 4
proc stage {out value} {
    set f [open $out/stage.txt w]; puts $f $value; close $f
    puts "RAMTEST_STAGE=$value"
}
if {[catch {
    create_project ypcb_ramtest $out/project -part xc7k480tffg1156-2 -force
    read_ip $out/ip/otpu_mig_ddr3/otpu_mig_ddr3.xci
    set_property generate_synth_checkpoint false [get_files *.xci]
    add_files -norecurse [glob $out/source/*.sv]
    add_files -norecurse [glob $out/source/traffic_gen/*.v]
    set_property top ypcb_ramtest_mig [get_filesets sources_1]
    add_files -fileset constrs_1 -norecurse [list $out/source/ramtest.xdc $out/source/ramtest_cdc.tcl]
    set_property PROCESSING_ORDER LATE [get_files ramtest_cdc.tcl]
    set_property USED_IN_SYNTHESIS false [get_files ramtest_cdc.tcl]
    update_compile_order -fileset sources_1
    file mkdir $out/reports
    stage $out SYNTHESIS_RUNNING
    launch_runs synth_1 -jobs 4
    wait_on_run synth_1
    if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "RAM-only synthesis failed"}
    set_property strategy Performance_Explore [get_runs impl_1]
    set_property STEPS.POST_ROUTE_PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
    stage $out IMPLEMENTATION_RUNNING
    launch_runs impl_1 -jobs 4
    wait_on_run impl_1
    if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "RAM-only implementation failed"}
    open_run impl_1
    foreach {ref expected} {PCIE_2_1 0 GTXE2_CHANNEL 0 BSCANE2 1 ISERDESE2 144 OSERDESE2 210 IDELAYE2 144 PHASER_IN_PHY 18 PHASER_OUT_PHY 24} {
        set count [llength [get_cells -hier -filter "REF_NAME == $ref"]]
        if {$count != $expected} {error "Unexpected $ref count: $count, expected $expected"}
    }
    report_timing_summary -report_unconstrained -max_paths 30 -file $out/reports/timing.rpt
    report_route_status -file $out/reports/route.rpt
    report_drc -file $out/reports/drc.rpt
    report_cdc -details -file $out/reports/cdc.rpt
    report_bus_skew -file $out/reports/bus_skew.rpt
    report_io -file $out/reports/io.rpt
    report_utilization -hierarchical -file $out/reports/utilization.rpt
    set setup [get_timing_paths -delay_type max -max_paths 1]
    set hold [get_timing_paths -delay_type min -max_paths 1]
    if {![llength $setup] || ![llength $hold]} {error "Missing timing paths"}
    if {[get_property SLACK $setup] < 0 || [get_property SLACK $hold] < 0} {error "RAM-only timing failed"}
    set f [open $out/reports/timing.rpt]; set timing [read $f]; close $f
    if {![regexp {All user specified timing constraints are met} $timing]} {error "Timing summary has violations"}
    set violations [get_drc_violations -quiet -filter {SEVERITY == Error || SEVERITY == {Critical Warning}}]
    if {[llength $violations]} {error "Blocking RAM-only DRC violations: $violations"}
    write_checkpoint -force $out/routed.dcp
    stage $out WRITING_BITSTREAM
    write_bitstream -force $out/ramtest.bit
    stage $out BITSTREAM_BUILT_PHYSICAL_TESTS_PENDING
} message]} {
    stage $out FAILED
    puts stderr $message
    exit 1
}
exit 0
