#!/usr/bin/env python3
"""Build an isolated checked-backend copy with double static WL exponentials.

Only placer_static.cc is rebuilt. All other object/archive inputs are copied
and hashed, headers remain identical, and the existing hardware corrections
are retained. Qualification of the new binary is a separate required step.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess

from fedora_openxc7 import describe, digest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--previous', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    previous, out = args.previous.resolve(), args.out.resolve()
    if out.exists():
        parser.error('Choose a new output directory')
    before = json.loads(previous.read_text())
    if before['status'] != 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED':
        parser.error('Expected the complete merged backend build receipt')
    if describe(before['binary']['path']) != before['binary']:
        parser.error('Previous executable differs from its receipt')
    out.mkdir(parents=True)
    info = dict(before, status='RUNNING', stage='copy-inputs',
                started_utc=datetime.now(timezone.utc).isoformat(),
                previous=describe(previous), previous_binary=before['binary'],
                helper=describe(__file__), physical_hardware='NOT_RUN',
                scope='FULL_BACKEND_STATIC_DOUBLE_EXP_CORRECTION')

    def save():
        temporary = out / 'manifest.json.tmp'
        temporary.write_text(json.dumps(info, indent=2) + '\n')
        temporary.replace(out / 'manifest.json')

    def run(stage, command):
        info.update(stage=stage)
        (out / (stage + '.command.json')).write_text(json.dumps(command, indent=2) + '\n')
        print('START ' + stage, flush=True)
        with (out / (stage + '.log')).open('w') as log:
            child = subprocess.Popen(command, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            info['child_pid'] = child.pid
            save()
            code = child.wait()
        info.pop('child_pid', None)
        (out / (stage + '.exit')).write_text(str(code) + '\n')
        info[stage + '_exit'] = code
        save()
        if code:
            raise RuntimeError(stage + ' exited ' + str(code))

    try:
        save()
        source = out / 'source'
        original = Path(before['source'])
        inventory = json.loads(Path(before['source_inventory']['path']).read_text())
        shutil.copytree(original, source)
        for relative, expected in inventory.items():
            if digest(source / relative) != expected:
                raise RuntimeError('Copied source differs: ' + relative)
        target = source / 'common/place/placer_static.cc'
        text = target.read_text()
        for variable in ('emin', 'emax'):
            old = 'std::exp(' + variable + ')'
            if text.count(old) != 1:
                raise RuntimeError('Expected one exponential for ' + variable)
            text = text.replace(old, 'std::exp(static_cast<double>(' + variable + '))')
        target.write_text(text)
        updated = {str(p.relative_to(source)): digest(p)
                   for p in source.rglob('*') if p.is_file()}
        if set(updated) != set(inventory):
            raise RuntimeError('Source inventory membership changed')
        changed = [name for name in inventory if inventory[name] != updated[name]]
        if changed != ['common/place/placer_static.cc']:
            raise RuntimeError('Unexpected source changes: ' + repr(changed))
        (out / 'source.input.json').write_text(json.dumps(updated, indent=2) + '\n')
        objects = out / 'input-objects'
        objects.mkdir()
        linked, reused = [], []
        replacements = 0
        object_out = objects / 'placer_static.cc.o'
        for index, value in enumerate(before['link_argv']):
            if value.endswith('/common/place/placer_static.cc.o'):
                linked.append(str(object_out))
                replacements += 1
            elif value.endswith(('.o', '.a')) and Path(value).is_file():
                destination = objects / (str(index).zfill(3) + '-' + Path(value).name)
                expected = digest(value)
                shutil.copy2(value, destination)
                if digest(destination) != expected:
                    raise RuntimeError('Copied object differs: ' + value)
                reused.append(dict(original=describe(value), copied=describe(destination)))
                linked.append(str(destination))
            else:
                linked.append(value)
        if replacements != 1:
            raise RuntimeError('Expected one original static placer object')
        linked[linked.index('-o') + 1] = str(out / 'nextpnr-himbaechel')
        template = before['compile_plan'][0]['argv']
        compile_command = [value.replace(str(original), str(source)) for value in template]
        for flag, value in (('-MF', str(object_out) + '.d'), ('-o', str(object_out)),
                            ('-c', str(target))):
            compile_command[compile_command.index(flag) + 1] = value
        info.update(source=str(source), source_inventory=describe(out / 'source.input.json'),
                    modifications=[describe(target)],
                    retained_corrections=[*before['retained_corrections'], 'STATIC_DOUBLE_EXP'],
                    compile_plan=[dict(source=str(target), output=str(object_out), argv=compile_command)],
                    link_argv=linked, reused_inputs=reused,
                    header_declarations='UNCHANGED_HASH_VERIFIED',
                    source_delta=changed, qualification='NOT_RUN')
        save()
        run('compile-static', compile_command)
        info['rebuilt_translation_units'] = [describe(object_out)]
        run('link', linked)
        info.update(status='BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED',
                    stage='compiled', binary=describe(out / 'nextpnr-himbaechel'))
        save()
        print(info['status'], flush=True)
        return 0
    except Exception as error:
        info.update(status='FAIL', error=repr(error))
        save()
        print(repr(error), flush=True)
        return 1
    finally:
        info['finished_utc'] = datetime.now(timezone.utc).isoformat()
        save()


if __name__ == '__main__':
    raise SystemExit(main())
