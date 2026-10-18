"""LLM backend loads must reject corrupted program bytes before LOAD or RUN."""
import json

import numpy as np
import pytest

from opentpu import isa as I
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
