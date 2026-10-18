#!/usr/bin/env python3
"""Measure c0182863 device read bandwidth after the LFM integration run.

Overwrites program/output memory. Compares the last 16 KiB only. No FPGA
programming, calibration or initialization. USB wall time is reported separately.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import statistics
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'tools')]
import numpy as np
from opentpu import isa as I
from opentpu.host import regs as R
from opentpu.host.program_verify import ProgramReadbackBoard as Board
from opentpu.host.dual_pcie import require,digest
from opentpu.host.spare_c0182863 import SparePcieProfile,SpareChestnutTransport,SpareXdmaTransport,SpareJtagTransport
from spare_runtime_c0182863 import check_calibration_receipt,calibration_snapshot
from run_lfm_spare_c0182863 import native_read_program,PROGRAM_AT,SWEEP_OUTPUT,SWEEP_CHUNK


def payload_digest(array):
    return hashlib.sha256(memoryview(array).cast('B')).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package',type=Path,required=True)
    parser.add_argument('--calibration-receipt',type=Path,required=True)
    parser.add_argument('--transport',choices=('chestnut','xdma','jtag'),default='chestnut')
    parser.add_argument('--dev',default='/dev/xdma0')
    parser.add_argument('--xvc-host',default='localhost')
    parser.add_argument('--xvc-port',type=int,default=3721)
    parser.add_argument('--span',type=int,default=64<<20)
    parser.add_argument('--repeats',type=int,choices=range(1,11),default=3)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args()
    if not (0<args.span<=1<<32 and args.span%SWEEP_CHUNK==0):
        parser.error('--span must be a positive 16 KiB multiple, at most 4 GiB')
    args.out.mkdir(parents=True,exist_ok=False)
    transport=board=None
    state=dict(status='CHECKING',hardware_accessed=False,programming_performed=False,
        flash_written=False,calibration_requested=False,memory_initialization_requested=False,
        build_id='c0182863',span=args.span,runs=[],
        scope='Device native-read counters and final-chunk comparison; not full-range qualification')
    def save():
        state['utc']=datetime.now(timezone.utc).isoformat()
        temp=args.out/'manifest.json.tmp'
        temp.write_text(json.dumps(state,indent=2)+'\n');temp.replace(args.out/'manifest.json')
    try:
        save();profile=SparePcieProfile(args.package)
        sources=[Path(__file__),ROOT/'opentpu/host/spare_c0182863.py',ROOT/'opentpu/host/board.py',
            ROOT/'opentpu/host/dual_pcie.py',ROOT/'opentpu/host/chestnut.py',
            ROOT/'tools/spare_runtime_c0182863.py',ROOT/'tools/run_lfm_spare_c0182863.py']
        state['sources']={str(path.relative_to(ROOT)):digest(path) for path in sources}
        state.update(package_manifest_sha256=profile.manifest_sha256,
                     bitstream_sha256=profile.bitstream_sha256,
                     status='OPENING_TRANSPORT',hardware_access_attempted=True,hardware_accessed=None)
        save()
        transport=(SpareJtagTransport(profile,args.xvc_host,args.xvc_port) if args.transport=='jtag' else SpareChestnutTransport(profile) if args.transport=='chestnut'
                   else SpareXdmaTransport(profile,args.dev))
        state['hardware_accessed']=True
        state['calibration_binding']=check_calibration_receipt(args.calibration_receipt,profile,transport)
        status=transport.reg_read(R.R_STATUS)
        require(not status&(R.ST_RUN|R.ST_LOADING|R.ST_ERROR|R.ST_AXI_ERR) and status&R.ST_WR_IDLE,
                'Compute must be idle and error-free')
        board=Board(transport,check=True,calibrate=False,program_receipts=args.out/'programs')
        state['identity']=board.info()
        require(state['identity']['build_id']==0xc0182863 and state['identity']['core_khz']==148837,
                'Image identity or clock differs')
        state['calibration_before']=calibration_snapshot(transport)
        require(transport.reg_read(R.R_SCRATCH)==R.DRAM_INIT,
                'Complete the exact-image LFM initialization first; benchmark does not initialize memory')
        program,plan=native_read_program(args.span)
        state['plan']=plan
        board.load_program(PROGRAM_AT,np.asarray(I.assemble(program),np.uint32))
        expected=board.read(args.span-SWEEP_CHUNK,SWEEP_CHUNK)
        state['expected_final_chunk_sha256']=payload_digest(expected)
        state['status']='NATIVE_READ_COUNTER_BENCHMARK_RUNNING';save()
        for repeat in range(args.repeats):
            transport.guard();before=board.snapshot()
            require(before is not None,'Performance counters unavailable')
            wall=time.perf_counter();stats=board.run(timeout=300);wall=time.perf_counter()-wall
            after=board.snapshot();require(after is not None,'Performance counters unavailable')
            delta={name:after[name]-before[name] for name in ('RUNNING','DRAM_RD','DRAM_WR')}
            row=dict(repeat=repeat,stats=stats,counter_before=before,counter_after=after,
                counter_delta=delta,host_run_call_seconds=wall)
            state['runs'].append(row);save()
            seconds=delta['RUNNING']/(state['identity']['core_khz']*1000)
            require(seconds>0 and delta['DRAM_RD']==args.span//64 and
                    delta['DRAM_WR']==SWEEP_CHUNK//64,'Device DRAM coverage counters differ')
            require(stats['instructions']==[plan['expected_instructions']] and
                    stats['b_reads']==plan['expected_b_reads'] and stats['b_writes']==plan['expected_b_writes'],
                    'Native instruction/beat coverage differs')
            actual=board.read(SWEEP_OUTPUT,SWEEP_CHUNK)
            row.update(final_chunk_sha256=payload_digest(actual),exact_final_chunk=bool(np.array_equal(actual,expected)))
            save();require(row['exact_final_chunk'],'Final read chunk differs; preserve state')
            row.update(device_seconds=seconds,logical_read_gbs=args.span/seconds/1e9,
                counter_total_gbs=(delta['DRAM_RD']+delta['DRAM_WR'])*64/seconds/1e9)
            transport.guard();save()
        state['calibration_after']=calibration_snapshot(transport)
        require(state['calibration_before']==state['calibration_after'],'Calibration changed')
        require(all(digest(ROOT/name)==value for name,value in state['sources'].items()),'Sources changed')
        state.update(status='PASS_OBSERVED_NATIVE_READ_BANDWIDTH_FULL_SYSTEM_QUALIFICATION_PENDING',
            median_logical_read_gbs=statistics.median(row['logical_read_gbs'] for row in state['runs']),
            temperature_after_c=board.info()['temp_c'],
            limitations=['Synthetic native reads; LLM/write bandwidth remain separate.',
                         'Only final-chunk data compared; USB run-call wall time includes transport overhead.'])
    except BaseException as error:
        state.update(status='FAIL',error=repr(error));raise
    finally:
        try:
            if board is not None:board.close()
        finally:
            try:
                if transport is not None:transport.close()
            finally:save()


if __name__=='__main__':main()
