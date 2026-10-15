#!/usr/bin/env python3
"""Verify a corrected backend, then route an existing full mapped checkpoint.

The durable controller records every stage and fails closed on changed inputs,
failed backend builds or failed real cascade probes. It never synthesizes the
full design, programs hardware or overwrites earlier failed-run evidence.
"""
from datetime import datetime, timezone
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from fedora_openxc7 import ROOT, configuration, describe, digest


def resume(out):
    mp = out/'pipeline.json'
    info = json.loads(mp.read_text())

    def save(**fields):
        info.update(fields, updated_utc=datetime.now(timezone.utc).isoformat())
        temporary = mp.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(info, indent=2)+'\n')
        temporary.replace(mp)

    def unchanged():
        for path, expected in info['planned_inputs'].items():
            if digest(path) != expected:
                raise RuntimeError('Planned input changed: '+path)

    def run(argv, name, env=None, stdout_path=None):
        unchanged()
        save(status='RUNNING', stage=name)
        (out/(name+'.command.json')).write_text(json.dumps(argv, indent=2)+'\n')
        with (out/(name+'.log')).open('w') as log:
            if stdout_path:
                with Path(stdout_path).open('w') as target:
                    result = subprocess.run(argv, cwd=ROOT, env=env, stdout=target, stderr=log)
            else:
                result = subprocess.run(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        (out/(name+'.exit')).write_text(str(result.returncode)+'\n')
        if result.returncode:
            raise RuntimeError(name+' exited '+str(result.returncode))

    try:
        unchanged()
        backend_path = Path(info['backend']['manifest'])
        save(status='WAITING_FOR_DSP_BACKEND_BUILD', stage='wait-backend')
        while True:
            try:
                backend = json.loads(backend_path.read_text())
            except (FileNotFoundError, json.JSONDecodeError):
                backend = dict(status='RUNNING')
            if backend.get('status') != 'RUNNING':
                break
            state = subprocess.run(['systemctl','--user','show',info['backend']['service'],
                                    '--property=ActiveState','--value'], capture_output=True, text=True)
            if state.stdout.strip() not in ('active','activating','deactivating'):
                raise RuntimeError('Backend owner is terminal without a completed manifest')
            time.sleep(10)
        if backend['status'] != 'BACKEND_BUILD_PASS_DSP_CASCADE_BEHAVIOR_NOT_YET_TESTED':
            raise RuntimeError('Backend build did not pass: '+str(backend.get('error',backend['status'])))
        if digest(backend['binary']['path']) != backend['binary']['sha256']:
            raise RuntimeError('Backend binary changed')
        for relative, expected in json.loads(Path(backend['source_inventory']['path']).read_text()).items():
            if digest(Path(backend['source'])/relative) != expected:
                raise RuntimeError('Backend source changed: '+relative)
        save(corrected_backend=dict(manifest=describe(backend_path), binary=backend['binary'], source=backend['source']))
        probe = out/'cascade-probe'
        run([sys.executable,str(ROOT/'tools/openxc7_dsp_cascade_check.py'),
             '--backend-manifest',str(backend_path),'--geometry',info['geometry'],
             '--modes',info['modes'],'--out',str(probe)],'dsp-cascade-probe')
        pm = json.loads((probe/'manifest.json').read_text())
        if pm['status'] != 'DSP_CASCADE_16_SITE_PLACEMENT_AND_ROUTING_PASS_STRICT_FRAMES_NOT_TESTED':
            raise RuntimeError('Cascade probe did not pass')
        cfg = configuration()
        frame_env = dict(os.environ, PYTHONPATH=str(cfg['xray']))
        run([str(cfg['fasm2frames'].parent/'python'),str(ROOT/'tools/openxc7_fasm2frames.py'),
             '--db-root',str(cfg['database']),'--part','xc7k480tffg1156-2',str(probe/'probe.fasm')],
            'dsp-probe-strict-frames',frame_env,probe/'probe.frames')
        save(cascade_probe=dict(manifest=describe(probe/'manifest.json'),
                               strict_frames=describe(probe/'probe.frames'),
                               status='PROBE_ROUTE_AND_STRICT_FRAMES_PASS_NUMERICAL_TIMING_NOT_QUALIFIED'))
        synth = Path(info['synthesis_directory'])
        sm = json.loads((synth/'manifest.json').read_text())
        if sm['status'] != 'SYNTHESIS_PASS_IMPLEMENTATION_NOT_RUN' or sm['parameters'] != info['configuration']:
            raise RuntimeError('Full mapped checkpoint status or parameters differ')
        if digest(synth/'synth.json') != sm['artifacts']['synth.json']['sha256']:
            raise RuntimeError('Full mapped checkpoint hash differs')
        save(adopted_synthesis_manifest=describe(synth/'manifest.json'), mapped_checkpoint=describe(synth/'synth.json'))
        route = out/'route'
        route_env = dict(os.environ, OTPU_NEXTPNR=backend['binary']['path'], OTPU_NEXTPNR_SOURCE=backend['source'])
        run([sys.executable,str(ROOT/'tools/fedora_openxc7.py'),'jtag-route',
             '--netlist',str(synth/'synth.json'),'--litedram-core',info['litedram_core'],
             '--out',str(route)],'full-ddr800-route',route_env)
        routed = json.loads((route/'manifest.json').read_text())
        if routed['parameters'] != info['configuration'] or routed['litedram']['manifest'] != str(Path(info['litedram_core'])/'openxc7-profile.json'):
            raise RuntimeError('Route changed the full DDR800 profile')
        frame, bit = out/'design.frames', out/'design.bit'
        run([str(cfg['fasm2frames'].parent/'python'),str(ROOT/'tools/openxc7_fasm2frames.py'),
             '--db-root',str(cfg['database']),'--part','xc7k480tffg1156-2',str(route/'design.fasm')],
            'strict-frames',frame_env,frame)
        run([str(cfg['frames2bit']),'--part_file='+str(cfg['database']/'xc7k480tffg1156-2/part.yaml'),
             '--part_name=xc7k480tffg1156-2','--frm_file='+str(frame),'--output_file='+str(bit)],'frames-to-bit')
        save(status='FULL_CONFIGURATION_ASSEMBLY_PASS_TIMING_QUALIFICATION_INCOMPLETE', stage='assembled',
             artifacts={p.name:describe(p) for p in (frame,bit)}, timing='NOT_QUALIFIED',
             physical_hardware='NOT_RUN', programming='NOT_RUN')
    except Exception as error:
        save(status='FAIL', error=str(error))
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', type=Path, required=True)
    args = ap.parse_args()
    sys.exit(resume(args.out.resolve()))
