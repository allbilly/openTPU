#!/usr/bin/env python3
"""Wait for the full CH1 JTAG image, load SRAM, and run physical LFM2.

Native Vivado cable driver only. No PCIe, fake transport or flash operations.
"""
import argparse
from collections import deque
from datetime import datetime,timezone
import importlib.util
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'tools'))
from fedora_run_vivado_native_jtag import NativeLink,TCL,VIVADO
from fedora_program_ch1_sram import describe,stop_group
from fedora_run_ch1_lfm2 import check_marker,main as run_model
from opentpu.host.jtag import JtagTransport,MAGIC
from opentpu.host import regs as R


class LfmNativeLink(NativeLink):
    """Advance the return toggle before Capture-DR; normal polling remains valid."""
    def scan(self,value,bits=640,ir=False):
        result=super().scan(value,bits,ir)
        if not ir and bits==640 and value>>572==MAGIC:
            self.shift(16,0,0)
        return result


class CalibratedJtagTransport(JtagTransport):
    """Keep the host from retraining CH0 if the recovery ready flags disappear."""
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.guard_calibration=False

    def arm_calibration_guard(self):
        self.guard_calibration=True

    def reg_read(self,off):
        value=super().reg_read(off)
        ready=R.ST_CALIB0|R.ST_CALIB1
        if self.guard_calibration and off==R.R_STATUS and value&ready!=ready:
            raise IOError(f'CH1 readiness was lost (STATUS={value:#x}); refusing host recalibration of physical CH0')
        return value


def require(ok,message):
    if not ok:raise ValueError(message)


def review_cdc(text):
    reviewed=[]
    for line in text.splitlines():
        if not re.match(r'^\s*\d+\s+CDC-\d+\s+Critical\s',line):continue
        fields=re.split(r'\s{2,}',line.strip())
        require(len(fields)==8,'Unexpected CDC row format')
        _,kind,_,_,depth,exception,source,target=fields
        reset=(kind=='CDC-10' and int(depth)>=8 and source=='u_ld/reset_storage_reg[0]/C'
               and target in ('u_ld/FDCE/D','u_ld/FDCE_8/D') and exception=='False Path')
        payload=(kind in ('CDC-1','CDC-4','CDC-15') and
                 ((source.startswith('u_mailbox/held_reg') and target.startswith('u_mailbox/req_reg')) or
                  (source.startswith('u_mailbox/response_reg') and target.startswith('u_mailbox/response_tck_reg'))))
        require(reset or payload,'Unreviewed critical CDC: '+line.strip())
        reviewed.append(dict(fields=fields,reason='Eight-stage clock-reset chain' if reset else
            'Single outstanding mailbox request; held payload and three-stage toggle; explicit delay/skew bounds'))
    return reviewed


