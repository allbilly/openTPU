#!/usr/bin/env python3
"""Check a completed full Vivado PCIe image without accessing hardware."""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from fedora_check_native_image import timing_summary, route_summary

COMPLETE = 'FULL_NATIVE_VIVADO_PCIE_CH1_RECOVERY_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING'
DUAL_COMPLETE = 'FULL_NATIVE_VIVADO_PCIE_DDR800_BUILD_PASS_IMAGE_AND_HARDWARE_REVIEW_PENDING'
FULL = dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2, MXU_IMPL=2, CORE_KHZ=100000, DDR_MTS=800)
CORE_FILENAMES = frozenset(('otpu_litedram.v', 'otpu_litedram.xdc',
                            'otpu_litedram_mem.init', 'csr.csv', 'sdram_init.py'))
VIVADO = Path(expand_paths('@VIVADO_BIN@/vivado'))
PACKETS = ROOT/'tools/check_vivado_bitstream.py'
CRC = ROOT/'build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/check-crc'
CRC_SHA = '047b5e0dc5c29193e2a1311eef1d09d44d8b08d37844fb6a771b1f9b76057802'


def require(ok, message):
    if not ok:
        raise ValueError(message)


def describe(path):
    path = Path(path).resolve()
    with path.open('rb') as stream:
        sha = hashlib.file_digest(stream, 'sha256').hexdigest()
    return dict(path=str(path), bytes=path.stat().st_size, sha256=sha)


def unchanged(item):
    actual = describe(item['path'])
    require(all(actual[k] == item[k] for k in ('bytes', 'sha256')),
            'Recorded file changed: '+item['path'])


def file_inventory(items, label):
    """Keep each canonical relative filename tied to exactly one digest."""
    inventory = {}
    for item in items:
        name = item['name']
        require(isinstance(name, str) and name and
                not Path(name).is_absolute() and '..' not in Path(name).parts and
                Path(name).as_posix() == name, 'Invalid '+label+' path: '+str(name))
        require(name not in inventory, 'Duplicate '+label+' file: '+name)
        inventory[name] = item
    return inventory


def compute_period_ns(manifest, core_khz):
    """Use the physical MMCM ratio; CORE_KHZ is only its rounded CSR value."""
    require(type(core_khz) is int and core_khz > 0 and
            manifest['profile']['CORE_KHZ'] == core_khz,
            'Compute clock profile differs')
    clock = manifest.get('compute_clock')
    if clock is None:
        # Before selectable clocks, this builder only requested exactly 100 MHz.
        require(core_khz == 100000, 'Exact compute clock metadata is missing')
        return 10.0
    keys = ('requested_mhz', 'actual_mhz', 'actual_hz', 'core_khz',
            'vco_mhz', 'output_divide')
    require(isinstance(clock, dict) and all(
        type(clock.get(key)) in (int, float) and math.isfinite(clock[key])
        for key in keys), 'Invalid exact compute clock metadata')
    requested, divide = clock['requested_mhz'], clock['output_divide']
    require(clock['vco_mhz'] == 800 and 800/128 <= requested <= 800 and
            1 <= divide <= 128 and divide*8 == math.floor(divide*8) and
            divide == math.floor(800/requested*8 + .5)/8,
            'Compute MMCM ratio differs from requested clock')
    actual = 800/divide
    require(math.isclose(clock['actual_mhz'], actual, rel_tol=0, abs_tol=1e-12) and
            clock['actual_hz'] == math.floor(actual*1e6) and
            clock['core_khz'] == core_khz == math.floor(actual*1000 + .5),
            'Exact compute clock and rounded register metadata disagree')
    return 1000*divide/800


def check_clock_periods(clocks, manifest, core_khz):
    expected = {'core_clk_otpu_bd_clk_wiz_0_0': compute_period_ns(manifest, core_khz),
                'crg_s7mmcm_clkout': 10.0}
    for name, period in expected.items():
        require(name in clocks and math.isfinite(clocks[name]) and
                abs(clocks[name] - period) < 0.001,
                'Implemented clock period differs: '+name)


