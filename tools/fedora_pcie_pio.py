#!/usr/bin/env python3
"""Run OpenTPU status, calibration or selftest on its open PCIe PIO image."""
import argparse
import importlib
from pathlib import Path
from opentpu.host.pcie_pio import PciePioTransport


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--bdf',required=True,help='explicit enumerated YPCB BDF, e.g. 0000:01:00.0')
    ap.add_argument('--timeout',type=float,default=30.0)
    ap.add_argument('--litedram-core',required=True,type=Path)
    ap.add_argument('action',choices=['smi','memcal','selftest'])
    args,extra = ap.parse_known_args()
    from fedora_prepare_litedram import profile
    data = profile(args.litedram_core)['data']
    if '--sim' in extra or '--fake' in extra:
        ap.error('This command selects physical PCIe PIO; use the normal tools for simulation')
    if args.action in ('smi','selftest') and '--dev' not in extra:
        extra = ['--dev','pcie-pio://'+args.bdf]+extra
    opened = []
    def factory(*unused):
        transport = PciePioTransport(args.bdf,args.timeout,calibration_data=data)
        opened.append(transport)
        return transport
    try:
        return importlib.import_module('opentpu.host.'+args.action).main(extra,open_transport=factory)
    finally:
        for transport in opened:
            transport.close()


if __name__ == '__main__':
    raise SystemExit(main())
