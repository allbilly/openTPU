#!/usr/bin/env python3
"""Test physical DDR800 CH1 while warm; never access CH0 memory or program flash."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from fedora_run_vivado_native_jtag import NativeLink,TCL,VIVADO
from fedora_vivado_ddr800_qualify import CORE,require,describe


def main():
    from opentpu.host import jtag,memcal,ddrcal,regs as R
    from opentpu.host.board import Board
    import numpy as np
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--seconds',type=int,default=90)
    args=ap.parse_args()
    require(args.seconds>=30,'Soak must last at least 30 seconds')
    out=args.out.resolve();require(not out.exists(),'Choose a new output directory')
    out.mkdir(parents=True)
    record=dict(status='STARTING',physical=True,physical_memory_channels=[1],
                compute_test='NOT_RUN',programming='NOT_RUN',flash_written=False,
                started_utc=datetime.now(timezone.utc).isoformat(),passes=[],samples=[])
    hw=bridge=t=board=None
    def save():
        p=out/'manifest.json.tmp';p.write_text(json.dumps(record,indent=2)+'\n');p.replace(out/'manifest.json')
    try:
        for name in ['hw_server','openFPGALoader','xsdb','fxload']:
            require(subprocess.run(['pgrep','-x',name],stdout=subprocess.DEVNULL).returncode!=0,
                    'Active cable owner: '+name)
        usb=subprocess.check_output(['lsusb'],text=True)
        require(sum('ID 03fd:' in l for l in usb.splitlines())==1,'Require a single adapter')
        record['inputs']=[describe(Path(__file__)),describe(CORE/'csr.csv'),describe(CORE/'sdram_init.py')]
        (out/'bridge.tcl').write_text(TCL)
        with (out/'hw-server.log').open('w') as log:
            hw=subprocess.Popen([str(VIVADO/'hw_server'),'-s','tcp::3122'],stdout=log,stderr=subprocess.STDOUT)
        env=dict(os.environ,OTPU_NATIVE_READY=str(out/'native-ready.txt'))
        # This probe is SRAM-preserving even if the parent shell carried old programming variables.
        env.pop('OTPU_NATIVE_BIT',None);env.pop('OTPU_NATIVE_PROGRAM_STATUS',None)
        with (out/'vivado.log').open('w') as log:
            bridge=subprocess.Popen([str(VIVADO/'vivado'),'-mode','batch','-nojournal','-nolog',
                                     '-source',str(out/'bridge.tcl')],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT)
        record.update(status='NATIVE_CHAIN_CHECK_RUNNING',hw_server_pid=hw.pid,vivado_pid=bridge.pid);save()
        deadline=time.monotonic()+120
        while not (out/'native-ready.txt').exists():
            require(hw.poll() is None and bridge.poll() is None,'Native bridge failed')
            require(time.monotonic()<deadline,'Native chain timeout');time.sleep(.5)
        t=jtag.JtagTransport(link=NativeLink(),calibration_data=CORE)
        board=Board(t,check=False)
        info=board.info();record['identity']=info
        require(t.reg_read(R.R_ID)==R.ID_OTPU and
                (info['D'],info['MCOLS'],info['LANES'],info['act_rows'],info['core_khz'],info['ddr_mts'])
                ==(128,4,8,4,100000,800),'Expected full DDR800 image')
        def idle():
            state=t.reg_read(R.R_STATUS)
            require(state&R.ST_CALIB1 and not state&(R.ST_RUN|R.ST_LOADING),
                    'Physical CH1 must be calibrated and compute idle')
        idle()
        csr=memcal.csr(t);ch=ddrcal.Chan(csr,1)
        record['ecc_before']={n:ch.r(n) for n in ['ecc_enable','ecc_sec_errors','ecc_ded_errors']}
        require(record['ecc_before']['ecc_enable']==1,'CH1 ECC must be enabled')
        record['status']='FULL_PHYSICAL_CH1_WARM_SOAK_RUNNING';save()
        start=time.monotonic();rounds=0
        with (out/'memory.log').open('w') as log:
            while rounds==0 or time.monotonic()-start<args.seconds:
                idle()
                sample=dict(seconds=time.monotonic()-start,temp_c=t.read_die_temperature())
                record['samples'].append(sample)
                for mode,seed in [(0,0x0123456789abcdef),(2,0x9e3779b97f4a7c15),(0,0)]:
                    for read in (False,True):
                        r=ddrcal.bist(ch,1<<25,mode|int(read),seed,100000000,timeout=120)
                        row=dict(physical_channel=1,mode=mode|int(read),seed=hex(seed),**r)
                        record['passes'].append(row);log.write(json.dumps(row)+'\n');log.flush();save()
                        require(r['beats']==1<<25 and not r.get('errors',0) and
                                not any(r.get('lanes',[])),'Physical CH1 BIST failed')
                rounds+=1
        record['soak_seconds']=time.monotonic()-start
        # The final raw zero pass leaves valid zero ECC. Verify normal ECC/DMA accesses next.
        rng=np.random.default_rng(1)
        for off in [0,1<<30,(1<<31)-8192]:
            data=rng.integers(0,256,8192,dtype=np.uint8)
            t.mem_write(1,off,data)
            got=t.mem_read(1,off,len(data))
            require(np.array_equal(got,data),'Physical CH1 normal-port data differs')
        record['ecc_after']={n:ch.r(n) for n in ['ecc_enable','ecc_sec_errors','ecc_ded_errors']}
        require(record['ecc_after']['ecc_sec_errors']==0 and record['ecc_after']['ecc_ded_errors']==0,
                'Physical CH1 ECC counters are nonzero')
        record.update(status='PASS_PHYSICAL_CH1_WARM_FULL_CAPACITY_AND_NORMAL_PORT',
                      final_temp_c=t.read_die_temperature(),normal_port_bytes_compared=3*8192)
        return 0
    except Exception as error:
        record.update(status='FAIL',error=repr(error));print(record['error'],flush=True);return 1
    finally:
        if board is not None:board.close()
        if t is not None:t.close()
        if bridge is not None:
            if bridge.poll() is None:
                try:
                    link=NativeLink(timeout=5);link.command('QUIT');link.close();bridge.wait(timeout=15)
                except (OSError,subprocess.TimeoutExpired):
                    bridge.terminate()
                    try:bridge.wait(timeout=5)
                    except subprocess.TimeoutExpired:bridge.kill();bridge.wait()
            record['vivado_exit']=bridge.returncode
        if hw is not None:
            hw.terminate()
            try:hw.wait(timeout=10)
            except subprocess.TimeoutExpired:hw.kill();hw.wait()
            record['hw_server_exit']=hw.returncode
        record['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':
    raise SystemExit(main())
