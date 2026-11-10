"""Shared runner for the small operation examples. Importing it opens no device."""
from dataclasses import asdict, replace
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[2]   # ladder/examples -> repo root
# A reviewed experimental image can require its matching full host source tree.
SOURCE = Path(os.environ.get('OTPU_EXAMPLES_SOURCE_ROOT', ROOT)).expanduser().resolve()
if not (SOURCE / 'opentpu/runtime.py').is_file():
    raise RuntimeError('OTPU_EXAMPLES_SOURCE_ROOT must contain the full opentpu package')
sys.path.insert(0, str(SOURCE))

import numpy as np
from opentpu import Config, isa, language as ol
from opentpu.runtime import Input, Output, Weight, collect, compile_kernel, run


def positive(value):
    number = int(value)
    if not 1 <= number <= 4096:
        raise argparse.ArgumentTypeError('choose an integer from 1 through 4096')
    return number


def parser(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--backend', choices=['isa', 'rtl', 'fpga'], default='isa')
    p.add_argument('--seed', type=int, default=1)
    p.add_argument('--out', type=Path, help='fresh output directory, for example build/examples/add')
    p.add_argument('--show-program', action='store_true', help='print the emitted accelerator instructions')
    p.add_argument('--package', type=Path, help='exact reviewed runtime package; required for fpga')
    p.add_argument('--transport', choices=['jtag', 'chestnut', 'xdma'], default='jtag')
    p.add_argument('--mode', type=int, choices=range(4), help='explicit runtime clock mode for fpga')
    p.add_argument('--xvc-host', default='127.0.0.1')
    p.add_argument('--xvc-port', type=int, default=3721)
    p.add_argument('--dev', default='/dev/xdma0')
    return p


def config():
    # Board arithmetic geometry, with a small simulation allocation. FPGA activation
    # validates the real geometry and substitutes the real 4 GiB address capacity.
    return Config(S=1, D=128, MCOLS=4, LANES=8, ACT_BLOCKS=128,
                  IMEM_WORDS=1 << 15, DRAM_BYTES=1 << 20,
                  PAIR=True, DSTEP=True, STREAM=True)


def bounded(p, *shapes):
    if any(int(np.prod(shape)) > 8192 for shape in shapes):
        p.error('keep each example tensor at or below 8192 elements')


def exact_int8_rows(rng, rows, columns):
    """Integer-valued fp32 data with unit quantizer scales in every 128-element block."""
    values = rng.integers(-8, 9, (rows, columns)).astype(np.float32)
    values[:, ::128] = 127
    return values


def _json(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    raise TypeError(type(value).__name__)


def _fpga(compiled, images, args, folder, state, save):
    from opentpu.host.runtime_model import RuntimeBoardBackend, runtime_config
    from opentpu.host.runtime_transport import open_runtime_transport

    kwargs = (dict(host=args.xvc_host, port=args.xvc_port) if args.transport == 'jtag'
              else dict(dev=args.dev) if args.transport == 'xdma' else {})
    transport = backend = None
    try:
        state['hardware_access_attempted'] = True
        state['hardware_accessed'] = None
        state['stage'] = 'opening_transport'
        save()
        transport = open_runtime_transport(args.package, args.transport, **kwargs)
        state['hardware_accessed'] = True
        state['stage'] = 'validating_live_geometry'
        save()
        actual = runtime_config(transport)
        wanted = replace(compiled.cfg, DRAM_BYTES=1 << 32)
        if asdict(actual) != asdict(wanted):
            raise ValueError('Live FPGA arithmetic/capabilities differ from this compiled example')
        hardware_compiled = replace(compiled, cfg=actual)
        state['stage'] = 'activating_runtime'
        save()
        backend = RuntimeBoardBackend(actual, images, transport, mode=args.mode,
                                      out=folder / 'activation', model='basic-operation-example', status=False)
        state['stage'] = 'executing_program'
        save()
        stats = backend.run(hardware_compiled.programs)
        state['stage'] = 'reading_outputs'
        save()
        # Read only the declared outputs, using the same verified backend/epoch.
        dram = np.array(images[0], copy=True)
        for argument, address in compiled.layout.params.values():
            if isinstance(argument, Output):
                length = 4 * int(np.prod(argument.shape))
                dram[address:address + length] = backend.read(0, address, length)
        result = collect(hardware_compiled, [dram], [], stats)
        state['image'] = dict(build_id=f'{transport.profile.build_id:08x}',
                             bitstream_sha256=transport.profile.bitstream_sha256,
                             mode=args.mode)
        return result
    finally:
        try:
            if backend is not None:
                backend.close()
        finally:
            if transport is not None:
                transport.close()


def execute(name, p, args, kernel, arguments, references, *, rtol=1e-5, atol=1e-6, notes=None):
    if args.backend == 'fpga':
        if args.package is None or args.mode is None or args.out is None:
            p.error('--backend fpga requires --package, --mode and a fresh --out directory')
        # Validate the complete image/software package before any device opening.
        from opentpu.host.runtime_transport import ReviewedRuntimeProfile
        ReviewedRuntimeProfile(args.package)
    elif args.package is not None or args.mode is not None:
        p.error('--package and --mode apply only to --backend fpga')
    compiled, images = compile_kernel(kernel, config(), **arguments)
    if any(len(isa.assemble(program)) > compiled.cfg.IMEM_WORDS for program in compiled.programs):
        raise ValueError('Example program exceeds instruction memory')
    assembly = isa.disassemble(compiled.programs[0])
    if args.show_program:
        print(assembly)
    folder = args.out.expanduser().resolve() if args.out else None
    state = dict(status='RUNNING', example=name, backend=args.backend, seed=args.seed,
                 config=asdict(compiled.cfg), instruction_count=len(compiled.programs[0]),
                 hardware_access_attempted=False, hardware_accessed=False, flash_written=False,
                 checks={}, notes=notes or [])

    def save():
        if folder is not None:
            temporary = folder / 'result.json.tmp'
            temporary.write_text(json.dumps(state, indent=2, default=_json) + '\n')
            temporary.replace(folder / 'result.json')

    if folder is not None:
        folder.mkdir(parents=True, exist_ok=False)
        images[0].tofile(folder / 'dram.bin')
        words = np.asarray(isa.assemble(compiled.programs[0]), dtype='<u4')
        words.tofile(folder / 'program.bin')
        (folder / 'program.asm').write_text(assembly + '\n')
        state['program_sha256'] = hashlib.sha256(words.tobytes()).hexdigest()
        state['initial_image_sha256'] = hashlib.sha256(images[0].tobytes()).hexdigest()
        save()
    try:
        started = time.perf_counter()
        golden = run(compiled, images, backend='isa')
        actual = (golden if args.backend == 'isa' else run(compiled, images, backend='rtl')
                  if args.backend == 'rtl' else _fpga(compiled, images, args, folder, state, save))
        state['run_wall_seconds'] = time.perf_counter() - started
        state['stats'] = actual.stats
        for output, expected in references.items():
            got = actual.outputs[output]
            expected = np.asarray(expected, dtype=np.float32)
            np.testing.assert_allclose(got, expected, rtol=rtol, atol=atol, equal_nan=False,
                                       err_msg=f'{name}/{output}: NumPy comparison')
            bit_exact = np.array_equal(got.view(np.uint32), golden.outputs[output].view(np.uint32))
            if not bit_exact:
                raise AssertionError(f'{name}/{output}: {args.backend} differs from exact ISA output')
            state['checks'][output] = dict(shape=list(got.shape), numpy_match=True,
                                          isa_bit_exact=True, rtol=rtol, atol=atol,
                                          max_abs_error=float(np.max(np.abs(got - expected))),
                                          sample=got.reshape(-1)[:8].tolist())
            if folder is not None:
                np.save(folder / (output + '.npy'), got)
                np.save(folder / (output + '.reference.npy'), expected)
        state['status'] = 'PASS'
        save()
    except BaseException as error:
        state.update(status='FAIL', error=repr(error))
        save()
        raise
    print(f"PASS {name}: backend={args.backend}, instructions={state['instruction_count']}")
    for output, row in state['checks'].items():
        print(f"  {output}: shape={row['shape']}, max_abs_error={row['max_abs_error']:.3g}, sample={row['sample']}")
    return state
