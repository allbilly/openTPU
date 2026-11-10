#!/usr/bin/env python3
"""Run otpu-chat through the full standalone JTAG or open PCIe PIO image.

Supply the generated DDR core matching the loaded image. Additional options
are otpu-chat options, such as --prompt, --max-new, --cap and --wformat.
"""
import argparse
from pathlib import Path


def physical_backend(create_transport, opened, backends=None):
    def make(name, spec, cap, dev, model=None, lookup=False,
             wformat='int8', head_format=None):
        from opentpu.host.board import Board, BoardBackend, ConfigMismatch, device_config
        if name != 'board':
            raise ValueError('This entry point requires its selected physical transport')
        transport = create_transport()
        opened.append(transport)
        info = Board(transport, lock=False).info()
        cfg = device_config(info)
        if (cfg.S, cfg.D, cfg.MCOLS, cfg.LANES, cfg.act_rows,
                info.get('core_khz'), info.get('ddr_mts')) != (1, 128, 4, 8, 4, 100000, 800):
            raise ConfigMismatch('Loaded image differs from the full DDR800 openXC7 profile '
                                 '(one slice, D=128, MCOLS=4, LANES=8, ACT_ROWS=4, 100 MHz)')
        def backend(c, images):
            result = BoardBackend(c, images, transport=transport, model=model)
            if backends is not None:
                backends.append(result)
            return result
        return backend, cfg
    return make


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--transport',required=True,choices=('jtag','pcie-pio'))
    ap.add_argument('--litedram-core',required=True,type=Path)
    ap.add_argument('--host',default='localhost',help='XVC host for JTAG')
    ap.add_argument('--port',type=int,default=3721,help='XVC port for JTAG')
    ap.add_argument('--bdf',help='Explicit enumerated BDF for PCIe PIO')
    ap.add_argument('--timeout',type=float,default=30.0)
    args,extra = ap.parse_known_args(argv)
    if any(x.split('=',1)[0] in ('--backend','--dev','--sim','--fake') for x in extra):
        ap.error('Use --transport to select this command\'s physical backend and device')
    if args.transport == 'pcie-pio' and not args.bdf:
        ap.error('--transport pcie-pio requires an explicit --bdf')
    if args.transport == 'jtag' and args.bdf:
        ap.error('--bdf applies to --transport pcie-pio')
    if args.timeout <= 0:
        ap.error('--timeout must be positive')
    from fedora_prepare_litedram import profile
    dram = profile(args.litedram_core)
    if dram['parameters'] != dict(CORE_KHZ=100000,DDR_MTS=800):
        ap.error('The complete openXC7 chat image requires the checked DDR800/100 MHz core')
    if args.transport == 'jtag':
        from opentpu.host.jtag import JtagTransport
        create = lambda: JtagTransport(args.host,args.port,args.timeout,calibration_data=dram['data'])
        device = f'jtag://{args.host}:{args.port}'
    else:
        from opentpu.host.pcie_pio import PciePioTransport
        create = lambda: PciePioTransport(args.bdf,args.timeout,calibration_data=dram['data'])
        device = 'pcie-pio://'+args.bdf
    from opentpu.host import chat
    opened = []
    backends = []
    original = chat.make_backend
    chat.make_backend = physical_backend(create,opened,backends)
    if not any(x.split('=',1)[0] == '--model' for x in extra):
        extra = ['--model','lfm2']+extra
    try:
        return chat.main(['--backend','board','--dev',device]+extra)
    finally:
        chat.make_backend = original
        for backend in backends:
            backend.close()
        for transport in opened:
            transport.close()


if __name__ == '__main__':
    raise SystemExit(main())
