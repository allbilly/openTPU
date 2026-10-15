#!/usr/bin/env python3
"""Generate an isolated full dual-channel DDR3-800 core and calibration firmware.

Requires core.json's pinned LiteX environment and an RV32I-capable compiler.
The committed DDR3-1066 core and the compute-array dimensions are preserved.
"""
from __future__ import annotations

import argparse
import ast
import csv
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'boards/ypcb-00338/litedram'
ENV = ROOT / 'build/fedora-openxc7/litedram-environment'
PROFILE_STATUS = 'GENERATED_PROFILE_PASS_IMPLEMENTATION_NOT_RUN'
FILES = {'verilog': 'otpu_litedram.v', 'xdc': 'otpu_litedram.xdc',
         'rom': 'otpu_litedram_mem.init', 'csr': 'csr.csv', 'init': 'sdram_init.py'}
CPU_MARKER = '// VexRiscv_Min.v (modules renamed otpu_selfcal_*)'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def phy_config(path):
    tree = ast.parse(Path(path).read_text())
    assignments = [n for n in tree.body if isinstance(n, ast.Assign)
                   and any(isinstance(t, ast.Name) and t.id == 'phy' for t in n.targets)]
    if len(assignments) != 1:
        raise ValueError('Expected exactly one generated PHY configuration')
    return ast.literal_eval(assignments[0].value)


def csr_registers(path):
    with Path(path).open() as f:
        return {r[1]: (int(r[2], 16), int(r[3]), r[4])
                for r in csv.reader(f) if r and r[0] == 'csr_register'}


def module_ports(text, name):
    match = re.search(r'\bmodule\s+'+re.escape(name)+r'\s*\((.*?)\);', text, re.S)
    if match is None:
        raise ValueError('Missing real otpu_litedram module')
    result = {}
    for declaration in match[1].split(','):
        p = re.fullmatch(r'\s*(input|output|inout)\s+(?:(?:wire|reg)\s*)?'
                         r'(?:\[\s*(\d+)\s*:\s*(\d+)\s*\])?\s*'
                         r'([A-Za-z_][A-Za-z_0-9]*)\s*', declaration)
        if p is None:
            raise ValueError('Unexpected generated port declaration syntax')
        direction, high, low, name = p.groups()
        if name in result:
            raise ValueError('Duplicate generated module port')
        result[name] = (direction, abs(int(high)-int(low))+1 if high else 1)
    return result


def ports(path):
    return module_ports(Path(path).read_text(), 'otpu_litedram')


def retain_reference_cpu(directory):
    """Reuse the real committed CPU when packaged CPU data has drifted.

    LiteX's pinned Python commit does not pin pythondata-cpu-vexriscv. Its
    published wheel currently embeds an older CPU. Retain the generated DDR
    logic/firmware and the original generator output, and append the exact
    reference CPU after verifying the instance's complete port ABI.
    """
    path = directory/FILES['verilog']
    generated, reference = path.read_text(), (BASE/FILES['verilog']).read_text()
    if generated.count(CPU_MARKER) != 1 or reference.count(CPU_MARKER) != 1:
        raise ValueError('Expected a single complete embedded calibration CPU')
    generated_body, generated_cpu = generated.split(CPU_MARKER, 1)
    reference_cpu = reference.split(CPU_MARKER, 1)[1]
    if module_ports(generated_cpu, 'otpu_selfcal_VexRiscv') != module_ports(reference_cpu, 'otpu_selfcal_VexRiscv'):
        raise ValueError('Packaged CPU and reference CPU have different port ABIs')
    original = directory/'otpu_litedram.generator.v'
    if generated_cpu != reference_cpu:
        if original.exists():
            raise ValueError('A prior CPU-preservation original already exists but the selected CPU differs')
        original.write_text(generated)
        path.write_text(generated_body+CPU_MARKER+reference_cpu)
    return dict(status='REFERENCE_CPU_RETAINED', reference_core=str(BASE/FILES['verilog']),
                reference_core_sha256=sha(BASE/FILES['verilog']),
                embedded_cpu_sha256=hashlib.sha256(reference_cpu.encode()).hexdigest(),
                original_generator_output_sha256=sha(original) if original.exists() else sha(path),
                port_abi='MATCH', hardware='NOT_RUN')


