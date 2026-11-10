#!/usr/bin/env python3
"""Derive image preparations that retain the qualified X-Ray venv invocation."""
from __future__ import annotations
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

from fedora_openxc7 import describe, digest


def prepare(image, dsp, python_argv, out):
    original = json.loads(image.read_text())
    correction = json.loads(dsp.read_text())
    if (original['status'] != 'FULL_PLACED_REPLAY_SOURCE_AND_ASSEMBLY_INPUTS_PREPARED_WAITING_FOR_ROUTE'
            or correction['status'] != 'NATIVE_DIFFERENTIAL_FASM_REPRODUCTION_AND_FULL_717_DSP_CORRECTION_MAP_PASS_ROUTE_PENDING'
            or correction['image_preparation'] != describe(image)):
        raise ValueError('Exact completed source preparation and DSP map required')
    python_argv = python_argv.absolute()  # Preserve venv spelling; do not resolve it.
    if describe(python_argv) != original['assembly_tools']['python']:
        raise ValueError('Venv invocation must use the same pinned interpreter bytes')
    prefix = python_argv.parent.parent
    cfg = prefix / 'pyvenv.cfg'
    if not cfg.is_file():
        raise ValueError('An actual Python virtual environment is required')
    if describe(original['planned_inputs']['path']) != original['planned_inputs']:
        raise ValueError('Original source inventory changed')
    inventory = json.loads(Path(original['planned_inputs']['path']).read_text())
    with ThreadPoolExecutor(max_workers=8) as pool:
        if not all(pool.map(lambda x: digest(x[0]) == x[1], inventory.items())):
            raise ValueError('Original full-source/database/tool inventory changed')
    out.mkdir(parents=True, exist_ok=False)
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'parent_image_preparation': describe(image), 'parent_dsp_preparation': describe(dsp),
            'helper': describe(__file__), 'hardware_accessed': False, 'live_route_changed': False,
            'scope': 'EXACT_SOURCE_PREPARATION_RUNTIME_FIX_AND_DERIVED_DSP_MAP_NOT_COMPLETED_FULL_IMAGE'}

    def save(**kw):
        info.update(kw)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save()
        env = dict(os.environ, PYTHONPATH=original['assembly_tools']['xray'])
        code = ('import sys,json,fasm,yaml,intervaltree; from utils import fasm2frames; '
                'print(json.dumps({"executable":sys.executable,"prefix":sys.prefix,"base_prefix":sys.base_prefix,'
                '"modules":{m.__name__:m.__file__ for m in (fasm,yaml,intervaltree,fasm2frames)}}))')
        argv = [str(python_argv), '-c', code]
        (out / 'runtime.command.json').write_text(json.dumps(argv, indent=2) + '\n')
        result = subprocess.run(argv, env=env, capture_output=True, text=True)
        (out / 'runtime.stdout').write_text(result.stdout)
        (out / 'runtime.stderr').write_text(result.stderr)
        (out / 'runtime.exit').write_text(str(result.returncode) + '\n')
        if result.returncode:
            raise ValueError('Exact venv cannot import the assembly dependencies')
        runtime = json.loads(result.stdout)
        if Path(runtime['prefix']).absolute() != prefix or Path(runtime['executable']).absolute() != python_argv:
            raise ValueError('Native sys.prefix/executable do not preserve the selected venv')
        (out / 'runtime.json').write_text(json.dumps(runtime, indent=2) + '\n')
        site_packages = prefix / 'lib/python3.13/site-packages'
        runtime_inventory = {str(cfg): digest(cfg), str(python_argv): digest(python_argv)}
        for path in site_packages.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix != '.pyc':
                runtime_inventory[str(path)] = digest(path)
        for module, path in runtime['modules'].items():
            if not Path(path).is_file():
                raise ValueError('Imported module source is absent: ' + module)
            runtime_inventory[path] = digest(path)
        root = Path(__file__).parent
        variants = {}
        changes = {
            'openxc7_clock_image_assemble.py': ("tools['python']['path']", "tools['python_argv']"),
            'openxc7_isolated_image_followup.py': ("with_name('openxc7_clock_image_assemble.py')", "with_name('openxc7_clock_image_assemble_runtime.py')"),
            'openxc7_dsp_image_followup.py': ("tools['python']['path']", "tools['python_argv']"),
        }
        for filename, (before, after) in changes.items():
            source = root / filename
            target = root / filename.replace('.py', '_runtime.py')
            text = source.read_text()
            if text.count(before) != 1 or target.exists():
                raise ValueError('Unexpected runtime variant anchor or existing output')
            target.write_text(text.replace(before, after))
            variants[filename] = {'parent': describe(source), 'variant': describe(target),
                                  'single_replacement': [before, after]}
            inventory[str(target)] = digest(target)
        inventory.update(runtime_inventory)
        inventory[str(Path(__file__).resolve())] = digest(__file__)
        (out / 'planned-inputs.json').write_text(json.dumps(inventory, indent=2) + '\n')
        derived = json.loads(image.read_text())
        derived['assembly_tools']['python_argv'] = str(python_argv)
        derived['assembly_tools']['python_runtime'] = describe(out / 'runtime.json')
        derived['planned_inputs'] = describe(out / 'planned-inputs.json')
        derived['runtime_parent'] = describe(image)
        derived['runtime_helper'] = describe(__file__)
        derived['runtime_variants'] = variants
        derived_path = out / 'image-preparation.json'
        derived_path.write_text(json.dumps(derived, indent=2) + '\n')
        # All backend, RTL, placement, owner, profile and qualification fields
        # stay exact; only the assembly runtime and its inventory are extended.
        allowed = {'assembly_tools', 'planned_inputs', 'runtime_parent', 'runtime_helper', 'runtime_variants'}
        if {k: v for k, v in derived.items() if k not in allowed} != {k: v for k, v in original.items() if k not in allowed}:
            raise ValueError('A non-runtime preparation field changed')
        updated = json.loads(dsp.read_text())
        old_descriptor = describe(image)
        updated['image_preparation'] = describe(derived_path)
        updated['inputs'] = [describe(derived_path) if x == old_descriptor else x for x in updated['inputs']]
        updated['inputs'] += [describe(dsp), old_descriptor]
        updated['runtime_parent'] = describe(dsp)
        updated['runtime_helper'] = describe(__file__)
        dsp_path = out / 'dsp-preparation.json'
        dsp_path.write_text(json.dumps(updated, indent=2) + '\n')
        unchanged = {k: v for k, v in updated.items() if k not in {'image_preparation', 'inputs', 'runtime_parent', 'runtime_helper'}}
        baseline = {k: v for k, v in correction.items() if k not in {'image_preparation', 'inputs', 'runtime_parent', 'runtime_helper'}}
        if unchanged != baseline:
            raise ValueError('DSP maps/native/vendor qualification changed')
        save(status='SAME_PINNED_PYTHON_VENV_IMPORTS_AND_RUNTIME_ONLY_IMAGE_PREPARATION_PASS',
             native_runtime=runtime, runtime_inventory_files=len(runtime_inventory), variants=variants,
             non_runtime_image_fields_identical=True, dsp_maps_and_qualification_identical=True,
             outputs={p.name: describe(p) for p in (derived_path, dsp_path, out / 'runtime.json', out / 'planned-inputs.json')})
        print(info['status'], flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('image', 'dsp', 'python-argv', 'out'):
        parser.add_argument('--' + name, type=Path, required=True)
    args = parser.parse_args()
    prepare(args.image.resolve(), args.dsp.resolve(), args.python_argv, args.out.resolve())
