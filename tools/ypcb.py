#!/usr/bin/env python3
"""Portable Linux entry points for YPCB CH1 builds, programming and inference."""
import argparse
from pathlib import Path
import runpy
import sys

COMMANDS = {
    'build-jtag': 'fedora_build_vivado_ch1_jtag',
    'build-pcie': 'fedora_build_vivado_ch1_recovery',
    'review-pcie': 'fedora_review_ch1_pcie',
    'program-sram': 'fedora_program_ch1_sram',
    'program-flash': 'fedora_flash_ch1_pcie',
    'run-lfm2': 'fedora_run_ch1_lfm2',
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=COMMANDS)
    parser.add_argument('arguments', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path[:0] = [str(root), str(root / 'tools')]
    sys.argv = [Path(__file__).name + ' ' + args.command, *args.arguments]
    runpy.run_module('tools.' + COMMANDS[args.command], run_name='__main__')


if __name__ == '__main__':
    main()
