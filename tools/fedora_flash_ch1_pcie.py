#!/usr/bin/env python3
"""Back up, permanently program, verify and boot the reviewed CH1 PCIe image.

Uses the native Vivado cable driver. Backup is read-only for NOR; the FPGA
temporarily runs Vivado's flash-access core. Programming requires the image/review/physical LFM2 witnesses. Normally two
complete old-flash reads must match; --skip-backup honors an explicit user override.
No DDR diagnosis is performed. Cold power-cycle/PCIe enumeration remains a
separate physical test on the other Linux PC.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from fedora_program_ch1_sram import artifact_matches, check_receipts, describe, require, stop_group
from fedora_run_vivado_native_jtag import VIVADO
from opentpu.host import bpi_image

BASE = ROOT / 'build/fedora-vivado'

TCL = r'''
open_hw_manager
connect_hw_server -url localhost:3122
set targets [get_hw_targets]
if {[llength $targets] != 1} {error "Expected one JTAG target"}
current_hw_target [lindex $targets 0]
set_property PARAM.FREQUENCY 3000000 [current_hw_target]
open_hw_target
set devices [get_hw_devices]
if {[llength $devices] != 1 || [get_property PART [lindex $devices 0]] ne "xc7k480t"} {
    error "Expected single XC7K480T"
}
close_hw_target
open_hw_target -jtag_mode 1
run_state_hw_jtag RESET
run_state_hw_jtag IDLE
scan_ir_hw_jtag 6 -tdi 09
set id [scan_dr_hw_jtag 32 -tdi 0]
if {[expr "0x$id"] != 0x23751093} {error "Unexpected raw FPGA IDCODE"}
close_hw_target
open_hw_target
set dev [lindex [get_hw_devices] 0]
current_hw_device $dev
set mode $::env(OTPU_FLASH_MODE)
if {$mode eq "boot"} {
    boot_hw_device $dev
    after 10000
    refresh_hw_device -update_hw_probes false $dev
    set init [get_property REGISTER.IR.BIT4_INIT_COMPLETE $dev]
    set done [get_property REGISTER.IR.BIT5_DONE $dev]
    if {![string is boolean -strict $init] || ![string is boolean -strict $done] || !$init || !$done} {
        error "Flash boot INIT/DONE failed"
    }
    report_property $dev REGISTER.*
    puts "PASS_BOOT_FROM_FLASH_INIT_DONE"
} else {
    set parts [get_cfgmem_parts {mt28gu512aax1e-bpi-x16}]
    if {![llength $parts]} {error "Micron BPI part unavailable"}
    foreach p $parts {
        if {[get_property NAME $p] ne "mt28gu512aax1e-bpi-x16" ||
            [get_property MEM_DENSITY $p] != 512 ||
            [get_property DATA_WIDTH $p] ne "x16" ||
            [lsearch -exact [get_property COMPATIBLE_PARTS $p] kintex7] < 0} {
            error "Unexpected configuration-memory part properties"
        }
    }
    create_hw_cfgmem -hw_device $dev [lindex $parts 0]
    set cfg [get_property PROGRAM.HW_CFGMEM $dev]
    set_property PROGRAM.BPI_RS_PINS {none} $cfg
    set_property PROGRAM.UNUSED_PIN_TERMINATION {pull-none} $cfg
    create_hw_bitstream -hw_device $dev [get_property PROGRAM.HW_CFGMEM_BITFILE $dev]
    program_hw_devices $dev
    refresh_hw_device -update_hw_probes false $dev
    if {$mode eq "backup"} {
        puts "BEGIN_FACTORY_READ_A"
        readback_hw_cfgmem -all -format bin -file $::env(OTPU_FLASH_BACKUP_A) $cfg
        puts "BEGIN_FACTORY_READ_B"
        readback_hw_cfgmem -all -format bin -file $::env(OTPU_FLASH_BACKUP_B) $cfg
        report_property $cfg
        puts "PASS_TWO_READONLY_FACTORY_READBACKS"
    } elseif {$mode eq "program" || $mode eq "verify"} {
        set_property PROGRAM.FILES [list $::env(OTPU_FLASH_MCS)] $cfg
        set_property PROGRAM.ADDRESS_RANGE {use_file} $cfg
        set_property PROGRAM.BLANK_CHECK 0 $cfg
        set write [expr {$mode eq "program"}]
        set_property PROGRAM.ERASE $write $cfg
        set_property PROGRAM.CFG_PROGRAM $write $cfg
        set_property PROGRAM.VERIFY 1 $cfg
        set_property PROGRAM.CHECKSUM 0 $cfg
        if {$write} {puts "BEGIN_AUTHORIZED_FLASH_ERASE_PROGRAM_VERIFY"}
        program_hw_cfgmem $cfg
        puts "PASS_FLASH_OPERATION_$mode"
    } else {error "Invalid flash mode"}
}
close_hw_target
disconnect_hw_server
close_hw_manager
exit
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--wait-usb', type=int, default=0)
    backup_mode = ap.add_mutually_exclusive_group()
    backup_mode.add_argument('--backup-only', action='store_true')
    backup_mode.add_argument('--skip-backup', action='store_true',
                             help='Omit old flash contents when explicitly requested by the user')
    a = ap.parse_args()
    require(a.wait_usb >= 0, 'USB wait must be nonnegative')
    out = BASE / ('ch1-permanent-pcie-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    out.mkdir()
    r = dict(status='REVIEW_PREFLIGHT', started_utc=datetime.now(timezone.utc).isoformat(),
             hardware_accessed=False, flash_write_attempted=False, flash_written=False,
             cold_boot_verified=False, physical_pcie_verified=False,
             backup_policy='SKIPPED_BY_USER' if a.skip_backup else 'TWO_MATCHING_FULL_READS',
             factory_backup_verified=False,
             deferred_task='CH0 DDR repair deferred by user; CH1-only image selected')
    hw = child = None

    def save():
        p = out / 'manifest.json.tmp'
        p.write_text(json.dumps(r, indent=2) + '\n')
        p.replace(out / 'manifest.json')

    def phase(mode, env):
        nonlocal child
        r['status'] = mode.upper() + '_RUNNING'
        save()
        command = [str(VIVADO / 'vivado'), '-mode', 'batch', '-nojournal', '-nolog',
                   '-source', str(out / 'flash.tcl')]
        r.setdefault('commands', []).append(dict(mode=mode, command=command))
        with (out / (mode + '.log')).open('w') as log:
            child = subprocess.Popen(command, cwd=out, env=dict(env, OTPU_FLASH_MODE=mode),
                                     stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            r['child_pid'] = child.pid
            save()
            deadline = time.monotonic() + 3600
            while child.poll() is None:
                require(time.monotonic() < deadline, 'Flash operation exceeded one hour: ' + mode)
                time.sleep(1)
        r.setdefault('phase_exits', {})[mode] = child.returncode
        save()
        require(child.returncode == 0, 'Vivado flash operation failed: ' + mode)
        text = (out / (mode + '.log')).read_text()
        marker = {'backup':'PASS_TWO_READONLY_FACTORY_READBACKS',
                  'program':'PASS_FLASH_OPERATION_program',
                  'verify':'PASS_FLASH_OPERATION_verify',
                  'boot':'PASS_BOOT_FROM_FLASH_INIT_DONE'}[mode]
        require(any(line.strip() == marker for line in text.splitlines()) and not any(line.startswith('ERROR:') for line in text.splitlines()),
                'Flash operation acknowledgement absent: ' + mode)

    try:
        pointer = json.loads((BASE / 'ch1-pcie-program-review-current.json').read_text())
        qpath, review = Path(pointer['qualification']), Path(pointer['review'])
        bit, q, reviewed = check_receipts(qpath, review)
        mcs = Path(pointer['mcs'])
        require(artifact_matches(reviewed['mcs'], mcs), 'Reviewed MCS changed')
        physical_path = Path(reviewed['physical_compute_proof']['path'])
        require(artifact_matches(reviewed['physical_compute_proof'], physical_path), 'Physical LFM2 proof changed')
        require(json.loads(physical_path.read_text())['status'] ==
                'PASS_AUDITED_PHYSICAL_CH1_JTAG_MATMUL_AND_LFM2', 'Physical LFM2 pass absent')
        r.update(bitstream=describe(bit), mcs=describe(mcs), review=describe(review),
                 qualification=describe(qpath), physical_lfm2_proof=describe(physical_path))
        (out / 'flash.tcl').write_text(TCL)
        (BASE / 'ch1-permanent-pcie-current.json').write_text(json.dumps(dict(out=str(out)), indent=2)+'\n')
        deadline = time.monotonic() + a.wait_usb
        while True:
            owners = [n for n in ('hw_server','openFPGALoader','xsdb','fxload')
                      if subprocess.run(['pgrep','-x',n], stdout=subprocess.DEVNULL).returncode == 0]
            require(not owners, 'Cable already owned: ' + ','.join(owners))
            usb = subprocess.check_output(['lsusb'], text=True)
            cables = [x for x in usb.splitlines() if 'ID 03fd:' in x]
            require(len(cables) <= 1, 'Multiple Xilinx adapters are ambiguous')
            r.update(status='WAITING_FOR_JTAG_USB', usb_lines=cables,
                     observed_utc=datetime.now(timezone.utc).isoformat())
            save()
            if cables:
                break
            require(time.monotonic() < deadline, 'Xilinx USB adapter absent; no hardware operation started')
            time.sleep(1)
        with socket.socket() as s:
            require(s.connect_ex(('127.0.0.1',3122)) != 0, 'Hardware-server port occupied')
        with (out / 'hw-server.log').open('w') as log:
            hw = subprocess.Popen([str(VIVADO / 'hw_server'),'-s','tcp::3122'],
                                  stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        r.update(hw_server_pid=hw.pid, hardware_accessed=True)
        save()
        env = dict(os.environ, OTPU_FLASH_MCS=str(mcs),
                   OTPU_FLASH_BACKUP_A=str(out / 'factory-a.bin'),
                   OTPU_FLASH_BACKUP_B=str(out / 'factory-b.bin'))
        if not a.skip_backup:
            phase('backup', env)
            factory = [out / 'factory-a.bin', out / 'factory-b.bin']
            require(all(p.stat().st_size == 64*1024*1024 for p in factory), 'Factory backup is not complete 64 MiB')
            r['factory_backups'] = [describe(p) for p in factory]
            require(r['factory_backups'][0]['sha256'] == r['factory_backups'][1]['sha256'],
                    'Two full factory flash reads do not match; programming remains prohibited')
            body, fmt = bpi_image.load(str(factory[0]))
            images = bpi_image.images(body)
            require(images and any(0x03751093 in words for x in images for words in x.reg('IDCODE')),
                    'Factory backup contains no recognizable XC7K480T image')
            r['factory_images'] = [bpi_image.describe(x) for x in images]
            r['factory_backup_verified'] = True
            r['flash_part_check'] = 'Vivado default part checking; no ID-check bypass used'
            save()
            if a.backup_only:
                r['status'] = 'PASS_VERIFIED_FACTORY_BACKUP_ONLY_FPGA_RUNNING_FLASH_ACCESS_CORE'
                return 0
        else:
            r.update(status='BACKUP_SKIPPED_BY_USER', factory_backup_skipped=True,
                     backup_skip_authorization='User explicitly requested skipping the old flash contents')
            save()
        r['flash_part_check'] = 'Vivado default part checking; no ID-check bypass used'
        # This write is explicitly authorized by the user after physical LFM2 passed.
        r['flash_write_attempted'] = True
        save()
        phase('program', env)
        r['flash_written'] = True
        save()
        phase('verify', env)
        r['flash_verified'] = True
        save()
        phase('boot', env)
        r.update(status='PASS_PERMANENT_CH1_PCIE_FLASH_VERIFIED_JTAG_BOOT_COLD_PCIE_TEST_PENDING',
                 jtag_boot_from_flash_verified=True)
        print(json.dumps(dict(status=r['status'], out=str(out)), indent=2))
        return 0
    except Exception as e:
        r.update(status='FAIL', error=repr(e))
        print(json.dumps(dict(status=r['status'], error=r['error'], out=str(out))), flush=True)
        return 1
    finally:
        stop_group(child)
        stop_group(hw)
        r['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