def profile(directory=None):
    """Resolve a checked core and its matching host configuration."""
    if directory is None:
        info = json.loads((BASE / 'core.json').read_text())
        for name, expected in info['sha256'].items():
            if sha(BASE / name) != expected:
                raise ValueError('Committed LiteDRAM core differs from core.json: ' + name)
        return dict(verilog=BASE/FILES['verilog'], xdc=BASE/FILES['xdc'],
                    rom=BASE/FILES['rom'], data=ROOT/'opentpu/host/litedram',
                    parameters=dict(CORE_KHZ=133333, DDR_MTS=1066),
                    manifest=None)
    directory = Path(directory).resolve()
    mp = directory / 'openxc7-profile.json'
    info = json.loads(mp.read_text())
    if info.get('status') != PROFILE_STATUS or info.get('part') != 'xc7k480tffg1156-2':
        raise ValueError('Requires a checked YPCB generated core profile')
    if info.get('parameters') != dict(CORE_KHZ=100000, DDR_MTS=800):
        raise ValueError('Unsupported alternate DDR/core rate')
    for key, name in FILES.items():
        if sha(directory/name) != info['files'][key]['sha256']:
            raise ValueError('Generated core/configuration changed: ' + name)
    reference = (BASE/FILES['verilog']).read_text().split(CPU_MARKER, 1)[1]
    selected = (directory/FILES['verilog']).read_text().split(CPU_MARKER, 1)[1]
    if selected != reference:
        raise ValueError('Generated profile changed the reference calibration CPU')
    phy = phy_config(directory/FILES['init'])
    if (phy['sys_hz'], phy['cl'], phy['cwl'], phy['channels'], phy['databits'], phy['phy']) != (
            100e6, 6, 5, [0, 1], 72, 'wl'):
        raise ValueError('Generated PHY does not match DDR3-800 dual-channel profile')
    return dict(verilog=directory/FILES['verilog'], xdc=directory/FILES['xdc'],
                rom=directory/FILES['rom'], data=directory,
                parameters=info['parameters'], manifest=mp)


