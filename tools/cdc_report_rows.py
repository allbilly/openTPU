"""Read every non-info Vivado CDC detail row and verify summary coverage.

Vivado right-aligns the row number in a three-character field. Rows 100 and
higher therefore need no leading whitespace. Summary/detail agreement also
prevents a partial or unexpectedly formatted report from being approved.
"""
from collections import Counter
import re

SUMMARY = re.compile(r'^\s*(CDC-\d+)\s+(Critical|Warning)\s+(\d+)\s+')
DETAIL = re.compile(r'^\s*\d+\s+CDC-\d+\s+(Critical|Warning)\b')


def summary_counts(text):
    result = {}
    for line in text.splitlines():
        match = SUMMARY.match(line)
        if match:
            key = match[1], match[2]
            if key in result:
                raise ValueError('Duplicate CDC summary entry: ' + str(key))
            result[key] = int(match[3])
    if not result:
        raise ValueError('Missing non-info CDC summary')
    return {key: value for key, value in result.items() if value}


def cdc_rows(text):
    rows = []
    for line in text.splitlines():
        if not DETAIL.match(line):
            continue
        fields = re.split(r'\s{2,}', line.strip())
        if len(fields) != 8:
            raise ValueError('Unexpected CDC detail format: ' + line[:160])
        rows.append(tuple(fields[1:]))
    if not rows:
        raise ValueError('Missing non-info CDC detail rows')
    expected = Counter(summary_counts(text))
    actual = Counter((row[0], row[1]) for row in rows)
    if expected != actual:
        raise ValueError('Incomplete CDC details: summary=' + repr(dict(expected)) +
                         ', parsed=' + repr(dict(actual)))
    return rows
