#!/usr/bin/env python3
"""Bind reviewed eight-lane firmware to c0182863 and calibrate CH0 over PCIe.

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
from opentpu.host.spare_c0182863 import SparePcieProfile,SpareXdmaTransport,SpareChestnutTransport, SpareJtagTransport
from opentpu.host.dual_pcie import require


def bind_firmware(profile,reference,firmware):
    from fedora_prepare_litedram import phy_config
    require(reference.resolve()==profile.package and firmware.resolve()==profile.package/'calibration',
            'DDR1066 calibration must come from this exact reviewed full-image package')
    bundle=json.loads((firmware/'bundle.json').read_text())
    review=profile.firmware_model_review()
    require(bundle['status']=='SPARE_DDR1066_CH0_FIRMWARE_HOST_MODEL_REVIEWED_IMAGE_BOUND',
            'DDR1066 CH0 firmware has not passed its model review and image binding')
    require(bundle['required_build_id']=='c0182863' and
            bundle['required_bitstream_sha256']==profile.bitstream_sha256 and
            bundle['firmware_id']=='c0172168' and bundle['startup_firmware_id']=='c0172160',
            'DDR1066 firmware/image identities differ')
    require(review['status']=='PASS_SPARE_CH0_FIRMWARE_HOST_EQUIVALENCE' and
            review['binary_sha256']==bundle['binary_sha256']==sha(firmware/'selfcal.bin') and
            review['core_config_sha256']==sha(profile.core/'sdram_init_ch0.py') and
            bundle['model_review_sha256']==profile.firmware_model_review_digest(),
            'Missing matching DDR1066 firmware equivalence evidence')
    require(0<(firmware/'selfcal.bin').stat().st_size<=16384,'Invalid CH0 firmware size')
    phy=phy_config(profile.core/'sdram_init_ch0.py')
    require(phy['channels']==[0] and phy['modules']==8 and phy['databits']==64 and
            phy['dfi_databits']==128 and phy['cl']==7 and phy['cwl']==6 and
            abs(phy['sys_hz']-400e6/3)<.01,'Wrong DDR1066 CH0 PHY configuration')
    matched={name:profile.core_file_digest(name) for name in
             ('otpu_litedram.v','csr.csv','sdram_init.py','sdram_init_ch0.py','otpu_litedram_mem.init')}
    require(bundle['matched_core_files']==matched,'DDR1066 calibration core binding changed')
    core_profile=profile.calibration_core_profile()
    adapter=profile.model_review('adapter-model')
    require(bundle['adapter_model_sha256']==core_profile['adapter_model_sha256']==adapter['source_sha256'] and
            adapter['status']=='PASS_SHARED_PIPELINED_NATIVE_CREDITS_ORDERING_AND_EXCLUSIVE_RMW',
            'DDR1066 adapter evidence binding changed')
    for name,status in (('bridge-model.json','PASS_ORIGINAL_BRIDGE_DEFECT_REPRODUCED_SHARED_PIPELINE_CORRECTION_VERIFIED'),
                        ('controller-model.json','PASS_SHARED_PIPELINE_REAL_LITEDRAM_CONTROLLER_BRIDGE_REGRESSION')):
        evidence=profile.model_review(name)
        require(bundle[name.replace('-','_').replace('.json','_sha256')]==evidence['source_sha256'] and
                evidence['status']==status,'DDR1066 integration evidence differs: '+name)
    return phy,dict(required_build_id='c0182863',required_bitstream_sha256=profile.bitstream_sha256,
        full_package_manifest_sha256=profile.original_image_digest(),firmware_id='c0172168',
        firmware_sha256=sha(firmware/'selfcal.bin'),matched_core_files=matched,
        firmware_model_review_sha256=profile.firmware_model_review_digest(),
        note='Exact DDR1066 package and model-reviewed firmware; physical calibration still required',
        **(dict(runtime_manifest_sha256=profile.manifest_sha256) if profile.runtime_only else {}))


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
    require(state['startup_mailbox'][:2]==[selfcal.MB_MAGIC_V,0xc0172160],'Unexpected startup firmware identity')
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
    require(mailbox[:2]==[selfcal.MB_MAGIC_V,0xc0172168],'Unexpected CH0 firmware identity')
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
    p.add_argument('--xvc-host',default='localhost');p.add_argument('--xvc-port',type=int,default=3721)
    p.add_argument('--transport',choices=('xdma','chestnut','jtag'),default='xdma');p.add_argument('--dev',default='/dev/xdma0')
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
        paths=[Path(__file__),ROOT/'opentpu/host/spare_c0182863.py',ROOT/'opentpu/host/selfcal.py',ROOT/'opentpu/host/ddrcal.py']
        state['source_hashes']={str(f.resolve()):sha(f) for f in paths};save()
        if a.preflight_only:state['status']='SPARE_PCIE_CALIBRATION_PREFLIGHT_PASS';return
        state['hardware_access_attempted']=True;save()
        transport=SpareJtagTransport(profile,a.xvc_host,a.xvc_port) if a.transport=='jtag' else SpareChestnutTransport(profile) if a.transport=='chestnut' else SpareXdmaTransport(profile,a.dev)
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
