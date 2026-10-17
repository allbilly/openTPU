#!/usr/bin/env python3
"""Bind reviewed eight-lane firmware to c0172300 and calibrate CH0 over PCIe.

Requires the pinned runtime files and a fresh configuration from flash or SRAM. No
FPGA programming or flash writes. Calibration overwrites disposable CH0 data;
whole-memory initialization and native qualification must follow separately.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import runpy
import sys

ROOT=Path(__file__).resolve().parents[1];sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
from opentpu.host import selfcal,regs as R
from opentpu.host.spare_c0172300 import (SparePcieProfile,SpareXdmaTransport,
                                       SpareChestnutTransport,REVIEWED_MANIFEST_SHA256)
from opentpu.host.dual_pcie import require,digest as sha


def bind_firmware(profile,firmware):
    require(profile.runtime_only,'Use runtime/c0172300 with this Mac calibration helper')
    require(firmware.resolve()==profile.package/'calibration',
            'Use the calibration firmware in this exact pipeline package')
    bundle=json.loads((firmware/'pipeline-binding.json').read_text())
    require(bundle['status']=='SPARE_PIPELINED_CH0_REFERENCE_FIRMWARE_IMAGE_BOUND' and
            bundle['required_build_id']=='c0172300' and
            bundle['required_bitstream_sha256']==profile.bitstream_sha256,
            'Pipeline firmware belongs to another image')
    require(bundle['firmware_id']=='c0172068' and bundle['startup_firmware_id']=='c0172060' and
            bundle['binary_sha256']==sha(firmware/'selfcal.bin') and
            bundle['firmware_model_sha256']==sha(firmware/'host-model-review.json') and
            bundle['reference_firmware_sha256']==sha(firmware/'bundle.json'),
            'Pipeline calibration reference binding changed')
    matched={name:profile.core_file_digest(name) for name in
             ('otpu_litedram.v','csr.csv','sdram_init.py','sdram_init_ch0.py','otpu_litedram_mem.init')}
    require(bundle['matched_core_files']==matched,'Pipeline calibration core binding changed')
    # The small pinned export records model review results and netlist hashes.
    # It does not ship or revalidate the omitted generated netlist/model inputs.
    model=profile.runtime_metadata['reviews']['adapter-model']
    require(bundle['adapter_model_sha256']==model['source_sha256'],'Adapter review binding differs')
    require(model['status']=='PASS_SPARE_PIPELINED_NATIVE_TWO_PORT_READS_AND_EXCLUSIVE_RMW' and
            model['report_count']==8,'Pipeline protocol review incomplete')
    firmware_model=json.loads((firmware/'host-model-review.json').read_text())
    require(firmware_model['status']=='PASS_SPARE_CH0_FIRMWARE_HOST_EQUIVALENCE' and
            firmware_model['binary_sha256']==bundle['binary_sha256'] and
            len(firmware_model['reports'])==3 and
            all(row['exact_reference_trace_match'] for row in firmware_model['reports']),
            'Firmware host equivalence review incomplete')
    phy=runpy.run_path(str(profile.core/'sdram_init_ch0.py'))['phy']
    require(phy['channels']==[0] and phy['modules']==8 and phy['databits']==64 and
            phy['dfi_databits']==128 and phy['cl']==6 and phy['cwl']==5 and
            abs(phy['sys_hz']-100e6)<.01,'Wrong DDR800 eight-lane calibration configuration')
    return phy,dict(required_build_id='c0172300',required_bitstream_sha256=profile.bitstream_sha256,
        full_package_manifest_sha256=REVIEWED_MANIFEST_SHA256,
        runtime_manifest_sha256=profile.manifest_sha256,firmware_id='c0172068',
        firmware_sha256=sha(firmware/'selfcal.bin'),matched_core_files=matched,
        reference_package_sha256=bundle['reference_package_sha256'],
        reference_firmware_sha256=sha(firmware/'bundle.json'),
        pipeline_binding_sha256=sha(firmware/'pipeline-binding.json'),
        omitted_core_files=['otpu_litedram.v'],
        note='Small runtime files checked locally; omitted netlist bound by the pinned image review. Live identity, physical calibration and inference remain required.')


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
    for name in ('package','firmware','out'):p.add_argument('--'+name,type=Path,required=True)
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
        phy,binding=bind_firmware(profile,a.firmware);state['binding']=binding
        paths=[Path(__file__),ROOT/'opentpu/host/spare_c0172300.py',ROOT/'opentpu/host/selfcal.py',ROOT/'opentpu/host/ddrcal.py']
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
