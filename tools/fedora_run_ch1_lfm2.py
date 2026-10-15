#!/usr/bin/env python3
"""Physical CH1-only PCIe recovery: warm memory, full-compute MM, then LFM2.

Requires recovery marker 0x08000102 at BAR0+0x5c and matching DDR800 tables.
Never programs FPGA SRAM or flash. Logical capacity is 2 GiB, not 4 GiB.
"""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'tools'))
from fedora_matmul_check import matmul_check

VIRTUAL_BYTES=1<<30
LOGICAL_BYTES=1<<31
MEMORY_PROFILE=0x08000102


def check_range(ch,off,n):
    if ch not in (0,1) or off<0 or n<0 or off+n>VIRTUAL_BYTES:
        raise ValueError('CH1 recovery permits 1 GiB per virtual channel, 2 GiB total')


def check_marker(t):
    value=t.reg_read(0x5c)
    if value!=MEMORY_PROFILE:
        raise ValueError(f'CH1 recovery image required: memory profile {value:#x}')


def main(open_transport=None):
    import numpy as np
    from opentpu.host import memcal,ddrcal,selfcal,regs as R
    from opentpu.host.board import Board,XdmaTransport,device_config
    from opentpu.host.checks import model_check
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dev',default='/dev/xdma0')
    ap.add_argument('--core',required=True,type=Path)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--model',default='lfm2')
    ap.add_argument('--soak-seconds',type=int,default=90)
    ap.add_argument('--preflight-only',action='store_true')
    a=ap.parse_args()
    if a.soak_seconds<30:ap.error('Warm soak must last at least 30 seconds')
    core=a.core.resolve();p=json.loads((core/'openxc7-profile.json').read_text())
    assert p['physical_user_channels']==[1] and p['usable_logical_bytes']==LOGICAL_BYTES
    assert p['calibration_mask']==2 and p['parameters']==dict(CORE_KHZ=100000,DDR_MTS=800)
    import hashlib
    for item in p['files'].values():
        f=core/item['name']
        assert f.stat().st_size==item['bytes'] and hashlib.sha256(f.read_bytes()).hexdigest()==item['sha256'],str(f)
    out=a.out.resolve()
    if out.exists():ap.error('Choose a fresh result directory')
    out.mkdir(parents=True)
    r=dict(status='STARTING',physical=True,flash_written=False,programming='NOT_RUN',
           physical_memory_channels=[1],logical_capacity_bytes=LOGICAL_BYTES,
           started_utc=datetime.now(timezone.utc).isoformat(),passes=[],temperature_samples=[],model_checks=[])
    def save():
        f=out/'manifest.json.tmp';f.write_text(json.dumps(r,indent=2)+'\n');f.replace(out/'manifest.json')
    def require(ok,message):
        if not ok:raise ValueError(message)
    base_transport=XdmaTransport if open_transport is None else open_transport
    class Transport(base_transport):
        def __init__(self):
            if open_transport is None:
                super().__init__(a.dev)
            else:
                super().__init__(calibration_data=core)
            self.calibration_data=core
            try:check_marker(self)
            except Exception:self.close();raise
        def mem_write(self,ch,off,data):
            check_range(ch,off,memoryview(data).nbytes)
            return super().mem_write(ch,off,data)
        def mem_read(self,ch,off,n,out=None):
            check_range(ch,off,n)
            return super().mem_read(ch,off,n,out)
        def scrub(self):
            c=ddrcal.Chan(memcal.csr(self),1)
            for mode in (0,1):
                res=ddrcal.bist(c,1<<25,mode,0,100000000,timeout=120)
                require(res['beats']==1<<25 and not res.get('errors',0),'CH1 zero scrub failed')
        def record_model_check(self,result):
            r['model_checks'].append(dict(result,physical=True,physical_memory_channels=[1]));save()
        def record_model_token(self,token):
            r.setdefault('actual_partial_token_ids',[]).append(int(token));save()
            print('PHYSICAL_LFM2_TOKEN '+str(int(token)),flush=True)
    t=board=None
    try:
        save()
        from importlib.metadata import version
        from opentpu.llm import model_dir
        model_path=model_dir(a.model).resolve()
        require(json.loads((model_path/'config.json').read_text()).get('model_type')
                in ('lfm2','lfm2_moe'),'An LFM2 checkpoint is required')
        r['python_runtime']=dict(executable=sys.executable,prefix=sys.prefix,
            packages={name:version(name) for name in ('numpy','torch','transformers','safetensors')})
        r['model_inputs']=[dict(name=name,bytes=(model_path/name).stat().st_size,
            sha256=hashlib.sha256((model_path/name).read_bytes()).hexdigest()) for name in
            ('config.json','tokenizer.json','tokenizer_config.json','model.safetensors')]
        save()
        if open_transport is None:
            nodes=[d for d in Path('/sys/bus/pci/devices').iterdir()
                   if (d/'xdma'/(Path(a.dev).name+'_user')).exists()]
            require(len(nodes)==1,'XDMA device must map to exactly one PCIe card')
            pci={k:(nodes[0]/k).read_text().strip() for k in
                 ['vendor','device','subsystem_vendor','subsystem_device','class']}
            require(pci==dict(vendor='0x10ee',device='0x7028',subsystem_vendor='0x10ee',
                             subsystem_device='0x4f54',**{'class':'0x120000'}),'Unexpected PCIe identity')
            r['pcie']=dict(bdf=nodes[0].name,**pci)
        else:
            r['transport']='Physical native Vivado USER2 JTAG'
        t=Transport();board=Board(t,check=True,calibrate=False);info=board.info();r['identity']=info
        require((info['D'],info['MCOLS'],info['LANES'],info['act_rows'],info['core_khz'],info['ddr_mts'])
                ==(128,4,8,4,100000,800),'Full recovery compute profile differs')
        if a.preflight_only:
            r['status']='PASS_RECOVERY_IDENTITY_ONLY_MODEL_NOT_RUN';return 0
        state=t.reg_read(R.R_STATUS)
        require(not state&(R.ST_RUN|R.ST_LOADING),'Recovery tests require idle compute')
        csr=memcal.csr(t);require(selfcal.present(csr),'Calibration CPU absent')
        selfcal.hold(csr);csr.w('selfcal_config',2|(1<<8));selfcal.release(csr)
        r['status']='CH1_CPU_CALIBRATION_RUNNING';save()
        state=selfcal.wait(csr,timeout=120,poll=.5)
        result=selfcal.result(csr,core/'sdram_init.py');r['calibration']=result;save()
        require(state['done'] and result.get(1,{}).get('state')=='ok' and
                result[1]['traffic_checked'],'Physical CH1 calibration failed')
        require(t.reg_read(R.R_STATUS)&96==96,'Both virtual channels must report CH1 ready')
        if hasattr(t,'arm_calibration_guard'):t.arm_calibration_guard()
        ch=ddrcal.Chan(csr,1)
        r['ecc_before']={k:ch.r(k) for k in ('ecc_enable','ecc_sec_errors','ecc_ded_errors')}
        require(r['ecc_before']['ecc_enable']==1 and r['ecc_before']['ecc_sec_errors']==0 and
                r['ecc_before']['ecc_ded_errors']==0,'Physical CH1 ECC must be enabled and clean')
        start=time.monotonic();r['status']='CH1_WARM_MEMORY_SOAK_RUNNING';save()
        while time.monotonic()-start<a.soak_seconds:
            temperature=t.read_die_temperature() if hasattr(t,'read_die_temperature') else board.info()['temp_c']
            r['temperature_samples'].append(dict(seconds=time.monotonic()-start,temp_c=temperature))
            for mode,seed in [(0,0x0123456789abcdef),(2,0x9e3779b97f4a7c15),(0,0)]:
                for read in (False,True):
                    v=ddrcal.bist(ch,1<<25,mode|int(read),seed,100000000,timeout=120)
                    r['passes'].append(dict(physical_channel=1,mode=mode|int(read),**v));save()
                    require(v['beats']==1<<25 and not v.get('errors',0) and
                            not any(v.get('lanes',[])),'Physical CH1 warm BIST failed')
        r['soak_seconds']=time.monotonic()-start;board.scrub(force=True)
        r['status']='PHYSICAL_MATMUL_RUNNING';save()
        r['matmul']=matmul_check(board);save()
        require(r['matmul']['exact_match'] and r['matmul']['actual_instructions']==r['matmul']['expected_instructions'],
                'Physical matmul differs from ISA')
        r['status']='PHYSICAL_LFM2_RUNNING';save()
        cfg=device_config(info,DRAM_BYTES=LOGICAL_BYTES)
        ok,msg=model_check(t,cfg,a.model,8,False,wformat='int8');r['model_message']=msg;save()
        require(ok and r['model_checks'] and all(x['exact_match'] and x['actual_token_ids']
                and x['actual_token_ids']==x['expected_token_ids'] and 'Paris' in x['text']
                for x in r['model_checks']),'Exact physical LFM2 answer absent')
        r['ecc_after']={k:ch.r(k) for k in ('ecc_enable','ecc_sec_errors','ecc_ded_errors')};save()
        require(r['ecc_after']['ecc_enable']==1 and r['ecc_after']['ecc_sec_errors']==0 and
                r['ecc_after']['ecc_ded_errors']==0,'CH1 ECC errors during compute')
        r['status']='PASS_PHYSICAL_CH1_RECOVERY_MATMUL_AND_LFM2';return 0
    except Exception as e:
        r.update(status='FAIL',error=repr(e));print(r['error'],flush=True);return 1
    finally:
        if board is not None:board.close()
        if t is not None:t.close()
        r['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':raise SystemExit(main())
