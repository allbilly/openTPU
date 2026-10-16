#!/usr/bin/env python3
"""Build an isolated full native-RTL Vivado DDR800/XDMA PCIe image.

Creates bit/MCS files only after route and timing gates. Never opens hardware
or programs flash; the user's flash authorization remains conditional.
"""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from fedora_prepare_litedram import profile, FILES
from fedora_vivado_ddr800_qualify import CORE, PROFILE, describe

SETTINGS = Path(expand_paths('@VIVADO_ROOT@/settings64.sh'))
VIVADO = Path(expand_paths('@VIVADO_BIN@/vivado'))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--core', type=Path, default=CORE,
                    help='Checked DDR800 core; use bitstreams/ch1-pcie-2gb/core for the release')
    ap.add_argument('--build-id', default='5b1e646c',
                    help='One to eight hexadecimal digits exposed in the BUILD_ID register')
    ap.add_argument('--prepare-only', action='store_true',
                    help='Write and check the source snapshot without running Vivado')
    args = ap.parse_args()
    if not re.fullmatch(r'[0-9a-fA-F]{1,8}', args.build_id):
        ap.error('--build-id must contain one to eight hexadecimal digits')
    core = args.core.resolve()
    out = args.out.resolve()
    if out.exists():
        ap.error('Choose a fresh build directory')
    checked = profile(core)
    if checked['parameters'] != dict(CORE_KHZ=100000, DDR_MTS=800):
        raise ValueError('Wrong checked full DDR800 core')
    memory = json.loads((core/'openxc7-profile.json').read_text())
    ch1 = memory.get('physical_user_channels') == [1]
    if ch1 and any(memory.get(key) != value for key, value in {
            'usable_logical_bytes': 1 << 31, 'virtual_channel_bytes': 1 << 30,
            'calibration_mask': 2,
            'user_address_mapping': 'physical CH1 beat = (virtual beat << 1) | virtual channel'
    }.items()):
        raise ValueError('CH1 recovery core has inconsistent capacity, calibration or mapping')
    out.mkdir(parents=True)
    src = out/'source'
    shutil.copytree(ROOT/'rtl', src/'rtl')
    board = src/'boards/ypcb-00338'
    shutil.copytree(ROOT/'boards/ypcb-00338/vivado', board/'vivado')
    shutil.copytree(ROOT/'boards/ypcb-00338/constraints', board/'constraints')
    (board/'litedram').mkdir()
    for name in FILES.values():
        shutil.copy2(core/name, board/'litedram'/name)
    shutil.copy2(core/'openxc7-profile.json', board/'litedram/openxc7-profile.json')
    if ch1:
        ctrl = src/'rtl/boards/ypcb-00338/otpu_ctrl.sv'
        text = ctrl.read_text()
        marker = "      10'h016: r_d <= 32'(ACT_ROWS);"
        if text.count(marker) != 1 or "10'h017:" in text:
            raise ValueError('Unexpected control-register recovery marker layout')
        ctrl.write_text(text.replace(marker, marker +
                        "\n      10'h017: r_d <= 32'h08000102; // CH1 recovery, ABI1, 2048 MiB"))
    create = board/'vivado/create_project.tcl'
    original = create.read_text()
    old = 'if {$DDR_SPEED != 1066} { error "DDR3-$DDR_SPEED: the LiteDRAM core is generated for DDR3-1066" }'
    if original.count(old) != 1:
        raise ValueError('Unexpected project speed guard')
    create.write_text('set_param general.maxThreads 8\n'+original.replace(old,
                      'if {$DDR_SPEED != 800} {error "Requires the pinned DDR800 core"}'))
    # Reuse the established timing/route parsers in a standalone frozen gate.
    parser = ROOT/'tools/openxc7_mapped_route_review.py'
    text = parser.read_text()
    tree = ast.parse(text)
    definitions = '\n\n'.join(ast.get_source_segment(text,n) for n in tree.body
                             if isinstance(n,ast.FunctionDef) and n.name in ('timing_summary','route_summary'))
    gate = out/'pre_bit_gate.py'
    gate.write_text('from pathlib import Path\nimport re,json,sys\n'+definitions+'''
timing=timing_summary(sys.argv[1])
route=route_summary(sys.argv[2])
assert all(timing[k]>=0 for k in ['wns_ns','whs_ns','wpws_ns']),timing
assert all(timing[k]==0 for k in ['setup_failing_endpoints','hold_failing_endpoints','pulse_failing_endpoints']),timing
assert route['routable nets']==route['fully routed nets'] and route['nets with routing errors']==0,route
Path(sys.argv[3]).write_text(json.dumps(dict(status='FULL_NATIVE_PCIE_ROUTE_AND_NUMERICAL_TIMING_PASS_HARDWARE_PENDING',timing=timing,route=route),indent=2)+'\\n')
''')
    build = board/'vivado/build.tcl'
    text = build.read_text()
    marker = '# ---- bitstream, written from the routed design opened above'
    if text.count(marker)!=1:
        raise ValueError('Unexpected build gate insertion point')
    strict = '''
write_checkpoint -force $out/final-routed.dcp
report_route_status -file $out/reports/route-status.rpt
set failures {}
foreach item [get_drc_violations -quiet] {
    set severity [get_property SEVERITY $item]
    if {[regexp -nocase {^(Error|Critical Warning)$} $severity]} {lappend failures $item}
}
if {[llength $failures]} {error "DRC errors/critical warnings: $failures"}
exec python3 $::env(OTPU_PRE_BIT_GATE) $out/reports/timing_summary.rpt $out/reports/route-status.rpt $out/pre-bit-gates.json
'''
    build.write_text('set_param general.maxThreads 8\n'+text.replace(marker,strict+'\n'+marker))
    record = dict(status='PREPARED', started_utc=datetime.now(timezone.utc).isoformat(),
                  profile=PROFILE, pcie='XDMA Gen2 x8', top='otpu_fpga_top_ld',
                  hardware_accessed=False, flash_written=False, hardware_ready=False,
                  build_id=args.build_id, core=str(core),
                  physical_user_channels=[1] if ch1 else [0, 1],
                  usable_logical_bytes=(1 << 31) if ch1 else (1 << 32),
                  virtual_channel_bytes=(1 << 30) if ch1 else (1 << 31),
                  calibration_mask=2 if ch1 else 3,
                  user_address_mapping=memory.get('user_address_mapping'),
                  memory_profile_register='0x5c: 0x08000102' if ch1 else None,
                  threads_requested=8, repository_revision=subprocess.check_output(
                      ['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                  reference_calibration_profile=describe(checked['manifest']),
                  adaptations=['Pinned generated DDR800 core replaces the default DDR1066 core',
                               'Snapshot project guard selects DDR800, core remains 100 MHz',
                               'Eight native workers and strict setup/hold/pulse/route/DRC pre-bit gates'],
                  mcs_scope='Prospective 64 MiB BPI x16 file; physical chip and boot verification still required',
                  sources=[describe(p) for p in sorted(src.rglob('*')) if p.is_file()],
                  gate=describe(gate), parser_source=describe(parser), tool=describe(VIVADO))
    def save():
        tmp=out/'manifest.json.tmp'
        tmp.write_text(json.dumps(record,indent=2)+'\n')
        tmp.replace(out/'manifest.json')
    save()
    if args.prepare_only:
        record['status'] = 'PREPARED_ONLY_IMPLEMENTATION_NOT_RUN'
        save()
        return 0
    env_data=subprocess.check_output(['/bin/bash','-c','source "$1"\nenv -0',
                                     'vivado-env',str(SETTINGS)])
    env=dict(item.decode().split('=',1) for item in env_data.split(b'\0') if item)
    env.update(OTPU_FAST='0',PCIE_GEN='2',OTPU_IP_CACHE=str(out/'ip-cache'),
               OTPU_PRE_BIT_GATE=str(gate))
    project=out/'project'
    try:
        stages=[
            ('create',[str(VIVADO),'-mode','batch','-nojournal','-nolog','-source',str(create),
                       '-tclargs','800',str(project),'4','100',args.build_id,'2','8','4','1','systolic']),
            ('build',[str(VIVADO),'-mode','batch','-nojournal','-nolog','-source',str(build),
                      '-tclargs',str(project),'8','full',''])]
        for name, command in stages:
            record['status']=name.upper()+'_RUNNING'
            (out/(name+'.command.json')).write_text(json.dumps(command,indent=2)+'\n')
            with (out/(name+'.log')).open('w') as log:
                child=subprocess.Popen(command,cwd=src,env=env,stdout=log,stderr=subprocess.STDOUT)
                record['child_pid']=child.pid
                save()
                code=child.wait()
            record.pop('child_pid',None)
            record[name+'_exit']=code
            (out/(name+'.exit')).write_text(f'{code}\n')
            save()
            if code:
                raise RuntimeError(name+' exited '+str(code))
        gates=json.loads((project/'pre-bit-gates.json').read_text())
        if gates['status']!='FULL_NATIVE_PCIE_ROUTE_AND_NUMERICAL_TIMING_PASS_HARDWARE_PENDING':
            raise ValueError('Full pre-bit gates absent')
        status = ('FULL_NATIVE_VIVADO_PCIE_CH1_RECOVERY_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING'
                  if ch1 else 'FULL_NATIVE_VIVADO_PCIE_DDR800_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING')
        record.update(status=status,
                      gates=gates, outputs={name:describe(project/name) for name in
                                          ['otpu.bit','otpu.mcs','final-routed.dcp']})
        return 0
    except Exception as error:
        record.update(status='FAIL',error=repr(error))
        print(record['error'],flush=True)
        return 1
    finally:
        record['finished_utc']=datetime.now(timezone.utc).isoformat()
        save()


if __name__=='__main__':
    raise SystemExit(main())