def qualify(build,core,ecc,out):
    m=json.loads((build/'manifest.json').read_text())
    require(m['status']=='CH1_JTAG_BITSTREAM_BUILD_PASS_IMAGE_REVIEW_PENDING' and m['build_exit']==0,'JTAG build incomplete')
    require(m['top']=='otpu_fpga_top_openxc7_jtag' and m['physical_user_channels']==[1] and
            m['logical_capacity_bytes']==1<<31 and Path(m['core'])==core,'Wrong JTAG recovery image')
    for item in m['source_files']+list(m['outputs'].values())+[m['reference_pins'],m['helper']]:
        require(describe(item['path'])==item,'Build input/output changed: '+item['path'])
    require((ecc/'four-port-ecc.exit').read_text().strip()=='0','Full ECC test failed')
    log=(ecc/'four-port-ecc.log').read_text()
    require(log.splitlines()[-1]=='PASS' and re.search(r'^1500 cycles,',log,re.M),'Full 1500-cycle ECC pass absent')
    gm=json.loads((core.parent/'manifest.json').read_text())
    for name in ('ecc_ports.py','ecc_ports_check.py'):
        witness=next(x for x in gm['source_witness'] if Path(x['path']).name==name)
        require(describe(witness['path'])==witness and describe(ecc/'generator'/name)['sha256']==witness['sha256'],'ECC source differs')
    skew=re.findall(r'^Slack \((MET|VIOLATED)\)\s*:\s*([-+0-9.]+)ns',(build/'reports/bus-skew.rpt').read_text(),re.M)
    require(len(skew)==30 and all(k=='MET' and float(v)>=0 for k,v in skew),'All 30 bus-skew constraints must pass')
    cdc=review_cdc((build/'reports/cdc.rpt').read_text())
    timing=(build/'reports/timing.rpt').read_text()
    coverage=dict((k,int(v)) for k,v in re.findall(r'^\d+\. checking (\w+) \((\d+)\)$',timing,re.M))
    require(all(coverage.get(k)==0 for k in ('no_clock','unconstrained_internal_endpoints','multiple_clock','generated_clocks','loops','latch_loops')),'Incomplete internal timing coverage')
    bit=Path(m['outputs']['otpu-ch1-jtag.bit']['path'])
    packet_checker=ROOT.parent/'bonetto-soc/scripts/fedora-check-vivado-bitstream.py'
    spec=importlib.util.spec_from_file_location('ch1_jtag_packets',packet_checker);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    packet=module.check(bit,m['outputs']['otpu-ch1-jtag.bit']['sha256']);require(packet['status']=='PASS','Packet check failed')
    (out/'packets.json').write_text(json.dumps(packet,indent=2)+'\n')
    checker=ROOT/'build/fedora-openxc7/bitstream-crc-qualification-20261013T152000Z/check-crc'
    require(describe(checker)['sha256']=='047b5e0dc5c29193e2a1311eef1d09d44d8b08d37844fb6a771b1f9b76057802','CRC checker changed')
    result=subprocess.run([str(checker),str(bit)],capture_output=True,text=True,timeout=60);crc=json.loads(result.stdout)
    require(result.returncode==0 and crc['status']=='ALL_PRESENT_CRC_CHECKPOINTS_MATCH' and crc['crc_checkpoints']==2,'CRC failed')
    q=dict(status='CH1_JTAG_IMAGE_SOURCE_ROUTE_TIMING_DRC_PINS_CRC_CDC_PASS_HARDWARE_PENDING',bitstream=describe(bit),
           bus_skew_constraints=30,critical_cdc_review=cdc,timing_coverage=coverage,crc=crc,hardware_accessed=False,flash_written=False)
    (out/'qualification.json').write_text(json.dumps(q,indent=2)+'\n');return bit,q


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',required=True,type=Path);ap.add_argument('--core',required=True,type=Path)
    ap.add_argument('--ecc-preparation',required=True,type=Path);ap.add_argument('--out',required=True,type=Path)
    ap.add_argument('--wait-unit',required=True)
    a=ap.parse_args();build=a.build.resolve();core=a.core.resolve();ecc=a.ecc_preparation.resolve();out=a.out.resolve()
    require(not out.exists(),'Choose a fresh run directory');out.mkdir(parents=True)
    r=dict(status='WAITING_FOR_CH1_JTAG_IMAGE',started_utc=datetime.now(timezone.utc).isoformat(),hardware_accessed=False,
           physical_model_verified=False,flash_written=False,programming='NOT_RUN',write_bytes=0,read_bytes=0,transfers=[],last_commands=[])
    lock=threading.RLock();recent=deque(maxlen=64);hw=bridge=None
    def save():
        with lock:
            tmp=out/'manifest.json.tmp';tmp.write_text(json.dumps(r,indent=2)+'\n');tmp.replace(out/'manifest.json')
    class Transport(CalibratedJtagTransport):
        def __init__(self,*,calibration_data):
            super().__init__(host='127.0.0.1',port=3741,link=LfmNativeLink(),calibration_data=calibration_data)
        def _command(self,opcode,addr,data=0,strobes=15):
            row=dict(opcode=opcode,address=hex(addr),started_utc=datetime.now(timezone.utc).isoformat())
            recent.append(row)
            try:return super()._command(opcode,addr,data,strobes)
            except Exception:
                with lock:r['last_commands']=list(recent);save()
                raise
        def mem_write(self,ch,off,data):
            import numpy as np
            data=np.ascontiguousarray(data,np.uint8).reshape(-1)
            for pos in range(0,len(data),65536):
                chunk=data[pos:pos+65536];start=time.monotonic();super().mem_write(ch,off+pos,chunk)
                with lock:
                    r['write_bytes']+=len(chunk);r['last_transfer']=dict(direction='write',virtual_channel=ch,offset=off+pos,bytes=len(chunk),seconds=time.monotonic()-start)
                    save()
        def mem_read(self,ch,off,n,out=None):
            result=super().mem_read(ch,off,n,out)
            with lock:r['read_bytes']+=n;save()
            return result
    try:
        save();invocation=None
        while True:
            m=json.loads((build/'manifest.json').read_text());require(m['status']!='FAIL','JTAG build failed: '+str(m.get('error')))
            if m['status']=='CH1_JTAG_BITSTREAM_BUILD_PASS_IMAGE_REVIEW_PENDING' and (ecc/'four-port-ecc.exit').exists():break
            props=dict(x.split('=',1) for x in subprocess.check_output(['systemctl','--user','show',a.wait_unit,'-p','MainPID','-p','InvocationID','-p','ExecMainStatus','-p','Result'],text=True).splitlines())
            require(props['InvocationID'],'Expected build service is missing')
            if invocation is None:invocation=props['InvocationID']
            require(props['InvocationID']==invocation and props['ExecMainStatus']=='0' and props['Result']=='success','Build service changed or failed')
            if m['status']!='CH1_JTAG_BITSTREAM_BUILD_PASS_IMAGE_REVIEW_PENDING':
                cmd=Path('/proc')/props['MainPID']/'cmdline';require(props['MainPID']!='0' and cmd.exists() and str(build).encode() in cmd.read_bytes(),'Expected build process is no longer live')
            r.update(build_service=props,observed_utc=datetime.now(timezone.utc).isoformat());save();time.sleep(5)
        r['status']='CH1_JTAG_IMAGE_QUALIFICATION_RUNNING';save();bit,q=qualify(build,core,ecc,out);r['qualification']=q;save()
        for name in ('hw_server','openFPGALoader','xsdb','fxload'):
            require(subprocess.run(['pgrep','-x',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL).returncode==1,'Cable owner: '+name)
        for port in (3122,3741):
            with socket.socket() as sock:require(sock.connect_ex(('127.0.0.1',port))!=0,'Native port already owned')
        usb=subprocess.check_output(['lsusb'],text=True);cables=[x for x in usb.splitlines() if 'ID 03fd:' in x]
        require(len(cables)==1,'Exactly one DLC10 cable is required');r['usb_at_start']=usb
        (out/'bridge.tcl').write_text(TCL)
        with (out/'hw-server.log').open('w') as log:hw=subprocess.Popen([str(VIVADO/'hw_server'),'-s','tcp::3122'],stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        env=dict(os.environ,OTPU_NATIVE_READY=str(out/'native-ready.txt'),OTPU_NATIVE_BIT=str(bit),OTPU_NATIVE_PROGRAM_STATUS=str(out/'native-program-status.txt'))
        with (out/'vivado.log').open('w') as log:bridge=subprocess.Popen([str(VIVADO/'vivado'),'-mode','batch','-nojournal','-nolog','-source',str(out/'bridge.tcl')],cwd=out,env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        r.update(status='NATIVE_CH1_JTAG_SRAM_PROGRAMMING_RUNNING',hardware_accessed=True,hw_server_pid=hw.pid,vivado_pid=bridge.pid);save()
        deadline=time.monotonic()+300
        while not (out/'native-ready.txt').exists():
            require(hw.poll() is None and bridge.poll() is None,'Native load failed; see vivado.log')
            require(time.monotonic()<deadline,'Native programming timed out');time.sleep(.5)
        require((out/'native-program-status.txt').read_text().strip()=='INIT=1 DONE=1','Fresh SRAM completion absent')
        t=Transport(calibration_data=core)
        try:check_marker(t)
        finally:t.close()
        r.update(programming='PASS_NATIVE_CH1_SRAM_INIT_DONE_AND_MAILBOX',status='PHYSICAL_MATMUL_AND_LFM2_RUNNING');save()
        sys.argv=[str(ROOT/'tools/fedora_run_ch1_lfm2.py'),'--core',str(core),'--out',str(out/'model'),'--model','lfm2']
        code=run_model(open_transport=Transport);r['model_exit']=code
        result=json.loads((out/'model/manifest.json').read_text());r['physical_result']=result
        require(code==0 and result['status']=='PASS_PHYSICAL_CH1_RECOVERY_MATMUL_AND_LFM2','Physical CH1 matmul/LFM2 failed; see model/manifest.json')
        r.update(status='PASS_PHYSICAL_JTAG_CH1_MATMUL_AND_LFM2',physical_model_verified=True);return 0
    except Exception as e:
        r.update(status='FAIL',error=repr(e));print(r['error'],flush=True);return 1
    finally:
        if bridge is not None and bridge.poll() is None:
            try:
                link=NativeLink(timeout=5);link.command('QUIT');link.close();bridge.wait(timeout=15)
            except (OSError,subprocess.TimeoutExpired):pass
        r['vivado_exit']=stop_group(bridge);r['hw_server_exit']=stop_group(hw)
        r['finished_utc']=datetime.now(timezone.utc).isoformat();save()


if __name__=='__main__':raise SystemExit(main())
