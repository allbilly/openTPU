#!/usr/bin/env python3
"""Build the full CH1 recovery accelerator with the standalone USER2 host.

Native Vivado RTL synthesis/implementation, 100 MHz, DDR800, full compute.
Creates an SRAM bitstream; never opens hardware or writes flash.
"""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from fedora_prepare_litedram import profile, FILES


def describe(path):
    path=Path(path).resolve()
    with path.open('rb') as f: sha=hashlib.file_digest(f,'sha256').hexdigest()
    return dict(path=str(path),bytes=path.stat().st_size,sha256=sha)


LATE=r'''
set bscan [get_cells -hier -filter {REF_NAME == BSCANE2}]
if {[llength $bscan] != 1 || [get_property JTAG_CHAIN $bscan] != 2} {error "USER2 primitive differs"}
create_clock -name jtag_tck -period 166.666667 [get_pins $bscan/TCK]
set core [get_clocks -of_objects [get_nets ld_sys_clk]]
if {[llength $core] != 1 || abs([get_property PERIOD $core]-10.0)>0.00001} {error "100 MHz core clock missing"}
foreach ch {0 1} {
    set inst [get_cells -quiet u_sys/u_ch$ch]
    if {[llength $inst] != 1} {error "Native channel instance missing"}
    current_instance $inst
    source $src/boards/ypcb-00338/constraints/otpu_mem_ch.tcl
    current_instance
}
set regs50 [filter [all_registers -clock sys_clk_50] {NAME =~ u_ld/*}]
if {[llength $regs50] != 16} {error "LiteDRAM clock-reset chains differ"}
set_false_path -from $core -to $regs50
foreach {source target bound} {
    held req 20.0
    response response_tck 300.0
} {
    set a [get_cells -quiet -hier -filter "NAME =~ u_mailbox/${source}_reg*"]
    set b [get_cells -quiet -hier -filter "NAME =~ u_mailbox/${target}_reg*"]
    if {![llength $a] || ![llength $b]} {error "Mailbox payload endpoint missing"}
    set_max_delay -datapath_only $bound -from $a -to $b
    set_false_path -hold -from $a -to $b
    set_bus_skew $bound -from $a -to $b
}
foreach prefix {rq_sync rs_sync} {
    set stages [get_cells -quiet -hier -filter "NAME =~ u_mailbox/${prefix}_reg*"]
    set first [get_cells -quiet "u_mailbox/${prefix}_reg\[0\]"]
    if {[llength $stages] != 3 || [llength $first] != 1} {error "Mailbox toggle synchronizer differs"}
    set_property ASYNC_REG TRUE $stages
    set_property DONT_TOUCH TRUE $stages
    set_false_path -to [get_pins $first/D]
}
'''


