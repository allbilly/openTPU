import json

from opentpu.host import regs as R
from tools.chestnut_thermal import TemperatureRecorder


def recorder(tmp_path):
    (tmp_path/'manifest.json').write_text(json.dumps({'status': 'DECODE_BENCHMARK'}))
    return TemperatureRecorder(tmp_path, interval=0)


def test_temperature_is_bracketed_by_running_status(tmp_path):
    r = recorder(tmp_path)
    reads = []
    def read(off):
        reads.append(off)
        return (R.TEMP_VALID | 2658) if off == R.R_TEMP else R.ST_RUN
    sample = r.capture(read, R.ST_RUN)
    assert reads == [R.R_TEMP, R.R_STATUS]
    assert sample['active_during_sample']
    assert r.active_summary()['DECODE_BENCHMARK']['max_c'] == R.temp_c(2658)


def test_completion_during_sensor_read_is_excluded_from_active_peak(tmp_path):
    r = recorder(tmp_path)
    sample = r.capture(lambda off: (R.TEMP_VALID | 2658) if off == R.R_TEMP
                       else R.ST_RUN | R.ST_HALTED, R.ST_RUN)
    assert not sample['active_during_sample']
    assert not r.active_summary()


def test_invalid_temperature_cannot_be_reported_as_under_load(tmp_path):
    r = recorder(tmp_path)
    sample = r.capture(lambda off: 2658 if off == R.R_TEMP else R.ST_RUN, R.ST_RUN)
    assert sample['temp_c'] is None
    assert not r.active_summary()


def test_idle_or_error_status_never_probes_sensor(tmp_path):
    r = recorder(tmp_path)
    def unexpected(off):
        raise AssertionError('Inactive/error states must not be sampled')
    for status in [0, R.ST_HALTED, R.ST_RUN | R.ST_HALTED,
                   R.ST_RUN | R.ST_LOADING, R.ST_RUN | R.ST_AXI_ERR]:
        assert r.capture(unexpected, status) is None


def test_live_clock_uses_one_consistent_counter_snapshot(tmp_path):
    r = recorder(tmp_path)
    calls = []
    registers = {R.R_TEMP: R.TEMP_VALID | 2658, R.R_STATUS: R.ST_RUN,
                 R.COUNTERS['UPTIME']: 17, R.COUNTERS['UPTIME']+4: 3}
    def read(off):
        calls.append(off)
        return registers[off]
    sample = r.capture(read, R.ST_RUN, latch=lambda: calls.append('SNAP'))
    assert calls == [R.R_TEMP, 'SNAP', R.COUNTERS['UPTIME'],
                     R.COUNTERS['UPTIME']+4, R.R_STATUS]
    assert sample['uptime_cycles'] == (3 << 32) | 17


def test_clock_estimate_bounds_include_snapshot_latency(tmp_path):
    r = recorder(tmp_path)
    r.samples = [dict(phase='DECODE_BENCHMARK', active_during_sample=True,
                      uptime_cycles=cycles, clock_before=start, clock_after=start+0.002)
                 for cycles, start in [(1234, 10), (200001234, 12)]]
    clock = r.clock_summary()['DECODE_BENCHMARK']
    assert abs(clock['estimate_mhz']-100) < 1e-9
    assert clock['lower_bound_mhz'] < 100 < clock['upper_bound_mhz']
