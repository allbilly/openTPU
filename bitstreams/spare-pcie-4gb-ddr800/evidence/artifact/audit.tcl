
set_param general.maxThreads 2
open_checkpoint [lindex $argv 0]
set out [lindex $argv 1]
set f [open $out/checkpoint.tsv w]
puts $f "PART\t[get_property PART [current_design]]"
puts $f "TOP\t[get_property TOP [current_design]]"
foreach key {CFGBVS CONFIG_VOLTAGE CONFIG_MODE} {
    puts $f "$key\t[get_property $key [current_design]]"
}
foreach p [lsort [get_ports]] {
    puts $f "PORT\t$p\t[get_property PACKAGE_PIN $p]\t[get_property IOSTANDARD $p]"
}
foreach c [lsort [get_cells -hier -filter {REF_NAME == GTXE2_CHANNEL}]] {
    puts $f "GT\t$c\t[get_property LOC $c]"
}
foreach c [get_cells -hier -filter {REF_NAME == PCIE_2_1}] {
    puts $f "PCIE\t$c\t[get_property LOC $c]"
}
foreach c [get_cells -hier -filter {REF_NAME == BSCANE2}] {
    puts $f "BSCAN\t$c\t[get_property JTAG_CHAIN $c]"
}
foreach ref {DSP48E1 RAMB36E1 RAMB18E1 ISERDESE2 OSERDESE2 IDELAYE2} {
    set cells [get_cells -hier -filter "REF_NAME == $ref"]
    puts $f "RESOURCE\t$ref\t[llength $cells]"
}
foreach c [lsort [get_clocks]] {
    puts $f "CLOCK\t$c\t[get_property PERIOD $c]"
}
set rp [get_pins {u_ld/OSERDESE2/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_1/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_1"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_1/Q}} {error "Reset driver differs for u_ld/OSERDESE2_1: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_1/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_1/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_1	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_2/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_2"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_2: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_2/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_2	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_3/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_3"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_3: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_3/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_3	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_4/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_4"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_4: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_4/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_4	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_5/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_5"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_5: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_5/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_5	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_6/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_6"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_6: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_6/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_6	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_7/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_7"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_7: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_7/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_7	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_8/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_8"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst/Q}} {error "Reset driver differs for u_ld/OSERDESE2_8: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_8/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_8	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_9/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_9"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_9: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_9/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_9	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_10/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_10"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_10: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_10/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_10	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_11/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_11"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_11: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_11/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_11	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_12/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_12"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_12: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_12/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_12	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_13/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_13"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_13: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_13/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_13	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_14/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_14"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_14: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_14/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_14	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_15/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_15"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_15: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_15/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_15	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_16/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_16"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_2/Q}} {error "Reset driver differs for u_ld/OSERDESE2_16: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_2/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_16/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_16	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_17/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_17"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_17: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_17/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_17	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_18/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_18"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_18: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_18/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_18	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_19/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_19"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_19: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_19/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_19	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_20/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_20"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_20: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_20/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_20	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_21/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_21"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_21: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_21/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_21	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_22/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_22"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_22: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_22/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_22	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_23/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_23"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_23: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_23/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_23	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_24/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_24"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_3/Q}} {error "Reset driver differs for u_ld/OSERDESE2_24: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_3/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_24/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_24	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_25/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_25"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_4/Q}} {error "Reset driver differs for u_ld/OSERDESE2_25: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_4/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_25/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_25	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_26/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_26"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_5/Q}} {error "Reset driver differs for u_ld/OSERDESE2_26: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_5/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_26/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_26	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_27/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_27"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_6/Q}} {error "Reset driver differs for u_ld/OSERDESE2_27: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_6/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_27/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_27	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_28/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_28"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_7/Q}} {error "Reset driver differs for u_ld/OSERDESE2_28: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_7/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_28/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_28	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_29/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_29"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_8/Q}} {error "Reset driver differs for u_ld/OSERDESE2_29: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_8/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_29/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_29	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_30/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_30"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_9/Q}} {error "Reset driver differs for u_ld/OSERDESE2_30: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_9/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_30/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_30	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_31/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_31"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_10/Q}} {error "Reset driver differs for u_ld/OSERDESE2_31: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_10/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_31/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_31	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_32/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_32"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_11/Q}} {error "Reset driver differs for u_ld/OSERDESE2_32: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_11/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_32/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_32	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_33/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_33"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_12/Q}} {error "Reset driver differs for u_ld/OSERDESE2_33: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_12/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_33/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_33	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_34/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_34"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_13/Q}} {error "Reset driver differs for u_ld/OSERDESE2_34: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_13/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_34/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_34	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_35/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_35"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_14/Q}} {error "Reset driver differs for u_ld/OSERDESE2_35: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_14/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_35/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_35	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_36/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_36"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_15/Q}} {error "Reset driver differs for u_ld/OSERDESE2_36: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_15/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_36/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_36	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_37/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_37"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_16/Q}} {error "Reset driver differs for u_ld/OSERDESE2_37: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_16/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_37/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_37	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_38/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_38"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_17/Q}} {error "Reset driver differs for u_ld/OSERDESE2_38: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_17/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_38/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_38	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_39/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_39"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_18/Q}} {error "Reset driver differs for u_ld/OSERDESE2_39: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_18/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_39/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_39	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_40/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_40"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_19/Q}} {error "Reset driver differs for u_ld/OSERDESE2_40: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_19/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_40/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_40	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_41/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_41"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_20/Q}} {error "Reset driver differs for u_ld/OSERDESE2_41: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_20/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_41/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_41	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_42/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_42"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_21/Q}} {error "Reset driver differs for u_ld/OSERDESE2_42: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_21/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_42/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_42	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_43/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_43"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_22/Q}} {error "Reset driver differs for u_ld/OSERDESE2_43: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_22/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_43/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_43	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_44/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_44"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_23/Q}} {error "Reset driver differs for u_ld/OSERDESE2_44: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_23/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_44/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_44	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_45/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_45"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_24/Q}} {error "Reset driver differs for u_ld/OSERDESE2_45: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_24/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_45/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_45	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_46/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_46"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_25/Q}} {error "Reset driver differs for u_ld/OSERDESE2_46: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_25/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_46/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_46	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_47/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_47"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_26/Q}} {error "Reset driver differs for u_ld/OSERDESE2_47: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_26/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_47/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_47	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_48/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_48"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_27/Q}} {error "Reset driver differs for u_ld/OSERDESE2_48: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_27/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_48/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_48	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_49/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_49"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_28/Q}} {error "Reset driver differs for u_ld/OSERDESE2_49: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_28/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_49/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_49	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_50/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_50"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_29/Q}} {error "Reset driver differs for u_ld/OSERDESE2_50: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_29/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_50/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_50	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_51/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_51"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_30/Q}} {error "Reset driver differs for u_ld/OSERDESE2_51: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_30/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_51/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_51	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_52/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_52"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_31/Q}} {error "Reset driver differs for u_ld/OSERDESE2_52: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_31/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_52/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_52	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_53/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_53"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_32/Q}} {error "Reset driver differs for u_ld/OSERDESE2_53: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_32/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_53/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_53	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_54/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_54"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_33/Q}} {error "Reset driver differs for u_ld/OSERDESE2_54: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_33/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_54/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_54	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_55/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_55"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_34/Q}} {error "Reset driver differs for u_ld/OSERDESE2_55: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_34/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_55/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_55	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_56/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_56"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_35/Q}} {error "Reset driver differs for u_ld/OSERDESE2_56: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_35/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_56/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_56	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_57/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_57"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_36/Q}} {error "Reset driver differs for u_ld/OSERDESE2_57: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_36/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_57/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_57	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_58/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_58"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_37/Q}} {error "Reset driver differs for u_ld/OSERDESE2_58: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_37/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_58/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_58	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_59/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_59"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_38/Q}} {error "Reset driver differs for u_ld/OSERDESE2_59: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_38/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_59/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_59	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_60/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_60"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_39/Q}} {error "Reset driver differs for u_ld/OSERDESE2_60: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_39/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_60/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_60	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_61/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_61"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_40/Q}} {error "Reset driver differs for u_ld/OSERDESE2_61: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_40/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_61/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_61	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_62/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_62"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_41/Q}} {error "Reset driver differs for u_ld/OSERDESE2_62: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_41/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_62/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_62	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_63/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_63"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_42/Q}} {error "Reset driver differs for u_ld/OSERDESE2_63: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_42/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_63/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_63	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_64/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_64"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_43/Q}} {error "Reset driver differs for u_ld/OSERDESE2_64: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_43/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_64/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_64	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_65/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_65"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_44/Q}} {error "Reset driver differs for u_ld/OSERDESE2_65: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_44/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_65/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_65	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_66/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_66"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_45/Q}} {error "Reset driver differs for u_ld/OSERDESE2_66: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_45/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_66/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_66	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_67/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_67"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_46/Q}} {error "Reset driver differs for u_ld/OSERDESE2_67: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_46/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_67/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_67	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_68/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_68"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_47/Q}} {error "Reset driver differs for u_ld/OSERDESE2_68: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_47/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_68/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_68	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_69/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_69"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_48/Q}} {error "Reset driver differs for u_ld/OSERDESE2_69: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_48/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_69/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_69	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_70/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_70"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_49/Q}} {error "Reset driver differs for u_ld/OSERDESE2_70: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_49/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_70/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_70	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_71/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_71"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_50/Q}} {error "Reset driver differs for u_ld/OSERDESE2_71: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_50/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_71/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_71	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_72/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_72"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_51/Q}} {error "Reset driver differs for u_ld/OSERDESE2_72: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_51/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_72/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_72	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_73/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_73"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_52/Q}} {error "Reset driver differs for u_ld/OSERDESE2_73: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_52/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_73/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_73	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_74/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_74"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_53/Q}} {error "Reset driver differs for u_ld/OSERDESE2_74: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_53/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_74/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_74	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_75/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_75"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_54/Q}} {error "Reset driver differs for u_ld/OSERDESE2_75: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_54/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_75/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_75	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_76/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_76"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_55/Q}} {error "Reset driver differs for u_ld/OSERDESE2_76: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_55/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_76/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_76	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_77/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_77"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_56/Q}} {error "Reset driver differs for u_ld/OSERDESE2_77: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_56/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_77/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_77	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_78/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_78"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_57/Q}} {error "Reset driver differs for u_ld/OSERDESE2_78: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_57/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_78/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_78	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_79/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_79"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_58/Q}} {error "Reset driver differs for u_ld/OSERDESE2_79: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_58/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_79/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_79	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_80/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_80"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_59/Q}} {error "Reset driver differs for u_ld/OSERDESE2_80: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_59/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_80/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_80	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_81/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_81"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_60/Q}} {error "Reset driver differs for u_ld/OSERDESE2_81: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_60/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_81/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_81	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_82/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_82"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_61/Q}} {error "Reset driver differs for u_ld/OSERDESE2_82: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_61/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_82/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_82	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_83/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_83"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_62/Q}} {error "Reset driver differs for u_ld/OSERDESE2_83: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_62/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_83/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_83	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_84/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_84"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_63/Q}} {error "Reset driver differs for u_ld/OSERDESE2_84: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_63/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_84/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_84	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_85/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_85"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_64/Q}} {error "Reset driver differs for u_ld/OSERDESE2_85: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_64/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_85/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_85	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_86/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_86"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_65/Q}} {error "Reset driver differs for u_ld/OSERDESE2_86: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_65/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_86/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_86	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_87/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_87"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_66/Q}} {error "Reset driver differs for u_ld/OSERDESE2_87: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_66/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_87/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_87	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_88/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_88"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_67/Q}} {error "Reset driver differs for u_ld/OSERDESE2_88: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_67/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_88/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_88	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_89/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_89"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_68/Q}} {error "Reset driver differs for u_ld/OSERDESE2_89: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_68/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_89/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_89	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_90/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_90"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_69/Q}} {error "Reset driver differs for u_ld/OSERDESE2_90: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_69/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_90/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_90	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_91/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_91"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_70/Q}} {error "Reset driver differs for u_ld/OSERDESE2_91: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_70/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_91/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_91	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_92/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_92"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_71/Q}} {error "Reset driver differs for u_ld/OSERDESE2_92: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_71/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_92/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_92	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_93/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_93"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_72/Q}} {error "Reset driver differs for u_ld/OSERDESE2_93: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_72/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_93/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_93	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_94/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_94"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_73/Q}} {error "Reset driver differs for u_ld/OSERDESE2_94: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_73/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_94/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_94	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_95/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_95"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_74/Q}} {error "Reset driver differs for u_ld/OSERDESE2_95: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_74/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_95/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_95	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_96/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_96"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_75/Q}} {error "Reset driver differs for u_ld/OSERDESE2_96: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_75/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_96/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_96	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_97/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_97"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_76/Q}} {error "Reset driver differs for u_ld/OSERDESE2_97: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_76/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_97/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	0	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_97	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_98/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_98"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_98: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_98/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_98	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_99/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_99"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_78/Q}} {error "Reset driver differs for u_ld/OSERDESE2_99: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_78/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_99/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_99	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_100/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_100"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_100: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_100/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_100	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_101/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_101"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_101: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_101/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_101	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_102/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_102"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_102: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_102/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_102	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_103/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_103"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_103: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_103/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_103	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_104/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_104"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_104: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_104/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_104	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_105/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_105"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_105: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_105/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_105	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_106/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_106"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_77/Q}} {error "Reset driver differs for u_ld/OSERDESE2_106: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_77/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_106/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_106	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_107/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_107"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_107: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_107/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_107	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_108/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_108"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_108: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_108/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_108	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_109/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_109"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_109: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_109/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_109	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_110/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_110"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_110: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_110/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_110	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_111/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_111"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_111: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_111/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_111	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_112/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_112"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_112: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_112/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_112	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_113/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_113"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_113: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_113/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_113	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_114/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_114"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_79/Q}} {error "Reset driver differs for u_ld/OSERDESE2_114: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_79/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_114/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_114	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_115/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_115"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_115: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_115/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_115	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_116/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_116"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_116: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_116/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_116	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_117/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_117"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_117: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_117/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_117	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_118/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_118"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_118: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_118/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_118	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_119/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_119"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_119: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_119/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_119	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_120/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_120"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_120: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_120/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_120	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_121/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_121"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_121: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_121/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_121	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_122/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_122"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_80/Q}} {error "Reset driver differs for u_ld/OSERDESE2_122: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_80/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_122/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_122	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_123/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_123"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_81/Q}} {error "Reset driver differs for u_ld/OSERDESE2_123: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_81/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_123/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_123	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_124/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_124"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_82/Q}} {error "Reset driver differs for u_ld/OSERDESE2_124: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_82/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_124/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_124	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_125/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_125"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_83/Q}} {error "Reset driver differs for u_ld/OSERDESE2_125: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_83/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_125/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_125	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_126/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_126"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_84/Q}} {error "Reset driver differs for u_ld/OSERDESE2_126: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_84/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_126/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_126	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_127/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_127"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_85/Q}} {error "Reset driver differs for u_ld/OSERDESE2_127: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_85/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_127/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_127	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_128/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_128"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_86/Q}} {error "Reset driver differs for u_ld/OSERDESE2_128: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_86/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_128/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_128	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_129/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_129"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_87/Q}} {error "Reset driver differs for u_ld/OSERDESE2_129: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_87/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_129/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_129	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_130/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_130"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_88/Q}} {error "Reset driver differs for u_ld/OSERDESE2_130: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_88/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_130/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_130	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_131/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_131"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_89/Q}} {error "Reset driver differs for u_ld/OSERDESE2_131: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_89/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_131/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_131	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_132/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_132"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_90/Q}} {error "Reset driver differs for u_ld/OSERDESE2_132: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_90/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_132/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_132	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_133/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_133"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_91/Q}} {error "Reset driver differs for u_ld/OSERDESE2_133: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_91/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_133/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_133	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_134/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_134"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_92/Q}} {error "Reset driver differs for u_ld/OSERDESE2_134: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_92/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_134/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_134	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_135/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_135"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_93/Q}} {error "Reset driver differs for u_ld/OSERDESE2_135: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_93/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_135/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_135	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_136/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_136"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_94/Q}} {error "Reset driver differs for u_ld/OSERDESE2_136: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_94/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_136/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_136	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_137/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_137"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_95/Q}} {error "Reset driver differs for u_ld/OSERDESE2_137: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_95/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_137/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_137	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_138/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_138"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_96/Q}} {error "Reset driver differs for u_ld/OSERDESE2_138: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_96/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_138/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_138	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_139/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_139"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_97/Q}} {error "Reset driver differs for u_ld/OSERDESE2_139: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_97/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_139/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_139	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_140/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_140"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_98/Q}} {error "Reset driver differs for u_ld/OSERDESE2_140: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_98/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_140/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_140	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_141/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_141"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_99/Q}} {error "Reset driver differs for u_ld/OSERDESE2_141: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_99/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_141/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_141	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_142/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_142"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_100/Q}} {error "Reset driver differs for u_ld/OSERDESE2_142: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_100/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_142/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_142	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_143/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_143"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_101/Q}} {error "Reset driver differs for u_ld/OSERDESE2_143: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_101/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_143/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_143	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_144/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_144"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_102/Q}} {error "Reset driver differs for u_ld/OSERDESE2_144: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_102/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_144/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_144	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_145/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_145"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_103/Q}} {error "Reset driver differs for u_ld/OSERDESE2_145: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_103/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_145/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_145	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_146/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_146"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_104/Q}} {error "Reset driver differs for u_ld/OSERDESE2_146: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_104/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_146/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_146	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_147/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_147"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_105/Q}} {error "Reset driver differs for u_ld/OSERDESE2_147: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_105/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_147/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_147	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_148/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_148"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_106/Q}} {error "Reset driver differs for u_ld/OSERDESE2_148: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_106/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_148/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_148	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_149/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_149"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_107/Q}} {error "Reset driver differs for u_ld/OSERDESE2_149: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_107/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_149/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_149	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_150/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_150"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_108/Q}} {error "Reset driver differs for u_ld/OSERDESE2_150: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_108/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_150/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_150	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_151/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_151"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_109/Q}} {error "Reset driver differs for u_ld/OSERDESE2_151: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_109/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_151/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_151	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_152/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_152"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_110/Q}} {error "Reset driver differs for u_ld/OSERDESE2_152: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_110/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_152/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_152	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_153/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_153"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_111/Q}} {error "Reset driver differs for u_ld/OSERDESE2_153: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_111/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_153/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_153	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_154/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_154"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_112/Q}} {error "Reset driver differs for u_ld/OSERDESE2_154: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_112/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_154/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_154	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_155/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_155"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_113/Q}} {error "Reset driver differs for u_ld/OSERDESE2_155: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_113/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_155/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_155	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_156/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_156"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_114/Q}} {error "Reset driver differs for u_ld/OSERDESE2_156: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_114/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_156/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_156	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_157/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_157"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_115/Q}} {error "Reset driver differs for u_ld/OSERDESE2_157: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_115/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_157/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_157	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_158/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_158"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_116/Q}} {error "Reset driver differs for u_ld/OSERDESE2_158: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_116/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_158/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_158	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_159/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_159"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_117/Q}} {error "Reset driver differs for u_ld/OSERDESE2_159: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_117/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_159/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_159	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_160/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_160"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_118/Q}} {error "Reset driver differs for u_ld/OSERDESE2_160: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_118/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_160/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_160	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_161/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_161"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_119/Q}} {error "Reset driver differs for u_ld/OSERDESE2_161: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_119/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_161/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_161	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_162/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_162"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_120/Q}} {error "Reset driver differs for u_ld/OSERDESE2_162: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_120/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_162/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_162	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_163/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_163"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_121/Q}} {error "Reset driver differs for u_ld/OSERDESE2_163: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_121/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_163/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_163	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_164/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_164"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_122/Q}} {error "Reset driver differs for u_ld/OSERDESE2_164: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_122/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_164/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_164	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_165/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_165"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_123/Q}} {error "Reset driver differs for u_ld/OSERDESE2_165: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_123/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_165/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_165	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_166/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_166"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_124/Q}} {error "Reset driver differs for u_ld/OSERDESE2_166: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_124/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_166/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_166	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_167/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_167"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_125/Q}} {error "Reset driver differs for u_ld/OSERDESE2_167: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_125/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_167/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_167	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_168/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_168"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_126/Q}} {error "Reset driver differs for u_ld/OSERDESE2_168: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_126/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_168/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_168	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_169/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_169"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_127/Q}} {error "Reset driver differs for u_ld/OSERDESE2_169: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_127/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_169/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_169	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_170/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_170"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_128/Q}} {error "Reset driver differs for u_ld/OSERDESE2_170: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_128/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_170/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_170	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_171/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_171"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_129/Q}} {error "Reset driver differs for u_ld/OSERDESE2_171: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_129/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_171/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_171	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_172/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_172"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_130/Q}} {error "Reset driver differs for u_ld/OSERDESE2_172: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_130/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_172/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_172	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_173/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_173"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_131/Q}} {error "Reset driver differs for u_ld/OSERDESE2_173: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_131/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_173/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_173	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_174/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_174"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_132/Q}} {error "Reset driver differs for u_ld/OSERDESE2_174: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_132/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_174/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_174	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_175/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_175"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_133/Q}} {error "Reset driver differs for u_ld/OSERDESE2_175: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_133/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_175/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_175	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_176/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_176"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_134/Q}} {error "Reset driver differs for u_ld/OSERDESE2_176: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_134/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_176/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_176	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_177/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_177"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_135/Q}} {error "Reset driver differs for u_ld/OSERDESE2_177: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_135/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_177/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_177	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_178/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_178"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_136/Q}} {error "Reset driver differs for u_ld/OSERDESE2_178: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_136/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_178/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_178	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_179/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_179"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_137/Q}} {error "Reset driver differs for u_ld/OSERDESE2_179: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_137/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_179/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_179	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_180/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_180"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_138/Q}} {error "Reset driver differs for u_ld/OSERDESE2_180: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_138/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_180/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_180	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_181/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_181"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_139/Q}} {error "Reset driver differs for u_ld/OSERDESE2_181: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_139/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_181/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_181	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_182/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_182"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_140/Q}} {error "Reset driver differs for u_ld/OSERDESE2_182: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_140/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_182/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_182	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_183/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_183"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_141/Q}} {error "Reset driver differs for u_ld/OSERDESE2_183: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_141/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_183/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_183	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_184/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_184"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_142/Q}} {error "Reset driver differs for u_ld/OSERDESE2_184: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_142/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_184/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_184	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_185/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_185"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_143/Q}} {error "Reset driver differs for u_ld/OSERDESE2_185: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_143/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_185/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_185	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_186/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_186"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_144/Q}} {error "Reset driver differs for u_ld/OSERDESE2_186: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_144/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_186/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_186	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_187/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_187"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_145/Q}} {error "Reset driver differs for u_ld/OSERDESE2_187: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_145/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_187/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_187	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_188/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_188"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_146/Q}} {error "Reset driver differs for u_ld/OSERDESE2_188: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_146/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_188/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_188	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_189/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_189"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_147/Q}} {error "Reset driver differs for u_ld/OSERDESE2_189: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_147/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_189/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_189	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_190/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_190"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_148/Q}} {error "Reset driver differs for u_ld/OSERDESE2_190: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_148/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_190/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_190	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_191/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_191"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_149/Q}} {error "Reset driver differs for u_ld/OSERDESE2_191: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_149/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_191/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_191	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_192/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_192"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_150/Q}} {error "Reset driver differs for u_ld/OSERDESE2_192: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_150/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_192/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_192	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_193/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_193"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_151/Q}} {error "Reset driver differs for u_ld/OSERDESE2_193: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_151/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_193/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_193	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_194/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_194"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_152/Q}} {error "Reset driver differs for u_ld/OSERDESE2_194: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_152/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_194/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_194	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_195/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_195"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_153/Q}} {error "Reset driver differs for u_ld/OSERDESE2_195: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_153/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_195/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_195	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_196/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_196"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_154/Q}} {error "Reset driver differs for u_ld/OSERDESE2_196: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_154/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_196/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_196	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_197/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_197"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_155/Q}} {error "Reset driver differs for u_ld/OSERDESE2_197: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_155/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_197/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_197	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_198/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_198"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_156/Q}} {error "Reset driver differs for u_ld/OSERDESE2_198: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_156/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_198/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_198	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_199/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_199"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_157/Q}} {error "Reset driver differs for u_ld/OSERDESE2_199: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_157/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_199/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_199	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_200/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_200"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_158/Q}} {error "Reset driver differs for u_ld/OSERDESE2_200: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_158/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_200/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_200	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_201/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_201"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_159/Q}} {error "Reset driver differs for u_ld/OSERDESE2_201: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_159/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_201/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_201	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_202/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_202"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_160/Q}} {error "Reset driver differs for u_ld/OSERDESE2_202: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_160/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_202/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_202	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_203/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_203"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_161/Q}} {error "Reset driver differs for u_ld/OSERDESE2_203: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_161/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_203/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_203	$rc	$rclk"
set rp [get_pins {u_ld/OSERDESE2_204/RST}]
if {[llength $rp]!=1} {error "Missing serializer reset u_ld/OSERDESE2_204"}
set drivers [get_pins -of_objects [get_nets -segments -of_objects $rp] -filter {DIRECTION == OUT}]
if {[llength $drivers]!=1 || [get_property NAME $drivers] ne {u_ld/wlrst_162/Q}} {error "Reset driver differs for u_ld/OSERDESE2_204: $drivers"}
set rc [get_cells -of_objects $drivers]
if {[get_property REF_NAME $rc] ne {FDRE}} {error "Reset register type differs"}
set rclk [get_clocks -of_objects [get_pins {u_ld/wlrst_162/C}]]
set sclk [get_clocks -of_objects [get_pins {u_ld/OSERDESE2_204/CLKDIV}]]
if {[llength $rclk]!=1 || [llength $sclk]!=1 || $rclk ne $sclk} {error "Serializer reset clock mismatch"}
puts $f "PHY_RESET	1	$rc	[get_property REF_NAME $rc]"
puts $f "SERIALIZER_RESET	u_ld/OSERDESE2_204	$rc	$rclk"
close $f
report_route_status -file $out/route.rpt
report_timing_summary -report_unconstrained -file $out/timing.rpt
report_bus_skew -file $out/bus-skew.rpt
report_cdc -details -file $out/cdc.rpt
report_clocks -file $out/clocks.rpt
report_drc -file $out/drc.rpt
foreach v [get_drc_violations -quiet] {
    if {[get_property SEVERITY $v] in {Error {Critical Warning}}} {
        error "Unresolved DRC: $v"
    }
}
if {[lindex $argv 3] eq "1"} {source $out/review_oob_clocks.tcl}

set pf [open $out/phase-query.tsv w]
foreach ch {0 1} {
 foreach {pin period} {CLKIN1 10.0 CLKOUT0 10.0 CLKOUT1 2.5} {
  set pins [get_pins -hierarchical -filter "NAME =~ */ldmmcm${ch}/${pin}"]
  if {[llength $pins]!=1} {error "Phase query has ambiguous or missing pin: $ch/$pin/$pins"}
  set clocks [get_clocks -of_objects $pins]
  if {[llength $clocks]!=1} {error "Phase query has ambiguous or missing clock: $ch/$pin/$clocks"}
  set actual [get_property PERIOD $clocks]
  if {abs($actual-$period)>0.001} {error "Unexpected phase clock period: $ch/$pin/$actual"}
  puts $pf "$ch\t$pin\t$pins\t$clocks\t$actual"
 }
}
close $pf

close_design
exit
