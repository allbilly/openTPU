#!/usr/bin/env python3
"""Sample the FPGA die sensor during physical LFM inference on Chestnut.

Uses the benchmark's correctness-checked 512-token prefill / 64-step decode.
Extra sensor reads affect host timing, so this diagnostic is stored separately
from the uninstrumented throughput results. No programming or reset occurs.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from opentpu.host import regs as R
from opentpu.host.chestnut import ChestnutTransport
from tools import chestnut_benchmark as benchmark


def running(status):
    return bool(status & R.ST_RUN) and not bool(
        status & (R.ST_HALTED | R.ST_LOADING | R.ST_ERROR | R.ST_AXI_ERR))


class TemperatureRecorder:
    def __init__(self, output, interval=0.25):
        self.output = Path(output)
        self.interval = interval
        self.next_sample = 0.0
        self.start = time.monotonic()
        self.samples = []

    def capture(self, read, status_before, latch=None):
        now = time.monotonic()
        if not running(status_before) or now < self.next_sample:
            return None
        self.next_sample = now + self.interval
        raw = read(R.R_TEMP)
        clock = {}
        if latch is not None:
            before = time.monotonic()
            latch()
            after = time.monotonic()
            low = read(R.COUNTERS['UPTIME'])
            high = read(R.COUNTERS['UPTIME']+4)
            clock = dict(uptime_cycles=low | high << 32,
                         clock_before=before, clock_after=after)
        status_after = read(R.R_STATUS)
        valid = bool(raw & R.TEMP_VALID)
        phase = json.loads((self.output/'manifest.json').read_text())['status']
        sample = dict(utc=datetime.now(timezone.utc).isoformat(),
                      elapsed_seconds=now-self.start, phase=phase,
                      status_before=status_before, status_after=status_after,
                      sensor_raw=raw, sensor_valid=valid,
                      temp_c=R.temp_c(raw) if valid else None,
                      active_during_sample=running(status_before) and running(status_after),
                      read_seconds=time.monotonic()-now, **clock)
        self.samples.append(sample)
        with (self.output/'temperature.jsonl').open('a') as stream:
            stream.write(json.dumps(sample)+'\n')
        if valid and sample['active_during_sample']:
            print(f'THERMAL {phase}: {sample["temp_c"]:.2f} C, '
                  f'STATUS {status_before:#x}->{status_after:#x}', flush=True)
        return sample

    def active_summary(self):
        result = {}
        for phase in sorted({sample['phase'] for sample in self.samples}):
            values = [sample['temp_c'] for sample in self.samples
                      if sample['phase'] == phase and sample['sensor_valid']
                      and sample['active_during_sample']]
            if values:
                result[phase] = dict(samples=len(values), min_c=min(values), max_c=max(values))
        return result

    def clock_summary(self):
        result = {}
        for phase in sorted({sample['phase'] for sample in self.samples}):
            values = [s for s in self.samples if s['phase'] == phase
                      and s['active_during_sample'] and 'uptime_cycles' in s]
            if len(values) < 2:
                continue
            first, last = values[0], values[-1]
            shortest = last['clock_before']-first['clock_after']
            longest = last['clock_after']-first['clock_before']
            if shortest < 0.25:
                continue
            cycles = (last['uptime_cycles']-first['uptime_cycles']) % (1 << 64)
            result[phase] = dict(samples=len(values), elapsed_seconds=(shortest+longest)/2,
                                 counter_delta=cycles,
                                 estimate_mhz=cycles/((shortest+longest)/2)/1e6,
                                 lower_bound_mhz=cycles/longest/1e6,
                                 upper_bound_mhz=cycles/shortest/1e6)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--interval', default=0.25, type=float)
    args = parser.parse_args()
    if args.interval <= 0:
        parser.error('The sample interval must be positive')
    output = args.out.resolve()
    recorder = TemperatureRecorder(output, args.interval)

    class ThermalTransport(ChestnutTransport):
        def reg_read(self, off):
            # Use the existing device handle, keeping the complete status / sensor
            # / status sequence serialized with every other transport operation.
            with self._dma:
                base = super()
                value = base.reg_read(off)
                if off == R.R_STATUS:
                    def latch():
                        base.reg_write(R.R_SNAP, 1)
                        base.reg_read(R.R_SNAP)  # Flush the posted write before the timestamp.
                    recorder.capture(base.reg_read, value, latch=latch)
                return value

    options = argparse.Namespace(model='lfm2', out=output, prompt=512, tokens=64,
                                 cap=1024, check_tokens=8, cpu_threads=8,
                                 quant_workers=1, wformat='int8', head_format=None,
                                 no_resident=False, ple_host=False, expert_slots=None)
    original = benchmark.ChestnutTransport
    benchmark.ChestnutTransport = ThermalTransport
    try:
        code = benchmark.run(options)
    finally:
        benchmark.ChestnutTransport = original
    manifest = json.loads((output/'manifest.json').read_text())
    summary = recorder.active_summary()
    clocks = recorder.clock_summary()
    required = {'PREFILL_BENCHMARK', 'DECODE_BENCHMARK'}
    passed = code == 0 and required <= summary.keys() and required <= clocks.keys()
    report = dict(status='PASS_FPGA_INFERENCE_THERMAL_CHECK' if passed else 'FAIL_THERMAL_CHECK',
                  measured_utc=datetime.now(timezone.utc).isoformat(),
                  model='LiquidAI/LFM2.5-230M', weights='int8',
                  measurement='FPGA die XADC sensor; RUN active and HALTED clear before and after each qualified sensor read',
                  interval_seconds=args.interval,
                  clock_khz=manifest['identity']['core_khz'],
                  clock_source='Build-parameter register; not an independent frequency measurement',
                  measured_clock_by_phase=clocks,
                  frequency_method='UPTIME delta divided by host monotonic elapsed time; bounds bracket each SNAP write and readback; UPTIME increments once per core clock even between kernels',
                  startup_temp_c=manifest['identity']['temp_c'],
                  active_by_phase=summary, samples=recorder.samples,
                  sources={**manifest['sources'], 'tools/chestnut_thermal.py':
                           hashlib.sha256(Path(__file__).read_bytes()).hexdigest()},
                  correctness=manifest.get('correctness'), ecc_after=manifest.get('ecc_after'),
                  temporary_pci_config_restored=manifest.get('temporary_pci_config_restored'),
                  throughput_note='Sensor reads add overhead; this pass is excluded from the benchmark throughput table',
                  manifest=str(output/'manifest.json'))
    (output/'thermal.json').write_text(json.dumps(report, indent=2)+'\n')
    print(report['status'], json.dumps(summary), flush=True)
    return 0 if passed else 1


if __name__ == '__main__':
    raise SystemExit(main())
