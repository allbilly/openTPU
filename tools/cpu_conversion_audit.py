#!/usr/bin/env python3
"""Observe llama.cpp's unchanged Q8_0 converter and explain numeric warnings.

Tiny BF16 weights can overflow the float32 reciprocal used by the Python
quantizer. Accept those warnings only when every affected block's stored FP16
scale is zero, so its decoded values are zero for any int8 payload. No converter
code or returned tensor bytes are changed. Compare the resulting GGUF hash with
the measured model to confirm this audit applies to the same bytes.
"""
import argparse
import hashlib
import json
from pathlib import Path
import runpy
import sys
import warnings


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--llama-source', type=Path, required=True)
    parser.add_argument('--model', type=Path, required=True)
    parser.add_argument('--outfile', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--expected-sha256', required=True)
    args = parser.parse_args()
    source = args.llama_source.resolve()
    if args.outfile.exists() or args.receipt.exists():
        raise RuntimeError('Audit outputs must be new files')
    sys.path[:0] = [str(source), str(source/'gguf-py')]
    import numpy as np
    from gguf.quants import Q8_0
    original = Q8_0.quantize_blocks
    report = dict(status='RUNNING', q8_calls=0, q8_blocks=0, reciprocal_overflow_blocks=0,
                  max_abs_affected_weight=0.0, warning_messages=[], unchanged_quantizer=True)

    def checked(cls, blocks):
        if not np.isfinite(blocks).all():
            raise RuntimeError('Nonfinite source weight')
        scales = np.abs(blocks).max(axis=1, keepdims=True)/127
        with np.errstate(over='ignore', invalid='ignore', divide='ignore'):
            inverse = np.where(scales == 0, 0, 1/scales)
        affected = ~np.isfinite(inverse[:, 0])
        count = int(affected.sum())
        if count and not (scales[affected].astype(np.float16) == 0).all():
            raise RuntimeError('Reciprocal overflow affects nonzero stored scales')
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter('always')
            result = original(blocks)
        stored_scales = np.ascontiguousarray(result[:, :2]).view(np.float16)
        if not np.isfinite(stored_scales).all():
            raise RuntimeError('Nonfinite GGUF scale')
        if count and not (stored_scales[affected] == 0).all():
            raise RuntimeError('Affected block has a nonzero GGUF scale')
        allowed = {'overflow encountered in divide', 'invalid value encountered in subtract',
                   'invalid value encountered in cast'}
        for warning in captured:
            message = str(warning.message)
            if not count or message not in allowed:
                raise RuntimeError(f'Unexplained quantization warning: {message}')
            if message not in report['warning_messages']:
                report['warning_messages'].append(message)
        report['q8_calls'] += 1
        report['q8_blocks'] += len(blocks)
        report['reciprocal_overflow_blocks'] += count
        if count:
            report['max_abs_affected_weight'] = max(report['max_abs_affected_weight'],
                                                   float(np.abs(blocks[affected]).max()))
        return result

    Q8_0.quantize_blocks = classmethod(checked)
    try:
        sys.argv = [str(source/'convert_hf_to_gguf.py'), str(args.model), '--outtype', 'q8_0',
                    '--outfile', str(args.outfile)]
        runpy.run_path(sys.argv[0], run_name='__main__')
        digest = hashlib.sha256()
        with args.outfile.open('rb') as data:
            for block in iter(lambda: data.read(4*1024*1024), b''):
                digest.update(block)
        report['gguf_sha256'] = digest.hexdigest()
        report['expected_sha256'] = args.expected_sha256
        if digest.hexdigest() != args.expected_sha256:
            raise RuntimeError('Audited GGUF differs from measured GGUF')
        report.update(status='PASS_UNCHANGED_Q8_CONVERSION_AUDIT',
                      all_affected_stored_scales_zero=True, all_q8_scales_finite=True)
    except BaseException as error:
        report.update(status='FAIL_Q8_CONVERSION_AUDIT', error=repr(error))
        raise
    finally:
        args.receipt.write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
