"""Initialization progress must preserve coverage, pacing and failed evidence."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

from opentpu.host import regs as R, spare_c0182863 as S
from opentpu.host.board import Board
from tools import run_lfm_spare_c0182863 as runner


class Memory(S._SpareMemory):
    ecc = True

    def __init__(self, fault=None):
        self.status = R.ST_CALIB0 | R.ST_CALIB1 | R.ST_WR_IDLE
        self._dma = threading.RLock()
        self.operations = []
        self.marker = R.DRAM_INIT
        self.fault = fault
        self.values = {ch: dict(ecc_enable=ch, ecc_sec_errors=0, ecc_ded_errors=0,
                               cal_ready=1, bist_done=1, bist_raw_sequence=0xfffffff0)
                       for ch in (0, 1)}
        self.channels = {}
        for ch in (0, 1):
            def write(name, value, ch=ch):
                state = self.values[ch]
                state[name] = value
                if name != 'bist_start':
                    return
                self.operations.append((ch, state['bist_mode'], state['bist_base']))
                read = state['bist_mode'] == 1
                state.update(bist_beats=state['bist_length'], bist_ticks=100,
                             bist_raw_sequence=(state['bist_raw_sequence']+1) & 0xffffffff,
                             bist_raw_returns=state['bist_length'] if read else 0,
                             bist_errors=0, bist_lane_bits=0)
                for lane in range(8 if ch == 0 else 9):
                    state[f'bist_lane{lane}_errors'] = 0
                if len(self.operations) != 1025:
                    return
                if self.fault == 'lane':
                    state['bist_lane6_errors'] = 1
                elif self.fault == 'returns':
                    state['bist_raw_returns'] -= 1
                elif self.fault == 'epoch':
                    state['bist_raw_sequence'] -= 1
                elif self.fault == 'ticks':
                    state['bist_ticks'] = 0
                elif self.fault == 'timeout':
                    state['bist_done'] = 0
                elif self.fault == 'interrupt':
                    raise KeyboardInterrupt

            self.channels[ch] = SimpleNamespace(r=self.values[ch].__getitem__, w=write)

    def reg_read(self, off):
        if off == R.R_SCRATCH:
            return self.marker
        assert off == R.R_STATUS
        return self.status

    def guard(self):
        super().guard()
        if self.fault == 'final-guard' and len(self.operations) == 2048:
            raise ValueError('final readiness check failed')

    def reg_write(self, off, value):
        assert off == R.R_SCRATCH
        self.marker = value


def initialize(tmp_path, monkeypatch, fault=None, experimental_pause_seconds=None):
    clock = SimpleNamespace(now=0., sleeps=[])

    def sleep(seconds):
        clock.sleeps.append(seconds)
        clock.now += seconds

    timer = SimpleNamespace(monotonic=lambda: clock.now, sleep=sleep)
    monkeypatch.setattr(S, 'time', timer)
    monkeypatch.setattr(runner, 'time', timer)
    transport = Memory(fault)
    board = Board.__new__(Board)
    board.t = transport
    result = {}
    saved = []

    def save():
        saved.append(dict(result['zero_initialization_progress']))

    def run():
        runner.zero_initialize(board, transport, tmp_path, result, save,
                               experimental_pause_seconds=experimental_pause_seconds)

    return transport, result, saved, clock, run


def test_complete_coverage_and_progress_keep_existing_200ms_pacing(tmp_path, monkeypatch):
    transport, result, saved, clock, run = initialize(tmp_path, monkeypatch)
    run()
    rows = [json.loads(line) for line in (tmp_path/'zero-initialization-chunks.jsonl').read_text().splitlines()]
    expected = [(mode, ch, base) for mode in (0, 1) for ch in (0, 1)
                for base in range(0, 1 << 31, 4 << 20)]
    assert [(r['chunk']['mode'], r['chunk']['channel'], r['chunk']['base']) for r in rows] == expected
    assert [r['progress']['completed_chunks'] for r in rows] == list(range(1, 2049))
    assert len(result['zero_initialization_chunks']) == 2048
    assert len(clock.sleeps) == 2048 and set(clock.sleeps) == {.2}
    assert clock.now == pytest.approx(409.6)
    assert saved[1]['completed_chunks'] == 1 and not saved[1]['initialization_complete']
    assert saved[-1]['initialization_complete'] and saved[-1]['all_chunks_validated']
    assert transport.marker == R.DRAM_INIT and not hasattr(transport, 'scrub_progress')


@pytest.mark.parametrize('fault', ['lane', 'returns', 'epoch', 'ticks', 'timeout', 'interrupt'])
def test_failure_preserves_partial_progress_and_never_sets_marker(tmp_path, monkeypatch, fault):
    transport, result, saved, _, run = initialize(tmp_path, monkeypatch, fault)
    expected = KeyboardInterrupt if fault == 'interrupt' else TimeoutError if fault == 'timeout' else ValueError
    with pytest.raises(expected):
        run()
    rows = (tmp_path/'zero-initialization-chunks.jsonl').read_text().splitlines()
    assert len(transport.operations) == 1025 and len(rows) == 1024
    assert saved[-1]['completed_chunks'] == 1024
    assert not saved[-1]['initialization_complete'] and not saved[-1]['all_chunks_validated']
    assert transport.marker == 0 and not hasattr(transport, 'scrub_progress')
    expected_records = 1024 if fault in ('timeout', 'interrupt') else 1025
    assert len(result['zero_initialization_chunks']) == expected_records
    if fault == 'lane':
        assert result['zero_initialization_chunks'][-1]['lanes'][6] == 1


def test_busy_accelerator_still_blocks_all_bist_operations(tmp_path, monkeypatch):
    transport, result, saved, _, run = initialize(tmp_path, monkeypatch)
    transport.status |= R.ST_RUN
    with pytest.raises(ValueError, match='idle'):
        run()
    assert not transport.operations and transport.marker == R.DRAM_INIT
    assert not saved[-1]['initialization_complete']


def test_all_chunks_do_not_hide_failed_final_readiness(tmp_path, monkeypatch):
    transport, result, saved, _, run = initialize(tmp_path, monkeypatch, 'final-guard')
    with pytest.raises(ValueError, match='final readiness'):
        run()
    assert saved[-1]['completed_chunks'] == 2048
    assert not saved[-1]['initialization_complete'] and not saved[-1]['all_chunks_validated']
    assert len(result['zero_initialization_chunks']) == 2048 and transport.marker == 0


def test_progress_journal_failure_blocks_initialization_marker(tmp_path, monkeypatch):
    transport, _, saved, _, run = initialize(tmp_path, monkeypatch)
    monkeypatch.setattr(runner.json, 'dumps', lambda _: (_ for _ in ()).throw(OSError('disk full')))
    with pytest.raises(OSError, match='disk full'):
        run()
    assert len(transport.operations) == 1 and transport.marker == 0
    assert not saved[-1]['initialization_complete']


@pytest.mark.parametrize('pause', [0, .005, .02, .05, .2])
def test_explicit_pacing_keeps_full_coverage_and_restores_transport(tmp_path, monkeypatch, pause):
    transport, result, _, clock, run = initialize(tmp_path, monkeypatch, experimental_pause_seconds=pause)
    run()
    assert len(transport.operations) == 2048 and transport.marker == R.DRAM_INIT
    rows = [json.loads(line) for line in (tmp_path/'zero-initialization-chunks.jsonl').read_text().splitlines()]
    assert [(row['chunk']['mode'], row['chunk']['channel'], row['chunk']['base']) for row in rows] == [
        (mode, ch, base) for mode in (0, 1) for ch in (0, 1)
        for base in range(0, 1 << 31, 4 << 20)]
    assert all(row['progress']['pause_seconds_per_chunk'] == pause for row in rows)
    assert clock.sleeps == ([pause]*2048 if pause else [])
    assert clock.now == pytest.approx(2048*pause)
    policy = result['zero_initialization_policy']
    assert policy['experimental'] and not policy['faster_pacing_physically_qualified']
    assert policy['full_write_and_read_verification_required']
    assert policy['planned_pause_seconds'] == pytest.approx(2048*pause)
    assert 'scrub' not in vars(transport) and not hasattr(transport, 'scrub_progress')


@pytest.mark.parametrize('fault', ['lane', 'returns', 'epoch', 'ticks', 'timeout', 'interrupt', 'final-guard'])
def test_fast_experiment_retains_error_guards_and_restores_callback(tmp_path, monkeypatch, fault):
    transport, result, saved, _, run = initialize(tmp_path, monkeypatch, fault, experimental_pause_seconds=0)
    expected = KeyboardInterrupt if fault == 'interrupt' else TimeoutError if fault == 'timeout' else ValueError
    with pytest.raises(expected):
        run()
    assert transport.marker == 0 and not saved[-1]['initialization_complete']
    assert not saved[-1]['all_chunks_validated']
    assert 'scrub' not in vars(transport) and not hasattr(transport, 'scrub_progress')


@pytest.mark.parametrize('pause', [True, False, -.001, .001, .201, float('nan'), float('inf'), '0', object()])
def test_invalid_pacing_rejected_before_any_hardware_write(tmp_path, monkeypatch, pause):
    transport, _, _, _, run = initialize(tmp_path, monkeypatch, experimental_pause_seconds=pause)
    with pytest.raises(ValueError, match='Experimental initialization pause'):
        run()
    assert not transport.operations and transport.marker == R.DRAM_INIT
    assert not list(tmp_path.iterdir())
    with pytest.raises(ValueError, match='Experimental initialization pause'):
        transport.scrub(experimental_pause_seconds=pause)
    assert not transport.operations and transport.marker == R.DRAM_INIT


@pytest.mark.parametrize('stage', ['identity', 'memory', 'inference'])
def test_experiment_only_accepted_for_lfm_before_opening_hardware(tmp_path, monkeypatch, stage):
    def unexpected_open(*args, **kwargs):
        pytest.fail('Invalid experiment attempted to open hardware')
    monkeypatch.setattr(runner, 'SparePcieProfile', unexpected_open)
    out = tmp_path/'not-created'
    with pytest.raises(SystemExit) as error:
        runner.main(['--package', 'unused', '--out', str(out), '--stage', stage,
                     '--experimental-init-pause-ms', '0'])
    assert error.value.code == 2 and not out.exists()


@pytest.mark.parametrize('pause', [None, '0', '20', '200'])
def test_mac_launcher_passes_pacing_only_to_the_lfm_stage(tmp_path, pause):
    calls = tmp_path/'calls.jsonl'
    python = tmp_path/'record-python'
    python.write_text(f'#!{sys.executable}\nimport json,os,sys\n'
                      "with open(os.environ['CAPTURE_CALLS'], 'a') as stream:\n"
                      "    stream.write(json.dumps(sys.argv[1:])+'\\n')\n")
    python.chmod(0o700)
    env = {k: v for k, v in os.environ.items() if k != 'SPARE_EXPERIMENTAL_INIT_PAUSE_MS'}
    env.update(SPARE_PYTHON=str(python), CAPTURE_CALLS=str(calls), SPARE_OUT=str(tmp_path/'out'))
    if pause is not None:
        env['SPARE_EXPERIMENTAL_INIT_PAUSE_MS'] = pause
    subprocess.run(['bash', str(Path(runner.ROOT)/'tools/mac_spare_c0182863.sh'), 'lfm'],
                   env=env, check=True, capture_output=True, text=True)
    recorded = [json.loads(line) for line in calls.read_text().splitlines()]
    assert len(recorded) == 4
    for argv in recorded:
        is_lfm = '--stage' in argv and argv[argv.index('--stage')+1] == 'lfm'
        assert ('--experimental-init-pause-ms' in argv) == (is_lfm and pause is not None)
        if is_lfm and pause is not None:
            assert argv[argv.index('--experimental-init-pause-ms')+1] == pause


@pytest.mark.parametrize('stage,pause', [('lfm', ''), ('lfm', '-1'), ('lfm', '1'),
                                         ('lfm', 'NaN'), ('quick', '0'), ('preflight', '20')])
def test_mac_launcher_rejects_invalid_experiment_before_python(tmp_path, stage, pause):
    capture = tmp_path/'python-started'
    python = tmp_path/'record-python'
    python.write_text('#!/usr/bin/env bash\ntouch "$CAPTURE_CALLS"\n')
    python.chmod(0o700)
    env = dict(os.environ, SPARE_PYTHON=str(python), CAPTURE_CALLS=str(capture),
               SPARE_EXPERIMENTAL_INIT_PAUSE_MS=pause, SPARE_OUT=str(tmp_path/'out'))
    result = subprocess.run(['bash', str(Path(runner.ROOT)/'tools/mac_spare_c0182863.sh'), stage],
                            env=env, capture_output=True, text=True)
    assert result.returncode == 2 and not capture.exists()
