#!/usr/bin/env python3
"""Reaudit the preserved MIG image with an exact historical host snapshot.

The model token observer added since qualification is not used by memory
diagnostics. Reconstruct its predecessor and prove the original witness hash,
then run every existing image/CDC/IP/runtime check without changing the donor.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CAND = ROOT / 'build/fedora-vivado/mig-jtag-controller-20261010T235833Z'


def describe(path):
    path = Path(path).resolve()
    return dict(path=str(path), bytes=path.stat().st_size,
                sha256=hashlib.sha256(path.read_bytes()).hexdigest())


def qualify(out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    checks = ROOT / 'opentpu/host/checks.py'
    historical = checks.read_text().replace(
        '    token_hook = getattr(t, "record_model_token", None) if not sim else None\n', '')
    historical = historical.replace(
        '    got = dev.generate(ids, max_new=tokens, **({"on_token": token_hook} if token_hook else {}))\n',
        '    got = dev.generate(ids, max_new=tokens)\n')
    snapshot = out / 'historical-model-checks.py'
    snapshot.write_text(historical)
    witnesses = json.loads((CAND / 'runtime-host-witness.json').read_text())
    expected = [x for x in witnesses if x['path'] == str(checks)]
    if len(expected) != 1 or any(describe(snapshot)[k] != expected[0][k]
                                 for k in ('bytes', 'sha256')):
        raise ValueError('Historical model helper does not match its exact original witness')
    original = CAND / 'check_candidate.py'
    source = original.read_text()
    anchor = 'CAND = Path(__file__).resolve().parent'
    assert source.count(anchor) == 1
    source = source.replace(anchor, 'CAND = Path(' + repr(str(CAND)) + ')')
    anchor = "    runtime = json.loads((CAND / 'runtime-host-witness.json').read_text())\n"
    assert source.count(anchor) == 1
    source = source.replace(anchor, anchor +
        '    # Exact witnessed predecessor; unused by this memory-only experiment.\n' +
        '    runtime = [dict(item, path=' + repr(str(snapshot)) + ') if item["path"] == ' +
        repr(str(checks)) + ' else item for item in runtime]\n')
    adapted = out / 'check_reference.py'
    adapted.write_text(source)
    spec = importlib.util.spec_from_file_location('qualified_mig_memory_reference', adapted)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    result = module.check()
    if result['status'] != 'PASS_MIG_NATIVE_IMAGE_OFFLINE_AUDIT':
        raise ValueError('MIG offline image audit did not pass')
    result.update(status='PASS_MIG_IMAGE_FOR_MEMORY_DIAGNOSTICS',
                  original_checker=describe(original), current_model_helper=describe(checks),
                  historical_model_helper=describe(snapshot),
                  historical_witness=expected[0],
                  scope='Existing image, pins, route, timing, CDC, generated IP and witnessed runtime; model helper reconstructed exactly; no model execution claimed',
                  original_donor_modified=False)
    (out / 'qualification.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    args = ap.parse_args()
    result = qualify(args.out)
    print(json.dumps({k:result[k] for k in ('status','bitstream','timing','route','scope')}))
