"""Tool discovery must work after cloning to a different directory and home."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
import pytest


def relocated(tmp_path, monkeypatch):
    checkout = tmp_path / 'another workspace' / 'accelerator'
    path = checkout / 'tools/workspace_paths.py'
    path.parent.mkdir(parents=True)
    shutil.copy2(Path(__file__).parents[1] / 'tools/workspace_paths.py', path)
    for name in ['OTPU_WORKSPACE_ROOT', 'YPCB_ROOT', 'OTPU_VIVADO_BIN', 'VIVADO_BIN',
                 'VIVADO_ROOT', 'XILINX_VIVADO', 'OTPU_YOSYS', 'OTPU_YOSYS_SHARE', 'OTPU_SLANG']:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv('HOME', str(tmp_path / 'different-home'))
    monkeypatch.setenv('PATH', str(tmp_path / 'empty-path'))
    spec = importlib.util.spec_from_file_location('relocated_workspace_paths', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return checkout, module


def test_checkout_and_sibling_defaults_follow_relocation(tmp_path, monkeypatch):
    checkout, module = relocated(tmp_path, monkeypatch)
    assert module.expand_paths('@REPO@/build') == str(checkout / 'build')
    assert module.expand_paths('@YPCB@/dlc10-init.sh') == str(checkout.parent / 'ypcb/dlc10-init.sh')


def test_external_paths_accept_explicit_configuration(tmp_path, monkeypatch):
    _, module = relocated(tmp_path, monkeypatch)
    tools = tmp_path / 'configured tool directory'
    monkeypatch.setenv('YPCB_ROOT', str(tools / 'board-tools'))
    monkeypatch.setenv('VIVADO_ROOT', str(tools / 'Vivado'))
    monkeypatch.setenv('OTPU_YOSYS', str(tools / 'yosys'))
    monkeypatch.setenv('OTPU_YOSYS_SHARE', str(tools / 'yosys-data'))
    monkeypatch.setenv('OTPU_SLANG', str(tools / 'slang.so'))
    assert module.expand_paths('@VIVADO_BIN@/vivado') == str(tools / 'Vivado/bin/vivado')
    assert module.expand_paths('@YOSYS@') == str(tools / 'yosys')
    assert module.expand_paths('@YOSYS_SHARE@/xilinx') == str(tools / 'yosys-data/xilinx')
    assert module.expand_paths('plugin -i @SLANG@') == 'plugin -i ' + str(tools / 'slang.so')
    assert module.expand_paths('@YPCB@') == str(tools / 'board-tools')


def test_vivado_discovery_from_path_and_directory_override(tmp_path, monkeypatch):
    _, module = relocated(tmp_path, monkeypatch)
    bindir = tmp_path / 'installed tools/bin'
    bindir.mkdir(parents=True)
    binary = bindir / 'vivado'
    binary.write_text('#!/bin/sh\nexit 0\n')
    binary.chmod(0o755)
    monkeypatch.setenv('PATH', str(bindir))
    assert module.vivado_bin() == bindir
    configured = tmp_path / 'preferred Vivado/bin'
    monkeypatch.setenv('OTPU_VIVADO_BIN', str(configured))
    assert module.vivado_bin() == configured


def test_artifact_receipts_accept_directory_aliases_and_reject_changed_bytes(tmp_path):
    import hashlib
    from tools.fedora_program_ch1_sram import artifact_matches
    current = tmp_path / 'new-checkout'
    current.mkdir()
    data = current / 'image.bit'
    data.write_bytes(b'qualified-image')
    alias = tmp_path / 'legacy-checkout'
    alias.symlink_to(current, target_is_directory=True)
    expected = dict(path=str(alias / data.name), bytes=data.stat().st_size,
                    sha256=hashlib.sha256(data.read_bytes()).hexdigest())
    assert artifact_matches(expected, data)
    data.write_bytes(b'corrupted-image')
    assert not artifact_matches(expected, data)


@pytest.mark.parametrize('command,option', [
    ('program-flash', '--skip-backup'),
    ('program-sram', '--qualification'),
    ('build-pcie', '--generation'),
    ('run-lfm2', '--soak-seconds'),
])
def test_portable_cli_forwards_help_from_another_directory(tmp_path, command, option):
    cli = Path(__file__).parents[1] / 'tools/ypcb.py'
    result = subprocess.run([sys.executable, str(cli), command, '--help'],
                            cwd=tmp_path, capture_output=True, text=True, timeout=20)
    assert result.returncode == 0, result.stderr
    assert option in result.stdout
    assert 'ypcb.py ' + command in result.stdout
