#!/usr/bin/env python3
"""Try full static placement while preserving the running heap implementation.

Reuse the existing reference controller, full-design preparation and guarded
assembly. A separate worker adds only --placer static to the actual native
command. Its source is pinned by the controller and its actual commands and
provenance are recorded. No existing pinned helper or FPGA source is edited.
"""
from pathlib import Path
import json
import sys

HERE = Path(__file__).resolve()


def route_worker(arguments):
    import fedora_openxc7 as implementation

    original_run = implementation.run
    route_out = Path(arguments[arguments.index('--out') + 1]).resolve()

    def run(command, out, label, env=None):
        if label == 'route':
            if '--placer' in command:
                raise RuntimeError('Unexpected existing placer override')
            command = [*command, '--placer', 'static']
            (out / 'placement-driver.json').write_text(json.dumps(dict(
                scope='FULL_DESIGN_STATIC_PLACEMENT_AND_ROUTING',
                algorithm='static', driver=implementation.describe(HERE),
                preparation_helper=implementation.describe(implementation.__file__),
                native_command=command, hardware_accessed=False,
            ), indent=2) + '\n')
        return original_run(command, out, label, env)

    implementation.run = run
    sys.argv = [str(implementation.__file__), *arguments]
    result = implementation.main()
    manifest = route_out / 'manifest.json'
    if manifest.is_file():
        data = json.loads(manifest.read_text())
        data.update(placement_algorithm='static',
                    placement_driver=implementation.describe(HERE))
        temporary = route_out / 'manifest.static.tmp'
        temporary.write_text(json.dumps(data, indent=2) + '\n')
        temporary.replace(manifest)
    return result


def controller():
    import fedora_resume_openxc7_reference as reference

    original_select = reference.select_jtag_backend
    original_popen = reference.subprocess.Popen

    def select(selection):
        backend, gates, inventory = original_select(selection)
        inventory[str(HERE)] = reference.digest(HERE)
        return backend, gates, inventory

    def popen(command, *arguments, **kwargs):
        if (isinstance(command, (list, tuple)) and len(command) > 2
                and command[1] == str(reference.ROOT / 'tools/fedora_openxc7.py')
                and command[2] == 'jtag-route'):
            route_out = Path(command[command.index('--out') + 1]).resolve()
            command = [command[0], str(HERE), '__route_worker', *command[2:]]
            # The reference controller recorded the command immediately before
            # this call. Replace that record with the command actually launched.
            (route_out.parent / 'full-route.command.json').write_text(
                json.dumps(command, indent=2) + '\n')
            (route_out.parent / 'placement-attempt.json').write_text(json.dumps(
                dict(algorithm='static', driver=reference.describe(HERE),
                     actual_worker_command=command,
                     full_design=True, hardware_accessed=False), indent=2) + '\n')
        return original_popen(command, *arguments, **kwargs)

    reference.select_jtag_backend = select
    reference.subprocess.Popen = popen
    return reference.main()


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == '__route_worker':
        raise SystemExit(route_worker(sys.argv[2:]))
    raise SystemExit(controller())
