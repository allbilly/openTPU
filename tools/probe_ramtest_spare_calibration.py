#!/usr/bin/env python3
"""Upload reviewed volatile CH0 firmware and calibrate the eight-lane spare.

Requires a fresh, already loaded c0172060 image and exclusive XVC access.
No FPGA programming or flash write. Calibration writes disposable CH0 data;
native generators stay reset. CH1 calibration must already have finished.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from fedora_prepare_litedram import sha


def checksums(folder):
    folder=folder.resolve();seen=set()
    for line in (folder/'SHA256SUMS').read_text().splitlines():
        checksum,name=line.split(None,1);name=name.strip();path=(folder/name).resolve()
        assert path.is_relative_to(folder) and name not in seen and sha(path)==checksum,name
        seen.add(name)
    return seen


def preflight(package,firmware):
    seen=checksums(package);fw_seen=checksums(firmware)
    assert {'manifest.json','bundle.json','ramtest.bit','core/sdram_init_ch0.py','core/csr.csv','evidence/extension-review.json'}<=seen
    assert {'bundle.json','selfcal.bin','core/csr.csv','core/sdram_init.py','build-manifest.json','host-model-review.json'}<=fw_seen
    b=json.loads((package/'bundle.json').read_text());f=json.loads((firmware/'bundle.json').read_text())
    m=json.loads((firmware/'build-manifest.json').read_text());review=json.loads((firmware/'host-model-review.json').read_text())
    ext=json.loads((package/'evidence/extension-review.json').read_text())
    assert b['variant']=='spare8' and b['build_id']==f['required_build_id']=='c0172060'
    assert b['ecc_channels']==[1] and ext['automatic_calibration_channels']==[1]
    assert ext['status']=='OFFLINE_RAM_VARIANT_EXTENSION_REVIEW_PASS_PHYSICAL_PENDING'
    assert ext['build_manifest_sha256']==sha(package/'manifest.json')
    assert ext['bitstream_sha256']==b['bitstream_sha256']==f['required_bitstream_sha256']==sha(package/'ramtest.bit')
    assert f['firmware_id']==m['firmware_id']=='c0172068' and f['channel_mask']==m['channel_mask']==1
    assert f['modules']==m['modules']==8 and m['dfi_words']==4 and m['bist_words_per_phase']==1
    assert review['status']=='PASS_SPARE_CH0_FIRMWARE_HOST_EQUIVALENCE'
    assert review['build_manifest_sha256']==sha(firmware/'build-manifest.json')
    assert review['binary_sha256']==m['binary_sha256']==f['binary_sha256']==sha(firmware/'selfcal.bin')
    assert sha(firmware/'core/csr.csv')==sha(package/'core/csr.csv')==m['csr_sha256']
    assert sha(firmware/'core/sdram_init.py')==sha(package/'core/sdram_init_ch0.py')==m['config_sha256']
    for name,checksum in m['sources'].items():assert sha(firmware/name)==checksum
    ns={};exec((firmware/'core/sdram_init.py').read_text(),ns)
    assert (ns['phy']['modules'],ns['phy']['databits'],ns['phy']['dfi_databits'],ns['phy']['channels'])==(8,64,128,[0])
    assert 0<(firmware/'selfcal.bin').stat().st_size<=16384
    return ns['phy']


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','firmware','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--host',default='localhost');p.add_argument('--port',type=int,default=3721)
    p.add_argument('--preflight-only',action='store_true');a=p.parse_args();a.out.mkdir(parents=True,exist_ok=False)
    state=dict(status='CHECKING',hardware_accessed=False,programming_performed=False,flash_written=False,
               firmware_uploaded=False,calibration_requested=False,native_generators_started=False,
               supply='Sole 12 V / 2 A adapter; current and card voltage unmeasured')
    link=None
    def save():
        state['utc']=datetime.now(timezone.utc).isoformat()
        t=a.out/'manifest.json.tmp';t.write_text(json.dumps(state,indent=2)+'\n');t.replace(a.out/'manifest.json')
    try:
        save();phy=preflight(a.package,a.firmware)
        state.update(bitstream_sha256=sha(a.package/'ramtest.bit'),firmware_sha256=sha(a.firmware/'selfcal.bin'),
                     firmware_model_sha256=sha(a.firmware/'host-model-review.json'),phy=phy,
                     sources={str(f.resolve()):sha(f) for f in [Path(__file__),ROOT/'opentpu/host/selfcal.py',
                        ROOT/'opentpu/host/ddrcal.py',ROOT/'opentpu/host/jtag.py']})
        if a.preflight_only:state['status']='SPARE_CALIBRATION_PREFLIGHT_PASS';return
        from opentpu.host.jtag import JtagTransport
        from opentpu.host import ddrcal,selfcal
        from probe_ramtest_mig import snapshot
        core=a.package.resolve()/'core';link=JtagTransport(a.host,a.port,calibration_data=core)
        state['hardware_accessed']=True;save()
        assert [link.reg_read(k) for k in (0,4,8,12,0x3c,0x48)]==[0x4c445254,3,0xc0172060,800,100000,0x52444331]
        csr=ddrcal.WordCsr(ddrcal.csr_map(core/'csr.csv'),link.reg_read,link.reg_write,base=0x10000)
        channels={ch:ddrcal.Chan(csr,ch) for ch in (0,1)}
        initial=selfcal.wait(csr,timeout=180,poll=.5)
        state['initial_calibration_state']=initial
        assert initial['channels'][0][0]=='idle' and initial['channels'][1][0]=='ok'
        state['ch1_calibration_before']=selfcal.result(csr,core/'sdram_init.py')[1]
        def idle():
            assert [link.reg_read(k) for k in (0x28,0x2c,0x44)]==[3,3,0]
            assert link.reg_read(0x38)==(channels[0].r('cal_ready')|(channels[1].r('cal_ready')<<1))
            assert all(c.r('bist_done') for c in channels.values())
        def native():
            idle();snap=snapshot(link,3)
            assert all(all(v[k]==0 for k in ('write_commands','read_commands','returned_beats','compared_beats'))
                       and v['raw_words'][62]==v['raw_words'][63]==0 for v in snap.values())
            assert [channels[ch].r('ecc_enable') for ch in (0,1)]==[0,1]
            assert all(c.r('ecc_sec_errors')==c.r('ecc_ded_errors')==0 for c in channels.values())
            return snap
        state['native_before']=native()
        assert channels[0].r('cal_ready')==0 and channels[1].r('cal_ready')==1
        ch1_phase=channels[1].r('phase_dqs_steps');state['ch1_phase_before']=ch1_phase
        state['temperature_before_c']=link.read_die_temperature()
        assert selfcal.present(csr) and selfcal.mem_words(csr)==4096
        state['status']='UPLOADING_AND_VERIFYING_VOLATILE_CH0_FIRMWARE';save()
        n=selfcal.load(csr,(a.firmware/'selfcal.bin').read_bytes(),verify=True)
        assert n==4096 and selfcal.held(csr)
        state.update(firmware_uploaded=True,firmware_memory_words_verified=n);save()
        csr.w('selfcal_config',1|(1<<8))
        assert csr.r('selfcal_config')==257
        state.update(status='CALIBRATING_EIGHT_LANE_CH0',calibration_requested=True);save()
        selfcal.release(csr)
        result=selfcal.wait(csr,timeout=180,poll=.5);mailbox=selfcal.mailbox(csr)
        assert mailbox[0]==selfcal.MB_MAGIC_V and mailbox[1]==0xc0172068
        assert result['done'] and result['channels'][1][0]=='idle'
        decoded=selfcal.decode(mailbox,phy,phy.get('groups'))
        assert set(decoded)=={0} and len(decoded[0]['read'])==8
        state.update(calibration_state=result,ch0_calibration=decoded[0],mailbox=mailbox)
        assert result['channels'][0][0] in ('ok','failed')
        assert channels[0].r('cal_ready')==int(result['channels'][0][0]=='ok')
        assert channels[1].r('cal_ready')==1 and channels[1].r('phase_dqs_steps')==ch1_phase
        state['native_after']=native();state['temperature_after_c']=link.read_die_temperature()
        for name,checksum in state['sources'].items():assert sha(Path(name))==checksum
        state['status']='SPARE_CH0_CALIBRATION_RECORDED_MEMORY_UNQUALIFIED'
    except Exception as error:
        state.update(status='FAIL',error=repr(error));raise
    finally:
        if link is not None:link.close()
        save()


if __name__=='__main__':main()
