#!/usr/bin/env python3
"""Isolated full PCIe build using the previously exercised CH1 snapshot."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import shlex
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from fedora_prepare_litedram import qualify, profile, FILES
from workspace_paths import vivado_bin

OUT = ROOT / 'build/fedora-vivado/ch0-reset-pcie-20261016'
BASELINE = ROOT / 'build/fedora-vivado/pcie-ch1-recovery-overlap-20261014T085912Z'
GENERATOR = ROOT / 'build/fedora-vivado/ch1-recovery-portable-20261014T081626Z/generator'
OLD_CORE = ROOT / 'build/fedora-vivado/ch1-core-writable-20261014T082631Z/core'
PYTHON = ROOT / 'build/fedora-openxc7/litedram-environment/venv/bin/python'
PATCHED = ROOT / 'build/handoffs/ch0-ddr-diagnostics-20261016T060847Z/candidate-upstream-reset/wl7ddrphy.py'
IMAGE = '7a9b5cf5977e9e09126101c2c2c9b642b3517c3d7894668c36b1d7c550a573b7'

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def now():
    return datetime.now(timezone.utc).isoformat()

def main():
    resume = '--resume-generated' in sys.argv
    OUT.mkdir(parents=True, exist_ok=resume)
    record = dict(status='PREPARING', started_utc=now(), hardware_accessed=False,
                  flash_written=False, physical_test_run=False, repair_verified=False,
                  full_compute=dict(MCOLS=4, ACT_ROWS=4, LANES=8, VPU_CL=2,
                                    MXU_IMPL=2, CORE_KHZ=100000, DDR_MTS=800),
                  logical_capacity_bytes=1 << 31, physical_user_channels=[1],
                  build_id='c0160001', baseline_build=str(BASELINE),
                  change='One additional sys-clock serializer-reset register per channel',
                  upstream_commit='f2d1023ddded0a4d70b8810a715e173ea989efd7',
                  driver_sha256=sha(__file__))
    if resume:
        previous = json.loads((OUT / 'manifest.json').read_text())
        assert previous.get('generate_exit') == 0
        record.update(previous)
        record.pop('error', None)
        record.pop('finished_utc', None)
        record.update(status='RESUMING_GENERATED_CORE', driver_sha256=sha(__file__),
                      prior_guard_failure=str(OUT / 'initial-failed-guard-manifest.json'))
    def save():
        temp = OUT / 'manifest.json.tmp'
        temp.write_text(json.dumps(record, indent=2) + '\n')
        temp.replace(OUT / 'manifest.json')
    def run(stage, command, *, cwd=OUT, env=None):
        record.update(status=stage.upper() + '_RUNNING', stage_started_utc=now())
        (OUT / (stage + '.command.json')).write_text(json.dumps(command, indent=2) + '\n')
        with (OUT / (stage + '.log')).open('w') as log:
            child = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=subprocess.STDOUT)
            record['child_pid'] = child.pid
            save()
            print(stage, 'PID', child.pid, flush=True)
            code = child.wait()
        record.pop('child_pid', None)
        record[stage + '_exit'] = code
        (OUT / (stage + '.exit')).write_text(str(code) + '\n')
        save()
        if code:
            raise RuntimeError(stage + ' failed; see ' + str(OUT / (stage + '.log')))
    try:
        save()
        if not resume:
            old = json.loads((BASELINE / 'manifest.json').read_text())
            for item in old['sources']:
                assert sha(item['path']) == item['sha256'], item['path']
            original = json.loads((GENERATOR.parent / 'manifest.json').read_text())
            for item in original['generator_sources']:
                assert sha(item['path']) == item['sha256'], item['path']
            src = OUT / 'generator'
            shutil.copytree(GENERATOR, src, ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
            assert sha(src / 'wl7ddrphy.py') == sha(ROOT / 'tools/litedram/wl7ddrphy.py')
            shutil.copy2(PATCHED, src / 'wl7ddrphy.py')
            record['patched_phy_sha256'] = sha(src / 'wl7ddrphy.py')
            record['generator_sources'] = [dict(path=str(p), sha256=sha(p))
                                           for p in sorted(src.rglob('*')) if p.is_file()]
            wrappers = OUT / 'compiler'
            wrappers.mkdir()
            runtime = ROOT / 'build/fedora-openxc7/litedram-environment/rv32-runtime'
            for tool in ['gcc', 'objcopy', 'objdump']:
                command = ['/usr/bin/podman', 'run', '--rm', '--network=none', '--userns=keep-id',
                           '--security-opt', 'label=disable', '--read-only', '--tmpfs', '/tmp:rw',
                           '-v', str(ROOT) + ':' + str(ROOT) + ':ro',
                           '-v', str(OUT) + ':' + str(OUT) + ':rw', '--workdir']
                shell = shlex.join(command) + ' "$PWD" ' + shlex.join(
                    ['--entrypoint', '/opt/et/bin/riscv64-unknown-elf-' + tool, IMAGE])
                if tool == 'gcc':
                    shell += ' ' + shlex.quote('-L' + str(runtime))
                path = wrappers / ('riscv64-elf-' + tool)
                path.write_text('#!/bin/sh\nexec ' + shell + ' "$@"\n')
                path.chmod(0o755)
            env = dict(os.environ, RV_CC=str(wrappers / 'riscv64-elf-gcc'), PYTHONHASHSEED='0')
            core = OUT / 'core'
            run('generate', [str(PYTHON), str(src / 'gen_core.py'), '--sys-mhz', '100',
                             '--phy', 'wl', '--selfcal', '--fw-id', 'c1010800', '--out', str(core)],
                cwd=src, env=env)
        else:
            src = OUT / 'generator'
            core = OUT / 'core'
        qualify(core)
        p = core / 'openxc7-profile.json'
        cfg = json.loads(p.read_text())
        previous = json.loads((OLD_CORE / p.name).read_text())
        for key in ['physical_user_channels', 'virtual_channel_bytes', 'usable_logical_bytes',
                    'user_address_mapping', 'calibration_mask', 'note']:
            cfg[key] = previous[key]
        p.write_text(json.dumps(cfg, indent=2) + '\n')
        profile(core)
        unchanged = ['sdram_init.py', 'otpu_litedram_mem.init',
                     'selfcal_fw/selfcal.bin', 'selfcal_fw/selfcal_cfg.h']
        for name in unchanged:
            assert sha(core / name) == sha(OLD_CORE / name), name
        def csr_rows(path):
            return [line for line in path.read_text().splitlines()
                    if line.strip() and not line.startswith('#')]
        assert csr_rows(core / 'csr.csv') == csr_rows(OLD_CORE / 'csr.csv')
        record['csr_registers_and_constants_unchanged'] = True
        record['unchanged_runtime_data_and_firmware'] = unchanged
        record['core'] = str(core)
        record['core_profile_sha256'] = sha(p)
        # ECC logic and the actual four-port checker retain the previously verified bytes.
        gate = ROOT / 'build/fedora-vivado/ch1-recovery-prepare-20261014T075931Z'
        assert (gate / 'four-port-ecc.exit').read_text().strip() == '0'
        assert (gate / 'four-port-ecc.log').read_text().splitlines()[-1] == 'PASS'
        for name in ['ecc_ports.py', 'ecc_ports_check.py']:
            assert sha(src / name) == sha(gate / 'generator' / name), name
        record['four_port_ecc_gate_reused_by_exact_source_hash'] = str(gate)
        source = OUT / 'source'
        shutil.copytree(BASELINE / 'source', source)
        ld = source / 'boards/ypcb-00338/litedram'
        for name in list(FILES.values()) + ['openxc7-profile.json']:
            shutil.copy2(core / name, ld / name)
        shutil.copy2(BASELINE / 'pre_bit_gate.py', OUT / 'pre_bit_gate.py')
        shutil.copytree(BASELINE / 'ip-cache', OUT / 'ip-cache')
        changed = []
        for path in sorted(source.rglob('*')):
            if path.is_file() and sha(path) != sha(BASELINE / 'source' / path.relative_to(source)):
                changed.append(str(path.relative_to(source)))
        assert set(changed) <= {'boards/ypcb-00338/litedram/' + n
                                for n in list(FILES.values()) + ['openxc7-profile.json']}, changed
        record['source_files_changed_from_baseline'] = changed
        record['source_hashes'] = {str(p.relative_to(source)): sha(p)
                                   for p in sorted(source.rglob('*')) if p.is_file()}
        executable = vivado_bin() / 'vivado'
        settings = executable.parent.parent / 'settings64.sh'
        raw = subprocess.check_output(['/bin/bash', '-c', 'source "$1"\nenv -0',
                                       'vivado-env', str(settings)])
        env = dict(x.decode().split('=', 1) for x in raw.split(b'\0') if x)
        env.update(OTPU_FAST='0', PCIE_GEN='2', OTPU_IP_CACHE=str(OUT / 'ip-cache'),
                   OTPU_PRE_BIT_GATE=str(OUT / 'pre_bit_gate.py'))
        project = OUT / 'project'
        tcl = source / 'boards/ypcb-00338/vivado'
        run('create', [str(executable), '-mode', 'batch', '-nojournal', '-nolog',
                       '-source', str(tcl / 'create_project.tcl'), '-tclargs', '800',
                       str(project), '4', '100', 'c0160001', '2', '8', '4', '1', 'systolic'],
            cwd=source, env=env)
        run('build', [str(executable), '-mode', 'batch', '-nojournal', '-nolog',
                      '-source', str(tcl / 'build.tcl'), '-tclargs', str(project), '8', 'full', ''],
            cwd=source, env=env)
        record['outputs'] = {name:dict(path=str(project / name), sha256=sha(project / name),
                                      bytes=(project / name).stat().st_size)
                             for name in ['otpu.bit', 'otpu.mcs', 'final-routed.dcp', 'pre-bit-gates.json']}
        record['status'] = 'CANDIDATE_BUILD_PASS_INDEPENDENT_IMAGE_REVIEW_AND_PHYSICAL_TEST_PENDING'
        return 0
    except BaseException as error:
        record.update(status='FAIL', error=repr(error))
        print(record['error'], flush=True)
        return 1
    finally:
        record['finished_utc'] = now()
        save()

if __name__ == '__main__':
    raise SystemExit(main())
