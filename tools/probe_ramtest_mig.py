#!/usr/bin/env python3
"""Collect coherent RAM-only MIG snapshots through an existing local XVC server.

The FPGA autonomously runs the vendor traffic generator. This reader only
requests status snapshots; it never retrains memory or programs the FPGA.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def decode(words):
    if len(words) != 64 or any(not 0 <= x <= 0xffffffff for x in words):
        raise ValueError('Expected exactly 64 unsigned snapshot words')
    flags = words[0]
    wide = lambda i: words[i] | words[i+1] << 32
    expected = b''.join(x.to_bytes(4, 'little') for x in words[24:40])
    actual = b''.join(x.to_bytes(4, 'little') for x in words[40:56])
    return dict(calibrated=bool(flags & 1), ui_reset=bool(flags & 2),
                compare_error=bool(flags & 4), initialized=bool(flags & 8),
                watchdog_errors=(flags >> 4) & 7, enabled=bool(flags & 128),
                pattern_mode=words[1], write_commands=wide(2), read_commands=wide(4),
                returned_beats=wide(6), bad_compare_cycles=wide(8),
                ecc_corrected_beats=wide(10), ecc_uncorrectable_beats=wide(12),
                full_write_passes=words[14], full_read_command_passes=words[15],
                write_discontinuities=words[16], read_discontinuities=words[17],
                min_write_address=hex(words[18]*8), max_write_address=hex(words[19]*8),
                min_read_address=hex(words[20]*8), max_read_address=hex(words[21]*8),
                # Vendor first-error payloads are retained for investigation.
                # Injection testing found their address/data pipelines are not
                # aligned; their XOR must not be reported as a failing DQ mask.
                vendor_error_record=dict(alignment_verified=False,
                    native_address=hex(words[22]), expected=expected.hex(), actual=actual.hex()),
                cumulative_bad_byte_lanes=words[56] & 255, clock_cycles=wide(57),
                ui_reset_edges=words[59], compared_beats=wide(60), raw_words=words)


def verdict(channels, completion_targets=None):
    selected = [x for x in channels.values() if x['enabled']]
    if not selected:
        return 'FAIL_NO_ENABLED_CHANNELS'
    for ch in selected:
        if (ch['compare_error'] or ch['bad_compare_cycles'] or ch['ecc_corrected_beats']
                or ch['ecc_uncorrectable_beats'] or ch['watchdog_errors'] or ch['ui_reset_edges'] > 1
                or ch['cumulative_bad_byte_lanes']):
            return 'FAIL_PHYSICAL_RAM_ERRORS'
    for ch in selected:
        if (not ch['calibrated'] or ch['ui_reset'] or not ch['initialized']
                or ch['full_write_passes'] < 1 or ch['full_read_command_passes'] < 1
                or ch['returned_beats'] < 1 << 25 or ch['compared_beats'] < 1 << 25):
            return 'INCOMPLETE_FULL_MEMORY_TEST'
    for channel, ch in channels.items():
        if not ch['enabled']:
            continue
        # A full command traversal can finish before its last data returns.
        # Qualify a frozen earlier prefix only after it has all been compared.
        target = (completion_targets or {}).get(channel, ch['read_commands'])
        if ch['returned_beats'] < target or ch['compared_beats'] < target:
            return 'INCOMPLETE_RETURNED_DATA_COVERAGE'
    return 'PASS_OBSERVED_FULL_MEMORY_PATTERN'


def snapshot(link, mask=3, timeout=10):
    link.reg_write(0x24, mask)
    deadline = time.monotonic() + timeout
    while link.reg_read(0x18) & mask:
        if time.monotonic() >= deadline:
            raise TimeoutError('RAM snapshot acknowledgment missing; a UI clock may be absent')
        time.sleep(.01)
    return {str(ch): decode([link.reg_read(0x100 + ch*0x100 + i*4) for i in range(64)])
            for ch in (0, 1) if mask & (1 << ch)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='localhost')
    parser.add_argument('--port', type=int, default=3721)
    parser.add_argument('--seconds', type=float, default=300)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--expect-build-id', type=lambda s: int(s, 16), required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    if args.seconds < 0 or args.interval <= 0:
        parser.error('Use nonnegative --seconds and positive --interval')
    args.out.mkdir(parents=True, exist_ok=False)
    result = dict(status='CONNECTING', started_utc=datetime.now(timezone.utc).isoformat(), samples=[])
    link = None
    exit_code = 1
    try:
        from opentpu.host.jtag import JtagTransport
        link = JtagTransport(args.host, args.port)
        if link.reg_read(0) != 0x52414d54 or link.reg_read(4) != 1:
            raise ValueError('Expected RAMT image and snapshot ABI 1; no snapshot write issued')
        result['build_id'] = link.reg_read(8)
        if result['build_id'] != args.expect_build_id:
            raise ValueError('RAM image build ID differs from --expect-build-id')
        result['ddr_mts'] = link.reg_read(12)
        result['channel_mask'] = mask = link.reg_read(16)
        result['pattern_mode'] = link.reg_read(20)
        if mask not in (1, 2, 3):
            raise ValueError('Invalid enabled channel mask')
        start = time.monotonic()
        completion_targets = {}
        while True:
            channels = snapshot(link, mask)
            for channel, ch in channels.items():
                if not ch['enabled'] or ch['pattern_mode'] != result['pattern_mode']:
                    raise ValueError('Snapshot enabled/pattern fields differ from image identity')
                if ch['full_read_command_passes'] >= 1 and channel not in completion_targets:
                    completion_targets[channel] = ch['read_commands']
            status = verdict(channels, completion_targets)
            sample = dict(elapsed_seconds=round(time.monotonic()-start, 3),
                          utc=datetime.now(timezone.utc).isoformat(), status=status,
                          fpga_die_c=link.read_die_temperature(), channels=channels)
            sample['completion_targets'] = dict(completion_targets)
            result['samples'].append(sample)
            with (args.out / 'samples.jsonl').open('a') as log:
                log.write(json.dumps(sample)+'\n')
            print(json.dumps({k:sample[k] for k in ('elapsed_seconds', 'status', 'fpga_die_c')}), flush=True)
            if status.startswith('FAIL') or time.monotonic()-start >= args.seconds:
                break
            time.sleep(min(args.interval, max(0, args.seconds-(time.monotonic()-start))))
        result['status'] = status
        if status.startswith('PASS'):
            result['status'] = 'PASS_PHYSICAL_RAM_PATTERN_OBSERVATION_COLD_WARM_COVERAGE_REQUIRES_REVIEW'
        exit_code = 0 if result['status'].startswith('PASS') else 1
    except Exception as error:
        result.update(status='FAIL', error=str(error))
        print(error, file=sys.stderr)
    finally:
        if link is not None:
            try:
                link.close()
            except Exception as error:
                result.update(status='FAIL', cleanup_error=str(error))
                exit_code = 1
        result['finished_utc'] = datetime.now(timezone.utc).isoformat()
        (args.out / 'manifest.json').write_text(json.dumps(result, indent=2)+'\n')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
