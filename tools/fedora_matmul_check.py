"""Compact physical matmul comparison used before full model inference."""

def require(ok, message):
    if not ok:
        raise ValueError(message)


def matmul_check(board):
    import numpy as np
    from opentpu import isa as I
    from opentpu.isasim import Machine
    from opentpu.host.board import device_config
    from opentpu.host.checks import demo_image, DATA, W8, SC, OUT, PROG_AT

    cfg = device_config(board.info(), DRAM_BYTES=1 << 23)
    image = demo_image()
    program = [I.ld(DATA, 0, 512), I.qact(0, 2, 0, 2, 256),
               I.mm(W8, SC, 1024, 16, 2, 256, 16, 2, 0, 8),
               I.st(OUT, 1024, 32), I.halt()]
    dram = np.zeros(1 << 23, np.uint8)
    dram[:len(image)] = image
    expected = Machine(cfg, [program], [dram]).run().slices[0]
    # Only defined operands are transferred. Full DDR was initialized and tested.
    for start, length in [(DATA, 512*4), (W8, 16*256), (SC, 64*4)]:
        board.write(start, image[start:start+length])
        got = board.read(start, length)
        require(np.array_equal(got, image[start:start+length]),
                f'Matmul operand transfer failed at {start:#x}')
    board.load_program(PROG_AT, np.asarray(I.assemble(program), np.uint32))
    stats = board.run(timeout=10)
    actual = board.read(OUT, 32*4)
    want = expected.dram[OUT:OUT+32*4]
    result = dict(physical=True, operation='MM int8 weights with QACT',
                  output_shape=[2, 16], reduction=256, bytes_compared=128,
                  expected_instructions=expected.icount,
                  actual_instructions=stats['instructions'][0], cycles=stats['cycles'],
                  exact_match=bool(np.array_equal(actual, want)),
                  actual_words=actual.view('<u4').tolist(),
                  expected_words=want.view('<u4').tolist())
    return result
