#!/usr/bin/env python3
"""Verify complete mapped RAM configuration against the linked Vivado design."""
from __future__ import annotations

try:
    from .workspace_paths import expand_paths
except ImportError:
    from workspace_paths import expand_paths

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil
import subprocess

from fedora_openxc7 import describe
from openxc7_mapped_edif import TOP, PROFILE


def quote(value):
    if any(c in value for c in '{}\r\n'):
        raise ValueError('Unsupported Tcl object name')
    return '{' + value + '}'


def expected_memory(path):
    top = json.loads(Path(path).read_text())['modules'][TOP]
    return {name: {'primitive': cell['type'], 'parameters': cell['parameters']}
            for name, cell in top['cells'].items()
            if cell['type'] in ('RAMB36E1', 'RAMB18E1', 'RAM32M', 'RAM64M')}


def binary_value(bits):
    value = mask = 0
    for bit in bits.lower():
        value <<= 1
        mask <<= 1
        if bit in '01':
            value |= int(bit)
            mask |= 1
        elif bit not in 'xz':
            raise ValueError('Not a four-state binary literal')
    return value, mask


def actual_number(raw, wanted_width):
    raw = raw.strip().lower()
    match = re.fullmatch(r"(\d+)'([bhd])([0-9a-fxz_]+)", raw)
    if not match:
        return int(raw, 10), (1 << wanted_width) - 1
    width, base, digits = int(match[1]), match[2], match[3].replace('_', '')
    if base == 'd':
        return int(digits, 10), (1 << wanted_width) - 1
    if base == 'h':
        bits = ''.join(char * 4 if char in 'xz' else format(int(char, 16), '04b') for char in digits)
    else:
        bits = digits
    fill = bits[0] if bits[0] in 'xz' else '0'
    bits = bits.rjust(width, fill)[-width:]
    bits = bits.rjust(wanted_width, '0')[-wanted_width:]
    return binary_value(bits)


def matches(expected, actual):
    if isinstance(expected, str) and expected and not set(expected.lower()) - set('01xz'):
        value, care = binary_value(expected)
        observed, known = actual_number(actual, len(expected))
        return (known & care) == care and ((value ^ observed) & care) == 0, care.bit_count(), len(expected) - care.bit_count()
    return str(expected) == actual, 0, 0


