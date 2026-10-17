#!/usr/bin/env python3
"""Bind reviewed eight-lane firmware to c0172080 and calibrate CH0 over PCIe.

Requires a reviewed full-image package and a fresh SRAM configuration. No
FPGA programming or flash writes. Calibration overwrites disposable CH0 data;
whole-memory initialization and native qualification must follow separately.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from fedora_prepare_litedram import sha
from probe_ramtest_spare_calibration import preflight as reference_preflight
from opentpu.host import selfcal,regs as R
from opentpu.host.spare_pcie import SparePcieProfile,SpareXdmaTransport,SpareChestnutTransport
from opentpu.host.dual_pcie import require


def bind_firmware(profile,reference,firmware):
    """A new explicit image binding; never change the reference package's guards."""
    phy=reference_preflight(reference,firmware)
    matched={}
    for name in ('otpu_litedram.v','csr.csv','sdram_init.py','sdram_init_ch0.py','otpu_litedram_mem.init'):
        require(sha(profile.core/name)==sha(reference/'core'/name),'Calibration core differs from reviewed reference: '+name)
        matched[name]=sha(profile.core/name)
    require(phy['channels']==[0] and phy['modules']==8 and phy['databits']==64 and phy['dfi_databits']==128,
            'Require CH0-only eight-lane firmware')
    return phy,dict(required_build_id='c0172080',required_bitstream_sha256=profile.bitstream_sha256,
                    full_package_manifest_sha256=profile.manifest_sha256,
                    firmware_id='c0172068',firmware_sha256=sha(firmware/'selfcal.bin'),
                    reference_package_sha256=sha(reference/'bundle.json'),
                    reference_firmware_sha256=sha(firmware/'bundle.json'),matched_core_files=matched,
                    note='Identical controller/CSR/PHY configuration; new full-image routing still needs physical qualification')


def calibrate(transport,image,phy,state,save):
    csr=transport.csr;channels=transport.channels
    transport.profile.check_image(transport)
    def idle():
        status=transport.reg_read(R.R_STATUS)
        require(not status&(R.ST_RUN|R.ST_LOADING|R.ST_ERROR|R.ST_AXI_ERR) and status&R.ST_WR_IDLE,
                f'Accelerator must be idle and error-free: {status:#x}')
        counts={str(off):transport.reg_read(off) for off in (R.R_A_RD,R.R_A_WR,R.R_B_RD,R.R_B_WR)}
        require(all(v==0 for v in counts.values()),'Fresh image with no native memory traffic required')
        require(all(c.r('bist_done') for c in channels.values()),'Raw BIST active')
        require(transport.ecc_state()=={ch:dict(ecc_enable=ch,ecc_sec_errors=0,ecc_ded_errors=0) for ch in (0,1)},
                'Unexpected ECC configuration or existing errors')
        return counts
    initial=selfcal.wait(csr,timeout=180,poll=.5)
    state['startup']=initial;state['startup_mailbox']=selfcal.mailbox(csr);save()
    require(initial['done'] and initial['channels'][0][0]=='idle' and initial['channels'][1][0]=='ok',
            'Require original CH1-only startup calibration')
    require(state['startup_mailbox'][:2]==[selfcal.MB_MAGIC_V,0xc0172060],'Unexpected startup firmware identity')
    state['native_before']=idle()
    require(channels[0].r('cal_ready')==0 and channels[1].r('cal_ready')==1,'Require a fresh spare configuration')
    ch1_phase=channels[1].r('phase_dqs_steps');state['ch1_phase_before']=ch1_phase
    state['temperature_before_c']=R.temp_c(transport.reg_read(R.R_TEMP))
    require(selfcal.present(csr) and selfcal.mem_words(csr)==4096,'Firmware RAM/CPU differs')
    transport.reg_write(R.R_SCRATCH,0)
    state['status']='UPLOADING_SPARE_PCIE_CH0_FIRMWARE';save()
    words=selfcal.load(csr,image,verify=True)
    require(words==4096 and selfcal.held(csr),'Incomplete verified firmware upload')
    state.update(firmware_uploaded=True,firmware_words_verified=words);save()
    csr.w('selfcal_config',257);require(csr.r('selfcal_config')==257,'CH0 calibration configuration differs')
    state.update(status='CALIBRATING_SPARE_PCIE_CH0',calibration_requested=True);save()
    selfcal.release(csr)
    result=selfcal.wait(csr,timeout=180,poll=.5);mailbox=selfcal.mailbox(csr)
    state.update(calibration=result,mailbox=mailbox);save()
    require(mailbox[:2]==[selfcal.MB_MAGIC_V,0xc0172068],'Unexpected CH0 firmware identity')
    decoded=selfcal.decode(mailbox,phy,phy.get('groups'));state['decoded']=decoded;save()
    require(set(decoded)=={0} and len(decoded[0]['read'])==8,'Wrong decoded calibration lane count')
    require(result['done'] and result['channels'][0][0]=='ok' and result['channels'][1][0]=='idle',
            'CH0 calibration did not complete successfully')
    require(channels[0].r('cal_ready')==channels[1].r('cal_ready')==1,'Channel readiness differs')
    require(channels[1].r('phase_dqs_steps')==ch1_phase,'CH1 calibration phase changed')
    state['native_after']=idle();state['temperature_after_c']=R.temp_c(transport.reg_read(R.R_TEMP))
    state['phase_after']={str(ch):c.r('phase_dqs_steps') for ch,c in channels.items()}
    require(state['native_after']==state['native_before'],'Native traffic occurred during calibration')
    transport.guard()
    state.update(status='SPARE_PCIE_CH0_CALIBRATION_RECORDED_MEMORY_UNQUALIFIED',
                 normal_memory_requires_initialization=True);save()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('package','reference-package','firmware','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--transport',choices=('xdma','chestnut'),default='xdma');p.add_argument('--dev',default='/dev/xdma0')
    p.add_argument('--preflight-only',action='store_true');a=p.parse_args()
    a.out.mkdir(parents=True,exist_ok=False);transport=None
    state=dict(status='CHECKING',hardware_accessed=False,programming_performed=False,flash_written=False,
               firmware_uploaded=False,calibration_requested=False,normal_memory_requires_initialization=True)
    def save():
        state['utc']=datetime.now(timezone.utc).isoformat();t=a.out/'manifest.json.tmp'
        t.write_text(json.dumps(state,indent=2)+'\n');t.replace(a.out/'manifest.json')
    try:
        save();profile=SparePcieProfile(a.package)
        phy,binding=bind_firmware(profile,a.reference_package,a.firmware);state['binding']=binding
        paths=[Path(__file__),ROOT/'opentpu/host/spare_pcie.py',ROOT/'opentpu/host/selfcal.py',ROOT/'opentpu/host/ddrcal.py']
        state['source_hashes']={str(f.resolve()):sha(f) for f in paths};save()
        if a.preflight_only:state['status']='SPARE_PCIE_CALIBRATION_PREFLIGHT_PASS';return
        state['hardware_access_attempted']=True;save()
        transport=SpareChestnutTransport(profile) if a.transport=='chestnut' else SpareXdmaTransport(profile,a.dev)
        state['hardware_accessed']=True
        calibrate(transport,(a.firmware/'selfcal.bin').read_bytes(),phy,state,save)
        require(all(sha(Path(n))==h for n,h in state['source_hashes'].items()),'Host sources changed during calibration')
    except Exception as e:state.update(status='FAIL',error=repr(e));raise
    finally:
        try:
            if transport is not None:transport.close()
        except Exception as e:state.update(status='FAIL',close_error=repr(e));raise
        finally:save()


if __name__=='__main__':main()
