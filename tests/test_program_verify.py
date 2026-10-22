"""LLM backend loads must reject corrupted program bytes before LOAD or RUN."""
import json

import numpy as np
import pytest

from opentpu import isa as I
from opentpu.host.program_verify import ProgramReadbackBoard
from opentpu.host import regs as R
from opentpu.host.board import BoardBackend
from opentpu.isasim import board_config


class MemoryTransport:
    devname = None

    def __init__(self):
        self.ch = [np.zeros(1 << 19, np.uint8) for _ in range(2)]
        self.regs = {R.R_ID: R.ID_OTPU, R.R_VERSION: 128 << 16 | 2 << 8 | 8,
                     R.R_REGMAP: 3, R.R_CAPS: R.CAP_CHASH}
        self.events = []
        self.corrupt = False

    def reg_read(self, off):
        return self.regs.get(off, 0)

    def reg_read_many(self, offsets):
        return [self.reg_read(off) for off in offsets]

    def reg_write(self, off, value):
        self.events.append(('register', off, value))
        self.regs[off] = value

    def poll(self, off, mask, value, *args):
        return value

    def mem_write(self, channel, off, data):
        self.ch[channel][off:off + len(data)] = data

    def mem_read(self, channel, off, size):
        self.events.append(('read', channel, off))
        data = self.ch[channel][off:off + size].copy()
        if self.corrupt and channel == 0:
            data[0] ^= 1
        return data


@pytest.mark.parametrize('corrupt', [False, True])
def test_backend_checks_program_before_load_and_run(tmp_path, corrupt):
    transport = MemoryTransport()
    receipts = tmp_path / 'programs'
    backend = BoardBackend(board_config(DRAM_BYTES=1 << 20, MCOLS=2),
                           [np.zeros(128, np.uint8)], transport=transport,
                           status=False, program_receipts=receipts)
    program = [[I.li(1, 0), I.nop(), I.nop(), I.halt()]]
    transport.corrupt = corrupt
    transport.events.clear()
    try:
        if corrupt:
            with pytest.raises(RuntimeError, match='readback differs before IMEM load'):
                backend.start(program)
            assert not any(event[0] == 'register' for event in transport.events)
            assert (receipts / 'program-000001.expected.bin').is_file()
            assert (receipts / 'program-000001.actual.bin').is_file()
        else:
            backend.start(program)
            load = ('register', R.R_CTRL, R.CTRL_LOAD)
            run = ('register', R.R_CTRL, R.CTRL_RUN)
            assert transport.events.index(load) < transport.events.index(run)
            assert any(event[0] == 'read' for event in
                       transport.events[:transport.events.index(load)])
        result = json.loads((receipts / 'program-000001.json').read_text())
        assert result['imem_load_finished'] is not corrupt
        assert result['imem_load_requested'] is not corrupt
        assert result['status'].startswith('FAIL_' if corrupt else 'PASS_')
    finally:
        backend.close()


# Retained local direct-board mapping, partial-tail and corruption coverage.
class Memory:
    def __init__(self, chash=False):
        self.ch = [np.zeros(1 << 17, np.uint8) for _ in (0, 1)]
        self.regs = {R.R_VERSION:128 << 16 | 4 << 8 | 8, R.R_REGMAP:3,
                     R.R_CAPS:R.CAP_CHASH if chash else 0}
        self.writes = []
        self.corrupt = False

    def reg_read_many(self, offsets):
        return [self.regs.get(off, 0) for off in offsets]

    def reg_write(self, off, value):
        self.writes.append((off, value))

    def poll(self, off, mask, value):
        assert self.writes[-1] == (R.R_CTRL, R.CTRL_LOAD)
        return 0

    def mem_write(self, ch, off, data):
        self.ch[ch][off:off+len(data)] = data

    def mem_read(self, ch, off, count):
        data = self.ch[ch][off:off+count].copy()
        if self.corrupt and ch == 0 and len(data):
            data[0] ^= 0x80
        return data


@pytest.mark.parametrize('chash', [False, True])
@pytest.mark.parametrize('instructions', [1, 3, 1371])
def test_verified_load_preserves_mapping_and_partial_tail(tmp_path, chash, instructions):
    t = Memory(chash)
    b = ProgramReadbackBoard(t, check=False, program_receipts=tmp_path/'programs')
    words = np.arange(instructions*8, dtype=np.uint32) ^ np.uint32(0xc0182301)
    b.load_program(16384, words)
    assert t.writes == [(R.R_CTRL,0),(R.R_PROG_ADDR,16384),
                        (R.R_PROG_N,instructions),(R.R_CTRL,R.CTRL_LOAD)]
    receipt = json.loads((tmp_path/'programs/program-000001.json').read_text())
    assert receipt['status'] == 'PASS_PROGRAM_READBACK_AND_LOAD_COMPLETION'
    assert receipt['expected_sha256'] == receipt['actual_sha256']


@pytest.mark.parametrize('chash', [False, True])
def test_bad_ch0_readback_blocks_load_and_saves_bytes(tmp_path, chash):
    t = Memory(chash)
    b = ProgramReadbackBoard(t, check=False, program_receipts=tmp_path/'programs')
    words = np.arange(1371*8, dtype=np.uint32)
    t.corrupt = True
    with pytest.raises(RuntimeError, match='before IMEM load'):
        b.load_program(16384, words)
    assert t.writes == []
    receipt = json.loads((tmp_path/'programs/program-000001.json').read_text())
    assert receipt['status'] == 'FAIL_PROGRAM_READBACK_IMEM_LOAD_WITHHELD'
    assert receipt['different_words'] == 1
    assert not receipt['imem_load_requested']
    assert (tmp_path/'programs/program-000001.expected.bin').stat().st_size == words.nbytes
    assert (tmp_path/'programs/program-000001.actual.bin').stat().st_size == words.nbytes
