# USER2 mailbox: toggle synchronizers and held payloads, exact endpoints only.
create_clock -name jtag_tck -period 166.666667 [get_pins u_status/u_bscan/TCK]
foreach name {rq_sync rs_sync} {
    set all [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${name}_reg*"]
    set first {}
    foreach c $all {
        if {[regexp {\[0\]$} [get_property NAME $c]]} {lappend first $c}
    }
    if {[llength $all] != 3 || [llength $first] != 1} {error "Missing mailbox synchronizer $name"}
    set_false_path -to $first
}
foreach {from_name to_name bound} {held req 20.000 response response_tck 166.666667} {
    set source [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${from_name}_reg*"]
    set target [get_cells -quiet -hier -filter "NAME =~ *u_mailbox/${to_name}_reg*"]
    if {![llength $source] || ![llength $target]} {error "Missing mailbox held data $from_name/$to_name"}
    set_max_delay -datapath_only -from $source -to $target $bound
    set_bus_skew -from $source -to $target $bound
}
set ack [get_cells -quiet -hier -filter {NAME =~ *u_status/ack_s1_reg*}]
if {[llength $ack] != 2} {error "Missing snapshot acknowledgment synchronizers"}
set_false_path -to $ack
foreach ch {0 1} {
    set first [get_cells -quiet -hier -filter "NAME =~ *u_observer${ch}/request_sync_reg*0*"]
    if {[llength $first] != 1} {error "Missing channel $ch snapshot request synchronizer"}
    set_false_path -to $first
    set payload [get_cells -quiet -hier -filter "NAME =~ *u_observer${ch}/snapshot_reg*"]
    set target [get_cells -quiet -hier -filter {NAME =~ *u_status/response_data_reg*}]
    if {![llength $payload] || ![llength $target]} {error "Missing channel $ch snapshot payload"}
    set_max_delay -datapath_only -from $payload -to $target 20.000
    set_bus_skew -from $payload -to $target 20.000
}
