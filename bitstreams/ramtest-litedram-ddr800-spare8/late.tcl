
create_clock -name jtag_tck -period 166.666667 [get_pins u_status/u_bscan/TCK]
foreach name {rq_sync rs_sync} {
    set all [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${name}_reg*"]
    set first {}
    foreach c $all {if {[regexp {\[0\]$} [get_property NAME $c]]} {lappend first $c}}
    if {[llength $all] != 3 || [llength $first] != 1} {error "Missing mailbox synchronizer $name"}
    set_property ASYNC_REG TRUE $all
    set_property DONT_TOUCH TRUE $all
    set_false_path -to [get_pins -of_objects $first -filter {REF_PIN_NAME == D}]
}
foreach {from_name to_name bound} {held req 20.000 response response_tck 166.666667} {
    set source [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${from_name}_reg*"]
    set target [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${to_name}_reg*"]
    if {![llength $source] || ![llength $target]} {error "Missing held mailbox payload"}
    set_max_delay -datapath_only -from $source -to $target $bound
    set_bus_skew -from $source -to $target $bound
}
set core [get_clocks -of_objects [get_pins u_ld/MMCME2_ADV/CLKOUT0]]
if {[llength $core] != 1 || abs([get_property PERIOD $core]-10.0)>0.001} {error "DDR800 sys clock differs"}
set regs50 [filter [all_registers -clock sys_clk_50] {NAME =~ u_ld/*}]
if {[llength $regs50] != 16} {error "LiteDRAM clock-reset chain count changed"}
set_false_path -from $core -to $regs50

# Apply after synthesis and the board oscillator clock. During an earlier
# read_xdc these generated clocks did not yet exist, losing the uncertainty.
set phase_constraints [open $out/phase-clock-constraints.tsv w]
foreach ch {0 1} {
    set sys [get_clocks -of_objects [get_pins u_ld/ldmmcm${ch}/CLKIN1]]
    set shifted [get_clocks -of_objects [get_pins u_ld/ldmmcm${ch}/CLKOUT0]]
    if {[llength $sys]!=1 || [llength $shifted]!=1} {error "DDR phase clock missing"}
    foreach mode {setup hold} {
        set_clock_uncertainty -$mode -from $sys -to $shifted 1.000
        set_clock_uncertainty -$mode -from $shifted -to $sys 1.000
        puts $phase_constraints "$ch\t$mode\t$sys\t$shifted\t1.000"
        puts $phase_constraints "$ch\t$mode\t$shifted\t$sys\t1.000"
    }
}
close $phase_constraints