BUILD=r'''
set_param general.maxThreads 8
set src [lindex $argv 0]
set out [lindex $argv 1]
create_project -force ch1_jtag $out/project -part xc7k480tffg1156-2
foreach f $::env(OTPU_JTAG_SV) {read_verilog -sv $src/$f}
read_verilog $src/boards/ypcb-00338/litedram/otpu_litedram.v
add_files -norecurse $src/boards/ypcb-00338/litedram/otpu_litedram_mem.init
set_property FILE_TYPE {Memory Initialization Files} [get_files otpu_litedram_mem.init]
set_property verilog_define {SYNTHESIS} [current_fileset]
set_property top otpu_fpga_top_openxc7_jtag [current_fileset]
set_property generic {MCOLS=4 ACT_ROWS=4 VPU_CL=2 MXU_IMPL=2 LANES=8 CORE_KHZ=100000 DDR_MTS=800 BUILD_ID=32'h5b1e646c DSTEP=1'b1} [current_fileset]
read_xdc $src/boards/ypcb-00338/litedram/otpu_litedram.xdc
read_xdc $out/board.xdc
synth_design -top otpu_fpga_top_openxc7_jtag -part xc7k480tffg1156-2 -flatten_hierarchy rebuilt -retiming
write_checkpoint -force $out/synth.dcp
source $out/late.tcl
opt_design -directive Explore
place_design -directive Explore
write_checkpoint -force $out/placed.dcp
phys_opt_design -directive AggressiveExplore
route_design -directive Explore -tns_cleanup
phys_opt_design -directive AggressiveExplore
write_checkpoint -force $out/final-routed.dcp
file mkdir $out/reports
report_route_status -file $out/reports/route.rpt
report_timing_summary -report_unconstrained -file $out/reports/timing.rpt
report_bus_skew -file $out/reports/bus-skew.rpt
report_cdc -details -file $out/reports/cdc.rpt
report_clocks -file $out/reports/clocks.rpt
report_utilization -hierarchical -file $out/reports/util.rpt
report_drc -file $out/reports/drc.rpt
report_io -file $out/reports/io.rpt
foreach v [get_drc_violations -quiet] {
    if {[get_property SEVERITY $v] in {Error {Critical Warning}}} {error "Unresolved DRC: $v"}
}
set f [open $out/checkpoint.tsv w]
puts $f "PART\t[get_property PART [current_design]]"
puts $f "TOP\t[get_property NAME [current_design]]"
foreach key {CFGBVS CONFIG_VOLTAGE} {puts $f "$key\t[get_property $key [current_design]]"}
foreach p [lsort [get_ports]] {puts $f "PORT\t$p\t[get_property PACKAGE_PIN $p]\t[get_property IOSTANDARD $p]"}
puts $f "BSCAN\t[get_property JTAG_CHAIN [get_cells -hier -filter {REF_NAME == BSCANE2}]]"
close $f
exec python3 $out/pre_bit_gate.py $out
write_bitstream -force $out/otpu-ch1-jtag.bit
close_project
exit
'''


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--core',required=True,type=Path)
    ap.add_argument('--ecc-preparation',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    a=ap.parse_args();core=a.core.resolve();out=a.out.resolve()
    if out.exists():ap.error('Choose a fresh build directory')
    checked=profile(core);p=json.loads((core/'openxc7-profile.json').read_text())
    assert checked['parameters']==dict(CORE_KHZ=100000,DDR_MTS=800)
    assert p['physical_user_channels']==[1] and p['usable_logical_bytes']==1<<31 and p['calibration_mask']==2
    out.mkdir(parents=True);src=out/'source';shutil.copytree(ROOT/'rtl',src/'rtl')
    board=src/'boards/ypcb-00338';shutil.copytree(ROOT/'boards/ypcb-00338/constraints',board/'constraints')
    (board/'litedram').mkdir()
    for name in list(FILES.values())+['openxc7-profile.json']:shutil.copy2(core/name,board/'litedram'/name)
    ctrl=src/'rtl/boards/ypcb-00338/otpu_ctrl.sv';text=ctrl.read_text();marker="      10'h016: r_d <= 32'(ACT_ROWS);";assert text.count(marker)==1
    ctrl.write_text(text.replace(marker,marker+"\n      10'h017: r_d <= 32'h08000102; // CH1 recovery, ABI1, 2048 MiB"))
    create=(ROOT/'boards/ypcb-00338/vivado/create_project.tcl').read_text()
    sv=re.search(r'set rtl \[list(.*?)\]\s*\nadd_files',create,re.S)[1].replace('\\','').split()
    sv.remove('rtl/boards/ypcb-00338/otpu_fpga_top_ld.sv')
    sv+=['rtl/boards/ypcb-00338/otpu_jtag_mailbox.sv','rtl/boards/ypcb-00338/otpu_jtag_axi.sv','rtl/boards/ypcb-00338/otpu_fpga_top_openxc7_jtag.sv']
    assert all((src/x).is_file() for x in sv)
    reference=ROOT/'build/fedora-openxc7/full-mapped-vivado-bitstream-top-20261012T183600Z'
    rm=json.loads((reference/'manifest.json').read_text())
    assert rm['status']=='FULL_MAPPED_REFERENCE_BITSTREAM_TIMING_DRC_PINS_PACKET_PASS_HARDWARE_PENDING'
    pins=reference/'pins.tsv'; rows=[x.split('\t') for x in pins.read_text().splitlines()[1:]]
    props={}
    for port,key,value in rows:
        props.setdefault(port,{})[key]=value
    assert len(props)==243 and all({'PACKAGE_PIN','IOSTANDARD'}<=set(v) for v in props.values())
    # DDR pads/standards come from the selected new core; ordinary pins are the
    # already exercised standalone board mapping. Check all pads again after route.
    xdc=['create_clock -name sys_clk_50 -period 20.0 [get_ports SYS_CLK]',
         'set_property LOC MMCME2_ADV_X0Y2 [get_cells u_ld/ldmmcm0]',
         'set_property LOC MMCME2_ADV_X0Y6 [get_cells u_ld/ldmmcm1]',
         'set_property CFGBVS GND [current_design]',
         'set_property CONFIG_VOLTAGE 1.8 [current_design]',
         'set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]',
         'set_property BITSTREAM.CONFIG.UNUSEDPIN PULLNONE [current_design]']
    for port,values in sorted(props.items()):
        if not port.startswith('ddram'):
            for key,value in values.items():
                assert re.fullmatch('[A-Z_0-9]+',key) and re.fullmatch('[A-Za-z0-9_.]+',value)
                xdc.append('set_property '+key+' '+value+' [get_ports {'+port+'}]')
    xdc+=['set_false_path -to [get_ports {led[*]}]',
          'set_false_path -from [get_ports {lm73_scl lm73_sda lm73_alert_n smb_scl smb_sda}]',
          'set_false_path -to [get_ports {lm73_scl lm73_sda smb_scl smb_sda}]']
    (out/'board.xdc').write_text('\n'.join(xdc)+'\n');(out/'late.tcl').write_text(LATE);(out/'build.tcl').write_text(BUILD)
    (out/'expected-pins.json').write_text(json.dumps(props,indent=2)+'\n')
    gate='''from pathlib import Path
import json,re,sys
p=Path(sys.argv[1])
t=(p/'reports/timing.rpt').read_text().split('| Design Timing Summary',1)[1]
r=re.search(r'^\\s*WNS\\(ns\\).*\\n\\s*-+.*\\n\\s*([-+0-9. ]+)\\s*$',t,re.M)
v=r[1].split();assert len(v)==12
assert all(float(v[i])>=0 for i in (0,4,8)) and all(float(v[i])==0 for i in (2,6,10)),v
text=(p/'reports/route.rpt').read_text()
def count(label):
 x=re.findall(r'# of '+label+r'\\.+\\s*:\\s*(\\d+)\\s*:',text);assert len(x)==1;return int(x[0])
assert count('routable nets')==count('fully routed nets')>0 and count('nets with routing errors')==0
lines=[x.split('\\t') for x in (p/'checkpoint.tsv').read_text().splitlines()]
meta={x[0]:x[1] for x in lines if len(x)==2}
assert meta==dict(PART='xc7k480tffg1156-2',TOP='otpu_fpga_top_openxc7_jtag',CFGBVS='GND',CONFIG_VOLTAGE='1.8',BSCAN='2'),meta
ports={x[1]:dict(PACKAGE_PIN=x[2],IOSTANDARD=x[3]) for x in lines if x[0]=='PORT'}
expected=json.loads((p/'expected-pins.json').read_text());assert len(ports)==len(expected)==243
assert all(ports[n]=={k:v for k,v in props.items() if k in ('PACKAGE_PIN','IOSTANDARD')} for n,props in expected.items())
(p/'pre-bit-gates.json').write_text(json.dumps(dict(status='CH1_JTAG_ROUTE_TIMING_DRC_PINS_PASS_CDC_REVIEW_PENDING',timing_columns=v,routable_nets=count('routable nets')),indent=2)+'\\n')
'''
    (out/'pre_bit_gate.py').write_text(gate);compile(gate,str(out/'pre_bit_gate.py'),'exec')
    command=[expand_paths('@VIVADO_BIN@/vivado'),'-mode','batch','-nojournal','-nolog','-source',str(out/'build.tcl'),'-tclargs',str(src),str(out)]
    (out/'build.command.json').write_text(json.dumps(command,indent=2)+'\n')
    record=dict(status='PREPARED',started_utc=datetime.now(timezone.utc).isoformat(),top='otpu_fpga_top_openxc7_jtag',part='xc7k480tffg1156-2',
        profile=dict(MCOLS=4,ACT_ROWS=4,VPU_CL=2,MXU_IMPL=2,LANES=8,CORE_KHZ=100000,DDR_MTS=800),host='USER2 JTAG',physical_user_channels=[1],logical_capacity_bytes=1<<31,
        hardware_accessed=False,flash_written=False,physical_model_verified=False,threads_requested=8,
        source_files=[describe(src/x) for x in sv]+[describe(board/'litedram'/name) for name in list(FILES.values())+['openxc7-profile.json']],
        reference_pins=describe(pins),core=str(core),ecc_preparation=str(a.ecc_preparation.resolve()),
        ecc_gate='Full four-port ECC test still required before programming; offline build may overlap',helper=describe(Path(__file__)))
    def save():
        tmp=out/'manifest.json.tmp';tmp.write_text(json.dumps(record,indent=2)+'\n');tmp.replace(out/'manifest.json')
    try:
        save();env=dict(os.environ,OTPU_JTAG_SV=' '.join(sv))
        with (out/'build.log').open('w') as log:
            child=subprocess.Popen(command,cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
            record.update(status='NATIVE_VIVADO_BUILD_RUNNING',child_pid=child.pid);save();code=child.wait()
        record.pop('child_pid',None);record['build_exit']=code;(out/'build.exit').write_text(str(code)+'\n')
        if code:raise RuntimeError('Vivado failed; inspect build.log')
        record.update(status='CH1_JTAG_BITSTREAM_BUILD_PASS_IMAGE_REVIEW_PENDING',outputs={name:describe(out/name) for name in ('otpu-ch1-jtag.bit','final-routed.dcp','pre-bit-gates.json')})
        return 0
    except Exception as e:
        record.update(status='FAIL',error=repr(e));print(record['error'],flush=True);return 1
    finally:
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':raise SystemExit(main())