def matched_dual_generation(generation, ecc, build):
    """Bind the dual core to its generator and the existing four-port ECC test.

    The original generator's ECC test has two ports. The historical witness
    expands only its port arrays, loops and read selector to four ports; verify
    that exact expansion before reusing the comparison log.
    """
    gm = json.loads((generation/'manifest.json').read_text())
    require(gm['status'] == 'GENERATED_PROFILE_PASS_IMPLEMENTATION_NOT_RUN',
            'Dual core generation did not pass')
    sources = gm['source']
    for path, expected in sources.items():
        require(describe(path)['sha256'] == expected, 'Generator source changed: '+path)
    core = generation/'core'
    profile = json.loads((core/'openxc7-profile.json').read_text())
    require(profile['parameters'] == dict(CORE_KHZ=100000, DDR_MTS=800) and
            profile.get('physical_user_channels', [0, 1]) == [0, 1],
            'Generation is not the dual-channel DDR800 core')
    inventory = file_inventory(profile['files'].values(), 'generated core')
    require(set(inventory) == CORE_FILENAMES, 'Incomplete generated core witness')
    matched = []
    for item in inventory.values():
        actual = describe(core/item['name'])
        require(all(actual[k] == item[k] for k in ('bytes', 'sha256')),
                'Generated core changed: '+item['name'])
        frozen = build/'source/boards/ypcb-00338/litedram'/item['name']
        require(describe(frozen)['sha256'] == actual['sha256'],
                'Implemented core differs from generation: '+item['name'])
        matched.append(actual)
    pinned = {}
    for name in ('ecc_ports.py', 'ecc_ports_check.py'):
        paths = [Path(p) for p in sources if Path(p).name == name]
        require(len(paths) == 1, 'Ambiguous ECC source: '+name)
        pinned[name] = paths[0]
    require(describe(ecc/'generator/ecc_ports.py')['sha256'] ==
            describe(pinned['ecc_ports.py'])['sha256'], 'ECC implementation differs')
    expected_test = pinned['ecc_ports_check.py'].read_text()
    require(expected_test.count('range(2)') == 7 and
            expected_test.count('pend = [[], []]') == 1 and
            expected_test.count('rnd.choice([None, None, 0, 1])') == 1,
            'Unexpected two-port test; review expansion explicitly')
    expected_test = expected_test.replace('range(2)', 'range(4)').replace(
        'pend = [[], []]', 'pend = [[], [], [], []]').replace(
        'rnd.choice([None, None, 0, 1])', 'rnd.choice([None, None, 0, 1, 2, 3])')
    require((ecc/'generator/ecc_ports_check.py').read_text() == expected_test,
            'Historical four-port test has additional changes')
    return dict(generation=describe(generation/'manifest.json'), matched_core_files=matched,
                implementation=describe(pinned['ecc_ports.py']),
                test=describe(ecc/'generator/ecc_ports_check.py'),
                adaptation='Exactly expand two ports to four; no other test changes',
                scope='ECC logic model only; does not qualify PHY, routing or physical DDR')


