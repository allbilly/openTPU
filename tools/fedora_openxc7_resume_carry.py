#!/usr/bin/env python3
"""Require real carry equivalence/route/frames before the existing full flow."""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from fedora_openxc7 import ROOT, configuration, describe, digest
from fedora_openxc7_resume_route import resume


def carry_then_resume(out):
    mp = out/'pipeline.json'
    info = json.loads(mp.read_text())
    def save(**fields):
        info.update(fields, updated_utc=datetime.now(timezone.utc).isoformat())
        tmp = mp.with_suffix('.json.tmp');tmp.write_text(json.dumps(info,indent=2)+'\n');tmp.replace(mp)
    def unchanged():
        for path, expected in info['planned_inputs'].items():
            if digest(path) != expected:
                raise RuntimeError('Planned input changed: '+path)
    def run(argv, stage, env=None, stdout=None):
        unchanged();save(status='RUNNING',stage=stage)
        (out/(stage+'.command.json')).write_text(json.dumps(argv,indent=2)+'\n')
        with (out/(stage+'.log')).open('w') as log:
            if stdout:
                with stdout.open('w') as target:
                    r = subprocess.run(argv,cwd=ROOT,env=env,stdout=target,stderr=log)
            else:
                r = subprocess.run(argv,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
        (out/(stage+'.exit')).write_text(str(r.returncode)+'\n')
        if r.returncode:
            raise RuntimeError(stage+' exited '+str(r.returncode))
    try:
        unchanged()
        bm = Path(info['backend']['manifest']);backend = json.loads(bm.read_text())
        if backend.get('carry_padding') != 'BUILT_BEHAVIOR_NOT_YET_TESTED':
            raise RuntimeError('Required carry correction did not build')
        probe = out/'carry-probe'
        argv = [sys.executable,str(ROOT/'tools/openxc7_carry_padding_check.py'),
                '--backend-manifest',str(bm),'--out',str(probe)]
        if info.get('adopt_carry_route'):
            argv += ['--adopt-routed',info['adopt_carry_route']]
        run(argv,'carry-route-and-equivalence')
        pm = json.loads((probe/'manifest.json').read_text())
        if pm['status'] != 'CARRY_ROUTE_AND_EXHAUSTIVE_EQUIVALENCE_PASS':
            raise RuntimeError('Real carry gate did not pass')
        cfg = configuration();frame = probe/'probe.frames'
        run([str(cfg['fasm2frames'].parent/'python'),str(ROOT/'tools/openxc7_fasm2frames.py'),
             '--db-root',str(cfg['database']),'--part','xc7k480tffg1156-2',str(probe/'probe.fasm')],
            'carry-probe-strict-frames',dict(os.environ,PYTHONPATH=str(cfg['xray'])),frame)
        save(carry_probe=dict(status='CARRY_ROUTE_EQUIVALENCE_AND_STRICT_FRAMES_PASS',
                              manifest=describe(probe/'manifest.json'),strict_frames=describe(frame),
                              patterns=pm['patterns'],compared_outputs=pm['compared_outputs']))
    except Exception as e:
        save(status='FAIL',error=str(e));print(e,file=sys.stderr);return 1
    return resume(out)


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,required=True)
    args = ap.parse_args()
    sys.exit(carry_then_resume(args.out.resolve()))
