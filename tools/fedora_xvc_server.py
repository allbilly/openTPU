#!/usr/bin/env python3
"""Start the locally prepared DLC10 XVC server after the existing cable checks."""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import os

ROOT = Path(__file__).resolve().parents[1]
BOOT = Path(expand_paths('@YPCB@/firmware/xusb_xp2-boot.hex'))
BOOT_SHA256 = '4fe1a679efcc7ed7c01e738beaf29d8a1f1201731780dfc026f724a88aee527a'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path)
    ap.add_argument('--port',type=int,default=3721)
    ap.add_argument('--dry-run',action='store_true',help='print the validated commands without opening hardware')
    args = ap.parse_args()
    if not 1 <= args.port <= 65535:
        ap.error('Port must be between 1 and 65535')
    manifest_path = args.manifest
    if manifest_path is None:
        ready = ROOT/'build/fedora-openxc7/xvc-ready.json'
        if not ready.is_file():
            ap.error('Prepare the server first: python3 tools/fedora_prepare_xvc.py')
        manifest_path = Path(json.loads(ready.read_text())['manifest'])
    manifest = json.loads(manifest_path.read_text())
    if manifest.get('status') != 'SERVER_COMPILED_PROTOCOL_PASS_PHYSICAL_NOT_RUN':
        ap.error('Server manifest must record both compilation and the XPCU protocol test pass')
    binary = Path(manifest['binary'])
    if hashlib.sha256(binary.read_bytes()).hexdigest() != manifest['binary_sha256']:
        ap.error('Server binary differs from the prepared manifest')
    if hashlib.sha256(BOOT.read_bytes()).hexdigest() != BOOT_SHA256:
        ap.error('Cable boot firmware differs from the verified DLC10 workflow')
    commands = [['bash',expand_paths('@YPCB@/dlc10-init.sh')],
                [str(binary),'--cable','xilinxPlatformCableUsb','--freq','6000000',
                 '--probe-firmware',str(BOOT),'--xvc','--port',str(args.port)]]
    if args.dry_run:
        print(json.dumps(commands,indent=2));return
    # Reject an active cable owner before the initializer uploads USB firmware.
    # That upload would interrupt an in-flight SRAM configuration or XVC scan.
    for owner in ('openFPGALoader', 'hw_server', 'xsdb', 'fxload'):
        if subprocess.run(['pgrep', '-x', owner], stdout=subprocess.DEVNULL,
                          stderr=subprocess.DEVNULL).returncode == 0:
            ap.error(f'Stop the active {owner} cable client before starting XVC')
    # The initializer verifies one cable, hashes, competing cable programs and
    # the YPCB IDCODE. The server binds only to localhost and exposes raw JTAG.
    subprocess.run(commands[0],check=True)
    os.execv(commands[1][0],commands[1])


if __name__=='__main__':
    main()
