#!/usr/bin/env python3
"""Control and observe the RAM-only LDRT image through USER2/XVC.

Status reads never retrain memory. Start overwrites the selected channels;
recalibrate explicitly pauses/drains traffic and uses the calibration CPU.
Restart changes the pattern after a clean, drained observation, resetting only
the traffic generators and retaining the DDR controllers and calibration.
Actual ECC counters come from the generated core's CSRs, not MIG pulse fields.
"""
from __future__ import annotations

import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'tools')]
from probe_ramtest_mig import snapshot, verdict

PATTERNS = dict(address=(2, 0), zeros=(1, 0), ones=(1, 0xffffffff),
                walking1=(5, 0), walking0=(6, 0), prbs=(7, 0))
CORE_FILENAMES = frozenset(('otpu_litedram.v', 'otpu_litedram.xdc',
                            'otpu_litedram_mem.init', 'csr.csv', 'sdram_init.py'))


def checked_core(core):
    """Bind every generated input, including the CSR map used for writes."""
    profile = json.loads((core/'openxc7-profile.json').read_text())
    if (profile.get('status') != 'GENERATED_PROFILE_PASS_IMPLEMENTATION_NOT_RUN' or
            profile.get('part') != 'xc7k480tffg1156-2' or
            profile.get('parameters') != dict(CORE_KHZ=100000, DDR_MTS=800) or
            profile.get('physical_user_channels', [0, 1]) != [0, 1]):
        raise ValueError('Require checked full dual-channel DDR800 tables')
    inventory = {}
    for item in profile['files'].values():
        name = item['name']
        if name not in CORE_FILENAMES or name in inventory:
            raise ValueError('Invalid or duplicate matched core file: '+str(name))
        inventory[name] = item
    if set(inventory) != CORE_FILENAMES:
        raise ValueError('Incomplete matched core inventory')
    for name, item in inventory.items():
        path = core/name
        if (not path.resolve().is_relative_to(core.resolve()) or
                path.stat().st_size != item['bytes'] or
                hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']):
            raise ValueError('Matched core file changed or escapes its directory: '+name)
    assignments = [node for node in ast.parse((core/'sdram_init.py').read_text()).body
                   if isinstance(node, ast.Assign) and
                   any(isinstance(target, ast.Name) and target.id == 'phy' for target in node.targets)]
    if len(assignments) != 1:
        raise ValueError('Missing generated PHY settings')
    phy = ast.literal_eval(assignments[0].value)
    if phy['sys_hz'] != 100000000:
        raise ValueError('Wrong memory sys clock')
    return phy


def require_prbs_package(core, build_id):
    """Reject the demonstrated runtime PRBS startup fault before hardware access."""
    path = core.parent / 'manifest.json'
    if not path.is_file():
        raise ValueError('PRBS requires a packaged runtime-pattern startup correction')
    package = json.loads(path.read_text())
    if (package.get('status') != 'EXPERIMENTAL_RAM_ONLY_LITEDRAM_IMAGE_PHYSICAL_TESTS_PENDING'
            or package.get('runtime_pattern_reset_fix') is not True
            or package.get('build_id') != f'{build_id:08x}'):
        raise ValueError('PRBS requires a matching package with the runtime-pattern startup correction')
    bit = core.parent / 'ramtest.bit'
    if (not bit.is_file() or
            hashlib.sha256(bit.read_bytes()).hexdigest() != package.get('bitstream', {}).get('sha256')):
        raise ValueError('PRBS package bitstream hash differs')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decode_first_read(words):
    if len(words) != 34 or any(not 0 <= value <= 0xffffffff for value in words):
        raise ValueError('Expected 34 unsigned read-capture words')
    flags = words[1]
    if flags & ~15:
        raise ValueError('Unknown read-capture flags')
    expected = b''.join(value.to_bytes(4, 'little') for value in words[2:18])
    actual = b''.join(value.to_bytes(4, 'little') for value in words[18:34])
    valid = bool(flags & 1)
    address_valid = valid and bool(flags & 2) and not flags & 12
    if address_valid and (words[0] > 0x0ffffff8 or words[0] & 7):
        raise ValueError('Captured native address is out of range or unaligned')
    return dict(captured=valid, address_valid=address_valid,
                queue_overflow=bool(flags & 4), queue_underflow=bool(flags & 8),
                byte_address=hex(words[0]*8) if address_valid else None,
                expected=expected.hex() if valid else None,
                actual=actual.hex() if valid else None,
                returned_payload_xor=bytes(a ^ b for a, b in zip(expected, actual)).hex() if valid else None,
                scope='First payload mismatch after ECC; corrected-only events and physical DQ syndrome are not captured')


def corrected_only(row):
    """Permit bounded diagnostic reads after SEC events, never a passing verdict."""
    channels = row['channels'].values()
    return bool(row['channels']) and any(v['ecc_corrected_beats'] for v in channels) and all(
        v['calibrated'] and v['initialized'] and not v['ui_reset'] and
        v['ecc']['ecc_enable'] == 1 and
        not any(v[key] for key in ('watchdog_errors', 'compare_error', 'bad_compare_cycles',
                                  'ecc_uncorrectable_beats', 'cumulative_bad_byte_lanes')) and
        not any(v['first_read_mismatch'][key]
                for key in ('captured', 'queue_overflow', 'queue_underflow'))
        for v in row['channels'].values())


def reset_clean_generators(link, row):
    """Begin another pattern epoch; preserve any failing evidence instead of resetting it."""
    clean = (row['traffic_reset'] == 0 and row['traffic_pause'] == 3 and
             not row['native_command_pending'] and not row['protocol_errors'] and
             set(row['channels']) == {'0', '1'})
    for ch in row['channels'].values():
        clean = clean and ch['calibrated'] and ch['initialized'] and not ch['ui_reset'] and (
            ch['full_write_passes'] >= 1 and ch['full_read_command_passes'] >= 1 and
            ch['write_commands'] == ch['written_beats'] >= 1 << 25 and
            ch['read_commands'] == ch['returned_beats'] == ch['compared_beats'] >= 1 << 25 and
            ch['ecc']['ecc_enable'] == 1 and not any(ch[k] for k in (
                'ecc_corrected_beats', 'ecc_uncorrectable_beats', 'watchdog_errors',
                'compare_error', 'bad_compare_cycles', 'cumulative_bad_byte_lanes')) and
            not any(ch.get('first_read_mismatch', {}).get(k, False) for k in
                    ('captured', 'queue_overflow', 'queue_underflow')))
    if not clean:
        raise ValueError('Pattern restart requires both full-range, clean, drained channels; preserve failing state')
    if (link.reg_read(0x28) != 0 or link.reg_read(0x2c) != 3 or
            link.reg_read(0x44) & 0x30003):
        raise ValueError('Traffic state changed before generator reset')
    # These registers reset the diagnostic bridge/generators/observers. They
    # do not feed the generated core's reset or any calibration CSR.
    link.reg_write(0x28, 3)
    if link.reg_read(0x28) != 3:
        raise ValueError('Traffic-generator reset readback differs')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=3721)
    parser.add_argument('--core', type=Path, required=True)
    parser.add_argument('--expect-build-id', type=lambda value: int(value, 16), required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--action', choices=('status', 'start', 'restart', 'pause', 'resume', 'recalibrate'), default='status')
    parser.add_argument('--channels', choices=('0', '1', 'both'), default='both')
    parser.add_argument('--pattern', choices=PATTERNS, default='address')
    parser.add_argument('--mixed', action='store_true', help='Address-pattern mixed read/write traffic')
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--retention-seconds', type=float, default=0,
                        help='After a full read pass, pause traffic at normal refresh, then require another full read pass')
    parser.add_argument('--capture-after-corrected', action='store_true',
                        help='ABI 3 resume only: keep the failing verdict but read through corrected-only errors until a mismatch/DED or the time limit')
    args = parser.parse_args()
    if not all(math.isfinite(value) and value >= 0 for value in (args.seconds, args.retention_seconds)):
        parser.error('Durations must be finite and nonnegative')
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error('--interval must be finite and positive')
    if args.mixed and (args.action not in ('start', 'restart') or args.pattern != 'address' or args.retention_seconds):
        parser.error('--mixed requires --action start/restart --pattern address without retention')
    if args.retention_seconds and args.action not in ('status', 'start', 'restart', 'resume'):
        parser.error('Retention applies to a running or newly started read test')
    if args.action == 'restart' and args.channels != 'both':
        parser.error('Pattern restart requires both channels because pattern controls are shared')
    if args.capture_after_corrected and (args.action != 'resume' or args.retention_seconds or args.mixed):
        parser.error('--capture-after-corrected requires --action resume without mixed traffic or retention')
    if not 0 <= args.expect_build_id <= 0xffffffff:
        parser.error('--expect-build-id must fit in 32 bits')
    args.out.mkdir(parents=True, exist_ok=False)
    core = args.core.expanduser().resolve()
    mask = {'0': 1, '1': 2, 'both': 3}[args.channels]
    result = dict(status='CONNECTING', action=args.action, selected_channel_mask=mask,
                  physical_tests_performed=False, physical_hardware_accessed=False,
                  physical_hardware_access_attempted=False,
                  traffic_started_by_this_command=False,
                  traffic_start_attempted=False,
                  traffic_generator_reset_attempted=False,
                  traffic_generators_reset=False,
                  controller_recalibration_requested=args.action == 'recalibrate',
                  programming='NOT_RUN', flash_written=False,
                  capture_after_corrected=args.capture_after_corrected,
                  started_utc=datetime.now(timezone.utc).isoformat(), samples=[])
    link = None

    def save():
        temporary = args.out / 'manifest.json.tmp'
        temporary.write_text(json.dumps(result, indent=2) + '\n')
        temporary.replace(args.out / 'manifest.json')

    def require(ok, message):
        if not ok:
            raise ValueError(message)

    try:
        save()
        if args.action in ('start', 'restart') and args.pattern == 'prbs':
            result['prbs_package_sha256'] = require_prbs_package(core, args.expect_build_id)
        phy = checked_core(core)
        result['core_profile_sha256'] = hashlib.sha256((core / 'openxc7-profile.json').read_bytes()).hexdigest()
        result['phy'] = phy
        from opentpu.host.jtag import JtagTransport
        from opentpu.host import ddrcal, selfcal
        # The constructor checks the real TAP/mailbox before it can return.
        # Preserve uncertainty if it fails after opening the device.
        result.update(physical_hardware_access_attempted=True, physical_hardware_accessed=None)
        save()
        link = JtagTransport(args.host, args.port, calibration_data=core)
        result['physical_hardware_accessed'] = True
        abi = link.reg_read(4)
        require(link.reg_read(0) == 0x4c445254 and abi in (2, 3),
                'Require LDRT ABI 2 or 3 with the command buffer; no diagnostic control write issued')
        if abi == 3:
            require(link.reg_read(0x48) == 0x52444331, 'Unknown first-read capture layout')
        result['abi'] = abi
        result['build_id'] = link.reg_read(8)
        require(result['build_id'] == args.expect_build_id, 'Expected LDRT build ID differs')
        require(link.reg_read(12) == 800 and link.reg_read(0x3c) == 100000, 'Image clocks differ')
        require(link.reg_read(16) == 3, 'Require both physical diagnostic channels')
        # memcal.csr performs OpenTPU CAPS checks; this diagnostic has its own
        # identity/register map and uses only the shared calibration CSR ABI.
        csr = ddrcal.WordCsr(ddrcal.csr_map(core / 'csr.csv'), link.reg_read, link.reg_write, base=0x10000)
        channels = {ch: ddrcal.Chan(csr, ch) for ch in (0, 1)}

        def sample(selected=mask):
            values = snapshot(link, selected)
            for name, data in values.items():
                raw = data['raw_words']
                data['written_beats'] = raw[62] | raw[63] << 32
                data['combined_command_passes'] = raw[22]
                data['combined_command_discontinuities'] = raw[23]
                data.pop('vendor_error_record')  # LDRT uses these two words for coverage.
                data['ecc_source'] = 'LiteDRAM native ECC CSRs'
                data['ecc'] = {key: channels[int(name)].r(key) for key in
                               ('ecc_enable', 'ecc_sec_errors', 'ecc_ded_errors')}
                data['ecc_corrected_beats'] = data['ecc']['ecc_sec_errors']
                data['ecc_uncorrectable_beats'] = data['ecc']['ecc_ded_errors']
                if abi == 3:
                    base = 0x400 + 0x100*int(name)
                    flags = link.reg_read(base+4)
                    words = [link.reg_read(base+4*i) for i in range(34)] if flags & 1 else [0, flags]+[0]*32
                    capture = decode_first_read(words)
                    data['first_read_mismatch'] = capture
            interface = link.reg_read(0x44)
            row = dict(utc=datetime.now(timezone.utc).isoformat(), channels=values,
                       native_command_pending=interface & 3, protocol_errors=interface >> 16 & 3,
                       fpga_die_c=link.read_die_temperature(), traffic_reset=link.reg_read(0x28),
                       traffic_pause=link.reg_read(0x2c), pattern_mode=link.reg_read(0x30),
                       fixed_data=link.reg_read(0x34), instruction_mode=link.reg_read(0x40))
            result['samples'].append(row)
            with (args.out / 'samples.jsonl').open('a') as stream:
                stream.write(json.dumps(row) + '\n')
            save()
            for data in values.values():
                require(data['enabled'], 'Selected diagnostic channel is not enabled')
                capture = data.get('first_read_mismatch', {})
                require(not capture.get('queue_overflow') and not capture.get('queue_underflow'),
                        'Read-capture address tracking failed; preserve this diagnostic result')
            return row

        def quiesce(selected):
            link.reg_write(0x2c, link.reg_read(0x2c) | selected)
            require(link.reg_read(0x2c) & selected == selected,
                    'Traffic pause readback differs; drain is unproven')
            deadline = time.monotonic() + 30
            previous = None
            stable = 0
            while True:
                row = sample(selected)
                counts = [(ch['write_commands'], ch['written_beats'], ch['read_commands'],
                           ch['returned_beats'], ch['compared_beats']) for ch in row['channels'].values()]
                drained = (row['traffic_pause'] & selected == selected and
                           not row['native_command_pending'] & selected and
                           all(writes == data and reads == returned == compared
                               for writes, data, reads, returned, compared in counts))
                stable = stable + 1 if counts == previous and drained else 0
                if stable >= 2:
                    return row
                require(time.monotonic() < deadline, 'Traffic did not drain; generators remain paused')
                previous = counts
                time.sleep(.05)

        result['before_action'] = sample()
        if args.action == 'restart':
            result['before_restart_drained'] = quiesce(3)
            result['calibration_before_restart'] = selfcal.result(csr, core / 'sdram_init.py')
            state = selfcal.state(csr)
            result['calibration_state_before_restart'] = state
            save()
            require(state['done'] and all(state['channels'][ch] == ('ok', '') for ch in (0, 1)),
                    'Calibration must already have completed successfully for both channels')
            result['traffic_generator_reset_attempted'] = True
            save()
            reset_clean_generators(link, result['before_restart_drained'])
            result['traffic_generators_reset'] = True
            result['restart_scope'] = 'Generator/observer reset and full refill only; no controller reset, retraining or ECC counter clear requested'
            save()
        if args.action == 'pause':
            result['paused'] = quiesce(mask)
            result['status'] = 'PAUSED_DRAINED_NO_RETRAIN'
            return 0
        if args.action == 'recalibrate':
            result['before_recalibration'] = quiesce(3)
            result['before_recalibration_maps'] = selfcal.result(csr, core / 'sdram_init.py')
            save()  # Retain the failing warm state before resets/CPU calibration.
            link.reg_write(0x28, 3)
            selfcal.hold(csr)
            csr.w('selfcal_config', mask | (1 << 8))
            selfcal.release(csr)
            result['physical_tests_performed'] = True
            result['calibration_state'] = selfcal.wait(csr, timeout=120, poll=.5)
            result['calibration'] = selfcal.result(csr, core / 'sdram_init.py')
            result['after_recalibration'] = sample()
            require(result['calibration_state']['done'] and all(
                result['calibration_state']['channels'][ch] == ('ok', '')
                for ch in channels if mask & (1 << ch)), 'Selected calibration CPU result failed')
            require(link.reg_read(0x38) & mask == mask, 'Selected channel calibration failed')
            # A CPU rescan does not clear the native ECC counters. Preserve both
            # sides of calibration before explicitly beginning a new test epoch.
            save()
            for ch in channels:
                if mask & (1 << ch):
                    channels[ch].w('ecc_clear', 1)
            result['ecc_clear_after_saved_recalibration'] = mask
            result['after_ecc_clear'] = sample()
            require(all(data['ecc_corrected_beats'] == 0 and data['ecc_uncorrectable_beats'] == 0
                        for data in result['after_ecc_clear']['channels'].values()),
                    'Selected ECC counters did not clear while traffic was stopped')
            result['status'] = 'PASS_CALIBRATION_ONLY_NATIVE_MEMORY_TEST_NOT_RUN'
            return 0
        if args.action in ('start', 'restart'):
            require(link.reg_read(0x28) == 3, 'Pause/drain and recalibrate or reload before a new start')
            # Let configuration-time calibration finish before isolating user
            # traffic; another channel's calibration must not overlap the test.
            result['initial_calibration_state'] = selfcal.wait(csr, timeout=120, poll=.5)
            result['initial_calibration'] = selfcal.result(csr, core / 'sdram_init.py')
            save()
            require(result['initial_calibration_state']['done'] and all(
                result['initial_calibration_state']['channels'][ch] == ('ok', '')
                for ch in channels if mask & (1 << ch)), 'Selected calibration CPU result failed')
            if args.action == 'restart':
                require(result['initial_calibration'] == result['calibration_before_restart'] and
                        result['initial_calibration_state'] == result['calibration_state_before_restart'],
                        'Calibration record changed across traffic-generator reset')
            require(link.reg_read(0x38) & mask == mask, 'Selected channel did not calibrate; pass maps saved')
            for ch in channels:
                if mask & (1 << ch):
                    require(channels[ch].r('ecc_enable') == 1 and
                            channels[ch].r('ecc_sec_errors') == 0 and
                            channels[ch].r('ecc_ded_errors') == 0,
                            'Start requires enabled, clean native ECC counters')
            mode, fixed = PATTERNS[args.pattern]
            result['traffic_start_attempted'] = True
            save()
            link.reg_write(0x30, mode)
            link.reg_write(0x34, fixed)
            link.reg_write(0x40, 2 if args.mixed else 1)
            link.reg_write(0x28, 3 ^ mask)
            link.reg_write(0x2c, 3 ^ mask)
            result['physical_tests_performed'] = True
            result['traffic_started_by_this_command'] = True
        elif args.action == 'resume':
            require(not link.reg_read(0x28) & mask, 'Selected generator is reset; use a new start')
            if args.capture_after_corrected:
                before = result['before_action']
                require(abi == 3 and before['instruction_mode'] == 1 and
                        before['traffic_pause'] & mask == mask and
                        not before['native_command_pending'] & mask,
                        'Capture continuation requires a paused, drained ABI 3 read epoch')
                require(all(v['initialized'] and v['full_write_passes'] >= 1 and
                            v['write_commands'] == v['written_beats'] >= 1 << 25 and
                            v['read_commands'] == v['returned_beats'] == v['compared_beats']
                            for v in before['channels'].values()),
                        'Capture continuation requires saved full initialization and drained reads')
                require(not before['protocol_errors'] & mask and corrected_only(before),
                        'Capture continuation requires corrected-only errors; preserve other failures')
            link.reg_write(0x2c, link.reg_read(0x2c) & ~mask & 3)

        started = time.monotonic()
        targets, write_targets, reset_edges, mixed_baselines = {}, {}, {}, {}
        retention_done = not args.retention_seconds
        retention_passes = None
        while True:
            row = sample()
            require(not row['protocol_errors'] & mask, 'Diagnostic command encoding/address error')
            if args.capture_after_corrected:
                require(all(v[key] == result['before_action']['channels'][ch][key]
                            for ch, v in row['channels'].items()
                            for key in ('write_commands', 'written_beats', 'ui_reset_edges')),
                        'Writes or reset occurred during retained-content capture')
            judged = {key: dict(value) for key, value in row['channels'].items()}
            status = None
            for key, value in judged.items():
                reset_edges.setdefault(key, value['ui_reset_edges'])
                require(value['ui_reset_edges'] == reset_edges[key], 'Unexpected reset during observation')
                if not row['traffic_reset'] & (1 << int(key)):
                    result['physical_tests_performed'] = True
                    require(value['ecc']['ecc_enable'] == 1, 'Native ECC correction disabled')
                    require(value['calibrated'] and not value['ui_reset'], 'Calibration/reset changed during traffic')
                    if value['watchdog_errors'] and value['write_commands']+value['read_commands'] == 0:
                        result['failure_scope'] = 'DIAGNOSTIC_INTERFACE_NO_ACCEPTED_COMMANDS'
                        raise ValueError('Diagnostic traffic did not start; no DDR data-error measurement')
                # Test-phase reset counts can exceed one after a deliberate rescan.
                # Preserve the actual count in the saved sample; the shared verdict
                # checks unexpected resets through the phase-relative value here.
                value['ui_reset_edges'] = 1
                if (row['instruction_mode'] == 1 and value['full_read_command_passes'] >= 1 and
                        (retention_passes is None or value['full_read_command_passes'] > retention_passes[key])):
                    targets.setdefault(key, value['read_commands'])
                    write_targets.setdefault(key, value['write_commands'])
            if row['instruction_mode'] == 2:
                require(row['pattern_mode'] == 2, 'Mixed traffic requires the address pattern')
                for key, value in judged.items():
                    if value['initialized']:
                        # Initialization may interleave reads with the fill.
                        # Qualify two new complete combined traversals after a
                        # recorded initialized snapshot, without new gaps.
                        mixed_baselines.setdefault(key, dict(
                            passes=value['combined_command_passes'],
                            gaps=value['combined_command_discontinuities']))
                    baseline = mixed_baselines.get(key)
                    if baseline and value['combined_command_passes']-baseline['passes'] >= 2:
                        targets.setdefault(key, value['read_commands'])
                        write_targets.setdefault(key, value['write_commands'])
                bad = any(v['compare_error'] or v['bad_compare_cycles'] or
                          v['ecc_corrected_beats'] or v['ecc_uncorrectable_beats'] or
                          v['watchdog_errors'] or v['cumulative_bad_byte_lanes'] for v in judged.values())
                covered = all(v['initialized'] and v['calibrated'] and not v['ui_reset'] and
                              v['full_write_passes'] >= 1 and key in mixed_baselines and
                              v['combined_command_passes']-mixed_baselines[key]['passes'] >= 2 and
                              v['combined_command_discontinuities'] == mixed_baselines[key]['gaps'] and
                              v['read_commands'] > 0 and
                              key in targets and v['returned_beats'] >= targets[key] and
                              v['compared_beats'] >= targets[key] and v['written_beats'] >= write_targets[key]
                              for key, v in judged.items())
                status = ('FAIL_PHYSICAL_RAM_ERRORS' if bad else
                          'PASS_OBSERVED_FULL_COMBINED_MIXED_TRAFFIC' if covered else 'INCOMPLETE_MIXED_TRAFFIC')
            else:
                status = verdict(judged, targets)
                if status.startswith('PASS') and not all(key in write_targets and value['written_beats'] >= write_targets[key]
                                                         for key, value in judged.items()):
                    status = 'INCOMPLETE_ACCEPTED_WRITE_DATA'
            if any(value.get('first_read_mismatch', {}).get('captured') for value in judged.values()):
                status = 'FAIL_PHYSICAL_RAM_ERRORS'
            if status.startswith('PASS') and not retention_done:
                require(row['instruction_mode'] == 1, 'Retention requires fill/read mode')
                paused = quiesce(mask)
                result['retention_before'] = paused
                save()
                deadline = time.monotonic() + args.retention_seconds
                after = paused
                while time.monotonic() < deadline:
                    time.sleep(min(5, args.interval, max(0, deadline-time.monotonic())))
                    after = sample()
                    for key, value in after['channels'].items():
                        before = paused['channels'][key]
                        require(all(value[field] == before[field] for field in
                                    ('write_commands', 'written_beats', 'read_commands', 'returned_beats', 'compared_beats')),
                                'Traffic changed during retention pause')
                        require(value['ecc'] == before['ecc'], 'ECC state changed during retention pause')
                result['retention_after_pause'] = after
                retention_passes = {key: value['full_read_command_passes'] for key, value in after['channels'].items()}
                link.reg_write(0x2c, link.reg_read(0x2c) & ~mask & 3)
                targets.clear()
                write_targets.clear()
                retention_done = True
                result['retention_refresh'] = 'Normal controller refresh remains enabled'
            if retention_passes is not None and not status.startswith('FAIL'):
                if not all(value['full_read_command_passes'] > retention_passes[key]
                           for key, value in judged.items()):
                    status = 'INCOMPLETE_POST_RETENTION_READ_PASS'
                else:
                    # Freeze the newly completed traversal before requiring return/compare.
                    for key, value in judged.items():
                        targets.setdefault(key, value['read_commands'])
                    if not all(value['returned_beats'] >= targets[key] and value['compared_beats'] >= targets[key]
                               for key, value in judged.items()):
                        status = 'INCOMPLETE_POST_RETENTION_RETURNED_DATA'
            row['status'] = status
            result['status'] = status
            result['completion_targets'] = dict(targets)
            result['write_completion_targets'] = dict(write_targets)
            result['mixed_coverage_baselines'] = dict(mixed_baselines)
            save()
            print(json.dumps(dict(status=status, seconds=round(time.monotonic()-started, 3),
                                  fpga_die_c=row['fpga_die_c'])), flush=True)
            continue_corrected = (args.capture_after_corrected and
                                  status == 'FAIL_PHYSICAL_RAM_ERRORS' and corrected_only(row))
            if (status.startswith('FAIL') and not continue_corrected) or time.monotonic()-started >= args.seconds:
                if args.action == 'restart':
                    drained = quiesce(3)
                    result['after_restart_drained'] = drained
                    save()
                    require(not drained['protocol_errors'], 'Protocol error while draining the pattern epoch')
                    if any(ch.get('first_read_mismatch', {}).get('captured')
                           for ch in drained['channels'].values()) or any(
                           ch[key] for ch in drained['channels'].values() for key in
                           ('ecc_corrected_beats', 'ecc_uncorrectable_beats', 'bad_compare_cycles',
                            'watchdog_errors', 'compare_error', 'cumulative_bad_byte_lanes')):
                        status = 'FAIL_PHYSICAL_RAM_ERRORS'
                        result['status'] = status
                    result['calibration_after_restart'] = selfcal.result(csr, core / 'sdram_init.py')
                    result['calibration_state_after_restart'] = selfcal.state(csr)
                    save()
                    require(result['calibration_after_restart'] == result['calibration_before_restart'] and
                            result['calibration_state_after_restart'] == result['calibration_state_before_restart'],
                            'Calibration record changed during the pattern observation')
                return 0 if status.startswith('PASS') else 1
            time.sleep(min(args.interval, max(0, args.seconds-(time.monotonic()-started))))
    except BaseException as error:
        result.update(status='FAIL_INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'FAIL',
                      error=repr(error))
        print(error, file=sys.stderr)
        if not isinstance(error, Exception):
            raise
        return 1
    finally:
        cleanup_exception = None
        if link is not None:
            if (args.action == 'restart' and result['traffic_start_attempted'] and
                    'after_restart_drained' not in result):
                try:
                    # A failed observation cannot prove drainage. Request only
                    # pause, preserving counters and calibration for recovery.
                    link.reg_write(0x2c, 3)
                    require(link.reg_read(0x2c) == 3, 'Restart cleanup pause readback differs')
                    result['restart_failure_pause'] = 'Pause read back; drainage unproven'
                except BaseException as error:
                    result['restart_failure_pause_error'] = repr(error)
                    if not isinstance(error, Exception):
                        result['status'] = 'FAIL_INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'FAIL'
                        cleanup_exception = error
            try:
                link.close()
            except BaseException as error:
                result.update(status='FAIL_INTERRUPTED' if isinstance(error, KeyboardInterrupt) else 'FAIL',
                              cleanup_error=str(error))
                if cleanup_exception is None or not isinstance(error, Exception):
                    cleanup_exception = error
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()
        if cleanup_exception is not None:
            if not isinstance(cleanup_exception, Exception):
                raise cleanup_exception
            raise RuntimeError('Transport cleanup failed; result marked FAIL') from cleanup_exception


if __name__ == '__main__':
    raise SystemExit(main())