def qualify(directory):
    """Check the generated interface, CSR ABI and real firmware before selecting it."""
    directory = Path(directory)
    cpu = retain_reference_cpu(directory)
    phy = phy_config(directory/FILES['init'])
    if (phy['sys_hz'], phy['cl'], phy['cwl'], phy['channels'], phy['databits'], phy['phy']) != (
            100e6, 6, 5, [0, 1], 72, 'wl'):
        raise ValueError('Generated core does not have the full DDR3-800 PHY configuration')
    if ports(directory/FILES['verilog']) != ports(BASE/FILES['verilog']):
        raise ValueError('Generated core changes the board interface')
    if csr_registers(directory/FILES['csr']) != csr_registers(ROOT/'opentpu/host/litedram/csr.csv'):
        raise ValueError('Generated core changes the host CSR register map')
    if not (directory/'selfcal_fw/selfcal.elf').is_file():
        raise ValueError('The actual self-calibration firmware was not linked')
    if not 0 < (directory/'selfcal_fw/selfcal.bin').stat().st_size <= 16384:
        raise ValueError('Calibration firmware does not fit its real CPU memory')
    # Retain ELF identity as well as the disassembly: the CPU executes RV32I.
    elf = (directory/'selfcal_fw/selfcal.elf').read_bytes()
    if elf[:6] != b'\x7fELF\x01\x01' or int.from_bytes(elf[18:20], 'little') != 243:
        raise ValueError('Calibration firmware is not a little-endian ELF32 RISC-V image')
    # LiteX places the identifier ROM in gateware/, while the board synthesis
    # reads it alongside the single-file Verilog.
    rom = directory/'gateware'/FILES['rom']
    (directory/FILES['rom']).write_bytes(rom.read_bytes())
    info = dict(status=PROFILE_STATUS, part='xc7k480tffg1156-2',
                parameters=dict(CORE_KHZ=100000, DDR_MTS=800),
                physical_hardware='NOT_RUN', timing='NOT_QUALIFIED', calibration_cpu=cpu,
                files={k: dict(name=n, sha256=sha(directory/n), bytes=(directory/n).stat().st_size)
                       for k, n in FILES.items()},
                note='Both 72-bit ECC channels, their BISTs, four native user ports and the real VexRiscv calibration CPU are retained. Full compute dimensions are selected separately by the board helper.')
    (directory/'openxc7-profile.json').write_text(json.dumps(info, indent=2)+'\n')
    return profile(directory)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--python', type=Path, default=ENV/'venv/bin/python')
    ap.add_argument('--rv-cc', type=Path, default=ENV/'toolchain/riscv64-elf-gcc')
    ap.add_argument('--out', type=Path)
    ap.add_argument('--qualify-existing', type=Path, help='recheck a completed generated core without repeating generation')
    args = ap.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    out = (args.out or ROOT/'build/fedora-openxc7'/f'ddr800-prepare-{stamp}').resolve()
    out.mkdir(parents=True, exist_ok=False)
    inputs = sorted((ROOT/'tools/litedram').glob('*.py')) + sorted((ROOT/'tools/litedram/selfcal_fw').glob('*'))
    inputs += [ROOT/'opentpu/host/ddrcal.py', BASE/'core.json', Path(__file__)]
    info = dict(status='RUNNING', part='xc7k480tffg1156-2', parameters=dict(CORE_KHZ=100000, DDR_MTS=800),
                started_utc=stamp, source={str(p): sha(p) for p in inputs if p.is_file()},
                physical_hardware='NOT_RUN')
    mp = out/'manifest.json'
    mp.write_text(json.dumps(info, indent=2)+'\n')
    try:
        if args.qualify_existing:
            core = args.qualify_existing.resolve()
            original = core.parent/'manifest.json'
            if (core.parent/'generate.exit').read_text().strip() != '0':
                raise ValueError('Existing core generation did not complete successfully')
            old = json.loads(original.read_text())
            for name, expected_sha in old['source'].items():
                # A validator correction does not change gen_core.py's output.
                if Path(name).resolve() == Path(__file__).resolve():
                    continue
                if sha(name) != expected_sha:
                    raise ValueError('Generator input changed since generation: '+name)
            info['generation_manifest'] = dict(path=str(original), sha256=sha(original))
            qualify(core)
            info['status'] = PROFILE_STATUS
            info['profile'] = str(core/'openxc7-profile.json')
            return 0
        for p in (args.python, args.rv_cc):
            if not p.is_file():
                raise ValueError('Missing build dependency: '+str(p))
        probe = "import importlib.metadata,json; print(json.dumps({n:importlib.metadata.distribution(n).read_text('direct_url.json') for n in ('migen','litex','litedram')}))"
        packages = json.loads(subprocess.check_output([str(args.python), '-c', probe], text=True))
        expected = json.loads((BASE/'core.json').read_text())['packages']
        for name, requirement in expected.items():
            if json.loads(packages[name] or '{}').get('vcs_info', {}).get('commit_id') != requirement['commit']:
                raise ValueError('Wrong pinned generator dependency: '+name)
        info['packages'] = packages
        info['compiler_wrapper_sha256'] = sha(args.rv_cc)
        cmd = [str(args.python), str(ROOT/'tools/litedram/gen_core.py'), '--sys-mhz', '100',
               '--phy', 'wl', '--selfcal', '--fw-id', '4461c052', '--out', str(out/'core')]
        (out/'generate.command.json').write_text(json.dumps(cmd, indent=2)+'\n')
        env = dict(os.environ, RV_CC=str(args.rv_cc.resolve()), PYTHONHASHSEED='0')
        (out/'generate.environment.json').write_text(json.dumps({k:env[k] for k in ('RV_CC','PYTHONHASHSEED')}, indent=2)+'\n')
        mp.write_text(json.dumps(info, indent=2)+'\n')
        with (out/'generate.log').open('w') as f:
            code = subprocess.run(cmd, cwd=out, env=env, stdout=f, stderr=subprocess.STDOUT).returncode
        (out/'generate.exit').write_text(str(code)+'\n')
        if code:
            raise RuntimeError(f'Generation exited {code}; see {out}/generate.log')
        qualify(out/'core')
        info['status'] = PROFILE_STATUS
        info['profile'] = str(out/'core/openxc7-profile.json')
    except Exception as e:
        info.update(status='FAIL', error=str(e))
        print(str(e), file=sys.stderr)
        return 1
    finally:
        info['finished_utc'] = datetime.now(timezone.utc).isoformat()
        mp.write_text(json.dumps(info, indent=2)+'\n')
        print(mp)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