def query(link_path: Path, review_path: Path, out: Path):
    link = json.loads(link_path.read_text())
    review = json.loads(review_path.read_text())
    if link['status'] != 'FULL_MAPPED_VIVADO_LINK_COMPLETE_IMPORT_GRAPH_REVIEW_PENDING' or link['native_exit'] != 0:
        raise ValueError('Completed full mapped link required')
    if link['profile'] != PROFILE or review['profile'] != PROFILE:
        raise ValueError('Complete profile changed')
    checkpoint = link['outputs']['linked.dcp']
    for descriptor in [checkpoint, review['exported_json']]:
        if describe(descriptor['path']) != descriptor:
            raise ValueError('Pinned full memory input changed')
    expected = expected_memory(review['exported_json']['path'])
    if len(expected) != 5623:
        raise ValueError('Complete memory-cell inventory changed')
    out.mkdir(parents=True, exist_ok=False)
    (out / 'expected.json').write_text(json.dumps(expected, indent=2) + '\n')
    lines = ['set_param general.maxThreads 8', 'set_param tcl.collectionResultDisplayLimit 0',
             'open_checkpoint ' + quote(checkpoint['path']),
             'set memory_cells [get_cells -hierarchical -filter {REF_NAME == RAMB36E1 || REF_NAME == RAMB18E1 || REF_NAME == RAM32M || REF_NAME == RAM64M}]',
             'if {[llength $memory_cells] != 5623} {error "Full imported memory inventory differs"}',
             'set by_name [dict create]',
             'foreach c $memory_cells {dict set by_name [get_property NAME $c] $c}',
             'set pf [open parameters.tsv w]', 'puts $pf "cell\\tprimitive\\tparameter\\tvalue\\tpresent"']
    for name, row in expected.items():
        lines += ['if {![dict exists $by_name ' + quote(name) + ']} {error "Exact imported memory cell missing"}',
                  'set c [dict get $by_name ' + quote(name) + ']',
                  'set properties [list_property $c]',
                  'if {[get_property REF_NAME $c] != ' + quote(row['primitive']) + '} {error "Memory primitive changed"}']
        for key in row['parameters']:
            lines += ['set present [expr {' + quote(key) + ' in $properties}]',
                      'set value PROPERTY_NOT_PRESENT',
                      'if {$present} {set value [get_property ' + quote(key) + ' $c]}',
                      'puts $pf [join [list ' + quote(name) + ' ' + quote(row['primitive']) + ' ' + quote(key) + ' $value $present] "\\t"]']
    lines += ['close $pf', 'puts "ALL_5623_MAPPED_MEMORY_PARAMETER_QUERIES_COMPLETE"', 'exit 0']
    (out / 'query.tcl').write_text('\n'.join(lines) + '\n')
    argv = [expand_paths('@VIVADO_BIN@/vivado'), '-mode', 'batch', '-nojournal', '-nolog', '-notrace',
            '-source', str(out / 'query.tcl')]
    (out / 'command.json').write_text(json.dumps(argv, indent=2) + '\n')
    info = {'status': 'RUNNING', 'created_utc': datetime.now(timezone.utc).isoformat(),
            'link': describe(link_path), 'review': describe(review_path), 'checkpoint': checkpoint,
            'profile': PROFILE, 'memory_cells': len(expected), 'helper': describe(__file__),
            'expected': describe(out / 'expected.json'), 'hardware_accessed': False,
            'live_full_jobs_changed': False, 'full_import_equivalence': False,
            'scope': 'COMPLETE_EXPLICIT_MEMORY_PARAMETERS_NOT_FULL_TIMING_OR_HARDWARE_PASS'}

    def save(**fields):
        info.update(fields)
        (out / 'manifest.json').write_text(json.dumps(info, indent=2) + '\n')

    try:
        save(stage='native-linked-memory-parameter-query')
        print('FULL_MEMORY_PARAMETER_QUERY_STARTED ' + str(out), flush=True)
        with (out / 'query.log').open('w') as log:
            child = subprocess.Popen(argv, cwd=out, stdout=log, stderr=subprocess.STDOUT)
            save(native_launcher_pid=child.pid)
            code = child.wait()
        (out / 'query.exit').write_text(str(code) + '\n')
        save(native_exit=code)
        if code or 'ALL_5623_MAPPED_MEMORY_PARAMETER_QUERIES_COMPLETE' not in (out / 'query.log').read_text(errors='replace'):
            raise RuntimeError('Complete native memory query failed')
        with (out / 'parameters.tsv').open() as stream:
            rows = list(csv.DictReader(stream, delimiter='\t'))
        wanted = {(n, key) for n, row in expected.items() for key in row['parameters']}
        found = {(row['cell'], row['parameter']) for row in rows}
        if len(found) != len(rows) or found != wanted:
            raise ValueError('Full parameter coverage or uniqueness differs')
        errors = []
        known_bits = dontcare_bits = 0
        for row in rows:
            raw = expected[row['cell']]['parameters'][row['parameter']]
            try:
                same, known, dontcare = matches(raw, row['value']) if row['present'] == '1' else (False, 0, 0)
            except (ValueError, TypeError):
                same, known, dontcare = False, 0, 0
            known_bits += known
            dontcare_bits += dontcare
            if not same:
                errors.append({'cell': row['cell'], 'parameter': row['parameter'], 'expected': raw,
                               'actual': row['value'], 'present': row['present']})
        (out / 'mismatches.json').write_text(json.dumps(errors, indent=2) + '\n')
        save(status='ALL_5623_MAPPED_MEMORY_CELLS_EXPLICIT_PARAMETERS_AND_KNOWN_INIT_BITS_MATCH' if not errors else
             'MEMORY_PARAMETER_REVIEW_INCOMPLETE_MISMATCHES_REQUIRE_REVIEW',
             parameters=len(rows), mismatch_count=len(errors), known_source_bits_compared=known_bits,
             source_dontcare_bits=dontcare_bits,
             outputs={name: describe(out / name) for name in ['parameters.tsv', 'mismatches.json']},
             completed_utc=datetime.now(timezone.utc).isoformat())
        print(json.dumps({key: info[key] for key in ['status', 'parameters', 'mismatch_count', 'known_source_bits_compared', 'source_dontcare_bits']}), flush=True)
    except Exception as exc:
        save(status='FAIL', error=repr(exc))
        raise
    finally:
        shutil.copy2(__file__, out / 'helper.py')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--link', type=Path, required=True)
    parser.add_argument('--review', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    query(args.link.resolve(), args.review.resolve(), args.out.resolve())


if __name__ == '__main__':
    main()