def matched_release_memory(directory, build, manifest):
    """Reuse historical ECC evidence only for the identical packaged memory core."""
    directory = directory.resolve()
    release = json.loads((directory/'manifest.json').read_text())
    inventory = file_inventory(release['files'], 'release')
    core_names = {'core/'+name for name in CORE_FILENAMES} | {'core/openxc7-profile.json'}
    require({name for name in inventory if name.startswith('core/')} == core_names,
            'Incomplete packaged memory-core witness')
    require({'otpu.bit', 'evidence/offline-image-review.json'} <= inventory.keys(),
            'Reference bitstream and ECC review must be hashed in the release inventory')
    for item in inventory.values():
        path = (directory/item['name']).resolve()
        require(path.is_relative_to(directory), 'Release path escapes its directory')
        actual = describe(path)
        require(all(actual[k] == item[k] for k in ('bytes', 'sha256')),
                'Packaged reference changed: '+item['name'])
    expected = dict(release['compute'], CORE_KHZ=manifest['profile']['CORE_KHZ'])
    require(manifest['profile'] == expected and
            release['memory']['physical_user_channels'] == [1] and
            release['memory']['logical_capacity_bytes'] == 1 << 31 and
            release['memory']['virtual_channel_bytes'] == 1 << 30 and
            release['memory']['ddr_mts'] == 800 and release['memory']['ecc'] is True,
            'Reference release is not the full CH1 DDR800 profile')
    pinned = []
    for name in sorted(core_names):
        item = inventory[name]
        source = build/'source/boards/ypcb-00338/litedram'/Path(item['name']).name
        require(describe(source)['sha256'] == item['sha256'],
                'Reused memory core differs: '+item['name'])
        pinned.append(item)
    evidence = directory/'evidence/offline-image-review.json'
    historical = json.loads(evidence.read_text())
    require(historical['status'] == 'CH1_PCIE_IMAGE_PACKET_CRC_PINS_ROUTE_TIMING_PASS_CDC_REVIEW_PENDING'
            and historical['ecc']['scope'] == 'Full four-port stock comparison' and
            historical['bitstream']['sha256'] == describe(directory/'otpu.bit')['sha256'],
            'Reference ECC evidence is missing or belongs to another image')
    return dict(scope='Historical four-port ECC comparison reused for the identical packaged core; not rerun',
                reference_manifest=describe(directory/'manifest.json'),
                reference_review=describe(evidence), matched_core_files=pinned,
                historical_ecc=historical['ecc'])


TCL = r'''
set_param general.maxThreads 8
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
if {[lindex $argv 2] eq "1"} {
    foreach ch {0 1} {
        set regs [get_cells -quiet -hier -filter "NAME =~ *wl7ddrphy${ch}_sys_rst_reg*"]
        if {![llength $regs]} {error "Serializer reset stage absent on channel $ch"}
        foreach c $regs {
            if {[get_property REF_NAME $c] ni {FDRE FDSE}} {error "Unexpected PHY reset register: $c"}
            puts $f "PHY_RESET\t$ch\t$c\t[get_property REF_NAME $c]"
        }
    }
}
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
close_design
exit
'''


def pin_settings(text):
    settings = {}
    rows = re.findall(r'set_property\s+(LOC|PACKAGE_PIN|IOSTANDARD)\s+(\S+)\s+\[get_ports\s+(?:\{([^}]+)\}|([^\s\]]+))\]',text)
    for prop,value,group,bare in rows:
        if prop in ('LOC','PACKAGE_PIN'):
            for name in (group or bare).split():
                settings.setdefault(name,{})['pin'] = value
    for prop,value,group,bare in rows:
        if prop == 'IOSTANDARD':
            for pattern in (group or bare).split():
                pattern = re.escape(pattern).replace(r'\*','.*')
                for name in settings:
                    if re.fullmatch(pattern,name):
                        settings[name]['standard'] = value
    return settings


