#!/usr/bin/env python3
"""Compare the bounded eight-lane firmware with a separately adapted host model.

All operations are simulated CSR callbacks. No hardware is accessed. The
reference copy adjusts 64-bit DQ framing, eight lane counters and one-word BIST
only; production host files remain unchanged.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import sys
from fedora_prepare_litedram import ROOT, sha
from prepare_ramtest_spare_calibration import load_module, replace_once


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--build',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    a=p.parse_args();build=a.build.resolve();a.out.mkdir(parents=True,exist_ok=False)
    m=json.loads((build/'manifest.json').read_text())
    assert m['status']=='SPARE_CH0_FIRMWARE_BUILT_MODEL_REVIEW_PENDING'
    for name,checksum in m['sources'].items():assert sha(build/name)==checksum
    assert sha(build/'target/selfcal.bin')==m['binary_sha256']
    source=build/'source'
    fw=load_module(source/'tools/litedram/selfcal_fw/fw.py')
    reference=(source/'opentpu/host/ddrcal.py').read_text()
    reference=replace_once(reference,'(72 + 8 * m + i)','(64 + 8 * m + i)')
    reference=replace_once(reference,'for m in range(9)]','for m in range(8)]')
    reference=replace_once(reference,'            beats = mib * (1 << 20) // 64','            beats = 1')
    ref_path=a.out/'reference_ddrcal.py';ref_path.write_text(reference)
    spec=importlib.util.spec_from_file_location('spare_reference',ref_path)
    ref=importlib.util.module_from_spec(spec);spec.loader.exec_module(ref)
    sys.path[:0]=[str(ROOT),str(ROOT/'tests')]
    import selfcal_harness as harness
    from opentpu.host import selfcal
    harness.fw=fw;harness.C=ref
    firmware=harness.Firmware(build/'core',a.out/'host-model')
    ns={};exec((build/'core/sdram_init.py').read_text(),ns);phy=ns['phy']
    reports=[]
    for case in ('ordinary','per-bit-frame','missing-lane-window'):
        def board():
            b=ref.FakeCsr(build/'core',nm=8,groups=[0]*8,ps_moves_ck=True)
            if case=='per-bit-frame':
                b.RB[6]=3;b.BOFF={(6,1):2,(6,5):-2}
            if case=='missing-lane-window':b.WLO[6]=100;b.WHI[6]=0
            return b
        before,results=harness.reference(build/'core',board(),stride=8,mask=1)
        b=board();trace=harness.Trace(b);mb,own,cycles=firmware.run(trace,mask=1,stride=8)
        assert trace.log==before,harness.first_diff(before,trace.log)
        dec=selfcal.decode(mb,phy,phy.get('groups'))
        assert set(dec)=={0} and len(dec[0]['read'])==8
        r=results[0]
        if isinstance(r,Exception):assert dec[0]['state']=='failed' and dec[0]['error']
        else:
            assert dec[0]['state']=='ok' and {k:dec[0][k] for k in r}==r
            assert b.v['cal_ready']==1
        assert all(not name.startswith(('ddrphy1_','sdram1_','bist1_','phase1_','wclk1_','cal1_')) for name,v in trace.log)
        lengths=[v for name,v in trace.log if name=='bist_length'];assert lengths and set(lengths)=={1}
        assert all(v<256 for name,v in trace.log if name=='ddrphy_dly_sel')
        reports.append(dict(case=case,state=dec[0]['state'],error=dec[0]['error'],csr_writes=len(trace.log),
                            bist_length_writes=len(lengths),simulated_cycles=cycles,exact_reference_trace_match=True))
    assert [r['state'] for r in reports]==['ok','ok','failed']
    receipt=dict(status='PASS_SPARE_CH0_FIRMWARE_HOST_EQUIVALENCE',hardware_accessed=False,
        build_manifest_sha256=sha(build/'manifest.json'),binary_sha256=m['binary_sha256'],reports=reports,
        reference_sha256=sha(ref_path),checker_sha256=sha(Path(__file__)),
        host_library_sha256=sha(a.out/'host-model/libselfcal.so'),
        limitations=['Host compilation exercises C algorithms and CSR accesses, not RV32 instruction execution',
                     'Firmware upload and physical eight-lane calibration remain pending'])
    (a.out/'manifest.json').write_text(json.dumps(receipt,indent=2)+'\n');print(json.dumps(receipt))


if __name__=='__main__':main()
