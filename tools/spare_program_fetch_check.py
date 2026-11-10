"""Small physical regression for the program-fetch failure before model upload."""
import hashlib
import json
from pathlib import Path

import numpy as np
from opentpu import isa as I, waits as W


def inputs(reference):
    reference = Path(reference).resolve()
    result = json.loads(reference.read_text())
    assert result['status'] == 'PASS_SHARED_PIPELINE_FULL_BOARD_PROGRAM_LOAD_AND_EXECUTION'
    assert result['scope']['D'] == 128 and result['scope']['MCOLS'] == 4
    assert result['scope']['ACT_ROWS'] == 4 and result['scope']['LANES'] == 8
    assert result['expected_instructions'] == 1371 and result['output_words'] == 65
    path = reference.parent/'program.u32le.bin'
    raw = path.read_bytes()
    assert len(raw) == result['program_bytes'] == 43872
    assert hashlib.sha256(raw).hexdigest() == result['program_sha256']
    expected = (np.arange(1, 66, dtype=np.float32)+np.float32(2)).view(np.uint8)
    digest = hashlib.sha256(expected.tobytes()).hexdigest()
    controls = [row for row in result['reports'] if row['adapter'] == 'shared']
    assert len(controls) == 2 and all(row['passed'] and row['exact_match']
        and row['output_sha256'] == digest for row in controls)
    return dict(reference_sha256=hashlib.sha256(reference.read_bytes()).hexdigest(),
                program_sha256=result['program_sha256'],
                expected_output_sha256=digest,
                program_address=result['program_address'],
                source_address=0x20000+result['source_displacement'],
                output_address=0x30004), np.frombuffer(raw, dtype='<u4'), expected


def program_fetch_check(board, reference, out):
    """Require exact program bytes, 1371 retired instructions and 65 output words.

    This is a distinctive synthetic program of the reported failing length;
    it is not the unavailable original Mac LFM instruction stream.
    """
    from opentpu.host.program_verify import ProgramReadbackBoard
    assert isinstance(board, ProgramReadbackBoard), 'Mandatory program readback is required'
    binding, words, expected = inputs(reference)
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    result = dict(status='PROGRAM_FETCH_OPERAND_TRANSFER', **binding,
        limitation='Synthetic program; original LFM230M/Mac acceptance remains separate')

    def save():
        temporary = out/'manifest.json.tmp'
        temporary.write_text(json.dumps(result, indent=2)+'\n')
        temporary.replace(out/'manifest.json')

    try:
        save()
        values = np.arange(1, 66, dtype=np.float32).view(np.uint8)
        board.write(binding['source_address'], values)
        assert np.array_equal(board.read(binding['source_address'], len(values)), values)
        result['status'] = 'VERIFIED_PROGRAM_TRANSFER_AND_NATIVE_FETCH'
        save()
        program = [I.Instr.decode(words[i:i+8]) for i in range(0, len(words), 8)]
        assert np.array_equal(I.assemble(program), words), 'Reference program decode changed its words'
        entries = W.entries(words, D=board.info()['D'], S=board.slices, prog=program) \
            if board.waitc else None
        if entries is not None:
            result['wait_entry_count'] = len(entries)
            result['wait_entries_sha256'] = hashlib.sha256(
                np.asarray(entries, dtype='<u8').tobytes()).hexdigest()
        board.load_program(binding['program_address'], words, entries)
        stats = board.run(timeout=10)
        result['stats'] = stats
        save()
        actual = board.read(binding['output_address'], len(expected))
        expected.tofile(out/'expected.bin')
        actual.tofile(out/'actual.bin')
        result['actual_output_sha256'] = hashlib.sha256(actual.tobytes()).hexdigest()
        assert stats['instructions'] == [1371], stats
        assert np.array_equal(actual, expected), 'Program-fetch regression differs from the ISA result'
        result.update(status='PASS_PHYSICAL_1371_INSTRUCTION_FETCH_AND_65_EXACT_WORDS',
            instructions=1371, words_compared=65, cycles=stats['cycles'], exact_match=True)
        return result
    except BaseException as error:
        result.update(status='FAIL_PHYSICAL_PROGRAM_FETCH_REGRESSION', error=repr(error))
        raise
    finally:
        save()
