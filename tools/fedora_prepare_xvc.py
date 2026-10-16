#!/usr/bin/env python3
"""Build an isolated DLC10/XPCU XVC server from the local working loader.

Existing cable firmware/USB fixes are captured with hashes. The donor checkout
and binaries are left intact. This prepares software; it does not open a cable.
"""

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths
from datetime import datetime, timezone
import argparse
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def digest(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def run(cmd, out, name):
    (out/f'{name}.command.json').write_text(json.dumps([str(x) for x in cmd],indent=2)+'\n')
    with (out/f'{name}.log').open('w') as log:
        code = subprocess.run(cmd,stdout=log,stderr=subprocess.STDOUT).returncode
    (out/f'{name}.exit').write_text(str(code)+'\n')
    if code:
        raise RuntimeError(f'{name} exited {code}; see {out/name}.log')


def extend(src):
    """Use the existing cable encoder and decoder for mixed TMS/TDI scans."""
    originals = {}
    def replace(rel, old, new):
        p = src/rel
        text = p.read_text()
        if text.count(old) != 1:
            raise RuntimeError('Source no longer matches the reviewed XVC extension: '+rel)
        originals.setdefault(rel,text)
        p.write_text(text.replace(old,new))

    replace('src/xilinxPlatformCableUSB.hpp',
        '\tint setClkFreq(uint32_t clkHz) override;',
        '\tint setClkFreq(uint32_t clkHz) override;\n\tbool writeTMSTDI(const uint8_t *tms, const uint8_t *tdi,\n\t\tuint8_t *tdo, uint32_t len) override;')
    method = '''bool XilinxPlatformCableUSB::writeTMSTDI(const uint8_t *tms,
        const uint8_t *tdi, uint8_t *tdo, uint32_t len)
{
    if (len == 0)
        return true;
    if (!tms || !tdi || !tdo)
        return false;
    if (_nb_bit != 0 && write(nullptr, 0) < 0)
        return false;
    std::memset(tdo, 0, (len + 7) / 8);
    uint32_t rx_offset = 0;
    for (uint32_t i = 0; i < len; ++i) {
        _curr_tms = (tms[i >> 3] >> (i & 7)) & 1;
        _curr_tdi = (tdi[i >> 3] >> (i & 7)) & 1;
        if (storeBit(_curr_tdi, _curr_tms, 1, 1)) {
            const uint32_t bits = _nb_tdo_bit;
            if (write(tdo, rx_offset) < 0)
                return false;
            rx_offset += bits;
        }
    }
    return _nb_bit == 0 || write(tdo, rx_offset) >= 0;
}

'''
    replace('src/xilinxPlatformCableUSB.cpp',
        'int XilinxPlatformCableUSB::writeTMS(', method+'int XilinxPlatformCableUSB::writeTMS(')
    replace('src/xvc_server.cpp', '#include "ftdiJtagMPSSE.hpp"',
        '#include "ftdiJtagMPSSE.hpp"\n#ifdef ENABLE_XILINX_PLATFORM_CABLE_USB\n#include "xilinxPlatformCableUSB.hpp"\n#endif')
    replace('src/xvc_server.cpp', '\tswitch (cable.type) {',
        '\tswitch (cable.type) {\n#ifdef ENABLE_XILINX_PLATFORM_CABLE_USB\n\tcase MODE_XPCU:\n\t\t_jtag = new XilinxPlatformCableUSB(cable.vid, cable.pid, clkHZ, firmware_path, verbose);\n\t\tbreak;\n#endif')
    replace('src/xvc_server.cpp', '_sock_addr.sin_addr.s_addr = INADDR_ANY;',
        '_sock_addr.sin_addr.s_addr = htonl(INADDR_LOOPBACK);')
    replace('src/xvc_server.cpp',
        '\t\t\t_jtag->writeTMSTDI(_tmstdi, _tmstdi + nr_bytes, _result, len);',
        '\t\t\tif (!_jtag->writeTMSTDI(_tmstdi, _tmstdi + nr_bytes, _result, len)) {\n\t\t\t\tprintError("JTAG mixed-vector transfer failed");\n\t\t\t\treturn 1;\n\t\t\t}')
    return ''.join(''.join(difflib.unified_diff(text.splitlines(True), (src/rel).read_text().splitlines(True),
                                             fromfile='a/'+rel,tofile='b/'+rel))
                   for rel,text in originals.items())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--donor',type=Path,default=Path(expand_paths('@YPCB@/openFPGALoader')))
    ap.add_argument('--out',type=Path)
    ap.add_argument('--usb-altsetting-patch',type=Path,
                    help='apply a reviewed FX2 descriptor-aware alternate-setting patch to the isolated copy')
    ap.add_argument('--jobs',type=int,default=os.cpu_count() or 1)
    ap.add_argument('--cxx', default=os.environ.get('CXX', 'c++'))
    ap.add_argument('--pkg-config', default=shutil.which('pkg-config') or 'pkg-config')
    ap.add_argument('--no-select',action='store_true',
                    help='preserve xvc-ready.json; qualify this binary separately before selecting it')
    args = ap.parse_args()
    if args.jobs < 1:
        ap.error('--jobs must be positive')
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = (args.out or ROOT/'build/fedora-openxc7'/f'xpcu-xvc-{stamp}').resolve()
    out.mkdir(parents=True,exist_ok=False)
    src = out/'source'; src.mkdir()
    manifest = dict(status='RUNNING',physical_hardware='NOT_RUN',donor=str(args.donor.resolve()),
                    started_utc=stamp,helper_sha256=digest(__file__))
    mp = out/'manifest.json'
    mp.write_text(json.dumps(manifest,indent=2)+'\n')
    try:
        revision = subprocess.check_output(['git','rev-parse','HEAD'],cwd=args.donor,text=True).strip()
        names = subprocess.check_output(['git','ls-files','-z'],cwd=args.donor).decode().split('\0')
        hashes = {}
        for name in filter(None,names):
            original = args.donor/name
            if original.is_file():
                target = src/name; target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(original,target); hashes[name] = digest(target)
        (out/'donor-local-changes.patch').write_bytes(subprocess.check_output(['git','diff','HEAD'],cwd=args.donor))
        manifest.update(revision=revision,donor_source_sha256=hashes)
        if args.usb_altsetting_patch:
            patch = out/'fx2-altsetting.patch'
            shutil.copy2(args.usb_altsetting_patch,patch)
            run(['patch','--batch','-p1','-d',str(src),'-i',str(patch)],out,'usb-patch')
            manifest['usb_altsetting_patch'] = dict(source=str(args.usb_altsetting_patch.resolve()),
                                                    sha256=digest(patch))
        (out/'xpcu-xvc.patch').write_text(extend(src))
        manifest['extension_sha256'] = digest(out/'xpcu-xvc.patch')
        mp.write_text(json.dumps(manifest,indent=2)+'\n')
        run(['cmake','-S',str(src),'-B',str(out/'binary'),'-DCMAKE_BUILD_TYPE=Release',
             '-DPKG_CONFIG_EXECUTABLE='+args.pkg_config,
             '-DENABLE_CABLE_ALL=OFF','-DENABLE_VENDORS_ALL=OFF',
             '-DENABLE_FTDI_BASED_CABLE=ON','-DENABLE_XILINX_PLATFORM_CABLE_USB=ON',
             '-DENABLE_XILINX_VIRTUAL_CABLE_SERVER=ON','-DENABLE_XILINX_SUPPORT=ON',
             '-DENABLE_UDEV=OFF'],out,'configure')
        run(['cmake','--build',str(out/'binary'),'--parallel',str(args.jobs)],out,'build')
        usb_cflags = shlex.split(subprocess.check_output(
            [args.pkg_config, '--cflags', 'libusb-1.0'], text=True))
        # The local Fedora donor adds an optional verbose constructor argument;
        # a Mac donor may retain upstream's original FX2 constructor instead.
        fx2_flags = (['-DXPCU_FX2_HAS_VERBOSE'] if 'int8_t verbose' in
                     (src/'src/fx2_ll.hpp').read_text() else [])
        run([args.cxx,'-std=c++17','-Wall','-Wextra','-Werror','-O0','-g',
             '-DISE_DIR=""','-DVIVADO_DIR=""',*usb_cflags,*fx2_flags,'-I'+str(src/'src'),
             str(ROOT/'tests/tb_xpcu_xvc.cpp'),str(src/'src/xilinxPlatformCableUSB.cpp'),
             str(src/'src/display.cpp'),'-o',str(out/'xpcu-protocol-test')],out,'protocol-compile')
        run([str(out/'xpcu-protocol-test')],out,'protocol-test')
        if args.usb_altsetting_patch:
            usb_libs = shlex.split(subprocess.check_output(
                [args.pkg_config, '--libs', 'libusb-1.0'], text=True))
            run([args.cxx,'-std=c++17','-Wall','-Wextra','-Werror','-O0','-g',
                 *usb_cflags,'-I'+str(src/'src'),
                 str(ROOT/'tests/tb_fx2_altsetting.cpp'),str(src/'src/fx2_ll.cpp'),
                 str(src/'src/ihexParser.cpp'),str(src/'src/configBitstreamParser.cpp'),
                 str(src/'src/progressBar.cpp'),str(src/'src/display.cpp'),
                 *usb_libs,'-o',str(out/'fx2-altsetting-test')],out,'usb-test-compile')
            run([str(out/'fx2-altsetting-test')],out,'usb-test')
            manifest['usb_altsetting_test_sha256'] = digest(ROOT/'tests/tb_fx2_altsetting.cpp')
        binary = out/'binary/openFPGALoader'
        run([str(binary),'--help'],out,'help')
        if '--xvc' not in (out/'help.log').read_text():
            raise RuntimeError('Built loader lacks the XVC server option')
        manifest.update(status='SERVER_COMPILED_PROTOCOL_PASS_PHYSICAL_NOT_RUN',
                        binary=str(binary),binary_sha256=digest(binary),
                        protocol_test_sha256=digest(ROOT/'tests/tb_xpcu_xvc.cpp'))
        ready = ROOT/'build/fedora-openxc7/xvc-ready.json'
        if not args.no_select:
            ready.write_text(json.dumps(dict(manifest=str(mp),binary=str(binary),
                                            binary_sha256=digest(binary)),indent=2)+'\n')
        manifest['selected'] = not args.no_select
    except Exception as e:
        manifest.update(status='FAIL',error=str(e)); print(str(e),file=sys.stderr)
        return 1
    finally:
        manifest['finished_utc'] = datetime.now(timezone.utc).isoformat()
        mp.write_text(json.dumps(manifest,indent=2)+'\n');print(mp)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
