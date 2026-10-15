#!/usr/bin/env python3
"""Run OpenTPU status, calibration or selftest through its physical USER2 image."""
import argparse
import importlib
from pathlib import Path
from opentpu.host.jtag import JtagTransport


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--host',default='localhost')
    ap.add_argument('--port',type=int,default=3721)
    ap.add_argument('--timeout',type=float,default=30.0)
    ap.add_argument('--litedram-core',type=Path,help='generated core directory matching the loaded image; default: committed DDR3-1066')
    ap.add_argument('action',choices=['smi','memcal','selftest'])
    args,extra=ap.parse_known_args()
    if args.litedram_core:
        from fedora_prepare_litedram import profile
        try:
            args.litedram_core = profile(args.litedram_core)['data']
        except (OSError, ValueError, KeyError) as e:
            ap.error('Invalid generated DDR profile: '+str(e))
    module=importlib.import_module('opentpu.host.'+args.action)
    opened=[]
    def factory(*unused):
        t=JtagTransport(args.host,args.port,args.timeout,calibration_data=args.litedram_core)
        opened.append(t)
        return t
    if args.action=='smi' and '--dev' not in extra:
        extra=['--dev',f'jtag://{args.host}:{args.port}']+extra
    if args.action=='selftest':
        # Default PCIe bandwidth runs are inappropriate over serial JTAG.
        if '--bw-mib' not in extra:
            extra=['--bw-mib','1']+extra
        if '--dev' not in extra:
            extra=['--dev',f'jtag://{args.host}:{args.port}']+extra
    if '--sim' in extra or '--fake' in extra:
        ap.error('This command selects physical JTAG; use the normal tools for simulation')
    try:
        return module.main(extra,open_transport=factory)
    finally:
        for t in opened:
            t.close()


if __name__=='__main__':
    raise SystemExit(main())