def oob_review(out):
    """Check fresh reports after modeling both OOB modes for each PCIe lane."""
    text = (out/'oob-timing.rpt').read_text()
    timing = timing_summary(text)
    require(all(timing[k] >= 0 for k in ('WNS', 'WHS', 'WPWS')) and
            all(timing[k] == 0 for k in ('setup_failing', 'hold_failing', 'pulse_failing')),
            'OOB clock-model timing failed')
    route = route_summary((out/'oob-route.rpt').read_text())
    require(route['routable'] == route['fully_routed'] > 0 and route['routing_errors'] == 0,
            'OOB clock-model routing is incomplete')
    coverage = {name: int(value) for name, value in
                re.findall(r'^\d+\. checking (\w+) \((\d+)\)$', text, re.M)}
    for name in ('no_clock', 'constant_clock', 'pulse_width_clock',
                 'unconstrained_internal_endpoints', 'multiple_clock', 'generated_clocks',
                 'loops', 'partial_input_delay', 'partial_output_delay', 'latch_loops'):
        require(coverage.get(name) == 0, 'OOB timing coverage incomplete: '+name)
    pulse = re.findall(r'^\d+\. checking pulse_width_clock \((\d+)\)$',
                       (out/'oob-pulse-clock-pins.rpt').read_text(), re.M)
    require(pulse and set(pulse) == {'0'}, 'OOB pulse-clock coverage incomplete')
    skew = re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',
                      (out/'oob-bus-skew.rpt').read_text(), re.M)
    require(len(skew) == 39 and all(k == 'MET' and float(v) >= 0 for k, v in skew),
            'Not all 39 PCIe bus-skew constraints are met')
    clocks = [line.split('\t') for line in (out/'oob-clocks.tsv').read_text().splitlines()]
    require(len(clocks) == 32 and all(len(row) == 6 for row in clocks) and
            len({row[0] for row in clocks}) == 8 and len({row[4] for row in clocks}) == 32,
            'OOB model does not cover eight lanes and both master/divider modes')
    for row in clocks:
        require(float(row[2]) in (4.0, 8.0) and int(row[3]) in (2, 4) and
                abs(float(row[5]) - float(row[2]) * int(row[3])) < 0.0001,
                'OOB clock period differs')
    for reg in {row[0] for row in clocks}:
        modes = [(float(row[2]), int(row[3])) for row in clocks if row[0] == reg]
        require(len(modes) == 4 and set(modes) == {(4.0, 2), (4.0, 4), (8.0, 2), (8.0, 4)},
                'OOB lane does not cover every master/divider mode: '+reg)
    return dict(timing=timing, route=route, coverage=coverage,
                generated_clocks=32, bus_skew_constraints=39,
                minimum_bus_skew_slack_ns=min(float(v) for _, v in skew),
                netlist_placement_routing_modified=False, cdc_review='PENDING')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build', type=Path, required=True)
    ap.add_argument('--memory-profile', choices=('ch1', 'dual'), default='ch1',
                    help='Require either the CH1 2 GiB recovery mapping or both physical channels/4 GiB')
    ap.add_argument('--generation', type=Path)
    ap.add_argument('--ecc-preparation', type=Path)
    ap.add_argument('--reference-release', type=Path,
                    help='Reuse the historical ECC evidence for an identical packaged memory core')
    ap.add_argument('--core-khz', type=int, default=100000,
                    help='Expected compute CORE_KHZ; the DDR800 user clock stays 100000 kHz')
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--wait-unit', help='Wait for this exact build service; never restart it')
    ap.add_argument('--expect-serializer-reset-stage', action='store_true',
                    help='Require the isolated upstream serializer-reset registers after implementation')
    ap.add_argument('--review-oob-clocks', action='store_true',
                    help='Model both PCIe Gen2 OOB divider modes and check timing coverage/bus skew')
    a = ap.parse_args()
    dual = a.memory_profile == 'dual'
    complete = DUAL_COMPLETE if dual else COMPLETE
    if dual and a.reference_release:
        ap.error('Dual-channel review requires generation and ECC preparation, not a CH1 reference release')
    if a.core_khz <= 0:
        ap.error('--core-khz must be positive')
    if a.reference_release:
        if a.generation or a.ecc_preparation:
            ap.error('--reference-release cannot be combined with generation or ECC preparation')
    elif not (a.generation and a.ecc_preparation):
        ap.error('Supply --reference-release or both --generation and --ecc-preparation')
    build = a.build.resolve(); out = a.out.resolve()
    ecc = a.ecc_preparation.resolve() if a.ecc_preparation else None
    expected_profile = dict(FULL, CORE_KHZ=a.core_khz)
    require(not out.exists(), 'Choose a fresh qualification directory')
    out.mkdir(parents=True)
    r = dict(status='STARTING',hardware_accessed=False,physical_model_verified=False,
             flash_written=False,started_utc=datetime.now(timezone.utc).isoformat())
    def save():
        tmp=out/'manifest.json.tmp'; tmp.write_text(json.dumps(r,indent=2)+'\n'); tmp.replace(out/'manifest.json')
    try:
        save()
        invocation = None
        while True:
            m = json.loads((build/'manifest.json').read_text())
            require(m['status'] != 'FAIL', 'Vivado build failed: '+str(m.get('error')))
            if m['status'] == complete and (a.reference_release or (ecc/'four-port-ecc.exit').exists()):
                break
            require(a.wait_unit is not None, 'Build and full ECC comparison must finish')
            props = subprocess.check_output(['systemctl','--user','show',a.wait_unit,
                '-p','MainPID','-p','InvocationID','-p','ExecMainStatus','-p','Result'],text=True)
            props = dict(x.split('=',1) for x in props.splitlines())
            require(props['InvocationID'], 'Build service is missing')
            if invocation is None:
                invocation = props['InvocationID']
            require(invocation == props['InvocationID'], 'Build service invocation changed')
            require(props['ExecMainStatus'] == '0' and props['Result'] == 'success', 'Build service failed')
            if m['status'] != complete:
                pid=props['MainPID']; cmd=Path('/proc')/pid/'cmdline'
                require(pid != '0' and cmd.exists() and str(build).encode() in cmd.read_bytes(),
                        'Expected build process is no longer live')
            else:
                em=json.loads((ecc/'manifest.json').read_text())
                cmd=Path('/proc')/str(em.get('child_pid',0))/'cmdline'
                require(cmd.exists() and str(ecc/'generator/ecc_ports_check.py').encode() in cmd.read_bytes(),
                        'Expected ECC test is no longer live')
            r.update(status='WAITING_FOR_BUILD_AND_FULL_ECC',build_service=props,
                     observed_utc=datetime.now(timezone.utc).isoformat());save();time.sleep(5)
        require(m['profile'] == expected_profile and m['top'] == 'otpu_fpga_top_ld' and
                m['physical_user_channels'] == ([0, 1] if dual else [1]) and
                m['usable_logical_bytes'] == 1 << (32 if dual else 31) and
                m['virtual_channel_bytes'] == 1 << (31 if dual else 30) and
                m['calibration_mask'] == (3 if dual else 2), 'Wrong image memory/compute profile')
        r['memory_profile'] = a.memory_profile
        require(m['build_exit'] == m['create_exit'] == 0, 'Build commands did not pass')
        for item in m['sources'] + list(m['outputs'].values()):
            unchanged(item)
        if a.reference_release:
            r['ecc'] = matched_release_memory(a.reference_release, build, m)
        else:
            gm=json.loads((a.generation/'manifest.json').read_text())
            if dual:
                r['dual_generation'] = matched_dual_generation(a.generation.resolve(), ecc, build)
            else:
                for name in ('ecc_ports.py','ecc_ports_check.py'):
                    witnesses=gm.get('source_witness',gm.get('generator_sources',[]))
                    witness=next(x for x in witnesses if Path(x['path']).name == name)
                    unchanged(witness)
                    require(describe(ecc/'generator'/name)['sha256'] == witness['sha256'], 'ECC tested source differs')
            require((ecc/'four-port-ecc.exit').read_text().strip() == '0', 'Four-port ECC failed')
            elog=(ecc/'four-port-ecc.log').read_text()
            require(elog.splitlines()[-1] == 'PASS' and re.search(r'^1500 cycles,',elog,re.M),
                    'Full 1500-cycle ECC comparison did not pass')
            r['ecc'] = dict(log=describe(ecc/'four-port-ecc.log'),exit=describe(ecc/'four-port-ecc.exit'),scope='Full four-port stock comparison')
        bit=Path(m['outputs']['otpu.bit']['path']); dcp=Path(m['outputs']['final-routed.dcp']['path'])
        require(bit == build/'project/otpu.bit' and dcp == build/'project/final-routed.dcp', 'Artifact paths differ')
        spec=importlib.util.spec_from_file_location('ypcb_packets',PACKETS)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        packet=module.check(bit,m['outputs']['otpu.bit']['sha256'])
        require(packet['status'] == 'PASS' and packet['structure']['header']['a'].split(';',1)[0] == 'otpu_fpga_top_ld', 'Bitstream packet check failed')
        (out/'packets.json').write_text(json.dumps(packet,indent=2)+'\n')
        checker = CRC
        if checker.is_file():
            require(describe(checker)['sha256'] == CRC_SHA, 'CRC checker changed')
        else:
            checker = out/'check-crc'
            source = ROOT/'tools/openxc7_bitstream_crc.cc'
            command = ['g++', '-std=c++17', '-O2', str(source), '-o', str(checker)]
            (out/'crc-build.command.json').write_text(json.dumps(command,indent=2)+'\n')
            with (out/'crc-build.log').open('w') as log:
                compiled = subprocess.run(command,stdout=log,stderr=subprocess.STDOUT,timeout=120)
            require(compiled.returncode == 0, 'CRC checker compilation failed')
            r['crc_checker_source'] = describe(source)
        r['crc_checker'] = describe(checker)
        result=subprocess.run([str(checker),str(bit)],capture_output=True,text=True,timeout=60)
        crc=json.loads(result.stdout)
        require(result.returncode == 0 and crc['status'] == 'ALL_PRESENT_CRC_CHECKPOINTS_MATCH' and crc['crc_checkpoints'] == 2,'Configuration CRC failed')
        (out/'crc.json').write_text(json.dumps(crc,indent=2)+'\n')
        r.update(status='ROUTED_CHECKPOINT_AUDIT_RUNNING',bitstream=describe(bit),crc=crc);save()
        (out/'audit.tcl').write_text(TCL)
        if a.review_oob_clocks:
            script = ROOT/'boards/ypcb-00338/vivado/review_oob_clocks.tcl'
            (out/'review_oob_clocks.tcl').write_bytes(script.read_bytes())
            r['oob_review_script'] = describe(out/'review_oob_clocks.tcl')
        command=[str(VIVADO),'-mode','batch','-nojournal','-nolog','-source',str(out/'audit.tcl'),'-tclargs',str(dcp),str(out),
                 '1' if a.expect_serializer_reset_stage else '0', '1' if a.review_oob_clocks else '0']
        (out/'audit.command.json').write_text(json.dumps(command,indent=2)+'\n')
        with (out/'audit.log').open('w') as log:
            result=subprocess.run(command,cwd=out,stdout=log,stderr=subprocess.STDOUT,timeout=1200)
        require(result.returncode == 0, 'Routed checkpoint audit failed; see audit.log')
        lines=[line.split('\t') for line in (out/'checkpoint.tsv').read_text().splitlines()]
        meta={x[0]:x[1] for x in lines if len(x)==2}
        require(meta == dict(PART='xc7k480tffg1156-2',TOP='otpu_fpga_top_ld',CFGBVS='GND',CONFIG_VOLTAGE='1.8',CONFIG_MODE='BPI16'),'Configuration/checkpoint profile differs')
        ports={x[1]:dict(pin=x[2],standard=x[3]) for x in lines if x[0]=='PORT'}
        require(len(ports) == 278 and len(set(x['pin'] for x in ports.values())) == 278 and all(x['pin'] for x in ports.values()),'Incomplete or overlapping pin coverage')
        board=build/'source/boards/ypcb-00338'
        expected=pin_settings((board/'constraints/otpu_top_ld.xdc').read_text())
        expected.update(pin_settings((board/'litedram/otpu_litedram.xdc').read_text()))
        for name,props in expected.items():
            require(name in ports and all(ports[name][k] == v for k,v in props.items()), 'Board pin/standard differs: '+name)
        require(ports['pcie_refclk_clk_n']['pin'] == 'J7', 'PCIe negative reference-clock pin differs')
        vendor=pin_settings((board/'constraints/vendor_ypcb003381p1.xdc').read_text())
        for lane in range(8):
            require(ports[f'pcie_mgt_txp[{lane}]']['pin'] == vendor[f'pci_express_x8_txp[{lane}]']['pin'],'PCIe lane pin differs')
        gt=[x[2] for x in lines if x[0]=='GT']
        require(len(gt) == 8 and set(gt) == {f'GTXE2_CHANNEL_X0Y{i}' for i in range(16,24)},'Eight PCIe GTX sites differ')
        require([x[2] for x in lines if x[0]=='PCIE'] == ['PCIE_X0Y0'] and not any(x[0]=='BSCAN' for x in lines),'PCIe primitive or top differs')
        inventory={x[1]:int(x[2]) for x in lines if x[0]=='RESOURCE'}
        clocks = {x[1]: float(x[2]) for x in lines if x[0] == 'CLOCK'}
        check_clock_periods(clocks, m, a.core_khz)
        r['clock_periods_ns'] = clocks
        r['profile'] = expected_profile
        for name, count in dict(DSP48E1=716, ISERDESE2=144, OSERDESE2=214, IDELAYE2=144).items():
            require(inventory.get(name) == count, 'Full compute/DDR primitive count differs: '+name)
        require(inventory.get('RAMB36E1',0) >= 562 and inventory.get('RAMB18E1',0) >= 34,
                'Full accelerator memory primitive count is absent')
        r['implemented_primitives'] = inventory
        if a.expect_serializer_reset_stage:
            resets=[x for x in lines if x[0]=='PHY_RESET']
            require({x[1] for x in resets} == {'0','1'} and all(x[3] in ('FDRE','FDSE') for x in resets),
                    'Implemented serializer reset stages differ')
            r['serializer_reset_registers'] = resets
        timing=timing_summary((out/'timing.rpt').read_text()); route=route_summary((out/'route.rpt').read_text())
        require(all(timing[k] >= 0 for k in ('WNS','WHS','WPWS')) and all(timing[k] == 0 for k in ('setup_failing','hold_failing','pulse_failing')), 'Numerical timing failed')
        require(route['routable'] == route['fully_routed'] > 0 and route['routing_errors'] == 0,'Route is incomplete')
        if a.review_oob_clocks:
            r['oob_clock_review'] = oob_review(out)
            r['oob_reports'] = [describe(p) for p in sorted(out.glob('oob-*')) if p.is_file()]
        r.update(status=('DUAL_PCIE_IMAGE_PACKET_CRC_PINS_ROUTE_TIMING_PASS_CDC_REVIEW_PENDING' if dual
                         else 'CH1_PCIE_IMAGE_PACKET_CRC_PINS_ROUTE_TIMING_PASS_CDC_REVIEW_PENDING'),
                 timing=timing,route=route,pins_checked=len(ports),gt_sites=gt,
                 cdc_scope='Fresh cdc.rpt and bus-skew.rpt require review before programming',
                 build_manifest=describe(build/'manifest.json'),checker=describe(Path(__file__)))
        return 0
    except Exception as error:
        r.update(status='FAIL',error=repr(error));print(r['error'],flush=True);return 1
    finally:
        r['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__ == '__main__':
    raise SystemExit(main())
