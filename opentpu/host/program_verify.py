"""Verify program DRAM bytes before asking the FPGA to load instruction RAM."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np

from .board import Board
from . import regs as R


class ProgramReadbackBoard(Board):
    """Board with a mandatory pre-load comparison and per-program receipts.

The comparison observes the normal host read path. It can detect corruption
but cannot independently distinguish writes from reads or attest IMEM bytes.
On mismatch, retain both byte streams before issuing any load/control write.
"""

    def __init__(self, *args, program_receipts, **kwargs):
        self.program_receipts = Path(program_receipts)
        self.program_receipts.mkdir(parents=True, exist_ok=False)
        self._program_ordinal = 0
        super().__init__(*args, **kwargs)

    def load_program(self, addr, words):
        words = np.asarray(words, dtype='<u4')
        if words.ndim != 1 or not len(words) or len(words) % 8 or addr < 0 or addr % 128:
            raise ValueError('Program needs a chunk-aligned address and complete 8-word instructions')
        expected = np.ascontiguousarray(words).view(np.uint8).reshape(-1)
        self._program_ordinal += 1
        stem = self.program_receipts / f'program-{self._program_ordinal:06d}'
        state = dict(status='WRITING_PROGRAM', logical_address=addr, bytes=len(expected),
                     words=len(words), instructions=len(words)//8, chash=self.chash,
                     expected_sha256=hashlib.sha256(expected.tobytes()).hexdigest(),
                     imem_load_requested=False, imem_load_finished=False,
                     limitation='Host write/read path; does not localize writes versus reads or attest IMEM contents')

        def save():
            state['utc'] = datetime.now(timezone.utc).isoformat()
            temp = stem.with_suffix('.json.tmp')
            temp.write_text(json.dumps(state, indent=2)+'\n')
            temp.replace(stem.with_suffix('.json'))

        try:
            save()
            self.write(addr, expected)
            state['status'] = 'READING_PROGRAM_BACK'
            save()
            actual = np.asarray(self.read(addr, len(expected)), dtype=np.uint8).reshape(-1)
            state['read_bytes'] = len(actual)
            state['actual_sha256'] = hashlib.sha256(actual.tobytes()).hexdigest()
            if not np.array_equal(actual, expected):
                expected.tofile(stem.with_suffix('.expected.bin'))
                actual.tofile(stem.with_suffix('.actual.bin'))
                if len(actual) == len(expected):
                    bad = np.flatnonzero(actual != expected)
                    bad_words = np.flatnonzero(actual.view('<u4') != words)
                    state.update(different_bytes=int(len(bad)), different_words=int(len(bad_words)),
                                 first_bad_byte=int(bad[0]), last_bad_byte=int(bad[-1]),
                                 first_bad_word=int(bad_words[0]),
                                 expected_first_bad_word=int(words[bad_words[0]]),
                                 actual_first_bad_word=int(actual.view('<u4')[bad_words[0]]))
                state['status'] = 'FAIL_PROGRAM_READBACK_IMEM_LOAD_WITHHELD'
                save()
                raise RuntimeError(f'Program DRAM readback differs before IMEM load; evidence: {stem}.json')
            state['status'] = 'PROGRAM_READBACK_EXACT_IMEM_LOAD_REQUESTED'
            save()
            # Same register sequence as Board.load_program, after comparison.
            self.t.reg_write(R.R_CTRL, 0)
            self.t.reg_write(R.R_PROG_ADDR, addr)
            self.t.reg_write(R.R_PROG_N, len(words)//8)
            state['imem_load_requested'] = True
            save()
            self.t.reg_write(R.R_CTRL, R.CTRL_LOAD)
            self.t.poll(R.R_STATUS, R.ST_LOADING, 0)
            state.update(status='PASS_PROGRAM_READBACK_AND_LOAD_COMPLETION', imem_load_finished=True)
        except BaseException as error:
            if state['status'] != 'FAIL_PROGRAM_READBACK_IMEM_LOAD_WITHHELD':
                state['status'] = 'FAIL_PROGRAM_TRANSFER_OR_LOAD'
            state['error'] = repr(error)
            raise
        finally:
            save()
