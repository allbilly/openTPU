
set bscan [get_cells -quiet -hier -filter {REF_NAME == BSCANE2}]
if {[llength $bscan] != 1 || [get_property JTAG_CHAIN $bscan] != 2} {error "Expected one USER2 primitive"}
create_clock -name jtag_tck -period 166.666667 [get_pins $bscan/TCK]
set core [get_clocks -of_objects [get_pins u_sys/u_ch0/clk]]
if {[llength $core] != 1} {error "Missing combined core clock"}
set tcore [get_property PERIOD $core]
foreach {source target bound} [list held req [expr {2*$tcore}] response response_tck 333.333334] {
  set a [get_cells -quiet -hier -filter "NAME =~ u_mailbox/${source}_reg*"]
  set b [get_cells -quiet -hier -filter "NAME =~ u_mailbox/${target}_reg*"]
  if {![llength $a] || ![llength $b]} {error "Missing held mailbox payload"}
  set_max_delay -datapath_only $bound -from $a -to $b
  set_false_path -hold -from $a -to $b
  set_bus_skew $bound -from $a -to $b
}
foreach prefix {rq_sync rs_sync} {
  set cells [get_cells -quiet -hier -filter "NAME =~ u_mailbox/${prefix}_reg*"]
  set first [get_cells -quiet "u_mailbox/${prefix}_reg\[0\]"]
  if {[llength $cells]!=3 || [llength $first]!=1} {error "Missing mailbox toggle synchronizer"}
  set_property ASYNC_REG TRUE $cells
  set_property DONT_TOUCH TRUE $cells
  set_false_path -to [get_pins $first/D]
}
foreach name {u_host_reset/lock_sync u_host_reset/pcie_sync host_reset_sync} {
  set cells [get_cells -quiet -hier -filter "NAME =~ ${name}_reg*"]
  set first [get_cells -quiet "${name}_reg\[0\]"]
  if {[llength $cells]!=2 || [llength $first]!=1} {error "Missing host reset synchronizer: $name"}
  set_property ASYNC_REG TRUE $cells
  set_property DONT_TOUCH TRUE $cells
  set_false_path -to [get_pins $first/D]
}
