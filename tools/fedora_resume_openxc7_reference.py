#!/usr/bin/env python3
"""Resume the full LiteDRAM implementation against the frozen Vivado reference.

Adopts the complete independently synthesized checkpoint and exact corrected
backend receipts. It runs placement/routing, then the existing guarded frame
assembler and independent image checker. It never opens or programs hardware.
"""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys

from fedora_openxc7 import ROOT, describe, digest
from fedora_check_jtag_image import select_jtag_backend, synthesis_witness

DEFAULT_SELECTION = ROOT/'build/fedora-openxc7/merged-carry-sites-backend-20261010T1935HKT/qualified-jtag-backend.json'
REFERENCE_BIT_SHA = '0863b3e2a7f45b1c75e8229e4d18247baaa73b3bc8746240f14d6199424d4e4f'


def now():
    return datetime.now(timezone.utc).isoformat()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--reference', required=True, type=Path)
    ap.add_argument('--selection', type=Path, default=DEFAULT_SELECTION)
    args = ap.parse_args()
    out, reference, selection = args.out.resolve(), args.reference.resolve(), args.selection.resolve()
    if out.exists():
        ap.error('Choose a new output directory')
    out.mkdir(parents=True)
    info = dict(status='RUNNING', stage='verify-inputs', started_utc=now(),
                controller_pid=os.getpid(), physical_hardware='NOT_RUN',
                flash_written=False, synthesis_reused=True,
                scope='FULL_LITEDRAM_OPENXC7_WITH_VIVADO_FUNCTIONAL_REFERENCE')

    def save():
        temp = out/'manifest.json.tmp'
        temp.write_text(json.dumps(info,indent=2)+'\n')
        temp.replace(out/'manifest.json')

    def unchanged():
        for path, expected in info.get('planned_inputs',{}).items():
            if digest(path) != expected:
                raise RuntimeError('Input changed: '+path)

    def run(stage, command, env=None):
        unchanged()
        info.update(status='RUNNING',stage=stage)
        (out/(stage+'.command.json')).write_text(json.dumps(command,indent=2)+'\n')
        print('START '+stage,flush=True)
        with (out/(stage+'.log')).open('w') as log:
            child = subprocess.Popen(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
            info['child_pid'] = child.pid
            save()
            code = child.wait()
        info.pop('child_pid',None)
        info[stage+'_exit'] = code
        (out/(stage+'.exit')).write_text(str(code)+'\n')
        save()
        if code:
            raise RuntimeError(stage+' exited '+str(code))

    try:
        save()
        selected = json.loads(selection.read_text())
        backend, gates, inventory = select_jtag_backend(selection)
        counts = synthesis_witness(selected)
        synthesis = json.loads(Path(selected['adopted_synthesis_manifest']['path']).read_text())
        native = json.loads((reference/'manifest.json').read_text())
        expected = selected['configuration']
        for name, value in expected.items():
            if name != 'DDR_MTS' and native['configuration'].get(name) != value:
                raise RuntimeError('Reference compute/core parameter differs: '+name)
        bit = reference/'implementation/otpu_mig_jtag.runs/impl_1/otpu_fpga_top_vivado_mig_jtag.bit'
        bit_record = describe(bit)
        if bit_record['sha256'] != REFERENCE_BIT_SHA:
            raise RuntimeError('Working Vivado reference bitstream differs')
        inventory.update(synthesis['source'])
        comparison = []
        for name, expected_sha in synthesis['source'].items():
            source = Path(name)
            if not source.is_relative_to(ROOT/'rtl'):
                continue
            frozen = reference/'source'/source.relative_to(ROOT)
            if not frozen.is_file():
                continue
            actual = describe(frozen)
            inventory[actual['path']] = actual['sha256']
            same = actual['sha256'] == expected_sha
            relative = str(source.relative_to(ROOT))
            if not same and relative != 'rtl/boards/ypcb-00338/otpu_mem_ch.sv':
                raise RuntimeError('Shared compute source differs from reference: '+relative)
            comparison.append(dict(relative=relative, same=same,
                                   openxc7_sha256=expected_sha, vivado_sha256=actual['sha256']))
        if len(comparison) != 25:
            raise RuntimeError('Shared reference-source comparison scope differs')
        for item in (describe(selection), selected['mapped_checkpoint'],
                     selected['adopted_synthesis_manifest'], describe(reference/'manifest.json'),
                     bit_record, describe(reference/'routed.dcp'), describe(__file__),
                     describe(ROOT/'tools/fedora_openxc7.py'),
                     describe(ROOT/'tools/fedora_finalize_jtag_route.py')):
            inventory[item['path']] = item['sha256']
        info.update(planned_inputs=inventory, selection=describe(selection),
                    corrected_backend=backend, correction_gates=list(gates),
                    mapped_counts=dict(counts), configuration=expected,
                    vivado_reference=dict(directory=str(reference),bitstream=bit_record,
                        configuration=native['configuration'],source_comparison=comparison,
                        memory_controller='MIG_NATIVE',physical_model='PENDING'),
                    openxc7_memory_controller='LITEDRAM',route_threads=len(os.sched_getaffinity(0)))
        save()
        run('vivado-reference-audit',[sys.executable,str(reference/'check_candidate.py'),
                                    '--out',str(out/'vivado-reference-audit.json')])
        route = out/'route'
        env = dict(os.environ, OTPU_THREADS='all', OTPU_NEXTPNR=backend['binary']['path'],
                   OTPU_NEXTPNR_SOURCE=backend['source'])
        run('full-route',[sys.executable,str(ROOT/'tools/fedora_openxc7.py'),'jtag-route',
                          '--netlist',selected['mapped_checkpoint']['path'],
                          '--litedram-core',selected['litedram_core'],'--out',str(route)],env)
        routed = json.loads((route/'manifest.json').read_text())
        if (routed.get('status') != 'ROUTE_PASS_TIMING_QUALIFICATION_INCOMPLETE' or
                routed.get('parameters') != expected or
                routed['tools']['nextpnr'] != backend['binary']):
            raise RuntimeError('Full route identity or terminal result differs')
        assembly = out/'assembly'
        run('prepare-assembly',[sys.executable,str(ROOT/'tools/fedora_finalize_jtag_route.py'),
                               'prepare','--out',str(assembly),'--route',str(route),
                               '--selection',str(selection)])
        run('assemble-and-check',[sys.executable,str(ROOT/'tools/fedora_finalize_jtag_route.py'),
                                 'assemble','--out',str(assembly)])
        info.update(status='FULL_OPENXC7_IMPLEMENTATION_AND_IMAGE_CHECK_PASS_TIMING_NOT_QUALIFIED',
                    stage='independently-checked',assembly_manifest=describe(assembly/'pipeline.json'),
                    timing='NOT_QUALIFIED',physical_hardware='NOT_RUN')
        save()
        print(info['status'],flush=True)
        return 0
    except Exception as error:
        info.update(status='FAIL',error=repr(error),finished_utc=now())
        save()
        print(info['error'],file=sys.stderr,flush=True)
        return 1
    finally:
        if info['status'] != 'RUNNING':
            info['finished_utc'] = now()
            save()


if __name__ == '__main__':
    raise SystemExit(main())
