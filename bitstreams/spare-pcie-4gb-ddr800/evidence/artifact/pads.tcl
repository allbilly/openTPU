set build [file normalize [lindex $argv 0]]
set out [file normalize [lindex $argv 1]]
set_param general.maxThreads 2
open_checkpoint $build/project/final-routed.dcp
set f [open $out/pad-groups.tsv w]
set cell [get_cells {u_ld/IOBUF_8}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_8"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_8/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[0]}} {error "Pad connection differs: u_ld/IOBUF_8/IO"}
puts $f "PAD	u_ld/IOBUF_8	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_9}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_9"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_9/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[1]}} {error "Pad connection differs: u_ld/IOBUF_9/IO"}
puts $f "PAD	u_ld/IOBUF_9	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_10}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_10"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_10/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[2]}} {error "Pad connection differs: u_ld/IOBUF_10/IO"}
puts $f "PAD	u_ld/IOBUF_10	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_11}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_11"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_11/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[3]}} {error "Pad connection differs: u_ld/IOBUF_11/IO"}
puts $f "PAD	u_ld/IOBUF_11	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_12}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_12"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_12/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[4]}} {error "Pad connection differs: u_ld/IOBUF_12/IO"}
puts $f "PAD	u_ld/IOBUF_12	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_13}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_13"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_13/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[5]}} {error "Pad connection differs: u_ld/IOBUF_13/IO"}
puts $f "PAD	u_ld/IOBUF_13	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_14}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_14"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_14/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[6]}} {error "Pad connection differs: u_ld/IOBUF_14/IO"}
puts $f "PAD	u_ld/IOBUF_14	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_15}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_15"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_15/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[7]}} {error "Pad connection differs: u_ld/IOBUF_15/IO"}
puts $f "PAD	u_ld/IOBUF_15	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_1}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_1"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_1/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[0]}} {error "Pad connection differs: u_ld/IOBUFDS_1/IO"}
puts $f "PAD	u_ld/IOBUFDS_1	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_1/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[0]}} {error "Pad connection differs: u_ld/IOBUFDS_1/IOB"}
puts $f "PAD	u_ld/IOBUFDS_1	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_16}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_16"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_16/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[8]}} {error "Pad connection differs: u_ld/IOBUF_16/IO"}
puts $f "PAD	u_ld/IOBUF_16	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_17}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_17"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_17/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[9]}} {error "Pad connection differs: u_ld/IOBUF_17/IO"}
puts $f "PAD	u_ld/IOBUF_17	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_18}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_18"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_18/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[10]}} {error "Pad connection differs: u_ld/IOBUF_18/IO"}
puts $f "PAD	u_ld/IOBUF_18	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_19}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_19"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_19/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[11]}} {error "Pad connection differs: u_ld/IOBUF_19/IO"}
puts $f "PAD	u_ld/IOBUF_19	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_20}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_20"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_20/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[12]}} {error "Pad connection differs: u_ld/IOBUF_20/IO"}
puts $f "PAD	u_ld/IOBUF_20	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_21}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_21"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_21/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[13]}} {error "Pad connection differs: u_ld/IOBUF_21/IO"}
puts $f "PAD	u_ld/IOBUF_21	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_22}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_22"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_22/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[14]}} {error "Pad connection differs: u_ld/IOBUF_22/IO"}
puts $f "PAD	u_ld/IOBUF_22	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_23}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_23"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_23/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[15]}} {error "Pad connection differs: u_ld/IOBUF_23/IO"}
puts $f "PAD	u_ld/IOBUF_23	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_2}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_2"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_2/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[1]}} {error "Pad connection differs: u_ld/IOBUFDS_2/IO"}
puts $f "PAD	u_ld/IOBUFDS_2	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_2/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[1]}} {error "Pad connection differs: u_ld/IOBUFDS_2/IOB"}
puts $f "PAD	u_ld/IOBUFDS_2	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_24}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_24"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_24/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[16]}} {error "Pad connection differs: u_ld/IOBUF_24/IO"}
puts $f "PAD	u_ld/IOBUF_24	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_25}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_25"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_25/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[17]}} {error "Pad connection differs: u_ld/IOBUF_25/IO"}
puts $f "PAD	u_ld/IOBUF_25	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_26}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_26"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_26/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[18]}} {error "Pad connection differs: u_ld/IOBUF_26/IO"}
puts $f "PAD	u_ld/IOBUF_26	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_27}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_27"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_27/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[19]}} {error "Pad connection differs: u_ld/IOBUF_27/IO"}
puts $f "PAD	u_ld/IOBUF_27	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_28}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_28"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_28/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[20]}} {error "Pad connection differs: u_ld/IOBUF_28/IO"}
puts $f "PAD	u_ld/IOBUF_28	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_29}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_29"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_29/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[21]}} {error "Pad connection differs: u_ld/IOBUF_29/IO"}
puts $f "PAD	u_ld/IOBUF_29	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_30}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_30"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_30/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[22]}} {error "Pad connection differs: u_ld/IOBUF_30/IO"}
puts $f "PAD	u_ld/IOBUF_30	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_31}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_31"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_31/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[23]}} {error "Pad connection differs: u_ld/IOBUF_31/IO"}
puts $f "PAD	u_ld/IOBUF_31	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_3}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_3"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_3/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[2]}} {error "Pad connection differs: u_ld/IOBUFDS_3/IO"}
puts $f "PAD	u_ld/IOBUFDS_3	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_3/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[2]}} {error "Pad connection differs: u_ld/IOBUFDS_3/IOB"}
puts $f "PAD	u_ld/IOBUFDS_3	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_32}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_32"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_32/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[24]}} {error "Pad connection differs: u_ld/IOBUF_32/IO"}
puts $f "PAD	u_ld/IOBUF_32	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_33}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_33"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_33/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[25]}} {error "Pad connection differs: u_ld/IOBUF_33/IO"}
puts $f "PAD	u_ld/IOBUF_33	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_34}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_34"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_34/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[26]}} {error "Pad connection differs: u_ld/IOBUF_34/IO"}
puts $f "PAD	u_ld/IOBUF_34	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_35}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_35"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_35/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[27]}} {error "Pad connection differs: u_ld/IOBUF_35/IO"}
puts $f "PAD	u_ld/IOBUF_35	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_36}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_36"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_36/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[28]}} {error "Pad connection differs: u_ld/IOBUF_36/IO"}
puts $f "PAD	u_ld/IOBUF_36	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_37}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_37"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_37/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[29]}} {error "Pad connection differs: u_ld/IOBUF_37/IO"}
puts $f "PAD	u_ld/IOBUF_37	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_38}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_38"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_38/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[30]}} {error "Pad connection differs: u_ld/IOBUF_38/IO"}
puts $f "PAD	u_ld/IOBUF_38	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_39}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_39"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_39/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[31]}} {error "Pad connection differs: u_ld/IOBUF_39/IO"}
puts $f "PAD	u_ld/IOBUF_39	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_4}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_4"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_4/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[3]}} {error "Pad connection differs: u_ld/IOBUFDS_4/IO"}
puts $f "PAD	u_ld/IOBUFDS_4	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_4/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[3]}} {error "Pad connection differs: u_ld/IOBUFDS_4/IOB"}
puts $f "PAD	u_ld/IOBUFDS_4	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_40}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_40"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_40/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[32]}} {error "Pad connection differs: u_ld/IOBUF_40/IO"}
puts $f "PAD	u_ld/IOBUF_40	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_41}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_41"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_41/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[33]}} {error "Pad connection differs: u_ld/IOBUF_41/IO"}
puts $f "PAD	u_ld/IOBUF_41	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_42}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_42"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_42/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[34]}} {error "Pad connection differs: u_ld/IOBUF_42/IO"}
puts $f "PAD	u_ld/IOBUF_42	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_43}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_43"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_43/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[35]}} {error "Pad connection differs: u_ld/IOBUF_43/IO"}
puts $f "PAD	u_ld/IOBUF_43	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_44}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_44"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_44/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[36]}} {error "Pad connection differs: u_ld/IOBUF_44/IO"}
puts $f "PAD	u_ld/IOBUF_44	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_45}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_45"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_45/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[37]}} {error "Pad connection differs: u_ld/IOBUF_45/IO"}
puts $f "PAD	u_ld/IOBUF_45	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_46}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_46"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_46/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[38]}} {error "Pad connection differs: u_ld/IOBUF_46/IO"}
puts $f "PAD	u_ld/IOBUF_46	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_47}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_47"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_47/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[39]}} {error "Pad connection differs: u_ld/IOBUF_47/IO"}
puts $f "PAD	u_ld/IOBUF_47	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_5}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_5"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_5/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[4]}} {error "Pad connection differs: u_ld/IOBUFDS_5/IO"}
puts $f "PAD	u_ld/IOBUFDS_5	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_5/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[4]}} {error "Pad connection differs: u_ld/IOBUFDS_5/IOB"}
puts $f "PAD	u_ld/IOBUFDS_5	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_48}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_48"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_48/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[40]}} {error "Pad connection differs: u_ld/IOBUF_48/IO"}
puts $f "PAD	u_ld/IOBUF_48	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_49}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_49"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_49/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[41]}} {error "Pad connection differs: u_ld/IOBUF_49/IO"}
puts $f "PAD	u_ld/IOBUF_49	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_50}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_50"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_50/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[42]}} {error "Pad connection differs: u_ld/IOBUF_50/IO"}
puts $f "PAD	u_ld/IOBUF_50	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_51}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_51"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_51/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[43]}} {error "Pad connection differs: u_ld/IOBUF_51/IO"}
puts $f "PAD	u_ld/IOBUF_51	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_52}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_52"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_52/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[44]}} {error "Pad connection differs: u_ld/IOBUF_52/IO"}
puts $f "PAD	u_ld/IOBUF_52	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_53}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_53"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_53/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[45]}} {error "Pad connection differs: u_ld/IOBUF_53/IO"}
puts $f "PAD	u_ld/IOBUF_53	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_54}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_54"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_54/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[46]}} {error "Pad connection differs: u_ld/IOBUF_54/IO"}
puts $f "PAD	u_ld/IOBUF_54	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_55}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_55"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_55/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[47]}} {error "Pad connection differs: u_ld/IOBUF_55/IO"}
puts $f "PAD	u_ld/IOBUF_55	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_6}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_6"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_6/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[5]}} {error "Pad connection differs: u_ld/IOBUFDS_6/IO"}
puts $f "PAD	u_ld/IOBUFDS_6	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_6/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[5]}} {error "Pad connection differs: u_ld/IOBUFDS_6/IOB"}
puts $f "PAD	u_ld/IOBUFDS_6	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_56}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_56"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_56/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[64]}} {error "Pad connection differs: u_ld/IOBUF_56/IO"}
puts $f "PAD	u_ld/IOBUF_56	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_57}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_57"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_57/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[65]}} {error "Pad connection differs: u_ld/IOBUF_57/IO"}
puts $f "PAD	u_ld/IOBUF_57	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_58}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_58"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_58/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[66]}} {error "Pad connection differs: u_ld/IOBUF_58/IO"}
puts $f "PAD	u_ld/IOBUF_58	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_59}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_59"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_59/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[67]}} {error "Pad connection differs: u_ld/IOBUF_59/IO"}
puts $f "PAD	u_ld/IOBUF_59	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_60}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_60"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_60/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[68]}} {error "Pad connection differs: u_ld/IOBUF_60/IO"}
puts $f "PAD	u_ld/IOBUF_60	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_61}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_61"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_61/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[69]}} {error "Pad connection differs: u_ld/IOBUF_61/IO"}
puts $f "PAD	u_ld/IOBUF_61	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_62}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_62"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_62/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[70]}} {error "Pad connection differs: u_ld/IOBUF_62/IO"}
puts $f "PAD	u_ld/IOBUF_62	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_63}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_63"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_63/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[71]}} {error "Pad connection differs: u_ld/IOBUF_63/IO"}
puts $f "PAD	u_ld/IOBUF_63	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_7}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_7"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_7/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[8]}} {error "Pad connection differs: u_ld/IOBUFDS_7/IO"}
puts $f "PAD	u_ld/IOBUFDS_7	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_7/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[8]}} {error "Pad connection differs: u_ld/IOBUFDS_7/IOB"}
puts $f "PAD	u_ld/IOBUFDS_7	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_64}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_64"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_64/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[56]}} {error "Pad connection differs: u_ld/IOBUF_64/IO"}
puts $f "PAD	u_ld/IOBUF_64	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_65}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_65"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_65/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[57]}} {error "Pad connection differs: u_ld/IOBUF_65/IO"}
puts $f "PAD	u_ld/IOBUF_65	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_66}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_66"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_66/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[58]}} {error "Pad connection differs: u_ld/IOBUF_66/IO"}
puts $f "PAD	u_ld/IOBUF_66	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_67}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_67"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_67/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[59]}} {error "Pad connection differs: u_ld/IOBUF_67/IO"}
puts $f "PAD	u_ld/IOBUF_67	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_68}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_68"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_68/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[60]}} {error "Pad connection differs: u_ld/IOBUF_68/IO"}
puts $f "PAD	u_ld/IOBUF_68	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_69}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_69"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_69/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[61]}} {error "Pad connection differs: u_ld/IOBUF_69/IO"}
puts $f "PAD	u_ld/IOBUF_69	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_70}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_70"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_70/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[62]}} {error "Pad connection differs: u_ld/IOBUF_70/IO"}
puts $f "PAD	u_ld/IOBUF_70	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_71}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_71"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_71/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[63]}} {error "Pad connection differs: u_ld/IOBUF_71/IO"}
puts $f "PAD	u_ld/IOBUF_71	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_8}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_8"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_8/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[7]}} {error "Pad connection differs: u_ld/IOBUFDS_8/IO"}
puts $f "PAD	u_ld/IOBUFDS_8	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_8/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[7]}} {error "Pad connection differs: u_ld/IOBUFDS_8/IOB"}
puts $f "PAD	u_ld/IOBUFDS_8	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[48]}} {error "Pad connection differs: u_ld/IOBUF/IO"}
puts $f "PAD	u_ld/IOBUF	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF"}
puts $f "HIGH_Z	u_ld/IOBUF	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_1}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_1"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_1/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[49]}} {error "Pad connection differs: u_ld/IOBUF_1/IO"}
puts $f "PAD	u_ld/IOBUF_1	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_1/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_1"}
puts $f "HIGH_Z	u_ld/IOBUF_1	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_2}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_2"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_2/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[50]}} {error "Pad connection differs: u_ld/IOBUF_2/IO"}
puts $f "PAD	u_ld/IOBUF_2	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_2/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_2"}
puts $f "HIGH_Z	u_ld/IOBUF_2	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_3}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_3"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_3/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[51]}} {error "Pad connection differs: u_ld/IOBUF_3/IO"}
puts $f "PAD	u_ld/IOBUF_3	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_3/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_3"}
puts $f "HIGH_Z	u_ld/IOBUF_3	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_4}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_4"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_4/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[52]}} {error "Pad connection differs: u_ld/IOBUF_4/IO"}
puts $f "PAD	u_ld/IOBUF_4	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_4/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_4"}
puts $f "HIGH_Z	u_ld/IOBUF_4	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_5}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_5"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_5/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[53]}} {error "Pad connection differs: u_ld/IOBUF_5/IO"}
puts $f "PAD	u_ld/IOBUF_5	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_5/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_5"}
puts $f "HIGH_Z	u_ld/IOBUF_5	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_6}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_6"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_6/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[54]}} {error "Pad connection differs: u_ld/IOBUF_6/IO"}
puts $f "PAD	u_ld/IOBUF_6	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_6/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_6"}
puts $f "HIGH_Z	u_ld/IOBUF_6	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_7}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_7"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_7/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dq[55]}} {error "Pad connection differs: u_ld/IOBUF_7/IO"}
puts $f "PAD	u_ld/IOBUF_7	IO	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_7/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUF_7"}
puts $f "HIGH_Z	u_ld/IOBUF_7	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUFDS}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_p[6]}} {error "Pad connection differs: u_ld/IOBUFDS/IO"}
puts $f "PAD	u_ld/IOBUFDS	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram0_dqs_n[6]}} {error "Pad connection differs: u_ld/IOBUFDS/IOB"}
puts $f "PAD	u_ld/IOBUFDS	IOB	[get_property NAME $ports]"
set drivers [get_pins -of_objects [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS/T}]] -filter {DIRECTION == OUT}]
set sources [get_cells -of_objects $drivers]
if {[llength $sources]!=1 || [get_property REF_NAME $sources] ne "VCC"} {error "Disabled lane is not held high-Z: u_ld/IOBUFDS"}
puts $f "HIGH_Z	u_ld/IOBUFDS	[get_property REF_NAME $sources]"
set cell [get_cells {u_ld/IOBUF_72}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_72"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_72/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[0]}} {error "Pad connection differs: u_ld/IOBUF_72/IO"}
puts $f "PAD	u_ld/IOBUF_72	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_73}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_73"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_73/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[1]}} {error "Pad connection differs: u_ld/IOBUF_73/IO"}
puts $f "PAD	u_ld/IOBUF_73	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_74}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_74"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_74/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[2]}} {error "Pad connection differs: u_ld/IOBUF_74/IO"}
puts $f "PAD	u_ld/IOBUF_74	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_75}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_75"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_75/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[3]}} {error "Pad connection differs: u_ld/IOBUF_75/IO"}
puts $f "PAD	u_ld/IOBUF_75	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_76}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_76"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_76/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[4]}} {error "Pad connection differs: u_ld/IOBUF_76/IO"}
puts $f "PAD	u_ld/IOBUF_76	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_77}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_77"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_77/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[5]}} {error "Pad connection differs: u_ld/IOBUF_77/IO"}
puts $f "PAD	u_ld/IOBUF_77	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_78}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_78"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_78/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[6]}} {error "Pad connection differs: u_ld/IOBUF_78/IO"}
puts $f "PAD	u_ld/IOBUF_78	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_79}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_79"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_79/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[7]}} {error "Pad connection differs: u_ld/IOBUF_79/IO"}
puts $f "PAD	u_ld/IOBUF_79	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_9}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_9"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_9/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[0]}} {error "Pad connection differs: u_ld/IOBUFDS_9/IO"}
puts $f "PAD	u_ld/IOBUFDS_9	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_9/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[0]}} {error "Pad connection differs: u_ld/IOBUFDS_9/IOB"}
puts $f "PAD	u_ld/IOBUFDS_9	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_80}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_80"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_80/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[8]}} {error "Pad connection differs: u_ld/IOBUF_80/IO"}
puts $f "PAD	u_ld/IOBUF_80	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_81}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_81"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_81/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[9]}} {error "Pad connection differs: u_ld/IOBUF_81/IO"}
puts $f "PAD	u_ld/IOBUF_81	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_82}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_82"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_82/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[10]}} {error "Pad connection differs: u_ld/IOBUF_82/IO"}
puts $f "PAD	u_ld/IOBUF_82	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_83}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_83"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_83/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[11]}} {error "Pad connection differs: u_ld/IOBUF_83/IO"}
puts $f "PAD	u_ld/IOBUF_83	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_84}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_84"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_84/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[12]}} {error "Pad connection differs: u_ld/IOBUF_84/IO"}
puts $f "PAD	u_ld/IOBUF_84	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_85}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_85"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_85/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[13]}} {error "Pad connection differs: u_ld/IOBUF_85/IO"}
puts $f "PAD	u_ld/IOBUF_85	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_86}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_86"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_86/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[14]}} {error "Pad connection differs: u_ld/IOBUF_86/IO"}
puts $f "PAD	u_ld/IOBUF_86	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_87}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_87"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_87/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[15]}} {error "Pad connection differs: u_ld/IOBUF_87/IO"}
puts $f "PAD	u_ld/IOBUF_87	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_10}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_10"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_10/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[1]}} {error "Pad connection differs: u_ld/IOBUFDS_10/IO"}
puts $f "PAD	u_ld/IOBUFDS_10	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_10/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[1]}} {error "Pad connection differs: u_ld/IOBUFDS_10/IOB"}
puts $f "PAD	u_ld/IOBUFDS_10	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_88}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_88"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_88/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[16]}} {error "Pad connection differs: u_ld/IOBUF_88/IO"}
puts $f "PAD	u_ld/IOBUF_88	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_89}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_89"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_89/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[17]}} {error "Pad connection differs: u_ld/IOBUF_89/IO"}
puts $f "PAD	u_ld/IOBUF_89	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_90}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_90"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_90/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[18]}} {error "Pad connection differs: u_ld/IOBUF_90/IO"}
puts $f "PAD	u_ld/IOBUF_90	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_91}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_91"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_91/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[19]}} {error "Pad connection differs: u_ld/IOBUF_91/IO"}
puts $f "PAD	u_ld/IOBUF_91	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_92}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_92"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_92/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[20]}} {error "Pad connection differs: u_ld/IOBUF_92/IO"}
puts $f "PAD	u_ld/IOBUF_92	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_93}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_93"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_93/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[21]}} {error "Pad connection differs: u_ld/IOBUF_93/IO"}
puts $f "PAD	u_ld/IOBUF_93	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_94}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_94"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_94/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[22]}} {error "Pad connection differs: u_ld/IOBUF_94/IO"}
puts $f "PAD	u_ld/IOBUF_94	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_95}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_95"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_95/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[23]}} {error "Pad connection differs: u_ld/IOBUF_95/IO"}
puts $f "PAD	u_ld/IOBUF_95	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_11}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_11"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_11/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[2]}} {error "Pad connection differs: u_ld/IOBUFDS_11/IO"}
puts $f "PAD	u_ld/IOBUFDS_11	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_11/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[2]}} {error "Pad connection differs: u_ld/IOBUFDS_11/IOB"}
puts $f "PAD	u_ld/IOBUFDS_11	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_96}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_96"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_96/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[24]}} {error "Pad connection differs: u_ld/IOBUF_96/IO"}
puts $f "PAD	u_ld/IOBUF_96	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_97}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_97"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_97/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[25]}} {error "Pad connection differs: u_ld/IOBUF_97/IO"}
puts $f "PAD	u_ld/IOBUF_97	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_98}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_98"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_98/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[26]}} {error "Pad connection differs: u_ld/IOBUF_98/IO"}
puts $f "PAD	u_ld/IOBUF_98	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_99}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_99"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_99/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[27]}} {error "Pad connection differs: u_ld/IOBUF_99/IO"}
puts $f "PAD	u_ld/IOBUF_99	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_100}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_100"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_100/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[28]}} {error "Pad connection differs: u_ld/IOBUF_100/IO"}
puts $f "PAD	u_ld/IOBUF_100	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_101}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_101"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_101/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[29]}} {error "Pad connection differs: u_ld/IOBUF_101/IO"}
puts $f "PAD	u_ld/IOBUF_101	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_102}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_102"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_102/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[30]}} {error "Pad connection differs: u_ld/IOBUF_102/IO"}
puts $f "PAD	u_ld/IOBUF_102	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_103}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_103"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_103/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[31]}} {error "Pad connection differs: u_ld/IOBUF_103/IO"}
puts $f "PAD	u_ld/IOBUF_103	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_12}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_12"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_12/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[3]}} {error "Pad connection differs: u_ld/IOBUFDS_12/IO"}
puts $f "PAD	u_ld/IOBUFDS_12	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_12/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[3]}} {error "Pad connection differs: u_ld/IOBUFDS_12/IOB"}
puts $f "PAD	u_ld/IOBUFDS_12	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_104}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_104"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_104/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[32]}} {error "Pad connection differs: u_ld/IOBUF_104/IO"}
puts $f "PAD	u_ld/IOBUF_104	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_105}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_105"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_105/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[33]}} {error "Pad connection differs: u_ld/IOBUF_105/IO"}
puts $f "PAD	u_ld/IOBUF_105	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_106}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_106"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_106/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[34]}} {error "Pad connection differs: u_ld/IOBUF_106/IO"}
puts $f "PAD	u_ld/IOBUF_106	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_107}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_107"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_107/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[35]}} {error "Pad connection differs: u_ld/IOBUF_107/IO"}
puts $f "PAD	u_ld/IOBUF_107	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_108}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_108"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_108/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[36]}} {error "Pad connection differs: u_ld/IOBUF_108/IO"}
puts $f "PAD	u_ld/IOBUF_108	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_109}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_109"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_109/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[37]}} {error "Pad connection differs: u_ld/IOBUF_109/IO"}
puts $f "PAD	u_ld/IOBUF_109	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_110}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_110"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_110/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[38]}} {error "Pad connection differs: u_ld/IOBUF_110/IO"}
puts $f "PAD	u_ld/IOBUF_110	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_111}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_111"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_111/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[39]}} {error "Pad connection differs: u_ld/IOBUF_111/IO"}
puts $f "PAD	u_ld/IOBUF_111	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_13}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_13"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_13/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[4]}} {error "Pad connection differs: u_ld/IOBUFDS_13/IO"}
puts $f "PAD	u_ld/IOBUFDS_13	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_13/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[4]}} {error "Pad connection differs: u_ld/IOBUFDS_13/IOB"}
puts $f "PAD	u_ld/IOBUFDS_13	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_112}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_112"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_112/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[40]}} {error "Pad connection differs: u_ld/IOBUF_112/IO"}
puts $f "PAD	u_ld/IOBUF_112	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_113}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_113"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_113/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[41]}} {error "Pad connection differs: u_ld/IOBUF_113/IO"}
puts $f "PAD	u_ld/IOBUF_113	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_114}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_114"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_114/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[42]}} {error "Pad connection differs: u_ld/IOBUF_114/IO"}
puts $f "PAD	u_ld/IOBUF_114	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_115}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_115"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_115/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[43]}} {error "Pad connection differs: u_ld/IOBUF_115/IO"}
puts $f "PAD	u_ld/IOBUF_115	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_116}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_116"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_116/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[44]}} {error "Pad connection differs: u_ld/IOBUF_116/IO"}
puts $f "PAD	u_ld/IOBUF_116	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_117}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_117"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_117/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[45]}} {error "Pad connection differs: u_ld/IOBUF_117/IO"}
puts $f "PAD	u_ld/IOBUF_117	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_118}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_118"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_118/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[46]}} {error "Pad connection differs: u_ld/IOBUF_118/IO"}
puts $f "PAD	u_ld/IOBUF_118	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_119}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_119"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_119/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[47]}} {error "Pad connection differs: u_ld/IOBUF_119/IO"}
puts $f "PAD	u_ld/IOBUF_119	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_14}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_14"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_14/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[5]}} {error "Pad connection differs: u_ld/IOBUFDS_14/IO"}
puts $f "PAD	u_ld/IOBUFDS_14	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_14/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[5]}} {error "Pad connection differs: u_ld/IOBUFDS_14/IOB"}
puts $f "PAD	u_ld/IOBUFDS_14	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_120}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_120"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_120/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[48]}} {error "Pad connection differs: u_ld/IOBUF_120/IO"}
puts $f "PAD	u_ld/IOBUF_120	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_121}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_121"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_121/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[49]}} {error "Pad connection differs: u_ld/IOBUF_121/IO"}
puts $f "PAD	u_ld/IOBUF_121	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_122}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_122"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_122/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[50]}} {error "Pad connection differs: u_ld/IOBUF_122/IO"}
puts $f "PAD	u_ld/IOBUF_122	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_123}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_123"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_123/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[51]}} {error "Pad connection differs: u_ld/IOBUF_123/IO"}
puts $f "PAD	u_ld/IOBUF_123	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_124}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_124"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_124/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[52]}} {error "Pad connection differs: u_ld/IOBUF_124/IO"}
puts $f "PAD	u_ld/IOBUF_124	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_125}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_125"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_125/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[53]}} {error "Pad connection differs: u_ld/IOBUF_125/IO"}
puts $f "PAD	u_ld/IOBUF_125	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_126}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_126"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_126/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[54]}} {error "Pad connection differs: u_ld/IOBUF_126/IO"}
puts $f "PAD	u_ld/IOBUF_126	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_127}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_127"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_127/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[55]}} {error "Pad connection differs: u_ld/IOBUF_127/IO"}
puts $f "PAD	u_ld/IOBUF_127	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_15}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_15"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_15/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[6]}} {error "Pad connection differs: u_ld/IOBUFDS_15/IO"}
puts $f "PAD	u_ld/IOBUFDS_15	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_15/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[6]}} {error "Pad connection differs: u_ld/IOBUFDS_15/IOB"}
puts $f "PAD	u_ld/IOBUFDS_15	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_128}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_128"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_128/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[56]}} {error "Pad connection differs: u_ld/IOBUF_128/IO"}
puts $f "PAD	u_ld/IOBUF_128	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_129}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_129"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_129/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[57]}} {error "Pad connection differs: u_ld/IOBUF_129/IO"}
puts $f "PAD	u_ld/IOBUF_129	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_130}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_130"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_130/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[58]}} {error "Pad connection differs: u_ld/IOBUF_130/IO"}
puts $f "PAD	u_ld/IOBUF_130	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_131}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_131"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_131/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[59]}} {error "Pad connection differs: u_ld/IOBUF_131/IO"}
puts $f "PAD	u_ld/IOBUF_131	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_132}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_132"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_132/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[60]}} {error "Pad connection differs: u_ld/IOBUF_132/IO"}
puts $f "PAD	u_ld/IOBUF_132	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_133}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_133"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_133/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[61]}} {error "Pad connection differs: u_ld/IOBUF_133/IO"}
puts $f "PAD	u_ld/IOBUF_133	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_134}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_134"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_134/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[62]}} {error "Pad connection differs: u_ld/IOBUF_134/IO"}
puts $f "PAD	u_ld/IOBUF_134	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_135}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_135"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_135/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[63]}} {error "Pad connection differs: u_ld/IOBUF_135/IO"}
puts $f "PAD	u_ld/IOBUF_135	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_16}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_16"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_16/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[7]}} {error "Pad connection differs: u_ld/IOBUFDS_16/IO"}
puts $f "PAD	u_ld/IOBUFDS_16	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_16/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[7]}} {error "Pad connection differs: u_ld/IOBUFDS_16/IOB"}
puts $f "PAD	u_ld/IOBUFDS_16	IOB	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_136}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_136"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_136/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[64]}} {error "Pad connection differs: u_ld/IOBUF_136/IO"}
puts $f "PAD	u_ld/IOBUF_136	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_137}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_137"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_137/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[65]}} {error "Pad connection differs: u_ld/IOBUF_137/IO"}
puts $f "PAD	u_ld/IOBUF_137	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_138}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_138"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_138/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[66]}} {error "Pad connection differs: u_ld/IOBUF_138/IO"}
puts $f "PAD	u_ld/IOBUF_138	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_139}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_139"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_139/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[67]}} {error "Pad connection differs: u_ld/IOBUF_139/IO"}
puts $f "PAD	u_ld/IOBUF_139	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_140}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_140"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_140/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[68]}} {error "Pad connection differs: u_ld/IOBUF_140/IO"}
puts $f "PAD	u_ld/IOBUF_140	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_141}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_141"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_141/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[69]}} {error "Pad connection differs: u_ld/IOBUF_141/IO"}
puts $f "PAD	u_ld/IOBUF_141	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_142}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_142"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_142/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[70]}} {error "Pad connection differs: u_ld/IOBUF_142/IO"}
puts $f "PAD	u_ld/IOBUF_142	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUF_143}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUF"} {error "Buffer differs: u_ld/IOBUF_143"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUF_143/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dq[71]}} {error "Pad connection differs: u_ld/IOBUF_143/IO"}
puts $f "PAD	u_ld/IOBUF_143	IO	[get_property NAME $ports]"
set cell [get_cells {u_ld/IOBUFDS_17}]
if {[llength $cell]!=1 || [get_property REF_NAME $cell] ne "IOBUFDS"} {error "Buffer differs: u_ld/IOBUFDS_17"}
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_17/IO}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_p[8]}} {error "Pad connection differs: u_ld/IOBUFDS_17/IO"}
puts $f "PAD	u_ld/IOBUFDS_17	IO	[get_property NAME $ports]"
set nets [get_nets -segments -of_objects [get_pins {u_ld/IOBUFDS_17/IOB}]]
set ports [get_ports -of_objects $nets]
if {[llength $ports]!=1 || [get_property NAME $ports] ne {ddram1_dqs_n[8]}} {error "Pad connection differs: u_ld/IOBUFDS_17/IOB"}
puts $f "PAD	u_ld/IOBUFDS_17	IOB	[get_property NAME $ports]"
close $f
close_design
exit
